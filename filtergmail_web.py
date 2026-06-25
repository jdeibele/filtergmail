# filtergmail_web.py — filtergmail.com main web application
# Version: 1.0.0 | 2026-06-11
# Stage 1: Filter table + community inspiration feed

import os
import sqlite3

from flask import Flask, g, jsonify, render_template, request, Response

from gmail_filter import (MATCHING_FIELDS, build_filters, generate_gmail_xml,
                          audit_filters, parse_gmail_xml, build_safe_filter,
                          consolidate_by_label, detect_field)
import gmail_paste
import starter_filters
import formats

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024

DB_PATH = os.environ.get("FILTERGMAIL_DB", "/data/filtergmail.db")
# The product is free. This is no longer a paywall — just a sane abuse ceiling so one
# request can't paste 10k rows and hammer the DB. (Jim 2026-06-25: "we're not charging".)
FREE_TIER_LIMIT = 100
MAX_FIELD_LEN = 200

# Brand is a single env-driven constant so a forced rename (if Google objects to the
# "gmail" trademark in the domain) is one config change + a new domain — no code edit.
# Strategy: launch + publicize as filtergmail.com; flip BRAND/DOMAIN and publicize the
# rename if/when a cease-and-desist arrives.
BRAND = os.environ.get("FILTERGMAIL_BRAND", "filtergmail.com")
TAGLINE = os.environ.get("FILTERGMAIL_TAGLINE", "Control your inbox")
# Corrections inbox for the "Roll Your Own" page. NOTE: this address must actually receive
# mail before launch (domain MX / forwarder), or the CTA bounces.
CORRECTIONS_EMAIL = os.environ.get("FILTERGMAIL_CORRECTIONS_EMAIL", "corrections@filtergmail.com")
# Minimum count for a pattern to appear in the community feed. Stage 1 shows
# everything (>= 1); bump to 3 or 5 once there is meaningful traffic to filter
# out one-off patterns (see CLAUDE.md "Known issues / tech debt").
FEED_MIN_COUNT = 1


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA journal_mode=WAL")
        _migrate(g.db)
    return g.db


@app.teardown_appcontext
def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def _migrate(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS patterns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pattern TEXT NOT NULL,
            label TEXT NOT NULL,
            field TEXT NOT NULL,
            count INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(pattern, label, field)
        )
    """)
    conn.commit()


def _record_patterns(filters):
    # `filters` are the enriched dicts from build_filters: pattern/label already
    # stripped, blanks dropped, and the matching field resolved via safe_field.
    # Reuse that work instead of re-validating the raw rows here.
    db = get_db()
    for f in filters:
        field = next((k for k in f if k in MATCHING_FIELDS), None)
        if field is None:
            continue
        pattern = f[field].strip().lower()
        label = f["label"].strip()
        if pattern and label:
            db.execute("""
                INSERT INTO patterns (pattern, label, field, count) VALUES (?, ?, ?, 1)
                ON CONFLICT(pattern, label, field) DO UPDATE SET count = count + 1
            """, (pattern, label, field))
    db.commit()


def _top_patterns(limit=40):
    db = get_db()
    rows = db.execute("""
        SELECT pattern, label, field, count
        FROM patterns
        WHERE count >= ?
        ORDER BY count DESC, pattern ASC
        LIMIT ?
    """, (FEED_MIN_COUNT, limit)).fetchall()
    return [dict(r) for r in rows]


@app.route("/")
def index():
    top = _top_patterns()
    return render_template("index.html", top_patterns=top, max_rows=FREE_TIER_LIMIT,
                           brand=BRAND, tagline=TAGLINE)


def _rows_to_filters(rows):
    """Turn the UI's working-list rows into safe filter dicts. Each row:
    {pattern|<field>, label, action?, field?}. Action defaults to 'trash' (every row already
    carries a reason-label; build_safe_filter enforces the safety rules)."""
    built = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        label = (r.get("label") or "").strip()[:MAX_FIELD_LEN]
        action = (r.get("action") or "trash").strip().lower()
        crit = {}
        for k in MATCHING_FIELDS:
            v = r.get(k)
            if isinstance(v, str) and v.strip():
                crit[k] = v.strip()[:MAX_FIELD_LEN]
        if not crit:                                   # legacy {pattern, field?}
            pat = (r.get("pattern") or "").strip()[:MAX_FIELD_LEN]
            if pat:
                fld = r.get("field") if r.get("field") in MATCHING_FIELDS else detect_field(pat)
                crit = {fld: pat}
        if not crit or not label:
            continue
        try:
            f, _ = build_safe_filter(crit, label, action)
            built.append(f)
        except ValueError:
            continue
    return built


@app.route("/download", methods=["POST"])
def download():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "No data"}), 400
    rows = data.get("filters") or data.get("rows")    # new model | legacy
    if not isinstance(rows, list) or not rows:
        return jsonify({"error": "No filters provided"}), 400
    if len(rows) > FREE_TIER_LIMIT:
        return jsonify({"error": f"Up to {FREE_TIER_LIMIT} filters at a time; received {len(rows)}"}), 400

    built = _rows_to_filters(rows)
    if not built:
        return jsonify({"error": "No valid filters (each needs a pattern and a label)."}), 400
    _record_patterns(built)
    if data.get("consolidate"):
        built = consolidate_by_label(built)

    fmt = (data.get("format") or "xml").lower()
    if fmt in formats.EXPORTERS:
        body = formats.EXPORTERS[fmt](built)
        mime = "application/json" if fmt == "json" else "text/plain; charset=utf-8"
        ext = fmt
    else:
        body, mime, ext = generate_gmail_xml(built), "application/xml", "xml"
    return Response(body, mimetype=mime, headers={
        "Content-Disposition": f"attachment; filename=gmail_filters.{ext}"})


@app.route("/parse", methods=["POST"])
def parse():
    """Paste-the-Gmail-details → a suggested safe filter. Backend for the (still to be
    designed) paste box. Body: JSON {"text": "<pasted details>"}. Returns the analysis:
    {kind, filter, reason, warnings, alternatives, evidence}. No account access, no storage —
    pure text in, suggestion out."""
    data = request.get_json(silent=True)
    text = (data or {}).get("text", "") if isinstance(data, dict) else ""
    user_email = (data or {}).get("user_email") if isinstance(data, dict) else None
    if not isinstance(text, str) or not text.strip():
        return jsonify({"error": "Paste the Gmail message details (the from/subject/mailed-by block)."}), 400
    if len(text) > 20000:
        return jsonify({"error": "Input too large."}), 400
    try:
        result = gmail_paste.analyze(text, user_email=user_email if isinstance(user_email, str) else None)
    except Exception:
        return jsonify({"error": "Could not parse that — paste the details block from Gmail."}), 400
    return jsonify(result)


@app.route("/roll-your-own")
def roll_your_own():
    """DIY / how-Gmail-filters-actually-work page for the power crowd — XML, the {} trick,
    the ~500 cap, the Advanced Protection note, editors, and a corrections email."""
    return render_template("roll_your_own.html", brand=BRAND, tagline=TAGLINE,
                           corrections_email=CORRECTIONS_EMAIL)


@app.route("/api/starter")
def api_starter():
    """Curated starter-filter library (Bills/Banking/Shopping/Travel/Social) for the
    one-click 'senders everyone has' on-ramp. Read-only catalog for the UI."""
    return jsonify(starter_filters.starter_catalog())


@app.route("/analyze", methods=["POST"])
def analyze_existing():
    """'Bring your existing filters': accept a pasted/exported Gmail mailFilters.xml and
    return a safety + hygiene audit (missing reason-labels, silent mark-as-read on one
    field, duplicate senders, label taxonomy). Read-only — nothing stored."""
    data = request.get_json(silent=True)
    xml = (data or {}).get("xml", "") if isinstance(data, dict) else ""
    if not isinstance(xml, str) or not xml.strip():
        return jsonify({"error": "Paste your exported Gmail filters XML (Settings → Filters → Export)."}), 400
    try:
        filters = parse_gmail_xml(xml.encode("utf-8"))
    except Exception:
        return jsonify({"error": "That doesn't look like a Gmail filters export."}), 400
    return jsonify(audit_filters(filters))


@app.route("/api/patterns")
def api_patterns():
    return jsonify(_top_patterns())


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5060))
    app.run(host="0.0.0.0", port=port, debug=False)

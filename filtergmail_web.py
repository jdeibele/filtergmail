# filtergmail_web.py — filtergmail.com main web application
# Version: 1.0.0 | 2026-06-11
# Stage 1: Filter table + community inspiration feed

import os
import sqlite3

from flask import Flask, g, jsonify, render_template, request, Response

from gmail_filter import MATCHING_FIELDS, build_filters, generate_gmail_xml
import gmail_paste

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


@app.route("/download", methods=["POST"])
def download():
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not data.get("rows"):
        return jsonify({"error": "No rows provided"}), 400
    if not isinstance(data["rows"], list):
        return jsonify({"error": "rows must be a list"}), 400

    rows = [
        r for r in data["rows"]
        if isinstance(r, dict)
        and isinstance(r.get("pattern"), str) and r["pattern"].strip()
        and len(r["pattern"]) <= MAX_FIELD_LEN
        and isinstance(r.get("label"), str) and r["label"].strip()
        and len(r["label"]) <= MAX_FIELD_LEN
    ]
    if not rows:
        return jsonify({"error": "No valid rows"}), 400

    if len(rows) > FREE_TIER_LIMIT:
        return jsonify({"error": f"Free tier allows up to {FREE_TIER_LIMIT} filters; received {len(rows)}"}), 400

    filters = build_filters(rows)
    _record_patterns(filters)

    xml = generate_gmail_xml(filters)
    return Response(
        xml,
        mimetype="application/xml",
        headers={"Content-Disposition": "attachment; filename=gmail_filters.xml"},
    )


@app.route("/parse", methods=["POST"])
def parse():
    """Paste-the-Gmail-details → a suggested safe filter. Backend for the (still to be
    designed) paste box. Body: JSON {"text": "<pasted details>"}. Returns the analysis:
    {kind, filter, reason, warnings, alternatives, evidence}. No account access, no storage —
    pure text in, suggestion out."""
    data = request.get_json(silent=True)
    text = (data or {}).get("text", "") if isinstance(data, dict) else ""
    if not isinstance(text, str) or not text.strip():
        return jsonify({"error": "Paste the Gmail message details (the from/subject/mailed-by block)."}), 400
    if len(text) > 20000:
        return jsonify({"error": "Input too large."}), 400
    try:
        result = gmail_paste.analyze(text)
    except Exception:
        return jsonify({"error": "Could not parse that — paste the details block from Gmail."}), 400
    return jsonify(result)


@app.route("/api/patterns")
def api_patterns():
    return jsonify(_top_patterns())


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5060))
    app.run(host="0.0.0.0", port=port, debug=False)

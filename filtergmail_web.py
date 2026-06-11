# filtergmail_web.py — filtergmail.com main web application
# Version: 1.0.0 | 2026-06-11
# Stage 1: Filter table + community inspiration feed

import os
import sqlite3

from flask import Flask, g, jsonify, render_template, request, Response

from gmail_filter import build_filters, detect_field, generate_gmail_xml

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024

DB_PATH = os.environ.get("FILTERGMAIL_DB", "/data/filtergmail.db")
FREE_TIER_LIMIT = 5


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
    if db:
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


def _record_patterns(rows):
    db = get_db()
    for row in rows:
        pattern = row.get("pattern", "").strip().lower()
        label = row.get("label", "").strip()
        field = row.get("field") or detect_field(row.get("pattern", ""))
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
        WHERE count >= 1
        ORDER BY count DESC, pattern ASC
        LIMIT ?
    """, (limit,)).fetchall()
    return [dict(r) for r in rows]


@app.route("/")
def index():
    top = _top_patterns()
    return render_template("index.html", top_patterns=top)


@app.route("/download", methods=["POST"])
def download():
    data = request.get_json()
    if not data or not data.get("rows"):
        return jsonify({"error": "No rows provided"}), 400

    rows = [r for r in data["rows"] if r.get("pattern", "").strip() and r.get("label", "").strip()]
    rows = rows[:FREE_TIER_LIMIT]

    if not rows:
        return jsonify({"error": "No valid rows"}), 400

    filters = build_filters(rows)
    _record_patterns(rows)

    xml = generate_gmail_xml(filters)
    return Response(
        xml,
        mimetype="application/xml",
        headers={"Content-Disposition": "attachment; filename=gmail_filters.xml"},
    )


@app.route("/api/patterns")
def api_patterns():
    return jsonify(_top_patterns())


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5060))
    app.run(host="0.0.0.0", port=port, debug=False)

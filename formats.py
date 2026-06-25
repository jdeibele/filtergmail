# formats.py — import/export the filter model as YAML / CSV / JSON
# Version: 0.1.0 | 2026-06-25
#
# One canonical model: a list of filter dicts (Gmail's own keys — `from`, `subject`,
# `label`, `shouldArchive`/`shouldTrash`/…), the exact thing generate_gmail_xml consumes
# and parse_gmail_xml produces. Every format below is just a codec around that model, so
# the round-trip is XML ⇄ {yaml,csv,json} for free.
#
# YAML matches Jim's existing filters.yaml schema (raw Gmail-key dicts + comments) — for
# the power/HN crowd. CSV is the spreadsheet lane (friendly columns). JSON is for tooling.
# PyYAML is lazy-imported so CSV/JSON work even where it isn't installed.

import csv
import io
import json

from gmail_filter import MATCHING_FIELDS, ACTION_PROPS, build_safe_filter

# Friendly, fixed columns for the spreadsheet crowd (one row per filter).
CSV_COLUMNS = ["from", "subject", "hasTheWord", "doesNotHaveTheWord", "label", "action"]


def _action_of(f):
    """Reverse a filter dict's should* props back to an action name for CSV display."""
    props = {k: f[k] for k in f if k.startswith("should")}
    for name, p in ACTION_PROPS.items():
        if props == p:
            return name
    if f.get("shouldTrash") == "true":
        return "trash"
    if f.get("shouldMarkAsRead") == "true":
        return "read"
    if f.get("shouldArchive") == "true":
        return "archive"
    return "keep"


def _normalize(d):
    """Validate one raw filter dict from YAML/JSON import (Jim's schema: Gmail keys). Keeps
    matching fields + label + should* props; drops unsupported keys (e.g. sizeOperator).
    Returns the cleaned dict, or None if it has no criteria / no label."""
    if not isinstance(d, dict):
        return None
    crit = {k: str(d[k]) for k in d if k in MATCHING_FIELDS and str(d.get(k) or "").strip()}
    label = str(d.get("label", "")).strip()
    if not crit or not label:
        return None
    f = dict(crit)
    f["label"] = label
    for k in d:
        if k.startswith("should") and str(d[k]).lower() == "true":
            f[k] = "true"
    return f


# ── JSON ──────────────────────────────────────────────────────────────────────
def to_json(filters):
    return json.dumps(filters, indent=2)


def from_json(text):
    data = json.loads(text)
    if not isinstance(data, list):
        raise ValueError("expected a JSON list of filter objects")
    return [f for f in (_normalize(d) for d in data) if f]


# ── YAML (matches filters.yaml) ─────────────────────────────────────────────────
def to_yaml(filters):
    import yaml  # lazy — only needed for YAML
    return yaml.safe_dump(filters, sort_keys=False, allow_unicode=True, default_flow_style=False)


def from_yaml(text):
    import yaml
    data = yaml.safe_load(text) or []
    if not isinstance(data, list):
        raise ValueError("expected a YAML list of filters")
    return [f for f in (_normalize(d) for d in data) if f]


# ── CSV (spreadsheet-friendly) ──────────────────────────────────────────────────
def to_csv(filters):
    out = io.StringIO()
    w = csv.DictWriter(out, fieldnames=CSV_COLUMNS, extrasaction="ignore")
    w.writeheader()
    for f in filters:
        row = {c: f.get(c, "") for c in CSV_COLUMNS if c != "action"}
        row["action"] = _action_of(f)
        w.writerow(row)
    return out.getvalue()


def from_csv(text):
    out = []
    for r in csv.DictReader(io.StringIO(text)):
        crit = {k: (r.get(k) or "").strip() for k in MATCHING_FIELDS if (r.get(k) or "").strip()}
        label = (r.get("label") or "").strip()
        action = (r.get("action") or "trash").strip().lower()
        if not crit or not label:
            continue
        try:
            f, _ = build_safe_filter(crit, label, action)
            out.append(f)
        except ValueError:
            continue
    return out


# Dispatch by format name (used by the export/import routes).
EXPORTERS = {"json": to_json, "yaml": to_yaml, "csv": to_csv}
IMPORTERS = {"json": from_json, "yaml": from_yaml, "csv": from_csv}

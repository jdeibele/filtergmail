# gmail_filter.py — filtergmail.com Gmail filter XML utilities
# Version: 1.0.0 | 2026-06-11

import io
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

ATOM_NS = "http://www.w3.org/2005/Atom"
APPS_NS = "http://schemas.google.com/apps/2006"

FILTER_FIELDS = [
    "from", "to", "subject", "hasTheWord", "doesNotHaveTheWord",
    "label", "shouldTrash", "shouldArchive", "shouldMarkAsRead",
    "shouldNeverSpam", "shouldNeverMarkAsImportant",
]

# Fields a client is allowed to choose for a pattern. Matching criteria only —
# never action fields (shouldTrash/shouldArchive/etc.), which would let a
# request (or a poisoned community chip) generate destructive filters.
MATCHING_FIELDS = frozenset({
    "from", "to", "subject", "hasTheWord", "doesNotHaveTheWord",
})


def safe_field(field, pattern: str) -> str:
    """Return a trusted matching field: the client value only if allowlisted,
    otherwise the auto-detected field for the pattern."""
    if isinstance(field, str) and field in MATCHING_FIELDS:
        return field
    return detect_field(pattern)


# Common TLDs used to decide whether a dotted token is a sender domain
# rather than a body keyword that merely contains a dot (e.g. node.js).
_KNOWN_TLDS = frozenset({
    "com", "org", "net", "edu", "gov", "mil", "int", "io", "co", "us",
    "uk", "ca", "de", "fr", "jp", "au", "nl", "ru", "ch", "it", "es",
    "se", "no", "fi", "dk", "be", "at", "nz", "in", "br", "mx", "info",
    "biz", "me", "tv", "app", "dev", "ai", "xyz", "online", "site",
    "tech", "store", "blog", "news", "email", "cloud", "live", "eu",
})

_DOMAIN_RE = re.compile(
    r"^[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?"
    r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?)*"
    r"\.([A-Za-z]{2,})$"
)


def detect_field(pattern: str) -> str:
    """Determine the Gmail filter field for a pattern string."""
    p = pattern.strip()
    if "@" in p:
        return "from"
    if " " not in p:
        m = _DOMAIN_RE.match(p)
        if m and m.group(1).lower() in _KNOWN_TLDS:
            return "from"
    return "hasTheWord"


def build_filters(rows: list[dict]) -> list[dict]:
    """Convert table rows [{pattern, label, field?}] to Gmail filter dicts."""
    filters = []
    for row in rows:
        pattern = row.get("pattern", "").strip()
        label = row.get("label", "").strip()
        if not pattern or not label:
            continue
        field = safe_field(row.get("field"), pattern)
        filters.append({
            field: pattern,
            "label": label,
            "shouldArchive": "true",
        })
    return filters


# ── Safety model (Jim's two rules, 2026-06-25) ──────────────────────────────────
# Together these guarantee: every filter action is either AUDITABLE (carries a
# reason-label you can find later) or HIGH-CONFIDENCE (matches 2+ criteria). Nothing
# is ever both silent AND low-confidence.
#
# Rule 1 — the label is the receipt. Every filter MUST carry a reason-label, so a
#   message that was archived/trashed tells you WHY (and which rule) — searchable as
#   `in:trash label:"Junk mail/<reason>"`. Never emit a bare action.
#
# Rule 2 — action aggressiveness scales with match confidence, by recoverability:
#   archive / trash are AUDITABLE — the message survives under the label (archive) or
#     in Trash for 30 days (trash), so a false positive is visible and recoverable.
#     Allowed on a single matching field.
#   mark-as-read is SILENT and effectively unrecoverable — a wrongly-read message
#     blends into "I already handled it" and is never noticed. So it requires >= 2
#     matching criteria; asked for on a single field it is DOWNGRADED to trash
#     (auditable) with a warning.
ACTION_PROPS = {
    "keep":    {},                                                      # label only, stays in inbox
    "archive": {"shouldArchive": "true"},                               # skip inbox, keep
    "trash":   {"shouldTrash": "true"},                                 # Trash (30d, auditable)
    "read":    {"shouldMarkAsRead": "true", "shouldArchive": "true"},   # silent auto-handle
}
DEFAULT_ACTION = "trash"
MIN_FIELDS_FOR_READ = 2


def build_safe_filter(criteria: dict, label: str, action: str = DEFAULT_ACTION):
    """Build ONE Gmail filter dict that obeys both safety rules.

    criteria: {matching_field: pattern} (one or more of MATCHING_FIELDS).
    label:    the reason-label (required — the receipt).
    action:   'archive' | 'trash' | 'read'.
    Returns (filter_dict, warnings:list[str]). Raises ValueError on no criteria / no label.
    """
    warnings: list[str] = []
    crit = {
        k: v.strip()
        for k, v in (criteria or {}).items()
        if k in MATCHING_FIELDS and isinstance(v, str) and v.strip()
    }
    label = (label or "").strip()
    if not crit:
        raise ValueError("a filter needs at least one matching criterion")
    if not label:
        raise ValueError("every filter must carry a reason-label (the label is the receipt)")
    action = action if action in ACTION_PROPS else DEFAULT_ACTION
    if action == "read" and len(crit) < MIN_FIELDS_FOR_READ:
        warnings.append(
            "mark-as-read is silent and unrecoverable; on a single criterion it was "
            "downgraded to trash (auditable). Add a second criterion to mark-as-read.")
        action = "trash"
    f = dict(crit)
    f["label"] = label
    f.update(ACTION_PROPS[action])
    return f, warnings


def generate_gmail_xml(filters: list[dict]) -> str:
    """Generate Gmail filter XML from a list of filter dicts."""
    ET.register_namespace("", ATOM_NS)
    ET.register_namespace("apps", APPS_NS)

    feed = ET.Element(f"{{{ATOM_NS}}}feed")
    ET.SubElement(feed, f"{{{ATOM_NS}}}title").text = "Mail Filters"
    ET.SubElement(feed, f"{{{ATOM_NS}}}updated").text = datetime.now(timezone.utc).isoformat()

    for f in filters:
        entry = ET.SubElement(feed, f"{{{ATOM_NS}}}entry")
        ET.SubElement(entry, f"{{{ATOM_NS}}}category", {"term": "filter"})
        ET.SubElement(entry, f"{{{ATOM_NS}}}content").text = ""
        for field in FILTER_FIELDS:
            if field in f and f[field] is not None:
                ET.SubElement(entry, f"{{{APPS_NS}}}property", {
                    "name": field,
                    "value": str(f[field]),
                })

    tree = ET.ElementTree(feed)
    ET.indent(tree, space="  ")
    buf = io.BytesIO()
    tree.write(buf, encoding="utf-8", xml_declaration=True)
    return buf.getvalue().decode("utf-8")


# Hardening for parse_gmail_xml (Stage 2/3 upload). Python's stdlib
# ElementTree does not resolve external entities, but offers no protection
# against entity-expansion ("billion laughs") DoS. Reject any DOCTYPE/entity
# declarations and cap input size before parsing. (Prefer defusedxml here once
# it is added to requirements.)
MAX_XML_BYTES = 1 * 1024 * 1024  # 1 MiB
_DOCTYPE_RE = re.compile(rb"<!DOCTYPE", re.IGNORECASE)
_ENTITY_RE = re.compile(rb"<!ENTITY", re.IGNORECASE)


def consolidate_by_label(filters: list[dict]) -> list[dict]:
    """Power-user export option: merge single-`from` filters that share the SAME label and
    SAME action into one filter using Gmail's airtight brace OR-grouping —
    `from: '{"a.com" "b.com"}'`. Cuts filter count to stay under Gmail's ~500 cap (Google's
    own advice). Filters with a subject/other or multiple criteria pass through unchanged.
    Per-sender remains the default; callers opt into this. Returns a new list."""
    groups, passthrough = {}, []
    for f in filters:
        crit = [k for k in f if k in MATCHING_FIELDS]
        fv = f.get("from", "")
        if crit == ["from"] and fv and "{" not in fv:
            props = tuple(sorted((k, f[k]) for k in f if k.startswith("should")))
            g = groups.setdefault((f.get("label", ""), props),
                                  {"froms": [], "props": props, "label": f.get("label", "")})
            if fv not in g["froms"]:
                g["froms"].append(fv)
        else:
            passthrough.append(f)
    out = []
    for g in groups.values():
        froms = g["froms"]
        merged = {"from": froms[0] if len(froms) == 1
                  else "{" + " ".join('"%s"' % v for v in froms) + "}"}
        if g["label"]:
            merged["label"] = g["label"]
        merged.update(dict(g["props"]))
        out.append(merged)
    out.extend(passthrough)
    return out


def audit_filters(filters: list[dict]) -> dict:
    """Audit an existing parsed filter list against the safety model + light hygiene —
    backs the 'bring your existing filters' (/analyze) feature. Returns a report dict:
      count, issues[{type,msg,filter}], duplicate_senders{value:[indexes]}, labels{label:n}.
    """
    issues, seen_from, labels = [], {}, {}
    for i, f in enumerate(filters):
        crit = {k: f[k] for k in f if k in MATCHING_FIELDS}
        label = f.get("label")
        acted = any(f.get(a) == "true" for a in ("shouldTrash", "shouldArchive", "shouldMarkAsRead"))
        if acted and not label:
            issues.append({"type": "no_label", "filter": f,
                           "msg": "Acts on mail with no reason-label — you won't know why it was filed/trashed."})
        if f.get("shouldMarkAsRead") == "true" and len(crit) < MIN_FIELDS_FOR_READ:
            issues.append({"type": "read_low_confidence", "filter": f,
                           "msg": "Marks as read on a single criterion — silent and unrecoverable. "
                                  "Add a second criterion, or trash instead."})
        fv = (f.get("from") or "").lower()
        if fv:
            seen_from.setdefault(fv, []).append(i)
        if label:
            labels[label] = labels.get(label, 0) + 1
    dupes = {v: idxs for v, idxs in seen_from.items() if len(idxs) > 1}
    return {"count": len(filters), "issues": issues,
            "duplicate_senders": dupes, "labels": labels}


def parse_gmail_xml(xml_bytes: bytes) -> list[dict]:
    """Parse Gmail filter XML into a list of filter dicts."""
    if len(xml_bytes) > MAX_XML_BYTES:
        raise ValueError("XML input too large")
    if _DOCTYPE_RE.search(xml_bytes) or _ENTITY_RE.search(xml_bytes):
        raise ValueError("DOCTYPE and entity declarations are not allowed")
    root = ET.fromstring(xml_bytes)
    ns = {"atom": ATOM_NS, "apps": APPS_NS}
    filters = []
    for entry in root.findall("atom:entry", ns):
        f = {}
        for prop in entry.findall("apps:property", ns):
            name = prop.get("name")
            value = prop.get("value")
            if name and value is not None:
                f[name] = value
        if f:
            filters.append(f)
    return filters

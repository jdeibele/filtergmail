# gmail_filter.py — filtergmail.com Gmail filter XML utilities
# Version: 1.0.0 | 2026-06-11

import io
import xml.etree.ElementTree as ET
from datetime import datetime

ATOM_NS = "http://www.w3.org/2005/Atom"
APPS_NS = "http://schemas.google.com/apps/2006"

FILTER_FIELDS = [
    "from", "to", "subject", "hasTheWord", "doesNotHaveTheWord",
    "label", "shouldTrash", "shouldArchive", "shouldMarkAsRead",
    "shouldNeverSpam", "shouldNeverMarkAsImportant",
]


def detect_field(pattern: str) -> str:
    """Determine the Gmail filter field for a pattern string."""
    p = pattern.strip()
    if "@" in p:
        return "from"
    if " " not in p and "." in p and len(p) > 3:
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
        field = row.get("field") or detect_field(pattern)
        filters.append({
            field: pattern,
            "label": label,
            "shouldArchive": "true",
        })
    return filters


def generate_gmail_xml(filters: list[dict]) -> str:
    """Generate Gmail filter XML from a list of filter dicts."""
    ET.register_namespace("", ATOM_NS)
    ET.register_namespace("apps", APPS_NS)

    feed = ET.Element(f"{{{ATOM_NS}}}feed")
    ET.SubElement(feed, f"{{{ATOM_NS}}}title").text = "Mail Filters"
    ET.SubElement(feed, f"{{{ATOM_NS}}}updated").text = datetime.utcnow().isoformat() + "Z"

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


def parse_gmail_xml(xml_bytes: bytes) -> list[dict]:
    """Parse Gmail filter XML into a list of filter dicts."""
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

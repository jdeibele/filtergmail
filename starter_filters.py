# starter_filters.py — curated ready-made filters for senders everyone has
# Version: 0.1.0 | 2026-06-25
#
# The blank-page killer: a new user picks "Chase, Xfinity, Amazon" and gets working
# filters + (Gmail auto-creates) the labels — no XML, no label setup. Every starter goes
# through gmail_filter.build_safe_filter, so the reason-label is the category and the
# action obeys the safety model.
#
# DEFAULT ACTION is conservative (Jim 2026-06-25, "don't hide a bank fraud alert"):
#   'keep'    = apply the label, LEAVE it in the inbox — nothing hidden. Default for
#               anything you might need to see (banks, bills, shopping, travel).
#   'archive' = label + skip inbox. Only for low-stakes promotional mail (social).
# Flip a category's action below to change the default; the UI can also offer per-pick choice.
#
# Domains are registrable domains Gmail's `from:` will match (incl. subdomains). A few use a
# dedicated mail domain (Facebook -> facebookmail.com). This is a confident STARTER set to
# expand/verify against real sending domains later.

from gmail_filter import build_safe_filter

STARTER_FILTERS = {
    "Banking": {"action": "keep", "senders": [
        ("Chase", "chase.com"), ("Bank of America", "bankofamerica.com"),
        ("Wells Fargo", "wellsfargo.com"), ("Citi", "citi.com"),
        ("Capital One", "capitalone.com"), ("American Express", "americanexpress.com"),
        ("PayPal", "paypal.com"),
    ]},
    "Bills & Utilities": {"action": "keep", "senders": [
        ("Xfinity / Comcast", "xfinity.com"), ("Verizon", "verizon.com"),
        ("AT&T", "att.com"), ("T-Mobile", "t-mobile.com"), ("PG&E", "pge.com"),
    ]},
    "Shopping": {"action": "keep", "senders": [
        ("Amazon", "amazon.com"), ("eBay", "ebay.com"), ("Etsy", "etsy.com"),
        ("Walmart", "walmart.com"), ("Target", "target.com"),
    ]},
    "Travel": {"action": "keep", "senders": [
        ("United", "united.com"), ("Delta", "delta.com"),
        ("American Airlines", "aa.com"), ("Southwest", "southwest.com"),
        ("Airbnb", "airbnb.com"), ("Marriott", "marriott.com"),
    ]},
    "Social": {"action": "archive", "senders": [
        ("Facebook", "facebookmail.com"), ("LinkedIn", "linkedin.com"),
        ("Instagram", "mail.instagram.com"), ("X / Twitter", "x.com"),
        ("Reddit", "redditmail.com"), ("Pinterest", "pinterest.com"),
    ]},
}


def starter_catalog():
    """The library as plain JSON-able data for the UI: category -> {action, senders[]}."""
    return {
        cat: {"action": v["action"],
              "senders": [{"name": n, "domain": d} for n, d in v["senders"]]}
        for cat, v in STARTER_FILTERS.items()
    }


def build_starter_filters(selections):
    """selections: list of {"domain": ..., "label"?: ...}. Returns (filters, warnings).
    Unknown domains are skipped. Label defaults to the sender's category."""
    index = {
        d: (cat, v["action"])
        for cat, v in STARTER_FILTERS.items() for _n, d in v["senders"]
    }
    filters, warnings = [], []
    for sel in selections or []:
        d = (sel or {}).get("domain", "")
        meta = index.get(d)
        if not meta:
            continue
        category, action = meta
        label = (sel.get("label") or "").strip() or category
        f, w = build_safe_filter({"from": d}, label, action=action)
        filters.append(f)
        warnings += w
    return filters, warnings

# tests/test_filtergmail.py — paste-parser + safety-rule tests
# Version: 0.1.0 | 2026-06-25
#
# Runs under pytest, OR standalone for environments without pytest:  python3 tests/test_filtergmail.py
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gmail_filter import (build_safe_filter, generate_gmail_xml, parse_gmail_xml,
                          audit_filters)
import gmail_paste as gp
import starter_filters as sf

# Real-world spam, exactly as Gmail's "details" block renders it (Jim's two examples).
EX_SENDER = """from:    Harbor.Freight.Surprise <fsfawkr@oopppmaj.hhi.yourwebsitesortedssl.com>
sent by:    Trusted Sender <jdeibele@gmail.com>
to:    me@aol.com
date:    Jun 24, 2026, 4:30 PM
subject:    Surprise in your inbox (for Harbor Freight customers Only)
mailed-by:    hhi.yourwebsitesortedssl.com
signed-by:    oopppmaj.hhi.yourwebsitesortedssl.com"""

EX_SUBJECT = """from:    jdeibele <fuonqurcicw@eqke.vjmkraodjhpja.us> via hss2719.secureserver.cpcalendars.dedomenico.ehost-services214.com.thandful.net
sent by:    bljlanqhmp
to:    jdeibele@gmail.com
date:    Jun 24, 2026, 8:30 PM
subject:    jdeibele¸Your Account Has been Blocked! Your Photos and Videos will be Removed Wed,24 Jun-2026. take action!!
mailed-by:    hss2719.secureserver.cpcalendars.dedomenico.ehost-services214.com.thandful.net"""


# ── safety rules ────────────────────────────────────────────────────────────────

def test_label_is_mandatory():
    try:
        build_safe_filter({"from": "x.com"}, "")
        assert False, "missing label must raise"
    except ValueError:
        pass

def test_criteria_required():
    try:
        build_safe_filter({}, "Junk")
        assert False, "no criteria must raise"
    except ValueError:
        pass

def test_single_field_read_downgrades_to_trash():
    f, warns = build_safe_filter({"from": "x.com"}, "Junk/Sender", action="read")
    assert "shouldMarkAsRead" not in f, "single-field mark-as-read must be downgraded"
    assert f.get("shouldTrash") == "true"
    assert warns, "downgrade must warn"

def test_two_field_read_allowed():
    f, warns = build_safe_filter({"from": "x.com", "subject": "win"}, "Junk", action="read")
    assert f.get("shouldMarkAsRead") == "true"
    assert not warns

def test_every_action_carries_label():
    for act in ("archive", "trash", "read"):
        f, _ = build_safe_filter({"from": "a.com", "subject": "b"}, "Junk/Reason", action=act)
        assert f.get("label") == "Junk/Reason"


# ── registrable domain + disposable detection ───────────────────────────────────

def test_registrable_domain():
    assert gp.registrable_domain("oopppmaj.hhi.yourwebsitesortedssl.com") == "yourwebsitesortedssl.com"
    assert gp.registrable_domain("a.b.c.thandful.net") == "thandful.net"
    assert gp.registrable_domain("news.example.co.uk") == "example.co.uk"

def test_disposable_detection():
    assert gp.looks_disposable("vjmkraodjhpja.us")           # gibberish
    assert not gp.looks_disposable("yourwebsitesortedssl.com")  # word-salad but stable
    assert not gp.looks_disposable("conservicemail.com")
    assert not gp.looks_disposable("mailchimp.com")


# ── the two decisions ───────────────────────────────────────────────────────────

def test_stable_sender_becomes_from_filter():
    a = gp.analyze(EX_SENDER)
    assert a["kind"] == "sender"
    assert a["filter"]["from"] == "yourwebsitesortedssl.com"
    assert a["filter"]["shouldTrash"] == "true"
    assert a["filter"]["label"] == gp.LABEL_SENDER

def test_rotating_sender_becomes_subject_filter():
    a = gp.analyze(EX_SUBJECT)
    assert a["kind"] == "subject"
    assert "blocked" in a["filter"]["subject"].lower()
    assert a["filter"]["shouldTrash"] == "true"
    assert a["filter"]["label"] == gp.LABEL_SUBJECT
    # the durable phrase must NOT carry the date / order number (over-fitting)
    assert "2026" not in a["filter"]["subject"]


# ── XML round-trip (generated filters import & re-parse cleanly) ─────────────────

def test_generated_xml_roundtrips():
    f1 = gp.analyze(EX_SENDER)["filter"]
    f2 = gp.analyze(EX_SUBJECT)["filter"]
    xml = generate_gmail_xml([f1, f2])
    back = parse_gmail_xml(xml.encode("utf-8"))
    assert len(back) == 2
    assert back[0]["from"] == "yourwebsitesortedssl.com"
    assert all("label" in f for f in back), "every filter must keep its reason-label"


# ── 'keep' action (starter filters: label only, stays in inbox) ──────────────────

def test_keep_action_is_label_only():
    f, warns = build_safe_filter({"from": "chase.com"}, "Banking", action="keep")
    assert f.get("label") == "Banking"
    assert "shouldArchive" not in f and "shouldTrash" not in f and "shouldMarkAsRead" not in f
    assert not warns


# ── audit existing filters (/analyze) ───────────────────────────────────────────

def test_audit_flags_violations():
    filters = [
        {"from": "a.com", "shouldTrash": "true"},                       # no label
        {"from": "b.com", "shouldMarkAsRead": "true", "label": "X"},    # read on 1 field
        {"from": "amazon.com", "label": "Shop", "shouldArchive": "true"},
        {"from": "amazon.com", "label": "Promo", "shouldArchive": "true"},  # dup sender
    ]
    rep = audit_filters(filters)
    types = {i["type"] for i in rep["issues"]}
    assert "no_label" in types
    assert "read_low_confidence" in types
    assert "amazon.com" in rep["duplicate_senders"]
    assert rep["count"] == 4


# ── starter-filter library ───────────────────────────────────────────────────────

def test_starter_catalog_shape():
    cat = sf.starter_catalog()
    assert "Banking" in cat and "Social" in cat
    assert cat["Banking"]["action"] == "keep"      # don't hide bank mail
    assert cat["Social"]["action"] == "archive"    # promotional, fine to file
    assert any(s["domain"] == "chase.com" for s in cat["Banking"]["senders"])

def test_build_starter_filters_uses_safe_actions():
    filters, warns = sf.build_starter_filters([
        {"domain": "chase.com"},          # Banking -> keep (label only, stays in inbox)
        {"domain": "facebookmail.com"},   # Social  -> archive
        {"domain": "nope.invalid"},       # unknown -> skipped
    ])
    assert len(filters) == 2
    chase = next(f for f in filters if f["from"] == "chase.com")
    assert chase["label"] == "Banking" and "shouldArchive" not in chase  # kept in inbox
    fb = next(f for f in filters if f["from"] == "facebookmail.com")
    assert fb["label"] == "Social" and fb["shouldArchive"] == "true"


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = 0
    for fn in fns:
        try:
            fn(); passed += 1; print(f"  ok   {fn.__name__}")
        except Exception as e:
            print(f"  FAIL {fn.__name__}: {type(e).__name__}: {e}")
    print(f"\n{passed}/{len(fns)} passed")
    sys.exit(0 if passed == len(fns) else 1)

# gmail_paste.py — turn a pasted Gmail "message details" block into a safe filter
# Version: 0.1.0 | 2026-06-25
#
# Replaces the abandoned Stage-4 Vision idea: instead of analysing a screenshot, the
# user pastes the text Gmail already shows for a message (the expandable header block):
#
#     from:      Harbor.Freight.Surprise <fsfawkr@oopppmaj.hhi.yourwebsitesortedssl.com>
#     sent by:   Trusted Sender <jdeibele@gmail.com>
#     mailed-by: hhi.yourwebsitesortedssl.com
#     signed-by: oopppmaj.hhi.yourwebsitesortedssl.com
#     subject:   Surprise in your inbox (for Harbor Freight customers Only)
#     <optional body pasted below>
#
# The value is not "extract the domain" — it is DECIDING what you can durably filter on:
#   * a STABLE sender  -> a `from:` filter on the registrable domain (kills its rotating
#     subdomains in one rule);
#   * a ROTATING/forged sender (random throwaway domain) -> the From address is useless,
#     so fall back to a SUBJECT phrase (which is what actually caught it).
#
# Every result is emitted through gmail_filter.build_safe_filter, so the two safety
# rules hold automatically: a reason-label is always attached, and a single criterion
# can only trash/archive (auditable) — never silently mark-as-read.
#
# NOTE: registrable-domain and "disposable domain" detection here are deliberately
# lightweight heuristics (no PSL, no dictionary). The honest long-term answer for the
# hard calls (is this domain disposable? what is the durable subject phrase?) is a cheap
# text LLM pass — far more tractable than Vision. These heuristics are the offline floor.

import re

from gmail_filter import build_safe_filter

# Reason-labels (children of a "Junk mail/" parent, matching Jim's real convention).
LABEL_SENDER = "Junk mail/Sender Blocked"
LABEL_SUBJECT = "Junk mail/Subject Spam"

# Shared / free-mail domains. We must NEVER reduce one of these to a `from: <domain>`
# rule — `from: gmail.com` would catch every Gmail sender (and possibly the user's own
# mail, since spam often spoofs the recipient's own address as the From). For a freemail
# sender we filter the FULL address if one was given, else fall back to the subject.
# (We assume a non-gmail address is NOT the user's; Google Workspace custom domains are
# out of scope for now. The first gmail address we see, the UI asks "is this yours?".)
FREEMAIL = {
    "gmail.com", "googlemail.com", "yahoo.com", "ymail.com", "outlook.com",
    "hotmail.com", "live.com", "msn.com", "aol.com", "icloud.com", "me.com",
    "mac.com", "proton.me", "protonmail.com", "gmx.com", "zoho.com",
}

_BLOCK_RE = re.compile(r"(?im)^\s*(from|subject|mailed-by|signed-by|sent by|to)\s*:")

# Public-suffix-LIGHT: enough multi-part suffixes to get the registrable domain right
# for common cases. A full implementation would use the PSL (tldextract).
_MULTI_SUFFIX = {
    "co.uk", "org.uk", "gov.uk", "ac.uk", "com.au", "net.au", "org.au", "co.nz",
    "co.jp", "com.br", "com.mx", "co.za", "co.in", "com.sg",
}

# Lines Gmail labels in the details block. We read the ones that carry domains.
_FIELD_RE = re.compile(r"^\s*([A-Za-z][A-Za-z \-]*?)\s*:\s*(.+?)\s*$")
_EMAIL_RE = re.compile(r"[\w.+-]+@([\w.-]+\.[A-Za-z]{2,})")
_VIA_RE = re.compile(r"\bvia\s+([A-Za-z0-9][A-Za-z0-9.\-]+\.[A-Za-z]{2,})", re.I)
_DOMAIN_RE = re.compile(r"([A-Za-z0-9][A-Za-z0-9.\-]*\.[A-Za-z]{2,})")


def registrable_domain(host):
    """Best-effort registrable domain (eTLD+1) from a host. Heuristic, not PSL-backed."""
    if not host:
        return None
    parts = host.strip().strip(".").lower().split(".")
    if len(parts) < 2:
        return host.lower()
    if len(parts) >= 3 and ".".join(parts[-2:]) in _MULTI_SUFFIX:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def _longest_consonant_run(label):
    runs = re.findall(r"[bcdfghjklmnpqrstvwxz]+", label.lower())
    return max((len(r) for r in runs), default=0)


def looks_disposable(domain):
    """True if a registrable domain looks like throwaway spam infrastructure (random,
    unpronounceable) rather than a real, stable sender you'd want to block by name.

    Heuristic: the main label has an unnatural consonant run (>=5, e.g. 'vjmkraodjhpja')
    or is a long, vowel-starved random string. Real word-salad spam domains that still
    read as words (e.g. 'yourwebsitesortedssl') are NOT flagged — they're stable enough
    that a `from:` filter on them works. Gibberish like 'vjmkraodjhpja.us' IS flagged.
    """
    if not domain:
        return True
    main = domain.split(".")[0]
    if not main:
        return True
    if _longest_consonant_run(main) >= 5:
        return True
    vowels = sum(c in "aeiou" for c in main)
    if len(main) >= 8 and vowels / len(main) < 0.2:
        return True
    return False


def parse_details(text):
    """Parse a pasted Gmail details block into the labelled fields we care about, plus
    everything after the header block treated as the body. Returns a dict."""
    fields = {}
    body_lines = []
    in_body = False
    for line in (text or "").splitlines():
        if in_body:
            body_lines.append(line)
            continue
        m = _FIELD_RE.match(line)
        if m:
            key = m.group(1).strip().lower()
            fields.setdefault(key, m.group(2).strip())
        elif line.strip() and "subject" in fields:
            # first non-field line after we've seen a subject = start of the body
            in_body = True
            body_lines.append(line)
    fields["body"] = "\n".join(body_lines).strip()
    return fields


def _email_domain(s):
    m = _EMAIL_RE.search(s or "")
    return m.group(1).lower() if m else None


def _bare_domain(s):
    m = _DOMAIN_RE.search((s or "").lower())
    return m.group(1) if m else None


# Strip the noise that makes a subject un-reusable: the recipient's own name, dates,
# order/ID numbers, and runaway punctuation. What's left is the durable spam phrase.
_DATE_RE = re.compile(
    r"\b(?:mon|tue|wed|thu|fri|sat|sun|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)"
    r"[a-z]*\.?[, ]*\d{0,4}[-/ ]*\d{0,4}", re.I)
_NUM_RE = re.compile(r"\b\d[\d,./:-]*\b")
_STOP = {"your", "you", "the", "a", "an", "is", "are", "to", "for", "will", "be", "in",
         "on", "of", "and", "take", "action", "dear", "user", "account"}


def subject_phrase_candidates(subject, recipient_name=None, max_candidates=4):
    """Suggest durable subject-filter phrases: the cleaned subject plus salient word
    runs, with dates / the recipient's name / numbers / punctuation stripped. The user
    picks (or an LLM ranks later) — over-fitting to the full subject is the failure mode
    (it has the date/name and never matches again)."""
    s = subject or ""
    if recipient_name:
        s = re.sub(re.escape(recipient_name), " ", s, flags=re.I)
    s = _DATE_RE.sub(" ", s)
    s = _NUM_RE.sub(" ", s)
    s = re.sub(r"[^\w ]+", " ", s)            # drop punctuation (¸ ! : etc.)
    s = re.sub(r"\s+", " ", s).strip().lower()
    if not s:
        return []
    words = s.split()
    cands = []
    # Whole cleaned subject (capped) first, then the longest run of content words.
    cands.append(" ".join(words[:8]))
    content = [w for w in words if w not in _STOP and len(w) > 2]
    # sliding 2- and 3-grams of content words, longest first, de-duped
    for n in (3, 2):
        for i in range(len(content) - n + 1):
            cands.append(" ".join(content[i:i + n]))
    seen, out = set(), []
    for c in cands:
        c = c.strip()
        if c and c not in seen and len(c) >= 4:
            seen.add(c)
            out.append(c)
    return out[:max_candidates]


def classify_input(text):
    """What did the user paste? 'block' (a Gmail details block), 'email' (a bare
    address — 'what do you want to do with mail from this address?'), or 'keyword'
    (a subject/phrase fragment)."""
    t = (text or "").strip()
    if not t:
        return "empty"
    if _BLOCK_RE.search(t):
        return "block"
    if "\n" not in t and len(t.split()) <= 3:
        m = re.search(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", t)
        if m:
            return "email"
    return "keyword"


def _result(kind, filt, warnings, reason, evidence=None, alternatives=None,
            ask_owner=False, input_kind="block"):
    return {"kind": kind, "filter": filt, "warnings": warnings, "reason": reason,
            "evidence": evidence or {}, "alternatives": alternatives or [],
            "ask_owner": ask_owner, "input_kind": input_kind}


def analyze(text, user_email=None):
    """Decide the best filter for pasted Gmail content — a full details block OR a bare
    email address OR a subject fragment. Optional `user_email` (the user's own address,
    captured progressively) is scrubbed from subjects and flags spoofs.

    Returns a dict: kind ('sender'|'subject'), filter (build_safe_filter dict or None),
    warnings, reason, evidence, alternatives, ask_owner (UI should ask "is this gmail
    address yours?"), input_kind.
    """
    user_email = (user_email or "").strip().lower() or None
    kind_in = classify_input(text)

    # ── bare email address: "what do you want to do with mail from this address?" ──
    if kind_in == "email":
        addr = re.search(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", text).group(0).lower()
        dom = addr.split("@", 1)[1]
        reg = registrable_domain(dom)
        ask = user_email is None and reg in ("gmail.com", "googlemail.com")
        if user_email and addr == user_email:
            return _result("subject", None, [],
                           "That's your own address — we won't filter your own mail.",
                           {"address": addr}, ask_owner=False, input_kind="email")
        # A full address is specific enough to filter even on a freemail domain
        # (from: john@gmail.com matches only John — unlike the bare domain).
        flt, warns = build_safe_filter({"from": addr}, LABEL_SENDER, action="keep")
        return _result("sender", flt, warns,
                       f"Mail from {addr} — choose what to do with it (kept + labelled by default).",
                       {"address": addr, "registrable": reg}, ask_owner=ask, input_kind="email")

    # ── bare keyword / subject fragment ──
    if kind_in == "keyword":
        cands = subject_phrase_candidates(text, recipient_name=_local_part(user_email))
        if not cands:
            return _result("subject", None, [], "Nothing usable to match on.", input_kind="keyword")
        flt, warns = build_safe_filter({"subject": cands[0]}, LABEL_SUBJECT, action="trash")
        return _result("subject", flt, warns,
                       f"Filter messages whose subject contains “{cands[0]}”.",
                       {"subject": text}, alternatives=cands[1:], input_kind="keyword")

    # ── full Gmail details block ──
    f = parse_details(text)
    from_line = f.get("from", "")
    to_email = _EMAIL_RE.search(f.get("to", "") or "")
    recipient = re.split(r"[@<]", to_email.group(0))[0] if to_email else _local_part(user_email)

    from_dom = _email_domain(from_line)
    from_addr = (_EMAIL_RE.search(from_line).group(0).lower() if _EMAIL_RE.search(from_line) else None)
    via_dom = (_VIA_RE.search(from_line).group(1).lower() if _VIA_RE.search(from_line) else None)
    mailed = _bare_domain(f.get("mailed-by", ""))
    signed = _bare_domain(f.get("signed-by", ""))
    from_reg = registrable_domain(from_dom)
    auth_reg = registrable_domain(mailed or signed or via_dom)
    subject = f.get("subject", "")
    evidence = {"from_domain": from_dom, "from_registrable": from_reg,
                "authenticated_registrable": auth_reg, "mailed_by": mailed,
                "signed_by": signed, "via": via_dom, "subject": subject}

    spoof = bool(user_email and from_addr == user_email)
    # Should the UI ask whether a seen gmail address is the user's? Only when we don't
    # already know their address and a gmail address showed up as the From.
    ask = user_email is None and from_reg in ("gmail.com", "googlemail.com")

    # SENDER filter is durable only for a STABLE, NON-freemail domain. A freemail From
    # (gmail.com etc.) must never become `from: <domain>` (catches everyone / maybe the
    # user) — and a disposable/gibberish domain rotates every send. Both fall to subject.
    if from_reg and from_reg not in FREEMAIL and not looks_disposable(from_reg):
        flt, warns = build_safe_filter({"from": from_reg}, LABEL_SENDER, action="trash")
        note = f"Stable sender domain '{from_reg}' — one from: rule catches its rotating subdomains."
        if auth_reg and auth_reg != from_reg:
            note += f" (Heads-up: authenticated sender is '{auth_reg}', not '{from_reg}'.)"
        return _result("sender", flt, warns, note, evidence, ask_owner=ask)

    cands = subject_phrase_candidates(subject, recipient_name=recipient)
    if not cands:
        return _result("subject", None, [],
                       "Sender can't be filtered safely and no usable subject phrase was found — "
                       "paste the subject line for a subject rule.", evidence, ask_owner=ask)
    flt, warns = build_safe_filter({"subject": cands[0]}, LABEL_SUBJECT, action="trash")
    if from_reg in FREEMAIL:
        why = (f"From is a {from_reg} address" + (" (and spoofs your own!)" if spoof else "")
               + " — a from: rule would catch everyone, so we filter the durable subject phrase.")
    else:
        why = (f"From domain '{from_reg or '(none)'}' looks disposable/rotating"
               + (f", disagreeing with authenticated '{auth_reg}'" if auth_reg and auth_reg != from_reg else "")
               + " — a from: rule won't hold, so we filter the durable subject phrase.")
    return _result("subject", flt, warns, why, evidence, alternatives=cands[1:], ask_owner=ask)


def _local_part(email):
    return email.split("@", 1)[0] if email and "@" in email else None

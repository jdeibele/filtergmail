# filtergmail.com — CLAUDE.md

## Project
filtergmail.com — "Control your inbox." A web tool that converts keyword/label pairs into Gmail filter XML files. Users enter what they want filtered and where it should go; the site generates an XML file they import directly into Gmail.

## Server
- OVH VPS: ubuntu@40.160.57.129
- Runs alongside blogsreader (/srv/blogsreader) and mypages (/srv/mypages)
- App lives at /srv/filtergmail
- Docker container on port 5060, nginx proxies filtergmail.com → 5060
- SSL cert via Certbot (Let's Encrypt), auto-renews

## Deploy
Push to main branch on GitHub (jdeibele/filtergmail) → GitHub Actions SSHs in → git pull → docker compose up -d --build

Manual deploy:
```
ssh ubuntu@40.160.57.129 'cd /srv/filtergmail && git pull && docker compose up -d --build'
```

SSH key is at ~/.ssh/id_ed25519 in this container.

## Process naming
Main file is `filtergmail_web.py` (not app.py or web.py) so it shows up unambiguously in `ps auxww`.

## File headers
Every file must have: filename, version number, date in a comment/docstring at the top.

## Architecture
- `filtergmail_web.py` — Flask app, port 5060
- `gmail_filter.py` — XML parsing/generation utilities
- `templates/index.html` — single-page UI
- `data/filtergmail.db` — SQLite, mounted as volume at /data
- No server-side session state; DB only stores anonymous pattern counts for community feed

## Database
SQLite at /data/filtergmail.db (volume-mounted, persists across rebuilds).
```sql
patterns (id, pattern, label, field, count, created_at)
UNIQUE(pattern, label, field)
```
WAL mode enabled. Patterns recorded on every XML download (anonymous, lowercase).

## Gmail filter fields
- `from` — sender email or domain (detected when pattern contains @ or looks like a domain)
- `hasTheWord` — keyword/phrase matching subject + body
- `subject` — subject line only (not used in Stage 1 auto-detection)
- `label` — Gmail creates the label automatically if it doesn't exist
- `shouldArchive: true` — all filters skip inbox by default

## Staged rollout plan
- **Stage 1 (live)**: keyword/label pairs → download XML, community inspiration feed
- **Stage 2**: CSV upload + export
- **Stage 3**: "Bring your existing mailFilters.xml" — import → tidy/organize → re-export.
  (Jim's own `jim/gmail-filters/` YAML↔XML workflow is the working prototype of this; his
  real 80-filter set is the reference fixture.)
- **Stage 4 (REPLACED)**: Claude Vision screenshot analysis was abandoned (Jim: "really tough
  to get right"). Replaced by the **paste-the-Gmail-details** parser (`gmail_paste.py`): the
  user pastes the text Gmail shows for a message; we decide sender-vs-subject and emit one safe
  filter. A cheap **text** LLM pass (rank durable subject phrases / judge disposable domains)
  is the future enhancement — far more tractable than Vision.

## Business model — FREE (2026-06-25)
- **Not charging.** The $4.99 paid tier is dropped. `FREE_TIER_LIMIT = 100` is now just an
  abuse ceiling, not a paywall.
- Entity: Oregon LLC under Jim's umbrella company.
- **Trademark / rename plan:** launch + publicize as filtergmail.com. The brand is a single
  env constant (`FILTERGMAIL_BRAND` / `FILTERGMAIL_TAGLINE`), so if Google sends a C&D over the
  "gmail" domain, the rename is one env change + a new domain (Jim is acquiring a backup) — and
  the rename itself becomes a second publicity beat. A trademark disclaimer ("independent tool,
  not affiliated with Google; Gmail is a trademark of Google LLC") is in the footer.

## Safety model — the spine of trust (gmail_filter.build_safe_filter)
Two rules from Jim's real, battle-tested filter set, so we never quietly delete on a hunch:
1. **The label is the receipt.** Every filter MUST carry a reason-label (`Junk mail/<reason>`),
   so a trashed/archived message tells you WHY — `in:trash label:"Junk mail/Subject Spam"`.
2. **Action scales with confidence.** archive/trash are *auditable* (survive under the label /
   in Trash 30 days) → allowed on one field. `mark-as-read` is *silent & unrecoverable* → needs
   ≥2 matching criteria; on a single field it's downgraded to trash with a warning.
Together: every action is auditable OR high-confidence — never both silent and low-confidence.

## Paste parser (gmail_paste.py)
`analyze(pasted_details_text)` → decides **sender** (stable From domain → `from:` on the
registrable domain, kills rotating subdomains) vs **subject** (disposable/forged sender →
durable subject phrase, dates/names/numbers stripped). Emits via `build_safe_filter`. Heuristic
registrable-domain + disposable detection; the hard calls are the LLM's future job. Tests in
`tests/test_filtergmail.py` (run `python3 tests/test_filtergmail.py`; no pytest needed).

## Templates
`templates/` is volume-mounted — editing index.html on the server takes effect immediately without rebuilding the Docker image. For Python file changes, rebuild is required.

## Inter-agent communication
Use /workspace/messages.md to pass messages to blogsreader or mypages Claude sessions.
Do NOT write to /workspace/blogsreader or /workspace/mypages.

## Environment variables
- `FILTERGMAIL_DB` — path to SQLite DB (default: /data/filtergmail.db)
- `PORT` — Flask port (default: 5060)
- No ANTHROPIC_API_KEY needed until Stage 4

## Free tier limit
`FREE_TIER_LIMIT = 100` in filtergmail_web.py (abuse ceiling, not a paywall — the tool is
free). Enforced server-side on /download; the route passes it to the template as `max_rows`.

## Known issues / tech debt

**GitHub Actions deploy broken**: The `OVH_SSH_KEY` secret in the filtergmail repo is incorrect. Fix by copying the working value from the blogsreader or mypages repo secrets (same server, same key). Until fixed, deploy manually via SSH.

**Community feed threshold too low**: `/download` records patterns at count ≥ 1, and the feed displays at count ≥ 1. With real traffic, bump the display threshold to ≥ 3 or ≥ 5 to filter out one-off patterns. Leave at 1 until there is meaningful traffic.

**`anthropic` in requirements.txt but unused**: Adds ~50MB to the Docker image with no benefit until Stage 4. Remove it from requirements.txt in Stage 1/2/3 and add back when screenshot analysis is built.

**No structured logging**: Flask runs in production mode with no application-level logging. Errors and download events are only captured by nginx access logs. Add logging before Stage 4 when payments are involved.

**No rate limiting**: `/download` has no rate limiting — repeated calls rack up DB writes. Negligible risk at current scale. Add before Stage 4.

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
- **Stage 1 (live)**: Up to 5 keyword/label pairs, download XML, community inspiration feed
- **Stage 2**: CSV upload + export (~3-4 weeks)
- **Stage 3**: Editing/persistence, merge with existing XML (~3-4 weeks)
- **Stage 4**: Screenshot analysis via Claude Vision, payment integration (~3-4 weeks)

## Business model
- Free: up to 5 filters per session
- Paid ($4.99 one-time): unlimited text entry + 10 screenshot analyses (Stage 4)
- No subscriptions. Credits don't expire.
- Entity: Oregon LLC under Jim's umbrella company

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
`FREE_TIER_LIMIT = 5` in filtergmail_web.py. Enforced server-side on /download.

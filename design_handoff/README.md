# Handoff: filtergmail — front door (Simple view)

## Overview
filtergmail is a tool that helps a non‑technical person clean up their Gmail without
ever handing over account access. The user lists junk to delete and mail to label,
**downloads a Gmail‑compatible filter file (`.xml`)**, and imports it into Gmail once.
We never sign in to or read the user's mail — we only generate a file the user imports
themselves (so it even works under Google Advanced Protection).

The brief calls for a single Flask template, **mobile‑first** (most people will use a phone).
The deliverable in this handoff is the **front‑door / Simple view**. "Advanced" is intentionally
**not** built — it is now an email‑capture interest gauge (see below).

The original brief is included alongside this README as `brief.md`.

## About the Design Files
`filtergmail.dc.html` in this bundle is a **design reference created in HTML** — a working
prototype that shows the intended look, copy, and behavior. It is **not** production code to
copy directly. It is authored in a small internal component format (a `<x-dc>` template plus a
`class Component` logic block and a `support.js` runtime). **Do not ship that format.**

Your task is to **recreate this design in the target codebase's environment**. The brief asks
for a **single Flask (Jinja2) template** with vanilla JS (or light Alpine/htmx) for the
interactions — no heavy SPA framework needed. If you are dropping it into an existing app,
follow that app's established patterns instead. All of the real logic (parsing, filter‑file
generation, the safety guards) is plain, framework‑agnostic JavaScript and is described in full
below so you can port it directly.

## Fidelity
**High‑fidelity.** Colors, typography, spacing, copy, and interactions are final. Recreate the
UI faithfully. Exact tokens are in the Design Tokens section.

## Audiences (informs tone — keep all three happy)
1. **Non‑technical users** (the primary audience): the 3 steps must be obvious and reassuring.
2. **Hacker News / power users**: the generated file is plain, readable text; honest about what
   it does; "we never touch your account" is a feature.
3. **Google/Gmail employees / legal**: the page is clearly **independent** and flatters Gmail's
   built‑in import feature. Keep the disclaimer footer and the "we never sign in" framing intact.

---

## Screen: Front door (single scrolling page)

Single centered column, `max-width: 520px`, horizontal padding `18px`, on a warm off‑white
page background. Vertical stack of sections, in order:

### 1. Header
- Left‑aligned. A 28×28px rounded square (8px radius) in the accent color containing the
  glyph `↯` (white, Bricolage Grotesque, 800), followed by the wordmark text.
- Wordmark: **"filtergmail"**, Bricolage Grotesque, 700, 17px, letter‑spacing −0.01em.
  The wordmark is **swappable** (the product name may change for trademark reasons) — keep it a
  single configurable value used in both the header and the download filename / feed title.
- Padding `18px 0`.

### 2. Intro
- H1: **"Tidy up your Gmail."** — Bricolage Grotesque, 800, 27px, line‑height 1.1,
  letter‑spacing −0.02em, `text-wrap: balance`.
- Paragraph: "Delete the junk, label the keepers, download a filter file, and import it into
  Gmail once. We never sign in or see your mail." — 15px, line‑height 1.5, color `#54504a`.

### 3. "Delete the junk" card
White card, `border: 1px solid #ece6dc`, radius 16px, padding 18px, margin‑top 22px.
- Title "Delete the junk" (Bricolage Grotesque, 700, 16px) + description (13px, `#6b665e`):
  "Paste a sender to block them, or words to block by subject. Caught mail gets labeled and
  sent to Trash."
- **Textarea** (controlled): monospace (IBM Plex Mono) 13.5px, 4 rows, padding `12px 13px`,
  `border: 1px solid #e2dccf`, radius 10px, background `#faf8f3`, resize vertical.
  Placeholder (3 lines): `deals@noreply.example.com`, `You have won`, `final notice`.
- Hint row (12px, `#9a948a`, flex, gap 16px, wrap):
  - "**an @address or domain (chase.com)** → "From Spam""
  - "**other words** → "Subject Spam""
- **Notice banner** (conditional): amber box (`background:#fbf6ea; border:1px solid #f0e4c8`,
  radius 10px), 13px text `#6f6450`. Shown after the self‑address removal flow (see Interactions).
- **Live preview** (conditional, shown when ≥1 parsed entry): a divider then one row per entry —
  the raw text (monospace 13px, ellipsis) left, and a red tag right
  (`color:#a8543c; background:#fbeae5`, 11px/700, radius 6px) reading "From Spam" or
  "Subject Spam". Each row has a bottom border `#f3efe7`, padding `8px 0`.

### 4. "Label & keep" card
White card (same style), margin‑top 16px.
- Title "Label & keep" + description: "Mail you want to keep but organize — like everything from
  your bank. It stays in your inbox and just gets your label."
- **Label groups** (repeatable, ≥1, default 1 empty group). Each group is an inset card
  (`border:1px solid #efe9df`, radius 12px, padding 13px, background `#fcfbf8`):
  - **Name input** (controlled): IBM Plex Sans 600, 13.5px, placeholder "Label name, e.g. Banks".
  - A small **×** remove button (32×32, red `#b4472f`) — only shown when there is more than one group.
  - **Textarea** (controlled): IBM Plex Mono 13px, 2 rows, placeholder (2 lines) `chase.com`,
    `statement is ready`.
  - **Note line** (11.5px, `#9a948a`): when the group has a name and ≥1 entry it reads
    `"<n> rule(s) → labeled "<name>", kept in your inbox"`; otherwise
    "One sender or subject per line — these stay in your inbox."
- **"+ Add another label"** button: full width, dashed border `#d8d2c6`, 13px/600, `#6b665e`.
- Reassurance line (11.5px, `#9a948a`): "No need to create these labels in Gmail first — it makes
  each one automatically when you import the file."

### 5. Download button + filename
- Full‑width button, margin‑top 18px, padding 15px, radius 12px, 15.5px/700 white text.
  Background = accent. Disabled look (opacity .5, `cursor:not-allowed`) when there is nothing to
  download. After a successful download the button turns dark (`#1f2420`) and reads
  "Downloaded — now import it below" (with a ✓); otherwise "Download filter file" (with ↓).
- Filename caption below (monospace 11.5px, `#9a948a`): the download filename, e.g.
  `filtergmail-filters.xml`.

### 6. "What the file does" card
Accent‑tinted card (`background: color-mix(in srgb, accent 7%, #fff)`,
`border: 1px solid color-mix(in srgb, accent 22%, #fff)`, radius 14px, padding 16px),
margin‑top 22px. Title "What the file does" + three ✓ bullets (accent check, 13.5px text):
1. "Junk you list gets a "From Spam" or "Subject Spam" label and goes to Trash (kept 30 days, just in case)."
2. "Mail you label — like everything from your bank — keeps its spot in your inbox and just gets your label too."
3. "It all applies to new mail from now on; your existing inbox is never touched."

### 7. "Import it, once" steps
Section label (uppercase 12px/700, `#9a948a`) then 4 numbered steps (24px circle outline in
accent, 14px body text):
1. "In the Gmail website, click the gear (⚙) → "See all settings"."
2. "Open the "Filters and Blocked Addresses" tab."
3. "Scroll down, choose "Import filters," and pick the file you downloaded."
4. "Click "Create filters." Done — new mail is handled automatically."

Followed by a tip box (`background:#f4f1ea`, radius 10px, 12.5px `#8a847a`): "Use the Gmail
**website**, not the app. On a phone you can open Gmail in Safari and tap "Desktop site," but
it's easier on a computer."

### 8. "Advanced" interest gauge (dark card)
Dark card (`background:#1f2420`, radius 16px, padding 20px, light text), margin‑top 24px.
- Uppercase label "ADVANCED" (12px/700, `#8fae9f`).
- Pitch (13.5px, `#cfcbc2`): "We've also built an advanced version — upload and download your
  filters as CSV, JSON or YAML, combine several fields into one filter, and more. If that sounds
  useful, leave your email and we'll release it if enough people want it."
- **Before submit**: an email input (monospace, dark `rgba(255,255,255,.06)` field) + "Notify me"
  button (accent). The button is disabled (opacity .55) until the email is valid. Tiny print:
  "We'll only email you about the advanced version — nothing else."
- **After submit**: a confirmation box with a ✓ and "Thanks — you're on the list. We'll be in
  touch if it ships."
- **Backend TODO:** the prototype only flips to the thank‑you state. Wire "Notify me" to a real
  endpoint that stores the address (this is the whole point of the gauge).

### 9. Footer
Top border `#e8e2d8`. Single small paragraph (11px, `#a39d92`):
"Not affiliated with, sponsored by, or endorsed by Google. Gmail™ is a trademark of Google LLC.
This is an independent tool that generates a filter file you import yourself."
**Keep this disclaimer.**

---

## Interactions & Behavior

### Input parsing (shared by both cards)
Split each textarea on newlines **and** commas; trim; drop empties. Classify each token:
- contains `@` → **sender**
- looks like a bare domain — matches `^[^\s@]+\.(com|org|net|edu|gov|io|co|us|info|biz|me|app)$`
  (case‑insensitive) → **sender**
- otherwise → **subject**

Query string per token: sender → `from:(<token>)`; subject → `subject:(<token>)`.

### Download flow (button click), in this exact order
1. If there is nothing to download (no delete entries and no label group with both a name and ≥1
   entry) → do nothing.
2. **Provider‑domain block (hard stop).** If the *delete* box contains a **bare provider domain**
   (no `@`, and the lowercased token is one of:
   `gmail.com, googlemail.com, yahoo.com, ymail.com, outlook.com, hotmail.com, live.com, msn.com,
   icloud.com, me.com, mac.com, aol.com, proton.me, protonmail.com, gmx.com, mail.com, zoho.com`)
   → show the **"That's too broad"** modal and stop. (`from:(gmail.com)` would trash mail from
   everyone on that provider.) This does **not** apply to the label card (labeling a whole
   provider is non‑destructive).
3. **Own‑address check.** Collect delete‑box **sender** tokens ending in `@gmail.com`
   (case‑insensitive).
   - Exactly **one** → show the **"Is this your own address?"** modal.
   - More than **one** → show the **"Check these first"** modal (we can't guess which is theirs;
     send them back to edit).
4. Otherwise → generate the file and download.

### Modals (all are fixed full‑screen overlays, `rgba(31,36,32,.5)`, centered white card max‑width 380px)
- **"Is this your own address?"** — shows the one address. Two buttons:
  - **"Yes, that's me"** → remove that line from the delete box. If nothing remains to download at
    all, save **nothing**, clear the delete box, and show the `removed-empty` notice. Otherwise
    proceed to download and show the `removed-saved` notice.
  - **"No, delete it"** → keep it and download.
- **"Check these first"** (multiple `@gmail.com`) — lists them; single "Back to edit" button (just
  closes).
- **"That's too broad"** (provider domain) — red title, lists the offending domain(s); single
  "Back to edit" button.

Notice strings:
- `removed-saved`: "We left your own address out — a filter on it would catch the mail you send and
  move it to Trash. Your file has everything else."
- `removed-empty`: "That was your own address, so there's nothing to delete yet — and a filter on it
  would Trash the mail you send. Add the senders or subjects you want gone."
- Editing the delete box clears the notice and the provider block.

### Advanced email capture
Valid if it matches `^[^\s@]+@[^\s@]+\.[^\s@]+$`. Button disabled until valid. On submit, flip to
the thank‑you state (and POST the address to your backend).

---

## Generated file format (Gmail filters — Atom XML)
The download is a Gmail‑importable filter feed. One `<entry>` per generated filter.

Top level:
```xml
<?xml version='1.0' encoding='UTF-8'?>
<feed xmlns='http://www.w3.org/2005/Atom' xmlns:apps='http://schemas.google.com/apps/2006'>
  <title><WORDMARK> filters</title>
  <!-- entries -->
</feed>
```
**Note:** the feed `<title>` deliberately uses `"<wordmark> filters"` — do **not** use Gmail's own
title "Mail Filters". Download filename is consistent: `<wordmark-slug>-filters.xml`
(slug = lowercase wordmark, non‑alphanumerics → `-`).

Each entry:
```xml
<entry>
  <category term='filter'></category>
  <title><human label></title>
  <content></content>
  <apps:property name='hasTheWord' value='<query>'/>
  <apps:property name='label' value='<label>'/>
  <!-- delete entries ONLY: --> <apps:property name='shouldTrash' value='true'/>
  <apps:property name='sizeOperator' value='s_sl'/>
  <apps:property name='sizeUnit' value='s_smb'/>
</entry>
```

Entry generation:
- **Delete box** → for each token: `label` = "From Spam" (sender) or "Subject Spam" (subject),
  `hasTheWord` = the query, **plus `shouldTrash=true`** (labeled **and** moved to Trash).
- **Label groups** → for each group with a non‑empty name, for each token: `label` = the group
  name, `hasTheWord` = the query, **no `shouldTrash`** (it gets the label and stays in the inbox).

Always XML‑escape values (`& < > " '`).

### Behavior facts to preserve (these are product decisions, not just copy)
- Filters act on **future** mail only; existing inbox is never modified (we do **not** apply
  filters to existing mail — intentionally, for safety).
- Deleted mail is **labeled and trashed** (recoverable from Trash for ~30 days), so the label
  explains *why* it was caught.
- Gmail **auto‑creates** any label on import; users don't pre‑create them.

---

## State Management
- `deleteText: string` — the delete textarea.
- `labelGroups: Array<{ id, name, text }>` — default one empty group.
- `downloaded: boolean` — toggles the success button state.
- `showConfirm: boolean` — drives the gmail own‑address modals (single vs multiple derived from
  the count of `@gmail.com` delete senders).
- `blockProvider: boolean` — drives the provider‑domain block modal.
- `notice: null | 'removed-saved' | 'removed-empty'`.
- `advEmail: string`, `advSubmitted: boolean`.
No data fetching in the front door (other than the Advanced POST you add).

## Design Tokens
**Color**
- Accent (primary): `#2f7d5b`. Swappable; curated alternates `#2f6f7d`, `#3a6ea5`, `#5a5fb0`.
- Page background: `#faf8f4`; body fallback `#f3efe8`.
- Card surface: `#ffffff`; inset surface `#fcfbf8`.
- Card border: `#ece6dc`; inset border `#efe9df`; input border `#e2dccf`; hairline `#f3efe7`.
- Input background: `#faf8f3`.
- Ink (text): `#2a2723`; secondary `#54504a` / `#6b665e`; muted `#8a847a` / `#9a948a`; faint `#a39d92`.
- Dark panel: `#1f2420` (text `#cfcbc2`, label `#8fae9f`).
- Danger / spam tag: text `#a8543c` / `#b4472f`, background `#fbeae5`, border `#f3d4c9`.
- Notice (amber): background `#fbf6ea`, border `#f0e4c8`, text `#6f6450`.
- Tints use CSS `color-mix(in srgb, var(--accent) N%, #fff)` so they follow the accent.

**Typography** (Google Fonts)
- Display: **Bricolage Grotesque** (600/700/800) — headings, wordmark, step numbers.
- Body/UI: **IBM Plex Sans** (400/500/600/700).
- Mono: **IBM Plex Mono** (400/500) — textareas, raw tokens, filename.

**Radius**: cards 16px; sub‑cards / inputs 10–14px; tags/chips 6px; pills/circles 999px/50%.
**Spacing**: section gaps ~16–24px; card padding 16–20px; input padding ~9–13px.
**Shadows**: modals `0 24px 60px -20px rgba(0,0,0,.55)`.

## Assets
- `assets/before-junk-inbox.png` and `assets/after-clean-inbox.png` — the "junk inbox → No new
  mail!" reference screenshots from the brief. **Not currently used** in the Simple view layout
  (the earlier hero was removed during MVP scoping). Included in case you want a before/after
  visual; otherwise ignore.
- The `↯` glyph and `⚙ ✓ ↓ ×` are plain Unicode characters — no icon library required.

## Screenshots
In `screenshots/`:
- `01-page.png` … `04-page.png` — the full front door, top to bottom (delete card, label card,
  download + "what the file does", import steps + Advanced interest card).
- `01-modal.png` — the "Is this your own address?" confirm (single `@gmail.com` in the delete box).
- `02-modal.png` — the "That's too broad" block (a bare provider domain in the delete box).

## Files
- `filtergmail.dc.html` — the full design reference (template + logic). Open in a browser to see
  it run. Read the `class Component` block for the exact, portable logic (parsing, `buildXml`,
  the provider list, validation).
- `brief.md` — the original product brief (audiences, promise, constraints).
- `assets/` — reference screenshots.

# filtergmail.com — front-door design brief

**The job:** design the *landing / first screen* for filtergmail.com so a non-technical person
gets it instantly and wants to use it. The current live screen (https://filtergmail.com) is a
filter-builder table — accurate and useful, but it reads as a *techie tool*. We're keeping that,
but it becomes an **"Advanced"** path, not the front door.

## Who it's for
A **capable non-techie**: can download a file and follow a few steps (think a smart relative —
someone's wife, sister, or grown kids). **Not** a developer (that's the Advanced screen). **Not**
someone who can't handle a file download at all (we accept that person isn't our user).

## The promise — lead with the outcome, not the mechanics
The product in two pictures (see references/): a **junk-clogged inbox → a clean "No new mail!"**.
The hero should *sell the calm*. Emotional, simple, reassuring — not a spreadsheet of filters.

## The flow — 3 steps, zero jargon
1. **Pick what to clear.** Big friendly toggles for the junk everyone has:
   *Spam & scams · Promotions · Social notifications · Bank & login notices.*
   Plus one box: *"A junk email that keeps coming back? Paste it."*
2. **Download your filter file.** One button.
3. **Import once into Gmail.** A short, picture-led walkthrough (Settings → Filters → Import).

## Honest constraints (don't overpromise)
- We **generate a file the user imports** — we never log into or touch their Google account.
  That's a feature: *works even with Google Advanced Protection*, where "connect your Gmail"
  tools fail. Worth a small trust line.
- So the promise is **"set it once and the junk stops piling up,"** not a literal one-click empty.

## Keep / demote (don't delete)
- The current filter-builder → **"Advanced"** (for power users / the HN crowd): the table,
  per-row actions, YAML/CSV/JSON export, `{}` consolidation.
- A "Roll Your Own" explainer (how Gmail filters work, editors) sits behind Advanced.

## Tone & brand
Clean, friendly, reassuring. Gmail-adjacent in feel but clearly **independent** (not affiliated
with Google; Gmail is a trademark of Google LLC). Name may change later (trademark) — keep the
wordmark swappable.

## Deliverable
A front-door layout (hero with before→after, the 3-step picker, the import walkthrough) we can
implement in a single Flask template. Mobile-first; most people will try this on a phone.

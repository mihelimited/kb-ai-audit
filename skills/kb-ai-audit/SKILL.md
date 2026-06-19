---
name: kb-ai-audit
description: >
  Audit a help center / knowledge base for AI customer-service-agent readiness, then produce
  paste-ready rewrites. Use when the user gives a help center URL and wants to know why their AI
  agent's resolution rate is low, wants a "KB audit", "help center audit", "AI readiness check",
  "optimise our knowledge base for AI", or names Zendesk / Intercom / Gorgias / Freshdesk / HubSpot
  and asks to review their articles. Pulls every article, grades each one A+ to F against
  13 plain-language checks, derives the house style, and writes rewrites that keep that voice.
---

# Knowledge Base AI-Readiness Audit

Help a business rewrite its help center so an AI support agent can actually resolve from it.
An AI agent reads one chunk at a time with no memory between answers; anything written for a
human who scrolls, skims and clicks "see also" is invisible to it. This skill finds the gaps and
**hands back the fixed articles**, not just a grade.

Framework: 13 plain-language checks grouped under 3 questions (find / use / trust), **plus a
help-centre-wide coherence layer** (coverage gaps, contradictions, near-duplicates, date analysis,
disambiguation) that looks across and between articles — see `reference/patterns.md`. The coherence
findings fold into the existing checks so they affect the grade. Never expose the underlying mechanism
in customer output with words like "retrieval", "RAG", "chunk", "embedding" or "cluster" — the ICP is a
CS leader, not an engineer.
Goal: be the audit that actually gets used. Always ship the rewrite, bound the scope, tie each
fix to resolution rate, and leave a tracker they work down.

## Operating principles
- **Never invent facts.** A rewrite may only use facts that are present in the source article (or
  another audited article when consolidating). Never fabricate specs, numbers, steps, button names,
  error strings, URLs, dates, prices or policies, and never "fill in" a plausible-sounding detail.
  Preserve every figure, unit and exact string verbatim. If the article needs a fact that isn't in
  the source, leave a clearly-marked `[VERIFY: …]` placeholder and call it out — do not guess.
  Minimising hallucination is the whole point: a confident wrong answer is worse than "I don't know".
- **Ship the rewrite, not the grade.** The deliverable is done work to paste back in.
- **Score objectively; rewrite on-brand.** Style never affects scoring; the derived style profile
  feeds the rewrites so voice is preserved (the answer to "aren't we writing for robots?").
- **Bound the scope.** Most KBs are 20–150 articles — audit them all. Surface the worst first;
  never tell anyone to "rewrite 400 articles".
- **Offer options, default to done.** Ask the checkpoints below, but every one has a default so a
  user who just pastes a URL still gets the full result.

## The guided flow (use AskUserQuestion at each checkpoint; each has a default)

**Checkpoint 1 — What to audit**
Whole help center (paste URL) · a single article (quick try) · a specific collection/section.
Ask the user to paste their own help-center URL — **do not pre-fill, suggest, or default to any
specific help center**, and in particular never offer My AskAI's own help center (help.myaskai.com)
or any example company as an option. The audit target is always whatever URL the user provides; if
they haven't given one yet, just ask for it with an empty prompt (a neutral placeholder like
`https://help.yourcompany.com` is fine, but it must not be a real suggested destination).

**Checkpoint 2 — Prioritisation signal** *(optional; default = self-rank)*
Default: rank the fix queue by engagement + high-intent topics. Or: user pastes top ticket
subjects / unanswered queries, or uploads a ticket export (CSV), to order the queue by real volume.

**Checkpoint 3 — House style** *(optional; default = derive from their KB)*
Default: derive the style profile from their own articles. Or: point at 2–3 "good" articles to
match, or use the neutral house template.

**Checkpoint 4 — Audit deliverables** *(default = all)*
dashboard, xlsx tracker, exec summary. These are the diagnostic; they always run. **Rewrites are a
separate, opt-in step — do NOT auto-rewrite.**

**Checkpoint 5 — Rewrites (ask AFTER showing the grades, never before).**
First ask *whether and which*:
 - Rewrite the worst / priority articles (recommend a number, e.g. the bottom 5–10 by grade)
 - Let me pick specific articles (show the graded list and let them choose)
 - Not now (just keep the audit)
Then, if they want rewrites, ask *how to deliver*:
 - A **Markdown rewrite pack** they paste in themselves (`rewrite_pack.md`) — default, works everywhere
 - **Push straight into the help center as drafts via API** — Zendesk / Intercom / Freshdesk / HubSpot
   (Gorgias = pack only). See `reference/writeback.md`. Always create as **drafts**, never publish; confirm
   the count and platform before writing anything.

**Checkpoint 6 — Loop**
Offer a scheduled monthly re-audit so the grade is tracked over time, not a one-off.

## Pipeline

1. **Detect platform & fetch** — `scripts/fetch_articles.py <help-centre-url> -o articles.json`
   auto-detects the platform and pulls the **entire** help centre into `articles.json`:
   - **Zendesk** → public API, no login (fully automatic).
   - **Intercom / Freshdesk / HubSpot** → API if the matching token env var is set
     (`INTERCOM_TOKEN` / `FRESHDESK_KEY` / `HUBSPOT_TOKEN`), otherwise it crawls.
   - **Gorgias** → crawl (no public read API).
   - **Anything else / unknown** → crawl: find the sitemap, collect article URLs, crop each page to
     its real **article-body container** (not the first `<main>`, which is often the site header),
     normalise.
   The crawl filters to **one language by default** (`--locale en`) and de-dupes by article id, so a
   multilingual help center isn't graded N times. Verified per-platform fingerprints, sitemap paths,
   article-URL patterns and content selectors (Intercom / Freshdesk / HubSpot / Gorgias) are in
   `reference/fetch.md`. Override detection with `--platform`, language with `--locale`, sample with `--max`.
2. **Triage every article** — run `scripts/kb_audit.py articles.json -o results.json`. Deterministic
   13-check scoring + the help-centre-wide coherence layer (coverage gaps, contradictions, near-duplicates,
   date analysis, disambiguation) + the house-style profile. To unlock coverage gaps, pass the ticket
   export from Checkpoint 2: `--tickets export.csv` (otherwise the coverage panel renders a locked nudge).
3. **Confirm + deep-audit the priority set** — for the top-ranked articles, confirm the judgement-
   call checks (answer-first, plain headings, jargon, cases-together) **and the corpus candidates
   marked `needs_confirm`** (contradiction / near-duplicate / disambiguation) with the prompts in
   `reference/patterns.md`. Drop any candidate the confirm rejects before it counts against the grade.
4. **Build the audit deliverables** — run BOTH:
   - `scripts/build_outputs.py results.json --kb-name "<KB>" --outdir out/` for `exec_summary.md` and
     `audit_tracker.xlsx`.
   - `scripts/build_branded.py results.json --kb-name "<KB>" --outdir out/` for the **My AskAI–branded**
     `dashboard.html` (hero grade card + by-question score cards + filterable **row-card** "Fix these
     first" list with issue chips + collapsed house-style panel) and `scorecard.html` (cream card, big
     grade block). `build_branded.py` copies the brand assets (`scripts/assets/`) into `out/assets/`,
     so keep that folder alongside the HTML when sharing. All generated UI is **US English**.
   Present these, then **stop and ask Checkpoint 5** — don't rewrite yet.
5. **Rewrite — only the articles they asked for, and produce the FINISHED article every time.** Apply
   the rewrite prompt (`reference/patterns.md`), injecting `results.json → style_profile.descriptor`
   (and the richer `style_profile.signals` / `style_profile.highlights` for finer voice-matching)
   so it matches their voice. **Write the complete, paste-ready article(s) in full — never a summary,
   never "follow the same template", never "do the same for the others".** If an article must be
   split, write out every resulting article in full. Re-score to show the grade before → after.
   - **Carry over the original images and videos.** The rewrite must include every image and video
     from the source article so the customer can copy-paste once and be done — not just describe
     them in words (the "spells out visuals" check still requires the words too; do both). The source
     media URLs are in `results.json → results[i].media` (`{type:"image"|"video", src, alt, embed}`).
     In the `body`, place each image as Markdown `![alt](https-url)` and each video as its embed (an
     `<iframe …>` on its own line) at the point in the steps where it belongs. Use absolute `https:`
     URLs (prefix protocol-relative `//…` embeds). When an article is split, put each image/video in
     whichever resulting article it actually belongs to.
   - **Markdown delivery:** save the human-readable `rewrite_pack.md` (before/after score, full
     rewrite, what-changed, facts-to-consolidate) AND a machine-readable `rewrites.json`. The latter
     drives the per-article pages embedded in the dashboard. `rewrites.json` is
     `{"rewrites": [ {new_title, source_title, source_url, before_grade, after_grade, body,
     what_changed, facts_to_consolidate, raw_grade?, resolved_notes?, verify_items?}, … ]}`.
     **`body` must contain ONLY the clean, paste-ready article** (its "Applies to:" line through
     "Last verified:", *including the carried-over images and video embeds*, and **no `[VERIFY]` text**
     — see below) — no grades, no "what changed", no source/heading meta, because that field is copied
     verbatim. Then re-run
     `scripts/build_branded.py results.json --kb-name "<KB>" --rewrites rewrites.json --outdir out/`
     (re-running `build_outputs.py` just refreshes `exec_summary.md` + `audit_tracker.xlsx`; `build_branded.py`
     owns all the HTML surfaces, so running both in either order no longer clobbers the dashboard).
     This regenerates `dashboard.html` (each rewritten article's row gains a **View rewrite →** button)
     and writes one self-contained page per rewrite (`rewrite-NN-<slug>.html`) with the full article —
     text, images and video — a **Copy article** button (copies rich HTML + plain text), a
     **← Back to audit** link, and **‹ Previous / Next ›**, plus two **collapsed-by-default** panels
     **above** the article (outside the copy region): *How this article was graded* and *Verify before
     publishing*.
   - **Grade honestly, then resolve the ceiling transparently.** After re-scoring, some flagged checks
     can't be improved without fabricating facts or harming the article (an archived announcement must
     cite its old date; a reference article has no "fix" to give; the grader false-positives on exact
     registration codes / tickers / the word "YouTube"). Genuinely fix what you can; for the rest, list
     each as a **resolved aspect with a one-line reason** in `resolved_notes` (`[{check, reason}]`) and
     count it as resolved for `after_grade`, while `raw_grade` keeps the unadjusted score. The page shows
     both — never silently drop a flag.
   - **Move `[VERIFY]` out of the copy.** Keep the article body clean; collect every unconfirmed fact
     into `verify_items` (a list of plain questions). They render as a **checklist on the page** (not in
     the copied text), so the customer pastes a clean article and works the checklist separately.
   - **Fact-check before presenting (anti-hallucination).** Once `rewrites.json` exists, run
     `scripts/verify_rewrites.py rewrites.json --source articles.json -o out/verify_report.md`. It
     extracts every checkable fact in each rewrite (measurements/specs + quoted error messages / UI
     labels) and confirms each appears in the source articles; anything that doesn't is flagged.
     **Resolve every flag** — correct the rewrite to match the source, or replace the value with a
     `[VERIFY: …]` note — and re-run until clean, *then* present the refreshed dashboard alongside
     `rewrite_pack.md` and `verify_report.md`. (It checks hard facts, not paraphrased prose — but those
     are the ones that cause confidently-wrong answers.)
   - **API delivery:** create each rewrite as a **draft** article with
     `scripts/push_drafts.py --platform <zendesk|intercom|freshdesk|hubspot> rewrites.json …`
     (dry-run by default; `--list` shows the section/collection/folder/category ids; add `--execute`
     to write). **Gorgias has no write API → Markdown pack only.** Confirm platform + count first;
     never publish; report back the draft links. Full per-platform endpoints in `reference/writeback.md`.
6. **Loop** — offer a scheduled monthly re-audit so the grade is tracked over time.

## Stage gates — what "done" looks like (don't pass over a stage until it's true)
Treat every stage as **gated**: verify its done-criterion before moving on, and say so out loud. A
failing gate stops the pipeline — fix the blocker and re-check, don't proceed. (Encode this discipline
even when running by hand; nothing should be casually skipped.)

| Stage | Done when (the gate) |
|---|---|
| **Fetch** | Every article pulled in **one language** (no other locales), each cropped to its article body. Spot-check: URLs all share the locale, median body > ~50 words, **no nav/header markup** in any body. |
| **Audit** | `results.json` has one row per fetched article, an overall grade, and all 13 checks rolled up (`article_count` matches the corpus). |
| **Deliverables** | branded `dashboard.html`, `scorecard.html`, `audit_tracker.xlsx`, `exec_summary.md` all exist and open. **Present them before asking about rewrites.** |
| **Rewrites** | Each rewrite uses **only source facts**; `body` contains **no `[VERIFY]` text**; every source image/video carried over; before→after grade recorded. |
| **Fact-check** | `verify_rewrites.py` reports **0 flags** — every measurement / quoted string traces to the source. Resolve every flag before presenting. |
| **Grade integrity** | Every flagged check is **either genuinely fixed or listed in `resolved_notes` with a reason** — nothing silently dropped; `raw_grade` keeps the unadjusted score. |
| **Render** | Each `rewrite-NN.html` has the two **collapsed** panels **above** the article and **outside** the copy region; `[VERIFY]` lives only in the verify checklist, never in the copied body. |

## Running it / scale
- **All articles, one command:** `fetch_articles.py` pulls the whole help centre (tested against a 125-article
  Zendesk help centre). The audit and rewrites then run over everything; the priority queue decides
  order, not which articles get looked at.
- **Where it runs:** anywhere the bundled scripts have normal network access — Claude Code on the
  user's machine is the most reliable for a full pull, but Cowork works too. Only the fetch step needs
  the network; `kb_audit.py` / `build_outputs.py` are offline.
- **Rewrite volume:** rewriting every failing article on a large KB is a lot of output — do it in
  batches (e.g. 10 at a time, worst first), but always deliver the *complete* rewrite for each.

## Output contract
The three HTML surfaces are emitted by `build_branded.py` in the **My AskAI brand system** (orange
`#EA3609`, Geist + Acid-Grotesk display type, fully-rounded pills, white background, the myAskAI
wordmark). All copy is **US English** ("help center"). Brand assets live in `scripts/assets/` and are
copied to `out/assets/` — ship that folder with the HTML.
- **dashboard.html** — the hub: a top bar (open scorecard / copy score summary), a **hero** (left grade
  card with the big letter grade + "% of checks pass"; right headline + explainer + stat chips), a
  **by-question** section (three cards, one per find/use/trust question, each with per-check pass-% bars
  coloured by threshold), a **collapsed** "Your house style" panel (editable, saves to the browser,
  feeds Optimize), and the **"Fix these first"** list: search + grade/priority selects + "rewritten
  only", a live count, and one **row-card per article** — rank, grade badge, title link, priority,
  orange **issue chips** (the failing checks), `pass/total`, a **View rewrite →** pill if rewritten, and
  an **Optimize** button that hands Claude a ready-made instruction (uses `sendPrompt()` as a chat
  widget, else copies to clipboard) including the current house style and a "use only source facts,
  never invent" guardrail. The "Fix these first" list shows the **top 5 with a "Show all" toggle** so the
  sections below stay reachable. Below it, a **Knowledge base coherence** section surfaces the corpus
  layer: coverage gaps (or a locked nudge), contradictions and near-duplicates each with a **Merge /
  Reconcile** button that hands Claude a resolution instruction, an article-age/freshness graph, and
  easily-confused names with links to the articles involved. Self-contained, re-openable.
- **scorecard.html** — a self-contained, share-ready card (1200×630): cream card, a solid grade block
  (orange F/D, amber C, green A/B) with the big letter, overall %, articles audited / worth fixing, and
  the three biggest gaps as bars. Screenshot or open to share.
- **rewrite-NN-&lt;slug&gt;.html** (one per rewrite) — a self-contained page: display-type H1, a
  before→after grade pair (orange-tint → green-tint badges), source link, **Copy article** button
  (copies title + body as rich HTML *and* plain text), the full article (text + carried-over images and
  video), and **two collapsed-by-default panels above the article** — *How this article was graded*
  (raw grade → resolved aspects with reasons → final grade) and *Verify before publishing* (the
  `[VERIFY]` checklist, with browser-persisted checkboxes) — both **outside** the copy region so neither
  is ever pasted. Has **← Back to audit** and **‹ Previous / Next ›**.
- **audit_tracker.xlsx** — 13-check grid × every article, colour-coded, with a "Rewrite status"
  column they tick off. The thing they work down.
- **rewrite_pack.md** — per priority article: before/after score, the **complete** paste-ready
  rewrite(s) in their style (full article text for every one, splits written out in full), what
  changed, facts to consolidate. No placeholders, no "same template".
- **rewrites.json** — the same finished articles in machine form (`{"rewrites":[…]}`), with a clean
  `body` per article (no `[VERIFY]` text) plus optional `raw_grade` / `resolved_notes` / `verify_items`,
  so the pages can embed them with copy buttons, grade-transparency and verify checklists. Feeds
  `build_branded.py --rewrites`.
- **verify_report.md** — output of `verify_rewrites.py`: per-article fact check confirming every
  measurement/spec and quoted string in each rewrite traces back to the source (anti-hallucination).
- **exec_summary.md** — 1 page for the CS lead/buyer: headline score, the 80/20, fix-these-first.

## Tone & honesty
- Be specific and quantified ("497 votes, event ended 3 Nov 2025, AI is quoting a dead event").
- Say which prioritisation signal was used (real ticket data vs proxy).
- One tasteful My AskAI footer only. Every fix must work with any AI vendor.

## Notes
- `kb_audit.py`, `build_outputs.py`, `build_branded.py` and `verify_rewrites.py` are stdlib + openpyxl,
  no network, safe to run anywhere. `push_drafts.py` (Zendesk/Intercom/Freshdesk/HubSpot) and the
  `push_to_intercom.py` wrapper are the only scripts that write externally — dry-run by default, drafts
  only, credentials from env vars (see `reference/writeback.md`).
- Fetching must use the host's web tools; for very large fetches, page and append to `articles.json`.
- See `demo/` in the repo for a full worked run against Bird Buddy's Zendesk help center (125
  articles → grade F): `demo/output/` has the dashboard, shareable `scorecard.html`, the 13
  per-article rewrite pages, `rewrite_pack.md` and the `verify_report.md` fact-check.

---
name: kb-ai-audit
description: >
  Audit a help center / knowledge base for AI customer-service-agent readiness, then produce
  paste-ready rewrites. Use when the user gives a help center URL and wants to know why their AI
  agent's resolution rate is low, wants a "KB audit", "help center audit", "AI readiness check",
  "optimize our knowledge base for AI", or names Zendesk / Intercom / Gorgias / Freshdesk / HubSpot
  and asks to review their articles. Pulls every article, grades each one A+ to F against
  13 plain-language checks, derives the house style, and writes rewrites that keep that voice.
---

# Knowledge Base AI-Readiness Audit

Help a business rewrite its help center so an AI support agent can actually resolve from it.
An AI agent reads one chunk at a time with no memory between answers; anything written for a
human who scrolls, skims and clicks "see also" is invisible to it. This skill finds the gaps and
**hands back the fixed articles**, not just a grade.

Framework: 13 plain-language checks grouped under 3 questions (find / use / trust), **plus a
help-center-wide coherence layer** (coverage gaps, contradictions, near-duplicates, date analysis,
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
- **Grade on the weighted score.** Each check carries an importance weight in `PATTERN_META`
  (3 = fundamental, 2 = matters, 1 = nice to have), and the grade uses the **weighted** pass rate.
  An unexplained acronym (weight 1) must not cost an article as much as never giving the fix
  (weight 3). The `x/13` shown to the customer stays a plain count of checks passed; the grade and
  the fix queue are the weighted figures. Two articles failing the same *number* of checks can and
  should grade differently.
- **Grade on a realistic scale, not a US school curve.** The 13 checks are a high bar that
  virtually no help center was written against in the first place, so a US curve (where anything
  under 60% is an F) hands almost every customer an F on the first pass — discouraging *and*
  inaccurate. The scale is: **A+ 90+, A 80, B+ 75, B 70, C+ 60, C 50, D 40, E 30, F 20**. Half the
  checks passing is an ordinary, workable help center — a **C**, not a failure. An **F** now means
  failing 10 of 13 checks, which is a genuinely broken article, not merely an unpolished one. Report
  the grade the tool produces; never re-grade an article harder by hand to make a point.
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
dashboard, xlsx tracker, exec summary, and a branded **PDF report** (the full audit, no rewrites). These
are the diagnostic; they always run (build them, but don't open/present the dashboard yet). **By default
the priority rewrites then run automatically (Checkpoint 5) and the dashboard is opened with them baked
in** — only skip the rewrites if the user has said not to. The PDF report is rendered and handed back as
an asset at the end of the run (step 7), regardless of whether rewrites were done.

**Checkpoint 5 — Rewrites (default = yes; do the priority set first, don't wait to be asked).**
The default flow is: **rewrite the priority set right after the audit, then open the dashboard with the
rewrites baked in, then continue** (next batches, coherence merges, the monthly loop). Don't stop to ask
permission first — just do the bottom 5–10 by grade/priority and state the batch you picked. The user can
always redirect ("pick these instead", "not now", "bigger batch"). Surface the *which* options explicitly
only when scope is genuinely ambiguous:
 - Rewrite the worst / priority articles (**default** — recommend the batch, e.g. bottom 5–10 by grade)
 - Let me pick specific articles (show the graded list and let them choose)
 - Not now (just keep the audit)
For *how to deliver*, default to the Markdown pack unless the user asks to push:
 - A **Markdown rewrite pack** they paste in themselves (`rewrite_pack.md`) — **default**, works everywhere
 - **Push straight into the help center as drafts via API** — Zendesk / Intercom / Freshdesk / HubSpot
   (Gorgias = pack only). See `reference/writeback.md`. Always create as **drafts**, never publish; confirm
   the count and platform before writing anything.

**Checkpoint 6 — Loop**
Offer a scheduled monthly re-audit so the grade is tracked over time, not a one-off.

## Pipeline

1. **Detect platform & fetch** — `scripts/fetch_articles.py <help-center-url> -o articles.json`
   auto-detects the platform and pulls the **entire** help center into `articles.json`:
   - **Zendesk** → public API, no login (fully automatic).
   - **Intercom / Freshdesk / HubSpot** → API if the matching token env var is set
     (`INTERCOM_TOKEN` / `FRESHDESK_KEY` / `HUBSPOT_TOKEN`), otherwise it crawls.
   - **Gorgias** → crawl (no public read API).
   - **Anything else / unknown** → crawl: find the sitemap, collect article URLs, crop each page to
     its real **article-body container** (not the first `<main>`, which is often the site header),
     normalize.
   The crawl filters to **one language by default** (`--locale en`) and de-dupes by article id, so a
   multilingual help center isn't graded N times. Verified per-platform fingerprints, sitemap paths,
   article-URL patterns and content selectors (Intercom / Freshdesk / HubSpot / Gorgias) are in
   `reference/fetch.md`. Override detection with `--platform`, language with `--locale`, sample with `--max`.
2. **Triage every article** — run `scripts/kb_audit.py articles.json -o results.json`. Deterministic
   13-check scoring + the help-center-wide coherence layer (coverage gaps, contradictions, near-duplicates,
   date analysis, disambiguation) + the house-style profile. To unlock coverage gaps, pass the ticket
   export from Checkpoint 2: `--tickets export.csv` (otherwise the coverage panel renders a locked nudge).
3. **Confirm + deep-audit the priority set, and review the whole coherence layer** — for the top-ranked
   articles, confirm the judgment-call checks (answer-first, plain headings, jargon, cases-together).
   Then **review EVERY contradiction ("articles that disagree") and EVERY near-duplicate ("articles that
   agree") candidate yourself before any of them are shown** — not only the ones flagged `needs_confirm`.
   The heuristics are deliberately broad and over-flag (two articles that merely share the topic
   "payment"; a base name vs a "`<name>` 2" artefact). Judge each with the confirm prompts in
   `reference/patterns.md` and **drop every candidate that's an overly-conservative false positive** — a
   pair only stays if a real customer's question would genuinely be hurt by the conflict / overlap. Apply
   the drop for real: delete the rejected items from `results.json → corpus` (`contradictions` /
   `collisions` / `disambiguation`) and revert any folded check **before building the deliverables**, so
   the dashboard only ever surfaces findings that survived the review.
4. **Build the audit deliverables** — run BOTH:
   - `scripts/build_outputs.py results.json --kb-name "<KB>" --outdir out/` for `exec_summary.md` and
     `audit_tracker.xlsx`.
   - `scripts/build_branded.py results.json --kb-name "<KB>" --outdir out/` for the **My AskAI–branded**
     `dashboard.html` (hero grade card + by-question score cards + filterable **row-card** "Fix these
     first" list with issue chips + collapsed house-style panel), `scorecard.html` (cream card, big
     grade block), and `report.html` — a **print-optimized, self-contained, audit-only** report styled as a
     lead magnet on the myaskai.com look (cream canvas, speech-bubble motif, kicker pills, serif-italic
     accents): magazine cover → "what an AI agent can't do" → by-question scores → top-12 fix-these-first
     → coherence → house style → dark CTA; **no rewrites**. It becomes the PDF in step 7. `build_branded.py` copies the brand assets (`scripts/assets/`) into
     `out/assets/`, so keep that folder alongside the HTML when sharing. All generated UI is **US English**.
   Build these now, but **don't open or present the dashboard yet** — by default go straight to the
   priority rewrites (step 5), rebuild the dashboard with them baked in, and open *that* version.
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
6. **Open the dashboard, then continue the flow** — once the priority batch is fact-checked, **open the
   dashboard** (`open out/dashboard.html` on macOS, `xdg-open out/dashboard.html` on Linux) so the user
   lands on the rewrites, present the before→after, then keep going through the remaining steps without
   waiting to be prompted: offer the next worst-N batch, the near-duplicate **merges** that survived the
   coherence review, unlocking coverage gaps with a ticket CSV, and a scheduled **monthly re-audit** so
   the grade is tracked over time.
7. **Render the branded PDF report and hand it back as an asset (always, on completion).** Once the run
   is complete — after the audit, and after any rewrites/fact-check — turn the audit-only `report.html`
   into a PDF and surface it to the user as a downloadable asset:
   `scripts/html_to_pdf.py out/report.html out/report.pdf`. The script renders with whatever engine is
   available (Playwright → headless Chrome/Chromium/Edge → WeasyPrint) and honours the report's A4
   `@page` CSS, so the PDF matches the brand. The PDF is the **diagnostic only — it never includes the
   help-center rewrites** (those live in the rewrite pages / Markdown pack). Present `out/report.pdf` as
   an attached asset **and** give a clickable absolute-path link to it. If no PDF engine is available,
   the script says so and leaves `report.html` — fall back to the host's print-to-PDF (e.g. open
   `report.html` and Print → Save as PDF) before handing it over; never skip delivering the report.

## Stage gates — what "done" looks like (don't pass over a stage until it's true)
Treat every stage as **gated**: verify its done-criterion before moving on, and say so out loud. A
failing gate stops the pipeline — fix the blocker and re-check, don't proceed. (Encode this discipline
even when running by hand; nothing should be casually skipped.)

| Stage | Done when (the gate) |
|---|---|
| **Fetch** | Every article pulled in **one language** (no other locales), each cropped to its article body. Spot-check: URLs all share the locale, median body > ~50 words, **no nav/header markup** in any body. |
| **Audit** | `results.json` has one row per fetched article, an overall grade, and all 13 checks rolled up (`article_count` matches the corpus). |
| **Coherence review** | Every contradiction & near-duplicate candidate reviewed; overly-conservative false positives **deleted from `results.json → corpus`** (and their folded checks reverted) before the dashboard is built. |
| **Deliverables** | branded `dashboard.html`, `scorecard.html`, `report.html`, `audit_tracker.xlsx`, `exec_summary.md` all exist and open. The dashboard is **opened for the user after the default priority rewrites are baked in**, so it shows the rewrite pages. |
| **Rewrites** | Each rewrite uses **only source facts**; `body` contains **no `[VERIFY]` text**; every source image/video carried over; before→after grade recorded. |
| **Fact-check** | `verify_rewrites.py` reports **0 flags** — every measurement / quoted string traces to the source. Resolve every flag before presenting. |
| **Grade integrity** | Every flagged check is **either genuinely fixed or listed in `resolved_notes` with a reason** — nothing silently dropped; `raw_grade` keeps the unadjusted score. |
| **Render** | Each `rewrite-NN.html` has the two **collapsed** panels **above** the article and **outside** the copy region; `[VERIFY]` lives only in the verify checklist, never in the copied body. |
| **Report (PDF)** | `report.pdf` exists (rendered from `report.html`), is **branded and audit-only — no rewrites**, and is **handed back to the user as an attached asset with a clickable link**. If no PDF engine ran, the report was print-to-PDF'd by hand and still delivered — never skipped. |

## Running it / scale
- **All articles, one command:** `fetch_articles.py` pulls the whole help center (tested against a 125-article
  Zendesk help center). The audit and rewrites then run over everything; the priority queue decides
  order, not which articles get looked at.
- **Where it runs:** anywhere the bundled scripts have normal network access — Claude Code on the
  user's machine is the most reliable for a full pull, but Cowork works too. Only the fetch step needs
  the network; `kb_audit.py` / `build_outputs.py` are offline.
- **Rewrite volume:** rewriting every failing article on a large KB is a lot of output — do it in
  batches (e.g. 10 at a time, worst first), but always deliver the *complete* rewrite for each.

## Output contract
The HTML surfaces (dashboard, scorecard, **report**, per-article rewrite pages) are emitted by
`build_branded.py` in the **My AskAI brand system** (orange `#EA3609`, Geist + Acid-Grotesk display
type, fully-rounded pills, white background, the myAskAI wordmark). All copy is **US English** ("help
center"). Brand assets live in `scripts/assets/` and are copied to `out/assets/` — ship that folder with
the HTML. (`report.html` inlines the wordmark, so it and `report.pdf` stand alone without `out/assets/`.)
- **dashboard.html** — the hub: a top bar (open scorecard / copy score summary), a **hero** (left grade
  card with the big letter grade + "% AI-readiness score"; right headline + explainer + stat chips), a
  **by-question** section (three cards, one per find/use/trust question, each with per-check pass-% bars
  colored by threshold), a **collapsed** "Your house style" panel (editable, saves to the browser,
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
  (orange F/E/D, amber C, green A/B) with the big letter, overall %, articles audited / worth fixing, and
  the three biggest gaps as bars. Screenshot or open to share.
- **report.html → report.pdf** — the **branded, print-optimized, audit-only report** (no rewrites),
  designed as a **lead magnet** in the myaskai.com look (cream canvas `#FAF9F1`, orange speech-bubble
  decorations, kicker pills, Instrument-Serif italic accents, dark CTA), and the deliverable handed back
  as an asset on completion. Paginated A4 (`@page` CSS): a magazine **cover** (grade band + serif-accent
  title), a "what an AI agent can't do" callout, the by-question scores, the **top-12** "Fix these first"
  articles (with "+N more — see the tracker" notes), the **Knowledge base coherence** section (button-free
  single-column static panels + freshness graph, long lists capped), the house-style summary, and a
  dark **CTA** outro. Full-bleed cream to the page edge (`@page` margin 0 + `box-decoration-break:clone`
  for a consistent inner border on every page); self-contained (wordmark inlined). `html_to_pdf.py` converts it to `report.pdf` via
  Playwright / headless Chrome / WeasyPrint.
- **rewrite-NN-&lt;slug&gt;.html** (one per rewrite) — a self-contained page: display-type H1, a
  before→after grade pair (orange-tint → green-tint badges), source link, **Copy article** button
  (copies title + body as rich HTML *and* plain text), the full article (text + carried-over images and
  video), and **two collapsed-by-default panels above the article** — *How this article was graded*
  (raw grade → resolved aspects with reasons → final grade) and *Verify before publishing* (the
  `[VERIFY]` checklist, with browser-persisted checkboxes) — both **outside** the copy region so neither
  is ever pasted. Has **← Back to audit** and **‹ Previous / Next ›**.
- **audit_tracker.xlsx** — 13-check grid × every article, color-coded, with a "Rewrite status"
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
  no network, safe to run anywhere. `build_branded.py` now also emits `report.html` (audit-only,
  print-ready). `push_drafts.py` (Zendesk/Intercom/Freshdesk/HubSpot) and the `push_to_intercom.py`
  wrapper are the only scripts that write externally — dry-run by default, drafts only, credentials from
  env vars (see `reference/writeback.md`).
- `html_to_pdf.py` (`report.html` → `report.pdf`) is stdlib orchestration; the rendering engine is
  optional and tried in order **Playwright → headless Chrome/Chromium/Edge/Brave → WeasyPrint**. It needs
  one of them present (Claude Code on the user's machine almost always has a Chrome install). If none are
  found it leaves `report.html` with a clear message; fall back to the host's print-to-PDF and still
  deliver the report.
- Fetching must use the host's web tools; for very large fetches, page and append to `articles.json`.

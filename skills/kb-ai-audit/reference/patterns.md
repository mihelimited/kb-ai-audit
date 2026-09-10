# The 13 checks (plain-language rubric + prompts)

Every label and explanation here is written for a CS/CX leader. **Never** use words like
"retrieval", "RAG", "chunk", "embedding", "vector" or "index" in any output the customer sees —
explain the mechanism in plain terms ("the AI reads one article at a time, with no memory between
answers; it can't scroll, click 'see also', or read a screenshot").

Score each Pass / Fix / N/A. `scripts/kb_audit.py` pre-scores all 13 and attaches a plain
"why it matters" to each. Scoring is objective — house style never makes a check pass or fail.

## Can the AI find the right answer?
1. **One question per article** — one article answers one question; a page bundling several can serve the wrong part.
2. **Worded the way customers ask** — title, headings and body use the customer's words: the symptom (not the internal feature), and the **exact** error message and button names they'd type.
3. **Says who and where it applies** — a top line naming who/which device/plan/region/version it's for.
   *Only assessed when the answer actually varies by audience; an article that applies to everyone is marked N/A.*

## Can the AI use the answer?
4. **Answer first, and each part stands alone** — the answer is in the opening lines of each section, and no section leans on "as mentioned above".
   *Scored per section (h2/h3), not on the article's opening paragraph: an AI agent reads one section at a time, so a long page with a weak intro but strong sections should pass. Fails when under 60% of sections lead with the answer; the note names the offending sections.*
5. **Answer written out, not behind a link or tab** — no bare Yes/No, no "click here", and nothing essential hidden in a drop-down, accordion or "read more".
6. **Explains acronyms and product names** — every acronym / in-house name spelled out on first use, in every article.
7. **Keeps every case in one place** — branches (EU/US, device A/B, Free/Pro) answered where the customer is, not cross-linked away.
8. **Spells out images, video and tables in words** — any step shown only in a screenshot or video is also written out; big tables become prose.
9. **Gives the actual fix, with anything needed first** — the concrete action to take, plus any prerequisite ("be logged in", "on the latest app version"), not just an explanation of the cause.
10. **Says what to do if it doesn't work** — an explicit next step (contact support, it's a hardware issue) so the AI has a safe fallback.

## Is it the right, current answer?
11. **Says what it doesn't cover or isn't possible** — states limits and known issues plainly, so the AI doesn't invent a workaround.
    *Only assessed on how-to, troubleshooting and policy articles, where "can this be done?" is a live question; a short reference article is marked N/A.*
12. **Dated and current** — a "last verified" date; expired/old content flagged; versions labeled.
    *The platform's own `updated_at` within ~18 months counts as an anchor, since the help center shows it to readers. Only genuinely time-bound content (promos, prices, deadlines, beta) is required to carry one.*
13. **No conflicting duplicates** — each fact lives in one article; others point to it.

Checks 2, 4, 6, 7, 9 are judgment calls — the script flags them `llm_confirm: true` so they get a
quick human/AI confirm on the priority articles. Each check also carries an importance weight (1–3)
used only to order the "biggest wins" list.

## The corpus-wide coherence layer (looks across and between articles)

The 13 checks above grade one article at a time. `kb_audit.py` also runs five **help-center-wide**
passes that catch what a per-article grade can't — and **fold each finding into an existing check so it
affects the grade** (the answer to "but the article looked fine on its own"):

| Pass | What it catches | Folds into |
|---|---|---|
| **Coverage gaps** | Questions customers ask (from a ticket export) that have **no article at all** — usually the #1 reason an AI can't resolve. KB-level only (no article to grade). | — (corpus headline) |
| **Contradictions** | The same subject stated with **different facts** across two related articles (refunds "14 days" vs "30 days"; a price, %, size, eligibility). Distinct from literal duplication. | Check 13 |
| **Near-duplicates / collisions** | Two **paraphrased** articles competing for the same query — the AI splits its pick and may surface the weaker one. Distinct from the literal-sentence overlap pass. | Check 13 |
| **Date analysis** | Article-age distribution (or, when no update dates exist, the most-recent date each article *mentions*) + articles quoting a **past-dated, time-sensitive** fact. | Check 12 |
| **Disambiguation** | **Confusable names** the KB never tells apart — chiefly a base name that also appears with a version/model suffix (v1 vs v2). | Check 6 |

Coverage gaps need a ticket export: run `kb_audit.py articles.json --tickets export.csv`. Without it the
dashboard shows a **locked** panel that doubles as a nudge to upload tickets. Reuse the Checkpoint 2 CSV.

Contradiction, collision and disambiguation findings are deterministic **candidates** — the heuristics
are intentionally broad and **over-flag**, so treat them as a shortlist to review, not findings to trust.
**Always review every contradiction ("disagree") and near-duplicate ("agree") candidate before any of
them are shown** — not only the ones marked `needs_confirm`, and regardless of whether they're on the
priority set — because they fold into the grade and a false positive costs an article a check. Use the
confirm prompts below and **drop every overly-conservative false positive**: a candidate only survives if
a real customer question would genuinely be hurt by the conflict / overlap (two articles that merely share
a topic word, or a base name vs a "`<name>` 2" detector artefact, do **not** survive). Delete each
rejected item from `results.json → corpus` (`contradictions` / `collisions` / `disambiguation`) and revert
the folded check to its prior verdict **before building the deliverables**, so the dashboard only surfaces
what survived. In the branded dashboard each surviving contradiction/near-duplicate carries a
**Merge / Reconcile** button that hands Claude the resolution instruction (merge into one canonical
article / reconcile both to agree), using only source facts.

### Corpus confirm prompts (run on candidates before relying on them)
> **Contradiction** — Do these two passages state genuinely conflicting facts about the same thing a
> customer would ask about (not just two different cases/plans)? Answer real/not-real + one sentence.
> A: "{a_context}"  B: "{b_context}".
> **Near-duplicate** — Would a customer's question be answered by *either* of these two articles, such
> that they should be merged into one canonical answer? real/not-real + which to keep. "{a}" vs "{b}".
> **Disambiguation** — Does this article use {names} as if the reader already knows the difference,
> without distinguishing them? real/not-real + one sentence. [article text]

## Confirm prompt (judgment-call checks, on the priority set)
> Confirm Pass or Fix for these checks on the article below, one sentence each: worded the way
> customers ask; answer first and stands alone; explains acronyms; keeps every case in one place;
> gives the actual fix. [article text]

## Rewrite prompt (per failing priority article)
> You are a technical writer rewriting a help article so an AI support agent can answer from it.
> The AI reads one article at a time, with no memory between answers; it can't scroll, click
> "see also", or read a screenshot. **Use ONLY facts present in the source article (or another
> audited article when consolidating) — never invent specs, numbers, steps, button names, error
> strings, URLs, dates or policies, and preserve every figure/unit/exact string verbatim. If a
> needed fact is missing, write a `[VERIFY: …]` placeholder instead of guessing.** Rewrite the
> article so it passes all 13 checks above:
> one question per article (split if needed and write every resulting article in full); lead with
> the answer; use the customer's words including any exact error message; add a top **Applies to:**
> line as a plain bold paragraph (not a blockquote — blockquotes get mangled on paste into some
> help-center editors); write out every step that only exists in a screenshot or video AND carry over the original
> images/videos so the article is paste-complete — place each source image as Markdown `![alt](https-url)`
> and each video as its `<iframe>` embed at the right point (source media URLs are in
> `results.json → results[i].media`; for a split, put each into the article it belongs to); spell out
> acronyms; answer each case in place; give the concrete fix plus any prerequisite; add a "if this
> doesn't work…" next step; state what it doesn't cover / isn't possible; add "Last verified: [today]".
> **Match this house style exactly: {STYLE_PROFILE.descriptor}** (from results.json; the richer
> `style_profile.signals`/`highlights` are there too for finer voice-matching).
> Produce the complete, paste-ready article(s) — never a summary or "same as above". End with
> "What changed" and "Facts to consolidate from other articles".

`{STYLE_PROFILE}` comes from the style pass in `kb_audit.py`, so rewrites keep the customer's voice.
The structure changes; the voice doesn't — which is also the answer to "aren't we writing for robots?".

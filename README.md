# Help Centre AI-Readiness Audit

Grades a help centre for how well an AI customer-service agent can answer from it, shows what to fix
first, and — only if you ask — rewrites the articles you choose in your own voice.

## What it does
1. **Pulls every article** from your help centre. Just give it the URL.
   - Zendesk works with no login. Intercom, Freshdesk and HubSpot use the API if you supply a token,
     otherwise crawl. Gorgias and any other platform are crawled. (See `skills/kb-ai-audit/reference/fetch.md`.)
2. **Grades each article A+ to F** against 13 plain-language checks grouped under three questions:
   *Can the AI find the answer? Can it use it? Is it current?* Plus an overall help-centre grade.
3. **Tells you what to fix first** — a priority (Very high → Very low) based on how busy the article
   is and how many issues it has.
4. **Gives you four outputs:** a branded dashboard, a 1-page summary, a spreadsheet tracker, and —
   on request — a rewrite pack.
5. **Rewrites on request** — you choose which articles, and whether to get a Markdown pack to paste
   in or have them pushed back into your help centre as **drafts** via API.

## How to run it
Just ask: *"Audit our help centre — here's the URL."* The plugin handles fetch → grade → outputs,
then asks whether you want rewrites and how to deliver them.

To pull the whole help centre in one go, it runs `scripts/fetch_articles.py <url>` (needs normal
internet access — Claude Code on your machine is the most reliable). Everything after fetch is offline.

## What's inside
- `skills/kb-ai-audit/SKILL.md` — the workflow.
- `skills/kb-ai-audit/scripts/` — `fetch_articles.py` (all platforms), `kb_audit.py` (the 13-check
  grading + duplicate-fact + house-style passes), `build_outputs.py` (dashboard / tracker / summary).
- `skills/kb-ai-audit/reference/` — `fetch.md` (per-platform fetching), `patterns.md` (the 13 checks
  + rewrite prompts), `writeback.md` (pushing drafts back via API).

Every fix works with any AI agent or helpdesk. Built by [My AskAI](https://myaskai.com).

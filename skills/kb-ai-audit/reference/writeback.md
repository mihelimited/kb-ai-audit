# Pushing rewrites back as drafts (API write-back)

Only when the user explicitly chooses API delivery at Checkpoint 5. **Rules, every time:**
- Create as a **draft / unpublished** article — never publish, never overwrite the live version.
- Confirm the platform and the exact list/count of articles before writing anything.
- Use credentials the user provides (token / API key), ideally via an env var — never hard-code.
- After writing, report back the draft URL/ID for each article so the user can review and publish.
- Respect rate limits; small batches with a short pause.

The rewrite body should be the article HTML (most platforms expect HTML, not Markdown — convert).

## Bundled script: `scripts/push_drafts.py` — all writable platforms
One script creates the drafts for **Zendesk, Intercom, Freshdesk and HubSpot** (dry-run by default,
draft-only, never publishes). **Gorgias has no public article-write API → Markdown pack only.**
```
python3 scripts/push_drafts.py --platform <p> rewrites.json --list      # show target container ids
python3 scripts/push_drafts.py --platform <p> rewrites.json <ids>       # dry run (preview)
python3 scripts/push_drafts.py --platform <p> rewrites.json <ids> --execute   # create the drafts
```
| Platform | Env vars | Required arg (from `--list`) | Draft state |
|---|---|---|---|
| zendesk | `ZENDESK_SUBDOMAIN`, `ZENDESK_EMAIL`, `ZENDESK_TOKEN` | `--section <id>` (`--locale`, default en-us) | `draft:true` |
| intercom | `INTERCOM_TOKEN` | `--author <id>` (`--collection <id>` optional) | `state:"draft"` |
| freshdesk | `FRESHDESK_DOMAIN`, `FRESHDESK_KEY` | `--folder <id>` | `status:1` |
| hubspot | `HUBSPOT_TOKEN` | `--category <id>` | `state:"DRAFT"` |

(`scripts/push_to_intercom.py` is the Intercom-only convenience wrapper; `push_drafts.py` supersedes it.)
Endpoint/field detail for each platform is below — the script implements exactly these.

## Zendesk Guide
Auth: API token or OAuth (`Authorization: Bearer`/basic `email/token:TOKEN`).
- **Create draft:** `POST /api/v2/help_center/{locale}/sections/{section_id}/articles.json`
  body `{"article":{"title":"…","body":"<p>…</p>","draft":true,"locale":"en-us"}}`
- **Update existing (keep as draft):** `PUT /api/v2/help_center/articles/{id}.json`
  with `{"article":{"draft":true,…}}`, or update the translation
  `PUT /api/v2/help_center/{locale}/articles/{id}/translations/{locale}.json`.
- Keep the original `section_id` from the audit so the draft lands in the right place.

## Intercom  — bundled script: `scripts/push_to_intercom.py`
Auth: access token (`Authorization: Bearer`), `Intercom-Version: 2.11`.
- **Create draft:** `POST https://api.intercom.io/articles`
  body `{"title":"…","body":"<p>…</p>","state":"draft","author_id":<admin id>,"parent_id":<collection>,"parent_type":"collection"}`
- **Update:** `PUT https://api.intercom.io/articles/{id}` (set `"state":"draft"`).

**Use the bundled helper** (dry-run by default, never publishes, creates NEW drafts so the live
article is untouched until the user reviews):
```
export INTERCOM_TOKEN=...
python3 scripts/push_to_intercom.py --list-admins        # find an author_id (a teammate id, required)
python3 scripts/push_to_intercom.py --list-collections    # optional: a collection to file drafts under
python3 scripts/push_to_intercom.py rewrites.json --author <id> [--collection <id>]            # dry run
python3 scripts/push_to_intercom.py rewrites.json --author <id> [--collection <id>] --execute  # writes drafts
```
It converts each rewrite's Markdown to the HTML subset Intercom accepts. **Video `<iframe>` embeds are
not supported in Intercom article bodies** — the script replaces them with a "Watch the video" link, so
make sure any video steps are also written out in words (the "spells out video" check ensures this).
`author_id` is required by the API to create an article; get it from `--list-admins`.

## Freshdesk
Auth: API key (basic auth `KEY:X`).
- **Create draft:** `POST /api/v2/solutions/folders/{folder_id}/articles`
  body `{"title":"…","description":"<p>…</p>","status":1}` (status 1 = draft, 2 = published).
- **Update:** `PUT /api/v2/solutions/articles/{id}` with `"status":1`.

## HubSpot Knowledge Base
Auth: private-app token (`Authorization: Bearer`), scope for knowledge base content.
- Create the article in **DRAFT** state via the Knowledge Base content API, then it appears in the
  KB editor for review before publishing. Confirm the current endpoint/scopes in the user's portal
  (HubSpot's KB API surface changes); if unavailable, fall back to the Markdown pack.

## Gorgias
No public article-write API. **Markdown pack only** — generate `rewrite_pack.md` and tell the user to
paste each rewrite into the Gorgias Help Center editor.

## If anything is uncertain
If you can't confirm the endpoint, scopes, or a safe draft state for a platform, **don't write** —
deliver the Markdown pack instead and say why. A wrong write to a live help centre is far worse than
asking the user to paste.

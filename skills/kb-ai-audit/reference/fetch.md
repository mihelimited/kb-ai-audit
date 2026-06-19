# Getting the articles out of each help centre

The auditor needs one file, `articles.json` — a list of articles, each normalised to:

```
{ "id", "title", "html_url", "body" (HTML), "updated_at", "section_id", "label_names": [], "vote_count" }
```

`scripts/fetch_articles.py <help-centre-url>` does this automatically for all platforms — detect,
fetch, normalise, write `articles.json`. This file documents what it does per platform and what to
do by hand if the script can't run (e.g. no network in the current environment).

**Detection order:** match the URL host first; if it's a custom domain, fetch the home page and look
for a platform fingerprint (response headers like `x-hs-portal-id` / `x-intercom-version` /
`x-fw-ratelimiting-managed`, the Gorgias robots template, or "zendesk"/"hubspot" in the body); for
Zendesk, the give-away is that the public API below responds. You can always override with `--platform`.

### Reading WITHOUT a key — what each platform exposes (tested 2026-06-19)
| Platform | No-key full-article pull? | How |
|---|---|---|
| **Zendesk** | ✅ Yes | Public Help Center API (no auth) — the clean route. |
| **Gorgias** | ✅ Yes | Unauthenticated `GET /api/help-centers/{uid}/questions` returns **every** article's full HTML in one call (`{uid}` = `__NEXT_DATA__.props.pageProps.helpCenter.uid`). Per-article body is also in `__NEXT_DATA__.props.pageProps.htmlContent`. |
| **Intercom** | 🟡 Content yes, via embedded JSON | No public JSON *endpoint* (official API needs a token; `/_next/data/*` 204s). But every article page embeds the full body in `__NEXT_DATA__.props.pageProps.articleContent.blocks` — cleaner than DOM scraping. |
| **HubSpot** | 🟡 Discovery only | `GET https://api.hubapi.com/cms/v3/site-search/search?portalId={id}&type=KNOWLEDGE_ARTICLE&q=…` works with no key but returns **titles/URLs/snippets only** (no body). Full KB content API needs a private-app token. |
| **Freshdesk** | ❌ No | Solutions API is `401` without `FRESHDESK_KEY`. Crawl the public HTML instead. |

`fetch_articles.py` uses these automatically: for Next.js help centers (Intercom, Gorgias) it reads
`__NEXT_DATA__` and uses it when it's at least as complete as the DOM crop; otherwise it crops the HTML.

Always: skip drafts, paginate to the end, be polite (small pauses), and prefer the **API** over
crawling — the API gives clean article bodies with no nav/menu noise.

---

## 1. Zendesk  — fully automatic, no login
The best case. The Help Center API is public for public help centres.

- **List every article:** `GET https://{HELPDESK_HOST}/api/v2/help_center/{locale}/articles.json?per_page=100`
  - Works on `*.zendesk.com` and on custom domains (hit the same path on the live host).
  - Follow `next_page` to the end. `count` tells you the total.
- **Fields map 1:1:** `title`, `body` (clean HTML), `updated_at`, `section_id`, `label_names`,
  `vote_count`, `html_url`, `draft`. Skip `draft: true`.
- Command: `python3 scripts/fetch_articles.py https://support.example.com`

## 2. Intercom — API with a token, else crawl
- **With a token** (`INTERCOM_TOKEN` env var): `GET https://api.intercom.io/articles?per_page=250`,
  header `Authorization: Bearer <token>` and `Intercom-Version: 2.11`. Follow `pages.next`.
  Keep `state: published`; map `title`, `body` (HTML), `url`, `updated_at`, `parent_id` → section.
- **No token:** Intercom help centres live on `*.intercom.help` (or a custom domain) with articles at
  `/{locale}/articles/{id}-slug` and a `/sitemap.xml`. The script crawls the sitemap and extracts the
  main article content. Command: `python3 scripts/fetch_articles.py https://help.example.com --platform intercom`

## 3. Freshdesk — API with an API key, else crawl
- **With a key** (`FRESHDESK_KEY` env var, HTTP basic `key:X`): walk the Solutions tree —
  `GET /api/v2/solutions/categories` → `/categories/{id}/folders` → `/folders/{id}/articles`.
  Keep `status: 2` (published); map `title`, `description` (HTML) → body, `updated_at`, folder → section.
- **No key:** public portal pages are at `/support/solutions/articles/...`; the script crawls them.
  Command: `python3 scripts/fetch_articles.py https://example.freshdesk.com`

## 4. HubSpot Knowledge Base — API with a private-app token, else crawl
- **With a token** (`HUBSPOT_TOKEN` env var, KB content scope): list published articles from the
  Knowledge Base content API (`/cms/v3/knowledge-base/articles?state=PUBLISHED`); map `title`,
  `postBody` (HTML) → body, `url`, `updated`, `categoryId` → section. HubSpot's KB API surface moves
  around — confirm the exact path/scopes in the portal; if unavailable, use the crawl.
- **No token:** KB lives on a custom domain or `*.hs-sites.com` with a sitemap; the script crawls it.

## 5. Gorgias — crawl (no public article API)
Gorgias Help Centers are on `*.gorgias.help` with a sitemap. There's no read API, so the script
discovers article URLs from the sitemap and extracts the main content of each page.
Command: `python3 scripts/fetch_articles.py https://brand.gorgias.help`

---

## 6. Any other / unknown platform — the crawl process
When it isn't one of the five (or the API isn't reachable), use the generic route. The script does
this automatically; the manual process is the same:

1. **Find the article list.** Try, in order: `/sitemap.xml`, **`/support/sitemap.xml`** (Freshdesk),
   `/sitemap_index.xml`, `/hc/sitemap.xml`, `/help/sitemap.xml`. If it's a sitemap *index*, open each
   child sitemap. Collect every URL whose path looks like an article: it contains `/articles/`,
   `/article/`, `/knowledge/`, `/kb/`, `/help/`, `/support/solutions/articles/`, **or ends in
   `…/{slug}-{numericId}` under a locale prefix** (Gorgias, e.g. `/en-US/how-to-…-79957`). Skip
   `/categories/`, `/sections/`, `/collections/`, `/search`, `/login`, `/tags/`.
   - No sitemap? Fall back to crawling the help-center home and category pages, following links that
     match those same patterns. Stay on the same domain.
2. **Filter to ONE language and de-dupe.** Multilingual help centers list the same article in every
   language in one sitemap — grading them all both wastes a pass and dilutes the score with duplicates.
   Keep only URLs under the target locale (`/en/`, `/en-US/`, …) via `--locale en` (the default), and
   de-dupe by the numeric article id. *(This was a real miss: an Intercom help center crawled in full
   pulled all 18 languages until we filtered to English.)*
3. **Fetch each article page** and **crop to the real content container — not just the first `<main>`.**
   The first `<main>` on many help centers is the site **header** (Intercom renders `<main class="header__lite">`
   before the article), so cropping to "first `<main>`" grabs the nav/logo. Instead, prefer, in order:
   an element whose class contains a known body container (`article_body`, `article-content-wrapper`,
   `article-body`, `fc-article-content`, `knowledgebase-post`, `post-body`), then `[itemprop="articleBody"]`,
   then a real `<article>`, then a `<main>`/`[role=main]` **whose class does not contain "header"**, then
   `<body>`. Drop `<nav> <header> <footer> <aside> <form> <script> <style> <svg> <button> <noscript>`.
   `scripts/fetch_articles.py` does exactly this (`MainExtractor` + `CONTENT_CLASSES`).
4. **Pull the fields:** title from the first `<h1>` or `<title>` (strip a trailing " | Brand"/" · Brand"
   suffix); body = the cropped HTML (keep headings, lists, images, tables — the checks need them);
   `updated_at` from a visible "updated" date or `<time>` if present; `vote_count` defaults to 0 (no
   engagement signal when crawling, so the priority ranking leans on topic + position instead).
5. **Write `articles.json`** in the same shape and run the audit exactly as for the API platforms.

Quality note: crawled bodies are slightly noisier than API bodies, so confirm a couple of the
flagged articles by eye before trusting the edge-case checks. Everything downstream is identical.

## Fetch hygiene (all platforms)
- Respect `robots.txt` and rate-limit (the script pauses between requests).
- Skip drafts and unpublished content.
- Cap with `--max` for a quick sample; default is the whole help center.
- Filter to one language with `--locale` (default `en`); the crawler de-dupes by article id.
- Credentials come from env vars only — never hard-code a token.

---

## Verified per-platform crawl reference (no API token; tested 2026-06-19)

Each of these was confirmed live with `curl` against a real public help center. All four crawl
cleanly **server-rendered** — the article prose is in the raw HTML, so no headless browser is needed.

### Intercom (e.g. `help.kriptomat.io`)
- **Fingerprint:** `x-intercom-version` response header; `intercom.help` in body/CSP.
- **Sitemap:** `/sitemap.xml` (flat, multilingual — filter to the locale).
- **Article URL:** `/{locale}/articles/{id}-{slug}`.
- **Content container:** `div.article_body` (inside `<article class="jsx-…">`). The first `<main>` is
  the page header (`header__lite`) — do **not** crop to it.
- **Gotchas:** heavily multilingual (one sitemap, ~18 langs) → always `--locale`. Body image URLs are
  signed `intercom-attachments`/`downloads.intercomcdn.com` links (carry over verbatim).

### Freshdesk (e.g. `support.freshdesk.com`)
- **Fingerprint (custom domains too):** headers `x-fw-ratelimiting-managed`, `report-to`/`nel` →
  `*.freshedge.net`; body class `fw-content--single-article`. Root `/` 302s to `/support/home`.
- **Sitemap:** **`/support/sitemap.xml`** (note the `/support/` prefix — plain `/sitemap.xml` 404s;
  `robots.txt` advertises the right one).
- **Article URL:** `/support/solutions/articles/{id}-{slug}` (slug optional; id-only works).
- **Content container:** `div.article-content-wrapper` (older themes: `.article-body`,
  `.fc-article-content` — match any).
- **API:** Solutions API (`/api/v2/solutions/categories` → folders → articles) is **not public** —
  401 without `FRESHDESK_KEY` (HTTP basic `key:X`). Use only with a key.
- **Gotchas:** rate-limited (`x-ratelimit-limit` ~200–300/window; back off on 429); multilingual
  `/<locale>/support/...`.

### HubSpot Knowledge Base (e.g. `knowledge.hubspot.com`, `*.hs-sites.com`)
- **Fingerprint (custom domains too):** header **`x-hs-portal-id`** (also `x-hs-hub-id`,
  `x-hubspot-correlation-id`); `<meta name="generator" content="HubSpot">`.
- **Sitemap:** `/sitemap.xml` (flat). Not always in `robots.txt`; some portals 404 it — fall back to
  the unauthenticated site-search API `GET https://api.hubapi.com/cms/v3/site-search/search?portalId={id}&type=KNOWLEDGE_ARTICLE&q=…`
  for URL discovery (returns snippets, not full bodies).
- **Article URL:** native KB tool `/knowledge/{slug}`; HubSpot's own (blog-engine) KB `/{category}/{slug}`.
- **Content container — TWO templates:** native KB → `article.knowledgebase-post`; blog-engine →
  `[itemprop="articleBody"]` / `#post-body`. Try both.
- **API:** `/cms/v3/knowledge-base/articles` needs a **private-app token** (`HUBSPOT_TOKEN`) and is a
  Service-Hub Pro/Enterprise feature — only for a customer's own portal.
- **Gotchas:** multilingual copies inflate the sitemap (`/es/`, `/de/`…) → `--locale`; detect by
  header, not domain (custom domains hide `hs-sites.com`); Cloudflare-fronted → use a browser UA.

### Gorgias (e.g. `tushy-support-center.gorgias.help` → `support.hellotushy.com`)
- **Fingerprint:** `*.gorgias.help` host (often 301/307 → custom domain); `robots.txt` contains
  `Allow: /api/help-centers/loader.js`; page HTML has `ghc-` classes (`ghc-app`, `ghc-last-updated`);
  Next.js (`__NEXT_DATA__`, `/_next/`).
- **Sitemap:** `/sitemap.xml` (flat; `<loc>`s point at the FINAL custom domain).
- **Article URL:** **`/{locale}/{slug}-{numericId}`** — NOT under `/articles/`, so the URL hint must
  match the trailing `-{id}` (the crawler's `GORGIAS_HINT` does this).
- **Content container:** the `<article>` tag (tightest body: the emotion-keyed `div.e1branct12`);
  strip `.ghc-article-rating-container`. The hashed `css-xxxxx` classes change between deploys — anchor
  on the `<article>` tag or `ghc-`/emotion keys.
- **Gotchas:** follow redirects (`curl -L`); multilingual sitemap → `--locale`; some subdomains 404
  after migration — verify reachability, fall back to the brand's custom domain.

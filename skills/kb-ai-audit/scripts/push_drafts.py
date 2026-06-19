# -*- coding: utf-8 -*-
"""push_drafts.py — push audited rewrites into a help desk as DRAFT articles, via API.

Supports the platforms that have an article-write API: Zendesk, Intercom, Freshdesk, HubSpot.
Gorgias has no public write API → use the Markdown pack (rewrite_pack.md) and paste.

Safety rules (enforced for every platform):
  * Creates NEW articles in DRAFT/unpublished state — never publishes, never overwrites the live one.
  * Dry-run by default; you must pass --execute to write anything.
  * Confirms platform + exact count before writing.
  * Credentials come from env vars only — never hard-coded.

Examples:
  python3 push_drafts.py --platform intercom  rewrites.json --list                 # show author/collection ids
  python3 push_drafts.py --platform intercom  rewrites.json --author 123 [--collection 456]
  python3 push_drafts.py --platform zendesk   rewrites.json --list                 # show section ids
  python3 push_drafts.py --platform zendesk   rewrites.json --section 789 [--locale en-us]
  python3 push_drafts.py --platform freshdesk rewrites.json --list                 # show folder ids
  python3 push_drafts.py --platform freshdesk rewrites.json --folder 321
  python3 push_drafts.py --platform hubspot   rewrites.json --category 555
  ...add --execute to actually create the drafts.

Env vars: INTERCOM_TOKEN | ZENDESK_SUBDOMAIN+ZENDESK_EMAIL+ZENDESK_TOKEN | FRESHDESK_DOMAIN+FRESHDESK_KEY | HUBSPOT_TOKEN
Stdlib only."""
import json, os, sys, argparse, base64, time, re, urllib.request, urllib.error
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from build_outputs import md_to_html
except Exception:
    try: from gen_rewrites import md_to_html
    except Exception: md_to_html = None

def to_html(md, strip_iframe=False):
    h = md_to_html(md) if md_to_html else "<p>" + (md or "").replace("\n\n", "</p><p>") + "</p>"
    if strip_iframe:
        h = re.sub(r'<iframe[^>]*src="([^"]+)"[^>]*>(?:</iframe>)?', r'<p><a href="\1">Watch the video</a></p>', h)
    return h

def req(method, url, headers, body=None):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(r, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"{method} {url} -> HTTP {e.code}: {e.read().decode('utf-8','replace')[:300]}")

def need(*names):
    miss = [n for n in names if not os.environ.get(n)]
    if miss: sys.exit("Missing env var(s): " + ", ".join(miss))

# ---------------- Zendesk ----------------
def zendesk(a, rewrites):
    need("ZENDESK_SUBDOMAIN", "ZENDESK_EMAIL", "ZENDESK_TOKEN")
    base = f"https://{os.environ['ZENDESK_SUBDOMAIN']}.zendesk.com"
    auth = "Basic " + base64.b64encode(f"{os.environ['ZENDESK_EMAIL']}/token:{os.environ['ZENDESK_TOKEN']}".encode()).decode()
    hdr = {"Authorization": auth, "Content-Type": "application/json"}
    loc = a.locale or "en-us"
    if a.list:
        d = req("GET", f"{base}/api/v2/help_center/{loc}/sections.json?per_page=100", hdr)
        print("Sections (use an id as --section):")
        for s in d.get("sections", []): print(f"  {s['id']:<12} {s.get('name','')}")
        return
    if not a.section: sys.exit("--section <id> required (run --list).")
    def create(rw):
        body = {"article": {"title": rw["new_title"], "body": to_html(rw.get("body", "")), "locale": loc, "draft": True}}
        d = req("POST", f"{base}/api/v2/help_center/{loc}/sections/{a.section}/articles.json", hdr, body)
        ar = d.get("article", d); return ar.get("id"), ar.get("html_url")
    return create

# ---------------- Intercom ----------------
def intercom(a, rewrites):
    need("INTERCOM_TOKEN")
    hdr = {"Authorization": f"Bearer {os.environ['INTERCOM_TOKEN']}", "Intercom-Version": "2.11",
           "Accept": "application/json", "Content-Type": "application/json"}
    if a.list:
        ad = req("GET", "https://api.intercom.io/admins", hdr)
        print("Teammates (use an id as --author):")
        for x in ad.get("admins", []): print(f"  {x.get('id'):<12} {x.get('name','')}  <{x.get('email','')}>")
        co = req("GET", "https://api.intercom.io/help_center/collections", hdr)
        print("Collections (use an id as --collection):")
        for c in co.get("data", []): print(f"  {c.get('id'):<12} {c.get('name','')}")
        return
    if not a.author: sys.exit("--author <teammate id> required (run --list).")
    def create(rw):
        body = {"title": rw["new_title"], "body": to_html(rw.get("body", ""), strip_iframe=True),
                "author_id": int(a.author), "state": "draft"}
        if a.collection: body["parent_id"] = int(a.collection); body["parent_type"] = "collection"
        d = req("POST", "https://api.intercom.io/articles", hdr, body); return d.get("id"), d.get("url")
    return create

# ---------------- Freshdesk ----------------
def freshdesk(a, rewrites):
    need("FRESHDESK_DOMAIN", "FRESHDESK_KEY")
    base = f"https://{os.environ['FRESHDESK_DOMAIN']}"
    auth = "Basic " + base64.b64encode(f"{os.environ['FRESHDESK_KEY']}:X".encode()).decode()
    hdr = {"Authorization": auth, "Content-Type": "application/json"}
    if a.list:
        cats = req("GET", f"{base}/api/v2/solutions/categories", hdr)
        print("Folders (use an id as --folder):")
        for c in cats:
            for f in req("GET", f"{base}/api/v2/solutions/categories/{c['id']}/folders", hdr):
                print(f"  {f['id']:<12} {c.get('name','')} / {f.get('name','')}")
        return
    if not a.folder: sys.exit("--folder <id> required (run --list).")
    def create(rw):
        body = {"title": rw["new_title"], "description": to_html(rw.get("body", "")), "status": 1}  # 1=draft
        d = req("POST", f"{base}/api/v2/solutions/folders/{a.folder}/articles", hdr, body)
        return d.get("id"), f"{base}/support/solutions/articles/{d.get('id')}"
    return create

# ---------------- HubSpot ----------------
def hubspot(a, rewrites):
    need("HUBSPOT_TOKEN")
    hdr = {"Authorization": f"Bearer {os.environ['HUBSPOT_TOKEN']}", "Content-Type": "application/json"}
    base = "https://api.hubapi.com/cms/v3/knowledge-base"
    if a.list:
        try:
            d = req("GET", f"{base}/categories?limit=100", hdr)
            print("Categories (use an id as --category):")
            for c in d.get("results", []): print(f"  {c.get('id'):<12} {c.get('name') or c.get('label','')}")
        except Exception as e:
            print("Couldn't list categories (the KB API surface varies by portal / needs Service Hub Pro+):\n ", e)
        return
    print("  NOTE: HubSpot's KB write API requires Service Hub Pro/Enterprise and a private-app token with"
          " knowledge-base scope; the exact endpoint can vary by portal. If a create 400s, fall back to the"
          " Markdown pack.")
    def create(rw):
        body = {"name": rw["new_title"], "postBody": to_html(rw.get("body", "")), "state": "DRAFT"}
        if a.category: body["categoryId"] = a.category
        d = req("POST", f"{base}/articles", hdr, body); return d.get("id"), d.get("url")
    return create

PLATFORMS = {"zendesk": zendesk, "intercom": intercom, "freshdesk": freshdesk, "hubspot": hubspot}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rewrites", nargs="?", default="rewrites.json")
    ap.add_argument("--platform", required=True, choices=list(PLATFORMS) + ["gorgias"])
    ap.add_argument("--list", action="store_true", help="list the target containers (sections/collections/folders/categories)")
    ap.add_argument("--execute", action="store_true", help="actually create the drafts (otherwise dry-run)")
    ap.add_argument("--section"); ap.add_argument("--locale", default="en-us")          # zendesk
    ap.add_argument("--author"); ap.add_argument("--collection")                         # intercom
    ap.add_argument("--folder")                                                          # freshdesk
    ap.add_argument("--category")                                                        # hubspot
    a = ap.parse_args()
    if a.platform == "gorgias":
        sys.exit("Gorgias has no public article-write API. Deliver the Markdown pack (rewrite_pack.md) and paste each rewrite into the Gorgias Help Center editor.")
    rw = json.loads(Path(a.rewrites).read_text())
    rewrites = rw.get("rewrites", rw) if isinstance(rw, dict) else rw
    handler = PLATFORMS[a.platform](a, rewrites)
    if handler is None: return  # --list path printed and returned
    print(f"Platform: {a.platform} · {len(rewrites)} article(s) will be created as DRAFTS (never published).")
    if not a.execute:
        print("DRY RUN — nothing written. Re-run with --execute to create the drafts.\n")
        for i, w in enumerate(rewrites, 1): print(f"  {i:>2}. \"{w.get('new_title')}\"")
        return
    created = []
    for i, w in enumerate(rewrites, 1):
        try:
            cid, url = handler(w); created.append((cid, url))
            print(f"  ✓ draft {i}/{len(rewrites)}  id={cid}  {w.get('new_title')[:46]}")
        except Exception as e:
            print(f"  ✗ {i}/{len(rewrites)} FAILED: {e}")
        time.sleep(0.3)
    print(f"\nCreated {len(created)} draft(s). Review and publish them from the {a.platform} editor.")
    for cid, url in created: print(f"  id {cid} · {url}")

if __name__ == "__main__":
    main()

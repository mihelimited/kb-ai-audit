# -*- coding: utf-8 -*-
"""push_to_intercom.py — push audited rewrites into Intercom as DRAFT articles via the API.

Safety rules (enforced):
  * Creates NEW articles in **draft** state — never publishes, never overwrites the live article.
  * Dry-run by default; you must pass --execute to write anything.
  * Confirms the platform + exact count before writing.
  * Reads the token from the INTERCOM_TOKEN env var (never hard-coded).

Setup (one-off):
  export INTERCOM_TOKEN="<your Intercom access token>"
  python3 push_to_intercom.py --list-admins         # find an author_id (a teammate id)
  python3 push_to_intercom.py --list-collections     # find a collection id to file drafts under
Then:
  python3 push_to_intercom.py --author 123456 [--collection 789] rewrites.json          # dry run
  python3 push_to_intercom.py --author 123456 [--collection 789] rewrites.json --execute # creates drafts

Stdlib only. Body Markdown is converted to the HTML subset Intercom accepts (headings, p, ul/ol,
strong/em, a, img). Note: video <iframe> embeds are NOT supported in Intercom article bodies — they
are dropped and replaced with a link, so confirm any video steps are also written out in words
(the audit's 'spells out video' check ensures this)."""
import json, os, sys, argparse, urllib.request, urllib.error, re, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from build_outputs import md_to_html          # plugin: md_to_html lives in build_outputs
except Exception:
    try:
        from gen_rewrites import md_to_html        # local working-dir fallback
    except Exception:
        md_to_html = None

API = "https://api.intercom.io"
TOKEN = os.environ.get("INTERCOM_TOKEN", "")

def _hdr():
    return {"Authorization": f"Bearer {TOKEN}", "Intercom-Version": "2.11",
            "Accept": "application/json", "Content-Type": "application/json"}

def _req(method, path, body=None):
    url = path if path.startswith("http") else API + path
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers=_hdr(), method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"{method} {path} -> HTTP {e.code}: {e.read().decode('utf-8','replace')[:400]}")

def md_to_intercom_html(md):
    """Markdown rewrite -> Intercom-safe HTML. Drops video iframes (unsupported), keeps images."""
    if md_to_html:
        h = md_to_html(md)
    else:
        h = "<p>" + md.replace("\n\n", "</p><p>") + "</p>"
    # replace iframe embeds with a plain link (Intercom strips iframes)
    h = re.sub(r'<iframe[^>]*src="([^"]+)"[^>]*>(?:</iframe>)?',
               r'<p><a href="\1">Watch the video</a></p>', h)
    return h

def list_admins():
    d = _req("GET", "/admins")
    print("Teammates (use an id as --author):")
    for a in d.get("admins", []):
        print(f"  {a.get('id'):<12} {a.get('name','')}  <{a.get('email','')}>")

def list_collections():
    d = _req("GET", "/help_center/collections")
    print("Collections (use an id as --collection):")
    for c in d.get("data", []):
        print(f"  {c.get('id'):<12} {c.get('name','')}")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rewrites", nargs="?", help="rewrites.json")
    ap.add_argument("--author", help="Intercom teammate id used as the article author (required to create)")
    ap.add_argument("--collection", help="Collection id to file the drafts under (optional)")
    ap.add_argument("--execute", action="store_true", help="actually create the drafts (otherwise dry-run)")
    ap.add_argument("--list-admins", action="store_true")
    ap.add_argument("--list-collections", action="store_true")
    a = ap.parse_args()
    if not TOKEN:
        sys.exit("Set INTERCOM_TOKEN first:  export INTERCOM_TOKEN=...")
    if a.list_admins: return list_admins()
    if a.list_collections: return list_collections()
    if not a.rewrites: sys.exit("Pass rewrites.json (or use --list-admins / --list-collections).")

    rw = json.loads(Path(a.rewrites).read_text())
    rewrites = rw.get("rewrites", rw) if isinstance(rw, dict) else rw
    print(f"Platform: Intercom · {len(rewrites)} article(s) will be created as DRAFTS (never published).")
    if not a.execute:
        print("DRY RUN — nothing written. Re-run with --execute to create the drafts.\n")
        for i, w in enumerate(rewrites, 1):
            html = md_to_intercom_html(w.get("body", ""))
            print(f"  {i:>2}. \"{w.get('new_title')}\"  ({len(html)} chars HTML)"
                  + (f"  -> collection {a.collection}" if a.collection else ""))
        print("\nNeed an --author id? run --list-admins.  A --collection id? run --list-collections.")
        return
    if not a.author:
        sys.exit("--author <teammate id> is required to create articles. Run --list-admins to find one.")
    created = []
    for i, w in enumerate(rewrites, 1):
        body = {"title": w.get("new_title"), "body": md_to_intercom_html(w.get("body", "")),
                "author_id": int(a.author), "state": "draft"}
        if a.collection:
            body["parent_id"] = int(a.collection); body["parent_type"] = "collection"
        res = _req("POST", "/articles", body)
        created.append((res.get("id"), res.get("url") or res.get("title")))
        print(f"  ✓ draft {i}/{len(rewrites)}  id={res.get('id')}  {w.get('new_title')[:48]}")
        time.sleep(0.3)
    print(f"\nCreated {len(created)} draft article(s) in Intercom. Review and publish them from the Help Center editor.")
    for cid, url in created:
        print(f"  id {cid} · {url}")

if __name__ == "__main__":
    main()

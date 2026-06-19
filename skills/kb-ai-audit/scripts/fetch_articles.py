#!/usr/bin/env python3
"""
fetch_articles.py - pull a whole help centre into articles.json, for any platform.

Auto-detects the platform from the URL (or pass --platform), then uses the cleanest
route available:

  Zendesk    -> public Help Center API (no auth)            [fully automatic]
  Intercom   -> Articles API if INTERCOM_TOKEN is set, else crawl
  Freshdesk  -> Solutions API if FRESHDESK_KEY is set, else crawl
  HubSpot    -> Knowledge Base API if HUBSPOT_TOKEN is set, else crawl
  Gorgias    -> crawl (no public article API)
  unknown    -> crawl (sitemap -> article pages -> main content)

Every article is normalised to the schema kb_audit.py expects:
  {id, title, html_url, body(html), updated_at, section_id, label_names, vote_count}

Stdlib only. Needs normal network access (run in Claude Code or any local run).

  python3 fetch_articles.py https://support.mybirdbuddy.com -o articles.json
  python3 fetch_articles.py https://help.example.com --platform intercom --max 200
"""
import json, re, sys, os, argparse, urllib.request, urllib.error, time, html
from urllib.parse import urlparse, urljoin
from html.parser import HTMLParser

UA={"User-Agent":"kb-ai-audit/0.2"}

def host_of(u):
    p=urlparse(u if "://" in u else "https://"+u); return f"{p.scheme}://{p.netloc}"

def get(url, headers=None, timeout=30):
    req=urllib.request.Request(url, headers={**UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")

def get_json(url, headers=None):
    return json.loads(get(url, headers))

def head_info(url, headers=None, timeout=20):
    """Return (status, {lowercased header: value}, body_text). Used for fingerprinting on custom
    domains — response headers are the most reliable signal and survive vanity domains."""
    req=urllib.request.Request(url, headers={**UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        hdrs={k.lower():v for k,v in r.headers.items()}
        return r.status, hdrs, r.read().decode("utf-8","replace")

# ---------------- platform detection ----------------
def detect_platform(url):
    h=urlparse(url if "://" in url else "https://"+url).netloc.lower()
    if "zendesk.com" in h: return "zendesk"
    if "intercom.help" in h or "intercom.io" in h: return "intercom"
    if "freshdesk.com" in h or "freshworks.com" in h: return "freshdesk"
    if "hs-sites.com" in h or "hubspot" in h: return "hubspot"
    if "gorgias.help" in h: return "gorgias"
    # custom domain: response HEADERS are the strongest fingerprint (survive vanity domains)
    base=host_of(url)
    try:
        _, hdrs, body = head_info(base)
        bl=body.lower()
        if "x-hs-portal-id" in hdrs or "x-hs-hub-id" in hdrs or 'content="hubspot"' in bl: return "hubspot"
        if "x-intercom-version" in hdrs or "intercom.help" in bl: return "intercom"
        # Freshdesk: x-fw-ratelimiting-managed / freshedge.net in report-to/nel, or /support/ paths
        if "x-fw-ratelimiting-managed" in hdrs or "freshedge.net" in (hdrs.get("report-to","")+hdrs.get("nel","")) \
           or "fw-content--single-article" in bl or "freshdesk" in bl or "freshworks" in bl: return "freshdesk"
        # Gorgias: its robots.txt template references the help-centers loader; pages carry ghc- classes
        if "ghc-app" in bl or "gorgiaschat" in bl.replace(" ",""):
            return "gorgias"
        try:
            rb=get(base+"/robots.txt").lower()
            if "help-centers/loader.js" in rb: return "gorgias"
        except Exception: pass
        for key,plat in [("zendesk","zendesk"),("gorgias","gorgias")]:
            if key in bl: return plat
        try:
            get(base+"/api/v2/help_center/en-us/articles.json?per_page=1"); return "zendesk"
        except Exception: pass
    except Exception: pass
    return "unknown"

def norm(a, **extra):
    d={"id":a.get("id"),"title":a.get("title") or a.get("name"),"html_url":a.get("html_url") or a.get("url"),
       "body":a.get("body") or a.get("description") or "","updated_at":a.get("updated_at"),
       "section_id":a.get("section_id") or a.get("folder_id") or a.get("parent_id"),
       "label_names":a.get("label_names",[]),"vote_count":a.get("vote_count",0)}
    d.update(extra); return d

# ---------------- Zendesk (auto, no auth) ----------------
def fetch_zendesk(base, locale, mx):
    url=f"{base}/api/v2/help_center/{locale}/articles.json?per_page=100"; out=[]; pg=1
    while url:
        d=get_json(url)
        for a in d.get("articles",[]):
            if a.get("draft"): continue
            out.append(norm(a))
        print(f"  zendesk page {pg}: {len(out)} so far")
        if mx and len(out)>=mx: return out[:mx]
        url=d.get("next_page"); pg+=1; time.sleep(0.2)
    return out

# ---------------- Intercom (token) ----------------
def fetch_intercom(base, mx):
    tok=os.environ.get("INTERCOM_TOKEN")
    if not tok: return None
    url="https://api.intercom.io/articles?per_page=250"; out=[]
    hdr={"Authorization":f"Bearer {tok}","Intercom-Version":"2.11","Accept":"application/json"}
    while url:
        d=get_json(url, hdr)
        for a in d.get("data",[]):
            if a.get("state")!="published": continue
            out.append(norm(a, id=a.get("id"), title=a.get("title"),
                            html_url=a.get("url"), body=a.get("body") or "",
                            updated_at=a.get("updated_at"), section_id=a.get("parent_id")))
        print(f"  intercom: {len(out)} so far")
        if mx and len(out)>=mx: return out[:mx]
        url=(d.get("pages") or {}).get("next"); time.sleep(0.2)
    return out

# ---------------- Freshdesk (key) ----------------
def fetch_freshdesk(base, mx):
    key=os.environ.get("FRESHDESK_KEY")
    if not key: return None
    import base64
    auth="Basic "+base64.b64encode(f"{key}:X".encode()).decode()
    hdr={"Authorization":auth}
    cats=get_json(f"{base}/api/v2/solutions/categories", hdr); out=[]
    for c in cats:
        folders=get_json(f"{base}/api/v2/solutions/categories/{c['id']}/folders", hdr)
        for f in folders:
            arts=get_json(f"{base}/api/v2/solutions/folders/{f['id']}/articles", hdr)
            for a in arts:
                if a.get("status")!=2: continue  # 2 = published
                out.append(norm(a, id=a.get("id"), title=a.get("title"),
                                html_url=f"{base}/support/solutions/articles/{a.get('id')}",
                                body=a.get("description") or "", updated_at=a.get("updated_at"),
                                section_id=f["id"], vote_count=(a.get("thumbs_up",0)+a.get("thumbs_down",0))))
                if mx and len(out)>=mx: return out[:mx]
    return out

# ---------------- HubSpot (token) ----------------
def fetch_hubspot(base, mx):
    tok=os.environ.get("HUBSPOT_TOKEN")
    if not tok: return None
    hdr={"Authorization":f"Bearer {tok}"}
    # HubSpot KB articles via Knowledge Base content API
    url="https://api.hubapi.com/cms/v3/knowledge-base/articles?limit=100&state=PUBLISHED"; out=[]
    while url:
        d=get_json(url, hdr)
        for a in d.get("results",[]):
            out.append(norm(a, id=a.get("id"), title=a.get("title") or a.get("name"),
                            html_url=a.get("url"), body=a.get("postBody") or a.get("body") or "",
                            updated_at=a.get("updated"), section_id=a.get("categoryId")))
        print(f"  hubspot: {len(out)} so far")
        if mx and len(out)>=mx: return out[:mx]
        url=(d.get("paging") or {}).get("next",{}).get("link"); time.sleep(0.2)
    return out

# ---------------- generic crawl (Gorgias / unknown / no-token fallback) ----------------
# article URLs: classic /articles/ /knowledge/ paths, OR Gorgias's /{locale}/{slug}-{numericId}
ARTICLE_HINT=re.compile(r"/(articles?|knowledge|hc|support/solutions/articles|kb|help)/", re.I)
GORGIAS_HINT=re.compile(r"/[a-z]{2}(-[A-Za-z]{2})?/[^/]+-\d+/?$")   # /en-US/how-to-…-79957
NONARTICLE=re.compile(r"/(categories|sections|collections|search|login|tags?)/", re.I)
# Article-body containers seen in the wild, in priority order. Cropping to one of these avoids
# grabbing the site header/nav (the classic bug: the first <main> on an Intercom page is the header).
CONTENT_CLASSES=("article_body","article-content-wrapper","article-body","fc-article-content",
                 "knowledgebase-post","article__body","post-body","kb-article-content")
def _classes(a): return (a.get("class") or "")
class MainExtractor(HTMLParser):
    """Capture the inner HTML of the article body. Prefers a known content container (by class or
    itemprop=articleBody), then a real <article>, then a <main> that is NOT the page header, then
    <body>. Drops script/style/nav/header/footer/aside/form/svg/button/noscript."""
    DROP={"script","style","nav","header","footer","aside","form","noscript","svg","button","path"}
    def __init__(self):
        super().__init__(convert_charrefs=False); self.buf=[]; self.depth=0; self.cap=False
        self.trig=None; self.drop_depth=0; self.title=None; self._in_title=False; self._in_h1=False
    def _is_content(self,t,a):
        cls=_classes(a).lower()
        if a.get("itemprop")=="articlebody": return True
        if any(c in cls for c in CONTENT_CLASSES): return True
        if t=="article": return True
        if t=="main" and "header" not in cls: return True
        if a.get("role")=="main" and "header" not in cls: return True
        return False
    def handle_starttag(self,t,attrs):
        a={k.lower():v for k,v in attrs}
        if t=="title": self._in_title=True
        if not self.cap:
            if t=="h1": self._in_h1=True
            if self._is_content(t,a): self.cap=True; self.trig=t; self.depth=1
            return
        if t in self.DROP: self.drop_depth+=1; return
        if self.drop_depth: return
        if t==self.trig: self.depth+=1
        self.buf.append(self._tag(t,attrs))
    def handle_startendtag(self,t,attrs):
        if self.cap and not self.drop_depth and t in ("img","br","hr"): self.buf.append(self._tag(t,attrs,close=True))
    def handle_endtag(self,t):
        if t=="title": self._in_title=False
        if t=="h1": self._in_h1=False
        if not self.cap: return
        if t in self.DROP:
            if self.drop_depth: self.drop_depth-=1
            return
        if self.drop_depth: return
        if t==self.trig:
            self.depth-=1
            if self.depth<=0: self.cap=False; return
        self.buf.append(f"</{t}>")
    def handle_data(self,d):
        if self._in_title and not self.title: self.title=d.strip()
        if self._in_h1 and not self.title and d.strip(): self.title=d.strip()
        if self.cap and not self.drop_depth and d.strip(): self.buf.append(d)
    def _tag(self,t,attrs,close=False):
        a="".join(f' {k}="{html.escape(v or "")}"' for k,v in attrs if k in ("src","alt","href"))
        return f"<{t}{a}{'/' if close else ''}>"
    def html_out(self): return "".join(self.buf)

def _article_id(u):
    m=re.search(r"(\d{4,})", u.rstrip("/").rsplit("/",1)[-1]); return m.group(1) if m else u

# ---- no-key embedded JSON: Next.js help centres (Intercom, Gorgias) ship the full article in
# __NEXT_DATA__, which is cleaner than scraping the rendered DOM. Use it when it's at least as
# complete as the DOM crop.
def _blocks_to_html(blocks):
    out=[]
    for b in blocks:
        if not isinstance(b,dict): continue
        t=(b.get("type") or "").lower(); txt=b.get("text") or ""
        if t in ("orderedlist","unorderedlist","list"):
            items=b.get("items") or ([txt] if txt else []); tag="ol" if "order" in t else "ul"
            out.append("<"+tag+">"+"".join(f"<li>{it}</li>" for it in items)+f"</{tag}>")
        elif "head" in t or t=="subheading": out.append(f"<h2>{txt}</h2>")
        elif "image" in t:
            src=b.get("url") or b.get("src") or b.get("imageUrl") or ""
            if src: out.append(f'<img src="{src}" alt="{html.escape(b.get("alt") or "")}">')
        elif t in ("video","iframe","embed"):
            src=b.get("url") or b.get("src") or ""
            if src: out.append(f'<iframe src="{src}"></iframe>')
        elif txt: out.append(f"<p>{txt}</p>")
    return "".join(out)

def _next_data_body(page):
    """Return (title, body_html) from a Next.js __NEXT_DATA__ blob, or (None, None)."""
    m=re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', page, re.S)
    if not m: return None,None
    try: d=json.loads(m.group(1))
    except Exception: return None,None
    pp=((d.get("props") or {}).get("pageProps")) or {}
    if pp.get("htmlContent"):                        # Gorgias: already clean HTML
        return (pp.get("title") or pp.get("name")), pp["htmlContent"]
    ac=pp.get("articleContent") or {}                # Intercom: structured blocks
    if ac.get("blocks"): return ac.get("title"), _blocks_to_html(ac["blocks"])
    art=pp.get("article") or {}
    if art.get("body"): return art.get("title"), art["body"]
    return None,None

def _txt_len(h): return len(re.sub(r"<[^>]+>"," ",h or "").split())

def discover_urls(base, mx, locale=None):
    """Find article URLs from the sitemap. Filters to a single language (so multilingual help
    centres aren't graded N times) and de-dupes by article id. Freshdesk's sitemap lives at
    /support/sitemap.xml, not /sitemap.xml — both are tried."""
    raw=[]
    for sm in ["/sitemap.xml","/support/sitemap.xml","/sitemap_index.xml","/hc/sitemap.xml","/help/sitemap.xml"]:
        try: xml=get(base+sm)
        except Exception: continue
        locs=re.findall(r"<loc>(.*?)</loc>", xml)
        if any(l.endswith(".xml") for l in locs):           # sitemap index → fetch children
            for child in locs[:30]:
                try: locs+=re.findall(r"<loc>(.*?)</loc>", get(child))
                except Exception: pass
        for l in locs:
            l=l.strip()
            if NONARTICLE.search(l): continue
            if ARTICLE_HINT.search(l) or GORGIAS_HINT.search(l): raw.append(l)
        if raw: break
    # language filter: keep only /<lang>/ or /<lang-XX>/ URLs when a locale is requested and present
    lang=(locale or "").split("-")[0].lower()
    if lang:
        rx=re.compile(r"/"+lang+r"(-[a-zA-Z]{2})?/", re.I)
        filt=[u for u in raw if rx.search(u)]
        if filt: raw=filt                                    # fall back to all if the locale isn't in the URLs
    seen=set(); urls=[]
    for u in raw:
        k=_article_id(u)
        if k in seen: continue
        seen.add(k); urls.append(u)
    return urls[: (mx or 100000)]

def fetch_generic(base, mx, label="crawl", locale=None):
    urls=discover_urls(base, mx, locale); out=[]
    if not urls:
        print(f"  {label}: no sitemap/article URLs found — try the platform API or pass a sitemap."); return out
    print(f"  {label}: {len(urls)} article URL(s)" + (f" (locale {locale})" if locale else ""))
    for i,u in enumerate(urls,1):
        try: page=get(u)
        except Exception: continue
        ex=MainExtractor()
        try: ex.feed(page)
        except Exception: pass
        dom_body=ex.html_out(); dom_title=ex.title
        nd_title,nd_body=_next_data_body(page)          # no-key embedded JSON (Intercom/Gorgias)
        if nd_body and _txt_len(nd_body)>=_txt_len(dom_body)*0.8:
            body=nd_body; title=nd_title or dom_title
        else:
            body=dom_body or page; title=dom_title
        title=title or (re.search(r"<h1[^>]*>(.*?)</h1>", page, re.S|re.I) or [None,u])[1]
        title=re.sub(r"<[^>]+>","",title or u).strip()
        title=re.sub(r"\s*[|·\-–]\s*[^|·\-–]{0,40}$","",title) if " | " in title or " · " in title else title
        out.append(norm({}, id=u.rstrip("/").rsplit("/",1)[-1], title=title[:200], html_url=u, body=body,
                        updated_at=None, section_id=None, vote_count=0))
        if i%20==0: print(f"  {label}: {i}/{len(urls)}")
        if mx and len(out)>=mx: break
        time.sleep(0.15)
    return out

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("url"); ap.add_argument("-o","--out",default="articles.json")
    ap.add_argument("--platform",choices=["zendesk","intercom","freshdesk","hubspot","gorgias","unknown"])
    ap.add_argument("--locale",default="en-us"); ap.add_argument("--max",type=int,default=0)
    a=ap.parse_args()
    base=host_of(a.url); plat=a.platform or detect_platform(a.url)
    print(f"Platform: {plat}  ·  {base}")
    arts=None
    if plat=="zendesk": arts=fetch_zendesk(base,a.locale,a.max)
    elif plat=="intercom": arts=fetch_intercom(base,a.max)
    elif plat=="freshdesk": arts=fetch_freshdesk(base,a.max)
    elif plat=="hubspot": arts=fetch_hubspot(base,a.max)
    if arts is None:  # token missing or gorgias/unknown
        if plat in ("intercom","freshdesk","hubspot"):
            print(f"  No API token for {plat} (set the env var) — falling back to crawl.")
        arts=fetch_generic(base,a.max,plat,a.locale)
    json.dump(arts, open(a.out,"w"), indent=2, default=str)
    print(f"Saved {len(arts)} articles -> {a.out}")

if __name__=="__main__": main()

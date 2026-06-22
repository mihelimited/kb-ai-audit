# -*- coding: utf-8 -*-
"""build_branded.py — generate the three HTML surfaces (dashboard, scorecard, rewrite pages)
faithfully reproducing the My AskAI redesign handoff, fed by results.json + rewrites.json.
Self-contained static HTML/CSS/JS; assets in out/assets/. Replaces the re-skin approach."""
import json, re, html, sys, os, argparse, shutil, base64
from pathlib import Path

_ap = argparse.ArgumentParser(description="Generate the My AskAI redesign HTML surfaces.")
_ap.add_argument("results", nargs="?", default="results.json")
_ap.add_argument("--rewrites", default="rewrites.json")
_ap.add_argument("--kb-name", default="Help Center")
_ap.add_argument("--outdir", default="out")
_ap.add_argument("--assets", default=None, help="dir with wordmark.png + logo-texture.png to copy into <outdir>/assets")
_A = _ap.parse_args()

# md_to_html: prefer the plugin's build_outputs (same dir), else the local gen_rewrites helper
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from build_outputs import md_to_html
except Exception:
    sys.path.insert(0, ".")
    from gen_rewrites import md_to_html

OUT = Path(_A.outdir); OUT.mkdir(parents=True, exist_ok=True)
KB = _A.kb_name
RES = json.loads(Path(_A.results).read_text())
RW = json.loads(Path(_A.rewrites).read_text()).get("rewrites", [])
# brand assets: copy from --assets (or a sibling assets/ dir) into <outdir>/assets if not already there
_asrc = _A.assets or os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
if os.path.isdir(_asrc):
    (OUT / "assets").mkdir(exist_ok=True)
    for _fn in ("wordmark.png", "logo-texture.png"):
        _p = os.path.join(_asrc, _fn)
        if os.path.exists(_p) and not (OUT / "assets" / _fn).exists():
            shutil.copy(_p, OUT / "assets" / _fn)

def _data_uri(path):
    """Inline an image file as a base64 data URI so report.html/report.pdf are fully
    self-contained (the PDF renderer doesn't need the assets/ folder alongside it)."""
    import base64, mimetypes
    p = Path(path)
    if not p.exists():
        return ""
    mime = mimetypes.guess_type(str(p))[0] or "image/png"
    return f"data:{mime};base64," + base64.b64encode(p.read_bytes()).decode("ascii")

def esc(s): return html.escape(str(s if s is not None else ""), quote=True)
def slugify(s):
    s = re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")
    return s[:50].strip("-")
def grade_color(letter):
    c = (letter or "")[:1]
    return "#EA3609" if c in "FD" else ("#8A6D3B" if c == "C" else ("#2F7D57" if c in "BA" else "#1B1B1B"))
def bar_color(pct):
    return "#EA3609" if pct < 40 else ("#E0892B" if pct < 70 else "#2F7D57")
def pri_val(band): return (band or "").lower().replace(" ", "")

GROUP_BLURB = {
 "Can the AI find the right answer?": "Whether the agent can match a customer's question to this article at all.",
 "Can the AI use the answer?": "Whether the agent can read a section on its own and hand back something useful.",
 "Is it the right, current answer?": "Whether the agent can trust it not to be stale, contradicted, or over-promising.",
}

HEAD = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Geist:wght@300;400;500;600;700&display=swap" rel="stylesheet">
__HEAD_EXTRA__
<style>
:root{--font-display:'Acid Grotesk','Geist','Geist Fallback',system-ui,sans-serif;
--font-ui:'Geist','Geist Fallback',system-ui,-apple-system,Segoe UI,Roboto,sans-serif;
--font-body:'Geist','Geist Fallback',system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
*{box-sizing:border-box}body{margin:0;font-family:var(--font-body);color:#1B1B1B;-webkit-font-smoothing:antialiased}
input:focus,select:focus,textarea:focus,button:focus-visible,a:focus-visible,summary:focus-visible{outline:2px solid #EA3609;outline-offset:2px}
::placeholder{color:#A8A29A}
__EXTRA_CSS__
</style></head><body>
"""

def page(title, extra_css, inner, head_extra=""):
    return (HEAD.replace("__TITLE__", esc(title)).replace("__HEAD_EXTRA__", head_extra)
            .replace("__EXTRA_CSS__", extra_css) + inner + "</body></html>")

WORDMARK = '<img src="assets/wordmark.png" alt="My AskAI" style="height:%dpx;display:block">'

# Homepage links carry UTM tags so clicks from each audit surface are attributable.
def home_url(content, medium="dashboard"):
    return ("https://myaskai.com/?utm_source=kb-audit&utm_medium=" + medium
            + "&utm_campaign=kb-ai-audit&utm_content=" + content)

# Favicon (inline SVG of the My AskAI speech-bubble mark) + social meta so a shared
# link unfurls with the brand instead of a bare URL. og:image is relative so it
# resolves against the page URL when the report is hosted.
_FAV_SVG = ("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'>"
            "<rect width='32' height='32' rx='8' fill='#EA3609'/>"
            "<rect x='7' y='7.5' width='18' height='12.5' rx='4' fill='#FBF8F3'/>"
            "<path d='M11.5 20L11.5 25L16.5 20Z' fill='#FBF8F3'/></svg>")
FAVICON = "data:image/svg+xml;base64," + base64.b64encode(_FAV_SVG.encode()).decode()
FAVICON_LINK = '<link rel="icon" href="' + FAVICON + '">'

def social_head(title, desc, image="assets/wordmark.png"):
    """OG/Twitter meta + favicon so a shared link unfurls with the My AskAI brand."""
    t, d = esc(title), esc(desc)
    return (FAVICON_LINK
            + '<meta name="description" content="' + d + '">'
            + '<meta property="og:type" content="website">'
            + '<meta property="og:site_name" content="My AskAI">'
            + '<meta property="og:title" content="' + t + '">'
            + '<meta property="og:description" content="' + d + '">'
            + '<meta property="og:image" content="' + image + '">'
            + '<meta name="twitter:card" content="summary">'
            + '<meta name="twitter:title" content="' + t + '">'
            + '<meta name="twitter:description" content="' + d + '">')

CARD = "background:#fff;border-radius:16px;box-shadow:0 1px 0 rgba(0,0,0,0.04),0 8px 24px rgba(0,0,0,0.06);padding:22px"
PTITLE = "font:500 16.5px var(--font-ui);color:#1B1B1B;letter-spacing:-.01em;margin-bottom:3px"
PBLURB = "font:300 13px/1.4 var(--font-body);color:#868181;margin-bottom:16px"
ITEM = "padding:11px 0;border-top:1px solid rgba(0,0,0,0.06);font:300 14px/1.5 var(--font-body);color:#2F2F2F"
OKLINE = "font:400 13.5px var(--font-body);color:#2F7D57"

def coh_svg(dates):
    bs = dates["buckets"]; mx = max([b["count"] for b in bs] + [1]); W, H, pad = 620, 184, 8
    slot = (W - 2*pad)/len(bs); bw = slot*0.62; out = []
    for i, b in enumerate(bs):
        h = round(b["count"]/mx*(H-58)); x = pad + i*slot + (slot-bw)/2; y = H-36-h
        fill = "#EA3609" if b.get("hot") and b["count"] else "#1B1B1B"
        out.append(f'<rect x="{x:.0f}" y="{y:.0f}" width="{bw:.0f}" height="{max(h,2)}" rx="4" fill="{fill}"/>')
        out.append(f'<text x="{x+bw/2:.0f}" y="{y-6:.0f}" text-anchor="middle" font-family="var(--font-ui)" font-size="13" font-weight="600" fill="#1B1B1B">{b["count"]}</text>')
        out.append(f'<text x="{x+bw/2:.0f}" y="{H-12}" text-anchor="middle" font-family="var(--font-body)" font-size="11.5" font-weight="300" fill="#868181">{esc(b["label"])}</text>')
    return f'<svg viewBox="0 0 {W} {H}" width="100%" style="max-width:620px;display:block;margin:2px 0 4px" role="img" aria-label="Freshness distribution">{"".join(out)}</svg>'

RBTN = "font:500 11.5px var(--font-ui);color:#EA3609;background:#fff;border:1px solid #EA3609;border-radius:1000px;padding:5px 12px;cursor:pointer;white-space:nowrap;flex:none"
def resolve_btn(label, data):
    attrs = " ".join(f'data-{k}="{esc(v)}"' for k, v in data.items() if v is not None)
    return f'<button type="button" class="resolvebtn" {attrs} style="{RBTN}">{esc(label)}</button>'

def coh_panel(title, blurb_html, inner, span=False):
    # blurb_html is trusted static markup (may contain <em>); titles are escaped
    gc = ';grid-column:1/-1' if span else ''
    blurb = f'<div style="{PBLURB}">{blurb_html}</div>' if blurb_html else ''
    return (f'<div style="{CARD}{gc}"><div style="{PTITLE}">{esc(title)}</div>'
            f'{blurb}{inner}</div>')

def build_coherence_section():
    c = RES.get("corpus")
    if not c:
        return ""
    okmark = f'<div style="{OKLINE}">&#10003; None found — nice.</div>'
    panels = []

    # Coverage gaps (full width — headline)
    cov = c["coverage"]
    if cov["status"] == "locked":
        inner = (f'<div style="background:#FBF8F3;border:1px dashed #EA3609;border-radius:12px;padding:16px 18px;color:#1B1B1B;font:300 14px/1.55 var(--font-body)">'
                 f'<b style="font-weight:600">Locked.</b> {esc(cov["hint"])} '
                 f'Re-run with <code style="background:#fff;border:1px solid rgba(0,0,0,0.1);border-radius:6px;padding:1px 6px;font-size:12.5px">--tickets&nbsp;export.csv</code> '
                 f'(or paste your top ticket subjects) and this fills in — usually the single biggest win.</div>')
    elif cov["status"] == "ok" and cov.get("gaps"):
        mxv = max(g["volume"] for g in cov["gaps"]); rows = ""
        for g in cov["gaps"]:
            eg = " &middot; ".join('&ldquo;'+esc(e)+'&rdquo;' for e in g["examples"])
            rows += (f'<div style="{ITEM};display:flex;gap:14px;align-items:baseline">'
                     f'<span style="flex:none;width:74px;font:600 13px var(--font-ui);color:#EA3609;font-variant-numeric:tabular-nums">{g["volume"]} tickets</span>'
                     f'<span style="flex:1;min-width:0"><span style="display:inline-block;height:8px;border-radius:4px;background:#EA3609;width:{round(g["volume"]/mxv*120)+10}px;vertical-align:middle;margin-right:10px"></span>'
                     f'no article on <b style="font-weight:600;color:#1B1B1B">{esc(", ".join(g["terms"]))}</b>'
                     f'<div style="font:300 12.5px var(--font-body);color:#A8A29A;margin-top:3px">e.g. {eg}</div></span></div>')
        inner = f'<div style="font:500 14px var(--font-ui);color:#1B1B1B;margin-bottom:4px">{cov["covered_pct"]}% of ticket topics are covered by an article <span style="font-weight:300;color:#868181">({cov["tickets"]} tickets read)</span></div>{rows}'
    else:
        inner = f'<div style="{OKLINE}">&#10003; Every ticket topic maps to an article ({cov.get("tickets",0)} tickets read).</div>'
    panels.append(coh_panel("Questions with no article", "The most common reason an AI can't resolve is that no article exists for the question. Drawn from your ticket export.", inner, span=True))

    # Contradictions
    con = c["contradictions"]
    if con:
        rows = ""
        for f in con:
            pre = "$" if f["unit"] == "money" else ""; post = "%" if f["unit"] == "percent" else ("" if f["unit"] in ("money", "percent") else " "+f["unit"]+"s")
            btn = resolve_btn("Reconcile", {"kind": "reconcile", "a": f["a"], "b": f["b"], "aurl": f.get("a_url"),
                                            "burl": f.get("b_url"), "subject": f["subject"], "aval": str(f["a_val"]), "bval": str(f["b_val"])})
            rows += (f'<div style="{ITEM};display:flex;gap:12px;align-items:flex-start;justify-content:space-between">'
                     f'<div style="min-width:0"><span style="color:#EA3609;font-weight:600">&#9888; {esc(f["subject"])}</span> &mdash; '
                     f'<b style="font-weight:600;color:#1B1B1B">{pre}{esc(f["a_val"])}{post}</b> in &ldquo;{esc(f["a"])}&rdquo; '
                     f'vs <b style="font-weight:600;color:#1B1B1B">{pre}{esc(f["b_val"])}{post}</b> in &ldquo;{esc(f["b"])}&rdquo;</div>{btn}</div>')
        inner = rows
    else:
        inner = okmark
    panels.append(coh_panel("Articles that disagree", "The AI answers from one article at a time — if two state different facts, it gives whichever it lands on. Reconcile fixes both to agree.", inner))

    # Near-duplicates
    col = c["collisions"]
    if col:
        def coll_row(p):
            btn = resolve_btn("Merge", {"kind": "merge", "a": p["a"], "b": p["b"], "aurl": p.get("a_url"), "burl": p.get("b_url")})
            return (f'<div style="{ITEM};display:flex;gap:12px;align-items:flex-start;justify-content:space-between">'
                    f'<div style="min-width:0">&ldquo;{esc(p["a"])}&rdquo; &nbsp;&#8644;&nbsp; &ldquo;{esc(p["b"])}&rdquo;'
                    f'<div style="font:300 12.5px var(--font-body);color:#A8A29A;margin-top:3px">{round(p["similarity"]*100)}% overlap &middot; shared: {esc(", ".join(p["shared"][:4]))}</div></div>{btn}</div>')
        SHOWN = 4
        inner = "".join(coll_row(p) for p in col[:SHOWN])
        if len(col) > SHOWN:
            rest = "".join(coll_row(p) for p in col[SHOWN:])
            inner += (f'<details style="margin-top:2px"><summary style="cursor:pointer;list-style:none;font:500 13px var(--font-ui);color:#EA3609;padding:11px 0 2px">'
                      f'Show {len(col)-SHOWN} more pair(s) &#9662;</summary>{rest}</details>')
    else:
        inner = okmark
    panels.append(coh_panel("Articles competing for the same question", "Near-identical articles split the AI's pick — it may surface the weaker one. Merge combines them into one canonical answer.", inner))

    # Dates / freshness (full width — has the graph)
    dt = c["dates"]; stale = dt["stale_dated"]
    sub = ("When each article was last updated." if dt["mode"] == "age"
           else "No article carries a last-updated date, so this shows the most recent date each one <em>mentions</em> — a proxy for how current it is.")
    bits = []
    if dt.get("no_freshness_signal"):
        bits.append(f'<span style="color:#EA3609;font-weight:600">{dt["no_freshness_signal"]} of {dt["total"]} articles</span> carry no last-updated date, so the AI can\'t tell what\'s current')
    if dt["stale_count"]:
        bits.append(f'<span style="color:#EA3609;font-weight:600">{dt["stale_count"]}</span> quote a past-dated, time-sensitive detail it may present as live')
    stat = '<div style="font:400 14px/1.6 var(--font-body);color:#2F2F2F;margin-top:6px">' + "; ".join(bits) + ".</div>" if bits else f'<div style="{OKLINE}">&#10003; Freshness looks healthy.</div>'
    slist = ""
    if stale:
        slist = '<div style="font:300 12.5px/1.6 var(--font-body);color:#A8A29A;margin-top:8px">' + " &middot; ".join(f'&ldquo;{esc(s["title"])}&rdquo; ({esc(s["detail"])})' for s in stale[:6]) + ('…' if len(stale) > 6 else '') + '</div>'
    inner = coh_svg(dt) + stat + slist
    panels.append(coh_panel("How fresh is the help center?", sub, inner, span=True))

    # Disambiguation
    dis = c["disambiguation"]
    if dis:
        rows = ""
        for f in dis:
            links = " &nbsp;&middot;&nbsp; ".join(
                f'<a href="{esc(a["url"])}" target="_blank" rel="noopener" style="color:#EA3609;text-decoration:none">{esc(a["title"])}</a>'
                for a in f["articles"])
            rows += (f'<div style="{ITEM}"><b style="font-weight:600;color:#1B1B1B">{esc(" / ".join(f["names"]))}</b>'
                     f'<span style="font:300 12.5px var(--font-body);color:#A8A29A"> &mdash; used together without saying which is which in {f["count"]} article(s):</span>'
                     f'<div style="font:400 13px/1.8 var(--font-body);margin-top:4px">{links}</div></div>')
        inner = rows
    else:
        inner = okmark
    panels.append(coh_panel("Easily-confused names", "Similar product/plan/version names the KB never tells apart, so the AI conflates them (e.g. v1 vs v2). Open each article to add a distinction.", inner))

    grid = '<div style="display:grid;grid-template-columns:repeat(2,1fr);gap:16px;margin-top:16px">' + "".join(panels) + '</div>'
    return (f'<div class="wrap sec-pad" style="padding-top:34px">'
            f'<div style="display:flex;align-items:baseline;gap:12px;flex-wrap:wrap;margin-bottom:2px">'
            f'<h2 style="font:500 24px var(--font-ui);letter-spacing:-.02em;color:#1B1B1B;margin:0">Knowledge base coherence</h2>'
            f'<span style="font:300 14px var(--font-body);color:#868181">Looks <b style="font-weight:600;color:#1B1B1B">across and between</b> your articles — gaps, clashes, duplicates, stale facts and confusable names — what a per-article grade can\'t see.</span>'
            f'</div>{grid}</div>')

# ----------------------------------------------------------------- DASHBOARD
def build_dashboard():
    r = RES; results = r["results"]; roll = r["pattern_rollup"]; order = r["order"]
    total = r["article_count"]; needfix = sum(1 for a in results if a["fixes"] > 0)
    rewritten = len(RW); sp = r["style_profile"]
    weakest = min(order, key=lambda k: roll[k]["pass_pct"]); weak_pct = roll[weakest]["pass_pct"]; weak_short = roll[weakest]["short"]
    link_by_url = {}
    for i, w in enumerate(RW, 1):
        link_by_url[w.get("source_url")] = f"rewrite-{i:02d}-{slugify(w.get('new_title'))}.html"
    overall = r["overall_grade"]; gcol = grade_color(overall)

    # hero
    headline = (f"Every one of your {total} articles has something worth fixing before an AI agent can answer from it."
                if needfix == total else
                f"{needfix} of your {total} articles have something worth fixing before an AI agent can answer from them.")
    chips = (
      f'<div style="background:#fff;border:1px solid rgba(0,0,0,0.08);border-radius:12px;padding:11px 16px">'
      f'<span style="font-family:var(--font-display);font-weight:700;font-size:22px;color:#EA3609">{needfix}</span>'
      f'<span style="font:300 13px var(--font-body);color:#868181;margin-left:8px">worth fixing</span></div>'
      f'<div style="background:#fff;border:1px solid rgba(0,0,0,0.08);border-radius:12px;padding:11px 16px">'
      f'<span style="font-family:var(--font-display);font-weight:700;font-size:22px;color:#2F7D57">{rewritten}</span>'
      f'<span style="font:300 13px var(--font-body);color:#868181;margin-left:8px">already rewritten</span></div>'
      f'<div style="background:#fff;border:1px solid rgba(0,0,0,0.08);border-radius:12px;padding:11px 16px">'
      f'<span style="font-family:var(--font-display);font-weight:700;font-size:22px;color:#EA3609">{weak_pct}%</span>'
      f'<span style="font:300 13px var(--font-body);color:#868181;margin-left:8px">pass the weakest check, &ldquo;{esc(weak_short)}&rdquo;</span></div>')

    # by-question cards
    qcards = ""
    for g in r["groups"]:
        checks = [k for k in order if roll[k]["group"] == g]
        bars = ""
        for k in checks:
            pct = roll[k]["pass_pct"]
            bars += (f'<div style="margin:11px 0" title="{esc(roll[k]["why"])}">'
                     f'<div style="display:flex;justify-content:space-between;gap:10px;font:400 13px/1.3 var(--font-body);margin-bottom:8px">'
                     f'<span style="color:#1B1B1B">{esc(roll[k]["short"])}</span>'
                     f'<span style="font-weight:600;color:#1B1B1B;font-variant-numeric:tabular-nums">{pct}%</span></div>'
                     f'<div style="height:8px;border-radius:4px;background:#F1F1F1;overflow:hidden">'
                     f'<div style="width:{pct}%;height:100%;border-radius:4px;background:{bar_color(pct)}"></div></div></div>')
        qcards += (f'<div style="background:#fff;border-radius:16px;box-shadow:0 1px 0 rgba(0,0,0,0.04),0 8px 24px rgba(0,0,0,0.06);padding:22px">'
                   f'<div style="font:500 16.5px var(--font-ui);color:#EA3609;letter-spacing:-.01em;margin-bottom:3px">{esc(g)}</div>'
                   f'<div style="font:300 13px/1.4 var(--font-body);color:#868181;margin-bottom:16px">{esc(GROUP_BLURB.get(g,""))}</div>'
                   f'{bars}</div>')

    # priority rows
    rows = ""
    for a in results:
        fails = [k for k in order if a["checks"][k]["verdict"] == "Fix"]
        chips_html = ""
        for k in fails[:4]:
            chips_html += (f'<span title="{esc(roll[k]["short"]+" — "+a["checks"][k]["note"])}" '
                           f'style="font:500 11.5px var(--font-ui);color:#EA3609;background:#FFD9D9;border-radius:1000px;padding:3px 10px">{esc(roll[k]["short"])}</span>')
        more = len(fails) - 4
        more_html = (f'<span style="font:400 12px var(--font-body);color:#A8A29A">+{more} more</span>' if more > 0 else "")
        gc = grade_color(a["grade"]); hot = a["priority_band"] in ("Very high", "High")
        prist = f'color:{"#EA3609" if hot else "#A8A29A"};font-weight:{600 if hot else 400};font-size:12.5px'
        href = link_by_url.get(a["url"])
        view = (f'<a href="{esc(href)}" style="font:500 12.5px var(--font-ui);text-decoration:none;color:#FBF8F3;background:#1B1B1B;border-radius:1000px;padding:8px 14px;white-space:nowrap">View rewrite &rarr;</a>' if href else "")
        votes = (f'<span style="font:300 12.5px var(--font-body);color:#A8A29A">{a["vote_count"]:,} votes</span>' if a.get("vote_count") else "")
        rows += (
          f'<div class="prow" data-title="{esc(a["title"].lower())}" data-grade="{esc(a["grade"][0])}" '
          f'data-pri="{esc(pri_val(a["priority_band"]))}" data-rw="{1 if href else 0}" '
          f'style="background:#fff;border-radius:14px;box-shadow:0 1px 0 rgba(0,0,0,0.03),0 6px 18px rgba(0,0,0,0.05);padding:15px 18px;display:grid;grid-template-columns:30px 1fr auto;gap:16px;align-items:center">'
          f'<div style="font-family:var(--font-display);font-weight:700;font-size:17px;color:#C9C3B8;text-align:center">{a["rank"]}</div>'
          f'<div style="min-width:0">'
          f'<div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap">'
          f'<span style="background:{gc};color:#fff;padding:3px 9px;border-radius:7px;font-weight:700;font-size:12px;white-space:nowrap;font-family:var(--font-ui)">{esc(a["grade"])}</span>'
          f'<a href="{esc(a["url"])}" target="_blank" rel="noopener" style="font:500 15px var(--font-ui);color:#1B1B1B;text-decoration:none;letter-spacing:-.01em">{esc(a["title"])}</a>'
          f'<span style="{prist}">{esc(a["priority_band"])} priority</span>{votes}</div>'
          f'<div style="display:flex;gap:6px;flex-wrap:wrap;margin-top:9px;align-items:center">'
          f'{chips_html}{more_html}</div></div>'
          f'<div style="display:flex;align-items:center;gap:10px">'
          f'<span style="font:400 12px var(--font-body);color:#A8A29A;white-space:nowrap">{a["passes"]} / {a["applicable"]}</span>'
          f'{view}'
          f'<button class="optbtn" data-title="{esc(a["title"])}" data-url="{esc(a["url"])}" type="button" '
          f'style="font:500 12.5px var(--font-ui);color:#EA3609;background:#fff;border:1px solid #EA3609;border-radius:1000px;padding:7px 14px;cursor:pointer;white-space:nowrap">Optimize</button>'
          f'</div></div>')

    sig = sp.get("signals", {})
    hs_stats = (f'Average {sig.get("avg_words_per_article","?")} words/article &middot; '
                f'{sig.get("avg_sentence_words","?")}-word sentences &middot; {sig.get("heading_case","Sentence case")} headings.')
    descriptor = sp["descriptor"]

    SHARE = (f'{KB} scored {overall} ({r["overall_pct"]}%) for AI-readiness across {total} help-center articles. '
             f'Biggest gap: "{roll[weakest]["short"]}" ({weak_pct}% pass). Audit by My AskAI — myaskai.com')

    extra = """
.wrap{max-width:1180px;margin:0 auto}
.sec-pad{padding:0 32px}
.fsel{appearance:none;-webkit-appearance:none;-moz-appearance:none;min-width:150px;
background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 12 12'%3E%3Cpath d='M2.5 4.5l3.5 3.5 3.5-3.5' stroke='%231B1B1B' stroke-width='1.5' fill='none' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E");
background-repeat:no-repeat;background-position:right 15px center}
details.hsfold>summary{list-style:none}
details.hsfold>summary::-webkit-details-marker{display:none}
details.hsfold .chev{display:inline-block;transition:transform .15s;color:#868181}
details.hsfold[open] .chev{transform:rotate(90deg)}
@media (max-width:760px){.hero{grid-template-columns:1fr!important}.qgrid{grid-template-columns:1fr!important}}
"""
    house_style = f"""
  <div class="wrap sec-pad" style="padding-top:28px">
    <details class="hsfold" style="background:#fff;border-radius:16px;box-shadow:0 1px 0 rgba(0,0,0,0.04),0 8px 24px rgba(0,0,0,0.06);overflow:hidden">
      <summary style="cursor:pointer;display:flex;align-items:center;gap:10px;padding:18px 22px;font:500 20px var(--font-ui);letter-spacing:-.02em;color:#1B1B1B">
        <span class="chev">&#9656;</span>Your house style
        <span style="margin-left:auto;font:300 13px var(--font-body);color:#868181">click to edit &mdash; saved in this browser, feeds every Optimize</span>
      </summary>
      <div style="padding:0 22px 22px">
        <p style="font:300 13px var(--font-body);color:#868181;margin:0 0 12px">Derived from your own articles so rewrites keep your voice (style never affects the grade).</p>
        <textarea id="hs" rows="4" style="width:100%;font:400 14px/1.55 var(--font-body);color:#1B1B1B;background:#FBF8F3;border:1px solid rgba(0,0,0,0.12);border-left:3px solid #EA3609;border-radius:10px;padding:13px 15px;resize:vertical">{esc(descriptor)}</textarea>
        <div style="display:flex;align-items:center;gap:14px;margin-top:11px;flex-wrap:wrap">
          <button id="hsreset" type="button" style="font:500 12.5px var(--font-ui);color:#868181;background:#fff;border:1px solid rgba(0,0,0,0.14);border-radius:1000px;padding:7px 14px;cursor:pointer">Reset to derived</button>
          <span style="margin-left:auto;font:300 12.5px var(--font-body);color:#A8A29A">{hs_stats}</span>
        </div>
      </div>
    </details>
  </div>"""
    body = f"""
<div style="min-height:100vh;background:#FFFFFF;font-family:var(--font-body);color:#1B1B1B;padding-bottom:56px">
  <div class="wrap" style="padding:26px 32px 0;display:flex;align-items:center;gap:16px;flex-wrap:wrap">
    <a href="{home_url('logo')}" target="_blank" rel="noopener" title="Build your own AI support agent with My AskAI" style="display:inline-block;line-height:0">{WORDMARK % 26}</a>
    <span style="font:500 13px var(--font-ui);color:#868181;border-left:1px solid rgba(0,0,0,0.16);padding-left:14px;letter-spacing:.02em">Help center AI-readiness audit</span>
    <div style="margin-left:auto;display:flex;gap:10px;align-items:center">
      <a href="scorecard.html" target="_blank" style="font:500 13.5px var(--font-ui);text-decoration:none;color:#1B1B1B;background:#fff;border:1px solid rgba(0,0,0,0.14);border-radius:1000px;padding:9px 16px">Open scorecard</a>
      <button id="copysum" type="button" style="font:500 13.5px var(--font-ui);color:#1B1B1B;background:#fff;border:1px solid rgba(0,0,0,0.14);border-radius:1000px;padding:9px 16px;cursor:pointer">Copy score summary</button>
      <a href="{home_url('header-cta')}" target="_blank" rel="noopener" style="font:600 13.5px var(--font-ui);text-decoration:none;color:#FBF8F3;background:#EA3609;border-radius:1000px;padding:10px 17px">Create AI agent &rarr;</a>
    </div>
  </div>

  <div class="wrap hero" style="padding:26px 32px 6px;display:grid;grid-template-columns:300px 1fr;gap:34px;align-items:center">
    <div style="position:relative;background:#fff;border-radius:20px;box-shadow:0 1px 0 rgba(0,0,0,0.04),0 8px 24px rgba(0,0,0,0.06);padding:30px 24px;text-align:center;overflow:hidden">
      <img src="assets/logo-texture.png" alt="" aria-hidden="true" style="position:absolute;inset:0;width:100%;height:100%;object-fit:cover;opacity:.07;pointer-events:none">
      <div style="position:relative;font:500 12px var(--font-ui);color:#868181;text-transform:uppercase;letter-spacing:.14em">Help center grade</div>
      <div style="position:relative;font-family:var(--font-display);font-weight:700;font-size:138px;line-height:.86;letter-spacing:-.05em;color:{gcol};margin:10px 0 6px">{esc(overall)}</div>
      <div style="position:relative;font:500 15px var(--font-ui);color:#1B1B1B">{r["overall_pct"]}% of checks pass</div>
    </div>
    <div>
      <h1 style="font-family:var(--font-display);font-weight:700;font-size:44px;line-height:1.03;letter-spacing:-.04em;color:#1B1B1B;margin:0 0 14px;text-wrap:balance">{esc(headline)}</h1>
      <p style="font:300 17px/1.5 var(--font-body);color:#2F2F2F;max-width:640px;margin:0 0 18px">An AI support agent reads your help center one article at a time, with no memory between answers. It can't scroll past intro text, tap &ldquo;see also&rdquo;, read a screenshot, or tell which article is current. We graded every article on the 13 things that decide whether the AI can answer from it &mdash; then you choose which to rewrite, in your own voice.</p>
      <div style="display:flex;gap:10px;flex-wrap:wrap">{chips}</div>
    </div>
  </div>

  <div class="wrap sec-pad" style="padding-top:30px;padding-bottom:6px">
    <div style="display:flex;align-items:baseline;gap:12px;flex-wrap:wrap;margin-bottom:4px">
      <h2 style="font:500 24px var(--font-ui);letter-spacing:-.02em;color:#1B1B1B;margin:0">How your help center scores</h2>
      <span style="font:300 14px var(--font-body);color:#868181">The 13 checks roll up into three questions we ask of every article. Bars show the share that pass.</span>
    </div>
    <div class="qgrid" style="display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin-top:16px">{qcards}</div>
  </div>

  {house_style}

  <div class="wrap sec-pad" style="padding-top:28px">
    <div style="display:flex;align-items:baseline;gap:12px;flex-wrap:wrap;margin-bottom:2px">
      <h2 style="font:500 24px var(--font-ui);letter-spacing:-.02em;color:#1B1B1B;margin:0">Fix these first</h2>
      <span style="font:300 14px var(--font-body);color:#868181">Ranked by how many issues each article has. <b style="font-weight:600;color:#1B1B1B">View rewrite</b> opens a finished rewrite; <b style="font-weight:600;color:#1B1B1B">Optimize</b> hands the next one to Claude in your voice.</span>
    </div>
    <div style="display:flex;gap:12px;flex-wrap:wrap;align-items:center;margin:18px 0 6px">
      <input id="fq" type="search" placeholder="Search article titles&hellip;" style="flex:1;min-width:180px;font:400 13.5px var(--font-ui);color:#1B1B1B;background:#fff;border:1px solid rgba(0,0,0,0.14);border-radius:1000px;padding:9px 15px">
      <select id="fg" class="fsel" style="font:500 13px var(--font-ui);color:#1B1B1B;background-color:#fff;border:1px solid rgba(0,0,0,0.14);border-radius:1000px;padding:9px 38px 9px 16px;cursor:pointer"><option value="">All grades</option><option value="F">F only</option><option value="D">D only</option><option value="C">C only</option><option value="B">B only</option><option value="A">A only</option></select>
      <select id="fp" class="fsel" style="font:500 13px var(--font-ui);color:#1B1B1B;background-color:#fff;border:1px solid rgba(0,0,0,0.14);border-radius:1000px;padding:9px 38px 9px 16px;cursor:pointer"><option value="">All priorities</option><option value="veryhigh">Very high</option><option value="high">High</option><option value="medium">Medium</option><option value="low">Low</option><option value="verylow">Very low</option></select>
      <label style="display:inline-flex;align-items:center;gap:7px;font:400 13px var(--font-ui);color:#1B1B1B;background:#fff;border:1px solid rgba(0,0,0,0.14);border-radius:1000px;padding:8px 14px;cursor:pointer"><input id="frw" type="checkbox" style="accent-color:#EA3609">Rewritten only</label>
    </div>
    <div style="display:flex;align-items:center;gap:10px;margin:8px 0 14px">
      <span style="font:300 13px var(--font-body);color:#868181">Sorted by urgency &mdash; the most pressing articles first.</span>
      <span id="fcount" style="margin-left:auto;font:500 12.5px var(--font-ui);color:#868181;font-variant-numeric:tabular-nums"></span>
    </div>
    <div id="plist" style="display:flex;flex-direction:column;gap:10px">{rows}</div>
    <div id="pempty" style="display:none;background:#fff;border-radius:14px;padding:34px;text-align:center;font:300 14px var(--font-body);color:#868181">No articles match those filters.</div>
    <div style="text-align:center;margin-top:16px"><button id="showmore" type="button" style="display:none;font:500 13.5px var(--font-ui);color:#1B1B1B;background:#fff;border:1px solid rgba(0,0,0,0.16);border-radius:1000px;padding:10px 20px;cursor:pointer"></button></div>
  </div>

  {build_coherence_section()}

  <div class="wrap sec-pad" style="padding-top:30px">
    <div style="font:300 12.5px var(--font-body);color:#868181">Every fix works with any AI agent or helpdesk. Keeping a help center AI-ready over time is what <a href="{home_url('footer')}" target="_blank" rel="noopener" style="color:#EA3609">My AskAI</a> does automatically.</div>
  </div>

  <div id="toast" style="position:fixed;left:50%;bottom:26px;transform:translateX(-50%) translateY(20px);background:#1B1B1B;color:#FBF8F3;font:500 13px var(--font-ui);padding:12px 18px;border-radius:1000px;box-shadow:0 8px 28px rgba(0,0,0,0.24);z-index:50;opacity:0;pointer-events:none;transition:opacity .2s,transform .2s"></div>
</div>
<script>
(function(){{
  var KB={json.dumps(KB)}, DEFAULT_HS={json.dumps(descriptor)}, SHARE={json.dumps(SHARE)};
  var rows=[].slice.call(document.querySelectorAll('.prow'));
  var fq=document.getElementById('fq'),fg=document.getElementById('fg'),fp=document.getElementById('fp'),frw=document.getElementById('frw');
  var cnt=document.getElementById('fcount'),empty=document.getElementById('pempty'),more=document.getElementById('showmore');
  var LIMIT=5,expanded=false;
  function apply(){{
    var q=(fq.value||'').trim().toLowerCase(),g=fg.value,p=fp.value,rw=frw.checked,matched=0,shown=0;
    rows.forEach(function(el){{
      var ok=true;
      if(q&&el.dataset.title.indexOf(q)<0)ok=false;
      if(g&&el.dataset.grade!==g)ok=false;
      if(p&&el.dataset.pri!==p)ok=false;
      if(rw&&el.dataset.rw!=='1')ok=false;
      if(ok){{matched++; if(expanded||matched<=LIMIT){{el.style.display='grid';shown++;}}else el.style.display='none';}}
      else el.style.display='none';
    }});
    cnt.textContent=shown+' of '+rows.length+' articles';
    empty.style.display=matched?'none':'';
    if(matched>LIMIT){{more.style.display='';more.textContent=expanded?'Show fewer':('Show all '+matched+' articles \\u2193');}}
    else more.style.display='none';
  }}
  more.addEventListener('click',function(){{expanded=!expanded;apply();if(!expanded)document.getElementById('plist').scrollIntoView({{behavior:'smooth',block:'start'}});}});
  [fq,fg,fp,frw].forEach(function(e){{e.addEventListener('input',function(){{expanded=false;apply();}});e.addEventListener('change',function(){{expanded=false;apply();}});}});
  apply();
  // resolve / merge buttons in the coherence section
  function rprompt(b){{
    var d=b.dataset;
    if(d.kind==='merge') return 'Using the kb-ai-audit skill, two '+KB+' help articles overlap and compete for the same customer question \\u2014 merge them into ONE canonical article: "'+d.a+'" ('+d.aurl+') and "'+d.b+'" ('+d.burl+'). Keep every unique fact from both, use ONLY facts present in the source articles (never invent \\u2014 flag any gap with [VERIFY]), point the weaker URL at the canonical one, add the merged article to rewrites.json, then regenerate the dashboard and per-article pages. Match this house style exactly: '+hs.value;
    return 'Using the kb-ai-audit skill, two '+KB+' help articles disagree about "'+d.subject+'": "'+d.a+'" ('+d.aurl+') says '+d.aval+', "'+d.b+'" ('+d.burl+') says '+d.bval+'. Work out the correct, current value from the sources (if it cannot be determined, flag [VERIFY] \\u2014 never guess), update BOTH articles so they agree, add the corrected articles to rewrites.json, then regenerate the dashboard and per-article pages. Match this house style exactly: '+hs.value;
  }}
  document.querySelectorAll('.resolvebtn').forEach(function(b){{
    b.addEventListener('click',function(){{
      var p=rprompt(b);
      if(typeof window.sendPrompt==='function'){{try{{window.sendPrompt(p);toast('Sent to Claude \\u2014 resolving this.');return;}}catch(e){{}}}}
      copy(p,'Instruction copied \\u2014 paste it into Claude to resolve this.');
    }});
  }});
  // toast
  var t=document.getElementById('toast'),th;
  function toast(m){{t.textContent=m;t.style.opacity='1';t.style.transform='translateX(-50%) translateY(0)';clearTimeout(th);th=setTimeout(function(){{t.style.opacity='0';t.style.transform='translateX(-50%) translateY(20px)';}},2600);}}
  function copy(text,msg){{ if(navigator.clipboard&&navigator.clipboard.writeText){{navigator.clipboard.writeText(text).then(function(){{toast(msg);}},function(){{toast(msg);}});}}else{{var ta=document.createElement('textarea');ta.value=text;ta.style.position='fixed';ta.style.opacity='0';document.body.appendChild(ta);ta.select();try{{document.execCommand('copy');}}catch(e){{}}document.body.removeChild(ta);toast(msg);}} }}
  document.getElementById('copysum').addEventListener('click',function(){{copy(SHARE,'Score summary copied — share it anywhere.');}});
  // house style
  var hs=document.getElementById('hs');
  try{{var v=localStorage.getItem('kbaudit_hs_'+KB);if(v!=null)hs.value=v;}}catch(e){{}}
  hs.addEventListener('input',function(){{try{{localStorage.setItem('kbaudit_hs_'+KB,hs.value);}}catch(e){{}}}});
  document.getElementById('hsreset').addEventListener('click',function(){{hs.value=DEFAULT_HS;try{{localStorage.removeItem('kbaudit_hs_'+KB);}}catch(e){{}}toast('House style reset to derived.');}});
  // optimize
  function buildPrompt(title,url){{
    return 'Using the kb-ai-audit skill, optimize the '+KB+' help center article "'+title+'" ('+url+') for AI-agent readiness: '
      +'produce the complete, paste-ready rewrite, split it if it covers more than one question, carry over its original images and videos, '
      +'use ONLY facts present in the source article (never invent specs, steps, numbers, button names, URLs or policies — flag any gap with [VERIFY] instead of guessing), '
      +'add it (and any splits) to rewrites.json, then regenerate the dashboard and per-article pages. Match this house style exactly: '+hs.value;
  }}
  document.querySelectorAll('.optbtn').forEach(function(b){{
    b.addEventListener('click',function(){{
      var p=buildPrompt(b.dataset.title,b.dataset.url);
      if(typeof window.sendPrompt==='function'){{try{{window.sendPrompt(p);toast('Sent to Claude — generating this rewrite.');return;}}catch(e){{}}}}
      copy(p,'Instruction copied — paste it into Claude to generate this rewrite.');
    }});
  }});
}})();
</script>
"""
    _desc = f"{KB} scored {overall} ({r['overall_pct']}%) for AI-readiness across {total} help-center articles. See which articles an AI support agent can't answer from — and the rewrites that fix them."
    (OUT / "dashboard.html").write_text(page(f"{KB} — AI-readiness audit", extra, body, head_extra=social_head(f"{KB} — AI-readiness audit", _desc)))

# ----------------------------------------------------------------- SCORECARD
def build_scorecard():
    r = RES; roll = r["pattern_rollup"]; order = r["order"]
    overall = r["overall_grade"]; total = r["article_count"]
    needfix = sum(1 for a in r["results"] if a["fixes"] > 0)
    gbg = grade_color(overall)
    gaps = sorted(order, key=lambda k: roll[k]["pass_pct"])[:3]
    gap_html = ""
    for k in gaps:
        pct = roll[k]["pass_pct"]
        gap_html += (f'<div style="display:grid;grid-template-columns:210px 1fr 48px;align-items:center;gap:14px">'
                     f'<span style="font:400 14.5px var(--font-body);color:#1B1B1B">{esc(roll[k]["short"])}</span>'
                     f'<span style="height:9px;background:#F1F1F1;border-radius:5px;overflow:hidden;display:block">'
                     f'<span style="display:block;height:100%;width:{pct}%;background:{bar_color(pct)};border-radius:5px"></span></span>'
                     f'<span style="text-align:right;font:600 14.5px var(--font-ui);color:#1B1B1B;font-variant-numeric:tabular-nums">{pct}%</span></div>')
    date = r["generated"][:10]
    body = f"""
<div style="min-height:100vh;background:#FFFFFF;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:16px;padding:24px;font-family:var(--font-body)">
  <div style="width:1200px;max-width:100%;aspect-ratio:1200/630;background:#FBF8F3;border-radius:24px;box-shadow:0 24px 70px rgba(0,0,0,0.16);padding:52px 58px;display:flex;flex-direction:column;overflow:hidden;position:relative">
    <img src="assets/logo-texture.png" alt="" aria-hidden="true" style="position:absolute;right:-80px;top:-90px;width:420px;height:420px;object-fit:cover;opacity:.06;pointer-events:none">
    <div style="display:flex;align-items:center;gap:14px;position:relative">
      {WORDMARK % 30}
      <span style="margin-left:auto;font:600 14px var(--font-ui);color:#868181;text-transform:uppercase;letter-spacing:.14em">Help center AI-readiness</span>
    </div>
    <div style="flex:1;display:flex;align-items:center;gap:46px;margin-top:6px;position:relative">
      <div style="flex:none;width:282px;height:282px;border-radius:28px;background:{gbg};display:flex;flex-direction:column;align-items:center;justify-content:center;position:relative;overflow:hidden;box-shadow:0 14px 36px rgba(234,54,9,0.28)">
        <img src="assets/logo-texture.png" alt="" aria-hidden="true" style="position:absolute;inset:0;width:100%;height:100%;object-fit:cover;opacity:.16;mix-blend-mode:multiply;pointer-events:none">
        <div style="position:relative;font-family:var(--font-display);font-weight:700;font-size:158px;line-height:.84;letter-spacing:-.05em;color:#FBF8F3">{esc(overall)}</div>
        <div style="position:relative;font:600 14px var(--font-ui);color:#FBF8F3;text-transform:uppercase;letter-spacing:.14em;margin-top:6px;opacity:.9">Overall grade</div>
      </div>
      <div style="flex:1;min-width:0">
        <div style="font-family:var(--font-display);font-weight:700;font-size:52px;line-height:1;letter-spacing:-.04em;color:#1B1B1B;margin-bottom:6px">{esc(KB)}</div>
        <div style="font:300 19px/1.35 var(--font-body);color:#2F2F2F;margin-bottom:22px">How ready this help center is for an AI support agent to answer from.</div>
        <div style="display:flex;gap:34px;margin-bottom:24px">
          <div><div style="font-family:var(--font-display);font-weight:700;font-size:34px;color:#EA3609;letter-spacing:-.03em">{r["overall_pct"]}%</div><div style="font:300 13.5px var(--font-body);color:#868181">of checks pass</div></div>
          <div><div style="font-family:var(--font-display);font-weight:700;font-size:34px;color:#1B1B1B;letter-spacing:-.03em">{total}</div><div style="font:300 13.5px var(--font-body);color:#868181">articles audited</div></div>
          <div><div style="font-family:var(--font-display);font-weight:700;font-size:34px;color:#1B1B1B;letter-spacing:-.03em">{needfix}</div><div style="font:300 13.5px var(--font-body);color:#868181">worth fixing</div></div>
        </div>
        <div style="font:600 12.5px var(--font-ui);color:#868181;text-transform:uppercase;letter-spacing:.1em;margin-bottom:11px">Biggest gaps</div>
        <div style="display:flex;flex-direction:column;gap:9px">{gap_html}</div>
      </div>
    </div>
    <div style="display:flex;align-items:center;margin-top:auto;padding-top:18px;border-top:1px solid rgba(0,0,0,0.1);font:300 14px var(--font-body);color:#868181;position:relative">
      <span><b style="font-weight:600;color:#1B1B1B">{esc(date)}</b> &middot; 13-check AI-readiness audit</span>
      <span style="margin-left:auto;font:600 14px var(--font-ui);color:#EA3609">Run your free audit &rarr; myaskai.com</span>
    </div>
  </div>
  <div style="font:300 13px var(--font-body);color:#8a857c">Screenshot this card to share your score &middot; <a href="{home_url('scorecard-cta', medium='scorecard')}" target="_blank" rel="noopener" style="color:#EA3609;font-weight:500">run your own free audit &rarr;</a></div>
</div>
"""
    _desc = f"{KB} scored {overall} ({r['overall_pct']}%) for AI-readiness across {total} help-center articles — a 13-check audit of whether an AI support agent can answer from them."
    (OUT / "scorecard.html").write_text(page(f"{KB} — AI-readiness score", "", body, head_extra=social_head(f"{KB} — AI-readiness score", _desc)))

# ----------------------------------------------------------------- PDF REPORT (audit only, no rewrites)
REPORT_HEAD = '<link href="https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&display=swap" rel="stylesheet">'
REPORT_CSS = """
@page{size:A4;margin:14mm}
:root{--cream:#FAF9F1;--ink:#1B1B1B;--ink2:#3A3A3A;--muted:#868181;--red:#EA3609;--green:#2F7D57;
--line:rgba(0,0,0,0.08);--serif:'Instrument Serif',Georgia,'Times New Roman',serif}
/* @page margin:0 lets the cream bleed to the physical page edge; the consistent inner border
   comes from .section padding, cloned onto every page fragment via box-decoration-break */
@page{size:A4;margin:0}
html,body{background:var(--cream)}
body{-webkit-print-color-adjust:exact;print-color-adjust:exact;color:var(--ink);background:var(--cream)}
.doc{margin:0}
.section{position:relative;page-break-before:always;break-before:page;padding:14mm;
-webkit-box-decoration-break:clone;box-decoration-break:clone}
.section.first{page-break-before:auto;break-before:auto}
/* the cover fills its page; overflow:hidden keeps decorations inside the sheet (cover only) */
.cover{overflow:hidden;min-height:289mm;display:flex;flex-direction:column}
.avoid{break-inside:avoid;page-break-inside:avoid}
a{color:inherit;text-decoration:none}
/* inline-block so the pill hugs its text; align-self stops it stretching inside the flex cover */
.kick{display:inline-block;align-self:flex-start;font:600 10.5px var(--font-ui);letter-spacing:.13em;text-transform:uppercase;
color:var(--red);border:1px solid var(--red);border-radius:1000px;padding:5px 13px}
h2.sec{font:500 24px var(--font-ui);letter-spacing:-.02em;color:var(--ink);margin:13px 0 3px}
.sechint{font:300 13px/1.5 var(--font-body);color:var(--muted);margin:0 0 18px;max-width:600px}
.serif{font-family:var(--serif);font-style:italic;font-weight:400;letter-spacing:0}
.rcard{background:#fff;border:1px solid var(--line);border-radius:18px;
box-shadow:0 1px 0 rgba(0,0,0,0.03),0 12px 32px rgba(0,0,0,0.06)}
/* speech-bubble decoration (the My AskAI mark), scaled via inline width/height/opacity */
.bub{position:absolute;background:var(--red);border-radius:30% 30% 30% 7%;pointer-events:none}
.bub:after{content:"";position:absolute;left:16%;bottom:-11%;width:30%;height:30%;background:var(--red);
clip-path:polygon(0 0,100% 0,0 100%)}
/* check / cross list */
.clist{list-style:none;margin:0;padding:0}
.clist li{display:flex;gap:11px;align-items:flex-start;font:300 13.5px/1.5 var(--font-body);color:var(--ink2);margin:10px 0}
.clist .ic{flex:none;width:21px;height:21px;border-radius:50%;display:flex;align-items:center;justify-content:center;
font-size:12px;font-weight:700;margin-top:1px;line-height:1}
.ic.x{background:#FFD9D9;color:var(--red)}.ic.ok{background:#DDEEE4;color:var(--green)}
/* dark CTA */
.cta{background:var(--ink);border-radius:22px;padding:32px 34px;color:#FBF8F3;position:relative;overflow:hidden}
.cta .btn{display:inline-block;background:var(--red);color:#fff;font:600 14px var(--font-ui);
border-radius:1000px;padding:12px 22px;margin-top:16px}
.pfoot{display:flex;align-items:center;gap:10px;font:300 11px var(--font-body);color:var(--muted);
border-top:1px solid var(--line);padding-top:12px;margin-top:20px}
"""

def build_report_coherence():
    """Static (no-button) print version of the coherence section for the PDF report."""
    c = RES.get("corpus")
    if not c:
        return ""
    OK = f'<div style="{OKLINE}">&#10003; None found — nice.</div>'
    # keep each coherence card compact so it stays a clean, self-contained card on one page
    def more_note(extra, noun):
        return (f'<div style="font:400 12px var(--font-body);color:#A8A29A;padding-top:10px">+ {extra} more {noun} &mdash; full set in <b style="font-weight:600;color:#868181">audit_tracker.xlsx</b>.</div>'
                if extra > 0 else "")
    panels = []

    cov = c["coverage"]
    if cov["status"] == "locked":
        inner = (f'<div style="background:#FBF8F3;border:1px dashed #EA3609;border-radius:12px;padding:14px 16px;color:#1B1B1B;font:300 13.5px/1.55 var(--font-body)">'
                 f'<b style="font-weight:600">Locked.</b> {esc(cov["hint"])} Add a ticket export to reveal the questions '
                 f'customers ask that have no article — usually the single biggest win.</div>')
    elif cov["status"] == "ok" and cov.get("gaps"):
        mxv = max(g["volume"] for g in cov["gaps"]); rows = ""
        for g in cov["gaps"]:
            eg = " &middot; ".join('&ldquo;'+esc(e)+'&rdquo;' for e in g["examples"])
            rows += (f'<div style="{ITEM};display:flex;gap:14px;align-items:baseline">'
                     f'<span style="flex:none;width:74px;font:600 13px var(--font-ui);color:#EA3609;font-variant-numeric:tabular-nums">{g["volume"]} tickets</span>'
                     f'<span style="flex:1;min-width:0">no article on <b style="font-weight:600;color:#1B1B1B">{esc(", ".join(g["terms"]))}</b>'
                     f'<div style="font:300 12.5px var(--font-body);color:#A8A29A;margin-top:3px">e.g. {eg}</div></span></div>')
        inner = f'<div style="font:500 14px var(--font-ui);color:#1B1B1B;margin-bottom:4px">{cov["covered_pct"]}% of ticket topics are covered by an article <span style="font-weight:300;color:#868181">({cov["tickets"]} tickets read)</span></div>{rows}'
    else:
        inner = f'<div style="{OKLINE}">&#10003; Every ticket topic maps to an article ({cov.get("tickets",0)} tickets read).</div>'
    panels.append((coh_panel("Questions with no article", "The most common reason an AI can't resolve is that no article exists for the question. Drawn from your ticket export.", inner), "full"))

    con = c["contradictions"]
    if con:
        rows = ""
        for f in con[:8]:
            pre = "$" if f["unit"] == "money" else ""; post = "%" if f["unit"] == "percent" else ("" if f["unit"] in ("money", "percent") else " "+f["unit"]+"s")
            rows += (f'<div style="{ITEM}"><span style="color:#EA3609;font-weight:600">&#9888; {esc(f["subject"])}</span> &mdash; '
                     f'<b style="font-weight:600;color:#1B1B1B">{pre}{esc(f["a_val"])}{post}</b> in &ldquo;{esc(f["a"])}&rdquo; '
                     f'vs <b style="font-weight:600;color:#1B1B1B">{pre}{esc(f["b_val"])}{post}</b> in &ldquo;{esc(f["b"])}&rdquo;</div>')
        inner = rows + more_note(len(con) - 8, "pair(s)")
    else:
        inner = OK
    panels.append((coh_panel("Articles that disagree", "The AI answers from one article at a time — if two state different facts, it gives whichever it lands on.", inner), "full"))

    col = c["collisions"]
    if col:
        rows = ""
        for p in col[:8]:
            rows += (f'<div style="{ITEM}">&ldquo;{esc(p["a"])}&rdquo; &nbsp;&#8644;&nbsp; &ldquo;{esc(p["b"])}&rdquo;'
                     f'<div style="font:300 12.5px var(--font-body);color:#A8A29A;margin-top:3px">{round(p["similarity"]*100)}% overlap &middot; shared: {esc(", ".join(p["shared"][:4]))}</div></div>')
        inner = rows + more_note(len(col) - 8, "pair(s)")
    else:
        inner = OK
    panels.append((coh_panel("Articles competing for the same question", "Near-identical articles split the AI's pick — it may surface the weaker one. Merge each into one canonical answer.", inner), "full"))

    dt = c["dates"]; stale = dt["stale_dated"]
    sub = ("When each article was last updated." if dt["mode"] == "age"
           else "No article carries a last-updated date, so this shows the most recent date each one <em>mentions</em> — a proxy for how current it is.")
    bits = []
    if dt.get("no_freshness_signal"):
        bits.append(f'<span style="color:#EA3609;font-weight:600">{dt["no_freshness_signal"]} of {dt["total"]} articles</span> carry no last-updated date, so the AI can\'t tell what\'s current')
    if dt["stale_count"]:
        bits.append(f'<span style="color:#EA3609;font-weight:600">{dt["stale_count"]}</span> quote a past-dated, time-sensitive detail it may present as live')
    stat = '<div style="font:400 13.5px/1.6 var(--font-body);color:#2F2F2F;margin-top:6px">' + "; ".join(bits) + ".</div>" if bits else f'<div style="{OKLINE}">&#10003; Freshness looks healthy.</div>'
    slist = ""
    if stale:
        slist = '<div style="font:300 12.5px/1.6 var(--font-body);color:#A8A29A;margin-top:8px">' + " &middot; ".join(f'&ldquo;{esc(s["title"])}&rdquo; ({esc(s["detail"])})' for s in stale[:6]) + ('…' if len(stale) > 6 else '') + '</div>'
    panels.append((coh_panel("How fresh is the help center?", sub, coh_svg(dt) + stat + slist), "full"))

    dis = c["disambiguation"]
    if dis:
        rows = ""
        for f in dis[:6]:
            links = ", ".join(esc(a["title"]) for a in f["articles"])
            rows += (f'<div style="{ITEM}"><b style="font-weight:600;color:#1B1B1B">{esc(" / ".join(f["names"]))}</b>'
                     f'<span style="font:300 12.5px var(--font-body);color:#A8A29A"> &mdash; used together without saying which is which in {f["count"]} article(s):</span>'
                     f'<div style="font:400 12.5px/1.7 var(--font-body);color:#2F2F2F;margin-top:4px">{links}</div></div>')
        inner = rows + more_note(len(dis) - 6, "name set(s)")
    else:
        inner = OK
    panels.append((coh_panel("Easily-confused names", "Similar product/plan/version names the KB never tells apart, so the AI conflates them (e.g. v1 vs v2).", inner), "full"))

    # pack panels into a 2-column flex grid (full-width panels span the row) so the cards sit
    # tightly together instead of leaving big gaps when a stacked card won't fit the page
    def wrap(html_, w):
        basis = "100%" if w == "full" else "calc(50% - 7px)"
        return f'<div class="avoid" style="flex:1 1 {basis};max-width:{basis};min-width:0">{html_}</div>'
    items = "".join(wrap(p, w) for p, w in panels)
    return f'<div style="display:flex;flex-wrap:wrap;gap:14px;align-items:flex-start">{items}</div>'

def _bub(w, h, css, op):
    """A decorative My AskAI speech-bubble, positioned via the css string (top/left/etc)."""
    return f'<span class="bub" style="width:{w}px;height:{h}px;opacity:{op};{css}"></span>'

def build_report():
    """A branded, print-optimized, audit-only PDF report (no rewrites) — designed as a lead magnet
    around the myaskai.com look (cream canvas, speech-bubble motif, kicker pills, serif-italic
    accents, dark CTA). One source of truth: reuses the dashboard brand system. PDF via html_to_pdf.py."""
    r = RES; results = r["results"]; roll = r["pattern_rollup"]; order = r["order"]
    total = r["article_count"]; needfix = sum(1 for a in results if a["fixes"] > 0); clean = total - needfix
    overall = r["overall_grade"]; gcol = grade_color(overall)
    weakest = min(order, key=lambda k: roll[k]["pass_pct"]); weak_pct = roll[weakest]["pass_pct"]; weak_short = roll[weakest]["short"]
    sp = r["style_profile"]; date = r["generated"][:10]
    wordmark = _data_uri(os.path.join(_asrc, "wordmark.png"))  # small; inlined so the PDF needs no assets/ folder
    headline = (f"Every one of your {total} articles has something worth fixing before an AI agent can answer from it."
                if needfix == total else
                f"{needfix} of your {total} articles have something worth fixing before an AI agent can answer from them.")

    def kbig(num, col, label):  # big stat, used in the cover grade band
        return (f'<div><div style="font-family:var(--font-display);font-weight:700;font-size:32px;letter-spacing:-.03em;color:{col};line-height:1">{num}</div>'
                f'<div style="font:300 12px var(--font-body);color:var(--muted);margin-top:3px">{label}</div></div>')

    # ---- COVER (full page, magazine-style) ----
    cover = f"""
  {_bub(150, 128, "top:-26px;right:-22px;", ".12")}
  {_bub(74, 64, "top:118px;right:120px;", ".10")}
  {_bub(230, 196, "bottom:-66px;left:-58px;", ".05")}
  <div style="display:flex;align-items:center;gap:13px;position:relative">
    <img src="{wordmark}" alt="My AskAI" style="height:30px;display:block">
    <span style="margin-left:auto;font:300 12px var(--font-body);color:var(--muted)">Prepared {esc(date)}</span>
  </div>
  <div style="flex:1;display:flex;flex-direction:column;justify-content:center;position:relative;padding:8px 0">
    <span class="kick">Help center AI-readiness audit</span>
    <h1 style="font-family:var(--font-display);font-weight:700;font-size:54px;line-height:1.0;letter-spacing:-.04em;color:var(--ink);margin:20px 0 0;max-width:15ch;text-wrap:balance">
      Is <span class="serif" style="color:var(--red)">{esc(KB)}</span> ready for an AI support agent?</h1>
    <p style="font:300 16px/1.55 var(--font-body);color:var(--ink2);margin:18px 0 0;max-width:54ch">
      We pulled all {total} of your help-center articles and graded every one against the 13 things that decide
      whether an AI agent can actually answer from it &mdash; plus what only shows up <span class="serif">across</span> the whole help center.</p>
    <div class="rcard avoid" style="margin-top:30px;padding:24px 26px;display:grid;grid-template-columns:auto 1px 1fr;gap:28px;align-items:center">
      <div style="text-align:center">
        <div style="font:600 10.5px var(--font-ui);color:var(--muted);text-transform:uppercase;letter-spacing:.14em">Overall grade</div>
        <div style="font-family:var(--font-display);font-weight:700;font-size:104px;line-height:.84;letter-spacing:-.05em;color:{gcol};margin:6px 0 0">{esc(overall)}</div>
      </div>
      <div style="background:var(--line);align-self:stretch"></div>
      <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:18px">
        {kbig(f'{r["overall_pct"]}%', "var(--red)", "of checks pass")}
        {kbig(total, "var(--ink)", "articles graded")}
        {kbig(needfix, "var(--red)", "worth fixing")}
      </div>
    </div>
  </div>
  <div class="pfoot" style="position:relative">
    <span>13-check AI-readiness audit + help-center-wide coherence layer</span>
    <span style="margin-left:auto;font-weight:600;color:var(--red)">myaskai.com</span>
  </div>"""

    # ---- "The headline" page: explainer + what an AI agent can't do ----
    cant = [
        "Scroll past a long intro to reach the actual answer",
        "Click &ldquo;see also&rdquo; or follow a link to another article",
        "Read a screenshot, diagram or video with no words around it",
        "Tell which article is current when two of them disagree",
        "Remember the last answer &mdash; every reply starts cold",
    ]
    cant_li = "".join(f'<li><span class="ic x">&#10005;</span><span>{c}</span></li>' for c in cant)
    headline_sec = f"""
    <span class="kick">The headline</span>
    <h2 class="sec" style="font-size:27px;max-width:20ch">{esc(headline)}</h2>
    <p class="sechint" style="font-size:14px;max-width:62ch">A human reader scrolls, skims and clicks around. An AI agent can't &mdash; it answers from
      <span class="serif" style="font-size:15px">one article at a time</span>, so every article has to stand on its own. Here's what it can't do for you:</p>
    <div class="rcard avoid" style="padding:22px 26px;display:grid;grid-template-columns:1fr 1fr;gap:8px 34px">
      <div style="grid-column:1/-1;font:600 12px var(--font-ui);color:var(--ink);text-transform:uppercase;letter-spacing:.1em;margin-bottom:4px">What an AI support agent can't do</div>
      <ul class="clist">{cant_li}</ul>
      <div style="align-self:center">
        <div style="font:400 14px/1.6 var(--font-body);color:var(--ink2)">That's why the weakest area to fix first is
          <b style="font-weight:600;color:var(--ink)">&ldquo;{esc(weak_short)}&rdquo;</b> &mdash; only
          <b style="font-weight:600;color:var(--red)">{weak_pct}%</b> of articles pass it today.</div>
        <div style="margin-top:12px;font:300 13px/1.55 var(--font-body);color:var(--muted)">Fix the structure and your human readers win too &mdash; the AI just makes it non-negotiable.</div>
      </div>
    </div>"""

    # ---- by-question scores ----
    qcards = ""
    for g in r["groups"]:
        bars = ""
        for k in [k for k in order if roll[k]["group"] == g]:
            pct = roll[k]["pass_pct"]
            bars += (f'<div style="display:grid;grid-template-columns:215px 1fr 44px;align-items:center;gap:12px;margin:9px 0">'
                     f'<span style="font:400 12.5px var(--font-body);color:var(--ink)">{esc(roll[k]["short"])}</span>'
                     f'<span style="height:8px;background:#EDEAE0;border-radius:4px;overflow:hidden;display:block"><span style="display:block;height:100%;width:{pct}%;background:{bar_color(pct)};border-radius:4px"></span></span>'
                     f'<span style="text-align:right;font:600 13px var(--font-ui);color:var(--ink);font-variant-numeric:tabular-nums">{pct}%</span></div>')
        qcards += (f'<div class="rcard avoid" style="padding:20px 24px;margin-bottom:14px">'
                   f'<div style="font:500 16px var(--font-ui);color:var(--red);letter-spacing:-.01em;margin-bottom:2px">{esc(g)}</div>'
                   f'<div style="font:300 12.5px var(--font-body);color:var(--muted);margin-bottom:10px">{esc(GROUP_BLURB.get(g,""))}</div>'
                   f'{bars}</div>')

    # ---- fix these first (top N) ----
    CAP = 12  # a tight, magazine-style list; the exhaustive grid lives in audit_tracker.xlsx
    to_fix = [a for a in results if a["fixes"] > 0]
    shown = to_fix[:CAP]; remainder = len(to_fix) - len(shown)
    rows = ""
    for a in shown:
        fails = [k for k in order if a["checks"][k]["verdict"] == "Fix"]
        chips_html = ""
        for k in fails[:6]:
            chips_html += (f'<span style="font:500 11px var(--font-ui);color:var(--red);background:#FFD9D9;border-radius:1000px;padding:3px 9px;margin:0 4px 4px 0;display:inline-block">{esc(roll[k]["short"])}</span>')
        more = len(fails) - 6
        if more > 0:
            chips_html += f'<span style="font:400 11px var(--font-body);color:var(--muted);white-space:nowrap">+{more} more</span>'
        gc = grade_color(a["grade"]); hot = a["priority_band"] in ("Very high", "High")
        prist = f'color:{"#EA3609" if hot else "#A8A29A"};font-weight:{600 if hot else 400};font-size:12px'
        rows += (
          f'<div class="rcard avoid" style="padding:13px 16px;margin-bottom:9px;display:grid;grid-template-columns:26px 1fr auto;gap:14px;align-items:start">'
          f'<div style="font-family:var(--font-display);font-weight:700;font-size:16px;color:#C9C3B8;text-align:center;padding-top:1px">{a["rank"]}</div>'
          f'<div style="min-width:0">'
          f'<div style="display:flex;align-items:center;gap:9px;flex-wrap:wrap">'
          f'<span style="background:{gc};color:#fff;padding:2px 8px;border-radius:6px;font-weight:700;font-size:11.5px;font-family:var(--font-ui)">{esc(a["grade"])}</span>'
          f'<a href="{esc(a["url"])}" style="font:500 14px var(--font-ui);color:var(--ink);letter-spacing:-.01em">{esc(a["title"])}</a>'
          f'<span style="{prist}">{esc(a["priority_band"])} priority</span></div>'
          f'<div style="margin-top:8px">{chips_html}</div></div>'
          f'<div style="font:400 12px var(--font-body);color:var(--muted);white-space:nowrap;padding-top:2px">{a["passes"]} / {a["applicable"]}</div>'
          f'</div>')
    remainder_note = (f'<div style="font:400 12.5px var(--font-body);color:var(--muted);margin-top:8px">+ {remainder} more article(s) worth fixing &mdash; the complete ranked grid is in <b style="font-weight:600;color:var(--ink)">audit_tracker.xlsx</b>.</div>' if remainder > 0 else "")

    # ---- house style ----
    hs_stats = (f'Average {sp.get("avg_words_per_article","?")} words/article &middot; '
                f'{sp.get("avg_sentence_words","?")}-word sentences &middot; {sp.get("heading_case","Sentence case")} headings.')
    house = (f'<div class="rcard avoid" style="padding:22px 26px">'
             f'<div style="font:400 16px/1.6 var(--serif);font-style:italic;color:var(--ink);background:var(--cream);border-left:3px solid var(--red);border-radius:10px;padding:16px 18px">{esc(sp["descriptor"])}</div>'
             f'<div style="font:300 12.5px var(--font-body);color:var(--muted);margin-top:12px">{hs_stats}</div></div>')

    # ---- CTA outro (dark, like the site) ----
    cta = f"""
    <div class="cta avoid">
      {_bub(150, 128, "top:-34px;right:-20px;", ".22")}
      {_bub(70, 60, "bottom:-18px;right:120px;", ".16")}
      <span class="kick" style="color:#fff;border-color:rgba(255,255,255,.45)">Keep it AI-ready</span>
      <div style="font-family:var(--font-display);font-weight:700;font-size:30px;line-height:1.05;letter-spacing:-.02em;margin:16px 0 8px;max-width:18ch;position:relative">
        Fix it once &mdash; then keep it that way, <span class="serif" style="color:var(--red);font-size:34px">automatically</span>.</div>
      <p style="font:300 14px/1.6 var(--font-body);color:rgba(251,248,243,.82);max-width:56ch;margin:0;position:relative">
        My AskAI turns your help center into an AI support agent that resolves tickets &mdash; and learns automatically
        from your human agent replies to continuously improve responses. Every fix in this report works with any AI agent or helpdesk.</p>
      <a class="btn" href="https://myaskai.com">Create your AI agent &rarr;</a>
      <span style="margin-left:14px;font:600 13px var(--font-ui);color:rgba(251,248,243,.7);position:relative">myaskai.com</span>
    </div>
    <div class="pfoot">
      <span>Built by <a href="https://myaskai.com" style="color:var(--red);font-weight:600">My AskAI</a> &middot; this report is the diagnostic; rewrites are delivered separately.</span>
      <span style="margin-left:auto">{esc(KB)} &middot; {esc(date)}</span>
    </div>"""

    inner = f"""
<div class="doc">
  <div class="section first cover">{cover}</div>
  <div class="section">{headline_sec}</div>
  <div class="section">
    <span class="kick">The scores</span>
    <h2 class="sec">How your help center scores</h2>
    <p class="sechint">The 13 checks roll up into three questions we ask of every article. Bars show the share that pass.</p>
    {qcards}
  </div>
  <div class="section">
    <span class="kick">Fix first</span>
    <h2 class="sec">Fix these first</h2>
    <p class="sechint">{needfix} article(s) worth fixing, ranked by how many issues each has &mdash; {clean} are already clean.{(" Showing the top "+str(len(shown))+".") if remainder > 0 else ""}</p>
    {rows or '<div style="'+OKLINE+'">&#10003; Every article passes its applicable checks.</div>'}
    {remainder_note}
  </div>
  <div class="section">
    <span class="kick">Coherence</span>
    <h2 class="sec">Knowledge base coherence</h2>
    <p class="sechint">Looks <span class="serif" style="font-size:14px">across and between</span> your articles &mdash; gaps, clashes, duplicates, stale facts and confusable names &mdash; what a per-article grade can't see.</p>
    {build_report_coherence()}
  </div>
  <div class="section">
    <span class="kick">Your voice</span>
    <h2 class="sec">Your house style</h2>
    <p class="sechint">Derived from your own articles so any rewrites keep your voice. Style never affects the grade.</p>
    {house}
    <div style="height:26px"></div>
    {cta}
  </div>
</div>"""
    (OUT / "report.html").write_text(page(f"{KB} — AI-readiness audit report", REPORT_CSS, inner, head_extra=REPORT_HEAD + FAVICON_LINK))

# ----------------------------------------------------------------- REWRITE PAGES
ART_CSS = """
#artbody h2{font:500 21px var(--font-ui);letter-spacing:-.01em;color:#1B1B1B;margin:28px 0 8px}
#artbody h3{font:500 17px var(--font-ui);color:#1B1B1B;margin:20px 0 6px}
#artbody p{font:300 16.5px/1.65 var(--font-body);color:#2F2F2F;margin:11px 0}
#artbody ol,#artbody ul{margin:11px 0;padding-left:24px}
#artbody li{font:300 16.5px/1.6 var(--font-body);color:#2F2F2F;margin:6px 0}
#artbody strong{font-weight:600;color:#1B1B1B}
#artbody a{color:#EA3609}
#artbody img{max-width:100%;height:auto;display:block;margin:14px 0;border:1px solid rgba(0,0,0,0.1);border-radius:12px}
#artbody iframe{width:100%;aspect-ratio:16/9;height:auto;border:0;border-radius:12px;margin:12px 0}
#artbody p.applies{background:#FBF8F3;border:1px solid rgba(0,0,0,0.08);border-left:3px solid #EA3609;border-radius:12px;padding:13px 16px;color:#1B1B1B;font-size:15.5px}
#artbody em{color:#A8A29A}
.kbpanel{margin:0 0 12px;border:1px solid rgba(0,0,0,0.08);border-radius:14px;background:#fff;box-shadow:0 1px 0 rgba(0,0,0,0.03),0 6px 18px rgba(0,0,0,0.05);overflow:hidden}
.kbpanel>summary{cursor:pointer;list-style:none;padding:14px 18px;display:flex;align-items:center;gap:10px;font:500 14.5px var(--font-ui);color:#1B1B1B;letter-spacing:-.01em}
.kbpanel>summary::-webkit-details-marker{display:none}
.kbpanel>summary .chev{flex:none;color:#868181;transition:transform .15s}
.kbpanel[open]>summary .chev{transform:rotate(90deg)}
.kbpanel>summary .lead{flex:none;width:9px;height:9px;border-radius:50%}
.kbpanel>summary .rt{margin-left:auto;color:#868181;font-weight:300;font-size:12.5px}
.kbpanel .pbody{padding:2px 18px 16px;font:300 13.5px/1.55 var(--font-body);color:#2F2F2F}
.kbpanel .vchk{accent-color:#EA3609}
"""

def grade_badge(txt, kind):
    # kind 'before' (orange tint) / 'after' (green tint)
    if kind == "before":
        return f'<span style="font:600 12px var(--font-ui);color:#EA3609;background:#FFD9D9;border-radius:7px;padding:4px 9px">{esc(txt)}</span>'
    return f'<span style="font:600 12px var(--font-ui);color:#2F7D57;background:#DDEEE4;border-radius:7px;padding:4px 9px">{esc(txt)}</span>'

def panels_html(w, idx):
    notes = w.get("resolved_notes", []); items = w.get("verify_items", [])
    grade = esc(w.get("after_grade", "")); raw = esc(w.get("raw_grade") or w.get("after_grade", ""))
    if notes:
        rows = "".join(f'<li style="margin:0 0 9px;list-style:none;display:flex;gap:9px;align-items:flex-start">'
                       f'<span style="flex:0 0 auto;color:#2F7D57;font-weight:600;margin-top:1px">&#10003;</span>'
                       f'<span><b style="font-weight:500;color:#1B1B1B">{esc(n["check"])}</b> &mdash; {esc(n["reason"])}</span></li>' for n in notes)
        why = (f'<div style="margin-bottom:10px">Automated re-grade <b style="font-weight:500">{raw}</b>. '
               f'{len(notes)} aspect(s) below can\'t be improved further without fabricating facts or harming the article, '
               f'so they\'re treated as resolved &mdash; <b style="font-weight:500">final grade {grade}</b>.</div>'
               f'<ul style="margin:0;padding:0">{rows}</ul>')
        grt = f'{len(notes)} aspect(s) resolved'
    else:
        why = f'<div>&#10003; <b style="color:#1B1B1B;font-weight:500">Final grade {grade}.</b> Passes every applicable check &mdash; no adjustments needed.</div>'
        grt = 'passes every check'
    vli = ""
    for j, it in enumerate(items):
        cid = f"vchk-{idx}-{j}"
        vli += (f'<li style="margin:0 0 8px;list-style:none"><label for="{cid}" style="display:flex;gap:10px;align-items:flex-start;cursor:pointer">'
                f'<input type="checkbox" id="{cid}" class="vchk" style="margin-top:3px;width:16px;height:16px;flex:0 0 auto"><span>{esc(it)}</span></label></li>')
    if not items:
        vli = '<li style="list-style:none;color:#2F7D57">&#10003; Nothing to verify — every fact traces back to the source article.</li>'
    vrt = f'{len(items)} to check' if items else 'all facts trace to source'
    vnote = ("These facts couldn't be confirmed from the source article. Tick each once you've checked it against the live "
             "product. <b>This checklist is not part of the article and is never included when you copy.</b>")
    return (f'<details class="kbpanel"><summary><span class="chev">&#9656;</span><span class="lead" style="background:#2F7D57"></span>'
            f'How this article was graded <span style="color:#868181;font-weight:300">&middot; {grade}</span>'
            f'<span class="rt">{grt}</span></summary><div class="pbody">{why}</div></details>'
            f'<details class="kbpanel"><summary><span class="chev">&#9656;</span><span class="lead" style="background:#EA3609"></span>'
            f'Verify before publishing<span class="rt">{vrt}</span></summary>'
            f'<div class="pbody"><div style="margin:0 0 10px;color:#868181">{vnote}</div><ul style="margin:0;padding:0">{vli}</ul></div></details>')

def article_body_html(md):
    h = md_to_html(md)
    # tag the Applies-to paragraph for the callout style
    h = h.replace('<p><strong>Applies to:</strong>', '<p class="applies"><strong>Applies to:</strong>', 1)
    return h

def build_rewrites():
    for old in OUT.glob("rewrite-*.html"): old.unlink()   # clear any stale pages from another generator
    n = len(RW)
    fns = [f"rewrite-{i+1:02d}-{slugify(w.get('new_title'))}.html" for i, w in enumerate(RW)]
    for i, w in enumerate(RW):
        bg, ag = w.get("before_grade", ""), w.get("after_grade", "")
        prev_fn = fns[i-1] if i > 0 else None; next_fn = fns[i+1] if i < n-1 else None
        nav = (f'<a href="{esc(prev_fn)}" style="font:500 13px var(--font-ui);text-decoration:none;color:#1B1B1B;border:1px solid rgba(0,0,0,0.14);background:#fff;border-radius:1000px;padding:8px 14px">&lsaquo; Previous</a>'
               if prev_fn else '<span style="font:500 13px var(--font-ui);color:#A8A29A;border:1px solid rgba(0,0,0,0.08);border-radius:1000px;padding:8px 14px">&lsaquo; Previous</span>')
        nav += (f'<a href="{esc(next_fn)}" style="font:500 13px var(--font-ui);text-decoration:none;color:#1B1B1B;border:1px solid rgba(0,0,0,0.14);background:#fff;border-radius:1000px;padding:8px 14px">Next &rsaquo;</a>'
                if next_fn else '<span style="font:500 13px var(--font-ui);color:#A8A29A;border:1px solid rgba(0,0,0,0.08);border-radius:1000px;padding:8px 14px">Next &rsaquo;</span>')
        notes_block = ""
        wc = w.get("what_changed"); fc = w.get("facts_to_consolidate")
        if wc or fc:
            bits = ((f'<p style="font:300 13px/1.55 var(--font-body);color:#868181;margin:9px 0"><b style="color:#1B1B1B;font-weight:600">What changed:</b> {esc(wc)}</p>' if wc else "")
                    + (f'<p style="font:300 13px/1.55 var(--font-body);color:#868181;margin:9px 0"><b style="color:#1B1B1B;font-weight:600">Facts to consolidate:</b> {esc(fc)}</p>' if fc else ""))
            notes_block = (f'<details style="margin-top:22px;border-top:1px dashed rgba(0,0,0,0.16);padding-top:14px">'
                           f'<summary style="cursor:pointer;font:600 12.5px var(--font-ui);color:#868181">Audit notes &mdash; not included in the copy</summary>{bits}</details>')
        body = f"""
<div style="min-height:100vh;background:#FFFFFF;font-family:var(--font-body);color:#1B1B1B;padding-bottom:48px">
  <div style="max-width:820px;margin:0 auto;padding:26px 24px 0">
    <div style="display:flex;align-items:center;gap:12px;margin-bottom:16px">
      <a href="{home_url('rewrite-logo', medium='rewrite')}" target="_blank" rel="noopener" title="Build your own AI support agent with My AskAI" style="display:inline-block;line-height:0">{WORDMARK % 24}</a>
      <span style="font:500 12.5px var(--font-ui);color:#868181;border-left:1px solid rgba(0,0,0,0.16);padding-left:12px">{esc(KB)} &middot; rewritten article</span>
    </div>
    <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:16px">
      <a href="dashboard.html" style="font:500 13px var(--font-ui);text-decoration:none;color:#FBF8F3;background:#1B1B1B;border-radius:1000px;padding:8px 15px">&larr; Back to audit</a>
      {nav}
      <span style="margin-left:auto;font:300 12.5px var(--font-body);color:#868181">Rewritten article {i+1} of {n}</span>
    </div>
    <div style="background:#fff;border-radius:20px;box-shadow:0 1px 0 rgba(0,0,0,0.04),0 8px 24px rgba(0,0,0,0.06);padding:30px 34px">
      <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:16px;flex-wrap:wrap">
        <h1 style="font-family:var(--font-display);font-weight:700;font-size:30px;line-height:1.08;letter-spacing:-.03em;color:#1B1B1B;margin:0;max-width:540px">{esc(w.get("new_title"))}</h1>
        <div style="display:flex;align-items:center;gap:8px;flex:none;margin-top:4px">{grade_badge(bg,"before")}<span style="color:#A8A29A">&rarr;</span>{grade_badge(ag,"after")}</div>
      </div>
      <div style="font:300 12.5px var(--font-body);color:#868181;margin:8px 0 18px">From <a href="{esc(w.get("source_url"))}" target="_blank" rel="noopener" style="color:#868181">{esc(w.get("source_title"))}</a></div>
      <div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin-bottom:18px">
        <button id="copybtn" type="button" style="font:500 13.5px var(--font-ui);border:none;border-radius:1000px;padding:10px 18px;cursor:pointer;color:#FBF8F3;background:#EA3609">Copy article</button>
        <span style="font:300 12.5px var(--font-body);color:#868181;max-width:440px">Copies the whole article &mdash; title, text, images and video &mdash; ready to paste straight into your help center.</span>
      </div>
      {panels_html(w, i)}
      <div id="artbody">{article_body_html(w.get("body",""))}</div>
      <textarea id="rawmd" readonly hidden>{esc(w.get("body",""))}</textarea>
      {notes_block}
    </div>
    <div style="font:300 12px var(--font-body);color:#868181;margin-top:20px;text-align:center">Rewritten in your own voice. Every fix works with any AI agent or helpdesk &middot; <a href="{home_url('rewrite-footer', medium='rewrite')}" target="_blank" rel="noopener" style="color:#EA3609">My AskAI</a></div>
  </div>
</div>
<script>
(function(){{
  var TITLE={json.dumps(w.get("new_title"))};
  var btn=document.getElementById('copybtn'),bodyEl=document.getElementById('artbody'),md=document.getElementById('rawmd');
  function flash(){{btn.textContent='Copied \\u2713';btn.style.background='#2F7D57';setTimeout(function(){{btn.textContent='Copy article';btn.style.background='#EA3609';}},1800);}}
  function htmlForCopy(){{return '<h1>'+TITLE+'</h1>\\n'+bodyEl.innerHTML;}}
  function plainForCopy(){{var t=(md&&md.value)||bodyEl.innerText;t=t.replace(/<iframe[^>]*src="([^"]+)"[^>]*>(<\\/iframe>)?/gi,'$1');return TITLE+'\\n\\n'+t;}}
  btn.addEventListener('click',function(){{
    if(navigator.clipboard&&window.ClipboardItem){{try{{var item=new ClipboardItem({{'text/html':new Blob([htmlForCopy()],{{type:'text/html'}}),'text/plain':new Blob([plainForCopy()],{{type:'text/plain'}})}});navigator.clipboard.write([item]).then(flash,tc);return;}}catch(e){{}}}}
    if(navigator.clipboard&&navigator.clipboard.writeText){{navigator.clipboard.writeText(plainForCopy()).then(flash,tc);}}else tc();
  }});
  function tc(){{var ta=document.createElement('textarea');ta.value=plainForCopy();ta.style.position='fixed';ta.style.opacity='0';document.body.appendChild(ta);ta.select();try{{document.execCommand('copy');}}catch(e){{}}document.body.removeChild(ta);flash();}}
  var key='kbverify:'+location.pathname.split('/').pop();var saved={{}};try{{saved=JSON.parse(localStorage.getItem(key)||'{{}}');}}catch(e){{}}
  document.querySelectorAll('.vchk').forEach(function(b){{if(saved[b.id])b.checked=true;b.addEventListener('change',function(){{saved[b.id]=b.checked;try{{localStorage.setItem(key,JSON.stringify(saved));}}catch(e){{}}}});}});
}})();
</script>
"""
        _desc = f'A rewrite of "{w.get("source_title")}" from {KB}, optimized so an AI support agent can answer from it — audited by My AskAI.'
        (OUT / fns[i]).write_text(page(f'{w.get("new_title")} — {KB}', ART_CSS, body, head_extra=social_head(f'{w.get("new_title")} — {KB}', _desc)))
    return fns

if __name__ == "__main__":
    build_dashboard(); build_scorecard(); build_report(); fns = build_rewrites()
    print(f"Branded: dashboard.html, scorecard.html, report.html + {len(fns)} rewrite page(s)")

#!/usr/bin/env python3
"""
build_outputs.py - turn results.json into the four deliverables, written for a reader
who has NEVER seen the source framework:
  1. exec_summary.md      (1-page shareable overview, self-explanatory)
  2. audit_tracker.xlsx   (plain-language check grid + rewrite-status column)
  3. dashboard.html       (My AskAI-branded live hub, with a 'how this works' intro)

Brand = My AskAI tokens (canonical: VideoFactory/remotion/brand.ts):
white canvas, near-black ink, ONE Signal Red accent, pale-red tint for highlights,
Inter type, flat/editorial (no gradients, no dark blue, no purple). Swap BRAND to retheme.
Usage: build_outputs.py results.json --kb-name "Bird Buddy" --outdir out/
"""
import json, argparse, html, re
from pathlib import Path

BRAND = {
 "red":"#EA3609",      # Signal Red - accent only, never large surfaces
 "red_tint":"#FCE7E1", # pale red - highlights/badges
 "ink":"#1B1B1B",      # near-black type
 "ink2":"#5A5A5A",     # secondary type
 "surface":"#FFFFFF",
 "muted":"#F7F7F7",    # soft grey fill
 "line":"#E4E4E4",     # outline
}

def esc(s): return html.escape(str(s))

def _inline(s):
    """Inline markdown -> HTML (bold, italic, code, images, links). Input is escaped first."""
    s=html.escape(s)
    s=re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', s)
    s=re.sub(r'(?<!\*)\*(?!\s)(.+?)(?<!\s)\*(?!\*)', r'<em>\1</em>', s)
    s=re.sub(r'`([^`]+)`', r'<code>\1</code>', s)
    # images BEFORE links (image syntax contains link syntax)
    s=re.sub(r'!\[([^\]]*)\]\(([^)\s]+)\)', r'<img src="\2" alt="\1" loading="lazy">', s)
    s=re.sub(r'\[([^\]]+)\]\(([^)\s]+)\)', r'<a href="\2" target="_blank" rel="noopener">\1</a>', s)
    return s

def _yt_id(s):
    m=re.search(r'(?:youtube(?:-nocookie)?\.com/embed/|youtu\.be/|[?&]v=)([A-Za-z0-9_-]{6,})', s or '')
    return m.group(1) if m else None

def _yt_facade(vid, embed):
    """A click-to-play thumbnail (works from any origin, incl. file://). The original embed is
    kept in data-embed so the Copy button can paste a real video into the help centre."""
    thumb=f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg"; watch=f"https://www.youtube.com/watch?v={vid}"
    return (f'<a class="ytfacade" href="{watch}" target="_blank" rel="noopener" '
            f'data-embed="{esc(embed)}" data-watch="{watch}">'
            f'<img src="{thumb}" alt="Watch the video on YouTube" loading="lazy">'
            f'<span class="ytplay" aria-hidden="true"></span></a>')

def md_to_html(md):
    """Compact, dependency-free Markdown -> HTML for the rewritten-article preview.
    Handles headings, bold/italic/code/links, blockquotes, ordered/unordered lists,
    pipe tables, horizontal rules and paragraphs — enough for help-article bodies."""
    lines=(md or "").replace("\r\n","\n").split("\n"); out=[]; i=0; n=len(lines)
    while i<n:
        ln=lines[i]
        if not ln.strip(): i+=1; continue
        if re.match(r'\s*---+\s*$', ln): out.append("<hr>"); i+=1; continue
        # raw HTML media (images / video embeds) — pass through verbatim so the original
        # screenshots and videos render in the preview and travel with the copy
        if re.match(r'\s*<(img|iframe|video|figure|embed)\b', ln, re.I):
            raw=ln; i+=1
            while '<iframe' in raw.lower() and '</iframe>' not in raw.lower() and i<n:
                raw+=" "+lines[i]; i+=1
            raw=raw.strip()
            vid=_yt_id(raw) if 'iframe' in raw.lower() else None
            out.append(_yt_facade(vid, raw) if vid else f'<p class="media">{raw}</p>'); continue
        m=re.match(r'\s*(#{1,6})\s+(.*)', ln)
        if m: lvl=len(m.group(1)); out.append(f"<h{lvl}>{_inline(m.group(2).strip())}</h{lvl}>"); i+=1; continue
        if re.match(r'\s*>', ln):
            buf=[]
            while i<n and re.match(r'\s*>', lines[i]):
                buf.append(re.sub(r'\s*>\s?', '', lines[i], count=1)); i+=1
            qt=" ".join(b for b in buf if b.strip())
            # "Applies to:" renders as a plain styled paragraph, NOT a blockquote — some help-centre
            # editors convert a pasted blockquote into a callout and drop everything after the bold lead-in.
            if re.match(r'\s*\*\*applies to', qt, re.I):
                out.append('<p class="applies">'+_inline(qt)+'</p>')
            else:
                out.append("<blockquote>"+_inline(qt)+"</blockquote>")
            continue
        if '|' in ln and i+1<n and '---' in lines[i+1] and re.match(r'\s*\|?[\s:|-]+\|', lines[i+1]):
            header=[c.strip() for c in ln.strip().strip('|').split('|')]; i+=2; rows=[]
            while i<n and '|' in lines[i] and lines[i].strip():
                rows.append([c.strip() for c in lines[i].strip().strip('|').split('|')]); i+=1
            th="".join(f"<th>{_inline(c)}</th>" for c in header)
            tb="".join("<tr>"+"".join(f"<td>{_inline(c)}</td>" for c in r)+"</tr>" for r in rows)
            out.append(f"<table class='rwt'><thead><tr>{th}</tr></thead><tbody>{tb}</tbody></table>"); continue
        if re.match(r'\s*[-*]\s+', ln):
            items=[]
            while i<n and re.match(r'\s*[-*]\s+', lines[i]):
                items.append(_inline(re.sub(r'\s*[-*]\s+', '', lines[i], count=1))); i+=1
            out.append("<ul>"+"".join(f"<li>{it}</li>" for it in items)+"</ul>"); continue
        if re.match(r'\s*\d+\.\s+', ln):
            items=[]
            while i<n and re.match(r'\s*\d+\.\s+', lines[i]):
                items.append(_inline(re.sub(r'\s*\d+\.\s+', '', lines[i], count=1))); i+=1
            out.append("<ol>"+"".join(f"<li>{it}</li>" for it in items)+"</ol>"); continue
        buf=[ln]; i+=1
        while i<n and lines[i].strip() and not re.match(r'\s*(#{1,6}\s|>|[-*]\s|\d+\.\s|---+\s*$)', lines[i]) and '|' not in lines[i]:
            buf.append(lines[i]); i+=1
        para=" ".join(buf)
        cls=' class="applies"' if re.match(r'\s*\*\*applies to', para, re.I) else ''
        out.append(f"<p{cls}>"+_inline(para)+"</p>")
    return "\n".join(out)

# ---------------- exec summary ----------------
def exec_summary(d, kb):
    r=d["results"]; n=d["article_count"]; roll=d["pattern_rollup"]; order=d["order"]
    needfix=[a for a in r if a["fixes"]>0]; clean=[a for a in r if a["fixes"]==0]
    weakest=sorted(roll.items(), key=lambda kv: kv[1]["pass_pct"])[:4]
    L=[]
    L.append(f"# {kb} — Help Centre AI-Readiness Audit\n")
    L.append(f"*{n} articles checked · generated {d['generated'][:10]}*\n")
    L.append("## What this is\n")
    L.append("An AI support agent doesn't read your help centre the way a person does. It looks at "
             "**one article at a time, with no memory of the last one**, and answers only from what's "
             "in front of it. It can't scroll past intro text, click 'see also', read a screenshot, or "
             "know which article is the up-to-date one. This audit grades every article on the 13 things "
             "that decide whether the AI can actually answer from it — then, if you want, rewrites the "
             "articles you choose so you can paste them straight back in (or push them as drafts).\n")
    L.append("## The headline\n")
    L.append(f"Your help centre scores an overall **{d['overall_grade']}** for AI-readiness "
             f"({d['overall_pct']}% of checks passing across {n} articles). "
             f"**{len(needfix)} articles** have at least one issue that can cost you a resolution; "
             f"**{len(clean)}** are already clean. Start with the priority list below "
             f"(busiest articles with the lowest grades first).\n")
    L.append("## The biggest wins across your whole help centre\n")
    for p,v in weakest:
        L.append(f"- **{p}** — {v['pass_pct']}% of articles pass. *Why it matters:* {v['why']}")
    L.append("")
    L.append("## Fix these first\n")
    for a in r[:5]:
        fails=[roll[k]['short'] for k in order if a["checks"][k]["verdict"]=="Fix"]
        L.append(f"### {a['rank']}. {a['title']} — Grade {a['grade']} ({a['score_str']} checks)")
        L.append(f"*{a['vote_count']} reader votes · priority to fix: {a['priority_band']}*  ")
        L.append("Needs work on: " + ", ".join(fails))
        for k in order:
            c=a["checks"][k]
            if c["verdict"]=="Fix":
                L.append(f"  - **{k}** — {c['note']}")
        L.append(f"  - [Open article]({a['url']})\n")
    c=d.get("corpus")
    if c:
        L.append("## Across your whole help centre (coherence)\n")
        L.append("These look between and across articles — what a per-article grade can't see:\n")
        cov=c["coverage"]
        if cov["status"]=="locked":
            L.append("- **Coverage gaps** — *locked.* Add a ticket export (`--tickets export.csv`) to reveal "
                     "the questions customers ask that have no article. This is usually the single biggest win.")
        elif cov["status"]=="ok" and cov["gaps"]:
            top=cov["gaps"][0]
            L.append(f"- **Coverage gaps** — {cov['covered_pct']}% of ticket topics have an article. Biggest miss: "
                     f"**{', '.join(top['terms'])}** ({top['volume']} tickets, no article).")
        if c["contradictions"]:
            f=c["contradictions"][0]
            L.append(f"- **Contradictions** — {len(c['contradictions'])} article pair(s) disagree, e.g. *{f['subject']}* "
                     f"is {f['a_val']} vs {f['b_val']} across two articles. The AI will quote whichever it lands on.")
        else:
            L.append("- **Contradictions** — none detected. ✓")
        if c["collisions"]:
            L.append(f"- **Near-duplicates** — {len(c['collisions'])} pair(s) of articles compete for the same question; "
                     "merge each into one canonical answer.")
        if c["dates"]["stale_count"]:
            L.append(f"- **Stale dates** — {c['dates']['stale_count']} article(s) quote a past-dated, time-sensitive detail.")
        if c["dates"].get("no_freshness_signal"):
            L.append(f"- **No freshness signal** — {c['dates']['no_freshness_signal']} article(s) carry no last-updated date.")
        if c["disambiguation"]:
            g=c["disambiguation"][0]
            L.append(f"- **Confusable names** — e.g. **{' / '.join(g['names'])}** are used together without being told apart.")
        L.append("")
    sp=d["style_profile"]
    L.append("## Your house style (so rewrites still sound like you)\n")
    L.append(f"> {sp['descriptor']}\n")
    L.append(f"Average article {sp['avg_words_per_article']} words · {sp['avg_sentence_words']}-word sentences · "
             f"{sp['faq_pattern_pct']}% step-by-step/FAQ · {sp['heading_case']} headings.\n")
    L.append("The audit scores structure objectively; rewrites keep this voice. Clearer articles help "
             "your human readers too — the AI just makes it non-negotiable.\n")
    L.append("---\n*Every fix here works with any AI agent or helpdesk. Keeping a help centre AI-ready "
             "over time is what [My AskAI](https://myaskai.com) does automatically.*\n")
    return "\n".join(L)

# ---------------- xlsx ----------------
def build_xlsx(d, path):
    from openpyxl import Workbook
    from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
    from openpyxl.comments import Comment
    order=d["order"]; roll=d["pattern_rollup"]
    fills={"Pass":BRAND["muted"][1:],"Fix":BRAND["red"][1:],"N/A":BRAND["surface"][1:]}
    fonts={"Pass":Font(color=BRAND["ink"][1:],bold=True),"Fix":Font(color="FFFFFF",bold=True),"N/A":Font(color=BRAND["line"][1:])}
    wb=Workbook(); ws=wb.active; ws.title="Audit"
    hdr=Font(bold=True,color="FFFFFF"); hfill=PatternFill("solid",fgColor=BRAND["ink"][1:])
    thin=Side(style="thin",color="E4E4E4"); bd=Border(thin,thin,thin,thin)
    cols=["#","Article","Grade","Score","Priority to fix","Votes"]+[roll[k]["short"] for k in order]+["Rewrite status"]
    base=7  # first check column
    ws.append(cols)
    for j,_ in enumerate(cols,1):
        c=ws.cell(1,j); c.font=hdr; c.fill=hfill; c.border=bd
        c.alignment=Alignment(horizontal="center",vertical="center",wrap_text=True)
        if base-1<j<=base-1+len(order):
            c.comment=Comment(order[j-base]+" — "+roll[order[j-base]]["why"],"audit")
    for a in d["results"]:
        verds=[a["checks"][k]["verdict"] for k in order]
        ws.append([a["rank"],a["title"],a["grade"],a["score_str"],a["priority_band"],a["vote_count"]]+verds+[""])
        ri=ws.max_row
        gc=ws.cell(ri,3); gc.font=Font(bold=True,color=(BRAND["red"][1:] if a["grade"][0] in "DF" else BRAND["ink"][1:])); gc.alignment=Alignment(horizontal="center")
        for idx,k in enumerate(order):
            cell=ws.cell(ri,base+idx); v=a["checks"][k]["verdict"]
            cell.value={"Pass":"✓","Fix":"✕","N/A":"–"}[v]
            cell.fill=PatternFill("solid",fgColor=fills[v]); cell.font=fonts[v]
            cell.alignment=Alignment(horizontal="center"); cell.border=bd
            if v=="Fix": cell.comment=Comment(a["checks"][k]["note"],"audit")
    ws.column_dimensions["B"].width=44
    for col in "CD": ws.column_dimensions[col].width=9
    ws.column_dimensions["E"].width=13
    ws.freeze_panes="B2"
    ws2=wb.create_sheet("What each check means")
    ws2.append(["Group","Check","Why it matters","% passing"])
    for j in range(1,5): ws2.cell(1,j).font=hdr; ws2.cell(1,j).fill=hfill
    for k in order:
        v=roll[k]; ws2.append([v["group"],k,v["why"],f"{v['pass_pct']}%"])
    ws2.column_dimensions["A"].width=32; ws2.column_dimensions["B"].width=30; ws2.column_dimensions["C"].width=72
    c=d.get("corpus")
    if c:
        ws3=wb.create_sheet("KB coherence")
        ws3.append(["Type","Finding","Detail"])
        for j in range(1,4): ws3.cell(1,j).font=hdr; ws3.cell(1,j).fill=hfill
        cov=c["coverage"]
        if cov["status"]=="locked": ws3.append(["Coverage gap","(locked)","Add --tickets export.csv to unlock"])
        else:
            for g in cov.get("gaps",[]): ws3.append(["Coverage gap",", ".join(g["terms"]),f"{g['volume']} tickets, no article · e.g. "+" / ".join(g["examples"])])
        for f in c["contradictions"]:
            ws3.append(["Contradiction",f["subject"],f"{f['a_val']} in '{f['a']}' vs {f['b_val']} in '{f['b']}' ({f['unit']})"])
        for p in c["collisions"]:
            ws3.append(["Near-duplicate",f"{p['a']}  /  {p['b']}",f"{round(p['similarity']*100)}% overlap · shared: {', '.join(p['shared'][:4])}"])
        for s in c["dates"]["stale_dated"]:
            ws3.append(["Stale date",s["title"],f"quotes past-dated detail: {s['detail']}"])
        for f in c["disambiguation"]:
            ws3.append(["Confusable names"," / ".join(f["names"]),f"used together in {f['count']} article(s) without distinction"])
        ws3.column_dimensions["A"].width=18; ws3.column_dimensions["B"].width=40; ws3.column_dimensions["C"].width=80
    wb.save(path)

# ---------------- per-article rewrite pages ----------------
def slugify(s):
    s=re.sub(r'[^a-z0-9]+','-',str(s).lower()).strip('-')
    return (s[:48] or "article").strip('-')

def _norm_url(u):
    return re.sub(r'^https?://','',str(u or '').strip()).rstrip('/').lower()

def _page_css(B):
    return f""":root{{--red:{B['red']};--tint:{B['red_tint']};--ink:{B['ink']};--ink2:{B['ink2']};
--surface:{B['surface']};--muted:{B['muted']};--line:{B['line']}}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--muted);color:var(--ink);
font:15px/1.6 Inter,-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;-webkit-font-smoothing:antialiased}}
.wrap{{max-width:760px;margin:0 auto;padding:22px 20px 70px}}
.brandbar{{display:flex;align-items:center;gap:9px;margin-bottom:14px}}
.bubble{{width:22px;height:18px;background:var(--red);border-radius:6px 6px 6px 2px;position:relative;flex:none}}
.bubble:after{{content:"";position:absolute;left:5px;bottom:-4px;width:7px;height:7px;background:var(--red);
clip-path:polygon(0 0,100% 0,0 100%)}}
.logo{{font-weight:800;letter-spacing:-.02em;font-size:16px}}.logo span{{color:var(--ink2);font-weight:500}}
.kicker{{color:var(--ink2);font-size:12px;border-left:1px solid var(--line);padding-left:9px;margin-left:3px}}
.nav{{display:flex;align-items:center;gap:10px;flex-wrap:wrap;background:var(--surface);border:1px solid var(--line);
border-radius:12px;padding:10px 12px;margin-bottom:16px}}
.nav a,.nav span.dis{{font:600 13px Inter;text-decoration:none;color:var(--ink);border:1px solid var(--line);
background:var(--surface);border-radius:8px;padding:7px 12px;white-space:nowrap}}
.nav a:hover{{border-color:var(--red);color:var(--red)}}
.nav a.back{{background:var(--ink);color:#fff;border-color:var(--ink)}}.nav a.back:hover{{background:#000;color:#fff}}
.nav span.dis{{opacity:.4;cursor:default}}.nav .pos{{margin-left:auto;color:var(--ink2);font-size:12.5px;border:0;background:none;font-weight:500}}
.card{{background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:26px 30px}}
.ah{{display:flex;align-items:flex-start;justify-content:space-between;gap:14px;flex-wrap:wrap;margin-bottom:4px}}
h1{{font-size:23px;letter-spacing:-.02em;margin:0;font-weight:800}}
.gr{{display:flex;align-items:center;gap:7px;flex:none;margin-top:4px}}
.gb{{font-weight:800;font-size:12px;padding:3px 8px;border-radius:6px;background:var(--muted);border:1px solid var(--line)}}
.gb.gf{{color:var(--red)}}.gb.gp{{color:#16794a}}.arr{{color:var(--ink2)}}
.src{{color:var(--ink2);font-size:12.5px;margin:6px 0 14px}}.src a{{color:var(--ink2)}}
.copyrow{{margin:0 0 18px}}
.copybtn{{font:700 13.5px Inter;color:#fff;background:var(--red);border:0;border-radius:9px;padding:10px 18px;cursor:pointer;transition:background .15s}}
.copybtn:hover{{background:#c52d06}}.copybtn.ok{{background:#16794a}}
.copyhint{{color:var(--ink2);font-size:12px;margin-left:10px}}
.body{{font-size:15px;color:var(--ink)}}
.body h1,.body h2,.body h3{{letter-spacing:-.01em;margin:20px 0 8px}}
.body h1{{font-size:20px}}.body h2{{font-size:17px}}.body h3{{font-size:15px}}
.body p{{margin:10px 0}}.body ul,.body ol{{margin:10px 0;padding-left:24px}}.body li{{margin:4px 0}}
.body blockquote{{margin:12px 0;padding:11px 15px;background:var(--tint);border-left:3px solid var(--red);
border-radius:7px;color:#5a241a}}
.body p.applies{{margin:12px 0;padding:11px 15px;background:var(--tint);border-left:3px solid var(--red);
border-radius:7px;color:#5a241a}}
.body a{{color:var(--red)}}.body code{{background:var(--muted);padding:1px 5px;border-radius:4px;font-size:13px}}
.body img{{max-width:100%;height:auto;display:block;margin:12px 0;border:1px solid var(--line);border-radius:10px}}
.body p.media{{margin:14px 0}}
.body iframe{{width:100%;aspect-ratio:16/9;height:auto;border:0;border-radius:10px;margin:6px 0}}
.body .ytfacade{{position:relative;display:block;margin:14px 0;border-radius:10px;overflow:hidden;border:1px solid var(--line);aspect-ratio:16/9;background:#000}}
.body .ytfacade img{{width:100%;height:100%;object-fit:cover;display:block;margin:0;border:0;border-radius:0}}
.body .ytplay{{position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);width:64px;height:46px;background:rgba(0,0,0,.72);border-radius:12px;transition:background .15s}}
.body .ytplay:after{{content:"";position:absolute;left:52%;top:50%;transform:translate(-50%,-50%);border-style:solid;border-width:10px 0 10px 17px;border-color:transparent transparent transparent #fff}}
.body .ytfacade:hover .ytplay{{background:var(--red)}}
.body table{{width:100%;border-collapse:collapse;margin:12px 0;font-size:14px}}
.body table th,.body table td{{border:1px solid var(--line);padding:7px 10px;text-align:left}}
.body table th{{background:var(--muted);font-weight:700}}
.notes{{margin-top:18px;border-top:1px dashed var(--line);padding-top:12px}}
.notes summary{{cursor:pointer;color:var(--ink2);font-size:12.5px;font-weight:600}}
.notes p{{color:var(--ink2);font-size:13px;margin:8px 0}}
.foot{{color:var(--ink2);font-size:12px;margin-top:22px;text-align:center}}.foot a{{color:var(--red)}}"""

def _nav_html(prev_fn, next_fn, idx, total):
    prev=(f'<a href="{esc(prev_fn)}">‹ Previous</a>' if prev_fn else '<span class="dis">‹ Previous</span>')
    nxt=(f'<a href="{esc(next_fn)}">Next ›</a>' if next_fn else '<span class="dis">Next ›</span>')
    return (f'<div class="nav"><a class="back" href="dashboard.html">← Back to audit</a>'
            f'{prev}{nxt}<span class="pos">Updated article {idx} of {total}</span></div>')

def article_page_html(kb, rw, idx, total, prev_fn, next_fn, B):
    body=rw.get("body","").strip()
    title=esc(rw.get("new_title") or rw.get("title") or "Rewritten article")
    src_t=esc(rw.get("source_title","")); src_u=rw.get("source_url","")
    bg=rw.get("before_grade",""); ag=rw.get("after_grade","")
    badge=""
    if bg or ag:
        bgc="gf" if str(bg)[:1] in "DF" else "gp"
        badge=(f'<span class="gb {bgc}">{esc(bg)}</span><span class="arr">→</span>'
               f'<span class="gb gp">{esc(ag)}</span>')
    src=f'<div class="src">From <a href="{esc(src_u)}" target="_blank" rel="noopener">{src_t}</a></div>' if src_t else ""
    notes=""
    wc=rw.get("what_changed"); facts=rw.get("facts_to_consolidate")
    if wc or facts:
        bits=(f"<p><b>What changed:</b> {esc(wc)}</p>" if wc else "")+(f"<p><b>Facts to consolidate:</b> {esc(facts)}</p>" if facts else "")
        notes=f'<details class="notes"><summary>Audit notes — not included in the copy</summary>{bits}</details>'
    nav=_nav_html(prev_fn,next_fn,idx,total)
    title_js=json.dumps(rw.get("new_title") or rw.get("title") or "Rewritten article")
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} — {esc(kb)}</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>{_page_css(B)}</style></head><body><div class="wrap">
<div class="brandbar"><span class="bubble"></span><span class="logo">my<span>AskAI</span></span>
<span class="kicker">{esc(kb)} · rewritten article</span></div>
{nav}
<div class="card">
<div class="ah"><h1>{title}</h1><div class="gr">{badge}</div></div>
{src}
<div class="copyrow"><button class="copybtn" id="copybtn" type="button">Copy article</button>
<span class="copyhint">Copies the whole article — title, text, images and video — ready to paste straight into your help centre.</span></div>
<div class="body" id="articlebody">{md_to_html(body)}</div>
<textarea id="rawmd" readonly hidden>{esc(body)}</textarea>
{notes}
</div>
{nav}
<div class="foot">Rewritten in your own voice. Every fix works with any AI agent or helpdesk · <a href="https://myaskai.com" target="_blank">myAskAI</a></div>
</div>
<script>
(function(){{
  var TITLE={title_js};
  var btn=document.getElementById('copybtn'),bodyEl=document.getElementById('articlebody'),md=document.getElementById('rawmd');
  function flash(){{ btn.textContent='Copied ✓'; btn.classList.add('ok'); setTimeout(function(){{btn.textContent='Copy article';btn.classList.remove('ok');}},1700); }}
  function esch(s){{ return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }}
  function htmlForCopy(){{
    var clone=bodyEl.cloneNode(true);
    Array.prototype.forEach.call(clone.querySelectorAll('.ytfacade'),function(f){{
      var holder=document.createElement('div'); holder.innerHTML=f.getAttribute('data-embed');
      var node=holder.firstChild; if(node&&f.parentNode) f.parentNode.replaceChild(node,f);
    }});
    return '<h1>'+esch(TITLE)+'</h1>\\n'+clone.innerHTML;
  }}
  function plainForCopy(){{
    var t=(md&&md.value)||bodyEl.innerText;
    t=t.replace(/<iframe[^>]*src="([^"]+)"[^>]*><\\/iframe>/gi,'$1').replace(/<iframe[^>]*src="([^"]+)"[^>]*>/gi,'$1');
    t=t.replace(/^[ \\t]*>[ \\t]?/gm,'');
    return TITLE+'\\n\\n'+t;
  }}
  btn.addEventListener('click',function(){{
    if(navigator.clipboard&&window.ClipboardItem){{
      try{{
        var item=new ClipboardItem({{'text/html':new Blob([htmlForCopy()],{{type:'text/html'}}),'text/plain':new Blob([plainForCopy()],{{type:'text/plain'}})}});
        navigator.clipboard.write([item]).then(flash,function(){{textFallback();}});
        return;
      }}catch(e){{}}
    }}
    if(navigator.clipboard&&navigator.clipboard.writeText){{ navigator.clipboard.writeText(plainForCopy()).then(flash,textFallback); }}
    else textFallback();
  }});
  function textFallback(){{ var ta=document.createElement('textarea'); ta.value=plainForCopy(); ta.style.position='fixed'; ta.style.opacity='0'; document.body.appendChild(ta); ta.select(); try{{document.execCommand('copy');}}catch(e){{}} document.body.removeChild(ta); flash(); }}
}})();
</script>
</body></html>"""

def build_article_pages(rewrites, kb, outdir, B):
    """Write one self-contained HTML page per rewrite, with Back / Prev / Next nav.
    Returns (source_url -> first page filename, list of filenames)."""
    fns=[f"rewrite-{i+1:02d}-{slugify(rw.get('new_title') or rw.get('title') or 'article')}.html"
         for i,rw in enumerate(rewrites)]
    by_source={}
    for i,rw in enumerate(rewrites):
        prev_fn=fns[i-1] if i>0 else None
        next_fn=fns[i+1] if i<len(rewrites)-1 else None
        (outdir/fns[i]).write_text(article_page_html(kb,rw,i+1,len(rewrites),prev_fn,next_fn,B))
        key=_norm_url(rw.get("source_url"))
        if key and key not in by_source: by_source[key]=fns[i]
    return by_source, fns

# ---------------- html dashboard ----------------
def build_html(d, kb, path, rewrites=None, rewrite_links=None):
    r=d["results"]; roll=d["pattern_rollup"]; sp=d["style_profile"]; order=d["order"]; groups=d["groups"]
    needfix=sum(1 for a in r if a["fixes"]>0)
    heads="".join(f'<th title="{esc(roll[k]["why"])}">{esc(roll[k]["short"])}</th>' for k in order)
    rows=""
    for a in r:
        cells=""
        for k in order:
            v=a["checks"][k]["verdict"]; cls={"Pass":"p","Fix":"f","N/A":"n"}[v]
            glyph={"Pass":"✓","Fix":"✕","N/A":"–"}[v]
            cells+=f'<td class="{cls}" title="{esc(roll[k]["short"])} — {esc(a["checks"][k]["note"])}">{glyph}</td>'
        gcls="gr"+(" gf" if a["grade"][0] in "DF" else "")
        prisl="pri-"+a["priority_band"].lower().replace(" ","")
        fn=(rewrite_links or {}).get(_norm_url(a["url"]))
        rwcell=(f'<td class="rwc"><a class="rwbtn" href="{esc(fn)}">View →</a></td>' if fn
                else f'<td class="rwc"><button class="optbtn" type="button" '
                     f'data-title="{esc(a["title"])}" data-url="{esc(a["url"])}">Optimize</button></td>')
        haspatch="1" if fn else "0"
        rows+=(f'<tr data-title="{esc(a["title"].lower())}" data-grade="{a["grade"][0]}" '
               f'data-pri="{esc(a["priority_band"].lower().replace(" ",""))}" data-fixes="{a["fixes"]}" data-rw="{haspatch}">'
               f'<td class="rk">{a["rank"]}</td>'
               f'<td class="ti"><a href="{esc(a["url"])}" target="_blank">{esc(a["title"])}</a></td>'
               f'{rwcell}'
               f'<td class="{gcls}" title="{a["score_str"]} checks pass">{a["grade"]}</td>'
               f'<td class="pri {prisl}">{a["priority_band"]}</td><td>{a["vote_count"]}</td>{cells}</tr>')
    blocks=""
    for g in groups:
        items=""
        for k in order:
            if roll[k]["group"]!=g: continue
            v=roll[k]
            items+=(f'<div class="bar"><span class="bl" title="{esc(v["why"])}">{esc(k)}</span>'
                    f'<span class="bt"><i style="width:{max(v["pass_pct"],2)}%"></i></span>'
                    f'<span class="bv">{v["pass_pct"]}%</span></div>')
        blocks+=f'<div class="grp"><h3>{esc(g)}</h3>{items}</div>'

    # ---- house-style summary line (single, editable block in the body) ----
    sig=sp.get("signals",{})
    style_stats=(f"Average {sp['avg_words_per_article']} words/article · "
                 f"{sp['avg_sentence_words']}-word sentences"
                 + (f" (typically {esc(sig['sentence_range'])})" if sig.get("sentence_range") else "")
                 + f" · {esc(sp['heading_case'])} headings.")

    n_rw=len(rewrite_links or {})
    kb_js=json.dumps(kb); desc_js=json.dumps(sp.get("descriptor",""))
    # shareable one-line summary + scorecard link
    weakest_check,weakest_v=min(roll.items(),key=lambda kv:kv[1]['pass_pct'])
    share_summary=(f"{kb} scored {d['overall_grade']} ({d['overall_pct']}%) for AI-readiness across "
                   f"{d['article_count']} help-centre articles. Biggest gap: \"{weakest_check}\" "
                   f"({weakest_v['pass_pct']}% pass). Audit by My AskAI — myaskai.com")
    share_js=json.dumps(share_summary)
    B=BRAND
    doc=f"""<!doctype html><html><head><meta charset="utf-8"><title>{esc(kb)} — Help Centre AI-Readiness Audit</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>
:root{{--red:{B['red']};--tint:{B['red_tint']};--ink:{B['ink']};--ink2:{B['ink2']};
--surface:{B['surface']};--muted:{B['muted']};--line:{B['line']}}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--surface);color:var(--ink);
font:14px/1.55 Inter,-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;-webkit-font-smoothing:antialiased}}
.wrap{{max-width:1120px;margin:0 auto;padding:30px 26px 64px}}
.brandbar{{display:flex;align-items:center;gap:9px;margin-bottom:22px}}
.bubble{{width:22px;height:18px;background:var(--red);border-radius:6px 6px 6px 2px;position:relative;flex:none}}
.bubble:after{{content:"";position:absolute;left:5px;bottom:-4px;width:7px;height:7px;background:var(--red);
clip-path:polygon(0 0,100% 0,0 100%)}}
.logo{{font-weight:800;letter-spacing:-.02em;font-size:17px;color:var(--ink)}}
.logo span{{color:var(--ink2);font-weight:500}}
.kicker{{color:var(--ink2);font-size:12px;border-left:1px solid var(--line);padding-left:9px;margin-left:3px}}
h1{{font-size:26px;margin:4px 0 2px;letter-spacing:-.02em;font-weight:800}}
.sub{{color:var(--ink2);margin-bottom:20px;font-size:13px}}
.intro{{background:var(--tint);border-radius:10px;padding:15px 18px;margin-bottom:24px;color:#5a241a;font-size:13.5px}}
.intro b{{color:var(--ink)}}
.cards{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:24px}}
.card{{background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:16px}}
.card .big{{font-size:28px;font-weight:800;letter-spacing:-.02em}}
.card.alert .big{{color:var(--red)}}
.card .lbl{{color:var(--ink2);font-size:12px;margin-top:3px}}
.sec{{background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:22px;margin-bottom:18px}}
.sec h2{{font-size:12px;margin:0 0 3px;color:var(--ink2);text-transform:uppercase;letter-spacing:.08em;font-weight:700}}
.sec .hint{{color:var(--ink2);font-size:12px;margin:0 0 16px}}
.grp{{margin:16px 0}}.grp h3{{font-size:14px;margin:0 0 9px;font-weight:700}}
.bar{{display:grid;grid-template-columns:268px 1fr 40px;align-items:center;gap:12px;margin:7px 0}}
.bl{{font-size:12.5px;color:var(--ink)}}
.bt{{background:var(--muted);border-radius:3px;height:9px;overflow:hidden;border:1px solid var(--line)}}
.bt i{{display:block;height:100%;background:var(--ink)}}
.bv{{text-align:right;font-variant-numeric:tabular-nums;color:var(--ink);font-weight:700}}
table{{width:100%;border-collapse:collapse;font-size:12px}}
th,td{{padding:8px 4px;text-align:center;border-bottom:1px solid var(--line)}}
th{{color:var(--ink2);font-weight:600;font-size:10px}}
td.ti{{text-align:left;max-width:250px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
td.ti a{{color:var(--ink);text-decoration:none;font-weight:500}}td.ti a:hover{{color:var(--red)}}
td.rk{{color:var(--ink2)}}td.gr{{font-weight:800;font-size:14px}}td.gr.gf{{color:var(--red)}}
.big.gf{{color:var(--red)}}
td.pri{{font-weight:600;font-size:11px}}td.pri-veryhigh,td.pri-high{{color:var(--red)}}
td.pri-low,td.pri-verylow{{color:var(--ink2)}}
td.p{{color:var(--ink2)}}
td.f{{background:var(--red);color:#fff;font-weight:700;border-radius:3px}}
td.n{{color:var(--line)}}
.legend{{color:var(--ink2);font-size:11px;margin-top:10px}}
.legend b.f{{color:var(--red)}}
.foot{{color:var(--ink2);font-size:12px;margin-top:26px}}.foot a{{color:var(--red)}}
.filters{{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin:0 0 14px}}
.filters input,.filters select{{font:13px Inter,sans-serif;color:var(--ink);background:var(--surface);
border:1px solid var(--line);border-radius:8px;padding:7px 10px;outline:none}}
.filters input{{flex:1;min-width:180px}}
.filters input:focus,.filters select:focus{{border-color:var(--red)}}
.filters .fcount{{color:var(--ink2);font-size:12px;margin-left:auto;font-variant-numeric:tabular-nums}}
tr.hide{{display:none}}
.emptyrow td{{padding:18px;color:var(--ink2);text-align:center}}
td.rwc{{text-align:center}}
.rwbtn{{display:inline-block;font:700 10.5px Inter,sans-serif;color:#fff;background:var(--red);text-decoration:none;
border-radius:6px;padding:3px 8px;white-space:nowrap}}
.rwbtn:hover{{background:#c52d06}}
.optbtn{{font:600 10.5px Inter,sans-serif;color:var(--red);background:var(--surface);border:1px solid var(--red);
border-radius:6px;padding:3px 8px;white-space:nowrap;cursor:pointer}}
.optbtn:hover{{background:var(--tint)}}.optbtn.ok{{color:#fff;background:#16794a;border-color:#16794a}}
.toast{{position:fixed;left:50%;bottom:26px;transform:translateX(-50%) translateY(20px);background:var(--ink);
color:#fff;font:500 13px Inter,sans-serif;padding:11px 16px;border-radius:10px;box-shadow:0 6px 24px rgba(0,0,0,.22);
opacity:0;pointer-events:none;transition:opacity .2s,transform .2s;max-width:90vw;z-index:50}}
.toast.show{{opacity:1;transform:translateX(-50%) translateY(0)}}
.hsedit{{width:100%;font:500 13.5px/1.5 Inter,sans-serif;color:var(--ink);background:var(--muted);border:1px solid var(--line);
border-left:3px solid var(--red);border-radius:8px;padding:12px 14px;resize:vertical;outline:none}}
.hsedit:focus{{border-color:var(--red);background:var(--surface)}}
.hsrow{{display:flex;align-items:center;gap:12px;margin-top:9px;flex-wrap:wrap}}
.hsbtn{{font:600 12px Inter,sans-serif;color:var(--ink2);background:var(--surface);border:1px solid var(--line);
border-radius:7px;padding:6px 11px;cursor:pointer}}.hsbtn:hover{{border-color:var(--red);color:var(--red)}}
.hssaved{{color:#16794a;font-size:12px;font-weight:600;opacity:0;transition:opacity .2s}}.hssaved.show{{opacity:1}}
.hsstats{{color:var(--ink2);font-size:12px;margin-left:auto}}
.sharebar{{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin:-8px 0 22px}}
.sharebtn,.sharebtn2{{font:600 12.5px Inter,sans-serif;text-decoration:none;border-radius:8px;padding:8px 13px;cursor:pointer;border:1px solid var(--red)}}
.sharebtn{{color:#fff;background:var(--red)}}.sharebtn:hover{{background:#c52d06}}
.sharebtn2{{color:var(--red);background:var(--surface)}}.sharebtn2:hover{{background:var(--tint)}}.sharebtn2.ok{{color:#fff;background:#16794a;border-color:#16794a}}
</style></head><body><div class="wrap">
<div class="brandbar"><span class="bubble"></span><span class="logo">my<span>AskAI</span></span>
<span class="kicker">Help Centre AI-Readiness Audit</span></div>
<h1>{esc(kb)}</h1>
<div class="sub">{d['article_count']} articles checked · {d['generated'][:16].replace('T',' ')}</div>
<div class="intro">An AI support agent reads your help centre <b>one article at a time, with no memory between answers</b>.
It can't scroll past intro text, click "see also", read a screenshot, or tell which article is current.
This audit grades every article on the 13 things that decide whether the AI can answer from it, then can
rewrite the ones you choose in your own voice. <b>A red mark is an issue worth fixing.</b> Hover anything for detail.</div>
<div class="sharebar"><a class="sharebtn" href="scorecard.html" target="_blank">📊 Open shareable scorecard</a>
<button class="sharebtn2" id="sharecopy" type="button">Copy score summary</button></div>
<div class="cards">
 <div class="card"><div class="big {('gf' if d['overall_grade'][0] in 'DF' else '')}">{d['overall_grade']}</div><div class="lbl">Help centre grade · {d['overall_pct']}% of checks pass</div></div>
 <div class="card alert"><div class="big">{needfix}</div><div class="lbl">Articles worth fixing</div></div>
 <div class="card"><div class="big">{d['article_count']-needfix}</div><div class="lbl">Already clean</div></div>
 <div class="card"><div class="big">{min(roll.items(),key=lambda kv:kv[1]['pass_pct'])[1]['pass_pct']}%</div><div class="lbl">Pass rate, weakest check</div></div>
</div>
<div class="sec"><h2>How your help centre scores, by question</h2>
<p class="hint">The 12 checks group into three questions about every article. Bars show the share of articles that pass.</p>
{blocks}</div>
<div class="sec"><h2>Fix these first</h2>
<p class="hint">Ranked by how busy the article is (reader votes) and how many issues it has. Hover any cell for the specific finding. Filter and search to work down your own list. In the <b>Rewrite</b> column, <b>View →</b> opens an already-rewritten article; <b>Optimize</b> hands Claude a ready-made instruction to rewrite that one next.</p>
<div class="filters">
 <input id="fq" type="search" placeholder="Search article titles…" aria-label="Search article titles">
 <select id="fg" aria-label="Filter by grade"><option value="">All grades</option><option value="F">F only</option><option value="D">D only</option><option value="C">C only</option><option value="B">B only</option><option value="A">A only</option><option value="DF">D &amp; F</option></select>
 <select id="fp" aria-label="Filter by priority"><option value="">All priorities</option><option value="veryhigh">Very high</option><option value="high">High</option><option value="medium">Medium</option><option value="low">Low</option><option value="verylow">Very low</option></select>
 <select id="ff" aria-label="Filter by issues"><option value="">All articles</option><option value="needfix">Has issues to fix</option><option value="clean">Already clean</option></select>
 {('<select id="fr" aria-label="Filter by rewrite"><option value="">Rewrite: any</option><option value="1">Has updated article</option></select>' if n_rw else '')}
 <span class="fcount" id="fcount"></span>
</div>
<table id="ftable"><thead><tr><th>#</th><th style="text-align:left">Article</th><th>Rewrite</th><th>Grade</th><th>Priority to fix</th><th>Votes</th>{heads}</tr></thead>
<tbody id="fbody">{rows}<tr class="emptyrow hide" id="femptyrow"><td colspan="{6+len(order)}">No articles match these filters.</td></tr></tbody></table>
<div class="legend">✓ passes · <b class="f">✕ worth fixing</b> · – not applicable.</div></div>
<div class="sec"><h2>Your house style</h2>
<p class="hint">Derived from your own articles so rewrites keep your voice (the audit scores structure objectively — style never affects the grade). <b>Edit it to taste</b> — your changes save in this browser and are used whenever you click <b>Optimize</b>.</p>
<textarea id="housestyle" class="hsedit" rows="4" aria-label="House style">{esc(sp['descriptor'])}</textarea>
<div class="hsrow"><button id="hsreset" class="hsbtn" type="button">Reset to derived</button><span id="hssaved" class="hssaved"></span>
<span class="hsstats">{esc(style_stats)}</span></div></div>
<div class="foot">Every fix works with any AI agent or helpdesk. Keeping a help centre AI-ready over time is what
<a href="https://myaskai.com" target="_blank">myAskAI</a> does automatically.</div>
</div>
<div id="toast" class="toast" role="status" aria-live="polite"></div>
<script>
(function(){{
  var body=document.getElementById('fbody');
  var rowsAll=body?Array.prototype.slice.call(body.querySelectorAll('tr')).filter(function(r){{return !r.classList.contains('emptyrow')}}):[];
  var empty=document.getElementById('femptyrow');
  var q=document.getElementById('fq'),g=document.getElementById('fg'),p=document.getElementById('fp'),f=document.getElementById('ff'),rw=document.getElementById('fr'),cnt=document.getElementById('fcount');
  function apply(){{
    var qt=(q.value||'').trim().toLowerCase(),gv=g.value,pv=p.value,fv=f.value,rv=rw?rw.value:'',shown=0;
    rowsAll.forEach(function(r){{
      var ok=true;
      if(qt && r.getAttribute('data-title').indexOf(qt)<0) ok=false;
      if(ok && gv){{ var gr=r.getAttribute('data-grade'); ok=(gv.length>1)?gv.indexOf(gr)>=0:gr===gv; }}
      if(ok && pv && r.getAttribute('data-pri')!==pv) ok=false;
      if(ok && fv){{ var fx=parseInt(r.getAttribute('data-fixes'),10)||0; if(fv==='needfix'&&fx<=0)ok=false; if(fv==='clean'&&fx>0)ok=false; }}
      if(ok && rv==='1' && r.getAttribute('data-rw')!=='1') ok=false;
      r.classList.toggle('hide',!ok); if(ok)shown++;
    }});
    if(empty) empty.classList.toggle('hide',shown!==0);
    if(cnt) cnt.textContent=shown+' of '+rowsAll.length+' articles';
  }}
  [q,g,p,f,rw].forEach(function(el){{ if(el){{ el.addEventListener('input',apply); el.addEventListener('change',apply); }} }});
  apply();

  // ---- "Optimize" : send a ready-made rewrite instruction back to Claude ----
  var KB={kb_js}, DESC={desc_js}, SHARE={share_js};
  function toast(msg){{ var t=document.getElementById('toast'); if(!t)return; t.textContent=msg; t.classList.add('show'); clearTimeout(t._h); t._h=setTimeout(function(){{t.classList.remove('show');}},3600); }}

  // ---- editable house style (saved per-KB in this browser; used by Optimize) ----
  var HSKEY='kbaudit_hs_'+KB, hs=document.getElementById('housestyle'), saved=document.getElementById('hssaved'), reset=document.getElementById('hsreset');
  function flagSaved(m){{ if(!saved)return; saved.textContent=m; saved.classList.add('show'); clearTimeout(saved._h); saved._h=setTimeout(function(){{saved.classList.remove('show');}},1400); }}
  if(hs){{
    try{{ var v=localStorage.getItem(HSKEY); if(v!=null) hs.value=v; }}catch(e){{}}
    hs.addEventListener('input',function(){{ try{{localStorage.setItem(HSKEY,hs.value);}}catch(e){{}} flagSaved('Saved ✓'); }});
    if(reset) reset.addEventListener('click',function(){{ hs.value=DESC; try{{localStorage.removeItem(HSKEY);}}catch(e){{}} flagSaved('Reset'); }});
  }}
  function houseStyle(){{ return (hs&&hs.value.trim())||DESC; }}

  // ---- share score summary ----
  var sc=document.getElementById('sharecopy');
  if(sc) sc.addEventListener('click',function(){{
    function done(){{ sc.textContent='Copied ✓'; sc.classList.add('ok'); setTimeout(function(){{sc.textContent='Copy score summary';sc.classList.remove('ok');}},1900); toast('Score summary copied — share it anywhere.'); }}
    if(navigator.clipboard&&navigator.clipboard.writeText){{ navigator.clipboard.writeText(SHARE).then(done,done); }}
    else {{ var ta=document.createElement('textarea'); ta.value=SHARE; ta.style.position='fixed'; ta.style.opacity='0'; document.body.appendChild(ta); ta.select(); try{{document.execCommand('copy');}}catch(e){{}} document.body.removeChild(ta); done(); }}
  }});

  function buildPrompt(title,url){{
    return 'Using the kb-ai-audit skill, optimise the '+KB+' help centre article "'+title+'" ('+url+') for AI-agent readiness: '
      +'produce the complete, paste-ready rewrite, split it if it covers more than one question, carry over its original images and videos, '
      +'use ONLY facts present in the source article (never invent specs, steps, numbers, button names, URLs or policies — flag any gap with [VERIFY] instead of guessing), '
      +'add it (and any splits) to rewrites.json, then regenerate the dashboard and per-article pages. '
      +'Match this house style exactly: '+houseStyle();
  }}
  Array.prototype.forEach.call(document.querySelectorAll('.optbtn'),function(b){{
    b.addEventListener('click',function(){{
      var prompt=buildPrompt(b.getAttribute('data-title'),b.getAttribute('data-url'));
      if(typeof window.sendPrompt==='function'){{ try{{ window.sendPrompt(prompt); b.textContent='Sent ✓'; b.classList.add('ok'); toast('Sent to Claude — generating this rewrite.'); return; }}catch(e){{}} }}
      function done(){{ b.textContent='Copied ✓'; b.classList.add('ok'); setTimeout(function(){{b.textContent='Optimize';b.classList.remove('ok');}},2000); toast('Instruction copied — paste it into Claude Code to generate this rewrite.'); }}
      if(navigator.clipboard&&navigator.clipboard.writeText){{ navigator.clipboard.writeText(prompt).then(done,done); }}
      else {{ var ta=document.createElement('textarea'); ta.value=prompt; ta.style.position='fixed'; ta.style.opacity='0'; document.body.appendChild(ta); ta.select(); try{{document.execCommand('copy');}}catch(e){{}} document.body.removeChild(ta); done(); }}
    }});
  }});
}})();
</script>
</body></html>"""
    Path(path).write_text(doc)

# ---------------- shareable scorecard ----------------
def build_scorecard(d, kb, path, B):
    """A self-contained, share-ready score card (1200x630, OG-sized) — screenshot or open to share."""
    roll=d["pattern_rollup"]; gradetop=d["overall_grade"]; pct=d["overall_pct"]; n=d["article_count"]
    needfix=sum(1 for a in d["results"] if a["fixes"]>0)
    weakest=sorted(roll.items(), key=lambda kv: kv[1]["pass_pct"])[:3]
    gf = gradetop[0] in "DF"
    gaps="".join(
        f'<div class="gap"><span class="gn">{esc(v["short"])}</span>'
        f'<span class="gt"><i style="width:{max(v["pass_pct"],3)}%"></i></span>'
        f'<span class="gv">{v["pass_pct"]}%</span></div>'
        for k,v in weakest)
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(kb)} — AI-Readiness score</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">
<style>
:root{{--red:{B['red']};--tint:{B['red_tint']};--ink:{B['ink']};--ink2:{B['ink2']};--surface:{B['surface']};--muted:{B['muted']};--line:{B['line']}}}
*{{box-sizing:border-box}}
body{{margin:0;min-height:100vh;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:14px;
background:#ECECEC;padding:24px;font-family:Inter,-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;color:var(--ink)}}
.card{{width:1200px;max-width:100%;aspect-ratio:1200/630;background:var(--surface);border:1px solid var(--line);
border-radius:22px;box-shadow:0 18px 60px rgba(0,0,0,.14);padding:54px 60px;display:flex;flex-direction:column;overflow:hidden}}
.top{{display:flex;align-items:center;gap:11px}}
.bubble{{width:30px;height:24px;background:var(--red);border-radius:8px 8px 8px 3px;position:relative;flex:none}}
.bubble:after{{content:"";position:absolute;left:7px;bottom:-5px;width:9px;height:9px;background:var(--red);clip-path:polygon(0 0,100% 0,0 100%)}}
.logo{{font-weight:900;font-size:23px;letter-spacing:-.02em}}.logo span{{color:var(--ink2);font-weight:500}}
.kick{{margin-left:auto;color:var(--ink2);font-size:15px;font-weight:600;text-transform:uppercase;letter-spacing:.1em}}
.mid{{flex:1;display:flex;align-items:center;gap:48px;margin-top:8px}}
.gradebox{{flex:none;width:280px;height:280px;border-radius:28px;background:{('var(--tint)' if gf else 'var(--muted)')};
border:2px solid {('var(--red)' if gf else 'var(--line)')};display:flex;flex-direction:column;align-items:center;justify-content:center}}
.grade{{font-size:150px;font-weight:900;line-height:.9;letter-spacing:-.04em;color:{('var(--red)' if gf else 'var(--ink)')}}}
.gradelbl{{font-size:15px;font-weight:700;color:var(--ink2);text-transform:uppercase;letter-spacing:.12em;margin-top:8px}}
.info{{flex:1;min-width:0}}
.kbname{{font-size:40px;font-weight:800;letter-spacing:-.02em;line-height:1.05;margin:0 0 4px}}
.subt{{color:var(--ink2);font-size:18px;margin-bottom:20px}}
.stats{{display:flex;gap:30px;margin-bottom:22px}}
.stat .v{{font-size:32px;font-weight:800;letter-spacing:-.02em}}.stat .v.gf{{color:var(--red)}}
.stat .l{{color:var(--ink2);font-size:13.5px}}
.gaps .gh{{font-size:13px;font-weight:700;color:var(--ink2);text-transform:uppercase;letter-spacing:.08em;margin-bottom:9px}}
.gap{{display:grid;grid-template-columns:190px 1fr 44px;align-items:center;gap:12px;margin:6px 0}}
.gn{{font-size:14px}}.gt{{height:9px;background:var(--muted);border:1px solid var(--line);border-radius:4px;overflow:hidden}}
.gt i{{display:block;height:100%;background:var(--ink)}}.gv{{text-align:right;font-weight:700;font-variant-numeric:tabular-nums;font-size:14px}}
.foot{{display:flex;align-items:center;margin-top:auto;padding-top:18px;border-top:1px solid var(--line);color:var(--ink2);font-size:14px}}
.foot b{{color:var(--ink)}}.foot .r{{margin-left:auto;color:var(--red);font-weight:700}}
.hint{{color:#8a8a8a;font-size:13px}}
@media (max-width:680px){{.card{{padding:30px 26px}}.mid{{flex-direction:column;align-items:flex-start;gap:22px}}.gradebox{{width:170px;height:170px}}.grade{{font-size:92px}}.kbname{{font-size:28px}}.gap{{grid-template-columns:130px 1fr 40px}}}}
</style></head><body>
<div class="card">
  <div class="top"><span class="bubble"></span><span class="logo">my<span>AskAI</span></span>
    <span class="kick">Help Centre AI-Readiness</span></div>
  <div class="mid">
    <div class="gradebox"><div class="grade">{esc(gradetop)}</div><div class="gradelbl">Overall grade</div></div>
    <div class="info">
      <h1 class="kbname">{esc(kb)}</h1>
      <div class="subt">How ready this help centre is for an AI support agent to answer from</div>
      <div class="stats">
        <div class="stat"><div class="v {('gf' if gf else '')}">{pct}%</div><div class="l">of checks pass</div></div>
        <div class="stat"><div class="v">{n}</div><div class="l">articles audited</div></div>
        <div class="stat"><div class="v">{needfix}</div><div class="l">worth fixing</div></div>
      </div>
      <div class="gaps"><div class="gh">Biggest gaps</div>{gaps}</div>
    </div>
  </div>
  <div class="foot"><b>{d['generated'][:10]}</b>&nbsp;· 13-check AI-readiness audit<span class="r">myaskai.com</span></div>
</div>
<div class="hint">Screenshot this card, or right-click → Save, to share your score.</div>
</body></html>"""

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("results")
    ap.add_argument("--kb-name",default="Help Centre"); ap.add_argument("--outdir",default=".")
    ap.add_argument("--rewrites",default=None,
                    help="Optional rewrites.json (list of finished articles) to embed in the dashboard "
                         "with per-article Copy buttons.")
    a=ap.parse_args()
    d=json.loads(Path(a.results).read_text()); out=Path(a.outdir); out.mkdir(parents=True,exist_ok=True)
    # build_outputs owns the non-HTML deliverables; build_branded.py owns dashboard.html / scorecard.html /
    # per-article pages (running both, in either order, no longer clobbers the branded HTML surfaces).
    (out/"exec_summary.md").write_text(exec_summary(d,a.kb_name))
    build_xlsx(d,out/"audit_tracker.xlsx")
    print("Wrote exec_summary.md, audit_tracker.xlsx")

if __name__=="__main__": main()

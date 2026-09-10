#!/usr/bin/env python3
"""
kb_audit.py - Help-center AI-readiness auditor (deterministic triage layer).

Scores every help article against 13 plain-language checks that decide whether an AI
support agent can actually answer from it. All wording is written for a CS/CX leader -
no technical jargon about how the AI works under the hood.

Two help-center-wide passes:
  - conflicting-duplicates detection (CHK_DUP)
  - house style / tone-of-voice profile (feeds rewrites, never affects scoring)

Outputs results.json. Stdlib only. No network.
"""
import json, re, sys, html, datetime, statistics, collections, argparse
from pathlib import Path

TODAY = datetime.date.today()

# ---- the three plain-language questions every article has to pass ----
G_FIND = "Can the AI find the right answer?"
G_USE  = "Can the AI use the answer?"
G_TRUST= "Is it the right, current answer?"

CHK_ONE   = "One question per article"
CHK_WORDS = "Worded the way customers ask"
CHK_SCOPE = "Says who and where it applies"
CHK_FIRST = "Answer first, and each part stands alone"
CHK_FULL  = "Answer written out, not behind a link or tab"
CHK_JARG  = "Explains acronyms and product names"
CHK_CASE  = "Keeps every case in one place"
CHK_VIS   = "Spells out images, video and tables in words"
CHK_FIX   = "Gives the actual fix, with anything needed first"
CHK_ESC   = "Says what to do if it doesn't work"
CHK_LIMITS= "Says what it doesn't cover or isn't possible"
CHK_FRESH = "Dated and current"
CHK_DUP   = "No conflicting duplicates"

# meta: (group, why-it-matters [jargon-free], short label, importance weight)
PATTERN_META = {
 CHK_ONE:  (G_FIND, "An AI answers from one article at a time, so a page that bundles several questions together can serve up the wrong part.", "One question", 3),
 CHK_WORDS:(G_FIND, "The AI looks for the customer's own words - the symptom, the exact error message, the button name. If the article only uses internal or feature names, it won't be matched.", "Customer words", 3),
 CHK_SCOPE:(G_FIND, "Without a line saying who, which device or which plan it's for, the AI gives the wrong audience's answer.", "Who it's for", 2),
 CHK_FIRST:(G_USE,  "The AI reads a section on its own. Bury the answer under intro text, or lean on 'as mentioned above', and the section is no use by itself.", "Answer first", 3),
 CHK_FULL: (G_USE,  "Anything hidden behind 'click here', a drop-down or a 'read more' tab often isn't picked up at all, so the AI can't give it.", "Written out", 3),
 CHK_JARG: (G_USE,  "The AI doesn't know your in-house terms. Left unexplained, it repeats them back and the customer is none the wiser.", "Explains jargon", 1),
 CHK_CASE: (G_USE,  "'If you're in the EU, see the other article' is a gamble. Spell out each case - region, device, plan - right where the customer is.", "Cases together", 2),
 CHK_VIS:  (G_USE,  "An AI can't read a screenshot, a video or a table grid. If a step only exists in an image, the AI can't pass it on.", "Not just images", 2),
 CHK_FIX:  (G_USE,  "The AI can only repeat what's written. An article that explains the cause but never the fix - or skips a step you need first - leaves the customer stuck.", "Gives the fix", 3),
 CHK_ESC:  (G_USE,  "Give the AI a safe next step - contact support, it's a hardware issue - so it doesn't loop or make something up.", "Next step", 1),
 CHK_LIMITS:(G_TRUST,"If an article never says 'this can't be done', the AI may invent a workaround. State limits and known issues plainly.", "States limits", 2),
 CHK_FRESH:(G_TRUST,"Nothing tells the AI an article is old, so it will quote last year's price or a finished promo as if it's live.", "Up to date", 2),
 CHK_DUP:  (G_TRUST,"When the same fact sits in several articles and they disagree, the AI can pick the wrong one.", "No clashes", 2),
}
ORDER = list(PATTERN_META.keys())

# ---------- HTML -> structured text ----------
TAG_RE=re.compile(r"<[^>]+>"); WS_RE=re.compile(r"[ \t]+")
def strip_tags(s):
    s=re.sub(r"<(script|style)[^>]*>.*?</\1>"," ",s,flags=re.S|re.I); s=TAG_RE.sub(" ",s)
    return WS_RE.sub(" ",html.unescape(s)).strip()
def get_headings(b):
    return [(int(m.group(1)),strip_tags(m.group(2))) for m in re.finditer(r"<h([1-6])[^>]*>(.*?)</h\1>",b,flags=re.S|re.I)]
def get_paragraphs(b):
    return [strip_tags(p) for p in re.findall(r"<p[^>]*>(.*?)</p>",b,flags=re.S|re.I) if strip_tags(p)]
def get_tables(b):
    return [len(re.findall(r"<tr",t,flags=re.I)) for t in re.findall(r"<table.*?</table>",b,flags=re.S|re.I)]
def count_visuals(b):
    imgs=re.findall(r"<img[^>]*>",b,flags=re.I)
    desc=sum(1 for im in imgs if (re.search(r'alt="([^"]+)"',im) and len(re.search(r'alt="([^"]+)"',im).group(1).strip())>3))
    vids=len(re.findall(r"(<iframe|youtube|data-oembed)",b,flags=re.I))
    return len(imgs),desc,vids
def extract_media(b):
    """Pull the actual images and video embeds out of the source article so the rewrite can
    carry them over verbatim (the copy includes them — the customer pastes once, done)."""
    out=[]
    for m in re.finditer(r"<img[^>]*>",b,flags=re.I):
        tag=m.group(0); src=re.search(r'src=["\']([^"\']+)["\']',tag); alt=re.search(r'alt=["\']([^"\']*)["\']',tag)
        if src: out.append({"type":"image","src":src.group(1),"alt":(alt.group(1).strip() if alt else "")})
    for m in re.finditer(r"<iframe[^>]*>.*?</iframe>|<iframe[^>]*/?>",b,flags=re.S|re.I):
        tag=m.group(0); src=re.search(r'src=["\']([^"\']+)["\']',tag)
        out.append({"type":"video","src":(src.group(1) if src else ""),"embed":WS_RE.sub(" ",tag.replace("\n"," ")).strip()})
    for m in re.finditer(r"<video[^>]*>.*?</video>",b,flags=re.S|re.I):
        out.append({"type":"video","src":"","embed":WS_RE.sub(" ",m.group(0).replace("\n"," ")).strip()})
    return out
def sentences(t): return [s.strip() for s in re.split(r"(?<=[.!?])\s+",t) if s.strip()]

# Ways a help center actually names its audience up front. (Previously this carried the demo
# customer's own product names — "nature cam", "birdbuddy 2" — which no other customer can match.)
# Audience tokens — the things a scope line actually names.
_AUD=(r"(?:ios|android|iphone|ipad|desktop|mobile|web|browser|chrome|safari|firefox|edge|windows|macos|mac|linux|"
      r"free|pro|plus|team|business|starter|premium|enterprise|paid|trial|legacy|plan|tier|subscription|"
      r"admins?|owners?|members?|agents?|managers?|customers?|users?|accounts?|us|eu|uk|ca|au)")
# A scope DECLARATION, not a passing mention. Anchored to audience tokens so ordinary prose like
# "not available on items marked final sale" or "on Android you must also…" doesn't count.
# (Previously this also carried the demo customer's own product names — "nature cam", "birdbuddy 2".)
SCOPE_RE=re.compile(r"\b(?:"
 r"(?:applies?|applicable|apply) to\b|"
 r"this (?:article|guide|page) is (?:for|about who)|intended for\b|relevant (?:to|for)\b|who (?:this|it)(?:'s| is) for|"
 r"available (?:on|in|to|for) "+_AUD+r"|only available\b|"
 r"(?:ios|android|desktop|mobile|web|browser|windows|mac|linux)(?:[ -]and[ -]\w+)? only\b|"
 r"(?:free|pro|plus|team|business|starter|premium|enterprise|paid|trial|legacy) (?:plan|tier|accounts?|users?|subscriptions?)\b|"
 r"(?:admins?|owners?|members?|agents?|managers?) (?:only|can)\b|"
 r"requires? (?:a|an|the) \w+ (?:plan|account|subscription|role|permission)\b|"
 r"for (?:us|eu|uk|ca|au) (?:customers|users|accounts)\b|"
 r"version \d|v\d\.\d"
 r")",re.I)
# Does anything here actually VARY by audience? If the article never mentions a platform, plan,
# region or role, there is no scope to state and demanding one is a false positive.
SCOPE_DEP_RE=re.compile(r"\b(ios|android|iphone|ipad|desktop app|mobile app|browser|chrome|safari|firefox|windows|macos|linux|"
 r"app store|google play|free plan|pro plan|paid plan|premium|enterprise|subscription tier|"
 r"admin|owner|permission|role|region|country)\b",re.I)
NEGBOUND_RE=re.compile(r"(this (article|guide) (doesn'?t|does not) cover|not covered (here|in this)|if you'?re looking for)",re.I)
LIMIT_RE=re.compile(r"\b(not supported|isn'?t possible|is not possible|cannot|can'?t be|can'?t currently|not available|"
 r"no longer|not currently|unable to|doesn'?t support|don'?t support|won'?t be able|only available|not eligible|not able to|"
 r"not include|doesn'?t include|excludes?|except( for)?|unless|limited to|limits? of|maximum( of)?|max(imum)? \d|up to \d|"
 r"at (most|this time)|only (works|applies|possible|supports?)|must be|requires?|not possible to|there is no way|"
 r"keep in mind|please note|note that|be aware)\b",re.I)
# Articles where "can this be done?" is a live customer question — how-tos, troubleshooting and
# policy pages. A short reference or announcement has no limits to state; failing it is noise.
POLICY_RE=re.compile(r"\b(refund|billing|payment|invoice|subscription|cancel|plan|pricing|price|upgrade|downgrade|"
 r"policy|terms|privacy|data|delete|deletion|eligib|warrant|return|shipping|deliver|security|compliance)\b",re.I)
CLICKHERE_RE=re.compile(r"\b(click here|tap here|see here|read here|consult this article|refer to (our|this|the)|see (our|this|the) .{0,30}(article|guide|page))\b",re.I)
HIDDEN_RE=re.compile(r"(<details|class=\"[^\"]*(accordion|collaps|toggle|spoiler|tab-pane|tabs?-)|read more|show more|expand)",re.I)
BAREYN_RE=re.compile(r"<p[^>]*>\s*(<strong>)?\s*(A[:.]\s*)?(Yes|No)[.!]?\s*(</strong>)?\s*</p>",re.I)
QWORD_RE=re.compile(r"\b(how do i|how to|how can|can i|what is|what are|where (is|do)|why (is|do|won'?t|can'?t)|when (will|does)|unable to|do i need|i can'?t)\b",re.I)
PROBLEM_RE=re.compile(r"\b(error|issue|can'?t|cannot|unable|won'?t|not working|troubleshoot|fix|problem|fail|offline|why|stuck|won't connect|won't pair)\b",re.I)
STEP_RE=re.compile(r"\b(tap|press|click|go to|select|open|charge|restart|reset|enter|download|install|update|remove|reinsert|hold|plug|turn (on|off)|allow|connect|navigate|choose|swipe|insert)\b",re.I)
ESC_RE=re.compile(r"(contact (support|us)|start a chat|reach out|submit a ticket|get in touch|let us know|@\w+\.(com|gd)|dis\.gd|if .{0,40}(persist|doesn'?t work|still (not|won'?t)|isn'?t))",re.I)
BACKREF_RE=re.compile(r"\b(as (mentioned|described|noted|shown|explained) above|see above|the above|as above|earlier in this article|previously mentioned)\b",re.I)
QUOTED_RE=re.compile(r"[\"“‘']([A-Za-z][^\"”’']{3,40})[\"”’']")
DATE_RE=re.compile(r"\b(20[12]\d)\b")
SINCE_DATE_RE=re.compile(r"since\s+\w*\s*20[12]\d",re.I)
ACRO_RE=re.compile(r"\b([A-Z]{2,6}(?:s)?)\b")
ACRO_STOP={"FAQ","FAQS","US","UK","EU","PST","PDT","PT","AM","PM","HD","QR","OS","ID","DM","DMS","URL","API","TOC","NOTE","Q","A","SKU","SKUS","USB","LED","AI","II","TV","X","BUDDY","OK","PDF"}
DEP_RE=re.compile(r"\b(no longer supported|deprecated|retired|expired|discontinued|sunset|legacy)\b",re.I)
# Genuinely time-bound content only. "version", "update" and "cost" appear in a huge share of
# ordinary articles ("update the app", "at no cost"), which made nearly everything time-sensitive
# and therefore demand a "last verified" line.
TIME_RE=re.compile(r"\b(promo|promotion|pricing|price of|\$\d|trial period|special offer|limited time|"
 r"event|seasonal|deadline|expires?|expiry|firmware \d|black friday|christmas|holiday hours|"
 r"beta|early access|coming soon|launch(ing|es)? (on|in)|as of \w+ 20\d\d)\b",re.I)

UPDATED_MAX_DAYS=548  # ~18 months: the help center itself is showing a recent last-updated date
def updated_age_days(v):
    """Days since the platform's own updated_at, or None if absent/unparseable.

    Zendesk/Intercom/Freshdesk all return this and the help center displays it to readers, so it
    is a real freshness anchor — it was being captured into results.json and then ignored.
    """
    if not v: return None
    m=re.search(r"(\d{4})-(\d{2})-(\d{2})",str(v))
    if not m: return None
    try: return (TODAY-datetime.date(int(m.group(1)),int(m.group(2)),int(m.group(3)))).days
    except ValueError: return None

def first_block(b,n=260):
    ps=get_paragraphs(b); intro=ps[0] if ps else strip_tags(b); return intro[:n],intro

def check_article(a):
    body=a.get("body","") or ""; title=a.get("title","") or ""
    text=strip_tags(body); wc=len(text.split())
    heads=get_headings(body); htop=[h for lvl,h in heads if lvl<=2 and not re.search(r"frequently asked|faq|in this article",h,re.I)]
    paras=get_paragraphs(body); tables=get_tables(body)
    n_img,n_desc,n_vid=count_visuals(body); head80,intro=first_block(body)
    labels=" ".join(a.get("label_names",[]))
    problem=bool(PROBLEM_RE.search(title+" "+labels)); howto=bool(re.search(r"\bhow\b|set up|pair|connect|change|create|install",title,re.I))
    actionable=problem or howto or bool(re.search(r"<ol|<li",body)) or bool(STEP_RE.search(text))
    res={}
    def R(v,note,llm=False): return {"verdict":v,"note":note,"llm_confirm":llm}

    # 1 One question per article
    sig=[]
    if re.search(r"\b(and|&|/)\b",title) and len(title.split())>3: sig.append("broad title")
    nsec=len(set(htop))
    if nsec>=4: sig.append(f"{nsec} separate sections")
    if wc>1000: sig.append(f"{wc} words")
    fix1 = (nsec>=4) or ("broad title" in sig and nsec>=3) or wc>1100
    res[CHK_ONE]=R("Fix" if fix1 else "Pass",("Covers several questions: "+"; ".join(sig)) if fix1 else "Single focused question.")

    # 2 Worded the way customers ask  (question phrasing + plain headings + exact error/button text)
    hasq=bool(QWORD_RE.search(text)) or "?" in text or bool(QWORD_RE.search(title))
    jargon_heads=[h for lvl,h in heads for ac in ACRO_RE.findall(h) if ac.upper() not in ACRO_STOP]
    needs_quote = problem and not QUOTED_RE.search(body)
    notes=[]
    if not hasq: notes.append("no customer-style question in the title or body")
    if jargon_heads: notes.append("internal terms in headings ("+jargon_heads[0]+")")
    if needs_quote: notes.append("a problem article with no exact error text in quotes")
    res[CHK_WORDS]=R("Fix" if notes else "Pass","; ".join(notes) if notes else "Uses the customer's own words.",llm=True)

    # 3 Scope — only demanded where the answer actually varies by audience
    top=" ".join([intro]+paras[:3]+[h for _,h in heads[:4]])
    scope=bool(SCOPE_RE.search(top))
    if not scope and not SCOPE_DEP_RE.search(text):
        # Nothing here differs by platform, plan, region or role, so there is no scope to state.
        res[CHK_SCOPE]=R("N/A","Applies to everyone — nothing in it varies by device, plan or region.")
    else:
        res[CHK_SCOPE]=R("Pass" if scope else "Fix","Scope named near the top." if scope
                         else "Mentions a device/plan/region, but no 'who this is for' line near the top.")

    # 4 Answer first + stands alone
    answer=bool(re.search(r"\b(you can|to (do|start|claim|change|enable|cancel|charge|pair|reset|fix|connect)|tap|press|go to|click|select|yes|no|download|open|first|\d)\b",head80,re.I))
    preamble=bool(re.search(r"^(at \w+|another year|we('re| are)? (happy|believe)|calling all|welcome|the \w+ app is|updating your)",intro.strip(),re.I)) or (not answer)
    backref=bool(BACKREF_RE.search(text)); n4=[]
    if preamble: n4.append("opens with intro/brand copy, not the answer")
    if backref: n4.append("relies on 'as above'-style back-references")
    res[CHK_FIRST]=R("Fix" if n4 else "Pass","; ".join(n4) if n4 else "Leads with the answer; sections stand alone.",llm=True)

    # 5 Written out (not behind link/tab/click-here)
    n5=[]
    if BAREYN_RE.search(body): n5.append("a bare Yes/No answer")
    if CLICKHERE_RE.search(body): n5.append("vague links like 'click here' / 'see our guide'")
    if HIDDEN_RE.search(body): n5.append("content hidden in a tab/drop-down/'read more'")
    res[CHK_FULL]=R("Fix" if n5 else "Pass","Contains "+"; ".join(n5) if n5 else "Answer is written out in full.")

    # 6 Acronyms
    undef=[ac for ac in set(ACRO_RE.findall(text)) if ac.upper() not in ACRO_STOP
           and not re.search(r"\([^)]*\b"+re.escape(ac)+r"\b[^)]*\)",text) and not re.search(re.escape(ac)+r"\s*\([A-Za-z]",text)]
    res[CHK_JARG]=R("Fix" if undef else "Pass",("Used but never explained: "+", ".join(sorted(undef)[:5])) if undef else "Acronyms explained on first use.",llm=True)

    # 7 Cases together
    cross=re.findall(r"(if you'?re? .{0,40}(see|click|visit|check|refer)|for .{0,30}\b(see|visit)\b)",text,re.I)
    res[CHK_CASE]=R("Fix" if cross else "Pass",f"{len(cross)} case(s) sent to another article instead of answered here." if cross else "Each case answered in place.",llm=True)

    # 8 Visuals - only count images/video against instructional articles
    n8=[]; big=[r for r in tables if r>3]
    if big: n8.append(f"{len(big)} table(s) over 3 rows")
    if actionable and n_img and (n_img-n_desc)>0: n8.append(f"{n_img-n_desc}/{n_img} image(s) with no text description")
    if actionable and n_vid: n8.append(f"{n_vid} video/embed(s) with steps only on screen")
    if not tables and not n_img and not n_vid: res[CHK_VIS]=R("N/A","No images, video or tables.")
    else: res[CHK_VIS]=R("Fix" if n8 else "Pass","; ".join(n8) if n8 else "Visuals are described in words.")

    # 9 Gives the actual fix (+ prerequisites)
    if not actionable: res[CHK_FIX]=R("N/A","Not a how-to or troubleshooting article.")
    else:
        steps=len(STEP_RE.findall(text))
        res[CHK_FIX]=R("Fix" if steps<2 else "Pass",
                       "Describes the situation but gives few clear actions to take." if steps<2 else "Gives concrete steps.",llm=True)

    # 10 Escalation / next step
    if not actionable: res[CHK_ESC]=R("N/A","Not a how-to or troubleshooting article.")
    else:
        esc=bool(ESC_RE.search(text))
        res[CHK_ESC]=R("Pass" if esc else "Fix","Gives a next step if it fails." if esc else "No fallback - nothing to do if the steps don't work.")

    # 11 Limits / what it doesn't cover — only where "can this be done?" is a live question
    lim=bool(NEGBOUND_RE.search(text)) or bool(LIMIT_RE.search(text))
    limits_matter=actionable or bool(POLICY_RE.search(title+" "+labels+" "+text))
    if not lim and not limits_matter:
        res[CHK_LIMITS]=R("N/A","Short reference article — no capability or policy boundary to state.")
    else:
        res[CHK_LIMITS]=R("Pass" if lim else "Fix","States limits / what it doesn't cover." if lim
                          else "Never says what it doesn't cover or what isn't possible.")

    # 12 Freshness
    # An explicit in-body date, OR the platform's own recent last-updated stamp, anchors freshness.
    age=updated_age_days(a.get("updated_at"))
    fresh=bool(re.search(r"\b(last (verified|updated|reviewed)|as of)\b",text,re.I)) or (age is not None and age<=UPDATED_MAX_DAYS)
    # past years, but ignore "since YYYY" history (e.g. "since 2015") - that's not staleness
    stale=[y for y in sorted({int(x) for x in DATE_RE.findall(text) if int(x)<TODAY.year})
           if not re.search(r"since\s+\w*\s*"+str(y),text,re.I)]
    ts=bool(TIME_RE.search(text)) or bool(TIME_RE.search(labels)); dep=bool(DEP_RE.search(text)); n12=[]
    if not fresh: n12.append("no 'last verified' date" if age is None else f"last updated {age//30} months ago")
    if stale: n12.append("past dates: "+",".join(map(str,stale)))
    v12="Pass"
    if (ts or dep) and (not fresh or stale): v12="Fix"
    elif not fresh and stale: v12="Fix"
    res[CHK_FRESH]=R(v12,"; ".join(n12) if n12 else "Freshness is anchored.")

    # 13 set by corpus pass
    res[CHK_DUP]=R("Pass","(set by corpus pass)")
    return {"id":a.get("id"),"title":title,"url":a.get("html_url"),"word_count":wc,"headings":len(heads),
            "images":n_img,"videos":n_vid,"tables":len(tables),"media":extract_media(body),
            "vote_count":a.get("vote_count",0),
            "updated_at":a.get("updated_at"),"section_id":a.get("section_id"),
            "checks":res,"_text":text,"_intro":intro}

def corpus_duplicates(results):
    norm=lambda s:re.sub(r"[^a-z0-9 ]","",s.lower()).strip()
    idx=collections.defaultdict(list)
    for i,r in enumerate(results):
        for s in sentences(r["_text"]):
            if len(s.split())<8: continue
            k=norm(s)
            if len(k)<30: continue
            idx[k].append(i)
    dup=collections.defaultdict(set)
    for k,his in idx.items():
        arts=sorted(set(his))
        if len(arts)>=2:
            for i in arts:
                for j in arts:
                    if i!=j: dup[i].add(results[j]["title"])
    for i,r in enumerate(results):
        if i in dup:
            r["checks"][CHK_DUP]={"verdict":"Fix","note":"Shares wording with: "+", ".join(sorted(dup[i])[:3]),"llm_confirm":False}

ENCOURAGE_RE=re.compile(r"\b(no worries|don'?t worry|happy to|we're here|here to help|great news|good news|"
                        r"feathery friends|easy|simply|just|that's it|you're all set|in no time)\b",re.I)
CONTR_RE=re.compile(r"\b\w+'(s|re|ll|ve|t|d|m)\b",re.I)
EMOJI_RE=re.compile("[\U0001F300-\U0001FAFF☀-➿✂-➰]")

# ================= corpus-wide coherence layer =================
# Five help-center-wide passes that look BETWEEN and ACROSS articles (the 13 checks
# only see one article at a time). Deterministic candidate-finders; the judgment-heavy
# ones (contradiction, collision, disambiguation) carry needs_confirm so the skill flow
# can confirm them on the priority set before they're shown. Findings fold into the
# existing per-article checks so they affect the grade:
#   contradictions + near-duplicates -> CHK_DUP   stale-dated -> CHK_FRESH   confusable names -> CHK_JARG
# Coverage gaps are KB-level (no article to attach a grade to).
import difflib
STOP=set(("a an the and or but if then else for to of in on at by with from as is are was were be been "
 "being this that these those it its it's you your you'll you're we our ours they their them he she his "
 "her do does did has have had can could will would should may might must not no nor so than too very just "
 "into over under out up down off about above below again here there when where which who whom what why how "
 "all any both each few more most other some such only own same s t now also get got use using need").split())
def toks(t): return [w for w in re.findall(r"[a-z0-9][a-z0-9'+-]*",t.lower()) if len(w)>2 and w not in STOP]
def tf(ws): return collections.Counter(ws)
def cosine(a,b):
    common=set(a)&set(b)
    if not common: return 0.0
    dot=sum(a[w]*b[w] for w in common)
    na=sum(v*v for v in a.values())**0.5; nb=sum(v*v for v in b.values())**0.5
    return dot/(na*nb) if na and nb else 0.0
def article_vectors(results): return [tf(toks(r["title"]+" "+r["_text"])) for r in results]

def _fold(check,note):
    """Set an existing per-article check to Fix (or append evidence) so corpus findings affect the grade."""
    if check["verdict"]=="N/A": check["verdict"]="Fix"; check["note"]=note
    elif check["verdict"]!="Fix": check.update(verdict="Fix",note=note,llm_confirm=False)
    elif note not in check["note"]: check["note"]=check["note"].rstrip(". ")+". "+note

# complementary pairs that share boilerplate but are NOT duplicates (don't flag a merge)
ANTONYMS=[("send","receive"),("buy","sell"),("deposit","withdraw"),("deposit","withdrawal"),
 ("add","remove"),("enable","disable"),("open","close"),("create","delete"),("import","export"),
 ("lock","unlock"),("connect","disconnect"),("activate","deactivate"),("start","stop"),("login","logout")]
def corpus_collisions(results,vecs,thresh=0.7,cap=15):
    """Paraphrased near-duplicate articles competing for the same query (distinct from the literal CHK_DUP pass).
    Requires both high body overlap AND similar titles, and skips complementary (send/receive-style) pairs."""
    pairs=[]; n=len(results)
    tl=[set(toks(r["title"])) for r in results]
    for i in range(n):
        for j in range(i+1,n):
            sim=cosine(vecs[i],vecs[j])
            if sim<thresh: continue
            tr=difflib.SequenceMatcher(None,results[i]["title"].lower(),results[j]["title"].lower()).ratio()
            if tr<0.55: continue  # near-dups share a title shape; complementary how-tos don't
            if any((x in tl[i] and y in tl[j]) or (y in tl[i] and x in tl[j]) for x,y in ANTONYMS): continue
            shared=sorted(set(vecs[i])&set(vecs[j]),key=lambda w:-(vecs[i][w]+vecs[j][w]))[:6]
            pairs.append({"a":results[i]["title"],"b":results[j]["title"],"ai":i,"bi":j,
                          "a_url":results[i].get("url"),"b_url":results[j].get("url"),
                          "similarity":round(sim,2),"shared":shared,"needs_confirm":sim<0.8})
    pairs.sort(key=lambda p:-p["similarity"])
    by=collections.defaultdict(set)
    for p in pairs: by[p["ai"]].add(p["b"]); by[p["bi"]].add(p["a"])
    for i,others in by.items():
        _fold(results[i]["checks"][CHK_DUP],"Overlaps heavily with: "+", ".join(sorted(others)[:3])+" — the AI may pick the wrong one.")
    return pairs[:cap]

SUBJ_RE=re.compile(r"\b(refunds?|returns?|shipping|delivery|deliver(?:ed|y)?|trials?|warrant(?:y|ies)|"
 r"cancel(?:lation)?|charges?|charging|batter(?:y|ies)|payments?|invoices?|passwords?|replacements?|"
 r"exchanges?|subscriptions?|storage|resolution|range|warranty)\b",re.I)
UNIT_RE=re.compile(r"\b(\d+(?:\.\d+)?)\s*(business days?|days?|hours?|hrs?|weeks?|months?|years?|gb|mb|metres?|meters?|feet|ft|°?[cf])\b",re.I)
MONEY_RE=re.compile(r"[$£€]\s?(\d+(?:\.\d{1,2})?)")
PCT_RE=re.compile(r"(\d+(?:\.\d+)?)\s?%")
def _unit_key(u):
    u=u.lower().rstrip('s')
    return {"hr":"hour","business day":"day","metre":"meter","meter":"meter","ft":"feet","foot":"feet"}.get(u,u)
def _quant_facts(text):
    out={}
    for m in UNIT_RE.finditer(text):
        ctx=text[max(0,m.start()-60):m.end()+25]; s=SUBJ_RE.search(ctx)
        if s: out.setdefault((s.group(1).lower().rstrip('s'),_unit_key(m.group(2))),set()).add(m.group(1))
    for rx,unit in ((MONEY_RE,"money"),(PCT_RE,"percent")):
        for m in rx.finditer(text):
            ctx=text[max(0,m.start()-60):m.end()+25]; s=SUBJ_RE.search(ctx)
            if s: out.setdefault((s.group(1).lower().rstrip('s'),unit),set()).add(m.group(1))
    return out

def corpus_contradictions(results,vecs,topic_thresh=0.18):
    """Same subject stated with different facts (timeframe/price/percent/size) across two related articles."""
    facts=[_quant_facts(r["_text"]) for r in results]; found=[]; n=len(results)
    for i in range(n):
        if not facts[i]: continue
        for j in range(i+1,n):
            if not facts[j] or cosine(vecs[i],vecs[j])<topic_thresh: continue
            for key in set(facts[i])&set(facts[j]):
                vi,vj=facts[i][key],facts[j][key]
                if vi and vj and not (vi&vj):
                    subj,unit=key
                    found.append({"subject":subj,"unit":unit,"ai":i,"bi":j,
                                  "a":results[i]["title"],"b":results[j]["title"],
                                  "a_url":results[i].get("url"),"b_url":results[j].get("url"),
                                  "a_val":sorted(vi)[0],"b_val":sorted(vj)[0],"needs_confirm":True})
    for f in found:
        u="" if f["unit"] in("money","percent") else " "+f["unit"]+"s"
        ev=f"'{f['subject']}' is {f['a_val']}{u} in \"{f['a']}\" but {f['b_val']}{u} in \"{f['b']}\""
        _fold(results[f["ai"]]["checks"][CHK_DUP],"Possible conflict — "+ev+".")
        _fold(results[f["bi"]]["checks"][CHK_DUP],"Possible conflict — "+ev+".")
    return found

SUFFIX="2|3|4|II|III|IV|Pro|Plus|Lite|Max|Mini|Premium|Air|SE|Ultra|XL|v\\d+"
# structural / generic words that take a number but are NOT product names
NAME_STOP=set(("step steps scenario example part option phase method figure note section chapter "
 "question point stage round version tier level day week item case image photo table tip way reason "
 "factor type form field box page line row column option phase tab menu screen window page google "
 "method appendix attachment exhibit").split())
def corpus_disambiguation(results):
    """Confusable product / plan / feature names the KB never explicitly tells apart — chiefly a base
    name that also appears with a version/model suffix (the 'v1 vs v2' trap), plus near-identical names.
    The (?![\\w-]) guard rejects '2-Step'/'2FA'-style numbers that aren't real version suffixes."""
    variant=re.compile(r"\b([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)?)\s+("+SUFFIX+r")(?![\w-])")
    base_variants=collections.defaultdict(set); seen=collections.Counter()
    for r in results:
        hay=r["title"]+". "+r["_text"]
        for m in variant.finditer(hay):
            base=re.sub(r"^(the|your|a|an)\s+","",m.group(1).strip(),flags=re.I)
            if base.lower() in STOP or base.lower() in NAME_STOP or len(base)<4: continue
            base_variants[base].add(base+" "+m.group(2)); seen[base]+=1
    groups=[]
    for base,vars_ in base_variants.items():
        # confusable only if the bare base also appears on its own somewhere (so both v1 and v2 are in the KB)
        bare=any(re.search(r"\b"+re.escape(base)+r"\b(?!\s+("+SUFFIX+r"))",r["title"]+" "+r["_text"]) for r in results)
        names=sorted(({base} if bare else set())|vars_,key=str.lower)
        if len(names)>=2: groups.append(names)
    cue=re.compile(r"\b(difference between|vs\.?|versus|compared|which (one|model|plan|version)|"
                   r"not to be confused|whereas|(?:"+SUFFIX+r")\s+(?:vs|or)\b)",re.I)
    findings=[]
    for grp in groups:
        arts=[]
        for i,r in enumerate(results):
            hay=r["title"]+" "+r["_text"]
            hits=[g for g in grp if re.search(r"\b"+re.escape(g)+r"\b",hay)]
            if len(hits)>=2 and not cue.search(hay):
                arts.append({"title":r["title"],"url":r.get("url")}); _fold(results[i]["checks"][CHK_JARG],
                    "Mentions "+" & ".join(hits[:2])+" without saying which is which — the AI can conflate them.")
        if arts: findings.append({"names":grp,"articles":arts[:8],"count":len(arts),"needs_confirm":True})
    findings.sort(key=lambda f:-f["count"]); out=[]; seen=set()  # dedupe case-variants of the same pair
    for f in findings:
        k=frozenset(n.lower() for n in f["names"])
        if k not in seen: seen.add(k); out.append(f)
    return out

def corpus_dates(results):
    """Freshness picture + past-dated time-sensitive content (folds the latter into CHK_FRESH).
    If articles carry a real last-updated date we bucket by age; otherwise (common on crawled KBs)
    we fall back to the most-recent date each article *mentions* as a recency proxy, and flag that
    nothing in the KB tells the AI how current an article is."""
    fulldate=re.compile(r"\b(\d{1,2}\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+20[12]\d|"
     r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+\d{1,2},?\s+20[12]\d)\b",re.I)
    ages=[]; recent_year=[]; stale=[]; no_signal=0; verified=re.compile(r"\b(last (verified|updated|reviewed)|as of)\b",re.I)
    for r in results:
        age=None; u=r.get("updated_at")
        if u:
            try: age=(TODAY-datetime.date.fromisoformat(str(u)[:10])).days
            except Exception: age=None
        ages.append(age)
        txt=r["_text"]; yrs=[int(x) for x in DATE_RE.findall(txt)]
        recent_year.append(max(yrs) if yrs else None)
        if age is None and not verified.search(txt): no_signal+=1
        past_year=[y for y in yrs if y<TODAY.year and not re.search(r"since\s+\w*\s*"+str(y),txt,re.I)]
        if (past_year or fulldate.search(txt)) and bool(TIME_RE.search(txt)):
            ex=str(min(past_year)) if past_year else (fulldate.search(txt).group(0))
            stale.append({"title":r["title"],"detail":ex}); _fold(r["checks"][CHK_FRESH],
                f"Quotes a past-dated, time-sensitive detail ({ex}) — the AI may present it as current.")
    dated=sum(1 for a in ages if a is not None)
    if dated>=max(5,0.4*len(results)):  # enough real update dates -> age view
        lab=["0-3 mo","3-6 mo","6-12 mo","1-2 yr","2 yr+","undated"]; counts=[0]*6
        for a in ages: counts[5 if a is None else (0 if a<92 else 1 if a<183 else 2 if a<366 else 3 if a<731 else 4)]+=1
        mode="age"; hot={"undated","1-2 yr","2 yr+"}
    else:  # recency-proxy view: bucket by the newest date each article mentions
        order=["No date","≤2021","2022","2023","2024","2025+"]; idx={l:k for k,l in enumerate(order)}; counts=[0]*6
        def b(y): return "No date" if y is None else ("≤2021" if y<=2021 else "2025+" if y>=2025 else str(y))
        for y in recent_year: counts[idx[b(y)]]+=1
        lab=order; mode="mentions"; hot={"No date","≤2021","2022"}
    return {"mode":mode,"buckets":[{"label":l,"count":c,"hot":l in hot} for l,c in zip(lab,counts)],
            "undated":sum(1 for a in ages if a is None),"no_freshness_signal":no_signal,
            "stale_dated":stale,"stale_count":len(stale),"total":len(results)}

def coverage_gap(results,tickets_path):
    """Topics customers ask about that the KB has no article for. Needs a ticket export; locked until then."""
    if not tickets_path: return {"status":"locked",
        "hint":"Upload a ticket export (CSV) to reveal the questions your customers ask that have no article."}
    import csv
    try: rows=list(csv.reader(open(tickets_path,encoding="utf-8-sig")))
    except Exception as e: return {"status":"error","hint":f"Couldn't read tickets CSV: {e}"}
    if not rows: return {"status":"empty","hint":"Ticket CSV was empty."}
    hdr=[h.lower().strip() for h in rows[0]]; sc=0
    for cand in ("subject","summary","title","question","description","ticket subject"):
        if cand in hdr: sc=hdr.index(cand); break
    body=rows[1:] if any(h.isalpha() for h in hdr) else rows
    subjects=[r[sc].strip() for r in body if len(r)>sc and r[sc].strip()]
    kb_terms=set()
    for r in results: kb_terms|=set(toks(r["title"]+" "+r["_text"]))
    # map each KB-absent salient token -> the ticket subjects that mention it
    tok_subj=collections.defaultdict(set)
    for i,s in enumerate(subjects):
        for w in set(toks(s)):
            if w not in kb_terms: tok_subj[w].add(i)
    # keep tokens asked about by >=2 tickets, then merge tokens that cover (mostly) the same subjects
    cand=sorted((t for t,si in tok_subj.items() if len(si)>=2),key=lambda t:-len(tok_subj[t]))
    topics=[]
    for t in cand:
        si=tok_subj[t]
        for top in topics:
            if len(si&top["subj"])/len(si|top["subj"])>=0.5: top["terms"].append(t); top["subj"]|=si; break
        else: topics.append({"terms":[t],"subj":set(si)})
    gaps=[{"topic":top["terms"][0],"terms":top["terms"][:4],"volume":len(top["subj"]),
           "examples":[subjects[k][:80] for k in sorted(top["subj"])[:2]]} for top in topics]
    gap_subj=set().union(*[t["subj"] for t in topics]) if topics else set()
    return {"status":"ok","tickets":len(subjects),"gaps":sorted(gaps,key=lambda g:-g["volume"])[:15],
            "covered_pct":round(100*(1-len(gap_subj)/max(1,len(subjects))))}

def style_profile(arts,results):
    """Derive a rich, multi-signal house-style profile. Feeds the rewrites and the dashboard;
    NEVER affects scoring. Returns a one-line `descriptor` (back-compat) plus structured
    `signals` and a short `highlights` list of plain-language style notes."""
    you=we=emoji=faq=0; sl=[]; wcs=[]; openers=[]; tc=sc=0
    excl=contr=please=enc=bullets=numbered=if_openers=tot_words=0
    quest_head=ger_head=noun_head=0; emoji_top=collections.Counter()
    for a,r in zip(arts,results):
        t=r["_text"]; body=a.get("body","")
        you+=len(re.findall(r"\byou(r|'ll|'ve|'re)?\b",t,re.I)); we+=len(re.findall(r"\bwe('ll|'ve|'re)?\b|\bour\b",t,re.I))
        ems=EMOJI_RE.findall(t); emoji+=len(ems); emoji_top.update(ems)
        sl+=[len(s.split()) for s in sentences(t)]; wc=r["word_count"]; wcs.append(wc); tot_words+=wc
        excl+=t.count("!"); contr+=len(CONTR_RE.findall(t)); please+=len(re.findall(r"\b(please|thanks|thank you)\b",t,re.I))
        enc+=len(ENCOURAGE_RE.findall(t))
        if r["_intro"]:
            openers.append(r["_intro"].split(".")[0][:90])
            if re.match(r"\s*if\b",r["_intro"],re.I): if_openers+=1
        if re.search(r"frequently asked|\bQ:\s",body,re.I): faq+=1
        if re.search(r"<ul\b",body,re.I): bullets+=1
        if re.search(r"<ol\b",body,re.I) or re.search(r"(?m)^\s*\d+\.\s",t): numbered+=1
        for lvl,h in get_headings(body):
            words=h.split(); caps=[w for w in words if w[:1].isupper()]
            if len(words)>1 and len(caps)>=len(words)-1: tc+=1
            else: sc+=1
            if h.strip().endswith("?"): quest_head+=1
            elif words and re.search(r"ing$",words[0],re.I): ger_head+=1
            elif words: noun_head+=1
    n=max(1,len(arts))
    sls=sorted(sl)
    def q(p): return sls[min(len(sls)-1,int(p*len(sls)))] if sls else 0
    avg_sl=round(statistics.mean(sl),1) if sl else 0
    you_per_100=round(100*you/max(1,tot_words),1)
    # dominant heading style
    hstyle=max([(quest_head,"question headings ('How do I…?')"),(ger_head,"action/gerund headings ('Charging your…')"),
                (noun_head,"noun-phrase headings ('Battery life')")],key=lambda x:x[0])[1] if (quest_head+ger_head+noun_head) else "noun-phrase headings"
    # warmth markers (only those that genuinely show up)
    warmth=[]
    if emoji>0: warmth.append("emoji")
    if excl/n>=0.8: warmth.append("exclamation marks")
    if enc/n>=0.8: warmth.append("encouraging asides ('no worries', 'simply', 'that's it')")
    if please/n>=0.4: warmth.append("polite phrasing ('please', 'thanks')")
    if contr/n>=2: warmth.append("contractions ('you'll', 'don't')")
    fmt=[]
    if numbered>=n*0.25: fmt.append("numbered steps for procedures")
    if bullets>=n*0.25: fmt.append("bulleted lists")
    if faq>=n*0.4: fmt.append("FAQ / Q-and-A blocks")
    sig={
        "voice":"Second-person — speaks directly to the reader ('you/your')" if you>we else "First-person brand voice ('we/our')",
        "you_vs_we":f"{you}:{we}","second_person_per_100_words":you_per_100,
        "avg_words_per_article":round(statistics.mean(wcs)) if wcs else 0,
        "avg_sentence_words":avg_sl,"sentence_range":f"{q(0.25)}–{q(0.75)} words",
        "warmth_markers":warmth,"encouraging":enc/n>=0.8,
        "emoji_used":emoji>0,"emoji_per_article":round(emoji/n,1),
        "emoji_top":[e for e,_ in emoji_top.most_common(6)],
        "exclamations_per_article":round(excl/n,1),"contractions_per_article":round(contr/n,1),
        "uses_contractions":contr/n>=2,"polite":please/n>=0.4,
        "heading_case":"Title Case" if tc>=sc else "Sentence case","heading_style":hstyle,
        "opens_with_if_clause":round(100*if_openers/n) if openers else 0,
        "formatting":fmt or ["mostly prose paragraphs"],
        "faq_pattern_pct":round(100*faq/n),"sample_openers":openers[:4],
    }
    # back-compat top-level fields (used by older callers / templates)
    p={"articles":len(arts),"avg_words_per_article":sig["avg_words_per_article"],
       "avg_sentence_words":avg_sl,"you_vs_we":sig["you_vs_we"],"emoji_used":emoji>0,
       "faq_pattern_pct":sig["faq_pattern_pct"],"heading_case":sig["heading_case"],
       "sample_openers":openers[:4],"signals":sig}
    # rich one-line descriptor (still the single string the rewrite prompt injects)
    tone=[sig["voice"]]
    warm="warm and encouraging" + (" (" + ", ".join(warmth) + ")" if warmth else "")
    tone.append(warm)
    tone.append(f"{avg_sl}-word sentences on average (typically {sig['sentence_range']})")
    tone.append(f"~{sig['avg_words_per_article']} words per article")
    tone.append("; ".join(sig["formatting"]))
    tone.append(f"{sig['heading_case'].lower()} {sig['heading_style']}")
    p["descriptor"]="; ".join(tone)+"."
    # plain-language highlights for the dashboard
    hl=[sig["voice"]+f" — 'you' outweighs 'we' {you}:{we}"]
    if warmth: hl.append("Warmth shows up as: "+", ".join(warmth))
    hl.append(f"Sentences average {avg_sl} words; most run {sig['sentence_range']}")  # typical range
    hl.append(f"Articles average {sig['avg_words_per_article']} words")
    hl.append("Structure: "+", ".join(sig["formatting"]))
    hl.append(f"Headings: {sig['heading_case'].lower()}, {sig['heading_style']}")
    if sig["opens_with_if_clause"]>=20: hl.append(f"Often opens by naming the situation first ('If you…') — {sig['opens_with_if_clause']}% of articles")
    if sig["emoji_used"]: hl.append("Light emoji use"+(": "+" ".join(sig["emoji_top"]) if sig["emoji_top"] else "")+f" (~{sig['emoji_per_article']}/article)")
    p["highlights"]=hl
    return p

# Grade bands. Deliberately NOT the US school curve (where <60% is an F): these checks are a
# high bar that almost no help center is written against in the first place, so a US curve hands
# nearly every customer an F on the first pass — which is both discouraging and inaccurate. A KB
# passing half the checks is doing an ordinary, workable job, so 50% is a C.
GRADE_TABLE=[(90,"A+"),(80,"A"),(75,"B+"),(70,"B"),(60,"C+"),(50,"C"),(40,"D"),(30,"E"),(20,"F")]
def grade_for(pct):
    for thr,g in GRADE_TABLE:
        if pct>=thr: return g
    return "F"

def score(results):
    """Grade on the IMPORTANCE-WEIGHTED pass rate, not a flat count of checks.

    Every check carries a weight in PATTERN_META (3 = fundamental, 2 = matters, 1 = nice to have).
    Counting checks flat made an unexplained acronym (weight 1) cost an article exactly as much as
    never giving the fix (weight 3), which punished tidy-but-imperfect help centers for nitpicks.
    The displayed "x/13" stays a plain check count — customers read it as "checks passed", and
    weighted fractions there would be meaningless — but the grade and the fix queue use the weights.
    """
    for r in results:
        pa=fx=na=0; wpass=wfix=0
        for k,c in r["checks"].items():
            w=PATTERN_META[k][3]
            if c["verdict"]=="Pass": pa+=1; wpass+=w
            elif c["verdict"]=="Fix": fx+=1; wfix+=w
            else: na+=1
        r["passes"],r["fixes"],r["na"]=pa,fx,na; r["applicable"]=pa+fx; r["score"]=pa; r["score_str"]=f"{pa}/{pa+fx}"
        r["weighted_passed"],r["weighted_fixes"]=wpass,wfix; r["weighted_applicable"]=wpass+wfix
        r["pct"]=round(100*wpass/max(1,wpass+wfix)); r["grade"]=grade_for(r["pct"])
        intent=1.5 if re.search(r"\b(cancel|refund|billing|payment|log ?in|password|can'?t|unable|delete|reset|charge|pair|connect|setup|subscription|account)\b",r["title"],re.I) else 1.0
        r["leverage"]=round((r.get("vote_count",0) or 0)**0.5*intent,2)
        # queue by the weight of what's failing, so a fundamental gap outranks a pile of nitpicks
        r["priority"]=round(r["weighted_fixes"]*(1+r["leverage"]/10),2)
    results.sort(key=lambda r:(-r["priority"],-r["weighted_fixes"]))
    n=len(results)
    for i,r in enumerate(results):
        r["rank"]=i+1
        if r["fixes"]==0 or r["priority"]==0:
            r["priority_band"]="Very low"
        else:
            frac=i/max(1,n)
            r["priority_band"]=("Very high" if frac<0.2 else "High" if frac<0.4 else
                                "Medium" if frac<0.6 else "Low" if frac<0.8 else "Very low")
    return results

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("articles"); ap.add_argument("-o","--out",default="results.json")
    ap.add_argument("--tickets",help="optional ticket export CSV; unlocks coverage-gap analysis")
    a=ap.parse_args(); arts=json.loads(Path(a.articles).read_text())
    results=[check_article(x) for x in arts]
    # corpus-wide coherence passes (run BEFORE score() so findings fold into the grade)
    corpus_duplicates(results)
    vecs=article_vectors(results)
    corpus={"collisions":corpus_collisions(results,vecs),
            "contradictions":corpus_contradictions(results,vecs),
            "disambiguation":corpus_disambiguation(results),
            "dates":corpus_dates(results),
            "coverage":coverage_gap(results,a.tickets)}
    profile=style_profile(arts,results); score(results)
    roll={}
    for p in ORDER:
        fix=sum(1 for r in results if r["checks"][p]["verdict"]=="Fix"); na=sum(1 for r in results if r["checks"][p]["verdict"]=="N/A")
        roll[p]={"fix":fix,"applicable":len(results)-na,"pass_pct":round(100*(len(results)-na-fix)/max(1,len(results)-na)),
                 "group":PATTERN_META[p][0],"why":PATTERN_META[p][1],"short":PATTERN_META[p][2],"weight":PATTERN_META[p][3]}
    for r in results: r.pop("_text",None)
    overall_pct=statistics.mean(r["pct"] for r in results) if results else 0
    grade_counts=collections.Counter(r["grade"] for r in results)
    out={"generated":datetime.datetime.now().isoformat(timespec="seconds"),"article_count":len(results),
         "avg_score":round(statistics.mean(r["score"] for r in results),1),
         "avg_applicable":round(statistics.mean(r["applicable"] for r in results),1),
         "overall_pct":round(overall_pct),"overall_grade":grade_for(overall_pct),
         "grade_counts":dict(grade_counts),
         "order":ORDER,"groups":[G_FIND,G_USE,G_TRUST],"pattern_rollup":roll,"style_profile":profile,
         "corpus":corpus,"results":results}
    Path(a.out).write_text(json.dumps(out,indent=2,default=str))
    print(f"Audited {len(results)} articles. Overall grade {out['overall_grade']} ({out['overall_pct']}%). Avg {out['avg_score']}/{out['avg_applicable']}.")
    cov=corpus["coverage"]
    print(f"Corpus: {len(corpus['collisions'])} near-duplicate pair(s), {len(corpus['contradictions'])} possible "
          f"contradiction(s), {len(corpus['disambiguation'])} confusable-name set(s), {corpus['dates']['stale_count']} "
          f"stale-dated article(s); coverage gaps "+("LOCKED (no tickets)" if cov["status"]=="locked" else str(len(cov.get("gaps",[])))) + ".")
    for r in results[:5]: print(f"  #{r['rank']:>2} {r['score_str']:>6} prio {r['priority']:>6} votes {r['vote_count']:>5}  {r['title'][:46]}")
    print("\nWeakest (by pass-rate then importance):")
    for p,v in sorted(roll.items(),key=lambda kv:(kv[1]['pass_pct'],-kv[1]['weight']))[:6]:
        print(f"  {v['pass_pct']:>3}%  w{v['weight']}  {p}  ({v['fix']} to fix)")
    print("\nStyle:",profile["descriptor"])

if __name__=="__main__": main()

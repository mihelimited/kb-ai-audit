#!/usr/bin/env python3
"""verify_rewrites.py - hallucination guard for rewrites.

For every rewritten article it extracts the *checkable facts* it asserts - measurements and specs
(numbers + units), and quoted strings (error messages / exact UI labels) - and confirms each one
actually appears in the source help-center articles. Anything that doesn't trace back is flagged
for a human to verify, so a rewrite can't quietly invent a number, spec or button name.

Deterministic, stdlib-only, no network. It cannot prove a rewrite is fact-perfect (paraphrased prose
isn't checked) - it catches the highest-risk fabrications: invented specs and made-up quoted strings.

Usage:
  verify_rewrites.py rewrites.json --source articles.json [-o verify_report.md] [--strict]
Exit code: 0 if no flags (or non-strict), 1 if flags found and --strict.
"""
import json, re, argparse, html, unicodedata, sys
from pathlib import Path

TAG=re.compile(r"<[^>]+>")

def _norm(s):
    s=html.unescape(s or ""); s=TAG.sub(" ", s)
    s=unicodedata.normalize("NFKD", s).lower()
    for a,b in [("–","-"),("—","-"),("−","-"),("’","'"),("‘","'"),("“",'"'),("”",'"'),(" "," ")]:
        s=s.replace(a,b)
    s=re.sub(r"(\d),(\d)", r"\1\2", s)          # 3,800 -> 3800
    s=re.sub(r"\s+", " ", s)
    return s.strip()

def _compact(s):                                 # unit-agnostic: "2.54 cm"=="2.54cm", '1"'=="1 inch"=="1-inch"
    s=_norm(s).replace('"', "inch").replace("″", "inch")
    return re.sub(r"[^a-z0-9.]", "", s)          # keep letters, digits, dot only

def _clean_body(body):
    """Strip embeds, raw HTML and image/link plumbing so we only check the prose's facts —
    iframe width/height/src attributes are not article facts."""
    body=re.sub(r"<[^>]+>", " ", body)                       # raw HTML tags (iframe, etc.)
    body=re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", body)          # markdown images
    body=re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", body)       # links -> link text
    return body

# measurements / specs: optional range, number, unit
UNIT=r"(?:mah|gb|mb|kb|tb|hours?|hrs?|minutes?|mins?|seconds?|secs?|days?|weeks?|months?|years?|°\s?[cf]|cm|mm|km|metres?|meters?|inch(?:es)?|ghz|mhz|hz|%|mp|fps|v\b|w\b)"
MEASURE=re.compile(r"(?<![\w.])-?\d[\d.,]*\s*(?:[-/]\s*-?\d[\d.,]*\s*)?(?:to\s*-?\d[\d.,]*\s*)?"+UNIT, re.I)
INCHQUOTE=re.compile(r'\b\d[\d.,]*\s?"(?=[\s/).,]|$)')      # 1" pole
QUOTED=re.compile(r'"([^"\n]{3,70})"')                       # error messages / UI labels in quotes

# strings that are NOT facts to check (structural labels we add ourselves)
SKIP_QUOTED=re.compile(r"^(applies to|last verified|what changed|good to know|the short answer)\b", re.I)

def facts_in(body):
    body=_clean_body(body)
    measures=set()
    for m in MEASURE.finditer(body): measures.add(m.group(0).strip())
    for m in INCHQUOTE.finditer(body): measures.add(m.group(0).strip())
    quotes=set()
    for m in QUOTED.finditer(body):
        q=m.group(1).strip()
        if q and not SKIP_QUOTED.match(q): quotes.add(q)
    return measures, quotes

def verified(fact, src_norm, src_compact):
    n=_norm(fact); c=_compact(fact)
    if c and c in src_compact: return True
    if n and n in src_norm: return True
    # ranges: check each endpoint+unit individually (e.g. "5-14 days" -> "14 days")
    m=re.match(r"(-?\d[\d.,]*)\s*[-/]\s*(-?\d[\d.,]*)\s*(.*)", n)
    if m:
        unit=m.group(3).strip()
        for num in (m.group(1), m.group(2)):
            if _compact(num+unit) in src_compact: return True
    return False

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("rewrites"); ap.add_argument("--source", required=True)
    ap.add_argument("-o","--out", default=None); ap.add_argument("--strict", action="store_true")
    a=ap.parse_args()
    rw=json.loads(Path(a.rewrites).read_text()); rewrites=rw.get("rewrites", rw) if isinstance(rw, dict) else rw
    arts=json.loads(Path(a.source).read_text())
    by_url={ re.sub(r"^https?://","",(x.get("html_url") or "")).rstrip("/").lower(): x for x in arts }
    corpus_norm=_norm(" ".join(x.get("body","") for x in arts))
    corpus_compact=_compact(" ".join(x.get("body","") for x in arts))

    rows=[]; total_flags=0; total_facts=0
    for r in rewrites:
        body=r.get("body","")
        src_url=re.sub(r"^https?://","",(r.get("source_url") or "")).rstrip("/").lower()
        src=by_url.get(src_url)
        # check against the named source first, then the whole help center (splits/consolidation)
        sn=_norm(src.get("body","")) if src else ""
        sc=_compact(src.get("body","")) if src else ""
        measures, quotes=facts_in(body)
        flagged=[]
        for f in sorted(measures):
            total_facts+=1
            if not (verified(f, sn, sc) or verified(f, corpus_norm, corpus_compact)):
                flagged.append(("spec", f))
        for f in sorted(quotes):
            total_facts+=1
            if not (verified(f, sn, sc) or verified(f, corpus_norm, corpus_compact)):
                flagged.append(("quote", f))
        total_flags+=len(flagged)
        rows.append((r.get("new_title") or r.get("title") or "?", len(measures)+len(quotes), flagged))

    # report
    L=["# Hallucination check — fact verification of rewrites\n",
       f"Checked **{len(rewrites)}** rewritten article(s): **{total_facts}** checkable facts "
       f"(measurements/specs + quoted strings), **{total_flags}** not found in the source.\n",
       "A flag means the fact (a number/spec, or a quoted error message/label) doesn't appear in the "
       "source help-center articles — verify it before publishing. Paraphrased prose isn't checked.\n"]
    if total_flags==0:
        L.append("✅ **Every checkable fact traces back to the source.** No invented specs or quotes detected.\n")
    for title, nfacts, flagged in rows:
        if flagged:
            L.append(f"\n## ⚠️ {title}  ({len(flagged)} to verify of {nfacts} facts)")
            for kind, f in flagged:
                L.append(f"- **[{kind}]** `{f}` — not found in source")
        else:
            L.append(f"\n## ✅ {title}  ({nfacts} facts, all verified)")
    report="\n".join(L)+"\n"
    if a.out: Path(a.out).write_text(report)
    print(report)
    print(f"SUMMARY: {total_flags} flag(s) across {len(rewrites)} article(s), {total_facts} facts checked.")
    if a.strict and total_flags: sys.exit(1)

if __name__=="__main__": main()

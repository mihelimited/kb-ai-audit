#!/usr/bin/env python3
"""
html_to_pdf.py — render a local HTML file to PDF with whatever engine is available.

The branded report HTML is the single source of truth (built by build_branded.py); this
turns it into a faithful, paginated PDF. It tries, in order:
  1. Playwright (bundled Chromium)         pip install playwright && playwright install chromium
  2. A headless Chrome / Chromium / Edge / Brave binary already on the machine
  3. WeasyPrint                            pip install weasyprint

Page size and margins come from the HTML's own `@page` CSS (A4), so every engine produces
the same layout. The orchestration here is pure standard library; the engines are optional.
If none are available it exits non-zero with a clear message — the HTML is still printable
by hand.

Usage: html_to_pdf.py out/report.html out/report.pdf
"""
import sys, os, shutil, subprocess, argparse, tempfile
from pathlib import Path


def _uri(path):
    return Path(path).resolve().as_uri()


def via_playwright(src, dst):
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        return False
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        try:
            page = browser.new_page()
            page.goto(_uri(src), wait_until="networkidle")
            # prefer_css_page_size honours the HTML's @page A4 + margins
            page.pdf(path=str(dst), print_background=True, prefer_css_page_size=True)
        finally:
            browser.close()
    return os.path.exists(dst)


# name-on-PATH candidates, then common macOS .app bundle paths
_CHROME_CANDIDATES = [
    "google-chrome", "google-chrome-stable", "chromium", "chromium-browser",
    "microsoft-edge", "microsoft-edge-stable", "brave-browser",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
]


def _find_chrome():
    for c in _CHROME_CANDIDATES:
        if os.path.basename(c) == c:           # bare name → look on PATH
            p = shutil.which(c)
            if p:
                return p
        elif os.path.exists(c):                # absolute path
            return c
    return None


def via_chrome(src, dst):
    exe = _find_chrome()
    if not exe:
        return False
    dst = os.path.abspath(dst)
    # newer Chrome wants --headless=new; older only knows --headless. Try new, then fall back.
    for headless in ("--headless=new", "--headless"):
        with tempfile.TemporaryDirectory() as ud:
            cmd = [exe, headless, "--disable-gpu", "--no-sandbox",
                   f"--user-data-dir={ud}", "--no-pdf-header-footer",
                   f"--print-to-pdf={dst}", _uri(src)]
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if os.path.exists(dst) and os.path.getsize(dst) > 0:
            return True
    return False


def via_weasyprint(src, dst):
    try:
        from weasyprint import HTML
    except Exception:
        return False
    HTML(filename=str(src)).write_pdf(str(dst))
    return os.path.exists(dst)


def main():
    ap = argparse.ArgumentParser(description="Render a local HTML file to PDF.")
    ap.add_argument("src", help="input HTML file")
    ap.add_argument("dst", help="output PDF file")
    a = ap.parse_args()
    if not os.path.exists(a.src):
        sys.stderr.write(f"html_to_pdf: input not found: {a.src}\n")
        return 2
    Path(a.dst).parent.mkdir(parents=True, exist_ok=True)

    for engine, name in ((via_playwright, "Playwright"), (via_chrome, "headless Chrome"), (via_weasyprint, "WeasyPrint")):
        try:
            if engine(a.src, a.dst):
                print(f"Wrote {a.dst} via {name}")
                return 0
        except Exception as e:
            sys.stderr.write(f"html_to_pdf: {name} failed ({e}); trying next engine…\n")

    sys.stderr.write(
        "html_to_pdf: no HTML→PDF engine available (tried Playwright, headless Chrome, WeasyPrint).\n"
        f"The branded report is still at {a.src} — open it and Print → Save as PDF, or install one of:\n"
        "  pip install playwright && playwright install chromium\n"
        "  pip install weasyprint\n")
    return 3


if __name__ == "__main__":
    sys.exit(main())

"""Assemble the landing page.

  python build.py            -> dist/index.html   everything inlined (one file; what the artifact shows)
  python build.py --site     -> site/             index.html + img/ + data/demo.json, for a web server

`src/index.html` is the one source.  `%%IMG:name%%` becomes a data URI (inline) or
`img/<name>.png` (site); `%%DEMO%%` is data/demo.json inline, or empty for the site build,
where the page fetches data/demo.json at load; `%%TRANSCRIPT%%` is data/transcript.json
when it exists, else empty and the page draws its placeholder.
"""
import base64
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "src" / "index.html"
IMAGES = {"fap-light": "img/fap-light.png", "fap-dark": "img/fap-dark.png",
          "gui-light": "img/gui-history-light.png", "gui-dark": "img/gui-history-dark.png"}
DEMO = HERE / "data" / "demo.json"
TRANSCRIPT = HERE / "data" / "transcript.json"
# Nothing from the contributor's bundle that names a file, a specimen, a machine or a person
# may reach the page. Tokens are substrings; the regexes catch the filename grammar itself.
LEAK = ("8pptn0", "etoh", "sio2", "0523",                       # specimen code, sample tags, acquisition-date prefix
        "02pct", "solgel", "8reg0", "drypack", "ultrathin",      # sibling specimens' tags
        "splitter",                                              # the reference's own parser
        "/Users/", "/Volumes/", "gaultois", "Michael", "michael", "Capel", "Donat")   # machines and people
LEAK_RE = (r"_I\d+_", r"\b\d{10}_", r"\b\d{8}_CuO")           # scan token, acquisition timestamp, run-folder date

def leaks(text: str) -> list[str]:
    """Every leak token or pattern found in `text`, in list order; empty means clean."""
    found = [t for t in LEAK if t in text]
    for pat in LEAK_RE:
        m = re.search(pat, text)
        if m:
            found.append(m.group(0))
    return found

def data_uri(p: Path) -> str:
    mime = "image/svg+xml" if p.suffix == ".svg" else "image/png"
    return f"data:{mime};base64,{base64.b64encode(p.read_bytes()).decode('ascii')}"

# `src/index.html` is authored as an artifact **fragment**: the Artifact runtime wraps it in
# a document and supplies the charset and the viewport, and refuses a file that brings its
# own `<html>`.  A web server supplies neither, so the site build adds the skeleton — the
# same one the runtime does, `<title>` and `<style>` at the top of `<body>` included, which
# the HTML parser hoists.  Measured: without the charset a server that does not say utf-8
# renders every `·`, `θ` and `α` on the page as mojibake, and without the viewport a phone
# lays it out 980 px wide.  The page's own CSS is complete (box-sizing, color-scheme, body
# background and font), so the skeleton carries no reset.
DOCUMENT = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
</head>
<body>
{body}</body>
</html>
"""


def assemble(site: bool) -> str:
    html = SRC.read_text(encoding="utf-8")
    fav = HERE / "src" / "favicon.svg"
    html = html.replace("%%FAVICON%%", "favicon.svg" if site else data_uri(fav))
    for name, rel in IMAGES.items():
        html = html.replace(f"%%IMG:{name}%%", rel if site else data_uri(HERE / rel))
    demo = "" if site else DEMO.read_text(encoding="utf-8")
    html = html.replace("%%DEMO%%", demo)
    tr = TRANSCRIPT.read_text(encoding="utf-8").strip() if TRANSCRIPT.exists() else ""
    html = html.replace("%%TRANSCRIPT%%", tr)
    assert "%%" not in html, "unfilled placeholder"
    bad = leaks(html)
    if bad:
        raise SystemExit(f"leak: {bad[:5]} in the page")
    return DOCUMENT.format(body=html) if site else html

if __name__ == "__main__":
    site = "--site" in sys.argv
    if site:
        out = HERE / "site"
        shutil.rmtree(out, ignore_errors=True)
        (out / "img").mkdir(parents=True)
        (out / "data").mkdir()
        for rel in IMAGES.values():
            shutil.copy(HERE / rel, out / rel)
        shutil.copy(HERE / "src" / "favicon.svg", out / "favicon.svg")
        # Absent is a state, not an error: the payload is a contributor's data and
        # lives outside this repository (README § How it is built and served), so a
        # fork builds the page without the animation rather than failing.
        if DEMO.exists():
            shutil.copy(DEMO, out / "data" / "demo.json")
        if TRANSCRIPT.exists():
            shutil.copy(TRANSCRIPT, out / "data" / "transcript.json")
        (out / "index.html").write_text(assemble(True), encoding="utf-8")
    else:
        out = HERE / "dist"
        out.mkdir(exist_ok=True)
        (out / "index.html").write_text(assemble(False), encoding="utf-8")
    print("wrote", out)

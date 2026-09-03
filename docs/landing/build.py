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
# **Matched case-insensitively**, because half of what this guards is prose cut by hand: a
# filename says `sio2` and `etoh` while a sentence says `SiO2` and `EtOH`.  A token written in
# one case would have passed the other straight through — which is the only failure this file
# has.  The people arm is now empty (WP-1331): the caption credits every one of them by name,
# and a person the page thanks cannot also be a token that fails the build.  What keeps a
# machine path out is `/Users/`, `/Volumes/` and LEAK_RE, none of which ever moved.
LEAK = ("8pptn0", "etoh", "sio2", "0523",                       # specimen code, sample tags, acquisition-date prefix
        "02pct", "solgel", "8reg0", "drypack", "ultrathin",      # sibling specimens' tags
        "splitter",                                              # the reference's own parser
        "/Users/", "/Volumes/")                                  # machine paths
LEAK_RE = (r"_I\d+_", r"\b\d{10}_", r"\b\d{8}_CuO")           # scan token, acquisition timestamp, run-folder date

# The support phases are kept out a rank earlier and are deliberately NOT tokens here: a
# denylist publishes what it denies, and these names would be in the repository either way.
# `build_demo.phase_columns` takes them from the bundle's own header instead and ships
# them as "support n", so no build of this page has ever held one (WP-1331).

# base64 is drawn from [A-Za-z0-9+/], so a four-character token turns up inside a
# 200 kB inlined PNG by chance — measured: `etoh` and `sio2` both do, and `0523`
# would have without the case fold.  A blob carries no name, so it is not scanned.
BLOB = re.compile(r"base64,[A-Za-z0-9+/=]+")

def leaks(text: str) -> list[str]:
    """Every leak token or pattern found in `text`, in list order; empty means clean."""
    text = BLOB.sub("base64,", text)
    lowered = text.lower()
    found = [t for t in LEAK if t.lower() in lowered]
    for pat in LEAK_RE:
        m = re.search(pat, text, re.IGNORECASE)
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
    if not site and not DEMO.exists():
        # The inline build is the one-file artifact, whose whole point is the payload;
        # absent, say so rather than raising FileNotFoundError from inside a replace.
        # (`--site` is the build where absent is a legitimate state — see __main__.)
        raise SystemExit(f"no payload at {DEMO} — the inline build needs one; "
                         f"`build.py --site` is the build that does not")
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
        # The payload is committed (README § The payload), so absence means someone
        # removed it.  Still not an error: the page renders without the animation
        # rather than failing the whole site build.
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

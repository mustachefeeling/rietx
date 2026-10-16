"""Serve both spike sites and screenshot each page, light and dark, desktop and phone."""
import functools
import http.server
import json
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "manual"))
from make_screenshots import chromium_path  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

S = Path(__file__).resolve().parents[1]
OUT = S / "shots"
OUT.mkdir(exist_ok=True)
SITES = {"sphinx": (S / "site-sphinx", 8811, ".html"), "myst": (S / "site-myst", 8812, "")}
PAGES = {"front": "index", "guide": "guides/calibrate", "theory": "theory/profiles"}


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def serve(root, port):
    handler = functools.partial(Quiet, directory=str(root))
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()


report = {}
for name, (root, port, ext) in SITES.items():
    serve(root, port)
with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=chromium_path())
    for name, (root, port, ext) in SITES.items():
        for page_key, path in PAGES.items():
            if name == "myst" and path == "index":
                url = f"http://127.0.0.1:{port}/docs/dev/"
            else:
                url = f"http://127.0.0.1:{port}/docs/dev/{path}{ext}"
            for scheme in ("light", "dark"):
                for label, vp in (("desk", {"width": 1280, "height": 900}), ("phone", {"width": 390, "height": 844})):
                    ctx = browser.new_context(viewport=vp, color_scheme=scheme)
                    page = ctx.new_page()
                    errors = []
                    page.on("pageerror", lambda e: errors.append(str(e)))
                    resp = page.goto(url, wait_until="networkidle")
                    page.wait_for_timeout(600)
                    shot = OUT / f"{name}-{page_key}-{scheme}-{label}.png"
                    page.screenshot(path=str(shot), full_page=True)
                    m = page.evaluate("""() => ({
                        scrollW: document.documentElement.scrollWidth,
                        clientW: document.documentElement.clientWidth,
                        imgs: [...document.querySelectorAll('img')].filter(i => i.offsetParent !== null && i.src.includes('angular')).map(i => i.src.split('/').pop()),
                        katexErr: document.querySelectorAll('.katex-error').length,
                    })""")
                    m["status"] = resp.status if resp else None
                    m["errors"] = errors
                    report[shot.name] = m
                    ctx.close()
    browser.close()
print(json.dumps(report, indent=1))

"""Check the Sphinx switcher and banner on dev and stable, and the /docs/ redirect."""
import functools
import http.server
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "manual"))
from make_screenshots import chromium_path  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

ROOT = str(Path(__file__).resolve().parents[1] / "site-sphinx")
handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=ROOT)
handler.log_message = lambda *a: None
httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 8813), handler)
threading.Thread(target=httpd.serve_forever, daemon=True).start()
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=chromium_path())
    page = b.new_page()
    page.goto("http://127.0.0.1:8813/docs/", wait_until="networkidle")
    print("redirect ->", page.url)
    for v in ("dev", "stable"):
        page.goto(f"http://127.0.0.1:8813/docs/{v}/theory/profiles.html", wait_until="networkidle")
        page.wait_for_timeout(800)
        banner = page.locator("#bd-header-version-warning").is_visible()
        items = page.locator(".version-switcher__menu a").evaluate_all(
            "els => els.map(e => e.textContent.trim() + ' ' + e.getAttribute('href'))")
        print(v, "banner", banner, "switcher", items)
    b.close()

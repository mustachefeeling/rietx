"""``rietx compare`` — a browser UI for comparing refinement settings.

    rietx compare              # → http://127.0.0.1:8730
    rietx compare --open --port 9000 --data /path/to/tests/data

Pick a standard, tick the variants to compare, press Run. The server refines
each (standard, variant) pair in a worker thread, caches the reduced result,
and the page draws three linked panes — see :mod:`rietx.viz.compare` for what
each one answers and why the first one is the load-bearing view.

Same architecture as ``rietx watch``: stdlib ``http.server``, plain fetch
polling, no FastAPI, no websockets, no javascript build step. The page is
files in ``static/`` (WP-1461; root CLAUDE.md: a page that is javascript is a
file), ``compare-core.mjs`` its half that touches no DOM. It draws with the
chart module and the uPlot vendored beside it (:mod:`rietx.viz.chart`),
served from the installed package, so the page is fully offline — a
strict-CSP or air-gapped machine needs no exception.

The poll carries each variant's statistics, diagnostics and parameters, never
its curves. Those come once per variant, packed, from ``/api/curves``, since
every channel of one variant of ``lab6_capillary`` is 5.57 MB and the poll
runs every 700 ms (the WP's § The payload behind a client zoom).

Runs are cached in memory keyed by ``(standard, variant)``. Re-ticking a
variant you already ran is instant, which is the point: the loop this supports
is *change one thing, look, change it back*.
"""

from __future__ import annotations

import http.server
import json
import threading
import urllib.parse
import webbrowser
from pathlib import Path

from ..viz import compare as cmp
from ..viz import theme
from ..viz.chart import CHART_DIR, CHART_FILES
from ..viz.packed import MEDIA_TYPE

DEFAULT_PORT = 8730

#: The page, as files in the package — ``watch/``'s ``STATIC_DIR`` again.
STATIC_DIR = Path(__file__).parent / "static"

#: What the page is made of, and what each file is served as.
STATIC_FILES = {
    "index.html": "text/html; charset=utf-8",
    "compare.css": "text/css; charset=utf-8",
    "compare.mjs": "text/javascript; charset=utf-8",
    "compare-core.mjs": "text/javascript; charset=utf-8",
}


class _State:
    """Run cache + one background worker, shared by every request thread."""

    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self.lock = threading.Lock()
        self.records: dict[tuple[str, str], cmp.RunRecord] = {}
        self.pending: set[tuple[str, str]] = set()
        self.log: list[str] = []
        self.worker: threading.Thread | None = None

    # -- worker ------------------------------------------------------
    def request(self, standard: str, variants: list[str]) -> None:
        """Queue the (standard, variant) pairs that are not already cached."""
        with self.lock:
            wanted = [(standard, v) for v in variants
                      if (standard, v) not in self.records]
            self.pending.update(wanted)
            busy = self.worker is not None and self.worker.is_alive()
        if wanted and not busy:
            self.worker = threading.Thread(target=self._drain, daemon=True)
            self.worker.start()

    def _drain(self) -> None:
        while True:
            with self.lock:
                if not self.pending:
                    return
                key = sorted(self.pending)[0]
                self.pending.discard(key)
            standard, variant = key
            self._note(f"running {standard} / {variant} …")
            try:
                record = cmp.run(standard, variant, data_dir=self.data_dir)
            except Exception as exc:  # registry/dataset problem, not a fit failure
                record = cmp.RunRecord.failed(
                    standard, variant, status="error",
                    error=f"{type(exc).__name__}: {exc}", seconds=0.0)
            with self.lock:
                self.records[key] = record
            done = record.error or f"Rwp {record.rwp:.4f}  GoF {record.gof:.3f}"
            self._note(f"  {standard} / {variant}: {done} "
                       f"({record.seconds:.1f} s)")

    def _note(self, line: str) -> None:
        with self.lock:
            self.log.append(line)
            del self.log[:-200]

    # -- reads -------------------------------------------------------
    def snapshot(self, standard: str, variants: list[str]) -> dict:
        with self.lock:
            ready = {v: self.records[(standard, v)].summary() for v in variants
                     if (standard, v) in self.records}
            running = sorted(v for s, v in self.pending if s == standard)
            busy = self.worker is not None and self.worker.is_alive()
            return {"records": ready, "queued": running, "busy": busy,
                    "log": list(self.log[-40:])}

    def curves(self, standard: str, variant: str) -> bytes | None:
        """One variant's packed curves, or ``None`` until it has a fit to draw."""
        with self.lock:
            record = self.records.get((standard, variant))
        if record is None or not len(record.two_theta):
            return None
        return record.curves().to_bytes()


def _themed(page: str) -> str:
    """Stamp the GUI's stored theme on the document, at load (WP-1429).

    This page has no poll to carry a change on, so it reads the choice when it
    is asked for and a switch in the GUI reaches it on the next reload.  An
    explicit choice becomes ``data-theme``; ``system`` is the *absence* of the
    attribute, which is what lets the ``prefers-color-scheme`` block in
    ``tokens.css`` answer — no server can see the machine the page is open on.

    Server-side rather than in script, because this page can be: there is no
    first paint in the wrong theme to correct afterwards.
    """
    choice = theme.theme_choice()
    stamp = f' data-theme="{choice}"' if choice in theme.THEMES else ""
    return page.replace("<html>", f"<html{stamp}>", 1)


def _handler(state: _State):
    class Handler(http.server.BaseHTTPRequestHandler):
        server_version = "rietx-compare"

        def log_message(self, *args) -> None:  # quiet by default
            pass

        def _send(self, body: bytes, content_type: str, code: int = 200) -> None:
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            # an upgraded package must not be served its old script out of a cache
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, payload: dict, code: int = 200) -> None:
            self._send(json.dumps(payload).encode("utf-8"),
                       "application/json; charset=utf-8", code)

        def do_GET(self) -> None:  # noqa: N802 - stdlib API
            path, _, raw = self.path.partition("?")
            query = {k: v[-1] for k, v in urllib.parse.parse_qs(raw).items()}
            name = path.lstrip("/") or "index.html"
            if name == "index.html":
                page = (STATIC_DIR / name).read_text(encoding="utf-8")
                self._send(_themed(page).encode("utf-8"), STATIC_FILES[name])
            elif name in STATIC_FILES:
                self._send((STATIC_DIR / name).read_bytes(), STATIC_FILES[name])
            elif name in CHART_FILES:
                self._send((CHART_DIR / name).read_bytes(), CHART_FILES[name])
            elif path == theme.CSS_ROUTE:
                self._send(theme.tokens_css().encode("utf-8"),
                           theme.CSS_CONTENT_TYPE)
            elif path == "/api/catalog":
                self._json(cmp.catalog(state.data_dir))
            elif path == "/api/state":
                variants = [v for v in query.get("variants", "").split(",") if v]
                self._json(state.snapshot(query.get("standard", ""), variants))
            elif path == "/api/curves":
                body = state.curves(query.get("standard", ""),
                                    query.get("variant", ""))
                if body is None:
                    self._json({"error": "no curves for that variant yet"}, 404)
                else:
                    self._send(body, MEDIA_TYPE)
            else:
                self._json({"error": "not found"}, 404)

        def do_POST(self) -> None:  # noqa: N802 - stdlib API
            if self.path != "/api/run":
                self._json({"error": "not found"}, 404)
                return
            n = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(n) or b"{}")
            standard = body.get("standard", "")
            variants = list(body.get("variants", []))
            if standard not in cmp.STANDARD_BY_KEY:
                self._json({"error": f"unknown standard {standard!r}"}, 400)
                return
            state.request(standard, variants)
            self._json({"queued": variants})

    return Handler


def serve(data_dir: Path | None = None, *, port: int = DEFAULT_PORT,
          open_browser: bool = False) -> None:
    data_dir = Path(data_dir) if data_dir is not None else cmp.default_data_dir()
    state = _State(data_dir)
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", port), _handler(state))
    url = f"http://127.0.0.1:{port}"
    available = [s.key for s in cmp.STANDARDS if s.available(data_dir)]
    print(f"rietx compare — {url}")
    print(f"  data: {data_dir}")
    print(f"  standards available: {', '.join(available) or '(none found)'}")
    if not available:
        print("  hint: pass --data <dir> pointing at a checkout's tests/data")
    if open_browser:
        webbrowser.open(url)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        httpd.server_close()


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        prog="rietx compare",
        description="Compare refinement settings on the bundled standards.")
    parser.add_argument("--data", type=Path, default=None,
                        help="directory holding the standards (default: the "
                             "checkout's tests/data)")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--open", action="store_true", dest="open_browser",
                        help="open a browser window")
    args = parser.parse_args(argv)
    serve(args.data, port=args.port, open_browser=args.open_browser)
    return 0

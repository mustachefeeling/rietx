"""``pxrdref gui`` — the localhost HTTP surface over a :class:`GuiSession`.

Stdlib ``http.server``, as ``pxrdref watch`` and ``pxrdref compare`` already are.
A single-user localhost app with ~30 routes gains nothing from an ASGI stack and
loses the two properties that matter here: a base install with no new
dependencies, and a page that works air-gapped (plotly.js is served out of the
installed package, so a strict-CSP or offline machine needs no exception).
Server-sent events work fine on ``ThreadingHTTPServer``.

**This module is transport only.**  Every route is one line — parse, call a
:class:`~pxrdref.gui.session.GuiSession` method, serialise — so replacing it
with a Tauri command handler means reimplementing this file and nothing else.
The route table is data for the same reason: ``ROUTES`` and
``session.RESERVED_ROUTES`` together are the complete wire surface, which is what
lets a test assert that no route is silently missing.

Security is the localhost kind and no more: bound to 127.0.0.1, ``Host`` and
``Origin`` checked so a page on another site cannot drive this server through a
DNS-rebinding attack, and export paths confined to the project's ``exports/``.
There is no auth, no TLS and no multi-user story — one user, one machine, one
process, one project.
"""

from __future__ import annotations

import http.server
import json
import math
import socket
import threading
import time
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from ..project import Project
from .imports import MAX_UPLOAD_BYTES, UPLOAD_KINDS
from .session import RESERVED_ROUTES, GuiError, GuiSession

#: ``compare`` owns 8730 and ``watch`` 8899; the GUI takes the next one up.
DEFAULT_PORT = 8731

#: Built frontend assets (WP-1010) land here and are committed, so installing
#: ``[gui]`` never needs node.  Until then the placeholder page below explains
#: itself and the API is fully usable without it.
STATIC_DIR = Path(__file__).parent / "static"

_ALLOWED_HOSTS = frozenset({"127.0.0.1", "localhost", "[::1]", "::1"})

_SSE_HEARTBEAT = 15.0  # seconds between ``: keepalive`` comments

_CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".mjs": "application/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".woff2": "font/woff2",
    ".map": "application/json; charset=utf-8",
}


# ----------------------------------------------------------------------
# serialisation
# ----------------------------------------------------------------------
def _finite(obj: Any) -> Any:
    """Replace every non-finite float with its string spelling, in place of nothing.

    ``json.dumps`` writes bare ``Infinity``/``NaN`` tokens, which are a Python
    extension: **JavaScript's ``JSON.parse`` rejects them outright**, so a single
    ``hi: inf`` bound turns a whole response into a parse error in the browser.
    Every parameter row has one, which is why this was invisible until a client
    read ``/api/params`` (WP-1011) rather than the curves.

    The spelling is not invented here — it is the one the schemas already chose
    (``ser_json_inf_nan="strings"``, CLAUDE.md: "±inf bounds must survive JSON
    round-trip"), so ``"Infinity"`` reads back as ``Number("Infinity")`` in JS and
    as ``float("Infinity")`` in Python.  The GUI server was the one place in this
    package re-serialising already-dumped dicts with stdlib ``json``, and so the
    one place that convention was being lost.
    """
    if isinstance(obj, float):
        return obj if math.isfinite(obj) else repr(obj).replace("nan", "NaN").replace(
            "inf", "Infinity")
    if isinstance(obj, dict):
        return {k: _finite(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_finite(v) for v in obj]
    return obj


def _dumps(payload: Any) -> str:
    """``json.dumps`` that a browser can parse.

    The scan is a substring test on the *output*, so the common response — no
    non-finite value anywhere — pays one C-level search rather than a recursive
    walk of a 4000-point curve payload.
    """
    text = json.dumps(payload, default=str)
    if "Infinity" in text or "NaN" in text:
        text = json.dumps(_finite(payload), default=str)
    return text


# ----------------------------------------------------------------------
# the route table
# ----------------------------------------------------------------------
def _query_float(query: dict, key: str) -> float | None:
    values = query.get(key)
    if not values or values[0] == "":
        return None
    try:
        return float(values[0])
    except ValueError:
        raise GuiError(f"{key}={values[0]!r} is not a number", where=[key]) from None


def _query_int(query: dict, key: str, default: int) -> int:
    values = query.get(key)
    if not values or values[0] == "":
        return default
    try:
        return int(values[0])
    except ValueError:
        raise GuiError(f"{key}={values[0]!r} is not an integer", where=[key]) from None


def _window(s: GuiSession, q: dict, _body: dict) -> dict:
    return s.result_window(lo=_query_float(q, "lo"), hi=_query_float(q, "hi"),
                           max_points=_query_int(q, "max_points", 4000))


def _diff(s: GuiSession, q: dict, _body: dict) -> dict:
    a, b = q.get("a", [""])[0], q.get("b", [""])[0]
    if not a or not b:
        raise GuiError("diff needs ?a=<node>&b=<node>", where=["a", "b"])
    return s.history_diff(a, b)


def _compare(s: GuiSession, q: dict, _body: dict) -> dict:
    ids = [i for i in ",".join(q.get("ids", [])).split(",") if i]
    if not ids:
        raise GuiError("compare needs ?ids=n0001,n0002", where=["ids"])
    return s.history_compare(ids)


def _structure3d(s: GuiSession, q: dict, _body: dict) -> dict:
    """Geometry for one phase.  Both knobs are *drawing* thresholds, not physics,
    which is why they ride here rather than in a settings document: the
    probability level an ellipsoid is drawn at and the radius-sum slack a bond is
    drawn at say nothing about the model, and persisting either would make one
    picture the project's opinion."""
    return s.structure3d(_query_int(q, "phase", 0),
                         probability=_query_float(q, "probability") or 0.5,
                         bond_tolerance=_query_float(q, "bond_tolerance"))


def _series_window(s: GuiSession, q: dict, _body: dict) -> dict:
    """One series member's curves.  ``index`` is required and is not defaulted to
    0: a window of "whichever pattern" is not a question anyone asks, and a
    silent default would draw pattern 0 under another one's label."""
    if not q.get("index") or q["index"][0] == "":
        raise GuiError("series window needs ?index=<pattern>", where=["index"])
    return s.series_window(_query_int(q, "index", 0),
                           lo=_query_float(q, "lo"), hi=_query_float(q, "hi"),
                           max_points=_query_int(q, "max_points", 4000))


def _series_history(s: GuiSession, q: dict, _body: dict) -> dict:
    if not q.get("index") or q["index"][0] == "":
        raise GuiError("series history needs ?index=<pattern>", where=["index"])
    return s.series_history(_query_int(q, "index", 0))


def _report(s: GuiSession, q: dict, _body: dict) -> dict:
    plan = q.get("plan", [None])[0]
    return s.report(plan=plan or None)


#: ``(method, path) → handler(session, query, body)``.  Exact matches only: the
#: surface has no path parameters (ids travel as query strings or in the body),
#: which keeps this table readable as the wire contract it is.
ROUTES: dict[tuple[str, str], Any] = {
    ("GET", "/api/capabilities"): lambda s, q, b: s.capabilities(),
    ("GET", "/api/version"): lambda s, q, b: s.version(),

    ("POST", "/api/project/new"): lambda s, q, b: s.project_new(b),
    ("POST", "/api/project/open"): lambda s, q, b: s.project_open(b),
    ("GET", "/api/project"): lambda s, q, b: s.project_doc(),
    ("POST", "/api/project"): lambda s, q, b: s.project_patch(b),
    ("POST", "/api/project/save"): lambda s, q, b: s.project_save(),
    ("GET", "/api/recent"): lambda s, q, b: {"recent": s.recent()},
    # the app's own `ui` keys, beside the recent list because both are the
    # *person's* rather than a project's (WP-1043)
    ("GET", "/api/settings"): lambda s, q, b: s.settings(),
    ("POST", "/api/settings"): lambda s, q, b: s.settings_patch(b),

    ("GET", "/api/params"): lambda s, q, b: s.params(),
    ("PATCH", "/api/params"): lambda s, q, b: s.params_patch(b),
    ("GET", "/api/plan"): lambda s, q, b: s.plan(),
    ("PUT", "/api/plan"): lambda s, q, b: s.plan_put(b),
    ("GET", "/api/plans"): lambda s, q, b: s.plans(),
    ("GET", "/api/structure"): lambda s, q, b: s.structure(),
    ("GET", "/api/structure3d"): _structure3d,
    ("PATCH", "/api/structure"): lambda s, q, b: s.structure_patch(b),
    ("POST", "/api/structure/aniso"): lambda s, q, b: s.structure_aniso(b),
    # symmetry is three routes rather than one because they are three costs: the
    # GET runs a spglib search per atom (WP-1035), the preview builds a candidate
    # parameter table per atom, and only the last of them writes a history node
    ("GET", "/api/structure/symmetry"):
        lambda s, q, b: s.structure_symmetry(_query_int(q, "phase", 0)),
    ("POST", "/api/structure/symmetry/preview"):
        lambda s, q, b: s.symmetry_preview(b),
    ("POST", "/api/structure/symmetry"): lambda s, q, b: s.symmetry_patch(b),
    ("GET", "/api/instrument"): lambda s, q, b: s.instrument(),
    ("PATCH", "/api/instrument"): lambda s, q, b: s.instrument_patch(b),

    ("POST", "/api/run"): lambda s, q, b: s.run(b),
    ("POST", "/api/cancel"): lambda s, q, b: s.cancel(),
    ("GET", "/api/run/state"): lambda s, q, b: s.run_state(),

    ("GET", "/api/result"): lambda s, q, b: s.result(),
    ("GET", "/api/result/window"): _window,
    ("GET", "/api/report"): _report,
    ("POST", "/api/report/apply"): lambda s, q, b: s.report_apply(b),

    ("GET", "/api/textdoc"): lambda s, q, b: s.textdoc(),
    ("PUT", "/api/textdoc"): lambda s, q, b: s.textdoc_put(b),

    ("GET", "/api/peaks"): lambda s, q, b: s.peaks(),
    ("POST", "/api/peaks"): lambda s, q, b: s.peaks_pick(b),
    ("POST", "/api/peaks/add"): lambda s, q, b: s.peaks_add(b),
    ("POST", "/api/peaks/remove"): lambda s, q, b: s.peaks_remove(b),
    ("POST", "/api/peaks/move"): lambda s, q, b: s.peaks_move(b),
    ("POST", "/api/peaks/flag"): lambda s, q, b: s.peaks_flag(b),
    ("POST", "/api/peaks/refit"): lambda s, q, b: s.peaks_refit(b),
    # /api/index rides the one run state machine: same worker, same 409
    ("POST", "/api/index"): lambda s, q, b: s.run({**b, "kind": "index"}),
    ("GET", "/api/index/result"): lambda s, q, b: s.index_result(),
    ("POST", "/api/index/adopt"): lambda s, q, b: s.index_adopt(b),
    # the extinction screen rides the same machine (WP-1025 served)
    ("POST", "/api/index/extinction"):
        lambda s, q, b: s.run({**b, "kind": "extinction"}),
    ("GET", "/api/index/extinction"): lambda s, q, b: s.index_extinction(),

    # a series is N patterns *outside* the project's single-pattern document
    # (WP-1016), so it is a route family of its own — and its run rides the one
    # run machine, exactly as /api/index does
    ("GET", "/api/series"): lambda s, q, b: s.series(),
    ("PUT", "/api/series"): lambda s, q, b: s.series_put(b),
    ("POST", "/api/series/run"): lambda s, q, b: s.run({**b, "kind": "series"}),
    ("GET", "/api/series/result"): lambda s, q, b: s.series_result(),
    ("GET", "/api/series/window"): _series_window,
    ("GET", "/api/series/history"): _series_history,

    ("GET", "/api/history"): lambda s, q, b: s.history(),
    ("GET", "/api/history/diff"): _diff,
    ("GET", "/api/history/compare"): _compare,
    ("POST", "/api/history/checkout"): lambda s, q, b: s.history_checkout(b),
    ("POST", "/api/history/branch"): lambda s, q, b: s.history_branch(b),
    ("POST", "/api/history/tag"): lambda s, q, b: s.history_tag(b),
    ("POST", "/api/history/annotate"): lambda s, q, b: s.history_annotate(b),
}

for _kind in ("cif", "reflections", "qpa", "html", "result_json"):
    ROUTES[("POST", f"/api/export/{_kind}")] = (
        lambda s, q, b, _k=_kind: s.export(_k, b))
del _kind

#: ``(method, path) → upload kind``.  The **only** routes in this surface whose
#: body is not JSON: a file goes up as its own bytes, and its name and options
#: travel in the query string.  Base64 in a JSON envelope was the alternative and
#: buys nothing — it inflates the body by a third and still needs the same cap —
#: while multipart would mean parsing a format the stdlib no longer ships a
#: parser for (``cgi`` is gone in 3.13).  Kept as a third table rather than a
#: branch inside :data:`ROUTES` so "the route table is the wire contract" stays
#: true and a test can assert the three tables are disjoint.
UPLOAD_ROUTES: dict[tuple[str, str], str] = {
    ("POST", f"/api/upload/{kind}"): kind for kind in UPLOAD_KINDS}


def _upload_options(query: dict) -> dict:
    """The reader keywords an upload may carry, off the query string.

    ``aniso`` is the checkbox that mirrors ``structure_from_cif(aniso=)`` and
    ``block`` names a pdCIF data block — both are *re-read* options, which is why
    they belong on the upload route rather than only on the commit that follows.
    """
    options: dict[str, Any] = {}
    if query.get("aniso"):
        options["aniso"] = query["aniso"][0].lower() not in ("", "0", "false")
    for key in ("phase_name", "block"):
        if query.get(key) and query[key][0]:
            options[key] = query[key][0]
    return options


# ----------------------------------------------------------------------
# the handler
# ----------------------------------------------------------------------
def _plotly_js() -> str:
    """plotly.js out of the installed package — ``compare_app``'s trick."""
    try:
        from plotly.offline import get_plotlyjs
    except ImportError:  # pragma: no cover - exercised by the missing-dep path
        return ("window.__PXRDREF_NO_PLOTLY__ = true;\n"
                "console.error('pxrdref gui: plotly is not installed — "
                "pip install \\'pxrd-refine[gui]\\'');")
    return get_plotlyjs()


def _handler(session: GuiSession, holder: dict):
    class Handler(http.server.BaseHTTPRequestHandler):
        server_version = "pxrdref-gui"
        # HTTP/1.0 semantics: no chunked encoding to arrange and a connection
        # that closes when a handler returns, which is what makes the SSE route
        # a plain write loop.
        protocol_version = "HTTP/1.0"

        def log_message(self, *args) -> None:  # the poll traffic would flood
            pass

        # -- plumbing ------------------------------------------------
        def _send(self, body: bytes, content_type: str, code: int = 200) -> None:
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        def _json(self, payload: Any, code: int = 200) -> None:
            self._send(_dumps(payload).encode("utf-8"),
                       "application/json; charset=utf-8", code)

        def _error(self, exc: GuiError) -> None:
            self._json(exc.payload(), exc.status)

        def _body(self) -> dict:
            length = int(self.headers.get("Content-Length") or 0)
            if not length:
                return {}
            raw = self.rfile.read(length)
            try:
                parsed = json.loads(raw or b"{}")
            except ValueError as exc:
                raise GuiError(f"request body is not JSON: {exc}") from None
            if not isinstance(parsed, dict):
                raise GuiError("request body must be a JSON object")
            return parsed

        def _raw_body(self) -> bytes:
            """The body as bytes — the upload routes' half of ``_body``.

            The cap is checked against the *declared* length before a byte is
            read, because reading first and refusing after is how a 4 GB
            ``Content-Length`` becomes this process's memory.
            """
            length = int(self.headers.get("Content-Length") or 0)
            if length > MAX_UPLOAD_BYTES:
                raise GuiError(
                    f"{length} bytes is over the {MAX_UPLOAD_BYTES}-byte upload "
                    "limit", code="UPLOAD_TOO_LARGE", status=413)
            return self.rfile.read(length) if length else b""

        def _origin_ok(self) -> bool:
            """Reject cross-site drivers; a same-origin fetch sends no Origin.

            The check is the one thing standing between a localhost API and any
            page the user happens to have open, since a browser will resolve a
            hostile domain to 127.0.0.1 if its DNS says so (rebinding).  Both
            headers are checked because ``Host`` alone is what rebinding
            defeats.
            """
            for header in ("Origin", "Referer"):
                value = self.headers.get(header)
                if not value:
                    continue
                host = urlparse(value).hostname or ""
                if host not in _ALLOWED_HOSTS:
                    return False
            host = (self.headers.get("Host") or "").rsplit(":", 1)[0]
            return host in _ALLOWED_HOSTS

        # -- dispatch ------------------------------------------------
        def do_GET(self) -> None:  # noqa: N802 - stdlib API
            self._dispatch("GET")

        def do_HEAD(self) -> None:  # noqa: N802 - stdlib API
            self._dispatch("GET")

        def do_POST(self) -> None:  # noqa: N802 - stdlib API
            self._dispatch("POST")

        def do_PATCH(self) -> None:  # noqa: N802 - stdlib API
            self._dispatch("PATCH")

        def do_PUT(self) -> None:  # noqa: N802 - stdlib API
            self._dispatch("PUT")

        def _dispatch(self, method: str) -> None:
            if not self._origin_ok():
                self._json({"error": {
                    "code": "FORBIDDEN_HOST",
                    "message": f"{self.headers.get('Host')!r} is not a loopback "
                               "host; pxrdref gui serves 127.0.0.1 only",
                    "where": []}}, 403)
                return
            parts = urlparse(self.path)
            path = parts.path.rstrip("/") or "/"
            query = parse_qs(parts.query, keep_blank_values=True)
            try:
                if method == "POST" and path == "/api/shutdown":
                    self._shutdown()
                    return
                if method == "GET" and path == "/api/events":
                    self._events(query)
                    return
                kind = UPLOAD_ROUTES.get((method, path))
                if kind is not None:
                    self._json(session.upload(
                        kind, data=self._raw_body(),
                        filename=query.get("filename", [""])[0],
                        token=query.get("upload", [""])[0],
                        options=_upload_options(query)))
                    return
                handler = ROUTES.get((method, path))
                if handler is not None:
                    body = self._body() if method != "GET" else {}
                    self._json(handler(session, query, body))
                    return
                if (method, path) in RESERVED_ROUTES:
                    owner = RESERVED_ROUTES[(method, path)]
                    self._json({"error": {
                        "code": "NOT_IMPLEMENTED",
                        "message": f"{method} {path} is reserved for {owner}; the "
                                   "path is settled, the behaviour is not here yet",
                        "where": []}}, 404)
                    return
                if method == "GET":
                    self._static(path)
                    return
                self._json({"error": {"code": "NOT_FOUND",
                                      "message": f"no route {method} {path}",
                                      "where": []}}, 404)
            except GuiError as exc:
                self._error(exc)
            except BrokenPipeError:  # pragma: no cover - client went away
                pass
            except Exception as exc:  # noqa: BLE001 — a 500 body beats a traceback
                self._json({"error": {
                    "code": "INTERNAL_ERROR",
                    "message": f"{type(exc).__name__}: {exc}",
                    "where": []}}, 500)

        # -- static --------------------------------------------------
        def _static(self, path: str) -> None:
            if path == "/plotly.js":
                self._send(_plotly_js().encode("utf-8"),
                           "application/javascript; charset=utf-8")
                return
            index = STATIC_DIR / "index.html"
            if path in ("/", "/index.html"):
                if index.is_file():
                    self._send(index.read_bytes(), "text/html; charset=utf-8")
                else:
                    self._send(_PLACEHOLDER.encode("utf-8"),
                               "text/html; charset=utf-8")
                return
            target = (STATIC_DIR / path.lstrip("/")).resolve()
            root = STATIC_DIR.resolve()
            if not target.is_relative_to(root) or not target.is_file():
                self._json({"error": {
                    "code": "NOT_FOUND",
                    "message": f"no static asset {path} (the built frontend "
                               "lands in WP-1010)", "where": []}}, 404)
                return
            self._send(target.read_bytes(),
                       _CONTENT_TYPES.get(target.suffix, "application/octet-stream"))

        # -- events --------------------------------------------------
        def _events(self, query: dict) -> None:
            since = _query_int(query, "since", 0)
            if query.get("poll"):
                self._json(session.events_since(since))
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Accel-Buffering", "no")  # no proxy buffering
            self.end_headers()
            state_key = ""
            last_beat = time.monotonic()
            try:
                while not session.closed:
                    events, since, frame, state_key = session.follow(
                        since, state_key, timeout=1.0)
                    for event in events:
                        self._frame("event", event, seq=event["seq"])
                    if frame is not None:
                        self._frame("state", frame)
                    if events or frame is not None:
                        last_beat = time.monotonic()
                    elif time.monotonic() - last_beat > _SSE_HEARTBEAT:
                        self.wfile.write(b": keepalive\n\n")
                        self.wfile.flush()
                        last_beat = time.monotonic()
            except (BrokenPipeError, ConnectionResetError, OSError):
                pass  # the client closed the tab; nothing to clean up

        def _frame(self, name: str, payload: dict, seq: int | None = None) -> None:
            chunk = "" if seq is None else f"id: {seq}\n"
            # the same encoder the JSON routes use: an event's `data` is an open
            # dict, so a non-finite value in it would break `JSON.parse` in the
            # stream's listener exactly as it would in a response body
            chunk += f"event: {name}\ndata: {_dumps(payload)}\n\n"
            self.wfile.write(chunk.encode("utf-8"))
            self.wfile.flush()

        # -- shutdown ------------------------------------------------
        def _shutdown(self) -> None:
            self._json({"stopping": True})
            session.close()  # release the SSE followers first
            server = holder.get("server")
            if server is not None:
                threading.Thread(target=server.shutdown, daemon=True).start()

    return Handler


# ----------------------------------------------------------------------
# serving
# ----------------------------------------------------------------------
def build_server(session: GuiSession, *, port: int = DEFAULT_PORT):
    """A bound ``ThreadingHTTPServer``, falling back to an ephemeral port.

    A busy port is the ordinary case, not an error: a second window, or a
    previous run that has not exited yet.  Refusing to start would be the wrong
    answer for a GUI, and the printed URL (or the ``--machine`` line) is where
    the real port is read from anyway.
    """
    holder: dict = {}
    handler = _handler(session, holder)
    try:
        httpd = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
    except OSError:
        httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    httpd.daemon_threads = True
    holder["server"] = httpd
    return httpd


def serve(session: GuiSession, *, port: int = DEFAULT_PORT,
          open_browser: bool = True, machine: bool = False,
          block: bool = True):
    """Serve ``session``; returns the server when ``block=False`` (tests)."""
    httpd = build_server(session, port=port)
    actual = httpd.server_address[1]
    url = f"http://127.0.0.1:{actual}/"
    if machine:
        # one line, first, so a supervising process (Tauri) can read the port
        # without parsing prose
        print(json.dumps({"url": url, "port": actual,
                          "project": session.version()["project"],
                          "pid": session.version()["pid"]}), flush=True)
    else:
        project = session.version()["project"]
        # flush: redirecting the banner to a log file otherwise buffers it until
        # the process exits, which is exactly when nobody needs to read the port
        print(f"pxrdref gui — {url}", flush=True)
        print(f"  project: {project or '(none open yet)'}", flush=True)
        if not (STATIC_DIR / "index.html").is_file():
            print("  frontend: not built — run `npm --prefix gui run build`; "
                  "the HTTP API is live either way", flush=True)
        print("  Ctrl-C to stop", flush=True)
    if open_browser:
        import webbrowser

        webbrowser.open(url)
    if not block:
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        return httpd
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        session.close()
        httpd.server_close()
    return httpd


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        prog="pxrdref gui",
        description="Serve the pxrd-refine GUI for a project on localhost.")
    parser.add_argument("project", nargs="?", default=None,
                        help="a .pxrd project directory to open on boot")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--no-open", action="store_false", dest="open_browser",
                        help="do not open a browser window")
    parser.add_argument("--machine", action="store_true",
                        help="print one JSON boot line (url, port, project, pid)")
    parser.add_argument("--backend", default="numpy",
                        help="Jacobian backend (see pxrdref.capabilities())")
    parser.add_argument("--solver", default="trf")
    args = parser.parse_args(argv)

    project = None
    if args.project is not None:
        try:
            project = Project.open(args.project, backend=args.backend,
                                   solver=args.solver)
        except (FileNotFoundError, ValueError) as exc:
            # the refusal messages name seven different remedies; printing the
            # one that applies is the whole value of them
            print(f"pxrdref gui: {exc}")
            return 2
    session = GuiSession(project, backend=args.backend, solver=args.solver)
    serve(session, port=args.port, open_browser=args.open_browser,
          machine=args.machine)
    return 0


def _free_port() -> int:  # pragma: no cover - helper for scripts and tests
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


# ----------------------------------------------------------------------
_PLACEHOLDER = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>pxrdref gui</title>
<style>
 :root { color-scheme: light dark; }
 body { margin:0; padding:2.5rem clamp(1rem, 5vw, 4rem); max-width:70ch;
        font:14px/1.55 ui-sans-serif, system-ui, sans-serif; }
 h1 { font-size:1.15rem; margin:0 0 .2rem; }
 p.sub { opacity:.7; margin:0 0 1.6rem; }
 code { font:12.5px ui-monospace, Menlo, monospace; }
 li { margin:.15rem 0; }
 .m { display:inline-block; min-width:4.2em; opacity:.65; }
</style></head><body>
<h1>pxrdref gui — server running, frontend not built</h1>
<p class="sub">The Svelte app is WP-1010. The HTTP API below is live now, and
every route is a method on <code>pxrdref.gui.GuiSession</code>.</p>
<ul>
 <li><span class="m">GET</span> <code>/api/capabilities</code> — what this build can do</li>
 <li><span class="m">GET</span> <code>/api/project</code> · <code>/api/params</code> ·
     <code>/api/plan</code> · <code>/api/structure</code> · <code>/api/instrument</code></li>
 <li><span class="m">POST</span> <code>/api/run</code> · <code>/api/cancel</code> ·
     <span class="m">GET</span> <code>/api/run/state</code></li>
 <li><span class="m">GET</span> <code>/api/events</code> — SSE (<code>?since=</code> replay,
     <code>?poll=1</code> JSON fallback)</li>
 <li><span class="m">GET</span> <code>/api/result</code> ·
     <code>/api/result/window?lo=&amp;hi=</code> · <code>/api/report</code></li>
 <li><span class="m">GET</span> <code>/api/history</code> ·
     <span class="m">POST</span> <code>/api/history/checkout</code></li>
 <li><span class="m">GET</span>/<span class="m">PUT</span> <code>/api/textdoc</code>
     — the project as text (<code>.pxt</code>), compare-and-set on a revision</li>
 <li><span class="m">POST</span> <code>/api/export/{cif,reflections,qpa,html,result_json}</code></li>
 <li><span class="m">GET</span>/<span class="m">POST</span> <code>/api/peaks</code>
     (+ <code>add/move/remove/flag/refit</code>) ·
     <span class="m">POST</span> <code>/api/index</code> ·
     <span class="m">GET</span> <code>/api/index/result</code> ·
     <code>/api/index/extinction</code> · <span class="m">POST</span>
     <code>/api/index/adopt</code></li>
</ul>
</body></html>
"""

"""``rietx watch`` — a window into the refinements under a directory.

With no argument it scans the working directory and lists every run beneath it,
live ones and finished ones together, and opening one shows its plot and its
event log. With a directory argument that *is* a run it opens straight onto
that run, so ``rietx watch live/`` keeps working exactly as it did.

This module is **transport only**, the split ``gui/server.py`` declares for
itself. Finding runs, deciding whether one is still being written and tailing
its log are :mod:`rietx.runs`, which has no HTTP in it and which
``gui/session.py`` can import when it attaches to a foreign run.

**The page is files, in** ``static/`` (WP-1430): an ``index.html``, a
stylesheet and two ES modules, served by :meth:`_Handler._static`. It was a
python string until seven WPs queued up against it, at which point the string
was costing an editor, a unit test and every merge. ``watch-core.mjs`` is the
half that touches no DOM and the suite runs it through ``node --test``;
``watch.mjs`` owns the document. What the page cannot know about this build
travels on the first ``/api/runs`` (:func:`_page_constants`).

**The watcher has one verb, and it is stop** (WP-1405). Everything else reads:
it opens no project, constructs no refinement, and offers the GUI as a command
to copy rather than a thing it launches. Stopping is the exception because it
is the one thing a reader cannot do from the other side, and it stays honest by
being the *only* one — ``POST /api/run/<id>/cancel`` writes
:data:`~rietx.runs.CANCEL_FILE` into a directory the walk already offered, and
the fit's own token is what acts on it. ``--read-only`` serves without it, for
a reader who is not the person who should be stopping things.

**A click here raises in another process.** That is the sharpest fact in this
module: a fit that did not ask to be cancellable is cancellable, and a script
that does not catch ``RefinementCancelled`` prints a traceback. It is why the
button takes two clicks, why the dialog says so in as many words, and why it
has no keyboard shortcut.

Run the refinement in one process::

    ref.fit(data, events=LiveSession("live/"))

and the viewer in another::

    rietx watch                  # every run under the working directory
    rietx watch live/            # straight onto one
"""

from __future__ import annotations

import functools
import http.server
import json
import os
import threading
import time
import urllib.parse
from pathlib import Path

from .. import runs as runs_mod
from .._about import DIST_NAME, LIVE_DIR_NAME, PROJECT_SUFFIX
from ..viz import theme as theme_mod
from ..viz.plotlyjs import CONTENT_TYPE as PLOTLY_CONTENT_TYPE
from ..viz.plotlyjs import plotly_js
from ..viz.plots import PALETTES

#: What a missing plotly says, in the pane the plot would have filled. Each
#: page that serves plotly owns its own fallback (``viz/plotlyjs.py``), and
#: this one has a shell worth keeping: the run list and the event log work
#: without a plotting library, so only the plot pane reports the absence.
_NO_PLOTLY_JS = (f"console.error('{DIST_NAME} watch: plotly is not installed "
                 f"\u2014 pip install \\'{DIST_NAME}[viz]\\'');")

#: The page, as files in the package — ``gui/server.py``'s ``STATIC_DIR`` one
#: rank down (WP-1430). A page quoted inside python is a page no editor lints,
#: no test imports and no merge resolves; this one had reached 90 lines of CSS
#: and 520 of javascript with ``node --check`` as its whole check.
STATIC_DIR = Path(__file__).parent / "static"

#: What the page is made of, and what each file is served as. A fixed table
#: rather than a directory served whole: four names cannot be walked out of,
#: and the static fallback below is rooted at somebody's run directory rather
#: than here.
STATIC_FILES = {
    "index.html": "text/html; charset=utf-8",
    "watch.css": "text/css; charset=utf-8",
    "watch.mjs": "text/javascript; charset=utf-8",
    "watch-core.mjs": "text/javascript; charset=utf-8",
}


def _page_constants() -> dict:
    """What the page cannot know about the build serving it.

    These were ``@TOKEN@`` substitutions into the page's text while the page
    was a python string, which a file cannot carry. A literal ``.rex`` in the
    page would be invisible to every test in the suite (``_about.py``).

    ``theme`` is the *choice* and not a resolved answer, and it rides here
    rather than being read once at boot because it is the one thing on this
    page a person changes while the page is open: the GUI writes it
    (WP-1044), every poll carries it, and the page re-stamps without a reload
    (WP-1429).  Every colour a *curve* is drawn in left this payload with that
    WP — those are custom properties the page reads off its own root element,
    so one stylesheet answers for all three surfaces.

    ``ticks`` did not, and the reason is the one WP-1429 could not settle. A
    reflection row per phase is a **categorical** set, and the GUI has none to
    lend: its `--plot-*` tokens each name one role, and its own tick rows take
    plotly's colorway, which is indexed by position in the trace array — so
    the row a phase owns changes colour at the stage that frees the background
    (measured, and `#d62728` at 0.043 from `--plot-calc` on the light theme,
    a third of the distance the curve colours themselves are held apart by). This page keeps the phase list it has always used,
    :data:`~rietx.viz.plots.PALETTES`, until somebody decides what a shared
    categorical palette should be.
    """
    return {"suffix": PROJECT_SUFFIX, "dist": DIST_NAME,
            "theme": theme_mod.theme_choice(),
            "ticks": {"one": PALETTES["dark"]["tick"],
                      "phase": PALETTES["dark"]["phase"]}}


#: How long a walk's result stands before the next request pays for another.
#: Shorter than the page's poll, so an open tab still sees a new run within a
#: poll or two, and short enough that a human refreshing by hand never waits.
INDEX_TTL_SECONDS = 1.0

#: The hosts a request carrying the one verb may claim to come from — the same
#: set ``gui/server.py`` keeps, and kept separately for the same reason the two
#: servers are separate modules. Binding ``127.0.0.1`` is not on its own enough:
#: any page the reader happens to have open can send a cross-origin ``POST``
#: with no preflight, and a hostile domain whose DNS answers ``127.0.0.1``
#: becomes same-origin, at which point the run ids are readable too.
_ALLOWED_HOSTS = frozenset({"127.0.0.1", "localhost", "[::1]", "::1"})


class _RunIndex:
    """One walk shared by the requests that arrive together.

    The detail page asks for the run and then for its events, so an uncached
    :func:`~rietx.runs.discover` would walk the whole tree twice per poll, per
    open tab — and the walk is the expensive half of every route here. One
    shared result behind a lock is also what stops a burst of parallel requests
    on :class:`~http.server.ThreadingHTTPServer` from starting a walk each.
    """

    def __init__(self, root: Path, ttl: float = INDEX_TTL_SECONDS):
        self.root = root
        self.ttl = ttl
        self._lock = threading.Lock()
        self._runs: list | None = None
        self._at = 0.0
        # Runs already read, keyed on what their files say about themselves
        # (WP-1427). The TTL above bounds how often the tree is *walked*; this
        # bounds what each walk re-reads, which is the larger half: on 500
        # finished runs the two sidecar reads and their two parses were 21.8 ms
        # of a 34.7 ms walk, once a second, about nothing. `discover` prunes it
        # to what the walk found, so a run that goes away leaves no entry.
        self._cache: dict = {}

    def runs(self) -> list:
        with self._lock:
            now = time.monotonic()
            if self._runs is None or now - self._at >= self.ttl:
                self._runs = runs_mod.discover(self.root, cache=self._cache)
                self._at = now
            return self._runs


class _Handler(http.server.SimpleHTTPRequestHandler):
    """Routes, and a static fallback rooted at the scanned directory.

    The fallback is what keeps ``rietx watch live/`` working for anything that
    already links at ``fit.html`` or ``events.jsonl`` by their bare names — a
    run recorded before WP-1402 included.
    """

    def __init__(self, *args, scan_root: Path, index: _RunIndex,
                 allow_cancel: bool = True, **kwargs):
        # set before super().__init__, which handles the request inline
        self.scan_root = scan_root
        self.index = index
        self.allow_cancel = allow_cancel
        self._marks: list[tuple[str, float]] = []
        super().__init__(*args, **kwargs)

    def _timed(self, name: str, call):
        """Run ``call``, and remember what it cost this request.

        The marks go out as ``Server-Timing``, which is the documented header
        for exactly this (MDN). A browser shows it in the network panel beside
        the request it belongs to, and a python test reads it off the response
        with no profiler and no clock of its own. That second reader is why the
        phases are named for what they do rather than for the function that
        does it: ``walk`` stays ``walk`` when :class:`_RunIndex` changes shape.
        """
        started = time.perf_counter()
        try:
            return call()
        finally:
            self._marks.append((name, (time.perf_counter() - started) * 1e3))

    def _send(self, body: bytes, content_type: str, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        if self._marks:
            self.send_header("Server-Timing", ", ".join(
                f"{name};dur={ms:.3f}" for name, ms in self._marks))
        self.end_headers()
        self.wfile.write(body)

    def _static(self, name: str) -> None:
        """One of the page's own files, out of the installed package.

        Read per request, like the plotly route below: the four of them are
        32 kB and a page fetches each once, so nothing here is on a path that
        runs per stage. ``no-store`` comes from :meth:`_send` and is wanted —
        a reader who restarts the watcher after an upgrade must not be served
        the old script out of their own cache.
        """
        self._send((STATIC_DIR / name).read_bytes(), STATIC_FILES[name])

    def _json(self, payload, status: int = 200) -> None:
        body = self._timed(
            "serialize", lambda: json.dumps(payload).encode("utf-8"))
        self._send(body, "application/json; charset=utf-8", status)

    def _origin_ok(self) -> bool:
        """Whether a write may be honoured — ``gui/server.py``'s check, here.

        Only the verb asks. Reading is served to whoever reaches the port, as
        it was before WP-1405, and the reason this exists is that the verb
        raises in another process: without it, any page the reader has open
        could ``POST`` ``/api/run/<id>/cancel`` and stop an overnight
        refinement. A same-origin fetch sends no ``Origin``, so an absent
        header is not a failure; ``Host`` is checked as well because ``Host``
        alone is what DNS rebinding defeats.
        """
        for header in ("Origin", "Referer"):
            value = self.headers.get(header)
            if not value:
                continue
            if (urllib.parse.urlparse(value).hostname or "") not in _ALLOWED_HOSTS:
                return False
        host = (self.headers.get("Host") or "").rsplit(":", 1)[0]
        return host in _ALLOWED_HOSTS

    def handle_one_request(self):  # noqa: D102 - http.server API
        # A keep-alive connection serves many requests through one handler
        # object, and the header is a fact about one of them.
        self._marks = []
        super().handle_one_request()

    def _runs(self) -> list:
        return self._timed("walk", self.index.runs)

    def _find(self, run_id: str):
        """An id is looked up in what the walk offered, never decoded into a
        path. That is why a request cannot name a directory we did not choose
        to serve."""
        for run in self._runs():
            if run.run_id == run_id:
                return run
        return None

    def _row(self, run) -> dict:
        live = runs_mod.liveness_of(run)
        row = run.as_dict()
        row["liveness"] = {"state": live.state, "evidence": live.evidence,
                           "heartbeat_age": live.heartbeat_age}
        # the picture is rewritten per stage, so the page needs to know when to
        # redraw rather than sit on the one it opened with.  The mtime is of
        # whichever file this run actually has: a legacy run's is its page's.
        name = (runs_mod.SNAPSHOT_FILE if run.has_snapshot
                else runs_mod.LEGACY_SNAPSHOT_FILE)
        try:
            row["snapshot_mtime"] = (run.path / name).stat().st_mtime
        except OSError:
            row["snapshot_mtime"] = None
        # a command a human can copy, not a verb this app performs: launching
        # the GUI is a process boundary and stays one (WP-1401 § the decision)
        project = run.path.parent
        row["gui_command"] = None
        if (run.path.name == LIVE_DIR_NAME
                and project.name.endswith(PROJECT_SUFFIX)):
            # the path as typed from where the scan started, not the bare name:
            # a project one directory down is not `rietx gui sample.rex` from
            # here
            try:
                where = os.path.relpath(project, self.scan_root)
            except ValueError:                      # pragma: no cover - Windows
                where = str(project)
            row["gui_command"] = f"{DIST_NAME} gui {where}"
        return row

    def do_GET(self):  # noqa: N802 - http.server API
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        if path in ("/", "/index.html"):
            self._static("index.html")
            return

        # the page's own files, before the fallback: a run directory holding a
        # `watch.css` of its own does not get to replace the page's
        name = path.lstrip("/")
        if name in STATIC_FILES:
            self._static(name)
            return

        if path == theme_mod.CSS_ROUTE:
            # generated rather than served off disk: `viz/theme.py` is the
            # authority and `gui/src/tokens.css` is the copy, not the reverse
            self._send(theme_mod.tokens_css().encode("utf-8"),
                       theme_mod.CSS_CONTENT_TYPE)
            return

        if path == "/plotly.js":
            # out of the installed package, so the page works air-gapped and
            # nothing vendors a copy (viz/plotlyjs.py)
            self._send(plotly_js(_NO_PLOTLY_JS).encode("utf-8"),
                       PLOTLY_CONTENT_TYPE)
            return

        if path == "/api/runs":
            found = self._runs()
            single = (found[0].run_id
                      if len(found) == 1 and found[0].path == self.scan_root
                      else None)
            self._json({"root": str(self.scan_root),
                        "single_run_id": single,
                        # the page draws no button under --read-only; the route
                        # refuses anyway, and a button that only ever 403s
                        # would be a worse answer than no button
                        "can_cancel": self.allow_cancel,
                        # read once, at boot, and 299 B of every poll after
                        # that — 1 % of a 41-run answer, whose rows are 735 B
                        # each. A route of its own would save that and make a
                        # second authority for what this server is.
                        "page": _page_constants(),
                        "runs": self._timed(
                            "rows", lambda: [self._row(r) for r in found])})
            return

        parts = [p for p in path.split("/") if p]
        if len(parts) >= 3 and parts[0] == "api" and parts[1] == "run":
            run = self._find(parts[2])
            if run is None:
                self._json({"error": "no such run"}, status=404)
                return
            rest = parts[3] if len(parts) > 3 else ""
            if rest == "":
                self._json(self._row(run))
                return
            if rest == "events":
                def _int(name):
                    try:
                        return int(query.get(name, [""])[0])
                    except (TypeError, ValueError):
                        return None

                def _limit():
                    value = _int("limit")
                    return value if value is not None and value > 0 else None
                # the cap is the page's, passed in rather than known here:
                # `MAX_LINES` lives in `watch.mjs` beside the pane it bounds,
                # and a second copy of it in python is a second authority for
                # how many lines a console keeps. An absent or junk `limit` is
                # no cap, which is what this route did before WP-1427.
                tail = self._timed("tail", lambda: runs_mod.tail_events(
                    run.path / runs_mod.EVENTS_FILE,
                    _int("offset") or 0, inode=_int("inode"),
                    max_events=_limit()))
                self._json({"events": tail.events, "offset": tail.offset,
                            "inode": tail.inode, "reset": tail.reset,
                            "bad_lines": tail.bad_lines, "size": tail.size,
                            "skipped": tail.skipped})
                return
            if rest in ("snapshot", "legacy"):
                # served as bytes, never parsed here: the reader constructs
                # nothing, and a half-written file is the writer's to make
                # atomic (it does)
                name = (runs_mod.SNAPSHOT_FILE if rest == "snapshot"
                        else runs_mod.LEGACY_SNAPSHOT_FILE)
                kind = ("application/json; charset=utf-8" if rest == "snapshot"
                        else "text/html; charset=utf-8")
                try:
                    body = self._timed("read",
                                       (run.path / name).read_bytes)
                except OSError:
                    self._send(b"no snapshot yet", "text/plain; charset=utf-8",
                               status=404)
                    return
                self._send(body, kind)
                return
            self._json({"error": "no such route"}, status=404)
            return

        super().do_GET()

    def do_POST(self):  # noqa: N802 - http.server API
        """The one verb (WP-1405): ``/api/run/<id>/cancel``.

        POST and never GET. A GET that cancels is one prefetching browser, one
        link preview or one crawler away from stopping somebody's overnight
        refinement, and the static fallback below serves GET to a whole tree.

        ``SimpleHTTPRequestHandler`` has no ``do_POST`` at all, so defining one
        means every other POST is answered here rather than by a 501 from the
        base class.

        POST is not enough on its own, which is what :meth:`_origin_ok` is for:
        a cross-origin POST with no body needs no preflight, so a page the
        reader has open in another tab can send this one. Binding
        ``127.0.0.1`` does not help there, and DNS rebinding hands that page
        the run ids as well.
        """
        # drained before anything is written back, or a keep-alive connection
        # reads the unread body as the next request line
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = 0
        if length > 0:
            capped = min(length, 1 << 16)
            self.rfile.read(capped)
            if capped < length:
                # the cap stops a declared gigabyte becoming this process's
                # memory, and then the connection has to go: the rest of that
                # body is still in the socket, and reusing the connection would
                # parse it as the next request — the desync this drain exists
                # to prevent
                self.close_connection = True

        if not self._origin_ok():
            self._json({"error": "this request did not come from the page "
                                 f"{DIST_NAME} watch serves"}, status=403)
            return

        parts = [p for p in urllib.parse.urlparse(self.path).path.split("/")
                 if p]
        if len(parts) == 4 and parts[:2] == ["api", "run"] and parts[3] == "cancel":
            self._cancel(parts[2])
            return
        self._json({"error": "no such route"}, status=404)

    def _cancel(self, run_id: str) -> None:
        """Ask one run to stop, or say why not.

        The id is looked up in what the walk offered (:meth:`_find`), so this
        route inherits WP-1401's property rather than restating it: a run id is
        never decoded into a path, and a request can only ever name a directory
        this server chose to serve. ``SimpleHTTPRequestHandler`` handles
        traversal for static files and a hand-written JSON route does not get
        that for free, which is why the lookup is the mechanism and not a
        check bolted beside one.

        Only a run that is **running here** is stoppable. ``unknown`` covers
        both another host and a writer that keeps no lock, and a request into
        either would lie in the directory until somebody deleted it.
        """
        if not self.allow_cancel:
            self._json({"error": "this watcher is serving read-only"},
                       status=403)
            return
        run = self._find(run_id)
        if run is None:
            self._json({"error": "no such run"}, status=404)
            return
        live = runs_mod.liveness_of(run)
        if live.state != "running":
            self._json({"error": f"this run reads {live.state} — "
                                 f"{live.evidence}", "state": live.state},
                       status=409)
            return
        # A latched recorder is still holding its lock and still reads running,
        # and it is the thing that would have read the request. Refusing says
        # so; writing the file would leave a button that did nothing.
        if run.status is not None and run.status.error:
            self._json({"error": "this run stopped recording, so nothing is "
                                 "reading requests: " + run.status.error,
                        "state": live.state}, status=409)
            return
        try:
            runs_mod.request_cancel(run.path, who=f"{DIST_NAME} watch")
        except OSError as exc:
            self._json({"error": f"could not write the request: {exc}"},
                       status=500)
            return
        self._json({"requested": True, "run_id": run_id, "state": live.state})

    def log_message(self, *args):  # quiet: polling floods the terminal
        pass


def serve(directory: str | Path | None = None, *, port: int = 8899,
          open_browser: bool = False, block: bool = True,
          allow_cancel: bool = True):
    """Serve the runs under ``directory`` (default: the working directory).

    Returns the server when ``block=False``. A directory that is itself a run
    is served as one and the page opens straight onto it.

    ``allow_cancel=False`` serves without the stop verb, and the page draws no
    button (``--read-only``).

    **Stopping is on by default, and that was the decision** (WP-1405). The
    argument for the other way is real: a click here raises in a process the
    reader cannot see, and making that a deliberate act by requiring a flag is
    cheap. Three things settled it the other way. The server binds
    ``127.0.0.1``, so the only person who can click is the person at the
    machine the fit is running on — who can already reach it with Ctrl-C, which
    raises in that process too. A flag you have to have set *in advance* is not
    there when a runaway starts, and killing the watcher to restart it with the
    flag is the moment you needed it. And the dialog already makes it a
    deliberate act, twice over. ``--read-only`` covers the case the argument is
    really about: a reader who is not the person who should be stopping things,
    which is a situation you know about beforehand.
    """
    directory = Path.cwd() if directory is None else Path(directory)
    if not directory.is_dir():
        raise FileNotFoundError(f"{directory} is not a directory")
    directory = directory.resolve()

    # `directory` is the static-file root SimpleHTTPRequestHandler wants;
    # `scan_root` is what the routes walk. Per instance, so two servers in one
    # process (the tests run several) cannot take each other's root.
    index = _RunIndex(directory)
    handler = functools.partial(_Handler, directory=str(directory),
                                scan_root=directory, index=index,
                                allow_cancel=allow_cancel)
    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
    url = f"http://127.0.0.1:{server.server_address[1]}/"
    found = index.runs()
    print(f"rietx watch: {len(found)} run(s) under {directory}")
    print(f"             {url}  (Ctrl-C to stop)")
    if not allow_cancel:
        print("             read-only: no stop button")
    if open_browser:
        import webbrowser

        webbrowser.open(url)
    if not block:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        return server
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return server


def main(argv: list[str] | None = None) -> None:
    import argparse

    parser = argparse.ArgumentParser(
        prog="rietx watch",
        description="list and watch the refinement runs under a directory")
    parser.add_argument("directory", nargs="?", default=None,
                        help="directory to scan (default: the working "
                             "directory); a directory that is itself a run "
                             "opens straight onto it")
    parser.add_argument("--port", type=int, default=8899)
    parser.add_argument("--open", action="store_true", help="open a browser")
    parser.add_argument("--read-only", action="store_true",
                        help="serve without the stop button: the page offers "
                             "no way to cancel a running fit, and the route "
                             "refuses")
    args = parser.parse_args(argv)
    serve(args.directory, port=args.port, open_browser=args.open,
          allow_cancel=not args.read_only)

"""``rietx watch`` — a window into the refinements under a directory.

With no argument it scans the working directory and lists every run beneath it,
live ones and finished ones together, and opening one shows its plot and its
event log. With a directory argument that *is* a run it opens straight onto
that run, so ``rietx watch live/`` keeps working exactly as it did.

This module is **transport only**, the split ``gui/server.py`` declares for
itself. Finding runs, deciding whether one is still being written and tailing
its log are :mod:`rietx.runs`, which has no HTTP in it and which
``gui/session.py`` can import when it attaches to a foreign run.

**The watcher has no verbs.** It reads; it never writes, never opens a project
and never constructs a refinement. Read-only is a stronger promise when an app
has no verbs than when a mode hides them — a user cannot click what is not
there. Cancel arrives in WP-1405 and will be the only one.

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
import threading
import urllib.parse
from pathlib import Path

from . import runs as runs_mod

_PAGE = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>rietx watch</title>
<style>
  :root { color-scheme: dark; }
  body { margin:0; font-family: ui-monospace, Menlo, monospace; font-size:12px;
         background:#111; color:#cdc; display:flex; flex-direction:column;
         height:100vh; }
  a { color:#9ad; text-decoration:none; }
  a:hover { text-decoration:underline; }
  #bar { background:#1c1c1c; border-bottom:1px solid #2c2c2c; padding:7px 12px;
         display:flex; gap:14px; align-items:center; flex:0 0 auto; }
  #root { color:#777; }
  #body { flex:1 1 auto; overflow:auto; }
  table { border-collapse:collapse; width:100%; }
  th { text-align:left; color:#777; font-weight:normal; padding:6px 12px;
       border-bottom:1px solid #2c2c2c; position:sticky; top:0;
       background:#151515; }
  td { padding:6px 12px; border-bottom:1px solid #1e1e1e; }
  tr.run:hover { background:#181818; cursor:pointer; }
  .state { padding:1px 7px; border-radius:9px; font-size:11px; }
  .running   { background:#14361d; color:#6ede8a; }
  .done      { background:#1b2d3d; color:#79b8e8; }
  .failed    { background:#3d1b1b; color:#e88; }
  .cancelled { background:#332b16; color:#e8b339; }
  .abandoned { background:#332b16; color:#c9a227; }
  .unknown   { background:#242424; color:#888; }
  .num { text-align:right; font-variant-numeric: tabular-nums; }
  .muted { color:#666; }
  #empty { padding:28px 12px; color:#777; }
  #detail { display:flex; flex-direction:column; height:100%; }
  #plot { flex:1 1 68%; border:0; background:#fff; min-height:180px; }
  /* a GUI project's run has no fit.html and never will, so the note is a
     line and the log gets the room rather than the other way round */
  #noplot { flex:0 0 auto; padding:7px 12px; color:#666;
            border-bottom:1px solid #2c2c2c; }
  #console { flex:0 0 30%; overflow-y:auto; background:#181818; font-size:11px;
             padding:6px 10px; white-space:pre; }
  #console.full { flex:1 1 auto; }
  .k { color:#e8b339; }
  .ev { color:#888; }
  code { background:#1c1c1c; padding:1px 5px; border-radius:3px; color:#9ad; }
</style></head><body>
<div id="bar">
  <strong>rietx watch</strong>
  <span id="crumb"></span>
  <span id="root"></span>
</div>
<div id="body"><div id="empty">scanning …</div></div>
<script>
const body = document.getElementById('body');
const crumb = document.getElementById('crumb');
const rootEl = document.getElementById('root');
let SINGLE = null;          // set when the served directory is itself a run
let timer = null;
let tail = {offset: 0, inode: null, id: null};

function esc(s) {
  return String(s).replace(/[&<>"]/g, c =>
    ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
}
function ago(t) {
  if (!t) return '—';
  const s = Date.now()/1000 - t;
  if (s < 60) return Math.max(0, Math.round(s)) + 's ago';
  if (s < 3600) return Math.round(s/60) + 'm ago';
  if (s < 86400) return Math.round(s/3600) + 'h ago';
  return Math.round(s/86400) + 'd ago';
}
function num(v, d) { return (v === null || v === undefined) ? '—' : v.toFixed(d); }

// ---------------------------------------------------------------- list
async function drawList() {
  const r = await fetch('api/runs', {cache: 'no-store'});
  if (!r.ok) return;
  const payload = await r.json();
  rootEl.textContent = 'scanned ' + payload.root;
  crumb.textContent = '';
  if (!payload.runs.length) {
    body.innerHTML = '<div id="empty">No runs under this directory. ' +
      'A run is a directory holding an <code>events.jsonl</code> — pass one ' +
      'to <code>LiveSession</code>, or open a <code>.rex</code> project in ' +
      'the GUI.</div>';
    return;
  }
  const rows = payload.runs.map(run => {
    const st = run.status || {};
    const gui = run.gui_command
      ? `<code>${esc(run.gui_command)}</code>` : '<span class="muted">—</span>';
    return `<tr class="run" data-id="${run.run_id}">
      <td><span class="state ${run.liveness.state}" title="${esc(run.liveness.evidence)}"
          >${run.liveness.state}</span></td>
      <td><a href="#/run/${run.run_id}">${esc(run.label)}</a>
          ${run.legacy ? '<span class="muted"> · legacy</span>' : ''}</td>
      <td>${esc(st.stage || '—')}</td>
      <td class="num">${num(st.rwp, 4)}</td>
      <td class="num">${num(st.gof, 2)}</td>
      <td class="muted">${ago(run.created)}</td>
      <td>${gui}</td></tr>`;
  }).join('');
  body.innerHTML = `<table><thead><tr>
    <th>state</th><th>run</th><th>stage</th><th class="num">Rwp</th>
    <th class="num">GoF</th><th>started</th><th>open in the GUI</th>
    </tr></thead><tbody>${rows}</tbody></table>`;
  for (const tr of body.querySelectorAll('tr.run')) {
    tr.onclick = ev => {
      if (ev.target.tagName !== 'CODE') location.hash = '#/run/' + tr.dataset.id;
    };
  }
}

// -------------------------------------------------------------- detail
function detailShell(run) {
  const plot = run.has_snapshot
    ? `<iframe id="plot" src="api/run/${run.run_id}/snapshot"></iframe>`
    : `<div id="noplot">no fit.html here — this run wrote only its log</div>`;
  const cls = run.has_snapshot ? '' : ' class="full"';
  body.innerHTML = `<div id="detail">${plot}<div id="console"${cls}></div></div>`;
}

async function drawDetail(id, first) {
  const r = await fetch('api/run/' + id, {cache: 'no-store'});
  if (!r.ok) { location.hash = ''; return; }
  const run = await r.json();
  const st = run.status || {};
  rootEl.textContent = run.path;
  crumb.innerHTML = (SINGLE ? '' : '<a href="#">all runs</a> · ') +
    `<span class="state ${run.liveness.state}" title="${esc(run.liveness.evidence)}"
     >${run.liveness.state}</span> ` + esc(run.label) +
    (st.stage ? ` · stage ${esc(st.stage)}` : '') +
    (st.rwp != null ? ` · Rwp ${st.rwp.toFixed(4)}` : '') +
    (st.gof != null ? ` · GoF ${st.gof.toFixed(2)}` : '') +
    (st.n_free != null ? ` · ${st.n_free} free` : '');
  if (first) { detailShell(run); tail = {offset: 0, inode: null, id}; }
  await pumpEvents(id);
}

async function pumpEvents(id) {
  const q = new URLSearchParams({offset: tail.offset});
  if (tail.inode !== null) q.set('inode', tail.inode);
  const r = await fetch(`api/run/${id}/events?` + q, {cache: 'no-store'});
  if (!r.ok) return;
  const payload = await r.json();
  const pane = document.getElementById('console');
  if (!pane) return;
  if (payload.reset) pane.textContent = '';   // a different log; do not renumber
  tail.offset = payload.offset;
  tail.inode = payload.inode;
  if (!payload.events.length) return;
  const atBottom = pane.scrollTop + pane.clientHeight >= pane.scrollHeight - 30;
  const html = payload.events.map(e => {
    const t = new Date(e.t * 1000).toLocaleTimeString();
    const data = Object.entries(e.data || {}).map(([k, v]) =>
      `${k}=${typeof v === 'number' ? +v.toPrecision(6)
              : Array.isArray(v) ? `[${v.length}]` : JSON.stringify(v)}`
    ).join(' ');
    return `<span class="ev">${t}</span> <span class="k">${esc(
      String(e.kind).padEnd(11))}</span> ${esc(data)}`;
  }).join('\\n');
  pane.innerHTML += (pane.innerHTML ? '\\n' : '') + html;
  if (atBottom) pane.scrollTop = pane.scrollHeight;
}

// ------------------------------------------------------------- routing
function currentId() {
  const m = location.hash.match(/^#\\/run\\/([0-9a-f]+)$/);
  return m ? m[1] : (SINGLE || null);
}
async function refresh(first) {
  const id = currentId();
  if (id) await drawDetail(id, first);
  else await drawList();
}
function schedule() {
  if (timer) clearInterval(timer);
  // polling stops when nobody is looking: a hidden tab costs the fit nothing
  timer = setInterval(() => { if (!document.hidden) refresh(false); }, 1200);
}
window.addEventListener('hashchange', () => refresh(true));
document.addEventListener('visibilitychange', () => {
  if (!document.hidden) refresh(false);
});

(async () => {
  const meta = await (await fetch('api/runs', {cache: 'no-store'})).json();
  SINGLE = meta.single_run_id;
  await refresh(true);
  schedule();
})();
</script></body></html>
"""


class _Handler(http.server.SimpleHTTPRequestHandler):
    """Routes, and a static fallback rooted at the scanned directory.

    The fallback is what keeps ``rietx watch live/`` working for anything that
    already links at ``fit.html`` or ``events.jsonl`` by their bare names.
    """

    def __init__(self, *args, scan_root: Path, **kwargs):
        # set before super().__init__, which handles the request inline
        self.scan_root = scan_root
        super().__init__(*args, **kwargs)

    def _send(self, body: bytes, content_type: str, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, payload, status: int = 200) -> None:
        self._send(json.dumps(payload).encode("utf-8"),
                   "application/json; charset=utf-8", status)

    def _runs(self) -> list:
        return runs_mod.discover(self.scan_root)

    def _find(self, run_id: str):
        """An id is looked up in what the walk offered, never decoded into a
        path. That is why a request cannot name a directory we did not choose
        to serve."""
        for run in self._runs():
            if run.run_id == run_id:
                return run
        return None

    @staticmethod
    def _row(run) -> dict:
        live = runs_mod.liveness_of(run)
        row = run.as_dict()
        row["liveness"] = {"state": live.state, "evidence": live.evidence,
                           "heartbeat_age": live.heartbeat_age}
        # a command a human can copy, not a verb this app performs: launching
        # the GUI is a process boundary and stays one (WP-1401 § the decision)
        project = run.path.parent
        row["gui_command"] = (f"rietx gui {project.name}"
                              if run.path.name == "live"
                              and project.name.endswith(".rex") else None)
        return row

    def do_GET(self):  # noqa: N802 - http.server API
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        if path in ("/", "/index.html"):
            self._send(_PAGE.encode("utf-8"), "text/html; charset=utf-8")
            return

        if path == "/api/runs":
            found = self._runs()
            single = (found[0].run_id
                      if len(found) == 1 and found[0].path == self.scan_root
                      else None)
            self._json({"root": str(self.scan_root),
                        "single_run_id": single,
                        "runs": [self._row(r) for r in found]})
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
                tail = runs_mod.tail_events(
                    run.path / runs_mod.EVENTS_FILE,
                    _int("offset") or 0, inode=_int("inode"))
                self._json({"events": tail.events, "offset": tail.offset,
                            "inode": tail.inode, "reset": tail.reset,
                            "bad_lines": tail.bad_lines, "size": tail.size})
                return
            if rest == "snapshot":
                snapshot = run.path / runs_mod.SNAPSHOT_FILE
                try:
                    body = snapshot.read_bytes()
                except OSError:
                    self._send(b"no snapshot yet", "text/plain; charset=utf-8",
                               status=404)
                    return
                self._send(body, "text/html; charset=utf-8")
                return
            self._json({"error": "no such route"}, status=404)
            return

        super().do_GET()

    def log_message(self, *args):  # quiet: polling floods the terminal
        pass


def serve(directory: str | Path | None = None, *, port: int = 8899,
          open_browser: bool = False, block: bool = True):
    """Serve the runs under ``directory`` (default: the working directory).

    Returns the server when ``block=False``. A directory that is itself a run
    is served as one and the page opens straight onto it.
    """
    directory = Path.cwd() if directory is None else Path(directory)
    if not directory.is_dir():
        raise FileNotFoundError(f"{directory} is not a directory")
    directory = directory.resolve()

    # `directory` is the static-file root SimpleHTTPRequestHandler wants;
    # `scan_root` is what the routes walk. Per instance, so two servers in one
    # process (the tests run several) cannot take each other's root.
    handler = functools.partial(_Handler, directory=str(directory),
                                scan_root=directory)
    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
    url = f"http://127.0.0.1:{server.server_address[1]}/"
    found = runs_mod.discover(directory)
    print(f"rietx watch: {len(found)} run(s) under {directory}")
    print(f"             {url}  (Ctrl-C to stop)")
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
    args = parser.parse_args(argv)
    serve(args.directory, port=args.port, open_browser=args.open)


if __name__ == "__main__":  # python -m rietx.watch [dir]
    main()

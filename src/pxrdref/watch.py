"""``pxrdref watch`` — live refinement viewer over stdlib http.server.

Serves a :class:`~pxrdref.viz.live.LiveSession` directory: the index page
embeds ``fit.html`` in an auto-reloading iframe and tails ``events.jsonl``
into a console pane by plain fetch polling — no FastAPI, no websockets, no
javascript build step.  Every console line shows the event's structured
fields, so the log doubles as a reproducible record of what the engine did.

Run the refinement in one process::

    ref.fit(data, events=LiveSession("live/"))

and the viewer in another::

    pxrdref watch live/            # or: python -m pxrdref.watch live/
"""

from __future__ import annotations

import functools
import http.server
import threading
from pathlib import Path

_INDEX = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>pxrdref watch</title>
<style>
  body { margin:0; font-family: ui-monospace, Menlo, monospace; display:flex;
         flex-direction:column; height:100vh; background:#111; }
  #plot { flex: 1 1 70%; border:0; background:#fff; }
  #bar  { color:#9ad; background:#222; padding:4px 10px; font-size:12px; }
  #console { flex: 0 0 26%; overflow-y:auto; color:#cdc; background:#181818;
             font-size:11px; padding:6px 10px; white-space:pre; }
  .k { color:#e8b339; }
</style></head><body>
<div id="bar">pxrdref watch — waiting for fit.html …</div>
<iframe id="plot" src="fit.html"></iframe>
<div id="console"></div>
<script>
const bar = document.getElementById('bar');
const consoleEl = document.getElementById('console');
let lastLen = 0, lastMod = "";

async function pollPlot() {
  try {
    const head = await fetch('fit.html', {method: 'HEAD', cache: 'no-store'});
    if (head.ok) {
      const mod = head.headers.get('Last-Modified') || "";
      if (mod !== lastMod) {
        lastMod = mod;
        document.getElementById('plot').src = 'fit.html?t=' + Date.now();
      }
    }
  } catch (e) {}
  try {
    const st = await fetch('status.json', {cache: 'no-store'});
    if (st.ok) {
      const s = await st.json();
      bar.textContent = `stage ${s.stage}   Rwp ${s.rwp.toFixed(4)}   ` +
                        `GoF ${s.gof.toFixed(2)}   free params ${s.n_free}`;
    }
  } catch (e) {}
}

async function pollEvents() {
  try {
    const r = await fetch('events.jsonl', {cache: 'no-store'});
    if (!r.ok) return;
    const text = await r.text();
    if (text.length === lastLen) return;
    lastLen = text.length;
    const lines = text.trim().split('\\n').slice(-400);
    consoleEl.innerHTML = lines.map(l => {
      try {
        const e = JSON.parse(l);
        const t = new Date(e.t * 1000).toLocaleTimeString();
        const data = Object.entries(e.data).map(
          ([k, v]) => `${k}=${typeof v === 'number' ? +v.toPrecision(6) : JSON.stringify(v)}`
        ).join(' ');
        return `${t} <span class="k">${e.kind.padEnd(11)}</span> ${data}`;
      } catch { return l; }
    }).join('\\n');
    consoleEl.scrollTop = consoleEl.scrollHeight;
  } catch (e) {}
}
setInterval(pollPlot, 1500);
setInterval(pollEvents, 1000);
pollPlot(); pollEvents();
</script></body></html>
"""


class _Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):  # noqa: N802 - http.server API
        if self.path in ("/", "/index.html"):
            body = _INDEX.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
            return
        super().do_GET()

    def log_message(self, *args):  # quiet: polling floods the terminal
        pass


def serve(directory: str | Path, *, port: int = 8899,
          open_browser: bool = False, block: bool = True):
    """Serve a live-session directory; returns the server when ``block=False``."""
    directory = Path(directory)
    if not directory.is_dir():
        raise FileNotFoundError(f"{directory} is not a directory")
    handler = functools.partial(_Handler, directory=str(directory))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
    url = f"http://127.0.0.1:{server.server_address[1]}/"
    print(f"pxrdref watch: serving {directory} at {url}  (Ctrl-C to stop)")
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
        prog="pxrdref watch",
        description="serve a LiveSession directory with auto-refresh + console")
    parser.add_argument("directory", help="directory passed to LiveSession(...)")
    parser.add_argument("--port", type=int, default=8899)
    parser.add_argument("--open", action="store_true", help="open a browser")
    args = parser.parse_args(argv)
    serve(args.directory, port=args.port, open_browser=args.open)


if __name__ == "__main__":  # python -m pxrdref.watch <dir>
    main()

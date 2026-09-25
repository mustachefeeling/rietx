"""WP-1461 task 2: where the GUI's full-resolution fetch spends its time.

Starts ``rietx gui`` on the NAC example and fits it, then times the real
``/api/result/window`` route with curl: time to the first byte (the server
building and serialising) and the rest (the transfer). Beside it, a stdlib
server with the GUI's own ``_send`` serves each file ``payloads.py`` wrote from
memory, which times the transfer of those bytes alone.

    .venv/bin/python docs/wp/1461-uplot-spike/transport.py
"""
from __future__ import annotations

import http.server
import json
import os
import subprocess
import tempfile
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
RIETX = os.environ.get("RIETX", str(HERE.parents[2] / ".venv" / "bin" / "rietx"))
REPS = 6


def curl(url: str) -> list[tuple[float, float]]:
    """(first byte, rest) in ms for REPS fetches after one warm-up."""
    out = []
    for _ in range(REPS + 1):
        r = subprocess.run(["curl", "-s", "-o", "/dev/null", "-w",
                            "%{time_starttransfer} %{time_total}", url],
                           capture_output=True, text=True, check=True)
        first, total = map(float, r.stdout.split())
        out.append((first * 1e3, (total - first) * 1e3))
    return out[1:]


def span(v) -> str:
    return f"{min(v):.1f}-{max(v):.1f}"


def report(label: str, url: str) -> None:
    t = curl(url)
    print(f"  {label:34s} first byte {span([a for a, _ in t])} ms, "
          f"transfer {span([b for _, b in t])} ms", flush=True)


def gui_route() -> None:
    state = tempfile.mkdtemp(prefix="wp1461-transport-")
    srv = subprocess.Popen([RIETX, "gui", "--no-open", "--machine", "--port", "8799",
                            "--state-dir", state], stdout=subprocess.PIPE, text=True,
                           env={**os.environ, "RIETX_TELEMETRY": "0"})
    base = json.loads(srv.stdout.readline())["url"].rstrip("/")
    try:
        def post(path, body):
            subprocess.run(["curl", "-s", "-o", "/dev/null", "-H",
                            "content-type: application/json", "-d", json.dumps(body),
                            base + path], check=True)
        post("/api/examples/open", {"name": "nac"})
        post("/api/run", {"kind": "fit"})
        while True:
            state_ = subprocess.run(["curl", "-s", base + "/api/run/state"],
                                    capture_output=True, text=True).stdout
            if json.loads(state_)["state"] == "idle":
                break
            time.sleep(0.3)
        print("rietx gui, NAC example, the real route:")
        for mp in (4000, 200000):
            report(f"/api/result/window?max_points={mp}",
                   f"{base}/api/result/window?max_points={mp}")
    finally:
        srv.terminate()


def mimic() -> None:
    files = {m["file"]: (HERE / "payloads" / m["file"]).read_bytes()
             for m in json.loads((HERE / "payloads" / "manifest.json").read_text())}

    class Handler(http.server.BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.0"

        def log_message(self, *args) -> None:
            pass

        def do_GET(self) -> None:  # noqa: N802 - stdlib API
            body = files[self.path.lstrip("/")]
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    print("the GUI's _send serving the bytes from memory, so transfer alone:")
    try:
        for name in ("nac_A_4000.json", "nac_A_full.json", "nac_B_f64.bin",
                     "nac_B_f32.bin", "cmp_nac_A_4000.json", "cmp_nac_A_full.json", "cmp_nac_B_f64.bin"):
            report(f"{name} ({len(files[name]) / 1e6:.2f} MB)",
                   f"http://127.0.0.1:{srv.server_port}/{name}")
    finally:
        srv.shutdown()


if __name__ == "__main__":
    print(f"load {' '.join(f'{x:.1f}' for x in os.getloadavg())}")
    gui_route()
    mimic()

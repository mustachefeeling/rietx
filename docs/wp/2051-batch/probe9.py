"""WP-2051 probe 9: probe 7 with the fast sizing.

Probe 7's modes and arms, with its ``sizing`` (a copy of ``rewindow``'s loop
using the 60-step k(η) bisection) replaced by ``forward.window_sizing``, which
reads k(η) off a table.  Probe 7's ``sync`` already rebuilds the layout only
for a phase whose windows or node counts moved, and keeps the scalar memo.

    OPENBLAS_NUM_THREADS=1 RIETX_TELEMETRY=0 .venv/bin/python docs/wp/2051-batch/probe9.py . time cpd1a
"""
import json
import pathlib
import signal
import sys

root = pathlib.Path(sys.argv[1]).resolve()
sys.path.insert(0, str(root / "docs/wp/2047-batch"))
import probe7  # noqa: E402

from rietx.model import forward as fw  # noqa: E402

probe7.sizing = fw.window_sizing

if __name__ == "__main__":
    signal.signal(signal.SIGALRM, probe7.on_alarm)
    mode, fam = sys.argv[2], sys.argv[3]
    if mode == "fit":
        signal.alarm(probe7.LIMIT)
        print(json.dumps(probe7.hostile(fam, sys.argv[4])), flush=True)
    elif mode == "time":
        signal.alarm(probe7.LIMIT * 4)
        print(json.dumps(probe7.timed(fam, int(sys.argv[4]) if len(sys.argv) > 4 else 5)),
              flush=True)
    else:
        signal.alarm(probe7.LIMIT)
        print(json.dumps(probe7.step(fam)), flush=True)

"""WP-1461: the chart module's pure half, run by the python suite.

``src/rietx/viz/static/rxplot.mjs`` is javascript, so its checks are node's:
``node --check`` for the file a page loads, and ``node --test`` over
``tests/rxplot.test.mjs``. Running them from here keeps them from going quiet,
the reason ``tests/test_watch_app.py`` runs ``watch-core.mjs``'s. The drawing
half needs a canvas, so ``tests/test_rxplot_browser.py`` covers it.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE = REPO_ROOT / "src" / "rietx" / "viz" / "static" / "rxplot.mjs"
CASES = Path(__file__).with_name("rxplot.test.mjs")


def _node() -> str:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed; the gui suite needs it too")
    return node


def test_the_module_parses_as_javascript():
    done = subprocess.run([_node(), "--check", str(MODULE)],
                          capture_output=True, text=True, check=False)
    assert done.returncode == 0, done.stderr


def test_the_pure_half_is_unit_tested():
    """``node --test`` over the pure half, and a count, since an empty file passes."""
    done = subprocess.run([_node(), "--test", "--test-reporter=tap", str(CASES)],
                          capture_output=True, text=True, check=False, cwd=REPO_ROOT)
    assert done.returncode == 0, done.stdout + done.stderr
    match = re.search(r"^# pass (\d+)$", done.stdout, re.MULTILINE)
    assert match is not None, done.stdout
    assert int(match.group(1)) >= 13, done.stdout


def test_the_browser_reads_what_python_packs(tmp_path):
    """D4's body is written by ``rietx.viz.packed`` and read by ``rxplot.mjs``'s
    ``unpack``: two halves of one format in two languages, so only running both
    says they agree. The offsets are what a one-sided test cannot see."""
    import json

    import numpy as np

    from rietx.viz.packed import pack

    arrays = {"two_theta": np.linspace(5.0, 6.0, 3), "kept": np.array([0, 2]),
              "odd": np.array([1.0 / 3.0]),
              "fitted": np.array([1, 2, 3], dtype=np.int64)}
    body = tmp_path / "body.bin"
    body.write_bytes(pack({"fit": True, "ticks": {"a": [5.5]}}, arrays))
    script = (f"import {{unpack}} from {json.dumps(MODULE.as_uri())};"
              "import {readFileSync} from 'node:fs';"
              f"const b = readFileSync({json.dumps(str(body))});"
              "const {header, arrays} = unpack("
              "b.buffer.slice(b.byteOffset, b.byteOffset + b.length));"
              "const out = {header};"
              "for (const [k, v] of Object.entries(arrays))"
              " out[k] = [v.constructor.name, Array.from(v)];"
              "console.log(JSON.stringify(out));")
    done = subprocess.run([_node(), "--input-type=module", "-e", script],
                          capture_output=True, text=True, check=False)
    assert done.returncode == 0, done.stderr
    out = json.loads(done.stdout)
    assert out.pop("header") == {"fit": True, "ticks": {"a": [5.5]}}
    assert out == {
        "two_theta": ["Float64Array", [5.0, 5.5, 6.0]],
        "kept": ["Int32Array", [0, 2]],
        # every digit survives: float64 on the wire, not a printed decimal
        "odd": ["Float64Array", [1.0 / 3.0]],
        "fitted": ["Int32Array", [1, 2, 3]]}

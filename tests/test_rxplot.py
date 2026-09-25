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
    assert int(match.group(1)) >= 9, done.stdout

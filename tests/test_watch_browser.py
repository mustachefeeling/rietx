"""WP-1423 — what holds still on the ``rietx watch`` page, measured in a browser.

A python test cannot see layout (WP-1402 and WP-1405 each found a page defect
no substring assertion could have), and ``node --check`` sees only syntax.
This file drives the page in chromium through playwright, which is not a
dependency (``docs/manual/make_screenshots.py`` says why), so every test here
skips where the package or a cached chromium is missing. That includes CI:
the guard is this machine's, and the handover names the skip.

What it pins is the WP's two rules. Nothing on the page is rebuilt on a poll,
and no dimension follows the stage being drawn: over two polls that rewrite
the snapshot and the status, the columns, the bar, the strip's slots, the
plot's inner size and its data-derived ranges are unchanged while the text in
the slots is not.
"""

from __future__ import annotations

import importlib.util
import json
import math
import sys
import time
from pathlib import Path

import pytest

from rietx import runs
from tests.test_watch_app import _served

playwright = pytest.importorskip("playwright")
from playwright.sync_api import sync_playwright  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
MAKE_SHOTS = REPO_ROOT / "docs" / "manual" / "make_screenshots.py"

#: One poll of the page, in seconds (``schedule`` in
#: ``watch/static/watch.mjs``); a wait of two of them is what "the page has
#: seen the write" means here.
POLL = 1.2


def _chromium() -> str:
    """The cached chromium ``make_screenshots.py`` drives, loaded by path.

    The script's playwright imports are inside its functions, so loading it
    costs nothing a suite without a browser would notice.
    """
    spec = importlib.util.spec_from_file_location("_make_screenshots", MAKE_SHOTS)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["_make_screenshots"] = module
    spec.loader.exec_module(module)
    return module.chromium_path()


@pytest.fixture(scope="module")
def browser():
    executable = _chromium()
    with sync_playwright() as p:
        try:
            handle = p.chromium.launch(executable_path=executable or None)
        except Exception as exc:  # no browser on this machine: not a failure
            pytest.skip(f"no chromium to drive: {exc}")
        try:
            yield handle
        finally:
            handle.close()


# ----------------------------------------------------------------------
# a run whose stages differ in everything but the data
# ----------------------------------------------------------------------
N = 600


def _snapshot(stage: str, *, scale: float, noise: float) -> dict:
    """A pattern with three peaks, and a fit at ``scale`` of it.

    Observed is the same in every stage; calculated and Δ/σ are not. That is
    the contract the page's ranges rest on: two of three are the data's.
    """
    tt = [10.0 + 70.0 * i / (N - 1) for i in range(N)]
    obs = [50.0 + 3000.0 * math.exp(-((t - 25) ** 2) / 0.05)
           + 1200.0 * math.exp(-((t - 44) ** 2) / 0.08)
           + 600.0 * math.exp(-((t - 63) ** 2) / 0.1) for t in tt]
    calc = [scale * v for v in obs]
    delta = [(o - c) / math.sqrt(max(o, 1.0)) for o, c in zip(obs, calc)]
    # a wide residual reads as a wide stage, so the ladder can be seen moving
    delta = [d + noise * math.sin(i) for i, d in enumerate(delta)]
    return {"schema": 1, "stage": stage, "weighted": False, "n_points": N,
            "n_drawn": N, "two_theta": tt, "y_obs": obs, "y_calc": calc,
            "y_bkg": [50.0] * N, "delta": delta,
            "ticks": {"phase 0": {"two_theta": [25.0, 44.0], "n_total": 2},
                      "phase 1": {"two_theta": [63.0], "n_total": 1}},
            "statistics": {"rwp": 0.3 if scale < 1 else 0.05, "gof": 2.0,
                           "chi2": 4.0, "rp": 0.2, "n_free": 5}}


def _write_stage(run_dir: Path, stage: str, *, scale: float, noise: float,
                 rwp: float) -> None:
    (run_dir / runs.SNAPSHOT_FILE).write_text(
        json.dumps(_snapshot(stage, scale=scale, noise=noise)), encoding="utf-8")
    (run_dir / runs.STATUS_FILE).write_text(
        json.dumps({"state": "done", "stage": stage, "rwp": rwp, "gof": 2.0,
                    "n_free": 5, "index": 2 if stage == "cell" else 3,
                    "n_stages": 3, "series_index": 4, "series_n": 8,
                    "series_label": "cpd-1e", "series_pass": "backward"}),
        encoding="utf-8")


def _make_tree(root: Path, *, n_done: int = 40) -> Path:
    """``n_done`` finished runs so the list scrolls, plus the one watched."""
    for i in range(n_done):
        d = root / f"old-{i:02d}"
        d.mkdir()
        (d / runs.EVENTS_FILE).write_text(
            json.dumps({"record": "event", "v": "2", "t": 1.0 + i,
                        "kind": "fit_start", "data": {}}) + "\n",
            encoding="utf-8")
        (d / runs.STATUS_FILE).write_text(
            json.dumps({"state": "done", "stage": "biso", "rwp": 0.1 + i / 1000,
                        "gof": 1.4}), encoding="utf-8")
    watched = root / "watched"
    watched.mkdir()
    (watched / runs.EVENTS_FILE).write_text(
        json.dumps({"record": "event", "v": "2", "t": 1e9, "kind": "fit_start",
                    "data": {"series_index": 4}}) + "\n", encoding="utf-8")
    _write_stage(watched, "cell", scale=0.7, noise=30.0, rwp=0.3)
    return watched


GEOMETRY = """() => {
  const r = el => { const b = el.getBoundingClientRect();
                    return [b.x, b.y, b.width, b.height].map(Math.round); };
  const plot = document.getElementById('plot');
  const L = plot && plot._fullLayout;
  return {
    bar: r(document.getElementById('bar')),
    strip: r(document.getElementById('strip')),
    slots: [...document.querySelectorAll('#strip > *')].map(r),
    cols: [...document.querySelectorAll('th')].map(th =>
      Math.round(th.getBoundingClientRect().width)),
    plot: plot ? r(plot) : null,
    size: L ? [L._size.l, L._size.t, L._size.w, L._size.h].map(Math.round) : null,
    x: L ? L.xaxis.range.map(v => +v.toFixed(3)) : null,
    y: L ? L.yaxis.range.map(v => +v.toFixed(1)) : null,
    y2: L ? L.yaxis2.range.map(v => +v.toFixed(2)) : null,
    y3: L ? L.yaxis3.range : null,
    listScroll: document.getElementById('runs').scrollTop,
    stripText: document.getElementById('strip').textContent.replace(/\\s+/g, ' ').trim(),
    stage: document.getElementById('s-stage').textContent,
    series: document.getElementById('s-series').textContent,
    rowsRebuilt: window.__rows,
  };
}"""

OBSERVE = """() => {
  window.__rows = 0;
  new MutationObserver(ms => { window.__rows += ms.length; })
    .observe(document.getElementById('rows'), {childList: true});
}"""


def _open(browser, base: str, run_id: str):
    page = browser.new_page(viewport={"width": 1400, "height": 900})
    errors: list[str] = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(f"{base}/#/run/{run_id}", wait_until="networkidle")
    page.wait_for_function("() => document.getElementById('plot') && "
                           "document.getElementById('plot')._fullLayout",
                           timeout=15000)
    page.wait_for_timeout(500)
    return page, errors


def test_a_stage_changes_the_text_and_nothing_else(browser, tmp_path):
    """The WP's acceptance: two polls after the writer moves on, every
    dimension the eye fixes on is where it was."""
    watched = _make_tree(tmp_path)
    with _served(tmp_path) as base:
        run_id = next(r.run_id for r in runs.discover(tmp_path)
                      if r.path == watched)
        page, errors = _open(browser, base, run_id)
        page.evaluate(OBSERVE)
        page.evaluate("() => { document.getElementById('runs').scrollTop = 250; }")
        page.wait_for_timeout(300)
        before = page.evaluate(GEOMETRY)

        # a later stage: the fit converged, the residual tightened
        time.sleep(0.05)
        _write_stage(watched, "biso", scale=1.0, noise=4.0, rwp=0.05)
        page.wait_for_timeout(int(2.5 * POLL * 1000))
        after = page.evaluate(GEOMETRY)
        page.close()

    assert not errors, errors
    # the poll happened: what the slots say moved with the writer
    assert before["stage"] == "stage 2/3 cell"
    assert after["stage"] == "stage 3/3 biso"
    assert before["series"] == after["series"] == "pattern 5/8 cpd-1e backward"
    assert before["stripText"] != after["stripText"]
    # and nothing the eye fixes on did
    for key in ("bar", "strip", "slots", "cols", "plot", "size", "x", "y", "y3"):
        assert before[key] == after[key], key
    assert before["listScroll"] == after["listScroll"] == 250
    assert after["rowsRebuilt"] == 0, "a poll rebuilt the run list"
    # the Δ/σ range is the one dimension that is the fit's: it stepped down
    # the ladder, symmetric both times
    assert before["y2"] == [-50, 50]
    assert after["y2"] == [-5, 5]


def test_the_ranges_are_the_datas(browser, tmp_path):
    """The x range is the pattern's span and the intensity range the observed
    curve's, with the page's own padding — never plotly's autorange over
    whatever the stage drew."""
    watched = _make_tree(tmp_path, n_done=1)
    with _served(tmp_path) as base:
        run_id = next(r.run_id for r in runs.discover(tmp_path)
                      if r.path == watched)
        page, errors = _open(browser, base, run_id)
        got = page.evaluate(GEOMETRY)
        page.close()
    assert not errors, errors
    assert got["x"] == [pytest.approx(10 - 0.7), pytest.approx(80 + 0.7)]
    snap = _snapshot("cell", scale=0.7, noise=30.0)
    lo, hi = min(snap["y_obs"]), max(snap["y_obs"])
    span = hi - lo
    assert got["y"] == [pytest.approx(lo - 0.03 * span, abs=0.1),
                        pytest.approx(hi + 0.05 * span, abs=0.1)]
    # two tick rows, one unit apart, on an axis of their own
    assert got["y3"] == [-1.5, 0.5]


def test_either_panel_collapses_and_the_other_takes_the_width(browser, tmp_path):
    watched = _make_tree(tmp_path, n_done=2)
    with _served(tmp_path) as base:
        run_id = next(r.run_id for r in runs.discover(tmp_path)
                      if r.path == watched)
        page, errors = _open(browser, base, run_id)
        both = page.evaluate(GEOMETRY)
        page.click("#toggle-runs")
        page.wait_for_timeout(600)
        list_closed = page.evaluate(GEOMETRY)
        assert page.evaluate("() => document.body.dataset.runs") == "closed"
        page.click("#toggle-run")
        page.wait_for_timeout(300)
        # closing the last open panel opens the other rather than leaving a
        # bar over nothing
        assert page.evaluate("() => document.body.dataset.runs") == "open"
        assert page.evaluate("() => document.body.dataset.run") == "closed"
        # the choice survives a reload
        page.reload(wait_until="networkidle")
        page.wait_for_timeout(300)
        assert page.evaluate("() => document.body.dataset.run") == "closed"
        page.close()
    assert not errors, errors
    assert list_closed["plot"][0] == 0
    assert list_closed["plot"][2] > both["plot"][2]
    assert list_closed["size"][2] > both["size"][2], "the plot did not resize"


def test_with_no_run_in_the_url_the_page_follows_the_newest(browser, tmp_path):
    _make_tree(tmp_path, n_done=3)
    with _served(tmp_path) as base:
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        page.goto(f"{base}/", wait_until="networkidle")
        page.wait_for_timeout(int(1.5 * POLL * 1000))
        assert page.evaluate("() => document.getElementById('s-stage').textContent") \
            == "stage 2/3 cell"
        selected = page.evaluate("() => document.querySelector('tr.run.selected').dataset.id")
        newest = page.evaluate("() => document.querySelector('tr.run').dataset.id")
        assert selected == newest
        assert page.evaluate("() => location.hash") == ""
        # a newer run arrives: the page moves to it, the URL still says nothing
        later = tmp_path / "later"
        later.mkdir()
        (later / runs.EVENTS_FILE).write_text(
            json.dumps({"record": "event", "v": "2", "t": 2e9,
                        "kind": "fit_start", "data": {}}) + "\n",
            encoding="utf-8")
        (later / runs.STATUS_FILE).write_text(
            json.dumps({"state": "done", "stage": "scale", "rwp": 0.5}),
            encoding="utf-8")
        page.wait_for_timeout(int(2.5 * POLL * 1000))
        assert page.evaluate("() => document.getElementById('s-stage').textContent") \
            == "stage scale"
        assert page.evaluate("() => location.hash") == ""
        # clicking a row pins it
        page.click("tr.run:nth-child(2)")
        page.wait_for_timeout(int(1.5 * POLL * 1000))
        assert page.evaluate("() => location.hash").startswith("#/run/")
        assert page.evaluate("() => document.getElementById('s-stage').textContent") \
            == "stage 2/3 cell"
        page.close()

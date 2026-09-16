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
import re
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


def _snapshot(stage: str, *, scale: float, noise: float, bkg: bool = True) -> dict:
    """A pattern with three peaks, and a fit at ``scale`` of it.

    Observed is the same in every stage; calculated and Δ/σ are not. That is
    the contract the page's ranges rest on: two of three are the data's.

    ``bkg=False`` writes an all-zero background, which the page reads as no
    background to draw. It is one trace and one legend entry fewer, and so the
    way to write the stage that *frees* the background: the entry arrives, the
    legend gains a row, and before WP-1426 the whole picture moved down.
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
            "y_bkg": [50.0 if bkg else 0.0] * N, "delta": delta,
            "ticks": {"phase 0": {"two_theta": [25.0, 44.0], "n_total": 2},
                      "phase 1": {"two_theta": [63.0], "n_total": 1}},
            "statistics": {"rwp": 0.3 if scale < 1 else 0.05, "gof": 2.0,
                           "chi2": 4.0, "rp": 0.2, "n_free": 5}}


def _write_stage(run_dir: Path, stage: str, *, scale: float, noise: float,
                 rwp: float, bkg: bool = True) -> None:
    (run_dir / runs.SNAPSHOT_FILE).write_text(
        json.dumps(_snapshot(stage, scale=scale, noise=noise, bkg=bkg)),
        encoding="utf-8")
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


# ----------------------------------------------------------------------
# WP-1426: what moves when a stage lands, a run arrives, or the window changes
#
# Two instruments, because neither sees what the other does. The browser's own
# `layout-shift` entry is the measure of a *box* moving, and it names the
# element; it is blind to the picture, the plot being one div whose insides
# plotly redraws without the layout engine ever hearing about it. Measured on
# the page before this WP: a stage that freed the background took the plot area
# from y=45 to y=64 and reported a layout shift of exactly 0. So the picture is
# read off `_fullLayout._size`, which is where that movement is.
# ----------------------------------------------------------------------

OBSERVE_SHIFT = """() => {
  window.__shifts = [];
  new PerformanceObserver(list => {
    for (const e of list.getEntries()) window.__shifts.push({
      value: e.value,
      nodes: (e.sources || []).map(s =>
        s.node ? (s.node.id || s.node.tagName + '.' + (s.node.className || '')) : null),
    });
  }).observe({type: 'layout-shift', buffered: true});
}"""

#: Reading drains, so each read covers the interval since the last one and the
#: shifts of settling in after load are never charged to a later act.
READ_SHIFT = """() => {
  const s = window.__shifts;
  window.__shifts = [];
  return {sum: s.reduce((a, e) => a + e.value, 0), n: s.length,
          nodes: s.flatMap(e => e.nodes)};
}"""

#: The plot area and the legend, in the plot div's own coordinates. `_size` is
#: the area plotly drew inside the margins, so `_size.t` growing is the picture
#: being pushed down by whatever is in the top margin.
PLOT_GEOMETRY = """() => {
  const div = document.getElementById('plot');
  const L = div._fullLayout;
  const g = div.querySelector('g.legend');
  const pr = div.getBoundingClientRect();
  const area = [L._size.l, L._size.t, L._size.w, L._size.h].map(Math.round);
  const b = g.getBoundingClientRect();
  const legend = [b.x - pr.x, b.y - pr.y, b.width, b.height].map(Math.round);
  return {ntraces: div.data.length, area, legend,
          rel: [legend[0] - area[0], legend[1] - area[1]],
          div: [Math.round(pr.width), Math.round(pr.height)]};
}"""

#: A wipe and a tail are both `childList` mutations, and the console's *line
#: count* tells them apart not at all: the wipe re-fetched from offset 0 and
#: put all 121 lines back, so before WP-1426 the count was 121 either way.
#: What separates them is whether any node was removed, whether the node that
#: was first still is, and whether a reader scrolled up kept their place.
WATCH_CONSOLE = """() => {
  const pane = document.getElementById('console');
  window.__con = {removed: 0, added: 0};
  window.__firstNode = pane.firstElementChild;
  new MutationObserver(ms => { for (const m of ms) {
    window.__con.removed += m.removedNodes.length;
    window.__con.added += m.addedNodes.length; } })
    .observe(pane, {childList: true});
}"""

READ_CONSOLE = """() => {
  const pane = document.getElementById('console');
  return Object.assign({}, window.__con, {
    lines: pane.childElementCount,
    sameFirstNode: window.__firstNode === pane.firstElementChild,
    scrollTop: Math.round(pane.scrollTop)});
}"""


def _pinned(browser, base: str, run_id: str, *, width: int = 1400):
    """Open a run named in the URL, and check the URL still names it.

    `run_id` is a digest of the path string (``runs.run_id_for``), so a caller
    that walked one spelling of a directory while the server walked another
    hands over an id the page cannot find — whereupon the page clears the hash
    and follows the newest run instead, which is a different measurement
    wearing this one's name. ``tmp_path`` is already resolved and the two
    agree; this says so rather than trusting it.
    """
    page, errors = _open(browser, base, run_id)
    assert page.evaluate("() => location.hash") == f"#/run/{run_id}", \
        "the page did not stay on the run this test pinned"
    return page, errors


def test_the_legend_is_a_dimension_the_page_fixes(browser, tmp_path):
    """A window resize moves the legend with the plot and nothing else.

    The legend used to sit above the plot area, where plotly grows the top
    margin to fit it. Narrowing the window wrapped its one row to two and then
    four, and each row came out of the picture: the plot area's top ran
    46 → 65 → 139 px and its height 465 → 446 → 372 across 1400 → 700 px. A
    resize moves everything by design, so the bar is not a layout shift of
    zero; it is that the legend's box relative to the plot area is the same at
    every width, which is what "a dimension the page fixes" means.
    """
    _make_tree(tmp_path, n_done=2)
    seen = {}
    with _served(tmp_path) as base:
        run_id = next(r.run_id for r in runs.discover(tmp_path)
                      if r.path.name == "watched")
        page, errors = _pinned(browser, base, run_id)
        for width in (1400, 1000, 700):
            page.set_viewport_size({"width": width, "height": 900})
            page.wait_for_timeout(800)
            seen[width] = page.evaluate(PLOT_GEOMETRY)
        page.close()

    assert not errors, errors
    tops = {w: g["area"][1] for w, g in seen.items()}
    heights = {w: g["area"][3] for w, g in seen.items()}
    # the declared top margin, and nothing added to it for a legend
    assert set(tops.values()) == {8}, tops
    assert len(set(heights.values())) == 1, heights
    # and the legend's top edge is the plot area's, at every width
    assert {w: g["rel"][1] for w, g in seen.items()} == {1400: 0, 1000: 0, 700: 0}
    # its left edge too, wherever the panel is wide enough to hold it. At the
    # narrowest the legend is wider than the plot area (125 px against 107) and
    # plotly keeps it inside the paper instead, which moves it left by a few
    # pixels. That is the panel being too narrow for this picture, which is
    # WP-1425's, and it is still not the legend driving the margin.
    for width, g in seen.items():
        if g["legend"][2] <= g["area"][2]:
            assert g["rel"][0] == 0, (width, g)
        else:
            assert -8 <= g["rel"][0] < 0, (width, g)


def test_a_stage_that_adds_a_legend_entry_does_not_move_the_picture(browser, tmp_path):
    """The stage that frees the background is the one that used to jump.

    It adds a trace, the trace adds a legend entry, the entry wraps the legend
    to a second row, and the row came out of the picture. No `layout-shift`
    entry was ever raised for it: the plot div's own box is untouched, and the
    movement is entirely inside plotly's redraw. Both instruments are read
    here, and the point of the second is that the first reported 0 while the
    picture moved 19 px.
    """
    watched = _make_tree(tmp_path, n_done=4)
    _write_stage(watched, "cell", scale=0.7, noise=30.0, rwp=0.3, bkg=False)
    with _served(tmp_path) as base:
        run_id = next(r.run_id for r in runs.discover(tmp_path)
                      if r.path == watched)
        page, errors = _pinned(browser, base, run_id)
        # narrow enough that the sixth entry is the one that wraps the row: at
        # 1400 the legend has 807 px of plot area and both counts fit on one
        # line, so the defect this test is about cannot arise there
        page.set_viewport_size({"width": 1200, "height": 800})
        page.wait_for_timeout(800)
        page.evaluate(OBSERVE_SHIFT)
        page.wait_for_timeout(300)
        page.evaluate(READ_SHIFT)
        before = page.evaluate(PLOT_GEOMETRY)
        _write_stage(watched, "bkg", scale=0.9, noise=10.0, rwp=0.2, bkg=True)
        page.wait_for_timeout(int(3.0 * POLL * 1000))
        after = page.evaluate(PLOT_GEOMETRY)
        shift = page.evaluate(READ_SHIFT)
        page.close()

    assert not errors, errors
    # the stage landed, and it is the trace count that changed
    assert before["ntraces"] + 1 == after["ntraces"]
    assert after["legend"][3] > before["legend"][3], "the legend did not gain a row"
    # and the picture did not move
    assert before["area"] == after["area"]
    assert before["div"] == after["div"]
    assert shift["sum"] == 0, shift


def test_a_stage_lands_with_no_layout_shift(browser, tmp_path):
    """The ordinary stage boundary, on both instruments."""
    watched = _make_tree(tmp_path, n_done=4)
    with _served(tmp_path) as base:
        run_id = next(r.run_id for r in runs.discover(tmp_path)
                      if r.path == watched)
        page, errors = _pinned(browser, base, run_id)
        page.evaluate(OBSERVE_SHIFT)
        page.wait_for_timeout(300)
        page.evaluate(READ_SHIFT)
        before = page.evaluate(PLOT_GEOMETRY)
        time.sleep(0.05)
        _write_stage(watched, "biso", scale=1.0, noise=4.0, rwp=0.05)
        page.wait_for_timeout(int(2.5 * POLL * 1000))
        after = page.evaluate(PLOT_GEOMETRY)
        shift = page.evaluate(READ_SHIFT)
        stage = page.evaluate("() => document.getElementById('s-stage').textContent")
        page.close()

    assert not errors, errors
    assert stage == "stage 3/3 biso", "the poll never happened"
    assert shift["sum"] == 0, shift
    assert before["area"] == after["area"]


def test_a_run_arriving_holds_the_readers_place(browser, tmp_path):
    """A new run is prepended, and the list must not move under the reader.

    Every row below the insertion goes down a row's height. Measured before
    WP-1426: one arrival on a scrolled list, 0.0134 of layout shift across four
    rows. A list already at its top is the other case and is left alone, the
    arriving run being the thing a reader at the top is watching for.
    """
    watched = _make_tree(tmp_path, n_done=40)

    def arrive(name: str, t: float) -> None:
        d = tmp_path / name
        d.mkdir()
        (d / runs.EVENTS_FILE).write_text(
            json.dumps({"record": "event", "v": "2", "t": t,
                        "kind": "fit_start", "data": {}}) + "\n", encoding="utf-8")
        (d / runs.STATUS_FILE).write_text(
            json.dumps({"state": "done", "stage": "scale", "rwp": 0.5}),
            encoding="utf-8")

    with _served(tmp_path) as base:
        run_id = next(r.run_id for r in runs.discover(tmp_path)
                      if r.path == watched)
        page, errors = _pinned(browser, base, run_id)

        page.evaluate("() => { document.getElementById('runs').scrollTop = 250; }")
        page.wait_for_timeout(300)
        page.evaluate(OBSERVE_SHIFT)
        page.wait_for_timeout(200)
        page.evaluate(READ_SHIFT)
        rows_before = page.evaluate("() => document.getElementById('rows').childElementCount")
        arrive("later-a", 2e9)
        page.wait_for_timeout(int(3.0 * POLL * 1000))
        scrolled = page.evaluate(READ_SHIFT)
        rows_after = page.evaluate("() => document.getElementById('rows').childElementCount")
        moved_to = page.evaluate("() => document.getElementById('runs').scrollTop")

        # and again with the list at its top
        page.evaluate("() => { document.getElementById('runs').scrollTop = 0; }")
        page.wait_for_timeout(300)
        page.evaluate(READ_SHIFT)
        arrive("later-b", 3e9)
        page.wait_for_timeout(int(3.0 * POLL * 1000))
        at_top = page.evaluate("() => document.getElementById('runs').scrollTop")
        newest_visible = page.evaluate(
            "() => { const box = document.getElementById('runs');"
            "        const tr = document.querySelector('tr.run');"
            "        return tr.getBoundingClientRect().top"
            "               >= box.getBoundingClientRect().top - 1; }")
        page.close()

    assert not errors, errors
    assert rows_after == rows_before + 1, "the run never arrived"
    # the reader's rows are where they were, and the scroll took the difference
    assert scrolled["sum"] == 0, scrolled
    assert moved_to > 250, "the scroll was not compensated"
    # a list at its top stays at its top, and the new run is what is there
    assert at_top == 0
    assert newest_visible


def test_the_console_survives_the_picture_being_rebuilt(browser, tmp_path):
    """A run opened before its first snapshot keeps its log at that snapshot.

    The picture and the console shared a builder, so the kind going from
    'none' to 'json' wiped the console and re-tailed it from offset 0: 121
    lines out and 121 back, and a reader who had scrolled up to read was
    dropped at the bottom. The line count is the one thing that did *not*
    change, which is why nothing about it is asserted here.
    """
    bare = tmp_path / "bare"
    bare.mkdir()
    (bare / runs.EVENTS_FILE).write_text(
        "".join(json.dumps({"record": "event", "v": "2", "t": 1e9 + i,
                            "kind": "iteration", "data": {"i": i}}) + "\n"
                for i in range(120)), encoding="utf-8")
    (bare / runs.STATUS_FILE).write_text(
        json.dumps({"state": "running", "stage": "scale", "rwp": 0.4}),
        encoding="utf-8")

    with _served(tmp_path) as base:
        run_id = next(r.run_id for r in runs.discover(tmp_path) if r.path == bare)
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(f"{base}/#/run/{run_id}", wait_until="networkidle")
        page.wait_for_timeout(int(2.0 * POLL * 1000))
        assert page.evaluate("() => !document.getElementById('plot')"), \
            "this run was supposed to open with no picture"
        # a reader who scrolled up to read
        page.evaluate("() => { document.getElementById('console').scrollTop = 200; }")
        page.wait_for_timeout(200)
        page.evaluate(WATCH_CONSOLE)
        page.wait_for_timeout(200)
        _write_stage(bare, "cell", scale=0.7, noise=30.0, rwp=0.3)
        page.wait_for_timeout(int(3.0 * POLL * 1000))
        console = page.evaluate(READ_CONSOLE)
        drawn = page.evaluate("() => !!document.getElementById('plot')")
        page.close()

    assert not errors, errors
    assert drawn, "the picture was never built"
    assert console["removed"] == 0, "the console was wiped"
    assert console["added"] == 0, "the console was re-tailed"
    assert console["sameFirstNode"]
    assert console["scrollTop"] == 200, "the reader lost their place"


def test_the_console_is_re_tailed_when_the_run_changes(browser, tmp_path):
    """The other half of the rule above: a reset still happens when it should.

    The tail follows the log, so moving to another run must drop it. Without
    this the console would keep the previous run's lines and carry an offset
    into a file it does not belong to.
    """
    for name, n in (("run-a", 10), ("run-b", 40)):
        d = tmp_path / name
        d.mkdir()
        (d / runs.EVENTS_FILE).write_text(
            "".join(json.dumps({"record": "event", "v": "2", "t": 1e9 + i,
                                "kind": "iteration", "data": {"i": i}}) + "\n"
                    for i in range(n)), encoding="utf-8")
        (d / runs.STATUS_FILE).write_text(
            json.dumps({"state": "done", "stage": name, "rwp": 0.1}),
            encoding="utf-8")

    lines = "() => document.getElementById('console').childElementCount"
    with _served(tmp_path) as base:
        found = {r.path.name: r.run_id for r in runs.discover(tmp_path)}
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(f"{base}/#/run/{found['run-a']}", wait_until="networkidle")
        page.wait_for_timeout(int(2.0 * POLL * 1000))
        first = page.evaluate(lines)
        page.evaluate("id => { location.hash = '#/run/' + id; }", found["run-b"])
        page.wait_for_timeout(int(2.0 * POLL * 1000))
        second = page.evaluate(lines)
        page.evaluate("id => { location.hash = '#/run/' + id; }", found["run-a"])
        page.wait_for_timeout(int(2.0 * POLL * 1000))
        back = page.evaluate(lines)
        page.close()

    assert not errors, errors
    assert (first, second, back) == (10, 40, 10)



# ----------------------------------------------------------------------
# WP-1424: every number is drawn whole, and every row can be told apart
#
# `table-layout: fixed` makes a `<col>` width the cell's whole box, padding
# included, so a column declared wide enough for its content is short by the
# 14 px the cell pads with. Nothing about that is visible in the markup or to
# a substring assertion: the cell renders, the text is in the DOM, and the
# browser quietly replaces the last character with an ellipsis.
#
# What is measured is the ink against the room — the range rectangle of the
# cell's contents against its content box — rather than `scrollWidth`, which
# is the same as `clientWidth` for anything whose overflow is `visible` and so
# reports 0 for a `<th>` whose heading is spilling into its neighbour.
# ----------------------------------------------------------------------

#: Every cell and slot, with how far its contents overrun the box.
OVERFLOW = """() => {
  const out = [];
  const rng = document.createRange();
  const add = (what, el) => {
    const cs = getComputedStyle(el);
    if (cs.display === 'none') return;
    rng.selectNodeContents(el);
    const pad = parseFloat(cs.paddingLeft) + parseFloat(cs.paddingRight);
    const room = el.clientWidth - pad;
    const ink = rng.getBoundingClientRect().width;
    out.push({what: what, over: +(ink - room).toFixed(2), room: room,
              ink: +ink.toFixed(2), text: el.textContent.trim(),
              title: el.getAttribute('title')});
  };
  const heads = [...document.querySelectorAll('#runs th')];
  heads.forEach(th => add('th:' + th.textContent.trim(), th));
  [...document.querySelectorAll('tr.run')].forEach((tr, r) =>
    [...tr.children].forEach((td, i) =>
      add(`td${r}:` + heads[i].textContent.trim(), td)));
  [...document.querySelectorAll('#strip > *')].forEach(el =>
    add('slot:' + el.id, el));
  return out;
}"""

#: Which cells must fit and which may elide, by what fills them. A cell the
#: page fills itself — a state word from a closed vocabulary, a number it
#: formats, a clock time — has a worst case the CSS can be sized for, and a
#: reader who cannot see all of it has simply been shown the wrong number. A
#: cell holding a name somebody else chose has no worst case: a stage is the
#: plan author's string (`preferred_orientation` is 21 characters), a label
#: and a path are the caller's. Those may be cut, and what is asserted of them
#: is that the whole string is in a `title` where the reader can still reach
#: it.
BOUNDED = ("state", "Rwp", "GoF", "started")
ELIDED = ("run", "stage")
BOUNDED_SLOTS = {"slot:s-state", "slot:s-rwp", "slot:s-gof", "slot:s-free",
                 "slot:s-notice", "slot:stop"}


def _batch(root: Path, *, n: int = 4) -> list[Path]:
    """One label over several runs, which is what a batch looks like.

    Every run here is one fit launched from one directory, so
    `RunRecorder._default_label` gives them all the same word and the list
    names nothing. The numbers are the maintainer's, off the 2026-09-16 demo:
    an Rwp that reads `0.1734` in the old form, a GoF of `12.34`, and a start
    time far enough back that the relative column says hours. The last run is
    cancelled, for the longest word the state pill has.
    """
    made = []
    now = time.time()
    for i in range(n):
        d = root / f"20260916-14{20 + i:02d}00-9{i}"
        d.mkdir()
        (d / runs.EVENTS_FILE).write_text(
            json.dumps({"record": "event", "v": "2", "t": now - 10800 + i,
                        "kind": "fit_start", "data": {}}) + "\n",
            encoding="utf-8")
        (d / runs.META_FILE).write_text(
            json.dumps({"record": runs.RECORD_TAG, "label": "campaign",
                        "created": now - 10800 + 60 * i,
                        "cwd": "/Users/someone/work/campaign",
                        "command": f"python fit_one.py candidate-{i}"}),
            encoding="utf-8")
        (d / runs.SNAPSHOT_FILE).write_text(
            json.dumps(_snapshot("preferred_orientation", scale=0.83,
                                 noise=6.0)), encoding="utf-8")
        (d / runs.STATUS_FILE).write_text(
            json.dumps({"state": "cancelled" if i == n - 1 else "done",
                        "stage": "preferred_orientation", "rwp": 0.1734,
                        "gof": 12.34, "n_free": 17, "index": 3,
                        "n_stages": 3}), encoding="utf-8")
        made.append(d)
    return made


def test_every_number_on_the_page_is_drawn_whole(browser, tmp_path):
    """No cell the page fills itself is cut off, at either window size.

    Measured on the page before WP-1424, in these two viewports, ink minus
    room in CSS pixels: `GoF` over by 7.13 in every row, `state` by 0.62 on
    the cancelled one, the `started` heading by 6.58, and `stage` by 20.67
    with no title to recover it. In the strip, `s-where` over by 1127 at both
    sizes — its `1fr` track had been squeezed to nothing, so the drawn-point
    count and the path were not cut but absent. At 1000x700 `s-stage` went
    with it, over by 136.95 with the stage name the reader is watching for.
    """
    _batch(tmp_path)
    with _served(tmp_path) as base:
        newest = max(runs.discover(tmp_path), key=lambda r: r.created)
        page, errors = _pinned(browser, base, newest.run_id)
        seen = {}
        for width, height in ((1400, 900), (1000, 700)):
            page.set_viewport_size({"width": width, "height": height})
            page.wait_for_timeout(600)
            seen[width] = page.evaluate(OVERFLOW)
        page.close()

    assert not errors, errors
    # reported per column rather than per cell: forty rows cut the same way
    # is one defect, and the widest cut is the one to size for
    bad = {}
    for width, cells in seen.items():
        for c in cells:
            what = c["what"].split(":")[1]
            bounded = (what in BOUNDED or c["what"] in BOUNDED_SLOTS
                       or c["what"].startswith("th:"))
            if c["over"] <= 0.5:
                continue
            why = "cut" if bounded else "cut with no title"
            if not bounded and c["title"]:
                continue
            where = (width, c["what"].split(":")[0].rstrip("0123456789")
                     + ":" + what)
            if c["over"] > bad.get(where, (0, ""))[0]:
                bad[where] = (c["over"], why, c["text"])
    assert not bad, sorted(bad.items())


#: Every row's visible text, cell by cell, and the tooltip behind each.
ROWS = """() => [...document.querySelectorAll('tr.run')].map(tr =>
  [...tr.children].map(td => [td.textContent.trim(),
                              (td.firstElementChild || td).getAttribute('title')]))"""


def test_two_runs_of_one_batch_are_told_apart(browser, tmp_path):
    """Forty runs of a batch carry one label, and the list must still name them.

    `RunRecorder._default_label` calls a run after the directory it was
    launched from, so a batch driven from one directory is forty rows reading
    `campaign`, `campaign`, `campaign`. Nothing in the record says what a run
    fitted — that is a caller's fact and WP-1431 gives the caller a way to
    write it — but the record does know when each one started, to the second,
    which is what the run directory is named after. So the started column is
    a clock time rather than `3h ago`, and the row's tooltip carries the
    directory, the command line and the working directory behind it.
    """
    made = _batch(tmp_path, n=6)
    with _served(tmp_path) as base:
        newest = max(runs.discover(tmp_path), key=lambda r: r.created)
        page, errors = _pinned(browser, base, newest.run_id)
        rows = page.evaluate(ROWS)
        page.close()

    assert not errors, errors
    assert len(rows) == len(made)
    # the label column is the same word on every row, which is the defect
    assert len({r[1][0] for r in rows}) == 1
    # and every row is still distinct, in a cell the reader can see
    started = [r[5][0] for r in rows]
    assert len(set(started)) == len(rows), started
    assert all(re.fullmatch(r"\d\d:\d\d:\d\d", s) for s in started), started
    # the tooltip is where the rest of the record is
    titles = [r[1][1] for r in rows]
    assert len(set(titles)) == len(rows), titles
    for i, title in enumerate(sorted(titles)):
        assert "fit_one.py candidate-" in title, title
        assert "in /Users/someone/work/campaign" in title, title

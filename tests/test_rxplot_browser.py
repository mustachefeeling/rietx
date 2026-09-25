"""WP-1461: the chart module's drawing half, in chromium.

``tests/rxplot_page.html`` loads the vendored uPlot and ``rxplot.mjs`` the way a
page does, and mounts three linked panes on synthetic data. Each case here is a
behaviour the spike found a way to get wrong (the WP's § What the spike found),
asserted from what the browser drew or holds rather than from what was asked.

Driven through playwright, which is not a dependency, so the module skips where
the package or a cached chromium is missing. That includes CI, as for
``tests/test_watch_browser.py``, whose chromium lookup this borrows.
"""

from __future__ import annotations

import http.server
import math
import threading
from pathlib import Path

import pytest

playwright = pytest.importorskip("playwright")
from playwright.sync_api import sync_playwright  # noqa: E402

from tests.test_watch_browser import _chromium  # noqa: E402

STATIC = Path(__file__).resolve().parents[1] / "src" / "rietx" / "viz" / "static"
HARNESS = Path(__file__).with_name("rxplot_page.html")

#: What the harness fetches, from where, as what.
FILES = {
    "/index.html": (HARNESS, "text/html; charset=utf-8"),
    "/rxplot.mjs": (STATIC / "rxplot.mjs", "text/javascript; charset=utf-8"),
    "/uPlot.iife.min.js": (STATIC / "uPlot.iife.min.js", "text/javascript; charset=utf-8"),
    "/uPlot.min.css": (STATIC / "uPlot.min.css", "text/css; charset=utf-8"),
}


class _Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args) -> None:
        pass

    def do_GET(self) -> None:  # noqa: N802 - http.server API
        found = FILES.get(self.path)
        if found is None:
            self.send_error(404)
            return
        body = found[0].read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", found[1])
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


@pytest.fixture(scope="module")
def url():
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}/index.html"
    server.shutdown()


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as p:
        try:
            handle = p.chromium.launch(executable_path=_chromium() or None)
        except Exception as exc:  # noqa: BLE001 - any launch failure is a skip
            pytest.skip(f"no chromium to drive: {exc}")
        yield handle
        handle.close()


@pytest.fixture
def page(browser, url):
    page = browser.new_page(viewport={"width": 900, "height": 600})
    errors: list[str] = []
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    page.goto(url)
    page.wait_for_function("window.ready === true")
    page.evaluate("mount()")
    yield page
    page.close()
    assert not errors, errors


def _frames(page, n: int = 2) -> None:
    """Wait ``n`` animation frames, which is when a paint has happened, never a timer."""
    page.evaluate("n => new Promise(r => { const f = k => k ? requestAnimationFrame(() => f(k - 1)) : r(); f(n); })", n)


def _box(page, key: str) -> dict:
    return page.evaluate("k => { const b = G.panes[k].over.getBoundingClientRect();"
                         " return {x: b.left, y: b.top, w: b.width, h: b.height}; }", key)


def _drag(page, key: str, x0: float, y0: float, x1: float, y1: float, *, alt=False) -> None:
    """A drag in pane ``key``, corners as fractions of its plot area."""
    b = _box(page, key)
    if alt:
        page.keyboard.down("Alt")
    page.mouse.move(b["x"] + x0 * b["w"], b["y"] + y0 * b["h"])
    page.mouse.down()
    page.mouse.move(b["x"] + x1 * b["w"], b["y"] + y1 * b["h"], steps=12)
    page.mouse.up()
    if alt:
        page.keyboard.up("Alt")
    _frames(page)


def _x(page, key: str) -> list[float]:
    return page.evaluate("k => [G.panes[k].scales.x.min, G.panes[k].scales.x.max]", key)


def _y(page, key: str) -> list[float]:
    return page.evaluate("k => [G.panes[k].scales.y.min, G.panes[k].scales.y.max]", key)


def test_a_select_drag_reports_once_from_its_own_pane(page):
    """Finding 1. Synced, a drag selected in every pane and the handler ran in each."""
    page.evaluate("G.setMode('select')")
    before = _x(page, "main")
    _drag(page, "main", 0.2, 0.5, 0.4, 0.52)
    _drag(page, "resid", 0.6, 0.5, 0.7, 0.5)
    selects = page.evaluate("G.selects")
    assert [s[2] for s in selects] == ["main", "resid"]
    assert all(lo < hi for lo, hi, _ in selects)
    # a select zooms nothing, and leaves no rectangle behind in any pane
    assert _x(page, "main") == before
    assert page.evaluate("Object.values(G.panes).every(u => u.select.width === 0)")


def test_a_flat_drag_zooms_x_in_every_pane_and_paints_each_once(page):
    """Findings 10 and 12: one x, copied by value, one paint a pane."""
    page.evaluate("mount({main: Array.from(X)})")   # a ramp, so y has to follow x
    _frames(page)
    page.evaluate("paints = {}")
    y_before = _y(page, "main")
    _drag(page, "main", 0.3, 0.5, 0.5, 0.51)
    lo, hi = _x(page, "main")
    assert 5 < lo < hi < 60
    assert _x(page, "ticks") == [lo, hi] and _x(page, "resid") == [lo, hi]
    assert page.evaluate("paints") == {"main": 1, "ticks": 1, "resid": 1}
    # an x-only zoom re-ranges y to the window rather than holding the old range
    assert _y(page, "main") != y_before


def test_a_box_drag_holds_its_y_range_until_a_double_click(page):
    """y-zoom: the pane dragged in, and no other, keeps the range across x zooms."""
    full_x, main_y, resid_y = _x(page, "main"), _y(page, "main"), _y(page, "resid")
    _drag(page, "main", 0.2, 0.2, 0.6, 0.6)
    boxed = _y(page, "main")
    assert boxed != main_y and _y(page, "resid") == resid_y
    b = _box(page, "main")
    page.mouse.move(b["x"] + 0.5 * b["w"], b["y"] + 0.5 * b["h"])
    page.mouse.wheel(0, -200)
    _frames(page)
    assert _x(page, "main") != full_x
    assert _y(page, "main") == boxed
    page.mouse.dblclick(b["x"] + 0.5 * b["w"], b["y"] + 0.5 * b["h"])
    _frames(page)
    assert _x(page, "main") == full_x and _x(page, "resid") == full_x
    assert _y(page, "main") == main_y


def test_the_wheel_zooms_about_the_pointer_and_shift_or_alt_pans(page):
    b = _box(page, "resid")
    page.mouse.move(b["x"] + 0.25 * b["w"], b["y"] + 0.5 * b["h"])
    at = page.evaluate("G.panes.resid.posToVal(G.panes.resid.cursor.left, 'x')")
    page.mouse.wheel(0, -300)
    _frames(page)
    lo, hi = _x(page, "main")
    assert lo < at < hi and hi - lo < 55
    width = hi - lo
    page.keyboard.down("Shift")
    page.mouse.wheel(0, 200)
    page.keyboard.up("Shift")
    _frames(page)
    lo2, hi2 = _x(page, "main")
    assert lo2 > lo and abs((hi2 - lo2) - width) < 1e-9
    _drag(page, "main", 0.6, 0.5, 0.4, 0.5, alt=True)
    lo3, hi3 = _x(page, "resid")
    assert lo3 > lo2 and abs((hi3 - lo3) - width) < 1e-9


def test_the_readout_comes_from_the_pane_under_the_pointer(page):
    b = _box(page, "main")
    for f in (0.2, 0.4, 0.6):
        page.mouse.move(b["x"] + f * b["w"], b["y"] + 0.5 * b["h"])
    _frames(page)
    hits = page.evaluate("G.cursors")
    assert hits and all(h is not None and h["key"] == "main" for h in hits)
    assert hits[-1]["idx"] > hits[0]["idx"]
    page.mouse.move(b["x"] + 0.5 * b["w"], b["y"] - 40)
    _frames(page)
    assert page.evaluate("G.cursors.at(-1)") is None


def test_a_live_update_keeps_the_readers_zoom(page):
    """``setData``: new numbers for a pane, the window the reader chose kept."""
    _drag(page, "main", 0.3, 0.2, 0.6, 0.7)
    window, y = _x(page, "main"), _y(page, "main")
    page.evaluate("G.setData('main', [Array.from(X, x => 100 + 40 * Math.cos(x))])")
    _frames(page)
    assert _x(page, "main") == window and _y(page, "main") == y
    assert page.evaluate("G.panes.main.data[1][0]") == 100 + 40 * math.cos(5)


def _pixel(page, key: str, x: float, y: float) -> list[int]:
    """The RGBA the pane's canvas holds at data point (x, y)."""
    return page.evaluate("""([k, x, y]) => {
        const u = G.panes[k];
        const px = Math.round(u.valToPos(x, 'x', true)), py = Math.round(u.valToPos(y, 'y', true));
        return Array.from(u.ctx.getImageData(px, py, 1, 1).data);
    }""", [key, x, y])


def test_a_theme_switch_repaints_in_the_new_colour(page):
    """Finding 5: colours are functions read at each draw, so one redraw restyles."""
    page.evaluate("mount({main: new Array(X.length).fill(100)})")
    assert _pixel(page, "main", 30, 100) == [0xc2, 0x3b, 0x22, 255]
    page.evaluate("document.documentElement.style.setProperty('--plot-calc', '#1f77b4');"
                  " G.redraw()")
    _frames(page)
    assert _pixel(page, "main", 30, 100) == [0x1f, 0x77, 0xb4, 255]


def test_a_series_on_part_of_the_grid_draws_only_there(page):
    """Finding 10: one x array, and a null is a gap uPlot leaves undrawn."""
    page.evaluate("""mount({main: rx.scatter(X.length,
        Int32Array.from({length: X.length / 2}, (_, i) => X.length / 2 + i),
        new Array(X.length / 2).fill(100))})""")
    assert page.evaluate("G.panes.main.data[1].length === X.length")
    # a grid line may cross the gap, but the series does not
    assert _pixel(page, "main", 15, 100) != [0xc2, 0x3b, 0x22, 255]
    assert _pixel(page, "main", 50, 100) == [0xc2, 0x3b, 0x22, 255]


def _labels(page, key: str) -> list[str]:
    return page.evaluate("k => G.panes[k].axes[1]._values", key)


def test_a_sqrt_axis_prints_several_labels(page):
    """Finding 2, through ``setY``, which rebuilds the pane at the same x."""
    page.evaluate("mount({main: Array.from(X, x => (x - 5) * 200)})")
    _drag(page, "main", 0.2, 0.5, 0.8, 0.51)
    window = _x(page, "main")
    page.evaluate("G.setY('main', 'sqrt')")
    _frames(page)
    assert _x(page, "main") == window
    labels = [s for s in _labels(page, "main") if s]
    assert len(labels) >= 4, labels


def test_a_narrow_range_prints_labels_that_differ(page):
    """Finding 3: a parameter spanning 1e-4 printed one number five times."""
    page.evaluate("mount({main: Array.from(X, x => 10.2510 + 0.0008 * (x - 5) / 55)})")
    labels = [s for s in _labels(page, "main") if s]
    assert len(labels) >= 3 and len(set(labels)) == len(labels), labels


def test_a_resize_shows_in_the_next_frame_with_no_timer(page):
    """The ResizeObserver path: uPlot has no autosize of its own."""
    page.evaluate("document.getElementById('host').style.width = '520px'")
    _frames(page, 2)
    assert page.evaluate("Object.values(G.panes).map(u => u.width)") == [520, 520, 520]
    assert page.evaluate("G.panes.main.ctx.canvas.width") == 520 * page.evaluate("devicePixelRatio")

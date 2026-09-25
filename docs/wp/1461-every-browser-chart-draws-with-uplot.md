# WP-1461 — every browser chart draws with uPlot

Milestone: unscheduled · Status: 🔄 2026-09-25 — tasks 2-4 done: the payload route settled, uPlot vendored at its pin, the module's core built, browser-tested and reviewed; the pilot next
Depends on: —
Priority: P2 2026-09-24 — the maintainer's decision that every browser chart builds on one module; today plotly blocks every GUI open for 0.7-0.8 s before the first plot

## Goal

Every 2D chart rietx draws in a browser comes from one rietx chart module
built on uPlot. That covers the GUI's pattern and Series panels,
`rietx watch`, `rietx compare` and the file `write_html` writes. None of those
pages loads plotly.js. Opening the GUI on the NAC example has no long frame
from a chart library, and § Acceptance holds against today's plotly renderer
measured the same way on the same machine.

## Context

### How the numbers were taken

The spike, its logs and screenshots are in
[`1461-uplot-spike/`](1461-uplot-spike/README.md), and every number below
names the log it comes from. Unless a line says *latency*, a number is
main-thread work: the change in CDP `TaskDuration`, minus the page's idle
rate over the same wall time, per event. Frames come from a
`requestAnimationFrame` loop and the `long-animation-frame` entry, which
fires above 50 ms. The browser is headless Chrome for Testing from
playwright's chromium build 1223, on an Apple M4 shared with other sessions.
Load averages ran from 7 to 29 during the runs, so absolute times move with
load. Ranges are over at least three runs where a log has them, and the
claims rest on ratios measured side by side.

The first draft of this WP timed plotly calls by promise latency. That
overstated plotly's resize about ninefold, because `Plots.resize` waits on a
100 ms `setTimeout` before it relayouts. `results/gpu3.txt` is that
latency-timed run. Everything quoted below is work unless it says otherwise.

### What plotly costs today

**The library head-to-head** at NAC's 59 498 channels, five series, three
fresh pages each (`results/bench_td.txt`):

| | plotly.js (Python `plotly` 7.1.0) | uPlot 1.6.32 | plotly / uPlot |
|---|---|---|---|
| minified / gzip | 4.82 MB / 1.47 MB | 51 KB / 22 KB | 94× / 67× |
| load and parse | 400-489 ms | 9.2-11.2 ms | ~45× |
| first draw | 197-265 ms | 27.5-32.6 ms | ~7× |
| new data | 23.9-27.2 ms | 9.9-10.3 ms | ~2.5× |
| zoom | 3.75-4.17 ms | 1.62-1.69 ms | ~2.4× |
| resize | 11.5-12.9 ms, then 101 ms of timer latency | 1.7-2.5 ms | ~6× in work |

Sizes are in `results/sizes.txt`. A plotly resize through `relayout` with an
explicit width and height costs 10.2-11.4 ms and skips the timer.

**Today's GUI**, NAC example fitted through the server
(`results/gui_td.txt`, `gui_boot.txt`, `run3.txt`, `gui2.txt`):

- **Opening.** Evaluating `plotly.js` is one long animation frame of 700-811
  ms across seven runs. The pattern's first `scattergl` react is a second
  one of 315-415 ms. The page answers no input during either. Under this
  load the first plot landed 1481-2295 ms after navigation. An earlier run
  under lighter load landed at 842 ms.
- **Resizing.** A viewport resize costs 27-61 ms of work for the whole app,
  of which plotly's share is about 12 ms. `Plots.resize` then resolves
  120-144 ms after it was asked (latency). The same latency ends every
  gesture that changes the layout around the plot. That happened after 3 of
  3 exclude drags, the double-click reset and 1 of 5 zoom drags; what
  changes the height is not traced.
- **Zooming.** Every zoom refetches `/api/result/window`. At the default
  budget that is 906 KB, fetched in 65-74 ms (latency). Zoomed windows took
  6-53 ms, then a react of 6-26 ms.
- **Per pointer move**, react, refetch and resize work included: hover
  2.11-2.27 ms over four runs, drag-zoom 3.66 ms and an exclude drag 4.69 ms
  over one run each.

### Staying on plotly, costed

Three changes would remove most of the lag without a new library:

- `relayout` with an explicit size instead of `Plots.resize` (10.2-11.4 ms
  of work, no timer);
- the full-resolution data in the page and a client-side zoom (D4), where a
  plotly zoom costs 3.75-4.17 ms;
- a partial plotly bundle, which is unmeasured.

The migration buys the rest:

- 400-489 ms less script evaluation at every open (a 700-811 ms frame in
  the app under load);
- a first draw about 7× cheaper;
- updates about 2.5× cheaper;
- the plotly-only code in § What changes deleted;
- 4.8 MB less in every file `write_html` writes.

The maintainer asked on 2026-09-24 for one backend for all plotting "if
it's good". The first task confirms that choice on these corrected numbers.

### Every feature, rebuilt on uPlot and measured

`proto.html` rebuilds the GUI's pattern plot on synthetic data.
`proto2.html` rebuilds the Series trajectory and the compare overlay, and
adds an in-situ 2D map as the first chart no page has yet.
`proto_driver.mjs` drives both with real mouse and wheel input. **The
prototype has none of the app's own work**: no Svelte, no stores, no
ten-field readout. So its costs are a floor for the port, never a
prediction, and § Acceptance measures the real pages.

At 59 498 points, three runs (`results/proto_59498*.txt`, the files without
`allmarkers`), every row held a p95 frame of 17.7 ms or less with **zero
long animation frames**:

| Behaviour (where it is used today) | uPlot mechanism | Per event, ms |
|---|---|---|
| hover readout, nearest reflection and peak (Plot strip, watch hkl) | `setCursor` hook, binary search | 0.65-0.95; tick pane 0.34-0.74 |
| drag-zoom (all) | built in | 0.84-1.33 |
| wheel zoom; wheel pan; alt-drag pan | a 20-line listener | 3.11-3.70; 2.88-3.52; 3.81-4.06 |
| exclude-region drag, armed (Plot) | `drag.setScale = false`, `setSelect` hook | 0.85-1.51 |
| peak drag-move; click-add (Plot) | listeners on `u.over`, `posToVal` | 1.09-1.17; 2.19-3.17 |
| shift-click and right-click on a peak (Plot) | the same listeners | asserted in the log |
| table-to-plot hover ring (Peaks) | a DOM overlay, no redraw | 0.16-0.22 |
| legend toggle (all) | `setSeries` | 1.19-1.37 |

And the one-off operations, same runs:

| Operation | uPlot mechanism | ms |
|---|---|---|
| mount three linked panes | three instances, cursor sync, a `setScale` hook | 53-94 |
| double-click reset | built in | 10.3-23.6 |
| linear, √ or log scale | `distr` 1, 100 or 3; a pane rebuild | 7.0-16.1 |
| theme switch | colour functions re-read at every draw | 0.7-3.9 |
| live stage update, zoom kept (watch) | `setData(data, false)` | 16.2-33.8 |
| resize | `setSize` | 1.7-2.7 |
| 426 or 92 103 candidate lines (Plot) | a draw hook, one stroke per pixel column | 0.5-1.4 or 15.9-20.0 |
| copy PNG to the clipboard, read back as `image/png` | panes composited, `ClipboardItem` | 20.5-48.7 |
| copy the visible data as TSV | `writeText` | 32.6-37.8 for 59 497 rows; 1.6-1.8 zoomed |

With the 92 103 candidate lines drawn, hover costs 0.39-0.52 ms and wheel
zoom 5.11-5.47 ms.

Single runs, so no range (`results/proto_run2.txt`, `proto_dpr2.txt`,
`run3.txt`):

- **devicePixelRatio 2**, 22 003 points: every per-event gesture cost
  0.05-3.4 ms and the double-click reset 12.4 ms, with zero long frames.
  The PNG copy is 2400×1276 in 42 ms. GPU raster time was not measured.
- **200 000 points**: hover 0.90 ms, wheel zoom 8.4 ms, reset 40 ms. Long
  frames: 51 ms in the wheel zoom, 56 ms in the exclude drag and 59 ms in the
  wheel zoom with candidate lines. That is the ceiling D4 needs.
- **SVG export** of a zoomed window: 180 ms, 526, 30 and 66 kB for the three
  panes, faithful to the canvas (`shots/export-svg.png`).
- **Standalone page**, the figure `write_html` draws, from the same arrays:
  1.63 MB, drawn 83-93 ms after navigation, against plotly's 6.53 MB at
  598-686 ms (latency, three loads each). Most of the 1.63 MB is the arrays
  at full JSON precision.
- **Series trajectory** with esd whiskers and a tooltip: hover 1.56 ms.
  **Compare overlay**, 10 × 22 003 with hover focus: hover 1.34 ms, wheel
  zoom 2.80 ms. **2D map**, 200 × 22 003 from a max-pooled pyramid: built in
  71 ms, wheel zoom 1.56 ms, hover 0.88 ms. These three are gross, without
  the idle subtraction.

### What the spike found that a session would otherwise relearn

1. **Cursor sync carries a drag selection to every pane in the group**, so a
   `setSelect` handler runs once per pane. Five exclude drags added fifteen
   regions until the handler ran only in the pane the drag began in
   (`results/proto_run1_before_fixes.txt`). The module's core goes further
   and syncs the cursor only. Its `filters.pub` keeps a mousedown, mouseup
   and double-click in their own pane, so a drag is one pane's event and its
   handler runs once. That also matches plotly, which draws the zoom box in
   the dragged subplot alone.
2. **A custom scale needs its own ticks.** Under `distr: 100` (√) uPlot
   printed one y label. `splits` evenly spaced in √ space fixes it, as the
   GUI's `sqrtTicks` does today (`plot.ts:796-807`). The labels need a
   `filter` as well. uPlot applies its log-axis label filter when `distr` is
   3 or more and `log` is 10, and a √ scale is `distr: 100` with `log` at its
   default of 10. So every √ label but a power of ten printed blank until the
   core's `filter` returned the splits unchanged.
3. **Tick labels do not adapt to a narrow range.** A trajectory spanning
   1e-4 Å printed `10.251` five times. An axis over a refined parameter needs
   a `values` formatter whose precision follows the tick step.
4. **uPlot draws every marker.** At 59 498 points that costs 1.3-1.6× the
   thinned figures on redraw-heavy gestures: wheel zoom 4.10-5.78 ms, reset
   25-41 ms. Two runs in three had long frames of 55-67 ms, in the drag-zoom
   and the wheel zoom, against none in the thinned runs
   (`results/proto_59498_allmarkers_run*.txt`, load about 12). At 200 000 points
   every marker cost 13 ms per wheel event with long frames
   (`proto_run1_before_fixes.txt`). A `paths` builder keeping each
   device-pixel column's minimum and maximum brought that to 8.4 ms. D5 says
   which to use.
5. **uPlot takes its 2D context once, at construction**
   (`const ctx = self.ctx = can.getContext("2d")`), and reads every colour
   function again at each draw. A theme switch is one redraw. A y-scale
   switch rebuilds the pane.
6. **SVG needs a recording `Path2D`.** svgcanvas cannot read a native
   `Path2D`, and uPlot strokes every series through one. About 40 lines swap
   in a recording class for the export chart only. The export chart must
   also join no sync group. Otherwise its first `setScale` redraws the live
   panes while `Path2D` is swapped, which threw page errors and reset the
   zoom.
7. **The first draw from a new 2D-map pyramid level uploads a texture**:
   two long frames, 100 ms at most, in the first wheel zoom.
8. **uPlot leaves the canvas transparent**, so a PNG export fills the ground
   colour first.
9. **jsdom has no canvas.** `getContext` returns null and uPlot's
   constructor uses the context at once. vitest stubs uPlot the way
   `test-setup.ts` stubs `window.Plotly` today, and browser tests cover the
   drawing.
10. **One chart, one x array.** uPlot's default mode aligns every series on
    one sorted x array. Every surface has data on a second grid (D8). The
    fitted and masked NAC grids merge onto one 59 498-point axis, with every
    series null-padded, in 4.4-5.4 ms (`results/gui_td.txt`).
11. **A tooltip is a capability, not a requirement.** WP-1213 deleted
    plotly's hover box because it covered the data, and the GUI answers
    hover with its readout strip. The spike's tooltip costs the same as the
    strip. Adding one to the GUI is the maintainer's call.
12. **Link panes by value.** uPlot fires `setScale` hooks from a microtask,
    after the call that set the scale has returned. A flag set around that
    call is already clear when the echo arrives. And every `setScale`
    repaints its pane, even when the range has not moved. The spike linked
    its panes with such a flag until 2026-09-25, so every zoom, pan and reset
    painted the main and tick panes twice. `setX` now leaves alone a pane
    already at the range. The gesture table above was measured with the echo,
    so its zoom, pan and reset rows overstate the cost
    (`results/zoom_probe.txt`).
13. **Firefox stalls where Chromium does not.** The table above is Chromium
    only, and the maintainer reads in Firefox. `zoom_probe.mjs` sent Firefox
    155 the same drag-zoom twelve times, at devicePixelRatio 2 and 59 498
    points. Most drags painted in 3-9 ms over the three panes. Two stalls
    recurred at the same drags in every run. The residual line took
    117-296 ms on the first two drags. On drags 9-11, one paint spent
    29-204 ms in the two dashed curves. Chrome 148 painted every drag in
    9 ms or less, though neither timer sees
    GPU raster. Turning off `gfx.canvas.accelerated` moved neither stall. The
    load average was 67-84, which inflates their size but did not move them.
    The pilot's Firefox row must look for both.
14. **A drag-zoom on macOS three-finger drag waits for the OS.** That
    setting holds a drag open after the fingers lift, and the browser gets
    the mouse-up only when it ends. The maintainer's trackpad has it on.
    They felt about 300 ms between lifting and the zoom, in Chrome, Safari
    and Firefox alike, and confirmed the setting as the cause. No page sees
    the fingers lift, so no library can remove the wait, and plotly has it
    too. Wheel and pinch zoom have no release. The `?demo` readout splits a
    drag's wait at the mouse-up: the pointer sitting still before it, then
    the page's time after it. A latency probe must start its clock at the
    mouse-up.

### Behaviours the spike did not rebuild

Verified in the code by the review; each is carried by the port and named
by a test.

- **GUI pattern panel:**
  - y-zoom, and the y and y2 ranges it pins;
  - the raw view (no result), and Esc to disarm (`Plot.svelte:1224`);
  - axis titles that name where σ came from;
  - peak markers: circle or diamond, open or filled, esd whiskers capped at
    3×FWHM;
  - per-group peak-fit curves on their own grids (`Plot.svelte:661-676`).
- **The readout's fields:** d-spacing, background, candidate hkl and
  emission line, peak-fit value, the masked-arm lookup, the residual kind.
- **Σχ² under a client zoom.** It is accumulated across the window
  (`session.py:2644-2651`). With full-resolution data it re-bases at each
  zoom as cum[i] − cum[i₀ − 1].
- **Series panel:**
  - the per-pattern obs, calc and Δ chart with its own excluded arm
    (`Series.svelte:363-374`);
  - the backward chain and the dashed tone of a path-dependent parameter;
  - an unrecovered pattern *plotted* as a cross, because "a gap reads as
    data nobody collected" (`series.ts:229-234`). The spike nulled it, which
    was wrong.
- **`rietx watch`:** the n_drawn-of-n_points annotation, the legend's cap
  label, the Δ/σ range ladder and the ±3σ band.
- **`write_html`:**
  - the weighted two-panel mode with its ±3σ band;
  - the per-phase `"hkl: …"` trace names that `test_magnetic_tick_row.py`
    parses out of the file;
  - its palette. It draws from `viz/plots.PALETTES` (calc `#ff7f0e`) while
    the browser pages use theme tokens (`--plot-calc` `#c23b22`), so the
    module takes a palette as input or the file changes colour silently.

### What changes

- **Pages.**
  - GUI: `gui/src/panels/Plot.svelte`, `lib/plot.ts`, `lib/peaks.ts`,
    `panels/Series.svelte`, `lib/series.ts`, `lib/plotly.ts`,
    `panels/Structure3D.svelte` (its loading only), `api.ts`.
  - The GUI server: the curves route (D4) in `src/rietx/gui/session.py` and
    `server.py`.
  - `rietx watch`: `src/rietx/watch/static/watch.mjs` and `watch-core.mjs`.
  - The page string in `src/rietx/compare_app.py`, which becomes a file
    (root CLAUDE.md: a page that is javascript is a file). Its `/api/state`
    drops the curves, and a route serves each variant's (D4).
  - `src/rietx/viz/html.py` and `src/rietx/viz/plotlyjs.py`.
- **Code that exists only to handle plotly.** It goes with plotly:
  - the axis pinning in `plot.ts` (`heldRanges`, `pinPatch`, reads of
    `ax._rl` and `_fullLayout`), which stops plotly autoranging on every
    `react`;
  - `movedAxes`, which parses `plotly_relayout` payloads;
  - the empty ring trace kept as SVG so select-drag does not crash;
  - `marker.color` set against the colorway, and `hoverinfo: "none"` on
    every trace;
  - the `!important` overrides of plotly's select outline;
  - the invisible marker overlay behind the Series error bars;
  - `Plotly.purge` for WebGL contexts, and the watcher's legend and margin
    placement.
  `readout`, `residual`, `curveToggles` and `sqrtTicks` in `plot.ts` stay as
  pure functions. `maskShapes` becomes the input of the shading hook.
- **Tests.**
  - `test_gui_manual.py` partitions the GUI's routes. The curves route needs
    a chapter, and the two window routes leave it when they go.
  - The `/plotly.js` route and its fallback: `test_gui_server.py`,
    `test_watch_app.py`, `test_gui_dist.py`.
  - The no-plotly paths: `test_snapshot.py`, `test_events_viz_history.py`.
  - The `importorskip("plotly")` in `test_examples.py`.
  - `write_html`'s output: `test_magnetic_tick_row.py`.
  - `test_gui_palette.py:436-480`, `test_compare_ui.py` and
    `test_docs_consistency.py:523`.
  - `test_watch_browser.py` reads `_fullData` because it is "what was
    painted rather than what was asked for" (`:227`). Its replacement must
    keep that property: sample canvas pixels, or record the resolved
    `strokeStyle` at draw time.
  - `App.test.ts` stubs `Plotly.react` in about 20 blocks, and
    `structure3d.test.ts` asserts on `uirevision`.
- **Rules.** `gui/CLAUDE.md` § Usability, § Repairs found by use, § What is
  fitted, shaded and selectable, and § The view, the armed cursor and the
  theme's scope.
  - Rules about what the plot says survive the port. A tick belongs to the
    model, hiding a curve is by exception, a hover link never redraws the
    pattern, a region drag is an armed mode, `cumulative_chi2` is
    accumulated over every point, and a `ResizeObserver` sizes the chart,
    since uPlot has no autosize.
  - Rules about how plotly behaves are deleted: the autorange traps, the
    view handed back on every draw, `doubleClick: "autosize"`, and
    `responsive: true` listening to window resizes only.
- **Dependencies.** `pyproject.toml`'s `gui` and `viz` extras. ATTRIBUTION.md's
  two plotly rows gain uPlot and svgcanvas rows.
- **Docs.** The manual's GUI chapters and their screenshots,
  `using/cli.md`, `using/install.md`, `using/files.md`, root CLAUDE.md,
  `tests/CLAUDE.md` and README. In the skill, `references/api.md` is
  generated by `make_api_index.py`.

### The payload behind a client zoom, measured

Task 2 measured D4 and D8 on three real answers:

- the NAC example, fitted through a `GuiSession`;
- the `nac` and `lab6_capillary` compare standards, four variants each;
- the QPA sample-1 series of eight patterns.

`payloads.py` builds each payload and times the server's half.
`payload_probe.mjs` fetches each one in Chrome for Testing 148 and Firefox
155, then times the decode, the parse and the grid union. `transport.py` times
the real GUI route with curl. Load averages were 3-5, and every range is over
six runs (`results/payloads.txt`, `payload_probe_chrome.txt`,
`payload_probe_firefox.txt`, `transport.txt`).

The proposed shape sends three things. The pattern's own 2θ and intensity
cover every channel. `fitted` lists the channels the fit kept. The five model
arrays cover those channels. Two facts carry it, and both held bit for bit on
NAC and on a series member:

- the result's 2θ is the pattern's 2θ under the fitted mask;
- the result's `y_obs` is the pattern's intensity on those channels.

So the union D8 asks for is the pattern's own channel list, and the model
lands on it by index.

**NAC, 59 498 channels, 22 003 fitted.** Server times are from
`payloads.txt`. The parse column leaves out the UTF-8 decode, which adds
0.1-1.2 ms to a JSON body.

| Payload | Size | Built, ms | Serialised, ms | Chrome parse, ms | Firefox parse, ms |
|---|---|---|---|---|---|
| today, one 4000-point window | 0.91 MB | 6.8-7.3 | 13.9-16.6 | 0.9-1.1 | 2.4-2.6 |
| today's JSON, every channel | 3.41 MB | 8.1-11.0 | 51.7-56.8 | 3.8-5.1 | 8.4-9.2 |
| proposed, JSON | 3.56 MB | 1.3 | 54.5-54.7 | 3.8-5.4 | 8.4-8.8 |
| proposed, JSON at seven digits | 2.08 MB | 1.3 | 36.2-37.3 | 2.7-4.0 | 3.9-4.2 |
| proposed, float64 binary | 1.93 MB | 1.3 | 0.2 | 0.0-0.2 | 0.0-0.1 |
| proposed, float32 binary | 1.01 MB | 1.3 | 0.1-0.2 | 0.0-0.1 | 0.0-0.1 |

- **The real route** answered its first byte in 59.3-60.3 ms at every
  channel and 20.5-21.3 ms at 4000 points. That is the server's work. On
  loopback the transfer took 0.2-1.4 ms for every payload here. `gui_td.txt`'s
  152-171 ms fetch of the same payload ran at load 7-29.
- **The union** onto 59 498 channels took 0.5-5.3 ms in Chrome and 0.7-1.6 ms
  in Firefox, for today's sorted merge and for the index alike. The index
  removes the merge as code. It saves no time.
- **Float32** puts at most 6.0e-8 relative error on any array. A Σχ² re-based
  as cum[j] − cum[i−1] loses more: 1.2e-3 of itself over a window of 0.1 % of
  the NAC pattern, and 6.5e-5 over 1 %.

**Compare.** On both standards every variant fitted the same channels with
the same `y_obs`. Today `/api/state` carries every ready variant's curves on
each 700 ms poll:

| `/api/state`, four variants | `nac`, 22 003 channels | `lab6_capillary`, 116 001 channels |
|---|---|---|
| today, 4000 points a variant | 2.96 MB, 41.3-42.2 ms serialised | 3.31 MB, 45.4-45.5 ms |
| today's shape, every channel | 8.77 MB, 123.3-123.7 ms | 45.69 MB, 632.9-653.8 ms |
| without the curves | 27.3 kB | 25.9 kB |
| one variant's curves, float64 binary | 1.06 MB, 1.6-1.7 ms | 5.57 MB, 8.7-9.7 ms |

Today's poll already costs the browser 3.2-3.6 ms of parse in Chrome and
7.5-9.0 ms in Firefox, every 700 ms. The server serialises it on a thread
beside the worker that fits. At every channel, `lab6_capillary`'s poll would
parse in 118-125 ms in Firefox, a long frame on every poll.

**Series.** `/api/series/result` for eight patterns is 480 kB, serialised in
2.3-2.5 ms and parsed in 0.3-1.1 ms. A member has 7251 channels. Today's
4000-point budget already sends 5864 of them, in 0.66 MB. All 7251 in float64
binary are 0.44 MB.

**The ceiling.** `payloads.txt` counts the channels of every pattern the
repository reads. Lab patterns run from 255 to 7251. The 11-BM patterns run
from 48 000 to 59 498, except `11BM_LaB6_660a.fxye` at 132 992, which
`lab6_capillary` fits over 116 001. `proto_driver.mjs` ran at those sizes,
three runs each at load 3-5:

- **132 992 points, thinned per pixel column.** One long frame over the three
  runs: 51 ms, in one hover sweep. Wheel zoom cost
  4.47-5.47 ms, the pans 4.75-5.55 ms and the reset 13.6-25.6 ms
  (`proto_132992_run*.txt`).
- **132 992 points, every marker.** A long frame of 62-67 ms in the wheel zoom
  with 92 103 candidate lines, in 3 of 3 runs. The reset cost 32.7-43.6 ms
  (`proto_132992_allmarkers_run*.txt`).
- **200 000 points, thinned.** A long frame of 53-57 ms in that same gesture,
  in 3 of 3 runs (`proto_200000_run*.txt`). The spike's first run at this
  size, at load 7-29, had long frames in three gestures. At load 3-5 only this
  one kept its long frame.

### Decisions this WP takes

Each carries the recommended answer. The maintainer confirms or overturns it
in the first task.

**Decided 2026-09-25.** The maintainer confirmed the migration to uPlot, D1
(every chart shown in a browser) and D2 (a vendored copy), and D4-D8 as
recommended. D3 went unanswered and stands as recommended. They asked how a
vendored copy stays current, and D2 now says. **D5 is decided in the
pilot.** It was first confirmed on a summary saying every marker "stays fast
at NAC's size", while finding 4 says two runs in three had long frames. Put
back with those numbers, the maintainer chose to let the pilot measure both
marker paths on the real panel and pick. The 3D viewer's move is
[WP-1462](1462-the-structure-viewer-draws-with-threejs.md), filed the same
day.

- **D1. Scope.** Every 2D chart in a browser.
  - matplotlib stays for the files it writes (`plots.py`, `indexing.py`,
    `plot_for_vlm`), which are made without a browser.
  - The 3D structure viewer is not covered (§ Non-goals). So this WP gives
    one backend for charts, not for all plotting.
- **D2. uPlot vendored once and bundled into the GUI.**
  - `uPlot.iife.min.js` and `uPlot.min.css` at a pinned version go into
    `src/rietx/viz/static/`, with uPlot's LICENSE beside them. The file
    carries only its URL and version (`results/sizes.txt`), and MIT needs
    the notice with every copy.
  - The watcher and the compare page load it from their servers.
    `write_html` inlines it with the notice.
  - The GUI bundles it and the chart module into its dist through a vite
    alias, as it bundles CodeMirror. plotly was loaded at runtime because
    of its 4.8 MB (WP-1010), and uPlot is 51 KB.
  - `gui/scripts/build_info.py` names the vendored directory in its digest,
    or the dist would go stale unseen. Bundling keeps the chart layer under
    svelte-check and within vitest's reach.
  - **Keeping it current.** Nothing in the repository watches a dependency
    today: there is no Dependabot or Renovate configuration. plotly.js moves
    with the Python `plotly` package, so a vendored uPlot would be the first
    copy that stays frozen by default. So uPlot is pinned exactly in
    `gui/package.json`, and `npm run build` copies its three files into
    `src/rietx/viz/static/`, the one step that writes them. A test holds the
    version in the vendored file's banner equal to the pin. Dependabot,
    limited to uPlot and svgcanvas, opens a pull request for each release.
    svgcanvas joins its allow list with the export task.
    The lock file is in the dist's digest, so that pull request stays red
    until someone runs the build, which refreshes the vendored copy too.
- **D3. One chart module in two layers.** `src/rietx/viz/static/rxplot.mjs`
  holds:
  - shared plumbing: panes on one x, sync, gestures, the readout hook,
    formatters, exports, theme and palette input;
  - the figures built on it: the pattern, the trajectory, the overlay.

  Its pure half (nearest lookups, tick formatting, TSV, the grid union) runs
  under `node --test` and vitest. Its drawing runs under browser tests.
- **D4. Full-resolution data once, zoom in the client.** Task 2 settled the
  route and the ceiling (§ The payload behind a client zoom).
  - **The route.** One GUI route answers with a fitted pattern's curves at
    full resolution, as float64 binary. The body is a uint32 length, a JSON
    header, then 8-aligned arrays. The header carries what the window
    route's JSON carries beside its arrays: `weighted`, the ticks and their
    hkl, `stale` and the counts. The arrays are the pattern's 2θ and
    intensity over every channel, `fitted` (int32), and `y_calc`,
    `y_background`, `delta`, `delta_raw` and `cumulative_chi2` on the fitted
    channels. The raw view is the same payload without the model arrays.
  - **Binary** cuts the server's work from about 60 ms to under 2 ms and the
    browser's parse from 4-9 ms to nothing, at 57 % of the bytes. JSON at
    seven digits still serialises for 36-37 ms.
  - **Float64**, because float32 moves a re-based Σχ² by 1.2e-3 of itself
    over a narrow window. At float64 the readout prints the server's numbers.
  - **A stale payload carries the current mask too.** `fitted` indexes the
    result's grid, and once `stale` is true that differs from the protocol's
    mask. The masked arm is the current protocol's, as `_masked_arm`
    computes it today. This part is unbuilt and unmeasured.
  - **When it is fetched.** The GUI fetches on open, on checkout and when a
    run ends (`App.svelte:960-976`), never per stage. It also refetches
    after an edit that can change the mask, as `draw` does today
    (`Plot.svelte:388-396`). A zoom fetches nothing.
  - **The series panel** reads a member through the same route with its
    index. `/api/series/result` stays JSON at 480 kB.
  - **The compare page's `/api/state`** drops the curves. Each variant's
    curves come once, in this format, when the variant lands.
  - The decoder is about five lines, and it belongs to `rxplot.mjs`'s pure
    half (D3), shared by all three pages. `/api/result/window` and
    `/api/series/window` go when the plotly renderer goes.
  - This reverses `session.py:2575-2582`, which excluded the arrays because
    "a browser then decimates for a plot it can only draw a few thousand
    points of". uPlot draws 59 498 at the costs above.
  - `rietx watch` is outside this route. The fit writes its snapshot per
    stage, decimated, at the cost WP-1413 measured.
  - **The ceiling follows D5.** Above it the server keeps decimating through
    `compare.decimation_index`. With per-column thinning it is 150 000
    channels, which binds no pattern on disk. The largest is 132 992, which
    held in the prototype, and 200 000 did not. With every marker it stays
    100 000, unmeasured, since every marker had a long frame at 132 992 in
    3 of 3 runs. The pilot measures the real panel at 132 992 either way.
- **D5. Draw every marker at NAC scale, or thin per pixel column.**
  Decided in the pilot (2026-09-25, § Decided). The pilot builds both paths
  and measures them on the real panel in all three browsers. It takes every
  marker if that holds § Acceptance 2's zero long frames, and thinning
  otherwise.
  - That costs 1.3-1.6× the thinned figures. In two runs of three it also
    made long frames of 55-67 ms, where the thinned runs had none
    (finding 4). This line said "stays inside a frame" until the
    `/code-review` pass of 2026-09-25 found it contradicting finding 4 and
    the logs. The client then does not decimate, so `decimation_index`
    remains the one authority for which points exist, as `compare.py:1021`
    and `gui/CLAUDE.md` require, and the watcher's n_drawn stays true.
  - Thinning per pixel column is the fallback if a browser or a larger
    pattern needs it. Adopting it retires "the client does not decimate" in
    the same commit.
- **D6. Exports.**
  - Copy PNG, download PNG, copy the visible data as TSV, and download SVG
    (svgcanvas, loaded on the first export, with its own and canvas2svg's
    notices). They replace the modebar's camera.
  - The modebar's modes become gestures: drag to zoom, wheel to zoom,
    shift-wheel or alt-drag to pan, double-click to reset, and the armed
    range and exclude modes as today.
- **D7. `write_html` keeps its name.** It loses `include_plotlyjs`, since
  uPlot is always inlined. `figure_from_arrays` returns a plotly Figure, so
  it is replaced by a function returning the page. An old file still opens.
  Code passing either breaks, and the break is recorded in the open
  milestone's record on the day it lands.
- **D8. A second grid, per surface.**
  - GUI pattern: the union is the pattern's own channel list, and the model
    lands on it through `fitted` (task 2). Onto 59 498 channels that took
    0.5-5.3 ms, no faster than merging the two grids. The index removes the
    merge as code.
  - Peak-group fits, candidate lines, ticks and peak markers: draw hooks.
  - Compare variants: each is decimated today on its own index set
    (`compare_app.py:481-495`). Every variant of `nac` and `lab6_capillary`
    fitted the same channels, bit for bit. So the variants share one x, and
    uPlot takes their typed arrays with no padding. The Δχ² panel's
    `resample` (`compare_app.py:461-472`) becomes a subtraction.
  - Series trajectory: in chain order, a heat-then-cool series loops. That
    needs mode 2 (an x per series) or a draw hook.
  - Series per-pattern chart: the union, as for the pattern panel.

### Where it will bite

- **Safari and Firefox are unmeasured.** Only Chromium is cached here, and
  `rietx gui` opens the default browser, which on a Mac is often Safari.
  WebKit also caps canvas size below Chromium, so the 2D map's 22 003-wide
  base level may need tiling. Both browsers are inside the pilot's gate.
- **The boot win needs the 3D viewer gated.** `Structure3D` mounts hidden
  inside Model at boot (`Model.svelte:455`, `viewer = true`), and it loads
  plotly. Loading it only when the view is first shown moves plotly's
  evaluation, a 700-811 ms frame today, onto that first click.
- **The prototype flatters.** Its per-event costs have no app overhead. The
  pilot measures the real panel against the real plotly renderer.
- **One maintainer.** uPlot is Leon Sorokin's. Vendoring a pinned copy
  means a stalled upstream costs nothing until a browser change breaks it.

## Non-goals

- **The 3D structure viewer.** It draws a scene, and uPlot has no 3D. It
  keeps plotly (`mesh3d`, `scatter3d`), loaded when first shown, and the `gui`
  extra keeps plotly until it moves.
  [WP-1462](1462-the-structure-viewer-draws-with-threejs.md) moves it.
- **matplotlib figures.** They are files, written without a browser.
- **New chart types.** The 2D map shows the module can carry one. A series
  map belongs to the WP that wants it; 1317 is the nearest.
- **The theme tokens** (`viz/theme.py`), consumed unchanged.

## Tasks

- [x] The maintainer confirms the migration on § Staying on plotly's numbers and decides D1-D8, and this file records which (D5 deferred to the pilot by that decision)
- [x] Measure D4 and D8 on real payloads (the NAC result, a compare standard, a series): JSON against binary arrays, parse, grid union. Settle the route and the ceiling. (Float64 binary, the pattern's own grid with a fitted index, compare curves out of the poll; the ceiling follows D5.)
- [x] Vendor uPlot 1.6.32, its css and LICENSE into `src/rietx/viz/static/`, copied there by `npm run build` from the exact pin in `gui/package.json` (D2, § Keeping it current). Add the ATTRIBUTION row and put the directory in `build_info.py`'s digest. A test holds the vendored banner's version equal to the pin. Add `.github/dependabot.yml` for uPlot in `gui/`. Rebuild the dist, since the pin moves the digest. (Serving it moved to the watch and compare tasks, where a page first loads it. svgcanvas joins Dependabot with the export task, which adds the dependency.)
- [x] The module's core: panes on one x, sync, drag, wheel and pan, y-zoom, select, the readout hook, the `ResizeObserver` path. Findings 1-3, 5 and 10 each get a case: the pure half under `node --test` and vitest, the drawing in a browser test. (`src/rietx/viz/static/rxplot.mjs`; `tests/rxplot.test.mjs` through `tests/test_rxplot.py`, and `tests/test_rxplot_browser.py`, which covers finding 12 too. Vitest moved to the pilot, where the GUI first imports the module.)
- [ ] Pilot, the gate: the curves route (D4) and its decoder in the module's pure half, and the GUI pattern panel on the core behind a flag, with the plotly renderer still selectable. Port the spike driver to the real page as the acceptance probe. Measure § Acceptance 1-3 against the plotly renderer on the same machine, in Chromium, WebKit and Firefox through playwright's builds. Build both marker paths (D5) and measure each, at NAC's 59 498 channels and at `11BM_LaB6_660a.fxye`'s 132 992. Record go or no-go, which marker path, and so which ceiling, in the handover. The GUI's vitest imports the module's pure half.
- [ ] GUI pattern panel complete: peaks, candidates, masks, raw view, readout fields, Esc, axis titles. Delete the plotly-only code, stub uPlot in `test-setup.ts`, and move `App.test.ts` off the `Plotly.react` stub. Drawn colours are asserted from pixels or from the recorded `strokeStyle`.
- [ ] `rietx watch` on the module, serving the vendored uPlot from its own server. `test_watch_browser.py` asserts what was drawn.
- [ ] GUI Series panel: trajectory (D8), per-pattern chart through the curves route, rings, crosses plotted, the dashed tone, the tick formatter
- [ ] `rietx compare`: its page becomes a file, on the module, and its server serves the vendored uPlot. `/api/state` drops the curves, and each variant's come once through a route (D4). `resample` becomes a subtraction.
- [ ] `write_html` writes the uPlot page, with the notice inline, the weighted mode, `viz/plots.PALETTES` as its palette and the `"hkl: …"` labels `test_magnetic_tick_row.py` reads. Drop `include_plotlyjs`, replace `figure_from_arrays`, take plotly out of the `viz` extra, and record the break.
- [ ] Exports: copy PNG, download PNG, copy TSV, SVG through svgcanvas with its notices. Pin svgcanvas exactly in `gui/package.json` and add it to `.github/dependabot.yml`'s allow list.
- [ ] Structure3D loads plotly when first shown. A test asserts no other page requests `/plotly.js`. Record the first-show cost.
- [ ] Remove the flag and the pattern panel's plotly renderer
- [ ] Docs: the `gui/CLAUDE.md` rules as § What changes sorts them, the manual's GUI chapters with regenerated screenshots, `using/cli.md`, `install.md` and `files.md`, root CLAUDE.md, `tests/CLAUDE.md`, README
- [ ] Tests: the suites in § Acceptance green, the fast count's movement stated, and every test listed in § What changes updated
- [ ] Skill: regenerate `references/api.md` with `make_api_index.py` when D7 lands, then `rietx skill --install . --copy`. Nothing else in the skill draws a browser chart.

## Acceptance

Measured by the spike driver ported to the real pages, on the NAC example,
in Chromium at devicePixelRatio 1 and 2. Each run is paired with the plotly
renderer on the same machine and load, and three or more runs give ranges.
These are measurements recorded in the handover, not test budgets (root
CLAUDE.md: a wall-clock budget in a test is a runaway guard).

1. **Opening the GUI:** no long animation frame is attributed to a chart
   library. Today plotly's evaluation is a 700-811 ms frame and its first
   draw a 315-415 ms frame.
2. **Gestures:**
   - Hover, drag-zoom, an exclude drag and a peak drag each cost no more
     main-thread work per event than the plotly renderer on the same run.
   - Wheel zoom and pan, which plotly's renderer does not offer, cost at
     most 8.3 ms per event, half a 60 Hz frame.
   - Every gesture holds a p95 frame of 17.7 ms or less with zero long
     animation frames.
   - A zoom ends without a network round trip.
3. **Resizing:** the chart's own work is at most 5 ms, and it shows its new
   size in the frame after the resize, with no timer.
4. **`write_html`** on the NAC result: at most half of today's plotly file,
   in both size and time to first draw. The spike measured 1.63 against
   6.53 MB and 83-93 against 598-686 ms.
5. **No plotly on chart pages.** No page requests `/plotly.js` except when
   the 3D view is first shown. `rietx watch`, `rietx compare` and a written
   file load no plotly at all.
6. **Coverage:** every behaviour in § Every feature and § Behaviours the
   spike did not rebuild is present and named by a test.
7. **Other browsers:** in WebKit and Firefox through playwright's builds,
   every gesture works, nothing throws, and per-event work is recorded.

```sh
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m pytest tests/test_watch_browser.py tests/test_gui_server.py tests/test_watch_app.py tests/test_magnetic_tick_row.py
npm --prefix gui test && npm --prefix gui run check
.venv/bin/python -m ruff check src tests examples
.venv/bin/python -m sphinx -W -q -b html docs/manual docs/manual/_build/html
```

## References

- uPlot 1.6.32, Leon Sorokin, MIT. <https://github.com/leeoniya/uPlot>
- svgcanvas 2.6.0, MIT, descended from Gliffy's canvas2svg (MIT).
  <https://github.com/zenozeng/svgcanvas>
- plotly.js, MIT, as served by the Python `plotly` 7.1.0 package.
- Apache ECharts 6.1.0, Apache-2.0. Measured once by latency
  (`results/gpu3.txt`): replacing its data at 22 003 points took 23-25 ms,
  longer than a 60 Hz frame. Not taken further.
- Grafana's time-series panel is built on uPlot, the prior art for a
  measurement UI on this library.
- Long Animation Frames API (W3C draft): what counts as a long frame here.

## Handover log

### 2026-09-25 (3rd session) — the payload route, uPlot vendored, the chart module's core

The pilot now has what it builds on. Measured on real answers, the curves
should travel as float64 binary over the pattern's own channels. That cuts
the server's 60 ms and the browser's parse to almost nothing, at 57 % of the
bytes. The compare page resends every variant's curves on every 700 ms poll
today, so it has to stop before it can go to full resolution. uPlot is
vendored at an exact pin, only the build writes the copy, and Dependabot
watches it. The chart module's core exists, with a test for each way the
spike found to get it wrong, and a review fixed four more defects in it. The
pilot, which decides go or no-go, has not started.

*Done:*
- Task 2: `payloads.py`, `payload_probe.mjs` and `transport.py` in the spike,
  with their logs. § The payload behind a client zoom holds the numbers, and
  D4 and D8 record what they settled. The ceiling follows D5: 150 000
  channels with thinning, 100 000 with every marker.
- Task 3: `gui/scripts/vendor.py` is the build's first step. The digest
  covers `src/rietx/viz/static/`, and `test_gui_dist.py` holds the banner to
  the pin and the files in the wheel. Also `LICENSE-3RD-PARTY.md`,
  ATTRIBUTION, `.github/dependabot.yml`, and `gui.yml` triggering on and
  diffing the vendored directory. The `gui/CLAUDE.md` rule fits its cap by
  dropping a stale size claim: `app.js` "well under" `vendor-cm.js` at
  114-164 kB, where the build prints 303 against 328 kB. Serving uPlot moved
  to the watch and compare tasks, and svgcanvas's Dependabot row to the
  export task.
- Task 4: `src/rietx/viz/static/rxplot.mjs`. Its pure half has 9 node cases,
  run by `tests/test_rxplot.py`. `tests/test_rxplot_browser.py` has 13
  chromium cases. Four guards were broken on purpose (findings 1, 2, 3 and
  12), and each failed with the expected message.
- `/code-review high --fix` made seven findings and fixed six (`c6f1cb80`):
  - a press under 8 px is a click, since uPlot turned a 1 px jitter into a
    whole-axis zoom;
  - a live update re-ranges an unzoomed y;
  - a narrow √ window keeps its ticks;
  - every tick label prints its own value;
  - the wheel test requires `rxplot.mjs`;
  - `vendor.py` names a missing package instead of printing a traceback.

  It declined narrowing the digest to the vendored files, because the pilot
  makes `rxplot.mjs` a GUI build input.
- Before the review, `share` heights went for want of a caller, and
  `setData` gained its case.
- Forward references: WP-1313 (the digest now covers the chart module) and
  WP-1462 (the allow list exists, and bundled code owes
  `LICENSE-3RD-PARTY.md` its licence).

*Measured:*
- The payload and ceiling figures are in § The payload behind a client zoom.
  The headline figures:
  - today's JSON route at every channel takes 59-60 ms to its first byte, of
    which 52-57 ms is `json.dumps`;
  - float64 binary takes 0.2 ms;
  - the parse falls from 3.8-5.1 ms in Chrome and 8.4-9.2 ms in Firefox to
    nothing;
  - the compare poll is 2.96 MB today, and 45.69 MB at every channel on
    `lab6_capillary`;
  - at 132 992 points, every marker gave a 62-67 ms long frame in 3 of 3
    runs.
- Fast suite on the final tree (main unchanged since the last handover, so
  this is the merge's tree): 6100 passed, 140 skipped and 2 failed, in 9:05.
  That is the `[dev]` venv plus playwright 1.63.0, on macOS arm64. No other
  suite was running, but load ran from 41 to 161. The total is 6242 against
  6179 last session. The +63 is the 16 tests added here (1 dist, 2 node
  wrappers, 13 browser) plus 47 from `test_watch_browser.py`, which was one
  module skip until playwright was installed and is now 48 cases.
- The 2 failures are that module's two seam cases, which assert at most 6
  resizes over a drag and counted 8. They failed again run alone, at load
  153-161. This branch changes no watcher file, and CI skips the module.
- The full selection did not run. Nothing here moves a measured number.

*Gotchas:*
- uPlot commits its first draw in a microtask, so a scale read right after
  construction is null. Wait a frame.
- Editing `rxplot.mjs` stales the dist. Rebuild with node 22
  (`~/.nvm/versions/node/v22.15.0/bin` first on `PATH`).
- Firefox rounds `performance.now()` to 1 ms unless
  `privacy.reduceTimerPrecision` is off (`payload_probe.mjs` sets it).
- `*.html` swallowed the browser harness, the seventh file it has taken.
  `.gitignore` carries a negation for it.
- The worktree guard refuses a heredoc naming git, and a shell variable in a
  `sed` or `node` argument. Run a scratchpad script by path.

*Next:*
1. The pilot, task 5, in a fresh session. Build the curves route first
   (`session.py`, `server.py`, its decoder in the module's pure half, a GUI
   chapter for `test_gui_manual.py`), since it fixes the panel's data shape.
   Then the pattern panel on the core behind a flag, then the probe in three
   browsers. WebKit needs playwright's webkit build, which is not cached here.
2. Rerun `tests/test_watch_browser.py` alone at low load. If the seam cases
   still count 8 resizes, file it against the watcher, not here.

### 2026-09-25 (2nd session) — the zoom delay, the maintainer's decisions, and WP-1462

The delay the maintainer felt on every zoom came from their trackpad. macOS
three-finger drag holds a drag's release back by about 300 ms, so every
browser and every chart library zooms that late, and no page can change it.
The search for it found a real defect as well: the prototype painted two of
its three panes twice on every zoom, and now paints each once. The
maintainer confirmed the move to uPlot and most of the design. One decision,
D5, went back to them, because the summary they confirmed it on misstated
the evidence. Moving the 3D viewer off plotly is filed as WP-1462, so once
both land no page needs plotly.

*Done:*
- Finding 12, the echo fix in `proto.html`. Finding 13, Firefox's two
  stalls. Finding 14, three-finger drag.
- `?demo` prints each frame's repaints, and after a drag it splits the wait
  at the mouse-up. `zoom_probe.mjs` counts and times the paints in Chrome
  for Testing or the installed Firefox, with `results/zoom_probe.txt`.
- The spike's `node_modules` is a real install with `puppeteer-core`, no
  longer a link into a dead scratchpad.
- `test_docs_consistency.py` drops gitignored files from the planning docs,
  so an `npm install` in a spike no longer breaks two link checks locally.
- § Decisions records the maintainer's answers. D2 and the vendoring task
  say how a vendored uPlot stays current. WP-1313's Inherited carries what
  that means for a post-merge rebuild. WP-1462 is filed with its ROADMAP
  row, and a line of 1131's repeated numbers made room under the cap.
- `/code-review high --fix` applied seven fixes in two commits: `-z` on the
  gitignore filter, a fresh state directory per GUI probe run,
  `fileURLToPath` in every script, four `proto.html` repairs, a 400 from
  `serve.mjs` on a bad escape, one hoisted minimum, and two `.gitignore`
  lines. It declined three: the D5 contradiction (the maintainer's call,
  now reopened), cleanups on code paths the logs measured, and an import
  order outside the lint scope.

*Measured:*
- Paints per zoom, main/ticks/resid, 59 498 points at devicePixelRatio 2:
  2/2/1 with the echo, 1/1/1 without, in Chrome for Testing 148 and
  Firefox 155. Firefox's wheel zoom painted in 5.3 ms against 3.5 ms, at
  load averages 67-84.
- Headless Chromium took 24-32 ms from input to frame on every event,
  including an empty mouse-down.
- three.js 0.186.1, the viewer's imports bundled: 557 KB, 138 KB gzip.
  3Dmol.js 2.5.5: 538 KB, 156 KB gzip.
- Fast suite on this branch with main `6641c8cf` merged: 6038 passed, 141
  skipped, in 2:22, `[dev]` venv, macOS arm64, no other suite running. An
  earlier merge of main measured 6034 and 141, and the four more passes
  came with main. This session added no test. The full selection did not
  run, since nothing here can move a measured number.

*Gotchas:*
- `npm --prefix X init` writes `package.json` into the working directory,
  not into X.
- The worktree guard refuses a shell variable in a `git`, `node` or `gzip`
  argument. Write a scratchpad script and run it by path.
- Firefox runs headless through `puppeteer-core` over WebDriver BiDi. Its
  first launch in a batch sometimes exits with code 0, so rerun.
- The demo server on port 8810 still runs the `serve.mjs` from before the
  review. Restart it to pick up the 400 answer.

*Next:*
1. D5 was put back to the maintainer and answered the same day: the pilot
   measures both marker paths and picks (§ Decided).
2. Task 2: measure D4 and D8 on the real payloads, which settles the route
   the pilot builds on.
3. The vendoring task, which also adds Dependabot.

### 2026-09-25 — session state saved for a `/clear`

  Session state saved for a `/clear`, before
  `/wp-handover`. The WP is filed and not started. PR #461 carries it with
  the spike and a demo someone can click through. Nothing in the package
  changed. The maintainer has not yet answered the first task (confirm the
  migration on § Staying on plotly's numbers, and D1-D8), nor whether to
  file a three.js WP for the 3D viewer now.
  *Done:* the WP and ROADMAP row, `1461-uplot-spike/` (drivers, logs,
  screenshots), the adversarial review and the re-measurement it forced, a
  forward reference in 1317's Inherited, and the demo (`serve.mjs`, `?demo`
  toolbar). Branch `wp1461-uplot` in worktree
  `.claude/worktrees/wp1461-uplot`, pushed.
  *In flight:* a demo server on `http://127.0.0.1:8810/`, started from this
  session. Restart it with `node docs/wp/1461-uplot-spike/serve.mjs 8810`.
  The spike's `node_modules` is a symlink into a session scratchpad that will
  be cleaned, so run `npm install` in the spike directory first (README).
  *Not yet done from the handover checklist:* the Stop hook asked for
  `/wp-handover 1461` on 2026-09-24. It still owes a `/code-review high
  --fix` over the spike's `.mjs`/`.py`, the `session_start.py` check, and
  a PR body rewritten from this log.
  *Gotchas:*
  - `Plotly.Plots.resize` resolves after a 100 ms `setTimeout`, so time work
    with `TaskDuration`, never a promise.
  - Load averages ran from 7 to 29 on this shared machine. GUI boot moved
    from 842 to 2295 ms between runs, so quote ranges and side-by-side
    ratios.
  - The worktree guard refuses heredoc scripts and shell loops; write a
    scratchpad script and run it by path.
  - The drivers rewrite `shots/`, and the spike's `.gitignore` keeps only
    the six cited screenshots.
  - WP numbers: 1460 was already held on WP-1454's branch, so check remote
    branches as well as main before taking one.
  *Next:*
  1. The maintainer's answers go into § Decisions, and the first task gets
     ticked.
  2. If a three.js WP is wanted, file it.
  3. Run `/wp-handover 1461`.
  4. Task 2: measure D4 and D8 on the real payloads, which sets the route
     the pilot builds on.
### 2026-09-24 — created

  The maintainer asked whether a lighter library
  would make the plots snappier, and asked for one backend for all plotting
  if it held up. The spike measured three libraries, today's GUI and a uPlot
  rebuild of every feature. An adversarial review then found the first
  draft had timed plotly's resize by its promise, a 100 ms timer included,
  and had missed behaviours and a shared-x-axis constraint. Everything was
  re-measured as main-thread work, and this file now quotes those numbers.
  Next: the maintainer confirms the migration and D1-D8 on them.

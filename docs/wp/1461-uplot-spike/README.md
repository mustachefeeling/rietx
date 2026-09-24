# WP-1461 spike

The pages and drivers that produced the numbers in
[WP-1461](../1461-every-browser-chart-draws-with-uplot.md). Nothing here ships
or runs in the suite. The logs in `results/` are the runs the WP quotes.

## Files

| File | What it is |
|---|---|
| `bench.html` | Plotly, uPlot and ECharts drawing the same five series. |
| `bench_td.mjs` | The library head-to-head as main-thread work: load, first draw, data update, zoom, resize. |
| `driver.mjs` | The first head-to-head, timed by promise latency. Kept because `results/gpu3.txt` is its output; its plotly resize includes a 100 ms timer. |
| `proto.html` | The GUI's pattern plot rebuilt on uPlot: three linked panes, every gesture, the exports. `?all` draws every marker. |
| `proto2.html` | The Series trajectory, the compare overlay and an in-situ 2D map. |
| `proto_driver.mjs` | Drives both prototype pages with real mouse and wheel input and times each gesture. |
| `gui_td.mjs` | Today's GUI as main-thread work: boot frames, hover, resize, and the full-resolution window with its parse and grid union. |
| `gui_probe.mjs`, `driver3.mjs` | Earlier GUI probes (latency of boot, zoom and resize), SVG export, and the standalone-page comparison. |
| `make_exports.py`, `make_uplot_export.mjs` | Build today's `write_html` page and its uPlot equivalent from one set of arrays. |

## Method

Each gesture is real input sent through playwright. The cost of one event is
the change in CDP `Performance.getMetrics` `TaskDuration`, minus the page's
idle rate over the same wall time, divided by the number of events. Frame
intervals come from a `requestAnimationFrame` loop. Long frames come from the
`long-animation-frame` performance entry, which fires above 50 ms.

Two traps met here. `Plotly.Plots.resize` resolves after a 100 ms
`setTimeout`, so timing its promise measures the timer, and only
`TaskDuration` measures its work. And the machine was shared with other
sessions: load averages ran from 7 to 29, so compare runs taken side by side
and quote ranges.

## Running it

From this directory (measured with node 20.11.1):

```sh
npm install
../../../.venv/bin/python -c "from plotly.offline import get_plotlyjs; open('plotly.min.js','w').write(get_plotlyjs())"
node bench_td.mjs                          # library head-to-head, work
node proto_driver.mjs                      # 22 003 and 200 000 points, then SVG, trajectory, compare, map
node proto_driver.mjs n=59498              # one size only
ALLMARKERS=1 node proto_driver.mjs n=59498 # every marker drawn
node proto_driver.mjs dpr2                 # 22 003 points at devicePixelRatio 2
node gui_td.mjs 0                          # today's GUI, run index 0; add `boot` for an uninstrumented boot
../../../.venv/bin/python make_exports.py .   # needs arrays.json, which proto_driver.mjs writes
node make_uplot_export.mjs
node driver3.mjs                           # starts `rietx gui` on port 8799 and fits the NAC example
```

The drivers expect Chrome for Testing from playwright's chromium build 1223
in the playwright cache (`~/Library/Caches/ms-playwright/chromium-1223`). Set
`RIETX` to use a `rietx` other than the repository's `.venv`. The GUI drivers
bind port 8799.

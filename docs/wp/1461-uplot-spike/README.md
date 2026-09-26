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
| `zoom_probe.mjs` | Counts and times the paints behind one drag-zoom and one wheel zoom, in Chrome for Testing or the installed Firefox (finding 12, finding 13). `echo` puts back the pane link that painted twice. |
| `gui_td.mjs` | Today's GUI as main-thread work: boot frames, hover, resize, and the full-resolution window with its parse and grid union. |
| `gui_probe.mjs`, `driver3.mjs` | Earlier GUI probes (latency of boot, zoom and resize), SVG export, and the standalone-page comparison. |
| `payloads.py` | Task 2's server half: builds today's and the proposed curve payloads for the NAC example, two compare standards and the QPA series, times building and serialising them, and counts every pattern's channels. Writes `payloads/`. |
| `payload_probe.mjs` | Task 2's browser half: fetch, decode, parse and grid union of each payload, in Chrome for Testing or Firefox. |
| `transport.py` | The real `/api/result/window` route timed with curl, beside the GUI's own `_send` serving the same bytes, so the server's work and the transfer separate. |
| `make_exports.py`, `make_uplot_export.mjs` | Build today's `write_html` page and its uPlot equivalent from one set of arrays. |
| `pilot.mjs` | The pilot's acceptance probe: the real GUI, plotly against the chart module on one server, every gesture as CDP work per event and as the time inside every callback the page registered. Chromium, Firefox and WebKit. |
| `pilot_matrix.mjs`, `pilot_summary.mjs` | The pilot's runs, appended to `results/pilot_<engine>_<dataset>_dpr<n>.txt`, and those logs read back as ranges. Logs before the D5 decision name three renderers: `uplot` drew every marker, `thin` thinned per pixel column. After it, `chart` is the thinned module. Task 14's acceptance run is `results/acceptance_*.txt`, written with `PILOT_PREFIX=acceptance`. |
| `hover_trace.mjs` | One chromium trace of a hover sweep per renderer, summed by trace event, with the rectangles repainted (the WP's finding 18). |
| `make_lab6.py` | The `lab6_capillary` standard as a GUI project, for the 132 992-channel runs. |
| `serve.mjs`, `index.html` | The demos for a person: `node serve.mjs [port]`, then <http://127.0.0.1:8810/>. `?demo` gives the prototype pages a toolbar that times each action, and the pattern page prints each frame's repaints. |

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
node serve.mjs 8810 & node zoom_probe.mjs firefox 2 [echo]   # or chrome; the probe loads the page from serve.mjs
(cd ../../.. && PYTHONPATH=. .venv/bin/python docs/wp/1461-uplot-spike/payloads.py sizes nac compare compare:lab6_capillary series)
node serve.mjs 8811 & node payload_probe.mjs chrome     # or firefox
../../../.venv/bin/python transport.py                  # needs payloads/ from payloads.py
(cd ../../.. && .venv/bin/python docs/wp/1461-uplot-spike/make_lab6.py <dir>)   # the 132 992-channel project
node pilot.mjs chromium nac 1 0 plotly chart            # one call: engine, dataset or .rex path, dpr, run, renderers
node pilot_matrix.mjs <dir>/lab6_capillary.rex [filter] # the whole matrix, or the rows naming `filter`
node pilot_summary.mjs                                  # the logs as ranges
RIETX_PLOTLY=<a rietx built at 58f7dbce> PILOT_PREFIX=acceptance node pilot_matrix.mjs none nac
PILOT_PREFIX=acceptance node pilot_summary.mjs          # task 14's run, as ranges
```

The drivers expect Chrome for Testing from playwright's chromium build 1223
in the playwright cache (`~/Library/Caches/ms-playwright/chromium-1223`). Set
`RIETX` to use a `rietx` other than the repository's `.venv`. The GUI drivers
bind port 8799. `zoom_probe.mjs` drives Firefox from
`/Applications/Firefox.app` through `puppeteer-core`, over WebDriver BiDi.
`pilot.mjs` binds 8790-8798 and drives playwright's own Firefox 1543 and WebKit
2359 builds, which `node node_modules/playwright-core/cli.js install firefox
webkit` fetches. In WebKit it supplies the mouse movement playwright leaves at
zero (the WP's finding 15). With `RIETX_PLOTLY` set, the plotly renderer comes
from that command on the next port up, a second server with its own fit: the
final tree has no plotly renderer, so task 14 paired it with a build of
`58f7dbce`, whose `src` ran under this repository's `.venv` through `PYTHONPATH`.

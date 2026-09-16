# WP-1427 — what a poll costs

Milestone: unscheduled · Status: 🔄 2026-09-17 — claimed by @yue-here
Depends on: 1430 (the page as files); 1426 soft (both rewrite `drawRun`)

## Goal

One idle poll of the `rietx watch` page, where nothing changed, costs the
server and the browser a measured and stated amount on a root of two hundred
runs, and a stage redraw produces no long task. Every optimisation lands with
the number it moved, and anything that did not move a number is not landed.

## Context

The maintainer asked for further performance work after the 2026-09-16 demo,
without naming what was slow. Nothing has been measured, so this WP starts
with the instrument and ends with the numbers. The candidates below are read
off the code. One of them has a plausible number behind it; the rest are
listed so the measurement can dismiss them.

### The poll cycle today

Every 1.2 s while the tab is visible (`schedule`), `refresh` fetches
`api/runs`, patches the list, and for the selected run fetches the snapshot
when its `snapshot_mtime` moved and the events tail from its offset.

Server, per `api/runs` request:

- `_RunIndex.runs()` re-walks the root when its 1.0 s TTL has lapsed
  (`INDEX_TTL_SECONDS`), so with one open tab the walk runs about once a
  second. `read_run` opens two files per run (`meta.json`, `status.json`,
  asserted by `tests/test_runs.py`) and stats the log. Two hundred runs is
  four hundred JSON reads and parses a second while nothing changes. That is
  the one candidate with a number: small files, so likely tens of
  milliseconds a second, and the measurement says whether that matters.
- `_row` calls `liveness_of` (a pid check and a lock probe) and stats the
  snapshot file, per run, per request, outside the TTL cache.
- The payload is every row every time. There is no `ETag`, so the browser
  parses and patches an identical list once a second.

Browser, per poll:

- A snapshot redraw is one JSON of `n_drawn` points in four arrays plus the
  tick rows, then `plotly.react` over four scattergl traces. WP-1423 saw
  5859 of 7251 points drawn on the demo; 11-BM NAC would be its 22 003 points
  through the same decimation.
- The console tail renders every event as a `<div>` through
  `insertAdjacentHTML`, then trims to `MAX_LINES` (2000) one
  `firstElementChild.remove()` at a time. A fit emitting an `eval` per
  residual evaluation gives the console more lines per poll than a reader
  can read, and each line carries the full `series_*` stamp (WP-1423's
  handover named this).

### The instrument

- Server: a `Server-Timing` response header per route (`walk`, `rows`,
  `serialize` in ms). It is the documented mechanism, it shows up in the
  browser's network panel, and a test can read it off the response.
- Browser: `performance.mark/measure` around fetch, parse, patch, react and
  the console append, read by the browser harness; a
  `PerformanceObserver({type: 'longtask'})` for anything over 50 ms.
- Three roots: the demo job (16 runs), a synthetic root of 200 recorded runs
  (the batch shape WP-1403's retention rule was written for), and one run
  drawing NAC.

### Candidates, to be kept or dismissed by the numbers

1. A per-run read cache in `_RunIndex` keyed on the `mtime` of `meta.json`
   and `status.json`, so an unchanged run is a stat and not a parse.
2. An `ETag` on `api/runs` (a digest of the payload) honoured with
   `If-None-Match`, so an idle poll is a 304 with no body and no client
   work. `http.server` has no helper for it; it is two header lines.
3. `Content-Encoding: gzip` on the snapshot when the client accepts it
   (stdlib `gzip`), measured against the parse cost it adds.
4. A console that caps lines per poll and says `+N more`, and drops the
   per-line `series_*` keys the strip already shows.
5. Server-sent events in place of polling. `ThreadingHTTPServer` can hold a
   `text/event-stream` per tab. It removes the round trip and the empty polls
   but not the walk: the stdlib has no file watcher, so the server would poll
   the disk instead of the browser polling the server. Take it only if the
   measurement puts the cost in the HTTP round trip and not in the walk, and
   say so either way.

### Inherited

- **2026-09-16, from [1429](1429-one-palette-and-one-theme-for-three-pages.md):
  the poll's payload changed under this WP, in both directions.** Measured on
  this machine, `[dev]`, darwin/arm64.
  - The `page` block shrank **262 B → 49 B** per poll. The dark palette left it
    — the page reads its colours off its own root element now — and the theme
    *choice* took its place. So 1430's "299 B of every poll" is stale and the
    row cost it was compared against (735 B each) is unchanged.
  - Every `/api/runs` now reads `state_dir/settings.json`, because the theme is
    the one thing on the page a person changes while it is open. **16.8 µs**
    with the file present, 4.6 µs without, against a 1.2 s poll. It is
    uncached on purpose; if this WP's instrument says the read is worth
    caching, the cache has to expire faster than a person notices a theme
    switch not arriving.
  - A new route, `/tokens.css`, is **43.6 µs** and 4972 B, rendered per request
    and fetched once per page load rather than per poll. It carries
    `Cache-Control: no-store` from `_send`, like every other route this server
    answers, so a reload pays for it again.
  - A theme change clears `shell.mtime`, which forces one extra snapshot fetch
    and redraw on the poll that carries it. Once per switch, so it is not a
    steady-state cost, but a benchmark that flips the theme will see it. It is
    gated on `shell.kind === 'json'`: a legacy run's picture is an iframe, and
    re-pointing it would refetch the 4.51-6.03 MB page WP-1402 measured.

- **2026-09-16, from [1429](1429-one-palette-and-one-theme-for-three-pages.md):
  a defect on the page this WP measures, found in its browser and not fixed
  here.** The GUI's reflection tick rows carry no explicit colour, so they take
  plotly's colorway — which is indexed by **position in the trace array**, and
  the GUI's background trace is both conditional on there being a background
  *and* toggleable by the reader (`Plot.svelte`, `shows(hidden, "bkg")`). So
  hiding the background moves every phase's tick colour one step along the
  colorway, on a click. Measured on the watcher, which briefly had the same
  shape: `phase 0` went `#d62728` → `#9467bd`, and `#d62728` is **0.043** from
  `--plot-calc` in OKLab on the light theme, against the 0.13 floor
  `tests/test_gui_palette.py` holds every other plot colour to. The watcher
  keeps explicit colours because of it (`PALETTES["dark"]`, with a guard in
  `test_watch_browser.py`); the GUI still has it. The fix needs a **categorical
  palette** the GUI does not own, which is the maintainer's question rather than
  either WP's — it is filed here because this is the WP with the instrument.


- **2026-09-16, from [1424](1424-a-row-that-names-its-run.md): a row does more
  per poll than it did when this WP was written.**
  - `fillRow` now writes three `title` attributes and a `<time>` element's
    `datetime` and `title` per row, on top of the six cells. Every one goes
    through `setAttr`/`setText`, which compare before assigning, so a poll that
    changes nothing still writes nothing — but the *comparison* count per row
    is up, and `runTitle` builds a four-line string per row per poll.
  - If this WP measures a per-row cost, measure it against a list of 40, and
    note that `runTitle` is a pure function of the run object: it is the
    obvious thing to memoise by `run_id` if the number matters. Nothing
    suggests it does yet; nothing has measured it either.
  - `drawSnapshot` gained one plotly annotation in the layout. It is
    paper-anchored with `automargin` off, so it costs no relayout.

- **2026-09-16, from [1426](1426-still-under-resize-and-across-a-stage.md):
  1426 landed first, so this WP is the one that rebases.** Both were declared
  to rewrite `drawRun` and they did not collide, but three shapes moved:
  - `buildShell` is gone, split into **`buildPicture`** (the shell, the plotly
    purge, the `full` class) and **`resetTail`** (the console and the tail
    offset). `drawRun` calls `resetTail` on a *run* change and `buildPicture`
    on a run-or-kind change. A poll-cost change that skips work must keep those
    two triggers apart: merging them back is the defect 1426 removed.
  - `patchList` opens by taking a scroll anchor and closes by applying it. A
    patch made cheaper must still run both ends, or the list shifts under the
    reader again.
  - `rangesOf` in `watch-core.mjs` cuts by count rather than by quantile now.
    It sorts the residual on every draw, which is the one O(n log n) step in
    the draw path and a candidate if the poll's cost is in the page rather than
    on the wire. 4000 points is the decimated ceiling.

- **2026-09-16, from [1430](1430-the-page-is-a-file.md): the page is files, and
  three of its names are not the ones 1430's plan said.** `watch.py` is the
  package `watch/`, and the page is `watch/static/`: `index.html`, `watch.css`,
  `watch.mjs` (the document) and `watch-core.mjs` (everything that touches no
  DOM). `rietx.watch` imports unchanged. What to carry:
  - **The DOM half is `.mjs`, not `.js`.** `node --check` reads a `.js` as
    CommonJS, where the `import` of `watch-core.mjs` is a syntax error. A
    browser cares about `type="module"` and the content type, never the
    extension.
  - **Node cases live in `tests/watch_core.test.mjs`**, not beside the module:
    hatchling ships everything under `src/rietx`. They are invoked from
    `tests/test_watch_app.py::test_the_pure_half_of_the_page_is_unit_tested`
    (15 cases today), which passes `--test-reporter=tap` because node picks its
    reporter by whether stdout is a terminal.
  - **`@SUFFIX@`, `@DIST@` and `@HUE@` are gone.** A file cannot carry a token,
    so the three ride on `/api/runs` as `payload.page.{suffix,dist,palette}`,
    read at boot into the module-level `HUE` and `DIST`. That is 299 B of every
    poll, against rows of 735 B each.
  - **A new file under `static/` needs a row in `watch.STATIC_FILES`** and
    nothing else — the route, the content type and the `.gitignore` guard all
    read that dict. `*.html` in `.gitignore` swallowed `index.html` on the way
    in, the sixth committed file that one rule has taken.
  - The poll payload grew a constant: `page` is 299 B of every `/api/runs`,
    measured against 735 B a row on a 41-run tree (30 431 B in all). It is one
    key and one function (`watch._page_constants`), so moving it to a
    boot-only route is a small edit if the measurement says to.
  - `tests/test_watch_browser.py` took no diff and stays the bar: if it
    moves, the page moved.

## Non-goals

- The snapshot's decimation and the fit's cost to write it (WP-1413, and the
  open decision it left the maintainer).
- Layout shift and flashing (WP-1426). A slow redraw that shifts is this
  WP's; a wrong layout is 1426's.
- A second server or a websocket library. The page stays on the stdlib.
- The GUI's own live panel, which reads an in-process ring.
- Micro-optimisations without a number. `patchList`'s per-row
  `querySelector` is quadratic and irrelevant at 200 rows; it is fixed only if
  the measure says otherwise.

## Tasks

- [ ] `Server-Timing` on the three routes and `performance.measure` marks on
      the page, read by the browser harness; the before numbers on the three
      roots in the handover
- [ ] The read cache in `_RunIndex`, with `test_runs.py`'s two-files budget
      restated as two files per *changed* run, if the walk is where the time
      is
- [ ] `ETag`/`If-None-Match` on `api/runs`; the page skips patching on a 304
- [ ] The console's per-poll cap and the stamp keys dropped from the line
- [ ] gzip on the snapshot, kept or dropped on its own measurement
- [ ] The SSE question answered from the numbers, in the handover, with no
      code unless it wins
- [ ] Tests: the 304 path, the cache invalidating on a status write, and a
      budget on the idle poll as a runaway guard (root CLAUDE.md § Testing:
      a budget is never a timer)
- [ ] Skill: none. The page is a human's.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_watch_app.py tests/test_watch_browser.py tests/test_runs.py
.venv/bin/python -m ruff check src tests examples
```

The handover states, as ranges over three runs each, the idle poll's server
time and main-thread time on the 200-run root before and after, and the long
task count over a NAC stage redraw. Quote wall clock as a range, never a
figure. The browser-side numbers need the cached chromium and are this
machine's; the `Server-Timing` numbers come from a python test and run in CI.

## References

- MDN, `Server-Timing`; MDN, `ETag` and `If-None-Match`; web.dev, Long Tasks
  API.
- WP-1402 (what the page cost before it was numbers), WP-1413 (what the
  snapshot costs the fit), WP-1423 (the poll cycle as it stands).

## Handover log

- **2026-09-16** — created, from the maintainer's asks after the demo job;
  revised the same day: the padded candidates moved to the non-goals, and the
  one with a number is said to be the one.

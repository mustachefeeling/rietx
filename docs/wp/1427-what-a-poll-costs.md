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

### What the five WPs before this one left on the poll path

All measured or read off the tree on 2026-09-17, in this worktree, `[dev]`
plus playwright, darwin/arm64. The mailbox they arrived in is consumed here.

**The payload's constant block is 137 B, not the 49 B its note claimed.**
WP-1429 wrote that number when the dark palette left `_page_constants` and the
theme choice took its place. The reflection tick colours went back in the same
WP's review pass (`d5529c6c`), so the block carries `suffix`, `dist`, `theme`
and `ticks` today. WP-1430's "299 B of every poll" is stale in the other
direction. Either way it is one part in 220 of a 41-run answer, whose rows are
735 B each, so a boot-only route for it buys nothing this WP would report.

**Every `/api/runs` reads `state_dir/settings.json`.** The theme is the one
thing on the page a person changes while it is open, so the read is uncached on
purpose: 16.8 µs with the file present, 4.6 µs without, against a 1.2 s poll
(WP-1429). A cache here has to expire faster than a person notices a theme
switch not arriving.

**`/tokens.css` is 43.6 µs and 4972 B, once per page load.** It carries
`no-store` from `_send`, as every route here does, so a reload pays again. It
is off the poll path.

**A theme change clears `shell.mtime`.** That forces one extra snapshot fetch
and redraw on the poll carrying it, once per switch. A benchmark that flips the
theme sees it; a steady-state one does not. It is gated on
`shell.kind === 'json'`, because re-pointing a legacy run's iframe would
refetch the 4.51-6.03 MB page WP-1402 measured.

**A row does more per poll than this WP's context said.** `fillRow` writes
three `title` attributes and a `<time>`'s `datetime` and `title` on top of the
six cells (WP-1424). Every one goes through `setAttr`/`setText`, which compare
before assigning, so an unchanged poll still writes nothing to the DOM. The
comparison count is up, and `runTitle` builds a four-line string per row per
poll. It is a pure function of the run object, so memoising it by `run_id` is
the obvious move if the number says so. `drawSnapshot` also gained one
paper-anchored annotation, which takes no relayout.

**Three shapes moved under WP-1426, and two of them are traps for this WP.**
`buildShell` split into `buildPicture` (the shell, the plotly purge, the `full`
class) and `resetTail` (the console and the tail offset); `drawRun` calls
`resetTail` on a run change and `buildPicture` on a run-or-kind change, and
merging the two triggers back together is the defect 1426 removed. `patchList`
opens by taking a scroll anchor and closes by applying it, and a cheaper patch
must still run both ends. `rangesOf` in `watch-core.mjs` cuts by count rather
than by quantile, sorting the residual on every draw: the one O(n log n) step
in the draw path, over a decimated ceiling of 4000 points.

**The page is four files under `watch/static/`** (WP-1430): `index.html`,
`watch.css`, `watch.mjs` and `watch-core.mjs`, the last being everything that
touches no DOM. A new file needs a row in `watch.STATIC_FILES` and nothing
else. The DOM half is `.mjs` because `node --check` reads a `.js` as CommonJS.
Node cases live in `tests/watch_core.test.mjs` and are invoked from
`tests/test_watch_app.py::test_the_pure_half_of_the_page_is_unit_tested`.
`tests/test_watch_browser.py` is the bar: if it moves, the page moved.

### Filed here, for the maintainer, and not this WP's to fix

**The GUI's reflection tick rows take plotly's colorway, which is indexed by
position in the trace array.** The GUI's background trace is conditional on
there being a background and toggleable by the reader (`Plot.svelte`,
`shows(hidden, "bkg")`), so hiding the background moves every phase's tick
colour one step along the colorway, on a click. Measured on the watcher, which
briefly had the same shape: `phase 0` went `#d62728` → `#9467bd`, and `#d62728`
sits **0.043** from `--plot-calc` in OKLab on the light theme, against the 0.13
floor `tests/test_gui_palette.py` holds every other plot colour to. The watcher
keeps explicit colours because of it (`PALETTES["dark"]`, guarded in
`test_watch_browser.py`). The fix needs a categorical palette the GUI does not
own. It is filed here because this is the WP with the instrument (WP-1429).


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

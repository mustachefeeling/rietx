# WP-1427 — what a poll costs

Milestone: unscheduled · Status: ⬜
Depends on: — (1423 soft: the poll cycle this measures)

## Goal

One idle poll of the `rietx watch` page, where nothing changed, costs the
server and the browser a measured and stated amount on a root of two hundred
runs, and a stage redraw produces no long task. Every optimisation lands with
the number it moved.

## Context

The maintainer asked for further performance work after the 2026-09-16 demo.
Nothing has been measured yet, so this WP starts with the instrument and ends
with the numbers. The candidates below are read off the code and ranked by
what the measurement says.

### The poll cycle today

Every 1.2 s while the tab is visible (`schedule`), `refresh` fetches
`api/runs`, patches the list, and for the selected run fetches the snapshot
when its `snapshot_mtime` moved and the events tail from its offset.

Server, per `api/runs` request (`watch.py`):

- `_RunIndex.runs()` re-walks the root when its 1.0 s TTL has lapsed
  (`INDEX_TTL_SECONDS`), so with one open tab the walk runs about once a
  second. `read_run` opens two files per run (`meta.json`, `status.json`,
  asserted by `tests/test_runs.py`) and stats the log. Two hundred runs is
  four hundred JSON parses a second while nothing changes.
- `_row` calls `liveness_of` (a pid check and a lock probe) and stats the
  snapshot file, per run, per request, outside the TTL cache.
- The payload is every row every time. There is no `ETag`, so the browser
  parses and patches an identical list once a second.

Browser, per poll:

- `patchList` does `tbody.querySelector('tr[data-id=…]')` inside a loop over
  the runs, O(N²) on the list.
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

### Candidates, to be ranked by the numbers

1. A per-run read cache in `_RunIndex` keyed on the `mtime` of `meta.json`
   and `status.json`, so an unchanged run is a stat and not a parse.
2. An `ETag` on `api/runs` (a digest of the payload) honoured with
   `If-None-Match`, so an idle poll is a 304 with no body and no client
   work. `http.server` has no helper for it; it is two header lines.
3. `patchList` on a `Map` from id to row.
4. `Content-Encoding: gzip` on the snapshot when the client accepts it
   (stdlib `gzip`; decimal arrays compress several-fold), measured against
   the parse cost it adds.
5. A console that renders the lines it shows, or caps lines per poll and says
   `+N more`, and drops the per-line `series_*` keys the strip already shows.
6. Server-sent events in place of polling. `ThreadingHTTPServer` can hold a
   `text/event-stream` per tab. It removes the round trip and the empty polls
   but not the walk: the stdlib has no file watcher, so the server would poll
   the disk instead of the browser polling the server. Take it only if the
   measurement puts the cost in the HTTP round trip and not in the walk, and
   say so either way.

## Non-goals

- The snapshot's decimation and the fit's cost to write it (WP-1413, and the
  open decision it left the maintainer).
- Layout shift and flashing (WP-1426). A slow redraw that shifts is this
  WP's; a wrong layout is 1426's.
- A second server or a websocket library. The page stays on the stdlib.
- The GUI's own live panel, which reads an in-process ring.

## Tasks

- [ ] `Server-Timing` on the three routes and `performance.measure` marks on
      the page, read by the browser harness; the before numbers on the three
      roots in the handover
- [ ] The read cache in `_RunIndex`, with `test_runs.py`'s two-files budget
      restated as two files per *changed* run
- [ ] `ETag`/`If-None-Match` on `api/runs`; the page skips patching on a 304
- [ ] `patchList` on a Map; the console's per-poll cap and the stamp keys
      dropped from the line
- [ ] gzip on the snapshot, kept or dropped on its own measurement
- [ ] The SSE question answered from the numbers, in the handover, with no
      code unless it wins
- [ ] Tests: the 304 path, the cache invalidating on a status write, and a
      budget on the idle poll as a runaway guard (root CLAUDE.md § Testing,
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
figure.

## References

- MDN, `Server-Timing`; MDN, `ETag` and `If-None-Match`; web.dev, Long Tasks
  API.
- WP-1402 (what the page cost before it was numbers), WP-1413 (what the
  snapshot costs the fit), WP-1423 (the poll cycle as it stands).

## Handover log

- **2026-09-16** — created, from the maintainer's asks after the demo job,
  unrolled with 1424–1426, 1428 and 1429.

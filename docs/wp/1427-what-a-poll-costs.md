# WP-1427 — what a poll costs

Milestone: unscheduled · Status: ✅ 2026-09-17 — the poll is measured; the walk is 1.7× and the console no longer freezes the page
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

### What the five WPs before this one left on the poll path (consumed 2026-09-17)

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

## Findings

Every number below is this machine's, darwin/arm64, `[dev]` plus playwright,
chromium 1223, at the page's own 1.2 s cadence. Two benchmarks of the same
thing on this machine differ by more than most of these changes do, so every
comparison is **interleaved in one process** rather than run before and after.

**The poll's cost was the walk, and the walk was two JSON parses per run.**
Server-Timing on `/api/runs`, 200 synthetic runs, ten polls: `walk`
27.8-49.2 ms, `rows` 2.1-3.3, `serialize` 0.8-1.8, payload 230 kB. Inside the
walk, on the same root: `read_run` 10.4-12.0 ms of a 12.5-25.1 ms `discover`,
and of that `read_run`, 6.4-6.7 ms is the two `read_text` calls and 0.7 ms more
is the two `model_validate_json`. `liveness_of` is 0.14-0.25 ms for all 200,
and `as_dict` 0.39-0.53. The candidates about `liveness_of` and the payload's
`page` block were reading the wrong end of it.

**The browser was never the problem.** An idle poll on that root spent
0.50-0.90 ms parsing and 1.80-3.20 ms patching, and drew nothing. A NAC stage
redraw — 8331 of 59 498 points, 1486 ticks, a 384 kB snapshot — is
`snap:net` 0.8-1.3, `snap:parse` 0.9-1.0 and `snap:react` 9.3-15.0 ms, with
**no long task** in six stage boundaries. `rangesOf`'s sort over 4000 points,
which WP-1426 flagged as the one O(n log n) step, is inside that 9.3-15.0.

**The one thing that froze the page was the console, and it was not a rate.**
A real NAC fit emits 56 events a second (68 a poll) and a cheap silicon fit on
1000 points emits 391 (469 a poll). Neither hurts. What hurts is **opening** a
run whose log is already long, because `resetTail` asks from offset 0: at
60 000 events the page parsed all of them and built 60 000 `<div>`s to keep
2000, for `tail:render` 997 ms, `tail:net` 101 ms and **three long tasks of
997, 974 and 168 ms**. A cheap fit writes that log in about two and a half
minutes.

### What was landed, and what it moved

| | before | after |
|---|---|---|
| `walk`, 200 runs | 27.8-49.2 ms (median 34.7) | 15.6-23.1 (median 20.7) |
| `walk`, 500 runs (`MAX_RUNS`) | 47.4-70.1 (median 59.7) | 24.1-41.7 (median 35.7) |
| `runs:parse` + `runs:patch`, idle | 2.3-4.1 ms | absent (304) |
| payload, idle poll | 230 kB | 0 |
| `tail:render`, opening 40 000 events | 997 ms | 31.0 |
| long tasks, opening 40 000 events | 3 | 0 |
| `tail:render`, 5000 events a poll | 84.3-140.7 (median 138.5) | 28.9-37.3 (median 32.5) |
| long tasks, 5000 events a poll | 8 | 0 |

### What was dismissed, and by what

**gzip on the snapshot loses by 27×.** Loopback here moves 3365 MB/s, so the
384 kB NAC snapshot crosses it in 0.11 ms. Compressing it costs 1.92-2.03 ms
at level 1 to save 0.07 ms of transfer, 15.7-16.1 ms at level 6, 54.3-56.2 at
level 9 — and the client then pays 17.0-17.2 ms to decompress. There is no
setting at which this is not a loss.

**Server-sent events would move the walk, not remove it.** The measurement puts
the poll's time in the walk and not in the round trip: `runs:net` is unmoved at
27.95 / 28.35 / 27.60 ms median across three interleaved arms with and without
the conditional request, while the body went from 222 kB to nothing. The
stdlib has no file watcher, so an SSE server would poll the disk on the same
cadence, in a thread, for as long as a tab is held — and it would lose the
thing the poll gets for free, that `document.hidden` stops it and a minimised
tab costs the fit nothing.

**The per-line `series_*` stamp stays.** Dropping it is a real number and a
small one: on a fit emitting 5000 events a poll, `tail:render` 31.3-39.3
(median 35.0) becomes 22.7-32.7 (median 27.5), and the pane's HTML 413 866
chars becomes 271 866. Neither arm makes a long task. Against that, `attach`
records **once per job** and a series hands each pattern a fresh
`_SeriesStream` around one stream (`runs.recorder_of`), so a sixty-pattern
series is one log and the stamp is the only thing on a line saying which
pattern wrote it. 7.5 ms of median render is not worth that.

**`patchList`'s quadratic `querySelector` was not touched**, as the non-goals
said. At 200 rows the whole patch is 1.8-3.2 ms, and on an idle poll it now
does not run at all.

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

- [x] `Server-Timing` on the three routes and `performance.measure` marks on
      the page, read by the browser harness; the before numbers on the three
      roots in the handover
- [x] The read cache in `_RunIndex`, with `test_runs.py`'s two-files budget
      restated as two files per *changed* run, if the walk is where the time
      is
- [x] `ETag`/`If-None-Match` on `api/runs`; the page skips patching on a 304
- [x] The console's per-poll cap. The **stamp keys stay**, measured: dropping
      them is 7.5 ms of a 35 ms median render on the worst case that exists,
      which no longer makes a long task, and they are the only thing in a
      series log saying which pattern a line belongs to (§ Findings)
- [x] gzip on the snapshot: **dropped**, losing by 27× at its cheapest setting
- [x] The SSE question answered from the numbers, in the handover, with no
      code unless it wins — it did not win
- [x] Tests: the 304 path, the cache invalidating on a status write, and a
      budget on the idle poll as a runaway guard (root CLAUDE.md § Testing:
      a budget is never a timer)
- [x] Skill: none. The page is a human's.

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

- **2026-09-17** — **the poll is measured, and the one thing that froze the
  page was not on anyone's candidate list.** The WP guessed that the walk's two
  JSON parses per run were the cost and that the rest were padding. The walk
  half was right and is now 1.7× faster. The half nobody had is the console:
  clicking a job that had been running a couple of minutes delivered its whole
  log on one poll, and the page spent a second building sixty thousand `<div>`s
  to keep two thousand of them. That is the change a reader will feel. The rest
  is a page that now does nothing at all on a poll where nothing changed.

  **The instrument first**, because none of the above was knowable without it.
  `Server-Timing` on every route this page uses (`walk`, `rows`, `serialize`,
  `tail`, `read`), which a browser shows in its network panel and a python test
  reads off the response with no profiler. `performance.measure` spans on the
  page (`runs:`/`snap:`/`tail:` × net/parse/work), cleared every 400 spans so a
  tab left open overnight does not grow a timeline. The long-task observer is
  the *harness's* and not the page's: an observer nobody reads is telemetry on
  somebody's overnight tab. § Findings has every before number, on three roots
  — 16 runs, 200 runs, and one drawing 11-BM NAC at 8331 of 59 498 points.

  **Three changes landed, each with the number it moved** (§ Findings has the
  table). A caller-owned read cache in `read_run`/`discover`, keyed on inode,
  size and nanosecond mtime of the three files a row reflects plus its two
  snapshot flags: the walk goes 34.7 → 20.7 ms median on 200 runs and
  59.7 → 35.7 at the `MAX_RUNS` ceiling of 500. An `ETag` on `/api/runs`, which
  takes an idle poll's parse and patch to absent and its payload to nothing.
  And the console cap, which is the one that mattered: `tail:render` 997 → 31.0
  ms on a 40 000-event open, and three long tasks to none.

  **The `ETag` needed a field removed before it could ever match.** Every row
  carried `liveness.heartbeat_age`, which is `now - heartbeat`, so every idle
  answer differed from the last one and no digest of the body could agree with
  itself. Nothing read it — not this page, not the GUI — and the heartbeat it
  derives from is in the row's `status` already. This is WP-1076's rule from
  the other side: a declared name with no *reader* costs nothing visible until
  something downstream depends on the payload being stable.

  **Two candidates were dismissed by measurement and one by judgement.** gzip
  on the snapshot loses by 27× at its cheapest setting, this machine's loopback
  moving 3365 MB/s. SSE would move the walk into a thread rather than remove
  it, the stdlib having no file watcher, and would lose the property that a
  hidden tab stops polling. The per-line `series_*` stamp would buy 7.5 ms of a
  35 ms median render, on a case that no longer makes a long task, at the cost
  of the only thing in a one-log series that says which pattern a line is from.

  **The review pass earned its place, on the change I was most pleased with.**
  `/code-review high --fix` found that the `ETag` had broken the selected-row
  highlight: the `selected` class was set only in `fillRow`, which is reached
  only from `patchList`, which the 304 branch skips. A click changes nothing on
  disk, so the poll *after* a click is exactly the poll that 304s — on a
  directory of finished runs the highlight would have stayed on the row the
  reader had just left, for ever. It has an authority of its own now
  (`markSelected`), called from both branches, and a browser test that was made
  to fail against the old script first. Two more were taken: the tag was
  committed before the payload was applied, so a truncated body would have
  pinned the page to a list it never drew; and the manual's route table still
  described the events route as `?offset=` alone. One finding was raised and
  **declined on inspection, correctly**: the 304 carries `Content-Length: 0`,
  which RFC 7230 allows only when it equals the 200 body's length. This server
  is HTTP/1.0 (`http.server`'s default, which `watch/` does not override), so
  the connection closes after every response and no client in the path can
  misread it.

  **Counts**, this worktree, `[dev]` **plus playwright** (installed for this
  session; without it every browser test self-skips), darwin/arm64. Acceptance
  115 → 136 passed, +21, which is exactly the tests added: 7 in
  `test_runs.py`, 10 in `test_watch_app.py`, 4 in `test_watch_browser.py` (3
  mine, 1 the review's). Fast selection 5235 passed, 132 skipped in 142 s,
  measured before the review's test landed. `ruff` clean over src, tests and
  examples. Wall clock is quoted as a range throughout because two runs of one
  benchmark on this machine move further than most of these changes did.

  **The mailbox was consumed and one number in it had already gone stale.**
  WP-1429's note said the poll's constant block was 49 B; it is 137 B, the
  reflection tick colours having gone back into `_page_constants` in that WP's
  own review pass (`d5529c6c`). Either way it is one part in 220 of a 200-run
  answer, so 1430's "move it to a boot-only route" buys nothing worth
  reporting. The rest of the mailbox was true and is folded into Context.

  **Next.** 1428 is the remaining rung of the watcher track. Two things this WP
  found and did not fix are the maintainer's: the GUI's tick rows still take
  plotly's colorway and change colour when the background is toggled (inherited
  from 1429, and it needs a categorical palette the GUI does not own); and a
  reader opening a run with a very long log now walks forward through it in
  4 MB chunks, so they see events from several minutes ago for a few seconds
  before reaching the tail. The freeze is gone either way. Seeking to the end
  of the log on a cold open would fix the staleness and would change what
  `offset` means, which is a route decision rather than a performance one.


- **2026-09-16** — created, from the maintainer's asks after the demo job;
  revised the same day: the padded candidates moved to the non-goals, and the
  one with a number is said to be the one.

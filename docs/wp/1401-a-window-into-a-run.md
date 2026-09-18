# WP-1401 — a window into a run: find the runs that already exist

Milestone: v1.5 · Status: ✅ 2026-09-14 — `rietx watch` lists every run
under a directory, reading only what today's code already writes; the baseline
says the event stream costs 1-3 % and the per-stage picture up to 49 %
Depends on: — (first rung of the live-watcher track; 1402, 1403 and 1405 all
build on the reader this lands)

## Goal

`rietx watch`, with no argument, scans the working directory and lists every
refinement run under it — the live ones and the finished ones together — and a
click opens one. It reads only directories that today's code already writes, so
nothing in `refine.py` is touched and the reader is exercised against a format a
writer really produces. The same session measures what `events=` costs today,
because that number decides whether WP-1403's automatic recording is affordable
at all.

## Context

When an agent drives rietx, the human has no window into the work. The telemetry
is good and it is unreachable, for three separate reasons.

**It is off unless the caller asks.** WP-1322 measured the consequence: three
independent subagents, each given a benchmarking task, each of which found and
read the packaged skill in full by a different route, all wrote `history=False`
— five occurrences. No event log existed afterwards, and reconstructing timing
from their own transcripts recovered 2.7–16.6 % coverage and nothing at all from
inside a solve. That is WP-1403's problem, not this one's, but it is why the
track exists.

**The human must know the directory.** `rietx watch <dir>` takes a path the agent
chose, in a process the human is not in. One directory holds one run, and
`LiveSession.__init__` truncates `events.jsonl`, so nothing is archived. This is
the gap this WP closes.

**Watching is expensive.** `LiveSession.write_snapshot` builds a self-contained
page with the whole of plotly inlined — 4.3 MB empty and 6.3 MB on a NAC-sized
pattern, measured 2026-09-13 under plotly 7.0.0 — on the fit's own thread, after
every stage. That is WP-1402's problem, and WP-1402 re-measures it rather than
carrying this figure.

### The decision this track rests on

The watcher **grows `rietx watch`; it is not a mode inside `rietx gui`**. Three
reasons, recorded here because the alternative will look attractive again:

- The GUI's live view is an in-process ring buffer fed by its own callback
  (`gui/session.py`, `EVENT_RING = 4096`, `_push`), so it has **no path to a run
  in another process** — which is exactly what an agent's run is. A file-tailing
  reader is new code wherever it lives; in `watch` it is the whole app rather
  than a second data path beside the first.
- The GUI is one project per session and every verb writes — that is why
  `--scratch` exists, and why `Project.open` appends a head annotation before any
  verb runs. `_require_idle()` raises 409 in 24 places. A multi-run read-only
  browser contradicts both.
- **Read-only is stronger when the app has no verbs than when a mode hides
  them.** A user cannot click what is not there. The watcher gets exactly one
  verb, cancel, in WP-1405, and nothing else.

Human-in-the-loop is not foreclosed; it is placed. Discovery, run metadata,
liveness and tailing go in `runs.py`, a plain library module with no HTTP, which
`watch.py` is transport over — the split `gui/server.py` already declares for
itself ("this module is transport only") — and which `gui/session.py` imports
when it attaches to a foreign run. Each run row carries "open in the GUI", so the
read-only/interactive boundary is a **process boundary, not a mode**.

### What exists, and where

- `src/rietx/history/events.py` (279 lines) — `EventStream(path=, callback=)`,
  `emit(kind, **data)` writing one JSON line and flushing. `EventKind` is a
  **closed** Literal of seven; `data` is an **open** dict, so a reader uses
  `.get` and never unpacks a fixed shape, and a new field bumps nothing.
  `read_events(path)` validates a log back through `EventRecord`.
- `src/rietx/viz/live.py` (66 lines) — `LiveSession(EventStream)`: truncates
  `events.jsonl` on construction, writes `fit.html` + `status.json` per stage.
- `src/rietx/watch.py` (151 lines) — `_INDEX` inline HTML, `_Handler`,
  `serve(directory, *, port=8899, open_browser=False, block=True)`,
  `main(argv)` with a positional `directory`. The page refetches the **whole**
  `events.jsonl` every second and re-renders the last 400 lines.
- `src/rietx/gui/session.py` — `GuiSession.run` opens
  `EventStream(path=p.live_dir / "events.jsonl", callback=self._push)` and
  **appends**. So a GUI project's `live/events.jsonl` is a real, populated log
  today: it is this WP's primary fixture, and the reason the reader can be built
  against a live format rather than an invented one.
- `src/rietx/project.py` — `LIVE_DIR = "live"`, `Project.live_dir` ("where an
  event stream belongs, so `rietx watch` can find it").
- `src/rietx/cli.py` (388 lines) — hand-rolled dispatch on `argv[0]`, lazy
  imports, `watch` at line 80.

### The rule this reader carries across a process boundary

`gui/session.py:27-41` states it for one process: a fit that raises emits **no**
`fit_end`, `EventKind` is closed, so the run's **state is not an event** — it
travels beside the stream and is never written to the log.

Across a process boundary the same rule needs a channel the OS maintains, because
a dead writer writes nothing:

- **Liveness is a held lock, not a pid.** The writer holds `run.lock` flock'd for
  its life; a reader takes it non-blocking and infers from the failure. Immune to
  pid reuse, needs no heartbeat contract, and the kernel releases it however the
  writer dies, `kill -9` included. `os.kill(pid, 0)` is the fallback where flock
  is unavailable, and the heartbeat age is **reported but never decides** — an
  alive process is evidence, a clock is not.
- A lock that is free while the status says running reads **abandoned**, which is
  a third answer and not a rounding of the other two.
- A different host reads **unknown**. A claim we cannot check is not a claim.

Nothing in this WP writes `run.lock` or `status.json`; WP-1403 does. The reader
ships knowing about them, treats every one as optional, and resolves a directory
that has neither as a **legacy** run — which is what every directory in the tree
today is, and what keeps them all visible forever.

### The reader constructs nothing

No `Project.open` — it appends a head annotation, which is why there is no
read-only way to open a project — no `Refinement`, no `read_pattern`. Everything
a reader needs, a writer captured. This is a hard rule in the module docstring,
not a style preference: a viewer that constructs a project mutates what it is
looking at.

### The measurement this WP owes the next one

WP-1403 proposes to record **every** fit. Whether that is affordable is decided
by a number, and the baseline half of that number needs none of this track's
code, because `events=` already exists. Two facts verified in the tree
(2026-09-13):

- `optimize/least_squares.py:1153` calls `_free_values(table, theta)` on every
  residual evaluation when `events is not None`. That is a **second full
  `table.decode`** (`least_squares.py:822`), and it happens **before** the sink is
  consulted, so no cleverness in a sink can avoid it. Then `emit` does
  `json.dumps` + write + `flush`: a syscall pair per residual evaluation, on the
  fit thread.
- `refine.py:1766-1785` computes a real `stage_end.rwp` from one `background`
  pass plus one `bragg_component` pass, **only when events were asked for**. That
  is one forward evaluation per *stage*, against a stage's hundreds.

So the cost is dominated by the eval stream and it is CPU as much as syscalls.
Measure it now, on the cases the next WPs will reuse.

## Non-goals

- **No automatic telemetry.** No `telemetry=` keyword, no recorder, no writing.
  WP-1403, and it is gated by this WP's measurement.
- **No `snapshot.json`, and `fit.html` keeps being written.** WP-1402. The page
  this WP lands shows a run's events and status; the plot stays the existing
  `fit.html` iframe where one exists.
- **No cancel.** No verb of any kind. WP-1405.
- **No manual or skill changes.** WP-1406.
- **No GUI change.** `gui/session.py` importing `runs.py` is the seam this WP
  leaves open, not work it does.

## Tasks

- [x] `runs.py`: the run-directory model and the run-id scheme. `RunMeta` /
      `RunStatus` as pydantic `Base` models **for reading only** (the
      `EventRecord` split: no pydantic on any write path). `RunStatus.state` has
      **no default** — a defaulted `"running"` is exactly WP-1076's field whose
      empty state reads as an answer — and a status missing it resolves to
      `unknown`. Every field's writer named in the docstring, since this WP
      writes none of them.
- [x] `runs.discover(root)`: depth- and count-bounded walk; prunes `.git`,
      `node_modules`, `.venv`, `__pycache__`, `_build`, `dist`; never follows
      symlinks; descends a `*.rex` only as far as its `live/`; reads **exactly
      two files per run**, asserted by counting opens, because a web page polls
      this. A directory with `events.jsonl` and no `meta.json` is a **legacy**
      run, synthesized from the file's mtime — which is every directory in the
      tree today.
- [x] `runs.liveness_of`: the ordered rule above — terminal state wins, then
      foreign host, then the flock probe, then `os.kill(pid, 0)`, with the
      heartbeat age reported and never deciding. A Windows shim for the lock
      probe, and a documented fall-through when neither mechanism is available.
- [x] `runs.tail_events`: byte-offset cursor, not the whole-file refetch the
      page does today. Carries a trailing fragment **unparsed**; resets on inode
      change or truncation and says so, so a client clears its pane rather than
      renumbering silently; counts a bad line instead of raising. Load-bearing
      rather than defensive from WP-1403 on, when writes become buffered.
- [x] `python -m rietx.runs [DIR]` printing the discovered table — how a human
      checks the walk without a browser.
- [x] `watch.py`: no-argument mode scanning the cwd, the run list page, and the
      JSON routes it needs (`/api/runs`, `/api/run/<id>`,
      `/api/run/<id>/events?offset=`). A directory argument that **is** a run is
      served as one and opens straight onto it, so `rietx watch ./live-dir` from
      `using/cli.md` keeps working unchanged. Polling stops when the page is
      hidden. The page says **"scanned \<root\>"**: an empty list must not read as
      "no runs exist".
- [x] The baseline measurement: `telemetry off` against today's plain
      `events=<path>` and against `events=LiveSession(dir)`, on `nac`, `cpd-2`
      and `trigger`, three runs each, one sitting. Numbers into the handover as a
      **range**, with venv and platform named. State plainly whether WP-1403's
      premise survives.
- [x] Tests: `tests/test_runs.py` (no fit at all — fixture directories) and
      `tests/test_watch_app.py`. Cases: a held lock against a released one, a
      foreign host, a status with no state, a torn last line, invalid JSON mid
      file, an empty directory, the depth cap, a symlink loop, the open-count
      assertion. Plus a real `<project>/live/` written by a GUI run.
- [x] Skill: **none**, and the reason. Nothing here changes what an agent driving
      rietx should do; WP-1406 carries the whole skill change for this track,
      once there is something an agent's behaviour depends on.

## Acceptance

`rietx watch` in a tree holding a GUI project lists that project's run, and
opening it shows the events the GUI wrote. Checked by looking, not only asserted.

```sh
.venv/bin/python -m pytest tests/test_runs.py tests/test_watch_app.py
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
.venv/bin/python -m rietx.runs .
```

The baseline measurement is reported in the handover log, never asserted in a
test: a wall-clock budget in a test is a runaway guard, never a timer.

## References

- WP-1006 — run control: streaming, progress, cancellation. The origin of
  `events=`, and of the rule that the run state is not an event.
- WP-1008 — the GUI's live machinery and `/api/result/window`.
- WP-1113 — what an `eval` event carries and why (`values`, `accepted`,
  `step_norm`), which is the trajectory a sampled log would cost.
- WP-1322 — the three subagents that all disabled telemetry; the measured
  2.7–16.6 % transcript coverage. Its Task 1, the terminal-shaped post-hoc
  aggregator, stays its own; its Task 2 is discharged by WP-1403.
- WP-1076 — a declared name is a claim; a field whose empty state reads as an
  answer. Why `RunStatus.state` has no default.

## Handover log

### 2026-09-14 — the window exists, and the stream turns out to be cheap

A person can now see the refinements an agent is running. `rietx watch` with no
argument scans the working directory and lists every run beneath it, live ones
and finished ones together, and opening one shows its plot and its event log.
Nothing about how a fit is launched had to change. The reader only reads
directories today's code already writes, so it was built against a format a
writer really produces. The measurement this rung owed the rest of the track
came back split, and the split is the useful part: the event stream costs 1-3 %
of a fit's wall clock, so recording every fit is affordable on anything, while
the per-stage picture costs up to 49 %. WP-1403 is therefore not gated, and
WP-1402 became the thing that has to land first.

*Done.* All nine tasks, six commits. `runs.py` is the reader and writes no file
at all. `discover` walks bounded in depth and in count, never following a
symlink, descending a `.rex` only as far as its `live/` and a run directory not
at all. `liveness_of` answers by the first rule that fires: a terminal state is
the writer's own last word, a foreign host is a claim we cannot check, a held
flock is the channel the kernel maintains however the writer dies, and a free
lock under a running status is `abandoned`. That last one is a third answer
rather than a rounding of the other two. `tail_events` reads from a byte offset,
holds a torn last line back unparsed, resets on truncation or a new inode, and
counts a bad line instead of raising. `watch.py` grew a no-argument mode, a run
list page and four JSON routes, and its old single-directory behaviour is
unchanged. The watcher still has no verbs: a `.rex` row carries
`rietx gui <name>` as text a person copies, so the read-only boundary stays a
process boundary.

*Measured.* The baseline, three configurations against three cases, three
repeats each, two sittings. `[dev]` venv (numba 0.67.0, no jax, no torch),
macOS arm64 (Darwin 25.5.0), python 3.12.12, rietx 1.4.0, run alone on an idle
machine. Wall clock as a range over both sittings.

| case | off | `events=<path>` | | `events=LiveSession(dir)` | |
|---|---|---|---|---|---|
| `nac` | 0.34-0.35 s | 0.35-0.36 s | 1.01-1.03x | 0.51-0.63 s | 1.47-1.49x |
| `cpd-2` | 2.30-2.39 s | 2.33-2.35 s | 1.01-1.02x | 2.53-2.56 s | 1.10x |
| `trigger` | 5.77-5.84 s | 5.83-5.85 s | 1.01x | 6.02-6.15 s | 1.04-1.05x |

Every configuration returned a bit-identical Rwp on every case, so none of this
is buying speed by changing the answer. The whole `events=` path costs 0.1-0.3 ms
a residual evaluation. Logs ran 0.03 MB over 59 events (`nac`), 0.30 MB over 358
(`cpd-2`) and 0.26 MB over 258 (`trigger`), so roughly 1 kB an event, dominated
by each `eval`'s `values` array. The resident `fit.html` was 6.36 / 5.27 /
4.99 MB; the run rewrote it once per stage, so the cumulative write is that
times the stage count. WP-1402 re-measures rather than carrying these.

Fast selection 4728 passed, 132 skipped, 2:45, same venv and platform, machine
checked idle first and measured alone. This session added 64 tests (40 in
`test_runs.py`, 23 in `test_watch_app.py`, 1 in `test_gui_server.py`), all
passes, no new skip. `origin/main` had not moved since the branch was cut, so
the branch tip is the merged tree and this count is that tree's. The full suite
was not run and is not owed: nothing here touches the forward model, the solver
or any physics, so no measured number can move.

*Review.* `/code-review high --fix` raised twelve findings, eleven applied and
one declined. Two were defects rather than cleanups. The detail view built its
plot iframe once and never reloaded it, so a **live** run's plot froze at
whatever stage it was opened on — the page this replaced polled
`Last-Modified`, that was dropped in the rewrite, and no test caught it because
every fixture here is a finished run. And the lock probe took an exclusive
lock, so two readers saw *each other* rather than the writer, which two browser
tabs are enough to reach. Both are fixed and the plot reload was re-checked by
looking. The declined one is in WP-1403's `### Inherited`: a single event line
longer than `tail_events`' 4 MiB bound stalls the tail permanently, and
skipping forward would emit a torn line instead.

*Gotchas.*

- The WP's own citations drift. `refine.py:1758-1771` was already 1766-1785 on
  arrival and is fixed in place; the 2026-09-13 entry's `write_snapshot` line is
  now 1991-1993 and was left alone, a dated entry being a record. Both
  behavioural findings did hold: `_free_values` really is a second full
  `table.decode` inside the `events is not None` guard and ahead of `emit`, and
  `stage_end.rwp` really is one background plus one bragg pass a stage.
- `schemas.common.Base` is `extra="forbid"`, which would refuse a `status.json`
  the moment any writer adds a field. The reader schemas here allow extra
  instead, for the reason `EventRecord.data` is an open dict. Anything else
  reading a run directory should inherit that choice.
- `test_portability`'s encoding guard fires on `open(path, "r+")` against the
  lock file. Binary mode is the fix rather than an encoding, because the file's
  bytes are never read.
- `discover` opens exactly two files a run and `liveness_of` opens at most one
  more. They are deliberately separate calls, so a caller that only wants the
  list pays two. A future route that needs both pays three, and the open-count
  test only pins `discover`.
- A ratio on a short fit is a small number wearing a large one. `nac`'s 1.47x is
  0.16 s, because the snapshot is a per-stage cost and `nac` is 0.35 s long.
- **Every fixture in both new suites is a finished run, and that is a blind
  spot rather than a convenience.** It is why the frozen plot survived a green
  suite. Anything about a run that *changes* while being watched — the plot
  reloading, a run appearing mid-scan, a status flipping to terminal — has no
  test here and has to be checked by looking.
- **A vocabulary and its `Literal` are two declarations, and widening the field
  orphans one.** Typing `RunStatus.state` as `str` left `runs.RunState` reachable
  by nothing but the docstring saying why it was unused, while `rietx.gui`
  already exports a different `RunState` meaning `idle`/`running`/`cancelling`.
  It is deleted; `RUN_STATES` is the vocabulary. Worth a look whenever a review
  widens a type.
- A non-finite Rwp reaches the page as the **string** `"NaN"`, because
  `ser_json_inf_nan="strings"` is on `Base` and a diverged fit writes one. Any
  new number the page formats needs the `isFinite` guard `num()` carries, or
  `toFixed` throws and the whole table stops rendering.
- Which part of the 1-3 % is the decode and which is the syscall pair is not
  separable without a configuration this WP did not run. WP-1404 owns that split
  and should not be told the answer is known.

*Next.* WP-1402, then WP-1403. That order is what the measurement bought: 1403
is affordable the moment the picture stops being written on the fit's thread,
and expensive until then. WP-1405 is independent of both and can go whenever.

- **2026-09-13** — created, and with it the whole live-watcher track
  (1401–1406). What this round settles is that a human will be able to see, and
  stop, a refinement an agent is running, without that costing the agent
  anything it has to remember to do. The design question that took the longest
  was where it lives, and the answer is that it grows `rietx watch` rather than
  becoming a mode in the GUI: the GUI's live view is an in-process ring that
  physically cannot see a run in another process, and read-only is a stronger
  promise when an app has no verbs than when a mode hides them. Nothing is
  implemented; six WP files and the ROADMAP rows are the whole deliverable.

  *Done.* Six self-contained WP files, one new Unscheduled section, and the
  track named in Current focus. The ROADMAP cap moved 648 → 672 with its ledger
  line, landing at 670; the section's paragraph was cut to the rungs' order and
  the one surface decision, because each file carries its reasoning in full.

  *Measured.* Nothing physical — this round measured nothing and must not be
  quoted as if it had. Fast selection 4487 passed, 127 skipped, `[dev]` venv (no
  jax, no torch), macOS arm64. Docs-only with no test added or removed, so that
  count is unchanged by construction rather than by comparison. The full suite
  was not run and is not owed: nothing here can move a measured number.

  *Gotchas for the successor.* Six cited `file:line` references in the drafts
  were wrong and are fixed (a review pass after the first sweep found two more:
  the `write_snapshot` call site is `refine.py:1985-1987`, and `cli.md`'s
  sentence about what watch serves is at 121, not the heading at 115); nothing
  tests them, so check any one you are about to rely on. The track's headline
  number was wrong the same way: "3.5 MB a stage" came from WP-1029's
  measurement of a whole `.rex` directory, not of `fit.html`. Measured here
  instead — plotly 7.0.0's bundle is 4.29 MB, an empty self-contained page
  4.30 MB, a NAC-sized one 6.3 MB — and WP-1402 re-measures rather than
  carrying it. Two facts were verified by hand and are load-bearing:
  `_free_values` is a second full `table.decode` on **every** residual
  evaluation and it runs *before* the sink is consulted, so no sink-side thrift
  avoids it; and `_abandon_on_cancel` short-circuits on `cancel is None` and
  says so in its docstring, which means WP-1405 attaching a token universally
  ends a guarantee the code currently makes. `origin/main` was ahead of the main
  checkout when this opened — WP-1344 already existed — so 14xx was taken as the
  next free block on the user's instruction; per
  `test_index_section_mirrors_the_wp_milestone_line` the number never carries
  the milestone, the `Milestone:` line does.

  *Next.* Start 1401 itself: `runs.py` plus the no-argument `rietx watch` over
  the directories today's code already writes. Its last task — the baseline
  measurement of what `events=` costs now — is the one that matters most,
  because it decides whether 1403's automatic recording ships on by default at
  all, and the three failure paths for that are already written down in 1404 so
  they cannot be quietly avoided. The track is slated for v1.5, behind v1.4's
  free-standing peaks; 1401 is the only rung that delivers a usable window on
  its own, so it is also the safe place to stop if the track is reprioritised.

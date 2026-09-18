# WP-1428 — open in the GUI, without touching the fit

Milestone: v1.5 · Status: ✅ 2026-09-17 — launch, in the run list; the track's last rung
Depends on: 1405 (the one verb and its gate), 1401 (the decision this revisits); 1430 soft

## Goal

A reader of `rietx watch` can open, in the GUI, a copy of the project a
running fit is writing, as it stood at the click, and the fit does not
notice. The copy is frozen: it shows the model, the parameters and the
history up to that moment and never the next stage. The GUI opens a scratch
copy, never the live project, and the watcher's gate for it is the one the
stop button already has.

## Context

The maintainer asked: can we have an "open in GUI" feature, in a safe way that
does not disrupt the ongoing refinement. Today the strip shows a command a
human can copy, `rietx gui <project>`, built by `_row` in `watch.py` for a run
that sits in a project's `live/`. WP-1401 § the decision kept it a string:
launching the GUI is a process boundary and the watcher performs no verbs.
WP-1405 then gave it one verb, stop, behind a host allowlist and a
`--read-only` flag. This WP asks whether a second verb is worth its cost,
and what "safe" has to mean first.

### What the feature can and cannot be

The GUI's live panel reads an in-process ring. It cannot follow a fit in
another process; `rietx watch` exists because of that (ROADMAP § A window into
a run). So "open in GUI" cannot mean a live view of the running fit. It means
a snapshot of the project at the click, opened for what the GUI is good at
and the watcher is not: reading the parameter table, the report, the 3D
structure, and branching a strategy from the current head in the copy. The
copy is frozen; the watcher stays the live view. The strip's button and the
manual say so in those words, or a reader clicks expecting the fit to follow
them.

### Why the live project is never safe to open

- There is no read-only way to open a project. `Project.open` appends a head
  annotation before any verb runs, and every verb writes into the directory
  (root CLAUDE.md § Project; `gui/server.py:scratch_copy`'s docstring).
- The fit appends to the same `history.jsonl` at every stage. Two appenders on
  one log is the interleaving WP-1403 separated the *run* directories to
  avoid, and the history log has no such separation.
- Two sessions would hold two heads. The fit advances the head with every
  stage; a GUI that opened earlier holds the older one, and its stale-revision
  409 (`gui/CLAUDE.md`) guards against its own in-process run, not a foreign
  writer. What a verb from the stale side does to the tree has never been
  defined.

So the only object the GUI may open is a copy. `rietx gui --scratch` makes
one with `shutil.copytree`, byte for byte, into a temp directory that nothing
removes, and its header says the source is not written to.

### Where the copy is fragile

`history/store.py:read_records` raises `malformed history record` on any line
it cannot parse. A history node is about 10 kB (root CLAUDE.md § Conventions).
Python's buffered writer and the kernel may each split an append of that size
into more than one write, so a copy taken while the fit is mid-append can
carry a torn last line and fail to open.

**Measured 2026-09-17** (macOS 25.5.0, M-series, `[dev]` venv; the writer is a
subprocess in every run, because `rietx watch` is not the process running the
fit and a thread would put the GIL in the window).

**The window opens at one threshold, and it is the write buffer.**
`append_record` writes through a `TextIOWrapper` whose buffer is
`io.DEFAULT_BUFFER_SIZE` = 8192 B. A record that fits lands in one `write(2)`
and is never visible half-written; one that does not is flushed in pieces. So
the mode decides whether the window exists at all:

| mode | 8 records, smallest-largest | over the buffer |
| --- | --- | --- |
| `rietveld` | 142-8068 B | 0 |
| `lebail` | 142-8573 B | 1 |
| `pawley` | 142-8963 B | 3 |

Polling the raw bytes against a hammer appending the largest record, 6 rounds
each: **34 of 258 107 samples (0.013 %) carried a partial last line on the
Pawley seed, and 0 of 260 107 on the rietveld one.** At 562 appends/s that is
about 0.24 µs of torn state per append — the interval between the buffer's
flush at 8192 B and the record's own.

**A copy does reproduce one.** Written deliberately rather than raced for, a
torn tail survives `scratch_copy` byte for byte, and both `read_records` and
`Project.open` refuse it by name: `history.jsonl:8: malformed history record`.
Copying again, the append having landed, opens.

**No copy caught one by racing**: 0 of 14 088 `copytree` copies under the
hammer, 0 of 2 767 in a shorter run, 0 of 200 under a real fit. The hammer's
duty cycle predicts ~1.8 in 14 088, so this is an upper bound rather than a
floor.

**What a reader would actually meet.** 20 fresh Pawley projects, a staged
`mccusker_default` fit in another process, 10 copies each at random moments:
**6.0 history appends per fit at 3.7/s, a 48 kB log, `scratch_copy` at 1.1 ms,
0 failures in 200 copies.** Scaling the window by that append rate puts a click
at roughly **10⁻⁶** of landing on a torn tail — and at zero for a `rietveld`
project, whose records never cross the buffer.

**So: retry the copy once.** It costs 1.1 ms on an event that does not
otherwise happen, and the second copy is measured to open. Teaching
`read_records` to tolerate a partial final line would change a load-bearing
"bad lines raise" rule for a one-in-a-million event, and the measurement does
not justify it.

### The two forms, and the decision

**Copy the command.** The strip's `gui_command` grows `--scratch`, gets a
copy-to-clipboard button, and the reader pastes it in a terminal. No new verb,
no process spawned by the watcher, nothing for `--read-only` to refuse. It is
what exists today with one flag and one button.

**Launch it.** `POST api/run/<id>/gui` spawns `rietx gui --scratch <project>
--no-open --machine` and returns the boot line's `url`; the page opens it in a
new tab. Behind the same host allowlist as stop, refused under `--read-only`,
refused for a run with no project. The spawned GUI outlives the watcher, as a
scratch copy already outlives its GUI. The `--machine` boot line (url, port,
project, pid, scratch_of) exists for exactly this caller. **The flag is
`--machine`; this file said `--json` until 2026-09-17 and no such flag exists.**

**Measured 2026-09-17, the spawn works as described.** Three GUIs launched in
turn on one project: **0.58-0.89 s from `Popen` to the boot line**, ports
8731 then 63972 then 63973 — `build_server` already falls back to an ephemeral
port when one is busy, so a second window needs no port argument from the
caller — and the source project's `history.jsonl` was byte-identical after all
three.

The launch form is what the ask means by a feature. It costs a second verb in
an app whose strength ROADMAP § A window into a run states as having none,
and a process the watcher spawns but does not own.

### The decision, 2026-09-17

**Launch, with the button in the run list.** Taken by the maintainer on the
measurements above, which settle the safety precondition: the copy's failure
mode is about one click in a million and is repaired by copying again, so
nothing here needed the `read_records` change the WP had held in reserve.

The button is in the **run list** rather than the status strip. The strip's
flexible slot is the first thing it drops, at 990 px of run panel against 882
at 1400x900 with the list open (WP-1424), so the GUI command the page already
had was invisible on an ordinary window. A real affordance in that slot would
have inherited exactly that.

### What the measurement turned up

Not a torn tail. **`gui_command` was `None` for every run a project had
actually recorded**, so there was nothing on the page for a button to key on.

Three places open-coded which project a run belongs to and two implemented
different halves of it. A recorder writes `<name>.rex/live/<run id>`; a caller
pointing `LiveSession` at a live directory writes `<name>.rex/live` itself.
`runs._label_for` matched the second, `RunRecorder._default_label` the first,
and the watcher's `_row` the second — and every fixture in
`tests/test_watch_app.py` built the second, so the row builder's own test
passed on a layout no recorder produces.

`runs.project_of` is now the one authority and knows both. This is the class
WP-1076 named from the other side: a claim with no writer fails no test, and
here the writer and the test agreed with each other while both disagreed with
the recorder.

### What the column cost

8ch, out of the run column, which is the flexible one. The list's drag floor is
declared (`SEAMS.list.minCh`) and goes 63ch → 71ch; the default list width goes
72ch → 80ch so the run names keep the room they had. **The 72ch default was
already one of 1425's open maintainer questions**, and this moves it without
settling it.

### What a run without a project gets

A bare `fit()` records under `.rietx/runs/` and has no project to copy. Its
row and strip show nothing for this feature. Building a project from a run's
snapshot is not a thing; the snapshot is a picture.

### What the page already gives this WP

Folded out of `### Inherited` on 2026-09-17. Three entries were there on
arrival and all three still held; two more arrived from 1427 mid-session, while
this WP was being built, and are folded in below.

- **2026-09-17, from [1427](1427-what-a-poll-costs.md): the watcher's routes
  gained two things a GUI-launching WP should know, and left one open
  question.** All measured on this machine, `[dev]` plus playwright,
  darwin/arm64.
  - **`/api/runs` now answers 304 to a conditional request**, so a client that
    polls it must send `If-None-Match` and read the status. A 304 carries the
    tag and no body. `liveness.heartbeat_age` left the row to make that
    possible: it was `now - heartbeat`, nothing read it, and the heartbeat it
    came from is in the row's `status`.
  - **The events route takes a `limit`** and reports what it dropped in
    `skipped`. The page passes its own `MAX_LINES`, so the pane's length is the
    one authority for how many lines are worth sending. Absent or junk is no
    cap, which is what the route did before.
  - **Open, and the maintainer's**: a reader opening a run with a very long log
    walks forward through it in 4 MB chunks, so they see events from several
    minutes ago for a few seconds before reaching the tail. The freeze is gone
    either way (997 ms → 31 ms on a 40 000-event open). Seeking to the end on a
    cold open would fix the staleness and would change what `offset` means,
    which is a route decision rather than a performance one.

- **2026-09-17, from [1427](1427-what-a-poll-costs.md), by way of
  [1429](1429-one-palette-and-one-theme-for-three-pages.md): a GUI defect
  neither WP fixed, filed here because this is the WP that opens a GUI.** The
  GUI's reflection tick rows carry no explicit colour, so they take plotly's
  colorway — which is indexed by **position in the trace array**, and the GUI's
  background trace is both conditional on there being a background *and*
  toggleable by the reader (`Plot.svelte`, `shows(hidden, "bkg")`). Hiding the
  background therefore moves every phase's tick colour one step along the
  colorway, on a click. Measured on the watcher, which briefly had the same
  shape: `phase 0` went `#d62728` → `#9467bd`, and `#d62728` sits **0.043**
  from `--plot-calc` in OKLab on the light theme, against the 0.13 floor
  `tests/test_gui_palette.py` holds every other plot colour to. The watcher
  keeps explicit colours because of it (`PALETTES["dark"]`, guarded in
  `test_watch_browser.py`). The fix needs a **categorical palette the GUI does
  not own**, which is the maintainer's question rather than any WP's.

- **The affordance has no home that survives an ordinary window** (1424). The
  strip's `#s-where` holds `run.gui_command` alone, and it is the **first slot
  the strip drops**: `@container (max-width: 990px)` sets `display:none` on it
  and on `#s-free`, and at 1400x900 with the list open the run panel is 882 px.
  So a reader on an ordinary window sees no GUI affordance at all today. 1424's
  own words: a real affordance should not live in that slot. `#stop` is
  grid-column 10 and is never dropped.
- **The page is files, and the names are `watch/static/`** (1430): `index.html`,
  `watch.css`, `watch.mjs` (the document) and `watch-core.mjs` (no DOM). A new
  file under `static/` needs a row in `watch.STATIC_FILES` and nothing else.
  Node cases live in `tests/watch_core.test.mjs`, invoked from
  `tests/test_watch_app.py::test_the_pure_half_of_the_page_is_unit_tested`.
  `_row`'s `gui_command` is in `watch/__init__.py`.
- **A GUI opened from the watcher already matches the page that opened it**
  (1429): both read the theme from `state_dir/settings.json` and draw from the
  same tokens. `theme.state_dir` is the single resolver, so a launch that
  passed a different `--state-dir` would split the two windows' themes and
  nothing else. This WP passes none.

## Non-goals

- Opening the live project.
- A GUI that follows a foreign run. The GUI's live panel is in-process, and
  the watcher is the live view.
- Removing scratch copies. `scratch_copy` says why nothing does.
- Two appenders on one `history.jsonl` when a caller runs `Project.fit` with
  the GUI already open on that project. Named here; not this WP's.

## Tasks

- [x] Measure the torn-tail rate of `scratch_copy` under a fit (200 copies at
      random moments), and record it here with the choice it forces
- [x] The decision: **launch**, taken by the maintainer 2026-09-17 on the
      measurements above, with the button **in the run list** rather than the
      status strip
- [x] `gui_command` carries `--scratch` — and it is now non-null for the runs
      a project actually records, which it was not (see § What the measurement
      turned up)
- [x] The route, gated as stop is (`_origin_ok`, `--read-only`, project runs
      only), spawning with `--machine` and returning the url; the page opens it
      in a new tab and the strip carries the url
- [x] Tests: the gate (read-only 403, unknown id 404, no project 409,
      cross-origin 403, GET 404), a real spawn whose boot line names the copy
      and leaves the source `history.jsonl` byte-identical, and three browser
      tests — the button's presence per row, its absence under `--read-only`,
      and a click that selects the run and reports the url
- [x] Manual: `cli.md` § `rietx watch` gains § Opening a copy in the GUI, and
      § `rietx gui` names the watcher as `--machine`'s caller
- [x] Skill: none. An agent driving rietx does not open a GUI.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_watch_app.py tests/test_watch_browser.py tests/test_gui_server.py
.venv/bin/python -m ruff check src tests examples
```

A project under a running fit is opened from the page; the fit's next stage
lands in the original `history.jsonl` and the GUI's header names the scratch
copy. The handover states the torn-tail rate.

## References

- WP-1401 § the decision, WP-1405 (the gate), WP-1403 (why run directories are
  separate and the history log is not).
- `gui/server.py:scratch_copy`, `main` (`--scratch`, `--json`).

## Handover log

### 2026-09-17 — the watcher opens a copy, and the row that could never offer one

A person watching a refinement can now open that project in the GUI from the
run list, in one click, without the running fit noticing. What opens is a copy
taken at the click. It carries the model, the parameters and the history as
they stood at that moment and never gains the next stage, so it is where to
read the parameter table, the report and the structure while the fit carries on
writing the original. It has to be a copy because a project cannot be opened
read-only at all: opening one appends to its history before anybody has clicked
anything, and two appenders on one log is what separate run directories exist
to avoid.

The WP expected the hard part to be a torn copy. It was not. That came out at
about one click in a million, with copying again as the repair. The real defect
was next door: the GUI command the page had offered since WP-1401 was `None`
for **every run a project actually records**, so there was nothing for a button
to key on, and the test covering it passed because its fixture built a layout
no recorder produces.

**Done**
- `POST /api/run/<id>/gui` spawns `rietx gui --scratch <project> --no-open
  --machine`, reads the boot line and answers with its url. Gated as stop is:
  `_origin_ok`, 403 under `--read-only`, 404 for an unknown id, 409 for a run
  with no project. `sys.executable -m rietx.cli`, so a watcher in a worktree
  launches that worktree's package rather than whatever is first on `PATH`;
  `start_new_session`, so Ctrl-C in the watcher's terminal does not reach it.
- `runs.project_of` is the one authority for which project a run sits in and
  knows both layouts. `_label_for` and `RunRecorder._default_label` had one
  branch each and now call it.
- The button is a seventh column in the run list, one per row, drawn only where
  `gui_command` is non-null and `can_open_gui` is true.
- `gui_command` carries `--scratch`, which the manual had already been telling
  people to type.
- `cli.md` gains § Opening a copy in the GUI; the route table and the "only
  verb" paragraph follow it. Root CLAUDE.md's "the reader has one verb" clause
  is rewritten, since this WP made it false.

**Measured** (macOS darwin 25.5.0, arm64, `[dev]` + playwright)
- The torn-tail window is one threshold and it is python's 8192 B write buffer.
  A record that fits lands in one `write(2)`; one that does not is flushed in
  pieces. Eight records of a `mccusker_default` fit: rietveld 142-8068 B, 0
  over; lebail 142-8573 B, 1 over; pawley 142-8963 B, 3 over.
- Polling raw bytes against a hammer: **34 of 258 107 samples (0.013 %)** held
  a partial last line on the pawley seed, **0 of 260 107** on the rietveld one.
  About 0.24 us of torn state per append at 562 appends/s.
- A copy does reproduce one when it exists (written deliberately rather than
  raced for), and `read_records` and `Project.open` both refuse it by name.
  Copying again opens.
- No copy caught one by racing: 0 of 14 088 under the hammer, 0 of 2 767 in a
  shorter run, 0 of 200 under a real fit. The duty cycle predicts ~1.8 in
  14 088, so that is an upper bound rather than a floor.
- A real pawley fit: 6.0 history appends at 3.7/s, a 48 kB log, `scratch_copy`
  at 1.1 ms. Scaling the window by that rate puts a click at ~10^-6, and at
  zero for a rietveld project.
- Three GUIs launched in turn: **0.58-0.89 s** from `Popen` to the boot line,
  ports 8731 / 63972 / 63973 — `build_server` falls back by itself — and the
  source `history.jsonl` byte-identical after all three.
- **5247 passed, 132 skipped** in the fast selection, on the rebased tree
  before the review pass. The WP's own acceptance command is **257 passed**
  after it, the slow real-spawn test included.
  The browser suite was skipping entirely before this session, playwright not
  being a dependency and this worktree's venv not having had it, so the fast
  count is **not** comparable to one taken without it. That is 26 more tests
  than the branch started with: 12 python for the route and the two layouts, 3
  browser for the button, 3 for the launch's pipe, and 8 the review pass
  prompted or that the gate table needed.
- **The full selection did not run.** Nothing here can move a refinement
  number, so CLAUDE.md's rule does not call for it, and
  `wp1309-measured-background` was mid-full-suite at handover, so a count taken
  anyway would not have been this tree's.

**Gotchas**
- The column costs **8ch**, out of the run column, which is the flexible one.
  `SEAMS.list.minCh` goes 63 to 71 and the default list width 72ch to 80ch so
  run names keep the room they had. Three browser tests carried those constants
  and moved with them.
- `openGui` selects the run it launches. A notice belongs to one run and
  `drawRun` drops one that is not on screen, so a launch from an unselected row
  would report neither its progress nor its refusal.
- Notices carry a `kind` now. The stop button hides for the stop flow rather
  than for any notice at all, or a 90 s launch notice hides it for its duration.
- **`--machine`, not `--json`.** This file said `--json` in three places and no
  such flag exists.
- **The review pass (`/code-review high --fix`) found seven, all real, none
  declined.** Two were serious and both were in the launch's reader. It took
  one line off a pipe that has `stderr` merged into it, so a warning printed
  before `serve` would have been read as the boot line and a GUI that was
  serving reported as a failure; and it stopped reading there, while nothing
  else drains that pipe, so a child filling its 64 kB buffer would block in
  `write` for good. The failure paths also returned without reaping, and
  `start_new_session` means a stray GUI outlives the watcher holding a port and
  a scratch copy nobody can find.
  - A third was on the page and is the one worth carrying: `openGui` put its
    notice up through `refresh`, **which returns without doing anything while a
    poll is already in flight**. So a click during a poll showed nothing, and a
    second click is the ordinary response to that — two GUIs, two scratch
    copies, two ports. There is a `launching` set now, and `setNotice` paints
    rather than asking for a poll. `stopRun` had the same defect for the same
    reason and now goes through it too.
  - Three smaller: the read-only banner read one flag though the handler
    carries two; the manual said a bare `fit()` run's strip shows the
    equivalent command, wrong twice over since `gui_command` is `None` there
    and the example path is a project's; and the new browser helpers had been
    inserted between the partition's `#:` rationale and the constant it
    explains.
  - The review left no tests, so three were added for the reader plus the
    `_gui_argv` seam they need to stand a script in for the GUI. Checked
    against the pre-review reader: all three fail on it. The failure-message
    one only discriminates once its stand-in grew a traceback, the last-line
    rule being invisible when the reason is also the first line.
- **One browser test flaked once** under the other session's full suite
  (`test_a_drag_moves_the_seam_and_the_picture_follows_it`), and passed alone
  and on a clean re-run of all 30. A layout measurement under CPU contention,
  not a defect — but it is the shape to suspect first if it recurs.

**Next**
1. Three questions are the maintainer's and now have no WP holding them, every
   rung of the track being closed: the GUI's reflection ticks taking plotly's
   colorway (filed here by 1427 by way of 1429), the snapshot cadence 1413 left
   over WP-1404's gate, and the run-list default width this WP moved from 72ch
   to 80ch without settling.
2. Nothing else in the live-watcher track is open. 1428 was its last rung.

- **2026-09-16** — created, from the maintainer's ask after the demo job;
  revised the same day: the Goal says the copy is frozen, the stale-head
  reason is added, and the torn-tail paragraph no longer cites `PIPE_BUF`.

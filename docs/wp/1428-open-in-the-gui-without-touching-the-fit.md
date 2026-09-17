# WP-1428 — open in the GUI, without touching the fit

Milestone: unscheduled · Status: 🔄 2026-09-17 — claimed by @yue-here
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

- **2026-09-16** — created, from the maintainer's ask after the demo job;
  revised the same day: the Goal says the copy is frozen, the stale-head
  reason is added, and the torn-tail paragraph no longer cites `PIPE_BUF`.

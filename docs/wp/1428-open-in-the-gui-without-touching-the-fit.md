# WP-1428 — open in the GUI, without touching the fit

Milestone: unscheduled · Status: ⬜
Depends on: 1405 (the one verb and its gate), 1401 (the decision this revisits)

## Goal

A reader of `rietx watch` can open the project a running fit is writing in the
GUI with one click, and the fit does not notice. The GUI opens a scratch copy,
never the live project, and the watcher's gate for it is the one the stop
button already has.

## Context

The maintainer asked: can we have an "open in GUI" feature, in a safe way that
does not disrupt the ongoing refinement. Today the strip shows a command a
human can copy, `rietx gui <project>`, built by `_row` in `watch.py` for a run
that sits in a project's `live/`. WP-1401 § the decision kept it a string:
launching the GUI is a process boundary and the watcher performs no verbs.
WP-1405 then gave it one verb, stop, behind a host allowlist and a
`--read-only` flag. This WP asks whether the second verb is worth its cost,
and what "safe" has to mean first.

### Why the live project is never safe to open

- There is no read-only way to open a project. `Project.open` appends a head
  annotation before any verb runs, and every verb writes into the directory
  (root CLAUDE.md § Project; `gui/server.py:scratch_copy`'s docstring).
- The fit appends to the same `history.jsonl` at every stage. Two appenders on
  one log is the interleaving WP-1403 separated the *run* directories to
  avoid, and the history log has no such separation.
- The GUI's 409 while a run is in flight guards its own in-process run. It
  cannot see a fit in another process.

So the only object the GUI may open is a copy. `rietx gui --scratch` makes
one with `shutil.copytree`, byte for byte, into a temp directory that nothing
removes, and its header says the source is not written to.

### Where the copy is fragile

`history/store.py:read_records` raises `malformed history record` on any line
it cannot parse. A history node is about 10 kB (root CLAUDE.md § Conventions),
larger than `PIPE_BUF`, so a copy taken while the fit is mid-append can carry
a torn last line and fail to open. Measure how often: copy a project under a
fit two hundred times at random moments and count failures. Then choose:
retry the copy once on a torn tail (the append finishes within milliseconds),
or teach `read_records` to stop at a final line with no newline and report it.
The second changes a "bad lines raise" rule and needs the measurement to
justify it.

### The two forms, and the decision

**Copy the command.** The strip's `gui_command` grows `--scratch`, gets a
copy-to-clipboard button, and the reader pastes it in a terminal. No new verb,
no process spawned by the watcher, nothing for `--read-only` to refuse. It is
what exists today with one flag and one button.

**Launch it.** `POST api/run/<id>/gui` spawns `rietx gui --scratch <project>
--no-open --json` and returns the boot line's `url`; the page opens it in a new
tab. Behind the same host allowlist as stop, refused under `--read-only`,
refused for a run with no project. The spawned GUI outlives the watcher, as a
scratch copy already outlives its GUI. The `--json` boot line (url, port,
project, pid, scratch_of) exists for exactly this caller.

The launch form is what the ask means by a feature. It costs a second verb in
an app whose strength ROADMAP § A window into a run states as having none,
and a process the watcher spawns but does not own. The recommendation is the
launch form, on two conditions: the scratch copy is the only thing it can
open, and the copy's consistency is measured and handled before the button
exists. **The maintainer decides**, in this file, before the verb is written.

### What a run without a project gets

A bare `fit()` records under `.rietx/runs/` and has no project to copy. Its
row and strip show nothing for this feature. Building a project from a run's
snapshot is not a thing; the snapshot is a picture.

## Non-goals

- Opening the live project. Never.
- A GUI that reads a foreign run's events (the GUI's live panel is
  in-process; `rietx watch` exists because of that).
- Removing scratch copies. `scratch_copy` says why nothing does.
- Two appenders on one `history.jsonl` when a caller runs `Project.fit` with
  the GUI already open on that project. Named here; not this WP's.

## Tasks

- [ ] Measure the torn-tail rate of `scratch_copy` under a fit (200 copies at
      random moments), and record it here with the choice it forces
- [ ] The decision: copy-the-command or launch, written into this file by the
      maintainer with the date
- [ ] Either way: `gui_command` carries `--scratch`, and the strip gets a
      copy button beside it
- [ ] If launch: the route, gated as stop is (`_origin_ok`, `--read-only`,
      project runs only), spawning with `--json` and returning the url; the
      page opens it in a new tab and shows the url in the strip until the tab
      is open
- [ ] Tests: the gate (same table as `test_only_a_run_being_written_here_is_
      stoppable`), the original project's bytes unchanged across an open
      (sha256 of `history.jsonl` before and after), the fit's run still
      writing afterwards; a browser test clicks the button
- [ ] Manual: `cli.md` § `rietx watch` and § `rietx gui` say what the button
      opens and that it is a copy
- [ ] Skill: none. An agent driving rietx does not open a GUI.

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

- **2026-09-16** — created, from the maintainer's ask after the demo job,
  unrolled with 1424–1427 and 1429.

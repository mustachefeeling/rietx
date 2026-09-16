# WP-1428 — open in the GUI, without touching the fit

Milestone: unscheduled · Status: ⬜
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
carry a torn last line and fail to open. Measure how often: copy a project
under a fit two hundred times at random moments and count failures. Then
choose: retry the copy once on a torn tail (the append finishes within
milliseconds), or teach `read_records` to stop at a final line with no
newline and report it. The second changes a "bad lines raise" rule and needs
the measurement to justify it.

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
launch form, on three conditions: the scratch copy is the only thing it can
open, the copy's consistency is measured and handled before the button
exists, and the button's label says the copy is frozen. **The maintainer
decides**, in this file, before the verb is written, and the decision weighs
whether a frozen copy is worth a verb at all.

### What a run without a project gets

A bare `fit()` records under `.rietx/runs/` and has no project to copy. Its
row and strip show nothing for this feature. Building a project from a run's
snapshot is not a thing; the snapshot is a picture.

### Inherited

- **2026-09-16, from [1429](1429-one-palette-and-one-theme-for-three-pages.md):
  a GUI opened from the watcher now matches the page it was opened from.**
  Both read the theme out of `state_dir/settings.json` and draw from the same
  colour tokens, so the scratch copy this WP is considering will not arrive in
  a different colour scheme from the run list that launched it. One thing to
  carry if this WP ever passes `--state-dir`: `theme.state_dir` is the single
  resolver for that directory now (`gui/session.py` calls it), and a launch
  that pointed the GUI somewhere else would give the two windows different
  themes and nothing else.


- **2026-09-16, from [1424](1424-a-row-that-names-its-run.md): the GUI command
  has the strip's flexible slot to itself, and is the first thing the strip
  drops.**
  - `whereOf(run)` is now `run.gui_command` alone. The path it used to carry is
    the label's tooltip (`runTitle`) and the point count is on the picture, so
    `#s-where` holds one copyable command and nothing else.
  - **It is hidden below 990 px of run panel**, the first slot to go, because
    at 1400×900 with the list open the panel is 882 px and the slot's track was
    being squeezed to zero anyway — the command was not being cut, it was
    absent. So today a reader on an ordinary window sees no GUI affordance at
    all unless they collapse the list. That is the gap this WP fills, and a
    real affordance should not live in that slot: it is the one the strip drops
    first.
  - The command itself is unchanged (`watch/__init__.py` `_row`), still a
    string a human copies rather than a verb the app performs.

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
  - `_row`'s `gui_command` is in `watch/__init__.py` now, unchanged. The
    strip element that shows it is `#s-where` in `index.html`, filled by
    `whereOf` in `watch.mjs`.
  - `tests/test_watch_browser.py` took no diff and stays the bar: if it
    moves, the page moved.

## Non-goals

- Opening the live project.
- A GUI that follows a foreign run. The GUI's live panel is in-process, and
  the watcher is the live view.
- Removing scratch copies. `scratch_copy` says why nothing does.
- Two appenders on one `history.jsonl` when a caller runs `Project.fit` with
  the GUI already open on that project. Named here; not this WP's.

## Tasks

- [ ] Measure the torn-tail rate of `scratch_copy` under a fit (200 copies at
      random moments), and record it here with the choice it forces
- [ ] The decision: copy-the-command or launch, written into this file by the
      maintainer with the date
- [ ] Either way: `gui_command` carries `--scratch`, and the strip gets a
      copy button beside it, labelled as a copy at the click
- [ ] If launch: the route, gated as stop is (`_origin_ok`, `--read-only`,
      project runs only), spawning with `--json` and returning the url; the
      page opens it in a new tab and shows the url in the strip until the tab
      is open
- [ ] Tests: the gate (same table as `test_only_a_run_being_written_here_is_
      stoppable`), the original project's bytes unchanged across an open
      (sha256 of `history.jsonl` before and after), the fit's run still
      writing afterwards; a browser test clicks the button
- [ ] Manual: `cli.md` § `rietx watch` and § `rietx gui` say what the button
      opens, that it is a copy, and that the copy does not follow the fit
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

- **2026-09-16** — created, from the maintainer's ask after the demo job;
  revised the same day: the Goal says the copy is frozen, the stale-head
  reason is added, and the torn-tail paragraph no longer cites `PIPE_BUF`.

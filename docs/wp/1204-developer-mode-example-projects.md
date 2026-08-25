# WP-1204 — Developer mode and example projects

Milestone: v1.2 · Status: 🔄 2026-08-25
Depends on: — (WP-1201 for the empty-state list's styling, soft)

## Goal

A developer opens any project in the GUI without touching git or their own
recent list; a new user sees a set of example projects in the empty state and
opens one with a click.

## Context

The user's question: "As the developer, I need a way to test the GUI by
loading projects and messing with them, without messing up the git. How do I
do this? Also, there should be a good range of example projects I can load as
a new user."

Findings (2026-08-25):

- **Settings persist on the verb** (`gui/CLAUDE.md`), so every edit in the
  GUI writes into the opened `.rex` directory immediately; there is no
  non-destructive way to open a project.
- `suggested_project` is `Path.cwd() / f"{stem}.rex"` (`src/rietx/gui/
  imports.py:293-297`; the `suggest_in=` parameter exists and `session.upload`
  never passes it, `session.py:247-248`). Run from the checkout, that is the
  repo root, and `.gitignore` has no `*.rex` entry, so a created project shows
  up untracked.
- `GuiSession(state_dir=)` exists (`session.py:155-163`) and the tests use it
  ("a recent-projects store that is never the user's real home",
  `tests/test_gui_server.py:63-67`); `rietx gui` does not expose it. The env
  var `RIETX_STATE_DIR` (`_about.py:60-61`) does the same today. The full CLI
  surface is `server.py:620-651`: `project`, `--port`, `--no-open`,
  `--machine`, `--backend`, `--solver`.
- **No `.rex` exists in the repo** and no script builds one: `examples/`
  holds `Refinement`-level scripts; every `Project.create` is in tests under
  `tmp_path` (`tests/test_gui_server.py:69-73` `_project` is the nearest
  builder). Real inputs live in `tests/data/` (`11BM_NAC.fxye` 2.5 MB,
  `nist_srm660c_100a.cif` 433 kB, `FAP.XRA`+`FAP.EXP` 59 kB,
  `qarr/corundum.prn` 145 kB; provenance in `tests/data/README.md`).
- User decision (2026-08-25): **ship a small set in the wheel** (~3.2 MB
  against numba's 157 MB); the empty state lists them beside Recent.
- The acceptance suites' protocols per standard (mode, plan, held
  parameters, excluded regions) are the `viz/compare.py` registry, asserted
  field by field by `tests/test_compare_ui.py`. An example project quotes
  that registry; it never restates a protocol.

Design:

- `rietx gui --scratch PROJECT.rex`: copy the directory to a temp dir
  (`tempfile.mkdtemp`), open the copy, print the path in the boot line
  (`--machine` includes it). `--state-dir PATH` wires `GuiSession(state_dir=)`.
  `suggested_project` defaults to `~/rietx-projects/<stem>.rex` (created on
  first use), never cwd. `.gitignore` gains `*.rex/`.
- `src/rietx/data/examples/`: the four inputs as package data (checked into
  the wheel via `pyproject`'s package-data rule; `tests/test_gui_dist.py`'s
  "in the wheel" pattern extended). `src/rietx/examples.py`: `list_examples()
  -> list[ExampleInfo(name, title, description, bytes)]`,
  `build_example(name, into) -> Project` (a `Project.create` with the
  standard's protocol from `compare.py`; no fit).
- `GET /api/examples`, `POST /api/examples/open {name}` (builds into
  `state_dir/examples/<name>.rex` if absent, then `project_open`; a rebuilt
  copy is one click away as `POST /api/examples/reset`).
- Empty state: an **Examples** list beside Recent, each with one docs-style
  line (what the specimen is, what it teaches).

## Non-goals

- Fitting the examples in CI: a build is `Project.create`, no refinement.
- A packing format for `.rex` (1003 §B's zip transport stays parked).
- The wizard and the empty state's Open control: WP-1205.

## Tasks

- [x] `rietx gui --scratch` and `--state-dir`; `suggested_project` default
      moved out of cwd; `.gitignore` `*.rex/`; `cli.md` option table updated.
- [x] Package data + `examples.py` + `pyproject` package-data; the wheel test
      extended to assert the examples are in it and under a size ceiling.
      (No `pyproject` entry was needed: hatchling takes a package directory's
      non-ignored files, which is exactly why the wheel test is not optional.)
- [x] `tests/test_example_projects.py`: every example builds under
      `tmp_path`, its protocol asserted field by field against `compare.py`'s
      registry, and `list_examples()` is in bijection with the data directory.
      (**Not** `tests/test_examples.py`, which the WP named and which already
      exists — it runs the `examples/` scripts the manual includes.)
- [ ] Routes + the empty-state Examples list (docs-style one-liners); the
      `RESERVED_ROUTES`/`ROUTES` disjointness test green.
- [ ] Manual: `using/quickstart.md` gains "open an example"; `files.md`
      names `--scratch`.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_example_projects.py tests/test_gui_server.py tests/test_gui_dist.py
.venv/bin/rietx gui --scratch "$(.venv/bin/python -c 'import rietx.examples as e, tempfile; print(e.build_example("nac", tempfile.mkdtemp()).path)')" --no-open --machine
git status --short   # clean after the run
```

## References

- `tests/data/README.md`: provenance and reference values for the four
  inputs; the example descriptions quote it.

## Handover log

- **2026-08-25** — created from the v1.2 triage.

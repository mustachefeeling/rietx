# WP-1204 — Developer mode and example projects

Milestone: v1.2 · Status: ✅ 2026-08-25 — shipped; three example projects in the wheel, `--scratch`/`--state-dir` on the CLI
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
- [x] Routes + the empty-state Examples list (docs-style one-liners); the
      `RESERVED_ROUTES`/`ROUTES` disjointness test green.
- [x] Manual: `using/quickstart.md` gains "open an example"; `files.md`
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

### 2026-08-25 (2nd session) — developer mode, and three example projects in the wheel

Both halves of the question are answered. A developer can now open any
project in the GUI without touching git:
`rietx gui PROJECT.rex --scratch` copies the directory to a temp dir and
opens the copy, so the one named on the command line is never written to,
and `--state-dir` keeps the recent list and theme out of the real home. That
matters more than it looked: **opening a project already writes to it**, a
head-annotation line appended to `history.jsonl` before any verb is called,
so there was no read-only way to look at one at all. And a new user is no
longer met by a wizard asking for a data file they do not have — three real
specimens ship in the wheel and open with one click.

The costly finding is a licence one, and it shrank the plan. The WP assumed
four inputs including `qarr/corundum.prn`; the round-robin patterns carry
**no explicit licence** and are already kept out of the sdist for that
reason, so the four pure-phase standards built on them cannot be examples
however small and useful they are. What ships is srm660c, fap and nac, and
fap had to be *created* as a `compare.py` standard to be shippable at all.

Done (all five checklist items):

- `--scratch` and `--state-dir` on `rietx gui`; the boot line carries
  `scratch_of`, the **source**, because the copy is already `project` and the
  source is the fact a path cannot carry. `--scratch` with no project is
  refused rather than ignored. `suggested_project` moved from `Path.cwd()`
  to `~/rietx-projects` (`_about.PROJECTS_DIR_NAME`); `.gitignore` gains
  `*.rex/`.
- A **`fap` standard** in `viz/compare.py`, mirroring
  `tests/test_acceptance_fap` field for field the way `lab6_capillary`
  mirrors the capillary acceptance, and pinned to it by a new anti-drift
  test. `Standard` also gains `pattern` and `reader_options`: which of
  `files` is the measurement and the reader *call* that claims it, declared
  rather than inferred, because `files[0]` was only a convention and a pdCIF
  with a `_meas` and a `_calc` block is a different pattern depending on
  `block`.
- `src/rietx/examples.py` + `src/rietx/data/examples/`. An example **is** a
  `STANDARDS` entry, so no protocol is restated, and `list_examples()` is
  that registry filtered by what shipped. The one hand-written half is
  `BLURBS` — `Standard.description` is written for a reader comparing
  corrections and answers a question a first-time user has not asked.
- `GET /api/examples`, `POST /api/examples/open|reset`, built into
  `state_dir/examples/`. Open ends in `project_open` and returns exactly what
  it returns. Both verbs are behind the 409; listing is a read and is not.
  `name` is checked against the example list rather than sanitised.
- Empty state: an **Examples** list beside Recent, `.pick` rows with a
  `button.ghost` Reset on the ones already built. `quickstart.md` gains "If
  you have no data yet" (both blocks execute); `files.md` and `cli.md` name
  `--scratch`.

Measured (`[dev]`, no jax/torch, darwin/arm64, Python 3.12.12):

- Fast suite **2800 passed, 117 skipped**, ~2:05 (one run, this machine).
  Collection 2915 = passed+skipped − the 2 module-level `importorskip`s that
  fire without jax/torch. **+39 against `main`**, exactly the 39 tests added
  and no new skip: `test_gui_server` 107→121, `test_gui_dist` 11→13,
  `test_compare_ui` 18→20, and `test_example_projects.py` 21 new. vitest
  412→415 (+3), 20 files.
- Wheel **2.20 → 2.79 MB**; examples 2.90 MB uncompressed, ~601 kB deflated.
  No `pyproject` entry was needed — hatchling takes a package directory's
  non-ignored files, which is exactly why the wheel test is not optional.
- Deflated cost of what was *not* shipped, for whoever revisits the licence
  question: `11BM_LaB6_660a.fxye` 1335 kB, each `qarr/*.prn` 26 kB.
- The **full suite was not run** (ladder rung 3): nothing here can move a
  measured number — GUI, CLI, packaging, docs, and additive registry fields.
  The one slow test reachable from the changed non-GUI code
  (`test_compare_runs_a_real_standard`) was run directly with
  `test_acceptance_fap.py`; 3 passed in 3.6 s.

Gotchas:

- **`tests/test_examples.py` was already taken** — it runs the `examples/`
  scripts the manual includes. The suite here is
  `tests/test_example_projects.py`; the WP's original name and acceptance
  line were corrected in place.
- The **browser found what jsdom could not**, again. `.pick` gives up its box
  because the row is the target, so a list that gives the row no hover reads
  as three paragraphs of prose that happen to be clickable. Driven end to end
  in Chromium in both themes; the fap example opens to
  `fap.rex · FAP.XRA · 5753 pts` with GSAS's 130° exclusion on the plot.
- Self-review caught one real defect: `example_reset` cleared `self.project`
  and left `_run`, so between the removal and the open one route answered
  `NO_PROJECT` while another still had the last fit's Rwp. WP-1201's "a
  statistic outlives the thing it describes", one scope over.
- Both CLAUDE.md caps were raised with the usual justification (855→869 root,
  612→628 `gui/`); root was sitting *exactly* on its cap.

Next: **[1202](1202-help-corpus.md) then [1203](1203-help-popover.md)**, which
attach the popover to the `.help` register WP-1201 declared — the examples
list added no `title=` beyond two verb phrases, so nothing here is owed a
help entry. [1205](1205-new-project-open-browse-defaults.md) has an
`### Inherited` note from this WP: its Open control now sits beside an
Examples section, and the wizard's suggested path is no longer the working
directory, which is half of the "sensible defaults" it was going to argue
for.

- **2026-08-25** — created from the v1.2 triage.

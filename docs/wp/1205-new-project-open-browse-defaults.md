# WP-1205 — New project: open any project, browse, sensible defaults, the wizard bug

Milestone: v1.2 · Status: ⬜
Depends on: WP-1201, WP-1203, WP-1204

## Goal

The empty state can open any project on the machine; the wizard reads like a
form for a person, with defaults visible and the registry's prose behind help;
opening a recent project no longer leaves the wizard painted over the Model
panel.

## Context

The user's notes, and what the code does (2026-08-25):

- **"Information overload."** The three quoted strings are: (1) `claimed by
  bruker_raw — <sniff>. σ: <sigma>` at `Model.svelte:692-695`, a client
  literal joined to `PatternFormat.sniff`/`sigma` served by `preview_pattern`
  (`imports.py:274-275`; the Bruker prose is `io/formats/bruker_raw.py:724-
  738`); (2) the `scan` option's `help` from `READER_OPTIONS`
  (`io/formats/base.py:141-155`) rendered verbatim at `Model.svelte:729`;
  (3) `Required, and not defaulted: Instrument has no default source…` at
  `Model.svelte:790-794`, a client literal paraphrasing the server's refusal
  at `session.py:2655-2658`. All were written for `capabilities()` consumers.
- **Scan field.** A picker only when `scan_count > 1` (`Model.svelte:696-
  731`); the count is never shown; labels load on `focus`/`pointerdown` via
  `GET /api/upload/pattern/scans` (`session.py:257-285`), so before a click
  the control reads `scan 0`. Default scan 0 is the reader's own, with
  `PATTERN_MULTISCAN_DEFAULTED` in the diagnostics list.
- **Project directory** is a text input pre-filled from `suggested_project`
  (`Model.svelte:843-846`, `:208`); the browser cannot give a path. No route
  lists the filesystem (`RESERVED_ROUTES` is empty, `session.py:105`).
- **Instrument is mandatory** at every level: `blocked()` (`lib/wizard.ts:
  234-236`), `Project.create` (`project.py:107-116`), `_as_instrument`
  (`session.py:2654-2658`), `Source._nonempty` (`schemas/instrument.py:126-
  130`). `bragg_brentano()`/`flat_plate_transmission()` default to Cu Kα;
  `debye_scherrer(wavelength)` has no anode to read. The header hint
  (`imports.suggest_instrument`, `imports.py:532-550`) pre-fills anode and
  radius when the file states them, and sends `null` when name and
  wavelength disagree.
- **No way to open a project.** `Open…` (`App.svelte:707-711`) is inside
  `{#if project}`; the empty state offers only the recent list
  (`Model.svelte:660-678`), populated by projects this machine has opened.
  `POST /api/project/open {path}` exists (`session.py:341-358`).
- **The wizard sticks.** `showWizard = !project || wizardOpen`
  (`Model.svelte:166`); the recent-list button (`Model.svelte:666-668`)
  calls `onopen` and never clears `wizardOpen`, so after `Open…` → recent
  the Model tab shows the wizard over the opened project until `Back to the
  project` is found. `Model` is mounted twice (`App.svelte:758-759` empty
  state, `:807-809` tab column) with independent state.

Decisions: the API keeps its refusal (an anode nobody chose must not become
a wavelength in every cell); the **wizard pre-fills a visible default**
(header hint, else Bragg-Brentano Cu Kα) and says in one line what it
assumed, so the choice is made by seeing it. A directory browser is a
read-only server route on a localhost server; roots are the home directory
and cwd, and a listing never leaves them.

### Inherited

**From [1204](1204-developer-mode-example-projects.md), 2026-08-25 — half of
"sensible defaults" already landed, and the empty state now has two lists.**
Three things to fold in before writing this WP's tasks.

1. **The suggested project path is no longer the working directory.**
   `imports.default_project_dir()` is the one authority and answers
   `~/rietx-projects` (`_about.PROJECTS_DIR_NAME`); `preview_pattern`'s
   `suggest_in=` is still the seam for a caller with a better idea, and
   `session.upload` still does not pass it. Nothing is created at preview time
   — `Project.create` makes the parents — so if this WP adds a *browse*
   control, "the directory does not exist yet" is the normal case rather than
   an error to report.
2. **The empty state is no longer wizard-only.** `Model.svelte`'s wizard now
   carries a `section.examples` beside `section.recent`, both fetched by the
   shell (`App.svelte`: `loadRecent`, `loadExamples`) because opening either is
   the shell's verb. This WP's "Open any project" control lands as a third
   thing in that block, and the ordering question (Recent / Examples / Open /
   New) is now a real design choice rather than an implicit one.
3. **`rietx gui --scratch` and `--state-dir` exist**, which changes what this
   WP has to solve. "Open a project without messing it up" is answered at the
   CLI; what is *not* answered is opening one from inside the app without
   changing it, and the honest options are to leave that to the CLI or to add a
   scratch checkbox to the Open control. `gui.server.scratch_copy` is the
   function either way.

Also worth knowing: the wire surface gained `GET /api/examples` and
`POST /api/examples/open|reset`, and `POST /api/examples/reset` is the only
destructive verb on the GUI surface. Its `name` is checked against the example
list rather than sanitised — the same shape any `GET /api/fs?path=` this WP
adds will need, except that a filesystem path has no list to check against, so
the confinement has to be a real containment test.

## Non-goals

- The CIF requirement (WP-1206, WP-1207).
- Reader-registry prose: it stays as the `capabilities()` contract; only
  what the wizard *shows* changes.

## Tasks

- [ ] `GET /api/fs?path=`: directories and `.rex` entries under a root,
      refusing paths outside the roots; `tests/test_gui_server.py`
      confinement tests (`..`, symlinks out, absolute paths elsewhere).
- [ ] `Browse.svelte`: one modal used for opening a project and for picking
      the project directory; a typed path field beside it; `Open…` in the
      empty-state header; `startImport` and the recent-list arm both settle
      `wizardOpen`; `Model` mounted once.
- [ ] Wizard prose: one docs-style line per step; `sniff`/`sigma`/option
      `help` behind the popover (WP-1203 keys); the `Model.svelte:790-794`
      literal deleted; `blocked()` sentences rewritten; instrument pre-fill
      with its one-line reason; the Create button's line rewritten.
- [ ] Scan control: "this file holds N scans; reading scan 1 of N (label)",
      labels fetched eagerly when N > 1; the default stated, not implied.
- [ ] Browser pass from a blank state: open a project by browsing, create a
      project without the CLI argument, open a recent one and confirm the
      Model tab shows the editor; rebuild the dist.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_gui_server.py -q
npm --prefix gui test && npm --prefix gui run check
.venv/bin/python -m pytest tests/test_gui_dist.py -q
```

## References

- WP-1014 (two-phase uploads, the `instrument_hint` rule), WP-1047 (reader
  options and the scan picker).

## Handover log

- **2026-08-25** — created from the v1.2 triage.

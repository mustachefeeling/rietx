# WP-1017 — GUI manual, in-app help, onboarding

Milestone: v1.2 · Status: ⬜ — re-scoped 2026-08-25 as the last WP of v1.2;
the GUI ships as a **beta** feature until it lands
Depends on: WP-1201…WP-1217 (last in v1.2: the chapters describe panels those
WPs settle, and the beta declaration lifts here)

## Goal

The GUI is documented where the theory manual lives, helps from inside the
app, and onboards a first-year PhD student without a wizard that hides the
real UI.

## Re-scoped 2026-08-25: the manual, and the mechanism that keeps it true

Deferred on 2026-08-14 because the GUI kept moving (eight sessions had
written "three sentences in this manual are now wrong" into the mailbox
below). It returns as the **last** WP of v1.2, after the seventeen panel WPs
(1201-1217) settle what it describes. Two things changed in the scope.

**The manual gets a sync mechanism, not only chapters.** The user's ask:
"we need a method of keeping all the manuals in sync with the code". Prose
about behaviour cannot be checked mechanically; names, vocabularies,
constants and pictures can, and the chapters are written so that everything
checkable is checked:

- **Descriptions have one authority.** Every parameter, flag, stage field
  and wizard field is described in the help corpus (`rietx.help`, WP-1202);
  the GUI popover renders it and `docs/manual/using/glossary.md` is
  generated from it. A chapter links to a glossary entry; it never restates
  one.
- **Routes are partitioned.** Every route in `gui/server.ROUTES` is named in
  a GUI chapter or excluded with a reason, the `tests/api_surface.py`
  pattern; a new route fails the partition until documented.
- **Panel and tab names are a corpus.** vitest writes `tests/data/gui/
  panels.json` from the live tab strip and pytest asserts every chapter
  names each, the fnmatch mechanism in the other direction.
- **The `.rxt` grammar quotes the parser.** `FORMAT_VERSION` and
  `VALUE_DIGITS` are fenced constants; the keyword table is injected from
  `textdoc._KEYWORDS`, already pinned to `lib/rxt.ts`.
- **Screenshots are generated.** `docs/manual/make_screenshots.py` drives
  playwright over the shipped example projects (WP-1204), light/dark pairs,
  the `make_figures.py` rule; a test asserts every screenshot a chapter
  references is one the script produces, so a moved control is a stale
  picture the build can name.

**In-app help is not this WP's any more.** The `static/help.json` and
tooltip wiring the original scope carried landed as the corpus (1202) and
the popover (1203); what remains here is the "learn more" anchors' dead-link
guard being green over the finished chapters, and the first-run checklist.

The mailbox below was accurate on 2026-08-06 and is **left for the session
that picks this up**, per its own rule: prune it against the running app,
not against the notes.

## Context

- **Inside `docs/manual/`** — same Sphinx/MyST/furo tree, same `-W`, same
  guards (`tests/test_manual.py`); a separate doc root would need its own
  guard set for no benefit. Three layered chapters matching the audience
  gradient:
  - `gui-quickstart.md` — install (`pip install rietx[gui]`) → open →
    fit → read the report.
  - `gui-guide.md` — panel by panel, including *when to branch* (the
    history worktree is the differentiator; teach the workflow, not just
    the buttons).
  - `gui-power.md` — the **normative `.rxt` text-format spec**,
    keyboard/palette, and the console-to-script transition — the API-echo
    story as the on-ramp to the Python API.
- The manual's anti-divergence rules apply and are executable
  (`tests/test_manual.py`): fenced constants are MyST substitutions
  injected from the live package in `docs/manual/conf.py` — **the rxt
  format version becomes a fenced constant injected from
  `gui.textdoc.FORMAT_VERSION`**, so a format bump that misses the manual
  fails the build. A new fenced constant needs a `conf.py` line *and* a use
  in a chapter.
- In-app help: tooltips from `static/help.json`, each with a "learn more"
  anchor into the built manual; `tests/test_gui_help.py` asserts every
  anchor exists (dead-link guard, same spirit as `test_manual.py`).
- First run: a **non-modal progressive checklist** (Load pattern → Load
  structure → Check instrument → Run → Read the report) — never a modal
  wizard; state in `ProjectDoc.ui`.

### The surface as it is, measured 2026-08-28

The mailbox fifteen sessions wrote into this file is consumed here. It was
right to keep — three of its entries were the only record that a control had
moved — but most of it described a screen that has since moved again, so it is
replaced by what the running app does today (HEAD `72c35ff6`, read off the
source and the tests that pin it, not off the notes). What a chapter must
*teach* rather than list survives below it.

- **Nine tabs, one column**: `Parameters | Plan | Peaks | Model | Text |
  Series | Report | History | Build` (`App.svelte`'s `TABS`, pinned by
  `App.test.ts`). WP-1034's "eight" is stale — 1016 added Series. The strip
  renders only with a project open, every panel stays mounted while hidden, and
  the header's `Split | Full` chooses only how much window the column gets.
- **The header**: title and version, the project chip (name · data file · pts ·
  mode · σ source), Rwp and GoF with a `⚠ not a fit yet` term past
  `MATURITY_MAX_RWP`, then `Open…`, `Split | Full`, `Simple | Advanced`, the
  three-way theme `◐ ☀ ☾`, the run pill, `Run`, `Cancel`, `⌘K`. There is no
  menu bar and no Save button: `Save the project` is a palette command only.
  The theme is the one control present on the empty state.
- **Ten single-key shortcuts, and Escape is not one of them**: `r` run, `.` run
  the selected stage, `f`/`x` free/fix the filtered glob, `/` focus the filter,
  `p` peaks, `?` report, `h` history, `t` text, `m` model; `⌘K` the palette.
  Escape closes the help popover if one is open, otherwise cancels a run —
  handled above the command table, so the `Esc` on the palette's Cancel row is
  a *label*. Single keys are ignored while focus is in a field. Eighteen
  palette commands, each carrying the Python call it makes.
- **The plot has no tooltip** (1213). `hoverinfo` is `"none"` on every trace and
  what a reader gets is the readout strip under the canvas: fixed slots, 2θ and
  d always, then one row per *drawn* curve, each label in its own ink. A slot
  empties to `—` rather than disappearing, so the canvas never resizes under
  the pointer. A solid spike marks the 2θ. Prose must not say "hover for
  values", and a screenshot taken after `data only` shows a shorter strip and
  is correct.
- **Two registers of knob under the plot, and only one changes the answer**:
  the residual selector (`Δ/σ` default, `Δ`, `Σχ²`), the intensity scale (`lin`,
  `√`, `log`) and the curve toggles are drawing choices and are not persisted;
  the fitted range, the excluded regions and their channel count are protocol,
  persist on the verb and move Rwp. `⇥ range` and `✂ exclude` arm a drag,
  suspend the peak verbs and disarm after one selection.
- **The empty state is the Model panel** with three ways in — the recent list,
  the shipped examples, and `Browse for a project…` — above a four-step wizard:
  Pattern, Structure (`CIF file` / `Type a cell` / `None yet`), Instrument,
  Project. Step 2's third answer means a project can exist with no phase, and
  `Run` then carries the reason it is disabled.
- **Seventy-seven routes**: 74 in `ROUTES` plus the three raw-byte upload
  routes; `RESERVED_ROUTES` is empty. That is the set the partition test in
  Tasks has to cover.

**What a chapter has to teach rather than list.** These are the mailbox's
surviving substance — each one is something the screen cannot say about itself:

- **A series is N refinements chained by a warm start**, not one joint
  residual, and `direction="both"` is the only check separating a measured
  trajectory from an ordering artefact. A series does not persist. Four status
  chips, taught as two pairs: `restaged`/`reseeded` against `hard`/
  `unrecovered`, and on the trajectory a ring is a good fit from a different
  start while a cross is not a measurement at all.
- **An edit empties the plot until the next run, and that is the design** — the
  curves described values the model no longer holds. Teach *edit → Run →
  compare*. Undo is a checkout, and a checkout throws the curves away for the
  same reason; users read the empty plot as a crash.
- **The filter box is the selection**, because one glob is one history node.
  Simple mode hides the rows nothing can free and reports the count it hid.
- **A suggestion with no Apply button is not broken**: four of the sixteen
  action kinds are advice, and the note beside them is the deliverable. A
  greyed one reading `vetoed:` is the engine agreeing with you. The predicted
  Δχ² is one number for the whole report and cannot rank anything.
- **"Could not rule out" is the headline, not a footnote** — applying
  `refine_zero_shift` to a fit whose *cell* was wrong improved Rwp from 21.6 %
  to 9.3 % by putting the error in the wrong parameter, and the report said so
  in advance. The best worked example in the repo for the never-a-confident-
  wrong-singleton rule.
- **A candidate list with no high-confidence entry is a result, not a
  failure**, and the extinction *symbol* is what a powder measures — a single
  space group is a convention the user chooses. `quick` is the default preset
  and its ceiling means a `low` from a truncated run is unconfirmed.
- **The bond threshold is a drawing threshold, not chemistry** (LaB6 at 1.15
  draws a cage; 1.05 leaves the B₆ octahedron), and the ellipsoids are a
  diagnostic — an over-flexible background arrives here as balloons. An
  exaggeration factor is not a probability, so a figure exported at ≠ 1 is not
  ORTEP-quotable. Element colours are decided **per phase**, so one element can
  be two colours in two phases.
- **There is no merge and no force-apply** in the text pane: the loser's
  document carries the winner's *old* values for every untouched row, so
  applying it would silently revert them. Comments do not survive a re-render.
- **The reader is a decision with consequences.** The wizard's pattern step
  names the *reader* that claimed the file and shows that reader's own
  diagnostics — sometimes a 188× attenuator correction, not only a repair. A
  header whose anode and wavelength disagree pre-fills **nothing**, because a
  wrong pre-fill looks like it was read.
- **Every pointer verb has a typed twin**, and the plot prints its four
  gestures whenever the Peaks tab is up — so the chapter's job is to explain
  why, not to repeat them. A drag only moves a line once you are zoomed in far
  enough for the grab radius to apply; at the survey view a drag is always a
  zoom.
- **rietx is also a phase this software analyses.** The manual needs a
  disambiguation convention from its first public page: the phase as
  `rietx (TiO₂)`, the package in code formatting. Never write `.rietx` — the
  format tokens are `.rex`, `.rxt` and `instrument_profile`, and where the name
  is needed in code it is imported from `_about.py`.

## Non-goals

- No screencasts/video, no hosted docs decisions (that is WP-1003's
  release scope).
- No autodoc API reference (0604's decision stands — a rendered API
  reference is its own document with its own failure modes).
- No restating theory — the GUI chapters link into the existing theory
  chapters rather than duplicating equations.

## Tasks

- [ ] `gui-quickstart.md` + toctree wiring; builds `-W`-clean.
- [ ] `gui-guide.md` — panel by panel, when-to-branch workflow section.
- [ ] `gui-power.md` — normative `.rxt` spec with `FORMAT_VERSION` as a
      fenced constant (conf.py line + chapter use), keyboard/palette table,
      console-to-script story.
- [ ] `static/help.json` + tooltip wiring + "learn more" anchors;
      `tests/test_gui_help.py` dead-link guard.
- [ ] First-run progressive checklist (non-modal), persisted dismissal.
- [ ] Route partition test (`server.ROUTES` documented or excluded with a
      reason) and the panel-name corpus (vitest writes, pytest reads).
- [ ] `docs/manual/make_screenshots.py` over the shipped examples +
      the referenced-screenshot test; light/dark pairs committed.
- [ ] The glossary and every `{ref}` to it from the chapters; lift the beta
      declaration in README and `using/compatibility.md`.

## Acceptance

```sh
.venv/bin/python -m sphinx -W -q -b html docs/manual docs/manual/_build/html
.venv/bin/python -m pytest tests/test_manual.py tests/test_gui_help.py -q
.venv/bin/python -m ruff check src tests examples
```

## References

- WP-0604's manual architecture (fenced constants, `*Source:*` lines,
  cited-bib guard) — the machinery these chapters extend.

## Handover log

- **2026-08-25** — re-scoped as the last WP of v1.2 (the GUI milestone):
  the chapters keep their shape, the sync mechanism above is added, and
  in-app help moved to WP-1202/1203. Milestone field, Depends line and the
  ROADMAP row (now in § v1.2) synced. The mailbox is untouched on purpose.
  Next: nothing until 1201-1217 land.
- **2026-08-14** — **deferred past the public release** (user decision): the
  GUI ships as a beta feature and gets its manual once the panels settle.
  Done: Status line, milestone field and the ROADMAP row moved to a new
  "Post-v1.0" section (shared with 1067, whose § Floor still gates the
  release); § Deferred added above with the grounds and the two hand-offs. Next: nothing here until post-release — the successor is
  [1067](1067-user-api-manual.md), which carries the README's beta
  declaration and the one-line `rietx gui` mention, and 1003, whose
  `### Inherited` now records that this WP no longer blocks the freeze.
  Gotcha for whoever returns: the mailbox below was accurate on 2026-08-06 and
  has not been re-read since; treat every "this sentence is now wrong" entry as
  itself possibly wrong, and prune against the running app rather than against
  the notes.
- **2026-07-29** — created from the v1.0 GUI plan.

# WP-1208 — Plan panel: the gentle introduction

Milestone: v1.2 · Status: ⬜
Depends on: WP-1203

## Goal

A crystallographer who has only ever refined one step at a time understands,
from the panel alone, that a plan is an ordered list of stages, that each
stage frees a named set of parameters on top of the last, and what the next
click will do.

## Context

The user: "the kind of plan we're implementing here is a new concept to most
crystallographers. Most refinement software just refines a single step at a
time."

Findings (2026-08-25, `gui/src/panels/Plan.svelte`, 358 lines):

- The panel offers a preset `<select>` (`:144-156`), a draggable stage list
  with a name input, a `Run` button and `×` per stage (`:173-218`), one
  comma-separated glob input per stage (`:195-200`, placeholder `dot-path
  globs freed here — phases.*.cell.*`), Advanced fields (`:201-215`) and
  Save/Revert (`:157-160`).
- The only visible prose is `when_to_use` (`:163-169`); `description` is a
  hover `title`; nothing says what a plan is. The panel's own source comment
  (`:2-16`) explains it to a code reader.
- Globs are never resolved against the live table: a stage shows its glob
  string, not which parameters it will free, how many are held and why.
- `PLAN_INFO` (`strategy/staged.py:446-467`) carries `title, description,
  modes, when_to_use` and reaches the panel through `capabilities()` →
  `GET /api/plans` (`session.py:639-646`).
- **Cumulative staging**: an intermediate stage's parameters keep refining
  in every later stage, and only the last stage converges
  (`RefinementPlan.intermediate_ftol`, WP-1123). That is the thing to draw.
- Per-stage results exist: `fit(stage_reports=True)` → `stage_reports_` and
  the `trajectory` companion (WP-1058), default off since WP-1003.
- `Params.svelte`'s bulk verbs send the glob and the client matcher is a
  preview held to Python by the committed fnmatch corpus (WP-1011).

Design: a `GET /api/plan/resolve` route returning, per stage, the paths its
globs match on the live table, which of those are new this stage, the
cumulative free count, and the held matches with `held_because`; the panel
renders the plan as a ladder ("stage 3 · +4 · 11 free"), each stage
expandable to its list. After a run, the ladder carries each stage's Rwp
from the stage reports (the GUI passes `stage_reports=True`; the answer is
bit-identical). An explainer line plus the preset's `description` visible,
under `/yue-docs-style`; `StageSpec` field help from the corpus.

## Non-goals

- Plan authoring beyond what exists (globs, order, per-stage fields).
- Suggesting a plan (`Refinement.suggest()` is a parameter, WP-1050).

## Tasks

- [x] `GET /api/plan/resolve` in `GuiSession` (a `ParameterTable` build per
      call; matched with `fnmatch` the way `set_vary` matches); tested
      against the fnmatch corpus vocabulary.
- [x] The ladder rendering, the per-stage disclosure, cumulative counts, held
      matches with their reason; the explainer and `description` visible;
      corpus help on every stage field; "Run this stage" / "Run all" named.
- [x] Stage Rwp on the ladder after a run — off the **history nodes**, not a
      `stage_reports=True` run verb: the two numbers are bit-identical (pinned
      by `test_the_node_rwp_is_the_trajectory_rung_rwp`) and the trajectory
      costs 7.7× the fit to rebuild, so the run verb is untouched.
- [x] Browser pass on the NAC example: read the ladder cold; dist rebuilt.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_gui_server.py -q -k "plan"
npm --prefix gui test && npm --prefix gui run check
```

## References

- McCusker et al. (1999) §3, the turn-on order the presets encode.
- WP-1123 (cumulative staging), WP-1058 (stage reports).

## Handover log

- **2026-08-25** — created from the v1.2 triage.

# WP-1004 — Parameter & plan API surface

Milestone: v1.0 · Status: ⬜ not started
Depends on: —

## Goal

Every parameter listable as data (`Refinement.parameters()`), vary flags and
values settable *through* `Refinement` with history nodes recorded, and
exactly one `StageSpec`/`PlanSpec` in the tree. This is the surface the GUI's
parameter table (WP-1011) and text pane (WP-1009) sit on — but it is plain
Python API, useful without either.

## Context

- `params/vector.py:85` — the `Entry` dataclass is the ground truth:
  `path, value, vary, lo, hi, transform, tie (AffineTie | None), locked`.
  `ParameterTable.set_vary(path_globs, vary) -> list[str]` already exists at
  `params/vector.py:450` (and `params/multi.py:94` for the stacked table) —
  the new `Refinement` verbs **delegate**; they do not reimplement glob
  matching or the locked-entry protections.
- `schemas/history.py:32` — `NodeKind` (a `Literal`, not an enum) already
  reserves `"set_vary"` and `"set_value"`, unused since v0.2.
  `NodeAction.api_call()` (`schemas/history.py:93`) already renders
  `ref.set_vary(...)` — and renders **`ref.set_values(...)` (plural)** for the
  singular kind `"set_value"` (verified 2026-07-29). Reconcile deliberately:
  either the public verb is `set_values({path: value, ...})` or `api_call`
  changes. The acceptance test `eval`s the rendered string, so the mismatch
  cannot survive this WP either way.
- **The StageSpec twins are incompatible, and the gap is a latent bug**
  (measured 2026-07-29, plan verification): `schemas/history.py:36` has
  `from_stage`/`to_stage` but **no `strain_seed`** — `from_stage` reads
  `getattr(stage, "seed", 0.0)` and never `strain_seed`, so a Stephens stage's
  `strain_seed` silently round-trips to 0 through the history tree (un-caught
  because no Stephens stage has been checked out and re-run). `agent.py:75`
  has `strain_seed` (`:86`) plus `min_length=1` on stages and schema
  descriptions, but no `from_*` direction. One schema in `schemas/plan.py`
  fixes both; `schemas/history.py` and `agent.py` re-export from it so
  existing imports keep working.
- Locked entries: `set_vary` globs can never free locked entries
  (emission-line weight 0, symmetry-fixed cell angles) — the existing table
  rule holds. `set_value` on a locked entry raises; on a tied entry raises
  **naming the tie target** (the GUI turns that into a tooltip; a bare
  `ValueError` is not actionable).
- `strategy/staged.py:235` — `PLAN_PRESETS`, seven names: `mccusker_default`,
  `mccusker_structural`, `lab_bragg_brentano`, `lab_calibrate`,
  `lab_sample_refine`, `profile_only`, `pawley_default`. **No `PLAN_INFO`
  exists anywhere** — the GUI preset picker needs per-preset title,
  description, intended mode, and when-to-use, and that belongs beside the
  registry, guarded by a membership meta-test (the WP-0602 pattern in
  `tests/test_agent_surface.py`).
- `Refinement.parameters()` is a cold path — pydantic is fine there (the
  no-pydantic rule binds the hot loop only). Unlike
  `RefinementResult.parameters` it must include fixed, locked and tied
  entries: the GUI shows the whole table, greyed where appropriate.

### Inherited

From the **v1.0 GUI plan** (un-fencing commit, 2026-07-29): this WP exists
because the GUI needs parameters-as-data, but everything here stays
GUI-agnostic — no HTTP, no session object, no serialization beyond the
schemas. The freeze implications (ParameterRow, the plan-schema unification
and its aliases) are already recorded in WP-1003's `### Inherited`.

## Non-goals

- No HTTP surface (WP-1008), no text format (WP-1009), no widgets.
- No new refinement semantics: the verbs mutate the table and record history
  nodes; they never touch a compiled model mid-run (frozen-per-stage
  discreteness is not this WP's to renegotiate).
- No structure/instrument object editing (WP-1014 owns that server-side).

## Tasks

- [ ] `schemas/params.py`: `ParameterRow` — path, value, vary, lo, hi,
      locked, tie, transform, esd. Anti-drift test pins its fields against
      `params.vector.Entry` via `dataclasses.fields`; `esd` is the one
      deliberate extra, asserted as such rather than special-cased silently.
- [ ] `Refinement.parameters() -> list[ParameterRow]`, merging the last
      result's esds; includes fixed/locked/tied entries.
- [ ] `Refinement.set_vary(globs, vary)` + the set-value verb (name decided
      against `NodeAction.api_call`, see Context) — delegate to
      `ParameterTable`, `apply_to_models`, record the reserved
      `set_vary`/`set_value` NodeKinds; test that `api_call()`'s rendered
      string `eval`s back to the same call; locked raises, tied raises naming
      the tie target.
- [ ] `schemas/plan.py`: THE `StageSpec` (incl. `strain_seed`) + `PlanSpec`;
      `schemas/history.py` and `agent.py` re-export from it. Old trees (no
      `strain_seed` key) still validate — test against a vendored old JSONL
      line, plus a new round-trip test proving `strain_seed` now survives
      history (the latent bug above, fixed and pinned).
- [ ] `strategy/staged.py`: `PLAN_INFO` (title, description, intended mode,
      when-to-use) with a membership meta-test against `PLAN_PRESETS`.
- [ ] Tests green + CLAUDE.md data-flow line updated if the public surface
      grew.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_params_surface.py tests/test_history.py tests/test_schemas.py -q
.venv/bin/python -m ruff check src tests examples
```

## References

- WP-0602's registry meta-test pattern (`tests/test_agent_surface.py`) —
  the shape `PLAN_INFO`'s guard copies.

## Handover log

- **2026-07-29** — created from the v1.0 GUI plan. Plan verified against the
  tree the same day: the `api_call` plural/singular mismatch and the
  `strain_seed` history round-trip loss are measured facts, not guesses.

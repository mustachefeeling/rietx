# WP-1004 — Parameter & plan API surface

Milestone: v1.0 · Status: ✅ landed 2026-07-30
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

From the **indexing plan** (WP-1018…1027, added 2026-07-29): a Le Bail-only
phase must carry a **dummy atom** — `Phase._nonempty` raises on an empty atom
list, while `Refinement._run_stage` force-fixes every `.atoms.` path, `.scale`
and `.source.lines.` in lebail/pawley mode (`refine.py:369-380`), so that atom
contributes nothing to the fit. Indexing (WP-1024) constructs such phases
routinely. **The parameter surface must not present that atom as an editable
site** — a user shown `phases.0.atoms.0.biso` on a Le Bail phase will
reasonably try to refine something that is structurally fixed.

## Non-goals

- No HTTP surface (WP-1008), no text format (WP-1009), no widgets.
- No new refinement semantics: the verbs mutate the table and record history
  nodes; they never touch a compiled model mid-run (frozen-per-stage
  discreteness is not this WP's to renegotiate).
- No structure/instrument object editing (WP-1014 owns that server-side).

## Tasks

- [x] `schemas/params.py`: `ParameterRow` — path, value, vary, lo, hi,
      locked, tie, transform, esd. Anti-drift test pins its fields against
      `params.vector.Entry` via `dataclasses.fields`; `esd` is the one
      deliberate extra, asserted as such rather than special-cased silently.
      *(Landed with **two** declared extras — `mode_fixed` joined `esd`, see
      the handover log; the test asserts the set, so both are declared rather
      than tolerated.)*
- [x] `Refinement.parameters() -> list[ParameterRow]`, merging the last
      result's esds; includes fixed/locked/tied entries.
- [x] `Refinement.set_vary(globs, vary)` + the set-value verb (name decided
      against `NodeAction.api_call`, see Context) — delegate to
      `ParameterTable`, `apply_to_models`, record the reserved
      `set_vary`/`set_value` NodeKinds; test that `api_call()`'s rendered
      string `eval`s back to the same call; locked raises, tied raises naming
      the tie target.
- [x] `schemas/plan.py`: THE `StageSpec` (incl. `strain_seed`) + `PlanSpec`;
      `schemas/history.py` and `agent.py` re-export from it. Old trees (no
      `strain_seed` key) still validate — test against a vendored old JSONL
      line, plus a new round-trip test proving `strain_seed` now survives
      history (the latent bug above, fixed and pinned).
- [x] `strategy/staged.py`: `PLAN_INFO` (title, description, intended mode,
      when-to-use) with a membership meta-test against `PLAN_PRESETS`.
- [x] Tests green + CLAUDE.md data-flow line updated if the public surface
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

- **2026-07-30 — landed**, on branch `v1-gui-backend-api` (with WP-1006).
  Acceptance green; fast suite 1145 passed / 4 skipped in ~61 s (was 1116).

  **Done.** All six checklist items. Two decisions and three findings are worth
  carrying:

  - *The plural/singular mismatch is resolved in favour of `api_call`.* The
    public verb is **`set_values({path: value})`**, so `api_call`'s rendering is
    unchanged and the `"set_value"` NodeKind literal — which is persisted in
    every tree ever written — stays as it is. Plural is also the better verb on
    its own merits: a client edits a table, not a cell, and one node per
    keystroke would bury the log. `tests/test_params_surface.py` `eval`s both
    rendered strings onto a *fresh* refinement and compares the resulting state,
    so the log's "this is the equivalent call" promise is executable.
  - *`ParameterRow` has **two** declared extras, not one.* `mode_fixed` joined
    `esd` to answer the inherited Le Bail dummy-atom problem. It is deliberately
    **not** `locked`: nothing is structurally fixed about a phase scale, and
    switching back to `rietveld` frees it — conflating them would have taught
    the GUI a wrong rule. The predicate is exported as
    `refine.mode_fixed_path(path, mode)` and `_run_stage` now calls it, so the
    force-fix set has one definition rather than two opinions.

  **Findings.**

  - **The `strain_seed` loss had a second, worse instance nobody had recorded:
    `NodeAction`.** `cherry_pick` rebuilds a `Stage` from that action, and it
    carried neither `seed` nor `strain_seed` — so a cherry-picked extinction
    stage started on the softplus dead-gradient floor and a cherry-picked
    Stephens stage from the all-zero block, i.e. exactly the two pathologies the
    seeds exist to avoid, silently. Fixed additively (0.0 default = the no-seed
    behaviour, so pre-v1.0 nodes replay unchanged); `api_call` renders the seeds
    only when nonzero, which keeps every existing rendered string
    byte-identical. A test pins both halves. **The general shape: the WP's
    framing was "the spec twins are duplicated and one loses data", but the
    third copy of a stage's arguments is `NodeAction`, and it is the one that
    actually replays.**
  - **Editing a value needed a new table primitive.** `ParameterTable` only ever
    recomputed tied entries inside `commit(θ)`, because until now values only
    changed by decoding a θ. A direct edit has no θ, so setting `a` on a cubic
    phase left `b` and `c` at their old values — silently breaking the symmetry
    the tie exists to enforce. `ParameterTable.refresh_ties()` is that missing
    verb (one pass suffices: `_flatten` resolves onto untied entries).
    `Refinement.merge` mutates entry values the same way and is *not* affected,
    because it writes every path including the dependents — but it is the other
    call site to check if that ever changes.
  - **`min_length=1` on `PlanSpec.stages` could not survive the unification.**
    The agent copy had it, the history copy did not, and the shared schema has
    to read history headers — which are written *before* the first stage runs.
    So the shared schema is permissive and the check moved to
    `agent._RequestBase._known_plan`, where it belongs: it is a statement about
    a request someone is about to spend minutes on, not about a schema.

  **Next / not done here.** Nothing outstanding in this WP. 1005 and 1007 are
  now unblocked and both are named in this file's `### Inherited` chain:
  `ProjectDoc.plan` stores `schemas.plan.PlanSpec` (not a third copy), and
  `capabilities()`'s plans arm reads `PLAN_INFO` rather than restating titles.

  **Gotchas for anyone extending this surface.**

  - `set_vary`/`set_values` record a node **only once the history tree exists**,
    and the tree is created on the first `fit`/`run_stage` because it is pinned
    to its pattern by a fingerprint. Pre-pattern edits change the working state
    and are not logged. WP-1008's session holds a pattern from the start, so it
    can force the tree early if the GUI wants those edits in the log.
  - `parameters()` reads the models' own `vary` flags before the first stage and
    the *recorded* free set after one (`_working_table`). That asymmetry is
    deliberate — an all-fixed listing before a fit would misreport what the
    caller set up — but it means `parameters()` is not a pure function of the
    history head.

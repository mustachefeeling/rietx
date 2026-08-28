# WP-1301 — An unsupported phase is held for the stage, never bounded

Milestone: v1.3 · Status: ⬜
Depends on: — (first of the v1.3 block; opens 13xx)

## Goal

A phase the data cannot see (`phase_support < PHASE_SUPPORT_SIGMA` at stage start)
has its structural parameters held for that stage, its scale stays free so it can
appear, and it is released within the same stage the moment it is seen. The flat
direction costs no iterations; a phase with no reflection in the fitted window is
reported, not silent; nothing changes for a fit with no unsupported phase.

## Context

- **What it costs today, measured.** The 2026-08-26 in-situ ramp run (68 simulated
  patterns, one agent, `refine_sequential`) spent 27 % of its 34.7 min on the CaF₂ cell
  walking a flat direction while the phase was absent. Reproducing the agent's own chain
  on the 13 sub-onset patterns (2026-08-27): with the ±2.5 % cell bounds the agent added
  later, 6.7 s and 1638 iterations with the cell pinned at both bounds and esds of 1e15;
  without them, not finished in 13 minutes (killed). `PHASE_UNCONSTRAINED` fired in 40 of
  68 patterns, i.e. after the cost was paid.
- **Why `cell_window` (WP-1110) does not save it**, read from `params/vector.py:
  cell_window`'s docstring: a finite stored bound suppresses the window on that side, so
  the agent's own bounds switched the safeguard off; and a window bounds the flat
  direction without removing it, so the solver still spends its iteration budget walking
  it. Its docstring already records two earlier agents driving cells to ≈ 39 293 Å and
  ≈ 40 000 Å on a 68-pattern series; the ramp is the third instance, now paid in wall
  clock rather than a crash.
- **The zero-reflection limit is silent on `main`.** A phase whose reflection list is
  empty inside the fitted window is the limit of "unsupported". Measured 2026-08-28 on
  SRM 660c LaB₆ fitted in 22.5-29.5° (data present, no reflection): `converged`, Rwp
  0.334, and the only diagnostic is `DISPERSION_NEGLECTED`; neither `PHASE_UNCONSTRAINED`
  nor any flat-direction finding fires. rietx 1.0.1 crashed on this state with an opaque
  einsum error; a contributor's campaign brief (2026-08, 86 runs) spent a paragraph
  telling its agents to work around it by hand. The crash is gone, the silence is not.
- **Seam.** `src/rietx/refine.py` `_run_stage` (`:1139-1181` at 79e5ae82; re-read on
  arrival): after `compile_model` (`moving_paths` is then a *superset* claim, the safe
  direction), measure `new_model.phase_support(table.decode(table.x0()))`; for each phase
  below σ, `held = {p in freed if p.startswith(f"phases.{ip}.") and not
  p.endswith(".scale")}`; `table.set_vary(held, False); freed -= held`, exactly the
  `mode_fixed_path` drop at `:1162-1171`. After the solve, re-measure support at the
  solution; a held phase now ≥ σ gets **one** second solve of the same stage with its
  hold lifted (bounded: never a third). `_freeze_cell_windows`
  (`optimize/least_squares.py:833-850`) then finds no free cell to window on a held phase;
  it stays for the joint path (`multi.py`) and is otherwise untouched. One authority:
  `CompiledModel.phase_support` (`model/forward.py:1358`), as its docstring demands.
- **Alternatives rejected.** (i) Hold only when the phase's scale is not free this
  stage: misses `refit="single"`, where `_collapse` frees scale and cell together, the
  ramp's own case. (ii) Widening `cell_window`: measured not to work (above). (iii) Hold
  and tell the caller to rerun: moves the cost to another API call, which is the
  currency being saved.
- **Record it.** New `StageResult.held: list[str]` (a declared name needs its writer,
  CLAUDE.md § Invariants: written in `_run_stage`, pinned set-equal to the hold in a
  test, documented in `docs/manual/using/results.md`). `PHASE_UNCONSTRAINED` keeps its
  code and meaning (the data cannot see this phase); its message says what happened
  ("its N structural parameters were held for stages a, b", "released in stage c after
  its scale rose to Xσ", or "no reflection of phase N lies in the fitted range"), `where`
  lists the held paths, `value` stays the support. `SEQUENTIAL_PERSISTENT_FINDING`
  aggregates it unchanged (`sequential.py:1134-1201` is code-agnostic). Event `data`
  gains `held`/`released` on `stage_start`/`stage_end` (open dict, no
  `EVENT_SCHEMA_VERSION` bump). `SCHEMA_VERSION` 0.9 → 0.10 for the new field, comment
  beside the constant.
- **Evidence for the agent.** The plan of record (maintainer's memory
  `v1-3-agents-and-programs-plan`) and the audit of the ramp run
  (`agent-surface-audit-insitu-ramp`); the raw run at
  `~/rietx-agent-runs/2026-08-26-insitu-ramp/` with `agent_call.txt` (the exact call).

### Inherited

Nothing yet.

## Non-goals

Per-iteration re-anchoring (TOPAS's shape; unavailable under scipy's fixed bounds).
Removing `cell_window`. Any change to `PHASE_SUPPORT_SIGMA`. Deciding *whether* a phase
is present (that is `SEQUENTIAL_PERSISTENT_FINDING`'s and the agent's).

## Tasks

- [x] `StageResult.held` + the hold in `_run_stage` + the diagnostic message; goldens
      bit-identical (`tests/test_golden*.py`: no unsupported phase → no hold).
- [x] The zero-reflection case: the LaB₆ 22.5-29.5° window asserts the diagnostic and
      the hold.
- [x] The release rule (second solve) + event fields; test: a phase appearing mid-series
      is refined in the pattern where it appears, not one later (synthetic: the ramp's
      generator at N = 13 straddling the onset, regenerated in-test from
      `tests/data/cod_1000236.cif`).
- [x] The runaway guard test (`slow`): the ramp's 13 sub-onset patterns through the
      agent's exact call, no user bounds; wall clock under a runaway guard (60 s),
      `n_iterations` against the bounded baseline (1638); and cpd-1c (`cell_window`'s
      docstring case) unchanged: a *supported* phase is never held.
- [x] `lebail`/`pawley` and the joint path: the same rule (an absent phase's cell is flat
      in every mode); tests.
- [ ] Docs: `using/results.md` (`held`), `using/series.md` (what a held phase looks like
      in a chain), `help.py` entry if a name is added, the protocol/skill row for the
      changed message.
- [ ] Tests + obs/calc/diff PNGs to `tests/output/`.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_absent_phase.py tests/test_held_phase.py tests/test_sequential*.py -n auto --dist loadgroup
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"   # count moves by exactly the tests added
.venv/bin/python -m ruff check src tests examples
```

The ramp reproduction under 60 s; goldens unchanged; full suite once on the final tree.

## References

- WP-1110 (`cell_window`, `phase_support`, `PHASE_UNCONSTRAINED`); WP-1051
  (quarantine); WP-1127 (the first rung's budget).
- McCusker, Von Dreele, Cox, Louër & Scardi (1999), *J. Appl. Cryst.* **32**, 36-50, §9
  (what the data can support).

## Handover log

- **2026-08-28** — created, from the parked v1.3 plan.

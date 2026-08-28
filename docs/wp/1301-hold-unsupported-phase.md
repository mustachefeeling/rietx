# WP-1301 — An unsupported phase is held for the stage, never bounded

Milestone: v1.3 · Status: ✅ 2026-08-28 — held, put back and released; the ramp's 13 sub-onset patterns need no user bound and report no cell
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
- [x] Docs: `using/results.md` (`held`), `using/series.md` (what a held phase looks like
      in a chain), `help.py` entry if a name is added, the protocol/skill row for the
      changed message.
- [x] Tests + obs/calc/diff PNGs to `tests/output/`.

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

### 2026-08-28 (2nd session) — Held, put back, and released

A refinement no longer spends its budget on a phase that is not in the
specimen, and no longer reports a number for it. Where the fit measures that a
phase contributes less than 1σ anywhere in the pattern, the stage holds every
structural parameter of it and leaves its scale free — the one direction that
is not flat, and the only way the phase can come back. A caller gets the value
they supplied rather than wherever a flat walk stopped, `PHASE_UNCONSTRAINED`
names the parameters and the stages that held them, and the held rows are
absent from `RefinementResult.parameters` because nothing measured them. On a
series that means a phase appearing part-way through has a trajectory that
*starts at the onset* instead of running the whole way over values that were
never measurements (`Trajectory.x`: 2 points of 4 on the straddling fixture).

The WP as filed covered only the phase that is invisible when the stage
starts, and that is not the case the in-situ ramp hit. `phase_support`
measures the *modelled* contribution, so CaF₂ seeded at scale 1e-4 — how the
agent seeded it for all 68 patterns — is well above the noise at stage start
whatever the specimen holds; nothing is held, and the flat direction opens
only as the solver drives that scale to nothing. So support is re-measured at
the answer as well, and it moves both ways: a held phase that has *appeared*
is released and the stage re-solved (the pattern where a phase first appears
is the one an operator reads), one that has *collapsed* is put back where the
stage found it and held. One extra solve covers either, never a third. The
restore is licensed by the measurement that licensed the hold: under 1σ a
phase contributes under 1σ wherever its peaks sit, since the peak height is
`scale·|F|²·profile` and the cell only moves them.

**Done** — all seven checklist items; the WP closes. `StageResult.held` and
`.released` (`SCHEMA_VERSION` 0.10 → 0.11); the hold and both post-solve arms
in `refine._run_stage`; `CompiledModel.phase_line_counts` for the zero-line
limit; `PHASE_UNCONSTRAINED` rewritten to say what was done, and now firing
for a single-phase model, which it never did; `held`/`released` on
`stage_start`/`stage_end`, with a **second `stage_start`** before a resumed
solve so `eval.values` keeps its declared alignment with
`stage_start.free_paths`; the same rule in `lebail`/`pawley` and in `multi.py`
under the joint authority (below σ in *every* histogram) plus the
`PHASE_UNCONSTRAINED` the joint path never had.
`_phase_support_diagnostics` now takes the measured arrays rather than a
model, so the two callers quote one implementation. Docs:
`using/refining.md` (the fields — `results.md` does not carry `StageResult`),
`using/series.md` (a phase that appears part-way through), `using/model.md`
(what the cell window is still for), both AGENT_PROTOCOL rows, and CLAUDE.md's
flat-direction invariant rewritten in place at its cap. v1.3 opened with the
version bump and `milestones/v1.3.md`.

**Measured** — the 13 sub-onset patterns of the ramp, the agent's exact call,
2251 points, macOS/arm64, `[dev]` venv:

| arm | wall | iterations | worst \|a − 5.4631\| |
|---|---|---|---|
| main, the agent's own bounds 5.30-5.60 | 2.8 s | 1342 | 0.163 Å (on a bound) |
| main, no bounds | 5.3 s | 2164 | 14.88 Å |
| hold at stage start only | 3.1 s | 927 | 11.96 Å (one at −6.49 Å) |
| + the collapse rule (shipped) | 3.5 s | 1669 | 0 |

The shipped arm needs no user bound at all, holds every CaF₂ cell at the
declared 5.4631 Å and fires no `HIGH_CORRELATION`. It costs 742 iterations
more than the start-of-stage hold alone, which is the price of not reporting a
cell of 20.3 Å with an esd of 1e24. The WP's remembered 1638 is another
machine's *bounded* number; this one measures 1342 bounded and 2164 unbounded
one flag apart, and the test asserts against the unbounded one because the
point is that no bound is needed.

Beside that: on one pattern where CaF₂ *is* present, seeded truthfully at
5.4631 Å in the collapsed single stage, main returns 5.6390 Å at Rwp 0.194 —
the cell wanders while the scale is still 1e-7 and never recovers — against
5.46301 Å at Rwp 0.055 here; from a 1.2 % wrong seed, main takes 400
iterations to 5.46313 Å and this takes 37 to 5.46303 Å. A four-pattern chain
straddling the onset: 549 iterations → 68, the two patterns above the onset
agreeing with main to 1e-5 Å. cpd-1c holds nothing in any of its eight stages.
Counts (this venv, this platform): fast suite 3216 → **3252 passed, 122
skipped** (+36: 31 fast tests in `tests/test_held_phase.py`, which has 35 of
which 4 are `slow`, plus 5 parametrised rows from the new validation-matrix
claim), 124-173 s across runs; the WP's own selection 123 passed in 29.8 s;
bit-identity goldens green. Full suite: FULL_SUITE.

**Gotchas for a successor** — (i) the hold lives in the table until the *next*
stage lifts it, because the free set a stage ends with is the set its solve
used and the esd map, the guard and `n_free` are indexed by it;
`_record_free_paths` is what stops it leaking into the state a checkout
restores, and `test_a_later_stage_re_decides_the_hold_rather_than_inheriting_it`
is what proves the lift (it went missing in `multi.py` and nothing was red).
(ii) A released or collapsed stage solves twice and the record is one stage:
the second solve's status, the first's `cost_initial`, both solves'
iterations. (iii) Le Bail and Pawley answer the same question differently and
that is the measurement, not a bug — their per-hkl intensities are fitted, so
an absent phase takes a share of what lies under its peaks; only the zero-line
case holds there. (iv) xdist **unions** every `xdist_group` mark on an item
rather than taking the closest, so a per-test group on a file that already
carries one at module level makes a third group and re-runs a shared fixture
on another worker; that is why the cpd-1c counter-example lives in
`test_acceptance_qpa_roundrobin.py`.

**Not done, deliberately** — per-iteration re-anchoring (the WP's non-goal,
and the only thing that would remove the *first* solve's wasted iterations:
400 of them on one ramp pattern before the collapse is detectable). A cell
length still has no absolute floor outside `cell_window`, which applies to
unsupported phases only, so a phase that stays supported can in principle
still be driven somewhere unphysical; this WP removes the case that produced
those here, and a general floor is a separate measurement that would have to
clear the goldens.

**Next** — WP-1302, the termination view. Nothing is owed back to this WP.

- **2026-08-28** — created, from the parked v1.3 plan.

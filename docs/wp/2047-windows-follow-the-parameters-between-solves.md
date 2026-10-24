# WP-2047 — Windows follow the parameters between solves

Milestone: unscheduled · Status: ⬜
Track: What fires, and what stays silent
Depends on: 2045 (the trigger it removes first); 2017 soft (the families this is measured on)
Priority: P3 2026-10-24 — down a rung from P2: 2045 removes the one trigger measured, and the sink it leaves has no second known case

## Goal

No stage ends at an answer that exists only in its frozen discretisation. A
stage's peak windows and FCJ node counts still stay frozen within each solve.
Between solves, they follow the parameters: a stage whose windows have gone
stale recompiles and solves again. It converges only on a solve that needed
no recompile. The four acceptance standards' answers move by a measured,
stated amount or not at all.

## Context

**The sink.** Each stage freezes its windows at the values it starts from
(root CLAUDE.md § Invariants, the first). When a parameter that widens peaks
grows during the solve, the part of each peak outside its frozen window
drops out of the model. That parameter can be the axial ratios or the
widths. Its growth then removes intensity, a direction the physics does not
have. Where the start's scales are too strong, that direction lowers χ² on
the frozen model.

**Measured by WP-2045's ruling session** (2026-10-24, Linux x86-64 cloud
container, 4 cores, `[dev]`, Python 3.12, `OPENBLAS_NUM_THREADS=1`; the
runs are in WP-2045's Context, the probes in that session's scratchpad).
The case is the hostile series' cpd-1a → cpd-1b
(`tests/test_acceptance_sequential.py`, `chained_all`):

- cpd-1b's warm stage ends "converged" at `axial_sl` 555, `w` 0.27 and `v`
  −5.5. Its frozen model reads Rwp 0.760. A fresh compile at the same values
  reads 1.29, and the stage started at 1.75.
- At that answer, the frozen windows drop 73.4 % of the Bragg intensity that
  a fresh compile computes, and χ²(fresh)/χ²(frozen) is 3.27. On every
  declared stage of cpd-1a's fit the same measure is 0.00-1.32 %, with a χ²
  ratio of 0.94-1.00.
- The same warm fit split into short stages, each of which recompiles
  (closing stage off):

  | recompile every | outcome |
  |---|---|
  | 10 iterations | Rwp 0.142, `axial_sl` 0.0077, 11 s |
  | 3 iterations | the same answer, 25 s |
  | 50 iterations | worse: `axial_sl` 4 041, zincite's scale 0, Rwp 0.779 |
  | never (one frozen stage at `ftol` 1e-9) | Rwp 0.196 |

  The independent fit of cpd-1b gets 0.137.
- From the runaway answer, a re-solve on fresh windows does not come back:
  at `ftol` 1e-6 it reaches `axial_sl` 4 114 and Rwp 0.782; at 1e-9 it
  reaches 4 100 and hits its 400-evaluation cap. So the windows must follow
  while the stage is still near where it started. A check after the stage
  can refuse the answer, but cannot repair it.

WP-2045 removes the trigger measured there: the warm stage stopped on the
sink because it ran at `intermediate_ftol`. It does not remove the sink.
This WP is option 4 of WP-2045's candidates, ruled out of 2045 and into its
own WP by the maintainer on 2026-10-24 ("5 now, 4 as own WP").

**Why the freeze, and what was never measured.** The freeze dates from v0.1.
DESIGN.md rule 1 gives as its reason "window membership depends on refined
cell/zero parameters and creates gradient bias", which the record never
measured. WP-2002's sixth-round brief adds a second reason: a point entering
or leaving a window between two evaluations steps χ², and derivatives cannot
see the step. A recompile between solves keeps both safe, because no solve
ever sees a window move. Two parts are open:

- the stopping rule. A stage that recompiles must not call itself converged
  on a solve that moved its windows.
- the history record. A stage that recompiled is several compiles, and
  `StageResult`/`NodeAction` record one `window_area_tol` and one compile per
  stage today, which `replay` and a cherry-pick read.

**Practice** (`docs/practice.md` § How far a peak is computed and §
Staging). TOPAS rebuilds its peak buffer when a width moves past a set
tolerance. GSAS-II, MAUD, RIETAN-FP and EasyDiffraction recompute their
windows at every evaluation. FullProf holds its windows for a whole run, as
rietx holds them for a stage. No program's manual states what its rule costs
in accuracy.

**Files.** `refine.py` (`Refinement._run_stage`, where a stage compiles and
solves), `model/forward.py` (`compile_model`'s window and FCJ sizing, and
where a staleness measure would be computed), `strategy/staged.py`
(`stage_ftols`, the closing stage), `schemas/results.py` (`StageResult`),
`schemas/history.py` (`NodeAction`).

## Non-goals

- Windows that move at every evaluation (WP-2045's option 7). That drops
  the frozen-per-solve invariant itself.
- The peaks buffer, shape reuse across reflections for speed. That is fenced
  to v2 with FPA (root CLAUDE.md, the backends paragraph; WP-1122).
- Restoring an axial ceiling, which B9 never named (WP-2045's Context, How
  the rounds missed it). That is a ruling of its own if it is wanted.

## Tasks

- [ ] The staleness test: what a stage measures between solves, at what
      cost, and its threshold. Two candidates were measured on one family:
      intensity dropped by the frozen windows, and the χ² ratio fresh/frozen.
      The threshold gets an `_audit` row (root CLAUDE.md § Every heuristic
      has a row), since tier 3 on one family is all that is known.
- [ ] The design, put to the maintainer. It covers the stopping rule, what
      the history records for a stage that recompiled, and whether the
      closing stage stays: its start-dependence half may be what this
      removes.
- [ ] Measured on the four acceptance protocols (SRM 660c LaB6, the
      fluorapatite tutorial, cpd-1a, 11-BM NAC) and on `chained_all`: time
      and answer shift against the shipped tree, in the shape of WP-2002's
      eighth-round table
- [ ] The implementation, its record field and its `_audit` row
- [ ] Tests: the hostile series' warm stage does not run away with the
      intermediate tolerance restored, and a stage that recompiled is
      recorded and replayed as what it ran
- [ ] Skill and manual: `reference/refinement.md`'s staging section, and a
      reference row only if a field or code is new

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_acceptance_sequential.py -n 4 --dist loadgroup
.venv/bin/python -m pytest tests/test_staged_start_invariance.py -n 4 --dist loadgroup
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
```

The hostile series' warm stages converge without running away at the
shipped tolerances. The four standards move by no more than the bar the
design brief states.

## Handover log

- **2026-10-24** — filed by WP-2045's ruling session, on the maintainer's
  ruling ("5 now, 4 as own WP"). No open WP owns window rebuilding:
  2017 measures tier-3 thresholds and does not change the window rule, and
  1122's v2 fence covers shape reuse, not when a window is rebuilt. Next:
  the staleness test, then the design brief.

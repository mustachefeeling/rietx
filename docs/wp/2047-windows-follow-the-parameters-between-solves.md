# WP-2047 — Windows follow the parameters between solves

Milestone: unscheduled · Status: 🔄 2026-10-25 — claimed by @yue-here
Track: What fires, and what stays silent
Depends on: 2045 (the trigger it removes first); 2017 soft (the families this is measured on)
Priority: P3 2026-10-24 — down a rung from P2: 2045 removes the one trigger measured, and the sink it leaves has no second known case

## Goal

No stage ends silently at an answer that exists only in its frozen
discretisation. Each stage measures, at its answer, how much Bragg intensity
its frozen windows drop against windows sized at that answer, records it,
and reports a stage whose loss exceeds its own window tolerance. Then a
prototype of windows recomputed at every evaluation is measured, to decide
whether rietx adopts the practice of GSAS-II, MAUD, RIETAN-FP and
EasyDiffraction. The four acceptance standards' answers do not move.

(Rewritten 2026-10-25 on the maintainer's ruling, Context § The ruling. The
goal as filed was a recompile between solves.)

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
runs are in WP-2045's Context, the probes in
[`2045-batch/`](2045-batch/README.md)).
The case is the hostile series' cpd-1a → cpd-1b
(`tests/test_acceptance_sequential.py`, `chained_all`):

- cpd-1b's warm stage ends "converged" at `axial_sl` 555, `w` 0.27 and `v`
  −5.5. Its frozen model reads Rwp 0.760. A fresh compile at the same values
  reads 1.29, and the stage started at 1.75.
- At that answer, the frozen windows drop 73.4 % of the Bragg intensity that
  a fresh compile computes, and χ²(fresh)/χ²(frozen) is 3.27. On each of
  cpd-1a's eight declared stages and its closing stage, the same measure is
  0.00-1.32 %, with a χ² ratio of 0.94-1.00.
- The same warm fit split into short stages, each of which recompiles
  (closing stage off; times are one run each, orders of magnitude only):

  | recompile every | outcome |
  |---|---|
  | 10 iterations | Rwp 0.142, `axial_sl` 0.0077, about 10 s |
  | 3 iterations | the same answer, about 25 s |
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

**The tier of each rule this WP adds** (written 2026-10-25 by the session
that started it; revised after the ruling). The report is of DESIGN §
Rules' third kind: the data cannot rank a remedy here, so the stage reports
the number with its meaning and acts on nothing. Its threshold is no new
number. It is the stage's own `window_area_tol`, the area the compile
already allows each window to drop, so `lost` above it means the frozen
windows drop more than the whole allowance. Its separation is measured on
one family (normal stages at most 1.73 % against the 2 % tolerance and 2e-5
against the closing 1e-3; the hostile stage 73-99 %).

**Files.** `refine.py` (`Refinement._run_stage`, where a stage compiles and
solves), `model/forward.py` (`compile_model`'s window and FCJ sizing, and
where a staleness measure would be computed), `strategy/staged.py`
(`stage_ftols`, the closing stage), `schemas/results.py` (`StageResult`),
`schemas/history.py` (`NodeAction`).

**What WP-2045's option 5 left** (folded from `### Inherited` 2026-10-25;
PR #1161). `RefinementPlan.stage_ftols` gives the last declared stage 1e-9 when a closing stage follows. On the hostile pair cpd-1b's warm stage reaches `axial_sl` 0.0082 at Rwp 0.1398 (macOS arm64), against 0.142 for your recompile-every-10-iterations probe and 0.137 for the independent fit, so a recompiling scheme still has about 0.003 in Rwp to find on this case. The frozen-window sink itself is untouched: a stage that converges into it at 1e-9 would still hand the closing stage a runaway, and no second case is known. The new slow test `test_the_hostile_pairs_warm_stage_stops_short_of_the_runaway` fails at once on any closing compile above `axial_sl` 1, so it guards your change too. Option 5's cost table (1.04-1.07× evaluations, no answer moved on the four protocols) is in WP-2045's Context.

**The axial zero case, #774** (folded from WP-1421's `### Inherited` entry
2026-10-25; re-check it by the maintainer's instruction, last task). The case was ruled (c), documented: with both axial ratios at exactly zero and either free, the compile sizes the windows and the FCJ nodes as if each were `forward.AXIAL_SIZING_FLOOR` (0.02), so `predict()` differs from the same model held at zero by 4.8e-5 of the strongest peak (the issue's rutile reproducer). Sizing every zero model at the floor (option a) made the gap exactly 0 and a default fluorapatite `mccusker_default` fit 2.0× slower (0.64-0.71 s → 1.32-1.35 s, `[dev]`, darwin/arm64). The floor does two jobs: a live derivative column at zero (the nodes) and room for the tail the stage grows (the windows). The 4.8e-5 is the windows' job. Once windows follow the parameters between solves, that job is this WP's, so a model at zero could size its nodes from the free set and its windows from its value, which may close the gap at no cost. Unmeasured: check that free and held curves at zero then agree, and that the derivative column at zero stays correct (`test_cross_backend.py`'s axial rows). `forward.MAGNETIC_SIZING_FLOOR` has the same zero-case shape (`forward.py:4008-4013`), unmeasured; check it in the same pass. The sentence to update if the gap closes is in `help.py`'s `axial_sl`/`axial_hl` entries and `Refinement.predict`'s docstring; `docs/practice.md` § Axial divergence at zero has the survey. A second point for your acceptance: WP-1421 re-measured the closing stage against one more empty stage on the fluorapatite tutorial (0.00 % under `mccusker_default`, 9.26 % with `closing_window_tol=None`), and a hand-run `run_stage` has no closing stage, so it keeps that gap. That is your sink at the size of one stage.

**The staleness test, measured** (2026-10-25, macOS arm64, `[dev]`, Python
3.12, `OPENBLAS_NUM_THREADS=1`, on `main` at `28c88711d`; probes in
[`2047-batch/`](2047-batch/README.md)). Three candidates, asked at every
stage's answer (probe 1) and at every accepted LM iteration of every stage
(probe 3), on the four acceptance protocols and on the hostile pair under the
pre-WP-2045 schedule, which still runs away on this tree (`axial_sl`
0.036 → 558).

| Candidate | Normal stages, any iteration | Hostile warm stage | Cost of one check |
|---|---|---|---|
| `lost`: Bragg intensity the frozen windows drop, against a fresh compile | ≤ 1.73 % (LaB6's `profile` stage at its first iteration; cpd-1a's 1.35 %); every other stage ≤ 0.1 % | 93 % at the first accepted iteration; never below 73 % after it | one compile, 4-17 ms, plus two Bragg evaluations |
| χ²(fresh)/χ²(frozen) | 0.94-1.07 | 180 at the first solve's first iteration, but 1.02 at the second solve's first, where `lost` is 77 % | the same compile |
| The pseudo-Voigt area outside each frozen window, from the frozen model alone | rises ≤ 3 % above its value at the compile, which is 0.5-1.9 % | catches the first solve's cell jump (99.9 %); reads 2.5 % at `axial_sl` 558, where `lost` is 73 % | 0.1-0.3 ms |

Three findings carry into the design:

- **The hostile stage goes stale at its first step, not by drift.** The
  first accepted trial of cpd-1b's warm stage moves corundum's cell +8.2 %
  (4.7585 → 5.15 Å), its scale ×165 and two Biso to 0. The answer it
  converges to then collapses a phase, and the stage's second solve, on the
  same frozen model, carries `axial_sl` to 558. Any threshold from 0.5 % to
  50 % fires at the first iteration. A check only at a solve's end is
  therefore late, which is WP-2045's "a check after the stage can refuse the
  answer, but cannot repair it".
- **Only `lost` separates both halves.** The χ² ratio misses the second
  solve, where both models fit equally badly. The pseudo-Voigt estimate is
  blind to the axial tail, which is the documented sink. The cheap
  estimate is ruled out as the test; it could only screen for position jumps.
- **The window tolerance is a natural threshold.** A declared stage's
  windows are compiled to drop at most `WINDOW_AREA_TOL` (2 %) of each peak.
  `lost` > that tolerance means the frozen windows drop more than a fresh
  compile by more than the whole allowance. No normal stage reaches it at any
  iteration (largest 1.73 %, a margin of 1.16×); the hostile stage exceeds it
  37-46×. Half the tolerance (1 %) fires on two normal `profile` stages, both
  at their first iteration. A false alarm costs one compile and a re-solve; a
  miss costs the sink.

A fresh compile costs 4-17 ms against whole fits of 0.6-3.4 s here, with
8-12 compiles a fit (probe 1). One check per stage end would add about
5-15 % to these short fits unless it reuses the next stage's compile, which
is at the same values; one per iteration would add about 50 %.

**Two rules, emulated** (probe 4, same machine and tree; 2026-10-25). Each
wraps the solver so a stage's solve becomes several solves, with a fresh
compile between two of them when `lost` exceeds the compile's own window
tolerance. `end` checks when a solve ends and re-solves, at most five times.
`chunkN` solves N iterations at a time and checks between chunks. The
emulation sits inside the solver call, so the stage's phase-collapse check
still runs after it, on the last model.

| Rule | cpd-1b, pre-2045 schedule | cpd-1b, shipped schedule | Four protocols: evaluations against shipped |
|---|---|---|---|
| shipped | runs away, `axial_sl` 558 | Rwp 0.1398, `axial_sl` 0.0082, 312 evaluations, 6 s | — |
| `end` | Rwp 0.1398, `axial_sl` 0.0082, 170 evaluations, 207 s | over 300 s, aborted | 1.00× on all four; no recompile |
| `chunk10` | runs away, `axial_sl` 4.8 | runs away, `axial_sl` 7.9 | 1.00-1.02×; no recompile |
| `chunk3` | Rwp 0.1398, `axial_sl` 0.0082, 118 evaluations, 5.6 s | Rwp 0.1398, `axial_sl` 0.0082, 145 evaluations, 7.1 s | 1.00-1.10× (cpd-1a 193 against 175); no recompile |

No rule recompiled any stage of the four protocols. Every answer stayed
within 0.001 esd of shipped. Wall time on them rose 2-47 %, mostly the
probe's own fresh compile per check; the first three families ran while the
machine was swapping, so those seconds are rough.

- **`end` rebuilds at the runaway, and that model is enormous.** Under the
  shipped schedule the warm stage's first solve converges after 230
  iterations with corundum's *a* at 41.04 Å (from 4.76). `lost` there is
  99.93 %, and the fresh compile has 354 million window points against
  68 thousand, which paged the machine. The shipped stage survives that
  answer because the collapse check restores the phase and solves again; the
  `end` rule compiled before the collapse check could act. A real
  implementation would check after the support step, but the old schedule's
  second solve also ends at `axial_sl` 558, where `end` paid 207 s.
- **`chunk3` works by catching the first step.** Its one recompile is at
  iteration 3, after the cell jump of 4.76 → 5.15 Å, while the model is
  still near where it started. The stage then never collapses, so the
  second solve's axial jump never happens. `chunk10` checks too late.
  The chunk size is therefore a tuned number whose margin is unknown: 3
  works and 10 fails, on one case.
- **The emulated check is wrong on a Le Bail stage unless it carries the
  extracted intensities** (`refine._carry_lebail`); without them NAC's
  first stages read 41-47 % lost and recompiled at the cap.

**The ruling** (maintainer, 2026-10-25, "go" on the session's proposal).
Four options were put: report a stale stage (1), recompile every N
iterations (2), check every accepted step and recompile on a trip (3), and
nothing (4). A check at each solve's end was out in all of them, since it
recompiles at the runaway. The maintainer then asked about windows
recomputed at every evaluation, which this WP had listed as a non-goal. The
session's view was that this is the right end state, since it removes the
sink rather than detecting it and matches four of the five programs
surveyed. Two costs are unmeasured. The residual steps by a tail value
whenever a window edge crosses a point, and whether LM still meets `ftol`
1e-9 is unknown; GSAS-II's windows run 50 FWHM below a peak and 75 above
(`GSASIIstrMath.py:4071-4077` in 5.8.4, read this session), where rietx's
reach about 16 FWHM of a Lorentzian at the 2 % tolerance. And the frozen
layout is built into the compiled kernels, the batched forward, the
derivative bases and jax's static shapes. Ruled: option 1 now, then a
prototype of per-evaluation windows, measured before anything is adopted.
Options 2 and 3 are dropped, since adoption would make them throwaway.

## Non-goals

- Recompiling between solves within a stage (options 2 and 3 of the
  ruling). Dropped for the prototype.
- The peaks buffer, shape reuse across reflections for speed. That is fenced
  to v2 with FPA (root CLAUDE.md, the backends paragraph; WP-1122).
- Restoring an axial ceiling, which B9 never named (WP-2045's Context, How
  the rounds missed it). That is a ruling of its own if it is wanted.

## Tasks

- [x] The staleness test: what a stage measures between solves, at what
      cost, and its threshold. Two candidates were measured on one family:
      intensity dropped by the frozen windows, and the χ² ratio fresh/frozen.
      The threshold gets an `_audit` row (root CLAUDE.md § Every heuristic
      has a row), since tier 3 on one family is all that is known.
- [x] The design, put to the maintainer (Context § Two rules, emulated, and
      § The ruling). Ruled 2026-10-25: report now, then the per-evaluation
      prototype.
- [ ] `forward.rewindow(model, values)`: a copy of a compiled model whose
      windows and FCJ node counts are sized at `values` on its frozen
      reflection list, without a compile. Its agreement with a fresh compile
      and its cost are measured on the four protocols.
- [ ] The report: each stage measures `lost` at its answer through
      `rewindow`, records it in a `StageResult` field and its `NodeAction`
      twin, and raises a diagnostic above the stage's own
      `window_area_tol`. Its `_audit` row, and its cost on NAC, the
      shortest fit, against the per-stage budget (root CLAUDE.md, a
      per-stage charge)
- [ ] Tests: the hostile pair under the pre-2045 schedule raises the
      diagnostic; the four protocols do not; the field round-trips through
      history
- [ ] Skill and manual: the diagnostic's reference row and
      `reference/refinement.md`'s staging section
- [ ] The prototype: windows recomputed at every evaluation on the numpy
      path, on the hostile pair under the pre-2045 schedule and the four
      protocols: answer shift in esd, evaluations, time, and whether LM
      still meets `ftol` 1e-9. Then a brief to the maintainer: adopt, and
      at what cost, or not
- [ ] #774's zero case (Context, The axial zero case): with windows sized
      from the value and nodes from the free set, measure whether free and
      held curves at zero agree and the axial derivative rows still pass;
      the same pass for `MAGNETIC_SIZING_FLOOR`; update `help.py` and
      `Refinement.predict`'s sentence if the gap closes

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_acceptance_sequential.py -n 4 --dist loadgroup
.venv/bin/python -m pytest tests/test_staged_start_invariance.py -n 4 --dist loadgroup
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
```

The hostile pair under the pre-2045 schedule raises the stale-window
diagnostic, and the four standards raise none and move not at all. The
report costs NAC, the shortest fit, no more than the per-stage budget, or
the excess is stated. The prototype's measurements and the brief that
follows them are in the Context.

## Handover log

- **2026-10-24** — filed by WP-2045's ruling session, on the maintainer's
  ruling ("5 now, 4 as own WP"). No open WP owns window rebuilding:
  2017 measures tier-3 thresholds and does not change the window rule, and
  1122's v2 fence covers shape reuse, not when a window is rebuilt. Next:
  the staleness test, then the design brief.

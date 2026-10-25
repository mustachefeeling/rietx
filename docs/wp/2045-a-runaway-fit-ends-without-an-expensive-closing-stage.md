# WP-2045 — A runaway fit ends without an expensive closing stage

Milestone: unscheduled · Status: 🔄 2026-10-25 — claimed by @yue-here
Track: A long run is not one fit
Depends on: —
Priority: P2 2026-10-24 — a defect that costs a user a workaround: a fit that runs away now seems to hang, where 1.9.0 ended it in seconds; 1.10.1 waits on it

## Goal

The stage before a plan's closing stage converges at the solver's tolerance,
so it does not stop on the frozen-window plateau measured below and hand
the closing stage a runaway to compile (ruled 2026-10-24, option 5). The
hostile series in `tests/test_acceptance_sequential.py` (`chained_all`)
finishes on every platform. The nightly `full` job completes inside its
150-minute limit again. What the change costs the four acceptance standards
is measured and stated.

## Context

**What happens, measured 2026-10-24 by WP-2043** (macOS arm64, `[dev]`, the
1.10.0 release tree; the probe is described under Acceptance). The hostile
series carries every parameter, the phase scales included, from one IUCr
round-robin mixture to the next (cpd-1a → cpd-1b is a large swing in phase
fractions). On cpd-1b the warm attempt's one declared stage ends "converged"
at Rwp 0.760 with these values:

- `instrument.geometry.axial_sl` 557.8. Until 1.10 it had a ceiling of 0.2,
  and real instruments sit near 0.01-0.05.
- `instrument.profile.v` −5.64 deg².
- zincite's oxygen Biso 25 Å².

Then `run_stages()` appends the closing stage (WP-2002), which recompiles at
that answer with windows dropping 1e-3 of each peak (`CLOSING_WINDOW_TOL`)
and the finer axial node rule. At this answer:

| | corundum's window points | FCJ nodes, max | point-nodes per evaluation |
|---|---|---|---|
| cpd-1b's declared stage (2 % windows) | 45 035 | 13 | 352 785 |
| cpd-1a's closing stage, a normal one | 613 003 | 22 | 6 307 023 |
| cpd-1b's closing stage, at the runaway answer | 850 103 (every window is the whole 7 251-point pattern) | 1 024 | 544 128 502 |

So one evaluation of corundum alone costs about 1 500× the declared stage's
and 86× a normal closing stage's. WP-2043's lane saw it spend over 50
CPU-minutes in that closing stage without finishing. The series would have
rejected the attempt anyway (Rwp 0.760 is far outside its fence) and
escalated to the next rung, but only after the closing stage returns.

**When it started.** A snapshot just before #1085 (WP-2002's merge,
`2330afc02`) runs both patterns in 3.1 s, and its warm stage converges at
Rwp 0.139. The nightly `full` job took about 95 minutes on 2026-10-21 and
2026-10-22, and hit its 150-minute `timeout-minutes` on 2026-10-23 and
2026-10-24, the first two nightlies after #1085 merged (2026-10-22 22:30).
WP-2037's local slow run stalled on the same test the same day.

**Two changes of #1085 combine.** (1) WP-2002 B9 removed the limits chosen on
quantities where the model stays defined; `axial_sl` and `axial_hl` lost
their 0.2 ceiling (the 1.10.0 notes, Numbers that move). That was a
maintainer ruling. It is why this warm stage can walk the ratio to 557.8
instead of stopping on a bound, and this WP does not reopen it. (2) The
closing stage polishes whatever the declared stages hand it, and nothing
asks whether that answer is worth polishing or what the polish costs.

**With the closing stage off, nothing runs away** (same probe,
`closing_window_tol=None` on `qpa_plan()`, 2026-10-24). All eight patterns
finish in 9.2 s, each kept on its warm rung, and cpd-1b's warm stage
converges at Rwp 0.163 (corundum 94.84, zincite 1.08, fluorite 4.08 wt %,
weighed 94.31, 1.36, 4.33). So the runaway itself depends on the start: it
begins from cpd-1a's closing-stage answer, not its declared-stage one. A
design that only makes the expensive stage cheaper leaves a warm attempt
that still diverges and is then escalated.

**Who sees it.** A user whose fit runs away now waits with no end in sight,
where 1.9.0 returned a bad Rwp in seconds. Cancelling is cooperative and read
between residual evaluations, so it should take effect within one evaluation
(inferred, not measured). Measured only on this series. A single fit should
behave the same when its last declared stage runs away (inferred from the
mechanism: the closing stage compiles at whatever answer it is handed).
1.10.0 ships with this as a stated limit (the maintainer's ruling,
2026-10-24, option A of WP-2043): `RefinementPlan.closing_window_tol=None`
skips the closing stage.

**What the runaway is, measured 2026-10-24 after the cut** (Linux x86-64
cloud container, 4 cores, `[dev]`, Python 3.12, `OPENBLAS_NUM_THREADS=1`,
tree `7d24e09e7`; the probes are in [`2045-batch/`](2045-batch/README.md)). The
probes ran cpd-1a → cpd-1b under `chained_all`'s protocol. They wrapped
`refine.compile_model` and stopped at the runaway closing compile, which they
reached within seconds. Every time quoted below comes from one run on that
container, so it gives an order of magnitude, not a benchmark. The warm
stage ended "converged" at `axial_sl` 555, with
`w` 0.27 and `v` −5.5. Its closing compile holds 873.7 M point-nodes
(window points × FCJ nodes, all phases and lines). That is 1 608× the warm
stage's own compile, where cpd-1a's normal closing compile is 19× its last
declared stage's.

- **It is a minimum of the frozen model only.** The probes evaluated the
  answer on the model the stage solved on and on fresh compiles. On the
  frozen windows Rwp is 0.760. On fresh windows it is 1.376 at the declared
  precision and 1.294 at the closing precision. The stage started at 1.748.
  At the answer the frozen windows drop **73.4 %** of the Bragg intensity
  a fresh compile computes, and χ²(fresh)/χ²(frozen) is 3.27. On each of
  cpd-1a's eight declared stages and its closing stage, the same measure is
  0.00-1.32 %, with a χ² ratio of 0.94-1.00. The mechanism, inferred from `forward.py:3980-3990`
  and `fcj.py:129-149`: as S/L grows, the asymmetry spreads each peak beyond
  the window frozen at the stage's start, and the part outside drops out of
  the model. So S/L, and the widths, act as an intensity sink, and the warm
  start's scales, carried from cpd-1a, are too strong for cpd-1b.
- **The tolerance stops the stage on the sink's plateau.** The same frozen
  stage, from the same start, ends at `axial_sl` 554.99 under `ftol` 1e-6
  and at 0.0139 (Rwp 0.196) under 1e-9. The 100-iteration cap changes
  neither (`max_iter` 100 and 400 agree). The warm stage runs at
  `intermediate_ftol` only because a closing stage follows it
  (`stage_ftols`, WP-1123). Before #1085 it was the last stage, at 1e-9.
  So #1085 combined three changes, not two: the ceiling, the closing stage,
  and the looser tolerance the closing stage gave the stage before it.
- **Windows that follow the parameters remove the runaway.** The probes ran
  the same warm fit as short stages, each recompiling, closing stage off:
  every 10 iterations ends at Rwp 0.142 (`axial_sl` 0.0077) in about 10 s,
  and every 3 at the same answer in about 25 s. The independent fit gets
  0.137. Every 50 iterations runs further away (`axial_sl` 4 041, zincite's
  scale 0, Rwp 0.779, about 4 minutes): the windows catch up too late.
- **A re-solve after the runaway does not repair it.** From the answer, on
  fresh declared-precision windows, `ftol` 1e-6 goes further (`axial_sl`
  4 114, Rwp 0.782, about 30 s). At 1e-9 it reaches 4 100 and hits its
  400-evaluation cap (about 2.5 minutes). So a check at the stage boundary
  can refuse to build on a runaway but cannot undo one.

**Moving windows were described but never offered.** The freeze dates from
v0.1 (DESIGN.md rule 1, whose stated reason, "gradient bias", the record
never measured). WP-2002's sixth-round brief listed GSAS-II, MAUD,
RIETAN-FP and EasyDiffraction as moving their windows at every evaluation,
and TOPAS as rebuilding them past a tolerance. All four of its options kept
the freeze (`2002-batch/rulings.md`, Q1). In the eighth round the maintainer
asked what those programs do. The five variants measured were all frozen
(`rulings.md`, § Eighth round).

**How the rounds missed it.** B9's brief named the boxes it covered and not
the axial ratios. Those sat in the `Geometry:bounds` hand row, and the
session read "no chosen limits on quantities that remain physical" as
covering them (WP-2002's handover). But `axial_sl` 555 is a sample
half-length 555 goniometer radii long, and the revised pick kept "a box that
guards a … non-physical region". The brief said each box "guards a
runaway", yet the evidence it asked for was whether a box binds an honest
fit. The closing stage was measured on four single fits from good starts.
Nobody measured either change on a fit that runs away. The one test that
does, `chained_all`, is slow-marked and runs only in the nightly `full`
job. That job timed out as cancelled, with no durations table (WP-2036
item 1). The one local slow run on a tree with #1085 (arm64 Mac,
`12f459e5`, before #1113) finished in 18 min.

**Ruled 2026-10-24: option 5 here, for 1.10.1, and option 4 as
[WP-2047](2047-windows-follow-the-parameters-between-solves.md).** The
maintainer's answer, to the candidates below with the measurements above:
"5 now, 4 as own WP". Option 5 sets no threshold, so it adds no `_audit`
row of its own. It changes what `stage_ftols` gives the last declared
stage, so the `intermediate_ftol` rows are re-read against it.

**What option 5 costs, measured 2026-10-25** (macOS arm64, `[dev]`, compiled
tier on, tree `ab5922dd3`, another session's pytest on about three of ten
cores; `2045-batch/probe6.py`). Shipped against the last declared stage's own
`ftol` set to `optimize.lm.FTOL`, two interleaved rounds each. "Away" is the
largest shift from the shipped answer in plain esd, non-background rows
(`test_window_domain._shift`). Evaluations counted at `StageResult.n_iterations`.

| Protocol | Evaluations, whole fit | Last declared stage | Closing stage | Wall clock in s | Away |
|---|---|---|---|---|---|
| SRM 660c LaB6 | 86 → 90 (1.05×) | 7 → 11 | 12 → 12 | 0.90-1.01 → 0.87-0.94 | 0.000 |
| fluorapatite | 47 → 49 (1.04×) | 7 → 9 | 9 → 9 | 2.16-2.17 → 2.15-2.87 | 0.000 |
| cpd-1a | 167 → 175 (1.05×) | 16 from 7 | 14 → 13 | 2.90-3.03 → 2.95-3.07 | 0.0004 |
| 11-BM NAC | 43 → 46 (1.07×) | 7 → 10 | 7 → 7 | 0.79-0.95 → 0.79-0.80 | 0.000 |
| mg090 joint (11-BM + BT-1) | 143 → 143 | 3 → 3 | 8 → 8 | 6.15-6.43 → 5.69-6.22 | 0.000 |

Every arm converged, and Rwp agreed to 1e-10. The joint fit is
`test_acceptance_wavelength._joint(None)`'s protocol. So option 5 hands back
1.04-1.07× of the 1.2-1.6× `intermediate_ftol` buys, and the second task's
rule ("if option 5 costs more than that saving, put the numbers to the
maintainer") does not fire.

**Design candidates, as put to the maintainer.** Each needs the maintainer's ruling, and
the generality audit table needs a row for any threshold
(`src/rietx/_audit.py`; root CLAUDE.md § Every heuristic has a row):

1. Skip the closing stage, recorded in a field and a diagnostic, when the
   recompiled model's work exceeds a factor of the last declared stage's.
   This covers every parameter that drives windows or FCJ nodes, but it is a
   tier-3 threshold.
2. A runaway reset for the axial ratios, on the pattern WP-2002 B8 built for
   a cell (`refine.reset_cell_runaway`, `CELL_RUNAWAY`: a parameter leaving
   a window around its stage-start value is put back and held for one more
   solve). This covers this case, not V or the widths.
3. In `sequential.py`, judge a warm attempt against the fence before its
   closing stage, and run the closing stage only on the attempt kept. This
   covers series and not single fits.

Added after the measurements above:

4. **Windows follow the parameters between short solves**, as TOPAS rebuilds
   its peak buffer when a width passes a tolerance. Each solve keeps its
   windows frozen, so the invariant holds inside it. A stage ends a solve
   and recompiles when its windows have gone stale, and converges only on a
   solve that needed none. Measured on this case: no runaway, Rwp 0.142.
   Unmeasured: whether it moves the four standards' converged answers, what
   it costs them, and which staleness test triggers the recompile (dropped
   intensity separates 0-1.3 % from 73 % here, on one family).
5. **The stage before the closing stage runs at the solver's tolerance.**
   This reverses, for that one stage, what the closing stage did to
   `stage_ftols`. Measured: no runaway, Rwp 0.196. It sets no threshold. It
   removes this trigger and leaves the sink: a sink that is a true minimum of
   the frozen model would still stop a stage there. Its cost on the four
   standards is unmeasured.
6. **The closing compile refuses a stale answer.** Before solving, it compares
   the frozen and fresh models at the answer, using the dropped-intensity
   measure above. On a stale answer it skips the closing stage and says so
   rather than polishing. This guards the cost from the measured cause, not
   a work ratio, but it cannot repair the answer (the last bullet above).
7. **Windows move at every evaluation**, as GSAS-II, MAUD, RIETAN-FP and
   EasyDiffraction do. This drops the frozen-per-stage invariant. The
   analytic and FD Jacobians, FCJ node sizing, the compiled kernels' row
   ranges, the traced backends' static shapes and `replay` all rest on that
   invariant. It is not a patch-release change.

The frozen-per-stage invariant constrains 1-3 and 5-6: window ranges and FCJ
node counts are fixed at compile and never change inside a solve, so any
decision is taken at compile, from values the stage cannot change. Option 4
keeps it per solve and gives it up per stage.

**Files.** `strategy/staged.py` (`run_stages`, the closing stage),
`model/forward.py` (`compile_model`, the window and FCJ sizing), `refine.py`
(`reset_cell_runaway`), `sequential.py` (the rung ladder and fence).

**Practice.** GSAS-II floors SH/L at 0.0005 or 0.002 and sets no ceiling
(`GSASIIstrMath.py`, `GSASIIpwd.py`; checked in GSAS-II 5.8.4 source on
2026-10-24). No program surveyed has a closing stage of this kind; BGMN ends
with every parameter free and restarted from the previous answer
(`docs/practice.md` does not survey axial limits; its § Staging carries
BGMN's closing run). BGMN holds its
ray-traced instrument function for the whole fit (`practice.md` § Staging),
so its closing run cannot move the axial geometry. That precedent does not
cover a closing stage that frees `axial_sl`. GSAS-II's `dropOOBvars`
(`GSASIIstrMain.py:1198-1230`) runs after every `Refine` and after every
histogram of `SeqRefine`. It sets each variable that refined outside a
user-set limit to the limit, freezes it for later refinements with esd 0,
and warns "N variable(s) refined outside limits and were frozen". The limits
are empty by default (`parmMinDict`), so it never fires unless the user arms
it (read on GSAS-II's `main` on 2026-10-24). It is the nearest precedent for
option 2's shape. It also corrects WP-2002 B8's "I know of no program that
clamps a cell after a solve", which was recalled, not checked.

**What the ladder does with it, measured by WP-2003** (2026-10-24, PR #1150,
4-core Linux x86-64 container, `[dev]`; `docs/wp/2003-batch/reseed.md`,
families `cpd` and `cpd-noclose`). At cpd-1b the warm rung's closing stage
ran to its 400-evaluation cap in 2 300-2 600 s and came back `max_iter` at
Rwp 0.7652. Under the default fence (1.25 × the median) the ladder escalated
to `warm_staged` and kept 0.13779, against 0.13732 for the independent fit.
With the fence off, the 0.7652 fit was kept and seeded cpd-1c, whose closing
stage then crawled at about 5 evaluations a minute. With
`closing_window_tol=None` the warm rung reached 0.16333 and nothing
escalated. The time per evaluation is mostly FCJ quadrature: node counts
climb to the 512 cap, and each new count misses the `leggauss` cache
(`model/profiles/fcj.py:88-92`). On Linux with default BLAS threading one
`leggauss(444)` took 5.4-6.0 s, against 0.014 s on one thread, so set
`OPENBLAS_NUM_THREADS=1` before timing anything there. WP-2003 also added
`test_the_first_rung_bound_moves_no_accepted_value`, a second
`chained_all`-shaped chain in the same `qpa-sample1` group. Both chains cost
1 h 17 min on that machine, so the nightly's 150-minute limit counts both.

## Non-goals

- Restoring the 0.2 ceilings, or any limit B9 removed. That was ruled.
- Which of S/L and H/L a fit reports. That is WP-2012.
- Every other nightly leg. That is WP-2036, which this WP unblocks for the
  `full` job.

## Tasks

- [x] The design, put to the maintainer with this file's numbers. Ruled
      2026-10-24: option 5, and option 4 filed as WP-2047.
- [x] Measure option 5 before building it, as the ruling asked: on the four
      acceptance protocols (SRM 660c LaB6, the fluorapatite tutorial,
      cpd-1a, 11-BM NAC), the whole-fit time and the largest shift in plain
      esd against the shipped tree, in the shape of WP-2002's eighth-round
      table, plus one joint fit, since `MultiHistogramRefinement.fit` reads
      `stage_ftols` too (`multi.py:1434`). On a single fit, emulate it with
      the last declared stage's own `ftol` set to `optimize.lm.FTOL`, since a
      stage's own `ftol` wins in `stage_ftols`. On a series that emulation
      does nothing: the collapsed warm plan (`sequential.py:502`) builds its
      one stage without an `ftol`. There, `probe3.py`'s single stage at
      `ftol` 1e-9 is the measured stand-in. Compare evaluations, not
      iterations: `StageResult.n_iterations` counts iterations, and WP-1123's
      saving is 1.2-1.6× fewer evaluations. If option 5 costs more than that
      saving, put the numbers to the maintainer.
- [x] The implementation: `RefinementPlan.stage_ftols` gives the last
      declared stage the solver's tolerance when a closing stage follows it,
      a stage's own `ftol` still winning. Every runner then inherits it:
      `PlanSpec` through `resolve_plan`, the joint fit through
      `multi.py:1434`, and the collapsed warm plan in `sequential.py`
      through the plan it builds. `StageResult.ftol` already records what a
      stage ran at.
- [x] A test that fails before the change: the hostile series' cpd-1b warm
      stage from cpd-1a's closing answer ends with `axial_sl` under 1 (on
      the 1.10.0 tree it reaches 555 within seconds on Linux), and a fast
      `stage_ftols` test on a plan with and without a closing stage
- [ ] The `intermediate_ftol` rows in `src/rietx/_audit.py`, and the
      `INTERMEDIATE_FTOL` and `CLOSING_WINDOW_TOL` docstrings, re-read
      against the new schedule
- [ ] `tests/test_acceptance_sequential.py` finishes, WP-2003's second
      chain (`test_the_first_rung_bound_moves_no_accepted_value`) included;
      VALIDATION.md's three `chained_all` rows (marked unmeasured on 1.10.0)
      re-measured
- [x] Notes for 1.10.1 (`docs/releases/`), and the 1.10.0 stated limit
      withdrawn from the skill. Staged in `1.11.0.md`, the one staging file;
      the cut names the release (ROADMAP rule 6)
- [x] Skill: the stated limit's bullet in `references/series.md` (beside
      the quarantine rule) removed or rewritten to what the fix does

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_acceptance_sequential.py -n 4 --dist loadgroup
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
```

The sequential suite finishes, alone on an arm64 Mac, in a time comparable to
1.9.0's (about 2.5 minutes for the module, measured by WP-2043's lane on the
pre-#1085 snapshot). The nightly `full` job completes on `main`.

WP-2043's probe (`hang/probe.py` in that session's scratchpad, not
committed) ran `SequentialRefinement(...).fit` on cpd-1a and cpd-1b under
`qpa_plan()` with `seed_scales` from cpd-1a, as `chained_all` does, wrapped
`compile_model` to log `win` and `fcj_n` per phase, and logged
`stage_start`/`stage_end` events.

## Handover log

### 2026-10-24 (2nd session) — ruled: the stage before the closing stage converges, and windows that follow the parameters get a WP of their own

The runaway that stalls the hostile series is not a real answer. It exists
only because each stage freezes its peak windows. As the axial ratio grows,
each peak spreads past its frozen window and the overflow drops out of the
model. So growing the ratio can only remove intensity, and with the warm
start's scales too strong for the next mixture, that lowers the error. The
warm stage stops there only because a closing stage now follows it, which
loosens its tolerance; at the tolerance it ran at before 1.10, the same
stage from the same start finds a sane answer. Windows recompiled every few
iterations avoid the runaway entirely and give the best answer measured.
The maintainer ruled the tolerance change for 1.10.1 and the recompiling
windows into WP-2047.

*Done.* The design was put to the maintainer in three rounds: options 1-3
(work ratio, axial reset, fence first), then how the rounds missed it and
what practice says, then whether windows that move at every evaluation were
considered. Each answer is in Context: "What the runaway is", "Moving
windows were described but never offered", "How the rounds missed it" and
the Practice paragraph (GSAS-II's `dropOOBvars`, checked on its `main`).
Candidates 4-7 were added and the ruling recorded above them. Goal and tasks
were rewritten to option 5. WP-2047 was filed for option 4. WP-2036 was
re-rated P1 → P2 with this WP as a hard dependency. The five probes are in
`2045-batch/`. No code changed.

*Measured* (Linux x86-64 cloud container, 4 cores, `[dev]`, Python 3.12,
`OPENBLAS_NUM_THREADS=1`, tree `7d24e09e7`, one run per probe). The runaway
reproduces within seconds at `axial_sl` 555. Its closing compile is 873.7 M point-nodes, 1 608×
the warm stage's, against 19× for cpd-1a's normal one. The full set (frozen
against fresh Rwp, intensity dropped, the `ftol` and K tables, the
re-solves) is in Context's four bullets.

*Gotchas.*
- `rietx.refine` is the exported function. The module is
  `sys.modules["rietx.refine"]`, where the probes patch `compile_model`.
- The probes are records, not tests, and nothing runs them
  (`2045-batch/README.md`).
- A force push to the session's branch was refused by the harness. The
  branch's old tip was an ancestor of `main`, so a fast-forward push did
  the job.
- A stage's own `ftol` never reaches a series' warm stage, which is built
  without one, so the single-fit emulation does nothing there (second task).

*Review* (`/code-review high`, run without `--fix` because the probes record
runs whose numbers are already quoted). Ten findings. Fixed: the "Next"
decision rule had been written inverted; the series emulation gap; the
joint fit's use of `stage_ftols`; single-figure timings, now one-run orders
of magnitude; the Practice paragraph contradicting itself; probe2's
docstring and its iterations labelled "evals"; probe.py's abort test,
aligned with the other four (both tests fire at the same compile in the
recorded run, so no number moves). Checked, not changed: probe4 pairs
consecutive compiles as stages, which holds for the recorded run (eight
declared stages, then the closing compile, then the final compile; the
wording now says so). Declined: one shared helper for the five probes,
because rewriting a record changes the script that produced its numbers.

*Verified.* The branch changes only `docs/wp/`. The probes sit outside
`testpaths` and ruff's targets, and they compile and pass `ruff check`.
`tests/test_docs_consistency.py` passes, 25 tests. No count can move, so
neither the fast nor the full selection ran. No generality judge was
dispatched: `_audit.py` is untouched, and option 5 adds no threshold until
it is built.

Next: measure option 5 on the four standards and one joint fit before
building it (the second task). If it costs no more than what
`intermediate_ftol` saves, build it (third and fourth tasks). If it costs
more, the numbers go to the maintainer before any code.

- **2026-10-24** — filed by WP-2043's session (the 1.10 cut), after its
  VALIDATION lane found the hostile series never finishing and the session
  reproduced the cause. No open WP owns the closing stage's cost: 2036 owns
  the nightly legs being green and gets an Inherited pointer, 2012 owns the
  axial pair's identity, 2020 owns opt-in bound sets. The maintainer chose to
  cut 1.10.0 with the limit stated and fix it here.

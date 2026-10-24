# WP-2045 — A runaway fit ends without an expensive closing stage

Milestone: unscheduled · Status: ⬜
Track: A long run is not one fit
Depends on: —
Priority: P2 2026-10-24 — a defect that costs a user a workaround: a fit that runs away now seems to hang, where 1.9.0 ended it in seconds; 1.10.1 waits on it

## Goal

A fit whose last declared stage ends at a runaway answer finishes in a time
comparable to its declared stages, and says what it skipped or held. The
hostile series in `tests/test_acceptance_sequential.py` (`chained_all`)
finishes on every platform. The nightly `full` job completes inside its
150-minute limit again.

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
tree `7d24e09e7`; probes in that session's scratchpad, not committed). The
probes ran cpd-1a → cpd-1b under `chained_all`'s protocol. They wrapped
`refine.compile_model` and stopped at the runaway closing compile, which they
reached in 13.6 s. The warm stage ended "converged" at `axial_sl` 555, with
`w` 0.27 and `v` −5.5. Its closing compile holds 873.7 M point-nodes
(window points × FCJ nodes, all phases and lines). That is 1 608× the warm
stage's own compile, where cpd-1a's normal closing compile is 19× its last
declared stage's.

- **It is a minimum of the frozen model only.** The probes evaluated the
  answer on the model the stage solved on and on fresh compiles. On the
  frozen windows Rwp is 0.760. On fresh windows it is 1.376 at the declared
  precision and 1.294 at the closing precision. The stage started at 1.748.
  At the answer the frozen windows drop **73.4 %** of the Bragg intensity
  a fresh compile computes, and χ²(fresh)/χ²(frozen) is 3.27. On every
  declared stage of cpd-1a's fit the same measure is 0.00-1.32 %, with a χ²
  ratio of 0.94-1.00. The mechanism, inferred from `forward.py:3980-3990`
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
  every 10 iterations ends at Rwp 0.142 (`axial_sl` 0.0077) in 11 s, and
  every 3 at the same answer in 25 s. The independent fit gets 0.137.
  Every 50 iterations runs further away (`axial_sl` 4 041, zincite's scale
  0, Rwp 0.779, 261 s): the windows catch up too late.
- **A re-solve after the runaway does not repair it.** From the answer, on
  fresh declared-precision windows, `ftol` 1e-6 goes further (`axial_sl`
  4 114, Rwp 0.782, 32 s). So a check at the stage boundary can refuse to
  build on a runaway but cannot undo one.

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

**Design candidates, none chosen.** Each needs the maintainer's ruling, and
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
(`docs/practice.md` does not yet survey either point). BGMN holds its
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

### Inherited

- **From WP-2003 (2026-10-24, PR #1150): the same runaway on Linux, what the ladder does with it, and one more chain in your acceptance.** WP-2003 measured the hostile series on a 4-core Linux x86-64 cloud container (`[dev]`). Results are in `docs/wp/2003-batch/reseed.md`, families `cpd` and `cpd-noclose`, per pattern. At cpd-1b the warm rung's closing stage ran to its 400-evaluation cap in 2 300-2 600 s and came back `max_iter` at Rwp 0.7652. Under the default fence (1.25 × the median) the ladder escalated to `warm_staged` and kept 0.13779, against 0.13732 for the independent fit. With the fence off, or with an infinite fence, the 0.7652 fit was kept and seeded cpd-1c, whose closing stage then crawled at about 5 evaluations a minute. With `closing_window_tol=None` the warm rung reached 0.16333 and nothing escalated. Two findings bear on the fix. (1) The time per evaluation is mostly FCJ quadrature: node counts climb to the 512 cap, and each new count misses the `leggauss` cache (`model/profiles/fcj.py:88-92`, reached from `refine.py:1548` → `model/forward.py:2212` → `fcj.py:241`). With default BLAS threading, one `leggauss(444)` took 5.4-6.0 s, against 0.014 s with one thread, so on Linux set `OPENBLAS_NUM_THREADS=1` before timing anything here. (2) WP-2003 added `tests/test_acceptance_sequential.py::test_the_first_rung_bound_moves_no_accepted_value`, which builds a second `chained_all`-shaped chain with the first-rung bound off, in the same `qpa-sample1` group. It cost 1 h 17 min for both chains on that machine, so your acceptance's "the nightly `full` job completes inside its 150-minute limit" has to count it. It should fall to the same seconds as `chained_all` once the runaway is cut short. WP-2036's Inherited carries the same measurement from the full suite's side.

## Non-goals

- Restoring the 0.2 ceilings, or any limit B9 removed. That was ruled.
- Which of S/L and H/L a fit reports. That is WP-2012.
- Every other nightly leg. That is WP-2036, which this WP unblocks for the
  `full` job.

## Tasks

- [ ] A fast test that reproduces the cost at compile, without running the
      expensive solve: compile cpd-1b's closing model at the runaway answer
      and assert the decision the chosen design makes
- [ ] The design, put to the maintainer with this file's numbers
- [ ] The implementation, its record field and diagnostic, and its `_audit`
      row
- [ ] `tests/test_acceptance_sequential.py` finishes; VALIDATION.md's three
      `chained_all` rows (marked unmeasured on 1.10.0) re-measured
- [ ] Notes for 1.10.1 (`docs/releases/`), and the 1.10.0 stated limit
      withdrawn from the skill
- [ ] Skill: the stated limit's bullet in `references/series.md` (beside
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

- **2026-10-24** — filed by WP-2043's session (the 1.10 cut), after its
  VALIDATION lane found the hostile series never finishing and the session
  reproduced the cause. No open WP owns the closing stage's cost: 2036 owns
  the nightly legs being green and gets an Inherited pointer, 2012 owns the
  axial pair's identity, 2020 owns opt-in bound sets. The maintainer chose to
  cut 1.10.0 with the limit stated and fix it here.

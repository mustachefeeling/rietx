# WP-2003 clash table: the chain actions against each other

Task 5. Every pair of actions a series takes between patterns that read or move the same thing:
the reseed fence, the rung ladder and its forced escalation, the kept-attempt choice
(`_prefer`/`_better`), the quarantine, the width-growth screen, the moment-floor carry, plus the
carry policy against the width twin hold, the closing stage against path dependence, and WP-2002's
B7 and B16. The three clashes found on 2026-10-24 are X1-X3. The classes (C1-C11) are those of
`classes.md`. Line numbers are this worktree's at `ded5c3f` (2026-10-24), each re-read this session.

**Measurements.** Linux x86-64, 4-core cloud container, worktree venv `[dev]`, compiled tier on
except the planted chain (off, as in `measure_reseed.py`'s planted protocol), one BLAS thread,
`RIETX_TELEMETRY=0`, beside the reseed lane's background CPD run. Run by this lane on 2026-10-24
from scratch scripts; each entry names the fixture and the arms, so the run can be repeated. The
families: the thermal ramp (`tests/test_sequential.py` `_simulate`, 7 patterns, `mccusker_default`);
the jump series (the same file's `jump_patterns`, 6 patterns); the trigger series
(`examples/bench_refinement.py` `_trigger_series`, 10 patterns, `qpa_plan()`); issue #451's soak
(`tests/test_sequential.py` `_soak_pattern`, 5 patterns, Pawley); the planted ramp
(`tests/planted_series.py` `generate(248, seed=0)`). Also read, without running anything: the reseed
lane's JSONs in `reseed/` (CPD with and without the closing stage, Cr₂WO₆, planted). "esd" below is
the reported esd (Bérar-Lelann f included) unless it says "plain". Wall clock is context only.

## Summary

| # | Clash | Order matters? | Measured? | Moves a reported value? | Class | Proposed resolution |
|---|---|---|---|---|---|---|
| X1 | First-rung bound × closing stage | Yes | Yes: thermal ramp at factor 0.5; planted at 3.0 | Yes. Hidden truncation: ≤ 8e-4 esd (thermal). The closing stage cut: 39.3 esd on the blank frame's scale (planted) | C3 | Fix: read the truncation off the rung's own stages, and cap and sample the same thing. Then FIRST_RUNG_FACTOR cannot be `invariant` on its present evidence (planted's ratio is 6.7) |
| X2 | `reseed=False` × forced escalation | Yes | Yes: thermal (no closing stage) and planted T087 | Yes: planted T087, the 39.3 esd of X1 | C1, C3 | Fix: no first-rung budget when `reseed=False`. One breach of the docstring, none other |
| X3 | Closing stage × the fence (cpd-1b) | Yes | Yes (reseed JSONs) | Yes: every value of cpd-1b; corundum *a* 4.8 % | C1, C9 | Ruling for C1, with the mechanism stated: the fence's one rescue is a runaway the closing stage made on a warm refit. Without the closing stage, a degraded warm fit passes every trigger |
| X4 | Closing stage × a status-only trigger | Yes | Yes (reseed JSONs: Cr₂WO₆ status+`max_iter`) | Yes: ≤ 0.087 esd, at 3.07× the evaluations | C1 | Ruling: which stage's `max_iter` counts. Reading the closing stage catches cpd-1b and triples Cr₂WO₆'s cost. Reading the warm stage catches neither |
| X5 | Ladder × `_prefer`/`_better` | Yes (the comparison order) | Partly: planted T087 | Yes: T087 kept the higher-Rwp attempt | C2 | Ruling on `max_iter` versus `converged` (C2). Fix: rank diverged before truncated. Fix the `_ladder` docstring |
| X6 | Ladder × width growth | No | Yes: soak, three arms | No: ≤ 5.1e-5 esd, finding identical | C7 | No interaction, shown by the soak. The C7 field carries `rung` beside each ratio |
| X7 | Ladder and quarantine × moment carry | Yes | No (no family has a floor before an escalation) | Record only | C8, C2 | No value interaction. Record fix: `floored` beside `seeded_from`, so a floored-then-cold pattern does not read as floored |
| X8 | Quarantine × median × fence | Yes (walk position, direction) | Partly: the soak's median following the drift | Not on disk | C1 | Ruling: the fence's first patterns are judged against a median of one or two. State it in the fence's help entry, or arm the fence after a minimum |
| X9 | `reseed_factor=inf` × the scan's above-fence drop and the outlier report | No | Yes: soak; tut05-broken (handover) | Yes: four `SEQUENTIAL_RWP_OUTLIER` to none; one `SEQUENTIAL_DISCONTINUITY` gained | C1, C4 | Fix: validate `reseed_factor`. Give a status-only trigger its own switch, so the fence stays a reported number |
| X10 | Rejected rungs and `verify_discontinuities` × the automatic profile interval | No | Yes: Cr₂WO₆ counts (reseed JSONs) | No: cost only | C2, C4 | Fix (task 3): `_auto_intervals = False` on every rung and verify refit, and the interval run once on the kept attempt |
| X11 | Carry policy × width twin hold | Yes (carry first, hold second) | Yes: the strict xfail | Yes: mean Rwp +0.0026 (values not measured) | C9 | Measure QPA against weighed before ruling `carry`. Candidate design: hold the twins for the chain at pattern 0's instrument-only value |
| X12 | Closing stage × path dependence | No | Yes: thermal, jump, trigger, `direction="both"` | No: no flag appears or vanishes; the gaps shrink | C5, C9 | No interaction that moves a flag, shown on three synthetic families. CPD not run |
| X13 | B7 (`intermediate_ftol`) along a chain | Yes (it stops the warm stage before the closing stage) | Yes: thermal, jump, trigger | ≤ 2.7e-4 esd, set by pattern 0 and not amplified | C9 | No chain amplification on three families. One CPD arm would settle whether 1e-6 on the warm stage feeds X3 |
| X14 | B16 (bound test) × the joint parametric form test | One way | No | Unmeasured | C10 | Measurement owed above `BVLS_MAX_COLUMNS`, where the joint fit leaves the exact active set |
| X15 | Ladder × path dependence | Yes | No (no measured `direction="both"` family escalates) | Unmeasured | C5, C1 | Unmeasured. The C5 field should carry each direction's `rung` beside each gap |

---

## X1. The first-rung bound × the closing stage

**The actions.** WP-1127's first-rung bound (`_first_rung_budget`, `sequential.py:571-603`, applied
by `_bounded_plan`, `:606-623`, at `:1574-1575`). WP-2002's closing stage, which `_collapse` carries
into every warm refit (`closing_window_tol=plan.closing_window_tol`, `:517`).

**Order matters.** The bound caps the plan before the rung runs. The closing stage runs inside the
rung. The ladder reads the result after both. Neither code path runs the other way round, but the
clash has two outcomes, depending on whether the closing stage fits inside the cap.

**Mechanism.** `_bounded_plan` caps `max_iter` on every declared stage. `RefinementPlan.closing_stage()`
copies the last declared stage's `max_iter` (`strategy/staged.py:390-394`), so **the cap reaches the
closing stage too**, once per stage: a bounded collapsed rung may spend up to twice its budget.
`RefinementResult.status` is the last stage's outcome, which is the closing stage's
(`refine.py:5171`). `truncated` reads `result.status == "max_iter"` (`sequential.py:1605-1606`). And
the budget's sample is `spent = sum(s.n_iterations for s in result.stages)` (`:1604`), the warm
stage plus the closing stage, while the cap applies to each stage separately.

- *Outcome 1: the closing stage converges inside the cap and hides the truncation.* The truncated
  warm stage reads `converged` at the rung level. No forced escalation follows (`:1563`), `_prefer`
  does not rank it down, and the rung's evaluations enter `accepted_first` as a converged first
  rung (`:1721-1724`). That sample now holds a truncated rung, though here it did not raise the
  running maximum.
- *Outcome 2: the closing stage itself exceeds the cap.* The rung reads `max_iter` and escalates,
  although its warm stage converged. The bound then cuts a winner. The sample sums both stages,
  while the cap applies to each, and a closing stage can cost more than everything before it.

**Measured.** Thermal ramp, `first_rung_factor=0.5`, with the closing stage and without it
(`closing_window_tol=None`), against the unbounded chain:

| arm | 700-900 K first rung | rungs | result status | evals | gap to unbounded |
|---|---|---|---|---|---|
| closing on | `warm_refit` `max_iter` at 8 evals (cap 2 iterations × 4), closing `converged` in 3 | `[warm]` | `converged` | 115 against 127 | 8e-4 esd (900 K, background c1) |
| closing off | `warm_refit` `max_iter` | `[warm, warm_staged]` (forced) | `converged` | 154 against 106 | 0.019 esd |

`STAGE_MAX_ITER` fires on each of the three entries in the closing-on arm, so the per-pattern
record does show the cut. The ladder does not see it.

Planted ramp, `reseed=False`, `FIRST_RUNG_FACTOR` (3.0) against `None`, compiled tier off.
The bound bit at T087, the blank frame. The budget was 30 evaluations (running maximum 10 × 3),
which is a cap of 8 iterations and 32 evaluations a stage. The unbounded first rung converged, its
warm stage in 24 evaluations and its closing stage in 43. The bounded rung spent 56 = 24 + 32, so
the cut fell on the closing stage (inferred from the counts). It escalated to `warm_staged` and kept
Rwp 0.048071, against the unbounded warm rung's 0.047958. Accepted values: T087's phase scale moved
39.3 esd; 4 values moved more than 1 esd and 11 more than 1e-3 esd, all T087's but one of T088's
(9.8e-4 esd); everything after T088 is within 7.3e-6 esd; patterns before T087 are bit-identical.
2 716 evaluations against 2 818. That first rung's ratio to the running maximum is 6.7. The constant's
comment calibrates its 3.0 on a worst ratio of 1.29 across three chains (`sequential.py:196-200`);
before T087 on planted the worst ratio is 1.11.

**What it moves.** Hidden truncation: a kept answer within 8e-4 esd of the unbounded one (thermal),
at a lower cost. The closing stage cut: a blank frame's every value, its scale by 39.3 esd, carried
1e-3 esd into its successor. Both contradict `first_rung_factor`'s docstring, "A bound that bites
costs an escalation and never an answer" (`:1104-1107`): the first outcome costs no escalation and
keeps the truncated answer; the second costs an answer. The bound's comment already admits the first
(`:213-219`).

**Class.** C3.

**Proposed.** A fix in two parts, then a decision. (1) Read the truncation off the rung's own stages:
any stage of a bounded first rung at `max_iter`, not `result.status`. (2) Cap and sample one thing:
either the warm stage alone, with the closing stage on its own budget and out of the sample, or the
rung as a whole. Then re-run both invariance tests and add planted as the third family, with an arm
where the bound bites. On today's evidence, FIRST_RUNG_FACTOR cannot enter the answer-invariant
class: on planted it moved an accepted value, at a ratio (6.7) the 2.3× margin does not cover. The
case for the margin is that T087 is a blank frame whose scale is noise; the record's rule counts a
moved accepted value, not a meaningful one.

---

## X2. `reseed=False` × the forced escalation

**The actions.** The caller's `reseed` switch, and WP-1127's forced escalation of a bitten first
rung.

**Order matters.** Yes. `forced = bound_hit and len(tried) == 1` (`sequential.py:1563`) is tested
before the switch: `elif not forced and not (reseed and _reseed_needed(…))` (`:1571-1573`). A forced
escalation short-circuits `reseed`. The all-raised branch does honour the switch (`:1569-1570`).

**Mechanism.** The budget is computed whatever `reseed` says (`:1539-1541`), so a bitten first rung
escalates against a switch the caller turned off. The docstring promises the opposite: "Switching it
off leaves each pattern with its first rung" (`:1079-1085`).

**Measured.** Thermal ramp without the closing stage, factor 0.5: `reseed=False` escalated
700-900 K `[warm, warm_staged]`, identical to `reseed=True` (154 evaluations, same values). Planted,
`reseed=False` (the reseed lane's `planted_off.json`, reproduced by this lane's bounded arm): T087
`[warm, warm_staged]`, with the consequences in X1. With the closing stage on, the thermal ramp at
0.5 escalates nothing in either arm (X1, outcome 1), so the breach shows only where the closing
stage exceeds the cap or is off.

**Anything else the docstring promises?** Checked, and the rest holds. The quarantine still applies
(`:1699`, independent of `reseed`). A pattern on which every rung raised stops at its first rung
(`:1569-1570`). The fence is still computed and reported: on the soak under `reseed=False`, four
`SEQUENTIAL_RWP_OUTLIER` say "the rungs the chain tried before stopping short of its cold rung
(reseed off, or a cancel)" (`:2112-2114`). The discontinuity scan's above-fence drop still works,
since `rwp_fence` comes from `reseed_factor`. The forced escalation is the one breach.

**What it moves.** Planted T087's values (X1). Elsewhere, any bitten first rung under `reseed=False`.

**Class.** C1 (the switch), C3 (the bound).

**Proposed.** Fix: pass no first-rung budget when `reseed=False` (`budget = None`), so a pattern
keeps its first rung uncut. The alternative, amending the docstring to say a bound still escalates,
would leave a caller who turned the ladder off paying for one. A bound without its escalation would
keep a truncated rung, so the budget has to go with the switch.

---

## X3. The closing stage × the fence (cpd-1b)

**The actions.** The closing stage on a collapsed warm refit (`_collapse`, `sequential.py:470-526`,
carrying `closing_window_tol` at `:517`), and the Rwp fence (`_reseed_needed`, `:2004-2009`).

**Order matters.** Yes. The closing stage runs inside the warm rung. The fence judges the rung's
result afterwards.

**Mechanism.** With the closing stage, a warm rung is two stages: `warm_refit`, now an intermediate
stage at `intermediate_ftol` 1e-6, then the closing stage at 1e-9, recompiled at the warm answer
on windows dropping 1e-3 of each peak (`strategy/staged.py:377-395`, `:418-440`). Without it,
`warm_refit` is the last stage and runs at 1e-9.

**Measured** (the reseed lane's `cpd_*.json` and `cpd-noclose_*.json`, read only). cpd-1b is
94.31 wt % corundum.

| arm | warm rung's stages | Rwp | corundum *a* (Å) | zero (°) | codes | fence | what happened |
|---|---|---|---|---|---|---|---|
| closing on | `warm_refit` converged in 136 evals, closing `max_iter` at 400 | 0.7652 | 4.987(88) | 18.0(74) | `CELL_RUNAWAY`, `STAGE_MAX_ITER`, among others | 0.2038 | escalated; kept `warm_staged`, Rwp 0.1378, *a* 4.75804(38) |
| closing off | `warm_refit` converged in 410 evals | 0.1633 | rows absent (held) | −0.012(14) | `CELL_RUNAWAY`, `PHASE_UNCONSTRAINED` | 0.2095 | kept: inside the fence |
| cold reference, closing on | — | 0.1373 | 4.75809(38) | −0.040(35) | — | — | — |
| cold reference, closing off | — | 0.1393 | 4.75809(39) | −0.040(36) | — | — | — |

So the closing stage turned a degraded but bounded warm fit (Rwp 17 % above the cold fit's,
corundum's cell held, corundum 94.84(27) wt % against 94.29 cold) into a runaway that the fence
catches. Without it, the degraded fit passes the fence, status-only, `reseed=False` and
status+`max_iter` alike: all four no-closing arms are bit-identical on all eight patterns (the
`values_sha` of each entry). The handover's "with the closing stage off no CPD pattern escalates"
is right, and it is also where a degraded fit goes uncaught.

**What an Rwp-free rule would have done.** Status+`max_iter`, closing stage on: cpd-1b's result
reads `max_iter` (its closing stage), so the rule would escalate it. That arm is being measured now
(`cpd_status_maxiter`, the reseed lane), so its kept attempt and cost are not given here. Closing stage
off: measured, no escalation (`cpd-noclose_status_maxiter.json`, bit-identical to the fence arm).
Status-only without `max_iter`: keeps the runaway (the handover's 1 220 esd).

**Inferred, not measured.** The warm stage stopped at 136 evaluations at 1e-6, against 410 at
1e-9. The closing stage ran away from that 136-evaluation point. Whether the looser stop is what let
it run away is X13's open arm.

**What it moves.** Every value of cpd-1b: unescalated, corundum *a* sits 4.8 % off with an 18°
zero.

**Class.** C1 (what triggers the ladder), C9 (`_collapse` carrying the closing stage).

**Proposed.** A ruling for C1, with the mechanism in its stakes line: the fence's one real rescue
is of a runaway that the closing stage created on a warm refit. Without the closing stage, the
same pattern's warm fit is degraded inside the fence, and only its own `CELL_RUNAWAY` and
`PHASE_UNCONSTRAINED` say so. Two follow-ups for the batch: (a) the status+`max_iter` CPD arm
(running) decides whether that rule reproduces the rescue; (b) whether a warm refit should carry
the closing stage at all is C9's `_collapse` row. Its cost along a chain is WP-2036's; X12 and X13
measure what it does to path dependence and to the stage tolerance.

---

## X4. The closing stage × a status-only trigger (new)

**The actions.** C1's proposed rule (escalate on diverged, raised or `max_iter`), and the closing
stage, whose verdict is the result's status.

**Order matters.** Yes. The status a rule reads is the closing stage's, which ran after the warm
stage.

**Mechanism.** `result.status` is the closing stage's (`refine.py:5171`). A rule counting `max_iter`
as unfinished therefore escalates a pattern whose warm stage converged and whose closing stage hit
its budget.

**Measured** (the reseed lane's `cr2wo6_status_maxiter.json`). Cr₂WO₆ 150 K: `warm_refit` converged
in 24 evaluations and the closing stage ended `max_iter` at 800, in every arm. Status+`max_iter`
escalated it through all three rungs, each closing stage again at 800. It kept the cold rung, still
`max_iter`. Cost: 2 533 evaluations against 824 (3.07×), 47 s against 14 s. Accepted values moved
≤ 0.087 esd (`phases.0.atoms.2.x`). Anchored DOFs are left out: their values are steps from where
each fit began, and differ by construction (WP-1333).

**The split.** Two readings of "unfinished", on the two cases on disk:

| reading | cpd-1b (closing ran away) | Cr₂WO₆ 150 K (closing at budget, values fine) |
|---|---|---|
| the result's status (the closing stage) | escalates (arm running) | escalates, 3.07× for ≤ 0.087 esd |
| the warm stage's status | does not escalate (`warm_refit` converged) | does not escalate |

**What it moves.** ≤ 0.087 esd on Cr₂WO₆, at three times the cost.

**Class.** C1.

**Proposed.** A ruling inside C1: if status+`max_iter` is chosen, the brief names which stage's
`max_iter` counts and shows this table. Neither reading separates a runaway from a closing stage
that merely ran out of iterations at a good answer. The kept attempt never gets worse (`_prefer`),
so the closing-stage reading costs evaluations, not answers, on these two cases.

---

## X5. The ladder × the kept attempt (`_prefer`, `_better`)

**The actions.** The escalation (fence, status, forced) and the choice of which attempt to keep.

**Order of comparison.** `_prefer` (`sequential.py:1967-1990`) asks three questions in order.
First, truncated against untruncated: a truncated attempt loses outright (`:1985-1987`). Then
`_better` (`:1960-1964`): a diverged attempt loses. Then the lower Rwp wins. `max_iter` ranks equal
to `converged` at every step.

**Can a truncated attempt beat a converged one?** Not while the truncation is visible. When the
closing stage hides it (X1, outcome 1), the rung counts as untruncated. No escalation follows, so
there is nothing for it to compete against. A plan-capped `max_iter` attempt (no bound involved)
can beat a converged one on Rwp. Nothing on disk turned on that. On cpd-1b the finished rung also
had the lower Rwp (0.1378 against the `max_iter` rung's 0.7652). On Cr₂WO₆ 150 K under
status+`max_iter`, all three rungs ended `max_iter`, so the ranking never had to choose between the
two states.

**Two consequences of the order.**

- *A truncated attempt loses even to a diverged untruncated one.* By reading `:1985-1987`: under
  `reseed=False` with a forced escalation (X2), a diverged `warm_staged` rung is kept over a
  truncated first rung that had a finite, in-fence Rwp, and the pattern is then quarantined. Not
  observed on disk.
- *The kept attempt can have the higher Rwp.* Planted T087: `_prefer` kept `warm_staged` at
  0.048071 over the truncated warm rung at 0.047958. This is by design (the truncated attempt may
  not pick the answer), but X1 shows the truncated rung there was a winner cut short.

The `_ladder` docstring says `_better` "prefers a converged fit and then the lower Rwp"
(`:559-561`). It prefers a non-diverged fit; `max_iter` and `converged` tie.

**What it moves.** T087's values (X1). Nothing else on disk.

**Class.** C2.

**Proposed.** The `max_iter` ranking is C2's ruling. If it is ranked below `converged`, X4's table
applies, because the closing stage sets the status. Two fixes regardless: test `diverged` before
`truncated` in `_prefer`, so a finite truncated fit beats a diverged completed one; and correct the
`_ladder` docstring.

---

## X6. The ladder × the width-growth screen

**The actions.** Escalation and the kept attempt, against `SEQUENTIAL_WIDTH_GROWTH`
(`_width_growth_diagnostics`, `sequential.py:2514-2626`).

**Order matters.** No. The screen runs after the chain, on the entries (`:1359`). It sees the
ladder only through the attempt each pattern kept.

**Mechanism.** The reference is the first pattern, in series order, that is not diverged and
measured the width above 3σ (`:2564-2570`). An escalated or cold-kept pattern is read like any
other. A quarantined pattern is skipped (`:2565`). An above-fence pattern is read on purpose (the
docstring). Escalation keeps the lower Rwp, so it can only lower a pattern's GoF and make the
conjunction harder to meet.

**Measured.** #451's soak (one-phase model, `_SOAK_PLAN`, Pawley), three arms. With the fence on,
all four soaked patterns climbed all three rungs and kept `warm_staged`, `cold`, `warm_staged` and
`warm`: 254 evaluations against 71. Every value lies within 5.1e-5 esd of `reseed=False` and of
status-only. The finding was identical in all three arms: 3.6× from fB=0.00 to fB=0.10 with GoF
3.1×, reaching 6.8× at fB=0.20.

**What it moves.** Nothing here. Unmeasured: a soak whose cold rung finds a narrower width, because
the cold start avoids the soak. That pattern would weaken the finding at the pattern the ladder
reseeded.

**Class.** C7.

**Proposed.** No interaction, shown by the soak. If C7's field lands (each width's ratio to its
first measured value), it carries each pattern's `rung` beside the ratio, so a reader can see a
ratio taken from a cold refit.

---

## X7. The ladder and the quarantine × the moment-floor carry

**The actions.** `_floor_unsupported_moments` (`sequential.py:859-922`, WP-1329), and the ladder and
quarantine.

**Order matters.** Yes. The floor is applied after the ladder decides, to the kept attempt and only
if it is not diverged (`:1699-1707`). It changes the next pattern's warm start. `floored[k]` is
recorded at the start of pattern k, before k's ladder runs (`:1531-1532`).

**Can a floored warm start be what diverges?** Yes. Pattern k's `warm` and `warm_staged` rungs start
from the floored modulus. Its `cold` rung starts from the initial models (`_fit_one` with
`previous=None`) and discards the floor. If k escalates to cold, `floored` still lists it, and
`SEQUENTIAL_MOMENT_HOLD`'s "reseeded to its floor on N successor patterns" counts it (`:2656-2674`),
although its kept fit never started there.

**Can a quarantined pattern's moments seed a successor?** No. A diverged entry leaves `previous`
unchanged, and `pending_floor` passes through it to the next pattern (comment `:1495-1501`), so the
floor reported is the last accepted pattern's. `on_error="skip"` clears it (`:1648-1650`).

**Measured.** No. Cr₂WO₆'s 150 K is the only floor on disk, and it is the last pattern, with no
successor. No test combines a floor with an escalation or a quarantine
(`tests/test_magnetic_series.py:587-624` tests the floor function alone).

**What it moves.** The record only. The floor moves the successor's starting point, never an entry's
value.

**Class.** C8 (the floor), C2 (`seeded_from`).

**Proposed.** No value interaction, by reading. The record fix rides with task 3's two fields:
`SeriesEntry.floored` set on the pattern whose *kept* attempt started from the floor, or kept beside
`seeded_from` and `rung` so that "floored, then kept cold" reads as such. Test to add: the magnetic
ramp with an injected divergence on the pattern after an unsupported one.

---

## X8. The quarantine × the median × the fence (both orders)

**The actions.** The quarantine (a diverged pattern joins no median), WP-1469's carve-out (an
above-fence pattern does join), and the fence (`reseed_factor` × the median of the accepted Rwp,
`_rwp_fence`, `sequential.py:1992-2001`).

**Order matters.** Yes: by walk position, and by direction under `direction="both"`.

**Mechanism.** `accepted_rwp` takes every kept pattern that is not diverged, including above-fence
and cold-kept ones (`:1713-1714`). A pattern's fence is taken before it joins (`:1679`). Pattern 0
is never fenced. From the third accepted pattern on, one outlier cannot move the median past the
second-highest value. Before that, the median is one value or the mean of two. So an early bad
pattern loosens the fence for its successors and a late one does not. Arithmetic: accepted
[0.30, 0.10] gives a fence of 0.25, against 0.125 for [0.10, 0.10]. A pattern at Rwp 0.20 passes
the first and escalates under the second. Under `direction="both"`, the backward walk has its own
median and its own unfenced first pattern, so one pattern can be above the fence in one direction
only. The quarantine half is pinned (`test_an_unrecovered_pattern_seeds_nothing_and_joins_no_median`,
`tests/test_sequential.py:1222`).

**Measured.** In part. On the soak, the fence follows the drift: 0.0195, 0.0280, 0.0365, 0.0479 as
each soaked pattern joins the median, every soaked pattern still above its fence. That is
WP-1469's design (a lasting change becomes the new normal; 18 of 18 flagged when such patterns were
quarantined, 7 when not). No family on disk has a bad first or second pattern.

**What it moves.** Nothing on disk.

**Class.** C1.

**Proposed.** A ruling that rides with C1. If the fence stays a trigger, arm it after a minimum of
accepted patterns, as the first-rung bound waits for `FIRST_RUNG_SAMPLES`. If it becomes a reported
number (C1's pick), state in its help entry that the first patterns are judged against a median of
one or two.

---

## X9. `reseed_factor=inf` × the scan's above-fence drop and the outlier report

**The actions.** `reseed_factor`, which sets both the fence trigger and the reported fence. The
discontinuity scan's drop of above-fence patterns (`sequential.py:2391-2392`). `SEQUENTIAL_RWP_OUTLIER`.

**Order matters.** No. One parameter feeds all three.

**Mechanism.** `reseed_factor` is not validated anywhere (`:1030`). `inf` makes `rwp_fence` inf
(`:1679`), so `SeriesEntry.above_fence` is never true. The scan then keeps above-fence patterns,
the outlier code never fires, and `_inside_before` finds nothing. `nan` behaves the same, since
every comparison is false. Zero or a negative factor makes the fence ≤ 0, so every warm rung
escalates (by reading).

**Measured.** Soak: four `SEQUENTIAL_RWP_OUTLIER` with the fence on and under `reseed=False`, none
at `inf`. tut05-broken: `inf` gains a `SEQUENTIAL_DISCONTINUITY` (the handover's *Gotchas*).

**What it moves.** Reported codes: outlier findings vanish and a discontinuity appears. No fitted
value moves.

**Class.** C1, C4.

**Proposed.** Fix: validate `reseed_factor` (finite and positive; what lower bound is part of C1's
ruling). And if C1 rules status-only with the fence kept as a reported statistic, give the trigger
its own switch (for example `reseed="status"`). Today the only way to get status-only, `inf`, also
deletes the report the pick wants to keep.

---

## X10. Rejected rungs and `verify_discontinuities` × the automatic profile interval

**The actions.** `attach_stationary_intervals` (WP-2002, gated by `Refinement._auto_intervals`), the
ladder's rejected rungs, and `_verify_discontinuities`' cold refits (`sequential.py:1813-1903`).

**Order matters.** No value interaction. The interval runs inside `fit`, after the result is
stamped and before the ladder judges it, and it never moves a value (`refine.py:5199-5208`).

**Mechanism.** `sequential.py` never mentions `_auto_intervals`. `_fit_one` builds a plain
`Refinement`, which defaults to `True` (`refine.py:2334`). So every rung pays the interval, rejected
or truncated, and so does every `.verify` cold refit (`sequential.py:1849-1855`). The trial path
sets it to `False` (`refine.py:2608`). `SeriesEntry.n_iterations` leaves these refits out.

**Measured** (reseed JSONs). Cr₂WO₆ 4 K: 49 evaluations recorded against 270 run, in 31 solver
calls. 150 K under status+`max_iter`: three rungs, two of them discarded, 2 533 recorded against
2 681 run in 20 calls. `verify_discontinuities` on a magnetic chain was not measured.

**What it moves.** Cost only.

**Class.** C2 (rungs), C4 (`verify_discontinuities`). Task 3 already names this fix.

**Proposed.** Fix: set `ref._auto_intervals = False` in `_fit_one` for every rung and verify refit.
Run `attach_stationary_intervals` once on the kept attempt (`best_ref`) after the ladder decides.

---

## X11. The carry policy × the width twin hold

**The actions.** `carry` (which values a warm start takes from its neighbour, `_carry_into`) and
WP-2002's width twin hold (`_hold_width_twins`, `refine.py:1031-1057`, approved 2026-10-23).

**Order matters.** Yes. The carry sets the start, and the hold freezes part of it.

**Mechanism.** `_collapse` frees every glob in one stage (`sequential.py:493-500`). On every warm
refit, the instrument X/Y and the phase Lorentzian widths are therefore free together. The twin
hold is asked at that stage's start (`refine.py:4423`) and again after a collapse
(`refine.py:4644-4651`). It decides on which columns are free, never on the answer, so it holds the
instrument column at the value it was carried in with. A cold staged plan refines X/Y in an
instrument-only stage before the specimen widths are freed. On a chain, the instrument split is the
carried one. That much is from the code. How the two carry policies reach different splits was not
traced.

**Measured.** The strict xfail in
`tests/test_acceptance_sequential.py::test_warm_start_iteration_cost_is_reported` (`:229-259`), on
CPD 1a-1h. Carrying everything but the scales (`CARRY`, `:85-86`) gives mean Rwp 0.1282, against
0.1256 carrying everything and 0.1258 independent. Values and QPA were not compared.

**What it moves.** Mean Rwp +0.0026 (2 % relative) under the restricted carry.

**Class.** C9.

**Proposed.** Measure before ruling `carry`: QPA against weighed for the two policies on CPD 1a-1h.
That costs about an hour an arm and is not run here. Candidate design for the batch: on a chain,
hold the twin columns at pattern 0's instrument-only value, the series form of "fix the instrument
from a standard" (`docs/practice.md` § Instrument and specimen widths refined together). The two
policies would then agree by construction.

---

## X12. The closing stage × path dependence

**The actions.** The closing stage on every pattern of both walks, and `direction="both"`'s
comparison (`_path_dependence_diagnostics`, `sequential.py:2942-3059`, 3σ).

**Order matters.** No. Both walks run the same plan.

**Measured.** `direction="both"`, with the closing stage on and off (`closing_window_tol=None`). The
gap is the largest |forward − backward| / √(σ_f² + σ_b²) over the patterns both walks measured. This
lane's mirror leaves out the code's noise floor, which only lowers gaps.

| family | closing on: largest gap | closing off: largest gap | flags on / off | forward evals on / off |
|---|---|---|---|---|
| thermal ramp | 0.00105σ (background c1) | 0.0177σ (profile y) | 0 / 0 | 127 / 106 |
| jump series | 2.4e-4σ | 9.0e-3σ | 0 / 0 | 79 / 61 |
| trigger series | 0.351σ (`phases.1.lor_strain`) | 0.379σ (same path) | 0 / 0 | 269 / 200 |

No `SEQUENTIAL_PATH_DEPENDENT` flag appears or vanishes. The closing stage narrows the gaps (17×
and 37× on the two toy ramps, 7 % on the trigger) at 1.2-1.35× the evaluations. Neither walk
escalated any pattern on these families.

**What it moves.** No flag, and the gaps shrink.

**Class.** C5, C9.

**Proposed.** No interaction that moves a flag, shown on three synthetic families. The real chain,
CPD with `direction="both"`, is two hours an arm and was not run. The handover's 7.05-14.2 esd
between the CPD chain and the independent fits is a different gap (chained against cold, not
forward against backward).

---

## X13. B7: `intermediate_ftol` along a chain

**The actions.** WP-1123's intermediate tolerance (1e-6), which WP-2002 kept with a 0.1-plain-esd
bar once the closing stage landed (`2002-batch/waiting.md` § B7), and the chain.

**Order matters.** Yes. Since WP-2002, a warm rung's `warm_refit` is an intermediate stage
(`RefinementPlan.stage_ftols`, `strategy/staged.py:418-440`). It stops at 1e-6, and the closing
stage then converges at 1e-9. Before the closing stage, `warm_refit` was the last stage, so the
tolerance reached only pattern 0's cold fit.

**Measured.** `intermediate_ftol=None` against the default, forward chain, with the closing stage
on and off:

| family | closing on | closing off |
|---|---|---|
| thermal ramp | 1.24e-5 esd (133 against 127 evals) | 4.0e-6 esd (112 / 106) |
| jump series | 2.5e-7 esd (84 / 79) | 5.7e-7 esd (66 / 61) |
| trigger series | 2.7e-4 esd (284 / 269) | 2.6e-4 esd (209 / 200) |

On the trigger, the per-pattern gap is about 3e-4 esd from pattern 0 onwards: set by the cold
multi-stage fit and carried, not amplified along the chain. These are reported esds. Plain esds
are f times larger, and f was not extracted; on the trigger, f below about 370 keeps the gap under
WP-2002's 0.1-plain-esd bar.

**Open.** cpd-1b's warm stage stopped at 136 evaluations at 1e-6 under the closing stage, against
410 at 1e-9 without it, and the closing stage ran away from that point (X3). The arm that separates
the two causes is CPD's first two patterns with the closing stage on and `intermediate_ftol=None`,
about 40 minutes.

**What it moves.** ≤ 2.7e-4 esd on three synthetic chains.

**Class.** C9 (`fit:plan`, by extending B7's approval to the series seat).

**Proposed.** No chain amplification on three families. Run the one CPD arm above before C9's
`_collapse` row is recorded, since it decides whether X3 is a closing-stage effect or a
tolerance-and-closing-stage effect.

---

## X14. B16: the bound test × the joint fit's parametric form test

**The actions.** `staged.bound_findings` (B16's two thresholds, both tier 3) and `multi.py`'s
parametric form test, which holds the columns it reports at a bound
(`at_bounds = bound_findings(…)`, `multi.py:1943-1946`, into `_parametric_form_tests`, `:1966`).

**Order matters.** One way. The bound test runs after the joint solve, the form test after it.

**What is known.** B4 was ruled option 1 (f stays on every reported esd,
`2002-batch/rulings.md:44`), so B16's 13× margin stands as measured (`rulings.md` § B16). That
margin was measured on 32 binding cases on FAP and Si SRM 640c, single fits, LM ≤ 128 columns or
TRF. A joint fit carries the shared columns plus each histogram's own, so it can pass
`BVLS_MAX_COLUMNS` (128, `optimize/lm.py:209`) at a modest histogram count. From there it leaves
the exact active set for the conjunction test, the regime B16's second pass was owed. That is
inferred from the column count. Not measured.

**What would settle it.** A joint parametric fit on one synthetic family, above 128 columns, with
its at-bound set checked against the exact active set of a ≤ 128-column refit of the same problem,
and whether `PARAMETRIC_FORM_REJECTED` changes between the two.

**Class.** C10. Its pick already waits on this: `PARAMETRIC_FORM_REJECTED` goes to tier 2 "once
clash B16 is measured".

**Proposed.** The measurement above, in the batch's second pass. No change until then.

---

## X15. The ladder × path dependence

**The actions.** The ladder, run separately in each walk of `direction="both"`, and the forward-
backward comparison.

**Order matters.** Yes. Each walk has its own median and fence (X8) and its own first-rung sample.
One pattern can escalate to cold in one walk and keep its warm rung in the other. The comparison
then sets a cold fit against a warm one, and the gap measures the ladder, not the path.

**Measured.** No. None of the three families measured with `direction="both"` (X12) escalated in
either walk.

**What it moves.** Possibly a `SEQUENTIAL_PATH_DEPENDENT` flag. Unmeasured.

**Class.** C5 (the comparison), C1 (the trigger).

**Proposed.** If C5's field of gaps lands, each row carries both walks' `rung`, so a gap between a
cold fit and a warm one reads as such. A measurement would need a family that escalates in one
direction: planted with `direction="both"` (about 5 minutes an arm).

---

## Bugs and docstring errors (fixes, not rulings)

- `first_rung_factor`'s docstring, "A bound that bites costs an escalation and never an answer"
  (`sequential.py:1104-1107`), is false twice: X1 outcome 1 costs no escalation, and planted T087
  costs an answer.
- `reseed`'s docstring (`sequential.py:1079-1085`) is broken by the forced escalation (X2).
- The `_ladder` docstring says `_better` "prefers a converged fit" (`sequential.py:559-561`). It
  prefers a non-diverged one (X5).
- `reseed_factor` is not validated (`sequential.py:1030`; X9).
- Every rung and verify refit pays the automatic profile interval, with no gate in
  `sequential.py` (X10; task 3).
- The first-rung sample sums the warm and closing stages (`sequential.py:1604`, `:1724`), while
  the cap applies to each stage separately through `closing_stage()` copying `max_iter`
  (`strategy/staged.py:390-394`). So the bound is calibrated on one quantity and applied to another
  (X1).

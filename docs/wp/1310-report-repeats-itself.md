# WP-1310 — the report repeats itself: stage dedup, the declared wavelength, the empty column

Milestone: unscheduled · Status: ✅ 2026-09-16 — four of six landed; the bound test is 1434 and the caller's hold is 1435
Depends on: —

## Goal

Every surface in this WP's class answers with a fact or a refusal, never with a
well-formed lie. Two of the three original defects landed before the WP was
opened and were verified discharged on arrival (2026-09-16, § Context 1 and 2).
What is left: `to_table`/`write_csv` answers a derived path with the curve or a
refusal, a `BOUND_HIT` on a converged result is true of that result, and a
parameter a caller pinned says which declaration won.

## Context

Six defects, one class: the repo's rules are strictest about a silent wrong
answer, and each of these is one (issues #106, #123, #162, #231, #211, #273).
Two were already fixed when this WP was opened, which the 2026-09-16 prune
below records rather than deletes — the measurements are still the fixtures
that verify them.

**1. Per-stage diagnostics repeat (issue #106). Superseded 2026-09-16: fixed
in WP-1302 (`a21e17ba`, 2026-08-29), three days before this WP was filed.**
The defect as measured: a real two-phase lab refinement (YBaCo₄O₇, 4787
points, 31 free parameters, staged plan) returned **96 `HIGH_CORRELATION`
diagnostics for 16 distinct pairs**, each re-emitted 2–7 times as the plan
advanced, 14 of 16 with the identical ρ to three decimals. The two entries
that mattered sat at the tail where a context-budgeted consumer truncates:
`axial_sl ~ axial_hl` at ρ = −1.000 and the single `STAGE_MAX_ITER`.
`_dedup_high_correlations` (`refine.py:2765`) now keeps one finding per pair,
the worst |ρ| among the stages that flagged it, naming every such stage in the
message; the unfiltered per-stage list still reaches the stage report and the
history node, so the trajectory that shape 1 was accused of losing is held.
Measured end-to-end 2026-09-16 on a cumulative LaB6 plan that frees
`axial_sl`/`axial_hl` in stage 2: the pair is flagged in four stages and the
result carries **one** entry, ρ = −1.000, naming all four.

**The ρ half of the bar is met; the `STAGE_MAX_ITER` half is met only in the
rendered view, and the WP's original wording about ranking does not hold.**
`refine.py:2120` appends the deduped correlations to what the stage loop
collected, sorted by |ρ| descending, but `_build_result` then appends the
post-fit diagnostics — `_max_iter_diagnostics` at `refine.py:3335` among them
— so in the **stored** list `STAGE_MAX_ITER` sits *after* every correlation.
What bounds its position is `_cap_high_correlation`
(`schemas/results.py:869`), which is documented **for rendering only** and
must never touch a stored list: it keeps the worst ten and one
`HIGH_CORRELATION_OMITTED` line, so a summary shows `STAGE_MAX_ITER` within a
bounded number of lines however many pairs fired. A consumer truncating
`result.diagnostics` itself still loses it. That residue is the original
shape-3 question — rank rather than dedup — which this WP said to measure
before deciding. Measured: dedup alone takes the fixture from 96 to 16 and
the render cap bounds the rendered view at 11 correlation lines, so ranking
buys ordering inside the stored list and nothing else. Recorded, not fixed.

**2. The declared wavelength is per-call (issue #123). Superseded 2026-09-16:
fixed in WP-1134 (`a173cb84` and `61cbce11`, 2026-08-25), a week before this
WP was filed.** The defect as measured: on the single-histogram path λ was
snapshotted per call, and a stage writes the refined λ back onto the
instrument, so run 2 of a LaB6 fit with λ declared 400 ppm low reported
−18.15 ppm "from the declared 1.540626 Å" — a value nobody declared.
`_declared_wavelengths` (`refine.py:4016`) is now the one authority,
snapshotted in `__init__` and again on an instrument `edit`; `multi.py:49` and
`sequential.py:119` import it rather than open-coding the comprehension; a
`branch` inherits the root's reference; the checkout caveat is in the
docstring. Every clause of the original task is discharged. What is left is
the measurement.

**3. `to_table`/`write_csv` is a second path resolver (issue #162). Live,
confirmed 2026-09-16.** `SeriesResult.to_table` (`schemas/sequential.py:397`)
calls `SeriesEntry.value(path)`, which scans `self.parameters` and returns
`None` for anything not a refined parameter — so `to_table(paths=["r_bragg.LaB6"])`
yields the header `['r_bragg.LaB6', 'r_bragg.LaB6_esd']` over rows of `None`.
`qpa.` behaves identically and always has. `resolve_trajectory`
(`schemas/sequential.py:346`) is documented as "the one authority for turning
a display path into a curve" and already serves `plot_trajectory` and
`gui/series.py`; this path just does not go through it. Fix chosen (the
issue's option 1, its author's lean): route through `resolve_trajectory`, and
emit **no `_esd` column for kinds that have none** — an agreement index has
`stderr = None` by design, and a column of blanks invites exactly the "zero or
absent?" ambiguity the trajectory work avoided. The class is
[1076](1076-result-row-honesty.md)'s: a declared shape whose empty state reads
as an answer.

**4. `BOUND_HIT` survives the stage that earned it (issue #231, folded from
the mailbox 2026-09-03; live, confirmed 2026-09-16).** The guard is generated
while a stage runs; when a later stage moves the parameter off the bound — the
normal, desired outcome of a staged plan — the warning survives onto the
converged result, with the message *"<path> refined to its bound"* and the
suggestion *"widen the bound or fix the parameter"*, both false of the
converged fit. The seam is `refine.py:2086`: every non-correlation code is
appended straight into `diagnostics` as each stage ends, and the only other
`_guard_diagnostics` call site is the single-stage path at 2220, so nothing
re-evaluates at convergence.

Reproduced synthetically on the repo's own `make_lab6`, cell seeded 0.5 %
large so stage 1 (only `zero_shift` free) drives the shift onto its ±0.02°
bound absorbing a cell error, stage 2 frees the cell and it returns:

| | `zero_shift` | `a` | `BOUND_HIT` |
|---|---|---|---|
| stop after `zero` | +0.020000° (100 % of bound) | fixed | True |
| then free the cell | +0.000001° (0 % of bound) | 4.156600227 | **True** |

The second row is a **fully successful fit** — truth is `a = 4.15660`,
`zero_shift = 0` — carrying a warning about a limit it is five orders of
magnitude from. `BOUND_HIT_RTOL = 1e-10` (`strategy/staged.py:1028`) is
**not** implicated: the tolerance is right and `bound_findings` is right for
the vector it is handed. The defect is *which vector reaches the final
diagnostics list*.

**It is convincing, which is why it is more than cosmetic.** Two independent
readers built confident wrong physical mechanisms on one before checking the
parameter's own value: on a real capillary synchrotron fit `BOUND_HIT` fired
on `capillary_offset_along_beam` in five of five fits, read as the specimen
offset being pinned and load-bearing and therefore the absolute cell values
untrustworthy; the second hypothesis was that the ±1 mm default
(`schemas/instrument.py:788`) is too tight for that instrument, with seven
GSAS-II refinements of the same specimens carrying 1.2–4.5 mm equivalents as
circumstantial support. **One experiment killed both**: re-running at ±1, ±5
and ±20 mm gave results bit-identical to six significant figures (same cell,
same sigma, same Rwp), the offset converging at 3.3 % of the ±1 mm bound on
the *opposite side of zero* from the bound hit in an early stage. The genuine
finding in that fit was the `HIGH_CORRELATION` beside it, which *is* evaluated
at convergence and *is* real; the bound warning cost two rounds of misdirected
analysis.

Three fixes, ranked by the reporter, and the first two are this WP's:
**(1) re-evaluate the guards on the converged vector** before building the
final diagnostics list, so the final list means exactly "true at
convergence" — a parameter genuinely at a bound at the end still reports;
**(2) carry the stage identity** on the finding and distinguish "hit during
stage N, resolved by convergence" from "at bound at convergence" — a transient
excursion is a useful signal about plan ordering even when it resolves, but
this is a design call rather than a fix; **(3) add `diagnostics` to
`StageResult`**, which today carries `name, status, n_iterations,
cost_initial, cost_final, freed, ftol, n_constraint_truncations, held,
released` and no diagnostics, so the aggregated list on `RefinementResult` is
the only view and it is undated. (1) and (3) are complementary and the
reporter offers a PR for either. WP-1076's rule applies to (3): a declared
field needs its writer named at review, and `staged.bound_findings` stays the
one bound test feeding both surfaces, pinned set-equal rather than re-derived.

Related and *not* this WP: `status == "converged"` on a fit whose diagnostics
say `MODEL_FAR_FROM_DATA` is
[1336](1336-the-fit-does-not-say-it-is-unusable.md).

**5. A plan frees a parameter the caller pinned (issue #211, folded from the
mailbox 2026-09-01).** A stage's `turn_on` glob frees a parameter the caller
pinned with `vary=False` (`ParameterTable.set_vary` cannot tell a deliberate
pin from a default, and `apply_to_models` writes the value back but never
`vary`), so the value moves while `Parameter.vary` still reads `False`.
WP-1208's rule already says a plan *replaces* the vary flags rather than
continuing them, so the defect is the record, not the precedence: which
declaration won has to be said (a diagnostic naming the pinned paths the plan
freed, and `vary` written back or reported per stage). Measured cost in the
issue: an invalidated pin-and-scan study, and it is the failure mode of
calibrate-on-a-certified-standard.

**Measured 2026-09-16, and the proposed diagnostic cannot be built on `vary`.**
Reproduced first: a LaB6 whose six cell parameters are declared `vary=False`,
fitted under a plan whose second stage carries `phases.*.cell.*`, refines
`cell.a` from the declared 4.15660 to 4.156599952 while `ref.structure`
still reads `vary=False` and no diagnostic names it. The row on
`RefinementResult.parameters` does say `vary=True`, so the result and the
fitted model contradict each other about the same parameter.

The trouble is the discriminator. On the shipped LaB6, **41 of 42 entries are
declared `vary=False`**, because that is the default rather than a decision, so
"declared fixed and freed by the plan" names almost everything a plan touches:

| plan | frees | of which declared fixed | with the cell pinned |
|---|---|---|---|
| `mccusker_default` | 17 | 16 | 17 |
| `mccusker_structural` | 21 | 20 | 21 |
| `lab_bragg_brentano` | 21 | 20 | 21 |
| `lab_calibrate` | 17 | 17 | 17 |

The user's pin moves one number in seventeen. A diagnostic keyed on it would
print sixteen lines on every ordinary fit and seventeen on the one that matters,
which is not a signal. `__pydantic_fields_set__` does separate an explicit
`vary=False` from a default one **in memory**, and does not survive a JSON round
trip — every field comes back set — so a project opened from disk reports every
parameter as deliberately pinned, and that is the commonest path.

So the missing thing is not a diagnostic. **A user's pin has no authority to be
read off**, exactly as a user's *tie* had none before WP-1070 gave it
`Refinement._ties` and made that the one place a user's declaration lives. The
same shape would fix this: a pin the caller states, which a plan's glob reports
rather than silently overriding. That is a feature rather than the fix this WP
scoped, so it is **asked rather than taken here**.

**6. The bound test is a function of the stage's `ftol` (issue #273, folded
from the mailbox 2026-09-15).** Measured read-only on `origin/main`
`2ba7a9a3` by moving a declared bound to the wrong side of a converged optimum
on the FAP and Si SRM 640c fixtures and freeing that parameter for one stage,
24 cases. TRF keeps its iterates interior, so how close a boundary solution
lands depends on when it stopped. At the shipped tolerances (1e-9, and 1e-6
for intermediate stages) it lands within 1e-13 of the bound and `BOUND_HIT`
fires. At `ftol ≥ 1e-4` it stops 1e-7–1e-6 away, up to 16 380× `BOUND_HIT_RTOL`,
with `status="converged"`, ordinary esds, and nothing fires: nine of the 24
cases. Two smaller facts. `bound_findings`' docstring says the test is scipy's
own; scipy fills `active_mask` with `find_active_constraints(x, lb, ub,
rtol=xtol)` and rietx passes `XTOL = 1e-12` (`optimize/least_squares.py`), so
`BOUND_HIT_RTOL = 1e-10` is scipy's rule at 100× its tolerance, and two rows
fire with `active_mask = 0`. And a softplus lower bound is −∞ internally, so
`BOUND_HIT` never fires from below on a scale or a width (1311's Inherited
records that as intended). Two fixes the issue admits: read `active_mask` off
the `OptimizeResult` the solve already returns, one source of truth; or scale
the test to the stage's `ftol`. Either lands on § 4's seam: re-evaluating the
guards on the converged vector inherits whatever tolerance the test uses, so
the tolerance and the vector are one change. #231 is a stale flag; #273 is a
missing one.

**Measured 2026-09-16, and it rules out both fixes the issue names.** Fixture:
`make_lab6` with a ±0.02° zero shift absorbing a 500 ppm cell error, the final
stage's `ftol` swept. § 4's fix already takes half the issue: the test now runs
on the **last** stage's guard, so the intermediate 1e-6 can no longer reach it
and only a caller's own coarse final `ftol` is left.

| final `ftol` | `zero_shift` | gap from bound | gap/esd | `active_mask` | `BOUND_HIT` |
|---|---|---|---|---|---|
| 1e-9, 1e-6 | 0.0199999999999934 | 6.58e-15 | 2.3e-12 | 1 | fires |
| 1e-4, 1e-3 | 0.0199999998757806 | 1.24e-10 | 4.4e-08 | **0** | silent |
| 1e-2 | 0.0083852136668427 | 1.16e-02 | 2.36 | 0 | silent |

Row 2 is the defect: 1.2e-10 from the bound is *at* it for any physical
reading, and the fit reports `converged` with ordinary esds and says nothing.
Row 3 is a stage that genuinely stopped early in the interior, correctly
silent.

**Fix (a), `active_mask`, changes nothing**: scipy's own mask agrees with
rietx's test on every row of this sweep, row 2 included, so adopting it would
make `bound_findings`' docstring honest and fix none of the issue's nine cases.
**Fix (b), scaling to `ftol`, has nothing to calibrate against**: this fixture
lands 1.2e-10 from the bound at `ftol` 1e-4 while the issue's landed 1e-7–1e-6
at the same `ftol`, four orders apart, so a rule reading `ftol` alone is fitted
to whichever fixture wrote it.

What does separate the rows is **the gap against the parameter's own esd**,
which is scale-free — independent of the bound's magnitude, the parameter's
units and the stopping tolerance alike. The two at-bound rows sit at 2.3e-12
and 4.4e-08, the interior row at 2.36: seven orders of margin, and any
threshold in ~[1e-3, 1e-1] separates all six cases where the absolute `rtol`
splits them. It is also the standard reading — a parameter whose distance to
its limit is far below what the data can resolve is at that limit.

That is a third option the issue does not list and it changes what an existing
diagnostic means, so it is **the maintainer's call and is asked rather than
taken here**. Open sub-questions if it is adopted: the threshold; what happens
where the esd is `None` (`unmeasured_rows`, a fixed or blind direction), where
the honest answer is probably `at_bound=None` rather than a fallback to the
absolute test.

## Non-goals

- **Not #166's esd notation** — the maintainer ruled it not worth a figure
  regeneration now; it rides whichever change next touches
  `make_figures.py`.
- **Not new diagnostics** — flat-direction reporting and the walking-
  parameter flags are [1311](1311-walking-parameter-bounds.md)'s.
- **Not a change to what a fit computes.** Every fix here is about what
  crosses the surface, and every accepted number stays bit-identical.

## Tasks

- [x] **Superseded, not done here** — stage dedup (§ 1) landed in WP-1302 and
      the construction-snapshot λ (§ 2) in WP-1134, both before this WP was
      filed. Verified on arrival 2026-09-16 by reading the seams.
- [x] Verified both by measurement, 2026-09-16. #123 needs nothing: WP-1134
      shipped `test_declared_is_the_constructed_lambda_so_run_stage_reports_cumulatively`
      (`tests/test_wavelength_freedom.py`), which is the issue's own two-call
      case quoting its +417/−18 ppm numbers, and it passes. #106 is fixed and
      unit-tested, but nothing pinned the **routing** — that the stage loop
      still collects into `correlation_hits` and calls the dedup — so a
      regression there would pass every test in
      `tests/test_high_correlation_dedup.py`.
- [ ] One end-to-end test for that routing: a cumulative plan freeing
      `axial_sl`/`axial_hl`, asserting the result carries one entry naming
      every stage that flagged it. Measured at 0.93 s, so it belongs in the
      fast selection.
- [ ] `to_table`/`write_csv` through `resolve_trajectory`; `_esd` columns
      suppressed where `stderr` is `None`; a derived path that
      `resolve_trajectory` cannot serve refuses by name (§ 3).
- [x] Re-evaluate the guards on the converged vector before the final
      diagnostics list is built, so a `BOUND_HIT` on a result is true of that
      result (§ 4, fix 1). `staged.bound_findings` stays the one bound test,
      and the fix restores WP-1076's set-equality, which the staleness had
      quietly broken inside a single result.
- [x] Settle the tolerance (§ 6). **Measured, and both of the issue's options
      are ruled out** — the table in § 6 has the sweep. Handed on as
      [1434](1434-the-bound-test-asks-the-wrong-question.md), which carries the
      measurement, the prior art and the redesign: the test asks how *near* θ
      is to the limit, and the question worth asking is whether the limit
      carried load.
- [x] A plan that frees a pinned path says so (§ 5). **Measured, and the
      diagnostic the issue proposes cannot be built on `vary`** — 41 of 42
      entries are declared fixed by default, so it would name 16 paths on an
      ordinary fit and 17 on the one that matters. Handed on as
      [1435](1435-a-hold-the-caller-declares.md): the missing thing is an
      authority for a caller's hold, which is GSAS-II's `'h'` constraint and
      WP-1070's shape, not a message.
- [x] Tests: six `to_table` cases across the trajectory kinds
      (`tests/test_sequential.py`), four on the bound seam
      (`tests/test_bound_hit_at_convergence.py`), one on the dedup routing
      (`tests/test_high_correlation_dedup.py`), and the manual's series
      chapter for `positions` and the derived-path export. No pinned-path
      fixture: that case moved to 1435 with the feature it needs.
- [x] Skill: one row, in `references/series.md`, for what `to_table` now takes
      and what it refuses (`api.md` regenerated with the docstring). Nothing
      in the body: the two changes a driving agent would act on are the ones
      handed forward, and their WPs carry the rows. `BOUND_HIT`'s existing row
      still reads correctly — a bound on a converged result now means what the
      row already said it meant.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_fitreport_layers.py tests/test_acceptance_wavelength.py tests/test_sequential.py
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

The bar: `to_table` on a derived path returns numbers or a refusal, never
`None` rows; a fit whose early stage hit a bound and whose last stage did not
carries no `BOUND_HIT`; a fit still at a bound at convergence still carries
one; a plan that frees a pinned path names it. All accepted fit values
bit-identical throughout.

The shipping PR carries `Closes #106`, `Closes #123`, `Closes #162`,
`Closes #231`. #123 closes on the verification alone, its fix and its
regression test both having shipped in WP-1134; #106 closes on the
verification plus the one routing test this branch adds. **#211 and #273 stay
open**, re-scoped onto [1435](1435-a-hold-the-caller-declares.md) and
[1434](1434-the-bound-test-asks-the-wrong-question.md): each was filed with a
fix that the measurements here rule out, so closing either on this branch
would lose the reason.

## References

- Issues #106, #123, #162 — measurements and fix-shape analyses.
- [1058](1058-report-delivery.md) — stage reports as the opt-in trajectory;
  [1076](1076-result-row-honesty.md) — the declared-name class.
- `docs/skill/rietx/` — the `WAVELENGTH_CALIBRATION` row whose reading this
  must match.

## Handover log

### 2026-09-16 — four of six, and the other two were filed with the wrong fix

Three of the six defects this WP collected are gone from the package, and a
fourth was never there: two of the three it was opened for had already been
fixed a week before it was written, by WP-1134 and WP-1302, and nobody had
checked the tree. A reader of a rietx result can now trust three things they
could not this morning. A warning that a parameter ended on one of its limits
means that it did, rather than that some earlier stage pushed it there and a
later one pulled it back. Exporting a series to a table or a CSV gives the
weight fractions and the agreement indices as numbers, and refuses a name no
pattern carries instead of handing back a column of blanks. And the report's
correlation list is now pinned end to end, so the deduplication that stops it
repeating itself cannot quietly stop being called.

The other two items are the interesting ones, because both were filed with a
proposed fix and both proposed fixes are wrong. Neither was implemented, and
each is handed on as a WP carrying the measurement that rules its own fix out,
so the next session does not begin by building what has already been
disproved.

**Done.** Verified #106 and #123 discharged by measurement rather than by
reading, and closed the one gap either had left: nothing pinned that the stage
loop still routes correlations through `_dedup_high_correlations`, so a
regression there would have passed all eight of that file's unit tests
(`tests/test_high_correlation_dedup.py`, one real fit, 0.27 s). Routed
`to_table`/`write_csv` through `resolve_trajectory`, added `Trajectory.positions`
so a table row and a trajectory that skips patterns can be aligned, and
suppressed the `_esd` column for kinds that have none. Made `BOUND_HIT`
describe the converged vector by holding it back through the stage loop and
re-taking it from the final guard. Wrote WP-1434 and WP-1435 for what is left,
pushed forward references into 1311 and 1336, and gave the series skill
reference a row for the new `to_table` behaviour.

**Measured.**

- #123 is fixed *and* tested: WP-1134 shipped the issue's own two-call case as
  `test_declared_is_the_constructed_lambda_so_run_stage_reports_cumulatively`.
  Both calls report +400.2 ppm against the declared 1.539984 Å, which is the
  injected error. Nothing to write.
- #106 end to end: a cumulative LaB6 plan freeing `axial_sl`/`axial_hl` flags
  the pair in four stages and the result carries one entry at ρ = −1.000
  naming all four.
- #231: with the zero shift bounded at ±0.02° and a 500 ppm cell error to
  absorb, stage 1 parks it at 0.0199999999999934 and stage 2 returns it to
  5.5e-07 with the cell recovered to 4.15659996805922 against a truth of
  4.15660. The warning used to survive onto that fit. The values either side
  of the change are bit-identical.
- #273, which rules out both of the issue's fixes. scipy's own `active_mask`
  agrees with rietx's test on every row of an `ftol` sweep, including the row
  1.24e-10 from the bound where rietx goes silent, and scipy's documentation
  disclaims `active_mask` for TRF in as many words. Scaling to `ftol` has
  nothing to calibrate against: this fixture lands 1.24e-10 from the bound at
  `ftol` 1e-4 where the issue's landed 1e-7 to 1e-6. The gradient does
  separate them, 1.755e+08 on both binding rows against 6.19e-04 at an
  interior optimum, and it does so identically at every `ftol`. Full table in
  § 6 and in WP-1434.
- #211, which rules out the diagnostic the issue asks for. 41 of 42 entries on
  the shipped LaB6 are declared `vary=False` because that is the default, so
  `mccusker_default` frees 17 paths of which 16 were already declared fixed,
  and a caller's pin moves that to 17. `__pydantic_fields_set__` separates an
  explicit pin from a default in memory and not across a JSON round trip,
  which is how a project loads from disk.
- Counts, `[dev]` venv (no jax/torch), darwin, numpy backend. On the branch
  alone: fast selection **5158 passed, 133 skipped**, against 5154/133
  measured mid-session after the `BOUND_HIT` source change and before its four
  tests landed — +4 passed, no new skip. This session added 11 tests (1
  routing, 6 `to_table`, 4 bound). Acceptance command 138 passed. **On the
  merged tree, which is what lands: 5165 passed, 133 skipped**; the +7 over
  the branch is WP-1431's, which merged into main mid-session, so the two
  parents' additions do not sum and only this number describes the result.
  Wall clock 138–295 s across four runs of one selection, which is machine
  state rather than any change here. The full selection did not run: nothing
  here can move a measured number, every change being what crosses a surface.

**Gotchas for whoever picks up 1434 or 1435.**

- The `BOUND_HIT` fix already took half of #273. The test now runs on the
  **last** stage's guard only, so `RefinementPlan.intermediate_ftol` (1e-6)
  can no longer reach it and only a caller's own final `ftol` is left.
- It also made WP-1076's set-equality true rather than nearly true.
  `RefinedParameter.at_bound` has always been projected from the last stage's
  `guard.at_bounds`, so before this a single result could carry
  `at_bound=False` on a row and `BOUND_HIT` in the diagnostics about that same
  parameter. The skill's `BOUND_HIT` row already told an agent the two were
  the same finding, which was not quite true when it was written and is now.
- `StageResult` still carries no diagnostics, so a stage's own findings reach
  only its history node. That is issue #231's third fix and nobody has taken
  it.
- The `STAGE_MAX_ITER` half of this WP's original bar does not hold as
  written. In the **stored** diagnostics list the deduped correlations precede
  every post-fit code, `_max_iter_diagnostics` among them, so a consumer
  truncating `result.diagnostics` loses it. What bounds its position is
  `_cap_high_correlation`, which is rendering-only by design. Recorded in § 1,
  not fixed.

**After the entry was first written.** `/code-review high --fix` raised four.
Two it fixed: the series skill row claimed a refusal lists the phases that
exist, which is true only of a derived path, and the checklist said "Skill:
none" while the branch added one. Two it raised and left, both taken here: the
WP-1434 title used "bound" as the past tense of *bind*, which stutters in an
index row, and the § What fires paragraph was left ragged by the 1310 clause
coming out. Then the merged-tree run caught one the branch never would have:
the skill row's example phase was the TiO2 polymorph whose name this package
once carried, which `test_no_stale_name` greps for, so the example became the
other half of the same canonical QPA pair. That was a miss of mine rather than
the merge's — the row landed after this session's last full run. WP-1431 hit
the identical trap on the same day, and naming the token here to explain it
trips the guard a second time, exactly as prose about a closing keyword is a
closing keyword.

**One thing to know about how this landed.** PR #352 was opened as the
`/wp-start` claim draft and **merged at 18:32 while the session was still
running**, carrying the first six commits. Everything after it — the two
forward WPs, the skill row, this entry, the review pass — was stranded on a
branch whose PR was already closed, and went up as a second PR. The claim draft
carried no closing keyword, so #106, #123, #162 and #231 close on that second
PR rather than on #352.

**Next:** nothing on this WP. 1434 starts by capturing the gradient on
`StageOutcome`, because no decision there can be made without it; 1435 starts
with `Refinement._holds` on WP-1070's model, because every other task reads it.
Neither is blocked. 1311's displacement bound reports through the machinery
1434 changes, so it should land before or after that WP rather than beside it.


- **2026-09-16** — claimed, and pruned on arrival before any work. Two of the
  three headline tasks were already fixed when this WP was filed on 2026-09-01:
  the stage dedup by WP-1302 (2026-08-29) and the construction-snapshot
  wavelength by WP-1134 (2026-08-25). Both are recorded as superseded in
  Context rather than deleted, because their measurements are the fixtures that
  verify them. The three mailbox
  entries (#231, #211, #273) were each checked against the tree and are all
  live; they are folded into Context as § 4, 5 and 6 and the mailbox is
  consumed. Net: one original task survives (§ 3) and three inherited ones
  join it, with #273 settling on § 4's seam rather than standing alone.


- **2026-09-01** — created, from issues #106/#123/#162 (2026-09-01 triage).
  Settled: fix shapes chosen as above (stage-union, construction snapshot,
  resolver routing); first open item is measuring shape 2 against shape 3 on
  the #106 fixture before touching ranking.

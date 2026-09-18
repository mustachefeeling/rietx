# WP-1434 — the bound test asks whether the value is near its limit, never whether the limit was binding

Milestone: unscheduled · Status: 🔄 2026-09-18 — claimed by @yue-here
Depends on: — (1310 landed the vector half; this is the tolerance half)

## Goal

`BOUND_HIT` fires when a declared limit **carried load** on the answer, and
stays quiet when it did not, whatever tolerance the stage stopped at. The
report a caller reads carries the evidence for that claim rather than a bare
flag.

## Context

From issue #273, and from [1310](1310-report-repeats-itself.md), which fixed
the other half and measured this one into a different shape than the issue
filed it in.

**What 1310 already did.** `BOUND_HIT` used to be appended to the result as
each stage ended, so a parameter pressed onto its limit in stage 1 and back in
the interior at convergence still carried the warning. That is fixed: the
findings are discarded through the stage loop and re-taken from the final
guard, which is the same object `RefinedParameter.at_bound` is projected from,
so the two surfaces of one bound test are now set-equal
(`tests/test_bound_hit_at_convergence.py`). One consequence reaches here: the
test now runs only on the **last** stage, so `RefinementPlan.intermediate_ftol`
(1e-6) can no longer reach it and only a caller's own final `ftol` is left.

**The defect that survives.** `bound_findings`
(`strategy/staged.py:1377`) decides by distance: is θ within
`BOUND_HIT_RTOL = 1e-10` of the limit. TRF keeps its iterates strictly
feasible, so how close a boundary solution lands is a function of when the
solver stopped. Measured 2026-09-16 on `make_lab6` with a ±0.02° zero shift
absorbing a 500 ppm cell error, final `ftol` swept:

| final `ftol` | `zero_shift` | gap from bound | \|grad\| | `active_mask` | `BOUND_HIT` |
|---|---|---|---|---|---|
| 1e-9, 1e-6 | 0.0199999999999934 | 6.58e-15 | 1.755e+08 | 1 | fires |
| 1e-4, 1e-3 | 0.0199999998757806 | 1.24e-10 | 1.755e+08 | **0** | **silent** |
| 1e-2 | 0.0083852136668427 | 1.16e-02 | 5.23e+07 | 0 | silent |
| interior optimum, any `ftol` | 0.0000008957961037 | 2.00e-02 | 6.19e-04 | 0 | silent |

Row 2 is the defect. A parameter 1.2e-10 from its limit is on it for any
physical reading, and the fit reports `converged` with ordinary esds and says
nothing. Issue #273 found nine such cases in 24, on the FAP and Si SRM 640c
fixtures.

**Both fixes the issue names are ruled out, by measurement.** *Read
`active_mask`*: scipy's own mask agrees with rietx's test on every row above,
row 2 included, so adopting it would fix none of the nine cases. scipy's
documentation disclaims it for this solver in as many words — "might be
somewhat arbitrary for 'trf' method as it generates a sequence of strictly
feasible iterates and `active_mask` is determined within a tolerance
threshold". *Scale the test to `ftol`*: this fixture lands 1.2e-10 from the
bound at `ftol` 1e-4 where the issue's fixtures landed 1e-7 to 1e-6, four
orders apart at one tolerance, so a rule reading `ftol` alone is fitted to
whichever fixture wrote it.

**The question is wrong, which is why no tolerance answers it.** "How close is
the value to the limit" is not what a caller needs to know. "Did the limit
change the answer" is, and it has a standard answer: an active set is
identified by the multiplier, never by proximity. At a limit that is carrying
load the gradient keeps pushing outward, and the table above shows it doing so
identically at every `ftol` — 1.755e+08 on both binding rows against 6.19e-04
at a genuine interior optimum, a separation of eleven orders where distance
gives none.

**The repo already answers this question correctly one door along.**
`CONSTRAINT_ACTIVE` (`refine.py:2953`) fires "when the answer-producing stage
**pressed** a constraint", counts truncations rather than distances, examines
only the stage whose θ becomes the result, and is `info` rather than `warning`
because landing on a constraint face is what a constrained driver is for. Its
docstring is the design note for this WP. The differences: it covers the
linear-inequality constraints of the `lm` driver and a box bound is not one,
and scipy's TRF exposes no accepted-point hook, so the evidence has to come
from the gradient the solve already returns rather than from a clamping count.

**Prior art.** Coelho (2005), *J. Appl. Cryst.* **38**, 455 — TOPAS's bound
handling removes a parameter from the conjugate-gradient loop when a limit is
violated and reinstates it on termination, so "at a bound" there is a state
during solving rather than a property of the converged vector. Nocedal &
Wright, *Numerical Optimization* (2nd ed.) ch. 12 and 16 for active-set
identification by multiplier sign, and Gill, Murray & Wright, *Practical
Optimization* §5.5 for the identification tolerance. TOPAS is closed and BGMN
is GPL: papers and concepts only, no ported code.

**A gradient is not free of judgement either.** The sign alone does not
discriminate, because at an interior optimum the gradient is small and its
sign is arbitrary — measured above, "pushes outward" reads true at the
interior optimum too. The test needs the magnitude, and the natural
normaliser is the optimality measure the solver already compares against
`gtol` (`OptimizeResult.optimality`, the projected-gradient norm). Row 3 is
the case to keep honest: the parameter is nowhere near its limit but the
gradient is large, because the stage stopped early en route. That is a
`STAGE_MAX_ITER`-shaped statement and must not become a `BOUND_HIT`, so the
test stays a conjunction — near the limit **and** still pushed into it.

**Three corrections, 2026-09-18, checked against the tree on arrival.**
`StageOutcome` is a name this WP and 1310 both use and no module defines. The
carrier is `LSQOutcome` (`optimize/least_squares.py:174`), which `refine.py`
reads and which already holds four WP-1076-shaped fields with named writers;
`LMOutcome` (`optimize/lm.py:205`) is the `lm` driver's half. Nothing else in
§ Context moved. The line numbers above are refreshed: WP-1311 landed on
2026-09-18 and grew `staged.py` by about 350 lines. And `bound_findings` takes
`(bounds, free, theta)` and no outcome, while its one caller `check_guards`
(`staged.py:1491`) already has `outcome` in hand, so the gradient reaches the
test through a signature change and not through new plumbing.

## Non-goals

- **Not which parameters get bounds.** The geometry-scaled displacement
  bound, the Biso flag and the rest are
  [1311](1311-walking-parameter-bounds.md)'s, which reports through this
  machinery. It closed 2026-09-18 and decided to *keep* the bounds it found —
  the ±1 mm on `sample_displacement`, the two capillary offsets and the 25 Å²
  Biso cap — on the maintainer's ruling, so what this WP inherits is settled
  rather than pending. Its four new diagnostics fire on no acceptance fixture,
  which is the baseline the last task measures against.
- **Not the softplus floor.** A softplus lower bound is −∞ internally so
  `BOUND_HIT` never fires from below on a scale or a width; 1311's Inherited
  records that as intended and it is not revisited here.
- **Not a change to what a fit computes.** Every accepted value stays
  bit-identical; this is what crosses the surface.

## Tasks

- [x] Capture the gradient and the optimality measure on `LSQOutcome`
      (`optimize/least_squares.py:174`), from the `OptimizeResult` both drivers
      already produce. A declared field needs its writer named at review
      (WP-1076), so the `lm` path either fills it or the field admits that it
      cannot; `LMOutcome` (`optimize/lm.py:205`) carries `fun` and `jac`, so
      the `lm` half is computable rather than absent.
      **Landed as one field, `LSQOutcome.residual_cosine`**, and the choice is
      measured rather than inherited: `gₖ/(‖J:,ₖ‖·‖r‖)`, the cosine of the
      angle between the residual and each Jacobian column. The normal
      equations force that to zero on every free column at an unconstrained
      optimum, so a column that keeps an angle is held by something, and at a
      limit that something is the limit. It is dimensionless, so it compares
      across parameters whose units do not, and it has one definition under
      both drivers — unlike scipy's `optimality`, which is Coleman-Li-scaled
      and which `lm` does not produce.
- [x] `bound_findings` takes the conjunction: within a *loose* distance of the
      limit **and** the gradient still pushing into it, normalised by the
      optimality measure. State the two thresholds with the measurement that
      set them, and keep `BOUND_HIT_RTOL`'s role explicit (it becomes the
      loose half, so its value moves and its meaning changes).
      `BOUND_HIT_ESD_FRAC = 1e-2` is the loose half, measured in the
      parameter's own esd; `BOUND_HIT_COS_MIN = 1e-4` the binding half, plus
      the sign. `BOUND_HIT_RTOL` keeps its value and becomes the **fallback**
      distance test, taken per column when no solve stands behind the call or
      when an esd is unavailable, which reproduces the pre-1434 answer.
- [x] The finding carries its evidence, as `CONSTRAINT_ACTIVE` does: the
      gradient and how far from the limit, so a reader can judge without
      re-running. `GuardFinding.at_bound` currently carries `value=None`.
      It now carries ρ there, with the rendered clause on a new `detail` field
      that only the `BOUND_HIT` diagnostic reads. `str(finding)` is untouched,
      which is what the byte-for-byte pin is about.
- [x] Re-measure issue #273's 24 cases on FAP and Si SRM 640c, and the four
      rows in the table above. The bar is every genuinely-binding case firing
      at every `ftol`, and the interior optimum silent at every `ftol`.
      **Met.** 32 cases on FAP and Si SRM 640c with `ftol` swept 1e-9 … 1e-3:
      nine silent before, none after. On the `make_lab6` sweep both binding
      rows fire at every `ftol`, the early-stopped row stays silent and the
      interior optimum stays silent at every `ftol`. Numbers in the handover.
- [ ] Check what moves on the acceptance suites. A test that changes which
      diagnostics fire is the point; one that changes a *value* is a bug.
- [x] Tests: the `ftol` sweep as a fixture, a binding bound and an interior
      optimum side by side, and the early-stopped row asserting it does **not**
      become a `BOUND_HIT`. Plus obs/calc/diff PNGs to `tests/output/`.
      Thirteen rows in `test_bound_hit_at_convergence.py`, two of them unit
      rows on `bound_findings` that need no fit. The early-stopped row asserts
      the **angle** as well as the silence, because a row that passed for the
      wrong reason would look identical.
- [x] Skill: the `BOUND_HIT` row in the diagnostics table says what the flag
      now means and what its evidence fields carry. It currently tells an
      agent to widen the bound or fix the parameter, which stays right, but
      the reading "this bound carried load" is new and is the part an agent
      acts on. Landed, including the *silence*: a parameter near a limit with
      no row is one the limit is not holding, so widening it buys nothing.
      **`diagnostics.md` now sits 9 bytes under its 36 000-byte cap**, and it
      had 615 bytes of headroom before this row. The next session adding a
      code here pays for it with a cut or splits the file.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_bound_hit_at_convergence.py tests/test_held_phase.py tests/test_capillary_displacement.py
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

The bar: on the fixture above `BOUND_HIT` fires on both binding rows and on
neither non-binding one, at every `ftol` in the sweep; issue #273's nine
silent cases all speak; every accepted fit value is bit-identical.

The shipping PR carries `Closes #273`.

## References

- Issue #273 — the 24-case sweep on FAP and Si SRM 640c.
- [1310](1310-report-repeats-itself.md) § 6 — the measurement that ruled out
  both of the issue's fixes, and § 4 for the vector half already landed.
- [1311](1311-walking-parameter-bounds.md) — reports through this machinery.
- `refine.py:2953` `_constraint_diagnostics` — the design note: evidence from
  the answer-producing stage, `info` not `warning`.
- Coelho (2005), *J. Appl. Cryst.* **38**, 455 (in the local corpus).
- Nocedal & Wright, *Numerical Optimization*, ch. 12, 16; Gill, Murray &
  Wright, *Practical Optimization*, §5.5.
- scipy `least_squares` documentation, `active_mask` and `optimality`.

## Handover log

- **2026-09-16** — created by WP-1310's session, which fixed the other half of
  issue #273 and measured this half into a different shape than the issue
  filed it in. The issue offers two fixes and the measurements rule out both,
  so the WP that inherits this should not start by implementing either. The
  table in § Context is the whole argument; the first action is capturing the
  gradient on `StageOutcome`, because nothing can be decided without it.

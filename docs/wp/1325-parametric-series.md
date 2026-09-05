# WP-1325 — parametric series: a parameter as a function of the series axis

Milestone: unscheduled · Status: ⬜
Depends on: — (1119 soft: a named coefficient is a named variable)

## Goal

A series can refine a parameter as a declared function of the series axis —
temperature, time, composition — across all its patterns in **one joint
residual**, with the function's coefficients as the refined parameters and
their esds from the joint covariance (Stinton & Evans 2007, "parametric
Rietveld"). A thermal-expansion coefficient, a transition temperature or a
rate is then a *measured* number with an esd, rather than a line fitted
afterwards to a trajectory of per-pattern values whose esds are each
conditional on their own pattern.

## Context

**This is a candidate.** It is on the roadmap because of a use case, not a
measurement, and its first task is the measurement that decides whether it
opens. It was named during the 2026-09-01 roadmap reorder as the gap between
three things the package already has.

- `sequential.py` chains N fits by warm start and reports **trajectories**;
  WP-1305's fourth deliverable prints a parameter against the series axis.
  That is the *output* whose *input* form this WP is: today the function is
  fitted to the trajectory, so every point's esd is conditional on its
  pattern's other parameters and the chain is path-dependent by construction
  (`direction="both"` flags it).
- `multi.py` stacks patterns into **one joint residual** (multi-histogram,
  WP-0308). That is the seam a parametric fit needs: N patterns, one θ.
- The tie machinery is affine, p = C·θ + d with constant C (WP-0301, WP-1070).
  A parametric tie that is *linear in its coefficients* — a(T_k) = a₀ + a₁·T_k
  on pattern k — is exactly an affine tie per pattern with C_k = [1, T_k], so
  the linear case needs **no new Jacobian branch**: `_column_extras` reads
  the reach off C, and the whole-model FD column covers what a branch does
  not claim. Nonlinear forms (Arrhenius, a critical exponent) are the same
  fence as WP-1119's `Parameter.expr`.
- Issue #212's conserved elemental ratio across a reduction series is a
  parametric constraint in disguise: linear in the phase scales, constant
  across the series axis.

**Prior art, concepts only.** TOPAS's parametric refinement (Stinton & Evans
2007) refines the function's coefficients directly against all patterns;
GSAS-II's sequential refinement fits a function to the sequential *table*
afterwards, which is the weaker form the package already has. The design
decision this WP owes is where the declaration lives — a `SeriesTie(path,
function, axis, coefficients)` beside `RefinementState.ties` is the shape that
keeps `Refinement._ties` the one authority for what is the user's.

**What the measurement has to say.** On the 68-pattern ZrMo₂O₈ ramp (the
v1.1 trigger series): the coefficient and esd from a line through the
trajectory, against the same coefficient from a joint fit with a = a₀ + a₁·T
over a window of patterns. If the two coefficients agree within an esd and
the joint esd is not smaller, the trajectory form is enough and this WP closes
as a finding. Cost is the second number: a joint residual over N patterns is
N× the rows, and WP-1125 measured that profiling a linear block buys no
evaluation, so the wall-clock ratio against the chain is reported, not
assumed.

### Inherited

- **2026-09-04, from [1119](1119-named-variables.md): the soft dependency is
  discharged, and one piece of your scope is now unowned.** A named coefficient
  is a named variable and that object exists: `Refinement.add_variable(name,
  value, min=, max=, transform=)` gives `vars.<name>`, an ordinary dot-path that
  `parameters()` lists, `set_vary("vars.*")` frees and a fit refines with an
  esd; `Refinement.tie` takes `{path: coefficient}` so one variable can be
  written in terms of others; and a variable is persisted in
  `RefinementState.variables`, so a checkout restores it. Two things to carry
  across. (1) **A variable's bounds are the only bounds the solve sees** — a
  tied dependent is not a free column, so a coefficient other than 1 can put it
  outside its own `min`/`max` and the failure is a pydantic error naming
  nothing (skill `references/surprises.md` § 8.22). A parametric coefficient
  driving several patterns' parameters has to be bounded for its dependents.
  (2) **The linear relation is exact and the nonlinear one does not exist**:
  `p = C·θ + d` is what the constraint block computes, so a coefficient times a
  series axis is free, and anything with a product or a power of the axis in it
  is outside the machinery entirely.
- **2026-09-04, from [1119](1119-named-variables.md): issue #212 is a WP of its
  own and nobody has cut it.** 1119 was asked to decide whether the cross-phase
  linear *restraint* row belongs to it, and the answer was no — it is a residual
  row and a `Structure`-level schema seam, sharing only the (path, coefficient)
  shape with a tie. The seam, as 1119 leaves it: `Phase.restraints` is per
  phase and `Structure` holds no cross-phase list, so the row belongs beside
  `resolve_phase_restraints` (`model/restraints.py:114`); it needs a new
  `BLOCK_ORDER` block in `model/rows.py`; and it needs no expression language,
  because `√w·(Σ c_k·x_k − target)/σ` over (path, coefficient) pairs is the
  whole thing and `phase_zmv(...).element_counts` (`optimize/qpa.py`) already
  carries n_{E,p}. The evidence in the issue: Cu/(Ca+Al) = 1.935 through a
  reduction series, where diffraction alone moves 17 wt % between two phases for
  0.2–0.5 pp of Rwp. This WP names it as one instance of a parametric
  constraint, so **cutting that WP is the next action on it** and it is recorded
  here rather than in 1119, which is closed.

- **2026-09-02, from the magnetic scattering track
  ([1329](1329-moment-in-a-series.md)): a second use case, named, not
  measured.** An ordered moment through T_N is an order parameter, m ∝
  (1 − T/T_N)^β, nonlinear in β and T_N, so it is the `Parameter.expr` fence
  rather than this WP's linear form; 1329 delivers the |m|(T) trajectory
  with held patterns marked and leaves the exponent to the user. If this
  WP's measurement on the ZrMo₂O₈ ramp says the joint form is worth having,
  the moment trajectory is the second series to measure it on.

## Non-goals

- A library of physical models. One declared function, linear in its
  coefficients, is the deliverable.
- Replacing the chain: it stays the exploratory tool and the seed.
- Nonlinear functions of the axis (fenced with `Parameter.expr`, WP-1119).

## Tasks

- [ ] The measurement above, on the ZrMo₂O₈ ramp: trajectory-line coefficient
      and esd against a joint a₀ + a₁·T fit over 10 patterns, and the
      wall-clock ratio. Decide open / close-as-finding on it.
- [ ] `SeriesTie` on the series surface, resolved into `multi.py`'s joint
      table as per-pattern affine ties; bit-identical to `refine_multi` when
      the function is a constant.
- [ ] esds of the coefficients from the joint covariance, marked unmeasured
      where a pattern contributes no gradient (WP-1110 item 14's rule).
- [ ] `SeriesResult.summary(deliverable="series")` prints the coefficients
      beside the trajectory it already prints.
- [ ] Manual Part 1 `using/series.md`; Part 2 the equation with its *Source*
      line; the skill's series reference.
- [ ] Tests on a synthetic ramp with a known a(T): a₁ within one esd of truth,
      the esd no larger than the trajectory-line's; obs/calc/diff PNGs to
      `tests/output/`.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_sequential.py tests/test_multi_histogram.py tests/test_parametric_series.py
.venv/bin/python -m ruff check src tests examples
```

## References

- Stinton, G. W. & Evans, J. S. O. (2007). *J. Appl. Cryst.* 40, 87-95 —
  parametric Rietveld refinement.
- WP-0308 (the joint residual), WP-0505 / WP-1051 / WP-1127 (the chain),
  WP-1305 (the series deliverable), WP-1119 (named variables), issue #212.

## Handover log

- **2026-09-01** — created as a candidate during the roadmap reorder; carries
  a use case and a seam, no measurement. First task is the measurement.

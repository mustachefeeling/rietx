# WP-1964 — a nonlinear law over the pattern coordinates, through the derived block

Milestone: unscheduled · Status: ⬜
Track: Candidates — named on a use case, not yet on a measurement
Depends on: 1325 (the joint path, its parametric tie and its form test); 1804 (the derived block)
Priority: P2 2026-10-14 — the maintainer called it important; the parametric examples in the literature are nonlinear, 1329's ordered moment is one, and the seam has existed since 1804

## Goal

A joint fit can refine a parameter as a named law that is nonlinear in its
coefficients, across each pattern's coordinates. Examples are an order
parameter (1 − T/T_c)^β with T_c and β refined, an Avrami rate, and an
Einstein temperature for Biso(T). Each coefficient comes back with an esd from
the joint covariance, and the law's form is tested as 1325's linear laws are.

## Context

Filed as a stub on 2026-10-14, from a review of WP-1325's API against prior
art. The maintainer asked why nonlinear laws were fenced, and called the
feature important. WP-1325's Non-goals fenced them, and no open WP owned them.

### Why they were fenced

Three reasons, from three records.

1. **Only the affine map was exact under autodiff.** WP-1119's Non-goals put
   `A*B`, `sqrt(A)` and trigonometry outside p = C·θ + d. Every reader of C
   (esds, reach, the structural freezes) relied on that one matrix.
2. **The general answer was never built.** `Parameter.expr`
   (`schemas/common.py:615`) is reserved for an AST-whitelisted expression
   language emitted as backend ops. DESIGN.md § Parameter system rejected
   asteval (it cannot run on autodiff tracers) and sympy (its torch printer
   is immature). The field still raises.
3. **The first named user needs polynomials.** WP-1325's outside lab fits
   composition surfaces, and those are linear in their coefficients.

### Why the first reason no longer holds

WP-1804 (merged 2026-10-07, PR #773) added a second seam to the parameter
table: `params.derived.DerivedBlock`, a nonlinear map applied after the
affine one. A block owes the table four things:

- `evaluate`, the map on the numpy path;
- `jacobian`, ∂outputs/∂inputs, exact, never a finite difference;
- `evaluate_traced`, the same map in `xp` ops, so jax and torch differentiate it;
- `reach_pattern`, the dependence declared from the map's structure.

Esds take the block's local Jacobian at θ (`stderr_physical`,
`physical_covariance`). A block's data-row column needs no new Jacobian
branch, because `_peak_chain_column` differences θ through `decode`. Rigid
bodies use the seam, joint fits included (`MultiParameterTable.commit`
commits each histogram's bodies). DESIGN.md § Parameter system, "Rigid
bodies: a typed `derived` block", has the measurement.

So a law can be a block whose inputs are the coefficients `vars.<name>_j` and
whose output is the target in one histogram, with that histogram's
coordinates as constants. A closed vocabulary of named laws then needs no
expression language. That matches 1325's closed basis vocabulary. The second
reason stops binding this WP, and `Parameter.expr` stays the general route.

### Prior art

From WP-1325 § Prior art (concepts only, per the licensing rule):

- TOPAS parametric refinement (Stinton & Evans 2007) feeds global
  coefficients into an expression in every dataset.
- Müller, Dinnebier & Schorr (2011) refined symmetry-mode amplitudes as a
  Landau power law in T. They report better statistics, stability and lower
  correlation than the sequential route.
- XAFS ties σ²(T) across temperatures through a refined Debye temperature.

In this repo, WP-1329 names m ∝ (1 − T/T_N)^β for the ordered moment and
leaves the exponent to the user, fitted to the trajectory
(`using/series.md`, "Nothing here fits m ∝ (1 − T/T_N)^β").

### What is hard, and what the WP must measure

- **Ordering in `decode`.** `ParameterTable.decode` (`params/vector.py:3779`)
  applies C·θ + d first and the blocks after it. An affine tie that reads a
  block's output therefore reads the stale affine value. A cubic `b ← a`
  under a law on `a` is that case. The block has to write every path that
  follows the target. `_install_parametric` (`params/multi.py:433`) already
  computes that set.
- **Starting values.** 1325 starts the coefficients from a linear
  least-squares fit of the law to the targets' starting values
  (`least_squares_start`). A nonlinear law has no closed-form start. Candidates
  are a fit to a chain's trajectory, and the caller's own start.
- **Bounds.** 1325's polynomial coefficients are unbounded. A law's
  parameters have physical ranges: β > 0, and T_c above every pattern of the
  subset. These are box bounds on the coefficients, which the default driver
  already holds.
- **A singular derivative.** For β < 1, ∂/∂T_c of (1 − T/T_c)^β diverges as
  T approaches T_c. A subset that stops short of T_c avoids it. Measure how
  close is safe.
- **Linearised esds.** The covariance is linear in the coefficients. For a
  strongly nonlinear parameter such as β, the true interval is asymmetric.
  Profile-likelihood intervals are the standard answer (Bates & Watts 1988).
  Measure coverage over seeds before choosing one.
- **The form test.** `params.parametric.form_tests` projects at the answer.
  Through the block's local Jacobian it should extend unchanged. That is a
  claim to test, not an assumption.

### Seams

- `schemas/parametric.py`: the vocabulary, as data with a JSON round-trip.
  Either a new `basis` member per law or a separate type. Decide in the
  first task.
- `params/parametric.py`: resolution, refusals, the start.
- `params/derived.py`: one `DerivedBlock` subclass per law, or one
  parameterised class.
- `params/multi.py` `_install_parametric`: wiring a block in place of a tie.
- `tests/test_cross_backend.py`: a row for the new derivative path (root
  CLAUDE.md § Backends; WP-1804's own toy-block row is still open).

### Inherited

- **2026-10-14, from [1325](1325-parametric-series.md) (seventh session,
  PR #977): three readers assume a law linear in its coefficients.**
  - `ParametricLaw.evaluate` computes Σ x_j·c_j and √(x·Σ·xᵀ) from the
    user-unit coefficients. A law through the derived block needs its own
    evaluator, the block's local Jacobian at the coordinate in place of x.
  - `params.parametric.target_columns` reads a pattern's own target column
    as J_coef·Φ_kᵀ/‖Φ_k‖², which needs a constant Φ. The form test and its
    `others_freed` reading both rest on it.
  - `RefinedParameter.laws` is written from each table's `entry_reach`.
    Check that a row the derived block reaches is marked.

## Non-goals

- A general expression language. That is `Parameter.expr`'s design, a
  separate decision.
- A law nonlinear in the coordinates only. `A·coth(θ_E/2T)` with θ_E fixed is
  linear in A, and 1325's `design` basis already declares it.
- A kernel prior over the coordinates:
  [1963](1963-a-kernel-over-the-pattern-coordinates.md).
- A single-pattern fit. A law needs several patterns.

## Tasks

- [ ] **Measure first.** Two synthetic ramps with a known nonlinear truth: an
  order parameter through T_c, and an Avrami fraction against time. Fit each
  with the true law (as a script-side block) and with 1325's best polynomial.
  Report the bias, the esd coverage at 2 esd over seeds, and the form test's
  verdict for both. If the polynomial matches the law inside the subset,
  record where the law still pays (extrapolation, a quoted T_c or β).
- [ ] The vocabulary: which laws, as data, and their units. Start from the
  measured cases and WP-1329's moment.
- [ ] The block per law, numpy and traced, with an exact Jacobian, its
  declared reach, and the follower paths written too. A cross-backend row.
- [ ] Starting values, bounds and the refusals before a solve, in 1325's
  style: each refusal names its fix.
- [ ] Output: `ParametricCoefficient` names a law's parameter (`T_c`,
  `beta`) in its `term`, with its unit. The form test through the block.
- [ ] Tests on the synthetic ramps; obs/calc/diff PNGs to `tests/output/`.
- [ ] Manual: Part 2 the equation of each law with its `*Source:*` line;
  Part 1 a section in `using/series.md`.
- [ ] Skill: the series reference's parametric row, or "none" and why.

## Acceptance

To be fixed when the WP is scoped. The bar it starts from: on the synthetic
order-parameter ramp, T_c and β within 2 esd of the truth in at least 90 % of
seeds, and the declared law matching a chain's trajectory.

```sh
.venv/bin/python -m pytest tests/test_parametric_series.py tests/test_derived_block.py tests/test_cross_backend.py
.venv/bin/python -m ruff check src tests examples
```

## References

- Stinton, G. W. & Evans, J. S. O. (2007). *J. Appl. Cryst.* 40, 87-95 —
  parametric Rietveld refinement.
- Müller, M., Dinnebier, R. E. & Schorr, S. (2011). *Z. Kristallogr.* 226,
  doi:10.1524/zkri.2011.1407 — parameterized Rietveld refinement of the
  CuInSe₂ transition.
- Bates, D. M. & Watts, D. G. (1988). *Nonlinear Regression Analysis and Its
  Applications*. Wiley — profile-likelihood intervals.
- WP-1119 (named variables, and the fence), WP-1325 (the linear law),
  WP-1329 (the ordered moment), WP-1803 and WP-1804 (the derived block),
  DESIGN.md § Parameter system.

## Handover log

- **2026-10-14** — Filed as a stub after the maintainer asked why nonlinear
  laws were fenced. No open WP owned them: 1325's Non-goals fenced them with
  `Parameter.expr`, and 1119 is closed. The fence's first reason predates
  1804's derived block, which is why this WP exists. Next: the first task.

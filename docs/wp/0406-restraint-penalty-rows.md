# WP-0406 — Restraint penalty rows

Milestone: v0.4 · Status: ⬜ not started
Depends on: —

## Goal

Soft restraints (bond lengths, bond angles, value targets) as extra
`√w·(computed − target)/σ` rows in the residual vector, following the
penalty-row seam the P-spline background and Pawley equal-split already
established: kept in the covariance, excluded from Rwp/Durbin-Watson/
Bérar-Lelann, with an analytic row-Jacobian and a restraint-summary report.

## Context

- **The penalty-row seam is already proven twice — reuse it, don't invent.**
  `BackgroundPSpline` appends `√λ·D₂·c` rows and Pawley appends
  `√λ/s·(δ − 1/n)·I` rows, both concatenated *after* the data rows in
  `_make_residual` ([`optimize/least_squares.py`](../../src/pxrdref/optimize/least_squares.py)),
  with `covariance_estimates(..., n_data=N_data)` keeping them in JᵀJ but
  slicing `fun[:n_data]` for χ²/Rwp/DW/Bérar-Lelann (statistics on data rows
  only). The three touchpoints: (1) compile a `√w`-scaled row block; (2)
  `concatenate` it below the data (and background-penalty) rows in
  `_make_residual`; (3) write its rows into the Jacobian below `n_data` and
  register the count so `covariance_estimates`/`compute_statistics` keep
  slicing `[:n_data]`. WP-0308 verified this contract survives the
  multi-histogram stacked layout.
- **The one new wrinkle:** the P-spline and Pawley rows are *constant*
  matrices; bond/angle restraints are **nonlinear** in the coordinates, so
  they need their own row-Jacobian (the precedents don't).
- **Natural consumer:** WP-0302 atomic coordinates — bond-length restraints
  become useful the moment coordinates refine.

### Design (decided)

- **Schema** (pydantic v2, `extra="forbid"`; opt-in, empty default so a
  phase that declares none is untouched — the extinction/PO pattern):
  `Phase.restraints: list[Restraint] = []`, with
  `BondRestraint{atom_i, atom_j, target, sigma, weight=1.0}`,
  `AngleRestraint{atom_i, atom_j, atom_k, target_deg, sigma, weight=1.0}`,
  `ValueRestraint{path, target, sigma, weight=1.0}`. Each contributes a row
  `√weight·(computed − target)/sigma`.
- **Distances/angles under PBC: explicit symmetry-op + translation, not bare
  minimum-image.** The restraint carries an optional (rotation-op index,
  lattice translation) for the *second* atom, defaulting to minimum-image
  when unspecified. Powder restraints almost always target a
  symmetry-generated neighbour (an M–O in an adjacent cell), which
  minimum-image alone renders ambiguous; the frozen `sites.ops`
  (`crystallography/structure_factor.py`) already stores the R, t arrays, so
  the restraint names an op index rather than re-deriving symmetry.
  d = |L·(R·x_j + t + n − x_i)| with L the direct cell matrix
  (`crystallography/lattice.py`); angles from two such vectors via `arccos`.
  Differentiable w.r.t. fractional coords **and** cell.
- **Jacobian: analytic row now, jacfwd later.** An analytic `∂d/∂θ` row —
  chain `∂d/∂x_frac · ∂x_frac/∂θ` through the same affine constraint block
  `_structural_column` uses, plus `∂d/∂cell` — keeps the numpy path exact.
  FD (`fd_cols`) is the fallback for any restraint kind whose analytic row
  isn't written yet. Under jax (WP-0402) the restraint rows fall out of
  jacfwd automatically (the residual is one function).
- **Statistics exclusion:** restraint rows go below the data (and
  background-penalty) rows, so χ²/Rwp/DW/Bérar-Lelann see data only, while
  JᵀJ keeps them — the covariance is the *restrained* one (correct:
  restraints inform parameter uncertainties). Identical to the multi-histogram
  penalty-row contract WP-0308 verified.
- **Reporting:** a `RestraintReport` on the result/FitReport — per-restraint
  (computed, target, deviation/σ) and a pooled restraint-χ². An over-tight
  restraint fighting the data (deviation ≫ σ) is thereby visible, matching
  the package's "never hide a bad sub-fit" ethos. Deviations in units of σ
  are the headline.

## Non-goals

Rigid bodies (v2 fence); anti-bump/van-der-Waals repulsion restraints
(future); torsion restraints; automatic restraint generation from a
connectivity search.

## Tasks

- [ ] `schemas/structure.py`: `BondRestraint`/`AngleRestraint`/
      `ValueRestraint` + `Phase.restraints` (opt-in, empty default); the PBC
      sym-op/translation spec
- [ ] `model/restraints.py`: differentiable distance/angle from (xyz, cell)
      using frozen `sites.ops`; `√w·(d − target)/σ` rows
- [ ] Compile-time restraint row block + analytic `∂/∂θ` row-Jacobian below
      the background-penalty rows in `_make_residual`/`_make_jacobian`; FD
      fallback
- [ ] `covariance_estimates` reuse verified (rows in JᵀJ, excluded from
      `fun[:n_data]`); `RestraintReport` in the FitReport
- [ ] Tests: `tests/test_restraints.py` — a bond restraint pulls a
      deliberately-displaced atom back to target within σ without changing
      the data-row statistics; the restraint-row analytic Jacobian vs FD
      <5e-3; Rwp/DW/Bérar-Lelann bit-identical to the no-restraint-row
      statistics at the same parameters + obs/calc/diff PNGs to
      `tests/output/`

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_restraints.py -q
```

Measured: a bond-length restraint recovers a perturbed coordinate to within
σ; the restraint-row analytic Jacobian matches FD <5e-3; Rwp/DW/Bérar-Lelann
are computed on data rows only (bit-identical to the no-restraint-row
statistics at the same parameters).

## References

- Waser (1963) Acta Cryst. 16, 1091 — least squares with observational
  restraints.
- Watkin (1994) Acta Cryst. A50, 411 — restraint weighting in practice.
- GSAS-II restraint conventions (BSD — concepts only, cite; never ported).

## Handover log

- **2026-07-22** — created as a stub from the ROADMAP split.
- **2026-07-24** — expanded from stub (v0.4 planning session): schema (opt-in
  bond/angle/value), explicit sym-op+translation PBC spec over minimum-image,
  analytic nonlinear row-Jacobian, statistics-exclusion seam reuse and the
  `RestraintReport` decided.

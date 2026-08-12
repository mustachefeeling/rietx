# WP-0302 — Atomic-coordinate refinement

Milestone: v0.3 · Status: ✅ 2026-07-23
Depends on: WP-0301

## Goal

Lift the `NotImplementedError` that blocks coordinate refinement and refine
fractional coordinates under the WP-0301 site-symmetry constraints, with
analytic-quality Jacobian columns and esds.

## Context

The block is explicit in
[`src/anatase/params/vector.py:113`](../../src/anatase/params/vector.py#L113) —
`_collect` raises when any `atom.{x,y,z}` has `vary=True`, telling the user
Wyckoff-aware constraints are planned for v0.3. Two things must change here:

1. Coordinates enter θ through the affine constraint block from WP-0301 (a
   special position contributes fewer free parameters than 3; general
   positions contribute 3).
2. `apply_to_models` (line ~205) currently writes back `occ` and `biso` only —
   it never writes `x/y/z`. Add the coordinate write-back or refined
   coordinates silently vanish between stages. **This is the easy bug to ship
   by accident**; cover it with a stage-boundary test.

Jacobian: coordinates enter through the structure factor, not the peak shape,
so they do **not** go through the per-point profile-derivative bases. The
cheapest correct route is the existing per-reflection scalar chain in
[`model/forward.py`](../../src/anatase/model/forward.py): |F_hkl|² depends on
coordinates, and ∂|F|²/∂x has a closed form
(F = Σ_j f_j·occ_j·exp(2πi h·r_j)·T_j summed over the frozen per-atom
symmetry-op subsets, so ∂F/∂x_j = Σ_ops 2πi·(Rᵀh)_x·f_j·occ_j·exp(...)).
Compute it over the same frozen op subsets `structure_factor.py` already
builds — reuse, do not rebuild.

Invariants that bite here (CLAUDE.md, [../DESIGN.md](../DESIGN.md#architecture-invariants)):
the per-atom symmetry-op subsets are frozen at stage compile and must not be
regenerated inside the least-squares run. Reciprocal-space symmetry action is
**Rᵀ** — see the comment in `crystallography/symmetry.py`; getting this wrong
is silent on cubic and wrong on everything else.

Staging: coordinates come late in the McCusker turn-on order. Extend the
staged plans in [`strategy/staged.py`](../../src/anatase/strategy/staged.py)
rather than inventing a new plan.

## Non-goals

- Aniso ADPs (WP-0303) — same constraint machinery, different quantity.
- Restraints / soft bond-length penalties (WP-0406 supplies the penalty rows).
- Rigid bodies (v2 fence).

## Tasks

- [x] Remove the `NotImplementedError`; route coordinates through the WP-0301
      constraint block (free count = site-symmetry-allowed dimensions)
- [x] Add coordinate write-back to `apply_to_models` + a stage-boundary test
      that a refined coordinate survives into the next stage's compile
- [x] Analytic ∂|F|²/∂(coordinate) columns over the frozen op subsets in
      `structure_factor.py`, chained into the Jacobian assembly
- [x] Jacobian agreement test vs FD for coordinates (match the existing
      tolerance style: <5×10⁻³ relative, cosine >0.99999), including a special
      position where the constraint reduces the free count
- [x] Staged-plan support: a coordinates stage in the McCusker order
- [x] Synthetic round-trip: perturb a known structure's coordinates, refine
      them back within esd; plus obs/calc/diff PNGs to `tests/output/`

## Acceptance

A synthetic perturbation of coordinates in a structure with both general and
special positions is recovered within the reported esds; FD/analytic Jacobian
agreement holds at stage boundaries; no shipped acceptance number moves.

```sh
.venv/bin/python -m pytest tests/test_coordinates.py tests/test_jacobian.py -q
.venv/bin/python -m pytest            # full suite: SRM 660c / FAP / NAC unchanged
```

## References

- Rietveld (1969) J. Appl. Cryst. 2, 65 — structure-factor derivatives.
- McCusker, Von Dreele, Cox, Louër & Scardi (1999) J. Appl. Cryst. 32, 36 —
  parameter turn-on order.

## Handover log

- **2026-07-22** — created from the ROADMAP split; not started.
- **2026-07-23** — **done**; three `WP-0302:` commits, full suite (217, incl.
  slow acceptance) + ruff green, shipped acceptance numbers unchanged.
  - Coordinates refine as synthetic DOFs `phases.i.atoms.j.dof.k` (one per
    site-symmetry direction), x/y/z affine-tied with const = compile-time
    anchor; anchors re-base whenever a fresh `ParameterTable` is built (θ=0
    ↔ current committed coords — exact, not a state loss). Freeing goes
    through the **dof glob** (`phases.*.atoms.*.dof.*`); x/y/z globs match
    nothing (tied/locked). `vary=True` on a coordinate of a fully fixed site
    raises; on a constrained site it frees *all* the site's DOFs.
  - New plan preset `mccusker_structural` (= mccusker_default + coordinates
    + biso stages). Existing presets untouched on purpose — adding stages to
    them would move shipped acceptance numbers.
  - Analytic column: `structure_factor.d_f2_d_xyz` (Rᵀ h action, frozen
    `sites.ops`) → `CompiledModel.coordinate_intensity_grad` → dedicated
    branch in `least_squares._make_jacobian` that reads the displacement
    direction off the DOF's column of the affine C. Lebail: guard re-fixes
    structural params AND now drops them from `StageResult.freed`.
  - Gotchas for WP-0303: reuse the dof-glob pattern for Uij (adp_basis is
    already in wyckoff.py); `coordinate_intensity_grad` shows the chain
    shape to copy for ∂|F|²/∂Uij; test tolerance style lives in
    `tests/test_jacobian.py::_check_columns`. Rwp assertions on weak
    synthetic patterns are bounded by Rexp — assert GoF instead.

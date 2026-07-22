# WP-0302 — Atomic-coordinate refinement

Milestone: v0.3 · Status: ⬜ not started
Depends on: WP-0301

## Goal

Lift the `NotImplementedError` that blocks coordinate refinement and refine
fractional coordinates under the WP-0301 site-symmetry constraints, with
analytic-quality Jacobian columns and esds.

## Context

The block is explicit in
[`src/pxrdref/params/vector.py:113`](../../src/pxrdref/params/vector.py#L113) —
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
[`model/forward.py`](../../src/pxrdref/model/forward.py): |F_hkl|² depends on
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
staged plans in [`strategy/staged.py`](../../src/pxrdref/strategy/staged.py)
rather than inventing a new plan.

## Non-goals

- Aniso ADPs (WP-0303) — same constraint machinery, different quantity.
- Restraints / soft bond-length penalties (WP-0406 supplies the penalty rows).
- Rigid bodies (v2 fence).

## Tasks

- [ ] Remove the `NotImplementedError`; route coordinates through the WP-0301
      constraint block (free count = site-symmetry-allowed dimensions)
- [ ] Add coordinate write-back to `apply_to_models` + a stage-boundary test
      that a refined coordinate survives into the next stage's compile
- [ ] Analytic ∂|F|²/∂(coordinate) columns over the frozen op subsets in
      `structure_factor.py`, chained into the Jacobian assembly
- [ ] Jacobian agreement test vs FD for coordinates (match the existing
      tolerance style: <5×10⁻³ relative, cosine >0.99999), including a special
      position where the constraint reduces the free count
- [ ] Staged-plan support: a coordinates stage in the McCusker order
- [ ] Synthetic round-trip: perturb a known structure's coordinates, refine
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

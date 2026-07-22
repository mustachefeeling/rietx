# WP-0307 — March-Dollase preferred orientation

Milestone: v0.3 · Status: ⬜ not started
Depends on: —

## Goal

Refinable single-axis preferred-orientation correction (March-Dollase) as an
intensity multiplier per reflection, with the geometry convention documented
by physics rather than by sign.

## Context

March-Dollase multiplies each reflection's intensity by

    P_hkl = (1/M) Σ_ops [ r²·cos²α + sin²α / r ]^(−3/2)

with α the angle between the preferred-orientation axis and the reflection's
scattering vector, r the refinable March coefficient, and the sum over the
reflection's symmetry-equivalent orbit — reuse the frozen orbit/multiplicity
machinery in
[`crystallography/symmetry.py`](../../src/pxrdref/crystallography/symmetry.py)
rather than recomputing equivalents. **Reciprocal-space symmetry action is
Rᵀ**; this matters for the orbit on non-cubic cells (the comment in
symmetry.py explains why).

Convention trap to document in the docstring: r < 1 and r > 1 correspond to
platy versus needle habit *depending on whether the geometry is reflection or
transmission* — the correction is not sign-symmetric across geometry. Follow
the package rule and document it **by physics** (which habit, which geometry),
not by letter. Codes disagree here; a reader must be able to tell what our r
means without running an experiment.

Placement: a per-phase optional PO block in
[`schemas/structure.py`](../../src/pxrdref/schemas/structure.py) with the axis
as integer hkl indices and `r` as a refinable `Parameter`. r must be bounded
positive — use the softplus transform already used for widths and scales
(`params/transforms.py`), since hard lower bounds stall TRF.

The Jacobian column is analytic: P_hkl is a smooth closed form in r, and the
per-reflection intensity chain in
[`model/forward.py`](../../src/pxrdref/model/forward.py) is exactly where the
existing scalar-derivative chaining happens. Add it there, not as FD.

Correlation warning worth surfacing: PO correlates strongly with occupancies
and with ADPs (all three scale intensities in Q-dependent ways). The FitReport
Layer 1 already does hkl-grouped intensity analysis with an
axis-angle→March-Dollase template — check whether refining r resolves what
Layer 1 was pointing at, and keep the correlation guards live.

## Non-goals

- Spherical-harmonics texture (Von Dreele 1997) — v2 fence; March-Dollase is
  the single-axis approximation and should say so.
- Multi-axis / two-component PO models.

## Tasks

- [ ] Per-phase PO block (axis hkl + refinable r, softplus-bounded) in the
      structure schema; JSON round-trip test
- [ ] `P_hkl` over frozen symmetry orbits in the intensity chain; docstring
      documenting the habit/geometry convention by physics
- [ ] Analytic ∂P/∂r column chained into the Jacobian; FD agreement test
- [ ] Staged-plan slot (PO turns on late, with/after the intensity terms)
- [ ] Tests: r = 1 is exactly the no-correction case (identity check); a
      synthetic PO injection is recovered within esds; correlation with
      occ/Biso surfaced by the existing guards
- [ ] Confirm the FitReport Layer-1 March-Dollase template points at the
      injected axis on the synthetic case

## Acceptance

r = 1 reproduces the uncorrected pattern to machine precision; a synthetic
March-Dollase injection is recovered within esds and the Layer-1 hkl-grouped
analysis identifies the correct axis.

```sh
.venv/bin/python -m pytest tests/test_preferred_orientation.py -q
```

## References

- Dollase (1986) J. Appl. Cryst. 19, 267 — March model in Rietveld refinement.
- March (1932) Z. Krist. 81, 285 — the original distribution.

## Handover log

- **2026-07-22** — created from the ROADMAP split; not started.

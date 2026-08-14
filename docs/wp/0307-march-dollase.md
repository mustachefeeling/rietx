# WP-0307 — March-Dollase preferred orientation

Milestone: v0.3 · Status: ✅ 2026-07-23
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
[`crystallography/symmetry.py`](../../src/rietx/crystallography/symmetry.py)
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
[`schemas/structure.py`](../../src/rietx/schemas/structure.py) with the axis
as integer hkl indices and `r` as a refinable `Parameter`. r must be bounded
positive — use the softplus transform already used for widths and scales
(`params/transforms.py`), since hard lower bounds stall TRF.

The Jacobian column is analytic: P_hkl is a smooth closed form in r, and the
per-reflection intensity chain in
[`model/forward.py`](../../src/rietx/model/forward.py) is exactly where the
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

- [x] Per-phase PO block (axis hkl + refinable r, softplus-bounded) in the
      structure schema; JSON round-trip test
- [x] `P_hkl` over frozen symmetry orbits in the intensity chain; docstring
      documenting the habit/geometry convention by physics
- [x] Analytic ∂P/∂r column chained into the Jacobian; FD agreement test
- [x] Staged-plan slot (PO turns on late, with/after the intensity terms)
- [x] Tests: r = 1 is exactly the no-correction case (identity check); a
      synthetic PO injection is recovered within esds; correlation with
      occ/Biso surfaced by the existing guards
- [x] Confirm the FitReport Layer-1 March-Dollase template points at the
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
- **2026-07-23** — **done.** Shipped `model/preferred_orientation.py`
  (`march_dollase_factors` / `_and_dr`, orbit-averaged P_hkl over a flat
  `orbit_layout`; identity at r=1 to machine precision; convention documented
  by physics — reflection geometry r<1 ⇒ platy with axis=plate normal, sense
  flips in transmission). Orbits frozen at stage compile via a new
  `symmetry.reflection_orbits` (orbit size == multiplicity, tested); the angles
  follow the cell through G*. P folded into `phase_peaks` **base** (ahead of the
  extinction multiply — both commute; extinction's x still uses raw |F|²) and,
  critically, into `_structural_intensity_grad` so the analytic coordinate/ADP
  columns carry P (hidden-Jacobian guard — they miss by ~25% at r=0.75
  otherwise; tested with PO+coords+ADP+extinction all live vs full-model FD).
  r is `phases.i.preferred_orientation.r` (softplus, default 1.0/vary=False);
  its analytic ∂P/∂r column (`po_intensity_grad` → `_po_column`, routed by
  `_PO_PATH` before the generic scalar-chain) matches FD to ~1e-6. Staged slot
  `preferred_orientation` sits after `biso`, before `extinction` in
  `mccusker_structural`.
  - **Layer-1 axis diagnostic** (`report/texture.py`, `analyse_texture` →
    `FitReport.texture`, computed *before* the maturity gate since texture is a
    common cause of immaturity). It extracts a per-reflection multiplicative
    correction (Le Bail-style partition of the residual, overlap-deconvolved by
    calc share) and grid-searches (axis, r) with a **free positive scale**,
    scoring by the fraction of intensity-misfit variation the March model
    explains. Two traps found & handled: (1) in high-symmetry crystals
    ⟨cos²α⟩ ≡ 1/3 for every reflection, so the *linear* template is useless —
    the full nonlinear P(r) is required, and `_equivalent` compares full P
    patterns, not ⟨cos²⟩; (2) a negative scale fits the anti-pattern (wrong r's
    mirror), so s>0 is enforced. On rutile (tetragonal — clean c-axis signal;
    cubic LaB6 barely shows single-axis PO, which is *why* it's not used) it
    nails [001] at r_est=0.500, R²=0.999 from an uncorrected fit; recovery of a
    free r gives 0.5004±0.0004, Rwp 0.62→0.08.
  - Gotchas for the next session: texture detection needs a *converged non-PO
    fit* to give a clean residual (a crude single-scale match leaves
    profile/background junk that caps R² ~0.35). Cubic single-axis PO is
    genuinely weak/ambiguous — don't tune the thresholds to force it, it's
    physics. `analyse_texture` is Rietveld-only (Le Bail/Pawley intensities are
    empirical). No Layer-2 `ActionKind` was added (the vocabulary is versioned;
    out of scope) — the diagnostic reports the axis, acting on it is left to a
    future WP if wanted.
- Acceptance: `.venv/bin/python -m pytest tests/test_preferred_orientation.py -q`
  → 19 passed; full suite green; ruff clean.

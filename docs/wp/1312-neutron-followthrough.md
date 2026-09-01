# WP-1312 — CW neutron follow-through: the seed, the resonant flag, the joint fit

Milestone: unscheduled · Status: ⬜
Depends on: — (WP-1132 is the maintainer's and does not gate any task here)

## Goal

The three loose ends the CW-neutron landing left are closed: the
`constant_wavelength_neutron` seed matches its own docstring, a resonant
absorber in a structure is named instead of silently mis-tabulated, and a
combined X-ray + neutron joint refinement is exercised, verified and
documented rather than merely admissible.

## Context

From issues #124 (maintainer-filed, fix stated), #113 item (a) (the cheap
slice; the rest is fenced), and #194 (verify, don't build).

**1. The seed (issue #124).** `Instrument.constant_wavelength_neutron(...,
fwhm_deg=...)` seeds `w = (0.5·fwhm)²` *and* `x = fwhm`. `w` gives a constant
Γ_G = fwhm/2, which is right; `x` is the Lorentzian Scherrer term
Γ_L = X/cosθ, so the full-FWHM seed both double-counts the width and makes it
strongly angle-dependent. Measured at fwhm_deg = 0.3, the seeded TCHZ FWHM
is 0.369° at 2θ = 20 (1.23×), 0.405 at 60, 0.474 at 90, 0.637 at 120,
**1.179 at 150 (3.93×)** — over exactly the high-angle peaks a CW neutron
cell refinement leans on hardest. Not a correctness bug (the terms refine
afterwards; every #108 fit converged) but three things make it worth fixing:
the docstring promises the observed width; the frozen per-stage windows are
sized from the seed, so the over-width is paid at every stage compile; and
the shape is wrong as well as the size — a real CW neutron resolution
function is narrowest near the focusing angle (Caglioti, Paoletti & Ricci
1958), and a monotonically widening seed is not a coarse version of that.
**Fix: seed `w` alone**; test asserts the seeded FWHM stays near `fwhm_deg`
across 20–150°, not only at low angle; a line in WP-1134's record.

**2. The resonant flag (issue #113 item a).** `crystallography/neutron.py`'s
Sears table ships `RESONANT_ABSORBERS` (Cd, Sm, Eu, Gd). Natural Yb belongs
in it: σ_abs 34.80 barn (14× Ru's 2.56) with an isotopic spread of nearly
three orders (¹⁶⁸Yb 2230.40 vs ¹⁷⁶Yb 2.85 barn) — absorption that large and
that isotope-dependent *is* a nuclear resonance, and a resonance is
energy-dependent, which the thermal table cannot express (the module's own
fence says so). The cheap, honest slice: add Yb, and emit a diagnostic when a
resonant absorber sits in a refined structure — the neutron analogue of
"this wavelength straddles an absorption edge", needing only the species
list plus a cited resonance energy per nuclide. The energy-dependent
correction itself (σ_abs(λ), the S(Q)-level utility) **stays fenced** with
TOF; issue #113 holds that design.

**3. The joint fit is admissible and unexercised (issue #194).**
Multi-histogram refinement ships (`multi.py`, WP-0308) and is stacked per
Von Dreele (1997), *J. Appl. Cryst.* **30**, 517 — the combined
X-ray/neutron paper itself. Nothing in `params/multi.py` restricts radiation
kind, and CW neutron landed in WP-1134 — so a mixed fit is structurally
admissible **today**, and no test or example runs one. Three tasks the issue
lists: an acceptance/example of a genuine X-ray + neutron joint fit on one
shared structure (source a public dual dataset — search the maintainer-local
paper corpus before asking); an audit that per-histogram physics keys on the
histogram's **own** radiation across a mixed fit (anomalous dispersion — on
by default, X-ray-only — must no-op cleanly on the neutron histogram; b vs
f(Q); polarization vs none; the WP-1134 paths); and a check that the
shared-vs-per-histogram parameter split holds when the two histograms weight
structure factors differently. WP-1134's own log notes three defects found
only by *combining* parts on a single path — the same argument for
exercising this combination.

## Non-goals

- **Not the neutron µR estimator** —
  [1132](1132-neutron-specimen-absorption.md), the maintainer's, checklist
  already written. Its absence does not gate any task here (declare no µR on
  the neutron histogram in the example, as every fit does today).
- **Not σ_abs(λ), S(Q) reduction, or anything TOF** — fenced; issue #113
  holds the design.
- **Not new physics.** Every task verifies, seeds, or names; none adds a
  correction.

## Tasks

- [ ] Seed fix: `w` alone; the 20–150° FWHM assertion; the WP-1134 record
      line.
- [ ] Yb into `RESONANT_ABSORBERS`; the resonant-absorber diagnostic with a
      cited resonance-energy entry per member; skill row.
- [ ] The mixed-fit acceptance/example (public dual dataset, provenance row)
      + the radiation-kind audit, any fix it forces landing as its own
      commit; obs/calc/diff PNGs for both histograms to `tests/output/`.
- [ ] Manual: the joint-refinement section states what is shared, what is
      per-histogram, and which corrections key on radiation kind.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_neutron_cw.py tests/test_multi_histogram.py
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

The bar: the seeded FWHM tracks `fwhm_deg` across the range; the diagnostic
fires for an Yb-bearing structure and is silent for Ru/O; the mixed fit
refines one structure against both histograms with dispersion active on the
X-ray one only, and the audit's findings (if any) each carry a test.

## References

- Issues #124, #113, #194; PR #108 / WP-1134 — where the seed and the fence
  landed.
- Caglioti, G., Paoletti, A. & Ricci, F. P. (1958), *Nucl. Instrum.* **3**,
  223 — the CW neutron resolution function.
- Von Dreele, R. B. (1997), *J. Appl. Cryst.* **30**, 517 — combined X-ray +
  neutron Rietveld refinement.
- Sears, V. F. (1992), *Neutron News* **3**(3), 26 — the shipped table.

## Handover log

- **2026-09-01** — created, from issues #124/#113(a)/#194 (2026-09-01
  triage). Settled: three verbs — fix the seed, name the absorber, exercise
  the joint fit; first open item is sourcing the public X-ray + neutron
  dual dataset.

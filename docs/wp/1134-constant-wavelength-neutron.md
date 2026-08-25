# WP-1134 — constant-wavelength neutron: b, λ/n harmonics, and a refinable λ

Milestone: v1.1 · Status: 🔄 2026-08-25 — in review as PR #108
Depends on: —

## Goal

Constant-wavelength neutron diffraction, as three changes that are one feature:
the bound coherent scattering length `b` where `f0` was, λ/n monochromator
harmonics as derived emission lines, and a wavelength that can refine where the
cell is held.  One `SCHEMA_VERSION` bump (0.6 → 0.7) because they reach a
consumer together.

**This file exists because the number did not.** The work was committed under
`WP-1128:`, which is the shipped v1.1 indexing WP
(`1128-prior-seed-before-the-gate.md`, cited from `indexing/svd.py:798`).  Two
meanings of one number costs more than a renumber, so the in-code citations
moved to 1134 — `optimize/least_squares.py`, `model/forward.py` ×2.  The commit
message prefixes are historical and were not rewritten.

## The three parts, and why each is not the obvious thing

**b, not f0.** `f0` has exactly one caller, so the amplitude is one seam rather
than a branch through the forward model.  What makes a neutron test a *neutron*
test is not that it converges: b(Al) < b(O) in fm while f(Al) > f(O) in
electrons, so a corundum pattern **peaks on a different reflection** under the
two radiations.  A test that would pass for an X-ray source is not testing the
radiation.  K = 1 and the absent dispersion channel are each a reason no new
correction code appears, and the Caglioti law *is* the neutron resolution
function (Caglioti, Paoletti & Ricci 1958) — the X-ray path is the borrower.

**Harmonics are emission lines, not a phase.** A λ/n component diffracts the
same hkl list with the same |F|², because |F|² is evaluated at sinθ/λ = 1/2d — a
property of the reflection, not of the wavelength reaching it.  A doubled-cell
phase reproduces the positions and carries the structure factors of a
fictitious cell, so its intensities are wrong.  Deriving λ/n in `lines` rather
than storing it is what keeps declaration and spectrum one fact.

**A free λ needs the cell pinned, not several histograms.** The flat direction
is λ → sλ with **a*** → s**a***, and pinning either end blocks it.  The first
implementation refused every single-histogram λ on the premise that it is
degenerate "whatever the data", which is false for a held cell — and a held
certified cell is exactly how a beamline's λ is calibrated.

## Findings

**Three defects were found by *combining* the parts, not by writing them.**

1. Folding harmonics and the refinable λ into one branch showed a derived λ/n
   does not follow a refining fundamental **in the residual**: `line_lambdas`
   read θ per line and a derived harmonic has no θ row, so it fell back to its
   frozen compile-time value.  Measured at +0.2 % on the fundamental: read
   (1.5404, 0.7702) where tracking gives (1.5434808, 0.7717404).  At the
   +258 ppm the acceptance suite finds on this instrument that misplaces the
   λ/2 peaks by up to 0.11° at 2θ = 150°, about a third of the assumed 0.30°
   FWHM — and nothing raised, because the Jacobian column agreed with the
   residual.  `HARMONIC_FRACTION` reported the same stale λ/n.
2. `Instrument.constant_wavelength_neutron` wrapped `mu_r` in a `Parameter`
   where `Geometry.mu_r` is a plain float, so **every** call passing a µR
   raised.  No test passed one.  Worse, `_resolve_specimen_absorption` runs
   automatically, so a neutron capillary was silently having an **X-ray** µR
   computed and written onto it — fenced, and WP-1132 / issue #117 specifies
   the neutron estimator.
3. The isotope convention was implemented and tested at the lookup and
   **discarded one line above it**: `compile_phase_sites` normalised species
   through the *X-ray* normaliser unconditionally, so `D`, `2H` and `7Li`
   raised "no Waasmaier-Kirfel coefficients" while the shipped Sears table has
   had b(²H) = +6.671 fm all along.  The headline neutron case.

**Validated against three codes on three datasets.** Cr₂WO₆ BT-1 c/a to
−3.4 ppm; Al₂O₃ BT-1 Rwp 0.1016 against 0.1115 at matched Rexp; Nd₂Ru₂O₇
x(O 48f) within 0.2σ of Kennedy & Vogt.  The harmonic fraction refines to
1.05 ± 0.19 % on the published Cu(311) histogram whose paper states a λ/2
contribution.  The refinable λ recovers XND 1.42's calibration on NIST SRM
640c Si to **1.26 ppm** — λ = 0.412375557 against 0.412376076(379), both about
41 ppm above the beamline's own stated 0.412359.

## Deliberately not in scope

- **TOF.** A bank spans a range of λ, so b(λ) would be needed near a resonance
  and µ varies inside one histogram.  Issue #113 scopes the resonant-absorption
  half at S(Q).
- **Magnetic scattering.** A discussion to raise, not a thing to implement.
- **A neutron µR estimator** — WP-1132.
- **The GUI's radiation blindness** and a `kind`-defaulting validator: named
  follow-ups rather than silent gaps.

## Handover log

- **2026-08-25** — In review as PR #108. Yue's 24 Aug review covered the
  amplitude half; the harmonics and wavelength halves were folded in eight
  minutes later at the owner's request to unstack #112/#114, which invalidated
  the scope of that review rather than its content. His 25 Aug follow-up found
  the stale harmonic λ, the deuterium path, a red in the slow tier
  (`EmissionLine.wavelength` type change reaching an un-migrated reader), the
  WP-number collision this file resolves, and an orphan 1.5 MB data file
  committed by an over-broad `git add`. All fixed. `WAVELENGTH_CALIBRATION` for
  the single-histogram case is still a gap: the diagnostic is emitted only from
  `multi.py`, so the calibration this feature now admits reports nothing.

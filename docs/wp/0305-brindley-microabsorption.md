# WP-0305 — Brindley microabsorption correction

Milestone: v0.3 · Status: ⬜ not started
Depends on: WP-0304

## Goal

Apply the Brindley particle-absorption correction to QPA weight fractions,
with the applicability limits enforced rather than documented-and-ignored.

## Context

Microabsorption biases QPA when phases differ in linear attenuation
coefficient µ and particle size R: the more absorbing phase is
under-represented. Brindley's correction multiplies each phase's scale
contribution by a factor τ_p depending on µ_p·R_p and the sample-average µ̄.

Inputs the user must supply per phase: particle radius R (there is no way to
get it from the pattern — do not pretend otherwise). µ_p comes from the
refined composition and cell volume via mass attenuation coefficients at the
instrument wavelength; the same tabulated-scattering infrastructure that
serves form factors lives in
[`crystallography/scattering.py`](../../src/pxrdref/crystallography/scattering.py).
Note that WP-0504 later brings **xraydb** in for f′/f″; if µ is easier and more
accurate from xraydb, coordinate — but do **not** pull in periodictable's
Henke tables, which cap at 30 keV and are the wrong tool (design record,
locked decisions).

The applicability fence is the point of this WP, not a footnote: Brindley's
treatment is derived for µR ≲ 0.01–0.1 ("fine particle" regime). Beyond that
the correction is applied outside its derivation and can make QPA *worse* with
more confidence attached. Emit a structured `Diagnostic` when any phase's µR
exceeds the fence, in the same style as the existing guards, and record the
per-phase µR in the QPA result object so the number travels with the answer.

Attach the correction to the `QuantitativePhaseAnalysis` object from WP-0304
as an adjustment with both corrected and uncorrected fractions present —
never silently replace the uncorrected numbers.

## Non-goals

- Bulk sample absorption (flat-plate / capillary) — that is WP-0501, a
  different physical effect on the *profile*, not on phase fractions.
- Deriving particle size from the pattern (size *broadening* is a coherent
  domain size, not the particle size Brindley needs — say this in the
  docstring; conflating them is a classic error).

## Tasks

- [ ] Per-phase µ from refined composition + cell volume at the instrument
      wavelength; unit test against published µ values for common phases
- [ ] Brindley τ_p factors; per-phase particle radius as an input field on the
      phase (or the QPA call), defaulting to "not supplied ⇒ no correction"
- [ ] Corrected + uncorrected fractions both present in the QPA result, with
      per-phase µR recorded
- [ ] µR fence diagnostic (outside the fine-particle regime → structured
      diagnostic, surfaced by the strategy engine)
- [ ] Test on a synthetic mixture with a deliberately high-µ phase: the
      correction moves the fractions in the physically correct direction and
      the fence fires when µR is pushed past the limit

## Acceptance

Correction reproduces published τ values; on a synthetic high-contrast
mixture the corrected fractions are closer to truth than the uncorrected ones;
the µR fence fires exactly when it should.

```sh
.venv/bin/python -m pytest tests/test_qpa.py -q
```

## References

- Brindley (1945) Phil. Mag. 36, 347 — particle-absorption correction.
- Taylor & Matulis (1991) J. Appl. Cryst. 24, 14 — practical QPA application
  and the limits of the correction.

## Handover log

- **2026-07-22** — created from the ROADMAP split; not started.

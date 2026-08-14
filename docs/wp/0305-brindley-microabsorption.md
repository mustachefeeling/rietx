# WP-0305 — Brindley microabsorption correction

Milestone: v0.3 · Status: ✅ 2026-07-23
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
[`crystallography/scattering.py`](../../src/rietx/crystallography/scattering.py).
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

- [x] Per-phase µ from refined composition + cell volume at the instrument
      wavelength; unit test against published µ values for common phases
- [x] Brindley τ_p factors; per-phase particle radius as an input field on the
      phase (or the QPA call), defaulting to "not supplied ⇒ no correction"
- [x] Corrected + uncorrected fractions both present in the QPA result, with
      per-phase µR recorded
- [x] µR fence diagnostic (outside the fine-particle regime → structured
      diagnostic, surfaced by the strategy engine)
- [x] Test on a synthetic mixture with a deliberately high-µ phase: the
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
- **2026-07-23** — **done**; five commits (`9f2f18f`…). Decisions & measured
  facts a follow-up should know:
  - **µ source**: bundled `data/mu_McMaster.dat`, an energy-trimmed
    (2–120 keV) 3-column extract of DABAX `CrossSec_McMaster.dat`
    (McMaster 1969; ATTRIBUTION.md updated). xraydb was *not* pulled in —
    it drags sqlalchemy; revisit the coordination when WP-0504 actually
    needs f′/f″. `crystallography/attenuation.py` interpolates log-log and
    **refuses** a wavelength whose grid interval contains an absorption
    edge (photoelectric column rising with E), rather than smearing it.
    Measured vs NIST Hubbell-Seltzer at 8 keV: ≤2.5 % for Z ≥ 9; B −7 %,
    O −3.6 % (known McMaster low-Z weakness; tolerances in the test say so).
  - **τ**: exact parallel-path sphere integral (closed form + series near 0),
    NOT either published fit. Inside |x| ≤ 0.1 it matches the FullProf
    quadratic (1 − 1.450x + 1.426x²) and the MAUD exponential fit to ≲1 %,
    which is also how much those two disagree with each other; unlike them
    it is exact at τ(0)=1 and stays monotone/positive past the fence.
  - **Fence**: Brindley's medium-powder limit is µ·D ≤ 0.1 with D the
    *diameter* (ILL/FullProf QPA notes) ⇒ `BRINDLEY_MU_R_FENCE = 0.05` in
    µ·R. The WP text's "µR ≲ 0.01–0.1" conflated the two conventions.
  - Correction needs **every** phase's `particle_radius_um` (µ̄ is a mixture
    average); partial input → `microabsorption_skipped` +
    MICROABSORPTION_SKIPPED warning, never a guess. µ̄ is the void-free
    solid average (porosity not modelled — documented as conservative).
  - Synthetic acceptance: τ injected into generating scales; uncorrected
    fractions biased ~1.7 % absolute, corrected land within 1 % of truth,
    recovered τ within 0.5 % of injected; fence fires end-to-end through
    `run_stage` on the rebuilt result. Suite 299 passed, ruff clean.
  - Gotcha for exporters (WP-0309): `weight_fraction` stays uncorrected by
    design; a QPA table should print both columns and the τ/µR provenance.

# WP-1132 — a neutron µR, from the table this package already ships

Milestone: unscheduled · Status: ⬜ — **the maintainer is handling this one** (stated
2026-08-24); this file is the specification, not a claim on the work
Depends on: the CW neutron source (PR #108, open) — `NeutronSource` and
`crystallography/neutron.py` are both prerequisites and both land there

## Goal

`Geometry.mu_r` and `Geometry.mu_t` can be **estimated from composition on a
neutron instrument**, from the Sears table this package already ships, with
the same "estimate, or say why not" contract the X-ray path has. Today the
estimator is fenced off from neutrons entirely (PR #108,
`refine._NON_XRAY_ABSORPTION_ESTIMATE`), which is correct but leaves a
neutron capillary fit with no absorption correction unless the user measured
µR themselves.

## Context — why the X-ray estimator is not merely coarse here

`crystallography/attenuation.py` is an **X-ray** compilation: photoabsorption
plus scattering, cross-checked against the Cromer-Liberman f'' table. Running
it on a neutron instrument does not give a rough answer, it gives an unrelated
number, and the two disagree in **kind**, not in precision:

| | X-ray µ/ρ | neutron µ |
|---|---|---|
| λ dependence | ≈ λ³ between edges | σ_abs ∝ **λ** (1/v), σ_scatt flat |
| discontinuities | absorption edges | nuclear **resonances** (isotope-specific) |
| Z dependence | rises steeply and smoothly with Z | no trend in Z at all |
| hydrogen | nearly transparent | one of the strongest attenuators (σ_inc = 80.27 barn) |
| isotopes | identical | up to 3 orders apart (¹⁶⁸Yb 2230 barn vs ¹⁷⁶Yb 2.85) |

The hydrogen row is the one that matters in practice: an organic or hydrous
specimen that an X-ray estimator calls transparent is the specimen a neutron
beam struggles to get through. Writing the X-ray number into `Geometry.mu_r`
would apply a confidently wrong correction with nothing said — the failure
this repo's own rules rank worst.

## What makes it tractable

**The table is already here.** PR #108 ships
`crystallography/neutron.py` over Sears (1992) / *International Tables* C
Table 4.4.4.1, whose `properties()` already returns `sigma_coh`, `sigma_inc`
and `sigma_abs` per species. Nothing new needs licensing or digitising.

The physics is one line, and unlike the X-ray case it has no edges to
interpolate across:

```
mu(lambda) = ( sum_i n_i * [ sigma_abs_i * (lambda / 1.798) + sigma_coh_i + sigma_inc_i ] ) / V
```

with `n_i` the occupancy-weighted atom count per cell, `V` the cell volume in
Å³, σ in barn, and **1.798 Å** the 2200 m/s wavelength at which σ_abs is
tabulated. µR and µt then reuse `attenuation.packed_mu_r` and the flat-plate
twin unchanged — the packing-fraction and geometry half is radiation-blind
and must not be duplicated.

## Checklist (commit-sized)

1. `crystallography/neutron.py`: `linear_attenuation_neutron(element_counts,
   volume, wavelength)` beside the existing `b_coh`/`properties`, citing Sears
   1992 in the docstring per the house rule. Its own test: σ_abs must scale
   **linearly** in λ (the 1/v law is the whole difference from the X-ray case),
   and a hydrogen-bearing composition must come out far *more* attenuating than
   the X-ray estimator says for the same cell — a test that would fail if the
   X-ray table were wired in by mistake.
2. `optimize/qpa.py`: dispatch `estimate_capillary_mu_r` /
   `estimate_flat_plate_mu_t` on `instrument.source.kind` rather than assuming
   X-ray. One seam, not two code paths — the volume-fraction weighting,
   packing fraction and geometry are shared, only µ per phase differs.
3. `refine.py`: `_resolve_specimen_absorption` stops returning
   `_NON_XRAY_ABSORPTION_ESTIMATE` for `neutron_cw` and estimates instead;
   `estimate_mu_r` likewise. **Keep the fence for every source that still has
   no table** — it is the mechanism that made this WP visible, and deleting it
   wholesale would re-open the hole for TOF.
4. **Refuse rather than guess where the table cannot answer**: a resonant
   absorber (`is_resonant_absorber`) at a λ near its resonance, where the
   thermal σ_abs is wrong in principle rather than merely imprecise. This is
   the neutron analogue of the X-ray "wavelength straddles an edge" reason and
   should read the same way. See also issue #113 (TOF resonant absorption).
5. Validate against a real measurement — the Cr₂WO₆ BT-1 60 K histogram
   (λ = 2.078 Å) is the obvious candidate, since a heavy W-bearing oxide in a
   vanadium can is where µR is least negligible.
6. Manual: a row in the specimen-absorption section of Part 2 with a
   `*Source:*` line, and Part 1 prose saying an estimate now happens on
   neutron instruments.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_neutron_cw.py tests/test_qpa.py \
    tests/test_acceptance_capillary.py -q
```

plus the estimated µR for the Cr₂WO₆ case quoted against a hand-computed value
from the Sears table, and the X-ray control in
`tests/test_neutron_cw.py::test_the_xray_control_still_estimates` still green —
that test exists precisely so a future change here cannot quietly turn X-ray
estimation off.

## Deliberately not in scope

- **Energy-dependent σ_abs near a resonance.** Item 4 *refuses* there; making
  it answer is issue #113's subject and needs a tabulation this package does
  not have.
- **TOF.** A bank spans a range of λ, so µ varies within one histogram; the
  v2 fence covers it.
- **Making µR refinable.** It is exactly singular against scale ⊗ Biso
  (`model/absorption.py`), and that is unchanged by the radiation.

## Handover log

- **2026-08-24** — Specified while fixing two defects found in PR #108's own
  code. First, `Instrument.constant_wavelength_neutron` wrapped `mu_r` in a
  `Parameter` where `Geometry.mu_r` is a plain float, so *every* call passing
  a µR raised `ValidationError`; no test passed one, which is why it survived.
  Second, and worse, `_resolve_specimen_absorption` runs **automatically** at
  fit time, so a neutron capillary with a declared radius was silently having
  an X-ray µR computed and written onto it. Both fixed in PR #108; the fence
  and this WP are what the second one turned into.

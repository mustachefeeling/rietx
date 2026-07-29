# pxrd-refine — validation matrix

<!-- GENERATED FILE — do not edit by hand.
     Source: tests/validation_matrix.py
     Regenerate: .venv/bin/python -m tests.validation_matrix
     Guarded by: tests/test_validation_matrix.py (fast suite) -->

Every real-data assertion in this repository, and what its tolerance is
referenced to. A bar without its referent is not a claim: `abs(a - 4.156780) <
2e-4` and `abs(delta_a) < 1e-9` look alike and are not remotely the same
statement — the first is a certified value the fit does not reach and does not
claim to, the second is two of our own fits that must agree to floating point.

The policy this table implements is in [DESIGN.md](DESIGN.md#testing--validation-policy);
the measured milestone records are in [milestones/](milestones/).

## The one rule that shapes everything below

**Judge a correction by what it changed, never by delta Rwp.** Of the eight
corrections in v0.5, two provably cannot move Rwp, one moves it the *wrong way*
when it is right, and the two largest accuracy wins are invisible in it. A
validation matrix whose columns were agreement indices would score that
milestone as having delivered nothing — which is why two of the tiers below
are kinds of evidence rather than kinds of tolerance.

## Tiers

### `identity`

Referenced to floating-point arithmetic, not to any physical quantity.  Two runs that must agree because the difference between them is provably an exact reparameterisation, a value that must be exactly what it was held at, or a sum that must close.  Bars are 1e-12 to 1e-6 and the measured margin is expected to sit orders inside — an identity row whose margin creeps toward its bar is a bug report, not a passing test.

### `certificate`

Referenced to a certified value **with its stated uncertainty**.  A row in this tier must say whether it asserts at certificate grade or is systematics-limited, because on lab data most are the latter: SRM 676a's axial ratio is certificate-grade (+30 ppm against a k=2 uncertainty of ~21 ppm) while its absolute axes carry a −300 ppm d-scale systematic that no widened band should be allowed to hide.

### `cross_code`

Referenced to another code's converged result, **with its protocol adopted** — the same refined set, the same held parameters, the same excluded regions, and a channel count checked to match before any number is compared.  A cross-code figure computed over different channels with a different free set is not a comparison (v0.2 learned this the expensive way: a plausible guessed protocol gave Rwp 16 % and +390 ppm; the mirrored one gives 9.73 % and +116 ppm).

### `spread`

Referenced to a published inter-laboratory spread — what practitioners actually achieve on this specimen — and never to sigma.  The QPA weight-fraction esds are 0.1-0.4 wt %, an order of magnitude below the measured errors, so a sigma-referenced bar would fail every participant in the round robin including the ones who got the right answer.

### `own_result`

Referenced to this package's own other result under a fixed protocol — the chained fit against the independent one, the Rietveld cell against the Le Bail cell.  Not truth, but far tighter than any external tolerance: two runs differing only in starting values should agree well inside the physics.

### `characterisation`

Asserts no accuracy at all.  Either the *shape* of a known systematic (that a cell offset is uniform across axes, hence a d-scale convention and not a structural error), or that a model is **inadmissible** — an Rwp improvement both statistical tests bless and a physics guard rejects.  This tier is how a measured failure gets recorded as a result instead of being tuned away.

### `prediction`

A parameter-free prediction written down **before** the measurement, then checked.  The strongest evidence in this repo and the rarest: the capillary correction's ΔB = c(µR)·λ²/2 predicted 0.0166542 Å² and the refits moved every Biso by 0.0166542, and the dispersion prediction (each phase's Bragg-power ratio, no free parameters) beat itself — predicted RMS 0.83 wt %, measured 0.69.

### `ceiling`

**Not a tier.**  A regression bar — `status == 'converged'`, `rwp < 0.20`, `gof < 2.0` — that carries no accuracy claim and is loose on purpose.  Labelled explicitly so it can never be read as validation.  Every acceptance test has these; only the rows whose *only* tier is `ceiling` are claiming nothing else.

## Start dependence

How many independent starting points a quoted number has to survive. This is
a validation axis because it was measured to change a conclusion: sweeping the
Stephens strain seed over 400/800/1600/3000 on round-robin brucite leaves the
coefficients spanning ~100 % relative spread under *both* solvers, and moves the
unconstrained fit in and out of the physical cone (15, 12, 0, 0 reflections
violating). A single-start acceptance number would have called that specimen
either fine or broken depending on which seed the suite happened to pin.

1. A **cell parameter, weight fraction or scale** may be quoted from one start.
   These are well-conditioned and the staged plan reaches the same basin from any
   sane starting model. Every `certificate`, `cross_code` and `spread` row below
   is single-start, and that is not a weakness.
2. A **width or shape parameter entering through a square root, a cone, or a
   softplus floor** must survive a documented sweep before any number is quoted
   from it — that is the class where the objective is flat or non-convex near
   the start.
3. When a sweep is run and the parameters move but the **conclusion** does not,
   the conclusion is what gets recorded and the sweep goes in the docstring. Pinning
   a per-seed number would convert a known instability into a flaky test.

## Datasets

| Key | File | Role | What it is |
|---|---|---|---|
| `srm660c` | `tests/data/nist_srm660c_100a.cif` | **absolute anchor** | NIST SRM 660c LaB6, lab Cu Ka doublet + graphite analyzer; the certification measurement itself |
| `srm676a` | `tests/data/qarr/corundum.prn` | **absolute anchor** | NIST SRM 676a corundum, lab Cu Ka; the round robin's pure-phase pattern doubles as the cell-anchor specimen |
| `nac` | `tests/data/11BM_NAC.fxye` | characterisation | APS 11-BM synchrotron Na2Ca3Al2F14 with a CaF2 impurity, lambda = 0.4139090 A from the .prm |
| `fap` | `tests/data/FAP.XRA` | cross-code | GSAS-II LabData tutorial fluorapatite; FAP.EXP is GSAS's converged fit and supplies both the reference values and the protocol |
| `qarr` | `tests/data/qarr` | **absolute anchor** | IUCr CPD QPA round-robin patterns (samples 1a-1h, 2, 4 and six pure phases), Cu Ka doublet, graphite diffracted-beam monochromator |
| `srm660a_capillary` | `tests/data/11BM_LaB6_660a.fxye` | consistency only — *never* an anchor | APS 11-BM SRM 660a LaB6 in the beamline's documented 0.81 mm Kapton bore; lambda was calibrated against this very standard |

`consistency` is a fence, not a label: 11-BM calibrated its wavelength against
SRM 660a LaB6 itself, so a refined LaB6 cell from that file reproduces the
certificate by construction. A guard refuses to let any such dataset carry a
`certificate` row.

## The matrix

### `tests/test_acceptance_srm660c.py`

The absolute lab anchor. NIST's own SRM 660c certification measurement, refined against the cell recomputed for this dataset's temperature block.

#### `test_srm660c_lab6_rietveld`

`certificate` `identity` `ceiling` · dataset `srm660c`

**Claims:** the absolute lab cell anchor: a, the Berar-Lelann esd inflation, the held zero shift, the sample displacement and the Ka2 ratio

**Referenced to:** NIST's cell recomputed for this dataset's 20.85 C block, 4.156780 A, under an explicitly interim +-2e-4 A band; the certificate's own +-8e-6 at 22.5 C is NOT claimed and the residual is a characterised cotTheta/sin2Theta aberration (divergence, tube tails, monochromator passband) fenced to the v2 FPA work

**Measured:** a = 4.156895(25) A, +28 ppm; Rwp 8.66 %, GoF 1.87; zero_shift held at exactly 0.0; displacement -0.0801 mm vs the CIF's -0.07877

#### `test_srm660c_extinction_does_no_harm`

`characterisation` `ceiling` · dataset `srm660c`

**Claims:** secondary extinction freed on a specimen that has none refines to zero and does not move the anchor

**Referenced to:** the cell must return to its own unextinguished value within the same 2e-4 A band; the extinction parameter itself is one-sided (< 1e-2 from a 1e-3 seed)

**Measured:** extinction 2.075e-10 from a 1e-3 seed; Rwp 0.08661400134, a 4.15689532166 — the warm-extend path is bit-equal

### `tests/test_acceptance_srm676a.py`

The second absolute anchor, and the sharper one — but only on the axial ratio, where the lab d-scale systematic cancels.

#### `test_srm676a_corundum_cell_anchor`

`certificate` `characterisation` `identity` `ceiling` · dataset `srm676a`

**Claims:** c/a at certificate grade, the absolute axes only at lab-realistic grade, and the difference between them asserted to be a uniform d-scale systematic rather than a structural error

**Referenced to:** NIST SRM 676a certificate a = 4.759355(80), c = 12.99231(15) A (k = 2, 22.5 C).  c/a's relative k=2 uncertainty is ~21 ppm and the bar is 100 ppm — a small multiple of it.  The absolute bar is 600 ppm, nowhere near certificate grade, and the uniformity check |da - dc| < 1.5e-4 is what stops an esd laundering a many-sigma systematic

**Measured:** c/a +30 ppm; absolute axes -313 / -283 ppm with |da - dc| within 3e-5; Rwp 14.4 %, GoF 1.61 against a GoF floor of 1.5-1.9 for analytical-PSF lab fits (Cline 2015)

### `tests/test_acceptance_fap.py`

The one cross-code comparison. GSAS-II's converged fluorapatite tutorial, with its protocol mirrored parameter for parameter.

#### `test_fap_lab_rietveld_matches_gsas`

`cross_code` `characterisation` `identity` `ceiling` · dataset `fap`

**Claims:** agreement with GSAS-II's converged fit on the same channels under the same protocol, with the residual cell offset asserted to be a uniform d-scale convention difference

**Referenced to:** GSAS's own FAP.EXP: Rwp 0.1005, Rp 0.0766, a = 9.371724(36), c = 6.885867(37) A on 5750 channels after its EXC 2 record.  Bars are rel=0.10 on the R-factors and 300 ppm on the cell — a convention-aware band, not 1e-4 A ground truth.  The esd window is one-sided on purpose: ours carry Berar-Lelann inflation and GSAS's do not

**Measured:** Rwp 0.0973 vs 0.1005, Rp 0.0776 vs 0.0766, cell +116/+113 ppm with the two agreeing inside 1e-4 (the uniformity claim); channel count 5750 exactly

### `tests/test_acceptance_nac.py`

The synchrotron vertical slice, and the FitReport's impurity claim: CaF2 is found from unmatched peaks rather than declared.

#### `test_nac_lebail_then_rietveld`

`own_result` `characterisation` `ceiling` · dataset `nac`

**Claims:** Le Bail then two-phase Rietveld; the cell is checked much more tightly against our own Le Bail pass than against the literature, and the CaF2 impurity is found by the report rather than declared

**Referenced to:** literature a = 10.2496-10.2506 A (high-accuracy powder) and 10.257(1) (Courbion & Ferey 1988) under a 2e-3 A band that allows for the beamline wavelength calibration; the Rietveld-vs-Le Bail agreement is held to 5e-4 A

**Measured:** a = 10.251285(12) A, Rwp 9.2 %; CaF2 lands at 5.4631 A

#### `test_nac_extinction_on_the_main_phase_is_bounded_and_unbiasing`

`identity` `characterisation` `ceiling` · dataset `nac`

**Claims:** extinction freed only on the well-determined phase stays bounded and does not bias the cell; the impurity's stays exactly zero

**Referenced to:** the correction's own size (min E > 0.8, i.e. at most ~12 % on the strongest line) and the unextinguished cell.  The impurity extinction is exact-zero because it is never freed — freeing it was measured to run away to E ~ 0.31

**Measured:** min E > 0.8 on the main phase; phases[1].extinction == 0.0 exactly

### `tests/test_acceptance_qpa_roundrobin.py`

Quantitative phase analysis against weighed truth, at tolerances referenced to what the round robin's participants achieved.

#### `test_read_prn_two_column_ascii`

`identity` · dataset `qarr`

**Claims:** the two-column .prn reader contract: grid, step, no esd column

**Referenced to:** the files themselves — 7251 points from 5 to 150 deg at 0.02 deg, to 1 microdeg because cpd-1e truncates its ordinates to seven characters; sigma is None so the Poisson fallback is what weights these fits

**Measured:** exact

#### `test_sample1_fractions_within_participant_spread`

`spread` `identity` `ceiling` · dataset `qarr`

**Claims:** weight fractions on the eight sample-1 mixtures, and the closure of the fraction sum

**Referenced to:** the weighed composition is truth; the tolerance is the published participant spread (Madsen 2001 Fig. 2), 6.0 wt % for majors and 2.0 for traces below 5 wt %.  Never sigma(W): those esds are 0.1-0.4 wt %, an order of magnitude below the measured errors

**Measured:** worst 5.13 wt % (1f zincite), traces <= 1.3, RMS 2.26; closure exact to 1e-6

#### `test_sample1_bias_has_the_dispersion_shape`

`characterisation` · dataset `qarr`

**Claims:** the sample-1 residual bias is not noise: its sign is fixed per phase and its shape is the one neglected anomalous scattering predicts

**Referenced to:** the per-phase Bragg-power ratios from f' at Cu Ka (1.0542 corundum / 0.8441 zincite / 1.0728 fluorite), which set the signs; WP-0502 separately excluded surface roughness as the competing explanation, which is what makes the attribution single-valued

**Measured:** zincite mean < -1.0, corundum mean > +0.5, fluorite |mean| < 2.0 wt %

#### `test_sample2_brucite_march_dollase`

`spread` `characterisation` `identity` `ceiling` · dataset `qarr`

**Claims:** platy brucite is detected as preferred orientation rather than absorbed into the fractions

**Referenced to:** participant spread again on the fractions; the March coefficient is judged as physics (r < 1 means platy, and 0.4 < r < 0.9 is far enough from the r = 1 identity to be a detection rather than a fitted nothing)

**Measured:** r ~ 0.68; worst fraction 2.9 wt %; H Biso held at exactly 2.5

#### `test_sample4_microabsorption_characterised_not_hidden`

`characterisation` `ceiling` · dataset `qarr`

**Claims:** the round robin's designed Brindley-defeating sample fails in the documented direction, the muR fence fires, and the correction moves two of three phases the right way

**Referenced to:** **no accuracy band is claimed** — this specimen is meant to defeat the correction.  What is asserted is the sign and rough size of each error, that BRINDLEY_OUTSIDE_REGIME names magnetite, and that tau < 1 < tau holds across the absorption contrast.  Zircon is deliberately NOT asserted to improve (measured -9.2 to -9.4)

**Measured:** corundum +24, zircon -15, magnetite -9 wt %

**Diagnostics:** `BRINDLEY_OUTSIDE_REGIME`

### `tests/test_acceptance_dispersion.py`

The same round robin with anomalous scattering applied — a pre-registered, parameter-free prediction about numbers already recorded in the v0.3 milestone.

#### `test_sample1_fractions_beat_the_dispersion_free_fit`

`prediction` `spread` `identity` `ceiling` · dataset `qarr`

**Claims:** with f' and f'' applied, every sample-1 mixture meets a tolerance the dispersion-free fit could not

**Referenced to:** the weighed composition at 2.5 wt %, tightened from the participant spread's 6.0/2.0 — the tightening IS the claim, and it was written down before the refits

**Measured:** worst 1.39 wt % (was 5.13)

#### `test_the_microabsorption_shape_was_mostly_dispersion`

`prediction` `own_result` · dataset `qarr`

**Claims:** the signed bias v0.3 attributed to microabsorption collapses when dispersion is applied — a v0.3 conclusion re-derived, not merely a number improved

**Referenced to:** the frozen V03_ERRORS table (the eight measured signed wt % errors from milestones/v0.3.md), phase by phase.  The prediction was parameter-free and beat itself: predicted RMS 0.83, measured 0.69

**Measured:** RMS 2.26 -> 0.69 wt %; zincite's -1 wt % mean bias goes to |mean| < 1.0

#### `test_zincite_cell_does_not_move`

`identity` · dataset `qarr`

**Claims:** dispersion is an intensity correction and must not move a non-centrosymmetric structure's cell

**Referenced to:** the same fit with the block off; 1e-5 A on a and c

**Measured:** within 1e-5 A

#### `test_zincite_oxygen_adp_becomes_physical`

`characterisation` · dataset `qarr`

**Claims:** the sharpest single dispersion result: B(O) comes off its floor once Zn's missing f' stops being absorbed by a displacement parameter, while Rwp barely moves

**Referenced to:** physical plausibility, not a reference value — B(O) below 0.1 A^2 is a parameter pinned on a bound, and 0.2-1.2 is the range an oxide oxygen actually occupies.  Rwp is asserted only one-sided, because this is exactly a case where the fit statistic does not see the fix

**Measured:** B(O) 0.022 -> 0.429 A^2

#### `test_srm660c_lattice_parameter_is_untouched`

`identity` · dataset `srm660c`

**Claims:** the absolute anchor survives the flip: a does not move when dispersion is applied

**Referenced to:** the dispersion-off baseline, at 2e-6 A — well inside the 25e-6 A esd, so the anchor is safe either way

**Measured:** a = 4.156895 A both ways

#### `test_srm660c_displacement_parameters_absorb_the_change`

`characterisation` · dataset `srm660c`

**Claims:** where the change lands instead: the displacement parameters, by 12 % and 22 %

**Referenced to:** the dispersion-off baseline; floors on the size of the move (>0.02 and >0.05 A^2) plus a physical band on the result, which is a characterisation and not an accuracy claim — no certified Biso exists for this specimen

**Measured:** B(La) and B(B) move ~12 % / ~22 %; Rwp 8.661 -> 8.640 %

#### `test_the_neglect_diagnostic_clears_when_the_block_is_on`

`identity` · dataset `srm660c`

**Claims:** 'off' is loud: the neglect diagnostic is present dispersion-off and absent dispersion-on

**Referenced to:** the diagnostic set itself — set membership, both directions

**Measured:** exact

**Diagnostics:** `DISPERSION_NEGLECTED`, `DISPERSION_NEGLECTED` asserted *absent*

### `tests/test_acceptance_capillary.py`

A correction that provably cannot improve the fit, on real data. The whole of its content is a predicted shift in every displacement parameter.

#### `test_estimated_mu_r_matches_the_documented_capillary`

`characterisation` `identity` · dataset `srm660a_capillary`

**Claims:** muR from composition and the documented bore lands in the physically plausible band, and the public estimator agrees with what the refinement resolved internally

**Referenced to:** the beamline's documented 0.81 mm Kapton bore and a packing fraction of 0.35-0.6, which spans muR 0.47-0.81; the estimator/resolver agreement is floating-point (rel=1e-9)

**Measured:** muR 0.674, method rouse_cylinder, not out of range

#### `test_capillary_absorption_is_an_exact_reparameterisation`

`prediction` `identity` · dataset `srm660a_capillary`

**Claims:** the headline: applying the correction provably cannot change the fit, and the whole of its content is a predicted shift in every Biso

**Referenced to:** the analytic prediction DeltaB = c(muR)*lambda^2/2, computed before the refits.  Rwp and the cell are held to 1e-6 and 1e-9 A **between two of our own fits** — referenced to floating point, not to any external value, because Rouse's expression factors exactly into a Debye-Waller shape

**Measured:** Delta Rwp 3.2e-8, Delta a -7.9e-12 A, every Biso +0.0166542 against a predicted 0.0166542

#### `test_fit_quality_and_the_circular_cell`

`characterisation` `ceiling` · dataset `srm660a_capillary`

**Claims:** the fit is sound and its cell agrees with SRM 660a — recorded as consistency, explicitly NOT as an anchor

**Referenced to:** **circular by construction**: 11-BM calibrated lambda against LaB6 itself (the file's own calibration header), so this cell reproduces the standard whatever the code does.  The 1e-4 relative band is a divergence guard, deliberately generous

**Measured:** 16 ppm from the SRM 660a certificate; Rwp 8.85 %

#### `test_the_absorption_shift_is_independent_of_dispersion`

`prediction` `identity` `characterisation` · dataset `srm660a_capillary`

**Claims:** the absorption identity still holds on a dispersion-on model, and the two corrections are separable in size and sign

**Referenced to:** the same analytic DeltaB prediction, re-measured on top of dispersion; plus a sign/magnitude cross-check that dispersion moves B(La) the other way and 2.6x further

**Measured:** Delta B still 0.0166542 to 1e-5; dispersion moves B(La) by about -0.044 A^2

### `tests/test_acceptance_sequential.py`

A warm-started chain over the round robin: what changes when only the starting point changes.

#### `test_chained_qpa_within_participant_spread`

`spread` `identity` · dataset `qarr`

**Claims:** a warm-started chain meets the unchained suite's criterion, unchanged

**Referenced to:** the QPA suite's own MAJOR_TOL/TRACE_TOL, imported rather than restated, so what differs between the two suites is only the chaining

**Measured:** identical to the independent fits' record

#### `test_chained_agrees_with_independent_fits`

`own_result` · dataset `qarr`

**Claims:** chaining changes the starting point, not the answer

**Referenced to:** this package's own independent fits under the same protocol, at 1 wt % and 0.005 in Rwp — generous rather than tight, and framed in participant-spread units because that is what the quantity means

**Measured:** mean Rwp 0.1278 either way; QPA identical to the v0.3 record

#### `test_cells_are_stable_across_the_series`

`characterisation` · dataset `qarr`

**Claims:** a trajectory that should be flat is flat: no trend imprinted by the chaining order

**Referenced to:** the trajectory's own spread — a slope is only a finding if it exceeds the scatter it is drawn from.  This is the shape check that separates a measured trajectory from an ordering artefact

**Measured:** per-phase spread < 20e-4 A with no monotone drift

#### `test_warm_start_iteration_cost_is_reported`

`characterisation` `ceiling` · dataset `qarr`

**Claims:** the headline iteration saving is printed and only divergence is gated — the number is a finding, not a bar

**Referenced to:** **deliberately not asserted.** 2863 iterations unchained, 1623 re-walking the staged plan warm, 904 with the plan collapsed; the carry-glob hypothesis was refuted at 838. Gating a speed number would turn machine noise into a test failure

**Measured:** 904 vs 2863 iterations at identical mean Rwp

#### `test_the_hostile_series_exercises_the_reseed_fence`

`identity` `characterisation` · dataset `qarr`

**Claims:** the reseed fence's accounting is exact, and a reseed never leaves the fit worse than the warm start it rejected

**Referenced to:** internal consistency: the SEQUENTIAL_RESEED diagnostic count must equal the number of entries flagged reseeded, exactly.  The fence never fired on the hostile series — the collapsed refit recovers a bad warm start within the fit — so it is insurance, pinned by unit tests rather than by this suite

**Measured:** exact accounting; zero reseeds on the hostile series

**Diagnostics:** `SEQUENTIAL_RESEED`

#### `test_series_exports`

`identity` · dataset `qarr`

**Claims:** the series CSV and trajectory plot exist with the declared columns and one row per pattern

**Referenced to:** the export contract itself

**Measured:** exact

### `tests/test_acceptance_stephens.py`

Anisotropic strain, and the matrix's canonical inadmissibility result — an improvement both statistical tests bless and the physics rejects.

#### `test_brucite_improvement_is_justified_but_leaves_the_physical_cone`

`characterisation` · dataset `qarr` · survives 4 starts

**Claims:** an Rwp improvement that both statistical tests bless is rejected by a physics guard, on real data — the matrix's canonical inadmissibility row

**Referenced to:** **no accuracy claim.** Hamilton at alpha = 0.05 and Delta BIC > 100 both pass; the strain-variance cone sigma^2(M) >= 0 fails on 12 of 43 reflections, so STEPHENS_STRAIN_NOT_POSITIVE fires and no S_HKL is quotable.  The r ~ 0.65 March coefficient is checked against WP-0310's own measurement on the same material

**Measured:** Rwp 18.55 -> 17.90 %, Delta BIC +488, 3 parameters added, anisotropy 3.45x on an injected 3.46x

**Diagnostics:** `STEPHENS_STRAIN_NOT_POSITIVE`

#### `test_corundum_is_reported_isotropic`

`characterisation` `ceiling` · dataset `qarr`

**Claims:** the control: an isotropic specimen must be reported isotropic, and must never leave the cone

**Referenced to:** the Layer-1 strain diagnostic's own thresholds (not detected, R^2 < 0.5, anisotropy < 2.0) plus the derived pattern count for R-3c

**Measured:** anisotropy 1.60x, 4 patterns, > 40 reflections; never leaves the cone at any seed

#### `test_corundum_block_is_inert_and_bic_says_so_where_hamilton_does_not`

`characterisation` `identity` · dataset `qarr`

**Claims:** freeing the block on an isotropic specimen is inert, and the two statistics disagree about whether that is fine — which is why the policy quotes Delta BIC and not Hamilton

**Referenced to:** Hamilton's R-ratio test at alpha = 0.05 **passes** a 0.13 % chi^2 improvement from three inert parameters, exactly as it passes brucite's real 6.9 % one: its threshold does not grow with the channel count, and these patterns have 7251 channels.  Delta BIC separates them (+488 vs -17).  The certificate-grade c/a is asserted not to move (rel=1e-4)

**Measured:** Delta BIC -17 while Hamilton says justified; c/a unmoved

#### `test_constrained_solver_keeps_brucite_inside_the_cone`

`characterisation` · dataset `qarr` · survives 4 starts

**Claims:** under solver='lm' the cone is carried as a linear inequality and brucite comes back inside it — at a higher Rwp, which is the point

**Referenced to:** the physics constraint itself: sigma^2(M) > 0 on all 43 reflections, with the optimum sitting on the cone face.  Rwp is bounded loosely and is expected to be WORSE than the unconstrained fit's

**Measured:** 0 of 43 violations; Rwp 0.18417 against TRF's 0.17899

#### `test_unconstrained_solver_leaves_the_cone_on_the_same_data`

`characterisation` · dataset `qarr` · survives 4 starts

**Claims:** the control for the row above: the default TRF driver, same data, leaves the cone

**Referenced to:** the same cone test, opposite direction — at least 10 of 43 reflections violating, plus the guard diagnostic

**Measured:** 12 of 43 violations at the pinned seed; 15/12/0/0 across the four-seed sweep, which is why that row carries starts=4

**Diagnostics:** `STEPHENS_STRAIN_NOT_POSITIVE`

## Known gaps

A matrix that lists only what passed is marketing. These are the holes a reader
should know about before trusting a number, each with what would close it.

- **Every acceptance number in the repo is a Cu Ka measurement.** Six anodes ship (Cr/Fe/Co/Cu/Mo/Ag plus Ka1-only variants) and what is validated for the other five is the wavelength table and its checks, not a refinement.  The cheapest close is one Co Ka pattern from an Fe-bearing specimen — the routine real case, since Cu Ka fluoresces Fe (mu/rho 297.7 vs 56.2) — which would exercise dispersion, absorption and the per-anode K-beta contamination check at once.

- **No dataset here can constrain a low-angle intensity correction.** The qarr phases first reflect at 25.6/28.3/31.8 deg and SRM 660c at 21.4, so surface roughness (WP-0502) has a negative acceptance result only: two of three phases collapse to the identity and raise ROUGHNESS_UNCONSTRAINED.  Closing it needs a pattern starting below ~15 deg with real low-angle reflections.

- **The SRM 660c certificate band is not reached and is not claimed.** Measured +28 ppm against a certificate uncertainty of +-8e-6 A.  The residual is a characterised cotTheta/sin2Theta aberration — equatorial divergence, tube tails, monochromator passband — which is the fundamental-parameters territory fenced to v2, not a tuning gap.

- **GoF does not reach 1 on lab data and should not be expected to.** Cline et al. (2015) put the floor for analytical-PSF fits on this instrument class at 1.5-1.9; FPA reaches 1.08.  Measured 1.61 on corundum with Rexp ~ 8.9 %, so Rwp 14.4 % is mostly counting statistics.  A policy demanding GoF -> 1 would be demanding FPA.

- **The Apple-GPU (MPS) evidence is maintainer-machine-only.** Every torch-mps assertion is gated on torch.backends.mps.is_available(), which is False on hosted macOS runners.  The all-fp32 refinement landing 3.5e-8 A from numpy fp64 is real-hardware evidence for the fp64-host boundary, and no CI job reproduces it.  A green macOS job must not be read as 'MPS verified'.

- **Multi-phase CIF round-tripping is not validated.** write_refinement_cif's round trip is checked single-phase only; a multi-phase re-read was never a v0.3 commitment.  Whatever the frozen API says about CIF round-tripping has to narrow to that.

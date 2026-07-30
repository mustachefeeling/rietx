"""The validation matrix: what every acceptance assertion is referenced to.

Data plus the renderer that turns it into ``docs/VALIDATION.md``; the
assertions live next door in ``tests/test_validation_matrix.py``, which keeps
this file honest and asserts the committed doc matches its regeneration — so
the doc cannot drift the way a hand-maintained table does.  Regenerate with

    .venv/bin/python -m tests.validation_matrix

(the same convention the backend goldens use).

The reason this exists is that a tolerance is meaningless without its
referent.  ``abs(a - 4.156780) < 2e-4`` and ``abs(Δa) < 1e-9`` look like the
same kind of statement and are not: the first is a certified value with a
stated uncertainty the fit does not reach and does not claim to, the second is
two of our own fits that must agree to floating-point.  Sorting every bar in
the tree by its referent is what turns a pile of numbers into a claim about
what this package has been shown to do.

**Judge a correction by what it changed, never by Δ Rwp.**  That is the v0.5
milestone's method result, and it is why the vocabulary below has
``characterisation`` and ``prediction`` in it.  Of that milestone's eight
corrections, two provably cannot move Rwp, one moves it the *wrong way* when
it is right, and the two largest accuracy wins are invisible in it.  A matrix
whose columns were agreement indices would score the milestone as having
delivered nothing.
"""

from __future__ import annotations

from dataclasses import dataclass, field

#: The closed tier vocabulary: what a bar can be referenced to.  Adding a tier
#: is a deliberate act — the guard rejects any row naming something not here,
#: which is what stops the next suite from inventing an eighth kind of
#: reference in a docstring nobody re-reads.
TIERS: dict[str, str] = {
    "identity": (
        "Referenced to floating-point arithmetic, not to any physical "
        "quantity.  Two runs that must agree because the difference between "
        "them is provably an exact reparameterisation, a value that must be "
        "exactly what it was held at, or a sum that must close.  Bars are "
        "1e-12 to 1e-6 and the measured margin is expected to sit orders "
        "inside — an identity row whose margin creeps toward its bar is a "
        "bug report, not a passing test."
    ),
    "certificate": (
        "Referenced to a certified value **with its stated uncertainty**.  A "
        "row in this tier must say whether it asserts at certificate grade "
        "or is systematics-limited, because on lab data most are the latter: "
        "SRM 676a's axial ratio is certificate-grade (+30 ppm against a k=2 "
        "uncertainty of ~21 ppm) while its absolute axes carry a −300 ppm "
        "d-scale systematic that no widened band should be allowed to hide."
    ),
    "cross_code": (
        "Referenced to another code's converged result, **with its protocol "
        "adopted** — the same refined set, the same held parameters, the "
        "same excluded regions, and a channel count checked to match before "
        "any number is compared.  A cross-code figure computed over "
        "different channels with a different free set is not a comparison "
        "(v0.2 learned this the expensive way: a plausible guessed protocol "
        "gave Rwp 16 % and +390 ppm; the mirrored one gives 9.73 % and "
        "+116 ppm)."
    ),
    "spread": (
        "Referenced to a published inter-laboratory spread — what "
        "practitioners actually achieve on this specimen — and never to "
        "sigma.  The QPA weight-fraction esds are 0.1-0.4 wt %, an order of "
        "magnitude below the measured errors, so a sigma-referenced bar "
        "would fail every participant in the round robin including the ones "
        "who got the right answer."
    ),
    "own_result": (
        "Referenced to this package's own other result under a fixed "
        "protocol — the chained fit against the independent one, the "
        "Rietveld cell against the Le Bail cell.  Not truth, but far tighter "
        "than any external tolerance: two runs differing only in starting "
        "values should agree well inside the physics."
    ),
    "characterisation": (
        "Asserts no accuracy at all.  Either the *shape* of a known "
        "systematic (that a cell offset is uniform across axes, hence a "
        "d-scale convention and not a structural error), or that a model is "
        "**inadmissible** — an Rwp improvement both statistical tests bless "
        "and a physics guard rejects.  This tier is how a measured failure "
        "gets recorded as a result instead of being tuned away."
    ),
    "prediction": (
        "A parameter-free prediction written down **before** the "
        "measurement, then checked.  The strongest evidence in this repo and "
        "the rarest: the capillary correction's ΔB = c(µR)·λ²/2 predicted "
        "0.0166542 Å² and the refits moved every Biso by 0.0166542, and the "
        "dispersion prediction (each phase's Bragg-power ratio, no free "
        "parameters) beat itself — predicted RMS 0.83 wt %, measured 0.69."
    ),
    "ceiling": (
        "**Not a tier.**  A regression bar — `status == 'converged'`, "
        "`rwp < 0.20`, `gof < 2.0` — that carries no accuracy claim and is "
        "loose on purpose.  Labelled explicitly so it can never be read as "
        "validation.  Every acceptance test has these; only the rows whose "
        "*only* tier is `ceiling` are claiming nothing else."
    ),
}

#: Tiers that make a claim about accuracy or physics; ``ceiling`` alone does
#: not, and a row that carries only it must say so rather than look like an
#: anchor.
CLAIM_TIERS = tuple(t for t in TIERS if t != "ceiling")


@dataclass(frozen=True)
class Dataset:
    """A measured pattern and what it is allowed to anchor.

    ``role`` is load-bearing rather than descriptive.  ``consistency`` marks a
    dataset whose agreement with its own standard is **circular**: 11-BM
    calibrated its wavelength against SRM 660a LaB₆, so a refined LaB₆ cell
    from that file reproduces the certificate by construction.  The guard
    refuses to let a ``consistency`` dataset carry a ``certificate`` row.
    """

    path: str
    description: str
    role: str  # "absolute" | "cross_code" | "consistency" | "characterisation"


DATASETS: dict[str, Dataset] = {
    "srm660c": Dataset(
        "nist_srm660c_100a.cif",
        "NIST SRM 660c LaB6, lab Cu Ka doublet + graphite analyzer; the "
        "certification measurement itself",
        "absolute"),
    "srm676a": Dataset(
        "qarr/corundum.prn",
        "NIST SRM 676a corundum, lab Cu Ka; the round robin's pure-phase "
        "pattern doubles as the cell-anchor specimen",
        "absolute"),
    "nac": Dataset(
        "11BM_NAC.fxye",
        "APS 11-BM synchrotron Na2Ca3Al2F14 with a CaF2 impurity, "
        "lambda = 0.4139090 A from the .prm",
        "characterisation"),
    "fap": Dataset(
        "FAP.XRA",
        "GSAS-II LabData tutorial fluorapatite; FAP.EXP is GSAS's converged "
        "fit and supplies both the reference values and the protocol",
        "cross_code"),
    "qarr": Dataset(
        "qarr",
        "IUCr CPD QPA round-robin patterns (samples 1a-1h, 2, 4 and six pure "
        "phases), Cu Ka doublet, graphite diffracted-beam monochromator",
        "absolute"),
    "srm660a_capillary": Dataset(
        "11BM_LaB6_660a.fxye",
        "APS 11-BM SRM 660a LaB6 in the beamline's documented 0.81 mm Kapton "
        "bore; lambda was calibrated against this very standard",
        "consistency"),
    "bethanechol": Dataset(
        "bethanechol_indexing.json",
        "Bergmann et al. (2004) Tables 5 and 6: ten sets of twenty 2theta "
        "positions for bethanechol chloride, the known P21/n cell, and every "
        "program's published score -- the only externally graded benchmark any "
        "feature in this package has",
        "cross_code"),
}


@dataclass(frozen=True)
class Claim:
    """One acceptance test and what it is entitled to claim."""

    module: str
    test: str
    dataset: str
    tiers: tuple[str, ...]
    claim: str
    #: what the bar is referenced to, in words.  Required unless the row's
    #: only tier is ``ceiling``.
    reference: str = ""
    #: frozen measured margin, so a row that quietly drifts toward its bar is
    #: visible in a diff even when the test still passes
    measured: str = ""
    #: how many independent starting points the quoted numbers survive.  1 is
    #: the honest default and is not a criticism; see START_DEPENDENCE below.
    starts: int = 1
    #: diagnostic codes the row asserts are present (or absent, "!" prefixed)
    diagnostics: tuple[str, ...] = field(default_factory=tuple)


CLAIMS: tuple[Claim, ...] = (
    # ---- SRM 660c: the absolute lab anchor -----------------------------
    Claim(
        "test_acceptance_srm660c", "test_srm660c_lab6_rietveld", "srm660c",
        ("certificate", "identity", "ceiling"),
        "the absolute lab cell anchor: a, the Berar-Lelann esd inflation, the "
        "held zero shift, the sample displacement and the Ka2 ratio",
        reference="NIST's cell recomputed for this dataset's 20.85 C block, "
                  "4.156780 A, under an explicitly interim +-2e-4 A band; the "
                  "certificate's own +-8e-6 at 22.5 C is NOT claimed and the "
                  "residual is a characterised cotTheta/sin2Theta aberration "
                  "(divergence, tube tails, monochromator passband) fenced to "
                  "the v2 FPA work",
        measured="a = 4.156895(25) A, +28 ppm; Rwp 8.66 %, GoF 1.87; "
                 "zero_shift held at exactly 0.0; displacement -0.0801 mm vs "
                 "the CIF's -0.07877",
    ),
    Claim(
        "test_acceptance_srm660c", "test_srm660c_extinction_does_no_harm",
        "srm660c", ("characterisation", "ceiling"),
        "secondary extinction freed on a specimen that has none refines to "
        "zero and does not move the anchor",
        reference="the cell must return to its own unextinguished value "
                  "within the same 2e-4 A band; the extinction parameter "
                  "itself is one-sided (< 1e-2 from a 1e-3 seed)",
        measured="extinction 2.075e-10 from a 1e-3 seed; Rwp 0.08661400134, "
                 "a 4.15689532166 — the warm-extend path is bit-equal",
    ),
    # ---- SRM 676a: certificate grade on the ratio only ------------------
    Claim(
        "test_acceptance_srm676a", "test_srm676a_corundum_cell_anchor",
        "srm676a", ("certificate", "characterisation", "identity", "ceiling"),
        "c/a at certificate grade, the absolute axes only at lab-realistic "
        "grade, and the difference between them asserted to be a uniform "
        "d-scale systematic rather than a structural error",
        reference="NIST SRM 676a certificate a = 4.759355(80), "
                  "c = 12.99231(15) A (k = 2, 22.5 C).  c/a's relative k=2 "
                  "uncertainty is ~21 ppm and the bar is 100 ppm — a small "
                  "multiple of it.  The absolute bar is 600 ppm, nowhere near "
                  "certificate grade, and the uniformity check "
                  "|da - dc| < 1.5e-4 is what stops an esd laundering a "
                  "many-sigma systematic",
        measured="c/a +30 ppm; absolute axes -313 / -283 ppm with |da - dc| "
                 "within 3e-5; Rwp 14.4 %, GoF 1.61 against a GoF floor of "
                 "1.5-1.9 for analytical-PSF lab fits (Cline 2015)",
    ),
    # ---- FAP: the one cross-code row ------------------------------------
    Claim(
        "test_acceptance_fap", "test_fap_lab_rietveld_matches_gsas", "fap",
        ("cross_code", "characterisation", "identity", "ceiling"),
        "agreement with GSAS-II's converged fit on the same channels under "
        "the same protocol, with the residual cell offset asserted to be a "
        "uniform d-scale convention difference",
        reference="GSAS's own FAP.EXP: Rwp 0.1005, Rp 0.0766, "
                  "a = 9.371724(36), c = 6.885867(37) A on 5750 channels "
                  "after its EXC 2 record.  Bars are rel=0.10 on the "
                  "R-factors and 300 ppm on the cell — a convention-aware "
                  "band, not 1e-4 A ground truth.  The esd window is "
                  "one-sided on purpose: ours carry Berar-Lelann inflation "
                  "and GSAS's do not",
        measured="Rwp 0.0973 vs 0.1005, Rp 0.0776 vs 0.0766, cell +116/+113 "
                 "ppm with the two agreeing inside 1e-4 (the uniformity "
                 "claim); channel count 5750 exactly",
    ),
    # ---- NAC: the synchrotron vertical slice ----------------------------
    Claim(
        "test_acceptance_nac", "test_nac_lebail_then_rietveld", "nac",
        ("own_result", "characterisation", "ceiling"),
        "Le Bail then two-phase Rietveld; the cell is checked much more "
        "tightly against our own Le Bail pass than against the literature, "
        "and the CaF2 impurity is found by the report rather than declared",
        reference="literature a = 10.2496-10.2506 A (high-accuracy powder) "
                  "and 10.257(1) (Courbion & Ferey 1988) under a 2e-3 A band "
                  "that allows for the beamline wavelength calibration; the "
                  "Rietveld-vs-Le Bail agreement is held to 5e-4 A",
        measured="a = 10.251285(12) A, Rwp 9.2 %; CaF2 lands at 5.4631 A",
    ),
    Claim(
        "test_acceptance_nac",
        "test_nac_extinction_on_the_main_phase_is_bounded_and_unbiasing",
        "nac", ("identity", "characterisation", "ceiling"),
        "extinction freed only on the well-determined phase stays bounded "
        "and does not bias the cell; the impurity's stays exactly zero",
        reference="the correction's own size (min E > 0.8, i.e. at most ~12 % "
                  "on the strongest line) and the unextinguished cell.  The "
                  "impurity extinction is exact-zero because it is never "
                  "freed — freeing it was measured to run away to E ~ 0.31",
        measured="min E > 0.8 on the main phase; phases[1].extinction == 0.0 "
                 "exactly",
    ),
    # ---- IUCr QPA round robin: the participant-spread rows ---------------
    Claim(
        "test_acceptance_qpa_roundrobin", "test_read_prn_two_column_ascii",
        "qarr", ("identity",),
        "the two-column .prn reader contract: grid, step, no esd column",
        reference="the files themselves — 7251 points from 5 to 150 deg at "
                  "0.02 deg, to 1 microdeg because cpd-1e truncates its "
                  "ordinates to seven characters; sigma is None so the "
                  "Poisson fallback is what weights these fits",
        measured="exact",
    ),
    Claim(
        "test_acceptance_qpa_roundrobin",
        "test_sample1_fractions_within_participant_spread", "qarr",
        ("spread", "identity", "ceiling"),
        "weight fractions on the eight sample-1 mixtures, and the closure of "
        "the fraction sum",
        reference="the weighed composition is truth; the tolerance is the "
                  "published participant spread (Madsen 2001 Fig. 2), 6.0 "
                  "wt % for majors and 2.0 for traces below 5 wt %.  Never "
                  "sigma(W): those esds are 0.1-0.4 wt %, an order of "
                  "magnitude below the measured errors",
        measured="worst 5.13 wt % (1f zincite), traces <= 1.3, RMS 2.26; "
                 "closure exact to 1e-6",
    ),
    Claim(
        "test_acceptance_qpa_roundrobin",
        "test_sample1_bias_has_the_dispersion_shape", "qarr",
        ("characterisation",),
        "the sample-1 residual bias is not noise: its sign is fixed per "
        "phase and its shape is the one neglected anomalous scattering "
        "predicts",
        reference="the per-phase Bragg-power ratios from f' at Cu Ka "
                  "(1.0542 corundum / 0.8441 zincite / 1.0728 fluorite), "
                  "which set the signs; WP-0502 separately excluded surface "
                  "roughness as the competing explanation, which is what "
                  "makes the attribution single-valued",
        measured="zincite mean < -1.0, corundum mean > +0.5, fluorite "
                 "|mean| < 2.0 wt %",
    ),
    Claim(
        "test_acceptance_qpa_roundrobin", "test_sample2_brucite_march_dollase",
        "qarr", ("spread", "characterisation", "identity", "ceiling"),
        "platy brucite is detected as preferred orientation rather than "
        "absorbed into the fractions",
        reference="participant spread again on the fractions; the March "
                  "coefficient is judged as physics (r < 1 means platy, and "
                  "0.4 < r < 0.9 is far enough from the r = 1 identity to be "
                  "a detection rather than a fitted nothing)",
        measured="r ~ 0.68; worst fraction 2.9 wt %; H Biso held at exactly "
                 "2.5",
    ),
    Claim(
        "test_acceptance_qpa_roundrobin",
        "test_sample4_microabsorption_characterised_not_hidden", "qarr",
        ("characterisation", "ceiling"),
        "the round robin's designed Brindley-defeating sample fails in the "
        "documented direction, the muR fence fires, and the correction moves "
        "two of three phases the right way",
        reference="**no accuracy band is claimed** — this specimen is meant "
                  "to defeat the correction.  What is asserted is the sign "
                  "and rough size of each error, that BRINDLEY_OUTSIDE_REGIME "
                  "names magnetite, and that tau < 1 < tau holds across the "
                  "absorption contrast.  Zircon is deliberately NOT asserted "
                  "to improve (measured -9.2 to -9.4)",
        measured="corundum +24, zircon -15, magnetite -9 wt %",
        diagnostics=("BRINDLEY_OUTSIDE_REGIME",),
    ),
    # ---- dispersion: the pre-registered prediction -----------------------
    Claim(
        "test_acceptance_dispersion",
        "test_sample1_fractions_beat_the_dispersion_free_fit", "qarr",
        ("prediction", "spread", "identity", "ceiling"),
        "with f' and f'' applied, every sample-1 mixture meets a tolerance "
        "the dispersion-free fit could not",
        reference="the weighed composition at 2.5 wt %, tightened from the "
                  "participant spread's 6.0/2.0 — the tightening IS the "
                  "claim, and it was written down before the refits",
        measured="worst 1.39 wt % (was 5.13)",
    ),
    Claim(
        "test_acceptance_dispersion",
        "test_the_microabsorption_shape_was_mostly_dispersion", "qarr",
        ("prediction", "own_result"),
        "the signed bias v0.3 attributed to microabsorption collapses when "
        "dispersion is applied — a v0.3 conclusion re-derived, not merely a "
        "number improved",
        reference="the frozen V03_ERRORS table (the eight measured signed "
                  "wt % errors from milestones/v0.3.md), phase by phase.  The "
                  "prediction was parameter-free and beat itself: predicted "
                  "RMS 0.83, measured 0.69",
        measured="RMS 2.26 -> 0.69 wt %; zincite's -1 wt % mean bias goes to "
                 "|mean| < 1.0",
    ),
    Claim(
        "test_acceptance_dispersion", "test_zincite_cell_does_not_move",
        "qarr", ("identity",),
        "dispersion is an intensity correction and must not move a "
        "non-centrosymmetric structure's cell",
        reference="the same fit with the block off; 1e-5 A on a and c",
        measured="within 1e-5 A",
    ),
    Claim(
        "test_acceptance_dispersion",
        "test_zincite_oxygen_adp_becomes_physical", "qarr",
        ("characterisation",),
        "the sharpest single dispersion result: B(O) comes off its floor "
        "once Zn's missing f' stops being absorbed by a displacement "
        "parameter, while Rwp barely moves",
        reference="physical plausibility, not a reference value — B(O) below "
                  "0.1 A^2 is a parameter pinned on a bound, and 0.2-1.2 is "
                  "the range an oxide oxygen actually occupies.  Rwp is "
                  "asserted only one-sided, because this is exactly a case "
                  "where the fit statistic does not see the fix",
        measured="B(O) 0.022 -> 0.429 A^2",
    ),
    Claim(
        "test_acceptance_dispersion",
        "test_srm660c_lattice_parameter_is_untouched", "srm660c",
        ("identity",),
        "the absolute anchor survives the flip: a does not move when "
        "dispersion is applied",
        reference="the dispersion-off baseline, at 2e-6 A — well inside the "
                  "25e-6 A esd, so the anchor is safe either way",
        measured="a = 4.156895 A both ways",
    ),
    Claim(
        "test_acceptance_dispersion",
        "test_srm660c_displacement_parameters_absorb_the_change", "srm660c",
        ("characterisation",),
        "where the change lands instead: the displacement parameters, by "
        "12 % and 22 %",
        reference="the dispersion-off baseline; floors on the size of the "
                  "move (>0.02 and >0.05 A^2) plus a physical band on the "
                  "result, which is a characterisation and not an accuracy "
                  "claim — no certified Biso exists for this specimen",
        measured="B(La) and B(B) move ~12 % / ~22 %; Rwp 8.661 -> 8.640 %",
    ),
    Claim(
        "test_acceptance_dispersion",
        "test_the_neglect_diagnostic_clears_when_the_block_is_on", "srm660c",
        ("identity",),
        "'off' is loud: the neglect diagnostic is present dispersion-off and "
        "absent dispersion-on",
        reference="the diagnostic set itself — set membership, both "
                  "directions",
        measured="exact",
        diagnostics=("DISPERSION_NEGLECTED", "!DISPERSION_NEGLECTED"),
    ),
    # ---- capillary absorption: the identity tier -------------------------
    Claim(
        "test_acceptance_capillary",
        "test_estimated_mu_r_matches_the_documented_capillary",
        "srm660a_capillary", ("characterisation", "identity"),
        "muR from composition and the documented bore lands in the physically "
        "plausible band, and the public estimator agrees with what the "
        "refinement resolved internally",
        reference="the beamline's documented 0.81 mm Kapton bore and a "
                  "packing fraction of 0.35-0.6, which spans muR 0.47-0.81; "
                  "the estimator/resolver agreement is floating-point "
                  "(rel=1e-9)",
        measured="muR 0.674, method rouse_cylinder, not out of range",
    ),
    Claim(
        "test_acceptance_capillary",
        "test_capillary_absorption_is_an_exact_reparameterisation",
        "srm660a_capillary", ("prediction", "identity"),
        "the headline: applying the correction provably cannot change the "
        "fit, and the whole of its content is a predicted shift in every "
        "Biso",
        reference="the analytic prediction DeltaB = c(muR)*lambda^2/2, "
                  "computed before the refits.  Rwp and the cell are held to "
                  "1e-6 and 1e-9 A **between two of our own fits** — "
                  "referenced to floating point, not to any external value, "
                  "because Rouse's expression factors exactly into a "
                  "Debye-Waller shape",
        measured="Delta Rwp 3.2e-8, Delta a -7.9e-12 A, every Biso +0.0166542 "
                 "against a predicted 0.0166542",
    ),
    Claim(
        "test_acceptance_capillary", "test_fit_quality_and_the_circular_cell",
        "srm660a_capillary", ("characterisation", "ceiling"),
        "the fit is sound and its cell agrees with SRM 660a — recorded as "
        "consistency, explicitly NOT as an anchor",
        reference="**circular by construction**: 11-BM calibrated lambda "
                  "against LaB6 itself (the file's own calibration header), "
                  "so this cell reproduces the standard whatever the code "
                  "does.  The 1e-4 relative band is a divergence guard, "
                  "deliberately generous",
        measured="16 ppm from the SRM 660a certificate; Rwp 8.85 %",
    ),
    Claim(
        "test_acceptance_capillary",
        "test_the_absorption_shift_is_independent_of_dispersion",
        "srm660a_capillary", ("prediction", "identity", "characterisation"),
        "the absorption identity still holds on a dispersion-on model, and "
        "the two corrections are separable in size and sign",
        reference="the same analytic DeltaB prediction, re-measured on top of "
                  "dispersion; plus a sign/magnitude cross-check that "
                  "dispersion moves B(La) the other way and 2.6x further",
        measured="Delta B still 0.0166542 to 1e-5; dispersion moves B(La) by "
                 "about -0.044 A^2",
    ),
    # ---- sequential: own-result comparisons ------------------------------
    Claim(
        "test_acceptance_sequential", "test_chained_qpa_within_participant_spread",
        "qarr", ("spread", "identity"),
        "a warm-started chain meets the unchained suite's criterion, "
        "unchanged",
        reference="the QPA suite's own MAJOR_TOL/TRACE_TOL, imported rather "
                  "than restated, so what differs between the two suites is "
                  "only the chaining",
        measured="identical to the independent fits' record",
    ),
    Claim(
        "test_acceptance_sequential", "test_chained_agrees_with_independent_fits",
        "qarr", ("own_result",),
        "chaining changes the starting point, not the answer",
        reference="this package's own independent fits under the same "
                  "protocol, at 1 wt % and 0.005 in Rwp — generous rather "
                  "than tight, and framed in participant-spread units "
                  "because that is what the quantity means",
        measured="mean Rwp 0.1278 either way; QPA identical to the v0.3 "
                 "record",
    ),
    Claim(
        "test_acceptance_sequential", "test_cells_are_stable_across_the_series",
        "qarr", ("characterisation",),
        "a trajectory that should be flat is flat: no trend imprinted by the "
        "chaining order",
        reference="the trajectory's own spread — a slope is only a finding "
                  "if it exceeds the scatter it is drawn from.  This is the "
                  "shape check that separates a measured trajectory from an "
                  "ordering artefact",
        measured="per-phase spread < 20e-4 A with no monotone drift",
    ),
    Claim(
        "test_acceptance_sequential", "test_warm_start_iteration_cost_is_reported",
        "qarr", ("characterisation", "ceiling"),
        "the headline iteration saving is printed and only divergence is "
        "gated — the number is a finding, not a bar",
        reference="**deliberately not asserted.** 2863 iterations unchained, "
                  "1623 re-walking the staged plan warm, 904 with the plan "
                  "collapsed; the carry-glob hypothesis was refuted at 838. "
                  "Gating a speed number would turn machine noise into a "
                  "test failure",
        measured="904 vs 2863 iterations at identical mean Rwp",
    ),
    Claim(
        "test_acceptance_sequential",
        "test_the_hostile_series_exercises_the_reseed_fence", "qarr",
        ("identity", "characterisation"),
        "the reseed fence's accounting is exact, and a reseed never leaves "
        "the fit worse than the warm start it rejected",
        reference="internal consistency: the SEQUENTIAL_RESEED diagnostic "
                  "count must equal the number of entries flagged reseeded, "
                  "exactly.  The fence never fired on the hostile series — "
                  "the collapsed refit recovers a bad warm start within the "
                  "fit — so it is insurance, pinned by unit tests rather "
                  "than by this suite",
        measured="exact accounting; zero reseeds on the hostile series",
        diagnostics=("SEQUENTIAL_RESEED",),
    ),
    Claim(
        "test_acceptance_sequential", "test_series_exports", "qarr",
        ("identity",),
        "the series CSV and trajectory plot exist with the declared columns "
        "and one row per pattern",
        reference="the export contract itself",
        measured="exact",
    ),
    # ---- Stephens: inadmissibility, and the start-dependence axis --------
    Claim(
        "test_acceptance_stephens",
        "test_brucite_improvement_is_justified_but_leaves_the_physical_cone",
        "qarr", ("characterisation",),
        "an Rwp improvement that both statistical tests bless is rejected by "
        "a physics guard, on real data — the matrix's canonical "
        "inadmissibility row",
        reference="**no accuracy claim.** Hamilton at alpha = 0.05 and "
                  "Delta BIC > 100 both pass; the strain-variance cone "
                  "sigma^2(M) >= 0 fails on 12 of 43 reflections, so "
                  "STEPHENS_STRAIN_NOT_POSITIVE fires and no S_HKL is "
                  "quotable.  The r ~ 0.65 March coefficient is checked "
                  "against WP-0310's own measurement on the same material",
        measured="Rwp 18.55 -> 17.90 %, Delta BIC +488, 3 parameters added, "
                 "anisotropy 3.45x on an injected 3.46x",
        starts=4,
        diagnostics=("STEPHENS_STRAIN_NOT_POSITIVE",),
    ),
    Claim(
        "test_acceptance_stephens", "test_corundum_is_reported_isotropic",
        "qarr", ("characterisation", "ceiling"),
        "the control: an isotropic specimen must be reported isotropic, and "
        "must never leave the cone",
        reference="the Layer-1 strain diagnostic's own thresholds "
                  "(not detected, R^2 < 0.5, anisotropy < 2.0) plus the "
                  "derived pattern count for R-3c",
        measured="anisotropy 1.60x, 4 patterns, > 40 reflections; never "
                 "leaves the cone at any seed",
    ),
    Claim(
        "test_acceptance_stephens",
        "test_corundum_block_is_inert_and_bic_says_so_where_hamilton_does_not",
        "qarr", ("characterisation", "identity"),
        "freeing the block on an isotropic specimen is inert, and the two "
        "statistics disagree about whether that is fine — which is why the "
        "policy quotes Delta BIC and not Hamilton",
        reference="Hamilton's R-ratio test at alpha = 0.05 **passes** a "
                  "0.13 % chi^2 improvement from three inert parameters, "
                  "exactly as it passes brucite's real 6.9 % one: its "
                  "threshold does not grow with the channel count, and these "
                  "patterns have 7251 channels.  Delta BIC separates them "
                  "(+488 vs -17).  The certificate-grade c/a is asserted not "
                  "to move (rel=1e-4)",
        measured="Delta BIC -17 while Hamilton says justified; c/a unmoved",
    ),
    Claim(
        "test_acceptance_stephens",
        "test_constrained_solver_keeps_brucite_inside_the_cone", "qarr",
        ("characterisation",),
        "under solver='lm' the cone is carried as a linear inequality and "
        "brucite comes back inside it — at a higher Rwp, which is the point",
        reference="the physics constraint itself: sigma^2(M) > 0 on all 43 "
                  "reflections, with the optimum sitting on the cone face.  "
                  "Rwp is bounded loosely and is expected to be WORSE than "
                  "the unconstrained fit's",
        measured="0 of 43 violations; Rwp 0.18417 against TRF's 0.17899",
        starts=4,
    ),
    Claim(
        "test_acceptance_stephens",
        "test_unconstrained_solver_leaves_the_cone_on_the_same_data", "qarr",
        ("characterisation",),
        "the control for the row above: the default TRF driver, same data, "
        "leaves the cone",
        reference="the same cone test, opposite direction — at least 10 of "
                  "43 reflections violating, plus the guard diagnostic",
        measured="12 of 43 violations at the pinned seed; 15/12/0/0 across "
                 "the four-seed sweep, which is why that row carries "
                 "starts=4",
        starts=4,
        diagnostics=("STEPHENS_STRAIN_NOT_POSITIVE",),
    ),
    # ---- WP-1026: indexing, the first externally graded feature ----------
    # Four rows verify the transcription itself.  Two hundred numbers were typed
    # from a printed table, and each of these checks a statement the paper makes
    # in PROSE and never tabulates, so a typo breaks at least one of them.
    Claim(
        "test_acceptance_indexing", "test_every_set_is_twenty_ascending_lines",
        "bethanechol", ("identity",),
        "the fixture has the shape the paper's Table 6 has: ten sets, twenty "
        "strictly ascending positions each",
        reference="Table 6's ten columns -- A/B/C/D are treatments and each was "
                  "applied to BOTH ICDD entries, which is why the global score "
                  "runs over twenty numbers and not ten",
        measured="10 sets x 20 lines, all ascending",
    ),
    Claim(
        "test_acceptance_indexing",
        "test_table_5_reconstruction_sums_to_the_published_globals",
        "bethanechol", ("identity", "cross_code"),
        "the transcribed per-program scores sum to the Global column the paper "
        "prints beside them, which is what makes the bar itself trustworthy",
        reference="Table 5 is a 20-column grid of +-1 with subscripted zeros and "
                  "does not survive conversion intact -- the copy this was read "
                  "from had a row of 21 values where there are 20.  Each graded "
                  "row's twenty independently-read cells must reproduce its "
                  "printed total",
        measured="First 4 sums to +9 and Best of all to +12, both exact; the "
                 "four programs the +9 is the best of scored -14, -8, -4 and +5 "
                 "individually",
    ),
    Claim(
        "test_acceptance_indexing",
        "test_the_zeroshift_correction_is_exactly_the_paper_s",
        "bethanechol", ("identity", "cross_code"),
        "the zero-corrected columns are exactly the raw ones less the paper's "
        "stated zeropoint",
        reference="the text says only that the entries carry 'a surprisingly "
                  "large zeropoint error that is close to 0.10 (2theta) deg' "
                  "and prints both columns; the arithmetic linking them is "
                  "never stated, and eighty values have to agree",
        measured="C = A - 0.100 and D = B - 0.100 to 5e-13 on all four pairs",
    ),
    Claim(
        "test_acceptance_indexing",
        "test_the_intensity_cut_is_a_subset_of_the_same_measurement",
        "bethanechol", ("identity", "cross_code"),
        "the I >= 5 % sets are subsets of the raw sets of the same specimen, "
        "and reach further in 2theta for the stated reason",
        reference="B is 'the first 20 lines with I >= 5 % I_max' of the same "
                  "pattern as A, so every B line inside A's range must be one "
                  "of A's bit-for-bit -- and dropping the weak lines is what "
                  "lets twenty survivors extend past A's last line",
        measured="13 of 13 and 15 of 15 common lines identical to 1e-12; both "
                 "B sets reach beyond their A set's maximum",
    ),
    Claim(
        "test_acceptance_indexing",
        "test_the_published_cell_reproduces_the_paper_s_impurity_counts",
        "bethanechol", ("cross_code", "characterisation"),
        "the published cell accounts for exactly as many of each entry's first "
        "twenty lines as the paper's own impurity statement implies",
        reference="'8 impurity lines among the first 26 lines' in PDF 43-1748 "
                  "and '3 impurity lines among the first 35' in 46-1964.  "
                  "Nothing is fitted: the cell is the paper's and the offset is "
                  "a one-parameter scan, so this uses the ANSWER to check the "
                  "data and no typo in either survives it",
        measured="3 unexplained of 20 in every 46-1964 set, 7 in 43-1748, 0 in "
                 "both new measurements",
    ),
    Claim(
        "test_acceptance_indexing",
        "test_a_bare_position_list_says_its_sigma_was_assumed",
        "bethanechol", ("characterisation",),
        "the benchmark's input form is carried honestly: every line says its "
        "sigma was assumed, and the quality gate lets it through anyway",
        reference="the sets are positions only, so sigma is "
                  "PEAK_ASSUMED_ESD_DEG -- chosen by this package.  A precision "
                  "nobody measured may not be grounds for refusing to index, "
                  "which is the inverse of the mistake indexing/quality.py "
                  "exists to prevent.  All ten sets failed the sigma(Q)/Q "
                  "abstention before WP-1026, including the one whose published "
                  "M(20) is 197",
        measured="source == 'positions' and sigma_assumed on every line of all "
                 "ten sets; supports_indexing True on all ten; shift.source "
                 "'unavailable'",
    ),
    Claim(
        "test_acceptance_indexing",
        "test_published_figures_of_merit_are_reproduced_unfloored",
        "bethanechol", ("cross_code", "characterisation"),
        "the published M(20) and F(20) are reproduced from the transcription "
        "with the de Wolff / Smith-Snyder definitions, and are shown NOT to be "
        "reproducible from this package's own floored versions",
        reference="M(20) = 197 and F(20) = 1080 (0.0006, 32) on the "
                  "synchrotron set.  m20/f_n floor <delta> at the median sigma, "
                  "which on a from_positions list is the ASSUMED 0.02 deg -- "
                  "thirty times the paper's <|d2theta|> -- so the floored "
                  "figures are not comparable with a published value computed "
                  "without the floor, and the row says so rather than quietly "
                  "comparing them",
        measured="unfloored M = 116, F = 654 with <|d2theta|> = 0.00099 deg "
                 "and N_poss = 31 against the published 0.0006 and 32; the "
                 "residual gap is the printed cell's own rounding (3 dp on the "
                 "axes, 2 on beta).  Floored, the same data give 5.8 and 32.3",
    ),
    Claim(
        "test_acceptance_indexing",
        "test_the_2004_zeroshift_hypothesis_cannot_be_tested_on_these_data",
        "bethanechol", ("characterisation", "prediction"),
        "the paper's own hypothesis about the cause of the zeroshift is tested "
        "for the first time and comes back UNANSWERABLE, with the reason "
        "quantified -- and the magnitude it does determine disagrees with the "
        "paper's round number",
        reference="Bergmann et al. wrote the shift 'would be consistent with a "
                  "systematic specimen-displacement error' and had no way to "
                  "check, every program of the day fitting one constant "
                  "zeropoint.  fit_shift_model fits three physical causes as "
                  "nested single fits.  The prediction written down before the "
                  "measurement is quality.py's: over a short low-angle range "
                  "the templates are collinear and no cause is attributable",
        measured="max_collinearity 1.0000 and separable=False on all ten sets "
                 "over their 6-31 deg span.  Magnitude: PDF 43-1748 carries "
                 "+0.062 deg and 46-1964 +0.058, not the quoted 0.10 -- so "
                 "subtracting 0.100 overshoots to -0.039 and -0.043, which is "
                 "why Table 5 does not show C as uniformly easier than A",
    ),
    Claim(
        "test_acceptance_indexing",
        "test_a_certified_lab_pattern_indexes_and_is_graded_honestly",
        "srm676a", ("certificate", "characterisation"),
        "a raw certified pattern is picked and indexed end to end, the "
        "certified lattice is ranked first with the right centring, and the "
        "gate still refuses to promote it -- naming four reasons, all real",
        reference="NIST SRM 676a a = 4.759355(80), c = 12.99231(15) A (k = 2). "
                  "Both axes are asserted at 150 ppm.  An earlier version of "
                  "this row asserted c as a RANGE of 1000-5000 ppm and called "
                  "it 'what an uncalibrated lab pattern costs'; it was not, it "
                  "was dichotomy's duplicate-leaf hash skipping the leaf that "
                  "held the certificate's c (WP-1026, _box_key)",
        measured="ranked first, trigonal R, a +101 ppm and c +16 ppm, 49 of 55 "
                  "lines, chi2_red 0.84.  Confidence low on four caveats: "
                  "engines_disagree, predicted_but_absent (12 -- the R-3c "
                  "c-glide, not an oversized cell), indexed_fraction_low "
                  "(49/55 = 0.891 against a 0.9 bar) and "
                  "shift_allowance_assumed.  best_or_none() returns None",
        diagnostics=("INDEX_SHIFT_ALLOWANCE",),
    ),
    Claim(
        "test_acceptance_indexing",
        "test_declaring_the_shift_template_is_what_recovers_the_certificate",
        "srm676a", ("certificate", "characterisation"),
        "declaring a shift template recovers a specimen displacement the "
        "package was never told about, and moves the cell to the certificate "
        "while it does so",
        reference="The displacement was measured independently against the "
                  "certificate as a -0.065 deg cos(theta) term (WP-1023).  "
                  "This row never supplies it: the search fits the template "
                  "after each candidate survives, from the pattern alone.  The "
                  "cell and the figures of merit are asserted TOGETHER, "
                  "because f_n's stated blind spot is that a refined shift can "
                  "manufacture a large figure of merit on its own",
        measured="fitted shift -0.0606 +/- 0.0138 deg; a -73 ppm, c -126 ppm; "
                  "M20 22.1 -> 76.6 and F_N 15.8 -> 59.5; indexed_fraction "
                  "0.891 -> 0.927 so indexed_fraction_low clears.  Still low, "
                  "because the allowance was assumed either way",
        diagnostics=("INDEX_SHIFT_ALLOWANCE",),
    ),
    Claim(
        "test_acceptance_indexing", "test_the_phantom_lines_are_what_had_blocked_it",
        "srm676a", ("characterisation",),
        "the peak list this package produces from a real lab pattern contains "
        "components that are profile-shape repair rather than lines, and they "
        "are flagged rather than reported",
        reference="detect_peaks proposes 41 groups with ONE seed each; the "
                  "fitter returns 63 components.  The row asserts the flagged "
                  "ones are weak satellites of much stronger lines -- the "
                  "geometry no dBIC can refuse, because dBIC judges two models "
                  "that both fail (chi2_red 17.4 at n=1, 4.6 at n=2)",
        measured="8 of 63 flagged not_separable, >=50 usable; before the fix "
                  "neither engine could index this certified pattern at all",
    ),
    Claim(
        "test_acceptance_indexing", "test_a_three_phase_mixture_abstains",
        "qarr", ("characterisation",),
        "a three-phase mixture returns no cell rather than the best of a bad "
        "list, and reports which systems were searched instead of concluding "
        "about the specimen",
        reference="qarr/cpd-1a.prn is corundum + zincite + fluorite.  The "
                  "failure this guards against is the one the prior art at the "
                  "guillemot-study tag retracted a claim over: a coverage "
                  "score cannot tell a multiphase pattern from a single-phase "
                  "one of lower symmetry",
        measured="best_or_none() is None; no candidate reaches high",
    ),
    # ---- SRM 660c indexed: the absolute anchor, and the phase with no
    # extinctions that turns the corundum caveat into a control ------------
    Claim(
        "test_acceptance_indexing",
        "test_a_certified_cubic_cell_is_recovered_with_no_extinction_caveat",
        "srm660c", ("certificate", "characterisation"),
        "the absolute lab anchor is indexed from the pattern alone, and the "
        "refuting caveat that fires on correct cells is silent on the one "
        "bundled phase whose space group has no absences",
        reference="P m -3 m extinguishes nothing, so if predicted_but_absent "
                  "means what WP-1026 read it to mean -- space-group "
                  "extinctions counted against the LATTICE group, the only "
                  "model that exists before determine_extinction_symbol runs "
                  "-- it must be silent here and is 11-12 on R-3c corundum.  "
                  "The cell bar is 200 ppm and is set by a defect this same "
                  "file measures, not by the data: a tighter one would assert "
                  "the tail components below do not exist",
        measured="cubic P ranked first, a -127 ppm against the CIF's "
                 "4.156780 A; predicted_but_absent 0 of 30 and "
                 "predicted_seen_fraction 1.000 against corundum's 0.86.  "
                 "Still low, on shift_allowance_assumed and engines_disagree; "
                 "best_or_none() returns None",
        diagnostics=("INDEX_SHIFT_ALLOWANCE",),
    ),
    Claim(
        "test_acceptance_indexing",
        "test_the_unflagged_tail_components_escape_for_three_different_reasons",
        "srm660c", ("characterisation",),
        "the not_separable screen misses six components on this pattern, and "
        "the census -- not any one threshold -- is what is pinned",
        reference="The screen asks three questions (re-seeded, inside the "
                  "neighbour's profile at <=25 % of its area, group still "
                  "refuted).  Thirteen components face them here; the six "
                  "survivors fail three DIFFERENT conditions, so widening "
                  "PEAK_SATELLITE_NEAR_FWHM would reach four of six and be a "
                  "knob rather than a measurement",
        measured="4 too far (1.73-2.99 FWHM), 1 not re-seeded (the detection "
                 "seed slid into the tail and the new component took the real "
                 "line), 1 on a group whose fit is not refuted (chi2_red 1.38)",
    ),
    Claim(
        "test_acceptance_indexing",
        "test_the_surviving_components_sit_on_the_axial_divergence_side",
        "srm660c", ("characterisation",),
        "the surviving components are aberration shape rather than lines, and "
        "the side they sit on names which aberration",
        reference="Axial divergence puts a tail on the low-2theta side below "
                  "90 deg and the high side above it; nothing else in a "
                  "Bragg-Brentano pattern changes sign there.  The single "
                  "exception is asserted to be exactly one and to sit on its "
                  "group-mate's Kalpha2 maximum -- an alias the detection "
                  "screen drops (PEAK_KALPHA2_ALIAS, 23 dropped) and the group "
                  "fit re-creates at 3 % of the parent's area",
        measured="5 axial-divergence tails, 1 Kalpha2 residual, 0 lines of "
                 "LaB6; the sign flips at 90 deg on every one of them",
        diagnostics=("PEAK_KALPHA2_ALIAS",),
    ),
    Claim(
        "test_acceptance_indexing",
        "test_the_shift_screen_survives_the_tail_components_but_the_search_cannot",
        "srm660c", ("certificate", "characterisation"),
        "an assumed matching allowance costs the relative weighting the peak "
        "fitter measured, which is why declaring a shift template recovers "
        "corundum's certificate and not this one's",
        reference="The displacement is PREDICTED, parameter-free, from NIST's "
                  "own recorded -0.07877 mm at R = 217.5 mm through "
                  "model.corrections.displacement_shift_deg: +0.0415 deg cos "
                  "theta.  fit_shift_model weights by each line's own sigma; "
                  "the search adds DEFAULT_UNKNOWN_SHIFT_DEG = 0.05 deg in "
                  "quadrature to every sigma, which is flat",
        measured="tail components carry sigma ~0.005 deg against the real "
                 "lines' ~0.0005; after the quadrature allowance that 100x "
                 "contrast is 1.005.  Screen: +0.0367 +- 0.0015 (0.88 of the "
                 "predicted 0.0415, the rest being the aberrations SRM 660c's "
                 "own docstring names).  Search: +0.009 +- 0.016, consistent "
                 "with none",
    ),
    Claim(
        "test_acceptance_indexing",
        "test_positions_alone_cannot_separate_lab6_from_a_half_volume_rival",
        "srm660c", ("identity", "characterisation"),
        "a geometrical ambiguity that is exact rather than approximate, and "
        "that the derivative-lattice enumeration cannot reach from one side",
        reference="Tetragonal P at (a/sqrt2, a) gives Q = (2h2+2k2+l2)/a2, and "
                  "2(h2+k2)+l2 represents exactly the integers h2+k2+l2 does "
                  "-- both miss precisely 4^n(8m+7).  So the two lattices are "
                  "isospectral everywhere, not within a tolerance.  "
                  "ambiguity_partners enumerates SUBlattices of index 2-4, "
                  "i.e. supercells, and this rival has half the volume",
        measured="represented sets identical to N=400; predicted Q identical "
                 "to 3e-16 relative (the round-off of sqrt2, not a "
                 "difference).  0 partners from the cubic side; from the "
                 "tetragonal side the cubic is found at index 2 with ZERO "
                 "discriminating reflections",
    ),
    Claim(
        "test_acceptance_indexing",
        "test_the_isospectral_rival_is_ranked_beside_the_truth",
        "srm660c", ("characterisation",),
        "both engines find the isospectral rival on the measured pattern, and "
        "neither it nor the truth carries the caveat that should hold the pair",
        reference="The WP's 'a geometrical-ambiguity case where NEITHER "
                  "partner reaches high' row, answered on certified data "
                  "rather than synthetically -- and a stronger case, because "
                  "this partner is exactly isospectral rather than isospectral "
                  "within a tolerance.  Nothing is promoted here for an "
                  "unrelated reason (the allowance was assumed), so what is "
                  "pinned is the missing geometric_ambiguity caveat",
        measured="the half-volume tetragonal cell is ranked in the same list, "
                 "found_by both engines; neither partner reaches high and "
                 "neither carries geometric_ambiguity",
    ),
    Claim(
        "test_acceptance_indexing",
        "test_what_the_unflagged_tail_components_cost_the_certified_cell",
        "srm660c", ("certificate", "characterisation"),
        "with every piece of evidence supplied the gate reaches high for the "
        "first time on real data, and the cell lands 2 ppm from a certified "
        "value",
        reference="An attribution probe, not a protocol: the off-lattice "
                  "components are identified USING the certificate, which no "
                  "user of an unknown phase can do.  What it establishes is "
                  "that the pipeline's arithmetic is sound to the ppm and that "
                  "what stands between it and a blind certified answer is a "
                  "peak list.  Three things are supplied -- the five "
                  "off-lattice components removed, the systematic measured "
                  "rather than assumed, the cos_theta template declared",
        measured="a = 4.156772 A, -2 ppm, M20 1113, ZERO caveats, confidence "
                 "high and best_or_none() non-None -- both firsts on real "
                 "data, against -127 ppm with none of the three.  Also "
                 "measured: declaring the screen's own sigma_sys (0.0078, the "
                 "residual the template LEAVES) returns no candidate at all, "
                 "because the search matches uncorrected positions and needs "
                 "the shift's amplitude (0.037) instead -- 4.3x apart",
        diagnostics=("!INDEX_SHIFT_ALLOWANCE",),
    ),
)


#: **How many starts a quoted number has to survive.**  WP-0601 measured the
#: reason this is a validation axis and not a solver detail: sweeping
#: ``Stage.strain_seed`` over 400/800/1600/3000 on round-robin brucite leaves
#: the Stephens coefficients spanning ~100 % relative spread under *both*
#: drivers, and moves the unconstrained fit in and out of the physical cone
#: (15, 12, 0, 0 reflections violating).  A single-start acceptance number
#: would have called that specimen either fine or broken depending on which
#: seed the suite happened to pin.
#:
#: The rule, in three parts:
#:
#: 1. A **cell parameter, weight fraction or scale** may be quoted from one
#:    start.  These are well-conditioned and the staged plan reaches the same
#:    basin from any sane starting model; every ``certificate``,
#:    ``cross_code`` and ``spread`` row in this matrix is single-start and
#:    that is not a weakness.
#: 2. A **width or shape parameter that enters through a square root, a cone,
#:    or a softplus floor** must survive a documented sweep before any number
#:    is quoted from it — that is the class where the objective is flat or
#:    non-convex near the start.  The Stephens rows carry ``starts=4``.
#: 3. When a sweep is run and the parameters move but the **conclusion** does
#:    not, the conclusion is what gets recorded, and the sweep goes in the
#:    docstring rather than into an assertion.  Pinning a per-seed number
#:    would convert a known instability into a flaky test.
START_DEPENDENCE_RULE = 3


#: **The one default WP-1001 was chartered to decide, and how it went.**
#: WP-0504 shipped anomalous scattering opt-in so that landing it did not
#: invalidate the record, and left a note that turning it on was "the right
#: default for v1.0".  Measured before flipping, not assumed:
#:
#: * *For.* It is the only correction in the package that needs **no
#:   information the caller does not already have** — capillary absorption
#:   wants µR, roughness a surface, Stephens a strain model, March-Dollase a
#:   habit; dispersion wants the species and the wavelength, both already in
#:   the model.  Neglecting it costs RMS 2.26 → 0.69 wt % on round-robin QPA.
#: * *Anchors survive.*  SRM 660c's cell does not move (4.156895 Å either
#:   way).  SRM 676a's certificate-grade c/a moves +29.8 → +30.2 ppm against a
#:   100 ppm bar — measured for this WP, since WP-0504 never checked it.
#: * *And Rwp gets **worse*** on corundum, 14.374 → 14.531 %, while the
#:   physics gets better.  The v0.5 method result once more, now at the level
#:   of a package default.
#: * *Against, measured.*  A wavelength inside an absorption-edge interval
#:   **raises** instead of degrading: 12 of 1176 (element × shipped anode)
#:   combinations, including Eu and Ho at Cu Kα, and 0.0-1.2 % of arbitrary
#:   synchrotron wavelengths depending on the specimen.  Raising is kept
#:   deliberately — a selective fallback would leave some species corrected
#:   and others not, manufacturing exactly the unequal cross-phase bias the
#:   correction exists to remove, which is *worse* than uniformly declining.
#:   ``dispersion = None`` is the one-line escape and the message names it.
#:
#: Decision: **flipped**.  The cost of absorbing it was 21 tests, and the
#: shape of that cost is the lasting lesson — nine of them were bit-identity
#: goldens that had no opinion about dispersion at all, they simply inherited
#: it.  Every one is now explicit (and every golden is bit-identical again,
#: which is the evidence the flip touched physics and not plumbing).  Two
#: knock-on effects are recorded rather than tuned away: light-atom ADPs come
#: back less *precise* even as they come back less *biased* (rutile U11/U33
#: separate at 1.9σ with the block on, 2.2σ without, because f″ raises the
#: heavy atom's share of every reflection), and the calibrate→freeze→refine
#: size/strain split degrades from 27 % low to 39 % low — a bar that was
#: already marginal on a degenerate direction.
DISPERSION_DEFAULT_ON = True

#: Gaps this matrix records rather than hides.  A validation matrix that only
#: lists what passed is marketing; these are the holes a reader should know
#: about before trusting a number, each with what would close it.
GAPS: tuple[tuple[str, str], ...] = (
    ("Every acceptance number in the repo is a Cu Ka measurement.",
     "Six anodes ship (Cr/Fe/Co/Cu/Mo/Ag plus Ka1-only variants) and what is "
     "validated for the other five is the wavelength table and its checks, "
     "not a refinement.  The cheapest close is one Co Ka pattern from an "
     "Fe-bearing specimen — the routine real case, since Cu Ka fluoresces Fe "
     "(mu/rho 297.7 vs 56.2) — which would exercise dispersion, absorption "
     "and the per-anode K-beta contamination check at once."),
    ("No dataset here can constrain a low-angle intensity correction.",
     "The qarr phases first reflect at 25.6/28.3/31.8 deg and SRM 660c at "
     "21.4, so surface roughness (WP-0502) has a negative acceptance result "
     "only: two of three phases collapse to the identity and raise "
     "ROUGHNESS_UNCONSTRAINED.  Closing it needs a pattern starting below "
     "~15 deg with real low-angle reflections."),
    ("The SRM 660c certificate band is not reached and is not claimed.",
     "Measured +28 ppm against a certificate uncertainty of +-8e-6 A.  The "
     "residual is a characterised cotTheta/sin2Theta aberration — equatorial "
     "divergence, tube tails, monochromator passband — which is the "
     "fundamental-parameters territory fenced to v2, not a tuning gap."),
    ("GoF does not reach 1 on lab data and should not be expected to.",
     "Cline et al. (2015) put the floor for analytical-PSF fits on this "
     "instrument class at 1.5-1.9; FPA reaches 1.08.  Measured 1.61 on "
     "corundum with Rexp ~ 8.9 %, so Rwp 14.4 % is mostly counting "
     "statistics.  A policy demanding GoF -> 1 would be demanding FPA."),
    ("The Apple-GPU (MPS) evidence is maintainer-machine-only.",
     "Every torch-mps assertion is gated on torch.backends.mps.is_available(), "
     "which is False on hosted macOS runners.  The all-fp32 refinement landing "
     "3.5e-8 A from numpy fp64 is real-hardware evidence for the fp64-host "
     "boundary, and no CI job reproduces it.  A green macOS job must not be "
     "read as 'MPS verified'."),
    ("Multi-phase CIF round-tripping is not validated.",
     "write_refinement_cif's round trip is checked single-phase only; a "
     "multi-phase re-read was never a v0.3 commitment.  Whatever the frozen "
     "API says about CIF round-tripping has to narrow to that."),
    ("The bit-identity goldens hold on one platform, by measurement.",
     "tests/test_backend_shim.py's array_equal gate — the check that says no "
     "refactor changed a single computed number — is pinned to darwin/arm64 "
     "(GOLDEN_PLATFORM) and skips elsewhere.  WP-1002's CI matrix measured "
     "why: a numpy change does not move the goldens (2.4.6 and 2.5.1 agree "
     "bit for bit) but Linux x86-64 diverges on every state, by 1 ulp on "
     "quantities that are a single arithmetic chain and up to ~1100 ulp "
     "(1.7e-13 relative) on y_calc, which accumulates ~130 windows of "
     "transcendentals.  That gradient with chain length identifies a libm and "
     "summation-order difference, not a code difference, and even the worst "
     "of it is ten orders below the tightest physical bar here.  A hosted "
     "macOS/arm64 runner then reproduced 7 of 8 states at identical "
     "numpy/scipy/Accelerate and missed toy_rich by exactly one ulp, so the "
     "pin is really to a machine image and **no CI environment asserts these "
     "bits at all** — maintainer-machine evidence, the same shape as the MPS "
     "gap.  A tolerance wide enough to absorb a libm difference would absorb "
     "a real one too, so the gate stays exact and CI reports it instead."),
    ("Windows passes, once, and nothing keeps it that way.",
     "Probed on a throwaway branch 2026-07-29: the fast suite is 982 passed / "
     "115 skipped / 0 failed on windows-latest with Python 3.13.  Getting "
     "there fixed one real bug — write_qpa_table handed csv.writer output, "
     "which already ends \\r\\n, to write_text, so text mode translated each "
     "\\n again and every row ended \\r\\r\\n, i.e. corrupt CSV for Windows "
     "users and invisible on POSIX — plus every text read/write in the tree "
     "now names encoding=utf-8, since the default is cp1252 there and UTF-8 "
     "here.  tests/test_portability.py guards both by AST.  But **no "
     "scheduled job runs Windows**, so this is a point measurement, not a "
     "supported platform, and pyproject claims no OS classifier."),
    ("CI reports; it does not gate.",
     "Branch protection needs a paid plan or a public repository, so nothing "
     "stops a red push landing on main today.  Every number in this document "
     "was produced by a green tree, but the enforcement that would keep it "
     "that way arrives with the v1.0 release (WP-1003)."),
)


# ---------------------------------------------------------------------------
# Renderer.  ``docs/VALIDATION.md`` is this function's output, byte for byte;
# the guard in ``test_validation_matrix.py`` fails if the committed file has
# drifted, which is the whole anti-drift design (WP-0604's, applied here).
# ---------------------------------------------------------------------------

#: Suite-level narrative, keyed by module.  The per-row prose is in the
#: ``Claim`` objects; this is the sentence that says what the *dataset* is for.
SUITE_INTROS: dict[str, str] = {
    "test_acceptance_indexing":
        "The only externally *graded* feature in the package. Bergmann et al. "
        "(2004) published both the data and every program's score, so the bar "
        "here is what ITO13, DICVOL91, TREOR90 and McMaille actually achieved "
        "rather than a tolerance chosen in this repo. The fixture is checked "
        "against three statements that paper makes in prose and never "
        "tabulates before anything is graded against it.",
    "test_acceptance_srm660c":
        "The absolute lab anchor. NIST's own SRM 660c certification "
        "measurement, refined against the cell recomputed for this dataset's "
        "temperature block.",
    "test_acceptance_srm676a":
        "The second absolute anchor, and the sharper one — but only on the "
        "axial ratio, where the lab d-scale systematic cancels.",
    "test_acceptance_fap":
        "The one cross-code comparison. GSAS-II's converged fluorapatite "
        "tutorial, with its protocol mirrored parameter for parameter.",
    "test_acceptance_nac":
        "The synchrotron vertical slice, and the FitReport's impurity claim: "
        "CaF2 is found from unmatched peaks rather than declared.",
    "test_acceptance_qpa_roundrobin":
        "Quantitative phase analysis against weighed truth, at tolerances "
        "referenced to what the round robin's participants achieved.",
    "test_acceptance_dispersion":
        "The same round robin with anomalous scattering applied — a "
        "pre-registered, parameter-free prediction about numbers already "
        "recorded in the v0.3 milestone.",
    "test_acceptance_capillary":
        "A correction that provably cannot improve the fit, on real data. "
        "The whole of its content is a predicted shift in every displacement "
        "parameter.",
    "test_acceptance_sequential":
        "A warm-started chain over the round robin: what changes when only "
        "the starting point changes.",
    "test_acceptance_stephens":
        "Anisotropic strain, and the matrix's canonical inadmissibility "
        "result — an improvement both statistical tests bless and the "
        "physics rejects.",
}


def _suite_order() -> list[str]:
    seen: list[str] = []
    for c in CLAIMS:
        if c.module not in seen:
            seen.append(c.module)
    return seen


def render_markdown() -> str:
    """The full ``docs/VALIDATION.md``, generated from the registry above."""
    out: list[str] = []
    w = out.append

    w("# pxrd-refine — validation matrix\n")
    w("<!-- GENERATED FILE — do not edit by hand.\n"
      "     Source: tests/validation_matrix.py\n"
      "     Regenerate: .venv/bin/python -m tests.validation_matrix\n"
      "     Guarded by: tests/test_validation_matrix.py (fast suite) -->\n")
    w("Every real-data assertion in this repository, and what its tolerance "
      "is\nreferenced to. A bar without its referent is not a claim: "
      "`abs(a - 4.156780) <\n2e-4` and `abs(delta_a) < 1e-9` look alike and "
      "are not remotely the same\nstatement — the first is a certified value "
      "the fit does not reach and does not\nclaim to, the second is two of "
      "our own fits that must agree to floating point.\n")
    w("The policy this table implements is in "
      "[DESIGN.md](DESIGN.md#testing--validation-policy);\nthe measured "
      "milestone records are in [milestones/](milestones/).\n")

    w("## The one rule that shapes everything below\n")
    w("**Judge a correction by what it changed, never by delta Rwp.** Of the "
      "eight\ncorrections in v0.5, two provably cannot move Rwp, one moves it "
      "the *wrong way*\nwhen it is right, and the two largest accuracy wins "
      "are invisible in it. A\nvalidation matrix whose columns were agreement "
      "indices would score that\nmilestone as having delivered nothing — "
      "which is why two of the tiers below\nare kinds of evidence rather than "
      "kinds of tolerance.\n")

    w("## Tiers\n")
    for name, rule in TIERS.items():
        w(f"### `{name}`\n")
        w(rule + "\n")

    w("## Start dependence\n")
    w("How many independent starting points a quoted number has to survive. "
      "This is\na validation axis because it was measured to change a "
      "conclusion: sweeping the\nStephens strain seed over 400/800/1600/3000 "
      "on round-robin brucite leaves the\ncoefficients spanning ~100 % "
      "relative spread under *both* solvers, and moves the\nunconstrained fit "
      "in and out of the physical cone (15, 12, 0, 0 reflections\nviolating). "
      "A single-start acceptance number would have called that specimen\n"
      "either fine or broken depending on which seed the suite happened to "
      "pin.\n")
    w("1. A **cell parameter, weight fraction or scale** may be quoted from "
      "one start.\n   These are well-conditioned and the staged plan reaches "
      "the same basin from any\n   sane starting model. Every `certificate`, "
      "`cross_code` and `spread` row below\n   is single-start, and that is "
      "not a weakness.\n"
      "2. A **width or shape parameter entering through a square root, a "
      "cone, or a\n   softplus floor** must survive a documented sweep before "
      "any number is quoted\n   from it — that is the class where the "
      "objective is flat or non-convex near\n   the start.\n"
      "3. When a sweep is run and the parameters move but the **conclusion** "
      "does not,\n   the conclusion is what gets recorded and the sweep goes "
      "in the docstring. Pinning\n   a per-seed number would convert a known "
      "instability into a flaky test.\n")

    w("## Datasets\n")
    w("| Key | File | Role | What it is |")
    w("|---|---|---|---|")
    roles = {
        "absolute": "**absolute anchor**",
        "cross_code": "cross-code",
        "consistency": "consistency only — *never* an anchor",
        "characterisation": "characterisation",
    }
    for key, ds in DATASETS.items():
        w(f"| `{key}` | `tests/data/{ds.path}` | {roles[ds.role]} | "
          f"{ds.description} |")
    w("")
    w("`consistency` is a fence, not a label: 11-BM calibrated its wavelength "
      "against\nSRM 660a LaB6 itself, so a refined LaB6 cell from that file "
      "reproduces the\ncertificate by construction. A guard refuses to let "
      "any such dataset carry a\n`certificate` row.\n")

    w("## The matrix\n")
    for module in _suite_order():
        rows = [c for c in CLAIMS if c.module == module]
        w(f"### `tests/{module}.py`\n")
        w(SUITE_INTROS[module] + "\n")
        for c in rows:
            tiers = " ".join(f"`{t}`" for t in c.tiers)
            w(f"#### `{c.test}`\n")
            w(f"{tiers} · dataset `{c.dataset}`"
              + (f" · survives {c.starts} starts" if c.starts > 1 else "")
              + "\n")
            w(f"**Claims:** {c.claim}\n")
            if c.reference:
                w(f"**Referenced to:** {c.reference}\n")
            if c.measured:
                w(f"**Measured:** {c.measured}\n")
            if c.diagnostics:
                shown = ", ".join(
                    (f"`{d[1:]}` asserted *absent*" if d.startswith("!")
                     else f"`{d}`") for d in c.diagnostics)
                w(f"**Diagnostics:** {shown}\n")

    w("## The one default this matrix decided\n")
    w("`Source.dispersion` shipped opt-in through v0.6 so that landing it did "
      "not\ninvalidate the record. WP-1001 was chartered to decide whether it "
      "should be the\ndefault, and measured the question rather than "
      "inheriting the recommendation.\n")
    w("**For it.** Dispersion is the only correction in the package that "
      "needs *no\ninformation the caller does not already have*. Capillary "
      "absorption wants muR,\nroughness a surface, Stephens a strain model, "
      "March-Dollase a habit — dispersion\nwants the species and the "
      "wavelength, both already in the model. Neglecting it\ncosts RMS 2.26 "
      "-> 0.69 wt % on round-robin QPA.\n")
    w("**The anchors survive.** SRM 660c's cell does not move (4.156895 A "
      "either way).\nSRM 676a's certificate-grade c/a moves +29.8 -> +30.2 "
      "ppm against a 100 ppm bar —\nmeasured for this WP, since WP-0504 never "
      "checked it. And Rwp on corundum gets\n*worse*, 14.374 -> 14.531 %, "
      "while the physics gets better: the rule at the top of\nthis document, "
      "now at the level of a package default.\n")
    w("**Against it, measured.** A wavelength inside an absorption-edge "
      "interval\n**raises** rather than degrading — 12 of 1176 (element x "
      "shipped anode)\ncombinations including Eu and Ho at Cu Ka, and "
      "0.0-1.2 % of arbitrary synchrotron\nwavelengths depending on the "
      "specimen. Raising is kept deliberately: a selective\nfallback would "
      "leave some species corrected and others not, manufacturing exactly\n"
      "the unequal cross-phase bias the correction exists to remove, which is "
      "*worse*\nthan uniformly declining. `dispersion = None` is the one-line "
      "escape and the\ndiagnostic names it.\n")
    w("**Decided: flipped.** Absorbing it moved 21 tests, and the shape of "
      "that cost is\nthe lasting lesson — nine were bit-identity goldens with "
      "no opinion about\ndispersion at all; they simply inherited it. Every "
      "test that pins a number now\ndeclares this setting explicitly, and "
      "every golden is bit-identical again, which\nis the evidence the flip "
      "touched physics and not plumbing. Two knock-on effects\nare recorded "
      "rather than tuned away:\n")
    w("- Light-atom ADPs come back **less precise even as they come back less "
      "biased**:\n  rutile U11/U33 separate at 1.9 sigma with the block on "
      "against 2.2 sigma without,\n  because f\" raises the heavy atom's "
      "share of every reflection.\n"
      "- The calibrate -> freeze -> refine size/strain split degrades from "
      "27 % low to\n  39 % low — a bar that was already marginal on a "
      "degenerate direction\n  (lor_size, gauss_strain and the frozen "
      "instrument X are one correlated triple).\n")

    w("## Known gaps\n")
    w("A matrix that lists only what passed is marketing. These are the holes "
      "a reader\nshould know about before trusting a number, each with what "
      "would close it.\n")
    for title, body in GAPS:
        w(f"- **{title}** {body}\n")

    return "\n".join(out).rstrip() + "\n"


if __name__ == "__main__":  # pragma: no cover - regeneration entry point
    import pathlib

    target = pathlib.Path(__file__).resolve().parents[1] / "docs" / "VALIDATION.md"
    target.write_text(render_markdown(), encoding="utf-8")
    print(f"wrote {target} ({len(CLAIMS)} claims, {len(TIERS)} tiers)")

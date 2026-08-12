"""FitReport Layers 1-2: synthetic misfit injection and confidence calibration.

The design record is explicit that without this suite the confidence numbers
are decorative.  Each test perturbs exactly **one** known cause in a
converged model, rebuilds the report, and asserts the report recovers that
cause — and, just as importantly, that deliberately-collinear setups are
reported as *unresolved* rather than as a confident wrong singleton.
"""

from pathlib import Path

import numpy as np
import pytest

import pxrdref as pr
from pxrdref.model.forward import compile_model
from pxrdref.params.vector import ParameterTable
from pxrdref.report import (
    apply_strategy_veto,
    build_report,
    delta_bic,
    hamilton_justified,
    predict_then_verify,
)
from pxrdref.report.schemas import LEBAIL_GAP_NOTABLE, VALIDITY_RADIUS_FWHM
from tests.test_schemas import make_lab6

WAVELENGTH = 1.5405929


# ----------------------------------------------------------------------
# a converged reference state we can perturb one knob at a time
# ----------------------------------------------------------------------
#: Poisson count scaling.  Kept high on purpose: the information that
#: separates a constant zero error from a cosθ displacement lives in the
#: *high-angle* peaks, and at low counts those regions carry no significant
#: misfit, so the report (correctly) refuses to separate the two.  Measured
#: separability ratio at these settings: 1.2 at ×8 counts vs 10 at ×60.
_COUNT_SCALE = 60.0


def _truth(lo=18.0, hi=125.0, step=0.02, seed=17):
    """A model and the noisy pattern it generates — i.e. a *converged* state.

    The background lives in the instrument (a flat Chebyshev term), not added
    on top of the pattern, so that the unperturbed model reproduces the data
    to within counting noise and Layer 1 has a mature fit to work from.
    """
    from pxrdref.schemas.instrument import BackgroundChebyshev

    structure = make_lab6()
    structure.phases[0].scale.value = 4e-4
    ins = pr.Instrument.bragg_brentano(monochromator_two_theta=26.6)
    ins.profile.w.value = 4e-3
    ins.profile.u.value = 3e-3
    ins.profile.x.value = 6e-3
    ins.geometry.axial_sl.value = 0.02
    ins.geometry.axial_hl.value = 0.02
    ins.background = BackgroundChebyshev(coefficients=[
        pr.Parameter(value=80.0), pr.Parameter(value=0.0),
        pr.Parameter(value=0.0), pr.Parameter(value=0.0)])

    tt = np.arange(lo, hi, step)
    grid = pr.PatternData(two_theta=tt.tolist(), intensity=[0.0] * len(tt))
    model = compile_model(structure, ins, grid, mode="rietveld")
    table = ParameterTable(structure, ins)
    y = model.evaluate(table.decode(table.x0()))
    rng = np.random.default_rng(seed)
    y_noisy = rng.poisson(np.maximum(y, 1.0) * _COUNT_SCALE) / _COUNT_SCALE
    data = pr.PatternData(two_theta=model.tt.tolist(), intensity=y_noisy.tolist(),
                          sigma=np.sqrt(np.maximum(y, 1.0) / _COUNT_SCALE).tolist())
    return structure, ins, data


def _result_for(structure, ins, data):
    """A RefinementResult evaluated at a *given* (unrefined) model state."""
    table = ParameterTable(structure, ins)
    model = compile_model(structure, ins, data, mode="rietveld")
    values = table.decode(table.x0())
    y_calc = model.evaluate(values)
    from pxrdref.optimize.statistics import compute_statistics
    from pxrdref.schemas.common import Provenance
    from pxrdref.schemas.results import RefinementResult

    stats = compute_statistics(model.y_obs, y_calc, model.sigma, n_free=0,
                               y_background=model.background(values))
    ticks = {}
    for ip, cp in enumerate(model.phases):
        cell = tuple(values[f"phases.{ip}.cell.{k}"]
                     for k in ("a", "b", "c", "alpha", "beta", "gamma"))
        pos = np.concatenate([cp.reflections.two_theta(cell, lam)
                              for lam in model.line_wavelengths])
        ticks[structure.phases[ip].name] = sorted(
            float(p) for p in pos if np.isfinite(p))
    result = RefinementResult(
        status="converged", mode="rietveld", parameters=[], statistics=stats,
        provenance=Provenance(package_version="test"),
        two_theta=model.tt.tolist(), y_obs=model.y_obs.tolist(),
        y_calc=y_calc.tolist(), y_background=model.background(values).tolist(),
        sigma=model.sigma.tolist(), ticks=ticks)
    return result, model, values


def _report_for(structure, ins, data, **kw):
    """Build the full report for a *given* (unrefined) model state."""
    result, model, values = _result_for(structure, ins, data)
    return build_report(result, model=model, values=values, **kw)


def _coefficients(report, kind):
    return [c.value for a in report.attribution if a.gates_passed
            for c in a.coefficients if c.kind == kind and c.significant]


def _template(report, observable, name):
    for t in report.trends:
        if t.observable == observable:
            for tpl in t.templates:
                if tpl.name == name:
                    return tpl
    return None


def _kinds(report, *, active_only=True):
    return [a.kind for a in report.suggested_actions if a.active or not active_only]


# ----------------------------------------------------------------------
# baseline: an unperturbed model must not invent causes
# ----------------------------------------------------------------------
@pytest.fixture(scope="module")
def truth():
    return _truth()


def test_unperturbed_model_reports_no_strong_cause(truth):
    structure, ins, data = truth
    report = _report_for(structure, ins, data)
    assert report.layer1_available, report.abstained_reason
    # noise only: nothing should reach high confidence
    strong = [a for a in report.suggested_actions if a.active and a.confidence > 0.6]
    assert not strong, f"invented causes on a correct model: {[a.kind for a in strong]}"
    # and the position coefficients must be small compared with the FWHM
    shifts = _coefficients(report, "position")
    if shifts:
        assert max(abs(s) for s in shifts) < 0.01


# ----------------------------------------------------------------------
# single-cause injections
# ----------------------------------------------------------------------
def _best_template(report, observable):
    trend = next(t for t in report.trends if t.observable == observable)
    return trend, max(trend.templates, key=lambda t: t.r2)


def test_injected_zero_shift_is_recovered(truth):
    """A pure zero-point error: constant Δ2θ across the whole pattern.

    The injection is deliberately small (0.008° ≈ 0.12·FWHM): the shape basis
    is a *first-order* expansion, and a shift approaching the validity radius
    is recovered with a systematic deficit (measured −0.014 for a 0.020°
    injection).  Large offsets are the validity gate's job, tested separately.
    """
    structure, ins, data = truth
    perturbed = ins.model_copy(deep=True)
    perturbed.zero_shift.value = 0.008

    report = _report_for(structure, perturbed, data)
    assert report.layer1_available, report.abstained_reason

    shifts = _coefficients(report, "position")
    assert shifts, "no significant position error detected"
    # observed sits 0.008° BELOW where the shifted model puts the peaks
    assert np.median(shifts) == pytest.approx(-0.008, abs=0.002)

    trend, best = _best_template(report, "position")
    assert best.name == "constant", f"a constant shift ranked as {best.name}"
    assert best.coefficient == pytest.approx(-0.008, abs=0.002)
    assert trend.separable, f"ratio={trend.separability_ratio:.2f}"
    assert "refine_zero_shift" in _kinds(report, active_only=False)


def test_injected_displacement_prefers_cos_theta_template(truth):
    """Specimen displacement has a cosθ signature, distinguishable from a
    constant zero error *because* the scan runs to 125° 2θ."""
    structure, ins, data = truth
    # 0.02 mm at R = 217.5 mm is ≈0.010° at low angle — inside the
    # linearisation radius (0.4·FWHM ≈ 0.027°)
    perturbed = ins.model_copy(deep=True)
    perturbed.geometry.sample_displacement.value = -0.02

    report = _report_for(structure, perturbed, data)
    assert report.layer1_available, report.abstained_reason

    trend, best = _best_template(report, "position")
    assert best.name == "cos_theta", f"a cosθ shift ranked as {best.name}"
    assert trend.separable, (
        f"cosθ and constant must separate over 18-125° 2θ "
        f"(ratio={trend.separability_ratio:.2f})")
    assert abs(best.coefficient) > 3 * best.stderr
    assert "refine_sample_displacement" in _kinds(report, active_only=False)


def test_injected_width_error_is_recovered(truth):
    """Peaks too narrow → a positive ΔΓ coefficient everywhere."""
    structure, ins, data = truth
    perturbed = ins.model_copy(deep=True)
    perturbed.profile.w.value = 2.0e-3      # truth is 4e-3

    report = _report_for(structure, perturbed, data)
    assert report.layer1_available, report.abstained_reason
    widths = _coefficients(report, "width")
    assert widths, "no significant width error detected"
    assert np.median(widths) > 0, "model is too narrow; ΔΓ must be positive"
    assert any(k in _kinds(report, active_only=False)
               for k in ("refine_profile_widths", "refine_sample_size_broadening",
                         "refine_sample_strain_broadening"))


def test_injected_scale_error_is_recovered(truth):
    structure, ins, data = truth
    perturbed = structure.model_copy(deep=True)
    perturbed.phases[0].scale.value = 4e-4 * 0.90   # 10 % too weak

    report = _report_for(perturbed, ins, data)
    assert report.layer1_available, report.abstained_reason
    rel = _coefficients(report, "intensity")
    assert rel, "no significant intensity error detected"
    assert np.median(rel) == pytest.approx(0.10, abs=0.05)
    assert "refine_scale" in _kinds(report, active_only=False)


def test_injected_impurity_peak_is_suggested_as_a_phase(truth):
    structure, ins, data = truth
    tt = np.asarray(data.two_theta)
    y = np.asarray(data.intensity, dtype=float)
    y = y + 900.0 * np.exp(-0.5 * ((tt - 29.35) / 0.06) ** 2)
    doped = pr.PatternData(two_theta=tt.tolist(), intensity=y.tolist(),
                           sigma=data.sigma)

    report = _report_for(structure, ins, doped)
    assert any(u.kind == "unmatched_obs" and abs(u.two_theta - 29.35) < 0.15
               for u in report.unmatched)
    assert "add_impurity_phase" in _kinds(report, active_only=False)


# ----------------------------------------------------------------------
# the gates: the report must refuse to over-read
# ----------------------------------------------------------------------
def test_large_offset_trips_the_validity_radius_gate(truth):
    """A cell error that moves peaks many FWHM must NOT be reported as a
    confident small shift — the gate exists precisely for this."""
    structure, ins, data = truth
    perturbed = structure.model_copy(deep=True)
    perturbed.phases[0].cell = pr.Cell.cubic(4.1568 * 1.004)   # 0.4 % off

    report = _report_for(perturbed, ins, data)
    tripped = [a for a in report.attribution
               if any("validity_radius" in f for f in a.gate_failures)]
    assert tripped, "gross peak offsets passed the validity radius unflagged"
    for a in tripped:
        assert not a.gates_passed
        assert abs(next(c.value for c in a.coefficients if c.kind == "position")) \
            > VALIDITY_RADIUS_FWHM * a.mean_fwhm


def test_immature_fit_makes_layer1_abstain():
    """With the model grossly wrong the whole layer must abstain rather than
    attribute the misfit to specific small parameter errors."""
    structure, ins, data = _truth()
    broken = structure.model_copy(deep=True)
    broken.phases[0].cell = pr.Cell.cubic(4.60)      # nowhere near
    broken.phases[0].scale.value = 4e-5

    report = _report_for(broken, ins, data)
    assert not report.layer1_available
    assert report.abstained_reason
    assert "abstained" in report.summary
    # no *parameter-level* claims survive abstention
    assert all(a.kind in ("add_impurity_phase", "reindex_or_recheck_cell")
               for a in report.suggested_actions)
    assert report.trends == []
    # the model-free layer must still work — that is its whole point
    assert report.rwp > 0.2 and report.regions
    assert report.gof > 5.0


def test_short_range_reports_position_templates_as_unseparable():
    """Over a narrow 2θ window constant/cosθ/sin2θ/tanθ are collinear; the
    report must say so instead of picking a confident winner."""
    # 20-56° 2θ gives ~6 LaB6 peak clusters (enough regions to fit the four
    # position templates) but only θ = 10-28°, over which cosθ barely varies:
    # measured template collinearity 0.9995, against 0.979 over the full
    # 18-125° range where the same templates *do* separate.
    structure, ins, data = _truth(lo=20.0, hi=56.0, seed=23)
    perturbed = ins.model_copy(deep=True)
    perturbed.zero_shift.value = 0.02

    report = _report_for(structure, perturbed, data)
    if not report.layer1_available:
        pytest.skip(f"layer 1 abstained: {report.abstained_reason}")
    trend = next(t for t in report.trends if t.observable == "position")
    assert trend.n_regions_used >= 4
    assert trend.max_template_collinearity > 0.995
    assert trend.separability_ratio < 2.0
    assert not trend.separable
    for action in report.suggested_actions:
        if action.kind in ("refine_zero_shift", "refine_sample_displacement",
                           "refine_sample_transparency", "refine_cell"):
            assert action.confidence <= 0.3, action
            assert action.alternatives, "an unseparable call must list its rivals"


# ----------------------------------------------------------------------
# confidence calibration over an injection ensemble
# ----------------------------------------------------------------------
def test_confidence_calibration_over_injection_ensemble():
    """Design-record criterion: when the report is confident (>0.8) it should
    be right; here we check the weaker, testable version — every confident
    call on a *known* single-cause injection names the true cause among its
    active suggestions, and the top-ranked suggestion is right ≥80 % of the
    time across the ensemble."""
    structure, ins, data = _truth(seed=31)
    cases = []

    # every injection stays inside the linearisation radius — outside it the
    # correct answer is the validity gate, not an attribution
    p = ins.model_copy(deep=True)
    p.zero_shift.value = 0.008
    cases.append(("refine_zero_shift", structure, p))

    p = ins.model_copy(deep=True)
    p.geometry.sample_displacement.value = -0.02
    cases.append(("refine_sample_displacement", structure, p))

    p = ins.model_copy(deep=True)
    p.profile.w.value = 3.0e-3          # truth 4e-3
    cases.append(("refine_profile_widths", structure, p))

    s = structure.model_copy(deep=True)
    s.phases[0].scale.value = 4e-4 * 0.92
    cases.append(("refine_scale", s, ins))

    ranked_first = 0
    for expected, st, ii in cases:
        report = _report_for(st, ii, data)
        assert report.layer1_available, f"{expected}: {report.abstained_reason}"
        kinds = _kinds(report, active_only=False)
        assert kinds, f"{expected}: no suggestions at all"

        # position causes are mutually substitutable when collinear
        family = {
            "refine_zero_shift": {"refine_zero_shift", "refine_sample_displacement",
                                  "refine_sample_transparency", "refine_cell"},
            "refine_sample_displacement": {"refine_sample_displacement",
                                           "refine_zero_shift", "refine_cell"},
            "refine_profile_widths": {"refine_profile_widths",
                                      "refine_sample_size_broadening",
                                      "refine_sample_strain_broadening"},
            "refine_scale": {"refine_scale", "refine_biso"},
        }[expected]
        assert family & set(kinds), f"{expected}: true cause absent, got {kinds}"
        if kinds[0] in family:
            ranked_first += 1

        # any *high-confidence* call must be in the true cause's family
        for a in report.suggested_actions:
            if a.confidence > 0.8:
                assert a.kind in family, (
                    f"{expected}: confident ({a.confidence}) but wrong: {a.kind}")

    assert ranked_first >= 0.8 * len(cases), (
        f"true cause ranked first in only {ranked_first}/{len(cases)} cases")


# ----------------------------------------------------------------------
# Layer 2 machinery
# ----------------------------------------------------------------------
def test_strategy_veto_marks_planned_actions_inactive(truth):
    structure, ins, data = truth
    perturbed = ins.model_copy(deep=True)
    perturbed.zero_shift.value = 0.02
    plan = pr.RefinementPlan.lab_bragg_brentano()

    report = _report_for(structure, perturbed, data, plan=plan)
    zero = report.action("refine_zero_shift")
    assert not zero.active, "the plan already refines zero — must be vetoed"
    assert zero.vetoed_by and "staged plan" in zero.vetoed_by


def test_veto_by_already_free_parameters(truth):
    structure, ins, data = truth
    perturbed = ins.model_copy(deep=True)
    perturbed.zero_shift.value = 0.02
    report = _report_for(structure, perturbed, data,
                         free_paths=["instrument.zero_shift"])
    zero = report.action("refine_zero_shift")
    assert not zero.active
    assert "already free" in (zero.vetoed_by or "")


def test_predict_then_verify_accepts_a_real_improvement(truth):
    """Verification must accept an action that genuinely helps, and the
    rollback must leave the parent state untouched."""
    structure, ins, data = truth
    start = ins.model_copy(deep=True)
    start.zero_shift.value = 0.02

    ref = pr.Refinement(structure, start)
    ref.fit(data, plan=pr.RefinementPlan(stages=[
        pr.Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"])]))
    chi2_before = ref.result_.statistics.chi2

    action = pr.SuggestedAction(kind="refine_zero_shift", confidence=0.9,
                                rationale="test", parameter_paths=["instrument.zero_shift"])
    outcome = predict_then_verify(ref, data, action)
    assert outcome.accepted, outcome.reason
    assert outcome.observed_delta_chi2 > 0
    # the parent refinement is untouched: verification ran on a branch
    assert ref.result_.statistics.chi2 == chi2_before


def test_predict_then_verify_rejects_a_useless_action(truth):
    structure, ins, data = truth
    ref = pr.Refinement(structure, ins.model_copy(deep=True))
    ref.fit(data, plan="lab_bragg_brentano")

    useless = pr.SuggestedAction(
        kind="refine_sample_transparency", confidence=0.2, rationale="test",
        parameter_paths=["instrument.geometry.sample_transparency"])
    outcome = predict_then_verify(ref, data, useless)
    assert not outcome.accepted
    assert "rolled back" in outcome.reason


def test_veto_helper_is_pure_annotation():
    actions = [pr.SuggestedAction(kind="refine_cell", confidence=0.9,
                                  rationale="x", parameter_paths=["phases.*.cell.*"])]
    out = apply_strategy_veto(actions, pr.RefinementPlan.mccusker_default())
    assert len(out) == 1                    # never dropped, only annotated
    assert not out[0].active
    assert out[0].confidence == 0.9         # and the reasoning is preserved


# ----------------------------------------------------------------------
# texture → typed action (the WP-0307 orphan, claimed by WP-0602)
# ----------------------------------------------------------------------
def _texture(detected=True, r2=0.82, runner_r2=0.1, **kw):
    from pxrdref.report import TextureAnalysis

    # best_axis is always populated since WP-1054 (evidence, not a verdict);
    # ``detected`` alone decides whether an action is emitted
    base = dict(phase_index=0, best_axis=(0, 0, 1),
                march_coefficient=0.71, r2=r2, n_reflections_used=17,
                detected=detected, runner_up_axis=(1, 1, 0),
                runner_up_r2=runner_r2)
    base.update(kw)
    return TextureAnalysis(**base)


def test_texture_action_emitted_only_when_detected():
    from pxrdref.report import texture_actions

    assert texture_actions([]) == []
    assert texture_actions([_texture(detected=False)]) == []

    (action,) = texture_actions([_texture()])
    assert action.kind == "refine_preferred_orientation"
    assert action.parameter_paths == ["phases.0.preferred_orientation.r"]
    assert action.confidence == pytest.approx(0.82, abs=1e-6)
    assert "(0, 0, 1)" in action.rationale and "r=0.710" in action.rationale
    # the linear-model Δχ² covers gated regions, not this per-reflection score
    assert action.expected_delta_chi2 is None


def test_texture_action_ambiguous_axis_caps_confidence():
    from pxrdref.report import texture_actions

    (action,) = texture_actions([_texture(runner_r2=0.75)])
    assert action.confidence <= 0.4
    assert "not cleanly resolved" in action.rationale
    assert "(1, 1, 0)" in action.rationale        # runner-up named, per §6


def test_texture_action_is_vetoed_by_a_plan_that_frees_r():
    from pxrdref.report import texture_actions

    actions = texture_actions([_texture()])
    out = apply_strategy_veto(actions, pr.RefinementPlan.mccusker_structural())
    assert not out[0].active                       # plan already frees r
    out = apply_strategy_veto(texture_actions([_texture()]),
                              pr.RefinementPlan.mccusker_default())
    assert out[0].active                           # profile-only plan does not


# ----------------------------------------------------------------------
# statistical justification for new parameters
# ----------------------------------------------------------------------
def test_hamilton_test_and_bic_agree_on_a_real_improvement():
    # χ² here is the raw Σw·Δ², so a well-scaled fit has χ² ≈ N − P.
    # A 200-unit drop for one added parameter over 5000 points is decisive.
    assert hamilton_justified(5000.0, 4800.0, n_points=5000,
                              n_free_restricted=10, n_added=1)
    assert delta_bic(5000.0, 4800.0, n_points=5000, n_added=1) > 0


def test_hamilton_test_rejects_a_cosmetic_improvement():
    # under the null each added parameter absorbs ~1 unit of χ² by itself,
    # so a drop of 1 is exactly what noise buys — F ≈ 1, not significant
    assert not hamilton_justified(5000.0, 4999.0, n_points=5000,
                                  n_free_restricted=10, n_added=1)
    assert delta_bic(5000.0, 4999.0, n_points=5000, n_added=1) < 0


def test_plot_for_vlm_writes_png_only(tmp_path, truth):
    structure, ins, data = truth
    perturbed = ins.model_copy(deep=True)
    perturbed.zero_shift.value = 0.008
    report = _report_for(structure, perturbed, data)

    # rebuild the bare result for plotting
    from pxrdref.viz.plots import plot_for_vlm
    ref = pr.Refinement(structure, perturbed, history=False)
    result = ref.fit(data, plan=pr.RefinementPlan(stages=[
        pr.Stage("bkg", ["instrument.background.*"])]))

    with pytest.raises(ValueError, match="PNG"):
        plot_for_vlm(result, report, path=str(tmp_path / "montage.jpg"))
    out = tmp_path / "montage.png"
    plot_for_vlm(result, report, path=str(out))
    assert out.exists() and out.stat().st_size > 20_000
    assert out.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_hamilton_rejects_degenerate_inputs():
    assert not hamilton_justified(100.0, 100.0, n_points=10,
                                  n_free_restricted=9, n_added=5)
    assert not hamilton_justified(100.0, 0.0, n_points=500,
                                  n_free_restricted=5, n_added=1)


# ----------------------------------------------------------------------
# WP-1054 — Layer-2 honesty on the abstained branch
# ----------------------------------------------------------------------
_OUT = Path(__file__).parent / "output"


def _plot_state(structure, ins, data, stem):
    """obs/calc/diff PNGs to tests/output/ (gitignored), full range + a
    low-angle zoom — house convention: Rwp hides locally-bad fits."""
    from pxrdref.viz.plots import plot_result

    result, _, _ = _result_for(structure, ins, data)
    _OUT.mkdir(exist_ok=True)
    plot_result(result, path=str(_OUT / f"{stem}.png"))
    plot_result(result, path=str(_OUT / f"{stem}_zoom.png"),
                two_theta_range=(18.0, 45.0))


def _broad_truth(lor_size, seed=17):
    """The `_truth` recipe with Lorentzian size broadening in the *data*, so
    the unperturbed model matches the broad peaks exactly."""
    from pxrdref.model.forward import compile_model
    from pxrdref.params.vector import ParameterTable

    structure, ins, _ = _truth(seed=seed)
    structure = structure.model_copy(deep=True)
    structure.phases[0].lor_size.value = lor_size
    tt = np.arange(18.0, 125.0, 0.02)
    grid = pr.PatternData(two_theta=tt.tolist(), intensity=[0.0] * len(tt))
    model = compile_model(structure, ins, grid, mode="rietveld")
    table = ParameterTable(structure, ins)
    y = model.evaluate(table.decode(table.x0()))
    rng = np.random.default_rng(seed)
    y_noisy = rng.poisson(np.maximum(y, 1.0) * _COUNT_SCALE) / _COUNT_SCALE
    data = pr.PatternData(
        two_theta=model.tt.tolist(), intensity=y_noisy.tolist(),
        sigma=np.sqrt(np.maximum(y, 1.0) / _COUNT_SCALE).tolist())
    return structure, ins, data


def _doped(data, two_theta=29.35, height=900.0, width=0.06):
    """The impurity doping recipe: one foreign Gaussian on top of the data."""
    tt = np.asarray(data.two_theta)
    y = np.asarray(data.intensity, dtype=float)
    y = y + height * np.exp(-0.5 * ((tt - two_theta) / width) ** 2)
    return pr.PatternData(two_theta=tt.tolist(), intensity=y.tolist(),
                          sigma=data.sigma)


def test_wrong_cell_abstained_leads_with_reindex(truth):
    """The WP-1054 headline state: a +0.4 % cell error abstains (correctly)
    and its displaced peaks read as 32 unmatched lines — before the WP the
    only surviving action was ``add_impurity_phase`` at 0.9, the phantom-phase
    invitation an on-haiku consumer quoted verbatim in WP-1053's pilot.  Now
    the abstained branch leads with the position-family pointer and the
    impurity call is capped, evidence intact on both."""
    from pxrdref.report.schemas import IMPURITY_SHIFT_CAP

    structure, ins, data = truth
    perturbed = structure.model_copy(deep=True)
    perturbed.phases[0].cell = pr.Cell.cubic(4.1568 * 1.004)

    report = _report_for(perturbed, ins, data)
    assert report.abstained_reason, "a 0.4 % cell error must abstain"

    # Layer-0 evidence is untouched: those peaks *are* unmatched
    strong = [u for u in report.unmatched
              if u.kind == "unmatched_obs" and u.height_over_sigma > 8.0]
    assert len(strong) >= 20, len(strong)

    # the verdict layer: reindex tops the active set, carrying the whole
    # position family — never a confident reindex singleton
    active = [a for a in report.suggested_actions if a.active]
    assert active and active[0].kind == "reindex_or_recheck_cell", (
        [a.kind for a in active])
    assert active[0].confidence <= 0.5, active[0]
    assert set(active[0].alternatives) == {"refine_zero_shift",
                                           "refine_sample_displacement"}
    assert "have not chosen" in active[0].rationale
    assert "lower bound" in active[0].rationale     # saturated-fit honesty

    impurity = report.action("add_impurity_phase")
    assert impurity.confidence <= IMPURITY_SHIFT_CAP, impurity
    assert impurity.alternatives[0] == "reindex_or_recheck_cell", impurity
    assert f"all {len(strong)} unmatched" in impurity.rationale
    assert "re-check the cell" in impurity.rationale

    _plot_state(perturbed, ins, data, "wp1054_cell_wrong_abstained")


def test_broad_peak_lobes_cap_impurity_without_reindex():
    """The broad-peak variant: residual lobes of 0.66°-wide peaks under a
    0.05° zero error read as unmatched (the 0.08° matching tolerance is tiny
    against the peak), and pre-WP they bought ``add_impurity_phase`` at 0.7.
    They all sit within a fraction of a FWHM of a calculated position, so the
    call is capped — and *no* reindex pointer is emitted, because the
    validity failures here are saturated-fit artefacts (4 of 12 misfitting
    regions, below the widespread-failure fraction; the true shift is inside
    the validity radius of these broad peaks)."""
    from pxrdref.report.schemas import IMPURITY_SHIFT_CAP

    structure, ins, data = _broad_truth(0.6)
    perturbed = ins.model_copy(deep=True)
    perturbed.zero_shift.value = 0.05

    report = _report_for(structure, perturbed, data)
    assert report.abstained_reason, "the lobes must abstain the report"
    strong = [u for u in report.unmatched
              if u.kind == "unmatched_obs" and u.height_over_sigma > 8.0]
    assert strong, "the residual lobes must still appear as unmatched"

    impurity = report.action("add_impurity_phase")
    assert impurity.confidence <= IMPURITY_SHIFT_CAP, impurity
    assert impurity.alternatives[0] == "reindex_or_recheck_cell", impurity
    assert "reindex_or_recheck_cell" not in [a.kind
                                             for a in report.suggested_actions]

    _plot_state(structure, perturbed, data, "wp1054_broad_zero_lobes")


def test_impurity_no_longer_outranked_by_manufactured_texture(truth):
    """The pinned inversion: a pure impurity injection leaks into the
    per-reflection extraction and manufactures a (1,0,1) texture detection at
    R²=0.66 that outranked the impurity call 0.66 vs 0.40 (measured
    2026-08-11).  The detection stays — it is a true measurement of the
    residual — but is capped below the impurity action that likely feeds it,
    annotated with the mechanism, and its evidence survives untouched."""
    structure, ins, data = truth
    doped = _doped(data)

    report = _report_for(structure, ins, doped)
    impurity = report.action("add_impurity_phase")
    po = report.action("refine_preferred_orientation")
    assert impurity.confidence > po.confidence, (impurity, po)
    assert po.alternatives[0] == "add_impurity_phase", po
    assert "manufacture" in po.rationale

    tex = report.texture[0]
    assert tex.detected                      # the residual measurement stands
    assert tex.best_axis is not None and tex.r2 > 0.5   # evidence preserved
    assert tex.caveat and "manufacture" in tex.caveat
    assert tex.march_coefficient != 1.0

    _plot_state(structure, ins, doped, "wp1054_impurity_texture")


def test_double_injection_keeps_the_impurity_call(truth):
    """The regression control: a 0.05° zero error *and* a genuine foreign
    line at 29.34°.  The report abstains and the position evidence is
    widespread (10 of 14 misfitting regions beyond the radius), yet the
    foreign line pairs with nothing — nearest missing calculated line 1.18°
    away, outside the 1.0° pairing window — so the impurity call keeps its
    full strength beside the reindex pointer instead of drowning in it."""
    structure, ins, data = truth
    perturbed = ins.model_copy(deep=True)
    perturbed.zero_shift.value = 0.05
    doped = _doped(data)

    report = _report_for(structure, perturbed, doped)
    assert report.abstained_reason

    impurity = report.action("add_impurity_phase")
    assert impurity.confidence == pytest.approx(0.4, abs=1e-6), impurity
    assert "29.34" in impurity.rationale     # the genuine line, named
    kinds = [a.kind for a in report.suggested_actions]
    assert "reindex_or_recheck_cell" in kinds
    # the manufactured texture is capped below the genuine impurity here too
    po = report.action("refine_preferred_orientation")
    assert po.confidence < impurity.confidence

    _plot_state(structure, perturbed, doped, "wp1054_double_injection")


# ----------------------------------------------------------------------
# WP-1057: purpose-grade evidence — the Le Bail gap, the resolution-limited
# abstention flavour, and the contents-type intensity clause
# ----------------------------------------------------------------------
def _pore_proxy_data(seed=17):
    """Data from LaB₆ + a guest scatterer (O at the 1b site, occ 0.6,
    Biso 2.0) — the WP-1057 pore-content proxy.  The returned host model
    never contains the guest, so its intensity model is wrong in the
    interference-coupled way real pore contents are: at (½,½,½) the guest's
    phase factor is (−1)^(h+k+l), so per-reflection errors alternate in sign
    by parity — never a scale, ADP or texture signature."""
    structure, ins, _ = _truth(seed=seed)
    doped = structure.model_copy(deep=True)
    doped.phases[0].atoms.append(pr.Atom(
        label="Oguest", species="O",
        x=pr.Parameter(value=0.5), y=pr.Parameter(value=0.5),
        z=pr.Parameter(value=0.5),
        occ=pr.Parameter(value=0.6), biso=pr.Parameter(value=2.0)))
    tt = np.arange(18.0, 125.0, 0.02)
    grid = pr.PatternData(two_theta=tt.tolist(), intensity=[0.0] * len(tt))
    model = compile_model(doped, ins, grid, mode="rietveld")
    table = ParameterTable(doped, ins)
    y = model.evaluate(table.decode(table.x0()))
    rng = np.random.default_rng(seed)
    y_noisy = rng.poisson(np.maximum(y, 1.0) * _COUNT_SCALE) / _COUNT_SCALE
    data = pr.PatternData(
        two_theta=model.tt.tolist(), intensity=y_noisy.tolist(),
        sigma=np.sqrt(np.maximum(y, 1.0) / _COUNT_SCALE).tolist())
    return structure, ins, data


def test_pore_proxy_gap_and_contents_clause():
    """The WP-1057 headline scenario: a converged host fit over data whose
    scattering contents it lacks.  Measured (2026-08-12): Rwp 0.0405,
    GoF 2.97, partition Rwp 0.0170 → ratio 2.38; intensity carries 83 % of
    the misfit in 8 gated regions split 5+/3−, best angular template
    R² = 0.011.  The report must carry the gap and name the contents
    signature — and still invent no action, because none applies."""
    structure, ins, data = _pore_proxy_data()
    ref = pr.Refinement(structure, ins)
    result = ref.fit(data, plan="mccusker_default")
    report = ref.report()

    assert report.layer1_available, report.abstained_reason
    gap = report.lebail_gap
    assert gap is not None
    assert gap.rwp_rietveld == pytest.approx(result.statistics.rwp, rel=1e-6)
    assert gap.rwp_lebail < gap.rwp_rietveld
    assert gap.ratio > 2.0, gap                    # measured 2.38
    assert "Le Bail partition" in report.summary
    assert "intensity model carries the misfit" in report.summary

    # the contents-type clause names the pattern; the evidence stays where
    # it always was, in the gated per-region coefficients
    assert "alternate in sign" in report.summary
    assert "un-modelled scattering contents" in report.summary
    sig = [c.value for a in report.attribution if a.gates_passed
           for c in a.coefficients if c.kind == "intensity" and c.significant]
    assert sum(1 for v in sig if v > 0) >= 2, sig
    assert sum(1 for v in sig if v < 0) >= 2, sig

    # honest silence preserved: naming the inference must not manufacture
    # actions the closed vocabulary cannot express
    assert not [a for a in report.suggested_actions if a.active]

    _plot_state(ref.fitted_structure, ref.fitted_instrument, data,
                "wp1057_pore_proxy")


def test_broad_abstention_is_resolution_limited():
    """The broad-peak abstention names the data's resolution, not model
    error: gram failures dominate the tally (measured 12 of 12 failing
    regions, 5 failing nothing else at median local R² 0.957) and the gap
    stays flat (measured ratio 1.00 — the partition's peaks are displaced
    identically, so position misfit can never masquerade as an intensity
    story)."""
    structure, ins, data = _broad_truth(0.6)
    perturbed = ins.model_copy(deep=True)
    perturbed.zero_shift.value = 0.05

    report = _report_for(structure, perturbed, data)
    assert report.abstained_reason
    assert report.abstained_kind == "resolution_limited"
    assert "Resolution-limited" in report.abstained_reason
    assert "not evidence the model is wrong" in report.abstained_reason
    assert "indistinguishable" in report.abstained_reason

    assert report.lebail_gap is not None
    assert report.lebail_gap.ratio < LEBAIL_GAP_NOTABLE, report.lebail_gap
    assert "Le Bail partition" not in report.summary

    _plot_state(structure, perturbed, data, "wp1057_broad_resolution_limited")


def test_sharp_converged_reference_stays_silent(truth):
    """The no-noise control: a converged correct model gets the gap field
    (measured ratio 1.00 — the partition is not a noise-floor estimator, so
    ≲ 1 is the healthy reading) and neither summary clause, and no
    abstention kind."""
    structure, ins, data = truth
    report = _report_for(structure, ins, data)

    assert report.layer1_available and report.abstained_kind is None
    gap = report.lebail_gap
    assert gap is not None
    assert gap.ratio < LEBAIL_GAP_NOTABLE, gap
    assert "Le Bail partition" not in report.summary
    assert "alternate in sign" not in report.summary

    _plot_state(structure, ins, data, "wp1057_sharp_reference")


def test_wrong_cell_abstentions_classify_as_model_error(truth):
    """The classifier must never read a wrong cell as resolution-limited.
    The +0.4 % state fails the Gram gate in 8 of its 10 failing regions too
    — which is why gram dominance alone cannot separate the flavours — and
    classifies "immature" on the Rwp arm (0.72); a milder +0.1 % state
    (Rwp 0.33) abstains via the explained-fraction clause with widespread
    validity failures and defers to the position family: "unreadable", the
    reindex pointer leading, no resolution wording."""
    structure, ins, data = truth

    p = structure.model_copy(deep=True)
    p.phases[0].cell = pr.Cell.cubic(4.1568 * 1.004)
    report = _report_for(p, ins, data)
    assert report.abstained_kind == "immature"

    p2 = structure.model_copy(deep=True)
    p2.phases[0].cell = pr.Cell.cubic(4.1568 * 1.001)
    report2 = _report_for(p2, ins, data)
    assert report2.abstained_kind == "unreadable"
    assert "Resolution-limited" not in (report2.abstained_reason or "")
    assert any(a.kind == "reindex_or_recheck_cell"
               for a in report2.suggested_actions)


def test_lebail_gap_mechanics(truth):
    """The partition borrows the caller's model: mode and per-hkl buffers
    are flipped and must come back bit-exact (the model keeps serving the
    session).  In Le Bail mode the gap is absent for cause — None, never a
    fabricated 1.0."""
    from pxrdref.report import lebail_gap

    structure, ins, data = truth
    result, model, values = _result_for(structure, ins, data)
    y_before = model.evaluate(values)
    gap = lebail_gap(model, values, rwp_rietveld=result.statistics.rwp)
    assert gap is not None and gap.rwp_lebail > 0
    assert model.mode == "rietveld"
    assert all(cp.hkl_intensity is None for cp in model.phases)
    assert np.array_equal(model.evaluate(values), y_before)

    lb = compile_model(structure, ins, data, mode="lebail")
    assert lebail_gap(lb, values, rwp_rietveld=0.1) is None

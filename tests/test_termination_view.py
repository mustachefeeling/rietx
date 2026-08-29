"""The termination view (WP-1302): ``str(result)``, ``Refinement.summary()``,
``SeriesResult.summary()``.

A projection of fields the objects already carry, so these tests check
*shape and presence*, never a re-derivation of the numbers — those are
covered where they are computed (statistics, the report, data_support).
"""

from __future__ import annotations

import numpy as np
import pytest

import rietx as rx
from rietx import Instrument, PatternData
from rietx.model.forward import compile_model
from rietx.params.vector import ParameterTable
from rietx.schemas.common import Parameter
from rietx.schemas.instrument import BackgroundChebyshev
from tests.test_refine_synthetic import synthesize
from tests.test_schemas import make_lab6


def _instrument() -> Instrument:
    ins = Instrument.debye_scherrer(wavelength=0.4139)
    ins.background = BackgroundChebyshev.with_terms(4)
    return ins


def _fit(plan=None) -> tuple[rx.Refinement, rx.RefinementResult]:
    ref = rx.Refinement(make_lab6(), _instrument(), history=False)
    result = ref.fit(synthesize(), plan=plan or rx.RefinementPlan.mccusker_default())
    return ref, result


def _clean_fit() -> tuple[rx.Refinement, rx.RefinementResult]:
    """A protocol tuned to raise no diagnostic at all (WP-1302's acceptance:
    the three stop-condition lines survive an empty diagnostics list)."""
    structure = make_lab6()
    structure.phases[0].cell.a.value = 4.1566
    structure.phases[0].cell.b.value = 4.1566
    structure.phases[0].cell.c.value = 4.1566
    structure.phases[0].scale.value = 5e-4
    ins = Instrument.debye_scherrer(wavelength=0.4139)
    ins.geometry.goniometer_radius_mm = 217.5
    ins.profile.w.value = 5e-3
    ins.background = BackgroundChebyshev(
        coefficients=[Parameter(value=v) for v in [40.0, -6.0, 1.5]])

    tt = np.arange(3.0, 24.0, 0.005)
    pattern = PatternData(two_theta=tt.tolist(), intensity=np.zeros_like(tt).tolist())
    model = compile_model(structure, ins, pattern, mode="rietveld")
    table = ParameterTable(structure, ins)
    y = model.evaluate(table.decode(table.x0()))
    y = np.random.default_rng(3).poisson(np.maximum(y, 1.0)).astype(float)
    data = PatternData(two_theta=model.tt.tolist(), intensity=y.tolist())

    ref = rx.Refinement(structure, ins, history=False)
    plan = rx.RefinementPlan(stages=[
        rx.Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"]),
        rx.Stage("zero", ["instrument.zero_shift"]),
        rx.Stage("cell", ["phases.*.cell.*"]),
        rx.Stage("profile_w", ["instrument.profile.w"]),
    ])
    return ref, ref.fit(data, plan=plan)


# --------------------------------------------------------------- __str__
def test_str_result_has_one_section_per_stage_and_no_more():
    _ref, result = _fit()
    text = str(result)
    lines = text.splitlines()
    assert lines[0].startswith("RefinementResult:")
    for stage in result.stages:
        assert f"stage {stage.name}: {stage.status}" in text
    assert "max|Δθ|/esd=" in text  # last stage only
    assert text.count("max|Δθ|/esd=") == 1


def test_str_result_diagnostics_line_present_even_at_zero():
    _ref, result = _clean_fit()
    assert not result.diagnostics
    assert "diagnostics: none" in str(result)


def test_str_result_names_every_diagnostic_by_substring():
    _ref, result = _fit()
    assert result.diagnostics, "fixture stopped producing any — pick another"
    text = str(result)
    for d in result.diagnostics:
        assert f"{d.level.upper()} {d.code}: " in text
        assert d.message in text


def test_str_result_ends_with_provenance_then_agreement():
    _ref, result = _fit()
    lines = [ln for ln in str(result).splitlines() if ln.strip()]
    assert lines[-2].strip().startswith("provenance:")
    assert lines[-1].strip().startswith("Rwp ")


def test_str_result_is_a_pointer_not_an_alias_still_holds():
    """The new __str__ must not disturb Base.__getattr__'s own pinned
    behaviour (tests/test_schemas.py) — same object, two independent uses."""
    _ref, result = _fit()
    assert not hasattr(result, "rwp")
    str(result)  # must not raise, must not add anything to __dict__
    assert not hasattr(result, "rwp")


# ------------------------------------------------------- Refinement.summary
def test_summary_default_prints_the_three_stop_conditions_only():
    ref, _result = _fit()
    text = ref.summary()
    assert "diagnostics:" in text
    assert "layer0/1:" in text
    assert "next: run suggest" in text
    assert "deliverable:" not in text


def test_summary_the_three_stop_condition_lines_survive_zero_diagnostics():
    ref, result = _clean_fit()
    assert not result.diagnostics
    text = ref.summary()
    assert "diagnostics: none" in text
    assert "layer0/1:" in text
    assert "next: run suggest" in text


@pytest.mark.parametrize("deliverable", ["phase_id", "qpa", "structure"])
def test_summary_deliverable_adds_its_own_section(deliverable):
    ref, _result = _fit()
    text = ref.summary(deliverable=deliverable)
    assert f"deliverable: {deliverable}" in text


def test_summary_unknown_deliverable_raises():
    ref, _result = _fit()
    with pytest.raises(ValueError, match="unknown deliverable"):
        ref.summary(deliverable="not_a_real_one")


def test_summary_plot_writes_the_file_and_names_it(tmp_path):
    ref, _result = _fit()
    path = tmp_path / "fit.png"
    text = ref.summary(plot=str(path))
    assert path.exists()
    assert str(path) in text


def test_summary_without_plot_names_the_call_instead():
    ref, _result = _fit()
    text = ref.summary()
    assert "plot_for_vlm" in text or "summary(plot=" in text


def test_summary_before_fit_raises():
    ref = rx.Refinement(make_lab6(), _instrument(), history=False)
    with pytest.raises(RuntimeError, match="call fit"):
        ref.summary()


def test_summary_protocol_names_the_plan_and_held_reasons():
    ref, _result = _fit()
    text = ref.summary()
    assert "plan: scale_bkg, zero, cell, profile_w, profile" in text
    assert "held:" in text
    assert "σ source:" in text


def test_summary_under_120_lines_on_a_five_stage_plan():
    ref, _result = _fit()
    text = ref.summary(deliverable="qpa")
    assert len(text.splitlines()) < 120


def test_str_result_under_80_lines():
    _ref, result = _fit()
    assert len(str(result).splitlines()) < 80


# ---------------------------------------------------------- SeriesResult
def test_series_summary_shows_every_entry_under_the_cap():
    patterns = [synthesize(noise_seed=i) for i in (1, 2, 3)]
    res = rx.refine_sequential(
        patterns, make_lab6(), _instrument(), labels=["a", "b", "c"],
        plan=rx.RefinementPlan(stages=[
            rx.Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"],
                    max_iter=5)]))
    text = res.summary()
    for label in ("a", "b", "c"):
        assert f"] {label} " in text
    assert "…" not in text


def test_series_summary_truncates_a_long_series():
    patterns = [synthesize(noise_seed=i) for i in range(8)]
    res = rx.refine_sequential(
        patterns, make_lab6(), _instrument(),
        plan=rx.RefinementPlan(stages=[
            rx.Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"],
                    max_iter=5)]))
    text = res.summary(max_entries=2)
    assert "[1/8]" in text and "[8/8]" in text
    assert "[4/8]" not in text
    assert "4 more" in text


def test_series_str_is_summary():
    patterns = [synthesize(noise_seed=1)]
    res = rx.refine_sequential(
        patterns, make_lab6(), _instrument(),
        plan=rx.RefinementPlan(stages=[
            rx.Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"],
                    max_iter=5)]))
    assert str(res) == res.summary()


def test_series_summary_diagnostics_line_present_even_at_zero():
    patterns = [synthesize(noise_seed=1)]
    res = rx.refine_sequential(
        patterns, make_lab6(), _instrument(),
        plan=rx.RefinementPlan(stages=[
            rx.Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"],
                    max_iter=5)]))
    if not res.diagnostics:
        assert "diagnostics: none" in res.summary()

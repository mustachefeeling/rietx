"""The Γ_G² floor the LM driver holds at every reflection (WP-1938 D7).

``gaussian_fwhm`` clamps Γ_G² at ``caglioti._MIN_GAMMA_G2`` = 1e-8 deg², and
under the clamp every Gaussian width column is exactly zero.  LM's bounded
step lands W exactly on its floor of 0, so with U = V = 0 a stage freeing W
puts Γ_G² under the clamp at every point and stops there.  A synthetic LaB₆
pattern with NAC's widths reproduces it in a fraction of a second; the
inequality keeps Γ_G² at or above the clamp and LM lands on TRF's minimum.

obs/calc/diff PNGs of both LM fits go to ``tests/output/``.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

import rietx as rx
import rietx.optimize.least_squares as ls
from rietx import Instrument, PatternData, Refinement
from rietx.model.forward import compile_model
from rietx.model.profiles.caglioti import _MIN_GAMMA_G2, gaussian_fwhm
from rietx.params.vector import ParameterTable
from rietx.schemas.common import Parameter
from rietx.schemas.instrument import BackgroundChebyshev
from tests.test_schemas import make_lab6

OUT = Path(__file__).parent / "output"
WAVELENGTH = 0.4139
#: NAC's widths under TRF (11-BM), x rounded: a narrow Gaussian beside a
#: Lorentzian, so the start's W = 1e-3 is far too broad
TRUE = {"u": 9e-4, "v": -2e-4, "w": 2.5e-5, "x": 2e-3}
_B = ["phases.0.scale", "instrument.background.*"]
PLAN = rx.RefinementPlan(stages=[
    rx.Stage(name="scale", turn_on=_B),
    rx.Stage(name="profile_w", turn_on=_B + ["instrument.profile.w"]),
    rx.Stage(name="profile", turn_on=_B + ["instrument.profile.u",
                                           "instrument.profile.v",
                                           "instrument.profile.w",
                                           "instrument.profile.x"]),
])


def _models(true: bool):
    structure = make_lab6()
    structure.phases[0].scale.value = 5e-4
    ins = Instrument.debye_scherrer(wavelength=WAVELENGTH)
    if true:
        for name, value in TRUE.items():
            getattr(ins.profile, name).value = value
        ins.background = BackgroundChebyshev(coefficients=[Parameter(value=40.0)])
    else:
        ins.background = BackgroundChebyshev.with_terms(1)
    return structure, ins


@pytest.fixture(scope="module")
def pattern() -> PatternData:
    structure, ins = _models(true=True)
    tt = np.arange(3.0, 24.0, 0.005)
    blank = PatternData(two_theta=tt.tolist(), intensity=np.zeros_like(tt).tolist())
    model = compile_model(structure, ins, blank, mode="rietveld")
    table = ParameterTable(structure, ins)
    y = model.evaluate(table.decode(table.x0()))
    y = np.random.default_rng(7).poisson(np.maximum(y, 1.0)).astype(float)
    return PatternData(two_theta=model.tt.tolist(), intensity=y.tolist())


def _fit(pattern, solver):
    structure, ins = _models(true=False)
    ref = Refinement(structure, ins, solver=solver, history=False)
    return ref, ref.fit(pattern, plan=PLAN)


def _g2_at_reflections(ref, result) -> np.ndarray:
    """The raw Γ_G² at every tick, before ``gaussian_fwhm``'s clamp."""
    p = ref.instrument.profile
    t = np.tan(np.radians(0.5 * np.asarray(
        [x for ticks in result.ticks.values() for x in ticks])))
    return p.u.value * t * t + p.v.value * t + p.w.value


def _draw(result, stem: str) -> None:
    from rietx.viz.plots import plot_result

    OUT.mkdir(exist_ok=True)
    plot_result(result, path=str(OUT / f"{stem}.png"))
    plot_result(result, path=str(OUT / f"{stem}_zoom.png"), two_theta_range=(9.5, 12.5))


@pytest.fixture(scope="module")
def trf(pattern):
    return _fit(pattern, "trf")


def test_without_the_floor_lm_stops_under_the_clamp(pattern, trf, monkeypatch):
    """The trap the inequality exists for: it must still be reachable, or the
    test below proves nothing."""
    monkeypatch.setattr(ls, "gaussian_width_inequalities", lambda m, t, x: [])
    ref, result = _fit(pattern, "lm")
    _draw(result, "gaussian_width_floor_off_lm")
    assert np.all(_g2_at_reflections(ref, result) < _MIN_GAMMA_G2)
    assert all(s.n_constraint_truncations == 0 for s in result.stages)
    assert result.statistics.chi2 > 10.0 * trf[1].statistics.chi2


def test_the_floor_holds_and_lm_reaches_trfs_minimum(pattern, trf):
    ref, result = _fit(pattern, "lm")
    _draw(result, "gaussian_width_floor_lm")
    assert np.all(_g2_at_reflections(ref, result) >= _MIN_GAMMA_G2)
    profile_w = next(s for s in result.stages if s.name == "profile_w")
    assert profile_w.n_constraint_truncations >= 1
    ref_trf, result_trf = trf
    assert result.statistics.chi2 == pytest.approx(result_trf.statistics.chi2, rel=1e-8)
    for name in "uvwx":
        assert getattr(ref.instrument.profile, name).value == pytest.approx(
            getattr(ref_trf.instrument.profile, name).value, rel=1e-4), name
    # the answer is interior, so the final stage pressed nothing
    assert not any(d.code == "CONSTRAINT_ACTIVE" for d in result.diagnostics)


def test_a_pawley_fit_pads_the_rows_past_its_intensity_block(pattern):
    """The rows read the table, and a Pawley solve's vector also carries one
    intensity per reflection.  Unpadded, ``T·θ`` raised a shape error on
    every Pawley stage freeing a width, and on a Stephens block before D7."""
    structure, ins = _models(true=False)
    ref = Refinement(structure, ins, solver="lm", history=False)
    result = ref.fit(pattern, plan=PLAN, mode="pawley")
    assert result.status == "converged"
    assert np.all(_g2_at_reflections(ref, result) >= _MIN_GAMMA_G2)


def _stage_table(pattern, free: list[str], **widths):
    structure, ins = _models(true=False)
    for name, value in widths.items():
        getattr(ins.profile, name).value = value
    structure.phases[0].gauss_size.value = 2e-5
    structure.phases[0].gauss_strain.value = 3e-5
    model = compile_model(structure, ins, pattern, mode="rietveld")
    table = ParameterTable(structure, ins)
    table.set_vary(free, True)
    return model, table


def test_a_row_is_the_clamped_quantity_at_a_reflection(pattern):
    """T·θ + c is Γ_G² − ε, the quantity ``gaussian_fwhm`` clamps, with the
    phase's Gaussian size and strain in it."""
    model, table = _stage_table(
        pattern, ["instrument.profile.u", "instrument.profile.v",
                  "instrument.profile.w", "phases.0.gauss_size",
                  "phases.0.gauss_strain"], u=1e-4, v=-3e-5, w=4e-5)
    x0 = table.x0()
    (block,) = ls.gaussian_width_inequalities(model, table, x0)
    assert block.label == "instrument.profile (phases.0)"
    v = table.decode(x0)
    tt = np.asarray(model._cell_block(
        model.phases[0], tuple(v[f"phases.0.cell.{k}"] for k in
                               ("a", "b", "c", "alpha", "beta", "gamma")),
        model.line_lambdas(v))[1][0])
    on_data = model.phases[0].win[0][:, 1] > model.phases[0].win[0][:, 0]
    g = gaussian_fwhm(0.5 * tt[on_data], v["instrument.profile.u"],
                      v["instrument.profile.v"], v["instrument.profile.w"],
                      v["phases.0.gauss_size"], v["phases.0.gauss_strain"])
    expected = np.unique(np.round(np.asarray(g) ** 2 - _MIN_GAMMA_G2, 18))
    got = np.unique(np.round(block.slack(x0), 18))
    np.testing.assert_allclose(np.sort(got), np.sort(expected), rtol=1e-12)


def test_no_row_without_a_free_width_and_none_the_start_violates(pattern):
    model, table = _stage_table(pattern, ["instrument.profile.x"])
    assert ls.gaussian_width_inequalities(model, table, table.x0()) == []
    # U = V = W = 0 and no sample term: Γ_G² = 0 < ε everywhere, so every row
    # is violated at the start and none is built (feasibility is kept, never
    # restored)
    structure, ins = _models(true=False)
    ins.profile.w.value = 0.0
    model = compile_model(structure, ins, pattern, mode="rietveld")
    table = ParameterTable(structure, ins)
    table.set_vary(["instrument.profile.w"], True)
    assert ls.gaussian_width_inequalities(model, table, table.x0()) == []


def test_constraint_active_names_the_block_that_bound():
    from rietx.refine import _constraint_diagnostics

    (d,) = _constraint_diagnostics("profile", SimpleNamespace(
        n_constraint_truncations=2,
        truncated_by={"instrument.profile (phases.0)": 2}))
    assert "instrument.profile (phases.0): 2" in d.message
    assert "Γ_G² floor" in d.suggestion
    assert "STEPHENS" not in d.suggestion
    (d,) = _constraint_diagnostics("strain", SimpleNamespace(
        n_constraint_truncations=1, truncated_by={"phases.0.microstrain": 1}))
    assert "phases.0.microstrain: 1" in d.message
    assert "STEPHENS_STRAIN_NOT_POSITIVE" in d.suggestion
    assert "Γ_G² floor" not in d.suggestion

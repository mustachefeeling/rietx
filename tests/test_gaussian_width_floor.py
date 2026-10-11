"""The Γ_G² clamp, kept out of LM's reach two ways (WP-1938 D7, D8).

``gaussian_fwhm`` clamps Γ_G² at ``caglioti._MIN_GAMMA_G2`` = 1e-8 deg², and
under the clamp every Gaussian width column is exactly zero.  LM's bounded
step lands W exactly on its floor, so with the floor at 0 and U = V = 0 a
stage freeing W put Γ_G² under the clamp at every point and stopped there.  A
synthetic LaB₆ pattern with NAC's widths reproduces it in a fraction of a
second.  Two things now keep the clamp out of reach, and each is tested here
alone.  W's floor is the clamp itself.  And Γ_G² ≥ ε at every reflection is
a row of LM's linear inequalities
(``least_squares.gaussian_width_inequalities``), held inside the step since
D8, which also covers a negative U or V.

obs/calc/diff PNGs of the LM fits go to ``tests/output/``.
"""

from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

import rietx as rx
import rietx.optimize.least_squares as ls
from rietx import Instrument, PatternData, Refinement
from rietx.io.instrument_profile import read_gsas2_instprm, read_gsas_prm
from rietx.model.forward import compile_model
from rietx.model.profiles.caglioti import _MIN_GAMMA_G2, gaussian_fwhm
from rietx.params.vector import ParameterTable
from rietx.schemas.common import Parameter
from rietx.schemas.instrument import (
    TCHZ_BOUNDS,
    TCHZ_BOUNDS_COARSE,
    BackgroundChebyshev,
    ProfileTCHZ,
)
from tests.test_schemas import make_lab6

OUT = Path(__file__).parent / "output"
DATA = Path(__file__).parent / "data"
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


def _fit(pattern, solver, *, w_min=None):
    structure, ins = _models(true=False)
    if w_min is not None:
        # written on the Parameter itself, which ProfileTCHZ's validator does
        # not see: the only way left to put W's floor back at 0
        ins.profile.w.min = w_min
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


def test_with_w_bounded_at_zero_and_no_rows_lm_stops_under_the_clamp(
        pattern, trf, monkeypatch):
    """The trap both remedies exist for: it must still be reachable, or the
    tests below prove nothing."""
    monkeypatch.setattr(ls, "gaussian_width_inequalities", lambda m, t, x: [])
    ref, result = _fit(pattern, "lm", w_min=0.0)
    _draw(result, "gaussian_width_floor_off_lm")
    assert ref.instrument.profile.w.min == 0.0
    assert np.all(_g2_at_reflections(ref, result) < _MIN_GAMMA_G2)
    assert all(s.n_constraint_truncations == 0 for s in result.stages)
    assert result.statistics.chi2 > 10.0 * trf[1].statistics.chi2


def test_with_w_bounded_at_zero_the_rows_hold_and_lm_reaches_trfs_minimum(pattern, trf):
    """The rows alone, W's floor put back at 0: the ``profile_w`` stage
    presses Γ_G² onto ε at every reflection, and the step holds it there
    rather than truncating short of it (WP-1938 D8)."""
    ref, result = _fit(pattern, "lm", w_min=0.0)
    _draw(result, "gaussian_width_rows_lm")
    assert np.all(_g2_at_reflections(ref, result) >= _MIN_GAMMA_G2 * (1.0 - 1e-9))
    profile_w = next(s for s in result.stages if s.name == "profile_w")
    assert profile_w.n_constraint_truncations >= 1
    ref_trf, result_trf = trf
    assert result.statistics.chi2 == pytest.approx(result_trf.statistics.chi2, rel=1e-8)
    for name in "uvwx":
        assert getattr(ref.instrument.profile, name).value == pytest.approx(
            getattr(ref_trf.instrument.profile, name).value, rel=1e-4), name
    # the answer is interior, so the final stage pressed nothing
    assert not any(d.code == "CONSTRAINT_ACTIVE" for d in result.diagnostics)


@pytest.mark.parametrize("rows", [False, True], ids=["floor_alone", "default"])
def test_on_the_floor_lm_reaches_trfs_minimum(pattern, trf, monkeypatch, rows):
    if not rows:
        monkeypatch.setattr(ls, "gaussian_width_inequalities", lambda m, t, x: [])
    ref, result = _fit(pattern, "lm")
    _draw(result, "gaussian_width_floor_lm" if rows else "gaussian_width_floor_alone_lm")
    assert ref.instrument.profile.w.min == _MIN_GAMMA_G2
    assert np.all(_g2_at_reflections(ref, result) >= _MIN_GAMMA_G2)
    ref_trf, result_trf = trf
    assert result.statistics.chi2 == pytest.approx(result_trf.statistics.chi2, rel=1e-8)
    for name in "uvwx":
        assert getattr(ref.instrument.profile, name).value == pytest.approx(
            getattr(ref_trf.instrument.profile, name).value, rel=1e-4), name


def test_the_declared_boxes_start_at_the_clamp():
    assert TCHZ_BOUNDS["w"][0] == TCHZ_BOUNDS_COARSE["w"][0] == _MIN_GAMMA_G2
    assert ProfileTCHZ().w.min == _MIN_GAMMA_G2
    assert ProfileTCHZ.coarse().w.min == _MIN_GAMMA_G2


def test_a_stored_min_of_zero_opens_with_the_floor():
    """The ``MARCH_R_MIN`` precedent: the broken bound outlives the default.

    A project or history node written before the floor stores ``min: 0.0``,
    and W itself may sit on that 0, which is where the trap leaves it.
    """
    doc = Instrument.debye_scherrer(wavelength=WAVELENGTH).model_dump(mode="json")
    doc["profile"]["w"].update(value=0.0, min=0.0)
    w = Instrument.model_validate(doc).profile.w
    assert (w.value, w.min, w.max) == (_MIN_GAMMA_G2, _MIN_GAMMA_G2, 1.0)

    # a value above the floor is kept, and only the bound moves
    doc["profile"]["w"].update(value=2.5e-5, min=0.0)
    w = Instrument.model_validate(doc).profile.w
    assert (w.value, w.min) == (2.5e-5, _MIN_GAMMA_G2)


def test_a_callers_bound_under_the_floor_is_raised():
    profile = ProfileTCHZ(w=Parameter(value=-0.01, min=-1.0, max=1.0))
    assert (profile.w.value, profile.w.min) == (_MIN_GAMMA_G2, _MIN_GAMMA_G2)
    # an assignment re-runs the model's validators
    profile.w = Parameter(value=0.0, min=0.0, max=1.0)
    assert (profile.w.value, profile.w.min) == (_MIN_GAMMA_G2, _MIN_GAMMA_G2)


def test_a_files_w_of_zero_reads_onto_the_floor(tmp_path):
    """A reader writes W onto a built profile, which the validator does not
    see, so each lifts a W in [0, floor) itself.  A negative W stays refused."""
    text = (DATA / "gsas2_hb2a.instprm").read_text(encoding="utf-8")
    path = tmp_path / "w0.instprm"
    path.write_text(re.sub(r"^W:.*$", "W:0.0", text, flags=re.M), encoding="utf-8")
    w = read_gsas2_instprm(path).profile.w
    assert (w.value, w.min) == (_MIN_GAMMA_G2, _MIN_GAMMA_G2)

    text = (DATA / "11bm_gsas.prm").read_text(encoding="utf-8")
    # PRCF11's GV and GW fields, at their fixed columns
    gw = "      -0.126000       0.063000"
    assert gw in text
    for new, name in (("      -0.126000       0.000000", "w0.prm"),
                      ("      -0.126000      -0.063000", "wneg.prm")):
        (tmp_path / name).write_text(text.replace(gw, new, 1), encoding="utf-8")
    w = read_gsas_prm(tmp_path / "w0.prm").profile.w
    assert (w.value, w.min) == (_MIN_GAMMA_G2, _MIN_GAMMA_G2)
    with pytest.raises(ValueError, match="wneg.prm"):
        read_gsas_prm(tmp_path / "wneg.prm")


# ----------------------------------------------------------------------
# the rows (WP-1938 D7, held inside the step since D8)
# ----------------------------------------------------------------------
def test_a_pawley_fit_pads_the_rows_past_its_intensity_block(pattern):
    """The rows read the table, and a Pawley solve's vector also carries one
    intensity per reflection.  Unpadded, ``T·θ`` raised a shape error on
    every Pawley stage freeing a width."""
    structure, ins = _models(true=False)
    ins.profile.w.min = 0.0               # so the rows, not the floor, bind
    ref = Refinement(structure, ins, solver="lm", history=False)
    result = ref.fit(pattern, plan=PLAN, mode="pawley")
    _draw(result, "gaussian_width_rows_pawley_lm")
    assert result.status == "converged"
    assert np.all(_g2_at_reflections(ref, result) >= _MIN_GAMMA_G2 * (1.0 - 1e-9))


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


def test_a_reflection_only_its_magnetic_window_reaches_still_gets_a_row(pattern):
    """A magnetic component is drawn over its own, wider window (``win_mag``),
    and its Γ_G² is the nuclear one.  So a reflection whose nuclear window
    holds no data, beside an excluded region or the range's edge, can still
    put a magnetic peak on the data, and its row is built."""
    model, table = _stage_table(
        pattern, ["instrument.profile.u", "instrument.profile.v",
                  "instrument.profile.w"], u=1e-4, v=-3e-5, w=4e-5)
    cp = model.phases[0]

    def n_rows():
        (block,) = ls.gaussian_width_inequalities(model, table, table.x0())
        return len(block.c)

    every = n_rows()
    cp.win_mag = cp.win.copy()
    cp.win = cp.win.copy()
    cp.win[0][3, 1] = cp.win[0][3, 0]          # reflection 3's nuclear window, emptied
    assert n_rows() == every
    cp.win_mag = None
    assert n_rows() == every - 1


def test_no_row_without_a_free_width_and_none_the_start_violates(pattern):
    model, table = _stage_table(pattern, ["instrument.profile.x"])
    assert ls.gaussian_width_inequalities(model, table, table.x0()) == []

    def rows_at(v: float):
        structure, ins = _models(true=False)
        ins.profile.w.value = _MIN_GAMMA_G2
        ins.profile.v.value = v
        model = compile_model(structure, ins, pattern, mode="rietveld")
        table = ParameterTable(structure, ins)
        table.set_vary(["instrument.profile.w"], True)
        return ls.gaussian_width_inequalities(model, table, table.x0()), table.x0()

    # U = V = 0 with W on its floor sits exactly on every row, and is held
    (block,), x0 = rows_at(0.0)
    assert np.all(block.slack(x0) == 0.0)
    # a negative V and no sample term: Γ_G² < ε at every reflection, so every
    # row is violated at the start and none is built (feasibility is kept,
    # never restored)
    assert rows_at(-1e-4)[0] == []


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

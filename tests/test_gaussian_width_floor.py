"""The Caglioti W's floor is the Γ_G² clamp, not 0 (WP-1938 D7).

``gaussian_fwhm`` clamps Γ_G² at ``caglioti._MIN_GAMMA_G2`` = 1e-8 deg², and
under the clamp every Gaussian width column is exactly zero.  LM's bounded
step lands W exactly on its floor, so with the floor at 0 and U = V = 0 a
stage freeing W put Γ_G² under the clamp at every point and stopped there.  A
synthetic LaB₆ pattern with NAC's widths reproduces it in a fraction of a
second.  With W's floor at the clamp, LM lands on TRF's minimum.

obs/calc/diff PNGs of both LM fits go to ``tests/output/``.
"""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pytest

import rietx as rx
from rietx import Instrument, PatternData, Refinement
from rietx.io.instrument_profile import read_gsas2_instprm, read_gsas_prm
from rietx.model.forward import compile_model
from rietx.model.profiles.caglioti import _MIN_GAMMA_G2
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


def test_with_w_bounded_at_zero_lm_stops_under_the_clamp(pattern, trf):
    """The trap the floor exists for: it must still be reachable, or the
    test below proves nothing."""
    ref, result = _fit(pattern, "lm", w_min=0.0)
    _draw(result, "gaussian_width_floor_off_lm")
    assert ref.instrument.profile.w.min == 0.0
    assert np.all(_g2_at_reflections(ref, result) < _MIN_GAMMA_G2)
    assert result.statistics.chi2 > 10.0 * trf[1].statistics.chi2


def test_on_the_floor_lm_reaches_trfs_minimum(pattern, trf):
    ref, result = _fit(pattern, "lm")
    _draw(result, "gaussian_width_floor_lm")
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

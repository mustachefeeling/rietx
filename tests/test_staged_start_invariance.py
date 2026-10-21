"""Starts and a floor that stop changing the answer behind the closing stage (WP-2002).

The sixth round's Q2 (ruled 2026-10-21, option 3): every plan ends in a closing
stage at tight windows, and a staged plan's start test passes at 0.1 plain esd
(``stderr_uncorrected``).  The yardstick is the larger of the two arms' esds on
every row that is not a background coefficient (``test_window_domain._shift``).
Before the closing stage, the three starts below moved answers by up to 0.75 esd,
because the last stage computed on a model frozen wherever the earlier stages
stopped.  Each arm here is a whole fit through the shipped closing stage.

Measured on 2026-10-21 (macOS arm64, worktree venv ``[dev]``, compiled tier on,
dispersion declined by every fixture), the largest disagreement in plain esd:

===============================  ===========  ======  =====  ===========
start                            fluorapat.   cpd-1a  NAC    LaB6
===============================  ===========  ======  =====  ===========
Biso 0.5 against 1.5 Å²          0.000        0.070   0.000  9.36
``intermediate_ftol`` 1e-6/None  0.000        0.042   0.000  0.000
axial sizing floor 0.02/0.05     0.002        0.138   n/a    0.007
===============================  ===========  ======  =====  ===========

The axial sizing floor (``forward.AXIAL_SIZING_FLOOR``) sizes the windows and
FCJ nodes of a stage that frees S/L or H/L from zero.  At 0.02 a stage reaching
0.05 leaves 0.27 of the peak maximum and drops 19.5 % of a peak's area, and the
two floors' answers differed by 0.16 esd on cpd-1a before the closing stage.
The closing stage recompiles at the ratios reached, where the floor no longer
binds (the seventh round's Q2), and cuts the floor's reach from 0.229, 0.516
and 0.380 plain esd (LaB6, FAP, cpd-1a, both arms with no closing stage) to
0.007, 0.002 and 0.138.  cpd-1a still misses the bar on corundum's ``c``: its
``lines_axial`` stage frees S/L alone from zero, and one closing solve does not
undo the path, so it is a strict xfail and the floor stays at tier 3.  NAC is a
synchrotron pattern and refines no axial ratio.

LaB6's two Biso starts land in its two mirrored axial-divergence minima, S/L and
H/L exchanged, under every window setting (WP-2012), so it is a strict xfail.
cpd-1a's 0.070 is ``axial_sl`` and leaves a margin of 1.4.

The intermediate tolerance fails on one more configuration, kept as a strict
xfail: cpd-1a with zircon declared, a phase the sample lacks.  Both schedules
now hold the zircon's nine structural paths in the closing stage and report
``PHASE_UNCONSTRAINED``, so the hold no longer flips.  The answers still differ
by 0.185 esd on fluorite ``a``.  With every stage at 1e-9, an earlier stage lets
the unseen zircon's cell walk until it spends its 400-evaluation budget
(``STAGE_MAX_ITER``) before the closing stage holds it.  The shipped 1e-6 is the
arm that stays inside its budget.

The harmonic weight seed is measured on a synthetic constant-wavelength neutron
corundum with a known λ/2 line, the one family a harmonic has (the held-out
Nd₂Ru₂O₇ pair stays unused).  Seeds 0.001 and 0.3 against the shipped 0.01
agree to 0.003 esd at a true weight of 0.003 and to 0.001 at 0.05 (0.1 was
measured too, at 0.001), and at a true weight of 0, the case a caller who
declares a harmonic to look for one meets.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

import rietx as rx
from rietx.model import compiled
from rietx.model.forward import compile_model
from rietx.params.vector import ParameterTable
from rietx.schemas.instrument import HARMONIC_WEIGHT_SEED, BackgroundChebyshev
from tests import test_window_domain as w
from tests.test_acceptance_qpa_roundrobin import (
    DATA,
    corundum_phase,
    fluorite_phase,
    qarr_instrument,
    qpa_plan,
    seed_scales,
    zincite_phase,
    zircon_phase,
)

pytestmark = [pytest.mark.slow, pytest.mark.xdist_group("staged-start-invariance")]

OUT = Path(__file__).parent / "output"

#: the ruled bar for a staged plan's start test, in plain esd
ESD_BAR = 0.1

_MIRRORED = ("LaB6's two starts land in its mirrored S/L and H/L axial minima under "
             "every window setting (WP-2012): 9.36 esd on axial_sl")


def _plotted(result, tag: str) -> dict:
    OUT.mkdir(exist_ok=True)
    result.plot(path=str(OUT / f"staged_start_{tag}.png"))
    import matplotlib.pyplot as plt

    plt.close("all")
    return w._rows(result)


@pytest.fixture(scope="module", autouse=True)
def _compiled_tier_on():
    was = compiled.set_enabled(True)
    yield
    compiled.set_enabled(was)


def _fit(family: str, *, biso: float | None = None, ftol="shipped", tag: str = "") -> dict:
    data, st, ins, plan, kw = w._protocol(family)
    assert plan.closing_window_tol == 1e-3, "the acceptance protocols ride the shipped stage"
    if ftol != "shipped":
        plan.intermediate_ftol = ftol
    if biso is not None:
        for phase in st.phases:
            for atom in phase.atoms:
                atom.biso.value = biso
    result = rx.Refinement(st, ins, history=False).fit(data, plan=plan, **kw)
    assert result.stages[-1].name == "closing"
    return _plotted(result, f"{family}_biso{biso}_ftol{ftol}{tag}")


def _assert_within_bar(a: dict, b: dict, what: str):
    worst, path = w._shift(a, b, background=False)
    assert worst <= ESD_BAR, f"{what}: {worst:.3f} plain esd on {path} (bar {ESD_BAR})"


@pytest.mark.parametrize("family", [
    "fap", "cpd1a", "nac",
    pytest.param("lab6", marks=pytest.mark.xfail(strict=True, reason=_MIRRORED))])
def test_the_biso_start_does_not_change_the_answer(family):
    """``Atom.biso``'s start of 0.5 Å² against 1.5 on every atom."""
    _assert_within_bar(_fit(family, biso=0.5), _fit(family, biso=1.5),
                       f"{family}, Biso 0.5 against 1.5")


@pytest.mark.parametrize("family", ["fap", "cpd1a", "nac", "lab6"])
def test_the_intermediate_tolerance_does_not_change_the_answer(family):
    """``intermediate_ftol`` 1e-6 against every stage at the solver's 1e-9."""
    _assert_within_bar(_fit(family), _fit(family, ftol=None),
                       f"{family}, intermediate_ftol 1e-6 against None")


@pytest.mark.parametrize("family", [
    "lab6", "fap",
    pytest.param("cpd1a", marks=pytest.mark.xfail(strict=True, reason=(
        "0.138 plain esd on corundum's cell c behind the closing stage (0.380 on the "
        "corundum scale without it): the lines_axial stage frees S/L from zero, and "
        "one closing solve does not undo the path (measured 2026-10-21)")))])
def test_the_axial_sizing_floor_does_not_change_the_answer(family, monkeypatch):
    """``AXIAL_SIZING_FLOOR`` 0.02 against 0.05, the value its domain test
    passes at (``tests/test_lab_instrument.py``), on the three lab protocols
    that refine the axial ratios.  Made to fail on 2026-10-21 by running both
    arms with ``closing_window_tol=None`` (a scratch probe of this comparison):
    0.229 esd on LaB6's ``x`` and 0.516 on the fluorapatite ``lor_size``."""
    import rietx.model.forward as fwd

    shipped = _fit(family)
    monkeypatch.setattr(fwd, "AXIAL_SIZING_FLOOR", 0.05)
    _assert_within_bar(shipped, _fit(family, tag="_axialfloor0.05"),
                       f"{family}, AXIAL_SIZING_FLOOR 0.02 against 0.05")


@pytest.mark.xfail(strict=True, reason=(
    "an absent zircon's cell walks to the stage budget when every stage runs at 1e-9, "
    "0.185 esd on fluorite a; the module docstring has the reading"))
def test_the_intermediate_tolerance_with_an_absent_phase_declared():
    def fit(tol):
        data = rx.read_pattern(DATA / "cpd-1a.prn")
        st = rx.Structure(phases=[corundum_phase(), zincite_phase(), fluorite_phase(),
                                  zircon_phase()])
        ins = qarr_instrument()
        seed_scales(st, ins, data)
        plan = qpa_plan()
        plan.intermediate_ftol = tol
        result = rx.Refinement(st, ins, history=False).fit(data, plan=plan)
        held = [p for p in result.stages[-1].held if p.startswith("phases.3.")]
        assert len(held) == 9, "the closing stage holds the unseen zircon either way"
        return _plotted(result, f"cpd1a_zircon_ftol{tol}")

    _assert_within_bar(fit(1e-6), fit(None), "cpd-1a with zircon, 1e-6 against None")


# --- the harmonic weight seed, on a synthetic neutron corundum ----------------------
_LAM = 1.5
_LIMITS = (5.0, 155.0)


def _neutron(weight: float) -> rx.Instrument:
    ins = rx.Instrument.constant_wavelength_neutron(_LAM, fwhm_deg=0.30, harmonics=[2])
    ins.source.harmonics[0].weight.value = weight
    return ins


def _synthetic(true_weight: float):
    """Corundum with a λ/2 line at ``true_weight``, its strongest peak 20 000
    counts over a flat 600, Poisson noise at a fixed seed."""
    st = rx.Structure(phases=[corundum_phase()])
    ins = _neutron(true_weight)
    ins.background = BackgroundChebyshev(
        coefficients=[rx.Parameter(value=v) for v in (600.0, -40.0, 12.0)])
    tt = np.arange(_LIMITS[0], _LIMITS[1] + 1e-9, 0.05)
    blank = rx.PatternData(two_theta=tt.tolist(), intensity=np.zeros_like(tt).tolist())
    st.phases[0].scale.value = 1.0
    unit = compile_model(st, ins, blank, mode="rietveld")
    table = ParameterTable(st, ins)
    y = unit.evaluate(table.decode(table.x0()))
    scale = 20000.0 / max(float(np.max(y) - 600.0), 1e-9)
    st.phases[0].scale.value = scale
    model = compile_model(st, ins, blank, mode="rietveld")
    table = ParameterTable(st, ins)
    y = model.evaluate(table.decode(table.x0()))
    counts = np.random.default_rng(11).poisson(np.maximum(y, 1.0)).astype(float)
    return rx.PatternData(two_theta=model.tt.tolist(), intensity=counts.tolist()), scale


def _harmonic_fit(pattern, scale: float, seed: float) -> dict:
    st = rx.Structure(phases=[corundum_phase()])
    st.phases[0].scale.value = scale * 0.8
    st.phases[0].cell.a.value *= 1.0005
    st.phases[0].cell.c.value *= 1.0005
    for atom in st.phases[0].atoms:
        atom.biso.value = 0.5
    ins = _neutron(seed)
    ins.background = BackgroundChebyshev.with_terms(6)
    ins.background.coefficients[0].value = 500.0
    base = rx.RefinementPlan.mccusker_structural()
    plan = rx.RefinementPlan(stages=[
        *base.stages, rx.Stage("harmonic", ["instrument.source.lines.*.weight"])])
    result = rx.Refinement(st, ins, history=False).fit(pattern, plan=plan,
                                                        two_theta_limits=_LIMITS)
    assert result.stages[-1].name == "closing"
    return _plotted(result, f"harmonic_seed{seed}")


@pytest.mark.parametrize("true_weight", [0.0, 0.003, 0.05])
def test_the_harmonic_seed_does_not_change_the_answer(true_weight):
    assert HARMONIC_WEIGHT_SEED == 0.01
    pattern, scale = _synthetic(true_weight)
    shipped = _harmonic_fit(pattern, scale, HARMONIC_WEIGHT_SEED)
    for seed in (0.001, 0.3):
        _assert_within_bar(shipped, _harmonic_fit(pattern, scale, seed),
                           f"true weight {true_weight}, seed 0.01 against {seed}")

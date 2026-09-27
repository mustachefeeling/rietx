"""WP-1320: a phase fraction the pattern cannot fix.

A trace phase's scale trades against its width.  Broadened far enough, its
peaks become a hump the background shares, and its scale can then grow at
almost no χ² cost, so the χ² surface along that ridge can hold separate basins
at one χ², each with ordinary curvature and a tight esd.  The fit reports
whichever it reached, and the esd — the curvature *there* — cannot see the
other.  Issue #203 measured it on a lab in-situ pattern (1.41 ± 0.65 wt%
against basins at 0 %, ~1.5 % and 98.7 % within 0.011 pp of Rwp); that data
is not in the repository, so the fixture here is synthetic.

**The fixture.**  LaB₆ with a trace of CaF₂ under lab Cu Kα, plus a 10-count
amorphous hump that the fitted six-term Chebyshev cannot follow.  A stiff
background is what recruits a phase smeared into a hump as extra background,
which is what puts the absurd basin at the same χ² as the true one.  The
**control** drops the hump and carries five times the CaF₂, the shape of
#203's 200 °C pattern: one minimum.

**Verified before anything asserts on it** — the width profile is run by hand,
at a sharp width, a barrier width and a hump-sized width, with the docs'
recipe (``docs/skill/rietx/references/judging.md`` § "a trace phase's esd
describes one basin"), whose numbers are this module's.
"""

from pathlib import Path

import numpy as np
import pytest

import rietx as rx
from rietx import Instrument, PatternData
from rietx.model.forward import compile_model
from rietx.params.vector import ParameterTable
from rietx.schemas.common import Parameter
from rietx.schemas.instrument import BackgroundChebyshev
from rietx.schemas.structure import Atom, Cell, Phase, Structure
from rietx.strategy.staged import RefinementPlan, Stage

pytestmark = pytest.mark.xdist_group("qpa-multimodal")

OUT = Path(__file__).parent / "output"
TWO_THETA = np.arange(15.0, 100.0, 0.02)
TRUE_BACKGROUND = (200.0, -60.0, 20.0)
#: (height in counts, centre and FWHM in degrees 2θ) — an amorphous hump
HUMP = (10.0, 30.0, 15.0)
TRACE_SCALE = 2e-6          # CaF₂ at ~1 wt% of the crystalline content
CONTROL_SCALE = 1e-5        # five times more, and no hump: one basin
FITTED_BACKGROUND_TERMS = 6
AXIS = "phases.1.lor_strain"
#: the Δχ² for one parameter at 95 %, before the χ²_red·f² scaling
DCHI2_95 = 3.84
FREE = ["phases.*.scale", "phases.*.cell.*", "instrument.background.*",
        "instrument.zero_shift", "instrument.profile.w", "phases.*.lor_strain"]
PLAN = RefinementPlan(stages=[
    Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"]),
    Stage("cell", ["phases.*.cell.*", "instrument.zero_shift"]),
    Stage("width", FREE),
])


def _p(value: float) -> Parameter:
    return Parameter(value=value)


def _models(trace_scale: float, n_background: int) -> tuple[Structure, Instrument]:
    lab6 = Phase(name="LaB6", space_group="P m -3 m", cell=Cell.cubic(4.1566),
                 atoms=[Atom(label="La", species="La", x=_p(0.0), y=_p(0.0), z=_p(0.0)),
                        Atom(label="B", species="B", x=_p(0.1993), y=_p(0.5), z=_p(0.5))])
    caf2 = Phase(name="CaF2", space_group="F m -3 m", cell=Cell.cubic(5.4631),
                 atoms=[Atom(label="Ca", species="Ca2+", x=_p(0.0), y=_p(0.0), z=_p(0.0)),
                        Atom(label="F", species="F1-", x=_p(0.25), y=_p(0.25), z=_p(0.25))])
    structure = Structure(phases=[lab6, caf2])
    structure.phases[0].scale.value = 1e-3
    structure.phases[1].scale.value = trace_scale
    structure.phases[0].lor_strain.value = 0.02
    structure.phases[1].lor_strain.value = 0.05
    instrument = Instrument.bragg_brentano(radiation="CuKa")
    coefficients = list(TRUE_BACKGROUND) + [0.0] * (n_background - len(TRUE_BACKGROUND))
    instrument.background = BackgroundChebyshev(
        coefficients=[_p(v) for v in coefficients])
    return structure, instrument


def _synthesize(trace_scale: float, hump) -> PatternData:
    structure, instrument = _models(trace_scale, len(TRUE_BACKGROUND))
    blank = PatternData(two_theta=TWO_THETA.tolist(),
                        intensity=np.zeros_like(TWO_THETA).tolist())
    model = compile_model(structure, instrument, blank, mode="rietveld")
    table = ParameterTable(structure, instrument)
    y = model.evaluate(table.decode(table.x0()))
    tt = np.asarray(model.tt)
    if hump is not None:
        height, centre, fwhm = hump
        y = y + height * np.exp(-4.0 * np.log(2.0) * ((tt - centre) / fwhm) ** 2)
    y = np.random.default_rng(3).poisson(np.maximum(y, 1.0)).astype(float)
    return PatternData(two_theta=tt.tolist(), intensity=y.tolist())


def _fitted(trace_scale: float, hump):
    data = _synthesize(trace_scale, hump)
    ref = rx.Refinement(*_models(trace_scale, FITTED_BACKGROUND_TERMS))
    result = ref.fit(data, plan=PLAN, telemetry=False)
    return ref, result, data


@pytest.fixture(scope="module")
def multimodal():
    return _fitted(TRACE_SCALE, HUMP)


@pytest.fixture(scope="module")
def control():
    return _fitted(CONTROL_SCALE, None)


def _data_chi2(result) -> float:
    """The data's own χ², Σ w·Δ² — ``statistics.chi2`` is reduced."""
    st = result.statistics
    return st.chi2 * (st.n_points - st.n_free_parameters)


def _cut(result) -> float:
    """95 % Δχ² scaled by the calibration every esd already carries."""
    st = result.statistics
    return DCHI2_95 * st.chi2 * st.esd_inflation ** 2


def _pinned(ref, data, values):
    """The docs' width profile, on a branch: (value, W, χ², result) per value."""
    trial = ref.branch()
    trial.set_vary([AXIS], False)
    rows = []
    for value in values:
        trial.set_values({AXIS: value})
        r = trial.run_stage(data, rx.Stage("width_pin", []), telemetry=False)
        rows.append((value, r.qpa.phases[1].weight_fraction, _data_chi2(r), r))
    return rows


def test_the_trace_fixture_has_two_basins_at_one_chi2(multimodal):
    """A sharp basin and a hump basin, both admissible, a barrier between."""
    ref, result, data = multimodal
    sharp, barrier, hump = _pinned(ref, data, [0.03, 10.0, 80.0])
    best = min(sharp[2], barrier[2], hump[2], _data_chi2(result))
    cut = _cut(result)
    assert sharp[2] - best <= cut
    assert hump[2] - best <= cut
    assert barrier[2] - best > cut, "no barrier: one ridge, not two basins"
    assert sharp[1] < 0.03 < 0.5 < hump[1], (sharp[1], hump[1])
    OUT.mkdir(exist_ok=True)
    result.plot(path=str(OUT / "qpa_multimodal_fit.png"))
    hump[3].plot(path=str(OUT / "qpa_multimodal_hump_basin.png"))


def test_the_fit_reports_the_sharp_basin_with_a_tight_esd_and_no_finding(multimodal):
    """The premise: a confident point, and nothing that points at the phase."""
    _, result, _ = multimodal
    row = result.qpa.phases[1]
    assert row.weight_fraction == pytest.approx(0.0119, abs=0.0005)
    assert row.weight_fraction_stderr == pytest.approx(0.0053, abs=0.0005)
    naming = [d.code for d in result.diagnostics
              if any("CaF2" in w or w.startswith("phases.1.") for w in d.where)]
    assert not naming, naming


def test_the_control_has_one_basin(control):
    """No hump and five times the trace: the hump-sized width is excluded."""
    ref, result, data = control
    sharp, barrier, hump = _pinned(ref, data, [0.03, 10.0, 80.0])
    best = min(sharp[2], barrier[2], hump[2], _data_chi2(result))
    cut = _cut(result)
    assert sharp[2] - best <= cut
    assert barrier[2] - best > 10 * cut
    assert hump[2] - best > 10 * cut
    OUT.mkdir(exist_ok=True)
    result.plot(path=str(OUT / "qpa_multimodal_control_fit.png"))

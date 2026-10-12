"""A tick sits where the forward model draws its peak (WP-1908).

``RefinementResult.ticks`` placed each reflection at its Bragg angle plus the
zero shift and nothing else.  The forward model also applies the geometry's own
position shift: sample displacement and transparency on a flat plate, the two
capillary offsets on a capillary.  A fit with a refined displacement therefore
drew its ticks off its own peaks, by 2·s·cosθ/R, while the calculated curve
sat on the data.  Measured on IUCr CPD sample 1c under the acceptance suite's
``qpa_plan``, the fit's displacement refined to -0.81 mm and every tick sat
0.50° from the peak it labelled.

The oracle here is the calculated curve, never the shift formula.  A tick is
right when it lies at the apex of the peak the model drew, so a test that
re-derived the shift from the same expression would certify the shift and not
the tick.  Peaks are noise-free and narrow, so the apex of a three-point
parabola on the 0.01 deg grid is good to well under the 0.01 deg bar.

Three builders owe the same answer and each has a test: the single-histogram
result (``refine._build_result``), the joint runner's
(``multi.MultiHistogramRefinement._ticks``) and the live view's
(``viz.snapshot.stage_ticks``).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

import rietx as rx
from rietx.model.forward import compile_model
from rietx.params.vector import ParameterTable
from rietx.schemas.common import Parameter
from rietx.schemas.instrument import CAPILLARY_OFFSETS, Instrument
from rietx.schemas.pattern import PatternData
from rietx.schemas.structure import Atom, Cell, Phase, Structure
from rietx.strategy.staged import RefinementPlan, Stage
from rietx.viz.snapshot import stage_ticks

OUT = Path(__file__).parent / "output"

#: the bar the WP states: a tick within a hundredth of a degree of its peak
BAR_DEG = 0.01
DISPLACEMENT_PATH = "instrument.geometry.sample_displacement"
TT_GRID = np.arange(20.0, 120.0, 0.01)


def _rutile() -> Structure:
    return Structure(phases=[Phase(
        name="rutile", space_group="P42/mnm",
        cell=Cell(a=Parameter(value=4.5937, min=0.1),
                  b=Parameter(value=4.5937, min=0.1),
                  c=Parameter(value=2.9587, min=0.1),
                  alpha=Parameter(value=90.0), beta=Parameter(value=90.0),
                  gamma=Parameter(value=90.0)),
        atoms=[Atom(label="Ti", species="Ti", x=Parameter(value=0.0),
                    y=Parameter(value=0.0), z=Parameter(value=0.0),
                    biso=Parameter(value=0.5, min=0.0, max=25.0)),
               Atom(label="O", species="O", x=Parameter(value=0.3053),
                    y=Parameter(value=0.3053), z=Parameter(value=0.0),
                    biso=Parameter(value=0.6, min=0.0, max=25.0))],
        scale=Parameter(value=8e-3, min=0.0, transform="softplus"))])


def _flat_plate(*, radiation: str = "CuKa1", displacement: float = 0.0,
                transparency: float = 0.0) -> Instrument:
    ins = rx.Instrument.bragg_brentano(radiation=radiation)
    ins.source.dispersion = None      # declined, not inherited (CLAUDE.md)
    ins.profile.w.value = 4e-3
    ins.profile.x.value = 2e-3
    ins.geometry.sample_displacement.value = displacement
    ins.geometry.sample_transparency.value = transparency
    return ins


def _capillary(along: float, across: float) -> Instrument:
    ins = Instrument.debye_scherrer(wavelength=1.5406,
                                    goniometer_radius_mm=200.0)
    ins.source.dispersion = None
    ins.profile.w.value = 4e-3
    ins.profile.x.value = 2e-3
    getattr(ins.geometry, CAPILLARY_OFFSETS[0]).value = along
    getattr(ins.geometry, CAPILLARY_OFFSETS[1]).value = across
    return ins


def _simulate(ins: Instrument, structure: Structure | None = None
              ) -> PatternData:
    """A noise-free pattern drawn by the forward model itself, on a flat floor."""
    structure = structure or _rutile()
    empty = PatternData(two_theta=TT_GRID.tolist(),
                        intensity=np.zeros_like(TT_GRID).tolist())
    model = compile_model(structure, ins, empty, mode="rietveld")
    table = ParameterTable(structure, ins)
    y = np.asarray(model.evaluate(table.decode(table.x0()))) + 50.0
    return PatternData(two_theta=model.tt.tolist(), intensity=y.tolist())


def _apex(tt: np.ndarray, y: np.ndarray, centre: float, half: float):
    """The top of the peak nearest ``centre``, parabola through three points."""
    window = (tt > centre - half) & (tt < centre + half)
    if window.sum() < 5:
        return None
    i = int(np.argmax(np.where(window, y, -np.inf)))
    if i == 0 or i == len(tt) - 1:
        return None
    y0, y1, y2 = y[i - 1], y[i], y[i + 1]
    curvature = y0 - 2.0 * y1 + y2
    step = tt[1] - tt[0]
    return tt[i] + (0.5 * (y0 - y2) / curvature * step if curvature else 0.0)


def _tick_offsets(tt, y_calc, ticks, *, half=0.25, isolation=0.3,
                  lo=None, hi=None, floor=60.0):
    """Apex minus tick, for every tick that sits alone and on a visible peak.

    A tick is judged only when no other tick lies within ``isolation`` of it,
    so a neighbour's apex cannot be mistaken for its own, and only when the
    calculated curve rises ``floor`` above the 50-count floor there, so a
    forbidden-by-intensity reflection with no peak is not asked for one.
    """
    tt, y_calc, ticks = (np.asarray(v, dtype=float) for v in (tt, y_calc, ticks))
    out = []
    for k, c in enumerate(ticks):
        if (lo is not None and c < lo) or (hi is not None and c > hi):
            continue
        if np.min(np.abs(np.delete(ticks, k) - c)) < isolation:
            continue
        apex = _apex(tt, y_calc, c, half)
        if apex is None:
            continue
        if y_calc[np.argmin(np.abs(tt - apex))] < 50.0 + floor:
            continue
        out.append((c, apex - c))
    return np.array(out)


def _first_phase_ticks(result) -> list[float]:
    return result.ticks["rutile"]


def _plot_with_zoom(result, stem: str, zoom: tuple[float, float]) -> None:
    """Save the obs/calc/diff panel and a zoom on one peak with its tick."""
    import matplotlib.pyplot as plt

    OUT.mkdir(exist_ok=True)
    result.plot(path=str(OUT / f"{stem}.png"))
    result.plot(path=str(OUT / f"{stem}_zoom.png"), two_theta_range=zoom)
    plt.close("all")


# ----------------------------------------------------------------------
# the acceptance case: a fitted 0.5 mm displacement
# ----------------------------------------------------------------------
def _fit_displaced(radiation: str, truth_mm: float = 0.5):
    data = _simulate(_flat_plate(radiation=radiation, displacement=truth_mm))
    ref = rx.Refinement(_rutile(), _flat_plate(radiation=radiation))
    plan = RefinementPlan(stages=[
        Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"]),
        Stage("displacement", [DISPLACEMENT_PATH]),
        Stage("cell", ["phases.*.cell.*"]),
    ])
    return ref.fit(data, plan=plan)


def test_every_tick_lies_on_its_peak_after_a_fitted_displacement():
    """The WP's acceptance, on a pattern whose displacement is 0.5 mm.

    Before the fix every tick sat 0.14° (at 117°) to 0.26° (at 27°) above its
    peak: the displacement shift is -2·s·cosθ/R, and the ticks lacked it.
    """
    result = _fit_displaced("CuKa1")
    fitted = {p.path: p.value for p in result.parameters}
    assert fitted[DISPLACEMENT_PATH] == pytest.approx(0.5, abs=1e-3)

    rows = _tick_offsets(result.two_theta, result.y_calc,
                         _first_phase_ticks(result), half=0.4, isolation=0.9)
    assert len(rows) >= 15, "too few isolated peaks for the claim to mean much"
    worst = float(np.max(np.abs(rows[:, 1])))
    assert worst < BAR_DEG, (
        f"a tick sits {worst:.4f} deg from its peak (bar {BAR_DEG}); the "
        f"uncorrected offset on this case is 0.14-0.26 deg")
    # and they cover the whole range, not only where the shift is small
    assert rows[:, 0].min() < 40.0 and rows[:, 0].max() > 100.0

    _plot_with_zoom(result, "tick_positions_displaced",
                    (26.5, 28.0))


def test_a_kalpha2_tick_takes_its_own_lines_shift():
    """Each emission line has its own θ, so each tick has its own shift.

    A doublet resolves above 100° (0.46° apart at 117°), so there each line's
    peak can be found and its tick compared with it.  Two reflections resolve
    on this pattern, so four ticks: both lines of each are judged.
    """
    result = _fit_displaced("CuKa")
    rows = _tick_offsets(result.two_theta, result.y_calc,
                         _first_phase_ticks(result), half=0.25,
                         isolation=0.3, lo=100.0, hi=120.0)
    assert len(rows) >= 4, f"{len(rows)} resolved lines is too few to cover both"
    # the pairs really are Kα1/Kα2 of one reflection, 0.4-0.5° apart
    gaps = np.diff(rows[:, 0])
    assert np.any((gaps > 0.4) & (gaps < 0.5))
    worst = float(np.max(np.abs(rows[:, 1])))
    assert worst < BAR_DEG, f"a tick sits {worst:.4f} deg from its line's peak"


# ----------------------------------------------------------------------
# every geometry's own shift, by the live view's builder and the result's
# ----------------------------------------------------------------------
GEOMETRIES = [
    pytest.param(lambda: _flat_plate(displacement=0.5), id="displacement"),
    pytest.param(lambda: _flat_plate(transparency=0.004), id="transparency"),
    pytest.param(lambda: _capillary(0.4, -0.3), id="capillary"),
]


@pytest.mark.parametrize("make_instrument", GEOMETRIES)
def test_the_live_views_ticks_follow_every_geometry(make_instrument):
    """``stage_ticks`` is the third builder, so it is held to the same oracle.

    No fit: the model is evaluated at the values it was built with, which is
    exactly the picture ``plot_pattern(model=...)`` draws before any fit.
    """
    ins = make_instrument()
    structure = _rutile()
    data = _simulate(ins, structure)
    model = compile_model(structure, ins, data, mode="rietveld")
    table = ParameterTable(structure, ins)
    values = table.decode(table.x0())
    y_calc = np.asarray(model.evaluate(values)) + 50.0
    ticks = stage_ticks(model, values)["phase 0"]["two_theta"]

    rows = _tick_offsets(model.tt, y_calc, ticks, half=0.5, isolation=1.0)
    assert len(rows) >= 10
    worst = float(np.max(np.abs(rows[:, 1])))
    assert worst < BAR_DEG, f"a live-view tick sits {worst:.4f} deg from its peak"


@pytest.mark.parametrize("make_instrument", GEOMETRIES)
def test_a_result_places_its_ticks_by_every_geometry(make_instrument):
    """The result's builder, on the geometries a plan can leave nonzero.

    The fit frees only the scale and background, so the geometry stays at the
    value it was declared with and the ticks must carry it from there.
    """
    ins = make_instrument()
    data = _simulate(ins)
    plan = RefinementPlan(stages=[Stage(
        "scale_bkg", ["phases.*.scale", "instrument.background.*"])])
    result = rx.Refinement(_rutile(), ins).fit(data, plan=plan)

    rows = _tick_offsets(result.two_theta, result.y_calc,
                         _first_phase_ticks(result), half=0.5, isolation=1.0)
    assert len(rows) >= 10
    worst = float(np.max(np.abs(rows[:, 1])))
    assert worst < BAR_DEG, f"a result tick sits {worst:.4f} deg from its peak"


# ----------------------------------------------------------------------
# the joint runner's own builder
# ----------------------------------------------------------------------
def test_the_joint_runners_ticks_follow_each_histograms_displacement():
    """``multi`` keeps its own tick builder, so it owes the same position.

    Two histograms of one specimen carrying different displacements: a tick
    list shared between them, or one that read the wrong histogram's shift,
    would be off by the difference.
    """
    truths = (0.5, -0.3)
    patterns = [_simulate(_flat_plate(displacement=s)) for s in truths]
    instruments = [_flat_plate(displacement=s) for s in truths]
    plan = RefinementPlan(stages=[Stage(
        "scale_bkg", ["phases.*.scale", "instrument.background.*"])])
    result = rx.MultiHistogramRefinement(_rutile(), instruments).fit(
        patterns, plan=plan)

    for h, hist in enumerate(result.histograms):
        rows = _tick_offsets(hist.two_theta, hist.y_calc,
                             hist.ticks["rutile"], half=0.4, isolation=0.9)
        assert len(rows) >= 10, h
        worst = float(np.max(np.abs(rows[:, 1])))
        assert worst < BAR_DEG, (
            f"histogram {h}: a tick sits {worst:.4f} deg from its peak")


# ----------------------------------------------------------------------
# what the fix leaves alone
# ----------------------------------------------------------------------
def test_a_zero_displacement_leaves_the_ticks_at_bragg_plus_zero():
    """With no geometry shift the new method must reduce to the old sum.

    An additive correction that moved a default would be a silent change to
    every stored project's ticks.
    """
    ins = _flat_plate()
    ins.zero_shift.value = 0.03
    structure = _rutile()
    data = _simulate(ins)
    model = compile_model(structure, ins, data, mode="rietveld")
    table = ParameterTable(structure, ins)
    values = table.decode(table.x0())
    cp = model.phases[0]
    cell = tuple(values[f"phases.0.cell.{k}"]
                 for k in ("a", "b", "c", "alpha", "beta", "gamma"))
    lam = model.line_wavelengths[0]
    bragg = cp.reflections.two_theta(cell, lam)
    ticks = stage_ticks(model, values, max_per_phase=10**9)["phase 0"]["two_theta"]
    expected = np.sort(bragg[np.isfinite(bragg)] + 0.03)
    assert np.allclose(ticks, expected, atol=1e-5, rtol=0.0)


def test_the_satellite_arms_lattice_follows_the_ticks_geometry():
    """``report.satellites`` places its own positions and owes the ticks' answer.

    The reciprocal lattice contains every allowed reflection, so each tick must
    lie on a lattice position.  The arm added the zero alone, which left every
    lattice and satellite position 0.14-0.26 deg from the peak a displaced
    specimen drew, and the residual peak it was matched against.
    """
    from rietx.report.satellites import _lattice_positions

    ins = _flat_plate(displacement=0.5)
    structure = _rutile()
    data = _simulate(ins, structure)
    model = compile_model(structure, ins, data, mode="rietveld")
    table = ParameterTable(structure, ins)
    values = table.decode(table.x0())
    ticks = np.asarray(
        stage_ticks(model, values, max_per_phase=10**9)["phase 0"]["two_theta"])
    lattice = np.sort(_lattice_positions(model, values, 0))
    nearest = np.min(np.abs(ticks[:, None] - lattice[None, :]), axis=1)
    assert nearest.max() < 1e-4, (
        f"a tick sits {nearest.max():.4f} deg from the nearest lattice position")

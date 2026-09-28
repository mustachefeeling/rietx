"""WP-1110 item 13 — a phase the data cannot see, and what it does to a fit.

Two mechanisms for one failure, and neither substitutes for the other:

* ``params.vector.cell_window`` bounds the **symptom**.  A phase at zero scale
  contributes a flat direction, the trust region wanders along it, and the cell
  leaves the physical range entirely — silently, because a parameter that does
  not affect the calculated pattern does not affect Rwp either.
* ``refine._phase_support_diagnostics`` names the **cause**.  A windowed cell
  re-anchors at every stage, so it walks quietly rather than loudly and
  ``BOUND_HIT`` need never fire; without this the caller is left inferring an
  absent phase from a ρ≈1 correlation between its cell and its scale.

The episode behind both: two agents independently drove a real phase's cell to
a ≈ 39 293 Å and a ≈ 40 000 Å on a 68-pattern in-situ series, and the run died
hundreds of stages later inside ``generate_reflections``.
"""

from __future__ import annotations

import numpy as np
import pytest

from rietx import Instrument, Refinement
from rietx.params.vector import (
    CELL_MIN_LENGTH_A,
    CELL_WINDOW_ANGLE_DEG,
    CELL_WINDOW_FRACTION,
    CELL_WINDOW_PAD_A,
    ParameterTable,
    cell_window,
)
from rietx.schemas.instrument import BackgroundChebyshev
from rietx.schemas.structure import Structure
from tests.test_refine_synthetic import TRUE_A, synthesize
from tests.test_schemas import make_lab6

pytestmark = pytest.mark.xdist_group("absent-phase")

OUT = __import__("pathlib").Path(__file__).parent / "output"


# ----------------------------------------------------------------------
# the window itself
# ----------------------------------------------------------------------
def test_the_window_is_relative_to_the_value_it_is_anchored_on():
    """±5 % + 0.05 Å either side of where the stage starts."""
    lo, hi = cell_window("a", 10.0, -np.inf, np.inf)
    assert (lo, hi) == pytest.approx((10.0 * 0.95 - 0.05, 10.0 * 1.05 + 0.05))
    # the fractional part scales with the cell; the pad does not, which is what
    # keeps a short cell from being held tighter than a long one in absolute Å
    lo2, hi2 = cell_window("a", 20.0, -np.inf, np.inf)
    assert (hi - lo) == pytest.approx(2 * (CELL_WINDOW_FRACTION * 10.0
                                           + CELL_WINDOW_PAD_A))
    assert (hi2 - lo2) == pytest.approx(2 * (CELL_WINDOW_FRACTION * 20.0
                                             + CELL_WINDOW_PAD_A))


def test_a_finite_stored_bound_is_the_callers_claim_and_is_kept_per_side():
    """TOPAS's rule: user limits override the defaults.

    Per **side**, because the two sides are separate claims — the failure this
    exists for is unbounded-above, and a caller who set only a floor has said
    nothing about a ceiling.
    """
    lo, hi = cell_window("a", 10.0, 0.1, np.inf)
    assert lo == 0.1                      # kept: the caller said so
    assert hi == pytest.approx(10.55)     # filled: nobody said anything

    lo, hi = cell_window("a", 10.0, -np.inf, 12.0)
    assert lo == pytest.approx(9.45)
    assert hi == 12.0

    # both claimed → wholly untouched
    assert cell_window("a", 10.0, 1.0, 99.0) == (1.0, 99.0)


def test_the_floor_is_absolute_and_never_excludes_where_the_cell_already_is():
    """A short cell gets the floor; an impossibly short one is not raised on.

    ``ParameterTable`` has no diagnostics channel, so a cell below the floor is
    a model to refuse where a message can be attached — not a bound to raise on
    here.  Proposing ``lo > value`` would make ``least_squares`` reject x0.
    """
    # 0.95·2.0 − 0.05 = 1.85 clears the floor, so the fraction still governs
    assert cell_window("a", 2.0, -np.inf, np.inf)[0] == pytest.approx(1.85)
    # 0.95·1.6 − 0.05 = 1.47 does not, so the floor takes over
    lo, _ = cell_window("a", 1.6, -np.inf, np.inf)
    assert lo == CELL_MIN_LENGTH_A
    lo, hi = cell_window("a", 0.8, -np.inf, np.inf)
    assert lo <= 0.8 <= hi, "the window must always contain the current value"


def test_angles_get_a_degree_window_clipped_inside_the_degenerate_ends():
    lo, hi = cell_window("beta", 93.2, -np.inf, np.inf)
    assert (lo, hi) == pytest.approx((93.2 - CELL_WINDOW_ANGLE_DEG,
                                      93.2 + CELL_WINDOW_ANGLE_DEG))
    # the metric tensor is singular at 0° and 180°, so the window stops short
    lo, hi = cell_window("gamma", 179.5, -np.inf, np.inf)
    assert hi < 180.0 and lo <= 179.5 <= hi


def test_a_value_no_cell_can_take_is_refused_by_name():
    """Not a short cell — not a cell.  WP-1130's bug.

    The clamp above keeps a *positive* short length (it is a model to refuse
    where there is a diagnostics channel).  At ``value <= -pad/f`` it instead
    snaps both ends of the window onto ``value``, and the degenerate pair goes
    to ``least_squares``, which raises "Each lower bound must be strictly less
    than each upper bound" — naming no parameter and nothing about cells.  A
    trigonal ``a`` reached −42.7 Å that way.
    """
    for name, value in [("a", -5.0), ("b", -42.7), ("c", 0.0)]:
        with pytest.raises(ValueError, match=r"phases\.1\.cell\." + name):
            cell_window(name, value, -np.inf, np.inf,
                        path=f"phases.1.cell.{name}")
    for name, value in [("alpha", 0.0), ("beta", 180.0), ("gamma", -1.0)]:
        with pytest.raises(ValueError, match="not a cell angle"):
            cell_window(name, value, -np.inf, np.inf,
                        path=f"phases.1.cell.{name}")

    # without a path it still says which parameter, since that is all it has
    with pytest.raises(ValueError, match="cell parameter 'a'"):
        cell_window("a", -5.0, -np.inf, np.inf)


def test_the_window_is_never_degenerate():
    """The postcondition, over every value the function accepts.

    ``lo == hi`` is the shape the caller cannot handle: it is passed straight
    to the solver's ``bounds``.  Sweeping both branches is cheap and is what
    would have caught this, since the failing value was outside the range
    anyone thought to write a case for.
    """
    for value in [1e-12, 1e-6, 0.8, 1.5, 2.0, 5.4312, 10.0, 42.7, 1e3, 1e6]:
        lo, hi = cell_window("a", value, -np.inf, np.inf)
        assert lo < hi and lo <= value <= hi
    for value in [1e-9, 0.5, 1.0, 60.0, 90.0, 120.0, 179.0, 179.999]:
        lo, hi = cell_window("beta", value, -np.inf, np.inf)
        assert lo < hi and lo <= value <= hi


def _lab6_table():
    s = make_lab6()
    s.phases[0].cell.a.vary = True
    return s, ParameterTable(s, Instrument.debye_scherrer(wavelength=1.5406))


def test_the_window_reaches_the_solver_and_not_the_parameter_surface():
    """The distinction the placement rests on.

    A window is a bound for the stage about to run, not a fact about the stored
    parameter — ``ParameterRow`` and the ``.rxt`` document both tell a reader
    that bounds come from the schema, so a window surfaced there would read as
    a claim the caller never made.
    """
    _, table = _lab6_table()
    table.freeze_cell_windows({0})

    entry = next(e for e in table.entries if e.path == "phases.0.cell.a")
    assert (entry.lo, entry.hi) == (-np.inf, np.inf), "the entry keeps the schema's bounds"

    lo, hi = table.bounds()
    i = table.free_paths.index("phases.0.cell.a")
    v = entry.value
    assert lo[i] == pytest.approx(v * (1 - CELL_WINDOW_FRACTION) - CELL_WINDOW_PAD_A)
    assert hi[i] == pytest.approx(v * (1 + CELL_WINDOW_FRACTION) + CELL_WINDOW_PAD_A)


def test_a_table_that_was_asked_nothing_windows_nothing():
    """``None`` is *no claim made*, and an empty set is the claim that no phase
    needs one — the ``moving_paths`` convention, one rank over."""
    _, table = _lab6_table()
    i = table.free_paths.index("phases.0.cell.a")

    for claim in (None, set()):
        table.freeze_cell_windows(claim)
        lo, hi = table.bounds()
        assert (lo[i], hi[i]) == (-np.inf, np.inf), f"claim={claim!r}"


def test_the_window_is_spent_only_on_the_phases_named():
    """Not free, so not universal.

    TRF derives its per-coordinate trust-region scale from the distance to the
    bounds, so a window changes the *step* taken in a cell even where the bound
    is never reached. Measured on the chained IUCr ``cpd-1c``, whose cell
    finishes 0.24 Å inside a ±5 % window and never touches it: windowing every
    phase took the collapsed warm refit from 82 iterations to its 400-iteration
    budget and left it at Rwp 0.1501 against 0.1079 — just inside the reseed
    fence, so the pattern was accepted rather than rescued. That is why the
    window is restricted rather than applied to everything.
    """
    s = make_lab6()
    s2 = make_lab6()
    s2.phases[0].name = "second"
    for n in "abc":
        getattr(s2.phases[0].cell, n).value = 5.2
    both = Structure(phases=[s.phases[0], s2.phases[0]])
    for ph in both.phases:
        ph.cell.a.vary = True
    table = ParameterTable(both, Instrument.debye_scherrer(wavelength=1.5406))
    table.freeze_cell_windows({1})

    lo, hi = table.bounds()
    healthy = table.free_paths.index("phases.0.cell.a")
    absent = table.free_paths.index("phases.1.cell.a")
    assert (lo[healthy], hi[healthy]) == (-np.inf, np.inf)
    assert np.isfinite(lo[absent]) and np.isfinite(hi[absent])


def test_the_bound_and_the_diagnostic_read_one_measurement():
    """One authority projected twice, never two opinions (WP-1076's rule).

    A second measurement here would pass its own test and still let the solver
    bound a phase the report calls visible.
    """
    from rietx.model.forward import PHASE_SUPPORT_SIGMA, compile_model
    from rietx.optimize.least_squares import _freeze_cell_windows

    structure, ins = _absent_phase_inputs()
    pattern = synthesize()
    model = compile_model(structure, ins, pattern, mode="rietveld")
    table = ParameterTable(structure, ins)
    table.set_vary(["phases.*.cell.a"], True)

    support = model.phase_support(table.decode(table.x0()))
    _freeze_cell_windows(model, table)
    assert table._cell_window_phases == {
        ip for ip, v in enumerate(support) if v < PHASE_SUPPORT_SIGMA}
    assert table._cell_window_phases == {1}, "only the absent phase"


# ----------------------------------------------------------------------
# the failure it exists for
# ----------------------------------------------------------------------
def _absent_phase_inputs():
    """LaB₆ that is really there, plus a copy of it that is not."""
    s1 = make_lab6()
    for n in "abc":
        getattr(s1.phases[0].cell, n).value = 4.1606
    s1.phases[0].scale.value = 5e-4 * 1.8

    s2 = make_lab6()
    absent = s2.phases[0]
    absent.name = "absent"
    for n in "abc":
        getattr(absent.cell, n).value = 5.2
    absent.scale.value = 1e-9

    ins = Instrument.debye_scherrer(wavelength=0.4139)
    ins.background = BackgroundChebyshev.with_terms(3)
    return Structure(phases=[s1.phases[0], absent]), ins


@pytest.fixture(scope="module")
def absent_phase_fit():
    structure, ins = _absent_phase_inputs()
    ref = Refinement(structure, ins, history=False)
    return ref, ref.fit(synthesize(), plan="mccusker_default")


def test_the_absent_phases_cell_stays_in_the_physical_range(absent_phase_fit):
    """Unbounded this walked 5.2 → 25.6 Å and still reported ``converged``.

    The bar is deliberately far looser than the measured result: the assertion
    is "did not leave the physical range", not a pin on the trajectory, which
    is a flat direction and therefore not reproducible to many figures.
    """
    ref, _ = absent_phase_fit
    a = ref.structure.phases[1].cell.a.value
    assert 4.0 < a < 7.0, f"absent phase cell ran to a = {a:.4g} Å"


def test_the_phase_that_is_really_there_is_untouched_by_the_window(absent_phase_fit):
    """The window must cost an honest phase nothing.

    Measured across 51 stage transitions of the 11-BM NAC and SRM 660c
    protocols the widest honest single-stage cell move was 2.8e-4 relative —
    two orders inside the window — so it is never reached by a fit that is
    working.
    """
    ref, result = absent_phase_fit
    assert result.statistics.rwp < 0.05
    a = ref.structure.phases[0].cell.a.value
    assert a == pytest.approx(TRUE_A, abs=2e-4), f"LaB6 a = {a}"


def test_the_diagnostic_names_the_cause_not_the_correlation(absent_phase_fit):
    """``HIGH_CORRELATION`` reports ρ≈1 between the cell and the scale.

    That is the symptom.  ``PHASE_UNCONSTRAINED`` says which phase the data
    cannot see and which of its parameters were refined against it anyway.
    """
    _, result = absent_phase_fit
    fired = [d for d in result.diagnostics if d.code == "PHASE_UNCONSTRAINED"]
    assert len(fired) == 1, [d.code for d in result.diagnostics]
    finding = fired[0]
    assert finding.value < 1.0
    assert "absent" in finding.message
    # it carries the paths whose values are not measurements
    assert all(p.startswith("phases.1.") for p in finding.where)
    assert "phases.1.scale" not in finding.where, \
        "the scale is how a phase legitimately climbs out of the noise"
    assert any(".cell." in p for p in finding.where)


def test_a_trace_phase_that_is_really_there_does_not_fire_it(absent_phase_fit):
    """The false-positive side, on the same fit.

    Measured on the 11-BM NAC protocol, whose CaF₂ impurity is a genuine minor
    phase: 185σ of support there against a *noise-level* absent phase here.
    The claim is that ordering, and it is asserted as one — against this run's
    own ``support[0]``, never against a remembered figure.

    **The absent phase's support is the landing point of a flat direction and
    cannot be pinned to a number** (WP-1129); the cell assertion above already
    says so about the same fit's other coordinate. The phase reaches the
    pattern only through ``scale × |F|² × profile``, and its scale converges to
    *a* zero, not to *the* zero: measured 1.6e-14 under the shipped schedule
    and 7.1e-09 under ``intermediate_ftol=None``, one macOS box, one commit.
    The support that follows spans **six orders** across settings and
    platforms — 9.1e-07 and 0.548 here, 0.088 on WP-1110's machine, 1.64 on a
    Windows CI worker, which is what a fixed ``< 1.0`` bound turned into a red
    nightly. Every one of those is noise beside the ~386σ the real phase
    carries, which is the only thing the fit actually determines.
    """
    ref, _ = absent_phase_fit
    from rietx.model.forward import compile_model

    model = compile_model(ref.structure, ref.instrument, synthesize(),
                          mode="rietveld")
    table = ParameterTable(ref.structure, ref.instrument)
    values = table.decode(table.x0())
    support = [float(np.max(np.asarray(model.phase_component(ip, values))
                            / model.sigma))
               for ip in range(len(ref.structure.phases))]
    assert support[0] > 10.0, \
        f"the real phase is far above the noise: {support[0]:.3g}σ"
    assert support[1] < support[0] / 20.0, (
        f"the absent one is not far below it: {support[1]:.3g}σ against the "
        f"real phase's {support[0]:.3g}σ — a ratio of "
        f"{support[0] / max(support[1], 1e-300):.3g}, and the bar is 20")


@pytest.mark.slow
def test_the_absent_phase_fit_is_drawn_for_inspection(absent_phase_fit):
    """Rwp hides locally-bad fits; the picture is the check that does not."""
    from rietx.viz.plots import plot_result

    _, result = absent_phase_fit
    OUT.mkdir(exist_ok=True)
    plot_result(result, path=str(OUT / "absent_phase.png"))
    import matplotlib.pyplot as plt

    plt.close("all")
    assert (OUT / "absent_phase.png").exists()


# ----------------------------------------------------------------------
# the same finding, read across a series (item 8)
# ----------------------------------------------------------------------
def _series_with(n: int, fired_in: int, *, code: str = "BOUND_HIT",
                 path: str = "phases.3.cell.c", level: str = "warning"):
    """``fired_in`` of ``n`` patterns carry ``code`` on ``path``."""
    from rietx.schemas.common import Diagnostic
    from rietx.schemas.sequential import SeriesEntry, SeriesResult

    return SeriesResult(entries=[
        SeriesEntry(index=i, label=f"p{i}", diagnostics=(
            [Diagnostic(level=level, code=code, where=[path], message="…")]
            if i < fired_in else []))
        for i in range(n)])


def test_a_finding_in_most_of_a_series_is_stated_once_with_its_count():
    """The sentence no per-pattern diagnostic can produce.

    The trigger episode's own numbers: ``phases.3.cell.c`` pinned in 42 of 68
    patterns, said 425 times per-pattern and never once as "42 of 68".
    """
    from rietx.sequential import _persistent_diagnostics

    out = _persistent_diagnostics(_series_with(68, 42))
    assert len(out) == 1
    finding = out[0]
    assert finding.code == "SEQUENTIAL_PERSISTENT_FINDING"
    assert "42 of 68" in finding.message and "BOUND_HIT" in finding.message
    assert finding.where == ["phases.3.cell.c"]
    assert finding.value == pytest.approx(42 / 68)


def test_the_threshold_is_a_change_of_subject_at_half_the_patterns():
    """Below half, the per-entry diagnostics are the whole story.

    Not a tuned sensitivity: above half a finding describes the series rather
    than some of its members, and a summary that repeated a minority finding
    would be a second authority on the same fact.
    """
    from rietx.sequential import _persistent_diagnostics

    assert _persistent_diagnostics(_series_with(68, 34)) == []   # exactly half
    assert len(_persistent_diagnostics(_series_with(68, 35))) == 1


def test_a_short_series_gets_no_summary_at_all():
    """A summary of three things is not a summary."""
    from rietx.sequential import MIN_POINTS_FOR_PERSISTENCE, _persistent_diagnostics

    short = MIN_POINTS_FOR_PERSISTENCE - 1
    assert _persistent_diagnostics(_series_with(short, short)) == []


def test_it_aggregates_whatever_fired_rather_than_a_list_of_codes():
    """Diagnostic codes are an open vocabulary (root CLAUDE.md).

    A new code must be summarised on the day it lands, with no edit here — so
    this asserts the *mechanism* is code-agnostic, using one that did not exist
    when the aggregation was written.
    """
    from rietx.sequential import _persistent_diagnostics

    out = _persistent_diagnostics(
        _series_with(10, 9, code="PHASE_UNCONSTRAINED", path="phases.3.cell.a"))
    assert len(out) == 1 and "PHASE_UNCONSTRAINED" in out[0].message


def test_the_summary_carries_the_worst_level_and_promotes_nothing():
    """It travels in both directions.

    Up, because a summary must not report an error as a warning. Down, because
    a deliberate `dispersion=None` fires an **info** `DISPERSION_NEGLECTED` on
    every pattern of a series — "68 of 68" is worth saying, and calling a
    declared choice a warning is not.
    """
    from rietx.sequential import _persistent_diagnostics

    assert _persistent_diagnostics(_series_with(10, 9, level="error"))[0].level \
        == "error"
    assert _persistent_diagnostics(
        _series_with(10, 10, code="DISPERSION_NEGLECTED",
                     level="info"))[0].level == "info"


def test_a_finding_about_how_a_pattern_was_measured_is_never_aggregated():
    """``FROZEN_COMPILE_STALE`` (#272) on every pattern is a chain whose every
    last stage re-sized its windows, not a model that is wrong, so it gains no
    series finding — while a model-level code beside it still does."""
    from rietx.schemas.common import Diagnostic
    from rietx.schemas.sequential import SeriesEntry, SeriesResult
    from rietx.sequential import NOT_A_SERIES_FINDING, _persistent_diagnostics

    assert "FROZEN_COMPILE_STALE" in NOT_A_SERIES_FINDING
    assert _persistent_diagnostics(
        _series_with(10, 10, code="FROZEN_COMPILE_STALE", path="",
                     level="info")) == []
    entries = [SeriesEntry(index=i, label=f"p{i}", diagnostics=[
        Diagnostic(level="info", code="FROZEN_COMPILE_STALE", message="…",
                   value=2e-3),
        Diagnostic(level="warning", code="BOUND_HIT",
                   where=["phases.0.cell.a"], message="…")])
        for i in range(10)]
    out = _persistent_diagnostics(SeriesResult(entries=entries))
    assert [d.message.split()[0] for d in out] == ["BOUND_HIT"]


def test_one_error_among_warnings_sets_the_summary_level():
    from rietx.schemas.common import Diagnostic
    from rietx.schemas.sequential import SeriesEntry, SeriesResult
    from rietx.sequential import _persistent_diagnostics

    entries = []
    for i in range(10):
        level = "error" if i == 3 else "warning"
        entries.append(SeriesEntry(index=i, label=f"p{i}", diagnostics=[
            Diagnostic(level=level, code="BOUND_HIT",
                       where=["phases.0.cell.a"], message="…")]))
    out = _persistent_diagnostics(SeriesResult(entries=entries))
    assert out[0].level == "error"


def test_one_pattern_counts_once_however_many_stages_fired_it():
    """Otherwise the count measures stages, not patterns."""
    from rietx.schemas.common import Diagnostic
    from rietx.schemas.sequential import SeriesEntry, SeriesResult
    from rietx.sequential import _persistent_diagnostics

    repeated = [Diagnostic(level="warning", code="BOUND_HIT",
                           where=["phases.0.cell.a"], message=f"stage {s}")
                for s in range(6)]
    series = SeriesResult(entries=[
        SeriesEntry(index=i, label=f"p{i}", diagnostics=list(repeated))
        for i in range(8)])
    out = _persistent_diagnostics(series)
    assert len(out) == 1
    assert "8 of 8" in out[0].message, out[0].message


# ----------------------------------------------------------------------
# a scale at zero, and the esds it takes with it (WP-1463)
# ----------------------------------------------------------------------
# No plan reaches these states on this fixture: TRF stops the absent scale
# between 1e-28 and 1e-135.  A real 48-pattern series reached 1e-179 and 0.0,
# so the fixture lets TRF finish and then moves the scale's internal value u to
# where that series stopped, re-evaluating the residual and Jacobian there.
# Every post-fit step then runs as in production.  S = softplus(u), and it
# reaches exactly 0.0 once u passes about -745.

def _scale_only_plan():
    from rietx.schemas.plan import PlanSpec, StageSpec

    return PlanSpec(stages=[
        StageSpec(name="scales",
                  turn_on=["phases.*.scale", "instrument.background.*"]),
        StageSpec(name="profile",
                  turn_on=["phases.0.cell.*", "instrument.zero_shift",
                           "instrument.profile.w", "phases.0.atoms.*.biso"]),
    ])


@pytest.fixture
def fit_absent_at(monkeypatch):
    """``fit(u)`` fits the absent-phase fixture with its scale moved to ``u``."""
    import importlib

    lsq = importlib.import_module("rietx.optimize.least_squares")
    refine_module = importlib.import_module("rietx.refine")
    solve, run = lsq.least_squares, refine_module.run_least_squares
    where = {"k": None, "u": None}

    def run_recording_the_column(model, table, **kw):
        free = table.free_paths
        where["k"] = free.index("phases.1.scale") if "phases.1.scale" in free else None
        return run(model, table, **kw)

    def solve_then_move(fun, x0, jac=None, **kw):
        res = solve(fun, x0, jac=jac, **kw)
        if where["k"] is not None and where["u"] is not None:
            x = res.x.copy()
            x[where["k"]] = where["u"]
            res.x, res.fun, res.jac = x, fun(x), jac(x)
            res.cost = 0.5 * float(res.fun @ res.fun)
        return res

    monkeypatch.setattr(lsq, "least_squares", solve_then_move)
    monkeypatch.setattr(refine_module, "run_least_squares", run_recording_the_column)

    def fit(u, plan="mccusker_default"):
        where["u"] = u
        structure, ins = _absent_phase_inputs()
        return Refinement(structure, ins, history=False).fit(synthesize(), plan=plan)

    fit.where = where
    return fit


def _row(result, path):
    return next(p for p in result.parameters if p.path == path)


def _fraction_esds(result):
    return [q.weight_fraction_stderr for q in result.qpa.phases]


@pytest.mark.parametrize("u", [-380.0, -400.0, -700.0])
def test_a_tiny_scale_keeps_the_esds_it_had_at_1e_135(fit_absent_at, u):
    """The answer no longer depends on how far TRF walked down a flat line.

    At u = -380 (S ≈ 1e-166) the internal variance overflowed; at -400
    (S ≈ 2e-174) its d² underflowed as well; -700 is S ≈ 1e-304.  Each lost
    every weight-fraction esd before WP-1463, and each now carries the esds
    of the natural fit, whose scale TRF left at 4.2e-135.
    """
    reference = fit_absent_at(None)
    moved = fit_absent_at(u)
    s_ref, s = _row(reference, "phases.1.scale"), _row(moved, "phases.1.scale")
    # where TRF leaves the natural scale moves with platform libm, and since
    # WP-1463 any nonzero value is a valid reference
    assert 0.0 < s.value < 1e-160 and s_ref.value > 0.0
    assert s.stderr == pytest.approx(s_ref.stderr, rel=1e-9)
    assert _fraction_esds(moved) == pytest.approx(_fraction_esds(reference),
                                                  rel=1e-9)
    assert all(e is not None for e in _fraction_esds(moved))
    assert "QPA_ESD_UNAVAILABLE" not in {d.code for d in moved.diagnostics}


@pytest.mark.parametrize("plan", ["mccusker_default", "scale_only"])
def test_a_scale_at_zero_names_the_phase_that_withheld_every_esd(fit_absent_at,
                                                                plan):
    """At exactly 0.0 the column is zero by every route, so the esds go.

    dS/du has underflowed, and the analytic branch hands a zero scale to the
    finite difference, which decodes 0.0 again.  What changed is that the loss
    now says which phase caused it, under a plan that frees the absent
    phase's cell and under one that frees only its scale.
    """
    result = fit_absent_at(-800.0, plan=_scale_only_plan()
                           if plan == "scale_only" else plan)
    assert _row(result, "phases.1.scale").value == 0.0
    assert _fraction_esds(result) == [None, None]
    fired = [d for d in result.diagnostics if d.code == "QPA_ESD_UNAVAILABLE"]
    assert len(fired) == 1
    assert fired[0].where == ["phases.1.scale"]
    assert fired[0].level == "warning"
    assert "phase 1 (absent)" in fired[0].message
    assert "profile_fraction(data, 1)" in fired[0].suggestion


def test_a_scale_only_plan_leaves_phase_unconstrained_nothing_to_say(fit_absent_at):
    """Why the QPA block's comment was wrong on 15 of the 16.

    ``PHASE_UNCONSTRAINED`` is about a phase's *other* free parameters, and a
    plan freeing only the scale gives it none.  The new finding is what names
    the phase there.
    """
    result = fit_absent_at(-800.0, plan=_scale_only_plan())
    codes = {d.code for d in result.diagnostics}
    assert "PHASE_UNCONSTRAINED" not in codes
    assert "QPA_ESD_UNAVAILABLE" in codes


@pytest.mark.parametrize("u", [None, -400.0, -800.0])
def test_at_bound_on_a_scale_at_its_floor_is_not_an_answer(fit_absent_at, u):
    """A softplus floor has no finite internal limit, so nothing tested it.

    Before WP-1463 the row said ``False``.  Asked in physical space the
    WP-1434 conjunction would say ``True``, since the residual cosine is 0.030
    and pushes outward, and ``BOUND_HIT`` would advise widening a bound on a
    quantity that cannot be negative.  The honest state is ``None``.  The
    phase that is there sits far from its floor, and stays a tested ``False``.
    """
    result = fit_absent_at(u)
    assert _row(result, "phases.1.scale").at_bound is None
    assert _row(result, "phases.0.scale").at_bound is False
    assert not any(d.code == "BOUND_HIT" and "phases.1.scale" in d.where
                   for d in result.diagnostics)


def test_a_joint_fit_withholds_a_blind_scale_and_names_it(monkeypatch):
    """``multi.py`` had its own QPA builder, and it skipped the blind-scale rule.

    So a joint fit with a scale at 0.0 propagated the other fractions as if
    that phase were known, which is the confident wrong number the single fit
    had been refusing since WP-1110.  Both now call one builder.  The row path
    is the joint surface's own: the absent scale is per histogram here, so
    ``hist.h.`` prefixes it.
    """
    import importlib

    from rietx import MultiHistogramRefinement
    from tests import test_multi_histogram as tmh

    lsq = importlib.import_module("rietx.optimize.least_squares")
    multi = importlib.import_module("rietx.multi")
    solve, run = lsq.least_squares, multi.run_multi_least_squares
    cols: list[int] = []

    def run_recording(models, mtable, **kw):
        cols[:] = [k for k, p in enumerate(mtable.free_paths)
                   if p.endswith("phases.1.scale")]
        return run(models, mtable, **kw)

    def solve_then_zero(fun, x0, jac=None, **kw):
        res = solve(fun, x0, jac=jac, **kw)
        if cols:
            x = res.x.copy()
            x[cols] = -800.0
            res.x, res.fun, res.jac = x, fun(x), jac(x)
            res.cost = 0.5 * float(res.fun @ res.fun)
        return res

    monkeypatch.setattr(lsq, "least_squares", solve_then_zero)
    monkeypatch.setattr(multi, "run_multi_least_squares", run_recording)

    structure, instruments = tmh.perturbed_inputs()
    absent = make_lab6().phases[0]
    absent.name = "absent"
    for n in "abc":
        getattr(absent.cell, n).value = 5.2
    absent.scale.value = 1e-9
    structure = Structure(phases=[structure.phases[0], absent])
    patterns = [
        tmh.synthesize(0.41390, 3.0, 24.0, scale=5e-4, zero=0.006,
                       bkg=[40.0, -6.0, 1.5], seed=1),
        tmh.synthesize(0.71070, 6.0, 46.0, scale=9e-4, zero=-0.010,
                       bkg=[70.0, 5.0, -2.0], seed=2),
    ]
    result = MultiHistogramRefinement(structure, instruments).fit(
        patterns, plan="mccusker_default")

    assert cols, "the absent scale was never free"
    for h, hist in enumerate(result.histograms):
        assert [q.weight_fraction_stderr for q in hist.qpa.phases] == [None, None]
        fired = [d for d in hist.diagnostics if d.code == "QPA_ESD_UNAVAILABLE"]
        assert [d.where for d in fired] == [[f"hist.{h}.phases.1.scale"]]


def test_a_series_whose_phase_left_says_so_in_every_pattern(fit_absent_at):
    """Five patterns, the absent scale at 0.0 in each.

    Each entry names the phase, and ``SEQUENTIAL_PERSISTENT_FINDING`` counts
    it across the series with no edit of its own, its codes being an open
    vocabulary.
    """
    from rietx.sequential import refine_sequential

    fit_absent_at.where["u"] = -800.0
    structure, ins = _absent_phase_inputs()
    series = refine_sequential([synthesize(noise_seed=s) for s in range(5)],
                               structure, ins, plan="mccusker_default")
    for entry in series.entries:
        fired = [d for d in entry.diagnostics if d.code == "QPA_ESD_UNAVAILABLE"]
        assert [d.where for d in fired] == [["phases.1.scale"]], entry.label
    persistent = [d for d in series.diagnostics
                  if d.code == "SEQUENTIAL_PERSISTENT_FINDING"
                  and d.message.startswith("QPA_ESD_UNAVAILABLE")]
    assert [d.where for d in persistent] == [["phases.1.scale"]]
    assert "5 of 5" in persistent[0].message

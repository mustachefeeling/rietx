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


def test_the_window_reaches_the_solver_and_not_the_parameter_surface():
    """The distinction the placement rests on.

    A window is a bound for the stage about to run, not a fact about the stored
    parameter — ``ParameterRow`` and the ``.rxt`` document both tell a reader
    that bounds come from the schema, so a window surfaced there would read as
    a claim the caller never made.
    """
    s = make_lab6()
    s.phases[0].cell.a.vary = True
    table = ParameterTable(s, Instrument.debye_scherrer(wavelength=1.5406))

    entry = next(e for e in table.entries if e.path == "phases.0.cell.a")
    assert (entry.lo, entry.hi) == (-np.inf, np.inf), "the entry keeps the schema's bounds"

    lo, hi = table.bounds()
    i = table.free_paths.index("phases.0.cell.a")
    v = entry.value
    assert lo[i] == pytest.approx(v * (1 - CELL_WINDOW_FRACTION) - CELL_WINDOW_PAD_A)
    assert hi[i] == pytest.approx(v * (1 + CELL_WINDOW_FRACTION) + CELL_WINDOW_PAD_A)


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
    phase: 185σ of support against the absent phase's 0.088σ here.  The 1σ
    threshold is three orders from either, so it is not a knife edge — pinned
    as an ordering rather than as a number.
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
    assert support[0] > 10.0, "the real phase is far above the noise"
    assert support[1] < 1.0, "the absent one is far below it"


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

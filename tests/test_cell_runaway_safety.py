"""A cell can run away *within one stage* even where ``phase_support`` never
falls below its threshold — a gap the WP-1110 window and the WP-1301 hold both
miss, because both key off one phase's own modelled contribution.

Trigger (synthetic, not the private dataset that surfaced it): two free
LaB6-shaped phases sharing the *same* starting cell, one at full scale and one
at a 2 % trace, with scale and cell freed together in one stage.  Neither
phase's own support ever drops — the full-scale phase's least of all — so the
support-based window (``params.vector.cell_window`` as applied by
``optimize.least_squares._freeze_cell_windows``) and the support-based hold
(``refine._hold_unsupported_phases``) both leave the pair unwindowed and
unheld the entire stage.  What actually happens is a **joint** degeneracy: the
two phases trade scale against each other along an axis in which either
phase's cell is free to run, and the phase that ends up walking it can be the
fully-supported one.  Measured on this exact construction before the fix: one
phase's cell.a walked 4.1566 -> 3803 Å in twenty TRF iterations of one "both"
stage (still reporting ``converged``), and the next stage's ``compile_model``
crashed with the WP-1110 ``generate_reflections`` refusal
(``refusing to enumerate reflections for cell a=295.588 ...``) before that
next stage's own ``_freeze_cell_windows`` ever ran.

The fix (``refine.clamp_cell_runaway``) is a **post-solve** correction, not a
second live bound: it inspects the committed cell values after a stage solves
and pulls any free cell parameter back inside
``CELL_SAFETY_FRACTION``/``CELL_SAFETY_ANGLE_DEG`` of the value the stage
*started* from, unconditionally — no phase_support test gates it, which is
the whole point, since the escaping phase here is exactly the one
phase_support calls fine.  Doing this on the outcome rather than as a bound
scipy's TRF sees is what keeps every other test in this suite bit-identical:
a live bound changes TRF's own trust-region step scaling even where it is
never hit (WP-1110's own measurement, on an honestly-converging phase), and
this project's suite has thousands of cell-refining fits that must not move a
digit.
"""

from __future__ import annotations

import math

import pytest

from rietx import Instrument, Refinement
from rietx.params.vector import (
    CELL_SAFETY_ANGLE_DEG,
    CELL_SAFETY_FRACTION,
    CELL_WINDOW_ANGLE_DEG,
    CELL_WINDOW_FRACTION,
    cell_window,
)
from rietx.refine import _build_result, _cell_runaway_diagnostic, clamp_cell_runaway
from rietx.schemas.common import Parameter
from rietx.schemas.instrument import BackgroundChebyshev
from rietx.schemas.structure import Atom, Cell, Phase, Structure
from rietx.strategy.staged import RefinementPlan, Stage
from tests.test_refine_synthetic import TRUE_A, synthesize
from tests.test_schemas import make_lab6

pytestmark = pytest.mark.xdist_group("cell-runaway-safety")


def _degenerate_pair(decoy_scale: float) -> tuple[Structure, Instrument]:
    """A real LaB6 phase and a second, identically-celled copy at a trace
    scale — the construction WP-1110 item 13's own docstring calls out as
    "the situation this documents", pushed one step further: freeing scale
    and cell of *both* phases together in one stage, which
    ``mccusker_default`` never does (its ``scale_bkg`` and ``cell`` stages
    are separate, so by the time cell frees the trace phase's scale has
    already collapsed and the ordinary window catches it)."""
    real = make_lab6()
    for n in "abc":
        getattr(real.phases[0].cell, n).value = TRUE_A
    real.phases[0].scale.value = 5e-4
    decoy_s = make_lab6()
    decoy = decoy_s.phases[0]
    decoy.name = "decoy"
    for n in "abc":
        getattr(decoy.cell, n).value = TRUE_A
    decoy.scale.value = decoy_scale
    ins = Instrument.debye_scherrer(wavelength=0.4139)
    ins.background = BackgroundChebyshev.with_terms(3)
    return Structure(phases=[real.phases[0], decoy]), ins


# ----------------------------------------------------------------------
# cell_window's new fraction/angle_deg parameters: old defaults untouched
# ----------------------------------------------------------------------
def test_cell_window_defaults_are_bit_identical_to_before_the_parameters():
    """Every existing caller of ``cell_window`` passes no ``fraction``/
    ``angle_deg`` and must see exactly the old numbers."""
    lo, hi = cell_window("a", 10.0, -math.inf, math.inf)
    assert (lo, hi) == pytest.approx(
        (10.0 * (1 - CELL_WINDOW_FRACTION) - 0.05,
         10.0 * (1 + CELL_WINDOW_FRACTION) + 0.05))
    lo, hi = cell_window("beta", 93.2, -math.inf, math.inf)
    assert (lo, hi) == pytest.approx(
        (93.2 - CELL_WINDOW_ANGLE_DEG, 93.2 + CELL_WINDOW_ANGLE_DEG))


def test_the_safety_window_is_three_times_wider_than_the_support_window():
    """The two constants the two mechanisms use, related as documented."""
    assert CELL_SAFETY_FRACTION == pytest.approx(3.0 * CELL_WINDOW_FRACTION)
    assert CELL_SAFETY_ANGLE_DEG == pytest.approx(3.0 * CELL_WINDOW_ANGLE_DEG)
    lo_support, hi_support = cell_window("a", 10.0, -math.inf, math.inf)
    lo_safety, hi_safety = cell_window("a", 10.0, -math.inf, math.inf,
                                       fraction=CELL_SAFETY_FRACTION,
                                       angle_deg=CELL_SAFETY_ANGLE_DEG)
    assert lo_safety < lo_support < 10.0 < hi_support < hi_safety


# ----------------------------------------------------------------------
# clamp_cell_runaway as a unit
# ----------------------------------------------------------------------
def test_a_cell_inside_the_window_is_left_alone():
    """The bit-identity property: nothing to clamp is nothing changed."""
    from rietx.params.vector import ParameterTable

    structure, ins = _degenerate_pair(5e-4)
    table = ParameterTable(structure, ins)
    table.set_vary(["phases.*.cell.a"], True)
    start_values = table.decode(table.x0())
    # nudge phase 0's cell by far less than CELL_SAFETY_FRACTION
    entry = table.entries[table._paths["phases.0.cell.a"]]
    entry.value = TRUE_A * 1.001
    clamped = clamp_cell_runaway(table, start_values)
    assert clamped == []
    assert entry.value == pytest.approx(TRUE_A * 1.001)


def test_a_cell_outside_the_window_is_pulled_back_and_reported():
    from rietx.params.vector import ParameterTable

    structure, ins = _degenerate_pair(5e-4)
    table = ParameterTable(structure, ins)
    table.set_vary(["phases.*.cell.a"], True)
    start_values = table.decode(table.x0())
    escaped = TRUE_A * 50.0  # far outside +/-15%
    # ``clamp_cell_runaway`` reads and writes ``table.entries`` — the table's
    # own committed state, exactly what a real stage leaves it in after
    # ``table.commit(outcome.theta)`` — not the pydantic ``structure`` a
    # caller happens to also hold a reference to.
    entry = table.entries[table._paths["phases.0.cell.a"]]
    entry.value = escaped
    clamped = clamp_cell_runaway(table, start_values)
    assert len(clamped) == 1
    path, old, new = clamped[0]
    assert path == "phases.0.cell.a"
    assert old == pytest.approx(escaped)
    lo, hi = cell_window("a", start_values[path], -math.inf, math.inf,
                         fraction=CELL_SAFETY_FRACTION,
                         angle_deg=CELL_SAFETY_ANGLE_DEG)
    assert new == pytest.approx(hi)
    assert entry.value == pytest.approx(hi)


def test_a_held_cell_is_never_visited():
    """Only ``table.free_paths`` is inspected — a fixed cell (or one held by
    WP-1301, which is the same ``set_vary(..., False)`` under the hood) cannot
    have "escaped" anything, since nothing moved it.

    Review of #385 finding 3.  The escape is staged on the table's own
    ``Entry`` — what a real stage's ``table.commit(outcome.theta)`` writes,
    and what ``clamp_cell_runaway`` actually reads — never on the pydantic
    ``structure``: ``ParameterTable._add`` snapshots ``Entry.value`` from the
    model at construction and does not track it afterwards, so a write to
    ``structure.phases[0].cell.a.value`` after the table is built lands
    nowhere the function looks.  ``make_lab6`` frees the cell by default
    (``Cell.cubic(..., vary=True)``), so this test held ``cell.a`` explicitly
    is what makes the fixture's comment true — the previous
    ``# cell.a not freed`` was false: the fixture frees it, and the old
    test's escape silently missed the entries this function reads on two
    counts, not one.

    Made to fail on purpose once (``tests/CLAUDE.md``): commenting out
    ``clamp_cell_runaway``'s ``if e.path not in free: continue`` line turned
    this from green to red — ``clamped`` came back
    ``[('phases.0.cell.a', 207.83, 4.830089999999999)]`` instead of ``[]``,
    confirming the filter is what this pins rather than a vacuous write.
    """
    from rietx.params.vector import ParameterTable

    structure, ins = _degenerate_pair(5e-4)
    table = ParameterTable(structure, ins)
    table.set_vary(["phases.0.cell.a"], False)  # explicitly held/fixed
    assert "phases.0.cell.a" not in table.free_paths
    start_values = table.decode(table.x0())
    entry = table.entries[table._paths["phases.0.cell.a"]]
    entry.value = TRUE_A * 50.0  # staged on the Entry itself, not the pydantic model
    clamped = clamp_cell_runaway(table, start_values)
    assert clamped == []


# ----------------------------------------------------------------------
# review of #385 (2026-09-22): a cell driven by a free ``vars.X`` is
# invisible to ``clamp_cell_runaway``, which tests a free path's own name
# -- and it must stay invisible to the clamp (a shared driver has no single
# clamp target), but it must never pass through silently.
# ----------------------------------------------------------------------
def test_a_vars_driven_cell_escape_is_never_clamped_but_is_named():
    """``phases.0.cell.a`` tied to a free ``vars.A`` (Yue's own reproduction,
    review of #385 finding 1): ``clamp_cell_runaway`` still does not touch
    it -- that is correct, per its own docstring, since pulling the driver
    back would move every other value it reaches -- but
    ``_vars_driven_cell_escapes`` must find it, and the ``CELL_RUNAWAY``
    diagnostic built from both must name ``vars.A`` and ``phases.0.cell.a``
    together, saying it was not pulled back and why."""
    from rietx import Refinement
    from rietx.refine import _cell_runaway_diagnostic, _vars_driven_cell_escapes

    structure, ins = _degenerate_pair(5e-4)
    ref = Refinement(structure, ins, history=False)
    ref.add_variable("A", TRUE_A, min=1.0, max=1000.0)
    ref.tie("phases.0.cell.a", "vars.A")
    table = ref._prepare_table(restore=False)
    table.set_vary(["vars.A", "phases.1.cell.a"], True)
    start_values = table.decode(table.x0())

    # the construction the review names: free (cells+vars) is ['phases.1.cell.a',
    # 'vars.A'], moving (cells+vars) additionally carries 'phases.0.cell.a'
    assert "phases.0.cell.a" not in table.free_paths
    assert "phases.0.cell.a" in table.moving_paths
    assert "vars.A" in table.free_paths

    # the escape happens through the driver -- exactly as it would after a
    # runaway TRF step + table.commit(outcome.theta) -- and the tie carries
    # it to the dependent cell
    driver = table.entries[table._paths["vars.A"]]
    driver.value = TRUE_A * 50.0  # far outside +/-15%, same escape as above
    table.refresh_ties()
    dependent = table.entries[table._paths["phases.0.cell.a"]]
    assert dependent.value == pytest.approx(TRUE_A * 50.0)

    # clamp_cell_runaway does not, and must not, touch it
    clamped = clamp_cell_runaway(table, start_values)
    assert clamped == []
    assert dependent.value == pytest.approx(TRUE_A * 50.0)  # still escaped

    # LaB6 is cubic, so ``vars.A`` reaches ``b``/``c`` too, transitively
    # through ``a``'s own symmetry tie -- column_reach's whole point (it
    # answers what a column moves, not what it is named) is that this is
    # not a special case to test around
    unresolved = _vars_driven_cell_escapes(table, start_values)
    assert unresolved == [("vars.A", ["phases.0.cell.a", "phases.0.cell.b",
                                     "phases.0.cell.c"])]

    # nothing is silently passed through: the diagnostic names the driver
    # and every escaped dependent
    diag = _cell_runaway_diagnostic(clamped, unresolved)
    assert diag is not None
    assert set(diag.where) == {"vars.A", "phases.0.cell.a",
                               "phases.0.cell.b", "phases.0.cell.c"}
    assert "vars.A" in diag.message
    assert "phases.0.cell.a" in diag.message
    assert "not pulled back" in diag.message


def test_a_vars_driver_with_no_escaped_dependent_is_not_reported():
    """The bit-identity companion: a free ``vars.X`` driving a cell that
    never leaves the window is not reported at all."""
    from rietx import Refinement
    from rietx.refine import _vars_driven_cell_escapes

    structure, ins = _degenerate_pair(5e-4)
    ref = Refinement(structure, ins, history=False)
    ref.add_variable("A", TRUE_A, min=1.0, max=1000.0)
    ref.tie("phases.0.cell.a", "vars.A")
    table = ref._prepare_table(restore=False)
    table.set_vary(["vars.A", "phases.1.cell.a"], True)
    start_values = table.decode(table.x0())

    assert _vars_driven_cell_escapes(table, start_values) == []


# ----------------------------------------------------------------------
# the failure it exists for: end to end through Refinement.fit
# ----------------------------------------------------------------------
@pytest.fixture(scope="module")
def degenerate_pair_fit():
    """The construction that crashed on main before this fix: two free
    cells sharing one starting value, scale+cell freed together in a single
    stage, followed by a second stage (forcing the next ``compile_model`` —
    exactly where the pre-fix crash actually fired, one stage after the
    escape, not inside the escaping stage itself)."""
    structure, ins = _degenerate_pair(1e-5)
    ref = Refinement(structure, ins, history=False)
    plan = RefinementPlan(stages=[
        Stage("both", ["phases.*.scale", "phases.*.cell.*"], max_iter=20),
        Stage("zero", ["instrument.zero_shift"], max_iter=20),
    ])
    return ref, ref.fit(synthesize(), plan=plan)


def test_the_trigger_construction_no_longer_crashes(degenerate_pair_fit):
    """Before the fix this raised ``ValueError: refusing to enumerate
    reflections ...`` out of the second stage's compile."""
    ref, result = degenerate_pair_fit
    assert result.status in ("converged", "max_iter")


def test_every_free_cell_ends_in_the_physical_range(degenerate_pair_fit):
    ref, _ = degenerate_pair_fit
    for phase in ref.structure.phases:
        a = phase.cell.a.value
        assert 1.0 < a < 100.0, f"{phase.name}: a = {a:.6g} Å ran away"


def test_cell_runaway_is_reported_when_it_fires(degenerate_pair_fit):
    _, result = degenerate_pair_fit
    fired = [d for d in result.diagnostics if d.code == "CELL_RUNAWAY"]
    assert len(fired) == 1, [d.code for d in result.diagnostics]
    finding = fired[0]
    assert finding.level == "warning"
    assert all(p.startswith("phases.") and p.endswith(".cell.a")
              for p in finding.where)
    assert finding.value is not None and finding.value > 0.0


#: the plan shape of the second instance on issue #374 (Le Bail, two phases
#: of one structure type): background, then cell, then widths, then an axial
#: term.  Staging is cumulative, so the cell stays free in every later stage.
_LEBAIL_WIDTHS = ["instrument.profile.u", "instrument.profile.v",
                  "instrument.profile.w"]
_LEBAIL_STAGES = [
    Stage("bkg", ["instrument.background.*"]),
    Stage("cell", ["phases.*.cell.*"]),
    Stage("widths", _LEBAIL_WIDTHS),
    Stage("axial", ["instrument.geometry.axial_sl"]),
]


@pytest.fixture(scope="module")
def lebail_pair_fits():
    """The degenerate pair in Le Bail mode, run twice: the plan cut after its
    ``cell`` stage, so the clamp fires in the stage that produces the answer
    ("end"), and the whole four-stage plan, so the clamp fires in ``cell`` and
    the two later stages re-converge the still-free cell from the window edge
    ("early").  Measured on this construction: every stage ``converged`` bar
    the axial one's ``max_iter``, the ``cell`` stage walks one phase's
    ``a`` to 757.853 Å (cut) / 16.9163 Å (full), and without the clamp the
    full plan returns ``a`` = 16.917 Å with nothing said."""
    out = {}
    for name, stages in (("end", _LEBAIL_STAGES[:2]), ("early", _LEBAIL_STAGES)):
        structure, ins = _degenerate_pair(5e-4)
        ref = Refinement(structure, ins, history=False)
        out[name] = ref.fit(synthesize(), mode="lebail",
                            plan=RefinementPlan(stages=list(stages)))
    return out


def _cell_rows(result, phase: int) -> dict[str, object]:
    by_path = {p.path: p for p in result.parameters}
    return {n: by_path.get(f"phases.{phase}.cell.{n}") for n in "abc"}


def test_a_clamped_cells_stderr_is_withheld(lebail_pair_fits):
    """Review of #385 round 3: the esd is withheld only where the clamp
    happened in the stage that produced the answer, and on every path tied to
    a withheld one (a tie inherits its source's blindness).

    "end": the answer stage clamped ``phases.0.cell.a`` to the window edge,
    so ``a`` — still a free column, never dropped — and the cubic ``b``/``c``
    tied to it all report ``stderr=None``.  "early": the same clamp fired in
    ``cell``, and ``widths``/``axial`` refined the cell again from there, so
    the value reported is a fit result and ``a``, ``b``, ``c`` all carry the
    esd that last stage measured.  Before this fix "early" withheld ``a``'s
    esd off the run's accumulated diagnostics and left ``b``/``c`` theirs."""
    end, early = lebail_pair_fits["end"], lebail_pair_fits["early"]

    fired = [d for d in end.diagnostics if d.code == "CELL_RUNAWAY"]
    assert len(fired) == 1 and "phases.0.cell.a" in fired[0].where
    rows = _cell_rows(end, 0)
    assert rows["a"] is not None and rows["a"].vary is True
    _, edge = cell_window("a", TRUE_A, -math.inf, math.inf,
                          fraction=CELL_SAFETY_FRACTION, angle_deg=CELL_SAFETY_ANGLE_DEG)
    assert rows["a"].value == pytest.approx(edge)   # the window edge, not a fit
    for n, row in rows.items():
        assert row is not None and row.stderr is None, f"end: cell.{n} {row}"

    fired = [d for d in early.diagnostics if d.code == "CELL_RUNAWAY"]
    assert len(fired) == 1 and "phases.0.cell.a" in fired[0].where
    assert [s.name for s in early.stages][-1] == "axial"
    for phase in (0, 1):
        rows = _cell_rows(early, phase)
        for n, row in rows.items():
            assert row is not None and row.stderr is not None, (
                f"early: phases.{phase}.cell.{n} withheld after re-converging")
        # one answer to "is this measured?" across a tie
        assert rows["b"].stderr == pytest.approx(rows["a"].stderr)
        assert rows["c"].stderr == pytest.approx(rows["a"].stderr)


def test_the_rietveld_trigger_reports_the_esd_its_last_stage_measured(
        degenerate_pair_fit):
    """Yue's round-3 probe on ``degenerate_pair_fit``: the clamp fires in
    ``both`` and ``zero`` refines the cell again, so ``phases.0.cell.a``
    (4.15657 Å, not the 4.83 Å edge) reports its esd, and so do ``b``/``c``."""
    _, result = degenerate_pair_fit
    assert any(d.code == "CELL_RUNAWAY" for d in result.diagnostics)
    rows = _cell_rows(result, 0)
    assert rows["a"].stderr is not None
    assert rows["b"].stderr == pytest.approx(rows["a"].stderr)
    assert rows["c"].stderr == pytest.approx(rows["a"].stderr)


def test_a_well_behaved_fit_never_fires_it():
    """The bit-identity claim, on a real fit rather than a unit call: a
    single genuine LaB6 phase, ``mccusker_default``, never comes near the
    safety window (matching ``synthesize()``'s own wavelength/background,
    exactly as ``_absent_phase_inputs()`` does)."""
    structure = make_lab6()
    for n in "abc":
        getattr(structure.phases[0].cell, n).value = TRUE_A
    structure.phases[0].scale.value = 5e-4
    ins = Instrument.debye_scherrer(wavelength=0.4139)
    ins.background = BackgroundChebyshev.with_terms(3)
    ref = Refinement(structure, ins, history=False)
    result = ref.fit(synthesize())
    assert not any(d.code == "CELL_RUNAWAY" for d in result.diagnostics)
    assert result.statistics.rwp < 0.05


def test_absent_phase_fixture_is_unaffected_by_the_new_safety_net():
    """WP-1110's own absent-phase fixture (support-window territory, not the
    joint-degeneracy this fix covers) must land exactly where
    ``test_absent_phase.py`` pins it — this fix must not change that path."""
    from tests.test_absent_phase import _absent_phase_inputs

    structure, ins = _absent_phase_inputs()
    ref = Refinement(structure, ins, history=False)
    result = ref.fit(synthesize(), plan="mccusker_default")
    assert not any(d.code == "CELL_RUNAWAY" for d in result.diagnostics)
    a = ref.structure.phases[0].cell.a.value
    assert a == pytest.approx(TRUE_A, abs=2e-4)


# ----------------------------------------------------------------------
# review of #385 (2026-09-22): theta/Entry.value desync after a clamp
# ----------------------------------------------------------------------
#
# ``clamp_cell_runaway`` mutates ``Entry.value`` directly and the caller
# calls ``table.refresh_ties()`` when it fires, but neither touches the
# ``LSQOutcome.theta`` the stage is carrying — and ``_build_result`` decodes
# *that* ``theta`` (never the table) to build ``y_calc``/``statistics``/
# ``ticks``, while ``RefinedParameter.value`` reads ``Entry.value`` straight
# off the table.  A clamp that fires desynced the two: the reported
# parameter was the clamped one, and the reported fit quality/pattern were
# the pre-clamp (escaped) one's.
#
# On the two-phase construction above, reproducing this against a full
# ``Refinement.fit()`` turned out to need more than the clamp itself: an
# escaped cell generally also drops one phase's support (WP-1301), which
# restores the pre-escape cell, holds it and re-solves — and that *second*
# solve's ``theta`` is a fresh encoder output, never stale to begin with, so
# the desync never reaches the stage's returned outcome on that route
# regardless of whether the fix is present.  Tried and confirmed inert here:
# (a) monkeypatching ``refine.CELL_SAFETY_FRACTION`` down to 0.02 so a modest
# drift trips the clamp — still routed through the same collapse-restore,
# because the joint degeneracy that drives the escape also drives one
# phase's scale towards the other's; (b) a decoy scale two orders larger
# (1e-2) than the fixture above, on the same reasoning.  So this asserts the
# contract directly at ``clamp_cell_runaway``/``_build_result`` — the
# review's own reproduction — which needs no solver at all: a stage's
# ``table.commit(outcome.theta)`` is exactly ``table.commit(entry-set-by-
# hand)`` from ``_build_result``'s point of view.
def test_build_result_uses_the_theta_a_firing_clamp_left_stale():
    """Demonstrates the *contract* directly: fed a stale (pre-clamp) theta,
    ``_build_result`` disagrees with the table it was handed; fed
    ``table.x0()`` re-derived after the clamp, it agrees exactly. This is
    unconditionally true of ``_build_result`` and does not by itself prove
    ``_run_stage``/``fit()`` honour it on a live solve (both thetas are
    supplied here by hand) -- see
    ``test_fit_re_derives_theta_after_a_firing_clamp_with_no_collapse``
    below for the integration check that fails on the pre-fix tree."""
    structure = make_lab6()
    for n in "abc":
        getattr(structure.phases[0].cell, n).value = TRUE_A
    structure.phases[0].scale.value = 5e-4
    ins = Instrument.debye_scherrer(wavelength=0.4139)
    ins.background = BackgroundChebyshev.with_terms(3)

    from rietx.params.vector import ParameterTable

    data = synthesize()
    table = ParameterTable(structure, ins)
    table.set_vary(["phases.0.cell.a"], True)
    start_values = table.decode(table.x0())

    # what a runaway TRF step + ``table.commit(outcome.theta)`` leaves: an
    # escaped cell, freshly committed.  ``stale_theta`` is exactly what
    # ``outcome.theta`` held before this fix re-derived it.
    entry = table.entries[table._paths["phases.0.cell.a"]]
    entry.value = TRUE_A * 1.30  # +30%, outside CELL_SAFETY_FRACTION
    stale_theta = table.x0()

    clamped = clamp_cell_runaway(table, start_values)
    assert len(clamped) == 1, clamped
    table.refresh_ties()
    fixed_theta = table.x0()  # the fix: re-derived after the clamp

    # entry.value is the ground truth either way — RefinedParameter.value
    # reads it directly and is not the thing under test here
    assert entry.value != pytest.approx(TRUE_A * 1.30)  # the clamp moved it

    import numpy as np

    from rietx.model.forward import compile_model
    from rietx.optimize.statistics import compute_statistics

    model = compile_model(structure, ins, data)

    def y_calc_and_rwp_at(theta):
        values = table.decode(theta)
        y_calc = model.evaluate(values)
        y_bkg = model.background(values)
        stats = compute_statistics(model.y_obs, y_calc, model.sigma,
                                   n_free=0, y_background=y_bkg)
        return y_calc, stats.rwp

    y_calc_stale, rwp_stale = y_calc_and_rwp_at(stale_theta)
    y_calc_fixed, rwp_fixed = y_calc_and_rwp_at(fixed_theta)

    # the clamp actually moved the cell, so the two thetas decode to
    # different y_calc/rwp -- otherwise this test would not be exercising
    # anything
    assert not np.allclose(y_calc_stale, y_calc_fixed)
    assert rwp_stale != pytest.approx(rwp_fixed)

    # the postcondition: _build_result called with the RE-DERIVED theta
    # agrees with what the table (== RefinedParameter.value) actually holds;
    # called with the STALE one, it does not.
    result_stale = _build_result(
        model, table, stale_theta, mode="rietveld", status="converged",
        stage_results=[], diagnostics=[], structure=structure)
    result_fixed = _build_result(
        model, table, fixed_theta, mode="rietveld", status="converged",
        stage_results=[], diagnostics=[], structure=structure)

    reported_a = {p.path: p.value for p in result_fixed.parameters}["phases.0.cell.a"]
    assert reported_a == pytest.approx(entry.value)  # both results report this

    # stale: y_calc/rwp reflect the escaped cell, not the reported parameter
    assert np.max(np.abs(np.asarray(result_stale.y_calc) - y_calc_fixed)) > 1.0
    assert result_stale.statistics.rwp != pytest.approx(rwp_fixed)

    # fixed: y_calc/rwp agree exactly with a recompute at the reported value
    assert np.asarray(result_fixed.y_calc) == pytest.approx(y_calc_fixed)
    assert result_fixed.statistics.rwp == pytest.approx(rwp_fixed)


def test_fit_re_derives_theta_after_a_firing_clamp_with_no_collapse(monkeypatch):
    """End-to-end regression, through the public ``Refinement.fit()`` surface
    rather than a direct ``_build_result`` call.

    On the degenerate-pair fixture, ``clamp_cell_runaway`` fires but so does
    WP-1301's collapse-restore (one phase's support drops once its cell is
    pulled back near the true value, since that is what stops it trading
    scale against the other phase) -- and the second, restore-driven solve's
    own ``theta`` is a fresh encoder output that was never stale, so it masks
    the very bug this checks for regardless of whether the fix is present
    (confirmed empirically: this construction, and two narrower-window
    variants, all passed even against the pre-fix tree). So
    ``_unsupported_phase_paths`` is patched to report no collapse ever, which
    does not change what the clamp does (still fires, still pulls the cell
    back to the same window edge) and isolates exactly the branch the fix
    touches: the stage's own outcome, clamped and returned directly to
    ``_build_result``, with no second solve in between.

    Rather than recompiling a second model to compare ``y_calc`` against (a
    fresh ``compile_model`` call makes its own frozen-window/FCJ-node sizing
    decisions -- WP-1110's own "Frozen-per-stage discreteness" invariant --
    which need not agree with the live fit's compiled model and produced a
    large, unrelated mismatch when tried), this spies on the real
    ``_build_result`` call ``fit()`` makes internally and checks its
    ``theta`` argument decodes to exactly what the SAME table's
    ``Entry.value``\\ s hold at that moment -- the literal postcondition the
    fix restores, on the real code path, with no independent model build to
    disagree about.
    """
    import sys

    refine_module = sys.modules["rietx.refine"]  # see the other test's note
    monkeypatch.setattr(refine_module, "_unsupported_phase_paths",
                        lambda *a, **k: [])

    captured = {}
    real_build_result = refine_module._build_result

    def spy(model, table, theta, **kwargs):
        captured["theta"] = theta
        captured["entry_values"] = {e.path: e.value for e in table.entries}
        captured["decoded"] = table.decode(theta)
        return real_build_result(model, table, theta, **kwargs)

    monkeypatch.setattr(refine_module, "_build_result", spy)

    structure, ins = _degenerate_pair(1e-5)
    ref = Refinement(structure, ins, history=False)
    plan = RefinementPlan(stages=[
        Stage("both", ["phases.*.scale", "phases.*.cell.*"], max_iter=20),
    ])
    data = synthesize()
    result = ref.fit(data, plan=plan)
    assert any(d.code == "CELL_RUNAWAY" for d in result.diagnostics)
    assert captured, "the spy never ran -- fit() must call _build_result by name"

    for path, entry_value in captured["entry_values"].items():
        assert captured["decoded"][path] == pytest.approx(entry_value, abs=1e-9), (
            f"{path}: table.decode(theta)={captured['decoded'][path]!r} but "
            f"Entry.value={entry_value!r} -- the theta _build_result received "
            f"disagrees with the table it came from")


# ----------------------------------------------------------------------
# review of #385 (2026-09-22): the CELL_RUNAWAY message named the wrong
# unit and the wrong window for an angle
# ----------------------------------------------------------------------
def _monoclinic_phase(beta: float) -> Structure:
    cell = Cell(a=Parameter(value=5.0, min=0.1), b=Parameter(value=6.0, min=0.1),
               c=Parameter(value=7.0, min=0.1), alpha=Parameter(value=90.0),
               beta=Parameter(value=beta), gamma=Parameter(value=90.0))
    return Structure(phases=[Phase(
        name="probe", space_group="P 1 2/m 1", cell=cell,
        atoms=[Atom(label="X", species="Si", x=Parameter(value=0.0),
                    y=Parameter(value=0.0), z=Parameter(value=0.0))])])


def test_a_free_beta_outside_the_angle_window_is_clamped_and_reported_in_degrees():
    """A monoclinic phase's free ``beta`` escaping the ±``CELL_SAFETY_ANGLE_DEG``
    window must be reported in degrees, at the angle window — never in Å at
    the length fraction, which is what every ``a/b/c`` path in this file's
    other tests correctly gets."""
    from rietx.params.vector import ParameterTable

    structure = _monoclinic_phase(98.3)
    ins = Instrument.debye_scherrer(wavelength=1.5406)
    table = ParameterTable(structure, ins)
    hits = table.set_vary(["phases.0.cell.beta"], True)
    assert "phases.0.cell.beta" in hits
    start_values = table.decode(table.x0())

    entry = table.entries[table._paths["phases.0.cell.beta"]]
    entry.value = 98.3 + 10.0  # +10 deg, outside the +/-CELL_SAFETY_ANGLE_DEG window
    clamped = clamp_cell_runaway(table, start_values)
    assert len(clamped) == 1
    path, old, new = clamped[0]
    assert path == "phases.0.cell.beta"
    lo, hi = cell_window("beta", 98.3, -math.inf, math.inf,
                         fraction=CELL_SAFETY_FRACTION,
                         angle_deg=CELL_SAFETY_ANGLE_DEG)
    assert new == pytest.approx(hi)

    diag = _cell_runaway_diagnostic(clamped)
    assert diag is not None
    assert "Å" not in diag.message
    assert "15%" not in diag.message
    assert "°" in diag.message
    assert f"±{CELL_SAFETY_ANGLE_DEG:.0f}°" in diag.message


def test_a_mixed_length_and_angle_clamp_names_both_windows():
    """A stage that clamps both a length and an angle in the same firing
    must not collapse to either unit alone."""
    diag = _cell_runaway_diagnostic([
        ("phases.0.cell.a", 5.403580000000001, 4.83009),
        ("phases.0.cell.beta", 108.3, 104.3),
    ])
    assert diag is not None
    assert "Å" in diag.message and "°" in diag.message
    assert f"±{CELL_SAFETY_FRACTION:.0%}" in diag.message
    assert f"±{CELL_SAFETY_ANGLE_DEG:.0f}°" in diag.message


# ----------------------------------------------------------------------
# issue #374's second instance: Le Bail, two phases of one structure type,
# cell lengths gone negative with every stage ``converged``
# ----------------------------------------------------------------------
_ORTHO = (4.02, 4.21, 4.43)


def _ortho_phase(name: str, f: float) -> Phase:
    a, b, c = (f * v for v in _ORTHO)
    return Phase(
        name=name, space_group="P m m m",
        cell=Cell(a=Parameter(value=a, vary=True), b=Parameter(value=b, vary=True),
                  c=Parameter(value=c, vary=True), alpha=Parameter(value=90.0),
                  beta=Parameter(value=90.0), gamma=Parameter(value=90.0)),
        atoms=[Atom(label="La", species="La", x=Parameter(value=0.0),
                    y=Parameter(value=0.0), z=Parameter(value=0.0)),
               Atom(label="B1", species="B", x=Parameter(value=0.2),
                    y=Parameter(value=0.5), z=Parameter(value=0.5))])


def _ortho_pattern():
    import numpy as np

    from rietx.model.forward import compile_model
    from rietx.params.vector import ParameterTable
    from rietx.schemas.pattern import PatternData

    truth = Structure(phases=[_ortho_phase("p", 1.0)])
    ins = Instrument.debye_scherrer(wavelength=0.4139)
    ins.profile.w.value = 0.002
    ins.background = BackgroundChebyshev(
        coefficients=[Parameter(value=v) for v in (200.0, -20.0, 5.0)])
    tt = np.arange(3.0, 24.0, 0.005)
    empty = PatternData(two_theta=tt.tolist(), intensity=np.zeros_like(tt).tolist())
    model = compile_model(truth, ins, empty, mode="rietveld")
    table = ParameterTable(truth, ins)
    y = model.evaluate(table.decode(table.x0())) * 2e4
    y = np.random.default_rng(7).poisson(np.maximum(y, 1.0)).astype(float)
    return PatternData(two_theta=model.tt.tolist(), intensity=y.tolist())


def test_a_negative_cell_length_in_lebail_is_caught_by_the_same_clamp(monkeypatch):
    """Two orthorhombic phases of one structure type with cells 0.8 % apart,
    Le Bail, the plan freeing background → cell → widths → an axial term.
    The ``cell`` solve's answer is replaced by the issue's shape — a ≈ −1.0e4,
    b ≈ −5.9e4, c ≈ 1.9e5 Å, a *positive* volume, so no degenerate-metric
    refusal can see it — and the stage still reports ``converged``.

    No positivity guard is needed beside the clamp: its window is a band
    around the stage's positive starting length (±15 %, and ±6° inside
    (0°, 180°) for an angle), so a length ≤ 0 is outside it by construction
    and is pulled back like any other escape, in Le Bail mode as in Rietveld.
    Measured without the clamp: the ``widths`` compile refuses to enumerate
    reflections for the escaped cell (``ValueError``); a run whose last stage
    escaped would have returned it."""
    import dataclasses
    import sys

    refine_module = sys.modules["rietx.refine"]
    real = refine_module.run_least_squares
    issue_shape = dict(zip("abc", (-1.0e4, -5.9e4, 1.9e5), strict=True))

    def solve(model, table, **kwargs):
        outcome = real(model, table, **kwargs)
        if kwargs.get("stage") != "cell":
            return outcome
        table.commit(outcome.theta)
        by_path = {e.path: e for e in table.entries}
        for n, v in issue_shape.items():
            by_path[f"phases.1.cell.{n}"].value = v
        return dataclasses.replace(outcome, theta=table.x0())

    monkeypatch.setattr(refine_module, "run_least_squares", solve)
    ins = Instrument.debye_scherrer(wavelength=0.4139)
    ins.background = BackgroundChebyshev.with_terms(3)
    ref = Refinement(Structure(phases=[_ortho_phase("p", 1.0),
                                       _ortho_phase("twin", 1.008)]),
                     ins, history=False)
    result = ref.fit(_ortho_pattern(), mode="lebail", plan=RefinementPlan(stages=[
        Stage("bkg", ["instrument.background.*"]),
        Stage("cell", ["phases.*.cell.*"]),
        Stage("widths", ["instrument.profile.u", "instrument.profile.v",
                         "instrument.profile.w"]),
        Stage("axial", ["instrument.geometry.axial_sl"]),
    ]))

    assert all(s.status == "converged" for s in result.stages)
    fired = [d for d in result.diagnostics if d.code == "CELL_RUNAWAY"]
    assert len(fired) == 1
    assert fired[0].where == [f"phases.1.cell.{n}" for n in "abc"]
    for n in "abc":
        assert f"phases.1.cell.{n} {issue_shape[n]:.6g} -> " in fired[0].message
    for phase in ref.structure.phases:
        assert all(v > 1.0 for v in phase.cell.lengths_angles()[:3]), phase.name


@pytest.mark.parametrize("beta", [-3.0, 0.0, 180.0, 185.0])
def test_an_angle_outside_zero_to_180_is_clamped(beta):
    """The angle half of the positivity question: a free β the solve left
    at or past 0° or 180° is outside ±6° of a physical start, so the clamp
    pulls it back to the window edge — no second test needed."""
    from rietx.params.vector import ParameterTable

    table = ParameterTable(_monoclinic_phase(95.0), Instrument.debye_scherrer(
        wavelength=0.4139))
    table.set_vary(["phases.0.cell.beta"], True)
    start_values = table.decode(table.x0())
    next(e for e in table.entries if e.path == "phases.0.cell.beta").value = beta
    clamped = clamp_cell_runaway(table, start_values)
    assert [(p, old) for p, old, _ in clamped] == [("phases.0.cell.beta", beta)]
    assert 0.0 < clamped[0][2] < 180.0

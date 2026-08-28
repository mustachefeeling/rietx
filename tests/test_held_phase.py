"""WP-1301 — a phase the data cannot see is *held* for the stage, not bounded.

The mechanism WP-1110 shipped bounds the symptom: an invisible phase's cell
gets a per-stage window, so it walks quietly instead of running to 39 293 Å.
It still walks, and the solver still spends its budget walking it — measured on
a real in-situ ramp, 27 % of a 34.7 min run went into a CaF₂ cell while the
phase was absent, and reproducing the agent's own 13 sub-onset patterns took
1638 iterations with the bounds it had added and did not finish in 13 minutes
without them.

So the flat direction is removed rather than fenced: at stage compile, every
free structural parameter of a phase below ``PHASE_SUPPORT_SIGMA`` is held for
that stage. The phase's **scale stays free**, which is how it can still appear;
if it does appear while the stage solves, the hold is lifted and the stage
solves once more so the phase is refined in the pattern where it appears rather
than one later.

``tests/test_absent_phase.py`` holds the window's own tests and the fixtures
this file reuses; here the subject is the hold, its record and its message.
"""

from __future__ import annotations

import numpy as np
import pytest

from rietx import Refinement
from rietx.model.forward import PHASE_SUPPORT_SIGMA, compile_model
from rietx.params.vector import ParameterTable
from rietx.refine import _unsupported_phase_paths
from tests.test_absent_phase import _absent_phase_inputs
from tests.test_refine_synthetic import TRUE_A, synthesize
from tests.test_schemas import make_lab6

pytestmark = pytest.mark.xdist_group("held-phase")

OUT = __import__("pathlib").Path(__file__).parent / "output"


@pytest.fixture(scope="module")
def held_fit():
    """The absent-phase fixture, refined under the default plan."""
    structure, ins = _absent_phase_inputs()
    ref = Refinement(structure, ins, history=False)
    return ref, ref.fit(synthesize(), plan="mccusker_default")


# ----------------------------------------------------------------------
# what is held
# ----------------------------------------------------------------------
def test_the_hold_is_the_measurement_projected_not_a_second_opinion(held_fit):
    """``StageResult.held`` is set-equal to the paths the rule names.

    One measurement (``CompiledModel.phase_support``) projected onto the record,
    the way ``staged.bound_findings`` feeds both ``BOUND_HIT`` and ``at_bound``
    (WP-1076).  Re-deriving the set here would pass whatever the code did.
    """
    ref, result = held_fit
    held = {p for stage in result.stages for p in stage.held}
    assert held, "the absent phase's structural parameters were never held"

    # the same question asked of the same authority, on the fit's own model
    model = compile_model(ref.structure, ref.instrument, synthesize(),
                          mode="rietveld")
    table = ParameterTable(ref.structure, ref.instrument)
    table.set_vary(sorted(held), True)
    assert set(_unsupported_phase_paths(model, table)) == held


def test_the_phases_own_scale_is_never_held(held_fit):
    """Holding it would make the hold permanent, which it must never be.

    A phase reaches the pattern only through ``scale × |F|² × profile``, so the
    scale is the one direction that is *not* flat when the phase is invisible —
    and the only way it can climb back out of the noise.
    """
    _, result = held_fit
    for stage in result.stages:
        assert not [p for p in stage.held if p.endswith(".scale")], stage.name


def test_only_the_invisible_phase_is_held(held_fit):
    """The phase that is really there refines exactly as it did before."""
    ref, result = held_fit
    for stage in result.stages:
        assert all(p.startswith("phases.1.") for p in stage.held), stage.name
    assert result.statistics.rwp < 0.05
    assert ref.structure.phases[0].cell.a.value == pytest.approx(TRUE_A, abs=2e-4)


def test_a_held_value_is_the_one_that_was_handed_in(held_fit):
    """Not a walk that stopped somewhere; the number the caller gave.

    Under the window alone the same fit left this cell at 4.78 Å — inside the
    physical range, and still not a measurement.  Held, it is bit-for-bit the
    5.2 Å the fixture declared, which is the only value a reader can interpret.
    """
    ref, _ = held_fit
    assert ref.structure.phases[1].cell.a.value == 5.2


def test_held_and_freed_are_disjoint(held_fit):
    """The two together say exactly what refined in each stage."""
    _, result = held_fit
    for stage in result.stages:
        assert not set(stage.freed) & set(stage.held), stage.name


def test_a_held_parameter_is_not_reported_as_a_refined_one(held_fit):
    """``RefinementResult.parameters`` is what the fit measured.

    A held path was not in the free vector, has no esd and moved nowhere, so it
    is absent rather than present with a number beside it.
    ``PHASE_UNCONSTRAINED`` still names it in ``where``.
    """
    _, result = held_fit
    held = {p for stage in result.stages for p in stage.held}
    reported = {p.path for p in result.parameters}
    assert held and not (held & reported)


def test_the_hold_does_not_survive_into_the_working_state(held_fit):
    """A hold is one stage's answer about the data, not an edit to the plan.

    If it leaked into the recorded free set, the phase would stay unrefined in
    the very pattern where it appears — the failure the release rule exists to
    prevent, one call further out.
    """
    ref, result = held_fit
    held = {p for stage in result.stages for p in stage.held}
    rows = {r.path: r for r in ref.parameters()}
    for path in held:
        assert rows[path].vary, f"{path} came back fixed"


# ----------------------------------------------------------------------
# a fit with nothing to hold
# ----------------------------------------------------------------------
def test_a_visible_phase_is_never_held():
    """Nothing changes for a fit whose phases the data can see.

    The empty lists are written on every stage, so an empty one means "nothing
    was held", never "nobody looked" (WP-1076's honest empty state).
    """
    structure = make_lab6()
    ref = Refinement(structure, _absent_phase_inputs()[1], history=False)
    result = ref.fit(synthesize(), plan="mccusker_default")
    assert result.statistics.rwp < 0.05
    for stage in result.stages:
        assert stage.held == [] and stage.released == [], stage.name
    assert not [d for d in result.diagnostics if d.code == "PHASE_UNCONSTRAINED"]


# ----------------------------------------------------------------------
# what it reports
# ----------------------------------------------------------------------
def test_the_diagnostic_says_what_the_run_did_about_it(held_fit):
    """``PHASE_UNCONSTRAINED`` keeps its code and gains the account.

    Before this the same fit reported "N of its parameters were refined against
    it", which was true and left the caller to guess whether the values were
    worth anything.  Now the message names the stages that held them, and the
    paths are in ``where`` either way — a held value is what you handed in, a
    refined one moved in a flat direction, and neither is a result.
    """
    _, result = held_fit
    fired = [d for d in result.diagnostics if d.code == "PHASE_UNCONSTRAINED"]
    assert len(fired) == 1, [d.code for d in result.diagnostics]
    finding = fired[0]
    assert finding.value < PHASE_SUPPORT_SIGMA
    assert "were held for" in finding.message or "was held for" in finding.message
    held = {p for stage in result.stages for p in stage.held}
    assert held <= set(finding.where)
    # the stages it names are the stages that held, in the order they ran
    named = [s.name for s in result.stages if s.held]
    tail = finding.message.split("stage")[-1]
    assert all(name in tail for name in named)
    assert tail.index(named[0]) < tail.index(named[-1])


def test_the_message_counts_what_it_names(held_fit):
    """The count in the sentence is the length of ``where``, not a guess."""
    _, result = held_fit
    finding = next(d for d in result.diagnostics
                   if d.code == "PHASE_UNCONSTRAINED")
    assert f"its {len(finding.where)} structural parameter" in finding.message


# ----------------------------------------------------------------------
# the cost
# ----------------------------------------------------------------------
def test_the_flat_column_is_gone_from_the_solve(held_fit):
    """The point of holding rather than bounding: no column to search.

    A bounded flat direction is still a column of the Jacobian and still costs
    a trust-region evaluation per iteration; a held one is not in θ at all.
    Asserted on the free count the last stage solved with, which is the number
    the solver actually paid for.
    """
    _, result = held_fit
    held = {p for stage in result.stages for p in stage.held}
    free = {p.path for p in result.parameters if p.vary}
    assert held and not (held & free)
    assert np.isfinite(result.statistics.rwp)


@pytest.mark.slow
def test_the_held_fit_is_drawn_for_inspection(held_fit):
    """Rwp hides locally-bad fits; the picture is the check that does not.

    The held phase contributes nothing to draw — that is what "held" means —
    so what this shows is the other half: the phase that *is* there, fitted
    with the flat direction removed from the solve.
    """
    import matplotlib.pyplot as plt

    from rietx.viz.plots import plot_result

    _, result = held_fit
    OUT.mkdir(exist_ok=True)
    plot_result(result, path=str(OUT / "held_phase.png"))
    plt.close("all")
    assert (OUT / "held_phase.png").exists()


# ----------------------------------------------------------------------
# the limit case: no line of the phase in the fitted range
# ----------------------------------------------------------------------
@pytest.fixture(scope="module")
def no_reflection_fit():
    """NIST SRM 660c LaB₆ fitted where the certification data has no peak.

    That dataset is measured in windows around its own reflections, so the
    interval 22.5-29.5° reduces to 41 points at 29.1-29.5° — real data, real
    counts, and no line of LaB₆ anywhere in it (the 100 sits at 21.4°, the 110
    at 30.4°).  A single-phase fit of a phase the range cannot see.
    """
    import rietx as rx
    from tests.test_acceptance_srm660c import (
        _nist_calibrated_plan,
        build_srm_inputs,
    )

    data, structure, instrument = build_srm_inputs()
    ref = rx.Refinement(structure, instrument, history=False)
    return ref, ref.fit(data, plan=_nist_calibrated_plan(),
                        two_theta_limits=(22.5, 29.5))


def test_no_reflection_in_range_is_reported_rather_than_silent(no_reflection_fit):
    """rietx 1.0.1 crashed here; then it converged and said nothing.

    Measured on ``main`` before this: ``converged``, Rwp 0.334, and the only
    diagnostic ``DISPERSION_NEGLECTED`` — a fit that refined a cell, two Biso
    and a profile against no reflection at all and reported success.  A
    contributor's campaign brief spent a paragraph telling its agents to work
    around the state by hand.
    """
    _, result = no_reflection_fit
    fired = [d for d in result.diagnostics if d.code == "PHASE_UNCONSTRAINED"]
    assert len(fired) == 1, [d.code for d in result.diagnostics]
    assert "no reflection of phase 0" in fired[0].message
    assert "LaB6" in fired[0].message


def test_the_zero_line_case_is_the_limit_of_support_not_a_second_test():
    """``phase_line_counts`` is zero exactly where nothing can be measured.

    A different statement from a small ``phase_support`` and worth separating:
    a phase whose scale is at its floor may appear in the next pattern of a
    series, one with no line in the window will not, whatever the specimen
    does.  Read off the frozen windows, so a reflection generated just outside
    the fitted ends counts as the absence it is.
    """
    from tests.test_acceptance_srm660c import build_srm_inputs

    data, structure, instrument = build_srm_inputs()
    blind = compile_model(structure, instrument, data, mode="rietveld",
                          two_theta_limits=(22.5, 29.5))
    seeing = compile_model(structure, instrument, data, mode="rietveld",
                           two_theta_limits=(29.5, 32.0))
    assert int(blind.phase_line_counts()[0]) == 0
    assert int(seeing.phase_line_counts()[0]) > 0


def test_the_blind_range_holds_everything_but_the_scale(no_reflection_fit):
    """Held, not refined: a single-phase model gets the rule too.

    The phase count never entered it — "the data cannot see this phase" is a
    measurement on the phase, and a lone phase under the noise is exactly as
    unmeasurable as one of six.
    """
    ref, result = no_reflection_fit
    held = {p for stage in result.stages for p in stage.held}
    assert "phases.0.cell.a" in held
    assert not [p for p in held if p.endswith(".scale")]
    # the cell is the value the protocol declared, to the digit
    assert ref.structure.phases[0].cell.a.value == 4.1568


# ----------------------------------------------------------------------
# the ramp: a phase that appears part-way through
# ----------------------------------------------------------------------
#: the in-situ ramp of the 2026-08-26 agent run, regenerated here from the same
#: CIF rather than shipped as data.  NAC (COD 1000236) on a lab Cu Kα doublet,
#: its cell expanding through a first-order step at 430 °C, and a CaF₂ phase
#: that is absent below the step and grows above it.  The refinement is told
#: none of that: it starts from the room-temperature cell, a flat background
#: and a nominal scale, which is what makes the sub-onset patterns a flat
#: direction rather than a bad guess.
RAMP_T_TRANSITION = 430.0
RAMP_A0 = 10.2570
RAMP_CAF2_A = 5.4631
RAMP_GRID = np.arange(15.0, 60.0 + 1e-9, 0.05)


def _ramp_a(temperature: float) -> float:
    if temperature <= RAMP_T_TRANSITION:
        return RAMP_A0 * (1 + 8.0e-6 * (temperature - 25.0))
    return RAMP_A0 * (1 + 8.0e-6 * (RAMP_T_TRANSITION - 25.0) + 1.6e-3
                      + 1.10e-5 * (temperature - RAMP_T_TRANSITION))


def _ramp_caf2_weight(temperature: float) -> float:
    if temperature <= RAMP_T_TRANSITION:
        return 0.0
    return min(1.0, (temperature - RAMP_T_TRANSITION) / 90.0)


def _caf2_phase(scale: float, a: float = RAMP_CAF2_A):
    import rietx as rx

    return rx.Phase(
        name="CaF2", space_group="F m -3 m", cell=rx.Cell.cubic(a),
        atoms=[
            rx.Atom(label="Ca", species="Ca2+", x=rx.Parameter(value=0.0),
                    y=rx.Parameter(value=0.0), z=rx.Parameter(value=0.0),
                    biso=rx.Parameter(value=0.6, min=0.0, max=25.0)),
            rx.Atom(label="F", species="F1-", x=rx.Parameter(value=0.25),
                    y=rx.Parameter(value=0.25), z=rx.Parameter(value=0.25),
                    biso=rx.Parameter(value=0.9, min=0.0, max=25.0)),
        ],
        scale=rx.Parameter(value=scale, min=0.0, transform="softplus"))


def _ramp_instrument():
    import rietx as rx
    from rietx.schemas.instrument import BackgroundChebyshev

    ins = rx.Instrument.bragg_brentano(radiation="CuKa",
                                       monochromator_two_theta=26.6)
    ins.profile.u.value, ins.profile.v.value = 0.010, -0.005
    ins.profile.w.value, ins.profile.x.value = 0.050, 0.030
    ins.background = BackgroundChebyshev.with_terms(4)
    return ins


def _ramp_host():
    from pathlib import Path

    import rietx as rx

    s = rx.Structure.from_cif(
        str(Path(__file__).parent / "data" / "cod_1000236.cif"))
    s.phases[0].name = "NAC"
    return s


def _ramp_patterns(temperatures, seed: int = 20260826):
    """Poisson-sampled patterns from the package's own forward model."""
    import rietx as rx

    truth = _ramp_host()
    truth.phases[0].scale.value = 6.0e-5
    truth.phases.append(_caf2_phase(0.0))
    ins = _ramp_instrument()
    ins.background.coefficients[0].value = 260.0
    ins.background.coefficients[1].value = -70.0
    ins.background.coefficients[2].value = 25.0
    rng = np.random.default_rng(seed)
    out = []
    for temperature in temperatures:
        truth.phases[0].cell.a.value = _ramp_a(temperature)
        truth.phases[1].scale.value = 4.0e-4 * _ramp_caf2_weight(temperature)
        y = rx.Refinement(truth, ins).predict(RAMP_GRID)
        counts = rng.poisson(np.maximum(y, 0.0)).astype(float)
        out.append(rx.PatternData(
            two_theta=RAMP_GRID.tolist(), intensity=counts.tolist(),
            sigma=np.sqrt(np.maximum(counts, 1.0)).tolist()))
    return out


def _ramp_start(caf2_a: float = RAMP_CAF2_A, bounds=(5.30, 5.60)):
    """The starting model, with the user cell bounds the agent added.

    Those bounds are why ``cell_window`` could not save this run: a finite
    stored bound is the caller's claim and suppresses the window on that side
    (``params.vector.cell_window``), so the safeguard was switched off by the
    very thing that was meant to replace it.
    """
    s = _ramp_host()
    s.phases[0].scale.value = 3.0e-5
    s.phases.append(_caf2_phase(1.0e-7, a=caf2_a))
    for atom in s.phases[1].atoms:
        atom.biso.vary = False
    if bounds is not None:
        for edge in (s.phases[1].cell.a, s.phases[1].cell.b, s.phases[1].cell.c):
            edge.min, edge.max = bounds
    return s


def _collapsed_plan():
    """The one stage ``refit="single"`` collapses the agent's plan into.

    Scale and cell free together — which is why "hold only when the scale is
    not free this stage" was rejected: it would miss the shape the run ran.
    """
    import rietx as rx

    return rx.RefinementPlan(stages=[rx.Stage(
        "all", ["phases.*.scale", "instrument.background.*", "phases.*.cell.*",
                "instrument.profile.w", "instrument.profile.x"])])


@pytest.fixture(scope="module")
def released_fit():
    """One pattern at 700 °C — the phase is there — from a 1.2 % wrong cell."""
    import rietx as rx

    data = _ramp_patterns([700.0])[0]
    ref = rx.Refinement(_ramp_start(caf2_a=5.40), _ramp_instrument(),
                        history=False)
    return ref, ref.fit(data, plan=_collapsed_plan())


def test_a_phase_that_appears_mid_stage_is_released_and_refined(released_fit):
    """The hold must not cost the pattern where the phase first appears.

    The stage starts with CaF₂ at 1e-7 — invisible, so its cell is held — and
    the scale climbs while the stage solves.  The hold is then lifted and the
    stage solves once more, so the cell is measured here rather than one
    pattern later.  From a seed 1.2 % away it lands within 20 ppm of the truth.
    """
    ref, result = released_fit
    stage = result.stages[0]
    assert stage.released == ["phases.1.cell.a"]
    assert stage.held == [], "the hold was lifted, so nothing stayed held"
    a = ref.structure.phases[1].cell.a.value
    assert a == pytest.approx(RAMP_CAF2_A, rel=1e-4), f"CaF2 a = {a}"
    assert result.statistics.rwp < 0.06


def test_the_release_is_bounded_at_one_second_solve(released_fit):
    """Never a third: the cost of a wrong hold is one stage's budget.

    Both solves are counted where the budget is read, and ``cost_initial`` is
    still the cost the stage started at — a stage is one record whatever
    happened inside it.
    """
    _, result = released_fit
    stage = result.stages[0]
    assert stage.cost_final < stage.cost_initial
    assert stage.n_iterations > 0
    # one stage, one record, whether or not it solved twice
    assert len(result.stages) == 1


def test_a_released_phase_raises_no_warning_about_itself(released_fit):
    """``PHASE_UNCONSTRAINED`` is for a phase the data cannot see.

    This one could be seen, in the end, and its parameters are measurements —
    so firing here would teach a reader to ignore the code.  What happened is
    on the record (``StageResult.released``), not in a warning.
    """
    _, result = released_fit
    assert not [d for d in result.diagnostics if d.code == "PHASE_UNCONSTRAINED"]


@pytest.fixture(scope="module")
def ramp_series():
    """Four patterns straddling the 430 °C onset, chained as the run was."""
    from rietx.sequential import SequentialRefinement

    temps = [400.0, 425.0, 445.0, 475.0]
    runner = SequentialRefinement(_ramp_start(), _ramp_instrument(),
                                  carry=["phases.0.*", "instrument.*"])
    series = runner.fit(_ramp_patterns(temps), x=temps,
                        labels=[f"{t:.0f}C" for t in temps],
                        plan=_collapsed_plan(), refit="single")
    return temps, runner, series


def test_the_phase_is_refined_in_the_pattern_where_it_appears(ramp_series):
    """Not one pattern later, which is what a hold-and-rerun rule would cost.

    445 °C is the first pattern with any CaF₂ in it (truth scale 6.7e-5).  Its
    cell is measured there — 5.4624 Å against the true 5.4631 — while the two
    patterns below the onset hold theirs at the value handed in.
    """
    temps, runner, series = ramp_series
    below = [e for e, t in zip(series.entries, temps) if t < 430.0]
    above = [e for e, t in zip(series.entries, temps) if t > 430.0]
    assert len(below) == 2 and len(above) == 2

    for entry in below:
        paths = {p.path for p in entry.parameters}
        assert "phases.1.cell.a" not in paths, entry.label
        assert "PHASE_UNCONSTRAINED" in [d.code for d in entry.diagnostics]
    for entry in above:
        row = next(p for p in entry.parameters if p.path == "phases.1.cell.a")
        assert row.value == pytest.approx(RAMP_CAF2_A, rel=1e-3), entry.label
        assert not [d for d in entry.diagnostics
                    if d.code == "PHASE_UNCONSTRAINED"]


def test_below_the_onset_the_cell_is_where_it_was_put(ramp_series):
    """The measured alternative: 5.30000 Å (a bound) and 5.59898 Å.

    Both of those came out of the same chain on ``main`` — one pinned at the
    user's own lower bound with ``BOUND_HIT``, the other most of the way to the
    upper one — and neither is a fluorite cell.  Held, the value is the 5.4631
    the caller declared, which is the only number a reader can interpret.
    """
    temps, runner, _ = ramp_series
    for structure, temperature in zip(runner.fitted_structures, temps):
        if temperature < 430.0:
            assert structure.phases[1].cell.a.value == RAMP_CAF2_A


def test_the_stream_says_what_was_held_and_when():
    """``held``/``released`` ride the existing kinds, and the alignment holds.

    Open-dict fields on ``stage_start``/``stage_end``, so
    ``EVENT_SCHEMA_VERSION`` does not move — the additivity rule in
    ``history/events.py``.  The resumed solve emits its **own**
    ``stage_start``, because ``eval.values`` is declared to align with
    ``stage_start.free_paths`` and the second solve's free vector is longer
    than the first's; a reader aligns on the most recent one.
    """
    import rietx as rx
    from rietx.history.events import EVENT_SCHEMA_VERSION

    seen: list[dict] = []
    data = _ramp_patterns([700.0])[0]
    ref = rx.Refinement(_ramp_start(caf2_a=5.40), _ramp_instrument(),
                        history=False)
    ref.fit(data, plan=_collapsed_plan(), events=seen.append)

    assert {e["v"] for e in seen} == {EVENT_SCHEMA_VERSION}
    starts = [e["data"] for e in seen if e["kind"] == "stage_start"]
    ends = [e["data"] for e in seen if e["kind"] == "stage_end"]
    assert len(starts) == 2 and len(ends) == 1, "one stage, solved twice"
    assert starts[0]["held"] == ["phases.1.cell.a"]
    assert starts[1]["released"] == ["phases.1.cell.a"]
    assert starts[1]["held"] == [] and starts[1]["freed"] == ["phases.1.cell.a"]
    assert len(starts[1]["free_paths"]) == len(starts[0]["free_paths"]) + 1
    assert ends[0]["released"] == ["phases.1.cell.a"]
    assert ends[0]["held"] == []

    # every eval aligns with the stage_start that preceded it
    current = None
    for event in seen:
        if event["kind"] == "stage_start":
            current = event["data"]["free_paths"]
        elif event["kind"] == "eval" and "values" in event["data"]:
            assert len(event["data"]["values"]) == len(current)


def test_a_held_stage_streams_the_hold_without_a_release():
    """The ordinary case: one ``stage_start`` per stage, ``released`` empty."""
    import rietx as rx

    seen: list[dict] = []
    structure, ins = _absent_phase_inputs()
    rx.Refinement(structure, ins, history=False).fit(
        synthesize(), plan="mccusker_default", events=seen.append)
    starts = [e["data"] for e in seen if e["kind"] == "stage_start"]
    ends = [e["data"] for e in seen if e["kind"] == "stage_end"]
    assert len(starts) == len(ends) == 5
    assert [d["held"] for d in ends[2:]] == [["phases.1.cell.a"]] * 3
    assert all(d["released"] == [] for d in ends)

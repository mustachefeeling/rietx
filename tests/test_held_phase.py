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

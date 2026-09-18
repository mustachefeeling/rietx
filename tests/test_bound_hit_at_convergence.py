"""``BOUND_HIT`` describes the converged vector, not a stage that is over.

WP-1310, issue #231.  A staged plan exists so that an early stage can absorb an
error a later one corrects, so a parameter pressed onto its limit in stage 1 and
back in the interior at the end is the plan *working*.  Until this, that stage's
finding was appended to the result's diagnostics as each stage ended and nothing
re-evaluated it, so a fully successful fit carried ``"<path> refined to its
bound"`` about a parameter five orders of magnitude from one.

**It is convincing, which is why it was worth a fix rather than a note.**  On a
real capillary synchrotron fit the same warning fired on
``capillary_offset_along_beam`` in five of five fits and was read as the
specimen offset being pinned and the cell therefore untrustworthy; re-running at
±1, ±5 and ±20 mm gave results bit-identical to six significant figures, the
offset converging at 3.3 % of the ±1 mm bound and on the opposite side of zero
from the early-stage hit.  Two rounds of analysis went into a warning about a
limit the answer was nowhere near.

The fixture is the repo's own ``make_lab6`` with a tight (±0.02°) zero shift and
a 500 ppm cell error for it to absorb, which is the issue's own construction.

**WP-1434, issue #273** then replaced the test itself.  Asking how *close* the
value sits to its limit answers a question about when the solver stopped: TRF
keeps its iterates strictly feasible, so the same binding bound lands 6.6e-15
away at ``ftol`` 1e-9 and 1.2e-10 away at 1e-4, and only the first fired.  The
test is now a conjunction — near the limit in units of the parameter's own esd,
**and** the residual still not orthogonal to that column with the sign pointing
out of the feasible set.  The rows below are the same fixture swept over
``ftol``, which is what makes the two halves visible: the gradient alone cannot
tell a bound that carried load from a stage that stopped early while still
travelling towards one (both push outward, 6.6e-2 against a binding range of
1.5e-2 … 2.1e-1), and the distance alone cannot tell either of them from a free
optimum that happens to sit nearby.
"""

from __future__ import annotations

import dataclasses
import sys
from pathlib import Path

import numpy as np
import pytest

import rietx as rx
from rietx.model.forward import compile_model
from rietx.params.vector import ParameterTable
from rietx.schemas.instrument import Instrument
from rietx.schemas.pattern import PatternData
from rietx.strategy.staged import (
    BOUND_HIT_COS_MIN,
    RefinementPlan,
    Stage,
    bound_findings,
)
from rietx.viz import plot_result
from tests.test_schemas import make_lab6

A_TRUE = 4.15660
ZERO_BOUND = 0.02
ZERO = "instrument.zero_shift"


@pytest.fixture(scope="module")
def data() -> PatternData:
    structure = make_lab6()
    structure.phases[0].cell.a.value = A_TRUE
    ins = Instrument.debye_scherrer(wavelength=1.5406)
    tt = np.arange(15.0, 110.0, 0.02)
    empty = PatternData(two_theta=tt.tolist(),
                        intensity=np.zeros_like(tt).tolist())
    model = compile_model(structure, ins, empty, mode="rietveld")
    table = ParameterTable(structure, ins)
    y = model.evaluate(table.decode(table.x0())) + 60.0
    rng = np.random.default_rng(5)
    return PatternData(
        two_theta=model.tt.tolist(),
        intensity=rng.poisson(np.maximum(y, 1.0)).astype(float).tolist())


def _seeded():
    """LaB6 500 ppm large, so a free zero shift tries to absorb the error."""
    structure = make_lab6()
    structure.phases[0].cell.a.value = A_TRUE * 1.0005
    return structure


def _instrument():
    ins = Instrument.debye_scherrer(wavelength=1.5406)
    ins.zero_shift.min, ins.zero_shift.max = -ZERO_BOUND, ZERO_BOUND
    return ins


_SCALE_BKG = Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"])
_ZERO = Stage("zero", [ZERO])
_CELL = Stage("cell", ["phases.*.cell.*"])


def _fit(data, *stages):
    return rx.Refinement(_seeded(), _instrument(), history=False).fit(
        data, plan=RefinementPlan(stages=list(stages)))


def _codes(result, code):
    return [d for d in result.diagnostics if d.code == code]


def test_a_parameter_still_at_its_bound_at_convergence_reports(data):
    """The half that must keep working: stop while the zero shift is pinned."""
    result = _fit(data, _SCALE_BKG, _ZERO)
    zero = {p.path: p for p in result.parameters}[ZERO]

    assert zero.value == pytest.approx(ZERO_BOUND, abs=1e-12)
    assert zero.at_bound is True
    (hit,) = _codes(result, "BOUND_HIT")
    # the sentence is unchanged; WP-1434 appends the evidence for it
    assert hit.message.startswith(f"{ZERO} refined to its bound (\u03c1=")
    assert "esd from the limit" in hit.message
    # at an upper limit the solver would still be raising the value, so the
    # residual keeps a negative angle with that column
    assert hit.value < 0.0


def test_a_bound_the_next_stage_resolves_is_not_reported(data):
    """The defect: the same plan with one more stage is a successful fit."""
    result = _fit(data, _SCALE_BKG, _ZERO, _CELL)
    fitted = {p.path: p for p in result.parameters}

    # a fully successful fit — the cell is recovered and the shift is ~zero
    assert result.status == "converged"
    assert fitted["phases.0.cell.a"].value == pytest.approx(A_TRUE, abs=1e-6)
    assert abs(fitted[ZERO].value) < 1e-5
    # …which is 0.005 % of the bound, so nothing may claim it is at one
    assert fitted[ZERO].at_bound is False
    assert _codes(result, "BOUND_HIT") == []


def test_the_diagnostic_and_the_row_cannot_disagree(data):
    """WP-1076's set-equality, which the staleness quietly broke.

    ``at_bound`` has always been projected from the **last** stage's
    ``guard.at_bounds`` while the diagnostics accumulated over every stage, so
    one result could carry ``at_bound=False`` on a row and ``BOUND_HIT`` in the
    diagnostics about that same parameter.  Asserted set-equal here rather than
    re-derived, which would pass whatever the code did.
    """
    for stages in ((_SCALE_BKG, _ZERO), (_SCALE_BKG, _ZERO, _CELL)):
        result = _fit(data, *stages)
        flagged = {p for d in _codes(result, "BOUND_HIT") for p in d.where}
        rows = {p.path for p in result.parameters if p.at_bound is True}
        assert flagged == rows, f"{stages[-1].name}: {flagged} != {rows}"


def test_the_stage_that_hit_the_bound_still_records_it(data):
    """Discarded from the *result*, never from the record.

    A transient excursion is a real signal about plan ordering, so the stage's
    own node keeps its finding — the same split the correlation dedup makes,
    where the unfiltered per-stage list still reaches the history node.  That
    node is the only per-stage view of it: ``StageResult`` carries no
    diagnostics, which is issue #231's third fix and is not this change.
    """
    ref = rx.Refinement(_seeded(), _instrument())
    result = ref.fit(data, plan=RefinementPlan(stages=[_SCALE_BKG, _ZERO, _CELL]))

    assert _codes(result, "BOUND_HIT") == []

    hit = [node for node in ref.history.nodes.values()
           if any(d.code == "BOUND_HIT" for d in node.diagnostics)]
    assert [node.action.name for node in hit] == ["zero"], (
        "the stage that pressed the bound no longer records that it did")


# --- WP-1434: the bound test asks whether the limit carried load ------------

#: the final tolerance, swept.  Every one of these is a tolerance a caller can
#: reach: 1e-9 is the solver's own, 1e-6 the shipped ``intermediate_ftol``, and
#: the loose two are what a caller sets to buy iterations back.
FTOLS = [1e-9, 1e-6, 1e-4, 1e-3]

#: loose enough that the stage stops while the zero shift is still travelling
#: towards its limit — the row both halves of the conjunction are needed for.
FTOL_STOPS_EARLY = 1e-2


def _fit_at(data, ftol, *stages):
    """``stages`` with the **last** one stopped at ``ftol``.

    ``RefinementPlan.stage_ftols`` is the one authority applying the schedule
    and only the plan knows which stage is last (WP-1123), so setting it on
    the last ``Stage`` is how a caller reaches the tolerance that produces the
    answer.
    """
    stages = [dataclasses.replace(s) for s in stages]
    stages[-1].ftol = ftol
    return _fit(data, *stages)


def _answering_stage(data, ftol, *stages):
    """``(table, outcome)`` of the stage whose θ becomes the result.

    ``check_guards`` is the one place both are in hand, and it is where the
    bound test is taken from, so reading them here reads exactly what the
    guard read rather than a reconstruction of it.
    """
    captured = []
    refine_mod = sys.modules["rietx.refine"]
    real = refine_mod.check_guards

    def spy(table, outcome, *a, **k):
        captured.append((table, outcome))
        return real(table, outcome, *a, **k)

    refine_mod.check_guards = spy
    try:
        _fit_at(data, ftol, *stages)
    finally:
        refine_mod.check_guards = real
    return captured[-1]


@pytest.mark.parametrize("ftol", FTOLS)
def test_a_binding_bound_fires_at_every_ftol(data, ftol):
    """The defect: two of these four were silent, and nothing else differed.

    The bound is binding in all four — the cell error has nowhere else to go —
    so a flag that appears and disappears with the stopping tolerance is
    reporting the solver, not the fit.
    """
    result = _fit_at(data, ftol, _SCALE_BKG, _ZERO)
    zero = {p.path: p for p in result.parameters}[ZERO]

    assert zero.at_bound is True, f"silent at ftol={ftol:g}"
    assert [d.code for d in _codes(result, "BOUND_HIT")] == ["BOUND_HIT"]


@pytest.mark.parametrize("ftol", FTOLS)
def test_an_interior_optimum_is_silent_at_every_ftol(data, ftol):
    """The other half, which must not have been bought with a looser distance.

    The third stage frees the cell, the shift returns to ~0, and the limit is
    half the interval away.
    """
    result = _fit_at(data, ftol, _SCALE_BKG, _ZERO, _CELL)
    fitted = {p.path: p for p in result.parameters}

    assert abs(fitted[ZERO].value) < 1e-5
    assert fitted[ZERO].at_bound is False, f"fired at ftol={ftol:g}"
    assert _codes(result, "BOUND_HIT") == []


def test_a_stage_that_stopped_early_is_not_a_bound_hit(data):
    """The row that keeps the conjunction honest (WP-1434 § Context row 3).

    The zero shift is heading for its limit and the gradient says so as loudly
    as it does on the binding rows, but the stage stopped 1.2e-2 short — 2.4
    esds, 29 % of the interval.  That is a statement about the iteration
    budget and must not be dressed as a bound the answer sits on, so it is the
    *distance* half that declines it.  Asserted with the angle, because a row
    that passed for the wrong reason would look identical.
    """
    result = _fit_at(data, FTOL_STOPS_EARLY, _SCALE_BKG, _ZERO)
    zero = {p.path: p for p in result.parameters}[ZERO]

    # nowhere near the limit …
    assert 0.0 < zero.value < 0.9 * ZERO_BOUND
    # … while the residual keeps a large angle with that column, i.e. the
    # gradient half alone would have fired
    table, outcome = _answering_stage(data, FTOL_STOPS_EARLY,
                                      _SCALE_BKG, _ZERO)
    cos = float(outcome.residual_cosine[list(table.free_paths).index(ZERO)])
    assert cos < -BOUND_HIT_COS_MIN

    assert zero.at_bound is False
    assert _codes(result, "BOUND_HIT") == []


def test_the_finding_carries_the_evidence_for_its_claim(data):
    """``value`` is the test statistic, and the sentence says it in words.

    A reader who cannot re-run the fit still has to be able to tell a bound
    that carried load from one the solver stopped beside, which is the whole
    content of this guard after WP-1434.
    """
    result = _fit_at(data, 1e-4, _SCALE_BKG, _ZERO)
    (hit,) = _codes(result, "BOUND_HIT")

    # ρ is signed: at an *upper* limit the solver would still be raising the
    # value, so the residual keeps a negative angle with the column
    assert hit.value is not None and hit.value < -BOUND_HIT_COS_MIN
    assert hit.where == [ZERO]
    assert hit.message.startswith(f"{ZERO} refined to its bound (\u03c1=")
    assert "esd from the limit" in hit.message


def test_the_fallback_is_the_pre_1434_test_and_needs_no_solve():
    """``bound_findings`` stays a pure function of arrays.

    Without a solve behind it there is no angle to read and no esd to scale
    by, so the conjunction cannot be evaluated and the distance test is what
    is left.  A caller that used to get an answer still gets the same one.
    """
    lo = np.array([0.0, 0.0])
    hi = np.array([1.0, 1.0])
    names = ["a", "b"]

    found = bound_findings((lo, hi), names, np.array([1.0, 0.5]))
    assert [f.paths[0] for f in found] == ["a"]
    # …and it renders exactly as it did, evidence-free
    assert found[0].message == "a"
    assert found[0].value is None
    assert found[0].detail == ""


def test_an_angle_of_zero_declines_a_value_sitting_on_its_limit():
    """The conjunction's point, in one call: sitting on a limit is not enough.

    A column the residual is orthogonal to is at a free optimum that happens
    to coincide with the limit, so the limit is carrying no load and there is
    nothing for a caller to widen or fix.
    """
    lo, hi = np.array([0.0]), np.array([1.0])
    esd = np.array([1.0])

    # on the limit, and the residual is orthogonal to the column
    assert bound_findings((lo, hi), ["a"], np.array([1.0]),
                          cos=np.array([0.0]), esd=esd) == []
    # on the limit, pushed *inward* — the solver would leave it if it could,
    # and it is free to, so again nothing is holding it there
    assert bound_findings((lo, hi), ["a"], np.array([1.0]),
                          cos=np.array([+0.5]), esd=esd) == []
    # on the limit and pushed out of the feasible set: this one is held
    (found,) = bound_findings((lo, hi), ["a"], np.array([1.0]),
                              cos=np.array([-0.5]), esd=esd)
    assert found.value == pytest.approx(-0.5)


def test_the_rows_render(data):
    """obs/calc/diff PNGs to ``tests/output/`` (gitignored), house convention.

    The binding panel and the interior one side by side: a bound test that
    changed which fits speak must not have changed what any of them fitted.

    **The binding panel is meant to look bad** (Rwp ~0.97 against ~0.015), and
    a reader opening the directory should not read it as a regression.  It is
    the two-stage plan, which never frees the cell, so the 500 ppm error has
    only the zero shift to hide in and the zero shift runs out of interval —
    which is the whole reason this fixture makes a bound bind.  The interior
    panel is the same data with the cell stage added.
    """
    out = Path(__file__).parent / "output"
    out.mkdir(exist_ok=True)
    for name, stages in (("binding", (_SCALE_BKG, _ZERO)),
                         ("interior", (_SCALE_BKG, _ZERO, _CELL))):
        result = _fit_at(data, 1e-4, *stages)
        plot_result(result, path=str(out / f"bound_hit_{name}.png"))
        plot_result(result, path=str(out / f"bound_hit_{name}_zoom.png"),
                    two_theta_range=(20.0, 35.0))

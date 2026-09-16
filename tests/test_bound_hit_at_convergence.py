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
"""

from __future__ import annotations

import numpy as np
import pytest

import rietx as rx
from rietx.model.forward import compile_model
from rietx.params.vector import ParameterTable
from rietx.schemas.instrument import Instrument
from rietx.schemas.pattern import PatternData
from rietx.strategy.staged import RefinementPlan, Stage
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
    assert [d.message for d in _codes(result, "BOUND_HIT")] == [
        f"{ZERO} refined to its bound"]


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

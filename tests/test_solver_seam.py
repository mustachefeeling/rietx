"""The two drivers are interchangeable at the entry points (WP-0601).

``solver="lm"`` must reach the same physical answer as the scipy TRF reference
through the *same* residual/Jacobian closures, on both entry points — the
single-histogram one and the joint multi-histogram one, which WP-0308 warned
is a second driver rather than a wrapper.
"""

from __future__ import annotations

import numpy as np
import pytest

from pxrdref import Instrument, MultiHistogramRefinement, Refinement, refine
from pxrdref.optimize.least_squares import SOLVERS
from tests.test_refine_synthetic import (
    TRUE_A,
    TRUE_ZERO,
    perturbed_models,
    synthesize,
)


@pytest.fixture(scope="module")
def pattern():
    return synthesize()


def test_both_solvers_are_offered():
    assert SOLVERS == ("trf", "lm")


@pytest.mark.parametrize("bad", ["lmfit", "TRF", "", "levenberg"])
def test_unknown_solver_is_refused_at_construction(bad):
    structure, ins = perturbed_models()
    with pytest.raises(ValueError, match="unknown solver"):
        Refinement(structure, ins, solver=bad)


def test_lm_reaches_the_same_minimum_as_trf(pattern):
    """Not bit-identical — different path — but the same answer."""
    out = {}
    for solver in SOLVERS:
        structure, ins = perturbed_models()
        ref = Refinement(structure, ins, solver=solver, history=False)
        result = ref.fit(pattern, plan="mccusker_default")
        assert result.status == "converged"
        # WP-0602: which driver ran is provenance, and no cone in this model
        # means the truncation counter must stay at zero on every stage
        assert result.provenance.solver == solver
        assert all(s.n_constraint_truncations == 0 for s in result.stages)
        assert not any(d.code == "CONSTRAINT_ACTIVE" for d in result.diagnostics)
        out[solver] = (ref.fitted_structure.phases[0].cell.a.value,
                       ref.fitted_instrument.zero_shift.value,
                       result.statistics.rwp)

    a_lm, zero_lm, rwp_lm = out["lm"]
    a_trf, zero_trf, rwp_trf = out["trf"]
    assert a_lm == pytest.approx(TRUE_A, abs=5e-5)
    assert a_lm == pytest.approx(a_trf, abs=2e-5)
    assert zero_lm == pytest.approx(TRUE_ZERO, abs=2e-3)
    assert zero_lm == pytest.approx(zero_trf, abs=5e-4)
    assert rwp_lm == pytest.approx(rwp_trf, rel=0.02)


def test_functional_api_takes_the_solver(pattern):
    structure, ins = perturbed_models()
    result = refine(pattern, structure, ins, solver="lm")
    assert result.status == "converged"
    assert result.statistics.rwp < 0.10


def test_branch_carries_the_solver(pattern):
    structure, ins = perturbed_models()
    ref = Refinement(structure, ins, solver="lm")
    ref.fit(pattern, plan="mccusker_default")
    assert ref.branch()._solver == "lm"


def test_multi_histogram_entry_point_takes_the_solver(pattern):
    """WP-0308's warning made executable: the joint driver is a second one.

    A solver swap that reached only ``run_least_squares`` would leave this
    path silently on scipy, and nothing else in the suite would notice.
    """
    structure, ins = perturbed_models()
    second = Instrument.debye_scherrer(wavelength=0.4139)
    second.zero_shift.value = 0.0
    second.profile.w.value = ins.profile.w.value
    second.background = ins.background.model_copy(deep=True)

    multi = MultiHistogramRefinement(structure, [ins, second], solver="lm")
    result = multi.fit([pattern, pattern])
    assert result.status in ("converged", "max_iter")
    assert result.statistics.rwp < 0.15
    assert result.provenance.solver == "lm"          # WP-0602 provenance
    assert all(s.n_constraint_truncations == 0 for s in result.stages)

    with pytest.raises(ValueError, match="unknown solver"):
        MultiHistogramRefinement(structure, [ins], solver="nope")


def test_sequential_takes_the_solver(pattern):
    """The series runner builds one Refinement per pattern; the solver must
    survive that construction or a series silently reverts to scipy."""
    from pxrdref import SequentialRefinement, refine_sequential

    structure, ins = perturbed_models()
    with pytest.raises(ValueError, match="unknown solver"):
        SequentialRefinement(structure, ins, solver="nope")

    series = refine_sequential([pattern, pattern], structure, ins, solver="lm",
                               plan="mccusker_default")
    assert series.provenance is not None
    assert series.provenance.solver == "lm"
    assert all(e.status == "converged" for e in series.entries)


def test_constraint_active_diagnostic_units():
    """`CONSTRAINT_ACTIVE` fires iff the answer-producing stage truncated.

    The counter's semantics: the only signal that a declared linear-inequality
    constraint was *active* rather than merely present (WP-0601 → WP-0602).
    """
    from types import SimpleNamespace

    from pxrdref.refine import _constraint_diagnostics

    quiet = _constraint_diagnostics("sample_profile", SimpleNamespace(
        n_constraint_truncations=0))
    assert quiet == []

    fired = _constraint_diagnostics("sample_profile", SimpleNamespace(
        n_constraint_truncations=3))
    assert len(fired) == 1
    d = fired[0]
    assert d.code == "CONSTRAINT_ACTIVE"
    assert d.level == "info"           # admissible, not wrong — never a warning
    assert "3 step(s)" in d.message and "sample_profile" in d.message
    assert "vary the starting seed" in d.suggestion


def test_outcome_records_which_driver_ran(pattern):
    """``LSQOutcome.solver`` is what a benchmark or a record field reads."""
    from pxrdref.model.forward import compile_model
    from pxrdref.optimize.least_squares import run_least_squares
    from pxrdref.params.vector import ParameterTable

    structure, ins = perturbed_models()
    model = compile_model(structure, ins, pattern, mode="rietveld")
    table = ParameterTable(structure, ins)
    table.set_vary(["phases.*.scale", "instrument.background.*"], True)

    for solver in SOLVERS:
        outcome = run_least_squares(model, table, max_iter=20, solver=solver)
        assert outcome.solver == solver
        assert outcome.cost_final <= outcome.cost_initial
        assert outcome.n_constraint_truncations == 0   # no cone in this model

    with pytest.raises(ValueError, match="unknown solver"):
        run_least_squares(model, table, solver="banana")


def test_lm_emits_eval_events_at_accepted_points_only(pattern):
    """The LM has a real callback, so its event stream is monotone per stage.

    TRF has none, so its stream hooks the residual and therefore also carries
    rejected trial points.  A live viewer reads both, and the difference is
    worth pinning: an LM stage's costs never go back up.
    """
    seen: list[dict] = []
    structure, ins = perturbed_models()
    ref = Refinement(structure, ins, solver="lm", history=False)
    ref.fit(pattern, plan="mccusker_default", events=seen.append)

    per_stage: dict[str, list[float]] = {}
    for event in seen:
        if event["kind"] == "eval":
            per_stage.setdefault(event["data"]["stage"], []).append(event["data"]["cost"])
    assert per_stage, "no eval events emitted"
    for stage, costs in per_stage.items():
        assert all(np.isfinite(c) for c in costs)
        assert costs == sorted(costs, reverse=True), f"{stage} cost went back up"

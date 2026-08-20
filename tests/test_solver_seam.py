"""The two drivers are interchangeable at the entry points (WP-0601).

``solver="lm"`` must reach the same physical answer as the scipy TRF reference
through the *same* residual/Jacobian closures, on both entry points — the
single-histogram one and the joint multi-histogram one, which WP-0308 warned
is a second driver rather than a wrapper.
"""

from __future__ import annotations

import numpy as np
import pytest

from rietx import Instrument, MultiHistogramRefinement, Refinement, refine
from rietx.optimize.least_squares import SOLVERS
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
    from rietx import SequentialRefinement, refine_sequential

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

    from rietx.refine import _constraint_diagnostics

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
    from rietx.model.forward import compile_model
    from rietx.optimize.least_squares import run_least_squares
    from rietx.params.vector import ParameterTable

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


# -- what the iteration budget means (WP-1109) ----------------------------

def _spy_least_squares(monkeypatch):
    """Record the kwargs every TRF call is made with."""
    import scipy.optimize as so

    import rietx.optimize.least_squares as ls

    calls = []
    original = so.least_squares

    def spy(*args, **kwargs):
        res = original(*args, **kwargs)
        calls.append({"max_nfev": kwargs.get("max_nfev"),
                      "xtol": kwargs.get("xtol"), "gtol": kwargs.get("gtol"),
                      "n_par": len(res.x), "nfev": int(res.nfev),
                      "njev": int(res.njev or 0), "status": int(res.status)})
        return res

    monkeypatch.setattr(ls, "least_squares", spy)
    return calls


def test_the_budget_counts_iterations_not_parameters(pattern, monkeypatch):
    """``max_iter`` prices iterations, and the multiplier that turns it into
    scipy's evaluation cap is a constant.  It used to be ``n_params``, which
    priced a finite-difference Jacobian this package does not build: the same
    stage then got a budget that grew with the model, ~30x looser than the
    name at 42 free parameters.  The claim under test is that the cap no
    longer depends on the parameter count at all."""
    import rietx as rx
    from rietx.optimize.least_squares import NFEV_PER_ITERATION

    calls = _spy_least_squares(monkeypatch)
    structure, instrument = perturbed_models()
    plan = rx.RefinementPlan.mccusker_default()
    for stage in plan.stages:
        stage.max_iter = 37
    refine(pattern, structure, instrument, plan=plan)

    assert calls, "no TRF call observed"
    assert len({c["n_par"] for c in calls}) > 1, \
        "fixture must span stages of differing size for this to discriminate"
    for c in calls:
        assert c["max_nfev"] == 37 * NFEV_PER_ITERATION


def test_a_converging_fit_never_feels_the_budget(pattern, monkeypatch):
    """CLAUDE.md's rule for a wall-clock budget applies to this one: a runaway
    guard, never a timer.  Tightening it ~30x is only answer-preserving if no
    converging stage was relying on the slack, so every stage here must both
    reach a convergence status and stop well inside its cap."""
    calls = _spy_least_squares(monkeypatch)
    structure, instrument = perturbed_models()
    result = refine(pattern, structure, instrument)

    assert result.status == "converged"
    for c in calls:
        assert c["status"] > 0, f"stage stopped on its budget: {c}"
        assert c["nfev"] < c["max_nfev"], c
        # and with real headroom, not by one evaluation
        assert c["nfev"] < 0.5 * c["max_nfev"], c


def test_the_trf_tolerances_are_the_module_constants(pattern, monkeypatch):
    """xtol/gtol were hardcoded literals at 1e-12 and are now named constants
    at the same value — named so the number has one home and the measurement
    that keeps it has somewhere to live, pinned so it cannot drift back into a
    literal *or* be tidied up to scipy's 1e-8 default.

    WP-1109 tried that tidy-up and put it back: it is a wash on speed (1.25x
    on one shipped protocol, 1.04x slower on another) and it takes the
    Stephens isotropic control past a shipped bar.  The constant's docstring
    carries the numbers."""
    from rietx.optimize.least_squares import GTOL, XTOL

    assert XTOL == GTOL == 1e-12
    calls = _spy_least_squares(monkeypatch)
    structure, instrument = perturbed_models()
    refine(pattern, structure, instrument)
    assert calls
    for c in calls:
        assert c["xtol"] == XTOL and c["gtol"] == GTOL

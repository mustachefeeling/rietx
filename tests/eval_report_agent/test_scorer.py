"""Deterministic unit tests for the WP-1053 scorer and shim (fast suite).

Everything here is synthetic JSON in ``tmp_path`` — no refinement runs, no
network, no LLM.  The shim's enforcement is tested with ``refine_json``
monkeypatched, because what these tests pin is the *harness contract*
(overlay restriction, report stripping, budget, logging), not the solver.
"""

import json
from pathlib import Path

import pytest

from tests.eval_report_agent.run_refine import run_episode, trim_response
from tests.eval_report_agent.scorer import score_episode

# ----------------------------------------------------------------------
# builders
# ----------------------------------------------------------------------


def _write_truth(tmp_path: Path, **overrides) -> Path:
    record = {
        "episode": "ET",
        "expected_verdict": "converged",
        "planted": {"path": "instrument.zero_shift", "start": 0.008,
                    "truth": 0.0, "tol": {"abs": 0.002}},
        "family": ["instrument.zero_shift", "phases.*.cell.*"],
        "notes": "",
    }
    record.update(overrides)
    path = tmp_path / "truth.json"
    path.write_text(json.dumps(record))
    return path


def _call(parameters=(), freed=(), overlay=None, ok=True, refused=False,
          condition="report-on"):
    if refused:
        return {"refused": True, "overlay": overlay or {},
                "response": {"ok": False,
                             "error": {"code": "OVERLAY_KEY_REFUSED",
                                       "message": ""}}}
    if not ok:
        return {"refused": False, "overlay": overlay or {},
                "condition": condition,
                "response": {"ok": False,
                             "error": {"code": "REFINEMENT_FAILED",
                                       "message": ""}}}
    return {
        "refused": False,
        "condition": condition,
        "include_report": condition == "report-on",
        "overlay": overlay or {},
        "response": {"ok": True, "result": {
            "status": "converged",
            "parameters": list(parameters),
            "stages": [{"name": "s", "freed": list(freed)}],
            "statistics": {"rwp": 0.01},
        }},
    }


def _write_episode_dir(tmp_path: Path, calls, answer) -> Path:
    edir = tmp_path / "ET"
    edir.mkdir(exist_ok=True)
    if calls is not None:
        (edir / "calls.jsonl").write_text(
            "".join(json.dumps(c) + "\n" for c in calls))
    if answer is not None:
        (edir / "answer.json").write_text(
            answer if isinstance(answer, str) else json.dumps(answer))
    return edir


def _param(path, value):
    return {"path": path, "value": value, "stderr": None, "vary": True,
            "at_bound": False}


# ----------------------------------------------------------------------
# scorer: recovery episodes
# ----------------------------------------------------------------------


def test_recovery_pass_abs_tolerance(tmp_path):
    truth = _write_truth(tmp_path)
    edir = _write_episode_dir(tmp_path, [
        _call(parameters=[_param("instrument.zero_shift", 0.0008)],
              freed=["instrument.zero_shift", "instrument.background.c0"]),
    ], {"verdict": "converged", "summary": "zero error"})
    card = score_episode(edir, truth)
    assert card["passed"] and card["recovered"] and card["verdict_ok"]
    assert card["planted_final_value"] == 0.0008
    assert card["wrong_frees"] == []
    assert card["n_calls"] == 1


def test_absent_planted_path_scores_not_recovered(tmp_path):
    """The vary-or-tie finding: a fixed parameter is absent from the
    serialised ``parameters``, so absence means never-freed and the value is
    the planted start — scored from absence, never re-read."""
    truth = _write_truth(tmp_path)
    edir = _write_episode_dir(tmp_path, [
        _call(parameters=[_param("phases.0.scale", 4e-4)],
              freed=["phases.0.scale"]),
    ], {"verdict": "converged", "summary": ""})
    card = score_episode(edir, truth)
    assert card["recovered"] is False and not card["passed"]
    assert card["planted_final_value"] is None
    assert any("never freed" in n for n in card["notes"])


def test_recovery_rel_tolerance_boundary(tmp_path):
    truth = _write_truth(tmp_path, planted={
        "path": "phases.0.scale", "start": 3.6e-4, "truth": 4e-4,
        "tol": {"rel": 0.02}})
    inside = _write_episode_dir(tmp_path, [
        _call(parameters=[_param("phases.0.scale", 4e-4 * 1.019)],
              freed=["phases.0.scale"])],
        {"verdict": "converged", "summary": ""})
    assert score_episode(inside, truth)["recovered"] is True
    outside = _write_episode_dir(tmp_path, [
        _call(parameters=[_param("phases.0.scale", 4e-4 * 1.03)],
              freed=["phases.0.scale"])],
        {"verdict": "converged", "summary": ""})
    assert score_episode(outside, truth)["recovered"] is False


def test_recovered_but_wrong_verdict_fails(tmp_path):
    truth = _write_truth(tmp_path)
    edir = _write_episode_dir(tmp_path, [
        _call(parameters=[_param("instrument.zero_shift", 0.0)],
              freed=["instrument.zero_shift"])],
        {"verdict": "abstain", "summary": ""})
    card = score_episode(edir, truth)
    assert card["recovered"] is True and not card["verdict_ok"]
    assert not card["passed"]


def test_wrong_frees_globbing_and_last_successful_call(tmp_path):
    """Wrong-frees come from the graded call only — the last *successful*
    one — and family + background globs absorb the legitimate frees."""
    truth = _write_truth(tmp_path)
    edir = _write_episode_dir(tmp_path, [
        _call(parameters=[_param("instrument.zero_shift", 0.0)],
              freed=["instrument.zero_shift", "phases.0.cell.a",
                     "instrument.background.c1", "phases.0.scale",
                     "phases.0.atoms.0.biso"]),
        _call(ok=False),
    ], {"verdict": "converged", "summary": ""})
    card = score_episode(edir, truth)
    # scale is ALWAYS_LEGIT (textbook stage 1), biso is a genuine wrong-free
    assert card["wrong_frees"] == ["phases.0.atoms.0.biso"]
    assert card["n_failed_calls"] == 1
    assert card["passed"]  # graded on the successful call, not the failure


# ----------------------------------------------------------------------
# scorer: trap episodes and degenerate records
# ----------------------------------------------------------------------


def test_trap_episode_scored_on_verdict_alone(tmp_path):
    truth = _write_truth(tmp_path, expected_verdict="abstain", planted=None,
                         family=None)
    edir = _write_episode_dir(tmp_path,
                              [_call(freed=["instrument.background.c0"])],
                              {"verdict": "abstain", "summary": "hopeless"})
    card = score_episode(edir, truth)
    assert card["passed"] and card["recovered"] is None
    # frees are recorded verbatim on a trap, but never counted wrong
    assert card["wrong_frees"] is None
    assert card["freed"] == ["instrument.background.c0"]


def test_planted_without_tol_reports_value_but_grades_verdict(tmp_path):
    """E8's shape: the planted zero is recorded when freed, but the grade is
    the ambiguity verdict, never the parameter."""
    truth = _write_truth(tmp_path, expected_verdict="ambiguous", planted={
        "path": "instrument.zero_shift", "start": 0.02, "truth": 0.0,
        "tol": None}, family=None)
    edir = _write_episode_dir(tmp_path, [
        _call(parameters=[_param("instrument.zero_shift", 0.013)],
              freed=["instrument.zero_shift"])],
        {"verdict": "ambiguous", "summary": "collinear"})
    card = score_episode(edir, truth)
    assert card["passed"] and card["recovered"] is None
    assert card["planted_final_value"] == 0.013


def test_no_successful_call_fails_even_with_right_verdict(tmp_path):
    truth = _write_truth(tmp_path, expected_verdict="abstain", planted=None,
                         family=None)
    edir = _write_episode_dir(tmp_path, [], {"verdict": "abstain",
                                             "summary": ""})
    card = score_episode(edir, truth)
    assert not card["passed"]
    assert any("no successful refinement call" in n for n in card["notes"])


@pytest.mark.parametrize("answer", [
    None,
    "not json {",
    {"verdict": "victory", "summary": ""},
])
def test_missing_or_invalid_answer_fails_without_crashing(tmp_path, answer):
    truth = _write_truth(tmp_path)
    edir = _write_episode_dir(tmp_path, [
        _call(parameters=[_param("instrument.zero_shift", 0.0)],
              freed=["instrument.zero_shift"])], answer)
    card = score_episode(edir, truth)
    assert not card["passed"] and card["verdict"] is None
    assert card["notes"]


def test_refused_calls_are_counted_separately(tmp_path):
    truth = _write_truth(tmp_path)
    edir = _write_episode_dir(tmp_path, [
        _call(refused=True),
        _call(parameters=[_param("instrument.zero_shift", 0.0)],
              freed=["instrument.zero_shift"],
              overlay={"two_theta_limits": [20.0, 100.0]}),
    ], {"verdict": "converged", "summary": ""})
    card = score_episode(edir, truth)
    assert card["n_calls"] == 1 and card["n_refused"] == 1
    assert card["excluded_regions"] == [[20.0, 100.0]]
    assert card["passed"]


# ----------------------------------------------------------------------
# shim: enforcement, with refine_json stubbed
# ----------------------------------------------------------------------


def _write_shim_episode(tmp_path: Path, *, include_report: bool,
                        max_calls: int = 8) -> Path:
    edir = tmp_path / "ES"
    edir.mkdir(exist_ok=True)
    (edir / "episode.json").write_text(json.dumps({
        "task": "refine", "structure": {"phases": []}, "instrument": {},
        "pattern": {"two_theta": [1.0], "intensity": [1.0]},
        "mode": "rietveld",
    }))
    (edir / "condition.json").write_text(json.dumps({
        "protocol_version": "1.0",
        "condition": "report-on" if include_report else "report-off",
        "include_report": include_report,
        "max_calls": max_calls,
    }))
    return edir


def _stub_response():
    return {"ok": True,
            "result": {"status": "converged", "parameters": [], "stages": [],
                       "statistics": {"rwp": 0.01},
                       "two_theta": [1.0, 2.0], "y_obs": [1.0, 2.0],
                       "y_calc": [1.0, 2.0], "y_background": [0.0, 0.0],
                       "sigma": [1.0, 1.0], "ticks": {"LaB6": [1.5]},
                       "history": [{"stage": "s", "iteration": 0,
                                    "cost": 1.0}]},
            "report": {"layer1_available": True}}


def test_shim_merges_overlay_and_forces_condition(tmp_path, monkeypatch):
    edir = _write_shim_episode(tmp_path, include_report=False)
    seen = {}

    def stub(request):
        seen.update(request)
        return _stub_response()

    monkeypatch.setattr("pxrdref.agent.refine_json", stub)
    (edir / "overlay.json").write_text(json.dumps(
        {"plan": "profile_only", "two_theta_limits": [20.0, 100.0]}))
    response = run_episode(edir)
    # overlay merged, core untouched, condition forced regardless of default
    assert seen["plan"] == "profile_only"
    assert seen["two_theta_limits"] == [20.0, 100.0]
    assert seen["mode"] == "rietveld"
    assert seen["structure"] == {"phases": []}
    assert seen["include_report"] is False
    # report-off: stripped from what the agent sees and from the log
    assert "report" not in response
    logged = json.loads((edir / "calls.jsonl").read_text().splitlines()[0])
    assert "report" not in logged["response"]
    assert logged["overlay"] == {"plan": "profile_only",
                                 "two_theta_limits": [20.0, 100.0]}


def test_shim_report_on_keeps_report_and_elides_bulk(tmp_path, monkeypatch):
    edir = _write_shim_episode(tmp_path, include_report=True)
    monkeypatch.setattr("pxrdref.agent.refine_json",
                        lambda request: _stub_response())
    response = run_episode(edir)
    assert response["report"] == {"layer1_available": True}
    result = response["result"]
    assert result["two_theta"] == {"elided_n_points": 2}
    assert result["ticks"] == {"LaB6": {"elided_n_ticks": 1}}
    assert result["history"] == {"elided_n_iterations": 1}
    assert result["statistics"]["rwp"] == 0.01  # numbers survive


def test_shim_refuses_unsanctioned_overlay_keys(tmp_path, monkeypatch):
    edir = _write_shim_episode(tmp_path, include_report=True)

    def stub(request):  # pragma: no cover - must not be reached
        raise AssertionError("refine_json called on a refused overlay")

    monkeypatch.setattr("pxrdref.agent.refine_json", stub)
    (edir / "overlay.json").write_text(json.dumps(
        {"plan": "profile_only", "include_report": False,
         "pattern": {"two_theta": []}}))
    response = run_episode(edir)
    assert response["ok"] is False
    assert response["error"]["code"] == "OVERLAY_KEY_REFUSED"
    assert "include_report" in response["error"]["message"]
    logged = json.loads((edir / "calls.jsonl").read_text().splitlines()[0])
    assert logged["refused"] is True


def test_shim_call_budget_is_a_runaway_guard(tmp_path, monkeypatch):
    edir = _write_shim_episode(tmp_path, include_report=True, max_calls=2)
    monkeypatch.setattr("pxrdref.agent.refine_json",
                        lambda request: _stub_response())
    (edir / "overlay.json").write_text("{}")
    assert run_episode(edir)["ok"]
    assert run_episode(edir)["ok"]
    third = run_episode(edir)
    assert third["ok"] is False
    assert third["error"]["code"] == "CALL_BUDGET_EXHAUSTED"
    records = [json.loads(x)
               for x in (edir / "calls.jsonl").read_text().splitlines()]
    assert [r.get("refused", False) for r in records] == [False, False, True]
    # a refused call never eats budget: the counter stays at max_calls
    fourth = run_episode(edir)
    assert fourth["error"]["code"] == "CALL_BUDGET_EXHAUSTED"


def test_trim_response_leaves_failures_alone():
    failure = {"ok": False, "error": {"code": "INVALID_REQUEST",
                                      "message": "m"}}
    assert trim_response(failure) == failure

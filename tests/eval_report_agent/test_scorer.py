"""Deterministic unit tests for the eval scorer, shim and fixtures.

Everything here is synthetic JSON in ``tmp_path`` — no refinement runs, no
network, no LLM.  The shim's enforcement is tested with ``refine_json``
monkeypatched, because what these tests pin is the *harness contract*
(overlay restriction, report and trajectory stripping, budget, logging, the
sibling condition marker), not the solver.  The episodes' physics — every
registered landing state and decision band — is pinned by the slow
``test_landing_states.py`` next door.
"""

import json
from pathlib import Path

import pytest

from tests.eval_report_agent import build_fixtures as bf
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
    path.write_text(json.dumps(record), encoding="utf-8")
    return path


def _call(parameters=(), freed=(), overlay=None, ok=True, refused=False,
          report=None, trajectory=None):
    """One 2.0 ``calls.jsonl`` record: no condition echo — the log lives in
    the workspace, so the response shape is the only condition-shaped thing
    on it (PROTOCOL.md 2.0)."""
    if refused:
        return {"refused": True, "overlay": overlay or {},
                "response": {"ok": False,
                             "error": {"code": "OVERLAY_KEY_REFUSED",
                                       "message": ""}}}
    if not ok:
        return {"refused": False, "overlay": overlay or {},
                "response": {"ok": False,
                             "error": {"code": "REFINEMENT_FAILED",
                                       "message": ""}}}
    response = {"ok": True, "result": {
        "status": "converged",
        "parameters": list(parameters),
        "stages": [{"name": "s", "freed": list(freed)}],
        "statistics": {"rwp": 0.01, "gof": 1.02},
    }}
    if report is not None:
        response["report"] = report
    if trajectory is not None:
        response["trajectory"] = list(trajectory)
    return {
        "refused": False,
        "overlay": overlay or {},
        "response": response,
    }


def _write_episode_dir(tmp_path: Path, calls, answer) -> Path:
    edir = tmp_path / "ET"
    edir.mkdir(exist_ok=True)
    if calls is not None:
        (edir / "calls.jsonl").write_text(
            "".join(json.dumps(c) + "\n" for c in calls), encoding="utf-8")
    if answer is not None:
        (edir / "answer.json").write_text(
            answer if isinstance(answer, str) else json.dumps(answer),
            encoding="utf-8")
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
# scorer: the WP-1059 descriptive measurements
# ----------------------------------------------------------------------


def test_watch_groups_report_which_family_was_freed(tmp_path):
    """E3's sign-inversion watch and R1's cause-vs-absorber choice are the
    same mechanism: truth-declared globs, reported against ``freed``."""
    truth = _write_truth(tmp_path, watch={
        "report_widths": ["phases.*.lor_size", "phases.*.lor_strain"],
        "default_width": ["instrument.profile.w"]})
    edir = _write_episode_dir(tmp_path, [
        _call(parameters=[_param("instrument.zero_shift", 0.0)],
              freed=["instrument.profile.w", "phases.0.lor_size",
                     "instrument.background.c0"])],
        {"verdict": "converged", "summary": ""})
    card = score_episode(edir, truth)
    assert card["watch"] == {"report_widths": ["phases.0.lor_size"],
                             "default_width": ["instrument.profile.w"]}


def test_watch_is_empty_when_the_truth_record_declares_none(tmp_path):
    truth = _write_truth(tmp_path)
    edir = _write_episode_dir(tmp_path, [
        _call(parameters=[_param("instrument.zero_shift", 0.0)],
              freed=["instrument.zero_shift"])],
        {"verdict": "converged", "summary": ""})
    assert score_episode(edir, truth)["watch"] == {}


@pytest.mark.parametrize("expected,verdict,flagged", [
    ("ambiguous", "converged", True),      # R1/E8: the overclaim
    ("abstain", "converged", True),        # E7: the overclaim
    ("ambiguous", "abstain", False),       # a miss, not an overclaim
    ("converged", "converged", False),     # the ordinary right answer
    ("converged", "abstain", False),       # under-claiming is not this flag
])
def test_overclaim_is_flagged_only_where_a_verdict_was_declined(
        tmp_path, expected, verdict, flagged):
    """The package's own hardest rule, scored on the agent: a confident
    ``converged`` where the data supports no single cause."""
    truth = _write_truth(tmp_path, expected_verdict=expected, planted=None,
                         family=None)
    edir = _write_episode_dir(tmp_path, [_call()],
                              {"verdict": verdict, "summary": ""})
    card = score_episode(edir, truth)
    assert card["overclaimed"] is flagged
    # and it never touches the grade, which stays the verdict match
    assert card["passed"] is (expected == verdict)


def test_bootstrap_calls_count_short_explicit_plans(tmp_path):
    """Round 1's measured mechanism — agents never generate the states where
    the report speaks — read straight off the overlay log."""
    truth = _write_truth(tmp_path)
    edir = _write_episode_dir(tmp_path, [
        _call(overlay={"plan": {"stages": [{"name": "scale_bkg",
                                            "turn_on": ["phases.*.scale"]}]}}),
        _call(overlay={"plan": {"stages": [{"name": "a"}, {"name": "b"},
                                           {"name": "c"}]}}),
        _call(overlay={"plan": "mccusker_default"}),
        _call(refused=True, overlay={"plan": {"stages": [{"name": "x"}]}}),
        _call(parameters=[_param("instrument.zero_shift", 0.0)],
              freed=["instrument.zero_shift"]),
    ], {"verdict": "converged", "summary": ""})
    card = score_episode(edir, truth)
    assert card["plans_used"] == ["stages:1", "stages:3", "mccusker_default",
                                  "default"]
    assert card["bootstrap_calls"] == 1  # the refused call is not a call
    assert card["passed"]


def test_graded_call_audit_shows_what_the_condition_delivered(tmp_path):
    """The condition is enforced by the shim; the scorecard has to be able to
    *show* that it was, or a grid cannot be checked by anyone else."""
    truth = _write_truth(tmp_path)
    on = _write_episode_dir(tmp_path, [
        _call(parameters=[_param("instrument.zero_shift", 0.0)],
              freed=["instrument.zero_shift"], report={"summary": "s"},
              trajectory=[{"stage": "scale_bkg"}, {"stage": "zero"}])],
        {"verdict": "converged", "summary": ""})
    card = score_episode(on, truth)
    assert card["report_present"] is True and card["trajectory_rungs"] == 2
    assert card["statistics"] == {"rwp": 0.01, "gof": 1.02}

    off = tmp_path / "off"
    off.mkdir()
    (off / "calls.jsonl").write_text(json.dumps(
        _call(parameters=[_param("instrument.zero_shift", 0.0)],
              freed=["instrument.zero_shift"])) + "\n",
        encoding="utf-8")
    (off / "answer.json").write_text(json.dumps(
        {"verdict": "converged", "summary": ""}), encoding="utf-8")
    card_off = score_episode(off, truth)
    assert card_off["report_present"] is False
    assert card_off["trajectory_rungs"] is None


def test_refusal_row_grades_the_verdict_and_records_the_parameter(tmp_path):
    """R1's shape: a planted path with ``tol: null``.  Freeing the true cause
    is recorded, and does not turn a declined verdict into a pass — on that
    pattern the data does not license the choice (WP-1059)."""
    truth = _write_truth(tmp_path, expected_verdict="ambiguous", planted={
        "path": "instrument.geometry.sample_displacement", "start": -0.02,
        "truth": -0.0801, "tol": None}, family=None)
    recovered_but_confident = _write_episode_dir(tmp_path, [
        _call(parameters=[_param("instrument.geometry.sample_displacement",
                                 -0.0801)],
              freed=["instrument.geometry.sample_displacement"])],
        {"verdict": "converged", "summary": "displacement refined"})
    card = score_episode(recovered_but_confident, truth)
    assert card["planted_final_value"] == -0.0801
    assert card["recovered"] is None      # never graded on this row
    assert card["overclaimed"] and not card["passed"]


# ----------------------------------------------------------------------
# shim: enforcement, with refine_json stubbed
# ----------------------------------------------------------------------


def _write_shim_episode(tmp_path: Path, *, include_report: bool,
                        include_trajectory: bool | None = False,
                        max_calls: int = 8,
                        condition: str | None = None) -> Path:
    """An episode dir plus its **sibling** marker (PROTOCOL.md 2.0: the
    workspace carries no condition bit).  ``include_trajectory=None`` omits
    the key — the malformed-marker case, which the shim must refuse rather
    than guess (the 1.0 single-switch compatibility read died with the
    relocation)."""
    edir = tmp_path / "ES"
    edir.mkdir(exist_ok=True)
    (edir / "episode.json").write_text(json.dumps({
        "task": "refine", "structure": {"phases": []}, "instrument": {},
        "pattern": {"two_theta": [1.0], "intensity": [1.0]},
        "mode": "rietveld",
    }), encoding="utf-8")
    marker = {
        "protocol_version": bf.PROTOCOL_VERSION,
        "condition": condition or ("surface" if include_report else "off"),
        "include_report": include_report,
        "max_calls": max_calls,
    }
    if include_trajectory is not None:
        marker["include_trajectory"] = include_trajectory
    (tmp_path / "ES.condition.json").write_text(json.dumps(marker),
                                                encoding="utf-8")
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
            "report": {"layer1_available": True},
            "trajectory": [{"stage": "scale_bkg", "rwp": 0.2}]}


def test_shim_merges_overlay_and_forces_condition(tmp_path, monkeypatch):
    edir = _write_shim_episode(tmp_path, include_report=False)
    seen = {}

    def stub(request):
        seen.update(request)
        return _stub_response()

    monkeypatch.setattr("anatase.agent.refine_json", stub)
    (edir / "overlay.json").write_text(json.dumps(
        {"plan": "profile_only", "two_theta_limits": [20.0, 100.0]}), encoding="utf-8")
    response = run_episode(edir)
    # overlay merged, core untouched, condition forced regardless of default
    assert seen["plan"] == "profile_only"
    assert seen["two_theta_limits"] == [20.0, 100.0]
    assert seen["mode"] == "rietveld"
    assert seen["structure"] == {"phases": []}
    assert seen["include_report"] is False
    # report-off: stripped from what the agent sees and from the log
    assert "report" not in response
    logged = json.loads((edir / "calls.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert "report" not in logged["response"]
    assert logged["overlay"] == {"plan": "profile_only",
                                 "two_theta_limits": [20.0, 100.0]}
    # and no condition echo: the log lives in the workspace, so a record that
    # repeated include_report would be the round-2 leak reopened
    assert "condition" not in logged
    assert "include_report" not in logged
    assert "include_trajectory" not in logged


def test_shim_report_on_keeps_report_and_elides_bulk(tmp_path, monkeypatch):
    edir = _write_shim_episode(tmp_path, include_report=True,
                               include_trajectory=True)
    monkeypatch.setattr("anatase.agent.refine_json",
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

    monkeypatch.setattr("anatase.agent.refine_json", stub)
    (edir / "overlay.json").write_text(json.dumps(
        {"plan": "profile_only", "include_report": False,
         "pattern": {"two_theta": []}}), encoding="utf-8")
    response = run_episode(edir)
    assert response["ok"] is False
    assert response["error"]["code"] == "OVERLAY_KEY_REFUSED"
    assert "include_report" in response["error"]["message"]
    logged = json.loads((edir / "calls.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert logged["refused"] is True


def test_shim_call_budget_is_a_runaway_guard(tmp_path, monkeypatch):
    edir = _write_shim_episode(tmp_path, include_report=True, max_calls=2)
    monkeypatch.setattr("anatase.agent.refine_json",
                        lambda request: _stub_response())
    (edir / "overlay.json").write_text("{}", encoding="utf-8")
    assert run_episode(edir)["ok"]
    assert run_episode(edir)["ok"]
    third = run_episode(edir)
    assert third["ok"] is False
    assert third["error"]["code"] == "CALL_BUDGET_EXHAUSTED"
    records = [json.loads(x)
               for x in (edir / "calls.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [r.get("refused", False) for r in records] == [False, False, True]
    # a refused call never eats budget: the counter stays at max_calls
    fourth = run_episode(edir)
    assert fourth["error"]["code"] == "CALL_BUDGET_EXHAUSTED"


def test_trim_response_leaves_failures_alone():
    failure = {"ok": False, "error": {"code": "INVALID_REQUEST",
                                      "message": "m"}}
    assert trim_response(failure) == failure


@pytest.mark.parametrize("condition", sorted(bf.CONDITIONS))
def test_shim_delivers_exactly_what_the_condition_declares(
        tmp_path, monkeypatch, condition):
    """The round-2 failure mode that would silently make a withheld arm a
    delivered one: the condition sets both halves on the *request* (so the
    package never builds one it withholds) and pops both from the response
    (so a package default cannot put one back)."""
    spec = bf.CONDITIONS[condition]
    edir = _write_shim_episode(tmp_path, include_report=spec.report,
                               include_trajectory=spec.trajectory,
                               condition=condition)
    seen = {}

    def stub(request):
        seen.update(request)
        return _stub_response()          # always offers both halves

    monkeypatch.setattr("anatase.agent.refine_json", stub)
    response = run_episode(edir)
    assert seen["include_report"] is spec.report
    assert seen["report_trajectory"] is spec.trajectory
    assert ("report" in response) is spec.report
    assert ("trajectory" in response) is spec.trajectory
    logged = json.loads(
        (edir / "calls.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert ("report" in logged["response"]) is spec.report
    assert ("trajectory" in logged["response"]) is spec.trajectory
    assert "include_trajectory" not in logged     # no echo (PROTOCOL.md 2.0)


def test_shim_requires_both_switches_in_the_marker(tmp_path, monkeypatch):
    """The 1.0 single-switch compatibility read died with the relocation —
    an old marker is in the wrong place to be read at all, so a marker
    missing a switch is a malformed build to refuse loudly, never a default
    to guess."""
    edir = _write_shim_episode(tmp_path, include_report=True,
                               include_trajectory=None)  # key omitted
    monkeypatch.setattr("anatase.agent.refine_json",
                        lambda request: _stub_response())
    with pytest.raises(KeyError):
        run_episode(edir)


# ----------------------------------------------------------------------
# fixtures: the condition axis, rendered
# ----------------------------------------------------------------------


def _prompt(condition: str, tmp_path: Path, **kw) -> str:
    return bf.render_prompt("E1", tmp_path, condition=condition, **kw)


def test_conditions_are_delivery_only_plus_the_baseline():
    """The 2.0 axis is delivery alone: the 1.1 instruction arms
    (``prompt``/``both``) are retired — round 2 measured zero bootstrap
    calls under §9 — so no condition quotes anything beyond §5/§6."""
    axes = {(c.report, c.trajectory) for c in bf.CONDITIONS.values()}
    assert axes == {(False, False),   # off
                    (True, False),    # report
                    (True, True)}     # surface
    assert all(set(c.sections) <= {"5.", "6."}
               for c in bf.CONDITIONS.values())


@pytest.mark.parametrize("condition", sorted(bf.CONDITIONS))
def test_prompt_quotes_the_manual_its_condition_declares(condition, tmp_path):
    spec = bf.CONDITIONS[condition]
    text = _prompt(condition, tmp_path)
    assert ("## 5. Read numbers, not pixels" in text) is spec.report
    assert ("## 6. Abstention is a result" in text) is spec.report
    # a report arm without the surface must say so, or it hunts for a key §5
    # promises; an arm that has the trajectory must not be told it is absent
    assert ("stripped by the harness" in text) is (spec.report
                                                   and not spec.trajectory)
    # the instruction axis is retired: no 2.0 prompt quotes §9 in any form
    assert "Read the run, not just its last state" not in text
    assert "### The DAG:" not in text


@pytest.mark.parametrize("condition", sorted(bf.CONDITIONS))
def test_prompt_glossaries_cover_the_closed_vocabularies(condition, tmp_path):
    """Every verdict and next-action token appears backticked in every
    prompt, ``off`` included — the closed vocabulary only protects anyone if
    the agent was shown all of it."""
    from tests.eval_report_agent.scorer import NEXT_ACTIONS, VERDICTS

    text = _prompt(condition, tmp_path)
    for token in VERDICTS + NEXT_ACTIONS:
        assert f"`{token}`" in text, token


def test_glossary_and_vocabulary_must_agree():
    """A token without a meaning (or a meaning without a token) fails the
    build, never confuses an agent."""
    with pytest.raises(ValueError, match="glossary/vocabulary mismatch"):
        bf._glossary({"converged": "x"}, ("converged", "abstain"))


def test_deliverable_section_renders_only_where_declared(tmp_path):
    """J1's sub-rows declare their purpose (§4b as an episode); every other
    episode's prompt carries no deliverable section at all."""
    plain = _prompt("off", tmp_path)
    assert "## Deliverable" not in plain
    phase = _prompt("off", tmp_path, deliverable="phase_id")
    struct = _prompt("off", tmp_path, deliverable="structure")
    assert "## Deliverable" in phase and "## Deliverable" in struct
    assert "phase identification" in phase
    assert "structure quality" in struct
    assert phase != struct


def test_off_carries_the_v2_contract_but_no_report_wording(tmp_path):
    """``off`` is not the 1.x report-off prompt: the v2 answer contract is
    in every arm — which is exactly why no 2.0 cell pools with any earlier
    grid — while report wording stays absent."""
    text = _prompt("off", tmp_path)
    assert "## Reading the FitReport" not in text
    assert "FitReport" not in text
    assert "run_refine" in text and "answer.json" in text
    assert '"next_action"' in text
    assert "`assumption_wrong`" in text


def test_condition_marker_is_a_sibling_and_carries_both_switches(tmp_path):
    """The marker lives beside the episode dir, never in it — the workspace
    must carry no condition bit (the round-2 leak, PROTOCOL.md 2.0)."""
    bf.write_fixtures(tmp_path / "runs", tmp_path / "truth",
                      condition="surface", only=["E1"])
    edir = tmp_path / "runs" / "E1"
    assert not (edir / "condition.json").exists()
    marker = json.loads((tmp_path / "runs" / "E1.condition.json")
                        .read_text(encoding="utf-8"))
    assert marker["protocol_version"] == bf.PROTOCOL_VERSION
    assert marker["include_report"] is True
    assert marker["include_trajectory"] is True
    assert marker["prompt_sections"] == ["5.", "6."]
    # nothing else in the workspace names the condition either
    workspace = {p.name for p in edir.iterdir()}
    assert workspace == {"episode.json", "prompt.md"}


def test_unknown_condition_is_refused(tmp_path):
    with pytest.raises(ValueError, match="condition must be one of"):
        bf.write_fixtures(tmp_path / "runs", tmp_path / "truth",
                          condition="report-on", only=["E1"])


def test_unknown_episode_id_is_refused(tmp_path):
    """Retired 1.1 ids (E2, R1, ...) must fail by name, not KeyError."""
    with pytest.raises(ValueError, match="unknown episode id"):
        bf.write_fixtures(tmp_path / "runs", tmp_path / "truth",
                          condition="off", only=["E2"])


def test_synthetic_selection_never_pays_for_a_real_dataset(tmp_path,
                                                           monkeypatch):
    """The SRM trio costs a baseline fit and W1/W2 cost real-file I/O; a
    synthetic-only build must stay as cheap as it was at 1.0."""
    def refuse():  # pragma: no cover - must not be reached
        raise AssertionError("a real-data group was built for a synthetic run")

    monkeypatch.setattr(bf, "build_real_episodes", refuse)
    monkeypatch.setattr(bf, "build_nac_episode", refuse)
    monkeypatch.setattr(bf, "build_qarr_episode", refuse)
    bf.write_fixtures(tmp_path / "runs", tmp_path / "truth",
                      condition="surface", only=["E1", "E8p"])
    dirs = sorted(p.name for p in (tmp_path / "runs").iterdir() if p.is_dir())
    assert dirs == ["E1", "E8p"]


# ----------------------------------------------------------------------
# grid: the assembled round
# ----------------------------------------------------------------------


def _cell(runs: Path, condition: str, model: str, eid: str, card_calls,
          answer, *, marker_condition=None):
    edir = runs / f"{condition}__{model}" / eid
    edir.mkdir(parents=True)
    (edir / "calls.jsonl").write_text(
        "".join(json.dumps(c) + "\n" for c in card_calls), encoding="utf-8")
    (edir / "answer.json").write_text(json.dumps(answer), encoding="utf-8")
    spec = bf.CONDITIONS[marker_condition or condition]
    (edir.parent / f"{eid}.condition.json").write_text(json.dumps({
        "protocol_version": bf.PROTOCOL_VERSION,
        "condition": marker_condition or condition,
        "include_report": spec.report,
        "include_trajectory": spec.trajectory,
        "prompt_sections": list(spec.sections),
        "max_calls": bf.MAX_CALLS,
    }), encoding="utf-8")
    return edir


def test_scorecard_condition_comes_from_the_sibling_marker(tmp_path):
    """With the echo gone from ``calls.jsonl``, the marker is the one
    authority; an episode dir without one (these tests' default) reports
    ``None`` rather than guessing."""
    truth = _write_truth(tmp_path)
    edir = _write_episode_dir(tmp_path, [
        _call(parameters=[_param("instrument.zero_shift", 0.0)],
              freed=["instrument.zero_shift"])],
        {"verdict": "converged", "summary": ""})
    assert score_episode(edir, truth)["condition"] is None
    spec = bf.CONDITIONS["report"]
    (tmp_path / f"{edir.name}.condition.json").write_text(json.dumps({
        "protocol_version": bf.PROTOCOL_VERSION, "condition": "report",
        "include_report": spec.report,
        "include_trajectory": spec.trajectory,
        "max_calls": bf.MAX_CALLS}), encoding="utf-8")
    assert score_episode(edir, truth)["condition"] == "report"


def test_grid_flags_a_cell_whose_payload_disagrees_with_its_condition(tmp_path):
    """The manipulation failure the shim cannot catch from inside one call:
    an arm that was supposed to withhold a half and did not.  It is marked,
    never explained away — the grid's own audit."""
    from tests.eval_report_agent import grid

    truth = tmp_path / "truth"
    truth.mkdir()
    (truth / "N1.json").write_text(json.dumps({
        "episode": "N1", "expected_verdict": "converged",
        "planted": None, "family": None}), encoding="utf-8")
    runs = tmp_path / "runs"
    # honest surface cell: report + trajectory, as declared
    _cell(runs, "surface", "sonnet", "N1",
          [_call(report={"summary": "s"}, trajectory=[{"stage": "a"}])],
          {"verdict": "converged", "summary": ""})
    # a cell that says "off" but was handed a report anyway
    _cell(runs, "off", "haiku", "N1",
          [_call(report={"summary": "s"})],
          {"verdict": "converged", "summary": ""})

    rows = {(r["condition"], r["model"]): r
            for r in grid.collect(runs, truth)}
    assert rows[("surface", "sonnet")]["payload_ok"] is True
    assert rows[("off", "haiku")]["payload_ok"] is False
    table = grid.render(list(rows.values()))
    assert "| surface | sonnet | pass | 1/1 |" in table
    assert "pass,!" in table            # the off cell is marked, not dropped
    assert "%" not in table             # counts, never percentages

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
# scorer v2: next_action membership, underclaimed, the deliverable axis
# ----------------------------------------------------------------------


def test_next_action_membership_gates_where_registered(tmp_path):
    """The registered *set* is the grade: a member passes, a non-member or a
    missing key fails — near-equivalents are a registration question, never
    a wording one (PROTOCOL.md 2.0)."""
    truth = _write_truth(tmp_path, expected_verdict="impurity_suspected",
                         planted=None, family=None,
                         next_action=["add_phase"])
    calls = [_call(freed=["instrument.background.c0"])]
    member = _write_episode_dir(tmp_path, calls, {
        "verdict": "impurity_suspected", "next_action": "add_phase",
        "summary": ""})
    card = score_episode(member, truth)
    assert card["next_action_ok"] is True and card["passed"]

    non_member = _write_episode_dir(tmp_path, calls, {
        "verdict": "impurity_suspected", "next_action": "none",
        "summary": ""})
    card = score_episode(non_member, truth)
    assert card["next_action_ok"] is False and not card["passed"]
    assert card["verdict_ok"]          # the verdict alone no longer passes

    missing = _write_episode_dir(tmp_path, calls, {
        "verdict": "impurity_suspected", "summary": ""})
    card = score_episode(missing, truth)
    assert card["next_action_ok"] is False and not card["passed"]


def test_next_action_is_unscored_where_no_set_is_registered(tmp_path):
    """A row without a registered set grades the verdict (and recovery)
    alone; the answered action is recorded, and an off-vocabulary token is
    noted, never a pass/fail input."""
    truth = _write_truth(tmp_path)     # E1's shape: no next_action key
    edir = _write_episode_dir(tmp_path, [
        _call(parameters=[_param("instrument.zero_shift", 0.0)],
              freed=["instrument.zero_shift"])],
        {"verdict": "converged", "next_action": "recalibrate_the_vibes",
         "summary": ""})
    card = score_episode(edir, truth)
    assert card["next_action_ok"] is None
    assert card["passed"]
    assert card["next_action"] == "recalibrate_the_vibes"
    assert any("closed vocabulary" in n for n in card["notes"])


@pytest.mark.parametrize("expected,verdict,flagged", [
    ("converged", "abstain", True),        # declines a solvable row
    ("converged", "ambiguous", True),      # same, the other token
    ("converged", "impurity_suspected", False),  # a committal miss
    ("ambiguous", "abstain", False),       # not a solvable row
    ("converged", "converged", False),     # the ordinary right answer
])
def test_underclaim_is_flagged_only_on_solvable_rows(
        tmp_path, expected, verdict, flagged):
    """The mirror of ``overclaimed``: what separates "declined correctly"
    (verdict match on the epistemic rows) from "declines everything"
    (non-committal on the solvable controls).  Descriptive — the grade stays
    the verdict match."""
    truth = _write_truth(tmp_path, expected_verdict=expected, planted=None,
                         family=None)
    edir = _write_episode_dir(tmp_path, [_call()],
                              {"verdict": verdict, "summary": ""})
    card = score_episode(edir, truth)
    assert card["underclaimed"] is flagged
    assert card["passed"] is (expected == verdict)


def test_assumption_wrong_grades_and_committal_misses_carry_no_flag(tmp_path):
    """W2's shape: ``assumption_wrong`` + ``fix_instrument_model`` passes;
    the designed-trap answer (``impurity_suspected``) is a plain miss —
    neither an overclaim nor an underclaim, because it *is* committal."""
    truth = _write_truth(tmp_path, expected_verdict="assumption_wrong",
                         planted=None, family=None,
                         next_action=["fix_instrument_model"])
    calls = [_call(freed=["instrument.background.c0"])]
    right = score_episode(_write_episode_dir(tmp_path, calls, {
        "verdict": "assumption_wrong", "next_action": "fix_instrument_model",
        "summary": ""}), truth)
    assert right["passed"]
    trapped = score_episode(_write_episode_dir(tmp_path, calls, {
        "verdict": "impurity_suspected", "next_action": "add_phase",
        "summary": ""}), truth)
    assert not trapped["passed"]
    assert not trapped["overclaimed"] and not trapped["underclaimed"]


def test_deliverable_rides_through_from_the_truth_row(tmp_path):
    """J1's sub-rows share one state and differ only in the truth record —
    the scorecard carries the axis so the grid can show it."""
    truth = _write_truth(tmp_path, expected_verdict="ambiguous", planted=None,
                         family=None, deliverable="structure",
                         next_action=["chemistry_or_contents"])
    edir = _write_episode_dir(tmp_path, [_call()], {
        "verdict": "ambiguous", "next_action": "chemistry_or_contents",
        "summary": ""})
    card = score_episode(edir, truth)
    assert card["deliverable"] == "structure" and card["passed"]
    assert score_episode(edir, _write_truth(tmp_path, expected_verdict="ambiguous",
                                            planted=None, family=None,
                                            next_action=["chemistry_or_contents"])
                         )["deliverable"] is None


# ----------------------------------------------------------------------
# scorer v2: the python-arm final_result.json adapter
# ----------------------------------------------------------------------


def _final_result_payload(parameters=(), freed=()):
    """The relevant shape of a ``RefinementResult.model_dump_json()`` — the
    fields the adapter reads and nothing else, because the scorer must not
    couple to the package version the agent's venv carried."""
    return {"status": "converged", "mode": "rietveld",
            "parameters": list(parameters),
            "stages": [{"name": "s", "freed": list(freed)}],
            "statistics": {"rwp": 0.02, "gof": 1.5}}


def _write_python_episode(tmp_path: Path, final_result, answer) -> Path:
    edir = tmp_path / "PT"
    edir.mkdir(exist_ok=True)
    (edir / "final_result.json").write_text(
        final_result if isinstance(final_result, str)
        else json.dumps(final_result), encoding="utf-8")
    if answer is not None:
        (edir / "answer.json").write_text(json.dumps(answer),
                                          encoding="utf-8")
    return edir


def test_python_arm_grades_the_final_result(tmp_path):
    """Same planted-path/tolerance logic, read off the agent's chosen final
    ``RefinementResult`` dump; the shim-only measurements record null — the
    condition audit is N/A by design in this arm."""
    truth = _write_truth(tmp_path)
    edir = _write_python_episode(tmp_path, _final_result_payload(
        parameters=[_param("instrument.zero_shift", 0.001)],
        freed=["instrument.zero_shift", "instrument.background.c0"]),
        {"verdict": "converged", "next_action": "none", "summary": ""})
    card = score_episode(edir, truth)
    assert card["arm"] == "python"
    assert card["passed"] and card["recovered"] is True
    assert card["statistics"] == {"rwp": 0.02, "gof": 1.5}
    assert card["wrong_frees"] == []
    assert card["report_present"] is None
    assert card["trajectory_rungs"] is None
    assert card["n_calls"] is None and card["plans_used"] is None
    assert card["condition"] is None   # no sibling marker in this arm


def test_python_arm_absence_still_means_never_freed(tmp_path):
    """The result model serialises vary-or-tie entries only (refine.py), so
    the JSON arm's absence rule carries over unchanged."""
    truth = _write_truth(tmp_path)
    edir = _write_python_episode(tmp_path, _final_result_payload(
        parameters=[_param("phases.0.scale", 4e-4)],
        freed=["phases.0.scale"]),
        {"verdict": "converged", "next_action": "none", "summary": ""})
    card = score_episode(edir, truth)
    assert card["recovered"] is False and not card["passed"]
    assert any("never freed" in n for n in card["notes"])


def test_python_arm_unparseable_final_result_fails_with_a_note(tmp_path):
    truth = _write_truth(tmp_path, expected_verdict="abstain", planted=None,
                         family=None)
    for payload in ("not json {", {"parameters": "nope"}):
        edir = _write_python_episode(tmp_path, payload,
                                     {"verdict": "abstain", "summary": ""})
        card = score_episode(edir, truth)
        assert card["arm"] == "python" and not card["passed"]
        assert any("final_result.json" in n for n in card["notes"])


def test_python_arm_watch_reads_off_the_dump(tmp_path):
    truth = _write_truth(tmp_path, expected_verdict="ambiguous", planted={
        "path": "instrument.geometry.sample_displacement", "start": -0.02,
        "truth": -0.08, "tol": None}, family=None, watch={
            "cause": ["instrument.geometry.sample_displacement"],
            "absorber": ["instrument.zero_shift"]})
    edir = _write_python_episode(tmp_path, _final_result_payload(
        parameters=[_param("instrument.geometry.sample_displacement", -0.079)],
        freed=["instrument.geometry.sample_displacement"]),
        {"verdict": "ambiguous", "summary": ""})
    card = score_episode(edir, truth)
    assert card["watch"] == {
        "cause": ["instrument.geometry.sample_displacement"], "absorber": []}
    assert card["planted_final_value"] == -0.079
    assert card["recovered"] is None       # tol: null — recorded, not graded
    assert card["passed"]


# ----------------------------------------------------------------------
# shim: enforcement, with refine_json stubbed
# ----------------------------------------------------------------------


def _write_shim_episode(tmp_path: Path, *, include_report: bool,
                        include_trajectory: bool | None = False,
                        max_calls: int = 8,
                        condition: str | None = None,
                        license_placement: str = "summary",
                        include_execution: bool = True) -> Path:
    """An episode dir plus its **sibling** marker (PROTOCOL.md 2.0: the
    workspace carries no condition bit).  ``include_trajectory=None`` omits
    the key — the malformed-marker case, which the shim must refuse rather
    than guess (the 1.0 single-switch compatibility read died with the
    relocation).  The 2.2 projection keys default to the status-quo shape,
    exactly as an archived marker reads through the shim's ``.get``."""
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
        "license_placement": license_placement,
        "include_execution": include_execution,
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


def _firing_report():
    """A stub report whose identifiability round-trips through the package
    schema and fires the exchange clause, its summary carrying the exact
    appended substring (``"; " + clause`` — report/__init__.py) and one
    execution-stamped action: the delivered shape both 2.2 projections act
    on.  Returns ``(report, clause)``."""
    from rietx.report import identifiability_clause
    from rietx.report.schemas import ExchangeFinding, IdentifiabilityEvidence

    evidence = IdentifiabilityEvidence(chi2_reduced=3.49, exchanges=[
        ExchangeFinding(
            held="instrument.geometry.sample_displacement", r2=0.9977,
            partner="instrument.zero_shift", partner_null=0.0,
            partner_value=0.0317, partner_esd=0.0005,
            partner_significance=63.0, exchangeable=True)])
    clause = identifiability_clause(evidence)
    assert clause is not None
    return {
        "layer1_available": True,
        "identifiability": evidence.model_dump(mode="json"),
        "summary": "Rwp=0.0100 GoF=1.00; 3 regions; " + clause,
        "suggested_actions": [{"kind": "add_impurity_phase",
                               "confidence": 0.9, "execution": "advice"}],
    }, clause


def test_shim_merges_overlay_and_forces_condition(tmp_path, monkeypatch):
    edir = _write_shim_episode(tmp_path, include_report=False)
    seen = {}

    def stub(request):
        seen.update(request)
        return _stub_response()

    monkeypatch.setattr("rietx.agent.refine_json", stub)
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
    monkeypatch.setattr("rietx.agent.refine_json",
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

    monkeypatch.setattr("rietx.agent.refine_json", stub)
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
    monkeypatch.setattr("rietx.agent.refine_json",
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
    (so a package default cannot put one back).  The 2.2 projections ride
    the same meta-test: every condition's delivered shape — clause location
    and ``execution`` presence — must match its declaration, both ways."""
    spec = bf.CONDITIONS[condition]
    edir = _write_shim_episode(tmp_path, include_report=spec.report,
                               include_trajectory=spec.trajectory,
                               condition=condition,
                               license_placement=spec.license_placement,
                               include_execution=spec.execution)
    report, clause = _firing_report()
    seen = {}

    def stub(request):
        seen.update(request)
        full = _stub_response()          # always offers both halves...
        full["report"] = report          # ...with a firing clause and an
        return full                      # execution-stamped action

    monkeypatch.setattr("rietx.agent.refine_json", stub)
    response = run_episode(edir)
    assert seen["include_report"] is spec.report
    assert seen["report_trajectory"] is spec.trajectory
    assert ("report" in response) is spec.report
    assert ("trajectory" in response) is spec.trajectory
    stats = response["result"]["statistics"]
    want_statline = spec.report and spec.license_placement == "statistics"
    assert ("identifiability_clause" in stats) is want_statline
    if spec.report:
        assert (clause in response["report"]["summary"]) is not want_statline
        delivered_exec = any(
            "execution" in a
            for a in response["report"]["suggested_actions"])
        assert delivered_exec is spec.execution
    logged = json.loads(
        (edir / "calls.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert ("report" in logged["response"]) is spec.report
    assert ("trajectory" in logged["response"]) is spec.trajectory
    assert "include_trajectory" not in logged     # no echo (PROTOCOL.md 2.0)
    assert "license_placement" not in logged      # the 2.2 keys neither
    assert "include_execution" not in logged


def test_shim_requires_both_switches_in_the_marker(tmp_path, monkeypatch):
    """The 1.0 single-switch compatibility read died with the relocation —
    an old marker is in the wrong place to be read at all, so a marker
    missing a switch is a malformed build to refuse loudly, never a default
    to guess."""
    edir = _write_shim_episode(tmp_path, include_report=True,
                               include_trajectory=None)  # key omitted
    monkeypatch.setattr("rietx.agent.refine_json",
                        lambda request: _stub_response())
    with pytest.raises(KeyError):
        run_episode(edir)


# ----------------------------------------------------------------------
# shim: the 2.2 projections (PROTOCOL.md 2.2)
# ----------------------------------------------------------------------


def test_shim_moves_the_clause_beside_the_statistics(tmp_path, monkeypatch):
    """The ``"statistics"`` placement is a *move*, byte-exact: the rendered
    clause lands as ``result.statistics["identifiability_clause"]`` and its
    appended substring leaves the summary — one copy, one location, and the
    log carries the same shape the agent saw."""
    report, clause = _firing_report()
    edir = _write_shim_episode(tmp_path, include_report=True,
                               condition="report_stat",
                               license_placement="statistics")
    stub = _stub_response()
    stub["report"] = report
    monkeypatch.setattr("rietx.agent.refine_json", lambda request: stub)
    response = run_episode(edir)
    assert response["result"]["statistics"]["identifiability_clause"] == clause
    assert response["report"]["summary"] == "Rwp=0.0100 GoF=1.00; 3 regions"
    logged = json.loads(
        (edir / "calls.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert (logged["response"]["result"]["statistics"]
            ["identifiability_clause"] == clause)
    assert clause not in logged["response"]["report"]["summary"]


def test_shim_placement_mismatch_fails_the_call_loudly(tmp_path, monkeypatch):
    """A summary that does not carry the rendered clause's exact substring
    is a projection the shim cannot apply: the call fails with a named code
    (the registration invalidates the cell), never a silent fallback — and
    the record logs the failure as a spent, non-refused call."""
    report, _clause = _firing_report()
    report["summary"] = "Rwp=0.0100 GoF=1.00; 3 regions"  # clause absent
    edir = _write_shim_episode(tmp_path, include_report=True,
                               condition="report_stat",
                               license_placement="statistics")
    stub = _stub_response()
    stub["report"] = report
    monkeypatch.setattr("rietx.agent.refine_json", lambda request: stub)
    response = run_episode(edir)
    assert response["ok"] is False
    assert response["error"]["code"] == "PLACEMENT_PROJECTION_MISMATCH"
    logged = json.loads(
        (edir / "calls.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert logged["refused"] is False
    assert logged["response"]["ok"] is False


def test_shim_projection_is_a_checked_noop_on_the_shipped_field(
        tmp_path, monkeypatch):
    """WP-1108 shipped the placement: ``build_report`` writes the summary's
    clause into ``result.statistics`` too, so a real response reaches the
    projection with the field already present and equal.  The injection is a
    no-op and the excision still constructs the round's *moved* shape — the
    package ships the copy, the arm delivered one copy in one location.
    (The package side of this equivalence is pinned by
    ``test_fitreport_layers.py::
    test_refine_json_delivers_the_license_beside_the_numbers``.)"""
    report, clause = _firing_report()
    edir = _write_shim_episode(tmp_path, include_report=True,
                               condition="report_stat",
                               license_placement="statistics")
    stub = _stub_response()
    stub["report"] = report
    stub["result"]["statistics"]["identifiability_clause"] = clause
    monkeypatch.setattr("rietx.agent.refine_json", lambda request: stub)
    response = run_episode(edir)
    assert response["result"]["statistics"]["identifiability_clause"] == clause
    assert clause not in response["report"]["summary"]


def test_shim_refuses_a_shipped_field_that_disagrees(tmp_path, monkeypatch):
    """A shipped ``statistics.identifiability_clause`` that is not the
    re-rendered clause is the render/excise mismatch one surface over: the
    package and the projection disagreeing about the sentence invalidates
    the cell by the same named code, never a silent overwrite."""
    report, _clause = _firing_report()
    edir = _write_shim_episode(tmp_path, include_report=True,
                               condition="report_stat",
                               license_placement="statistics")
    stub = _stub_response()
    stub["report"] = report
    stub["result"]["statistics"]["identifiability_clause"] = "another sentence"
    monkeypatch.setattr("rietx.agent.refine_json", lambda request: stub)
    response = run_episode(edir)
    assert response["ok"] is False
    assert response["error"]["code"] == "PLACEMENT_PROJECTION_MISMATCH"
    assert "WP-1108" in response["error"]["message"]


def test_shim_placement_is_inert_without_a_clause(tmp_path, monkeypatch):
    """No firing clause, nothing to move: the ``"statistics"`` arm delivers
    the response unchanged — the key is absent, never null (a writerless
    claim, the WP-1076 rule)."""
    edir = _write_shim_episode(tmp_path, include_report=True,
                               condition="report_stat",
                               license_placement="statistics")
    stub = _stub_response()
    stub["report"] = {"layer1_available": True, "identifiability": None,
                      "summary": "Rwp=0.0100 GoF=1.00; 3 regions"}
    monkeypatch.setattr("rietx.agent.refine_json", lambda request: stub)
    response = run_episode(edir)
    assert "identifiability_clause" not in response["result"]["statistics"]
    assert response["report"]["summary"] == "Rwp=0.0100 GoF=1.00; 3 regions"


def test_shim_strips_execution_when_the_condition_says_so(tmp_path,
                                                          monkeypatch):
    """``include_execution: false`` pops WP-1106's field from every
    delivered action — and only that field: the action's kind and confidence
    survive untouched."""
    report, _clause = _firing_report()
    edir = _write_shim_episode(tmp_path, include_report=True,
                               condition="report_noexec",
                               include_execution=False)
    stub = _stub_response()
    stub["report"] = report
    monkeypatch.setattr("rietx.agent.refine_json", lambda request: stub)
    response = run_episode(edir)
    actions = response["report"]["suggested_actions"]
    assert actions == [{"kind": "add_impurity_phase", "confidence": 0.9}]


# ----------------------------------------------------------------------
# scorer: the v3 contract and the 2.2 delivered-shape facts
# ----------------------------------------------------------------------


def test_scorer_records_caveats_and_the_delivered_shape(tmp_path):
    """``caveats`` is recorded, never graded (the stance the retired
    ``report_with_caveat`` token used to absorb), and the four 2.2 shape
    facts read straight off the delivered calls."""
    truth = _write_truth(tmp_path, planted=None, family=None)
    report, clause = _firing_report()
    call = _call(report=report)
    call["response"]["result"]["statistics"]["identifiability_clause"] = clause
    edir = _write_episode_dir(tmp_path, [call], {
        "verdict": "converged", "next_action": "none",
        "caveats": ["Durbin-Watson 0.66: residual peak-shape misfit"],
        "summary": ""})
    card = score_episode(edir, truth)
    assert card["caveats"] == [
        "Durbin-Watson 0.66: residual peak-shape misfit"]
    assert not any("caveats" in n for n in card["notes"])
    assert card["license_in_statistics"] is True
    assert card["statline_missing_where_fired"] is False
    assert card["execution_delivered"] is True
    assert card["action_missing_execution"] is False
    assert card["passed"]                     # caveats never touch the grade


def test_scorer_reads_the_statline_gap_and_the_stripped_field(tmp_path):
    """The two mismatch directions the grid audits: an exchangeable finding
    delivered without the statistics key, and an action missing
    ``execution`` — both shape-only, no rendering in the scorer."""
    truth = _write_truth(tmp_path, planted=None, family=None)
    report, _clause = _firing_report()
    report["suggested_actions"].append(
        {"kind": "refine_biso", "confidence": 0.2})   # no execution key
    edir = _write_episode_dir(tmp_path, [_call(report=report)], {
        "verdict": "converged", "summary": ""})
    card = score_episode(edir, truth)
    assert card["license_in_statistics"] is False
    assert card["statline_missing_where_fired"] is True
    assert card["execution_delivered"] is True
    assert card["action_missing_execution"] is True


def test_scorer_tolerates_absent_and_malformed_caveats(tmp_path):
    """Absent reads as unwritten (``None``), a wrong shape is noted and
    recorded as written — descriptive either way, never a grade input."""
    truth = _write_truth(tmp_path, planted=None, family=None)
    edir = _write_episode_dir(tmp_path, [_call()], {
        "verdict": "converged", "summary": ""})
    card = score_episode(edir, truth)
    assert card["caveats"] is None
    edir2 = tmp_path / "ET2"
    edir2.mkdir()
    (edir2 / "calls.jsonl").write_text(json.dumps(_call()) + "\n",
                                       encoding="utf-8")
    (edir2 / "answer.json").write_text(json.dumps({
        "verdict": "converged", "caveats": "one bare string",
        "summary": ""}), encoding="utf-8")
    card2 = score_episode(edir2, truth)
    assert card2["caveats"] == "one bare string"
    assert any("caveats" in n for n in card2["notes"])


def test_report_with_caveat_is_off_vocabulary_at_v3(tmp_path):
    """The retired token scores exactly like any off-vocabulary word: the
    2.1 hedge sink cannot pass a registered set again."""
    truth = _write_truth(tmp_path, next_action=["none"], planted=None,
                         family=None)
    edir = _write_episode_dir(tmp_path, [_call()], {
        "verdict": "converged", "next_action": "report_with_caveat",
        "summary": ""})
    card = score_episode(edir, truth)
    assert card["next_action_ok"] is False
    assert not card["passed"]
    assert any("closed" in n for n in card["notes"])


# ----------------------------------------------------------------------
# fixtures: the condition axis, rendered
# ----------------------------------------------------------------------


def _prompt(condition: str, tmp_path: Path, **kw) -> str:
    return bf.render_prompt("E1", tmp_path, condition=condition, **kw)


def test_conditions_are_delivery_only_plus_the_baseline():
    """The 2.0 axis is delivery alone: the 1.1 instruction arms
    (``prompt``/``both``) are retired — round 2 measured zero bootstrap
    calls under §9 — so no condition quotes anything beyond §5/§6.  The 2.2
    projection arms move response *shape*, never delivery: each differs from
    ``report`` on exactly one projection, and neither touches a withheld or
    trajectory-bearing arm."""
    axes = {(c.report, c.trajectory) for c in bf.CONDITIONS.values()}
    assert axes == {(False, False),   # off
                    (True, False),    # report, report_stat, report_noexec
                    (True, True)}     # surface
    assert all(set(c.sections) <= {"5.", "6."}
               for c in bf.CONDITIONS.values())
    projected = {name: (c.license_placement, c.execution)
                 for name, c in bf.CONDITIONS.items()
                 if (c.license_placement, c.execution) != ("summary", True)}
    assert projected == {"report_stat": ("statistics", True),
                         "report_noexec": ("summary", False)}
    for name in projected:
        spec = bf.CONDITIONS[name]
        assert spec.report and not spec.trajectory
        assert spec.sections == bf.CONDITIONS["report"].sections


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


def test_off_carries_the_answer_contract_but_no_report_wording(tmp_path):
    """``off`` is not the 1.x report-off prompt: the answer contract (v3 at
    2.2 — ``caveats`` in, ``report_with_caveat`` out) is in every arm —
    which is exactly why no 2.x cell pools with any earlier grid — while
    report wording stays absent."""
    text = _prompt("off", tmp_path)
    assert "## Reading the FitReport" not in text
    assert "FitReport" not in text
    assert "run_refine" in text and "answer.json" in text
    assert '"next_action"' in text
    assert '"caveats"' in text
    assert "`report_with_caveat`" not in text
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
        "license_placement": spec.license_placement,
        "include_execution": spec.execution,
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


def test_grid_renders_two_group_tables_and_the_python_arm(tmp_path):
    """The epistemic and solvable groups are separate count tables, always
    (pooling them is how round 1's null was misread); a python cell has no
    marker and its payload audit is N/A, never a `!`."""
    from tests.eval_report_agent import grid

    truth = tmp_path / "truth"
    truth.mkdir()
    (truth / "N1.json").write_text(json.dumps({
        "episode": "N1", "expected_verdict": "ambiguous",
        "next_action": ["extend_range_or_calibrate"],
        "planted": None, "family": None}), encoding="utf-8")
    (truth / "C1.json").write_text(json.dumps({
        "episode": "C1", "expected_verdict": "converged",
        "next_action": ["none"], "planted": None, "family": None}),
        encoding="utf-8")
    runs = tmp_path / "runs"
    # a JSON cell on the epistemic row: verdict right, action out of the set
    _cell(runs, "report", "sonnet", "N1",
          [_call(report={"summary": "s"})],
          {"verdict": "ambiguous", "next_action": "none", "summary": ""})
    # a python cell on the solvable row: no marker, final_result.json,
    # underclaiming — the flag the solvable table exists to show
    pdir = runs / "python__sonnet" / "C1"
    pdir.mkdir(parents=True)
    (pdir / "final_result.json").write_text(
        json.dumps(_final_result_payload()), encoding="utf-8")
    (pdir / "answer.json").write_text(json.dumps(
        {"verdict": "abstain", "next_action": "collect_better_data",
         "summary": ""}), encoding="utf-8")

    rows = grid.collect(runs, truth)
    by = {(r["condition"], r["episode"]): r for r in rows}
    assert by[("python", "C1")]["arm"] == "python"
    assert by[("python", "C1")]["payload_ok"] is None
    assert by[("python", "C1")]["group"] == "solvable"
    assert by[("report", "N1")]["group"] == "epistemic"
    text = grid.render(rows)
    assert "## Epistemic rows" in text and "## Solvable rows" in text
    assert "ambiguous,na" in text       # verdict right, action missed
    assert "abstain,uc,na" in text      # the underclaim, flagged as such
    assert "%" not in text


def test_a_json_cell_without_its_marker_is_invalid(tmp_path):
    """The marker is the payload audit's authority; a shim cell that lost it
    is unauditable, and unauditable is invalid (`!`), never quietly N/A —
    only the markerless-by-design python arm gets N/A."""
    from tests.eval_report_agent import grid

    truth = tmp_path / "truth"
    truth.mkdir()
    (truth / "N1.json").write_text(json.dumps({
        "episode": "N1", "expected_verdict": "converged",
        "planted": None, "family": None}), encoding="utf-8")
    edir = tmp_path / "runs" / "off__haiku" / "N1"
    edir.mkdir(parents=True)
    (edir / "calls.jsonl").write_text(json.dumps(_call()) + "\n",
                                      encoding="utf-8")
    (edir / "answer.json").write_text(json.dumps(
        {"verdict": "converged", "summary": ""}), encoding="utf-8")
    rows = grid.collect(tmp_path / "runs", truth)
    assert rows[0]["payload_ok"] is False
    assert "pass,!" in grid.render(rows)


def test_grid_audits_the_projections_where_the_marker_declares_them(
        tmp_path):
    """The 2.2 payload audit, all four directions: a ``report_stat`` cell
    whose statline never carried a fired clause, a ``report`` cell that
    leaked the statline, a ``report_noexec`` cell still delivering
    ``execution``, and the honest status-quo cell — mismatches are ``!``,
    never explained."""
    from tests.eval_report_agent import grid

    truth = tmp_path / "truth"
    truth.mkdir()
    (truth / "N1.json").write_text(json.dumps({
        "episode": "N1", "expected_verdict": "converged",
        "planted": None, "family": None}), encoding="utf-8")
    runs = tmp_path / "runs"
    answer = {"verdict": "converged", "summary": ""}

    # marker says statistics; the delivered calls never carried the key
    _cell(runs, "report_stat", "sonnet", "N1",
          [_call(report=_firing_report()[0])], answer)
    # marker says summary; the statline leaked in anyway
    leaked_report, leaked_clause = _firing_report()
    leaked = _call(report=leaked_report)
    leaked["response"]["result"]["statistics"][
        "identifiability_clause"] = leaked_clause
    _cell(runs, "report", "sonnet", "N1", [leaked], answer)
    # marker says no execution; the field arrived anyway
    _cell(runs, "report_noexec", "haiku", "N1",
          [_call(report=_firing_report()[0])], answer)
    # the honest status quo: clause in the summary, execution delivered
    _cell(runs, "report", "haiku", "N1",
          [_call(report=_firing_report()[0])], answer)

    rows = {(r["condition"], r["model"]): r for r in grid.collect(runs, truth)}
    assert rows[("report_stat", "sonnet")]["payload_ok"] is False
    assert rows[("report", "sonnet")]["payload_ok"] is False
    assert rows[("report_noexec", "haiku")]["payload_ok"] is False
    assert rows[("report", "haiku")]["payload_ok"] is True


def test_grid_leaves_archived_markers_unaudited_on_the_new_axes(tmp_path):
    """A pre-2.2 marker carries neither projection key, and absent means the
    condition never existed — a 2.1-era record (actions without
    ``execution``, clause in the summary) re-grades without a ``!``, so the
    archived rounds' grids regenerate byte-identically."""
    from tests.eval_report_agent import grid

    truth = tmp_path / "truth"
    truth.mkdir()
    (truth / "N1.json").write_text(json.dumps({
        "episode": "N1", "expected_verdict": "converged",
        "planted": None, "family": None}), encoding="utf-8")
    runs = tmp_path / "runs"
    era_report, _clause = _firing_report()
    for action in era_report["suggested_actions"]:
        action.pop("execution", None)          # a thresholds-0.9 response
    edir = _cell(runs, "report", "sonnet", "N1", [_call(report=era_report)],
                 {"verdict": "converged", "summary": ""})
    marker_path = edir.parent / "N1.condition.json"
    marker = json.loads(marker_path.read_text(encoding="utf-8"))
    del marker["license_placement"], marker["include_execution"]
    marker["protocol_version"] = "2.1"
    marker_path.write_text(json.dumps(marker), encoding="utf-8")

    rows = grid.collect(runs, truth)
    assert rows[0]["action_missing_execution"] is True   # the fact is read
    assert rows[0]["payload_ok"] is True                 # but never audited

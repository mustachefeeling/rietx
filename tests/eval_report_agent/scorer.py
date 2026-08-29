"""Deterministic scorer for the eval episodes (v2, PROTOCOL.md 2.0).

Grades one episode dir against the scorer-side truth record
``build_fixtures`` wrote.  Two arms, one grading logic:

- **JSON arm**: the answer state is the **last successful** call in
  ``calls.jsonl`` (the shim's record — never the agent's self-report);
- **python arm**: the answer state is ``final_result.json`` — the agent's
  chosen final ``RefinementResult.model_dump_json()``.  The planted-path /
  tolerance / watch logic reads off it unchanged, because the result model
  itself serialises **vary-or-tie entries only** (refine.py), so absence
  still means never-freed.  ``report_present``/``trajectory_rungs`` record
  null — the condition audit is N/A by design in this arm — and the call
  counts are the transcript audit's to make, not this file's.

Rules, from PROTOCOL.md 2.0 § Scoring rules:

- ``passed`` = verdict match ∧ tolerance-recovery *where a tolerance is
  registered* ∧ ``next_action`` ∈ the truth row's registered set *where a
  set is registered*.  The single grade; everything else is descriptive.
- recovery is by the planted parameter, never delta-chi2 (WP-1052); a
  planted path absent from the answer state's ``parameters`` was never
  freed and scores not-recovered, deterministically;
- ``next_action`` is graded by **set membership** — near-equivalents are a
  registration question, never a wording one; an off-vocabulary token is
  noted and can never be in a registered set;
- no answer state (no successful call / no parseable final result), or no
  valid ``answer.json`` → failed;
- ``overclaimed``: expected non-committal, answered ``converged``.
  ``underclaimed`` (new): expected ``converged``, answered non-committal —
  what separates "declined correctly" from "declines everything".  Both
  descriptive; neither touches ``passed``;
- wrong-frees and ``watch`` groups: descriptive localisation evidence,
  never pass/fail inputs;
- the condition comes from the **sibling marker** (PROTOCOL.md 2.0: no
  condition bit in the workspace); ``deliverable`` rides through from the
  truth row (J1's sub-rows share one state and differ only there).

Usage::

    python -m tests.eval_report_agent.scorer EPISODE_DIR TRUTH_FILE
"""

from __future__ import annotations

import argparse
import json
import sys
from fnmatch import fnmatch
from pathlib import Path

#: the answer's closed verdict vocabulary (v2, PROTOCOL.md 2.0).
#: ``assumption_wrong`` is the W2 verdict — a *declared input* (source lines,
#: geometry) disagreeing with the data — kept distinct from
#: ``impurity_suspected`` (the *specimen's phase content*): the prompt
#: glossary draws that line, and ``build_fixtures`` renders both glossaries
#: from these tuples so a token cannot exist without a meaning
VERDICTS = ("converged", "impurity_suspected", "assumption_wrong",
            "abstain", "ambiguous")

#: the answer's closed next-action vocabulary (v3, PROTOCOL.md 2.2) — graded
#: by membership in the truth row's registered *set*, so near-equivalents are
#: a registration question, never a wording one.  ``report_with_caveat``
#: left at 2.2: the one delivery-stance token in a remedial vocabulary, and
#: on real data an unfalsifiable hedge sink (the WP-1107 archaeology, 7 of
#: 10 valid 2.1 cells); the stance moved to the unscored ``caveats`` list
NEXT_ACTIONS = ("none", "extend_range_or_calibrate", "add_phase",
                "fix_instrument_model", "collect_better_data",
                "chemistry_or_contents")

#: verdicts that decline to name one confident cause; answering ``converged``
#: where one of these is expected is an overclaim, and answering one of these
#: where ``converged`` is expected is an underclaim.
#: ``impurity_suspected``/``assumption_wrong`` are committal claims, so they
#: are misses, never overclaims or underclaims
NON_COMMITTAL = ("abstain", "ambiguous")

#: an explicit stage list no longer than this is a *bootstrap* plan — a state
#: reached deliberately before the plan's own end.  Two, not one, because the
#: state where a report speaks is an early rung and not always the first
BOOTSTRAP_MAX_STAGES = 2

#: paths always legitimate to free, whatever was planted: the background is
#: co-refined, never subtracted (CLAUDE.md Weights), and scale + background
#: is the mandatory first stage of every legitimate plan (the agent skill §2)
#: — a metric that flagged textbook stage 1 on every episode would measure
#: the protocol, not the agent's localisation
ALWAYS_LEGIT = ("instrument.background.*", "phases.*.scale")


def _matches_any(path: str, globs) -> bool:
    return any(fnmatch(path, g) for g in globs)


def _load_calls(episode_dir: Path) -> list[dict]:
    log = episode_dir / "calls.jsonl"
    if not log.exists():
        return []
    return [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()
            if line.strip()]


def _plan_label(overlay: dict) -> str:
    """How one call asked to be planned, in one token: the preset name, the
    stage count of an explicit list, or ``default`` for an absent plan."""
    plan = overlay.get("plan")
    if plan is None:
        return "default"
    if isinstance(plan, str):
        return plan
    if isinstance(plan, dict):
        stages = plan.get("stages")
        return f"stages:{len(stages) if isinstance(stages, list) else '?'}"
    return "unknown"


def _is_bootstrap(label: str) -> bool:
    prefix, _, count = label.partition(":")
    return (prefix == "stages" and count.isdigit()
            and int(count) <= BOOTSTRAP_MAX_STAGES)


def _condition(episode_dir: Path) -> str | None:
    """The condition, from the sibling marker (PROTOCOL.md 2.0: the marker —
    and with it every condition bit — lives outside the workspace, so neither
    the agent's ``ls`` nor its own call log can reveal it).  A python-arm
    workspace has no marker and reports ``None``: its condition audit is N/A
    by design."""
    path = episode_dir.resolve()
    marker = path.parent / f"{path.name}.condition.json"
    if not marker.exists():
        return None
    return json.loads(marker.read_text(encoding="utf-8")).get("condition")


def _answer(episode_dir: Path) -> tuple[dict | None, str | None]:
    """(answer, problem) — an unreadable or invalid answer.json is a scored
    failure with a note, never a scorer crash."""
    path = episode_dir / "answer.json"
    if not path.exists():
        return None, "answer.json missing"
    try:
        answer = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        return None, f"answer.json is not valid JSON: {exc}"
    if not isinstance(answer, dict) or answer.get("verdict") not in VERDICTS:
        return None, ("answer.json verdict must be one of "
                      + " | ".join(VERDICTS))
    return answer, None


def _final_result(episode_dir: Path) -> tuple[dict | None, str | None]:
    """(result, problem) for the python arm's ``final_result.json``.

    Minimal shape check only — ``parameters`` and ``stages`` lists — because
    the grading below reads nothing else; a full schema validation would
    couple the scorer to the package version the *agent's* venv carried.
    """
    path = episode_dir / "final_result.json"
    try:
        result = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        return None, f"final_result.json is not valid JSON: {exc}"
    if (not isinstance(result, dict)
            or not isinstance(result.get("parameters"), list)
            or not isinstance(result.get("stages"), list)):
        return None, ("final_result.json must be a RefinementResult dump "
                      "with parameters and stages lists")
    return result, None


def score_episode(episode_dir: Path, truth_file: Path) -> dict:
    """The per-episode scorecard, graded from the record alone."""
    truth = json.loads(truth_file.read_text(encoding="utf-8"))
    python_arm = (episode_dir / "final_result.json").exists()
    answer, answer_problem = _answer(episode_dir)

    card = {
        "episode": truth["episode"],
        "arm": "python" if python_arm else "json",
        "condition": _condition(episode_dir),
        "deliverable": truth.get("deliverable"),
        "verdict": answer.get("verdict") if answer else None,
        "expected_verdict": truth["expected_verdict"],
        "next_action": answer.get("next_action") if answer else None,
        "registered_next_actions": truth.get("next_action"),
        "summary": answer.get("summary", "") if answer else "",
        # v3 (PROTOCOL.md 2.2): recorded, never graded — the delivery stance
        # the retired ``report_with_caveat`` token used to absorb.  Mining
        # counts it descriptively; absence reads as empty
        "caveats": answer.get("caveats") if answer else None,
        "notes": [],
    }
    if answer_problem:
        card["notes"].append(answer_problem)
    if (card["caveats"] is not None
            and (not isinstance(card["caveats"], list)
                 or any(not isinstance(c, str) for c in card["caveats"]))):
        card["notes"].append(
            "caveats should be a list of strings; recorded as written")
    if (card["next_action"] is not None
            and card["next_action"] not in NEXT_ACTIONS):
        card["notes"].append(
            f"next_action {card['next_action']!r} is not in the closed "
            "vocabulary")

    # ---- the answer state, per arm -----------------------------------
    if python_arm:
        state, state_problem = _final_result(episode_dir)
        card.update({"n_calls": None, "n_refused": None,
                     "n_failed_calls": None, "plans_used": None,
                     "bootstrap_calls": None, "excluded_regions": None})
        # the condition audit is N/A in this arm, by design: there is no
        # shim, so there is nothing whose delivery could disagree
        card["report_present"] = None
        card["trajectory_rungs"] = None
        card["license_in_statistics"] = None
        card["statline_missing_where_fired"] = None
        card["execution_delivered"] = None
        card["action_missing_execution"] = None
        if state_problem:
            card["notes"].append(state_problem)
    else:
        calls = _load_calls(episode_dir)
        ok_calls = [c for c in calls if not c.get("refused", False)
                    and c["response"].get("ok", False)]
        final = ok_calls[-1] if ok_calls else None
        state = final["response"]["result"] if final is not None else None
        card["n_calls"] = len([c for c in calls
                               if not c.get("refused", False)])
        card["n_refused"] = len([c for c in calls if c.get("refused", False)])
        card["n_failed_calls"] = len([c for c in calls
                                      if not c.get("refused", False)
                                      and not c["response"].get("ok", False)])
        card["excluded_regions"] = [c["overlay"]["two_theta_limits"]
                                    for c in ok_calls
                                    if c["overlay"].get("two_theta_limits")]
        plans = [_plan_label(c["overlay"]) for c in calls
                 if not c.get("refused", False)]
        card["plans_used"] = plans
        card["bootstrap_calls"] = sum(1 for label in plans
                                      if _is_bootstrap(label))
        if state is None:
            card["notes"].append("no successful refinement call")
        # what the graded call actually carried — the condition's own audit
        card["report_present"] = None
        card["trajectory_rungs"] = None
        if final is not None:
            response = final["response"]
            card["report_present"] = "report" in response
            if isinstance(response.get("trajectory"), list):
                card["trajectory_rungs"] = len(response["trajectory"])
        # the 2.2 delivered-shape facts (PROTOCOL.md 2.2), read over every
        # ok call — a projection is per-call, so one leak anywhere is the
        # mismatch.  ``statline_missing_where_fired`` pairs per call: an
        # exchangeable finding delivered without the statistics key is the
        # ``"statistics"`` placement silently not applied (the exchange
        # firing implies the clause, shape-only — no rendering here)
        card["license_in_statistics"] = None
        card["statline_missing_where_fired"] = None
        card["execution_delivered"] = None
        card["action_missing_execution"] = None
        if ok_calls:
            in_stats, missing, has_exec, lacks_exec = [], [], [], []
            for c in ok_calls:
                resp = c["response"]
                stats = (resp.get("result") or {}).get("statistics") or {}
                has_key = "identifiability_clause" in stats
                in_stats.append(has_key)
                report = resp.get("report")
                report = report if isinstance(report, dict) else {}
                exchanges = ((report.get("identifiability") or {})
                             .get("exchanges") or [])
                fired = any(isinstance(e, dict) and e.get("exchangeable")
                            for e in exchanges)
                missing.append(fired and not has_key)
                actions = [a for a in (report.get("suggested_actions") or [])
                           if isinstance(a, dict)]
                has_exec.append(any("execution" in a for a in actions))
                lacks_exec.append(any("execution" not in a for a in actions))
            card["license_in_statistics"] = any(in_stats)
            card["statline_missing_where_fired"] = any(missing)
            card["execution_delivered"] = any(has_exec)
            card["action_missing_execution"] = any(lacks_exec)

    card["statistics"] = None
    if state is not None:
        stats = state.get("statistics") or {}
        card["statistics"] = {k: stats[k] for k in ("rwp", "gof")
                              if k in stats}

    # ---- the grade and its descriptive companions --------------------
    verdict_ok = (answer is not None
                  and answer["verdict"] == truth["expected_verdict"])
    card["verdict_ok"] = verdict_ok
    card["overclaimed"] = bool(
        answer is not None
        and truth["expected_verdict"] in NON_COMMITTAL
        and answer["verdict"] == "converged")
    card["underclaimed"] = bool(
        answer is not None
        and truth["expected_verdict"] == "converged"
        and answer["verdict"] in NON_COMMITTAL)

    registered = truth.get("next_action")
    card["next_action_ok"] = (None if not registered
                              else card["next_action"] in registered)

    planted = truth.get("planted")
    card["planted_path"] = planted["path"] if planted else None
    card["recovered"] = None
    card["planted_final_value"] = None
    if planted and state is not None:
        rows = {p["path"]: p for p in state["parameters"]}
        row = rows.get(planted["path"])
        if row is not None:
            card["planted_final_value"] = row["value"]
        tol = planted.get("tol")
        if tol is not None:
            if row is None:
                # never freed => still the planted start (the start is fixed;
                # the result serialises vary-or-tie entries only — docstring)
                card["recovered"] = False
                card["notes"].append(
                    f"{planted['path']} absent from parameters: never freed, "
                    "value is the planted start")
            elif "abs" in tol:
                card["recovered"] = (
                    abs(row["value"] - planted["truth"]) <= tol["abs"])
            else:
                card["recovered"] = (
                    abs(row["value"] - planted["truth"])
                    <= tol["rel"] * abs(planted["truth"]))

    family = truth.get("family")
    card["freed"] = []
    card["wrong_frees"] = None
    if state is not None:
        freed: set[str] = set()
        for stage in state["stages"]:
            freed.update(stage["freed"])
        card["freed"] = sorted(freed)
        if family:
            legit = list(family) + list(ALWAYS_LEGIT)
            card["wrong_frees"] = sorted(
                p for p in freed if not _matches_any(p, legit))

    # truth-declared watch groups: which named set of paths the agent freed.
    # Data, not code — the cause-vs-absorber choice is the same question
    # asked of every position episode
    card["watch"] = {}
    for name, globs in (truth.get("watch") or {}).items():
        card["watch"][name] = sorted(p for p in card["freed"]
                                     if _matches_any(p, globs))

    needs_recovery = bool(planted and planted.get("tol"))
    card["passed"] = bool(
        state is not None and verdict_ok
        and (card["recovered"] if needs_recovery else True)
        and (card["next_action_ok"] if registered else True))
    return card


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("episode_dir", type=Path)
    parser.add_argument("truth_file", type=Path)
    args = parser.parse_args(argv)
    card = score_episode(args.episode_dir, args.truth_file)
    json.dump(card, sys.stdout, indent=1)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

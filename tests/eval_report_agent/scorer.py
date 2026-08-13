"""Deterministic scorer for the eval episodes.

Grades one episode dir from its ``calls.jsonl`` (the shim's record — never
the agent's self-report) plus the mandated ``answer.json``, against the
scorer-side truth record ``build_fixtures`` wrote.  Rules, from the WP:

- recovery episodes (a ``planted`` entry with a ``tol``): pass iff the
  verdict is the expected one **and** the planted parameter is at truth
  within tolerance in the *last* non-refused successful call — recovery is by
  the planted parameter, never by delta-chi2 (WP-1052 finding 2);
- the ``AgentSuccess`` surface serialises only vary-or-tie entries
  (refine.py:1397), so a planted path absent from that call's ``parameters``
  was never freed and still holds the planted start: absence scores
  not-recovered, deterministically;
- trap episodes (E5/E7/E8) and the real-data refusal row (R1): pass iff the
  verdict matches.  R1 plants a parameter *without* a tolerance on purpose —
  its displacement is recorded and never graded, because on that pattern
  recovering it is not what the data licenses (WP-1059);
- an episode with no successful call, or no ``answer.json``, fails —
  an answer with no refinement behind it scores zero;
- wrong-frees (recovery episodes only): stage-``freed`` paths outside the
  planted family + ``ALWAYS_LEGIT``, unioned over the answer call's stages.
  A descriptive localisation metric, never a pass/fail input — the lazy
  default plan solves E1/E4 while freeing plenty outside the family.

Four descriptive measurements ride beside the grade (WP-1059) — none of them
touches ``passed``:

- ``overclaimed``: the answer says ``converged`` where the episode's supported
  verdict is a non-committal one.  The failure mode this whole package exists
  to avoid, and a bare ``verdict_ok=False`` does not distinguish it from
  abstaining on a solvable row;
- ``watch``: truth-declared glob groups reported against what was freed — how
  the E3 sign inversion, and R1's cause-vs-absorber choice, are read off a
  grid rather than out of a transcript;
- ``bootstrap_calls`` / ``plans_used``: how often the agent asked for a
  deliberately short plan.  Round 1's measured mechanism was that agents never
  generate the states where the report speaks, so this is the dependent
  variable of the prompt-vs-surface contrast;
- ``report_present`` / ``trajectory_rungs``: what the graded call actually
  carried.  The condition is enforced by the shim, but a grid that cannot show
  the enforcement held is a grid nobody can check.

Usage::

    python -m tests.eval_report_agent.scorer EPISODE_DIR TRUTH_FILE
"""

from __future__ import annotations

import argparse
import json
import sys
from fnmatch import fnmatch
from pathlib import Path

VERDICTS = ("converged", "impurity_suspected", "abstain", "ambiguous")

#: verdicts that decline to name one confident cause; answering ``converged``
#: where one of these is expected is an overclaim, not merely a miss
NON_COMMITTAL = ("abstain", "ambiguous")

#: an explicit stage list no longer than this is a *bootstrap* plan — a state
#: reached deliberately before the plan's own end.  Two, not one, because the
#: state where a report speaks is an early rung and not always the first
BOOTSTRAP_MAX_STAGES = 2

#: paths always legitimate to free, whatever was planted: the background is
#: co-refined, never subtracted (CLAUDE.md Weights), and scale + background
#: is the mandatory first stage of every legitimate plan (AGENT_PROTOCOL §2)
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


def score_episode(episode_dir: Path, truth_file: Path) -> dict:
    """The per-episode scorecard, graded from the record alone."""
    truth = json.loads(truth_file.read_text(encoding="utf-8"))
    calls = _load_calls(episode_dir)
    ok_calls = [c for c in calls if not c.get("refused", False)
                and c["response"].get("ok", False)]
    answer, answer_problem = _answer(episode_dir)

    card = {
        "episode": truth["episode"],
        "condition": ok_calls[-1]["condition"] if ok_calls else None,
        "n_calls": len([c for c in calls if not c.get("refused", False)]),
        "n_refused": len([c for c in calls if c.get("refused", False)]),
        "n_failed_calls": len([c for c in calls
                               if not c.get("refused", False)
                               and not c["response"].get("ok", False)]),
        "verdict": answer.get("verdict") if answer else None,
        "expected_verdict": truth["expected_verdict"],
        "summary": answer.get("summary", "") if answer else "",
        "excluded_regions": [c["overlay"]["two_theta_limits"]
                             for c in ok_calls
                             if c["overlay"].get("two_theta_limits")],
        "notes": [],
    }
    if answer_problem:
        card["notes"].append(answer_problem)

    plans = [_plan_label(c["overlay"]) for c in calls
             if not c.get("refused", False)]
    card["plans_used"] = plans
    card["bootstrap_calls"] = sum(1 for label in plans if _is_bootstrap(label))

    verdict_ok = (answer is not None
                  and answer["verdict"] == truth["expected_verdict"])
    card["verdict_ok"] = verdict_ok
    card["overclaimed"] = bool(
        answer is not None
        and truth["expected_verdict"] in NON_COMMITTAL
        and answer["verdict"] == "converged")

    planted = truth.get("planted")
    card["planted_path"] = planted["path"] if planted else None
    card["recovered"] = None
    card["planted_final_value"] = None

    final = ok_calls[-1] if ok_calls else None
    if final is None:
        card["notes"].append("no successful refinement call")

    # what the graded call actually carried — the condition's own audit
    card["report_present"] = None
    card["trajectory_rungs"] = None
    card["statistics"] = None
    if final is not None:
        response = final["response"]
        card["report_present"] = "report" in response
        if isinstance(response.get("trajectory"), list):
            card["trajectory_rungs"] = len(response["trajectory"])
        stats = response["result"].get("statistics") or {}
        card["statistics"] = {k: stats[k] for k in ("rwp", "gof")
                              if k in stats}

    if planted and final is not None:
        rows = {p["path"]: p for p in final["response"]["result"]["parameters"]}
        row = rows.get(planted["path"])
        if row is not None:
            card["planted_final_value"] = row["value"]
        tol = planted.get("tol")
        if tol is not None:
            if row is None:
                # never freed => still the planted start (the shim fixes the
                # start; the surface omits fixed entries — see module docstring)
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
    if final is not None:
        freed: set[str] = set()
        for stage in final["response"]["result"]["stages"]:
            freed.update(stage["freed"])
        card["freed"] = sorted(freed)
        if family:
            legit = list(family) + list(ALWAYS_LEGIT)
            card["wrong_frees"] = sorted(
                p for p in freed if not _matches_any(p, legit))

    # truth-declared watch groups: which named set of paths the agent freed.
    # Data, not code — E3's report-path-vs-default-path inversion and R1's
    # cause-vs-absorber choice are the same question asked of two episodes
    card["watch"] = {}
    for name, globs in (truth.get("watch") or {}).items():
        card["watch"][name] = sorted(p for p in card["freed"]
                                     if _matches_any(p, globs))

    needs_recovery = bool(planted and planted.get("tol"))
    card["passed"] = bool(
        final is not None and verdict_ok
        and (card["recovered"] if needs_recovery else True))
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

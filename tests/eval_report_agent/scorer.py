"""Deterministic scorer for WP-1053 episodes.

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
- trap episodes (E5/E7/E8): pass iff the verdict matches
  (``impurity_suspected`` / ``abstain`` / ``ambiguous``);
- an episode with no successful call, or no ``answer.json``, fails —
  an answer with no refinement behind it scores zero;
- wrong-frees (recovery episodes only): stage-``freed`` paths outside the
  planted family + ``ALWAYS_LEGIT``, unioned over the answer call's stages.
  A descriptive localisation metric, never a pass/fail input — the lazy
  default plan solves E1/E4 while freeing plenty outside the family.

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

    verdict_ok = (answer is not None
                  and answer["verdict"] == truth["expected_verdict"])
    card["verdict_ok"] = verdict_ok

    planted = truth.get("planted")
    card["planted_path"] = planted["path"] if planted else None
    card["recovered"] = None
    card["planted_final_value"] = None

    final = ok_calls[-1] if ok_calls else None
    if final is None:
        card["notes"].append("no successful refinement call")

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

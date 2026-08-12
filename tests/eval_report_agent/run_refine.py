"""The agent's only sanctioned call path into ``refine_json`` (WP-1053).

The shim, not the prompt, enforces the condition — an agent can ignore a
prompt; it cannot un-strip a response:

- the request is always ``episode.json`` (fixed) plus ``overlay.json``
  restricted to ``plan`` / ``mode`` / ``two_theta_limits`` — the agent
  structurally cannot touch the pattern or the starting parameter values;
- ``include_report`` comes from ``condition.json``, never from the agent, and
  a report-off response additionally has any ``report`` stripped;
- every call is appended to ``calls.jsonl`` (the record the scorer and the
  call count come from, never the agent's self-report), with the bulk curve
  arrays elided — the fit is deterministic from episode + overlay, so the
  curves are reproducible, and what the agent saw is exactly what was logged;
- calls beyond ``max_calls`` are refused (a runaway guard, never a timer),
  and a refused call is logged but does not count against the budget.

Usage (from the repository root)::

    python -m tests.eval_report_agent.run_refine EPISODE_DIR
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ALLOWED_OVERLAY_KEYS = frozenset({"plan", "mode", "two_theta_limits"})

#: bulk per-point arrays elided from the logged/printed response; each is
#: replaced by its length so the elision is visible, never silent
_BULK_KEYS = ("two_theta", "y_obs", "y_calc", "y_background", "sigma")


def _refusal(code: str, message: str) -> dict:
    """Same envelope grammar as ``refine_json``'s failures, so the agent
    branches on ``ok``/``error.code`` either way."""
    return {"ok": False, "error": {"code": code, "message": message}}


def trim_response(response: dict) -> dict:
    """Elide bulk curve arrays from a response (in the ``result`` arm and any
    per-histogram slices); every parameter, statistic, diagnostic and the
    report survive intact."""
    trimmed = json.loads(json.dumps(response))  # deep copy, JSON types only
    result = trimmed.get("result")
    blocks = [result] if isinstance(result, dict) else []
    if isinstance(result, dict):
        blocks.extend(h for h in result.get("histograms", ())
                      if isinstance(h, dict))
    for block in blocks:
        for key in _BULK_KEYS:
            if isinstance(block.get(key), list):
                block[key] = {"elided_n_points": len(block[key])}
        if isinstance(block.get("ticks"), dict):
            block["ticks"] = {name: {"elided_n_ticks": len(pos)}
                              for name, pos in block["ticks"].items()}
        if isinstance(block.get("history"), list):
            block["history"] = {"elided_n_iterations": len(block["history"])}
    return trimmed


def _count_prior_calls(log_path: Path) -> int:
    """Non-refused calls already on the log — the budget counter."""
    if not log_path.exists():
        return 0
    n = 0
    with log_path.open(encoding="utf-8") as fh:
        for line in fh:
            if line.strip() and not json.loads(line).get("refused", False):
                n += 1
    return n


def run_episode(episode_dir: Path) -> dict:
    """One shim call: merge, enforce, run, log.  Returns what it printed."""
    episode_bytes = (episode_dir / "episode.json").read_bytes()
    condition = json.loads((episode_dir / "condition.json").read_text(encoding="utf-8"))
    log_path = episode_dir / "calls.jsonl"

    overlay_path = episode_dir / "overlay.json"
    overlay = {}
    refusal = None
    if overlay_path.exists():
        try:
            overlay = json.loads(overlay_path.read_text(encoding="utf-8"))
        except ValueError as exc:
            refusal = _refusal("OVERLAY_INVALID",
                               f"overlay.json is not valid JSON: {exc}")
            overlay = {"unparseable": True}
    if refusal is None and not isinstance(overlay, dict):
        refusal = _refusal("OVERLAY_INVALID", "overlay.json must be an object")
    if refusal is None:
        bad = sorted(set(overlay) - ALLOWED_OVERLAY_KEYS)
        if bad:
            refusal = _refusal(
                "OVERLAY_KEY_REFUSED",
                f"overlay key(s) {', '.join(bad)} refused; allowed: "
                f"{', '.join(sorted(ALLOWED_OVERLAY_KEYS))}")
    if refusal is None and _count_prior_calls(log_path) >= condition["max_calls"]:
        refusal = _refusal(
            "CALL_BUDGET_EXHAUSTED",
            f"the {condition['max_calls']}-call budget is spent; "
            "write answer.json")

    if refusal is not None:
        record = {"refused": True, "overlay": overlay, "response": refusal}
    else:
        request = json.loads(episode_bytes)
        request.update({k: overlay[k] for k in ALLOWED_OVERLAY_KEYS
                        if k in overlay})
        # the condition, never the agent, decides whether a report exists
        request["include_report"] = condition["include_report"]
        import anatase.agent as agent_mod

        response = agent_mod.refine_json(request)
        if not condition["include_report"]:
            # both halves of the report surface: the final report and the
            # per-stage trajectory (WP-1058).  The package already ties the
            # trajectory to include_report; this stays because the shim's
            # guarantee is that *the condition* decides, not a package default
            response.pop("report", None)
            response.pop("trajectory", None)
        record = {
            "refused": False,
            "episode_sha256": hashlib.sha256(episode_bytes).hexdigest(),
            "condition": condition["condition"],
            "include_report": condition["include_report"],
            "overlay": overlay,
            "response": trim_response(response),
        }

    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")
    return record["response"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("episode_dir", type=Path)
    args = parser.parse_args(argv)
    response = run_episode(args.episode_dir)
    json.dump(response, sys.stdout, indent=1)
    sys.stdout.write("\n")
    return 0 if response.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())

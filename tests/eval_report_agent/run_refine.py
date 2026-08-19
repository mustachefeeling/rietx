"""The agent's only sanctioned call path into ``refine_json`` (WP-1053).

The shim, not the prompt, enforces the condition — an agent can ignore a
prompt; it cannot un-strip a response:

- the request is always ``episode.json`` (fixed) plus ``overlay.json``
  restricted to ``plan`` / ``mode`` / ``two_theta_limits`` — the agent
  structurally cannot touch the pattern or the starting parameter values;
- ``include_report`` and ``include_trajectory`` come from the **sibling**
  condition marker (``<episode_dir>.condition.json`` — outside the
  workspace, PROTOCOL.md 2.0), never from the agent: they are set on the
  request (so the package never builds what this condition withholds) **and**
  popped from the response (so a package default can never leak one back in);
- the 2.2 projections come from the same marker (PROTOCOL.md 2.2):
  ``license_placement: "statistics"`` moves the identifiability clause from
  ``report.summary`` into ``result.statistics["identifiability_clause"]``
  (one renderer, byte-exact excision, loud failure), and
  ``include_execution: false`` pops WP-1106's ``execution`` from every
  delivered action — response *shape*, not withholding, and both inert when
  the report is withheld.  Since WP-1108 the *package* delivers the
  statistics field itself (``build_report``'s declared write), so on a real
  response the projection's injection half is a checked no-op — a shipped
  field disagreeing with the re-render fails the call — and the excision is
  what still constructs the round's *moved* shape (the package ships the
  copy).  A ``"summary"`` marker on a real response is therefore historical:
  it delivers 1.2's summary placement *plus* the shipped field, and a future
  round wanting a field-free arm must add a strip projection;
- every call is appended to ``calls.jsonl`` (the record the scorer and the
  call count come from, never the agent's self-report), with the bulk curve
  arrays elided — the fit is deterministic from episode + overlay, so the
  curves are reproducible, and what the agent saw is exactly what was logged.
  The log lives in the workspace, so it carries **no condition echo** — in
  1.1 each record repeated ``condition``/``include_report``/
  ``include_trajectory``, which was the same leak as the in-dir marker; the
  delivered response shape is itself the auditable evidence;
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


def _condition_path(episode_dir: Path) -> Path:
    """The sibling marker (``build_fixtures.condition_marker_path`` writes
    it): derived from the episode dir, never named in the prompt."""
    path = episode_dir.resolve()
    return path.parent / f"{path.name}.condition.json"


def _project_license_placement(response: dict) -> dict | None:
    """The 2.2 ``"statistics"`` placement (PROTOCOL.md 2.2): move the
    identifiability clause from ``report.summary`` into
    ``result.statistics["identifiability_clause"]`` — inside the block the
    miners proved agents grep.

    The clause is re-rendered from the *delivered* evidence by the package's
    own renderer — one authority for the sentence, so the excision target is
    the exact appended substring (``"; " + clause``, report/__init__.py) and
    never string surgery on prose.  A render/excise mismatch returns a
    refusal envelope: the registration invalidates the cell loudly, never a
    silent fallback.  Returns None on success (including the no-clause case,
    where there is nothing to move).

    Since WP-1108 shipped the placement, a real response already carries the
    field (``build_report`` writes the summary's clause to
    ``result.statistics.identifiability_clause`` in the same build), so the
    injection is a **checked no-op**: a shipped field that disagrees with
    the re-render is the same mismatch one surface over, refused by the same
    code.  What the projection still constructs is the round's *moved* shape
    — the package ships the copy, the arm delivered one copy in one
    location.  The equivalence with a real ``refine_json`` response is
    pinned from the package side by ``tests/test_fitreport_layers.py::
    test_refine_json_delivers_the_license_beside_the_numbers``.
    """
    from rietx.report import identifiability_clause
    from rietx.report.schemas import IdentifiabilityEvidence

    report = response.get("report")
    if not isinstance(report, dict):
        return None
    evidence = report.get("identifiability")
    clause = (identifiability_clause(
        IdentifiabilityEvidence.model_validate(evidence))
        if evidence is not None else None)
    if clause is None:
        return None
    needle = "; " + clause
    summary = report.get("summary", "")
    if needle not in summary:
        return _refusal(
            "PLACEMENT_PROJECTION_MISMATCH",
            "the rendered identifiability clause is not in report.summary; "
            "the cell is invalid (PROTOCOL.md 2.2)")
    shipped = response["result"]["statistics"].get("identifiability_clause")
    if shipped is not None and shipped != clause:
        return _refusal(
            "PLACEMENT_PROJECTION_MISMATCH",
            "the shipped statistics.identifiability_clause disagrees with "
            "the re-rendered clause; the cell is invalid (WP-1108)")
    report["summary"] = summary.replace(needle, "", 1)
    response["result"]["statistics"]["identifiability_clause"] = clause
    return None


def _strip_execution(response: dict) -> None:
    """The 2.2 ``include_execution: false`` projection: pop WP-1106's
    ``execution`` field from every delivered action.  The trajectory's rung
    actions are covered too — no 2.2 cell combines the arms, but the
    guarantee is the condition's, not the matrix's."""
    report = response.get("report")
    if isinstance(report, dict):
        for action in report.get("suggested_actions") or []:
            if isinstance(action, dict):
                action.pop("execution", None)
    for rung in response.get("trajectory") or []:
        if isinstance(rung, dict):
            for action in rung.get("actions") or []:
                if isinstance(action, dict):
                    action.pop("execution", None)


def run_episode(episode_dir: Path) -> dict:
    """One shim call: merge, enforce, run, log.  Returns what it printed."""
    episode_bytes = (episode_dir / "episode.json").read_bytes()
    condition = json.loads(
        _condition_path(episode_dir).read_text(encoding="utf-8"))
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
        # the condition, never the agent, decides which halves of the report
        # surface exist.  Every 2.0 marker carries both keys (the 1.0
        # single-switch compatibility read died with the relocation: an old
        # marker is in the wrong place to be read at all)
        include_report = condition["include_report"]
        include_trajectory = condition["include_trajectory"]
        request["include_report"] = include_report
        request["report_trajectory"] = include_trajectory
        import rietx.agent as agent_mod

        response = agent_mod.refine_json(request)
        # the 2.2 projections (PROTOCOL.md 2.2), applied before the pops so
        # they see the report; ``.get`` defaults are the pre-2.2 shape, so a
        # marker without the keys — an archived round's — means status quo
        if (include_report and response.get("ok")
                and condition.get("license_placement", "summary")
                == "statistics"):
            failure = _project_license_placement(response)
            if failure is not None:
                response = failure
        if include_report and not condition.get("include_execution", True):
            _strip_execution(response)
        # asked for on the request, popped again here: the shim's guarantee is
        # that *the condition* decides, not a package default that could move
        if not include_report:
            response.pop("report", None)
        if not include_trajectory:
            response.pop("trajectory", None)
        # no condition echo: the log lives in the workspace (module docstring)
        record = {
            "refused": False,
            "episode_sha256": hashlib.sha256(episode_bytes).hexdigest(),
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

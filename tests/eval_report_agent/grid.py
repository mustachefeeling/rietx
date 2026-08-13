"""Assemble a round's scorecards into the dated outcome grid (2.0).

One run directory per cell, named ``<condition>__<model>`` and holding one
subdirectory per episode; the truth tree is the one ``build_fixtures`` wrote.
For a JSON cell the condition is read from the episode's **sibling** marker
(``<eid>.condition.json``, outside the workspace — PROTOCOL.md 2.0) — the
authority — and only the model comes from the directory name.  A **python**
cell has no marker and no shim, so its condition is the cell name's own
prefix and the payload audit is N/A by design; a *JSON* cell whose marker is
missing is an invalid cell, not a python one.

Three rules from the protocol are enforced here rather than left to whoever
writes the summary:

- **two count tables, always**: the epistemic group (expected verdict is an
  epistemic outcome) and the solvable group (expected ``converged``) answer
  different questions, and pooling them is how round 1's null was misread;
- **counts, never percentages** (the indexing-scoreboard rule): at these N a
  percentage is a rounding of two runs into a claim;
- **a cell whose delivered payload disagrees with its condition is marked
  ``!``, not explained** — ``report_present``/``trajectory_rungs`` come off
  the graded call, so this catches a manipulation that silently failed.

Usage::

    python -m tests.eval_report_agent.grid RUNS_DIR TRUTH_DIR [--json]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from tests.eval_report_agent.build_fixtures import CONDITIONS
from tests.eval_report_agent.scorer import score_episode

#: the two group tables (PROTOCOL.md 2.0 § Reading the grid); every expected
#: verdict that is not ``converged`` is an epistemic outcome by construction
GROUPS = ("epistemic", "solvable")


def _group(card: dict) -> str:
    return "solvable" if card["expected_verdict"] == "converged" else "epistemic"


def _expected_payload(condition: str) -> tuple[bool, bool]:
    spec = CONDITIONS[condition]
    return spec.report, spec.trajectory


def collect(runs_dir: Path, truth_dir: Path) -> list[dict]:
    """Every episode dir under ``runs_dir``, scored.

    Each row is the scorecard plus ``cell``/``model``/``condition`` and the
    ``payload_ok`` audit (``None`` = N/A, the python arm).  A cell directory
    whose name carries no ``__`` is reported with ``model = "?"`` rather than
    skipped: a run that cannot be attributed is a finding, not a gap.
    """
    rows = []
    for cell_dir in sorted(p for p in runs_dir.iterdir() if p.is_dir()):
        prefix, _, model = cell_dir.name.partition("__")
        model = model or "?"
        for edir in sorted(p for p in cell_dir.iterdir() if p.is_dir()):
            truth_file = truth_dir / f"{edir.name}.json"
            if not truth_file.exists():
                continue
            card = score_episode(edir, truth_file)
            marker_path = edir.parent / f"{edir.name}.condition.json"
            if marker_path.exists():
                condition = json.loads(
                    marker_path.read_text(encoding="utf-8"))["condition"]
                want_report, want_trajectory = _expected_payload(condition)
                got_trajectory = (card["trajectory_rungs"] or 0) > 0
                payload_ok = (card["report_present"] is None
                              or (card["report_present"] == want_report
                                  and got_trajectory == want_trajectory))
            elif prefix == "python":
                # no shim, no marker: nothing whose delivery could disagree
                condition, payload_ok = "python", None
            else:
                # a JSON cell without its marker is a damaged record: the
                # payload cannot be audited, and unauditable is invalid
                condition, payload_ok = prefix, False
            card.update({
                "cell": cell_dir.name,
                "model": model,
                "condition": condition,
                "group": _group(card),
                "payload_ok": payload_ok,
            })
            rows.append(card)
    return rows


def _flags(card: dict) -> str:
    """The one-glance suffix on a cell: what happened beside the grade."""
    flags = []
    if card["payload_ok"] is False:
        flags.append("!")
    if card["overclaimed"]:
        flags.append("oc")
    if card["underclaimed"]:
        flags.append("uc")
    if card["next_action_ok"] is False:
        flags.append("na")
    if card["bootstrap_calls"]:
        flags.append(f"b{card['bootstrap_calls']}")
    return ("," + ",".join(flags)) if flags else ""


def _table(rows: list[dict]) -> list[str]:
    """One markdown count table: one row per (condition, model)."""
    episodes = sorted({r["episode"] for r in rows})
    cells = sorted({(r["condition"], r["model"]) for r in rows},
                   key=lambda cm: (list(CONDITIONS).index(cm[0])
                                   if cm[0] in CONDITIONS else 99, cm[1]))
    by_key = {(r["condition"], r["model"], r["episode"]): r for r in rows}

    out = ["| condition | model | " + " | ".join(episodes) + " | passed |",
           "|---|---|" + "---|" * (len(episodes) + 1)]
    for condition, model in cells:
        line, passed = [], 0
        for eid in episodes:
            card = by_key.get((condition, model, eid))
            if card is None:
                line.append("—")
                continue
            passed += bool(card["passed"])
            mark = "pass" if card["passed"] else (card["verdict"] or "no answer")
            line.append(f"{mark}{_flags(card)}")
        n = sum(1 for eid in episodes if (condition, model, eid) in by_key)
        out.append(f"| {condition} | {model} | " + " | ".join(line)
                   + f" | {passed}/{n} |")
    return out


def render(rows: list[dict]) -> str:
    """The two group tables, counts only — dated by whoever files them."""
    out = []
    for group in GROUPS:
        subset = [r for r in rows if r["group"] == group]
        if not subset:
            continue
        title = ("Epistemic rows — expected verdict is an epistemic outcome"
                 if group == "epistemic"
                 else "Solvable rows — expected `converged`")
        out += [f"## {title}", ""]
        out += _table(subset)
        out.append("")
    out.append("Flags: `!` delivered payload disagrees with the condition "
               "(or a JSON cell's marker is missing); `oc` overclaimed "
               "(converged where the data supports no single cause); `uc` "
               "underclaimed (non-committal on a solvable row); `na` "
               "next_action outside the registered set; `bN` N bootstrap "
               "calls.  A python cell's payload audit is N/A by design.")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("runs_dir", type=Path)
    parser.add_argument("truth_dir", type=Path)
    parser.add_argument("--json", action="store_true",
                        help="emit the scorecards instead of the tables")
    args = parser.parse_args(argv)
    rows = collect(args.runs_dir, args.truth_dir)
    if args.json:
        json.dump(rows, sys.stdout, indent=1)
        sys.stdout.write("\n")
    else:
        print(render(rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

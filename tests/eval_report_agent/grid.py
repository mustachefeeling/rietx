"""Assemble a round's scorecards into the dated outcome grid.

One run directory per cell, named ``<condition>__<model>`` and holding one
subdirectory per episode; the truth tree is the one ``build_fixtures`` wrote.
The condition is read from each episode's own ``condition.json`` — the
authority — and only the model comes from the directory name, because nothing
else in the record carries it.

Two rules from the WP are enforced here rather than left to whoever writes the
summary:

- **counts, never percentages** (the indexing-scoreboard rule): at these N a
  percentage is a rounding of two runs into a claim;
- **a cell whose delivered payload disagrees with its condition is marked
  ``!``, not explained.**  ``report_present``/``trajectory_rungs`` come off
  the graded call, so this catches a manipulation that silently failed —
  which is worth more than any outcome the cell would otherwise report.

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


def _expected_payload(condition: str) -> tuple[bool, bool]:
    spec = CONDITIONS[condition]
    return spec.report, spec.trajectory


def collect(runs_dir: Path, truth_dir: Path) -> list[dict]:
    """Every episode dir under ``runs_dir``, scored, newest layout first.

    Each row is the scorecard plus ``cell``/``model``/``condition`` and the
    ``payload_ok`` audit.  A cell directory whose name carries no ``__`` is
    reported with ``model = "?"`` rather than skipped: a run that cannot be
    attributed is a finding, not a gap.
    """
    rows = []
    for cell_dir in sorted(p for p in runs_dir.iterdir() if p.is_dir()):
        model = cell_dir.name.split("__", 1)[1] if "__" in cell_dir.name else "?"
        for edir in sorted(p for p in cell_dir.iterdir() if p.is_dir()):
            truth_file = truth_dir / f"{edir.name}.json"
            if not truth_file.exists():
                continue
            card = score_episode(edir, truth_file)
            marker = json.loads(
                (edir / "condition.json").read_text(encoding="utf-8"))
            condition = marker["condition"]
            want_report, want_trajectory = _expected_payload(condition)
            got_trajectory = (card["trajectory_rungs"] or 0) > 0
            card.update({
                "cell": cell_dir.name,
                "model": model,
                "condition": condition,
                "payload_ok": (card["report_present"] is None
                               or (card["report_present"] == want_report
                                   and got_trajectory == want_trajectory)),
            })
            rows.append(card)
    return rows


def _flags(card: dict) -> str:
    """The one-glance suffix on a cell: what happened beside the grade."""
    flags = []
    if not card["payload_ok"]:
        flags.append("!")
    if card["overclaimed"]:
        flags.append("oc")
    if card["bootstrap_calls"]:
        flags.append(f"b{card['bootstrap_calls']}")
    return ("," + ",".join(flags)) if flags else ""


def render(rows: list[dict]) -> str:
    """The markdown grid: one row per (condition, model), counts only."""
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

    out.append("")
    out.append("Flags: `!` delivered payload disagrees with the condition; "
               "`oc` overclaimed (converged where the data supports no single "
               "cause); `bN` N bootstrap calls (an explicit plan of at most "
               "two stages).")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("runs_dir", type=Path)
    parser.add_argument("truth_dir", type=Path)
    parser.add_argument("--json", action="store_true",
                        help="emit the scorecards instead of the table")
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

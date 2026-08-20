"""Score one agent-surface round from the shim's trace log (WP-1110).

Reads the JSONL `rietx_surface_trace` appends and answers the round's
pre-registered read-outs (PROTOCOL.md § Pre-registered read-outs):

  R1  did a `bare` run reach `agent.refine_json`?
  R2  did a `pointed` run drive the fit through it?
  R3  did a `mandated` run complete, and through what?

**Attribution is by process, not by directory.**  A subagent runs python from
wherever its shell happens to sit -- in the first minutes of round 1.0 that was
the session's own cwd, not the workspace -- and ``python -c`` leaves nothing but
``-c`` in ``sys.argv``, so cwd alone attributes almost nothing.  What does
attribute is the **data file**: every cell must read its own copy of
``d8_01612.raw``, so the first path argument the tracer sees names the
workspace.  So each pid is bound to a cell by the first path, cwd or argv
mentioning one, and every row from that pid inherits it.

A pid bound to two different cells is reported rather than resolved: the round
is short enough that pid reuse across cells is a defect to look at, not a case
to handle silently.

Run it as::

    python tests/eval_agent_surface/score_round.py TRACE.jsonl [CELL ...]
"""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict

CELLS = ("bare-1", "bare-2", "pointed-1", "pointed-2", "mandated-1", "mandated-2")

# the calls that answer the read-outs, in the order a report should read them
HEADLINE = ("agent.refine_json", "agent.tool_definition", "agent.request_schema",
            "agent.response_schema", "capabilities", "refine",
            "refine_sequential", "Refinement.fit", "SequentialRefinement.run")


def load(path: str) -> list[dict]:
    rows = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    rows.sort(key=lambda r: r.get("t", 0.0))
    return rows


def _hint(row: dict, cells) -> str | None:
    """The cell this single row names, from its path, cwd or argv."""
    haystacks = [row.get("path") or "", row.get("cwd") or ""]
    haystacks += [str(a) for a in row.get("argv", [])]
    for cell in cells:
        if any(cell in h for h in haystacks):
            return cell
    return None


def bind_pids(rows: list[dict], cells) -> tuple[dict[int, str], list[str]]:
    """pid -> cell, from the first row that names one, plus any conflicts."""
    bound: dict[int, str] = {}
    conflicts: list[str] = []
    for row in rows:
        cell = _hint(row, cells)
        if cell is None:
            continue
        pid = row.get("pid")
        if pid in bound and bound[pid] != cell:
            conflicts.append(f"pid {pid}: {bound[pid]} then {cell}")
        bound.setdefault(pid, cell)
    return bound, conflicts


def by_cell(rows: list[dict], cells=CELLS) -> dict[str, list[dict]]:
    bound, _ = bind_pids(rows, cells)
    out: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        out[bound.get(row.get("pid")) or _hint(row, cells) or ""].append(row)
    return out


def report(rows: list[dict], cells=CELLS) -> str:
    grouped = by_cell(rows, cells)
    _, conflicts = bind_pids(rows, cells)
    lines = []
    for cell in cells:
        entries = grouped.get(cell, [])
        calls = Counter(r["name"] for r in entries if r.get("event") == "call")
        starts = sum(1 for r in entries if r.get("event") == "import")
        if not entries:
            lines.append(f"{cell}: no traced interpreter attributed to this cell")
            continue
        reached = "yes" if calls.get("agent.refine_json") else "NO"
        lines.append(f"{cell}: {starts} traced starts, "
                     f"refine_json {reached} ({calls.get('agent.refine_json', 0)})")
        for name in HEADLINE:
            if calls.get(name):
                lines.append(f"    {name:<28} {calls[name]}")
        other = sorted(set(calls) - set(HEADLINE))
        if other:
            lines.append("    other: " + ", ".join(f"{n}×{calls[n]}" for n in other))
    stray = grouped.get("")
    if stray:
        names = Counter(r.get("name", r.get("event")) for r in stray)
        lines.append(f"\nunattributed: {len(stray)} rows from "
                     f"{len({r.get('pid') for r in stray})} pids "
                     f"-- {dict(names)}")
    if conflicts:
        lines.append("pid bound to more than one cell: " + "; ".join(conflicts))
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    cells = tuple(argv[2:]) or CELLS
    print(report(load(argv[1]), cells))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

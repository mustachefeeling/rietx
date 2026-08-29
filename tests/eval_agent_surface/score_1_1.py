"""Score round 1.1 from its runs, its traces and its transcripts.

    python tests/eval_agent_surface/score_1_1.py <root> [cell ...]

**This scores round 1.1 and nothing earlier.** `score_round.py` scores 1.0,
whose read-outs are about a surface WP-1303 deleted; the two share no cell and
no number. A later round declares its own read-outs and writes its own scorer,
and neither of these is edited afterwards (tests/CLAUDE.md § Two eval
protocols).

What it prints is the machine half of the pre-registered read-outs: R1 the
price, R2 the surfaces reached, R6 the condition's effect, R7 the scaffolding
ratio, R8 the per-process floor, R9 the build. R3, R4, R10 and R11 are scored
by hand from the transcripts, by declaration, and this file prints the counts
that go beside them rather than pretending to classify a closing paragraph.

**It refuses to divide two cells into a rate.** N = 2 per cell, and the two
runs differ by model, so a within-cell disagreement cannot be told from a model
difference; the protocol says every such row is reported as a disagreement with
both models named. The scorer therefore prints both numbers side by side and
never their ratio.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HARNESS = Path(__file__).resolve().parent
REPO = HARNESS.parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from tests.eval_agent_surface import runner, trail  # noqa: E402

# What the 2026-08-27 audit found invisible to the reader they were built for,
# and what WP-1301..1305 added.  R2 reads the two lists separately because they
# answer different questions: whether a surface is *findable*, and whether a
# *new* one is reached at all.  Both are the protocol's R2 sublists spelled as
# *traced targets*: the audit's "the history DAG" is `replay`/`branch`/
# `checkout`, and `CandidateGroup.delta_bic` is not an entry point, so what is
# observable of it is the `Refinement.suggest`/`Refinement.report` call that
# renders it.  `verify_discontinuities=True` is a value and is scored under
# DELIBERATE.  A CLI verb is not traceable as a name and is scored by hand.
INVISIBLE = ("capabilities", "help_for", "help_key_for", "help_registry",
             "Refinement.set_vary", "Refinement.branch", "Refinement.checkout",
             "replay")
ADDED = ("Refinement.summary", "SeriesResult.summary", "Refinement.suggest",
         "read_recipe", "Refinement.report")
# R11's three sub-rows are values, not names: the 2026-08-26 agent did all
# three by hand, so passing the keyword *is* the observation.
DELIBERATE = ("deliverable=series", "verify_discontinuities=True", "direction=both")


def read_cell(root: Path, cell: str) -> dict | None:
    p = runner.paths(root, cell)
    if not p["run"].is_file():
        return None
    record = json.loads(p["run"].read_text(encoding="utf-8"))
    result = record.get("result") or {}
    seen = trail.trace(trail.load(p["log"])) if p["log"].is_file() else trail.Trace()
    transcript = runner.transcript_for(root, cell)
    rows = trail.load(transcript) if transcript else []
    return {"cell": cell, "record": record, "result": result, "trace": seen,
            "transcript": transcript, "bill": trail.usage(rows),
            "calls": trail.tool_calls(rows)}


def _row(cell: dict) -> str:
    bill, seen = cell["bill"], cell["trace"]
    wall = bill.wall_seconds or 0.0
    cost = cell["result"].get("total_cost_usd")
    return (f"{cell['cell']:<20} {bill.api_calls:5d} "
            f"{bill.cache_read / 1e6:7.2f} {bill.mean_context / 1e3:6.0f} "
            f"{bill.output_tokens / 1e3:6.0f} {wall / 60:7.1f} "
            f"{seen.fit_seconds:7.1f} "
            f"{'' if cost is None else f'{cost:7.2f}'}")


def report(root: Path, cells: list[str]) -> str:
    found = [c for c in (read_cell(root, name) for name in cells) if c]
    if not found:
        return f"no runs under {root}"

    out = ["R1 — the price of an answer",
           f"{'cell':<20} {'calls':>5} {'cacheM':>7} {'ctx k':>6} {'out k':>6} "
           f"{'wall m':>7} {'fit s':>7} {'  $':>7}",
           *(_row(c) for c in found), ""]

    out.append("R2 — surfaces reached")
    for c in found:
        calls = c["trace"].calls
        invisible = [n for n in INVISIBLE if calls.get(n)]
        added = [n for n in ADDED if calls.get(n)]
        marks = {k for counter in c["trace"].kwargs.values() for k in counter}
        out.append(f"  {c['cell']:<20} invisible:   {', '.join(invisible) or 'none'}")
        out.append(f"  {'':<20} added:       {', '.join(added) or 'none'}")
        out.append(f"  {'':<20} deliberate:  "
                   f"{', '.join(m for m in DELIBERATE if m in marks) or 'none'}")
        if c["trace"].missing:
            out.append(f"  {'':<20} UNRESOLVED TARGETS: {sorted(c['trace'].missing)}")
    out.append("")

    out.append("R7/R8/R9 — scaffolding, floor, build")
    for c in found:
        seen, bash = c["trace"], sum(1 for k in c["calls"] if k.tool == "Bash")
        ratio = f"{bash / seen.fit_calls:.1f}" if seen.fit_calls else "no traced fit"
        floor = f"{seen.floor_share:.1%}" if seen.floor_share is not None else "?"
        log = runner.paths(root, c["cell"])["log"]
        rows = trail.load(log) if log.is_file() else []
        version = next((r.get("version") for r in rows
                        if r.get("event") == "import" and r.get("version")), "?")
        out.append(f"  {c['cell']:<20} {bash:3d} Bash / {seen.fit_calls} fits = {ratio}; "
                   f"floor {seen.import_seconds:.1f}s of {seen.process_wall:.1f}s ({floor}); "
                   f"build {version}")
    out.append("")

    out.append("R6 — the condition, per episode and model")
    for episode in runner.EPISODES:
        for model in runner.MODELS:
            pair = {c["cell"].split("-")[1]: c for c in found
                    if c["cell"].startswith(f"{episode}-") and c["cell"].endswith(f"-{model}")}
            if len(pair) < 2:
                continue
            bare, skill = pair["bare"], pair["skill"]
            out.append(f"  {episode}/{model}: calls {bare['bill'].api_calls} bare "
                       f"against {skill['bill'].api_calls} skill; "
                       f"wall {(bare['bill'].wall_seconds or 0) / 60:.1f} against "
                       f"{(skill['bill'].wall_seconds or 0) / 60:.1f} min; "
                       f"errors {sum(1 for k in bare['calls'] if k.error)} against "
                       f"{sum(1 for k in skill['calls'] if k.error)}")
    out += ["", "R3, R4, R10, R11 are scored by hand from the transcripts:",
            *(f"  {c['cell']:<20} {c['transcript'] or 'transcript not found'}" for c in found),
            "", "No rate is quoted from N = 2, and the two runs of a cell differ by "
            "model: a within-cell disagreement is reported as a disagreement, with "
            "both models named."]
    return "\n".join(out)


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    root = Path(argv[1]).resolve()
    cells = argv[2:] or [f"{e}-{c}-{m}" for e in runner.EPISODES
                         for c in runner.CONDITIONS for m in runner.MODELS]
    print(report(root, cells))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

"""Read `claude plugin eval` rounds into the read-outs PROTOCOL.md registers.

    python tests/eval_skill/readout.py show    RESULT.json [--build BUILD.json] [--json]
    python tests/eval_skill/readout.py compare CURRENT.json CANDIDATE.json [CURRENT.json CANDIDATE.json ...]

WP-1905; `PROTOCOL.md` § Read-outs and § The decision rule are what this
computes. `show` prints one round per case and arm: the comparable score of
each run and their mean, the pass rate, agent and judge cost, wall time, turns,
tokens per run, whether the skill fired, which reference files tool calls
named, and beside it the build's ``skill_sha256``/``tree_sha256``; leaks,
errors and void runs are listed under the table, never dropped. `compare` takes
rounds in (today's body, candidate) pairs on one model and applies the decision
rule to each pair: exit 0 when it holds, 1 when a case loses more than one
grader's worth, 2 when a pair cannot be decided (a partial round, two models,
N short of 3 after void or unscored runs, graders that differ).

**The score is recomputed, never read off the harness.** A two-arm run drops
every `tool_used: Skill` and `arm: with-only` grader from both arms, and
`--ablation none` drops nothing, so the harness scores one run state 1/7 in one
mode and 2/8 in the other (PROTOCOL.md § The score a comparison reads). Today's
body runs two-arm and a candidate runs one arm, so every run here is scored over
the graders a two-arm run keeps, whichever mode it ran in.

**Tokens, the route and leaks come from the kept trace** (``--keep-temp``), the
JSON carrying none of them. A run whose trace is gone reads `None` for each,
never zero or empty: an unread trace is not a run that read nothing. The bill
is summed by `trail.usage`, once per ``message.id``, whose docstring has why.

**The trace is read as a Claude Code transcript**, rows of ``{"type",
"message"}``, the shape the placement round's `read_out` reads; a bare
``{"role", "content"}`` message is lifted into it. The harness's own
``trace.jsonl`` was not read when this was written, so that is an assumption the
first round checks (PROTOCOL.md § Assumptions). `read_out` itself is not reused:
its module imports rietx and its leak test is one machine's checkout path.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from fractions import Fraction
from pathlib import Path, PurePosixPath

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from tests.eval_agent_surface import trail  # noqa: E402
from tests.eval_skill.build import STAMP  # noqa: E402

#: Runs per arm the decision rule reads (PROTOCOL.md § Models, N).
N = 3
#: Directories any run may name besides its own, the loaded skill's and the
#: interpreter's environment.
SYSTEM = tuple(PurePosixPath(p) for p in
               ("/usr", "/bin", "/sbin", "/lib", "/lib64", "/dev", "/proc", "/sys", "/etc"))
#: An absolute path of two or more parts; one part (`/tmp`) is not caught, and
#: a leading digit is refused so `x /2/3` in code is not a path.
ABSOLUTE = re.compile(r"(?<![\w.~$/-])/[A-Za-z_.@+-][\w.@+-]*(?:/[\w.@+-]*)+")
HOME = re.compile(r"(?<![\w$])~/[\w.@+/-]*")
#: A skill copy named by path: the checkout's, a package's, another install's.
COPY = re.compile(r"(?:^|/)(?:docs/skill|data/skill|skills)/rietx(?:/|$)|(?:^|/)SKILL\.md$")
RELATIVE_COPY = re.compile(
    r"(?<![\w./~-])(?:[\w.-]+/)*(?:docs/skill|data/skill|skills)/rietx(?:/[\w.@+-]*)*")
#: The package's own ways to a copy: the CLI verb and the function behind it.
SURFACE = re.compile(r"\brietx\s+skill\b|\bskill_path\b|\brietx\.skill\b")
REFERENCE = re.compile(r"references/([a-z0-9-]+\.md)")
BASE = re.compile(r"Base directory for this skill: (\S+)")
#: A `Skill` call loading rietx, bare or plugin-namespaced, read off its
#: JSON-encoded input: the harness documentation's pattern, and the
#: `input_match` every case's `Skill` grader carries, so a run's "fired" and its
#: grader count the same calls (another skill firing is neither).
FIRED = re.compile(r'"skill"\s*:\s*"(?:[\w-]+:)?rietx"')


def load(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


# --- the score ---------------------------------------------------------------

def _w(grader: dict) -> float:
    return grader.get("weight", 1)


def excluded(grader: dict) -> bool:
    """Whether a two-arm run drops this grader from both arms' scores (the
    harness's rule: https://code.claude.com/docs/en/plugin-evals, § Score
    against the no-plugin baseline)."""
    cfg = grader.get("config") or {}
    arm = cfg.get("arm", grader.get("arm"))
    if arm in ("both", "with-only"):
        return arm == "with-only"
    if grader.get("type") == "tool_used" and cfg.get("tool") == "Skill":
        return True
    return "mock_calls" in (cfg.get("target"), cfg.get("focus"))


def comparable(graders: list[dict]) -> list[dict]:
    """The graders a two-arm run scores; all of them where it would drop all."""
    kept = [g for g in graders if not excluded(g)]
    return kept or list(graders)


def tolerance(graders: list[dict]) -> float:
    """One grader's worth: the smallest comparable weight over their total."""
    kept = comparable(graders)
    return min(map(_w, kept)) / sum(map(_w, kept))


def run_score(run: dict, graders: list[dict]) -> float | None:
    """A run's score over the comparable graders; `None` where one is missing."""
    got = {r.get("name"): r for r in run.get("graders") or ()}
    kept = comparable(graders)
    if not kept or any(g["name"] not in got for g in kept):
        return None
    return sum(_w(g) for g in kept if got[g["name"]].get("passed")) / sum(map(_w, kept))


def tier0(graders: list[dict]) -> str | None:
    """``fire`` or ``quiet`` for a triggering case (one `Skill` grader, `arm:
    both`), else `None`."""
    if len(graders) != 1:
        return None
    g, cfg = graders[0], graders[0].get("config") or {}
    if g.get("type") != "tool_used" or cfg.get("tool") != "Skill" or cfg.get("arm") != "both":
        return None
    return "quiet" if cfg.get("max") == 0 else "fire"


# --- the trace ---------------------------------------------------------------

def _normalise(rows: list[dict]) -> list[dict]:
    out = []
    for i, row in enumerate(rows):
        if "message" not in row and row.get("role") in ("assistant", "user"):
            row = {"type": row["role"], "message": row}
        msg = row.get("message")
        if row.get("type") == "assistant" and isinstance(msg, dict) and not msg.get("id"):
            row = {**row, "message": {**msg, "id": f"row-{i}"}}
        out.append(row)
    return out


def _strings(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from _strings(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _strings(v)


def _uses(rows: list[dict]):
    for row in rows:
        content = (row.get("message") or {}).get("content") if row.get("type") == "assistant" else None
        for block in content if isinstance(content, list) else ():
            if isinstance(block, dict) and block.get("type") == "tool_use":
                yield block.get("name", "?"), block.get("input") or {}


def _under(path: PurePosixPath, roots) -> bool:
    return any(path.is_relative_to(r) for r in roots)


def _leaks(uses, inside, skill_roots, allowed) -> list[str]:
    out: list[str] = []
    for name, payload in uses:
        hits: list[str] = []
        for text in _strings(payload):
            hits += [m.group(0) for m in SURFACE.finditer(text)]
            hits += [m.group(0) for m in RELATIVE_COPY.finditer(text)]
            hits += [m.group(0) for m in HOME.finditer(text)]
            for raw in ABSOLUTE.findall(text):
                path = PurePosixPath(os.path.normpath(raw.rstrip(".")))
                if _under(path, skill_roots):
                    continue
                if COPY.search(str(path)) or not _under(path, [*inside, *allowed]):
                    hits.append(str(path))
        out += [f"{name}: {h}" for h in dict.fromkeys(hits)]
    return out


def trace_facts(path: str | None, *, arm: str, plugin: str | None = None,
                python: str | None = None) -> dict:
    """Tokens, the route, leaks and whether the condition held, off one trace."""
    facts = dict.fromkeys(("tokens", "output_tokens", "fired", "opened",
                           "skill_dir", "leaks", "held"))
    if not path or not Path(path).is_file():
        return {**facts, "trace": "missing"}
    rows = _normalise(trail.load(path))
    if not any(r.get("type") == "assistant" for r in rows):
        return {**facts, "trace": "unread"}
    bill = trail.usage(rows)
    uses = list(_uses(rows))
    # rietx's base directory, never the first skill's: another skill loaded
    # first would otherwise void the run for a condition it says nothing about.
    base = next((b for r in rows for s in _strings(r) for m in BASE.finditer(s)
                 for b in [m.group(1).rstrip(".")] if PurePosixPath(b).name == "rietx"), None)
    run_dir = PurePosixPath(path).parent.parent  # <run>/out/trace.jsonl
    inside = [run_dir, *(PurePosixPath(r["cwd"]) for r in rows
                         if r.get("type") == "system" and isinstance(r.get("cwd"), str))]
    skill_roots = []
    if arm == "with":
        skill_roots = [PurePosixPath(p) for p in
                       (base, plugin and f"{plugin}/skills/rietx") if p]
    allowed = list(SYSTEM)
    if python and len(PurePosixPath(python).parents) > 2:
        allowed.append(PurePosixPath(python).parents[1])
    fired = any(n == "Skill" and FIRED.search(json.dumps(i)) for n, i in uses)
    if arm == "with":
        homes = [run_dir, *([PurePosixPath(plugin)] if plugin else [])]
        held = None if base is None else _under(PurePosixPath(base), homes)
    else:
        held = not fired
    return {"trace": "read",
            "tokens": bill.input_tokens + bill.cache_read + bill.cache_write + bill.output_tokens,
            "output_tokens": bill.output_tokens, "fired": fired,
            "opened": sorted({m for _, i in uses for s in _strings(i) for m in REFERENCE.findall(s)}),
            "skill_dir": base, "leaks": _leaks(uses, inside, skill_roots, allowed), "held": held}


# --- one round ---------------------------------------------------------------

def summarise(doc: dict, build: dict | None = None) -> dict:
    """Every read-out of one result document, per case, arm and run."""
    suite = doc.get("suite") or {}
    root = suite.get("root")
    if build is None and root and (Path(root) / STAMP).is_file():
        build = load(Path(root) / STAMP)
    python = (build or {}).get("python")
    threshold = suite.get("threshold", 1)
    cases = []
    for case in doc.get("cases") or ():
        graders = case.get("graders") or []
        arms = {}
        for arm, runs in (case.get("arms") or {}).items():
            arms[arm] = []
            for run in runs:
                score = run_score(run, graders)
                arms[arm].append({
                    "score": score, "harness_score": run.get("score"),
                    "passed": None if score is None else score >= threshold,
                    "cost": run.get("costUsd"), "judge_cost": run.get("judgeCostUsd"),
                    "seconds": run.get("durationSeconds"), "turns": run.get("turns"),
                    "error": run.get("error"), "skipped_paid": bool(run.get("skippedPaidGraders")),
                    "trace_path": run.get("tracePath"),
                    **trace_facts(run.get("tracePath"), arm=arm, plugin=root, python=python)})
        cases.append({"name": case.get("name"), "tier0": tier0(graders),
                      "comparable": {g["name"]: _w(g) for g in comparable(graders)},
                      "tolerance": tolerance(graders) if graders else None, "arms": arms})
    keep = ("skill_sha256", "tree_sha256", "tree", "body", "python", "commit")
    return {"model": suite.get("modelOverride"), "judge": suite.get("judgeModel"),
            "ablation": suite.get("ablation"), "concurrency": suite.get("concurrency"),
            "threshold": threshold, "claude": doc.get("claudeVersion"),
            "partial": bool(doc.get("partial")), "partial_reason": doc.get("partialReason"),
            "cost": doc.get("costUsd"), "seconds": doc.get("durationSeconds"), "root": root,
            "build": {k: build.get(k) for k in keep} if build else None, "cases": cases}


def _mean(values) -> float | None:
    got = [v for v in values if v is not None]
    return sum(got) / len(got) if got else None


def tier0_rates(summary: dict) -> dict[str, tuple[int, int]]:
    """Fire rate over the should-fire prompts and quiet rate over the rest, as
    (runs whose `Skill` grader passed, runs)."""
    rates: dict[str, tuple[int, int]] = {}
    for case in summary["cases"]:
        if case["tier0"]:
            runs = case["arms"].get("with") or []
            hit, n = rates.get(case["tier0"], (0, 0))
            rates[case["tier0"]] = (hit + sum(r["score"] == 1 for r in runs), n + len(runs))
    return rates


def _f(x, spec: str = ".2f") -> str:
    return "?" if x is None else format(x, spec)


def _k(x) -> str:
    return "?" if x is None else f"{x / 1000:.0f}k"


def _count(runs, key) -> str:
    seen = [r[key] for r in runs if r[key] is not None]
    return f"{sum(map(bool, seen))}/{len(runs)}" if seen else "?"


def _notes(where: str, arm: str, run: dict, two_arm: bool) -> list[str]:
    """What a run's row cannot hold: reported under the table, never dropped."""
    out = [f"LEAK {where}: {leak}" for leak in run["leaks"] or ()]
    mine, theirs = run["score"], run["harness_score"]
    if two_arm and None not in (mine, theirs) and abs(mine - theirs) > 1e-9:
        # Equal by construction where both arms ran (PROTOCOL.md § Assumptions, 5).
        out.append(f"SCORE {where}: comparable {mine:.3f} against the harness's {theirs:.3f}")
    if run["error"]:
        out.append(f"ERROR {where}: {run['error']}")
    if run["held"] is False:
        out.append(f"VOID {where}: " + (f"skill loaded from {run['skill_dir']}" if arm == "with"
                                        else "a skill fired in the without arm"))
    if run["skipped_paid"]:
        out.append(f"SKIPPED-JUDGE {where}: the cost ceiling skipped its judge graders")
    if run["trace"] != "read":
        out.append(f"TRACE {where}: {run['trace']} ({run['trace_path']})")
    return out


def render(summary: dict, name: str) -> str:
    b = summary["build"]
    head = (f"{name}: claude {summary['claude']}, model {summary['model']}, judge "
            f"{summary['judge']}, ablation {summary['ablation']}, -j {summary['concurrency']}, "
            f"${_f(summary['cost'])}, {summary['seconds']} s")
    if summary["partial"]:
        head += f", PARTIAL ({summary['partial_reason']})"
    lines = [head, f"build: SKILL.md {b['skill_sha256'][:12]}, tree {b['tree_sha256'][:12]}, "
                   f"python {b['python']}" if b else
             "build: no build.json beside the result's plugin (pass --build)",
             f"{'case':26s} {'arm':7s} n  score per run           pass  $/run judge "
             "s/run turns  tok/run  out  fired refs"]
    notes = []
    for case in summary["cases"]:
        for arm, runs in case["arms"].items():
            turns = [r["turns"] for r in runs if r["turns"] is not None]
            opened = [r["opened"] for r in runs if r["opened"] is not None]
            refs = ",".join(sorted(set().union(*opened))) or "-" if opened else "?"
            lines.append(
                f"{case['name']:26s} {arm:7s} {len(runs)}  {_f(_mean(r['score'] for r in runs))} "
                f"{','.join(_f(r['score']) for r in runs):17s} "
                f"{_count(runs, 'passed'):5s} {_f(_mean(r['cost'] for r in runs), '.3f')} "
                f"{_f(_mean(r['judge_cost'] for r in runs), '.3f')} "
                f"{_f(_mean(r['seconds'] for r in runs), '5.0f')} "
                f"{f'{min(turns)}-{max(turns)}' if turns else '?':5s} "
                f"{_k(_mean(r['tokens'] for r in runs)):>7s} "
                f"{_k(_mean(r['output_tokens'] for r in runs)):>4s}  "
                f"{_count(runs, 'fired'):5s} {refs}")
            for i, r in enumerate(runs, 1):
                notes += _notes(f"{case['name']} {arm} run {i}", arm, r,
                                summary["ablation"] == "with-without")
    rates = tier0_rates(summary)
    if rates:
        lines.append("tier 0: " + ", ".join(
            f"{k} rate {hit}/{n}" for k, (hit, n) in sorted(rates.items())))
    return "\n".join(lines + notes)


# --- the decision rule -------------------------------------------------------

def compare(current: dict, candidate: dict) -> dict:
    """PROTOCOL.md § The decision rule on two `summarise` outputs of one model."""
    problems = [f"{k}: {current[k]} against {candidate[k]}" for k in ("model", "judge")
                if current[k] != candidate[k]]
    problems += [f"{side} round is partial ({s['partial_reason']})"
                 for side, s in (("current", current), ("candidate", candidate)) if s["partial"]]
    builds = current["build"], candidate["build"]
    notes = ["A/A: both rounds ran one tree"] if all(builds) and builds[0]["tree_sha256"] \
        and builds[0]["tree_sha256"] == builds[1]["tree_sha256"] else []
    if current.get("root") and current.get("root") == candidate.get("root"):
        # PROTOCOL.md § The conditions: one <out> per condition.
        notes.append(f"both rounds name one plugin directory, {current['root']}: its "
                     f"{STAMP} is the later build's, so the hashes cannot tell them apart")
    old = {c["name"]: c for c in current["cases"]}
    problems += [f"{n}: not in the candidate round" for n in
                 sorted(set(old) - {c["name"] for c in candidate["cases"]})]
    rows = []
    for case in candidate["cases"]:
        before = old.get(case["name"])
        if before is None:
            problems.append(f"{case['name']}: not in the current round")
            continue
        why = [] if before["comparable"] == case["comparable"] else ["graders differ"]
        usable = {}
        for side, c in (("current", before), ("candidate", case)):
            usable[side] = [r for r in c["arms"].get("with") or ()
                            if r["score"] is not None and not r["skipped_paid"] and r["held"] is not False]
            if len(usable[side]) < N:
                why.append(f"{side} N = {len(usable[side])} of {N}")
        a, b = _mean(r["score"] for r in usable["current"]), _mean(r["score"] for r in usable["candidate"])
        delta = None if a is None or b is None else b - a
        tol = case["tolerance"]
        loses = delta is not None and delta < -tol - 1e-12
        without = _mean(r["score"] for r in before["arms"].get("without") or ())
        cand_runs = case["arms"].get("with") or []
        rows.append({
            "case": case["name"], "tolerance": tol, "current": a, "candidate": b, "delta": delta,
            "vs_none": None if b is None or without is None else b - without,
            "tokens": (_mean(r["tokens"] for r in before["arms"].get("with") or ()),
                       _mean(r["tokens"] for r in cand_runs)),
            "cost": (_mean(r["cost"] for r in before["arms"].get("with") or ()),
                     _mean(r["cost"] for r in cand_runs)),
            "loses": loses, "why": why,
            "suspect_judge": delta is not None and delta < 0 and bool(cand_runs)
            and all(r["fired"] for r in cand_runs)})
    # A pair the rule cannot read (two models, a partial round, a missing case)
    # decides nothing, a loss inside it included: rule 3 makes it undecided.
    if problems:
        verdict = "undecided"
    elif any(r["loses"] and not r["why"] for r in rows):
        verdict = "fails"
    elif any(r["why"] for r in rows):
        verdict = "undecided"
    else:
        verdict = "holds"
    return {"model": candidate["model"], "builds": builds, "rows": rows,
            "problems": problems, "notes": notes, "verdict": verdict}


def render_compare(out: dict, current: str, candidate: str) -> str:
    def sha(b):
        return f"SKILL.md {b['skill_sha256'][:12]} tree {b['tree_sha256'][:12]}" if b else "no build.json"

    lines = [f"{out['model']}: {current} ({sha(out['builds'][0])}) -> {candidate} "
             f"({sha(out['builds'][1])})",
             f"{'case':26s}  t      cur   cand      Δ  vs none  tok/run cur -> cand  $/run cur -> cand"]
    for r in out["rows"]:
        t = Fraction(r["tolerance"]).limit_denominator(100) if r["tolerance"] else "?"
        flag = ("LOSES" if r["loses"] else "") + ("  suspect the judge" if r["suspect_judge"] else "")
        lines.append(
            f"{r['case']:26s} {str(t):5s} {_f(r['current'])}  {_f(r['candidate'])} "
            f"{_f(r['delta'], '+.2f'):>6s} {_f(r['vs_none'], '+.2f'):>8s} "
            f"{_k(r['tokens'][0]):>7s} -> {_k(r['tokens'][1]):7s} "
            f"{_f(r['cost'][0], '.3f')} -> {_f(r['cost'][1], '.3f')}  {flag}".rstrip()
            + (f"  [{'; '.join(r['why'])}]" if r["why"] else ""))
    lines += [f"note: {n}" for n in out["notes"]] + [f"problem: {p}" for p in out["problems"]]
    lost = [r["case"] for r in out["rows"] if r["loses"] and not r["why"]]
    lines.append(f"rule: {out['verdict']}" + (f" ({', '.join(lost)})" if lost else ""))
    return "\n".join(lines)


EXIT = {"holds": 0, "fails": 1, "undecided": 2}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="verb", required=True)
    show = sub.add_parser("show", help="one round's read-outs")
    show.add_argument("result", type=Path, help="aggregate-result.json, or --json's file")
    show.add_argument("--build", type=Path, help="build.json, if not beside the plugin")
    show.add_argument("--json", action="store_true", help="print every read-out as JSON")
    pair = sub.add_parser("compare", help="the decision rule, per (current, candidate) pair")
    pair.add_argument("results", type=Path, nargs="+")
    args = ap.parse_args(argv)
    if args.verb == "show":
        summary = summarise(load(args.result), load(args.build) if args.build else None)
        print(json.dumps(summary, indent=1) if args.json else render(summary, args.result.name))
        return 0
    if len(args.results) % 2:
        ap.error("compare takes CURRENT CANDIDATE pairs")
    verdicts = []
    for cur, cand in zip(args.results[::2], args.results[1::2]):
        out = compare(summarise(load(cur)), summarise(load(cand)))
        print(render_compare(out, cur.name, cand.name))
        verdicts.append(out["verdict"])
    return next((EXIT[v] for v in ("fails", "undecided") if v in verdicts), 0)


if __name__ == "__main__":
    sys.exit(main())

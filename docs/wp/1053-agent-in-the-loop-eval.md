# WP-1053 — Agent-in-the-loop FitReport eval (refine_json only)

Milestone: v1.0 · Status: ⬜
Depends on: WP-1052

## Goal

A scored, repeatable protocol that measures whether the FitReport helps a **real LLM
agent** converge a refinement through the shipped `agent.refine_json` surface:
episode fixtures + a condition-enforcing shim + a deterministic scorer in
`tests/eval_report_agent/`, plus a first dated pilot grid ({report on, off} ×
2 models × 8 episodes) recorded in this file's handover log and the v1.0 appendix.
The package gains no LLM dependency; the runs happen in the Claude Code harness.

## Context

**Question.** WP-1052 measures the report's *advice quality* with a mechanical
driver. This WP measures the report's *marginal value to an agent*: same episodes,
real models, with the FitReport attached or stripped. A falsifiable side hypothesis
comes free: if the report's value is real, it should lift the weaker model/effort
conditions most.

**Interface facts, verified 2026-08-04.** `RefineRequest` (`agent.py:160-174`) =
task / structure / instrument / **inline `PatternData`** / mode / two_theta_limits /
history_path / `include_report` (default True); `_RequestBase.plan: str | PlanSpec`
**defaults to `"mccusker_default"`** (`agent.py:126`). Two consequences:

1. Fixtures are **request JSON** (pydantic round-trips by design), not pattern
   files — the agent never parses data formats.
2. The lazy path — submit the request untouched — already runs the full default
   preset, which fixes E1/E3/E4/E6 without reading anything. **The report-on/off A/B
   therefore discriminates on E2 (displacement — in no default-plan stage) + the
   traps E5/E7/E8; E1/E4 are competence controls.** State this in every summary of
   the grid, or a null result on the easy rows will be misread as "the report
   doesn't help".

**Episode mechanics — overlay + logging shim.** Episodes are WP-1052's eight
planted-cause starts (built from `tests/test_fitreport_layers.py::_truth()`).
`build_fixtures.py` writes episode dirs **to a runner-chosen directory at eval
time** — nothing generated is committed, so fixtures stay in lockstep with
`_truth()`. Each dir holds `episode.json` (the fixed request core: task, structure,
instrument, pattern) and `prompt.md`. **Ground truth lives in a separate scorer-side
tree the agent is never pointed at.**

The agent's only sanctioned call path is a thin shim, `run_refine.py`: it merges the
agent's `overlay.json` — **`plan` / `mode` / `two_theta_limits` only** — onto
`episode.json`, calls `refine_json`, appends request+response to `calls.jsonl`, and
returns the response. The shim, not the prompt, **enforces the condition**:

- report-off runs force `include_report=False` and strip any report from the
  response;
- the agent structurally cannot touch the pattern or the starting parameter values
  (no hand-editing the planted cause away — comparability is enforced, not asked
  for);
- the call trace and count come from `calls.jsonl`, never from the agent's
  self-report.

Iteration is **on the plan, not the state**: every call runs from the same fixed
perturbed start; the report from call N informs the plan overlay for call N+1. This
matches `refine_json`'s statelessness and needs no warm-start support. (Excluding a
contaminated region via `two_theta_limits` is legitimate practice and stays allowed;
the scorer records it.)

**Scoring** (`scorer.py`, graded from `calls.jsonl` + a mandated `answer.json` with
`verdict ∈ converged | impurity_suspected | abstain | ambiguous`):

- Recovery episodes **E1–E4 and E6**: planted parameter at truth within the WP-1052
  tolerances. E6 differs from the mechanical loop on purpose — a 0.4 % cell error is
  a trap only for the *gated* driver; a competent agent legitimately frees the cell
  and converges.
- E5 → `impurity_suspected` (must not silently fit through the spike);
  E7 → `abstain`; E8 → `ambiguous` (must not name one confident cause between zero
  and displacement — the window makes them collinear, and freeing both just lands
  somewhere on the degenerate ridge).
- Plus: wrong-frees (per-stage `freed` paths outside the true family — `StageResult.
  freed` exists, `refine.py:786`) and call count.
- `test_scorer.py` unit-tests the scorer deterministically (fast suite, no network).

**Runner protocol** (`PROTOCOL.md`, versioned): one shared prompt, no per-model
tuning. Report-on runs include AGENT_PROTOCOL §5/§6 excerpts — the manual ships with
the feature; report-off runs get neither. Runs execute in the Claude Code harness
(the Workflow `agent()` call takes per-run `model` and `effort`). **Pilot framing**:
{report on, off} × 2 models × 8 episodes, N=2 repeats on the discriminating rows
(E2, E5, E7, E8) — ~40 runs, each 2–6 shim calls, roughly 1–2 h wall parallelized.
Results are a **dated raw outcome grid** (counts, never percentages from tiny N,
never rounded up — the indexing-scoreboard rule) in this handover + the v1.0
appendix. It is a pilot establishing protocol soundness and effect direction, not a
benchmark, and never a CI assertion — outcomes move with the models. Effort as a
second pass once the matrix runs clean.

**Packaging**: `tests/eval_report_agent/` — the `from tests.<module> import …`
pattern is house practice (`test_report_apply.py`), and ruff already covers
`tests/`. pytest collects only `test_scorer.py` there.

## Non-goals

- No LLM/API dependency in the package — no `anthropic` import, no judge, no
  transcript parser in `src/` or `tests/`.
- No CI assertion on agent outcomes; the deterministic scorer's own unit tests are
  the only collected tests.
- No MCP server (v2 fence) and no per-model prompt tuning.
- No full-Python-interface condition (an agent working like a dev session) —
  deliberately deferred; it answers a different question from the shipped surface.
- No significance claims from the pilot.

## Tasks

- [ ] Verify what `AgentSuccess` serialises (refined parameter values, per-stage
      `freed`) — near-certain from `_build_result(model, table, outcome.theta …)`
      (`refine.py:795`); a gap is a *finding about the surface* and gets recorded,
      not silently worked around.
- [ ] `tests/eval_report_agent/build_fixtures.py`: episode dirs (episode.json +
      prompt.md) written to a runner-chosen directory; scorer-side truth tree
      written separately; nothing generated committed.
- [ ] `run_refine.py` shim: overlay merge (plan/mode/limits only), condition
      enforcement (report-off forces + strips), `calls.jsonl` logging.
- [ ] `scorer.py` + the `answer.json` schema + `test_scorer.py` (deterministic,
      fast suite).
- [ ] `PROTOCOL.md`: the shared versioned prompt, §5/§6 excerpt policy, condition
      matrix, runner instructions (Workflow `agent()` with per-run model/effort),
      audit note (spot-check transcripts; the shim log is the record).
- [ ] Run the pilot matrix; record the dated raw grid (model IDs, efforts, per-
      episode scorecards) in this handover log and the v1.0 appendix, with the
      discriminating-rows caveat attached.

## Acceptance

```sh
.venv/bin/python -m pytest tests/eval_report_agent/test_scorer.py
.venv/bin/python -m ruff check src tests examples
grep -ri "anthropic\|openai" src tests --include="*.py"   # no hits
```

The dated pilot grid is present in the handover with model IDs and per-episode
scorecards; the scorer's unit tests pass; the repo carries no LLM dependency.

## References

- `docs/AGENT_PROTOCOL.md` §5 (numbers, not pixels), §6 (abstention is a result),
  §9 (the canonical loop).
- `docs/DESIGN.md` — the report-instead-of-plot-reading rationale this eval tests.
- `docs/wp/1052-report-loop-eval.md` — episodes, tolerances, families, and the
  mechanical floor this compares against.

## Handover log

- **2026-08-05** — created; not started, and blocked on WP-1052 only for the
  episode tolerances/families (the fixtures themselves come from `_truth()`
  directly). Interface facts in Context were verified against `agent.py`, not
  assumed. Next: the `AgentSuccess` payload verification task — do it first, the
  scorer's design rests on it. Gotchas: conditions are enforced by the shim, not
  the prompt (an agent can ignore a prompt; it cannot un-strip a response), and
  every summary of the pilot grid must carry the discriminating-rows caveat — the
  default plan alone solves E1/E3/E4/E6, so a flat "report didn't help" reading
  of those rows is the misread this WP exists to prevent.

# WP-1053 — Agent-in-the-loop FitReport eval (refine_json only)

Milestone: v1.0 · Status: ✅ 2026-08-11 — protocol + scorer shipped (17 fast tests), 48/48-run pilot grid recorded here and in the v1.0 appendix; outcomes move with models, so the grid is a dated record, never a CI assertion
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

**`AgentSuccess` payload, verified 2026-08-11.** `StageResult.freed` is real and
populated at both construction sites (`refine.py:906`, `:966`), and each
`RefinedParameter` row carries `path`/`value`/`stderr`/`vary`. The gap:
`_build_result` serialises **only `vary or tie` entries** (`refine.py:1397-1398`)
— a *fixed* parameter is absent from `result.parameters`, not present at its held
value, and `initial` is never populated by that path. Consequence for the scorer,
deterministic because the shim fixes the start: a planted path absent from every
call's `parameters` was never freed, so its final value *is* the planted start —
score not-recovered from absence, never by re-reading a value the surface does
not carry. Recorded as a surface finding per this WP's first task; no src/
change made.

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

**Measured by [WP-1052](1052-report-loop-eval.md) (closed 2026-08-11) — four
findings that bind the scorer** (folded from Inherited on arrival, same day;
none stale). The driver and all eight episodes live in
`tests/test_report_loop.py` (plus two slow real-data SRM 660c rows); every
number below is pinned there.

1. **E6 is a sharper trap than this WP's Context assumes.** After the
   background bootstrap the wrong-cell state *abstains* (Rwp 0.716), and an
   abstained report never emits `reindex_or_recheck_cell` (mature-branch-only
   emitter) — what the report actually serves is **`add_impurity_phase` at
   confidence 0.9**, with indexing mentioned only in that action's rationale
   and `alternatives`. A real agent following the report on E6 is being
   invited to add a phantom phase; score what it does with that invitation,
   and do not treat "agent proposed an impurity" as a scorer surprise.
2. **E8 has a legitimate-looking wrong turn built in**: the axial-divergence
   term (fixed confidence 0.5, a different observable, invisible to the
   position collinearity cap) absorbs ~70 % of χ² on the short window and
   *survives verification*. An agent that takes it sees a large real
   improvement; the scorer must count recovery by the planted parameter,
   never by Δχ² — the mechanical loop's line ("no position kind applied")
   is the scoreable one.
3. **E3 can invert the report-on/off sign.** The report's width emitters name
   only `lor_size`/`lor_strain`, whose proxy plateaus at χ²_red ≈ 4.3, while
   the lazy default-plan path frees `w` itself and reaches the ≈1.01 floor —
   so on E3, *following the report* can lose to *ignoring it*. State this
   beside the A/B table or the E3 row will be misread.
4. **Synthetic calibration does not transfer wholesale to real data**: on
   SRM 660c a planted 0.01° zero comes back with the whole position family
   capped ≤ 0.3 (genuinely non-separable from the fitted displacement) and
   `add_impurity_phase` outranking it — refusal is the *correct* report
   behaviour there and must be scored as such, not as a miss.

Also measured there: the predicted/observed Δχ² band measured 0.79–1.42 across
first accepted actions (pinned 0.3–3×), and the 1 % keep-threshold never
rejected a true first-round cause — the report-calibration failure mode
WP-1052 was told to record did not occur.

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

- [x] Verify what `AgentSuccess` serialises (refined parameter values, per-stage
      `freed`) — done 2026-08-11; the vary-or-tie-only gap and its scorer rule
      are in Context (§ `AgentSuccess` payload).
- [x] `tests/eval_report_agent/build_fixtures.py`: episode dirs (episode.json +
      prompt.md) written to a runner-chosen directory; scorer-side truth tree
      written separately; nothing generated committed.
- [x] `run_refine.py` shim: overlay merge (plan/mode/limits only), condition
      enforcement (report-off forces + strips), `calls.jsonl` logging.
- [x] `scorer.py` + the `answer.json` schema + `test_scorer.py` (deterministic,
      fast suite).
- [x] `PROTOCOL.md`: the shared versioned prompt, §5/§6 excerpt policy, condition
      matrix, runner instructions (Workflow `agent()` with per-run model/effort),
      audit note (spot-check transcripts; the shim log is the record).
- [x] Run the pilot matrix; record the dated raw grid (model IDs, efforts, per-
      episode scorecards) in this handover log and the v1.0 appendix, with the
      discriminating-rows caveat attached — done 2026-08-11, 48/48 runs.

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

- **2026-08-11 (close)** — **Done**: all six checklist items, one commit each
  (`9f5cf40`…`e7e67c4`): the `AgentSuccess` verification (gap in Context),
  `tests/eval_report_agent/` (fixtures builder, shim, scorer + 17
  deterministic tests, PROTOCOL.md v1.0), and the 48/48-run pilot below.
  Acceptance green: scorer tests pass, ruff clean, `grep -ri
  "anthropic\|openai" src tests` empty. Fast suite measured **2273 passed +
  5 skipped** (`[dev]` venv, darwin/arm64, ~3:36–3:50) — this session's 17
  tests are all fast-suite passes, no new skips; the full selection was not
  run this session (none of the 17 is slow-marked, so it inherits the same
  +17 — the next weekly log verifies). **In flight**: nothing. **Next**:
  nothing on this WP; the one queued follow-up idea — a §9-excerpt prompt
  condition — is a protocol-v1.1 *experiment for a future decision*, noted
  in finding 1, deliberately not a task. **Gotchas**: fixtures are built
  fresh per run (`build_fixtures --episodes RUN_DIR --truth TRUTH_DIR
  --only E{n}`) — an episode dir is consumed by its `calls.jsonl`; the
  pilot's raw scorecards live only in the session scratchpad (reproducible:
  same protocol, rerun and rescore — outcomes will move with models, which
  is why the grid here is the record); `test_portability` requires
  `encoding=` on every text I/O call, which bit this session once.

- **2026-08-11** — **the pilot grid, dated and raw.** Protocol v1.0; runs in
  the Claude Code harness via Workflow `agent()`, agent type
  `general-purpose`, effort pinned `medium`, harness model aliases `sonnet`
  (Sonnet 5, `claude-sonnet-5`) and `haiku` (Haiku 4.5,
  `claude-haiku-4-5-20251001`); one 12-agent workflow per condition × model
  cell, 48/48 completed, cell wall 11–30 min under varying concurrent load.
  Scorecards + `calls.jsonl` archived in the session scratchpad only; the
  scorer reproduces them from any rerun. Cells: **on-sonnet 8/12,
  off-sonnet 8/12, on-haiku 6/12, off-haiku 6/12** (passes of runs; calls
  totalled 18/21/35/35). Per episode (pass counts over
  {on,off}×{sonnet,haiku}, repeats folded in; E2/E5/E7/E8 ran twice per
  cell):

  | episode | on-sonnet | off-sonnet | on-haiku | off-haiku | failure shape |
  |---|---|---|---|---|---|
  | E1 zero | 1/1 | 1/1 | 1/1 (8 calls) | 1/1 | — |
  | E2 displacement | 0/2 | 0/2 | 0/2 | 0/2 | verdict `converged`, displacement never freed |
  | E3 width | 1/1 | 1/1 | 1/1 | 1/1 | — |
  | E4 scale | 1/1 | 1/1 | 1/1 | 1/1 | — |
  | E5 impurity | 2/2 | 2/2 | 2/2 | 2/2 | — |
  | E6 cell +0.4 % | 1/1 | 1/1 | 1/1 | 1/1 | — |
  | E7 hopeless | 2/2 | 2/2 | 0/2 | 0/2 | haiku: `impurity_suspected` |
  | E8 collinear | 0/2 | 0/2 | 0/2 | 0/2 | verdict `converged` everywhere |

  **Mandatory caveats** (PROTOCOL.md § Reading the grid): the lazy path fixes
  E1/E3/E4/E6, so those rows are competence controls (16/16 — clean); E3's
  possible sign inversion never fired because *no agent followed the report's
  width emitters* — everyone ran the default plan, which frees `w` itself;
  pilot, not benchmark; counts, never percentages.

  **Findings, in rank order:**
  1. **The A/B on outcomes is null in both models, and the measured reason is
     process, not content.** Every agent's first move was the untouched
     request; the resulting states look converged (E2: Rwp 0.0137 with the
     compensating zero; E8: Rwp 0.0126 at truth-looking values) and the
     report *at those states* is empty — actions `[]`, measured. WP-1052
     proved the discriminating content exists at bootstrap-grade states
     (`refine_sample_displacement` named, position family capped 0.3); no
     agent ever generated such a state, so report-attached was never
     report-read-where-it-speaks. The §5/§6 excerpts teach how to read a
     report, not *when to generate one* — the §9 canonical-loop gap. Testing
     a §9 excerpt is a protocol-version bump (v1.1), deliberately not done
     mid-pilot.
  2. **E7 split by model with the report on the wrong side of the split**:
     the abstained report's only action is `add_impurity_phase` at 0.9
     (measured in the on-haiku E7a trace), haiku's answer quotes it verbatim
     as grounds for the wrong verdict, and off-haiku reaches the same
     misread unaided; sonnet in both conditions **declines the invitation by
     indexing the unmatched peaks itself** (a ≈ 4.157 Å from 21.36/30.38/
     37.44/48.96°, "the cell is wrong, not a second phase") and abstains.
     WP-1052 finding 1 anticipated this invitation on E6; measured, it bites
     on E7 instead (the lazy path rescues E6 before any report is read), and
     the side hypothesis — the report lifts the weaker model most — came out
     **inverted** on this row: the report reinforced the weaker model's
     error and the stronger model ignored it.
  3. **E5 is the one row where report value was accessible at a bad-fit
     state, and it showed as efficiency, not outcome** (8/8 pass):
     on-sonnet E5a answered from Layer 2's `add_impurity_phase` in **1
     call**; off-sonnet E5a needed **3 calls** including a hand-rolled
     7-stage plan and its own LaB6 position calculation to find the
     unindexed 29.34° line. Not consistent though — E5b 2 vs 1 calls, haiku
     7/3 vs 6/7 — so a direction, never a claim.
  4. **E2 and E8 failed 8/8 each, exactly on the sharpened traps**: E2 ends
     `converged` at χ²_red ≈ 1.01 with the displacement absent from
     `parameters` (the vary-or-tie absence rule scored it, no re-derivation);
     E8's lazy fit lands zero at −2e-4 and the cell −6 ppm with only
     u~v/v~w `HIGH_CORRELATION` diagnostics visible, so `converged` is what
     every agent said — the ambiguity evidence exists only in unconverged-
     state reports no one generated.
  5. **Harness soundness**: 48/48 runs completed, `n_refused` 0 everywhere
     (no agent attempted an unsanctioned overlay key), 48/48 wrote a valid
     `answer.json` (two late, after the first scoring pass), wrong-frees
     constant per episode across all four cells (5/5/2/7/5 for
     E1/E2/E3/E4/E6 — everyone ran the same preset, so localisation shows
     no condition effect either).

  Also this session, before the pilot: the `AgentSuccess` vary-or-tie gap
  (Context § payload) and two measured harness facts folded into the prompt
  (episode.json is bulk; a diverging E7 call takes ~113 s and fails with a
  structured envelope naming the runaway cell). Audit per PROTOCOL.md: one
  transcript per cell spot-checked (E5a on/off sonnet, E7a on-haiku, E5a
  off-haiku); all four followed the prompt, worked from response numbers,
  and wrote their own answer.json; grading used the shim log only.
  Arrival note: the Inherited section was folded into Context verbatim
  (none stale — 1052 closed the same day, all four findings bind the
  scorer; findings 1, 2 and 4 were each measured again here).

- **2026-08-05** — created; not started, and blocked on WP-1052 only for the
  episode tolerances/families (the fixtures themselves come from `_truth()`
  directly). Interface facts in Context were verified against `agent.py`, not
  assumed. Next: the `AgentSuccess` payload verification task — do it first, the
  scorer's design rests on it. Gotchas: conditions are enforced by the shim, not
  the prompt (an agent can ignore a prompt; it cannot un-strip a response), and
  every summary of the pilot grid must carry the discriminating-rows caveat — the
  default plan alone solves E1/E3/E4/E6, so a flat "report didn't help" reading
  of those rows is the misread this WP exists to prevent.

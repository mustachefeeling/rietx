# WP-1058 — Deliver the report where it speaks: the per-stage trajectory

Milestone: v1.0 · Status: ✅ 2026-08-13
Depends on: —

## Goal

The informative report reaches a `refine_json` consumer without operator skill:
a `diagnose` task (and/or per-stage report trajectory) that generates the
bootstrap-grade states where the report actually has something to say, so an
agent no longer has to *know* to create them. This is the direct fix for
WP-1053's measured bottleneck.

**Shipped as the trajectory alone**, because the premise turned out to be
half-wrong in a useful way: nobody had to *generate* those states — every plan
already passes through them, and only the last one was ever delivered.

## Context

**The measured bottleneck (WP-1053, closed 2026-08-11).** The 48-run pilot came
back null on outcomes in both models, and the measured mechanism is process, not
content: every agent's first move was the untouched request; the default-plan
fit lands at converged-looking states (E2: Rwp 0.0137 behind a compensating
zero; E8: Rwp 0.0126) where the report's action list is empty — measured
`actions: []`. WP-1052 proved the discriminating content exists at
bootstrap-grade states (`refine_sample_displacement` named; the position family
capped at 0.3 on the collinear window); no agent ever generated such a state.
The pilot's transferable lesson, quoted from its record: **information placed
where the agent already looks beats information the agent must know to
request.** This WP is items 1 and 3 of that campaign's ranked follow-ups.

**Five things a delivery surface must place, not four** (from WP-1055, closed
2026-08-12). `FitReport.background` is Layer-0-grade — it speaks on an abstained
report too, it always publishes its numbers, and exactly two of them are summary
triggers. The Rwp / Rwp-background-subtracted pair is **deliberately not** one:
measured, every background-dominated pattern crosses any useful threshold on it,
converged ones at ratio 3.6 and 5.6 included, so a delivery loop that
re-promotes it into a headline undoes a measured decision. It sits at step 7 of
AGENT_PROTOCOL §4's judging order, paired with raw Rwp.

**One ranking question is open on purpose, and this WP is where it can be
answered** (WP-1055 had no measurement to settle it). On the too-stiff fixture —
a Gaussian hump under a 2-term Chebyshev — the residual runs 12σ over hundreds
of channels, noise on top clears the 5σ peak-detection floor in **146** places,
and `add_impurity_phase` is emitted at **0.90** on a specimen with no impurity,
above `increase_background_flexibility` at 0.60. `note_background_crosstalk`
makes each action name the other, but deliberately does **not** cap: unlike
`cap_texture_crosstalk` (where the impurity was the plausible cause of the
texture signature on the *same* reflections), these two findings are about
disjoint channels by construction — Layer 0 segments a region around every
residual peak, so an unmatched peak is never off-region — and both statements
are true. A diagnose task that orders hypotheses is the surface that can rank
them.

**Design space** (decide in-session; both halves are additive):

1. **`task="diagnose"`** in `agent.refine_json`: runs a declared ladder of
   evaluate/bootstrap-grade states (e.g. background-only, then
   +scale, then the full preset — the WP-1052 episode bootstrap is the shape)
   and returns the report *from each state where it speaks*, plus the final
   fit's report. A new request arm in the strict task union and a new answer
   arm (different shape ⇒ separate arm, the WP-1043 rule); `SCHEMA_VERSION`
   reasoning documented either way.
2. **Report trajectory on `task="refine"`**: `include_report="per_stage"` (or a
   sibling flag) attaching each stage's report summary to the existing
   `StageResult`. Numbers not curves — the token budget rule (top-N regions +
   rollup) already exists; measure the payload before choosing defaults
   (episode.json bulk was a measured harness fact in 1053).

**Fences and interactions:**

- **No autopilot** (the 1050 fence): diagnose *informs*; it never applies a
  suggestion. The ladder is **declared and fixed** — it must never be derived
  from its own intermediate reports (that would be the report driving the
  refinement, the exact thing the fence forbids). `predict_then_verify` remains
  the caller's move.
- **Wall clock is part of the contract**: a diagnose ladder is several fits per
  synchronous call, and 1053 measured a single diverging call at ~113 s. The
  ladder's stages are bootstrap-grade (small free sets, cheap) — measure the
  end-to-end time on the episode fixtures and document it beside the payload
  budget; a `diagnose` that takes minutes silently is a regression against the
  bounded-anytime lesson the indexing `quick` preset encodes.
- **The vary-or-tie contract is WP-1003's decision** (its `### Inherited`
  carries it from 1053, with the measured 16/16-invisible consequence). This WP
  must not pre-empt it: if 1003 widens `result.parameters`, diagnose inherits
  it; if 1003 freezes the filter, diagnose's states still make held-parameter
  families *reportable* via WP-1056's exchangeability section rather than via
  the parameters list.
- **Frozen-per-stage discreteness**: diagnose states are ordinary stages (or
  evaluate-only compiles); nothing new moves inside a solve.
- **A ladder branches on the abstention *kind*, not on the presence of a reason**
  (WP-1057, closed 2026-08-12). `abstained_kind="resolution_limited"` is a
  *terminal* state for a declared phase-ID deliverable — AGENT_PROTOCOL §4b calls
  it a legitimate stopping point, "not evidence the model is wrong" — so a ladder
  that keeps escalating on it is exactly the push-finer-corrections behaviour the
  WP-1057 regime directive forbids. §4b's per-deliverable stopping criteria are
  themselves decision-point content: 1053's bottleneck was *when the report is
  read*, and §4b is the first content that licenses stopping early, so it is worth
  surfacing at whatever delivery point this WP builds — a coordinate for the §9
  wording task above.
- **Report builds are no longer free**: a rietveld-mode report runs a 5-cycle
  Le Bail partition per build (un-timed in isolation, suite wall unchanged) —
  which matters only if this WP makes report builds per-stage-frequent, i.e. it
  is a cost to measure on the trajectory half of the design space.
- **Never spell the distribution name, the tool name or a format token** — import
  from `_about.py` (`AGENT_TOOL_NAME`, `DIST_NAME`); WP-1062 landed 2026-08-12 and
  its audit test greps the **old** token, so it is blind to a hardcoded new one.
  `agent.tool_definition()`'s name is already such a literal and is pinned by
  `tests/test_agent_surface.py`; a new task arm must not add another.
- **409-while-running** and the GUI: `GET /api/report` is idle-only; a diagnose
  ladder through the GUI run-state machine is out of scope here (session verbs
  are `gui/CLAUDE.md` territory) — the agent surface is this WP's consumer.
- Whatever ships must be what the protocol teaches: coordinate the §9 wording
  with WP-1059's prompt-condition experiment (the eval measures *this* WP's
  effect).

## Non-goals

- No stateful agent-surface iteration (history_path continuation as a
  conversational session) — 1053's ranked item 5, deliberately after this.
- No report-content changes (WP-1054…1057) — delivery only.
- No MCP server (v2 fence); no GUI diagnose panel.

## Tasks

- [x] Decide diagnose-vs-trajectory (or both) with a measured payload budget;
      record the decision and the SCHEMA_VERSION reasoning in `agent.py`'s
      docstring and the schema. **Decided: trajectory only** — the ladder is
      redundant with every shipped preset (measurement in the handover), and a
      ladder that added states would change the fit being compared. Neither
      version moves; the reasoning is in `agent.py`'s docstring.
- [x] Implement the chosen surface in `agent.refine_json` + `tool_definition()`
      (registry-quoted, meta-test extended — the trajectory's type must appear
      in the exported response schema, beside the four arms and `evidence`).
      Library half: `fit(stage_reports=True)` → `Refinement.stage_reports_`;
      `FitReport.for_stage()` is the projection; `capabilities().features`
      gains the derived `report_trajectory` flag.
- [x] `docs/AGENT_PROTOCOL.md` §9: the read-the-run rule as §9a, the DAG loop
      after it, §9c JSON example checked field for field against a real call
      (and §9c's "four tasks" corrected to five). §5 gains the rule itself, so
      the report-on prompt's live excerpt teaches it.
- [x] Tests: one `refine_json` call on the E2 fixture, asserted in both halves
      (empty converged action list + the 1056 exchange finding; the first
      rung's named displacement); report-off strips both halves, two ways;
      the answer is bit-identical with and without; payload budget; PNG to
      `tests/output/`.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_agent_surface.py tests/test_report_loop.py -q
.venv/bin/python -m ruff check src tests examples
```

One `refine_json` call on the E2 fixture returns a report in which the
displacement family is named — the state that in the 1053 pilot no agent ever
generated — with no LLM dependency added and the task-union meta-test green.

## References

- WP-1053 pilot findings (restated in Context; the WP file holds the dated
  grid) and its ranked follow-ups (items 1, 3).
- WP-1052's episode bootstrap (the ladder shape).
- `docs/AGENT_PROTOCOL.md` §9 (the loop this makes one call).

## Handover log

- **2026-08-11** — created, from the 1053 campaign's ranked follow-ups (the
  when-the-report-is-read bottleneck). Not started.

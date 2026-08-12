# WP-1058 — Deliver the report where it speaks: diagnose task and per-stage trajectory

Milestone: v1.0 · Status: ⬜
Depends on: —

## Goal

The informative report reaches a `refine_json` consumer without operator skill:
a `diagnose` task (and/or per-stage report trajectory) that generates the
bootstrap-grade states where the report actually has something to say, so an
agent no longer has to *know* to create them. This is the direct fix for
WP-1053's measured bottleneck.

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
- **409-while-running** and the GUI: `GET /api/report` is idle-only; a diagnose
  ladder through the GUI run-state machine is out of scope here (session verbs
  are `gui/CLAUDE.md` territory) — the agent surface is this WP's consumer.
- Whatever ships must be what the protocol teaches: coordinate the §9 wording
  with WP-1059's prompt-condition experiment (the eval measures *this* WP's
  effect).

### Inherited

**From [1062](1062-rename-to-anatase.md), created 2026-08-12 — the package is
being renamed to `anatase`; keep the name out of new literals.** A `diagnose`
task adds surface to `agent.py`, whose tool name is already a name literal
(`tool_definition(name="anatase_refine")`, pinned by
`tests/test_agent_surface.py`). If 1062 has not landed when you start, take the
tool name and any `pip install` hint from `_about.py` (`AGENT_TOOL_NAME`,
`DIST_NAME`) rather than writing the string — that file is 1062's Phase 1 and is
designed to land before the rename itself. Every new literal is a file 1062 has
to sweep, and after it lands the audit test fails CI on a reintroduction.

**From [1055](1055-background-evidence.md), closed 2026-08-12 — a new report
section to deliver, and one ranking question left open on purpose.**
`FitReport.background` is a fifth thing a delivery surface must place: it is
Layer-0-grade (it speaks on an abstained report too), it always publishes its
numbers, and exactly two of them are summary triggers. The Rwp /
Rwp-background-subtracted pair is **deliberately not** one — measured, every
background-dominated pattern crosses any useful threshold on it, including
converged ones at ratio 3.6 and 5.6 — so a delivery loop that re-promotes it
into a headline would be undoing a measured decision. AGENT_PROTOCOL §4's
judging order is where it now sits, at step 7, paired with raw Rwp.

**The open question, with its measurement.** On the too-stiff fixture (a
Gaussian hump under a 2-term Chebyshev) the residual runs 12σ over hundreds of
channels, noise on top of it clears the 5σ peak-detection floor in **146**
places, and `add_impurity_phase` is emitted at **0.90** on a specimen with no
impurity — above `increase_background_flexibility` at 0.60. WP-1055 added
`note_background_crosstalk`, which makes each action name the other, but
deliberately did **not** cap: unlike `cap_texture_crosstalk` (where the impurity
was the plausible cause of the texture signature on the same reflections), these
two findings are about disjoint channels by construction — Layer 0 segments a
region around every residual peak, so an unmatched peak is never off-region —
and both statements are true. Whether the top-ranked *action* should still be
the phantom phase is a delivery/ranking question this WP had no measurement to
settle; a diagnose task that orders hypotheses is where it can be answered.


**From [1057](1057-purpose-grade-evidence.md), closed 2026-08-12 — two
report facts a delivery loop must respect.** An abstention with
`abstained_kind="resolution_limited"` is a *terminal* state for a declared
phase-ID deliverable (AGENT_PROTOCOL §4b: a legitimate stopping point, "not
evidence the model is wrong") — a diagnose ladder that keeps escalating on
it is exactly the push-finer-corrections behaviour the WP-1057 regime
directive forbids, so the ladder should branch on the kind, not just on the
presence of a reason. And §4b's per-deliverable stopping criteria are
decision-point content: the 1053 pilot's bottleneck was *when the report is
read*, and §4b is the first content that licenses stopping early — worth
surfacing at whatever delivery point this WP builds, and a coordinate for
the §9 wording task above. (Rietveld-mode reports also now run a 5-cycle
Le Bail partition per build — un-timed in isolation, suite wall unchanged;
relevant only if this WP makes report builds per-stage-frequent.)

## Non-goals

- No stateful agent-surface iteration (history_path continuation as a
  conversational session) — 1053's ranked item 5, deliberately after this.
- No report-content changes (WP-1054…1057) — delivery only.
- No MCP server (v2 fence); no GUI diagnose panel.

## Tasks

- [ ] Decide diagnose-vs-trajectory (or both) with a measured payload budget;
      record the decision and the SCHEMA_VERSION reasoning in `agent.py`'s
      docstring and the schema.
- [ ] Implement the chosen surface in `agent.refine_json` + `tool_definition()`
      (registry-quoted, meta-test extended — a new task arm must appear in the
      exported schema).
- [ ] `docs/AGENT_PROTOCOL.md` §9: the bootstrap-then-read loop rewritten
      around the new surface (one call where three hand-rolled ones were);
      §9c JSON example.
- [ ] Tests: diagnose on the E2-shaped fixture returns a report that names the
      displacement family at a bootstrap state (the content 1052 proved
      exists, now reachable in one call); report-off condition still strips
      everything; payload stays within the documented budget + obs/calc/diff
      PNGs to `tests/output/`.

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

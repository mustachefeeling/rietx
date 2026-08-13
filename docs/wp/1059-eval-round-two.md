# WP-1059 — Agent eval round 2: protocol v1.1 and the post-fix re-A/B

Milestone: v1.0 · Status: ⬜
Depends on: WP-1054, WP-1056, WP-1057, WP-1058

## Goal

The 1053 harness re-run as protocol v1.1 after the content and delivery fixes
land, with pre-registered hypotheses: does the §9 bootstrap-then-read excerpt
(prompt-side), and does the diagnose/trajectory surface (package-side), move the
rows that failed 0/8 — and does WP-1054 flip the one row where the report was on
the wrong side? A dated grid, never a CI assertion.

## Context

**What round 1 established (WP-1053, closed 2026-08-11; harness lives in
`tests/eval_report_agent/`, protocol v1.0).** 48/48 runs, {report on,off} ×
{Sonnet 5, Haiku 4.5} × WP-1052's eight episodes: **null on outcomes in both
models** (sonnet 8/12 both conditions, haiku 6/12 both), measured mechanism =
agents never generate the states where the report speaks. Where it spoke it cut
sonnet's E5 work 3→1 calls (efficiency, not outcome) and fed haiku its wrong E7
verdict verbatim (`add_impurity_phase` 0.9 on the abstained branch). The side
hypothesis "the report lifts the weaker model most" came out **inverted** on E7.

**Mandatory caveats that carry into every round-2 summary** (from the 1053
record; restated because the protocol forbids reading other WP files):

- The lazy default-plan path solves E1/E3/E4/E6 — those rows are competence
  controls, and a flat "report didn't help" reading of them is the designed
  misread.
- E3 can invert the on/off sign (the report's width emitters name
  `lor_size`/`lor_strain`, plateau χ²_red ≈ 4.3, while the default plan frees
  `w` to the ≈1.01 floor). It never fired in round 1 *because* nobody followed
  the report; if round 2's delivery fixes work, it can start firing — watch it.
- Counts, never percentages, at these N; pilot grids are dated records, outcomes
  move with models, nothing lands in CI beyond the deterministic scorer's own
  tests.
- Score recovery by the planted parameter, never by Δχ² (E8's axial-divergence
  absorber survives verification).

**Round-2 conditions** (1053's ranked items 2 and 6, plus the fix measurements):

1. **Protocol v1.1 prompt**: add the AGENT_PROTOCOL §9 bootstrap-then-read
   excerpt (rewritten by WP-1058) to the shared prompt. This was 1053's
   deliberately-deferred experiment — a prompt change is a protocol version
   bump, never a mid-pilot edit.
2. **Package-side delivery**: episodes run against the WP-1058 surface (the
   per-stage `trajectory`; the `task="diagnose"` ladder was *declined* on
   measurement), so "the report where it speaks" arrives without operator
   skill. Conditions separate prompt-only from surface-only — that is the
   cleanest reading of *which* intervention moved E2/E8.
3. **Content fixes live**: WP-1054 (E7's invitation), WP-1056 (converged-state
   exchangeability — the E2/E8 evidence), WP-1057 (stopping criteria — bears on
   verdict quality for the non-ideal rows).
4. **Wider matrix per 1053's item 6**: a second effort tier (round 1 pinned
   `medium`), a third model if available, more repeats on discriminating rows,
   and one real-data episode pair (SRM 660c — where *refusal* is the correct
   behaviour and must be scored as such).

**The content the round measures, as it stands after 1054-1058** (folded in
from the `### Inherited` mailbox on arrival, 2026-08-13; the WPs are closed and
the protocol forbids reading their files):

- **The treatment is now delivery, not content.** `build_fixtures.PROTOCOL_VERSION`
  is **1.1**: a report-on response carries `trajectory` (the report at every
  stage boundary, default-on) and the §5 excerpt the prompt quotes now says to
  read it. A 1.1 run cannot be pooled with the 1.0 pilot's grid — the treatment
  is different, which is the point. The pre-registered question is therefore
  sharper than "does the report help": it is *does naming the cause at a state
  the agent did not have to ask for change what the agent does*.
- **The report-off arm is clean two ways** — `include_report=false` strips the
  trajectory package-side, and the shim pops both. Verify before the round: it
  is the one failure mode that would silently make report-off a report-on.
- **E2 and E8 have the most to gain** (both converge to silent reports over
  compensated parameters); E5/E7 already spoke at the final state, so a null
  there is not evidence against delivery. Score the two groups separately.
- **Content deltas since round 1**: `FitReport.identifiability` (trio + δR
  unconditionally, `exchanges`/`soft_modes` when measured — WP-1056),
  `FitReport.background` (unconditional, plus two never-before-emitted
  `ActionKind` members — WP-1055), `lebail_gap` and `abstained_kind` with the
  resolution-limited flavour (WP-1057), and the abstained-branch action set led
  by `reindex_or_recheck_cell` with `add_impurity_phase` capped at 0.3
  (WP-1054). `THRESHOLDS_VERSION` is **0.7** (round-1 traces read "0.3" — a
  clean condition marker in the grids).
- **The E8 re-scoring nuance (WP-1056)**: on E8's window the *default-plan* path
  frees the planted zero and converges to truth, and that state is correctly
  quiet (partner 1.2σ, bit-identical to the clean-short control). An agent that
  runs the preset and reads the quiet report is *right* to answer converged
  there; the exchange sentence fires on the wrong-family-freed state
  (displacement freed, zero held: 119σ, R² 1.0000).
- **The background trap as a condition axis (WP-1055)**: on the 1055 fixture the
  over-flexible background wins Rwp (0.08852 vs 0.08969) and GoF (1.022 vs
  1.025) while landing 2.6× further from the true Biso — every statistic an
  agent reads improves. Also, `add_impurity_phase` (0.90) still outranks
  `increase_background_flexibility` (0.60) on the too-stiff state with each
  naming the other in `alternatives`: following the ranking blindly buys a
  phantom phase, reading the alternatives does not.
- **The §4b axis (WP-1057)**: the deliverable an episode *declares* (phase ID vs
  structure) is a protocol-side variable, and the hypothesis is that a declared
  phase-ID deliverable plus the gap clause changes when the weak model *stops*.

**Pre-registered hypotheses** (write them into PROTOCOL.md v1.1 before any run):
(a) E2/E8 move off 0/8 only in conditions where the converged-state evidence
(WP-1056) or the bootstrap states (WP-1058) are reachable; (b) E7-haiku flips
with WP-1054's fix regardless of delivery; (c) the §9 excerpt alone, without the
surface, under-performs the surface (the pilot's lesson — placement beats
instruction).

**Budget the matrix before running it.** The full cross
(4 conditions × ≥2 models × 2 efforts × 12 runs) is ~200 runs against round 1's
48 — do not run it flat. Pre-register which cells answer which hypothesis and
prioritise: the prompt-only/surface-only split on the discriminating rows
(E2/E7/E8) is the core; effort tiers and the third model extend only the cells
that showed an effect.

**Harness rules that stand unchanged**: conditions enforced by the shim, never
the prompt; fixtures built fresh per run from `_truth()`; ground truth in the
scorer-side tree; `calls.jsonl` is the record; no LLM dependency anywhere in the
repo; runs execute in the Claude Code harness.

## Non-goals

- No CI assertion on agent outcomes; no significance claims at pilot N.
- No per-model prompt tuning; one shared prompt per condition.
- No stateful-iteration condition (1053's item 5 — still after this).
- No new episodes beyond the SRM 660c pair — episode design changes confound
  the A/B against round 1.

## Tasks

- [ ] PROTOCOL.md v1.1: condition matrix (prompt-only / surface-only / both /
      off), the §9 excerpt text, pre-registered hypotheses, effort tiers,
      model list.
- [ ] Extend the shim/fixtures for the WP-1058 surface (diagnose overlays are
      sanctioned keys; report-off strips the trajectory too — condition
      enforcement stays structural).
- [ ] Scorer: SRM 660c real-data pair rows (refusal-is-correct scoring), and
      the E3 sign-inversion watch (a scored flag, not a pass/fail change).
- [ ] Run the matrix; record the dated grid (model IDs, efforts, per-episode
      scorecards, caveats attached) in this handover log and the v1.0 appendix.
- [ ] Tests: scorer extensions unit-tested (deterministic, fast suite) +
      obs/calc/diff PNGs to `tests/output/` where fixtures render.

## Acceptance

```sh
.venv/bin/python -m pytest tests/eval_report_agent -q
.venv/bin/python -m ruff check src tests examples
grep -ri "anthropic\|openai" src tests --include="*.py"   # no hits
```

PROTOCOL.md carries v1.1 with pre-registered hypotheses; the dated round-2 grid
is in the handover with the mandatory caveats; the repo still carries no LLM
dependency.

## References

- `tests/eval_report_agent/` (harness, protocol v1.0, scorer) — the artifact
  this WP versions forward.
- WP-1052/1053 records (episodes, tolerances, round-1 grid) — key facts
  restated in Context.
- `docs/AGENT_PROTOCOL.md` §9 (as rewritten by WP-1058).

## Handover log

- **2026-08-11** — created, from the 1053 campaign's ranked items 2 and 6 plus
  the design-review fixes it should measure. Blocked until enough of
  WP-1054/1056/1057/1058 lands to define the condition matrix — partial landing
  is fine, but the matrix must say which fixes were live.

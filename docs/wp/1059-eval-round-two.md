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
2. **Package-side delivery**: episodes run against the WP-1058 surface (diagnose
   or trajectory), so "the report where it speaks" arrives without operator
   skill. Conditions should separate prompt-only from surface-only if budget
   allows — that is the cleanest reading of *which* intervention moved E2/E8.
3. **Content fixes live**: WP-1054 (E7's invitation), WP-1056 (converged-state
   exchangeability — the E2/E8 evidence), WP-1057 (stopping criteria — bears on
   verdict quality for the non-ideal rows).
4. **Wider matrix per 1053's item 6**: a second effort tier (round 1 pinned
   `medium`), a third model if available, more repeats on discriminating rows,
   and one real-data episode pair (WP-1052's SRM 660c pair, ready — where
   *refusal* is the correct report behaviour and must be scored as such).

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

### Inherited

**From [1062](1062-rename-to-anatase.md), created 2026-08-12 — a rename is
pending, and it can silently invalidate an A/B comparison.** The package becomes
`anatase`; the `refine_json` surface this WP measures through is renamed with it,
including the agent tool name (`pxrdref_refine` → an `_about.py` constant). Two
consequences. First, **do not straddle the rename with a single A/B**: prompts,
transcripts and episode fixtures that name the package are inputs to the model,
so a round measured half before and half after is comparing two prompt sets, not
two protocols. Land 1062 first or finish the round first — say which in the
handover either way. Second, if you write new episode fixtures before 1062 lands,
take the name from `_about.py` rather than a literal.

**From [1056](1056-identifiability-layer.md), closed 2026-08-12 — the
content change aimed squarely at round 1's two 0/8 rows, and the
pre-registration nuance that matters.** Deltas a re-A/B will see: every
report carries `FitReport.identifiability` (trio + δR unconditionally;
`exchanges`/`soft_modes` whenever the fit measured them), AGENT_PROTOCOL §4
gained step 6 (the §5/§6 excerpts the report-on prompt ships are untouched —
the new reading is *not* in the round-1 prompt's excerpt, only in the
report itself and §4), and the summary gains at most two clauses.  On the
E2 baseline state the summary now reads "fitted instrument.zero_shift =
−0.0109913 stands 128σ from 0 but is exchangeable with the held
instrument.geometry.sample_displacement (R² = 0.9999) … a confident verdict
is not supported" — the ambiguity evidence at the converged state that
round 1's E2 (0/8) and E8 (0/8) failed for want of.  `THRESHOLDS_VERSION`
is **0.7**.  The nuance to pre-register: on E8's window the *default-plan*
path frees the planted zero and converges to truth — that state is
correctly quiet (partner 1.2σ; measured bit-identical to the clean-short
control), so an agent that runs the preset and reads the quiet report is
*right* to answer converged there, and E8's expected verdict may need
re-scoring against the state actually reached; the exchange sentence fires
on the wrong-family-freed state (displacement freed, zero held: 119σ,
R² 1.0000), which is the state a round-1-style lazy path lands on only if
it frees displacement.  Also: the clean full-window control is pinned quiet
on *both* clauses, so any summary-noise hypothesis has a control.

**From [1055](1055-background-evidence.md), closed 2026-08-12 — the third
content change round 2 measures.** Deltas a re-A/B will see: every report now
carries `FitReport.background` (published unconditionally, so it is in the
serialized report an agent reads whether or not anything fired); the summary
gains **one** clause when either background failure mode fires, and none
otherwise (the converged control is pinned silent); and two `ActionKind`
members that had never been emitted anywhere can now appear in
`suggested_actions` — `decrease_background_flexibility` (confidence = the
measured block-projection R², ~0.46 on the fixture) and
`increase_background_flexibility` (capped at 0.60). `THRESHOLDS_VERSION` is
**0.6**.

**One condition axis worth pre-registering, with the trap measured.** The
over-flexible background is the failure mode where *every* statistic an agent
reads improves: on the WP-1055 fixture the wrong background wins Rwp (0.08852
vs 0.08969) and GoF (1.022 vs 1.025) while landing 2.6× further from the true
Biso, and the plot shows white-noise residuals inside ±3σ. An episode planted
this way tests whether a consumer can be moved off a better-looking fit by a
single projection number — which is a sharper version of round 1's question
(*when* the report is read) than any position-family episode, because here
reading it later is not merely late but actively misleading. Note the report's
own honest asymmetry when scoring: `add_impurity_phase` still outranks
`increase_background_flexibility` on the too-stiff state (0.90 against 0.60,
146 noise-driven unmatched peaks), with each action naming the other in
`alternatives` — a consumer that follows the ranking blindly gets a phantom
phase, and one that reads the alternatives does not.


**From [1057](1057-purpose-grade-evidence.md), closed 2026-08-12 — the
second content change round 2 measures, and one new condition axis worth
pre-registering.** Deltas a re-A/B will see: Rietveld-mode reports now carry
`lebail_gap` and up to two new summary clauses (the gap clause above ratio
1.5, the contents-type clause on sign-alternating trend-free intensity
misfit), abstained reports carry `abstained_kind` with the
resolution-limited flavour appending "not evidence the model is wrong" to
the reason, and `thresholds_version` reads "0.5" (round-1 traces "0.3",
1054-era "0.4" — three clean condition markers). AGENT_PROTOCOL grew §4b
("Declare the deliverable"): the deliverable an episode *declares* (phase ID
vs structure) is now a protocol-side variable the prompt can set, and the
hypothesis worth pre-registering is that a declared phase-ID deliverable
plus the gap clause changes when the weak model *stops* — the 1053 pilot's
bottleneck was when the report is read, and §4b is the first content that
licenses stopping early. On E6/E7-shaped abstained states the report now
leads with `reindex_or_recheck_cell` (0.4, calibration candidates in
`alternatives`) and `add_impurity_phase` is capped at 0.3 with reindex first
among its alternatives whenever every strong unmatched peak matches the
position-error evidence — so the E7 quote-the-invitation failure mode
(haiku citing `add_impurity_phase` 0.9) now has the opposite sign available:
the hypothesis to pre-register is that the weak model quotes the *reindex*
rationale instead. Texture false positives no longer outrank the impurity
call (capped below it, `TextureAnalysis.caveat` set), which touches E5's
incidental-rejection round. Reports now carry `thresholds_version: "0.4"` —
round-1 traces say "0.3", a clean condition marker in the grids.

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

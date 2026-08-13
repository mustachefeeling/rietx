# WP-1059 — Agent eval round 2: protocol v1.1 and the post-fix re-A/B

Milestone: v1.0 · Status: ✅ 2026-08-13
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

- [x] PROTOCOL.md v1.1: condition matrix (five cells — a 2×2 on trajectory × §9
      plus the report-less baseline), the §9 excerpt policy, five
      pre-registered hypotheses, effort tier, model list, budgeted cells.
- [x] Extend the shim/fixtures for the WP-1058 surface (the trajectory, not a
      diagnose ladder — 1058 declined it; both halves set on the request *and*
      popped from the response, so enforcement stays structural).
- [x] Scorer: SRM 660c real-data pair rows (R1 refusal-is-correct, graded on
      the verdict with the planted value recorded and not graded), the E3
      sign-inversion watch, and three more descriptive flags —
      `overclaimed`, `bootstrap_calls`/`plans_used`, the payload audit.
- [x] Run the matrix; record the dated grid (model IDs, efforts, per-episode
      scorecards, caveats attached) in this handover log and the v1.0 appendix.
- [x] Tests: scorer/shim/fixture extensions unit-tested (17 → 46, of which two
      slow: the real pair's construction and R1's landing state) + the
      obs/calc/diff PNGs from the one test that refines.

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

- **2026-08-13** — **round 2 ran; the harness is sound and two of its three
  rows are not.** Protocol 1.1, five conditions, 30/30 runs returned with 0
  errors (656 tool uses, 1.688 M subagent tokens, 9 m 55 s wall), models
  `claude-sonnet-5` and `claude-haiku-4-5-20251001` at effort `medium`, N=1,
  `[dev]` venv on darwin/arm64, `THRESHOLDS_VERSION` 0.7, package 1.0.0.dev0.

  **Grid, pre-registered scoring** (E2 → converged + displacement within
  0.005 mm; E8 → ambiguous; R1 → ambiguous):

  | condition | model | E2 | E8 | R1 | passed |
  |---|---|---|---|---|---|
  | off | haiku | converged | converged,oc | converged,oc | 0/3 |
  | off | sonnet | converged | converged,oc | converged,oc | 0/3 |
  | report | haiku | converged,b2 | converged,oc | **pass** | 1/3 |
  | report | sonnet | ambiguous,b1 | converged,oc | **pass**,b2 | 1/3 |
  | prompt | haiku | converged | converged,oc | converged,oc | 0/3 |
  | prompt | sonnet | ambiguous | converged,oc | **pass** | 1/3 |
  | surface | haiku | ambiguous | converged,oc | impurity_suspected | 0/3 |
  | surface | sonnet | ambiguous | converged,oc | impurity_suspected | 0/3 |
  | both | haiku | converged | converged,oc | converged,oc | 0/3 |
  | both | sonnet | ambiguous | converged,oc | converged,oc | 0/3 |

  `oc` = overclaimed, `bN` = N bootstrap calls. Per arm (6 runs each): off
  0 passed / 13 calls / 0 bootstraps, report 2 / 20 / 5, prompt 1 / 13 / 0,
  surface 0 / 23 / 0, both 0 / 29 / 0.

  **Audit: clean.** No cell carried a payload disagreeing with its condition
  (`report_present`/`trajectory_rungs` matched all 30), and no transcript
  referenced `docs/`, `src/` or any path outside its run tree — nobody gave
  itself the withheld manual. One leak to fix: `condition.json` lives *in* the
  agent's workspace and several agents read it, so the arm name is visible
  (no manual content is). Move it out of the episode dir next round.

  **What the round measured** — mechanism, not outcome:

  1. **The exchange clause moves agents onto the ridge.** 7 of the 20
     position-episode cells freed *both* zero and displacement: E2 lands at
     +0.0141…+0.0147 (truth 0.000, tol 0.005), R1 at −0.1202/−0.1277 (truth
     −0.0801) — at the best Rwp in the round (E2 0.01369, R1 0.08555). The
     manual forbids exactly this (§4b: "resolved by protocol … never by
     freeing the rival into the same fit"), but the sentence an agent
     actually reads — the WP-1056 summary clause — names the degeneracy
     without naming the action, and the natural action is to free the rival.
     All four cells that reached truth did it by **swapping** which parameter
     is free, never by freeing both (E2: both/sonnet, prompt/sonnet at
     −0.000243; R1: off/sonnet −0.080098, report/sonnet −0.080100).
  2. **`ambiguous` becomes available only with a report**: 8 of 16
     report-bearing position cells against 0 of 4 in `off`. The report does
     convert confident-wrong into declined — the package's stated goal — but
     on E2 that verdict is scored wrong and on R1 the data actually chooses
     (below), so the conversion cost passes in both directions.
  3. **Hypothesis (c) refuted.** `prompt` (1/6) did not under-perform
     `surface` (0/6); the two trajectory arms did *worse* than report-only
     (2/6). And instruction produced no bootstrapping at all: every one of
     the round's 5 bootstrap calls came from `report`, the arm carrying
     neither §9 nor the trajectory, while `prompt` — which quotes §9's "read
     the report at every stage it passed through" — produced zero.
  4. **Hypothesis (d) supported, and its cure is not a fix.** `surface`
     answered `impurity_suspected` on R1 2/2 (the first rung serves
     `add_impurity_phase` 0.9 on a displaced pattern); `both`, which quotes
     §9's climbing-confidence rule, did so 0/2 — and answered a confident
     `converged` from the ridge instead.
  5. **Delivery costs work**: median calls per cell off 2.0, report 3.0,
     prompt 2.0, surface 3.5, both 4.5. Round 1 measured the report *saving*
     a call on E5; here it adds them.

  **Two episode-validity findings, both post-hoc, both blocking a re-run:**

  - **E8 is a broken row, not a null.** 10/10 cells answered `converged`.
    Under WP-1056 the default-plan path frees the planted zero and converges
    to truth with a correctly *quiet* report, so `converged` is what the
    reached state supports and no competent agent can pass the row as
    written. Round 1's 0/8 was read as a null; it was a scoring artefact.
  - **R1's pre-registered `ambiguous` is not supported by the data.** The fair
    rival test — each position parameter freed alone with the other at its
    null — gives zero-only Rwp 0.09361 / χ² 4.0752 against disp-only 0.08661 /
    3.4890 on 5332 points, and the zero-only model also biases *a* by +100 ppm
    (4.157310 vs 4.156895). The exchange R² of 0.9977 is a **geometric**
    measure; at these counting statistics the 0.23 % of the column it leaves
    unexplained is decisive. Scored with R1 → `converged` the ranking
    **inverts**: off 2, report 0, prompt 1, surface 0, both 2. Both grids are
    published; neither supports a claim about delivery.
  - Related, and the reason only R1 could answer that question: E2 and E8
    plant their aberration in the **starting model**, never in the data
    (`_truth()` has zero = disp = 0), so their one-parameter rivals tie
    exactly (χ² ratio 1.0000). Only a real specimen is genuinely displaced.

  **Verdict on the round**: at N=1 per cell, with two of three rows' expected
  verdicts in doubt, the grid does not support a claim about delivery in
  either direction — and saying otherwise from these 30 runs would be the
  same error the package refuses in its own reports. What it does support is
  the ridge mechanism, the two episode defects, and a manual gap.

  **Landed**: PROTOCOL v1.1 (5 conditions, §9 excerpt policy, 5 pre-registered
  hypotheses, budgeted cells, episode-validity section); both condition
  switches enforced on the request and popped from the response; R1/R2 real
  episodes off the SRM 660c converged state; scorer gains `overclaimed`,
  `watch`, `bootstrap_calls`/`plans_used`, the payload audit; `grid.py`; and
  the one rule the round paid for, in `tests/CLAUDE.md`.

  **Counts** (`[dev]` venv, darwin/arm64): this directory 17 → 46 tests, of
  which 2 are slow — the real pair's construction, and R1's landing state,
  which pins the episode design and writes its PNGs. 0.9 s fast, 5.8 s with
  the slow pair. Whole tree: `-m "not slow"` collection 2277 → 2304 (**+27**)
  and total collection 2384 → 2413 (**+29**) — the 29 added, 27 of them in the
  fast selection, no new skips. The fast run itself reports **2198 passed,
  108 skipped** in ≈2:20 (one machine, one run — wall clock is a range), and
  2306 against 2304 collected is the documented two-module `importorskip`
  undercount rather than a discrepancy.

  **Next, in this order** — none of it is a re-run:
  1. Redesign E8 (plant where the default plan cannot free it) and re-score
     R1 to `converged`; both are in PROTOCOL.md § Episode validity.
  2. The manual gap is the one finding with a consumer-facing fix: the
     exchange clause should name the **swap** (re-fit with the rival free and
     the fitted one held, compare χ²), because "the data cannot tell which is
     physical" is read as an invitation to free both. Pushed to WP-1003's
     `### Inherited`; it is a content change, so it is a protocol version
     bump and must not be made mid-round.
  3. Only then the deferred cells (E7 for hypothesis (b), the controls, the
     effort tier, R2).

  **Gotcha**: the round cost 1.69 M subagent tokens for 30 runs (~56 k/run).
  Budget the deferred pass from that figure, not from round 1's.

- **2026-08-11** — created, from the 1053 campaign's ranked items 2 and 6 plus
  the design-review fixes it should measure. Blocked until enough of
  WP-1054/1056/1057/1058 lands to define the condition matrix — partial landing
  is fine, but the matrix must say which fixes were live.

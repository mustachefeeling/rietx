# WP-1065 — What a decisive swap licenses: the follow-through sentence, measured on the row it failed

Milestone: v1.0 · Status: ⬜
Depends on: WP-1063, WP-1064 (both closed — every finding this WP acts on is
restated below); before WP-1003 (the clause is public report text and a
`THRESHOLDS_VERSION` bump — the freeze should freeze the follow-through
wording, not 0.8's)

## Goal

The exchange clause, §4 step 6 and §4b say what a *decisive* swap outcome
licenses (the winning rival's fit is the answer, quoted without caveat) and
what a tie licenses (protocol or declared ambiguity) — `THRESHOLDS_VERSION`
0.8 → 0.9; the eval glossary's `assumption_wrong` stops naming refinable
geometry; and a targeted 12-cell round (protocol 2.1) measures whether
round 3's 0/7 solvable control was the missing sentence, with the tie row as
the guard against overcorrection.

## Context

**The measured defect (WP-1064, round 3, 28 runs, 2026-08-13).** The 0.8
clause **produces the experiment and not the verdict**. On C1 — real SRM
660c, displacement knocked to −0.02, the rivals decisive at χ² ratio 1.1679,
expected `converged` with tol {abs: 0.005} + next_action `none` — the
solvable control went **0/7 valid**. The decomposition, off the round's
mining: three sonnet cells ran the swap and recovered the displacement to
−0.0801, and two still declined — `report__sonnet` recovered −0.080098 and
answered `ambiguous` + `extend_range_or_calibrate`; `off__sonnet` recovered
the displacement and answered `assumption_wrong` (the glossary defect,
below); `python__sonnet` converged, recovered −0.08011, and failed only on
`report_with_caveat` ∉ {none} — it hedged a solved fit. Nothing in the
clause or AGENT_PROTOCOL §4b says what a decisive swap *licenses*: the
sentence ends at "…compare χ²", the agent runs the comparison, wins it, and
has nowhere to read that winning it is an answer. Round 2's
recovered-and-still-declined tension, reproduced in mirror on the row built
to catch it.

**The sentence to extend.** `identifiability_clause()`
(`src/anatase/report/identifiability.py`, the firing-exchange branch)
currently ends:

```
f"…never by freeing both into one fit (that is a ridge): fit each of the "
f"pair alone with the other held at its null and compare χ²"
```

Proposed continuation (final wording may adjust; the four properties are
fixed):

```
f"; a χ² gap of ≥ {RIVAL_DECISIVE_MIN_CHI2_RATIO - 1:.0%} means the data "
f"has chosen — the winning rival's fit is the answer, quoted without "
f"caveat; a smaller gap means the pair is genuinely unresolved: fix it by "
f"protocol (a calibrant-fixed zero, a wider window) or say the data has "
f"not chosen"
```

(i) **Both branches stated.** Round 2 measured what naming the degeneracy
without the action costs (the ridge); round 3 measured what naming the
experiment without the license costs (the 0/7). Stating only the decisive
branch would recreate the same asymmetry a third time, on ties. (ii) **The
strength grade is a named constant, not prose** —
`RIVAL_DECISIVE_MIN_CHI2_RATIO = 1.10` in `report/schemas.py`, exported from
`anatase.report` (the `TRAJECTORY_MAX_ACTIONS` precedent: a documented
reading aid that gates nothing). The value is the round's registered
decision band, and it is measured on both sides: C1's real ratio is 1.1679
(decisive), N1's is 1.0075 and E8′'s 1.0001 (ties, inside [0.99, 1.01]).
(iii) **No verdict token in the summary string.** `test_fitreport_layers.py`
pins `"ambiguous" not in report.summary` on the E2-aberrant and E8-short
states — the verdict stays the reader's. The continuation must not smuggle
`converged`/`ambiguous` in; "the winning rival's fit is the answer" states
the license without the token. Keep that pin, extend the shape pins ("data
has chosen", "without caveat"), never a second full copy of the string.
(iv) **The package states the rule and never applies it.** `RivalComparison`
keeps **no** `decisive` field (WP-1063's fence, deliberate); the swap is two
constrained fits expressible in any surface — round 3's `report__sonnet` ran
it through plain `refine_json` calls — so the sentence names the experiment
and its reading, never an API.

**The glossary defect (recorded post-hoc in round 3, scoring untouched).**
`VERDICT_MEANINGS["assumption_wrong"]`
(`tests/eval_report_agent/build_fixtures.py`) names "the geometry" among
declared inputs — and displacement is *refinable* geometry, so on the one
row where it bites the glossary invites exactly the confusion it caused
(`off__sonnet`/C1 recovered the displacement, then answered
`assumption_wrong`). Fix: name only non-refinable declarations (the source's
emission lines, the geometry *type*, the radiation) and add the explicit
exclusion — a refinable parameter at a wrong starting value is never
`assumption_wrong`; converge it or say the data cannot. Prompt content
changes ⇒ protocol 2.0 → **2.1**, registered and dated before any run
(the standing round discipline); scorer v2 untouched.

**The targeted round — 12 cells, one question, one guard.** {off, report,
python} × {C1, N1} × {sonnet, haiku}, N=1, effort `medium`, expected
answers unchanged from the 2.0 registration (C1 `converged` + tol
{abs: 0.005} + `none`; N1 `ambiguous` + `extend_range_or_calibrate`). The
three conditions decompose the fix: `off` receives neither report nor
manual, so it isolates the glossary fix (its 2.1 prompt is the only thing
that changed for it); `report` adds the clause with the license sentence;
`python` adds the pulls (its workspace manual carries the §4b/§9 updates).
N1 is the **guard**: its swap ties (1.0075) and its expected answer is the
decline — a license sentence that converts a genuine tie into a confident
answer is worse than no sentence, and N1 is the real-data row that would
show it. Episode fixtures are **unchanged** — the package content changes,
not the landing states, so the slow landing-state tests keep their bands —
but python workspaces rebuild (fresh wheel, 2.1 prompt/manual copy).
Budget from round 3's measured figure (1.833 M / 28 cells): ~0.8 M tokens.
Audits per the round-3 pattern: payload enforcement, forbidden reads,
the 8-fit-run cap (which invalidated `python__haiku` C1 at 16 last round).

**Pre-registered read-outs**, written into PROTOCOL.md 2.1 before the run:

- (a) C1 produces valid passes where round 3 had 0/7 — specifically the
  swap-running cells (`report__sonnet`, `python__sonnet`) flip to
  `converged` + `none`, and `off__sonnet` stops answering
  `assumption_wrong` (glossary in isolation).
- (b) N1 does not degrade: the round-3 JSON passes (`off__sonnet`,
  `report__sonnet`) stay passes, and no arm that received the sentence
  newly overclaims `converged` on the tie. A new N1 overclaim means the
  wording overcorrects — revise before any wider claim, and add the E8′
  cells (the synthetic exact tie) to the revision's guard set.
- (c) The both-free overlay counts (round 3: N1 4 cells, C1 2) do not grow.

Counts, never percentages; dated grid, no CI; the record to `eval-runs/`
per its README contract. A null on (a) is a finding too: it would say the
0/7 was not the sentence, and the follow-through question moves from
wording to delivery — recorded, not re-run.

**Close-out mailbox (1003), in addition to the round outcome.** Two notes
for the freeze: `THRESHOLDS_VERSION` 0.9 is the wording it should freeze;
and round 3's pull-usage counts — `report()` pulled in 6 of 8 python cells,
`compare_rivals` in 3, `suggest`/`branch`/`predict_then_verify` in **0** —
are posture evidence for how AGENT_PROTOCOL and the freeze docs describe
those surfaces (demonstrably-pulled vs so-far-unpulled), not grounds for
removal at N=8.

## Non-goals

- No `decisive` field on `RivalComparison`, no auto-adoption anywhere — the
  no-autopilot fence stands; the package states the reading rule and never
  applies it.
- No `EXCHANGEABLE_MIN_R2` retune (the 0.8 changelog's geometric argument
  stands) and no other gate move — 0.9 is wording plus one documented
  constant.
- No `compare_exchanges` arm on `RefineRequest` — decided by round 3, in
  1003's Inherited, not re-litigated here.
- No full round 4: no new episodes, no second tier (J2/E7 stay deferred),
  no `surface` arms (`report_trajectory` flips to False at the freeze), no
  E8′ cells unless read-out (b) triggers them.
- No mid-round change of any kind; defects found mid-round are recorded
  post-hoc for a successor (the standing discipline).
- No freeze decisions — version ratification and posture language land in
  1003; this WP only posts the evidence.

## Tasks

- [x] `RIVAL_DECISIVE_MIN_CHI2_RATIO = 1.10` in `report/schemas.py`
  (exported from `anatase.report`), the clause continuation in
  `identifiability_clause()`, `THRESHOLDS_VERSION = "0.9"` + changelog
  entry (the C1 0/7 evidence, the four fixed properties, why no gate
  moved); `test_fitreport_layers.py` shape pins extended, the
  no-verdict-token pin kept, and the quiet-guard check run (a deliberate
  wording edit fails with the expected message, then passes restored)
- [x] `docs/AGENT_PROTOCOL.md`: §4 step 6 gains the license rule with the
  measured ratios (1.1679 decisive; 1.0075/1.0001 ties) quoting the
  constant; §4b's swap paragraph gains the follow-through sentence; §9's
  `compare_rivals` paragraph states the reading orientation-neutrally
  ("the winning rival"), beside the existing `chi2_ratio` comment
- [x] PROTOCOL.md 2.1: the `assumption_wrong` glossary fix in
  `VERDICT_MEANINGS` + `PROTOCOL_VERSION` bump in `build_fixtures.py`, the
  12-cell matrix, read-outs (a)–(c), the budget — dated before any run;
  scorer v2 asserted unchanged; python workspace builder picks up the
  fresh wheel and the updated manual copy
- [x] Run the 12 cells in the Claude Code harness; audit per the round-3
  pattern; grid (both group tables) from `scorecards.json`; mined
  clause-delivery/overlay/pull counts; raw record to `eval-runs/` per the
  README contract
- [ ] Close-out: read-outs (a)–(c) against their registrations in the
  handover; 1003 `### Inherited` gets the 0.9 note, the round outcome and
  the pull-usage posture note; narrative to `docs/milestones/v1.0.md` +
  the dated grid to its appendix; "say which numbers moved" (both
  selections, venv and platform quoted)

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_fitreport_layers.py tests/eval_report_agent
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

Plus: PROTOCOL.md 2.1 dated before the run; the changelog carries 0.9 with
the no-gate-moved rationale; the clause pins fail on a deliberate wording
edit with the expected message, then pass restored; the dated 12-cell grid
in the handover; the round record per `eval-runs/README.md`.

## References

- WP-1064 handover + `docs/milestones/v1.0.md` § Appendix (round-3 grid,
  2026-08-13) — the C1 0/7, its mined decomposition, and the tie bands this
  WP quotes.
- WP-1063 handover — the 0.8 clause's four-property design pattern this
  continuation extends, and the `RivalComparison` no-verdict fence.
- `tests/eval_report_agent/PROTOCOL.md` 2.0 § Decision bands — the ≥ 1.10
  decisive band and [0.99, 1.01] tie band the constant adopts.

## Handover log

- **2026-08-13** — created, from the post-1064 assessment (the report's
  content keeps its measured value; the delivery claim stays honest; the
  sharpest measured defect is one missing sentence, and its fix is
  testable for a fraction of a round). The round's design confirmed with
  the maintainer: license sentence + glossary fix land first, then the
  targeted 12-cell round decides read-outs (a)–(c).

# WP-1107 — Eval protocol 2.2: the placement round

Milestone: v1.1 · Status: ✅ 2026-08-19 — 2.2 registered before any run;
22/22 cells valid; all three questions answered in the v1.1 appendix; the
winning placement filed as 1108
Depends on: 1105 (the python arm ships a verbatim AGENT_PROTOCOL copy — it
must not carry §9's stale claims into the cells), 1106 (the `execution` field
must exist to be measured)

## Goal

The three questions the v1.0 eval programme recorded but left unowned are
answered by a pre-registered round: where the decisive-swap license must live
to reach agent context, whether the `report_with_caveat` migration is a
scoring artifact or a decision pattern, and whether 1106's `execution` field
changes what agents do with advice actions. A placement wins by grid, and
only then does it ship in the package.

## Context

The harness is `tests/eval_report_agent/` (PROTOCOL.md at 2.1; the shim
`run_refine.py` enforces conditions structurally — switches set on the
request *and* popped from the response; `MAX_CALLS = 8`; workspace and truth
placement rules verified, not assumed). Round records go to `eval-runs/`
(gitignored; its README is the record contract). Budget expectation from the
prior rounds: ~56 k tokens per JSON run, ~100–150 k per python run; rounds
ran 0.85–1.9 M total. Runs execute as real subagents (model and effort are
variables); no grid is ever a CI assertion.

**The three unowned questions, with their numbers:**

1. **License placement** (WP-1065, protocol 2.1, 12 cells): the reworded
   license sentence — a decisive swap gap of ≥ `RIVAL_DECISIVE_MIN_CHI2_RATIO`
   − 1 means the data has chosen — fixed the verdict semantics (C1 moved 0/7
   → 1/5 valid, `assumption_wrong` vanished), but transcript mining showed it
   reached agent context in **2 of 12 cells**: agents pipe the JSON response
   to a file and grep statistics back, and the summary string is what the
   greps drop. The wording question is answered; the open question is
   placement.
2. **The `report_with_caveat` migration**: in 7 of 10 valid 2.1 cells the
   verdict moved toward `converged` while the hedge migrated into the
   `next_action` field. Artifact of the scoring vocabulary, or a real
   decision pattern the vocabulary should admit? Re-read the 2.1 transcripts
   first — the 1063 archaeology precedent ("paid better than expected": three
   counts moved round 3's design before it ran) — before deciding whether
   this needs cells at all.
3. **Second-tier episodes, built and pinned but never run**: J2 (the designed
   Brindley failure, deliverable = QPA), E7 under the capped abstained set,
   E8′ (N1's synthetic control), J1P/J1S (the deliverable axis). The standing
   rule: they run only on cells that showed an effect — do not spend them on
   arms the grid already called null.

**Arm design for placement — the shim constructs it, the package does not
change.** The shim already rewrites responses (popping condition echoes); the
placement arms are projections of the *same* response: (i) status quo — the
license where it lives today, in `summary`; (ii) structured — the shim moves
the license clause (and the threshold constant it quotes) into a field
adjacent to the statistics keys the miners proved agents grep; (iii) the
python arm reads it on `compare_rivals`' return, where the agent that ran the
experiment is certainly reading. *(Registration note, 2026-08-19: (iii) as
written needs the additive `RivalComparison` field — a pre-grid package
change the non-goals forbid — so 2.2 runs the python arm unconstructed, as
the certainly-reading comparator; the manual-§4b route it tests was measured
working in 2.1, and the field stays the successor's candidate if the grid
shows the python route deciding where JSON arms fail.)* Whichever placement
the grid favors ships
afterward as its own additive change; nothing ships on plausibility. Keep the
recorded stance while designing arm (ii): the license is stated, the verdict
is not — no `decisive` boolean, no verdict token
(`report/schemas.py:73-112`).

**Also measured, because 1106 shipped it**: does
`SuggestedAction.execution = "advice"` change what agents do with advice
actions? The 1053 pilot measured the failure this addresses — haiku quoted an
abstained report's `add_impurity_phase 0.9` verbatim as grounds for the wrong
verdict. A W1-family row on {report with `execution`, report without} is the
cheapest honest cell pair.

**1106 moved the episodes under the cells** (closed 2026-08-19; verified in
this tree: `execution` stamped by `build_report`, `report_thresholds_version`
1.2). Three movements the round design must absorb: (i) a width episode's
report now carries `refine_profile_widths` as the instrument-side peer at
half the sample action's confidence, and the E3 loop **converges** (proxy
15.1 → 4.3, then the peer → the 1.01 noise floor) — any W1-family cell
premised on "the loop stalls with nothing left to name" is stale; (ii) a
`resolution_limited` abstention now emits `collect_better_data` at 0.5,
leading the phantom-impurity call — broad-peak episodes gain an advice
action where they had none; (iii) every payload carries
`statistics.max_shift_over_esd` and the protocol's §4 step 1 tells agents to
read it — a new number in every cell's context. Hence Task 2's re-pin of the
landing states before 2.2 is registered.

**Discipline, unchanged from 2.0/2.1** (`tests/CLAUDE.md` § the eval rules;
PROTOCOL.md's own version history): measure the landing states → register →
run, never the reverse; protocol 2.2 dated before any run; deterministic
scorer, closed vocabularies, no LLM judge; counts never percentages; grids
dated to the milestone appendix; **no mid-round content or protocol change**
— defects found mid-round are recorded post-hoc for a successor. Audit per
round: payload enforcement (mismatch invalidates, never explained), forbidden
reads, the fit-run cap, usage mining (`mine_transcripts.py`: probed /
delivered / voiced — never word-matching summaries). The 2.1 runner-
instruction bug is a standing check: the instruction must not name the repo
root (a python cell once sys.path-inserted the repo `src`; cell invalidated).

### The `report_with_caveat` migration — the 2.1 archaeology (Task 1)

Read 2026-08-19 from the round record (`eval-runs/2026-08-13-round3p1`:
answers, scorecards, transcripts; the off-arm and python C1 transcripts
carry no thinking text, so their `answer.json` summaries are the record).
**Answer to the question as posed: both, decomposed.** The action-field
hedge is a real decision pattern — a delivery stance — that the contract
should admit *structurally*, as an unscored field, never as a scoreable
token; the verdict shift toward `converged` is not the vocabulary's at all.
Four mechanisms, separated:

1. **The vocabulary conflates the remedial axis with a delivery stance —
   real, and worth 2 of the 7 rwc cells.** `report_with_caveat` ("deliver
   the result with its named limitation attached") is the one
   delivery-stance token among six remedial ones, and real lab data always
   supplies a true limitation (the round's landing states carry
   Durbin-Watson 0.58–0.92), so the token is always available and always
   honest — an unfalsifiable hedge sink, graded a failure by every
   registered set except second-tier J2's. Exactly two cells fail *only* on
   it: `off__sonnet` C1 (verdict right, displacement recovered −0.08010,
   inside {abs: 0.005}) and `report__sonnet` N1, whose answer states the
   registered `extend_range_or_calibrate` diagnosis in substance ("this
   narrow angular window cannot separate a constant zero offset from a cosθ
   displacement term") and still picks `report_with_caveat` — it read
   `next_action` as "what I recommend doing with this result".
2. **The other five rwc cells fail on grounds no vocabulary reaches**:
   three N1 `converged` overclaims (`off` both models, `python__sonnet`)
   and two C1 tolerance misses (−0.08661 / −0.08649 against −0.0801 at
   {abs: 0.005}; the second is the cell-held `lab_calibrate` state).
3. **The unread-license reading (1065 gotcha iii) is refuted as
   sufficient**: `python__sonnet` C1 had the license in context (clause
   delivered at call 42), ran the decisive swap (ratio 1.59), quoted the
   winner "without further caveat" — and still answered
   `report_with_caveat`, for a different, true, non-rival caveat (the
   zero/displacement esd coupling). The license closes the *rival* caveat
   only; the general hedge has exactly one place to go.
4. **The `converged` shift tracks the glossary imperative, at N=1** (1065
   read-out (b); the archaeology adds no counter-evidence and no proof —
   the off transcripts hold no reasoning). `off` received only the glossary
   fix, and all four of its verdicts flipped to `converged` (round 3:
   `impurity_suspected`, `assumption_wrong` ×2, `ambiguous` — including the
   round-3 N1 pass). The exclusion ends "converge it, or say the data
   cannot", and every off cell took the first branch. One licensed-but-wrong
   route rides beside it, for the audit design: `python__sonnet` N1
   measured a *decisive* 1.277 for the wrong rival on a cell-held state
   (the registered tie [0.99, 1.01] is a property of the registered
   protocol) and the license then licensed the overclaim — so **the state a
   swap ran at becomes a mined fact in 2.2**.

**Decision: amendment *and* cells, one registration — not a re-score, not
amendment-only.**

- Re-scoring 2.1 is refused (standing discipline), and would move only the
  2 cells in mechanism 1.
- **The amendment** (2.2, all arms, harness-side only — the package is
  untouched): split the axes. `report_with_caveat` leaves the `next_action`
  vocabulary; a new **unscored `caveats` field** (free text, mined
  descriptively) takes the delivery stance; `none` re-glossed "no further
  remedial action is needed". J2's second-tier registration becomes
  `converged` + {none} with the µR/Brindley citation mined — equal rigor,
  since token membership never graded caveat *content* anyway. Rejected
  alternatives: admitting rwc into more sets (every real fit carries a
  nameable limitation, so the sets stop discriminating — N1's would no
  longer test that the agent knows the *window* is what is missing);
  re-glossing rwc (wording against wording, when 2.1 just measured wording
  redirecting behaviour; structural enforcement is the house rule).
- **The cells**: no dedicated migration cells. The placement round's C1/N1
  cells re-ask the verdict-shift question under the amended contract and a
  revised glossary imperative — the two changes act on different answer
  fields, so the read-outs stay separable (verdict movement reads against
  the glossary revision; the action field's validity reads against the
  amendment). **E8′ joins the guard set as mandatory**, per 1065's
  pre-commitment ("any wording revision adds the E8′ cells") — 2.2 revises
  wording twice over. The imperative's revision weights both branches
  equally; exact wording lands with the Task 2 registration.

## Non-goals

- Changing report *content* — the content half closed with 1055–1057 and its
  value is measured independently of any agent effect.
- Re-litigating the trajectory default (1064's pre-registered kill stands) or
  Layer 2's posture (left "not isolable from Layer 0" by the same grid).
- Shipping any placement before the grid: the package is untouched until the
  round reports.
- A CI assertion anywhere in this WP; grids are dated pilot records.

## Tasks

- [x] Transcript archaeology on 2.1 for the `report_with_caveat` migration;
      write the finding into the round design (cells, scoring change, or
      "no cells needed — vocabulary amendment only", each with its reason).
- [x] Register PROTOCOL.md 2.2: placement arms (shim-projection design),
      the `execution` cell pair, episode selection (C1/N1 for placement;
      W1-family for `execution`; second-tier only where prior effects
      showed), landing states re-pinned (`test_landing_states.py`).
- [x] Implement the shim placement projections + their unit tests (the shim,
      not the prompt, enforces the condition — both directions).
- [x] Run the grid; audit (payload, forbidden reads, cap, mining); dated
      grids to the milestone appendix, counts not percentages.
- [x] Kill/keep decisions recorded; the winning placement (if any) filed as
      a successor WP or executed here if it is one additive field whose
      writer is already named.
- [x] Handover: token totals, cells invalidated (with reasons), and what the
      next round should not repeat.

## Acceptance

Protocol 2.2 is registered and dated before the first run; every cell in the
grid is audited; each of the three questions has a written answer (or a
written reason it stays open) in the milestone record.

```sh
.venv/bin/python -m pytest tests/eval_report_agent -q
.venv/bin/python -m ruff check src tests examples
```

## References

- WP-1064 (protocol 2.0, the round-3 grid and kill criteria), WP-1065 (the
  2-of-12 placement finding and the 7-of-10 migration), WP-1063 (the
  archaeology precedent and the miner), WP-1053 (the verbatim-quoting
  failure), WP-1052 (the mechanical loop that stays in CI).
- `tests/eval_report_agent/PROTOCOL.md` — the version history is the design
  record; 2.2 extends it.

## Handover log

- **2026-08-19 (close)** — the whole WP ran in one session; all counts
  `[dev]` venv, darwin/arm64.  Nothing in flight; the placement ships as
  [1108](1108-license-statistics-placement.md) (created ⬜, its Inherited
  carries the shim-reference note), and the next eval round's obligations
  are in the gotchas below.

  **Landed** (commits `47758b2a`…`7769c8ab` + this close): the 2.1
  archaeology (§ Context — the migration decomposed into four mechanisms;
  the caveats-field decision with its rejected alternatives); PROTOCOL.md
  2.2 registered and dated before any run (landing states re-measured
  first: 9 passed, ~10 s, `-n 4 --dist loadgroup`); the implementation —
  contract v3 (`report_with_caveat` retired, unscored `caveats`, the
  glossary imperative revised to name both target verdicts, the
  `fix_instrument_model` parenthetical fixed per 1065 gotcha ii), the two
  shim projections (`license_placement` moves the identifiability clause
  byte-exactly via the package's own renderer with a loud
  `PLACEMENT_PROJECTION_MISMATCH`; `include_execution` pops WP-1106's
  field), scorer caveats + four delivered-shape facts, grid audit keyed to
  the marker's own keys (archived rounds regrade byte-identically, tested),
  miner extensions (`LICENSE_PHRASE` pinned to the live clause by test,
  `swap_rows` with the cell-held column, the `execution` token,
  underscore-bearing condition names in `_CELL_RE`); the round + audit;
  the dated grids and read-outs (a)–(e) in `milestones/v1.1.md` § Appendix;
  the round-record row in `eval-runs/README.md` (on disk — the dir is
  gitignored); WP-1108 filed with the ROADMAP row.

  **The round** (2026-08-19, `eval-runs/2026-08-19-round4`): 22/22 cells
  finished, **0 invalidated** (zero payload mismatches including the
  four-direction projection audit; every JSON cell ≤ the 8-call cap, max
  exactly 8; python 4 and 2 fit-bearing runs; zero forbidden-read flags —
  two cells read back their own harness spill files, a discipline note).
  1,661,595 subagent tokens against the ~1.4 M registered ceiling (~19 %
  over), ~16 min wall, effort `medium`, models `sonnet`/`haiku` as the
  harness reports them.  12/22 passed (2.1: 1/10 valid; sonnet 10/11,
  haiku 2/11).  The three answers, in the appendix with their counts:
  **(1) placement** — the pre-registered rule favours `report_stat`
  (in-context 4/4 vs 3/4, no added overclaim; haiku's C1 trap became a
  clean pass), ships via 1108; **(2) migration** — the vocabulary half
  dissolved structurally (caveats written in 22/22 cells, zero rwc-shaped
  failures, every correct-verdict N1 cell lands the registered eroc) and
  the verdict half was the wording's (`off__sonnet` N1 restored to a pass;
  haiku still overclaims N1 — a capacity result now); **(3) execution** —
  null at N=1 on W2 (haiku trapped in both arms, sonnet passed both,
  `execution` voiced by nobody).  The E8p guard fired (3/4 converged on
  the synthetic exact tie's first-ever run) — recorded post-hoc, no
  mid-round change, interpretation deferred for lack of any baseline.

  **Numbers moved**: fast suite 2424 + 117 → **2444 + 117** measured on
  the final tree (2:36, `-n auto --dist loadgroup`) — exactly +20: 14 new
  test functions (10 scorer/shim/grid, 4 miner) plus 6 new parametrize
  instances (the three condition-parametrized tests × the two new
  conditions), no new skips.  Eval selection 93 → 113 passed serial — the
  "97 → 109" in two commit messages counted passed-beside-12-failures
  mid-implementation, not a baseline; this paragraph is the corrected
  ledger.  Ruff clean throughout.  No CLAUDE.md was edited this session.

  **Gotchas for a successor / what the next round must not repeat**:
  (i) J2's trigger fired (caveats 22/22) but its fixture has never been
  built — build, landing measurement and registration come before any J2
  cell; (ii) E8p has no baseline — do not read its 3/4 `converged` as the
  wording's overcorrection without one (N1, the real-data tie, moved the
  *other* way under the same wording); (iii) budget from this round's
  measured figure: ~75 k tokens per JSON cell average (agents print whole
  responses more often than they pipe them), not 2.1's 56 k; (iv) both
  python cells passed **without** `compare_rivals` — the swap is not the
  only route to the right answer, so a swap-conditioned read-out needs
  cells that measurably swap; (v) the two harness spill-file reads match
  no `AUDIT_PATTERNS` entry — benign here (an agent's own stdout), but a
  `tool-results/` pattern would make the audit's silence explicit;
  (vi) `pytest … | tail` masks the exit code — a chained commit went
  through on a red docs-consistency run this session (the ROADMAP cap
  breach, fixed at close); gate commits on pytest's own status.

- **2026-08-19** — session start: Inherited pruned. The single entry (from
  1106) was still-true in full — verified against the tree (`execution` in
  `report/schemas.py`, `THRESHOLDS_VERSION = "1.2"`) — so it folded into
  Context as the "1106 moved the episodes under the cells" paragraph; its
  re-pin instruction was already Task 2's landing-states clause. Nothing was
  stale, nothing deleted as wrong.
- **2026-08-18** — created from the agentic-report planning session, with
  [1104](1104-agent-protocol-literature-audit.md)/[1105](1105-agent-protocol-hygiene.md)/[1106](1106-report-placement-fields.md).
  The three questions were recorded as open by 1065/1003 and owned by no WP
  until this one.

# WP-1107 — Eval protocol 2.2: the placement round

Milestone: v1.1 · Status: ⬜
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
experiment is certainly reading. Whichever placement the grid favors ships
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

### Inherited

- From 1106 (closed 2026-08-19): the `execution` field landed as this WP
  assumes (stamped by `build_report` on every emitted action, `None` only on
  hand-built ones) — but the **episodes moved under the cells**, in three
  ways the round design must absorb.  (i) A width episode's report now
  carries `refine_profile_widths` as the instrument-side peer at half the
  sample action's confidence, and the E3 loop **converges** (proxy 15.1 →
  4.3, then the peer → the 1.01 noise floor) — any W1-family cell premised
  on "the loop stalls with nothing left to name" is stale.  (ii) A
  `resolution_limited` abstention now emits `collect_better_data` at 0.5,
  leading the phantom-impurity call — broad-peak episodes gain an advice
  action where they had none.  (iii) Every payload carries
  `statistics.max_shift_over_esd`, and the protocol's §4 step 1 tells agents
  to read it — a new number in every cell's context.
  `report_thresholds_version` is 1.2; re-pin the landing states
  (`test_landing_states.py`) against the new tree before registering 2.2.

## Non-goals

- Changing report *content* — the content half closed with 1055–1057 and its
  value is measured independently of any agent effect.
- Re-litigating the trajectory default (1064's pre-registered kill stands) or
  Layer 2's posture (left "not isolable from Layer 0" by the same grid).
- Shipping any placement before the grid: the package is untouched until the
  round reports.
- A CI assertion anywhere in this WP; grids are dated pilot records.

## Tasks

- [ ] Transcript archaeology on 2.1 for the `report_with_caveat` migration;
      write the finding into the round design (cells, scoring change, or
      "no cells needed — vocabulary amendment only", each with its reason).
- [ ] Register PROTOCOL.md 2.2: placement arms (shim-projection design),
      the `execution` cell pair, episode selection (C1/N1 for placement;
      W1-family for `execution`; second-tier only where prior effects
      showed), landing states re-pinned (`test_landing_states.py`).
- [ ] Implement the shim placement projections + their unit tests (the shim,
      not the prompt, enforces the condition — both directions).
- [ ] Run the grid; audit (payload, forbidden reads, cap, mining); dated
      grids to the milestone appendix, counts not percentages.
- [ ] Kill/keep decisions recorded; the winning placement (if any) filed as
      a successor WP or executed here if it is one additive field whose
      writer is already named.
- [ ] Handover: token totals, cells invalidated (with reasons), and what the
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

- **2026-08-18** — created from the agentic-report planning session, with
  [1104](1104-agent-protocol-literature-audit.md)/[1105](1105-agent-protocol-hygiene.md)/[1106](1106-report-placement-fields.md).
  The three questions were recorded as open by 1065/1003 and owned by no WP
  until this one.

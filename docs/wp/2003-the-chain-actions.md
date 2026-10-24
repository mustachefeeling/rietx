# WP-2003 — The chain actions: what a series decides between patterns

Milestone: generality · Status: 🔄 2026-10-24 — the inventory, the reseed fence measured on eight chain families, and the first-rung invariance tests landed (PR #1150); next the tiers, the clash table and the batch
Track: The audits
Depends on: 2002, 2037
Priority: P2 2026-10-24 — 2037 closed, so its clause 1 and the response column this WP's first demotion takes are in place; the maintainer's next after 2037; the seam the maintainer's own example (a series discontinuity) lives in

## Goal

Every action `refine_sequential` and the joint fit take between patterns is in the audit
table with a tier: the reseed fence, the rung ladder and quarantine, the kept-attempt
choice, the width-growth fences, the moment-floor carry. Opt-in tools are classified as
such and left alone; answer-invariant items get their invariance test. Each surviving
tier-3 action carries its two grounds and approval; the rest are demoted by their kind of
ambiguity (DESIGN.md § Rules, 1), to a ranking or to the number in a record field.

## Context

The rule is `../milestones/generality.md` § The rule. This WP applies it to
`src/rietx/sequential.py` (3 070 lines) and `src/rietx/multi.py` (2 482 lines).

**The maintainer's example.** "In a series there may be many types of discontinuity due to
phase transitions etc. We don't need to (and can't) cover all of them. It might be useful
to suggest a symmetry-mode refinement, but we shouldn't enforce a test by default." The
discontinuity test (`SEQUENTIAL_DISCONTINUITY`, 5× the median step and 3σ, ~lines
226–227) is DESIGN.md § Rules, 1's own example of the third kind: what a jump means depends
on facts outside the pattern (a transition, a sample shift, a beam dump), so it fails the
judgement ground. Since its threshold is its trigger, no diagnostic remains: the statistic
becomes a **record field with no threshold**, `SeriesResult.steps` (every step in esds,
largest first, under a name that asserts no jump), its explanation in `rietx.help` keyed to
the field, one line naming it in the trajectory block, and **no diagnostic** (the record
§ Demotion and *Attention is a cost* clause 1, ruled 2026-10-23 by WP-2037, reversing the
`info`-record shape ruled 2026-10-18; `2037-attention/examples.md` § 5 is the mock-up). The
explanation carries the reading: what a jump can be, and that a symmetry-mode refinement
separates the cases. The third review had put that reading in the skill's
`references/series.md`, because a suggestion inside the package needed a trigger; a field
with no threshold needs none. `SeriesResult.discontinuities`, the trajectory plot's shading
and `verify_discontinuities` all read the flagged pairs today, so each moves to the largest
steps or is ruled in the batch.

**The seats this WP lands in exist** (WP-2037, closed 2026-10-24). `rietx.help.RESULT_FIELD_HELP`
describes every field of `RefinementResult`, `StageResult`, `SeriesEntry` and `SeriesResult`
keyed `Type.field`, crossed both ways by `tests/test_help.py::test_every_result_field_has_an_entry`,
so `SeriesResult.steps` fails until its entry is written and `rietx.help.explain(…)` then answers
it. Every code row in `rietx._audit` carries `response`/`responds`/`scope` or sits on the
shrink-only `RESPONSE_BASELINE`: a code this WP keeps leaves that list with a response (one
level at every raise site), and a code given `response="warning"` adds a fire/silent pair to
`tests/silence.py`. `SeriesResult.summary(levels=…, deliverable="series")` and
`rx.diagnostics_summary(results)` read those responses. One cost is this WP's: with no
deliverable a `SEQUENTIAL_PERSISTENT_FINDING` row prints as one line,
`SEQUENTIAL_PERSISTENT_FINDING: warning under every purpose`, which no longer says *which*
per-pattern code persisted (tutorial 05, cells 19 and 34); a wrapper code's one-line form is
shaped when its row is tiered.

**What WP-2002 handed on** (closed 2026-10-23; its rows settled, so the holds inside one stage
are fixed ground here). Tier 2 names seven programs (GSAS-II, FullProf, TOPAS, RIETAN-FP,
BGMN, MAUD, EasyDiffraction; `docs/practice.md` holds each one's defaults by topic), and a row
resting on a program default names what each does. Two record fields reach a chain:
`StageResult.collapsed` (columns a stage restored and held, from all three runners) and the
Stephens seed's rows in `StageResult.seeded`; the joint runner seeds no Stephens block. Every
plan ends in a closing stage and a warm refit carries it (`_collapse` passes
`closing_window_tol`), 1.05-2.05× a single fit's time a pattern, its cost along a chain and its
effect on path dependence unmeasured (`closing_window_tol=None` is the bit-identical way back).
The **width twin hold** makes the carry policy matter: on CPD sample 1a-1h the chain carrying
the widths but not the scales averages Rwp 0.1282 against 0.1256 carrying everything and 0.1258
independent, a strict xfail in
`tests/test_acceptance_sequential.py::test_warm_start_iteration_cost_is_reported`; the
iteration saving stands (388 against 1218). The **held-out family** is the Nd₂Ru₂O₇ pair
(`tests/data/mg090*`), which no audit may use as evidence. Two of 2002's clash candidates
reach the chain (`2002-batch/clashes.md`): B16, `multi.py`'s parametric test holding at-bound
columns through `staged.bound_findings`, whose margin falls to 13/f if class B4 lands; and B7,
the 0.03-esd bound on `intermediate_ftol`, a one-fit bound whose chain effect is this WP's.

**The table's mechanics** (WP-2001). This WP's rows are those `_audit.WALKED` and
`_audit.DEFAULT_SEATS` map to 2003 (`sequential.py`, `multi.py`, `params/multi.py`;
`refine_sequential` and `SequentialRefinement.fit`, the latter a seat because
`refine_sequential` reaches its `reseed`, `refit`, `on_error` and `direction` defaults through
`**kw`), plus the codes and suggestion rows of the subsystem. Auditing a row gives it a tier
and evidence in place and deletes its line from `UNAUDITED_BASELINE`; `tests/test_audit_table.py`
fails until both are done. The walk sees module-level numbers and tuples of numbers only, so a
number in a dict, list or array is audited by hand. The series floor-reseed of an unsupported
moment (near the `SEQUENTIAL_MOMENT_HOLD` raise) has no record field, only that code's message,
so it has no action row yet; `SeriesEntry.rungs_raised` and `rungs_tried` do.

**The inventory**, keyed on `SeriesEntry` (`schemas/sequential.py`) fields `rung`,
`reseeded`, `rwp_fence` and on the constants:

- `RESEED_FACTOR = 1.25` (~line 168): Rwp above this multiple of the accepted-so-far median
  triggers a cold refit. No citation, no measurement in its comment; WP-1469 already
  carved an exception out of it (~lines 1682–1690). The second review proposed escalating
  on status alone (diverged or non-finite) with the Rwp fence opt-in. **A finding to
  measure here, not a decision taken at filing.**
- The rung ladder and quarantine (~lines 1677–1715, WP-1051): a rejected warm fit retried
  from colder starts, then `SEQUENTIAL_UNRECOVERED`, seeding no successor. Under the
  judgement ground this is kept unless a competent caller can be named who would let a
  diverged fit seed its successors (fourth review; the record § The rule names it as the
  case that flipped from contested to kept when visibility gave way to judgement). Rule 1
  also names it among the protections of expensive work ("seeds no successor from a
  diverged fit"). What
  is on trial is the *ladder*: its rungs, the order of colder starts and the point at
  which it gives up are choices, so tier them. Measure what the caller sees: does the
  returned `SeriesResult` show which pattern diverged and which were seeded from it? If
  not, that record field is added whatever the ruling.
- `DISCONTINUITY_FACTOR = 5.0` and `DISCONTINUITY_SIGMA = 3.0` (~lines 226–227): the
  threshold the removed code was keyed on. The walk enters both at `unaudited`; when the
  code goes, the constants go with it or are re-tiered as the trajectory field's own
  (the step size needs no threshold), so the baseline can shrink past them.
- `FIRST_RUNG_FACTOR = 3.0` (~line 218): measured bit-identical, 0 of 1030 and 0 of 392,
  with 2.3× margin; its docstring calls it a bet, since the budget truncates only a losing
  rung while a winning one stays cheaper than the budget. The answer-invariant class; the
  invariance test asserts the accepted values *and* the margin (every kept first rung
  under the budget), not a comment.
- `_better` / `_prefer` (~lines 1952–1959): which attempt is kept, by Rwp, with a truncated
  attempt ranked below any completed one. Keeping the best attempt is one of Rule 1's
  protections; what is on trial is the criterion that names the best, so tier it.
- `WIDTH_GROWTH_FACTOR = 3.0`, `WIDTH_GROWTH_GOF_FACTOR = 2.0`, `WIDTH_GROWTH_SIGMA = 3.0`
  (~lines 279–303): under `THRESHOLDS_VERSION`, which 2004 owns. Hand 2004 the rulings;
  do not bump the version here.
- `_floor_unsupported_moments` (~line 851, WP-1329): the moment-floor carry across
  patterns. Not in the first plan; the review found it.
- `direction="both"` and `verify_discontinuities` (~lines 1020–1024): opt-in, the caller
  asks. Classified, not audited; a row each at tier `caller` (2001).
- `SEQUENTIAL_PERSISTENT_FINDING` ("42 of 68"): a count across patterns, tier 1 as a
  statistic; whether it carries a verdict is the question.
- `multi.py`: the joint residual's own holds and its second builder of the extra
  components (root CLAUDE.md § extra_components names it as the miss). Its cell runaway
  resets and holds the phase's cell like the single runner's (`StageResult.cell_reset`), but
  `_cell_runaway_diagnostic(cell_runaway)` (~line 1632) never passes
  `refine._vars_driven_cell_escapes`, which the single runner folds into `CELL_RUNAWAY`, so a
  `vars.X`-driven escape goes unnamed in a joint fit (WP-2002, PR #1050; checked 2026-10-24).

**A chain is measured, never assumed.** Root CLAUDE.md: cumulative staging's bound holds
for one fit and is unbounded in a chain, both signs measured. So every family here is a
chain family: the Durham in-situ tutorials, the 13-pattern sub-onset ramp (the v1.3 row),
the ten-pattern warm series of v1.1, the corpus series cited by number. Three families is
the bar.

## Non-goals

- The holds inside one stage: 2002, already landed when this starts.
- `THRESHOLDS_VERSION` and the width-growth thresholds' version bump: 2004.
- The series panels of the GUI and `rietx watch`: a demoted code's row changes in
  `gui/src/lib/history.ts`'s `PLACES` only if a family is renamed, which this WP does not
  do.
- A new discontinuity classifier or a symmetry-mode suggestion engine: a follow-up WP if
  the batch wants one.

## Tasks

- [x] Inventory: one row per action and constant, with what it decides, what the caller
      sees without it, and whether it is opt-in or answer-invariant. `2003-batch/inventory.json`
      (2026-10-24): the 77 table rows 2003 owns (not 65: `SERIES_PATTERN_FAILED` and the
      joint fit's five codes, with their suggestion rows) and 34 row-less actions; task 3's
      question answered in `2003-batch/README.md`.
- [ ] Tier each row per part, with evidence. The `RESEED_FACTOR` question measured on
      three chain families with the fence on, off and status-only: patterns reseeded,
      accepted values that differ, and the cost in evaluations.
- [ ] Quarantine's record: does the returned `SeriesResult` name the pattern that
      diverged, the rung it reached, and the successors seeded from an earlier pattern
      instead? Quarantine is one of Rule 1's protections and stays; a protection records
      each time it acts, so a missing field is added. The ladder's rungs and give-up point
      are tiered as above. A rejected rung and `_verify_discontinuities`' cold refits each
      pay the automatic moment-angle profile interval (20-32 refits an angle, 2.6-16.7 s on
      fits of 0.2-1.2 s; `strategy/parameter_interval.attach_stationary_intervals`) on a
      result the chain discards: gate them with `_auto_intervals = False` until an attempt
      is accepted (WP-2002, PR #1050; no gate in `sequential.py` on 2026-10-24).
      Answered 2026-10-24 (`2003-batch/README.md` § Quarantine's record): the pattern and
      its rung are on the record; the successors seeded from an earlier pattern are not,
      nor is the moment-floor carry. Proposed fields: `SeriesEntry.seeded_from` (the
      index whose fitted state seeded this pattern's warm rungs, `None` on a cold-only
      pattern) and `SeriesEntry.floored` (the moment paths floored before its warm start,
      from `_chain`'s local `floored`). Each is an action row a name new to the table
      cannot enter at `unaudited`, so they land with the quarantine's ruling in the batch.
- [x] `FIRST_RUNG_FACTOR`'s invariance test (accepted values bit-identical with the bound
      on and off, on two chain families), replacing the comment's claim. 2026-10-24: the
      thermal ramp (`tests/test_sequential.py`) and the CPD chain (slow,
      `tests/test_acceptance_sequential.py`), both asserting the margin too. The row stays
      `unaudited`: the closing stage now hides a bitten first rung (clash table, below).
- [ ] The clash table: reseed × rung × `_prefer` × width growth × the moment carry, both
      orderings where order matters; plus the carry policy × the width twin hold, the
      closing stage × path dependence, and 2002's B7 and B16 (Context). Found 2026-10-24:
      the first-rung bound × the closing stage (a truncated warm stage the closing stage
      converges reads `converged`, so WP-1127's forced escalation never fires);
      `reseed=False` × the forced escalation (`sequential.py:1561`, `1569-1571`: a bitten
      first rung escalates against a switch the caller turned off, against `reseed`'s
      docstring); the closing stage × the fence (cpd-1b escalates with it, not without it).
- [ ] The batch to the maintainer, each brief opening with its stakes line (the record
      § The rule, 2026-10-20); rulings dated into the table.
- [ ] Approved demotions, each its own commit; `SEQUENTIAL_DISCONTINUITY` replaced by the
      `SeriesResult.steps` field and its help entry (no diagnostic), if the batch agrees; the
      release notes staged.
- [ ] Goldens re-pinned only if no further from reference. A series golden's first
      reference is the cold-fit chain, rietx's own result on the same data, so it
      verifies and does not validate (DESIGN.md § Rules, 2). Where a series member has a
      certified value or a second engine's answer, that reference is measured too and
      the handover says which each number was held to.
- [ ] Width-growth rulings handed to 2004 as an `### Inherited` entry there.
- [ ] Tests + PNGs; the fast count moved by exactly the tests added.
- [ ] Skill: none here. List each `references/series.md` row (5 308 words) that names a
      demoted verdict, for 2008 (DESIGN.md § Rules, 3; the record § Decisions, the
      skill's role).

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_audit_table.py -q          # no sequential.py/multi.py row at unaudited
.venv/bin/python -m pytest tests/test_sequential*.py tests/test_multi*.py -q
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m pytest -n auto --dist loadgroup                # once, final tree
```

The handover carries the three-family measurement for the reseed fence and the
quarantine, with the per-pattern table (WP-1124's rule: judged on the table, never a
summary).

## References

- `docs/milestones/generality.md`; WP-1051 (quarantine), 1127 (the first rung), 1016,
  1441, 1469 (the carve-out), 1329 (the moment carry), 1124 (the per-pattern table).
- Root CLAUDE.md § Series.

## Handover log

### 2026-10-24 — the inventory, the reseed fence measured on eight chain families, the first-rung invariance tests; eleven clear defaults tiered and nothing contested

Every decision a series makes between patterns is now listed: 77 rows the table already had (not the 65 the WP assumed) and 34 actions with no row, each with what it decides and what a caller would see without it. The Rwp fence that sends a bad warm fit back to colder starts carries real load on real data. On the CPD round-robin chain it alone rescues a pattern whose warm fit ended at 3.75× the fence with corundum's cell 5 % off and an 18° zero shift. A status-only fence, the second review's proposal, would have kept that fit. On the synthetic series the fence escalates 115 times for 4.3× the evaluations and moves no value past 0.0007 esd. That contrast is the reseed brief's stakes line. The first-rung budget is shown answer-invariant on two chains, but WP-2002's closing stage now hides a truncated first rung from the ladder, so WP-1127's safety escalation no longer fires; that and `reseed=False` escalating anyway are clash-table items, not fixed here. No contested row was tiered: the batch is next session's.

*Done.*
- Inherited pruned, eleven entries re-checked and folded into Context and Tasks (`9077375`).
- Task 1, the inventory (`f156c9e`): `2003-batch/inventory.json`, 111 entries (77 rowed, 34 row-less: 18 in `sequential.py`, 16 in the joint fit); `2003-batch/README.md` answers task 3's question. The 12 extra rows over the WP's 65 are `SERIES_PATTERN_FAILED` and the joint fit's five codes (`SIZE_NORMALISED_ACROSS_WAVELENGTHS`, three `PARAMETRIC_*`, `STAGE_FREED_NOTHING`), each with its suggestion row.
- Task 3 answered, not built: the pattern and its rung are on the record, the successors seeded from an earlier pattern are not, nor is the moment-floor carry. The two proposed fields are in task 3's text; they wait for the batch because an action row cannot enter the table at `unaudited`.
- Task 4 (`092991c`, `c4edce6`, `f494e2f`, `cc36121`): the invariance test on the thermal ramp (fast) and the CPD chain (slow), each asserting equality to the bit and the margin; `FIRST_RUNG_FACTOR`'s duplicated comment is one paragraph citing the tests, plus one on the closing stage.
- Eleven defaults tiered (`8b78f2c`, `c4edce6`, `db61420`): seven observation channels of the series seat `invariant`, shown by a new series section in `tests/test_answer_invariant_defaults.py` (made to fail once on purpose at `reseed_factor=0.5`); `backend` `caller` and `solver` tier 2 as on the single fit; `direction` and `verify_discontinuities` `caller`, with the judge's two wording corrections.
- Task 2's measurement half (`6ca9e2e`): `2003-batch/measure_reseed.py`, `reseed/*.json` (34 files), `reseed.md` (per-pattern tables, facts only).
- Code review (`/code-review high --fix`), seven findings: six fixed (`f494e2f`: one chain-answer helper comparing every number and code a chain reports, a ratio for every kept first rung including a `max_iter` one, the twin fixtures built by one function, a docstring); one declined, `measure_reseed.py` matching arms by list position, because no committed family recorded a `SeriesFailure`.
- Forward references (`2e15c3e`): WP-2036 (the closing stage on a warm chain and the BLAS threads under it; the new slow test's cost in `qpa-sample1`), WP-1317 (`planted_series/signals.json` lists 20 reseeds where the tree gives 49).

*Measured* (Linux x86-64, 4-core cloud container, worktree venv `[dev]`, compiled tier on).
- The reseed fence, per family (`reseed.md` holds the per-pattern tables). Arms: on (1.25), status-only (`reseed_factor=inf`), off (`reseed=False`), plus a cold independent reference.

  | family | on | status-only | off |
  |---|---|---|---|
  | CPD sample 1 (real; status/off on 2 patterns) | 1 escalated (1b), 0 reseeded; 987 evals | 1b kept at Rwp 0.7652, 1 220 esd from on; 703 evals | as status, 1b `SEQUENTIAL_RWP_OUTLIER` |
  | CPD, `closing_window_tol=None` | none escalated; 708 evals | bit-identical | bit-identical |
  | planted, 248 (synthetic) | 115 escalated, 49 reseeded; 11 790 evals | 1 escalated (budget-forced); 2 716 | as status |
  | planted null twin | none; 2 080 | bit-identical | bit-identical |
  | trigger, 10 (simulated) | none; 269 | bit-identical | bit-identical |
  | Cr₂WO₆ HB-2A pair (real neutron) | none; 873 | bit-identical | bit-identical |
  | tutorial 05 jump | none; 551 | bit-identical | bit-identical |
  | tutorial 05 broken | 1 reseeded (pattern 4); 157 | 0; 135 | as status |

  No arm quarantined anything on any family. Planted's 49 reseeds are near-ties (warm and cold Rwp within 7.6e-7 relative) and no value moved past 0.0007 esd. On CPD under on, the chain sits 7.05-14.2 esd from the independent fits, worst path a `lor_strain` each time; mean Rwp 0.12565 against 0.12580 independent; RMS |ΔW| 2.268 against 2.301 wt %. cpd-1b's warm rung came back `max_iter`, not `diverged`, so a status-only fence that also escalated on `max_iter` would have caught it.
- The first-rung bound: thermal ramp, three armed patterns at 1.0× the running maximum; CPD (from the bounded arm), 0.34-0.39×; factor 3.0. At `first_rung_factor=0.5` on the thermal ramp, patterns 4-6 kept a warm stage truncated at `max_iter` and closed by the closing stage, reading `converged`, within 8e-4 esd of the unbounded chain.
- Wall clock (context only): the CPD chain with the closing stage costs about an hour an arm here (the slow CPD test 1 h 17 min for two chains, one BLAS thread, beside the lane's runs), against 33.7 s quoted for `cpd-series`.
- Fast selection, the branch at `f494e2f` (before the matrix row), beside one single-test run of my own: 11 640 passed, 284 skipped, 27 xfailed, 3 failed, 44:57. The three: `test_validation_matrix.py::test_every_acceptance_test_has_a_matrix_row` (mine, fixed in `cc36121`), `test_audit_delta.py::test_the_reader_agrees_with_the_import` (the file was edited mid-run; passes alone), `test_examples.py::…[moment]` (Linux x86-64, recorded in WP-2036's Inherited, not this branch). Added: 8 fast tests (15.65 s locally: 10.09 s the six series channels, 3.82 s the thermal first-rung test, 1.73 s the recorded series), 1 slow (CPD). Main's count not measured (CI's job), so the +8 is by name in the junit file, not by subtraction.
- Full selection: not run, since the branch moves no measured number (tests, table data, docs, one comment).
- Lanes (`session_usage.py lanes`): inventory est 40, 122 requests, +$7.14; reseed-measure est 35, 328 requests, −$7.62; kept prune-inherited est 4. Trial row: re-read 0K, 17 main requests a lane, 36K left in main, actual/estimated 3.05, −1 %. Baseline replay, the selective policy (main > 150K and item ≥ 20): 4 sessions, +22 %.

*Gotchas.*
- The Durham host is denied by this environment's network policy, so the in-situ ZrMo₂O₈, WO₃ and ZrP₂O₇ series (`tests/local_data.py`) were not fetched; the 68-pattern ramp and the corpus series are not on disk here. The families above are what a cloud session has. The held-out Nd₂Ru₂O₇ pair was not used.
- Run any CPD chain with `OPENBLAS_NUM_THREADS=1` on Linux, or `leggauss` alone costs seconds a call (WP-2036's Inherited).
- `tests/test_sequential.py::chain_answer` is the one helper for "every number a chain reports"; both invariance files use it.
- `reseed=inf` is accepted unvalidated (`sequential.py:1028`) and turns every `rwp_fence` to inf, which also disables the discontinuity scan's above-fence drop (tutorial 05 broken gains a `SEQUENTIAL_DISCONTINUITY` under status-only).
- `SeriesEntry.n_iterations` omits the automatic profile-interval refits (Cr₂WO₆: 873 recorded, 1 146 run).

*Generality* (the `generality-review` judge on `_audit.py`'s eleven changed rows; its sections pasted unedited).

**Item 1: the seven observation and control defaults go to `invariant`**
`rietx.sequential.SequentialRefinement.fit:{cancel, events, label, on_result, progress, telemetry}` and `rietx.sequential.refine_sequential:history`

**holds.** The evidence for the tier is stronger: a bit-identity test runs the chain's real code path. The case against comes down to coverage gaps in that test, and none of the code I read turns a gap into a changed answer.

| Question | Author's answer (where) | What I found | Verdict |
|---|---|---|---|
| 1. What it decides | "an observation channel" (events, cancel, progress); "the run recorder, one run a job" (telemetry); "a run's name" (label); "a callback handed each kept fit" (on_result); "one history tree per pattern" (history). Each row's `evidence`, `_audit.py` series rows. | None of these picks a value. `telemetry=None` does do something unasked: it writes a run directory and adds a cancel token to every fit (`sequential.py:1261-1273`; the `_audit.py` docstring: "`telemetry=None` records the run"). That is a side effect, not an answer. `cancel` is a control channel, so calling it "an observation channel" is wrong only in wording. | agrees |
| 2. Ambiguity kind | `ambiguity=1` | Kind 1. No reading of the data is in question. | agrees |
| 3. Case against | none given | The test chain is three patterns: one cold fit and two warm first rungs (`tests/test_answer_invariant_defaults.py:146-149`). `FIRST_RUNG_SAMPLES` is 3, so the first-rung budget (WP-1127's cap on a warm fit's first attempt) never switches on. No rung escalates, no pattern is quarantined, and neither `direction="both"` nor `verify_discontinuities` runs. Those untested paths are exactly where `cancel` is read again (`sequential.py:1327, 1362, 1411`, and `except RefinementCancelled` at 1585) and where `history` changes file names (the `.cold`, `.verify` and `.backward` suffixes in `_history_spec`). Reading the code, none of those reads feeds a value or a choice of rung, so the gap is in the test, not in the claim. Smaller gaps: (a) the suite runs with `RIETX_TELEMETRY=0`, so in the `label` arm the label reaches nothing, and label with the recorder on is never run for a series (the single-fit file does run it, for `run_stage` and `refine`). (b) Nothing checks that the events file or the progress stream received anything, so a channel that `refine_sequential` silently dropped would still pass. (c) `history` is tested with `True` (trees in memory), never with a directory path. | minor coverage gaps |
| 4. Case for | The dispatch says the test compares "every kept value, esd, rung, `rungs_tried`, `reseeded`, `rwp_warm`, `rwp_fence`, Rwp, per-entry codes, series codes and `discontinuities`", and was made to fail once on purpose with `reseed_factor=0.5`. | Confirmed: `chain_answer` (added to `tests/test_sequential.py`) compares all of those. It does not compare `y_calc`, which the single-fit `_same` does. The `on_result` arm checks that the callback ran once per pattern (`seen == [0, 1, 2]`), and the telemetry arm checks that exactly one run directory was written, so those two arms cannot pass without the channel running. The rows match the single-fit precedent (`rietx.refine.refine:events`, `…:history` and the rest, `_audit.py:3164-3180`). | supports |
| 5. Tier and source | `invariant`, tested in `tests/test_answer_invariant_defaults.py` | Tests: `test_a_series_observed_is_the_series_unobserved[events,progress,cancel,label,on_result,history]` and `test_a_recorded_series_is_the_series_unrecorded` (telemetry). generality.md asks an invariant test to also assert its margin. A channel is not a bet like the first-rung budget, so equality is the margin, as in the single-fit rows. | holds |
| 6. Dataset families | none given | Not a threshold, so families do not apply. The one dataset is the synthetic thermal ramp (`tests/test_sequential.py` `_simulate`). | n/a |
| 7. Record that it fired | none given | No field is needed for a channel. Telemetry's record is its run directory (`meta.json`). History's record is `SeriesEntry.tree_id` / `node_id`. | adequate |

What would change the verdict: a channel arm on a chain that escalates or quarantines (the author's own `reseed_factor=0.5` chain would do) giving a different answer from the same chain with the channel off.

**Item 2: `rietx.sequential.refine_sequential:backend` goes to `caller`**

**holds.** The evidence for leaving it to the caller is stronger. It copies the single-fit row word for word in substance, and the chain adds no choice of its own inside the switch.

| Question | Author's answer (where) | What I found | Verdict |
|---|---|---|---|
| 1. What it decides | "each pattern's Refinement gets it unchanged (sequential.py:1765)" (row `evidence`) | Confirmed at `sequential.py:1765`. The constructor checks a non-numpy backend and refuses it when the optional package is missing (`:975-981`). | agrees |
| 2. Ambiguity kind | `ambiguity=1` | Kind 1. | agrees |
| 3. Case against | none given | none found. No competent refiner wants the package to choose a GPU or autodiff backend for them. | — |
| 4. Case for | "jax/torch/torch-mps need an extra no default install has, and agree with numpy only to fp tolerance" | Nothing new falls to the caller. One nuance for a chain: a floating-point difference can flip a reseed-fence verdict that sits near 1.25× the median Rwp (the fence sends a pattern back for a colder refit). A chain's choice of rung can then differ by backend, not only its last digits. That is not measured, and it is still the caller's choice. | — |
| 5. Tier and source | `caller`, citing `rietx.refine.refine:backend` | Both conditions hold. (1) The switch is asked for by name and its off state is `numpy`. (2) Inside it the package picks no number; the floating-point spread comes from the caller's choice of backend. This matches `_audit.py:3155`. | holds |
| 6. Dataset families | n/a | n/a | n/a |
| 7. Record that it fired | none given | `RefinementResult.provenance.backend` on each pattern's result (`schemas/results.py:1848`). I did not check whether `SeriesEntry` or `SeriesResult` carries it. | adequate |

What would change the verdict: a default path that passes a non-numpy backend.

**Item 3: `rietx.sequential.refine_sequential:solver` goes to tier 2**

**holds.** The evidence for the tier is stronger. It inherits the single fit's row, and the one dissenter named keeps it at tier 2 under the rule.

| Question | Author's answer (where) | What I found | Verdict |
|---|---|---|---|
| 1. What it decides | "handed to each pattern's Refinement unchanged (sequential.py:1765-1766)" | Confirmed. It sets bounded Levenberg-Marquardt (damped least squares, with an exact set of parameters active at a bound), with TRF (a trust-region solver) available by name. | agrees |
| 2. Ambiguity kind | `ambiguity=1` | Kind 1, as for the single fit. | agrees |
| 3. Case against | "FullProf dissents, Gauss-Newton with relaxation factors" | Matches `docs/practice.md:180`. Under generality.md tier 2, a dissenting program does not move a default off tier 2. Nothing in the change says what any program's *sequential* mode defaults to. | dissent named |
| 4. Case for | "Marquardt-damped in six" | `docs/practice.md:180`: GSAS-II, TOPAS, RIETAN-FP, MAUD, EasyDiffraction, and BGMN (regularised Gauss-Newton). | supports |
| 5. Tier and source | tier 2; "GSAS-II 5.8.4 GSASIImath.HessianLSQ is Marquardt-damped (checked)" | I checked this in the repository's practice.md only, not in GSAS-II's source. That each program's sequential mode uses the same solver as its single fit is not given; I believe it is so for GSAS-II, from memory only, not checked. | holds |
| 6. Dataset families | n/a | No threshold. | n/a |
| 7. Record that it fired | none given | `RefinementResult.provenance.solver` (`schemas/results.py:1848`). | adequate |

What would change the verdict: nothing under the current rule. Even a program whose sequential mode defaults to a different solver would only be one more dissenter.

**Item 4: `rietx.sequential.SequentialRefinement.fit:direction` goes to `caller`**

**holds, but the case for acting is stronger than the row admits, and the row cites none of it.** `direction="both"` runs the chain a second time in reverse and flags parameters whose two trajectories disagree. The caller-class conditions are met, because `'forward'` moves no reported value; it only leaves that check out.

| Question | Author's answer (where) | What I found | Verdict |
|---|---|---|---|
| 1. What the caller must now decide | "its off default walks one chain" (row `evidence`) | Under `'both'` the reported entries are still the forward ones (`sequential.py:1076`). So the default changes no value; it leaves out the path-dependence check. The caller decides whether to pay for a second chain. | agrees |
| 2. Ambiguity kind | `ambiguity=1` | The switch is kind 1. What it opens up (path dependence) is reported as a statistic, under `SEQUENTIAL_PATH_DEPENDENT`. | agrees |
| 3. Case against defaulting to `'both'` | none given | Cost: a whole extra chain, at least doubling the wall clock; no figure is in the change. Value: `docs/skill/rietx/references/series.md:136-150` says agreement both ways is not evidence of correctness (0 of 35 patterns disagreed on a physically wrong construction), and the largest flags it measured were axis relabellings (81.5σ in `Fddd`). So a default `'both'` would issue codes that need careful reading. Program practice: `docs/practice.md` has no entry on sequential refinement. I recall GSAS-II's reverse-order option being off by default, but I did not check it. | real, unmeasured |
| 4. Case for defaulting to `'both'` | none given | The package's own words: series.md:131-135, "For any trajectory you intend to publish, run it — it is the only check that separates a measurement from an ordering artefact"; judging.md:418-419, "a one-way chain has not looked"; the root CLAUDE.md says the same. So every caller who publishes a trajectory pays a full rerun of the chain. That cost is not measured. The default is visible: `SeriesResult.direction` (`schemas/sequential.py:699`), and the series summary prints "ordering artefact: NOT measured — this chain ran forward only…" (`schemas/sequential.py:1325-1329`). The row should cite both. | strong, uncited |
| 5. Tier and source | `caller`; "the GUI's series panel defaults to 'forward' (gui/series.py:80) and passes the user's choice (gui/session.py:1710), and no other default path sets it (searched 2026-10-24)" | Checked: `gui/series.py:77-82`, `gui/session.py:1710`, and a grep of `src/rietx` finds no other caller. Condition 2 holds: `PATH_DEPENDENCE_SIGMA` (3.0), `NOISE_FLOOR_REL` (1e-9) and `SEQUENTIAL_PATH_DEPENDENT` have their own rows, still `unaudited`. That matches how WP-2002 treated TRF's tolerances. A side finding: the GUI's `DEFAULTS` dict holds its own copy of `'forward'`. That is a second seat for this default, which the table cannot see because the value sits in a dict. | holds |
| 6. Dataset families | n/a | n/a | n/a |
| 7. Record that it fired | none given | `SeriesResult.direction`, `SeriesResult.backward` and `SEQUENTIAL_PATH_CHECK_INCOMPLETE`. | adequate |

What would change the verdict: a measurement, on the suites' chain families, of how often a forward-only trajectory moves by more than its esds when run both ways, set against the cost of the second chain in evaluations.

**Item 5: `rietx.sequential.SequentialRefinement.fit:verify_discontinuities` goes to `caller`**

**holds for now.** The case for acting is real and the row does not state it. The row will need re-reading once WP-2003's own demotion of `SEQUENTIAL_DISCONTINUITY` (the code that flags a large jump between neighbouring patterns) lands.

| Question | Author's answer (where) | What I found | Verdict |
|---|---|---|---|
| 1. What the caller must now decide | "a cold refit of each flagged pair" (row `evidence`) | Whether to refit each flagged pair of patterns cold and independently, and record the cold step as a signed ratio of the chain's step (`sequential.py:1888-1892`). | agrees |
| 2. Ambiguity kind | `ambiguity=1` | Kind 1 for the switch. It adds a second number to a kind-3 statistic and no threshold. | agrees |
| 3. Case against defaulting on | none given | `sequential.py:1117-1121`: a cold fit is "roughly triple a warm one", and "a series flagging s steps pays up to 2s of them". The WP's task list adds an ungated moment-angle interval (an automatic profile interval on magnetic moment angles) on each cold refit: 20-32 refits an angle, 2.6-16.7 s on fits of 0.2-1.2 s. | real |
| 4. Case for defaulting on | none given | `sequential.py:1115`: "It is the check the diagnostic's own suggestion asks the reader for, run automatically"; `help.py:3719` points the reader at it. Measured "~5 %" on the 68-pattern thermal ramp with four flagged steps (`:1122-1124`, WP-1305), on one dataset family. Leaving it off means the caller refits the pairs by hand or reruns. The docstring's "not cheap" and its own "~5 %" pull opposite ways. | real, uncited |
| 5. Tier and source | `caller`; "no default path sets it, the GUI included (searched 2026-10-24)" | Confirmed by grep: nothing outside `sequential.py` passes it. Condition 2 holds: "no fitted value, entry, rung or median in the reported chain moves" (`:1126-1130`). The row calls what it adds "the verdict added to SEQUENTIAL_DISCONTINUITY", but the code adds a ratio and a reading with no threshold ("near 1.0 … near 0", `:1892-1900`). That is not a verdict, and the row understates its own case. Which pairs get refitted is set by `DISCONTINUITY_FACTOR` 5.0 and `DISCONTINUITY_SIGMA` 3.0, both `unaudited`. The WP's own plan removes that code for `SeriesResult.steps`, a field with no threshold, and says `verify_discontinuities` "moves to the largest steps or is ruled in the batch". Whatever then picks which steps get refitted is a package number inside the switch, and it needs its own row. | holds now |
| 6. Dataset families | n/a | The 5 % cost figure comes from one family. | n/a |
| 7. Record that it fired | none given | `Diagnostic.value` and the message on `SEQUENTIAL_DISCONTINUITY`, plus the `<label>.verify` histories. No result field. Once the code is removed, the ratio needs a new home. | adequate now, orphaned after the demotion |

What would change the verdict: the batch's ruling on `SEQUENTIAL_DISCONTINUITY`. If refitting then picks steps by a package-set count or cutoff, that number needs a row before this row stays `caller`.

**Item 6: eleven names removed from `UNAUDITED_BASELINE`**

**holds.** The eleven names removed are exactly the eleven rows tiered above (backend, solver, history, and the eight `fit:` defaults). Nothing was added to `UNAUDITED_BASELINE`, `OTHER_RECORD_FIELDS`, `NOT_WALKED`, `WALKED` or `DEFAULT_SEATS`. A removal from a list that only shrinks needs no reason. `tests/test_audit_table.py` holds the list equal to the tiers; I did not run it.

What would change the verdict: a name removed whose row is still `unaudited`.

**Second trigger: the findings in the inventory (comment only, not edits)**

- **`reseed=False` still escalates.** The `reseed` docstring (`sequential.py:1077-1083`) says "Switching it off leaves each pattern with its first rung". But `forced` (`:1561`, `:1569-1571`) sends a first rung cut short by the budget to the next rung anyway. So the package acts against a switch the caller turned off. It is visible in `rungs_tried`, but the docstring contradicts the code. This belongs in the `reseed` row's batch brief, and the docstring needs fixing. No new row is needed, since `reseed` has one.
- **The closing stage can hide a budget cut.** If `result.status` reports the closing stage's verdict (`:1603`), a first rung cut by the budget and followed by a converged closing stage is not counted as truncated. Then nothing forces an escalation, and `_prefer` (which ranks a truncated attempt below a completed one) does not rank it down. The budget could then keep a fit that was cut short, which is exactly what `FIRST_RUNG_FACTOR`'s invariance claim rules out. Both new tests assert `max(ratios) < FIRST_RUNG_FACTOR`, meaning the budget never bit, so they cannot see this case. I did not check whether `_bounded_plan`'s cap reaches the closing stage. This should be settled before `FIRST_RUNG_FACTOR` is tiered `invariant`.
- **Quarantine successors and the moment-floor carry** (the floor reset applied to an unsupported magnetic moment before it seeds the next pattern) have no record field. An action row is keyed on its field, so holding them out of the table until WP-2003's task 3 adds the field is correct.

Author's answers: items 4 and 5's wording corrections are applied (`db61420`); item 1's coverage gaps are accepted as gaps (the escalating `reseed_factor=0.5` chain is the arm to add if a channel is ever suspected); `FIRST_RUNG_FACTOR` is deliberately left `unaudited` for the reason the judge gives.

*Next*, in order:
1. Tier the remaining 66 rowed entries and give the 34 row-less ones a row or a reason, working from `inventory.json` (task 2), the reseed fence first, since its stakes line now exists: the fence carried load on the one real chain where it acted, and cost 4.3× for nothing on a synthetic one.
2. The clash table (task 5), with the three clashes found here as its first rows: the bound × the closing stage, `reseed=False` × the forced escalation, the closing stage × the fence.
3. The batch (task 6), one brief per class, with task 3's two fields and the `reseed` docstring fix in the quarantine's and the fence's briefs.
4. After the rulings: tasks 3 and 7 (the fields, the demotions with `SeriesResult.steps`), then the width-growth hand-off to 2004.

- **2026-10-21** — the repair itself: WP-2019's session, started under this
  WP's `repair first` flag, wrote the reconstructed entry below (f036bf9, on
  #1095's branch). No work on this WP's tasks, and Next is unchanged.
- **2026-10-20** (reconstructed post hoc, 2026-10-21, from 5c88100 / #1084) — a
  process edit, not work on this WP's tasks: the brief this WP sends the maintainer now
  opens with a stakes line, and a measured-consequence column was weighed and declined.
  - **What the commit shows.** `docs/milestones/generality.md` § The rule gains the
    paragraph "A brief opens with its stakes": the reported quantity the action can move,
    the case on disk and its distance from reference, the dissenter or `none found`;
    context, never a filter. A kept guard no ordinary fit reaches is kept on an injected
    case its row names (`test_cell_runaway_safety`'s escape for the cell clamp). § Decisions
    gains the declined consequence axis with its three reasons. This file's and 2004's
    batch task each carry the stakes line.
  - **What it does not show.** The session's branch carried this one commit and no
    handover entry; the record names a planning session and the maintainer's note of
    that date as the source. No checklist item moved, and no test or count.
  - **Next** is unchanged: the inventory, after 2002's holds settle.
- **2026-10-18** — created, from the milestone's opening session. 1317 (the series
  scrubber) and 1325 (parametric series) are open and adjacent; neither owns the fences,
  and this WP changes no view.

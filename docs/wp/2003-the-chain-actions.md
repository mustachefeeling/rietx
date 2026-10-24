# WP-2003 — The chain actions: what a series decides between patterns

Milestone: generality · Status: 🔄 2026-10-24 — claimed by @yue-here
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

- [ ] Inventory: one row per action and constant, with what it decides, what the caller
      sees without it, and whether it is opt-in or answer-invariant.
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
- [ ] `FIRST_RUNG_FACTOR`'s invariance test (accepted values bit-identical with the bound
      on and off, on two chain families), replacing the comment's claim.
- [ ] The clash table: reseed × rung × `_prefer` × width growth × the moment carry, both
      orderings where order matters; plus the carry policy × the width twin hold, the
      closing stage × path dependence, and 2002's B7 and B16 (Context).
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

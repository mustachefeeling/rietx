# WP-2003 — The chain actions: what a series decides between patterns

Milestone: generality · Status: ⬜
Track: The audits
Depends on: 2002
Priority: P2 2026-10-18 — the seam the maintainer's own example (a series discontinuity) lives in; waits on 2002's settled holds

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
judgement ground. Since its threshold is its trigger, the code becomes an `info` record
with no threshold (the record § Demotion, ruled 2026-10-18). On every series it states each
parameter's largest step as a multiple of its typical step, largest first, under a name
that asserts no jump. Its explanation carries the reading: what a jump can be, and that a
symmetry-mode refinement separates the cases. The third review had put that reading in the
skill's `references/series.md`, because a suggestion inside the package needed a trigger;
a record with no threshold needs none. `SeriesResult.discontinuities`, the trajectory
plot's shading and `verify_discontinuities` all read the flagged pairs today, so each
moves to the largest steps or is ruled in the batch.

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
  components (root CLAUDE.md § extra_components names it as the miss).

**A chain is measured, never assumed.** Root CLAUDE.md: cumulative staging's bound holds
for one fit and is unbounded in a chain, both signs measured. So every family here is a
chain family: the Durham in-situ tutorials, the 13-pattern sub-onset ramp (the v1.3 row),
the ten-pattern warm series of v1.1, the corpus series cited by number. Three families is
the bar.

### Inherited

- **From WP-2002 (2026-10-21, 4th session): tier 2 names seven programs.** `docs/milestones/generality.md` § The rule's tier 2 now reads "by default in an established Rietveld program": GSAS-II, FullProf, TOPAS, RIETAN-FP, BGMN, MAUD and EasyDiffraction, the list rietx-bench runs (the maintainer's instruction). A row resting on a program default names the programs it checked and what each does; a program doing otherwise by default is a dissenter, one without the feature is neither. What each does on peak windows, staging, roughness starts, width limits, dispersion, solver, mode and background seed is in `docs/wp/2002-batch/practice.md`; where each program's manual or source sits is in the maintainer's memory (`foreign-code-sources-on-disk`), and rietx-bench's `tools/` holds BGMN, MAUD, RIETAN-FP and EasyDiffraction's environment beside GSAS-II and FullProf.
- **From WP-2002 (2026-10-20, PR #1050): a series pays the automatic moment-angle interval on fits it discards.** A moment angle the stationary-angle test leaves out of the covariance now gets its profile interval after every single-pattern fit (`strategy/parameter_interval.attach_stationary_intervals`, gated by `Refinement._auto_intervals`). Each pattern of a chain computes its own, and so do rejected ladder rungs and `_verify_discontinuities`' cold refits, whose results the chain throws away: 20-32 refits an angle, 2.6-16.7 s on test fits of 0.2-1.2 s. Gate them (set `_auto_intervals = False` on an attempt until it is accepted) when auditing the rungs.
- **From WP-2002 (2026-10-20, PR #1050): the joint runner names no `vars.X`-driven cell escape.** `multi.py` (~line 1480, `_cell_runaway_diagnostic(cell_runaway)`) never calls `refine._vars_driven_cell_escapes`, which the single runner folds into `CELL_RUNAWAY`. The cell runaway itself now resets the phase's cell to the stage start and holds it in both runners (`StageResult.cell_reset`).
- **From WP-2001 (2026-10-19, PR #1047).** The table is `src/rietx/_audit.py`; this WP's rows are the ones `_audit.WALKED` and `_audit.DEFAULT_SEATS` map to 2003, plus the codes and suggestion rows of its subsystem. Auditing a row means giving it a tier and evidence in place and deleting its line from `UNAUDITED_BASELINE`; `tests/test_audit_table.py` fails until both are done. The walk sees module-level numbers and tuples of numbers only, so a number held in a dict, list or array is audited here by hand. From the generality judge's first run: the series floor-reseed of an unsupported moment (`sequential.py`, near the `SEQUENTIAL_MOMENT_HOLD` raise) has no record field, only that code's message, so it has no action row; `SeriesEntry.rungs_raised` and `rungs_tried` now do. `SequentialRefinement.fit` is a seat, since `refine_sequential` reaches its `reseed`, `refit`, `on_error` and `direction` defaults through `**kw`.

- **From WP-2002 (2026-10-19, PR #1050).** 2002 named the held-out family at its open: the Nd₂Ru₂O₇ pair (`tests/data/mg090*`), which no audit may use as evidence. Two of 2002's clash candidates reach the chain (`2002-batch/clashes.md`): `multi.py`'s parametric test holds at-bound columns through `staged.bound_findings`, whose esd threshold carries the Bérar-Lelann factor, so its margin falls to 13/f if 2002's batch class B4 lands (B16). The 0.03-esd bound on `intermediate_ftol` is a one-fit bound, and a chain's effect is yours (B7).

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
      are tiered as above.
- [ ] `FIRST_RUNG_FACTOR`'s invariance test (accepted values bit-identical with the bound
      on and off, on two chain families), replacing the comment's claim.
- [ ] The clash table: reseed × rung × `_prefer` × width growth × the moment carry, both
      orderings where order matters.
- [ ] The batch to the maintainer, each brief opening with its stakes line (the record
      § The rule, 2026-10-20); rulings dated into the table.
- [ ] Approved demotions, each its own commit; `SEQUENTIAL_DISCONTINUITY` replaced by the
      `info` record of the largest steps, if the batch agrees; the release notes staged.
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

- **2026-10-20** — (reconstructed post hoc, from 5c8810091; the session was a claude.ai/code one and left no entry). The milestone record's rule gained a paragraph: each class's brief to the maintainer now opens with its stakes, meaning the reported quantity the action can move, the case on disk and its distance from reference, and the dissenting caller named or `none found`. That line is context for the ruling and never a filter. A kept guard that the ordinary fits never reach names its injected case. The record also dates a decision not to add a consequence column, with three reasons the commit message does not restate. This WP's batch item and 2004's now carry the stakes line. No code, test or tier changed, and this WP stays unstarted.
- **2026-10-18** — created, from the milestone's opening session. 1317 (the series
  scrubber) and 1325 (parametric series) are open and adjacent; neither owns the fences,
  and this WP changes no view.

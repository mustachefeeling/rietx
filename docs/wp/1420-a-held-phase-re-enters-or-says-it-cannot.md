# WP-1420 — a held phase re-enters, or the chain says it cannot

Milestone: unscheduled · Status: ⬜
Depends on: — (1301 shipped, the hold this is about; 1333 soft, the same
chain's other silent shape; 1342 soft, the freeze's blind tie; 1419 soft,
the metric symmetry point a probe needs)
Priority: P2 2026-09-23 — a held phase stays out of every later pattern and the chain says nothing, on the series path

## Goal

A phase that WP-1301 held in one pattern of a series and that the data
support in a later one gets back in. Where the chain cannot get it back in,
the series result says so, at the pattern where the hold stopped being
right. A subgroup seeded at its parent's identity point is named as the
case the hold cannot judge on the data's authority.

## Context

Issue #267 (2026-09-05), a design proposal with a fully synthetic
reproduction: an eight-pattern series through `SequentialRefinement`, both
directions, defaults, run at three fractions. Read against the tree at
`28429810`: the `prepare` hook, `on_result`, `first_rung_factor`,
`RESEED_FACTOR = 1.25`, the `warm`/`warm_staged`/`cold` ladder with
`_prefer`, `StageResult.held`, `cell_window` and
`PHASE_SUPPORT_SIGMA = 1.0` are all as the issue quotes them.

**The hold's escape route.** WP-1301 holds every free structural path of
a phase below 1σ support and never its scale, "the one direction that is
not flat, and the only way the phase can come back" (`refine.py`, the
hold's docstring). Release is tested where the frozen structure is right
(`tests/test_held_phase.py::test_the_phase_is_refined_in_the_pattern_where_it_appears`,
CaF₂ at its true cell). The issue measures the route where the frozen
structure is *collinear* with a supported phase.

**The measurement.** Cu (`F m -3 m`) throughout; a tetragonal subgroup
(`I 4/m m m`, same atom, fcc → bct) appears at p004 at a fraction f of the
parent's scale with c/(a√2) − 1 = +6.0e-3. The subgroup is seeded at the
group–subgroup identity point at 2 % of the parent's scale, `carry=("*",)`,
`direction="both"`, ladder on.

| f | forward | backward |
|---|---|---|
| 0.40 | p004 deadlocked at 1.26× the running median; the 1.25× fence fired and `warm_staged` rescued it (16σ, tet +6.0) | cold start at p007 fell to the wrong sign (tet −8.0, `max_iter`), carried down p006–p004 |
| 0.25 | p004 deadlocked at 1.11×, under the fence; p005's first-rung budget forced `warm_staged` (1.3σ); p006 role swap, subgroup 332σ, parent cell jumped 0.011 Å (`SEQUENTIAL_DISCONTINUITY` on `phases.0.cell.*`) | correct: found at the cold start, carried down, held at p003 |
| 0.15 | p004 deadlocked at 1.03×; p005–p007 released into the wrong basin (tet −6.7) | cold start found the phase absent (0.00σ, held) and carried "absent" through all eight (`max_iter` ×7); `PHASE_UNCONSTRAINED` 5 of 8 |

The forward chain fails at every fraction, three ways. The backward chain
fails at two of three. "Absent everywhere one way, present the other",
which the reporter had seen from a hand-rolled chain on real data,
reproduces from the package's own chain with its ladder on.

**The mechanism, as far as measured.** At the identity point every
subgroup line sits under a parent line, so its support is a coordinate
along the two-scale ridge and the hold decides on that coordinate. At
re-entry the free scale's gradient is what the parent leaves in the
residual, about zero where the parent's model already carries the unsplit
intensity. That is the deadlock. When the scale does climb, release happens
at the identity point, a saddle of the symmetry-breaking direction, and
which sign it falls to is set by nothing in the data: three of the runs
above fell to the wrong sign with a "significant" scale (5–16σ) and an Rwp
10–15 % above the right basin. The fence is a symptom threshold. It
reopened the route at 1.26× and stayed shut at 1.11× and 1.03×. Nothing in
the chain reads the held state itself.

**What user code can do today.** `on_result` runs after each accepted
pattern with the full `RefinementResult`, before the next pattern's
`prepare`, so a re-entry policy is expressible as a closure over the
previous result. The issue measured one (re-seed the held phase's cell off
the identity point at 10 % of the parent's scale): worse than the ladder at
0.40, no better at 0.25 and 0.15. Three things a closure cannot do: probe
and keep the best, since a reseed is unconditional for that pattern; know
the sign; or tell "absent, correctly frozen" from "present but
unreachable", which look identical in the previous result.

**The framing that survives.** A re-entry attempt is a bet, WP-1127's word
for the collapsed first rung, and the chain already has the machinery for
bets: the ladder with `_prefer`. The rungs vary the plan and the starting
*state*. None varies the starting *structure* of a held phase.

**Four options, from the issue,** each checked against WP-1051's rule for a
trigger (a property of this pattern's own fit, readable when it finishes,
plausibly fixed by a different starting point):

1. **A re-entry probe rung.** Trigger: a phase held in this pattern and in
   the previous accepted one, and this pattern's Rwp risen against the
   accepted median by a factor well under `RESEED_FACTOR`. Probe: the held
   phase re-seeded off its metric symmetry point in both signs of its
   symmetry-breaking DOFs, at a scale that clears support; keep the best by
   `_prefer`. Passes all three clauses. Cost: two extra fits on
   held-and-rising patterns only, zero on a chain with no held phase. The
   0.40 rescue already is this, minus the sign and minus the lower
   threshold.
2. **A lower, held-only fence.** Same trigger, escalate to `warm_staged`
   at about 1.05× when a phase is held. Cheapest. Would have fired at 0.25
   and stayed shut at 0.15, and cannot fix the sign.
3. **Report only.** A series-level finding when a phase is held for a run
   of patterns and the chain's Rwp trend rises across it, with the ± two-seed
   check documented as the user's job. Leaves the deadlock in place.
4. **Documentation only.** `using/series.md` and the skill's
   `references/series.md` state that a subgroup seeded at its identity point
   is collinear with its parent and cannot be held or released on the
   data's authority, that the seed is a saddle, and that both signs must be
   tried. Owed whatever else is chosen.

**Triage recommendation (2026-09-15):** 4 and 3 first, then 1 on a measured
trigger. The docs are owed. The finding costs nothing, passes 1051's rule,
and is the package's "evidence, not verdicts" shape (1043). Option 1 is the
only one that fixes the sign, and the ladder has the seam for it, but its
trigger threshold and its two-fit cost have one synthetic series behind
them. Before it lands: the trigger measured on a real held-phase series
(the issue's own hand-rolled case, or 1329's onset data once 1327 is in),
and the threshold set with 1127's margin rule, a win/lose gap and not a
number picked from three runs. One design note for option 1: "re-seeded
off its metric symmetry point" needs that point found from the child cell
alone. That is the invariant metric subspace #293 and 1419 describe, so
the probe's seed is 1419's `MetricConstraints` read the other way.
Option 2 is dominated by 1 and is not recommended on its own.

Two neighbours. 1333 is the same chain's other silent shape (a pattern that
died reading as passed); this one is a pattern that converged to the wrong
basin reading as right. 1342 is the hold's blind tie, the freeze one rank
down.

### Inherited

**From WP-1333 (2026-09-23): the ramp reproduction's wall-clock guard is a
load sensor.** `tests/test_held_phase.py::test_the_ramp_reproduction_no_longer_runs_away`
failed in WP-1333's full run (`[dev]`, Linux x86-64, 4 cores, 1:24:44). It
passed alone, and in that session's slow-series run. Measured serially, the
chain takes 9.1 s compiled and 11.2 s on the numpy path, against its 60 s
`RAMP_RUNAWAY_GUARD_S`, with 1609 and 1659 iterations against the 2164 bar. So
every deterministic assertion holds on both paths, and only the guard can
move with load, on a run whose fixtures were up to 3.4× slower than CI's
nightly. About 6× margin is under what `tests/CLAUDE.md` § Budgets calls
several times, and this WP will add rows to that file, so it is the one to
widen the guard or move the claim to the iteration count, which already
carries it.

**From WP-1333 (2026-09-22).** The chain now says one of this WP's silences
out loud. `SEQUENTIAL_PATH_CHECK_INCOMPLETE` at `info` names every path some
chain measured that no pattern could judge in the `direction="both"`
comparison, and a phase held throughout one direction is exactly that case
(issue #269). So "the chain says it cannot" has a first member for held paths
under `"both"`. It says nothing about re-entry within one direction, which
stays this WP's. Two rules came with it that a re-entry diagnostic should
reuse. A path is named only if *some* chain measured it, and only if the two
chains differ above `_noise_floor`. Without both it fired on every clean
series (a tie row off a never-freed source, `profile.y` on its floor). And a
rung whose fit raises now escalates the ladder (`SeriesEntry.rungs_raised`),
so a held phase that makes a warm rung raise is rescued cold, not failed.

**From WP-1342 (2026-09-19).** A held path is now a **column**, and it need
not be a phase path at all: a caller's `vars.X` driving that cell is what the
freeze stops, so `StageResult.held` can read `vars.caf2_a` where this WP
expects `phases.1.cell.a`. Three consequences for the re-entry question.
`_released_phases` is handed that column list, so whatever this WP builds on
top of it inherits the same shape. The phase behind a held column is found
through `StageResult.held_reach`, which maps each held column to the tied
entries it also stopped — `_held_by_phase` is the worked example. And a column
reaching a *supported* phase as well as an unsupported one is never held
(`refine._only_moves`), so the "cannot get back in" case this WP is about
cannot arise for a shared column; it is already free.

**From WP-1435 (closed 2026-09-18), which put a second hold on the same
object.** There are now two holds on a `Refinement` and they mean opposite
things, so name them carefully in anything this WP writes.

- `Refinement._held` is WP-1301's and this WP's subject: the *package's*
  reading of what one stage's data can see, lifted at the start of the next
  stage, recorded on `StageResult.held`/`.released`.
- `Refinement._user_holds` is the *caller's* declaration that a parameter
  does not move whatever a plan asks, lifted only by `unhold`, carried on
  `RefinementState.holds` and recorded on `StageResult.blocked_by_hold`.
  It was deliberately **not** named `_holds`, which would have sat one letter
  from `_held` in the same method bodies meaning the reverse.

They never overlap today, and the reason is worth keeping true: WP-1301's
`_hold_unsupported_phases` only holds paths that are *free*, and a
user-held path is never free. A re-entry mechanism that lifts a hold has to
respect that split, because lifting a user hold is not this WP's to do.

## Non-goals

- Per-iteration re-anchoring (1301's stated non-goal).
- `PHASE_SUPPORT_SIGMA`, or the package deciding whether a phase is present.
- Passing `phase_support` or `held` into `prepare`: the previous result is
  already reachable through `on_result`, and the plumbing buys convenience
  only.
- A general sign-of-distortion search. Two signs of a one-parameter
  symmetry-breaking DOF is the scope; a higher-dimensional order-parameter
  space is 1418's M-7.

## Tasks

- [ ] Docs: the collinear-seed paragraph in `using/series.md` and the
      `references/series.md` row (Measured: issue #267's three fractions),
      paid for by a cut if the reference is at its cap.
- [ ] The series-level finding: a phase held over a run of patterns with the
      chain's Rwp rising across the run, naming the pattern where the hold
      stopped being right; `GuardFinding` constructor, `help.py` entry,
      `references/diagnostics.md` row.
- [ ] Measure the probe's trigger on a real held-phase series and on the
      issue's synthetic one at the three fractions; the table in the
      handover sets the threshold by 1127's margin rule.
- [ ] The probe rung, if the table supports it: both signs, `_prefer` keeps
      the best, the seed off the metric symmetry point, `entry.rung` records
      it; goldens bit-identical on every chain with no held phase.
- [ ] Tests: the issue's synthetic series at f = 0.15, 0.25, 0.40 in both
      directions, asserting the finding fires at the right pattern and, with
      the rung, that the forward chain reaches the right basin at all three.
      Obs/calc/diff PNGs to `tests/output/`.

## Acceptance

The synthetic series at f = 0.15 forward, the worst case, ends with the
subgroup in the right basin or with the finding naming p004; every shipped
series golden is bit-identical.

```sh
.venv/bin/python -m pytest tests/test_held_phase.py tests/test_sequential.py -q
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
```

## References

- Issue #267 (2026-09-05), with its `repro_deadlock.py` and outputs at three
  fractions.
- WP-1301 (the hold), WP-1051 (the trigger rule), WP-1127 (the first rung is
  a bet), WP-1043 (never a confident singleton), WP-1333, WP-1342, WP-1419.

## Handover log

- **2026-09-15** — created, from the 2026-09-15 issue triage (issue #267).
  Added in the round's second pass: the first pass read the issue and
  placed nothing. Checked against the tree: every hook, constant and rung
  the issue names exists as quoted; the hold's own docstring calls the
  scale the way a phase comes back, which is the route the issue measures
  shut. Recommendation recorded: docs and the finding first, the probe rung
  on a measured trigger.

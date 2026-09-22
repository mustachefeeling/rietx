# WP-1333 — a series survives one pattern, and says which one it lost

Milestone: unscheduled · Status: 🔄 2026-09-22 — seven of eight tasks landed in a cloud session; the coordinate carry remains, and the branch waits on a push from a local clone (the session could not reach GitHub)
Depends on: — (1317 soft: #218's forward-pass exposure is the sibling ask)
Priority: P1 2026-09-23 — a chain of hundreds lost to one raise, and a check that died reading as passed

## Goal

A raise on one pattern no longer destroys a chain of hundreds. A failed
pattern is marked, the last good warm state carries forward, and the run
returns what it measured. An esd that cannot be computed arrives as `None`
with a diagnostic, the way the schema already says it may. And a
path-dependence check that never ran is distinguishable from one that passed.

## Context

Two issues from the 2026-09-01 benchmarking campaign, filed separately and
sharing one mechanism: **`SequentialRefinement.fit()` is all-or-nothing, and
the things that raise are not the answer.**

**Issue #224 — the enumerator refuses a collapsed cell, and 20 good patterns
go with it.** Reproduced on **3 of 9** chains over a 638-pattern laboratory
series:

```
ValueError: refusing to enumerate reflections for cell a=-347.644,
b=-3546.49, c=616.024 Å at d_min=1.086 Å ... span 4.74e+09 grid points
```

| series | patterns lost |
|---|---|
| A | **20 of 24** |
| B | 8 of 25 |
| C | 0 of 125 forward (the backward pass died) |

Recovery cost 252.5 s of re-fitting, and `on_result=` had saved what landed,
so nothing was unrecoverable — the defect is the **granularity of the
failure**. A recovered chain also carries a seam: each restarted
segment warm-starts from the *original calibrated model*, because the dead
chain's warm state is not recoverable from a `RefinementResult`, so a
recovered chain is not the same object as an uninterrupted one.

**Why the ladder never saw it, measured on the tree.** `sequential.py`
catches `RefinementCancelled` and nothing else (its two `except` clauses), so
a raise inside a fit propagates straight out of `fit()`. The escalation
ladder (WP-1051, WP-1127) ranks rung *outcomes* — a `"diverged"` status is a
rung that lost, and escalates — but an exception is not an outcome, so the
rung it would have escalated from is never recorded and the chain has no next
move. That is the granularity defect in one sentence: the ladder's vocabulary
has no member for "this rung raised".

> **Superseded in part, 2026-09-22** (re-read at `16b72c3`). PR #386 (issue
> #375, merged 2026-09-18) gave `SequentialRefinement.fit` an `on_error`
> policy — `"raise"` (the default), `"skip"` (successor cold) and `"carry"`
> (successor warm from the last accepted state) — recording a pattern that
> raised as a `SeriesFailure` on `SeriesResult.failures`/`.n_failed` with a
> `SERIES_PATTERN_FAILED` warning, and keeping partial results on `self` and
> on the exception under `"raise"`. So "catches `RefinementCancelled` and
> nothing else" is no longer true. **The sentence above still is**: the policy
> abandons *every rung* of the failing pattern together, so the ladder still
> has no member for "this rung raised". Measured on the same tree, three
> defects the policy left: (1) `_fit_one` runs `prepare`/`constrain` inside
> the guarded call, so under `"skip"`/`"carry"` a raise in the *caller's*
> hook is swallowed per pattern, against the `constrain` docstring's "a raise
> in it ends the series"; (2) under `"raise"`, a raise in the `direction=
> "both"` backward pass overwrites `results_`/`trees_`/`failures_` with the
> *backward* chain's partial state, losing the complete forward chain — issue
> #224's series C exactly; (3) under `"skip"`/`"carry"` the backward pass's
> failures are discarded (`back_entries, *_ = self._chain(...)`), so the
> comparison runs on fewer patterns and nothing says so.
>
> And the #224 case needs the ladder, not the policy: the runaway cell is
> produced by a pattern that **converges** and is accepted, so its successor
> raises at compile (below) — and under `"carry"` every later successor
> warm-starts from that same accepted state and raises too. Only a cold rung
> escapes it, which is the ladder's third rung.

**Check this before designing.** The reported cells are **negative**
(−347.6, −3546.5, +616.0 Å). WP-1110's `cell_window` / `CELL_MIN_LENGTH_A` is
deliberately applied only to phases the support test flags, so either the
support test did not flag these phases or the window was not in force on this
path. Establish which; the answer may make the raise rarer without changing
the granularity question, and both are wanted.

**Issue #225 — a *converged* fit's esd computation raises, and 103 patterns
go with it.** Reproduced deterministically, twice (291 s and 289 s), at
pattern 78 of a 182-pattern variable-temperature 11-BM series:

```
LinAlgError: Eigenvalues did not converge
run_least_squares → covariance_estimates → normal_covariance
  (optimize/statistics.py:124) → np.linalg.pinv(..., hermitian=True) → eigh
```

**By that point the least-squares fit has already converged.** What failed is
only the covariance. And `RefinedParameter.stderr` is declared `float | None`,
`weight_fraction_stderr` likewise with the comment *"None if scale esds
absent"* — so the package's own schema already says this quantity may be
absent. An exception here discards 103 answers that were in hand.

The reporter's honest limits, which constrain the design: **reproducing it
needs the full chain state** (a 21-pattern subset around the failing index ran
clean; a state rebuilt from the persisted record also ran clean), and it could
not be reduced to a data-free synthetic case (Jacobians with columns at 1e-90,
1e-160 and 1e-200 all passed through `normal_covariance` without raising). So
the `live = d > 0.0` guard is **not** asserted as the cause. What can be said
is that the guard admits columns of arbitrarily small nonzero norm, that
`JTJ * outer(inv_d, inv_d)` then divides by those norms, and that the overflow
warning observed points at that line. Do not write the mechanism into a
docstring without measuring it.

**The third defect, and the one to prioritise — a crash in the backward pass
turns `SEQUENTIAL_PATH_DEPENDENT` into a false clean bill.** On series C the
forward pass completed all 125 patterns and the crash landed in the
**backward** pass. What died was not the trajectory but the path-dependence
check itself, and that series then reports **zero** findings — which is
exactly what a clean series reports. From the result object there is no way to
tell *"both passes ran and agreed"* from *"the second pass died, so the
comparison never happened"*. For a diagnostic whose whole purpose is to
separate a measured trajectory from an ordering artefact, an unrun check
presenting as a passed check is worse than a loud failure. When it did run,
across nine series, it found **21** path-dependent findings — including a
`Pnma` phase whose `a` and `c` exchange between passes (5.404 ↔ 5.665 Å,
**15.8σ**).

`direction="both"` **already has the right instinct** on the other half: the
cancelled-forward-pass path deliberately skips the comparison, commented *"the
comparison is between two complete chains, and half of one says nothing"*.
This asks for the same care when the backward half ends early, and for the
outcome to be visible in the result rather than only in the absence of
findings.

The vocabulary for "this pattern's value is not a measurement" already exists:
`SEQUENTIAL_UNRECOVERED`, and `plot_trajectory` already draws such a point
crossed out rather than dropping it, precisely so a gap does not read as data
never collected. That is the shape the failed pattern should take.

**A refined atomic coordinate never crosses a pattern boundary, and
`carry=["*"]` says it does** (folded 2026-09-22 from WP-1432's review pass,
2026-09-19, verified then against `sequential._carry_into`: 0.2500 carried in,
0.1993 landing). `_carry_into` copies each carried value, then re-derives every
tied entry through `decode`; a coordinate is tied to its displacement DOF, the
DOF is carried at 0.0 because a freshly built source table rederives it there,
and the anchor is the *destination* structure's stored coordinate — so the
carried coordinate is overwritten by the pattern's own start. `cell.a` carries
correctly, which is what says this is the relative DOFs and not the carry. It
costs iterations rather than an answer, but it also silences
`SEQUENTIAL_PATH_DEPENDENT` for a reason that is not the data's (a parameter
that never chains cannot be path-dependent), and the fix is not local: a
`constrain` hook gives the right coordinate today *because* of this, so
carrying it without handling the hook's re-declaration would start the
displacement accumulating. `ParameterTable.rebase_anchored_dofs` (WP-1432) is
the shape a fix reuses.

**A path the comparison could not reach reads exactly like one that agreed**
(folded 2026-09-22 from the 2026-09-15 triage of issue #269). Since PR #264
`SEQUENTIAL_PATH_DEPENDENT` is judged per pattern and only where both chains
measured an esd (the `comparable` mask), and the narrowing has no output: a
cubic phase held for part of a series emits `cell.b`/`cell.c` tie rows with no
esd while `cell.a` is absent, so a path held throughout one direction falls out
silently. The reporter's options: (1) a list on `SeriesResult` of the paths not
reached, with the reason; (2) an info diagnostic; (3) per-path counts of
comparable patterns. Triage recommended (1) with (3) folded in as a field — a
schema addition and a `SCHEMA_VERSION` bump, the maintainer's to direct, and
the reporter offers the PR once directed. Rule: absent rather than zero, and
the absence visible (1072, 1076).

## Non-goals

- Making the reflection enumerator's guard laxer. The guard is right and its
  message is a good one; this WP changes what a *chain* does about it.
- Fixing whatever drives a cell to −3546 Å. That is a `cell_window` /
  phase-support question, and is scoped here only to "establish whether the
  window was in force", not to redesign it.
- Exposing the forward pass's `SeriesResult` mid-run — that is #218, owned by
  1317. If both land, a caller sees the forward trajectory *and* knows whether
  the verification half ever ran.

## Tasks

- [x] Establish whether `cell_window` / `CELL_MIN_LENGTH_A` was in force on
      the failing path in #224, and record the answer (either way it changes
      how the raise is characterised, not whether the chain should survive it).
      *Answered 2026-09-22 from the tree* (the #224 data are not in it, so
      from code, not a re-run): **not in force where the cell escaped, and
      unreachable where it raised.** (1) A windowed cell cannot leave
      ±5 % + 0.05 Å of its stage's start, and |a| went from a lattice repeat to
      348 Å, so the stage it escaped in did not window the phase: its
      `phase_support` was at or above `PHASE_SUPPORT_SIGMA` at that stage's
      start. PR #385 (issue #374) measured that mechanism on a synthetic pair
      (a *supported* phase trading scale with a near-identical one walks
      4.16 → 3803 Å in one stage, reporting `converged`), and its post-solve
      clamp is the fix for the escape, which stays this WP's non-goal. (2) The
      raise lands at the **next compile**, the next stage's, or when the escape
      is in the last stage, the next *pattern's* first rung via the carried
      warm state. `_run_stage` compiles, and so enumerates reflections, before
      `run_least_squares` calls `_freeze_cell_windows`, so no window can catch
      a cell that arrives already escaped. That is why the ladder, not the
      window, is this WP's fix: the successor raises, every warm rung inherits
      the cell, and only the cold rung escapes it. (3) The signs are a red
      herring, assuming 90° angles (the message quotes lengths only): the
      metric's diagonal is a², b², c² and its off-diagonals vanish, so a
      negative length is an exact symmetry of the forward model and of the
      degenerate-cell guard (det G = a²b²c² > 0). They say a step crossed
      zero, not that the cell was degenerate.
- [x] `covariance_estimates` returns `stderr=None` for the affected block plus
      a diagnostic naming the stage and the reason, instead of raising; a
      failed eigensolve is not a failed fit. *Landed 2026-09-22* one rank up,
      in `least_squares._guarded_covariance` (both solver entry points), so
      `covariance_estimates` keeps its array return; `COVARIANCE_UNAVAILABLE`
      per stage, the answer-producing one saying every esd is absent. The
      eigensolve is the whole normal matrix, so "the affected block" is all
      of it. Values bit-identical to a working eigensolve (tested).
- [x] A chain continues past a failed pattern: mark it, carry the last good
      warm state forward, report it as `SEQUENTIAL_UNRECOVERED`.
      *Superseded in part 2026-09-22*: continuing and carrying exist since
      PR #386 as the opt-in `on_error="carry"`, reported as
      `SERIES_PATTERN_FAILED` (shipped vocabulary, kept). What remains:
      (a) a rung that raises is a rung that lost, and the ladder escalates;
      (b) the caller's `prepare`/`constrain` stay outside the guard; (c) the
      backward pass keeps the forward state and records its own failures;
      (d) the default — `"carry"`, this WP's goal, against #386's `"raise"`,
      landed as its own commit so the maintainer can take it or leave it.
      *(a)-(c) landed 2026-09-22*: `SeriesEntry.rungs_raised` (schema
      0.24 → 0.25), `_PatternRaised` around the fit alone, the forward chain
      published before the backward pass, `result.backward.failures`.
      *(d) landed 2026-09-22, its own commit*: `on_error="carry"` is the
      default, and a chain that fitted **no** pattern raises under every
      policy, so an empty `SeriesResult` is never an answer.
- [x] Record that the path-dependence comparison did not run — a distinct
      finding naming the pass that died and the pattern it died on, or a field
      on the series result. Zero findings must mean *checked and clean*. The
      #269 half (Context, above) rides the same finding: a path no pattern
      could judge is named, in the diagnostic form (the reporter's option 2);
      the field form stays the maintainer's to direct. *Landed 2026-09-22* as
      `SEQUENTIAL_PATH_CHECK_INCOMPLETE`: `warning` when the comparison did not
      run (forward cancelled, backward cancelled, backward raised), `info`
      when it ran on fewer patterns or paths. A path is named only if some
      chain measured it and the two chains differ above the noise floor —
      without both conditions it fired on every clean series (measured: a tie
      row off a never-freed source and `profile.y` on its floor, on the
      eight-pattern LaB6 fixture).
- [x] Say in the handover what a recovered chain is **not**: warm state is not
      recoverable from a `RefinementResult`, so a restart is a cold seam.
      *Said 2026-09-22* in the handover entry and in the skill's `series.md`.
- [x] Tests: a chain with one deliberately poisoned pattern returns the rest
      flagged; a covariance failure yields `None` esds and a diagnostic; a
      series whose backward pass is cancelled reports the check as not run.
      *Landed 2026-09-22*: `tests/test_series_error_policy.py` (+9) and
      `tests/test_covariance_scaling.py` (+4).
- [ ] A refined coordinate crosses the pattern boundary (Context, folded from
      WP-1432's review): through `rebase_anchored_dofs`, with the `constrain`
      re-declaration handled — or its own WP if it outgrows this one.
- [x] Skill: `references/series.md` — the row saying that zero
      `SEQUENTIAL_PATH_DEPENDENT` findings is only a clean bill once the
      not-run signal exists, and the row on what survives a failed pattern.
      *Landed 2026-09-22*, with `abstention.md`'s #269 row pointed at the new
      finding and the two new codes' `diagnostics.md` rows.

## Acceptance

On a suite fixture with one pattern poisoned to raise, the chain returns
every other pattern with the poisoned one flagged; a series whose backward
pass is cancelled reports the comparison as not run. The #224 configuration
is the reporter's and is not in the repo: quote a re-run of it if they offer
one, never as the gate.

```sh
.venv/bin/python -m pytest tests/test_sequential.py tests/test_covariance_scaling.py -q
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
```

## References

- Issues #224, #225 (638-pattern laboratory chemical-looping series; a
  182-pattern 11-BM variable-temperature series at 84 K). #225 offers a
  `crash_capture.py` and a serialised `failing_state.json` on request.
- `optimize/statistics.py::normal_covariance` — the equilibration rule
  (WP-1110 item 14): a direction the data does not move has no esd rather than
  a small one.

## Handover log

- **2026-09-22** — A long series no longer dies because one pattern could not
  be fitted. A pattern whose fit raises now goes down the same ladder a
  diverged fit does, so a neighbour that handed on a runaway cell (#224) costs
  one cold refit instead of the rest of the chain. A pattern no rung can fit
  is marked and, by default, stepped over. An esd computation that fails
  after a converged fit (#225) now yields absent esds and a warning instead of
  losing the answer. And `direction="both"` now says when its comparison did
  not run, or ran on less than the series, so zero path-dependence findings
  means checked and clean at last. What is left is the coordinate carry folded
  in from WP-1432's review, which is not local and probably wants a WP of its
  own. Nothing of this reached GitHub, because the session could not push
  (Gotchas).

  *Done*, eight commits `0c98f6c..f4bbf37` on `wp1333-a-series-survives-one-pattern`:
  - **Prune.** Inherited was folded into Context and Tasks and deleted. Context
    re-read at `16b72c3`: PR #386 (merged 2026-09-18, after this WP was
    written) had added `on_error` = raise/skip/carry, so "catches
    `RefinementCancelled` only" was stale and is marked superseded in place.
    But #386 abandoned every rung at the first raise, and it left three
    defects, all now fixed. The caller's hooks sat inside the guard. A
    backward raise under `"raise"` overwrote the forward `results_`. And the
    backward pass's failures were discarded.
  - **Covariance** (`b7ebe0b`). `least_squares._guarded_covariance` catches
    `LinAlgError` only, on both solver entry points. `LSQOutcome.covariance_error`
    carries `repr(exc)`, and `COVARIANCE_UNAVAILABLE` is emitted once per stage.
    The values are bit-identical to a fit with a working eigensolve (tested),
    and the mechanism is not asserted anywhere.
  - **Ladder** (`3535a78`). A raised rung escalates. `SeriesEntry.rungs_raised`
    is new (schema 0.24 → 0.25), and `rwp_warm` is `None` when the warm rung
    raised. `_PatternRaised` wraps `ref.fit` alone. The forward chain is
    published before the backward pass, and backward failures land on
    `result.backward.failures`. `SERIES_PATTERN_FAILED.where` is now the label
    (it was `entries[k]`, which is off by one). A `verify_discontinuities`
    refit that raises now leaves its step unmeasured.
  - **`SEQUENTIAL_PATH_CHECK_INCOMPLETE`** (`3535a78`, `464c0df`). It fires at
    `warning` when the comparison did not run, naming the chain and the
    pattern, and at `info` for missing patterns and for #269's unjudged paths.
    `summary(deliverable="series")` now reads it.
  - **Default** (`475d9fd`, its own commit so it can be reverted alone).
    `on_error="carry"`, and a reported chain with no entry raises under every
    policy.
  - **Task 1** (`9835aea`, answered from code). The window was not in force
    where the cell escaped, and it cannot be reached where the raise lands,
    because the compile precedes `_freeze_cell_windows`.
  - **Docs.** The manual's series chapter documents the failure surface, which
    empties `tests/api_surface_deferred.txt` again (#386 had refilled it with
    six names). The skill gains rows in `series.md`, `diagnostics.md` and
    `abstention.md`. The 1.5.1 notes (`f4bbf37`) cover #386's `on_error` too,
    since it had no record entry and is not in v1.5.0.

  *Measured* (`[dev]` venv, Linux x86-64, py3.12, 4 cores, no other suite
  running). A clean both-way run of the eight-pattern LaB6 fixture fires no
  `SEQUENTIAL_PATH_CHECK_INCOMPLETE`. A naive "unjudged" list named two paths
  there: `phases.0.atoms.1.x`, a tie row off a DOF never freed, and
  `instrument.profile.y` on its softplus floor, which each chain measured on
  different patterns at about 1e-15. That is why a path is named only if some
  chain measured it and the chains differ above `_noise_floor`. The tests add
  +18 items: 17 functions, one parametrized twice, none slow, in
  `test_series_error_policy.py` (+12), `test_covariance_scaling.py` (+5) and
  `test_termination_view.py` (+1). On the final tree (`cbda6bd`, which is main merged, since main had not moved from `16b72c3`), the fast selection was 1 failed, 5486 passed, 147 skipped (total 5634) in 12:41. Before the review the total was 5633, and the difference is the one test the review added. The failure is the uid-0 telemetry case under *Review*. The series slow rows (`test_acceptance_sequential.py`, `test_held_phase.py`, `test_sequential.py -m slow`) were 23 passed, both before and after the review. The full suite was not run.

  *What a recovered chain is not* (task 5). A `RefinementResult` carries no
  warm state, so re-running `fit` over the patterns after a dead chain starts
  from the initial models. The recovered chain has a cold seam there that an
  uninterrupted one does not. Within one run the ladder's cold rescue is the
  same seam, and it says so (`reseeded`, `SEQUENTIAL_RESEED`).

  *Decisions left to the maintainer*, each a place this branch departs from
  #386 or from the triage:
  - The default flip, revertable alone.
  - `on_error="raise"` now tries every rung before raising.
  - "A chain that fitted nothing raises" is a rule of this branch's own.
  - #269's field form (a list on `SeriesResult` with a per-path count) was not
    built. The diagnostic form shipped instead, and the field is still the
    maintainer's to direct, with the reporter's offered PR.

  *Gotchas*:
  - Push was refused (403, "Claude doesn't have GitHub access": the GitHub
    App), and the GitHub MCP's `create_branch` was refused too. So there is
    no draft claim PR. The claim sits in this file and nowhere GitHub can see
    it, and the commits travel as a git bundle.
  - To inject an eigensolve failure into a whole fit, patch
    `optimize.statistics.normal_covariance`. A global `np.linalg.pinv` patch
    also breaks the report's region fits (`report/layer1.py`).
  - This environment's worktree guard refuses heredocs and `$VAR` arguments,
    so edit scripts went through the scratchpad.

  *Review* (`/code-review high --fix`, `cbda6bd`): eight findings, six taken.
  - The most important was a real hole. `check_guards`' soft-mode screen
    eigensolves the same unit-column Gram, so #225's raise came back one call
    after `_guarded_covariance` absorbed it, and the fit was discarded anyway.
    My test had patched `normal_covariance` alone. Fixed, with a test shown
    to fail without the fix.
  - Also taken: the forward chain is published before
    `verify_discontinuities` too; `result_`/`backward_` are reset per fit;
    one `arrays()` call per trajectory; the `rungs_tried` docstring's cost
    invariant; and the intermediate-stage `COVARIANCE_UNAVAILABLE` wording.
  - Left for the maintainer, both deliberately: (4) a warm rung that raised
    and was rescued by `warm_staged` fires no diagnostic, only `rungs_raised`,
    which is a vocabulary call; (5) `_carry_into`/`_carry_variables` run
    outside the fit guard, so a refusal there ends the series even where the
    cold rung would succeed. `_carry_variables`' docstring calls that
    refusal the caller's.
  - The fast suite's one failure,
    `test_telemetry.py::…[unwritable-directory]`, is this container running
    as uid 0, where `chmod 0o500` does not stop a write. Not run on main.
    What was checked is that the branch touches neither that test nor
    `runs.py`, and that the sibling parameter (`parent-is-a-file`) passes.
    Its fix is a root `skipif` beside the existing Windows one, which is
    outside this WP.

  Next, in order:
  1. From a local clone, fetch the bundle, push the branch, open the PR and
     mark it ready. That is the claim and the review this session could not
     make.
  2. Run the full suite on main merged into the branch. Only the series' own
     slow rows ran here (counts above).
  3. Decide the coordinate-carry task. The recommendation is its own WP: its
     fix reaches `rebase_anchored_dofs` and the `constrain` re-declaration,
     not the failure path. Then close 1333, rewriting Current focus.

- **2026-09-03** — created, from the 2026-09-03 issue triage (issues #224,
  #225). Two raises, one granularity question, and one silent wrong answer
  underneath both. Re-checked the same day against the tree: the chain
  catches `RefinementCancelled` only, so a raise is not a rung outcome;
  acceptance moved to a fixture, the #224 tranche not being in the repo; test
  modules named as they exist.

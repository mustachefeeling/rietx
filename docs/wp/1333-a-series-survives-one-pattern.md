# WP-1333 — a series survives one pattern, and says which one it lost

Milestone: unscheduled · Status: ⬜
Depends on: — (1317 soft: #218's forward-pass exposure is the sibling ask)

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
failure**. A recovered chain also carries a seam worth naming: each restarted
segment warm-starts from the *original calibrated model*, because the dead
chain's warm state is not recoverable from a `RefinementResult`, so a
recovered chain is not the same object as an uninterrupted one.

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

- [ ] Establish whether `cell_window` / `CELL_MIN_LENGTH_A` was in force on
      the failing path in #224, and record the answer (either way it changes
      how the raise is characterised, not whether the chain should survive it).
- [ ] `covariance_estimates` returns `stderr=None` for the affected block plus
      a diagnostic naming the stage and the reason, instead of raising; a
      failed eigensolve is not a failed fit.
- [ ] A chain continues past a failed pattern: mark it, carry the last good
      warm state forward, report it as `SEQUENTIAL_UNRECOVERED`.
- [ ] Record that the path-dependence comparison did not run — a distinct
      finding naming the pass that died and the pattern it died on, or a field
      on the series result. Zero findings must mean *checked and clean*.
- [ ] Say in the handover what a recovered chain is **not**: warm state is not
      recoverable from a `RefinementResult`, so a restart is a cold seam.
- [ ] Tests: a chain with one deliberately poisoned pattern returns the rest
      flagged; a covariance failure yields `None` esds and a diagnostic; a
      series whose backward pass is cancelled reports the check as not run.
- [ ] Skill: `references/series.md` — the row saying that zero
      `SEQUENTIAL_PATH_DEPENDENT` findings is only a clean bill once the
      not-run signal exists, and the row on what survives a failed pattern.

## Acceptance

A 9-chain re-run of the #224 configuration loses no pattern to another
pattern's raise, and the series that lost its backward pass says so.

```sh
.venv/bin/python -m pytest tests/test_sequential.py tests/test_statistics.py -q
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

- **2026-09-03** — created, from the 2026-09-03 issue triage (issues #224,
  #225). Two raises, one granularity question, and one silent wrong answer
  underneath both.

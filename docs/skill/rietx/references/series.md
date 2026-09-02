# 9b. Series: refine a ramp as a chain, and check it both ways

Load it for an in-situ ramp, a parametric sweep or a tray of related specimens.

*A reference file of the `rietx` skill. The body it belongs to is [`SKILL.md`](../SKILL.md); section numbers are the ones the body cites.*

An in-situ ramp, a parametric sweep or a tray of related specimens is
`rx.SequentialRefinement` / `rx.refine_sequential`: N separate refinements,
each warm-started from its predecessor.  (One *joint* residual over patterns
that share structural parameters is the different verb `rx.refine_multi`.)
What comes back is a `SeriesResult` — per-pattern summaries plus
`trajectory(path)`, `qpa_trajectory(phase)`, `to_table()`, `write_csv()`.

```python
series = rx.refine_sequential(patterns, structure, instrument,
                              x=temperatures, x_label="T (K)",
                              plan="lab_sample_refine")
a_of_T = series.trajectory("phases.0.cell.a")     # x, value, stderr
```

`x` is the series coordinate, and where it comes from is the file: a reader
puts a scan's own temperature in `data.metadata["temperature_k"]`, and
`rx.io.readers.list_scans(path)` reports the same number per scan before any of
them is read.  Today the Bruker `.raw` v3 range header is the one format here
with such a field; the others record no specimen temperature and none is
guessed from an axis named for something else.  A missing key is a file that
recorded nothing — **refuse rather than substitute an ambient value**, because
an invented coordinate makes the trajectory a fiction while every fit in it
stays perfectly good.

What an operator must know, all measured:

- **Chaining is worth ~3x in iterations, not in accuracy.**  On the eight
  round-robin sample-1 mixtures: 2863 iterations unchained, 904 chained, at
  identical Rwp and identical weight fractions.  Use it to make a long series
  affordable, never to make an individual fit better.
- **What licenses a chain is physical continuity, and a *tray* has none** — so
  of the three cases above, the tray is the one to think twice about.  Chaining
  eight ex-situ YBaCo₄O₇ specimens that shared only a method *created* the
  disagreement it was then used to measure: refitting them as independent cold
  points moved the referenced pattern's Rwp gap from **0.571 to 0.045 pp** and
  its cell-*a* gap from **0.051 to 0.0041 Å**, and what had been recorded as
  that campaign's largest cell-*a* disagreement with TOPAS was the chain's own
  artefact.  Warm chaining is ~10x cheaper per pattern (**0.16 s against
  1.82 s** measured on one series), and on specimens with no physical ordering
  that is the wrong saving.  Inside a *genuine* ramp the same test is worth
  running step by step rather than once: on that series a different, larger
  jump survived having no chain, so that one was real — chaining artefacts are
  established or refuted transition by transition.
- **The default `refit="single"` collapses the plan into one stage** for every
  pattern after the first.  The staged turn-on order exists to keep early
  stages conditioned from a *poor* starting model; a converged neighbour is not
  one.  A pattern where that turns out to be wrong is caught by the reseed
  fence, which **escalates one rung at a time** — the full staged plan from the
  warm state, then the full staged plan cold — and keeps the best attempt.
  `entry.rung` says which one produced the values and `entry.rungs_tried` says
  what else was tried; `entry.reseeded` still means only the cold rung won, so
  a `"warm_staged"` point is one whose chain is unbroken.
- **A pattern that no rung recovers is quarantined, not merely flagged**
  (`SEQUENTIAL_UNRECOVERED`): it seeds no successor and its Rwp is left out of
  the median that decides every later trigger.  So a single failure cannot
  propagate down the chain or quietly raise the bar for the patterns after it —
  but it is still *reported*, and reading its parameters is on you.
- **A sequential trajectory is path-dependent by construction**, so a smooth
  curve is exactly what a poisoned chain produces.  `direction="both"` runs the
  series each way and reports `SEQUENTIAL_PATH_DEPENDENT` per parameter.  For
  any trajectory you intend to publish, run it — it is the only check that
  separates a measurement from an ordering artefact.
- **But forward/backward *agreement* is not evidence of correctness**, and the
  two failures it cannot see were both measured.  A flat degenerate band
  reproduces the same wrong answer in both directions — **|Δweight| median
  0.000, max 0.030, 0 of 35 patterns disagreeing by more than 5 pp** on a
  construction that was physically wrong — because the check compares two
  paths, not two basins.  And where findings *are* present the set is not the
  signal: `SEQUENTIAL_PATH_DEPENDENT` was non-empty on all four series of one
  tranche, and the single chain actually sitting in a wrong basin was localised
  by **σ magnitude** (98.9σ and 84.4σ on the scales the QPA is built from,
  against ≤8.8σ everywhere else).  Read what was flagged before reading physics
  into it: two of the largest flags measured anywhere — **81.5σ** for *a* and
  *b* exchanging in `Fddd` and **15.8σ** for *a* and *c* in `Pnma`
  (5.404 ↔ 5.665 Å) — are degenerate axis relabellings, and the largest on
  another run (16.6σ) was a *held* cell reaching the pattern with two different
  held histories, which is bookkeeping rather than two measurements.
- **`SEQUENTIAL_RESEED` is not the net for a wrong basin.**  Its trigger is
  Rwp > `reseed_factor` × the running median of accepted patterns (default
  1.25), so it needs roughly a **25 % relative Rwp jump** — and a polymorph
  swap does not cost that.  Tested directly on 20 such patterns it fired **0
  times**; where it *can* fire it works, 6 firings elsewhere in the same run
  all keeping the chain out of the disagreement set.  A wrong basin at
  negligible Rwp cost is the case for `direction="both"` and for cold refits,
  not for the reseed ladder.
- **The `SEQUENTIAL_*` codes live on `SeriesResult.diagnostics`, one level up
  from the entries.**  Reading `entry.diagnostics` for them returns zero on
  every series, which presents as a clean run rather than as a lookup in the
  wrong place — it cost one operator a full re-run of the chain stage for nine
  series, caught only by distrusting a suspiciously flat all-zero result.
  Per-entry diagnostics are real and carry every per-pattern occurrence; the
  rollups are not among them.
- **An unrun check is indistinguishable from a passed one.**  A series whose
  forward pass completed all 125 patterns and whose **backward pass crashed**
  reports **zero** `SEQUENTIAL_PATH_DEPENDENT` findings — byte-for-byte what a
  clean series reports.  Confirm both passes completed before reading an empty
  set as a pass, and report the empty set as a measured result rather than
  omitting it.  Both safety checks are also worth pricing up front: on one
  series the backward pass was **43.9 %** of wall clock and the
  `verify_discontinuities` refits **15.1 %**, so **59 % of the run bought
  assurance rather than answers** — the right trade for a trajectory you will
  publish, the wrong one for a screen.
- **A flagged step can check itself.**  `verify_discontinuities=True` refits
  each `SEQUENTIAL_DISCONTINUITY`'s two patterns **cold and independently** and
  writes the cold step over the chain's step to the diagnostic's `value`, signed:
  near 1.0 the step is in the data, near 0 the chain made it, negative a cold
  pair that moved the other way.  Off by default because
  a cold fit is the full staged plan from the initial models; measured on a
  68-pattern ramp flagging four steps over four patterns it costs 5 % of the
  chain, and the cost scales with the patterns flagged rather than with the
  series length.  Nothing else moves: the refits are separate `Refinement` runs
  writing to their own `<label>.verify` histories.

- **A trajectory of phase fractions is a QPA question at every point of it, and
  the background is what decides it.**  Fractions ride on scales, and an
  over-flexible background biases scales silently while *improving* every
  agreement index — which is why §4b's QPA row reads
  `report.background.worst_absorption` before any statistic beside it.  Nothing
  in `SeriesResult` repeats that check for you, and no `SEQUENTIAL_*` code can:
  they compare each pattern against its neighbours, and a background too
  flexible for the *specimen* is wrong in the same direction at every point, so
  the trajectory it produces is smooth, self-consistent and false.  Measured on
  a real 68-pattern reel: a 12-term cold fit put LT-ZrMo₂O₈ at **77.9 wt %**
  when that phase is not present at all, Rwp 0.0821 against 0.0822 for the
  correct answer, with a difference curve that looks fine; over the round the
  absent phase took **40-96 wt %** at an Rwp within 0.01 of the right one.
  Neither Rwp nor the plot separates them.  So read
  `background.worst_absorption` per pattern — at least on the first, the last
  and every flagged step — before quoting a fraction trajectory at all.  The
  route is not `SeriesResult`, which carries summaries only, and not
  `rx.refine_sequential`, which discards the per-pattern results: use the class
  form, whose `results_` holds them.  `sr = rx.SequentialRefinement(structure,
  instrument)`, `series = sr.fit(patterns, ...)`, then
  `rx.build_report(sr.results_[i]).background.worst_absorption`.

Driving one: **`fit()` is all-or-nothing, so wire `on_result=` before starting
anything long.**  The per-pattern loop catches `RefinementCancelled` and nothing
else and returns its `SeriesResult` only at the very end, so one exception
discards every pattern already fitted — measured as a `LinAlgError: SVD did not
converge` at pattern 217 of 531 taking all 216 with it, and a deterministic
`LinAlgError: Eigenvalues did not converge` at index 78 destroying **103
already-fitted patterns whose values were fine, because the fit had converged
and only the error bars failed**.  Cell lengths carry no physical upper bound,
so a pattern reaching `a = −347.644 Å` raises out of the reflection enumerator
and takes the chain with it (**3 of 9 chains** on one tranche, one losing 20 of
24 patterns).  The failure mode is reassuringly narrow — across **1846
`fit_start`/`fit_end` pairs the only exceptions raised anywhere were those
reflection-enumeration guards**, no hangs, no NaNs, no silent wrong-shape
results — so a driver only has to survive that one.  `on_result=(index,
result)` fires as each pattern lands; persisting there is what saved the 103
above, and it is the single highest-value line in a series driver.

**`on_result` fires on the forward pass only, and so does `results_`.**  With
`direction="both"` the backward chain is passed `None` for the callback, so
backward-pass patterns have event-log timings and **no `RefinementResult`** — 53
of them on one run.  The backward `SeriesResult` is on `.backward_` and on
`series.backward`; any per-pattern instrumentation you plan is half-populated by
design, which matters most for exactly the check above, since
`background.worst_absorption` is unreachable for the backward pass.

**Turn history on explicitly — the two defaults disagree.**  `Refinement`'s
`history` defaults to `True` and `SequentialRefinement`'s to **`False`**, and
one harness silently lost the restorable per-pattern tree for **550 fits** by
never passing it.  Here the path becomes a *directory* of one JSONL per pattern
holding **more files than patterns**, because reseed retries write their own
(291 files for 275 patterns) — so file count is not a completion check.

When the deliverable *is* the trajectory, print its deciding rows:
`series.summary(deliverable="series")` — §4b's fourth row, and the two
statements no diagnostic can make for you.

```python
print(series.summary(deliverable="series"))
```

`carry` (dot-path globs) restricts what crosses a pattern boundary.  Reach for
it when a parameter must provably not be chained; do **not** reach for it
because a parameter jumps.  That hypothesis was tested on a series whose
composition swings 1 → 94 wt % and it is false: carrying everything is cheaper
there than excluding the scales.

`prepare=(index, data, structure, instrument)` is the other half of that, and
the case above is what forces it: excluding a parameter from `carry` only falls
back to the **first** pattern's guess, which is not the same as re-estimating
it.  `prepare` runs on the *warmed* models just before each fit, so a scale
that must be estimated from *this* pattern rather than carried or left at an
initial value has somewhere to be set.  Two smaller hooks worth passing on any
long run: `progress=` (a stream or path) emits one line per stage boundary per
pattern and is the cheap way to know a run is alive, and `labels=` names the
entries — without it every downstream table is keyed by integer.  A cancelled
series **returns** what completed, with `SEQUENTIAL_CANCELLED`.  Note that
`stage_reports=True` does *not* exist here; it is a `Refinement.fit()` argument
and raises `TypeError`, and per-stage Rwp lives on the `stage_end` events of the
shared `EventStream` instead (present on **637 of 637** payloads in one run,
where `StageResult` carries no `rwp` field at all).

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
  and every flagged step — before quoting a fraction trajectory at all.

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

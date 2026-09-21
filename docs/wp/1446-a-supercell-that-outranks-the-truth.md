# WP-1446 — a supercell that outranks the truth, on evidence the panel already has

Milestone: unscheduled · Status: ⬜
Depends on: — (1442 soft)

## Goal

A candidate cell that predicts reflections the pattern does not show ranks
below one that does not. The number that says so is already computed.

## Context

Split out of WP-1442 on 2026-09-22 with the maintainer, because it is an
indexing-panel change and 1442 is a contamination screen.

**What 1442 exposed.** Until 1442 the Kβ/W Lα screen dropped lines on evidence
that could not be right — it fired at the chance rate on patterns collected
behind a graphite monochromator, where neither line reaches the detector. Two
of those wrong drops were on `qarr/brucite.prn`. With them gone, the round-robin
brucite row ranks an **a × 2 supercell first**, and
`test_the_supercells_that_used_to_outrank_brucite_now_sit_below_it` fails at
`a = 6.2950` against a certified 3.1475.

**The panel has the evidence and does not use it.** Measured 2026-09-22 on
`75ac934a`, over the 38 usable lines (WP-1442's handover names the script
that draws both tick rows against the pattern, which is the fastest way to see
the claim):

| candidate | predicts | of those, present | fraction | indexes, of 38 observed |
|---|---|---|---|---|
| truth, P -3 m 1, a = 3.1477 | 29 | 25 | **0.86** | 31 |
| a × 2, a = 6.2950 | 90 | 25 | **0.28** | 31 |

Both index the same observed lines. The supercell earns its rank on
`n_indexed` = 34 against 33 on the *fitted* panel, a margin of one line, while
predicting three times as many reflections as the pattern shows. The failing
row's own docstring states the intended behaviour and the intended mechanism:
"the truth shows 0.86 of its own predicted lines against the c × 2 cell's 0.43
and the c × 3 cell's 0.32 — very close to the 1/2 and 1/3 an exact supercell
must give, which is what makes it a signature rather than a threshold."

**This is WP-1026's failure returning.** That session found every one of twelve
brucite candidates a supercell. The row exists to catch exactly this. It was
green while the contamination screen was removing lines for a false reason, so
the guard and the defect were cancelling.

**The margin is one line, and 1442 did not create that.** Measured both ways:
removing either re-admitted line alone leaves the supercell first; only removing
both restores the truth, and that run finds a different candidate set entirely
(70 s against 245 s), so the counts are not comparable across it. The ranking is
fragile at this dataset whatever the peak list.

**Where to look, and the first task is already answered.** The number is
*reachable*: `CellCandidate.fom_value("predicted_seen_fraction")` returns it,
and `test_the_supercells_that_used_to_outrank_brucite_now_sit_below_it` asserts
on it directly (`best.fom_value(...) > 1.5 * cell.fom_value(...)`). So this is
not a missing measurement, it is a ranking that does not weigh one it holds.
`indexing/fom.py` and the ordering in `indexing/engines.py`.

## Non-goals

- Retuning the contamination screen. WP-1442's numbers are measured against a
  control and are not the lever here.
- Promoting brucite. The gate already declines to promote it and should carry
  on declining; this is about the *order*, which is what a caller reads first.
- A general supercell detector. The reverse-direction fraction is the evidence
  the panel already computes, and the tractable question is whether the ranking
  weighs it.

## Tasks

- [x] Find where the reverse-direction fraction is computed, and whether the
      ranking reads it. **Answered while filing** (2026-09-22): it is on the
      candidate as `fom_value("predicted_seen_fraction")` and an acceptance row
      already asserts on it, so the ranking has it and does not weigh it.
- [ ] Rank so that a candidate predicting reflections the pattern does not show
      cannot outrank one that does not, on the measured 0.86-against-0.28.
      Measured on brucite and on every other row of
      `tests/test_acceptance_indexing.py`, which is the only way to see what it
      costs elsewhere.
- [ ] Restore the rank assertion. WP-1442 split the row: the original keeps
      every physics assertion and locates the truth in the candidate list
      rather than at index 0, and `test_brucites_truth_is_not_ranked_first`
      carries the rank as `xfail(strict=True)`. **That row goes red the moment
      this WP works**, which is the signal to fold the assertion back into the
      row above and delete the fence.
- [ ] The 2 × and 3 × supercells stay *in* the candidate list. They are real
      solutions of the metric and a reader should see them ranked, not hidden.
- [ ] Whether the same fragility reaches the other round-robin rows, measured
      rather than assumed.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_acceptance_indexing.py
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
```

## References

- WP-1026 (the first recorded instance), WP-1030/1039/1040/1041 (the prunes,
  ordering, third engine and dedup key the row was never re-run across).
- WP-1442 (what removed the mask, and every number above).
- WP-1442's handover § Figures — how to redraw the two tick rows against the
  pattern, which is the fastest way to see the claim.

## Handover log

### 2026-09-22 — filed

The software ranks an obviously wrong unit cell first on brucite, and it has
the number that says the cell is wrong. A cell with one edge twice too long
predicts ninety reflections where twenty-five are present; the right cell
predicts twenty-nine where twenty-five are present. Both index the same
observed lines, and the wrong one wins on a single extra line. WP-1442 did not
cause this. It removed a contamination screen that was throwing away real peaks
for a reason that could not be true, and two of those peaks were on brucite, so
the defect had been hidden rather than absent.

Next: find out whether the ranking can see the reverse-direction fraction at
all. Everything else follows from that answer.

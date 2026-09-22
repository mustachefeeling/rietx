# WP-1446 — a supercell that outranks the truth, on evidence the panel already has

Milestone: unscheduled · Status: 🛑 2026-09-22 — premise measured false; WP-1449 inherits the question
Depends on: — (1442 soft)

## Goal

A candidate cell that predicts reflections the pattern does not show ranks
below one that does not. The number that says so is already computed.

**Outcome (2026-09-22): the premise is false.** The number is computed and it
does not separate the cases. See the handover entry; WP-1449 inherits the goal.

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
- [x] Rank so that a candidate predicting reflections the pattern does not show
      cannot outrank one that does not. **Built, measured and reverted**: it puts
      brucite's truth first and demotes SRM 676a's own cell, and the two cases are
      not separable by that question. `ambiguity._refuted_supercell` is kept
      private, unwired and tested.
- [ ] ~~Restore the rank assertion.~~ **Not reached.** The fence stands and its
      xfail reason now names WP-1449. Folding it back is that WP's last task.
- [x] The 2 × and 3 × supercells stay *in* the candidate list. Measured while the
      rule was wired: a **tier** pushes them out of the reported twelve in favour
      of cells at `predicted_seen_fraction` 0.14-0.24 that are nobody's
      derivative, so the constraint has to be pairwise. That finding survives the
      revert and is what WP-1449 should build on.
- [x] Whether the same fragility reaches the other round-robin rows. It reaches
      **corundum and LaB6**, and it is not fragility: it is the question being
      the wrong one.

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

### 2026-09-22 (2nd session) — the reverse direction cannot order two fitted candidates (reconstructed post hoc)

**Reconstructed on 2026-09-22 from the three commits, their messages and the
checklist**, the working session having ended without writing an entry and
without pushing. Every number below is one those commits record. The repair
pass added the push, the review and the counts at the end.

The indexing panel ranks an obviously wrong unit cell first on brucite, and the
number refuting that cell already sits on the candidate. This session wired the
ranking to weigh it, and the rule does what it was built to do: brucite's
certified cell goes from third place to first, and the doubled cell drops below
it. The same rule then demotes the certified corundum cell, whose unseen
reflections are absent because its symmetry forbids them. Every variant measured
fires on that correct cell, so the ranking change came back out and the question
passes to WP-1449, which will ask the extinction screen instead of the peak
list. What the tree keeps is a refutation nobody has to pay for twice, and the
instrument that measured it.

**Done.**

- `ambiguity._derivative_transform` and `ambiguity._refuted_supercell`: the
  exclusion `ambiguity_partners` already asks of an enumerated partner, asked of
  two candidates already in the list. Private, unwired, three rows in
  `tests/test_indexing_reduce.py`, the numbers in the docstring. Kept as
  `fom._log_sum_scores` is kept, because it is the instrument this was measured
  with.
- `src/rietx/indexing/engines.py` is byte-identical to `origin/main`. 56eebbaa
  wired `order_below_parents`, c1990e9f took it back out.
- Brucite's strict xfail on the rank stands, its reason now naming WP-1449.
  c7a8f663 folded the assertion back into the row holding the physics when the
  fix looked good, and c1990e9f re-fenced it.
- One standing rule in `src/rietx/indexing/CLAUDE.md`, on the bullet that
  already owned the question. Its cap goes 300 to 306 with the log entry
  `tests/test_docs_consistency.py` asks for, raised rather than shaved.
- `tests/validation_matrix.py` and its generated `docs/VALIDATION.md`: brucite's
  measured line now carries the refutation and names WP-1449.
- WP-1449 filed, carrying the measurement, the interleaving table and the
  literature the tree can cite. Its corpus section is unsearched and says so.

**Measured.** Recorded by the working session's commits, on this machine
(macOS arm64) in this worktree's `.venv`, `[dev]`.

- Wiring the rule, on the captured 146-candidate brucite merge: the truth goes
  rank 2 to rank 0, the a × 2 supercell rank 0 to rank 2, and both c × 2
  supercells stay in the reported list. The ranking step costs 0.65 s to 2.16 s
  inside a 248 s search.
- What it costs elsewhere: four acceptance rows, two on corundum and two on
  LaB6, against a baseline of 44 passed and 1 xfailed.
- Why no bar on the question separates the populations. Absent-extra share reads
  0.943 for corundum's truth against 0.931 and 0.983 for the two brucite
  supercells that have to go down. Indexed-line gain over the parent reads −1 to
  +15 against +1 and 0. Three variants were measured, any absent extra, a share
  bound, and a gain bounded by `n_unindexed`, and each one fires on the correct
  cell.
- Why H comes from the lattice: the parent's predicted lines sit a median 7.0e-5
  in Q from the supercell's against a median σ(Q) of 6.8e-5. A line-position
  test is not separable at this data's own precision. `same_lattice` on the
  reduced forms is exact to the fitting difference.
- Why the volume prefilter can be loose: brucite's a × 2 supercell sits 6 ppm
  from 4 × the truth's volume, so one per cent is four orders of slack on what
  it has to admit.

**Gotchas for WP-1449.**

- The constraint has to be pairwise. A tier sinking all 46 refuted candidates
  below all 100 others put the truth first and pushed the 2 ×, 3 × and c × 2
  supercells out of the reported twelve, in favour of cells at
  `predicted_seen_fraction` 0.14 to 0.24 that were nobody's derivative. That
  finding survives the revert.
- Enumerate the parent's lines from the child's own fitted metric through H⁻¹.
  Enumerated from the parent's own fit the two sets sit a median σ(Q) apart and
  the extras cannot be counted.
- The coverage self-check earns its place. H relates two metrics and says
  nothing about centring, so the pair is declined when the child does not
  actually predict the parent's lines.
- A true superstructure has its superlattice reflections present, so it has no
  absent extras and the rule leaves it where the panel put it.

**Not reached.** Restoring the rank assertion. The fence stands and folding it
back is WP-1449's last task.

**No skill row.** `SKILL.md` §19 already tells an agent never to take
`candidates[0]` on its rank, and `abstention.md` carries the reasoning. What this
session measured is that `predicted_seen_fraction` does not separate a supercell
from a space-group absence, so there is no action to publish. WP-1449 owns the
row if the screen-based route works.

**Why this entry is a repair.** PR #413 merged the claim commit on its own and
closed. The three working commits were never pushed, so `origin/main` carried
WP-1446 as claimed, held none of the code, and had no WP-1449 file.
`.claude/hooks/handover_owed.py` did not fire, its trigger being a branch that
is clean **and** pushed. The Stop hook therefore cannot see the case where the
push is what is missing, which is the one that strands a whole session.

Next: WP-1449, which asks `determine_extinction_symbol` rather than the peak
list. Its first act is the corpus search its stub declines to fake, and
`/Users/yue/zotero-linker` is gone as of 2026-09-22, so that needs the
maintainer. WP-1445 wants a schema decision before it can start. WP-1447 and
WP-1448 block nothing and are the cheapest of the four.

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

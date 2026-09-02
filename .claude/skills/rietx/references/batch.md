# 9c. Many fits as one job: candidates against one pattern, patterns fitted separately

Load it when one refinement is a unit of a larger job — candidate models
screened against one pattern, or many patterns fitted independently rather
than chained (§9b is the chain, whose fits share an order and a path).

*A reference file of the `rietx` skill. The body it belongs to is
[`SKILL.md`](../SKILL.md); section numbers are the ones the body cites. Every
row carries its evidence: `(Measured: …)` names the run and its number,
`(Hypothesis: …)` names what would decide it.*

A batch is N separate `rx.Refinement` runs, or N branches of one history tree
([`references/history.md`](history.md)), each a whole §1-§10 job with its own
deliverable, stop rule and report. It is not `rx.refine_sequential` (§9b: each
fit is warm-started from its neighbour, so the set has an order and its
trajectory a path) and not `rx.refine_multi` (one joint residual over patterns
that share structural parameters). What the body settles for one fit is
settled here too and is not restated: the deliverable and its deciding rows
(§4b), the three stop conditions (§10), abstention (§6). This file holds only
what exists once fits are **compared, budgeted or stopped as a set**.

## Writing a row

A row is a rule an operator of a batch needs and a single fit never does, with
the measurement that produced it. From a run's logs the form is: the rule as
one imperative sentence in bold, numbered `9c.N`; what was measured — the
dataset or episode, N, the number that decides — in two to four sentences;
then the tag. `(Measured: …)` names the run. Where the run is in this
repository — a WP, an eval round, a dataset in `tests/data/README.md` — name
it so a reader can go and look. Where it is not, name the **corpus** the file
declares in its provenance line above, and name it the same way every time:
the package has to be tested on data it cannot ship, so a row measured on data
a reader cannot open is admitted, but it must be recognisable as one before
the reader acts on it. Two things the private case does not relax. Every
number still comes from the log, and anything the log does not decide is a
`Hypothesis` row: unverifiable is not a licence to be vaguer. And a scientific
magnitude derived from unpublished data stays out. The line is what the row is
about: what the *run* did may be quoted — counts, rates, wall clock, a ratio of
fit qualities, which is what the rows below are made of anyway — and what the
*specimen* is may not: a cell, a phase fraction, a domain size, a transition
temperature, and a ratio of two of those is still one of those. Quote the
shape, or a published figure, instead, which is where the lesson was anyway.
`(Hypothesis: …)` is for a
rule the logs suggest but do not decide, and names what would decide it. A
hypothesis row is not a weaker rule; it is an open question stated as one, and
§6 applies to it — do not act on it as if it were measured. Before adding a
row, ask whether it holds for one fit alone: if it does, it belongs in the
body or in §8, not here. All rows sit under *The rows*, one after another,
each closed by its tag; `tests/test_skill.py` refuses a row without one, and
`CONTRIBUTING.md` § The agent skill has the sync step.

## The rows

**9c.1 Declare each job's deliverable and stop rule before the batch starts,
and read the stop on the report, never on Rwp.** §4b's *Stop when* column is
the stop rule per job and it differs by deliverable; a batch launched without
one stops on whatever its author reached for — in the campaign's six refining
runs an external comparison, a script exit, an instruction, and for three of
them nothing: they ended waiting. *(Measured: WP-1307 round 1.1, R11 — three of four ramp
cells stopped on a §4b deliverable row, against 0 of 6 in the 86-run campaign
and 0 in round 1.0, when §4b had no such row to reach for.)*

**9c.2 A candidate the data cannot see is unseen, not refuted.**
`PHASE_UNCONSTRAINED` says the phase was held for the stage because nothing of
it moved the residual (§6, rule 22): its scale at the floor is not a
measurement of 0 wt %, and its cell is the one you handed in. Screening
candidates, sort such a fit into "not testable on this pattern", never into the
rejects — and never let the batch walk it: before the hold existed, one absent
phase cost 27 % of a 35-minute session, and its chain, reproduced on 13
sub-onset patterns, took 6.7 s with cell bounds and was killed unfinished at
13 minutes without them. *(Measured: WP-1301, and WP-1307's baseline ramp
run — the flat direction's share of wall.)*

**9c.3 Rank candidates only on fits of the same channels, the same excluded
regions and the same background flexibility.** §4 makes Rwp a relative number
between fits *of the same data over the same channels*, and §4 step 17 makes
R_B flatter whichever model partitioned the intensities, so neither ranks
across protocols. A batch that varies the background order or the excluded
regions per candidate has ranked protocols, not models: on one fit, the
over-flexible background won on every agreement index while being wrong, and
`worst_absorption` (0.46 against 0.08) was the only row that separated the
two. Compare `rwp_background_subtracted` pairs, the Le Bail gap ratio and ΔBIC
for nested models, each on an identical protocol. *(Hypothesis: follows from
§4's same-channels rule and WP-1055's single-fit measurement; no batch has
measured the ranking itself.)*

**9c.4 Budget a job from what a converged job costs on this batch, and read a
job past its budget as a diagnosis.** §8.13: a stage that takes minutes is
telling you it is degenerate. On a chain the rung budget is a factor times the
dearest *converged* first rung, never a fixed wall (WP-1127); a job several
times the median converged job is a flat direction or a degeneracy to read in
its trajectory, not a fit to wait for. *(Hypothesis: the mechanism is measured
on a chain, WP-1127, and on the ramp run's 27 %; the factor for independent
jobs is not.)*

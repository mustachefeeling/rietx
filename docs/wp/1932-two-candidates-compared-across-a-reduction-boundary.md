# WP-1932 — two candidates compared across a reduction boundary

Milestone: unscheduled · Status: ⬜
Track: What fires, and what stays silent
Depends on: — (1923 soft: the same `reduce.py` seam and the #797 cell; 1915 soft: the covariance the distance's esd reads)
Priority: P3 2026-10-08 — a proposal whose harm on the tree is unmeasured: one lattice near a Niggli boundary could be kept as two candidates; P2 if the first task finds a dedup or `same_lattice` call that splits one

## Goal

Whether two indexing candidates are the same lattice is decided by a distance
that is continuous across the Niggli reduction's boundaries (NCDIST in G6, or
the S6 distance), with the reduced cell kept as the grouping key.

## Context

Issue #834 (mustachefeeling, 2026-10-08).

**Today.** `engines.dedup_groups` (`indexing/engines.py:1430`) Niggli-reduces
each candidate's A..F and compares the reduced vectors with
`reduce.equal_reduced` (`reduce.py:414`): a χ² on Δ under the summed
covariances against `CELL_EQUALITY_CHI2` = 16.8119, or, without covariances,
every component within `CELL_EQUALITY_RELATIVE` = 5e-3. The stacked form is
`equal_reduced_many` (WP-1519). `reduce.same_lattice` (`:503`) asks the same
question for two unreduced vectors. WP-1518 fixed the frame each covariance
is read in (77-98 % of real comparisons were weighed in the wrong one).

**The problem #834 names.** Niggli reduction is a canonical form with decision
boundaries. Near one, two descriptions of one lattice can reduce to
different sides, and a comparison of reduced forms then calls them distinct.
WP-1923's #797 trace is one instance: at ε = 7.2e-5, `normalize` gives E the
opposite sign of the exact image, |E| = 1.75e-5 inside ε. 1923 makes that one
reduction an exact change of basis. This WP makes the *comparison* indifferent
to which side a reduction fell.

**Prior art.** Andrews & Bernstein (1988) define G6, where Niggli reduction is
a set of boundary reflections. Andrews & Bernstein (2014) give NCDIST, a
distance continuous across those boundaries. Andrews, Bernstein & Sauter
(2019) show the Selling/S6 form has simpler boundaries and give its distance.
A database keys records by a canonical form and matches them by a metric, for
this reason. **Licensing:** build from the papers. Before reading any
implementation, check its licence against ATTRIBUTION.md's rules.

**The proposal** (#834): keep the reduced cell as the dedup key; replace
`equal_reduced`'s χ² with NCDIST or the S6 distance; propagate the candidate
covariance into G6 (A..F are G6 coordinates up to the factor 2 on D, E, F)
and report distance over its esd; `same_lattice` uses the same test. The
engines' search is unchanged.

**Checked against the tree at `a3f9140a`:** every symbol named exists where
the issue says. Not measured, by the issue or here: whether any comparison
on the indexing acceptance corpus or the bethanechol benchmark splits one
lattice across a boundary today. That count is the first task, since the
priority rests on it.

**Consumers of the test** (grep at `a3f9140a`). `dedup_groups`, both its
pairwise (`engines.py:1543`) and stacked (`:1601`) paths; `same_lattice` in
`ambiguity.py:179` and in `priors.py:345`, which matches a candidate against
a prior cell; and WP-1921's planned `find(cell=)`, whose acceptance holds it
equal to `equal_reduced_many` on every pair.

### Inherited

(empty)

## Non-goals

- The #797 reduction being an exact change of basis, and the conventional
  setting a candidate is reported in: WP-1923. 1923's own non-goal keeps
  `dedup_groups`' grouping unchanged, which is why this is a separate WP.
- What the engines search.
- NaN esds from an unmeasured A..F direction: WP-1915.

## Tasks

- [ ] Measure first: on the WP-1518 acceptance corpus and
      `tests/data/bethanechol_indexing.json`, count the pairs that one
      lattice's two descriptions reduce to across a boundary, and how many
      `equal_reduced` then calls distinct. Re-rate Priority from the count.
- [ ] Choose NCDIST or S6, with the reason (boundary count, cost per pair
      against `equal_reduced_many`'s stacked solve), and its esd's
      propagation from `cov_af`.
- [ ] Replace the test in `equal_reduced`, `equal_reduced_many` and
      `same_lattice` from one implementation.
- [ ] Run `tests/test_acceptance_indexing.py` and the bethanechol benchmark
      alone (root CLAUDE.md: engine budgets are wall-clock), listing every
      group and grade that moves.
- [ ] Tests: the #797 `red` and `t @ af` at distance 0; a pair either side of
      each Niggli boundary type.
- [ ] Skill: none expected, since a candidate list's shape does not change;
      say so in the handover or add the row if a field lands.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_indexing_reduce.py tests/test_indexing_consensus.py -n auto --dist loadgroup
.venv/bin/python -m pytest tests/test_acceptance_indexing.py -n auto --dist loadgroup
.venv/bin/python -m tests.bethanechol_benchmark
.venv/bin/python -m ruff check src tests examples
```

No pair `equal_reduced` joined correctly is separated, and every group that
moves is listed in the handover with its cause.

## References

- Issue #834; #797 and #779 (WP-1923); WP-1518, WP-1519, WP-1921.
- Andrews, L. C. & Bernstein, H. J. (1988). *Acta Cryst.* A44, 1009-1018,
  doi:10.1107/S0108767388006427.
- Andrews, L. C. & Bernstein, H. J. (2014). *J. Appl. Cryst.* 47, 346-359,
  doi:10.1107/S1600576713031002; erratum 47, 1477.
- Andrews, L. C., Bernstein, H. J. & Sauter, N. K. (2019). *Acta Cryst.* A75,
  115-120, doi:10.1107/S2053273318015413.
- Bergmann, J. et al. (2004), the bethanechol benchmark
  (`tests/data/bethanechol_indexing.json`).

## Handover log

- **2026-10-08** — created, from the 2026-10-08 issue triage (issue #834).
  Checked against the tree at `a3f9140a`: the named functions and constants
  are where the issue says. No open WP owns the equality test: 1923 shares
  the seam and fences dedup's grouping out as a non-goal; 1518 and 1519 are
  closed; 1921 is a consumer. The reporter names this the proposal they
  would take on first.

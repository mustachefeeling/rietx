# WP-2033 — a declared Z or density filters an extinction class's members

Milestone: unscheduled · Status: ⬜
Track: Data and metadata in, a structure out
Depends on: — (1967 soft, closed: the `ExtinctionPrior` filter this extends; 2030 soft: the formula's Z check in the search)
Priority: P3 2026-10-23 — a workaround covers it: the user drops the groups by hand after the screen, as #935 describes

## Goal

A caller who knows the formula units per cell (Z), or a measured density that
fixes Z through the formula weight and the cell volume, can declare it to the
extinction screen. The screen then removes from each class the space groups
whose site multiplicities cannot hold that content, and names each one removed.
Nothing changes for a caller who declares nothing.

## Context

- **Source.** Issue #935 (2026-10-13) proposed one `restrict=` covering
  `sohncke`, `polar`, `centrosymmetric`, `z` and `density`. WP-1967 built the
  first three as `rx.ExtinctionPrior` through PR #940 (merged 2026-10-17,
  `c93c4213`). The maintainer's 2026-10-14 decision, recorded in 1967's
  Context, split Z and density off as a follow-up outside #940, because they
  need Wyckoff multiplicities, which gemmi does not ship. #935 stays open for
  this half.
- **What the tree has, at `12f459e`.** `ExtinctionPrior`
  (`schemas/indexing.py:2054`) holds three optional booleans, each read off
  the group's operators. Its contract is "a filter, never evidence". It is
  reported as `EXTINCTION_PRIOR_APPLIED` naming every removed group. It never
  enters a ΔBIC. Every class is still fitted, and a class it empties stays in
  the ranking. `crystallography/wyckoff.py` gives the multiplicity of a
  **given** position (`site_constraints(...).multiplicity`, read off
  `symmetry.site_orbit`), but no group's list of available orbit sizes.
  `indexing/diagnostics.py`'s `INDEX_Z_NOT_INTEGER` (WP-1510) already turns a
  formula and a volume into Z for the search, and WP-2030 owns its window.
- **The first decision is what "cannot hold" means.** Each element's count
  per cell, Z × its count in the formula, must be a sum of the group's orbit
  sizes. That test is exact for an ionic solid. A molecular crystal with
  Z′ < 1 needs a molecule on a special position whose site symmetry the
  molecule itself carries. #935's own case is a P2₁ organic salt at Z = 2,
  where P2₁/m would need the molecule on a mirror or an inversion centre. So
  decide between a hard exclusion and a reported, weaker statement for
  Z′ < 1, and record the reason here.
- **Rules that bind the work** (from 1967): each fact is read off the group's
  operators, never a table. `INDEXING_THRESHOLDS_VERSION` bumps when an
  answer can move. A new diagnostic code needs its skill row and its
  `rietx._audit` row with a tier.

## Non-goals

- The search's volume window and its Z check (WP-2030).
- Carrying the declaration on to `IndexingResult` or
  `structure_from_candidate` (1967's decision 3 holds).

## Tasks

- [ ] Every Wyckoff orbit size of a group, derived from its operators (the
      site orbits of the special positions plus the general position), held
      against ITA's multiplicities on one group per crystal class.
- [ ] Decide the Z′ < 1 rule (Context) and record it here as
      `Decided YYYY-MM-DD:`.
- [ ] `ExtinctionPrior` gains `z` and `density` (with the formula `density`
      needs). They are validated against each other where both are given,
      filtered as the other three are, and reported under
      `EXTINCTION_PRIOR_APPLIED`.
- [ ] Tests: #935's P2₁ case, an ionic case where Z excludes a group outright,
      and every extinction screen in the tree unchanged with nothing
      declared.
- [ ] Skill and audit rows for any new code or field. The manual's extinction
      page names the two new fields.

## Acceptance

A declared Z removes only groups whose orbits cannot hold the declared
content, and names each one. A declaration the data contradict ends in an
abstention, never in the declared answer. With nothing declared, every
extinction screen answers as on `main`.

```sh
.venv/bin/python -m pytest tests/test_extinction_prior.py tests/test_extinction_symbol.py -n auto --dist loadgroup
.venv/bin/python -m pytest tests/test_acceptance_indexing.py -n auto --dist loadgroup
.venv/bin/python -m ruff check src tests examples
```

## References

- Issue #935; PR #940; [WP-1967](1967-what-the-chemist-declares-reaches-the-extinction-screen.md).
- *International Tables for Crystallography* Vol. A, the Wyckoff positions
  (the multiplicities the derived orbits are checked against).

## Handover log

- **2026-10-23** — created by WP-1967's close, on the maintainer's decision to
  close 1967 and file this half on its own. No open WP owns a declared Z for
  the extinction screen. 2030 holds Z in the search, not the screen. 1910
  holds the screen at a small cell error.

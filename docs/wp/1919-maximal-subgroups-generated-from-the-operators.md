# WP-1919 — maximal subgroups, their conjugacy classes, (P, p) and Wyckoff splittings, generated from the group's own operators

Milestone: unscheduled · Status: ⬜
Track: Data and metadata in, a structure out
Depends on: — (1419 soft: the symmetry package its front half creates)
Priority: P3 2026-10-08 — a workaround covers it: MAXSUB and WYCKSPLIT by hand; its three consumers (1515, 1418, 1419) are queued or have a narrower stand-in

## Goal

`subgroups.maximal(group, ...)` returns every maximal t- and k-subgroup of a
space group up to index 4, and any isomorphic subgroup on demand, each with
its conjugacy class, its (P, p) to the standard setting verified exactly, and
`subgroups.wyckoff_splitting(group, sub)`. Nothing is read from a printed or
online table.

## Context

From issue #806 (mustachefeeling, 2026-10-07), with a working prototype on
the reporter's side. Three open threads need the group-subgroup step:

- #677 step 7 (folded into WP-1515): each maximal subgroup of the leading
  group is warm-started from the leader's solution, the pattern of the
  magnetic descent audit.
- #390 (WP-1418): that audit, `strategy/magnetic.py:1106`
  `_maximal_subgroups`, is maximal only among the other classes enumerated at
  the winner's own k. Its docstring says so.
- #418 (WP-1419's front half): a child group with its (P, p) for a
  displacive candidate.

Users building Bärnighausen trees go to Bilbao's MAXSUB and WYCKSPLIT by
hand today. The ITA A1 tables (2011) are not redistributable, and the
servers are not for automated use.

**The method**, all from ITA A1 ch. 1.2-1.7, 2.1 and 3.1, restated because it
decides the tests:

- Maximal subgroups are t or k (Hermann's theorem, A1 Lemma 1.2.8.1.3).
- t-subgroups correspond to maximal subgroups of the point group, since
  H/T ≤ G/T ≅ P. Conjugacy in G acts on G/T as conjugation in P.
- k-subgroups keep the point group on a P-invariant sublattice L' < L. H is
  maximal exactly when L/L' is an irreducible F_p[P]-module, so pL ⊆ L' and
  the index is p, p² or p³ (A1 Lemma 1.2.8.2.1). For each prime, the maximal
  P-invariant subspaces of F_p³ give L' = pL + U. The subgroups on one L' are
  the complements of L/L' in G/L', whose translation shifts solve a linear
  system over F_p. Every solution is one subgroup, so the list is complete
  by construction.
- Conjugacy classes: closure under G's generators and lattice translations.
- (P, p): spglib (BSD-3) identifies a probe structure's type and returns a
  transformation, then P⁻¹HP is checked exactly against the Hall-database
  group. A1 fixes one (P, p) of the set the affine normaliser relates; the
  proposal documents its own choice rule.
- Wyckoff positions from operators alone, as stabiliser-conjugacy classes
  (1731 over the 230 groups, ITA's total). A splitting decomposes the
  G-orbit of a generic point into H-orbits, mapped by (P, p). Letters come
  from spglib, as `wyckoff.site_constraints` (`crystallography/wyckoff.py:199`)
  does. A1 3.1.1.6.5 warns that another (P, p) permutes labels within a
  Wyckoff set, so the labels are stated as belonging to the chosen (P, p).
- Index ≤ 4 eagerly, which covers every non-isomorphic maximal subgroup
  (A1 Lemma 1.2.8.2.2). Isomorphic subgroups are infinite in number
  (A1 2.1.5) and come on demand, for an index, a prime or a supercell.

**The prototype's validation**, the reporter's: index ≤ 9 over all 230 types,
about 9300 maximal subgroups, each standardised exactly onto its Hall-database
group; closed-form isomorphic-series counts for P1 (p² + p + 1), P-1, P2,
P2/m, P4, P4/m, P3, P-3, P-6, P222 and Pmmm; every generated subgroup
re-derived from its (standard group, P, p) and checked as a subgroup and as
maximal, with the maximality test held to known non-maximal cases (P4 with
2a, 2b; P4 with 5a, 5b); multiplicity conservation Σ m_H = m_G·|det P| on
every splitting row; identical subgroup multisets across origin choices,
unique axes, cell choices, hexagonal and rhombohedral axes, and Cmce against
Ccmb. Cost: exact `Fraction` arithmetic, 13 CPU-minutes for all 230 groups
at index ≤ 9, at most 23 s for one group.

**Rules that apply.** The Rᵀ trap (root CLAUDE.md § Invariants): a
transposed rotation set is a group too, so every count passes under the
wrong action. The tests here assert that a named subgroup is present with
its (P, p), never only how many there are. Settings follow the space-group
setting, never the crystal system (`cell_constraints`'s rule).

**Licensing.** Concepts from ITA A1's text; no table is transcribed. spglib
is BSD-3 and already a dependency. Bilbao's servers are neither a source nor
an automated oracle; a published A1 entry may be quoted in a test as a
literature value. moyo (#426, WP-1452) would replace only the
identification call.

### Inherited

Empty at filing.

## Non-goals

- Magnetic subgroups (time reversal): M-7's isotropy subgroups, WP-1418.
  A magnetic descent may consume this list through its nuclear part.
- Minimal supergroups and the upward direction of #677's audit.
- Moving `irreps.py`, `modes.py` and `isotropy.py` into a symmetry package:
  WP-1419's front half (#418, decided 2026-09-23).
- The spglib-to-moyo migration: WP-1452.

## Tasks

- [ ] **Decision (maintainer):** placement. Under the symmetry package
      WP-1419 creates, or under `crystallography/` now (#806 question 1).
- [ ] **Decision (maintainer):** the (P, p) choice rule. A1-identical where
      it can be reproduced, or a documented canonical choice (#806
      question 2).
- [ ] **Decision (maintainer):** exact `Fraction` arithmetic as the prototype
      has it, or an integer implementation the reporter estimates at about
      10× faster (#806 question 4).
- [ ] t-subgroups from the point group's maximal subgroups, with conjugacy
- [ ] k-subgroups: maximal P-invariant sublattices per prime, complements
      over F_p, conjugacy classes
- [ ] (P, p) to the standard setting, verified exactly against the
      Hall-database group
- [ ] Wyckoff positions from operators, and `wyckoff_splitting`
- [ ] Isomorphic subgroups on demand (`index=`, `supercell=`)
- [ ] Tests: the closed-form series counts; a stated set of named maximal
      subgroups each present with its (P, p); the non-maximal controls;
      multiplicity conservation; the setting-invariance multisets; the 1731
      total. The full 230-group index ≤ 9 sweep as a `slow` test or a
      benchmark, as its cost decides
- [ ] Manual Part 2: the t/k construction and the F_p reduction with
      *Source* lines (ITA A1)
- [ ] Skill: none at first, since no fit reaches it until a consumer WP
      calls it; a row in the consumer's reference file when one does

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_subgroups.py -q
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

- Every maximal subgroup of index ≤ 4 of all 230 types standardises exactly
  onto its Hall-database group.
- The isomorphic-series counts match their closed forms for the listed
  groups and primes up to a stated bound.
- P4 with 2a, 2b and P4 with 5a, 5b are reported non-maximal.
- Σ m_H = m_G·|det P| holds on every splitting row.
- Two settings of one type give the same subgroup multiset.

## References

- Issue #806; #677 (WP-1515), #390 (WP-1418), #418 (WP-1419), #426 (WP-1452).
- *International Tables for Crystallography* Vol. A1, 2nd ed. (2011), ed.
  Wondratschek & Müller: ch. 1.2-1.7, 2.1, 3.1.
- Togo, A. et al., spglib (BSD-3).

## Handover log

- **2026-10-08** — created, from the 2026-10-08 issue triage (issue #806).
  Checked against the tree at `5d1f5f67`: no maximal-subgroup enumeration
  exists in `src/`; `_maximal_subgroups` (`strategy/magnetic.py:1106`) is
  maximal only among the classes found at the winner's k, as its docstring
  says; `wyckoff.site_constraints` takes letters from spglib; no symmetry
  package exists yet, since WP-1419 has not started. The prototype's counts
  are the reporter's and were not re-run. No open WP owns it: WP-1419 owns
  the package move and `distortion_candidates`, which take a child group from
  an irrep direction rather than enumerating subgroups; WP-1418's audit and
  WP-1515's #677 step 7 consume the list and do not build it.

# WP-1452 — spglib to moyo, once

Milestone: unscheduled · Status: ⬜
Track: The repo's own process
Depends on: 1327, 1418, 1419 (the v1.6 magnetic PRs carry most of the call sites)
Priority: P3 2026-10-10 — the round-trip failure that motivated it is fixed upstream (spglib 2.8.0, now the floor); what remains is Context's item 1, which library matches the BNS tables

## Goal

rietx calls moyopy wherever it calls spglib today, in one migration. Every
magnetic group round-trips, and every place the two libraries give
different answers is either matched or shown to be the right one.

## Context

Issue #426 (2026-09-23) and the maintainer's reply on its thread the same
day, which took the timing decision: **one migration, after the v1.6
magnetic PRs land**, so no in-flight branch is ported twice. No WP moves
the package to spglib's new error mode. moyo makes that moot, and the
`DeprecationWarning` noise (about 1530 from `test_magnetic_operators.py`
alone) is bearable until then.

**Call sites on `main`**, checked at `644dff84`: ten `spglib.` calls in
three files. `crystallography/magnetic/operators.py` has seven
(`get_magnetic_spacegroup_type`, `get_magnetic_symmetry_from_database`,
`get_spacegroup_type`, `get_magnetic_spacegroup_type_from_symmetry`).
`crystallography/wyckoff.py` has one `get_symmetry_dataset`, and
`indexing/reduce.py` has two. Since PR #389, `magnetic/isotropy.py` also
imports `spglib.error.SpglibError`. The magnetic branches will add their
own sites. The issue's table maps each call to its moyopy 0.19.0
counterpart (`MoyoDataset`, `SpaceGroupType`, `HallSymbolEntry`,
`MagneticSpaceGroupType`, `magnetic_operations_from_uni_number`,
`MagneticSpaceGroup`).

**The one semantic difference the reporter found.** moyo identifies a group
only from **primitive-basis** operations. Conventional-cell operator lists,
which rietx holds, fail on every centred group. The migration needs a
reduction step before identification.

**Why moyo**: spglib 2.7.0 fails the 1651-group round trip on UNI 282 →
275, 283 → none and 284 → 277, the three type-4 groups filed under No. 37
whose operators are No. 36 black-white groups. moyopy 0.19.0 passes all
1651. The maintainer's run reproduced this.

**Four differences a round trip cannot catch**, from the maintainer's run
(moyopy 0.19.0 against spglib 2.7.0, every kind of call on `main`):

1. **218 magnetic groups at a different origin.** The database lists
   differ for 221 UNI numbers: 282-284 and 218 in the 24 space-group
   families with two origin choices (48, 50, 59, 68, 70, 85, 86, 88, 125,
   126, 129, 130, 133, 134, 137, 138, 141, 142, 201, 203, 222, 224, 227,
   228). For UNI 355 (BNS 48.257) spglib puts the inversion at
   `-x+1/2,-y+1/2,-z+1/2` and moyo at `-x,-y,-z`. Every stored operator
   list and every magCIF in those settings moves. **Settle which library
   matches the Stokes & Campbell BNS tables before anything else.**
2. **moyo serves only the default setting.**
   `magnetic_operations_from_uni_number(uni, *, primitive=False)` takes no
   Hall number. `operators.magnetic_group(spec, hall_number=...)` and
   `database_settings` walk the alternative settings through spglib, so
   the migration builds them itself, probably by transforming the default.
   This is the largest piece of new code.
3. **Wyckoff letters differ on 215 of 136,416 sites** (`wyckoff.site_constraints`
   over all 564 gemmi settings on a 7-value coordinate grid, moyo in
   `Setting.spglib()`). The site-symmetry symbol agrees everywhere. Every
   difference swaps two positions of equal multiplicity and site symmetry
   (133 `8h` ↔ `8i`, 15 `4c` ↔ `4d`, 68 `4a` ↔ `4b`). A golden pinning a
   letter moves.
4. **The standardised cell is not idealised.** On `indexing/reduce.py`'s
   path (400 cells × 7 Bravais types × 3 `symprec`, 1200 cases), the
   space-group number and short symbol agree on all 1200. The cell agrees
   to 1e-6 on 959. The rest differ in axis order (Pmmm, P2/m, P4/mmm) or
   return the noisy metric (Im-3m: 89.9985° against spglib's 90°).
   `conventional_cell` would idealise it itself.

**Smaller facts.** Every moyo failure raised a plain `ValueError`.
`moyopy._moyopy.MoyoError` is not an exception class, so catch
`ValueError`. Speed is a wash (the Wyckoff sweep: 138.5 s spglib, 128.5 s
moyo, mostly rietx's own code). moyopy ships abi3 wheels for every CI
target under MIT OR Apache-2.0, so the licensing fence allows it. It is
pre-1.0, with six releases since 2026-07-04, so pin a version range. It
needs Python ≥ 3.10. spgrep depends on spglib, so spglib stays in `[dev]`
while spgrep is the irreps oracle.

**The reporter offers** the primitive-reduction helper, the 1651-group
acceptance test and a checklist of every magnetic golden that pins a
spglib convention, as PRs against the migration branch once it exists.

### Inherited

- **2026-10-10, from the fix for main's red CI: spglib 2.8.0 fixed the
  round trip, and rietx now requires it.** 2.8.0 (PyPI 2026-10-10) corrects
  the time-reversal flags of UNI 282-284. All 1651 groups now round-trip, and
  every type IV group's unprimed part is its family. Main's fast tier went red
  on every leg the day it shipped, because five tests pinned the defect. The
  fix raised the floor to `spglib>=2.8` and deleted `UNI_NOT_IDENTIFIABLE`. The
  unnamed path is now tested on `not_a_group()` in
  `tests/test_magnetic_operators.py`. **The 29-row sweep was the same
  defect**, and not the quarter-translation setting effect its comments
  claimed. On 2.7.0 an 8-operation subgroup in every row went unnamed. On
  2.8.0 all are named, some outside the 282-284 family (UNI 133, 275).
  `_identify_in_a_reduced_cell` may now be dead weight; that is not measured.
  **A crash for this WP's error handling:** spglib segfaults (exit 139, 2.7.0
  and 2.8.0 alike) on UNI 283's operators with the time-reversal flag of
  index 3 flipped. `identification` passes any list through, so a malformed
  list from a magCIF can kill the process. The "Why moyo" paragraph's first
  reason is now gone.

- **2026-10-02, from the issue triage (issue #426): the reporter holds no ITA
  Vol. A either, and one letter-rule data point.** Their reply of 2026-09-30
  (after the maintainer's) says the check of the printed Fd-3m tables has to
  be done from a copy on the maintainer's side; Bilbao's WYCKPOS served them a
  human-verification page. The data point, spglib 2.7.0 as a black box: the
  usual spinel description in `Fd-3m:2` (Mg ⅛⅛⅛, Al ½½½, O x x x with
  x = 0.2624) standardises to Hall 525 (origin choice 1) with origin shift
  (⅝, ⅛, ⅛), and the sites come back Mg 8b, Al 16c, O 32e. The usual labels
  are 8a / 16d / 32e. The two differ by the (½, ½, ½) normaliser shift, so
  both are valid, and the choice is the undocumented tie-break. A candidate
  test for decision (1): under origin choice 2 the rule gives 8a / 16d / 32e
  on the textbook spinel.

- **2026-09-30, from the issue triage (issue #426): the two rules only the
  maintainer can set, with a recommendation each.** *Evidence is thin*: the
  local paper corpus held no space-group, Wyckoff or Bilbao item, and no
  International Tables text was read. What was read: moyo's `setting.rs`
  (`Setting::Standard` is origin choice 2 for centrosymmetric groups;
  `Setting::Spglib` is the smallest Hall number, which is origin choice 1 by
  accident of numbering), and a gemmi 0.7.5 run (a bare `Fd-3m` resolves to `:1`).
  The remaining tool defaults (GSAS-II, FullProf, TOPAS, VESTA, pymatgen) are
  unchecked. **Decided 2026-09-30 (the maintainer left it to judgement; evidence thin, so the Fd-3m check in (2) gates the code):** (1) origin choice 2 for
  all 24 two-origin families on both the magnetic and nuclear paths, since it
  matches Bilbao, the ISO-MAG and BNS tables and moyo with no transform, and
  moves only goldens at hall 0 and 525; other Hall numbers follow the ITA
  setting transformation, not the normalizer, which has 1 to 92 160 candidates
  (median 64); (2) rietx writes its own Wyckoff-letter rule, matching a site's
  orbit to ITA's listed coordinates in the chosen setting, because the two
  libraries differ on 151 of 23 497 sites (spglib) and 215 of 136 416 (moyo) and
  no tool documents its tie-break; check it against the printed Fd-3m tables for
  `:1` and `:2` first, since the libraries disagree in opposite directions there.
  Record one golden per family with the inversion centre at (0, 0, 0), and a
  release-note line for the move.

- **2026-09-23, from the issue triage.** Issue #418 proposes moving
  `irreps.py`, `modes.py` and half of `isotropy.py` out of
  `crystallography/magnetic/`. Both changes touch the same files and both
  wait on the magnetic PRs, so whichever goes second rebases onto the
  first. WP-1419's Inherited carries #418.

## Non-goals

- The spglib error-mode move (moot; see Context).
- Removing spglib from `[dev]` while spgrep needs it.
- Magnetic symmetry search on a cell (`MoyoCollinearMagneticDataset`); no
  caller wants it today.

## Tasks

- [ ] Settle difference 1 against the Stokes & Campbell BNS tables, and
      record which library matches and what rietx does with the other.
- [ ] Primitive reduction before identification (take the reporter's helper
      if offered).
- [ ] Alternative magnetic settings built from the default, checked against
      spglib on every Hall number until they agree.
- [ ] Port the ten call sites and the error handling to `ValueError`.
- [ ] Idealise the standardised cell in `conventional_cell`.
- [ ] Re-derive every golden pinning a Wyckoff letter, Hall number or
      standardised setting, from the reporter's checklist.
- [ ] Tests: the 1651-group round trip with zero failures, UNI 282-284
      included; the settings agreement check; the fast selection and
      `tests/test_acceptance_indexing.py` (an engine is touched).
- [ ] Skill: none expected, since no user-facing name changes. Check
      `references/magnetic.md` if it exists by then.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_magnetic_operators.py tests/test_acceptance_indexing.py
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

## References

- moyo / moyopy (MIT OR Apache-2.0), 0.19.0.
- Stokes & Campbell, the ISO-MAG tables of magnetic space groups (BNS and
  OG settings).
- Issue #426 and the maintainer's reply of 2026-09-23.

## Handover log

- **2026-09-23** — created, from the 2026-09-23 issue triage (issue #426).
  Checked against the tree at `644dff84`: ten `spglib.` calls in three files,
  plus `isotropy.py`'s error import since PR #389. The timing and the four
  differences are the maintainer's, from the thread. Next: wait for the
  magnetic PRs, then settle difference 1 first.

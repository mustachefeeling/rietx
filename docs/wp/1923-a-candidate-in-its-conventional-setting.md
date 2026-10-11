# WP-1923 — A candidate is reported as a lattice in its conventional setting, and the reduction is an exact change of basis

Milestone: unscheduled · Status: ✅ 2026-10-11 — #797 and #779 fixed; release record v1.8
Track: What fires, and what stays silent
Depends on: — (1915 soft, the same file's covariance map)

## Goal

`index_pattern` reports each candidate in the IUCr conventional setting for its system (monoclinic: b unique, β obtuse and closest to 90°), keeps the engine's own setting and the change of basis in the record, and the Niggli-reduced form `reduction` returns is an exact change of basis of its input.

## Context

Two issues, one seam (`src/rietx/indexing/reduce.py` and how its output reaches `CellCandidate`).

**Issue #779 (mustachefeeling, 2026-10-06).** Candidates keep the engine's setting. `dedup_groups` compares on the Niggli-reduced metric, but the reported member is whichever setting the engine arrived at. The reporter saw β = 148.86°, 167.62°, 59.27° and 45.29° for one V = 224 Å³ lattice, whose conventional cell is a = 4.541, b = 4.884, c = 10.198 Å, β = 98.22°. Grades and Le Bail fits are setting-invariant. The harm is to a reader comparing against a database or `SearchSpec.prior_cells`, and to code assuming β in 90-120°. Whether the change belongs in the engines, in `consensus` or only in the report is open. The reporter proposes the report.

**Issue #797 (maintainer, 2026-10-06).** For the triclinic cell (3.0, 11.0, 14.197202585325392, 65, 65, 65), `reduction(af)` returns `(red, t)` with `t @ af` differing from `red` by (−4.0e-8, −4.0e-8, −4.0e-8, −2.5e-7, −1.2e-5, −1.0e-6) relative. `t` is an integer map, so `t @ af` is exact. `tests/test_indexing_reduce.py::test_the_reduction_map_takes_a_to_f_where_the_reduction_does` draws it from a local hypothesis database. CI draws it only by chance. `@example(3.0, 11.0, 14.197202585325392, 65.0, 65.0, 65.0)` would make CI see it.

**Traced on 2026-10-08** (gemmi, `[dev]`, macOS arm64, `scratchpad` script `trace-797.py`). Direct-space parameters out of `niggli_reduce` + `normalize` equal the exact image of the input G6 under the recorded triplet to 4e-16 at ε = 1e-12. At ε = 7.2e-5 (`NIGGLI_EPS_RELATIVE` · V^(1/3)) every parameter still equals that image except E, which has the opposite sign, with |E| = 1.75e-5 inside ε. So the drift is `normalize` choosing a sign for a parameter it treats as zero. Flipping one sign is not a change of basis. `reduction`'s existing row flip makes `t @ af` agree with `red` in that sign and leaves the metric one ε away from the input's. The fix is not yet chosen.

**Re-traced 2026-10-11 (folded from the #843 triage, a duplicate of #797): the sign is chosen inside `niggli_reduce`, not `normalize`.** At 7d9be3cb (`[dev]`, macOS arm64) the G6 vector straight out of `niggli_reduce` already carries η = −1.753e-5 against the exact image's +1.753e-5, and its other five parameters match that image to 1.7e-16; `normalize` changes nothing. The flip moves the metric by 2|η| = 3.5e-5 on a G6 vector of scale 202, which is #843's 2.3e-7 of max|red| in reciprocal A..F. A machine whose `.hypothesis/` database replays the cell fails this test on every gate run until task 2 lands.

## Non-goals

- Changing what the engines search or how `dedup_groups` groups. The reduced metric stays the identity.
- Choosing the monoclinic convention for the other crystal systems beyond what `conventional_cell` already does. Triclinic stays Niggli-reduced.
- Loosening `NIGGLI_EPS_RELATIVE`. Its value is the paper's (Grosse-Kunstleve, Sauter & Adams 2004) and its measurement is in the constant's comment.

## Tasks

- [x] Add the `@example` to the existing test so CI draws the 797 cell, and confirm it fails on 5d1f5f67. (Fails on 6075319c, `reduce.py` unchanged since 5d1f5f67: rel (−4.0e-8 ×3, −2.5e-7, −1.2e-5, −1.0e-6).)
- [x] Make the near-zero sign step an exact image: either decide the sign from the exact image of the input, or carry the ε-sized difference as a stated tolerance of `reduction` and have `same_lattice` count it. Measure how often an indexing run meets such a cell first (the 797 text says it is unmeasured). (The first: `reduce_cell` builds the cell from M·G·Mᵀ wherever a sign disagrees with it, and `reduction`'s row flip is gone. Measured over `test_acceptance_indexing.py`: a sign disagreed in ~4.5 % of reductions, almost all a right angle's rounding, none at #797's ε scale — numbers in the handover.)
- [x] Decide where the conventional setting is applied (report only, per #779's proposal, or consensus). Record the engine's cell and the change of basis on `CellCandidate`, quoting the new fields from one place (WP-1076: a field's default needs its writer named). (In `engines.to_cell_candidate`, which consensus calls: a report-only pass could not re-derive `cell_esd`, whose covariance lives on `CandidateFit`, and would have had to patch supercell parent cells, ambiguity transformations and diagnostics after the fact. `engines.conventional_fit` carries af, `cov_af`, cell and esds through `reduce.af_map`; `CellCandidate.engine_cell`/`.change_of_basis` are written there on every candidate, the identity where nothing moved, `None` only on one built elsewhere. `INDEXING_THRESHOLDS_VERSION` 1.7 → 1.8.)
- [x] Report monoclinic candidates with b unique and β obtuse, closest to 90°. Cross-check against `conventional_cell` and `ambiguity.py`, which reduce independently. (`reduce.conventional_setting`: P is Lagrange-Gauss reduced in the ac-plane with a ≤ c; C keeps (a+b)/2, so a′ = p·a + q·c with q even and no swap; then a → −a for β obtuse and b → ±b for handedness. Held equal to spglib's `std_lattice` by property test on P and C. `ambiguity.py` runs on the reported `CellCandidate`, so its partners' transformations are relative to the conventional basis without change.)
- [x] Check every reader of a candidate's `cell`: the GUI indexing panel, `evidence()`, `prior_cells` matching, `rank_of_lattice` in `tests/indexing_gallery.py`, the skill's indexing reference. (GUI displays `cell` and adopts through `structure_from_candidate`, lattice group plus cell, both preserved; `evidence()` copies `cell`; prior matching uses `same_lattice`; `rank_of_lattice` reduces `af` and compares centring, which the re-set keeps; `provisional_payload` now re-sets too.)
- [x] Tests (unit/property; acceptance if this WP carries it). Run `tests/test_acceptance_indexing.py`, since the change touches consensus output. (Property: the reduced cell is M·G·Mᵀ in five centrings, and the monoclinic re-set equals spglib's `std_lattice` on P and C; unit: the covariance carried, `to_cell_candidate` on P, C and identity. Acceptance 44 passed on the final tree, `[dev]`, Linux x86-64, alone.)
- [x] Skill: the indexing reference row saying which setting a reported cell is in, and where the engine's lives. (`diagnostics-indexing.md` §7d point 6, paid for by a cut in point 3; manual `using/indexing.md` § One candidate.)

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_indexing_reduce.py tests/test_indexing_consensus.py -n auto --dist loadgroup
.venv/bin/python -m pytest tests/test_acceptance_indexing.py -n auto --dist loadgroup
.venv/bin/python -m ruff check src tests examples
```

On the 797 cell, `max(abs((t @ af - red) / red))` is under 1e-9. A synthetic P 1 2/m 1 cell of 4.541, 4.884, 10.198 Å, β = 98.22° indexed through `index_pattern` is reported with β in 90-120° (on 5d1f5f67 candidate 0 comes back as β = 81.78°).

## References

- Grosse-Kunstleve, Sauter & Adams (2004), *Acta Cryst.* A60, 1-6 (the relative ε).
- Mighell & Santoro (1975) for the setting ambiguity already named in `indexing/CLAUDE.md`.
- International Tables for Crystallography A, § 9.3 (reduced and conventional cells).

## Handover log

- **2026-10-11** — closed. An indexing candidate is now reported the way a
  database or a paper writes its lattice. A monoclinic cell comes back b-unique
  with β obtuse and a, c the shortest translations normal to b, where it used to
  keep whatever setting its engine reached (#779's β = 81.78° is now 98.22°).
  The engine's own cell and the integer change of basis stay on the candidate.
  Under that, a reduced cell is now an exact change of basis of its input, where
  a sign gemmi picked inside ε could leave it one ε away (#797, #843). Grades,
  ranks and Le Bail fits are setting-invariant and did not move. What remains
  is WP-1932's comparison across a reduction boundary, now on a tree where one
  of its boundary classes moved.

  *Done.* (1) `@example` for the 797 cell; it failed on 6075319c. (2)
  `reduce_cell` builds the cell from M·G·Mᵀ wherever an entry's sign disagrees
  with it, and gemmi's cell is kept to the bit elsewhere. `reduction`'s row flip
  is gone, because T is now the whole map. (3)-(4) `reduce.conventional_setting`
  (P: Lagrange-Gauss in the ac-plane, a ≤ c; C: q even, no swap; then β obtuse,
  b → ±b for handedness), `reduce.af_map`, and `engines.conventional_fit`,
  applied in `to_cell_candidate` and in `provisional_payload`.
  `CellCandidate.engine_cell` and `.change_of_basis` are written by
  `to_cell_candidate` on every candidate, the identity where nothing moved;
  `None` means a candidate built elsewhere. `INDEXING_THRESHOLDS_VERSION` is
  now 1.8. (5) Readers checked; none needed a change (the item's own note). (6)
  The tests below. (7) Skill §7d point 6, paid for by a cut in point 3, and the
  manual's § One candidate. Indexing CLAUDE.md: two rules, cap 323 → 328.

  *Where, and why not report-only.* #779 proposed re-setting in the report.
  That cannot re-derive `cell_esd` when a step mixes a and c, because the
  covariance lives on `CandidateFit`, not on `CellCandidate`. It would also
  have had to patch supercell parent cells, ambiguity transformations and
  diagnostics after they were built. `to_cell_candidate` is the one place an
  engine answer becomes a reported one, and consensus, the streamed per-system
  snapshot and `evidence()` all pass through it.

  *Measured* (`[dev]`, Linux x86-64, 4 cores). The 797 cell's
  max |(T·af − red)/red| went from 1.2e-5 to 6.8e-16. The #779 synthetic cell
  through `index_pattern` (monoclinic only, 154 s on a loaded machine) gives
  candidate 0 at β = 98.2200°, `engine_cell` β = 81.78°, change
  ((−1,0,0),(0,−1,0),(0,0,1)). The sign step over 27 300 reductions of
  `test_acceptance_indexing.py`'s searches (the run was killed partway, on the
  task-2 tree with a temporary trace): 792 had a sign to correct, 447 distinct
  cells; 440 of them by under 1e-14 of the metric's scale, 7 by 1e-14 to
  1e-10, none at or above 1e-10 (797 is 1.7e-7). Acceptance on the
  pre-review branch: 44 passed, 21:04 alone. Merged tree (main at
  0f30d584): fast `-m "not slow"` 9154 passed, 186 skipped,
  2 xfailed (15:59); indexing acceptance 44 passed (20:38), each alone. Added:
  15 cases over 7 tests, all passes (14 in `test_indexing_reduce.py`, one of
  them a case on an existing parametrisation; 1 in `test_indexing_consensus.py`).
  No full-suite run: on 4 cores it would run for hours, and the one measured
  number this moves is the indexing acceptance, run twice above.
  The added tests cost 0.61 s in that run (0.29 s the exact-image property,
  0.25 s the re-set property); none joins the slow tail.

  *Review* (`/code-review high --fix`, 17a37045). Four fixes taken.
  (a) Rounding decided three ties (the β flip at 90°, the P swap at a = c, a
  Gauss ±½), so the re-set was not idempotent: fuzzed, >10 of 20 000 settings
  re-set again; a 1e-12 tolerance takes it to 3, all with cells over 200 Å.
  (b) A non-finite or non-positive-definite af raised out of consensus; it now
  has no setting. (c) The skill row read as cell == engine_cell. (d)
  `conventional_fit` exported. Declined: the image costs `reduce_cell`
  ~4.5 → ~22 µs (≈0.5 s over the acceptance file's reductions), and a cheaper
  path is a second metric formula or a skipped check; `provisional_payload`
  maps a covariance it discards, at most three cells a unit.

  *Gotchas.* gemmi's `is_niggli` tests signs without ε and fails gemmi's own
  output on fp ties, so it is no oracle for the exact image. The test holds
  the image within ε of gemmi's vector instead. The worktree hook refuses a
  Bash line that both sets a variable and runs a heredoc'd python; write
  the script to the scratchpad.

  *Forward.* WP-1932's Inherited: the 1 670 bethanechol splits "at g4/g5/g6 =
  0" were counted on a reduction this tree no longer runs. Its priority is
  unchanged, since it never depended on this one.

  *Next.* Nothing on this WP. Whoever takes 1932 recounts its splits first.

- **2026-10-08** — created, from the 2026-10-08 issue triage (issues #779, #797). Checked against the tree at 5d1f5f67: #797 reproduces (drift −1.15e-5 on E, −4.0e-8 on A, B, C); #779 reproduces on a synthetic P 1 2/m 1 cell of 4.541, 4.884, 10.198 Å, β = 98.22° (candidate 0 comes back as 4.541, 4.884, 10.198 Å, β = 81.78°); `git log --since=2026-10-06 -- src/rietx/indexing/reduce.py` is empty and no PR cites either issue. No open WP owns it: 1915 owns the NaN esd through `reduced_covariance` and says nothing about the reported setting or the exactness of the map, 1520 and 1510 are search cost and priors, and 1518 (closed) built `reduction`'s map and did not check it against a near-zero parameter.

# WP-1535 — A direction the covariance discards reads as measured

Milestone: unscheduled · Status: ✅ 2026-10-02 — shipped as COVARIANCE_DIRECTION_DISCARDED; esds left, see handover
Track: What fires, and what stays silent
Depends on: —

## Goal

When two or more live columns are exactly degenerate, the parameters that
direction touches report no esd rather than a small one. This is WP-1110
item 14's rule, extended from a single column to a combination of columns.

## Context

**What WP-1534 measured (2026-10-02).** The equilibrated normal matrix goes
to `pinv` with `PINV_RCOND` (1e-15, `optimize/statistics.py`). An eigenvalue
under the cut is *discarded*, so its direction comes back with **zero**
variance. Each parameter's esd then shows only its projection onto the
directions the data did measure. On a 25–50° Cu Kα mixture, bcc Fe's scale
and B columns were collinear to rounding (1 − |cos| = 2.2e-16). Their
direction's eigenvalue was −3.8e-18 against a cut of 2.9e-15. Fe's scale came
back "measured to 2.7 %", and its fraction read 0.000 ± 0.000 wt% at
B = −150 Å². `_cov_free` and `ParameterTable.unmeasured_rows` catch a column
with **no** gradient. Nothing catches a combination with none. WP-1534 holds
the scale–B shape before the solve (`SCALE_B_INSEPARABLE`), which removes the
direction from that pair, but every other exactly degenerate pair is
untouched.

**Measured 2026-10-02 (task 1; numpy, Darwin, `[dev]` venv, worktree `pure-frolicking-bubble`).**
A pytest plugin wrapped `statistics.normal_factors`, re-formed the equilibrated
matrix, and counted eigenvalues with |λ| ≤ `PINV_RCOND·|λ|max` that load on two
or more live columns (a one-column cut is a dead column, already handled).

- **Fast selection**: 3 100 whole-pattern solves, 24 with such a direction
  (0.8 %). Pawley overlap groups (intensities, already
  `PAWLEY_OVERLAP_UNRESOLVED`) and tests that build a degenerate pair on
  purpose. No ordinary Rietveld fit.
- **`-m slow` (the acceptance fixtures)**: 1 899 whole-pattern solves, 183 with
  one (9.6 %), 461 directions in all. They sit in the headline fixtures:
  cpd-1a QPA (round-robin, dispersion, sequential), SRM 676a's two R
  descriptions, brucite March–Dollase and Stephens, the surface-roughness
  pure phases, the Cr₂WO₆ 150 K pattern. Depth below the cut, |λ|/cut:
  88 in 0.5–1, 226 in 0.1–0.5, 146 in 0.001–0.1, 1 under 1e-3. So most are
  at the rounding floor rather than far under it, and they load on 4–8
  columns, not a pair.
- **Occupancy against scale (confirmed)**: one-site bcc Fe, 20–100°, scale and
  `occ` free, from 1e-4 and 0.8. The direction's λ is 3.1e-16 against a cut of
  2.0e-15, loaded 0.707/0.707, and the fit returns scale 1.84e-4 ± 4.5e-6 and
  occ 1.039 ± 0.0127, with `HIGH_CORRELATION` and `FLAT_DIRECTION` beside them.
  Both esds are confident; the pair is exactly degenerate.
- The one red row in the slow selection, `test_watch_app.py::…scratch_copy…`,
  passed alone (4.6 s): load, not this.
- `normal_covariance` (indexing's per-peak fits) has 144 such solves in the
  slow selection, all two-column pairs; out of this WP's whole-pattern scope
  and not examined further.

**Candidate shapes (hypothesis; the first is confirmed above).**

- A one-site phase's occupancy against its scale. |F|² ∝ occ², so on any
  range the occupancy is exactly a reparameterisation of the scale.
- A phase's displacement against its scale on an all-anisotropic phase, which
  WP-1534's probe skips because it has no isotropic site to step.
- Any user tie or `vars.X` that makes two free columns identical.

**Why this is not a one-line fix.** Marking every parameter that a discarded
eigenvector touches would change the esds of every fit that has such a
direction. The moment probe's docstring (`refine.MOMENT_DIRECTION_SUPPORT`)
records the same reluctance about widening `_cov_free`. So measure first: how
many fits in the acceptance suites have a cut direction at all, and which
parameters it touches.

**Machinery.** `statistics.normal_factors` (the cut), `covariance_from_factors`
(where `inf` is written for a dead column), `ParameterTable.unmeasured_rows`
and the "consumers mark, never clamp" rule (root CLAUDE.md, WP-1110 item 14),
and WP-1460 (how a flat direction is *reported*; this WP is about its *esd*).

## Non-goals

- Reporting the pair once. That is WP-1460.
- Holding anything. WP-1534 holds the scale–B shape; a hold for another
  shape is a WP of its own once this one has measured it.

## Tasks

- [x] **Measure first.** Count discarded eigen-directions (eigenvalue under
      `PINV_RCOND × λmax`) across the fast suite's fits and the acceptance
      fixtures, and record which parameters each one touches. Build the
      one-site occupancy–scale case and confirm or refute the hypothesis.
- [x] Decide from the count: mark the touched parameters unmeasured in the
      covariance, or add a finding naming the direction and leave the esds.
      Write down the threshold for "touches" (a loading on the discarded
      eigenvector), derived, not tuned.
      **Decision (2026-10-02): a finding, esds left.** 9.6 % of the acceptance
      solves cut a direction, at the rounding floor and over 4–8 columns, so
      marking would blank esds across the QPA, SRM 676a and brucite fixtures
      on a threshold the arithmetic cannot defend. The pair case is already
      covered by `FLAT_DIRECTION` (|ρ| ≥ 1 − 5e-4, and it already says each esd
      is conditional); the gap is a combination of three or more columns, where
      no pairwise ρ reaches it. New guard `COVARIANCE_DIRECTION_DISCARDED`
      (`GuardReport.discarded_directions`), computed in `check_guards` from
      `outcome.jac`, which is where `background_absorption` already reads it.
      **"Touches", derived:** the true eigenvalue of a discarded direction is at
      most the cut, so it adds at least v_i²/(PINV_RCOND·|λ|max) to column i's
      equilibrated variance. Column i is touched when that is at least the
      variance the solve reports, Σ_kept v_i²/λ — the esd is then at least √2
      short. A direction whose touched set is exactly a pair `FLAT_DIRECTION`
      already reported adds no row.
- [x] Tests, and the record line or diagnostic that states what changed.
- [x] Manual Part 2: the equilibrated cut in `estimation.md`, beside
      WP-1534's ridge section.
- [x] Skill: the row for whatever the decision adds.

## Acceptance

No exactly degenerate pair on the fixtures returns a finite esd for a
parameter its discarded direction touches, or a finding says which esds are
conditional.

```sh
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

## References

- WP-1534 (the measurement), WP-1110 item 14 (equilibration), WP-1463
  (column rescale), WP-1460 (reporting a degeneracy once).
- van der Sluis, A. (1969). Numer. Math. 14, 14–23.

## Handover log

- **2026-10-02** — The covariance cut that gives a discarded direction zero
  variance is not rare, and a pair test cannot see most of it. On the
  acceptance fixtures about one whole-pattern solve in ten discards a direction
  that spans four to eight columns, and a typical case is the sample-broadening
  block of a QPA mixture: size, strain and the instrument widths trading off
  against each other. Those fits now carry a warning, `COVARIANCE_DIRECTION_DISCARDED`,
  naming the parameters whose esds are at least √2 short. The esds themselves
  are unchanged, because blanking them would have emptied the headline fixtures
  on a threshold that rounding sets. A one-site occupancy against its scale is
  confirmed as an exact degeneracy, and it was already reported as a flat pair.

  *Done.* Task 1 measured it (below). Task 2 decided a finding over a mark:
  `statistics.discarded_directions` (eigenpairs of the equilibrated normal
  matrix under the cut, the touched test summed over the discarded subspace),
  `check_discarded_directions` and `GuardReport.discarded_directions` in
  `strategy/staged.py`, one `Diagnostic` in `refine._guard_diagnostics`, and the
  joint-fit twin in `multi.py` (`GUARD_SCOPES`: FIT). Retaken on the answer stage
  through `_REVISABLE_CODES`. Skipped when a Pawley block is present (the cut
  matrix includes intensities `outcome.jac` omits), when no covariance exists,
  and when the Jacobian width differs from `free_paths`. A touched set inside a
  pair `FLAT_DIRECTION` already reported adds no row. Tests in
  `tests/test_discarded_direction.py` (8). Manual Part 2: `estimation.md` §
  "A combination of three or more", eq. `est-discarded-touch`, beside
  WP-1534's ridge. Skill: one row in `references/diagnostics.md`, paid for by
  trimming the `FLAT_DIRECTION` and `FLAT_DIRECTION_OMITTED` rows (the skill's
  byte budget; the dropped sentences were the sign note, the `axial_sl ~
  axial_hl` example and "rides beside … loses nothing").

  *Measured* (numpy, Darwin arm64, `[dev]` venv in this worktree, one session
  alone on the machine for the full run). Probe: a plugin wrapping
  `normal_factors`, counting eigenvalues |λ| ≤ `PINV_RCOND·|λ|max` loading on
  two or more live columns. Fast selection: 24 of 3 100 whole-pattern solves
  (0.8 %), all Pawley overlaps or pairs built on purpose. `-m slow`: 183 of
  1 899 (9.6 %), 461 directions, 88 at 0.5–1 of the cut, 226 at 0.1–0.5, 146 at
  0.001–0.1, 1 below; in cpd-1a QPA (round-robin, dispersion, sequential),
  SRM 676a's two R descriptions, brucite March–Dollase and Stephens, the
  roughness pure phases and the Cr₂WO₆ 150 K pattern. After the build, on
  three acceptance files (29 tests): 64 of 237 guard calls carry the finding,
  and on cpd-1a it names `lor_size`, `lor_strain`, `gauss_size`, `gauss_strain`
  and the profile W/X/Y. One-site Fe, scale and `occ` free: λ 3.1e-16 against a
  cut of 2.0e-15, scale 1.84e-4 ± 4.5e-6, occ 1.039 ± 0.0127. Counts: fast
  selection after the review fixes, before merging main, 7929 passed, 159
  skipped (2:30); the 8 added tests cost 0.01 s together there. Full selection
  on the tree merged with origin/main (six commits in), 8186 passed, 170
  skipped, 18:13, alone. The earlier full run, before the review fixes, was
  8185 passed, 170 skipped (23:37): +1 is the review's added test. I did not run
  a baseline on main.

  *Review* (`/code-review high --fix`, 8 findings). Fixed: the code was not in
  `_REVISABLE_CODES`, so it printed once per stage (a test added). I fixed four
  more by hand: a single touched column was dropped (`len >= 2` where `>= 1`
  was meant), a Pawley solve analysed the wrong matrix, a fit with no covariance
  still warned about esds, and a width mismatch could mislabel columns. Declined:
  the extra `eigh` and Gram build per stage (not timed; worth a number if the
  stage charge is ever judged, WP-1413), `value` being the
  count of all discarded directions (reworded the message instead), and the
  absence of a staged end-to-end test and a joint-fit test. The stage-loop path
  has the membership assertion and the acceptance runs, nothing finer.

  *Gotchas.* `discarded_directions` rebuilds the equilibrated matrix rather than
  reading `normal_factors`' own eigendecomposition, so the two agree only while
  `normal_factors` keeps its Jacobi scaling and its cut; both read
  `PINV_RCOND`. The 144 `normal_covariance` solves of the indexing peak fits (all
  two-column pairs) were counted and not examined. A series' per-pattern
  repeat of this finding is not deduplicated by `sequential`; HIGH_CORRELATION's
  "N of M" does not cover it yet.

  Next: nothing open here. If the stage charge is ever judged, move the
  eigendecomposition into `normal_factors`' return and derive `touched` from it
  (WP-1413's test is the shortest fit). If a series shows the finding in every
  pattern, `sequential._persistent_diagnostics` needs the code added to its list.

- **2026-10-02** — filed from WP-1534's handover. No open WP owns the esd of
  a discarded *combination*: 0407 and 1056 are closed, and 1460 reports pairs
  without touching their esds. Next: task 1's count, because it decides
  whether this is a covariance change or a finding.

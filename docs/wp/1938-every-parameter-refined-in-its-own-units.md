# WP-1938 — every parameter refined in its own units

Milestone: unscheduled · Status: ⬜
Track: What fires, and what stays silent
Depends on: 1936 (the FD step, landed 2026-10-09), 1937 (a driver that handles widths on zero, landed 2026-10-10)
Priority: P1 2026-10-10 — was P2: WP-1937 landed, nothing blocks it, and it now carries the default-driver flip WP-1929's P1 rests on

## Goal

The solver refines every parameter in physical units, with its declared
`min`/`max` passed to the driver as box bounds. Softplus, logit and exp stop
being solver coordinates. A fit whose minimum sits on a floor reaches the same
point and reports the same esds on every platform, with no seed and no
special case for a tiny column.

## Context

**Why** (WP-1929's second session, 2026-10-09; macOS arm64, `[dev]`, tree
`35f4ac14`). Softplus p = log(1 + eᵘ) (`params/transforms.py`; a lower bound
≤ 1e-12 maps to internal −∞) does two harmful things near zero. Its column
is expit(u)·∂r/∂p, so a step in u moves p below rounding and the column is
noise that equilibration turns into a direction: BT-1's `profile.x` esd came
out 0.0032, 0.0066 or 0.0089 at one χ² depending on where u stopped. And its
gradient vanishes, so rounding chooses whether a floored width ever leaves
(WP-1930): LaB₆ + cBN reached four minima, χ²_red 9.69–12.51, across five
starts nudged by 1e-14. With softplus entries made identity and
`lo = max(lo, 0)` (a monkeypatch of `ParameterTable.__init__`), TRF reached
one minimum on every fit except where TRF's own bound handling crawls
(WP-1937), and BT-1's `profile.x` esd was 0.0098437 at every stopping point,
the value a hand-computed physical column gives.

**What a softplus coordinate was buying.** Log-like steps for a value near
zero, so a floored width stops moving and redundant widths settle (why
brucite and corundum converge under softplus + TRF). An active-set driver
(WP-1937) does that explicitly. A per-parameter FD scale (WP-1936) replaces
the relative step softplus gave by accident.

**Readers that branch on the word** (the adversarial review's list, and a grep
of the merged tree). Each would silently change meaning:

- `ParameterTable.seed_softplus` (`params/vector.py`, the `transform ==
  "softplus"` filter): `Stage.seed` and `suggest()`'s probe
  (`SUGGEST_SEED_SOFTPLUS`, `refine.py` near `seed_softplus(cand_paths`) do
  nothing under identity. The review measured a joint `lor_size` stage
  starting at cost 1 022 348 instead of 990 890. Decide per caller whether a
  seed is still needed once the gradient at a floor is physical.
- WP-1930's `seed_floor` / `FLOOR_SEEDS` / `SOFTPLUS_FREED_AT_FLOOR`
  (PR #849, not on `main` at this writing) exist only because of the trap.
- `io/recipe.py:739` and `:771`, `io/instrument_profile.py:1301`.
- `schemas/common.py`: `_TRANSFORM_ENFORCES`, `Parameter.positive`, and the
  `TransformKind` literal.
- `strategy/staged.bound_untested` (WP-1463): a floor becomes an ordinary
  bound, so the function and its `None` third state go.
- `backend/linalg64.column_agreement`'s 1e-12 skip; `backend/traced.py`'s
  transform application; `gui/textdoc.py`'s `softplus`/`logit` flag words;
  three `help.py` texts; `viz/compare.py` and the `io/projects/` writers
  that build `transform="softplus"` parameters.
- Root CLAUDE.md: the "softplus `min=0.0` … a pole at zero" invariant, the
  WP-1463 "a tiny column is live" clause in the equilibration invariant, and
  the parameter-system line of `docs/DESIGN.md` ("softplus for widths and
  scales (hard lower bounds stall TRF)"), which this WP's measurements answer.

**The stored field.** `Parameter.transform` is in every saved project, `.rxt`
document and history line. Old files must always open (root CLAUDE.md,
breaking by direction). So a stored `"softplus"` reads as "bounded below at
`max(min, 0)`", `"logit"` as `[max(min, 0), min(max, 1)]`, and the field is
either migrated away at the read points (`schemas/migrate.py`) or kept inert.
A pole at zero still needs a real floor (`MARCH_R_MIN`), which is now just a
`min`.

**Every pinned number moves.** Most acceptance fits agree between the two
coordinate systems to 1e-9. LaB₆ + cBN and the joint `lor_size` fixture do
not (the review: χ² 4.2987 against 4.0619 at parameters within one esd, both
a poor basin). VALIDATION.md's rows and the landing page are re-measured.

### Inherited

- **2026-10-10, from WP-1937 (maintainer decision): the default-driver flip
  lands here, with the coordinates, in one PR.** Each half alone is worse
  than today. Grid of `examples/probe_driver_grid.py` (14 acceptance fits,
  five starts nudged by 1e-14, macOS arm64, `[dev]`, `src` at `790c7ce7`),
  fits whose χ²_red spread is over 1e-9: softplus + TRF (today) 3, softplus
  + LM 7, physical + TRF 4 with `max_iter` on brucite, corundum and brucite +
  Stephens, physical + LM 2 with no `max_iter` anywhere. Residual
  evaluations over twelve fits: 1292 today, 1065 physical + LM, 2717
  physical + TRF. In softplus coordinates the exact LM step drives widths to
  u ≈ −400, their columns die, and stages end on `ftol_runs` after moving
  Biso by 4e-9, so softplus + LM must never ship as the default. The full
  table is in WP-1937's 2026-10-10 handover entry.
  - *Moved here from 1937's checklist.* Flip `solver=` to `"lm"` in every
    signature that defaults it (`refine.py` ×4, `multi.py` ×2,
    `sequential.py` ×2, `project.py` ×2, both `run_*least_squares`,
    `LSQOutcome.solver`), as one constant; `Provenance.solver`'s `"trf"`
    default stays, since every old record was TRF. Keep `"trf"` selectable.
    Rewrite `lm.py`'s module docstring: re-measure "not a speed play" and
    "prefer the default driver on a texture plan" with
    `examples/bench_solver.py`. Rewrite `docs/manual/estimation.md` §
    Solvers (add `stark1995`), `using/refining.md` near the
    `solver="trf"` example and the `n_constraint_truncations` paragraph, and
    `using/first-refinement.md`'s `solver=trf` provenance line. Every text
    saying the Stephens cone is a guard "under the default TRF driver"
    changes: root CLAUDE.md's anisotropic-strain clause,
    `strategy/staged.check_stephens_positive`, `refine.py`'s
    `CONSTRAINT_ACTIVE` suggestion, `help.py`, `crystallography/stephens.py`,
    `viz/compare.py`, `schemas/structure.py`, and the skill's
    `STEPHENS_STRAIN_NOT_POSITIVE` and `CONSTRAINT_ACTIVE` rows. A joint fit
    builds no cone under LM (`run_multi_least_squares`), so the guard still
    fires there. Regenerate the skill's `api.md`. PNGs for the fits whose
    answer moves.
  - *Task: brucite's valley.* Physical + LM spreads 1.1e-8 on brucite
    (isotropic). Two exactly degenerate Lorentzian pairs (`profile.y` with
    `lor_strain`, `profile.x` with `lor_size`) split differently per start,
    and `axial_sl` ends at 0.2 or under 3e-10. A final ftol of 1e-12 leaves
    1.4e-8. Hypothesis: the Γ_G² < 0 clamp (`u` = −0.049) makes the
    objective piecewise at that level. Today's default reaches 1.7e-9 on the
    same fit. Establish the mechanism, then fix it or give brucite its own
    bar with the reason.
  - *Task: the cone stall.* Physical + LM spreads 1.6e-6 on brucite +
    Stephens. `sample_broadening` truncates 8 steps against the strain cone
    and stops `exhausted_fp64`, and the S_HKL differ at 7e-5 relative. BVLS
    holds boxes only, and the cone is projected and truncated around the
    step (`lm.LinearInequality`, `lm.minimize`'s inner loop). Hold the cone
    inside the step's quadratic programme, or show the stall moves no
    quoted number. Under LM brucite + Stephens reaches χ²_red 8.00056
    against TRF's 7.636, a point outside the cone.
  - *The 16 suite failures under physical + LM*, out of 455 tests in the
    files 1937's item named, slow included; TRF passes all 455. Two are
    expected: `test_acceptance_stephens`'s
    `test_unconstrained_solver_leaves_the_cone_on_the_same_data` and
    `test_brucite_improvement_is_justified_but_leaves_the_physical_cone`
    assert TRF's cone-leaving point, so their fixture names `solver="trf"`.
    Four come from the coordinates alone and fail under physical + TRF too:
    `test_acceptance_lab6_cbn`'s seeded-set assertion, and three in
    `test_multi_histogram` (a seed that lands on `lor_size`, and the
    `CELL_RUNAWAY` pair, whose cell no longer runs away). Five in
    `test_lebail_alternation`: LM's pass 1 lands on the 13.865 % fixed point
    the docstring describes, where TRF stops at the pinned 0.138453.
    `test_magnetic_series::test_the_ascent_out_of_the_floor_terminates_at_once`:
    with `max_iter=1` LM leaves the moment on its 0.001 floor, where TRF
    reaches 2.73 in four evaluations. `test_magnetic_solve`'s budget-stop
    continuation: LM converges both one-iteration stages, so nothing is
    continued. `test_magnetic_solve_acceptance::test_the_150k_pattern_has_nothing_to_solve`:
    under LM all four classes refine (ΔBIC ≤ −21.9), and the test pairs
    rows to classes by index. `test_multi_diagnostics::test_the_specimen_and_the_fit_are_told_once`
    needs a stage that runs out of budget, and LM solves its linear scale
    stage. One is unexplained:
    `test_acceptance_sequential::test_chained_agrees_with_independent_fits`
    gives cpd-1d chained 0.14604 against 0.13087 alone (bar 0.005). Its warm
    refit starts with five widths at exactly 0 carried from cpd-1c.
    Hypothesis: a carried zero starts on its bound unseeded
    (`ParameterTable.seed_floor` lifts softplus rows only).
  - *Numbers that move with the flip* (physical + LM against today): the
    LaB₆ free-Gaussian plans swap between two genuine minima, 9.661408 and
    9.840220, by schedule (no test runs them); brucite + Stephens +4.8e-2
    (the cone is enforced); absent phase −8.0e-7 (the coordinates); FAP
    +5.5e-8, Si 640c +7.5e-8, corundum +1.4e-7 (inside today's own
    five-start range); NAC Pawley Rwp 0.13478 against 0.13628. Above 128
    columns the LM step is still BCCG's (`lm.BVLS_MAX_COLUMNS`).

- **From WP-1936 (2026-10-09): the FD step is one more reader that branches on
  the transform.** `least_squares._fd_typicals` sizes a column's step by
  `FLOOR_SEEDS` only when the row is `identity` *and* its lower bound is at
  least 0, or its unit is deg². A softplus row keeps 1, its θ being
  logarithmic. Under physical coordinates with `lo = max(lo, 0)` every width
  qualifies. A width given a negative lower bound would not, and would go
  back to an absolute step. The bound is how an offset (zero shift, peak
  position, both in degrees) is told from a width.
- **Two baselines that are not minima.** Brucite with the Stephens block under
  softplus + TRF spans χ²_red 7.635871–7.636119 across four FD steps that
  differ by 1e-12, and two of eight runs stop on `max_iter`, under the old step
  and the new. LaB₆ + cBN with `u v w x y` free now reaches 9.793673 under
  softplus and 9.840220 under physical coordinates, each at every step, so the
  two coordinate systems no longer meet on that fit (both met at 9.6614 under
  the old step).

## Non-goals

- The esd rule for a row on its bound, and the floor diagnostic: WP-1929.
- The driver (WP-1937) and the FD step (WP-1936).
- Moment angles at a stationary direction: already identity, so untouched
  here (WP-1929 task 4).

## Tasks

- [ ] The table builds identity entries for every declared transform, with
      the bounds above; `transforms.py` keeps only what migration needs.
- [ ] Read-point migration for a stored `transform`, with a fixture of a
      pre-change project and history opening unchanged in meaning.
- [ ] Every reader in the list above, each fixed or deleted, and the grep that
      finds no `"softplus"` branch left outside migration.
- [ ] Seeds: for each caller of `seed_softplus` and WP-1930's floor seed,
      measure whether it still changes an answer, and delete what does not.
- [ ] The traced backends (`backend/traced.py`) and the cross-backend matrix.
- [ ] Re-measure every acceptance suite and VALIDATION.md's rows; list every
      number that moves by more than 1 % with its reason.
- [ ] Root CLAUDE.md and DESIGN.md clauses rewritten in the same change.
- [ ] Tests, plus obs/calc/diff PNGs to `tests/output/` for the fits whose
      answer moves.
- [ ] Skill: any rule that tells an agent to seed a width before freeing it.

## Acceptance

```sh
.venv/bin/python -m pytest -n auto --dist loadgroup
.venv/bin/python -m ruff check src tests examples
```

The twelve-fit grid of WP-1929's second session, rerun on the default driver,
reaches one minimum per fit (spread under 1e-9) and one `profile.x` esd on
BT-1.

## References

- WP-1929 (the measurement and the review), WP-1930 (the trap), WP-1463 (the
  tiny-column rule this retires), WP-1102 (the read-point migration pattern).
- TOPAS 5 Technical Reference § 2.4-2.5 (limits inside the solver, physical
  derivatives); ROOT `TMinuit` documentation, parameter limits (why a
  transformed parameter's error is meaningless near its limit).

## Handover log

- **2026-10-09** — created from WP-1929's second session. No open WP owns the
  parameter transforms: 1463 and 1535, which last changed the floor handling,
  are closed; 1930 seeds a floor rather than removing it; 1914 reads a
  coefficient after the fit.

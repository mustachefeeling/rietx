# WP-2002: rows still at `unaudited`, with what each waits on (2026-10-20)

Written by the session's audit-row lane; the B10 rows that landed at tier 3 with their owed test named (B10 option 2) are removed. Each row lands with the change, test or WP it names.

All stay on `UNAUDITED_BASELINE`. Out-of-scope classes (B5, B13, B14) are not listed.
Hand rows (not in `_audit.ROWS`) are not listed; B15 has only hand rows, so nothing of it
is here or landed.

## B2: the stationary-angle test's demotion (code change)

- `rietx.optimize.least_squares.STATIONARY_ANGLE_LEVEL`: the test's demotion (Δχ² to a record field, angle keeps its esd).
- `rietx.optimize.least_squares.STATIONARY_ANGLE_STEP`: the same demotion.
- `rietx.optimize.least_squares.STATIONARY_ANGLE_MAX_ITER`: the same demotion.
- `rietx.schemas.results.StageResult.moment_angle_tests`: the same demotion (the action row of the test).
- `MOMENT_ANGLE_STATIONARY`: becomes an info record carrying the Δχ².
- `MOMENT_ANGLE_STATIONARY.suggestion`: rewritten with the info record.

## B3: the roughness seed's two-start test

- `rietx.schemas.results.StageResult.seeded`: two-start test (b = 0 against 0.3 on three lab families); records only the roughness seed today.
- `rietx.strategy.suggest.SUGGEST_SEED_ROUGHNESS`: the same two-start test (the suggestion probe's copy of 0.3).

## B7: the intermediate tolerance's invariance test

- `rietx.schemas.plan.INTERMEDIATE_FTOL`: invariance test in plain esds (1e-6 against 1e-9 on three families, same held set).
- `rietx.schemas.plan.PlanSpec:intermediate_ftol`: the same test.
- `rietx.schemas.plan.StageSpec:ftol`: the same test (None resolves to the schedule).
- `rietx.schemas.results.StageResult.ftol`: the same test (records the schedule).

## B8 and B9: limits (the size floor, March r, the harmonic and extra-peak ceilings landed with the limits lane)

- `rietx.schemas.instrument.EXTRA_PEAK_FWHM_MIN`: it guards a pole, but lowered to a pole-only value a Gaussian narrower than about 0.03 of the grid step underflows to an exactly zero column (the W failure, root CLAUDE.md). A floor that keeps the column live depends on the step, so it needs a per-stage freeze like `strain_cap`: a design change.
- `rietx.schemas.instrument.HUMP_FWHM_MIN`: the same.
- `rietx.strategy.staged.HUMP_MIN_WIDTH_MULT`: not a limit on a caller's parameter; a diagnostic threshold (gates `HUMP_TOO_NARROW`, so B13/WP-2005) and the extinction screen's internal floor (`indexing/extinction.py:737`).
- `rietx.schemas.instrument.HARMONIC_WEIGHT_SEED`: the two-start test for starting values.
- Hand rows with no seat until B14's lifts: `Atom:occ` (widened to no ceiling), `EmissionLine:weight` (widened), `Geometry:bounds` (the axial ratios widened; the position corrections kept, a question for the maintainer), `Instrument:zero_shift` (kept, the same question), `TCHZ_BOUNDS` and `TCHZ_BOUNDS_COARSE` (their U/V floors and ceilings are chosen, but WP-1312 ruled on 2026-09-11 that "the bound stays": a question for the maintainer).

## B10: numerical settings with no domain test, and one undecided switch

Each waits on a test that bounds its error over its claimed domain (tier 1), or one asserting identity (invariant). The batch found only single-case checks; I found none either.

- `rietx.model.profiles.fcj.MAX_NODES`: the same; it fails below about 6.5 deg 2θ on lab Bragg-Brentano data.

## B11: the iteration budgets' margin test

- `rietx.optimize.least_squares.NFEV_PER_ITERATION`: a margin test under both LM and TRF.
- `rietx.optimize.lm._INNER_MAX`: the same.
- `rietx.schemas.plan.StageSpec:max_iter`: the same.

## B12: pick verbs whose code changes

- `rietx.background.auto.AIR_SCATTER_TRIGGER`: auto_background returning its evidence beside the pick (1(a)).
- `rietx.background.auto.HUMP_TRIGGER`: the same.
- `rietx.background.auto._KNOT_STEP_SMOOTH_DEG`: the same.
- `rietx.background.auto._KNOT_STEP_HUMPY_DEG`: the same.
- `rietx.background.auto.AUTO_BACKGROUND_SEED_PERCENTILE`: the same.
- `rietx.background.auto.auto_background:kind`: the same.
- `rietx.background.auto.auto_background:diagnostics`: the same.
- `rietx.background.auto.auto_background:wavelength`: the same.
- `rietx.background.auto.auto_background:two_theta_limits`: the same.
- `rietx.background.auto.auto_background:source`: the same.
- `rietx.background.auto.auto_background:seed`: the same.
- `rietx.strategy.magnetic.SOLVE_TIE_DELTA_BIC`: solve_magnetic's N/f² ΔBIC (2(a)) and the dropped R tie-break (2(b)); its tier is ruled 3.
- `rietx.strategy.magnetic.SOLVE_K_TIE_DELTA_BIC`: the N/f² ΔBIC (2(a)); tier ruled 3.
- `K_VECTOR_UNSEPARATED`: the N/f² ΔBIC (2(a)); tier ruled 3.
- `MAGNETIC_SUBGROUP_PREFERRED`: the N/f² ΔBIC (2(a)); tier ruled 3.
- `rietx.strategy.magnetic.SOLVE_TIE_R_MAGNETIC`: dropped (2(b)).
- `rietx.strategy.magnetic.SOLVE_D_MIN`: the form-factor follow-up (not yet filed).
- `QPA_FRACTION_UNDETERMINED`: the warning becoming an info record (3(a)).
- `rietx.schemas.fraction.FRACTION_PROFILE_EXCESS`: the same.

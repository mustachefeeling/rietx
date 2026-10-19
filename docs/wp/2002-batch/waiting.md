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

## B8: the cell clamp and the 2 nm floor (code changes)

- `rietx.params.vector.CELL_SAFETY_FRACTION`: the clamp becoming restore-and-hold.
- `rietx.params.vector.CELL_SAFETY_ANGLE_DEG`: the same.
- `CELL_RUNAWAY`: the same (its record entry changes).
- `CELL_RUNAWAY.suggestion`: the same.
- `rietx.params.vector.SIZE_CAP_MIN_SIZE_A`: removal of the 2 nm floor.

## B9: limits and starting values inside opt-in features

- `rietx.schemas.structure.MARCH_R_MIN`: the 0.15 floor's removal. Its value IS the 0.15 today (`schemas/structure.py:41`); the pole floor that stays will be a new, smaller value of this constant, so the row waits for that value.
- `rietx.schemas.structure.MARCH_R_MAX`: the B9 principle ("no chosen limits on quantities that remain physical") not yet applied to this box; the ruling names only occupancy and March r's floor.
- `rietx.schemas.instrument.HARMONIC_WEIGHT_MAX`: the same principle not yet applied to this box.
- `rietx.schemas.instrument.EXTRA_PEAK_FWHM_MIN`: the same.
- `rietx.schemas.instrument.EXTRA_PEAK_FWHM_MAX`: the same.
- `rietx.schemas.instrument.HUMP_FWHM_MIN`: the same (it guards the Gaussian's pole at zero width, but its 0.1 deg value is chosen, like March r's 0.15).
- `rietx.strategy.staged.HUMP_MIN_WIDTH_MULT`: the same (batch lists it with the B9 boxes; it also gates HUMP_TOO_NARROW).
- `rietx.schemas.instrument.HARMONIC_WEIGHT_SEED`: the two-start test for starting values.

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

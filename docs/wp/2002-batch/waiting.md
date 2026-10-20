# WP-2002: rows still at `unaudited`, with what each waits on (2026-10-20)

Written by the session's audit-row lane; the B10 rows that landed at tier 3 with their owed test named (B10 option 2) are removed. Each row lands with the change, test or WP it names.

All stay on `UNAUDITED_BASELINE`. Out-of-scope classes (B5, B13, B14) are not listed.
Hand rows (not in `_audit.ROWS`) are not listed; B15 has only hand rows, so nothing of it
is here or landed.

## B3: the roughness seed's two-start test

Measured 2026-10-20 (`tests/test_seed_invariance.py`'s docstring has the table). Suortti's b
is answer-invariant on five lab patterns from three laboratories: every Biso, scale and b
within 2.7e-3 of the smaller esd, the same branch wherever b leaves its floor, the same
distance from each reference. Two things keep both rows here:

- `rietx.schemas.results.StageResult.seeded`: the same literal seeds Pitschke's `c`, which
  is *not* start-invariant (CPD zincite from c = 0: the turned-over regime, scale x2.1,
  `ROUGHNESS_OUTSIDE_REGIME`; corundum: Biso 0.26 esd). A question for the maintainer:
  GSAS-II has no Pitschke model, so the ruled fallback to its 0 names no dissenter here.
  And where roughness ends switched off, the start picks which off point the fit stops
  at (b = 0 with a free, or a = 1), and Biso's and the scale's esds differ by x1.1 to x4.4
  between the two (conditional at a = 1, where b's column is zero; marginal at b = 0).
- `rietx.strategy.suggest.SUGGEST_SEED_ROUGHNESS`: not measured. It is the suggestion
  probe's start for scoring a column, not a solve's start, so the question is whether
  `suggest`'s ranking moves between 0.3 and other starts.

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
- Hand rows with no seat until B14's lifts: `Atom:occ` (widened to no ceiling), `EmissionLine:weight` (widened), `Geometry:bounds` (the axial ratios widened; the position corrections widened to no bound on 2026-10-20, transparency keeping its physical floor of 0), `Instrument:zero_shift` (widened to no bound, 2026-10-20), `TCHZ_BOUNDS` and `TCHZ_BOUNDS_COARSE` (their U/V floors and ceilings are chosen, but WP-1312 ruled on 2026-09-11 that "the bound stays": a question for the maintainer).

## B10: numerical settings with no domain test, and one undecided switch

Each waits on a test that bounds its error over its claimed domain (tier 1), or one asserting identity (invariant). The batch found only single-case checks; I found none either.

- `rietx.model.profiles.fcj.MAX_NODES`: the same; it fails below about 6.5 deg 2θ on lab Bragg-Brentano data.

## B11: the iteration budgets' margin test

- `rietx.optimize.least_squares.NFEV_PER_ITERATION`: a margin test under both LM and TRF.
- `rietx.optimize.lm._INNER_MAX`: the same.
- `rietx.schemas.plan.StageSpec:max_iter`: the same.

## B12: the form-factor follow-up (the other B12 rows landed with the pick-verb changes)

- `rietx.strategy.magnetic.SOLVE_D_MIN`: the form-factor follow-up (not yet filed).

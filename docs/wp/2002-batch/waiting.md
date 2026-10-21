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

Run 2026-10-21 on SRM 660c, FAP, the CPD round robin and 11-BM NAC, under LM and TRF, each
protocol's own plan and the default plan, 1e-6 against `intermediate_ftol=None` (every stage
at 1e-9). "Plain esd" is `stderr_uncorrected`; paths `FLAT_DIRECTION` or
`COVARIANCE_DIRECTION_DISCARDED` names are listed apart as degenerate.

- Within WP-1123's 0.03 esd everywhere but cpd-1a under its QPA protocol: 0.033 (LM,
  corundum scale) and 0.074 (TRF, corundum Al Biso) as fitted, 0.046 and 0.074 after one
  stage recompiled at each answer. In the inflated esd WP-1123 used they are 0.009 and
  0.021, so the switch to plain esds (f = 3.52 there) is what crosses the bar. Under LM
  three recompiles bring the arms within 0.0074; under TRF they stay 0.074 apart and the
  None arm then moves 0.106 by itself, so TRF's own scatter there exceeds the bar. QPA moved
  0.0055 and 0.009 wt %.
- **A hold flips** (the brief's change-my-mind condition, and clash C18): cpd-1a with
  zircon declared, a phase the sample lacks, under LM. At 1e-6 the last stage holds nine
  zircon structural paths and `PHASE_UNCONSTRAINED` fires; at 1e-9 nothing is held, the
  zircon cell walks (0.30 esd as fitted, 1.28 after a recompile, in `axial_sl`) and the
  `lines_axial` stage hits its 400-evaluation budget. Zircon's scale sits near 2σ in plain
  esd, by the hold's threshold. The looser default is the one that held.
- Evaluations saved by 1e-6: 1.00-2.15× on the ordinary fits, 4.9× on the flip.

No test written. All five rows (`INTERMEDIATE_FTOL`, `PlanSpec:intermediate_ftol`,
`StageSpec:ftol`, `StageResult.ftol`, and the hand row `run_least_squares:ftol`) wait on the
maintainer: what bar a staged plan's invariance test uses (the same question as B9's), and
the batch's fallback if it fails (tier 3, demoted to kind 3).

## B8 and B9: limits (the size floor, March r, the harmonic and extra-peak ceilings landed with the limits lane)

- `rietx.schemas.instrument.EXTRA_PEAK_FWHM_MIN`: it guards a pole, but lowered to a pole-only value a Gaussian narrower than about 0.03 of the grid step underflows to an exactly zero column (the W failure, root CLAUDE.md). A floor that keeps the column live depends on the step, so it needs a per-stage freeze like `strain_cap`: a design change.
- `rietx.schemas.instrument.HUMP_FWHM_MIN`: the same.
- `rietx.strategy.staged.HUMP_MIN_WIDTH_MULT`: not a limit on a caller's parameter; a diagnostic threshold (gates `HUMP_TOO_NARROW`, so B13/WP-2005) and the extinction screen's internal floor (`indexing/extinction.py:737`).
- `rietx.schemas.instrument.HARMONIC_WEIGHT_SEED`: two-start test run 2026-10-20, synthetic
  (corundum, constant-wavelength neutron, true λ/2 weight 0, 0.003, 0.05; the held-out
  Nd₂Ru₂O₇ pair unused) and so one family. Not invariant at B3's bar of 0.01 esd: the
  weight moves up to 0.15 esd between seeds 0.01 and 0.3, a background coefficient 0.86.
  Every seed reaches the right verdict (`HARMONIC_ABSENT` at 0, `HARMONIC_FRACTION`
  otherwise). The mechanism is the plan's, not the seed's: the weight is held at its seed
  until the last stage, whose model is frozen where the earlier stages stopped, and one
  extra stage recompiled at the answer brings the seeds within 0.012 esd. The same
  mechanism fails `Atom:biso` below, so both wait on one question for the maintainer:
  what bar an invariance test across a staged plan should use.
- `Atom:biso`* (hand row, 0.5 Å²): two-start test run 2026-10-20 on SRM 660c, FAP, CPD
  (corundum, fluorite, zincite) and 11-BM NAC, starts 0.5 and 1.5 (worst over 0 to 10 in
  brackets). Biso moves 0.008 to 0.08 esd (0.16), other parameters up to 0.27 esd (0.50),
  χ² up to 6.2e-4 relative; NAC passes. Recompiling the model at one answer changes its
  cost by 0.05 to 0.3 %, and one extra recompiled stage brings FAP, corundum and fluorite
  within 7.9e-3 esd. `crystallography/cif.py:762` carries a second copy of the 0.5 for a
  CIF site with no ADP.
- `TCHZ_DEFAULTS`* (hand row): invariant, `tests/test_seed_invariance.py`'s second test
  (its docstring has the table and the margin). Waits only on B14's lift for a seat. Two
  readings it does not cover: a start near the answer's x lands on a second, deeper
  minimum on LaB6, 46.7 χ² below and nearly the S/L ↔ H/L mirror of the default's, moving u
  0.38 esd (WP-2012's interchange; the FCJ node count was measured and is not the cause); and a protocol holding an uncalibrated width holds it at
  this default, where x = 0 instead moves FAP's `lor_size` 0.69 esd at equal χ².
- Hand rows with no seat until B14's lifts: `Atom:occ` (widened to no ceiling), `EmissionLine:weight` (widened), `Geometry:bounds` (the axial ratios widened; the position corrections widened to no bound on 2026-10-20, transparency keeping its physical floor of 0), `Instrument:zero_shift` (widened to no bound, 2026-10-20), `TCHZ_BOUNDS` and `TCHZ_BOUNDS_COARSE` (their U/V floors and ceilings are chosen, but WP-1312 ruled on 2026-09-11 that "the bound stays": a question for the maintainer).

## B10: numerical settings with no domain test, and one undecided switch

Each waits on a test that bounds its error over its claimed domain (tier 1), or one asserting identity (invariant). The batch found only single-case checks; I found none either.

No B10 row is unaudited now. `MAX_NODES` landed at tier 3 on 2026-10-21 beside the other three FCJ constants. Their domain test (`tests/test_lab_instrument.py`, the FCJ section) fails over part of the domain for all four, and the constants wait on the maintainer. Measured for the ruling (2026-10-21, scratch code, 10 491 cases against converged references; image counts summed over every `compile_model` call at the fitted values, today 664 on SRM 660c and 5036 on FAP):

- Cheapest set meeting both bars under today's equal split: `NODES_PER_FWHM` 11, `MAX_NODES` 768, `SKIP_EXTENT_FWHM_RATIO` 3.5e-4 (any `MIN_NODES` ≤ 8 is inert, since `max(n//2, 4)` floors every reflection at 8 images). Images 948 and 5704 (×1.43, ×1.13). Thin: 0.95 of the bar at the cap and at the skip.
- The first proposal, 12 / 10 / 1024 / 3e-4: worst 0.25 (lab) and 0.81 (synchrotron) of the bar, images ×1.57 and ×1.37, fit wall clock ×1.15-1.3 on the two lab protocols, no parameter moved past 0.025 esd.
- Splitting the nodes between the two segments by length instead of equally is unsafe, because the split would be frozen per stage while S/L and H/L refine. A segment with zero length at compile time (S/L = H/L, or one aperture at zero) gets no nodes and then grows, and its share of the peak is missing: errors 950-1390× the bar. Both lab acceptance protocols start on S/L = H/L and refine off it. A floor of 4 nodes per segment still fails at up to 480×. So the equal split stays.
- The skip ratio's bound is split-independent: a peak drawn symmetric errs by at most 0.477 × extent/FWHM, so 3.67e-4 is the ceiling.
- Measured effect of today's error on answers: SRM 660c with every reflection at 512 nodes moved no parameter past 0.04 esd.

The window rows, measured 2026-10-21 on SRM 660c, FAP, cpd-1a and 11-BM NAC (`tests/test_window_domain.py`'s docstring has every number). The bar is 0.1 of each point's own σ at fixed parameters, and 0.1 plain esd on every non-background row after both arms are polished to a fixed point from one common start:

- `WINDOW_AREA_TOL` 2e-2 fails on all four: up to 2.15σ at a point, and a converged refit moves the cpd-1a zincite scale 0.97 esd, FAP's `lor_size` 0.91 and the background 2.1-5.1. At 1e-3 all four pass, at 1.2-3.5× the fit time (FAP the dearest); at 2e-4, 1.9-6.8×. Against it: from the shipped answer FAP's χ² is 110 higher with converged tails, the other three 37-1730 lower.
- `REFLECTION_MARGIN_DEG` 0.5° fails on FAP and cpd-1a (0.12σ, 0.10 esd); 5° is bit-identical to 20°. The coherent fix generates reflections out to the largest window half-width at the range edges (`forward.py:3733-3734`).
- `AXIAL_SIZING_FLOOR` 0.02 fails for a stage that frees S/L and H/L from zero and reaches the typical 0.05 (0.27 of the peak maximum, 19.5 % of an area dropped); 0.05 passes at 1.25-1.8× the fit time, mostly because the floor also applies to every positive ratio below it (`forward.py:3693-3696`), which a separate refine-from-zero floor would avoid.
- `MAGNETIC_SIZING_FLOOR` 0.1° drops 3.2-4.1 % of a magnetic peak at the planted widths; the preset's answer moves 0.031 esd. Raise it to ≥ 0.3, or size from the width's bound as `_compile_extra_peaks` does (`forward.py:3910-3919`).
- Landed: `WINDOW_MIN_DEG` and `StageSpec:window_slack_deg` at tier 1 (largest move 0.21° against 0.3°, so a 1.4× margin), `_BASES_CHUNK_ROWS` and `_DENSE_EIGEN_MAX` invariant.
- Found beside them: windows are sized from start-of-stage widths, so a stage that widens peaks drops 3.0-6.5 % of an area by its end (LaB6 `profile`, cpd-1a `profile` and `sample_broadening`); every final stage holds the 2 % bound. No constant claims this; strict xfails record it.

Eight more, measured 2026-10-21 (each row's evidence has the numbers):

- The three geometry caps (`CONTACT_MAX_ANG`, `MAX_ASYM_ATOMS`, `MAX_CONTACTS_PER_ATOM`) landed at tier 1, as a report scope: a domain test was the wrong frame for a cap on what a table lists, and the tests assert completeness within the scope and exact disclosure beyond it.
- `FD_STEP` and `_MIN_GAMMA_G2` pass on the smooth domain and at the FAP and NAC answers, but the SRM 660c and cpd-1a protocol answers end with high-angle reflections on the Gaussian-variance floor, where an FD column is 2.2e-2 off and a polish moves U 1.2 plain esd under a 5e-7 step or a 1e-10 floor, at χ² 0.25 % worse. A defect of the clamp the solver leans on, not of either constant (forwarded to WP-1467); both stay tier 3.
- `A5_CLIP` fails by a little (1.40 % against 1 %); 1e-4 passes at no measured cost.
- `TEXTURE_SPHERE_SAMPLES` fails at every order (2.0e-3 to 7.9e-3 against 1e-3); 32 000 samples pass at 10× the cost, or a local polish at any order.
- `MIN_IMAGE_SHELL` misses restraint images in unreduced monoclinic cells (β 135-150°), so a restraint can bind the wrong pair: a defect, fixed by sizing the shell with `geometry._shell(g, d)`.

Domain tests still owed at tier 3: the interval settings (`PARAMETER_INTERVAL_*`) and the width-grid settings (`FRACTION_PROFILE_*`). The other B10 rows sit at tier 3 with their domain tests still owed (grep `_audit.py` for "claimed domain is owed").

## B12: the form-factor follow-up (the other B12 rows landed with the pick-verb changes)

- `rietx.strategy.magnetic.SOLVE_D_MIN`: the form-factor follow-up (not yet filed).

# WP-1953 — a large Pawley stage converges under the default driver

Milestone: unscheduled · Status: 🔄 2026-10-12 — the FCJ limit (its traced column fixed for CI's jax job) and the projected-CG Pawley step in PR #918; the held column scale waits on a rule for a column that is noise from a stage's start
Track: What fires, and what stays silent
Depends on: —
Priority: P2 2026-10-12 — was P1: PR #918 fixes the Windows gate's `test_e8` (measured on Windows, Linux and macOS runners); what remains is LM's crawl beside a vanishing or noise column, which reports `converged` far from a minimum on magnetic fits

## Goal

The default LM driver converges where it reports converging, in the three
places it now crawls to its evaluation cap or stops early. A Pawley fit with
more than `lm.BVLS_MAX_COLUMNS` (128) columns converges every stage. A stage
beside a column that vanishes at its minimum converges rather than reporting
`ftol_runs` far from one. The FCJ axial ratios are continuous at a zero
aperture, so the exact bounded step can land on that bound. Whether LM and
TRF then reach the same answer on such fits is measured and written down.

## Context

**What landed before this.** WP-1937 built the LM driver (`optimize/lm.py`).
Its box step is exact up to 128 columns (BVLS on the eigendecomposed normal
matrix, `_solve_step`) and BCCG's above (`optimize/bccg.py`), because scipy's
BVLS refactors the free set at each active-set change. WP-1938 made LM the
default (#883, merged 2026-10-11). A Pawley fit appends one column per
reflection, so it is the fit that crosses 128.

**The seam.** `lm._solve_step`'s `n > BVLS_MAX_COLUMNS` branch calls
`bccg.solve(A + lam·diag(d²), b, …)`. The inner loop in `lm.minimize` reads
the taken step's promise, `−stepᵀb`. A promise ≥ 0 raises λ and retries
without evaluating (the `promise >= 0.0` branch). A promise under the fp64
floor ends the stage `exhausted_fp64`.

**The measurement that filed this** (WP-1938's fifth session, macOS 26.6.2
arm64, `[dev,jax]`, one run each under load). FAP.XRA from
`tests/test_acceptance_fap.build_fap_inputs()`, `mode="pawley"`, default
plan, 343 columns at the `profile` stage:

| arm | `profile` stage | Rwp | wall |
|---|---|---|---|
| `main` `6075319c` (TRF, before the flip) | converged | 0.07825358 | 20.2 s |
| TRF, after the flip | converged | 0.07838295 | 11.0 s |
| LM as shipped (BCCG above 128) | 400-evaluation cap, 635 box solves | 0.08035928 | 16.7 s |
| LM, exact step at every size | converged | 0.08028663 | 6.3 s |
| LM started from TRF's answer | converged | 0.07825264 | |

Two findings sit in that table.

1. **BCCG's steps often promised no descent.** The crawling stage made 635
   box solves for 400 evaluations. Only the no-descent branch retries
   without evaluating, so about 235 steps were rejected there and λ raised.
   On eight systems sampled from the stage, BCCG's step left its own damped
   model ½sᵀ(A + λD)s − bᵀs above zero, worse than not moving, at six of
   the seven with λ > 0 (+0.05 down to +7e-6). The exact solve's value was
   below zero at all eight. WP-1937 had measured BCCG 5-22 % short of the
   exact model minimum on synthetic systems, never on the wrong side of
   zero.
2. **LM settles in a worse place than TRF from the default start.** The
   exact-step LM converges at 0.08029, TRF at 0.07838, and LM started at
   TRF's answer keeps it. The refined profile parameters of the two answers
   differ by at most 1.5 esd, so the gap is mostly in the intensities. NAC
   Pawley (142 columns) went the other way under WP-1937: LM 0.13478453
   against TRF 0.13628068, on either step. So it is not yet known whether
   this is a driver property or one fixture's landscape.

**What the exact step costs** (WP-1937, synthetic Pawley-shaped systems, per
solve, exact against BCCG): 2-34 ms against under 1 ms at 128 columns,
0.13-0.8 s at 400, 1.5-11 s at 1000, 10-177 s at 2000 against at most 22 ms.
On FAP the exact-step fit was the faster one, because it converged.

**The constrained step is not the cost here.** WP-1938's lane found no
Pawley fit crossing a linear-inequality row, and `nnls` never ran out of
iterations on any of 16 fits. Forced onto FAP's systems the constrained step
took 42-70 ms at 343 columns.

**The standard remedy to weigh.** A trust-region step need only achieve a
fraction of the Cauchy point's model decrease to keep the global convergence
argument (Nocedal & Wright 2006, *Numerical Optimization*, §4.1-4.2). The
projected-gradient step along −b is cheap at any size, so a step that
promises less could fall back to it. That is a candidate, not a decision.

### The Windows gate's `test_e8` (diagnosed 2026-10-12)

Folded from WP-1954's note at the 1.8.0 tag.
`test_report_loop.py::test_e8_collinear_window_applies_no_position_action`
failed on every Windows run from 2026-10-12, and 1.8.0 shipped with it red
as a known issue (`docs/releases/1.8.0.md` names this WP). Freeing axial
asymmetry on the test's 20-56° window ended at χ²_red 51.43422542054468 on
Windows (GitHub `windows-latest`, AMD EPYC 7763, Python 3.13.15, numpy 2.5.4,
scipy 1.18.1) against 51.41434042984701 on macOS arm64. From there the
Windows report read the position trend as separable and offered
`refine_sample_transparency` at 0.999, where macOS capped every position
action at 0.3. Linux 3.12 and 3.13 passed. The nightly macOS job, which does
not gate, failed two more rows on the same commits that pass on a local Mac:
`test_high_correlation_dedup.py::test_a_real_plan_reports_a_persistent_pair_once_naming_every_stage`
("the axial pair raised no HIGH_CORRELATION at all") and
`test_stationary_moment_angle.py::test_an_angle_without_an_esd_still_has_a_profile_interval`
(0.00435 against a bar of 0.00309).

Measured here (macOS arm64, `[dev]`, Python 3.12.10, `main` `4a8c6d08`):

- **The axial stage crawls on macOS too.** The verify stage of
  `refine_axial_asymmetry` frees S/L, H/L and four background terms and ends
  on `max_nfev`: 400 evaluations, 266 outer iterations, λ 1.4e3. Its endpoint
  is wherever 400 damped steps reach, so a rounding difference moves it. That
  is the platform split.
- **Cause one is the model.** `fcj_offsets_weights` falls back to the
  symmetric peak when *either* aperture is zero. The h → 0⁺ limit of the
  module's own normalised trapezoid W is a uniform smear over ξ ∈ [0, s]. The
  exact bounded step lands H/L on its bound of 0, χ² jumps from 92 250 to
  793 600, and λ rises. WP-1938's rule names this class: a bound must be a
  value where the model and its columns are defined. March r and W were its
  first two instances. `Geometry`'s docstring already says only both zero is
  off. FCJ 1994 is not in the local corpus, so the limit rests on the
  module's W.
- **The prototype.** One aperture at 0 with the other positive gives the
  limit, and both at 0 is off. H/L then lands on 0. The refits converge in
  2-5 evaluations at χ² 92 032 against 92 237. LM ends the episode at
  χ²_red 51.29977262 and TRF at 51.29977244, with S/L 0.0413309 in both.
  Every position action stays at or under 0.3.
- **Cause two remains.** The verify stage still runs to 400 evaluations. At
  H/L = 0 its column norm is 131 against S/L's 40 130. Along H/L, χ² has a
  dip of 0.025 at H/L ≈ 2e-5 with curvature ≈ 7e7, against Gauss-Newton's
  1.7e4. The exact integral has zero slope at H/L = 0 (f = G(s)/s +
  h²·g′(s)/(6s)), so that slope is the fixed-node quadrature's. LM holds the
  H/L step inside the dip by raising λ to 230-2300, which crawls every other
  parameter. It is the vanishing-column crawl below, on an axial ratio.
- **A protocol that did nothing now does something.** QPA cpd-1a's
  `lines_axial` stage frees S/L with H/L at 0, so on `main` it changed
  nothing. With the prototype S/L refines from 0 to 0.0406 and converges in
  29 evaluations. The stage's χ² falls 4.9 %, and the fit's Rwp goes from
  0.17125 to 0.16676. Weight fractions move by at most 0.035 wt % (corundum
  1.665 → 1.630, weighed 1.15). The Stephens brucite protocol has the same
  stage.

### The crawl beside a vanishing column (from WP-1929)

Folded from WP-1929's notes of 2026-10-12, the maintainer's call that day
moving it here as the same `lm.py` step and stop. A moment angle's column
scales with its modulus and vanishes at a direction the symmetry fixes.
`_solve_step` scales every column to unit norm, so that angle takes the
largest step, and λ grows until every parameter crawls. `ftol_runs` then
fires on three tiny decreases in a row and reports `converged`. Measured in
WP-1938 D12 (macOS arm64, `[dev,jax]`): the two-site Pnma set
(`tests/test_pair_diagnostic_class.py`) released stopped at χ² 454 660 with
λ 5e7-7e9, against 2555.8 under TRF. `solve_magnetic` frees the moduli first
(`magnetic.SOLVE_STAGE_NAMES`) and reaches 2556.06, but a plan a user builds
gets no such stage. `tests/test_magnetic.py`'s `_LM_FALSE_CONVERGENCE` row is
the same stop on one site (λ ≈ 1e11, χ²_red 11.03; a fresh LM solve from
there reaches χ² 4e-16 in 17 evaluations) and stays a strict xfail until this
lands.

Remedies named, none measured: count a decrease toward `ftol_runs` only
while λ is small; give an angle column a scale floor from its
finite-rotation response; keep each column's scale at its largest so far.
The last is MINPACK's `mode=1` scaling and the documented form of the second.
Any of them moves every default fit's iterates, so the goldens and the
acceptance grid are re-measured.

**WP-1929 keeps the esd half.** `least_squares.stationary_angle_test` zeroes
a passing angle's column for the covariance with its own central
differences. The forward quotient's I''·h/2 still decides the column the
driver steps on, and the esds of an angle the test keeps.

**The exact angle column is parked on branch
`wp1953-central-angle-columns`** (`87c6d6de`, cut from `main`, no PR).
`_peak_chain_column` forward-differences each reflection's scalars with
h = 1e-6·max(1, |φ|), and at a stationary point that quotient is I''·h/2:
0.009801 (Mn1) and 0.001328 (Mn2) on the two-site Pnma set, issue #831's
numbers, and 0.1038 / 0.0042 on the polar angles at θ = π/2. Central
differences give ≤ 2e-12. The branch differences moment angles centrally
and adds a `magnetic_stationary` cross-backend config and an exact-zero
test, both failing before and passing after. It is parked because the exact
zero column sets off the crawl: under LM `test_magnetic_moment_frame`
[103.0] goes from χ²_red 0.978 to 5.861, still `converged`, and [101.1] from
0.978226 to 0.979134. Under TRF all six arms keep 0.978226.

**On Linux arm64 the two-site class 0 winner is the swapped minimum**
(WP-1929's fifth session, run 38239010950 at `main` `869b6cf8`, numpy 2.5.4,
scipy-openblas 0.3.34). `ubuntu-24.04-arm` (Neoverse-N2) has Mn1 at 0.69950
and Mn2 at 3.49821 μ_B, χ²_red 1.0574924. `ubuntu-latest` has Mn1 at 3.49778,
χ²_red 1.0574900, and macOS arm64 3.49801 and 1.0574474. So
`test_the_two_site_winner_finds_each_site_its_own_moment` would fail on arm64
Linux, which no CI job runs slow. Not diagnosed: whether the simulated
pattern is bit-identical across the three, and which start reached which
minimum. The swapped point sits 0.66 higher in χ² by the test's docstring and
arm64's winner only 0.11 above macOS's, so the pattern itself may differ.

### The step above 128 columns, measured (2026-10-12)

macOS arm64, `[dev]`, Python 3.12.10, branch at `5ba19a83` plus the
running-max column scale (its task below) unless a row says otherwise. That
scale did not land, so the rows marked *shipped* were re-run without it.
Another session's suite loaded the machine for part of the time, so the
seconds are loose. The default plan with `mode="pawley"`.

FAP.XRA, 335-343 columns:

| step above 128 columns | `profile` stage | no-descent steps | Rwp | wall |
|---|---|---|---|---|
| BCCG as shipped, scale per iteration | `max_nfev`, 400 | 236 of 635 solves | 0.08035928 | 18.7 s |
| BCCG, running-max scale | `max_nfev`, 400 | 237 of 636 | 0.08035932 | 18.5 s |
| BCCG, Cauchy point when it lowers the model more | `max_nfev`, 400 | 0 | 0.08035937 | 16.7 s |
| exact BVLS, either scale | converged, 13 | 0 | 0.08028663 | 6.0-6.6 s |
| projected Newton (Bertsekas 1982), ridge 1e-8 | converged, 10 | 0 | 0.08024166 | 2.2 s |
| projected Newton, ridge 1e-12 | converged, 9; half its solves at the 50-iteration cap | 0 | 0.07824433 | 7.3 s |
| projected CG, tight | converged, 22 | 0 | 0.07824512 | 2.3 s |
| projected CG, 2n budget | converged, 20 (`profile_w` 95) | 0 | 0.07824506 | 2.1 s |
| *shipped*: projected CG, 2n budget, scale per iteration | converged, 9 | 0 | 0.07824432 | 0.8 s, idle |
| TRF (WP-1938's row) | converged | | 0.07825358 | 20.2 s |

11-BM NAC, 1 492-1 499 columns, not the 142 WP-1937 quoted:

| step | stages | Rwp | wall |
|---|---|---|---|
| BCCG as shipped | `profile` on `max_nfev` 400, 68 no-descent | 0.15340222 | 299 s, loaded |
| projected CG, tight | every stage converged | 0.12620514 | 326 s, loaded |
| projected CG, 2n budget | every stage converged | 0.12620721 | 74 s |
| *shipped*: projected CG, 2n budget, scale per iteration | every stage converged, 0.20-0.77 s a solve | 0.12620721 | 71 s |
| TRF | every stage converged | 0.13483346 | 750 s, partly loaded |

Per solve, offline on 13 FAP and 24 NAC systems captured from those fits:
BCCG's model value was positive at most λ > 0, up to 6e6 times the size of
the best value found, so it is wrong in sign and not only short. BVLS took
0.04-0.25 s at 343 columns and 0.66-3.11 s at 1 493-1 495. Tight projected
CG took 0.002-0.04 s at 343 and 0.007-11 s at 1 493, the long solves all at
λ = 0. The 2n budget holds every NAC solve under 0.64 s and reaches 0.10-0.98
of the tight step's decrease on the hardest λ = 0 systems.

**The basin follows the near-null directions.** At λ = 0 the FAP systems
have 4-8 eigenvalues under 1e-8 of the largest, and on one system they carry
gradient 6e-4. BVLS's eigenvalue cut and a 1e-8 ridge damp them, and both
land at 0.0802-0.0803. CG and a 1e-12 ridge follow them, and both land at
0.0782, TRF's answer. This is WP-1938's second finding: LM did not settle
worse than TRF, the exact step's cut did. The same cut serves every table
fit up to 128 columns, which the basin task should keep in mind.

### Inherited

- **2026-10-12, from WP-1930: #918 also fixes the macOS nightly's red
  `test_high_correlation_dedup.py`.** At 56427c4a the axial pair's columns
  at the zero-aperture start were exactly zero, so the `axial` stage ended
  where it began and later stages left 0 by rounding. A 1e-14 nudge to `w`'s
  start sent the pair to `axial_sl` 0 and `axial_hl` 0.2 with no
  `HIGH_CORRELATION`, reproducing the CI failure on an M4. At e1d19359 each
  start column is 8.81 and ten nudges all end interior with the pair flagged.
  The next macOS nightly is the confirmation. The Linux LaB₆ + cBN silence
  over the same nightlies was the covariance's sign handling, fixed in
  WP-1930's `statistics._psd_pinv`, and touches none of this WP's files.

## Non-goals

- When a stage that is improving little should stop and say so: WP-1334.
- Esds at a stopping point beside a flat column: WP-1929.
- The constrained step's cost and its `nnls` fallback: measured and closed in
  WP-1938.

## Tasks

- [x] FCJ at a zero aperture: one aperture at 0 is the limit, both at 0 is
      off. The siblings are the compile sizing (`fcj_on`), the axial
      column's `axial_ok`, and the indexing peak fit's own `fcj` flag. A test
      that the profile at H/L = 0 is the H/L → 0⁺ limit, and that e8's
      verify stage lands on 0. Re-measure what frees one aperture from 0
      (QPA sample 1 and cpd-2, Stephens brucite, the `rietx compare`
      standards). Stage the note in `docs/releases/1.9.0.md`. `fcj_live` is
      the one off-state test; `test_lab_instrument.py` pins the limit, the
      exchange symmetry and the sizing, all failing on `main`. Every
      acceptance suite passed on the shipped tree (full suite below), so the
      protocols that now refine S/L beside H/L = 0 stay inside their bars;
      cpd-1a moved Rwp 0.17125 → 0.16676.
- [x] Windows: re-run `test_e8` on `windows-latest` after the fix, and the
      two macOS-nightly rows, before diagnosing either alone. Throwaway run
      38272975913 on the FCJ commit `5ba19a83` alone (Python 3.13, `[dev]`):
      `test_e8` passes on Windows, Linux and macOS runners, the episode ending
      at χ²_red 51.29977261567037, 51.29977261521287 and 51.2997726156772.
      The verify stage still stops on `max_nfev` on all three, at χ² 92 224,
      92 083 and 92 233, and the refit converges from each to 92 031.79.
      Windows and Linux land S/L on 0 with H/L 0.0413309, and macOS the
      reverse, the exchange symmetry `test_one_zero_aperture_is_the_limit_…`
      pins. `test_high_correlation_dedup`'s row passes on the macOS runner.
      `test_stationary_moment_angle`'s still fails there, 0.004349 against
      0.003091, so it is the vanishing-column task's. Run 38280327011 on the
      shipped tree (`243863de`, FCJ limit and projected CG): Windows and
      Ubuntu pass all 35 rows, `test_e8` ends at χ²_red 51.2997726156772 on
      macOS, and the macOS runner fails only that row, with `main`'s digits.
      Its cause is the stalled profile refits of the noise-column task.
- [x] Measure before deciding: every Pawley fixture above 128 columns the
      suite or the examples can build (FAP.XRA at least, and a wider range of
      NAC or a round-robin pattern if one crosses 128), under TRF, LM as
      shipped and LM with `lm.BVLS_MAX_COLUMNS = 10**6`. Record per stage the
      termination, the count of BCCG steps promising no descent, and the
      seconds per step. Measured 2026-10-12 below (§ The step above 128
      columns, measured).
- [x] Decide the step above 128 columns when BCCG promises no descent (the
      exact step, a Cauchy-point fallback, a tighter BCCG, or a higher cap),
      and record it here as `Decided YYYY-MM-DD:`. **Decided 2026-10-12:**
      projected conjugate gradients from the Cauchy point (Moré & Toraldo
      1991; Lin & Moré 1999's subspace step). CG runs on the free variables,
      stops at the first bound it meets, fixes that variable on it exactly and
      restarts; once CG converges on a face, a variable whose gradient points
      into the box is released. Every segment lowers the model, so every step
      descends. A budget of 2n Hessian products caps a solve. Not exact BVLS
      everywhere: 10-100× the cost per solve wherever λ > 0, 0.7-3.1 s at
      1 500 columns, and at λ = 0 its steps have norm 1e11-1e12 along null
      directions. Not a Cauchy fallback: it ends the wrong-side steps and
      still crawls. Not BCCG's own loose stop on the new loop: FAP's
      `profile` stage then takes 341 evaluations.
- [x] Implement it, with a test on a system where BCCG's step promises no
      descent. `bccg.projected_cg`, taken by `lm._solve_step` above the cut.
      `test_bccg.py::test_a_clamp_past_a_bound_raises_the_model_…` is a
      two-variable system where Coelho's BCCG ends at model value +44 070 and
      the projected CG on the exact minimiser; six random bounded problems
      pin it to BVLS's answer at 1e-9.
- [ ] The vanishing-column crawl: measure the three remedies on e8's verify
      stage, the two-site Pnma set and `_LM_FALSE_CONVERGENCE`; decide.
      **Measured 2026-10-12, not landed.** Keeping each column's largest norm
      this stage as its scale (Moré 1978, MINPACK's `mode=1`) fixes every
      case named: e8's verify stage converges in 22 evaluations at λ 0.42
      where it ran 400 at λ ≈ 1e3; `_LM_FALSE_CONVERGENCE` passes; the
      two-site Pnma set with moduli and angles freed together (no `moduli`
      stage) finds the truth, Mn1 3.4981 and Mn2 0.6996 μ_B at χ²_red
      1.05745, where `main` lands on the swapped minimum at 1.05772; and
      `test_magnetic_moment_frame`'s four arms keep `main`'s χ²_red to nine
      digits. The toy `test_lm_solver.py::test_a_column_that_vanishes_…` is a
      strict xfail until it lands (per-iteration scale: `ftol_runs` at λ
      1.7e10, χ² 1.891; held: 0.744854).
      **It broke one row, and that is why it is out.**
      `test_stationary_moment_angle.py::test_an_angle_without_an_esd_still_has_a_profile_interval`
      failed on the Linux and macOS runners (throwaway run 38279055364) and
      here under a +1e-14 nudge of the start tilt (one of six nudges; `main`
      passes all six). The fit's azimuth stops at 0.01550 against `main`'s
      0.01089, still inside the ±0.03 rad interval, but now on a creep that
      ends on `ftol_runs` at λ 1.38 after 105 evaluations and moves 1e-5
      with each nudge. The profile behind the interval is the real fault:
      every refit has one column at 1.3e-7 to 5.4e-7 of the largest (the
      polar angle at its own fixed direction), and most refits end
      `exhausted_fp64` at λ 1e10 after 12 evaluations without moving, on
      `main` too. The upper side warm-starts from a first refit that
      wandered 193 evaluations, so Δχ² there rises from 5.8 at φ 0.028 to
      11.2 beside the fit, and the interval's upper end lands on the value.
      So the held scale lands together with the rule below.
- [ ] **A column that is rounding noise from a stage's first iteration.**
      The held scale cannot help it: a running maximum of noise is noise,
      and noise normalised to unit norm is a random direction with a huge
      physical step. Two measured cases. The parked exact angle column
      (`wp1953-central-angle-columns`, cherry-picked over the held scale):
      the moment stage's angle column is 1.7e-13 of the largest where the
      smallest real one is 3.2e-5, and LM stops on `ftol_runs` at λ 4e6-2.4e9,
      χ²_red 0.978236, 0.979134, 1.335554 and 1.352919 for β₀ 101.0, 101.1,
      101.5 and 103.0. And the profile refits above, at 1.3e-7 against a
      real 1.6e-5. A cut on the relative norm alone risks holding a real
      parameter in silence, since parameters refine in their own units and
      two decades separate those last two. Candidates: a floor from the
      column's response to a finite step (the WP's "finite-rotation
      response"), or a floor from the column's own difference noise. scipy's
      TRF runs these unscaled (`x_scale=1`), which is why it never meets
      either. Measure across the grid, then land the held scale and the
      parked branch with it.
- [x] Re-measure the goldens and the acceptance grid under the FCJ limit
      and the projected-CG step (this PR). Full suite on `243863de`, macOS
      arm64, `[dev]`, Python 3.12.10, 26 m 41 s with another session's
      benchmark and this session's NAC runs loading the machine: 9553
      passed, 186 skipped, 3 xfailed, 1 failed, the failure the missing
      validation-matrix row for the new FAP Pawley test, since added. No
      golden moved.
- [ ] Re-measure the goldens and the acceptance grid again when the held
      scale lands, and the Linux arm64 two-site winner with it.
- [x] The basin: five starts 1e-14 apart per fixture under both drivers.
      Write down whether LM's and TRF's answers differ by start or by driver.
      Measured 2026-10-12 on the shipped tree (macOS arm64, `[dev]`), cell a
      nudged by −2…+2 × 1e-14 relative, default plan, `mode="pawley"`.
      FAP.XRA: LM gives Rwp 0.07824432 on all five starts; TRF gives
      0.07826556, 0.07826736, 0.07833952, 0.07838295 and 0.07992336, a
      spread of 1.7e-3, every stage converged under both. **So the
      difference is the driver's, and LM's answer sits below TRF's whole
      spread**; TRF's lands by start. 11-BM NAC: LM gives 0.12620721 on all
      five; TRF's one start gives 0.13483346 (five would cost about an hour
      at 750 s each, not run). The WP-1938 finding that LM settles above TRF
      on FAP was the exact step's eigenvalue cut, and does not survive.
- [x] Tests + obs/calc/diff PNGs to `tests/output/` for each fit whose answer
      moves. `fap_pawley.png` (new acceptance row) and `qarr_cpd-1a*.png`
      looked at: calculated tracks observed, the residual a small
      derivative shape on fluorite's strongest line. `report_loop_e8*.png`
      come from `test_e8` itself.
- [x] Skill: `references/surprises.md` §8.31 says a large Pawley stage can
      stop on its budget under LM. Remove it, or restate it, once this lands.
      Removed: LM now converges FAP.XRA and NAC Pawley at or below TRF's Rwp.

## Acceptance

Every stage of FAP.XRA's Pawley fit converges under the default driver, and
its Rwp sits within the five-start spread of TRF's or the difference is
written down as a property of the fixture. `test_e8` passes on Windows.

```sh
.venv/bin/python -m pytest tests/test_pawley.py tests/test_lm_solver.py tests/test_report_loop.py
.venv/bin/python -m ruff check src tests examples
```

## References

- WP-1937 (the driver and the 128-column split), WP-1938 (the default flip,
  and the fifth session's handover entry with the measurement).
- Nocedal, J. & Wright, S. J. (2006). *Numerical Optimization*, 2nd ed.,
  §4.1-4.2. New York: Springer.
- Finger, L. W., Cox, D. E. & Jephcoat, A. P. (1994). *J. Appl. Cryst.*
  **27**, 892-900 (the axial model `model/profiles/fcj.py` implements).

## Handover log

### 2026-10-12 (second session) — CI's jax job caught the traced column at one zero aperture

The last entry said the `axial_one_zero` config covered the traced backends
at a zero aperture. Its jax and torch rows skip on `[dev]`, and CI's jax job
failed on them. At one zero aperture the FCJ kink sat on a tie between two
equal expressions. jax and torch give each side of a tie half its derivative,
so the traced axial column came out 3360 where the feasible side's is 0.047.
The kink is now capped by the tangent alone. That removes the tie and changes
no value, so no fit on the default numpy path moves.

*Done* (branch `wp1953-lm-step`, PR #918):
- `a5885a61` `fcj_offsets_weights` caps ξ_kink by |tan 2θ| alone, through
  `_tan_cap` split out of `_xi_max`. The batched twin follows, so the two
  keep one expression. Values are bit-identical. For s, h ≥ 0,
  fl(|s − h|) ≤ fl(s + h), so the dropped cap was never the smaller.
- `test_cross_backend.py::test_a_zero_aperture_column_meets_its_one_sided_difference`,
  one row each for jax and torch. It compares the `axial_hl` column at
  H/L = 0 with the one-sided central difference at the column's own scale.
  The agreement matrix cannot hold it: the column's norm is 0.047 against a
  largest column of 1.82e6, under `DEAD_COL_FRAC` (1e-6).
- `feec41cb` merged `main` `29b884d5` (#922) cleanly. No conflict remained
  at this session's start: `git merge-tree` was clean and GitHub read the
  PR as mergeable.
- `tests/CLAUDE.md` § Quoting numbers: a change to a traced path is checked
  with `[jax,torch]` installed.

*Review* (`/code-review high --fix d4318d68..a5885a61`): six findings. Two
fixed in `WP-1953: review`: the kink comment's claim holds only for
apertures ≥ 0, and the new test goes through `_assert_columns`, which adds
the cosine check. The docstring now names torch too. Three declined. The
numpy analytic column at H/L = 0 sits 0.240 rel-L2 off the same reference
and no test checks it; fixing it changes how `forward.py` differences the
FCJ nodes at a bound and moves every fit that frees the ratio. The matrix
treats a column as dead relative to its largest, so any small-scale column
escapes every backend row; changing that needs its own measurement. The
batched routine still writes out the tangent cap, because `_tan_cap` reads
the active backend and the batch is numpy-only.

*Measured* (macOS arm64, `[dev,jax,torch]`, Python 3.12.10):
- CI run 38290626822 on `d4318d68`: `fast jax 1/2` failed
  `test_jacobian_matches_analytic[jax-axial_one_zero]` and
  `[jax+fp32-axial_one_zero]`, `axial_hl` at rel-L2 1.000.
- The `axial_hl` column at H/L = 0 on that config: numpy analytic norm
  0.0486, one-sided central difference 0.04696, jax 3360 before the fix and
  0.04696 after (rel-L2 1.49e-3, torch the same). With the tie restored, the
  new test fails at rel-L2 7.156e4 on jax and on torch. The nightly
  `[torch]` job would have failed too.
- Fast suite on the tree merged with `main` `29b884d5`, no other suite
  running: 9482 passed, 33 skipped, 3 xfailed, 0 failed, 6 m 23 s, before
  the review. After it, 9481 passed and 1 failed, 6 m 29 s. The failure was
  `tests/CLAUDE.md` two lines over its cap from this session's rule, since
  folded into the bullet's own three lines, and `test_docs_consistency.py`
  passes 25 of 25. No `[dev,jax,torch]` baseline from before this session
  exists, so the count check is the added tests: +1 test, 2 cases, which
  skip on `[dev]`. They cost 0.56 s together on that run, the state shared
  with the `xb-axial_one_zero` group.

*Gotchas:*
- Not generalised: `caglioti.py`'s `xp.maximum(g2, _MIN_GAMMA_G2)` ties when
  U and V are both zero beside W on its floor. It is the only other
  `minimum` or `maximum` on the traced path found to sit on a bound LM lands
  on. `sharp_widths` covers W on its floor with U and V nonzero. Not probed.

*Next*, unchanged in order from the entry below: (1) a rule for a column
that is rounding noise from a stage's first iteration; (2) the held scale
and the parked branch with it, then the goldens and the grid; (3) the Linux
arm64 two-site winner. Two of this review's declines join (1), since both
are about a column tiny beside the largest. The numpy `axial_hl` column at
a zero aperture is 0.240 off its one-sided difference, and the matrix's
dead-column cut hides any such column from every backend row.

### 2026-10-12 — the Windows gate fixed and the large Pawley step replaced; the held column scale measured and left out

The Windows release gate's failing test was a crawl, not a platform bug. The
axial-divergence profile jumped at a zero aperture, LM's exact step landed
on that zero, and the stage ran out its 400 evaluations wherever rounding
left it. The profile now takes its physical limit there, and the test ends
at the same χ²_red on Windows, Linux and macOS runners, TRF's own. A Pawley
fit above 128 columns now converges under LM: the old approximate step was
wrong in sign, and the projected conjugate-gradient step that replaces it
reaches TRF's basin on FAP.XRA and a lower Rwp than TRF on 11-BM NAC, the
same from five starts. The third crawl, beside a column that vanishes at its
minimum, has a measured remedy (keep each column's largest norm as its
scale), but it moved a flat angle's stop and exposed a fourth defect, a
column that is rounding noise from a stage's first iteration, so it did not
land.

*Inherited pruned on arrival:* all six notes folded into Context (the
Windows `test_e8` section, the vanishing-column section) and Tasks; none
was stale. The 1.8.0 notes' bullet became the staged 1.9.0 note.

*Done* (branch `wp1953-lm-step`, PR #918):
- `5ba19a83` FCJ at a zero aperture: one ratio at 0 is the h → 0⁺ limit,
  a uniform weight over [0, s]; only both at 0 is off. `fcj.fcj_live` is the
  one off-state test, read by the weights, the node count, the compile
  sizing, the axial columns, the indexing peak fit and its window, and (the
  review) `indexing.diagnostics.undeclared_instrument`. Manual Part 2's FCJ
  section, `help.py`'s `axial_hl` entry and the staged note follow.
- `33f93e55` → `243863de` `bccg.projected_cg`, the LM step above
  `BVLS_MAX_COLUMNS`; Coelho's `bccg.solve` stays as the paper's method with
  no caller in the driver. The held column scale went in with it and came
  back out in `243863de`.
- `test_acceptance_fap::test_a_pawley_fit_past_the_bvls_cut_converges_every_stage`
  and its validation-matrix row; skill §8.31 removed; three review fixes.

*Measured* (macOS arm64, `[dev]`, Python 3.12.10 unless named):
- Throwaway probe workflows, branch deleted after: run 38272975913 (FCJ
  alone) and 38280327011 (shipped tree), Python 3.13 `[dev]` on
  windows-latest, ubuntu-latest and macos-latest. `test_e8` passes on all
  three; the episode ends at χ²_red 51.2997726156772 on macOS and agrees to
  ~1e-11 elsewhere. The macOS runner still fails the stationary-angle
  interval row with `main`'s digits (0.004349 against 0.003091).
- FAP.XRA and NAC Pawley under every candidate step, offline per-solve
  timings on 37 captured systems, and five-start basins: the tables are in
  § The step above 128 columns, measured, and the basin task.
- Fast suite on this branch merged with `main` `a7e71bf7`: 9278 passed,
  179 skipped, 3 xfailed, 0 failed, 11 m 17 s with another session's suite
  holding load averages at 145-158. No local `main` baseline was taken
  (`tests/CLAUDE.md`, the ladder's rung 4), so the delta is stated as tests
  added: `test_bccg.py` +3 tests (8 cases), `test_lab_instrument.py` +2 (3
  cases, and the singular-integral test parametrised 1 → 3), `test_lm_solver.py`
  +1 renamed and +1 strict xfail, `test_cross_backend.py`'s `axial_one_zero`
  config (its jax and torch rows skip on `[dev]`), and the slow FAP row.
  The added fast tests cost 0.21 s together on that run.
- Full suite on `243863de` before the review and the merge: 9553 passed,
  186 skipped, 3 xfailed, 1 failed (the missing matrix row, since added),
  26 m 41 s under load. Every acceptance suite passed, the QPA, Stephens
  and SRM 660c protocols included, and no golden moved. Full suite on the
  merged tree (`5c82a90b` plus this entry), run alone once the other
  session's suite had finished: 9579 passed, 190 skipped, 3 xfailed, 0
  failed, 23 m 22 s. `main` then moved 13 commits (the TOPAS P1 export,
  WP-1317's series forward pass), touching none of this branch's code; on
  the re-merge with `a8960f79` the fast suite gives 9304 passed, 179
  skipped, 3 xfailed, 0 failed, 4 m 57 s alone. The full suite was not
  re-run on that tree.

*Review* (`/code-review high --fix`): four fixed. The traced backends
differentiated a constant weight at one zero aperture (about 245 against
the true 0.01), now the trapezoid's one-sided weight with unchanged values,
and a new `axial_one_zero` cross-backend config covers it. The batched
bases' reference loop and the undeclared-instrument check now read
`fcj_live`. Three declined: `projected_cg` makes no eigenvalue cut at λ = 0
(FAP and NAC measured fine; a ±inf-bounded near-null direction could take
a long first step that LM then rejects); it ends on a zero-curvature
direction without trying a release; and a fixed zero ratio is floored to
0.02 for sizing beside a positive one, which is #774's rule.

*Gotchas:*
- The held scale cannot help a column that is small from a stage's first
  iteration. Its cut-off cannot be a relative norm alone: the noise column
  sat at 1.3e-7 of the largest beside a real background column at 1.6e-5.
- `test_stationary_moment_angle`'s interval row reproduces its runner
  failure on this Mac under a +1e-14 nudge of the start tilt
  (`_fit(0.0, two=False, seed=2, start_tilt=0.04 * (1 + 1e-14))`), but only
  once the azimuth's stop moves, which the held scale does.
- WP-1937's "NAC Pawley, 142 columns" is not the default plan's NAC Pawley,
  which solves 1 492-1 499.

*Next*, in order: (1) a rule for a column that is rounding noise from a
stage's first iteration, measured on the nudged interval row, the parked
exact angle column's four moment-frame arms and the acceptance grid; a
floor from the column's response to a finite step is the first candidate.
(2) Land the held scale with it and the parked branch
`wp1953-central-angle-columns`, re-measure the goldens and the grid, and
check whether `solve_magnetic`'s moduli-first stage is still needed (freed
together, the held scale found the two-site truth). (3) The Linux arm64
two-site winner. Whether to delete Coelho's `bccg.solve`, now unused by
the driver, along with the manual's §Coelho (2005) source line, is the
maintainer's call.

- **2026-10-11** — Filed from WP-1938's last open task when #883 merged
  without a fix. No open WP owns the step above `BVLS_MAX_COLUMNS`. WP-1334
  owns stopping a stage that improves little, which would shorten this
  crawl but not end it, and WP-1929 owns esds. Next: the first task, since
  the decision needs more than one fixture.

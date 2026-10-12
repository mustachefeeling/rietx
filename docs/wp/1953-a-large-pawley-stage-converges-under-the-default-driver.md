# WP-1953 — a large Pawley stage converges under the default driver

Milestone: unscheduled · Status: 🔄 2026-10-12 — claimed by @yue-here
Track: What fires, and what stays silent
Depends on: —
Priority: P1 2026-10-12 — was P2: WP-1954 found the Windows release gate red on `test_e8` from a platform-dependent LM stop, every Windows run since that day, so each cut ships it as a known issue until this lands

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
running-max column scale (its task below) unless a row says otherwise.
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
| TRF (WP-1938's row) | converged | | 0.07825358 | 20.2 s |

11-BM NAC, 1 492-1 499 columns, not the 142 WP-1937 quoted:

| step | stages | Rwp | wall |
|---|---|---|---|
| BCCG as shipped | `profile` on `max_nfev` 400, 68 no-descent | 0.15340222 | 299 s, loaded |
| projected CG, tight | every stage converged | 0.12620514 | 326 s, loaded |
| projected CG, 2n budget | every stage converged | 0.12620721 | 74 s |
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

## Non-goals

- When a stage that is improving little should stop and say so: WP-1334.
- Esds at a stopping point beside a flat column: WP-1929.
- The constrained step's cost and its `nnls` fallback: measured and closed in
  WP-1938.

## Tasks

- [ ] FCJ at a zero aperture: one aperture at 0 is the limit, both at 0 is
      off. The siblings are the compile sizing (`fcj_on`), the axial
      column's `axial_ok`, and the indexing peak fit's own `fcj` flag. A test
      that the profile at H/L = 0 is the H/L → 0⁺ limit, and that e8's
      verify stage lands on 0. Re-measure what frees one aperture from 0
      (QPA sample 1 and cpd-2, Stephens brucite, the `rietx compare`
      standards). Stage the note in `docs/releases/1.9.0.md`.
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
      0.003091, so it is the vanishing-column task's.
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
      stage, the two-site Pnma set and `_LM_FALSE_CONVERGENCE`; decide; land
      it with the parked branch; re-measure the goldens and the acceptance
      grid, and the Linux arm64 two-site winner.
- [ ] The basin: five starts 1e-14 apart per fixture under both drivers.
      Write down whether LM's and TRF's answers differ by start or by driver.
- [ ] Tests + obs/calc/diff PNGs to `tests/output/` for each fit whose answer
      moves.
- [ ] Skill: `references/surprises.md` §8.31 says a large Pawley stage can
      stop on its budget under LM. Remove it, or restate it, once this lands.

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

- **2026-10-11** — Filed from WP-1938's last open task when #883 merged
  without a fix. No open WP owns the step above `BVLS_MAX_COLUMNS`. WP-1334
  owns stopping a stage that improves little, which would shorten this
  crawl but not end it, and WP-1929 owns esds. Next: the first task, since
  the decision needs more than one fixture.

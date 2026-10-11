# WP-1938 — every parameter refined in its own units

Milestone: unscheduled · Status: ✅ 2026-10-11 — shipped in #883; the large Pawley stage moved to WP-1953
Track: What fires, and what stays silent
Depends on: 1936 (the FD step, landed 2026-10-09), 1937 (a driver that handles widths on zero, landed 2026-10-10), 1940 soft (merge after it, so the re-pinned numbers and the grid are the shipping kernels'; the work can start before)

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
  exist only because of the trap. (Superseded in part 2026-10-11: PR #849
  merged on 2026-10-09, so they are on `main`, called from `refine.py` and
  `multi.py` beside `seed_softplus`.)
- `least_squares._fd_typicals` (WP-1936) sizes a column's step by
  `FLOOR_SEEDS` only when the row is `identity` *and* its lower bound is at
  least 0, or its unit is deg². A softplus row keeps 1, its θ being
  logarithmic. Under physical coordinates with `lo = max(lo, 0)` every width
  qualifies. A width given a negative lower bound would not, and would go
  back to an absolute step. The bound is how an offset (zero shift, peak
  position, both in degrees) is told from a width.
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

**The default driver flips here, with the coordinates, in one PR**
(WP-1937, maintainer decision 2026-10-10). Each half alone is worse than
today. Grid of `examples/probe_driver_grid.py` (14 acceptance fits, five
starts nudged by 1e-14, macOS arm64, `[dev]`, `src` at `790c7ce7`), fits
whose χ²_red spread is over 1e-9: softplus + TRF (today)
3, softplus + LM 7, physical + TRF 4 with `max_iter` on brucite, corundum and
brucite + Stephens, physical + LM 2 with no `max_iter` anywhere. On 1937's
final tree, whose LM start is no longer nudged 1e-12 off a bound (`4708b855`),
physical + LM misses on brucite + Stephens alone. Residual evaluations over
twelve fits: 1292 today, 1065 physical + LM, 2717 physical + TRF. In softplus
coordinates the exact LM step drives widths to u ≈ −400, their columns die,
and stages end on `ftol_runs` after moving Biso by 4e-9, so softplus + LM must
never ship as the default. The full table is in WP-1937's 2026-10-10 handover
entry.

**Issue #900: a restated `min=0.0` meets TRF** (folded 2026-10-11 from the
issue triage, PR #901). Before this WP, `schemas.common.declared_fills`
inherited a declared transform only when the caller omitted every bound it
enforced. So `Phase.scale=Parameter(value=1.0, min=0.0)` came back identity
with a hard bound at zero, which is the coordinate system this WP now applies
to every field. The issue's script (synthetic PbSO₄, one stage freeing
everything, scale started 2400× high; `08176f6f`, macOS arm64, `[dev]`):
softplus + TRF, identity + LM and softplus + LM all reach χ² 7111 (Pb Biso
1.48). Identity + TRF converges at χ² 2.657e5 with Pb Biso 61.1, in 153
iterations, and `x_scale="jac"` lands in the same basin in 92. So the LM
default closes #900, and `solver="trf"` keeps the failing row. The triage
declined an interim fix to `declared_fills`, and told the reporter that
`solver="lm"` or omitting the `min` works until this WP lands.

**The 16 suite failures under physical + LM**, out of 455 tests in the
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

**Numbers that move with the flip** (physical + LM against today): the
LaB₆ free-Gaussian plans swap between two genuine minima, 9.661408 and
9.840220, by schedule (no test runs them); brucite + Stephens +4.8e-2
(the cone is enforced); absent phase −8.0e-7 (the coordinates); FAP
+5.5e-8, Si 640c +7.5e-8, corundum +1.4e-7 (inside today's own
five-start range); NAC Pawley Rwp 0.13478 against 0.13628. Above 128
columns the LM step is still BCCG's (`lm.BVLS_MAX_COLUMNS`).

**Two review findings 1937 declined, both moving converged fits if
changed.** `lm._solve_step` ignores `lsq_linear`'s status. BVLS can stop
at status 2 (cost change under `tol`·cost, where the cost carries
½‖c‖²); the review saw it on 125 of 400 random ill-conditioned systems,
each step feasible and still downhill, so no harm was shown. And the
step recomputes `eigh` for every λ trial, though the eigenvectors do not
depend on λ. Measure either on the grid before changing it.

**Two baselines that are not minima** (WP-1936, 2026-10-09). Brucite with
the Stephens block under softplus + TRF spans χ²_red 7.635871–7.636119 across
four FD steps that differ by 1e-12, and two of eight runs stop on `max_iter`,
under the old step and the new. LaB₆ + cBN with `u v w x y` free now reaches
9.793673 under softplus and 9.840220 under physical coordinates, each at every
step, so the two coordinate systems no longer meet on that fit (both met at
9.6614 under the old step).

**The kernels** (WP-1940, closed 2026-10-11). rietx-kernels 1.2.0 is on PyPI,
and rietx's floor stays at `>=1.1`. On arm64, 1.2.0 gives 1.1.0's bits, so a
grid or re-pinned number measured on a Mac does not depend on which wheel is
installed. On x86-64 the FCJ kernels call SLEEF's exponential in 1.2.0 (within
1 ulp), so a compiled-path number from an x86-64 machine or CI runner quotes
`rietx_kernels.__version__`. The bit goldens are the numpy path's and do not
move.

**Decisions taken 2026-10-11** (first session, after the fast suite's first
run under the change: 68 failed, 9013 passed, 188 skipped on macOS arm64,
`[dev]`; 18 of the 68 pass under physical + TRF, so they come from the
driver alone).

- *D1, the table.* Every entry is built `identity`;
  `params.transforms.physical_bounds` turns a declared transform into the box
  it enforced (softplus and exp `lo = max(lo, 0)`, logit also
  `hi = min(hi, 1)`).
- *D2, the driver.* `optimize.least_squares.DEFAULT_SOLVER = "lm"`, read by
  every signature that defaults `solver=`, the GUI's included.
- *D3, a plan's seed stays.* `Stage.seed` and `suggest()`'s probe seeds keep
  acting through `ParameterTable.seed_floored`, on a free row whose lower
  bound is at least 0 and whose value sits on it, never on the transform
  word. A row merely below the seed is not touched (issue #499): selected
  that way, the roughness stage's 0.3 lifted Pitschke `tau` from its 0.05
  default to its maximum. The probe's 1e-3 seed reaches only rows whose unit
  has a `FLOOR_SEEDS` size, since seeded by bounds alone sample transparency
  moved every peak in the probe's second build. The roughness seed's reason
  is the plan's start, not a dead column: the lane measured Suortti b's
  column at b = 0 as 2.7e6 against the scale's 1.9e6 (synthetic LaB₆, Bragg
  Brentano). Whether the extinction and magnetic-width seeds still change an
  answer is the Seeds task's measurement. (Superseded in part 2026-10-11,
  third session: D11 deletes the probe's width seed and both of those.)
- *D4, the floor seed goes.* WP-1930's `seed_floor`, its `FLOOR_SEEDS` use
  there and `SOFTPLUS_FREED_AT_FLOOR` existed only for the trap, and WP-1937's
  grid measured physical + LM without them. `FLOOR_SEEDS` survives as
  `_fd_typicals`' step table (WP-1936). `StageResult.seeded` stays, recording
  what `Stage.seed` lifted.
- *D5, a floor is an ordinary bound.* `bound_untested` and its `None` third
  state go, so a scale or width on 0 is answered by `bound_findings` and keeps
  its marginal esd (WP-1929's decided rule). Until WP-1929 gives a floor its
  own code, `BOUND_HIT` on a lower limit of exactly 0 must not advise widening
  the bound.
- *D6, the stored field.* `Parameter.transform` leaves the schema. A
  `mode="before"` validator on `Parameter` folds a stored or passed
  `transform` into the bounds (D1's map), as
  `Instrument._migrate_v1_2_background_peaks` does for a vanished field, so
  every read point and old python code both open unchanged in meaning.
  `SCHEMA_VERSION` takes a bump.
- *D7, the Γ_G² clamp is kept out of reach* (the maintainer's choice,
  2026-10-11). LM's exact step puts W exactly on 0. With U and V near 0,
  Γ_G² then falls under `caglioti._MIN_GAMMA_G2` (1e-8 deg²) at every point,
  so the U, V and W columns are exactly zero and the stage stops in place.
  Measured on the manual's minimal NAC call (macOS arm64, `[dev]`): Rwp
  0.18028 under LM against 0.13375 under TRF; with W's floor raised to 1e-8,
  LM lands on TRF's minimum to four digits. The 150 K Cr₂WO₆ fixture ends at
  0.2546 against 0.0994, with U and V negative. GSAS-II clamps the same way
  (`sig = max(0.001, sig)` centideg², `GSASIIstrMath.GetReflSigGamCW`) but its
  Marquardt takes no bounds, so nothing lands on a floor there. The rule:
  Γ_G² ≥ `_MIN_GAMMA_G2` at every reflection is an LM `LinearInequality`,
  beside the Stephens cone, and `RESOLUTION_NOT_POSITIVE` stays the guard
  under TRF. Measure it on NAC, the 150 K fixture and the grid before relying
  on it, since it inherits the cone's truncation stall. If the stall bites,
  the fallback is W's floor at 1e-8, with the reason recorded.
  *Measured the same day:* the inequality (`7a849e7d`) fixed NAC (0.13375)
  and the 150 K fixture (0.09924) but stalled on 3 of the 14 grid fits
  (lab6_uvwxy1 χ²_red 12.993 against 9.661; lab6_uvwxy `no_descent`;
  bt1_xray 2.4262 against 2.3838), each wanting Γ_G² under the clamp at most
  reflections. W's floor alone (`cf31d595`) fixes NAC and leaves only the
  cone stall on the grid, but the 150 K fixture stays trapped at 0.25458:
  U −0.0767 and V −0.179 put Γ_G² under the clamp at 31 of 31 reflections.
- *D8, the step holds the inequalities* (the maintainer's choice,
  2026-10-11). LM's step solves its quadratic programme with the linear
  inequalities inside it, rather than truncating a box-only step against
  them. That is the cone-stall task, and it lets D7's inequality return on top
  of W's floor. The LaB₆ free-Gaussian answers move, since their optimum now
  lives in the clamp region.
- *D9, brucite + Stephens is a recorded exception* (the maintainer's choice,
  2026-10-11, second session). Its spread is a property of the model's edge,
  not of the driver. Six of 43 reflections end exactly on the cone's edge,
  where the width √σ² has infinite slope. Lifting any of them raises the cost
  as √h, so each is a genuine minimum in that direction. The forward-difference
  columns there read the √ secant or 0, and LM stalls with one face set at
  costs 4e-5 apart (χ²_red 7.7177-7.7202). A 1 ppm strain floor gave one
  answer (7.7406) at 0.3 % worse χ², and smaller floors brought the stall
  back, so it was declined. No code surveyed keeps σ² ≥ 0 at all, and no
  quoted number rests on the fit: VALIDATION.md declares brucite's S_HKL
  unquotable, and the test asserts 0.17 < Rwp < 0.20. That bracket is this
  fit's bar on the grid. A formulation that cannot go negative is WP-1946.
- *D10, one minimum is judged by the answer* (the maintainer's choice,
  2026-10-11, third session). A fit has one answer when every refined value
  agrees across the five starts to under 0.01 of its esd. The χ²_red spread
  is reported beside it under the old 1e-9 bar. Brucite isotropic (1.1e-8)
  and corundum (3.5e-8) pass the first and miss the second, and the cause is
  frozen-per-stage windows rather than the driver. An intermediate stage
  stops at ftol 1e-6, so the starts leave it slightly apart. On corundum
  that put two window edges, of about 200, one data point apart at the last
  stage's compile, and that stage's cost then differed by 2.1e-5. The answers
  differ by 4.5e-5 esd (brucite) and 3.7e-3 esd (corundum). Re-solving the
  last stage once on a fresh compile collapses the spreads to 1.1e-10 and
  3.3e-12. It was declined, since it moves every fit's final χ² (by −1.7e-5
  and −6e-5 here) and costs 6-8 evaluations a fit.
- *D11, the seeds* (measured 2026-10-11, third session, macOS arm64,
  `[dev]`). Four go and one stays.
  - The extinction stage's 1e-3 fired on both BT-1 fits alone, and moved χ²
    by at most 1.8e-13 and any value by at most 3.4e-8 esd.
  - The magnetic-width step's 0.05° moved nothing on four planted MnF₂ cases
    (χ² 1e-14, values 2.3e-6 esd).
  - `suggest()`'s 1e-3 width seed now invents suggestions. Seeded, BT-1
    X-ray's leaders were the four phase widths (gain up to 18 910) and Si
    640c's `profile.x` and `profile.y`. Freed and refitted, each stays on its
    floor at Δχ² 0.000. Unseeded, the leaders are `atoms.2.occ` (predicted
    946.6, real Δχ² −945.5) and extinction (predicted 758, real −2479).
  - A series' warm refit took the plan's largest seed, 0.3 wherever the
    roughness stage is in the plan, and lifted every freed row on its floor.
    On the LaB₆ ramp of `test_sequential.py` it lifted a converged
    `profile.y` and extinction from 0 to 0.3, and pattern 1 ended at χ²_red
    1.05828 against 1.05145 unseeded. The warm refit now takes no `seed`, and
    keeps the plan's `strain_seed`.
  - The roughness stage's 0.3 stays (D3: it chooses where the solve starts).
- *D12, a moment's angles turn after its size climbs* (the maintainer's
  choice, 2026-10-11, fourth session). A moment angle's column scales with
  the modulus and vanishes at a direction the symmetry fixes. There the angle
  is set only by the curvature term Gauss-Newton drops. LM scales each column
  to unit norm, so such an angle takes the largest step and λ grows until
  everything crawls. On the two-site Pnma set the released starts stopped at
  χ² 454 660 with λ 5e7-7e9 and reported `converged`. TRF reached 2555.8, and
  a modulus-only first stage under LM reached 2556.06. So
  `solve_magnetic`'s default plan gains that stage
  (`SOLVE_STAGE_NAMES`). A test whose trial still crawls is re-pinned to the
  verdict, which excludes a trial stopped short. The driver side (a crawl
  that reports `converged`, for any magnetic plan a user builds) goes to
  WP-1929 task 4, which owns moment angles at a stationary direction.
- *D13, a series' moment may come back reversed* (the maintainer's choice,
  2026-10-11, fourth session). Reversing every moment gives the same powder
  pattern. The moment-angle series' two chains now end on reversed (TRF) or
  reversed-and-mirrored (LM) branches at equal χ², and the series fences read
  that as 92σ of path dependence. `origin/main` passed by which branch it
  landed on. The test keeps its #604 claim and checks that the finding it gets
  is such a branch. Teaching the fences which moment directions a powder
  cannot tell apart went to WP-1329's Inherited rather than a new WP, since
  1329 owns the moment's path-dependence flag (the template's fold-first rule).

## Non-goals

- The esd rule for a row on its bound, and the floor diagnostic: WP-1929.
- The driver (WP-1937) and the FD step (WP-1936).
- Moment angles at a stationary direction: already identity, so untouched
  here (WP-1929 task 4).

## Tasks

- [x] The table builds identity entries for every declared transform, with
      the bounds above; `transforms.py` keeps only what migration needs.
      (Deleted: the one map left is `schemas.common.legacy_transform_bounds`.)
- [x] Read-point migration for a stored `transform`, with a fixture of a
      pre-change project and history opening unchanged in meaning.
      (`test_project.py::test_a_log_written_with_transforms_opens_unchanged_in_meaning`.)
- [x] Every reader in the list above, each fixed or deleted, and the grep that
      finds no `"softplus"` branch left outside migration. (Code done
      2026-10-11; the docs pass closed it the same day. What `grep -rn
      softplus src` still finds is migration or a dated note.)
- [x] Seeds: for each caller of `seed_softplus` and WP-1930's floor seed,
      measure whether it still changes an answer, and delete what does not.
      (D11. The extinction, magnetic-width and probe width seeds are gone.
      No warm start seeds, whether the collapsed refit, `refit="stages"` or
      the `warm_staged` rung (`sequential._unseeded`). Roughness keeps 0.3.)
- [x] The traced backends (`backend/traced.py`) and the cross-backend matrix.
      (`[dev,jax]`, macOS arm64: three srm660c rows failed on extinction at its
      0 floor, rel-L2 0.779, because `_laue_and_deriv` selected the constant
      arm at x = 0. The series arm is exact there; then 182 passed, 103
      skipped, goldens bit-identical. Torch is the nightly's.)
- [x] Re-measure every acceptance suite and VALIDATION.md's rows; list every
      number that moves by more than 1 % with its reason.
      (Fourth session, by a lane: 17 of 129 rows moved, each attributed on
      this tree, under forced TRF and on `origin/main`, and listed in the
      1.8.0 notes. The landing page's SRM 660c cell follows.)
- [x] Root CLAUDE.md and DESIGN.md clauses rewritten in the same change.
      (The softplus invariant became the physical-units one, WP-1463's
      clause keeps `column_rescale` without its softplus case, and DESIGN.md
      dates the transforms' removal and the driver flip.)
- [x] Tests, plus obs/calc/diff PNGs to `tests/output/` for the fits whose
      answer moves. (No moved fit is locally worse. SRM 660c's 148.7° peak
      top is underfit at 85 % of its height, 83 % on `main`.)
- [x] Skill: any rule that tells an agent to seed a width before freeing it.
      (`surprises.md` §8.6 and §8.14, a row each in `magnetic.md` and
      `diagnostics-projects.md`; both copies re-synced.)
- [x] **The default driver flip** (moved from 1937's checklist).
      (Text edits landed in the second and third sessions; its PNGs are the
      item above.) Flip
      `solver=` to `"lm"` in every signature that defaults it (`refine.py` ×4, `multi.py` ×2,
      `sequential.py` ×2, `project.py` ×2, both `run_*least_squares`,
      `LSQOutcome.solver`), as one constant; `Provenance.solver`'s `"trf"`
      default stays, since every old record was TRF. Keep `"trf"` selectable.
      Rewrite `lm.py`'s module docstring: re-measure "not a speed play" and
      "prefer the default driver on a texture plan" with
      `examples/bench_solver.py`. In `docs/manual/estimation.md` § Solvers
      the step paragraph and `stark1995` landed with 1937; its first sentence
      (the default) and the speed paragraph change here. So do
      `using/refining.md` near the
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
- [x] **Brucite's valley.** Closed 2026-10-11 as D10: the split is a
      frozen window one data point apart at the last stage's compile, and
      the answers agree to 4.5e-5 esd. No Linux run was needed, since five
      starts 1e-14 apart reproduce it here. The original text follows.
      Physical + LM spread 1.1e-8 on brucite
      (isotropic) at `790c7ce7`. Two exactly degenerate Lorentzian pairs
      (`profile.y` with `lor_strain`, `profile.x` with `lor_size`) split
      differently per start, and `axial_sl` ended at 0.2 or under 3e-10. A
      final ftol of 1e-12 left 1.4e-8. Hypothesis: the Γ_G² < 0 clamp (`u` =
      −0.049) makes the objective piecewise at that level. On 1937's final
      tree the five starts agree to 2.8e-10, but the pairs are still
      degenerate, so the agreement may be this platform's luck. Today's
      default reaches 1.7e-9. Rerun it on Linux and after the coordinates
      land; if it splits again, establish the mechanism, then fix it or give
      brucite its own bar with the reason.
- [x] **The cone stall.** Closed 2026-10-11 as D9: D8 holds the cone inside
      the step, and the spread that remains is the model's edge, not the
      driver. It moves no quoted number. WP-1946 owns a formulation that
      cannot go negative. The original text follows.
      Physical + LM spreads 1.6e-6 on brucite +
      Stephens. `sample_broadening` truncates 8 steps against the strain cone
      and stops `exhausted_fp64`, and the S_HKL differ at 7e-5 relative. BVLS
      holds boxes only, and the cone is projected and truncated around the
      step (`lm.LinearInequality`, `lm.minimize`'s inner loop). Hold the cone
      inside the step's quadratic programme, or show the stall moves no
      quoted number. Under LM brucite + Stephens reaches χ²_red 8.00056
      against TRF's 7.636, a point outside the cone.
- [x] The 16 suite failures above, each fixed or given its reason.
      (The last three, fourth session: the two-site pair test and the 150 K
      solve by D12, `solve_magnetic` freeing the moduli first; the
      moment-angle series by D13, a powder twin the fences cannot see.)
- [x] Issue #900's script as a test of the default driver: about 5 s, no
      download, and it must reach χ² 7111 (Context, Issue #900).
      (`tests/test_issue_900_restated_bound.py`, 0.6 s. With dispersion
      declared off it reaches χ² 7304, both spellings. The true parameters
      score 5777, but the one stage freezes its windows at the start's
      narrower Lorentzian widths, so the bar is twice the truth's χ².)
- [x] `solver="trf"` says what it costs now: under physical coordinates a
      positive field can land in the wrong basin (#900's 2.657e5 against
      7111), and `x_scale="jac"` does not rescue it. A docstring, or a
      diagnostic when TRF is selected; the choice is the maintainer's.
      (A sentence, no diagnostic: `estimation.md` § Solvers, `refining.md`
      and the `SOLVERS` comment, with #900's dispersion-on numbers, χ² 4.5e5
      and Pb Biso 133 under TRF.)
- [x] **An old `.rxt` row under a raised floor** (review of #883,
      2026-10-11). `gui/textdoc._check_annotations` refuses any annotation
      that differs from the live row. A document saved before W's floor
      carries `w … min 0`, and applying it fails: "min on
      instrument.profile.w is 1e-08, and cannot be edited here". March `r`'s
      floor (`MARCH_R_MIN`) is the same case one WP earlier. Old files must
      open (D6), so a stored bound the schema would raise to the live one is
      no edit. Decide where that rule lives once. `ProfileTCHZ._w_floor_is_reachable`
      owns W's, and `io/instrument_profile.py` (two sites) and `io/recipe.py`
      restate it, which the review also flagged.
      (Fifth session. The rule stays in the schema's validators.
      `textdoc._schema_keeps` re-validates the model holding the row's
      Parameter with the typed numbers, as `recipe.py` already does, and a
      number the schema raises to the live one is no edit. The value needed
      it too: an old W of 1e-12 opens as 1e-8. The two `.prm`/`.instprm`
      sites keep their line, because a negative W there is the reader's to
      refuse, and the validator would raise it silently.)
- [x] **LM's two constrained-step costs** (review of #883). When `nnls` runs
      out of iterations (`lm._NoConstrainedStep`), the fallback shortens the
      box step to the first row it reaches. From a point already on a face that
      is τ = 0, so the stage ends `exhausted_fp64` and reads as converged, and
      λ is never raised. And `_solve_constrained_step` does a dense
      eigendecomposition plus `nnls` whatever `BVLS_MAX_COLUMNS` says. The
      review measured 0.63 s a crossing at 1013 columns on a synthetic
      Pawley-shaped system, against BCCG's ≤ 22 ms, and Γ_G² rows are now built
      in every mode. Measure both on the NAC Pawley protocol and the grid
      before changing either, since both move converged fits.
      (Fifth session, by a lane: neither changed, because neither reaches a
      fit. The 14 grid fits at start 0, NAC Pawley (142 columns) and FAP
      Pawley (343) ran no `nnls` fallback. Every constrained step was at 29
      columns or fewer, and neither Pawley crossed a row. Forced onto the
      Pawley systems, the constrained step took 2.7-5.7 ms at 142 columns
      and 42-70 ms at 343, against BCCG's 0.4-1.9 ms. The τ = 0 path stays
      unmeasured, since no fixture reaches it.)
- [x] **`max_iter=0` keeps its refusal under LM** (folded 2026-10-11 from
      the triage of #890, which reached this WP through `main`). Under TRF a
      stage that frees anything with `max_iter=0` raises scipy's "`max_nfev`
      must be None or positive integer." LM ran it as one evaluation that
      moved nothing, reported as `max_iter`, so the default flip turned a
      refusal into a quiet result. `lm.minimize` now refuses a budget under
      one evaluation in scipy's words, which covers the joint fit too.
      WP-1947 still owns a refusal that names `max_iter`.
- [x] **A large Pawley under the default driver** (fifth session). Moved
      2026-10-11 to WP-1953, with the measurement, when #883 merged
      without a fix.

## Acceptance

```sh
.venv/bin/python -m pytest -n auto --dist loadgroup
.venv/bin/python -m ruff check src tests examples
```

The grid of `examples/probe_driver_grid.py`, rerun on the default driver,
reaches one minimum per fit (every refined value within 0.01 esd across the
five starts, D10) and one `profile.x` esd on BT-1. Brucite + Stephens is the
one exception (D9): its bar is the 0.17 < Rwp < 0.20 its acceptance test
asserts, on every start.

## References

- WP-1929 (the measurement and the review), WP-1930 (the trap), WP-1463 (the
  tiny-column rule this retires), WP-1102 (the read-point migration pattern).
- TOPAS 5 Technical Reference § 2.4-2.5 (limits inside the solver, physical
  derivatives); ROOT `TMinuit` documentation, parameter limits (why a
  transformed parameter's error is meaningless near its limit).

## Handover log

### 2026-10-11 (sixth session) — closed: #883 merged, the large Pawley stage moved to WP-1953

The work shipped. The maintainer merged #883 with the large Pawley stage
unfixed, so that task moved to its own WP, and the skill now warns an agent
about it. This handover closes the WP.

*Done* (branch `wp1938-close`, from `ab8d949a`):
- `b59715ae`: WP-1953 filed with the measurement, the last task here
  ticked as moved, and the dependants re-rated. WP-1929 goes to P1, its
  last blocker landed; WP-1945, 1946 and 1948 name the landing, and 1948
  stays down a rung for 1947. The fifth entry's sentence on BCCG is
  corrected in place: six of seven sampled λ > 0, not every one.
- `e1a41beb`: `surprises.md` §8.31, in budget (+1 B) by shortening §8.14's
  story and a sentence of §8.6, both this WP's own rows.

*Measured*: none new. The prose-only branch skipped `/code-review`.

*Next*: none here. WP-1953 owns the large Pawley stage. A release is owed
at once (`docs/RELEASING.md` § When): this WP was P1 and closes #900, a
silent wrong basin under TRF.

### 2026-10-11 (fifth session) — both review tasks closed; a large Pawley fit needs a decision

An old text document of a project applies cleanly again. W's new floor had
made it fail on a number nobody edited, and the check now asks the schema
what an old number becomes today. The two solver costs the review worried
about never occur on any fit measured, so neither was changed. Two tests
that failed only on Linux asserted something one platform happened to do,
and each now asserts what holds on every platform. Measuring the solver
found a real cost of the default flip, though. A Pawley fit with 343
columns stops one stage on its evaluation cap and ends 2.7 % worse in Rwp
than on `main`, and what to do about it is the maintainer's call. A stage
given no iterations is refused again under the new default, as it was
under the old one.

*Done* (on top of `d4fc4a25`):
- `8eb60025`: `test_the_step_reaches_a_face_where_truncation_stalls` failed
  on every Linux leg since the PR went ready (`c0b3e79b` and `d4fc4a25`,
  unnoticed until this session). Its counterfactual has two ways to fail
  and a 1e-15 change in the start picks one: `exhausted_fp64` after 7
  evaluations, 2.08 from θ* with S 69 % above, or a crawl to the
  400-evaluation cap, 0.83 from θ* with S 11 % above. Linux takes the
  second from (3, 3). Three starts now take both here, and the bars are
  what both share (distance > 0.5, S > 1.05·S*).
- `e735f51f`: task 1, the old `.rxt` row. `textdoc._schema_keeps`
  re-validates the model holding the row's Parameter with the typed value
  and bounds, as `recipe.py` already did. The value needed it too: an old
  W of 1e-12 opens as 1e-8.
- `92a602c9`: the Kernels job's `test_a_fit_on_the_kernels_lands_where_the_numpy_path_does[trigger]`
  failed once on Linux x86-64, `profile.x` 181 esd apart, on source it had
  passed twice. The trigger plan frees x, y and every phase's `lor_size` and
  `lor_strain` in one stage, and a phase's Lorentzian width reads only
  x + `lor_size` and y + `lor_strain` (`forward.py:1105`). So the Lorentzian
  block is the same null set as the Gaussian one the test already left out,
  and now both are left out.
- `4c61f617`: task 2 measured and closed with neither cost changed; the
  large Pawley task filed.
- `541de409`: the review's three fixes (below).
- `a670222d`: `main` merged. It had added #890's note to this WP's
  Inherited, which conflicted with the branch's pruned section.
- `f7082e00`: that note, folded and done. `lm.minimize` refuses a budget
  under one evaluation in scipy's words.
- `d4923ebc`: the second review's two fixes (below).

*Reviews*: `/code-review high --fix d4fc4a25..HEAD` found six. It fixed
four in `541de409`. A value the schema raises past the live one went into
the change set as typed, so a check passed and the apply failed. The
schema's numbers were compared after 12-digit rounding, which dropped a
typed edit past the 12th digit. The re-validation ran up to three times a
row. The kernels comment cited a figure for a set it no longer compared.
Two are declined below. `/code-review high --fix a670222d..f7082e00`
found six in the refusal. It fixed two in `d4923ebc`: the joint fit's own
test, and `minimize`'s docstring. Two went to WP-1947's Inherited
(`cherry_pick`'s `or 100`, and `Stage.max_iter` without `ge=1`). Two are
declined below.

*Measured* (macOS 26.6.2 arm64, Python 3.12.10, rietx-kernels 1.2.0,
`[dev,jax]`):
- The lane (`lane: constrained-step costs ~25`), start 0 of the 14 grid
  fits plus NAC Pawley (142 columns) and FAP Pawley (343): no `nnls`
  fallback anywhere. Constrained steps ran only at 29 columns or fewer, and
  the wrapper's count equals `n_truncated` in every fit. Forced onto the
  Pawley systems, the constrained step took 2.7-5.7 ms at 142 columns and
  42-70 ms at 343, against BCCG's 0.4-1.9 ms. One run each at load average
  67-103, beside another session's suite.
- FAP.XRA Pawley, default plan:

  | arm | `profile` stage | Rwp | wall |
  |---|---|---|---|
  | `main` `6075319c`, TRF | converged | 0.07825358 | 20.2 s |
  | this branch, TRF | converged | 0.07838295 | 11.0 s |
  | this branch, LM (BCCG above 128 columns) | 400-evaluation cap | 0.08035928 | 16.7 s |
  | this branch, LM, exact step at every size | converged | 0.08028663 | 6.3 s |
  | this branch, LM from TRF's answer | converged | 0.07825264 | |

  The stage made 635 box solves for 400 evaluations, so about 235 BCCG
  steps were rejected unevaluated as promising no descent. On eight
  sampled systems BCCG's step left its own damped model above zero at six
  of the seven with λ > 0 (+0.05 to +7e-6), and the exact solve's was
  below zero at all eight. (Corrected 2026-10-11: this said "at every
  λ > 0" and called the model value a promise.) The refined profile
  parameters of the TRF and exact-LM answers differ by at most 1.5 esd.
  Walls are one loaded run each.
- The trigger fit on the kernels from starts 1e-14 apart in `profile.x`:
  two land at numpy's x 0.04483, three at x 0 with every `lor_size` 0.0448
  higher, 181.0 esd. Every other parameter agrees to 0.01 esd, and the curve
  to 1.2e-4 σ against the 0.25 σ bar.
- CI on `8eb60025`: every CI job green, the counterfactual included. Its
  Kernels run failed on the trigger case (above). `e735f51f` ran no
  workflow, because `main` had moved and the PR was conflicting.
- Fast suite: 9217 passed, 111 skipped, 2 xfailed, in 13:10 beside a
  `/pr-review` suite in `pr-bench` at load average ~100. That is +6 passed
  against the fourth session's 9211, exactly the six cases added, and no new
  skip. Added tests, this junit: the counterfactual 0.98 s (three starts,
  two crawling to the cap), each `max_iter=0` pair 0.19 s, the `.rxt` test
  0.16 s, the bare budget test 0.01 s. `test_lm_solver.py`'s nine added
  tests take 1.52 s in all. The full suite was not run: nothing here moves
  a fit's number.
- Lanes (`session_usage.py lanes`; the session id spans the fourth and
  fifth sessions):

  | lane | est | requests | main at dispatch | lane base | re-read | main requests | left in main | main edits after | redo | lane $ | main $ | in-session $ | saved $ |
  |---|---|---|---|---|---|---|---|---|---|---|---|---|---|
  | validation-remeasure (4th) | 60 | 119 | 332K | 72K | 8K of 790K | 3 | 6K | 1 | 0 | 13.09 | 0.28 | 30.96 | +17.31 |
  | constrained-step costs | 25 | 37 | 217K | 72K | 0K of 12K | 44 | 64K | 8 | 0 | 1.73 | 3.37 | 2.87 | -2.31 |

  Selective policy (lane when main > 150K and the item is ≥ 20 requests):
  129 sessions, +2 %. The constrained-step lane cost $1.73 against $2.87 in
  session and so lost $2.31: the item was short and the main context
  217K. The trial row in `process.md` now carries both lanes.

*Declined*:
- From the first review: the `.rxt` reader raises an old number to a
  floor without saying so, though root CLAUDE.md asks a reader to report a
  repair. `TextError` has no warning level, so reporting it is a design
  change. And the counterfactual's bars sit 1.7× from the crawl branch's
  numbers, where `tests/CLAUDE.md` wants ~10×. A wider bar needs the
  spread measured on another platform.
- From the second review: the message says `max_nfev` "must be None or
  positive integer", and `lm.minimize` takes no None. The words are scipy's
  on purpose, so the two drivers refuse alike. And the end-to-end tests sit
  in `test_lm_solver.py` rather than `test_solver_seam.py`; moving them is
  churn.
- The two `.prm`/`.instprm` readers keep their one line raising W to the
  floor. A negative W there is the reader's to refuse, and the validator
  would raise it silently.

*Gotchas*:
- A PR that conflicts with `main` runs no `pull_request` workflow. `gh pr
  view --json mergeable` says `CONFLICTING`, and `gh run list` shows nothing
  for the pushed sha.
- `/code-review high --fix A..B` reviews a commit range, which scopes it to
  one session's work on a long branch.
- The lane's probe scripts are in the session scratchpad and do not
  survive it. The Pawley task in *Tasks* carries the recipe.

*Next*, in order:
1. The large Pawley task: what the step above `BVLS_MAX_COLUMNS` should do
   when BCCG promises no descent, and whether that blocks the merge. It is
   the maintainer's call. The exact step costs 1.5-11 s a step at 1000
   columns (WP-1937), and on FAP it was the faster fit. If the PR merges
   without a fix, the skill's Pawley rows need one saying a large Pawley
   stage can stop on its cap under LM and that `solver="trf"` converged.
2. Merging the PR, with or without 1.
3. Whether to free a recipe's zero `LG_eta` half (fourth session).

### 2026-10-11 (fourth session) — the last three failures had causes; VALIDATION.md re-measured; the review left two tasks

The last three tests that failed under the new default now pass, and each
failure had a real cause. Two came from a magnetic moment whose direction
barely changes the pattern. The fitting routine stepped too far along it,
slowed to a crawl, and once called a fit finished at a χ² 180 times its
answer's. The magnetic workflow now fits each moment's size before its
direction, which removes that failure there. A plan someone writes by hand can
still meet it, and WP-1929 now owns that. The third was a series check that
cannot tell a reversed moment, which a powder pattern cannot see, from a
different one, and WP-1329 owns teaching it. The validation table was
re-measured: 17 of its 129 quoted results moved by more than 1 %, each traced
to its cause. Not closing: the review of the whole branch left two findings
that need a decision or a measurement first. A second review, run after the
handover, found four more real defects and fixed them. The worst was a solver
step that could crash a fit outright on a rare iteration cap.

*Done* (5 commits on top of `dd1cac2e`, then 5 from the second review):
- `ff49f084`: D12 and D13. `solve_magnetic`'s default plan is moduli, moment,
  all (`SOLVE_STAGE_NAMES`), and the nuclear reference drops a stage that
  repeats its predecessor, so the reference fit is unchanged. The two-site test
  asserts the answer and the named pair's quadrature sum. The 150 K test
  accepts a trial stopped short with its caveat. The series test allows a path
  dependence between powder twins, and fails without the twins (checked). The
  manual's `refining.md`, the 1.8.0 notes, and WP-1929's and WP-1329's
  Inherited carry it.
- `057974f1`: `lm.minimize`'s docstring says a crawl can end on `ftol_runs`.
- `5aa667ff`: the lane's re-measure of all 129 VALIDATION.md rows, the 1.8.0
  notes' list, the landing page's SRM 660c cell (source only, since `site/` is
  ignored build output), `compare.py`'s registry text, and the Stephens,
  sequential and SRM 660c docstrings with both trees' values.
- `49776abb`: the skill's `magnetic.md` says a hand-built plan frees
  `moment.dof0` first, with copies re-synced.
- `bdeb9f24`: three fixes from `/code-review high` on #883.
- Ticked: the 16 failures, the re-measure, tests and PNGs, the driver flip.
  Added: the two review tasks above Acceptance.
- Second review, `/code-review high --fix 883` after the handover. Each fix has
  a test that fails without it (checked):
  - `fed5b3be`: the polish's optimality check in `_solve_constrained_step` is
    an `nnls` call with no catch, so its iteration cap raised out of the fit.
    Capped, the least-distance point is now the step.
  - `076e0335`: `bdeb9f24`'s "a seed above the box is not written" let a joint
    fit write a shared column's seed in one histogram and decline it in
    another, when a caller shares an instrument row across mounts with
    different `max`. `MultiParameterTable.seed_floored` asks every histogram
    first.
  - `fa4befe6`: `FLOOR_SEEDS` and `_units` comments named `suggest` as a
    reader after this branch removed its seed.
  - `93251ad7`: Γ_G² rows also come from a magnetic component's wider window
    (`cp.win_mag`), which shares the nuclear Γ_G².
  - `61379ecb`: `io/recipe._split`'s `LG_eta` hold keeps its behaviour and
    states a measured reason (below), replacing the dead-gradient one.

*Measured* (macOS 26.6.2 arm64, Python 3.12.10, rietx-kernels 1.2.0,
`[dev,jax]`):
- Two-site Pnma, class 0. The flat start lands on the swapped point (0.70,
  3.50) at χ² 2556.51 under both drivers. TRF's released starts reach 2555.85
  and 2555.95. Before D12, LM's stopped at 454 660 and 448 315 on `ftol_runs`,
  λ 5.4e7 and 7.3e9. After it, LM's reach 2555.850 (3.498, 0.700) and 2555.985
  (swapped). LM's winner has esds 0.031 and 0.159 μ_B and is paired, where TRF's
  were 0.002 and 0.001.
- 150 K Cr₂WO₆, class 3 at k = (0, ½, ½): `max_iter` after ten continuations
  under LM (102 s) and TRF (130 s), moments 0.14 and 0.58 μ_B with esds 2.3 and
  0.5. Moduli-first does not help it. The verdict is "nothing to solve" either
  way.
- Moment-angle series: forward p000 φ = 3.06481, backward 0.07678 (LM) or
  −0.07678 (TRF), χ²_red 0.992763 in both. The same on `fb2f62d8^`, so the
  seeds did not cause it. On `origin/main` both chains stayed near π and p004
  read ±3.104, 0.8σ. LM's backward chain also stops worse at p002, χ²_red
  1.048235 against 1.044684, at the stationary azimuth.
- Magnetic files after D12: the two re-pinned files 5 passed in 2:52, the ten
  files calling `solve_magnetic` 306 passed in 25 s.
- VALIDATION.md (the lane): the 17 acceptance files 156 passed, 3 skipped, in
  30:02 beside its own probes. 17 of 129 rows moved over 1 %, each checked on
  this tree, under forced TRF and on `origin/main`, and listed in the notes.
  SRM 660c a = 4.156895 → 4.156882 Å (+28 → +25 ppm), from the Γ_G²
  inequality. No moved fit's PNG is locally worse. SRM 660c's 148.7° top sits
  at 85 % of its height, 83 % on `main`.
- Fast suite on the final tree, alone: 0 failed, 9208 passed, 111 skipped,
  2 xfailed, 3:44, the third session's count exactly, since this session added
  no fast test. The branch's added tests cost about 13 s, led by
  `test_absent_phase.py`; none joins the tail.
- Full suite on the final tree, which equals `main` merged in (behind 0),
  alone: 0 failed, 9511 passed, 118 skipped, 2 xfailed, 22:04. Slowest
  setups: indexing acceptance 764 s, the 150 K Cr₂WO₆ fixture 506 s.
- After the second review, alone: fast suite 0 failed, 9211 passed, 111
  skipped, 2 xfailed, 5:53, the three added tests exactly. They cost under a
  second together. The four magnetic acceptance files, 14 passed in 2:50. On
  both Cr₂WO₆ patterns all 43 reflections' nuclear windows hold data, so the
  magnetic-window rows add no row to a measured fit. The full suite did not
  re-run: no other change can move a measured number, and main has not moved.
- `LG_eta` released, on a snapshot: DRX_33's four held halves freed, Rwp
  0.073280 → 0.073077, cells +40 and +28 ppm (0.07 and 0.10 esd). Three
  halves stayed at 0. Phase 0's strain split 0.27 Lorentzian, 0.46 Gaussian,
  esds 1.2 and 1.3. The PowderLine acceptance passed; only the two unit tests
  asserting the hold failed.
- Lanes: one, opus.

  | lane | est | requests | main at dispatch | saved $ |
  |---|---|---|---|---|
  | validation-remeasure | 60 | 119 | 332K | +3.49 |

  Trial row in `docs/milestones/process.md`: +$3.49 (+12 %), requests 1.98× the
  estimate. The selective policy's replay row reads 125 items laned, −20 %.

*Declined or deferred*:
- Review of #883 (high): nine findings. Three fixed in `bdeb9f24`. Two became
  tasks: the `.rxt` floor, and LM's constrained-step costs. Not changed: the GUI
  colouring `softplus`/`logit` as paths in an old document
  (`gui/src/lib/rxt.ts` `FLAGS`; a fix needs a dist rebuild), a second `eigh`
  per crossing step (cost only), and W's floor restated in three readers (folded
  into the `.rxt` task). `BOUND_HIT`'s floor advice still ends "Fix it at 0"
  for W at 1e-8 deg², which is zero in practice, and the tutorials quote it.
- Second review of #883 (high): eight findings. Four fixed and one restated
  (above). Two were already tasks: the dense constrained step past
  `BVLS_MAX_COLUMNS`, and the old `.rxt` W row. Declined: `seed_floored`
  lifts only a row exactly on its floor, so a TRF fit that left Suortti b a
  hair above 0 is not re-seeded. The test stays exact for issue #499, and b's
  column at 0 is live (2.7e6 against the scale's 1.9e6), so the start is not
  stuck.
- D13 asked for a new WP. It went to WP-1329's Inherited by the fold-first
  rule, since 1329 owns the moment's path-dependence flag.
- The two-site test no longer asserts `n_minima`, the winner's esds, or that it
  pairs nothing. WP-1929's Inherited asks for the last two back.
- `test_acceptance_wavelength.py`'s table and rows moved under 1 %, unchanged.
  The landing rows for QPA (1.39 wt %) and indexing were stale before this WP,
  and VALIDATION row 86's "8-14 absences" measures 6-15 on all three trees.
  None changed.

*Gotchas*:
- `from rietx import refine` gives the function. A probe imports the module
  with `importlib.import_module("rietx.refine")`.
- Setting `least_squares.DEFAULT_SOLVER` reaches no signature default, and a
  `Refinement.__init__` wrapper misses `refine_sequential`, which passes
  `solver=` itself. Pass `solver=` to the call.
- `/code-review` with a dirty tree reviews the uncommitted diff against the
  branch's upstream. Name the PR to review the branch.

*Next*, in order:
1. The `.rxt` floor task. Decide where "a stored bound the schema raises is no
   edit" lives, once, and let `textdoc` and the two readers ask it.
2. Measure LM's constrained-step costs on NAC Pawley and the grid, then decide.
3. Then the full suite on merged `main`. The PR is ready, so the maintainer may
   instead merge now and take 1 and 2 as a follow-up.
4. Whether to free a recipe's zero `LG_eta` half is the maintainer's call;
   the numbers above say the split goes unresolved on DRX_33.

### 2026-10-11 (third session) — the docs, the seeds and the grid settled; three magnetic slow tests left

The package now describes itself as it behaves. The manual, the agent skill,
the examples and the tutorials say that a parameter's limits are held
directly and that LM is the default driver. Four seeds that existed only for
the old coordinates are gone, and one of them had been recommending moves a
refit gained nothing from. A series no longer pushes a converged zero back up
on its next pattern, which had cost one pattern 0.65 % in χ². Every fit on the
grid now reaches one answer from every start, judged by its values in esd as
the maintainer chose. The two fits that still scatter in χ² do so because one
window edge falls a data point apart, not because the driver stops in two
places. Not closing: three magnetic acceptance tests fail on the slow
selection, and VALIDATION.md's quoted numbers have not been re-measured. The
session stopped there because the account's weekly usage limit stopped every
subagent.

*Done* (13 commits on top of `d23750de`):
- `f7e41574`: TRF's caveat as a sentence (no diagnostic) in `estimation.md`
  § Solvers, `refining.md` and the `SOLVERS` comment. #900's TRF failure is
  the issue's dispersion-on protocol (χ² 4.5e5, Pb Biso 133). With
  dispersion off, as `test_issue_900_restated_bound.py` declares, TRF reaches
  the true basin at 1.04e4, and the test's docstring now says which is which.
- `3f3e2908`: root CLAUDE.md and DESIGN.md. The softplus invariant became
  the physical-units rule (a bound is reached exactly, so it must be a value
  where the model and its columns are defined). WP-1463's clause keeps
  `column_rescale` without its softplus case.
- `3cb8c3c0`: D10 and the grid script. Its arms are drivers now, and each row
  records stage costs and every value's esd. The bar is 0.01 esd.
- `ad659455`: the docs pass, by a lane. Part 1, the skill (§8.6, §8.14), the
  examples, the five tutorials and the src comments. Two things were checked
  here: `method.md`'s S/L-H/L story (both drivers now leave the diagonal to
  mirror points) and the minimal call's output in `first-refinement.md`. Its
  old block was the worked example's, which named `phases.1`, so 0.1337 is
  the minimal call's own Rwp.
- `42ebdfdd`, `fb2f62d8`, `d3c202ac`: D11, by a lane on this session's
  measurements, plus `sequential._unseeded` for the two warm paths the lane
  found (`refit="stages"` and the `warm_staged` rung). The 1.8.0 notes stage
  all of it. They also paired TRF's dispersion-on χ² with LM's dispersion-off
  one, and now quote 7111 for LM on the issue's protocol.
- `1f8e10b1`: jax's extinction column at the 0 floor read 0.779 from the
  analytic one. `_laue_and_deriv` now selects the series arm at x = 0, which
  is exactly 1 there, so no value moved and the goldens are bit-identical.
- `a9c28efc`: four slow tests re-pinned by the acceptance lane, each checked
  here (NAC golden's new `lor_strain` suggestion gains Δχ² −24 017 when
  freed; SRM 660c displacement −0.0801 → −0.0791 from the Γ_G² rows; the
  kernels-vs-numpy test leaves out an exact Gaussian null set; the absent
  phase's 0-floor scale is a `BOUND_HIT` persistent finding).
- Ticked: the readers, seeds, traced backends, CLAUDE.md/DESIGN.md, skill,
  valley and TRF-caveat tasks. Not ticked: the acceptance re-measure (rows),
  tests + PNGs (no PNG looked at), the 16 failures (three remain) and the
  driver flip (its PNGs).

*Measured* (macOS 26.6.2 arm64, Python 3.12.10, rietx-kernels 1.2.0; `[dev]`
until the traced-backends task, `[dev,jax]` after):
- Grid, LM, five starts (`examples/probe_driver_grid.py --arms lm`): all 14
  under 0.01 esd. χ²_red spreads over 1e-9: brucite isotropic 1.1e-8 (values
  4.5e-5 esd), corundum 3.5e-8 (3.7e-3 esd), brucite + Stephens 3.3e-4 (7.4e-3
  esd, Rwp 0.17939-0.17942). BT-1 neutron's `profile.x` esd is 0.0098437 at
  every start.
- The window flip (D10's evidence): corundum starts 0 and 3 compile
  identically through stage 8, whose windows differ at two edges by one
  point, `[0, 50]` and `[1, 6]`. Re-solving the last stage once on a fresh
  compile collapses χ² spreads to 3.3e-12 (corundum) and 1.1e-10 (brucite).
- Seeds (D11): the numbers are in Context. Roughness 0.3 fired on no grid fit.
- `bench_solver.py`, three runs (the lane): LM 1.19-1.30× on SRM 660c and
  NAC; 11.6-14.5× and 34.1-35.3× on corundum and cpd-2, where TRF stops on
  `max_iter`. LM reaches cpd-2's texture basin (Rwp 0.13260 against 0.13297).
- SRM 660c S/L and H/L from 0.025 each: LM 0.0367/0.0254 (Rwp 0.08751), TRF
  0.0251/0.0376 (0.08668).
- Cross-backend matrix on `[dev,jax]` after the Laue fix: 182 passed, 103
  skipped across the cross-backend, jax, conformance, shim and extinction
  files.
- Slow selection (`-m slow`, `[dev,jax]`, alone on the machine): 3 failed,
  302 passed, 12 skipped, 17:36. The lane's earlier run before its re-pins
  read 7 failed, 298 passed. Slowest setups: indexing acceptance 576 s, the
  150 K Cr₂WO₆ fixture 415 s.
- Fast suite on the final tree, `[dev,jax]`, alone on the machine: 0 failed,
  9208 passed, 111 skipped, 2 xfailed, 4:54. The seeds lane's run on `[dev]`
  read 9131 / 175 / 2. The totals differ by 13: one test added since that
  run (`test_sequential.py`), and the jax modules whose skips became cases.
  So the two are not comparable. The branch's added tests cost about 13.5 s
  (local junit), led by `test_absent_phase.py` at 6.58 s for 6,
  `test_gaussian_width_floor.py` at 3.51 s for 11 and
  `test_issue_900_restated_bound.py` at 2.40 s for 2. This session's two in
  `test_sequential.py` cost 0.01 s.
- Lanes: three, opus. The acceptance lane and four agents it started stopped
  on the weekly usage limit before reporting; the tree kept their edits.

  | lane | est | requests | main at dispatch | saved $ |
  |---|---|---|---|---|
  | docs-pass | 45 | 175 | 146K | +9.77 |
  | seeds-edit | 30 | 105 | 298K | +6.71 |
  | acceptance-remeasure | 50 | 168 | 347K | +7.45 |

  Trial row in `docs/milestones/process.md`: +$23.93 (+37 %), requests 3.50×
  the estimates. The selective policy's replay row reads 125 items laned,
  −9 %.

*Declined or deferred*:
- `/code-review high --fix`, deferred for the third time. The WP is not
  closing, the PR stays draft, the three magnetic failures will move code,
  and the review's agents cannot run while the usage limit holds.
- The full suite did not run: the slow and fast selections ran separately on
  this tree, and the final tree is still to come.
- D10's settle pass (a re-solve on a fresh compile) was offered and declined.
  No WP was filed for it.
- `io/recipe.py`'s `_split` still holds an `LG_eta` half at its off state.
  Its softplus reason is gone, and the docs now describe the hold without a
  mechanism. Not changed.
- The 4 K Cr₂WO₆ width numbers in `using/refining.md` (near line 565) were not
  re-measured.
- Explicit `seed=1e-3` extinction stages in `test_acceptance_nac.py:241` and
  `test_acceptance_srm660c.py:187`, and `qpa_plan`'s 1e-4 width seed, stay as
  those tests' declared protocols.

*Gotchas*:
- A lane that dies keeps its edits in the tree but loses its report, and a
  piped pytest keeps only what was piped. Rerun with `-rf` before trusting a
  count.
- The worktree guard refuses `sed -i` with an `a\` append and any multi-line
  sed. Use Edit or a scratchpad script.
- The venv is `[dev,jax]` now, so counts are not comparable with session 2's
  `[dev]` ones.

*Next*, in order:
1. The three slow failures, each by mechanism.
   `test_pair_diagnostic_class::test_the_two_site_winner_reaches_one_minimum_and_pairs_nothing`
   reports a quadrature sum of 0.112 ± 6.043 where it should be 3.568, so it
   looks like a stall near moment zero. The lane's agent had started freeing
   moduli only in the first stage.
   `test_moment_angle_chart::test_a_series_on_the_cut_gives_no_finding_and_every_angle_in_the_chart`
   gets `SEQUENTIAL_PATH_DEPENDENT` on `moment.dof1`. Check whether
   `_unseeded` or LM moved it, by running the series on `fb2f62d8^`.
   `test_magnetic_solve_acceptance::test_the_150k_pattern_has_nothing_to_solve`
   is on the 16-failure list: under LM all four classes refine, and the test
   pairs rows to classes by index.
2. VALIDATION.md: compare every row that quotes a measured number with the
   slow run (`tests/validation_matrix.py`, then regenerate). List each move
   over 1 % in the 1.8.0 notes, and look at the PNGs of those fits.
3. `/code-review high --fix`, then the full suite on current main merged in,
   then `gh pr ready`.

### 2026-10-11 (second session) — the stored field goes, the fast suite is green, and the cone stall is the model's

A saved project, history log or `.rxt` document no longer stores how a
parameter was transformed. Every old one opens with the same meaning, and the
numbers the package computes did not move by a single bit. Every quick test
passes under the new default solver. The one fit that still scatters across
starts is brucite with a direction-dependent strain model. The cause is the
model's edge, not the solver: there the width grows as a square root, so no
slope-following solver can steer. No other program handles that edge better,
so it is a recorded exception, and WP-1946 holds an idea for removing the edge
altogether. Issue #900 is closed by this branch and has a test. Not closing:
the seeds, the docs pass, brucite's valley and the acceptance re-measure
remain.

*Done* (11 commits on top of `f7841a6d`, plus two from main):
- `248051f7`: the ten backend goldens re-captured, each move checked by
  mechanism first (below). `tests/data/README.md` § backend_goldens has the
  record.
- `95fb4008`: `test_neutron_cw`'s X-ray box reads W's floor through
  `_MIN_GAMMA_G2`. The joint test asserts one `w` column per histogram,
  because on flat data both widths now end exactly on the floor.
- `b6509529`: the P 1 runaway test names TRF, the trajectory that reaches the
  guard. Under LM the wrong cell stays put.
- `ffee6d38`: the Le Bail alternation pins re-measured under LM.
  `WORSE_START` 1.0048 → 1.0036, the middle of LM's worse-pass range.
- `b5892f77`: D9 and WP-1946 (the maintainer chose "exception + new WP" after
  the prior-art survey).
- `c7cadcc1`: D6, by a lane. `Parameter.transform` is gone and schema
  0.45 → 0.46. `schemas.common.legacy_transform_bounds` is the one map from an
  old word to bounds, used by `Parameter`'s before-validator and the `.rxt`
  parser. Breaks for old code: `transform=` on `add_variable`/`add_parameter`,
  and `Candidate.dp_du`.
- `b2beb767`: #900's script as `tests/test_issue_900_restated_bound.py`.
  #900 was folded by the merge of #901, and its Inherited entry was pruned
  into Context and two tasks.
- `7b125061`: the 1.8.0 notes. Session 1 had left them describing WP-1930's
  floor seed (deleted by D4), "the default driver is unchanged" and schema
  0.44.
- `b263a180`: `test_cross_backend[fd-srm660c]` failed here and passed on
  main. The FD reference now differences a column on its bound from inside.
- The cone stall is ticked as D9. Not ticked: the 16 failures (the fast tier
  is green, but the slow ones need step 5 of *Next*), and the traced
  backends (jax/torch are not installed here; CI's `[dev,jax]` job runs them
  at `gh pr ready`).

*Measured* (macOS 26.6.2 arm64, `[dev]`, Python 3.12.10, numpy 2.5.4,
rietx-kernels 1.2.0):
- Goldens. Main's code at `12db370b` reproduces main's goldens in this venv,
  so every move is this branch's. θ moved by exactly the softplus map. Old
  column = new × expit(u) to ≤ 3.7e-6 on every column but three: Lorentzian
  widths stored at 0 (`profile.y` in srm660c and toy_rich, `lor_size` in
  toy_stephens). Against a Richardson one-sided derivative, the old columns
  were 7 %, 45 % and 14 % off, and the new ones are off by 1.1e-6, 2.8e-8 and
  1.6e-8. D6 then left all ten bit-identical.
- Le Bail under LM: TRF's pass 1 (13.847 %) sits where Γ_G² is under the
  clamp (U = −0.0032), so LM stops at 13.918-13.920 %. The worse-pass shape
  holds from +0.20 % to +0.52 %, and +0.10 % and +0.56 % converge instead.
  The kept Rwp is 0.139185, and the slow +2 % wander gives 1.750941 kept and
  1.945486 for the next fit. Each number is identical across starts 1e-14
  apart.
- P 1 runaway: under LM the cell moves < 0.01 Å, Rwp 0.3316 at three starts.
  TRF runs away on each, with Rwp 127.7, 0.33 and 7.8e6.
- The cone (D9's evidence). Six of 43 reflections end on σ² = 0. Lifting any
  of them raises the cost as √h (+0.0032 at 1e-6, +0.10 at 1e-3, +3.3 at 1).
  The FD quotient along the lifting direction grows as 1/√h, and the
  forward-difference columns read the secant or 0. Five starts give one face
  set, with costs up to 4e-5 apart. A floor σ² ≥ ε²M² gives:

  | floor | χ²_red, five starts | last stage |
  |---|---|---|
  | none | 7.7177-7.7202 | `exhausted_fp64` |
  | 1 ppm | 7.74062688-89 | `ftol_runs` |
  | 0.1 ppm | 7.6999-7.7008 | `exhausted_fp64` |
  | 0.01 ppm | 7.7359-7.7362 | `exhausted_fp64` |

  Prior art (a Sonnet survey, GSAS-II checked at `GSASIIstrMath.py:3265`): no
  code holds σ² ≥ 0. The details are in WP-1946.
- Brucite isotropic and corundum end every stage with no Γ_G² row on the
  face. One start in five takes a different path through a middle stage:
  χ²_red 1.1e-8 and 3.4e-8 apart. That is brucite's-valley work, not D7's.
- #900 under LM: both spellings reach χ² 7304 with scale 4.18e-4 and Pb Biso
  1.479 (truth 4.2e-4 and 1.49). The truth scores 5777, but one stage freezes
  its windows at the start's narrower Lorentzian widths: `y_calc` gives 7372,
  and a fresh `predict` at the same values 6725. TRF ends `max_iter` at 4.5e5
  with Pb Biso 133, under seven warnings, so the TRF caveat is a sentence
  rather than a new diagnostic.
- `fd-srm660c`: extinction on its 0 floor is 0.78 off differenced from below,
  and the central quotient 0.389. The analytic column meets the one-sided one
  to 6.2e-6. Matrix: 54 passed, 101 skipped (the jax/torch rows).
- Fast suite on the final tree, with main `d80ca5f4` merged and no other suite
  running: 0 failed, 9131 passed, 175 skipped, 2 xfailed, 5:09. The lane's run
  read 9129 / 175 / 2, and the +2 is #900's two cases. Session 1's last run
  read 22 failed, 9089 passed and 178 skipped, on an x86-64 venv for part of
  it. The branch's 40 added tests cost 14.73 s (local junit), led by
  `test_absent_phase.py` at 7.13 s for 6, `test_gaussian_width_floor.py` at
  3.45 s for 11, and `test_issue_900_restated_bound.py` at 2.25 s for 2.
- Lanes: one, opus.

  | lane | est | requests | main at dispatch | saved $ |
  |---|---|---|---|---|
  | d6-stored-field | 45 | 224 | 208K | +2.76 |

  The trial row is in `docs/milestones/process.md`, entered as kept 1. The
  selective policy's replay row with this session's u, mo and d reads 123,
  +55 %.

*Declined or deferred*:
- `/code-review high --fix` was deferred again. The PR stays draft mid-WP, and
  the docs pass and the acceptance re-measure still move code. Run it before
  `gh pr ready`.
- The full suite did not run, since the WP is mid-flight.
- About 20 test files still pass `transform=` (`grep -rln 'transform="softplus"' tests`).
  The validator folds them, and they double as old-code coverage.

*Gotchas*:
- To probe while a lane edits the tree, export a snapshot:
  `git archive HEAD src tests examples | tar -x -C <scratchpad>/headtree`,
  then run with `PYTHONPATH=<snapshot>/src`. Every cone and #900 number above
  came that way.
- A χ² compared with the truth's needs the frozen windows in mind: a
  one-stage plan from a far start truncates its own tails.
- The worktree guard refuses `$(...)`, a variable in a path, and a `cd`.
  Write the path out.

*Next*, in order:
1. TRF's caveat, decided in this session: a sentence, no diagnostic. Put it in
   `docs/manual/estimation.md` § Solvers and the `solver=` docstrings, with
   #900's numbers. Tick the task.
2. The docs pass. The lane's list of Part 1 lines is `using/data.md` 44-52,
   196-201, 803-805, 814, 1033-1034, 1199-1201; `model.md` 195-214, 366,
   389-391; `concepts.md:246`; `recipe.md` 83, 125; `refining.md` 562,
   891-892; `gui-power.md` 45, 101; `files.md:653`; `report.md:600`. Then the
   skill's `surprises.md` 57, 186-187, `magnetic.md:55` and
   `diagnostics-projects.md:80`. Then examples (`nac_11bm.py:70`,
   `srm660c_lab.py:34`, `bench_*`, `probe_varpro.py`, and
   `probe_driver_grid.py`, whose `_install_physical` is now a no-op) and
   `src/rietx/io/CLAUDE.md:300`. Also session 1's list: the tutorials'
   `solver=trf`, `first-refinement.md:73-87`, the speed sentences in `lm.py`
   and `estimation.md` (`examples/bench_solver.py`), root CLAUDE.md's
   softplus and WP-1463 clauses, and `DESIGN.md:268,371`. Finally, stale src
   comments: `least_squares.py` 68/70/2103, `vector.py` 1018/2909,
   `staged.py` 135/288/411/535, `suggest.py:56`.
3. Seeds: the extinction and magnetic-width measurement, and the
   `SUGGEST_SEED_SOFTPLUS` name.
4. Brucite's valley: a Linux run (a temporary branch workflow), then the
   mechanism behind the mid-stage path split on brucite isotropic and
   corundum.
5. The acceptance suites and VALIDATION.md re-measured, with every > 1 % move
   listed in the 1.8.0 notes and PNGs written. The slow half of the 16
   failures gets checked here (`test_magnetic_solve_acceptance` 150 K trial,
   `test_acceptance_sequential`).
6. `/code-review high --fix`, the full suite on main merged in, and
   `gh pr ready`.

- **2026-10-11** — first session: physical coordinates and the LM default
  land, and LM's step now holds linear inequalities exactly. Not closing.

  Every parameter is now refined in its own units, and LM is the default
  driver. That removed the softplus trap this WP exists for. It also exposed a
  second trap that softplus had hidden. LM's exact step can land a Gaussian
  width exactly on zero, where the model's variance clamp makes every width
  column zero and the fit stops in place: the manual's first-refinement call
  ended at Rwp 0.180 against TRF's 0.134. Flooring W at the clamp and making
  LM hold Γ_G² ≥ 1e-8 at every reflection, with its inequalities solved
  inside the step rather than by truncating it, fixes that call and the 150 K
  magnetic fixture. Three grid fits still miss the one-minimum bar, and
  roughly a third of the WP's tasks remain, the stored-field removal among
  them.

  *Done* (12 commits; decisions D1-D8 in Context say why each went the way it
  did; D7 and D8 were the maintainer's choices after measurements):
  - D1/D2 (`6fad41ac`): identity entries with `physical_bounds`, and
    `DEFAULT_SOLVER = "lm"` in every defaulting signature, the GUI's included.
  - D3/D4 (`db5cb8fe`): `seed_floored` replaces `seed_softplus` and lifts only
    a freed row on a floor at or above 0; WP-1930's floor seed, its diagnostic
    and `StageResult.floor_unseeded` are deleted (a before-validator drops the
    stored key, which D6's schema bump must mention).
  - D5 (`15fc6105`): `bound_untested` is gone; `GuardFinding.limit` carries
    which bound held, and `BOUND_HIT` on a lower limit of 0 gets
    `refine._ZERO_FLOOR_SUGGESTION` until WP-1929 gives a floor its own code.
  - The driver flip's tests and texts (`901e55e6`): TRF-subject tests name
    `solver="trf"`, the solver-seam spy records both drivers, the Stephens
    cone texts say LM holds it, the flat-combination case at 1e-6 is a strict
    xfail (LM stops on `ftol_runs` at λ ≈ 1e11).
  - D7 (`7a849e7d`, measured, then `cf31d595`): W's floor is
    `caglioti._MIN_GAMMA_G2`, raised at read by `ProfileTCHZ` like
    `MARCH_R_MIN` and by the `.instprm`, `.prm` and recipe readers; the TOPAS
    writer imports the constant.
  - D8 (`e1cf66de`): a box step that crosses an inequality row is replaced by
    Lawson and Hanson's LSI → LDP → NNLS solve (1974, ch. 23), its active set
    then solved as equalities; a step crossing no row is the BVLS/BCCG step
    unchanged. `gaussian_width_inequalities` returns on top of W's floor, and
    `_pad_inequalities` fixes Pawley + Stephens under LM raising a shape error.
  - None of the checklist's items is complete, so none is ticked: each has a
    named remainder under *Next*.

  *Measured* (macOS arm64, `[dev]` unless marked):
  - Minimal NAC call: Rwp 0.18028 under LM before D7, 0.13375 after, equal to
    TRF to four digits in u, v, w, x, y. 150 K Cr₂WO₆ fixture: 0.2546 → 0.09924
    (TRF's). The W floor alone left it at 0.25458, with U −0.0767 and V −0.179
    putting Γ_G² under the clamp at 31 of 31 reflections.
  - The 14-fit grid (`examples/probe_driver_grid.py --arms softplus:lm`, the
    "softplus" arm now physical): with D8, over the 1e-9 bar are brucite +
    Stephens (spread 3.3e-4, χ²_red 7.7177; every late step held as λ climbs to
    6e9, likely Λ = √σ² masked to zero slope at the cone's face,
    `stephens.py:211`), brucite isotropic (1.1e-8) and corundum (3.5e-8), each
    after one held Γ_G² step. Both LaB₆ free-Gaussian plans reach χ²_red
    9.692771 (9.661421 and 9.840220 before); bt1_xray 2.383802 → 2.384175.
  - Fast suite on the final tree: 22 failed, 9089 passed, 178 skipped, 2
    xfailed, 5:25. The 22: 11 `test_backend_shim` goldens, which this venv runs
    and the session's earlier x86_64 venv skipped; D6's three
    (`test_textdoc` fixed point, `test_named_variables`,
    `test_params_surface`); three `test_neutron_cw` box pins of W's old 0
    floor; `test_joint_xray_neutron::test_the_structure_is_shared_and_the_instruments_are_not`;
    three `test_lebail_alternation` cases that D8's step moved after `15fc6105`
    fixed them; `test_cell_runaway_safety::test_a_wrong_triclinic_le_bail_fit_raises_no_degenerate_cell_error`.
    The first run, before any fix and under x86_64, was 68 failed, 9013 passed,
    188 skipped, 1 xfailed, so the two totals are not comparable. Added tests
    cost 13.86 s over 30 (local junit), led by `test_absent_phase.py` at 8.00 s
    for 6 and `test_gaussian_width_floor.py` 4.74 s for 11.
  - Slow files run by lanes: `test_acceptance_stephens` 5 of 5 (one assertion
    widened to the guard's tolerance, σ² on the face at −6.5e-16),
    `test_acceptance_nac` 3 of 3, `test_magnetic_solve_acceptance` 1 of 2 (150 K
    trial 2.7 S2(a,b) ends `max_iter`, as under the truncating driver). The
    sequential cpd-1d case from the 16-failure list no longer reproduces:
    0.13092 chained against 0.13087 alone (x86_64).
  - The full suite did not run: the WP is mid-flight, and the tree moves again
    under D6.
  - Lanes: six, all opus, $63.89 against main's $13.50; trial row in
    `docs/milestones/process.md`, saved +$52.91 (+41 %). Requests ran 4.42× the
    estimates. The selective policy's replay row reads 118, −17 %.

  | lane | est | requests | main at dispatch | saved $ |
  |---|---|---|---|---|
  | seeds | 30 | 139 | 252K | +6.83 |
  | floor-bounds | 40 | 197 | 290K | +12.23 |
  | driver-flip | 45 | 189 | 302K | +7.12 |
  | resolution-inequality | 40 | 113 | 353K | +5.22 |
  | w-floor | 30 | 153 | 367K | +9.63 |
  | qp-step | 60 | 181 | 380K | +11.88 |

  *Gotchas*:
  - Until it was rebuilt after the driver-flip lane, this worktree's venv ran
    x86_64 under Rosetta (a WP-1940
    probe's `uv python install` had made it the default 3.12). The seeds,
    floor-bounds and driver-flip lanes measured there: `lab6_cbn`'s 0.168656
    and the first fast run among them. Re-measure any of those before quoting.
  - `.claude/hooks` refuses `cd`, an `awk` program, and complex shell lines
    in this worktree; scratch scripts go in the scratchpad and run as one
    plain command.
  - LM's stall shows as `exhausted_fp64` or `no_descent` with every step held
    and λ climbing. Read the stage's truncation count before reading its Rwp.
  - `/code-review high --fix` was deferred: the PR stays draft mid-WP, and D6
    rewrites much of this code.

  Next, in order:
  1. Re-pin the 11 `test_backend_shim` goldens and the three `test_neutron_cw`
     box pins, with old → new in the commit, and fix
     `test_joint_xray_neutron`, the three Le Bail cases and the triclinic
     cell-runaway test, each by its mechanism.
  2. D6 (task 2 and the rest of tasks 1, 3 and 5): remove `Parameter.transform`
     with a before-validator, `Entry.transform`/`ParameterRow.transform`, the
     transform machinery in `vector.py`, `least_squares._fd_typicals`'s branch,
     `traced.py`'s masks, the textdoc and GUI flag words (`gui/src/lib/rxt.ts`
     `FLAGS`, `Params.svelte`; rebuild the dist), the help texts, and bump
     `SCHEMA_VERSION` naming `floor_unseeded`'s drop too. This fixes D6's three
     failures.
  3. The three grid fits over the bar: brucite + Stephens first (the cone
     task; read `stephens.py:211`'s zero-slope mask at the face), then the
     held Γ_G² step behind brucite isotropic and corundum. Decide each against
     the acceptance (one minimum per fit) before tuning anything.
  4. The seeds measurement (extinction and magnetic-width), the tutorial
     notebooks still printing `solver=trf` (`examples/tutorials/build.py`),
     `first-refinement.md:73-87`'s example output, `lm.py`'s and
     `estimation.md`'s speed sentences with `examples/bench_solver.py` on
     arm64, root CLAUDE.md's softplus and WP-1463 clauses (~line 776) and
     `DESIGN.md:268,371`.
  5. Then `/code-review high --fix`, the acceptance suites and VALIDATION.md
     re-measured with every >1 % move listed, the full suite on main merged
     in, and `gh pr ready`.

- **2026-10-09** — created from WP-1929's second session. No open WP owns the
  parameter transforms: 1463 and 1535, which last changed the floor handling,
  are closed; 1930 seeds a floor rather than removing it; 1914 reads a
  coefficient after the fit.

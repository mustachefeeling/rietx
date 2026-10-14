# WP-1325 — parametric series: a parameter as a function of each pattern's coordinates

Milestone: unscheduled · Status: 🔄 2026-10-14 — claimed by @yue-here (Claude session); scope decided, survey landed, synthetic measurement next
Track: Candidates — named on a use case, not yet on a measurement
Depends on: — (1119 soft: a named coefficient is a named variable)
Priority: P2 2026-10-14 — was P3: the maintainer took the combinatorial-library case (the first named outside user) and the scalable solver it needs; 1962 waits on that solver

## Goal

A joint fit over many patterns can refine a parameter as a declared function
of each pattern's coordinates: a temperature or time down a ramp, an (x, y)
composition across a combinatorial library, an (x, y, z) position across a
reconstructed tomography slice. All patterns go into **one joint residual**.
The function's coefficients are the refined parameters, and their esds come
from the joint covariance (Stinton & Evans 2007, "parametric Rietveld"). A
thermal-expansion coefficient, a Vegard slope or a composition surface is then
a *measured* number with an esd, rather than a curve fitted afterwards to
per-pattern values whose esds are each conditional on their own pattern. The
joint solve scales to **hundreds of patterns**, because a library is that size.

## Context

### Scope, decided 2026-10-14

The maintainer took three decisions after the survey below.

1. **The library is a target, so the scalable solver is in this WP.** The
   joint path stores its Jacobian dense, and that does not reach hundreds of
   patterns (§ What the code has). The solver tasks below make memory and
   time grow in proportion to the pattern count.
2. **Direct XRD tomography is its own candidate,
   [1962](1962-xrd-ct-a-pattern-summed-over-the-voxels-its-beam-crosses.md).**
   There, a measured pattern is a sum over the voxels its beam crosses. This
   WP keeps to one pattern, one specimen. The reconstruct-then-fit route to
   XRD-CT *is* covered here, as a library with (x, y, z) coordinates.
3. **The measurement runs on a synthetic ramp first.** The 68-pattern
   ZrMo₂O₈ ramp the first task named is not in the repo
   (`examples/bench_refinement.py:651` simulates its size only). A synthetic
   ramp with a known a(T) checks the joint fit is *right* and is re-runnable.
   The real ramp, from the maintainer's local copy, then measures what the
   joint form is *worth* on real data.

### The general shape, and which part this WP builds

Every precedent below is one case of two independent choices. Write pattern
k's calculated curve as y_k = Σ_v A_kv · f(p_v), and specimen v's parameters
as p_v = Φ(z_v)·c, where z_v are its coordinates, Φ is a basis (a design
matrix) and c are the refined coefficients.

| case | A (specimens into patterns) | Φ (parameter over coordinates) |
|---|---|---|
| `multi.py` today | one specimen in every pattern | constant |
| `sequential.py` | identity | independent per pattern |
| this WP, series | identity | e.g. [1, T] |
| this WP, library | identity | e.g. a polynomial in (x, y) |
| XRD-CT reconstruct-then-fit | identity over voxel patterns | per voxel, or smooth in (x, y, z) |
| XRD-CT direct (1962) | path lengths along the beam, plus parallax | per voxel |

**This WP builds Φ in general and A = identity only.** The number of
coordinates costs nothing extra: Φ is a matrix whatever produced it. The
pattern count is what costs, and the solver tasks pay for it.

**Linear in the coefficients is the line, and it is free.** The tie machinery
is affine, p = C·θ + d with constant C (WP-0301, WP-1070). A parametric tie
p_k = Σ_j Φ_kj·c_j is exactly an affine tie per pattern with C_k = Φ_k, so it
needs **no new Jacobian branch**: `_column_extras` reads the reach off C, and
the whole-model FD column covers what a branch does not claim. A form with a
parameter inside a power or an exponential (Arrhenius, an order-parameter
exponent, a Debye σ²(T)) is the `Parameter.expr` fence of WP-1119.

### Prior art (survey, 2026-10-14; concepts only, per the licensing rule)

**Crystallography.**
- **TOPAS parametric refinement** (Stinton & Evans 2007, user docs only):
  global coefficients feed an expression in every dataset. Müller, Dinnebier
  & Schorr (2011) refined symmetry-mode amplitudes as a Landau power law in T,
  and report better statistics, stability and lower correlation than the
  sequential route. The outside lab's polynomial surfaces are this, over
  composition.
- **GSAS-II** fits an equation to its sequential *table* after the fact.
  That is the weaker form `sequential.py` already has.
- **FullProf's multi-pattern refinements** share a parameter through a
  refinement codeword with a multiplier: one column of C, with no notion of a
  per-pattern coordinate, so any multiplier is computed by hand.
- **XRD-CT.** Wragg et al. (2015) refined a whole reconstructed slice as one
  parametric TOPAS refinement. Vamvakeros et al. (2020, DLSR) fitted the raw
  scans directly to remove parallax. Both are carried in 1962.
- **Combinatorial phase mapping** (AgileFD, Suram et al. 2017; Phase-Mapper,
  Xue et al. 2017) models composition-driven peak shift as a per-sample
  stretch of a basis pattern, and holds the Gibbs phase rule as a sparsity
  limit; Phase-Mapper's benchmarks keep phase fields connected. The lesson
  for here: **a property varies smoothly inside a phase field, not across a
  boundary.** So a tie needs a subset of patterns it applies to.

**General fitting.**
- **lmfit** `Parameters` with `expr`: arbitrary expressions, evaluated as
  code. That is the WP-1119 fence, not this.
- **Mantid simultaneous fits** share a parameter with a tie (`f1.Sigma`), and
  ISIS adds "parameter functions" computing each group's value from global
  ones (arXiv 1605.02088).
- **XAFS (IFEFFIT/Artemis)** ties σ²(T) across temperatures through a guessed
  Debye temperature: nonlinear, the fence again.
- **Global and target analysis** (van Stokkum, Larsen & van Grondelle 2004;
  pyglotaran) shares kinetic parameters across datasets, with the model
  declared as data.

**Statistics.**
- **Varying-coefficient models** (Hastie & Tibshirani 1993) are the formal
  name for "a model's coefficients are functions of a modifying variable".
  The standard fit is penalised splines.
- **Mixed-effects models** add partial pooling: each unit keeps its own value,
  pulled toward the shared surface by a penalty. That is the soft variant this
  WP leaves for later (Non-goals).

**Model-formula languages** (Wilkinson & Rogers 1973; patsy, formulaic).
`1 + x + y + x:y + I(x**2)` names a basis, and a design matrix is built from a
table of per-sample metadata. Two lessons. `I()` evaluates python, so a
formula string is code unless its grammar is closed. And patsy's stateful
transforms (`center`, `standardize`, spline knots) **record the centring they
learned and reuse it on new data**. Without that, adding a sample silently
changes what every coefficient means.

**Elsewhere.**
- **Dynamic PET, direct versus indirect parametric reconstruction** (Kamasak
  et al. 2005): fitting kinetic parameters straight from the raw data beats
  reconstructing each frame and fitting afterwards, with 30-60 % lower
  coefficient of variation in one study. The gain shrinks at high counts.
  This is the closest analogue to "joint fit versus a line through the
  trajectory", and it says what the measurement should expect.
- **Bundle adjustment** (Triggs, McLauchlan, Hartley & Fitzgibbon 2000) solves
  joint problems with a few shared parameters and many local ones per unit.
  Its normal matrix is block-diagonal with a border ("arrow"), and the Schur
  complement makes the cost linear in the number of units. Sliding-window
  bundle adjustment folds old units into a prior on the shared parameters.
  That is the long-run answer to a growing campaign.
- **Autonomous-experimentation stacks** (CAMEO, Kusne et al. 2020) describe
  each sample as a row of a table keyed by sample (composition, position,
  process), and the analysis step reads named columns.

### The shape, answering the survey's five questions

1. **Data, not code: yes.** The declaration is a pydantic model with a JSON
   round-trip. It has:
   - targets as globs;
   - a basis from a **closed** vocabulary: `constant`, `polynomial` (terms over
     named coordinates, e.g. `[[], ["x"], ["y"], ["x", "y"]]`), or `design`
     (explicit per-pattern rows; this is the escape hatch for splines,
     Scheffé mixture forms and sin²ψ);
   - the pattern subset it applies to;
   - a reference point and a scale per coordinate.

   A formula string, if one is ever accepted, is input sugar parsed to that
   form by a closed grammar, never `I()`. Gap: a joint fit keeps **no
   history** today (`multi.py:886`), so "a history node can store it" has
   nowhere to land yet.
2. **The axis lives in a coordinate table passed with the patterns**: one row
   per pattern, named columns with units. It does not go inside each tie,
   because several ties share one table. It does not go in
   `PatternData.metadata` either, which is `dict[str, str]`. `SeriesEntry.x`
   (`schemas/sequential.py:51`) stays the 1-D view of one column.
3. **Refusals before a solve**, each naming its fix:
   - a design matrix whose rank is below its basis size. QR on the centred,
     scaled columns names the collinear terms. The ternary case,
     `1 + x_A + x_B + x_C` with x_A + x_B + x_C = 1, names the fix: drop the
     intercept (Scheffé form).
   - fewer patterns in the subset than coefficients;
   - a pattern in the subset with no coordinate;
   - a target that matches in no pattern;
   - a target already driven by another tie;
   - a coefficient box whose image under Φ_k leaves a dependent's own
     `min`/`max` on some pattern. This is the WP-1119 hazard: a variable's
     bounds are the only ones the solve sees. For a linear map that image is
     exact, Σ_j min/max(Φ_kj·lo_j, Φ_kj·hi_j).
   - a target that is held, `mode_fixed`, locked or symmetry-tied (the reason
     read off `held_because`).
4. **Conditioning.** Coordinates are centred and scaled by a reference and a
   half-range **stored in the declaration** (patsy's lesson). The defaults
   are computed once at declaration from the coordinates present. Coefficients
   are reported in user units, at the reference: c₀ is "a at T_ref", never an
   extrapolation to T = 0. The normal-matrix equilibration (van der Sluis)
   fixes column *scale*. It does not fix the intercept-slope correlation that
   an off-centre axis creates, which is why centring is the declaration's job.
5. **A growing campaign.** Because the reference and scale are frozen, a new
   pattern never redefines a coefficient. A refit starts warm from the last
   coefficients. A quarantined pattern (WP-1051's rule) leaves the joint
   residual, its row of Φ is dropped, and the rank refusal re-runs. An
   unbounded campaign wants sliding-window marginalisation; that is out of
   scope.

### What the code has (survey, 2026-10-14)

- **`multi.py` is the seam: N patterns, one θ** (WP-0308).
  `refine_multi` → `MultiHistogramRefinement` is separate from `Refinement`
  and keeps no history (`multi.py:886`).
  - `SharingMap` makes a path per-histogram iff it starts with `instrument.`
    or ends with `.scale`; overrides are checked first
    (`params/multi.py:152-173`). Per-histogram paths are scoped as
    `hist.{h}.<path>`.
  - Each histogram has its own `ParameterTable` with its own C. The joint θ
    is a gather through `col_map`, and sharing is the only cross-histogram
    link.
- **One starting `Structure` is deep-copied into every histogram**
  (`params/multi.py:187`). A library needs each specimen to start from its
  own cell, occupancies and widths.
- **The joint path has no tie, variable or hold verb** (the
  `_hold_diagnostics` row at `multi.py:275`). The substrate exists:
  `ParameterTable.add_parameter`/`set_tie`. A `vars.` path counts as
  *shared* under the default rule. So the same variable in every table, tied
  per table onto `hist.{h}.` targets, folds onto one column with no solver
  change: that is the mechanism for a parametric tie.
- **Latent WP-1342 bug the parametric tie would trigger.** The joint
  absent-phase hold matches free paths by name prefix
  (`_unsupported_paths_multi`, `multi.py:374-380`). The single fit reads
  `column_reach` (`refine.py:509-513`). Once a `vars.` coefficient drives
  per-histogram cells, the prefix test cannot see it.
- **The joint Jacobian is dense, and so is everything after it.**
  - It is assembled as `np.zeros((n_rows, n_cols))`
    (`optimize/least_squares.py:2459-2469`).
  - LM forms `A = JᵀJ` from it every outer iteration (`optimize/lm.py:476`).
  - The bounded step uses BVLS on an eigen-factor up to `BVLS_MAX_COLUMNS` =
    128 columns, and dense projected CG above that (`lm.py:731-733`).
  - The covariance forms JᵀJ again (`statistics.normal_factors`).
  - At 3 000 points per pattern, 20 shared and 10 private parameters, J alone
    is ≈ 1.2 GB at 70 patterns, ≈ 22 GB at 300 and ≈ 240 GB at 1000.
  - Residual and Jacobian loop over histograms serially.
- **WP-1125's identity is the solver's equivalence bar.** The Schur-complement
  Gauss-Newton step *is* the joint step, at every point and not only at the
  optimum, measured to ≤ 6.6e-7 relative on 70 stages
  (`docs/solver-survey.md` §2.A1). It holds **only while no bound is
  active**: a bounded local block (phase scales) leaves the identity once a
  bound binds.
- **Soft restraints are refused in a joint fit**
  (`least_squares.py:2424-2430`, deferred since WP-0406). So partial pooling
  or a smoothness penalty over the axis needs that refusal lifted first.
- **Reusable bases:** `background/models.py` has `bspline_design_matrix`,
  `chebyshev_design_matrix` and `second_difference_matrix`, all 1-D. n-D
  polynomial terms are a few lines over numpy.

### Use cases carried here

- **The outside lab (2026-10-13, by email).** It runs rietx and TOPAS side by
  side on combinatorial libraries. For gradual, broad, interfering peaks it
  refines **polynomial surfaces** over the library in TOPAS, calling it "the
  only way" to get consistent, smoothly evolving models across a library and
  to decouple the measured quantities from how the diffuse features are
  modelled. Its targets include weak and broad features in `instrument.*`
  (background, `extra_components`), so a tie reaches `hist.{h}.` paths. The
  same email names spherical-harmonics texture as their other gap; that is
  WP-1960 (PR #966), not this.
- **Issue #212's conserved elemental ratio** is a parametric constraint in
  disguise: linear in the phase scales and constant across the axis. Its
  restraint row is [1942](1942-a-soft-restraint-on-a-sum-across-phases.md),
  which holds the seam, the workaround and #349's exports.
- **Named variables exist** ([1119](1119-named-variables.md)).
  `Refinement.add_variable` gives `vars.<name>`, which `parameters()` lists,
  `set_vary("vars.*")` frees, a fit refines with an esd and
  `RefinementState.variables` persists. `Refinement.tie` takes
  `{path: coefficient}`. They are single-pattern only today
  (`refine.py:1980-1992`).
- **The ordered moment through T_N** ([1329](1329-moment-in-a-series.md)),
  m ∝ (1 − T/T_N)^β, is nonlinear in β and T_N, so it is fenced. If the
  measurement says the joint form pays, the moment trajectory is a further
  series to measure it on.

## Non-goals

- A library of physical models: the caller supplies the basis, or names a
  polynomial.
- Replacing the chain: it stays the exploratory tool and the seed.
- Nonlinear functions of the coordinates (fenced with `Parameter.expr`,
  WP-1119).
- One pattern as a sum over several specimens (A ≠ identity): direct XRD-CT,
  depth profiles. That is [1962](1962-xrd-ct-a-pattern-summed-over-the-voxels-its-beam-crosses.md).
- Soft forms: partial pooling toward the surface, or a P-spline smoothness
  penalty over a coordinate. Both need the joint path's restraint refusal
  lifted, and both make the esds conditional on a penalty weight. They are a
  follow-up WP if the hard form proves too stiff across a library.
- Sliding-window marginalisation for unbounded campaigns.

## Tasks

- [ ] **The measurement, synthetic first.**
  - A synthetic ramp of 10 patterns with a known a(T): the trajectory-line
    coefficient and esd against a joint a₀ + a₁·T fit, plus the wall-clock
    ratio against the chain. It runs on today's dense joint path.
  - Then the real ZrMo₂O₈ ramp (maintainer-local) for the same two numbers on
    real data. If the coefficients agree within an esd and the joint esd is
    not smaller, say so: the series use case then rests on convenience, and
    the library case on the outside lab's report.
- [x] **Survey the prior art for declaring a parametric model**, for a
  self-driving lab as the writer. Written into Context: § Prior art, § The
  shape and § What the code has.
- [ ] **The declaration**: the coordinate table, the closed basis vocabulary,
  the subset, the reference and scale, with JSON round-trip, and every
  refusal of § The shape item 3 before any solve.
- [ ] **Per-pattern starting values in a joint fit**: a `Structure` per
  histogram, or per-pattern overrides, in place of the deep copy at
  `params/multi.py:187`.
- [ ] **Ties and variables reach the joint table**: a `vars.` coefficient
  shared, per-table ties onto `hist.{h}.` targets, and
  `_unsupported_paths_multi` reading `column_reach` per the WP-1342 rule
  before any variable drives a per-histogram cell. Bit-identical to
  `refine_multi` when the basis is `constant`.
- [ ] **Scalable solver, the step.** A block-structured joint Jacobian (per
  histogram: its rows against its own columns, plus its rows against the
  shared columns), never assembled dense. Two routes to decide between by
  measurement:
  - (i) the existing projected CG (`lm.py:731-733`) fed a block operator for
    A·v, which already handles bounds;
  - (ii) Schur elimination of each histogram's private block, which is exact
    only while no bound in it is active (WP-1125).

  Equivalence bar against the dense path at N ≤ 20: the step to WP-1125's
  6.6e-7 relative with no bound active, and the converged answer within
  0.01 esd.
- [ ] **Scalable solver, the covariance.** The shared coefficients'
  covariance from the reduced (Schur) matrix, equilibrated first. Each
  histogram's own esds from its diagonal block of the full inverse,
  Σ_LL = H_LL⁻¹ + H_LL⁻¹·H_LG·S⁻¹·H_GL·H_LL⁻¹. Unmeasured rows marked through
  each table's reach (WP-1110 item 14's rule).
- [ ] **Scaling measured**: memory and wall clock at N = 10, 70, 300 on a
  synthetic library, dense against blocked. State where dense stops being
  possible on the measuring machine.
- [ ] esds of the coefficients in user units at the reference, marked
  unmeasured where no pattern in the subset contributes gradient.
- [ ] `SeriesResult.summary(deliverable="series")` prints the coefficients
  beside the trajectory it already prints. A joint-fit summary prints them
  for a library.
- [ ] Manual Part 1 `using/series.md` (series and library); Part 2 the
  equation with its *Source* line; the skill's series reference.
- [ ] Tests: a synthetic ramp with a known a(T) (a₁ within one esd of truth,
  and the esd no larger than the trajectory-line's); a synthetic library
  with a known 2-D surface over ≥ 100 patterns, through the blocked solver.
  obs/calc/diff PNGs to `tests/output/`.
- [ ] Skill: the series reference's routing row for "a parameter as a
  function of composition or temperature across patterns", or "none" and why.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_sequential.py tests/test_multi_histogram.py tests/test_parametric_series.py
.venv/bin/python -m ruff check src tests examples
```

## References

- Stinton, G. W. & Evans, J. S. O. (2007). *J. Appl. Cryst.* 40, 87-95 —
  parametric Rietveld refinement.
- Müller, M., Dinnebier, R. E. & Schorr, S. (2011). *Z. Kristallogr.* 226,
  doi:10.1524/zkri.2011.1407 — parameterized Rietveld refinement of the
  CuInSe₂ transition.
- Hastie, T. & Tibshirani, R. (1993). *J. R. Stat. Soc. B* 55, 757-796 —
  varying-coefficient models.
- Wilkinson, G. N. & Rogers, C. E. (1973). *Appl. Stat.* 22, 392-399 —
  symbolic description of factorial models.
- van Stokkum, I. H. M., Larsen, D. S. & van Grondelle, R. (2004). *Biochim.
  Biophys. Acta* 1657, 82-104 — global and target analysis.
- Kamasak, M. E., Bouman, C. A., Morris, E. D. & Sauer, K. (2005). *IEEE
  Trans. Med. Imaging* 24, 636-650 — direct reconstruction of kinetic
  parameter images from dynamic PET data.
- Triggs, B., McLauchlan, P. F., Hartley, R. I. & Fitzgibbon, A. W. (2000).
  *Vision Algorithms: Theory and Practice*, LNCS 1883, 298-372 — bundle
  adjustment.
- Suram, S. K. et al. (2017). *ACS Comb. Sci.* 19, 37-46 — AgileFD.
- Kusne, A. G. et al. (2020). *Nat. Commun.* 11, 5966 — CAMEO.
- WP-0308 (the joint residual), WP-0505 / WP-1051 / WP-1127 (the chain),
  WP-1305 (the series deliverable), WP-1119 (named variables), WP-1125 (the
  Schur identity), issue #212.

## Handover log

- **2026-10-13 (reconstructed post hoc)** — two planning commits landed on
  `main` this morning without a handover entry, and the session-start hook
  flagged the WP for repair. Neither one changed code or measured anything.
  Together they say this WP's first outside user wants a 2-D surface across a
  combinatorial library rather than a 1-D line through a ramp. They also say
  the declaration has to be designed for an automated writer (a self-driving
  lab) before it is built.
  - `a9a577e` added the 2026-10-13 `### Inherited` entry from the outside
    lab's email: the axis is a vector, there are many specimens, targets
    include `hist.{h}.` paths, and the priority claim is disputed.
  - `b23bb9a` added the prior-art survey task (second in Tasks) with its five
    design questions.
  - The diff does not say which session wrote them or why they were not
    handed over. Both touch only this file.

  Next: the survey task, then the measurement.
- **2026-09-01** — created as a candidate during the roadmap reorder; carries
  a use case and a seam, no measurement. First task is the measurement.

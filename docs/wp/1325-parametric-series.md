# WP-1325 — parametric series: a parameter as a function of each pattern's coordinates

Milestone: unscheduled · Status: 🔄 2026-10-14 — claimed by @yue-here (Claude session); scope decided, synthetic measurement landed, a kernel over the coordinates surveyed; the regime a single pattern cannot see is next
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

### Measured: the synthetic ramp (2026-10-14)

`1325-measure/synthetic_ramp.py`, output in `1325-measure/results.txt`.

**Setup.**
- Ten LaB₆ patterns at T = 300-1200 K, built by `tests/test_sequential.py`'s
  `_simulate` with the cell on a known line.
- 20 noise seeds per regime.
- Linux x86_64, 4 CPUs, `[dev]` venv, compiled kernels on, nothing else
  running.
- The joint fit is today's dense path, with no `src/` change. The pieces:
  - `SharingMap(per_histogram=["phases.*"])`;
  - `vars.a0`/`vars.a1` added to every sub-table, which fold onto one shared
    column each;
  - `phases.0.cell.a` tied per table to a0 + a1·t_h;
  - `_rebuild_columns()` called by hand;
  - `mccusker_default` with `vars.*` added to its cell stage.
- `MultiParameterTable.set_vary` skips tied entries
  (`params/multi.py:281`), so the tie survives every stage. The script
  asserts a, b and c sit on the line to 1e-12 in every table.

**Results.** a₁ is in 10⁻⁹ Å/K; truth 20 783. "Scatter" is a₁'s spread over
the 20 seeds.

| regime | estimator | bias | scatter | mean esd |
|---|---|---|---|---|
| R1, strong signal, only a0/a1 shared | weighted line through the chain | −0.45 | 4.45 | 5.48 |
| | joint a0 + a1·t | −0.46 | 4.41 | 5.48 |
| R2, phase scale ×0.035 (per-pattern cell esd ×4.95) | weighted line | −2.45 | 17.9 | 27.1 |
| | joint | −2.67 | 17.95 | 27.1 |
| R3, instrument (zero, profile) shared in the joint fit | weighted line | −0.45 | 4.45 | 5.48 |
| | joint | +0.10 | 1.57 | 2.13 |
| | control: shared instrument, cells free, GLS line over their joint covariance | +0.10 | 1.57 | 2.12 |

**What it says.**
- **The tie is correct.** In R1 and R2 the joint a₁ sits a mean 0.024 and
  0.021 esd from the weighted line (max 0.074). The esd ratio is 0.983-1.011.
  Theory says that when only the coefficients are shared, the joint estimate
  is the line weighted by each pattern's *raw* information, and it is. That
  line is not the chain's weighted line, whose weights also carry each
  pattern's own χ²_red and Bérar-Lelann factor; across this ramp the raw
  information is near-equal, so the reference is the equal-weight line. The
  joint a₁ sits a mean 0.0012 esd from it in R1 (max 0.0037, the printed
  resolution) and 0.0048 in R2 (max 0.018), 20× and 4× closer than to the
  weighted line (computed from the per-seed rows of `results.txt`).
- **The tie alone buys no precision while each pattern's own fit is linear.**
  Weakening the signal 5× in esd (R2) kept every per-pattern fit Gaussian and
  unbiased, so the constraint had nothing to fix.
- **Sharing buys precision, the tie does not.** Sharing the instrument across
  the ramp (R3) cuts a₁'s esd 2.6× (ratio 0.381-0.392) and its scatter 2.8×.
  The untied control gets the same answer to within 0.001 esd: a joint fit of
  per-pattern cells already has that gain. a(T_ref) does not sharpen
  (1.57e-6 Å in R1 and R3 alike, for every estimator), because a common shift
  of every cell still trades off against the zero shift.
- So, on this evidence, the parametric form's value for a series is:
  - **convenience:** a coefficient with its esd, without exporting the joint
    covariance, which a joint result does not carry today;
  - **fewer columns:** one per coefficient instead of one per pattern;
  - **what remains untested:** whatever happens where a single pattern
    cannot see the parameter (the second measurement task).

  The library case rests on the outside lab's report until that measurement
  says otherwise.
- **Cost.** Joint ÷ chain wall clock is 1.41-2.19 (R1), 1.66-2.11 (R2) and
  1.44-2.36 (R3) at N = 10. The chain is 1.3-1.9 s and the joint fit
  2.2-3.2 s.
- **Calibration, in passing.** Scatter/esd is 0.81 (R1), 0.66 (R2) and 0.74
  (R3). In R1 and R3 that is about 1/BL, where BL is the Bérar-Lelann factor
  the package multiplies into every esd (1.263 here), so the raw esds are
  near honest. The weighted line's χ²_red (mean 0.56) agrees. R2 does not fit
  that reading: its factor is 1.137, so its raw esds still overstate the
  scatter by about 1.3× (0.66 × 1.137 = 0.75). Why the factor is 1.26 on a
  model that matches its Poisson data exactly, and why R2's raw esds run
  wide, are open, and not this WP's question.
- **Gaps the script had to work around.** These belong to the "ties and
  variables" task:
  - no public verb to add a joint variable or tie, hence the hand call to
    `_rebuild_columns`;
  - a joint result carries no covariance, so the control subclassed
    `_build_result` (`multi.py:1406`) to read it.

### A kernel over the coordinates (survey, 2026-10-14)

The maintainer asked whether a *kernel* over the pattern coordinates, rather
than a declared basis, would be useful. A kernel makes a parameter vary
smoothly without naming its functional form. This section is three
literature searches plus the algebra that places a kernel in this WP. The
searches confirmed each citation and its abstract-level claim through indexed
records, but every full-text fetch failed on DNS, so no paper was read
whole. Numbers that came only from secondary summaries are left out.

**The form.** Each pattern keeps its own p_k, and a prior over the
coordinates pulls the values together: p = Φc + g, with g a Gaussian process
of covariance K_ij = s²·r(|z_i − z_j|/ℓ). In least squares the prior is extra
residual rows R(p − Φc), with RᵀR = K⁻¹. Φc is left unpenalised, so the
kernel penalises only departures from the declared basis. This is Wahba's
(1978) partially improper prior, framed by her as a guard against the
basis's model error. One family holds every form this WP names:
- s → 0 is the hard tie, the form this WP scopes;
- s → ∞ is independent per-pattern fits, the chain's answer;
- ℓ → 0 (a white kernel) is partial pooling toward Φc, the mixed-effects
  soft form in Non-goals;
- a second-difference precision is the P-spline over a coordinate in
  Non-goals. It is an intrinsic GMRF whose null space is the straight line
  (Eilers & Marx 1996; Rue & Held 2005, ch. 3).

So both soft forms in Non-goals are members of one family. The hard tie and
the chain are its two limits, and both make regression tests for an
implementation.

**What it can buy, read against § Measured.** Profiling out a pattern's
private parameters (the Schur step) leaves a quadratic in p_k. Its curvature
I_k is exactly the information that pattern's own fit reports. So when
nuisances are private and each fit is linear, a joint fit under a kernel
**is** GP regression on the trajectory (z_k, p̂_k) with noise I_k⁻¹. This is
the theorem R1 and R2 measured for the line, which is the s → 0 member. In
that regime a kernel buys nothing that a smoother run afterwards on the
chain's output does not.

On a lattice parameter it is pure cost. A pattern's own cell esd in R1 is
4.98e-6 Å (1.2 ppm), against a 2.1e-3 Å step between neighbouring patterns.
Any kernel that admits the observed trajectory therefore leaves each value's
data share at ≈ 1.

Where it might pay is the regime the next measurement task already targets,
where one pattern's likelihood is not Gaussian in p:
- **Weakly determined parameters**: Biso, occupancy, microstrain, and a
  minor phase's cell near its detection limit. Pinning a weak phase's cell to
  its neighbours removes the noise a free cell lets its scale fit. So the
  payoff may be the *phase fraction* more than the cell (hypothesis,
  unmeasured).
- **Overlap that changes along the axis.** Patterns where two phases' peaks
  are resolved inform the patterns where they are not, with no declared
  form.
- **Prediction at an unmeasured coordinate**, for a self-driving lab
  choosing its next sample. A polynomial's esd is conditional on its form
  being right (Brynjarsdóttir & O'Hagan 2014). A GP's variance carries the
  form's uncertainty too.
- **A seed for a library.** Points in (x, y) have no chain order. Kriging
  from already-fitted neighbours seeds the next pattern without one.

Measured precedent agrees on the regime:
- **Dynamic PET.** Fitting kinetic parameters straight to the raw data beats
  frame-then-fit most at low counts, and the two converge at high counts
  (Kamasak et al. 2005; reviewed by Reader & Verhaeghe 2014).
- **MRI.** Parameter maps fitted to raw k-space keep their accuracy at 5-10×
  undersampling (Sumpf et al. 2011).

The mechanism in both is pooling where each measurement is weak.

**Three uses, by how much they touch the answer.**

| use | changes a converged answer? | needs |
|---|---|---|
| seed: krige a pattern's start from fitted neighbours | no | nothing new; a 2-D/3-D chain warm start |
| afterwards: GP regression on (z_k, p̂_k, I_k⁻¹) | no; it reads the answers | each pattern's information, or the joint covariance where nuisances are shared (R3's control) |
| prior inside the joint fit | yes, outside the linear regime | prior rows in the joint residual (refused today, `least_squares.py:2424`), hyperparameters, a prior-share report |

A kernel can also be used as a **basis**: p = K(z, u)·α with M centres u.
This is Wang & Qi's (2015) PET kernel method, or an inducing-point basis. It
is a `design` Φ, so it is already in the declaration and needs no new
machinery. With M = N and no penalty it is a reparametrisation and
constrains nothing. The PET method's gain rests on stopping EM early, which a
converged LM does not do. With M ≪ N it is just a smoother hard basis.

**Costs and hazards.**
- **Transitions.** A stationary kernel smears a jump, and its esds hide the
  smear. Bayesian intervals cover only on average along the curve, and fail
  at kinks (Wahba 1983; Nychka 1988). That collides with the chain's rule that
  a step is "reported, never smoothed" (`_discontinuity_steps`,
  `sequential.py:2377`).

  Every field that smooths over coordinates segments first:
  - SAGE fits one GP per phase region (Kusne, McDannald & DeCost 2024);
  - SARA uses the GP to *locate* boundaries (Ament et al. 2021);
  - EBSD and hyperspectral maps use edge-preserving total variation
    (Athavale et al. 2023; Iordache et al. 2012);
  - ANDiE's data preferred a first-order law to the continuous one its run
    assumed (McDannald et al. 2022).

  So a kernel is declared, never a default, and its subset is a phase field
  (§ The shape item 1 already carries the subset). In difference or Markov
  form, a declared break is one deleted prior row.
- **Hyperparameters.** Only s²/ℓ^{2ν} can be estimated consistently
  (Zhang 2004). Estimate it by REML on the reduced problem (p̂, I), never
  inside the nonlinear fit, or fix ℓ from physics. Quote the answer again at
  ℓ×½ and ℓ×2. GCV can undersmooth badly and REML is steadier (Wood 2011).
  Over 500 000 synthetic DEER traces, AIC and GCV chose the strength better
  than the L-curve (Edwards & Stoll 2018).
- **What an esd means.** With the prior rows in, (JᵀJ)⁻¹ is a posterior
  covariance conditional on the hyperparameters. It leaves out the smoothing
  bias, so its intervals undercover (Kuusela & Panaretos 2015, in unfolding).
  That is a confident wrong singleton in a new form. A kernel fit therefore
  reports, per pattern:
  - the data share h_k = diag[(I + K⁻¹)⁻¹·I];
  - the independent esd beside the posterior esd;
  - tr(H) as the trajectory's effective degrees of freedom (Hodges &
    Sargent 2001).

  A value whose data share is small belongs to the prior and is marked so.
  That is WP-1110's rule (no esd rather than a small one) and WP-1301's (a
  value that is not a measurement is the caller's), applied to a prior. Prior
  rows take no χ²_red or Bérar-Lelann factor and stay out of the observation
  count, as restraint rows already do.
- **The absent-phase hold.** A prior gives a flat direction curvature, so the
  WP-1301 hold and a kernel disagree about a phase the data cannot see. The
  hold freezes it; the prior pins it to its neighbours. That has to be
  decided before the joint path admits prior rows.
- **Identifiability beside Φ.** A GP beside a parametric mean confounds c
  with the discrepancy unless c is *defined* (Kennedy & O'Hagan 2001;
  Brynjarsdóttir & O'Hagan 2014). Either definition fixes it: the GLS
  projection (Tuo & Wu 2015), or Φ as the kernel's null space. The hard tie's
  esd on c is overconfident whenever Φ is wrong.

**Computation: a kernel keeps the solver's structure.**
- Order the unknowns as [private blocks | p | c]. The prior touches only p,
  so the kernelised parameters join the Schur *border*.
- Eliminating each pattern's private block leaves I + K⁻¹ over (p, c): GP
  regression with each pattern's profiled information as its noise.
- The arrow survives, with a border of N·d_p + n_c columns, where d_p is the
  number of kernelised parameters per pattern. The scalable solver's route
  (ii) carries a kernel with no new structure.

How the border scales:
- **Dense K** is affordable up to N·d_p ≈ 3 000 (a Cholesky of order 10¹⁰
  flops, seconds per iteration).
- **1-D.** A half-integer Matérn kernel is a linear SDE (Hartikainen &
  Särkkä 2010). Prior rows Q^{-½}(x_{k+1} − A·x_k) then couple neighbours
  only, so the border is block-tridiagonal and the solve is O(N). At ν = 3/2
  the state carries dp/dz, a thermal-expansion coefficient with an esd.
- **Scattered 2-D/3-D (a library).** Vecchia or NNGP rows, each with m + 1
  nonzeros (Datta et al. 2016; Katzfuss & Guinness 2021).
- **A grid (a tomography slice).** The SPDE square root (Lindgren, Rue &
  Lindström 2011).
- **Partial pooling needs no dense K.** A latent mean in the border and
  per-pattern rows (p_k − μ)/τ suffice (Henderson 1976 writes the precision
  directly). Model the precision, never the covariance.

**The chain is half a smoother.** The iterated extended Kalman smoother is
Gauss-Newton on the joint problem (Bell 1994).
- The warm-start chain is a forward pass with no prior precision.
- A forward *filter* would add a `ValueRestraint` (`schemas/structure.py:550`)
  toward each predicted value, which a single-pattern fit already accepts.
- `direction="both"` runs both passes and *compares* them
  (`SEQUENTIAL_PATH_DEPENDENT`). A two-filter smoother (Fraser & Potter 1969)
  would *combine* them.

In 1-D that is a route to a kernel prior with no joint solver. But iterated
to convergence it is the joint fit by another name, and a forward filter
alone makes the answer depend on direction by construction.

**Precedent in diffraction.** No published Rietveld refinement puts a kernel
prior across patterns. The diffraction work does one of three things:
- smooths per-pattern values afterwards: GSAS-II's equations on its
  sequential table; CAMEO and SAGE on phase labels and properties;
  CrystalShift, which fits each pattern alone (Chang et al. 2025);
- ties hard (Stinton & Evans 2007; Wragg et al. 2015);
- fits jointly with no prior between voxels (DLSR, Vamvakeros et al. 2020).

The one place a kernel prior sits inside a fit to raw diffraction data is
**GP strain tomography** (Jidling et al. 2018; Hendriks et al. 2019;
Henningsson & Hendriks 2021):
- the strain field is a GP whose covariance satisfies equilibrium;
- it is fitted per grain to raw Bragg-edge and 3DXRD projections, with
  hyperparameters estimated from the data;
- it beat both the algebraic inversion and an earlier hand-weighted
  smoothing penalty on reconstruction error.

Outside diffraction, two precedents have the same structure:
- **geostatistical inversion** (Kitanidis 1995): a GP prior, a nonlinear
  forward model, and structural parameters by maximum likelihood.
  Gauss-Newton failed under strong nonlinearity and LM fixed it (Nowak &
  Cirpka 2004);
- **integrated plasma-profile analysis** (Kwak et al. 2020): GP priors fitted
  jointly to raw Thomson-scattering data.

Where a kernel over measurement coordinates has paid most is in choosing
*what to measure*:
- CAMEO, about 10× fewer experiments (Kusne et al. 2020);
- gpCAM, roughly half the measuring time in ILL tests (Noack et al. 2021);
- ANDiE, about 5× fewer temperature steps, with a parametric rather than a
  kernel model (McDannald et al. 2022).

**Reading.**
- **The kernel is the general soft form.** The hard tie and the independent
  fit are its limits, and it leaves the solver's structure unchanged.
- **Where each fit is linear it buys nothing** beyond a smoother run
  afterwards. That is the same regime where § Measured found the hard tie
  buys nothing. Any in-fit value lies where the next measurement already
  looks.
- **Two uses are cheap and change no fitted answer**: seeding a library that
  has no chain order, and smoothing afterwards with prediction at unmeasured
  coordinates.
- **Using it inside the fit has three costs**: a hyperparameter, a posterior
  esd that undercovers at a transition, and a decision against the WP-1301
  hold. It is measured against the hard tie before it is built.

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
  [1960](1960-spherical-harmonics-texture.md), not this.
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
  follow-up WP if the hard form proves too stiff across a library. Both are
  members of one kernel family (§ A kernel over the coordinates), so such a
  WP would build the kernel, not either one alone.
- Sliding-window marginalisation for unbounded campaigns.

## Tasks

- [x] **The measurement, synthetic half.** A ramp of 10 patterns with a known
  a(T): the trajectory-line coefficient and esd against a joint a₀ + a₁·T fit,
  plus the wall-clock ratio against the chain, on today's dense joint path.
  Landed as `1325-measure/synthetic_ramp.py`; the numbers are in
  § Measured.
- [ ] **The measurement, where a single pattern cannot see the parameter.**
  § Measured shows the tie buys nothing while every pattern's own fit is
  linear. Push the synthetic ramp until it is not:
  - a minor phase whose per-pattern scale falls under the 3σ hold
    (WP-1301), so the trajectory has gaps;
  - overlapping or broad peaks, the outside lab's case.

  Report the joint a₁ and its scatter across seeds against whatever line the
  surviving trajectory points allow.

  *Proposed 2026-10-14, not yet agreed* (§ A kernel over the coordinates):
  - add two arms beside the hard tie: a GP fitted afterwards on the
    trajectory, and a joint fit with kernel prior rows (the script appends
    them, as it already subclasses the joint path);
  - add a truth that is not a line, one curved and one with a kink, so the
    hard tie's form error and the kernel's smoothing bias both show;
  - report the weak phase's *fraction* as well as its cell.
- [ ] **The measurement on real data**: the ZrMo₂O₈ ramp (maintainer-local),
  with the same numbers as the synthetic half.
- [x] **Survey the prior art for declaring a parametric model**, for a
  self-driving lab as the writer. Written into Context: § Prior art, § The
  shape and § What the code has.
- [x] **Survey a kernel over the pattern coordinates** (the maintainer's
  question): precedent across fields, its place in this WP's family of
  forms, what it can buy, its costs, and how it scales. Written into Context
  as § A kernel over the coordinates.
- [x] **The declaration**: the coordinate table, the closed basis vocabulary,
  the subset, the reference and scale, with JSON round-trip, and every
  refusal of § The shape item 3 before any solve. Landed as
  `schemas/parametric.py` (`CoordinateTable`, `ParametricTie`,
  `ParametricCoefficient`) and `params/parametric.py` (`resolve_parametric`,
  the one authority). Coefficients are unbounded in this cut, so the box
  refusal became `PARAMETRIC_OUT_OF_RANGE` after the fit.
- [x] **Per-pattern starting values in a joint fit**: a `Structure` per
  histogram, or per-pattern overrides, in place of the deep copy at
  `params/multi.py:187`. Landed as `structure: Structure | list[Structure]`;
  a list must agree on topology and on every shared value.
- [x] **Ties and variables reach the joint table**: a `vars.` coefficient
  shared, per-table ties onto `hist.{h}.` targets, and
  `_unsupported_paths_multi` reading `column_reach` per the WP-1342 rule
  before any variable drives a per-histogram cell. Bit-identical to
  `refine_multi` when the basis is `constant`. Landed, and bit-identical (θ,
  esds, statistics and y_calc `==`): a coefficient takes its target's column
  slot, box and unit. The release (`_rehold_multi`) reads the reach too.
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
- [x] esds of the coefficients in user units at the reference, marked
  unmeasured where no pattern in the subset contributes gradient. Landed as
  `RefinementResult.parametric` (schema 0.55).
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
- Kernel survey (2026-10-14; each record and abstract confirmed by search,
  no full text read):
  - Wahba, G. (1978). *J. R. Stat. Soc. B* 40, 364-372 — improper priors,
    spline smoothing and model errors.
  - Eilers, P. H. C. & Marx, B. D. (1996). *Stat. Sci.* 11, 89-121 —
    P-splines.
  - Kennedy, M. C. & O'Hagan, A. (2001). *J. R. Stat. Soc. B* 63, 425-464 —
    calibration with model discrepancy.
  - Brynjarsdóttir, J. & O'Hagan, A. (2014). *Inverse Problems* 30, 114007.
  - Tuo, R. & Wu, C. F. J. (2015). *Ann. Stat.* 43, 2331-2352.
  - Zhang, H. (2004). *J. Am. Stat. Assoc.* 99, 250-261 — what infill
    asymptotics can estimate.
  - Wood, S. N. (2011). *J. R. Stat. Soc. B* 73, 3-36 — REML against GCV.
  - Hodges, J. S. & Sargent, D. J. (2001). *Biometrika* 88, 367-379 —
    effective degrees of freedom.
  - Nychka, D. (1988). *J. Am. Stat. Assoc.* 83, 1134-1143 — average
    coverage of Bayesian intervals.
  - Kuusela, M. & Panaretos, V. M. (2015). *Ann. Appl. Stat.* 9, 1671-1705 —
    undercoverage under regularisation.
  - Edwards, T. H. & Stoll, S. (2018). *J. Magn. Reson.* 288, 58-68 —
    choosing the regularisation strength.
  - Bell, B. M. (1994). *SIAM J. Optim.* 4, 626-636 — the iterated Kalman
    smoother as Gauss-Newton.
  - Fraser, D. C. & Potter, J. E. (1969). *IEEE Trans. Autom. Control* 14,
    387-390 — the two-filter smoother.
  - Hartikainen, J. & Särkkä, S. (2010). IEEE MLSP — GP regression as Kalman
    smoothing.
  - Lindgren, F., Rue, H. & Lindström, J. (2011). *J. R. Stat. Soc. B* 73,
    423-498 — the SPDE approach.
  - Datta, A. et al. (2016). *J. Am. Stat. Assoc.* 111, 800-812 — NNGP.
  - Wang, G. & Qi, J. (2015). *IEEE Trans. Med. Imaging* 34, 61-71 — the PET
    kernel method.
  - Reader, A. J. & Verhaeghe, J. (2014). *Phys. Med. Biol.* 59, R371-R418 —
    direct parametric reconstruction.
  - Kitanidis, P. K. (1995). *Water Resour. Res.* 31, 2411-2419 —
    quasi-linear geostatistical inversion.
  - Kwak, S. et al. (2020). *Nucl. Fusion* 60, 046009 — GP priors in
    integrated Thomson-scattering analysis.
  - Hendriks, J. N. et al. (2019). *Strain* 55, e12325; Henningsson, A. &
    Hendriks, J. N. (2021). *J. Appl. Cryst.* 54, 1057-1070 — GP strain
    tomography.
  - Kusne, A. G., McDannald, A. & DeCost, B. (2024). *Digital Discovery* 3,
    2211-2225 — SAGE, one GP per phase region.
  - McDannald, A. et al. (2022). *Appl. Phys. Rev.* 9, 021408 — ANDiE.
- WP-0308 (the joint residual), WP-0505 / WP-1051 / WP-1127 (the chain),
  WP-1305 (the series deliverable), WP-1119 (named variables), WP-1125 (the
  Schur identity), issue #212.

## Handover log

- **2026-10-14** — the parametric fit is scoped, and measured once. The
  maintainer made the combinatorial library a target, which puts a joint
  solver that scales to hundreds of patterns inside this WP. Direct XRD
  tomography went to its own candidate,
  [1962](1962-xrd-ct-a-pattern-summed-over-the-voxels-its-beam-crosses.md),
  and the first measurement ran on synthetic data. On a synthetic heating
  ramp, fitting the cell as a straight line in temperature across all the
  patterns at once gives exactly the slope and error bar that a line through
  the per-pattern fits gives. The only precision gain (2.6× on the slope's
  error bar) came from sharing the instrument's parameters across the
  patterns, and a joint fit without the line constraint gets that too. So far
  the constraint's value is convenience. The case that could show more, a
  parameter one pattern cannot pin down on its own, is untested.

  *Done* (session started 2026-10-13):
  - Claimed with draft PR #968. This morning's two unlogged commits got a
    reconstructed entry, written by hand rather than through a full repair
    run, because both only edited this file.
  - The survey task: Context § Prior art, § The shape (the five questions
    answered) and § What the code has, with file:line pointers. Ticked.
  - The maintainer's three decisions went into § Scope. Tasks were
    restructured to match:
    - the measurement split three ways;
    - the declaration;
    - per-pattern starting values;
    - ties and variables reaching the joint table, with the WP-1342 prefix
      fix;
    - the scalable solver's step, covariance and scaling;
    - the remaining deliverables.
  - Priority went P3 → P2.
  - `### Inherited` pruned on arrival: all four entries were still true and
    were folded into § Use cases and § The shape's refusals; the mailbox is
    empty.
  - Filed 1962 after checking for an owner: a grep of `docs/` and `src/` for
    tomography, XRD-CT and voxel found nothing.
  - The synthetic half of the measurement (a lane), in `1325-measure/`.
    Results and reading are in § Measured. Ticked.
  - `/code-review high --fix` returned 8 findings and 6 were fixed:
    - the joint slope is the line weighted by each pattern's *raw*
      information (here the equal-weight line, 0.0012 esd away), not the
      chain's weighted line (0.024 away);
    - a(T_ref)'s esd is quoted for R1/R3 only;
    - R2's wide raw esds are named as open;
    - the script refuses a missing esd or a malformed argument by name.

    Two were declined. Caching R1's chain for R3 would copy R1's wall clock
    into R3's ratio. Moving the Track line off "not yet on a measurement" is
    the maintainer's call.

  *Measured*:
  - The synthetic ramp: § Measured holds the table. Linux x86_64, 4 CPUs,
    `[dev]` venv, compiled kernels on, nothing else running.
  - Lanes (`session_usage.py lanes`):

    | lane | est | requests | main at dispatch | lane base | re-read | main requests | left in main | main edits after | redo | lane $ | main $ | saved $ |
    |---|---|---|---|---|---|---|---|---|---|---|---|---|
    | measurement | 30 | 62 | 336K | 113K | 0K of 9K | 26 | 40K | 2 | 0 | 3.95 | 2.38 | +0.43 |

    The trial row went to `docs/milestones/process.md`, with fixed 0 where
    the tool printed 1: the two later edits were to this file. Baseline,
    selective policy row: `lane when main > 150K and item >= 20 requests | 2
    | +4%`. Estimate against actual was 2.07×: the lane ran 20 seeds, not 5.
  - Fast suite: not quoted. A local run was stopped at about 10 %, because
    merging `main` mid-run changed two `src/` files under it, and a 4-CPU
    container ran it at that pace. The branch adds no test and touches
    nothing under `src/`, `tests/` or `examples/`, so CI's run on the ready
    PR is the record. `test_docs_consistency.py` (25 passed) and ruff are
    clean on the merged tree.

  *Gotchas*:
  - `MultiHistogramRefinement` builds its joint table once (`multi.py:815`),
    so sub-table edits persist across stages. But a new variable or tie needs
    `_rebuild_columns()` called by hand.
  - `MultiParameterTable.set_vary` skips tied entries
    (`params/multi.py:281`), which is what keeps the tie alive through a
    plan.
  - A joint result carries no covariance. The script subclasses
    `_build_result` (`multi.py:1406`) to read it. This belongs to the "ties
    and variables" task, not forwarded to 1341.
  - The Bérar-Lelann factor is 1.26 on data its model matches exactly, and
    R2's raw esds run about 1.3× wide. No open WP owns esd calibration (1931
    only divides the factor out), so it is recorded in § Measured and not
    filed.
  - Not ported to the skill. "Share the instrument across a ramp" is
    synthetic-only, and sharing a zero or displacement through a heating ramp
    is valid only while the mount does not move. It waits for the real ramp.
  - The outside lab's other request, spherical-harmonics texture, is
    [1960](1960-spherical-harmonics-texture.md). It landed on `main` during
    this handover and already cites the lab, so nothing was forwarded into
    it.
  - This session's local branch `wp1325-parametric-series` pushes to
    `origin/claude/blissful-ptolemy-tb7b7k`, the cloud session's branch. That
    branch is PR #968's head.

  Next, in order:
  1. The measurement where a single pattern cannot see the parameter. Reuse
     `synthetic_ramp.py`, with a minor phase under the per-pattern 3σ hold,
     or broad, overlapping peaks. It decides whether the constraint earns
     anything beyond convenience.
  2. The scalable solver, starting with route (i): per-pattern blocks feeding
     the existing projected CG, which already handles bounds. Measure it
     against dense at N = 10/70/300. It is justified by the sharing result
     whatever item 1 says.
  3. The real ZrMo₂O₈ ramp, when the maintainer supplies it.
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

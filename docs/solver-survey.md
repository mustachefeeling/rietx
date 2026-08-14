# Solver & inference survey — candidate methods from outside crystallography

Status: **survey, not a plan.** Nothing here is committed to a milestone. Written
2026-07-28 during v0.6 scoping, at the user's request, to answer: *are there
minimisation and inference methods from ML / statistics / applied maths that the
powder-diffraction community has not adopted, and what could they actually buy?*

Read with the v0.5 method result in mind — **a change is judged by what it
provably changed, not by Δ Rwp.** For solver work the analogue is: judge by
*basin of attraction* (fraction of perturbed starts reaching the reference
minimum) and by *iterations to a fixed, statistically meaningful tolerance* —
never by the final Rwp, which is the same number at every minimum worth having.
Coelho benchmarks his own solvers exactly this way (400 randomised starts,
sorted final-Rwp distributions), and that is the bar to copy.

---

## 0. The measurement that governs every ceiling

Run before surveying, on the real NIST SRM 660c LaB₆ acceptance fit (full NIST
protocol, 24 stitched scans, converged Rwp = 8.67 %). **Three numbers decide most
of what follows.**

### 0.1 Solver work cannot buy speed — the Jacobian can

| | share of wall clock |
|---|---|
| analytic **Jacobian assembly** (108 calls) | **62.2 %** |
| residual evaluation (117 calls) | 17.7 % |
| everything else — scipy's trust-region solve, stage compiles, statistics, report | 20.0 % |

A *perfect, zero-cost* linear solver therefore caps at **1.25×**, and that is an
over-estimate because "everything else" also contains compile, statistics and
report. **So WP-0601 must be justified by constraints and robustness, never by
speed** — which is what its `## Inherited` section already argues on other
grounds, now with a number. Conversely **WP-0605 (batched peak loop, ≈2.4× on the
Jacobian path) is aimed at the 62 % and is correctly first in the v0.6 queue.**

### 0.2 This problem is *not* sloppy. It is badly scaled — and that turns out not to matter either

Final-stage Jacobian, 5332 × 19:

| | cond(J) | cond(JᵀJ) | decades spanned |
|---|---|---|---|
| as refined | 3.27 × 10⁵ | 1.07 × 10¹¹ | **11.0** |
| **columns normalised to unit norm** | **25.7** | 660 | **2.8** |

Essentially *all* of the apparent ill-conditioning is unit-scaling, not intrinsic
degeneracy. That is a **negative result for the entire sloppy-model programme
here**: this is not a Transtrum hyper-ribbon with a log-uniform eigenvalue
cascade, it is a well-conditioned problem expressed in mixed units. Geodesic
acceleration and MBAM are correspondingly demoted (§2.B1).

### 0.3 …and the indicated fix is measured to do nothing (E2, done)

The obvious inference from 0.2 is that scipy is running with `x_scale=1.0` over
parameters spanning ~8 orders of magnitude, and that Moré's adaptive scaling
should help. **It does not:**

| configuration | nfev | njev | wall | Rwp | a (Å) |
|---|---|---|---|---|---|
| baseline (`x_scale=1.0`) | 117 | 108 | 1.87 s | 0.086613 | 4.1568952 |
| `x_scale='jac'` | 127 | 115 | 1.96 s | 0.086613 | 4.1568953 |
| `tr_solver='lsmr'` | **1018** | 1013 | **15.2 s** | 0.091018 | 4.1568465 |
| both | 176 | 154 | 2.43 s | 0.086723 | 4.1568808 |

`x_scale='jac'` is a **clean null** — 9 % *more* iterations, identical answer to
7 decimal places. And `tr_solver='lsmr'` is actively harmful: 8.7× the
iterations, 8× the wall clock, and it converges to a *different and worse*
answer (Δa = 4.9 × 10⁻⁵ Å ≈ 2σ). Both suspicions are now measured and dead.
scipy's TRF is already doing the right thing; the §2.B conditioning arguments
are theoretically sound and practically inert at this problem size.

**Caveat on all three**: one dataset, and 0.2 is the *final* stage (19 free
parameters). Earlier stages and larger problems (Pawley, multi-histogram) are
unmeasured and could differ — 0.1 in particular should be repeated on a
600-parameter Pawley fit before being treated as general.

---

## 1. Measured here: the misfit landscape (§ own work, reproducible)

Two experiments were run before surveying anything, because the shape of the
objective decides which methods are worth reading about. Synthetic patterns,
Gaussian peaks, exact intensities, no noise — so these are *upper bounds on
niceness*: a real pattern is worse, never better.

### 1.1 The L2 misfit is severely multimodal in exactly the parameters staging exists to protect

Local minima counted along a 1-D scan through the true answer, on 15–120° 2θ at
0.02° steps, FWHM 0.09°:

| scan | sparse cubic (LaB₆-like, 83 refl) | dense orthorhombic (289 refl) |
|---|---|---|
| rigid 2θ shift, ±4° | **60 local minima**, descent basin ±0.45° | **26 local minima**, basin ±0.26° |
| fractional cell error d*a*/*a*, ±25 % | **52 local minima**, basin −2.4/+3.0 % | **59 local minima**, basin −1.1/+1.6 % |

### 1.1b Confirmed on real data — for the cell, and refuted for displacement

Same scan on the converged SRM 660c fit, re-optimising **only** the linear block
(scale + background) at each grid point — i.e. the *profiled* objective, which is
what the nonlinear parameters actually see and what variable projection would
optimise directly (§2.A1). 241 points, 44 s:

| scanned parameter | local minima | monotone descent basin |
|---|---|---|
| cell parameter *a*, ±3 % | **16** | **−0.15 % / +0.70 %** (and still 2 minima within ±0.5 %) |
| specimen displacement, ±0.6 mm | **1** | the whole ±0.6 mm — **unimodal** |

Two corrections to the synthetic picture, and the second one matters:

1. **The real cell basin is narrower and markedly asymmetric** (−0.15 %/+0.70 %)
   than synthetic suggested (−2.4 %/+3.0 %). Synthetic was stated as an upper
   bound on niceness; it was.
2. **Displacement is not multimodal at all** over a physically generous range.
   Its aberration is a cosθ shift that stays well under one peak spacing across
   ±0.6 mm, so it never skips. **The multimodality is specific to parameters that
   *dilate* the d-spacing axis — the cell — not to those that translate it.**
   That kills the "zero/displacement" half of the claim above and sharpens where
   any continuation ladder or shift estimator should be aimed.

So the usable capture range of a cold cell refinement is well under a percent,
and outside it the gradient points at the wrong peak rather than nowhere. This is
the powder analogue of *cycle skipping* in seismic full-waveform inversion, and
it is the reason staged plans and good starting values are load-bearing.

### 1.2 Scale-space broadening (graduated non-convexity) widens that basin 4–12×, and is non-monotone

Broadening **both** observed and calculated patterns — convolving the data with a
Gaussian and inflating the model's profile widths to match — is the standard
continuation trick in FWI and computer vision. Measured basin in fractional cell
error, ±25 % scan:

| broadening FWHM | sparse cubic | dense orthorhombic |
|---|---|---|
| 0.09° (native) | −2.4 / +3.0 % (52 minima) | −1.1 / +1.6 % (59 minima) |
| 1.0° | −3.9 / +4.4 % (13) | −10.3 / +13.5 % (6) |
| 2.0° | −7.0 / +9.1 % (9) | **−14.6 / +13.9 % (3)** |
| 4.0° | **−10.6 / +15.1 % (8)** | −12.3 / +7.5 % (10) |
| 8.0° | −10.6 / +6.4 % (11) | −5.1 / +5.6 % (13) |

Two findings, and the second is the one that matters:

1. **The win is real and large**: ~4× wider capture on the sparse pattern, ~9–12×
   on the dense one, and over a ±6 % scan the 2° case was *unimodal* — one
   minimum, no spurious structure at all.
2. **It reverses.** Past an optimum (≈2° dense, ≈4° sparse) broadening makes
   things *worse* — peaks merge into a featureless hump and the pattern stops
   localising the cell. A naive "smooth a lot, then sharpen" schedule would be a
   regression. Any implementation must *choose* the broadening, and the obvious
   principled choice is to tie it to the mean peak spacing rather than to a
   constant.

### 1.3 An optimal-transport misfit was predicted to win, and did not

Hypothesis (from FWI, where Wasserstein misfits are the standard cycle-skipping
cure): for a pure translation W₂² is exactly the squared shift, hence convex, so
a 1-D Wasserstein misfit — computable in O(n) from cumulative sums, and
differentiable — should convexify the alignment problem outright.

Measured: it helps but loses to plain broadening, and is *inconsistent*. Rigid
shift, sparse pattern: W₂ gives 4 local minima vs L2's 60 (good) but broadened-L2
gives **1**. Cell error, sparse pattern: W₂'s basin (−2.6/+1.0 %) is *narrower*
than L2's (−2.4/+3.0 %). Dense pattern it does win over native L2 (−3.8/+6.0 %
vs −1.1/+1.6 %) but still loses to broadening.

Diagnosis — and this is a **defect in the test, not a refutation of the theory**.
W₂'s convexity theorem assumes the two measures have equal mass and that one is a
transport of the other. Over a *fixed* 15–120° window neither holds: shifting by
4° or dilating the cell by 25 % pushes reflections out of the window at one end
and pulls them in at the other, so mass is created and destroyed and the
normalisation smears that error across the whole quantile function. (Background
was *not* the cause here — the ±25 % scans were run background-free.)

So the honest status is **"naive full-pattern W₂ loses to broadening; a fair test
still owes an edge-corrected implementation"** — window wide enough that the
reflection set is constant, or an unbalanced/partial-OT variant. The theory is
strong enough (for a pure translation W₂² = s² *exactly*, independent of profile
shape, and 1-D W₂ is O(N log N) from cumulative sums and differentiable) that one
more careful attempt is warranted before discarding it. Recorded here so the next
attempt starts from the known failure mode rather than repeating it.

Note also what W₂ can never do: mass normalisation makes it blind to the scale
factor and it has no counting statistics, so it could only ever be a
basin-finding stage handing off to weighted L2 — never a reported statistic.

---

## 2. Candidate methods, assessed

Grouped by what they change. **Speed, robustness and correctness are three
different currencies** and must not be traded in one table — a method that halves
iteration count is worth much less here than one that removes a bias, because
this package's whole thesis is that Rwp is not the product.

### 2.A Structural — change what the optimiser is asked to solve

**A1. Variable projection (separable nonlinear least squares).** Golub & Pereyra
(1973) SIAM JNA 10, 413; Kaufman (1975) BIT 15, 49; Ruhe & Wedin (1980) SIAM Rev
22, 318; O'Leary & Rust (2013) Comput. Optim. Appl. 54, 579.

The residual is *separable*: phase scales, background coefficients and per-hkl
intensities enter linearly, everything else nonlinearly. The field has known this
since Cheary & Coelho 1992 and universally handles it by **alternating** — linear
regression for the linear block, Gauss-Newton for the rest. Ruhe & Wedin is the
comparison paper: alternation converges **linearly**, variable projection
**quadratically**, and VarPro is markedly less sensitive to the nonlinear
parameters' starting values.

Why this codebase is unusually ready for it: the linear block is already isolated
and *named* as such — `forward.py` states "the background is linear in its
parameters" and evaluates it as `coeffs @ bkg_design`, and the Pawley columns are
documented as "exactly linear". More striking, **the projector VarPro needs is
already implemented, as a diagnostic**: `block_projection_r2` /
`background_absorption` in `optimize/statistics.py` project a structural Jacobian
column onto the background column span. The package computes the very operator
that would eliminate the pathology it uses that operator to measure.

**The strongest form of this idea is that VarPro unifies Le Bail and Pawley.**
Today those are two separate modes with two separate defects:

- `lebail_update` is a multiplicative fixed-point *partitioning heuristic* (Le
  Bail 1988). Its fixed point is right when y_obs = y_calc, but off the fixed
  point it is not the conditional least-squares minimiser; the extracted
  intensities are path-dependent (CLAUDE.md says so), they are then treated as
  data, and cell esds computed that way are known to be optimistic.
- Pawley refines the intensities jointly, which is honest but ill-conditioned for
  overlaps, and needs hand-imposed equal-split restraints
  (`PAWLEY_OVERLAP_UNRESOLVED`).

VarPro gives Le Bail's *small* nonlinear problem with Pawley's *correct*
statistics: I*(θ) is the exact conditional solution rather than a partition; the
Golub-Pereyra derivative accounts for dI*/dθ, so cell esds stop being optimistic;
and for exactly-overlapping reflections the minimum-norm pseudoinverse solution
**is** the equal split — the restraint is derived instead of imposed. The
dimensional win is largest exactly where the field feels pain: Coelho's own
motivating Pawley problem is 550 parameters of which 530 are intensities; under
VarPro that is a ~20-parameter nonlinear problem.

Two sharper statements of the same benefit, worth keeping because they are the
ones that will convince a referee:

- **The VarPro Jacobian is exactly (I − P_B)·J** — the structural columns with
  their background-imitable component removed. `background_absorption` reports
  the size of that component as a *correctness hazard*. VarPro does not measure
  the hazard, it deletes it.
- **The VarPro normal matrix is the Schur complement** of the full one, so
  structural esds emerge already *marginalised* over the background rather than
  conditional on it. That is the statistically correct number, and the current
  formulation has to recover it the hard way.

Caveats, stated honestly: positivity on scales/intensities makes the inner solve
a bounded (NNLS-type) problem and the projector derivative on an active set is
subtler; the P-spline penalty rows make the inner solve a *ridge* regression
(fine — still linear, still composes with `rows.py`); Kaufman's cheaper
approximate derivative usually suffices; and VarPro's advantage over alternation
shrinks as the linear block shrinks, so a plain 2-phase Rietveld fit with a
handful of background terms will benefit far less than a Pawley fit.

**A2. Scale-space continuation / graduated non-convexity.** Blake & Zisserman
(1987); Bunks et al. (1995) *Geophysics* 60, 1457 (multiscale FWI); Yang et al.
(2020) IEEE RA-L. **Measured in §1.2: 4–12× wider capture range, non-monotone in
the broadening.** `strategy/staged.py` is already a hand-built homotopy; this
would make the first stage principled rather than heuristic, and it is the single
cheapest robustness win identified here. The frozen-per-stage discreteness
invariant already provides the recompile-between-stages mechanism.

Two sharp distinctions that decide whether this is worth anything:

- **This is not the folk remedy.** "Start with large U/V/W" broadens *calc only* —
  a change to the **model**, which distorts relative peak amplitudes and
  contaminates the very width parameters being refined. The multiscale method
  convolves *both* `y_obs` and `y_calc` with the same kernel — a change to the
  **misfit**, leaving the model untouched, and it is the version with a
  basin-widening argument behind it. §1.2 measured the latter.
- **A smoothed stage can never report a statistic.** Convolving the residual makes
  it serially correlated by construction, so χ², esds and Bérar-Lelann are all
  meaningless inside the ladder. The ladder must terminate at kernel = identity
  before any number is quoted. Implementation is a fixed banded matrix `S` built
  at stage compile: residual rows become `S·r`, Jacobian `S·J`.

### 2.B Solver mechanics — same problem, better steps

**B1. Geodesic acceleration, exactly.** Transtrum, Machta & Sethna (2010) PRL
104, 060201; (2011) PRE 83, 036701. Adds a second-order correction from one
directional second derivative of the residual along the proposed step. Everyone
else computes it by finite difference; **with jax it is a nested JVP, so this
package could compute it exactly** — a capability v0.4 bought and has not spent.
Cost is one extra JVP per iteration, no extra Jacobian.

**Demoted by §0.2.** The sloppy-model framing predicts a JᵀJ spectrum spanning
many decades *log-uniformly* after scaling. Measured here: 11.0 decades raw but
only **2.8 after unit-normalising the columns**, with no cascade. This is a
well-conditioned problem in bad units, not a hyper-ribbon — so geodesic
acceleration has little curvature to exploit and MBAM (Transtrum & Qiu 2014, PRL
113, 098701) has no near-boundary directions to find. Keep the *idea* that
`report/layer1.py`'s scale-normalised Gram is the right object for identifiability
questions; drop the expectation of a solver win. Worth re-measuring on a Pawley
or multi-histogram problem before closing the door entirely.

**B2. Do *not* adopt normal equations — a caution for WP-0601.** The driver today
is scipy TRF, which works on **J**. A TOPAS-style Gauss-Newton forms **JᵀJ** and
squares the condition number; WP-0403's invariant already half-knows this. LSQR /
LSMR (Paige & Saunders 1982; Fong & Saunders 2011) exist precisely so one never
forms the normal equations, and scipy exposes them via `tr_solver='lsmr'`. On
numerical foundations the current path is the better one. **WP-0601's value is
the bounds handling, not the solve** — which is what its `## Inherited` section
now says, but it is worth repeating where the survey can see it.

**B3. Scaling — measured, and it is a null (§0.3).** The argument was good:
scipy runs with `x_scale=1.0` over parameters spanning ~8 orders of magnitude,
and `x_scale='jac'` is Moré's adaptive scaling, the same idea as Marquardt's 1963
improvement over Levenberg that Coelho 2018 opens with. **Measured: 9 % more
iterations, byte-identical answer.** `tr_solver='lsmr'` is worse still — 8.7×
the iterations and a different, worse minimum. Recorded as a dead end so it is
not re-proposed; scipy's bounds-aware TRF scaling already covers this.

**B4. Reuse the Jacobian.** Whether this matters is decided entirely by the
profiling in E1. If analytic Jacobian assembly dominates residual evaluation,
then Broyden-style rank-one updates between iterations, or simply *caching the
columns that cannot change*, is the lever. Note the background columns are
**exactly constant within a stage** — `bkg_design` is frozen at compile, so
∂y/∂c_i is literally a stored row. Any recomputation of those columns per
iteration is pure waste.

**B5. A statistically meaningful convergence criterion.** The driver stops on
`ftol` with `xtol=gtol=1e-12`; the field stops on "ΔRwp < 0.001". Both are
arbitrary. The natural criterion for a package whose product is *parameters with
uncertainties* is to stop when every step is small **relative to that parameter's
own esd** — |Δθᵢ| < ε·σᵢ. That is scale-free, prevents both premature stopping on
stiff directions and wasted iterations chasing sloppy ones, and makes solver
comparisons fair. Coelho 2018 notes himself that loose termination criteria bias
solver benchmarks; this fixes that at the root.

**B6. Cone constraints, which BCCG cannot do.** The Stephens positivity
constraint σ²(M) = T·θ ≥ 0 is a *linear inequality in the free parameters*, so a
Gauss-Newton step subject to it is a **QP** — active-set, or ADMM (Boyd et al.
2011) for a few hundred variables. The ADP positive-definiteness constraint is
the **PSD cone**, whose projection is eigenvalue clipping, giving a
projected/proximal Gauss-Newton step. Both cones the package currently *guards*
are enforceable with textbook convex optimisation. This is the concrete answer to
the gap recorded in WP-0601: published BCCG constrains parameters to boxes and
explicitly cannot express either of these.

**B7. Anderson acceleration for the Le Bail iteration.** Anderson (1965); Walker
& Ni (2011) SIAM JNA 49, 1715 — the same trick as DIIS/Pulay mixing in
electronic-structure SCF. `lebail_update` is a Picard iteration converging
linearly; Anderson accelerates exactly that shape from a short iterate history at
negligible cost. Honest caveat: **A1 subsumes this** (VarPro removes the
iteration rather than accelerating it), so B7 is the cheap interim, not the
destination.

**B9. A cycle-skip-immune shift estimator (do this before any of the ladders).**
Adapted from adaptive waveform inversion (Warner & Guasch 2016, *Geophysics* 81,
R429), whose insight is that a matched *filter*'s lag varies smoothly and
monotonically with model error even when the waveforms themselves are
cycle-skipped. Powder version: cross-correlate observed against calculated in a
handful of 2θ windows, extract lag(2θ), and **regress it onto the known shift
basis** — constant (zero error), cosθ (specimen displacement), sin2θ
(transparency), and the d-spacing term (cell error). That gives a *linear*,
multimodality-immune estimate of exactly the four parameters §1.1 shows are the
multimodal ones, with no nonlinear optimisation at all.

Two reasons this ranks high despite being unglamorous: it is an excellent
initialiser *and* it is precisely the "say what actually moved" diagnostic this
codebase is built around — a user gets told "your zero is −0.02°, your
displacement is −0.011 mm" as a *measurement*, not as a refined parameter with an
esd that hides a false minimum. Caveat: the shift basis functions {1, cosθ,
sin2θ} are near-parallel over a narrow 2θ range, so the regression must report
its own conditioning — which is the same non-separability gate Layer 1 applies.

**B8. Predictor-corrector continuation for series.** `sequential.py` warm-starts
each pattern from the last, worth "≈3× in iterations". Numerical continuation
does better: extrapolate along the tangent dθ/dT (implicit function theorem,
available from the same J already factorised) instead of copying the previous
point. Bonus: the tangent *is* the parameter's sensitivity to the series
variable, which is scientifically interesting output, not just a warm start.

### 2.C Statistics & inference — where the field is weakest

**C1. HAC / sandwich covariance instead of a scalar inflation — the single
highest-value item in this survey.** Bérar & Lelann (1991) inflates every esd by
one factor derived from residual serial correlation (`berar_lelann_factor`). The
general solution is the sandwich with a HAC middle (Newey & West 1987, *Ecta* 55,
703): cov = D⁻¹ V D⁻¹ with bread D = JᵀWJ and meat V = JᵀW Σ_true W J.

**The argument that kills every scalar correction.** The inflation in direction
u is ratio(u) = (uᵀD⁻¹VD⁻¹u)/(uᵀD⁻¹u). In the Fourier domain, if the residual
has power spectrum S(f) and a parameter's Jacobian column concentrates its energy
near f₀, then ratio ≈ S(f₀)/S_white. Peak-shape misspecification is **spectrally
concentrated at the peak frequencies**. So:

- a scale factor or low-order background coefficient (slowly varying Jacobian
  column) sees only the *low-frequency* misfit power;
- a **cell parameter or profile width** — whose Jacobian column is a sharp
  dipole at every peak — sees the misfit power *exactly where imperfect peak
  shape puts it*, and is inflated the most.

χ²_red, Bérar-Lelann, and any Gibbs-posterior "learning rate" all apply **one
number to every direction**. The true inflation varies by direction by a factor
that is itself the physics of the misspecification. That is the case for a
matrix-valued fix, and it is falsifiable: compute both on the shipped standards
and publish the ratio.

**Two free inputs the field already has.** For AR(1) residuals of lag-1
correlation ρ the exact inflation is √((1+ρ)/(1−ρ)); and Durbin-Watson
d ≈ 2(1−ρ), so ρ ≈ 1 − d/2. **Hill & Flack (1987), J. Appl. Cryst. 20, 356
already established DW as a Rietveld diagnostic**, explicitly for "assessing
parameter variance reliability". Typical Rietveld d ≈ 0.3–1.2 ⇒ ρ ≈ 0.4–0.85 ⇒
inflation **1.6–3.5×**, *on top of* √χ²_red. The field reports the input to the
correct calculation and then does not do the calculation.

**Recommended estimator: batch means, not a kernel.** With whitened residual
gᵢ = √wᵢ·rᵢ, whitened Jacobian rows aᵢ, and score contributions sᵢ = aᵢgᵢ, split
the pattern into B blocks of length ≳ a few FWHM and form V̂ = (1/B)Σ_b u_bu_bᵀ
with u_b the block sums. O(Np + Bp²) — one matmul. Trivially positive
semi-definite, and needs no bandwidth theory because **the correlation length is
physical (the peak width), not a nuisance to be estimated.** Report
inflation_j = √((D⁻¹V̂D⁻¹)_jj / (χ²_red·D⁻¹_jj)) — precisely a "what did this
change" diagnostic that moves no Rwp at all.

**Standing caveat that must reach the FitReport wording**: the sandwich corrects
*width*, around the pseudo-true value. It does not correct *bias*. If an
imperfect peak shape biases the cell, the sandwich gives an honest interval
around the biased number.

**C2. Profile likelihood instead of Wald intervals.** Venzon & Moolgavkar (1988);
Bates & Watts (1988). For µt, occupancies, ADPs near the positive-definite
boundary and Stephens coefficients on the cone, the quadratic approximation is
simply wrong and can return intervals spanning physically forbidden values.
Profile likelihood gives correct asymmetric intervals — squarely in service of
"the FitReport must never return a confident wrong singleton." Cost is real (a
sub-refinement per parameter per bound) but it is an opt-in audit, not a default.

**C3. The weights are biased at low counts.** Poisson esds from *observed* counts
(`readers.py`, "STD: counts only, Poisson esd") is the standard choice and the
standard bias: weighting by observed rather than expected counts systematically
pulls fitted intensities low, because upward fluctuations get downweighted. X-ray
astronomy abandoned this for the Cash (1979) statistic / Poisson deviance for
exactly this reason. Powder patterns have genuinely low-count regions — weak
peaks of minor phases, which is precisely what QPA of a trace phase depends on.
The deviance still gives a Gauss-Newton form, so this is a weighting change, not
an architecture change.

**C4. Effective degrees of freedom, and choosing the background smoothing —
substantially revised after the sweeps, including one reversal.**

*(a) The field has never done this, and says so in print.* Toby (2006), *Powder
Diffr.* 21, 67 — the standard reference on Rietveld R-factors — states verbatim
that the DOF correction is deliberately ignored: "for powder diffraction, the
number of data points had better be sufficiently larger than the number of varied
parameters such that the subtraction of the latter can be safely ignored." No
notion of *effective* DOF appears anywhere in the crystallographic canon; a
literature search for penalised-spline backgrounds in diffraction returns **zero
papers**. GSAS-II's source computes `GOF = sqrt(chisq/(Nobs + RestraintTerms −
len(varyList)))` — a raw count, with **restraints counted as extra
observations**, so adding restraints *improves* GOF. FullProf uses `(n−p)`
likewise. The one "effective" idea in the field (Altomare et al. 1995; McCusker
et al. 1999 §9) corrects the *observation* count for peak overlap, never the
parameter count for flexibility.

*(b) The exactly correct denominator, and its true magnitude.* For a linear
smoother H, E[RSS] = ‖(I−H)μ‖² + σ²·tr[(I−H)ᵀ(I−H)], so the reduced-χ²
denominator is **N − tr(2H − HᵀH)**, *not* N − tr(H) and not N − tr(HᵀH). Since
tr(2H−H²) ≥ tr(H), using tr(H) makes χ²_red **optimistically low**. Cost is nil:
one p×p Cholesky and one product on the JᵀWJ already formed. **But the honest
magnitude is small** — at N = 10⁴–10⁵ with tr(H) ~10–100 the χ²_red difference is
O(10⁻³–10⁻⁴) relative, i.e. *negligible for goodness-of-fit and decisive only for
information criteria*, where the absolute df enters linearly.

*(c) The reversal: GCV is actively dangerous here, and REML is the safer default
— but for the opposite reason to the one usually given.* Wahba (1985), *Ann.
Statist.* 13, 1378 proves GML/REML **undersmooths** relative to GCV when the truth
is smooth, with a slower MSE rate; REML's real advantage is *variance* and fewer
local minima (Wood, Pya & Säfken 2016). What decides it for this package is
different and worse: **GCV's leave-one-out logic breaks under correlated errors,
and it gets worse with n, not better** — neighbouring points are informative
about the *noise*, so the criterion is rewarded for interpolating it and drives
λ → 0. That is exactly the "background eats the physical model's misfit"
pathology the project already guards against; GCV would drive the fit *into* it.
(Key reference to obtain and read before implementing: Opsomer, Wang & Yang 2001,
*Statist. Sci.* 16, 134, on nonparametric regression with correlated errors; and
Krivobokova & Kauermann 2007, *JASA* 102, 1328, on REML's robustness to a
misspecified correlation structure.)

*(d) A second reversal — naive AIC with effective DOF is biased toward
complexity, not simplicity.* My draft assumed effective DOF would stop an inert
addition being blessed. Greven & Kneib (2010), *Biometrika* 97, 773 show the
opposite: plugging in an *estimated* smoothing parameter makes conditional AIC
"select any random effect not predicted to be exactly zero", and Wood et al.'s
simulation measures it choosing the over-complex model **>70 % of the time**.
(Marginal AIC is the one biased toward simplicity.) The fix is Wood, Pya &
Säfken's correction `AIC = −2l + 2tr(ÎV′_β)` with V′_β carrying the
smoothing-parameter uncertainty — O(Mp³) with M = 1, essentially free. **Any ΔBIC
this package reports on a penalised fit needs this, or it will systematically
favour keeping the flexible background** — arriving at the project's existing
background invariant from a second direction.

*(e) Where the method already exists, one field over.* Small-angle scattering
solved this in *J. Appl. Cryst.*: Hansen (2000) puts a posterior on the
regularisation hyperparameter so "no choice of hyperparameters has to be made";
Vestergaard & Hansen (2006) define the **effective number of parameters**
N_g = Σλᵢ/(λᵢ+α) determined from the data; and **Larsen & Pedersen (2021)** use
N_g to set the correct reduced-χ² target when fitting models. That last is
almost exactly the deliverable here, published on scattering data in the same
journal, with a working implementation (BayesApp).

*(f) A design trap in this repo specifically.* `model/rows.py` carries
background-penalty rows in the residual vector. Following GSAS-II's convention
(restraint rows counted as observations) would make a *stiffer* background look
statistically better — the exact inverse of the intended correction. Whatever is
done must be a deliberate, documented choice rather than an inherited one.

*(g) And none of it substitutes for the diagnostic already shipped.* Every λ
criterion optimises a predictive risk, and a background that absorbs the physical
model's misfit *improves* predictive risk. No smoothing criterion can distinguish
"the background is right" from "the background is covering for the peak-shape
model". That is a structural identifiability question — which
`background_absorption`'s block-projection R² already answers correctly, and
which, on the evidence of the sweep, **appears to be the first quantification of
background-flexibility bias in the diffraction literature.** McCusker et al.
(1999) §7 asserts the mechanism qualitatively ("scale, occupancy and thermal
parameters … more sensitive to the background correction than … positional
parameters") and the FullProf manual warns that too little background smoothing
gives "wrong estimation of structural parameters" — both without a single
number.

**C5. Gradient-based posteriors — and a correction to my own first draft.** I
initially proposed collapsed HMC/NUTS on the jax model as the way to get
"correct" uncertainties. **That is wrong under misspecification, and the
literature is unambiguous about it.**

Kleijn & van der Vaart (2012), *EJS* 6, 354, prove the Bernstein-von Mises
theorem under misspecification: the posterior concentrates as
N(θ̂, V⁻¹/n) where V is the **KL-Hessian — the *bread***, while the estimator's
actual sampling variability is the **sandwich** D⁻¹VD⁻¹. Their own words: credible
sets "are in general not 1−α-confidence sets … may over- or under-cover … **to
extreme amounts**." The two coincide **iff the model is correctly specified.**

The uncomfortable corollary for this package: **plain MCMC over the Rietveld
likelihood would be *worse* than what rietx does today**, because current
practice multiplies by √χ²_red and a straight posterior does not. At
χ²_red = 2–10, naive credible intervals come out **1.4–3.2× too narrow before
serial correlation is even counted.**

The fix is cheap and post-hoc. Müller (2013), *Econometrica* 81, 1805, shows
naive posteriors give **inadmissible** decisions about pseudo-true values and
proposes the artificial *sandwich posterior*; Shaby (2014), *JCGS* 23, 853, gives
the implementation as an affine map on existing draws —
θ_OFS = θ̂ + Ω(θ − θ̂) with Ω = Q⁻¹P^{1/2}Q^{1/2} — his "open-faced sandwich",
about ten lines. Note Shaby's own warning that his moment estimator of the meat
needs *independent replicates*, which one diffraction pattern does not provide;
so the meat must come from the block/HAC estimator of C1 anyway.

**Net effect: C5 collapses into C1.** If you build the sandwich you get the
honest widths without sampling at all; if you later ship MCMC, the same matrix
post-corrects the draws. Sampling remains useful as a *shape* diagnostic (does
the scale/Biso/absorption degeneracy show up as a ridge? does capillary µR show
up as an *unbounded* one, as it provably must?) — not as the uncertainty source.

**C5b. Gibbs posteriors / calibrated learning rates — considered, rejected.**
Bissiri, Holmes & Walker (2016); Lyddon, Holmes & Walker (2019); Grünwald & van
Ommen (2017). The learning rate w is calibrated from a *trace* of exactly the
same H and J matrices the full sandwich uses — so it needs identical inputs and
throws away the direction information that C1 shows is the entire content. A
scalar η is Bérar-Lelann with better manners. Lyddon et al. concede in print that
setting w "remains an open problem", and their loss-likelihood bootstrap
reweights *iid* observations, which would destroy the very serial correlation
being measured. Grünwald's SafeBayes is worth citing as a caution (Bayes can be
*inconsistent*, not merely overconfident, under misspecification) but its
pathology — heavy prior mass on bad models — does not resemble a tight,
physically constrained Rietveld family.

**C5c. A Kennedy-O'Hagan discrepancy GP — actively harmful here, do not.**
Brynjarsdóttir & O'Hagan (2014) show a flexible additive discrepancy destroys
identifiability of the physical parameters unless its prior is genuinely
informative. A GP discrepancy over 2θ is a *strictly more flexible* version of
the flexible background this package already refines under a penalty — it would
be near-perfectly confounded with the P-spline **and** with the profile
parameters, and would bias exactly the quantities (ADPs, scales, QPA fractions)
the existing invariant flags, while improving Rwp. Record as considered-and-
rejected with that citation. The one configuration where a discrepancy term
could be identified is multiple responses sharing parameters (Arendt, Apley &
Chen 2012) — i.e. `multi.py` or a sequential series.

**C6. Leave-a-peak-out cross-validation for background absorption.** The existing
`background_absorption` R² measures the *geometry* of the problem. A decisive
behavioural test: mask a peak region, refit, predict the masked region. A
background that is absorbing signal will predict it well; an honest one will not.
Cheap, and it turns a diagnostic number into a falsifiable claim.

**C7. Robust loss — but asymmetric, and the asymmetry is the whole content.**
The obvious move (`scipy`'s `loss='soft_l1'`, one argument) is a **trap**. In a
diffraction pattern the largest residuals sit at *peak tops*, which are the most
information-rich channels; a symmetric robust loss silently downweights exactly
the data determining scale, width and ADPs, and "improves" the fit by biasing
them. FWI and astronomy get away with symmetric robust losses because their
outliers are isolated; here they are not. The correct version uses the physics:
an **unmodelled impurity phase can only produce y_obs > y_calc, never the
reverse**, so downweight positive residuals and hold negative ones at full
weight. That is the same asymmetric-weighting idea `background/estimators.py`
already relies on (AsLS/arPLS), promoted from the background estimator to the
refinement residual. Free consequence: the converged asymmetric weights **are**
an impurity map, so excluded regions come from a stated rule instead of by eye.

**C8. Boundary-parameter tests are invalid, and the package already has the
evidence.** Protassov, van Dyk, Connors, Kashyap & Siemiginowska (2002) ApJ 571,
545: likelihood-ratio and F tests do not follow their nominal distributions when
the tested parameter lies on the *boundary* of the allowed space. That is
precisely "is this minor phase present?" (weight fraction ≥ 0) and "is this
impurity peak real?" — decided today by Δχ² or ΔRwp, which is exactly the invalid
test they name. WP-0503 already measured a symptom of this (Hamilton's F test at
α = 0.05 blessed an inert 3-parameter addition just as it blessed a real one).
The fix is a reference distribution calibrated by simulation, which is cheap here
because the forward model is fast — and it converts a known-bad test into a
correct one rather than replacing it with a different arbitrary threshold.

**C9. Non-negative sparse deconvolution for Layer 0's unindexed peaks.** Instead
of thresholding a smoothed residual, solve an NNLS fit of the residual against a
dictionary of instrument-profile-shaped peaks on a fine 2θ grid. Non-negativity
*alone* delivers sparse recovery for well-separated positive sources — no L1
penalty, no tuning constant (Donoho, Johnstone, Hoch & Stern 1992; Slawski & Hein
2013). Output is a peak list with amplitudes, using the profile the refinement
already knows. (The full line-spectral machinery — ESPRIT/Prony/atomic norm — is
*not* recommended: it assumes exact Lorentzians, and powder violates that badly
through θ-dependent widths and FCJ axial asymmetry.)

**C10. The background prior should come from the instrument, not only from the
data.** C4 proposes REML/GCV, which is data-driven. Model-discrepancy theory
(Kennedy & O'Hagan 2001; Brynjarsdóttir & O'Hagan 2014) proves that is *not
sufficient*: a flexible additive discrepancy destroys identifiability of the
physical parameters unless its prior is genuinely informative, and the remedy is
a better-justified **prior**, not a better fit statistic. This is the theory of
which the package's background invariant is an instance — and it supplies the
missing half, because for a diffractometer you actually know the answer: **the
background must not be able to vary on the scale of a peak width.** That is a
physics-derived rule for `lambda_smooth`/breakpoint spacing, and it should be
tested *against* REML rather than replaced by it.

**C11. Localising *where* the model is wrong — and one structural fact that makes
this easier here than in neuroimaging.** Global Rwp/χ² answer a question whose
answer is already known. The mature machinery for "which regions are genuinely
misfit" is the neuroimaging cluster-inference literature, and it transfers with
an important advantage: **in a photon-counting pattern the null is white.** The
serial correlation is a property of the *misspecification signal*, not of the
null, so i.i.d.-based scan and FDR theory is legitimately in reach — and, unlike
fMRI, a **generative null exists**, so the exact null of any statistic is
available by drawing y* ~ Poisson(y_calc) and re-forming the residual. 1000
replicates costs well under a second. (This should be *checked*, not assumed —
Kα2 stripping, rebinning or smoothing would break whiteness.)

Four practical points, in descending order of how easy they are to get wrong:

- **Standardise exactly, or the diagnostic is worthless.** For window weights w
  the statistic is Z = wᵀr / √(wᵀ(I−H)w), and wᵀ(I−H)w = ‖w‖² − ‖Qᵀw‖² with Q
  the thin-QR of the whitened Jacobian `derivative_bases()` already builds.
  Skipping the leverage correction ships a detector that **always flags the
  pattern ends and the strongest peaks**, because those are the high-leverage
  channels.
- **Work in resel space.** Peak width grows with 2θ (size ↔ 1/cosθ, strain ↔
  tanθ), so a fixed window is a matched filter at exactly one angle. Map
  τ = ∫d(2θ)/FWHM(2θ) using the *already fitted* profile; the field becomes
  stationary by construction and the 1-D random-field p-value is two lines:
  P(max Z ≥ t) ≈ Φ(−t) + (L/FWHM)·0.2650·e^(−t²/2) (Worsley et al. 1996).
  Sobering honest note: in 1-D this lands within 0.2σ of plain Bonferroni over
  the resel count, so the sophisticated machinery buys very little over
  "Bonferroni on the effective number of independent peak widths".
- **Prefer peak height to cluster extent.** Eklund, Nichols & Knutsson (2016)
  PNAS 113, 7900 found cluster-extent inference reaching **70 % FWER against a
  nominal 5 %** while peak-height inference stayed conservative — because extent
  depends on the assumed smoothness in a way height does not.
- **FDR at the window level, split by sign.** A rejected *channel* is not a
  finding; one impurity peak produces sixty of them. Test clusters, not channels
  (Benjamini & Heller 2007), and run **two separate one-sided families** — a
  two-sided |Z| family leaves BH's PRDS guarantee and costs the
  Benjamini-Yekutieli factor c(m) ≈ 9.8 at m = 10⁴.

The most attractive output shape is **All-Resolutions Inference** (Rosenblatt et
al. 2018; Goeman et al. 2022): closed testing gives a simultaneous lower bound on
the true discovery proportion for *any* region chosen post hoc, so the report can
say "region 42.8–43.6° contains at least 61 % genuinely misfit channels" rather
than "this cluster is significant". That is exactly the shape of statement the
"never a confident wrong singleton" invariant demands.

### 2.D Considered and rejected

- **Learned / amortised optimisers, neural warm-starts.** No credible evidence at
  20–600 parameters, and enormous machinery. Rejected.
- **Neural surrogates for the forward model.** Incompatible with the fp64
  invariant on its face — the package validates cells to ~10⁻⁸ Å. Rejected
  firmly.
- **Stochastic / minibatch gradient methods.** Sub-sampling channels destroys the
  statistics that are the product, and the problem is far too small to need it.
  Rejected.
- **Simulation-based inference.** The likelihood is available and cheap; SBI
  solves the opposite problem. Rejected.
- **Randomised sketching / sketch-and-solve least squares.** Pays off at
  n_params ≫ 10³. Possibly relevant to very large joint Pawley or
  multi-histogram, irrelevant otherwise. Parked.
- **Optimal-transport misfit.** Predicted to win, measured to lose to plain
  broadening (§1.3) — but the test had a known defect (window truncation), so
  this is *parked pending an edge-corrected retest*, not rejected.
- **Symmetric robust losses** (Huber/Cauchy via `loss=`). Rejected on the
  argument in C7 — they downweight peak tops, which is where the information is.
- **Internal / redundant coordinates** (Pulay & Fogarasi 1992). Seductive and
  mostly wrong here. Internal coordinates win in quantum chemistry because
  Cartesians make a nearly-diagonal *physical* Hessian look dense — the
  transformation reveals structure that is really there. Refinement parameters
  are already "internal", and the strong correlations (scale↔Biso↔absorption,
  zero↔displacement↔cell) are **real physical degeneracies**, not artefacts of a
  bad basis. You cannot orthogonalise away a genuine degeneracy. *One narrow
  piece does transfer*: the shift basis {1, cosθ, sin2θ} is collinear only
  because the 2θ range is finite, which is a true conditioning artefact worth
  orthogonalising over the measured range (reporting back in physical units).
- **GDIIS / RFO / quasi-Newton with model Hessians.** Rejected — these exist
  because quantum-chemistry Hessians are expensive and only gradients are cheap.
  Gauss-Newton supplies JᵀJ analytically and nearly free, which is strictly
  better information than any quasi-Newton update.
- **Plug-and-play / learned denoiser priors.** Rejected — PnP wins where the
  prior is over an image and cannot be written down. Here the only object needing
  a prior is a smooth 1-D background, and the P-spline second-difference penalty
  is not a crude stand-in for the right prior, it *is* the right prior: convex,
  banded, differentiable, and already contributing rows the covariance consumes.
- **ESPRIT / Prony / atomic-norm line-spectral methods.** Rejected in their
  headline form (they assume exact Lorentzians; powder has θ-dependent widths and
  FCJ asymmetry). The non-negativity-only fragment survives as C9.

---

## 3. Experiments

Ordered so that each one's *prerequisite* comes before it. Every entry states a
**kill criterion** — the observation that would end the line of work — because
the failure mode of a survey like this is a list of things that are all "worth
trying" and never falsified.

### E0 (prerequisite). A perturbed-start benchmark harness

Nothing in §2.A/B can be honestly evaluated without it, and no such harness
exists. Build: perturb the starting parameters of an existing acceptance fit by a
controlled amount (log-uniform over a stated range, fixed seed), run N ≈ 100–400
refinements, and report the *distribution* of final cost and the fraction
reaching the reference minimum — Coelho's own methodology. Report iteration count
at a **fixed, stated termination rule** (see E4), because otherwise the benchmark
measures the stopping criterion rather than the solver.

- **Ceiling**: none — it is instrumentation. But it converts every later claim
  from "faster on my example" to a distribution with an error bar.
- **Verification**: the harness itself is verified by reproducing a known result
  — the current solver's failure rate should rise smoothly as the perturbation
  widens, and should collapse near the ±1–3 % cell figure measured in §1.1.
- **Cost**: small. Highest value-per-line item on this page.

### E1 (prerequisite) — **DONE, see §0.1–0.2.** Jacobian assembly is 62 % of wall
clock and the solve is inside a 20 % "everything else"; Amdahl caps solver work
at **1.25×**. Conditioning is 11 decades raw but **2.8 after column scaling**, so
the problem is not sloppy. Outstanding: repeat on a large Pawley / multi-histogram
fit, where both the parameter count and the linear-block fraction are far larger
and the conclusion may invert.

### E2 — **DONE, and a clean null, see §0.3.** `x_scale='jac'` costs 9 % more
iterations for a byte-identical answer; `tr_solver='lsmr'` is 8.7× slower and
lands on a different, worse minimum. Both recorded as dead ends. *This is the
model outcome for a cheap experiment: a standing suspicion removed for an hour's
work.*

### E3. Scale-space continuation (the §1.2 result, on real data)

Add a pre-stage that convolves the observed pattern with a Gaussian and inflates
the model profile widths to match, then shrinks both over 2–4 steps. Tie the
initial broadening to mean peak spacing, **not** a constant (§1.2 is non-monotone
— over-broadening is a regression).

- **Ceiling**: measured 4–12× wider capture in fractional cell error on synthetic
  patterns; on real data the meaningful ceiling is *the current cold-start failure
  rate*, which E0 measures. If cold starts already succeed 99 % of the time from
  realistic indexing output, the ceiling is small and this is not worth shipping.
  That is the key uncertainty.
- **Verification**: E0 harness with cell perturbations swept from 0.5 % to 15 %;
  plot success fraction vs perturbation for with/without continuation. Success is
  "reaches the reference minimum", not "lower Rwp".
- **Falsification**: if the two curves coincide, the real-data landscape is
  benign and §1.1's multimodality is an artefact of noise-free synthetic peaks —
  itself a publishable-grade finding about this package's robustness.
- **Cost**: moderate. Reuses the staged runner; needs no new solver.

### E4. A statistically meaningful termination rule

Replace/augment `ftol` with "stop when |Δθᵢ| < ε·σᵢ for all i".

- **Ceiling**: not speed — *comparability*. Expect iteration counts to move in
  both directions (fewer on sloppy directions, more on stiff ones).
- **Verification**: reproducibility — refine the same pattern from many starts and
  measure the spread of each converged parameter *in units of its own esd*. A
  good rule makes that spread ≪ 1; the current rule's spread is unmeasured.
- **Why early**: E0's iteration-count comparisons are meaningless without it, and
  Coelho 2018 explicitly warns that loose criteria bias solver benchmarks.

### E5. Variable projection, on Pawley first

Pawley/Le Bail is where the linear block is largest and the payoff clearest.
Implement I*(θ) as an exact (ridge-regularised, non-negativity-constrained) inner
solve; start with Kaufman's approximate derivative.

- **Ceiling**: nonlinear dimension from O(n_reflections) to O(20) — on a
  Coelho-scale problem 550 → ~20. Convergence order from linear (alternation) to
  quadratic. But the *most valuable* outcome is not speed: it is that cell esds
  from Le Bail stop being optimistic, and that overlap equal-splitting becomes
  derived (minimum-norm) rather than imposed.
- **Verification**, three separate claims, each independently falsifiable:
  1. *Agreement*: VarPro and joint Pawley reach the same minimum on the same data
     (parameters within σ/10).
  2. *Exactness*: the returned intensities equal the conditional weighted
     least-squares solution to machine precision — and, for a synthetic pattern
     with exactly-overlapped reflections, the equal split falls out without a
     restraint.
  3. *Coverage* (the real prize): simulate many noisy patterns from a known cell,
     refine each by Le Bail and by VarPro, and measure how often the true cell
     lies inside the nominal 68 % interval. The prediction is that Le Bail
     under-covers and VarPro does not.
- **Kill criterion**: if claim 3 shows Le Bail already covers correctly, the
  correctness argument evaporates and VarPro reduces to a speed optimisation to
  be judged against E1's Amdahl bound.
- **Cost**: high — the largest item here. Worth a WP of its own if E0/E1 support it.

### E6. Cone-constrained Gauss-Newton for Stephens strain

Solve the GN step as a QP subject to T·θ ≥ 0 (active-set or ADMM).

- **Ceiling**: binary and specific — turn `STEPHENS_STRAIN_NOT_POSITIVE` from
  the normal outcome of an anisotropic refinement into an exception, making
  refined S_HKL reportable for the first time. There is no percentage to quote;
  the feature either becomes usable or does not.
- **Landed 2026-07-28 (WP-0601)**, as fraction-to-the-boundary truncation plus
  active-set projection on the cone rows rather than a full QP. Measured on
  brucite at the acceptance suite's seed: 0 of 43 reflections outside the cone
  against 12 of 43 unconstrained, Rwp 18.42 % against 17.90 % — the constrained
  fit is the worse one by Rwp and the only admissible one. It holds from every
  start tried. **The kill criterion below then fires**: a four-seed sweep of
  `Stage.strain_seed` (400/800/1600/3000) leaves the coefficients spanning
  ~100 % relative spread under *both* drivers, so the data do not determine
  brucite's S_HKL and the guard was right that they are not quotable. The two
  runs that reach Rwp 0.1782 agree to 1.3 %; the rest agree with nothing. What
  the constraint buys is therefore narrower than this entry assumed and worth
  stating exactly: a bad start now degrades into a worse Rwp instead of a
  confident unphysical answer. Two premises were also corrected — the isotropic
  control never left the cone (the guard's ≤ 0 test was firing on the all-zero
  block), and the unconstrained driver leaves the cone only from the low seeds,
  not always.
- **Verification**: on the two real round-robin patterns already in
  `test_acceptance_stephens.py` — cone satisfied at convergence on every
  reflection, and coefficients stable (within esd) across perturbed starts. The
  isotropic control (corundum) must return coefficients consistent with the
  isotropic limit S = ε²·[M²], which is a strong, independent check.
- **Kill criterion**: if constrained refinement drives coefficients onto the cone
  boundary and they remain start-dependent, the data do not determine them and
  the honest answer is that the guard was right all along — report that.

### E7. Sandwich/HAC covariance vs Bérar-Lelann

- **Ceiling**: correctness only — but with a **sharp, pre-registered directional
  prediction** (from C1's spectral argument, which reverses my first guess):
  parameters whose Jacobian column is a *sharp dipole at every peak* — cell
  constants, profile widths — should be inflated **most**, because peak-shape
  misspecification puts its power exactly at the peak frequencies. Slowly-varying
  columns (scale, low-order background) should be inflated least. A scalar
  Bérar-Lelann must therefore be simultaneously too large for some and too small
  for others. Independent cross-check available for free: from the pattern's
  Durbin-Watson d (Hill & Flack 1987), ρ ≈ 1 − d/2 predicts an AR(1) inflation
  √((1+ρ)/(1−ρ)) ≈ 1.6–3.5× at typical Rietveld d — the sandwich should land in
  that neighbourhood on average while *spreading* around it by parameter class.
- **Verification — the decisive design**: a simulation coverage study with
  *deliberate* misspecification. Generate patterns from a known structure using a
  peak shape slightly different from the fitting model (that is the real source
  of correlated residuals), add Poisson noise, refine N times, and count how often
  the true value lies within the nominal 68 % interval. Correct esds ⇒ 68 %
  coverage. Report coverage per parameter class for (a) raw esds, (b) BL-inflated,
  (c) sandwich/HAC. This is the only way to settle it, and it settles it fully.
- **Cost**: moderate; the simulation harness is reusable for E5.3, E8 and E9.
- **Bonus**: the same study immediately tells you whether BL's *scalar* is even
  the right shape, independent of which estimator replaces it.

### E8. REML/GCV for the background penalty, and effective DOF

- **Ceiling**: removes a hand-set constant (`lambda_smooth = 1.0`) that the
  project's own invariant says is a correctness knob, and unblocks unbiased
  BIC/reduced-χ² for penalised fits.
- **Verification**: (a) on the coverage harness, REML-chosen smoothing should not
  degrade parameter coverage and should reduce the spread of
  `background_absorption` R² across datasets; (b) an inert 3-parameter addition
  must not be blessed once BIC uses effective rather than nominal DOF — the exact
  failure WP-0503 measured with Hamilton's test.

### E9. Poisson deviance vs observed-count weighting

- **Ceiling**: the bias scales as ~1/counts, so ~1 % at 100 counts/channel and
  negligible at 10⁴. It matters specifically for **weak peaks of minor phases**,
  i.e. trace-phase QPA — which the round-robin suites already measure against
  weighed truth, so the test bed exists.
- **Verification**: simulate low-count patterns of a known 2-phase mixture, refine
  both ways, and compare recovered weight fractions to truth. Prediction:
  observed-count weighting biases the minor phase low.
- **Kill criterion**: no measurable bias at the count levels of the shipped
  suites → record the bound and leave the weighting alone.

### E10. Collapsed HMC as an audit instrument

Sample the nonlinear parameters with NUTS on the jax model, marginalising the
linear block analytically (composes with E5).

- **Ceiling**: not speed — this will be far slower than a fit. The product is a
  *reference posterior* against which every cheap uncertainty estimate (raw esds,
  BL, sandwich, profile likelihood) can be scored on one real dataset.
- **Verification**: standard sampler diagnostics (R̂, ESS, divergences) plus the
  physics check — the known scale/Biso/absorption degeneracy must appear as a
  visible ridge, and the capillary-µR case (provably an exact reparameterisation)
  must appear as an *unbounded* ridge. If it does not, the sampler is wrong.
- **Positioning**: an offline instrument and a validation oracle, never a default
  code path.

### E11. The cross-correlation shift estimator (B9) — cheapest robustness item

Cross-correlate obs vs calc in ~10 windows, regress lag(2θ) on {1, cosθ, sin2θ,
d-spacing term}, report the four shift parameters with the regression's own
conditioning.

- **Ceiling**: should recover zero/displacement/cell error over the *whole* range
  where peaks are recognisable — i.e. far outside the ±1–3 % basin of §1.1. If it
  works it largely retires the cold-start problem that E3 attacks by a more
  expensive route.
- **Verification**: on synthetic patterns with *known* injected zero/displacement/
  cell errors, sweep the injected error and plot recovered vs true. The test is
  monotonicity and unbiasedness over a stated range, not precision — precision
  comes from the subsequent refinement.
- **Kill criterion**: if the recovered lag is non-monotone in the injected error
  at realistic overlap densities, the matched-filter analogy has broken and the
  method is out.
- **Cost**: small. Run it before E3, since a cheap linear estimator that lands
  inside the existing basin makes the continuation ladder unnecessary.

### E12. Asymmetric residual weighting as an impurity detector (C7)

- **Ceiling**: converts hand-drawn excluded regions into a stated rule, and gives
  an impurity map as a by-product. Bounded by how often unmodelled impurity is
  actually the problem — the 11-BM NAC dataset (with its CaF₂ impurity) and the
  misfit-injection suite are the natural test beds.
- **Verification**: on the misfit-injection suite, the asymmetric weights must
  localise the injected impurity and the refined parameters must move *toward*
  their known-correct values. A symmetric robust loss run alongside is the
  control, and the prediction is that it degrades ADPs and scale — which would
  simultaneously confirm the C7 argument for asymmetry.

### E13. Leave-a-peak-out cross-validation for background absorption

- **Ceiling**: converts an existing geometric diagnostic into a behavioural test.
  No speed, no new parameters.
- **Verification**: construct a case with a deliberately over-flexible background
  (many spline breakpoints) and one with a correct one; the over-flexible fit
  should predict masked peak regions *better* than it has any right to, and the
  gap between them is the statistic.

---

## 4. What the measurements changed, and what to do next

**Four things in this document were falsified by measurement, three of them my
own claims.** Recording them is the point of the exercise:

1. Optimal transport was predicted to convexify peak alignment. It lost to plain
   broadening (§1.3) — on a test with a known defect, so it is parked, not dead.
2. The problem was assumed sloppy in the Transtrum sense. **It is not** — 11
   decades of cond(JᵀJ) collapse to 2.8 on column scaling (§0.2). Geodesic
   acceleration and MBAM demoted.
3. `x_scale='jac'` was "the cheapest experiment on this page" and the fix that
   §0.2 pointed to. **Measured null** (§0.3); `tr_solver='lsmr'` measurably
   harmful.
4. Effective DOF was assumed to *stop* an inert component being blessed. Greven &
   Kneib show naive conditional AIC with an estimated λ is biased the **other**
   way, selecting the over-complex model >70 % of the time (C4d).

And one claim survived contact with real data in a sharper form: the cell
parameter really is multimodal (16 local minima, capture −0.15 %/+0.70 %) while
**specimen displacement is unimodal over ±0.6 mm** (§1.1b). The pathology belongs
to parameters that *dilate* the d-spacing axis, not those that translate it.

### If only three things happen

1. **E7 — the sandwich/HAC coverage study.** Now clearly the highest-value item,
   and the measurements promoted it: solver work is capped at 1.25× (§0.1), so
   speed is not where the wins are, while C1's spectral argument gives a sharp,
   falsifiable, *directional* prediction that no scalar correction can be right.
   The field already computes the input (Durbin-Watson, since Hill & Flack 1987)
   and has never done the calculation. Either outcome is publishable: Bérar-Lelann
   is vindicated with evidence, or the field's standard esd correction is shown
   to be structurally the wrong shape.
2. **E0 — the perturbed-start harness**, still unbuilt and still the thing that
   makes every robustness claim falsifiable. Now better targeted: aim the
   perturbations at the **cell**, since §1.1b shows displacement does not need
   protecting.
3. **E11 before E3.** Both attack the cell multimodality, but E11 (a linear,
   skip-immune shift estimate from cross-correlation lags) is hours against E3's
   days, and if it lands the start inside the −0.15 %/+0.70 % basin the
   continuation ladder becomes unnecessary.

**E5 (variable projection) remains the largest structural idea** and is now
better motivated than when it was written: §0.1 shows the Jacobian is 62 % of
runtime, and VarPro removes whole columns from it rather than solving with them.
It is still milestone-sized work.

**Do not start with WP-0601's solver.** §0.1 caps it at 1.25× and §0.3 shows the
conditioning arguments are inert at this size; its justification is the Stephens
cone (E6) and bounds handling, exactly as its `## Inherited` section says.
**WP-0605's batched peak loop is aimed at the measured 62 %** and is correctly
first in the v0.6 queue.

**E5 (variable projection) is the largest idea on this page** and the one most
likely to be genuinely novel in the field, but it is a milestone-sized piece of
work and should not start before E0/E1 say what it would buy.

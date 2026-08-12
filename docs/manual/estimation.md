(ch-estimation)=
# Estimation

## Objective and weights

```{math}
:label: est-obj

S(\theta) \;=\; \sum_i w_i \bigl(y_{\mathrm{obs},i}
- y_{\mathrm{calc},i}(\theta)\bigr)^2,
\qquad w_i = 1/\sigma_i^2,
```

*Source:* `anatase.optimize.least_squares`

minimised over the residual rows of {eq}`fm-rows` {cite}`rietveld1969`.
Weights come from the data file's esd column whenever it is present;
Poisson $\sigma = \sqrt{\max(y, 1)}$ is only the fallback for bare counts.

The Jacobian is assembled column-by-column, preferring exact work over
full-model finite differences: linear background columns, analytic
peak-chain columns (everything flowing through per-peak position, width,
mixing and intensity), analytic site-DOF columns for coordinates and
anisotropic ADPs over the frozen operator subsets, analytic axial columns
for the FCJ apertures, and plain forward differences only as a fallback.
Under a differentiable backend the same residual is traced and columns
come from forward-mode autodiff, whose cost scales with the parameter
count {cite}`nocedal2006`; every backend is held to per-column agreement
with the analytic Jacobian.

## Agreement statistics

Defined per Toby {cite}`toby2006`:

```{math}
:label: est-indices

R_{wp} = \sqrt{\frac{\sum w (y_o - y_c)^2}{\sum w y_o^2}}, \qquad
R_{\exp} = \sqrt{\frac{N - P}{\sum w y_o^2}}, \qquad
\chi^2_{\mathrm{red}} = \frac{\sum w (y_o - y_c)^2}{N - P},
```

*Source:* `anatase.optimize.statistics`

with $\mathrm{GoF} = \sqrt{\chi^2_{\mathrm{red}}} = R_{wp}/R_{\exp}$, plus
the background-subtracted $R_{wp}$ variant Toby recommends when the
background carries much of the raw intensity. The Durbin-Watson statistic
on weighted residuals {cite}`hillflack1987` flags serial correlation
($d \approx 2$ ⇒ uncorrelated).

A recurring result across the shipped corrections is that ΔRwp is a poor
judge of physical improvements ({ref}`ch-corrections`, {ref}`ch-method`) —
what these indices measure is agreement, not correctness.

## Esds and the Bérar-Lelann inflation

```{math}
:label: est-cov

\mathrm{Cov} \;=\; \chi^2_{\mathrm{red}} \cdot (J^\top J)^{-1},
\qquad \mathrm{esd}_i = \sqrt{\mathrm{Cov}_{ii}} \cdot
\sqrt{\chi'^2 / \chi^2},
```

*Source:* `anatase.optimize.least_squares.covariance_estimates`

where the second factor is the Bérar-Lelann serial-correlation inflation
{cite}`berar1991`: consecutive same-sign weighted residuals are summed
coherently, $\chi'^2 = \sum_{\mathrm{runs}} (\sum_{i\in\mathrm{run}}
\delta_i)^2 \ge \chi^2$, because serially correlated neighbours do not
carry independent information. The estimator is conservative — even white
residuals land at an expected factor ≈1.51, so treat it as an upper bound
on the serial-correlation esd damage; Andreev's serial-correlations figure
of merit {cite}`andreev1994` removes that bias by carrying the correlation
into the minimised quantity itself — and reported esds *carry* the
inflation. The correlation matrix does **not**: it is the true Pearson
matrix, so a genuinely degenerate pair reports $|\rho| \approx 1$ and the
0.98 high-correlation guard means what it says. Values are quoted with
two-significant-figure su's per the IUCr convention
{cite}`schwarzenbach1989`.

## Staged strategy and series

Parameter groups are freed cumulatively in the IUCr-guideline order
{cite}`mccusker1999` — scale and background first, then peak positions,
then profile widths — with the discrete model state regenerated between
stages and frozen within them. A *series* of related patterns (an in-situ
ramp, a parametric sweep) is chained by warm starts; the result is a
parameter *trajectory*, path-dependent by construction, so the chain can
be run in both directions and parameters the two disagree on are flagged —
the only check separating a measured trajectory from an ordering artefact.
True parametric refinement across patterns {cite}`stinton2007` is out of
scope.

## Solvers

The default driver is scipy's Trust Region Reflective. The bounded
Levenberg-Marquardt alternative implements Coelho's adaptive Marquardt
constant {cite}`coelho2018` over the bound-constrained conjugate-gradient
solve of the normal equations {cite}`coelho2005` (conjugate gradients per
{cite}`hestenes1952,polak1971`), with the system diagonally
pre-conditioned to $A_{ii} = 1$ — which is what makes λ dimensionless and
lets the published constants transfer. Conventions: $A = J^\top J$, $b =
-J^\top r$, and the paper's objective $S = r^\top r$ is $\chi^2$.

The driver earns its place with **constraint vocabulary**, not speed: box
bounds enforced *inside* the linear solve, and linear inequalities on
functionals of θ — rows $T\theta \ge 0$, the shape of the Stephens
positivity cone ({ref}`ch-microstructure`), which no per-parameter box can
express. An answer that pressed the cone says so: per-stage truncation
counts are recorded and a `CONSTRAINT_ACTIVE` diagnostic fires for the
answer-producing stage — the only signal that a declared constraint was
*active*. Speed was measured at 0.74–1.04× against TRF, the expected
result: the normal-equation solve is a minority of the runtime, so solver
work is Amdahl-bounded at ≈1.25× here. Two places where the Coelho papers
disagree with their own text, and how the discrepancies were resolved by
measurement, are worked through in {ref}`ch-method`.

## The fp64 floor

The residual used for cost and statistics, and the parameter solve and
covariance, are always fp64 on host; a GPU backend may compute Jacobian
*columns* in fp32. The asymmetry is not a preference:

- **The residual cancels.** $\sqrt{w}(y_{\mathrm{obs}} - y_{\mathrm{calc}})$
  subtracts numbers of order 10⁵ counts to leave order 10²; fp32's ~7
  digits put an absolute error of order 10 counts — ~10 % of the very
  quantity formed — into everything that reads it.
- **The solve squares the conditioning** {cite}`higham2002`:

```{math}
:label: est-cond

\operatorname{cond}(J^\top J) \;=\; \operatorname{cond}(J)^2,
```

*Source:* `anatase.backend.linalg64`

  so a routine Rietveld $\operatorname{cond}(J) \sim 10^4$ leaves
  $\operatorname{cond}(J^\top J) \sim 10^8$, which fp32 cannot invert at
  all. The bounded LM forms $J^\top J$ explicitly, making it the direct
  illustration.
- **Columns are relative-accuracy tolerant.** A column enters only through
  a descent direction and a curvature estimate; the trust region
  re-measures every step against a fresh fp64 cost. Measured on real
  hardware: an Apple-GPU refinement with every column in fp32 lands
  3.5×10⁻⁸ Å from the numpy fp64 cell.

## From fit to report

The FitReport reads the converged state in three layers. Layer 0 is
model-free: cumulative-χ² breakpoints localise *where* misfit lives
{cite}`david2004`, and unindexed peaks are flagged against the tick
positions of **every** emission line (an impurity must clear
{{ IMPURITY_SIGMA }}σ). Layer 1 attributes per-region misfit to profile
shape derivatives, under four gates (resolvability on the scale-normalised
Gram, a validity radius, local-χ² significance, global maturity) so that a
collinear pair is declared non-separable rather than resolved into a
confident wrong singleton. Layer 2 turns attributions into actions,
testing candidate model extensions with Hamilton's ℛ-ratio test
{cite}`hamilton1965` and ΔBIC {cite}`schwarz1978`; its thresholds are
versioned (currently {{ THRESHOLDS_VERSION }}).

## Which parameter to free next

`Refinement.suggest()` ranks every held-but-refinable parameter by the χ²
reduction one Gauss-Newton solve would obtain from freeing it, at the cost
of a single Jacobian evaluation and no solve. With $F$ the currently-free
columns, $P_F$ the orthogonal projector onto their span, $r$ the weighted
residual and $J_j$ a held parameter's column,

```{math}
:label: est-suggest

\tilde{\jmath} = (I - P_F)\, J_j, \qquad
\tilde{r} = (I - P_F)\, r, \qquad
\Delta\chi^2_j \;=\; \frac{(\tilde{\jmath}^{\top} \tilde{r})^2}
                          {\tilde{\jmath}^{\top} \tilde{\jmath}},
```

*Source:* `anatase.optimize.statistics.one_parameter_gains`

which is Rao's score statistic {cite}`rao1948` applied to the linearised
model, computed through the Frisch-Waugh-Lovell projection identity
{cite}`frisch1933,lovell1963`. It is exactly the drop in $\sum w\Delta^2$
that a least-squares solve of $[F \mid J_j]$ achieves over $F$ alone, it is
invariant under any rescaling of the column (so no per-parameter step
heuristics), and at a converged minimum $J^\top r \approx 0$ makes every
gain vanish. GSAS-II's answer to the same recipe problem {cite}`toby2024`
obtains its ranking by ±δ finite differences with per-type δ heuristics and
a sign-consistency test, because its analytic derivatives are locked inside
Hessian assembly; exact columns at the current state make all three
workarounds unnecessary.

Under the null hypothesis a gain is distributed as
$\chi^2_1 \cdot \chi^2_{\mathrm{red}}$, so a candidate is quotable only
above a noise floor of {{ SUGGEST_MIN_GAIN }} · max(χ²_red, 1) — the 3σ
point of $\chi^2_1$, with the same floor-at-one convention as the
covariance scale. Two gates keep the ranking honest (the Layer-1
discipline one call over): a candidate whose column the free block absorbs
is reported non-separable rather than scored — the same projection also
caps the $1/(1-R^2)$ inflation of near-collinear gains — and candidates
whose projected columns are pairwise indistinguishable come back as one
unresolved *group* carrying a joint gain: a tie, never a winner. As with
indexing there is no `.best`; `best_or_none()` answers `None` whenever the
evidence does not choose one parameter.

(ch-microstructure)=
# Microstructure

## Isotropic size and strain

Sample broadening rides on the instrument profile through the width laws of
{eq}`prof-caglioti-g` and {eq}`prof-caglioti-l`: crystallite-**size**
broadening varies as $1/\cos\theta$ (Scherrer; Lorentzian $X_s$, Gaussian
variance $P/\cos^2\theta$), micro**strain** broadening as $\tan\theta$
(Lorentzian $Y_s$, Gaussian variance $U_s \tan^2\theta$). The instrument ⊕
sample split is a workflow, not just an equation: calibrate $U, V, W, X, Y$
on a line-width standard with its certified cell held fixed, freeze them,
and refine only the sample terms on the specimen.

These laws depend on $hkl$ only through θ. Real strained powders break
that — $(00l)$ and $(hk0)$ can differ threefold at the same $2\theta$.

(sec-width-as-size)=
## Reading a width as a size

A width in degrees is not transferable between instruments; the crystallite
size it implies is. Scherrer's relation {cite}`scherrer1918` reads a single
line's breadth as an apparent size,

```{math}
:label: ms-scherrer

L \;=\; \frac{K\lambda}{\beta\,\cos\theta} \qquad [\text{Å}],
```

*Source:* `rietx.model.profiles.caglioti`

with $\beta$ the FWHM in radians of $2\theta$. $K$ depends on the crystallite
shape **and** on which measure of breadth is used — 0.89 for the FWHM of a
sphere against 1.0747 for its integral breadth {cite}`langford1978` — so an
apparent size is an order-of-magnitude statement, never a quotable two-figure
one. It is also a *lower* bound unless the instrument and strain contributions
have been taken out first: Scherrer attributes every degree it is handed to
size.

Why the size and not the degrees is the transferable number is the same
statement as working in $Q$. With $Q = 4\pi\sin\theta/\lambda$ the local
Jacobian is $dQ/d(2\theta) = 2\pi\cos\theta/\lambda$, and the $\cos\theta$ of
{eq}`ms-scherrer` cancels against it:

```{math}
:label: ms-delta-q

\Delta Q \;=\; \frac{2\pi\cos\theta}{\lambda}\,\beta \;=\; \frac{2\pi K}{L}
\qquad [\text{Å}^{-1}],
```

*Source:* `rietx.model.profiles.caglioti`

independent of both $\lambda$ and $\theta$ — Scherrer broadening is *constant
in Q*. Because the size law of {eq}`prof-caglioti-l` **is** $1/\cos\theta$, the
same cancellation removes the reference angle entirely: a size *coefficient*
maps to one size for the whole pattern,

```{math}
:label: ms-size-coefficient

L \;=\; \frac{180}{\pi}\cdot\frac{K\lambda}{X_s}
\qquad\Longleftrightarrow\qquad
X_s \;=\; \frac{180}{\pi}\cdot\frac{K\lambda}{L},
```

*Source:* `rietx.model.profiles.caglioti`

reading $\sqrt{P}$ in place of $X_s$ for the Gaussian variance coefficient of
{eq}`prof-caglioti-g`. The right-hand form is the seeding direction — a width
from a specimen already known from a micrograph, a synthesis or an earlier
refinement, rather than from a default calibrated on a synchrotron linewidth.

```{warning}
Only the $1/\cos\theta$ coefficients have a size to read. $W$ is constant in
θ and $U$ goes as $\tan^2\theta$, so a number of degrees taken off either is
a number *at one chosen angle*: $U = 1.0\ \deg^2$ alone is 0.268° FWHM at
$2\theta = 30$° and 3.172° at $2\theta = 145$°, a factor of twelve across an
ordinary pattern.

This is what makes a declared bound in degrees hard to transfer. $X$ carries
$\max = 1.0$° — 79.4 Å on Cu Kα against 21.3 Å on 11-BM's 0.4139 Å, one cap
admitting a 3.7× spread in the physics — while the sample terms $X_s$ and $P$
carry $\min = 0$ and no maximum at all. Decide such a limit as a size; report
it in degrees.
```

(sec-width-as-strain)=
## Reading a width as a strain

Microstrain broadens by a fixed *fraction* of every d-spacing rather than by a
fixed reciprocal-space width {cite}`stokes1944`. Differentiating Bragg's law
$\lambda = 2d\sin\theta$ at fixed $\lambda$ gives $\Delta d/d = -\cot\theta\,
\Delta\theta$, so a relative spread in $d$ appears as

```{math}
:label: ms-strain-law

\Delta 2\theta \;=\; 2\,\frac{\Delta d}{d}\,\tan\theta
\qquad [\text{radians}],
```

*Source:* `rietx.model.profiles.caglioti`

which is the $\tan\theta$ term of {eq}`prof-caglioti-l`. Inverting it for the
coefficient $Y_s$ in deg $2\theta$,

```{math}
:label: ms-strain-coefficient

\frac{\Delta d}{d} \;=\; \frac{\pi}{180}\cdot\frac{Y_s}{2}
\qquad\Longleftrightarrow\qquad
Y_s \;=\; \frac{360}{\pi}\cdot\frac{\Delta d}{d},
```

*Source:* `rietx.model.profiles.caglioti`

reading $\sqrt{U_s}$ in place of $Y_s$ for the Gaussian variance coefficient of
{eq}`prof-caglioti-g`, exactly as {eq}`ms-size-coefficient` reads $\sqrt{P}$.

**No wavelength appears in {eq}`ms-strain-coefficient` and no shape constant
either**, and the contrast with {eq}`ms-size-coefficient` is the whole of the
asymmetry: of the six sample-broadening quantities in {eq}`prof-caglioti-g` and
{eq}`prof-caglioti-l` — two sizes, two strains, and the Stephens block of
{eq}`ms-lambda` — exactly the two named "size" depend on $\lambda$. One
specimen measured at two wavelengths therefore shows the *same* number of
degrees of strain broadening and size coefficients in the ratio $\lambda_2 /
\lambda_1$ (their Gaussian variances in the ratio squared). A joint refinement
must share the size, not the coefficient; `rietx.params.multi` normalises it, reporting
the rescaling as the `SIZE_NORMALISED_ACROSS_WAVELENGTHS` diagnostic.

$\Delta d/d$ here is the **FWHM** of the d-spacing distribution, matching what
{eq}`ms-strain-law` relates and what the coefficients of
{eq}`prof-caglioti-g`–{eq}`prof-caglioti-l` are. Other codes publish other
measures of the same width: GSAS-II's `mustrain` is $2\Delta d/d$ in units of
$10^{-6}$, and FullProf's apparent strain is $\tfrac{1}{2}\beta^{*}d$, read off
the integral breadth rather than the FWHM. A microstrain is not comparable
between codes without its convention.

## Stephens anisotropic strain

Stephens' phenomenological model {cite}`stephens1999` lets every
crystallite carry its own lattice metric. With

```{math}
:label: ms-m

M_{hkl} \;\equiv\; \frac{1}{d^2_{hkl}} \;=\;
\mathbf{h}\cdot G^*\cdot \mathbf{h}^\top \quad [\text{Å}^{-2}],
```

the spread of a *quadratic form's* coefficients makes the variance of $M$ a
homogeneous **quartic** in $(h, k, l)$:

```{math}
:label: ms-sigma

\sigma^2(M) \;=\; 10^{-12} \sum_{H+K+L=4} S_{HKL}\; h^H k^K l^L,
```

*Source:* `rietx.crystallography.stephens`

fifteen monomials, hence at most fifteen coefficients. Since $2\theta =
2\arcsin(\lambda\sqrt{M}/2)$ gives $d(2\theta)/dM = \tan\theta / M$, the
contribution in the deg-2θ FWHM units the Lorentzian strain term already
uses is

```{math}
:label: ms-lambda

\Lambda(hkl) \;=\; \frac{180}{\pi}\cdot 10^{-6}\cdot d^2_{hkl}
\cdot \sqrt{\textstyle\sum_{HKL} S_{HKL}\, h^H k^K l^L} \quad [\deg],
```

*Source:* `rietx.crystallography.stephens`

added to the Lorentzian FWHM as $\Lambda(hkl)\cdot\tan\theta$ — the first
width in the model that depends on $hkl$ rather than only on θ.

```{warning}
Three independent labelling conventions sit behind these $S_{HKL}$, and
getting any one wrong rescales every published number. A manual that
reproduced Stephens' equation (1) without them would be worse than none —
a reader would transfer literature values straight in and get a wrong
width law that still refines.

1. $\sqrt{\sum S\cdot\text{monomial}}\cdot d^2\cdot 10^{-6}$ is the
   **FWHM** of the $\Delta M/M = 2\Delta d/d$ distribution, *not* its
   standard deviation — no $\sqrt{8\ln 2}$ appears anywhere.
2. The coefficients are carried in **10⁻¹² Å⁻⁴**, not physical Å⁻⁴ — and
   that is load-bearing numerically, not cosmetic: the shared
   finite-difference step is absolute below 1, so a coefficient at its
   physical ~10⁻⁸ Å⁻⁴ magnitude would be differenced with a step 100× its
   own value.
3. They multiply the **literal monomials** $h^H k^K l^L$. Other codes fold
   symmetry multiplicities into their templates (writing the cubic S₂₂₀
   term as $3(h^2k^2 + h^2l^2 + k^2l^2)$, say), so their printed values
   differ by small integer factors as well. Never transfer a literature
   $S_{HKL}$ without checking numerically.
```

## Symmetry and the allowed coefficients

$\sigma^2(M)$ must be invariant under the Laue group. Miller indices
transform under the reciprocal-space action $\mathbf{h}' =
R^\top\mathbf{h}$, which induces a 15×15 integer action $A(R)$ on the
monomial coefficients; the allowed $S_{HKL}$ span $\bigcap_R \ker(A(R) -
I)$, computed as an exact rational nullspace — the rank-4 twin of the
rank-2 construction used for ADPs {cite}`peterse1966`, sharing the same
kernel. Degree 4 is inversion-even, so no Laue classification is needed.
The derived dimensions reproduce Stephens' Table 1: $m\bar 3m$ 2, $6/mmm$
and $6/m$ 3, $\bar 3m1$ and $\bar 31m$ 4, $\bar 3$ 5, $4/mmm$ 4, $4/m$ 5,
$mmm$ 6, $2/m$ 9, $\bar 1$ 15.

The coefficients refine as **absolute** degrees of freedom on that basis —
a set outside the allowed subspace raises rather than being symmetrised.
A Stephens block **locks the scalar `lor_strain`**: its isotropic direction
is identically that column, so the block subsumes it, and it must be freed
*in* the sample-broadening stage, not after.

## The positivity cone, the seed, and how to read the guard

$\sigma^2(M) \ge 0$ for every $hkl$ is a *cone* coupling all fifteen
coefficients — it cannot be a box bound. Under the default TRF driver it
is a guard (`STEPHENS_STRAIN_NOT_POSITIVE`); under the bounded-LM driver
it is carried as a linear inequality and the guard falls silent because
there is nothing left to report ({ref}`ch-estimation`). Read a firing as
"these coefficients are not quotable", never as evidence *of* anisotropy —
and note that **zero is on the cone, not outside it**: the guard's test is
one-sided, and an earlier ≤ 0 form that flagged the inert all-zero block
produced a since-withdrawn claim about isotropic specimens.

The isotropic limit $S = \varepsilon^2\,[M^2]$ lies exactly in the allowed
subspace for every symmetry and is both the seed and the only legal start:
at $S \equiv 0$ the square root in {eq}`ms-lambda` has unbounded slope, so
strain stages seed through a dedicated mechanism rather than a generic
parameter seed.

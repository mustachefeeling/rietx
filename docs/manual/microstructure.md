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

*Source:* `pxrdref.crystallography.stephens`

fifteen monomials, hence at most fifteen coefficients. Since $2\theta =
2\arcsin(\lambda\sqrt{M}/2)$ gives $d(2\theta)/dM = \tan\theta / M$, the
contribution in the deg-2θ FWHM units the Lorentzian strain term already
uses is

```{math}
:label: ms-lambda

\Lambda(hkl) \;=\; \frac{180}{\pi}\cdot 10^{-6}\cdot d^2_{hkl}
\cdot \sqrt{\textstyle\sum_{HKL} S_{HKL}\, h^H k^K l^L} \quad [\deg],
```

*Source:* `pxrdref.crystallography.stephens`

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

(ch-profiles)=
# Peak profiles

## The instrument ⊕ sample width split

The Gaussian and Lorentzian component widths each carry an instrument part
and a sample part, combined by the physics of convolution: **Gaussian
variances add, Lorentzian FWHMs add.**

```{math}
:label: prof-caglioti-g

\Gamma_G^2(\theta) \;=\; (U + U_s)\tan^2\theta + V\tan\theta + W
+ \frac{P}{\cos^2\theta}
\qquad [\deg^2 2\theta]
```

*Source:* `rietx.model.profiles.caglioti`

$U, V, W$ are the instrument resolution function {cite}`caglioti1958`; the
sample adds a Gaussian microstrain term $U_s\tan^2\theta$ and a Gaussian
size term $P/\cos^2\theta$ {cite}`larson2004,thompson1987`.

```{math}
:label: prof-caglioti-l

\Gamma_L(\theta) \;=\; \frac{X + X_s}{\cos\theta} + (Y + Y_s)\tan\theta
\qquad [\deg 2\theta]
```

*Source:* `rietx.model.profiles.caglioti`

```{warning}
Conventions here are documented by *physics*, not letters: the
$1/\cos\theta$ (and $1/\cos^2\theta$ variance) terms carry Scherrer
crystallite-**size** broadening, the $\tan\theta$ (and $\tan^2\theta$) terms
micro**strain**. The letter assignments differ between codes — GSAS uses
X = size, Y = strain; FullProf swaps them. Transfer values by matching the
$\theta$-law, never the letter.
```

Reading either $1/\cos\theta$ coefficient back as a crystallite size — and why
$U$ and $W$ have no size to read — is {ref}`sec-width-as-size`. Anisotropic
(hkl-dependent) sample broadening is deferred to {ref}`ch-microstructure`.

(sec-strain-cap)=
## How wide a strain term is allowed to get

Nothing in $Y_s\tan\theta$ stops at a physical strain, and an unbounded $Y_s$
is not a slightly wide peak: past some width the phase's lines are flat across
the whole scan, it is degenerate with the background, it starves whatever it
overlaps, and the covariance loses conditioning. Measured on a 248-pattern
in-situ reduction series, $Y_s$ reached $1.1\times10^{5}$ where the reference
protocol for the same data used 0.3.

So $Y_s$ — and $U_s$, which is the same width squared, being a variance —
carries a default upper bound derived from **the pattern itself** rather than
from any material:

```{math}
:label: prof-strain-cap

Y_s \;\le\; \frac{f\,(2\theta_{\max} - 2\theta_{\min})}{\tan\theta_{\max}},
\qquad
U_s \;\le\; \left(\frac{f\,(2\theta_{\max} - 2\theta_{\min})}
{\tan\theta_{\max}}\right)^{\!2},
\qquad f = {{ STRAIN_CAP_RANGE_FRACTION }}
```

*Source:* `rietx.params.vector.strain_cap`

with $2\theta_{\min}, 2\theta_{\max}$ the ends of the **fitted** range —
excluded regions removed, since an excluded interval was not measured. Read
{eq}`prof-strain-cap` as the statement that *a line wider than the interval it
was measured over is not a line*: at $f = 1$ the strain term alone contributes
one whole range's worth of FWHM at the pattern's highest $\theta$. It is
dimensional and self-scaling — a 15–80° lab scan and a 0.5–50° low-angle scan
get different bounds out of one rule, and no calibrated constant enters.

```{warning}
This bounds **numerics, not strain**. It sits two orders of magnitude above
anything a specimen produces (≈ 83 deg on a 10–80° scan), so it is not the
judgement about whether a width is believable. That judgement is the
`STRAIN_UNUSUALLY_LARGE` diagnostic, which fires above
{{ STRAIN_FLAG_WIDTH }} deg — the top of a corpus of 606 solved refinements —
and bounds *nothing*. Nanocrystalline and heavily defective specimens
legitimately refine into that tail, and a flag there is a number to check
rather than a fit to discard.
```

Two properties follow from *where* the bound is applied, which is at the
optimiser interface for one stage and never on the stored parameter:

* it is **armed only on a term that has already reached it**, because a finite
  bound changes the trust-region step in a coordinate even where it is never
  approached — so a fit whose strain stays inside {eq}`prof-strain-cap` gets no
  bound at all and is bit-identical to an unbounded build;
* a **finite stored `max` is the caller's claim and outranks it**, the same rule
  the per-stage cell window follows, so declaring any ceiling — including a
  deliberately enormous one — switches the default off.

Enforcement is therefore per stage, not per iteration: a stage that starts
below the bound may cross it, and the next stage pulls it back and reports
`BOUND_HIT` on the path (`RefinedParameter.at_bound` carries the same finding
on the row).

## Thompson-Cox-Hastings pseudo-Voigt

The default profile approximates the Voigt (Gaussian ⊗ Lorentzian) as a
linear blend with a single FWHM $\Gamma$ and mixing $\eta$
{cite}`thompson1987`:

```{math}
:label: prof-pv

\mathrm{pV}(x) \;=\; \eta\, L(x; \Gamma) + (1 - \eta)\, G(x; \Gamma),
```

```{math}
:label: prof-tch-gamma

\Gamma^5 = \Gamma_G^5 + 2.69269\, \Gamma_G^4 \Gamma_L
+ 2.42843\, \Gamma_G^3 \Gamma_L^2 + 4.47163\, \Gamma_G^2 \Gamma_L^3
+ 0.07842\, \Gamma_G \Gamma_L^4 + \Gamma_L^5,
```

```{math}
:label: prof-tch-eta

\eta = 1.36603\, q - 0.47719\, q^2 + 0.11116\, q^3,
\qquad q = \Gamma_L / \Gamma.
```

*Source:* `rietx.model.profiles.pseudovoigt`

Both component shapes are unit-area normalised, so $\int \mathrm{pV}\,dx =
1$ and the reflection intensity of {eq}`fm-rietveld` enters purely through
the prefactor:

```{math}
:label: prof-components

G(x) = \frac{2}{\Gamma}\sqrt{\frac{\ln 2}{\pi}}
\exp\!\left(-\frac{4 \ln 2\, x^2}{\Gamma^2}\right),
\qquad
L(x) = \frac{2/(\pi\Gamma)}{1 + 4x^2/\Gamma^2}.
```

*Source:* `rietx.model.profiles.pseudovoigt`

## The true Voigt, via the Faddeeva function

An opt-in shape (`Instrument.profile.shape = "voigt"`; TCHZ stays the
default) evaluates the exact convolution {cite}`armstrong1967`:

```{math}
:label: prof-voigt

V(x; \sigma, \gamma) \;=\; \frac{\operatorname{Re}[w(z)]}{\sigma\sqrt{2\pi}},
\qquad z = \frac{x + i\gamma}{\sigma\sqrt{2}},
```

*Source:* `rietx.model.profiles.voigt`

where $\sigma$ is the Gaussian standard deviation and $\gamma$ the
Lorentzian *half*-width at half maximum, recovered from the same component
FWHMs of {eq}`prof-caglioti-g`-{eq}`prof-caglioti-l`:

```{math}
:label: prof-voigt-widths

\sigma = \frac{\Gamma_G}{2\sqrt{2\ln 2}}, \qquad \gamma = \frac{\Gamma_L}{2}.
```

*Source:* `rietx.model.profiles.voigt`

Both limits are exact and recovered branchlessly: $\gamma \to 0$ makes $z$
real and $\operatorname{Re}[w] = e^{-z^2}$ (the unit Gaussian); $\sigma \to
0$ sends $|z| \to \infty$ where $w(z) \to i/(\sqrt{\pi} z)$ (the unit
Lorentzian).

The Faddeeva function $w(z) = e^{-z^2}\operatorname{erfc}(-iz)$
($\operatorname{Im} z \ge 0$) is computed by the Weideman rational
approximation {cite}`weideman1994`: the conformal map of the upper
half-plane onto the unit disc,

```{math}
:label: prof-weideman

Z = \frac{L + iz}{L - iz}, \qquad L = \sqrt[4]{1/2}\cdot\sqrt{N},
\qquad
w(z) = \frac{2\, p(Z)}{(L - iz)^2} + \frac{1/\sqrt{\pi}}{L - iz},
```

*Source:* `rietx.model.profiles.faddeeva`

with $p$ an $N$-term polynomial whose real coefficients come from a single
FFT at import time; $N = 32$ reaches ≈1e-13. The algorithm was chosen for
being **branchless** over the whole upper half-plane — no region partition
(Humlíček's w4 {cite}`humlicek1982`) and no series switching
{cite}`zaghloul2011` — which keeps the residual smooth for
finite-difference and autodiff Jacobians. The Voigt argument always has
$\operatorname{Im} z = \gamma_L/(\sigma\sqrt{2}) \ge 0$, so the reflection
formula for the lower half-plane is never needed. Derivatives reuse the same
$w$ call through the identity $w'(z) = -2z\,w(z) + 2i/\sqrt{\pi}$
{cite}`abramowitz1964`.

## Finger-Cox-Jephcoat axial divergence

With a sample of axial half-length $S$ and a receiving slit of axial
half-length $H$ at goniometer radius $L$, rays leaving the diffraction plane
are detected at an *apparent* angle $2\varphi$ related to the true Bragg
angle by {cite}`finger1994`

```{math}
:label: prof-fcj-apparent

\cos 2\varphi \;=\; \cos 2\theta \cdot \sqrt{1 + \xi^2},
\qquad \xi = u/L,
```

*Source:* `rietx.model.profiles.fcj`

where $u$ is the signed axial offset of the ray. For $2\theta < 90°$
intensity smears from $2\theta$ *down* to $2\varphi_{\min}$ — the classic
low-angle tail of laboratory data; above 90° the smear is toward high angle.
The weight of a given offset is the axial overlap of sample and slit, a
trapezoid in $\xi$ (with $s = S/L$, $h = H/L$):

```{math}
:label: prof-fcj-weight

W(\xi) \;=\; \operatorname{clip}\bigl(s + h - \xi,\; 0,\; 2\min(s, h)\bigr),
\qquad \xi \ge 0.
```

*Source:* `rietx.model.profiles.fcj`

Expressed as a density in $2\varphi$, the aberration diverges like
$1/\sqrt{2\theta - 2\varphi}$ at the Bragg position — the reason naive
sampling fails. Substituting $\xi$ as the integration variable removes the
singularity exactly:

```{math}
:label: prof-fcj-integral

y(2\theta_i) \;=\;
\frac{\int_0^{\xi_{\max}} W(\xi)\, \Omega\bigl(2\theta_i - 2\varphi(\xi)\bigr)\, d\xi}
     {\int_0^{\xi_{\max}} W(\xi)\, d\xi},
\qquad
\xi_{\max} = \min\bigl(s + h,\; |\tan 2\theta|\bigr),
```

*Source:* `rietx.model.profiles.fcj`

with a smooth integrand, evaluated by fixed-node Gauss-Legendre quadrature
in $\tau = \xi/\xi_{\max}$. The $|\tan 2\theta|$ cap removes the unphysical
$\cos 2\varphi > 1$ branch at very low angle, and the weights are
renormalised to $\sum\omega = 1$ so the composite peak keeps exactly unit
area — reflection intensities remain areas. Node *counts* are frozen per
stage ({{ NODES_PER_FWHM }} nodes per FWHM of smear where the map moves
fastest, clamped to [8, 64]); node positions follow $s$, $h$ and $2\theta$
smoothly. When the asymmetric extent is below {{ SKIP_EXTENT_FWHM_RATIO }}
of the peak FWHM the aberration is invisible and the peak is treated as
symmetric.

The quadrature is split at the kink of the trapezoid {eq}`prof-fcj-weight`,
which keeps the response $C^1$ everywhere *except* the inherent FCJ corner
at $s = h$ — a genuine non-differentiability with measured consequences for
refinement when both apertures are equal, worked through in
{ref}`ch-method`.

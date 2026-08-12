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

*Source:* `anatase.model.profiles.caglioti`

$U, V, W$ are the instrument resolution function {cite}`caglioti1958`; the
sample adds a Gaussian microstrain term $U_s\tan^2\theta$ and a Gaussian
size term $P/\cos^2\theta$ {cite}`larson2004,thompson1987`.

```{math}
:label: prof-caglioti-l

\Gamma_L(\theta) \;=\; \frac{X + X_s}{\cos\theta} + (Y + Y_s)\tan\theta
\qquad [\deg 2\theta]
```

*Source:* `anatase.model.profiles.caglioti`

```{warning}
Conventions here are documented by *physics*, not letters: the
$1/\cos\theta$ (and $1/\cos^2\theta$ variance) terms carry Scherrer
crystallite-**size** broadening, the $\tan\theta$ (and $\tan^2\theta$) terms
micro**strain**. The letter assignments differ between codes — GSAS uses
X = size, Y = strain; FullProf swaps them. Transfer values by matching the
$\theta$-law, never the letter.
```

Anisotropic (hkl-dependent) sample broadening is deferred to
{ref}`ch-microstructure`.

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

*Source:* `anatase.model.profiles.pseudovoigt`

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

*Source:* `anatase.model.profiles.pseudovoigt`

## The true Voigt, via the Faddeeva function

An opt-in shape (`Instrument.profile.shape = "voigt"`; TCHZ stays the
default) evaluates the exact convolution {cite}`armstrong1967`:

```{math}
:label: prof-voigt

V(x; \sigma, \gamma) \;=\; \frac{\operatorname{Re}[w(z)]}{\sigma\sqrt{2\pi}},
\qquad z = \frac{x + i\gamma}{\sigma\sqrt{2}},
```

*Source:* `anatase.model.profiles.voigt`

where $\sigma$ is the Gaussian standard deviation and $\gamma$ the
Lorentzian *half*-width at half maximum, recovered from the same component
FWHMs of {eq}`prof-caglioti-g`-{eq}`prof-caglioti-l`:

```{math}
:label: prof-voigt-widths

\sigma = \frac{\Gamma_G}{2\sqrt{2\ln 2}}, \qquad \gamma = \frac{\Gamma_L}{2}.
```

*Source:* `anatase.model.profiles.voigt`

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

*Source:* `anatase.model.profiles.faddeeva`

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

*Source:* `anatase.model.profiles.fcj`

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

*Source:* `anatase.model.profiles.fcj`

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

*Source:* `anatase.model.profiles.fcj`

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

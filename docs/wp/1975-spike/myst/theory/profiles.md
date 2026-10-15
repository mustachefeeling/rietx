(ch-profiles)=
# Peak profiles

A measured peak is the specimen's line convolved with the instrument's, so its Gaussian variances add and its Lorentzian widths add.

(sec-caglioti)=
## The Gaussian width

The Gaussian full width at half maximum, in degrees 2θ, follows a law for its square, because the variance is what adds:

```{math}
:label: prof-caglioti-g

\Gamma_G^2(\theta) \;=\; (U + U_s)\tan^2\theta + V\tan\theta + W
+ \frac{P}{\cos^2\theta}
\qquad [\deg^2 2\theta]
```

{source}`rietx.model.profiles.caglioti.gaussian_fwhm`

$U, V, W$ are the instrument resolution function {cite:p}`caglioti1958`. The sample adds a Gaussian microstrain term $U_s\tan^2\theta$ and a Gaussian size term $P/\cos^2\theta$ {cite:p}`larson2004,thompson1987`.

$\Gamma_G^2$ is a variance, so the constraint is on the sum, not on each coefficient:

```{math}
:label: prof-caglioti-positive

\Gamma_G^2(\theta) \;>\; 0
\qquad \text{for every } \theta \text{ in the fitted range}
```

{source}`rietx.strategy.staged.check_resolution_positive`

A negative $V$ is normal for a focusing geometry. The sum in {eq}`prof-caglioti-g` can't go below zero where a peak is fitted, so `gaussian_fwhm` clamps it to {const}`MIN_GAMMA_G2` deg², and a fit that breaks {eq}`prof-caglioti-positive` reports `RESOLUTION_NOT_POSITIVE`.

## Telling the terms apart

Each width term has its own angular signature. Over a wide range they separate; over a narrow one they nearly coincide.

```{image} ../figures/angular-signatures-light.png
:class: dark:hidden
:alt: Four angular signatures over 110 degrees, where they separate, and over 20 degrees, where they nearly coincide
```

```{image} ../figures/angular-signatures-dark.png
:class: hidden dark:block
:alt: Four angular signatures over 110 degrees, where they separate, and over 20 degrees, where they nearly coincide
```


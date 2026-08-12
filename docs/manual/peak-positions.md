(ch-positions)=
# Peak positions

## Lattice metric and Bragg's law

The d-spacing of reflection $(h,k,l)$ follows from the reciprocal metric
tensor $G^*$ {cite}`itc-b`:

```{math}
:label: pos-dspacing

\frac{1}{d^2} \;=\; \mathbf{h} \cdot G^* \cdot \mathbf{h}^\top,
\qquad G^* = G^{-1},
```

*Source:* `anatase.crystallography.lattice`

where $G$ is the direct metric tensor built from $(a, b, c, \alpha, \beta,
\gamma)$. Peak positions then follow Bragg's law,

```{math}
:label: pos-bragg

2\theta \;=\; 2 \arcsin\!\left(\frac{\lambda}{2d}\right).
```

*Source:* `anatase.crystallography.lattice`

Every emission line diffracts at its own Bragg angle. Differentiating
{eq}`pos-bragg` at fixed $d$ gives the doublet-splitting law

```{math}
:label: pos-doublet

\Delta 2\theta \;=\; 2 \tan\theta \cdot \frac{\Delta\lambda}{\lambda},
```

*Source:* `anatase.schemas.instrument`

which grows with $\tan\theta$ — a Kα₂ line is never a fixed offset from Kα₁.

## Aberration shifts

Three additive $2\theta$ shifts with distinct angular signatures are
modelled; the signatures are what makes them separable, and only barely so
(the decorrelation workflow below).

The **zero-point error** is a constant. **Sample displacement** in
Bragg-Brentano geometry, for a flat specimen whose surface sits a distance
$s$ off the goniometer axis with goniometer radius $R$
{cite}`wilson1963,klug1974`:

```{math}
:label: pos-displacement

\Delta 2\theta \;=\; -\frac{2 s}{R} \cos\theta \quad [\mathrm{rad}].
```

*Source:* `anatase.model.corrections.displacement_shift_deg`

The $\cos\theta$ dependence is what separates it from the zero-point error.
**Sample transparency** — finite beam penetration puts the effective
diffracting surface below the physical one (thick-sample limit
{cite}`klug1974,wilson1963`):

```{math}
:label: pos-transparency

\Delta 2\theta \;=\; -t \sin 2\theta \quad [\mathrm{rad}],
\qquad t = \frac{1}{2 \mu_{\mathrm{eff}} R},
```

*Source:* `anatase.model.corrections.transparency_shift_deg`

with $t \ge 0$ dimensionless; for strongly absorbing samples $t \to 0$ and
the correction vanishes.

These three columns (constant, $\cos\theta$, $\sin 2\theta$) are nearly
collinear over a typical angular range, and all three trade against the cell
parameters. The house workflow decorrelates them by *calibration*: refine
zero and displacement on a standard whose certified cell is held fixed, save
the instrument profile, and load it frozen for sample work.

## Wavelength scales

Kα₁/Kα₂ wavelengths are **peak** positions of the measured line shapes, not
centroids, quoted on one consistent scale: the NIST X-ray Transition
Energies Database {cite}`srd128,deslattes2003`, whose 3d-metal values derive
from the Hölzer et al. measurements {cite}`holzer1997` and whose Mo/Ag
values from Deslattes & Kessler {cite}`deslattes1985` — one *column* is the
claim, not one paper. One column of one
evaluation for all anodes is the load-bearing choice — mixing wavelength
scales between anodes (or against an older table) is the classic ~100 ppm
cell-parameter error. Bearden's compilation {cite}`bearden1967` is a
*different* scale (Mo Kα₂ differs by 24 ppm); individual rows must not be
"corrected" toward it.

*Source:* `anatase.schemas.instrument`

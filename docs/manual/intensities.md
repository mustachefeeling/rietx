(ch-intensities)=
# Intensities

## The species scattering factor

```{math}
:label: int-species

f(s, \lambda) \;=\; f_0(s) + f'(\lambda) + i\, f''(\lambda),
\qquad s = \frac{\sin\theta}{\lambda} = \frac{1}{2d}\ [\text{Å}^{-1}].
```

{source}`rietx.crystallography.dispersion`

$f_0$ is the angle-dependent, wavelength-independent elastic form factor. $f'$
and $f''$ are the angle-independent, wavelength-dependent dispersion
corrections. The split is physical. $f_0$ probes the whole electron density, so
it is keyed by ion (`La3+`). $f'/f''$ are core-level resonance effects, near
enough independent of valence, so they are keyed by element (`La`).
$f'' \ge 0$ in this convention.

$f_0$ uses the five-Gaussian parameterisation of Waasmaier & Kirfel
{cite}`waasmaier1995`:

```{math}
:label: int-f0

f_0(s) \;=\; \sum_{i=1}^{5} a_i\, e^{-b_i s^2} + c,
\qquad \text{valid for } s \le 6\ \text{Å}^{-1}.
```

{source}`rietx.crystallography.scattering.f0`

$f'/f''$ come from the Cromer-Liberman tabulation
{cite}`cromer1970,cromer1981`, the crystallographic reference calculation and
what {cite}`itc-c` §4.2.6 tabulates. That choice makes a disagreement with
another Rietveld code attributable. The Kissel & Pratt high-energy-limit
correction {cite}`kissel1990` is applied on top of it, and reaches −1.3 e at
uranium.

Absorption edges are never interpolated across, since $f''$ jumps by nearly an
order of magnitude across one grid interval at the Fe K edge. Within
{{ NEAR_EDGE_EV }} eV of an edge the request is refused outright, because the
true $f''$ there is the XANES of the compound, which no atomic table knows.
Supply measured overrides instead.

Dispersion is applied by default. It was opt-in through v0.6, so every number
recorded in `docs/milestones/` up to and including that milestone was measured
without it. Setting `source.dispersion = None` declines it and reproduces those
numbers bit-identically, and `DISPERSION_NEGLECTED` then says so. Declining a
correction that needs nothing but the species and the wavelength is a modelling
statement, and the diagnostic records it as one.

(int-neutron-b)=
### The neutron scattering length

For neutrons the whole of {eq}`int-species` collapses to one number per
species:

```{math}
:label: int-b

b \;=\; b_{\mathrm{coh}}\ [\text{fm}],
\qquad \frac{\partial b}{\partial s} = 0.
```

{source}`rietx.crystallography.neutron.b_coh`

The derivative is the content of the equation. An X-ray form factor falls off
with $s$ because the electron cloud has spatial extent comparable to $1/s$; a
nucleus is a point scatterer on this scale, so the bound coherent scattering
length carries no angular dependence at all. There is no five-Gaussian
expansion, no $f'/f''$, and $b$ is real for every nuclide this table covers.

Values are the Sears tabulation {cite}`sears1992`, reproduced as {cite}`itc-c`
§4.4.4 Table 4.4.4.1. That is the same volume this package already relies on for
dispersion, flat-plate absorption and the Lorentz-polarisation factor. Three
properties have no X-ray counterpart, and each breaks an assumption the X-ray
path is entitled to make.

- $b$ may be negative: H, Li, Ti, V and Mn among the natural-abundance elements.
  A negative $b$ is a 180° phase shift on scattering, and not an error state.
  $|F|^2$ stays positive while individual terms of the sum do not, so anything
  taking an absolute value or a square root of a single species' amplitude is
  wrong here.
- $b$ depends on the isotope rather than the element. $b(^{1}\mathrm{H}) =
  -3.741$ fm against $b(^{2}\mathrm{H}) = +6.671$ fm is a change of sign, and
  deuteration is routine for that reason. An isotope resolves to its own row and
  a mass number is kept, while an ionic charge is discarded, because the nucleus
  does not care about valence electrons. {eq}`int-species` takes the opposite
  convention, where an ion resolves to its element because $f'/f''$ is a
  core-level effect. There the element is the identity; here the isotope is.
- The table is thermal. For the resonant absorbers (Cd, Sm, Eu, Gd, and notably
  $^{113}$Cd and $^{157}$Gd) $b$ is complex and varies with wavelength near a
  resonance, the neutron analogue of an X-ray edge. At one constant wavelength a
  single thermal value is the right number. An instrument spanning a range of
  wavelengths would need $b(\lambda)$, which this table cannot give.

Everything downstream of the amplitude is unchanged. {eq}`int-F` takes $b$ where
it took $f$, the Debye-Waller factors of {eq}`int-dw-aniso` are properties of
the displacement and not of the probe, and {eq}`int-friedel` is trivially
satisfied because $B \equiv 0$ when the amplitude is real. The
Lorentz-polarisation factor {eq}`corr-lp` reduces to the bare Lorentz factor.
Neutrons are not polarised by the monochromator the way the Thomson cross
section polarises X-rays, so there is no polarisation term to carry, and
$K = 1$ makes the numerator of {eq}`corr-lp` identically 1. That is not the
unpolarised value. $K$ is the $\sigma$-polarised fraction everywhere in this
manual, and an unpolarised X-ray beam sits at $K = 0.5$.

## The structure factor

```{math}
:label: int-F

F(hkl) \;=\; \sum_j \mathrm{occ}_j\, f_j(s)
\sum_m T_{jm}(\mathbf{h})\,
e^{2\pi i\, \mathbf{h}\cdot(R_m \mathbf{x}_j + \mathbf{t}_m)},
```

{source}`rietx.crystallography.structure_factor.structure_factors_squared`

where the inner sum runs over a per-atom subset of symmetry operations, chosen
once per stage so that special-position images are not double counted. The
subset is frozen and discrete, while the positions it produces stay smooth
functions of the refined coordinates. Intensities use $|F|^2$ with the
reflection multiplicity applied separately {cite}`rietveld1969`. Multiplicities
are computed by explicit orbit counting under the Laue group, so
$\pm\mathbf{h}$ always merge into one orbit.

## Debye-Waller factors and ADP representations

Isotropic sites take $T = \exp(-B_j s^2)$ with $B_{\mathrm{iso}} = 8\pi^2
U_{\mathrm{iso}}$ (Å²) {cite}`itc-c`, identical for every image, so it
factors out of the orbit sum. Anisotropic sites do not factor:

```{math}
:label: int-dw-aniso

T_{jm}(\mathbf{h}) \;=\;
\exp\!\bigl(-2\pi^2\, \mathbf{q}^\top U^*_j\, \mathbf{q}\bigr),
\qquad \mathbf{q} = R_m^\top \mathbf{h},
\qquad U^*_{ij} = U^{ij} a^*_i a^*_j.
```

{source}`rietx.crystallography.structure_factor`

Three representations of the same tensor appear in the literature, named
explicitly here per the IUCr nomenclature report {cite}`trueblood1996`:

- $U^{ij}$ (Å²), the CIF `_atom_site_aniso_U_ij` convention, defined by
  $T(\mathbf{h}) = \exp(-2\pi^2 \sum_{ij} U^{ij} h_i h_j a^*_i a^*_j)$. This is
  the stored form, so what goes into a CIF is what came out of one.
- $U^*$ (dimensionless), $U^*_{ij} = U^{ij} a^*_i a^*_j$, the mean-square
  displacement tensor in fractional coordinates. $U^*$ transforms as
  $U^* \to R\,U^* R^\top$, so evaluating the image atom's factor at
  $\mathbf{h}$ is identically the parent's at $R^\top\mathbf{h}$, the
  reciprocal-space action again. The structure factor uses this form, and the
  identity is then exact rather than contingent.
- $U_{\mathrm{cart}}$ (Å²), whose eigenvalues are the physical mean-square
  displacements along the ellipsoid axes, with $U_{\mathrm{eq}} =
  \operatorname{tr}(U_{\mathrm{cart}})/3$ {cite}`fischer1988`.

Positive-definiteness is a property of $U_{\mathrm{cart}}$. The three
representations are congruent, so by Sylvester's law of inertia the signs of the
eigenvalues can be tested in any of them. A non-positive-definite tensor raises
an `ADP_NOT_POSITIVE_DEFINITE` diagnostic. The Debye-Waller factor diverges at
high $Q$, so the finding is not cosmetic. It is a diagnostic rather than a
bound, because the constraint couples all six components. Component order
throughout is $(U_{11}, U_{22}, U_{33}, U_{12}, U_{13}, U_{23})$. Site-symmetry
constraints on both coordinates and ADPs are covered in
{ref}`ch-parameterisation`.

## Anomalous scattering and the powder average

With dispersion on, Friedel's law dies in a non-centrosymmetric group:
$|F(\mathbf{h})|^2 \ne |F(-\mathbf{h})|^2$. A powder cannot resolve the pair,
since $d(\mathbf{h}) = d(-\mathbf{h})$ and both land in one peak. The model must
therefore return the orbit average rather than one representative's value.
Splitting the species factor into real and imaginary parts,

```{math}
:label: int-AB

\begin{aligned}
A(\mathbf{h}) &= \sum_j \mathrm{occ}_j\, (f_{0,j} + f'_j)
\sum_m T_{jm}\, e^{2\pi i \mathbf{h}\cdot\mathbf{x}_{jm}}, \\
B(\mathbf{h}) &= \sum_j \mathrm{occ}_j\, f''_j
\sum_m T_{jm}\, e^{2\pi i \mathbf{h}\cdot\mathbf{x}_{jm}},
\end{aligned}
```

gives $F = A + iB$, and since $T$ is real, $F(-\mathbf{h}) =
\overline{A - iB}$, so

```{math}
:label: int-friedel

\langle |F|^2 \rangle \;=\;
\tfrac{1}{2}\bigl(|F(\mathbf{h})|^2 + |F(-\mathbf{h})|^2\bigr)
\;=\; |A|^2 + |B|^2
```

{source}`rietx.crystallography.structure_factor`

exactly, over the same orbit sums, with no second orbit pass and no
centro/non-centro case split. In a centrosymmetric group $A$ and $B$ share one
common phase, so the cross term vanishes identically. $f'' = 0$ makes
$B \equiv 0$ and recovers $|F|^2$ bit-identically, so a structure without a
dispersion block is unchanged. Merging $\pm\mathbf{h}$ is exact with anomalous
scattering and without it, for two different reasons. {eq}`int-friedel` is the
one that keeps a single representative per Laue orbit correct to enumerate.

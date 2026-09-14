(ch-parameterisation)=
# Parameterisation and constraints

## From tree to vector

The pydantic model tree compiles to an ordered table of parameters with
stable dot-separated paths (`phases.0.cell.a`, `instrument.profile.w`) and
an affine constraint block

```{math}
:label: par-affine

p_{\mathrm{phys}} \;=\; C\, p_{\mathrm{free}} + d,
```

{source}`rietx.params.vector`

with sparse $C$ rebuilt at every stage boundary and constant during a
least-squares run, so a constant matmul stays exact under the autodiff backends.
Cell ties ($b \leftarrow a$, fixed angles) are the identity-row special case,
and Wyckoff site constraints supply general rows. Three kinds of entry are
structurally locked and can never be freed by a glob: the first emission line's
weight (degenerate with the phase scales), symmetry-fixed cell angles, and fully
fixed special positions.

The cell ties follow the space-group setting rather than the crystal system.
Three settings disagree with the system alone, and in each the number of free
cell parameters is the same either way. The count is right while the subspace is
wrong, so the test is which angle is held and which length follows which:

- a monoclinic symbol may be unique-axis $a$, $b$ or $c$, and the one angle its
  symmetry leaves free is $\alpha$, $\beta$ or $\gamma$ respectively;
- an R lattice on rhombohedral axes needs $a = b = c$ with
  $\alpha = \beta = \gamma$ free, in place of the hexagonal-axes
  $b \leftarrow a$ with $c$ free and all three angles fixed. The file decides
  which description arrives: `read_small_structure` resolves a bare `R -3 c`
  over a rhombohedral cell to the `:R` setting;
- the `:1`/`:2` extensions are origin choices and leave the metric untouched.

A symmetry-fixed angle is checked against the value its symmetry demands, and
the cell is refused if it disagrees by more than {{ SYMMETRY_ANGLE_TOL_DEG }}°.
The angle is held at its stored value, so an orthorhombic symbol over a cell
carrying $\beta = 93.2°$ would otherwise compute every $d$-spacing from that
angle in silence.

{source}`rietx.crystallography.symmetry.cell_constraints`

Strictly positive quantities (widths, scales) refine through the softplus
transform,

```{math}
:label: par-softplus

p \;=\; \log(1 + e^{u}),
```

{source}`rietx.params.transforms`

smooth, monotonic and $p > 0$ for all finite $u$, so the optimiser works in an
unconstrained variable instead of pressing a hard zero bound. Bounded quantities
use a logit.

## Site-symmetry degrees of freedom

Coordinates and anisotropic ADPs refine as site-symmetry DOFs. The constraint
bases are derived from the space-group operators by exact rational linear
algebra, with no floating-point tolerance and no per-site lookup table. (Wyckoff
naming is a separate job, delegated to spglib {cite}`togo2024`.)

A displacement δ of a site fixed by operations $\{(R, \mathbf{t})\}$ must
satisfy $R\,\delta = \delta$, so the coordinate basis spans

```{math}
:label: par-coord

\bigcap_R \ker(R - I)
```

{source}`rietx.crystallography.wyckoff`

({cite}`itc-a` sect. 8.3.2). The $U^{ij}$ tensor transforms as $U \to R\,U
R^\top$ under a rotation acting on fractional coordinates, so the allowed
ADP pattern spans the invariant subspace of that action on symmetric 3×3
matrices {cite}`peterse1966` (cross-checked against the cctbx tables
{cite}`grossekunstleve2002`):

```{math}
:label: par-adp

U \;=\; \sum_k \theta_k\, B_k,
\qquad R\, B_k\, R^\top \in \operatorname{span}\{B_j\} \ \forall R.
```

{source}`rietx.crystallography.wyckoff`

Both bases come back as smallest-integer row vectors in a deterministic
RREF-derived form. An $x,x,z$ site gives $[[1,1,0],[0,0,1]]$, and a hexagonal
three-fold site gives $U_{11} = U_{22} = 2U_{12}$ as $[2,2,0,1,0,0]$. Coordinate
DOFs are affine ties through {eq}`par-affine`. ADP DOFs are absolute
($U = \sum_k \theta_k B_k$), which enforces the site symmetry exactly, and a
tensor outside the allowed subspace raises rather than being symmetrised. The
same construction one rank up yields the Stephens $S_{HKL}$ bases of
{ref}`ch-microstructure`.

The stabiliser also fixes how many atoms the site puts in the cell. The
site multiplicity is the orbit length, and by orbit-stabiliser it is

```{math}
:label: par-multiplicity

m \;=\; \frac{|G|}{|G_{\mathbf{x}}|},
\qquad G_{\mathbf{x}} = \{(R, \mathbf{t}) : R\,\mathbf{x} + \mathbf{t} \equiv
\mathbf{x} \bmod 1\},
```

{source}`rietx.crystallography.symmetry.site_orbit`

so $m$ always divides the group order {cite}`itc-a`, and the orbit is generated
one image per left coset of $G_{\mathbf{x}}$. Counting distinct images by
pairwise comparison instead gives the same answer wherever the comparison is
exact, and no answer at all where it is inexact: proximity within a tolerance is
not transitive, so the partition follows the order the operators arrive in and
its size need not divide $|G|$. A coordinate within the tolerance of a special
position is therefore projected onto it before the images are generated, by the
Reynolds average over $G_{\mathbf{x}}$, which moves the coordinate only along
the directions {eq}`par-coord` forbids. Multiplicities feed $ZMV$ and hence
every quantitative phase fraction of {ref}`ch-estimation`, and none of that
reaches $R_{wp}$.

## Magnetic moment constraints

A site's ordered magnetic moment is symmetry-constrained the way a coordinate
is, by the operators that fix the site. Two things differ. A moment is an axial
vector rather than a polar one, and a magnetic operation carries a time-reversal
sign $\varepsilon = \pm 1$ that an ordinary space-group operation does not. An
operation $(R, \mathbf{t}, \varepsilon)$ acts on a moment as

```{math}
:label: par-moment-action

\mathbf{m} \;\to\; \varepsilon \,\det(R)\, R\, \mathbf{m},
```

{source}`rietx.crystallography.magnetic.operators.MagneticOperator.moment_matrix`

with $R$ untransposed {cite}`halpern1939` and $\varepsilon$ the magnetic
group's own sign {cite}`perezmato2015`. The reciprocal-space $R^\top$ convention
this manual uses elsewhere for an hkl does not apply to a real-space axial
vector. The allowed-moment subspace for a site's stabiliser is then
$\bigcap \ker(\varepsilon\det(R)R - I)$, the same construction as
{eq}`par-coord` with this action in place of $R$.

Moment components are stored on the crystal axes, in a right-handed basis of
unit vectors parallel to the cell edges rather than the edges themselves.
Outside a cubic cell the magnitude is therefore something other than
$\sqrt{\sum_i m_i^2}$:

```{math}
:label: par-moment-magnitude

|\mathbf{m}| \;=\; \sqrt{\mathbf{m}^\top G\, \mathbf{m}},
```

{source}`rietx.crystallography.magnetic.operators.moment_magnitude`

with $G$ the unit-vector metric, ones on the diagonal and the cell's cosines
off it. A hexagonal $(1, 1, 0)$ moment therefore has magnitude 1 $\mu_B$, and
not $\sqrt{2}$. A moment in this crystal-axis form also converts to the
orthonormal Cartesian frame `rietx.crystallography.adp.cartesian_basis` already
builds for the ADP tensor above. Normalise each direct-lattice basis vector to
unit length before applying it:

```{math}
:label: par-moment-cartesian

\mathbf{m}_{\mathrm{cart}} \;=\; \left(\frac{\mathbf{a}}{a}, \frac{\mathbf{b}}{b},
\frac{\mathbf{c}}{c}\right) \mathbf{m},
```

{source}`rietx.crystallography.magnetic.operators.moment_to_cartesian`

the same Cholesky-derived Cartesian frame the ADP construction above uses, so
the crystal-axis and fractional actions of $R$ agree and the constraint
algebra above never has to see a cell.

## Soft restraints

A bond-length, angle or value restraint contributes one row to the residual
of {eq}`fm-rows` {cite}`waser1963,watkin1994`:

```{math}
:label: par-restraint

r_{\mathrm{restr}} \;=\; \sqrt{w}\,
\frac{\mathrm{computed}(\theta) - \mathrm{target}}{\sigma},
```

{source}`rietx.model.restraints`

appended after the data rows, so restraints land in the covariance $J^\top J$
and are excluded from $R_{wp}$, Durbin-Watson and the Bérar-Lelann inflation. A
soft observation carries weight in the solution and none in the agreement
statistics. The geometry is nonlinear in θ,
where the background-penalty and Pawley rows are linear, because a bond length
$d = \sqrt{\Delta x^\top G\, \Delta x}$ depends on coordinates and cell. The
rows and their Jacobian are therefore recomputed per θ. The neighbour atom is
taken at a symmetry image $R\mathbf{x} + \mathbf{t} + \mathbf{n}$ with
$(R, \mathbf{t}, \mathbf{n})$ frozen per stage, the exact analogue of the
frozen reflection list, so positions move smoothly inside a stage while the
discrete image choice stays fixed.

## Weighting the restraints

A stage scales every restraint at once. The minimised quantity is then
eq (7) of the IUCr guidelines {cite}`mccusker1999`,

```{math}
:label: par-restraint-weight

S \;=\; S_y \;+\; c_w S_G,
\qquad S_G \;=\; \sum_k w_k \left(
\frac{\mathrm{computed}_k(\theta) - \mathrm{target}_k}{\sigma_k}\right)^2,
```

{source}`rietx.model.forward.CompiledModel.restraint_residual`

with $S_y$ the data rows of {eq}`est-obj` and $S_G$ the restraint rows of
{eq}`par-restraint` squared. The guidelines set $c_w$ high while the structural
model is incomplete or approximate, and reduce it as the model improves. That
makes it a property of the stage rather than of the restraint. It is frozen onto
the compiled model at stage compile, so a schedule changes it between stages and
never inside one.

Two seams decide where the scalar may act. $\sqrt{c_w}$ multiplies the assembled
rows, so every backend sees it through one row builder. It never reaches the
compiled restraints or their partials, whose second consumer computes the
derived-quantity esds of {eq}`est-derived` at $\sigma = w = 1$; a scale leaking
that far would multiply every reported bond esd by $\sqrt{c_w}$. And $c_w = 0$
silences the rows without deleting them, so the row count the agreement
statistics exclude cannot move part-way through a plan.

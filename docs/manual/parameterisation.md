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

*Source:* `pxrdref.params.vector`

with sparse $C$ rebuilt at every stage boundary and constant during a
least-squares run — a constant matmul stays exact under the autodiff
backends. Crystal-system cell ties ($b \leftarrow a$, fixed angles) are the
identity-row special case; Wyckoff site constraints supply general rows.
Structurally locked entries — the first emission line's weight (degenerate
with the phase scales), symmetry-fixed cell angles, fully fixed special
positions — can never be freed by a glob.

Strictly positive quantities (widths, scales) refine through the softplus
transform,

```{math}
:label: par-softplus

p \;=\; \log(1 + e^{u}),
```

*Source:* `pxrdref.params.transforms`

smooth, monotonic and $p > 0$ for all finite $u$, so the optimiser works in
an unconstrained variable instead of pressing a hard zero bound; bounded
quantities use a logit.

## Site-symmetry degrees of freedom

Coordinates and anisotropic ADPs refine as site-symmetry DOFs, with the
constraint bases *derived* from the space-group operators by exact rational
linear algebra — no floating-point tolerance, and no per-site lookup table.
(Wyckoff naming is a separate job, delegated to spglib {cite}`togo2024`.)

A displacement δ of a site fixed by operations $\{(R, \mathbf{t})\}$ must
satisfy $R\,\delta = \delta$, so the coordinate basis spans

```{math}
:label: par-coord

\bigcap_R \ker(R - I)
```

*Source:* `pxrdref.crystallography.wyckoff`

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

*Source:* `pxrdref.crystallography.wyckoff`

Both bases come back as smallest-integer row vectors in a deterministic
RREF-derived form — an $x,x,z$ site gives $[[1,1,0],[0,0,1]]$; a hexagonal
three-fold site gives $U_{11} = U_{22} = 2U_{12}$ as $[2,2,0,1,0,0]$.
Coordinate DOFs are affine ties through {eq}`par-affine`; ADP DOFs are
**absolute** ($U = \sum_k \theta_k B_k$), which enforces the site symmetry
exactly — a tensor outside the allowed subspace raises rather than being
symmetrised. The same construction, one rank up, yields the Stephens
$S_{HKL}$ bases of {ref}`ch-microstructure`.

## Soft restraints

A bond-length, angle or value restraint contributes one row to the residual
of {eq}`fm-rows` {cite}`waser1963,watkin1994`:

```{math}
:label: par-restraint

r_{\mathrm{restr}} \;=\; \sqrt{w}\,
\frac{\mathrm{computed}(\theta) - \mathrm{target}}{\sigma},
```

*Source:* `pxrdref.model.restraints`

appended after the data rows, so restraints land in the covariance
$J^\top J$ but are excluded from Rwp, Durbin-Watson and the Bérar-Lelann
inflation — soft observations, not data. Unlike the background-penalty and
Pawley rows the geometry is nonlinear in θ (a bond length
$d = \sqrt{\Delta x^\top G\, \Delta x}$ depends on coordinates *and* cell),
so the rows and their Jacobian are recomputed per θ. The neighbour atom is
taken at a symmetry image $R\mathbf{x} + \mathbf{t} + \mathbf{n}$ with
$(R, \mathbf{t}, \mathbf{n})$ **frozen per stage** — the exact analogue of
the frozen reflection list — so positions move smoothly inside a stage
while the discrete image choice stays fixed.

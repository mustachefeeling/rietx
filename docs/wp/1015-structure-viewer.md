# WP-1015 — Structure viewer, zero new dependencies

Milestone: v1.0 · Status: ⬜ not started
Depends on: WP-1010 (WP-1014 soft — the viewer is richer once editing exists)

## Goal

A rotatable 3D structure view — atoms, bonds, cell, thermal ellipsoids —
with **no new JS dependency**: the server computes a small geometry payload
from code that already exists, and plotly (already on the page) renders it.

## Context

- **Everything hard already exists server-side**:
  - `crystallography/symmetry.py:56` `expand_positions(sg, xyz, *, tol=1e-4)`
    — symmetry expansion to the full cell.
  - `crystallography/adp.py` — `cartesian_basis` (`:89`), `u_cartesian`
    (`:101`), `principal_values` (`:113`), `is_positive_definite` (`:132`)
    are exactly the eigen-decomposition a thermal ellipsoid needs (already
    used by the positive-definiteness guard); `u_equivalent` (`:108`) sizes
    the isotropic spheres.
  - gemmi (a core dep) supplies element radii/colours and neighbour search
    for bonds.
- `src/pxrdref/gui/structure3d.py` computes a JSON payload: expanded atom
  positions in Cartesian coordinates, cell-edge polyline, bond segments by
  radius-sum cutoff, and per-atom ellipsoid transforms. Frontend renders
  with plotly `Scatter3d` (atoms, bonds, cell edges) + `Mesh3d` (a unit
  sphere transformed by each U_cart eigen-decomposition). Rotate/zoom come
  free. Payload for a typical cell is a few kB. Served at
  `GET /api/structure3d` (route reserved in WP-1008).
- **Why this is a diagnostic, not decoration**: the ellipsoids are refined
  quantities. A non-positive-definite ADP — the existing
  `ADP_NOT_POSITIVE_DEFINITE` diagnostic — becomes visibly degenerate
  (flagged in the payload, rendered distinctly, never NaN geometry), and an
  over-flexible background inflating ADPs becomes visible as balloons.
  Ellipsoids draw at a selectable probability (default 50 %); isotropic
  atoms draw as spheres of the U_eq-equivalent radius.
- Remember the representation rules (`crystallography/adp.py` module doc):
  stored CIF **U^ij**, fractional **U\*** for the structure factor,
  **U_cart** where eigenvalues are physical — the viewer wants U_cart, and
  the isotropic limit is U^ij = Uiso·G\*ᵢⱼ/(a\*ᵢa\*ⱼ), not Uiso·δᵢⱼ.

### Inherited

From the **v1.0 GUI plan** (2026-07-29): escalation path if a full
ball-and-stick/polyhedra viewer is later wanted — 3Dmol.js (BSD-3,
permissive, clears the licensing invariant, needs an ATTRIBUTION.md entry)
as an opt-in vendored asset. **Not v1**; recorded so the next person doesn't
re-derive the licence answer.

From **WP-1008** (GUI server, landed 2026-07-30): `GET /api/structure3d` is
**reserved** and 404s naming this WP, so the route is settled — decide its
payload here. `GET /api/structure` already serves the whole validated
`Structure` dump, so the 3D route only earns its place by returning something
the model does not already say (expanded symmetry images, bonds, a cell frame);
if it would only reshape `Structure`, do it in the frontend and leave the route
reserved rather than shipping a second view of the same fact.

## Non-goals

- No coordination polyhedra, no supercell packing view, no measurement
  tools (distances/angles readout beyond hover) — v2 with the 3Dmol.js
  escalation if wanted.
- No client-side crystallography: the frontend receives Cartesian geometry
  and draws it; symmetry never crosses the wire.

## Tasks

- [ ] `src/pxrdref/gui/structure3d.py`: payload builder (expanded
      positions, cell edges, bonds by radius-sum cutoff, ellipsoid
      transforms at a probability level; NPD tensors flagged).
- [ ] `GET /api/structure3d` on the session (current model state, so edits
      reflect immediately).
- [ ] Structure panel: Scatter3d + Mesh3d rendering, probability selector,
      species legend from gemmi colours.
- [ ] `tests/test_structure3d.py`: cubic and monoclinic phases give the
      right atom multiplicity and 12 cell edges; a known aniso CIF's
      ellipsoid axes match `principal_values`; a non-positive-definite
      tensor is flagged in the payload rather than producing NaN geometry.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_structure3d.py -q
npm --prefix gui test
.venv/bin/python -m ruff check src tests examples
```

## References

- `crystallography/adp.py` (three-representation module doc);
  `crystallography/symmetry.py` `expand_positions`; gemmi element tables.

## Handover log

- **2026-07-29** — created from the v1.0 GUI plan. All cited server-side
  helpers verified present (exact names/lines) the same day.

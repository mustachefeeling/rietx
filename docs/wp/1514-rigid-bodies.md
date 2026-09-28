# WP-1514 — Rigid bodies: a fragment refined by position, orientation and torsion

Milestone: unscheduled · Status: ⬜
Track: Data and metadata in, a structure out
Depends on: — (1319 soft, the fragment file a body is read from)
Priority: P3 2026-09-28 — a workaround covers it (bond restraints at high weight, or an external parameterisation); prerequisite for WP-1515

## Goal

A molecular fragment of known geometry enters a phase as one object and is
refined by its translation, its orientation and, where declared, its
torsions. It goes through `ParameterTable` and the Jacobian like any other
parameter family. A disorder copy of it can be tethered to its partner, and
its hydrogens ride on it.

## Context

**Unfenced 2026-09-28.** "Z-matrices and rigid bodies (#195)" sat in
ROADMAP § v2+. The grounds for moving it are in DESIGN.md § Locked
decisions, *Structure fence revised*.

**Source.** `solution case 1` (private corpus map § 5), described in
WP-1510. The structure has two metal sites and two rigid aromatic ligands
in the asymmetric unit. What the run needed:

- **Free atoms failed.** At about 2.4 effective observations per parameter
  a free-atom Rietveld fit let the rings buckle to chase intensity. The
  person asked for flat rings.
- **So the agent built its own body.** 18 degrees of freedom: two metal
  positions, plus per ligand an anchor atom, an axis (two angles) and a
  twist, with a Rodrigues rotation of an ideal template. It lived outside
  rietx and pushed coordinates in through `set_values`.
- **The handoff to Rietveld held the shape with restraints.**
  `BondRestraint` on the 1-2, 1-3 and 1-4 ring distances at
  `restraint_weight_scale=100`. That keeps a hexagon planar, at the cost of
  a stiff restraint block.
- **Disorder copies needed a tether.** Two copies of each ligand were held
  within about 1 Å of each other by a penalty in a raw scipy loop, because
  rietx's restraints (`Bond`, `Angle`, `Value` in
  `schemas/structure.py:623-676`) are all equalities.
- **Hydrogens were placed by hand** at a fixed distance for the CIFs.

**The design problem.** `ParameterTable` is affine: coordinates are
x = x₀ + C·θ, with ties and site-symmetry DOFs as rows of C. A rotation is
not affine. A body needs a nonlinear decode between θ and atom coordinates,
and root CLAUDE.md's invariants apply to it:

- a new Jacobian branch declares its reach, and anything beyond it takes
  the whole-model FD column (`_column_extras`);
- the traced twin (`backend/traced.py`) must carry it for jax and torch,
  and `test_cross_backend.py` gets a row;
- no pydantic in the hot loop;
- frozen-per-stage discreteness is unaffected, since orientation is
  continuous.

**Choices to make in the design note.**

- The orientation: a quaternion or Euler angles (gimbal lock).
- Where the body's origin sits, and how a body on a special position
  interacts with site symmetry.
- The fragment's source: an ideal template, a CIF fragment, or WP-1319's
  molecular XYZ, which was waiting for exactly this consumer.
- Torsions as a Z-matrix or as named rotatable bonds.

**Prior art and licences** (DESIGN.md § Locked decisions):
- GSAS-II: vector and residue rigid bodies. BSD-style, so verify its
  LICENSE before reading any code.
- TOPAS: rigid bodies and Z-matrices in its macro language. Closed, so
  papers only (Coelho 2000).
- FOX / ObjCryst++: native Z-matrix bodies. Licence **unverified**, so
  papers only until it is checked.
- DASH: builds Z-matrices from mol2. Commercial, so papers only.

## Non-goals

- Global search (WP-1515).
- Molecules built from a SMILES string. That needs a toolkit dependency,
  and is a later rung.

## Tasks

- [ ] Design note in this file: orientation, decode placement, the reach
      the Jacobian branch declares, the fragment source. Maintainer decision
      recorded.
- [ ] Schema for a body on a phase, and its dot-paths.
- [ ] Decode with an FD column first, then the analytic branch, with its
      reach gate and a `test_cross_backend.py` row.
- [ ] A max-distance (tether) restraint between two bodies or atoms.
- [ ] Riding hydrogens, written to the CIF.
- [ ] Manual Part 2 equation with its `*Source:*` line; Part 1 chapter;
      `help.py` family.
- [ ] Skill: the routing row for a molecular fragment.

## Acceptance

A public organic or metal-organic structure refined from a perturbed start
with its rings as bodies recovers the published ring centroids and
orientations within their esds, and the cross-backend row agrees.

```sh
.venv/bin/python -m pytest tests/test_cross_backend.py tests/test_restraints.py -n auto --dist loadgroup
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

## References

- Coelho, A. A. (2000). *J. Appl. Cryst.* 33, 899–908. Rigid bodies and
  Z-matrices in whole-profile simulated annealing.
- Favre-Nicolin, V. & Černý, R. (2002). *J. Appl. Cryst.* 35, 734–743. FOX.
- Toby, B. H. & Von Dreele, R. B. (2013). *J. Appl. Cryst.* 46, 544–549.
  GSAS-II.

## Handover log

- **2026-09-28** — created from the review of `solution case 1`, with
  WP-1510 to 1513 and 1515 to 1517. Nothing started.

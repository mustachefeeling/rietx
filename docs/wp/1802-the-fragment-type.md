# WP-1802 — the fragment: a body template with a frame and declared bonds

Milestone: v1.8 · Status: 🔄 2026-09-30 — claimed by @mustachefeeling
Depends on: 1801 soft (the rotation of a template into place)
Priority: P3 2026-09-30 — a building block; no user sees it until 1803's seam and a later WP exist

## Goal

`crystallography/fragments.py` holds a `Fragment`: atoms with Cartesian
template coordinates, an explicit bond list, and a body frame with its count of
rotational degrees of freedom. A Z-matrix builds one, and a collinear triple is
refused by name.

## Context

Scoped in issue #561 (chunk R1) and WP-1514, amended by the 2026-09-30 review.

- The DOF count follows the template's inertia rank: none for one atom, two for
  a linear fragment, three otherwise. A near-linear tolerance needs a test.
- **Bonds are declared, never perceived from geometry** (WP-1319's rule): a
  coordinate-only format cannot tell an aromatic ring from a chain.
- TOPAS's manual gives the third Z-matrix atom's plane as x–z on p. 103 and x–y
  on p. 139. Pick one and pin it with a test.
- **Benzene is built from ideal D6h geometry**, not from the printed numbers of
  a closed manual (licensing fence, root CLAUDE.md).
- The Cartesian frame is `crystallography.adp.cartesian_basis`. Its docstring
  disclaims any a-along-x convention and it calls `np.linalg.cholesky`, which is
  not an `xp` op. 1803 decides the frame contract; this WP stores template
  coordinates in Å and assumes nothing about the cell.

## Non-goals

- A `RigidBody` schema, a parameter-table block, torsions, restraints (later WPs).
- Public export: keep it unexported, so `api_surface.py` and the skill's
  `api.md` headroom stay as they are.
- File readers (XYZ, SMILES): WP-1319 and a later WP.

## Tasks

- [ ] `Fragment` type, body frame, DOF count, declared bonds
- [ ] Z-matrix builder; a collinear triple raises naming the atoms; the plane convention pinned
- [ ] Tests: ideal D6h benzene; a Z-matrix cyclopentadienyl round trip; a linear fragment gets 2 DOFs; a near-linear tolerance case
- [ ] Skill: none, no public surface

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_fragments.py -q
.venv/bin/python -m ruff check src tests examples
```

## References

- Issue #561; WP-1514; WP-1319.

## Handover log

- **2026-09-30** — created, from the 2026-09-30 issue triage (issue #561). No
  open WP owns it.

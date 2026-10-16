# WP-1814 — refinable internal geometry: Z-matrix lengths, angles and dihedrals

Milestone: rigid-bodies · Status: ⬜
Depends on: 1815 (the derived-geometry table its esds are reported through); 1805
Priority: P3 2026-10-16 — TOPAS users expect it, and a refined bond with its esd is what a paper reports; nothing is wrong without it

## Goal

A rigid body built from a Z-matrix can refine its bond lengths, bond
angles and dihedral angles as ordinary parameters, each with an esd.

## Context

Issue #759 (mustachefeeling, 2026-10-06), section 1, chunk "1814" in its
provisional numbering, kept here. A Z-matrix places each atom of a molecule
from three earlier ones by a bond length r, a bond angle θ and a dihedral
φ. TOPAS refines them (Coelho, *TOPAS-Academic V6 Technical Reference*,
2015, § 10.22.1).

Checked at `138d55dc`: `from_zmatrix` (`crystallography/fragments.py:252`)
takes constant lengths, angles and dihedrals.

The proposal (#759 § 1), taken as the plan on 2026-10-16:

- `RigidBody.zmatrix: list[ZLine]`, each line's `r`, `angle` and `dihedral`
  a `Parameter`; a `PointLine` for a Cartesian template point.
- The map x_i = o + M(cell)⁻¹·Exp(δω)·R₀·(T_i(ζ) − c₀), with **c₀ a constant
  body-frame point frozen at declaration**. Recomputing the centroid as a
  length changes would turn a bond stretch into a shift of every atom.
- ∂x/∂ζ by forward-mode tangent propagation through the placement
  recursion. The reporter checked it against central differences to 8e-11
  on a synthetic triclinic fragment.
- A Z-matrix dihedral is not WP-1808's named-bond torsion. The subtree rule
  is wrong for it in general (line 3's angle off by 0.065 Å per degree on
  the reporter's fragment). A body declaring both on one bond compares the
  two reaches and refuses on a difference.
- Restrained or refined, never both by accident: a restraint on a fixed
  template quantity is refused at compile; on a refined `r` it is that
  parameter's prior.

### Inherited

## Non-goals

- Named-bond torsions (WP-1808, shipped).
- TLS and the TOPAS rigid import (fenced 2026-10-16).

## Tasks

- [ ] `ZLine`/`PointLine` on `RigidBody`, the frozen c₀, and the dot-paths.
- [ ] The tangent-propagation Jacobian; the six placement partials checked against complex step.
- [ ] The restrain-or-refine refusals and the torsion-reach refusal.
- [ ] Tests: placement partials vs complex step < 1e-12; the map's Jacobian vs FD < 1e-9; a freed C–C on acridine IX (COD 2242872) within its published esd
- [ ] Skill: the routing row for refining a Z-matrix body

## Acceptance

```sh
.venv/bin/python -m pytest tests/ -k "zmatrix or rigid_bod" -q
.venv/bin/python -m ruff check src tests examples
```

## References

- Coelho (2015), *TOPAS-Academic V6 Technical Reference*, § 10.22 (papers-only fence).
- Von Dreele (2019), *Powder Diffr.* 34, S32.
- Issue #759.

## Handover log

- **2026-10-16** — created, from the 2026-10-16 issue triage (issue #759),
  behind WP-1815 as the maintainer decided. Checked against the tree at
  `138d55dc`: `from_zmatrix` takes constants. No open WP owns it: WP-1808
  names it as a non-goal and is closed. Next: wait for WP-1815.

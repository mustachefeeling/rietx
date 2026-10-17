# WP-1815 — derived geometry: torsions, a request form, one table every writer reads

Milestone: rigid-bodies · Status: ⬜
Depends on: 1804 (the derived block's local Jacobian, for body atoms)
Priority: P3 2026-10-16 — a view over what the fit already knows; WP-1933's CIF torsion loop waits on it

## Goal

`GeometryTable` carries torsion angles with esds beside bonds, contacts and
angles. A caller can ask for particular distances, angles and torsions. The
CIF writer, the FitReport and the foreign exporters read that one table and
never compute an esd themselves.

## Context

Issue #759 (mustachefeeling, 2026-10-06), section 2, chunk "1815" in its
own provisional numbering, kept here. Decided 2026-10-16 (the issue triage,
maintainer): file this first and the Z-matrix internals (WP-1814) behind
it; fence TLS and the TOPAS rigid import.

Checked at `138d55dc`: `model/geometry.py` has no torsion rows. It lists
bonds, contacts and angles with esds through the full covariance, built once
at fit close because the covariance is never serialised. The CIF writer
writes `_geom_bond`, `_geom_contact` and `_geom_angle` only.

The proposal (#759 § 2):

- `GeometryTable.torsions` (`GeometryTorsion`: four labels, four symmetry
  codes, value, esd, diagonal-only esd), listed over bonded chains with a
  cap recorded in `notes`; Klyne–Prelog sign, range (−180, 180]
  (cif_core `_geom_torsion.angle`).
- `GeometryRequest(distances, angles, torsions)` and
  `Refinement.geometry(request=None)`, answered while the last stage's
  covariance is live; a replay answers values with `None` esds, as today.
- `TorsionRestraint` sharing the torsion row's partials (the WP-1072 reuse
  rule: a geometry row is a restraint row); its residual is the circular
  difference, so 180° is a smooth target.

Three rules the reporter measured, to keep:

- A quantity fixed by symmetry or by a body reports no esd (the existing
  `VARIANCE_CANCELLATION_FLOOR`).
- Esds carry the Bérar–Lelann factor once. The covariance is already built
  from the inflated diagonal, so nothing downstream multiplies again.
- Torsion partials are analytic through atan2. A central difference at
  exactly 180° gave an esd of 6·10⁶°.

### Inherited

## Non-goals

- Refinable Z-matrix internals (WP-1814).
- TLS and the TOPAS rigid import (#759 § 4, fenced 2026-10-16).
- Riding hydrogens on a free atom (#759's "1816"), not filed in this round.

## Tasks

- [ ] `GeometryTorsion` rows over bonded chains, with the cap in `notes`.
- [ ] `GeometryRequest` and `Refinement.geometry(request=)`.
- [ ] `TorsionRestraint` on the shared partials.
- [ ] The CIF torsion loop (with WP-1933, which waits on it).
- [ ] Tests: J·Cov·Jᵀ against Monte Carlo (circular difference) within 5 %; a template-fixed bond reports `None`; a torsion at exactly 180° has a finite esd; the CIF torsion loop round-trips
- [ ] Skill: the reference row for `Refinement.geometry`

## Acceptance

```sh
.venv/bin/python -m pytest tests/ -k geometry -q
.venv/bin/python -m ruff check src tests examples
```

## References

- Klyne & Prelog (1960), *Experientia* 16, 521 (torsion sign convention).
- Issues #759, #756.

## Handover log

- **2026-10-16** — created, from the 2026-10-16 issue triage (issue #759).
  The maintainer took the triage's recommendation: this WP first, WP-1814
  behind it, TLS and TOPAS rigid import fenced. Checked against the tree at
  `138d55dc`: no torsion rows in `model/geometry.py`. No open WP owns it:
  WP-1808 and WP-1922 name it as a non-goal and are closed. Next: the rows.

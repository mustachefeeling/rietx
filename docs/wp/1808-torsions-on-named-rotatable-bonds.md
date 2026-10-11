# WP-1808 — torsions on named rotatable bonds

Milestone: rigid-bodies · Status: ⬜
Depends on: 1802, 1805
Priority: P3 2026-10-06 — a flexible molecule needs it; a rigid one does not

## Goal

A torsion rotates a declared atom subset about the line through two named body atoms,
and refines with an esd. This is chunk R7 of issue #561, sized M.

## Context

- A torsion is an anchored rotation, composed at commit like the body's own rotation
  (WP-1805).
- A torsion that moves nothing, or that misses the body, is refused.
- The forward tangents run through chained torsions, and each torsion declares its
  reach (WP-1804's rule: readers use the declared reach, never the numeric one).
- Manual Part 2 gains the torsion equation (`par-torsion`).
- An outside branch builds it (`3401fdd7`, on #561, 2026-10-06). It treats the angle as
  an absolute parameter wrapped at write-back. About one axis that equals composing, but
  WP-1805's commit rule governs.

### Inherited

- **2026-10-08, from WP-1805 (answer a to #801): torsions are the second kind that
  folds at commit.** The maintainer chose to keep a body's rotation kind on its
  `RigidBodyBlock`, with no `Entry` field and no further side dict on the table. A
  torsion composed at commit is the second user, so build the general form here: each
  block names the inputs it folds and returns its piece of ∂θ_old/∂θ_new, and
  `ParameterTable.commit` loops over blocks. The moment sign flip (#604) can join it.
  Ceres's `Manifold` on a parameter block is the same pattern.

- **2026-10-11, from the issue triage (#561, in PR #823): this WP is open as
  a PR.** PR #823 (the reporter's) builds R7: a torsion is an anchored rotation
  composed at commit (φ₀ ← φ₀ + δφ), `rechart_outcome` is unchanged because
  composing about one axis is addition, and the twist rides WP-1805's seams
  (the commit guard and rollback, `restore_body_anchors`,
  `displace_anchored_dofs(…, torsions=)`, `anchored_rotation_paths`,
  `body_dofs`). It is a third increment kind for the tie rule and targets
  schema 0.44 → 0.45. WP-1805's handover says it needs a rebase onto #801 and
  #825. Checked against the tree at 7d9be3cb: no `BodyTorsion` in
  `schemas/structure.py`; this file named only the branch commit `3401fdd7`.

- **2026-10-11, from the issue triage (#759 § 1): a Z-matrix dihedral is not
  this WP's torsion.** Rotating the downstream subtree is wrong for a Z-matrix
  parameter, since a later line's dihedral may reference an atom that moves:
  on the reporter's 8-atom fragment line 3's angle moved 0.065 Å a degree.
  This WP stays the rigid rotation of a declared set about a line. Where a
  body declares both on one bond, compile compares the two reaches and refuses
  on a difference, naming the atoms. Refinable Z-matrix internals stay a
  separate chunk. Checked against the tree at 7d9be3cb: `from_zmatrix`
  (`crystallography/fragments.py:252`) takes constant values, and this file
  lists internals only as a non-goal.

## Non-goals

- Refinable Z-matrix internals on free atoms (issue #759).

## Tasks

- [ ] `BodyTorsion` schema (SCHEMA bump) and the collector
- [ ] Forward map, declared reach, refusals
- [ ] Manual equation; cross-backend torsion column
- [ ] Tests + obs/calc/diff PNGs to `tests/output/`
- [ ] Skill: a reference row if a new code lands

## Acceptance

- A 30° biphenyl twist is recovered from a synthetic pattern within 1°, and the esd
  covers it.
- The block Jacobian agrees with central FD.
- The two torsion conventions (Z-matrix dihedral and bond rotation) agree on one
  fragment.
- A torsion that moves nothing is refused.

## References

- Issue #561; PR #596.

## Handover log

- **2026-10-06** — created by WP-1803's re-cut, from #596's proposal.

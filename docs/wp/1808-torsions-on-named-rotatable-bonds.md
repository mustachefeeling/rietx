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

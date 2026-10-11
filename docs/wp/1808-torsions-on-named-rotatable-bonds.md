# WP-1808 — torsions on named rotatable bonds

Milestone: rigid-bodies · Status: 🔄 2026-10-11 — every task landed from outside (PR #823, merged as `c6163587`); the close is the maintainer's
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

- [x] `BodyTorsion` schema (SCHEMA bump) and the collector
- [x] Forward map, declared reach, refusals
- [x] Manual equation; cross-backend torsion column
- [x] Tests + obs/calc/diff PNGs to `tests/output/`
- [x] Skill: a reference row if a new code lands

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

- **2026-10-11** — every task landed from outside: PR #823 (`mustachefeeling`),
  head `47b0d793`, merged as `c6163587` after three review rounds.
  - **What it adds.** `RigidBody.torsions`, a list of `BodyTorsion`
    (`SCHEMA_VERSION` 0.45): a named turn of a declared atom set about the line
    through two body atoms, applied before the pose (TOPAS's
    `Rotate_about_points`). It refines as an anchored increment,
    `phases.*.rigid_bodies.*.torsions.*.twist`, composed into the `angle`
    record at every commit as the body rotation is. Part 2 has the equation
    (`par-torsion`), `help.py` the twist entry, and `test_cross_backend.py`'s
    `bodies` config a torsion column.
  - **Acceptance.** `tests/test_body_torsions.py` covers all four lines: the
    planted 30° twist, the block Jacobian against a central difference, the
    Z-matrix dihedral against the bond rotation, and a torsion that moves
    nothing refused. No diagnostic code landed, so the skill task adds nothing.
  - **Found in review and fixed before merge.** A zero-length axis made every
    body atom NaN without an error; it is now refused by the torsion's name,
    the chained case included. The hold refusal names the twist glob. Three
    citations gained their journals. The commit's docstring, `RigidBody`'s map
    and the `help.py` sign now say what the code does.
  - **Gate.** Stacked with #870, #822 and #853 on `main` `b7df6a10` as
    `a3495a34`, macOS arm64, `[dev,jax]`, nothing else running: fast 9173
    passed, 115 skipped, 1 xfailed and 1 failed (#843's Hypothesis case); slow
    305 passed, 12 skipped. `main` after the
    last merge (`8c5c6879`) differs from it only by three docs-and-CI merges
    (#879, #881, #874) that landed between #823 and #822. The fast suite on
    `f7ab7096` with #853 gave the same counts, and nothing the slow suite
    runs changed.
  - **This entry's PR** fixes the manual's dihedral sentence, which round 1
    fixed in `help.py` only. Written with its middle pair in the axis's order,
    a dihedral changes by +φ when its last atom moves and by −φ when its first
    does.
  - **Left open, by agreement:** a tied twist in `test_cross_backend.py`'s
    `bodies` config; one helper for the three numpy walks of the torsion chain
    and the two index-triple builders; `compare_freed` reading
    `anchored_dof_paths` and not the rotation set (inherited from #801).

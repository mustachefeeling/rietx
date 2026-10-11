# WP-1808 — torsions on named rotatable bonds

Milestone: rigid-bodies · Status: ✅ 2026-10-11 — merged as #823: a torsion turns a declared set about a bond, composed at commit
Depends on: 1802, 1805

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

## Non-goals

- Refinable Z-matrix internals on free atoms (issue #759).

## Tasks

- [x] `BodyTorsion` schema (SCHEMA bump) and the collector
- [x] Forward map, declared reach, refusals
- [x] Manual equation; cross-backend torsion column
- [x] Tests + obs/calc/diff PNGs to `tests/output/`
- [x] Skill: a reference row if a new code lands (none landed, so no row)

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

- **2026-10-11** — what the review of #823 adds to the reconstructed entry
  below, from the `/pr-review` run that merged it.
  - **Found in review and fixed before merge.** A zero-length axis made every
    body atom NaN without an error (`NaN < TORSION_STILL_TOL` is false); it is
    now refused by the torsion's name, the chained case included. The hold
    refusal names the twist glob. Three citations gained their journals.
  - **Gate.** Stacked with #870, #822 and #853 on `main` `b7df6a10` as
    `a3495a34`, macOS arm64, `[dev,jax]`, nothing else running: fast 9173
    passed, 115 skipped, 1 xfailed and 1 failed (#843's Hypothesis case); slow
    305 passed, 12 skipped.
  - **The manual's dihedral sentence** is fixed in PR #884. Round 1 fixed it
    in `help.py` only: written with its middle pair in the axis's order, a
    dihedral changes by +φ when its last atom moves and by −φ when its first
    does.
  - **Left open, by agreement:** a tied twist in `test_cross_backend.py`'s
    `bodies` config; one helper for the three numpy walks of the torsion chain
    and the two index-triple builders; `compare_freed` reading
    `anchored_dof_paths` and not the rotation set (inherited from #801).

- **2026-10-09** — (reconstructed post hoc, 2026-10-11, from the three
  `WP-1808:` commits and PR #823's body and thread) built by @mustachefeeling
  in PR #823; the maintainer merged it on 2026-10-11 as `c6163587`; closed.

  A rigid body can now carry torsions. Each one turns a declared set of the
  body's atoms about the line through two of its atoms, and refines with an
  esd. It follows WP-1805's rule for the body's rotation: the record keeps the
  angle, the table refines an increment that is zero at every build, and the
  commit folds the increment into the record. All four acceptance rows were
  met and measured in the PR. No session handed the WP over at the time,
  because the work arrived as a contributor's pull request.

  *Done* (commits `79c97733` 2026-10-06, `bec7a0f4` 2026-10-08, `b8b6bad7`
  2026-10-09):
  - `RigidBody.torsions: list[BodyTorsion]` in `schemas/structure.py`, with
    `SCHEMA_VERSION` 0.44 → 0.45. The record is `BodyTorsion.angle`, in
    degrees and kept in (−180, 180]. The refined path is
    `…torsions.t.twist`, so the record and the step have different names.
  - `params/bodies.py` builds the forward map and its tangents through chained
    torsions, so a later torsion's axis may ride on atoms an earlier one moved.
    `RigidBodyBlock.commit_torsions` sets φ₀ ← φ₀ + δφ and δφ ← 0.
    `rechart_outcome` needed no change, because composing about one axis is
    addition.
  - The torsion rides each of WP-1805's seams: the commit guard and its
    rollback (`_commit_state`/`_restore_commit_state` from #825),
    `restore_body_anchors`, the series carry (`displace_anchored_dofs(…,
    torsions=)`), `anchored_rotation_paths`, `body_dofs` and
    `apply_to_models`. A twist ties only to a twist.
  - Refusals: an empty moved set (schema), a moved set on the axis line within
    1e-6 Å (table build), an axis or moved atom outside the body, a repeated
    name, and an axis shorter than `TORSION_STILL_TOL` (the review fix).
  - A `help.py` row, `PLACES` in `gui/src/lib/history.ts` with the dist
    rebuilt, manual Part 2's `par-torsion`, two torsions in the `bodies`
    config of `tests/test_cross_backend.py`, and `tests/test_body_torsions.py`.
    `BodyTorsion` is deferred in `tests/api_surface_deferred.txt` until
    WP-1812.

  *Measured* (the contributor's figures, quoted from #823):
  - The planted 30° twist came back as 29.93° from a 0° start, esd 0.054°,
    so the error is 1.2σ, at Rwp 0.031.
  - The block Jacobian agrees with a central difference within 1e-8 relative
    at a turned anchor, and the chained-axis tangent within 1e-9. The Z-matrix
    dihedral and the bond rotation agree to 1e-12 on a tree fragment.
  - Fast suite on head `b8b6bad7`, Mac, `.venv-test`, Python 3.12,
    `-m "not slow"`: 9063 passed, 108 skipped, 1 xfailed, 6 failed. Linux
    x86-64, `[dev,jax]`, Python 3.12, on `0c77b3e1`: 8943 passed, 128
    skipped, 1 xfailed, 6 failed. In both, the six were a version-stamp
    warning from a stale editable install (`test_skill` and five
    `test_tutorials` cells), and they failed identically on main.

  *Inherited, consumed at the close.* The entry saying #823 was open is
  stale, since it merged. The triage's #759 § 1 entry is a rule for future
  work: a Z-matrix dihedral and a torsion declared on one bond must have their
  reaches compared at compile, with a refusal naming the atoms on a
  difference. It cannot fire today, because `from_zmatrix` returns Cartesian
  positions and keeps no dihedral to compare. It waits on refinable Z-matrix
  internals, which #759 tracks and no WP owns yet. The v1.8 record carries it.

  The diff does not say why the PR answered its three questions (the
  twist's name, no box on the twist, reporting the increment rather than the
  angle) the way it did. The thread says only that the maintainer's answers
  matched what was built.

  Next: nothing on this WP. Reporting the composed angle with its esd is
  WP-1812's surface, as is promoting `BodyTorsion` out of the deferred list.

- **2026-10-06** — created by WP-1803's re-cut, from #596's proposal.

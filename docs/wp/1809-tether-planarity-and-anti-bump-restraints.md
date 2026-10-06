# WP-1809 — Tether, planarity and anti-bump restraints, pairs frozen per plan

Milestone: rigid-bodies · Status: ⬜
Depends on: —
Priority: P3 2026-10-06 — needs no body; it can run beside WP-1804

## Goal

Three restraint kinds join `Bond`/`Angle`/`Value`: a one-sided maximum distance (the
tether), a planarity term, and anti-bump over a candidate pair list. This is chunk R8 of
issue #561, sized M. It needs no body.

## Context

- It builds on the shipped restraint seam (WP-0406, WP-1074) and on nothing in this
  milestone.
- The `Restraint` union grows, so SCHEMA bumps.
- **The anti-bump pair list is frozen at plan compile**, from pairs within r₀ + a
  margin (the record, [`docs/DESIGN.md` § Parameter system](../DESIGN.md#parameter-system)).
  Its rows exist for the whole plan, zero inside the one-sided term. A per-stage rebuild
  would move the restraint row count that `rows.layout`, WP-1074's per-stage c_w and the
  stage-boundary Jacobian test assume constant. A plan-end `RESTRAINT_PAIRS_STALE`
  diagnostic names pairs that entered r₀ from outside the list.
- An outside branch (`3b333db0`, on #561, 2026-10-06) has the caller build the list
  into explicit rows instead of the engine freezing it at plan compile. That departs
  from the record. If it is kept, ask the maintainer first.
- The pair-list builder uses the minimum-image shift from PR #778 (merged), so the list
  does not depend on which cell an atom is stored in.
- It may land as two PRs: tether and anti-bump first, then planarity and the stale-pairs
  diagnostic.

## Non-goals

- Restraints across a body under the live cell, beyond what these tests cover.

## Tasks

- [ ] Tether and anti-bump rows; the pair-list builder frozen at plan compile
- [ ] Planarity rows; `RESTRAINT_PAIRS_STALE` at plan end
- [ ] Manual Part 2 equations for the new kinds
- [ ] Tests (the acceptance below)
- [ ] Skill: a reference row for `RESTRAINT_PAIRS_STALE`

## Acceptance

- The tether row is zero inside and has slope 1/σ outside.
- Analytic against FD < 5e-3 for each kind, tested *at the kink* and on both sides.
- Rwp is bit-identical to the no-row statistics.
- The restraint row count is constant across a plan's stages.
- The pair list is complete against an exhaustive search and independent of the stored
  cell.
- A pair that enters r₀ from outside the list is named.

## References

- Issue #561; PR #596; issue #777 and PR #778 (the minimum-image shift).

## Handover log

- **2026-10-06** — created by WP-1803's re-cut, from #596's proposal.

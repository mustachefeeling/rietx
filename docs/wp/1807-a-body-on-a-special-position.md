# WP-1807 — a body on a special position

Milestone: rigid-bodies · Status: ⬜
Depends on: 1805
Priority: P3 2026-10-06 — a body on a centre or a mirror is refused until this lands

## Goal

An invariant body on a special position refines with only the DOFs its site allows. This
is chunk R6 of issue #561, sized S.

## Context

- The rotation DOFs take the axial-vector invariant subspace of the site stabiliser,
  `allowed_moment_basis(ops, use_time_reversal=False)`. The origin takes its site basis.
- A non-invariant fragment is refused, naming the atom. WP-1805's
  `RIGID_BODY_NOT_INVARIANT` already fires on diacetylene (an outside branch, 2026-10-06).
- A disordered body is stored at occupancy 1/|G_s| with `Atom.disorder_group`.

### Inherited

- **2026-10-08, from WP-1805 (answer c to #801): two free turn directions are
  refused.** A body's free turn directions must number 0, 1 or 3, since two turns
  combined produce the third and the re-chart cannot be exact on two. A site
  stabiliser's axial-vector invariant subspace always has dimension 0, 1 or 3 (a
  mirror or a 2-fold leaves one axis, two axes leave none), so a body on a special
  position never trips the refusal. A test that a stabiliser-derived basis passes it
  is cheap and pins that.

## Non-goals

- Torsions (WP-1808).

## Tasks

- [ ] Rotation and origin bases from the site stabiliser; the refusal by name
- [ ] The diacetylene case and a monoclinic case + obs/calc/diff PNGs to `tests/output/`
- [ ] Skill: none expected; say why at handover

## Acceptance

- Diacetylene at 5 K (COD 1577467, CC0; Wombat, 2.413 Å) on the Pnma mirror gets 2
  origin DOFs and 1 rotation DOF. Origin x and z lie within the deposited esds, and the
  orientation stays in the mirror to 1e-12.
- A monoclinic case passes.
- A non-invariant fragment is refused, naming the atom.

## References

- Issue #561; PR #596.

## Handover log

- **2026-10-06** — created by WP-1803's re-cut, from #596's proposal.

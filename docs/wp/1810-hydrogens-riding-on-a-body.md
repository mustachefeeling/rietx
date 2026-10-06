# WP-1810 — hydrogens riding on a body, CIF flags

Milestone: rigid-bodies · Status: ⬜
Depends on: 1805; 1806 soft (a real case to show it on)
Priority: P4 2026-10-06 — a body refines without its hydrogens; this is completeness

## Goal

A body's H atoms ride with it, at an X–H length set by bond class and radiation, and a
CIF write records which atoms were constrained. This is chunk R9 of issue #561, sized S.

## Context

- `crystallography/riding.py` holds the X–H lengths by bond class and radiation. The
  neutron template's C–H differs from the X-ray one by the tabulated offset, and a joint
  fit takes the neutron lengths.
- `_atom_site_refinement_flags_posn` writes `G` for body atoms, `R` for riding H, and
  `calc` where computed.
- It touches no v1.6 file. #596 made WP-1806 a hard dependency. Nothing here reads
  WP-1806's data, so it is soft.
- An outside branch builds it (`0d28c964`, on #561, 2026-10-06). That file reads back,
  but the reader does not rebuild a body from the flags.

## Non-goals

- Riding H on free atoms (issue #759).
- Rebuilding a body from CIF flags on read.

## Tasks

- [ ] Riding H lengths by class and radiation; `RigidBody.riding`
- [ ] The CIF flags on write
- [ ] Tests (the acceptance below)
- [ ] Skill: none expected; say why at handover

## Acceptance

- A CIF round trip keeps the flags.
- The neutron and X-ray templates differ by exactly the tabulated offset.
- A class with no tabulated length is refused.
- A phase with no body writes neither column.

## References

- Issue #561; PR #596.

## Handover log

- **2026-10-06** — created by WP-1803's re-cut, from #596's proposal, with WP-1806
  made a soft dependency.

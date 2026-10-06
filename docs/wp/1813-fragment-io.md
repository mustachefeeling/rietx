# WP-1813 — fragment I/O: XYZ, Z-matrix write, SMILES behind an extra

Milestone: rigid-bodies · Status: ⬜
Depends on: 1802, 1319
Priority: P4 2026-10-06 — a fragment can already be built by hand or from a Z-matrix

## Goal

A `Fragment` reads from XYZ, writes as a Z-matrix, and builds from SMILES when an
optional extra is installed. This is chunk R12 of issue #561, sized M.

## Context

- XYZ lands with WP-1319's structure interchange.
- Bonds are declared, never perceived from geometry (WP-1319's rule), so an XYZ read
  needs its bonds from somewhere else.
- **Licensing:** RDKit (BSD-3) only, never OpenBabel (GPL-2).
- It touches no v1.6 file.

## Non-goals

- Rebuilding a body from CIF flags (WP-1810's non-goal).

## Tasks

- [ ] XYZ read (with WP-1319)
- [ ] Z-matrix write
- [ ] SMILES behind an extra, with a refusal naming the extra when it is absent
- [ ] Tests (the acceptance below)
- [ ] Skill: a reference row for the new readers

## Acceptance

- Benzene built from SMILES has a planar template.
- An install without the extra refuses, naming the extra.

## References

- Issue #561; PR #596; WP-1319.

## Handover log

- **2026-10-06** — created by WP-1803's re-cut, from #596's proposal.

# WP-0501 — Capillary and flat-plate absorption

Milestone: v0.5 · Status: ⬜ not started (stub — expand before starting)
Depends on: —

## Scope (carried verbatim from the pre-split roadmap)

- Capillary (Debye-Scherrer) and flat-plate absorption (Sabine 1998 /
  Lobanov-Alte da Veiga)

## Context pointers

- Lands beside displacement/transparency in `model/corrections.py`, gated on
  `Geometry.kind` the same way.
- v0.5 milestone acceptance: capillary/absorption vs GSAS-II consistency —
  which means **adopting GSAS-II's protocol**, per
  [../DESIGN.md](../DESIGN.md#testing--validation-policy).
- Distinct from WP-0305 (Brindley acts on QPA fractions; this acts on the
  profile/intensity vs θ).

## Tasks

- [ ] Expand this stub into a full WP before writing code

## Handover log

- **2026-07-22** — created as a stub from the ROADMAP split.

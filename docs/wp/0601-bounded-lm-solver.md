# WP-0601 — TOPAS-style bounded LM solver

Milestone: v0.6 · Status: ⬜ not started (stub — expand before starting)
Depends on: —

## Scope (carried verbatim from the pre-split roadmap)

- TOPAS-style bounded LM: Gauss-Newton normal equations + adaptive Marquardt
  λ (Coelho 2018, JAC 51:428) + bound-constrained CG inner solve (Coelho
  2005, JAC 38:455) + line search — independent implementation from the
  papers, same driver interface as the scipy path

## Context pointers

- [../DESIGN.md](../DESIGN.md#minimizer-strategy) — same driver interface as
  `optimize/least_squares.py`; the scipy TRF path remains the reference.
- Licensing fence: TOPAS is closed — **papers only**, independent
  implementation ([../DESIGN.md](../DESIGN.md#locked-decisions)).
- Milestone acceptance: solver benchmark vs scipy TRF.

## Tasks

- [ ] Expand this stub into a full WP before writing code

## Handover log

- **2026-07-22** — created as a stub from the ROADMAP split.

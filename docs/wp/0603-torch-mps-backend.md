# WP-0603 — torch backend (MPS fp32 forward)

Milestone: v0.6 · Status: ⬜ not started (stub — expand before starting)
Depends on: WP-0401

## Scope (carried verbatim from the pre-split roadmap)

- torch backend with MPS fp32 forward (the Mac GPU path; no Apple GPU has
  fp64 in any framework)

## Context pointers

- [../DESIGN.md](../DESIGN.md#locked-decisions) — the no-Apple-fp64 hard
  constraint; fp32 is Jacobian-columns-only per invariant 2.
- One autodiff backend at a time (scope discipline): torch starts only after
  the jax path (WP-0402…0404) is green.
- torch has no `wofz` — the WP-0405 shared Faddeeva is what makes true Voigt
  work here.

## Tasks

- [ ] Expand this stub into a full WP before writing code

## Handover log

- **2026-07-22** — created as a stub from the ROADMAP split.

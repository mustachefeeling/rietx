# WP-0404 — Cross-backend Jacobian-agreement CI

Milestone: v0.4 · Status: ⬜ not started (stub — expand before starting)
Depends on: WP-0402

## Goal

CI that proves analytic, FD and jacfwd Jacobians agree — including at stage
boundaries — so backend drift is caught the day it happens, not the day it
ships a wrong esd.

## Scope (carried verbatim from the pre-split roadmap)

- Cross-backend Jacobian-agreement CI (analytic vs FD vs jacfwd, incl. stage
  boundaries)

## Context pointers

- [../DESIGN.md](../DESIGN.md#risks--mitigations) — "Backend drift → small op
  vocabulary + mandatory cross-backend tests"; this WP is that mitigation.
- The v0.2 analytic-vs-FD agreement test (<5×10⁻³ relative, cosine >0.99999
  over 18 parameter families) is the tolerance style to extend, not replace.

## Tasks

- [ ] Expand this stub into a full WP before writing code
- [ ] Stage-boundary cases (frozen-state regeneration between stages is where
      discreteness bugs would surface)

## Handover log

- **2026-07-22** — created as a stub from the ROADMAP split.

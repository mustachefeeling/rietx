# WP-0401 — Backend op shim

Milestone: v0.4 · Status: ⬜ not started (stub — expand before starting)
Depends on: —

## Goal

A ~40-op backend abstraction (`backend/api.py`) that lets the forward model
run on numpy or jax without per-call branching.

## Scope (carried verbatim from the pre-split roadmap)

- ~40-op backend shim (`backend/api.py`); per-backend `scatter_add` (not in
  the Array API standard)

## Context pointers

- [../DESIGN.md](../DESIGN.md#locked-decisions) — backend decision, the fp64
  constraint, and why one autodiff backend at a time.
- Risk to design against: **backend drift** → keep the op vocabulary small and
  make cross-backend tests mandatory (WP-0404).

## Non-goals

torch (WP-0603). Anything that toggles jax's global x64 flag (WP-0403 covers
that fence).

## Tasks

- [ ] Expand this stub into a full WP (Goal/Context/Tasks/Acceptance) before
      writing code
- [ ] Enumerate the op set actually used by the forward model; keep it minimal
- [ ] `scatter_add` per backend

## Handover log

- **2026-07-22** — created as a stub from the ROADMAP split.

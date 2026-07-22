# WP-0402 — JAX backend: chunked jacfwd Jacobians

Milestone: v0.4 · Status: ⬜ not started (stub — expand before starting)
Depends on: WP-0401

## Goal

The forward model running on the WP-0401 shim under jax, with chunked
`jacfwd` Jacobians and jit.

## Scope (carried verbatim from the pre-split roadmap)

- jax backend: chunked `jacfwd` Jacobians (cost ≈ N_params × forward — the
  win is exactness + jit, not fewer evals)

## Context pointers

- [../DESIGN.md](../DESIGN.md#locked-decisions) — backend decision; jax-metal
  is abandoned, no Apple-GPU fp64 anywhere.
- [../DESIGN.md](../DESIGN.md#architecture-invariants) — frozen-per-stage
  discreteness is what makes the residual traceable at all; nothing
  data-dependent may enter the graph.
- The forward model was written differentiable from day one (no clamps,
  smooth reparameterisations, quadrature split at the FCJ kink) — jacfwd
  correctness is the payoff for those invariants.

## Non-goals

CUDA/mixed-precision policy (WP-0403); torch (WP-0603).

## Tasks

- [ ] Expand this stub into a full WP before writing code
- [ ] Optional `[jax]` extra; import must not affect numpy-only users
- [ ] Chunked jacfwd with a chunk size that bounds peak memory

## Handover log

- **2026-07-22** — created as a stub from the ROADMAP split.

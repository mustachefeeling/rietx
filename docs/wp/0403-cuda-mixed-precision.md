# WP-0403 — CUDA + mixed-precision policy

Milestone: v0.4 · Status: ⬜ not started (stub — expand before starting)
Depends on: WP-0402

## Goal

GPU execution with the fp64 correctness boundary enforced: fp32 is allowed
for Jacobian *columns* only; the residual used for cost/statistics and the
solve stay fp64 on host.

## Scope (carried verbatim from the pre-split roadmap)

- CUDA + mixed precision: fp32 Jacobian *columns* only; residual for
  cost/statistics and the solve stay fp64 on host (fp32 y_calc at ~10⁵ counts
  loses ~10 counts to cancellation)
- Never toggle jax's global x64 flag on import; fp64 lives in host numpy
  (`linalg64.py`)

## Context pointers

- [../DESIGN.md](../DESIGN.md#architecture-invariants) invariant 2 — the fp64
  correctness boundary this WP implements; JᵀJ squares the condition number,
  which is why the solve can never be fp32.

## Non-goals

Apple-GPU paths (no fp64 exists there — torch-MPS fp32 forward is WP-0603).

## Tasks

- [ ] Expand this stub into a full WP before writing code
- [ ] `linalg64.py` host-side fp64 boundary; agreement gate vs the fp64 path

## Handover log

- **2026-07-22** — created as a stub from the ROADMAP split.

# WP-0403 — Mixed-precision policy (CUDA-deferred, CPU-testable)

Milestone: v0.4 · Status: ⬜ not started
Depends on: WP-0402

## Goal

The fp32-Jacobian-columns / fp64-host-residual-and-solve policy implemented
as an explicit, CPU-testable policy object (`backend/linalg64.py`), validated
on the numpy path by simulated fp32 column casting, with an opt-in CUDA
validation script for whenever a GPU appears. **No CUDA hardware is assumed
or required to complete this WP** (decided 2026-07-24: the maintainer's
machine is a Mac; real-GPU validation of the same policy arrives locally via
torch-MPS in WP-0408).

## Context

- [../DESIGN.md](../DESIGN.md#architecture-invariants) invariant 2 — the fp64
  correctness boundary this WP implements. fp32 y_calc at ~10⁵ counts loses
  ~10 counts to cancellation, and JᵀJ squares the condition number — the
  residual used for cost/statistics and the solve can never be fp32; only
  Jacobian *columns* are relative-accuracy tolerant.
- Never toggle jax's global x64 flag on import (WP-0402 owns the scoped-x64
  mechanism); fp64 lives in host numpy, and the boundary lives in exactly one
  file: `backend/linalg64.py`.

### Design (decided)

- **`MixedPrecisionPolicy`** in `backend/linalg64.py`: fields
  `jacobian_dtype: fp32|fp64` (default fp64), `residual_dtype` and
  `solve_dtype` fixed fp64 (not configurable — the invariant is code, not a
  setting). Casting is **column-granular**: the policy's `cast_columns(J)`
  hook is applied per Jacobian column; it never touches the residual or the
  JᵀJ solve.
- **The CPU-testable gate: simulate fp32 by round-tripping.** On the numpy
  path, `cast_columns` = `col.astype(np.float32).astype(np.float64)` — this
  is deterministic and incurs exactly the precision loss a real GPU fp32
  column would, so the agreement gate ("an fp32-column Jacobian still solves
  to the same parameters within a looser tolerance") is fully testable
  without hardware. The *policy* is the unit under test, decoupled from the
  device.
- **`linalg64.py` host boundary contents:** the policy object; the single
  explicit fp64 cast of any incoming Jacobian before JᵀJ
  (`J64 = np.asarray(J, dtype=np.float64)`); assertions/documentation that
  residual and covariance solve are fp64 by construction.
- **CUDA-deferred validation script:** `examples/validate_cuda_mixed_precision.py`
  — opt-in, guarded by GPU availability (skips cleanly on this Mac). When a
  CUDA box exists it builds the SRM 660c Jacobian on-device in fp32 columns,
  crosses the fp64 host boundary, solves, and asserts the refined parameters
  match the pure-fp64 path within the fp32-column tolerance. It is
  documentation-as-code for that day, not a CI gate.
- Tolerances (shared with WP-0404): per-column fp32 agreement <2e-2 rel-L2 /
  cosine >0.999; parameter-level gate: SRM 660c `a` within 3e-5 Å and Rwp
  within 1e-4 of the pure-fp64 refine.

## Non-goals

Apple-GPU paths (torch-MPS is WP-0408, which *consumes* this policy on real
local hardware); any change to the fp64 numpy default path; making
`jacobian_dtype=fp32` a user-facing default anywhere.

## Tasks

- [ ] `backend/linalg64.py`: `MixedPrecisionPolicy` + host fp64 boundary
      (cast J→fp64 before JᵀJ); residual/solve fp64 asserted
- [ ] Wire `cast_columns` into the Jacobian assembly (numpy path applies the
      fp32 round-trip when the policy is active)
- [ ] `examples/validate_cuda_mixed_precision.py` — opt-in, GPU-gated, skips
      cleanly without CUDA
- [ ] Tests: `tests/test_mixed_precision.py` — fp32-column-simulated SRM 660c
      refine matches the fp64 `a` within 3e-5 Å and Rwp within 1e-4;
      residual/solve dtypes asserted fp64 + obs/calc/diff PNGs to
      `tests/output/`

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_mixed_precision.py -q
```

Measured: with fp32-column simulation active, SRM 660c refines to the same
`a` within 3e-5 Å and Rwp within 1e-4 of the pure-fp64 path; residual and
JᵀJ solve are fp64 (asserted). The CUDA script runs only where a GPU exists.

## References

- Higham (2002) *Accuracy and Stability of Numerical Algorithms*, 2nd ed.,
  SIAM — normal-equations conditioning (cond(JᵀJ) = cond(J)²).

## Handover log

- **2026-07-22** — created as a stub from the ROADMAP split.
- **2026-07-24** — expanded from stub (v0.4 planning session): retitled to
  "Mixed-precision policy (CUDA-deferred, CPU-testable)"; simulated-fp32
  gate, `linalg64.py` contents and the opt-in CUDA script decided (no CUDA
  hardware available — real-GPU validation arrives via WP-0408 torch-MPS).

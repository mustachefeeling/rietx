# WP-0403 — Mixed-precision policy (CUDA-deferred, CPU-testable)

Milestone: v0.4 · Status: ✅ 2026-07-24
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

- [x] `backend/linalg64.py`: `MixedPrecisionPolicy` + host fp64 boundary
      (cast J→fp64 before JᵀJ); residual/solve fp64 asserted
- [x] Wire `cast_columns` into the Jacobian assembly (numpy path applies the
      fp32 round-trip when the policy is active)
- [x] `examples/validate_cuda_mixed_precision.py` — opt-in, GPU-gated, skips
      cleanly without CUDA
- [x] Tests: `tests/test_mixed_precision.py` — fp32-column-simulated SRM 660c
      refine matches the fp64 `a` within 3e-5 Å and Rwp within 1e-4;
      residual/solve dtypes asserted fp64 + obs/calc/diff PNGs to
      `tests/output/`

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_mixed_precision.py -q
```

**Measured 2026-07-24** — 13 tests green (12 fast + 1 `slow`); full suite 388
tests green, ruff clean.

| quantity | fp64 | fp32 columns | Δ | bar |
|---|---|---|---|---|
| SRM 660c `a` (Å) | 4.156895220 | 4.156895220 | 2.6e-11 | 3e-5 |
| Rwp | 0.08661290 | 0.08661290 | 1.1e-13 | 1e-4 |
| esd(`a`) | 7.3688e-06 | 7.3688e-06 | 1.9e-7 rel | 5e-2 rel |
| worst column rel-L2 | — | — | 2.6e-8 | 2e-2 |
| worst column cosine | — | — | 1.0 | >0.999 |

Residual and JᵀJ solve are fp64 by construction and asserted at runtime
(`require_fp64` in `run_least_squares` and `covariance_estimates`). The CUDA
script skips with a printed reason on this Mac.

**Read the margins honestly.** The CPU round-trip reproduces the fp32
*representation* limit exactly — what a device fp32 column costs crossing the
host boundary — but not error accumulated *inside* a device fp32 forward pass,
which is strictly larger. So clearing device-sized bars by six orders of
magnitude is expected, and is not evidence about real GPU numerics. This
acceptance proves the **plumbing**: reduced columns cannot leak into the
residual or the solve, and the policy reaches the assembled Jacobian on every
mode. WP-0408 (torch-MPS) supplies the device-numerics evidence.

## References

- Higham (2002) *Accuracy and Stability of Numerical Algorithms*, 2nd ed.,
  SIAM — normal-equations conditioning (cond(JᵀJ) = cond(J)²).

## Handover log

- **2026-07-22** — created as a stub from the ROADMAP split.
- **2026-07-24** — expanded from stub (v0.4 planning session): retitled to
  "Mixed-precision policy (CUDA-deferred, CPU-testable)"; simulated-fp32
  gate, `linalg64.py` contents and the opt-in CUDA script decided (no CUDA
  hardware available — real-GPU validation arrives via WP-0408 torch-MPS).
- **2026-07-24** — **landed.** All four checklist items in three commits;
  measured acceptance recorded above.

  **Done.** `backend/linalg64.py` holds invariant 2 in one file:
  `MixedPrecisionPolicy` (only `jacobian_dtype` is a field; `residual_dtype`
  and `solve_dtype` are read-only properties pinned to fp64, so the violating
  configuration is *unspellable* rather than merely discouraged),
  `to_host_fp64` as the single explicit cast, `require_fp64` as the check, and
  `column_agreement` supplying the rel-L2/cosine metric. Exported from
  `pxrdref.backend`. Scoped via `with precision_policy(FP32_JACOBIAN)`,
  mirroring `set_backend`'s existing global-with-scope shape.

  **Where the hook went, and why there.** `cast_columns` is applied in
  `optimize.least_squares._jacobian_for`, wrapping whichever callable the
  backend produced — the one exit point numpy and jax already share. That
  means WP-0408's torch backend inherits the policy with no further wiring.
  The policy is read *per call*, not captured at closure build, so a
  `with precision_policy(...)` block takes effect on an already-constructed
  solver (that is what lets the acceptance test wrap a whole `ref.fit`).
  Under the default fp64 policy the wrapper degrades to `np.asarray`, so the
  numpy path is unchanged — `test_policy_reaches_the_assembled_jacobian`
  asserts bit-equality against `_make_jacobian` to keep it that way.

  **Gotcha for 0404/0408 — the CPU simulation is weaker than it looks.**
  Round-tripping fp64→fp32→fp64 captures representation loss only, not
  accumulation inside a device forward pass. Measured column agreement is
  ~2.6e-8 rel-L2 against a 2e-2 bar. Do **not** read that margin as headroom
  for real hardware, and do not tighten the shared bars to match it — they are
  sized for a device computing the whole peak-chain in fp32, which nothing on
  this machine can do. `COLUMN_REL_L2_MAX` / `COLUMN_COSINE_MIN` live in
  `linalg64.py` for 0404 to import rather than restate.

  **Gotcha — `require_fp64` refuses, it never upcasts.** On the residual path
  a silent upcast would hide exactly the bug the check exists to catch. Note
  the asymmetry at `covariance_estimates`: the *Jacobian* argument is upcast
  (reduced columns are legal, and that is where they re-enter fp64) while the
  *residual* argument raises. Anything feeding a non-fp64 residual there is a
  real defect, not a configuration.

  **Not a vacuous suite.** `test_normal_equations_square_the_conditioning` is
  the one that would actually catch a regression of the invariant: a
  Vandermonde design at cond(J) ≈ 1e5 recovers coefficients to <1e-4 through
  fp32 columns + an fp64 solve, and is destroyed by an fp32 normal matrix. It
  makes Higham's cond(JᵀJ) = cond(J)² argument executable rather than asserted
  in a docstring.

  **Next.** WP-0404 (cross-backend Jacobian CI) — import the bars from
  `linalg64`, add an fp32-column row to the agreement matrix alongside the
  jax/numpy rows, and carry 0402's handover note about the FCJ S/L == H/L
  subgradient kink needing a loose bar. Then WP-0408 consumes this policy on
  torch-MPS for the first real-hardware measurement.

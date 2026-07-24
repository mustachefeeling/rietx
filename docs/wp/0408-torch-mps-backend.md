# WP-0408 — torch backend (MPS fp32 forward)

Milestone: v0.4 · Status: ⬜ not started
Depends on: WP-0401, WP-0402, WP-0404 (also consumes WP-0403's policy and
WP-0405's `w(z)`)

<!-- Was WP-0603 (v0.6); pulled into v0.4 on 2026-07-24 — see Context. -->

## Goal

A `TorchBackend` on the WP-0401 op shim: fp64 on CPU (an independent row in
the cross-backend agreement matrix) and fp32 forward + Jacobian columns on
Apple MPS under the WP-0403 mixed-precision policy — local GPU acceleration
on the maintainer's Mac, and the first *real-hardware* validation of the
fp32-column policy.

## Context

- **Why this is in v0.4 and not v0.6** (decided 2026-07-24): MPS acceleration
  cannot come through jax — jax-metal is abandoned, a locked decision
  ([../DESIGN.md](../DESIGN.md#locked-decisions)) — so it requires torch. The
  v0.4 shim (0401) and agreement CI (0404) make a second backend far cheaper
  to add, and torch-MPS is what makes WP-0403's fp32-Jacobian-column policy
  testable on real GPU hardware rather than only in CPU simulation. See the
  dated amendment in DESIGN.md's locked decisions.
- **The scope-discipline condition is preserved by sequencing, not by
  milestone:** torch work starts only after the jax path (WP-0402) *and* the
  cross-backend CI (WP-0404) are green. One autodiff backend is brought up at
  a time; the second lands against an existing agreement harness.
- **The hard constraint:** no Apple GPU supports fp64 in any framework
  ([../DESIGN.md](../DESIGN.md#locked-decisions)), and JᵀJ squares the
  condition number ⇒ fp64 torch runs on **CPU**; MPS runs fp32 for the
  forward and Jacobian columns only, crossing WP-0403's `linalg64.py` host
  boundary before the solve (invariant 2). complex128 on CPU, complex64 on
  MPS.
- torch has no `wofz` — the WP-0405 shared Faddeeva is what makes the true
  Voigt option work here, and is the reason it is implemented on the op set
  rather than per-backend.

### Design (decided)

- **Autodiff strategy: torch accelerates the *forward*; `torch.func.jacfwd`
  is the fp64-CPU cross-check.** The analytic peak-chain columns are already
  exact and cheap, so on MPS the win is forward throughput (batched
  einsum/exp/`window_add`), not autodiff. Use `torch.func.jacfwd`/`vmap` over
  one-hot seeds on **CPU fp64** as an independent Jacobian for the WP-0404
  matrix — that is what proves the torch impl of the op set is correct.
- **`window_add` / `segment_sum` on torch:** both via `index_add` on the
  frozen window range; keep the functional signature from 0401.
- **Packaging/wiring:** optional `[torch]` extra; lazy import inside
  `set_backend("torch")` so numpy-only users are unaffected; flip the
  `backend="torch"` `NotImplementedError` in `refine.py`/`multi.py`. Device
  and dtype come from the WP-0403 policy, not from ad-hoc flags.
- **Benchmark, reported not gated:** `examples/bench_torch_mps.py` times the
  forward evaluation and a full refine, MPS vs numpy, on the 11-BM NAC
  pattern (synchrotron, single wavelength — the simplest hot loop) and SRM
  676a corundum. Wall-clock is hardware-dependent, so it is **reported** in
  the milestone record, never asserted as a threshold.

## Non-goals

torch autodiff replacing the analytic Jacobian on the numpy path; fp64 on
MPS (does not exist); CUDA-specific work (WP-0403 owns the policy and its
deferred CUDA script); the TOPAS-style bounded LM solver (WP-0601).

## Tasks

- [ ] `[torch]` extra; `TorchBackend` on the 0401 op set (`window_add`/
      `segment_sum` via `index_add`; complex128 CPU / complex64 MPS); device
      and dtype selected by the WP-0403 policy
- [ ] `torch.func.jacfwd`/`vmap` fp64-CPU Jacobian; add the torch row to the
      WP-0404 matrix
- [ ] MPS fp32 forward + fp32 Jacobian columns crossing the `linalg64.py`
      fp64 host boundary
- [ ] Wire `backend="torch"` through `refine.py`/`multi.py`; add the
      `uv pip install -e ".[dev,jax,torch]"` line to CLAUDE.md commands
- [ ] `examples/bench_torch_mps.py`: MPS vs numpy wall-clock on 11-BM NAC and
      SRM 676a (reported)
- [ ] Tests (`pytest.importorskip("torch")`): torch-fp64-CPU Jacobian
      agreement <5e-3 / cosine >0.99999; torch-MPS-fp32 SRM 676a refine
      matches the numpy `a` within 3e-5 Å; the numpy path is unaffected +
      obs/calc/diff PNGs to `tests/output/`

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_backend_torch.py -q   # skips without torch
.venv/bin/python examples/bench_torch_mps.py                # reports MPS vs numpy, not gated
```

Measured: the torch fp64-CPU Jacobian agrees with the analytic and jax
Jacobians to <5e-3 rel-L2 / cosine >0.99999; a torch-MPS fp32 refine of SRM
676a matches the numpy `a` within 3e-5 Å (the WP-0403 fp32-column band); the
MPS-vs-numpy speedup on 11-BM NAC is recorded in the milestone record.

## References

- [../DESIGN.md](../DESIGN.md#locked-decisions) — the no-Apple-fp64 hard
  constraint and the 2026-07-24 amendment moving `[torch]` into v0.4.
- Higham (2002) *Accuracy and Stability of Numerical Algorithms*, 2nd ed.,
  SIAM — why the solve stays fp64 (shared with WP-0403).
- `torch.func` (`jacfwd`, `vmap`) documentation.

## Handover log

- **2026-07-22** — created as a stub (WP-0603, v0.6) from the ROADMAP split.
- **2026-07-24** — **moved to WP-0408 / v0.4** and expanded (v0.4 planning
  session). Rationale: the maintainer wants local GPU acceleration, which
  jax cannot provide on Apple hardware; sequencing after 0402+0404 preserves
  the one-autodiff-backend-at-a-time discipline. Strategy decided: torch
  accelerates the forward on MPS fp32 under the 0403 policy, with
  `torch.func.jacfwd` on CPU fp64 as the agreement cross-check; benchmark
  reported, not gated.

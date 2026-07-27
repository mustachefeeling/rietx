# WP-0408 — torch backend (MPS fp32 forward)

Milestone: v0.4 · Status: ✅ shipped 2026-07-27
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

### Inherited

From **WP-0401** (op shim, landed 2026-07-24) — the contract `TorchBackend`
must satisfy, so these are not open design choices:

- **The three sites to flip.** `backend: str = "numpy"` is already threaded
  through `refine.py` (~line 58), `multi.py` (~line 73) and
  `schemas/common.py` (~line 109), each raising for unknown backends. That is
  the whole integration surface.
- **`window_add` is functional**, returning a new array — callers thread
  `y = xp.window_add(...)`. torch may implement it with `index_add`, but must
  not expose in-place semantics, and must **not** widen the API to a general
  index-array scatter even though torch supports one: data-dependent indices
  are what frozen-per-stage discreteness forbids. `segment_sum` is likewise
  `index_add` (numpy uses `bincount`, jax `jax.ops.segment_sum`).
- **Bind once, not per op.** Hot-loop code does `xp = get_backend()` once per
  compiled-model call, so the backend cannot depend on per-call device/dtype
  inspection — device and dtype come from WP-0403's policy object.
- **Gotcha (1), which binds every non-numpy backend, not just jax:**
  compile-time code (`fcj_extent_deg`, node sizing) shares `_xi_max`, which is
  xp-routed. Set the non-numpy backend only *around the solve*, or
  `np.asarray` at the compile boundary, so frozen state stays host numpy. For
  MPS this is sharper than it was for jax: leaking device tensors into
  `compile_model` would put non-fp64 arrays into frozen state.
- **Gotcha (2):** the FCJ fallback `ok` predicate and one-hot fallback weights
  assume `n_nodes` (hence shapes) frozen — true by construction, but a
  shape-dynamic torch implementation would break it silently.
- **The analytic-column path is not traceable and never will be.**
  `derivative_bases` keeps a python `isfinite` skip on purpose: it is host-side
  Jacobian support, and mask-converting it would let NaN structural/PO gradient
  columns reach `window_add`. Residual-path masking lives in
  `_reflection_profile` and `phase_peaks` instead.

From **WP-0402** (jax backend, landed 2026-07-24): `_jacobian_for` in
`optimize/least_squares.py` is the single dispatch point — add the torch branch
there and the mixed-precision policy, multi-histogram wiring and Pawley/Le Bail
row layout all come for free. 0402 deliberately shipped no multi-histogram jax
test for that reason (the wiring is shared); the same argument applies here.

From **WP-0403** (mixed-precision policy, landed 2026-07-24):

- The policy object is `MixedPrecisionPolicy` in `backend/linalg64.py`; scope
  it with `with precision_policy(FP32_JACOBIAN)`. `jacobian_dtype` is its only
  field — `residual_dtype`/`solve_dtype` are read-only properties pinned to
  fp64, so there is deliberately no way to configure an fp32 residual or solve.
- `cast_columns` is already applied at `_jacobian_for`'s exit, so **torch
  inherits the policy with no new wiring** — do not add a second hook.
- **This WP supplies the first real evidence about the policy.** The CPU gate
  round-trips fp64→fp32→fp64, which captures fp32 *representation* loss only,
  not error accumulated inside a device fp32 forward pass. Measured CPU
  agreement is ~2.6e-8 rel-L2 against a 2e-2 bar; MPS computing the whole
  peak-chain in fp32 is expected to be far worse, and that is the number worth
  reporting. If the bars fail on MPS, that is a finding, not a bar to loosen
  without saying why.
- `column_agreement(J_ref, J_test)` in `linalg64.py` gives (worst rel-L2, worst
  cosine) with dead columns already skipped — reuse it.

From **WP-0404** (cross-backend Jacobian CI, landed 2026-07-24) — **the torch
row of the matrix is already written and self-skipping**, so most of the
"prove the op set is correct" work above is done for you:

- `tests/test_cross_backend.py` has a `"torch"` method row (and a
  `"torch+fp32"`-shaped seam via `_fp32_over`) that calls
  `pytest.importorskip("torch")` and then `_jacobian_for(model, table,
  "torch")`, skipping on the `ValueError: unknown backend`. **Adding the torch
  branch to `_jacobian_for` plus a `torch` extra in `pyproject.toml` activates
  it across every config at once** — the 18 analytic families, Le Bail with
  P-spline penalty rows, Pawley (aux block + restraint rows), the aniso/PO/
  extinction state, real srm660c/nac data, and the stacked multi-histogram
  layout. Add a `_fp32_over("torch")` entry to `METHODS` at the same time.
  Do not write a parallel torch-only agreement test; extend that matrix.
- **Expect the srm660c axial columns to disagree at the few-1e-3 level** and
  that is not your bug: the state starts at S/L == H/L, the FCJ quadrature-split
  kink, where right-sided, subgradient and central estimates legitimately
  differ. The matrix already applies WP-0402's loose bar (2e-2 / 0.9995) to
  exactly those two columns, and only when the state sits on the kink.
- **The FD reference in that file is central, not forward.** Forward
  differences sit 6.2e-3 from the analytic column on srm660c cell `a` — past
  the 5e-3 fp64 bar for pure truncation reasons. If you add a torch FD variant,
  make it central too.
- `_multi_closures(models, mtable, *, weights, backend)` now exists in
  `optimize/least_squares.py` (split out of `run_multi_least_squares`): it
  returns the stacked `(residual, jacobian, n_data_total)` without running a
  solve. That is how the multi-histogram row gets a torch Jacobian.
- The benchmark above stays out of this file: WP-0404's acceptance is
  correctness only, and its tests deliberately assert no wall-clock.

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

- [x] `[torch]` extra; `TorchBackend` on the 0401 op set (`window_add`/
      `segment_sum` via `index_add`; complex128 CPU / complex64 MPS); device
      and dtype selected by the WP-0403 policy
- [x] `torch.func.jacfwd`/`vmap` fp64-CPU Jacobian; add the torch row to the
      WP-0404 matrix
- [x] MPS fp32 forward + fp32 Jacobian columns crossing the `linalg64.py`
      fp64 host boundary
- [x] Wire `backend="torch"` through `refine.py`/`multi.py`; add the
      `uv pip install -e ".[dev,jax,torch]"` line to CLAUDE.md commands
- [x] `examples/bench_torch_mps.py`: MPS vs numpy wall-clock on 11-BM NAC and
      SRM 676a (reported)
- [x] Tests (`pytest.importorskip("torch")`): torch-fp64-CPU Jacobian
      agreement <5e-3 / cosine >0.99999; torch-MPS-fp32 SRM 676a refine
      matches the numpy `a` within 3e-5 Å; the numpy path is unaffected +
      obs/calc/diff PNGs to `tests/output/`

Deviation from the plan above, in one place only: the device is selected by a
second **backend name** (`"torch-mps"`), not by the WP-0403 policy object.
`MixedPrecisionPolicy` has one field, `jacobian_dtype`, and no device — and MPS
fp32 is not a policy choice but a hardware fact, so folding it into the policy
would have made "torch-mps at fp64" spellable. Two names keep it unspellable,
which is the same discipline the policy applies to the residual.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_backend_torch.py -q   # skips without torch
.venv/bin/python -m pytest tests/test_cross_backend.py -q   # the torch/torch+fp32 rows
.venv/bin/python examples/bench_torch_mps.py                # reports MPS vs numpy, not gated
```

**Measured (2026-07-27, Apple-silicon Mac, torch 2.13.0; 461 tests collected,
458 passed / 3 skipped, 38 `slow`, 7 min 19 s).**

*Correctness — the deliverable that held.* The torch fp64-CPU Jacobian clears
the WP-0404 fp64 bars (5e-3 rel-L2 / cosine 0.99999) on every config in the
matrix: the 18 analytic families, Le Bail with P-spline penalty rows, Pawley
with the aux block and restraint rows, aniso/PO/extinction, real srm660c and
nac data, and the stacked multi-histogram layout — with only the documented
S/L == H/L kink exception, unchanged. Worst column against the analytic
assembly: **2.7e-5 rel-L2** (`families`), cosine 1.0 to eight places. The Pawley
aux block agrees to <1e-9, as an exactly linear block must. `torch+fp32` clears
WP-0403's reduced bars on the same set.

*The fp32-column policy, on real hardware at last — and WP-0403's bar sizing
vindicated.* Columns computed entirely on the Apple GPU sit **4.0e-4 rel-L2 /
cosine 0.99999992** from the torch fp64 columns (worst over the four fast
configs; bars 2e-2 / 0.999). Compare WP-0403's CPU simulation of the same
policy, which round-trips fp64→fp32→fp64 and measured **2.6e-8**: real device
fp32 is *four orders of magnitude* worse, exactly as `backend/linalg64.py`
predicted in prose ("it does not reproduce error accumulated inside a device's
fp32 forward pass; that is strictly larger"), and still 50× inside a bar that
was deliberately "sized for the real device case". The prose can now cite a
number.

End to end, an MPS refinement of SRM 676a corundum lands **Δa = −3.5e-8 Å,
Δc = −4.6e-8 Å, ΔRwp = +5e-11** against numpy (bar: 3e-5 Å), with
c/a = 2.7299281 — the v0.3 record's value. For scale, torch *fp64* on CPU sits
further out (Δa = +3.0e-6 Å), so the spread across backends is dominated by
convergence-path differences, not by column precision. That is WP-0403's
argument, measured: the trust region re-measures every step against an fp64
cost, so reduced columns move the path and not the answer.

*Speed — a finding, not a speedup.* **MPS is 30-100× slower than numpy.**
Forward evaluation, best of 3: 11-BM NAC 2.0 ms (numpy) / 6.3 ms (torch CPU) /
199 ms (MPS); SRM 676a corundum with the axial aperture opened 6.2 / 14.2 /
480 ms. The cause is the loop shape, not the device: the residual walks ~130
frozen windows of 200-900 points one at a time in python, so each window is a
handful of kernel launches — tens of microseconds of dispatch against a
microsecond of arithmetic. No fp32 arithmetic recovers a 50× dispatch deficit.
The fix is a **batched peak loop** (one padded reflection × window tensor per
phase, which the frozen window layout already permits), and it is a change to
the forward model for every backend rather than to this one. Left undone
deliberately; recorded in DESIGN.md's locked decisions and pushed to WP-0601's
`### Inherited`.

## References

- [../DESIGN.md](../DESIGN.md#locked-decisions) — the no-Apple-fp64 hard
  constraint and the 2026-07-24 amendment moving `[torch]` into v0.4.
- Higham (2002) *Accuracy and Stability of Numerical Algorithms*, 2nd ed.,
  SIAM — why the solve stays fp64 (shared with WP-0403).
- `torch.func` (`jacfwd`, `vmap`) documentation.

## Handover log

- **2026-07-27** — **shipped.** Five commits; measured acceptance above. Done:
  `[torch]` extra, `TorchBackend` under two names, `torch.func.jvp` Jacobian,
  the WP-0404 `torch`/`torch+fp32` rows, `backend=` wiring through
  `refine.py`/`multi.py` (+ `Provenance.backend`/`dtype`, which had said
  "numpy/float64" since v0.1 regardless), `examples/bench_torch_mps.py`, and
  `tests/test_backend_torch.py`. Nothing in flight.

  **Gotchas, in the order they cost time** — every one is a torch-vs-numpy/jax
  difference the op shim did not anticipate, and all are now handled in
  `backend/api.py` or documented there:

  1. **torch ops take tensors only** (`torch.exp(ndarray)` raises), so every op
     coerces. Cheap; not the problem.
  2. **`ndarray ⊗ tensor` through a python operator.** `*`, `-`, `+` raise
     outright; `/` happens to work, which makes it look arbitrary. Worse,
     `tensor ⊗ ndarray` *silently* routes through numpy's deprecated
     `__array_wrap__` — fine on a plain tensor, hard failure under a functorch
     transform ("Cannot access data pointer of Tensor that doesn't have
     storage"). So the rule is stronger than "traced value on the left": a
     frozen numpy constant must not meet a traced value through a bare operator
     at all. Nine hot-path sites were lifted with `xp.matmul`/`xp.asarray`
     (both no-ops on numpy); the rule is in `backend/api.py`'s module docstring
     and now also in CLAUDE.md's Conventions, because it binds every future
     hot-path WP and an Inherited note in six of them would not.
  3. **`conj_physical` has no vmap batching rule** — torch silently falls back
     to a per-sample python loop over the whole structure factor (15× on
     `toy_rich`). `torch.conj(...).resolve_conj()` is the spelling that batches.
  4. **MPS: 1-D·1-D `matmul`** lowers to `aten::dot`, which asserts internally
     under a batching rule for every seed-block size except 3 (so a
     `chunk_size == matrix dim` probe hides it). Expanded in `matmul`.
  5. **MPS: `linalg.det`** decomposes into `solve_triangular`, whose batching
     rule broadcasts the vmap batch against the matrix dimension. `linalg.inv`
     on the same device is fine. `_TorchLinalg.det` is the 3×3 cofactor
     expansion — the only matrices this vocabulary sees are metric tensors.
  6. **MPS: a 0-d dual tensor cannot be combined with a python float** under
     `torch.func.jvp` — `x[0] * 2.0` raises `TypeError` even though
     `torch.result_type` reports fp32; the dispatch tries to materialise an fp64
     MPS tensor. Every decoded parameter is 0-d and meets literals constantly
     (`0.5 * tt`, `s/R`, `2.0 * min(s, h)`), so patching call sites would have
     scattered a device workaround through the physics code and re-broken on the
     next obvious line. Instead `scalar_tensor_class()` is a 0-d `Tensor`
     subclass that lifts python scalars, and the MPS instance guarantees every
     0-d value it produces is of that type (`TorchBackend.scalarize`, applied to
     all of `_OP_NAMES`, plus the decode, which produces 0-d by indexing rather
     than by an op). It is **shed at the first array-valued result**, so no
     `__torch_function__` hop lands in front of the hot loop. The CPU instance
     carries none of this — `self._scalar is None` there.

  **Next**, for whoever picks up v0.4: 0405/0406/0407 remain. Nothing in this WP
  blocks them; the forward-references they need are in their `### Inherited`
  sections. The one thing left undone *here* is the batched peak loop — see
  WP-0601's `### Inherited` and DESIGN.md's dated measurement.
- **2026-07-22** — created as a stub (WP-0603, v0.6) from the ROADMAP split.
- **2026-07-24** — **moved to WP-0408 / v0.4** and expanded (v0.4 planning
  session). Rationale: the maintainer wants local GPU acceleration, which
  jax cannot provide on Apple hardware; sequencing after 0402+0404 preserves
  the one-autodiff-backend-at-a-time discipline. Strategy decided: torch
  accelerates the forward on MPS fp32 under the 0403 policy, with
  `torch.func.jacfwd` on CPU fp64 as the agreement cross-check; benchmark
  reported, not gated.

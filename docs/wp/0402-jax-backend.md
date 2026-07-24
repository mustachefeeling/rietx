# WP-0402 — JAX backend: chunked jacfwd Jacobians

Milestone: v0.4 · Status: ⬜ not started
Depends on: WP-0401

## Goal

The 0401-shimmed forward model running under a `JaxBackend` with
jit-compiled evaluation and a chunked `jacfwd` Jacobian that reproduces the
analytic/FD columns within tolerance — fp64 on host, without ever touching
jax's global x64 flag at import.

## Context

- [../DESIGN.md](../DESIGN.md#locked-decisions) — backend decision; jax-metal
  is abandoned, no Apple-GPU fp64 anywhere ⇒ jax fp64 is **CPU-only** here.
  The win is exactness + jit, not GPU (GPU is WP-0403/0408).
- [../DESIGN.md](../DESIGN.md#architecture-invariants) — frozen-per-stage
  discreteness is what makes the residual traceable at all; nothing
  data-dependent may enter the graph. The forward model was written
  differentiable from day one (no clamps, smooth reparameterisations,
  quadrature split at the FCJ kink) — jacfwd correctness is the payoff.
- `jacfwd` cost ≈ N_params × forward (one tangent per column) — same order
  as FD, but exact and jit-compiled.

### Design (decided)

- **fp64 mechanism: scoped x64, never at import.** Wrap the jacfwd/jit call
  sites in `jax.experimental.enable_x64()` (context manager — re-entrant,
  cannot leak into a numpy-only user's process). The alternative
  (`jax.config.update("jax_enable_x64", True)` inside `set_backend("jax")`
  with teardown) is simpler but stateful; if the context manager proves
  incompatible with jit caching in practice, fall back to the activation-time
  update and document the scope. Either way: a unit test asserts a numpy-only
  process never sees the flag set.
- **Chunked jacfwd.** Chunk over the *parameter* axis: `vmap` over blocks of
  one-hot tangent seeds, default `chunk_size = 32` (peak memory ≈
  chunk × n_data × 8 B ≈ 1.3 MB at 5·10³ points — bounded), overridable.
  `jit` the residual once per stage with the frozen compiled state
  (windows, hkl, node counts, design matrix) **closed over as constants**
  (legal per frozen-per-stage discreteness); only θ is traced. One XLA
  executable is reused across chunks.
- **`table.decode` under the trace.** Transforms (softplus/logit) are
  elementwise `xp` ops. The affine constraint block `p = C·θ + d`:
  materialise the scipy.sparse `C` **dense** at activation
  (`jnp.asarray(C.toarray())`) as a closure constant — a constant matmul,
  exact under autodiff (`params/vector.py` promises exactly this).
- **Pawley / Le Bail.** Pawley θ = `[table θ | per-hkl I]`; after the
  WP-0401(a) functional-intensity refactor the combined θ traces cleanly, and
  jacfwd must reproduce the exact linear intensity columns (a built-in
  correctness cross-check). Le Bail's `lebail_update` is an *outer*
  intensity-partitioning iteration that runs **between** residual evals — it
  stays numpy and is not traced; the jax path differentiates the residual at
  fixed extracted intensities, exactly as the analytic Jacobian does today.
- **What stays numpy (host):** `compile_model`, the scipy TRF driver,
  `covariance_estimates`, all statistics. jax produces the Jacobian *array*;
  the fp64 host consumes it. The produced layout must match
  `_make_jacobian`'s exactly: data rows, then background-penalty rows, then
  Pawley-restraint rows.
- **Packaging/wiring:** optional `[jax]` extra in `pyproject.toml`; lazy
  import inside `set_backend("jax")` so import never affects numpy-only
  users; flip the `backend="jax"` `NotImplementedError` in
  `refine.py`/`multi.py` to dispatch a jax Jacobian callable into
  `run_least_squares` (residual for cost/statistics and the solve stay
  numpy fp64).

## Non-goals

CUDA/mixed-precision policy (WP-0403); torch (WP-0408); making the TRF driver
or statistics jax-aware.

## Tasks

- [ ] `[jax]` extra in `pyproject.toml`; `JaxBackend` in `backend/api.py`
      (lazy import; numpy-only users unaffected); add the
      `uv pip install -e ".[dev,jax]"` line to CLAUDE.md commands
- [ ] Scoped x64 at the jacfwd/jit sites; unit test that a numpy-only
      process never sees `jax_enable_x64`
- [ ] jit-ed residual with frozen state closed over; dense-`C` constant
      matmul for `decode`
- [ ] Chunked jacfwd (vmap over one-hot seed blocks, default 32) returning
      the fp64 host Jacobian in `_make_jacobian`'s row/column layout
- [ ] Wire `backend="jax"` through `refine.py`/`multi.py` into
      `run_least_squares`
- [ ] Tests (`pytest.importorskip("jax")`): jacfwd vs analytic vs FD on the
      18 `ANALYTIC_FAMILIES` + Pawley linear columns (<5e-3 rel,
      cosine >0.99999); SRM 660c end-to-end under `backend="jax"` matches the
      numpy `a` within 1e-6 Å + obs/calc/diff PNGs to `tests/output/`

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_backend_jax.py -q   # skips without jax
.venv/bin/python -m pytest tests/test_v02_core.py -q
```

Measured: jax jacfwd agrees with the analytic Jacobian to <5e-3 rel-L2 /
cosine >0.99999 on every family; a full SRM 660c refine under
`backend="jax"` matches the numpy `a` to ≤1e-6 Å.

## References

- JAX documentation: `jacfwd`, `jit`, `experimental.enable_x64` (mechanism,
  no paper).
- Nocedal & Wright (2006) *Numerical Optimization* — forward-mode
  cost-per-column ≈ one forward evaluation.

## Handover log

- **2026-07-22** — created as a stub from the ROADMAP split.
- **2026-07-24** — expanded from stub (v0.4 planning session): scoped-x64
  mechanism, chunk-over-columns jacfwd (32), dense-C decode, Pawley/Le Bail
  interaction and the numpy/jax split decided.

# WP-0404 — Cross-backend Jacobian-agreement CI

Milestone: v0.4 · Status: ⬜ not started
Depends on: WP-0402

## Goal

A test matrix proving that analytic, FD, jax-jacfwd, torch-fp64-CPU and
fp32-column-policy Jacobians agree — including across stage boundaries and in
Rietveld/Le Bail/Pawley single- and multi-histogram modes — so backend drift
is caught the day it happens, not the day it ships a wrong esd. Green with
and without the optional backends installed.

## Context

- [../DESIGN.md](../DESIGN.md#risks--mitigations) — "backend drift → small op
  vocabulary + mandatory cross-backend tests"; this WP is that mitigation.
- The v0.2 harness to extend, not replace:
  `tests/test_v02_core.py::test_analytic_jacobian_matches_fd` — 18
  `ANALYTIC_FAMILIES` paths on a lab Bragg-Brentano state (Kα doublet + FCJ +
  displacement/transparency), per-column rel-L2 <5e-3, cosine >0.99999, FD
  step `1e-6·max(1,|θ|)`. `tests/test_jacobian.py::_check_columns` is the
  coordinate/ADP-DOF variant with the same tolerances.

### Design (decided)

- **The matrix.** Methods × configs, parametrized in one
  `tests/test_cross_backend.py`:
  - Methods: analytic, FD, jax-jacfwd fp64 (WP-0402), torch-jacfwd fp64-CPU
    (row added when WP-0408 lands), fp32-column policy (WP-0403).
  - Configs: the 18 `ANALYTIC_FAMILIES`; Pawley exact linear intensity
    columns; Le Bail (fixed extracted intensities); single- and
    multi-histogram (stacked layout from `run_multi_least_squares`);
    stage-boundary regeneration cases.
- **Tolerances, centralized as module constants:** fp64 methods <5e-3
  rel-L2 / cosine >0.99999 (v0.2 style); fp32 columns <2e-2 / cosine >0.999
  (fp32 carries ~7 significant digits; a column near a cancellation loses
  2–3 more — a wrong *direction* is still caught by the cosine, and the
  stricter parameter-level gate lives in WP-0403's acceptance).
- **Stage-boundary is the headline case** (frozen-state regeneration between
  stages is where discreteness bugs surface): run a 3-stage SRM 660c plan;
  at each recompile assert Jacobian continuity `‖J_after − J_before‖/‖J‖ <
  1e-6` at the shared parameter values. Cover Rietveld, Le Bail and Pawley.
- **Runs without extras.** Backend-specific rows use
  `pytest.importorskip("jax")` / `importorskip("torch")` (the established
  pattern — see `tests/test_pawley.py`); the analytic-vs-FD core always
  runs, so a numpy-only checkout stays green. The full matrix runs after
  `uv pip install -e ".[dev,jax,torch]"`. GitHub Actions wiring is
  deliberately deferred to WP-1002 (no `.github/` exists yet) — acceptance
  here is pytest-command-based.

## Non-goals

CI-service configuration (WP-1002); performance benchmarking (reported in
WP-0402/0408); esd-value assertions (WP-0407 owns the esd path).

## Tasks

- [ ] `tests/test_cross_backend.py`: parametrized (method × config) matrix;
      analytic-vs-FD always-on; jax/torch/fp32 rows `importorskip`-gated;
      tolerance constants centralized
- [ ] Stage-boundary continuity cases (3-stage SRM 660c; Rietveld + Le Bail
      + Pawley)
- [ ] Multi-histogram stacked-Jacobian agreement (via
      `run_multi_least_squares` layout)
- [ ] Document the extras invocation (`uv pip install -e ".[dev,jax,torch]"`)
      in this file and CLAUDE.md once the extras exist

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_cross_backend.py -q   # numpy-only: analytic vs FD
# after: uv pip install -e ".[dev,jax,torch]"
.venv/bin/python -m pytest tests/test_cross_backend.py -q   # full matrix
```

Measured: all fp64 methods agree <5e-3 / >0.99999 on every config; the
fp32-column method agrees <2e-2 / >0.999; stage-boundary Jacobian continuity
<1e-6; the file is green both with and without the extras installed.

## References

No new physics — this WP is the DESIGN.md risk mitigation made concrete. The
tolerance style is the measured v0.2 harness.

## Handover log

- **2026-07-22** — created as a stub from the ROADMAP split.
- **2026-07-24** — expanded from stub (v0.4 planning session): matrix,
  centralized tolerances (fp64 5e-3/0.99999, fp32 2e-2/0.999),
  stage-boundary continuity test and the extras-gated execution model
  decided; torch row lands with WP-0408.

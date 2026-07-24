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

### Inherited from upstream WPs (added 2026-07-24, after 0402 and 0403 landed)

This section exists because the session protocol forbids reading other WP
files — anything 0402/0403 learned that changes work *here* has to be
restated here or it is lost.

- **Import the fp32 bars, do not restate them.** WP-0403 exports
  `COLUMN_REL_L2_MAX = 2e-2` and `COLUMN_COSINE_MIN = 0.999` from
  `pxrdref.backend.linalg64`, together with
  `column_agreement(J_ref, J_test) -> (worst rel-L2, worst cosine)`, which
  already skips transform-floor-dead columns. Re-declaring those numbers in
  `tests/test_cross_backend.py` would be the exact drift this WP exists to
  catch. (The fp64 bars 5e-3 / 0.99999 have no home yet — declare those here.)
- **Driving the fp32-column row.** It is not a backend; it is a policy over
  whichever backend built the columns:
  `with precision_policy(FP32_JACOBIAN): J32 = _jacobian_for(model, table, be)(theta)`.
  So it composes with the numpy *and* jax rows rather than being a row of its
  own, and it needs no `importorskip` — it runs on a numpy-only checkout.
- **Do not tighten the fp32 bars to the measured CPU numbers.** The CPU
  simulation round-trips fp64→fp32→fp64, which reproduces fp32
  *representation* loss only, not error accumulated inside a device fp32
  forward pass. Measured agreement is ~2.6e-8 rel-L2 against the 2e-2 bar;
  that six-order margin is an artifact of the simulation, and the bars are
  sized for the real hardware WP-0408 brings. Tightening them would make the
  torch-MPS row fail for the wrong reason.
- **The FCJ S/L == H/L kink needs a loose bar (from 0402).** At axial
  S/L = H/L the quadrature split point ξ_kink = |S/L − H/L| sits at its own
  non-differentiable zero, so analytic node-FD (right-sided), jax
  (sign(0) = 0 subgradient) and central FD legitimately differ by ~3e-3.
  Not a bug. The `srm660c` shim state *starts* at exactly that point, so its
  two axial columns carry a documented 2e-2 loose bar in
  `test_backend_jax.py::_column_agreement`; reuse that convention here.
  States built for FD comparison (`_lab_state`, `toy_rich`) use unequal
  ratios on purpose.
- **The multi-histogram jax row was deferred *to this WP* (from 0402).** 0402
  deliberately shipped no jax test for `MultiHistogramRefinement` — the wiring
  is shared via `_jacobian_for`, so a dedicated test there would have doubled
  jit-compile cost for no new code path. This WP's stacked-layout task is its
  intended home.
- **Reusable state builders.** `tests/test_acceptance_srm660c.py` exposes
  `build_srm_inputs()` (extracted by 0402 for exactly this reason), and
  `tests/test_backend_shim.py` exposes `STATES` — `srm660c`, `nac`,
  `toy_lebail`, `toy_pawley`, `toy_rich`, each returning
  `(model, table, extras)` at a compiled expansion point.
- **Budget jit compile, not flops.** jax's per-stage jit compile is ~1-4 s and
  dominates toy-sized runs; parametrizing the matrix finely over jax configs
  costs compile time, not compute.
- **The Goal above overpromises: multi-histogram Le Bail and Pawley cells do
  not exist.** WP-0308 shipped multi-histogram as Rietveld-only, with an
  explicit `NotImplementedError` in `multi.py` — "Le Bail / Pawley intensities
  are per-pattern extractions, not shared, so a joint fit of them is just
  independent single-pattern fits". So the matrix is (Rietveld × {single,
  multi}) + ({Le Bail, Pawley} × single). Shrink the Goal sentence rather than
  growing scope this WP does not own.
- **Pawley is not the same comparison as Rietveld** (from 0306). Its Jacobian
  differentiates the *augmented* residual — extra overlap-restraint rows below
  the data and background-penalty rows — over θ = [table θ | per-hkl
  intensities], and `LSQOutcome` hides that tail behind `n_aux` while returning
  table-only columns. Compare the full augmented array from `_jacobian_for`,
  not the outcome's `jac`. The intensity columns are exact analytic
  (`−√w·Σ_lines w_line·Ω`), never FD, so they should agree to round-off — a
  loose bar there is hiding something.
- **Reuse the five-state golden corpus, don't build new states** (from 0401).
  `tests/data/backend_goldens/` already pins SRM 660c, NAC, toy Le Bail (with
  P-spline penalty rows), toy Pawley (pseudo-cubic cell so overlap-restraint
  rows exist) and a toy with aniso + PO + extinction + displacement/
  transparency all *nonzero*. They are environment-pinned; re-baseline only
  via the documented rule in `tests/data/README.md`.
- **Extinction is off by default, and that hides a real Jacobian trap** (from
  WP-0506). The analytic `dof`/`adp` columns carry a factor `G = E + x·dE/dx`
  (`model/forward.py`), and if it is wrong the columns disagree with FD **only
  when `ext ≠ 0`**. Every default-state comparison would pass. The `toy_rich`
  golden state has extinction nonzero — use it, or the matrix is blind here.
- **FCJ columns routed to FD are out of scope by decision** (from 0401): when
  `axial_ok=False` the axial columns fall back to FD, and autodiff correctness
  *at* that discontinuity was explicitly declared out of scope. Exclude or
  specially tolerate those cells rather than treating a mismatch as drift.

### Design (decided)

- **The matrix.** Methods × configs, parametrized in one
  `tests/test_cross_backend.py`:
  - Methods: analytic, FD, jax-jacfwd fp64 (WP-0402), torch-jacfwd fp64-CPU
    (row added when WP-0408 lands), fp32-column policy (WP-0403 — a policy
    layered over the numpy/jax rows, not a backend of its own; see Context).
  - Configs: the 18 `ANALYTIC_FAMILIES`; Pawley exact linear intensity
    columns; Le Bail (fixed extracted intensities); single- and
    multi-histogram (stacked layout from `run_multi_least_squares`);
    stage-boundary regeneration cases.
- **Tolerances, centralized as module constants:** fp64 methods <5e-3
  rel-L2 / cosine >0.99999 (v0.2 style) — declare these here; fp32 columns
  <2e-2 / cosine >0.999 — **import** these from `backend.linalg64` as
  `COLUMN_REL_L2_MAX` / `COLUMN_COSINE_MIN` (WP-0403 owns them; see Context).
  The fp32 rationale: fp32 carries ~7 significant digits and a column near a
  cancellation loses 2–3 more — a wrong *direction* is still caught by the
  cosine, and the stricter parameter-level gate lives in WP-0403's acceptance.
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

- [x] `tests/test_cross_backend.py`: parametrized (method × config) matrix;
      analytic-vs-FD and fp32-column always-on (the fp32 policy needs no
      extra); jax/torch rows `importorskip`-gated; fp64 tolerance constants
      declared here, fp32 bars imported from `backend.linalg64`
- [x] Stage-boundary continuity cases (3-stage SRM 660c; Rietveld + Le Bail
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
- **2026-07-24 (from the 0403 session, not yet started here)** — added the
  "Inherited from upstream WPs" Context block. 0402 and 0403 both landed
  facts that change the work here (the fp32 bars now exist as importable
  constants; the fp32 row is a policy, not a backend; the FCJ kink needs a
  loose bar; the multi-histogram jax test was deferred *to* this WP), and the
  session protocol forbids reading their files — so they are restated above.
  The Design tolerance bullet previously said to declare the fp32 bars
  locally; that would have duplicated `linalg64`'s exports, which is the very
  drift this WP exists to catch. Corrected.

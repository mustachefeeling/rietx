# WP-0401 — Backend op shim (+ residual purity refactors)

Milestone: v0.4 · Status: ✅ 2026-07-24
Depends on: —

## Goal

A small (~41-op) backend namespace (`backend/api.py`) plus numpy-semantics-
preserving purity refactors, so the forward model, structure factor, lattice
and profile code run through `xp.*` instead of bare `np.*` — identical
numbers on numpy today, traceable by jax (WP-0402) and torch (WP-0408)
without per-call branching.

## Context

- [../DESIGN.md](../DESIGN.md#locked-decisions) — backend decision, the fp64
  constraint, one autodiff backend at a time.
- [../DESIGN.md](../DESIGN.md#risks--mitigations) — "backend drift → small op
  vocabulary + mandatory cross-backend tests (WP-0404)". Every op added is a
  per-backend maintenance liability; keep the vocabulary minimal.
- The seams are already half-built: `src/pxrdref/backend/` exists (empty, the
  home for `api.py`), and a `backend: str = "numpy"` kwarg is threaded through
  [`refine.py`](../../src/pxrdref/refine.py) (~line 58),
  [`multi.py`](../../src/pxrdref/multi.py) (~line 73) and
  [`schemas/common.py`](../../src/pxrdref/schemas/common.py) (~line 109), each
  raising `NotImplementedError` for non-numpy. WP-0402/0408 flip that switch;
  this WP builds what they flip to.
- `params/vector.py` (comment at top) already keeps constraints as a matmul
  "so it stays exact under the future autodiff backends".

### Architecture (decided)

- **Namespace object, not a function registry.** `backend/api.py` defines a
  `Backend` protocol and a concrete `NumpyBackend` whose attributes *are*
  numpy functions (zero overhead — the numpy path cannot regress), plus
  `set_backend()`/`get_backend()`. Hot-loop code binds `xp = get_backend()`
  **once per compiled-model call**, never per op (matches the "compile once
  per stage" invariant; no per-call branching).
- **`window_add(y, i0, i1, vals)` is THE scatter primitive.** The residual
  only ever does *contiguous frozen-window* accumulation
  (`y[i0:i1] += intensity·prof` — `model/forward.py` `phase_component`/
  `lebail_update`, and the Jacobian column assembly in
  `optimize/least_squares.py`). `(i0, i1)` are python ints frozen at stage
  compile → legal **static** slice bounds under jax. Do NOT provide a general
  index-array scatter: it is more than the model needs and invites
  data-dependent indices into the graph, which frozen-per-stage discreteness
  exists to forbid. **Functional signature** — returns the updated array
  (jax arrays are immutable); the numpy impl may mutate internally but
  callers thread `y = xp.window_add(y, i0, i1, vals)`.
- **`segment_sum(vals, seg_ids, n)` replaces `np.bincount`** (the March-
  Dollase orbit mean in `model/preferred_orientation.py`): numpy impl =
  `bincount(weights=…)`, jax = `jax.ops.segment_sum`, torch = `index_add`.
- **Complex stays first-class.** The structure factor is complex128-heavy;
  the shim needs a complex-capable `exp` plus `conj`/`real`/`imag`.
  complex128 on host/CPU; complex64 only under the WP-0403 fp32 policy.
- **The op list (~41), enumerated from the measured trace:** elementwise
  `exp` (complex-capable), `sqrt`, `log`, `sin`, `cos`, `tan`, `arcsin`,
  `arccos`, `radians`, `degrees`, `abs`, `sign`, `power`, `clip`, `maximum`,
  `minimum`, `where`; reductions/linalg `einsum` (five signatures:
  `"nk,mkc->mnc"`, `"mnc,cd,mnd->mn"`, `"ni,ij,nj->n"`, `"mi,ij,mj->m"`,
  `"i,in->n"`), `matmul`, `sum`, `cumsum`, `diff`, `linalg.inv` (3×3),
  `linalg.det` (3×3); construction `asarray`, `zeros`, `zeros_like`,
  `full_like`, `concatenate`, `stack`; complex `conj`, `real`, `imag`;
  scatter `window_add`, `segment_sum`; constant `pi`. **No `scipy.special`**
  — the hot path has none today; the WP-0405 Faddeeva is built *on* this op
  set, so leave room but implement nothing for it here.
- **What stays numpy (never shimmed):** everything in `compile_model`
  (searchsorted window edges, leggauss nodes, BSpline design matrix,
  Chebyshev recursion, overlap grouping), the scipy TRF driver,
  `covariance_estimates`, all of `optimize/statistics.py`.

### Purity refactors (folded in here — prerequisites for ANY autodiff backend)

All are numpy-semantics-preserving (identical numbers), gated by the full
existing suite:

- **(a) Functional intensity threading.** `set_pawley_intensities`
  (`optimize/least_squares.py`, residual closure) and `lebail_update`
  (`model/forward.py`) mutate per-phase `hkl_intensity` buffers mid-residual.
  Refactor so `phase_peaks`/`evaluate` receive the intensity vector as an
  argument, never from a mutated buffer. The one non-trivial refactor; the
  hard prerequisite for tracing Pawley/Le Bail under jax.
- **(b) θ-branches → unconditional evaluation.** `if s != 0.0` /
  `if t != 0.0` (displacement/transparency, `model/forward.py`) and
  `if ext != 0.0` (six sites) branch on values decoded from θ — under jacfwd
  these are tracers and the branches cannot stay. Every off-value is an exact
  identity (shift = 0, E ≡ 1, P ≡ 1), so unconditional evaluation is
  numerically safe. Keep `if P is not None` — that is a *compile-time
  structural* choice (frozen state), which is legal; only the *value*
  branches go.
- **(c) `isfinite(pos)` masking.** `if i1 <= i0 or not np.isfinite(pos_k)`
  (`model/forward.py`, two sites): `i1 <= i0` is frozen (fine);
  `isfinite(pos)` is θ-dependent → reformulate as a `where`/multiply mask so
  a non-finite position contributes exactly zero without a python branch.
- **(d) FCJ fallback as `where`.** The `sl <= 0 or hl <= 0` / `total <= 0`
  early returns to the symmetric image (`model/profiles/fcj.py`) guard a
  genuine parameterisation discontinuity. Express the fallback as `where` so
  the traced path is branchless; `axial_ok=False` already routes those
  Jacobian columns to FD, so autodiff correctness *at* the discontinuity is
  out of scope.

Modules to route through `xp`: `crystallography/{structure_factor,lattice,
scattering}.py`, `model/profiles/{pseudovoigt,fcj,caglioti}.py`,
`model/{corrections,extinction,preferred_orientation}.py`, and
`model/forward.py` (`evaluate`/`phase_peaks`/`phase_component` via
`window_add`).

## Non-goals

The jax backend itself (WP-0402); torch (WP-0408); any x64/precision policy
(WP-0403); Faddeeva/`wofz` (WP-0405). Nothing here may change a single
computed number on the numpy path.

## Tasks

- [x] `backend/api.py`: `Backend` protocol + `NumpyBackend` (attributes =
      numpy funcs), `set_backend`/`get_backend`, the ~41-op vocabulary;
      `window_add` + `segment_sum` numpy impls
- [x] Route `crystallography/{structure_factor,lattice,scattering}.py`
      through `xp` (einsum/exp/conj/real/inv/det)
- [x] Route `model/profiles/{pseudovoigt,fcj,caglioti}.py` and
      `model/{corrections,extinction,preferred_orientation}.py` through `xp`
      (`segment_sum` replaces `bincount`)
- [x] Route `model/forward.py` accumulation through `window_add`
      (functional threading of `y`)
- [x] Purity refactor (a): thread Pawley/Le Bail intensities functionally
- [x] Purity refactors (b)+(c)+(d): unconditional off-value evaluation,
      `where`-masks (numbers unchanged — assert bit-identity in tests)
- [x] Tests: `tests/test_backend_shim.py` — numpy backend bit-identical
      (`np.array_equal`) to pre-refactor golden `evaluate`/Jacobian arrays on
      the SRM 660c and NAC states; full suite green unchanged + obs/calc/diff
      PNGs to `tests/output/`

## Acceptance

Full existing suite green with zero numeric change, plus the shim-identity
test:

```sh
.venv/bin/python -m pytest -q
.venv/bin/python -m pytest tests/test_backend_shim.py -q
.venv/bin/python -m ruff check src tests examples
```

## References

- Thompson, Cox & Hastings (1987) J. Appl. Cryst. 20, 79 — TCHZ pseudo-Voigt
  (the profile the op set must reproduce).
- Finger, Cox & Jephcoat (1994) J. Appl. Cryst. 27, 892 — FCJ axial
  divergence (the branchless-fallback target).

## Handover log

- **2026-07-22** — created as a stub from the ROADMAP split.
- **2026-07-24** — expanded from stub (v0.4 planning session): op-shim
  architecture decided (namespace object, `window_add`/`segment_sum`
  primitives, ~41-op list enumerated from a code survey), purity refactors
  (a)–(d) folded in as numpy-identical commits.
- **2026-07-24 (later)** — **done.** All tasks landed as seven commits
  (`9e769ff…3db6d25`). Acceptance measured: full suite **363 passed** with
  zero numeric change (bit-identity goldens all pass), `ruff` clean,
  obs/calc/diff PNGs visually checked (SRM 660c Rwp 8.66 %, NAC Rwp 9.31 % —
  unchanged).
  - **Goldens beyond the WP ask**: five states, not two — SRM 660c, NAC, plus
    toy Le Bail (+P-spline penalty rows), toy Pawley (pseudo-cubic cell so
    overlap-restraint rows exist), and a toy with aniso+PO+extinction+
    displacement/transparency all *nonzero* (gates the on-values). Captured
    pre-refactor at `c9fc8c0`; environment-pinned npz under
    `tests/data/backend_goldens/` (provenance + re-baseline rule in
    `tests/data/README.md`; regenerate via
    `python -m tests.test_backend_shim` only from a green tree).
  - **Extra modules routed**: `adp.reciprocal_axis_lengths` +
    `adp.ustar_from_ucif` (both on the θ chain via `_site_values`/aniso DW),
    and the caglioti `gauss_size` branch folded into (b) — all θ-value
    branches in the residual path are gone, not just the listed ones.
  - **One deliberate deviation from (c)**: `derivative_bases` (forward.py)
    keeps its `isfinite` python skip.  It is host-side Jacobian support,
    never traced (an autodiff backend differentiates the residual, not the
    analytic-column machinery), and mask-converting it would let NaN
    structural/PO intensity-gradient columns (Lp of a NaN position) reach
    `window_add`.  The residual-path masking lives in `_reflection_profile`
    (where-mask at a safe position) + `phase_peaks` (zeroes the matching
    intensity — NaN·0 protection).
  - **API changes**: `pawley_restraint_residual(vec)` now takes the intensity
    vector; new `CompiledModel.split_pawley_intensities`;
    `set_pawley_intensities` is the single post-solve commit;
    `evaluate`/`phase_peaks`/`derivative_bases` grew optional intensity args
    (buffers = storage at rest for plots/exporters/replay/history);
    `cell_volume` returns a 0-d fp64 scalar (np.float64 subclasses float, so
    QPA/pydantic are unaffected).
  - **Gotchas for WP-0402**: (1) compile-time code (`fcj_extent_deg`,
    node sizing) shares `_xi_max`, which is xp-routed — set the non-numpy
    backend only *around the solve*, or `np.asarray` at the compile boundary,
    so frozen state stays host numpy.  (2) The FCJ fallback `ok` predicate
    and the one-hot fallback weights assume `n_nodes` (hence shapes) frozen —
    true by construction.  (3) `isfinite` was added to the op vocabulary
    (needed by (c)); the shim ended at 37 named ops + `linalg.inv/det` + `pi`.

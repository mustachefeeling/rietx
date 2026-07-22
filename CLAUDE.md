# CLAUDE.md — pxrd-refine

API-first Rietveld refinement package (powder XRD). MIT. numpy/scipy fp64
core, pydantic v2 schemas, gemmi for CIF/symmetry. Import name: `pxrdref`.

## Commands

```sh
uv venv --python 3.12 && uv pip install -e ".[dev]"   # setup (once)
.venv/bin/python -m pytest                             # full suite ~5 s, incl. real-data acceptance
.venv/bin/python -m pytest -m "not slow"               # skip acceptance
.venv/bin/python -m ruff check src tests examples      # lint (must be clean)
.venv/bin/python examples/nac_11bm.py                  # end-to-end demo + plot
```

## Data flow

```
Structure/Instrument/PatternData (schemas/, pydantic, JSON round-trip)
  → ParameterTable (params/vector.py): tree → flat fp64 θ, dot-paths
    ("phases.0.cell.a", "instrument.profile.w", "instrument.background.c2"),
    crystal-system cell ties (b←a etc.), softplus/logit transforms
  → CompiledModel (model/forward.py): per-stage frozen state — reflection list
    (crystallography/symmetry.py, gemmi), per-atom symmetry-op subsets
    (structure_factor.py), per-reflection point windows, Chebyshev design matrix
  → run_least_squares (optimize/least_squares.py): scipy TRF, bounds, mixed
    analytic/FD Jacobian, esds from χ²·(JᵀJ)⁻¹
  → staged runner (strategy/staged.py) loops stages, guards, recompiles
  → RefinementResult (schemas/results.py) → FitReport (report.py) / plot (viz/)
```

Entry points: `Refinement.fit()` / `refine()` in `refine.py`; modes
`"rietveld"` and `"lebail"` (Le Bail intensity partitioning lives in
`CompiledModel.lebail_update`).

## Invariants (do not break)

- **Frozen-per-stage discreteness**: the hkl list, symmetry-op subsets, FCJ
  quadrature (future), and window index ranges are computed at stage compile
  and NEVER change during a least-squares run; regenerate only between stages.
  This keeps the residual smooth for FD/autodiff Jacobians.
- **fp64 everywhere** in the core; future GPU backends may compute Jacobian
  *columns* in fp32 but the residual used for cost/statistics and the solve
  stay fp64 on host.
- **No pydantic in the hot loop**: `ParameterTable.decode()` returns a plain
  dict; the forward model consumes floats/arrays only.
- **Weights**: use the file's esd column when present (readers), Poisson
  √max(y,1) only as fallback. Never subtract an estimated background —
  hold it additively (`BackgroundFixedPlusChebyshev`).
- **Reciprocal-space symmetry action is Rᵀ** (transposed rotation) — matters
  for non-cubic orbit/multiplicity counting (see symmetry.py comment).
- **Every physics function cites its reference** (author, year, journal) in
  the docstring, and documents conventions by physics not letters (e.g.
  size↔1/cosθ, strain↔tanθ; GSAS and FullProf swap X/Y labels).
- **Licensing**: port code only from permissive sources with ATTRIBUTION.md
  updates. BGMN/Profex/xrayutilities are GPL — concepts only, never code.
  TOPAS/FullProf are closed — papers only.

## Conventions

- Parameter paths are dot-separated, glob-matched with fnmatch in stage plans
  (`"phases.*.cell.*"`). No brackets in paths (fnmatch treats `[..]` as class).
- Schemas: `extra="forbid"`, `ser_json_inf_nan="strings"` (±inf bounds must
  survive JSON round-trip — tested).
- Angles in degrees throughout; Caglioti U,V,W in deg²(2θ); Biso in Å²
  (= 8π²·Uiso); wavelengths in Å; k = sinθ/λ.
- v0.1 limitation: atomic-coordinate refinement raises NotImplementedError
  (needs Wyckoff-aware constraints, v0.2). Occ/Biso refinement is fine.
- Tests: fast unit/property tests always; real-data acceptance marked
  `@pytest.mark.slow` (`tests/test_acceptance_nac.py`, ~3 s). Reference
  values and data provenance in `tests/data/README.md`.

## Roadmap (abridged; full plan was reviewed adversarially)

- **v0.2**: lab Bragg-Brentano — Kα1/Kα2 per-line dispersion (refinable
  ratio), Finger-Cox-Jephcoat axial asymmetry (fixed-node quadrature),
  sample displacement/transparency, instrument⊕sample profile split,
  background auto-selection (BIC + Durbin-Watson), P-spline co-refined
  background (smoothness penalty as extra residual rows), analytic cell→2θ
  and width Jacobian columns, FitReport Layers 1-2 (gated derivative-basis
  misfit attribution + typed suggested_actions with strategy-engine veto),
  plotly HTML viewer + live watch + event stream. Acceptance: NIST SRM 660c
  LaB6 CuKα certification profiles (already in tests/data/).
- **v0.3**: QPA (Hill-Howard + Brindley), Pawley mode, aniso ADPs +
  Wyckoff constraints (spglib), multi-histogram residuals.
- **v0.4**: JAX backend via a small op shim (chunked jacfwd, CUDA, mixed
  precision). **v0.6**: TOPAS-style bounded LM (Coelho 2005/2018), torch-MPS.
- v2: FPA (differentiable convolution stack), neutron/TOF, texture, MCP server.

Key test data: `tests/data/11BM_NAC.fxye` (synchrotron, λ=0.4139090 from the
.prm; NAC + CaF₂ impurity — the acceptance expects a≈10.2513, Rwp<0.12) and
`tests/data/nist_srm660c_100a.cif` (NIST LaB6 certification profile with
CuKα doublet — reserved for v0.2).

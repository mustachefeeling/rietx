# WP-1003 — API freeze + PyPI release

Milestone: v1.0 · Status: ⬜ not started (stub — expand before starting)
Depends on: WP-1001, WP-1002

## Scope (carried verbatim from the pre-split roadmap)

- API freeze, PyPI release (name `pxrd-refine` verified available)

## Inherited

From **WP-0602** (agent JSON surface, landed 2026-07-29): **`pxrdref.agent` is
deliberate public API to freeze** — `refine_json`, `request_schema`,
`response_schema`, `tool_definition`, the request/response envelope models and
`ERROR_CODES`.  Two contracts inside it are load-bearing for external
consumers: the three error codes are a **closed set** (agents branch on them),
and the success envelope sets exactly one of `result`/`series`.  The
backend/solver/plan schema descriptions are generated from the live registries
at import — the freeze should pin the *mechanism* (the meta-test in
`tests/test_agent_surface.py`), not the name lists.

From **WP-0310** (v0.3 acceptance, landed 2026-07-24) — **a release blocker,
flagged deliberately for this WP.** The 16 vendored IUCr CPD QPA round-robin
patterns in `tests/data/qarr/` were freely released for re-analysis but carry
**no explicit open licence**. Confirm vendoring is acceptable before
publishing, or exclude them from the sdist/wheel and fetch on demand. Noted in
the README; unresolved.

From **WP-0401** (op shim, landed 2026-07-24) — public signatures that changed
during v0.4 and need an explicit freeze-or-hide decision:
`pawley_restraint_residual(vec)` now takes the intensity vector; new
`CompiledModel.split_pawley_intensities`; `set_pawley_intensities` is the
single post-solve commit; `evaluate` / `phase_peaks` / `derivative_bases` grew
optional intensity arguments; `cell_volume` returns a 0-d fp64 scalar
(`np.float64` subclasses `float`, so QPA and pydantic are unaffected). Plus the
whole new `backend/` surface — `Backend`, `get_backend`, `set_backend`,
`resolve_backend`, and WP-0403's `MixedPrecisionPolicy` / `precision_policy` /
`to_host_fp64` in `backend/linalg64.py`. Most of these are internals that
happen to be importable; decide which are API.

From **WP-0309** (exporters, landed 2026-07-24): `write_refinement_cif`'s
round-trip is validated for **single-phase only** — a full multi-phase
structure re-read was never a v0.3 commitment. Whatever guarantee the frozen
API states about CIF round-tripping has to say that, or narrow the claim.

## Tasks

- [ ] Expand this stub into a full WP before starting

## Handover log

- **2026-07-22** — created as a stub from the ROADMAP split.

# WP-0602 — Agent JSON surface hardened

Milestone: v0.6 · Status: ✅ 2026-07-29
Depends on: —

## Goal

`anatase.agent.refine_json(dict) → dict`: one call that takes a fully-typed
JSON request (single-pattern, multi-histogram, or sequential series), runs the
refinement, and returns either a serialized result + FitReport or a
structured, actionable error — never a raw traceback.  Beside it,
`request_schema()` / `response_schema()` / `tool_definition()` export the
JSON Schemas an LLM tool-calling loop needs, with the backend/solver/plan
vocabularies drawn from the live registries rather than restated literals.

## Scope (carried verbatim from the pre-split roadmap)

- Agent JSON surface hardened: `agent.refine_json(dict) → dict`, JSON-Schema
  export for tool-calling

## Context pointers

- Every schema already exports JSON Schema (pydantic v2, `extra="forbid"`,
  ±inf-safe serialization) — this WP is the single-call composition and its
  hardening (errors as structured, actionable JSON), not new schema work.
- The MCP server wrapping `refine_json` stays fenced in v2.

## Decisions (made 2026-07-29, expanding the stub)

- **One module, `src/anatase/agent.py`** — request/response envelope models and
  the dispatch live together; the surface is one file to read.  Consumers use
  `anatase.agent.refine_json`; no new top-level re-exports.
- **Envelope**: success is `{"ok": true, "result": …, "series": …, "report": …}`
  (exactly one of `result`/`series` set — a JSON consumer branches on which,
  answering the 0505 two-result-types asymmetry structurally); failure is
  `{"ok": false, "error": {code, message, where, suggestion, details}}` — the
  same shape vocabulary as `Diagnostic`, so an agent has one grammar for "the
  fit warns" and "the call failed".  `refine_json` never raises on data-shaped
  problems.
- **Three error codes, closed**: `INVALID_REQUEST` (any validation failure,
  with per-field `details[]` carrying dot-paths; unknown plan/backend/solver
  names land here via validators that quote the live registry),
  `BACKEND_UNAVAILABLE` (a *valid* backend name whose package is not
  installed — the install hint is the `suggestion`), `REFINEMENT_FAILED`
  (an exception mid-fit, message preserved).
- **Task union answers the Inherited asymmetries deliberately**:
  `task="refine"` (all three modes; optional `history_path` — node/tree ids
  are null without it, matching `refine()`'s history-off default),
  `task="refine_multi"` (node/tree ids **always null** and the schema field
  description says so — the 0308 seam, documented rather than accidental),
  `task="refine_sequential"` (returns `series`; history ids are per-entry,
  never per-run).  Multi responses carry no FitReport — reports are
  per-histogram (`result.for_histogram(h)` + `build_report`), and the surface
  says so instead of picking a histogram silently.
- **Plans**: a preset name (validated against `PLAN_PRESETS`, mode-mapping
  handled by `fit()` as in python) or an explicit `{stages: [...],
  correlation_guard}` spec mirroring `Stage` — the AGENT_PROTOCOL allows
  hand-rolled stage lists only with a stated reason; the schema description
  carries that warning.
- **Validation through live registries**: backend names via
  `backend.api.BACKEND_NAMES`, solvers via `optimize.least_squares.SOLVERS`,
  plans via `PLAN_PRESETS` — schema `description` strings are built at import
  time from the same tuples, and a test asserts every registry member appears
  in the exported schema so a new backend/solver cannot ship without the
  schema knowing it.
- **`Provenance.solver`** carries which driver produced the result (the 0601
  decision); `StageResult.n_constraint_truncations` carries the per-stage
  count, and a final stage with a nonzero count emits a new **`CONSTRAINT_ACTIVE`**
  `info` diagnostic — the only signal that a constraint was *active* rather
  than merely declared.  Its agent semantics follow the AGENT_PROTOCOL §6
  Stephens row: admissible, not measured; vary the start before quoting.
  `SequentialRefinement`/`refine_sequential` gain `solver=` passthrough, and
  `refine_multi` gains `backend=`/`solver=` (both constructors already had
  them; the functional wrapper dropped them).
- **The orphaned texture ActionKind is claimed**: `refine_preferred_orientation`
  joins the Layer-2 vocabulary (THRESHOLDS_VERSION 0.2 → 0.3, a minor bump),
  emitted from `FitReport.texture` entries with `detected=True` in both the
  mature and the abstained branch (texture is a common *cause* of immaturity —
  same reasoning that computes it pre-gate).  `parameter_paths` names
  `phases.{i}.preferred_orientation.r` whether or not the block is declared:
  the strategy veto handles the declared-and-planned case, and
  `predict_then_verify` degrades gracefully (frees nothing → no improvement →
  rolled back) on the undeclared one, with the axis and r in the rationale so
  the agent knows what block to declare.

## Non-goals

- No MCP server, no HTTP, no file paths / CIF text in the request (the v2 MCP
  wrapper is the place for I/O conveniences; this surface takes typed objects).
- No new refinement capability: `refine_json` composes `refine`,
  `refine_multi`, `refine_sequential` exactly as the python API exposes them.
- No `SharingMap` beyond the two glob lists it already is.
- No FitReport for multi-histogram responses (see Decisions).

### Inherited

From **WP-0508** (flat-plate absorption, landed 2026-07-28) — new surface to
cover, and one enum that is no longer binary.

- **`Geometry.kind` has three values**, not two: `debye_scherrer`,
  `bragg_brentano` and `flat_plate_transmission`. Anything that branches on
  "capillary or flat plate" (JSON schema enums, request validation, the
  worked examples) needs the third, and the two flat kinds behave differently —
  only `bragg_brentano` accepts `surface_roughness`, and the absorption
  expression differs between them.
- **`AbsorptionCorrection` grew four fields** (`method`, `unabsorbed_fraction`,
  `identifiable_fraction`, `intensity_fraction_of_optimal`), and `method` is
  the discriminator a consumer must read before interpreting `mu_r` — it is
  µ·R for a cylinder and µ·t for a plate, deliberately one field because it is
  one dimensionless product, but they are not the same quantity.
- **Two new diagnostic codes**, both flat-plate: `ABSORPTION_THICKNESS_MATTERS`
  (`info`, but it is the one that says a wrong thickness lands partly in the
  ADPs) and `ABSORPTION_PLATE_THICKNESS` (`info`, specimen-preparation advice
  with no bearing on the fit). Their agent-facing semantics are in
  AGENT_PROTOCOL §7's table and §8.12; the JSON surface should not restate
  them, only stay consistent with them.

Four result-surface shapes landed in v0.3 that a single-call JSON API will trip
over. All are real, none are bugs.

From **WP-0303** (anisotropic ADPs): **not all six U^ij components appear in
`result.parameters`.** Symmetry-locked components (U13/U23 on rutile's 4f, say)
never enter θ at all, so a consumer that assumes six entries per anisotropic
atom will `KeyError` on exactly the high-symmetry sites. Report what is there;
do not synthesise zeros.

From **WP-0308** (multi-histogram): `refine_multi` runs **without** the
`RefinementTree` DAG — no history, no per-stage nodes — because a multi-pattern
fingerprint was left as a future seam. So a uniform `refine_json(dict) → dict`
either excludes multi-histogram or returns a fit with no history where the
single-pattern call has one. That asymmetry needs a deliberate answer in the
schema, not an accident. The `RefinementResult` itself still fully serializes.

From **WP-0505** (sequential series, landed 2026-07-28): **there is now a
second top-level result type.** `SeriesResult` (`schemas/sequential.py`) is
what `SequentialRefinement` / `refine_sequential` return, and it is *not* a
`RefinementResult` — it carries per-pattern `SeriesEntry` summaries (statistics,
refined values + esds, QPA, diagnostics, node/tree ids) and deliberately no
curves, so a `refine_json` that only knows how to emit `RefinementResult` cannot
express a series at all. It also brings three diagnostic codes the agent
vocabulary must carry: `SEQUENTIAL_RESEED`, `SEQUENTIAL_DISCONTINUITY`,
`SEQUENTIAL_PATH_DEPENDENT` (semantics in `docs/AGENT_PROTOCOL.md` §9b). One
asymmetry to decide deliberately rather than by accident, the same shape as the
0308 one above: a series produces **one history tree per pattern**, so its
`node_id`/`tree_id` are per entry and there is no single tree id for the run.

From **WP-0307** (March-Dollase): `FitReport.texture` reports a diagnosed
preferred-orientation axis, but **no Layer-2 `ActionKind` was ever added for
it** — the vocabulary is versioned, so 0307 deferred it and no WP has claimed
it since. An agent surface consuming Layer-2 actions is the closest natural
owner; either claim it here or it stays orphaned.

From **WP-0408** (torch backend, landed 2026-07-27) — two surface facts a
single-call JSON API has to get right:

- **`backend` is a name from a registry, not a boolean.** There are four:
  `numpy`, `jax`, `torch`, `torch-mps`. `backend.api._BACKEND_NAMES` is the live
  list and `resolve_backend` is the validator both `Refinement` and
  `MultiHistogramRefinement` now call, raising with the available set. A JSON
  surface should validate through the same call rather than restate a literal
  union that will go stale — the fourth name arrived after the third by two
  days.
- **`Provenance.backend` / `.dtype` are now populated** (they had said
  `"numpy"` / `"float64"` since v0.1 no matter what ran). `dtype` is
  `"float64"` except on Apple GPU, where it is
  `"float64/jacobian:float32"` — the residual and solve are fp64 there too, so
  it is one honest string rather than a dtype per stage. An agent reporting
  reproducibility metadata should surface both; do not parse the string for the
  fp32 substring to decide anything, ask
  `backend.api.backend_dtype_note(name)`.

From **WP-0506** (secondary extinction): **never expose the raw `ext`
coefficient with a fixed bound or plausibility check.** Its scale is
wavelength/cell-dependent (x ∝ (λ/V)²): ~0 for CuKα/LaB6 but ~300 for
0.414 Å/NAC. Judge extinction by its *effect* (x, or the minimum E across
reflections), never by the coefficient — a hard-coded range would be wrong for
half the instruments.

From **WP-0601** (bounded LM solver, landed 2026-07-28) — one diagnostic's
meaning changed, and two new fields exist for the surface to decide about.

- **`STEPHENS_STRAIN_NOT_POSITIVE` no longer means what the protocol table said
  it meant, and the row in `docs/AGENT_PROTOCOL.md` has been rewritten.** Two
  changes: (a) the guard's test was `σ² ≤ 0`, which reported the *all-zero*
  Stephens block — documented as the exact no-broadening identity — as
  unphysical in every stage before the one that frees the patterns; it is now
  one-sided with a relative tolerance, because zero is *on* the cone and a
  constrained optimum lands there by construction. (b) The claim it "fires on
  isotropic and anisotropic specimens alike" was an artefact of (a) and is
  withdrawn: corundum never leaves the cone at any stage, and unconstrained
  brucite leaves it only from the low starting seeds. An agent can now act on a
  firing — re-run with `solver="lm"`, which enforces the cone — but the honest
  follow-up is a start-stability check, since the coefficients still span
  ~100 % across seeds under both drivers.
- **`LSQOutcome` gained `solver` and `n_constraint_truncations`**, and neither
  currently reaches `RefinementResult`. Which driver ran is provenance
  (`Provenance` already carries `backend`/`dtype`, so it is the obvious home),
  and the truncation count is the only signal that a constraint was *active*
  rather than merely declared. Decide deliberately rather than by omission: a
  refinement whose answer sits on a constraint face and does not say so is
  exactly the confident-singleton failure the FitReport rules exist to prevent.
- **`solver=` is now a constructor argument on `Refinement`,
  `MultiHistogramRefinement` and `refine()`**, validated against
  `optimize.least_squares.SOLVERS`. Any JSON surface that reconstructs a
  refinement from a request object has a second axis to carry beside `backend=`.

## Tasks

- [x] Expand this stub into a full WP before writing code
- [x] Solver provenance: `Provenance.solver`, `StageResult.n_constraint_truncations`,
      `CONSTRAINT_ACTIVE` diagnostic, `solver=` on `SequentialRefinement` /
      `refine_sequential`, `backend=`/`solver=` on `refine_multi` + tests
- [x] Layer-2: `refine_preferred_orientation` ActionKind, `texture_actions`,
      emission in both build_report branches, THRESHOLDS_VERSION bump + tests
- [x] `agent.py`: request/response models (task union, StageSpec/PlanSpec,
      SharingSpec), `refine_json` dispatch with the three-code error envelope
- [x] `agent.py`: `request_schema` / `response_schema` / `tool_definition`,
      live-registry descriptions
- [x] `tests/test_agent_surface.py`: round-trips (all three tasks on the
      synthetic LaB6), validation errors with dot-paths, registry-schema
      containment, envelope invariants
- [x] Docs: AGENT_PROTOCOL §7 row for `CONSTRAINT_ACTIVE` + §9c JSON-surface
      section; CLAUDE.md data-flow line + test counts (939 fast / 1021 total)

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_agent_surface.py tests/test_fitreport_layers.py tests/test_sequential.py tests/test_multi_histogram.py tests/test_lm_solver.py -q
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"   # full fast suite
.venv/bin/python -m ruff check src tests examples
```

Plus, by hand once: `refine_json` on an intentionally broken request returns
`ok:false` with a dot-path into the offending field, and
`tool_definition()["input_schema"]` names every live backend, solver and plan.

## Handover log

- **2026-07-29 (later, same session)** — **shipped.** Done: all six checklist
  rows, five commits (`5e88a64` WP expansion, `d24a1c8` solver provenance,
  `3a01927` texture ActionKind + THRESHOLDS_VERSION 0.3 stamped into
  Provenance, `699d925` agent.py + 21 tests, `d08e69a` docs). Fast suite green
  at 939 tests (`-n auto --dist loadgroup -m "not slow"`, exit 0), ruff clean.
  Forward-references written into 0604 / 1001 / 1003 `### Inherited`.
  Gotchas for anyone touching this surface:
  - `anatase.refine` the *module* is shadowed by `anatase.refine` the
    *function* on the package object — patch/import via
    `sys.modules["anatase.refine"]`, not attribute access (bit the
    BACKEND_UNAVAILABLE test twice).
  - The request union is discriminated on `task`; pydantic prefixes every
    validation loc with the branch tag, and `_validation_failure` strips it.
    If a fourth task is added, extend `_TASK_TAGS` or the dot-paths grow a
    prefix again.
  - `_dispatch` resolves plans through `sequential._resolve_plan` so the plan
    the Layer-2 veto sees is the mode-mapped plan that actually ran
    (mccusker_default → profile_only under lebail) — do not "simplify" it to
    `PLAN_PRESETS[name]()`.
  - `CONSTRAINT_ACTIVE` is emitted only for the answer-producing stage
    (final stage of `fit()`, the stage of `run_stage()`); per-stage counts
    live on `StageResult.n_constraint_truncations`.
- **2026-07-29** — expanded from stub; decisions recorded above (envelope,
  three error codes, task union answering the 0308/0505 asymmetries,
  live-registry validation, `Provenance.solver` + `CONSTRAINT_ACTIVE`,
  texture ActionKind claimed).
- **2026-07-22** — created as a stub from the ROADMAP split.

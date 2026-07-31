# WP-1050 — `Refinement.suggest()`: which parameter to free next

Milestone: v1.0 (proposed 2026-07-30) · Status: ⬜
Depends on: — (1004 landed). Must land **before** 1003 if `suggest()` ships in
the frozen API.

## Goal

A read-only `Refinement.suggest()` that ranks held-but-refinable parameters by
their predicted χ² leverage at the current state, gates every candidate for
collinearity, and — like `IndexingResult` — never hands back a confident
singleton it cannot defend: ties come back as unresolved groups.

## Context

Toby (2024) computes ∂χ²/∂p by ±δ finite differences for every held parameter
and picks the largest — with per-parameter-type δ heuristics and a
sign-consistency test to reject converged-but-sensitive parameters, because
GSAS-II's analytic derivatives are locked inside Hessian assembly. Ours are
not: `_make_jacobian(model, table)` (`optimize/least_squares.py`) is a pure
closure over the table, so a probe table with candidates freed yields exact
weighted columns at the current θ, no solve. That replaces all three of his
workarounds:

- **Score** = Gauss-Newton one-parameter gain. Project the currently-free
  column block `F` out of candidate column and residual (Frisch-Waugh-Lovell):
  `j̃ = (I−P_F)J_j`, `r̃ = (I−P_F)r`; gain `Δχ²_j = (j̃ᵀr̃)²/(j̃ᵀj̃)`.
  Scale-invariant (no δ heuristics — column rescaling by dp/du cancels) and
  ≈ 0 at a minimum (no sign test — the score statistic is ~χ²₁·χ²_red under
  H₀, hence the noise floor `SUGGEST_MIN_GAIN = 9.0 · max(χ²_red, 1)`,
  ≈ 3σ; calibrate on the truth fixture and record the measured separation in
  the constant's comment). Report the gradient in physical units:
  `2(Jᵀr)_j / (dp/du)_j`.
- **Gates**, both via `block_projection_r2` (`optimize/statistics.py:144`):
  absorption of `J_j` by span(F) (R² > `SUGGEST_ABSORPTION_MAX = 0.95` ⇒
  non-separable — this also caps the `1/(1−R²)` blow-up in the gain), and
  candidate-vs-candidate groups by pairwise ρ² between *projected* unit
  columns + union-find at `SUGGEST_GROUP_R2 = 0.95`. A multi-member group
  gets a joint gain and `resolved=False` — this is Toby's own stated failure
  mode ("a much larger derivative for an instrumental broadening term than
  for sample broadening") reported as the tie it is, instead of a winner.
- **Cross-check, not replacement, of Layer 2**: `SuggestedAction` speaks the
  closed template vocabulary (zero/displacement/cell/size/strain/scale/ADP);
  leverage covers *every* table entry (atom DOFs, ADPs, Stephens blocks, PO,
  background). When a top candidate matches an action's paths (the two-way
  fnmatch of `apply_strategy_veto`, `report/layer2.py:341-349`), record its
  kind — two independent methods agreeing is the house device.

Verified against the tree (2026-07-30 review session; restated so this file
stands alone):

- **Read-only means model copies.** Seeding a probe `ParameterTable` never
  reaches `compile_model` — `_run_stage` calls `table.apply_to_models(...)`
  *before* compiling (`refine.py:564`). Apply the probe table to **deep
  copies** of structure/instrument and compile from the copies.
- **Softplus-floor candidates have dead internal columns** (dp/du ≈ 0); seed
  them, per family: `1e-3` generic, `0.3` for Suortti roughness (both ends of
  that transform are the identity — `strategy/staged.py:62-67`), Stephens via
  `seed_stephens` at `1000.0` (the √ has unbounded slope at S ≡ 0). Seeding,
  not divide-out-dp/du: the gain is coordinate-invariant for live columns, a
  divide-out cannot fix Stephens-at-zero at all, and the seed predicts the
  solve a stage would actually run. Report `seeded=True` per candidate.
- **Full row layout**, one Jacobian build, one combined table (free ∪
  candidates): penalty + restraint rows included, else absorption is
  overstated (the `background_absorption` precedent, `statistics.py:134-137`).
  Pawley θ is `[table θ | intensities]` — mirror the aux-block x0 assembly in
  `run_least_squares`; Le Bail intensity carry mirrors `refine.py:568-589` /
  `816-825`. `scalar_chain_supported` covers all candidate families, so no
  column falls to FD.
- **`ActionKind` cannot be imported into `schemas/`** (report imports
  schemas, not the reverse): the cross-reference field is a plain
  `str | None`, pinned to the vocabulary by a meta-test via
  `typing.get_args(ActionKind)`.
- **Zero-norm columns** go to a `skipped` list (no leverage at this state),
  never silently dropped. Candidates whose feature block is undeclared
  (PO/strain/roughness absent) never enumerate — their paths don't exist.
- Enumeration authority is the parameter surface: `row.refinable and not
  row.vary` + include/exclude fnmatch — locked/tied/mode-fixed excluded by
  construction (`schemas/params.py`, whose module docstring anticipated this
  caller).

Pieces: `optimize/statistics.one_parameter_gains(jac, resid, block, targets)`
(shares one thin QR with `block_projection_r2` via a private helper; that
function stays byte-identical); `schemas/suggest.py` (`ParameterCandidate`,
`CandidateGroup`, `SuggestionResult` — **no `.cell`-style `.best`**, only a
gated `best_or_none()`; constants live here, report/schemas.py pattern);
`strategy/suggest.build_suggestion`; `Refinement.suggest(data, *, top_n=5,
include="*", exclude=(), mode=None, two_theta_limits=None, report=None)` —
no history node, no mutation (*considering* freeing is not a refinement
move); agent task; manual.

### Inherited

From the **2026-07-30 review session** (commit `732535d`, not a WP): the
weighted Δ/σ default in `viz/` already cites Toby 2024 in docstrings, but
deliberately without a bib entry — `tests/test_manual.py` fails an uncited
bib entry, so **this WP owns** adding `toby2024` to
`docs/manual/references.bib` together with its citing manual subsection.

From **WP-0602**: `tests/test_agent_surface.py` pins the request schema at
`len(schema["oneOf"]) == 3` — update to 4 in the same commit as the task.

## Non-goals

- No automatic stage insertion: the staged runner stays preset; `suggest()`
  informs a caller (human, GUI, or the agent loop), it does not drive.
- No GUI panel (a later GUI WP wires it).
- `ParameterRow` grows **no** field — the `dataclasses.fields(Entry)` mirror
  meta-test keeps exactly its two declared extras; a suggestion is a joint
  property of (model, data, θ, free set), not of a row.
- Not a replacement for FitReport Layer 2 (see cross-check above).

## Tasks

- [ ] `optimize/statistics.py`: `one_parameter_gains` + shared-QR refactor;
      brute-force property test against explicit lstsq of `[F | j]` on random
      matrices. `block_projection_r2` behaviour unchanged.
- [ ] `schemas/suggest.py`: models + constants (measured-rationale comments);
      JSON round-trip tests, `extra="forbid"`.
- [ ] `strategy/suggest.py`: `build_suggestion` (score, gate, group, rank,
      summary, Layer-2 cross-reference); synthetic-matrix tests.
- [ ] `refine.py`: `Refinement.suggest()` (enumeration, per-family seeding,
      model-copy compile, lebail/pawley carry); `__init__.py` exports.
- [ ] Misfit-injection tests (reuse `_truth` from
      `tests/test_fitreport_layers.py`): converged → `best_or_none() is
      None`; injected zero shift ranks top; Layer-2 agreement recorded;
      W-vs-gauss_size comes back one group, `resolved=False`; candidate
      absorbed by free set is not a winner; softplus-floor candidate found
      with `seeded=True`; read-only assertion (history/vary/values/result_
      untouched); lebail mode-fixed paths never enumerate.
- [ ] `agent.py`: read-only `suggest` task — the first no-solve task. Split
      `_BackendBase` out of `_RequestBase` (no solver/plan fields, so passing
      them errors loudly under `extra="forbid"`); `AgentSuccess.suggestion`,
      invariant "exactly one of result/series/suggestion"; `_TOOL_DESCRIPTION`;
      meta-test updates (oneOf 3→4).
- [ ] Manual: `docs/manual/estimation.md` subsection (gain equation with
      *Source:* `pxrdref.optimize.statistics.one_parameter_gains`), `toby2024`
      bib entry, `conf.py` substitution for `SUGGEST_MIN_GAIN` + a chapter use.
- [ ] Acceptance run + obs/calc/diff PNGs to `tests/output/`.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_suggest.py tests/test_agent_surface.py -q
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
.venv/bin/python -m sphinx -W -q -b html docs/manual docs/manual/_build/html
```

Criterion: every misfit-injection case above passes, including the two
negative controls (converged model suggests nothing; the collinear pair is a
group, not a winner).

## References

- Toby, B. H. (2024). *J. Appl. Cryst.* **57**, 175–180.
  doi:10.1107/S1600576723011032 — the recipe problem and the FD worst-fit
  mechanism this WP replaces with analytic columns.
- Ozaki, Y. *et al.* (2020). *npj Comput. Mater.* **6**, 75 — the black-box
  alternative (hundreds of refinements); context for why one-evaluation
  leverage is worth having.
- Rao, C. R. (1948). *Proc. Camb. Phil. Soc.* **44**, 50–57 — the score test
  the gain statistic instantiates.
- Frisch, R. & Waugh, F. V. (1933). *Econometrica* **1**, 387–401; Lovell,
  M. C. (1963). *J. Am. Statist. Assoc.* **58**, 993–1010 — the projection
  identity.

## Handover log

- **2026-07-30** — created from the Toby 2024 / SrRietveld literature review;
  design verified against the tree (model-copy compile, per-family seeds,
  Pawley aux block, ActionKind layering, agent oneOf pin).

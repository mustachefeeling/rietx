# WP-1102 — The additive component seam, and broad humps as its first member

Milestone: v1.2 · Status: ⬜
Depends on: — (independent of 1101; [1103](1103-peak-components.md) lands its
second member in this seam)

## Goal

`Instrument.extra_components` — a discriminated union of declared parametric
components added to the calculated pattern, this package's serializable,
differentiable, agent-visible answer to TOPAS's `fit_obj` — with
`HumpComponent` (a broad pseudo-Voigt: amorphous humps, very broad
impurities) as its first member. A hump refines center/fwhm/area/eta with
esds and reports an **area, never a weight fraction**.

## Context

- **Why a union seam and not two ad-hoc features.** A hump and a sharp extra
  peak ([1103](1103-peak-components.md)) are the same mathematical object —
  `area · pseudo_voigt(tt − center, fwhm, eta)`
  (`model/profiles/pseudovoigt.py`, unit-area, xp ops) — differing only in
  which aggregates they join. One extensible seam (the `Background`-union /
  backend-registry pattern) means a future shape (exponential tail, Debye
  amorphous term, split-pV) is one member + one evaluator + one cross-backend
  row. TOPAS prior art, concepts only (closed source): `fit_obj` is the
  capability; its *textual* form is not portable here — see the fence below.
- **The seam.** `ExtraComponent = HumpComponent` union alias (bare PEP-604 +
  `kind` Literals, the `Background` precedent in `schemas/instrument.py`);
  `Instrument.extra_components: list[ExtraComponent] = []`. An additive
  defaulted field — no `SCHEMA_VERSION` event (the events precedent) — and it
  rides `RefinementState` (which stores the full `Instrument`) into history,
  checkout and replay with nothing to add. Paths
  `instrument.extra_components.{i}.{field}`: matched by **no** preset glob
  (presets free `instrument.background.*`, the profile letters, zero,
  geometry singletons, line weights), so freeing is always the caller's
  explicit act — the microstrain "declared block, freed deliberately"
  precedent, pinned by test.
- **Freeing recipe — stages are cumulative** (`refine.py`: "stages are
  cumulative: start from everything the user left vary=True"). A
  `set_vary("instrument.extra_components.*", True)` before a preset run
  survives the plan — but the components are then free from stage 1
  (scale_bkg) onward, the unseeded-early-freeing failure mode. The
  recommended route, documented in the manual, is a custom plan appending a
  late `Stage("humps", ["instrument.extra_components.*"])`;
  `Stage.seed`/`seed_softplus` already exist to lift a softplus `area` off
  the zero floor in that stage. State both facts in the manual.
- **The member contract** (goes in the union's docstring; every future member
  obeys it): (1) an xp-ops evaluator, whole-grid or frozen-window; (2) every
  member's curve is subtracted from the Le Bail partition net
  (`CompiledModel.lebail_update` and `structure_intensity_partition` — else
  phases are handed shares of component counts); (3) each member declares its
  aggregate memberships — a hump joins the *reported background*
  (`result.y_background`, `BackgroundEvidence`, the absorption span); a peak
  ([1103](1103-peak-components.md)) joins ticks instead; (4) a new member is
  an evaluator + a cross-backend CONFIGS row + a manual equation with
  `*Source:*`, **and is itself a schema closed-vocabulary event** (moot for
  1103 while both land inside the same 1.1.0 release, but stated so a third
  member is not assumed free).
- **The fence, with grounds**: arbitrary callables or an expression DSL
  (`fit_obj` proper) violate three invariants at once — history stores state,
  not code; the traced twin must differentiate the same expression on
  jax/torch; the agent surface is JSON schemas under `extra="forbid"`. TOPAS
  can do textual fit_obj because its equation text *is* its serialization
  format. An expression-DSL member is v2+ material if ever. Not a phase kind
  (TOPAS `xo_Is`) either: `Phase` is crystallographic through and through
  (cell ties, Wyckoff, QPA) and a cell-less phase breaks every consumer.
- **`HumpComponent` fields**: `kind: Literal["hump"]`; `label: str | None`;
  `center` (Parameter, deg 2θ, apparent, required); `area` (Parameter,
  counts·deg, softplus min=0 is safe — zero is the off state); `fwhm`
  (Parameter, deg, default value=5.0, **hard floor `HUMP_FWHM_MIN = 0.1`** +
  reachability validator — the `MARCH_R_MIN` pattern, and for the same
  reason: the profile divides by Γ and a stored `min: 0.0` outlives the
  default); `eta` ([0, 1], default 0.5). All `vary=False` by default.
  Whole-grid evaluation, no windows — broad by declaration, O(n_points) per
  hump.
- **Never in the linear stack.** `bkg_paths` is hand-built at compile
  (`model/forward.py`) and a nonlinear path there gets a silently wrong exact
  Jacobian column (the background branch fires first on `path in bkg_cols`).
  Guard test: `set(bkg_paths) ∩ component paths == ∅` — `area` stays out too,
  one membership rule, no conditional. Jacobian: unknown paths fall to the
  whole-model FD column (data rows only — correct, components own no penalty
  rows; exact, FD decodes through C like the residual). Analytic columns via
  `pseudo_voigt_derivs` are deliberately out of scope: with ≤ ~10 such
  parameters the FD cost is ~10 residual evaluations per Jacobian, and the
  cross-backend agreement matrix is the correctness check.
- **Table wiring**: one authority helper `extra_component_parameters(comp)`
  (`model_fields` minus `kind`/`label` — the `roughness_parameters`
  precedent, `params/vector.py`) feeding **both** `_collect_instrument` and
  `apply_to_models` — a parameter registered in one and forgotten in the
  other silently loses its refined value at the next stage's recompile.
  Test exactly that.
- **Background-aggregate membership**: `result.y_background` gains hump
  curves (one authority — a model method consumed by `_build_result`, every
  renderer through it); `background_absorption`'s column selection
  generalizes from the hard `instrument.background.` prefix
  (`optimize/statistics.py`) to a model-declared background-block set that
  includes hump paths — the R² then measures what the *whole declared
  background* can imitate. Guard/diagnostic chain follows unchanged.
- **Evidence** (a new correction ships with a record field or a diagnostic,
  never an Rwp comparison): the hump rows in `result.parameters` — declared,
  refined, esds — are the record. New diagnostic `BACKGROUND_HUMP_SHARP`: a
  fitted fwhm approaching the instrumental predicted FWHM at its center is a
  crystalline peak being eaten, not a hump. Evidence, never refusal — and
  the width-ratio constant is **not invented up front**: thresholds are
  quoted from a paper or a measurement, never tuned, so the acceptance
  task's width-ladder measurement fixes it, provenance recorded beside it.
- `save_instrument_profile` strips `extra_components` (mount/specimen state,
  not goniometer constants — the roughness/µt precedent in
  `io/instrument_profile.py`).
- Untouched: the `Background` union and all its consumers,
  `background/auto.py`, `gui/imports.py`. GUI: the parameter panel and the
  `.rxt` instrument block render component rows for free (whole-table rule);
  no model editor (the P-spline precedent — it has none either).

## Non-goals

- Arbitrary callables / an expression DSL (fenced above, with grounds).
- A fourth `Background` union kind — humps compose with any base background
  from outside it.
- Amorphous / internal-standard QPA (v2 fence): a hump's quotable number is
  its area (counts·deg) with esd, never a fraction.
- Analytic Jacobian columns for component parameters.
- Preset stages that free components — freeing stays the caller's declared act.
- A GUI component editor.
- Sharp peaks ([1103](1103-peak-components.md)).

## Tasks

- [ ] Schema: `ExtraComponent` union + `HumpComponent` + `HUMP_FWHM_MIN` +
      reachability validator; JSON round-trip tests; release-notes line (the
      1.0.2 notes' "three background models now frozen" neighbourhood gets
      its amendment).
- [ ] Table wiring via `extra_component_parameters` feeding both collect and
      apply; test that refined hump values survive a stage recompile.
- [ ] Forward model: evaluator joins `evaluate()`; Le Bail / partition
      subtraction seams; `bkg_paths` disjointness guard test; test that a
      declared hump leaves Le Bail extracted phase intensities unbiased.
- [ ] Jacobian: FD-fallback assertion + new CONFIGS row in
      `tests/test_cross_backend.py`.
- [ ] Background-aggregate membership: `y_background` authority +
      `background_absorption` generalization + tests.
- [ ] `BACKGROUND_HUMP_SHARP` (constant fixed by the acceptance task's
      width-ladder measurement, provenance beside it) +
      `../AGENT_PROTOCOL.md` §7 row + §3 degeneracy line.
- [ ] Surfaces: capabilities schema-shaped key
      (`"extra_components" in Instrument.model_fields`) + expected-key set;
      `io/exporters._background_description` mentions "+ N humps";
      instrument-profile strip.
- [ ] Manual: `using/data.md` subsection (declare, free late,
      area-not-fraction, when a hump vs P-spline flexibility) +
      `../manual/background.md` equation with `*Source:*`; api-surface
      documentation of the new public names (freezes them).
- [ ] Compare: `_with_hump` variant beside `_with_pspline` (`viz/compare.py`;
      declare a hump + a late freeing stage) + `tests/test_compare_ui.py` row.
- [ ] Acceptance measurement + tests: synthetic crystalline + known hump —
      area recovered within its esd band; the absorption table
      declared-hump vs P-spline-flexibility on the same pattern (the honest
      evidence, not Rwp); the width ladder that fixes
      `BACKGROUND_HUMP_SHARP`; obs/calc/diff PNGs to `tests/output/`.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_cross_backend.py tests/test_capabilities.py tests/test_compare_ui.py tests/test_manual.py tests/test_manual_api.py -q
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
.venv/bin/python -m sphinx -W -q -b html docs/manual docs/manual/_build/html
```

Full suite once on the final tree: the `background_absorption` selection
change touches guard evidence on every state.

## References

- Thompson, Cox & Hastings (1987), J. Appl. Cryst. 20, 79 — the pseudo-Voigt;
  already cited in `../manual/profiles.md`.
- [1055](1055-background-evidence.md) and the v0.5 milestone record — the
  measured background-bias failure this parameterisation answers.
- [1028](1028-robustness-external-data.md) §(e) — `MARCH_R_MIN`, the
  softplus-pole precedent the fwhm floor copies.
- TOPAS `fit_obj` as prior art — concepts only (closed source; papers and
  manual concepts). If the hump parameterisation should cite prior practice,
  the citation comes from the maintainer-local paper corpus, not memory.

## Handover log

- **2026-08-18** — created from the single-peak planning session; numbering
  opens the 11xx block (v1.1). The seam design replaced an earlier
  humps-inside-`Background` draft: unifying with
  [1103](1103-peak-components.md) under one union deleted that draft's
  riskiest task (retightening `instrument.background.*` in every preset,
  which fnmatch's dot-crossing `*` made necessary there and the
  `extra_components` prefix makes unnecessary here).

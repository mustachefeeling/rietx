# CLAUDE.md — pxrd-refine

API-first Rietveld refinement package (powder XRD). MIT. numpy/scipy fp64
core, pydantic v2 schemas, gemmi for CIF/symmetry. Import name: `pxrdref`.

## Commands

```sh
uv venv --python 3.12 && uv pip install -e ".[dev]"   # setup (once)
uv pip install -e ".[dev,jax,torch]"                   # + optional jax/torch backends
.venv/bin/python -m pytest -n auto --dist loadgroup    # full suite ~6-8 min (1197 tests), incl. real-data acceptance
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"   # skip acceptance (1116 tests, ~45-55 s)
.venv/bin/python -m pytest tests/test_cross_backend.py # Jacobian agreement matrix; rows self-skip without their backend
.venv/bin/python -m ruff check src tests examples      # lint (must be clean)
.venv/bin/python examples/nac_11bm.py                  # end-to-end demo + plot
.venv/bin/python -m sphinx -W -q -b html docs/manual docs/manual/_build/html  # theory manual
.venv/bin/pxrdref watch <live-dir>                     # live viewer for a LiveSession run
.venv/bin/pxrdref compare --open                       # settings-comparison UI on the standards
```

`-n` is deliberately **not** in `addopts`: a bare `pytest tests/x.py::y` stays
serial, so `-s` and pdb keep working. `--dist loadgroup` is not optional
either — it is what honours the `xdist_group` marks that keep a shared fixture
on one worker (see the Tests bullet below); plain `--dist load` ignores them
and silently refits. Measured on a 10-core M4 (4P+6E), 2026-07-28: full
7:57 at `-n auto` and 7:24 at `-n 6`, both dominated by the single longest
group rather than by total work — fast suite 60-80 s over three runs.
**Quote wall clock as a range, never as a figure**: the same green tree
measured 7:37 and 5:44 minutes apart on that machine (2026-07-29), so machine
state moves it further than most changes do. Compare runs, not records.

`pxrdref compare` is the fastest way to answer "does this new correction
actually help?": pick a standard, tick variants, and read the **cumulative
Δχ² vs reference** panel, which localises *where* a change acted rather than
only whether Rwp moved. Registry + runner in `viz/compare.py` (also usable
headlessly as `compare.run(standard, variant)`); server/page in
`compare_app.py`. Its standards are the acceptance suites' protocols, and
`tests/test_compare_ui.py` asserts that field-by-field so the two cannot
drift — **add a row there whenever a new correction lands.**

## Data flow

```
Structure/Instrument/PatternData (schemas/, pydantic, JSON round-trip)
  → ParameterTable (params/vector.py): tree → flat fp64 θ, dot-paths
    ("phases.0.cell.a", "instrument.profile.w", "instrument.background.c2"),
    crystal-system cell ties (b←a etc.), softplus/logit transforms
  → CompiledModel (model/forward.py): per-stage frozen state — reflection list
    (crystallography/symmetry.py, gemmi), per-atom symmetry-op subsets
    (structure_factor.py), per-(emission line, reflection) point windows,
    FCJ quadrature node counts (profiles/fcj.py), background design matrix
    (+ P-spline penalty rows); derivative_bases() serves both the analytic
    Jacobian and FitReport Layer 1 from one expansion
  → run_least_squares (optimize/least_squares.py): scipy TRF, bounds,
    analytic peak-chain Jacobian (FD fallback), esds from χ²·(JᵀJ)⁻¹ ×
    Bérar-Lelann inflation
  → staged runner (strategy/staged.py) loops stages, guards, recompiles
  → RefinementResult (schemas/results.py) → FitReport (report/, 3 layers)
    → plot / plot_for_vlm / write_html (viz/)
  → history DAG (history/, schemas/history.py): every stage auto-commits an
    immutable restorable node; checkout/run_stage/branch to fork a strategy,
    merge/cherry_pick to recombine, replay to recompute a node evaluate-only,
    append-only JSONL to persist; history/events.py streams per-iteration
    events, viz/live.py + watch.py render them live
```

`fit`, `run_stage` and `refine` all take `events=` (telemetry) and `cancel=`
(an `optimize.cancel.CancelToken` another thread sets). Cancellation is
**cooperative, read between residual evaluations** — never an interrupt, so
frozen-per-stage discreteness holds — and the in-flight stage is *abandoned*:
no node, no commit, and the models restored to their pre-stage values, because
a seeding stage writes to them before solving. `RefinementCancelled` carries
`.completed_stages` and `.node_id`, the last completed node the working state
now stands at. Event `data` is an **open dict**: adding a field to a kind is
not an `EVENT_SCHEMA_VERSION` bump (a new kind is) — the rule, and both halves
of its test, are in `history/events.py`.

A **series** (in-situ ramp, parametric sweep, tray of related specimens) is N
separate refinements chained by a warm start — `sequential.py`
(`SequentialRefinement` / `refine_sequential`), returning a `SeriesResult` of
per-pattern summaries plus parameter *trajectories*, one history tree per
pattern (a tree is pinned to its pattern by `TreeHeader.data_fingerprint`),
linked by annotation notes. Not to be confused with `multi.py`, which stacks
patterns into **one joint residual**. A chained fit is worth ≈3× in iterations
and nothing in accuracy, and its trajectory is path-dependent by construction,
so `direction="both"` runs the chain each way and flags parameters the two
disagree on (`SEQUENTIAL_PATH_DEPENDENT`) — the only check that separates a
measured trajectory from an ordering artefact.

The **parameter surface** (WP-1004) is how a client works the table without
running a fit: `Refinement.parameters() → list[ParameterRow]` lists *every*
entry — fixed, locked and tied included, esds from the last fit merged in, each
held row saying which of the three reasons holds it (`.refinable`,
`.held_because`); `set_vary(globs, vary)` and `set_values({path: value})` edit
it and auto-commit the `set_vary`/`set_value` history nodes. Three rules there
are load-bearing: `ParameterRow` mirrors `params.vector.Entry` field for field
(pinned by `dataclasses.fields`, `esd`/`mode_fixed` declared as the deliberate
extras), a **tied** path refuses an edit and names its sources instead, and
`mode_fixed` — lebail/pawley force-fix every `.atoms.` path, `.scale` and
`.source.lines.` — is *not* `locked`, which is what keeps a Le Bail phase's
mandatory dummy atom from looking editable. There is exactly **one**
`StageSpec`/`PlanSpec`, in `schemas/plan.py`; `schemas/history.py` and
`agent.py` re-export it, and `PLAN_INFO` in `strategy/staged.py` carries a
title/description/modes/when-to-use per preset, in bijection with
`PLAN_PRESETS` by meta-test.

Entry points: `Refinement.fit()` / `refine()` in `refine.py`; modes
`"rietveld"`, `"lebail"` (intensity partitioning in
`CompiledModel.lebail_update`) and `"pawley"` (per-hkl intensities refined as
an off-table θ block — `model.forward.PawleyBlock`, appended in
`run_least_squares`; overlapped groups get equal-split restraints and come back
flagged `PAWLEY_OVERLAP_UNRESOLVED` rather than confidently split). For
tool-calling there is `agent.refine_json(dict) → dict` (`agent.py`, WP-0602):
one call covering refine/refine_multi/refine_sequential behind a strict task
union, errors as a structured `{ok:false, error:{code,…}}` envelope (never a
traceback), and `agent.tool_definition()` exporting the JSON Schema with the
backend/solver/plan names quoted from the live registries — a meta-test fails
if a registry member is missing from the schema.

## Invariants (do not break)

- **Frozen-per-stage discreteness**: the hkl list, symmetry-op subsets, FCJ
  quadrature node counts, and window index ranges are computed at stage
  compile and NEVER change during a least-squares run; regenerate only
  between stages. This keeps the residual smooth for FD/autodiff Jacobians.
  (FCJ node *positions* follow the parameters smoothly, with the quadrature
  split at the overlap-trapezoid kink — see profiles/fcj.py.)
- **fp64 everywhere** in the core; a GPU backend may compute Jacobian
  *columns* in fp32 but the residual used for cost/statistics and the solve
  stay fp64 on host — `backend/linalg64.py` is that boundary, and it holds on
  real hardware: an Apple-MPS refinement whose every column was computed in
  fp32 lands 3.5e-8 Å from the numpy fp64 cell, because the trust region
  re-measures each step against an fp64 cost.
- **No pydantic in the hot loop**: `ParameterTable.decode()` returns a plain
  dict; the forward model consumes floats/arrays only.
- **Weights**: use the file's esd column when present (readers), Poisson
  √max(y,1) only as fallback. Never subtract an estimated background —
  hold it additively (`BackgroundFixedPlusChebyshev`) or co-refine it under
  a smoothness penalty (`BackgroundPSpline`).
- **Background flexibility is a correctness question, not a cosmetic one.**
  A background able to imitate the peaks biases ADPs up and scales (hence QPA
  fractions) down while Rwp *improves*. Measure it as the block projection
  R² of a structural Jacobian column onto the background column span
  (`optimize.statistics.background_absorption`) — pairwise ρ misses it
  entirely (~0.2 per coefficient while the block absorbs ~46 %).
- **Reciprocal-space symmetry action is Rᵀ** (transposed rotation) — matters
  for non-cubic orbit/multiplicity counting (see symmetry.py comment). **This is
  about hkl, and applying it to a *tensor* is the opposite mistake**: a quantity
  that contracts with h twice — G\*, or the U\* form of an ADP — is invariant
  under U → R·U·Rᵀ with R **untransposed**, because (Rᵀh)ᵀU(Rᵀh) = hᵀ(RURᵀ)h. So
  `wyckoff.adp_basis` takes untransposed rotations for a metric or an ADP basis.
  The trap is that the transposed set is a group too, so the *dimension* of the
  invariant subspace is identical in every crystal system and a
  degrees-of-freedom test passes: WP-1020 built the whole indexing metric
  subspace from Rᵀ, reproduced 1/2/2/2/3/4/6 exactly, and had F = −A for
  hexagonal (the *direct* metric's cos γ) where the reciprocal metric has F = +A.
  Only asserting that the true metric lies in the span catches it.
- **Every physics function cites its reference** (author, year, journal) in
  the docstring, and documents conventions by physics not letters (e.g.
  size↔1/cosθ, strain↔tanθ; GSAS and FullProf swap X/Y labels).
- **The FitReport must never return a confident wrong singleton.** Every
  Layer-1 statement passes four gates (resolvability on the *scale-normalised*
  Gram, 0.4·FWHM validity radius, local-χ²_red significance, share-based
  global maturity); collinear angular templates are compared as *nested single
  fits* and reported non-separable rather than resolved. Confidence weights
  importance (share of χ²), not just statistical significance.
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
- **Hot-path code must not put a frozen numpy constant on the left of a python
  operator against a θ-derived value** — `ndarray * tensor` raises on the torch
  backend (and `tensor * ndarray` routes through numpy's deprecated
  `__array_wrap__`, then fails under a functorch transform). Route it through
  `xp.matmul` or lift it with `xp.asarray(c, dtype=np.float64)`; both are no-ops
  on numpy. Same rule for a *new op*: add it to `_OP_NAMES` and implement it on
  every backend — `tests/test_backend_conformance.py` fails, for every
  registered backend at once, if you don't.
- **Two things are written once and consumed everywhere; never restate either.**
  The residual **row layout** `[data | background-penalty | Pawley-restraint |
  soft-restraint]` lives in `model/rows.py` (`BLOCK_ORDER`, `layout()`,
  `assemble()`) — the numpy residual, the numpy Jacobian's row offsets and every
  traced residual build from it, so a new block is one edit. The **traced twin**
  of `decode`/residual lives in `backend/traced.py`, parameterised by `xp` — jax
  and torch share it, and a new backend inherits it. Adding a backend means
  adding a name to `backend.api.BACKEND_NAMES` and a row to
  `test_cross_backend.METHODS`; the conformance suite's meta-test fails if you
  do the first without the second.
- **Traced code runs inside `backend.traced.active(xp)`** — it makes `xp` the
  globally-bound backend *and* opens the backend's `full_precision()` scope.
  jax's fp64 is scoped, so a constant (or a θ vector) materialised outside it
  is silently float32: this cost the Pawley aux columns four orders of accuracy
  once, and is why constants are lifted inside the traced call, not at closure
  build.
- **Specimen absorption is one seam, three geometries, and their "off" states
  disagree** (`model/absorption.py`, `CompiledModel._absorption`). Capillary:
  `Geometry.mu_r`, Rouse (1970), off at µR = 0, and *exactly* a
  reparameterisation of {scale, Biso} — Rwp provably cannot move, the whole
  content is ΔB = c(µR)·λ²/2 (measured on real 11-BM SRM 660a data:
  ΔRwp 3e-8, every Biso +0.0166542 Å² against a predicted 0.0166542). Flat plate:
  `Geometry.mu_t`, ITC Table 6.3.3.1 case (2) under `bragg_brentano` and case
  (3a) under `flat_plate_transmission`, **off at µt = ∞** (thick specimen, ITC
  (1a), the assumption every flat-plate fit here made before v0.5) — so `mu_t`
  absent ≠ `mu_t = 0`, which is a specimen of no thickness and raises. It is
  *not* an exact reparameterisation (1-40 % of ln A survives the projection), so
  it moves Rwp, its ΔBiso is an order of magnitude larger and negative, and on a
  genuinely thick specimen declaring a thickness correctly makes the fit worse.
  Neither µR nor µt is refinable: µR is exactly singular, µt is merely
  ill-conditioned and knowable from the specimen, and the difference is recorded
  rather than smoothed over.
- **Instrument ⊕ sample profile split**: Gaussian *variances* add
  (instrument U,V,W + phase `gauss_size`/`gauss_strain`), Lorentzian *FWHMs*
  add (instrument X,Y + phase `lor_size`/`lor_strain`). Workflow:
  `lab_calibrate` on a standard with its **certified cell held fixed** (that
  is what decorrelates zero/displacement/cell) → `save_instrument_profile` →
  `load_instrument_profile` (everything `vary=False`) → `lab_sample_refine`.
- Atomic coordinates refine as site-symmetry DOFs: `ParameterTable` wires
  `phases.i.atoms.j.dof.k` (one per allowed direction from
  `crystallography/wyckoff.py`) and affine-ties x/y/z to them; free them with
  the `phases.*.atoms.*.dof.*` glob (the `mccusker_structural` plan does).
  Fully fixed special positions get locked coords — `vary=True` there raises.
- **Anisotropic ADPs are opt-in per atom** (`Atom.aniso`, CIF U^ij in Å²) and
  refine the same way: `phases.i.atoms.j.adp.k` patterns from
  `wyckoff.adp_basis`, freed by the `phases.*.atoms.*.adp.*` glob that every
  displacement stage carries alongside `…biso`. Unlike coordinate DOFs they
  are **absolute** (U = Σₖ θₖ·Bₖ), which enforces the site symmetry exactly;
  a tensor outside the allowed subspace raises rather than being symmetrised.
  Three representations, all named in `crystallography/adp.py` — the stored
  CIF **U^ij**, the fractional-space **U\*** = U^ij·a\*ᵢa\*ⱼ that the structure
  factor uses (U\* is what transforms as R·U·Rᵀ, making `Rᵀh` on the parent
  *identically* the image's tensor), and **U_cart** where eigenvalues and
  U_eq are physical. The isotropic limit is U^ij = Uiso·G\*ᵢⱼ/(a\*ᵢa\*ⱼ), **not**
  Uiso·δᵢⱼ except for orthogonal reciprocal axes. Non-positive-definite
  tensors raise an `ADP_NOT_POSITIVE_DEFINITE` diagnostic (the Debye-Waller
  factor diverges at high Q, so this is not cosmetic); positive-definiteness
  is not enforced by bounds, since the constraint couples all six components.
  `structure_from_cif(..., aniso=True)` is opt-in — several test CIFs carry
  aniso loops, and reading a file must not silently change what a plan frees.
- **Anisotropic strain is opt-in per phase** (`Phase.microstrain`, Stephens
  1999) and is the first width that depends on hkl rather than only on θ:
  σ²(M) = 10⁻¹²·Σ S_HKL h^H k^K l^L adds Λ(hkl)·tanθ to the *Lorentzian* FWHM.
  Same shape as the ADP story one rank up — the Laue-allowed S_HKL patterns are
  **derived** from the operators (`crystallography/stephens.py`, exact rational
  nullspace of the induced rank-4 action, sharing `wyckoff._nullspace_int`),
  refine as absolute DOFs `phases.i.microstrain.dof.k`, and an out-of-subspace
  set raises. Three conventions are load-bearing and stated in that module:
  √Σ·d²·10⁻⁶ is the **FWHM** (not σ) of the ΔM/M distribution; the coefficients
  are in **10⁻¹² Å⁻⁴** (physical Å⁻⁴ values ~10⁻⁸ would be finite-differenced
  with a step 100× their own size); and they multiply the **literal** monomials,
  where other codes fold symmetry multiplicities in. A block **locks
  `lor_strain`** — its isotropic direction is identically that column, the
  `biso`/`aniso` bargain again — so the block subsumes it, and it must be freed
  *in* the sample-broadening stage, not after. The isotropic limit S = ε²·[M²]
  (exactly in the subspace, whatever the symmetry) is both the seed and the only
  legal start: at S ≡ 0 the √ has unbounded slope, so `Stage.strain_seed`, not
  `Stage.seed`, which reaches softplus entries only. σ²(M) ≥ 0 is a *cone*
  coupling all fifteen, so it cannot be a box bound: under the default TRF
  driver it is a guard (`STEPHENS_STRAIN_NOT_POSITIVE`), and under
  `solver="lm"` (WP-0601) it is carried as a linear inequality and the guard
  falls silent because there is nothing left to report. Read a firing as "these
  coefficients are not quotable", never as evidence *of* anisotropy. **Zero is
  on the cone, not outside it** — the guard's test is one-sided, and the ≤ 0
  form it had before v0.6 reported the inert all-zero block as unphysical,
  which is what produced the since-withdrawn claim that it "fires on isotropic
  and anisotropic specimens alike". Re-measured: brucite leaves the cone on 12
  of 43 reflections unconstrained and 0 of 43 under `solver="lm"`; corundum
  never leaves it at all.
- **Anomalous scattering is ON by default since v1.0** (`Source.dispersion`, f = f₀ +
  f′ + i·f″ from bundled Cromer-Liberman `data/f1f2_CromerLiberman.dat`), and
  the load-bearing part is *not* that f goes complex — F always was. It is that
  `generate_reflections` merges ±h into one Laue orbit and evaluates a single
  representative, which is exact only while f is real: with f″ ≠ 0 in a
  non-centrosymmetric group |F(h)|² ≠ |F(−h)|², and both land in the *same*
  powder peak. So `structure_factors_squared` returns the **Friedel average**,
  in the exact closed form ⟨|F|²⟩ = |A|² + |B|² with A carrying f₀+f′ and B
  carrying f″ over the *same* orbit sums — no second orbit pass, no
  centro/non-centro case split, and B ≡ 0 recovers |F|² bit-identically (which
  constrains the fp *association order* in `_orbit_terms`, not just the
  algebra). f′/f″ are frozen at stage compile onto `PhaseSites.f_anom`: they
  depend only on species and λ, and `EmissionLine.wavelength` is a plain float,
  so they can never be a function of θ. One |F|² is shared across emission
  lines, *guarded* rather than smeared — `dispersion.resolve` raises when a line
  differs from the primary by more than 1 % of Z (an edge between them). Near an
  edge the table is wrong in principle, not merely coarse, so that is refused
  too and `Dispersion.overrides` takes measured pairs. It is the **only**
  correction here needing no information the caller does not already have
  (µR, a habit, a strain model, a surface — dispersion wants species and λ),
  which is why WP-1001 made it the default; `dispersion = None` declines it and
  reproduces every ≤ v0.6 number bit-identically, and `DISPERSION_NEGLECTED`
  then says so. **Every test that pins a number declares this setting
  explicitly rather than inheriting it** — a suite whose numbers move when a
  default moves is not pinning a protocol, and `tests/test_validation_matrix.py`
  enforces it for the acceptance suites. Ions resolve to the element
  (core-level effect), unlike ionic f₀.
- History nodes store **state, not curves** (a node is ~10 kB; embedding
  y_calc would make it ~1.24 MB). Their cached metrics are *as-optimised* —
  measured on a model frozen at the values each stage *started* from — so
  `refine.replay`, which recompiles at the values the stage *ended* on, can
  differ marginally. That gap is a staleness signal, not a bug. Le Bail
  extracted intensities live outside θ and are path-dependent, so they are
  serialized per node (`ReflectionState`); Pawley will reuse that container
  rather than adding one dot-path per reflection to `free_paths`.
- Emission-line weights are relative to line 0, which is structurally locked
  at 1 (degenerate with phase scales); `set_vary` globs can never free locked
  entries (also protects symmetry-fixed cell angles).
- `RefinementResult.ticks` carries **every emission line's** positions, not
  just the primary — otherwise Layer 0 flags each Kα2 peak as an unindexed
  impurity (this was a real bug, caught by the misfit-injection suite).
- Tests: fast unit/property tests always; real-data acceptance marked
  `@pytest.mark.slow` (`test_acceptance_nac.py`, `_srm660c.py`, `_fap.py`,
  `_capillary.py`).
  Reference values and data provenance in `tests/data/README.md`. Every test
  refinement also writes obs/calc/diff PNGs to `tests/output/` (gitignored)
  for visual inspection — Rwp hides locally-bad fits.
- **CI runs the same commands** (`.github/`), on cadences set by a **free-tier
  budget** — 2000 Actions minutes/month on a private repo, billed per job
  rounded up, so an over-budget config buys a month with no CI rather than a
  bill. Per push: ruff + the fast suite on 3.13, Linux, skipped entirely for
  docs-only pushes (5 billed min). Weekly: the full suite plus 3.11/3.12/3.14
  (55). Monthly: macOS and `[torch]` (66 — macOS bills at **10×**).
  **Before adding a job, price it**: the first version of this matrix cost 21
  minutes per push and 1350 a month, which did not fit. Two consequences for
  local work. **The bit-identity goldens are pinned to `darwin/arm64`**
  (`GOLDEN_PLATFORM` in `tests/test_backend_shim.py`) and *skip* elsewhere:
  measured, Linux x86-64 diverges by 1 ulp to 1.7e-13 relative — a libm and
  summation-order difference — so the gate is asserted where it was captured
  rather than loosened to a tolerance it could never distinguish from a real
  change. And **`tests/.jax_cache` is why the jax rows feel free locally** —
  deleting it takes the two jax files from ~12 s to 107 s — but caching it in
  CI was measured and does *not* help (8:18 warm against 8:12 cold): jax's
  persistent cache holds only XLA compilations above a time threshold, while
  per-process tracing and lowering are paid every run.
- **A refinement that two suites both need is computed once, in
  `tests/conftest.py`** (`sample1_results`, `srm660c_baseline`), and **every
  consumer must carry the matching `@pytest.mark.xdist_group`** — otherwise a
  second worker rebuilds the whole fixture and the sharing costs more than it
  saved. Same rule one scope down: a module fixture several tests share pins
  its module (`nac`, `capillary`, `srm660c`, `stephens-brucite`, …). The
  failure is silent, so the check is a `--durations` scan for the same setup
  appearing twice. Because runtime is set by the longest *group*, not by total
  work, splitting a group is the only way to go faster — and un-sharing a
  fixture to do it just moves the cost.
- Comparing against another code means **adopting its protocol**, not just
  its numbers: mirror its refine flags, held parameters and excluded regions,
  then check the channel count matches before believing any Rwp comparison.

## Roadmap & how to work on it

Planning docs are split so a session loads only what it needs — do not read
them all:

- `docs/ROADMAP.md` — thin index: milestone table, work-package (WP) index,
  "Current focus", and the session protocol.
- `docs/wp/NNNN-*.md` — one **self-contained** WP per task (context, commit-
  sized checklist, acceptance command, handover log).
- `docs/DESIGN.md` — design record; read only the section a WP links.
- `docs/milestones/vX.Y.md` — shipped records with measured acceptance blocks.

**Protocol**: to work on the roadmap, read the active WP file (named under
"Current focus" in ROADMAP.md) and nothing else. Commit per checklist item,
prefixed `WP-NNNN:`. Before ending any session that touched a WP — or when
interruption threatens — append a dated handover-log entry (done / in flight /
next / gotchas) and sync its Status glyph into ROADMAP.md's index. When a
milestone ships, record measured acceptance in `docs/milestones/` and flip
the ROADMAP.md row.

Because sessions never read other WP files, **a handover log only reaches your
own successor on the same WP**. Anything you learned that changes work in a
not-yet-started WP — a constant now exported for reuse, a design bullet there
that has gone stale, a deferral into it, a gotcha that would mislead it — goes
in *that* WP's `### Inherited` section, naming yours as the source
(ROADMAP.md step 3b; slot defined in `docs/wp/TEMPLATE.md`).

Shipped: **v0.1** (synchrotron vertical slice), **v0.2** (2026-07-22: lab
Bragg-Brentano, analytic Jacobian, background automation, FitReport L1-2,
history DAG, live viz), **v0.3** (2026-07-24: coordinate refinement, anisotropic
ADPs, QPA weight fractions, Brindley microabsorption, Pawley whole-pattern mode,
March-Dollase preferred orientation, multi-histogram, exporters — WP-0301…0310,
measured acceptance in `docs/milestones/v0.3.md`: SRM 676a cell anchor via c/a
(+30 ppm) plus the IUCr QPA round robin with participant-spread-referenced
tolerances), **v0.4** (2026-07-27: differentiable backends — WP-0401…0408,
measured acceptance in `docs/milestones/v0.4.md`).

**v0.5 — corrections & microstructure** (2026-07-28: capillary absorption 0501,
surface roughness 0502, Stephens anisotropic strain 0503, anomalous f′/f″ 0504,
sequential series 0505, secondary extinction 0506, anode wavelengths 0507,
flat-plate absorption + the real-data capillary acceptance 0508; measured
acceptance in `docs/milestones/v0.5.md`). Its method result is worth carrying
into any future correction: **not one of the eight is well judged by Δ Rwp** —
two provably cannot move it, one moves it the *wrong way* when it is right, and
the two largest accuracy wins are invisible in it. So a new correction ships
with a record field or a diagnostic that states what it changed, never with an
Rwp comparison as its evidence.

**v0.6 — solver, performance & agents** (2026-07-29: batched-peak-loop no-go
with the FCJ node memo shipped instead 0605, bounded LM with the Stephens cone
as a linear inequality 0601, agent JSON surface 0602, Sphinx + MyST theory
manual 0604; measured acceptance in `docs/milestones/v0.6.md`). The **theory
manual** lives in `docs/manual/` and is guarded against drifting from the code
by `tests/test_manual.py`: the build runs `-W` in the fast suite, fenced
constants are MyST substitutions injected from the live package in
`docs/manual/conf.py` (a new fenced constant needs a line there *and* a use in
a chapter), every displayed equation carries a `*Source:*` line whose symbol
must import, and every bib entry must be cited. Consequence: renaming a
physics symbol or retuning a fenced constant means touching the manual in the
same change.

**In flight: v1.0 — hardening, human GUI, indexing, API freeze, PyPI.**
`pyproject.version` tracks the milestone *in flight* (1.0.0.dev0), not the
last one shipped, because that string is stamped into every
`RefinementResult.provenance` and history node. The GUI (WP-1004…1017,
expanded into v1.0 on 2026-07-29) lands *before* the freeze (WP-1003) so the
freeze covers an exercised surface; stack decision in DESIGN.md §Outputs.
**Indexing** (WP-1018…1027, added the same day) lands before the freeze for the
same reason — `index()` is a peer of `refine()`, and until it exists the
package cannot touch a phase whose cell is unknown. Its governing rule is the
FitReport's one rank up: an indexer must never hand back one cell confidently,
so `IndexingResult` has **no** `.cell`/`.best` attribute, only a gated
`best_or_none()`; geometrical ambiguity (Mighell & Santoro 1975) is reported
with the reflections that would break the tie rather than silently resolved;
coverage is scored in *both* directions because ranking on
share-of-observed-intensity alone demonstrably puts a 390-line wrong phase
above the truth; and a restricted search reports `systems_searched` rather than
concluding anything about the sample. Engines supply the confidence by
**agreeing**, the same device as `direction="both"` and the cross-backend matrix —
**two** of them, not three: the whole-profile Monte Carlo is a measured no-go
(WP-1023), so `high` confidence means both landed engines agree and that is the
ceiling rather than a shortfall.

Everything the engines share is `indexing/engines.py` — one `SearchSpec`, one
`EngineResult` (carrying the `CandidateFit`, because consensus dedup is a χ² test
that needs `cov_af`), the live registry the agent schema quotes, `Budget`, and the
`reflection_ceiling_ok` crash guard that stands in front of every
`generate_reflections` call a search reaches. `search_dichotomy` bounds Q over boxes
in A..F (corner-exact, because Q is linear in the metric) and its silence is evidence
*only when* `search_complete[system]` is true; `search_trial_error` assumes the
indices of a few base lines and solves the metric exactly, so a bad base line poisons
it where a wide domain poisons the other. Both rank on the FoM **panel** via
`rank_candidates`, never on a member — supercells index every observed line exactly
and lose only on `predicted_seen_fraction`.

**The tolerance an engine searches with is not the per-line σ, and this is the one
thing to know before touching indexing.** A fitted σ(2θ) is the right *weight* and
the wrong *matching window*: measured on the bundled qarr corundum pattern, whose
cell is certified, the lines sit a median 0.060° from the true positions (a cos θ
displacement) against a median fitted σ of 0.0056° — an 11σ systematic — so at 3σ the
true cell indexes **zero** lines and both engines return nothing. Hence
`DEFAULT_UNKNOWN_SHIFT_DEG` (0.05° 2θ, added in quadrature whenever no shift has been
*measured*, reported as `INDEX_SHIFT_ALLOWANCE` because an assumed precision must
never look like a measured one) and `refine_with_shift`, which fits the shift template
to a candidate **after** it survives — a shift is identifiable only against reference
positions, and a candidate cell is what supplies them. A cell found under a widened
window but never shift-refined is biased by roughly the shift (+1400 ppm measured).
Closing this on real data is WP-1026.

**v0.4 — differentiable backends.** `backend=` takes `"numpy"` (the default and
the only one anyone needs), `"jax"`, or the **experimental** `"torch"` (CPU
fp64) / `"torch-mps"` (Apple GPU, necessarily fp32) — never installed by
default, kept as an independent opinion in the agreement matrix and as the
route to using the forward model as a differentiable layer (DESIGN.md, "What
the differentiable core unlocks"). Every backend is held to per-column
agreement with the analytic Jacobian in `tests/test_cross_backend.py` — whose
configs must grow whenever a *new derivative path* does, or no backend row
covers it. Also landed: true Voigt
(`Instrument.profile.shape="voigt"`, one shared Weideman Faddeeva `w(z)`, TCHZ
still the default), soft bond/angle/value restraints (extra residual rows below
the data, Rietveld and single-histogram only), and the Bérar-Lelann esd fix
(reported esds now carry the inflation; the correlation matrix is a true Pearson
matrix and the 0.98 guard is live). Apple-GPU execution is *slower* than numpy
(46-182×, launch-latency-bound) — `torch-mps` buys precision validation, not
speed; the measured break-even (≈65 k elements per kernel) and ceiling (≈2.5×)
are in the v0.4 record. v2 fence:
FPA, neutron/TOF, spherical-harmonics texture, MCP server.

Key test data (provenance + every reference value in `tests/data/README.md`):
- `11BM_NAC.fxye` — APS 11-BM synchrotron, λ=0.4139090 from the .prm; NAC +
  CaF₂ impurity; acceptance expects a≈10.2513, Rwp<0.12.
- `nist_srm660c_100a.cif` — NIST LaB6 certification data, CuKα doublet +
  graphite analyzer; fits the `…_meas` block with zero fixed / displacement
  refined; expects a≈4.15678±2e-4, Rwp<0.10. **Absolute** anchor.
- `FAP.XRA` + `FAP.EXP` — GSAS-II LabData tutorial fluorapatite; the `.EXP` is
  GSAS's converged fit and supplies both the reference values and the protocol
  the test mirrors. **Cross-code consistency** check (±300 ppm), not truth.
- `qarr/*.prn` — IUCr CPD QPA round-robin patterns (samples 1a-1h, 2, 4 + six
  pure phases; plain 2-column ASCII, Cu Kα doublet, graphite diffracted-beam
  mono). QPA truth is the **weighed composition**; tolerances referenced to
  the published participant spread, never to σ(W). `corundum.prn` doubles as
  the SRM 676a cell-anchor specimen (c/a is the certificate-grade assertion;
  absolute axes carry lab d-scale systematics).

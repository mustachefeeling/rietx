# CLAUDE.md — pxrd-refine

API-first Rietveld refinement package (powder XRD). MIT. numpy/scipy fp64
core, pydantic v2 schemas, gemmi for CIF/symmetry. Import name: `pxrdref`.

## Commands

```sh
uv venv --python 3.12 && uv pip install -e ".[dev]"   # setup (once)
uv pip install -e ".[dev,jax,torch]"                   # + optional jax/torch backends
.venv/bin/python -m pytest -n auto --dist loadgroup    # full suite ~8-15 min, incl. real-data acceptance (counts: Current numbers)
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"   # skip acceptance, ~1-3 min
.venv/bin/python -m pytest tests/test_cross_backend.py # Jacobian agreement matrix; rows self-skip without their backend
.venv/bin/python -m ruff check src tests examples      # lint (must be clean)
.venv/bin/python examples/nac_11bm.py                  # end-to-end demo + plot
.venv/bin/python -m sphinx -W -q -b html docs/manual docs/manual/_build/html  # theory manual
.venv/bin/pxrdref gui my_sample.pxrd                   # the refinement GUI (localhost:8731)
npm --prefix gui ci && npm --prefix gui run build      # rebuild the GUI's committed dist
npm --prefix gui test && npm --prefix gui run check    # vitest (jsdom mount, fnmatch parity, panel/text-sync/model-edit/3D-trace/splitter/theme/plot/peaks logic; count: Current numbers) + svelte-check
.venv/bin/pxrdref watch <live-dir>                     # live viewer for a LiveSession run
.venv/bin/pxrdref compare --open                       # settings-comparison UI on the standards
```

`-n` is deliberately **not** in `addopts`: a bare `pytest tests/x.py::y` stays
serial, so `-s` and pdb keep working. `--dist loadgroup` is not optional
either — it is what honours the `xdist_group` marks that keep a shared fixture
on one worker (see `tests/CLAUDE.md`); plain `--dist load` ignores them and
silently refits.

Headline testing rules — operating detail and evidence in `tests/CLAUDE.md`,
the dated measurement diary in `docs/milestones/v1.0.md` § Appendix:

- **Quote wall clock as a range, never as a figure** — machine state moves it
  further than most changes do; compare runs, not records. And **quote the
  extras with any count**: a bare "N tests" means nothing without the venv it
  was measured in.
- **One dataset, one group**: runtime is set by the longest xdist group, and
  a group ordering is a measurement with a shelf life — re-read `--durations`
  rather than the last session's sentence about it.
- **A wall-clock budget inside a test is a runaway guard, never a timer** —
  if the declared budget is not several times the serial time, the assertion
  is a load sensor. The budget a test depends on may be one rank down, in
  the library.
- **When a budget fix makes something slow, narrow the scope, never the
  budget** — and never a silent cap.
- **Say which numbers moved**: after adding N tests, passed+skipped moves by
  exactly N in both selections, and a new skip is not a new pass.

### Current numbers

Replaced at every handover, never appended (history: the v1.0 appendix). Measured
2026-08-05 at the **WP-1041** handover, darwin/arm64 M4, `worktree-indexer`, venv
`[dev,jax]`, no torch — **WP-1034's `[dev]` figures do not compare**.
- fast: **1743 / 67 skipped**, 3-4 min — 1040's 1738 **+5**: seven added, one deleted
  (`svd`'s scale-invariance pin, subsumed by the shared key's), one *moved* to `slow`
  (`INDEX_DOMINANT_ZONE`). full: **1841 / 72**, 25-36 min, **+6** — that move is the
  whole difference between the deltas; no new skip. `test_acceptance_indexing.py`
  sets the clock: **38 rows, 13-14 min**.
- frontend (vitest) **330**, `svelte-check` clean, `test_gui_*.py` collect **81**;
  1040/1041 touched no `gui/` file. **A module-level `importorskip` collapses its
  module into one skip**, so `--collect-only` undercounts (`tests/CLAUDE.md`).

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

`capabilities()` (WP-1007, `capabilities.py`) is the one call that says what this
build can do — backends *with whether each optional dependency imports here*,
solvers, plans from `PLAN_INFO`, modes, anodes, the formats `read_pattern` opens,
and the **five** versioned contracts (schema / report-thresholds / event-schema /
project-format / textdoc-format — in the arm rather than in prose because a
client reads the field list, and a meta-test fails on a `*_version` field that
is not the constant it claims to quote). **Every arm is quoted from a live registry and a meta-test fails
on a member missing from its arm**; `features` flags are *derived predicates* (a
schema field's presence, a top-level export's existence), never literal `True`,
so a flag flips by itself when its feature lands. **A derived flag still rots,
and it rots silently**: the `hasattr` name and the real export drift together
while the test asserts the flag's own expression — `features["indexing"]` spent
its whole life `False` this way (`index` vs `index_pattern`, fixed WP-1037). So
each surface flag's export name is *data* (`_SURFACE_FLAGS`), the flags derive
from that table, and a meta-test checks every name in it against `__all__`.
Guard hits are `GuardFinding(code, paths, value, message)` — `GuardReport`'s six
fields hold those, `str(finding)` is the pre-v1.0 text byte for byte (pinned by
test, because the diagnostics' messages are built from it), and every guard
`Diagnostic` now carries its paths in `where`, `HIGH_CORRELATION` included. Add a
new guard by adding a `GuardFinding` constructor there; `code` is deliberately an
open vocabulary, not a `Literal`.

A **project** (WP-1005) is a `.pxrd/` **directory** — `project.json`, the pattern
file copied byte-for-byte, `history.jsonl`, `live/`, `exports/` — opened and
saved through `Project.create/open/save` (`project.py`, `schemas/project.py`). A
directory, not an archive: the log's crash safety is append-only writes by one
writer, and rewrite-on-save would lose it. **One authority per fact.**
`project.json` holds the *settings* — selected plan/mode/limits, excluded
regions, the GUI's own `ui` keys — while `history.jsonl` holds the model state
and its head *is* the working state, so no parameter value is duplicated
between them and **saving is about settings, not durability** (the tree exists
from `create`, so every `set_vary`/`set_value` is already on disk). Two things
follow from the pattern being a file rather than a `PatternData`: the bytes are
the contract (the readers' esd column is never overridden), and the **reader
call** is part of the reference — `DataRef` records which
`io.readers.PATTERN_FORMATS` entry claimed the file plus its options, because a
pdCIF with a `_meas` and a `_calc` block is a different pattern depending on
`block`. It carries sha256 of the bytes *and* the parsed-array fingerprint on
purpose: agreeing bytes with a disagreeing fingerprint is a reader change, not a
corrupt project. `excluded_regions` live in the document because they are
protocol that is in neither the file nor `RefinementState` — a node cannot say
what was excluded when it ran. Two rules follow (WP-1033):
`Project.fitted_mask()` is the one authority for **which channels the next run
fits** (`compile_model`'s first act, pinned by asserting `len(result.two_theta)`
against its sum), and an inverted or empty interval is **refused, not reordered**
by `schemas.project.check_interval` — one sentence the verb, the `.pxt` parser
and the document's own validators all quote.

Entry points: `Refinement.fit()` / `refine()` in `refine.py`; modes
`"rietveld"`, `"lebail"` (intensity partitioning in
`CompiledModel.lebail_update`) and `"pawley"` (per-hkl intensities refined as
an off-table θ block — `model.forward.PawleyBlock`, appended in
`run_least_squares`; overlapped groups get equal-split restraints and come back
flagged `PAWLEY_OVERLAP_UNRESOLVED` rather than confidently split). For
tool-calling there is `agent.refine_json(dict) → dict` (`agent.py`, WP-0602):
one call covering refine/refine_multi/refine_sequential/**index** behind a strict
task union, errors as a structured `{ok:false, error:{code,…}}` envelope (never a
traceback), and `agent.tool_definition()` exporting the JSON Schema with the
backend/solver/plan/**engine** names quoted from the live registries — a meta-test
fails if a registry member is missing from the schema. The four answers live in
separate arms (`result` / `series` / `indexing`) because they are different
*shapes*, and for indexing the shape is the rule: the serialized answer carries no
`cell` key either.

### GUI

The **GUI** (WP-1008…1015, 1029, 1032-1034) is `pxrdref gui [PROJECT.pxrd]` — stdlib
`http.server` on 127.0.0.1 serving a committed Svelte 5 dist. `gui/session.py`
holds every verb as a plain method and nothing there knows about HTTP;
`gui/server.py` is the wire layer a Tauri host would replace. The rulebook —
server contract, `.pxt` text document, editors, panels, 3D viewer, theming —
is `gui/CLAUDE.md` (loads when working under `gui/`; `src/pxrdref/gui/`
carries a pointer stub). Two rules matter outside the GUI too: mutating verbs
return **409 while a run is in flight** (frozen-per-stage discreteness
enforced structurally), and the **run state is not an event** — `EventKind`
is closed, and `live/events.jsonl` stays the one stream `watch` tails.

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
- **Every weighted residual in the package divides by
  `RefinementResult.sig()`** — the matplotlib panel, the plotly export, the VLM
  montage, Layer 0 and the GUI window — a peer of `PatternData.sig()`, where the
  esd-column/Poisson choice was already made: `CompiledModel` stores
  `pattern.sig()` and `refine` copies it to `result.sigma` verbatim, so a
  result's σ is a *lookup*, never a re-derivation (five call sites open-coded
  it under three policies before WP-1029 (s), whose file has the story). The
  bug hid beside the fallback, not in it: `weighted` meant `bool(result.sigma)`
  — constant-true — so a Poisson fit was labelled `(obs−calc)/σ` as though its
  σ had been measured. **`weighted` is `DataRef.has_sigma`** (σ *measured*, not
  σ *present* — the fact `textdoc` renders as "σ from file"), `delta` is always
  Δ/σ because Δ/σ is what the fit minimised either way, and the flag changes
  only the axis title. A test that recomputes a residual cannot catch this
  class of bug: the pin compares what each renderer **drew** against what the
  route **sent**.
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
- **Cell ties follow the space-group *setting*, never the crystal system** —
  `crystallography.symmetry.cell_constraints(sg)` is the one authority, and
  `ParameterTable` is its only caller. Three settings disagree with the system
  alone: monoclinic has three unique-axis choices (`monoclinic_unique_axis()`),
  an R lattice on **rhombohedral** axes (`sg.ext == "R"`) needs a = b = c with
  α = β = γ free rather than `b ← a` with c free, and the `:1`/`:2` extensions
  are origin choices that leave the metric alone. **`read_small_structure`
  picks the R setting from the cell**, so a bare `R -3 c` over a rhombohedral
  cell arrives as `:R` — no non-standard symbol needed. This is the Rᵀ trap one
  rank down and it fails the same way: the free-parameter *count* is right in
  every broken case (2 for both R settings, 4 for all three monoclinic ones), so
  assert **which** angle is held and **which** length follows which, never how
  many — 79 of gemmi's 564 settings were served wrong under a correct count. A symmetry-fixed angle is **refused** when it disagrees with its
  symmetry, not normalised — the table has no diagnostics channel, so an edit
  there could not be made visible, and it is held at its stored value, which is
  how a monoclinic β = 93.2° once survived under an orthorhombic symbol.
- **Every physics function cites its reference** (author, year, journal) in
  the docstring, and documents conventions by physics not letters (e.g.
  size↔1/cosθ, strain↔tanθ; GSAS and FullProf swap X/Y labels).
- **The FitReport must never return a confident wrong singleton.** Every
  Layer-1 statement passes four gates (resolvability on the *scale-normalised*
  Gram, 0.4·FWHM validity radius, local-χ²_red significance, share-based
  global maturity); collinear angular templates are compared as *nested single
  fits* and reported non-separable rather than resolved. Confidence weights
  importance (share of χ²), not just statistical significance.
- **A new correction ships with a record field or a diagnostic that states
  what it changed — never an Rwp comparison as its evidence.** v0.5's
  measured method result: of eight corrections, two provably cannot move
  Rwp, one moves it the wrong way when it is right, and the two largest
  accuracy wins are invisible in it (`docs/milestones/v0.5.md`).
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
  on the cone, not outside it** — the guard's test is one-sided; the ≤ 0 form
  before v0.6 flagged the inert all-zero block as unphysical (the source of a
  since-withdrawn claim — v0.6's record has it). Re-measured: brucite leaves
  the cone on 12 of 43 reflections unconstrained and 0 of 43 under
  `solver="lm"`; corundum never leaves it at all.
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
  correction needing no information the caller lacks — species and λ suffice —
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
- Tests, timing, budgets, CI: `tests/CLAUDE.md` (loads when working under
  `tests/`); the headline rules are in Commands above.
- Comparing against another code means **adopting its protocol**, not just
  its numbers: mirror its refine flags, held parameters and excluded regions,
  then check the channel count matches before believing any Rwp comparison.
- The **theory manual** (`docs/manual/`) is guarded against drift by
  `tests/test_manual.py`: the build runs `-W` in the fast suite, fenced
  constants are MyST substitutions injected from the live package in
  `docs/manual/conf.py`, every displayed equation carries a `*Source:*` line
  whose symbol must import, and every bib entry must be cited. Renaming a
  physics symbol or retuning a fenced constant means touching the manual in
  the same change.

## Roadmap & how to work on it

Planning docs are split so a session loads only what it needs — do not read
them all:

- `docs/ROADMAP.md` — the index: session protocol, a ≤40-line "Current
  focus", milestone table, WP index.
- `docs/wp/NNNN-*.md` — one **self-contained** WP per task (context, commit-
  sized checklist, acceptance command, handover log).
- `docs/DESIGN.md` — design record; read only the section a WP links.
- `docs/milestones/vX.Y.md` — one record per milestone: measured acceptance
  at ship, plus (while in flight) the running "How vX.Y is getting here"
  narrative and the dated appendices. `v1.0.md` is the live one.
- `docs/LITERATURE.md` — where the papers physically are, and which are unread.
  **Search the local corpus before asking for a paper or re-deriving a published
  constant**: `sqlite3 /Users/yue/zotero-linker/index.sqlite` (table `documents`,
  columns `title`/`md_path`); the lesson that pinned this rule is in that file.
- `docs/AGENT_PROTOCOL.md` — consumer-facing operator guide; a WP that adds
  a diagnostic code or a correction adds its row there.
- `gui/CLAUDE.md`, `tests/CLAUDE.md` — subsystem rulebooks; they load with
  their subtrees, so nothing here restates them.

**Protocol**: `docs/ROADMAP.md` § Session protocol is the one authority. In
short: read the active WP file and nothing else; commit per checklist item
prefixed `WP-NNNN:`; end every session that touched a WP with
`/wp-handover`; a CLAUDE.md takes **rules, not findings**.
`tests/test_docs_consistency.py` enforces the mechanical parts.

Shipped: **v0.1 … v0.6**, one record each in `docs/milestones/` (the
milestone table in ROADMAP carries the acceptance one-liners — neither is
restated here).

**In flight: v1.0 — hardening, human GUI, indexing, API freeze, PyPI.**
`pyproject.version` tracks the milestone *in flight* (1.0.0.dev0), not the last one
shipped, because that string is stamped into every `RefinementResult.provenance`
and history node. The GUI (WP-1004…1017) and **indexing** (WP-1018…1027) both land
*before* the freeze (WP-1003) so it covers an exercised surface; grounds in the
v1.0 record. Indexing's governing rule is the FitReport's one rank up: an indexer
must never hand back one cell confidently, so `IndexingResult` has **no**
`.cell`/`.best` attribute, only a gated `best_or_none()`; geometrical ambiguity
(Mighell & Santoro 1975) is reported with the reflections that would break the tie
rather than silently resolved; coverage is scored in *both* directions because
ranking on share-of-observed-intensity alone demonstrably puts a 390-line wrong
phase above the truth; and a restricted search reports `systems_searched` rather
than concluding anything about the sample. Engines supply the confidence by
**agreeing**, the same device as `direction="both"` and the cross-backend matrix —
**three** of them (two until WP-1040), and `high` means *every* engine that ran found
the lattice, so adding one raises the bar rather than diluting it. They must fail
differently for that to mean anything, and they do: a wide domain (dichotomy), a
poisoned base line (trial_error), a bad starting basin (svd). The same rule runs one
step further into the workflow: the **extinction symbol**, not the space group, is
what a powder measures, so `determine_extinction_symbol` answers with a ranked list
of classes and every class carries a *list* of space groups — the one place in the
package where the singleton is not merely unsupported but unmeasurable.

`index_pattern(peaks | data+instrument)` (`indexing/workflow.py`) runs that
pipeline: quality gate → engines → `indexing/consensus.py` (merge on the reduced
cell, `found_by` union, Borda over the panel, two-opinion Bravais, ambiguity) →
Le Bail validation → the gate. Three rules there are load-bearing. **`high`
requires zero caveats**, and `IndexCaveat`/`INDEX_REFUTING_CAVEATS`
(`schemas/indexing.py`) are the whole gate: five caveats refute a cell and drop it
to `low`, the rest cap it at `medium`, and *count* deliberately does not separate
medium from low. **Whole-profile validation is mandatory** — the FoM panel sees ≤20
lines and cannot see reflections predicted where there is no intensity, so
`validate_by_lebail` reports `predicted_but_absent`, which is what catches an
oversized cell (117 of 153 reflections for a doubled cell against 0 of 28 for the
truth, while Rwp moves only 0.216 → 0.379). Layer 0's `unmatched_calc` **cannot**
serve as that detector: Le Bail extraction assigns ~nothing to a phantom reflection,
so it fires on 61 % either way. **The validation fit holds the cell** and frees
exactly one peak-position parameter, from the candidate's own shift template. And on
real data with no measured shift, `high` is currently *unreachable* by design
(`shift_allowance_assumed`); the fix is evidence, not a bigger constant (WP-1026).

Everything the engines share is `indexing/engines.py` — one `SearchSpec`, one
`EngineResult` (carrying the `CandidateFit`, because consensus dedup is a χ² test
that needs `cov_af`), the live registry the agent schema quotes, `Budget`, and the
`reflection_ceiling_ok` crash guard that stands in front of every
`generate_reflections` call a search reaches. `search_dichotomy` bounds Q over boxes
in A..F (corner-exact, because Q is linear in the metric) and its silence is evidence
*only when* `search_complete[system]` is true; `search_trial_error` assumes the
indices of a few base lines and solves the metric exactly, so a bad base line poisons
it where a wide domain poisons the other; `search_svd` (WP-1040) proposes a metric at
random and alternates "assign each line to its nearest calculated one" with "re-solve
A..F from that assignment" until the assignment stops changing — **no tolerance to
search with**, failing instead on a bad starting basin, the only *stochastic* engine
(`SearchSpec.seed` is part of its answer and must never come from `hash()` of a name,
which python salts per process) and the only one whose search reads observed
intensities. All three rank on the FoM **panel** via `rank_candidates`, never on a
member — supercells index every observed line exactly and lose only on the reversed
members. There are **seven**: M₂₀, F_N, three coverage fractions, and Oishi-Tomiyasu
(2013)'s `m_rev`/`m_sym`, whose whole content is that the reversed direction is a
*ratio* where ours is a windowed fraction — measured on a doubled axis, `m_rev`
separates truth from supercell 64-74× where M₂₀ separates them 1.8×. Its `N^cal` is
Σ 1/m over centring-allowed triples and is **never rounded**: Σ 1/m over a complete
orbit is exactly 1, so an integer result is the *self-check* that the multiplicity is
right, while a hexagonal orbit cut by the box legitimately contributes a fraction.
Two things the panel needs from its caller (WP-1026): the **matching window** is an
argument (`fom_panel(..., q_match=)`) separate from the per-line σ, because coverage
members must ask the same "is this the same line" question the *search* asked while
M₂₀ and F_N floor their discrepancy on what the measurement resolves; and a candidate
carrying a fitted shift is scored on `engines.scored_positions`, the **corrected**
lines it actually claims, or the panel marks it down for its own correction.

**The search window is a correctness parameter, measured rather than assumed**
(WP-1038, `indexing/pairs.py`). A *harmonic reflection pair* — planes that are
integer multiples, so `m·sin θ_B = sin θ'_B` for any lattice — is one equation in
the shift and none in the cell, so Dong (1999) gives its **magnitude** from the
peak list alone and `ShiftScreen.allowance_deg` is what a window must span. Four
measured rules, stories in the appendix. **The magnitude is knowable with no
reference and the cause is not** — `constant` and `cos_theta` concentrate
identically, so the screen may refute `sin_2theta` and never choose between the
other two. **Detection is concentration against a seeded structureless null,
because the published false-pair rule fails on real data** (DICVOL04's margin
admits 11-BM NAC at chance, reporting −0.09° where the shift is zero). **A window
wider than the shift manufactures a confident wrong singleton** — at σ_sys = 0.060
SRM 660c returns a cell 293 000 ppm off at `high` confidence — so headroom scales
the amplitude's *standard error*, never the pair scatter. And **an allowance is
not a correction**: it finds lines, only `shift_template` moves the cell.

**The tolerance an engine searches with is not the per-line σ, and this is the one
thing to know before touching indexing.** A fitted σ(2θ) is the right *weight* and the
wrong *matching window*: measured on the bundled qarr corundum pattern, whose cell is
certified, the lines sit a median 0.060° from the true positions (a cos θ displacement)
against a median fitted σ of 0.0056° — an 11σ systematic — so at 3σ the true cell
indexes **zero** lines and both engines return nothing. Hence
`DEFAULT_UNKNOWN_SHIFT_DEG` (0.05° 2θ, the fallback when the pair screen above
declines, reported as `INDEX_SHIFT_ALLOWANCE` because an assumed precision must never
look like a measured one) and `refine_with_shift`, which fits the shift *template*
**after** a candidate survives — the *shape* needs reference positions, which a candidate
cell supplies. A cell found under a widened window but never shift-refined is biased by
roughly the shift (+1400 ppm measured).

Fourteen more indexing rules, each learned the hard way — the measured stories are in
the v1.0 record's appendix ("the CLAUDE.md indexing dossier"), constants in `indexing/`:

- **A filter inside a search fails with a wrong *answer*, so a silence indicts the
  filters before the tolerance.** `engines.solution_key` is the one dedup authority —
  quantised **scale** *and* **centring**, claimed before scoring, so a *rejected*
  metric poisons its whole shape family (scale invariance merges every uniform
  rescaling: a cell collides with its own supercell). It lost a cubic-I truth and
  fired `INDEX_DOMINANT_ZONE` for two years on a fixture the base table could solve
  (WP-1041); the peak list blocked the certified pattern twice the same way (fitted
  satellites, then `_box_key` skipping unrefined leaves).
- **Profile an engine before ranking what to fix in it: a cost model reasoned from
  the algorithm's structure is not a profile** (WP-1030's ranking came out nearly
  inverted). Two corollaries: **wall clock is worthless while a second search shares
  the machine**, and **a candidate cell is a lattice, not a tuple** — compare with
  `reduce.same_lattice`, never sorted axes, or a correct answer in another setting
  reads as a miss (it bit WP-1040's own monoclinic row).
- **Removing a redundant search must not remove its prunes**, and only real data
  will say that you did: the centred passes are redundant *as searches* (each
  centred trial set is a subset of the primitive one) and not as *filters*; the
  prunes being monotone under bisection, replaying one at the leaf is equivalent
  to the whole pass. WP-1030 skipped that and put a pseudo-cubic trigonal R
  description of the certified LaB6 lattice above the cubic truth with **115 fast
  indexing tests green** — so run `tests/test_acceptance_indexing.py` before
  closing anything that touches an engine.
- Read a `predicted_but_absent` firing as "this cell predicts lines the pattern
  lacks", **never** "this cell is too big": it counts against the *lattice* group,
  so a space-group extinction (corundum's R-3c c-glide) refutes a correct cell, and
  only the extinction screen separates the two. Choose acceptance datasets **by
  space group** — SRM 660c (P m -3 m) is the control that proved it.
- The scoreboard across eight known-cell datasets is *never wrong, and silent more
  often than right*; never round it up (counts: WP-1041).
- **An ambiguity partner must be refuted by the lines it needs and the data lack**
  (asymmetric: the partner's extra predictions, never the parent's own absences), or
  every derivative lattice is reported and the gate can never promote. And
  `ambiguity_partners` walks sublattices only, so a *smaller*-volume isospectral
  rival is invisible — tetragonal P (a/√2, a) vs cubic P a.
- **A Niggli-reduced cell is primitive**: `ReducedCell.centring` is provenance
  about the input, never handed to anything that applies a centring. Reduction needs
  the *relative* ε (`NIGGLI_EPS_RELATIVE`) or one lattice splits into two and denies
  the gate its agreement.
- **An assumed precision may never refuse to index** (`from_positions` lists get no
  `MAX_RELATIVE_SIGMA_Q` vote; the shift-allowance half is above). `volume_envelope`
  is a mean line, not an envelope — WP-1030's.
- **This package is not slow at indexing, it is silent** — DICVOL04 reaches 3770 s
  on hard triclinic patterns and McMaille "hours, if not a night", against our
  measured 0.7–177 s. Buy responsiveness with ordering and reporting, never by
  shrinking the box. **`budget_seconds` is per (engine × system)**, with the
  probe and Le Bail validation on top and *outside* it, so the whole-run bound is
  `SearchSpec.total_budget_seconds`, enforced as a `Deadline` that *is* the cancel
  token (it nests under every cooperative check with no engine changes);
  `estimate_ceiling` is the pre-run arithmetic and `INDEX_BUDGET_EXHAUSTED` names the
  three states a bound run leaves (searched / truncated / not reached). A truncated
  validation reads `not_validated`, never `validation_failed` (1037). And **a Monte
  Carlo indexer must refine each proposal; scoring raw random cells does not rank** —
  WP-1023 ranked corundum's truth 29 053 of 200 001 unrefined, where `search_svd`,
  iterating each to a fixed assignment, returns it alone.
- **Coelho's N_c/N_o gate bounds the *volume*, it is not a per-trial verdict**
  (WP-1040, `svd.volume_window`): N_c ∝ V, so one probe gives κ and the gate is
  V ∈ [N_o/3κ, 4N_o/κ] — it held the truth on all nine corpus datasets and is most
  of why that engine costs seconds. **N_c counts distinct d-spacings, not hkl**, or
  the gate refuses certified LaB6 (the paper's caption and prose disagree).
- **An impurity cut is worth nothing until the metric is roughly right, and a *budget*
  is not a *tolerance*** (WP-1040): cutting far lines in the first pass rather than the
  last takes zincite 5/5 → 1/5 and zircon and FAP to **0/5**; a cut bounded to
  `n_unindexed` rescues one dataset and costs the rest — a **retry after silence**.
- **The 2θ shift is solved *before* indexing — but a zero-error *column* inside the
  search is what stops a converged answer being wrong** (WP-1038; WP-1040 task 3,
  `svd.zero_error_column`). A cell found inside a widened window absorbs the shift,
  which is why DICVOL04 solves it first and McMaille refuses to scan the zeropoint.
  Coelho §2.3's column is the other half, and it does *not* raise the hit rate: at an
  injected 0.10°, started **at** the truth, one pass lands 3.5 % out where §2.4's
  three land 1e-4 out and report the shift to 1 % (corundum 0 candidates → the truth
  ranked first, nothing regressed). It agrees with the pair screen to **0.003°** needing
  neither references nor pairs — and still may not correct a cell, being the `constant`
  template *by construction*: **a shift measured without an attribution sizes windows,
  and only a declared template moves a cell.**
- **A search is driven by the *strongest* N lines, and "enumerate liberally" is a
  rule this package cannot have** (WP-1039, `engines.search_line_order`). *Which*
  twenty beats *how many* (NAC: 6 of the truth's lines in 2θ order, 18 by intensity
  over a `SEARCH_POOL_MULTIPLE` low-Q pool), and raising N *loses* answers, since
  `indexes_the_search_lines` is an **absolute** budget. Ties fall back to Q, so
  position-only lists are untouched.

**Backends (v0.4).** `backend=` takes `"numpy"` (the default and the only one
anyone needs), `"jax"`, or the **experimental** `"torch"` (CPU fp64) / `"torch-mps"`
(Apple GPU, necessarily fp32) — never installed by default, kept as an independent
opinion in the agreement matrix. Every backend is held to per-column agreement with
the analytic Jacobian in `tests/test_cross_backend.py` — **whose configs must grow
whenever a new derivative path does**, or no backend row covers it. Apple-GPU
execution is *slower* than numpy (46-182×, launch-latency-bound): `torch-mps` buys
precision validation, not speed (break-even and ceiling: the v0.4 record). Also
since v0.4: true Voigt (`shape="voigt"`, TCHZ still the default), soft restraints,
the Bérar-Lelann esd inflation. v2 fence: FPA, neutron/TOF, spherical-harmonics
texture, MCP server.

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

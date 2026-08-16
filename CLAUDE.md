# CLAUDE.md — rietx

API-first Rietveld refinement package (powder XRD). MIT. numpy/scipy fp64
core, pydantic v2 schemas, gemmi for CIF/symmetry. Import name: `rietx`,
aliased `rx` throughout (`import rietx as rx`).

**This file is for changing the package.** To *use* it — refine someone's data
— read `docs/AGENT_PROTOCOL.md` (the operating protocol) and `docs/manual/`
Part 1 instead; nothing here is a substitute for either.

## Commands

```sh
uv venv --python 3.12 && uv pip install -e ".[dev]"   # setup (once); a WORKTREE needs its own venv — main's .venv imports main's src (tests/CLAUDE.md)
uv pip install -e ".[dev,jax,torch]"                   # + optional jax/torch backends
.venv/bin/python -m pytest -n auto --dist loadgroup    # full suite ~15-30 min, incl. real-data acceptance (counts: § Numbers)
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"   # skip acceptance, ~1-3 min
.venv/bin/python -m pytest tests/test_cross_backend.py # Jacobian agreement matrix; rows self-skip without their backend
.venv/bin/python -m tests.bethanechol_benchmark        # the graded indexing benchmark (~1 h; run it ALONE — engine budgets are wall-clock)
.venv/bin/python -m ruff check src tests examples      # lint (must be clean)
.venv/bin/python examples/nac_11bm.py                  # end-to-end demo + plot
.venv/bin/python -m sphinx -W -q -b html docs/manual docs/manual/_build/html  # theory manual
.venv/bin/rietx gui my_sample.rex                   # the refinement GUI (localhost:8731)
npm --prefix gui ci && npm --prefix gui run build      # rebuild the GUI's committed dist
npm --prefix gui test && npm --prefix gui run check    # vitest (jsdom mount, fnmatch parity, panel/text-sync/model-edit/3D-trace/splitter/theme/plot/peaks logic; count: § Numbers) + svelte-check
.venv/bin/rietx watch <live-dir>                     # live viewer for a LiveSession run
.venv/bin/rietx compare --open                       # settings-comparison UI on the standards
```

`-n` is deliberately **not** in `addopts`: a bare `pytest tests/x.py::y` stays
serial, so `-s` and pdb keep working. `--dist loadgroup` is not optional either —
it honours the `xdist_group` marks that keep a shared fixture on one worker
(`tests/CLAUDE.md`); plain `--dist load` ignores them and silently refits.

Headline testing rules — operating detail and evidence (xdist group ordering,
budget narrowing, quoting counts) in `tests/CLAUDE.md`; the dated measurement
diary is `docs/milestones/v1.0.md` § Appendix:

- **Quote wall clock as a range, never as a figure** — machine state moves it
  further than most changes do; compare runs, not records.
- **A wall-clock budget in a test is a runaway guard, never a timer** — and it
  may live one rank down, in the library.
- **Say which numbers moved**: after adding N tests, passed+skipped moves by
  exactly N in the fast selection, and a new skip is not a new pass.
- **The full suite fires once, on the final tree**, and only when the change
  could move a measured number — never while still editing, and never on `main`
  for a baseline. The ladder, and what one session's ~80 min bought, are in
  `tests/CLAUDE.md` § Running.

### Numbers

Measure, never quote. Local fast counts: the `-m "not slow"` command above,
verbatim — never add `-q` (`addopts` has one; `-qq` prints no summary at all).
Full-suite counts and `--durations`: the latest nightly `full` job log
(`gh run list --workflow nightly.yml`; `[dev,jax]`, Linux, ~90-day retention,
up to a day stale). Quote any count with its venv **and** platform
(`tests/CLAUDE.md` § Quoting numbers); a session's own go in its WP handover.

`rietx compare` answers "does this new correction actually help?": pick a
standard, tick variants, read the **cumulative Δχ² vs reference** panel — it
localises *where* a change acted, not just whether Rwp moved. Registry + runner in
`viz/compare.py` (headless: `compare.run(standard, variant)`), server/page in
`compare_app.py`; its standards are the acceptance suites' protocols, asserted
field by field by `tests/test_compare_ui.py` — so **add a row there whenever a new
correction lands.**

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
per-pattern summaries plus parameter *trajectories*, one history tree per pattern
(pinned to it by `TreeHeader.data_fingerprint`), linked by annotation notes. Not
`multi.py`, which stacks patterns into **one joint residual**. A chained fit is
worth ≈3× in iterations and nothing in accuracy, and its trajectory is
path-dependent by construction, so `direction="both"` runs the chain each way and
flags parameters the two disagree on (`SEQUENTIAL_PATH_DEPENDENT`) — the only
check separating a measured trajectory from an ordering artefact. A rejected warm
fit **escalates a rung at a time**, keeping the best attempt (`entry.rung`), and one
still diverged after the last rung is **quarantined** (WP-1051): reported with
`SEQUENTIAL_UNRECOVERED`, but seeding no successor and joining no median.
`events=`/`cancel=` are **per pattern** (WP-1016): every event carries
`series_index`/`…_label`/`…_n`/`…_pass` (+`…_rung`/`…_cold` on a *restart*) in
`data`, so no `EventKind` is new, and a cancelled series **returns** what
completed with `SEQUENTIAL_CANCELLED` — WP-1006's rule one rank up, not an
exception (`sequential.py`'s docstring has why).

The **parameter surface** (WP-1004) is how a client works the table without
running a fit: `Refinement.parameters() → list[ParameterRow]` lists *every*
entry — fixed, locked and tied included, esds from the last fit merged in, each
held row saying which of the three reasons holds it (`.refinable`,
`.held_because`); `set_vary(globs, vary)` and `set_values({path: value})` edit
it and auto-commit the `set_vary`/`set_value` history nodes. Three rules there
are load-bearing: `ParameterRow` mirrors `params.vector.Entry` field for field
(pinned by `dataclasses.fields`, `esd`/`mode_fixed` declared as the
deliberate extras), a **tied** path refuses an edit and names its sources
instead, and `mode_fixed` — lebail/pawley force-fix every `.atoms.` path,
`.scale` and `.source.lines.` — is *not* `locked`, which is what keeps a Le
Bail phase's mandatory dummy atom from looking editable. **User constraints**
(WP-1070) sit beside the derived ties: `tie`/`tie_equal`/`untie`, auto-committing
`set_tie` nodes, with `Refinement._ties` the one authority for *which* ties are
the user's (every `ParameterTable` build rederives the symmetry ties and knows
nothing about a user's) and `RefinementState.ties` the reason a checkout
restores the parameter *count*. Symmetry outranks a user tie, enforced in
`_apply_ties` and not only in the verbs' refusals — a model edit can make an
already-tied path symmetry-tied after the fact. There is exactly
**one** `StageSpec`/`PlanSpec`, in `schemas/plan.py`; `schemas/history.py`
and `agent.py` re-export it, and `PLAN_INFO` in `strategy/staged.py` carries a
title/description/modes/when-to-use per preset, in bijection with
`PLAN_PRESETS` by meta-test.

`capabilities()` (WP-1007, `capabilities.py`) is the one call that says what this
build can do — backends *with whether each optional dependency imports here*,
solvers, plans from `PLAN_INFO`, modes, anodes, the formats `read_pattern` opens,
and the **six** versioned contracts (schema / report-thresholds / event-schema /
project-format / textdoc-format / indexing-thresholds — in the arm, not prose:
a client reads the field list, and a meta-test fails on a `*_version` field
that is not the constant it claims to quote). **Every arm is quoted from a live registry and a meta-test fails
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

A **project** (WP-1005) is a `.rex/` **directory** — `project.json`, the pattern
file copied byte-for-byte, `history.jsonl`, `live/`, `exports/` — opened and saved
through `Project.create/open/save` (`project.py`, `schemas/project.py`). A
directory, not an archive: the log's crash safety is append-only writes by one
writer, and rewrite-on-save would lose it. **One authority per fact.**
`project.json` holds the *settings* — selected plan/mode/limits, excluded regions,
the GUI's own `ui` keys — while `history.jsonl` holds the model state and its head
*is* the working state, so no parameter value is duplicated between them and
**saving is about settings, not durability** (the tree exists from `create`, so
every `set_vary`/`set_value` is already on disk). Two things follow from the pattern
being a file rather than a `PatternData`: the bytes are the contract (the readers'
esd column is never overridden), and the **reader call** is part of the reference —
`DataRef` records which `io.readers.PATTERN_FORMATS` entry claimed the file plus its
options, because a pdCIF with a `_meas` and a `_calc` block is a different pattern
depending on `block`. It carries sha256 of the bytes *and* the parsed-array
fingerprint on purpose: agreeing bytes with a disagreeing fingerprint is a reader
change, not a corrupt project. `excluded_regions` live in the document because they
are protocol that is in neither the file nor `RefinementState` — a node cannot say
what was excluded when it ran. Two rules follow (WP-1033): `project.fitted_mask` is
the one authority for **which channels the next run fits** (`compile_model`'s first
act, pinned by asserting `len(result.two_theta)` against its sum, and a function so
a pattern the project does not own — a series member — asks the same question), and
an inverted or empty interval is **refused, not reordered** by
`schemas.project.check_interval` — one sentence the verb, the `.rxt` parser and the
document's own validators all quote.

Entry points: `Refinement.fit()` / `refine()` in `refine.py`; modes `"rietveld"`,
`"lebail"` (intensity partitioning in `CompiledModel.lebail_update`) and `"pawley"`
(per-hkl intensities refined as an off-table θ block — `model.forward.PawleyBlock`,
appended in `run_least_squares`; overlapped groups get equal-split restraints and
come back flagged `PAWLEY_OVERLAP_UNRESOLVED` rather than confidently split). For
tool-calling there is `agent.refine_json(dict) → dict` (`agent.py`, WP-0602): one
call covering refine/refine_multi/refine_sequential/**index**/suggest behind a
strict task union, errors as a structured `{ok:false, error:{code,…}}` envelope
(never a traceback), and `agent.tool_definition()` exporting the JSON Schema with
the backend/solver/plan/**engine** names quoted from the live registries — a
meta-test fails if a registry member is missing from the schema. The four answers
live in separate arms (`result`/`series`/`indexing`/`suggestion`) because they are
different *shapes*, and for indexing the shape is the rule: the serialized answer
carries no `cell` key either. Two **companions** ride beside an arm rather than
being one, additive as defaulted fields: `evidence` (WP-1043, the answer
projected for a reasoning consumer) and `trajectory` (WP-1058) — **the report at
every stage boundary, because a run's last state is routinely its least
informative**: a plan absorbs an error it cannot free into whatever it can and
converges suggesting nothing, while its own first stage named the cause.
Default-off on both halves since WP-1003 (1064 measured: unasked rungs bought
no better decisions at more calls) — `report_trajectory`, and
`fit(stage_reports=True)` → `stage_reports_`, called in loops. Rungs are states
the plan already visits (the answer is bit-identical), and a report is derived
from a result, so it rides *beside* one, never inside.

### GUI

The **GUI** is `rietx gui [PROJECT.rex]` — stdlib `http.server` on 127.0.0.1
serving a committed Svelte 5 dist. Its rulebook — the session/wire split, the
server contract, the `.rxt` document, the editors, the nine panels, the 3D
viewer, theming — is `gui/CLAUDE.md`, which loads under `gui/`. Three rules
matter outside the GUI too: mutating verbs return **409 while
a run is in flight** (frozen-per-stage discreteness enforced structurally); the
**run state is not an event** — `EventKind` is closed, and `live/events.jsonl`
stays the one stream `watch` tails; and a **project setting is one that is about
the project** — the theme is the person's, lives in `/api/settings` beside the
recent list, and is therefore not behind the 409 (WP-1044).

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
- **An analytic Jacobian branch is a claim about what one parameter *name*
  reaches.** `_make_jacobian` dispatches on the free path's name and each branch
  computes only the rows it was written for — one background design row, one
  atom's coordinate rows, the phases the path's own prefix names. A tie makes a
  column move rows outside that reach, and the column then comes back **short**
  rather than raising. So `_column_extras` reads off C what each column also
  moves, every branch declares the reach it covers, and anything beyond takes
  the whole-model FD column, which is exact because it decodes through C like
  the residual does. A new branch — or a new way to widen C — extends that gate,
  and `test_cross_backend.py`'s `families_tied` row is where other backends
  check it (WP-1070 measured an un-gated background column wrong by 49 % of its
  own scale).
- **Pydantic knows no crystallography, so a whole-model swap is checked by
  building its table.** Every symmetry refusal is raised in
  `ParameterTable.__init__` and the snapshot `Refinement.edit` commits performs
  none of it, so `edit` builds the **proposed** pair's table and refuses rather
  than recording (before WP-1035 such a model was accepted, recorded a node, and
  raised from whatever next asked for the table).
- **Weights**: use the file's esd column when present (readers), Poisson
  √max(y,1) only as fallback. Never subtract an estimated background —
  hold it additively (`BackgroundFixedPlusChebyshev`) or co-refine it under
  a smoothness penalty (`BackgroundPSpline`).
- **The observation count is reflections, not points — and it gates nothing**
  (WP-1071). `n_points` is the algorithm's N; McCusker §9's warning is that
  refining against it outruns the data in silence (measured: 22 003 points
  against 132 reflections on 11-BM NAC). `optimize.statistics` is the one
  authority — `count_unique_reflections`, and `effective_observations`
  (Altomare 1995, overlap-corrected, a float). Its two bands, like
  `background.diagnostics`' five-to-ten steps per FWHM, are **quoted from the
  papers, never tuned**: they set a diagnostic's *level* and nothing else.
- **A derived quantity's esd goes through the whole covariance, and one that
  cannot be measured is absent rather than zero** (WP-1072, McCusker §10).
  `model/geometry.py` propagates J·Cov·Jᵀ off the final Jacobian and carries
  the diagonal-only number beside it (`qpa.weight_fractions`' precedent) —
  measured on 11-BM NAC, dropping the correlations moves an esd by ×0.71 to
  ×1.15, in *both* directions, so a diagonal esd is not the conservative
  choice. `None` covers all four ways a number is unavailable: no covariance,
  no free source, a quadratic form that reaches zero by cancelling (a
  symmetry-fixed 90° angle), and a straight angle, where linear propagation
  does not hold at all. Two rules for anything built on it: a geometry row
  **is** a restraint row (σ = weight = 1), so `model/restraints.py` stays the
  one derivative chain; and a neighbour search is proved complete by **orbit
  counting** (|A_ij|·m_i = |A_ji|·m_j), never by the distances looking right —
  a wrong deduplication passed every distance-value test in the file.
- **A position correction belongs to a geometry, and so does the action that
  names it** (WP-1073, McCusker §5 eq 3/4). `sin 2θ` is flat-plate
  transparency on a plate and the along-beam capillary offset on a capillary,
  so `report/layer1.POSITION_TEMPLATES` and
  `layer2._POSITION_ACTIONS_BY_GEOMETRY` are keyed by `Geometry.kind` and
  meta-tested against each other *and a real* `ParameterTable` — geometry-blind,
  the map suggested a force-fixed parameter and the route answered 409. Three
  rules for a new aberration, all measured in 1073's file: a parameter the
  forward branch skips is **force-fixed, not merely unfree** (else a free entry
  is a dead column); "this instrument has no such error" is not "refine it and
  get zero" (on 11-BM the pair is a degeneracy the fit rides to a bound while
  Rwp *improves* and the cell moves 1117 ppm); and its evidence is a **rung**,
  never the endpoint, which zero shift + cell leave with no cause named.
- **A stage weights the restraints, and the scalar stops at the row build**
  (WP-1074, McCusker §8 eq 7). `Stage.restraint_weight_scale` is c_w in
  S = S_y + c_w·S_G — frozen onto `CompiledModel` at stage compile, so a
  schedule changes it *between* stages and never inside one. √c_w multiplies the
  **assembled** rows (`CompiledModel.restraint_residual`, which every backend
  reaches through `rows.assemble`, and the analytic block in `least_squares`) and
  never the compiled items or `restraint_partials`, whose *second* consumer is
  `model/geometry.py` calling it at σ = weight = 1 for the unweighted partials
  every reported esd is built from. Default 1.0 is the identity, measured
  bit-identical on a restrained five-stage fit; 0.0 silences the rows without
  removing them, so the count the statistics exclusion rests on cannot move
  mid-plan. Two tests cover this and neither covers the other: the geometry
  Monte Carlo catches an unconditional error in `pref`, and only a
  restraints-plus-c_w fixture catches a leak conditioned on the model.
- **A pattern reader may repair a file only where it can say that it did**
  (WP-1047). `read_pattern(..., diagnostics=[])` is `structure_from_cif`'s
  channel one layer down; four consequences reach a caller outside `io/`. A
  multi-range file's ranges are **scans selected by `scan=`, never concatenated**
  (GSAS-II concatenates, mixing two weighting regimes); a reader raises
  `ValueError`/`OSError` **naming the file**, never its parser's exception; the
  **intensities and σ need not be the file's numbers** — an attenuator is applied
  or not by *measured* vendor convention (four formats, three answers) and σ goes
  through it either way, while an unestablishable scale **withholds** σ
  (`PATTERN_INTENSITY_SCALED`; the fallback is wrong by √t on a rate); and the
  scanned **axis** is never trusted — most vendor files are not powder scans, so
  a non-2θ one is refused by name and an unknown one says so. Dispatch, repairs,
  options and how to add a format are `src/rietx/io/CLAUDE.md`, under `io/`.
- **Every weighted residual in the package divides by `RefinementResult.sig()`**
  — every renderer and both GUI windows — a peer of `PatternData.sig()`, where
  the esd-column/Poisson choice was already made: `CompiledModel` stores
  `pattern.sig()` and `refine` copies it to `result.sigma` verbatim, so a
  result's σ is a *lookup*, never a re-derivation (five call sites, three
  policies before WP-1029, whose file has the story). **`weighted` is `DataRef.has_sigma`** (σ *measured*, not σ
  *present* — the fact `textdoc` renders as "σ from file"), `delta` is always
  Δ/σ because Δ/σ is what the fit minimised either way, and the flag changes
  only the axis title. A test that recomputes a residual cannot catch this class
  of bug: the pin compares what each renderer **drew** against what the route
  **sent**.
- **Background flexibility is a correctness question, not a cosmetic one.** A
  background able to imitate the peaks biases ADPs up and scales (hence QPA
  fractions) down while Rwp *improves*. Measure it **once**, as the block
  projection R² of a structural Jacobian column onto the background column span
  (`optimize.statistics.background_absorption`; pairwise ρ misses it), and carry
  the whole table to `FitReport.background` — whose other half, a too-stiff
  background, Layer 0's peak-cluster regions are blind to (WP-1055).
- **Reciprocal-space symmetry action is Rᵀ** (transposed rotation) — matters
  for non-cubic orbit/multiplicity counting (see symmetry.py comment). **This is
  about hkl, and applying it to a *tensor* is the opposite mistake**: a quantity
  that contracts with h twice — G\*, or the U\* form of an ADP — is invariant
  under U → R·U·Rᵀ with R **untransposed**, because (Rᵀh)ᵀU(Rᵀh) = hᵀ(RURᵀ)h. So
  `wyckoff.adp_basis` takes untransposed rotations for a metric or an ADP basis.
  The trap is that the transposed set is a group too, so the invariant subspace's
  *dimension* is identical in every crystal system and a degrees-of-freedom test
  passes — WP-1020 built the whole indexing metric subspace from Rᵀ and satisfied
  its own 1/2/2/2/3/4/6 criterion. Only asserting that the true metric lies in
  the span catches it.
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
- **A silent correction is a reader's to make, never a table's — and only where
  the deviation is a *report* rather than a contradiction.** The rule above
  fixes *where*: `ParameterTable` has no diagnostics channel, `structure_from_cif`
  does, so a stranger's file is repaired at read with the substitution recorded
  as a `Diagnostic` (species: `CIF_SPECIES_NORMALISED`, cell angle:
  `CIF_CELL_ANGLE_CORRECTED`) while both lookups and the table stay strict.
  What decides *whether* is magnitude, because the reader cannot see intent: up
  to `cif.CIF_ANGLE_CORRECT_MAX_DEG` a fixed angle is an experimenter quoting a
  refined value (β = 90.002(3) under `P m m m`) and snapping costs ≤ 830 ppm in
  d; past it the symbol and the angle contradict each other (β = 93.2 — an
  orthorhombic cell cannot have it), one of the two is wrong, and choosing is
  the caller's, so the value is left byte-for-byte and still raises (WP-1028).
- **A softplus `min=0.0` is safe wherever zero is the *off state*, and a bug
  wherever the physics divides.** `internal_bounds` maps any lower bound ≤ 1e-12
  to −∞ and `log(1+e^u)` underflows to exactly 0.0 below u ≈ −745, so "strictly
  positive" is a promise the transform does not keep. Thirteen of the fourteen
  parameters declaring it are fine — a zero width is no broadening, extinction 0
  is E ≡ 1 — because their identity *is* zero; `PreferredOrientation.r`'s
  identity is interior (r = 1) with a pole at the bound, and it fed the solver
  NaNs for a whole budget without raising. So the pattern to check on a new
  parameter is not "softplus with min=0" but "softplus with min=0 **and** a pole
  at zero", which needs a real floor (`MARCH_R_MIN`), plus a validator, because
  a stored `min: 0.0` outlives the default.
- **Every physics function cites its reference** (author, year, journal) in
  the docstring, and documents conventions by physics not letters (e.g.
  size↔1/cosθ, strain↔tanθ; GSAS and FullProf swap X/Y labels).
- **The FitReport must never return a confident wrong singleton.** Every Layer-1
  statement passes four gates (resolvability on the *scale-normalised* Gram,
  0.4·FWHM validity radius, local-χ²_red significance, share-based global
  maturity); collinear angular templates are compared as *nested single fits* and
  reported non-separable. Confidence weights importance (share of χ²), not just
  statistical significance.
- **A new correction ships with a record field or a diagnostic that states
  what it changed — never an Rwp comparison as its evidence.** v0.5's
  measured method result: of eight corrections, two provably cannot move
  Rwp, one moves it the wrong way when it is right, and the two largest
  accuracy wins are invisible in it (`docs/milestones/v0.5.md`). **Nor an
  R_Bragg comparison** (WP-1069): I(obs) is I(calc) times the reflection's
  own obs/calc count ratio, so it flatters whatever model partitioned it.
- **Licensing**: port code only from permissive sources with ATTRIBUTION.md
  updates. BGMN/Profex/xrayutilities are GPL — concepts only, never code.
  TOPAS/FullProf are closed — papers only.

## Conventions

- **Never spell the distribution name, a format token or the state dir — import
  it from `_about.py`** (WP-1062; 1066 renamed the brand again, format tokens
  unmoved): its docstring says which is which, and why no test can enforce it.
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
  content is ΔB = c(µR)·λ²/2 (measured on real 11-BM SRM 660a data to the
  predicted digit; ROADMAP's v0.5 row and its record). Flat plate:
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
  since-withdrawn claim — v0.6's record has it, with the re-measured brucite
  and corundum cone counts).
- **Anomalous scattering is ON by default since v1.0** (`Source.dispersion`, f = f₀ +
  f′ + i·f″ from bundled Cromer-Liberman `data/f1f2_CromerLiberman.dat`), and
  the load-bearing part is *not* that f goes complex — F always was. It is that
  `generate_reflections` merges ±h into one Laue orbit and evaluates a single
  representative, which is exact only while f is real: with f″ ≠ 0 in a
  non-centrosymmetric group |F(h)|² ≠ |F(−h)|², and both land in the *same*
  powder peak. So `structure_factors_squared` returns the **Friedel average**,
  in the closed form ⟨|F|²⟩ = |A|² + |B|² over the *same* orbit sums (A: f₀+f′,
  B: f″) — no second orbit pass, no centro/non-centro case split, and B ≡ 0
  recovers |F|² bit-identically, which constrains the fp *association order* in
  `_orbit_terms`. f′/f″ are frozen at stage compile onto `PhaseSites.f_anom`: they
  depend only on species and λ, and `EmissionLine.wavelength` is a plain float,
  so they can never be a function of θ. One |F|² is shared across emission
  lines, *guarded* rather than smeared — `dispersion.resolve` raises when a line
  differs from the primary by more than 1 % of Z (an edge between them). Near an
  edge the table is wrong in principle, not merely coarse, so that is refused
  too and `Dispersion.overrides` takes measured pairs. It is the **only**
  correction needing no information the caller lacks — species and λ suffice —
  which is why WP-1001 made it the default; `dispersion = None` declines it,
  reproduces every ≤ v0.6 number bit-identically, and says so through
  `DISPERSION_NEGLECTED`. **Every test that pins a number declares this setting
  explicitly rather than inheriting it** — a suite whose numbers move when a
  default moves is not pinning a protocol, and `tests/test_validation_matrix.py`
  enforces it for the acceptance suites. Ions resolve to the element (core-level
  effect), unlike ionic f₀.
- History nodes store **state, not curves** (a node is ~10 kB; embedding y_calc
  would make it ~1.24 MB). Their cached metrics are *as-optimised* — measured on
  a model frozen at the values each stage *started* from — so `refine.replay`,
  which recompiles at the values the stage *ended* on, can differ marginally:
  a staleness signal, not a bug. Le Bail extracted intensities live outside θ
  and are path-dependent, so they are serialized per node (`ReflectionState`);
  Pawley will reuse that container rather than adding one dot-path per
  reflection to `free_paths`.
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
- The **manual** (`docs/manual/`) is one `-W` Sphinx tree in two parts, each
  guarded differently because each fails differently. **Part 2 — Theory**
  (`tests/test_manual.py`): fenced constants are MyST substitutions injected
  from the live package in `conf.py`, every displayed equation carries a
  `*Source:*` line whose symbol must import, every bib entry is cited — so
  renaming a physics symbol or retuning a fenced constant means touching the
  manual in the same change, and **a WP that adds physics adds its equation
  there**, never only Part 1 prose (four of the six McCusker WPs did the second
  only — WP-1067's log). **Part 1 — Using rietx** (`docs/manual/using/`,
  `tests/test_manual_api.py`): a reference manual's failure is a *name*, so
  every dotted name and dot-path must resolve, every python block parses and
  either executes or carries a written reason, and the public call surface is
  partitioned into documented / excluded-with-a-reason / a generated deferred
  bucket. That surface is **derived** (`tests/api_surface.py`, whose docstring
  has the three rules), never listed — a curated list cannot notice a new
  public method, `_SURFACE_FLAGS` one rank up — so **adding a public method or
  field fails that partition until it is documented or deferred.**
  **A green build is not a rendered page**: `-W` cannot see a paragraph that
  printed its own TeX, so `test_no_unrendered_math_survives_the_build` scans the
  *built* HTML, and a diagram or a themed figure is checked by looking at it.
  Part 1's figures are **committed** in light/dark pairs, regenerated by
  `docs/manual/make_figures.py` (the one authority for how each was drawn), and
  agent-facing prose carries the `agent` admonition rather than a sentence
  saying so.
- **A walkthrough has one authority, and it is `examples/`.** The manual
  `{literalinclude}`s those scripts and `tests/test_examples.py` runs them, so
  a worked example is code that ran. Never write a third copy.

## Roadmap & how to work on it

Planning docs are split so a session loads only what it needs — do not read
them all:

- `docs/ROADMAP.md` — the index: session protocol, a "Current focus" capped
  within `CURRENT_FOCUS_CAP` (tests/test_docs_consistency.py), milestone
  table, WP index.
- `docs/wp/NNNN-*.md` — one **self-contained** WP per task (context, commit-
  sized checklist, acceptance command, handover log).
- `docs/DESIGN.md` — design record; read only the section a WP links.
- `docs/milestones/vX.Y.md` — one record per milestone: measured acceptance
  at ship, plus (while in flight) the running "How vX.Y is getting here"
  narrative and the dated appendices. `v1.0.md` is the live one.
- The **paper corpus** — where the papers physically are, and which are still
  unread — is maintainer-local, outside this repo (`AGENTS.md` names the
  split; the maintainer's memory holds the location). **Search it before
  asking for a paper or re-deriving a published constant.**
- `docs/AGENT_PROTOCOL.md` — consumer-facing operator guide; a WP that adds
  a diagnostic code or a correction adds its row there.
- `gui/CLAUDE.md`, `tests/CLAUDE.md`, `src/rietx/io/CLAUDE.md`,
  `src/rietx/indexing/CLAUDE.md` — subsystem rulebooks; they load with their
  subtrees, so nothing here restates them.

**Protocol**: `docs/ROADMAP.md` § Session protocol is the one authority
(`tests/test_docs_consistency.py` enforces the mechanical parts). Two clauses to
carry everywhere: commit per checklist item prefixed `WP-NNNN:`, and a CLAUDE.md
takes **rules, not findings**.

Shipped: **v0.1 … v0.6**, one record each in `docs/milestones/`; ROADMAP's table
carries the acceptance one-liners, restated in neither place.

**In flight: v1.0 — hardening, human GUI, indexing, API freeze, PyPI.**
`pyproject.version` tracks the milestone *in flight* (1.0.0.dev0), not the last one
shipped, because that string is stamped into every `RefinementResult.provenance`
and history node. The GUI (WP-1004…1017) and **indexing** (WP-1018…1027) both land
*before* the freeze (WP-1003) so it covers an exercised surface; grounds in the
v1.0 record.

**Indexing — the rules that govern behavior outside `indexing/`.** The full
dossier is `src/rietx/indexing/CLAUDE.md` (auto-loads when a session works
there), measured stories in the v1.0 record's appendix:

- **The tolerance an engine searches with is not the per-line σ.** A fitted
  σ(2θ) is the right *weight* and the wrong *matching window*: on certified
  corundum the lines sit a median 11σ from the true positions (a cos θ
  displacement), so at 3σ the true cell indexes zero lines. Hence
  `DEFAULT_UNKNOWN_SHIFT_DEG`, reported as `INDEX_SHIFT_ALLOWANCE` because an
  assumed precision must never look like a measured one, and
  `refine_with_shift` *after* a candidate survives — a cell never
  shift-refined is biased by roughly the shift (+1400 ppm measured).
- **Never a confident singleton**: `IndexingResult` has no `.cell`/`.best`,
  only a gated `best_or_none()`; `determine_extinction_symbol` returns ranked
  classes each carrying a *list* of space groups — the extinction symbol, not
  the space group, is what a powder measures.
- **The gate**: `high` requires zero caveats; whole-profile Le Bail
  validation is mandatory (the FoM panel sees ≤20 lines and cannot see a
  reflection predicted where there is no intensity); and read
  `predicted_but_absent` as "this cell predicts lines the pattern lacks",
  never "this cell is too big".
- **Confidence is engines agreeing** — three, failing differently (wide
  domain / poisoned base line / bad starting basin), so adding one raises the
  bar rather than diluting it; and the FoM panel ranks, never scores.
- **`quick` is `index_pattern`'s default** (WP-1042): all engines, all
  requested systems run **system-major** under a whole-run ceiling, with
  progress and a graded shortlist per completed system streamed on the event
  ladder — so the GUI, CLI and agent inherit a bounded, anytime first click. A
  caller's own `total_budget_seconds` is never overridden (the result records
  `preset="custom"`); `preset="full"` is the unbounded pre-1.0 run, and a test
  asserting a complete search declares it explicitly.
- **Run `tests/test_acceptance_indexing.py` before closing anything that
  touches an engine** — a real ranking regression once sat under 115 green
  fast indexing tests (WP-1030).
- A new indexing rule lands in `src/rietx/indexing/CLAUDE.md`; it earns a
  clause here only if it changes behavior outside `indexing/`.

**Backends (v0.4).** `backend=` takes `"numpy"` (the default and the only one
anyone needs), `"jax"`, or the **experimental** `"torch"` (CPU fp64) /
`"torch-mps"` (Apple GPU, necessarily fp32) — never installed by default, kept as
an independent opinion in the agreement matrix. Every backend is held to
per-column agreement with the analytic Jacobian in `tests/test_cross_backend.py`
— **whose configs must grow whenever a new derivative path does**, or no backend
row covers it. Apple-GPU execution is *slower* than numpy (46-182×,
launch-latency-bound): `torch-mps` buys precision validation, not speed (the v0.4
record). Also since v0.4: true Voigt (`shape="voigt"`, TCHZ still the default),
soft restraints, the Bérar-Lelann esd inflation. v2 fence: FPA, neutron/TOF,
spherical-harmonics texture, MCP server.

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
  pure phases; 2-column ASCII, Cu Kα doublet, graphite diffracted-beam mono).
  QPA truth is the **weighed composition**; tolerances referenced to the
  published participant spread, never to σ(W). `corundum.prn` doubles as the
  SRM 676a cell-anchor specimen (c/a is the certificate-grade assertion;
  absolute axes carry lab d-scale systematics).

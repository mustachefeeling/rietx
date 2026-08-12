# WP-1024 — Consensus, `index_pattern`, Le Bail validation, agent & CLI surface

Milestone: v1.0 · Status: ✅ 2026-07-30
Depends on: 1021, 1022, 1023

## Goal

`index_pattern(...) -> IndexingResult` — the public entry point. It runs the
engines, deduplicates their candidates as reduced cells, enumerates geometrical
ambiguities, validates the survivors by Le Bail fit, and gates confidence on
**agreement**. Its API cannot express a confident wrong singleton.

## Context

- **The founding rule, enforced by the type.** `IndexingResult` has **no**
  `.cell`, `.best` or `.solution` attribute. `candidates` is always a list.
  The only singleton accessor is

  ```python
  def best_or_none(self) -> CellCandidate | None:
      """The single candidate, or None.  Returns a cell only when exactly one
      candidate has confidence == "high" and no ambiguity partners."""
  ```

  Same species of guard as `Geometry.mu_r` being a plain `float` so the type
  forbids refining it: the shape of the API, not a caller's discipline, is what
  holds.
- **The confidence gate:**

  ```
  high   ← found_by == all engines run  AND no ambiguity partners
           AND not fom_panel_disagrees  AND lebail is not None
           AND lebail.predicted_but_absent == 0
           AND indexed_fraction ≥ min_indexed_fraction
  medium ← ≥2 engines, or all with one caveat
  low    ← 1 engine, or any refuting caveat
  ```

  Agreement between engines sharing only the tolerance model and the Q form is
  a genuine independent-opinion signal — the device `direction="both"` uses in
  `sequential.py` and `tests/test_cross_backend.py` uses per Jacobian column.
- **Why Le Bail validation is mandatory, not an option.** The FoM panel is
  computed on ≤20 lines and is structurally blind to three things the whole
  pattern sees:
  1. lines beyond the panel — a cell can index the first 20 and fail from 21;
  2. **reflections predicted where there is no intensity** — the classic
     doubled/oversized-cell false positive. M₂₀ cannot see it (its `N_poss`
     denominator penalises it only weakly, which is Oishi-Tomiyasu's 2013
     critique). Layer 0's `unmatched_calc` strong-negative-residual detector
     (`report/layer0.py:104-109`) sees it directly, and `predicted_but_absent`
     is that count;
  3. impurity content — `unmatched_obs` at 8σ is the existing detector, and
     `report/layer2.layer0_actions` already emits `add_impurity_phase` with
     `alternatives=["reindex_or_recheck_cell"]`. **That pre-declared enum
     member is the seam this whole milestone closes.**

  Both source papers make whole-pattern validation their closing
  recommendation. With `data=None` every candidate caps at `medium` and
  `INDEX_NOT_VALIDATED` fires — the *result* abstains rather than one field
  being quietly downgraded.
- **`structure_from_candidate` carries two footguns; document both loudly.**
  `Phase._nonempty` raises on an empty atom list, so a Le Bail-only phase needs
  a dummy atom — which contributes nothing because `_run_stage` force-fixes
  `.atoms.`, `.scale` and `.source.lines.` in lebail/pawley mode
  (`refine.py:369-380`). And `space_group=None` must default to the
  **highest-symmetry group of the lattice with no extra absences** (`Pm-3m`,
  `P4/mmm`, `P6/mmm`, `Pmmm`, `P2/m`, `P-1`, plus centring), so validation
  tests the **lattice** — an absence-carrying group would hide exactly the
  reflections whose absence is not yet established.
- **Restricted searches must not read as verdicts.** Measured (tag
  `guillemot-study`, `audit_tools.py` check C — see References): a
  two-parameter engine scores 47-60 % on single-phase orthorhombic/monoclinic
  patterns, 82-100 % on genuinely tetragonal/hexagonal ones, and 69 % on a real
  mixture — **the bands overlap, and a "at least two phases" claim built on
  that ambiguity was withdrawn**. So `IndexingResult` carries
  `systems_searched` beside `search_complete`, and failure is reported as
  *"no cell found in the systems searched"*, never as *"this pattern is
  multiphase"*. `INDEX_SYSTEMS_NOT_COVERED` says which systems were not tried.
- **Lab cells carry a systematic no esd reports.** Measured (same commit, check
  A): sweeping `Geometry.goniometer_radius_mm` over 180-320 mm moves Rwp by
  0.029 points (the data cannot identify R), specimen displacement absorbs it
  4.6×, and **≈ ±85 ppm lands on the cell** — larger than the fit's own 1 σ.
  That study's own ROADMAP section records it as a candidate gap ("a lab cell
  quoted tighter than that with no radius supplied deserves a diagnostic");
  indexing is where it bites, because indexing *produces* a cell from lab data
  with nothing to compare against. `INDEX_CELL_SYSTEMATIC_UNQUANTIFIED` fires
  on Bragg-Brentano data when no radius was supplied.
- **`anatase compare` gets no new row, deliberately.** CLAUDE.md requires one
  whenever a new *correction* lands; indexing is not a correction and produces
  no alternative fit of the same model, so a variant row would be a fake
  comparison. Record that reasoning here so a future session does not add a
  meaningless row to satisfy the rule.
- **No `ActionKind` change and therefore no `THRESHOLDS_VERSION` bump.**
  `reindex_or_recheck_cell` already exists in `report/schemas.py`'s closed
  enum; only its rationale/suggestion text changes, to name the new API.

### Inherited

From **WP-1014** (import & in-GUI editing, landed 2026-07-30): **`structure_from_candidate`'s
dummy atom must carry a species with a form factor.** `GuiSession._as_structure`
now refuses a structure whose atom species is absent from the Waasmaier-Kirfel
table (`crystallography.scattering.normalize_species`), naming the atom — a
GUI-boundary judgement, because such a structure validates fine and fails at
*stage compile* instead. So a placeholder species like `"Xx"` or `"?"` would make
an adopted cell unloadable through the GUI while working from Python; pick a real
element (the dummy exists only because `Phase._nonempty` refuses an empty atom
list, and `_run_stage` force-fixes `.atoms.` in lebail mode, so its identity is
inert either way). Related, already noted in WP-1004: the parameter surface should
make that atom's *placeholder* status legible.

Adopting a cell also has a route now: `PATCH /api/structure` takes a whole
validated model and records one `edit_model` node, and the structure editor
(WP-1014) is what a user will see the adopted phase in.

From **WP-1006** (landed 2026-07-30): the `"index"` **run kind that WP's
Inherited asked for was deliberately not added** — `EventKind` is a closed
Literal and a kind nothing emits is an untested guess about a search loop that
does not exist yet. What did land is everything the guess was protecting:
`CancelToken` works on any loop that evaluates something (the check is
cooperative, between evaluations — it needs no stages, no Rwp and no history
node), and `stage_start`'s payload is an **open dict**, so "engine 2 of 3,
orthorhombic" is expressible today as
`index=2, n_stages=3, engine="dichotomy", system="orthorhombic"`. So: adding
`"index"` (and any `index_start`/`index_end` pair) is **this WP's** commit, and
it *is* a `EVENT_SCHEMA_VERSION` bump — a new kind bumps, an added field does
not. That rule is now written down in `history/events.py`; read it before
touching the constant.

From **WP-1012** (landed 2026-07-30): **`reindex_or_recheck_cell` is already
declared applicable and already wired to a refusal that expires by itself.**
`report/apply.py` classifies it `how="index"`, and `GuiSession.report_apply` refuses
it with `ACTION_NOT_APPLICABLE` naming WP-1024 *only while*
`capabilities().features["indexing"]` is False — a derived predicate
(`hasattr(anatase, "index")`), so the report panel's Apply button on that suggestion
turns on the moment `index()` exists, with **no edit in `report/apply.py`, in the
session, or in the frontend**. Two consequences for this WP:

- `tests/test_report_apply.py::test_indexing_is_declared_applicable_and_refused_until_an_engine_exists`
  asserts `pr.capabilities().features["indexing"] is False` with a message saying
  the applicable branch is now the live one. **It will fail here, deliberately** —
  flip that assertion in this WP's commit and add the positive case.
- `report/apply.py`'s `refusal()` is the only place indexing-availability is
  consulted, and it takes `indexing: bool` as an argument rather than importing
  `capabilities` — so if `index()` needs a *precondition* beyond existing (a peak
  list, say), that precondition belongs in the session's `_indexing()`, not spread
  through the report module.

Also: **applying an action is one `StageSpec` through `POST /api/report/apply`**,
which is a stage-shaped verb. An indexing run is not a stage, so this WP has to
decide whether the apply route grows a second shape or whether the report panel's
button posts `/api/index` directly. The second is cleaner and needs nothing new;
the first would make the panel's control uniform. `Recipe.how == "index"` exists to
mark exactly this fork.

From **WP-1021/1022/1023**: each engine registers itself; `engines_run`,
`engine_stats` and `search_complete` come from the registry, and
`agent.tool_definition()` must quote the **live** registry so a new engine
cannot be absent from the exported schema (the WP-0602 meta-test pattern).

From **WP-1007** (landed 2026-07-30): **`capabilities()` exists and has no
indexing arm — adding it is this WP's commit.** It was left out deliberately
rather than stubbed: there is no engine registry yet, and a hardcoded or
wrongly-named lookup would pass its own meta-test *while lying*, which is the
failure that note was written to prevent. What to do here, in one commit:

- add an `indexing_engines` arm to `capabilities.py` quoting the live registry
  (name / title / when-to-use / whether it is a re-scorer rather than an
  independent opinion — the WP-1023 no-go case), and extend
  `tests/test_capabilities.py`'s registry meta-tests with it, exactly as the
  backend/solver/plan/anode/reader arms are;
- nothing else: **`features["indexing"]` needs no edit.** It is
  `hasattr(anatase, "index")`, a derived predicate, so it flips the moment
  WP-1020 exports `index()`. Every flag there is derived for this reason; if you
  find yourself writing a literal `True`, that is the smell.

Also from **WP-1007**: guard hits are now `GuardFinding(code, paths, value,
message)` with an **open** `code` vocabulary, so an indexing guard (an ambiguous
cell, a restricted search) can be reported through the same channel without
reopening a `Literal`, and `Diagnostic.where` is expected to carry paths.

From **WP-1023**: if its spike returned **no-go**, engine C is dropped from the
confidence gate and `high` requires the two remaining engines — make that
change here, in the same commit, rather than leaving a gate that silently
counts a re-scorer as an independent opinion.

**It did (2026-07-30). The gate is a two-engine consensus.** Measured: tier-1
throughput is fine (~25 000 trials/s) and tier-2 is both affordable (13-15 ms per
state) and discriminating (Rwp 1.29 for the certified cell against 7.25 for one 1 %
off), but tier-1 **cannot rank**: on the certified qarr corundum pattern the true
cell scores 0.0000 and ranks 29 053 of 200 001, because the pattern's 0.060° cos θ
displacement is 11σ of the fitted per-line σ. Widening the window puts the truth at
rank 4 and simultaneously lets coincidence-rich large cells outscore it (0.969
against 0.896) — the failure the FoM panel exists to prevent, moved inside the
proposal mechanism where no panel can see it. So `high` confidence means *both*
landed engines agree; two agreeing engines is the ceiling, not a shortfall to
apologise for, and `found_by` must never contain a re-scorer. A Le Bail *re-scorer*
built on the measured tier-2 is still worth having — as validation, which this WP
already owns — but it is not an engine and does not count toward agreement.

From **WP-1023** (2026-07-30), and this one is a live hazard for your gate:
**both landed engines currently fail on real lab data**, and the cause is measured.
Their tolerance is the fitted per-line σ, which on the bundled corundum pattern is
11× too tight for the systematic the data carries; both now add
`engines.DEFAULT_UNKNOWN_SHIFT_DEG` (0.05° 2θ) when no shift has been *measured* and
say so with `INDEX_SHIFT_ALLOWANCE`, and both consume `SearchSpec.shift_template`
through `engines.refine_with_shift` so an accepted cell is corrected rather than
left carrying the shift. That is **not yet sufficient** — see WP-1026, which owns
closing it. Two consequences for the gate: `INDEX_SHIFT_ALLOWANCE` being present
means the tolerance was *assumed*, which should cap confidence on its own; and a
cell found under a widened window but never refined with a shift template is biased
by roughly the shift (+1400 ppm measured), so quoting it without the template is the
kind of confident wrong answer the gate exists to stop.

From **WP-1020**: `reduce.py`'s χ² cell-equality is the dedup primitive;
`ambiguity.py` supplies partners; the FoM panel supplies the Borda ranking.

From **WP-1028** (measured 2026-07-29): **the Le Bail validation step is only
sound for one phase at a time.** `CompiledModel.lebail_update` partitions
`max(y_obs − y_bkg, 0)` per phase with nothing to arbitrate two phases claiming
the same channel, so they inflate one another without bound — measured Rwp by
phase count: 1 phase converges (7.5–24.8 %), 2 phases 742–9 281 %, 3 phases
2.6 × 10⁵ %. It survives seeding both the widths and the background, so it is
the partition, not the starting point. Validate a candidate cell against a
single-phase Le Bail; do not use it to score a multi-phase hypothesis until
WP-1028 decides whether to damp, refuse or fence.

From **WP-1020** (landed 2026-07-30), three things that land in this WP's lap:

- **1020 emits no diagnostics at all**, deliberately: it has no answer to qualify.
  So `INDEX_BRAVAIS_AMBIGUOUS` is *this* WP's code to emit, from
  `BravaisScreen.ambiguous` (symmetry that appears only at a loose tolerance) and
  `BravaisScreen.methods_disagree` (gemmi and spglib differ at their tightest
  tolerances — which happens on genuine pseudosymmetry, because an obliquity in
  degrees and a `symprec` in Å are different kinds of number). Both fields are
  already computed; only the translation is missing.
- **`lebail_rwp` is owed here, not to 1020.** It needs a Le Bail fit against a
  candidate, i.e. exactly this WP's `structure_from_candidate`. Four other
  published figures (`m20_reversed`, `m20_symmetric`, `wrip20`, `mcm20`) are
  *not* implemented and should not be added without their papers — see 1020's
  handover for why guessing a formula and citing a source for it is the WP-0501 b₂
  failure again.
- **`CellCandidate` already carries `found_by`, `fom`, `ambiguity`,
  `lattice_group` and the shift fields**, and it deliberately has no "is correct"
  field. The consensus gate fills `found_by` and reads `fom_panel_disagrees`; the
  ambiguity list is populated by 1020's `ambiguity_partners`, whose entries carry
  `discriminating_reflections` — the hkl and 2θ that would break the tie, which is
  what makes an ambiguity report actionable rather than merely honest.

From **WP-1021** (landed 2026-07-30) — **the shared engine surface exists; build
on it rather than beside it.** `indexing/engines.py` holds everything the three
engines have in common, and six things about it are not obvious from the names:

- **`SearchSpec` is the one option object** (systems, centrings, `min_d_axis` /
  `max_d_axis`, `min_volume` / `max_volume`, `n_unindexed`, `n_search_lines`,
  `k_sigma`, `budget_seconds`, `max_candidates`, `seed`). The three engines must
  mean the *same* thing by `max_volume` and `n_unindexed` or their agreement is not
  evidence of anything, so take a `SearchSpec` and do not add per-engine keywords
  for anything it already carries. `spec.centrings_for(system)` and
  `spec.volume_limit(system, fallback)` are the accessors.
- **Return an `EngineResult`, and fill `search_complete` per system.** It carries
  `candidates: list[EngineCandidate]`, `systems_searched`, `search_complete`,
  `stats` and `diagnostics`. `EngineCandidate` holds the `CandidateFit` itself
  (not just the cell) because WP-1024's dedup is a χ² test needing `cov_af`, plus
  the hkl assignment and the `line_index` it was fitted on. **`search_complete` is
  the half that makes a negative result mean anything** — use
  `engines.incomplete_diagnostic` for `INDEX_SEARCH_INCOMPLETE`.
- **`engines.rank_candidates(cands, peaks, n_unindexed=…)` is how a ranked list is
  produced** — dedup, then the FoM panel, then Borda over the whole panel. Do not
  sort on `n_indexed` or χ²: on synthetic data supercells index every observed line
  *exactly* and tie the truth on every forward-looking figure, losing only on
  `predicted_seen_fraction`. Pass `spec.n_unindexed` through: the figures' mean
  discrepancy is trimmed by the same count the search was allowed to leave
  unindexed, and getting that wrong ranks an impurity-covering supercell first
  (measured: M₂₀ 13.2 for the truth against 62.5 for an a√5 supercell).
- **`engines.reflection_ceiling_ok(cell, λ, 2θ_max)` before every
  `generate_reflections`** — the measured 1.6 PiB guard. It is arithmetic on the
  cell, so it costs nothing and never touches memory.
- **`engines.trial_hkl(max_index, centring)`** (re-exported from `qspace`) is the
  centring-filtered, Friedel-halved trial set, and
  **`engines.assign_lines(q, σ, hkl, af, design=…)`** gives each line its nearest
  hkl within k·σ. Pass `design=design_matrix(hkl)` if you call it in a loop —
  rebuilding the (N, 6) matrix per candidate was 90 % of one search's runtime.
- **`engines.Budget(seconds, cancel)`** wraps the deadline *and* WP-1006's
  `CancelToken`; `budget.expired()` is cheap enough to call per unit of work, and a
  cancelled search returns what it has rather than raising.

**Also from WP-1021: `metric_basis` is memoised and its arrays are read-only.**
It re-derived the exact rational nullspace once per accepted box before that (2.5 s
of a 15 s run). Do not mutate what it returns.

**And the sharper lesson, if you are about to reach for a tolerance:** stopping
rules and measurement tolerances are different numbers. WP-1021 conflated them and
the 4-D search stopped terminating — zero leaves reached in 445 000 boxes. Its
exhaustiveness comes from the pruning, which is exact however coarse the leaves
are; the tolerance belongs in the *scoring*, not in the stopping rule.

**Specific to this WP (WP-1021, 2026-07-30).** Four things land in your lap:

- **`EngineResult.search_complete` must reach `IndexingResult`.** An exhaustive
  engine that finished and found nothing has said "no such cell within these
  bounds"; the same engine stopped by its budget has said nothing. The two must not
  be one field, and `INDEX_SEARCH_INCOMPLETE` is already emitted per system.
- **`systems_searched` is already on `EngineResult`** and a restricted search
  populates only the systems it covered (tested). Merge them across engines rather
  than recomputing.
- **The engine registry is `engines.engine_names()` / `engine_descriptions()`**;
  every registered engine has a one-line description precisely so
  `tool_definition()` can quote it. The meta-test you owe is "every registered
  engine appears in the exported schema".
- **A candidate's `found_by` starts as one engine name** (`to_cell_candidate` sets
  it from `EngineCandidate.engine`); merging is yours, and `dedup_candidates` keys
  within a centring on purpose — the same metric with two centrings is two
  *lattices* (one predicts half the lines of the other), and merging them would
  silently drop a hypothesis the panel exists to choose between.

## Non-goals

- No space-group determination (WP-1025) — validation uses the absence-free
  lattice group.
- No GUI (WP-1027).
- No multi-phase indexing (index the residual after subtracting a solved
  phase) — a fence, recorded not attempted.

## Tasks

- [x] `indexing/consensus.py`: reduce → two-opinion Bravais → χ² dedup and
      `found_by` merge → ambiguity partners → Borda rank → validation →
      the confidence gate; `best_or_none`.
- [x] `indexing/workflow.py`: `structure_from_candidate` (both footguns in the
      docstring), `validate_by_lebail` returning `LeBailValidation` with
      `predicted_but_absent` from ~~Layer 0's `unmatched_calc`~~ **the net
      intensity above the fitted background** — `unmatched_calc` was measured
      unusable (see the handover).
- [x] `index_pattern` + `IndexingResult` in `schemas/indexing.py`
      (`systems_searched`, `search_complete`, `engine_stats`, seed in
      `Provenance`); `anatase/__init__.py` exports.
- [x] All `INDEX_*` diagnostics not already owned by 1019, in particular
      `INDEX_ABSTAINED`, `INDEX_MULTIPLE_SOLUTIONS`,
      `INDEX_GEOMETRIC_AMBIGUITY`, `INDEX_SYSTEMS_NOT_COVERED`,
      `INDEX_NOT_VALIDATED`, `INDEX_IMPURITY_LINES`,
      `INDEX_VOLUME_UNPHYSICAL`, `INDEX_CELL_SYSTEMATIC_UNQUANTIFIED`
      (+ `INDEX_BRAVAIS_AMBIGUOUS`, `INDEX_PREDICTED_BUT_ABSENT`).
- [x] `history/events.py`: the `index_start`/`index_end` kinds WP-1006 deferred,
      `EVENT_SCHEMA_VERSION` 1 → 2 (a new kind bumps; the per-engine progress
      reuses `stage_start`/`stage_end`, which is additive and would not have).
- [x] `agent.py`: `IndexRequest` in the discriminated task union
      (`_TASK_TAGS`), `tool_definition()` quoting the live engine registry, and
      the meta-test that fails when a registered engine is missing from the
      schema. `cli.py`: `anatase index`.
- [x] `docs/AGENT_PROTOCOL.md`: the closed-loop workflow section
      (`pick_peaks → index_pattern → best_or_none → … → refine`), plus §6
      abstention and §7 code rows; `report/layer2.py` suggestion text points at
      the new API (**no enum change, no version bump** — said so in the commit).
- [x] `tests/test_indexing_consensus.py` (not `test_indexing.py` — the WP-1018…
      1022 files are already split by subject): the confidence gate under each
      caveat; the **API-shape test** (no unconditional singleton accessor;
      `best_or_none()` returns `None` for each gate failure); the
      **restricted-search test** (synthetic orthorhombic list with
      `systems=("cubic","tetragonal","hexagonal")` ⇒
      `INDEX_SYSTEMS_NOT_COVERED`, `systems_searched` excludes orthorhombic,
      nothing asserts multiphase; rerun with orthorhombic in scope finds it).

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_indexing_consensus.py tests/test_agent_surface.py -q
.venv/bin/python -m pytest tests/test_fitreport_layers.py -q
.venv/bin/python -m ruff check src tests examples
```

Criterion: `best_or_none()` returns `None` under every gate failure and a cell
only when the gate is fully satisfied; the agent schema quotes every registered
engine; and the restricted-search test proves a limited search cannot be read
as a multiphase verdict.

**Met, 2026-07-30.** 26 + 28 + 22 tests green; ruff clean; **full suite 1325 passed
/ 71 skipped in 8:11**, fast suite 1247 / 66 in 2:10. End to end on a synthetic
LaB₆ pattern, picking its own peaks: `best_or_none()` returns a = 4.15659 Å against
a true 4.1566 (2 ppm) at `high`, and the cubic F and I supercells — which index
every observed line and tie the truth on every forward-looking figure — come back
`low`, refuted by `predicted_but_absent`.

The first full-suite run was **2 failed**, and the failure is worth the paragraph
because it was not in this WP's code and not really a flake either. Both monoclinic
engine rows failed under `-n auto` and passed serially: they assert
`search_complete["monoclinic"]` — that the metric *domain* was exhausted — while
declaring `budget_seconds=180` against a search that takes ~85-105 s alone, so
adding one more test module was enough to push them over their own stopping rule.
They then reported themselves incomplete **correctly**, and failed an assertion
about exhaustiveness for a reason that had nothing to do with the domain. Fixed by
declaring a generous per-system budget (`BUDGET_SECONDS` in
`tests/test_indexing_engines.py`) with the reasoning attached, and the general rule
is now in CLAUDE.md: **a wall-clock budget inside a test is a runaway guard, never a
timer** — any test whose serial time is a large fraction of its declared budget is a
load sensor pretending to be an assertion.

## References

- Bergmann *et al.* (2004) *Z. Kristallogr.* **219**, 783-790 and Altomare
  *et al.* (2019) IT Vol. H ch. 3.4 — both close on whole-profile validation.
- Oishi-Tomiyasu, R. (2013). *J. Appl. Cryst.* **46**, 1277-1282 — why M₂₀
  cannot see predicted-but-absent reflections.
- Prior art, at the tag `guillemot-study` — **not merged into `main`, and it
  does not need to be**; every number above is restated here, so this is
  corroboration:

  ```sh
  git show guillemot-study:studies/guillemot/out/audit_full.txt   # §A, §C
  git show guillemot-study:docs/ROADMAP.md                        # the gap note
  ```

## Handover log

- **2026-07-29** — created from the indexing plan.

- **2026-07-30 — landed.** `indexing/consensus.py` (merge → Bravais → ambiguity →
  Borda → the gate), `indexing/workflow.py` (`index_pattern`,
  `structure_from_candidate`, `validate_by_lebail`), `IndexingResult` +
  `LeBailValidation` + `BravaisOpinion` + the gate fields in
  `schemas/indexing.py`, the `INDEX_*` translators in `indexing/diagnostics.py`,
  the `index_start`/`index_end` event kinds, `task="index"`, `anatase index`,
  AGENT_PROTOCOL §7c/§7d/§8.15/§8.16, and
  `tests/test_indexing_consensus.py`.

  **Done / measured.** The whole pipeline works end to end from a raw pattern:
  peaks picked, both engines run, the truth ranked first, validated, gated, and
  `best_or_none()` returning a cell 2 ppm from the true one. The CLI does the same
  from a file and carries the verdict in its exit status.

  ### The three findings that outlast this WP

  **1. The plan's `predicted_but_absent` detector cannot work, and the reason is
  structural.** WP-1024's context section named Layer 0's `unmatched_calc` — its
  strong-negative-residual count. Le Bail extraction sets each intensity from
  `max(y_obs − y_bkg, 0)`, so a reflection predicted where there is nothing is
  assigned ~nothing and **produces no negative residual at all**; what the detector
  finds instead is 5σ noise excursions that happen to sit near a tick. Measured on
  a synthetic LaB₆ pattern (15-145° 2θ, Poisson noise): `unmatched_calc` fired on
  **17 of the certified cell's own 28 reflections** and 94 of a doubled cell's 153
  — 61 % either way, i.e. it does not separate them. `workflow.absent_reflections`
  asks the question directly against the *fitted* background and separates them
  cleanly (0/28 against 117/153). The generalisable form: **a detector built for a
  Rietveld residual does not transfer to a Le Bail one**, because Le Bail cannot
  over-predict by construction — it fits whatever is there. Anything else that
  reads the Le Bail residual for "the model says something the data do not" needs
  re-deriving, not re-using.

  **2. Two WP-1020 defects, both invisible until a consumer needed a *yes*.** Every
  earlier WP consumed 1020 to *rank*; this one is the first to consume it to
  *promote*, and both defects only bit in that direction.

  - `ambiguity.py` never implemented the exclusion its own module docstring
    states. A superlattice's reciprocal lattice contains the parent's, so it
    indexes every observed line exactly and passed both existing screens
    (`n_indexed`, mean discrepancy): **28 partners for a certified cubic cell** on
    exact positions, 20-35 across systems. Since the gate refuses `high` to any
    candidate with a partner, the indexer could never have answered. The fix is the
    docstring's own rule — a partner needing a line the data lack is refuted — and
    it moves the discriminating reflections *outside* the measured range, so
    partner lines are now predicted to 1.5× 2θ_max.
  - `bravais_screen` handed `ReducedCell.centring` back to
    `gemmi.find_lattice_symmetry`, but Niggli reduction of a centred cell returns
    the reduced **primitive** cell — the centring is already consumed. gemmi
    therefore called a cubic I lattice **trigonal** (6 lattice rotations instead of
    24) while spglib, which gets the bare lattice, correctly said `Im-3m`. The two
    "disagreed" on every centred candidate, and `methods_disagree` capped their
    confidence for good. Half of all real structures are centred.

  Both had passing tests. The ambiguity one had a test asserting the *wrong*
  behaviour, with reasoning ("a supercell indexes every observed line, so it cannot
  be excluded by the positions alone") that reads only the observed positions and
  ignores the absences — which is `indexed_fraction`'s measured blind spot, one
  module over, in a test. It is rewritten with the crystallography: a 2a cell whose
  odd reflections are identically zero has the a-translation, so the *lattice* is
  the a-lattice and the supercell is a cell choice.

  **3. `high` confidence is currently unreachable on real lab data, by design, and
  that is the honest state rather than a bug to file.** Both engines widen their
  matching window by an *assumed* `DEFAULT_UNKNOWN_SHIFT_DEG` when no shift has
  been measured, which raises `shift_allowance_assumed` — and a cell found inside a
  widened window absorbs the shift (+1400 ppm measured). The gate therefore caps
  such a candidate at `medium`. Declaring a calibrated `sigma_sys_deg`, or handing
  `assess_peak_list` reference positions from an internal standard, clears it — and
  the synthetic tests reach `high` by declaring `sigma_sys_deg=1e-9`. **Do not
  "fix" this by removing the caveat or widening the constant.** WP-1026 owns
  closing it with evidence.

  ### Decisions taken against the plan, with reasons

  - **`INDEX_CELL_SYSTEMATIC_UNQUANTIFIED`'s trigger changed.** The plan asked for
    it "on Bragg-Brentano data when no radius was supplied"; `Geometry`'s validator
    *raises* on exactly that, so no such instrument can exist. The reachable — and
    stronger — statement is that a **declared** radius is not identifiable from the
    data either (Rwp moves 0.029 points across 180-320 mm), so the ±85 ppm is
    present whatever the caller declared and unquantified because the fit cannot
    measure it. It now fires on any Bragg-Brentano answer, and also when no
    instrument was supplied at all (geometry unknown).
  - **The validation fit holds the cell.** `profile_only` frees
    `phases.*.cell.*`, which would validate a *different* cell from the one
    reported. `workflow.validation_plan` frees the background, exactly **one**
    peak-position parameter (chosen from the candidate's own `shift_template`
    through `diagnostics.SHIFT_CAUSE`'s mapping, because the three templates are
    collinear), then the widths in the `profile_only` order.
  - **`lebail_rwp` is a field on `LeBailValidation`, not a panel member.** 1020's
    handover owed it here. It costs a refinement, so it exists only for the
    shortlist — and ranking on it would reintroduce the blind spot validation
    exists to close, since a bigger cell with more free intensities fits better.
  - **Two extra caveats beyond the plan's gate**: `validation_failed` (a Le Bail
    fit that raised or diverged — evidence *about* the candidate, and not the same
    statement as `not_validated`, which is the absence of a test), and
    `bravais_ambiguous`. And **caveat count does not separate medium from low**: an
    assumed tolerance plus an unvalidated candidate is the ordinary state of a
    peaks-only run, so the plan's "all with one caveat → medium" is read with its
    first clause ("≥2 engines") as the fallback.
  - **`anatase compare` got no new row**, as the plan required, and the reasoning
    is worth keeping: indexing is not a correction and produces no alternative fit
    of the same model, so a variant row would be a fake comparison.

  ### In flight / next

  Nothing in flight. What this WP did **not** do, and where it went:

  - **Real-data acceptance is WP-1026's**, and it inherits a live gap (see §3
    above) plus a working `index_pattern` to test with.
  - **Space-group determination is WP-1025's.** `structure_from_candidate`'s
    absence-free default is the seam it takes over, and the reflections
    `predicted_but_absent` lists are exactly the extinction evidence it wants.
  - **The GUI (WP-1027)** now has `IndexingResult` to render, `index_start`/
    `index_end` to drive a progress bar from, and `CancelToken` support.

  ### Gotchas for a successor on this WP

  - **A short pattern tests the abstention, not the search.** A cubic cell shows 15
    lines to 100° 2θ and 23 to 145°, and `PEAK_MIN_USABLE_LINES = 20` means the
    first list comes back `supports_indexing=False`. Two spikes were debugged
    before noticing that the gate was doing its job.
  - **The expensive checks run on a subset** (`consensus.checked_indices`:
    the top 3 plus every candidate all engines found). Ambiguity is ~0.5 s per
    candidate and validation ~0.6 s, so the cap matters — but it must never remove
    a candidate the gate could promote, which is why the second half of that union
    is not optional. A candidate outside the set carries `geometric_ambiguity`,
    because an unasked question must not read as a clean answer.
  - **Engine diagnostics are deduplicated on (code, message)**, not on code: both
    engines widen their window by the same allowance in the same words, and two
    copies read as two problems, while two engines saying *different* things under
    one code must both survive.

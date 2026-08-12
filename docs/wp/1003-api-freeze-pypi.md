# WP-1003 — API freeze + PyPI release

Milestone: v1.0 · Status: ⬜ — stub, expand before starting
Depends on: WP-1001, WP-1002, WP-1004…WP-1017 (the GUI expansion — this WP is
the milestone's last row, so the freeze covers a surface the GUI exercised),
WP-1018…WP-1030 (indexing), WP-1032…WP-1036 (the 2026-08-04 use session),
**WP-1062 (the rename — must land first, see Inherited)**

## Scope (carried verbatim from the pre-split roadmap)

- API freeze, PyPI release (name `anatase` verified available)

### Inherited

**From [1062](1062-rename-to-anatase.md), closed 2026-08-12 — the rename has
landed, so this is the surface you are freezing.** The distribution, import and
CLI are all `anatase`; PyPI `anatase` was free as of 2026-08-12 but **nothing
has been uploaded**, so re-check before the release rather than trusting that
date. GitHub is `yue-here/anatase` (renamed in place; the old URL redirects).

**What the freeze now covers, and the one asymmetry in it.** Brand tokens —
`DIST_NAME`, `STATE_DIR_NAME`/`STATE_DIR_ENV`, `AGENT_TOOL_NAME`
(`anatase_refine`), `DATA_PACKAGE`, `SERVER_TOKEN` — all live in
`src/anatase/_about.py` and move together. The **format** tokens live there too
but are deliberately brand-free and are *separately* versioned: `.rex`
(`PROJECT_FORMAT_VERSION` 1.1), `.rxt` with header `rxt N`
(textdoc `FORMAT_VERSION` 1), and the profile tag `instrument_profile`
(`FORMAT_VERSION` 1). Freezing a brand and freezing a format are two promises,
and they were split on purpose so a later rename cannot be a format break —
the freeze should say so rather than quietly re-coupling them.

**One live question the split raises for you.** The textdoc's magic word changed
to `rxt` while its `FORMAT_VERSION` stayed `"1"`, on the argument that
the document is rendered afresh and never persisted, so no stored file can carry
the old header. That holds today. If the freeze promises `.rxt` as a *file* — an
export, a diff artefact, anything a user can save — the argument expires and the
version should have moved.

**One inconsistency left for you deliberately.** The LICENSE now names the
copyright holder as **Yue Wu** (an actual legal person; the old
"⟨project⟩ developers" form named none), while `pyproject.toml` still has
`authors = [{ name = "anatase developers" }]`. Release metadata is this WP's,
so the two should be reconciled here — with an email, which `authors` wants and
the LICENSE does not.

**Also new since this WP was written:** `tests/test_no_stale_name.py` audits the
old name out of the tree, written against the **old** token because `anatase` is
a phase this software analyses. It cannot catch a hardcoded *new* literal, so
any name-bearing string the freeze adds must be an `_about.py` import.

**Three things already parked here that 1062 does *not* take.** They stay this
WP's, and all three embed the name, so do them *after* the rename: the sdist and
wheel metadata (which "currently names only anatase's own licences"), the
`classifiers` block, and the `tests/data/qarr/` licence blocker. Add two more to
the list: there is **no `CITATION.cff`** and **no `@software` entry** in
`docs/manual/references.bib` — a first public release wants both, and both embed
the name.

**One decision 1062 left to this WP.** `ANATASE_STATE_DIR` and `~/.anatase` are
now `_about.py` constants (`STATE_DIR_ENV`, `STATE_DIR_NAME`); whether the state
dir should be XDG-aware before it is frozen is still open, and is noted below in
the entry that raised it.

**From [1056](1056-identifiability-layer.md), closed 2026-08-12 — the fourth
lander's surface changes for the freeze.** `THRESHOLDS_VERSION` is now
**0.7**. `RefinementResult.identifiability` gained three additive defaulted
fields — `top_correlations: list[CorrelationPair]`, `soft_modes:
list[SoftMode]`, `exchangeability: list[ExchangeRow]` — three new models on
`anatase.schemas.results`, same never-recomputable character 1055's entry
below names (read off the final Jacobian), `SCHEMA_VERSION` unmoved.
`FitReport` gained `identifiability: IdentifiabilityEvidence | None`
(absent-for-cause only when the result has no channels; its carrier-derived
fields are individually None when unmeasured — a replay). New exports on
`anatase.report`: `IdentifiabilityEvidence`, `ExchangeFinding`,
`assess_identifiability`, `identifiability_clause`, `is_exchangeable`. New
module `anatase.optimize.identifiability` whose `EXCHANGE_CANDIDATE_GLOBS`
and `NULL_IDENTITY` are protocol pinned by test — a freeze decision about
them is a decision about what every report can say. `check_guards` gained a
keyword (`scan_exchangeability`, default False — existing callers
unchanged) and `GuardReport` three more not-findings `measured_*` fields,
extending the sentence 1055's entry flags. The scan is deliberately absent
in Pawley mode and for `mode_fixed`-held paths (the module docstring has the
confident-wrong-singleton argument); if the freeze documents the carrier,
document that absence with it.

**From [1055](1055-background-evidence.md), closed 2026-08-12 — the third
lander's surface changes for the freeze.** `THRESHOLDS_VERSION` is now
**0.6**. `FitReport` gained `background: BackgroundEvidence | None`
(absent-for-cause when the result carries no background curve) and
`RefinementResult` gained `identifiability: Identifiability | None` — the
first field on the result whose value cannot be recomputed from the result
(it is read off the final Jacobian, which is never serialized), so a freeze
decision about it is a decision about *what a stored result promises*, not
just about a shape. Both are additive and defaulted, so `SCHEMA_VERSION`
stays at 0.1 on the WP-1043 events precedent. New exports on
`anatase.report`: `BackgroundEvidence`, `assess_background`,
`background_actions`, `background_clause`, `note_background_crosstalk`,
`too_flexible`, `too_stiff`; new on `anatase.schemas.results`:
`Identifiability`. `GuardReport` gained a seventh field,
`measured_background_absorption`, which is **not** findings — worth naming in
the freeze because the six-findings-fields sentence has been the documented
shape of that dataclass since v0.2. Two `ActionKind` members that had never
been emitted anywhere now are (`increase_`/`decrease_background_flexibility`),
which changes what a client can actually receive without changing the closed
vocabulary itself.


**From [1057](1057-purpose-grade-evidence.md), closed 2026-08-12 — the
second lander's surface changes for the freeze.** `THRESHOLDS_VERSION` is
now **0.5**. `FitReport` gained two defaulted fields: `lebail_gap:
LeBailGap | None` (a new four-field model — `rwp_rietveld`, `rwp_lebail`,
`ratio`, `n_cycles`; None is *absent-for-cause* outside Rietveld mode and on
model-free reports, a semantics worth a freeze-time doc sentence) and
`abstained_kind: Literal["immature", "resolution_limited", "unreadable"] |
None` — a **closed** vocabulary, so adding a kind is a minor version and
renaming one is breaking. `anatase.report.__all__` gained `LeBailGap`,
`lebail_gap`, `abstention_flavour` and `contents_signature`; nine pinned
constants joined `report.schemas` (`LEBAIL_GAP_*`, `RESOLUTION_LIMITED_*`,
`CONTENTS_*`). The summary string now carries up to two extra clauses (gap +
contents) and the abstained reason a flavour sentence — anything freezing
summary *wording* freezes these too. All additive; no `ActionKind` changed.

**From [1054](1054-abstained-branch-honesty.md), closed 2026-08-12 — the
first of the queued six landed; its surface changes for the freeze.**
`THRESHOLDS_VERSION` is now **0.4** (the planning session's "may bump" below
is decided: emission conditions moved on measured states — reindex on the
abstained branch, capped impurity/texture confidences — and WP-1024's
no-bump precedent was rationale-only). Schema surface: `TextureAnalysis`
gained `caveat: str | None` (set when strong unmatched peaks coexist with a
detection), and `best_axis` is now **always populated** evidence with
`detected` the only branch field — a consumer that treated `best_axis is
not None` as detection would silently change meaning, which is worth a
freeze-time doc sentence. `anatase.report.__all__` gained `reindex_action`
and `cap_texture_crosstalk`. All additive; no `ActionKind` changed meaning.

**From the 2026-08-11 planning session (FitReport design review + 1053
follow-ups) — six queued WPs touch surface this freeze covers; sequencing is
this WP's call.** [1054](1054-abstained-branch-honesty.md)…[1058](1058-report-delivery.md)
propose additions to the report/agent surface, all shaped to be additive
(defaulted `FitReport`/result fields, a new task arm, protocol text), with
[1059](1059-eval-round-two.md) re-running the A/B afterwards. Two interactions
to decide rather than inherit: 1054 may bump `THRESHOLDS_VERSION` (changed
Layer-2 emission conditions on the abstained branch — the report contract, not
the schema); and 1058 (a `diagnose` task / per-stage report trajectory) adds a
task-union arm, so freezing the union before 1058 means freezing an
already-planned extension out or in. 1058 explicitly does *not* decide the
vary-or-tie `parameters` filter — that stays the question below.

**From [1053](1053-agent-in-the-loop-eval.md), closed 2026-08-11 — one
serialisation contract the freeze should confirm as deliberate, with its
measured consequence.** `_build_result` serialises into
`RefinementResult.parameters` only entries with `vary or tie` (refine.py,
`_build_result`'s entry loop), so a **fixed** parameter is *absent*, not
present at its held value, and `RefinedParameter.initial` is never populated
on this path. WP-1053's scorer leaned on the absence deliberately (absent ⇒
never freed ⇒ still the start value — decidable because its shim fixes the
start), and the pilot measured the consumer-side effect: an agent reading
`parameters` cannot see that a held parameter *exists*, so a planted
sample-displacement survived 16/16 runs invisibly behind χ²_red ≈ 1.01.
Freeze the vary-or-tie filter as the contract (a client wanting the full
table has `Refinement.parameters()`, WP-1004) or widen it — but decide it,
don't inherit it; and if `initial` stays unpopulated on the fit path, the
field's docstring should say who does populate it.

**From [1052](1052-report-loop-eval.md), closed 2026-08-11 (recorded here at
the 1053 close, which retired the focus text that carried it) — the
`predict_then_verify` contract is pinned by an executable consumer, so the
freeze confirms rather than re-derives it.** `tests/test_report_loop.py`
runs AGENT_PROTOCOL §9's canonical loop closed: accept on >1 % χ²
improvement, a rejection leaves a dead leaf and a bit-untouched parent, the
shared tree's HEAD *is* the verify node after acceptance, and
`VerificationOutcome` carrying **no node id** is measured sufficient — the
freeze can confirm that omission as deliberate.

**From [1051](1051-sequential-escalation.md), closed 2026-08-09 — four series
surfaces moved, all additive, and one of them is a format rather than a field.**

1. **`SeriesEntry` gained `rung` and `rungs_tried`** (which attempt produced the
   values; every attempt made, in ladder order). `reseeded` and `rwp_warm` kept
   their exact meanings — only the *cold* rung sets `reseeded`, and `rwp_warm` is
   still the first warm attempt's Rwp — so a client reading the old two fields is
   unaffected. Freeze the four together: `rung == "cold"` is **not** the same
   question as `reseeded`, because the first pattern of every chain runs the cold
   rung with nothing to warm from.
2. **`SeriesResult.to_table`/`write_csv` grew a `rung` column**, positionally
   *between* `status` and `rwp`. That is the one change here a client can trip
   over — a reader indexing columns by number sees `rwp` move from 4 to 5. It was
   landed before the freeze deliberately, for that reason.
3. **`SEQUENTIAL_UNRECOVERED`** (warning) is new, and the *behaviour* behind it is
   the part to freeze: a diverged pattern seeds no successor and joins no reseed
   median. `Diagnostic.code` is an open vocabulary, so this needs no schema
   decision — but AGENT_PROTOCOL's two tables now carry it, and a consumer's
   handling of a quarantined point is a documented contract.
4. **`series_rung` is a new event `data` key**, stamped on a *restart* only, and
   `series_cold` was kept beside it purely so the change stays additive
   (`EVENT_SCHEMA_VERSION` still "2"). If the freeze wants one authority on the
   wire, dropping `series_cold` is the version bump to price — the argument for
   keeping it is in `sequential._rung_stamp`.

**From [1046](1046-candidate-cap-before-ranking.md), closed 2026-08-09 — three
indexing-surface facts, and one question the freeze should settle.**

1. **`SearchSpec.max_candidates` changed meaning without changing its name**: it
   is the **reported** cap, applied once, by consensus, and each (engine ×
   system) unit hands the merge `SearchSpec.engine_pool()` =
   `ENGINE_POOL_MULTIPLE ×` it. Freeze the pair — a client that reads the field
   as "candidates per engine" is reading the pre-1046 contract.
   `estimate_ceiling().validation_calls` still prices `max_candidates`, and that
   is now exactly right rather than approximately.
2. **New names on the indexing surface**: `engines.ENGINE_POOL_MULTIPLE`,
   `engines.MIN_AGREEMENT`, `engines.agreement`, `engines.corroborated`,
   `SearchSpec.engine_pool()`, and one new diagnostic code
   `INDEX_CANDIDATES_TRUNCATED` (info, with its `AGENT_PROTOCOL.md` row).
   `PRIOR_FINDER` **moved** from `indexing.priors` to `indexing.engines` and is
   re-exported from its old home, so both spellings work; freeze whichever you
   prefer, but say which.
3. **The reported order now leads with corroboration** (`engines.corroborated`,
   binary at `MIN_AGREEMENT`), then Borda over the panel. A consumer that
   assumed "candidates[0] is the panel's winner" is assuming the pre-1046 order;
   what it *is* now is "corroborated first, panel-ranked within that".
4. **Unsettled, and noticed while doing 3**: `consensus.grade` floors a
   candidate at `low` on `len(set(found_by)) < 2`, and `found_by` may contain
   `PRIOR_FINDER` — so a **one-engine candidate that a declared prior also
   matched grades `medium` rather than `low`**. That is a prior changing a
   *verdict*, which WP-1045's "a prior steers, never gates" appears to forbid;
   the ranking key was made to exclude it (WP-1046) and the gate was left
   alone, because changing a grade is a scoreboard-moving decision and not this
   WP's. Settle it before the freeze: either `grade` counts engines the way
   `agreement` does, or the rule is written down as "a prior corroborates but
   does not confirm" with the measurement to back it.

**From [1047](1047-vendor-pattern-formats.md), in flight 2026-08-08 — the
reader surface the freeze covers has changed shape, and one signature broke on
purpose.** Four things to fold into the freeze rather than re-derive:

1. **`read_pattern(path, *, diagnostics=None, **options)`** — the `block=`
   keyword this file recorded as "additive" is gone as a *named* parameter. It
   is now one entry in `io.readers.READER_OPTIONS`, the build-wide allowlist,
   with `PatternFormat.options` naming the subset each format honours and
   `reader_options_for` the single authority that coerces and filters. Freeze
   the pair, not the keyword: a format added after the freeze adds an option
   without touching the signature.
2. **`Project.create(block=)` became `reader_options=`** — dropped, not
   shimmed, deliberately: the freeze had not landed, a shim would be a second
   authority, and every call site was in this repo. If the freeze wants a
   deprecation path for anything, this is the precedent to reverse.
3. **`DataRef.options` records the *effective* options** (what the parse used,
   not what was requested), and its vocabulary grows with the formats — so a
   `scan` entry lands when the multi-scan readers do, which is the
   `PROJECT_FORMAT_VERSION` minor bump WP-1047 task 8 carries. The **major**
   gate already opens such a project correctly.
4. **Additive schema fields, no bump** (the events rule): `ReaderCapability`
   gained `refuses` and `Capabilities` gained a `reader_options` arm. Confirm
   that reading rather than re-litigating it.

**Updated 2026-08-09 (1047 tasks 8-9, `.ras` and `.uxd` landed).** Point 3 has
happened: **`PROJECT_FORMAT_VERSION` is now `"1.1"`**, `scan` is in
`READER_OPTIONS`, and `DataRef.options` records it. Three additions, each a
decision the freeze should make rather than inherit:

5. **`ReaderCapability` did *not* gain a `scans` field**, though this WP's
   contract-versions section mentions one in passing. A meta-test holds
   `fmt.scans is not None ⟺ "scan" in fmt.options`, so the field would be a
   second authority for one fact. Smaller surface; confirm rather than add.
6. ~~Three formats spell the same diagnostic three ways.~~ **Settled in
   WP-1047 at the fourth consumer** (`.xrdml`), which is where its own rule
   said to factor: the policy is `io.formats.base.check_axis()`, the code is
   **`PATTERN_X_AXIS_ASSUMED`**, and the classifying stays per format because
   the four inputs are four shapes. Nothing left to decide — confirm the one
   code in the freeze's vocabulary and that no `*_X_AXIS_ASSUMED` survives.
7. **`DataRef.has_sigma` now covers a *derived* σ, and three formats produce
   one.** A `.ras`/`.rasx` exported as a rate gets σ = √(y·t)/t from the file's
   own counting time; an `.xrdml` point behind a beam attenuator gets
   σ = √counts·a; a `.brml` absorber point gets σ = √(y/a)·a. All three set
   `has_sigma`, so every surface says "σ from file", while the same scans
   without the scaling get `has_sigma` false and the Poisson fallback, which is
   correct. Every one is honest — a derived σ genuinely could not come from the
   fallback — but the flag is documented as "σ *measured*, not σ *present*" and
   a reader-derived σ is a third thing. Decide whether it needs its own state
   before the surface freezes; nothing depends on the answer yet.

**Updated 2026-08-09 (1047 tasks 10-12, `.xrdml`/`.rasx`/`.brml` landed).**
Point 6 is now settled (struck above). Two more for the vocabulary review:

8. **Two format-specific diagnostic codes joined `RAS_ATTENUATOR_PRESENT`** —
   `XRDML_ATTENUATOR_APPLIED` and `BRML_ABSORBER_ENGAGED`. They are deliberately
   *not* one code: the three say opposite things about the same field (not
   applied / applied / already applied by the vendor), so a consumer switching
   on them is switching on the answer, not on the format. Confirm rather than
   collapse — this is the contrast with point 6, where the three codes meant one
   thing.
9. **`PROJECT_FORMAT_VERSION` did not move again.** Five formats now take
   `scan`, but the *vocabulary* did not grow past the 1.1 bump task 8 made, so
   there is nothing further to record. Confirm and move on.

**Updated 2026-08-09 (1047 closed — `.raw` v3/v4, the instrument hint, the scan
picker).** Points 1-5 and 7-9 stand as written; three additions, and one is a
*shape* the freeze has to decide on rather than confirm:

10. **`suggest_instrument(metadata) -> dict | None` is a new public-ish
    surface** (`gui.imports`), and its return value is a **preset spec**, the
    same dict shape `instrument_from_preset` consumes — deliberately, so the
    hint round-trips through the form without a second vocabulary. It is
    reachable only through `POST /api/upload/pattern`'s `instrument_hint` field
    today. Decide whether the freeze covers it as an importable function or only
    as a wire field; if the former, `WAVELENGTH_RTOL` and the three-candidate
    match become frozen behaviour.
11. **`GET /api/upload/pattern/scans` is the first upload route that is not a
    POST**, and the first read-only one. `UPLOAD_ROUTES` still maps only the
    POSTs, so this lives in `ROUTES` beside the rest — worth confirming the
    freeze's route inventory reflects that split rather than assuming the
    `/api/upload/` prefix means one family.
12. **`METADATA_KEYS["wavelength_alpha2"]` now carries a load-bearing zero.** A
    recorded Kα2 of 0.0 means "the file says the doublet was not used" and
    resolves to the `…Ka1` radiation; an *absent* key means the format records
    nothing. Since `metadata()` drops `None` and stringifies `0.0`, the
    distinction is present-vs-absent in a `dict[str, str]` — which works, and is
    the kind of thing a freeze should either bless explicitly or replace with a
    typed field.

**From [1026](1026-indexing-acceptance.md), closed 2026-08-08 — one constant's
*meaning* is in question, and freezing it would ratify a behaviour nobody
intended.** `engines.DEFAULT_MAX_CANDIDATES = 12` is documented as "a cap, not a
ranking: the panel ranks, and 1024 consensus-merges". Measured on the
bethanechol benchmark, it **is** a ranking: it truncates each engine's *own*
Borda before consensus ever ranks, so on set F the published lattice — found by
both `svd` and `trial_error` — is returned first at a 5 s budget and is **absent
from the result** at 30 s. Filed as
[1046](1046-candidate-cap-before-ranking.md), with the second half measured too:
raising it 12 → 60 over the benchmark's whole manual half is **net zero** (F
enters at rank 3, Db is displaced from first). So the freeze should either
follow 1046 or state explicitly that the cap's number is frozen while its
*documented meaning* is known to be wrong. This is a docstring-and-semantics
question, not a signature one — the field itself is already public on
`SearchSpec`/`SearchSpecSpec`.

**From [1050](1050-suggest-next-parameter.md), closed 2026-08-08 — a new
read-only surface for the freeze to ratify.** `Refinement.suggest(data, *,
top_n, include, exclude, mode, two_theta_limits, report)` →
`SuggestionResult` (`schemas/suggest.py`: `ParameterCandidate`,
`CandidateGroup`, three gate constants with measured calibration; all three
models package-exported). The *shape* is the contract: no `.best`, only a
gated `best_or_none()`; `action_kind` a plain `str` pinned to Layer 2's
`ActionKind` by meta-test, because schemas cannot import report. The agent
request union grew its fifth arm (`task="suggest"`, the first no-solve
task): `_BackendBase` (backend only) split out of `_RequestBase` so
solver/plan on it fail by name, `AgentSuccess.suggestion` joined the
exactly-one-of invariant, and `test_agent_surface.py` pins
`len(oneOf) == len(_TASK_TAGS) == 5`.
`optimize.statistics.one_parameter_gains` is new one rank down.

**From [1045](1045-indexing-search-controls.md), closed 2026-08-08 — the
control surface moved house and two names changed, all pre-freeze on
purpose; the freeze ratifies the new shapes.** `SearchSpecSpec` now lives in
`schemas/indexing.py` (agent re-exports it — the `StageSpec` precedent) and
gained `centrings`, `prior_cells`, `prior_spacegroups`; `IndexingControls`
(search + engines + validate_candidates + check_top) sits beside it and is
embedded as `ProjectDoc.indexing` — a **project-format** surface, though no
format-version bump was taken (additive with defaults; old documents read
back with the defaults, pinned). Renames the freeze should know were
deliberate: `SearchSpec.sigma_sys_deg` → `shift_allowance_deg` (with the
CLI flag `--sigma-sys` → `--shift-allowance`, the agent field, the engine
stats key and the provenance note — `viz` reads the old note key as a
legacy fallback, pinned). `capabilities()` gained four arms
(`indexing_engines`, `crystal_systems`, `centrings`, `shift_templates`);
`IndexRequest` gained `check_top`; `index_pattern` behaviour under a
ceiling changed additively (`VALIDATION_RESERVE_FRACTION`, ambiguity after
validation — `consensus.enumerate_ambiguity` is a new public name).
`INDEX_PRIOR_USED` joined the open diagnostic vocabulary.

**From [1042](1042-anytime-results-quick-default.md), closed 2026-08-07 —
the default changed and the surface grew, both for the freeze to ratify.**
`index_pattern` gained `preset=` and resolves `"quick"` (a 120 s whole-run
ceiling) when the caller declares nothing — a *behaviour* default the freeze
locks in, stated in AGENT_PROTOCOL §7d; `IndexingResult` gained `preset`
(additive, defaults `None` on old records); `SearchSpecSpec` (agent) gained
`preset`; `capabilities()` gained the `search_presets` arm; and the event
ladder gained additive `data` fields plus `consensus:<system>` units
(`EVENT_SCHEMA_VERSION` stayed 2 under the events rule — same judgement to
ratify or bump deliberately as 1043's below).

**From [1043](1043-agent-and-human-indexing.md), closed 2026-08-07 — three
additive surface extensions the freeze must ratify, not discover.**
`AgentSuccess` gained the `evidence` arm (`IndexingEvidence`, present exactly
when `indexing` is), `IndexCaveat` gained the capping member
`fom_panel_reduced`, and `PeakFlag` gained `axial_tail` /
`kalpha2_residual` (both informational — deliberately absent from
`PEAK_UNUSABLE_FLAGS`). All three were judged the events rule's "new field,
not a new kind"; `SCHEMA_VERSION` stayed 0.1 and the grounds live on
`AgentSuccess.evidence`'s docstring. The freeze should either ratify that
judgement or bump deliberately — the decision record is there to be
disagreed with, not rediscovered.

**From [1060](1060-docs-ci-consolidation.md) (closed 2026-08-06) — three more
free-tier CI shapings for the going-public un-shaping list.** The workflow
headers already say "undo on going public"; 1060 added: the job-level `if`
skipping the merged-PR push run in `ci.yml`/`gui.yml`, the dispatch-only
macOS job in `monthly.yml` (whose goldens guard now lives locally in
`test_backend_shim.py` and stays either way), and the weekly `pythons`
matrix trimmed to the 3.11/3.14 edges. Publishing makes standard runners
free: the first two conditions can simply be deleted, and the matrix can
grow back to the full support window in one nightly.

**From [1016](1016-sequential-series-panel.md) (closed 2026-08-05) — one
deliberate omission this WP has to decide, and three surfaces to cover.**

The omission: **a series has nowhere durable to live.** Its patterns are staged
uploads (`UploadStore`, emptied by `GuiSession.close`) and its answer is
session-scoped, because `ProjectDoc.patterns` is length 1 and `Project.open`
refuses more — so closing the window loses the staged list, which is the one
absence a user notices. Persisting it needs a *document* naming the files (paths,
reader options, the coordinate, the chain settings), and the v1.0 GUI plan
explicitly told 1016 to record that here rather than grow the project schema
mid-WP. It is the same seam multi-histogram (WP-0308) wants, so decide the two
together or fence both: a `series/` block in `project.json` referencing files
*outside* the project directory is a new kind of reference, and `DataRef` records
a filename relative to the project on purpose.

The surfaces: `SequentialRefinement.fit` gained **`events=`/`cancel=`**, so the
frozen signature is the one with them — and with it a documented event contract
(`series_index`/`series_label`/`series_n`/`series_pass`/`series_cold` as *added*
`data` fields on existing kinds, so `EVENT_SCHEMA_VERSION` stays "2") and a new
diagnostic code `SEQUENTIAL_CANCELLED`. `sequential.REFIT_MODES`/`DIRECTIONS` and
`sequential.unique_labels` are now public because the GUI quotes them; freezing
them means a caller may rely on the tuples' *contents*. And **six new routes**
(`GET`/`PUT /api/series`, `POST /api/series/run`, `GET
/api/series/{result,window,history}`) plus two module-level helpers promoted out
of `GuiSession` — `session.curve_window` and `session.tree_payload` — which two
panels now share; `project.fitted_mask` likewise became a function beside the
method. Freezing the method without the function would leave the shared authority
un-frozen.

**From [1041](1041-indexing-benchmark-gallery.md) closing, 2026-08-05 — two more
surface changes, and unlike `log_sum_scores` below both are wired and load-bearing.**

- **`anatase.indexing.engines.match_window(peaks, spec=None, quality=None)`** is a
  new public export: the σ(Q) the *search* matched with, which is `q_esd` widened
  by the shift allowance. It exists because `consensus` and `viz.indexing` were
  deriving it two ways and the second was wrong. Freeze it as the **one authority**
  — a third caller re-deriving it is the defect it was created to prevent.
- **`viz.indexing.plot_candidates` gained `q_match=`**, defaulting to
  `peaks.q_esd()`. The default is the identity when no allowance applies, so it is
  backward compatible, but *a caller with a result in hand should always pass
  `match_window`* — the default silently draws a figure whose legend contradicts
  its own labels on any pattern carrying an allowance. If the freeze wants a
  narrower surface, the alternative is to take the `IndexingResult` instead of the
  window; either way the parameter cannot simply be dropped.

`tests/indexing_gallery.py` is a test helper and deliberately **not** public
surface, despite being the thing that generates the scoreboard.

**From [1041](1041-indexing-benchmark-gallery.md), 2026-08-05 — one new public
export that is deliberately unwired, and the freeze has to decide about it.**
`anatase.indexing.fom.log_sum_scores` (plus `AGGREGATE_EXCLUDES`,
`AGGREGATE_FLOOR_RTOL`) is exported from `fom.__all__` and `indexing/__init__`,
is tested, and **nothing in the package calls it**: `rank_candidates` still
aggregates with `borda_scores`. It ships because it is the instrument that
measured the panel-aggregation question and refuted the recorded design, and its
docstring carries that measurement. Freeze options are to keep it public as a
measurement tool, make it private, or land a successor aggregate first — but it
must not be frozen *by accident* as a supported ranking API, because it is not
the ranking. Same question, smaller: the constants are exported beside it.

**From [1044](1044-gui-view-cursor-theme.md), 2026-08-06 — one new route pair,
and the `ui`-only question below is now smaller rather than open.** `GET`/`POST
/api/settings` is the **app's** `ui` dict, in `state_dir/settings.json` beside
`recent.json`, with `POST /api/project`'s exact grammar at app scope (top-level
merge, `null` drops a key, persisted on the verb) — so the freeze covers two
`ui` scopes and the rule that tells them apart: a key belongs to whichever thing
it is *about*. The theme moved there because `ProjectDoc.ui` re-read it per
project (measured: dark, open a second project, back to `system`), and its
`ui.theme` key is now simply unread — an existing project's stored value is
inert, deliberately not migrated. Two consequences for the questions already
here. The **"a `ui`-only patch is not model state"** question loses its
motivating example: `/api/settings` takes no lock, so a theme is settable
mid-run and *asserted* to be, while `simple`/`console_height`/`side_width`/
`model_columns` still ride `POST /api/project` and still 409 — the question is
now only about those four. And the freeze should decide whether an app-level
store is the right home for anything else a client currently keeps per project.

**From the 2026-08-04 use session (WP-1032…1036) — two freeze-relevant surface
changes and one that touches a question already in this mailbox.**
[1035](1035-symmetry-surfaced.md) makes a phase's **space group editable**
through `PATCH /api/structure` plus a preview verb beside it, so the freeze
covers a route that can change what the parameter table *contains* — and the
existing behaviour it repairs is itself a defect worth pinning at freeze time:
today that route accepts a symbol change, commits an `edit_model` node, and the
incompatibility surfaces as a **500 on the next `GET /api/params`**.
[1033](1033-plot-range-regions.md) makes the GUI a writer of
`two_theta_limits`/`excluded_regions` through `POST /api/project`, which until
now has only ever carried `{ui: …}` from a client — so the **"a `ui`-only patch
is not model state" question below stops being about `ui` alone**: the same
route will carry genuine settings, and whether a settings patch may land while a
run is in flight is the freeze's call, not a panel's.

**1033 closed 2026-08-05 and left that question exactly where it found it**, on
purpose: a settings patch still 409s mid-run and is now *asserted* to, on the
grounds that an exclusion changes which channels the compiled model was built
from — which is an argument about `two_theta_limits`/`excluded_regions` and not
about `ui`, so the mailbox question stands. Four things it added for the freeze
to cover: **`Project.fitted_mask()`** (the one authority for which channels the
next run fits); **`schemas.project.check_interval`** plus field validators on
`ProjectDoc`, so an inverted or empty interval now raises where it used to be
stored — a *behaviour* change to a shipped schema, worth pinning deliberately;
an **`excluded` arm, `n_excluded` and `stale`** on `/api/result/window` and on
`GET /api/peaks`'s `pattern`; and **`n_fitted`** in `GET /api/project`'s `data`.
[1036](1036-crystal-system-settings.md) may change which cell parameters are
refinable for two space-group settings; if it lands after the freeze it is a
behaviour change to a frozen surface, so prefer it before.

**From WP-1027 (peak picker + indexing panel, 2026-07-31) — new public surface
for the freeze to cover.** `ObservedPeak` gained `origin`
(`"fitted"|"manual"|"edited"`, default `"fitted"` — provenance a reader weighs,
no gate branches on it); `indexing.pick` now exports `pick_peaks_with_state`,
`peaks_of_group` and `flag_ghosts(only=)`; `indexing.peakfit` exports
`fit_group_at` and `group_profile`. The GUI wire surface grew the whole
peak/index route family and `RESERVED_ROUTES` is now empty; on 2026-08-01 it
grew two more — `POST`/`GET /api/index/extinction` (the WP-1025 screen as a
fourth run kind, `"extinction"`, in `GuiSession.run`'s vocabulary) — so the
run-kind set the freeze pins is `fit | stage | index | extinction`. One versioning
question is deliberately left to you: `peaks.json` (the `.rex/` container's
peak-list artifact, `gui/peaks.py`) carries its own internal
`format_version "1"` and is *not* one of the five contracts `capabilities()`
quotes — decide at freeze time whether it becomes the sixth or stays a GUI
internal.

**From the 2026-07-30 assessment session — your dependency list grew by one, and
one frozen constant is on a decision.** [1030](1030-engine-scaling-low-symmetry.md)
was added to the indexing group (engine cost at low symmetry, plus the two
Oishi-Tomiyasu figures of merit), so this row now depends on 1004–1030 rather
than 1004–1027. Two consequences for the freeze itself. `SearchSpec` gains or
changes fields there — at minimum `MAX_ANGLE_COSINE` is explicitly filed as a
*costed choice* to be decided on measurement (150° today against DICVOL04's
130°), and the volume-envelope slack may become a `SearchSpec` field rather than
a `consensus` constant — so **do not freeze `SearchSpec` before 1030 closes.**
And `fom.FomPanel` is expected to gain two members (`M^Rev`, `M^Sym`), which is a
schema addition on a type that already travels on every `CellCandidate`; if 1030
slips, freeze the panel as *extensible* rather than fixed, since the two figures
are published and their absence is a recorded gap rather than a design choice.
(These three references said "1029" when written; that WP was renumbered to
[1030](1030-engine-scaling-low-symmetry.md) the same day — 1029 is the GUI
usability WP, closed — and the stale number would have read as "already
satisfied".)

**From WP-1025 (landed 2026-07-30) — new frozen surface, and one decision left
open on purpose.** `determine_extinction_symbol` is exported from `anatase` as a
peer of `index_pattern`, with `ExtinctionCandidate`/`ExtinctionScreen` in
`schemas/indexing.py`; `ExtinctionScreen.best_or_none()` is the singleton
accessor and the freeze should cover the *absence* of a `.symbol`/`.space_group`
attribute as deliberately as it covers what is there. The open decision: **the
agent JSON surface has four task arms and the extinction screen is not one of
them.** WP-0602's union is strict and `agent.tool_definition()` quotes live
registries, so adding a fifth arm is a schema change that ought to happen before
the freeze rather than after — or be declined on the record. Note its answer is a
third *shape* (a ranked list of classes, each with a list of groups), so it would
need its own arm the way `indexing` did, not a field on an existing one.

From **WP-1014** (import & in-GUI editing, landed 2026-07-30) — **one question,
and some new public surface.**

The question: **should `Atom.species` validate?** A `Structure` carrying a species
no form-factor table knows (`"D"`, `"Xx"`, a CIF's `"Wat"`) validates fine today
and fails at *stage compile*, a long way from where it was typed.
`GuiSession._as_structure` now refuses it at the GUI boundary, naming the atom —
which means the GUI is stricter than the API it fronts. That asymmetry is
defensible (an earlier, better message on the path a human takes) and it is
exactly the kind of thing a freeze should make a decision about rather than
inherit: either the schema validates and the two agree, or the difference is
documented as deliberate.

The surface, all new here and all inside `anatase.gui`: the module
`anatase.gui.imports` (`UploadStore`, `MAX_UPLOAD_BYTES`, `UPLOAD_KINDS`,
`INSTRUMENT_PRESETS`, the `preview_*` functions), `UPLOAD_ROUTES` in `server.py`,
`GuiSession.upload`, `GuiSession.structure_aniso`, and two additive route
changes — `GET /api/structure` gained a `sites` arm, and `POST
/api/structure/aniso` is new. The upload routes are also **the only ones in the
wire surface whose body is not JSON** (raw bytes; filename and reader options in
the query string), which any statement of the HTTP contract has to say out loud.


From **WP-1013** (landed 2026-07-30) — **the wheel redistributes third-party
JavaScript, and until now nothing said so.** The committed dist ships inside the
wheel by design, so `assets/app.js` carries Svelte's runtime (true since WP-1010,
never written down) and `assets/vendor-cm.js` carries CodeMirror 6 — ~330 kB of
it. Both are MIT and unmodified; `ATTRIBUTION.md` now has a *Bundled frontend
code* section stating it, with `gui/package-lock.json` as the version statement.
What this WP owes at publication is the packaging half rather than the prose: a
wheel that redistributes MIT code should carry those licenses, and the sdist/wheel
metadata currently names only anatase's own. Worth deciding at the same time
whether the `[gui]` extra's description should mention the bundle size, since
`pip install anatase[gui]` now pulls ~460 kB of committed assets whether or
not anyone opens the text pane. `tests/test_gui_dist.py` already asserts every
chunk is *in* the wheel and that none of them names a remote host.

From **WP-1011** (landed 2026-07-30) — **the HTTP wire has a JSON dialect, and
it should be stated rather than inherited.** `json.dumps` writes bare
`Infinity`/`NaN` tokens, which are a Python extension that `JSON.parse` rejects
outright; `gui/server.py` therefore spells a non-finite float as the *string*
`"Infinity"`/`"-Infinity"`/`"NaN"`, matching the schemas' own
`ser_json_inf_nan="strings"`. Nearly every `ParameterRow` has an unbounded side,
so this is the common case, not an edge one. Two consequences for the freeze:
any non-Python client must be told (a `"lo": "Infinity"` that a naive consumer
coerces to `NaN` is a silent wrong bound), and the rule belongs with whatever
statement WP-1017's `gui-power.md` makes about the routes being provisional. A
third option exists and was *not* taken — `null` for non-finite — because it
cannot distinguish +∞ from −∞.

From the **v1.0 GUI expansion** (un-fencing commit, 2026-07-29) — new surface
the freeze must cover, and four decisions parked here deliberately:

- **New freeze surface**: `schemas/params.py` (`ParameterRow`),
  `schemas/plan.py` (the unified `StageSpec`/`PlanSpec` — the unification
  retires the `schemas/history.py` and `agent.py` twins; decide whether the
  re-export aliases are frozen API or a deprecation), `schemas/project.py`
  (`DataRef`/`ProjectDoc`), `capabilities()`, the new `Refinement` verbs
  (`parameters()`, `set_vary`, the set-value verb — WP-1004 settles its
  name against `NodeAction.api_call`'s rendering), and
  `CancelToken`/`RefinementCancelled` (WP-1006).

  *Updated 2026-07-30, WP-1004 + WP-1006 landed.* Now concrete, and the
  top-level exports are already added: `ParameterRow`, `TieSpec`, `PlanSpec`,
  `StageSpec`, `PlanInfo`, `PLAN_INFO`, `PLAN_PRESETS`, `CancelToken`,
  `RefinementCancelled`; the verbs are `parameters()`, `set_vary(globs, vary)`
  and **`set_values({path: value})`** (plural — decided in favour of what
  `api_call` had always rendered, so the persisted `"set_value"` NodeKind
  literal is untouched). Four freeze decisions this leaves:
  (a) the `schemas.history` / `agent` re-export aliases — frozen path or
  deprecation, as above, now that both are one-line `# noqa: F401` imports;
  (b) `NodeAction` gained `seed`/`strain_seed` (WP-1004) and event `data` is an
  open dict (WP-1006) — **the freeze should say explicitly that additive fields
  on these two are not breaking changes**, or every later correction is stuck;
  (c) `ParameterRow`'s field set is pinned to `params.vector.Entry` by test, so
  freezing the row freezes the *internal* dataclass by proxy — say so
  deliberately or the coupling will be discovered the hard way;
  (d) `PlanSpec.stages` is permissive (no `min_length`) because it must read
  pre-v1.0 history headers, with the non-empty check living in the agent
  request validator — that asymmetry is intentional and worth a release note.
- **The HTTP routes and the `.rxt` text format are declared *provisional* at
  v1.0** — schemas frozen, wire/text surfaces not. State this in the release
  notes (WP-1017's `gui-power.md` states it user-facing; this WP states it
  normatively).

From **WP-1007** (capabilities + guard findings, landed 2026-07-30) — new surface
and one open question:

- **New freeze surface**: `capabilities()` and its five models
  (`Capabilities`, `BackendCapability`, `PlanCapability`, `AnodeCapability`,
  `ReaderCapability`), `GuardFinding` (frozen dataclass, its seven constructors,
  and `str(finding)` — a *published* rendering pinned by literals in
  `tests/test_capabilities.py`, because the diagnostics' messages are built from
  it), `GuardReport.findings()`, and the newly exported `auto_background`,
  `diagnose`, `PreferredOrientation`, `capabilities`, `GuardFinding`.
- **`Capabilities` reports four contract versions** — schema, report thresholds,
  event schema, project format. The freeze should state what each promises and,
  in particular, that `features` keys are **additive** (a client must tolerate an
  unknown flag) while removing one is breaking. The flags are derived predicates,
  so `features["indexing"]` flips when `index()` lands with no code change here.
- **Open: should `Diagnostic` grow an optional numeric `value`?** WP-1007 fenced
  it out on purpose (no second diagnostic vocabulary), so a guard's *number* — ρ,
  a block R², a min eigenvalue — reaches a client only inside the message text.
  `GuardFinding` has it as `.value`, but `GuardReport` is transient and never
  serialized, so nothing exposes it. A GUI that wants to sort by ρ has to parse
  prose, which is the failure WP-1007 existed to end, one field short of finished.
  Additive and cheap; decide it here rather than leaving each client to regex.
- `GuardFinding.code` is deliberately an open `str`, not a `Literal` — WP-1028
  adds codes. Say in the release notes that guard/diagnostic codes are an
  extensible vocabulary and that clients must not exhaustively match on them.

From **WP-1005** (project container, landed 2026-07-30) — three freeze
decisions and one new surface:

- **New freeze surface, now concrete**: `schemas/project.py`
  (`DataRef`/`ProjectDoc`, both top-level exports along with `Project`),
  `PROJECT_FORMAT_VERSION` (currently `"1"`, and `Project.open` refuses a
  different *major* by name rather than letting `extra="forbid"` report an
  unknown field), and `io.readers.PATTERN_FORMATS` / `identify_format` — the
  reader dispatch is now a registry two other things quote, so freezing
  `capabilities()`'s reader arm freezes the registry's field names by proxy.
  `read_pattern`'s keyword surface is now `READER_OPTIONS` — see this
  file's `### Inherited` note from WP-1047, which supersedes the
  `block=` sentence that stood here.
- **Decide whether `RefinementState` grows `excluded_regions`.** It does not
  carry them today, so **a history node cannot say what was excluded when it
  ran** — and excluding a region does not change the pattern fingerprint, so
  nothing refuses a replay against a differently-masked residual. WP-1005 works
  around it by recording the regions in `project.json`, which covers a project
  and covers nothing else (a bare `Refinement` + `PatternData` still has no
  record). The field is additive with an empty default; what is *not* free is
  deciding whether `replay` then honours the node's regions over the caller's
  data. Excluded regions are protocol (CLAUDE.md: mirror them or do not compare
  Rwp), which is the argument for settling this before the freeze rather than
  after.
- **A project's `backend`/`solver` are arguments to `Project.open`, not fields of
  `ProjectDoc`** — deliberately, because a project saved with `backend="jax"`
  would otherwise be unopenable where jax is absent (`Refinement.__init__` fails
  fast by design). If the freeze wants them persisted, it needs a stated
  fallback policy, not just a field.
- **`RefinementResult.history` is a dead field** — declared at
  `schemas/results.py:291` (`list[IterationRecord]`), never populated by any
  writer (verified 2026-07-29; `IterationRecord` has no other consumer).
  Delete or fill; **recommend delete** — the GUI reads the event stream, and
  per-iteration curves in every result would violate the state-not-curves
  rule the history nodes follow.
- **`[gui]` extra + committed-static wheel audit**: `src/anatase/gui/static/`
  ships in the wheel (hatchling packages `src/anatase` wholesale) — audit
  wheel *and* sdist contents for the static assets, `help.json`, and
  `build-info.json`, and decide whether the `gui/` TS workspace is excluded
  from the sdist the same way the tests question above is decided.
- **Going public zeroes the `gui.yml` CI line** (~3 billed min per
  gui-touching push today) — a fourth entry for WP-1002's "public is the
  same change as three other things" finding below.

From **WP-1002** (CI matrix, landed 2026-07-29) — **going public is not just a
licence decision: three separate limitations here are consequences of the repo
being a private free-plan repo, and they all lift at once.**

- **CI cannot gate anything today.** `repos/…/branches/main/protection`
  returns 403 *"Upgrade to GitHub Pro or make this repository public"*, so the
  per-push matrix **reports** — nothing stops a red push landing on `main`.
  Making the repo public is therefore also the moment to require the `fast`
  jobs as status checks; do both in one change or the freeze rests on a badge.
- **The whole CI cadence is shaped by a budget that publishing removes.**
  There is no CI budget: this repo is private on the free plan (2000
  minutes/month, billed per job rounded up, default spending limit $0 — so
  over-budget means a month with *no* CI rather than a bill). That is why the
  per-push gate runs one Python instead of four, why the full suite is weekly
  rather than nightly, and why macOS + `[torch]` are monthly — macOS bills at a
  **10× multiplier**, so 5 wall-clock minutes there costs 50. Current spend:
  5 per push, 237/month weekly, 66/month monthly. **Publishing makes standard
  runners free**, at which point the three workflows can collapse into one
  nightly and the per-push matrix can carry the full Python range again. Do
  that in the same change as going public, or the coverage stays artificially
  thin for no reason.
- **The supported-Python claim is now measured, and `pyproject` under-states
  it.** 3.11, 3.12, 3.13 *and* 3.14 all install `[dev]` and pass the fast
  suite; `requires-python = ">=3.11"` is right, but `classifiers` names only
  `Programming Language :: Python :: 3` — add the per-version rows for PyPI's
  filters, and decide whether 3.14 is claimed or left allow-fail in CI.
- **Windows passes but is not a supported platform, and the difference is a
  decision this WP has to take.** Probed 2026-07-29: `982 passed / 115
  skipped / 0 failed` on `windows-latest` + Python 3.13 — but only after
  fixing a real bug (`write_qpa_table` wrote `\r\r\n` rows, i.e. corrupt CSV,
  because `csv.writer` output went through text mode) and naming
  `encoding="utf-8"` at every text-I/O site, since the default is cp1252
  there. `tests/test_portability.py` guards both by AST. **No scheduled job
  runs Windows**, so a claim would be a point measurement dressed as support.
  Either add a Windows job — a fast-suite run is ~3 min at a **2×** multiplier,
  so 6 billed minutes: 6/month folded into `monthly.yml`, 26/month if weekly,
  and free once the repo is public — and then
  claim `Operating System :: Microsoft :: Windows`, or claim
  `POSIX`/`MacOS` only and say Windows is untested. Do not claim it on the
  strength of the one green run — that is precisely the drift this milestone
  exists to stop.
- **The QARR licence blocker below now has a concrete mechanism.** Nothing is
  fetched today: all 18 MB of `tests/data/` is vendored, which is why
  `weekly.yml` has no network step. If 1003 un-vendors the round-robin
  patterns, the fetch route is the Internet Archive (`web.archive.org/web/
  2020id_/…/QARR/col/<name>.prn`), the weekly grows a network dependency it
  currently does not have, and nine acceptance suites become
  network-conditional. Excluding `tests/` from the sdist is the cheaper answer
  if the goal is only "do not redistribute in the wheel" — CI checks out the
  repo and is unaffected either way.
- **`tests/data/backend_goldens/*.npz` are pinned to `darwin/arm64` and skip
  elsewhere** (`GOLDEN_PLATFORM` in `tests/test_backend_shim.py`), measured:
  Linux x86-64 diverges by 1 ulp to 1.7e-13 relative, a libm/summation-order
  difference, on *every* state. Two consequences for a release: a user or
  contributor on Linux sees 8 skips, not 8 failures, which is the intended
  first experience — and the 7.3 MB of npz is pure CI weight in an sdist, so
  the "do the tests ship?" question is now a size question as well as a
  licence one.

From **WP-1001** (validation matrix, landed 2026-07-29) — **one deliberate
behaviour change to put in the release notes, and two smaller freeze items.**

- **`Source.dispersion` now defaults to `Dispersion()` instead of `None`.**
  This is the single breaking behaviour change between v0.6 and v1.0 and it
  changes every computed intensity: anomalous scattering was opt-in through
  v0.6, so **every number in `docs/milestones/` up to and including v0.6 was
  measured without it**. The release notes need the exact escape hatch —
  `source.dispersion = None` reproduces the pre-v1.0 model bit-identically —
  and the one new failure mode: a wavelength inside an absorption-edge
  interval now **raises** where the model previously ran uncorrected (12 of
  1176 element × shipped-anode combinations, including Eu and Ho at Cu Kα;
  0.0–1.2 % of arbitrary synchrotron wavelengths depending on specimen). That
  refusal is deliberate — a selective fallback would leave some species
  corrected and others not, which is the unequal cross-phase bias the
  correction exists to remove — but it is exactly the kind of thing a user
  upgrading from v0.6 hits without warning. Grounds and the full measured
  trade are in `tests/validation_matrix.DISPERSION_DEFAULT_ON` and
  [../VALIDATION.md](../VALIDATION.md).
- **The `DISPERSION_NEGLECTED` diagnostic's `suggestion` text changed** (it
  now addresses a caller who *declined* the block rather than one who never
  enabled it). If the freeze makes any promise about diagnostic message
  stability, note that the `code` is the contract and the prose is not — same
  rule the three `ERROR_CODES` follow.
- **`docs/VALIDATION.md` is generated, not written.** It is the natural
  document to point a PyPI long-description or a "what is validated" section
  at, but it is regenerated by `python -m tests.validation_matrix` from a
  module that lives in `tests/` — so it ships only if `docs/` does, and the
  generator is *not* package API. Decide whether the sdist carries it; do not
  move the registry into `src/` just to make it importable, because its
  content is per-test bookkeeping, not runtime behaviour.

From **WP-0604** (theory manual, landed 2026-07-29) — two facts for the
freeze:

- **`tests/test_manual.py::test_every_source_symbol_imports` is a live list
  of symbols the manual quotes** (every `*Source:*` line in
  `docs/manual/*.md`). A rename during the freeze fails that test — treat it
  as the manual's stake in the API discussion, not as an obstacle; if a
  symbol is deliberately renamed/hidden, the manual page is the other half
  of the edit.
- **An autodoc API reference was deliberately not built** (0604 design
  decision: the docstrings' unicode-math prose would mangle under reST
  rendering with `-W`). If a rendered API reference is wanted for release,
  it is a new document with its own failure modes — budget it here, don't
  bolt it onto `docs/manual/`.

From **WP-0602** (agent JSON surface, landed 2026-07-29): **`anatase.agent` is
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

From the **indexing plan** (WP-1018…1027, added 2026-07-29) — a second block of
new freeze surface, and one API-shape decision that must survive the freeze
intact:

- **New freeze surface**: five entry points that are peers of `refine()` —
  `pick_peaks`, `index_pattern`, `determine_extinction_symbol`,
  `structure_from_candidate`, `validate_by_lebail`; the whole of
  `schemas/indexing.py` (`ObservedPeak`, `PeakFlag`, `PeakList`,
  `DataQualityReport`, `FigureOfMerit`, `AmbiguityPartner`, `CellCandidate`,
  `LeBailValidation`, `IndexingResult`, `ExtinctionCandidate`,
  `ExtinctionScreen`, plus `INDEXING_THRESHOLDS_VERSION` and its pinned
  constants); the `PEAK_*` / `INDEX_*` / `EXTINCTION_*` diagnostic codes; the
  `agent.py` `index` task; and `anatase index` in the CLI.
- **`IndexingResult` must keep having no unconditional singleton accessor.**
  There is deliberately no `.cell`, `.best` or `.solution`; `candidates` is
  always a list and `best_or_none()` is gated. This is the same species of
  guard as `Geometry.mu_r` being a plain `float` — the *type* is what forbids
  the mistake. A freeze is exactly the moment someone adds a convenience
  property "since everyone writes `candidates[0]` anyway"; the answer is no,
  and the reason is that the module exists to be able to say "the data cannot
  distinguish these". WP-1026 ships an API-shape test asserting this; keep it.
  *(Amended by WP-1024, 2026-07-30: the API-shape test landed **here**, not in
  1026 — `tests/test_indexing_consensus.py`, asserting on
  `IndexingResult.model_fields` and on the class itself, plus a second one on the
  **serialized** agent answer, since the envelope is where a convenience
  singleton is easiest to reintroduce.)*
- **`report/schemas.py`'s `ActionKind` does not change** — indexing gives the
  already-declared `reindex_or_recheck_cell` something to call, nothing more —
  so `THRESHOLDS_VERSION` should **not** bump for it. Check this before
  bumping anything reflexively at freeze time.
- **`crystallography.lattice.inv_d_squared`** is new (WP-1018, extracted from
  `d_spacings`) — decide whether it is API or an internal that happens to be
  importable, alongside the other `crystallography/` calls.
- **This WP's `Depends on` becomes `1001, 1002, 1004-1027`**, and the freeze is
  still the milestone's last row: the point of landing indexing before it is
  that the frozen surface has been exercised.

**From WP-1024 (landed 2026-07-30) — three additions to that freeze list, and one
version that already moved.**

- **Two closed vocabularies join the frozen surface**: `IndexCaveat` (the reasons a
  candidate is not `high`) and `INDEX_REFUTING_CAVEATS` (which of them refute rather
  than cap). They are closed for the same reason `ActionKind` is — consumers branch
  on them, and a GUI colours chips from the split — so adding a member is a
  compatibility event, not a detail. Also `Confidence`
  (`"high" | "medium" | "low"`) and `INDEX_MIN_INDEXED_FRACTION`.
- **`EVENT_SCHEMA_VERSION` is now `"2"`.** WP-1024 added the
  `index_start`/`index_end` kinds WP-1006 deferred, which is what that constant is
  *for*; the per-engine progress deliberately reuses `stage_start`/`stage_end` with
  extra `data` keys, which is additive. So the freeze inherits `"2"` and the
  additivity rule written down in `history/events.py` — check it before bumping
  reflexively, in both directions.
- **`AgentSuccess` has a third arm, `indexing`**, and the docstring's "exactly one
  of result/series" became "exactly one of result/series/indexing". A consumer
  branching on which arm is set is the intended contract and is now three-way.
- **`report/schemas.py`'s `ActionKind` did not change and `THRESHOLDS_VERSION` did
  not bump**, exactly as the note above predicted: `reindex_or_recheck_cell` and
  `add_impurity_phase` got new *rationale text* naming `index_pattern`, nothing
  more. Confirmed rather than assumed.

From **WP-0309** (exporters, landed 2026-07-24): `write_refinement_cif`'s
round-trip is validated for **single-phase only** — a full multi-phase
structure re-read was never a v0.3 commitment. Whatever guarantee the frozen
API states about CIF round-tripping has to say that, or narrow the claim.

From **WP-1008** (GUI server, landed 2026-07-30): three additions to the public
surface, and one thing that is explicitly *not* frozen.

- New top-level module `anatase.gui` exporting `GuiSession`, `GuiError`,
  `serve`, `build_server`, `main`, `ROUTES`, `RESERVED_ROUTES`, `DEFAULT_PORT`,
  `EVENT_RING`, `RunState`. `GuiSession`'s **methods** are the surface a Tauri or
  notebook driver would use, so they are worth freezing; `gui.server` is
  transport and can be replaced wholesale.
- Two helpers were promoted from private to public because a fourth and a second
  consumer arrived: `strategy.staged.resolve_plan` (preset name + mode → plan;
  was inline in `Refinement.fit` *and* duplicated as `sequential._resolve_plan`)
  and `viz.compare.decimation_index`. Both are freeze-worthy and neither is
  re-exported from the package root — decide whether they should be.
- **The HTTP wire surface stays provisional at v1.0**, as the note above from the
  GUI plan already says. The freeze covers the schemas the routes carry (all
  existing pydantic models) and `GuiSession`'s method names, not the paths.
- New CLI subcommand `anatase gui`, and a new env var `ANATASE_STATE_DIR`
  (recent-projects store, default `~/.anatase`) — the first user-level state this
  package has ever written outside a project directory. Worth a README line and a
  decision on whether it should be XDG-aware before it is frozen.

From **WP-1009** (text document, landed 2026-07-30): more surface to weigh, and
one signature change.

- `anatase.gui.textdoc` — `FORMAT_VERSION` (`rxt 1`, its own versioned contract,
  making **five** in the build rather than the four `capabilities()` reports),
  `VALUE_DIGITS`, `RESERVED_BLOCKS`, `render`, `parse`, `changes`, `apply`,
  `revision`, and the `TextError`/`Row`/`ParsedDocument`/`Delta` dataclasses.
  Decide whether `FORMAT_VERSION` joins the `capabilities()` contract arm — an
  editor pane needs it, and it is currently only reachable through
  `GET /api/textdoc`.
- **`Refinement.parameters()` gained a keyword-only `mode=`**, and
  `Project.parameters()` is new. Both are corrections rather than additions: a Le
  Bail project's rows were answered for the wrong mode. Freeze the pair together.
- `PlanSpec.preset_name()` is a new schema method (derived, never stored).

From **WP-1010** (frontend scaffold, landed 2026-07-30) — packaging facts the
freeze has to decide about, all measured:

- **The built frontend ships in the wheel** (`anatase/gui/static/{index.html,
  build-info.json,assets/app.js,assets/app.css}`, verified by `uv build --wheel`
  in `tests/test_gui_dist.py`). Hatchling includes it because it is a non-ignored
  file under the package — and the repo-wide `*.html` ignore rule matched
  `static/index.html` until this WP un-ignored it, which is a trap worth
  re-checking before the first real publish.
- **`gui/` itself must not ship** (it is outside `src/`, so it does not today),
  and `gui/node_modules` is gitignored. An sdist that carried the workspace would
  be harmless but confusing; decide explicitly.
- The `[gui]` extra stays **plotly-only**: plotly.js is served from the installed
  package at runtime rather than vendored into the dist, which is what keeps the
  dist at 48.7 kB and the page offline-safe.
- `.github/workflows/gui.yml` is a fourth workflow, priced at ~3 billed minutes
  per GUI-touching push (~120/month at 40 such pushes). It joins the list of
  things that go to zero when the repo goes public.

From **WP-1012** (history/report panels, landed 2026-07-30) — one new module to
freeze and **three additive-field decisions** that only exist because something
finally consumed the report mechanically:

- **`anatase.report.apply` is new public surface**: `RECIPES` (a
  `dict[ActionKind, Recipe]` classifying every member of the closed vocabulary as
  `stage` / `index` / `advice`), `recipe`, `stage_for`, `api_call`, `unreachable`,
  `refusal`, `describe_action`, `missing_kinds`. Re-exported from `anatase.report`.
  Freeze question: is the *classification* part of the contract, or an
  implementation detail of the GUI? It is the second half of `ActionKind` — a
  vocabulary member whose `how` nobody can read is not actionable — so it probably
  belongs in the frozen surface, and then moving a kind from `advice` to `stage`
  becomes a minor-version change the way adding an `ActionKind` member is.
- **`RegionAttribution.gate_failures` has no code field.** It is a list of
  formatted strings (`local_r2=0.31<0.5`,
  `outside_validity_radius(|Δ2θ|=0.030°>…)`), so a client that wants to group
  fifteen regions by *which* gate refused has to read the prefix —
  `gui/src/lib/report.ts`'s `gateName` is that parse, and it is the only message
  parsing left in the frontend. This is exactly the gap WP-1007 closed for
  `Diagnostic.where`, one layer up. An additive `gate: str` (or a
  `list[GateFailure]` with `code`/`value`/`message`) would remove it; deciding
  before the freeze is cheaper than after.
- **`Diagnostic` still has no numeric field**, which WP-1007 fenced out of scope
  and WP-1012 confirmed matters: the history panel renders each node's guard
  diagnostics and cannot sort or threshold on ρ / a block R² / a min eigenvalue,
  because the number is only in the message. `GuardFinding.value` has it and
  `GuardReport` is transient. Additive optional `value: float | None`.
- **`SuggestedAction.expected_delta_chi2` is one number per report**, stamped on
  every Layer-1-derived action by `build_report`, and not a bound on what applying
  one achieves (measured: 16.19 predicted, 16.33 observed). The docstrings now say
  so. If the freeze wants it to *mean* "what this action will buy", that is a
  Layer-2 change (per-action estimation) and a `THRESHOLDS_VERSION` bump — decide
  which of the two the field is before it is frozen.
- **Layer 2 emits actions for corrections the instrument does not have.** Measured
  on a Debye-Scherrer fit: the highest-confidence suggestion (1.000,
  `refine_sample_transparency`) names a path `params/vector.py` force-fixes off
  `bragg_brentano`. WP-1012 reports it as unreachable rather than suppressing it
  (its non-goals forbade changing what the report emits). Whether a *frozen* report
  may propose a structurally impossible action is a contract question, not a
  rendering one.

From **WP-1015** (structure viewer, landed 2026-07-30) — one new public
crystallography function and one route promoted.

- **`crystallography.symmetry.expand_orbit(sg, xyz, *, tol)`** is new and public:
  the orbit as `(position, rotation)` pairs, with `expand_positions` now a
  one-liner over it. It exists because a displacement ellipsoid *transforms*
  (U\* → R·U\*·Rᵀ) rather than merely moving, so any caller drawing or comparing a
  per-image tensor needs the operation and not only the site. Freeze it alongside
  `expand_positions` — it is the more general of the two and the other is derived
  from it.
- **`GET /api/structure3d` is live**, so `RESERVED_ROUTES` is down to the ten
  WP-1024/1027 paths. Its two query parameters (`probability`, `bond_tolerance`)
  are *drawing thresholds* and deliberately not in `ProjectDoc`; if the freeze
  covers the HTTP surface, that distinction is the thing to state, not the
  numbers.
- **The GUI now redistributes nothing new.** plotly.js is still served from the
  installed Python package rather than bundled, and the element colours are this
  repo's own values (see `ATTRIBUTION.md` → Data tables), so the publication
  checklist gains no row from this WP.

From **WP-1029** (GUI usability, landed 2026-07-30):

- **A freeze question, measured and deliberately not settled there.** Changing a
  `ProjectDoc.ui` key while a run is in flight is **refused with a 409**, because
  WP-1008 made every mutating verb refuse and `POST /api/project` is one. Two
  things are wrong with that for a `ui` key and neither was WP-1029's to decide
  unilaterally: **a `ui` key is not model state** — no compiled stage was built
  from the theme — and the refusal the client shows is the generic one, *"this
  verb would change the model a compiled stage was built from
  (frozen-per-stage discreteness)"*, which is simply untrue of a theme or a pane
  width. Measured in Chrome: the theme applies locally, the POST 409s, and the
  console prints that sentence. If the freeze covers the HTTP surface, the rule
  worth writing is **a `ui`-only patch is not a mutating verb** — which is a
  change to what a settled route refuses, hence a freeze decision rather than a
  usability repair.
- **Two more contracts are now quoted rather than copied, and both are cheap to
  freeze.** `GET /api/result` carries a `maturity` arm whose `max_rwp` is
  `report.schemas.MATURITY_MAX_RWP` verbatim, and `GET /api/result/window`
  carries `weighted` plus three residual curves — the point in both cases being
  that a client must not re-derive a number the package owns. They are the same
  shape as `capabilities()`'s registry-quoting arms, so the meta-test style
  there applies.
- **`RefinementResult`'s curve fields are five `list[float]`**, and whether they
  stay that way is a freeze decision because it is the JSON contract. Measured
  on a 59 498-point pattern: **9.6 MB** in memory against **2.38 MB** for the
  same numbers as numpy fp64 — a 4× overhead in Python float objects, for arrays
  that are *never persisted* (a `.rex/` holds the pattern file and
  `history.jsonl`; nodes have stored state-not-curves since v0.2). Three of the
  five (`two_theta`, `y_obs`, `sigma`) duplicate the pattern file the project
  already stores byte-for-byte, and the other two are derivable — `refine.replay`
  recomputes a node evaluate-only today. So the freeze question is narrow:
  **does the frozen surface promise `list[float]`, or arrays?** WP-1029's
  handover log has the full measurement and the trap (as-optimised metrics vs
  as-replayed curves can differ marginally, which is fine for a diagnostic and
  not fine if a plot silently swaps one for the other).

  *WP-1029 (r) settled its half on 2026-07-31, leaving only the field typing
  here.* The decision: **curves stay in-session and nothing new is persisted**
  — a result's five arrays belong to the session that computed them; `y_calc`
  for any *other* node, if a client ever wants it, is a `refine.replay` behind
  a `?node=` parameter on `/api/result/window`, not a schema change, and such
  a response must say it is as-replayed rather than as-optimised (the trap
  above). No route reservation was made — the query parameter does not exist
  until someone builds it, and `RESERVED_ROUTES` is for paths, not options.
  What this WP still owns is only the sentence above: `list[float]` or arrays
  in the frozen contract.

- ~~**The weighted residual is now defined twice**~~ — resolved by WP-1029 (s)
  on 2026-07-31, before this WP starts: it was *five* definitions under three σ
  policies, unified on `RefinementResult.sig()` (a peer of `PatternData.sig()`),
  with `weighted` sourced from `DataRef.has_sigma` and pinned by
  `test_the_weighted_residual_has_exactly_one_authority`. Nothing left to
  freeze here beyond what that test already holds; the normative definition is
  the method, so freezing `RefinementResult` freezes it.

- **`ProjectDoc.ui` gained four keys** (`theme`, `side_width`, `model_columns`,
  on top of `simple`/`console_height`). It is an open dict on purpose; if the
  freeze wants to say anything about it, the sentence is that the *frontend*
  owns those keys and the schema deliberately does not enumerate them.

## Tasks

- [ ] Expand this stub into a full WP before starting

## Handover log

- **2026-07-22** — created as a stub from the ROADMAP split.

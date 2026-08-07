# CLAUDE.md — src/pxrdref/indexing/

Scope: the indexing subsystem — engines, consensus, the FoM panel, the shift
screen, validation, budgets. This is the indexing dossier that lived in the
root CLAUDE.md until WP-1060; it auto-loads when a session works under
`indexing/`, and the root keeps only the clauses that govern behavior outside
this package. The measured stories behind every rule are in
`docs/milestones/v1.0.md` § Appendix (named "the CLAUDE.md indexing dossier"
after this file's former home); the constants live in this package. **A new
indexing rule lands here; it earns a clause at root only if it changes
behavior outside `indexing/`.**

## The governing rule

Indexing's governing rule is the FitReport's one rank up: an indexer
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

## The pipeline

`index_pattern(peaks | data+instrument)` (`workflow.py`) runs that
pipeline: quality gate → engines → `consensus.py` (merge on the reduced
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
so it fires on 61 % either way. Nor can its mirror `unmatched_observed` be a caveat:
its level is the *specimen's*, not the candidate's (10-188 across 21 **correct**
candidates), and inside one pattern it is Rwp again — comparative only (WP-1041).
**The validation fit holds the cell** and frees
exactly one peak-position parameter, from the candidate's own shift template. And on
real data with no measured shift, `high` is currently *unreachable* by design
(`shift_allowance_assumed`); the fix is evidence, not a bigger constant (WP-1026).

## The scheduler, the presets and the stream (WP-1042)

- **(engine × system) units run system-major** — `index_pattern` calls each
  engine with `spec.systems` restricted to one system, all engines finish a
  system before any starts the next (`SYSTEM_ORDER` stays the one authority),
  and `merge_engine_units` folds each engine's units back into the one
  `EngineResult` consensus reads. The point is the deadline: a binding ceiling
  cuts trailing *systems* for every engine equally, never a whole engine, so a
  candidate from a completed system keeps every finder. Two consequences are
  load-bearing: a system is **complete only if every engine that ran entered
  and exhausted it** (`consensus` — a partially covered system used to read
  complete with nothing to name it), and trial_error's dominant-zone probe is
  **deferred** (`probe=False` per unit; `dominant_zone_probe` asked once, over
  the entered systems, only on an empty merged harvest — the probe explains a
  *whole-run* silence, and left per-unit it would fire on every empty system
  of a run that found its cell elsewhere).
- **`quick` is the default preset**: every engine, every requested system, a
  whole-run ceiling (`SEARCH_PRESETS`/`SEARCH_PRESET_INFO`, bijection by
  meta-test, quoted live by `capabilities()` and the agent schema), and
  validation fits each drawing an equal **slice** of the remaining clock.
  Nothing is narrowed — a binding ceiling reports, and what it cuts is the
  trailing low-symmetry systems, cheapest-first ordering's documented cost. A
  declared `total_budget_seconds` is never overridden and records
  `preset="custom"`; `"full"` is the unbounded pre-1.0 behaviour, and **a test
  asserting a complete search declares it** (the acceptance rows all do).
- **What streams is graded conservatively or not at all.** Facts ride every
  ladder emission (`elapsed_seconds`, `remaining_seconds` under a ceiling); a
  finished unit streams ≤3 `provisional` cells with **no confidence field**; a
  *completed* system streams the cumulative ranked list as its own
  `consensus:<system>` ladder unit through the real gate with validation and
  ambiguity still open (`ambiguity=False`, both capping) — a streamed grade
  can rise at the end, never fall. Candidate shape:
  `schemas.indexing.candidate_evidence`, shared with `evidence()` — never
  fork it. All added `data` on existing kinds; a new kind is a version bump.

## The control surface and the priors (WP-1045)

- **One spec, three chairs.** `SearchSpecSpec` (`schemas/indexing.py`, the
  pydantic twin of `SearchSpec`) is what the agent request carries, what
  `ProjectDoc.indexing` embeds (the GUI form edits it; the index run reads
  the document), and what `to_spec()` maps — held field-for-field by
  `tests/test_search_controls.py` (dataclass↔model by `dataclasses.fields`,
  defaults by `SearchSpecSpec().to_spec() == SearchSpec()`, `to_spec`
  coverage per field, `index_pattern`'s signature against declared
  exceptions) and by `gui/src/lib/controls.test.ts` replaying the committed
  corpus `tests/data/gui/index_controls.json`. `_spec_notes` records
  **every** spec field (optional narrowings only when declared), so identical
  controls in two chairs produce byte-identical notes — asserted literally.
  Vocabularies are served by `capabilities()` (engines with descriptions,
  `SYSTEM_ORDER` — the order is information — `CENTRINGS`,
  `SHIFT_TEMPLATES`), never restated in a client.
- **The declared allowance is named for what it is**:
  `SearchSpec.shift_allowance_deg` (was `sigma_sys_deg` until WP-1045 — the
  name collision with `ShiftScreen.sigma_sys_deg`, the residual *scatter*,
  made the measure-on-a-standard protocol fail silently by declaring the
  4.3×-smaller number). `effective_shift_allowance` is the resolver; the
  only `sigma_sys_deg` left is the screen's scatter.
- **The envelope enters a search only through its slack**
  (`search_volume_ceiling`, the one authority all four engine call sites
  use): a declared `max_volume` verbatim, else `VOLUME_ENVELOPE_SLACK ×`
  Smith's mean line (which excludes the true cell below p = 0.71
  line-completeness — pinned at p = 0.6, where the raw envelope reads 0.94×
  the corundum-setting cell). The slack lives in `quality.py` beside the
  formula; consensus flags `volume_unphysical` above the *same* boundary, so
  a cell the search could reach is never flagged for having been reached.
- **A prior steers, never gates** (`priors.py`, three rules pinned by
  `tests/test_indexing_priors.py`). Its system jumps the queue and its
  metric seeds `search_svd`'s starting basin (one deliberate Table-1 start
  per centring, before the random ladder and outside the N_c/N_o gate — a
  statistic about random starts; the caller's box still binds in `_keep`).
  The stated cell is checked the engines' own way and joins consensus as
  finder `"prior"` — merged into an engine candidate when one lattice, else
  appended **after** the ranked list: prior-only candidates never enter the
  Borda ranking (Borda violates IIA, so this is what makes "a wrong prior
  changes no rank" structural). `"prior"` is absent from `engines_run`, so
  `engines_disagree` grades a prior-only candidate down with no new gate
  vocabulary. Two traps live in constants: the check itself can basin-hop
  (`PRIOR_DRIFT_MAX` — a wrong prior once walked to the truth and claimed
  confirmation), and a seeded find legitimately arrives in another setting
  (`same_lattice`, never cell tuples — WP-1040's trap, hit again).

## Engines and the FoM panel

Everything the engines share is `engines.py` — one `SearchSpec`, one
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
**But the panel ranks; it does not score** (WP-1041) — a margin is comparable within a
member, not across them, so a raw log-sum merely re-weights the panel by each member's
dynamic range: 5 of 6 datasets, exactly Borda's, failing on a different one.
`fom.log_sum_scores` carries the measurement and stays **unwired**.
Two things the panel needs from its caller (WP-1026):
the **matching window** is an argument (`fom_panel(..., q_match=)`) separate from the
per-line σ, because coverage members must ask the same "is this the same line"
question the *search* asked while M₂₀ and F_N floor their discrepancy on what the
measurement resolves; and a candidate carrying a fitted shift is scored on
`engines.scored_positions`, the **corrected** lines it claims, or the panel marks it
down for its own correction.

## The search window and the shift

**The search window is a correctness parameter, measured rather than assumed** (WP-1038,
`pairs.py`). A *harmonic reflection pair* — planes that are integer multiples,
so `m·sin θ_B = sin θ'_B` for any lattice — is one equation in the shift and none in the
cell, so Dong (1999) gives its **magnitude** from the peak list alone and
`ShiftScreen.allowance_deg` is what a window must span. Four measured rules, stories in
the appendix. **The magnitude is knowable with no reference and the cause is not** —
`constant` and `cos_theta` concentrate identically, so the screen may refute
`sin_2theta` and never choose between the other two. **Detection is concentration
against a seeded structureless null, because the published false-pair rule fails on real
data** (DICVOL04's margin admits 11-BM NAC at chance, reporting −0.09° where the shift
is zero). **A window wider than the shift manufactures a confident wrong singleton** —
at σ_sys = 0.060 SRM 660c returns a cell 293 000 ppm off at `high` confidence — so
headroom scales the amplitude's *standard error*, never the pair scatter. And **an
allowance is not a correction**: it finds lines, only `shift_template` moves the cell.

**The tolerance an engine searches with is not the per-line σ, and this is the one thing
to know before touching indexing.** A fitted σ(2θ) is the right *weight* and the wrong
*matching window*: measured on the bundled qarr corundum pattern, whose cell is
certified, the lines sit a median 0.060° from the true positions (a cos θ displacement)
against a median fitted σ of 0.0056° — an 11σ systematic — so at 3σ the true cell
indexes **zero** lines and both engines return nothing. Hence
`DEFAULT_UNKNOWN_SHIFT_DEG` (0.05° 2θ, the fallback when the pair screen above declines,
reported as `INDEX_SHIFT_ALLOWANCE` because an assumed precision must never look like a
measured one) and `refine_with_shift`, which fits the shift *template* **after** a
candidate survives — the *shape* needs reference positions, which a candidate cell
supplies. A cell found under a widened window but never shift-refined is biased by
roughly the shift (+1400 ppm measured).

## Thirteen more rules, each learned the hard way

The measured stories are in the v1.0 record's appendix; constants in this package:

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
  inverted). Corollary: **a candidate cell is a lattice, not a tuple** — compare with
  `reduce.same_lattice`, *its centring*, **and the dataset's own accuracy band**,
  never sorted axes. Drop any of the three and a wrong answer reads as right: sorted
  axes miss a correct answer in another setting (WP-1040's monoclinic row), no
  centring reads a P description as its own I truth (NAC), and `same_lattice` alone
  falls back to a deliberately loose 5e-3 that calls FAP's +966 ppm leader and its
  +258 ppm cross-code cell the same answer (WP-1041).
- **Removing a redundant search must not remove its prunes**, and only real data will
  say that you did: the centred passes are redundant *as searches* (each centred trial
  set is a subset of the primitive one) and not as *filters*; the prunes being monotone
  under bisection, replaying one at the leaf is equivalent to the whole pass. WP-1030
  skipped that and put a pseudo-cubic trigonal R description of the certified LaB6
  lattice above the cubic truth with **115 fast indexing tests green** — so run
  `tests/test_acceptance_indexing.py` before closing anything that touches an engine.
- Read a `predicted_but_absent` firing as "this cell predicts lines the pattern
  lacks", **never** "this cell is too big": it counts against the *lattice* group,
  so a space-group extinction (corundum's R-3c c-glide) refutes a correct cell, and
  only the extinction screen separates the two. Choose acceptance datasets **by
  space group** — SRM 660c (P m -3 m) is the control that proved it.
- The known-cell scoreboard is *never wrong, and silent more often than right* —
  **never round it up**, and **keep the found-but-not-first bucket**: the truth *in
  the list* under a wrong leader is what this package produces most, and collapsing
  it into right-or-wrong is how the old board named nine datasets under a total of
  eight. It is **generated** by `tests/indexing_gallery.py`, so re-measure by running
  the suite; counts live in the v1.0 dossier, never retyped here (WP-1041). And
  **say "high-symmetry" whenever the board is quoted** (WP-1043): nine of ten
  known-cell datasets sit at ≤ 2 free metric parameters, so every claim from it
  is about high-symmetry lattices until the corpus moves — post-v1.
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

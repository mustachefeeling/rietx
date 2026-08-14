# CLAUDE.md — src/rietx/indexing/

Scope: the indexing subsystem — the dossier that lived in the root CLAUDE.md
until WP-1060. Auto-loads with this subtree; the root keeps only clauses that
govern behavior outside it. Measured stories: `docs/milestones/v1.0.md`
§ Appendix ("the CLAUDE.md indexing dossier"); constants live in this
package. **A new indexing rule lands here; it earns a clause at root only if
it changes behavior outside `indexing/`.**

## The governing rule

The FitReport's rule one rank up: an indexer must never hand back one cell
confidently — `IndexingResult` has **no** `.cell`/`.best`, only a gated
`best_or_none()`; geometrical ambiguity (Mighell & Santoro 1975) is reported
with the reflections that would break the tie, never silently resolved;
coverage is scored in *both* directions (share-of-observed alone puts a
390-line wrong phase above the truth); a restricted search reports
`systems_searched` rather than concluding anything about the sample. Engines
supply the confidence by **agreeing** (`direction="both"`'s device) — three
of them (two until WP-1040), `high` meaning *every* engine that ran found
the lattice, so adding one raises the bar. They must fail differently for
that to mean anything, and they do: wide domain (dichotomy), poisoned base
line (trial_error), bad starting basin (svd). One step further: the
**extinction symbol**, not the space group, is what a powder measures —
`determine_extinction_symbol` answers with ranked classes, each carrying a
*list* of space groups; there the singleton is not unsupported but
unmeasurable.

## The pipeline

`index_pattern(peaks | data+instrument)` (`workflow.py`): quality gate →
engines → `consensus.py` (merge on the reduced cell, `found_by` union, Borda
over the panel, two-opinion Bravais, ambiguity) → Le Bail validation → the
gate. Three load-bearing rules. **`high` requires zero caveats**, and
`IndexCaveat`/`INDEX_REFUTING_CAVEATS` (`schemas/indexing.py`) are the whole
gate: five caveats refute a cell to `low`, the rest cap at `medium`, and
*count* deliberately separates nothing. **Whole-profile validation is
mandatory** — the FoM panel sees ≤20 lines, so `validate_by_lebail`'s
`predicted_but_absent` is what catches an oversized cell (117 of 153 for a
doubled cell against 0 of 28 for the truth, Rwp moving only 0.216 → 0.379);
Layer 0's `unmatched_calc` **cannot** serve (Le Bail assigns ~nothing to a
phantom, so it fires 61 % either way), nor `unmatched_observed` as a caveat
(its level is the *specimen's* — 10-188 across 21 correct candidates —
comparative only, WP-1041). **The validation fit holds the cell**, freeing
exactly one peak-position parameter from the candidate's own shift template.
On real data with no measured shift, `high` is *unreachable* by design
(`shift_allowance_assumed`); the fix is evidence, not a bigger constant
(WP-1026).

## The scheduler, the presets and the stream (WP-1042)

- **(engine × system) units run system-major** — each engine gets
  `spec.systems` restricted to one system, all finish it before any starts
  the next (`SYSTEM_ORDER` the one authority; `merge_engine_units` folds the
  units back into the one `EngineResult` consensus reads). The point is the
  deadline: a binding ceiling cuts trailing *systems* for every engine
  equally, never a whole engine, so a completed system keeps every finder.
  Load-bearing: a system is **complete only if every engine that ran entered
  and exhausted it**, and trial_error's dominant-zone probe is **deferred**
  (`probe=False` per unit; asked once over the entered systems, only on an
  empty merged harvest — it explains a *whole-run* silence, and per-unit it
  would fire on every empty system of a run that found its cell elsewhere).
- **`quick` is the default preset**: every engine, every requested system,
  a whole-run ceiling (`SEARCH_PRESETS`/`SEARCH_PRESET_INFO`, bijection by
  meta-test, quoted live by `capabilities()` and the agent schema),
  validation fits each drawing an equal **slice** of the remaining clock.
  Nothing is narrowed — a binding ceiling reports, and what it cuts is
  trailing low-symmetry systems, cheapest-first ordering's documented cost.
  A declared `total_budget_seconds` is never overridden and records
  `preset="custom"`; `"full"` is unbounded, and **a test asserting a
  complete search declares it** (the acceptance rows all do).
- **What streams is graded conservatively or not at all.** Facts ride every
  ladder emission (`elapsed_seconds`, `remaining_seconds` under a ceiling);
  a finished unit streams ≤3 `provisional` cells with **no confidence
  field**; a *completed* system streams its cumulative ranked list as a
  `consensus:<system>` unit through the real gate with validation and
  ambiguity still open (both capping) — a streamed grade can rise, never
  fall. Candidate shape: `schemas.indexing.candidate_evidence`, shared with
  `evidence()` — never fork it. All added `data` on existing kinds; a new
  kind is a version bump.

## The control surface and the priors (WP-1045)

- **One spec, three chairs**: `schemas.indexing.SearchSpecSpec` is the
  agent request's, `ProjectDoc.indexing`'s (the GUI form) and `to_spec()`'s
  — bijection pinned by `tests/test_search_controls.py` +
  `gui/src/lib/controls.test.ts` over the committed corpus; `_spec_notes`
  records every spec field (two chairs, byte-identical notes, asserted);
  vocabularies come from `capabilities()`, never a client literal.
  `shift_allowance_deg` is the declared *window* (its old name was the
  screen's scatter's, which failed the calibration protocol silently, 4.3×
  apart); `search_volume_ceiling` is the one pruning authority (declared
  `max_volume` verbatim, else `VOLUME_ENVELOPE_SLACK ×` Smith's mean line,
  which raw excludes truth below p = 0.71 completeness).
- **A prior steers, never gates** (`priors.py`): its system jumps the
  queue, its metric seeds svd's basin (outside the N_c/N_o gate; the box
  still binds), and the stated cell is checked the engines' own way,
  entering as finder `"prior"` — merged when an engine found the lattice,
  else appended **after** the ranked list, never in the Borda ranking (IIA —
  what makes "a wrong prior changes no rank" structural); absent from
  `engines_run`, so the agreement caveat grades it with no new vocabulary.
  Traps met: `PRIOR_DRIFT_MAX`, `same_lattice`-never-cell-tuples (WP-1045).

## Engines and the FoM panel

Everything the engines share is `engines.py` — one `SearchSpec`, one
`EngineResult` (carrying `CandidateFit`: consensus dedup is a χ² test needing
`cov_af`), the live registry the agent schema quotes, `Budget`, and the
`reflection_ceiling_ok` crash guard before every `generate_reflections` a
search reaches. `search_dichotomy` bounds Q over boxes in A..F (corner-exact
— Q is linear in the metric); its silence is evidence *only when*
`search_complete[system]`. `search_trial_error` assumes base-line indices and
solves the metric exactly — a bad base line poisons it where a wide domain
poisons the other. `search_svd` (WP-1040) alternates assign-nearest with
re-solve until the assignment settles — **no tolerance to search with**,
failing on a bad starting basin; the only *stochastic* engine
(`SearchSpec.seed` is part of its answer, never `hash()` of a name — python
salts per process) and the only one reading observed intensities. All three
rank on the FoM **panel** via `rank_candidates`, never on a member —
supercells index every observed line and lose only on the reversed members.
Seven members: M₂₀, F_N, three coverage fractions, and Oishi-Tomiyasu
(2013)'s `m_rev`/`m_sym` (the reversed direction as a *ratio* where ours is
a windowed fraction — on a doubled axis `m_rev` separates truth from
supercell 64-74× where M₂₀ manages 1.8×). Its `N^cal` is Σ 1/m over
centring-allowed triples, **never rounded**: a complete orbit sums to
exactly 1 (the multiplicity self-check) while a box-cut hexagonal orbit
legitimately contributes a fraction.
**A cap applied above the layer that ranks *is* a ranking** (WP-1046).
`max_candidates` is the **reported** cap, applied once, by consensus; a unit
hands the merge `SearchSpec.engine_pool()` = `ENGINE_POOL_MULTIPLE ×` it, and
consensus scores the *whole* merge (`shortlist=None` — the cheap pre-rank bounds
an engine's unbounded harvest and consensus has none, so tying it to the reported
number was the same defect in a cheaper disguise). Applied lower, Borda's
rank-sum over the pool being ranked made the cap the ranking, and a **longer**
search *lost* set F's truth — rank 1 at 5 s, absent at 30 s. Two numbers because
they buy different things: the pool bounds panel cost, the reported cap bounds
*validation* and is what `estimate_ceiling` prices. `INDEX_CANDIDATES_TRUNCATED`
states what the list left out — a count at the merge, a flag at the pool. **The
known-cell corpus could not have found this**: it is high-symmetry, its truths'
own units harvest single digits, and the cap binds in the low-symmetry ones.

**Corroboration outranks every figure of merit — and it is binary, not a count**
(`engines.corroborated`, WP-1046). The doctrine above applied to the *order* and
not only to the verdict: `grade` floors a candidate below `MIN_AGREEMENT`
finders at `low` before a caveat is read, so a list ranked on the panel alone put
candidates the gate refuses to promote above the one it could. It is **not** an
aggregation artefact and no re-weighting reaches it (WP-1041 stands): the
displacing candidate *wins* the panel on the members — what separates it from the
truth is who found it. **A finder count is not comparable across systems**, and
that is measured, not feared: the engines' reach differs by system, three of them
meet in a cheap orthorhombic domain where only two reach an expensive monoclinic
one, and ranking on the count sent four bethanechol truths from rank 1 to ranks
5/3/9/8 behind orthorhombic cells all three engines found. The one comparable
statement is the gate's own boundary, so `MIN_AGREEMENT` is read by both and the
panel decides within a tier. Inert inside an engine, where `found_by` is empty.

**But the panel ranks; it does not score** (WP-1041) — a margin is comparable within a
member, not across them, so a raw log-sum merely re-weights the panel by each member's
dynamic range: 5 of 6 datasets, exactly Borda's, failing on a different one.
`fom.log_sum_scores` carries the measurement and stays **unwired**. Two things the
panel needs from its caller (WP-1026): the **matching window** is an argument
(`fom_panel(..., q_match=)`) separate from the per-line σ, because coverage members
must ask the same "is this the same line" question the *search* asked while M₂₀ and
F_N floor their discrepancy on what the measurement resolves; and a candidate carrying
a fitted shift is scored on `engines.scored_positions`, the **corrected** lines it
claims, or the panel marks it down for its own correction.

## The search window and the shift

**The search window is a correctness parameter, measured rather than assumed**
(WP-1038, `pairs.py`). A *harmonic reflection pair* (integer multiples:
`m·sin θ_B = sin θ'_B` for any lattice) is one equation in the shift and none in
the cell, so Dong (1999) gives its **magnitude** from the peak list alone;
`ShiftScreen.allowance_deg` is what a window must span. Four measured rules
(stories in the appendix): **the magnitude is knowable with no reference and the
cause is not** (`constant` and `cos_theta` concentrate identically — the screen
may refute `sin_2theta` and never choose between the others); **detection is
concentration against a seeded structureless null** (the published false-pair
rule admits 11-BM NAC at chance, −0.09° where the shift is zero); **a window
wider than the shift manufactures a confident wrong singleton** (at 0.060° SRM
660c returns a cell 293 000 ppm off at `high`), so headroom scales the
amplitude's *standard error*, never the pair scatter; and **an allowance is not
a correction** — it finds lines, only `shift_template` moves the cell.

**The tolerance an engine searches with is not the per-line σ** — the root
CLAUDE.md clause, whose absolute numbers live here: certified corundum's lines
sit a median 0.060° from truth against a median fitted σ of 0.0056° (the 11σ),
`DEFAULT_UNKNOWN_SHIFT_DEG` is 0.05° 2θ (the fallback when the pair screen
declines), and `refine_with_shift` runs after survival because the shift's
*shape* needs reference positions, which a candidate cell supplies.

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
  inverted). Corollary: **a candidate cell is a lattice, not a tuple** — reduce both
  sides, then compare the **centring** and the **dataset's own band** on the *reduced*
  cell (`indexing_gallery.rank_of_lattice`, the one implementation). Each weaker form
  has read a right answer as wrong or a wrong one as right: sorted axes miss another
  setting (WP-1040), no centring reads a P description as its own I truth (NAC), a
  *conventional*-cell band scored bethanechol's rank-1 answer −1 because a monoclinic
  setting is not unique (WP-1026), and `same_lattice` is **not** a band — its 5e-3 is
  componentwise on A..F, so near 90° it is arbitrarily tight (WP-1026) while alone it
  merges FAP's +966 ppm leader with its +258 ppm cross-code cell (WP-1041).
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
  **never round it up**, and **keep the found-but-not-first bucket** (collapsing it
  into right-or-wrong is how the old board named nine datasets under a total of
  eight). It is **generated** by `tests/indexing_gallery.py` — re-measure by running
  the suite; counts live in the v1.0 dossier, never retyped here (WP-1041). And
  **say "high-symmetry" whenever the board is quoted** (WP-1043): nine of ten
  known-cell datasets sit at ≤ 2 free metric parameters — until the corpus moves,
  post-v1, every claim from it is about high-symmetry lattices.
- **An ambiguity partner must be refuted by the lines it needs and the data lack**
  (asymmetric: the partner's extra predictions, never the parent's own absences), or
  every derivative lattice is reported and the gate can never promote. And
  `ambiguity_partners` walks sublattices only, so a *smaller*-volume isospectral
  rival is invisible — tetragonal P (a/√2, a) vs cubic P a.
- **A Niggli-reduced cell is primitive**: `ReducedCell.centring` is provenance about the
  input, never handed to anything that applies a centring. Reduction needs the *relative*
  ε (`NIGGLI_EPS_RELATIVE`) or one lattice splits into two and denies the gate agreement.
- **An assumed precision may never refuse to index** (`from_positions` lists get no
  `MAX_RELATIVE_SIGMA_Q` vote; the shift-allowance half is above).
- **This package is not slow at indexing, it is silent** — DICVOL04 reaches 3770 s
  on hard triclinic patterns and McMaille "hours, if not a night", against our
  0.7–177 s. Buy responsiveness with ordering and reporting, never by shrinking
  the box. **`budget_seconds` is per (engine × system)** — probe and validation on
  top — so the whole-run bound is `total_budget_seconds`, a `Deadline` that *is*
  the cancel token; `estimate_ceiling` is the pre-run arithmetic,
  `INDEX_BUDGET_EXHAUSTED` names the three states (searched/truncated/not reached),
  and a truncated validation reads `not_validated`, never `validation_failed`
  (1037). And **a Monte Carlo indexer must refine each proposal; raw random cells
  do not rank** — WP-1023 ranked corundum's truth 29 053 of 200 001 unrefined,
  where `search_svd`, iterating to a fixed assignment, returns it alone.
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
  `svd.zero_error_column`). Coelho §2.3's column does *not* raise the hit rate: at
  an injected 0.10°, started **at** the truth, one pass lands 3.5 % out where §2.4's
  three land 1e-4 out and report the shift to 1 % (corundum 0 candidates → the truth
  ranked first, nothing regressed). It agrees with the pair screen to **0.003°**
  needing neither references nor pairs — and still may not correct a cell, being the
  `constant` template *by construction*: **a shift measured without an attribution
  sizes windows, and only a declared template moves a cell.**
- **A search is driven by the *strongest* N lines, and "enumerate liberally" is a
  rule this package cannot have** (WP-1039, `engines.search_line_order`). *Which*
  twenty beats *how many* (NAC: 6 of the truth's lines in 2θ order, 18 by intensity
  over a `SEARCH_POOL_MULTIPLE` low-Q pool), and raising N *loses* answers, since
  `indexes_the_search_lines` is an **absolute** budget. Ties fall back to Q, so
  position-only lists are untouched.

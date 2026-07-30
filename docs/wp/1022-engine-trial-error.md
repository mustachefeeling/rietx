# WP-1022 — Engine B: index-heuristic trial and error

Milestone: v1.0 · Status: ⬜ not started
Depends on: 1020

## Goal

A fast, deterministic, seed-free engine that assigns trial Miller indices to a
few low-angle base lines and **solves** for the metric exactly, then checks the
result against every line. Seconds where WP-1021 takes minutes, with a
different failure mode.

## Context

*Sources*: Werner (1964); Werner, Eriksson & Westdahl (1985) — TREOR90; and
the N-TREOR09 improvements of Altomare *et al.* (2000, 2009). **Papers only —
no TREOR or EXPO code may be read or ported.**

- **The method is the linearity used from the other end.** Where WP-1021 bounds
  Q over a box of metrics, this engine *assumes* the hkl of `n` base lines and
  solves `M·X = Q_base` exactly, `n` = the metric DOF (1/2/2/3/4/6). No
  iteration, no tolerance in the solve itself — the tolerance is spent
  afterwards, checking the solution against all lines.

  ```
  for system in cubic … triclinic:
      n = metric_dof(system)                       # WP-1020's adp_basis(Rᵀ)
      for base in combinations(first ~8 usable lines, n):
          for assignment in index_sets[system]:    # small hkl tables, h,k,l ≤ 2..4
              solve M·X = Q_base  exactly (n×n)
              reject: G* not positive definite / axes or volume out of range /
                      reduced cell invalid
              score against ALL usable lines; refine_candidate; keep if
              indexed_fraction ≥ threshold
  ```

- **Three cheap kills remove most of the enumeration** before any scoring:
  positive-definiteness of G*, axis/volume bounds, and Niggli validity. Order
  them cheapest-first; this is what makes a combinatorial search tractable.
- **Its failure mode is a bad base line**, and it is not shared with WP-1021.
  One impurity among the base lines poisons the exact solve — so iterate base
  sets (leave-k-out is implicit in `combinations`) and *require* the solution to
  survive the full-list check. The 2004 benchmark paper's TREOR rows are mostly
  this failure.
- **Its other failure mode is a dominant zone**: a large axis makes the base
  lines carry a large index along it, outside the index table. ~~`INDEX_DOMINANT_ZONE`
  from WP-1019 is the pre-warning~~ — **there is no such pre-warning: 1019
  measured that a dominant zone is not detectable from a census (see Inherited),
  so this engine has to raise the condition itself**, from the fact that its own
  base sets keep needing indices outside the table. That is a better signal
  anyway: it is the engine's own experience rather than a proxy statistic.
- **Prior art in miniature.** `studies/guillemot/index_hl2.py` is this engine
  restricted to two-parameter metrics: `candidates()` takes every pair of
  observed Q plus a pair of trial (M, l) labels and solves the 2×2 exactly.
  **Read it before starting** — it confirms the exact-solve design works, and
  its measured limits are this WP's design constraints. It is pinned at the
  annotated tag `guillemot-study` and **deliberately not merged into `main`**;
  read it in place with

  ```sh
  git show guillemot-study:studies/guillemot/index_hl2.py
  ```

  Two limits in particular:
  - its tolerance is `|ΔQ| < 0.004·Q`, an arbitrary relative constant; this WP
    replaces it with the per-line `σ_eff` from WP-1018/1019;
  - **its coverage score cannot distinguish "multiphase" from "lower symmetry
    than the engine reaches"** — audit check C measured 47-60 % for
    single-phase orthorhombic/monoclinic patterns against a two-parameter
    metric, 82-100 % for genuinely tetragonal/hexagonal ones, and 69 % for a
    real mixture. A claim built on that ambiguity was **withdrawn**. Hence the
    `systems_searched` reporting in WP-1024: a low score under a restricted
    search is never evidence of a multiphase sample.
- **Reflection-count ceiling before `generate_reflections`** — same crash guard
  as WP-1021 (measured 1.6 PiB request, audit check B).

### Inherited

From **WP-1020**: `metric_dof` via `adp_basis(Rᵀ)` sets `n` per system — do not
hardcode 1/2/2/3/4/6; `refine_candidate`; the FoM panel; the χ² cell-equality
for deduping this engine's own output.

From **WP-1019**: `σ_eff` and the shift template — but note the shift screen is
*conditional* on reference positions, so at search time `shift.source` is
normally `"unavailable"`; see the correction below.

**Correction from WP-1019 (2026-07-30): `INDEX_DOMINANT_ZONE` does not exist,
and detecting a dominant zone or row is owed to *this* WP.** 1019's plan said
both are "detectable in Q-space before any search"; measured, they are not.
Neither is a summary statistic of a peak list — a dominant zone is the statement
that the low-angle lines satisfy a **two-dimensional** quadratic form, and a
dominant row is an arithmetic progression k²B among the low Q values. Each is a
search, which is why it lands here. The census that was tried and removed (Ito's
most-repeated Q difference) scored dominant-zone cells (c = 3.1, 2.7 Å) at +0.9σ
and +0.8σ against a permutation null while scoring a *general* monoclinic cell at
+3.3σ; against a uniform null a **cubic** list scores +15.6σ, because
Q = A(h²+k²+l²) makes every difference a multiple of A. Two lessons for any
statistic this engine invents: use a **permutation** null (same spacing multiset,
order destroyed) rather than a uniform one, since the uniform null would have
"confirmed" the useless statistic; and check the negative case (a general cell)
before believing the positive one. A test in `tests/test_indexing_quality.py`
asserts the code's absence so it cannot creep back as an unmeasured claim.

From **WP-1020** (landed 2026-07-30) — the shared surface, and five things about
it that are not obvious from the names:

- **`refine_candidate(q, q_esd, hkl, *, system=...)` without a shift template is
  one `lstsq` on an (N, m) system** — no iteration, no scipy call, because it is
  this engine's inner loop. With `shift_template=` it becomes Gauss-Newton (≤ 8
  steps). **Do not put a shift column inside the search loop**: fit the shift
  after a candidate survives, which is also the order WP-1019's screen needs
  (it is conditional on reference positions, and a candidate is what supplies
  them).
- **`metric_basis(system)` is the search space.** Its row count is the box
  dimension — 1 cubic … 6 triclinic — and it is derived from the operators, so it
  is right in any setting. Import it; do not hardcode 1/2/2/2/3/4/6. It takes the
  rotations **untransposed**, and getting that wrong is invisible in the dimension
  (see 1020's handover: the transposed call returns the *direct* metric's
  invariants, same dimension in every system, wrong subspace for hexagonal and
  trigonal).
- **`cell_from_af` raises on a non-positive-definite metric** rather than
  returning NaNs. A search that steps outside the cone will hit this, so catch
  `ValueError` at the point where a trial metric is turned into a cell rather than
  letting it abort a sweep.
- **`reduce.same_lattice(af_a, af_b, cov_a=…, cov_b=…)` is the dedup**, returning
  `(verdict, χ²)`; it Niggli-reduces both first, so a setting change is *equality*
  and never an ambiguity. Feed it `CandidateFit.cov_af`, which is already the
  delta-method covariance; the relative fallback (χ² = NaN) means one of the
  covariances was missing.
- **`fom_panel(...)` returns the whole panel and `borda_scores` ranks it.** Rank on
  the panel, never on a member: `indexed_fraction` alone prefers a large cell, and
  1020's test reproduces that failure on synthetic data (an impostor ties or beats
  the truth on the forward direction and loses 5× on `predicted_seen_fraction`).
  Two figures' means are **floored at the measured precision** — a candidate that
  fits within fp noise would otherwise score 0 or ∞.

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

**Specific to this WP (WP-1021, 2026-07-30): the monoclinic case is yours.**
Engine A recovers monoclinic only with a *declared* axis range (84 s over
d ∈ [6, 18] Å; it does not finish over d ∈ [2, 18] Å in 90 s, and says so). The
cost is the grid — (range/0.4)³ × angle slabs — so it is a domain cost, not a
tolerance one, and no amount of tuning inside engine A changes it. **This engine's
exact n×n solve does not pay it at all**, which is the concrete form of "three
engines with different failure modes": measure that and record it, because it is
the evidence that the design's premise holds. Two supporting facts: the canonical
axis ordering engine A uses (derived in `dichotomy.axis_swaps` from which
permutations preserve the metric subspace — orthorhombic and triclinic admit all
three adjacent exchanges, monoclinic only a↔c) applies equally to a trial-and-error
base set, and `assert_same_lattice` in `tests/test_indexing_engines.py` already
compares cells up to a setting change, which you will need since the monoclinic
truth legitimately comes back as its a↔c partner.

## Non-goals

- No consensus or confidence gate (WP-1024) — this WP returns a ranked list.
- No zero-shift *search* inside the engine: the shift model is fitted once in
  WP-1019 and carried, not re-searched per base set.
- The index tables stop at h,k,l ≤ 4; larger indices are a dominant-zone case
  reported rather than brute-forced.

## Tasks

- [ ] `indexing/trial_error.py`: per-system index tables, base-set enumeration,
      the exact n×n solve, the three cheap kills in cost order.
- [ ] Full-list scoring + `refine_candidate`; dedup via WP-1020's χ² equality.
- [ ] Dominant-zone abstention **raised here** (1019 has no such code — see
      Inherited), from base sets repeatedly needing out-of-table indices;
      predicted-reflection ceiling; time budget and `search_complete`.
- [ ] Registry entry (so WP-1024's agent schema quotes it live).
- [ ] `tests/test_indexing_engines.py::trial_error`: recover known cells in
      every system from synthetic lists; recover with 1 impurity among the
      first 8 lines (the base-set robustness test); **determinism** — same peak
      list twice gives bit-identical reduced cells, and the candidate *set* is
      invariant to peak-list ordering.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_indexing_engines.py -k trial_error -q
.venv/bin/python -m ruff check src tests examples
```

Criterion: cubic through monoclinic recovered from synthetic lists; the
engine is deterministic and order-invariant; wall clock per system recorded in
the handover log. Triclinic is budgeted, not claimed.

## References

- Werner, P.-E. (1964). *Z. Kristallogr.* **120**, 375-387.
- Werner, P.-E., Eriksson, L. & Westdahl, M. (1985). *J. Appl. Cryst.* **18**,
  367-370.
- Altomare, A. *et al.* (2000). *J. Appl. Cryst.* **33**, 1180-1186;
  (2009) **42**, 768-775 — N-TREOR / N-TREOR09.
- Altomare *et al.* (2019), IT Vol. H ch. 3.4 §3.4.3.1.3, eq. (3.4.8).
- Prior art at the tag `guillemot-study` (**not merged into `main`**; the
  measured numbers are restated in Context, so this is corroboration):

  ```sh
  git show guillemot-study:studies/guillemot/index_hl2.py
  git show guillemot-study:studies/guillemot/out/audit_full.txt   # §C
  ```

## Handover log

- **2026-07-29** — created from the indexing plan.

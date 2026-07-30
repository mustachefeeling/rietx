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

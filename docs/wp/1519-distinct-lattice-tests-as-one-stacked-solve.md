# WP-1519 — the distinct-lattice χ² tests run as one stacked solve

Milestone: unscheduled · Status: 🔄 2026-09-28 — claimed by @yue-here
Track: A long run is not one fit
Depends on: — (1509 fenced this; 1518 soft: batch the test it settles, not the one it replaces)
Priority: P3 2026-09-28 — cost only: since 1509 no acceptance search is cut at 300 s, and this is ~45 s of corundum's 236 s tetragonal unit; 1518 closed, so the test it batches is settled

## Goal

A dedup pass over many *distinct* lattices spends its χ² tests in one stacked
pseudo-inverse per candidate rather than one LAPACK call per pair, and every
group, and so every finished search, comes out bit-identical. Where stacking is
not proven identical on a platform, the pass keeps its per-pair loop there.

## Context

**What is left after WP-1509.** 1509 made dedup answer each copy once and ask
the volume gate only inside the band. Copies were most of a raw harvest
(bethanechol F's cut unit: 7000 raw, 761 distinct, 18.8 → 2.6 s). A harvest of
genuinely distinct lattices is not helped by either change. Corundum's
tetragonal unit (5037 candidates, 4942 lattices) still spends ~45 s on
**567 535 χ² tests** between distinct lattices, a 6×6 `pinv` each.
Dedup is 24 % of that unit's 236.5 s after 1509 (`[dev]`, Linux x86-64,
4 cores, py3.12, numpy 2.5.3 on OpenBLAS 0.3.34, one BLAS thread). The same
pass runs in consensus over every engine's pool and inside svd and trial_error
at their own `DEDUP_EVERY`.

**The loop** (`engines._dedup_groups`). For each candidate, in `(-n_indexed,
chi2_red)` order, walk the groups in the volume band in creation order, and
join the **first** whose `reduce.equal_reduced` verdict is true; a miss opens a
group. `equal_reduced` computes Δᵀ·`np.linalg.pinv(Σ, hermitian=True)`·Δ with
Σ = cov_a + cov_b, one call per pair, and the pass caches each (distinct
candidate, group) verdict.

**Stacking keeps the semantics if each χ² is the same double.** Compute every
band group's χ² for one candidate in one `pinv` over a (k, 6, 6) stack, then
take the first passing group in creation order. The extra tests past the first
match are wasted work, not changed answers. Whether it is the same double is a
**platform claim**. `pinv(hermitian=True)` goes through numpy's `svd(...,
hermitian=True)`, which calls `eigh`, and a stack goes through the gufunc loop.
That loop should call the same LAPACK routine once per matrix, but WP-1509
learnt not to assume this: numpy sends a (1, 6) product to `dot` rather than
`gemv`, and 1378 of 4054 single-row products then differed. So measure, the way
`engines.row_local_product` does. Probe once a process on a witness stack, and
use the stacked form only where it reproduces the per-matrix one bit for bit.

**The same platform question is still open for 1509's own probe.** Its
`test_a_subset_product_is_the_whole_products_rows_where_the_probe_says_so`
skips where `row_local_product()` says the BLAS is not row-local. Whether it
skips on the macOS and Windows nightly jobs was not read at close. Read both
on the same logs this WP measures on.

**An exact prefilter is the other route, and it is harder than it looks.**
χ² ≥ |Δ|²/λ_max(Σ) would reject most pairs without a solve, but `pinv`
truncates eigenvalues under its cutoff, so the part of Δ in Σ's truncated
directions contributes nothing. The bound holds only for Δ projected onto the
kept subspace, which needs the eigendecomposition it was meant to avoid.
WP-1518 found that this truncation hides real differences today. Try the
prefilter only after 1518, and only with an argument that survives truncation.

**The bar is WP-1509's.** Finished units replayed to their digests, never a
green suite. Brucite hexagonal `c82630be`, trigonal `719d4e0b`; corundum
hexagonal `6a060c83`, trigonal `e8466d7f`, tetragonal `f610fbdc`; synthetic
monoclinic `fc4d2b0b`. Each unit's inputs are captured by swapping
`engines._REGISTRY` for recorders and running `index_pattern` once, then
replayed to completion. The digest is sha256 of `np.array([[*cell, n_indexed]
…], float64).tobytes()`. 1509's scripts were session scratch, so rebuild the
harness first and reproduce the six digests on the unchanged tree. If WP-1518
has landed, its handover names the digests it moved, and those are the ones
to hold.

**What WP-1518 changed underneath** (folded from Inherited, 2026-09-28).
The test being batched now takes **reduced-frame** covariances:
`engines._dedup_groups` carries each candidate's `fit.cov_af` through
`reduce.reduction`'s map (`reduce.reduced_covariance`) and keeps the carried
covariance beside the reduced vector, in `prepared` and in `kept`. Stack
those, never `fit.cov_af`. The map is `None` wherever the reduction kept the
setting, so a stack must accept both. A zero-variance component (a
structurally fixed D, E or F, in whatever slot the reduction moved it to) is
still truncated by `pinv`, so the prefilter above still needs its argument.
**A digest belongs to a platform**: it hashes the cells' bits, and on macOS
arm64 not one of 1509's six Linux digests reproduced on the unchanged path.
There 1518 moved five of the six units and held corundum tetragonal
(`8a5fd6cd`); on any platform, take the post-1518 digests from the current
tree before holding anything. The harness is now `tests/unit_replay.py`.

## Non-goals

The frame the test reads its covariance in (WP-1518). `CELL_EQUALITY_CHI2`,
`DEDUP_VOLUME_RTOL`, `DEDUP_EVERY`. The per-assignment refinement (WP-1520).
A compiled kernel: `pinv` is LAPACK, the tier's bit-identity bar does not reach
it (WP-1508 § Context).

## Tasks

- [x] Rebuild the replay harness; reproduce the six digests; time corundum
      tetragonal's dedup (first pass and consensus) at one BLAS thread.
- [ ] Measure stacked against per-matrix `pinv(hermitian=True)` on 6×6 stacks
      of real dedup Σ (captured from the tetragonal unit): the count that
      differ, on Linux here, and on macOS and Windows through the nightly or a
      probe the suite runs. Read `test_a_subset_product_…`'s skip state on
      the same logs. *Linux done 2026-09-29; macOS and Windows are read off
      the first nightly after merge, whose legs now print both probes.*
- [x] If stacking reproduces the per-matrix χ²: a probe once a process
      (`row_local_product`'s pattern), the stacked walk where it says yes, the
      per-pair loop elsewhere. A test holding the two equal on a harvest that
      has a first match in the middle of the band. Otherwise close 🛑 with the
      counts.
- [ ] Re-time the unit; `tests/test_acceptance_indexing.py` once on the final
      tree.
- [ ] Skill: none expected (no call an agent makes changes); say so at close.

## Acceptance

Every finished unit's digest unchanged; the tetragonal unit's dedup re-timed.

```sh
.venv/bin/python -m pytest tests/test_indexing_engines.py tests/test_indexing_consensus.py -n auto --dist loadgroup
.venv/bin/python -m pytest tests/test_acceptance_indexing.py -n auto --dist loadgroup
.venv/bin/python -m ruff check src tests examples
```

## References

WP-1509 (the fence, the caches, the harness, the row-locality probe);
WP-1508 (the tier's reach); WP-1518 (the test being batched).

## Handover log

- **2026-09-29 (in progress; `/wp-handover` rewrites this)** — `[dev]`, Linux
  x86-64, 4 cores, py3.12, numpy 2.5.3 on OpenBLAS 0.3.34, one BLAS thread.
  Harness committed as `tests/unit_replay.py`. On the pre-1518 tree
  (09c9486) it reproduces all six of 1509's digests; 1509's synthetic
  monoclinic `fc4d2b0b` is the engine called directly with `spec_for`, not
  a unit captured through `index_pattern` (`50f61135` there). Post-1518
  digests on this platform, held by the stacked code: brucite hexagonal
  `56677409`, trigonal `816c0422`; corundum hexagonal `605772e8`, trigonal
  `aa4fd3f9`, tetragonal `f610fbdc` (unmoved by 1518, as on macOS);
  synthetic monoclinic `ac68ad82` direct, `c6acb64f` through
  `index_pattern`. Tetragonal unit: 573 605 χ² tests in 4970 candidate runs
  (median 91 a candidate, 71 ending in a match, at band positions 1-336).
  Stacked per candidate, **0 of 573 605** `pinv` differ from per-matrix and
  0 χ² differ; `pinv` alone 24.7 → 2.4 s. The whole-array matmul chain was
  also exact here, einsum was not (291 782 differ); the code keeps each
  pair's own product. Final code (the stack filled lazily from the walk):
  every digest above held, and every corundum svd and trial_error unit is
  identical to `main`'s (4 systems each). Dedup times so far were under a
  parallel load (not quotable; the alone re-time is running). macOS and
  Windows: nightly legs now print both probes; not yet read.
- **2026-09-28** — filed from WP-1509's *Fenced* and *Next* (item 3), with
  the platform check its handover left for the nightly logs.

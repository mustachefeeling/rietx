# WP-1519 — the distinct-lattice χ² tests run as one stacked solve

Milestone: unscheduled · Status: 🔄 2026-09-29 — stacked dedup landed (#519); macOS and Windows probe answers await the first nightly after merge
Track: A long run is not one fit
Depends on: — (1509 fenced this; 1518 soft: batch the test it settles, not the one it replaces)
Priority: P3 2026-09-29 — the code landed; what is left is reading two nightly lines after merge, minutes of work

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
- [x] Re-time the unit; `tests/test_acceptance_indexing.py` once on the final
      tree.
- [x] Skill: none expected (no call an agent makes changes); say so at close.
      *None: no call an agent makes changed (2026-09-29).*

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

- **2026-09-29** — Dedup now asks its χ² tests between distinct lattices a
  stack at a time, one pseudo-inverse per stack instead of one per pair, and
  the groups are provably the ones it built before. A once-a-process probe
  switches the stack on only where every stacked χ² equals the pair's own, bit
  for bit. On Linux x86-64 all 573 605 real tests of corundum's tetragonal unit
  came back identical, that unit's dedup fell from ~29 s to ~7 s alone, and
  every replayed unit's digest held. The replay harness three WPs had rebuilt
  in scratch is now committed. On the tree before WP-1518 it reproduces all
  six of 1509's digests, which is the check that it measures what they
  measured. Still open: whether macOS and Windows keep the stacked path. The
  nightly legs now print both indexing probes, and no one has read them yet.

  *Done.* `reduce.equal_reduced_many` (Δ, Σ and the final product per pair
  exactly as `equal_reduced`, only `pinv` over the stack) and
  `reduce.stacked_pinv_exact`. The probe runs 11 stacks of 1-1024 (the walk's
  own sizes among them) of sums of two rank-1-6 covariances, whose near-zero
  eigenvalues sit at `pinv`'s cutoff, and stops at a first mismatch; ~95 ms
  cold, once a process, True here. `engines._dedup_groups`: where the probe says yes, the
  walk fills its verdict cache from the group it is at (`_ask_stacked`,
  stacks of `DEDUP_STACK_FIRST` = 16, then ×4), reads it back in creation
  order and stops at the first match as before. A group without a covariance
  and anything after a stack raises go one pair at a time. The gate is
  `_dedup_admits`, shared by walk and stack. `tests/unit_replay.py`
  (capture/replay/pool, `--count` counts stacked tests too) + its test. The
  nightly's three environment steps print `row_local_product` and
  `stacked_pinv_exact`: the suite runs at `-q` without `-rs`, so no log could
  say whether 1509's probe skips on macOS or Windows. Indexing CLAUDE.md: one
  clause on the exact-restriction rule (cap 321 → 323). Tests: the stacked χ²
  equals the pair's own on covariances built from each system's metric basis
  and carried through the reduction (skips where the probe says no). And the
  stacked groups equal the per-pair and plain ones on a band of 81 lattices,
  with a covariance-less group first and probes matching at position 2,
  mid-band (second stack, answering past the match), nowhere, and by copy,
  plus a stack that raises. Both mutations checked red: verdicts cached
  against the wrong groups; a first stack swallowing the band (vacuity).

  *Measured* (`[dev]`, Linux x86-64, 4 cores, py3.12, numpy 2.5.3 on OpenBLAS
  0.3.34, one BLAS thread):
  - Harness validation, tree 09c9486 (before 1518): brucite hexagonal
    `c82630be`, trigonal `719d4e0b`; corundum hexagonal `6a060c83`, trigonal
    `e8466d7f`, tetragonal `f610fbdc`; synthetic monoclinic `fc4d2b0b`, all
    six of 1509's.
  - Post-1518 digests to hold on this platform, identical on `main` (ebdc2ab)
    and the final tree: brucite hexagonal `56677409`, trigonal `816c0422`;
    corundum hexagonal `605772e8`, trigonal `aa4fd3f9`, tetragonal `f610fbdc`;
    synthetic monoclinic `ac68ad82` (`c6acb64f` through `index_pattern`).
    Corundum's svd and trial_error units, four systems each, identical to
    `main`'s. The consensus pool (308 → 296 groups) digests `c3dd2095` on
    both trees.
  - Tetragonal unit alone, `main` then final, interleaved, four runs each
    side over two sittings (the second after the review's fixes, `main`'s
    runner then confirmed at one BLAS thread): wall 160.5-164.6 →
    140.1-142.8 s; dedup 28.4-29.7 → 6.51-7.38 s. χ² tests
    573 605 → 575 112, so 1 507 (0.26 %) are asked past a first match and
    wasted. The consensus pool's dedup is 0.05-0.07 s either way (687 → 1 147
    tests). Engines hand it their ranked output, not the raw harvest.
  - Every Σ and Δ of that unit captured: 573 605 tests in 4970 candidate runs
    (median 91 a candidate). 71 runs end in a match, at band positions 1-336
    (median 35). Stacked per candidate: **0** `pinv` differ from the
    per-matrix ones, and 0 χ² differ with each pair's product on a row view.
    The whole-array matmul chain also matched, einsum did not (291 782
    differ). `pinv` alone 24.7 → 2.4 s.
  - Acceptance (`tests/test_acceptance_indexing.py`, final tree, alone): 44
    passed in 18:02. Engines + consensus + harness files: 123 passed.
  - Fast selection, final tree (the same counts before the review's fixes):
    6703 passed, 163 skipped, 1 failed (6867), 20:33. The failure is
    `test_telemetry`'s unwritable-directory case, which `chmod`s a directory
    0o500. This container runs as root, and root writes anyway. The diff
    touches no telemetry. +3 tests, all passing. There is no `main` count on
    this machine, so CI's fast legs are the comparison.
    `tests.added_test_times` on that run (`junit_duration_report=total`, one
    run under the suite's load): 3.48 s the harness test, 0.68 s and 0.48 s
    the two dedup tests, none in the slow tail.
  - Full selection not run. The only slow suite the change can move is the
    indexing acceptance, which ran above.

  *Gotchas.*
  - 1509's synthetic monoclinic digest is the engine called **directly**
    with `spec_for("monoclinic")`, no `quality`. Through `index_pattern` the
    engine gets the workflow's quality report and a different harvest (10
    candidates against 14 before 1518). The harness keeps both
    (`synthmono`, `synthmono_ip`).
  - A first draft stacked every uncached band group before the walk. That
    wastes a stack per copy in a copy-heavy harvest, because the walk would
    have stopped at a cached match first. So the stack is filled from inside
    the walk.
  - This environment's worktree guard refuses a python command beside a
    `PYTHONPATH=` or a shell variable. To run another tree's `rietx`, use a
    runner script that inserts its `src` into `sys.path` and `runpy`s
    `tests.unit_replay`.
  - Inherited pruned on arrival: both of 1518's entries still held (reduced-
    frame covariances; a digest belongs to a platform) and went into Context.
  - Skill: none, no call an agent makes changed.
  - `/code-review high --fix` found 10, fixed 9 (one commit). The probe now
    covers the walk's stack sizes (16, 256, 1024) and stops at a first
    mismatch. An empty batch answers `[]`. The walk passes an `islice`, not a
    copy of the band. The harness sets its BLAS threads only when run (a test
    importing it no longer leaks one thread into a worker's subprocesses). It
    counts a stack once answered and pools engines in registry order. The cap
    raise has its rationale, and a duplicate import went. Declined: folding
    the nightly's probe line (now in three legs) into one place, which needs
    a YAML anchor or a shared script, a CI restructure beyond this diff;
    pushed to WP-1506's Inherited.
    Every digest re-held on the post-review code.

  *Next.* (1) After merge, read the first nightly's "Record the environment"
  step on the macOS and Windows legs (and Linux `full`): the line
  `row_local_product … stacked_pinv_exact …`. (2) Record both answers in
  task 2 and close ✅, whatever they say. A False means that platform runs the
  per-pair path, slower but never different, which is the design working. A
  new WP only if that platform's dedup time matters to someone. (3) The
  exact prefilter in Context stays unbuilt: the 6.5-7.4 s left is ~5 % of
  the unit.
- **2026-09-28** — filed from WP-1509's *Fenced* and *Next* (item 3), with
  the platform check its handover left for the nightly logs.

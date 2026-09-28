# WP-1508 — compiled dichotomy spike (gated: build only if the box traversal is the unit's cost)

Milestone: unscheduled · Status: ✅ 2026-09-28 — the traversal compiled, bit-identical (synthetic
monoclinic ~20×); every real pattern measured is bound by its leaves instead (2-D 3-8 %, bethanechol's
cut sets 13 % further), which are WP-1509's
Track: A long run is not one fit
Depends on: — (1115 built the tier; 1030 measured the box counts; 1449 measured the cut)

## Goal

**Done** (2026-09-28): the gate read split, the traversal is compiled and
bit-identical, and the searches the budget cuts are cut by their leaves, not their
traversal — § Gate reading and the handover log say which is which.

Answer "would a compiled kernel improve indexing performance?" with a profile rather
than a cost model, and — **only if the profile says the box traversal is where a
dichotomy unit spends its time** — move that traversal onto the compiled tier,
bit-identically, so the searches the 300 s budget cuts today finish inside it.

## Context

**The question came from the maintainer (2026-09-27), and the pre-profile answer is
"yes for one engine, no elsewhere".** The research behind that answer is below; the
rule it must still pass is `indexing/CLAUDE.md`'s *profile an engine before ranking
what to fix in it* — WP-1030's reasoned ranking came out nearly inverted. **No
function-level profile of indexing exists in the repo**, and every engine timing
before 1446/1449 predates the compiled tier (2026-08-22).

**Why it matters: the clock binds answers, not just patience.**

- Nightly `full` job, 2026-09-27 (Linux, `[dev,jax]`, `-n auto`): the slowest items
  of the whole suite are indexing acceptance fixtures — 1349, 1246, 1121, 871, 768,
  708, 597, 584 s setup — plus `test_trial_error_recovers_a_monoclinic_cell` 512 s
  and `test_dichotomy_recovers_a_monoclinic_cell` 411 s (call). Job 1:23:50 against
  a 150-minute limit.
- `REAL_DATA_BUDGET_SECONDS = 300` still binds (WP-1449): on 2026-09-26 six real-data
  searches came back cut on the nightly. Brucite's **two dichotomy units** take
  139–232 s (Mac arm64); finished on Linux x86-64 4-core, brucite 710 s (slowest unit
  343 s) and corundum 1408 s (696 s). A cut search's *order* is a reading of machine
  load, so every order-reading row now calls `_skip_unless_finished`.
- `quick` (120 s ceiling) cuts trailing low-symmetry systems; bethanechol's default
  mode reaches orthorhombic inside its budget and not monoclinic (v1.0 record).

**Why dichotomy's box traversal is the numba-shaped part**
(`src/rietx/indexing/dichotomy.py`):

- Phase 2 of `_search_one` is a Python LIFO stack holding 97.6 % of the boxes
  (WP-1030, bethanechol monoclinic); units run 10⁵–10⁶+ boxes at a measured
  ~52 µs/box, "20 µs once the set collapses" (`_test_box`'s comment).
- Per box, `_test_box` + `_push_children` make ~70–80 numpy calls on ~20 lines ×
  ~15–20 surviving rows × ≤ 6 metric dimensions: `_q_bounds`, `_af_interval`,
  `_det_interval` (scalar `np.sqrt`), a lines × rows `hit` matrix and its
  reductions, `_assignment_possible` (`np.unique` of an argmax). The comment above
  `hit` already records the mechanism: a per-line loop with early exit lost to the
  vectorised form **only because of numpy's call overhead** — the thing a compiled
  loop does not pay.
- The arithmetic is `+ − × ÷`, comparisons, min/max and `sqrt` (correctly rounded):
  **no libm, no LAPACK**. So the tier's strictest bar — **bit-identity** — is
  reachable: same boxes, same order, same leaves, same candidates on any *finished*
  search. A *cut* search stops at a different box, and that is already machine load.
- Estimate, **not a measurement**: a per-box kernel called from the Python loop
  ≈ 5×; the whole traversal in-kernel ≈ 20–50× on collapsed boxes, much less on
  phase 1's wide boxes (thousands of rows, already vectorised).

**Where a kernel does not pay** — fences, each with its reason:

- `search_svd`: `lstsq`/`eigvalsh`/`inv`/`arcsin`/`argsort` per iteration, and
  numba's `argsort` breaks Q-tie order, which decides the merge and the convergence
  key → not bit-identical, moderate gain.
- `search_trial_error`: batched LAPACK solve + per-solution `_score`
  (`lstsq`/`eigvalsh`/`pinv`); not bit-identical; which half dominates is
  unmeasured — profiled here, not built.
- The FoM panel (~1 ms/candidate: BLAS, `rankdata`), dedup/Niggli/Bravais (gemmi,
  spglib), peak picking (scipy TRF): foreign-library bound.
- Le Bail validation already runs on the compiled tier (`Refinement.fit` →
  `compile_model`).
- The ambiguity enumeration (once 45 s of a 105 s corundum run, WP-1037) and
  `rank_candidates` recomputing panels are caching / per-axis-bound numpy fixes.

**The compiled tier's rules** (root CLAUDE.md, `model/compiled.py`), which a new
kernel inherits: mandatory, exercised numpy fallback (soft import; entry points
decline, never raise; `RIETX_COMPILED=0` / `compiled.set_enabled`); serial
`njit(cache=True, nogil=True, fastmath=False)`, never `prange`; an equivalence bar
per kernel, stated and asserted; **one path per process**. `model/_kernels_numba.build()`
is paid by every refinement process (~0.28 s cold), so indexing kernels must not
join it — they build lazily on first dichotomy use.

## Gate reading (2026-09-27) — split by the search's dimension

**The gate reads open for a 4-D search and shut for a 2-D one, so the kernel is
built for the regime it serves and the rows the budget cuts get a different fix.**
Measured by replaying each unit exactly as `index_pattern` hands it to the engine
(inputs captured by stubbing the registry), serial, to completion, under a 50 Hz
`py-spy` sample; `[dev]` venv, Linux x86-64, 4 cores, py3.12, numba 0.67.0, numpy
2.5.3, nothing else running. Shares are of the unit's samples.

| unit | wall | boxes | rows/box | box traversal | leaves (`_accept` / centred replay) |
|---|---|---|---|---|---|
| brucite hexagonal | 241 s | 75 475 | 2074 | 12 % | 85 % (50 / 35) |
| brucite trigonal | 275 s | 75 475 | 2074 | 10 % | 87 % (46 / 41) |
| corundum hexagonal | 204 s | 59 886 | 1983 | 11 % | 85 % (56 / 28) |
| corundum trigonal | 221 s | 59 886 | 1983 | 10 % | 87 % (51 / 36) |
| corundum tetragonal | 555 s | 103 255 | 492 | 4 % | 82 % (50 / 32), + 13 % ranking and dedup |
| synthetic monoclinic | 206 s | 1 309 957 | 107 | **94 %** | 0.6 % |

- **The cost model this WP opened with was wrong for the rows it was written
  about** — the third time for this engine (WP-1030's ranking, and `_test_box`'s own
  "20 µs once the set collapses"). On a 2-parameter metric the box set never
  collapses: ~2000 rows survive to every box, the traversal is ~3 ms a box of
  already-vectorised numpy, and ~900 leaves each pay the expensive part.
- **Where a 2-D unit's time goes is the leaves, and neither leaf cost is
  dispatch.** `_accept` is `assign_lines` over the whole trial set (the `dm @ af`
  gemv and the in-window mask over up to `MAX_TRIAL_HKL` rows, per anneal pass, per
  centring, per leaf) plus `refine_candidate`'s LAPACK. The centred replay re-tests
  the centring's *entire* search set — ~2000 rows — at every leaf, where only the
  leaf's own survivors can reach a line (every prune is monotone, so a row that
  reaches no line over an ancestor reaches none here). That second one has an exact
  numpy fix and is filed as its own WP, not built here (the maintainer's call).
- **Where a 4-D unit's time goes is the traversal, and it is dispatch.** 157 µs a
  box at 107 rows: `_q_bounds` 26 %, `_det_interval`'s scalar interval arithmetic
  11 %, `_assignment_possible` 7 %, `_af_interval` 7 %, and the loop body 8 %. This
  is the regime `quick` never reaches today (bethanechol's default mode stops at
  orthorhombic) and the one `test_dichotomy_recovers_a_monoclinic_cell` spends
  411 s in on the nightly.
- **Pinned for bit-identity**: numpy 2.5.3's `.sum(axis=1)` over ≤ 6 columns is
  plain left-to-right addition at every row count tried (1-200 003), probed with
  `[1e16, 1, 1]`; a sequential kernel loop reproduces it.

## Non-goals

A kernel for svd or trial_error (not bit-identical; profiled, not built). Raising or
lowering `REAL_DATA_BUDGET_SECONDS`. The ambiguity-enumeration and panel-caching
numpy fixes. Any change to what a finished search reports.

## Tasks

- [x] **Profile gate** — read **split** (§ Gate reading): open for the 4-D traversal,
      shut for the 2-D rows, whose leaves go to a follow-on WP.
      Current tree, numba installed, serial, machine checked idle.
      Finished (large-budget) dichotomy units on brucite and corundum — the rows the
      budget cuts — and the synthetic monoclinic row of `tests/test_indexing_engines.py`,
      under a 50 Hz `py-spy` sample (`cProfile` would weight the many small calls it
      was measuring). Split each unit into phase 1 grid / phase 2 box work
      (`_test_box`, `_push_children`) / leaves (`_box_key`, `_accept`) / other; record
      boxes, rows and µs per box. Same profile for trial_error's monoclinic unit,
      recorded only: 270.5 s, `_score` 82 %, the batched solve 13 % — leaf-shaped
      again, and carried to WP-1509. **Gate:** build if phase-2 box work is ≥ ~60 % of the slowest
      dichotomy units; otherwise close 🛑 with the profile as the outcome.
- [x] **Per-box kernel**, bit-identical: `_kernels_numba._box_test` (`_test_box`,
      with `_push_children`'s child test beside it as `_child_key`), exposed as
      `test_rows` for the grid pass and the tests, dispatched from `dichotomy.py`
      behind `compiled.enabled()`, the numpy path kept as oracle and fallback.
      **Not measured on its own** — the traversal below was built directly on it,
      which departs from the plan's step order; the gate's own numbers (the loop
      body alone is 8 % at 157 µs a box) said the python loop would cap it.
- [x] **In-kernel traversal**: `_kernels_numba.traverse`, the stack as flat arrays
      and the survivors as `(start, length)` into one index pool used as a stack;
      it hands back at a full leaf buffer, a row-test chunk or a pool that must
      grow, so python keeps `Budget.expired()`, `_box_key` and `_accept`. Visit
      order equal to the numpy loop's, asserted leaf by leaf. Synthetic monoclinic
      194.8 → 17.7 s with the profile queue on another core (idle re-time below).
- [x] Tests: `tests/test_indexing_kernels.py` — one box against `_test_box` on the
      bit at every metric dimension (1-4 and 6), 400 boxes each with both verdicts
      asserted to occur; whole searches with the switch on and off on the five fast
      synthetic cases (counts, candidates *and* the leaf sequence); every handback
      forced on every box; an expired budget; the switch; and numpy's left-to-right
      reduction pinned by name. Each failure was made once on purpose: re-associating
      one Q-bound sum fails the width bits; flipping the children's tie rule passed
      every counts-and-candidates assertion and is caught only by the leaf sequence,
      which is why that assertion exists.
- [x] Before/after timings of the gate's units — replayed from the captured inputs,
      serial, idle machine, same venv and platform as § Gate reading; every unit's
      boxes, rows per box and candidate digest identical to its numpy baseline:

      | unit | numpy | compiled | ratio |
      |---|---|---|---|
      | synthetic monoclinic | 194.8-205.6 s | 10.0 s (9.995, 10.023) | ~20× |
      | brucite hexagonal | 241.1 s | 226.0 s | 1.07× |
      | brucite trigonal | 274.6 s | 253.0 s | 1.09× |
      | corundum trigonal | 220.5 s | 203.3 s | 1.08× |
      | corundum tetragonal | 554.6 s | 536.6 s | 1.03× |

      The monoclinic figure includes `_centre_volumes`: once the traversal was
      compiled, ordering the grid's survivors (`_centre_volume` per cell) was 24 %
      of the unit, 14.0 s → 10.0 s when batched on the same bits. The kernels
      build before any unit's clock starts: 4.4 s cold, 0.23-0.27 s from the
      numba cache.
- [x] `tests/test_acceptance_indexing.py` once on the final tree (with the engine
      and kernel files, `-n auto`): 135 passed, 4 skipped — the four order rows
      `_skip_unless_finished` still skips, the 2-D units cut at 300 s — nothing
      failed. `tests.bethanechol_benchmark --modes manual` alone, both paths: the same
      −2 of +10 and the same ranks, every set cut at its 30 s budget either way.
- [x] Skill: no routing row (a faster engine changes no call an agent makes, and the
      `quick` preset's reach did not move on real data); the reference's speed-flag
      paragraph now names the dichotomy search, at one byte under main's size.

## Acceptance

Gate reading recorded with its profile. If built: bit-identical `n_boxes`/`n_rows`
and candidates with the kernel on and off; the gate's units faster by a stated,
measured range; the acceptance file green with no finished-search row changed.

```sh
.venv/bin/python -m pytest tests/test_indexing_kernels.py tests/test_indexing_engines.py -n auto --dist loadgroup
RIETX_COMPILED=0 .venv/bin/python -m pytest tests/test_indexing_kernels.py tests/test_indexing_engines.py -n auto --dist loadgroup
.venv/bin/python -m pytest tests/test_acceptance_indexing.py -n auto --dist loadgroup
.venv/bin/python -m ruff check src tests examples
```

## References

Louër & Louër (1972, *J. Appl. Cryst.* **5**, 271-275) and Boultif & Louër (1991, *J. Appl.
Cryst.* **24**, 987-993) — the dichotomy method, as `dichotomy.py` cites them;
WP-1030 (box-death profile), WP-1115 (the tier), WP-1449 (the cut searches).

## Handover log

### 2026-09-28 — closed: the search is compiled and bit-identical; real indexing is bound by its leaves

Would a compiled kernel improve indexing? For the dichotomy engine's box search,
yes, and it is built: the same boxes in the same order and the same answers, bit for
bit, about twenty times faster on a synthetic monoclinic list. But on every real
pattern measured the search was not where the time went. Brucite and corundum (two
free metric parameters) spend 85-87 % of a unit refining the cells the search
reaches and gain 3-8 %; the bethanechol benchmark's real monoclinic sets, cut at
their 30 s budgets, score the same on both paths and get 13 % further. So the kernel
answers the question asked and not the one the budget poses: whether a real search
finishes is decided by its leaves, which are now WP-1509's.

*Done.* The profile gate (§ Gate reading), read split and put to the maintainer, who
chose the kernel here and the leaves as a new WP. `src/rietx/indexing/_kernels_numba.py`
(`test_rows`, `traverse`) behind `dichotomy._traversal_kernels`, under the model
tier's switch, built before any unit's clock starts; `_search_one`'s leaf body moved
into one closure both paths call; `_centre_volumes` orders the grid for both paths
on the scalar key's bits. `tests/test_indexing_kernels.py`, seven tests, eighteen
cases, two made to fail on purpose (§ Tasks). A rule in `indexing/CLAUDE.md` (cap
306 → 312), the skill's speed-flag paragraph, the manual's compiled-kernels section,
a 1.5.1 release-note section, and WP-1509 filed and re-rated P2.

*Measured* (`[dev]`, Linux x86-64, 4 cores, py3.12, numba 0.67.0, numpy 2.5.3,
nothing else running unless named):
- The gate table and the before/after table are in § Gate reading and § Tasks. Every
  unit replayed from the inputs `index_pattern` hands the engine, captured by
  stubbing the engine registry: boxes, rows per box and candidate digest identical
  on both paths for all five, and for corundum hexagonal.
- Bethanechol set F, manual mode, its 30 s dichotomy unit: numpy 93 082-95 451
  boxes, compiled 105 357-107 799. Numpy spends 21 % in the grid, 15 % in the
  bisection, 45 % in leaves and 9 % ranking; compiled, the grid and traversal are
  3.7 %, leaves 67 % and `dedup_candidates` 20 % (the unit crossed `DEDUP_EVERY`).
  Run to completion with a 3600 s budget, the compiled unit had not finished after
  35 minutes, and was stopped: a finished real 4-D search is long even compiled.
- The manual-mode benchmark, both paths, alone: −2 of +10, identical ranks and
  nearest-cell ppm, 115.8-121.4 s a set, every set incomplete.
- Kernel build 4.4-4.6 s cold (three fresh caches), 0.23-0.27 s from the numba cache.
- After the review pass made the grid pass one shared function (so the on/off tests
  can no longer see a grid bug), synthetic monoclinic was replayed again on both
  paths against the digest recorded before it: 1 309 957 boxes, 107.4 rows a box,
  `fc4d2b0b`, identical; 10.07 s compiled, 193.4 s numpy.
- Fast suite (`-m "not slow"`, `-n auto`) on this branch merged with main at
  `40820ff`: 6676 passed, 163 skipped, 1 failed, 20:54 — the failure is
  `test_telemetry`'s unwritable-directory case, which a root container cannot fail
  (WP-1449 recorded the same). Before the merge the branch read 6583 + 163 + 1; the
  +93 is main's merge, and this session's own addition is the 18 cases of the new
  file, all passing. Main's own count at `40820ff` was not measured (CI's job), so
  the exact baseline check could not be closed. The seven added tests cost 5.46 s
  over their 18 cases (`tests.added_test_times`), none in the slow tail.
- `test_acceptance_indexing.py` + `test_indexing_engines.py` (slow rows included) +
  the new file, `-n auto`: 135 passed, 4 skipped, 48:45 — the skips are the order
  rows whose 2-D dichotomy units the 300 s budget cut, as before. The full selection
  was not run; the nightly is its measurement.
- The same three files again after the review pass, on the tree merged with main at
  `40820ff`: 135 passed, 4 skipped, 0 failed, 48:51 — identical to the first run,
  the same four order rows skipped.

*Review* (`/code-review high --fix`, eight findings). Taken: the kernels build after
the cancel check, so a stopped run does not wait on a cold compile; a singular
matrix in the stacked inverse falls back to the scalar key rather than taking the
unit down; the grid pass is one function both paths call; wall clock quoted as
ranges (the cold build re-measured twice for it); a dead counter, a docstring, a
wrap. Declined: `compiled_kernels_active` stays `True` when the indexing kernels'
build fails and latches off — the model tier's flag has the same gap (`enabled()`
never learns of a failed `build`), and fixing it means a signal both tiers report,
not a branch here.

*Gotchas.*
- **The cost model was wrong three times for this engine**, twice in this WP: the
  plan read 2-D units as box-bound (they keep ~2000 rows a box), and the synthetic
  4-D unit as representative of real 4-D data (real monoclinic data tolerates 8
  unindexed lines and wider windows, and its leaves dominate once the search is fast).
- **Only the leaf-sequence assertion sees a traversal-order bug**: a finished search
  tests the same set of boxes in any order, so counts and candidates cannot.
- **A cut search stops later on the compiled path** — by up to one
  `TRAVERSAL_ROW_CHUNK` (about 0.1 s) or one leaf — which is machine load either way.
- The leaves' BLAS is multithreaded, so a "serial" replay uses several cores;
  compare runs on one machine, never across.

*Next.*
1. WP-1509, in its task order: the centred replay on survivors first (exact, and
   28-41 % of a 2-D unit, 8 % of bethanechol F's compiled one), then an
   order-preserving restriction of `assign_lines`' trial set, which also reaches
   trial_error's `_score` (82 % of its monoclinic unit), then `dedup_candidates`.
2. After 1509, the acceptance file again: whether the 2-D rows now finish inside
   300 s is what lets 1449's order rows stop skipping.

- **2026-09-27** — created from the maintainer's question; gate not yet read.

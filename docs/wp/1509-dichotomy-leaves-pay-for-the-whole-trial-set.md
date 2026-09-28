# WP-1509 — a dichotomy leaf pays for the whole trial set

Milestone: unscheduled · Status: ✅ 2026-09-28 — real 2-D searches ~3× faster (255-363 s → 81-107 s),
every finished search bit-identical; no acceptance row cut at 300 s; a distinct-lattice dedup remainder fenced
Track: A long run is not one fit
Depends on: — (1508 soft: both edit `_search_one`'s phase 2)

## Goal

A 2-D dichotomy unit (hexagonal, trigonal, tetragonal) spends its time on the work a
leaf needs, not on re-reading every trial reflection at every leaf — with every
finished search's boxes, leaves and candidates unchanged.

## Context

**Where the time goes, measured by WP-1508's gate** (serial replays of the units
`index_pattern` hands the engine, to completion, `py-spy` at 50 Hz; `[dev]`, Linux
x86-64, 4 cores, py3.12). On the four real 2-D units the 300 s budget cuts, the box
traversal is 10-12 % and the **leaves are 85-87 %**:

| unit | wall | leaves | `_accept` | centred replay |
|---|---|---|---|---|
| brucite hexagonal | 241 s | 85 % | 50 % | 35 % |
| brucite trigonal | 275 s | 87 % | 46 % | 41 % |
| corundum hexagonal | 204 s | 85 % | 56 % | 28 % |
| corundum trigonal | 221 s | 87 % | 51 % | 36 % |

~900 raw candidates a unit, so ~900+ leaves, each paying both costs once per
admissible centring (trigonal has two, which is why its replay share is larger).

**Real 4-D data is leaf-bound too, once the traversal is compiled** (WP-1508,
2026-09-28). 1508's gate read a *synthetic* monoclinic unit as 94 % traversal; the
bethanechol benchmark's set F in manual mode (monoclinic, 8 unindexed lines
tolerated, a 30 s unit) is not that. On the numpy path it spends 21 % in the grid,
15 % in the bisection, **45 % in leaves** and 9 % ranking; with the traversal
compiled those two fall to 3.7 % and the budget-bound unit spends the freed time
in leaves (`_accept` 59 %, centred replay 8 %) and in `dedup_candidates` (20 %),
which ran because the unit now found more than `DEDUP_EVERY` = 2000 raw
candidates. The manual-mode benchmark scored the same on both paths (−2 of +10,
all ten sets incomplete at ~118 s a set). So this WP is the lever for real data in
**both** regimes, and `dedup_candidates` (a python O(N·K) loop over the raw
harvest) is a third leaf-side cost to measure.

**Cost 1 — the centred replay re-tests the centring's *whole* search set.** At a
leaf, `_search_one` (phase 2, the `for centring … _test_box(m_search[centring], …)`
line) replays the centred pass WP-1030 folded into the primitive one. It hands
`_test_box` `m_search[centring]` — every search-set row of that centring, ~2000 on
these units — where only the leaf's own **survivors** can reach a search line.
Exact by the same monotonicity every prune rests on: a child's Q intervals are
subsets of its parent's, so a row that reaches no line over an ancestor reaches none
over the leaf, and a row that reaches no line changes nothing `_test_box` computes
(no column of `hit` is set, so misses, `relevant`, the counts, the forced-line
distinctness and the width are all unmoved; the `q_min ≤ q_hi` filter only ever
drops such rows). So the replay can run on survivors ∩ centring. The stack carries
row *values* (`m`), not row identities, so the fix needs the centring membership to
ride with the rows — a per-row centring bitmask filtered by the same masks, or row
indices. *Superseded in part 2026-09-28:* WP-1508's kernel has landed (PR #514) and
its pool carries row indices into `m_full`, but a leaf leaves the kernel as
`(lo, hi, width)` only — its survivors sit at `pool[pool_top:pool_top + k]` and are
overwritten by the next box, so the kernel must copy them out beside the leaf. The
numpy loop still stacks values.

**Cost 2 — `assign_lines` scans the whole centred trial set per anneal pass.**
`_accept` calls it up to `MAX_ASSIGN_PASSES + 2` times per leaf per centring, and each
call computes `dm @ af` over every row of `hkl_c` (up to `MAX_TRIAL_HKL` = 200 000)
before dropping everything outside the observed Q window. Measured on corundum
hexagonal: the gemv is 12.7 % of the unit and the in-window mask/fancy-index 17.5 %;
`refine_candidate`'s LAPACK is 15 %. Two traps for an exact restriction:
- **Row order is part of the answer.** `assign_lines` argsorts the in-window Q, and
  symmetry-equivalent reflections tie exactly, so which hkl a line is assigned
  follows the input order — a reordered trial set moves the refined cell in its last
  bits. A restriction must keep the original row order (a mask, never a sort).
- **A BLAS gemv on a subset is not promised to reproduce the full gemv's rows.**
  Measure it on the platforms the goldens use before relying on it; otherwise
  compute the restricted rows the way the full product did.
A bound that is exact across the anneal passes has to hold for every af the passes
visit, not only the leaf's box (refinement moves af out of it).

**trial_error pays the same leaf cost** (WP-1508, 2026-09-28). Its synthetic
monoclinic unit (270.5 s) spends 82 % in `_score` — `assign_lines` over the trial
set plus `refine_candidate` and `refine_with_shift`, once per surviving solution —
and 13 % in the batched solve. An exact restriction of `assign_lines` lands in both
engines, so measure trial_error beside dichotomy when it does.

**What a fix must not do**: change any finished search's `n_boxes`, `rows_per_box`,
candidate list or digest. WP-1508's replay harness is the way to check: each unit's
inputs captured by swapping the engine registry (`engines._REGISTRY`) for recorders
and running `index_pattern` once, then replayed to completion per unit; the per-unit
digest is sha256 of every candidate's cell and `n_indexed`. Its scripts were session
scratch. Digests (first 8 hex; `SearchSpec` as `index_pattern` builds it at a 1e5 s
budget): brucite hexagonal `c82630be`, trigonal `719d4e0b`; corundum hexagonal
`6a060c83`, trigonal `e8466d7f`, tetragonal `f610fbdc`; synthetic monoclinic
`fc4d2b0b` — each identical on both paths on 2026-09-28.

## Non-goals

The traversal kernel (WP-1508). svd and trial_error. The budget constant
(`REAL_DATA_BUDGET_SECONDS`).

## Tasks

- [x] Centred replay on survivors ∩ centring; equivalence on the synthetic suite and
      the four 2-D units (identical `n_boxes`, `rows_per_box`, candidate digest).
- [x] An exact, order-preserving restriction of `assign_lines`' trial set at the
      leaves, or a measured statement of why none is exact.
- [x] `dedup_candidates` on a harvest past `DEDUP_EVERY`: 20 % of bethanechol F's
      compiled 30 s unit (1508); measure it on a finished search and fix or fence it.
- [x] Re-profile the four units; `tests/test_acceptance_indexing.py` once on the final
      tree, reporting which searches now finish inside 300 s.
- [x] Skill: none expected (no call an agent makes changes); say so at close.
      *None: no call an agent makes changed, and the skill's speed-flag paragraph
      quotes no number this moved.*

## Acceptance

Identical finished-search outputs; the four units' leaf share and wall re-measured.

```sh
.venv/bin/python -m pytest tests/test_indexing_engines.py -n auto --dist loadgroup
.venv/bin/python -m pytest tests/test_acceptance_indexing.py -n auto --dist loadgroup
.venv/bin/python -m ruff check src tests examples
```

## References

WP-1508 § Gate reading (the profile); WP-1030 (why the centred pass is replayed at
the leaf, and why only real data showed it); WP-1449 (the cut searches).

## Handover log

### 2026-09-28 — closed: a real indexing search spends its time on the cells it finds

Brucite's and corundum's indexing searches now finish about three times faster
(81-107 s where they took 255-363 s on the same machine; corundum's tetragonal
search 237 s where it took 794 s), and every finished search returns exactly what
it did before: the same boxes, candidates and line assignments, bit for bit. The
time had gone on work no answer depended on: re-testing reflections a leaf's box
had already ruled out, scanning a 150 000-row trial set to use about 1 000 of
them, and comparing thousands of identical candidates one by one. With it gone
the acceptance suite's 300 s budget cuts no search, so the ranking rows that used
to skip now run, and pass. What is left in a leaf is mostly refining the cell
itself. A harvest of genuinely distinct candidates still spends ~45 s in pairwise
χ² tests, which is fenced below rather than fixed.

*Done.*
- **Centred replay on survivors ∩ centring** (85f5cfe). Both paths hand the leaf
  its surviving rows as indices into the search set: the numpy loop stacks ids
  beside values, and its grid now carries ids; the kernel copies a leaf's pool
  slice into a `leaf_rows` buffer (`state[5]`), handing back before it could
  overflow. `dichotomy._centred_replay` tests survivors ∩ centring and falls back
  to the whole set only for an empty intersection when every line may go
  unindexed.
- **`engines.TrialIndex`** (66e38d3, 6bd1157). An exact per-axis bound, |hᵢ| ≤
  aᵢ√Q_top, in closed-form 3×3 arithmetic. It is guarded by Sylvester's criterion,
  a defect floor and a condition cap, and its margins are sized for the product's
  and the inverse's rounding. Rows come back in the set's own order, the last bound
  is reused while it repeats, and sets under 15 000 rows are not indexed.
  `assign_lines(index=)` gathers hkl only for the matched rows, everywhere. The
  product shrinks to `dm[rows] @ af` only where `row_local_product()` (a probe,
  once a process) found the BLAS row-local; elsewhere `(dm @ af)[rows]`. Wired
  into dichotomy (per centring) and trial_error (per scoring set). The task's
  "or a measured statement of why none is exact" did not arise: the restriction
  is exact, and only its product half is platform-measured.
- **Dedup** (52b20a4). Each (distinct candidate, group) verdict is computed once,
  and so is each distinct A..F reduction. The volume gate is asked only of groups
  in the band, kept per (system, centring) sorted by volume, with infinite volumes
  always asked. `rank_candidates(deduped=True)` comes from dichotomy when its list
  is exactly a dedup output, since a second pass over that is the identity.
- Tests: the per-leaf replay equivalence on both paths
  (`test_indexing_kernels.py`, 8 cases), and four engine tests: the index as a
  superset in order, `assign_lines` with and without it, the BLAS subset where the
  probe says yes, and fast against plain dedup. Each was made to fail on purpose,
  and the dedup test needed three witnesses before it could see its three breaks.
- A rule in `indexing/CLAUDE.md` (cap 312 → 318, logged), a 1.5.1 release-note
  section, and the kernel's `_test_box` survivor ids asserted in the one-box test.

*Measured* (`[dev]`, Linux x86-64, 4 cores, py3.12, numba 0.67.0, numpy 2.5.3 on
OpenBLAS 0.3.34's Haswell kernel, py-spy 0.4.2 installed in the worktree venv):
- **Harness rebuilt; all six of WP-1508's digests reproduced** on the unchanged
  tree. The digest is sha256 of `np.array([[*cell, n_indexed] …], float64).tobytes()`.
  On the final tree all six units (four 2-D, corundum tetragonal, synthetic
  monoclinic) are identical down to hkl and line assignment bytes, and trial_error
  is identical on corundum hexagonal and synthetic monoclinic.
- **Re-profile**, same machine, serial, alone, default threads, 50 Hz:

  | unit | before | after | leaves | `refine_candidate` | replay | `rows_within` |
  |---|---|---|---|---|---|---|
  | brucite hexagonal | 327.1 s | 106.7 s | 96 → 81 % | 17 → 42 % | 35 → 4 % | 1.5 % |
  | brucite trigonal | 362.6 s | 97.0 s | 96 → 86 % | 16 → 44 % | 41 → 6 % | 1.6 % |
  | corundum hexagonal | 254.7 s | 80.6 s | 95 → 85 % | 19 → 46 % | 29 → 4 % | 1.7 % |
  | corundum trigonal | 285.8 s | 82.7 s | 96 → 87 % | 17 → 46 % | 34 → 6 % | 1.3 % |
  | corundum tetragonal | 793.5 s | 236.5 s | 84 → 72 % | 15 → 40 % | 29 → 4 % | 1.3 % |

  The index's bound cost 15-16 % of a unit while it used LAPACK and 1.3-1.7 % in
  closed form. Tetragonal's dedup is 24 % after (14.5 + 7.4 % before), the fence
  below.
- **The index per call**, reuse defeated, one BLAS thread: 1188 → 138 µs at
  150 381 rows, even at ~12 000, ahead from ~18 000. The LAPACK-bound first
  version made trial_error's monoclinic unit (2456-row sets) 19 % slower, which
  is why the floor exists; back to back and alone that unit reads 346.5 s before
  and 339.7 s after. trial_error on corundum hexagonal: 14.5 → 6.0 s.
- **BLAS row-locality**: 0 of 12 000 subsets (2-5000 rows of a 113 490-row
  product) differ, while the whole product itself differs from a left-to-right
  sum on 38 475 rows. 1378 of 4054 single-row products differ, because numpy sends
  a (1, 6) product to `dot`.
- **Dedup**, one BLAS thread, idle machine. Bethanechol F's cut unit held 7000 raw
  candidates, 761 distinct: 18.8 → 2.6 s. Corundum tetragonal's finished unit held
  5037 → 4942: first pass 53.2 → 49.7 s, and the second pass (52.5 s) is gone.
- **Fast suite**, `-m "not slow"`, `-n auto`: 6690 passed, 163 skipped, 1 failed,
  21:34-22:01 over two runs. The second ran on the final tree, after the review
  fix, with identical counts, and main had not moved from `3b04eef`, so that is
  the tree that merges. The failure
  is `test_telemetry`'s unwritable-directory case, which a root container cannot
  fail, as WP-1508 and WP-1449 recorded. This session added 14 cases (8 kernel, 6
  engine), 3.21 s in all (`tests.added_test_times`: the replay test 2.39 s over 8
  cases, the rest ≤ 0.42 s), none in the slow tail. The exact +14 check is not
  closed, since main's own count at `3b04eef` was not measured (CI's job).
- **Acceptance**, `test_indexing_engines.py` + `test_acceptance_indexing.py`,
  `-n auto`, slow rows included: 127 passed, 0 skipped, 22:33. WP-1508's run of the
  same two files had 121 cases with 4 skipped (order rows whose 2-D units the
  300 s budget cut); 121 + this session's 6 engine cases = 127, and none skipped.
  The longest fixture setup is corundum's at 621 s for three searches. The full
  selection was not run: the change is indexing-only, its slow rows ran, and the
  nightly measures the rest.

*Fenced.* Corundum tetragonal still spends ~45 s of dedup in 567 535 χ² tests
between distinct lattices, a 6×6 pseudo-inverse each. Batching them would rest on
numpy running the same LAPACK routine per matrix in a stack, a platform claim
like `row_local_product`'s, so it was not built here. `refine_candidate`'s
`lstsq` (40-46 % of a 2-D unit) is now the largest leaf cost, and it is work a
leaf needs.

*Review* (`/code-review high --fix`, five findings, no correctness bug). Three
were taken (b072098). The numpy fallback's grid gathered a parent's rows once per
child and its phase-2 stack once per frontier cell, both costs the ids this WP
added. And the BLAS probe ran inside the first unit's clock. The fix was
replayed to the digests: synthetic monoclinic and corundum hexagonal on the numpy
path, corundum trigonal compiled. Two were declined. Re-probing per product size
or thread setting would change the probe's design, and the WP records the answer
as a per-machine measurement. Wiring the index into svd and priors is a non-goal
here and needs its own measurement, since small sets were measured slower. That
one goes to Next.

*Gotchas.*
- The index made trial_error slower before it made anything faster: a fixed
  per-call cost against a scan of a few thousand rows. Measure the small sets
  before claiming a restriction wins.
- A dedup equivalence test with only copies cannot see a cache keyed without the
  group. Without a same-lattice pair 0.6 % apart in volume it cannot see a narrow
  band, and unless an infinite-volume lattice leads its family it cannot see that
  lattice left out. Each passed here until its witness was added.
- Default-thread OpenBLAS makes the leaves' small products slower than one thread
  (1-thread replays 82-94 s against 91-112 s at default on the same tree). Compare
  runs at one setting.
- `pgrep -f <script>` inside an `until` loop matches the loop's own command line,
  so the waiter never exits.

*Next.* This WP is closed, so there is nothing further here.
1. PR #516's review and merge are the maintainer's.
2. WP-1449 can read its finished-run confirmation off the acceptance file once
   #516 merges (pushed into its `### Inherited`).
3. If indexing speed comes back: batching the distinct-lattice χ² tests (with its
   own equivalence argument), `refine_candidate`'s per-pass `lstsq`, or the index
   in svd's assign-and-refine loop and `priors`, which still scan whole sets
   (measure the set sizes first, since the floor exists for small ones). The macOS
   and Windows nightly logs show whether
   `test_a_subset_product_is_the_whole_products_rows_where_the_probe_says_so`
   skips there, which is where the index keeps the whole product.

- **2026-09-27** — filed from WP-1508's profile gate, at the maintainer's call to
  build the 4-D kernel there and take the 2-D leaves here.

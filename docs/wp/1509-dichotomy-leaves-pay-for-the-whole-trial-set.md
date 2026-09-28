# WP-1509 — a dichotomy leaf pays for the whole trial set

Milestone: unscheduled · Status: ⬜
Track: A long run is not one fit
Depends on: — (1508 soft: both edit `_search_one`'s phase 2)
Priority: P2 2026-09-28 — was P3: 1508 measured real monoclinic data leaf-bound too (every bethanechol manual set is cut at its 30 s budget on either path), so this is the lever for every real search, not only the 2-D acceptance rows 1449 skips

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
indices. WP-1508's kernel, if it has landed, carries indices already.

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

**What a fix must not do**: change any finished search's `n_boxes`, `rows_per_box`,
candidate list or digest. WP-1508's replay harness (inputs captured by stubbing the
engine registry) is the way to check; its digests are below (`### Inherited`).

### Inherited

- **From WP-1508 (2026-09-28): trial_error pays the same leaf cost.** Its synthetic
  monoclinic unit (270.5 s) spends 82 % in `_score` — `assign_lines` over the trial
  set plus `refine_candidate` and `refine_with_shift`, once per surviving solution —
  and 13 % in the batched solve. An exact restriction of `assign_lines` lands in both
  engines, so measure trial_error beside dichotomy when it does.
- **From WP-1508: the replay harness.** Each unit's inputs were captured by swapping
  the engine registry (`engines._REGISTRY`) for recorders and running
  `index_pattern` once, then replayed to completion per unit; the per-unit digests
  (sha256 of every candidate's cell and `n_indexed`) are what "unchanged" was
  checked against. Rebuilding it takes minutes; the scripts were session scratch.
  Digests (first 8 hex; `SearchSpec` as `index_pattern` builds it at a 1e5 s
  budget): brucite hexagonal `c82630be`, trigonal `719d4e0b`; corundum hexagonal
  `6a060c83`, trigonal `e8466d7f`, tetragonal `f610fbdc`; synthetic monoclinic
  `fc4d2b0b` — each identical on both paths on 2026-09-28.

## Non-goals

The traversal kernel (WP-1508). svd and trial_error. The budget constant
(`REAL_DATA_BUDGET_SECONDS`).

## Tasks

- [ ] Centred replay on survivors ∩ centring; equivalence on the synthetic suite and
      the four 2-D units (identical `n_boxes`, `rows_per_box`, candidate digest).
- [ ] An exact, order-preserving restriction of `assign_lines`' trial set at the
      leaves, or a measured statement of why none is exact.
- [ ] `dedup_candidates` on a harvest past `DEDUP_EVERY`: 20 % of bethanechol F's
      compiled 30 s unit (1508); measure it on a finished search and fix or fence it.
- [ ] Re-profile the four units; `tests/test_acceptance_indexing.py` once on the final
      tree, reporting which searches now finish inside 300 s.
- [ ] Skill: none expected (no call an agent makes changes); say so at close.

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

- **2026-09-27** — filed from WP-1508's profile gate, at the maintainer's call to
  build the 4-D kernel there and take the 2-D leaves here.

# WP-2035 — a reduced cell is its input's exact image, near a right angle too

Milestone: unscheduled · Status: ⬜
Track: What fires, and what stays silent
Depends on: — (1923, closed: the exact change of basis; 1932, closed: the boundary-free comparison that reads it)
Priority: P3 2026-10-23 — a property test fails on a reachable F-centred cell at 1.1e-7 of the metric's scale, and replays only from one machine's local hypothesis database, so CI cannot see it

## Goal

`reduce_cell` returns a cell whose metric is M·G·Mᵀ of its input under the
change of basis it records, to rounding, on every centring. This is
WP-1923's claim, and a cell near a right angle still breaks it. A test that
CI runs pins the case.

## Context

- **The case** (WP-1930 found it on 2026-10-13, macOS arm64, at `aea419b6`):
  centring F, a = 3.2, b = 16.0, c = 23.602486327493914 Å, α = 81°, β = 66°,
  γ = 65°. `test_the_reduced_cell_is_the_exact_image_of_its_input[F]`
  (`tests/test_indexing_reduce.py:350`) asserts the reduced metric equals
  M·G·Mᵀ to 1e-12·max|G|. It failed on `c4607fa0` as well, a tree without
  WP-1930's change. It was carried in WP-1932's `### Inherited` and moved
  here at 1932's close.
- **Still failing at `12f459e`** (`[dev]`, Linux x86-64, 2026-10-23, replayed
  through the test's `inner_test`). The reduced cell is (3.2, 7.388025,
  10.780972 Å, 91.049995°, 90.00001°, 101.073895°). The worst entry is G₃₂:
  −1.4595751161 from `reduce_cell` against −1.4595624988 for M·G·Mᵀ. That is
  1.26e-5 absolute and 1.09e-7 of max|G|, the same numbers WP-1930 recorded
  on macOS. So the defect is the same on both platforms and is not rounding.
- **Where to look first.** β sits 1e-5° from a right angle. WP-1923 builds the
  cell from M·G·Mᵀ only where an entry's sign disagrees with gemmi's, and
  otherwise keeps gemmi's ε-reduced cell (WP-1932's Inherited, 2026-10-11).
  A cell whose sign agrees but whose value gemmi moved within ε would take
  that second path. That is a hypothesis, not a measurement.
- **Why it matters beyond the test.** Since PR #949, `equal_reduced`,
  `equal_reduced_many` and `same_lattice` compare reduced cells through
  `reduce._equal_across_boundaries`, which assumes the reduced cell is an
  exact image of the candidate. #949's bethanechol run moved no grade
  (WP-1932's close), so no measured answer depends on this case yet.

## Non-goals

- The comparison across boundaries (WP-1932, shipped).

## Tasks

- [ ] Pin the case as an `@example` CI runs, as a strict xfail first so the
      suite stays green.
- [ ] Find which path in `reduce_cell` returns the non-image metric, and
      return M·G·Mᵀ there. Lift the xfail. The unit replay digests
      (`python -m tests.unit_replay`) and `tests/test_acceptance_indexing.py`
      either stay unchanged or have each move named.
- [ ] Skill: none expected.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_indexing_reduce.py tests/test_indexing_reduce_boundaries.py -n auto --dist loadgroup
.venv/bin/python -m pytest tests/test_acceptance_indexing.py -n auto --dist loadgroup
.venv/bin/python -m ruff check src tests examples
```

## References

- [WP-1923](1923-a-candidate-in-its-conventional-setting.md) (the exact
  change of basis); [WP-1930](1930-a-width-freed-on-its-floor-leaves-it-by-rounding.md)
  (where the case surfaced); [WP-1932](1932-two-candidates-compared-across-a-reduction-boundary.md).

## Handover log

- **2026-10-23** — created by WP-1932's close, from its `### Inherited` entry
  of 2026-10-13, after re-running the case on today's tree. No open WP owns
  `reduce_cell`'s exactness. 1452 replaces spglib, 1528 declines a declared
  cell's box, and 1921 indexes a user's database, and none of them changes
  the reduction.

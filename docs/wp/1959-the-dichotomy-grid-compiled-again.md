# WP-1959 — the dichotomy grid compiled again, so a ceiling reaches svd

Milestone: unscheduled · Status: ⬜
Track: A long run is not one fit
Depends on: —
Priority: P2 2026-10-13 — a defect that fires wrongly: on #780's monoclinic case a whole-run ceiling under ~157 s of CPU returns no candidate, although svd alone finds the cell in 27 s; the workaround is a longer ceiling or `engines=("svd",)`

## Goal

`indexing/dichotomy.py`'s box test (and as much of the traversal around it as a measurement says pays) runs in the `rietx-kernels` crate. Every finished search returns the same candidates bit for bit, and on #780's case the grid costs a small fraction of the ceiling it starves today.

## Context

**Why this exists (WP-1924, 2026-10-12/13).** The scheduler in `indexing/workflow.py` runs each crystal system's units in registry order, `dichotomy`, `svd`, `trial_error`, under one search `Deadline` and with no per-unit share. WP-1940 (PR #864) deleted dichotomy's numba twin, so the traversal runs on numpy alone. On #780's case its first phase, the grid (`_grid_pass`), alone costs about 157 s of CPU over 161 705 boxes (macOS arm64, `[dev]`, at `e1d19359`, load 110-180). So under any ceiling below that, dichotomy takes the whole run. At 120 s of CPU it reached 131 912 boxes, svd and trial_error never started, and the run returned nothing. svd alone had the lattice at 27 s of CPU.

**The decision (maintainer, 2026-10-13).** Two answers were on the table: let the cheapest engine open each system (a scheduling change), or compile the grid again. This WP is the second. It shrinks the window in which a ceiling starves svd and does not close it: a ceiling below the compiled grid's cost still ends before svd. So the acceptance states that ceiling on #780's case rather than claiming the defect gone.

**What a compiled traversal bought before** (WP-1508's table, numba, macOS arm64): synthetic monoclinic 194.8-205.6 s on numpy against 10.0 s compiled, about 20×. Four real patterns were leaf-bound and gained only 1.03-1.09× (the leaves are WP-1509's, which the compiled traversal did not reach). So the win lands on box-bound searches, which #780's is.

**Seams.**
- `_test_box` (`dichotomy.py`, ~line 241) is every prune, in cost order: Q bounds per trial row (`_q_bounds`), the A_f interval and the axis-swap prune, the determinant band (`_det_interval`), one lines × reflections hit matrix, `_assignment_possible`, the induced width and the uniqueness stop. The grid (`grid_test` inside `_search_one`) and phase 2 share it, so the two phases cannot disagree about a box. A port keeps that: one kernel, both callers.
- `_grid_pass` is a breadth-first Python loop that calls `test(rows, lo, hi)` per box. Open question for the first task: port `_test_box` alone and keep the loops in Python (~1 ms a box now, so per-call overhead is small against it), or port the whole traversal as 1508's numba twin did. Measure before choosing.
- The deleted numba twin is rietx's own MIT code and may be read as a reference: `git show 2cc71c3^:src/rietx/indexing/_kernels_numba.py` (514 lines).
- Survivor lists are `_row_index_type`'s narrowest unsigned type (WP-1924; uint16 on #780's case). The kernel takes that width, not int64.

**Rules that bind the port** (root CLAUDE.md § compiled tier, `indexing/CLAUDE.md`):
- The numpy loop is the oracle, **on the bit and leaf by leaf**, because box counts cannot see the order.
- A new kernel is a serial loop over a row range that releases the GIL. It ships as a minor `rietx-kernels` release (1.3.0 after today's 1.2.0) that raises `compiled.KERNEL_FLOOR` and rietx's pin, with `KERNEL_ABI` unchanged.
- The fallback stays mandatory and exercised: `RIETX_COMPILED=0` / `compiled.set_enabled` runs the numpy side, and a missing kernel declines with a warning, never raises.
- One path per process, never per call.

**Measuring.** `tests/repro_780.py` rebuilds #780's case. On macOS read memory as the physical footprint (`memory_bytes`), not RSS. Under load, count a ceiling with `--cpu-clock`. The bethanechol benchmark's limits are wall clock, so run it alone, on the same class of machine as its baseline. Baseline on the merged WP-1924 tree, Linux x86_64 `[dev]`, 2026-10-13: global −9, manual −3, default −6. Set F's default-mode miss reproduced identically on `main` before #930.

## Non-goals

- Shrinking the metric box to buy speed (`indexing/CLAUDE.md`).
- Reordering engines or giving each unit a share of the ceiling (the alternative not taken, 2026-10-13).
- The leaves' cost (WP-1509 shipped; WP-1520 is `refine_candidate`'s).

## Tasks

- [ ] Profile one grid on #780's case: the share of `_test_box` against the loop around it. Decide between a box-test kernel and a whole-traversal kernel, and write the measurement here.
- [ ] The kernel in `kernels/src/`, with its `compiled.py` entry point and the numpy fallback. Bit-identical to `_test_box` box by box on #780's case and the seven WP-1924 replay digests.
- [ ] Wire it into the grid and phase 2. Leaf-by-leaf agreement with the numpy loop under `RIETX_COMPILED=0` in a test.
- [ ] `rietx-kernels` 1.3.0 and rietx's floor raised (`docs/RELEASING.md`'s kernel route).
- [ ] Measure: #780's grid CPU before and after, and the largest whole-run ceiling under which #780's case still returns no candidate. Then `tests/test_acceptance_indexing.py`, and the bethanechol benchmark run alone in default mode against −6.
- [ ] Skill: `references/abstention.md`'s `INDEX_BUDGET_EXHAUSTED` row if the advice on a ceiling for large volumes moves, else "none" and why.

## Acceptance

Every finished search bit-identical, with the numpy loop as the oracle. #780's grid at least an order of magnitude cheaper in CPU. The starving ceiling stated.

```sh
.venv/bin/python -m pytest tests/test_compiled_kernels.py tests/test_indexing_engines.py -n auto --dist loadgroup
.venv/bin/python -m pytest tests/test_acceptance_indexing.py -n auto --dist loadgroup
.venv/bin/python -m tests.repro_780 120 --cpu-clock
.venv/bin/python -m tests.bethanechol_benchmark --modes default   # alone
```

## References

- Boultif, A. & Louër, D. (2004). *J. Appl. Cryst.* **37**, 724-731 (dichotomy indexing).
- Bergmann, J., Le Bail, A., Shirley, R. & Zlokazov, V. (2004). *Z. Kristallogr.* **219**, 783-790 (the bethanechol benchmark).
- Issue #780; WP-1924 (profile), WP-1508 (the compiled spike), WP-1940 (the kernel tier).

## Handover log

- **2026-10-13** — created from WP-1924's last task, on the maintainer's choice of compiling the grid over reordering engines. No open WP owns it: 1508 and 1940 are closed, and 1924 owns the memory and the profile, not a kernel.

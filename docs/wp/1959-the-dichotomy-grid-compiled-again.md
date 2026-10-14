# WP-1959 — the dichotomy grid compiled again, so a ceiling reaches svd

Milestone: unscheduled · Status: 🔄 2026-10-13 — claimed by @yue-here
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

## Findings (2026-10-14)

Measured on #780's case, macOS arm64, `[dev]`, load ~3 on 10 cores, CPU seconds from `time.process_time`. Scripts in the session scratchpad; the numbers are what to carry.

**The grid is 57 s of CPU at this load, not 157 s.** The Context's figure was taken at load 110-180. 99.2 % of it is inside `_test_box`. The loop, `_stage_edges` and the children cost 0.45 s together.

**Most of the grid's cost went to boxes a row-free prune refuses.** In the last stage, 135 593 of 158 282 boxes die at the axis-swap or volume prune. `_test_box` computed ~8 300 rows' Q bounds and filtered them before asking either. Q bounds and filter were 90 % of the grid. Moving the row-free prunes first cut the grid from 59.2 s to 13.5 s. All 161 705 boxes returned the same answer under both orders, and the seven WP-1924 units replay to their digests (`a7ba2bbb`).

**Phase 2, not the grid, holds #780's ceiling.** With the grid at 13.6 s, phase 2 ran 387 s over 6.67 M boxes (median 30 rows) and reached no leaf. At that size a box costs 58 µs, 92 % of it in `_test_box` and `_push_children`, which is WP-1508's overhead-bound regime. All of it was spent inside one grid cell. Phase 2 pops cells smallest volume first: the first 518 of 273 871 died at their first test, and the 519th (centre volume 29.5 Å³) took 5.1 M boxes in 281 s without finishing.

**That cell's sub-boxes lie wholly outside the search domain, and nothing refuses them.** A kept box at depth ~45 has A = 0.18538, C = 0.17430 and E = 0.36046, so |ρ₁₃| = E/(2√(AC)) ≈ 1.003. The domain is |ρ| ≤ cos 30° (`_inside_domain`), and this metric is not even positive definite. Two tests could refuse it and neither does:
- `_rho_interval` clips ρ to ±cos 30°. An interval lying wholly beyond the bound comes out inverted, and nothing reads that as a refusal.
- The expanded determinant A·B·C − B·(E/2)² carries B twice, so its interval bound loses the coupling. Its upper end stays positive while det G* < 0 at every point of the box.

Near a singular metric Q is dense, so every line keeps matching and the subtree does not converge (1.13 M boxes kept against 44 574 pruned in 75 s, depths up to 48).

**A prune on the unclipped ρ interval finds #780's lattice.** The experiment refuses a box when the ρ interval of any off-diagonal lies wholly outside ±cos 30°. It is monotone under bisection, like every other prune. On synthmono it refused 21 689 boxes, kept the digest `30473892` and took 38.6 s against 69.4 s. On #780 under a 600 s ceiling dichotomy returned 60 candidates, led by the true lattice in a non-reduced setting (4.541, 4.884, 11.742 Å, β = 120.73°, 61 of 61 lines). It did not finish the unit: 3.8 M boxes at 567 rows on average. In a second run its first accepted leaf came 132 s after the search started, and its first 61-line leaf at 144 s (the same lattice, c + a = 10.554 Å).

**On the kernel path #780's lattice comes at 6.5-7.5 s.** The grid takes 3.6-4.5 s of CPU, against 57 s at the start of the session. That is 13-16×, and the range is load: the acceptance file was running beside the second measurement. Phase 2 then costs 94-110 µs a box, and `_accept` is 82 % of it (46.3 s of 56.4 s over 26 419 leaves). The two kernels are 10 % and the Python loop about 9 %. So a whole-traversal kernel would save at most that 9 %, and the leaves are WP-1520's.

**The starving ceiling is 7 s of CPU on the kernel path.** `tests.repro_780 N --cpu-clock` at load 5-6: no candidate at 4, 6 and 7 s, and #780's cell (4.541, 4.884, 10.198 Å, β = 98.22°, found by dichotomy) at 8 and 12 s. On the numpy loop (`RIETX_COMPILED=0`) a 120 s ceiling returns the cell too (242 raw candidates at load 4), where the Context's run returned nothing. svd still never starts under these ceilings: dichotomy holds them, and now finds the cell inside them.

**The acceptance file passes on the pruned loop.** `tests/test_acceptance_indexing.py`: 44 passed in 18:03, `[dev]`, macOS arm64, with this session's measurements running beside it.

**The kernel matches numpy.** `kernels/src/dichotomy.rs` (`dichotomy_box_test`, `dichotomy_child_key`) agreed with numpy on 788 450 boxes of #780 (the grid and ~627 000 of phase 2) and on 1.17 M child keys. Its line test is a `u64` mask per row from two rank lookups, so the dense hit matrix never forms. Inside the calls it took 4.3 s against numpy's 40.5 s, Python call overhead included.

**The decision (maintainer, 2026-10-14).** The obliquity prune lands in this WP, before the kernel. It changes which boxes phase 2 visits, so it is held to the digests it cannot move, `tests/test_acceptance_indexing.py` and the bethanechol benchmark. The kernel then transcribes the pruned loop, and the bit-identity bar applies to that step.

## Non-goals

- Shrinking the metric box to buy speed (`indexing/CLAUDE.md`).
- Reordering engines or giving each unit a share of the ceiling (the alternative not taken, 2026-10-13).
- The leaves' cost (WP-1509 shipped; WP-1520 is `refine_candidate`'s).

## Tasks

- [x] Run the row-free prunes before the Q bounds (`a7ba2bbb`): the grid 4.4× cheaper, every box's answer unchanged, the seven digests replayed.
- [ ] The obliquity prune in `_test_box`: refuse a box whose unclipped ρ interval lies wholly outside ±cos 30° for some off-diagonal. A test on #780's out-of-domain box. The seven digests (only synthmono has an off-diagonal free), `tests/test_acceptance_indexing.py`, and the bethanechol benchmark alone in default mode against −6.
- [x] Profile one grid on #780's case: the share of `_test_box` against the loop around it. Decide between a box-test kernel and a whole-traversal kernel, and write the measurement here. The box test alone (§ Findings): `_test_box` was 99.2 % of the grid, and once the kernel runs, phase 2 is 82 % leaves.
- [x] The kernel in `kernels/src/`, with its `compiled.py` entry point and the numpy fallback. Bit-identical to `_test_box` box by box on #780's case and the seven WP-1924 replay digests. `kernels/src/dichotomy.rs`; `compiled.dichotomy_kernels` declines for the indexer alone on a wheel without it.
- [x] Wire it into the grid and phase 2. Leaf-by-leaf agreement with the numpy loop under `RIETX_COMPILED=0` in a test. `tests/test_indexing_kernels.py`, which `kernels.yml` runs against the wheel a pull request builds.
- [ ] `rietx-kernels` 1.3.0 and rietx's floor raised (`docs/RELEASING.md`'s kernel route).
- [ ] Measure: #780's grid CPU before and after, and the largest whole-run ceiling under which #780's case still returns no candidate. Then `tests/test_acceptance_indexing.py`, and the bethanechol benchmark run alone in default mode against −6.
- [x] Skill: `references/abstention.md`'s `INDEX_BUDGET_EXHAUSTED` row if the advice on a ceiling for large volumes moves, else "none" and why. Its measured sentence moved: #780's cell now comes 8 s of CPU into the search, where a 120 s ceiling returned nothing; the advice itself stands.

## Acceptance

The obliquity prune no worse on the acceptance file and the benchmark. Every finished search bit-identical to the pruned numpy loop, which is the kernel's oracle. #780's grid at least an order of magnitude cheaper in CPU. The starving ceiling stated.

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

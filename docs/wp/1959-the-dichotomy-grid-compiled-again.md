# WP-1959 — the dichotomy grid compiled again, so a ceiling reaches svd

Milestone: unscheduled · Status: ✅ 2026-10-14 — prune, kernel and measurements landed; rietx-kernels 1.3.0 published and the pin's floor raised to it
Track: A long run is not one fit
Depends on: —

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
- [x] The obliquity prune in `_test_box`: refuse a box whose unclipped ρ interval lies wholly outside ±cos 30° for some off-diagonal. A test on #780's out-of-domain box. The seven digests (only synthmono has an off-diagonal free), `tests/test_acceptance_indexing.py`, and the bethanechol benchmark alone in default mode against −6. `56f0cfd9`: synthmono keeps its digest, the acceptance file 44 passed, the benchmark −3 (macOS arm64; the −6 baseline is Linux x86_64).
- [x] Profile one grid on #780's case: the share of `_test_box` against the loop around it. Decide between a box-test kernel and a whole-traversal kernel, and write the measurement here. The box test alone (§ Findings): `_test_box` was 99.2 % of the grid, and once the kernel runs, phase 2 is 82 % leaves.
- [x] The kernel in `kernels/src/`, with its `compiled.py` entry point and the numpy fallback. Bit-identical to `_test_box` box by box on #780's case and the seven WP-1924 replay digests. `kernels/src/dichotomy.rs`; `compiled.dichotomy_kernels` declines for the indexer alone on a wheel without it.
- [x] Wire it into the grid and phase 2. Leaf-by-leaf agreement with the numpy loop under `RIETX_COMPILED=0` in a test. `tests/test_indexing_kernels.py`, which `kernels.yml` runs against the wheel a pull request builds.
- [x] `rietx-kernels` 1.3.0 and rietx's floor raised (`docs/RELEASING.md`'s kernel route). Tag `kernels-v1.3.0` on `2cbd7363`, five wheels on PyPI; the floor in `fc91feb2`.
- [x] Measure: #780's grid CPU before and after, and the largest whole-run ceiling under which #780's case still returns no candidate. Then `tests/test_acceptance_indexing.py`, and the bethanechol benchmark run alone in default mode against −6. Grid 57 s → 3.6-4.5 s of CPU; starving ceiling 7 s; acceptance 44 passed; benchmark default −3 (Bb, Db and E rank 1, F rank 4), run alone on macOS arm64 `[dev]`.
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

### 2026-10-14 — rietx-kernels 1.3.0 on PyPI, the floor raised to it, and the WP closed

rietx now requires the kernel wheel that carries the dichotomy's box test, and PyPI serves it on all five platforms. A plain install gets the compiled indexer with no further step. A wheel older than 1.3 is now treated like any incomplete wheel. The whole compiled tier steps aside and rietx warns once with the pin that fixes it. That ends the silent fallback the 2nd session added for the weeks PyPI had no 1.3.0. The WP is closed. Its last open question, why svd never starts under a short ceiling, belongs to WP-1924 and WP-1520.

*Done.* The maintainer tagged `kernels-v1.3.0` on the merge commit `2cbd7363` and approved the `pypi` deployment. Run 38532295652 built and tested five wheels and published them. A fresh venv installed 1.3.0 from the index on the first try, reporting interface 1 and both dichotomy kernels (darwin/arm64). PyPI lists macOS x86-64 and arm64, Linux x86-64 and aarch64, and Windows x64. `fc91feb2` raises `KERNEL_FLOOR` and the pin to 1.3 and moves the two names into `KERNEL_NAMES`. `DICHOTOMY_NAMES` is gone, and `dichotomy_kernels` reads the two from the loaded set. The indexer-only decline test became `test_a_wheel_before_the_floor_is_declined_whole_and_says_so`. It holds a 1.2.0-shaped wheel to a whole-tier decline naming both kernels, and to one warning quoting `rietx-kernels>=1.3,<2`. `install.md`, `compatibility.md` and the 1.9.0 notes quote the new pin, and the notes gain a "Requirements that rise" entry.

*Measured.* Fast selection on `[dev]`, darwin/arm64, with PyPI's 1.3.0 wheel, on main at `2cbd7363` plus `fc91feb2`: 9685 passed, 186 skipped, 1 xfailed, in 7:46. The branch removes one test and adds one, so it moves the count by zero. Main had moved since the 2nd session's 9612, so the two counts are not comparable. The renamed test runs in 1 ms. The touched files and the manual and docs tests on the final tree: 91 passed, 1 skipped. The full selection did not run, since nothing here moves a fit's arithmetic.

*Review* (`/code-review high --fix 2cbd7363..fc91feb2`, `0eacc899`). It found no code bug and seven pieces of stale text, all fixed. The decline warning and three passages of `install.md` named fits and figures as all the tier serves, and the requirements table still said 1.1. The indexing kernel tests now skip on `compiled.available()`, since a wheel is loaded or declined whole. The new test builds its pin from `KERNEL_FLOOR`. One sibling it left outside its range was fixed by hand: `install.md`'s `compiled_kernels_active` sentence. Declined: `references/diagnostics-indexing.md` says the active flag covers "the next refinement". That stays true, and the skill file has a size budget.

*Gotchas.* The Kernels gate flaked once on #971, on macOS x86-64, with no kernel past its bar (worst 5.3e-16). The gate compares the fit on the twins with the numpy path's only where two numpy fits agree. On that runner two numpy fits usually disagree: 3.5e-3 and 54 esd on #964's run, 4.0e-3 and 0.83 esd on the rerun. In the failing run the two cpd-1a fits happened to agree, so the twins' fit was gated and landed 4.6e-2 esd away. A rerun of the job passed. Two agreeing fits are luck there, not evidence that the path is deterministic. No open WP owns the bench (WP-1940 closed), so whether to change the gate is the maintainer's decision, with these numbers.

*Next.* None here. WP-1961's cut no longer waits on the wheel, only on the nightly it names. WP-1924 and WP-1520 hold the dichotomy questions this WP left open (their `### Inherited`).

### 2026-10-14 (2nd session) — two red checks on #964, neither the kernel's

The kernel this WP adds was never wrong. The check comparing the compiled derivatives with numpy measured each array against its own size. At a zero slit one array is millions of times smaller than the numbers summed into it, so rounding alone failed the check on every platform. It now measures against those numbers, with the same bar. Until rietx-kernels 1.3.0 reaches PyPI, the indexer quietly runs the numpy loop it ran before this WP, rather than advising a wheel nobody can install. Both checks are green on all five kernel platforms and every Python leg.

*Done.* `8bd93797` makes the indexer-only decline silent. CI installs `rietx-kernels` 1.2.0 from PyPI, so tutorial 03's indexing cell printed the decline's warning to stderr on the py3.14 leg. The warning advised a wheel the index cannot serve until `kernels-v1.3.0` is tagged from main. The maintainer chose silence (2026-10-14). The state ends at the floor raise, and the gotcha below ("warns once") no longer holds. `8a35e484` holds the FCJ bases to their terms. Since WP-1953 the cpd-1a fit builds ∂Ω/∂(H/L) at H/L = 0 beside S/L > 0. There the plane is up to 2.6e7 times smaller than the node terms summed into it. Divided by its own size, the kernel's gap read 4.7e-9 on darwin/arm64 and 4.9e-9 on Linux x86-64, against a 1e-13 bar. The maintainer chose (2026-10-14) to divide by the terms, in the bench and in `test_compiled_kernels.py` alike. `bench_aot_kernels.fcj_terms` computes that denominator for both, and the bar stays 1e-13. `origin/main` at `977ec2a5` failed the gate identically. WP-1953 changed `forward.py` and `fcj.py`, and neither file triggers `kernels.yml`.

*Measured.* Locally (darwin/arm64, `[dev]`, the local 1.3.0 wheel), on one kernel thread, every other plane agreed to 4e-16. The H/L plane's gap over its terms was at most 2.1e-16, one rounding. The gate reads 5.0e-16 on cpd-1a and 8.7e-16 on the trigger fit. On CI at `3b8a343e`, Linux x86-64 reads 4.1e-16 and 9.9e-16, and all five platforms pass with no call past the bar. On the unit test's model at H/L = 0 the plane is 2.3e5 times smaller than its terms. The old denominator reads 4.2e-11 there and the new one 1.8e-16, so the new case fails under the old metric.

*Tests.* `test_fcj_rows_agree_to_rounding_on_every_plane` is parametrised over H/L 0.030 and 0.0, one new id. Fast selection on `[dev]`, darwin/arm64, the local 1.3.0 wheel: 9612 passed, 186 skipped, 1 xfailed, one pass more than the entry below. CI's py3.14 leg at `3b8a343e` timed the two cases at 0.057 s and 0.042 s. `tests.added_test_times` lists none, since the test's signature changed. The full selection did not run: nothing here moves a fit's arithmetic.

*Review* (`/code-review high --fix 25d2b13f..HEAD`). Fixed in `a04b94b4`: the bench docstring quoted cpd-1a's 5.0e-16 as every plane's bound, and the trigger fit reads 8.7e-16. Declined, five. (a) The silent decline breaks root CLAUDE.md's compiled-tier rule (1), that a decline warns once and reaches `capabilities()`. The indexer-only decline never reached `capabilities()` (the first session's review, item (a)), and now it does not warn either. This is the maintainer's choice and a temporary exception: the floor raise in Next (2) ends the state, and from then on the whole-tier decline keeps the rule. (b) The unit test divides by one scalar per plane name, where the bench divides call by call. On its one-phase model the symmetric rows write zero into the axial planes, and in the other planes the terms equal the values, so nothing loosens there. Per-call comparison would redesign the test. (c) `fcj_terms` transcribes `_np_bases_fcj` with absolute values, and nothing links the two copies. Merging them would touch the numpy oracle. (d) The `aot_bench` fixture puts `examples/` and `tests/` on `sys.path`, as the existing `bench` fixture already does. (e) The test spells `_both`'s order inline, because only the compiled half takes the wrapper.

*Deliberately not generalised.* (1) `omega_fcj`, the forward and `bases_sym` keep the plane's own size as denominator. Their terms are non-negative or single, so the two denominators agree. (2) `kernels.yml` still ignores `forward.py` and `fcj.py`. Its header says the fast suite tests changes there against the published wheel. That suite's models never reached H/L = 0, so WP-1953's change met the gate only through this PR. Adding the two files as triggers costs five wheel builds on every such PR, and that trade is the maintainer's.

*Next.* (1) Merge #964, then tag `kernels-v1.3.0` on main and approve the `pypi` deployment. WP-1961's 1.9.0 cut waits on that wheel. (2) Raise `KERNEL_FLOOR` and the pin to 1.3 and move `DICHOTOMY_NAMES` into `KERNEL_NAMES`. That removes `dichotomy_kernels`' silent branch. In the same change, revise `install.md` and the 1.9.0 notes, which still say an older wheel runs the numpy loop: after the raise pip refuses one. (3) and (4) as in the entry below. The `kernels.yml` trigger question in (2) above can be answered at any point.

- **2026-10-14** — #780's monoclinic search now finds its cell, 8 s into the search where 400 s found nothing. The grid was not the real blocker. At normal load it cost 57 s, and the run then spent minutes in one grid cell lying outside the search's own domain, where nothing refused a box. This session refuses such boxes, compiles the box test into `rietx-kernels` 1.3.0, and runs the cheap prunes first. svd still never starts under a short ceiling, because dichotomy holds the ceiling until its unit completes, and its leaves are now 82 % of the cost. The maintainer chose (2026-10-14) to fold the prune in ahead of the kernel, so the bit-identity bar applies to the kernel step only.

  *Done.* `a7ba2bbb` the row-free prunes before the Q bounds (identical on all 161 705 grid boxes and the seven WP-1924 digests). `56f0cfd9` `_outside_obliquity`, refusing a box whose unclipped ρ interval lies wholly beyond ±cos 30°. `1f477f60` `kernels/src/dichotomy.rs` (`dichotomy_box_test`, `dichotomy_child_key`), `compiled.dichotomy_kernels`, the wiring in the grid, phase 2 and the centred replay, the crate at 1.3.0, and `kernels.yml` running `tests/test_indexing_kernels.py` on its wheel. Also the 1.9.0 notes, the manual's kernel section, its dichotomy chapter's obliquity equation (`eng-oblique`), and the skill's `INDEX_BUDGET_EXHAUSTED` row. Forward references: WP-1520 and WP-1924 `### Inherited`.

  *Measured* (macOS arm64, `[dev]`, CPU seconds; § Findings has the rest). Grid 57 s → 13.5 s (reorder) → 3.6-4.5 s (kernel). Starving ceiling (`tests.repro_780 N --cpu-clock`): no candidate at 7 s, the cell at 8 s; the numpy loop returns it at 120 s. Phase 2 on the kernel path: `_accept` 82 %, kernels 10 %, loop 9 %, so no whole-traversal kernel. Kernel against numpy: 788 450 boxes and 1.17 M child keys identical. Acceptance file 44 passed (18:03, the pruned numpy tree, measurements beside it). Bethanechol default mode −3, run alone (Bb, Db, E rank 1; F rank 4, +0), against the WP's −6 baseline. That baseline is Linux x86-64, so the comparison is "no worse", not a measured +3.

  *Tests.* 21 new test ids, 20 of them fast. In the engines file: `test_the_obliquity_prune_refuses_only_boxes_wholly_outside_the_domain`. In `test_compiled_kernels.py`: the indexer-only decline. In `test_indexing_kernels.py`: 15, one of them slow (the oblique monoclinic search, ~11 s). The centred-replay test also gains its compiled half (4 ids). On CI's 1.2.0 wheel, 17 of the 20 fast ids skip. They run in `kernels.yml` on every wheel a PR builds, and everywhere once 1.3.0 is published. `test_dichotomy_holds_its_frontier_as_indices_until_a_cell_is_popped` now pins the numpy path, since the kernel gathers no rows. On main merged at `0dec5232`, `[dev]`, macOS arm64, the local 1.3.0 wheel: the fast selection 9611 passed, 186 skipped, 1 xfailed (+5 on this session's earlier run, the review's five ids, with main adding no tests); the full suite 9918 passed, 195 skipped, 1 xfailed in 22:02, alone. The added fast tests cost 3.4 s locally, the largest being the five leaf-by-leaf searches (1.65 s together).

  *Review* (`/code-review high --fix`, `173f186e`, `791cb9ae`). It found no case where the kernel and numpy disagree. Fixed: an untested decline path, a panic on a zero-width `m`, per-call allocations, a wrong test-file pointer, and the manual's comparison. Taken from its skipped list: the replay test's path, and the oblique search test. Declined: (a) `capabilities()` cannot see the indexer-only decline (the floor raise in Next removes the state); (b) the rule that a kernel splits on the pool (a box is tens of µs, under `_THREAD_MIN_NS`); (c) caching `Masks` across calls (about 1 µs a call; it needs a stateful object across the boundary); (d) ρ computed twice per box (a small numpy-path cost).

  *Deliberately not generalised.* (1) `_det_interval` can still come out inverted (`det_lo > det_hi`, two valid bounds disjoint) without refusing. That is a sibling of the clip: sound to refuse, but it changes the boxes visited, and nobody has counted how often it fires after the obliquity prune. (2) The expanded determinant repeats B (the interval dependency problem). Factoring B out would tighten it, with the same caveat. (3) Contractors (HC4/ACID) and an exact matching test (Glover 1967) would prune more boxes; both change the traversal and need their own acceptance.

  *Gotchas.* `maturin develop --release -m kernels/Cargo.toml` (with `~/.cargo/bin` on PATH) replaces the venv's wheel; do not run it while a suite is collecting. Until the floor reaches 1.3, `compiled.dichotomy_kernels` declines for the indexer alone and warns once, so the model's kernels still load from 1.2.0. The worktree guard refuses a long heredoc; edit with the tools instead.

  *Next.* (1) After the merge, tag `kernels-v1.3.0` on main and approve the `pypi` deployment (`docs/RELEASING.md` § The kernel wheel). Do it soon: the maintainer wants the 1.9.0 cut to follow this merge, and WP-1961 waits for 1.3.0 on the index, since a 1.9.0 whose floor names an unpublished wheel cannot be installed (WP-1961's note, folded here 2026-10-14). (2) Then raise `KERNEL_FLOOR` and the pin to 1.3, move `DICHOTOMY_NAMES` into `KERNEL_NAMES`, tick the last task and close. (3) WP-1924's scheduling question: re-measure what corroboration a short ceiling now allows. (4) WP-1520, the leaves.

- **2026-10-13** — created from WP-1924's last task, on the maintainer's choice of compiling the grid over reordering engines. No open WP owns it: 1508 and 1940 are closed, and 1924 owns the memory and the profile, not a kernel.

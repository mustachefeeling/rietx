# WP-1924 — A monoclinic search stays inside its ceiling and its memory

Milestone: unscheduled · Status: 🔄 2026-10-13 — the frontier's memory fixed and #895 landed, acceptance and bethanechol run on the merged tree; the ceiling's scheduling remains
Track: A long run is not one fit
Depends on: 1959 (the grid compiled, this WP's last task); 1520 soft (the same units' leaf cost)
Priority: P2 2026-10-08 — a defect that fires wrongly: a declared ceiling overrun and a multi-GB peak on a clean 61-line monoclinic pattern, with the workaround of capping the volume and the systems by hand; the reporter's 9 GB and 25.8 GB are the reason it is not P3

## Goal

A monoclinic search of a clean pattern for a V ≈ 224 Å³ cell finishes inside a stated time and memory bound on a laptop. A declared `total_budget_seconds` holds to within one unit's slice, and the peak resident set is a number the docs state per engine.

## Context

**Issue #780 (mustachefeeling, 2026-10-06, Linux x86 WSL2, 1.7.0.dev0).** Synthetic lab pattern, 62 usable lines, V = 224 Å³, `SearchSpec(systems=("monoclinic",), max_volume=600, budget_seconds=900)`, `preset="full"`. `dichotomy` and `trial_error` report `INDEX_SEARCH_INCOMPLETE` at 900 s, only `svd` finds the lattice, wall 1967 s, peak RSS 9.0 GB. A second dataset (≈5300 Å³ hexagonal, private) reached 25.8 GB at 31 min.

**Measured on 2026-10-08** (5d1f5f67, `[dev]`, macOS arm64, numba on; `scratchpad` scripts `repro-780.py`, `mem-780.py`). Synthetic P 1 2/m 1, a = 4.541, b = 4.884, c = 10.198 Å, β = 98.22° (V = 224 Å³), 61 lines to 55° 2θ, `systems=("monoclinic",)`, `max_volume=600`, `preset="full"`, `validate=False`, ceilings 15-120 s. The slice cannot show the 900 s behaviour. It shows the shape:

| engine | ceiling | wall | peak RSS |
|---|---|---|---|
| dichotomy | 15 s | 16 s | 2.4 GB |
| dichotomy | 30 s | 32 s | 2.1 GB |
| dichotomy | 60 s | not recorded | 1.9 GB |
| trial_error | 60 s | 41 s | 0.44 GB |
| svd | 15 s | 19 s | 0.22 GB |
| svd | 30 s | 32 s | 0.28 GB |
| svd | 45 s | 56 s | 1.9 GB |
| svd | 60 s | 110 s, then 38 s | 2.5 GB, then 0.66 GB |
| all three | 120 s | 108 s | 2.6 GB |

Dichotomy reaches about 2 GB inside 15 s and then holds: a fast allocation, not growth with time. svd's peak varies by 4× between two runs of one setting and overran its ceiling by 50 s once and 11 s once. All three engines still return the lattice's reduced cell as candidate 0 (svd alone at 60 s) with `INDEX_SEARCH_INCOMPLETE` on dichotomy and trial_error. `tracemalloc` slows the run so far that the peak does not appear (200 MB traced, 0.5 GB RSS), so use RSS and a sampling profiler, not `tracemalloc`.

Not yet established: what dichotomy holds at 2 GB; whether the 9 GB is that allocation scaling with the 900 s budget or the candidate harvest `dedup_groups` describes (thousands of raw candidates per unit); whether svd's overrun is search, post-processing (supercell checks, Bravais opinion) or a deadline read at too coarse a boundary. The reporter's claim that published dichotomy implementations take seconds (Boultif & Louër 2004) is for a different algorithm's box budget and is not evidence about this one. `indexing/CLAUDE.md` already says the package is silent rather than slow, and "buy responsiveness with ordering and reporting, never by shrinking the box".

**The table predates WP-1940** (2026-10-10, PR #864). The dichotomy traversal now runs on numpy alone, its numba twin deleted. On WP-1508's synthetic monoclinic list the numpy loop takes about 200 s where the compiled one took 10 s, so a box-bound monoclinic search spends far more of its ceiling in the traversal. Re-measure before building on the table. A compiled port would go into the `rietx-kernels` crate, held to the numpy loop leaf by leaf (`indexing/CLAUDE.md`).

**Issue #895 (2026-10-11): Stop waits up to about 5 s a candidate in the ambiguity sweep.** It is one form of "a deadline read at too coarse a boundary". Checked at `d80ca5f4` and again at `e1d19359`: `consensus.enumerate_ambiguity` reads `cancel` once per candidate, and `cancel` is the run's `Deadline`, which wraps the caller's token (`workflow.py`). The work between reads is `ambiguity.ambiguity_partners`, a loop over 55 `derivative_cells` with `predicted_lines` per child, and it takes no `cancel`. Measured on synthetic 40-line lists (Cu Kα, `[dev]`, macOS arm64): one candidate's sweep takes 0.19 s cubic, 1.5 s tetragonal, 3.0 s orthorhombic and 3.8-4.9 s monoclinic or triclinic. The slowest single child is 8-233 ms. `consensus.supercell_checks` takes no `cancel` at all. A read per derivative cell bounds the wait at the slowest child, and `Deadline.expired` is a monotonic-clock read. One rule: a sweep the token stops leaves its candidate out of `ambiguity_checked` and returns no partial list, since an empty list reads as "no partners", a clean answer. No test called `enumerate_ambiguity` directly before this WP.

### Profile (2026-10-12)

Measured at `e1d19359`, `[dev]`, macOS arm64, on a machine shared with five other sessions at load 110-180. Memory is the process's physical footprint, sampled every 20 s and read as its lifetime peak (`proc_pid_rusage`), with each phase boundary logged. macOS leaves compressed pages out of the resident set, so under this load the resident set read 57 MB while the footprint read 1.9 GB. Every clock below is CPU seconds, because the load gave a run about a fifth of a core. `tests/repro_780.py` rebuilds the case; `--cpu-clock` counts its ceiling the same way.

**Dichotomy.** The allocation was phase 2's setup in `_search_one` (`dichotomy.py:995` at `e1d19359`). It gathered every survivor list's rows at once, `n_dof` floats an index, into a dict held until the unit returned. The lists come from the grid's last stage (`_grid_pass`, `:797`). Each surviving box there keeps its own int64 list, shared only by its few children. On #780's case the grid ends after 161 705 boxes and 157 s of CPU, with 273 871 cells, 22 689 lists and 165 million indices. That is 1.29 GB of lists and 5.2 GB of gathered rows. The footprint climbed from 1.9 GB to 6.79 GB in the two minutes after the grid finished, and held there. The size is the index count times 8 + 8·`n_dof` bytes. The index count grows with the grid: steeply with `max_d_axis`, and with `max_volume` until the axis bounds cap the volume. Over d ∈ [3, 11] Å it is 0.63 M at 150 Å³, 2.1 M at 300 Å³, 3.6 M at 600 Å³ and 4.1 M at 1200 Å³. At 600 Å³ it is 12.6 M to 14 Å and 26.5 M to 17 Å. The grid's own CPU over those domains, one run each at load 110-180: 0.7, 1.2, 1.4 and 1.5 s by volume, and 1.4, 5.5 and 13.9 s by axis bound. The budget does not enter: a unit that finishes its grid holds the allocation whatever its ceiling.

**svd.** Neither the 0.2-2.5 GB spread nor the 11-50 s overrun reproduces. At 120 s of CPU svd made 11 200 calls, kept 53 candidates and peaked at 0.26 GB. Its unit overran its slice by 0.2 s, one block of 200 trials between clock reads. Ranking took 0.2 s, consensus 0.1 s and the supercell checks 0.1 s. The 2026-10-08 runs had numba on, and nothing measured here says what moved them.

**The ceiling holds, and it starves the engine that finds the cell.** Since WP-1940 the grid alone costs 157 s of CPU on this case. Dichotomy runs first in each system, so under any ceiling below that it takes the whole run. At 120 s of CPU it reached 131 912 boxes, and svd and trial_error never started. The run returned no candidate. svd alone finds the lattice in 27 s of CPU. This is a scheduling question, left as the last task.

## Non-goals

- Shrinking the metric box to buy speed (`indexing/CLAUDE.md`).
- The leaf cost of `refine_candidate` (WP-1520, gated on a count).
- The reporting of the candidate's setting (the 779 WP).

## Tasks

- [x] Profile one dichotomy unit for memory with a sampling tool, not `tracemalloc`, on the monoclinic fixture above. Name the allocation, its size as a function of box count and of `max_volume`, and whether it is released.
- [x] Do the same for svd's 0.2-2.5 GB spread, and find where the 11-50 s past the ceiling is spent.
- [x] Fix what the profile names, keeping every finished search bit-identical (`python -m tests.unit_replay`, digests per platform; 1519's harness).
- [x] #895: read `cancel` at the child boundary in `ambiguity_partners` and `supercell_checks`, with a test that a cancelled token stops a sweep within one child's work and leaves the candidate unchecked. Done for `ambiguity_partners`. `supercell_checks` keeps no token: it runs over the reported list (≤ 12 candidates), 10-16 ms of CPU a pair, 0.1 s on #780's run, and the gate has no unasked state for it (2026-10-12 handover).
- [x] Add a peak-RSS figure to `estimate_ceiling` or to the result's budget diagnostic if the profile shows it is predictable from the spec, so a caller can see it before a run. Not added: the frontier's size is the number of grid boxes the lines let survive, which only running the grid shows. The spec bounds it only through `MAX_GRID_CELLS` and the search set's size, a ceiling of gigabytes that would mislead more than help. After the fix #780's case peaks at 0.72 GB (2026-10-12 handover).
- [x] Tests: a bounded-memory guard that fails on the allocation, declared with its measured spread (a pass margin under 10× is a load sensor). Quote platform and extras with every count.
- [ ] Scheduling: under a whole-run ceiling shorter than dichotomy's grid, svd and trial_error never start and the run returns nothing (§ Profile). Decide how the scheduler draws a unit's share of the ceiling, or which engine opens a system, and keep finished searches bit-identical. *Decided 2026-10-13 by the maintainer:* compile the grid again rather than reorder engines; the work is WP-1959, and this box ticks when it lands.
- [x] Skill: the indexing reference row for a monoclinic or hexagonal search with a large volume bound (cap the volume, search one system at a time, read `INDEX_SEARCH_INCOMPLETE` per engine), tagged Measured or Hypothesis.

## Acceptance

```sh
.venv/bin/python -m tests.repro_780 120         # peak memory and wall within the stated bound
.venv/bin/python -m pytest tests/test_indexing_scheduler.py tests/test_indexing_engines.py -n auto --dist loadgroup
.venv/bin/python -m pytest tests/test_acceptance_indexing.py -n auto --dist loadgroup
.venv/bin/python -m ruff check src tests examples
```

## References

- Boultif & Louër (2004), *J. Appl. Cryst.* 37, 724 (DICVOL04).
- WP-1508, WP-1509, WP-1519 (the unit replay harness), WP-1520.

## Handover log

### 2026-10-13 (2nd session) — the handoff's checks run on the merged tree: acceptance green, bethanechol unmoved

The checks the handoff left for this PR all came back clean. Current `main` merges in without a conflict, CI is green on the merged head, and the indexing acceptance passes on it. The bethanechol benchmark, run alone on an idle machine, matches its last record in manual mode set for set. It misses set F in default mode, but `main` misses it identically on the same machine, so the miss belongs to the search budget and not to this branch. What stays open is the scheduling task, which waits on the maintainer's choice of fairness rule.

*Done.* Merged `origin/main` (`f5ffc23`) into the branch as `ed4e9a9`, with no conflict to resolve and the WP index unchanged by `wp_index.py`. No code was written this session, and no checklist item landed. The scheduling task stays open.

*Measured* (`[dev]` with the `rietx_kernels` wheel, no jax or torch, Linux x86_64, 4 cores, a cloud container with nothing else running, load 1.3-2.1):
- CI on `ed4e9a9`: lint, fast py3.11 1-2/2, py3.14 1-2/2, jax 1-2/2 and `ci-ok` all passed (15:56-16:11 UTC). `docs` was skipped, as on the previous head.
- `ruff check src tests examples` clean. `test_docs_consistency.py` with `test_indexing_consensus.py`: 67 passed in 200 s.
- `main` moved again during the handover (`6e2f9a8`, #961, TOF). Its indexing changes are `require_two_theta` entry guards in `extinction.py`, `peaks.py`, `pick.py` and `workflow.py`, and the last of those auto-merged beside this branch's edit. On that final merged tree, `test_docs_consistency.py`, `test_indexing_scheduler.py`, `test_indexing_engines.py` and `test_indexing_consensus.py` ran 167 passed in 6:54, and ruff is clean. The acceptance file and the benchmark below ran on the `ed4e9a9` tree and were not repeated on this one.
- `tests/test_acceptance_indexing.py` on the merged tree: 44 passed, 0 skipped, 24:27 wall. This is the rerun the handoff asked for after finding 1. The macOS run before the review fixes was 41 passed and 3 skipped. Which three skip on macOS was not checked.
- `python -m tests.bethanechol_benchmark` on the merged tree, run alone: **global −9** over 20 runs (ceiling +8), **manual −3**, **default −6**. Manual matches WP-1518's 2026-09-28 record set for set: Bb, E and F at rank 1, Db at rank 2. Default finds Bb and E at rank 1 and misses the other eight; of those, only Db and F are reachable. One set took 96-111 s in manual mode and 278-565 s in default.
- Default F, the one reachable set that missed in default mode, run on its own on both trees. `main` (`f5ffc23`) took 561.7 s and the branch 528.9 and 539.8 s. All three missed in the same way: the nearest candidate is the same wrong P orthorhombic cell (7.103, 8.2435, 17.2079 Å) at rank 11, 71 160 ppm off, and orthorhombic, monoclinic and triclinic report `search_complete=False`. The budget runs out before monoclinic finishes, and the branch changes none of it.

*Not done.* `/code-review` was not run again. This session wrote no code, and the merge needed no resolution. The branch's diff had already been through `high --fix` (`282ac1cd`) and `medium`, which found seven issues, all fixed. The full suite was not run: the change replays bit-identically, and CI's fast matrix plus the acceptance file both ran on the merged tree.

*Gotchas.* The Aa default run printed `RuntimeWarning: invalid value encountered in matmul` at `indexing/qspace.py:410` (`cov_af = basis.T @ cov… @ basis`). That module is not in this branch's diff, and the F runs on `main` did not print it. Aa on `main` was not run, so whether `main` prints it too is open. The benchmark's per-run budget is wall clock, so a default-mode score is a statement about the machine. Compare one with a baseline from the same box, as done for F above.

*Next.* (1) The scheduling task: pick between the cheapest engine opening each system and a `rietx-kernels` port of the grid's box test (the previous entry sets out both). The default-mode bethanechol misses above are budget-bound in the same way, so whichever lands should rerun default mode against the −6 above on the same class of machine. (2) Post the #780 and #895 replies; #780 stays open until (1) lands. (3) Once (1) lands, the WP can close.

### 2026-10-13 — the frontier's memory fixed, Stop inside the ambiguity sweep, and a ceiling that starves svd

A monoclinic search no longer needs gigabytes. #780's multi-GB peaks came from one step: once dichotomy's grid finished, phase 2 copied the rows of every surviving grid cell at once and kept them until the search ended. On the issue's 224 Å³ case that was 6.8 GB. The same search now holds about 0.6 GB, and every finished search returns the same candidates bit for bit. Stop now takes effect within one derivative cell of the ambiguity sweep (#895). The profile also found a defect the WP did not know about. Since the dichotomy traversal lost numba, its grid alone costs 157 s of CPU on this case, so a whole-run ceiling shorter than that ends before svd starts and returns nothing, although svd alone finds the cell in 27 s.

*Done.* Tasks 1-6 and #895 are ticked; the scheduling task is new and open. The profile is in § Context. `tests/repro_780.py` rebuilds the case: its peak is the physical footprint on macOS, and `--cpu-clock` counts a ceiling in CPU seconds. Dichotomy now gathers a grid cell's rows when it pops the cell and keeps the survivor lists in the narrowest unsigned type (`_row_index_type`, uint16 here). `ambiguity_partners(cancel=)` reads the token before each derivative cell and returns `None` when stopped; `enumerate_ambiguity` then leaves the candidate out of `ambiguity_checked`. `supercell_checks` keeps no token, because it runs over at most the 12 reported candidates (10-16 ms of CPU a pair, 0.1 s on #780's run) and the gate has no unasked state for it. Task 4 adds no figure: the frontier's size is the number of grid boxes the lines let survive, which only the grid shows. The skill's `INDEX_BUDGET_EXHAUSTED` row (`references/abstention.md`) says to read `engines_run` and gives the large-volume advice. `tests/CLAUDE.md` gained the rule that memory on macOS is the footprint. `/code-review high --fix` found no correctness bug and landed four fixes in `282ac1cd`: the grid's gather cache is released before phase 2, the guard traces phase 2 alone (15 s to 5 s), and two comments described the old sweep. It declined two: one gather per cell is the intended trade, and the guard's "about a second of grid" was measured at lower load.

*Measured* (`[dev]`, with memray and py-spy installed into the venv by hand by `uv pip install memray py-spy` and used for no figure here, macOS arm64, a machine at load 70-225 for the whole session, so CPU seconds wherever a clock matters):
- #780's case, dichotomy alone. Before: 6.79 GB of footprint once the grid finished, held. After: 0.72 GB peak at 300 s of CPU, 0.58-0.61 GB through phase 2 (1.34 M boxes, no candidate yet).
- Seven dichotomy units replay to their digests, macOS arm64: brucite hexagonal `af186da4` and trigonal `ceb84493`, corundum cubic `e3b0c442`, hexagonal `05aa58a2`, trigonal `2907adc0` and tetragonal `6471da88`, synthmono `30473892`.
- The per-cell gather's CPU, two runs each beside each other: synthmono 203.0-219.1 s before, 211.6-225.3 s after; corundum trigonal 180.0-185.4 s before, 183.6-190.3 s after.
- The acceptance repro at 120 s of wall, two runs: 129.0-129.2 s of wall at load 151-172, 14.0-14.7 s of CPU, 0.22-0.23 GB, no candidate. All engines at 120 s of CPU: 131 912 boxes, svd never started, 0.34 GB. svd alone at 120 s of CPU: 11 200 calls, 53 kept, 0.26 GB, 0.2 s over its slice; at 27 s of CPU it had the lattice first.
- One ambiguity sweep on #780's cell: 0.87 s of CPU over 55 children, the slowest child's lines 47 ms.
- Fast selection, two runs at load 3-150 taking 19-38 min: before merging main 9306 passed, 181 skipped, 3 xfailed and 1 failed; after the review fixes, on main merged in, 9343 passed, 181 skipped, 1 xfailed. The one failure was `test_three_cells_a_side_build_in_no_more_than_a_moment`, a timing row that passes alone. The three added tests cost 2.94, 2.65 and 1.54 s locally (junit, `tests.added_test_times`).
- `tests/test_acceptance_indexing.py` before the review fixes: 41 passed, 3 skipped, at load ~120. `test_indexing_scheduler.py` and `test_indexing_engines.py` with the consensus and kernel files: 143 passed, 1 skipped, and the two slow monoclinic recovery rows failed on `search_complete` at load 225. Run alone they passed. trial_error's row is code this branch does not touch.

*Not run.* `tests.bethanechol_benchmark`: an hour of wall that must run alone, and this machine was shared all session. The full suite: the change is bit-identical by replay, and the indexing acceptance ran on its own.

*Gotchas.* Under this machine's load the resident set read 57 MB against 1.9 GB of footprint, so read memory through `memory_bytes`. A wall ceiling under load searches less and peaks lower, so compare peaks with `--cpu-clock`. The 2026-10-08 svd spread and overrun do not reproduce, and nothing measured here says what moved them.

*Handoff (2026-10-13).* A `/code-review medium` pass on #930 returned seven findings, quoted here as the coordinator sent them:
1. "`src/rietx/indexing/consensus.py:574` `_partners` turns a refused sweep (ValueError/RuntimeError/LinAlgError) into `[]`, and `enumerate_ambiguity` then appends the candidate to `ambiguity_checked`, so a sweep that never ran grades as 'asked, no partners' and the gate can still say 'high'." Fixed in `2307968e`: a refusal returns `None` and the loop moves on; `test_a_candidate_whose_sweep_refuses_stays_unasked` fails on the old code with `[0, 1]` against `[1]`.
2. "`tests/repro_780.py:49` `peaks()` and `WAVELENGTH` re-implement `tests.test_indexing_engines.synthetic_peaks(system, sg=, cell=, two_theta_max=)` and its `LAM`." Fixed in `0d886f05`; the list is bit-identical to the old one.
3. "`docs/skill/rietx/references/abstention.md:38` ... claims 'the grid cost 10× more CPU at 17 Å than at 11 Å', which the WP records nowhere." Fixed in `8a8f3659` by recording the numbers in § Profile, tag kept Measured: the grid's CPU at d ∈ [3, 11] Å was 0.7, 1.2, 1.4 and 1.5 s at 150, 300, 600 and 1200 Å³, and at 600 Å³ 1.4, 5.5 and 13.9 s to 11, 14 and 17 Å (one run each, load 110-180). The skill text is unchanged, so its copies need no re-sync.
4. "WP file lines 87-94: wall-clock times quoted as single figures ... quote as ranges with the load." Fixed in `8a8f3659`.
5. "`tests/repro_780.py:156` `cpu_clock()` replaces the whole `time` module inside `engines` with a namespace exposing only `monotonic`." Fixed in `0d886f05`: a module subclass forwards every name and overrides `monotonic`.
6. "`tests/repro_780.py:194` `os.getloadavg()` does not exist on Windows." Fixed in `0d886f05`; it prints `n/a`.
7. "WP handover line 87 and the PR body say '[dev] with memray and py-spy added as dev tooling' but pyproject.toml is unchanged." Fixed in the WP (`8a8f3659`) and in the PR body with this handoff. No `[profile]` extra was added.

Pending at handoff. The indexing acceptance rerun on the fixed tree was still running, because finding 1 changes what the gate reads. Run it first: `.venv/bin/python -m pytest tests/test_acceptance_indexing.py -n auto --dist loadgroup`. Then confirm CI with `gh run list --branch wp1924-monoclinic-ceiling`. The touched files pass: `test_indexing_consensus.py`, the frontier guard, `test_portability.py` and `test_docs_consistency.py`, 82 passed (`[dev]`, macOS arm64). `tests.bethanechol_benchmark` is still unrun and must run alone before the WP closes.

*Next.* (1) The scheduling task. Two answers, and the maintainer's view of the ceiling's fairness rule decides between them. One lets the cheapest engine open each system: results merge in registry order, so finished searches stay bit-identical, but the streamed order and `INDEX_BUDGET_EXHAUSTED`'s wording need checking. The other ports the grid's box test into `rietx-kernels`, held to the numpy loop leaf by leaf. It recovers the grid's speed and shrinks the window in which a ceiling starves svd, without removing it. (2) Run `python -m tests.bethanechol_benchmark` alone before the WP closes. (3) Post the #780 and #895 replies drafted in the session report.

- **2026-10-08** — created, from the 2026-10-08 issue triage (issue #780). Checked against the tree at 5d1f5f67: `git log --since=2026-10-06 -- src/rietx/indexing` shows only #726, #747 and WP-1545 work, none on memory or the deadline; no PR cites #780. Reproduced as a bounded slice only (ceilings 15-120 s; the 900 s run and the 9 GB were not attempted): dichotomy 1.9-2.4 GB inside 15 s, svd up to 2.5 GB and past its ceiling by 11-50 s. No open WP owns it: 1520 is the leaf cost of `refine_candidate` and gated on a count, 1334 and 1335 are refinement stages and reports, 1508 is closed (the traversal compiled, memory never measured).

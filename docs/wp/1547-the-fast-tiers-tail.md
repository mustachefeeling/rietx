# WP-1547 — the fast tier's tail is cut back, and its report reads CI's seconds

Milestone: unscheduled · Status: 🔄 2026-10-09 — five of six tasks landed (PR #857); the ten-run re-measure waits for the merge
Track: The repo's own process
Depends on: —
Priority: P2 2026-10-09 — a cost item with the maintainer at the wall: every code PR waits 32-37 min, and the median leg rose 43 % in one week

## Goal

A readied code PR's fast legs finish in about 20 minutes again, with no
assertion lost: a test leaving the fast tier runs in the nightly. The handover
report on added tests shows what they cost on CI, so the next 5-minute file is
seen before it merges.

## Context

**The symptom.** Weekly median wall clock of main's successful CI runs
(`gh run list --workflow ci.yml --branch main --event push --status success`):

| ISO week | 38 | 39 | 40 | 41 |
|---|---|---|---|---|
| Median min | 16.3 | 20.6 | 24.1 | 35.7 |

A run waits for the slowest of five legs (py3.11-3.14 and jax). Legs of one
run differ by up to 1.6× on the same tree (run 37966391017: py3.13 19.4 min,
py3.12 30.6, jax 36.0), so the run usually draws a slow runner.

**The suite is a normal size.** Counted 2026-10-09 with one script over each
project's HEAD tarball, lines of code excluding blanks, comments and
docstrings:

| Project | Source kLOC | Test kLOC | Test/source | Test functions per source kLOC |
|---|---|---|---|---|
| rietx | 72.5 | 96.7 | 1.33 | 81 |
| astropy | 104.7 | 134.6 | 1.29 | 83 |
| scikit-learn | 82.8 | 121.7 | 1.47 | 66 |
| scipy | 120.7 | 176.4 | 1.46 | 99 |
| lmfit | 4.5 | 6.1 | 1.34 | 85 |

Test code has tracked source at about 1.1× (raw lines) since August. The
codebase grew from 38k raw source lines on 2026-08-01 to 150k on main
1007c9bf, so the count grew with it. The time grew faster than the count.

**Where the time went.** Three main runs whose junit artifacts survive:
36362163974 (2026-09-28), 37100295315 (10-03), 37978210348 (10-09). Each
file's time is divided by its leg's parallelism (test-time over the pytest
step's wall), which cancels the worker change below. Medians of the four
Python legs:

| Snapshot | Tests | Leg wall (min) | Tests over 10 s (wall-min) |
|---|---|---|---|
| 09-28 | 6800 | 20.1 | 12.7 |
| 10-03 | 8219 | 21.7 | 11.9 |
| 10-09 | 9116 | 31.1 | 17.9 |

From 10-03 to 10-09, new files added 7.1 wall-min a leg and existing files
2.0. Three files are 8.1 of the 9.4:

- `test_lebail_alternation.py` (WP-1323, merged 10-02): +5.0. Twelve tests,
  each fitting the 11-BM LaB6 + cBN pattern over 5.1-50° from scratch. Only
  the pattern is a module fixture. Two pairs repeat a fit exactly:
  `_refinement(1.0)` at `_plan(3)` in the history-less marking test and the
  cap-recording test, and `_refinement(1.003)` at `_plan(4)` with telemetry
  in the run-directory test and the pass-ending test.
- `test_magnetic_isotropy.py`: +1.8. It moved −0.7 the week before, so part
  of this is runner noise. Why `isotropy.analyse` is slow is WP-1418's.
- `test_tutorials.py` (WP-1545): +1.3. It executes 23 notebook cases on every
  leg.

The tail's named members from WP-1506 still stand: the 230-group and
every-setting sweeps (`test_the_sweep_over_the_230_settings_at_gamma`, three
230-group tests in `test_magnetic_irreps.py`,
`test_symmetry_orbits.py::test_the_invariant_holds_across_every_setting_gemmi_knows`).
A sample of them could stay fast with the whole sweep nightly. Choose the
sample by trap, never at random: 79 of gemmi's 564 settings were once served
wrong under a correct count (root CLAUDE.md, cell ties). A break in an
unsampled setting would then show the next morning, and the WP states that
trade.

**The report went quiet by a factor of 3-4.** tests/CLAUDE.md § Budgets in
tests makes the fast tier's guard a report (`tests/added_test_times.py`), read
at handover. It fired for the Le Bail tests. WP-1323's handover quoted
18.4-30.7 s for its four slowest, from a local run on a 10-core Mac, and kept
them fast as the only real-pattern cover of the loop. On 2026-10-09's CI legs
the same file's four slowest took 56-131 s each. The report also judges each
test alone, so twelve 1-2 minute tests were never seen as one 5-minute file.
The report stays a report: a failing per-test ceiling would be the timer the
budgets section forbids.

**Two physical cores, so the worker count is not a lever.** GitHub's 4-vCPU
Linux runner has 2 physical cores. `pytest -n auto` counts physical cores
whenever `psutil` imports (xdist's `pytest_xdist_auto_num_workers`), and
`psutil` entered `[dev]` through ipykernel when PR #810 (WP-1544's `notebooks`
extra) merged on 2026-10-07. Test-time over wall fell from 3.84-3.88 to
1.95-1.96 on every leg. Leg wall clock did not move: 29/33/25/29 min on
565e8f1d, the run before, and 28/28/20/32 on 57aa2c1f, the merge. Four
hyperthreaded workers had each run at about half speed. So `-n logical` is
not a fix. One side effect matters here: per-test seconds in junit halved on
10-07, so compare junit across that date only after the division above.

**Sharding constraints (from WP-1506).** Sharding must keep each
`xdist_group` whole. GitHub Free allows 20 concurrent jobs, so five legs
times N shards meets the limit when two PRs are readied together. Sharding
probably comes with a smaller PR matrix (oldest and newest Python per PR, the
middle two nightly). Larger runners need a paid organization plan (1506's
"Considered and not taken").

**For scale.** SciPy's fast Linux jobs take 3-14 min including a C build, and
several run `--timeout=60` per test (`.github/workflows/linux.yml`,
2026-10-09). That is a runaway cap at 60 s, which this repo would read as a
load sensor. The comparison shows the size of their tail, and it is not a
mechanism to copy.

**This is WP-1506's task 7.** 1506's last open item was "from two weeks of
junit timings, choose the next cut". The timings it waited for are the three
snapshots above, and its candidates are the sweeps, sharding and a smaller PR
matrix, all carried here.

**If the nightly is reshaped, take the probe line with it** (WP-1519's note,
carried from 1506 at its close). Each nightly "Record the environment" step
(`full`, `windows`, `macos`) pastes the same line printing
`row_local_product` and `stacked_pinv_exact`. Those two indexing probes pick
an exact slower path on a platform whose BLAS or LAPACK fails them. The
nightly runs at `-q` without `-rs`, so these lines are the only record of
which path each OS took. A third probe or a rename needs three identical
edits, and a missed one drops that platform's answer silently. A YAML anchor
or one script every leg calls would fix it. It is low stakes, and in scope
only if the last task moves Python versions into the nightly.

## Non-goals

- Why `isotropy.analyse` is slow: WP-1418.
- The nightly's length.
- The docs-only skip and `ci-ok`: WP-1506, live since 2026-09-27.
- The worker count. Measured above, it buys nothing on this runner.

## Tasks

- [x] `test_lebail_alternation.py`: share the two repeated fits through
      module fixtures, and measure whether a narrower 2θ window keeps the
      three shapes the module docstring names (pass 2 worse at exact cells,
      convergence at +0.3 %, no settling at +2 %). Every quoted Rwp is the
      hand loop's at 5.1-50°, so a narrower window re-measures each one. A
      test that still costs over about 30 s on CI says in its docstring why
      it is fast, or moves to `slow`.
- [x] The sweeps: a trap-chosen sample in the fast tier, the whole sweep
      marked `slow`. The commit names the sample and the trap each member
      covers.
- [x] `test_tutorials.py`: run it on one Python leg, or nightly. The
      decision states what a notebook could break on one Python version and
      not another.
- [x] `tests/added_test_times.py`: add a per-file total for the added tests,
      and let `/wp-handover` read the PR's CI `junit-py3.13` artifact when
      one exists, falling back to the local file. tests/CLAUDE.md § Budgets
      in tests gains one clause: local seconds understate CI by 3-4×.
- [ ] Re-measure ten main runs after the above. If the median Python leg is
      still over about 20 min, shard by recorded junit time with groups kept
      whole, and trim the PR matrix to the oldest and newest Python, with
      the middle two in the nightly.
- [x] `ci.yml`'s header: one line saying `-n auto` is 2 workers on this
      runner, and that `-n logical` was measured to buy nothing (this WP).
- [x] Skill: none. This changes how the repo is tested, not how rietx is
      driven.

## Acceptance

- Over ten consecutive successful main runs after the last task lands, the
  median of the four Python legs' "Fast suite" step is 20 min or under.
- Every test that left the fast tier passes once in the nightly's `full` job.
- Fast passed+skipped moves by exactly the tests added minus those marked
  `slow`, quoted with venv and platform.

```sh
gh run list --workflow ci.yml --branch main --event push --status success --limit 10 --json databaseId
gh run view <id> --json jobs   # each "fast py3.x" job's "Fast suite" step
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m pytest -n auto --dist loadgroup -m slow tests/test_lebail_alternation.py tests/test_magnetic_irreps.py
```

## References

- pytest-xdist 3.8, `xdist/plugin.py` `pytest_xdist_auto_num_workers`
  (physical cores when `psutil` imports; `-n logical` for logical).
- SciPy `.github/workflows/linux.yml` (fast jobs, `--timeout=60`).
- Runs 36362163974, 37100295315, 37966391017, 37978210348; PR #810.

## Handover log

### 2026-10-09 (2nd session) — the tail cut lands; the ten-run re-measure waits for the merge

The fast tier's three named costs are cut, and no assertion was lost. The
Le Bail tests now fit under half the angular range and share their fits. All
three behaviours they pin still appear there, at the same starting cells. The
space-group sweeps run a 23-group sample, chosen by trap, on every push. The
whole sweeps run nightly. The tutorials execute on one Python leg instead of
five. Whether this brings a leg back to about 20 minutes is not yet known.
Ten main runs after the merge decide it, and they decide whether sharding is
needed.

**Done** (PR #857, branch `wp1547-fast-tier-cut`, cut fresh from main because
the filing PR #856 had merged):

- Le Bail: `LIMITS` is 5.1-25°. +0.3 % keeps pass 1 (13.845, then 13.865),
  +0.4 % converges over five passes, and +2 % never settles. The slow test
  keeps 5.1-50° (`WIDE_LIMITS`), since its pins were checked on Linux in
  #849. Three module fixtures (`exact`, `worse`, `converging`) share fits,
  each in its own `xdist_group`. History, a run directory and an event
  callback each left the fit bit-identical (Rwp and every parameter, at
  +0.3 % and +0.4 %), so sharing is honest. The converging test accepts pass
  4 or 5 as kept, because at 25° the two are level within
  `LEBAIL_CONVERGED_REL`.
- Sweeps: `tests/space_group_sample.py` holds 23 groups, each named with its
  trap. Six sweeps take `[sample]` fast and `[all-230]`/`[all-564]` slow.
  The real-amplitude count joined the five the WP named: same shape, 41.7 s
  on CI. A new test asserts that the sample covers all 16 (system, centring)
  pairs.
- Tutorials: the py3.14 leg executes them, through a matrix `include`. The
  other legs skip through `RIETX_TUTORIALS=skip`. The trade is stated in
  `test_tutorials.py`'s docstring.
- `added_test_times.py` prints per-file totals and leaves skipped cases out.
  `/wp-handover` step 7 reads CI's `junit-py3.14` when the branch has one.
  `tests/CLAUDE.md` gained the 3-4× clause and stays at its 302-line cap.
- `ci.yml`'s header records that `-n auto` means 2 workers here.
- `/code-review high --fix` made six fixes, committed as one, listed in its
  commit. Declined: renaming the sweep tests. Their ids say which case ran,
  and a rename would move every id this WP quotes.
- Forward references: WP-1418 (sampled magnetic sweeps), WP-1545 (tutorials
  on one leg).

**Measured:**

- Probe fits at the old and new window, run beside each other on a loaded
  machine: +0.3 % took 10.6 s at 50° and 2.7 s at 25°; +0.4 % took 23.1 s
  and 4.4 s. Starts of +0.6 % and above diverge at 25°. A worse-pass start
  holds from +0.30 % to +0.52 %.
- Base run 37988294011 (deed30b5, py3.12 leg): the Le Bail file cost 1076 s
  of test time, not the 590 s of run 37978210348. #849 sits between them.
  The six sweeps cost 156 s and the tutorials 119 s.
- This branch's fast run, `[dev]`, macOS arm64, Python 3.12, load average
  33-47: Le Bail about 31 s of test time; the samples 2-16 s each.
  The two added tests read 0.00 s each, per file too.
- Count: fast passed+skipped 9148 (8975 passed, 172 skipped, 1 xfailed)
  against 9146 at the base (CI py3.12 junit). That is exactly the two added
  tests. The seven `all-*` cases are `slow`, so the full selection moves by
  +9. The full suite was not run: the change is test-only. Every slow case
  it added or touched passed locally: the seven sweeps and the Le Bail wander.

**Gotchas:**

- The worse-pass margin at 25° is 0.020 points of Rwp. Linux and macOS
  disagreed by 0.015 on the discarded pass at 50°. It held on all five legs
  of run 37992022325, the first Linux reading at 25°.
- `tests/CLAUDE.md` sits at its cap; a clause added there pays with a cut.
- **+0.4 % sits on an edge at 25°.** Under PR #855's step for `u` and `v`
  (WP-1936) it comes back worse on pass 2 instead of converging. So the
  converging fixture and the cap test start at −0.15 %, which converges on
  macOS with and without #855. All 13 Le Bail tests pass there on both trees.
  #855 still conflicts in this file as text. Whichever merges second takes
  this branch's version of it.
- **A converging run's pass count is a platform reading.** At −0.15 % on
  main, macOS took five passes to 13.932 and Linux six to 13.905 (run
  37996829339): the paths split at pass 3. #855's own pin at 50° failed on
  its Linux legs the same way, pass 5 against its macOS pass 6. So the
  converging test asserts the shape: at least four passes, each lower than
  the last until a level one, the kept pass last or second-last. Its Rwp
  bar is 1e-3, for a measured spread of 2.7e-4. A test that pins which pass
  a converging alternation stops on senses the platform.
- PR #853 (WP-1418, `isotropy.py`) merges cleanly. The isotropy sweeps, sample
  and full, passed on the merge, so the 140-candidate pin holds.

**CI, run 37992022325** (f16953c7, one run each, so a direction rather
than a measurement; legs on one tree differ by up to 1.6×):

- "Fast suite" step, py3.11/3.12/3.13/3.14 and jax: 30.7, 26.4, 25.0,
  26.1 and 18.9 min. Base run 37988294011: 39.8 (cancelled), 30.8, 35.1,
  28.2 and 35.5. The median Python leg fell from about 33 min to about 26.
- py3.13 test time: 2943 s, with the Le Bail file at 217 s. The base's
  py3.12 total was 3635 s, with the Le Bail file at 1076 s.
  `test_magnetic_isotropy` is now the largest file, at 453 s, from tests
  outside the sweeps (WP-1418's question).
- py3.11 failed one test this branch does not touch:
  `test_fit_usable.py::test_issue_243_reproduction_reads_unusable_while_converged`
  returned `max_iter`, not `converged`. It passed on #849's last py3.11 run
  with the same source and identical package versions. Locally it passes
  with the compiled tier on and off, and its dearest stage used 112 of 400
  evaluations. The fit ends at Rwp 155 %, the #243 shape, so its solver
  path is erratic. The test declares no compiled path, and its owner
  WP-1336 is closed. Not filed yet: the maintainer's call.

Next:

1. Read the new run's py3.11 leg. A pass there supports the flaky reading of
   the `test_fit_usable` failure.
2. After the merge, re-measure ten main runs (the open task). Shard and trim
   the PR matrix only if the median Python leg is still over about 20 min.
3. Then check that each `slow` case added here passed once in the nightly
   `full` job, which acceptance requires.

- **2026-10-09** — Filed. The suite is a normal size for its code, and CI
  slowed because about 60 slow tests grew faster than the rest. The worker
  count is ruled out: halving it changed nothing. The maintainer asked why
  CI takes so long and whether the suite is a normal size. Open WP-1506 owned
  the cut as its task 7, but its scope is the docs-only skip. So the cut moved
  here, and the maintainer had 1506 closed on the same PR (#856). Its open
  WP-1519 note about the nightly probe line now sits in this Context. No forward reference went to 1545: its PR #812 is open, and
  where the tutorials run is this WP's decision. The measurements come from
  `gh run list`, job logs, junit artifacts and peer tarballs, all counted with
  one tokenize-based script. The scripts were scratch and not kept. Docs only:
  no review pass, no suite run beyond the docs job's four files (124 passed,
  macOS arm64, `[dev]`). Next: the Le Bail file, the largest single item at
  5 wall-min a leg. Its re-measured CI leg decides whether the sweeps and
  tutorials are enough or sharding is needed.

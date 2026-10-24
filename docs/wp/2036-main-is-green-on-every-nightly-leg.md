# WP-2036 — main is green on every nightly leg: a full suite that finishes, two Windows tooling tests, and answers that move with the platform

Milestone: unscheduled · Status: ⬜
Track: The repo's own process
Depends on: — (2002 soft, the closing stage that moved most of these; 2012 soft, the LaB6 axial mirror)
Priority: P1 2026-10-23 — main's only full-suite run has produced no result since #1085 merged, and the `qpa` guide's phase-fraction esd is 0.21 wt % on macOS against 2.24 wt % on Linux, with nothing firing

## Goal

Every job of `nightly.yml` passes on `main`, and the full suite passes on an arm64 Mac.
Each answer a guide page or an acceptance test quotes is either the same on every
platform or quoted only to the precision the platforms share.

## Context

`nightly.yml` runs six jobs at 06:00 UTC. It has been red every night from 2026-10-16
to 2026-10-23, the last run checked (run 39940543791, `3e0dc6f7`). The failures have
four separate causes. They share this WP because they share its acceptance: one green
nightly.

**1. The Linux full suite no longer finishes.** On 2026-10-22 (`d01ae735`) the job
`full suite (Linux, incl. slow acceptance)` ran the whole suite in 1 h 37 min. On
2026-10-23 it reached 32 % at its 150-minute `timeout-minutes` and was cancelled, so it
printed no `--durations` table. Two stretches account for most of it: 7 % → 11 % took
48 min and 11 % → 15 % took 52 min. The four fast jobs took the same time on both days
(Linux 3.12: 15 and 18 min). PR #1085 merged between the two runs, at 23:30 on
2026-10-22. It is WP-2002's single-fit actions, which end every plan in a closing stage
at tight windows. So the full suite has not completed on Linux since the closing stage
landed. The slow tests that #1085 added or moved have therefore never run on Linux on
`main`. On an arm64 Mac the slow selection takes 18-19 min. The job's comment records
an earlier budget: 77 min of the old runtime was indexing-acceptance fixture setup on
the 2-core runner. Cause not measured. `workflow_dispatch` is on, so a run can be
started by hand.

**2. Two Windows-only tooling failures.** Both appear only in `fast suite (Windows)`.
- `tests/test_closed_wp_writes.py`, 5 tests, red every night since 2026-10-17. WP-1994
  shipped `.claude/hooks/closed_wp_writes.py` on 2026-10-16. Each test gets `[]` where
  it expects a closed WP (`assert [] == ['0001-closed.md']`). *Hypothesis, not run*:
  `_git` calls `subprocess.run(..., text=True)` with no `encoding=`, so Windows decodes
  git's UTF-8 output as cp1252. Every byte of ✅ (E2 9C 85) decodes in cp1252, so
  nothing raises. The status then reads `âœ…`, `wp_index.STATUS_RE` never matches, and
  no WP looks closed. Seven more hooks call `subprocess.run(text=True)` without
  `encoding=` (`handover_owed.py`, `session_start.py` ×3, `session_usage.py`,
  `worktree_remove.py`, `worktree_only.py`, `worktree_create.py` ×2).
  `tests/test_portability.py::test_every_text_io_call_names_its_encoding` exists for this
  class and does not see `subprocess.run(text=True)`.
- `tests/test_manual.py::test_the_page_contract_fails_what_it_should`, 2 errors, red
  since at least 2026-10-16: `ValueError: the environment variable is longer than 32767
  characters`, at setup and at teardown. *Hypothesis, not run*: pytest writes each
  test's node id into `PYTEST_CURRENT_TEST`, and this test's parametrize id is the
  page text itself, which runs past Windows' 32 767-character limit. An `ids=` would
  fix it.

**3. Two guide scripts print different numbers on different platforms.**
`tests/test_examples.py::test_every_guide_script_prints_what_its_page_quotes` runs each
`examples/guides/*.py` and checks that its page quotes only lines the script printed.
Linux passes both cases below. macOS CI failed `moment` on 2026-10-22 and `qpa` on
2026-10-23. Windows failed `moment` on 2026-10-23. An arm64 Mac (`[dev,jax]`, Python
3.12) fails both on `882644c1`.
- `qpa`. `docs/docs/guides/qpa.md` quotes `NAC 96.92 ± 2.24 wt%` and `CaF2 3.08 ±
  2.24 wt%`. On the Mac the script prints the same fractions at **± 0.21 wt %**. This is
  not rounding: one esd is ten times the other. The same run prints `HIGH_CORRELATION`
  on `phases.1.scale ~ phases.1.extinction` (ρ = +0.996) and `FLOOR_HIT` on two CaF₂
  Biso values. A near-singular block like that is where an esd depends on how the
  covariance is cut, so the platforms' LAPACK builds are a suspect. On the Mac SciPy
  and numpy link Accelerate, and on Linux OpenBLAS (WP-2002, 2026-10-21: Accelerate's
  `gesdd` failed where OpenBLAS's decomposed). Not measured. Which esd is honest is the
  question, and a user quoting either one is told nothing.
- `moment`. WP-2002 found on 2026-10-22 that the guide's two refinement rounds stop at
  one of two nearby points under a 1e-14 nudge to the start (0.41 or 0.47 esd of scale
  shift; Linux takes one, the Mac the other). It changed the page to quote only what
  both share (`6f1d131d`). The page still fails. On Windows it quotes `|m| = 2.04 ±
  0.05 μB` where the script printed `2.03 ± 0.05`. On the Mac the script stops at
  `examples/guides/moment.py:112`, `assert steps[1][0] < 0.001` (round 2's move in
  |m|).

**4. Four slow tests fail on an arm64 Mac.** They fail on `main` `12f459e5`, which
contains #1085 (darwin/arm64, `[dev,jax]`, nothing else running; full `-m slow`
selection 4 failed, 404 passed, 12 skipped, 14 xfailed in 18 min 23 s). Whether they
fail on Linux is unknown until item 1 is fixed.
- `test_staged_start_invariance.py::test_the_biso_start_does_not_change_the_answer[cpd1a]`:
  Biso starts 0.5 and 1.5 Å² land 0.175 plain esd apart on `instrument.profile.x`
  (bar 0.1; plain esd is the esd without the Bérar-Lelann inflation). WP-2012's
  Inherited notes the cause: cpd-1a's QPA protocol frees the instrument Lorentzian `x`
  and each phase's `lor_size` together. Both go as 1/cosθ, so only their sum is
  determined.
- `…::test_the_axial_sizing_floor_does_not_change_the_answer[lab6]`: `AXIAL_SIZING_FLOOR`
  0.02 against 0.05 lands 8.82 plain esd apart on `instrument.geometry.axial_hl`. This is
  WP-2012's S/L ↔ H/L mirror. The test's lab6 Biso row is already a strict xfail citing
  WP-2012, and this row is not.
- `…::test_the_axial_sizing_floor_does_not_change_the_answer[cpd1a]`: a strict xfail
  that passes (XPASS(strict)). Its reason expects 0.138 plain esd on corundum's cell c
  behind the closing stage, and here it comes in under the bar.
- `test_acceptance_magnetic.py::test_the_150k_null_finds_no_moment`: the null's Rwp is
  0.0991227 against the nuclear-only fit's 0.0992423, 1.2e-3 relative against a bar of
  1e-3. The moment is still reported unsupported. The Rwp assertion is the only one
  that fails.

Items 3 and 4 are one class: a fit with two nearby stopping points, where the platform
picks the point. The local reproduction is a relative nudge of 1e-14 to one start value,
which reproduced Linux's answer on a Mac in WP-1930. A test or page that quotes one
stopping point's digits fails on the other platform whatever the code does.

The full Linux job failed once before in this window, on 2026-10-17:
`test_lebail_alternation.py::test_the_state_the_loop_keeps_is_the_state_a_hand_loop_would_continue_from`.
It passed on every later night, so it is out of scope unless it recurs.

### Inherited

- **From WP-2037 (2026-10-24): `moment` fails on Linux x86-64 too, and `hold` sat on a rounding edge.** On a `[dev]` venv in a cloud container (Linux x86-64, branch `claude/focused-maxwell-app5wv` at `1174cbf`), `examples/guides/moment.py:117` fails with `steps[0][0]` = 0.1034 against its `< 0.10` (round 1's move in |m|; round 2's is 1.5e-6), identical with and without 2037's CIF change, so not 2037's. The same container's `hold.py` printed 348.5 ppm against the guide's `< 350` before 2037 read FAP's Ca1 on 1/3 and 351.9 after; 2037 changed the guide to print the floor every platform clears ("more than 250 ppm", asserting 250-400, `79bb977`), which is item 3's rule applied to one more page.

## Non-goals

- Removing the S/L ↔ H/L mirror or the `x`/`lor_size` degeneracy. Those are WP-2012's.
  This WP marks the rows that fail because of them, citing WP-2012, as the lab6 Biso row
  already does.
- WP-2002's open rulings (the evaluation windows, its sixth round).
- Raising `timeout-minutes` without the durations table that says why. The job's
  timeout is a runaway guard (root CLAUDE.md § Testing headlines).

## Tasks

- [ ] Linux full suite: start `nightly.yml` by hand on `main` with `--durations=50`
      reachable (a temporary branch workflow if needed), find what slowed after #1085,
      and fix the cause. Rebudget only if the cost is the closing stage's own and the
      durations table says so.
- [ ] Windows `test_manual`: give the page-contract cases `ids=`, and confirm on the
      Windows leg.
- [ ] Windows `closed_wp_writes`: confirm the cp1252 hypothesis on a Mac (run `_git`'s
      decode as `cp1252`), name `encoding="utf-8"` on every `subprocess.run(text=True)`
      in `.claude/hooks/`, and extend `test_every_text_io_call_names_its_encoding` to see
      `subprocess.run(text=True)` and to walk `.claude/hooks/`.
- [ ] `qpa` guide: find why the esd differs tenfold between Linux and the Mac, decide
      which is honest, and fix the package if the covariance depends on the LAPACK
      build. Change the page only if both values are honest readings of one fit.
- [ ] `moment` guide: make the page and the script's own asserts hold at both stopping
      points, or make the rounds land on one point.
- [ ] The four slow tests: re-run on Linux once task 1 lands. Mark the lab6 and cpd1a
      start rows that fail through WP-2012's degeneracies as strict xfails citing it.
      Resolve the cpd1a XPASS. Find whether the closing stage moved the 150 K null's Rwp
      ratio, and fix the fit or the bar on that evidence.
- [ ] Tests: each fix has a test that fails before it, and the 1e-14 nudge is the
      local check for every platform split.
- [ ] Skill: none expected, since these fix tests, CI and one esd. If the `qpa` esd
      changes, check `references/` for a quoted QPA esd.

## Acceptance

One `nightly.yml` run on `main` with all six jobs `success`, and the full suite green on
an arm64 Mac.

```sh
gh run list --workflow nightly.yml --branch main --limit 1
.venv/bin/python -m pytest -n auto --dist loadgroup
.venv/bin/python -m ruff check src tests examples
```

## References

- Nightly runs 39940543791 (2026-10-23, `3e0dc6f7`) and 39765617812 (2026-10-22,
  `d01ae735`); the Windows job's red nights 2026-10-16 to 2026-10-23.
- PR #1085 (WP-2002, merged `425334ad`); WP-1994 (`closed_wp_writes.py`); WP-2012
  (the two degeneracies); WP-1930 (the 1e-14 nudge).

## Handover log

- **2026-10-23** — created by the maintainer's `/pr-review` session, which found these
  failures while gating #1122. No open WP owns them as a set. WP-2002 is in flight and
  caused items 1, 3 and 4, but its file is waiting on rulings, and item 2 comes from
  WP-1994, which is closed. WP-2012 owns two of the degeneracies and none of the
  failing rows. Next: task 1, since items 3 and 4 cannot be read on Linux until the full
  job finishes.

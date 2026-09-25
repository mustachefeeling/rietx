# WP-1459 — a Pawley intensity past the end of the data

Milestone: unscheduled · Status: ✅ 2026-09-25 — all five tasks landed from outside in PR #453; an off-data reflection is ridged rather than dropped, and `carry_hkl_intensities` is the switch
Depends on: — (1336 soft: its status channel is where "converged at 2494× the cleared Rwp" belongs)

## Goal

A reflection whose centre lies outside the fitted window cannot carry an
unbounded Pawley intensity, and TRF's step test no longer reads in the units
of the largest component of θ. A warm-started sequential Pawley chain then
refits each pattern as far as a cleared one does.

## Context

Issue #440 (2026-09-23), found on a real operando series and reproduced
synthetically. The reporter's first hypothesis (carried intensities near the
≥ 0 bound make the first steps inert) is refuted in the issue itself: none
of the 105–107 carried intensities sits at or below zero at the stall, and
flooring them does not remove it.

**The mechanism, three parts, each at `8fbafe5`:**

1. **The reflection list runs 0.5° past the data.** `model/forward.py:2827`
   sets `hi_eff = tt_max - zero + 0.5`, so a reflection centred beyond the
   last channel enters the Pawley block with only its tail on the data. Its
   intensity is bounded below, barely determined and free to grow.
2. **The carry compounds it.** `SequentialRefinement._fit_one`
   (`sequential.py:1383` onward) seeds each warm pattern's Pawley block from
   the previous pattern's per-hkl intensities, and `refine.py:2075-2083`
   skips the first stage's Le Bail seed when they are carried. The value
   grows pattern to pattern.
3. **TRF's xtol test is relative to the unscaled ‖x‖.** scipy stops when
   `‖dx‖ < xtol·(xtol + ‖x‖)`, and rietx passes `XTOL = 1e-12`
   (`optimize/least_squares.py:118`). With one component near 1e11, any step
   shorter than about 0.1 in the raw units of the whole vector ends the
   solve as `xtol`, which maps to `converged`.

**Checked against the tree at `8fbafe5`** with the issue's script (ten
synthetic fluorapatite patterns, cell +0.3 % over the series, `plan="pawley_default"`,
`reseed=False` unless stated), Linux x86_64, about 7 minutes for all four
chains:

| i | carried Rwp % | it:term | max carried I | cleared Rwp % | carried, xtol off | default ladder |
|---|---|---|---|---|---|---|
| 0 | 3.396 | 3:xtol | 0 | 3.396 | 3.396 | 3.396 |
| 1 | 3.442 | 12:ftol | 4.13e7 | 3.442 | 3.442 | 3.442 |
| 2 | 3.422 | 16:xtol | 4.22e10 | 3.422 | 3.422 | 3.422 |
| 3 | **9.486** | **2:xtol** | 3.9e11 | 3.409 | 3.409 | 3.409 |
| 4 | 15.748 | 3:xtol | 3.9e11 | 3.422 | **80.461** | 3.422 |
| 5 | **865.401** | 7:xtol | 2.69e10 | 3.417 | 80.312 | 3.417 |
| 6 | 72.531 | 3:xtol | 2.69e10 | 3.447 | 80.199 | 3.447 |
| 7 | **8725.769** | 2:xtol | 5.38e10 | 3.499 | 80.086 | 3.499 |
| 8 | 75.542 | 73:ftol | 5.38e10 | 3.371 | 79.938 | 3.371 |
| 9 | 75.359 | 33:ftol | 2.05e3 | 3.417 | 79.791 | 3.417 |

Every pattern of every chain reports `status="converged"`. Three
differences from the issue's macOS table matter for the work:

- **The mechanism reproduces, but not the digits.** Pattern 3 stalls after
  two iterations at 2.78× here against 2.81× there. The later patterns
  diverge by different amounts.
- **Turning the xtol test off does not rescue the chain here.** From
  pattern 4 on it sits near 80 % Rwp, where the issue measured 1.00×
  throughout. So the out-of-window reflection (part 1) is the root, and
  scaling xtol (part 3) alone is not a fix. Test both fixes separately and
  together.
- **The shipped default ladder rescued every pattern here.** The issue saw
  pattern 2 pass the 1.25× fence at 1.015×. A drift under the fence is
  where a user with defaults meets this.

**A single fit has it too.** Pattern 0's fit, with nothing carried, ends
with (6 0 2), centred at 75.44° past the last channel at 74.99°, at 4.13e7
against a median of 81 over 105 reflections; the next largest is 2.6e3
(checked with a hook on pattern 1's carried state). Its last stage ended on
`xtol` after 3 iterations. So any multi-stage
Pawley fit's later stages inherit the scale problem. Whether that costs a
single fit anything is unmeasured.

**Shapes of a fix, from the issue, to be measured:**

- Keep reflections centred outside the fitted window out of the Pawley
  block, or bound or regularise their intensities. The 0.5° margin exists
  so a tail reaching into the window is modelled. Find why before removing
  it; the Le Bail path shares the list.
- Pass `x_scale` to TRF, or test xtol on the table's columns only, so the
  intensity block cannot set the step scale for Å and degrees.
- A public switch for carrying extraction state along a series. Today the
  only way to clear it is the private `ref._pending_reflections = []` in a
  `constrain` hook.

## Non-goals

- The status channel. `converged` at many times the Rwp is WP-1336's
  concern (issue #243). This WP removes the cause, and 1336 makes the
  status say so.
- Changing the reseed ladder's 1.25× fence.

## Tasks

- [x] Measure part 1's fix alone, part 3's alone, and both, on the issue's
      series and on one single multi-stage Pawley fit; record the table.
- [x] Implement the chosen fix. Check that Le Bail on the shared reflection
      list is unchanged or better, and say which.
- [x] Decide the public carry switch, and implement it or record the
      decision here.
- [x] Tests: a short synthetic chain (fewer patterns than the issue's, for
      the fast suite) where the carried chain's Rwp equals the cleared one's
      within a stated tolerance; no reflection outside the window carries an
      intensity above a stated multiple of the median after a fit.
- [x] Skill: a row in `references/series.md` (it has none for Pawley at
      `8fbafe5`) if the carry switch lands; otherwise none, since the fix is
      inside the fit.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_sequential.py tests/test_pawley.py -q
.venv/bin/python -m ruff check src tests examples
```

## References

Pawley (1981), *J. Appl. Cryst.* **14**, 357. The TRF step test: Branch,
Coleman & Li (1999), *SIAM J. Sci. Comput.* **21**, 1, as scipy implements
it.

## Handover log

### 2026-09-25 — done from outside: a ridge, not a drop, and a carry switch

The out-of-window Pawley intensity is bounded, and a carried chain refits
as far as a cleared one. It landed as an outside contributor's PR #453, reviewed
over two rounds and merged as `52eb1f70`. Issue #440 closed on the merge.
The contributor left this file alone, as contributors do, so the measured
tables the Tasks ask for are in the PR description. This entry records
what was chosen and where the evidence is.

- *Done*: all five tasks, ticked above.
  - **Part 1 alone, as a ridge.** A reflection with no emission line
    centred on the fitted channels stays in the list and gets one Pawley
    restraint row, √λ·I_k/s_p. Here s_p is the phase's largest on-data
    intensity at stage start and λ is `PAWLEY_OVERLAP_LAMBDA`
    (`CompiledPhase.off_data`, `PawleyBlock.off_data`,
    `build_pawley_restraint`). Dropping the reflection was measured and
    refused. The 0.5° margin is what lets a stage move a reflection onto
    the data, and without it a cold pattern-3 cell stage stalled at 24.5 %
    Rwp against 3.409 %.
  - **Part 3 was not adopted.** scipy's TRF tests `xtol` on the unscaled
    step, so `x_scale` never reaches that test. `x_scale="jac"` made the
    runaway worse (6.7e51), and a scaled intensity block made it much worse
    (4.8e29). With the ridge in, turning `xtol` off changes no digit.
  - **Measured** (PR #453 § 2, macOS arm64, the issue's ten-pattern
    series, `reseed=False`): the carried and cleared chains agree to four
    decimals on every pattern, against 769× before. The largest carried
    intensity went from 1.1e12 to 3.35e3. On one fit, (6 0 2) went from
    1.45e8 to 2e-4 ± 3.9e3 at the same Rwp, 3.3963 %.
  - **Le Bail is unchanged, bit for bit.** That path never reads
    `off_data`.
  - **The carry switch**: `SequentialRefinement(carry_hkl_intensities=)`,
    also on `refine_sequential`, default `True`. Le Bail's cleared chain
    ends higher than its carried one (4.29 % against 3.95 % at pattern 9),
    so carrying stays the default.
  - **The result names the ridged reflections.** `PAWLEY_OFF_DATA_RIDGED`
    (info, one per phase, the hkls in `where`) sits beside
    `PAWLEY_OVERLAP_UNRESOLVED`. Round 1 of the review asked for it, since
    an exported intensity otherwise carries no sign that it is the ridge's.
  - **Skill and manual**: a `series.md` row for the switch, a
    `diagnostics.md` row for the code, and equation `fm-pawley-ridge` in
    the theory chapter.
- *Checked at merge*, on the merged tree (`9e377c55` + `bb08ae92`),
  darwin/arm64, `[dev,jax]` venv, load average 17 to 45 from unrelated work:
  fast selection 6097 passed, 89 skipped (main's 6094 plus the PR's three
  tests); full `-m slow` 197 passed, 7 skipped, 1 xfailed (brucite,
  WP-1449) in 46:05; ruff clean. The contributor's numbers were not rerun.
- *Not done, and why*:
  - A reflection centred inside an **interior** excluded region has the
    same indeterminacy. The criterion covers only the two ends of the
    fitted window, which is all this WP names. It waits for a report.
  - The status channel ("converged at N× the cleared Rwp") is WP-1336's.
  - `PAWLEY_OFF_DATA_RIDGED` belongs beside the codes in SKILL.md rule 22,
    which say a number did not come from the data, and in
    `references/abstention.md`. SKILL.md is near its cap, so placing it is
    left to the maintainer.
- *Gotcha*: this PR and #385 each fit `references/diagnostics.md` under
  `REFERENCE_MAX_BYTES` alone. Together they exceed it by about 370 B.
  This one merged first, so #385 carries the fix.

- **2026-09-24** — created, from the 2026-09-24 issue triage (issue #440).
  Checked against the tree at `8fbafe5`: the carried chain stalls on `xtol`
  and diverges as reported, and the cleared chain and the default ladder do
  not. Turning the xtol test off does *not* rescue this machine's chain,
  unlike the reporter's, so the out-of-window reflection is the root. Next:
  the three-way measurement.

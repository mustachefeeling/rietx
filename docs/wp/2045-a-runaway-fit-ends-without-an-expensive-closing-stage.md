# WP-2045 — A runaway fit ends without an expensive closing stage

Milestone: unscheduled · Status: ⬜
Track: A long run is not one fit
Depends on: —
Priority: P2 2026-10-24 — a defect that costs a user a workaround: a fit that runs away now seems to hang, where 1.9.0 ended it in seconds; 1.10.1 waits on it

## Goal

A fit whose last declared stage ends at a runaway answer finishes in a time
comparable to its declared stages, and says what it skipped or held. The
hostile series in `tests/test_acceptance_sequential.py` (`chained_all`)
finishes on every platform. The nightly `full` job completes inside its
150-minute limit again.

## Context

**What happens, measured 2026-10-24 by WP-2043** (macOS arm64, `[dev]`, the
1.10.0 release tree; the probe is described under Acceptance). The hostile
series carries every parameter, the phase scales included, from one IUCr
round-robin mixture to the next (cpd-1a → cpd-1b is a large swing in phase
fractions). On cpd-1b the warm attempt's one declared stage ends "converged"
at Rwp 0.760 with these values:

- `instrument.geometry.axial_sl` 557.8. Until 1.10 it had a ceiling of 0.2,
  and real instruments sit near 0.01-0.05.
- `instrument.profile.v` −5.64 deg².
- zincite's oxygen Biso 25 Å².

Then `run_stages()` appends the closing stage (WP-2002), which recompiles at
that answer with windows dropping 1e-3 of each peak (`CLOSING_WINDOW_TOL`)
and the finer axial node rule. At this answer:

| | corundum's window points | FCJ nodes, max | point-nodes per evaluation |
|---|---|---|---|
| cpd-1b's declared stage (2 % windows) | 45 035 | 13 | 352 785 |
| cpd-1a's closing stage, a normal one | 613 003 | 22 | 6 307 023 |
| cpd-1b's closing stage, at the runaway answer | 850 103 (every window is the whole 7 251-point pattern) | 1 024 | 544 128 502 |

So one evaluation of corundum alone costs about 1 500× the declared stage's
and 86× a normal closing stage's. WP-2043's lane saw it spend over 50
CPU-minutes in that closing stage without finishing. The series would have
rejected the attempt anyway (Rwp 0.760 is far outside its fence) and
escalated to the next rung, but only after the closing stage returns.

**When it started.** A snapshot just before #1085 (WP-2002's merge,
`2330afc02`) runs both patterns in 3.1 s, and its warm stage converges at
Rwp 0.139. The nightly `full` job took about 95 minutes on 2026-10-21 and
2026-10-22, and hit its 150-minute `timeout-minutes` on 2026-10-23 and
2026-10-24, the first two nightlies after #1085 merged (2026-10-22 22:30).
WP-2037's local slow run stalled on the same test the same day.

**Two changes of #1085 combine.** (1) WP-2002 B9 removed the limits chosen on
quantities where the model stays defined; `axial_sl` and `axial_hl` lost
their 0.2 ceiling (the 1.10.0 notes, Numbers that move). That was a
maintainer ruling. It is why this warm stage can walk the ratio to 557.8
instead of stopping on a bound, and this WP does not reopen it. (2) The
closing stage polishes whatever the declared stages hand it, and nothing
asks whether that answer is worth polishing or what the polish costs.

**With the closing stage off, nothing runs away** (same probe,
`closing_window_tol=None` on `qpa_plan()`, 2026-10-24). All eight patterns
finish in 9.2 s, each kept on its warm rung, and cpd-1b's warm stage
converges at Rwp 0.163 (corundum 94.84, zincite 1.08, fluorite 4.08 wt %,
weighed 94.31, 1.36, 4.33). So the runaway itself depends on the start: it
begins from cpd-1a's closing-stage answer, not its declared-stage one. A
design that only makes the expensive stage cheaper leaves a warm attempt
that still diverges and is then escalated.

**Who sees it.** A user whose fit runs away now waits with no end in sight,
where 1.9.0 returned a bad Rwp in seconds. Cancelling is cooperative and read
between residual evaluations, so it should take effect within one evaluation
(inferred, not measured). Measured only on this series. A single fit should
behave the same when its last declared stage runs away (inferred from the
mechanism: the closing stage compiles at whatever answer it is handed).
1.10.0 ships with this as a stated limit (the maintainer's ruling,
2026-10-24, option A of WP-2043): `RefinementPlan.closing_window_tol=None`
skips the closing stage.

**Design candidates, none chosen.** Each needs the maintainer's ruling, and
the generality audit table needs a row for any threshold
(`src/rietx/_audit.py`; root CLAUDE.md § Every heuristic has a row):

1. Skip the closing stage, recorded in a field and a diagnostic, when the
   recompiled model's work exceeds a factor of the last declared stage's.
   This covers every parameter that drives windows or FCJ nodes, but it is a
   tier-3 threshold.
2. A runaway reset for the axial ratios, on the pattern WP-2002 B8 built for
   a cell (`refine.reset_cell_runaway`, `CELL_RUNAWAY`: a parameter leaving
   a window around its stage-start value is put back and held for one more
   solve). This covers this case, not V or the widths.
3. In `sequential.py`, judge a warm attempt against the fence before its
   closing stage, and run the closing stage only on the attempt kept. This
   covers series and not single fits.

The frozen-per-stage invariant constrains all three: window ranges and FCJ
node counts are fixed at compile and never change inside a solve, so any
decision is taken at compile, from values the stage cannot change.

**Files.** `strategy/staged.py` (`run_stages`, the closing stage),
`model/forward.py` (`compile_model`, the window and FCJ sizing), `refine.py`
(`reset_cell_runaway`), `sequential.py` (the rung ladder and fence).

**Practice.** GSAS-II floors SH/L at 0.0005 or 0.002 and sets no ceiling
(`GSASIIstrMath.py`, `GSASIIpwd.py`; checked in GSAS-II 5.8.4 source on
2026-10-24). No program surveyed has a closing stage of this kind; BGMN ends
with every parameter free and restarted from the previous answer
(`docs/practice.md` does not yet survey either point).

### Inherited

- **From WP-2003 (2026-10-24, PR #1150): the same runaway on Linux, what the ladder does with it, and one more chain in your acceptance.** WP-2003 measured the hostile series on a 4-core Linux x86-64 cloud container (`[dev]`). Results are in `docs/wp/2003-batch/reseed.md`, families `cpd` and `cpd-noclose`, per pattern. At cpd-1b the warm rung's closing stage ran to its 400-evaluation cap in 2 300-2 600 s and came back `max_iter` at Rwp 0.7652. Under the default fence (1.25 × the median) the ladder escalated to `warm_staged` and kept 0.13779, against 0.13732 for the independent fit. With the fence off, or with an infinite fence, the 0.7652 fit was kept and seeded cpd-1c, whose closing stage then crawled at about 5 evaluations a minute. With `closing_window_tol=None` the warm rung reached 0.16333 and nothing escalated. Two findings bear on the fix. (1) The time per evaluation is mostly FCJ quadrature: node counts climb to the 512 cap, and each new count misses the `leggauss` cache (`model/profiles/fcj.py:88-92`, reached from `refine.py:1548` → `model/forward.py:2212` → `fcj.py:241`). With default BLAS threading, one `leggauss(444)` took 5.4-6.0 s, against 0.014 s with one thread, so on Linux set `OPENBLAS_NUM_THREADS=1` before timing anything here. (2) WP-2003 added `tests/test_acceptance_sequential.py::test_the_first_rung_bound_moves_no_accepted_value`, which builds a second `chained_all`-shaped chain with the first-rung bound off, in the same `qpa-sample1` group. It cost 1 h 17 min for both chains on that machine, so your acceptance's "the nightly `full` job completes inside its 150-minute limit" has to count it. It should fall to the same seconds as `chained_all` once the runaway is cut short. WP-2036's Inherited carries the same measurement from the full suite's side.

## Non-goals

- Restoring the 0.2 ceilings, or any limit B9 removed. That was ruled.
- Which of S/L and H/L a fit reports. That is WP-2012.
- Every other nightly leg. That is WP-2036, which this WP unblocks for the
  `full` job.

## Tasks

- [ ] A fast test that reproduces the cost at compile, without running the
      expensive solve: compile cpd-1b's closing model at the runaway answer
      and assert the decision the chosen design makes
- [ ] The design, put to the maintainer with this file's numbers
- [ ] The implementation, its record field and diagnostic, and its `_audit`
      row
- [ ] `tests/test_acceptance_sequential.py` finishes; VALIDATION.md's three
      `chained_all` rows (marked unmeasured on 1.10.0) re-measured
- [ ] Notes for 1.10.1 (`docs/releases/`), and the 1.10.0 stated limit
      withdrawn from the skill
- [ ] Skill: the stated limit's bullet in `references/series.md` (beside
      the quarantine rule) removed or rewritten to what the fix does

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_acceptance_sequential.py -n 4 --dist loadgroup
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
```

The sequential suite finishes, alone on an arm64 Mac, in a time comparable to
1.9.0's (about 2.5 minutes for the module, measured by WP-2043's lane on the
pre-#1085 snapshot). The nightly `full` job completes on `main`.

WP-2043's probe (`hang/probe.py` in that session's scratchpad, not
committed) ran `SequentialRefinement(...).fit` on cpd-1a and cpd-1b under
`qpa_plan()` with `seed_scales` from cpd-1a, as `chained_all` does, wrapped
`compile_model` to log `win` and `fcj_n` per phase, and logged
`stage_start`/`stage_end` events.

## Handover log

- **2026-10-24** — filed by WP-2043's session (the 1.10 cut), after its
  VALIDATION lane found the hostile series never finishing and the session
  reproduced the cause. No open WP owns the closing stage's cost: 2036 owns
  the nightly legs being green and gets an Inherited pointer, 2012 owns the
  axial pair's identity, 2020 owns opt-in bound sets. The maintainer chose to
  cut 1.10.0 with the limit stated and fix it here.

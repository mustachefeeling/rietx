# WP-1469 — what the series fences cannot see

Milestone: unscheduled · Status: ⬜
Track: A long run is not one fit
Depends on: — (1333 landed the ladder and quarantine this extends; 1420 soft)
Priority: P2 2026-09-27 — a blank frame reads as a good fit and a real step goes unreported, silently, on the series path; `series.md` calls the default refit safe where it is not

## Goal

A chain says so when a pattern's kept rung still fails the Rwp fence, never
calls that pattern a good fit, and does not let one bad frame's step hide a
real step on the same path. A flagged step names its two patterns in a
field, not only in prose. And `references/series.md` stops promising that the
reseed fence catches a `refit="single"` collapse that every pattern shares.

## Context

Two issues from one source, 2026-09-25 and -26, both filed for the maintainer
from the rietx-jev driver's planted-series runs. Both are the same kind of
defect: a `SequentialRefinement` fence that compares a pattern with the
chain's own running median cannot see what the median moves with.

**Issue #481: three gaps, reproduced.** A synthetic LaB6 ramp of 24 patterns
(`Refinement.predict` from `tests/test_sequential.py`'s thermal-ramp models,
cell growing 6.4e-5 a pattern, Poisson noise). Pattern 7 is blank: every
phase scale 0, so background and noise only. The cell steps by 2e-3 Å from
pattern 12, the size of `jump_patterns`' step. The first pattern is fitted
with `mccusker_default`, then
`fit(patterns, plan="mccusker_default", refit="stages", on_error="carry",
verify_discontinuities=True)`. The script is in the issue, and it ran
unchanged here.

| Pattern | Rung kept | Rwp | cell a (Å) | Series code |
|---|---|---|---|---|
| ramp_006 | warm_staged | 0.0423 | 4.15819 | — |
| ramp_007, blank | cold | 0.1587 | 4.14990 (esd 1.6e-3) | `SEQUENTIAL_RESEED` |
| ramp_008 | warm_staged | 0.0427 | 4.15872 | — |
| ramp_011 | warm_staged | 0.0417 | 4.15953 | — |
| ramp_012, stepped | warm_staged | 0.0424 | 4.16179 | — |

Series median Rwp 0.0424. `SEQUENTIAL_DISCONTINUITY` fires on a, b, c, the
scale and `profile.v`, each "between ramp_007 and ramp_008" (a: 0.008824 Å,
33× the median step), and the verification refit confirms it. Nothing names
ramp_011 → ramp_012, a step of 0.002261 Å. The reporter's Mac (Python
3.12.10, macOS 26.6 arm64, at `8963fc19`) gave the same digits as this
triage's Linux x86_64 container at `91deebbb`. Started from the unfitted
models instead, the reporter found the blank kept its warm rung at Rwp
0.1589 and then carried **no series code at all**; in that run the planted
step was flagged, at 8×. That second run is theirs, not reproduced here.

1. **A pattern the fence still rejects after the ladder has no code.**
   `_reseed_needed` rejects a fit whose Rwp exceeds `RESEED_FACTOR` (1.25)
   × the median of accepted patterns. The blank's best rung sits at 3.7×.
   `_unrecovered_diagnostics` tests `entry.status == "diverged"` alone, so
   it stays silent. When the cold rung wins, `_reseed_diagnostics`'
   suggestion says "this point is a good fit". When a warm rung wins, no
   code fires. The Rwp leg of the fence is therefore a trigger for the
   ladder and never a verdict on the pattern.
2. **One flag per path lets a bad frame hide a real step.**
   `_discontinuity_steps` keeps `k = argmax(step * big)` per path, so of
   the steps passing both legs (`DISCONTINUITY_FACTOR` 5 × the median step,
   `DISCONTINUITY_SIGMA` 3 × the combined esd) only the largest is
   reported. Here that is the blank's, and the cold verification confirms
   it, because both cold fits reproduce a cell fitted to noise.
3. **The pair lives in the message alone.** `where` is the parameter path.
   `_FlaggedStep.labels` carries the pair but is private, and `Diagnostic`
   has no field for it (`level`, `code`, `message`, `where`, `suggestion`,
   `value`). A caller finds the two patterns by parsing prose.

The reporter's suggestions, in order: (1) a code for a pattern whose kept
rung still trips the Rwp leg. `SEQUENTIAL_UNRECOVERED` fits, since its
suggestion already reads "the values on this point are not a measurement",
and the reseed text then stops calling such a point a good fit. (2) Flag
every step that passes both legs, or leave a pattern out of the step scan
once the fence rejected it on every rung. (3) The pair in a structured
field beside `where`. rietx-jev's driver already treats
`SEQUENTIAL_UNRECOVERED` as a gap, so (1) reaches it unchanged.

Whether (1) also **quarantines** the pattern (seeds no successor, leaves the
median) is part of the decision. 1051's quarantine is keyed on `diverged`
for a reason its docstring gives: "diverged after the last rung" and
"diverged" are one statement. An Rwp-leg rejection is not a divergence. A
blank frame is the case for quarantine, and a genuine specimen change at
3.7× the median is the case against it.

**Issue #475: the reseed fence cannot see an offset every pattern shares.**
`references/series.md` § "The default `refit="single"`" says a pattern where
the collapsed plan is wrong "is caught by the reseed fence". The reporter ran
the eight QPA round-robin sample-1 mixtures (phases and `qarr_instrument()`
from `tests/test_acceptance_qpa_roundrobin.py`, `rx.Dispersion()` added) with
`lab_bragg_brentano`, which frees U, V, W and the axial terms, carrying
everything from cpd-1a's fitted models, `on_error="carry"`:

| Pattern | `refit="single"` | `refit="stages"` | independent |
|---|---|---|---|
| cpd-1a | 0.1632 | 0.1632 | 0.1632 |
| cpd-1b | 0.1626 | 0.1404 | 0.1415 |
| cpd-1c | 0.1224 | 0.1020 | 0.1020 |
| cpd-1d | 0.1440 | 0.1253 | 0.1253 |
| cpd-1e | 0.1427 | 0.1238 | 0.1238 |
| cpd-1f | 0.1264 | 0.1093 | 0.1092 |
| cpd-1g | 0.1383 | 0.1186 | 0.1185 |
| cpd-1h | 0.1377 | 0.1198 | 0.1198 |

`"single"`: 384 iterations, 66 s, `instrument.profile.u ~ v ~ w` at
|ρ| = 1.000 on seven of eight, no `SEQUENTIAL_RESEED`. `"stages"`: 2334
iterations, 103 s, no U/V/W correlation row. The weight fractions met the
round robin's bar under both, 24 of 24. The collapsed patterns all sit
15-20 % high, so the median they are compared with rises with them and
none crosses 1.25×. `test_acceptance_sequential.py` found chained and
unchained Rwp identical, but with `qpa_plan()` and the scales re-seeded per
pattern, so the skill's saving for `"single"` is measured on that setup
only.

*Re-run at `91deebbb`* (Linux x86_64), with a simpler start than the
reporter's driver. cpd-1a was fitted directly with `lab_bragg_brentano`
after `seed_scales`, with no Le Bail pass and no report loop, and reached the
same 0.1632. Then the chain was run under both settings:

| Pattern | `"single"` here | `"stages"` here |
|---|---|---|
| cpd-1b | 0.1455 | 0.1406 |
| cpd-1c | 0.1313 | 0.1020 |
| cpd-1d | 0.1578 | 0.1257 |
| cpd-1e | 0.1549 | 0.1238 |
| cpd-1f | 0.1347 | 0.1093 |
| cpd-1g | 0.1485 | 0.1185 |
| cpd-1h | 0.1500 | 0.1198 |

The staged column matches the reporter's to 0.0004. The collapsed one sits
3-29 % above it (1.23-1.29× on six of seven), so it is further off than
theirs. It shows the same silence: no `SEQUENTIAL_RESEED`, since the series
median rose to 0.1493 with it. The collapse shows up differently here: no
U/V/W `HIGH_CORRELATION` row is on any entry of either chain. What separates
the two chains is `SEQUENTIAL_PERSISTENT_FINDING` on
`RESOLUTION_UNCONSTRAINED` for U, V and W, which appears in 6 of 8 collapsed
patterns and in none of the staged ones. `RESOLUTION_NOT_POSITIVE` on U, V
and W does not separate them: it fires in 6 of 8 collapsed patterns and in
7 of 8 staged ones. Both chains carry the zero/displacement correlation in
8 of 8.

`series.md` already says two neighbouring things: "`SEQUENTIAL_RESEED` is
not the net for a wrong basin" (it needs a ~25 % jump) and "Sample the chain
cold; it is the only check here that catches a cheap wrong basin". What it
does not say is that the `refit="single"` bullet's own promise fails the
same way when the offset is shared, and that a width-freeing plan is where
it was measured. The reporter's two cheap reads: the per-pattern Caglioti
correlation rows, and a few patterns refitted cold.

### Inherited

- **From WP-1465, 2026-09-27: a third series fence now reads the trajectory,
  and it skips only `"diverged"` entries.** `SEQUENTIAL_WIDTH_GROWTH`
  (`sequential._width_growth_diagnostics`) fires when a phase width reaches
  3× the first value the series measured (> 3σ) and GoF reaches 2× that
  pattern's GoF, at the same pattern. It compares against that reference
  pattern, not a running median, so the median drift this WP is about does
  not reach it. A **kept pattern that still fails the Rwp fence** does reach
  it, though. Issue #481's blank ramp_007 is fitted cold with a high GoF;
  were a width free and measured there, that frame could be the point where
  the trigger fires. Whatever marker this WP gives such an entry, add it to
  the trigger's skip beside `"diverged"`. The trigger's hand-built tests in
  `tests/test_sequential.py` (`_width_series`) are the place to pin that.

## Non-goals

- A held phase that cannot re-enter a chain: WP-1420 (#267).
- The direction-dependence check (`direction="both"`) and its cost: 1453.
- Choosing `RESEED_FACTOR` again. The factor is not what failed in either
  issue: a shared offset moves the median, and a rejected frame is let
  through by the code's condition, not by the threshold.
- A physics answer for the blank frame. The chain says the point is not a
  measurement; why the shutter stayed shut is the caller's.

## Tasks

- [ ] Gap 1: a pattern whose kept rung still fails `_reseed_needed`'s Rwp
      leg carries a warning-level code (`SEQUENTIAL_UNRECOVERED` widened,
      or a sibling), and `_reseed_diagnostics` no longer calls it a good
      fit. Decide, and record in this file, whether it is also quarantined
      (no successor seeded, out of the median), measuring both on #481's
      ramp and on a series with a real specimen change.
- [ ] Gap 2: every step passing both legs is flagged, or a pattern the
      fence rejected on every rung is left out of the step scan; pick one
      and say why. On #481's ramp the planted ramp_011 → ramp_012 step is
      flagged. Count the new flags on the suite's clean series, which must
      stay at zero.
- [ ] Gap 3: the pair is a field. `Diagnostic` is shared by every
      producer, so either a new optional field there (with its writer named,
      WP-1076) or a `SeriesResult`-level record beside the diagnostics, as
      `_FlaggedStep` already is privately. The verification pass reads the
      same record.
- [ ] #475: settle which chain-level signal separates the collapse. The
      triage's re-run found `SEQUENTIAL_PERSISTENT_FINDING` on
      `RESOLUTION_UNCONSTRAINED` for U, V and W (6 of 8, absent from the
      staged chain; `RESOLUTION_NOT_POSITIVE` fires in both), and the
      reporter found the U/V/W correlation row. Check which one holds on the reporter's start
      (Le Bail first) as well as on this one. If one does, the skill names
      it. If neither holds on both starts, the skill names a cold-refit
      sample.
- [ ] Tests: #481's ramp as a slow-marked fixture asserting all three gaps
      closed; a clean ramp asserting no new code; the round-robin chain
      under `"single"` if a signal is added.
- [ ] Skill: `references/series.md`'s `refit="single"` bullet stops
      promising the reseed fence catches a shared offset, names the
      width-freeing case and the two cheap reads; the `SEQUENTIAL_RESEED`
      and `SEQUENTIAL_UNRECOVERED` rows in its code table say what a kept
      rung above the fence now reports.

## Acceptance

On #481's ramp, the blank frame carries a warning-level code that does not
call it a good fit, the planted step is flagged, and a caller reads both
patterns of a flagged step from a field. The suite's existing series fire
nothing new. `series.md` makes no claim about `refit="single"` that the
round-robin chain contradicts.

```sh
.venv/bin/python -m pytest tests/test_sequential.py -q
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m pytest tests/test_skill.py -q
.venv/bin/python -m ruff check src tests examples
```

## References

- Issues #475 and #481, each with its full setup and, for #481, the script.
- WP-1051 (the ladder, keep-best, quarantine keyed on `diverged`), WP-1127
  (the first rung's budget), WP-1333 (a raise is a rung that lost).
- WP-1076 (a declared name is a claim: a new field names its writer).
- Madsen, I. C., Scarlett, N. V. Y., Cranswick, L. M. D. & Lwin, T. (2001).
  *J. Appl. Cryst.* 34, 409 (round-robin sample 1, the #475 data).

## Handover log

- **2026-09-27** — created, from the 2026-09-27 issue triage (issues #475,
  #481). Checked against the tree at `91deebbb`: #481's script reproduced
  every number in its table to the digit on Linux x86_64, and the three
  gaps were read in `sequential.py` (`_unrecovered_diagnostics` on
  `status` alone, `_discontinuity_steps`' `argmax`, `_FlaggedStep`
  private). #475 re-run on the same tree from a simpler first fit (table in
  Context): the staged chain matches the reporter's to 0.0004, and the
  collapsed one is 3-29 % high with no reseed. It surfaces as a persistent
  `RESOLUTION_UNCONSTRAINED` on U, V and W, which the staged chain does not
  carry, rather than as the reporter's correlation row. Next: gap 1's
  quarantine decision, measured.

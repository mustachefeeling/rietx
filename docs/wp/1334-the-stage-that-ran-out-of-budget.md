# WP-1334 — the stage that ran out of budget

Milestone: unscheduled · Status: ⬜
Depends on: —

## Goal

A stage that exhausts its iteration budget while barely improving the cost
stops rather than escalating, and says so. A caller holding a `StageResult`
can apply the keep-the-best-pass discipline the skill asks for without parsing
the event log for a number the object was standing next to when it was
computed.

## Context

From issue #222, measured over a 638-pattern laboratory-XRD chemical-looping
series — 1846 fits, 56.8 min wall, single-threaded (`OMP_NUM_THREADS=1`),
durations taken from rietx's own event log:

| termination | n | total time | share of stage time | median duration |
|---|---|---|---|---|
| `ftol` | 6297 | 1056.8 s | 53.1 % | **0.042 s** |
| `max_nfev` | 258 | 927.9 s | **46.6 %** | **3.036 s** |
| `ftol+xtol` | 30 | 3.9 s | 0.20 % | — |
| `xtol` | 29 | 3.1 s | 0.15 % | — |
| `gtol` | 8 | 0.4 s | 0.02 % | — |

**3.9 % of stages consume 46.6 % of stage time.** A `max_nfev` stage costs
**72×** the median `ftol` stage and returns a **median cost reduction of
1.23 %** for it. p90 is 92 %, so a minority genuinely rescue a fit — the
median one does not. They run a median of **201 iterations against 34**, and
concentrate in `warm_refit` (153) and `biso` (74); the worst individual
stages are `biso` at 15.98 s / 400 iterations and `phase_strain` at 8.51 s /
400, both `max_nfev`.

The ask is a per-stage rule of the shape *"if a stage exhausts its iteration
budget while improving cost by less than ε, stop rather than escalate"* —
**reported, not silent**. Everything it needs is already emitted.

**Two corrections to the issue, established on the tree at `c79fb5df`.**

1. `StageResult.status` is `Literal["converged", "max_iter", "diverged"]`, so
   "this stage exhausted its budget" **is already on the object** as
   `status == "max_iter"`. What is missing is the finer split the event log
   carries (`ftol` vs `xtol` vs `gtol` vs both), which is a different and
   smaller ask than the issue's wording suggests.
2. `rwp` genuinely is absent. `stage_end` emits `rwp=stage_rwp`, computed
   right there (`refine.py`, the `_run_plan` loop), while `StageResult`'s
   fields are `name, status, n_iterations, cost_initial, cost_final, freed,
   ftol, n_constraint_truncations, held, released`. So a caller doing
   keep-the-best has to re-derive Rwp from `cost_final` or read the log. Same
   shape as #218 and #222's own sibling ask: the quantity exists and is not
   reachable from the object the caller holds.

**What the measurement method establishes, and is worth keeping.** The
campaign started from the opposite hypothesis — that fits get slow when peaks
broaden or a phase fraction collapses. Pooled over 976 timed stage rows the
correlations point at reflection count (r = +0.398); stratifying into 12
(protocol × scan-geometry) cells reverses it:

| driver | median r within strata | range | sign consistent? |
|---|---|---|---|
| peak width | −0.147 | −0.486 … +0.190 | **no** |
| min phase fraction | +0.258 | −0.439 … +0.773 | **no** |
| n reflections | +0.052 | −0.573 … +0.636 | **no** |
| **n iterations** | **+0.859** | +0.142 … +0.961 | **yes** |

Cost tracks **iteration count** at a per-iteration price linear in pattern
size: `s/iter = 4.4 µs × n_points + 2.9 ms`, r(n_points, s/iter) = **+0.972**.
Broadening moves neither the number of steps nor the price of one. So the
lever this WP pulls (fewer iterations) is the only one measured to work.

A result that reflects well on the package and belongs in the record: the one
repeatable phase-fraction signal has the **opposite** sign to the naive
expectation — a phase going to zero makes fits *faster*, because
`PHASE_UNCONSTRAINED` fires and rietx holds that phase's 7–9 parameters
(WP-1301). The machinery designed to protect the answer also protects the
clock.

**The stop rule is a judgement, not a threshold to invent.** Root CLAUDE.md's
rule stands: a wall-clock budget in a test is a runaway guard, never a timer.
Here the budget is in the *library*, so the criterion must be stated in the
quantity the solver owns (relative cost decrease over the last k iterations),
never in seconds, and its default must be justified against the p90 = 92 %
tail — the point of the rule is to stop the median case without abandoning the
minority that rescues a fit.

## Non-goals

- The reporting cost that sits outside the stage brackets — 1335. #245
  measured that summing stage durations understates fit cost by ~9× under
  `stage_reports=True`; that is a different number and a different fix.
- A new solver or driver. This is a stop rule over the existing TRF path.
- Changing `Stage.ftol` or the intermediate-ftol schedule (WP-1123's rule:
  the plan alone knows which stage is last).

## Tasks

- [ ] `StageResult.rwp` — the number `stage_end` already emits, on the object
      that was standing next to it. Name its writer at review (WP-1076: a
      declared field with no writer fails no test).
- [ ] The finer termination reason on `StageResult`, or a written statement
      that `status == "max_iter"` is the whole answer and the log's split is
      deliberately log-only.
- [ ] A stop rule: a stage exhausting its budget below a stated relative-cost
      improvement stops, and raises a finding saying it did. Default chosen
      against the measured p90, not invented.
- [ ] Re-measure the #222 tranche shape on a suite fixture and record the
      recovered fraction, so the rule's effect is a number and not a claim.
- [ ] Tests: a stage that would exhaust its budget for nothing now stops and
      reports; a stage that would rescue the fit still runs.
- [ ] Skill: `references/batch.md` — the keep-the-best row, now expressible
      from `StageResult` alone; and the row saying what the new finding means.

## Acceptance

The measured tranche's `max_nfev` share of stage time falls substantially with
no converged parameter moving beyond its esd; the number is quoted with its
venv and platform (root CLAUDE.md § Numbers).

```sh
.venv/bin/python -m pytest tests/test_staged.py tests/test_schemas.py -q
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
```

## References

- Issue #222 (638-pattern laboratory chemical-looping series, 1846 fits).
  Its method note is worth keeping: bucketing timed fits on
  `(series_index, series_pass)` is wrong whenever an index recurs (a reseed
  retry, a verification refit, a restarted segment) — it reported 700.686 s
  against a 147.988 s wall clock, **ratio 4.73**, and nothing about the number
  looked wrong. Fixed by pairing `fit_start`/`fit_end` in order; the
  whole-run check that caught it was event-log-summed 3472.73 s against an
  independently measured 3409.27 s, ratio 1.0186. Assert that, do not assume
  it, in anything reporting a duration.

## Handover log

- **2026-09-03** — created, from the 2026-09-03 issue triage (issue #222).
  Two of the issue's asks were checked against the tree first: `max_iter` is
  already on `StageResult.status`, `rwp` genuinely is not.

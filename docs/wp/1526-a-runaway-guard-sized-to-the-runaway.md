# WP-1526 — A runaway guard sized to the runaway

Milestone: unscheduled · Status: ⬜
Track: The repo's own process
Depends on: —
Priority: P4 2026-09-29 — a slow test's wall-clock guard sits at 3.5× its serial time and failed once under load; changes no number

## Goal

`tests/test_held_phase.py`'s runaway guard fails only on a runaway, never on
a busy machine.

## Context

`test_the_ramp_reproduction_no_longer_runs_away` (slow) times a 13-pattern
`refine_sequential` chain against `RAMP_RUNAWAY_GUARD_S = 60.0`. Its comment
calls it a runaway guard, not a timer: the chain it guards against ran past
13 minutes on the pre-WP-1301 tree without finishing.

Measured 2026-09-29 in WP-1469's session (Linux x86_64, 4 cores, Python
3.12, `[dev]`): **17.1 s alone, 112 s** when a second test selection ran
beside a `-n 4` run on the same four cores. That is a 3.5× budget, and
`tests/CLAUDE.md` § Budgets in tests has the check: "if the budget is not
several times larger, the assertion is a load sensor". The runaway it guards
is ≥ 780 s, so a guard anywhere in 300-600 s still separates the two by
more than 1.3× on the runaway side. `REAL_DATA_BUDGET_SECONDS` (300 s) is the
precedent. The test's second assertion, iterations below the unbounded
baseline, is the real regression bar and is untouched.

## Non-goals

- The chain itself, and the iteration assertion.

## Tasks

- [ ] Re-measure the serial time on this machine class and under a loaded
      `-n auto` run, then set the guard with the margin stated in its comment
      (the runaway at ≥ 780 s on one side, the loaded time on the other).
- [ ] Skill: none — test hygiene; say so here.

## Acceptance

The guard's comment carries both measured ends, and the test passes under a
loaded `-n auto` full run.

```sh
.venv/bin/python -m pytest tests/test_held_phase.py -q
```

## References

- `tests/CLAUDE.md` § Budgets in tests; WP-1301 (the ramp this reproduces).

## Handover log

- **2026-09-29** — created, from WP-1469's session, where the guard failed
  once at 112 s under load and passed at 17.1 s alone. Next: the one task.

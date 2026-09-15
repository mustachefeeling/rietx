# WP-1404 — what recording every fit costs

Milestone: unscheduled · Status: ⬜
Depends on: 1403 (the layer being measured); 1401 (its baseline)

## Goal

A measured answer, quoted as a range, to whether every fit can afford to record
itself — and the authority to reopen WP-1403's design if it cannot. The number
reaches the handover and the milestone record; none of it becomes a test that
times anything.

## Context

WP-1403 makes recording the default for every `fit()` in the wild. That is a tax
on people who never asked for it, so it is settled by measurement rather than by
argument. This WP exists separately because **a measurement that cannot change
the design is not a gate**: it is licensed to send 1403 back, and if it never
could, it should not be a package.

### What is being priced

Verified in the tree 2026-09-13 and **re-verified 2026-09-15**, when the
`## Non-goals

- **No optimisation of the fit itself.** The two v1.1 speed fronts nobody owns
  (the per-reflection 19.4 %, WP-1121; the `refit=` choice, WP-1124) are not this
  WP's, however tempting they look once a profiler is open.
- **No new benchmark harness.** `examples/bench_refinement.py` is the
  measurement authority every speed WP quotes; add configurations to it, do not
  write a second one.
- **No timing assertion.** Every wall-clock number lands in prose.

## Tasks

- [ ] Add the five configurations to `examples/bench_refinement.py` as named
      keys, and a row per key to `tests/test_bench_refinement.py`.
- [ ] Run the matrix, alone, on one machine in one sitting. Nothing else running:
      these are wall-clock numbers and machine state moves them further than most
      changes do.
- [ ] The counted assertions (evaluation count identical, extra forwards exactly
      `n_stages`, flush count bounded) as ordinary tests.
- [ ] The measured numbers into this WP's handover and into the milestone
      record's appendix, as ranges, with venv and platform named.
- [ ] The verdict, written out: which gate applied (the 5 % or the control's own
      spread), whether the shipping candidate passed, and — if not — which of the
      three failure paths was taken and why.
- [ ] Snapshot and run-directory sizes per case, as a range, for WP-1406 to
      quote. WP-1403's one measured run is **204 kB** on the synthetic
      five-stage LaB6 case — `snapshot.json` 171 kB, event log 30.8 kB over 87
      events, `[dev]`, macOS arm64 — so the question this answers is how that
      scales with points, parameters and evaluations. The retention scan is
      once per *process*, not once per fit (0.2 ms at 10 runs, 2.2 ms at 100,
      27.6 ms at 1000), so it is on the first fit's path and nowhere else.
- [ ] Skill: **none**. WP-1406 carries the track's skill change; if a number
      here changes what an agent should do, say so in that WP's `### Inherited`.

## Acceptance

```sh
.venv/bin/python examples/bench_refinement.py --cases nac,cpd-2,trigger   # × 5 configurations × 3, run alone
.venv/bin/python -m pytest tests/test_bench_refinement.py tests/test_telemetry.py
```

The deliverable is the handover entry, not a green test. A session that ran the
matrix and reported "it seems fine" has not done this WP.

## References

- WP-1121 — the per-reflection 19.4 %, and how a speed claim is quoted here.
- WP-1113 — the evaluation-count mechanism analysis; what a thinned eval stream
  would cost a consumer.
- WP-1335 — the report costing 26× the fit, and the precedent for pricing a
  default before it becomes one.
- `tests/CLAUDE.md` § Running, and the root CLAUDE.md's testing headlines: quote
  wall clock as a range, never a figure; a budget in a test is a runaway guard,
  never a timer.

## Handover log

- **2026-09-13** — created. Separated from WP-1403 deliberately: a measurement
  folded into the WP it measures is a rubber stamp, because the session that
  built the thing is the session deciding whether it is fast enough. The failure
  paths are written down in advance for the same reason — the third one, shipping
  off by default and saying the premise did not survive, is the one that gets
  quietly avoided if it is not named before the numbers arrive.

# WP-1413 — the snapshot is what recording costs

Milestone: unscheduled · Status: ✅ 2026-09-15 — decimation 8.8-11.9× faster at
a bit-identical index set; `cpd-2` and `trigger` under 1.05×, `nac` at 1.23× and
unreachable without thinning the snapshot, which is the maintainer's call
Depends on: 1404 (the measurement that names this); 1402 (the code, and its one
binding constraint)

## Goal

The per-stage snapshot costs less, and the recorded fit comes in under WP-1404's
1.05× gate on every one of its three cases. Nothing a consumer reads off the
snapshot changes, and the decimated index set comes back bit for bit.

## Context

WP-1404 priced the default-on recorder and failed its own gate on two cases of
three, then measured where the cost actually is. Its § Findings is the authority
and this section restates only what a session needs to start.

**The bill is per stage and it is nearly constant.** Recording adds 16.7 to
21.9 ms a stage across three cases spanning a factor of 16 in fit length, so the
ratio orders by how long the fit runs: 1.279× on `nac` (0.357 s), 1.075× on
`cpd-2` (2.311 s), 1.030× on `trigger` (5.827 s). `[dev]`, macOS arm64, seven
interleaved repeats.

**The snapshot is 84 to 96 % of it**, at 16.0 to 18.4 ms a stage. The event log
is the rest, and WP-1404 measured that twice over: a caller's `events=<path>`
buys the whole stream for 1.005 to 1.012×, and dropping the stream *and* stubbing
the `_free_values` decode lands within noise of the full recorder. **So do not
reopen the decode.** WP-1403's mitigations 1 and 2 were withdrawn on that
evidence and re-deriving them is the first way to waste this WP.

**What is inside the 16-18 ms.** WP-1402 profiled the build at 9.3 to 14.2 ms:
`decimation_index` 6.6 to 7.1 ms of it, `json.dumps` 2.4 to 4.5, `model.evaluate`
0.3 to 5.7, everything else under 1 ms. The remainder of WP-1404's per-stage
figure is the forward work the recorder adds around the build, pinned by
`test_what_a_recorded_stage_costs_in_forward_evaluations`: one extra `evaluate`,
two extra `bragg_component` and three extra `background` calls a stage.

`decimation_index` is 2000 buckets of python and costs the same on a 22 003-point
pattern as on a 4165-point one, which is why it is the largest single item and
why it is the same item on every case.

### The constraint that governs the whole WP

**A faster decimation must return a bit-identical index set** (WP-1402). Three
consumers read it: the comparison UI, the GUI's window route, and the snapshot
with `viz/html.py`. A plot that disagreed with the comparison UI about which
points it drew would be a picture of a different fit. So the acceptance is an
equality assertion against the current implementation over every bench case, and
a candidate that is faster and *nearly* the same is a no-go rather than a
trade-off.

`_json_list`'s `tolist()` fast path is already taken and cannot be counted twice.

### The option that is not free

Writing the snapshot less often than every stage also removes the cost, and it is
not equivalent. A stage boundary is what `rietx watch` redraws on, so a thinned
snapshot is a slower live view, and the live view is the feature the track exists
to provide. If this WP ends up there, it says so in the milestone record and in
`using/refining.md`, because it changes what a watcher sees.

## Non-goals

- **No change to what the snapshot contains.** The payload is WP-1402's and its
  consumers are documented; this WP makes the same bytes cheaper to produce.
- **No reopening of the event stream.** Measured at 4 to 16 % of the bill and
  withdrawn. See Context.
- **No optimisation of the fit itself**, which is WP-1121's and WP-1124's ground.

## Findings

**2026-09-15 — WP-1402's split still holds.** One snapshot build on each bench
case's last stage, best of five, `[dev]` venv, macOS arm64, Python 3.12.12.

| | `nac` | `cpd-2` | `trigger` |
|---|---|---|---|
| points / snapshots / drawn | 22 003 / 6 / 7 385 | 7 251 / 9 / 5 907 | 4 165 / 8 / 4 117 |
| `build_snapshot` | 9.32 ms | 9.00 ms | 13.71 ms |
| `decimation_index` | 6.84 | 6.70 | 6.52 |
| `model.evaluate` | 0.30 | 0.39 | 5.63 |
| `stage_ticks` | 0.07 | 0.20 | 0.42 |
| `table.decode` / `model.background` | 0.01 / 0.01 | 0.02 / 0.00 | 0.03 / 0.01 |
| `json.dumps(payload)` | 4.46 ms (329 kB) | 3.08 ms (241 kB) | 2.31 ms (183 kB) |

WP-1402 measured `decimation_index` at 6.6-7.1 ms and `json.dumps` at 2.4-4.5;
both reproduce, the two figures outside those ranges being under 2 % out. The
decimation costs the same on 4 165 points as on 22 003, which is the shape of a
cost that is 2000 buckets of python rather than anything the data does.

`trigger`'s build is the outlier and it is not the snapshot's doing: its
`model.evaluate` is 5.63 ms against 0.30 on `nac`, because 1 188 line-reflection
pairs on 4 165 points is the dispatch-heavy case.

**2026-09-15 — the decimation, before and after.** Best of seven, one process,
same arrays. The three bench pattern sizes, three curves, budget 4000:

| points | loop | scan | |
|---|---|---|---|
| 4 165 | 6.66 ms | 0.558 ms | 11.9× |
| 7 251 | 6.78 ms | 0.648 ms | 10.5× |
| 22 003 | 6.93 ms | 0.785 ms | 8.8× |

The cost now moves with the pattern rather than sitting flat, which is the
signature of the python loop having been the whole of it.

**2026-09-15 — the matrix, before and after on one machine.** Two runs of
`--cases nac,cpd-2,trigger --configs off,record --repeats 7`, ten minutes apart,
each internally interleaved. Quoted as median / min of seven, beside the control
spread that sets the harness's own gate.

| case | before | after | control spread, after |
|---|---|---|---|
| `nac` (0.354 s, 6 stages) | 1.300× / 1.286× | **1.233× / 1.200×** | 6.4 % |
| `cpd-2` (2.43 s, 9 stages) | 1.062× / 1.076× | **1.049× / 1.032×** | 7.3 % |
| `trigger` (5.90 s, 8 stages) | 1.028× / 1.038× | **1.031× / 1.031×** | 2.3 % |

`cpd-2` crosses the 1.05 line and `trigger` was already under it. `nac` does not
and cannot; § The gate on `nac` says why. `trigger`'s pair is one measurement
twice: the change is worth 49 ms on a 5.9 s fit, which is 0.8 points of ratio
against a 2.3 % spread, so it is correctly invisible.

A third run was discarded rather than quoted. Its control spreads were 46.1,
17.2 and 32.1 % because the desktop was busy, and the load average reached 10.4.
An arm measured under that is measuring the box.

### The gate on `nac`

**The 1.05× gate is unreachable on `nac` by arithmetic, and no further
optimisation of the snapshot reaches it.** The fit is 0.354 s over 6 stages, so
the whole 5 % budget is 17.7 ms, or 2.95 ms a stage. What a stage now costs,
best of seven, end to end through `write_snapshot`:

| | `nac` | `cpd-2` | `trigger` |
|---|---|---|---|
| `write_snapshot` | 8.30 ms | 6.54 ms | 10.56 ms |
| — `json.dumps` | 4.56 | 3.12 | 2.35 |
| — `decimation_index` | 0.80 | 0.66 | 0.56 |
| — `model.evaluate` | 0.30 | 0.40 | 5.66 |
| — round + to-list, 4 curves | 0.56 | 0.45 | 0.32 |
| — `compute_statistics` | 0.18 | 0.08 | 0.06 |
| — `stage_ticks` | 0.07 | 0.20 | 0.40 |
| — write + rename | 0.15 | 0.15 | 0.14 |
| whole-fit share | 6 × 8.30 = 50 ms | 9 × 6.54 = 59 ms | 8 × 10.56 = 84 ms |

`nac`'s snapshot alone is 50 ms against a 17.7 ms budget, so the gate would fail
on this case with the decimation, the rounding, the statistics and the ticks all
free. `json.dumps` is now the largest item and it is 4.56 ms of a 2.95 ms
budget on its own.

Serialising 329 kB is not a cost a faster serialiser removes either, because the
payload size is the thing: `nac` draws 7 385 points from a 4 000 budget, the
three curves disagreeing about where their extremes are. Cutting that is cutting
what the snapshot contains, which this WP's non-goals reserve.

So the remaining lever is the one § The option that is not free already named:
write the snapshot less often than every stage. That is a product decision about
what a watcher sees, not an optimisation, and it is left to the maintainer.

## Tasks

- [x] Profile one snapshot build on each bench case, and confirm WP-1402's split
      still holds on the current tree before optimising anything.
- [x] Make `decimation_index` cheap. It buckets 2000 spans in python over an
      already-sorted axis, which is a `searchsorted` shape.
- [x] Pin the bit-identity: the new index set equals the old one element for
      element on every bench case and on the acceptance patterns, as an ordinary
      test.
- [x] Re-run WP-1404's matrix, interleaved, and report whether `record` now comes
      in under 1.05× on all three cases. The harness already has the
      configurations; `--configs off,record --repeats 7` is the selection.
      *Two of three: `cpd-2` and `trigger` pass, `nac` does not.*
- [x] If the gate still fails on `nac`, say so and price the remaining term
      rather than iterating: a 0.357 s fit has 6 stages, so the whole budget is
      about 18 ms a stage. *§ The gate on `nac`.*
- [x] Update `docs/manual/using/refining.md` and the skill's
      `references/watching.md` § 9d.7 **only if the measured range moves**. Both
      quote 1.03-1.28× today and WP-1404 confirmed that figure, so a change here
      is a change there. *It moved to 1.03-1.23×; both updated and the two
      committed skill copies re-synced.*

## Acceptance

```sh
.venv/bin/python examples/bench_refinement.py --cases nac,cpd-2,trigger --configs off,record --repeats 7
.venv/bin/python -m pytest tests/test_snapshot.py tests/test_compare_ui.py tests/test_bench_refinement.py
```

The deliverable is the ratio, quoted as a range with its venv and platform, plus
the bit-identity test. A faster build that moved one index is a regression.

## References

- WP-1404 § Findings — the measurement this WP acts on, and the two mitigations
  it withdrew.
- WP-1402 — the snapshot's build, its parts, and the bit-identity constraint.
- `tests/CLAUDE.md` § Running — the interleaving rule WP-1404 learned the hard
  way: blocked repeats measure the machine, not the change.

## Handover log

- **2026-09-15 (2nd session)** — Recording a fit costs less, and what it still
  costs is now settled rather than suspected. The per-stage picture was mostly
  one python loop, which bucketed the pattern two thousand times to decide which
  points a viewer draws; that loop is gone, replaced by a segmented scan that
  returns the same points and runs 8.8 to 11.9 times faster. Two of the three
  benchmark fits now record for under 5 % of their own wall clock, where before
  only one did. The third cannot, and not because anything is slow: a 0.354 s
  fit has a 5 % budget of 17.7 ms, and its six snapshots cost 50 ms with the
  decimation, the rounding, the statistics and the ticks all free. The only
  lever left is writing the picture less often than every stage, which changes
  what a watcher sees, so it is a decision about the feature rather than an
  optimisation.

  **Done.** All six tasks. `viz.compare.decimation_index` finds each bucket's
  min and max with `reduceat` over the distinct edges instead of 2000 python
  slices. The manual and the skill move from 1.03-1.28× to 1.03-1.23×, both
  committed skill copies re-synced. Root CLAUDE.md gains one clause, that a
  per-stage charge is judged on the shortest fit.

  **Measured** — `[dev]` venv (numba 0.67.0, no jax, no torch), macOS arm64,
  Python 3.12.12, rietx 1.4.0, numpy 2.5.3. The decimation alone, best of seven
  in one process: 6.66→0.558 ms at 4 165 points, 6.78→0.648 at 7 251,
  6.93→0.785 at 22 003. The matrix twice on one machine ten minutes apart,
  seven interleaved repeats, median/min: `nac` 1.300/1.286 → 1.233/1.200,
  `cpd-2` 1.062/1.076 → 1.049/1.032, `trigger` 1.028/1.038 → 1.031/1.031. Rwp
  bit-identical across every arm and both runs. § Findings holds the per-part
  breakdown and the third, discarded run.

  **Counts.** Fast selection on this branch: 4854 passed, 132 skipped in 212 s.
  The 27 new tests are all passes and add no skip, so passed moved by exactly
  27 and skipped did not move.

  **Gotchas.** Ties are the whole difficulty: `argmin` keeps the *first* index
  attaining an extreme, which a segmented scan reproduces only on purpose, and
  a real background ties constantly. NaN takes the old loop, because `argmin`
  returns the first NaN while a running minimum propagates it. The oracle lives
  in the test rather than in the library, so the loop is still readable beside
  what replaced it. `trigger`'s ratio did not move and should not have: 49 ms
  on a 5.9 s fit is 0.8 points against a 2.3 % control spread.

  The index-set contract was deliberately **not** promoted to the root
  CLAUDE.md. It is already in the function's docstring, in the test that
  enforces it by name, and in WP-1402, and the file sits at its 811-line cap.

  **Next**, in order. (1) The maintainer decides whether the snapshot is written
  every stage or less often; nothing else moves `nac` and the cost of deciding
  is one sentence in `using/refining.md` about what a watcher sees. (2) If the
  answer is "every stage", `nac`'s 1.23× is the shipping figure and WP-1404's
  1.05× gate should be restated as a rule about fit length rather than a target,
  since no sub-second fit can meet it. (3) `json.dumps` at 4.56 ms a stage is
  the largest item left, and it is payload size rather than serialiser speed:
  `nac` draws 7 385 points from a budget of 4 000 because its three curves
  disagree about where their extremes are. Cutting that is cutting what the
  snapshot contains, which this WP's non-goals reserve.

- **2026-09-15** — created by WP-1404's session, on the maintainer's decision to
  keep recording on by default and cut the cost instead. WP-1404 named three
  failure paths in advance and its own measurement killed two of them, because
  all three were written believing the per-evaluation decode was the expense.
  This WP is the fourth path, and it exists because the measurement found the
  cost somewhere the plan had not looked.

# WP-1413 — the snapshot is what recording costs

Milestone: unscheduled · Status: ⬜
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

## Tasks

- [ ] Profile one snapshot build on each bench case, and confirm WP-1402's split
      still holds on the current tree before optimising anything.
- [ ] Make `decimation_index` cheap. It buckets 2000 spans in python over an
      already-sorted axis, which is a `searchsorted` shape.
- [ ] Pin the bit-identity: the new index set equals the old one element for
      element on every bench case and on the acceptance patterns, as an ordinary
      test.
- [ ] Re-run WP-1404's matrix, interleaved, and report whether `record` now comes
      in under 1.05× on all three cases. The harness already has the
      configurations; `--configs off,record --repeats 7` is the selection.
- [ ] If the gate still fails on `nac`, say so and price the remaining term
      rather than iterating: a 0.357 s fit has 6 stages, so the whole budget is
      about 18 ms a stage.
- [ ] Update `docs/manual/using/refining.md` and the skill's
      `references/watching.md` § 9d.7 **only if the measured range moves**. Both
      quote 1.03-1.28× today and WP-1404 confirmed that figure, so a change here
      is a change there.

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

- **2026-09-15** — created by WP-1404's session, on the maintainer's decision to
  keep recording on by default and cut the cost instead. WP-1404 named three
  failure paths in advance and its own measurement killed two of them, because
  all three were written believing the per-evaluation decode was the expense.
  This WP is the fourth path, and it exists because the measurement found the
  cost somewhere the plan had not looked.

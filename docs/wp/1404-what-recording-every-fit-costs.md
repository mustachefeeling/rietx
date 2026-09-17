# WP-1404 — what recording every fit costs

Milestone: v1.5 · Status: ✅ 2026-09-15 — the default-on recorder costs 1.03-1.28×, fails the 1.05× gate on two cases of three, and 84-96 % of it is the per-stage snapshot rather than the event stream the WP was written about; recording stays on and WP-1413 cuts the snapshot
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
`### Inherited` block was folded in here and deleted. WP-1403 carries the same
table with the code references, and this WP is the one that puts numbers
against it.

- **Per residual evaluation**: `_free_values` is a second full `table.decode`,
  running *before* the sink is consulted, then `json.dumps` and a write. The
  write is **buffered** since WP-1403: `eval` lines sit in the handle's own
  buffer and reach the disk on a `runs.FLUSH_INTERVAL_SECONDS` (0.2 s) cadence,
  while every other kind flushes as written. So the syscall pair this WP was
  drafted against is now a `dumps` and a buffer append. The decode itself was
  left exactly as it was (`least_squares.py:822`, called at `:866` and `:1153`),
  which is what made WP-1403's mitigation 2 the obvious first move if the gate
  failed. **WP-1401 could not split the decode from the serialisation** and left
  that split here. § Findings § The premise this WP was written on is wrong is
  the answer, and it is that neither half matters.
- **Per stage**: one extra forward evaluation for a real `stage_end.rwp`
  (`refine.py:1834`, inside the `events is not None` guard), the recorder's own
  snapshot, and two `model_copy(deep=True)` from `_abandon_on_cancel`, which
  every recorded fit now pays since WP-1405 attached a cancel token to one
  unconditionally.
- **Per stage**: `decimation_index` buckets in a python loop. WP-1402 priced it
  at **6.6-7.1 ms a stage**, 50-75 % of a snapshot's build and the same number
  on all three cases, because it is 2000 buckets of python whatever the pattern
  length; the rest of a build is `json.dumps` 2.4-4.5 ms and `model.evaluate`
  0.3-5.7 ms, 9.3-14.2 ms in total. `[dev]`, macOS arm64, best of five per
  part. Start from those rather than re-deriving them, and note that
  `_json_list`'s `tolist()` fast path is **already taken**, so it cannot be
  counted again as a win.

### The matrix

Three cases from `examples/bench_refinement.py`, chosen to bracket both axes
rather than to be representative:

| case | why |
|---|---|
| `nac` | many points, few parameters: evaluation cost high, payload small |
| `cpd-2` | many parameters and phases: payload large per evaluation |
| `trigger` | dispatch-heavy, many evaluations: the syscall and decode term |

Five configurations, one machine, one sitting. **This list is 2026-09-15's**:
WP-1405 shipped an unconditional cancel token on every recorded fit, which
collapsed the original configurations 2 and 3 into one row and freed the slot
`events-path` now holds.

0. `off` — recording declined (`telemetry=False`). **The control, and its own
   repeat spread is reported first.**
1. `no-eval` — recorder on, stage boundaries only. The package has no such
   knob, so this row is a **harness scaffold** and says so wherever it is
   quoted; what it prices is the ceiling of WP-1403's mitigations 2 and 3
   together, which is the headroom available if the gate fails.
2. `record` — the shipping default: recorder on, eval events buffered, cancel
   token attached. The original configurations 2 and 3 are this single row.
   WP-1405 measured the token at **1.0036× median, 1.0019× on the minima**
   (three-stage synthetic LaB6, 47 evaluations, interleaved arms, n=9 each,
   Rwp bit-identical), bounding its two components separately: the two
   `model_copy(deep=True)` run 132 µs at 2 atoms, 350 µs at 16, 4.44 ms at 256
   and 19.3 ms at 1024, **per stage**, and the solver's extra residual wrapper
   is **37 ns per evaluation**, so 0.19 s worst case at 1024 atoms over ten
   stages. That interleaved instrument is finer than this matrix, so **do not
   re-derive the token's cost here**; a disagreement is a finding and not noise,
   because those numbers are why eager attachment shipped.
3. `events-path` — `events=<path>`, no recorder. WP-1401 measured it at
   **1.01-1.03× throughout**, so it is the bridge that says whether this
   sitting and that one are comparable at all.
4. `live` — today's `events=LiveSession(dir)`, no recorder: the reference for
   what a user pays when they *do* ask. WP-1401: **1.47-1.49× on `nac`,
   1.10× on `cpd-2`, 1.04-1.05× on `trigger`**, the `events=` path costing
   0.1-0.3 ms a residual evaluation and a log running about 1 kB an event,
   dominated by each `eval`'s `values` array. WP-1402 then took the whole of it
   to **1.03-1.28×** by replacing the plotly page with `snapshot.json`.

Configurations 0, 3 and 4 need none of this track's code and were measured in
WP-1401 on `[dev]` (numba 0.67.0, no jax, no torch), macOS arm64 (Darwin
25.5.0), python 3.12.12, rietx 1.4.0, machine checked idle, three repeats over
two sittings. They are repeated here on the same machine in the same sitting,
because a number carried across machines is not a comparison.

Recorded per configuration: wall clock (median and minimum of seven), **total
residual evaluations**, bytes written, lines written, flush count. The
evaluation count is the assertion that telemetry changed no number.

### The gate, in three channels

**Asserted in a test**, because these are machine-independent and a count is not
a timer:

- the total residual-evaluation count is identical with and without the recorder;
- the extra forward evaluations number exactly `n_stages`;
- the flush count is bounded by the non-`eval` event count plus the run's
  duration over the flush interval.

**Measured into the handover and the milestone record, never into a test** — a
wall-clock budget in a test is a runaway guard, never a timer:

- recorder-on against off, median of three, **quoted as a range across the three
  cases**, with the venv and the platform named;
- **gate: ≤ 1.05× on every case.** Five per cent because `stage_reports` is
  accepted at 2.5× as an *opt-in*, and the intermediate-ftol schedule was worth
  1.2–1.6× fewer evaluations; a default-on tax must sit well inside both.
- **And the honest clause: if the control's own three-run spread exceeds 5 %,
  the gate becomes that spread and this WP says so.** A gate tighter than the
  measurement's resolution is a coin toss wearing a check's clothes.

**Reported, with no invented number**: bytes per run for each case, as a range.
"How big does this get" is the first question a reader asks, and WP-1406's manual
page quotes this and nothing else.

### What a failure means

If the shipping candidate does not come in under the gate, the outcome is
recorded, not worked around. In order of preference:

1. Adopt WP-1403's mitigation 2 — let the sink answer whether it wants the
   values, so a thinned log is cheap in CPU and not only in bytes — and
   re-measure.
2. Adopt mitigation 3, thinning the eval stream, **and record that the automatic
   log no longer reconstructs the WP-1113 trajectory**. That is a semantic
   change and it is not made quietly. It no longer costs the cancel probe:
   WP-1405 hung that on the *unthinned* evaluation boundary precisely so
   thinning cannot reach it, and `test_the_probe_needs_no_event_at_all` is the
   guard to re-run rather than the assumption to make.
3. Ship WP-1403 **off by default**, with the env variable turning it on, and say
   plainly in the milestone record that the track's premise did not survive its
   own measurement. That is a legitimate ending, and naming it here is what stops
   it being avoided.

## Non-goals

- **No optimisation of the fit itself.** The two v1.1 speed fronts nobody owns
  (the per-reflection 19.4 %, WP-1121; the `refit=` choice, WP-1124) are not this
  WP's, however tempting they look once a profiler is open.
- **No new benchmark harness.** `examples/bench_refinement.py` is the
  measurement authority every speed WP quotes; add configurations to it, do not
  write a second one.
- **No timing assertion.** Every wall-clock number lands in prose.

## Tasks

- [x] Add the five configurations to `examples/bench_refinement.py` as named
      keys, and a row per key to `tests/test_bench_refinement.py`.
- [x] Run the matrix on one machine in one sitting, **interleaved**. Not alone:
      the box carried its desktop and another session's mypy, and a gate waiting
      for it to go quiet never fired. Interleaving the configurations inside each
      repeat is what makes the comparison hold, and the control's own spread
      (1.1-5.9 %) is what says so. § Findings § The instrument.
- [x] The counted assertions (evaluation count identical, extra forwards, flush
      count bounded) as ordinary tests, in `tests/test_telemetry.py`.
      **"Extra forwards exactly `n_stages`" was a guess and it was the smallest
      of three numbers.** Measured 2026-09-15 on the five-stage synthetic:
      `evaluate` +1 a stage, `bragg_component` +2, `background` +3. The middle
      arm says why — a caller's own `events=` already pays the real
      `stage_end.rwp` (+1 Bragg, +1 background, no second y_calc), and what the
      recorder adds on top is its snapshot, which is the same forward work a
      `LiveSession` has always done. So the recorder's per-stage forward cost
      is not new work; what is new is that it happens unasked.
- [x] The measured numbers into § Findings above, this WP's handover entry and
      the v1.4 record's narrative, as ranges, with venv and platform named.
- [x] The verdict, written out: § Findings § The verdict. The gate was 5 % on
      `cpd-2` and `trigger` and the control's own 5.9 % spread on `nac`; the
      shipping candidate **failed on two cases of three**. Which failure path
      follows is the one open question, because the measurement withdrew two of
      the three the WP had written down and added a fourth it could not have
      named.
- [x] Snapshot and run-directory sizes per case, as a range: § Findings
      § Bytes on disk. **358-534 kB a run.** WP-1406 is closed and its two
      quoted figures turn out to need no correction, which § The manual and the
      skill need no correction records. The comparison point is WP-1403's one
      measured run, 204 kB on the synthetic five-stage LaB6 case.
- [x] Skill: **none**, as planned, and now for a measured reason. WP-1406's two
      figures stand unchanged, so nothing an agent reads moves.

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

## Findings — the matrix, measured 2026-09-15

`[dev]` venv (numba 0.67.0, no jax, no torch), macOS arm64 (Darwin 25.5.0),
python 3.12.12, numpy 2.5.3, rietx 1.4.0. Seven interleaved repeats a
configuration, three cases, one sitting. The machine carried its ordinary
desktop load and another session's mypy throughout, so it was not idle. §&nbsp;The
instrument says what was done about that and why the numbers survive it.

### The table

Ratio of medians against `off`, with the minimum of seven beside it. The two
agree to 0.01 on every row, so neither is carrying the machine.

| case | control spread | `no-eval` | `record` | `events-path` | `live` |
|---|---|---|---|---|---|
| `nac` — 22 003 pts, 6 stages, 39 evals | 5.9 % | 1.286× | **1.279×** | 1.012× | 1.261× |
| `cpd-2` — 7251 pts, 9 stages, 329 evals | 1.1 % | 1.062× | **1.075×** | 1.010× | 1.058× |
| `trigger` — 4165 pts, 8 stages, 232 evals | 2.5 % | 1.040× | **1.030×** | 1.005× | 1.026× |

`nfev` and Rwp were identical across all five configurations on every case, to
every digit printed. Recording changes no number, and the counted assertions in
`tests/test_telemetry.py` are what keep that true.

### The verdict

**The shipping default costs 1.03 to 1.28× and it fails this WP's gate on two
cases of three.** The gate was 1.05×, widened on any case whose control spread
exceeded it. `nac` fails at 1.279× against a widened 1.059×. `cpd-2` fails at
1.075× against 1.050×. `trigger` passes at 1.030×.

That is the answer to the question this WP was opened to ask. What the failure
means took a second measurement, and it is not what the WP expected.

### The cost is per stage, and it is nearly constant

Recording adds **16.7 to 21.9 ms a stage**, and the three cases span a factor of
16 in fit length while that number moves by a third. So the ratio orders by how
long the fit runs, and not at all by how big the pattern is: `nac` carries the
most points, finishes in 0.36 s, and pays the worst ratio of the three.

| case | fit (median, `off`) | recorder, per stage | of which the snapshot |
|---|---|---|---|
| `nac` | 0.357 s | 16.7 ms | 16.0 ms (96 %) |
| `cpd-2` | 2.311 s | 19.2 ms | 16.6 ms (86 %) |
| `trigger` | 5.827 s | 21.9 ms | 18.4 ms (84 %) |

This settles the ordering question WP-1406 raised and could not answer. Its
manual page and §&nbsp;9d.7 had once attributed the spread to how many points a
pattern has, corrected that to a near-constant absolute cost on WP-1402's
evidence, and left the re-measurement owed. The correction was right.

### The premise this WP was written on is wrong

WP-1404 named the per-evaluation `_free_values` decode "the dominant term". It
is 4 to 16 % of the bill, and the per-stage snapshot is the rest.

Two independent measurements say so. A caller's own `events=<path>`, which buys
the whole event stream and no snapshot, runs **1.005 to 1.012×** whole-fit, or
0.073 to 0.121 ms a residual evaluation. And `no-eval`, which is the recorder
with its event stream dropped *and* the decode stubbed out, sits within noise of
`record` on all three cases: 1.286 against 1.279, 1.062 against 1.075, 1.040
against 1.030. Removing the eval stream entirely buys nothing measurable.

**So WP-1403's mitigations 1 and 2 are withdrawn as candidates.** Letting the
sink answer whether it wants the values, and thinning the eval stream, are each
chasing a term worth at most 1.2 % of a fit. Neither is worth the semantic
change it costs, and mitigation 2's whole appeal was that it looked free.

### What that leaves

The WP wrote its three failure paths in advance, on the belief that the eval
stream was the expense. Two of them are now measured dead. The third, shipping
off by default, is live but is a decision the maintainer owns rather than one a
measurement makes.

**The maintainer's decision, 2026-09-15: keep recording on by default, and cut
the snapshot cost instead.** That is a fourth path, and the WP could not have
named it because it was written believing the eval stream was the expense. It is
now [WP-1413](1413-the-snapshot-is-what-recording-costs.md).

The snapshot is 16.0 to 18.4 ms of the 16.7 to 21.9, and WP-1402 already priced
its two halves: `decimation_index` at 6.6-7.1 ms a stage, the rest of the build
at 2.7-7.1. One constraint governs that work and it is load-bearing. Three
consumers read the decimated index set, so a faster decimation must return the
same one bit for bit, or the comparison UI and the plot disagree about which
points they drew.

Writing the snapshot less often than every stage is the other half of that
option, and it is not free either. A stage boundary is what a watcher redraws
on, so a thinned snapshot is a slower live view, which is the feature the track
exists to provide.

### The manual and the skill need no correction

WP-1406 left a conditional: if this number landed outside 1.03-1.28×, then
`docs/manual/using/refining.md` and the skill's `references/watching.md`
§&nbsp;9d.7 both needed correcting, since both quote the `LiveSession` path as
the nearest measured proxy for a recorded fit. **The recorded fit measures 1.03
to 1.28×**, and `live` and `record` land within 0.02 of each other on every
case. The proxy was sound and the conditional is discharged with no edit.

It was sound for a reason worth keeping: a `LiveSession` and the recorder do the
same per-stage forward work, which
`test_what_a_recorded_stage_costs_in_forward_evaluations` pins at one extra
`evaluate`, two extra `bragg_component` and three extra `background` calls a
stage. The two paths were always going to cost the same.

### Bytes on disk

A recorded run is **358 to 534 kB** on these three cases, against WP-1403's
204 kB on the five-stage synthetic LaB6. The two halves scale differently.

| case | run directory | `snapshot.json` | event log | log lines |
|---|---|---|---|---|
| `nac` | 358.0 kB | 329.1 kB | 27.2 kB | 59 |
| `cpd-2` | 533.5 kB | 240.6 kB | 288.2 kB | 358 |
| `trigger` | 442.7 kB | 183.0 kB | 255.8 kB | 258 |

`snapshot.json` is overwritten each stage and does not grow with the run. The
event log does, at roughly 0.8 kB an `eval` line, so its size follows the
evaluation count times the free-parameter count. `cpd-2` carries 51 free
parameters over 329 evaluations and its log is ten times `nac`'s.

Flush counts were 15, 27 and 41 against 14, 20 and 18 non-`eval` events, which
is the buffering doing its job on runs of 0.46, 2.48 and 6.00 s.

### The instrument

**Blocked repeats measure the machine.** The first run of this matrix put every
repeat of one configuration before the next configuration started, so each one
occupied a contiguous slice of wall clock and any drift landed on it entire. It
produced `events=<path>` at 0.816× a bare fit on `nac`, which is faster than not
recording, and on `cpd-2` a recorder cheaper than the event stream it contains.
Control spreads were 11.4 % and 13.2 %.

Interleaving the configurations inside each repeat fixed it, and the control
spread fell to 1.1-5.9 %. WP-1405 arrived at the same shape from the other end
when it interleaved the arms of one fit to price a cancel token. That is why its
1.0036× is a finer number than anything in this table, and the harness now
carries the reason at the loop.

Two smaller notes. The matrix measures the per-fit cost and excludes the
retention scan, which `run_root()` performs once a process and WP-1403 priced at
0.2-27.6 ms; `telemetry=<scratch dir>` skips it. And this session lost about
twenty minutes to a wrapper script that waited for a load average below 2.0
before starting, on a desktop whose ambient load sits near 3.5. Interleaving is
the defence that works. A quiet-machine gate is a wish.

## Handover log

- **2026-09-15** — We now know what it costs a user to have every fit record
  itself, and the answer is 1.03 to 1.28× the fit, which fails the gate this WP
  set for itself on two of its three cases. The more useful half is that the
  cost is not where anyone thought. This WP was written believing the
  per-evaluation parameter dump was the expense, and that term turns out to be 4
  to 16 % of the bill; the per-stage picture is the rest. So the two cheap fixes
  WP-1403 had lined up are dead, each worth at most a hundredth of a fit, and
  the thing worth attacking is a snapshot builder nobody suspected. The
  maintainer's call was to keep recording on by default and go after the
  snapshot, which is WP-1413. Nothing a user reads needed correcting: the manual
  and the skill already quote 1.03-1.28× from the live-view path, and the
  recorder measures the same, because the two do the same work per stage.

  **Measured** — `[dev]` venv (numba 0.67.0, no jax, no torch), macOS arm64
  (Darwin 25.5.0), python 3.12.12, numpy 2.5.3, rietx 1.4.0, seven interleaved
  repeats a configuration. Full table and decomposition in § Findings above.
  `record` 1.279× on `nac`, 1.075× on `cpd-2`, 1.030× on `trigger`, against
  gates of 1.059× (the control's own spread), 1.050× and 1.050×. In absolute
  terms 16.7 to 21.9 ms a stage, of which the snapshot is 16.0 to 18.4. The
  event stream alone is 1.005 to 1.012×, or 0.073 to 0.121 ms an evaluation. A
  run directory is 358 to 534 kB. `nfev` and Rwp identical across all five
  configurations on every case.

  **Suite** — fast selection **4827 passed, 132 skipped, 3:14-3:20**, `[dev]`,
  macOS arm64, against WP-1405's 4818/132 on the same venv: **+9 passed, skips
  unchanged**, which is exactly the nine tests added (three in
  `test_telemetry.py`, six in `test_bench_refinement.py`). The full selection
  did **not** run and deliberately: this WP changed no file under `src/`, so it
  cannot move a measured number, and the ladder in `tests/CLAUDE.md` § Running
  reserves that rung for changes that can.

  **Done** — the configuration axis in `examples/bench_refinement.py`
  (`--configs`, five keys, defaulting to `off` because WP-1403 made recording
  the default and an unconfigured run would silently re-baseline every historic
  row); the comparison block with its ratio of medians, minimum of N, byte and
  flush accounting; three counted assertions in `test_telemetry.py`; six
  structural rows in `test_bench_refinement.py`; the verdict and decision in
  § Findings; the v1.4 record's narrative entry; WP-1413 opened.

  **Gotchas** — three, all paid for.

  1. **Blocked repeats measure the machine.** The first matrix ran every repeat
     of one configuration before the next and produced orderings that cannot
     happen: a telemetry path faster than no telemetry, a recorder cheaper than
     the event stream inside it. Control spreads were 11.4 and 13.2 %.
     Interleaving inside each repeat took them to 1.1-5.9 % and the
     impossibilities went away. The rule is now rule 2 of the harness docstring.
     It did **not** go into `tests/CLAUDE.md`, which sits at exactly its
     275-line cap, and buying room by cutting someone else's facts is not the
     trade that cap intends.
  2. **A quiet-machine gate is a wish.** A wrapper that waited for a load
     average below 2.0 never fired on a desktop whose ambient load is ~3.5, and
     cost this session about twenty minutes of doing nothing. Interleaving is
     the defence that works; the sitting's load is recorded instead.
  3. **My own prune deleted three sections of this file.** The script cut from
     `t.index("### Inherited")`, which matched that phrase inside the text it had
     just inserted, so the cut ran from the wrong anchor and took "The matrix",
     "The gate" and "What a failure means" with it. Restored from `28429810` in
     `f1252fcd`. Anchor a deletion on something the replacement cannot contain.

  **Review** — `/code-review high --fix` found seven, all in the harness, all
  applied, none declined. The one worth knowing: `runs.enabled()` lets the
  environment outrank `telemetry=`, so under `RIETX_TELEMETRY=0` a recording
  configuration attaches no recorder, times the control and prints a ratio, and
  the only trace is an all-zero accounting row — which is what an honest control
  prints too. `main` refuses that before any timed work now. This session's
  matrix is unaffected and the accounting rows are the proof: 59 to 358 log
  lines with non-zero snapshot bytes and flush counts on every `record` row.
  Also fixed: a stream configuration on a series case raised too late to save
  the run, an empty `--configs` built every case and timed none, and the
  harness never closed the `LiveSession` it built.

  **Next**, in order. WP-1413 is the work this WP created and it starts from
  § Findings rather than from scratch: confirm WP-1402's split still holds, then
  make `decimation_index` cheap under the bit-identity constraint, then re-run
  `--configs off,record --repeats 7` and say whether `record` comes in under
  1.05× on all three. Two prohibitions travel with it and are already written
  into its Context: do not reopen the `_free_values` decode, and do not count
  `_json_list`'s `tolist()` fast path twice. If 1413 moves the measured range,
  `using/refining.md` and the skill's `references/watching.md` § 9d.7 both need
  the new figure; today neither does.

- **2026-09-13** — created. Separated from WP-1403 deliberately: a measurement
  folded into the WP it measures is a rubber stamp, because the session that
  built the thing is the session deciding whether it is fast enough. The failure
  paths are written down in advance for the same reason — the third one, shipping
  off by default and saying the premise did not survive, is the one that gets
  quietly avoided if it is not named before the numbers arrive.

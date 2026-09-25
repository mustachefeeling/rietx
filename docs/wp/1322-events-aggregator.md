# WP-1322 — the run is instrumentable, and nothing says so

Milestone: unscheduled · Status: ⬜
Depends on: —
Priority: P3 2026-09-23 — a view over events already written

## Goal

The telemetry the package already emits becomes legible without a GUI — a
post-hoc aggregator over an `events.jsonl`, sibling to `watch` and `html` —
and becomes discoverable, so the next agent that drives a series does not
switch it off. The defaults asymmetry that made switching it off the
accidental norm is decided, either way, on the record.

## Context

From issue #207 (the 2026-09-01 benchmarking campaign; the contributor has
offered the aggregator as a PR).

**The finding.** Three independent subagents, each given a benchmarking
task and no instructions about how to drive rietx, all found and read the
packaged skill in full by three different routes — and **all three wrote
`history=False`**, five occurrences, on both `Refinement` and
`SequentialRefinement`. No event log existed afterwards; reconstructing
timing from the agents' own transcripts recovered **2.7–16.6 %** coverage
and nothing inside a solve. One instrumented fit
(`EventStream(path=…)` + `stage_reports=True`) emitted 288 records —
`fit_start`, 7× `stage_start`, 274× `eval`, 5× `stage_end`, `fit_end` —
with `stage_end` carrying `termination` and `held`/`released`: strictly
better than anything external instrumentation can recover.

**Two causes, both cheap.** (1) The defaults are asymmetric and the
asymmetry is deliberate: `Refinement.history` defaults `True`
(`refine.py`), `SequentialRefinement.history` defaults `False`
(`sequential.py` — "a long series makes a lot of files", a documented
reason). (2) Nothing in the skill's fitting path says the run is
instrumentable: the series and judging references teach what to check in a
result and never mention `events=`, `history=` or `stage_reports=`.

**Task 1 — `rietx events <log.jsonl> [--json]`.** Dependency-free,
consuming only rietx's own format through the existing primitives
(`read_events`/`read_records`, today consumed only by `history/tree.py`).
Reports: fits and stages counted, wall-clock total and per stage name, a
histogram of `termination` values, the most frequently `held` parameter
paths, first/last Rwp. On the campaign's runs the per-stage timing showed
one stage dominating a whole series, and the held-path histogram was a
faster route to "the data cannot see this phase" than reading per-pattern
reports. The contributor asked for the shape rather than guessing: this WP
records it — a CLI subcommand sibling of `watch`/`html`, thin over a plain
function in `rietx.history` so a CI job can call either. If the offered PR
arrives, this WP becomes its review against that spec plus the two
rietx-side tasks below.

**Task 2 — the defaults decision. DISCHARGED 2026-09-15 (WP-1406), by
removal of its premise, and neither flipped nor deferred.** The task was to
decide which knob to flip so that an agent would have a log. WP-1403 shipped
2026-09-15 and every fit now writes a run directory whether or not `history` or
`events=` was passed, so no defaults asymmetry decides coverage any more. The
asymmetry itself survives, `Refinement.history` defaulting `True` and
`SequentialRefinement.history` `False`, and it is now a question about history
nodes alone rather than about whether a run leaves a record.

Nothing was flipped, so there is no behaviour change and nothing to release-note.
Its original text, for anyone reopening it: flip `SequentialRefinement.history`
to match `Refinement`'s, or keep it and make the skill carry the asymmetry out
loud, decided against the 3/3 evidence and the documented disk-cost reason.

**Task 3 — the skill line.** `references/series.md` (all committed copies)
gains the sentence the campaign says would have saved the reconstruction:
pass `history=<path>`/`events=EventStream(path)` when you need a run
record; `stage_end` carries the termination criterion.

**One vocabulary, shared with 1317.** Issue #133's scrubber is the
interactive consumer of the same substrate ("same substrate, different
consumer" — #207's own framing): the aggregator's `termination` histogram
and held-path counts summarise exactly the marker vocabulary 1317 reads
from `SeriesResult`, so neither surface invents a second set of names.

### Inherited

- **2026-09-25, from a transcript review of an agent session on `in-situ
  series 1`: the records were there and the report was still wrong.** The user
  asked the agent to report its own metrics. The session left 887 run
  directories in `.rietx/runs` (843 `done`, 44 `failed`), each with its
  `meta.json`, `status.json` and log. The agent counted fits by hand instead,
  in a file of its own plus "about 60 in early unlogged probes". It put its
  first screen at "about 15 min", where the transcript's timeline says 89.
  Every `fit` outside a series writes its own directory, so a job of many
  fits is many directories. The question this session needed answered is
  therefore across the runs of one job (count, failures, wall, slowest run),
  not within one log. Decide whether that is Task 1's second mode or another
  verb, and name it in `batch-operating.md` either way (WP-1464 edits that
  file too).
- **2026-09-24, from the issue triage: #237 closed as a duplicate of #223.**
  This file keeps citing both. The 9c.13 row the 2026-09-03 entry below
  places in `references/batch.md` merged with PR #233 and now lives in
  `references/batch-operating.md` § 9c.13, still cross-referenced from
  `references/series.md`; revise it there.

From **WP-1403** (2026-09-15), which removed this WP's Task 2 premise:

- **Task 2 is discharged, not deferred.** The `history` defaults asymmetry was
  a decision about which knob to flip so that an agent would have a log; every
  fit now writes one whether or not `history` or `events=` was passed, so there
  is no longer an asymmetry to decide. Strike the task rather than answering it,
  and say in the handover that 1403 is why.
- **Task 1 is untouched and still wanted.** The terminal-shaped post-hoc
  aggregator now has a reliable input rather than a hoped-for one: a run
  directory per fit, discoverable by `runs.discover`, with `meta.json` and
  `status.json` beside the log. An aggregator can read what a run *says about
  itself* instead of inferring it from the stream.
- The measurement this WP made is what carried 1403: three agents, three routes
  to the skill, five occurrences of `history=False`, and 2.7-16.6 % coverage
  recovered from transcripts afterwards. It is quoted in 1403's own Context and
  in the new `tests/test_telemetry.py` docstring, so it is no longer only here.

- **2026-09-13, from WP-1401 (the live-watcher track): Task 2 is on its way to
  being answered by removing its own premise — do not decide it standing
  alone.** WP-1403 makes every `fit()` record itself, with an env switch and
  nothing for a caller to remember, on this WP's own evidence: an agent cannot
  switch off by accident what it never had to switch on. If 1403 ships, the
  `history` defaults asymmetry stops being the thing that decided coverage and
  Task 2 becomes a note in the skill rather than a defaults flip. If 1403 is
  reprioritised or fails WP-1404's cost gate, Task 2 is live again exactly as
  written. Either way WP-1406 is scheduled to record the outcome here, dated.
  **Task 1 is untouched by all of it**: the post-hoc aggregator over an event
  log is a terminal-shaped surface for a moment the watcher does not serve, and
  it is a contributor's offered PR. Also relevant to it: WP-1401 lands
  incremental tailing of an `events.jsonl` by byte offset, tolerant of a torn
  last line — import that rather than writing a second reader.

  Related, and the reason this entry is not stronger: WP-1403 gives each run its
  own directory, which answers the segmentation problem below for *recorded*
  runs without touching `EventStream`'s append mode. A log a caller opened by
  hand still has no run marker.

- **2026-09-03, from the issue triage (issues #223 and #237, the same defect
  reported twice): an aggregator cannot segment the log it is given, because
  `EventStream` appends with no run marker.** `EventStream.__init__` opens
  unconditionally in append mode (`history/events.py:139`):

  ```python
  self._fh = open(self.path, "a", encoding="utf-8") if self.path else None
  ```

  So re-running anything into the same `events=` path silently merges the new
  run into the previous one, with nothing in the file saying two runs are
  present, and `read_events` returns both as one stream. **The failure is
  silent, the corrupted quantity is plausible, and the only signal is an
  external check most callers will not have.** Measured twice during a timing
  study over a 638-pattern series: in the worst case a **10.3 s fit reported as
  459.0 s** (44.67x). It was caught only by asserting event-log-summed
  durations against an independently measured wall clock (3472.73 s against
  3409.27 s, ratio 1.0186 once fixed). It is worse for a long series, where
  re-running one leg after a crash is the normal recovery and the merged log is
  then the *expected* workflow rather than an accident.

  **Append is nonetheless the right default and must stay one.** It is
  load-bearing in two places: `SequentialRefinement` forwards every pattern's
  events through one stream so a series run appends to exactly one log (the
  module comment at `sequential.py` ~248 says so explicitly), and `rietx watch`
  tails the file, so truncating under a reader would be worse. The fix is not
  to change the mode.

  Three directions, cheapest first, and the reporters agree on which: **(1) a
  run header record written on open** — a `record: "run"` line carrying the
  fingerprint and created timestamp the header already computes, so a reader
  can partition a file into runs and a consumer summing durations can refuse or
  warn when it sees more than one; one line per file, and it protects the
  *reader* rather than relying on the writer remembering, which is the case
  that actually bites. **(2)** an explicit `EventStream(path,
  mode="append"|"truncate")` with the default unchanged. **(3)** at minimum,
  document it where `events=` is documented. A contributor has offered a PR
  for (1).

  **The design constraint to settle first**: `EventKind` is closed and the run
  state is deliberately not an event (root CLAUDE.md), so a new *kind* is an
  `EVENT_SCHEMA_VERSION` bump while a header *record* on a different key may
  not be. Decide which shape (1) takes before writing it — this WP's aggregator
  is its first consumer either way.

  Skill rows that may need revising **in the same change** (all three copies,
  via `rietx skill --install . --copy`): on this tree `references/batch.md`
  holds rows 9c.1–9c.4 only, but **PR #233 (open, unmerged on 2026-09-03)**
  adds a 9c.13 telling an operator to rotate or re-path the log before every
  run, cross-referenced from `references/series.md` for ramps. If #233 has
  merged by then, both become descriptions of a package that no longer needs
  the workaround.

## Non-goals

- **Not the interactive scrubber** — [1317](1317-series-scrubber.md)'s.
- **Not transcript/token attribution** — harness-specific, stays with the
  campaign (the issue offers only the half that consumes rietx's format).
- **Not a new event kind or schema field** — `EventKind` stays closed; the
  aggregator reads what is already written.
- **Not live viewing** — `rietx watch` owns the running case.

## Tasks

- [ ] The aggregator: a plain function in `rietx.history` + the
      `rietx events <log.jsonl> [--json]` subcommand over it; fixture logs
      from the package's own emitters, never hand-written JSONL.
- [x] ~~The defaults decision on `SequentialRefinement.history`~~ —
      **discharged 2026-09-15 by WP-1406**, premise removed by WP-1403. Nothing
      flipped, nothing to release-note. See Task 2 above.
- [ ] The skill `series.md` instrumentation line (all committed copies
      re-synced via `rietx skill --install . --copy`).
- [ ] CLI docs/manual coverage per the standing partition gates
      (`tests/test_manual_api.py`, the CLI chapter) + tests per item.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_events_aggregator.py   # new module, this WP's
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

The bar: on a fixture series log the aggregator's counts reconcile exactly
with the emitting run's own records (stages, terminations, held paths,
wall-clock within the events' own timestamps); `--json` round-trips; the
skill line ships in every committed copy.

The shipping PR carries `Closes #207`.

## References

- Issue #207 — the 3/3 finding, the 288-record example, the offer and its
  deliberate fence.
- [1317](1317-series-scrubber.md) — the interactive sibling and the
  one-vocabulary rule; [1305](1305-series-deliverable.md) — the series
  answer both read.
- `history/events.py`, `history/tree.py` — the emitters and today's only
  consumer.

## Handover log

- **2026-09-01** — created, from issue #207 (2026-09-01 triage, second
  batch). Settled: CLI subcommand thin over a `rietx.history` function;
  fixtures from the real emitters; the defaults question is a decision to
  take in-WP, not a bug. If the contributor's PR lands first, start from
  the review.

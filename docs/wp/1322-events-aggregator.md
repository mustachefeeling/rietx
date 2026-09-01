# WP-1322 — the run is instrumentable, and nothing says so

Milestone: unscheduled · Status: ⬜
Depends on: —

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

**Task 2 — the defaults decision.** Flip `SequentialRefinement.history` to
match `Refinement`'s, or keep it and make the skill carry the asymmetry out
loud. Decided against the 3/3 evidence and the documented disk-cost reason,
not assumed here; if flipped, it is a behaviour change on a shipped surface
— recorded per the few-users policy (breaks are cheap, but every one is
recorded), with the disk cost stated (history nodes are ~10 kB; a long
series is many files either way).

**Task 3 — the skill line.** `references/series.md` (all committed copies)
gains the sentence the campaign says would have saved the reconstruction:
pass `history=<path>`/`events=EventStream(path)` when you need a run
record; `stage_end` carries the termination criterion.

**One vocabulary, shared with 1317.** Issue #133's scrubber is the
interactive consumer of the same substrate ("same substrate, different
consumer" — #207's own framing): the aggregator's `termination` histogram
and held-path counts summarise exactly the marker vocabulary 1317 reads
from `SeriesResult`, so neither surface invents a second set of names.

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
- [ ] The defaults decision on `SequentialRefinement.history`, measured
      against the 3/3 evidence and the disk-cost reason; recorded either
      way, release-noted if flipped.
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

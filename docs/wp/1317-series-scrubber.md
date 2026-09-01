# WP-1317 — scrub the series along its own trace

Milestone: unscheduled · Status: ⬜
Depends on: —

## Goal

An in-situ series is navigated by the experiment's own axis: a master trace
(temperature or time versus pattern index, from the series' own metadata)
carries markers wherever the series' diagnostics fired, and dragging along
it updates a linked obs/calc/diff view of that pattern at interactive speed
— the "play through the phase transition and watch the peak split" motion
that today takes ~40 clicks through drill-downs.

## Context

From issue #133, with issue #141's surviving half folded in.

**What exists.** WP-1016's series panel plots per-parameter trajectories
with esds and drills into per-pattern history trees. Navigation by the
experiment's axis, and event annotation on it, do not exist — the issue
notes v1.2's seventeen GUI WPs do not cover it.

**Why it is series-shaped, not sugar.** A transition is legible only
*across* patterns: the motivating cases in the filer's archive read as a GoF
step plus an unmatched-peak collapse over 2–3 patterns, invisible in any
single fit view. The scrubber is the human-speed version of the same
discriminators the batch heuristics already use.

**One vocabulary, already shipped — the first task.** The markers come from
what `SeriesResult` already carries: the `SEQUENTIAL_*` findings
(`PATH_DEPENDENT`, `UNRECOVERED`, `CANCELLED`, `PERSISTENT_FINDING`),
per-pattern refusals and abstentions, agreement steps. This is issue #141's
surviving insight — its proposal (a batch verb returning aggregates plus
flags, reports on demand) targeted `refine_json`, which WP-1303 deleted,
and its aggregates-plus-flags answer is what WP-1305 shipped as the series
deliverable; what remains is the rule that **the flag list and the event
markers are one vocabulary**, read from the result, never a second set
invented view-side. Later external annotations (a gas switch, a declared
transition interval) extend the same vocabulary.

**The issue's open questions are this WP's questions**: which panel owns the
trace; whether external annotations are a schema addition or view-side;
animation/export and 2-D film views (probably out, but decided here, not
assumed).

**Standing GUI gates apply**: mutating verbs 409 while a run is in flight;
`EventKind` stays closed (the run state is not an event); the GUI-manual
partition test will demand a chapter for any new tab or route, and
screenshots come from `docs/manual/make_screenshots.py`.

## Non-goals

- **Not the batch computation** — `refine_sequential` already computes the
  findings; nothing here changes what a series run produces.
- **Not a second flag vocabulary** — read the result's.
- **Not 2-D film/waterfall rendering as a deliverable** — decided in-WP,
  and if wanted it is its own later work.

## Tasks

- [ ] The vocabulary: enumerate the marker set from `SeriesResult`'s own
      findings and per-pattern flags; write it down once, view and docs both
      quoting it.
- [ ] The trace: T/t vs index from series metadata, markers placed, owned
      by a panel decided here.
- [ ] Scrubbing: drag updates the linked pattern+fit view at interactive
      speed; the drill-down stays one click away.
- [ ] External annotations decided (schema vs view-side) and, if schema, the
      minimal addition with its round-trip test.
- [ ] GUI manual chapter + screenshots via `make_screenshots.py`; vitest
      coverage for the panel logic; `npm --prefix gui run check` clean.

## Acceptance

```sh
npm --prefix gui test && npm --prefix gui run check
.venv/bin/python -m pytest tests/test_gui_manual.py -q
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
```

The bar: on a series fixture with a known transition, the trace shows the
event cluster where the transition is; scrubbing across it updates the fit
view with no per-step server round-trip cost beyond the pattern fetch; the
manual partition is green with the new chapter.

## References

- Issues #133 and #141 — the motion, the measurements, and the vocabulary
  rule.
- [1016](1016-sequential-series-panel.md) — the panel this extends;
  [1305](1305-series-deliverable.md) — the series answer the vocabulary
  reads.
- `gui/CLAUDE.md` — the panel, route and manual-partition rules.

## Handover log

- **2026-09-01** — created, from issue #133 with #141's residual
  (2026-09-01 triage). Settled: one vocabulary read from the result; first
  open decision is which panel owns the trace.

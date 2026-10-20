# WP-2018 — The clash table: actions that read or move the same parameter, measured both ways

Milestone: generality · Status: ⬜
Track: The audits
Depends on: —
Priority: P3 2026-10-20 — split from WP-2002 by the maintainer; 38 candidate pairs found and none measured, and one past clash (WP-1320) changed a design

## Goal

For each pair of automatic actions that read or move the same parameter in one fit, the
measured interaction: Rwp and the parameter's value with the actions in both orders, on a
dataset that exercises both. A pair that interacts is reported with what it changes and
what a caller sees; a pair that does not is recorded as measured and independent.

## Context

**Why a clash table.** The generality milestone's plan review asked each audit to keep one,
because heuristics interact (`docs/milestones/generality.md`, the plan review): WP-1320
chose the fraction profile's axis because the collapse rule fought it. WP-2002's readers
listed 38 candidate pairs, deduplicated in `docs/wp/2002-batch/clashes.md` with the
parameter, both actions at file and line, the dataset that exercises both and which reader
named it. Nothing there is measured. Line numbers are of 2026-10-19 and have moved.

**Two pairs to start with.** C1 is WP-1320's clash: `profile_fraction` pins one width per
branch and refits through `run_stage`, against the stage-start hold and the collapse
restore. WP-1320 measured it under the pre-WP-1523 significance test and never since. C3 is
the cell window, the hold and the reset-and-hold that replaced the clamp (2026-10-20).

**What changed since the list.** The B8 cell reset replaced the clamp; the position bounds
went; Le Bail and Pawley now refine the emission lines; the package's own trials inherit
`phase_support_sigma` and `correlation_guard`. Re-derive each pair's file:line before
measuring, and drop a pair one of these changes dissolved, saying why.

## Non-goals

- Fixing a clash found here. A fix is the owning audit's, or a ruling for the maintainer.
- Pairs across fits in a series (WP-2003's).

## Tasks

- [ ] Re-derive the 38 pairs against the tree; drop or merge the dissolved ones with a line
      each.
- [ ] Per pair, the dataset that exercises both, chosen before running.
- [ ] Measure both orders (or with and without one action, where order is fixed by the
      code): Rwp, the shared parameter, and its esd. PNGs to `tests/output/`.
- [ ] The table in this file: pair, effect, size in esds, verdict (independent, ordered,
      or a clash). A clash goes to its owner WP's `### Inherited` or to the maintainer.

## Acceptance

```sh
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
```

Every pair in `2002-batch/clashes.md` has a measured row or a stated reason it was dropped.

## References

- WP-2002, `docs/wp/2002-batch/clashes.md`; WP-1320 (the fraction profile's clash);
  WP-1523 (the significance test).
- `docs/milestones/generality.md`, the plan review's clash-table requirement.

## Handover log

- **2026-10-20** — Filed by WP-2002's session at the maintainer's request ("split"): the clash table moves here so that 2002 closes on its owed tests and B14's lifts. Nothing measured yet.

# WP-1453 — a series whose phases come and go

Milestone: unscheduled · Status: ⬜
Depends on: — (1420 soft: a held phase re-entering is the fixed-list half of this)
Priority: P2 2026-09-24 — an in-situ series whose phase set changes cannot use the chain, and the hand-built replacement loses every check the chain carries

## Goal

A series whose phase set changes along the chain runs through
`SequentialRefinement` and keeps the ladder, the quarantine,
`direction="both"` and `verify_discontinuities`. If task 1 shows that the
fixed phase list already serves, nothing is built and the skill says how to
drive it.

## Context

**The evidence.** The 2026-09-24 review of an agent session read one run
end to end. The agent drove rietx at `644dff84` through the skill, on a
private synchrotron in-situ series of 48 patterns. Several candidate phases
entered and left along the series, and at most three were present in any
pattern. Two candidates were proxies that share one structure with a
neighbour. The maintainer holds the transcript, the scripts and the data.
None of it is public, so quote only what the runs did (CONTRIBUTING, WP-1450).

The agent read `references/series.md` and inspected
`SequentialRefinement.fit`, then wrote its own chain in about 240 lines over
two scripts. The stated reason was that one `Structure` spans the whole
chain. The hand chain added four things the package does not offer:

- a candidate window per phase, as a range of pattern indices;
- significance pruning: a phase under 1 wt % or under 2σ was dropped and the
  pattern refitted, and a phase pruned twice was retired;
- holds on the cells and widths of phases under 3 wt %;
- per-phase cell bounds of about ±0.15 % around a reference cell, to keep
  each phase's identity.

It lost everything the chain carries: the escalation ladder and the
quarantine (WP-1051), `direction="both"` with `SEQUENTIAL_PATH_DEPENDENT`,
`verify_discontinuities`, one telemetry record per job, and `SeriesResult`
trajectories. Seven chains ran, at 9.5-12.5 CPU-minutes each, and five of them
were diagnostic. The first swapped two phases' identities across a
transition. A warm-started cell walked onto a neighbour's reflections, Rwp
stayed smooth, and no series diagnostic fired. The agent then compared
forward, backward and cold solutions by hand (WP-1454).

The thresholds above were chosen by the agent. None of them is evidence for
a default.

**The fixed-list route the package already has.** Pass every candidate in
one `Structure`. WP-1301 holds a phase below 1σ support for the stage (its
structural paths are held and its scale stays free) and releases it at the
pattern where it appears (`tests/test_held_phase.py`). WP-1420 (issue #267)
measured the failure of that route. When a held phase's frozen structure is
collinear with a supported phase, the phase does not get back in and the
chain says nothing. A proxy that shares a neighbour's structure is that case
by construction. Nobody has measured whether the fixed list survives
proxies, or what carrying every candidate through every pattern costs.

**The seams.**

- `SequentialRefinement.__init__(structure, instrument, carry=("*",))`
  (`src/rietx/sequential.py:662`) takes one structure for the chain.
- `_carry_into` (`sequential.py:521`) moves values by dot-path glob. Dot-paths
  index phases by position (`phases.3.cell.a`), so a change in membership
  re-indexes every later phase's paths.
- `prepare(index, data, structure, instrument)` runs before the pattern's
  `Refinement` exists. `constrain(index, ref)` runs after, and may `hold`
  (`sequential.py:800-830`).
- `SeriesResult.trajectory(path)` is keyed by the same indexed path, and
  `_path_dependence_diagnostics` (`sequential.py:1937`) pairs the two chains
  by pattern label.

**Prior art, not yet read.** How GSAS-II's sequential refinement and a TOPAS
batch file each treat a phase that enters mid-series. Read both before
choosing a design.

## Non-goals

- Pruning thresholds as defaults. A threshold here is quoted from a paper or
  measured, never tuned, and the hand chain's values were neither.
- Deciding which phases exist. The caller supplies the candidates.
- Joint fits across patterns (`refine_multi`).

## Tasks

- [ ] Measure the fixed-list route first, on a synthetic series. Phases A, B
      and C succeed each other with overlap windows, and a proxy B′ shares
      B's structure with a cell within 0.5 %. Run `refine_sequential` with
      all four in one `Structure`, in both directions. Record where each
      phase enters and leaves, whether B′ takes B's reflections, and the cost
      per pattern against a hand-windowed chain. The result decides the rest
      of this list.
- [ ] If the fixed list serves: write the recipe into the skill and stop.
- [ ] If it does not: design membership. The candidates are a window per
      phase or a `phases_at(index)` callable, with carry, trajectories and
      path dependence keyed by phase name. Write the decision here before
      the code.
- [ ] Identity: check whether `verify_discontinuities` catches task 1's B/B′
      swap. If it does not, say what would.
- [ ] Tests: the synthetic series as a fixture, both directions, with
      identity asserted per pattern.
- [ ] Skill: `references/series.md` has no route for a changing phase set or
      for proxies. Add a situation row and the recipe, in a shape reference
      if the body cannot take it (root CLAUDE.md § skill).

## Acceptance

The synthetic series from task 1 runs through the package in both
directions, and every phase is present exactly in its window. Phase identity
survives each transition, or a named diagnostic fires at the pattern where
it does not.

```sh
.venv/bin/python -m pytest tests/test_sequential*.py tests/test_held_phase.py -q
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

## References

- WP-1301 (the hold), WP-1420 and issue #267 (the collinear re-entry),
  WP-1051 (the ladder), WP-1454 (choosing between passes).

## Handover log

- **2026-09-24** — created from the review of an agent session on a private
  in-situ series. The hand chain, its seven runs and the identity swap are
  measured in that session's transcript. The seams were checked against the
  tree at `2d42303a`. Next: task 1's synthetic measurement.

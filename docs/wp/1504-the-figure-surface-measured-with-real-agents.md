# WP-1504 — the figure surface measured with real agents

Milestone: v1.7 · Status: 🔄 2026-10-01 — claimed by @yue-here
Depends on: 1501, 1502, 1503
Priority: P3 2026-09-30 — 1501, 1502 and 1503 have landed, so it can start; costed menu first

## Goal

A before-and-after measurement of whether an agent given only the skill can
make the figures a chemist asks for, on two models, with the tasks, the
harness and the scores committed. Its result decides what WP-1501 to 1503
keep and whether WP-1505's trigger has fired.

## Context

### Why a measurement, and why real agents

Three rules from earlier rounds bind this WP. An eval of usefulness to an
agent needs real agents, with model and effort as variables, and a
deterministic proxy measures nothing. A registered round is not
authorisation to run its cells: the session offers a costed menu and runs
what is picked. And a declared field with no reader is a claim, so which
numbers of `report` the agents read decides which stay.

The v1.3 round 1.1 cost $38.39 for eight cells and is the price anchor.

### The tasks

Stated as a chemist would, from the 21 phases in
`tests/data/polyhedra_phases.json`, every one COD-cited and so public:

1. Rutile's edge-sharing TiO₆ chains, seen down c.
2. One layer of gypsum with its water, seen edge-on.
3. Calcite's CO₃ groups alone, no Ca, no polyhedra.
4. NAC's AlF₆ octahedra as a 2×2×1 block.
5. LaB₆'s B₆ octahedra without the La–B sticks.
6. Fluorapatite down c for print, 17 cm at 300 dpi, with a legend.

### The conditions

- **Before**: the WP-1470 tree. The agent has `render_structure`, the
  dict, and the manual as it was. Cuts and extents must be done by hand.
- **After**: the WP-1503 tree.
- Sonnet and Opus, at the default effort, three repeats each.
- The agent gets the skill and a shell, and nothing staged in its folder.

### The scores

- Done or not. An Opus judge reads the final picture against a rubric per
  task, and the maintainer spot-checks every "done".
- Renders taken, and the size of each.
- Tokens and wall time.
- Which fields of `report` were read, from the trace.
- Where the agent stalled, in one line per run.

### Where it lives

`docs/wp/1504-eval/` holds the harness, the rubric and the run log. A
condition is enforced in a shim, never in the prompt.

## Non-goals

- Running it in CI.
- A leaderboard or a published benchmark.
- Any figure on data without a peer-reviewed citation.

## Tasks

- [ ] The harness: a shim per condition, the six task prompts, the rubric,
  the trace parser for `report` reads.
- [ ] A costed menu to the maintainer before any cell runs.
- [ ] The before round, on the picked cells.
- [ ] The after round, on the same cells.
- [ ] The table in this file's handover, and one line per `report` field:
  read or never read.
- [ ] The cuts pushed into 1501 to 1503's `### Inherited`, and 1505's
  trigger rated.

## Acceptance

- Every run's picture, trace and score are in `docs/wp/1504-eval/`.
- The handover states, per task and model, done or not before and after,
  with renders and tokens as ranges.

```sh
.venv/bin/python docs/wp/1504-eval/run.py --menu
```

## References

- The v1.3 record, round 1.1, for the harness pattern and the cost.
- The agent skill's `references/api-figure.md`.

## Handover log

- **2026-09-27** — filed from the session that closed WP-1470. Next: wait
  for 1503; then write the harness and bring the menu.

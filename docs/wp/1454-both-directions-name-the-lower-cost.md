# WP-1454 — both directions name the lower cost

Milestone: unscheduled · Status: ⬜
Depends on: — (1453 soft: the evidence came from a hand chain)
Priority: P3 2026-09-24 — `SEQUENTIAL_PATH_DEPENDENT` already fires; it does not say which of the two answers to quote

## Goal

When the forward and backward chains disagree, the series result says, per
pattern, which pass reached the lower cost of the same objective. A caller
can ask for the better one.

## Context

**What the package does now.** `direction="both"` runs the chain each way
and reports `SEQUENTIAL_PATH_DEPENDENT` where a parameter disagrees beyond
its esds. The docstring says so plainly: "The reported entries are the
forward ones" (`src/rietx/sequential.py:743-745`).
`_path_dependence_diagnostics` (`sequential.py:1937`) compares parameter
values and never costs.

Within one pattern the ladder already ranks attempts. `_prefer` and
`_better` (`sequential.py:1550`) rank a diverged fit below a finished one,
rank a truncated attempt below a completed one, and then go on Rwp. A
backward pass is two more attempts at the same pattern, and nothing ranks
them against the forward one. With one phase list, both passes minimise the
same objective on the same data. The lower cost is then the better local
minimum by the same logic the ladder uses.

**The evidence.** Taken from the session WP-1453 describes (a private
series, so only fit qualities are quoted). The agent compared three
solutions per pattern by hand: forward, backward and a cold refit. Neither
direction won everywhere. Over the 27 patterns the agent compared, the
lower-BIC pass was the forward one at 13 and the backward one at 14. The two
differed by more than 10³ in BIC at 15 of the 27, inside the transition
windows and outside them. At one pattern the forward pass's χ²_red was 2.4×
the backward's, and at another the backward's was 1.5× the forward's. The
phase sets sometimes differed between the passes, because that chain pruned
phases, so the agent ranked on BIC. With a fixed list, χ² compares directly.

**The design question.** A per-pattern best mixes the two passes, so the
returned trajectory is no longer one chain. Each entry is still a converged
optimum of its own pattern. The options:

1. Report only. Each `SEQUENTIAL_PATH_DEPENDENT` finding carries the two
   costs, and the entries carry the backward cost beside the forward one.
2. `keep="lower_cost"` returns the better pass per pattern and marks which
   one it took.
3. A cold rung at every pattern the two passes disagree on, ranked by
   `_prefer` with the other two.

Option 1 changes no number and could land first.

## Non-goals

- Choosing between different models. With different phase sets the
  comparison needs an information criterion, and WP-1417 owns ΔBIC at powder
  channel counts.
- Changing how a single chain seeds its successor.

## Tasks

- [ ] A synthetic two-basin series where the backward pass reaches a lower
      cost than the forward one at a known pattern. The WP-1420 fixture
      (issue #267) may already be one.
- [ ] Option 1: costs on the finding and on the entry.
- [ ] Decide whether 2 or 3 ships, and write the decision here.
- [ ] Tests: the fixture reports the right pass at the right pattern.
- [ ] Skill: `references/series.md`'s `direction="both"` paragraph says
      which pass to quote when they disagree.

## Acceptance

On the fixture, the finding at the disagreeing pattern names the pass with
the lower cost, and quotes both costs.

```sh
.venv/bin/python -m pytest tests/test_sequential*.py -q
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

## References

- WP-0505 (the chain), WP-1051 (the ladder), WP-1127 (`_prefer`'s truncation
  rule), WP-1417 (ΔBIC).

## Handover log

- **2026-09-24** — created from the same session review as WP-1453. The
  forward-only return and the value-only comparison were checked against the
  tree at `2d42303a`. Next: the fixture, then option 1.

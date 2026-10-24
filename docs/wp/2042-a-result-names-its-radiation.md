# WP-2042 — a result names its radiation

Milestone: unscheduled · Status: ⬜
Track: Render what the fit already knows
Depends on: —
Priority: P3 2026-10-24 — a view over what the fit already knows, and `wavelength=` is the workaround

## Goal

`RefinementResult.plot()` labels its 2θ axis with the radiation, as `PatternData.plot()` does,
without the caller passing it.

## Context

- WP-2039 made `plot_pattern` name the radiation on its 2θ label (`viz/plots.py`,
  `_stated_radiation`): the model's source where its lines match the radiation table, else the
  file's own `anode` and wavelength from `data.metadata`.
- `plot_result` cannot do the same. A `RefinementResult` carries no field naming its source, so
  the function can only take `wavelength=`. In the tutorials, `data.plot()` says "Cu Kα" and
  `best.plot()` a few cells later says nothing.
- Closing it needs a recorded field on the result, so it is a schema change
  (`schemas/results.py`). A new field's default and its writer are named at review (root
  CLAUDE.md, WP-1076): an old result reopened from JSON has no value, and `None` must read as
  "not recorded", never as "no radiation".
- `_stated_radiation`'s rule (name an anode only where the lines match the table to the last
  digit) is the one to reuse, never a second copy.

## Non-goals

- Any other figure's labels.

## Tasks

- [ ] The field on `RefinementResult`, written where `refine` builds the result, and read by
      `plot_result` through `_stated_radiation`'s rule.
- [ ] Tests: a fit on a preset source labels the axis; a result from an older JSON file loads
      and draws an unnamed axis.
- [ ] Skill: none. A figure label changes no judgement.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_viz.py -q
```

## References

None.

## Handover log

- **2026-10-24** — Created from WP-2039's inherited note to WP-2040, because no open WP owns
  the result schema's source fields and WP-1444, which added figure titles, is closed.
  Next: the first task.

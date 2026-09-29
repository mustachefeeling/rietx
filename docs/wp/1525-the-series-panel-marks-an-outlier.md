# WP-1525 — The series panel marks an outlier

Milestone: unscheduled · Status: ⬜
Track: Render what the fit already knows
Depends on: — (1469 landed the verdict this draws)
Priority: P3 2026-09-29 — the GUI draws a frame the chain flagged as an ordinary point, while the matplotlib plot of the same series boxes it

## Goal

The GUI's series panel marks a pattern above the Rwp fence the way
`plot_trajectory` does, so the two renderers of one series say the same
thing about it.

## Context

WP-1469 added `SEQUENTIAL_RWP_OUTLIER`: a pattern every rung left above the
Rwp fence. Its verdict is `SeriesEntry.above_fence`, a **property** derived
from the stored `SeriesEntry.rwp_fence` and the entry's own Rwp and status, so
it is not in the entry's JSON. `viz/plots.plot_trajectory` boxes such a point
(hollow square) beside the reseeded ring and the unrecovered cross, and its
docstring says the plot shows the same fences the diagnostics carry.

The GUI draws the same trajectory in `gui/src/panels/Series.svelte`, marking
points through `gui/src/lib/series.ts` (`reseededFlags`, the diverged cross,
`trajectoryLegend`), from the payload `src/rietx/gui/series.py` serves. It
has no outlier mark, so a blank frame reads there as an ordinary point. The
1469 review named this as a second builder (root CLAUDE.md: "a second builder
of anything is the miss") and declined it as outside that diff.

Two ways to carry the verdict, and the choice is this WP's first task:
serve `above_fence` in the payload (one authority, the property), or derive
it in TypeScript from `rwp_fence` (a second derivation, which the rule above
argues against).

The GUI rulebook is `gui/CLAUDE.md`: the vitest suite, the committed dist
(`npm --prefix gui ci && npm --prefix gui run build`), and `test_gui_manual.py`
for anything a chapter names.

## Non-goals

- Anything the fence decides. This is a view over 1469's verdict.

## Tasks

- [ ] Carry the verdict to the page (served, not re-derived), with a test on
      the route's payload.
- [ ] The mark and its legend entry in `series.ts`/`Series.svelte`, with
      vitest cases beside the reseeded and unrecovered ones.
- [ ] Rebuild the committed dist; the GUI manual chapter says what the box
      means if it lists the other marks.
- [ ] Skill: none — an agent reads the code, not the panel; say so here.

## Acceptance

A series with a blank frame shows it boxed in the GUI panel and in
`plot_trajectory`, and nowhere else.

```sh
npm --prefix gui test && npm --prefix gui run check
.venv/bin/python -m pytest tests/test_gui_server.py tests/test_gui_manual.py -q
.venv/bin/python -m ruff check src tests examples
```

## References

- WP-1469 (the verdict and the matplotlib mark), WP-1016 (the series panel).

## Handover log

- **2026-09-29** — created, from WP-1469's review (the declined GUI finding).
  Next: task 1.

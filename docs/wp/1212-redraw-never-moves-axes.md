# WP-1212 — A redraw never moves the axes

Milestone: v1.2 · Status: ⬜
Depends on: WP-1210

## Goal

Nothing but a zoom or a double-click changes the plot's axes: not a hover in
the peak table, not an excluded region, not a peak edit. The armed exclude
drag shows two edge lines and a wash while it is dragged.

## Context

The user: "the plot jitters when mousing over in the peaks panel"; "Plot
jitters sometimes when exclude selected. Eliminate all jitters"; "the cursor
changes to the plotly select region cursor (rectangle; desired behaviour is
two vertical lines and shading showing the selected region)".

Findings (2026-08-25), mechanisms identified in code and **not yet measured**:

- **Hover.** The table's `mouseenter` sets `hovered` (`Peaks.svelte:567-569`
  → `App.svelte:818, 768`); `drawRing` (`Plot.svelte:453-461`) restyles the
  `hovered` trace's arrays. That trace is a full `scattergl` trace on the
  data axes with `marker.size: 16` (`Plot.svelte:441-445`). `heldRanges`
  (`lib/plot.ts:195-207`) keeps an axis only when `autorange === false`, so
  on a plot the user has not zoomed every `restyle` lets plotly re-autorange,
  and scatter autorange padding depends on marker size. That is the
  candidate mechanism for the hover jitter.
- **Exclude.** One drag runs: `arm = null` → the knob effect
  (`Plot.svelte:753-767`, `void arm`) → **react #1**; `clearSelection()` →
  `relayout({selections: []})`; the `project` reassignment → `protocolKey`
  → the fetch effect → **react #2**; `await loadPeaks()` → `peaks` → the
  fetch effect → **react #3**. Each react on an unzoomed plot re-autoranges
  over a trace set that now differs (`masked` arm, `maskShapes`).
- **The armed drag.** `dragmode: arm ? "select" : "zoom"`, `selectdirection:
  "h"` (`Plot.svelte:182-183`); nothing sets `layout.newselection` or
  `activeselection`; the two dotted edge lines and the wash come from
  `maskShapes` (`lib/plot.ts:131-150`) only after the POST lands. The cursor
  rule (`col-resize` on `.nsewdrag`, `Plot.svelte:946-956`) is WP-1044's.
- Plotly call sites in `Plot.svelte`: `react` (`:330`), `restyle` (`:460`),
  `relayout` (`:583`), `Plots.resize` (`:666`), `purge` (`:742`); no
  `addTraces`/`deleteTraces`.
- WP-1044's rule ("a redraw is not a reason to move the axes") pins the view
  only after the user zoomed; the shapes are clipped to `extent` because a
  shape on a data axis takes part in the autorange (WP-1033).

Method (from `gui/CLAUDE.md`): **measure first**, in Chrome via
playwright-core; when a claim is about an event, count the events; read
ranges off `_fullLayout` before and after each gesture. Suspect the harness
first when a result is impossible.

Design: after the first paint of a payload the axes are **explicit**
(`range` set, `autorange: false`), so every later `react`/`restyle` holds
them; a payload change (new result, checkout) and a double-click re-autorange
once; the exclude chain coalesces to one paint (arm cleared and the protocol
change land in the same tick; the peaks reload repaints without a fetch of
the window). The ring trace moves off the data axes (an overlaying pair with
`fixedrange`, matched to the data axes) or becomes a `layout.shapes` entry
with `xref: "x"` clipped to the extent, whichever the measurement shows
holds the range. The live selection is styled through `layout.newselection`
(line) and `activeselection` (fill) to match `maskShapes`; if plotly 3.7's
selection styling cannot draw two edge lines, a `plotly_selecting`-driven
shape pair is the fallback, measured for its own jitter.

## Non-goals

- The hover readout (WP-1213).
- Any change to what a region *does* (WP-1033's protocol strip).

## Tasks

- [ ] The measurement: a table of (gesture → react count, x/y range before
      and after) for hover, exclude drag, peak move, on the NAC example;
      recorded in this file's log.
- [ ] Explicit ranges after first paint; the double-click and payload-change
      re-autorange; `heldRanges` retargeted; `plot.test.ts` on the pure
      parts.
- [ ] The exclude chain coalesced to one paint; the ring off the autorange
      path; re-measure.
- [ ] `newselection`/`activeselection` styling matching `maskShapes`;
      cursor kept; re-measure.
- [ ] `gui/CLAUDE.md`: the rule replaces WP-1044's weaker form (one clause
      plus the measurement pointer); dist.

## Acceptance

The before/after table in the handover log shows zero range change on hover
and on an exclude drag, and one react per exclude drag.

```sh
npm --prefix gui test && npm --prefix gui run check
```

## References

- WP-1044 (the view handed back), WP-1033 (shapes and autorange), WP-1032
  (a hover link costs a restyle).

## Handover log

- **2026-08-25** — created from the v1.2 triage.

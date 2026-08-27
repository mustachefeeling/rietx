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

### Inherited

From **WP-1210** (2026-08-27, shipped):

- **The line numbers above have moved** — `Plot.svelte` grew the layer's
  toggles, its two colours and the tab gate. Find the call sites by name
  (`peakTraces`, `drawRing`, the repaint effect that lists the knobs), not by
  line.
- **The ring trace is now located by name, not by position**: `ringAt =
  traces.findIndex(t => t.name === "hovered")`, because the layer's traces are
  conditional and counting back from the end named whichever one happened to be
  last. If this WP moves the ring onto its own axes or into `layout.shapes`,
  that lookup is what has to move with it — and the ring exists **only while
  the Peaks tab is up**, since the whole layer is now drawn only there. A hover
  jitter measurement therefore has to be taken on that tab; elsewhere there is
  no ring to restyle and `drawRing` returns at `ringAt < 0`.
- **`peaksActive` is a drawing input and sits in the repaint effect.** So the
  effect that "must not move the axes" now also fires on a tab change, which is
  a *new* occasion for the autorange this WP is chasing — worth counting in the
  same pass as the hover and exclude chains, since it re-`react`s with a
  different trace set (the layer appearing or leaving) on a plot the user may
  never have zoomed.
- The data-only button hides the residual with everything else, and its subplot
  keeps its domain, so a quarter of the plot goes empty. Observed and not
  repaired in 1210 because hiding `Δ/σ` alone has always done it; if this WP
  touches the layout it is the cheap moment to decide whether an empty subplot
  should collapse.

From **WP-1211** (2026-08-27, shipped):

- **The data-only press now has a second caller**, so the empty-subplot item
  above went from "a button somebody pressed" to "what selecting a candidate
  does for you". Same repair, more of the time.
- **There is a `yaxis4`** — the candidate overlay's, declared only while it is
  drawn, `overlaying: "y"` with `range [0, 1]` and `fixedrange: true`. It is a
  *fifth* axis this WP's rule has to hold for, and the two properties that keep
  it out of the way are worth not breaking: it never autoranges (so a redraw
  cannot move it), and its trace is clipped server-side to the measured extent
  (so, unlike the peak markers and the mask shapes, it cannot widen `xaxis`).
  A `heldRanges` that grew a `yaxis4` key would be asserting something about an
  axis nobody can move.
- **A layer's props are two now, and both are drawing inputs**: `candidate` and
  `candidatePicked`, joining `peaksActive` in the repaint effect. So a candidate
  click and a candidate *hover* are each a new occasion for the autorange this
  WP is chasing — a hover fires one `react` per row the pointer crosses. Worth
  counting beside the tab-change chain above; measured in Chrome, the zoom did
  survive a candidate swap, so the count is the question rather than the
  correctness.

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

- [x] The measurement: a table of (gesture → react count, x/y range before
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

### 2026-08-27 — the measurement: what jitters is what plotly is still autoranging

The findings above were mechanisms read off the code; this is what the browser
says. Chrome for Testing 1223 driven by playwright-core, plotly 3.7.0 from
`/plotly.js`, the NAC example fitted in the page (Rwp 0.0932), viewport
1500x950, Peaks tab up unless the row says otherwise. Every plotly entry point
is wrapped by an init script before the library loads, and each `react` is
attributed to the effect that caused it by a temporary tag through `paint`
(`scratchpad/instrument.py`, reverted after the run).

| gesture | react | restyle | relayout | resize | xaxis | yaxis | yaxis2 |
|---|---|---|---|---|---|---|---|
| boot → first paint | 3 | — | — | 1 | — | — | — |
| hover a peaks row | **0** | 1-2 | — | — | held | **moves** | held |
| pointer off the table | **0** | 1 | — | — | held | **moves back** | held |
| box-zoom drag | 1 | 5 | — | — | the drag's | the drag's | re-autoranges |
| hover a row, zoomed | 0 | 1 | — | — | held | held | held |
| peak move, zoomed | 1 | 6 | — | — | held | held | held |
| double-click, Report tab | 1 | — | — | — | resets | resets | resets |
| tab Peaks ⇄ Report | 1 | 0-2 | — | 1 | held | **moves** | **moves** |
| arm exclude | 1 | 1 | — | 1 | held | **moves** | **moves** |
| **exclude drag** | **4** | 3-13 | 1 | 1-2 | held | **moves** | **moves** |

**The jitter is on the axes plotly is still autoranging, and on no others.**
WP-1044's `heldRanges` keeps an axis only when `autorange === false`, which is
exactly "the user has zoomed it" — so on the plot a user has *not* zoomed,
every redraw and every `restyle` re-autoranges, and the same gesture on a
zoomed plot is clean (`hover a row, zoomed`, `peak move, zoomed`: nothing
moves). That is why the repair looked complete and the report kept coming.

Sizes, so the word "jitter" carries a number: a hover moves `yaxis` from
−18597.7-283838.2 to −21714.8-284045.7 — the bottom by 3117 counts, 1.03 % of
the span — because the ring is a `scattergl` trace with `marker.size: 16` and
scatter autorange pads by marker size. It moves *back* when the pointer leaves
the table, so running down the rows pumps the axis once per row. `xaxis` never
moved in any gesture measured: the ring's x sits inside the pattern's own
extent, so its padding is swallowed. The hover costs **no** `react` — WP-1032's
`restyle` is doing its job, and the restyle is enough to re-autorange on its
own.

The exclude drag's four reacts, named:

1. `arm` → null (the knob effect: the drag mode is layout, so arming repaints)
2. a knob repaint with **no knob changed** — `extent` is `$derived` off
   `project`, so `project = await api.patchProject(...)` hands the effect a new
   array identity holding the same two numbers
3. `protocolKey` → the window refetch (real: the masked points are an arm of
   the payload)
4. `peaks` → `setProtocol`'s `await loadPeaks()`, a second flush after the
   third

Two findings this WP did not go looking for:

- **A select drag throws once per pointer move, inside plotly.** `TypeError:
  Cannot read properties of undefined (reading 'length')` at scattergl's
  `selectPoints` ← `moveFn`, 7 times over three exclude drags — and none on the
  first drag of a session, only after an exclusion exists. `selectPoints` reads
  `scene.selectBatch[trace.index].length`, and every scattergl trace on a
  subplot shares one `_scene` whose batches are indexed by position, so a trace
  that comes and goes mid-list (`masked` appears the moment a region is
  excluded) leaves the scene's batches short. The selection still lands; the
  console fills. Candidate repair: the trace list keeps its shape, empty rather
  than absent.
- **The candidate chain is not measured yet.** `POST /api/index` was still
  running when the pass's budget ran out and no candidate table was on screen,
  so 1211's inherited question (one react per row the pointer crosses) is
  re-asked after the repair, where the answer is what matters.

- **2026-08-25** — created from the v1.2 triage.

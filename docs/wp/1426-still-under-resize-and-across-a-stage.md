# WP-1426 — still under resize, and across a stage

Milestone: unscheduled · Status: ⬜
Depends on: 1423 (the page and the browser harness this extends)

## Goal

Nothing on the `rietx watch` page flashes or shifts when the window is resized,
when a stage lands, or when a run appears. The legend stays where it was drawn.
The console keeps its lines when the picture changes. The page's cumulative
layout shift over a poll cycle is zero and a browser test says so.

## Context

WP-1423 made the page hold still between polls, measured as distinct states of
each element over 25 s. The maintainer's next reading found the movement it
did not measure: the legend jumps into the middle of the plot on a window
resize; changing the plot also reloads the console; and there is still jitter
and flashing to look into. This WP takes those three and the metric that
covers the class.

### The legend

`drawSnapshot` lays the legend out horizontally above the plot: `legend:
{orientation: 'h', y: 1.02, yanchor: 'bottom', x: 0}` under `margin.t: 8`.
`viz/html.py` line 146 uses the same spec. Eight pixels of top margin is
less than one legend row, so the legend already sits outside the paper and is
clipped or overdrawn; on a resize plotly re-lays a horizontal legend and wraps
it when the entries (one `hkl: <phase>` row per phase, widened by the
`(n of m)` cap) no longer fit the width. Where it lands afterwards is the
thing to measure, not guess: record the legend group's bounding box before and
after `Plots.resize` at 1400, 1000 and 700 px widths in the browser test.

Whatever the measurement shows, the fix must obey WP-1423 rule 2. The legend's
box is a dimension the page fixes. Two forms satisfy it: the legend inside the
paper at a fixed anchor (`y: 1, yanchor: 'top'`, where plotly never re-lays it
on resize), or an HTML legend the page owns in a strip of declared height with
`showlegend: false`. Prefer the first if it measures still; it keeps the
picture `viz/html.py`'s.

### The console

`drawRun` rebuilds the shell whenever `shell.kind` changes:

```js
if (shell.id !== id || shell.kind !== kind) buildShell(run, kind);
```

`buildShell` sets `$('console').textContent = ''` and resets `tail` to offset
0. A run opened before its first snapshot has kind `none`; at the first stage
boundary it becomes `json`, the shell is rebuilt, and the console is wiped and
re-tailed from the start of the log (`tail_events` serves up to 4 MB per
call). That is the reload the maintainer saw. The picture and the console are
two things that happen to share a builder. The fix is to rebuild the picture
alone, and to reset the tail only when the run changes or the route says
`reset`.

### Flashing

Candidates, each to be confirmed or cleared by measurement:

- `plotly.react` on scattergl traces rebuilds the WebGL scene when the trace
  count changes. It changes when the background trace appears
  (`snap.y_bkg.some(v => v)`) or a tick row is added, so a stage that first
  frees the background can flash the whole plot.
- `patchList` moves rows with `insertBefore` into the server's order. A new
  run arrives at the top and shifts every row down under the reader's eye;
  WP-1423 measured one new run and called it one mutation, which it is, and
  it is also a layout shift of the whole list. The chat-log pattern holds the
  viewport: compensate `scrollTop` by the inserted height when the list is
  not scrolled to the top.
- The state pill's class change and the row's `selected` toggle repaint a
  cell. Cheap; confirm they are not shifts.
- The legacy `iframe` reload on a pre-1402 run. Out of scope, named here so it
  is not mistaken for a defect of this page.

### The metric

Cumulative layout shift is the standard measure of exactly this defect:
`new PerformanceObserver(list => …).observe({type: 'layout-shift',
buffered: true})` yields one entry per shift with a score and the elements
that moved. The browser test injects the observer at load and reads the sum
after a stage boundary, a new run and a resize. WP-1423 counted distinct
states by hand; this observer sees every shift the browser's own layout
engine saw and names the element. A flash is not a layout shift, so the flash
probe is a screencast: frames at 20 fps around a stage boundary through
playwright, counting frames that differ from both neighbours.

## Non-goals

- The plot's marks and colours (WP-1423's fence; WP-1429 owns the palette).
- Resizable panels (WP-1425), which depend on this WP's legend fix.
- Poll cost and payload size (WP-1427). A shift that is a slow redraw is
  1427's; a shift that is a wrong layout is this WP's.
- The GUI's own plot, whose legend rules are `lib/plot.ts`'s.

## Tasks

- [ ] Browser test with a layout-shift observer and a frame differ; measure
      today's page over a stage boundary, a new run and three resize widths,
      and record the legend's box at each; the numbers go in the handover
- [ ] The legend holds still under resize, as a dimension the page fixes;
      `viz/html.py`'s legend spec follows if the measurement says its page has
      the same defect
- [ ] The picture is rebuilt alone; the console and its tail survive a change
      of picture kind, and reset only on a run change or a `reset` from the
      route
- [ ] The list holds the viewport when a run arrives above the fold
- [ ] Whatever the frame differ found at a stage boundary, fixed or recorded
      as measured and left, with the reason
- [ ] The test asserts layout shift 0 over the three events and the legend's
      box constant across widths
- [ ] Skill: none. The page is a human's.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_watch_app.py tests/test_watch_browser.py
.venv/bin/python -m ruff check src tests examples
```

The browser test, where it runs, reports a layout-shift sum of 0 over a stage
boundary, a new run and a resize from 1400 to 700 px, and the console's line
count unchanged across a picture kind change.

## References

- web.dev, Cumulative Layout Shift (the `layout-shift` performance entry).
- WP-1423 (the two rules and the harness), WP-1402 and WP-1405 (the two page
  defects no python test could see).

## Handover log

- **2026-09-16** — created, from the maintainer's reading of the page over the
  demo job, unrolled with 1424, 1425 and 1427–1429.

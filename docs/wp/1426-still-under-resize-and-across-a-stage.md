# WP-1426 — still under resize, and across a stage

Milestone: unscheduled · Status: 🔄 2026-09-16 — claimed by @yue-here
Depends on: 1430 (the page as files), 1423 (the rules and the browser harness this extends)

## Goal

Nothing on the `rietx watch` page flashes or shifts when a stage lands or a
run appears, and a window resize moves the legend with the plot and nothing
else. The console keeps its lines when the picture changes. A browser test
reads the page's layout-shift entries and finds none over a stage boundary
and a new run.

## Context

WP-1423 made the page hold still between polls, measured as distinct states of
each element over 25 s. The maintainer's next reading found movement it did
not measure: the legend jumps into the middle of the plot on a window resize;
changing the plot also reloads the console; and there is still jitter and
flashing to look into. This WP takes those three and the metric that covers
the class.

### The legend

`drawSnapshot` lays the legend out horizontally with `legend: {orientation:
'h', y: 1.02, yanchor: 'bottom', x: 0}` under `margin: {t: 8}`. `viz/html.py`
line 146 uses the same spec. Where the legend sits today, and where it goes
after a resize, has not been looked at; the maintainer's report is the only
observation. Two things about the spec are worth knowing before measuring. A
legend anchored above the plot area lives in the top margin, and eight pixels
is less than one legend row. A horizontal legend wraps when its entries (one
`hkl: <phase>` row per phase, widened by the `(n of m)` cap) exceed the
width, and plotly re-lays it on `Plots.resize`. The first task records the
legend group's bounding box, relative to the plot area's, before and after a
resize at 1400, 1000 and 700 px.

Whatever the measurement shows, the fix must obey WP-1423 rule 2. The legend's
box is a dimension the page fixes. Two forms satisfy it: the legend inside the
paper at a fixed anchor (`y: 1, yanchor: 'top'`), or an HTML legend the page
owns in a strip of declared height with `showlegend: false`. Prefer the first
if it measures still; it keeps the picture `viz/html.py`'s.

### The console

`drawRun` rebuilds the shell whenever `shell.kind` changes:

```js
if (shell.id !== id || shell.kind !== kind) buildShell(run, kind);
```

`buildShell` sets `$('console').textContent = ''` and resets `tail` to offset
0. A run opened before its first snapshot has kind `none`; at the first stage
boundary it becomes `json`, the shell is rebuilt, and the console is wiped and
re-tailed from the start of the log (`tail_events` serves up to 4 MB per
call). That is the one cause the code shows. It only fires on a run opened
before its first snapshot, so the first task also reproduces the maintainer's
observation on a run that already had one, and looks further if it
reproduces there. Either way the picture and the console are two things
sharing one builder, and the fix is to rebuild the picture alone and reset the
tail only when the run changes or the route says `reset`.

### Flashing

Candidates, each to be confirmed or cleared by the frame differ:

- `plotly.react` on scattergl traces rebuilds the WebGL scene when the trace
  count changes. It changes when the background trace appears
  (`snap.y_bkg.some(v => v)`) or a tick row is added, so a stage that first
  frees the background can flash the whole plot.
- `patchList` moves rows with `insertBefore` into the server's order. A new
  run arrives at the top and shifts every row down under the reader's eye.
  WP-1423 measured one new run and called it one mutation, which it is; it
  is also a layout shift of the whole list. The chat-log pattern holds the
  viewport: compensate `scrollTop` by the inserted height when the list is
  not scrolled to the top.
- The state pill's class change and the row's `selected` toggle repaint a
  cell. Cheap; confirm they are not shifts.
- The legacy `iframe` reload on a pre-1402 run. Out of scope, named here so it
  is not mistaken for a defect of this page.

### The metric, and where it does not apply

Layout shift is the browser's own measure of this defect:
`new PerformanceObserver(cb).observe({type: 'layout-shift', buffered:
true})` yields one entry per shift with a score and the elements that moved.
The browser test installs the observer at load and reads the sum after a
stage boundary and after a new run. WP-1423 counted distinct states by hand;
this observer sees every shift the layout engine saw and names the element.

It does not apply to a resize. A resize moves everything by design, so a
zero over a resize is not a bar anything could pass. The resize assertion is
the legend's box relative to the plot area, constant across the three widths.
Flashing is not a layout shift either. Its probe is a screencast: frames at
20 fps around a stage boundary through playwright, counting frames that
differ from both neighbours. The screencast is a measurement and not a gate;
what it finds is fixed or recorded.

### The page this edits

WP-1430 took the page out of its python string on 2026-09-16, so everything
below is a file. `src/rietx/watch/static/` holds `index.html`, `watch.css`,
`watch.mjs` (the document half) and `watch-core.mjs` (everything that touches
no DOM). Five facts carry into this WP's edits.

- **A new file under `static/` needs a row in `watch.STATIC_FILES`** and
  nothing else. The route, the content type and the `.gitignore` guard all
  read that dict. A DOM half is `.mjs`, because `node --check` reads a `.js`
  as CommonJS and the `import` of `watch-core.mjs` is a syntax error there.
- **Node cases live in `tests/watch_core.test.mjs`**, since hatchling ships
  everything under `src/rietx`. `tests/test_watch_app.py::test_the_pure_half_of_the_page_is_unit_tested`
  invokes the 15 of them.
- **The page's three build constants ride on `/api/runs`** as
  `payload.page.{suffix,dist,palette}`, read at boot into module-level `HUE`
  and `DIST`. A file cannot carry the `@TOKEN@` substitutions they were.
- **`drawSnapshot` opens with `if (!HUE) return false;`.** A poll can reach
  the draw before the first `/api/runs` has landed the palette. Keep the
  guard in whatever `drawSnapshot` becomes.
- **`tests/test_watch_browser.py` took no diff across 1430 and stays the
  bar.** If it moves, the page moved.

### The Δ/σ ladder's spike guard, handed over as a call

`rangesOf` takes the residual's `floor(0.999 · n)`th value. That index *is*
`n - 1` for every n ≤ 1000, so the "99.9th percentile" is the maximum on a
short pattern and one spiked point sets the ladder's scale for the whole run.
Above 1000 it bites as intended: a snapshot decimates to
`viz/snapshot.MAX_POINTS` = 4000, where a lone 900σ point is cut and a
ten-point misfitted peak is not. WP-1430 pinned both directions in
`tests/watch_core.test.mjs` as the behaviour rather than the intention,
because its fence was that nothing the page does changes. The axis is this
WP's subject, so the call belongs here.

## Non-goals

- The plot's marks and colours (WP-1423's fence; WP-1429 owns the palette).
- Resizable panels (WP-1425), which depend on this WP's legend fix.
- Poll cost and payload size (WP-1427). A shift that is a slow redraw is
  1427's; a shift that is a wrong layout is this WP's. Both rewrite
  `drawRun`; whichever lands second rebases.
- The GUI's own plot, whose legend rules are `lib/plot.ts`'s.

## Tasks

- [ ] Browser test with a layout-shift observer and a frame differ; measure
      today's page over a stage boundary and a new run, record the legend's
      box relative to the plot at three widths, and reproduce the console
      reload on a run that already had a snapshot; the numbers go in the
      handover
- [ ] The legend holds still under resize, as a dimension the page fixes;
      `viz/html.py`'s legend spec follows if its page shows the same defect
- [ ] The picture is rebuilt alone; the console and its tail survive a change
      of picture kind, and reset only on a run change or a `reset` from the
      route
- [ ] The list holds the viewport when a run arrives above the fold
- [ ] Whatever the frame differ found at a stage boundary, fixed or recorded
      as measured and left, with the reason
- [ ] The test asserts layout shift 0 over a stage boundary and a new run,
      the legend's box constant relative to the plot across the three
      widths, and the console's line count unchanged across a picture kind
      change
- [ ] The spike guard's short-pattern case: fixed, or recorded as measured
      and left, with the reason (inherited from 1430)
- [ ] Skill: none. The page is a human's.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_watch_app.py tests/test_watch_browser.py
.venv/bin/python -m ruff check src tests examples
```

The browser test, where it runs, reports a layout-shift sum of 0 over a stage
boundary and a new run, the legend's box constant relative to the plot area
from 1400 to 700 px, and the console's line count unchanged across a picture
kind change. It skips without a cached chromium, CI included; the handover
names the skip.

## References

- web.dev, Cumulative Layout Shift (the `layout-shift` performance entry).
- WP-1423 (the two rules and the harness), WP-1402 and WP-1405 (the two page
  defects no python test could see).

## Handover log

- **2026-09-16** — created, from the maintainer's reading of the page over the
  demo job; revised the same day: the resize case no longer claims a zero
  layout shift, and the console cause is stated as the one the code shows.

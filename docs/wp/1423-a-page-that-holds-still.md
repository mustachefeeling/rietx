# WP-1423 — a page that holds still

Milestone: unscheduled · Status: 🔄 2026-09-15 — claimed by @yue-here
Depends on: 1405 (the page this reworks), 1402 (the snapshot it draws)

## Goal

`rietx watch` shows a run list and the selected run side by side, either
panel collapsible, and nothing on the page moves unless the thing it shows
changed. Column widths, the plot's axes and geometry, the status line and the
scroll position of every pane hold still across polls. A reader can leave the
page open beside an agent's job and read it at a glance.

## Context

The page was demonstrated on 2026-09-15 over an agent-shaped job: the eight
CPD round-robin mixtures chained both ways, sixteen fits of eight stages in
one run directory, a new run every 18 s. The maintainer's report: every
element jitters when something changes, columns resize, plot scales and axes
move, and the scroll bars go wild on every update.

### Measured, before

Chromium 1223 at 1400×900, driving the page for 25 s over that job
(`docs/wp/1423` probe, macOS arm64, worktree `[dev]` venv plus playwright).
One poll is 1.2 s.

The run list:

| What | Distinct states in 25 s | Cause |
|---|---|---|
| whole-table rewrites | 21 | `drawList` sets `body.innerHTML` every poll |
| column width sets | 4 (run column 160 to 336 px) | auto table layout follows the content |

A table rewritten every poll also drops the hover, the text selection and,
on a list longer than the window, the scroll position.

The run page:

| What | Distinct states in 25 s | Cause |
|---|---|---|
| crumb rewrites | 28 | `crumb.innerHTML` every poll |
| bar height | 29 and 51 px | the crumb wraps once the stop button and the point count are on it |
| plot top edge | 29 and 51 px | it follows the bar |
| stop button x | 100, 103, 141 px | the state pill and label before it change width |
| x range | 8 | plotly's autorange over a decimated set that differs per stage |
| intensity range | 7 | autorange over calculated as well as observed; 7812 to 8021 within one pattern, 25 804 on another |
| Δ/σ range | 8 | autorange per stage, ±14 to ±112 |
| tick rows | move with the Δ/σ range | placed in Δ/σ units below its data |
| point count note | 7 | drawn count differs per stage |

The plot's inner area was constant (`_size` 58, 47, 1328, 489) whenever the
bar was: the geometry that moved was the bar's. The console followed its tail
correctly, but its scroll width ran 1639 to 1871 px against a 1400 px pane, so a
horizontal bar comes and goes.

### The class

Every one of these is one of two things. Content is rewritten wholesale where
it should be patched, so state the browser holds for the reader (scroll,
hover, focus) is thrown away. Or a dimension is derived from the current stage
where it should be derived from the data or fixed by the page, so it moves when
the fit moves.

The fix is therefore two rules, applied everywhere on the page.

1. **Patch, never rewrite.** Rows are keyed by run id and updated cell by cell.
   The status line is fixed slots whose text changes. The stop button exists
   once and is shown or hidden. Nothing sets `innerHTML` on a container that
   scrolls or that the reader might be pointing at.
2. **A dimension comes from the data or from the page, never from the stage.**
   Column widths are declared (`table-layout: fixed`). The bar is one line
   that clips. The x range is the pattern's 2θ span and the intensity range is
   the observed curve's, both constant across the stages of one pattern (the
   decimation keeps the endpoints and the bucket extremes, so both are exact
   from the snapshot). The tick rows sit on their own axis with a fixed
   domain. Margins are fixed and `automargin` stays off.

The Δ/σ range is the one dimension that is the fit's and not the data's. A
range pinned at the first stage hides the answer at the last: ±112 at the
first warm start against ±15 at convergence, so the ±3 band would be 3 % of
the panel. A range that autoranges per stage is the strobe the maintainer
saw. It takes a **ladder**: symmetric ±L with L the smallest of
3, 5, 10, 20, 50, 100, 200, 500, 1000 at or above the 99.9th percentile of
|Δ/σ|. On the measured run that is three changes across a fit where autorange
made eight, each a step of at least ×2, and a reader who has zoomed keeps
their zoom through `uirevision`. The percentile and not the max, so one
spiked point does not set the scale for the run; 99.9 and not 99, so a
misfitted peak of ten points still does.

### Two panels

Today the list and the run are two pages. The list is where an agent's job
shows up (a new run every 18 s on the demo) and the run is where the fit is
judged, and a reader watching an agent needs both at once. The page becomes
one view: the run list on the left, the selected run on the right, each with
a toggle that collapses it and gives the other the width. The choice persists
in `localStorage`. With no run in the URL the page follows the newest run, so
opening `rietx watch` shows what is happening now; clicking a run pins it and
`all runs` unpins. A directory that is itself a run has no list to show and
the toggle is hidden.

The status line moves off the bar into the run panel, where it can be a fixed
strip. For a series it now also says which pattern is being fitted: the
recorder copies the `series_index`/`series_n`/`series_label`/`series_pass`
stamp off `stage_start` into `status.json`, four declared fields with a named
writer. Without them a run page shows "ramp · stage biso" and the one fact
that matters about a series is in the console tail only.

### What sees layout

A python test cannot (WP-1402, WP-1405 both learnt this). `node --check`
catches syntax. Layout takes a browser, so this WP adds a test that drives the
page in chromium through playwright when both are importable and skips
otherwise, and the probe script's numbers are the acceptance. playwright is
not a dependency (`docs/manual/make_screenshots.py` says why) and CI will
skip the test; the handover names that skip.

### Inherited

—

## Non-goals

- The GUI's own live panel (`gui/`), which draws from an in-process ring.
- Any new verb. The page reads, and stops (WP-1405), and that is all.
- A different plot: the marks, colours and the Δ/σ panel are `viz/html.py`'s
  and stay.
- Filtering, search or grouping of the run list. A directory a batch writes
  into is the grouping there is.

## Tasks

- [x] The status carries a series pattern's position, read off the stamp
- [x] The page: two panels with a collapse each, following the newest run when none is chosen; the list patched in place under fixed columns; the status strip fixed slots and the stop button one element; the plot's axes from the data, the Δ/σ range from a ladder, the ticks on their own axis (one template, one commit)
- [x] A browser test that measures what holds still, skipped where it cannot run
- [x] Manual: the `rietx watch` section says what the page is now; the v1.4 record stages the change
- [x] Skill: none. The page is a human's; an agent driving rietx never reads it.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_watch_app.py tests/test_watch_browser.py tests/test_telemetry.py tests/test_runs.py
.venv/bin/python -m ruff check src tests examples
```

The browser test, where it runs, asserts over two polls that rewrite the
snapshot and the status: column widths, bar height, plot inner size, x and
intensity ranges and the list's scroll position are unchanged, and the run
list is not rebuilt.

## References

- Toby, B. H. (2024), the Δ/σ residual convention `viz/html.py` follows.
- WP-1401, 1402, 1405: the page's three prior sessions.

## Handover log

- **2026-09-15** — created, from the maintainer's report on the live demo,
  with the measurements above taken the same evening.

# WP-1425 — the panels are the reader's to size

Milestone: unscheduled · Status: ⬜
Depends on: 1426 (the legend must hold still under resize before a splitter makes resize continuous); 1423 soft

## Goal

The two seams of the `rietx watch` page, list against run and picture against
console, are splitters a reader can drag, collapse and restore. The sizes
survive a reload and are re-clamped against the window they reopen in. The
`runs` and `run` toggle buttons are gone.

## Context

WP-1423 made the page two panels with a collapse each. The maintainer's first
line about the result was that the two toggles, labelled `runs` and `run`,
are confusing, and the fourth line asked for resizable panels. The two asks
have one answer. A splitter with a collapse affordance on its grip does what
the buttons do and says where it does it.

### What is on the page today

`src/rietx/watch.py`, `_PAGE_TEMPLATE`. `#runs { flex: 0 0 72ch }` and
`#console { flex: 0 0 30% }` are the two fixed sizes. `applyPanels` writes
`data-runs`/`data-run` on the body from a `localStorage` key
(`rietx-watch-panels`) and calls `Plotly.Plots.resize` on the plot when the
run panel reopens, because plotly's `responsive` option follows the window
and not the element. `togglePanel` refuses to close the last open panel.

### The GUI already has the rules

`gui/CLAUDE.md` § Usability, from WP-1029, with the code in
`gui/src/lib/resize.ts` and `gui/src/panels/Splitter.svelte`:

- **Report a size, never write one.** The grip calls `onsize(size, done)`
  and the owner persists on the verb.
- **A stored size is not a settled size.** A drag clamps against the extent it
  happens in, and nothing clamps a width that outlives its window, so the
  owner re-clamps at render (`clampSize`, `fitColumns`). Widths chosen at
  1500 px reopened at 1000 px left a column 24 px wide.
- **One resize in flight, at most one queued** (`resize.ts:coalesce`), because
  a plotly resize per pointer move is a redraw per pointer move.
- The grip flows `inline`, because an absolute grip inside `overflow: auto`
  scrolls away from the edge it marks.

The watch page is vanilla JavaScript in a python string and cannot import a
Svelte component. It ports the rules and the arithmetic of `clampSize` and
`dragged`, and names them in a comment. WP-1429 may later give the two pages a
shared script file; until then the port is the answer, and a test pins the
watch copy of `clampSize` to the GUI's on a table of inputs
(`gui/src/lib/resize.test.ts` already has the cases).

### The documented pattern

WAI-ARIA's window splitter: the grip is focusable, `role="separator"`,
`aria-orientation`, `aria-valuenow/min/max`, arrow keys move it, Enter or a
double-click collapses and restores. That is the supported mechanism for both
the pointer and the keyboard, and it is what replaces the two buttons.

### Measured before, to take at the start

WP-1423's browser harness (`tests/test_watch_browser.py`) is the tool. Record,
over a drag of the list splitter from 72ch to 40ch: how many `Plots.resize`
calls plotly saw, how many layout-shift entries the page produced, and the
plot's inner size before and after. The legend's position is WP-1426's and
must already hold.

## Non-goals

- Column widths inside the list. Declared (WP-1423 rule 2).
- Persisting sizes anywhere but `localStorage`. The page has no project and no
  settings document; the GUI's `ProjectDoc.ui` is not this page's.
- Splitting the picture from the strip. The strip is one line by rule.
- The GUI's own panels, which already have this.

## Tasks

- [ ] Measure: the drag probe above, before any change, in the handover
- [ ] The list splitter: a grip between `#runs` and `#run`, pointer and
      keyboard, sizes in px re-clamped at render, `Plots.resize` coalesced to
      one per animation frame
- [ ] The console splitter: the same grip between `#picture` and `#console`
- [ ] Collapse and restore on the grip (double-click, Enter), with the last
      panel refusing to close; the `runs`/`run` buttons and `data-runs`/
      `data-run` removed, the stored key migrated or dropped
- [ ] Browser test: drag moves the seam, reload keeps it, a narrower viewport
      re-clamps it, the plot's inner size follows, the layout-shift score
      over the drag is what the measurement made it
- [ ] Manual: `docs/manual/using/cli.md` § `rietx watch` and the screenshot
- [ ] Skill: none. The page is a human's.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_watch_app.py tests/test_watch_browser.py
.venv/bin/python -m ruff check src tests examples
npm --prefix gui test
```

The browser test drags each grip, reloads, and asserts the size persisted and
was clamped at a 900 px viewport. A test pins the page's `clampSize` to the
GUI's on the GUI's own cases.

## References

- WAI-ARIA Authoring Practices, Window Splitter pattern.
- WP-1029 (the GUI's resize rules), WP-1423 (the panels).

## Handover log

- **2026-09-16** — created, from the maintainer's reading of the page over the
  demo job, unrolled with 1424 and 1426–1429.

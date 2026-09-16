# WP-1425 — the panels are the reader's to size

Milestone: unscheduled · Status: ⬜
Depends on: 1430 (the page as files, so the port below is importable), 1426 (the legend must hold still under resize before a splitter makes resize continuous)

## Goal

The two seams of the `rietx watch` page, list against run and picture against
console, are splitters a reader can drag, collapse and restore. The sizes
survive a reload and are re-clamped against the window they reopen in. The
two toggle buttons are gone, their job done by the grips.

## Context

WP-1423 made the page two panels with a collapse each. The maintainer asked
for resizable panels. Separately, the two toggles were confusing; WP-1424
renames them as the interim, and this WP removes them, because a grip that
collapses is one control where there were three.

### What is on the page today

`#runs { flex: 0 0 72ch }` and `#console { flex: 0 0 30% }` are the two fixed
sizes. `applyPanels` writes `data-runs`/`data-run` on the body from a
`localStorage` key (`rietx-watch-panels`) and calls `Plotly.Plots.resize` on
the plot when the run panel reopens, because plotly's `responsive` option
follows the window and not the element. `togglePanel` refuses to close the
last open panel.

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

The page cannot import a Svelte component or the GUI's TypeScript. It ports
`clampSize` and `dragged` into `watch-core.mjs` (WP-1430) and the port is
pinned to the original: a `node --test` case table copied from
`gui/src/lib/resize.test.ts`, with a comment naming the source and a
`test_watch_app.py` check that the two tables are equal text. If the GUI's
test changes its cases, the copy fails until it follows.

### The documented pattern

WAI-ARIA Authoring Practices, window splitter: the grip is focusable,
`role="separator"`, `aria-orientation`, `aria-valuenow/min/max`, arrow keys
move it, Enter or a double-click collapses and restores. It is a pattern and
not a library, so the JavaScript is still the page's; the pattern fixes what
the keyboard does so nobody invents it.

### Measured before, to take at the start

WP-1423's browser harness (`tests/test_watch_browser.py`) is the tool. Record,
over a drag of the list seam from 72ch to 40ch: how many `Plots.resize`
calls plotly saw, and the plot's inner size before and after. The legend's
position is WP-1426's and must already hold.

### Inherited

- **2026-09-16, from [1430](1430-the-page-is-a-file.md): the page is files, and
  three of its names are not the ones 1430's plan said.** `watch.py` is the
  package `watch/`, and the page is `watch/static/`: `index.html`, `watch.css`,
  `watch.mjs` (the document) and `watch-core.mjs` (everything that touches no
  DOM). `rietx.watch` imports unchanged. What to carry:
  - **The DOM half is `.mjs`, not `.js`.** `node --check` reads a `.js` as
    CommonJS, where the `import` of `watch-core.mjs` is a syntax error. A
    browser cares about `type="module"` and the content type, never the
    extension.
  - **Node cases live in `tests/watch_core.test.mjs`**, not beside the module:
    hatchling ships everything under `src/rietx`. They are invoked from
    `tests/test_watch_app.py::test_the_pure_half_of_the_page_is_unit_tested`
    (15 cases today), which passes `--test-reporter=tap` because node picks its
    reporter by whether stdout is a terminal.
  - **`@SUFFIX@`, `@DIST@` and `@HUE@` are gone.** A file cannot carry a token,
    so the three ride on `/api/runs` as `payload.page.{suffix,dist,palette}`,
    read at boot into the module-level `HUE` and `DIST`. That is 299 B of every
    poll, against rows of 735 B each.
  - **A new file under `static/` needs a row in `watch.STATIC_FILES`** and
    nothing else — the route, the content type and the `.gitignore` guard all
    read that dict. `*.html` in `.gitignore` swallowed `index.html` on the way
    in, the sixth committed file that one rule has taken.
  - The panel state is already split the way this WP wants `clampSize`:
    `parsePanels(raw)` and `nextPanels(p, which)` are in `watch-core.mjs` with
    cases, and `watch.mjs` keeps `localStorage` and the document. Put the port
    beside them.
  - `tests/test_watch_browser.py` took no diff and stays the bar: if it
    moves, the page moved.

## Non-goals

- Column widths inside the list. Declared (WP-1423 rule 2).
- Persisting sizes anywhere but `localStorage`. The page has no project and no
  settings document; the GUI's `ProjectDoc.ui` is not this page's.
- Splitting the picture from the strip. The strip is one line by rule.
- The GUI's own panels, which already have this.

## Tasks

- [ ] Measure: the drag probe above, before any change, in the handover
- [ ] `clampSize` and `dragged` in `watch-core.mjs`, pinned to the GUI's cases
- [ ] The list splitter: a grip between `#runs` and `#run`, pointer and
      keyboard, sizes in px re-clamped at render, `Plots.resize` coalesced to
      one per animation frame
- [ ] The console splitter: the same grip between `#picture` and `#console`
- [ ] Collapse and restore on the grip (double-click, Enter), the last panel
      refusing to close; the two buttons and `data-runs`/`data-run` removed,
      the stored key migrated or dropped
- [ ] Browser test: drag moves the seam, reload keeps it, a 900 px viewport
      re-clamps it, the plot's inner size follows
- [ ] Manual: `docs/manual/using/cli.md` § `rietx watch` and the screenshot
- [ ] Skill: none. The page is a human's.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_watch_app.py tests/test_watch_browser.py
.venv/bin/python -m ruff check src tests examples
node --test src/rietx/watch/static/
```

The browser test drags each grip, reloads, and asserts the size persisted and
was clamped at a 900 px viewport. `node --test` runs the GUI's `clampSize`
cases against the port. The browser test skips without a cached chromium, CI
included; the handover names the skip.

## References

- WAI-ARIA Authoring Practices, Window Splitter pattern.
- WP-1029 (the GUI's resize rules), WP-1423 (the panels), WP-1430 (the module
  the port lives in).

## Handover log

- **2026-09-16** — created, from the maintainer's reading of the page over the
  demo job; revised the same day: the toggle rename went to 1424 as the
  interim, and the port's pin is now a copied case table under `node --test`.

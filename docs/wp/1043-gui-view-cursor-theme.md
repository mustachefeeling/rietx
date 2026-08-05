# WP-1043 — GUI defects found by use: the view, the armed cursor, the theme

Milestone: v1.0 · Status: 🔄 2026-08-06 — three of four reported items landed
Depends on: 1029 (theming), 1032–1033 (`Plot.svelte`, the armed gesture), 1027 (peaks)

## Goal

Four defects reported from a use session are fixed, each with the browser
measurement that found it: a horizontal zoom survives an excluded region, a peak
edit does not throw the view away, an armed range gesture says so at the pointer,
and a theme chosen once stays chosen when another project is opened.

## Context

The four, as reported:

1. *Theme does not persist on loading a project.*
2. *Horizontal zoom does not work when there are excluded regions.*
3. *When selecting range/regions, the cursor changes to the zoom cursor.*
4. *On selecting/deselecting peaks, the zoom immediately resets.*

**2 and 4 are one defect** and neither is about the thing it was reported
against. Every redraw handed `Plotly.react` a layout with no `range`, so plotly
re-autoranged over *everything drawn* — and what is drawn is not only the fetched
window: the peak markers span the whole pattern (the list is not windowed), and
so do the mask shapes, which are `xref: "x"` and therefore take part in the
autorange, the same property `maskShapes` was already clipping against
(WP-1033). Measured in Chrome on the synthetic fixture (`tests/output` of this
WP's browser pass), a drag to **9.97–14.66°** came back as:

| also on the plot            | axis after the refetch |
|-----------------------------|------------------------|
| nothing                     | 9.97–14.66 ✓           |
| a peak list                 | 4.57–24.85             |
| an excluded region at 4–5°  | 3.99–24.88             |
| an excluded region at 20–21°| 4.57–24.85             |
| a fitted range of 8–18°     | 3.00–24.94             |

So the zoom worked only on a plot with nothing else on it. The same react is
what threw the view away on a peak edit — and on the **raw** view (no fit) there
is not even a window fetch to land back in, so a shift-click went 9.97–14.66 →
the full 1.74–25.25 in one gesture.

The repair is WP-1015's rule for the 3D camera, one panel over: **`react`
rebuilds the scene, so the view must be handed back on every draw**, read off
`_fullLayout` immediately before the call rather than tracked in a variable.

3 is measured too: plotly's `updateFx` gives the drag layer `cursor-crosshair`
for every dragmode that is not `pan`, so `dragmode: "select"` and
`dragmode: "zoom"` are pointer-identical — arming changed the mode and nothing
under the pointer said so.

1 is a design question rather than a bug in the code that implements it.
WP-1029 persisted the theme in `ProjectDoc.ui` "like every other GUI setting",
and `readUi()` therefore *re-reads it per project*: measured, choosing dark and
then opening a second project comes back `system`. A width or Simple/Advanced is
plausibly the project's; a theme is a fact about the person and the room they
are in.

## Non-goals

- The GUI manual and onboarding — WP-1017.
- Persisting anything else at app level; `/api/settings` opens the store with
  one key in it and the same open-dict rule `ProjectDoc.ui` has.
- Migrating a stored `ui.theme` out of existing projects: the key is simply no
  longer read (the frontend owns those keys, and an unread one is inert).

## Tasks

- [x] The view is handed back on every draw (`lib/plot.ts:heldRanges`/`span`,
      `Plot.svelte`) — fixes 2 and 4, and the window a redraw refetches follows
      the axis instead of falling back to the whole pattern.
- [x] An armed range gesture gets its own cursor (`col-resize` on the plot-area
      rect, which beats an inherited one with no specificity fight).
- [x] The theme is the person's, not the project's: `GET`/`POST /api/settings`
      over `state_dir/settings.json`, beside `recent.json`.
- [x] Tests: vitest over `heldRanges`/`span` and the panel's own draw;
      `test_gui_server.py` over the settings store.
- [ ] Docs: `gui/CLAUDE.md` rules, ROADMAP row, handover.

## Acceptance

```sh
npm --prefix gui test && npm --prefix gui run check
npm --prefix gui run build && git diff --exit-code src/pxrdref/gui/static
.venv/bin/python -m pytest tests/test_gui_server.py tests/test_gui_dist.py
.venv/bin/python -m ruff check src tests examples
```

and, in a real browser against a fitted project (the pass this WP was built
from): a drag zoom holds with a peak list, an excluded region and a fitted range
on the plot; one drag costs exactly one `/api/result/window` fetch; a peak
toggle keeps the view and refetches *that window*; a double-click still resets
to the whole pattern; a panel's zoom request still moves the axis, twice in a
row for the same region; the armed cursor is `col-resize` and returns to
`crosshair` on Esc.

## References

- WP-1015 — "`react` with fresh trace objects resets the gl3d camera, so the
  view must be handed back on every draw"; the rule this reuses.
- WP-1033 — `maskShapes`, and the measurement that a data-referenced shape takes
  part in the autorange (bands drawn past the data *became* the range).
- WP-1029 — the three-way theme and `ProjectDoc.ui`; this WP moves one key out.

## Handover log

- **2026-08-06** — created; the plot's view fix and the armed cursor landed
  against a browser pass (`scratchpad/{zoomcheck,verify,request}.mjs`).

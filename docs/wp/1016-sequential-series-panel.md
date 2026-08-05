# WP-1016 — Sequential series panel

Milestone: v1.0 · Status: ⬜
Depends on: WP-1008, WP-1010, WP-1011

## Goal

An in-situ/parametric series is drivable from the GUI: multi-file upload →
ordered series → `SequentialRefinement` run with live per-pattern progress →
trajectory plots with esds, with path-dependence surfaced as the headline
warning and per-pattern drill-down into each pattern's own history tree.

## Context

- Backend exists: `SequentialRefinement` (`sequential.py:220`) /
  `refine_sequential` (`:644`) → `SeriesResult`
  (`schemas/sequential.py:111` — mode, `entries: list[SeriesEntry]`,
  x_label, direction, diagnostics, provenance). A series is N separate
  refinements chained by a warm start — one history tree per pattern,
  pinned by `TreeHeader.data_fingerprint` — not `multi.py`'s joint
  residual; the panel must not blur that.
- Events: the series needs a series-level wrapper forwarding each
  pattern's `fit_start`/`fit_end` (`history/events.py:38` EventKind) to the
  GUI's SSE stream with a `series_index` field — additive, same `v="1"`
  rule as WP-1006.
- **`direction="both"` disagreement is the headline, not a footnote**:
  `SEQUENTIAL_PATH_DEPENDENT` (emitted per parameter at `sequential.py:631`,
  consumed by `viz/plots.py:185`) is the only check separating a measured
  trajectory from an ordering artefact — a smooth curve is exactly what a
  poisoned chain produces (WP-0505's measured lesson). The panel renders
  flagged parameters' trajectories visually distinct and puts the warning
  at the top of the series view.
- Trajectory plots: per-parameter value ± esd vs series index (or x_label),
  from `SeriesResult` — the payload matches what `SeriesResult` carries
  (state, not curves; per-pattern obs/calc comes from checking out that
  pattern's tree).
- Carry-glob editor behind Advanced disclosure: WP-0505 measured that
  `carry` is a **control** for parameters that provably must not chain, not
  tuning — the editor's help text says so.
- Defaults follow the measured WP-0505 results: `refit="single"`, carry
  everything; do not re-litigate them in the UI.

### Inherited

From **[1034](1034-panel-layout.md)** (closed 2026-08-05) — this panel is the
**ninth** tab, and two things follow. The strip already **wraps** rather than
truncating (no label is shortened, the buttons do not grow), so a ninth costs a
second row at a narrow column and nothing else — but pick a short label, because
eight already fill a 455 px strip. And **the full-window hatch is free**: the
header's `Split | Full` expands the whole column with its tabs, so a trajectory
panel that wants width does not need a mode of its own — which is what the two
panes that had one gave up. A panel that cannot work below some width should say
so the way `Model.svelte` does: measure its floor, put the threshold in
`lib/resize.ts` as arithmetic over the parts, and reflow.

From **WP-1029** (GUI usability, landed 2026-07-30): **the splitter you were told
to expect exists — use it, do not build a second one.**
`panels/Splitter.svelte` over `lib/resize.ts`, carrying `Console.svelte`'s rule
generalised: the component **reports a size and never writes one**, emitting
`onsize(size, done)` where `done` is false on every pointer move and true once on
release, so a drag renders live and persists once. Two flows: `overlay` (an
absolute grip on a pane's own edge, needing a positioned ancestor) and `inline`
(a flex item *between* two panes) — a scrolling pane needs `inline`, because an
absolute edge inside `overflow: auto` scrolls away from the edge it is meant to
be. A series panel splitting a trajectory list from a per-pattern plot wants the
inline form.

Two rules that came with it and are not optional. **Widths persist in
`ProjectDoc.ui`**, owned by the shell rather than by the panel (the panel takes a
`columns`-style prop and an `oncolumns` callback; see `panels/Model.svelte`). And
**a stored size must be re-clamped at render, not only at drag** — `fitColumns`
in `lib/resize.ts` — because a drag clamps against the extent it happens in and
nothing clamps a width that outlives its window. Measured: widths chosen at
1500 px reopened at 1000 px left a column **24 px** wide before that landed.

Also: the plot's residual and scaling knobs are `lib/plot.ts`, and a series panel
drawing per-pattern residuals should reuse `residual()` rather than re-deciding
what Δ/σ means — `/api/result/window` sends all three curves plus a `weighted`
flag precisely so no client has to.

From **WP-1014** (import & in-GUI editing, landed 2026-07-30): **the upload
machinery is how N patterns get in.** `POST /api/upload/pattern` stages one file
and answers with the reader that claimed it, the point count, the 2θ range,
whether the file carries σ, and a decimated preview curve; the token it returns is
what `project_new` takes. A series panel wanting to load a directory of ramp
patterns should loop that verb rather than inventing a second ingest path — and
note the two-phase property it buys, which matters more for 40 files than for one:
*a file that does not parse is a message, not a half-built project*.

Two specifics. `preview_pattern` reports `has_sigma` per file, and a series whose
files disagree about that is a weighting inconsistency worth surfacing before the
chain runs (CLAUDE.md, Weights). And an upload's **token is session-scoped** —
`UploadStore` is emptied by `GuiSession.close`, so a panel must commit its uploads
within the session that staged them, not persist tokens anywhere.

From **WP-1015** (structure viewer, landed 2026-07-30): **there is now one plotly
loader, and one trap every panel that plots must avoid.**

`gui/src/lib/plotly.ts` is the shared runtime loader (`loadPlotly()`, a
deduplicating promise around the `<script src="/plotly.js">` injection that
WP-1010 kept out of the dist). A trajectory plot should call it rather than copy
the injection a third time.

The trap is measured, not theoretical: **plotly's `responsive: true` listens for
*window* resizes only.** If a panel puts controls or a caption *below* its plot,
those render after the first payload arrives, the plot's box shrinks under an
already-sized canvas, and the canvas then overhangs and **swallows the clicks** of
everything beneath it — in a real browser the controls look live and are not.
A jsdom mount cannot see this at all (no layout). `Structure3D.svelte` fixes it
with a `ResizeObserver` → `Plotly.Plots.resize`; do the same, or put every control
*above* the plot.

One method note that cost this WP two wrong claims in a row, and applies to any
plotly panel: **reading `gd.layout` back is not a reading of the view.** It
reports whatever was last passed *in*, so a check written that way says a user's
zoom or rotation was preserved when it has been thrown away. Compare screenshots
— but not their hashes, since a re-render differs by a pixel.

The consequence for a 3D panel specifically (measured against plotly 6.9.0,
2026-07-30): **`plotly_relayout` does not fire for a gl3d camera drag at all**,
so a listener for it is not a fallback — it receives nothing, silently. If a
panel needs to preserve a camera across a redraw that replaces traces, read
`gd._fullLayout.scene._scene.getCamera()` immediately before the redraw and hand
it back in; that is private API and it is the only reading of the view there is.
A 2D plot has the same question with a different answer: its zoom lives in
`xaxis.range`, which `uirevision` does keep as long as the trace *count* is
stable.

Also worth knowing: this WP did **not** add a sixth tab — the viewer is a third
column inside the model pane, which leaves the sixth-tab question below exactly
where WP-1013 left it.

From **WP-1013** (landed 2026-07-30): **the tab strip is still five wide, and a
`Series` tab would be the sixth.** WP-1012 warned that six labelled tabs stop
fitting a `clamp(340px, 38%, 560px)` sidebar and handed the question to 1013,
which took the text pane *out* of the strip rather than growing it — but on
grounds that do not transfer: the `.pxt` document is line-oriented and its columns
are aligned so a rectangular selection can hit one field, which a narrow column
undoes. A series panel is a table of per-pattern summaries and trajectories, which
the sidebar suits. So the sixth-tab problem is still open and is now this WP's; the
two shapes available are a full-width **mode** (`App.svelte`'s `textMode`, a header
toggle plus a palette entry, hidden with `class:hidden` so it stays mounted) and a
narrower tab strip. Pick deliberately rather than adding a sixth label and seeing.

From **WP-1011** (landed 2026-07-30): the sidebar is a **tab strip whose tabs all
stay mounted** — add a `Series` tab, not a route or a modal. `lib/table.ts` is
reusable for the per-pattern parameter listing (grouping, the virtual window, and
`formatValue`/`formatEsd`, which render a value at the precision its esd
justifies); a trajectory table is the same shape one axis over. And the plan
editor's preset picker is the thing a series run needs to *reuse* rather than
re-implement, since `refine_sequential` takes the same `PlanSpec` — including its
`refit` semantics, where WP-0505 measured the collapsed single-stage refit as the
default.

From **WP-1012** (landed 2026-07-30): the sidebar is now five tabs
(Parameters, Plan, Report, History, Build) at `clamp(340px, 38%, 560px)`, so a
`Series` tab is the sixth and the strip's width is the thing to check first — see
the same note in WP-1013, which faces it for the text pane.

Two reusable pieces. **`lib/history.ts`'s `layout`** assigns lanes over a
topologically-ordered node list and returns edges with rows and lanes, drawn as
plain SVG — a series is N history trees linked by annotation notes (WP-0505), and
per-pattern lanes are the same shape as per-branch ones, so the renderer is
reusable if the trees are concatenated with the links as edges. And **the
trajectory table's `SEQUENTIAL_PATH_DEPENDENT` flags are `Diagnostic`s**, which
carry `where` but **no numeric field** — the history panel hit the same wall
displaying guard diagnostics per node, and it is recorded in WP-1003's Inherited as
a freeze decision. If the panel wants to sort a trajectory by disagreement
magnitude, expect to need it.

From the **v1.0 GUI plan** (2026-07-29): series routes/panel are v1's only
multi-pattern surface — `ProjectDoc.patterns` stays length 1 (a series is N
patterns *outside* the project's single-pattern model, referenced by the
series run, one history tree each). If this feels awkward in practice,
record it for WP-1003 rather than growing the project schema mid-WP.

From **WP-1008** (GUI server, landed 2026-07-30): **no series routes were
reserved**, deliberately — the shapes in WP-1008's charter came from the GUI plan
and the indexing plan, and a series does not fit the session model as it stands.
Two things to settle here rather than discover:

- **`GuiSession` is one project, and a project is one pattern.**
  `ProjectDoc.patterns` is a list but `Project.open` *refuses* more than one, so
  a series panel either drives N projects (and the session needs a second
  container verb) or runs outside the project container. That decision is this
  WP's, and it is the same seam multi-histogram (WP-0308) will want.
- **The run state machine is single-slot** (`idle | running | cancelling`, one
  worker, one `CancelToken`). A `refine_sequential` run fits it as *one* long run
  — which is right, since `SequentialRefinement` already emits per-pattern
  events and takes `events=`/`cancel=` — so prefer adding a `kind: "series"` to
  `GuiSession.run` over a second machine. The per-pattern progress a panel needs
  is already expressible in the event `data` dict without a new `EventKind`.

## Non-goals

- No multi-histogram (joint residual) UI — different machinery
  (`multi.py`), deferred with the compare/QPA dashboard.
- No series-level parameter editing (edit the model, re-run the series).
- No trajectory analytics beyond what `SeriesResult` + its diagnostics
  already carry.

## Tasks

- [ ] Multi-file upload → ordered series (reorder/remove before run);
      series run/cancel via the session worker.
- [ ] Series event wrapper: per-pattern `fit_start`/`fit_end` → SSE with
      `series_index`; progress "pattern k of N".
- [ ] Trajectory plots with esds; `SEQUENTIAL_PATH_DEPENDENT` parameters
      rendered distinct + headline warning; `direction="both"` toggle.
- [ ] Per-pattern navigation into that pattern's own history tree (loads
      the tree, plot follows).
- [ ] Carry-glob editor behind Advanced, help text per WP-0505.
- [ ] `tests/test_gui_server.py`: series rows on 3 tiny synthetic patterns;
      trajectory payload matches `SeriesResult`.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_gui_server.py -q
npm --prefix gui test
.venv/bin/python -m ruff check src tests examples
```

## References

- WP-0505's measured findings (`refit="single"`, carry hypothesis refuted,
  path-dependence check) — summarised in CLAUDE.md's series paragraph.

## Handover log

- **2026-07-29** — created from the v1.0 GUI plan.

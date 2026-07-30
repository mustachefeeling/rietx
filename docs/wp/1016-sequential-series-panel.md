# WP-1016 — Sequential series panel

Milestone: v1.0 · Status: ⬜ not started
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

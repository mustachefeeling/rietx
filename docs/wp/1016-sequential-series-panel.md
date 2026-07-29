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

From the **v1.0 GUI plan** (2026-07-29): series routes/panel are v1's only
multi-pattern surface — `ProjectDoc.patterns` stays length 1 (a series is N
patterns *outside* the project's single-pattern model, referenced by the
series run, one history tree each). If this feels awkward in practice,
record it for WP-1003 rather than growing the project schema mid-WP.

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

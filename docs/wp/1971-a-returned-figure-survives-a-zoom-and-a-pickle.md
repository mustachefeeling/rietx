# WP-1971 — a returned figure survives a caller's zoom and a pickle

Milestone: unscheduled · Status: 🔄 2026-10-15 — claimed by @yue-here
Track: Render what the fit already knows
Depends on: —
Priority: P3 2026-10-14 — a workaround covers each: `two_theta_range=` zooms, and `fig.savefig` keeps a picture

## Goal

A caller can change the figure a rietx plot returns, as matplotlib allows
any figure to be changed, and a notebook still shows it at its designed
size. The figure can be pickled like any matplotlib figure.

## Context

Both found by WP-1970 on 2026-10-14, on tutorial 01's FAP Le Bail fit
(`[dev]` venv, macOS arm64, matplotlib 3.11.2).

**A caller's zoom.** `fig = best.plot(); fig.axes[0].set_xlim(30, 34)`
makes the figure 30 076 × 871 px when saved tight at 200 dpi, against
1 386 × 871 px before the zoom. `plot_result` places the gutter labels (observed,
calculated, background, the residual, each phase row) and the statistics
annotation in data coordinates, beyond the old x range. `_notebook_png`
saves with `bbox_inches="tight"`, which grows the canvas to reach them. The
documented zoom, `two_theta_range=`, builds a figure of the window's own
data and is unaffected. A sibling to check: `set_ylim`, and a log axis
switched after the call.

**A pickle.** `pickle.dumps(fig)` raises `AttributeError: Can't get local
object '_figure_class.<locals>._NotebookFigure'`. The figure class is built
inside `viz.plots._figure_class`, because the module imports matplotlib
lazily, and pickle finds a class by its qualified name. `copy.deepcopy`
works, and WP-1970's dark copy relies on it.

## Tasks

- [x] The gutter labels and the annotation placed so that a caller's
  `set_xlim` keeps the notebook image at its designed size. Axes or
  figure coordinates are the candidates. Check the pixel pins in
  `tests/test_viz.py` (`PRE_TITLE_RENDER`) before changing any placement.
- [x] `_NotebookFigure` reachable by its qualified name, so a pickle
  round-trips. A module-level class built on first use is the candidate.
- [x] Tests: a zoomed figure's notebook width; a pickle round trip.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_viz.py tests/test_display.py
```

## Handover log

- **2026-10-14** — filed from WP-1970's handover. No open WP owns the
  returned figure: WP-1075, which set the gutter convention, is closed.
  The two findings share one seam, the figure a plot hands back, so they are
  one WP.

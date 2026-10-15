# WP-1971 — a returned figure survives a caller's zoom and a pickle

Milestone: unscheduled · Status: ✅ 2026-10-15 — a caller's zoom keeps the notebook image its
designed size in both directions, and every renderer's figure pickles
Track: Render what the fit already knows
Depends on: —

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

- **2026-10-15** — closed. A caller can zoom a figure a plot returns, in
  either direction, and a notebook still shows it at its designed size. A
  figure from any renderer now pickles and loads back to the same pixels.
  The y direction had not been reported and was the worse of the two:
  a zoom to the lowest twentieth made the image 15 times taller. The
  unzoomed renders are byte for byte what `main` draws, and the stored pixel
  pin that proves it had been skipping on every machine. It is re-pinned.

  *Done.* Gutter labels sit at `_GUTTER_X` of the axes width
  (`get_yaxis_transform`, `indexing.py`'s precedent). Each is an annotation
  anchored inside the axes at its own data height with `annotation_clip`, so
  a y zoom that leaves the height outside the view hides the whole label.
  The statistics line is in axes coordinates, with the y label's arithmetic.
  The two left spines bounded in data coordinates are clipped to the axes'
  height (`_height_clip`). That was the class's third member. Matplotlib
  clips no spine, and after a y zoom one ran 16 000 px past the canvas.
  Pickle: `_NotebookFigure` is found through the module's `__getattr__`. A
  second blocker, the intensity axis's tick formatter, was a lambda and is
  now `partial(_tick_over)`. `PRE_TITLE_RENDER` was pinned to matplotlib
  3.11.1 and so skipped under 3.11.2. It is re-captured from `origin/main`
  at 703d3fbd, and a clip-margin mutation turns it red.

  *Review* (`/code-review high --fix`, five findings, four fixed). A clip
  box sliced a label straddling its edge, and the annotation replaced it.
  The pickle test now drops the cached class before loading. The statistics
  height had used `transScale + transLimits`. The zoom test drew twice. The
  fifth finding was the skipped pin, which this session re-pinned.

  *Measured* (`[dev]`, macOS arm64, matplotlib 3.11.2). Notebook image on
  the synthetic LaB6 fit, designed against zoomed, before the fix: x to
  40-50 % 1 386 → 10 608 px wide; y to the lowest 5 % 871 → 13 369 px tall;
  y to the top half 871 → 1 484. After the fix, no zoom widens any of the
  four panel figures, and the height grows by at most 15 px of 1 073. That
  is `_CLIP_MARGIN`, which a clipped spine reaches; at 0 three of the six
  hashed renders change. A log axis switched after the call grew 14 px
  before and after, so it is not this class. Six renders (default, weighted,
  log, dark, the pattern panel, the notebook PNG) hash identically to
  `origin/main`. All 23 new tests fail against `origin/main`'s `src`.
  Acceptance command: 84 passed, none skipped (the pin had been the skip).
  Fast suite, alone on the machine: 10 451 passed, 191 skipped, 1 xfailed
  in 4:47. `tests/test_viz.py` went from 33 to 56 items, so passed+skipped
  is 23 above `main`'s on this venv, with one skip turned into a pass. `main`
  was not re-measured. The added tests cost 8.56 s in one run: the zoom test
  6.03 s over 12 cases, the pickle test 2.40 s over 10, the hidden label
  0.13 s. The full suite did not run, because no fitted number can move.

  *Not generalised.* `plot_for_vlm` places its region labels as data
  annotations, which matplotlib already hides outside the view, and it is
  drawn to a path rather than zoomed. The `fig.savefig` default keeps
  `savefig.bbox: "tight"`, which a long phase name still needs.

  Next: nothing in this WP. The pin's platform scope stays darwin/arm64, so
  the next matplotlib bump skips it again until someone re-captures it.

- **2026-10-14** — filed from WP-1970's handover. No open WP owns the
  returned figure: WP-1075, which set the gutter convention, is closed.
  The two findings share one seam, the figure a plot hands back, so they are
  one WP.

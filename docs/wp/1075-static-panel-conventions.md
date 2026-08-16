# WP-1075 — The static panel takes the house figure conventions

Milestone: v1.0 · Status: ✅ 2026-08-16 — layout, palette, axes and scales; the
raw difference is the default and the rows moved below it
Depends on: — (touches the frozen surface, so before [1003](1003-api-freeze-pypi.md))

## Goal

`result.plot()` produces a figure that can go into a report unedited: the house
conventions applied to the panel's *layout* rather than only its colours, the
classic `obs − calc` difference back as the default with the reflection rows
below it, and the axes a diffractionist actually asks for — Q and d-spacing on
x, a root or log intensity on y.

## Context

The renderer is `plot_result` in `src/rietx/viz/plots.py`, reached as
`RefinementResult.plot()` (`schemas/results.py`). Its sibling renderers are
`plot_for_vlm` in the same file (drawn for a vision model — exempt by design
and now said so in the module docstring) and the plotly viewer in
`viz/html.py`, which `write_html`, the CLI export, the GUI's export route and
`viz/live.py` all reach.

Two things decide this WP and neither is in the code:

- **The house figure conventions**, as the user states them: colour by role and
  never by series index; every label in the right-hand gutter rather than in a
  legend; the caption is the title, so no chart title; four to six ticks per
  axis; ink justified by the work it does; type sized from the *exposure
  surface* rather than scaled in the document afterwards; and, for a
  diffraction panel specifically, observed as markers, the difference on the
  data's own axis at the data's own scale, one tick row per phase below it,
  rows spaced by type and not by eye.
- **Only rendering tells you the truth.** Collisions, escaping data, a label
  in dead space: none of it appears in the code and all of it appears in the
  image. Every layout decision here was checked by looking at a render — of
  the 11-BM NAC fit, at the default size, at 3.3 in, with four phases, and
  with no tick rows at all.

Three constraints the panel already had, and kept:

- `RefinementResult` carries no wavelength, so λ is a **parameter**, not a
  lookup. Reading it off `AbsorptionCorrection` would make the axis label
  depend on whether an unrelated correction ran.
- The renderer draws under a `plt.style.context`, never a global rcParams
  update, so a caller's own settings come back when the call returns.
- `style="dark"` exists because the subordinate roles — residual, background
  line, zero rule — have to be chosen *per ground*; a bare `dark_background`
  context would flip the axes and leave all three at their light-ground hues.

## Non-goals

- `plot_for_vlm`. It is drawn for a vision model: high contrast, annotated
  redundancy, per-panel titles carrying exact numbers, one fixed ground. Every
  rule here would make it worse.
- `plot_trajectory`. The style file has a *Refined parameters vs. condition*
  section and the function does not follow it yet (per-panel titles, two font
  sizes). A separate pass.
- The manual's hand-drawn figures in `docs/manual/make_figures.py`. They
  inherit the palette; their type and layout are their own.
- The GUI's live plot. It is a Svelte canvas with its own rulebook
  (`gui/CLAUDE.md`), and an interactive figure is a different medium — its
  legend is a control, not a colour key.

## Tasks

- [x] Layout and palette: role colours, gutter labels, lens tick marks, row
      spacing solved from the type size, statistics as a corner annotation,
      the left spine spanning the data rather than the last tick, `style=`,
      `wavelength=`, `figsize=`, `font_size=`; `two_theta_range` becomes a
      *window* (the scale and the rows come from what it contains).
- [x] `viz/html.py` quotes the role colours from `PALETTES` instead of its own
      hexes, so the PNG and the interactive page are two pictures of one fit.
- [x] Reading order fixed to data → residual → rows in **both** layouts: the
      rows follow the residual into the lower panel when there is one, in the
      matplotlib panel and in plotly.
- [x] The seam goes. Two panels are separated with the interior spine hidden,
      not butted with ticks on both sides.
- [x] `obs − calc` is the default difference again (`weighted=True` opts into
      Δ/σ), in `plot_result` and in `write_html`; `viz/live.py` keeps Δ/σ by
      passing `sigma` explicitly.
- [x] `label_align="bottom"` (default) puts the curve names in one block
      bottom-aligned with the data; `"curve"` keeps the old per-curve levels.
- [x] `x_axis="q"`/`"d"`, both derived through `wavelength=`; a *d* axis is
      drawn ascending, and the tick rows make the same trip as the curves.
- [x] `y_scale="sqrt"/"log"/"asinh"`, with the whole layout re-solved in the
      axis's transformed space; a nonlinear intensity axis moves the raw
      difference into its own linear panel.
- [x] A shared power of ten in the y *label* rather than a floating offset
      text, and small crosses for the observed points.
- [x] `dpi` 150 → 300 for `plot_result`, 110 → 200 for the manual's `_save`.
- [x] Tests + rendered PNGs to `tests/output/`; manual figures regenerated;
      `quickstart.md` rewritten for the new layout and keywords.

## What is deliberately asymmetric

- **`weighted=False` in the two file writers, Δ/σ in the live view.** A file
  someone takes away is read as a figure; a stage-by-stage live view is asking
  "is the model right yet" of the same numbers, which is what Δ/σ answers.
  `viz/live.py` already chose explicitly, so only the defaults moved.
- **The plotly figure keeps its legend and its own layout.** In an interactive
  figure a legend is a control — click a name to hide its trace — not a colour
  key the eye has to look up. Only the colours and the reading order are shared.
- **The panel breaks one house rule and says so in its docstring**: with
  `weighted=True` the difference takes a second axis. The rule exists to stop a
  second y scale inviting a silent rescale and to keep a featureless line
  running across the figure; Δ/σ is not the intensity in the intensity's units,
  its axis is labelled, and the panels are now separated rather than joined by
  a line.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_events_viz_history.py
.venv/bin/python -m pytest tests/test_manual.py tests/test_manual_api.py \
    tests/test_examples.py tests/test_docs_consistency.py
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m pytest -n auto --dist loadgroup   # the acceptance suites
.venv/bin/python -m ruff check src tests examples docs
.venv/bin/python docs/manual/make_figures.py     # and look at the PNGs
```

The measurable criterion is not a number: it is that every mode renders
without a collision, without data escaping the axes, and without a label in
dead space, on the 11-BM NAC fit at the default size, at 3.3 in / 8 pt, with
four phases, and with no tick rows.

## References

- The house figure conventions (`yue-figure-style`), which merge
  `FIGURE_STYLE.md` with Tufte, *The Visual Display of Quantitative
  Information* (1983/2001), *Envisioning Information* (1990) and *Visual
  Explanations* (1997).
- Toby, B. H. (2024), *J. Appl. Cryst.* **57**, 175 — Δ/σ has expectation 1
  under a correct model, which is what puts the weighted difference on an
  absolute scale.
- Data: `tests/data/11BM_NAC.fxye` (APS 11-BM, λ = 0.4139090 Å), through
  `examples/nac_11bm.py`.

## Handover log

- **2026-08-16** — closed. Landed in one session, in two passes: the house
  conventions first (layout, palette, gutter, rows, window, `style`/
  `wavelength`/`figsize`/`font_size`), then the corrections the user made on
  reading the result — seam out, residual above the rows, bottom-aligned label
  block, `obs − calc` default, higher dpi, scientific notation, crosses — plus
  the Q/d and nonlinear-y axes.

  **Done.** `plot_result` rewritten; `viz/html.py` quotes `PALETTES` and moved
  its rows below the residual; both file writers default to the raw
  difference; 10 manual figures regenerated at 200 dpi; `quickstart.md`
  rewritten; WP-1003's `### Inherited` carries the new public surface.

  **Measured** (main checkout `.venv`, `[dev]`, darwin/arm64):
  `tests/test_events_viz_history.py` 15 → **19 passed**, 4 new tests, all
  passes. Fast selection **2401 passed, 117 skipped** — +4 against the 2397 the
  first pass measured, exactly the four new tests, no new skip. Wall clock
  4–7 min, and quote it as a range rather than a figure: this session measured
  169 s, 236 s, 249 s and 369 s on the same machine hours apart. Full suite,
  once on the final tree: **2509 passed, 126 skipped**, 28:44, exit 0 — +4 on
  the 2505 the first pass measured, the same four, so nothing the acceptance
  suites fit moved. It was worth running for a rendering-only change because
  those suites are the only place `plot_result` meets *real* results, and a
  layout that divides by a span can only fail on data the synthetic fixture
  does not have. Ruff clean on `src tests examples docs`; the manual builds
  `-W` clean (`test_manual.py`), and its 10 committed figure pairs were
  regenerated.

  **Gotchas.** The first two were found only by rendering and looking; the
  rest came out of writing the guards, which is the other half of the same
  lesson — a layout claim you cannot state as an assertion is usually a layout
  claim you have not finished thinking about.
  1. `set_ylabel(..., va="center")` **moves a rotated label sideways**, not
     vertically: `ha` is what centres it along the axis. With `va="center"` the
     label ate its own `labelpad` and touched the tick numbers. `y=` alone,
     with the default alignment, is the fix.
  2. matplotlib's offset text (`×10⁵`) floats above the axes a whole headroom
     away from the numbers it multiplies. The multiplier is in the y *label*
     instead, and an additive offset is refused outright — it moves the origin
     without saying so.
  3. A `LogLocator` will label a tick a full decade above the tallest peak,
     where the spine has already stopped — and so will `AsinhLocator`'s minor
     ticks. Both are now set explicitly, inside `[base, top]`. **The fix has
     its own failure**: a pattern living inside one decade has no decade to
     label, so asking for the ones inside its range returns *none*, and the log
     axis comes back with no numbers on it at all. That case falls through to
     rounded values and a plain formatter, and it is the second guard that was
     made to fail on purpose before being trusted.
  4. The plotly raw layout put its tick rows at a fixed fraction of the
     *intensity* span, so a noisy residual on a weak pattern reached below them
     and the rows landed inside the difference. They now sit under the drawn
     difference, as the matplotlib panel's always did. This was a pre-existing
     defect the new ordering test surfaced.
  5. The regression guard that earns its keep is
     `test_the_residual_sits_between_the_data_and_the_tick_rows`: it was made
     to fail on purpose against a one-line revert (rows drawn on the intensity
     axes in panel mode) before being trusted. Asserting the drawn y values
     alone would have passed with the rows in the wrong *axes*, so it asserts
     which axes holds how many lines as well.
  6. The headroom assertion had to be rewritten before it meant anything. Its
     first form bounded the axis ceiling as a multiple of the tallest peak,
     which is a statement about counts and therefore false on a log axis by
     construction. What the layout actually promises is a fixed share of the
     panel's *height* — 1/6 on every scale — and asserting that is what makes
     "the layout is arithmetic in display distance" a checked claim rather
     than a comment.

  **Next.** `plot_trajectory` is the one renderer left that does not follow the
  conventions — per-panel titles and two font sizes against a section of the
  style file written for exactly that figure. Not started, and not blocking
  1003.

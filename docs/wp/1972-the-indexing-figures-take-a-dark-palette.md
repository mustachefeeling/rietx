# WP-1972 — the indexing figures take a dark palette

Milestone: unscheduled · Status: ✅ 2026-10-15 — the four indexing figures take `style=` and carry a
notebook dark copy; a light figure drawing a colour outside the palette fails a test
Track: Render what the fit already knows
Depends on: —

## Goal

The four indexing figures have a dark form, as the pattern, fit, series and
structure figures do since WP-1970. In a notebook each one follows the
frontend's theme.

## Context

**Today.** `viz/indexing.py` draws `plot_peak_list`, `plot_candidates`,
`plot_validation` and `plot_indexing` on rietx's notebook figure class, so
each is encoded for a notebook. None takes `style=`. Each returns through
`indexing._handed_back(fig)`, which passes no style, so
`viz.plots._notebook_bundle` emits the PNG alone. The colours are module
constants (`OBS`, `CALC`, `BKG`, `DIFF`, `ABSENT`, `UNMATCHED`) and eight
`CANDIDATE_COLORS`, all chosen for a white page.

**What WP-1970 built that this reuses.** A light figure recoloured by
`viz.plots._darkened` matches the figure drawn dark in every pixel, provided
each light colour maps to one dark colour (`PALETTES`, tested by
`test_the_light_palette_maps_onto_the_dark_one`). So the work is the dark
values, a `style=` on each function, and the style passed to
`_handed_back`. The notebook pair then follows. The candidate colours are a
categorical set, like `PHASE_COLOURS`, and may keep one value for both
grounds if each reads on both. `tests/test_gui_palette.py` measures that.

**A consequence for the Lite site.** `docs/lite/build.py` `settings()`
keeps the site light while any stored figure lacks the pair. A tutorial
that stores an indexing figure would hold the whole site light until this
WP lands. No tutorial stores one today.

## Tasks

- [x] Dark values for the indexing roles, checked against the dark ground
  for contrast, and the candidate set checked on both grounds.
- [x] `style=` on the four functions, passed to `_handed_back`.
- [x] The pixel test of `tests/test_viz.py` extended to the four figures.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_viz.py tests/test_indexing_plots.py tests/test_gui_palette.py
```

## Handover log

- **2026-10-15** — closed. Every rietx figure now has a dark form. In a
  dark notebook an indexing figure shows dark, where before it showed as a
  white rectangle. The light figures look as they did. A new test also
  closes the gap that hid these figures: a light figure that draws a colour
  outside the palette now fails, where the pixel test passed it. The cost is
  a small break, recorded in the staged notes. Six colour constants left
  `rietx.viz.indexing`, and their values are now palette roles.

  *Done.* The indexing colours are roles in `viz.plots.PALETTES`:
  `index_obs`, `index_calc`, `index_bkg`, `index_diff`, `absent`,
  `unmatched` and the ranked list `candidate`. This follows WP-1970's
  trajectory roles. `_darkened` maps a list role entry by entry. The four
  functions take `style=`, draw under `_ground_context` (renamed from
  `_trajectory_context`, which the trajectory shares) and pass the style to
  `_handed_back`. A figure that `plot_indexing` composes records its style
  too, so the inline backend's draw at the cell's end carries the pair.
  `plots._palette` is now the one style check, from the review.
  `CANDIDATE_COLORS` stays as the light tuple. The zero line moved from
  `#cccccc` to the palette's `zero`, `#c9c9c9`. That is 3 grey levels, and
  the new guard needs it.

  *Measured.* A light hue the palette already held keeps that role's dark
  colour: `#1f5fa8`, `#c23b22` and `#2a9d2a` take the `series`, `reseeded`
  and `band` dark values. Each new hue keeps its OKLab hue and gains 0.19 in
  lightness, the mean lift of those three pairs. The derivation script is
  not committed, and the values are literals. Distances from the figure
  ground (OKLab, floor 0.13): the weakest light colour is `absent` at 0.218
  and the weakest candidate rank 5 at 0.369. On dark the weakest is
  `index_bkg` at 0.42. The closest candidate pair is ranks 1 and 8, at 0.064
  on light and 0.080 on dark. The fast selection, `[dev]` venv, macOS arm64,
  CPython 3.12, main unmoved since dcbafa94, with another session's pytest
  running: 9744 passed, 187 skipped, 1 xfailed. That is 9931 against
  WP-1970's 9913, so +18, the cases this session added: 5 drawings joining
  the pixel test, 10 cases of the ink guard, 2 contrast cases and 1
  composition test. No skip moved. The run after the review showed 1
  failure, the WP index, stale because the Status line changed mid-run; it
  passed regenerated. `added_test_times`: 4.8 s over the three new
  functions, the ink guard dearest at 2.5 s over 10 cases. None joins the
  slow tail. The full selection did not run, because no refined number can
  move.

  *Review.* `/code-review high --fix` found nine problems and fixed five.
  The fixes: `plot_indexing(path=)` now saves under its style, the staged
  notes record the removed constants, the `PALETTES` note says which dark
  hues are reused, one style check replaces three copies, and two long lines
  are rewrapped. Declined: the close candidate pair (it predates this work,
  and the light colours stay); dark copies of `plot_result` now also map the
  indexing hues a caller might draw (the copy maps every palette colour, by
  design); the zero-line grey (above); the hand-written role list in
  `test_gui_palette.py` (a new role still meets the ink guard, which fails
  first).

  *Gotchas.* The pixel test cannot see a colour outside the palette. The
  copy leaves it as drawn, and the dark figure draws it too. That is why
  `test_every_ink_a_light_figure_draws_has_a_dark_form` exists. A marker-only
  line carries matplotlib's default `#1f77b4` as an unused line colour, so
  the guard skips a `linestyle="None"` line's line colour.

  Next: nothing in this WP. Two things are left open, neither filed. If
  someone wants the candidate rows separable past rank 7, rank 8's hue is the
  one to move. That changes the light figure, so it is a figure-style call
  for the maintainer.

- **2026-10-14** — filed from WP-1970's handover, where the code review
  found that the indexing figures get no dark copy. No open WP owns the
  indexing figures, so this is new. It is separate from WP-1971, which is
  about the returned figure's geometry and pickling, not its palette.

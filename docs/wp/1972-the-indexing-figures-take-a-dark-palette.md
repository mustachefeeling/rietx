# WP-1972 — the indexing figures take a dark palette

Milestone: unscheduled · Status: 🔄 2026-10-15 — claimed by @yue-here
Track: Render what the fit already knows
Depends on: —
Priority: P3 2026-10-14 — no workaround: an indexing figure has no `style=`, so in a dark notebook it is a white rectangle

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

- [ ] Dark values for the indexing roles, checked against the dark ground
  for contrast, and the candidate set checked on both grounds.
- [ ] `style=` on the four functions, passed to `_handed_back`.
- [ ] The pixel test of `tests/test_viz.py` extended to the four figures.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_viz.py tests/test_indexing_plots.py tests/test_gui_palette.py
```

## Handover log

- **2026-10-14** — filed from WP-1970's handover, where the code review
  found that the indexing figures get no dark copy. No open WP owns the
  indexing figures, so this is new. It is separate from WP-1971, which is
  about the returned figure's geometry and pickling, not its palette.

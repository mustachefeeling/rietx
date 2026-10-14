# WP-1967 — a notebook figure follows the frontend's theme

Milestone: unscheduled · Status: ⬜
Track: Render what the fit already knows
Depends on: —
Priority: P3 2026-10-14 — a workaround covers it: every pattern figure takes `style="dark"` and `render_structure` a dark `background=`; the series figure has no dark form

## Goal

In a notebook, every rietx figure shows in the frontend's light or dark
theme. It follows a theme switch without the cell being run again. Where the
frontend cannot switch, the reader sees the light figure, as today.

## Context

**Today.** `PatternData.plot` and `RefinementResult.plot` draw through
`viz.plots.plot_pattern` and `plot_result`. Both take `style="light"` or
`"dark"` (`PALETTES`, `_style_context`). `SeriesResult.plot` reaches
`plot_trajectory`, which takes no `style`. `rx.viz.render_structure` picks
its dark tokens when `background=` is dark (`viz/figure3d/render.py`, at
`tokens = TOKENS[...]`). A notebook shows a rietx figure through
`_notebook_png`, an IPython `image/png` formatter registered for
`_NotebookFigure` alone (`viz/plots.py`, `_figure_class`). The HTML reprs in
`_display.py` set no colours, so they already follow the theme.

The JupyterLite site (WP-1966) is pinned to JupyterLab Light by `SETTINGS`
in `docs/lite/build.py`, because every figure is drawn on white. The manual
renders the committed tutorial notebooks with myst-nb under furo, which has
a dark theme.

**The design.** The formatter emits a `text/html` output beside the
`image/png`. It holds two `<img>` elements, light and dark. The dark one
carries an inline `style="display:none"`. A `<style>` block swaps the two
when the frontend's marker says dark. Inline styles survived every sanitizer
measured and `<style>` did not, so where the swap is stripped the reader
sees the light figure. The images also carry furo's `only-light` and
`only-dark` classes, which switch the manual's pages with no `<style>` at
all. The swap's own classes take an `rx-` prefix, because in a Sphinx page a
`<style>` applies to the whole page.

**The frontends**, read from their source on 2026-10-14. Colab and VS Code
were not run live.

| frontend | dark marker | `<style>` in an output | what the reader would see |
|---|---|---|---|
| JupyterLab 4, Notebook 7, JupyterLite | `body[data-jp-theme-light="false"]` | kept when the cell ran in this session; stripped when the notebook opened with its outputs (untrusted) | a live swap; the light figure |
| VS Code | `body.vscode-dark`, `body.vscode-high-contrast` | kept | a live swap; Restricted Mode renders no HTML (a blank output is expected, unverified) |
| Colab | `html[theme=dark]` (a Colab maintainer, 2020, `googlecolab/colabtools#1214`; unverified since) | kept when run | a live swap, if the marker still holds |
| GitHub's notebook viewer | its iframe sets the Lab marker | stripped; inline `style` and `class` kept (observed) | the light figure |
| myst-nb under furo | `body[data-theme="dark"]`, and `"auto"` under the media query | kept, raw in the page | the `only-*` classes swap it |

Sources: JupyterLab `packages/apputils-extension/src/themesplugins.ts`,
`packages/apputils/src/sanitizer.ts` (the tag and property allowlists),
`packages/rendermime/src/factories.ts` (rank order); VS Code
`extensions/notebook-renderers/src/index.ts`; nbconvert
`exporters/html.py`; myst-nb `core/render.py`; furo
`assets/styles/base/_theme.sass`. `text/html` outranks `image/png` in every
one of them, so the PNG is the fallback only for an output with no HTML
renderer, such as a PDF export. `prefers-color-scheme` follows the OS in Lab
and in VS Code. The editor theme does not move it, so it is a poor marker.

**Prior art.** scikit-learn's estimator repr reads the same markers in a
script (`sklearn/utils/_repr_html/estimator.js`), and a script runs only in a
trusted output. xarray's repr falls back through the `--vscode-*`, `--jp-*`
and `--pst-*` CSS variables. That works for text and fails for a raster.
JupyterLab's Vega renderer reads `data-jp-theme-light` once, at render, and
does not redraw on a switch. matplotlib-inline's `needs_background` metadata
puts a contrasting backdrop behind a transparent PNG, in Lab only.

**Costs**, measured on tutorial 01's `data.plot()` (`[dev]` venv, macOS
arm64, warm). Drawing takes about 15 ms in either palette. `_notebook_png`'s
encode takes 220-240 ms. So a second palette costs about 0.25 s a figure
natively, and more in the browser. The dark PNG is 27 kB against the light
one's 26 kB. The six committed notebooks hold 12 PNGs, 676 kB of base64 in
829 kB of files, so a pair per figure adds about 680 kB.

**The open question** is how the dark copy is made. It can be drawn again,
or recoloured. Drawing again needs the call's arguments held on the figure,
and it loses whatever the caller changed on the returned figure, such as
`ax.set_xlim` or an annotation. Recolouring maps each light role colour in
`PALETTES` to its dark one on a copy, and keeps the caller's changes. It
needs the light role colours to be distinct, or to map to one dark colour:
`obs` and `tick` share `#1a1a1a` today and both become `#d2c9bd`.

## Non-goals

- One transparent figure for both grounds. Type and spines cannot take one
  colour that reads on both.
- Detecting the theme in the kernel. A kernel cannot see the frontend.
- Figures a caller draws with matplotlib directly. The formatter is
  registered for rietx's own figure class only.

## Tasks

- [ ] `plot_trajectory` takes `style=`, so every figure call has both palettes.
- [ ] Redraw or recolour, decided on one figure, with a caller's
  `ax.set_xlim` as the case that separates them.
- [ ] The notebook formatter emits the pair as `text/html` beside the light
  `image/png`, keeping the width-only metadata of WP-1957.
- [ ] `render_structure`'s notebook output emits the same pair.
- [ ] A browser check: JupyterLab or the Lite site switched from Light to
  Dark swaps the figure without a rerun, and the same notebook opened
  untrusted shows one light figure.
- [ ] The tutorial notebooks rebuilt. The manual's tutorial pages checked
  in furo's dark theme. GitHub's render checked to show one figure.
- [ ] The Lite site's light pin lifted (`SETTINGS` in `docs/lite/build.py`),
  with the README sentence that explains it.
- [ ] Tests: the bundle's shape, the inline fallback on the dark image, the
  prefixed classes.
- [ ] Skill: none. An agent reads a figure as a PNG file or through
  `plot_for_vlm`.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_viz.py tests/test_tutorials.py
.venv/bin/python -m ruff check src tests examples
```

The browser check above passes in JupyterLab, and the manual's tutorial
pages show dark figures under furo's dark theme.

## References

- JupyterLab sanitizer allowlist: `packages/apputils/src/sanitizer.ts`.
- furo light/dark images: the `only-light` and `only-dark` classes.

## Handover log

- **2026-10-14** — created from a maintainer question in WP-1966's fourth
  session: can the notebook figures follow a dark theme? No open WP owns
  notebook figure theming. The index has no open row on it, and WP-1966
  fenced a dark theme out as a non-goal. The frontend table comes from a
  source-reading pass that day.

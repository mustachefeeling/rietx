# WP-1970 — a notebook figure follows the frontend's theme

Milestone: unscheduled · Status: ✅ 2026-10-14 — a pattern, fit, series or structure figure in a notebook
carries a dark copy the frontend's theme picks; the indexing figures are WP-1972
Track: Render what the fit already knows
Depends on: —

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

**The dark copy is recoloured, not drawn again** (decided 2026-10-14). The
formatter deep-copies the light figure and maps each light ink to its dark
one. A `PALETTES` role maps to the same role in dark. Matplotlib's own
black maps by the artist's kind: text to `fg`, and spines, ticks and other
lines to `rule`. White maps to `ground`, as `_ground_rc` paints it. The map
must be a function, so two roles sharing a light colour must share a dark
one: `obs` and `tick` share `#1a1a1a`, and both become `#d2c9bd`.

It was measured on tutorial 01's FAP Le Bail fit, three figures:
`best.plot()`, `data.plot()`, and `data.plot(model=ref,
two_theta_range=(25, 35))`. At 200 dpi the recoloured copy matched the
figure drawn with `style="dark"` in every pixel, 0 differing of about
1.2 million in each. The copy costs 21-23 ms and the recolour 2-8 ms. A
redraw costs 20-92 ms. Both are small beside the 220-240 ms encode.

The caller's case separates the two. An annotation added to the returned
figure stays in the recoloured copy, and its text turns from black to `fg`.
A redraw drops it. The probe's first recolour missed the annotation's arrow,
which a walk over `findobj()` does not reach, so the arrow is mapped
separately. Neither route fixes a caller's `ax.set_xlim(30, 34)`. The light
figure then encodes at 30 076 × 871 px, because the gutter labels sit in data
coordinates beyond the new limits and `bbox_inches="tight"` reaches them.
That issue predates this WP. Recolouring shows the same figure in both
themes, and a redraw would show a different one.

A CSS `filter: invert(1) hue-rotate(180deg)` on the one light image would
cost no second image. Its output is a fixed function of each pixel, so the
ground becomes `#000000` rather than the page's `#1d1813`, and the roles
cannot reach the dark palette's hand-tuned values.

## Non-goals

- One transparent figure for both grounds. Type and spines cannot take one
  colour that reads on both.
- Detecting the theme in the kernel. A kernel cannot see the frontend.
- Figures a caller draws with matplotlib directly. The formatter is
  registered for rietx's own figure class only.

## Tasks

- [x] `plot_trajectory` takes `style=`, so every figure call has both palettes.
- [x] Redraw or recolour, decided on one figure, with a caller's
  `ax.set_xlim` as the case that separates them. Recolour (Context).
- [x] The notebook formatter emits the pair as `text/html` beside the light
  `image/png`, keeping the width-only metadata of WP-1957.
- [x] `render_structure`'s notebook output emits the same pair. Drawn again
  from the recipe, on a copy of the structure taken at the call.
- [x] A browser check: JupyterLab or the Lite site switched from Light to
  Dark swaps the figure without a rerun, and the same notebook opened
  untrusted shows one light figure.
- [x] The tutorial notebooks rebuilt. The manual's tutorial pages checked
  in furo's dark theme. GitHub's render checked to show one figure.
- [x] The Lite site's light pin lifted (`SETTINGS` in `docs/lite/build.py`),
  with the README sentence that explains it. Now `settings()`: the site
  follows the reader once the newest tag's figures all carry the pair, and
  the build marks the outputs trusted.
- [x] Tests: the bundle's shape, the inline fallback on the dark image, the
  prefixed classes.
- [x] Skill: none. An agent reads a figure as a PNG file or through
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

### 2026-10-14 (2nd session) — the figures follow the theme, and the WP closes

A pattern, fit, series or structure figure in a notebook now shows in the
reader's light or dark theme, and switches when the theme does, with no cell
run again. Where a frontend cannot switch, the reader sees the light figure
as before. The dark image is the light figure recoloured, so a note a caller
adds to the figure shows in both. A redraw would have dropped it. The cost is
about twice the encode time per figure shown, and about three times the image
bytes in a saved notebook. Every task is done and the WP closes. The indexing
figures have no dark form yet, which is WP-1972. Two older defects of the
returned figure, which this work found, are WP-1971.

*Renumbered.* This WP was filed as WP-1967 in WP-1966's PR. Main took 1967 to
1969 for issues the same day, so it is WP-1970. Commit e0fa96dc carries the
old prefix.

*Done.* `plot_trajectory` takes `style=`. Its five mark colours became
`PALETTES` roles, and the light figure is byte-identical to before. The
notebook output is `_repr_mimebundle_` (`viz.plots._notebook_bundle`): the
light PNG, and for a figure drawn light an HTML pair from `_pair_html`. One
light encode serves both. A PNG formatter returning `None` is registered for
the figure class, which stops the inline backend's `Figure` formatter
re-encoding over the bundle's PNG. `_darkened` recolours a deep copy: a
role to its dark role, matplotlib's black to `fg` on text and `rule` on
lines, and white to `ground`. It reaches an annotation's arrow, which
`findobj()` misses. A failure in the dark copy warns and leaves the PNG.
`StructureFigure` keeps a deep copy of its first argument, taken at the
call, and redraws from `recipe` on the dark ground. A raster's antialiased
edges cannot be recoloured. Any ground but the default white shows alone.
The tutorials are rebuilt. The Lite build marks every code cell trusted and
picks its theme with `settings()`. The manual's exports chapter and the
series chapter say what a reader sees, and the 1.10 notes stage it.

*Measured.* All on macOS arm64. Probes ran in the `[dev]` venv, the browser
checks in a scratch venv with this tree installed.
- Recolour against a `style="dark"` drawing, tutorial 01's FAP Le Bail fit
  at 200 dpi: 0 differing pixels of about 1.2 million on `best.plot()`,
  `data.plot()` and `data.plot(model=ref, two_theta_range=(25, 35))`. The
  committed test adds a weighted panel, a sqrt axis with two phase rows, and
  the trajectory, all exact at 100 dpi. The copy took 21-23 ms, the
  recolour 2-8 ms, a redraw 20-92 ms.
- One figure's display: PNG alone 244-484 ms, the whole bundle 539-933 ms
  (FAP `data.plot()`, no other suite running). Before the shared encode the
  bundle took 980-1584 ms.
- A structure figure: dark redraw 44-47 ms, snapshot 0.4-2.4 ms, encode
  88-145 ms (fluorapatite, 1000 px).
- Tutorials: 828 505 → 2 195 188 bytes over six notebooks. All 12 figure
  PNGs are byte-identical, and all 12 carry the pair.
- JupyterLab 4.6.4, Chromium: a figure run in the session swaps light, dark,
  light with no rerun. The same figure opened from a saved notebook has no
  `<style>` left and shows the light image in both themes.
- GitHub's viewer, branch blob of tutorial 01: three outputs, the light
  image shown and the dark hidden in each, under both colour schemes.
- The built manual under furo, tutorials 01, 02 and 05: one image per pair,
  the right one, under the OS scheme and under an explicit choice.
- JupyterLite 0.8.6, a minimal site: a stored output keeps 0 `<style>`
  untrusted and 1 with `metadata.trusted`. Trusted, under `adaptive-theme`,
  the stored figure follows the OS scheme in both the Notebook and Lab views.
- Tests: `tests/test_viz.py`, `test_display.py`, `test_sequential.py`,
  `test_lite.py` and the acceptance pair all pass. The fast-suite count is
  below.

*Review* (`/code-review high --fix` over this WP's range). It found a real
bug. A deep copy of a figure pyplot still holds registered the copy with
pyplot, so each display under any backend but inline left a stray figure or
opened a window. The copy is now made with the canvas manager detached, and
a test that went red without the fix pins it. A display that drops
`text/html` no longer draws the dark copy. The manual's frontend sentence
now separates the frontends seen switching from those read from source. A
`.jupyterlite.doit.db` cache, written to the tree root by this session's
JupyterLite probe and committed, is removed and ignored. The indexing
figures had no dark form, against a status that claimed every figure; the
claims are narrowed and WP-1972 owns them. Declined: copying the structure
lazily, which would let a later edit split the two pictures, and caching the
structure's dark raster, which would hold a second image on every figure.

*Gotchas.* JupyterLite applies a settings override only from inside the
lite-dir. A path outside it builds with `overrides.json: 0` and no error. The
build already writes it there. The figure's warm dark ground, `#1d1813`,
shows as a slightly lighter card on JupyterLab Dark's near-black. It matches
the manual and the landing page.

*Not generalised.* A caller's `set_xlim` makes a 30 076 px wide notebook
image, and a rietx figure cannot be pickled. Both predate this WP and are
WP-1971. VS Code and Colab were read from source, not run. VS Code's
Restricted Mode is still unverified.

*Next.* Nothing remains in this WP. WP-1972 first, if a tutorial is to
store an indexing figure, because one such figure holds the Lite site light.
WP-1971 when a zoomed or pickled figure matters. At the next cut, check that the Lite site has switched to
`adaptive-theme`: it follows the reader once the newest tag's notebooks
carry the pair.

### 2026-10-14 — filed

Created from a maintainer question in WP-1966's fourth session: can the
notebook figures follow a dark theme? No open WP owns notebook figure
theming. The index has no open row on it, and WP-1966 fenced a dark theme
out as a non-goal. The frontend table comes from a source-reading pass that
day.

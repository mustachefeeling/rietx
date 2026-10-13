# WP-1957 — a fit seen in Colab: figures at their own shape, a picture as it runs, the structure beside it

Milestone: unscheduled · Status: ⬜
Track: Render what the fit already knows
Depends on: —
Priority: P2 2026-10-13 — a defect with a named user: the Colab quickstart (1917) is live, every figure in it draws distorted, and the maintainer asked

## Goal

A notebook opened from the landing page's Colab links shows every rietx figure
at its designed aspect ratio. A fit can draw itself while it runs, in the cell
that started it, with nothing installed beyond rietx and no JavaScript. Notebook
02 shows the fit right after the first refinement, and shows the refined
structure as a picture.

## Context

Four asks from the maintainer (2026-10-13), each answered below with what the
tree already holds.

**1. Figures stretch in Colab.** Every figure shown in a notebook goes through
`viz.plots._notebook_png` (WP-1544), which returns the PNG with metadata
`{"width": w, "height": h}` in CSS pixels. Both keys reach the frontend as
`<img width=… height=…>`. JupyterLab's stylesheet carries
`max-width: 100%; height: auto`, so a narrow output shrinks the image and keeps
its shape. **Hypothesis, unmeasured:** Colab clamps the width to the output
column and keeps the declared height, so any column narrower than the figure
squashes it. Our figures are about 690 CSS px wide (the committed `.ipynb`
outputs read `{'height': 435, 'width': 672…693}`), which is wider than Colab's
column on a laptop with the file browser open.
The fix is to declare the **width alone**: one dimension cannot disagree with
itself, and every frontend derives the height from the pixels. HiDPI sharpness
survives, because the 2× density is set by the width. `tests/test_display.py:243`
pins both keys and changes with the fix.
`StructureFigure._repr_png_` (`viz/figure3d/render.py`) declares no size at
all, so it draws at the raster's own pixel size. Hold it to the same rule:
width in CSS px, no height.
Only the maintainer can measure Colab. The task names the check.

**2. A live fit in the cell. The design exists, and it needs no widget.**
The stage loop already hands a picture to any object passed as `events=` that
has a `write_snapshot(model, table, outcome, stage_name)` method
(`refine._snapshot_sinks`, duck-typed so `viz/live.py` needs no import from
`refine`). `viz/snapshot.build_snapshot` builds the payload from the stage's
frozen model: `two_theta`, `y_obs`, `y_calc`, `y_bkg`, `delta`, `ticks` and
`statistics`. Each value is read, never recomputed, and `y_calc` is the fit's
own `model.evaluate`. `history/events.progress_writer` already formats a status
line from `stage_end` events without computing anything.
So a notebook live view is an `EventStream` with a `write_snapshot`. At each
stage it draws the payload with the plotting code `plot_result` uses and
replaces one output in place, through `IPython.display.display(…, display_id=True)`
and then `handle.update(fig)`. Between stages it updates a text line from
`eval` events: the stage, `n_eval` and the cost, **throttled by time and never
by count** (root CLAUDE.md, WP-1413).
This is the best-practice tier for a live view, for four reasons:
- `update_display_data` is part of the core Jupyter message protocol. It works
  in JupyterLab, classic Notebook, VS Code and Colab with no comm, no frontend
  extension, no trust step and no new dependency.
- The fit runs on the kernel's main thread, and iopub messages go out while the
  cell is still running, so the frames arrive during the fit. No thread is
  needed.
- `nbclient` folds updates into the output with the same `display_id`. An
  executed and committed notebook therefore stores **one** final frame, not one
  per stage. This is unmeasured; the tests task checks it.
- A frame is a PNG through `_notebook_png`, so the fix for ask 1 covers it too.

The tier above it is an interactive, per-iteration chart: `anywidget` carrying
the `rxplot.mjs` module that `rietx watch` already uses. It costs a dependency.
Colab needs `google.colab.output.enable_custom_widget_manager()` and a CDN
fetch. A committed notebook would hold a dead widget, and the comm channel is
exactly what the fence below covers. **It is not in this WP.**

**The fence.** `DESIGN.md` § Locked decisions says "Notebook widgets stay
fenced", and WP-1544's non-goals read that fence as covering "a live fit view".
The first task is a dated amendment that narrows the fence rather than lifting
it:
- **In:** an output that replaces itself, carrying a static PNG and text, with
  no comm, no JavaScript and no dependency.
- **Still fenced:** ipywidgets, anywidget, or any comm-backed or JavaScript
  output.
The maintainer takes the decision. The WP stops at task 1 if they refuse it.

**Its cost, and whose it is.** Drawing a frame costs one matplotlib figure per
stage, unmeasured and probably 100–300 ms. WP-1413 judges a per-stage charge
on the shortest fit, `nac` at 0.354 s. This view is opt-in, so the caller pays
by choosing it, and nothing pays when it is off. Measure it anyway and record
it in the handover. If the charge has to shrink, thin by time (at most one
frame per interval, and always the last), never by count.

**A public name.** `rx.viz.live_view()` (working name) is a new public call,
so `tests/api_surface.py`'s partition fails until Part 1 documents it. Document
it in the notebook chapter that WP-1544 and 1545 wrote, and add a `help.py`
entry only if it takes options that need one. The name should not collide with
`viz.live.LiveSession`, which writes a directory for `rietx watch`. One
sentence in the docstring tells them apart: this one draws **here**, and that
one draws **elsewhere**.

**3. Notebook 02 shows nothing after its first fit.** The first refinement
cell (`examples/tutorials/02_simple_rietveld.py`, "A first refinement") prints
the status, the cell and the diagnostics. The first figure arrives as
`final.plot()`, ten cells later. A person verifies a fit by looking at the
difference curve. Pass the live view to that first fit, so its final frame is
the picture, and keep `result.plot()` as the explicit call that a reader copies.
Use one of the two, not both: two identical figures in one cell teach nothing.
Edit the `.py` and rebuild with `build.py`, never the `.ipynb`
(`examples/tutorials/README.md`). Look over 01, 03, 04 and 05 for a fit with
no picture after it, and give each the same treatment, or say why not.

**4. The 3D viewer in Colab. Two rungs, and only the first is small.**
- *Static:* `rx.viz.render_structure(structure)` already draws the GUI viewer's
  scene to a `StructureFigure`, and a notebook shows it through `_repr_png_`
  (WP-1544). Notebook 02 gains a cell drawing the refined fluorapatite after
  the bonds section, with polyhedra on the phosphate and a view down c. This
  costs one cell and no code.
- *Interactive:* the GUI viewer is `gui/src/lib/structure3d.ts` (scene
  arithmetic, 1035 lines) and `lib/gl3d.ts` (WebGL2 impostors, 723 lines).
  Its payload comes from `gui/structure3d.build` in Python. The rotate, zoom
  and hover controls live in `panels/Structure3D.svelte` (826 lines), so a
  notebook viewer needs a second vite entry: a framework-free bundle of the two
  `lib/` modules plus a pointer controller extracted from the panel, emitted
  as an inline `<script type=module>` with the payload as JSON. Colab trusts
  outputs, and a committed notebook stores the script and its data in every
  output. That is WP-1544's 275 KB objection to `rx.viz.interactive`,
  unchanged. It also sits inside the JavaScript-output half of the fence. So it
  gets a scoping task in this WP, which measures the bundle's minified size and
  FAP's payload size and records a go or no-go. It gets no build.

## Non-goals

- An interactive per-iteration chart (anywidget/ipywidgets), and building the
  interactive 3D viewer. The fence stays on both. Task 6 decides whether the
  3D viewer gets its own WP.
- Making the live view a default. A notebook that shows a fit unasked grows
  every committed output, and `fit()` stays silent in a kernel unless asked.
- `rietx watch` and the GUI. They draw from the run directory, and nothing here
  changes how they do it.
- The landing page and its Colab links (WP-1917).

## Tasks

- [ ] `DESIGN.md` § Locked decisions: a dated amendment to the widget fence,
      with the in and out halves exactly as stated in Context, once the
      maintainer agrees. Fix WP-1544's non-goal by pointing to it, without
      rewriting it.
- [ ] Declare the width alone: `_notebook_png` and `StructureFigure._repr_png_`
      both declare CSS width only. Update `tests/test_display.py`. Then the
      maintainer opens notebook 01 in Colab at a narrow window, before and after
      the fix (`build.py` regenerates the outputs), and records the result in
      the handover.
- [ ] The live view: an `EventStream` subclass with `write_snapshot`, a
      `display_id` frame per stage drawn from `build_snapshot`'s payload with
      `plot_result`'s code, and a status line on `eval`, throttled by time. It
      declines quietly outside a kernel, and a recording that fails never breaks
      the fit (the recorder rule in root CLAUDE.md, `runs.py`). Export it, then
      document it in Part 1.
- [ ] Notebook 02: the live view on the first fit, and the structure figure
      after the bonds. Sweep 01, 03, 04 and 05 for fits with no picture after
      them. Rebuild with `build.py`, then run `build.py --check`.
- [ ] Tests: the frames fold into one output under `nbclient` (one image
      output in the executed cell, which is the measurement Context calls
      unmeasured); there are no outputs and no error outside a kernel; the time
      throttle holds; the frame's numbers equal the snapshot payload's. Record
      the per-stage frame cost on FAP and on `nac` in the handover.
- [ ] Scope the interactive 3D viewer: measure a standalone bundle of
      `structure3d.ts`, `gl3d.ts` and a pointer controller (minified KB), and
      FAP's `structure3d.build` payload as JSON. Record a go or no-go against
      WP-1544's 275 KB objection and the fence. On go, file the build WP; do
      not build it here.
- [ ] Skill: the live view is for people watching a cell, and an agent reads
      the result, so the skill takes no line. State that in the handover, or
      add a `references/` row if an agent driving a notebook for a person
      needs it.

## Acceptance

Every figure shown in a notebook declares only its width. Notebook 02's
first-fit cell holds exactly one figure, and the executed notebook passes:

```sh
.venv/bin/python -m pytest tests/test_display.py tests/test_tutorials.py -n auto --dist loadgroup
.venv/bin/python examples/tutorials/build.py --check
.venv/bin/python -m pytest tests/test_manual_api.py -n auto --dist loadgroup
.venv/bin/python -m ruff check src tests examples
```

The maintainer records the Colab check, before and after, in the handover.

## References

- Jupyter messaging protocol, `update_display_data`:
  https://jupyter-client.readthedocs.io/en/stable/messaging.html#update-display-data
- IPython `display(..., display_id=True)` and `DisplayHandle.update`.
- anywidget (the tier left out): https://anywidget.dev. Colab's custom widget
  manager: `google.colab.output.enable_custom_widget_manager()`.

## Handover log

- **2026-10-13** — created from the maintainer's four Colab asks. Checked for
  an owner first. No open WP owns this work. 1545 (tutorial notebooks, every
  task done, in review) fences widgets in its non-goals. 1917 owns the landing
  page's Colab links, not what renders inside them. 1544, which owns the
  notebook PNG encoding, is ✅, so a defect in it belongs in a new WP.
  Next: the maintainer decides on the fence amendment (task 1).

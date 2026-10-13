# WP-1957 — a fit seen in Colab: figures at their own shape, the structure beside them, a template for your own data

Milestone: unscheduled · Status: 🔄 2026-10-13 — width-only figures, notebook 02's fit and structure, template 06 landed; the Colab check and the PNG-size decision remain
Track: Render what the fit already knows
Depends on: —
Priority: P2 2026-10-13 — a defect with a named user: the Colab quickstart (1917) is live, every figure in it draws distorted, and the maintainer asked

## Goal

A notebook opened from the landing page's Colab links shows every rietx figure
at its designed aspect ratio. Notebook 02 shows the fit right after the first
refinement and draws the refined structure from views that teach the viewer's
controls. A sixth notebook is a template a person fills in with their own data.

## Context

The maintainer asked for these on 2026-10-13.

**1. Figures stretch in Colab.** Every figure shown in a notebook goes through
`viz.plots._notebook_png` (WP-1544). Until this WP that function declared the
PNG's `{"width", "height"}` in CSS pixels, and the frontend renders that as
`<img width=… height=…>`. JupyterLab's stylesheet carries
`max-width: 100%; height: auto`, so it shrinks the whole image. **Hypothesis,
still unmeasured:** Colab clamps the width to the output column and keeps the
declared height, so a figure is squashed in any column narrower than it. The
fit figures are 670–796 CSS px wide.
**Landed:** a figure declares its width alone, and every frontend derives the
height from the pixels. `StructureFigure._repr_png_` follows the same rule,
drawn at half its pixel width as a fit figure is. Only the maintainer can
measure Colab, so that check is the open task.

**2. The live view is deferred** (maintainer, 2026-10-13). The design is kept
here for whoever picks it up. The stage loop hands a picture to any object
passed as `events=` that has a `write_snapshot(model, table, outcome,
stage_name)` method (`refine._snapshot_sinks`). `viz/snapshot.build_snapshot`
builds the payload from the stage's frozen model. A notebook view would be an
`EventStream` with that method, drawing each stage's payload and replacing one
output in place through `display(…, display_id=True)` and `handle.update(fig)`.
It would update a status line on `eval` events, throttled by time. That needs
no comm, no JavaScript and no dependency, and it works in Colab. It does need
`DESIGN.md`'s widget fence narrowed first, because WP-1544 read that fence as
covering "a live fit view". The interactive tier (anywidget carrying
`rxplot.mjs`) stays fenced.

**3. PNG size: the measurements, and the decision still open.** The
maintainer asked whether the PNGs could be replaced with refinement output to
save space. All figures below are the FAP fit figure, with sizes as base64 in
the `.ipynb`:

| Encoding | Size |
|---|---|
| As shipped (2× density, 256 colours) | 69 kB |
| 2× density, 64 colours | 56 kB |
| 2× density, 16 colours | 45 kB |
| 1× density, 256 colours | 26 kB |
| 1× density, 16 colours | 17 kB |
| Lossless WebP, 2× density | 55 kB |
| SVG | 910 kB |
| The three curves as JSON at 6 significant figures, for a JS chart to draw (before the chart library) | 127 kB |
| The result's own text view (`_repr_html_`, no picture) | 6 kB |

So the PNG is the smallest form that carries the picture. Drawing the
picture from data in the page costs more, and only the text view is smaller.
The one real saving that keeps a picture is 1× density, at 62 % smaller, and
it costs sharpness on a HiDPI screen. That is the maintainer's call, so this
WP does not decide it.

The structure figure was the actual space problem. Its `_repr_png_` wrote
full-colour RGBA, about 185–200 kB a view, and 02 grew from 99 kB to 688 kB.
It is now palette-quantised at the fit figure's 256 colours (74 kB a view,
no visible banding; 64 colours bands the shaded balls). A transparent figure
keeps its alpha. Committed sizes now: 01 150 kB, 02 378 kB, 03 159 kB,
04 101 kB, 05 44 kB, 06 334 kB.

**4. The structure view, chosen by agents.** `render_structure`'s controls
are `view` (`"a"`/`"b"`/`"c"`, `[u, v, w]`, `{"hkl": (h, k, l)}`,
`"opening"`, `"auto"`), `turn` (ASE's `"20x,10y"`, about the screen's axes),
`mode`, `polyhedra` and `atom_labels`.
Round 1: three blind reviewers judged 15 renderings of refined fluorapatite.
They were a crystallographer, a newcomer and a figure designer.
- The view down c ranked first, first and second.
- The designer ranked the default oblique view first.
- `auto` was called a tangle by all three.

Round 2: one reviewer judged six follow-ups. It chose `view="c"` at its
default portrait size (a square canvas makes the picture 1.4× smaller at
600 px). For the second cell it chose the default view with `turn="-15x"`,
the only candidate that reads as 3D, and said the cell earns its place only
with a caption saying what to look for.
Notebook 02 carries that pair. The template uses the default view rather
than `auto`, for the same reason. Each render took 75–700 ms here, and
110–200 ms for the two chosen views. What the reviewers found wrong with the
viewer went to WP-1504's Inherited.

**5. A template notebook.** `examples/tutorials/06_your_own_data.py`. Cells
marked ✏️ take the pattern, the CIFs (one per phase), the anode and the
range. It runs top to bottom:
1. the data, and `rx.diagnose`;
2. the model over a 10° window before any fit;
3. Le Bail, on a copy of the model;
4. Rietveld;
5. `summary(deliverable="structure")`;
6. the structure figure;
7. a refinement CIF, the fit PNG and a `.rex` project, written to
   `rietx_output/`.

It ships running on the fluorapatite files, so `tests/test_tutorials.py`
executes it like the tutorials, and the landing page and manual list it. The
build now executes every notebook in a scratch directory, so the files 06
writes never land in the repository.
Measured on the example: Le Bail Rwp 0.0982 and Rietveld Rwp 0.0936. Le Bail
under `profile_only` frees less than `mccusker_structural`, so it is **not**
a floor on Rietveld here, and the template's text says only that a Rietveld
Rwp well above it points at the structure.

## Non-goals

- The live view and any interactive chart. Both are deferred, with the design
  kept in Context.
- An interactive 3D viewer in a notebook. It needs a JavaScript bundle in
  every committed output, which WP-1544 cut for the fit at 275 KB, and it sits
  inside the fence.
- Fixing what the view reviewers found in the viewer (WP-1504).
- The landing page and its Colab links (WP-1917).

## Tasks

- [x] A notebook figure declares its width alone. Both `_notebook_png` and
      `StructureFigure._repr_png_` now do, and `tests/test_display.py` was
      updated.
- [x] The structure figure in a notebook uses the 256-colour palette, and a
      transparent one keeps its alpha.
- [x] Notebook 02: the plot after the first fit, and the refined structure
      down c and at `turn="-15x"`, with captions. `test_tutorials` now checks
      that a `render_structure` cell shows an image. Every notebook is rebuilt.
- [x] Notebook 06, the template, plus its README and manual rows and the
      scratch-directory build.
- [ ] The maintainer opens notebook 02 in Colab at a narrow window, once the
      next release carries this, and records whether the figures keep their
      shape.
- [ ] The maintainer decides the PNG density question (Context 3): keep 2×,
      or go to 1× and save about 60 %.
- [ ] Skill: none. The changes are display encoding and notebooks for people.
      An agent reads results rather than notebook outputs, and the figure
      surface it uses did not change.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_display.py tests/test_tutorials.py tests/test_landing.py tests/test_docs_consistency.py tests/test_manual.py tests/test_manual_api.py -n auto --dist loadgroup
.venv/bin/python examples/tutorials/build.py --check
.venv/bin/python -m ruff check src tests examples
```

The maintainer records the Colab check in the handover.

## References

- Jupyter messaging protocol, `update_display_data` (for the deferred live view):
  https://jupyter-client.readthedocs.io/en/stable/messaging.html#update-display-data
- anywidget, the interactive tier left out: https://anywidget.dev

## Handover log

### 2026-10-13 (second session) — the figures, notebook 02, the template

The notebooks now give every figure its width only. A frontend that clamps
the width cannot then squash a figure, which is the likely cause of the
stretching in Colab. The fix reaches Colab with the next release, and only
the maintainer can confirm it there. Notebook 02 shows the fit the moment the
first refinement ends. It also draws the refined apatite twice, down c and
tipped 15°, in views three blind agent reviewers chose and a fourth
confirmed, so a reader learns `view` and `turn` from a picture they recognise.
A sixth notebook is a template that runs on the example files until a person
puts in their own. One problem surfaced along the way and is fixed: a
structure figure cost about 190 kB a view in a notebook, and now costs 74 kB.

*Measured* (Linux cloud container, `[dev]` venv in this worktree). The
display, tutorials, landing, docs-consistency and manual files pass: 147
passed before the landing fix, 30 landing after. Ruff is clean, and
`build.py --check` exits 0. A FAP fit took 5.4 s; the 06 build took 14 s.
Every number on PNG size and the view choice is in Context 3 and 4.

*Decided by the maintainer:* the live view is deferred, and its design stays
in Context 2.

The fast suite (`-m "not slow"`, run alone): 9333 passed, 192 skipped,
1 xfailed, 1 failed, in 19:31. The failure was
`test_figure_boundary`: `figure3d/render.py` had imported `viz.plots` for its
colour count, which crosses the boundary WP-1505's split moves. The count is
now restated as `render.NOTEBOOK_COLOURS`, and `test_display` holds the two
equal. That file, the boundary file and the manual-API file then passed (45).
The suite was not re-run after the fix.

Next: the maintainer's two open tasks, the Colab check and the PNG density.

- **2026-10-13** — created from the maintainer's four Colab asks. Checked for
  an owner first. No open WP owns this work. 1545 (tutorial notebooks, every
  task done, in review) fences widgets in its non-goals. 1917 owns the landing
  page's Colab links, not what renders inside them. 1544, which owns the
  notebook PNG encoding, is ✅, so a defect in it belongs in a new WP.
  Next: the maintainer decides on the fence amendment (task 1).

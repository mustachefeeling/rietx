# WP-1462 — the structure viewer draws with three.js

Milestone: unscheduled · Status: ⬜
Depends on: 1461 (soft)
Priority: P3 2026-09-25 — after WP-1461 the structure viewer is the last page that loads plotly, 4.82 MB evaluated in a 700-811 ms frame on its first show

## Goal

The GUI's 3D structure viewer draws with three.js. No page rietx serves
loads plotly.js, and `pyproject.toml` names plotly nowhere. Everything the
viewer shows and does today survives, and its crystallography rules in
`gui/CLAUDE.md` stand unchanged.

## Context

### What the viewer is

WP-1015 built the viewer and its second pass set its look
(`gui/CLAUDE.md`, the structure viewer paragraphs). Its founding rule is
that everything hard stays on the server. `GET /api/structure3d`
(`src/rietx/gui/structure3d.py`) sends Cartesian positions, 3×3 matrices and
index pairs. The browser's whole job is `pos + T·v` over one unit sphere,
which is also why a ball and an ellipsoid are one code path.

The browser half is `gui/src/panels/Structure3D.svelte` (507 lines) and
`gui/src/lib/structure3d.ts` (701 lines), tested by `structure3d.test.ts`
(435 lines) and `tests/test_structure3d.py`. It draws, through plotly:

- atoms as one `mesh3d` per species, each atom the unit sphere under its
  own transform, in Å;
- bonds as two-tone cylinders in Å, one `mesh3d` per species, where a half
  belongs to its atom;
- the cell as `scatter3d` lines in `--accent`, and the a, b and c labels as
  `scatter3d` text at a clearance set by the largest ball;
- a parallel projection, a free trackball (`dragmode: "orbit"`), and a
  light that rides the camera.

And it does:

- ball or ellipsoid mode, and a phase picker;
- a legend whose buttons hide a species, its bond halves included;
- buttons that look down a, b or c, and a reset;
- knobs for the ellipsoid probability, an exaggeration factor and the bond
  tolerance, the last a server round trip;
- hover text per atom (`atomLabel`: label, species, fractional position,
  occupancy, RMS displacements, image outside the cell) and per bond (the
  two site labels and the length in Å);
- a PNG of the scene, plotly's modebar `toImage` and the only button kept;
- the view kept across every redraw, and a `ResizeObserver` size.

### What plotly costs it

The viewer mounts hidden inside the Model panel at boot
(`Model.svelte:455`), so today it is one reason the GUI evaluates plotly
at every open: a 700-811 ms long animation frame (WP-1461,
`1461-uplot-spike/results/gui_td.txt`). WP-1461 defers that load to the
viewer's first show. After WP-1461, this viewer is the only thing that
loads plotly, and the only reason the `gui` extra depends on it.

Several of the viewer's rules exist only because of plotly:

- `react` with fresh trace objects resets the gl3d camera, so the view is
  read back from `gd._fullLayout.scene._scene.getCamera()` before every
  draw, since `layout.scene.camera` reports only what was passed in and
  `plotly_relayout` never fires for a gl3d camera drag;
- `dragmode: "orbit"`, because turntable rewrites any camera whose `up` is
  not +z;
- `responsive: true` hears window resizes only, so a `ResizeObserver`
  calls `Plots.resize`;
- `scatter3d` markers and lines are sized in pixels, so every shape is a
  `mesh3d`.

### The candidates, measured

Measured 2026-09-25. For three.js, the viewer's likely imports were bundled
with esbuild `--minify` and compressed with `gzip -9`: `WebGLRenderer`,
`Scene`, `OrthographicCamera`, `PerspectiveCamera`, `InstancedMesh`,
`BufferGeometry`, `BufferAttribute`, `MeshLambertMaterial`, `LineSegments`,
`LineBasicMaterial`, `AmbientLight`, `DirectionalLight`, `Raycaster`,
`Vector2`, `Matrix4`, `Color` and `TrackballControls`.

| | version, licence | minified | gzip |
|---|---|---|---|
| plotly.js, as today | Python `plotly` 7.1.0, MIT | 4.82 MB | 1.47 MB |
| three.js, the subset above | 0.186.1, MIT | 557 KB | 138 KB |
| 3Dmol.js, whole build | 2.5.5, BSD-3-Clause | 538 KB | 156 KB |

Both are about a ninth of plotly. Neither has been timed drawing this
viewer's scenes.

three.js is a general 3D engine. An `InstancedMesh` draws one geometry
under a matrix per instance, which is the `pos + T·v` the viewer already
does, so the server's payload maps onto it unchanged. `TrackballControls`
is a free trackball like plotly's orbit mode, at 5 KB compressed.

3Dmol.js is a molecule viewer with its own model of atoms, bonds and
styles, and by default it finds bonds itself. The server owns the bond rule
here (`gui/CLAUDE.md`: LaB6's La–La edges). Whether 3Dmol.js draws the
server's ellipsoids and bonds as given is untested.

### Inherited

**From WP-1461 (2026-09-25).** The Dependabot allow list exists now, as
`.github/dependabot.yml` with `uplot` alone, so three.js is one more
`dependency-name` there. A library compiled into the dist also owes its
licence text to `LICENSE-3RD-PARTY.md`, the file the wheel ships as its
notices, beside the ATTRIBUTION row this WP's pin task names. WP-1461 added
uPlot's there.

**From WP-1461 (2026-09-25, 5th session).** The pattern panel left plotly, so
two things in `gui/src` serve only this viewer and the Series panel:
`lib/plot.ts:hoverLabel` and the `Plotly` stand-in in `test-setup.ts`.
Whichever of this WP and WP-1461's Series task lands second deletes them. The
jsdom answer to "jsdom has no canvas" is `gui/src/test-uplot.ts`, a stand-in
that records what was asked to be painted, with `tests/test_gui_browser.py`
reading what chromium painted. A three.js scene wants the same two halves.

## Decisions this WP takes

Each carries the recommended answer, for the maintainer to confirm or
overturn in the first task.

- **D1. three.js, bundled into the GUI.** Pinned exactly in
  `gui/package.json` and bundled by vite, as CodeMirror is, so tree-shaking
  keeps only what the viewer imports. Only the GUI draws in 3D, so there is
  no vendored copy for other pages. It joins the Dependabot allow list that
  WP-1461 creates.
- **D2. The payload does not change.** `/api/structure3d` and every rule
  in `structure3d.py` stay as they are. `structure3d.ts` keeps its pure
  half: `unitSphere`, `unitCylinder`, `stickTransform`, `atomTransform`,
  `axisCamera`, `atomLabel`, `legend` and `caption`. Its plotly trace
  builders go.
- **D3. The a, b and c labels are a DOM overlay.** Each label is placed at
  its projected 3D position on every frame. Text stays crisp, takes the
  theme's font and colour, and needs no font atlas.
- **D4. Hover by picking.** A `Raycaster` finds the instance under the
  pointer. The instance index gives the atom or the bond half, and the
  tooltip shows today's text.
- **D5. PNG export draws once more into a canvas.** The scene renders once
  on request and the canvas becomes a PNG. The WebGL buffer is not kept
  between frames for this.

## Where it will bite

- **A WebGL context is a scarce resource.** Browsers cap the number of
  live contexts. The viewer must dispose its renderer, geometries and
  materials on unmount. Today it disconnects its `ResizeObserver` and
  nothing else, and never calls `Plotly.purge`, so toggling the viewer
  may already leak a context. The spike counts contexts across toggles.
- **jsdom has no WebGL.** vitest covers the pure half and the scene
  builders' outputs. A browser test covers the drawing, and it compares
  pictures or reads back pixels, never a hash of a screenshot
  (`gui/CLAUDE.md`: a WebGL re-render differs by a pixel).
- **WebGL lines are one pixel wide.** The cell frame is thin at any zoom.
  If that reads badly, the edges become cylinders like the bonds.
- **The camera is owned outright.** three.js keeps the camera between
  draws, so the read-back rule above goes. A redraw must still not reset
  the view, and a test says so.

## Non-goals

- **A new look.** The second pass's choices (parallel projection, no axis
  box, cylinders in Å, a/b/c labels, the light on the camera) carry over.
- **New structure features:** polyhedra, a packing diagram, labels on
  atoms, animation of a refinement.
- **Any other chart.** 2D charts are WP-1461's.

## Tasks

- [ ] The maintainer confirms D1-D5, and this file records which
- [ ] Spike, the gate: three.js drawing the real `/api/structure3d` payload for LaB6, one structure with anisotropic sites in ellipsoid mode, and the largest cell among the example projects. Measure first show (load to first frame), rotation frames and hover work per event, beside today's plotly viewer on the same machine, in Chromium, WebKit and Firefox. Record go or no-go in the handover. On no-go, try 3Dmol.js on the same payloads before stopping.
- [ ] Pin three.js in `gui/package.json`, add its ATTRIBUTION row, and add it to the Dependabot allow list
- [ ] The scene: instanced atoms per species, two-tone bond cylinders, the cell frame, the a/b/c overlay, the orthographic camera, the trackball, the light on the camera, theme colours, and disposal on unmount
- [ ] Interaction: hover, legend toggles, the a/b/c and reset views, the three knobs, the view kept across redraws, `ResizeObserver` sizing, and PNG export
- [ ] Delete plotly: the trace builders, the camera read-back, `gui/src/lib/plotly.ts`, the `/plotly.js` route, the `gui` extra's plotly, and `viz/plotlyjs.py` if WP-1461 left it only for this viewer
- [ ] Tests: `structure3d.test.ts` on the scene builders; a browser test that reads pixels at known atoms and asserts a redraw keeps the view; a test that no page requests `/plotly.js`
- [ ] Docs: the structure viewer paragraphs in `gui/CLAUDE.md` (crystallography rules kept, plotly traps deleted), `using/install.md` for the `gui` extra, ATTRIBUTION.md, and the root CLAUDE.md's GUI lines if they name plotly

## Acceptance

Measured like WP-1461's § Acceptance: the spike driver ported to the real
page, paired with the plotly viewer on the same machine and load, three or
more runs for ranges, recorded in the handover.

1. **No plotly anywhere.** No page requests `/plotly.js`, the route is
   gone, and `pyproject.toml` names plotly in no extra.
2. **First show:** no long animation frame is attributed to the 3D library.
   The time from the viewer's first show to its first frame is recorded
   beside plotly's.
3. **Rotation:** on the largest example structure, a trackball drag holds a
   p95 frame of 17.7 ms or less with zero long animation frames. Hover work
   per event is recorded.
4. **Coverage:** every item in § What the viewer is is present and named by
   a test.
5. **Browsers:** in Chromium, WebKit and Firefox through playwright's
   builds, the viewer draws, rotates and hovers, and nothing throws.

```sh
npm --prefix gui test && npm --prefix gui run check
.venv/bin/python -m pytest tests/test_structure3d.py tests/test_gui_server.py
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

## References

- three.js 0.186.1, MIT. <https://github.com/mrdoob/three.js>
- 3Dmol.js 2.5.5, BSD-3-Clause. Rego, N. & Koes, D. (2015). 3Dmol.js:
  molecular visualization with WebGL. *Bioinformatics* 31, 1322-1324.
  <https://github.com/3dmol/3Dmol.js>
- plotly.js, MIT, as served by the Python `plotly` 7.1.0 package.
- VESTA, Momma, K. & Izumi, F. (2011). *J. Appl. Cryst.* 44, 1272-1276.
  The viewer's second pass read its look against VESTA, Jmol and 3Dmol.js.
- WP-1015 (the viewer) and WP-1461 (every 2D chart on uPlot).

## Handover log

- **2026-09-25** — filed from WP-1461's session, on the maintainer's
  request, once they confirmed the move to uPlot. The library sizes above
  were measured that day. Nothing else was: no scene was drawn in three.js
  or 3Dmol.js. *Next:* the maintainer confirms D1-D5, then the spike.

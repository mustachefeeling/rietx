# WP-1462 — the structure viewer draws with three.js

Milestone: unscheduled · Status: ⬜
Depends on: 1461 (soft)
Priority: P3 2026-09-25 — after WP-1461 the structure viewer is the last page that loads plotly, 4.82 MB evaluated in a 700-811 ms frame on its first show

## Goal

The GUI's 3D structure viewer leaves plotly. No page rietx serves loads
plotly.js, and `pyproject.toml` names plotly nowhere. Everything the viewer
shows and does today survives, and its crystallography rules in
`gui/CLAUDE.md` stand unchanged.

The title names three.js, the answer this file was filed with. The second
session recommends a renderer of our own instead (D1). The file keeps its
name until the maintainer decides, because WP-1461's in-flight file links
to it.

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

### How big the scenes are

`structure3d.MAX_ATOMS` = 400 and `MAX_BONDS` = 4000 bound every scene. The
three payloads the spike drew hold 116 to 173 atoms and 174 to 255 bonds
(`1462-spike/payloads.py`: LaB6, NAC with its anisotropic tensors, and
fluorapatite). Any renderer draws that at 60 frames a second. So speed
does not separate the candidates. Load size, the look and the code we own
do.

### The field, measured

Measured 2026-09-25 by `1462-spike/measure.mjs`
(`results/sizes.txt`). Each row bundles the imports a viewer would use,
with esbuild 0.28.2 `--minify`, then `gzip -9`.

| Library | version, licence, upkeep | minified | gzip |
|---|---|---|---|
| plotly.js, as today | Python `plotly` 7.1.0, MIT | 4.82 MB | 1.47 MB |
| NGL | 2.5.0, MIT | 1329 KB | 377 KB |
| three.js, `three/webgpu` | 0.186.1, MIT | 791 KB | 216 KB |
| 3Dmol.js, whole ESM build | 2.5.5, BSD-3-Clause | 587 KB | 169 KB |
| three.js, the 17 imports D1 named | 0.186.1, MIT | 557 KB | 139 KB |
| three.js, renderer and one custom shader | 0.186.1, MIT | 545 KB | 137 KB |
| regl | 2.1.1, MIT, no release since 2024-11 | 123 KB | 41 KB |
| uPlot, for scale | 1.6.32, MIT | 52 KB | 23 KB |
| OGL, scene graph with orbit and raycast | 1.0.11, Unlicense, last release 2025-01 | 63 KB | 19 KB |
| PicoGL.js | 0.17.9, MIT, last commit 2022 | 66 KB | 15 KB |
| twgl.js | 7.0.0, MIT, maintained | 41 KB | 14 KB |
| the spike's prototype renderer | no dependency | 11 KB | 4.8 KB |

The three.js rows show where its size lives. Swapping the stock materials
and lights for one custom shader saves under 3 KB of 139 KB, because
`WebGLRenderer` carries its whole material system.

The rows fall into three tiers. The general engines (three.js, and Babylon.js
and PlayCanvas, which are larger) carry a scene graph, materials and
controls. The thin helpers (twgl.js, OGL) wrap WebGL's program and buffer
calls and are uPlot's size. The molecular viewers own a model of atoms,
bonds and styles. Only Mol\* (5.11.0, MIT) among maintained browser
libraries was found to draw displacement ellipsoids, from its own mmCIF
tensor reader. JSmol draws them too, at 18-20 MB and LGPL. Both would take
the crystallography back from the server, against WP-1015's founding rule.
matterviz (MIT, Svelte 5, three.js through threlte) draws no displacement
ellipsoids, and ChemDoodle Web's free tier is GPLv3. This paragraph comes
from a survey agent's reading of each project's source and docs, and none
of it was measured here.

### What the molecular viewers do

The fast molecular viewers draw an atom as a ray-cast impostor: Mol\*,
NGL, VMD, QuteMol and speck. One screen-aligned quad stands for each atom
or bond. The fragment shader solves the sphere, cylinder or ellipsoid
exactly along the pixel's ray, discards a miss, and writes the hit's depth
through `gl_FragDepth`. The surface is exact at every zoom, and a scene
costs four vertices per primitive (Sigg et al. 2006; Gumhold 2003; Tarini
et al. 2006). A parallel projection makes it simpler still, since every ray
has the same direction.

Mol\* picks by rendering primitive ids to an offscreen buffer and reading
one pixel. That is needed when a surface exists only in a shader. Here the
browser holds each atom's position and T, so the CPU can solve the same
quadric for the pixel under the pointer.

Two platform facts bound the choice. WebGL2 is universal in the three
engines the GUI supports, and `gl_FragDepth` is core in it. WebGPU is not
yet universal: Firefox ships it on Windows since 141 and on Apple silicon
macOS since 145, with Linux still in progress.

### The prototype

`1462-spike/viewer.js` draws the served payload unchanged, as ray-cast
quadrics. It is 392 lines with no dependency.

- **Atoms.** One instanced quad per atom, sized to the exact projected
  extent of the ellipsoid (the norms of the first two rows of R·k·T). The
  fragment shader solves |(k·T)⁻¹(p − c)| = 1 along the view ray. A ball
  is k·T = r·I, so ball and ellipsoid stay one code path.
- **Principal ellipses.** `structure3d._ellipsoid` returns
  T = V·diag(√λ), so T's columns are the principal axes. A principal
  ellipse is then one unit-frame coordinate near zero, three lines of
  shader. ORTEP draws these rings (Johnson 1965). The viewer has never had
  them. `shots/nac-rings.png` shows them on NAC at 2.5× exaggeration.
- **Bonds.** One quad per bond half, solved as a finite cylinder, coloured
  by the atom the half leaves.
- **The rest.** The cell as `gl.LINES`, the a/b/c labels as DOM text, a
  trackball, wheel zoom, CPU picking and a PNG through `toDataURL` in the
  drawing task.
- **Degenerate tensors.** A zero semi-axis has no inverse, so the prototype
  draws it at 1 mÅ. The server's rule stands: the axis still reads as zero.

Measured 2026-09-25, playwright-core 1.63.0, headed, devicePixelRatio 2, on
an Apple M4 shared with other sessions (load average up to 48). Three runs
(`results/proto_run0.txt` to `proto_run2.txt`):

| | Chromium 1223 | Firefox 1543 | WebKit 2359 |
|---|---|---|---|
| data to first frame, first page | 78-265 ms | 33-101 ms | 145-1643 ms |
| data to first frame, later pages | 23-55 ms | 29-97 ms | 22-47 ms |
| draw call, main-thread work per frame | p95 0.1-0.2 ms | p95 ≤ 1 ms (1 ms timer) | p95 ≤ 1 ms (1 ms timer) |
| frame gap during rotation, p95 | 17.5-17.6 ms | 17-33 ms | 17-22 ms |
| hover pick, per event | 12-24 µs | 14-61 µs | 14-26 µs |
| errors | none (a favicon 404) | none | none |

The first page's cost is the browser's first WebGL context and shader
compile. It moved from 1643 ms to 145 ms between runs on WebKit, so it is
the machine's state as much as the page's. It applies to plotly's viewer
too, and only a paired measurement separates them. The three engines drew
the same picture: a mean absolute difference of 0.07 and 0.02 levels of 255
against Chromium (`shots/engines-nac.png`). Headless Chromium runs on
SwiftShader, the CPU rasteriser `tests/test_gui_browser.py` gets, and drew
the same scenes. No CI workflow installs playwright, so no browser test
runs in CI.

The prototype lacks the legend, the a/b/c buttons, the knobs, bond hover,
theme colours and context-loss handling. A full viewer is estimated at
700 lines and under 10 KB gzip.

### Polyhedra

The maintainer asked for a polyhedral view on the same day, because many
users will be solid-state chemists. The spike added one to test whether it
moves D1. `payloads.py` stands in for the server. It reads each centre's
shell off the bond segments, takes the convex hull with scipy, and sends
vertices, outward-wound triangles and edges. `viewer.js` draws them as
ordinary triangles after the opaque impostors: depth-tested against them,
writing no depth, blended at alpha 0.55. Each frame orders the polyhedra
farthest first by centroid and draws each one's back faces before its
front faces.

- **The renderer part is small.** It is 88 lines, taking the prototype to
  480 lines, 13.3 KB minified and 5.5 KB gzip (`results/sizes_poly.txt`).
  NAC's 26 polyhedra (AlF₆ and CaF₈) drew the same in the three engines, a
  mean difference of 0.016 and 0.009 levels of 255
  (`shots/engines-nac-poly.png`). A frame's draw call stayed at p95 0.3 ms
  in Chromium and the frame gap at p95 17-18 ms in all three
  (`results/proto_run3_poly.txt`, load average 43).
- **The ordering is right while polyhedra do not interpenetrate.**
  Coordination polyhedra share corners, edges or faces and never overlap in
  volume, so ordering whole polyhedra works. If artefacts appear,
  weighted blended order-independent transparency needs no ordering at all
  (McGuire & Bavoil 2013). three.js also orders transparent objects whole
  and ships no order-independent mode, so it gains nothing here.
- **The bond rule is not a coordination rule.** Under the radius-sum rule,
  fluorapatite's P reaches 4 Ca at 3.1-3.2 Å beside its 4 O, so its first
  hull had 8 vertices. The spike's ligand rule takes the non-metal
  neighbours of another element. It gives PO₄, AlF₆ and CaF₈. gemmi carries
  no electronegativity table and neither does rietx, so a better rule needs
  a table with a citation.
- **A shell is matched by position.** The server can find a contact from a
  translated copy of the centre, so a shell collected by atom index came out
  short on 6 of 18 Ca in NAC.
- **The hull needs care at its edges.** A square face comes out as two
  triangles, so an edge is drawn only where its two faces are not
  coplanar. A shell of fewer than four atoms, or a planar one such as CO₃,
  has no 3D hull, and the spike met neither.
- **A shell's size under the bond rule is not a safe default key.** Every
  site as a centre gives LaB6's La 24 B, NAC's Al 6, Ca 8 and Na 4 F, and
  fluorapatite's P 4 O and both Ca 9. Na's shell of 4 is the covalent-radius
  cutoff cutting a large ionic cation's shell short. So "draw polyhedra
  where the shell holds 4 to 6" would draw a NaF₄ tetrahedron that is not
  there.
- **Not tried:** hovering a polyhedron (a ray–triangle test on the CPU),
  hiding the centre-to-ligand bonds inside a polyhedron, and choosing the
  centres in the GUI.

Hard polyhedra work falls on the server. The ligand rule, the hull and the
degenerate shells are chemistry and geometry, and WP-1015's founding rule
keeps both there.

## Decisions this WP takes

Each carries the recommended answer, for the maintainer to confirm or
overturn in the first task. The second session changed D1 and D4 and
added D6 to D8.

- **D1. The viewer draws its own quadrics in WebGL2, with no library.** It
  follows the practice of Mol\* and NGL, measured above at 4.8 KB gzip
  against three.js's 139 KB. It needs no Dependabot entry, no licence row
  and no bundle pin, as WP-1015's "zero new dependencies" had it. Three
  alternatives were weighed. A thin helper (twgl.js, OGL) would replace the
  60 lines of program and buffer setup the prototype already has. three.js
  would draw tessellated meshes and would need a custom shader or extra
  geometry for the rings. A molecular viewer owns the crystallography. **Fallback:**
  three.js, bundled and pinned, if the spike's gate fails on a GPU the
  prototype has not met.
- **D2. The payload does not change.** The prototype drew it as served.
  `structure3d.ts` keeps its pure half: `atomTransform`, `axisCamera`,
  `atomLabel`, `legend`, `caption` and `stickRadius`. The trace builders
  and the tessellation (`unitSphere`, `unitCylinder`, `stickTransform`) go,
  since impostors need no mesh.
- **D3. The a, b and c labels are a DOM overlay.** Each label is placed at
  its projected 3D position on every frame. Text stays crisp, takes the
  theme's font and colour, and needs no font atlas.
- **D4. Hover solves the quadric on the CPU.** The same equation the shader
  solves, for the pixel under the pointer, costs 12-61 µs an event at 116
  to 173 atoms. It needs no id buffer and no pixel read-back.
- **D5. PNG export draws once more and reads the canvas in the same task.**
  The WebGL buffer is not kept between frames for this.
- **D6. Anisotropic sites show their principal ellipses in ellipsoid
  mode.** This is the one new look this WP adds, three lines of shader.
  The octant cut-out stays out (Non-goals). Strike it and the rest stands.
- **D7. Silhouettes are antialiased in the shader.** MSAA smooths triangle
  edges only, and an impostor's outline is a `discard`. At devicePixelRatio
  1 the prototype's outlines step (`shots/lab6-dpr1-edges.png`). The fix is
  coverage from the ray's discriminant through alpha-to-coverage, or a
  2× buffer.
- **D8. The polyhedral view is a WP of its own, filed to follow this
  one.** § Polyhedra showed it fits D1 as one more pass of 88 lines, so
  nothing in this WP is built for it. The new WP carries a `polyhedra` arm
  in the payload, the ligand rule, degenerate shells, a choice of centres,
  the translucent pass and their tests. None of that is needed to leave
  plotly. The alternative folds it in here and makes D2 "the payload gains
  one arm".
  **The new WP's first deliverable is its defaults.** Most users should
  never need a polyhedron setting. Its proposal, to be measured across more
  phases than the three here:
  - *centres*: sites with a separated shell of 4 to 8 ligands, where a clear
    gap in distance follows the last ligand. That draws PO₄, AlF₆ and CaF₈
    and skips NAC's Na and LaB6's La;
  - *ligands*: non-metal neighbours of another element (§ Polyhedra);
  - *look*: the centre's colour at alpha 0.55, edges in a darker ink, the
    centre atom kept, and the centre-to-ligand sticks hidden;
  - *when*: on in ball mode when a centre qualifies, and off in ellipsoid
    mode, where translucent faces would cover the ADPs the mode exists to
    show. One toggle overrides either.

## Where it will bite

- **A WebGL context is a scarce resource.** Browsers keep about 16 live
  contexts a page and silently drop the oldest past that. The viewer keeps
  one context for its life and releases it on unmount. Today it disconnects
  its `ResizeObserver` and nothing else, and never calls `Plotly.purge`, so
  toggling the viewer may already leak a context. The spike counts contexts
  across toggles.
- **A lost context must come back.** `webglcontextlost` and
  `webglcontextrestored` rebuild the programs and buffers from the payload
  already held.
- **Only Apple GPUs have drawn it.** Chromium ran on ANGLE over Metal,
  Firefox and WebKit on the same M4, and headless Chromium on SwiftShader.
  Windows (ANGLE over D3D11) and Linux drivers have not.
- **jsdom has no WebGL.** vitest covers the pure half: the projected
  extents, the pick, the trackball and the instance data. A stand-in
  records what was asked to be drawn, as `gui/src/test-uplot.ts` does for
  uPlot. A browser test covers the drawing, and it reads back pixels or
  compares pictures, never a hash of a screenshot (`gui/CLAUDE.md`: a WebGL
  re-render differs by a pixel).
- **WebGL lines are one pixel wide.** The cell frame is thin at any zoom.
  If that reads badly, the edges become cylinder impostors at a radius set
  in pixels each frame.
- **The camera is owned outright.** The renderer keeps the camera between
  draws, so the read-back rule above goes. A redraw must still not reset
  the view, and a test says so.

## Non-goals

- **A new look,** beyond D6. The second pass's choices carry over: parallel
  projection, no axis box, cylinders in Å, a/b/c labels and the light on
  the camera.
- **New structure features:** a packing diagram, labels on atoms, the
  octant cut-out, depth cueing, ambient occlusion, animation of a
  refinement. Each is an addition on D1 and a WP of its own. Polyhedra are
  D8's.
- **WebGPU.** Firefox on Linux does not ship it yet.
- **Any other chart.** 2D charts are WP-1461's.

## Tasks

- [ ] The maintainer confirms D1-D8, and this file records which, renamed if D1 holds, with the polyhedra WP filed if D8 holds
- [ ] Spike, the gate: the prototype on the GPU paths it has not met (any Windows or Linux machine the maintainer can reach), and paired against today's plotly viewer on the same machine: first show, rotation frames and hover work per event, in Chromium, WebKit and Firefox. Record go or no-go in the handover. On no-go, draw the same payloads with three.js before stopping.
- [ ] The renderer: instanced atom and bond-half impostors, the cell frame, the a/b/c overlay, the orthographic camera, the trackball, the light on the camera, theme colours, D6's ellipses, D7's antialiasing, context loss, and release on unmount
- [ ] Interaction: hover on atoms and bond halves, legend toggles, the a/b/c and reset views, the three knobs, the view kept across redraws, `ResizeObserver` sizing, and PNG export
- [ ] Delete plotly: the trace builders, the tessellation, the camera read-back, `gui/src/lib/plotly.ts`, the `/plotly.js` route, the `gui` extra's plotly, and `viz/plotlyjs.py` if WP-1461 left it only for this viewer. `lib/plot.ts:hoverLabel` and the `Plotly` stand-in in `test-setup.ts` go with whichever of this WP and WP-1461's Series task lands second.
- [ ] Tests: `structure3d.test.ts` on the pure half and the instance data; a WebGL stand-in beside `test-uplot.ts`; a browser test that reads pixels at known atoms, finds a principal ellipse on an anisotropic site, and asserts a redraw keeps the view; a test that no page requests `/plotly.js`
- [ ] Docs: the structure viewer paragraphs in `gui/CLAUDE.md` (crystallography rules kept, plotly traps deleted), `using/install.md` for the `gui` extra, ATTRIBUTION.md, and the root CLAUDE.md's GUI lines if they name plotly. On the three.js fallback also: its row in `.github/dependabot.yml`'s allow list (WP-1461 created it) and its licence text in `LICENSE-3RD-PARTY.md`.

## Acceptance

Measured like WP-1461's § Acceptance: the spike driver ported to the real
page, paired with the plotly viewer on the same machine and load, three or
more runs for ranges, recorded in the handover.

1. **No plotly anywhere.** No page requests `/plotly.js`, the route is
   gone, and `pyproject.toml` names plotly in no extra.
2. **First show:** no long animation frame is attributed to the renderer.
   The time from the viewer's first show to its first frame is recorded
   beside plotly's.
3. **Rotation:** on the largest example structure, a trackball drag holds a
   p95 frame of 17.7 ms or less with zero long animation frames. Hover work
   per event is recorded.
4. **Size:** the renderer adds under 15 KB gzip to the GUI bundle, or
   three.js's measured size on the fallback.
5. **Coverage:** every item in § What the viewer is is present and named by
   a test.
6. **Browsers:** in Chromium, WebKit and Firefox through playwright's
   builds, the viewer draws, rotates and hovers, and nothing throws.

```sh
npm --prefix gui test && npm --prefix gui run check
.venv/bin/python -m pytest tests/test_structure3d.py tests/test_gui_server.py
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

## References

- Sigg, C., Weyrich, T., Botsch, M. & Gross, M. (2006). GPU-based
  ray-casting of quadratic surfaces. *Eurographics Symposium on
  Point-Based Graphics*.
- Gumhold, S. (2003). Splatting illuminated ellipsoids with depth
  correction. *Vision, Modeling and Visualization 2003*, 245-252.
- Tarini, M., Cignoni, P. & Montani, C. (2006). Ambient occlusion and edge
  cueing for enhancing real time molecular visualization. *IEEE Trans.
  Vis. Comput. Graph.* 12, 1237-1244.
- Johnson, C. K. (1965). ORTEP: a Fortran thermal-ellipsoid plot program.
  Report ORNL-3794, Oak Ridge National Laboratory. Burnett, M. N. &
  Johnson, C. K. (1996), ORTEP-III, ORNL-6895, for the principal ellipses
  and the octant convention.
- McGuire, M. & Bavoil, L. (2013). Weighted blended order-independent
  transparency. *Journal of Computer Graphics Techniques* 2(2).
- Rose, A. S. & Hildebrand, P. W. (2015). NGL Viewer: a web application for
  molecular visualization. *Nucleic Acids Res.* 43, W576.
- three.js 0.186.1, MIT. <https://github.com/mrdoob/three.js>
- 3Dmol.js 2.5.5, BSD-3-Clause. Rego, N. & Koes, D. (2015). 3Dmol.js:
  molecular visualization with WebGL. *Bioinformatics* 31, 1322-1324.
  <https://github.com/3dmol/3Dmol.js>
- Mol\* 5.11.0, MIT. <https://github.com/molstar/molstar>
- plotly.js, MIT, as served by the Python `plotly` 7.1.0 package.
- VESTA, Momma, K. & Izumi, F. (2011). *J. Appl. Cryst.* 44, 1272-1276.
  The viewer's second pass read its look against VESTA, Jmol and 3Dmol.js.
- WP-1015 (the viewer) and WP-1461 (every 2D chart on uPlot).
- `1462-spike/README.md`: the files and how to rerun them.

## Handover log

- **2026-09-25 (2nd session)** — scoped on the maintainer's question: which
  3D library is the uPlot of structure plotting, and can we do better than
  one. No library is. The engines cost 137-216 KB gzip, and most of that is
  a material system this viewer does not use. The thin helpers are uPlot's
  size but only wrap WebGL calls. The molecular viewers bring their own
  crystallography. What the molecular viewers do inside is the answer:
  ray-cast impostors. A 392-line prototype drew the served payload that
  way in all three engines at 4.8 KB gzip, with exact surfaces and the
  ORTEP principal ellipses the viewer has never had. D1 now recommends it,
  with three.js as the fallback. The maintainer then asked for a polyhedral
  view for solid-state chemists. The spike drew translucent coordination
  polyhedra beside the impostors in 88 more lines, so D1 stands. The hard
  part is a ligand rule on the server, and D8 gives the view a WP of its
  own. The maintainer added that good defaults are part of the design, for
  polyhedra too, so D8 now opens that WP with a proposed set. Folded the
  `### Inherited` mailbox: its Dependabot and licence
  entries went to the docs task as fallback-only, and its `hoverLabel` and
  stand-in entry went to the delete and test tasks. *Next:* the maintainer
  decides D1-D8. If D1 holds, rename this file and its ROADMAP row. If D8
  holds, file the polyhedra WP. Then run the spike gate.
- **2026-09-25** — filed from WP-1461's session, on the maintainer's
  request, once they confirmed the move to uPlot. The library sizes above
  were measured that day. Nothing else was: no scene was drawn in three.js
  or 3Dmol.js. *Next:* the maintainer confirms D1-D5, then the spike.

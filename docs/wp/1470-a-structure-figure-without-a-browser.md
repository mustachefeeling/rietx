# WP-1470 — a structure figure from Python, drawn without a browser

Milestone: unscheduled · Status: ✅ 2026-09-27 — render_structure landed; the GUI's b button keeps c up
Depends on: — (1462, 1466 shipped)

## Goal

`rietx.viz.render_structure` draws one phase of a structure to an RGBA array
or a PNG. It needs no browser, no display and no new dependency. It draws the
structure viewer's geometry with the viewer's look. It is fast enough for an
agent to call in a loop: the spike drew a 185-atom cell at 1000 px in about
0.1 s.

## Context

### Why

The maintainer asked on 2026-09-27 for agents to be able to make 3D figures
of refined structures. Today the picture exists only in the GUI. The
structure viewer draws it in the browser with its own WebGL2 renderer
(WP-1462) and exports a PNG from a button. A script can get the geometry,
`structure3d.build()`, but no picture.

### The routes, measured

`1470-spike/README.md` has every number below and the scripts that made
them.

- **Drive the GUI's renderer in headless Chromium.** The picture would match
  the GUI pixel for pixel, and `tests/test_structure3d_browser.py` shows
  SwiftShader draws the same scenes. But playwright is no dependency, a
  Chromium download is a large ask of an agent's sandbox, and no CI workflow
  installs a browser (WP-1462), so CI would never run the feature.
- **Hand the CIF to another program.** `Refinement.write_cif` writes the
  `_atom_site_aniso_` loop (`crystallography/cif.py`,
  `write_structure_block`). VESTA exports an image from its command line
  (`-export_img scale=2`), and JmolData renders headless with ellipsoids.
  This needs no rietx code and is the skill row this WP adds first. It loses
  rietx's bond rules, polyhedra and colours, and needs VESTA or Java.
- **A Python rendering library.** None is both light and correct in 3D
  without a display. matplotlib and skia-python draw in 2D, back to front,
  and the matplotlib baseline draws bonds over balls they pass behind.
  pycairo has a wheel only for Windows. moderngl and vispy need an OpenGL
  context, which headless Linux often lacks. vtk is 80-140 MB. pyrender's
  last release was 2021.
- **Our own ray-caster.** `1470-spike/spike.py` (219 lines, numba and
  `zlib`) draws NAC in 85-108 ms at 1000 px with 2×2 supersampling. The first
  render compiles, in 0.64-0.76 s. At 3000 px and 2× it takes 0.73-0.96 s,
  of which 514-521 ms is the numpy box filter, so a filter inside the kernel
  removes most of it.

This WP takes the last route.

### What exists

- **The geometry.** `src/rietx/gui/structure3d.py`'s
  `build(structure, phase, *, probability, bond_tolerance, max_atoms)`
  returns a JSON-ready dict, Cartesian in Å: `atoms` (`pos`, the 3×3
  `ellipsoid` matrix T, `rms`, `boundary`, `vertex_only`, `npd`), `sites`
  (`color`, `radius`, `aniso`, `species`, `label`), `bonds` (`i`, `j`, `a`,
  `b`), `polyhedra` (`center`, `vertices`, `faces`, `edges`, `bonds`,
  `drawn_by_default`), `lattice`, `corners`, `edges`, `scale` (k(p)) and
  `ball_fraction`. Everything chemical is decided here (root CLAUDE.md
  § GUI, `gui/CLAUDE.md` § structure viewer).
- **The scene rules**, in `gui/src/lib/structure3d.ts`. `buildScene` turns
  the geometry and the toggles into what the renderer draws: a species the
  legend hides takes its bond halves with it; a boundary image is dimmed
  (`dim`, factor 0.62); a drawn polyhedron hides its centre's sticks to its
  own vertices; a `vertex_only` atom is drawn only while one of its
  polyhedra is; a polyhedron's edges take `dim(colour, 0.5)`. `drawable`
  floors a zero semi-axis at `FLAT_AXIS` = 1 mÅ. `stickRadius` is 0.08 Å in
  ball mode and `max(0.02, min(0.08, 0.5 × smallest drawn semi-axis))` in
  ellipsoid mode. `axisLabels` puts a, b, c beyond each edge at a clearance
  of `0.35 + ball_fraction × largest radius` Å. `shownPolyhedra` turns
  polyhedra on in ball mode and off in ellipsoid mode by default.
- **The views**, in the same file. `lookFrom(eye, up)`; `openingView()` is
  `lookFrom([1.35, 1.35, 0.95], [0, 0, 1])`; `axisView` looked down a with c
  up, down b with a up, down c with b up, so the next vector was to the
  right, until D12 moved down b to c up. Projection is parallel.
- **The look**, in `gui/src/lib/gl3d.ts`. One key light fixed to the camera
  at `(-0.40, 0.55, 0.73)`; atoms and sticks take `shade = base × (0.45 +
  0.60 × diffuse) + 0.16 × spec⁴⁰`. Polyhedron faces take their own rule,
  `base × (0.45 + 0.55 × diffuse)` with no specular term. A principal ring
  is `min |uᵢ| < 0.035` in the unit frame, inked lighter on a dark atom
  (luminance < 0.33) and darker on a light one. The constants beside it
  live in `structure3d.ts`: `POLY_ALPHA` = 0.55, and line widths in CSS px,
  `CELL_WIDTH_PX` = 2 and `EDGE_WIDTH_PX` = 1.25. The cell frame takes the
  theme's `--accent`.
- **The compiled tier's rules** apply to a new kernel (root CLAUDE.md
  § compiled tier): a soft numba import with a numpy fallback that stays
  exercised; serial `njit(cache=True, nogil=True)` over a row range on the
  shared pool, never `prange`; a stated equivalence bar; one path per
  process, switched by `RIETX_COMPILED=0`.
- **The public surface.** `rietx.viz` imports matplotlib lazily and reaches
  `write_html` and `LiveSession` through `__getattr__`. A public name fails
  `tests/test_manual_api.py`'s partition until documented;
  `PROVISIONAL_MODULES` in `tests/api_surface.py` declares a module
  provisional. The plotting chapter is `docs/manual/using/exports.md`
  § Plotting the fit.
- **The parity mechanism.** Python writes a committed corpus and a vitest
  replays it: `tests/data/gui/fnmatch_cases.json` and
  `tests/data/gui/index_controls.json` (`gui/CLAUDE.md`). Python owns the
  model and the TypeScript proves it states the same.

## Decisions

Read against two surveys run on 2026-09-27: how PyMOL, ChimeraX, VMD, OVITO,
VESTA, Jmol and ASE render stills without a display, and what molecular
graphics and journals do about antialiasing, depth cues, transparency, text
and PNG metadata. Each decision says what it takes and what it declines.

- **D1. The renderer ray-casts on the CPU in numba, with a numpy fallback.**
  Atoms and bond halves are exact quadrics, the practice of Mol\*, NGL and
  the GUI (WP-1462). The numpy path works per primitive over its bounding
  box and is the oracle the kernel is measured against. The image is split
  into row bands on the shared pool, and each band draws every primitive
  that reaches it, so no two threads write one pixel.
- **D2. The geometry stays where it is.** `render_structure` calls
  `rietx.gui.structure3d.build()`. Importing `rietx.gui` costs 21-26 ms on
  top of `import rietx`'s 0.60-0.85 s (measured, `-X importtime`, four
  runs), and moving the builder would touch the server, its tests and
  `gui/CLAUDE.md` for no change in behaviour. A package boundary drawn for
  tidiness is declined.
- **D3. The scene rules are ported, and held equal to `buildScene` by a
  committed corpus.** A second copy of the scene rules and the view
  arithmetic is the risk this WP carries: 171 lines of code in eleven
  functions of `structure3d.ts`, counted without comments. The root
  CLAUDE.md's warning about a second builder applies.
  Serving the scene from the server instead would cost the GUI a round trip
  on every legend click. So Python gets `build_scene(geometry, mode, hidden,
  show_boundary, exaggeration, polyhedra)`, writes
  `tests/data/gui/scene_cases.json` over several payloads and toggles, and
  `structure3d.test.ts` replays it against `buildScene`. The constants both
  renderers draw with (the light, the shading coefficients, the ring width
  and ink rule, `POLY_ALPHA`, `FLAT_AXIS`, the stick and label rules, the
  views) are in the corpus too.
- **D4. The look is the GUI's, and shading stays in sRGB.** The survey
  recommends shading and filtering in linear light. It is declined: the
  palette's separability floor (`structure3d._oklab_distance`) was measured
  on colours shaded the way the GUI shades them, and linear light would
  change both that and the match with the GUI's picture.
- **D5. Antialiasing is supersampling with a box filter**, 2×2 by default
  and up to 4×4, with a depth test per sample. PyMOL (`antialias`) and
  Tachyon do the same. The GUI's analytic edge coverage is declined here:
  it does not compose in a z-buffer, where the surface behind an edge may
  be drawn later. The filter runs inside the kernel, band by band, so a
  3000 px 4×4 render never holds a 12000 px buffer. It rounds to the
  nearest level; the spike truncates, which darkens every filtered pixel
  by up to one level.
- **D6. Polyhedra are sorted whole, back to front.** By centroid, back
  faces then front, blended at `POLY_ALPHA` over the opaque z-buffer and
  writing no depth, as the GUI does. Coordination polyhedra share faces and
  edges but never overlap in volume (WP-1462 § Polyhedra). A centroid order
  is still not exact: it can put a large polyhedron behind a small
  neighbour that it partly covers, and the GUI has the same fault.
  Order-independent transparency (McGuire & Bavoil 2013) is declined until
  a picture shows that fault.
- **D7. The output is an array first, and a PNG on request.** The call
  returns an RGBA `uint8` array with the anchors below, so an agent
  composing a figure never reads a file back. The survey found PyMOL,
  ChimeraX, VMD and ASE writing files only. The background is opaque white
  by default, as in PyMOL and ChimeraX, and `background=None` is
  transparent. `path=` writes a PNG with `zlib`, straight alpha as the PNG
  standard has it, a `pHYs` chunk for the resolution and an `sRGB` chunk.
  On a transparent background a pixel's alpha is its opaque sample
  coverage, composited with the polyhedron faces by the over operator, and
  its colour is the mean over the samples that hit, never over the
  background. So the GUI's second render on black is not needed, and edges
  carry no white fringe. JPEG is refused, as `plot_for_vlm` refuses it.
  There is no SVG or PDF (Non-goals).
- **D8. The renderer draws its own letters, and returns where everything
  landed.** The a, b, c labels are in every picture the GUI exports, so a
  figure without them is a step back. They are drawn from a bundled subset
  of the Hershey Roman simplex font through the same line path as the cell
  frame. Its licence allows any use on two conditions: its acknowledgement
  ships with the font data, and the data is never distributed in the NTIS
  format. Atom labels are optional. The result also carries each
  atom's and each letter's position in pixels, so a caller can annotate in
  matplotlib. Pillow and FreeType are declined, being a dependency for
  three letters.
- **D9. Depth cues are optional and off by default.** A silhouette outline
  from the z-buffer's depth discontinuities gives the most legibility for
  its cost (PyMOL `ray_trace_mode 1`; Tarini, Cignoni & Montani 2006) and
  is offered as `outline=`. It is off because the GUI draws none, and an
  agent's figure should look like what the person sees in the GUI. Fog is
  declined for the same reason. Ambient occlusion is declined as a cost the
  figure does not need.
- **D10. An agent customises through data.** `render_structure` takes a
  `Structure`, or the dict `build()` returns. An agent that wants a
  different colour, a hidden site or a larger ellipsoid edits the dict and
  renders it. The keyword arguments cover what the GUI's controls cover and
  nothing more.
- **D11. The module is provisional by declaration.** Its look and its
  arguments follow the structure viewer, which WP-1468 is still changing.
  Superseded in part 2026-09-27: the declaration cannot be a
  `PROVISIONAL_MODULES` entry. That table must cover a name on the derived
  surface (`test_provisional_modules_are_live_and_reasoned`), and nothing in
  `rietx.viz` is on it: `rietx.viz` is not in `rietx.__all__`, and none of
  its functions are among the 1800 derived names. So the declaration is a
  bullet in `compatibility.md` § Provisional by declaration, which the
  manual section links.
- **D12. A view is named in crystallographic terms, and round-trips.** No
  program surveyed takes a zone axis or a plane normal. PyMOL's `set_view`
  takes 18 numbers and ChimeraX's `view matrix` 12, which an agent cannot
  write without first capturing one. OVITO's `camera_dir` and `camera_up`
  are the primitive underneath, and a direction [uvw] or a plane normal
  (hkl) converts to one through the metric. So `view=` takes `"opening"`
  (the GUI's), `"a"`, `"b"` or `"c"` (the GUI's buttons), a direction
  `[u, v, w]`, a normal `{"hkl": (h, k, l)}`, or a 3×3 rotation. `up=`
  names the direction kept up. `turn=` takes ASE's rotation string
  (`"30y,-15x"`), with ASE's signs and its rule that the order matters
  (`ase.utils.rotate`), because agents already know it from
  `ase.io.write`. `up=` defaults to the convention: c up, unless c is the
  lattice axis nearest the view direction, and then b. VESTA's standard
  orientation keeps +c up the screen, and megane's VESTA-derived axis
  buttons keep c upright for the a and b views and b for the c view, with
  the named end of the axis toward the viewer (megane PR #694,
  `cameraOrientation.ts`). The maintainer chose the convention on
  2026-09-27. The GUI's b button put a up, so it moves to c up in this WP,
  and the corpus holds the two renderers equal on all three. So down [001]
  with no `up=` is `"c"`, and the default is never parallel to the view.
  The result carries the rotation it
  drew, so passing it back as `view=` reproduces the picture. Every view is
  fitted to the frame, as ChimeraX's `view` and OVITO's `zoom_all` are, so
  a caller never chooses a camera distance. Projection is parallel. Every
  program surveyed defaults to perspective, and the GUI chose parallel
  because perspective converges a cell's far edges (`gui/CLAUDE.md`).
- **D13. Size is pixels; resolution is metadata.** `size=` is the long side
  in pixels, or `(width, height)` with the structure fitted inside.
  Supersampling is a separate knob, as in PyMOL and ChimeraX. `dpi=` only
  fills the PNG's `pHYs` chunk. The manual gives the recipe for a journal
  column. The default size suits an agent looking at its own picture, and a
  figure for print passes its size.

## Non-goals

- **Vector output.** WP-1462 D1 declined it for the GUI, and a ray-caster
  has no primitives to write. A vector export would project ellipses and
  cylinders back to front, and must solve the crossing fault the matplotlib
  baseline shows.
- **A new look for the GUI.** An outline here is an option; the GUI gaining
  one is its own WP.
- **Ambient occlusion, shadows, perspective, a packing diagram.** The
  payload's rules decide what is drawn (WP-1462 § Non-goals).
- **Magnetic moments.** When WP-1326/1327's model lands, a moment is a
  cylinder and a cone in this renderer. Not here.
- **A CLI verb.** The python API is the one integration surface (root
  CLAUDE.md, WP-1303).
- **Replacing the GUI's renderer**, or moving `build()` out of `rietx.gui`.

## Tasks

- [x] Skill: a row saying that `Refinement.write_cif` into VESTA
  (`-export_img`) or JmolData draws a refined structure today. It lands
  first and stands on its own.
- [x] `build_scene` in Python, the corpus, and the vitest that replays it
  against `buildScene` (D3). The GUI's b button moves to c up (D12).
  `npm --prefix gui test` and a rebuilt dist.
- [x] The kernel and its numpy oracle: balls, ellipsoids with rings, bond
  halves, the cell frame as lines with a width in pixels, the `FLAT_AXIS`
  floor, row bands on the shared pool, the box filter inside the kernel
  (D1, D5). State and assert the equivalence bar between the two paths.
- [x] Polyhedra: faces and edges after the opaque pass (D6).
- [x] Views (D12): the named views, `[u, v, w]`, `{"hkl": ...}`, a 3×3
  rotation, `up=`, ASE's `turn=` string; the rotation drawn carried in the
  result; always fitted to the frame. Test that a round trip reproduces the
  picture, and that down [001] on a cubic cell equals `"c"`.
- [x] Output: the array, the anchors, the PNG writer with `pHYs` and `sRGB`,
  the transparent background (D7).
- [x] Letters: the Hershey subset with its acknowledgement beside it in the
  wheel, an `ATTRIBUTION.md` row, a, b, c by default and atom labels on
  request (D8).
- [x] Options: phase, mode, probability, exaggeration, hidden species, boundary
  images, polyhedra on or off or by formula, background, size, supersampling,
  `outline=` (D9).
- [x] Public surface: `rietx.viz.render_structure` through `__getattr__`, a
  `PROVISIONAL_MODULES` entry (D11), a section in
  `docs/manual/using/exports.md`, and `examples/structure_figure.py`, which
  the manual includes and `tests/test_examples.py` runs.
- [x] Tests: a ball's silhouette radius against `r ×` pixels per Å; an
  ellipsoid's silhouette against the exact projected ellipse (the norms of
  the first two rows of R·k·T); a cubic cell viewed down c projects to a
  square; alpha zero outside the structure on a transparent background; the
  PNG chunks read back; the two paths agree to the stated bar; two renders
  are identical; a polyhedron leaves a translucent pixel; a non-positive
  tensor draws no NaN; the numpy path runs under `RIETX_COMPILED=0`.
  Pictures to `tests/output/`.
- [x] A browser parity row in `tests/test_structure3d_browser.py`: one
  scene and one view drawn by both renderers, and the mean difference
  measured. The Python side takes the GUI's framing for this row
  (`buildScene`'s orientation-free `radius`), because D12's fit to the
  frame is tighter and would otherwise be what the row measures. Set its
  bar from that measurement and say so. It skips in CI.
- [x] Skill: the entry point in the generated `api-<shape>.md`, and a
  routing row keyed by the situation "a figure of the structure".
  (Done 2026-09-27 as `api-figure.md`, the generator's first technique index.
  The situation joined the existing "writing the answer out" row, since the
  body had 52 bytes left; a 21-byte cut elsewhere in the body paid for it.)
- [x] The addition staged in the open milestone's record.

## Acceptance

- `render_structure` draws NAC in ball mode, ellipsoid mode and with
  polyhedra on, at 1000 px and 2×2, with no browser, and each picture is
  checked by looking at it.
- The handover quotes the warm render time on NAC at 1000 px and 3000 px as
  ranges, beside the spike's.
- The browser parity row passes locally at the bar its measurement set.

```sh
.venv/bin/python -m pytest tests/test_render_structure.py tests/test_structure3d.py
.venv/bin/python -m pytest tests/test_structure3d_browser.py   # local; skips without playwright
RIETX_COMPILED=0 .venv/bin/python -m pytest tests/test_render_structure.py
npm --prefix gui test && npm --prefix gui run check
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

## References

- Sigg, C., Weyrich, T., Botsch, M. & Gross, M. (2006). GPU-based
  ray-casting of quadratic surfaces. *Eurographics Symposium on
  Point-Based Graphics*. The quadric the GUI and this renderer both solve.
- Tarini, M., Cignoni, P. & Montani, C. (2006). Ambient occlusion and edge
  cueing for enhancing real time molecular visualization. *IEEE Trans.
  Vis. Comput. Graph.* 12, 1237-1244.
- McGuire, M. & Bavoil, L. (2013). Weighted blended order-independent
  transparency. *Journal of Computer Graphics Techniques* 2(2).
- Johnson, C. K. (1965). ORTEP: a Fortran thermal-ellipsoid plot program.
  Report ORNL-3794, Oak Ridge National Laboratory. Burnett, M. N. &
  Johnson, C. K. (1996), ORTEP-III, ORNL-6895.
- megane's axis views, VESTA-derived:
  <https://github.com/megane-labs/megane/pull/694>
- VESTA, Momma, K. & Izumi, F. (2011). *J. Appl. Cryst.* 44, 1272-1276. Its
  command line: <https://jp-minerals.org/vesta/en/doc/VESTAch17.html>
- Jmol headless rendering: <http://wiki.jmol.org/index.php/Jmol_Application>
- PyMOL `antialias` and `ray_trace_mode`:
  <https://pymolwiki.org/Antialias>,
  <https://wiki.pymol.org/index.php/Ray_trace_mode>
- ChimeraX `lighting`, `view` and `save`:
  <https://www.cgl.ucsf.edu/chimerax/docs/user/commands/lighting.html>,
  <https://www.cgl.ucsf.edu/chimerax/docs/user/commands/view.html>,
  <https://www.rbvi.ucsf.edu/chimerax/docs/user/commands/save.html>
- PyMOL `set_view` and `png`:
  <https://pymol.org/dokuwiki/doku.php?id=command:set_view>,
  <https://pymolwiki.org/index.php/Png>
- OVITO `Viewport`: <https://docs.ovito.org/python/modules/ovito_vis.html>
- ASE `ase.io.write` and `ase.utils.rotate`:
  <https://docs.ase-lib.org/ase/io/io.html>
- PNG, `pHYs` and `sRGB` chunks: <https://w3c.github.io/png/>
- Hershey fonts and their licence:
  <https://fedoraproject.org/wiki/Licensing:HersheyFontLicense>

## Handover log

### 2026-09-27 (3rd session) — CI

PR #498 failed on every Linux job, and the renderer was never at fault. The
check that keeps the Python and browser copies of the scene rules equal
depended on the machine that ran it, because the order of a polyhedron's
corners is decided by rounding noise. The check now compares the rules over
fixed inputs, so it holds on any machine and still catches a changed rule.
The manual and the skill also stopped offering an edit that raised. WP-1501
and WP-1502 (#501) now sit on this branch as a stacked PR.

- **Why CI saw it late.** A draft PR runs ruff alone. The fast suite first
  ran when the PR was marked ready, at 04:51:43, and that run failed. The
  green run on the same commit, 21 s earlier, was the draft's.
- **Cause.** `test_the_committed_scene_corpus_is_current` rebuilt the
  payloads and compared the file byte for byte. `structure3d.build` breaks
  ties in distance on the last bit, and rutile's octahedron is all ties.
  Four ulps of noise on the linear algebra reorder its vertices and hull
  faces, so the file depends on the platform while the picture does not.
- **Fix.** The check replays the scene rules over the committed payloads,
  which are pure python. Floats agree within 1e-10 of max(1, |v|), a tenth
  of vitest's bar. The committed file sits 5.5e-12 from its own replay. A
  new case or payload field still rewrites the file, through field names that
  16 ulps of noise leave alone on four seeds. Made to fail on purpose three
  ways, each naming where: `POLY_ALPHA` moved, the stick radius nudged 1e-8
  (below vitest's bar), and a field added. WP-1468's inherited note says
  how to refresh the payloads after a change to `build()`.
- **Siblings.** `test_gui_fnmatch.py` and `test_gui_palette.py`'s
  `tokens.css` regenerate strings from constants, so they hold on any
  platform. The scene corpus was the only float fixture compared by bytes.
- **The manual** offered "an atom removed" as a dict edit, and the skill's
  figure index "a site to leave out". Both raise (WP-1501's probe). Both now
  name a site's colour or radius, say a colour is `#rrggbb`, and say a
  deletion raises. WP-1501's `keep()` stays the route to a cut.
- **Measured.** darwin/arm64, `[dev]` venv plus `playwright`. Fast suite:
  6622 passed, 145 skipped, 3:05-3:33 over two runs, the second after the
  review's fixes, no other suite running. That is the earlier count exactly,
  since no test was added. The full suite did not
  run: no forward model, solver or statistic changed.
- **Review.** `/code-review high` over `tests/test_render_structure.py`
  found nine, and seven were taken (`8768a0fd`). A rule-only drift now
  rewrites over the committed payloads. The coverage test asks both
  monoclinic payloads for a floored axis. The PNG walk checks CRCs. The c
  view is compared to [0, 0, 1] and (001) as rotations, since c* sits 6e-17
  from c. Declined: pinning the compiled tier on the bit-identity renders,
  which another test already holds equal, and a fixture read that races a
  rewrite only when the test is already failing.
- **Stacked.** #501's branch merged this one, and #501 now targets
  `wp1470-structure-figure`. The repo does not delete a merged branch by
  itself, and GitHub retargets a stacked PR to `main` only when its base is
  deleted.

Next: merge #498 once its Linux run is green, and delete its branch so #501
retargets to `main`. If the branch stays, run `gh pr edit 501 --base main`
before merging #501. Then WP-1468 and WP-1501 are the 3D track's open work.

### 2026-09-27 (2nd session) — closed

An agent can now make a 3D figure of a refined structure from Python.
`render_structure` draws what the GUI's structure viewer draws, as an array or
a PNG, with no browser and no new dependency. It takes about 35 ms at 1000 px.
A committed test corpus keeps the two copies of the viewer's scene rules
equal. The picture sits within about one 8-bit level of the browser's on
average. The cost is that second copy: a change to how the viewer draws now
edits Python too, and a red vitest says so when it does not.

- **Done.** All thirteen tasks. The WP arrived numbered 1469, which another
  WP filed the same morning also used. Both merged unchecked, and together
  they put ROADMAP one line over its cap. So this session first repaired
  `main` in #497 (merged): this file moved to 1470 with its spike, the cap
  rose to 856, and the bijection test now refuses two WP files of one number.
- **Decisions taken.** D12's default up follows the convention, as the
  maintainer asked: c up, or b up when looking down c. VESTA's standard
  orientation sets it, and megane's VESTA-derived axis buttons keep it
  (PR #694). The GUI's `b` button moved from a-up to c-up to match, and its
  tooltip says so. D11 cannot be a `PROVISIONAL_MODULES` entry: nothing in
  `rietx.viz` is on the derived surface (0 of 1800 names), so the declaration
  is a bullet in `compatibility.md`. The skill routing row joined the
  existing "writing the answer out" row, paid for by wording cuts in the
  body, because `SKILL.md` had 52 bytes left and WP-1320 then took most of
  those.
- **Measured.** Apple M4, `[dev]` venv plus `playwright`, darwin/arm64.
  - Warm render of NAC from a `Structure`: 33-40 ms at 1000 px and 71-94 ms
    at 3000 px, 2 × 2. From a built geometry: 13-22 ms and 52-84 ms, over two
    runs of five. The spike measured 85-108 ms and 0.73-0.96 s. `build()`
    takes 19-22 ms, and 3000 px at 4 × 4 takes 239-247 ms. The first render
    in a process compiled in 1.5 s, and 0.15-0.16 s from numba's cache.
  - The kernel and the numpy oracle agree to the bit, whole and in dozens of
    bands.
  - Parity with the viewer: 1.06 levels mean difference in three runs
    (headless chromium, SwiftShader, 507 × 300 canvas), 86 % of it on edges.
    The bar is 2.0. A one-row crop misalignment scored 4.49. That was the
    first reading, until the row clipped the page at the canvas's rounded box.
  - `CANVAS_CSS_PX` is that measured 507, where it was a placeholder 600.
  - Scene corpus: 234 kB. Nudging one Python constant turned the vitest red.
  - Fast suite on this branch with current `main` merged (WP-1320
    included): 6622 passed, 145 skipped, 3:25, no other suite running. This
    branch adds 29 tests to that selection (27 in `test_render_structure.py`,
    one example, one browser row), all passes. The first fast run found one
    real failure, a positional `encoding` argument, fixed in `e239a0e1`. The
    full suite did not run: no forward model, solver or statistic changed.
  - vitest 575 passed (4 new in the scene-parity block); `svelte-check`
    clean; the manual builds under `-W`.
- **Review.** `/code-review high --fix` found nine and all were taken
  (`5ac12f77`). The notable ones: atom labels could run off the frame; an
  unknown `polyhedra=` formula switched nothing silently; `__array__` handed
  out its own buffer on `copy=True`; and bands left the pool idle at 1000 px.
  I reworded its tooltip to drop an em dash. Declined: a float `supersample`
  truncates, a negative `exaggeration` passes, and `phase=` beside a geometry
  dict is ignored. My own browser look found the outline inking the cell
  frame black, fixed in `06856541` with a guard that fails on the old order.
- **Filed elsewhere.** WP-1468 inherits what a scene-rule edit now owes.
  `gui/CLAUDE.md` names the Python twin, its cap rising by the four lines.
- **Gotchas.** The worktree guard refuses long heredocs and `&&` chains that
  end in a commit, so messages go through a scratchpad file and `git commit
  -F`. `npm --prefix gui exec` run from the repo root leaves a
  `node_modules/.vite` there. BSD `sed` ignores `\b`. An element screenshot
  of the canvas gains a row at a fractional CSS position, so the parity row
  clips the page instead.

Next: nothing owed here. Two follow-ups are worth a WP if anyone asks. A
magnetic moment drawn as a cylinder and a cone, once WP-1326/1327's model
lands (a Non-goal here). And a vector export, which D1 declines until a
picture shows the need. WP-1468's first task that changes the default picture
should re-run the parity row.

### 2026-09-27 — filed

The maintainer asked whether rietx could make 3D figures of a structure
from Python, for agents. Today only the GUI draws one, in a browser. This
session showed that a CPU ray-caster of the GUI's own geometry draws a
185-atom cell in about 0.1 s and needs no new dependency. It also showed
that the obvious alternative, matplotlib, draws bonds over atoms they pass
behind. The cost is a second copy of the GUI's scene rules, and the plan
holds the two equal with a shared test corpus. Nothing is built.

- **Done.** This file, the ROADMAP row, and `1470-spike/` with three
  scripts and their numbers.
- **Measured.** The spike's timings and the PyPI survey are in
  `1470-spike/README.md`, on an Apple M4, `[dev]` venv. No test count moved:
  the branch adds no test, and the suite did not run, since nothing under
  `src/` or `tests/` changed.
- **Research.** Two survey agents read the other programs' documentation.
  The journal resolution requirements they reported are unverified, because
  iucr.org refused the fetch. The API survey also marked these unverified:
  ChimeraX's lighting and silhouette defaults at launch, VMD's image size
  and antialiasing defaults, VESTA's default projection, Jmol's ellipsoid
  syntax, and whether pymatgen's VTK renderer works without a display.
  OVITO's documentation did not confirm what `render_image` returns. No
  decision here rests on any of them. ASE's rotation string was read from
  `ase/utils/__init__.py`, and the Hershey licence from the Fedora page.
- **Review.** `/code-review high --fix` made nine fixes, landed as one
  commit because they interleave in two files. It corrected where
  `POLY_ALPHA` and the line widths live, added the faces' own shading rule,
  made D7's transparent alpha composite the faces, quoted import time as a
  range, corrected the spike's line count, listed the scene rules the spike
  skips, added the Hershey licence's second condition, noted that the
  spike's filter truncates, and made the browser row use the GUI's framing.
  It also chose D12's default `up=`, which the maintainer should confirm. I
  restored D6's "never overlap in volume", which it had weakened to
  "rarely", and kept its point that a centroid order is still not exact.
  Declined: `spike.py` keeps its truncating filter, because its timings are
  the record; its 13 ruff style errors stay, because `docs/` is outside the
  lint command, as for the other spike folders.
- **Gotchas.** Running the spike leaves numba's `__pycache__` in
  `1470-spike/`, which git ignores. This worktree's guard refuses compound
  shell such as `awk -v` inside loops, so measure through a scratchpad
  script.

Next: the skill row first, because it helps agents today and needs nothing
else. Then D3's corpus, because every later task draws from the ported
scene. Confirm D12's default `up=` before the view task starts.

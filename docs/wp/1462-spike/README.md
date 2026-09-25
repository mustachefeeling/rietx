# WP-1462 spike

The pages and drivers that produced the numbers in
[WP-1462](../1462-the-structure-viewer-draws-with-threejs.md). Nothing here
ships or runs in the suite. The logs in `results/` are the runs the WP quotes.

## Files

| File | What it is |
|---|---|
| `viewer.js` | The prototype: the `/api/structure3d` payload drawn as ray-cast spheres, ellipsoids and cylinders in WebGL2, with no dependency. |
| `index.html` | One viewer on a page. Query: `s` (`lab6`, `nac`, `fap`), `mode` (`ball`, `ellipsoid`), `rot`, `zoom`, `ex` (exaggeration), `poly` (draw the polyhedra). It exposes `spin(n)` and `pickBench(n)` for the driver. |
| `payloads.py` | Writes `lab6.json`, `nac.json` and `fap.json` from `tests/data` through `rietx.gui.structure3d.build`, plus a `polyhedra` arm the server does not send: AlF₆ and CaF₈ in NAC, PO₄ in fluorapatite. |
| `driver.mjs` | Loads each payload in Chromium, Firefox and WebKit: time to first frame, 240 rotation frames, 2000 picks, one real hover, a screenshot. The last case is NAC with its polyhedra. |
| `shot.mjs` | One screenshot for a query string, at `DPR` (default 2). |
| `gap.py` | Every site's sorted ligand distances and the largest gap among the first 13, for D8's default shell (`results/shell_gaps.txt`). Run as `.venv/bin/python docs/wp/1462-spike/gap.py docs/wp/1462-spike`. |
| `measure.mjs` | Bundles each candidate library's likely imports with esbuild and reports minified and gzip bytes. |
| `gui_viewer.mjs` | The real GUI's viewer on a project, in one engine: screenshots, a hover sweep, a drag, both PNG exports, WebGL contexts made and lost over five toggles, any `/plotly.js` request, and every failed response. The GPU gate's probe. Port 8798. |
| `paired.mjs` | Whichever build the GUI serves, measured as a person meets it: opening the Model tab to a drawn picture, frame gaps and long frames over a drag and a hover sweep. Appends to `results/paired_<engine>_<label>.txt`. Port 8796. |
| `first_frame.mjs` | Draw calls and screenshots at three delays after the Model tab opens, which showed Firefox presenting its first frame late. Port 8797. |
| `loaf_attribution.mjs` | The script each long animation frame on opening names, with the viewer open and after a reload (Chromium). Port 8795. |
| `gl_time.mjs` | Every WebGL2 method timed over a first opening, beside that opening's long frames (Chromium). Port 8794. |

## Running it

From the repository root, with node 20.11.1:

```sh
npm --prefix docs/wp/1462-spike install
.venv/bin/python docs/wp/1462-spike/payloads.py
node docs/wp/1462-spike/measure.mjs                     # results/sizes.txt
HEADED=1 node docs/wp/1462-spike/driver.mjs             # all three engines; or chromium,webkit
HEADED=1 node docs/wp/1462-spike/shot.mjs chromium "s=nac&mode=ellipsoid&rot=0.6&zoom=2.2&ex=2.5" nac-rings.png
```

The GUI probes drive `rietx gui --scratch` on a project. The NAC example is the
one the WP quotes; build it once, anywhere outside the repository:

```sh
.venv/bin/python -c "from rietx.examples import build_example; build_example('nac', '/tmp/ex')"
HEADED=1 node docs/wp/1462-spike/gui_viewer.mjs /tmp/ex/nac.rex chromium /tmp/ex/shots
HEADED=1 node docs/wp/1462-spike/paired.mjs /tmp/ex/nac.rex firefox new 3
```

`paired.mjs` measured the plotly build by checking out the dist of commit
`040c07ce` into `src/rietx/gui/static`, running with the label `plotly`, and
checking the dist back out of `HEAD` afterwards.

`driver.mjs` binds port 8823 and `shot.mjs` port 8824. Both expect
playwright's browser builds in the playwright cache: chromium 1223, firefox
1543 and webkit 2359, which playwright-core 1.63.0 names. Without `HEADED=1`
Chromium runs headless on SwiftShader, a CPU rasteriser, and its timings
measure that. The machine was shared with other sessions, so compare runs
taken side by side and quote ranges.

The five kept screenshots are the ones the WP cites. `nac-rings.png` is NAC
at 2.5× exaggeration, and `engines-nac.png` is the same view in Chromium,
Firefox and WebKit. `lab6-dpr1-edges.png` is a 3× nearest-neighbour crop at
devicePixelRatio 1, showing the unsmoothed outlines D7 is about.
`nac-poly.png` is NAC with its polyhedra, and `engines-nac-poly.png` is that
view in the three engines.

`results/proto_run0.txt` to `proto_run2.txt` predate the polyhedra case.
`proto_run3_poly.txt` has it.

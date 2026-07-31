# WP-1029 — GUI usability: legibility, layout, colour, theming

Milestone: v1.0 · Status: 🔄 landed 2026-07-30, **reopened** the same day
(items p, q, r, then s and t — see the handover log; two are regressions from
the first pass). **(s) done 2026-07-31**; p, q, r, t open.
Depends on: 1010–1015 (all landed) · soft: 1016, 1017

## Goal

Fifteen items, all from use. The GUI stops being a collection of correct panels
and becomes one program a
person can read: panes the user can size, controls that look like each other,
fields that line up, a structure view whose atoms are told apart by colour and
by shading, a plot whose points are visible and whose residual can be asked a
different question, and a dark mode that is dark everywhere.

## Context

**Every item here came from the user driving the shipped GUI on 2026-07-30**,
after WP-1015's second pass. None of it was found by reading code, and almost
none of it is a correctness bug — which is the reason it needs its own WP rather
than a line in someone else's: each item is cheap, none is urgent, and together
they are the difference between a tool that works and a tool that is used.

The evidence is one screenshot of the Model pane at a 1000 px window, which
shows nine of the fifteen items at once. Reproduce it with:

```sh
.venv/bin/pxrdref gui <project>.pxrd --port 8760 --no-open
# then Model, at a ~1000 px wide window
```

### The fifteen items, with what is already known about each

**(a) The 3D scene is flat, and overlapping atoms and bonds merge.**
`LIGHTING` in `gui/src/lib/structure3d.ts` is `ambient 0.75, diffuse 0.55,
specular 0.08` — set that way *deliberately* by WP-1015's second pass, because
plotly's `lightposition` is a fixed point in **data** space and the panel does
not redraw during a drag, so a camera-following light would go stale and leave
the far side black. Raising ambient bought "never black" at the cost of every
depth cue.

That trade is now avoidable, and this is the one item where a landed change
opens a door: **the panel already reads the live camera on every draw**
(`liveCamera()`, added when `plotly_relayout` turned out never to fire). So
`lightposition` can be recomputed from the camera at each `react` for free. It
still will not follow a drag — but a drag is exactly the interaction that
supplies its own depth cue by moving, and every *redraw* would then be lit from
over the viewer's shoulder. Expect to restore diffuse and some specular once
the light points the right way.

Do not stop at the light. Overlapping same-colour spheres merge because they
have no boundary; the options worth measuring are a darker rim (a second,
slightly larger mesh drawn back-face-only is not available in plotly — but
`contour` on `mesh3d`, or a per-species colour that is darkened for images
outside the cell, are), and simply drawing the stick joint smaller than the
ball. Judge by screenshot, on NAC, at a 1000 px column.

**(b) The element colours are not distinguishable inside a phase.** Measured
from the live table (`_CPK` and the golden-angle fallback in
`src/pxrdref/gui/structure3d.py`):

| | | |
|---|---|---|
| F `#48d860` | Ca `#40c060` | both mid-greens, **and both are in NAC** |
| Si `#5cbc64` | Cl `#28c828` | two more greens, one derived, one CPK |
| Na `#8040e0` | La `#995cbc` | two purples |
| Ti `#909090` | *unknown element* `#909090` | **exactly equal** — an unparseable species is drawn as titanium |

Three separate defects: CPK-convention colours chosen here that sit too close
together, a golden-angle-in-Z fallback that lands on colours the table already
uses, and a fallback grey that collides with a real element.

The rule that fixes it durably: **distinguishability is a property of the set
being drawn, not of the element table.** The server knows the phase's species
list, so it can enforce a minimum perceptual separation among *those* colours
while keeping the famous anchors (O red, N blue, C dark, S yellow) fixed.
Keep CLAUDE.md's licensing fence in view — the colours are the CPK
*convention* with values chosen here, never transcribed from Jmol/VESTA/PyMOL
(ATTRIBUTION.md records this). A perceptual distance needs a colour space that
has one; sRGB does not. The `dataviz` skill's palette guidance and its contrast
validator are the right tool for choosing the replacements.

**(c) "The NAC refinement just doesn't refine" — answered, and it is not a
bug here.** The `nac.pxrd` used for the WP-1015 browser checks pairs the **NAC
structure with a synthetic LaB6 pattern** (`tests/test_refine_synthetic.py`
`synthesize()` makes LaB6; the scratchpad script that built the project says in
its own docstring that the pattern is irrelevant *for a viewer check*). There
is nothing there to fit.

What is worth carrying forward is what the GUI said about it. Measured: the run
completes all five stages in 3.6 s and reports **`status: "converged"` at
Rwp = 96.3 %, GoF 18.4**, and the header renders a calm `converged` pill beside
those numbers. That is WP-1028's finding (`status = "converged"` at
Rwp = 7 225 %) reproduced in miniature — **the vocabulary is 1028's to fix, not
this WP's**. What *is* this WP's: the shell should not present a hopeless fit in
the same visual register as a good one, and FitReport Layer 0 already computes
the statement that would explain it (peaks with no reflection under them). One
task below, deliberately narrow.

**(d) Panels are not resizable.** Measured column widths of the Model pane's
three equal-flex columns: 463/464/573 px at a 1500 px window, 370/371/458 at
1200, 309/310/381 at 1000, 266/267/327 at 860. The structure column is the one
that breaks first (its atom table is the widest content), and the 3D column is
the one the user cannot make bigger when they want to look at the structure.

**There is already a precedent to copy, not invent**: `gui/src/panels/Console.svelte`
implements drag-to-resize with the rule "the component reports a new height and
never writes one", persisted through `ProjectDoc.ui` (WP-1005: settings persist
on the verb, not on save). Extract that into one splitter component and use it
for the plot/sidebar split and the Model pane's columns.

**(e) Labels and fields do not line up.** Visible in the screenshot: the Cell
block's two-column grid wraps `a b` / `c alpha beta` / `gamma`; the atoms table
truncates `X Y Z`; header casing is inconsistent (`LABEL` `SPECIES` `X Y Z`
against `moves along`); `U^ij patterns` wraps its basis matrices into a jumble.
This is one careful pass over `Model.svelte`, `Params.svelte` and `Plan.svelte`,
not a redesign.

**(f) The pattern's points are too small.** `gui/src/panels/Plot.svelte:85`,
`marker: { size: 2.5 }`. Note the interaction with WP-1010's decimation rule
before changing it: the *server* decides how many points cross the wire
(`/api/result/window` through `viz.compare.decimation_index`), so point size and
point count are two different knobs and only one of them is here.

**(g) Residual kinds and scalings.** Today `Plot.svelte` draws exactly one
residual — `delta` on `y2`. Wanted: at least Δ, Δ/σ (the weighted residual the
fit actually minimises) and cumulative χ², plus a y-scaling choice (linear /
√ / log) for the pattern itself. **Δ/σ needs σ, which `/api/result/window` does
not currently send** — so this item has a server half. Check `viz/` first: the
report and comparison plots already make some of these choices, and a
disagreement between the GUI's residual and the PNG's residual would be a second
authority on the same picture.

**(h) A light/dark toggle.** `gui/src/app.css` themes by CSS custom properties
under `@media (prefers-color-scheme: dark)` only — the system decides and the
user cannot. Wanted: an explicit three-way (system / light / dark), persisted in
`ProjectDoc.ui` like every other GUI setting. Keep the variables as the single
source of colour: no component should learn a hex value it could read from
`--fg`.

**(i) CodeMirror's gutter is bright white in dark mode.** `gui/src/lib/editor.ts:160`
sets an `EditorView.theme` with only `height`, `fontSize` and `fontFamily`, so
the library's default light gutter survives into a dark page. Fix by theming the
gutter, selection, cursor and active line from the same custom properties, and
setting `dark: true` when the resolved theme is dark. WP-1013's rule still
holds: the highlighter may not invent a vocabulary, but colours are not
vocabulary.

**(j) One top-level selector: `[ plot | model | text ]`.** Today `App.svelte`
has `mode: "panes" | "text" | "model"` driven by two toggle buttons in the
header, and leaving a mode is a `Close` button inside the pane — so there are
two different controls for one choice and no button named for where you land.
**This is not a re-litigation of WP-1013**, which decided that Model and Text
are *modes over the whole window* rather than a sixth tab; that decision stands
and this item is about the control that selects them looking like one control.
The five-wide strip (Parameters/Plan/Report/History/Build) stays what it is: the
sidebar's tabs *within* the plot mode.

**(k) UI-element consistency.** In one header row today: two toggle buttons, a
segmented Simple/Advanced pair, a status pill, a primary Run, a secondary
Cancel and a `⌘K` chip — six visual registers. Settle a small set (primary /
secondary / toggle / segmented / pill) in `app.css` and apply it.

**(l) The cell belongs on one row.** `Model.svelte:629` iterates
`a b c alpha beta gamma` into a two-column grid, which wraps into three ragged
rows. Crystallography writes a cell as one row of six; so should this. Watch the
held/tied cases while doing it — a symmetry-fixed angle renders as fixed text,
not an input, so the row has to align mixed content (see `editableValue`).

**(m) The 3D view wants more controls, and fewer of them on screen.** Today
`Structure3D.svelte` shows every knob it has, all the time: mode, phase,
probability, bond threshold, boundary images, four view buttons — under a plot
that is 300 px tall in a column that is 380 px wide. Wanted: more parameters
exposed (ball scale, stick radius, sphere quality, and whatever item (a)'s
shading pass adds) but folded into a menu, with only mode and the view buttons
left in the open.

Two rules already settled decide where each new knob lives. WP-1015's: these are
**drawing thresholds, not facts about the sample**, so none of them enters
`ProjectDoc` — storing one would make a picture the project's opinion. And the
existing split between server and client: **the server owns anything that
changes the payload** (the bond threshold changes which bonds *exist*, so it is
a round trip), **the client owns anything that only changes drawing** (ball
scale, stick radius, sphere quality are multiplications on geometry already in
hand). Note that `BALL_FRACTION` currently sits server-side purely so the
caption can quote it, while `STICK_RADIUS` sits client-side — if both become
controls they should stop disagreeing about where they live. Reuse WP-1011's
Simple/Advanced disclosure rather than inventing a second kind of menu.

**(n) The bond slider's number does not follow the drag.** Deliberate, and
half-right: `Structure3D.svelte` binds `onchange`, not `oninput`, because every
change is a **server** round trip and one fetch per pixel would be a flood. But
the *label* is not the fetch. Split them — the displayed value follows `oninput`
so you can see where it will land, the fetch stays on `onchange`. The mount test
must assert both halves, since the bug is precisely that the cheap one was tied
to the expensive one.

**(o) Ellipsoids are too small to read, and the sticks are part of why.**
Measured on NAC at the default 50 % (k = √χ²₃(0.5) = 1.5382), against the 0.08 Å
stick radius:

| site | Biso | semi-axes at 50 % |
|---|---|---|
| Al1 | 0.592 | 0.130 – 0.135 Å |
| Ca1 | 0.650 | 0.136 – 0.147 Å |
| F3 | 0.821 | 0.146 – 0.177 Å |
| Na1 | 2.156 | 0.152 – 0.292 Å |

So the smallest ellipsoid is **1.6× the stick radius** — the sticks are nearly
as thick as the atoms, which is exactly the "tiny and hidden" complaint. Below
**k ≈ 0.95** the smallest semi-axis is *inside* the stick, and the shipped 10 %
level (k = 0.764) is already there.

Half of that is a defect from WP-1015's scene pass and should be fixed as one:
the justification written into `unitCylinder`'s docstring — that a cylinder may
be uncapped because "the far end is buried inside its own atom, whose ball is
larger than the stick for every element there is" — is true in **ball** mode and
overclaims in ellipsoid mode, where an atom's size comes from √U·k(p) and not
from a covalent radius. The stick has to know which mode it is drawn in.

The other half is the request for a maximum above 100 %, and it needs a
distinction rather than a bigger number. **A probability cannot exceed 1**:
k(p) = √χ²₃(p) diverges as p → 1, and `probability_scale(1.0)` raises (pinned by
test). "Bigger so I can see it" is therefore an **exaggeration factor**, not a
probability, and has to be labelled as one — an ORTEP figure quotes a
probability because the surface *means* something, so a viewer that silently
drew 1.5·k(0.5) under a "50 %" label would be claiming a surface it is not
drawing. Add an explicit scale multiplier, keep the probability selector as the
probability, and make `caption()` state both whenever the multiplier is not 1.

### Inherited

From **WP-1015** (structure viewer + its scene pass, 2026-07-30): the panel now
reads the live gl3d camera before every redraw
(`Structure3D.svelte:liveCamera()`), because `plotly_relayout` **never fires for
a gl3d camera drag** — measured against plotly 6.9.0, zero events, and true of
the build before the fix too. Two consequences here: item (a)'s
camera-following light is newly cheap, and any future "did the view survive?"
check must compare screenshots (never a hash of one — a WebGL re-render differs
by a pixel) and never read `layout.scene.camera` back, which reports whatever
was passed *in*.

Also from WP-1015: `LIGHTING`/`LIGHT_POSITION` and `STICK_RADIUS` are single
exported constants in `lib/structure3d.ts`, and `BALL_FRACTION` (0.40) is
server-side with a test pinning it above the stick radius for hydrogen — item
(a) should move the constants, not fork them.

From **WP-1010** (frontend scaffold): the built dist under
`src/pxrdref/gui/static` is **committed**, so every commit that touches `gui/`
must end with `npm --prefix gui run build`; `tests/test_gui_dist.py` recomputes
the digest over `gui/src/**/*` (test files included) and fails on a stale dist.
The client does **not** decimate, and plotly is **not** vendored.

From **WP-1005** (project format): GUI settings live in `ProjectDoc.ui` and
persist **on the verb**, not on save — a theme choice or a pane width follows
that rule, and nothing here should add a save prompt.

From **WP-1028** (robustness on data we did not author): `status = "converged"`
at an absurd Rwp is *that* WP's item. Item (c) here must not fix the vocabulary
independently, or the two will disagree.

## Non-goals

- **Not a redesign.** Every item is a repair to something that exists. If an
  item argues for a new panel, it belongs in a new WP.
- **Not the manual.** Explaining the controls is WP-1017; this WP changes what
  there is to explain, so land it *before* 1017 writes the chapter, and put
  anything 1017 must say into its `### Inherited` on sign-off.
- **Not the series panel** (WP-1016) and **not the peak picker** (WP-1027),
  even though both will want the splitter from item (d) — export it, do not
  build panels for them.
- **Not the `converged` vocabulary** (WP-1028), see item (c).
- **Not a new 3D dependency.** WP-1015's "zero new dependencies" holds; the
  3Dmol.js escalation note is still not v1.

## Tasks

- [x] **Splitter.** Extract `Console.svelte`'s drag-resize into one component
      (report-a-size, never write-a-size); apply to the plot/sidebar split and
      the Model pane's three columns; persist in `ProjectDoc.ui`. (d)
- [x] **Theme.** Three-way system/light/dark in `ProjectDoc.ui`, driven entirely
      by the custom properties; theme CodeMirror's gutter/selection/cursor from
      the same variables. (h), (i)
- [x] **One selector.** `[ plot | model | text ]` as a single segmented control;
      settle the button registers in `app.css` and apply them across the header
      and panel headers. (j), (k)
- [x] **Alignment pass** over `Model.svelte` (cell on one row of six, atoms
      table that does not truncate, ADP basis rows that do not wrap into a
      jumble), then `Params.svelte`/`Plan.svelte`. (e), (l)
- [x] **Plot.** Point size; residual selector (Δ, Δ/σ, cumulative χ²) with the
      σ the weighted form needs added to `/api/result/window`; pattern y-scaling
      (linear / √ / log) — reusing `viz/`'s choices rather than inventing a
      second set. (f), (g)
- [x] **Colour.** A per-phase separation pass over the element colours, anchors
      kept, fallback grey no longer equal to titanium; a test that asserts a
      minimum perceptual distance across the species of every phase in
      `tests/data`. (b)
- [x] **Shading.** `lightposition` from the live camera at each draw, diffuse
      and specular restored, and whatever second cue survives a screenshot
      comparison on NAC at a 1000 px column. (a)
- [x] **Viewer controls.** A disclosure menu holding the drawing thresholds and
      the new ball/stick/quality knobs, with mode and the view buttons left in
      the open; the server/client ownership split written down where the knobs
      are declared; the bond slider's label following `oninput` while its fetch
      stays on `onchange`. (m), (n)
- [x] **Ellipsoid size.** An exaggeration factor that is named one and never
      folded into the probability label (`caption()` states both), and a stick
      radius that knows which mode it is drawn in — with `unitCylinder`'s
      docstring corrected, since its justification for going uncapped holds only
      in ball mode. (o)
- [x] **One honest signal** that a fit is hopeless — Layer 0 already computes
      it — without touching the `status` vocabulary WP-1028 owns. (c)
- [x] Tests: vitest for every pure function added; a jsdom mount test per
      control; the colour-distance test above. Note that jsdom has no layout, so
      the splitter's *behaviour* is testable and its *effect* is not — the
      screenshot is the check.

### Second pass (reopened 2026-07-30)

- [ ] **(p) The 3D scene.** `lightposition` is inert on plotly.js 3.7.0
      (measured, six pairs pixel-identical), so item (a)'s camera light does
      nothing and only its `LIGHTING` change is visible — shadow-side luminance
      85 → 48. Find a depth cue that works, correct the three places that claim
      the light follows the camera, and judge by screenshot on NAC.
- [ ] **(q) Repaint both plots on a theme change** — the theme is in neither
      draw effect's dependencies, so `getComputedStyle` colours sampled at draw
      time go stale and the text ends up light grey on white. While there, take
      `Plot.svelte`'s five fixed hex curve colours onto the custom properties.
- [x] **(s) Two authorities on the weighted residual — it was five.** Done
      2026-07-31. `√max(y,1)` was open-coded in `viz/plots.py` **twice**
      (`plot_result`, `plot_for_vlm`), `viz/html.py`, `report/layer0.py` and
      `gui/session.py`, under **three** different policies: the four
      result-readers took `result.sigma` raw with no zero guard, `result_window`
      guarded σ ≤ 0 → 1.0 but had no fallback at all, and `PatternData.sig()` —
      the one the *fit* uses — floors against a median-relative value. Unified on
      a new **`RefinementResult.sig()`**, a peer of `PatternData.sig()`; all five
      call it, so the three drawers agree by construction rather than by luck.
      Pinned by `test_the_weighted_residual_has_exactly_one_authority`, which
      compares what matplotlib **drew** and what plotly **drew** against what the
      route **sent** (a test that recomputed the residual would pass while all
      three were wrong).

      **The fallback divergence this item was written about is not what was
      wrong.** It is unreachable: `CompiledModel.sigma` *is* `PatternData.sig()`
      and `refine` stores it verbatim, so `result.sigma` is never empty for
      anything built since v0.2 — the branches disagreed only on legacy results.
      The live bug was one line up. `weighted` was `bool(res.sigma)`, which asks
      "is this a *pre-v0.2* result", so it was **pinned true**: the flag was a
      constant, `lib/plot.ts`'s no-esd branch was dead code, and a Poisson fit
      had its axis labelled `(obs−calc)/σ` with nothing saying the σ was an
      assumption. `weighted` is now `DataRef.has_sigma` — the same fact the text
      document already renders as "σ from file" — `delta` is *always* Δ/σ, and
      the flag changes only the axis title (`(obs−calc)/σ (Poisson σ)`). That is
      also the honest reading: the fit minimised Δ/σ_Poisson, so Δ/σ is exactly
      the curve the Δ/σ button promises, and dropping to raw Δ there was the
      wrong repair.
      *This WP's own charter told it to check `viz/` first and it did not.*
- [ ] **(t) One unidentified test flake, seen once and never reproduced.**
      Fast suite (`-n auto --dist loadgroup`) reported `1 failed, 1198 passed,
      108 skipped in 45.08s` on 2026-07-30; the immediate re-run gave `1199
      passed, 108 skipped` — the same 1199 non-skipped tests, so one of them is
      order- or timing-dependent. **The identity is lost**: the run was piped
      through a `grep` that kept only the summary line and discarded the
      `FAILED` line. Five consecutive runs of `tests/test_gui_server.py` (the
      threaded suite, the obvious suspect) are clean, the full suite is green at
      1268/117, and Linux CI is green — so it is unreproduced, **not
      explained**. If it recurs, capture the whole output before filtering.

- [ ] **(r) `RefinementResult` curves.** Nothing is persisted already; the cost
      is 9.6 MB of `list[float]` where numpy fp64 would be 2.38 MB. Decide
      between the cheap win (array-backed fields) and the fuller one (`y_calc`
      by `replay` for any node but the live one), knowing the as-optimised /
      as-replayed gap. Field types are a WP-1003 freeze question.

## Acceptance

```sh
npm --prefix gui test && npm --prefix gui run check
.venv/bin/python -m pytest tests/test_gui_server.py tests/test_structure3d.py -q
.venv/bin/python -m ruff check src tests examples
npm --prefix gui run build && .venv/bin/python -m pytest tests/test_gui_dist.py -q
```

And the part no suite covers, in WP-1015's words: **look at it in a real
browser**, in both themes, at 1500 px and at 1000 px. The bar for each item is
the screenshot that prompted it, taken again.

## References

- The CPK colour convention (values chosen here, never transcribed —
  ATTRIBUTION.md, and CLAUDE.md's Licensing invariant).
- `gui/src/panels/Console.svelte` — the drag-resize precedent.
- `viz/` — the residual and scaling choices the PNG exports already make.

## Handover log

- **2026-07-30** — created from a user's list after driving the shipped GUI,
  then extended the same day with three more (m, n, o). Nothing is started.
  Four things were measured while writing it and should not be re-measured: the
  Model pane's column widths at four window sizes (item d), the four colour
  collisions including Ti against the unknown-element grey (item b), NAC's
  ellipsoid semi-axes against the stick radius — smallest 0.130 Å against
  0.08 Å, and inside the stick below k ≈ 0.95, which the shipped 10 % level
  already is (item o) — and the NAC "does not refine" report, which *does* run,
  five stages in 3.6 s, `converged` at Rwp 96.3 %, the cause being that the
  scratchpad project pairs the NAC structure with a synthetic **LaB6** pattern
  (item c).

  Suggested order is the task list's: splitter and theme first, because they are
  structural and everything else is read against them; colour and shading last,
  because they are the two that need a browser to judge and the rest can be
  judged in a diff. Two items carry a decision rather than a repair and are
  worth doing deliberately: (m)'s server/client ownership split for the drawing
  knobs, and (o)'s insistence that an exaggeration factor is not a probability —
  get that one wrong and the picture claims a surface it is not drawing.

- **2026-07-30 (later) — landed. All fifteen items, in the suggested order.**

  **Done.** Ten commits, one per task-list row plus a browser pass:

  - `lib/resize.ts` + `panels/Splitter.svelte` — Console's drag extracted, not
    reinvented, carrying its rule generalised (**report a size, never write
    one**; `onsize(size, done)` is what keeps a drag from POSTing per pixel).
    Applied to the plot/sidebar split and the Model pane's columns. (d)
  - `lib/theme.ts` — three-way system/light/dark in `ProjectDoc.ui`, resolved
    once and stamped as `data-theme` on the root; CodeMirror's chrome moved
    into `editorTheme()` behind a `Compartment`. (h, i)
  - One segmented `[ Plot | Model | Text ]`, the in-pane `Close` buttons
    deleted, and five control registers settled in `app.css`. (j, k)
  - Alignment pass: cell on one row of six with α β γ, atoms table that does
    not truncate, DOF/ADP patterns as grids, a stage's four knobs as four
    columns. (e, l)
  - `lib/plot.ts` + a server half — points 2.5 → 4 px, three residuals,
    three intensity scalings. (f, g)
  - `phase_palette` in OKLab. (b)
  - `lightPosition` from the live camera; boundary images dimmed. (a)
  - Drawing knobs behind a disclosure; the bond slider's label on `oninput`
    and its fetch still on `onchange`. (m, n)
  - `stickRadius(geometry, mode, exaggeration)` and an exaggeration factor that
    is named one. (o)
  - `GET /api/result` → a `maturity` arm quoting `MATURITY_MAX_RWP`. (c)

  **Four decisions worth carrying, none of them in the charter.**

  1. **A stored size must be clamped where it is *rendered*, not only where it
     was dragged.** A drag clamps against the extent it happens in; nothing
     clamps a width that outlives its window. Found in Chrome: widths chosen at
     1500 px reopened at 1000 px left the 3D column **24 px** wide. The sidebar
     covers this with a CSS `max-width`; a row of N sized columns cannot express
     that, so `fitColumns` is the guard as arithmetic, shrinking proportionally
     because the *relative* choice is what is still worth keeping.
  2. **Distinguishability is a property of the set being drawn.** `_CPK` stays
     an element table; `phase_palette` decides what a *picture* uses, anchoring
     the famous assignments and rotating the rest in OKLab hue. Placement order
     (anchors → table → derived) is what decides which of a colliding pair
     moves, and it should be the hue nobody chose.
  3. **An exaggeration is not a probability.** k(p) = √χ²₃(p) diverges as p → 1,
     so there is no "150 % ellipsoid"; the caption states both figures and names
     the second one. Get this wrong and the picture claims a surface it is not
     drawing.
  4. **The report already owns the judgement "this is not a fit."** Item (c)
     added no vocabulary: `maturity` quotes `MATURITY_MAX_RWP`, and `status`
     still reads `converged` at Rwp 96 %, which stays WP-1028's.

  **Measured, in Chrome for Testing against a real project** — COD 1000236
  (NAC, aniso) + `11BM_NAC.fxye`, which refines to **Rwp 13.374 %, GoF 3.749**:

  | | |
  |---|---|
  | boot-to-interactive | 198–385 ms over six sessions |
  | model columns, 1500 px | 627 / 393 / 470 (dragged), 455 / 285 / 250 at 1000 px |
  | CodeMirror gutter | `#ffffff` light, `#1e1e1e` dark |
  | NAC's four species | Ca `#00c4b8`, Al `#bc5c70`, Na `#8040e0`, F `#48d860` |
  | stick radius | 0.080 Å ball · 0.065 Å at p = 0.5 · **0.032 Å at p = 0.1** |
  | colour separation | F/Ca 0.070 → 0.141, Si/Cl 0.078 → 0.132, Na/La 0.099 → 0.131 |

  Python fast suite 1193 → **1198 passed / 108 skipped** (77.96 s), collected
  1298 → 1304 — **both figures moved by exactly six**, and the one new skip is
  the pdCIF the new per-CIF colour test cannot read as a structure. vitest
  221 → **255**. `app.js` 164.3 → 174.0 kB (59.2 kB gzip).

  **A real browser found four more, for the sixth session running, and two were
  mine.** The plot's canvas swallowed the clicks of the knobs this WP put under
  it — WP-1015's `responsive: true` finding in a new place, and playwright
  reported it in the defect's own words (`<rect class="sdrag drag"> … intercepts
  pointer events`). The stored-column bug above. Plus two that predate this WP:
  the parameter table listed five rows called `0`, `1`, `2`, `3` and `occ`
  (a bare-index leaf says nothing), and the shared 2θ axis was anchored to the
  upper subplot so its title was drawn *inside* the residual plot — invisible
  against a flat Δ and unmissable across a cumulative χ².

  **Method note, and it cost two wrong measurements.** Playwright's viewport
  option is `newContext({ viewport })`, **not** `viewportSize` — which is
  silently ignored, so a run that claims 1500 px and 1000 px is a run at the
  default 1280 px twice. Every column width quoted above was re-measured after
  that was found. Second: the drive script waited for a stage-name regex that
  did not include `zero`, so it raced a still-running fit and its theme change
  was 409'd; the screenshots said "dark mode is broken" when the page was
  correctly light. **When a browser check disagrees with a unit test, suspect
  the harness before the code.**

  **Not done, deliberately — one finding, recorded rather than fixed.** While a
  run is in flight, changing the theme applies locally and is **refused
  persistence with a 409** (measured), because `POST /api/project` is a mutating
  verb under WP-1008's blanket rule. Two things are wrong with that and neither
  is this WP's to settle unilaterally: a `ui` key is not model state, and the
  refusal message says "this verb would change the model a compiled stage was
  built from", which is untrue of a theme. The fix is a rule — *a `ui`-only
  patch is not model state* — and it changes what a settled route refuses, so it
  is filed in [1003](1003-api-freeze-pypi.md)'s `### Inherited` as a freeze
  question rather than taken here.

  **Next**: nothing on this WP. [1017](1017-gui-manual-onboarding.md) has been
  told what changed under it.

- **2026-07-30 (reopened, same evening) — three items from the user driving the
  landed build. Two are regressions from the work above; nothing is started.**

  Same provenance as the WP itself: found by *use*, not by reading. Everything
  below is measured, so the next session should not re-measure it.

  **(p) `lightposition` does nothing, so item (a)'s mechanism is inert and its
  side effect is the whole visible change.** Reported as "3D colours not
  rendering properly, desaturated/dark and flat", and that is exactly right.

  Measured three ways:

  - In the app, with the camera light against the old fixed `(1e5, 1e5, 1e5)`:
    **pixel-identical** renders (mean |Δ| = 0.000 over the plot area).
  - In isolation — one `mesh3d` sphere, one camera down −y, `Plotly.newPlot`
    fresh each time so nothing can be blamed on `restyle` — four light
    positions spanning ±x at two magnitudes (1e5 and 3 scene units) are **all
    six pairs pixel-identical**. A light from the left and a light from the
    right light a sphere the same way, which no working renderer does.
  - The light *is* computed and *is* on the trace: read off the shipped build,
    `lightposition = (11543, 63418, 76452)`, which matches the hand arithmetic
    for `camera.eye = (1.35, 1.35, 0.95)` to four figures. So `lightPosition()`
    is correct and ignored.

  What therefore changed the picture is only `LIGHTING`, and it changed it for
  the worse in the direction reported. Measured on the NAC scene, WP-1015's
  `ambient 0.75 / diffuse 0.55` against WP-1029's `0.42 / 0.88`:

  | | mean L | 5th pct | 95th pct | contrast | saturation |
  |---|---|---|---|---|---|
  | WP-1015 | 233.7 | **85** | 251 | 166 | 0.090 |
  | WP-1029 | 229.3 | **48** | 251 | 203 | 0.089 |

  The shadow side dropped 85 → 48 (−44 %, exactly the ambient ratio) while the
  lit side did not move, so "dark" is confirmed and "desaturated" follows from
  it — HSV saturation is unchanged to three decimals, and a darker colour of the
  same saturation simply reads as less saturated. "Flat" is the one the numbers
  seem to contradict (contrast went *up*), and the explanation is the inert
  light: after any rotation the scene is still lit from wherever it was lit
  before, so the shading stops corresponding to the view.

  **Do not just restore the old constants.** That returns the WP-1015 trade
  (never-black bought with no depth cue) and leaves the docstrings this WP
  committed asserting a mechanism that does not work. The honest options, in the
  order worth trying: find whether plotly.js exposes any working light control
  for `mesh3d` (`flatshading`, vertex colours per face, or a second dimmed mesh
  as a rim); if not, **get the depth cue from something other than the light** —
  per-vertex `intensity` with a colorscale is a real option, since a viewer can
  shade by depth along the view axis itself, which is a cue that *does* follow
  the camera. Whatever lands, the ROADMAP paragraph, CLAUDE.md's bullet and
  `lib/structure3d.ts`'s `LIGHTING` docstring all currently claim the camera
  light works and must be corrected in the same change.

  **(q) The plots do not repaint on a theme change**, so their text keeps the
  old theme's colour — light grey on white, invisible, which is what was
  reported. Diagnosed by reading, no browser needed: `Plot.svelte`'s draw
  `$effect` depends on `plotKey`, `zoom`, `kind` and `scale`, and
  `Structure3D.svelte`'s on `geo`, `mode`, `hidden`, `showBoundary`,
  `exaggeration` and `view` — **the theme is in neither**, while both sample
  `getComputedStyle(...).color` (and the viewer, `--accent` for the cell frame)
  *at draw time*. Before this WP the theme could only change by the OS changing
  it mid-session, so the staleness was unreachable; the toggle made it a
  one-click bug. The fix is to make the resolved theme a prop of both panels and
  a dependency of both draw effects — the same shape as `Text.svelte`'s
  `setTheme` `$effect`, which was done correctly. Note the second half while
  there: `Plot.svelte`'s `COLORS` are five fixed hexes (`obs: "#8a8a8a"`) rather
  than custom properties, so even a correct repaint leaves the *curves* off the
  palette; `--fg`/`--muted`/`--accent` are what everything else reads.

  **(r) Should `y_calc` be recomputed rather than stored?** — the user's
  question, and the measurements say the premise is half true already.

  - **Nothing is persisted.** A `RefinementResult` never reaches disk: the
    `.pxrd/` directory is `project.json` + the pattern file + `history.jsonl` +
    `live/events.jsonl`, and history nodes have stored **state, not curves**
    since v0.2 for exactly this reason (a node is ~10 kB; embedding `y_calc`
    would make it ~1.24 MB). Measured on the NAC project: 3.5 MB on disk, of
    which the 59 498-point pattern file is nearly all.
  - **The cost is memory, and it is worse than array-sized.** The five fields
    are `list[float]`, not arrays: for 59 498 points that is **9.6 MB**, against
    2.38 MB for the same numbers as numpy fp64 — a 4× overhead paid in Python
    float objects. *That* is the cheapest win available and it needs no
    recomputation at all.
  - **Two of the five are already duplicates**: `two_theta`, `y_obs` and `sigma`
    are the pattern file, which the project stores byte-for-byte anyway.
    `y_calc` and `y_background` are the only ones that are genuinely derived —
    and `refine.replay` already recomputes a node evaluate-only, so the
    machinery exists.
  - **The known trap, already documented**: cached metrics are *as-optimised*,
    frozen at the values each stage **started** from, while `replay` recompiles
    at the values it **ended** on — so a recomputed curve can differ marginally
    from the stored one. CLAUDE.md calls that gap "a staleness signal, not a
    bug", which is fine for a diagnostic and is *not* fine if a plot silently
    swaps one for the other.

    So the shape of the answer: keep the result's curves for the session that
    computed them, store nothing, and make `y_calc` for *any other* node a
    `replay` — which is a `/api/result/window?node=` route, not a schema change.
    `RefinementResult`'s field types are a **WP-1003 freeze question** (`list[float]`
    → `ndarray` changes the JSON contract), so 1003 has been told.

  **And a documented fact that is wrong, found on the way.** CLAUDE.md, the
  ROADMAP and this file all say browser behaviour was "measured against the
  bundled plotly (6.9.0)". **6.9.0 is the Python `plotly` package; the library
  in the browser is plotly.js 3.7.0** (`window.Plotly.version`, on the bundle
  `/plotly.js` serves). Both numbers are real and they version independently, so
  every claim about *rendering* — WP-1015's `plotly_relayout` finding, the
  `uirevision` behaviour, and (p) above — is a claim about **plotly.js 3.7.0**.
  Corrected in place; worth knowing before anyone reads a plotly changelog to
  explain a rendering result.

- **2026-07-31 — (s) done: the weighted residual now has one authority.**
  Merged `origin/main` into `worktree-gui` first (clean; the GUI work was
  already on main via PR #17, and main's tip is a byte-identical duplicate of
  this branch's), which is what brought `viz/plots.py`'s half of the collision
  into the same tree as `gui/session.py`'s.

  **The item understated the count and misnamed the bug.** Not two definitions
  but five — `plot_result`, `plot_for_vlm`, `write_html`, `layer0` and
  `result_window` — under three σ policies. And the divergence the item names
  (Poisson fallback against raw Δ) **cannot fire**: `CompiledModel.sigma` is
  `PatternData.sig()` and `refine` stores it verbatim, so `result.sigma` is
  only ever empty on a pre-v0.2 result. Chasing the documented symptom would
  have found nothing wrong.

  The live bug was the flag beside it. `weighted = bool(res.sigma)` asks "is
  this a pre-v0.2 result", so it was **constant-true**, `lib/plot.ts`'s no-esd
  branch had never once executed, and a Poisson project was labelled
  `(obs−calc)/σ` as though its σ had been measured. Fixed by sourcing it from
  `DataRef.has_sigma` and making the flag change the axis *title* only —
  `delta` is always Δ/σ, because Δ/σ_Poisson is precisely what the fit
  minimised, so the Δ/σ button's tooltip is now true on both kinds of project.

  Method note worth keeping: the pin compares **what each renderer drew**
  (`fig.axes[1].lines[0].get_ydata()`, the plotly trace's `y`) against **what
  the route sent**, not three re-derivations of one formula — those agree with
  each other while all being wrong. Equality is exact (`assert_array_equal`,
  no tolerance): masking before or after an elementwise divide is bit-identical.

  Measured, numpy-only `[dev]` venv: fast suite 1201 → **1203 passed / 108
  skipped** (+2, the two new tests; skips unchanged), vitest 255 → **256**
  (+1). Dist rebuilt — editing `lib/plot.ts` fails `test_gui_dist.py` until
  `npm --prefix gui run build` reruns.

  **Not done, and (s) does not cover it:** nobody has looked at a Poisson
  project in a real browser. The changed pixels are one axis title, but this
  WP's own bar is the screenshot. (p), (q), (r) and (t) are untouched.

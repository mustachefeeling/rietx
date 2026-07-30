# WP-1029 — GUI usability: legibility, layout, colour, theming

Milestone: v1.0 · Status: ⬜ not started
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

- [ ] **Splitter.** Extract `Console.svelte`'s drag-resize into one component
      (report-a-size, never write-a-size); apply to the plot/sidebar split and
      the Model pane's three columns; persist in `ProjectDoc.ui`. (d)
- [ ] **Theme.** Three-way system/light/dark in `ProjectDoc.ui`, driven entirely
      by the custom properties; theme CodeMirror's gutter/selection/cursor from
      the same variables. (h), (i)
- [ ] **One selector.** `[ plot | model | text ]` as a single segmented control;
      settle the button registers in `app.css` and apply them across the header
      and panel headers. (j), (k)
- [ ] **Alignment pass** over `Model.svelte` (cell on one row of six, atoms
      table that does not truncate, ADP basis rows that do not wrap into a
      jumble), then `Params.svelte`/`Plan.svelte`. (e), (l)
- [ ] **Plot.** Point size; residual selector (Δ, Δ/σ, cumulative χ²) with the
      σ the weighted form needs added to `/api/result/window`; pattern y-scaling
      (linear / √ / log) — reusing `viz/`'s choices rather than inventing a
      second set. (f), (g)
- [ ] **Colour.** A per-phase separation pass over the element colours, anchors
      kept, fallback grey no longer equal to titanium; a test that asserts a
      minimum perceptual distance across the species of every phase in
      `tests/data`. (b)
- [ ] **Shading.** `lightposition` from the live camera at each draw, diffuse
      and specular restored, and whatever second cue survives a screenshot
      comparison on NAC at a 1000 px column. (a)
- [ ] **Viewer controls.** A disclosure menu holding the drawing thresholds and
      the new ball/stick/quality knobs, with mode and the view buttons left in
      the open; the server/client ownership split written down where the knobs
      are declared; the bond slider's label following `oninput` while its fetch
      stays on `onchange`. (m), (n)
- [ ] **Ellipsoid size.** An exaggeration factor that is named one and never
      folded into the probability label (`caption()` states both), and a stick
      radius that knows which mode it is drawn in — with `unitCylinder`'s
      docstring corrected, since its justification for going uncapped holds only
      in ball mode. (o)
- [ ] **One honest signal** that a fit is hopeless — Layer 0 already computes
      it — without touching the `status` vocabulary WP-1028 owns. (c)
- [ ] Tests: vitest for every pure function added; a jsdom mount test per
      control; the colour-distance test above. Note that jsdom has no layout, so
      the splitter's *behaviour* is testable and its *effect* is not — the
      screenshot is the check.

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

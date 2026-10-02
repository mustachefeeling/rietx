# WP-1533 — what the promo agent reached around: a cell frame with no switch, a stick width in a module constant, a score that argues against the axis view, and the furniture every script rebuilds

Milestone: unscheduled · Status: ✅ 2026-10-02 — closed, PR #671
Track: Render what the fit already knows
Depends on: — (1531 soft: the same surface, and its report fixes are the P2)

## Goal

`render_structure` drops the cell frame and sets the stick width by
argument, and both reach `fig.recipe`. The report and the skill stop
sending an agent away from an axis view it was asked for. A helper for the
legend, axis triad and scale bar, and a change to the default colours, are
each landed or declined on the record.

## Context

The evidence is two recorded takes for a rietx promo video
(yue-here/rietx-promo, `demo/log/figures-take-1.md` and
`figures-take-2.md`) and the trial before them (`figures-trial-1.md`).
Claude Opus 5.5 at xhigh effort drew six structures in each take, one prompt
per structure and no follow-ups, from rietx and its installed skill. Take 1
ran on `fix/file-biso-bounds` before PR #663 merged. Take 2 ran with
`--setting-sources project,local`, so no personal skill or CLAUDE.md reached
the agent. The agents' scripts are kept outside any repository, so the
numbers they support are restated below.

The surface:

- `viz/figure3d/render.py`: `render_structure`'s signature and `recipe`.
- `viz/figure3d/scene.py:32`: `STICK_OF_SEMI_AXIS = 0.5`. Line 134 sets the
  ellipsoid-mode stick radius to `max(STICK_FLOOR, min(STICK_RADIUS,
  STICK_OF_SEMI_AXIS * smallest))`, where `smallest` is the smallest drawn
  semi-axis.
- The TypeScript twin, `gui/src/lib/structure3d.ts:371` and `:398`.
  `gui/src/lib/structure3d.test.ts:725` pins the two copies equal, so a
  constant that changes changes in both.
- The geometry dict `rietx.gui.structure3d.build` returns. Its `edges` key
  is the cell frame (WP-1470).
- `view="auto"` and its ranking (WP-1503).
- The skill: `docs/skill/rietx/references/api-figure.md`.

### The cell frame has no switch

All twelve final scripts, six per take, set `g["edges"] = []` before
rendering. The view is fitted to everything drawn, frame included. In trial
1, a 22 Å sphere cut from HKUST-1's 26 Å cell drew at about a third of the
frame until the edges were cleared, and then the fit followed the atoms. No
docstring or skill passage mentions the trick. The skill's one `"edges"` is
`component(via="edges")`, which means something else.

### The stick width in ellipsoid mode is a module constant

At 100 K, paracetamol's 50 % ellipsoids (COD 2104364) are small, and the
sticks drew nearly as wide as them. The take-2 script set
`rietx.viz.figure3d.scene.STICK_OF_SEMI_AXIS = 0.25` before rendering. It
works, because line 134 reads the module global at call time. It also
changes every later render in the process. And it is not an argument, so
`render_structure(g, **fig.recipe)` in a fresh process draws the thicker
sticks. The workaround breaks the recipe's promise to give `image` bit for
bit.

### The report and the skill argue against the axis view

`hidden` is the share of atoms covered over 80 % by one in front. An axis
projection of a framework stacks each atom behind its own periodic images,
so it scores high by construction. Trial 1 measured HKUST-1 down a at 0.53,
ZSM-5 down b at 0.52 and YBa₂Cu₃O₇ down b at 1.00. The skill's rule is
"When `hidden` is high, draw `view="auto"`". On YBa₂Cu₃O₇ that gave a
cluttered oblique view. In take 2 the agent had been asked to look down a
cell axis, read 0.52 on HKUST-1, and wrote that it "matches expected column
stacking": it had to argue the number away.

WP-1503 left this open on the record: "the WP ties toward small indices only
after hidden and empty, so a recognisable axis view loses to a cleaner one.
That is the place to soften if agents dislike it." WP-1503 is closed, so
the work is here.

One way in: each atom in a block carries `image`, which says which atom of
the cell it is. An atom covered by an atom with the same `image` is stacked
behind its own copy, and can be counted apart from one covered by a
different atom. Measure that split on the three trial views before choosing
between three changes: the report, the `auto` ranking, or only the skill's
rule.

### Every script rebuilds the furniture

Every final script draws its own legend, axis triad and scale bar in
matplotlib around `fig.image`, from `fig.palette`, `fig.letters` and
`fig.pixels_per_angstrom`. The code after the `render_structure` call
(furniture, fonts and export) runs to 42-76 of 139-186 lines in take 1 and
80-116 of 182-216 in take 2. WP-1501 gave `palette` so that "a caller can
draw a legend in matplotlib", so the caller composing is a design choice.
The question is whether a helper earns its place against a short recipe in
the skill.

### The default colours

A colour outside the CPK set is a hue stepped by the golden angle in Z
(`gui/structure3d.py:260`). Trial 1 found Si, Co, Pb and Ba between 113° and
140°, so four of the six frameworks it drew were green. Default C is
`#383838`, which vanishes on a `#151515` background. Ten of the twelve final
scripts recolour at least one site. `recolour` is the designed route
(WP-1501), so this item is a decision. A change alters the GUI's colours
too. WP-1468's non-goals require any change to the default picture to
re-run WP-1466's `measure.py` and name the rows that moved.

## Non-goals

- The report's trim counts, bonds through polyhedron faces, label placement
  and `keep(complete=...)`: WP-1531 (issues #664 to #667).
- `build` leaving `rietx.gui` for `rx.viz` or a package of its own:
  WP-1505.
- Polyhedron chemistry: WP-1468.
- Another agent round: WP-1504.

## Tasks

- [x] `cell=` on `render_structure`. On by default. Off drops the frame, the
      fit follows the atoms, and the argument is in `fig.recipe`
- [x] `stick=` on `render_structure`, in `fig.recipe`. The module constant
      stays the default, and the twin stays equal
- [x] The axis view: measure `hidden` split into own-image stacking and
      occlusion on HKUST-1 down a, ZSM-5 down b and YBa₂Cu₃O₇ down b. Then
      change the report, the `auto` ranking or only the skill's rule, and
      say which
- [x] Furniture: land a helper or decline it, with the line counts above as
      the case. **A drawing helper declined 2026-10-02, `fig.to_px` landed.**
      10 of 12 scripts drew the same legend, triad and bar, but strip,
      fonts and annotations differ in every one. Four fitted an Å-to-pixel
      map by least squares and the rest typed the triad by hand, so the map
      is on the figure and `examples/structure_furniture.py` draws the three
- [x] Default colours: change or decline. A change re-runs WP-1466's
      `measure.py` and names the rows that moved. **Declined 2026-10-02.**
      The hues separate within a phase (WP-1029), which is their job. C's
      #383838 reads at 1.56:1 on the dark #151515, the mirror of H's
      1.38:1 on light, and a plain 3:1 rule would repaint 11 of 20 CPK
      colours. The skill now says to recolour C on a dark background, and
      a theme-dependent C goes to WP-1468 with these numbers
- [x] Tests, with a rendered PNG of each new argument to `tests/output/`
- [x] Skill: `cell=` and `stick=` in `api-figure.md`'s signature row and
      body, and the `hidden` rule rewritten for a view the prompt named

## Acceptance

`render_structure(g, cell=False)` draws no frame, and
`render_structure(g, **fig.recipe)` redraws it bit for bit. The same holds
for `stick=`. On the three trial views, the number the skill's rule reads
no longer sends an agent to `view="auto"`, or this file records why the
rule stands.

```sh
.venv/bin/python -m pytest tests/test_render_structure.py tests/test_structure3d.py -q
npm --prefix gui test
.venv/bin/python -m ruff check src tests examples
```

## References

- COD 4002052 (HKUST-1; Peterson et al., 2014, *Chem. Mater.* **26**, 4712).
- IZA-SC `MFI.cif` (ZSM-5; Baerlocher & McCusker, Database of Zeolite
  Structures).
- COD 9007744 (YBa₂Cu₃O₆.₈₂; Brodt et al., 1990, *Acta Cryst. C* **46**,
  354).
- COD 2104364 (paracetamol form I, 100 K; Bouhmaida et al., 2009, *Acta
  Cryst. B* **65**, 363).

## Handover log

- **2026-10-02** — closed, all seven tasks, in one session with WP-1531 under
  the `/wp-lanes` trial (PR #671). The lane tables are in WP-1531's entry.

  An agent no longer has to patch rietx to get the figure it wants. The cell
  frame and the stick width are arguments, so `fig.recipe` redraws what was
  drawn. The figure carries the map from Å to pixels, so a legend, axis triad
  and scale bar need no least-squares fit and no hand-typed directions, and
  an example draws all three. The report now separates atoms stacked behind
  a copy of their own site from atoms another site hides, and the skill
  keeps a view the task named. Two changes were declined on the record: a
  drawing helper, and a new default palette.

  *Done.*
  - `cell=` (`948d9042`): `cell=False` drops the frame and its a, b, c, and
    the fit follows the atoms.
  - `stick=` (`047a5e59`): a multiple of the mode's stick rule, the floor
    unscaled, in `fig.recipe`. The TypeScript twin takes the same option and
    the scene corpus replays a rutile case at 0.5. GUI dist rebuilt.
  - The axis view (`5efd60b5`): `FigureReport.stacked`. The `auto` ranking
    is unchanged, because ranking by occlusion moves every default pick and
    WP-1504's agent round is where that is measured.
  - Colours declined (`d7d439df`), furniture helper declined with
    `fig.to_px` and `examples/structure_furniture.py` landed (`9beaddb3`),
    skill rows (`0129188b`).

  *Measured* (`[dev]` venv, macOS 26.6.2 arm64):
  - HKUST-1's 22 Å sphere at `size=400`: 8.5 px/Å with the frame, 16.4
    without it.
  - Paracetamol at 100 K, ellipsoid mode: stick radius 0.0723 Å at
    `stick=1` and 0.0361 Å at 0.5, against a smallest semi-axis of
    0.1445 Å.
  - `hidden` split, one cell each: HKUST-1 down a 328 hidden atoms, all 328
    behind an atom of their own site and 24 behind a translate of
    themselves. ZSM-5 down b: 149, 144 and 8. YBa₂Cu₃O₇ down b: 14, 14 and
    14. So the split is by site: in one cell most copies come from
    rotations. Stacked shares 0.53, 0.50 and 1.00 against hidden 0.53, 0.52
    and 1.00. NAC's opening view hides 0.18 and stacks 0.00.
  - Contrast against the backgrounds: C `#383838` on `#151515` 1.56:1, H
    `#d8d8d8` on `#fbfbfa` 1.38:1. Under 3:1 are 3 of the 20 CPK colours on
    dark and 11 on light.
  - Furniture, from the twelve final promo scripts: 10 draw a per-element
    legend, an L-shaped triad and a round-length scale bar, with strip,
    fonts and annotations different in each. Four fitted an Å-to-pixel map
    by least squares and the rest typed the triad from `view=`. None used
    `fig.palette` or `fig.letters`. `to_px` reproduces every atom's `x`, `y`
    to 2.8e-14 px on a skewed, turned view.

  *Not done, deliberately.* A drawing helper: the styling differs in every
  script, so a helper would fix choices agents then fight. A new default
  palette: within-phase separation holds, and a theme-dependent C changes
  the GUI's dark picture, which is WP-1468's rule. Cropping to the ink, done
  by hand in all six take-2 scripts, also went to WP-1468.

  Next: none here. WP-1504's next round should measure whether `auto`
  ranks by `hidden - stacked`.

- **2026-10-02** — created, from the second promo take and the trial before
  it (yue-here/rietx-promo `demo/log/figures-take-2.md`,
  `figures-trial-1.md`). No open WP owns these. WP-1531 owns take 1's four
  defects (#664 to #667), WP-1505 the package move, WP-1468 polyhedron
  chemistry, and WP-1504 is the measurement. WP-1503 flagged the axis-view
  tie as "the place to soften", but it is closed and takes no fold. Checked
  against `d0498c7c`: `STICK_OF_SEMI_AXIS` at `scene.py:32` and
  `structure3d.ts:371`, the skill's `hidden` rule in `api-figure.md`, and no
  passage in the skill on clearing `edges`. Next: the axis-view
  measurement, the item that steers an agent wrong.

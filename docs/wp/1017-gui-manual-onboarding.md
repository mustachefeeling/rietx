# WP-1017 — GUI manual, in-app help, onboarding

Milestone: v1.0 · Status: ⬜
Depends on: WP-1011…WP-1016 (soft — chapters can land as their panels do)

## Goal

The GUI is documented where the theory manual lives, helps from inside the
app, and onboards a first-year PhD student without a wizard that hides the
real UI.

## Context

- **Inside `docs/manual/`** — same Sphinx/MyST/furo tree, same `-W`, same
  guards (`tests/test_manual.py`); a separate doc root would need its own
  guard set for no benefit. Three layered chapters matching the audience
  gradient:
  - `gui-quickstart.md` — install (`pip install pxrd-refine[gui]`) → open →
    fit → read the report.
  - `gui-guide.md` — panel by panel, including *when to branch* (the
    history worktree is the differentiator; teach the workflow, not just
    the buttons).
  - `gui-power.md` — the **normative `.pxt` text-format spec**,
    keyboard/palette, and the console-to-script transition — the API-echo
    story as the on-ramp to the Python API.
- The manual's anti-divergence rules apply and are executable
  (`tests/test_manual.py`): fenced constants are MyST substitutions
  injected from the live package in `docs/manual/conf.py` — **the pxt
  format version becomes a fenced constant injected from
  `gui.textdoc.FORMAT_VERSION`**, so a format bump that misses the manual
  fails the build. A new fenced constant needs a `conf.py` line *and* a use
  in a chapter.
- In-app help: tooltips from `static/help.json`, each with a "learn more"
  anchor into the built manual; `tests/test_gui_help.py` asserts every
  anchor exists (dead-link guard, same spirit as `test_manual.py`).
- First run: a **non-modal progressive checklist** (Load pattern → Load
  structure → Check instrument → Run → Read the report) — never a modal
  wizard; state in `ProjectDoc.ui`.

### Inherited

From **[1032](1032-gui-repairs.md)** (closed 2026-08-05) — the three sentences
below were forecast by the use-session note that follows; two are now facts and
one is not this WP's to state:

- **Right-click removes a line**, refit is the peak table's `↻`, and the
  component-count prompt is gone from the app entirely (the count survives only
  through the `.pxt` peaks block). The plot now prints the four gestures
  whenever the Peaks tab is up, each naming its non-pointer route — so the
  manual's job there is to *not* repeat that line, and to explain the one thing
  the screen cannot: why every pointer verb has a typed twin.
- **Per-curve visibility toggles** exist and are deliberately unpersisted, next
  to the residual and scale knobs. The paired half of that sentence — the fit
  range and excluded regions *are* persisted — landed with
  [1033](1033-plot-range-regions.md) (below).

From **[1033](1033-plot-range-regions.md)** (closed 2026-08-05) — the strip
below the plot is now a second register of control, and the manual's job is the
distinction rather than the list:

- **Two kinds of knob sit on one plot and only one changes the answer.** The
  residual selector, the scale and the curve toggles are drawing choices and are
  not stored; the fitted range and the excluded regions change what is fitted,
  persist in `project.json` the moment they are set, and move Rwp. That is the
  sentence to write, and the screen can only *imply* it through the separating
  rule and the typed fields.
- **A fifth pointer gesture exists and it is a mode**: `⇥ range` / `✂ exclude`
  arm a drag, suspend the peak verbs while armed, and disarm after one
  selection (Esc cancels). Worth explaining *why* it is armed rather than
  modifier-driven — a region drag and a zoom drag are the same gesture at every
  distance — because that is the difference from the peak verbs one paragraph up.
- **Two numbers on that strip answer questions the manual would otherwise have
  to**: "N of M channels fitted" is what makes a shaded band checkable, and
  "the curves shown were fitted over a different set of channels — re-run"
  is the app saying that settings persist immediately while curves do not.
- The masked channels are drawn recessively under the shading and have their own
  `masked` curve toggle; the exported PNG/HTML deliberately do **not** shade
  (grounds in 1033's file), which is a difference a manual should state once.
- Two new things to document that the forecast did not include: the reflection
  ticks now have a **band of their own** between the two subplots (so "the ticks
  vanish under Σχ²" is no longer true and should not be written as a caveat),
  and **hovering a peak row lights it on the plot and vice versa**.

From the **2026-08-04 use session**, which created
[1032](1032-gui-repairs.md), [1033](1033-plot-range-regions.md),
[1034](1034-panel-layout.md) and [1035](1035-symmetry-surfaced.md): **do not
write the panel-by-panel chapter until those land.** All four change controls
this chapter documents, and one of them ([1034](1034-panel-layout.md)) moves
Model and Text out of full-window modes and into right-panel tabs — which
rewrites the paragraph the WP-1029 note below asks for, and with it the
"[ Plot | Model | Text ]" sentence. The quickstart and the `.pxt` spec chapter
are unaffected and can be written now. Three things those WPs will hand over
that a manual must state: the peak picker's **right-click will remove** a line
rather than refit its group (refit moves to the table's `↻`), the plot gains
**per-curve visibility toggles** that are deliberately *not* persisted while the
**fit range and excluded regions** beside them *are* (one is a drawing choice,
the other is protocol), and a phase's **symmetry becomes editable** with a
preview of what the change would invalidate.

From **WP-1027** (closed 2026-08-01), extending the note below: the browser
pass changed two behaviours the manual should state, and the extinction
screen landed. **A drag only moves a line once you are zoomed in enough for
the line to be visible** — the move grab radius is min(10 px, 1.5× the median
FWHM), so at the survey view a drag is always plotly's zoom (tell users:
zoom first, then correct); shift-click and right-click keep the coarse 10 px
aim. **"Screen extinctions" lives in a candidate's expanded detail row** and
serves WP-1025: one table, one row per extinction class, every space group in
the class listed, ΔBIC against the absence-free reference, refuting hkl named
— and the space-group chips become adopt buttons only when the candidate
itself passes the adopt gate. The teaching point is the package's own: the
extinction *symbol* is what a powder measures; a single space group is a
convention the user chooses, never a measurement the table makes.

From **WP-1027** (peak picker + indexing panel, 2026-07-31): **the GUI grew its
indexing surface, and it is gesture-driven — the manual must name the
gestures.** The Peaks tab plus four plot interactions (click empty = add a
peak, drag a marker = move, shift-click = exclude/overrule, right-click = refit
the group), each with a non-pointer route that the docs should surface for
accessibility: a typed add-at-2θ box in the panel, and the `.pxt` peaks block
whose only editable columns are `2theta` and `flags` (everything else derived
and refused). Three reading rules worth a paragraph each: `not_separable` lines
render distinct rather than hidden (the fitter's own explanation of a strong
peak's shape) and the use-for-indexing checkbox is the overrule; a pasted
position list is badged "σ assumed" and its σ(Q)/Q is not a property of the
data; and the candidate table is abstention-first — `best_or_none()` is a badge
on a ranked list, never a headline, with Adopt driven by the server's per-row
verdict and adoption landing as a Le Bail scaffold that flips the mode.

From **WP-1029** (GUI usability, landed 2026-07-30): **the controls this chapter
was going to document have changed, which is why 1029 landed first.** Read the
list below *before* the WP-1015 note underneath it — several of that note's
sentences describe controls that have moved.

- **One top-level selector**, `[ Plot | Model | Text ]`, a segmented control in
  the header. The old pair of toggle buttons is gone, and so is the `Close`
  inside each pane: there is now exactly one control for that choice, and every
  option is named for where it lands you. The five-wide strip
  (Parameters/Plan/Report/History/Build) is unchanged and is the sidebar's tabs
  *within* plot mode — a distinction worth one sentence, since both look like
  tab strips.
- **Panes are draggable and the widths persist** (`ProjectDoc.ui`): the
  plot/sidebar split and the Model pane's first two columns. Until dragged they
  are responsive defaults, which is the behaviour to describe — a manual should
  not print a pixel width. One caveat a user will hit: a drag is refused while a
  run is in flight (see WP-1003's `### Inherited`).
- **A three-way theme** — system / light / dark, in the header as ◐ ☀ ☾. Worth
  a sentence on *why* three: "system" keeps following the machine at dusk, and
  an explicit choice keeps overriding it.
- **The plot has two new knobs.** A residual selector (Δ, Δ/σ, **Σχ²**) and an
  intensity scaling (lin, √, log). Two of these need explaining rather than
  listing. **Σχ² is the one to teach**: a flat stretch contributed nothing and a
  step is where the misfit is, which answers "where is my fit bad?" better than
  any Rwp. And **√ is drawn on the data with the axis relabelled in intensity**,
  so it is the same numbers seen differently, not a different dataset.
- **The 3D drawing knobs are behind a `drawing` disclosure**; only the mode
  buttons and *view down a/b/c* stay in the open. The WP-1015 note below
  describes the bond threshold as if it were on screen — it is one click away
  now, and it is still the one control a first-time user needs.
- **Ellipsoids gained an exaggeration factor, and the manual must not call it a
  probability.** k(p) = √χ²₃(p) diverges as p → 1, so there is no ellipsoid
  above 100 %; "× size" is a drawing scale, the caption prints both figures, and
  a figure exported at a multiplier ≠ 1 is **not** an ORTEP-quotable surface.
  That last clause is the sentence worth writing, because an ORTEP figure's
  quoted probability is the whole reason the number is on the plot.
- **A hopeless fit now says so.** Past `MATURITY_MAX_RWP` (0.35) the header
  shows `⚠ not a fit yet` beside Rwp and links to the Report; the pill still
  reads `converged`, because that vocabulary is WP-1028's. If both are on
  screen at once the manual should say which to believe and why.
- **Element colours are decided per phase**, not per element, so *the same
  element can be drawn in different colours in two different phases* — the
  anchors (H C N O S P F Cl Fe) never move, the rest are separated in OKLab
  against whatever else is in that phase. Worth one sentence, because a reader
  comparing two phase views will otherwise think something is wrong.

From **WP-1015** (structure viewer, landed 2026-07-30): **there is a 3D view, and
its two knobs are the part a manual has to explain.**

It is a **third column of the model pane** (not a tab, not a window), toggled by a
`3D` button in that pane's header and on by default. Two modes: *balls* (spheres
at 0.40× the covalent radius — the shape of the structure) and *ellipsoids*
(displacement ellipsoids at a selectable probability, default 50 %). Everything
geometric is computed server-side by `GET /api/structure3d`; the client draws.

Three things the second pass (2026-07-30) added that a manual should name, all of
them conventions rather than features. The projection is **parallel**, not
perspective, and there is **no Cartesian axis box** — the cell's own edges are
labelled a, b, c, and they are the picture's frame of reference. Rotation is a
free trackball (Jmol's and VESTA's, not plotly's z-locked turntable), with **view
down a / b / c** buttons that snap to the three projections a structure is
normally drawn in, and *reset* for the opening view. And a bond is drawn as two
half-cylinders **coloured by the atoms at each end**, which is worth one sentence
because it is how a reader tells which two species a stick joins without hovering
— and because switching a species off in the legend takes its half-sticks with
it.

What the manual owes it is the two things a user will otherwise misread.
**The bond threshold is a drawing threshold, not chemistry**: a bond is drawn at
d ≤ tol·(rᵢ+rⱼ) on covalent radii, no fixed value is right for both a large cation
and an organic (LaB6 at 1.15 draws every La–B contact and looks like a cage; at
1.05 only the B₆ framework survives), and metal–metal contacts are suppressed
unless the phase is all-metal. It is also the one control a first-time user
*needs*: LaB6 at the default 1.15 draws 210 stick segments and 109 out-of-cell
neighbours, and one turn of the slider to 1.05 turns that into the B₆ octahedron
in a cell. **The ellipsoids are a diagnostic, not
decoration**: their axes are refined quantities, so an over-flexible background —
which improves Rwp while inflating ADPs (CLAUDE.md's block projection R²) —
arrives here as balloons, and a non-positive-definite tensor arrives as a flat
disc with the reason in its hover. Measured on NAC: Na1's Biso of 2.16 Å² against
Al's 0.59 is obvious in the picture and is six ordinary-looking numbers in the
parameter table. That contrast is the best onboarding argument the GUI has for
why the view exists at all.

Costs, measured on an M4: nothing at boot (65–99 ms, unchanged), and 605–1447 ms
from clicking *Model* to a drawn scene — almost all of it fetching and parsing
plotly. Worth a sentence, because a first-time user clicks *Model* and waits a
second.

From **WP-1014** (import & in-GUI editing, landed 2026-07-30): **the onboarding
path now exists and is the empty state.** With no project open the app renders the
import wizard itself (`panels/Model.svelte`, the same component that is the model
editor when a project *is* open), so "how do I start?" is answered by the screen
rather than by a manual page. What the manual owes it is the part the wizard
cannot say in a form: why the instrument step refuses to default (an anode nobody
chose becomes a wavelength in every refined cell), what the aniso opt-in actually
changes (which parameters a plan frees), and why the pattern step names a
*reader* rather than a file type.

Also: the wizard's own copy is deliberately terse and every step already carries
its "why" as a `title` or a muted line — if the manual repeats those sentences
they become two authorities. Link to them instead, or move them.

From **WP-1013** (landed 2026-07-30): the **text pane** is the surface this manual
has the most to explain, and three of its facts are not discoverable from the UI.
It is a *mode*, not a tab — the header's `Text` button and the palette's `t` — so a
chapter that walks the tabs will miss it entirely. `⌥`-drag is a **rectangular
selection**, which is the entire reason the `.pxt` format aligns its columns, and
the pane's footer says so in one line that a manual should expand rather than
repeat. And **a re-render discards the user's own comments**: the pane warns when
the buffer has gained comment lines, but the flow ("apply, then re-read") wants
stating once, properly.

`textdoc.FORMAT_VERSION` is still owed to this WP as a **fenced constant**
(WP-1009's own note says a bump that misses the manual must fail the docs build),
and the `.pxt` grammar chapter should quote `gui/src/lib/pxt.ts`'s token
vocabulary rather than restating it — that array is already pinned to
`textdoc._KEYWORDS` by `test_textdoc.py::test_the_highlighter_quotes_the_parsers_words`,
so a manual that quotes it inherits the guard.

One sentence is worth carrying verbatim into the conflict/undo chapter, because it
is the pane's whole safety story: **there is no merge and no force-apply** — a
document regenerated from state has one authority, so a stale buffer re-reads and
re-applies. The reason is sharper than "merging is hard": the loser's document also
carries the winner's *old* values for every row it did not touch, so applying it
anyway would silently revert them.

From **WP-1011** (landed 2026-07-30): **the command palette is already the
manual's index, and it is executable.** Cmd-K lists every command with the Python
call it makes (`ref.set_vary(glob, True)`, `ref.run_stage(stage)`,
`project.doc.ui["simple"]`), and the console echoes the same string when a control
is clicked — so the chapter that teaches "the GUI is a front for the API" should
quote the palette rather than restate it, and any command added later appears
without the manual being edited. The shortcut set to document is `r` run, `.` run
the selected stage, `Esc` cancel, `f`/`x` free/fix the filtered selection, `/`
focus the filter, Cmd-K palette.

Two things the onboarding path must say plainly, because both are surprising and
both are deliberate. **The filter box is the selection** — a bulk free acts on the
glob, not on ticked rows, because one glob is one history node. And **Simple mode
hides the rows nothing can free** (locked, tied, mode-fixed) along with bounds and
transforms; it reports the count it hid, and Advanced brings them back.

From **WP-1012** (history/report panels, landed 2026-07-30): the palette gained
`?` (report) and `h` (history), and there are now **five things the report panel
says that a user will misread unless the manual says them first** — every one is
the FitReport's own design showing through, so this chapter is where they get
explained rather than in tooltips:

- **A suggestion with no Apply button is not a broken button.** Four `ActionKind`s
  are advice (`report/apply.py`'s `RECIPES`), and the note beside them *is* the
  action. The two background-flexibility ones are the interesting case: they are
  advice because a more flexible background lowers Rwp *while* biasing ADPs up and
  scales down, and the statistic that catches it (`BACKGROUND_ABSORPTION`) is not
  in the report — so there is no honest one-click version.
- **A greyed suggestion with "vetoed:" is the engine agreeing with you and having
  already handled it.** Worth a sentence, because it looks like a refusal.
- **"could not rule out" is the headline, not a footnote.** Measured on the WP's own
  fixture: applying `refine_zero_shift` on a fit whose *cell* was wrong improves Rwp
  from 21.6 % to 9.3 % by putting the error in the wrong parameter, and the report
  said so in advance (confidence capped at 0.5, both templates listed,
  `separable=false`). This is the best worked example in the repo of why the
  never-a-confident-wrong-singleton rule earns its keep — use it.
- **The predicted Δχ² is one number for the whole report**, not per suggestion, and
  it is not a bound (16.19 predicted, 16.33 observed for a cell correction). The
  panel prints it once and says so; the manual should explain why it cannot rank.
- **Undo is a checkout**, and a checkout throws the fitted curves away because they
  described the values it replaced. Users will read the empty plot as a crash.

One onboarding fact: **boot-to-interactive is 104–200 ms** measured in Chrome for
Testing (load → the parameter table's first row), so "it feels instant" is a claim
this chapter may make.

From the **v1.0 GUI plan** (2026-07-29): `gui-power.md` is where the
provisional status of the HTTP routes and `.pxt` format is stated
user-facing (schemas frozen at v1.0, wire/text surfaces provisional) —
WP-1003 states it in the release notes; this chapter is the other half.

From the **indexing plan** (WP-1018…1027, added 2026-07-29): add an
**indexing walkthrough** as an onboarding path — it is the natural entry point
for a user with a pattern and no CIF, which is the audience least served today.
`docs/manual/indexing.md` already exists from WP-1020 for the theory; this
chapter covers the panel (WP-1027). The one thing the walkthrough must teach
rather than gloss is that **a candidate list with no high-confidence entry is a
result, not a failure** — the whole module is built so that "the data cannot
distinguish these" is sayable, and a user who reads that as a bug will go
looking for a setting to force an answer.

From **WP-1009** (text document, landed 2026-07-30): `gui.textdoc.FORMAT_VERSION`
is the fenced constant this WP was asked to inject into the manual (the `pxt 1`
header line), and `gui.textdoc.VALUE_DIGITS` is worth injecting beside it — the
manual has to state that the text view renders **12 significant digits and is
lossy**, and why that is safe (a typed number is compared against the rendered
current value, so an unedited apply is a no-op). Two more things a manual chapter
should say because they are decisions, not accidents: comments in the text pane
do **not** survive a re-render, and a glob line like `profile.* @` is bulk sugar
that the next render expands into one line per parameter.

From **WP-1010** (frontend scaffold, landed 2026-07-30): the app's help text has a
home — `panels/Stubs.svelte` is where "this build can do X" is rendered from
`capabilities().features`, whose flags are derived predicates, so an in-app
capability list cannot drift from the package. Two constants worth injecting into
the manual beside the textdoc ones: the dist is **committed** (a manual chapter
should say `npm --prefix gui run build` is only for contributors, never for users)
and plotly is served from the installed package rather than bundled, which is why
`[gui]` is a plotly-only extra.

## Non-goals

- No screencasts/video, no hosted docs decisions (that is WP-1003's
  release scope).
- No autodoc API reference (0604's decision stands — a rendered API
  reference is its own document with its own failure modes).
- No restating theory — the GUI chapters link into the existing theory
  chapters rather than duplicating equations.

## Tasks

- [ ] `gui-quickstart.md` + toctree wiring; builds `-W`-clean.
- [ ] `gui-guide.md` — panel by panel, when-to-branch workflow section.
- [ ] `gui-power.md` — normative `.pxt` spec with `FORMAT_VERSION` as a
      fenced constant (conf.py line + chapter use), keyboard/palette table,
      console-to-script story.
- [ ] `static/help.json` + tooltip wiring + "learn more" anchors;
      `tests/test_gui_help.py` dead-link guard.
- [ ] First-run progressive checklist (non-modal), persisted dismissal.

## Acceptance

```sh
.venv/bin/python -m sphinx -W -q -b html docs/manual docs/manual/_build/html
.venv/bin/python -m pytest tests/test_manual.py tests/test_gui_help.py -q
.venv/bin/python -m ruff check src tests examples
```

## References

- WP-0604's manual architecture (fenced constants, `*Source:*` lines,
  cited-bib guard) — the machinery these chapters extend.

## Handover log

- **2026-07-29** — created from the v1.0 GUI plan.

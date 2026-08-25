# CLAUDE.md — the GUI: gui/ (frontend) and src/rietx/gui/ (server)

Scope: the refinement GUI's rulebook — server contract, `.rxt` text document,
editors, panels, 3D viewer, theming. Loads when a session works under `gui/`;
`src/rietx/gui/CLAUDE.md` is a pointer here. The root CLAUDE.md holds the
pipeline and package-wide invariants; `docs/milestones/v1.0.md` holds the
narrative of how these panels landed; the WP files (1008…1015, 1029) hold the
measured detail behind each rule below.

Two rules for anything a person reads here (v1.2, WP-1201/1202/1203):
**GUI prose is written under `/yue-docs-style`** (help entries, wizard lines,
empty states, error text), and **a button's `title=` is a verb phrase; every
other explanation is an entry in the help corpus** (`rietx.help`, rendered by
the help popover), never a `title=`. Until 1203 lands, `title=` stays the one
mechanism, so the second rule binds new text and not existing strings.

The **GUI** (WP-1008, `gui/`) is `rietx gui [PROJECT.rex]` — stdlib
`http.server` on 127.0.0.1, the third such app here after `watch` and `compare`.
`gui/session.py` holds `GuiSession`, where **every verb is a plain method and
nothing knows about HTTP**; `gui/server.py` parses a path, calls one, serialises
the answer, and is the layer a Tauri host would replace. Its route table plus
`RESERVED_ROUTES` (paths settled here, behaviour owed by a later WP, 404 naming
it) are the complete wire surface, held disjoint by test. Four rules: mutating
verbs return **409 while a run is in flight** — frozen-per-stage discreteness
enforced structurally rather than by discipline, and that refusal outranks body
validation; **settings persist on the verb**, not on `save`, which is what keeps
WP-1005's "nothing to warn about on close" true; the **run state is not an
event** (a failed fit emits no `fit_end`, and `EventKind` is closed) so it
travels beside them as its own SSE frame type while `live/events.jsonl` stays the
one stream `watch` tails; and `/api/result` omits the curves, which
`/api/result/window` serves per 2θ window through the *same*
`viz.compare.decimation_index` the comparison UI uses — where `max_points` is a
budget, not a ceiling. `strategy.staged.resolve_plan` (preset name + mode → plan)
is likewise one function, previously inline in `fit` and duplicated in
`sequential`.

The **text document** (WP-1009, `gui/textdoc.py`, `rxt 1`) is the line-oriented
view of a project — settings, plan, and every parameter row, where `@` frees and a
bare value holds. `render` → `parse` → `changes` → `apply`, and the rule that
makes it safe is that **a delta is diffed against the live project, never against
the old text**: an untouched document emits no verbs, a read-only field is an
error only when it *differs* (so everything can be shown without a "look, don't
touch" syntax), and a typed number is compared to the **rendered** value, which is
what lets values render lossily at 12 significant digits. Everything applies
through the same verbs a form calls — same history nodes — and every refusal is
the verb's own words (`held_because`, `TieSpec.describe`) with a line number
attached, never restated. Three grammar facts are load-bearing: a `tie` renders
**last** on its line (it contains spaces, so `=` runs to end-of-line); column
widths are **per block** (a fixed width made the renderer emit
`polarization 0.99min 0`, which its own parser refused); and a **stage line's
keys are derived from `StageSpec`** (`textdoc.STAGE_KEYS`), never listed, so a
new field on the schema reaches the renderer, the parser and — via
`test_textdoc`'s pin against `model_fields` — `lib/rxt.ts` too. Listed, it was
the same tuple in two places, and a field missing from both is not a rendering
gap but a value dropped on every save. An added key is not a `FORMAT_VERSION`
bump, on the events precedent: no line's *meaning* changed. Comments parse but do not
survive a re-render, on purpose: storing one would be a second authority.

The **frontend** (WP-1010) is a Svelte 5 + Vite + TS workspace in `gui/` whose
build output is **committed** under `src/rietx/gui/static`, so installing the
wheel never needs node — and `tests/test_gui_dist.py` is what keeps that honest:
the dist's digest is recomputed in the ordinary (node-free) suite, nothing may
gitignore the dist (the repo-wide `*.html` rule matched its `index.html` once),
the built files must be *in* the wheel, and no built file may name a remote host.
The digest itself lives once, in `gui/scripts/build_info.py`, called by both the
build and the test; `build-info.json` deliberately carries no timestamp, because
`git diff --exit-code src/rietx/gui/static` has to mean "stale", not "rebuilt".
Two duplications were refused: the client does **not** decimate (`/api/result/window`
does, through `viz.compare.decimation_index`, and zoom refetches the window) and
plotly is **not** vendored (injected at runtime from `/plotly.js`, so the app boots
and says so when it is absent). `npm run build` needs `python3`, `vitest` needs
`resolve.conditions: ["browser"]` or `mount()` comes from svelte's server build,
and `@sveltejs/vite-plugin-svelte` must be v7 for Vite 8.

**Driving a real browser: the chromium binaries are already cached even when
playwright is not installed**, so a browser pass costs an
`npm i playwright-core` **in a scratch directory, never in `gui/`** (it must not
reach the committed lockfile) pointed at the cached executable. Worth the setup
every time: the streak of "every browser session finds a defect jsdom
structurally cannot" is what the traps recorded below are made of. And when a
browser pass reports something impossible, **suspect the harness first** — a
"missing" `window.prompt` echo was headless playwright auto-dismissing the
dialog, not the app.

The **editors** (WP-1011) are the parameter table and the plan editor, and their
logic is in `gui/src/lib/` as pure functions (`table.ts`, `fnmatch.ts`,
`palette.ts`) so it can be asserted without a DOM. Four rules. **The filter box
is the selection**: a bulk free/fix sends the *glob*, because `set_vary` takes one
and records **one** history node for it — a per-row multi-select would be N globs
and N nodes — and `asGlob` wraps a bare word as `*word*` so the string previewed
and the string sent are the same one. **A held row gets no vary checkbox at all**,
with `held_because` as its tooltip and the three reasons rendered as three
(`mode_fixed` is not `locked`). **A typed number is compared to the *rendered*
value**, WP-1009's rule reused, so a cell showing `4.1568(2)` cannot truncate a
parameter on a click-in/click-out. And the client's matcher is a **preview only**
— it is `fnmatch.fnmatchcase` ported, held to Python by a committed corpus
(`tests/test_gui_fnmatch.py` writes `tests/data/gui/fnmatch_cases.json` from the
live parameter vocabulary; `fnmatch.test.ts` replays it), so a divergence is a
wrong count, never the wrong parameters freed. **`JSON.parse` rejects Python's
bare `Infinity`**, which `json.dumps` writes by default and every parameter row
carries: `gui/server.py` spells non-finite floats as the schemas do
(`ser_json_inf_nan="strings"`) on responses *and* SSE frames, and the client reads
them back with `lib/table.ts`'s `num()`. jsdom lacks `ResizeObserver` (which
`bind:clientHeight` compiles to, so its absence throws *during mount*) and
`DragEvent`; `gui/src/test-setup.ts` is the one place that gap is filled. It
also has no plotly **emitter** — the library decorates the graph div with `on`
at runtime, so `plotNode.on?.(…)` is a silent no-op and no plotly event can be
driven at all; a test that needs one patches `on`/`removeAllListeners` onto
`HTMLDivElement.prototype` for its own block (WP-1033) rather than globally,
because what it wants is to *capture* the handlers.

The **history and report panels** (WP-1012) are the GUI's read-and-act half, and
the module that carries them is `report/apply.py` — the *how* beside Layer 2's
*what*, in a separate file because the two version differently (the vocabulary is
a contract; the mapping onto verbs changes when a verb arrives). Four rules.
**An applicable action is one stage**: `stage_for` returns a `StageSpec` and runs
nothing, so applying a suggestion travels the path the per-stage Run button
travels — one `run_stage`, one history node, the same 409 — and *undo is a
`checkout`*, not an inverse verb. **The action's own `parameter_paths` are the
globs**; `RECIPES` declares only how each of the sixteen `ActionKind`s is carried
out (11 `stage`, 1 `index`, 4 `advice`, pinned complete against `get_args`), and
the four advice notes *are* the deliverable — the background-flexibility pair is
advice because it changes what the background can absorb rather than which
parameters move, and the statistic that catches the cost (the block projection R²
behind `BACKGROUND_ABSORPTION`) is not in the report. **Applicability and
reachability are different questions**: `unreachable` separates a glob matching
*nothing* (a `preferred_orientation` block not declared) from one whose every match
is *held*, quoting `held_because`, and `GET /api/report` serves the answer as an
`apply` arm **parallel to** `suggested_actions` — positional, because a kind is not
unique — so a button's enabled-ness and the route's willingness to act are one
answer. And **`expected_delta_chi2` is one number per report, not per action**:
`build_report` stamps the same figure on every Layer-1-derived action and it bounds
only the misfit attributed inside the *gated* regions (measured 16.19 predicted
against 16.33 observed), so the panel prints it once and says what it is. Two
traps a browser found and jsdom could not: the two `unmatched` kinds are opposite
diagnoses (an observed peak with no reflection is an impurity; a calculated peak
with no intensity is what a *mispositioned* model produces at every peak — 15 of
them read as "unindexed" once), and `Plot`'s window fetch must stay guarded because
a `checkout` clears the result server-side while the component still holds it.

The **text pane** (WP-1013, `gui/src/panels/Text.svelte`, `gui/src/lib/`) is the
`.rxt` document in CodeMirror 6, and it is a **mode over the whole window rather
than a sixth tab** — five tabs already fill the sidebar, and this is the one panel
whose content is line-oriented, the format's columns being aligned precisely so a
rectangular selection can hit one field. It stays mounted while hidden (a typed
buffer survives a look at the parameter table) and builds its editor on first
entry. Four rules. **The head is the reload signal** — no third SSE frame type was
added, because the head already moves for every writer and the parameter table
already reloads on it. **There is no merge and no force-apply**: a stale buffer
re-reads and re-applies, which is also what the server's 409 `STALE_REVISION`
says, and the reason is sharper than "merging is hard" — the loser's document
carries the winner's *old* values for every row it did not touch, so applying it
would silently revert them. **Only the server decides validity**: `lib/rxt.ts` has
no `error` token to emit (asserted from both sides, with the shared vocabulary
pinned to `textdoc._KEYWORDS` and `StageSpec.model_fields` by
`test_the_highlighter_quotes_the_parsers_words`), and *indentation is the parser's
own dispatch*, so an indented `plan` is a parameter named `plan`. And **a response
carrying an older `seq` is dropped** — a 300 ms debounce puts two validations in
flight across one pause and they can land out of order. CodeMirror is a separate
committed chunk (`assets/vendor-cm.js`, 328 kB) imported *dynamically*, so
`app.js` stays well under it — 114 kB when this was written, 164 kB after
WP-1015's two passes — and boot-to-interactive stays under ~120 ms;
`tests/test_gui_dist.py` asserts the split, because a stray static import would
inline the library and no byte count would say so. The editor's document and its diagnostics are `$effect`s
over the sync state, never pushed — pushing let a head move wipe a squiggle while
the problem list still named the line.

**Import and model editing** (WP-1014, `src/rietx/gui/imports.py`,
`gui/src/panels/Model.svelte`, `gui/src/lib/{model,wizard}.ts`) is how data gets
*in* from a browser and how the model is edited once it is. Its founding rule is a
split: **if the parameter table has the path, the parameter table owns it** — a
cell edge, an occupancy, a Biso, a profile term, a coordinate DOF go through
`PATCH /api/params`, where the tie/lock/mode/bound rules already live, while a
species, a label, an atom added or removed, a geometry, a wavelength or a
background family go as a whole validated model, because each changes what the
table *contains*. Coordinates are therefore never typed as x/y/z (they are affine
ties onto `…dof.k`); the editor offers the DOFs, so a site-symmetry violation is
unrepresentable rather than refused, and a fully fixed special position gets no
coordinate control at all — `GET /api/structure`'s **`sites` arm** is what says
which is which, deliberately without the Wyckoff letter (spglib per atom on a
route that refetches on every head move). Uploads are **two-phase** — a file is
staged and read before anything is created, and only an opaque token crosses back,
never a path — and they are the one route family whose body is not JSON (raw
bytes; filename and reader options in the query string, `UPLOAD_ROUTES`). Two
previews are judgements rather than descriptions: a pattern names the *reader*
that claimed it in the reader's own words, and a CIF's `aniso_available` is
**measured** by reading it a second time with `aniso=True`. A pattern preview
also carries an `instrument_hint` — the anode and goniometer radius its header
already states, matched **server-side** (`imports.suggest_instrument`) because
deciding that 1.5418 Å is a Cu doublet is a physics judgement against the
package's radiation table, and a client-side match would be a second copy of that
table in TypeScript; a header whose name and wavelength disagree sends **null**,
and the form is then left alone, because a wrong pre-fill looks like it was read.
The scan picker splits the same way for a different reason: `scan_count` rides
along in the preview's metadata from the read that already happened, while
*labelling* the scans costs a second walk of the ranges, so it is its own route
(`GET /api/upload/pattern/scans`) fetched when someone opens the control. `POST
/api/structure/aniso` exists because both directions are physics
(`AnisoU.isotropic` on, U_eq → Biso off). Three browser-only traps are recorded in
code: `structuredClone` **throws on a Svelte 5 `$state` proxy** (use
`lib/model.ts:clone`), a verb's refusal and a panel's load error **must not share
one field** (the reload after a failed apply wiped it), and `axialWarning` stays
silent on the S/L = H/L pair that is 0-and-held, because that is the shipped
default and a warning on every fresh lab instrument is a warning nobody reads.

The **structure viewer** (WP-1015, `src/rietx/gui/structure3d.py`,
`gui/src/panels/Structure3D.svelte`, `gui/src/lib/structure3d.ts`) is the model as
drawable geometry, served by `GET /api/structure3d` and rendered by the plotly
already on the page — **zero new dependencies**, and a third column of the model
pane rather than a sixth tab. Its founding rule is that **everything hard stays on
the server**: the payload is Cartesian points, 3×3 matrices and index pairs, and
the browser's whole job is `pos + T·v` over one unit sphere (which is also why a
ball and an ellipsoid are one code path — plotly's markers are sized in *pixels*,
so a ball-and-stick drawn with them cannot be compared with the cell around it).
That forced the one new crystallography verb: **`symmetry.expand_orbit` returns
the operation as well as the position**, because U\* → R·U\*·Rᵀ means an image
drawn with its parent's tensor is right on a cubic site and wrong on every other
one; `expand_positions` now delegates to it. Four rules. **gemmi has no colour
table** — it supplies radii and `is_metal`, and the colours are the CPK convention
with values chosen here (ATTRIBUTION.md), never transcribed. **A radius-sum bond
rule needs one chemical predicate**: bond metals to metals only when the phase has
no non-metal in it, or LaB6's twelve cell edges become La–La sticks (covalent
radius 2.07 Å against a = 4.158 Å). **A non-positive-definite tensor draws its
non-positive axes at zero**, because `√(negative)` is a NaN and one NaN vertex
loses the whole mesh, not one atom. And **bond segments complete their partners
exactly one level** — a bond to a translated image is correct and *reads* as
broken — which is the line between a coordination and the packing diagram this WP
declined. `probability` and `bond_tolerance` are drawing thresholds on the query
string, never in `ProjectDoc`.

Its **second pass** (2026-07-30) changed no geometry and every default, because
the scene was plotly's rather than crystallography's — read against VESTA, Jmol
and 3Dmol.js, and measured against the bundled **plotly.js 3.7.0** (which is
what `/plotly.js` serves; 6.9.0 is the Python `plotly` package, and the two
version independently) rather than its
docs. **Parallel projection** (perspective converges a cubic cell's far edges),
**no Cartesian axis box** (`axisTrace` labels the cell's own a/b/c edges instead,
at a clearance in Å set by the largest ball — a percentage of the edge put every
letter inside a corner atom), and **bonds as two-tone cylinders in Å**, which is
the marker argument above applied to sticks and which settles the legend rule *a
half belongs to its atom*. `STICK_RADIUS` = 0.08 Å is a lower bound on
`BALL_FRACTION` = 0.40 (VESTA's fraction, on covalent rather than atomic radii),
pinned by test so hydrogen cannot become a lump on a rod. **`dragmode: "orbit"`
is load-bearing**: turntable pins `camera.up` to +z and rewrites any camera that
disagrees, and `cartesian_basis` is upper-triangular, so c ∥ ẑ for every
orthogonal cell and `axisCamera`'s "view down c" would draw nothing — the free
trackball and the a/b/c buttons are one decision. `axisCamera` also depends on a
second job `aspectmode: "data"` does: the data→scene map is a *uniform* scale, so
a direction in Å is a direction in camera coordinates.

Browser-only traps, and the last is the durable one: plotly's `responsive: true`
listens for **window** resizes only, so a plot with controls below it keeps an
oversized canvas that swallows their clicks (`ResizeObserver` → `Plots.resize`;
`gui/src/lib/plotly.ts` is the one runtime loader, shared with `Plot.svelte`);
`--line` is invisible in a 3D scene, so the cell frame takes `--accent`; and
**`react` with fresh trace objects resets the gl3d camera** (replacing a `mesh3d`
rebuilds the scene from the layout, which `uirevision` does not cover), so the
view must be handed back on every draw. *Where it is read from* took three
attempts and two wrong claims in the log: `layout.scene.camera` reports whatever
was passed **in**, and `plotly_relayout` **never fires for a gl3d camera drag at
all** — measured, zero events, and true of the shipped build too, so the listener
that replaced the first wrong answer was silently receiving nothing. The only
reading of the view is `gd._fullLayout.scene._scene.getCamera()`, read back
immediately before each `react`. Method note behind all three: compare
screenshots, never a sha256 of one (a WebGL re-render differs by a pixel), and
when a claim is about an event, count the events.

**Usability** (WP-1029, `gui/src/lib/{resize,theme,plot}.ts`,
`panels/Splitter.svelte`, `gui/structure3d.py`) is the pass that made the eleven
correct panels one program, and its findings are rules rather than repairs.
**A stored size is not a settled size**: a drag clamps against the extent it
happens in, and nothing clamps a width that outlives its window — so
`fitColumns` re-clamps at *render* (widths chosen at 1500 px reopened at 1000 px
left the 3D column 24 px wide). The splitter itself carries `Console.svelte`'s
rule generalised — **report a size, never write one**, `onsize(size, done)`,
persisted to `ProjectDoc.ui` on the verb — with an `inline` flow because an
absolute grip inside `overflow: auto` scrolls away from the edge it is meant to
be. **Distinguishability is a property of the set being drawn**: `_CPK` is an
element table, `phase_palette` decides what a *picture* uses, anchoring the
famous CPK assignments and rotating the rest in **OKLab** hue at constant L and
C — sRGB has no distance, and F `#48d860` against Ca `#40c060` (both in NAC) is
0.070 apart against a 0.13 floor. Placement is anchors → table → derived, so the
hue nobody chose is the one that moves. **An exaggeration is not a
probability** — k(p) = √χ²₃(p) diverges as p → 1, so `caption()` states the
level and the multiplier separately or the picture claims a surface it is not
drawing — and **a stick knows which mode it is drawn in**: `stickRadius` returns
half the smallest semi-axis in ellipsoid mode (0.080 Å ball → 0.065 at p = 0.5 →
0.032 at p = 0.1, where the fixed stick had been *wider than the atom*), which
turns `unitCylinder`'s uncapped justification into a proof. The theme is
three-way and resolved **once**, stamped as `data-theme` on the root, because
"follow the system" is a choice and not the absence of one; CodeMirror's chrome
must be an `EditorView.theme` rather than a stylesheet rule, since CM injects
its own as `.ͼ1 .cm-gutters` and wins on specificity. `/api/result/window` sends
**three** residuals and a `weighted` flag: two are derivable in a client and
`cumulative_chi2` is not, because it must be accumulated over every point and
decimated afterwards. And plotly's `responsive: true` window-only listener bit a
**second** panel — any control row under a plot needs the `ResizeObserver`.

**Repairs found by use** (WP-1032, `lib/resize.ts`, `lib/plot.ts`,
`panels/{Plot,Peaks,Structure3D}.svelte`) is the pass that measured what the
eleven panels *feel* like, and its rules are about how to find such things.
**A trailing canvas is not a dropped frame**: `Plotly.Plots.resize` returns a
promise and does its work in chunks, so an un-coalesced `ResizeObserver` costs
*latency*, not jank — a drag issued one ~111 ms resize per pointer move and the
last landed 1.10 s late at a steady 60 fps. Every `Plots.resize` therefore goes
through `resize.ts:coalesce` (one in flight, at most one queued, and the queued
one runs, so the last redraw is the final size), and both plotly panels were
*measured* before taking it. **Instrument before the library loads**: a `$state`
rune proxies the namespace and caches each property on first read, so patching
`window.Plotly` after boot counts nothing while the plot redraws — use an init
script. **A fix that does not remove the symptom is evidence about the cause**:
the sticky peak header's backdrop is opaque and the panel column's missing
surface was a real, separate mismatch; what paints a row over the header is
`opacity: 0.55`, which promotes it to z-index 0 while the sticky `th` sat at
`auto`. Three rules about what a plot may say: **a tick belongs to the model,
not the residual** (its own `yaxis3` band in the free `[0.22, 0.28]` gap —
on `y2` its visibility was a property of which residual was chosen), **hiding a
curve is by exception** (`curveToggles`/`hidden`, unpersisted, so a curve a
later build adds arrives drawn), and **a hover link costs a `restyle`, never a
`react`** — one ring trace whose two coordinates move. Right-click **removes** a
peak (refit stays on the table's `↻`; the `window.prompt` is gone), and the
gestures are stated whenever the Peaks tab is up, each naming its non-pointer
route. `title=` is these forms' only help mechanism, so **every `PresetField`
and every `instrumentFields()` entry carries one**, pinned by a meta-test over
every geometry — the assertion found ten mute fields the day it was written.

**What is fitted, shaded and selectable** (WP-1033, `lib/plot.ts`,
`panels/Plot.svelte`, `session._masked_arm`, `Project.fitted_mask`) is the fit
range and the excluded regions made visible, and its founding measurement is
that **a mask is invisible in a picture of its own output**: `compile_model`
masks before a result exists, so both payloads carried only the surviving
channels — a band would have shaded a hole, and a fit range had no *outside* at
all, the axis autoranging inside it. So the masked channels travel beside the
fitted ones (`excluded`, quarter budget) and `Project.fitted_mask` is the one
authority for which channels the next run fits, pinned to `compile_model` by
asserting `len(result.two_theta)` against it. Four rules. **Protocol is not a
drawing choice and may not wear its clothes** — the residual selector and the
scale are session-local and unpersisted, while a region changes Rwp and persists
on the verb, so it lives in a strip of its own with typed fields and chips, and
that strip carries the **channel count**, because a band drawn over points still
in the residual is worse than no band. **Settings persist on the verb and curves
move only on a run**, so between the two the picture contradicts the setting: the
route says `stale` by comparing the fitted 2θ *values*, not their count. **A
shape is `yref: "paper"` and clipped to the measured extent** — paper because a
rectangle in log space is not the rectangle in linear space and `TICK_BAND` owns
the only free y-domain; clipped because a shape bound to a data axis **takes part
in the autorange**, and bands drawn past the data to survive a zoom-out *became*
the range (measured: −40 to 100 on a 0.5–59.99° pattern). And **a new pointer
meaning that is ambiguous everywhere is a mode, not an arbitration**: WP-1027
could make the peak grab radius readable because the ambiguity was local, but a
region drag is a zoom drag at every distance — so arming is explicit, hands the
drag to plotly's own select box, *suspends* the peak verbs, and disarms after
one selection. `viz/` deliberately does not shade (grounds in the WP): a result
cannot say what was excluded, so the exported figure shows it as absence.

**One column, eight panels** (WP-1034, `App.svelte`, `Model.svelte`,
`lib/resize.ts`) is where the panels live: Model and Text stopped being modes
over the window and became tabs beside the plot, and the full-window surface
they had is now **the column expanding, tab strip and all** — one hatch for
eight panels instead of two, with the header's `Split | Full` the only control
for it (session-local: a layout is a view choice, not a setting). Five rules,
each a measurement in the WP. **A panel's minimum width is measured, not
chosen** — the atom table's `min-content` is 448 px (+24 padding), the `.rxt`
document's *editable* columns end at 546 px with the gutter and its trailing
comments at 756, against a sidebar that clamps at 340–560 and drags to 72 %: so
WP-1013's "a narrow sidebar undoes the alignment" is true at the floor and false
at the ceiling. **A column that must not lose gets a flex *basis*, not a share**
— equal `flex: 1 1 0` gave the structure column 306 px of a 1000 px pane while
the columns needing less had plenty, and a basis is not a maximum, so a drag
still overrides it. **Overflow is wrap, never truncation, and it applies to the
header too**: no tab label is shortened, the buttons do not grow (a lone wrapped
tab stretched into a banner), and the header wraps because at 860 px it had
pushed `Cancel` and `⌘K` past the window's edge — a wrapping row breaks on its
items' *bases*, so anything meant to ellipsise instead needs `flex-basis: 0`.
**A statistic outlives the thing it describes**: an edit discards the curves
server-side, but the run frame keeps its Rwp, so the header printed a fit's Rwp
beside a plot saying there was none — the frame is the source only while a run
is in flight. That class of bug is invisible until two panels share a screen,
which is the argument for tabs restated as a defect. And **opening another
project replaces the session's** with no prompt and no dialog: settings persist
on the verb and the log is on disk, so there is nothing unsaved, and a run in
flight is already refused by `project_open`'s 409.

**Symmetry, surfaced and editable** (WP-1035, `src/rietx/gui/symmetry.py`,
`gui/src/lib/symmetry.ts`) is the phase's space group stopping being one
read-only string quoted in three places while everything it *does* — a tied `b`,
a locked angle, two DOFs instead of three — showed in the parameter table as an
effect with no named cause. Five rules. **Two tiers, split by a measurement**:
the phase facts are one `get_spacegroup` call, so they ride on `GET
/api/structure` beside `sites` as `symmetry` + `causes`, while a Wyckoff letter
is spglib per atom (**1.8-8.7 ms**, measured, and an orbit expansion is another
0.4-1.3) and lives on the deliberately-opened `GET /api/structure/symmetry` — the
escape that route's own docstring had already named. **`causes` names the
symmetry and stays silent where symmetry is not the subject**: it supplies the
missing subject of `held_because`'s "structurally fixed by symmetry **or by the
model**", so a locked `lor_strain` (the Stephens block's) keeps the anonymous
version rather than getting a wrong cause. **The preview is a diff of two
`ParameterTable`s and duplicates no rule** — the raises *are* the incompatibility
list, nearest-allowed values included, and since a table stops at the first bad
item the per-atom pass probes one atom at a time against a *real* table rather
than parsing a sentence this package owns elsewhere. **The gate is
`Refinement.edit`'s, not this layer's** — the failure was never a GUI one, so it
was fixed where it lived (root CLAUDE.md), and all `GuiSession._edit` adds is the
**address**: the refusal's leading dot-path, which a form needs to highlight the
field. And **the notes are for what a table diff structurally cannot see**: a
setting change, a centring change, `_free_paths` casualties (dropped *and*
renumbered — `…dof.k` is positional), an orbit collision, and the **orbit
multiplicity**, which a browser found by taking NAC from `I 21 3` to `I 41 3 2` —
same orders, same DOFs, same ties, same centring, empty diff, and 84 atoms in the
cell becoming 168. Two corollaries: a **blocked** preview is given no
consequences at all, since they would be computed from operators the model cannot
carry; and **a shared orbit is judged as a group, by its occupancies**. Atoms the
symmetry merges are one *site*, so the members are the connected components of
the coincidence relation and the verdict is the sum over the whole group — three
atoms at 0.4 are over-occupied where no pair of them is, which makes pairwise not
a coarser answer but a wrong one. Over 1 blocks; at or under it the same geometry
is a legal mixed site and F is right for it. **No prior art to copy, checked**:
GSAS-II recomputes every site symmetry on a space-group change
(`G2spc.UpdateSytSym`) and runs no such check, and TOPAS's `occ_merge` rescales
occupancies continuously during *structure solution* rather than refusing an edit
— deliberately not copied, because it silently rewrites a number the user typed,
which is the objection that made `check_cell_angles` refuse rather than
normalise.

The **series panel** (WP-1016, `src/rietx/gui/series.py`,
`panels/Series.svelte`, `lib/series.ts`) is the ninth tab and the only one whose
subject is a *method* rather than a model: N separate refinements chained by a
warm start, so **a smooth curve is exactly what a poisoned chain produces** and
the presentation is built around that. Five rules. **A series lives beside the
project, not inside it** — staged uploads, in-memory trees, a session-scoped
answer, `ProjectDoc.patterns` still length 1 — and its protocol (mode, plan,
limits, exclusions) is *quoted* from `project.json` rather than offered, because
one protocol over N specimens is what makes their trajectories comparable. That
is not a shortcut: an upload token dies with the session, so a persisted series
needs a document, which is WP-1003's to decide. **The order is the series**, so
every edit is a whole-list `PUT` and every file is read *there* (WP-1014's
two-phase property at N files) — with a member already described not re-read,
since a staged upload is immutable and re-reading forty patterns per keystroke
proves nothing. **`SEQUENTIAL_PATH_DEPENDENT` is a banner, and its magnitude is
computed rather than carried**: a `Diagnostic` has `where` and no number (the
wall WP-1012 hit), and both chains' trajectories are in hand, so
`series.trajectories` recomputes the fence's own combined-σ distance and serves
it — a panel ranks by disagreement with no schema change. **Ranking stops where
the fence stops**: on a clean ramp nothing is flagged and every distance is under
5e-4 σ, so sorting the unflagged ones by it ordered fifteen parameters by noise
and put `phases.0.cell.a` eighth. And **a per-pattern tree is read-only here** —
one tree per pattern, pinned by `data_fingerprint`, so a node cannot be checked
out into this project; what makes the chain navigable is the root node's
`series_warm_start_node` note. Two shared authorities came out of it rather than
second copies: `session.curve_window` (so the two panels cannot draw residuals
under two σ policies) and `session.tree_payload`.

Its **five keys on every event** are the thing to know outside the panel:
`SequentialRefinement.fit` takes `events=`/`cancel=` (since this WP — WP-1008's
charter said it already did), and `_SeriesStream` stamps
`series_index`/`series_label`/`series_n`/`series_pass`/`series_cold` onto
existing kinds, so `EVENT_SCHEMA_VERSION` does not move and "pattern k of N"
reaches the run record through the *existing* `stage`/`stage_index`/`n_stages`.
The console pays for that: five fields on every `eval` pushed the cost off the
right edge, so `lib/stream.ts` folds them into one `[T300 1/3 ↩]` prefix.
Measured browser facts: this plot is plotly **SVG**, not canvas, so WP-1015's
swallowed-click trap cannot apply to it (`Plot.svelte` draws its residual with
`scattergl`, which is what made it a canvas there) — but the `ResizeObserver`
still earns its place, since the plot refits 539 → 1480 px when the column takes
the window; a *rotated* y-axis title shares the fixed left margin with the tick
labels, so `phases.0.cell.a` clipped to `aes.0.cell.a` and the axis takes the
**leaf** (the heading above carries the path); and the staged table's floor is
per column — core 308 px, detail 231 — reflowed by `lib/resize.ts:seriesCompact`
beside `modelStacks`, because the reorder buttons are the last column and the
panel's main verb.

**The view, the armed cursor and the theme's scope** (WP-1044,
`lib/plot.ts:heldRanges`, `Plot.svelte`, `session.settings`) is the pass that
answered four defects reported from use, and three rules came out of it. **A
redraw is not a reason to move the axes** — `react` gets a layout with no
`range`, so plotly re-autoranges over *everything drawn*, and what is drawn is
not only the fetched window: the peak markers span the whole pattern and so do
the mask shapes, which are `xref: "x"` and take part in the autorange (WP-1033's
own finding one step further). Measured in Chrome, a drag to 9.97-14.66° came
back 4.57-24.85 with a peak list, 3.99-24.88 with an excluded region at 4-5° and
3.00-24.94 with a fitted range — so the zoom worked only on a plot with nothing
else on it, and every peak edit threw it away (on the raw view there is not even
a window fetch to land back in). The repair is WP-1015's camera rule one panel
over — **the view is handed back on every draw**, read off `_fullLayout`
immediately before the react, `autorange === false` being exactly "the user has
said" — plus the window a redraw refetches following the axis, `doubleClick:
"autosize"` (plotly's default *reset* means "back to the range the plot was
drawn with", which is now the zoom itself), and an **untracked** knob comparison,
because `view()` is called from the fetch effect too and a tracked read there
made choosing Δ over Δ/σ a refetch. Beside it: a payload is not a knob — the
repaint effect reads `held` untracked, or every fetch costs a second identical
react (counted: 2 per zoom drag, 6 at boot). **An armed range gesture must say so
under the pointer**: plotly's `updateFx` gives the drag layer one cursor for
every dragmode that is not `pan`, so `select` and `zoom` are pointer-identical;
`col-resize` goes on the plot-area **rect**, where an inherited cursor loses to
it without a specificity fight. And **a `ui` key belongs to whatever it is about**
— a width or Simple/Advanced is the project's (four phases, so the table wants to
be wide), a theme is the *person's*, so it lives in `GET`/`POST /api/settings`
over `state_dir/settings.json` beside the recent list, with `ProjectDoc.ui`'s
exact grammar (top-level merge, `null` drops, persisted on the verb) at app
scope. In `ProjectDoc.ui` it was re-read per project, so dark lasted until the
next `Open…`; out of there it also stops being refused mid-run, which is the
finding WP-1029 recorded and could not fix from inside `POST /api/project` (the
project's *other* `ui` keys still ride that route).

The **search controls** (WP-1045, `gui/src/lib/controls.ts`, the Peaks
panel's disclosure) are `ProjectDoc.indexing` rendered as a form — the same
`SearchSpecSpec` the agent request carries, so the two chairs are two views
of one spec. Five rules. **The document is the authority and the commit is
whole-object**: every change POSTs the entire `indexing` block on the verb (a
partial merge could let two half-specs disagree), and the draft re-syncs from
the document on every head move — including after a refusal, so the form
never shows a value the server refused. **Vocabularies come from
`/api/capabilities`** (`indexing_engines`, `crystal_systems` in search order,
`centrings`, `shift_templates`, `search_presets`), never from literals — a
fourth engine appears with no GUI change. **The field inventory is the
bijection's GUI leg**: `controls.ts` declares every field with its widget
kind, label and `title` (WP-1029's no-mute-fields rule, pinned), and
`controls.test.ts` replays the committed corpus
`tests/data/gui/index_controls.json` (the fnmatch mechanism — python owns the
model, TS proves the form states it). **A prior cell is parsed locally**
(six numbers, refused with a reason in the form's own error field — which is
deliberately not the peak verbs' failure field), while a prior space-group
symbol is validated server-side and refused in gemmi's words. And **the
streamed shortlists are the shell's to fold**: `consensus:<system>`
`stage_end` frames collect in App (cleared on `index_start`, kept after the
run so the anytime answer stays readable beside the final one) and render
with the conservative-grade caveat in the tooltip — a streamed grade can
rise, never fall.

The **peak picker and indexing panel** (WP-1027, `src/rietx/gui/peaks.py`,
`panels/Peaks.svelte`, `lib/peaks.ts`, the plot's peak layer) is where the
indexing line meets the GUI line. Peak lists are a **project artifact**
(`peaks.json`, keyed by `data_fingerprint` and refused against the wrong
pattern); every edit refits exactly one group through the picker's own solver,
and the human-owned facts (`origin`, `excluded`) carry across refits. The plot
is an editing surface **only while the Peaks tab is active**, and every pointer
verb has a non-pointer route (typed 2θ, the `.rxt` peaks block — whose only
editable columns are `2theta` and `flags`; everything else is derived and
regenerated). Two pointer rules are measured, not aesthetic: the **move
gesture's grab radius is `grabToleranceDeg` — min(10 px, 1.5× median fitted
FWHM)** — because a pixel radius alone is ±1.9° at the survey view, where a
zoom drag starting 0.9° from a marker silently moved a line 11° (the coarse
10 px stays for shift-toggle and click-to-add, whose precision comes from the
group refit); and a drawn **σ whisker is capped at 3×FWHM**, because a
degenerate component reports σ in tens of degrees (111° measured) and an
uncapped error bar owns the autorange. `/api/index` and
`/api/index/extinction` are run *kinds* on the one machine — a cancelled
search or screen **returns** what it has and its status is read off the token.
The candidate table's Adopt follows the server's `adopt` arm (one answer with
the route), the extinction table's badge follows the served `best` the same
way, and the screen itself is **not** gated on the adopt verdict — it is a
read-only measurement and `best_or_none() is None` is the normal real-data
state — while adoption stays gated, and a space-group chip acts only when the
adopt arm allows and its class is unrefuted. A right-click refit prompts via
`window.prompt`, which a headless driver must answer (`page.on("dialog")`) or
the verb silently never fires — round 1's false "missing echo".

Its second pass (2026-07-31) added three browser facts. **plotly's
`lightposition` is screen-relative, not a data-space point** — read through the
inverse of the full projection transform, so z > 0 sits *behind* the scene and
a z-dominant light renders the whole visible side ambient-flat, which is what
"desaturated, dark and flat" was: both earlier passes had shipped one, and the
scene had never been lit by its diffuse term at all. The viewer's key is one
fixed `LIGHT_POSITION = (−1e5, 1e5, 0)` (z = 0 keeps it lateral; z < 0 is a
headlight and the lateral part dies) that follows the camera by construction,
mid-drag included — no camera arithmetic exists, and `Plotly.version` at
runtime is the only version measurement (a static grep of the bundle finds a
sub-dependency's `version:"…"` string). **A style sampled synchronously inside
an effect races the shell's `applyTheme` effect in the same flush** —
`Plot.svelte` awaits one microtask before `getComputedStyle`, or the first
dark repaint wears light ink; the 3D panel never had the bug because its draw
awaits the plotly loader first. And **an effect that reads the project
*object* refires on every ui-only PATCH** — Model reloads on a boolean
`$derived` (`hasProject`), or a theme click refetches three routes plus the 3D
geometry with the head unmoved.

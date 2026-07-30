# CLAUDE.md — pxrd-refine

API-first Rietveld refinement package (powder XRD). MIT. numpy/scipy fp64
core, pydantic v2 schemas, gemmi for CIF/symmetry. Import name: `pxrdref`.

## Commands

```sh
uv venv --python 3.12 && uv pip install -e ".[dev]"   # setup (once)
uv pip install -e ".[dev,jax,torch]"                   # + optional jax/torch backends
.venv/bin/python -m pytest -n auto --dist loadgroup    # full suite ~6-12 min (1378 collected), incl. real-data acceptance
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"   # skip acceptance (1299 collected, ~20-65 s)
.venv/bin/python -m pytest tests/test_cross_backend.py # Jacobian agreement matrix; rows self-skip without their backend
.venv/bin/python -m ruff check src tests examples      # lint (must be clean)
.venv/bin/python examples/nac_11bm.py                  # end-to-end demo + plot
.venv/bin/python -m sphinx -W -q -b html docs/manual docs/manual/_build/html  # theory manual
.venv/bin/pxrdref gui my_sample.pxrd                   # the refinement GUI (localhost:8731)
npm --prefix gui ci && npm --prefix gui run build      # rebuild the GUI's committed dist
npm --prefix gui test && npm --prefix gui run check    # vitest (206: jsdom mount, fnmatch parity, panel/text-sync/model-edit/3D-trace logic) + svelte-check
.venv/bin/pxrdref watch <live-dir>                     # live viewer for a LiveSession run
.venv/bin/pxrdref compare --open                       # settings-comparison UI on the standards
```

`-n` is deliberately **not** in `addopts`: a bare `pytest tests/x.py::y` stays
serial, so `-s` and pdb keep working. `--dist loadgroup` is not optional
either — it is what honours the `xdist_group` marks that keep a shared fixture
on one worker (see the Tests bullet below); plain `--dist load` ignores them
and silently refits. Measured on a 10-core M4 (4P+6E), 2026-07-28: full
7:57 at `-n auto` and 7:24 at `-n 6`, both dominated by the single longest
group rather than by total work — fast suite 60-80 s over three runs.
**Quote wall clock as a range, never as a figure**: the same green tree
measured 7:37 and 5:44 minutes apart on that machine (2026-07-29), 11:52 on
a busier one (2026-07-30), and 12:40 later the same day on a machine
simultaneously running a headless browser, three vite builds and a second pytest
— machine state moves it further than most changes do. Compare runs, not records.
**Quote the extras with any count**: measured 2026-07-30 on a **numpy-only
`[dev]`** venv, the full suite is 1262 passed / 116 skipped (1378 collected, 10:27)
and the fast suite 1192 passed / 107 skipped (1299 of 1378 collected). Installing
`[jax,torch]` converts most of those skips into passes, so a bare "N tests" figure
means nothing without the venv it was measured in. (WP-1012 added twelve tests and
**both** counts moved by exactly twelve; WP-1013 added three and both moved by
three; WP-1014 added sixteen and both moved by sixteen; WP-1015 added twenty-eight
and both moved by twenty-eight, then one more on its second pass — every time
with the skips unchanged. That is the bookkeeping check worth doing: the same two
figures a day earlier disagreed by one, and a session that cannot say which of
its numbers moved cannot tell a new skip from a new pass. The frontend's own
suite is counted separately and moved 85 → 139 → 184 → 207 → 221 — where that
**207 was quoted as 206** until the next session re-ran it, which is the same
lesson one suite over.)

`pxrdref compare` is the fastest way to answer "does this new correction
actually help?": pick a standard, tick variants, and read the **cumulative
Δχ² vs reference** panel, which localises *where* a change acted rather than
only whether Rwp moved. Registry + runner in `viz/compare.py` (also usable
headlessly as `compare.run(standard, variant)`); server/page in
`compare_app.py`. Its standards are the acceptance suites' protocols, and
`tests/test_compare_ui.py` asserts that field-by-field so the two cannot
drift — **add a row there whenever a new correction lands.**

## Data flow

```
Structure/Instrument/PatternData (schemas/, pydantic, JSON round-trip)
  → ParameterTable (params/vector.py): tree → flat fp64 θ, dot-paths
    ("phases.0.cell.a", "instrument.profile.w", "instrument.background.c2"),
    crystal-system cell ties (b←a etc.), softplus/logit transforms
  → CompiledModel (model/forward.py): per-stage frozen state — reflection list
    (crystallography/symmetry.py, gemmi), per-atom symmetry-op subsets
    (structure_factor.py), per-(emission line, reflection) point windows,
    FCJ quadrature node counts (profiles/fcj.py), background design matrix
    (+ P-spline penalty rows); derivative_bases() serves both the analytic
    Jacobian and FitReport Layer 1 from one expansion
  → run_least_squares (optimize/least_squares.py): scipy TRF, bounds,
    analytic peak-chain Jacobian (FD fallback), esds from χ²·(JᵀJ)⁻¹ ×
    Bérar-Lelann inflation
  → staged runner (strategy/staged.py) loops stages, guards, recompiles
  → RefinementResult (schemas/results.py) → FitReport (report/, 3 layers)
    → plot / plot_for_vlm / write_html (viz/)
  → history DAG (history/, schemas/history.py): every stage auto-commits an
    immutable restorable node; checkout/run_stage/branch to fork a strategy,
    merge/cherry_pick to recombine, replay to recompute a node evaluate-only,
    append-only JSONL to persist; history/events.py streams per-iteration
    events, viz/live.py + watch.py render them live
```

`fit`, `run_stage` and `refine` all take `events=` (telemetry) and `cancel=`
(an `optimize.cancel.CancelToken` another thread sets). Cancellation is
**cooperative, read between residual evaluations** — never an interrupt, so
frozen-per-stage discreteness holds — and the in-flight stage is *abandoned*:
no node, no commit, and the models restored to their pre-stage values, because
a seeding stage writes to them before solving. `RefinementCancelled` carries
`.completed_stages` and `.node_id`, the last completed node the working state
now stands at. Event `data` is an **open dict**: adding a field to a kind is
not an `EVENT_SCHEMA_VERSION` bump (a new kind is) — the rule, and both halves
of its test, are in `history/events.py`.

A **series** (in-situ ramp, parametric sweep, tray of related specimens) is N
separate refinements chained by a warm start — `sequential.py`
(`SequentialRefinement` / `refine_sequential`), returning a `SeriesResult` of
per-pattern summaries plus parameter *trajectories*, one history tree per
pattern (a tree is pinned to its pattern by `TreeHeader.data_fingerprint`),
linked by annotation notes. Not to be confused with `multi.py`, which stacks
patterns into **one joint residual**. A chained fit is worth ≈3× in iterations
and nothing in accuracy, and its trajectory is path-dependent by construction,
so `direction="both"` runs the chain each way and flags parameters the two
disagree on (`SEQUENTIAL_PATH_DEPENDENT`) — the only check that separates a
measured trajectory from an ordering artefact.

The **parameter surface** (WP-1004) is how a client works the table without
running a fit: `Refinement.parameters() → list[ParameterRow]` lists *every*
entry — fixed, locked and tied included, esds from the last fit merged in, each
held row saying which of the three reasons holds it (`.refinable`,
`.held_because`); `set_vary(globs, vary)` and `set_values({path: value})` edit
it and auto-commit the `set_vary`/`set_value` history nodes. Three rules there
are load-bearing: `ParameterRow` mirrors `params.vector.Entry` field for field
(pinned by `dataclasses.fields`, `esd`/`mode_fixed` declared as the deliberate
extras), a **tied** path refuses an edit and names its sources instead, and
`mode_fixed` — lebail/pawley force-fix every `.atoms.` path, `.scale` and
`.source.lines.` — is *not* `locked`, which is what keeps a Le Bail phase's
mandatory dummy atom from looking editable. There is exactly **one**
`StageSpec`/`PlanSpec`, in `schemas/plan.py`; `schemas/history.py` and
`agent.py` re-export it, and `PLAN_INFO` in `strategy/staged.py` carries a
title/description/modes/when-to-use per preset, in bijection with
`PLAN_PRESETS` by meta-test.

`capabilities()` (WP-1007, `capabilities.py`) is the one call that says what this
build can do — backends *with whether each optional dependency imports here*,
solvers, plans from `PLAN_INFO`, modes, anodes, the formats `read_pattern` opens,
and the **five** versioned contracts (schema / report-thresholds / event-schema /
project-format / textdoc-format — the fifth arrived with WP-1009, which is the
argument for keeping them in the arm rather than in prose: a client reads the
field list, and a meta-test fails on a `*_version` field that is not the constant
it claims to quote). **Every arm is quoted from a live registry and a meta-test fails
on a member missing from its arm**; `features` flags are *derived predicates* (a
schema field's presence, a top-level export's existence), never literal `True`,
which is what lets `features["indexing"]` flip by itself when `index()` lands.
Guard hits are `GuardFinding(code, paths, value, message)` — `GuardReport`'s six
fields hold those, `str(finding)` is the pre-v1.0 text byte for byte (pinned by
test, because the diagnostics' messages are built from it), and every guard
`Diagnostic` now carries its paths in `where`, `HIGH_CORRELATION` included. Add a
new guard by adding a `GuardFinding` constructor there; `code` is deliberately an
open vocabulary, not a `Literal`.

A **project** (WP-1005) is a `.pxrd/` **directory** — `project.json`, the pattern
file copied byte-for-byte, `history.jsonl`, `live/`, `exports/` — opened and
saved through `Project.create/open/save` (`project.py`, `schemas/project.py`). A
directory, not an archive: the log's crash safety is append-only writes by one
writer, and rewrite-on-save would lose it. **One authority per fact.**
`project.json` holds the *settings* — selected plan/mode/limits, excluded
regions, the GUI's own `ui` keys — while `history.jsonl` holds the model state
and its head *is* the working state, so no parameter value is duplicated
between them and **saving is about settings, not durability** (the tree exists
from `create`, so every `set_vary`/`set_value` is already on disk). Two things
follow from the pattern being a file rather than a `PatternData`: the bytes are
the contract (the readers' esd column is never overridden), and the **reader
call** is part of the reference — `DataRef` records which
`io.readers.PATTERN_FORMATS` entry claimed the file plus its options, because a
pdCIF with a `_meas` and a `_calc` block is a different pattern depending on
`block`. It carries sha256 of the bytes *and* the parsed-array fingerprint on
purpose: agreeing bytes with a disagreeing fingerprint is a reader change, not a
corrupt project. `excluded_regions` live in the document because they are
protocol that is in neither the file nor `RefinementState` — a node cannot say
what was excluded when it ran.

The **GUI** (WP-1008, `gui/`) is `pxrdref gui [PROJECT.pxrd]` — stdlib
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

The **text document** (WP-1009, `gui/textdoc.py`, `pxt 1`) is the line-oriented
view of a project — settings, plan, and every parameter row, where `@` frees and a
bare value holds. `render` → `parse` → `changes` → `apply`, and the rule that
makes it safe is that **a delta is diffed against the live project, never against
the old text**: an untouched document emits no verbs, a read-only field is an
error only when it *differs* (so everything can be shown without a "look, don't
touch" syntax), and a typed number is compared to the **rendered** value, which is
what lets values render lossily at 12 significant digits. Everything applies
through the same verbs a form calls — same history nodes — and every refusal is
the verb's own words (`held_because`, `TieSpec.describe`) with a line number
attached, never restated. Two grammar facts are load-bearing: a `tie` renders
**last** on its line (it contains spaces, so `=` runs to end-of-line) and column
widths are **per block** (a fixed width made the renderer emit
`polarization 0.99min 0`, which its own parser refused). Comments parse but do not
survive a re-render, on purpose: storing one would be a second authority.

The **frontend** (WP-1010) is a Svelte 5 + Vite + TS workspace in `gui/` whose
build output is **committed** under `src/pxrdref/gui/static`, so installing the
wheel never needs node — and `tests/test_gui_dist.py` is what keeps that honest:
the dist's digest is recomputed in the ordinary (node-free) suite, nothing may
gitignore the dist (the repo-wide `*.html` rule matched its `index.html` once),
the built files must be *in* the wheel, and no built file may name a remote host.
The digest itself lives once, in `gui/scripts/build_info.py`, called by both the
build and the test; `build-info.json` deliberately carries no timestamp, because
`git diff --exit-code src/pxrdref/gui/static` has to mean "stale", not "rebuilt".
Two duplications were refused: the client does **not** decimate (`/api/result/window`
does, through `viz.compare.decimation_index`, and zoom refetches the window) and
plotly is **not** vendored (injected at runtime from `/plotly.js`, so the app boots
and says so when it is absent). `npm run build` needs `python3`, `vitest` needs
`resolve.conditions: ["browser"]` or `mount()` comes from svelte's server build,
and `@sveltejs/vite-plugin-svelte` must be v7 for Vite 8.

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
`DragEvent`; `gui/src/test-setup.ts` is the one place that gap is filled.

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
`.pxt` document in CodeMirror 6, and it is a **mode over the whole window rather
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
would silently revert them. **Only the server decides validity**: `lib/pxt.ts` has
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

**Import and model editing** (WP-1014, `src/pxrdref/gui/imports.py`,
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
**measured** by reading it a second time with `aniso=True`. `POST
/api/structure/aniso` exists because both directions are physics
(`AnisoU.isotropic` on, U_eq → Biso off). Three browser-only traps are recorded in
code: `structuredClone` **throws on a Svelte 5 `$state` proxy** (use
`lib/model.ts:clone`), a verb's refusal and a panel's load error **must not share
one field** (the reload after a failed apply wiped it), and `axialWarning` stays
silent on the S/L = H/L pair that is 0-and-held, because that is the shipped
default and a warning on every fresh lab instrument is a warning nobody reads.

The **structure viewer** (WP-1015, `src/pxrdref/gui/structure3d.py`,
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
and 3Dmol.js, and measured against the bundled plotly (6.9.0) rather than its
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

Entry points: `Refinement.fit()` / `refine()` in `refine.py`; modes
`"rietveld"`, `"lebail"` (intensity partitioning in
`CompiledModel.lebail_update`) and `"pawley"` (per-hkl intensities refined as
an off-table θ block — `model.forward.PawleyBlock`, appended in
`run_least_squares`; overlapped groups get equal-split restraints and come back
flagged `PAWLEY_OVERLAP_UNRESOLVED` rather than confidently split). For
tool-calling there is `agent.refine_json(dict) → dict` (`agent.py`, WP-0602):
one call covering refine/refine_multi/refine_sequential behind a strict task
union, errors as a structured `{ok:false, error:{code,…}}` envelope (never a
traceback), and `agent.tool_definition()` exporting the JSON Schema with the
backend/solver/plan names quoted from the live registries — a meta-test fails
if a registry member is missing from the schema.

## Invariants (do not break)

- **Frozen-per-stage discreteness**: the hkl list, symmetry-op subsets, FCJ
  quadrature node counts, and window index ranges are computed at stage
  compile and NEVER change during a least-squares run; regenerate only
  between stages. This keeps the residual smooth for FD/autodiff Jacobians.
  (FCJ node *positions* follow the parameters smoothly, with the quadrature
  split at the overlap-trapezoid kink — see profiles/fcj.py.)
- **fp64 everywhere** in the core; a GPU backend may compute Jacobian
  *columns* in fp32 but the residual used for cost/statistics and the solve
  stay fp64 on host — `backend/linalg64.py` is that boundary, and it holds on
  real hardware: an Apple-MPS refinement whose every column was computed in
  fp32 lands 3.5e-8 Å from the numpy fp64 cell, because the trust region
  re-measures each step against an fp64 cost.
- **No pydantic in the hot loop**: `ParameterTable.decode()` returns a plain
  dict; the forward model consumes floats/arrays only.
- **Weights**: use the file's esd column when present (readers), Poisson
  √max(y,1) only as fallback. Never subtract an estimated background —
  hold it additively (`BackgroundFixedPlusChebyshev`) or co-refine it under
  a smoothness penalty (`BackgroundPSpline`).
- **Background flexibility is a correctness question, not a cosmetic one.**
  A background able to imitate the peaks biases ADPs up and scales (hence QPA
  fractions) down while Rwp *improves*. Measure it as the block projection
  R² of a structural Jacobian column onto the background column span
  (`optimize.statistics.background_absorption`) — pairwise ρ misses it
  entirely (~0.2 per coefficient while the block absorbs ~46 %).
- **Reciprocal-space symmetry action is Rᵀ** (transposed rotation) — matters
  for non-cubic orbit/multiplicity counting (see symmetry.py comment).
- **Every physics function cites its reference** (author, year, journal) in
  the docstring, and documents conventions by physics not letters (e.g.
  size↔1/cosθ, strain↔tanθ; GSAS and FullProf swap X/Y labels).
- **The FitReport must never return a confident wrong singleton.** Every
  Layer-1 statement passes four gates (resolvability on the *scale-normalised*
  Gram, 0.4·FWHM validity radius, local-χ²_red significance, share-based
  global maturity); collinear angular templates are compared as *nested single
  fits* and reported non-separable rather than resolved. Confidence weights
  importance (share of χ²), not just statistical significance.
- **Licensing**: port code only from permissive sources with ATTRIBUTION.md
  updates. BGMN/Profex/xrayutilities are GPL — concepts only, never code.
  TOPAS/FullProf are closed — papers only.

## Conventions

- Parameter paths are dot-separated, glob-matched with fnmatch in stage plans
  (`"phases.*.cell.*"`). No brackets in paths (fnmatch treats `[..]` as class).
- Schemas: `extra="forbid"`, `ser_json_inf_nan="strings"` (±inf bounds must
  survive JSON round-trip — tested).
- Angles in degrees throughout; Caglioti U,V,W in deg²(2θ); Biso in Å²
  (= 8π²·Uiso); wavelengths in Å; k = sinθ/λ.
- **Hot-path code must not put a frozen numpy constant on the left of a python
  operator against a θ-derived value** — `ndarray * tensor` raises on the torch
  backend (and `tensor * ndarray` routes through numpy's deprecated
  `__array_wrap__`, then fails under a functorch transform). Route it through
  `xp.matmul` or lift it with `xp.asarray(c, dtype=np.float64)`; both are no-ops
  on numpy. Same rule for a *new op*: add it to `_OP_NAMES` and implement it on
  every backend — `tests/test_backend_conformance.py` fails, for every
  registered backend at once, if you don't.
- **Two things are written once and consumed everywhere; never restate either.**
  The residual **row layout** `[data | background-penalty | Pawley-restraint |
  soft-restraint]` lives in `model/rows.py` (`BLOCK_ORDER`, `layout()`,
  `assemble()`) — the numpy residual, the numpy Jacobian's row offsets and every
  traced residual build from it, so a new block is one edit. The **traced twin**
  of `decode`/residual lives in `backend/traced.py`, parameterised by `xp` — jax
  and torch share it, and a new backend inherits it. Adding a backend means
  adding a name to `backend.api.BACKEND_NAMES` and a row to
  `test_cross_backend.METHODS`; the conformance suite's meta-test fails if you
  do the first without the second.
- **Traced code runs inside `backend.traced.active(xp)`** — it makes `xp` the
  globally-bound backend *and* opens the backend's `full_precision()` scope.
  jax's fp64 is scoped, so a constant (or a θ vector) materialised outside it
  is silently float32: this cost the Pawley aux columns four orders of accuracy
  once, and is why constants are lifted inside the traced call, not at closure
  build.
- **Specimen absorption is one seam, three geometries, and their "off" states
  disagree** (`model/absorption.py`, `CompiledModel._absorption`). Capillary:
  `Geometry.mu_r`, Rouse (1970), off at µR = 0, and *exactly* a
  reparameterisation of {scale, Biso} — Rwp provably cannot move, the whole
  content is ΔB = c(µR)·λ²/2 (measured on real 11-BM SRM 660a data:
  ΔRwp 3e-8, every Biso +0.0166542 Å² against a predicted 0.0166542). Flat plate:
  `Geometry.mu_t`, ITC Table 6.3.3.1 case (2) under `bragg_brentano` and case
  (3a) under `flat_plate_transmission`, **off at µt = ∞** (thick specimen, ITC
  (1a), the assumption every flat-plate fit here made before v0.5) — so `mu_t`
  absent ≠ `mu_t = 0`, which is a specimen of no thickness and raises. It is
  *not* an exact reparameterisation (1-40 % of ln A survives the projection), so
  it moves Rwp, its ΔBiso is an order of magnitude larger and negative, and on a
  genuinely thick specimen declaring a thickness correctly makes the fit worse.
  Neither µR nor µt is refinable: µR is exactly singular, µt is merely
  ill-conditioned and knowable from the specimen, and the difference is recorded
  rather than smoothed over.
- **Instrument ⊕ sample profile split**: Gaussian *variances* add
  (instrument U,V,W + phase `gauss_size`/`gauss_strain`), Lorentzian *FWHMs*
  add (instrument X,Y + phase `lor_size`/`lor_strain`). Workflow:
  `lab_calibrate` on a standard with its **certified cell held fixed** (that
  is what decorrelates zero/displacement/cell) → `save_instrument_profile` →
  `load_instrument_profile` (everything `vary=False`) → `lab_sample_refine`.
- Atomic coordinates refine as site-symmetry DOFs: `ParameterTable` wires
  `phases.i.atoms.j.dof.k` (one per allowed direction from
  `crystallography/wyckoff.py`) and affine-ties x/y/z to them; free them with
  the `phases.*.atoms.*.dof.*` glob (the `mccusker_structural` plan does).
  Fully fixed special positions get locked coords — `vary=True` there raises.
- **Anisotropic ADPs are opt-in per atom** (`Atom.aniso`, CIF U^ij in Å²) and
  refine the same way: `phases.i.atoms.j.adp.k` patterns from
  `wyckoff.adp_basis`, freed by the `phases.*.atoms.*.adp.*` glob that every
  displacement stage carries alongside `…biso`. Unlike coordinate DOFs they
  are **absolute** (U = Σₖ θₖ·Bₖ), which enforces the site symmetry exactly;
  a tensor outside the allowed subspace raises rather than being symmetrised.
  Three representations, all named in `crystallography/adp.py` — the stored
  CIF **U^ij**, the fractional-space **U\*** = U^ij·a\*ᵢa\*ⱼ that the structure
  factor uses (U\* is what transforms as R·U·Rᵀ, making `Rᵀh` on the parent
  *identically* the image's tensor), and **U_cart** where eigenvalues and
  U_eq are physical. The isotropic limit is U^ij = Uiso·G\*ᵢⱼ/(a\*ᵢa\*ⱼ), **not**
  Uiso·δᵢⱼ except for orthogonal reciprocal axes. Non-positive-definite
  tensors raise an `ADP_NOT_POSITIVE_DEFINITE` diagnostic (the Debye-Waller
  factor diverges at high Q, so this is not cosmetic); positive-definiteness
  is not enforced by bounds, since the constraint couples all six components.
  `structure_from_cif(..., aniso=True)` is opt-in — several test CIFs carry
  aniso loops, and reading a file must not silently change what a plan frees.
- **Anisotropic strain is opt-in per phase** (`Phase.microstrain`, Stephens
  1999) and is the first width that depends on hkl rather than only on θ:
  σ²(M) = 10⁻¹²·Σ S_HKL h^H k^K l^L adds Λ(hkl)·tanθ to the *Lorentzian* FWHM.
  Same shape as the ADP story one rank up — the Laue-allowed S_HKL patterns are
  **derived** from the operators (`crystallography/stephens.py`, exact rational
  nullspace of the induced rank-4 action, sharing `wyckoff._nullspace_int`),
  refine as absolute DOFs `phases.i.microstrain.dof.k`, and an out-of-subspace
  set raises. Three conventions are load-bearing and stated in that module:
  √Σ·d²·10⁻⁶ is the **FWHM** (not σ) of the ΔM/M distribution; the coefficients
  are in **10⁻¹² Å⁻⁴** (physical Å⁻⁴ values ~10⁻⁸ would be finite-differenced
  with a step 100× their own size); and they multiply the **literal** monomials,
  where other codes fold symmetry multiplicities in. A block **locks
  `lor_strain`** — its isotropic direction is identically that column, the
  `biso`/`aniso` bargain again — so the block subsumes it, and it must be freed
  *in* the sample-broadening stage, not after. The isotropic limit S = ε²·[M²]
  (exactly in the subspace, whatever the symmetry) is both the seed and the only
  legal start: at S ≡ 0 the √ has unbounded slope, so `Stage.strain_seed`, not
  `Stage.seed`, which reaches softplus entries only. σ²(M) ≥ 0 is a *cone*
  coupling all fifteen, so it cannot be a box bound: under the default TRF
  driver it is a guard (`STEPHENS_STRAIN_NOT_POSITIVE`), and under
  `solver="lm"` (WP-0601) it is carried as a linear inequality and the guard
  falls silent because there is nothing left to report. Read a firing as "these
  coefficients are not quotable", never as evidence *of* anisotropy. **Zero is
  on the cone, not outside it** — the guard's test is one-sided, and the ≤ 0
  form it had before v0.6 reported the inert all-zero block as unphysical,
  which is what produced the since-withdrawn claim that it "fires on isotropic
  and anisotropic specimens alike". Re-measured: brucite leaves the cone on 12
  of 43 reflections unconstrained and 0 of 43 under `solver="lm"`; corundum
  never leaves it at all.
- **Anomalous scattering is ON by default since v1.0** (`Source.dispersion`, f = f₀ +
  f′ + i·f″ from bundled Cromer-Liberman `data/f1f2_CromerLiberman.dat`), and
  the load-bearing part is *not* that f goes complex — F always was. It is that
  `generate_reflections` merges ±h into one Laue orbit and evaluates a single
  representative, which is exact only while f is real: with f″ ≠ 0 in a
  non-centrosymmetric group |F(h)|² ≠ |F(−h)|², and both land in the *same*
  powder peak. So `structure_factors_squared` returns the **Friedel average**,
  in the exact closed form ⟨|F|²⟩ = |A|² + |B|² with A carrying f₀+f′ and B
  carrying f″ over the *same* orbit sums — no second orbit pass, no
  centro/non-centro case split, and B ≡ 0 recovers |F|² bit-identically (which
  constrains the fp *association order* in `_orbit_terms`, not just the
  algebra). f′/f″ are frozen at stage compile onto `PhaseSites.f_anom`: they
  depend only on species and λ, and `EmissionLine.wavelength` is a plain float,
  so they can never be a function of θ. One |F|² is shared across emission
  lines, *guarded* rather than smeared — `dispersion.resolve` raises when a line
  differs from the primary by more than 1 % of Z (an edge between them). Near an
  edge the table is wrong in principle, not merely coarse, so that is refused
  too and `Dispersion.overrides` takes measured pairs. It is the **only**
  correction here needing no information the caller does not already have
  (µR, a habit, a strain model, a surface — dispersion wants species and λ),
  which is why WP-1001 made it the default; `dispersion = None` declines it and
  reproduces every ≤ v0.6 number bit-identically, and `DISPERSION_NEGLECTED`
  then says so. **Every test that pins a number declares this setting
  explicitly rather than inheriting it** — a suite whose numbers move when a
  default moves is not pinning a protocol, and `tests/test_validation_matrix.py`
  enforces it for the acceptance suites. Ions resolve to the element
  (core-level effect), unlike ionic f₀.
- History nodes store **state, not curves** (a node is ~10 kB; embedding
  y_calc would make it ~1.24 MB). Their cached metrics are *as-optimised* —
  measured on a model frozen at the values each stage *started* from — so
  `refine.replay`, which recompiles at the values the stage *ended* on, can
  differ marginally. That gap is a staleness signal, not a bug. Le Bail
  extracted intensities live outside θ and are path-dependent, so they are
  serialized per node (`ReflectionState`); Pawley will reuse that container
  rather than adding one dot-path per reflection to `free_paths`.
- Emission-line weights are relative to line 0, which is structurally locked
  at 1 (degenerate with phase scales); `set_vary` globs can never free locked
  entries (also protects symmetry-fixed cell angles).
- `RefinementResult.ticks` carries **every emission line's** positions, not
  just the primary — otherwise Layer 0 flags each Kα2 peak as an unindexed
  impurity (this was a real bug, caught by the misfit-injection suite).
- Tests: fast unit/property tests always; real-data acceptance marked
  `@pytest.mark.slow` (`test_acceptance_nac.py`, `_srm660c.py`, `_fap.py`,
  `_capillary.py`).
  Reference values and data provenance in `tests/data/README.md`. Every test
  refinement also writes obs/calc/diff PNGs to `tests/output/` (gitignored)
  for visual inspection — Rwp hides locally-bad fits.
- **CI runs the same commands** (`.github/`), on cadences set by a **free-tier
  budget** — 2000 Actions minutes/month on a private repo, billed per job
  rounded up, so an over-budget config buys a month with no CI rather than a
  bill. Per push: ruff + the fast suite on 3.13, Linux, skipped entirely for
  docs-only pushes (5 billed min). Weekly: the full suite plus 3.11/3.12/3.14
  (55). Monthly: macOS and `[torch]` (66 — macOS bills at **10×**).
  **Before adding a job, price it**: the first version of this matrix cost 21
  minutes per push and 1350 a month, which did not fit. Two consequences for
  local work. **The bit-identity goldens are pinned to `darwin/arm64`**
  (`GOLDEN_PLATFORM` in `tests/test_backend_shim.py`) and *skip* elsewhere:
  measured, Linux x86-64 diverges by 1 ulp to 1.7e-13 relative — a libm and
  summation-order difference — so the gate is asserted where it was captured
  rather than loosened to a tolerance it could never distinguish from a real
  change. And **`tests/.jax_cache` is why the jax rows feel free locally** —
  deleting it takes the two jax files from ~12 s to 107 s — but caching it in
  CI was measured and does *not* help (8:18 warm against 8:12 cold): jax's
  persistent cache holds only XLA compilations above a time threshold, while
  per-process tracing and lowering are paid every run.
- **A refinement that two suites both need is computed once, in
  `tests/conftest.py`** (`sample1_results`, `srm660c_baseline`), and **every
  consumer must carry the matching `@pytest.mark.xdist_group`** — otherwise a
  second worker rebuilds the whole fixture and the sharing costs more than it
  saved. Same rule one scope down: a module fixture several tests share pins
  its module (`nac`, `capillary`, `srm660c`, `stephens-brucite`, …). The
  failure is silent, so the check is a `--durations` scan for the same setup
  appearing twice. Because runtime is set by the longest *group*, not by total
  work, splitting a group is the only way to go faster — and un-sharing a
  fixture to do it just moves the cost.
- Comparing against another code means **adopting its protocol**, not just
  its numbers: mirror its refine flags, held parameters and excluded regions,
  then check the channel count matches before believing any Rwp comparison.

## Roadmap & how to work on it

Planning docs are split so a session loads only what it needs — do not read
them all:

- `docs/ROADMAP.md` — thin index: milestone table, work-package (WP) index,
  "Current focus", and the session protocol.
- `docs/wp/NNNN-*.md` — one **self-contained** WP per task (context, commit-
  sized checklist, acceptance command, handover log).
- `docs/DESIGN.md` — design record; read only the section a WP links.
- `docs/milestones/vX.Y.md` — shipped records with measured acceptance blocks.

**Protocol**: to work on the roadmap, read the active WP file (named under
"Current focus" in ROADMAP.md) and nothing else. Commit per checklist item,
prefixed `WP-NNNN:`. Before ending any session that touched a WP — or when
interruption threatens — append a dated handover-log entry (done / in flight /
next / gotchas) and sync its Status glyph into ROADMAP.md's index. When a
milestone ships, record measured acceptance in `docs/milestones/` and flip
the ROADMAP.md row.

Because sessions never read other WP files, **a handover log only reaches your
own successor on the same WP**. Anything you learned that changes work in a
not-yet-started WP — a constant now exported for reuse, a design bullet there
that has gone stale, a deferral into it, a gotcha that would mislead it — goes
in *that* WP's `### Inherited` section, naming yours as the source
(ROADMAP.md step 3b; slot defined in `docs/wp/TEMPLATE.md`).

Shipped: **v0.1** (synchrotron vertical slice), **v0.2** (2026-07-22: lab
Bragg-Brentano, analytic Jacobian, background automation, FitReport L1-2,
history DAG, live viz), **v0.3** (2026-07-24: coordinate refinement, anisotropic
ADPs, QPA weight fractions, Brindley microabsorption, Pawley whole-pattern mode,
March-Dollase preferred orientation, multi-histogram, exporters — WP-0301…0310,
measured acceptance in `docs/milestones/v0.3.md`: SRM 676a cell anchor via c/a
(+30 ppm) plus the IUCr QPA round robin with participant-spread-referenced
tolerances), **v0.4** (2026-07-27: differentiable backends — WP-0401…0408,
measured acceptance in `docs/milestones/v0.4.md`).

**v0.5 — corrections & microstructure** (2026-07-28: capillary absorption 0501,
surface roughness 0502, Stephens anisotropic strain 0503, anomalous f′/f″ 0504,
sequential series 0505, secondary extinction 0506, anode wavelengths 0507,
flat-plate absorption + the real-data capillary acceptance 0508; measured
acceptance in `docs/milestones/v0.5.md`). Its method result is worth carrying
into any future correction: **not one of the eight is well judged by Δ Rwp** —
two provably cannot move it, one moves it the *wrong way* when it is right, and
the two largest accuracy wins are invisible in it. So a new correction ships
with a record field or a diagnostic that states what it changed, never with an
Rwp comparison as its evidence.

**v0.6 — solver, performance & agents** (2026-07-29: batched-peak-loop no-go
with the FCJ node memo shipped instead 0605, bounded LM with the Stephens cone
as a linear inequality 0601, agent JSON surface 0602, Sphinx + MyST theory
manual 0604; measured acceptance in `docs/milestones/v0.6.md`). The **theory
manual** lives in `docs/manual/` and is guarded against drifting from the code
by `tests/test_manual.py`: the build runs `-W` in the fast suite, fenced
constants are MyST substitutions injected from the live package in
`docs/manual/conf.py` (a new fenced constant needs a line there *and* a use in
a chapter), every displayed equation carries a `*Source:*` line whose symbol
must import, and every bib entry must be cited. Consequence: renaming a
physics symbol or retuning a fenced constant means touching the manual in the
same change.

**In flight: v1.0 — hardening, human GUI, indexing, API freeze, PyPI.**
`pyproject.version` tracks the milestone *in flight* (1.0.0.dev0), not the
last one shipped, because that string is stamped into every
`RefinementResult.provenance` and history node. The GUI (WP-1004…1017,
expanded into v1.0 on 2026-07-29) lands *before* the freeze (WP-1003) so the
freeze covers an exercised surface; stack decision in DESIGN.md §Outputs.
**Indexing** (WP-1018…1027, added the same day) lands before the freeze for the
same reason — `index()` is a peer of `refine()`, and until it exists the
package cannot touch a phase whose cell is unknown. Its governing rule is the
FitReport's one rank up: an indexer must never hand back one cell confidently,
so `IndexingResult` has **no** `.cell`/`.best` attribute, only a gated
`best_or_none()`; geometrical ambiguity (Mighell & Santoro 1975) is reported
with the reflections that would break the tie rather than silently resolved;
coverage is scored in *both* directions because ranking on
share-of-observed-intensity alone demonstrably puts a 390-line wrong phase
above the truth; and a restricted search reports `systems_searched` rather than
concluding anything about the sample. Three engines (dichotomy, index
heuristic, whole-profile Monte Carlo) supply the confidence by agreeing, the
same device as `direction="both"` and the cross-backend matrix.

**v0.4 — differentiable backends.** `backend=` takes `"numpy"` (the default and
the only one anyone needs), `"jax"`, or the **experimental** `"torch"` (CPU
fp64) / `"torch-mps"` (Apple GPU, necessarily fp32) — never installed by
default, kept as an independent opinion in the agreement matrix and as the
route to using the forward model as a differentiable layer (DESIGN.md, "What
the differentiable core unlocks"). Every backend is held to per-column
agreement with the analytic Jacobian in `tests/test_cross_backend.py` — whose
configs must grow whenever a *new derivative path* does, or no backend row
covers it. Also landed: true Voigt
(`Instrument.profile.shape="voigt"`, one shared Weideman Faddeeva `w(z)`, TCHZ
still the default), soft bond/angle/value restraints (extra residual rows below
the data, Rietveld and single-histogram only), and the Bérar-Lelann esd fix
(reported esds now carry the inflation; the correlation matrix is a true Pearson
matrix and the 0.98 guard is live). Apple-GPU execution is *slower* than numpy
(46-182×, launch-latency-bound) — `torch-mps` buys precision validation, not
speed; the measured break-even (≈65 k elements per kernel) and ceiling (≈2.5×)
are in the v0.4 record. v2 fence:
FPA, neutron/TOF, spherical-harmonics texture, MCP server.

Key test data (provenance + every reference value in `tests/data/README.md`):
- `11BM_NAC.fxye` — APS 11-BM synchrotron, λ=0.4139090 from the .prm; NAC +
  CaF₂ impurity; acceptance expects a≈10.2513, Rwp<0.12.
- `nist_srm660c_100a.cif` — NIST LaB6 certification data, CuKα doublet +
  graphite analyzer; fits the `…_meas` block with zero fixed / displacement
  refined; expects a≈4.15678±2e-4, Rwp<0.10. **Absolute** anchor.
- `FAP.XRA` + `FAP.EXP` — GSAS-II LabData tutorial fluorapatite; the `.EXP` is
  GSAS's converged fit and supplies both the reference values and the protocol
  the test mirrors. **Cross-code consistency** check (±300 ppm), not truth.
- `qarr/*.prn` — IUCr CPD QPA round-robin patterns (samples 1a-1h, 2, 4 + six
  pure phases; plain 2-column ASCII, Cu Kα doublet, graphite diffracted-beam
  mono). QPA truth is the **weighed composition**; tolerances referenced to
  the published participant spread, never to σ(W). `corundum.prn` doubles as
  the SRM 676a cell-anchor specimen (c/a is the certificate-grade assertion;
  absolute axes carry lab d-scale systematics).

# WP-1027 — GUI peak picker and indexing panel

Milestone: v1.0 · Status: ⬜ not started
Depends on: 1010, 1011, 1018-1024 (1009 touched)

## Goal

A human can see every fitted peak against the data, correct the ones the fitter
got wrong, run indexing, and read the candidate table — including what the data
cannot distinguish — without leaving the browser.

## Goal, restated

Peak picking is the one step in this workflow where a human eye genuinely beats
the algorithm: a shoulder the fitter missed is obvious on screen and invisible
in a number. This panel exists for that, not for convenience.

## Context

- **Stack is already decided** (DESIGN.md §Outputs, 2026-07-29 amendment):
  local web app, stdlib `http.server`, SSE on `ThreadingHTTPServer`, Svelte 5 +
  TypeScript with **committed** build assets shipping in the wheel, plotly from
  the installed package, `[gui]` extra = plotly only. Every verb is a plain
  method on `GuiSession`; `server.py` is transport only, so a Tauri shell can
  wrap it later.
- **Session verbs** (all plain methods):

  ```python
  pick_peaks(**opts) -> PeakList
  add_peak(two_theta) -> PeakList        # seed + refit that group
  remove_peak(i) -> PeakList
  move_peak(i, two_theta) -> PeakList    # drag → reseed + refit the group
  set_peak_flags(i, *, use_for_indexing=None, flags=None) -> PeakList
  refit_group(g, *, n_components=None) -> PeakList
  index(**opts) -> str                   # run id — long-running
  index_result() -> IndexingResult
  adopt_candidate(i, *, space_group=None) -> str   # history node id
  ```

  Every verb echoes its equivalent API call into the console pane
  (`session.move_peak(7, 23.451)`), so the session log stays a reproducible
  script — the GUI's standing rule from DESIGN.md §Outputs.
- **The peak-list verbs are cheap and synchronous; `index()` is not.** It goes
  through WP-1006's run state machine — cancel token, SSE progress, the
  409-while-running rule. That means the run kind must not be refinement-only;
  an `### Inherited` note was left in WP-1006 for exactly this.
- **Peak lists are a project artifact, not a history node.** They live in
  WP-1005's `.pxrd/` container as `peaks.json`, keyed by `data_fingerprint`, so
  a peak list can never be displayed against the wrong pattern — the same
  device `TreeHeader.data_fingerprint` uses for history trees. By contrast
  `adopt_candidate` **is** a model edit and goes through
  `Refinement.edit(structure=…, label="adopted indexed cell …")`, which already
  records an `edit_model` node: **no new NodeKind**.
- **The plot shows the fitted group profile over the data**, not just a tick
  mark, plus a per-group residual strip. That is the whole point: it is what
  lets a human see the `PEAK_UNRESOLVED_SHOULDER` case the fitter reported but
  could not resolve. Peak markers carry `2θ ± σ` error bars; excluded peaks are
  drawn hollow; flags drive colour.
- **Interactions**: click empty space → `add_peak`; drag a marker →
  `move_peak`; shift-click → cycle `impurity_candidate` / `excluded_by_user`;
  right-click a group → "fit N components". Peak-list diagnostics render as an
  inline strip, not a modal — they are information, not an interruption.
- **The candidate view is deliberately a table**, one row per candidate, one
  column per FoM panel member, `found_by` as engine chips, ambiguity partners
  as an expandable sub-row. A table cannot express a confident singleton, which
  is the same property WP-1024 gives the API. **"Adopt" is per-row and disabled
  with a tooltip when `confidence != "high"`** — the UI must not be the place
  the gate leaks.
- **`.pxt` gains a `peaks` block** (format reserved by WP-1009). Peaks are not
  refinable parameters, so they carry **no `@` marker** — that is the visual
  distinction from every other block:

  ```
  peaks 20                              # pick_peaks(min_sigma=5.0, shape=tchz)
    #      2theta      esd     fwhm         I    flags
     0     8.4712   0.0009   0.0812     10420
     1    10.7743   0.0011   0.0834      3310   impurity
     2    12.0316   0.0026   0.0901       220   kbeta_ghost excluded
  ```

  On apply, **only the `2theta` and `flags` columns are editable** — a 2θ edit
  is a `move_peak` (refit the group), a flags edit is `set_peak_flags`; every
  other column is derived and regenerated on the next render. Same
  all-or-nothing delta semantics and 1-based line numbers as the rest of the
  format, and the existing hypothesis `render → parse → render` fixed-point
  test extends to cover it.

### Inherited

From **WP-1014** (import & in-GUI editing, landed 2026-07-30): three things this
panel can reuse rather than rebuild.

**The upload flow** (`POST /api/upload/pattern` → token → commit) is how a pattern
with no known phase gets into a project at all, which is the case indexing exists
for — and the wizard's structure step is currently *required*. An
index-from-nothing flow needs a way past that, and the honest shape is a wizard
branch that creates the project with the indexed candidate (or a Le Bail
placeholder) rather than a fourth ingest path.

**A full-window mode is an available shape.** `panels/Model.svelte` is toggled
from the header beside Text; a peak list plus an FoM panel plus a plot has the same
width problem the atom table did, and the sidebar is `clamp(340px, 38%, 560px)`.

**`GET /api/structure`'s `sites` arm** and `POST /api/structure/aniso` exist, so an
adopted cell's atoms render with their site-symmetry DOFs immediately — nothing
about adoption needs a new read.

From **WP-1013** (landed 2026-07-30): the `peaks` keyword **already highlights** in
the text pane — `gui/src/lib/pxt.ts`'s `KEYWORDS` quotes `textdoc._KEYWORDS`,
reserved blocks included — so a picked-peaks block will be coloured the day the
parser stops refusing it, with no frontend change. Two things follow.

`test_textdoc.py::test_the_highlighter_quotes_the_parsers_words` compares the four
word lists in `pxt.ts` against `textdoc._KEYWORDS`, `_FLAG_WORDS`, `_PAIR_WORDS`
and `StageSpec.model_fields`; **a new annotation word in the peaks block is a
failing test until it is restated there**, which is deliberate — that is the guard
that keeps the frontend's second reading of the grammar from drifting. A new
*block* name needs nothing, since `peaks` is already in the list.

And the peaks block's own sketch (in `textdoc.RESERVED_BLOCKS`) says it carries
**no `@` markers**, because peaks are not refinable parameters. The scanner colours
`@` as its own `vary` token in green, so that absence will read visually as well as
grammatically — worth keeping when the block is designed, rather than adding a mark
that means something else.

From **WP-1011** (landed 2026-07-30): the sidebar is a **tab strip whose tabs
stay mounted** — `Peaks` is a tab, and a picker holding an unsaved edit survives a
visit elsewhere. Reuse `lib/table.ts` for the peak list (grouping, the virtual
window, esd-aware value formatting) rather than writing a second table; a
thousand-peak list is exactly the case its virtualization exists for. Two
contract facts: non-finite floats cross the wire as **strings** (`"Infinity"`),
because `JSON.parse` rejects Python's bare token — read them with `num()`; and
`gui/src/test-setup.ts` stubs the browser APIs jsdom lacks (`ResizeObserver`;
`DragEvent` is also absent, which matters for a drag-to-move peak marker).

From **WP-1008**: routes `GET/POST /api/peaks`,
`POST /api/peaks/{add,remove,move,flag,refit}`, `POST /api/index`,
`GET /api/index/result`, `POST /api/index/adopt` were reserved (404 until this
WP), and `/api/index` was wired to the run state machine.

From **WP-1009**: the `peaks` block is reserved in `FORMAT_VERSION`, so this WP
fills it in without a format bump.

From **WP-1024**: `best_or_none()` is the only singleton accessor and
`IndexingResult.candidates` is always a list — the frontend must not synthesise
a "the answer is" view from `candidates[0]`.

From **WP-1012** (landed 2026-07-30) — three reusable pieces and one measured trap:

- **The plot takes a `zoom` prop** (`[lo, hi] | null`) and refetches
  `/api/result/window` when it changes, so pointing at a 2θ range from a panel is
  one line and arrives at full point budget (measured: 4129 points over 3–24°
  becomes 54 over 17.060–17.325°). A peak picker wants exactly this, plus the
  reverse direction — clicking the plot to *add* a peak needs a click handler on
  the plotly node, which nothing has registered yet.
- **`gui/src/test-setup.ts` now stubs `Plotly`** as well as `ResizeObserver`,
  because jsdom does not fetch `<script src>` and the runtime plotly loader
  therefore never resolves — without it, no component test can reach the line that
  fetches plot data at all. Any picker test that asserts on plot interaction
  depends on that stub.
- **`lib/report.ts`'s `worstRegions` ranks by χ² share, not local Rwp**, and the
  reason applies to a peak list too: a region can have a dreadful local Rwp over
  four counts of noise. The candidate list should not be ranked on a normalised
  quantity alone.
- The trap: **`Plot.draw`'s fetch must stay guarded.** A checkout clears the result
  server-side while the component still holds the old one, and the unguarded fetch
  escaped as an unhandled page error — invisible to jsdom, found in Chrome. A
  picker that fetches peaks on a head change has the same shape.

From **WP-1018**: `ObservedPeak.origin` distinguishes `"fitted"` / `"manual"` /
`"edited"`; surface it, because a hand-placed peak and a fitted one carry
different weight and the user should see which is which.

From **WP-1008** (GUI server, landed 2026-07-30): every route this WP asked to
have reserved **is** reserved and 404s naming it — `GET/POST /api/peaks`,
`POST /api/peaks/{add,remove,move,flag,refit}`, `POST /api/index`,
`GET /api/index/result`, `POST /api/index/adopt` (see
`gui.session.RESERVED_ROUTES`, held disjoint from `ROUTES` by a test). Filling
one in is a `ROUTES` entry plus a `GuiSession` method.

For the long-running half: `GuiSession.run(body)` is the machinery — it takes
`kind`, builds a `CancelToken` and an `EventStream(path=live/events.jsonl,
callback=…)`, starts one worker, and 409s every mutating verb while busy. Wiring
`/api/index` to it means adding a `kind: "index"` branch there, and the run
record's fields (`status`, `stage`, `node_id`, `completed_stages`, `error`) are
generic enough to carry an indexing run without new keys. Remember WP-1006's
note carried into WP-1024: a **new** `EventKind` is a schema-version bump where
an added `data` field is not.

From **WP-1009** (text document, landed 2026-07-30): the **`peaks` block name is
reserved in `pxt 1`**, so filling it in needs no format bump —
`gui.textdoc.RESERVED_BLOCKS` maps it to this WP and the parser refuses it with
that owner rather than as an unknown keyword. The intended layout (and the two
editable columns, `2theta` and `flags`) is recorded in that module's docstring.
Two grammar rules to follow when implementing it: an annotation containing spaces
must render **last** on its line, and column widths are computed **per block** —
a fixed width is what made the renderer emit output its own parser refused.

## Non-goals

- No new indexing capability — this WP is a surface over WP-1018-1025.
- No structure solution view.
- No new dependency: plotly is already the `[gui]` extra, and the panel adds
  nothing.

## Tasks

- [ ] `GuiSession` verbs above, each with its console-pane API echo.
- [ ] Fill in the WP-1008 routes; `/api/index` on the run state machine with
      SSE progress and cancel.
- [ ] `peaks.json` in the `.pxrd/` container, keyed by `data_fingerprint`;
      `adopt_candidate` through `Refinement.edit`.
- [ ] Frontend: peak layer (markers, σ error bars, fitted group profile,
      residual strip), the four interactions, the diagnostics strip.
- [ ] Frontend: candidate table with the FoM columns, engine chips, ambiguity
      sub-rows, and the gated Adopt button.
- [ ] `.pxt` `peaks` block: render, parse, apply (2θ and flags only); extend
      the fixed-point property test.
- [ ] `tests/test_gui_peaks.py`: verbs round-trip through the live server;
      a peak list keyed to one pattern is refused against another; `.pxt`
      fixed point; **Adopt is disabled for a `medium` candidate** (the gate
      does not leak into the UI).

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_gui_peaks.py -q
.venv/bin/python -m pytest tests/test_textdoc.py -q
.venv/bin/python -m ruff check src tests examples
```

Criterion: a peak can be added, dragged, flagged and refitted through the live
server with the console echo matching the API call that would reproduce it; the
`.pxt` round trip is a fixed point; and no UI path adopts a candidate that
`best_or_none()` would not return.

## References

- DESIGN.md §Outputs, 2026-07-29 amendment — the stack decision.
- `viz/compare.py` + `compare_app.py`, `watch.py` — the stdlib-`http.server`
  precedent this follows.

## Handover log

- **2026-07-29** — created from the indexing plan.

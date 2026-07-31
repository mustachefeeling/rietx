# WP-1027 — GUI peak picker and indexing panel

Milestone: v1.0 · Status: 🔄 2026-07-31
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

### What the landed neighbours settled (Inherited, pruned 2026-07-31)

**Peak-list semantics (WP-1026).** `pick_peaks` emits components flagged
`not_separable` — shape the fitter believes in, a line it does not — kept in
`PeakList.peaks` but excluded from `usable()` like the Kβ/W ghosts. On real lab
data `len(peaks.peaks) != len(peaks.usable())` is the *normal* case (8 of 63 on
bundled corundum), so the panel renders both, distinguished. `not_separable` is
the flag a user most wants to overrule; `excluded` is the existing route for a
caller's own decision, and overruling `not_separable` is a *different* act that
should look different. A pattern full of `not_separable` usually means a
mis-declared instrument profile — an actionable message, not a peak-picking one.
And a `from_positions` list indexes despite its assumed σ, but every line carries
`sigma_assumed` — the panel must say "precision assumed", never quote σ(Q)/Q as a
property of the data.

**Correction (pruned): `ObservedPeak.origin` does not exist.** The note here
attributing a `"fitted"`/`"manual"`/`"edited"` origin field to WP-1018 was wrong
— no such field is in `schemas/indexing.py` and WP-1018's file never mentions
it. The *need* is real (a hand-placed peak and a fitted one carry different
weight), so **this WP adds the field** (default `"fitted"`, set by the GUI's
add/move verbs) rather than pretending to inherit it.

**The candidate answer (WP-1024).** `best_or_none()` returning `None` is the
*expected* first outcome (on real lab data with no measured shift,
`shift_allowance_assumed` caps everything at `medium`), so the candidate list is
the primary view and the singleton a badge on it. `confidence_caveats` is the
closed `IndexCaveat` vocabulary → chips, coloured red from
`INDEX_REFUTING_CAVEATS` (served, never hand-listed client-side). Per-candidate
diagnostics live on `candidates[i].diagnostics` — rendering only
`result.diagnostics` drops the most actionable messages.
`AmbiguityPartner.discriminating_two_theta` now lies *outside* the measured
range: render "collect to here" beyond the pattern's right edge. Progress and
cancellation are wired (`index_start`/`index_end`, per-engine
`stage_start`/`stage_end` with `engine`/`index`/`n_stages`;
`EVENT_SCHEMA_VERSION` is `"2"`; a **new** EventKind is a bump, a new `data`
field is not).

**Extinction (WP-1025).** The panel after "adopt this cell" is another table:
`determine_extinction_symbol` → ranked `ExtinctionScreen`, one row per class
with `symbol`, *all* its `space_groups`, `delta_bic`, `n_absent`/`n_testable`,
refuting hkl. One space group rendered singly is unmeasurable, not merely
unsupported; `EXTINCTION_GROUPS_NOT_SEPARABLE` is an `info` that must be shown.
Cost: one shared profile fit (~2 s) then ~0.1 s per class (7 classes hexagonal,
71 orthorhombic P).

**Server machinery (WP-1008/1006).** The ten routes are reserved in
`gui.session.RESERVED_ROUTES`; filling one in is a `ROUTES` entry plus a
`GuiSession` method. `GuiSession.run(body)` is the long-running machinery —
add a `kind: "index"` branch; the run record's fields are generic enough, no
new keys. Mutating verbs 409 while busy.

**Text document (WP-1009/1013).** The `peaks` block name is reserved in `pxt 1`
(`textdoc.RESERVED_BLOCKS`) — filling it needs no format bump. Grammar rules: an
annotation containing spaces renders last on its line; column widths are per
block. No `@` markers — peaks are not parameters, and the scanner's green `@` is
a vary token that must not appear here. The `peaks` keyword already highlights;
`test_textdoc.py::test_the_highlighter_quotes_the_parsers_words` pins the word
lists in `gui/src/lib/pxt.ts` to the parser's, so new flag words in the peaks
block are a failing test until restated there — deliberate.

**Frontend facts (WP-1010…1015, 1029).** `Peaks` is a sidebar tab; tabs stay
mounted. Reuse `lib/table.ts` (virtual window, esd formatting, `num()` for
`"Infinity"` strings). `lib/plotly.ts` `loadPlotly()` is the one runtime loader;
**any plot with controls below it needs `ResizeObserver` → `Plotly.Plots.resize`
on the plot div** (plotly's `responsive: true` is window-only; an oversized
canvas swallows clicks and maps a picker's click to the wrong 2θ). The plot takes
a `zoom` prop and refetches `/api/result/window`; clicking to *add* a peak needs
a click handler nothing has registered yet; a click on √-scaled intensities maps
back through `lib/plot.ts`'s `scaleValues` (√ is applied to the data, only tick
labels map back); the shared 2θ axis is anchored to the lower subplot
(`xaxis.anchor: "y2"`), so pixel→2θ off the upper plot's geometry is wrong.
`Plot.draw`-style fetches stay guarded (a checkout clears the result server-side
mid-flight); `test-setup.ts` stubs `Plotly`, `ResizeObserver` (jsdom also lacks
`DragEvent`). `gd.layout` read back is not a reading of the view; compare
screenshots, not hashes. `worstRegions` ranks by χ² share, not local Rwp — a
candidate list should not rank on a normalised quantity alone.
`GET /api/structure3d` draws an adopted cell immediately — a cheap sanity check
no figure of merit provides. A full-window mode (like Model) is an available
shape if the panel outgrows the sidebar; the wizard's structure step is
currently *required*, so an index-from-nothing flow needs a wizard branch that
creates the project with a Le Bail placeholder — recorded here as follow-on,
not this WP's checklist.

## Non-goals

- No new indexing capability — this WP is a surface over WP-1018-1025.
- No structure solution view.
- No new dependency: plotly is already the `[gui]` extra, and the panel adds
  nothing.

## Tasks

- [x] `GuiSession` verbs above, each with its console-pane API echo.
- [x] Fill in the WP-1008 routes; `/api/index` on the run state machine with
      SSE progress and cancel.
- [x] `peaks.json` in the `.pxrd/` container, keyed by `data_fingerprint`;
      `adopt_candidate` through `Refinement.edit`.
- [x] Frontend: peak layer (markers, σ error bars, fitted group profile,
      residual strip), the four interactions, the diagnostics strip.
- [x] Frontend: candidate table with the FoM columns, engine chips, ambiguity
      sub-rows, and the gated Adopt button.
- [x] `.pxt` `peaks` block: render, parse, apply (2θ and flags only); extend
      the fixed-point property test.
- [x] `tests/test_gui_peaks.py`: verbs round-trip through the live server;
      a peak list keyed to one pattern is refused against another; `.pxt`
      fixed point (in `test_textdoc.py`, beside the other fixed-point
      properties); **Adopt is disabled for a `medium` candidate** (the gate
      does not leak into the UI — asserted server-side there and from the
      JS side in `App.test.ts`).

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

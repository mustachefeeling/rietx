# WP-1034 — Model and Text in the right panel

Milestone: v1.0 · Status: ⬜
Depends on: 1013, 1014, 1029 (all landed) · soft: 1032

### Inherited

From **[1033](1033-plot-range-regions.md)** (closed 2026-08-05) — one fact that
changes this WP's recon, and one that constrains where a control may go:

- **The plot column is one row taller.** A `.protocol` strip now sits under the
  knobs — typed range boxes, an arm control, one chip per excluded region, a
  channel count — and it *wraps*, so with several regions it is two rows on a
  narrow window. The three measurements task 1 asks for must be taken with it
  present, and the number that matters is how much vertical room the plot has
  left at 860 px, not how wide the sidebar is.
- **Protocol controls may not be moved in beside drawing controls.** The strip
  is separate from `.knobs` because one set changes what is fitted and the other
  changes only the picture; if this WP reflows the plot column, that separation
  is the thing to preserve — a rule stated in `gui/CLAUDE.md`, not a layout
  preference.

## Goal

Editing a parameter and seeing the fit change are the same glance: the model
editor and the text document become tabs in the right panel beside the plot,
with a full-window mode kept for the two things that are genuinely wide, and the
open/recent screen reachable without restarting the program.

## Context

**The user's words**: *"Text mode and model mode should fall into the right
panel; users are used to viewing the change in refinement after making edits to
the parameters."* That is a workflow argument, and it is a good one — every
other panel in the app is beside the plot, and the two that are not are the two
where an edit most obviously wants a before/after.

**This re-opens a decision that was taken twice, on grounds that were sound.**
WP-1013 made the text pane a mode over the whole window because five tabs
already filled the sidebar and its content is line-oriented — the `.pxt` columns
are aligned precisely so a rectangular selection can hit one field, which a
340-560 px sidebar undoes. WP-1014 made the model pane a mode for two further
reasons: an atom table is eight columns wide, and it is the only pane that must
work with **no project open at all**, which no tab can. WP-1029 then declined to
re-litigate either, and settled the *control* instead — one segmented
`[ Plot | Model | Text ]` in the header (`App.svelte:81-85`).

**What has changed since, and it is the whole case for revisiting**: WP-1029
made the panel column draggable. `.side` is `flex: 0 0 clamp(340px, 38%, 560px)`
until a drag replaces it with a number, and its `max-width` is **72 %** of the
window (`App.svelte:762-773`); `fitColumns` re-clamps a stored width at render
so one chosen at 1500 px cannot leave a column 24 px wide at 1000 px
(`lib/resize.ts:61-71`). So "the sidebar is too narrow for this" may simply no
longer be true — but **nobody has measured it**, and that is task 1.

### The recon that comes first

The user chose "tabs, with a full-window escape hatch kept" **without numbers in
front of them**. The decision stands; this WP's first job is to put the numbers
behind it, and to say so if they contradict it:

- The Model pane's **minimum content width** — it is three columns today
  (`Model.svelte`, with two `Splitter` grips at `:805-809` and `:873-877`), and
  the atom table is the widest content. Measure at what width it stops being
  readable, on NAC (four species, aniso) rather than on a two-atom cell.
- Whether the atom table fits at **560 px**, the current `clamp` ceiling, and at
  the 72 % `max-width`.
- The `.pxt` document's natural column width — the format is column-aligned by
  design, so the number is the longest rendered line on a real project, not a
  guess.

If those numbers say the pane cannot work as a tab even dragged wide, **report
back rather than shipping a cramped tab**: the escape hatch would then be the
primary surface and the tab a shortcut to it, which is a different design and
the user should get to choose it with the measurements in hand.

### What the change touches

- **The tab strip goes eight wide.** It is already six
  (`App.svelte:630-637`: Parameters, Plan, Peaks, Report, History, Build) —
  WP-1013 predicted five was the limit and it has been over that since WP-1027.
  **Settle overflow before adding tabs, not after**: a strip that silently
  truncates is worse than the mode buttons it replaces.
- **Everything stays mounted.** The current panels are hidden with
  `class:hidden`, never unmounted, because switching must not throw away a
  filter, a pending edit, an unsaved stage list or a two-node comparison
  (`App.svelte:638-639`); the text pane additionally builds its editor on first
  entry and keeps a typed buffer across a visit elsewhere. Both properties must
  survive the move.
- **`Model.svelte` reflows to one column when narrow**, its 3D column becoming a
  collapsible section rather than a third of a 400 px pane. Note what that
  interacts with: the viewer's plot needs its `ResizeObserver`, because plotly's
  `responsive: true` listens for **window** resizes only and an oversized canvas
  swallows the clicks of any control under it — a trap that has now bitten two
  panels.
- **The full-window hatch stays** for both, and the header control has to make
  "where am I" and "where can I go" one reading, which is WP-1029's stated
  reason for the segmented three. Two routes to one pane is the cost the user
  accepted; the control must not become two controls again.
- **The open/recent screen rides along.** The import wizard *is* `Model.svelte`
  (`showWizard = !project || wizardOpen`, `:134`), so once Model is a tab the
  wizard is in the right panel. Half the route back already exists — the
  palette's "Import a new project" sets `wizardOpen` with a project open
  (`Model.svelte:451`, `App.svelte:414-415`). What is missing is the **recent
  list inside the wizard** rather than only in the empty state
  (`App.svelte:589-604`, fed by `api.recent()` only when `GET /api/project`
  fails with `NO_PROJECT`), a header control beside the palette entry, and a
  decision about what "open another" does to the session in flight.

### Rules that bind the implementation

- **Widths persist in `ProjectDoc.ui`, owned by the shell**, and the splitter
  **reports a size and never writes one** (`onsize(size, done)`, false on every
  pointer move and true once on release). Do not add a second splitter.
- **A stored size must be re-clamped at render**, not only at drag —
  `fitColumns` exists because a drag clamps against the extent it happens in and
  nothing clamps a width that outlives its window.
- **An effect that reads the project *object* refires on every `ui`-only PATCH**
  — Model reloads on a boolean `$derived` keyed to the project *path*, or a pane
  drag refetches three routes and the 3D geometry with the head unmoved.
- A drag is **refused persistence while a run is in flight** (409); that is a
  known wart filed as a freeze question in [1003](1003-api-freeze-pypi.md), not
  this WP's to settle.

## Non-goals

- **Not the repairs** ([1032](1032-gui-repairs.md)) or the fitted range
  ([1033](1033-plot-range-regions.md)).
- **Not a redesign of the panels themselves** — this moves them and reflows
  `Model.svelte`; it does not restyle the parameter table.
- **Not the manual** ([1017](1017-gui-manual-onboarding.md)); write into its
  `### Inherited` on sign-off, because this WP changes the two sentences that
  chapter would have opened with.
- **Not multi-project**: "open another" replaces the session's project as it
  does today; nothing here opens two at once.

## Tasks

- [ ] **Recon**: the three measurements above, on NAC, at 1500/1200/1000/860 px.
      Write the numbers into this file. If they contradict the tabs decision,
      stop and report rather than shipping a cramped tab.
- [ ] **Tab-strip overflow** settled first — scroll, wrap, or a grouped
      overflow control — with a mount test that a hidden tab is still reachable.
- [ ] **Model and Text as tabs**, both still always-mounted, the text pane still
      building its editor on first entry and keeping its buffer.
- [ ] **`Model.svelte` reflows to one column** below a threshold, 3D collapsible,
      with the `ResizeObserver` intact for the viewer.
- [ ] **The full-window hatch**, reachable from one control that still answers
      "where am I" in one reading, and from the palette.
- [ ] **Recent list inside the wizard**, a header route to it with a project
      open, and the "open another" behaviour decided and written down.
- [ ] Tests: mount tests for tab reachability, the reflow threshold's pure
      function, buffer survival across a tab switch, and the wizard's recent
      list with a project open.

## Acceptance

```sh
npm --prefix gui test && npm --prefix gui run check
.venv/bin/python -m pytest tests/test_gui_server.py -q
.venv/bin/python -m ruff check src tests examples
npm --prefix gui run build && .venv/bin/python -m pytest tests/test_gui_dist.py -q
```

And in a real browser on the NAC project (COD 1000236 + `11BM_NAC.fxye`), in
both themes at 1500 px and at 1000 px: edit a cell parameter in the Model tab
and **watch the plot beside it**, which is the entire point of the WP; then
confirm the atom table is readable at the width the recon said it needed, and
that a typed text buffer survives a trip to Parameters and back.

jsdom has no layout, so the reflow's *behaviour* is testable and its *effect* is
not — the screenshot is the check. Playwright's viewport option is
`newContext({ viewport })`, **not** `viewportSize`, which is silently ignored.

## References

- `docs/wp/1013-text-pane-sync.md` and `docs/wp/1014-import-structure-editing.md`
  — the two decisions this WP revisits, and why they were right when taken.
- `docs/wp/1029-gui-usability.md` — the splitter, the segmented control, and
  `fitColumns`.
- `gui/CLAUDE.md` — the always-mounted rule and the `responsive: true` trap.

## Handover log

- **2026-08-04** — created from a user's list after driving the shipped GUI,
  alongside [1032](1032-gui-repairs.md), [1033](1033-plot-range-regions.md),
  [1035](1035-symmetry-surfaced.md) and
  [1036](1036-crystal-system-settings.md). Nothing is started.

  **This is the only redesign in the set, and it was separated out for that
  reason**: the other GUI items are hour-sized repairs that must not be held
  hostage to it.

  **The user's decision is on record and is binding: tabs, with the full-window
  mode kept.** It was taken without measurements — a planning failure worth
  naming, since the numbers were available and nobody fetched them — so task 1
  fetches them, and contradicting the decision *with numbers* is a legitimate
  outcome the user asked to hear about.

  **The strongest argument for the change is not aesthetic.** Every other panel
  is beside the plot; the two that are not are the two where an edit most wants
  a before/after. The strongest argument against is still WP-1013's and it has
  not been refuted, only made measurable: the `.pxt` format's columns are
  aligned so a rectangular selection can hit one field, and a narrow pane undoes
  that. Both of those sentences should survive into the manual.

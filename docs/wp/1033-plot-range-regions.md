# WP-1033 — 2θ limits and excluded regions, visible and selectable

Milestone: v1.0 · Status: ⬜
Depends on: **1032** (strictly — both edit `Plot.svelte`; see below) · 1005,
1008, 1009 (landed)

### Inherited from [1032](1032-gui-repairs.md) (added 2026-08-05, on its close)

**`Plot.svelte` moved under you**, which is what the strict dependency was for.
Four things to know before editing it:

- The reflection ticks are on **`yaxis3`**, a band at `[0.225, 0.275]` between
  the two subplots (`lib/plot.ts:tickBand`). The gap is no longer free — a
  shaded fit-range or excluded region must be drawn as a **shape** across the
  paper, or on `xaxis`, not by claiming that domain.
- **Which curves are drawn is now a client choice** (`hidden`, an *exception*
  list, `curveToggles`). A shaded region is not a curve and should not join it:
  it is a fact about the protocol, and the WP-1015 rule that kept the toggles
  unpersisted is the same rule that says a *region* belongs in `ProjectDoc`.
- **The `ResizeObserver` is coalesced** through `lib/resize.ts:coalesce` — one
  `Plots.resize` in flight, at most one queued. If a region drag ends up
  calling `relayout` per pointer move, measure it the way task 1 did (an init
  script, before `window.Plotly` is assigned — see this WP's handover for why a
  later patch is invisible) rather than assuming it is cheap: one redraw of the
  NAC pattern is ~111 ms.
- Right-click now **removes a peak**; a region gesture must not collide with it
  while the Peaks tab is active, and the gestures line under the header is
  where any new gesture has to be named.

## Goal

A user can see which part of the pattern is being fitted and change it from the
plot: the fit range and every excluded region shaded where they act, selectable
by pointer, with the typed route the text document already has — and one
authority, so the GUI, the `.pxt` document and the exported figures cannot
disagree about what was masked.

## Context

**The feature exists and is invisible.** Nothing here adds a model, a verb or a
persistence path; all three landed with WP-1005 and WP-1009. What is missing is
that no renderer in the package draws them, and no pointer sets them.

### What is already implemented (read at `660c950`)

- **Two fields, one verb.** `ProjectDoc.two_theta_limits` and
  `ProjectDoc.excluded_regions` (`schemas/project.py:99,106`);
  `Project.set_excluded_regions` (`project.py:275-284`) writes the document
  *and* the in-memory `PatternData` together, "because the two must not
  disagree", and deliberately does **not** rebind history — the fingerprint is
  over the measured arrays, so excluding a region leaves every node replayable.
- **The masking is real, not a weighting.** `PatternData.in_range_mask`
  (`schemas/pattern.py:58-65`) drops the points; `compile_model` applies it as
  its first act and intersects it with `two_theta_limits`
  (`model/forward.py:1075-1082`), raising if fewer than ten points survive. So
  excluded channels never enter the residual, and therefore never enter Rwp or
  χ². The same mask is honoured by background anchor selection
  (`background/select.py:68,108`), background diagnostics
  (`background/diagnostics.py:153`), peak picking (`indexing/peaks.py:307`), the
  GUI's raw peak-plot pattern (`gui/session.py:1118`) and the peak-editor cache
  key (`gui/session.py:1136`) — so changing an exclusion correctly invalidates
  the fitted peak list.
- **The wire verb accepts both already.** `POST /api/project` takes
  `{mode, two_theta_limits, excluded_regions, ui}` and rejects anything else
  (`gui/session.py:341-353`). The frontend's `api.patchProject`
  (`gui/src/api.ts:102`) is called from exactly one place, always with
  `{ui: …}` (`App.svelte:166`).
- **The text document is the only surface.** `textdoc.py:318-322` renders
  `limits 3 60` and `excluded 7.5 8  24 25.2` (or `none`), `:531-548` parses
  them — `excluded` takes pairs and refuses an odd count in its own words — and
  `:991-994` applies through `Project.set_excluded_regions`, echoing the call.
- **Nothing draws them.** There are no `layout.shapes` anywhere in the frontend,
  and `viz/` has no `excluded_regions` consumer at all: not `plot_result`, not
  `plot_for_vlm`, not `write_html`. A region you excluded is invisible in every
  picture the package produces.

### The two rules this WP is really about

**1. These are protocol, not drawing choices, and must not look like the knobs
beside them.** The residual selector and the intensity scale are session-local
and unpersisted, because storing one would make a picture the project's opinion
(WP-1015's rule, applied in `Plot.svelte:73-75`). An excluded region is the
opposite: it changes what is fitted, it persists in `project.json` **on the
verb**, and it lives in the document precisely because *a history node cannot
record what was excluded when it ran* (`schemas/project.py:101-105`). Two kinds
of knob will now sit on one plot; if they wear the same clothes the user cannot
tell which one changes the answer.

**2. A fourth drag meaning is the risk in this WP.** The canvas already carries
peak-add (a plain click on empty space), peak-move (a drag captured from plotly
inside `grabToleranceDeg`), shift-toggle, right-click, and plotly's own zoom
drag — all in `Plot.svelte:324-394`, and all gated on `peaksActive`. WP-1027
measured what happens when two of those overlap: a 10 px grab radius is ±1.9° at
the survey view, so a zoom drag starting 0.9° from a marker silently **moved a
line 11°**. The repair was to derive the radius from the fitted FWHM
(`grabToleranceDeg` = min(10 px, 1.5× median FWHM), `lib/peaks.ts:97-106`), so
that a drag over a subpixel line falls through to the zoom.

**Settle the arbitration before writing a handler.** The obvious candidates:
region selection lives on its own modal state (a "select range" toggle, the way
`peaksActive` gates the peak gestures), or it takes a modifier, or plotly's own
`dragmode: "select"` is turned on while the control is armed. Whatever is
chosen, the rule that survived WP-1027 must survive here: **an ambiguous drag
must do the harmless thing**, and every pointer verb keeps a non-pointer route —
which for this one already exists as the `.pxt` `limits`/`excluded` lines, plus
typed bounds in the panel.

### The `viz/` question, which is a decision and not a task

The GUI would shade regions the exported PNG and HTML do not, making them two
authorities on one picture. That is the shape of the bug WP-1029 (s) found: five
open-coded weighted residuals under three policies, where the pin that caught it
compared **what each renderer drew** against **what the route sent**, because
three re-derivations of one formula agree with each other while all being wrong.
Decide explicitly whether `viz/` shades too — and if the answer is no, write
down why, because the next person will ask.

## Non-goals

- **Not the repairs** in [1032](1032-gui-repairs.md), which lands first.
- **Not multi-pattern.** `Project.open` refuses a project holding more than one
  pattern (`project.py:196-201`); a per-histogram range is a later milestone's.
- **No `.pxt` format change.** `limits` and `excluded` are already in the
  grammar; if this WP finds it needs a new line, that is a format-version
  question and it stops here.
- **Not a new masking semantics.** Excluded points are dropped, not
  down-weighted; nothing here revisits that.

## Tasks

- [ ] **Shade both from `ProjectDoc`** through `layout.shapes` — the fit range
      as what is *outside* it, the excluded regions as bands — legible in both
      themes, from the custom properties, and correct under every intensity
      scale (a shape in log space is not a shape in linear space).
- [ ] **Settle the gesture arbitration and write the argument down** where the
      handler lives, with WP-1027's measured overlap as the precedent. Then
      implement selection.
- [ ] **Typed bounds in the panel** as the non-pointer route, refusing an
      inverted or empty range in the verb's own words.
- [ ] **Send through `POST /api/project`**, which means `api.patchProject` stops
      being a `{ui: …}`-only call site — check that the 409-while-running rule
      still reads correctly for a settings-only patch (the open question in
      [1003](1003-api-freeze-pypi.md)'s `### Inherited` about `ui`-only patches
      is adjacent, and this WP must not settle it unilaterally).
- [ ] **The two surfaces agree**, asserted: a region set on the plot renders in
      the `.pxt` document, and one typed into the document shades on the plot.
- [ ] **Decide the `viz/` question** and record the answer either way.
- [ ] Tests: vitest for the shape-building and range-arithmetic pure functions,
      a jsdom mount test for the controls, a `tests/test_gui_server.py` case for
      the settings round trip, and obs/calc/diff PNGs to `tests/output/` if
      `viz/` changes.

## Acceptance

```sh
npm --prefix gui test && npm --prefix gui run check
.venv/bin/python -m pytest tests/test_gui_server.py -q
.venv/bin/python -m ruff check src tests examples
npm --prefix gui run build && .venv/bin/python -m pytest tests/test_gui_dist.py -q
```

Plus, in a real browser on the NAC project (COD 1000236 + `11BM_NAC.fxye`):
exclude a region by pointer, confirm it shades, confirm the `.pxt` document
shows it, re-run, and confirm the fit's channel count dropped by the number of
points in the region. **The channel count is the check that the shading is
telling the truth** — a band drawn over points still in the residual is worse
than no band at all.

## References

- WP-1027's measured pointer overlap (`docs/milestones/v1.0.md`, the 1027 close
  entry) — the precedent for arbitrating a new drag.
- WP-1029 item (s) — why two renderers of one fact is a bug shape rather than a
  cosmetic mismatch.
- `docs/wp/1005-project-container.md` — why `excluded_regions` lives in the
  document and not in a history node.

## Handover log

- **2026-08-04** — created from a user's list after driving the shipped GUI,
  alongside [1032](1032-gui-repairs.md), [1034](1034-panel-layout.md),
  [1035](1035-symmetry-surfaced.md) and
  [1036](1036-crystal-system-settings.md). Nothing is started.

  **The feature is done; only the pixels are missing.** The model, the mask, the
  verb, the persistence and the text surface all exist and were read at
  `660c950` — the citations above are a map, and a successor should not go
  looking for the backend half.

  **This WP is sequenced after [1032](1032-gui-repairs.md) deliberately**, and
  the reason is not politeness: both edit `Plot.svelte`, and the repo already
  carries the scar of concurrent sessions in one working directory — WP-1018's
  files are committed inside WP-1004's and WP-1006's commits, whose messages
  name the wrong WP, and `git log -- src/pxrdref/indexing/` misleads because of
  it. One worktree per session, or one session at a time on this file.

  **The one thing to get right** is the second rule above: an excluded region
  and a residual selector are both knobs on one plot, and only one of them
  changes the answer. If they end up looking alike, this WP has made the GUI
  worse in a way no test will catch.

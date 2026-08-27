# WP-1210 — The peak layer: hide it, tell it apart, data-only

Milestone: v1.2 · Status: ✅ 2026-08-27 — the layer has its own colours, its own tab and a way off
Depends on: WP-1201

## Goal

The picked-peak markers and their fitted curves can be hidden, look like
nothing else on the plot, appear only where they can be edited, and one click
leaves only the data.

## Context

The user's notes: hide picked peak markers; hide the individual fitted peaks
(which "are not clearly explained"); "an easy way to hide everything except
the data"; and the picked-peak fit line and the model's calculated line "both
the same colour".

Findings (2026-08-25):

- The peak layer is `peakTraces()` (`Plot.svelte:389-447`), pushed
  unconditionally at `:323`: `peak fit` (the joined per-group `y_fit`,
  `scattergl`, width 1.4, colour `--accent`, `hoverinfo: "skip"`), the raw
  view's `(y−fit)/σ` strip, `peaks` (markers plus the σ whiskers as
  `error_x`, capped at 3×FWHM), and the empty `hovered` ring trace.
- `curveToggles()` (`lib/plot.ts:317-345`) derives from the window payload
  and never mentions peaks; the hideable set is `obs`, `masked`, `calc`,
  `bkg`, `diff`, `ticks:<phase>`. No "data only". On the raw view the toggle
  row often does not render (`{#if toggles.length > 1}`, `Plot.svelte:838`).
- Colours: `peak fit` takes `--accent` (`#1f5fa8` light), which **equals
  `--plot-diff`**; `--bad` for unusable markers equals `--plot-calc`
  (`#c23b22`); `calc` is `--plot-calc` at width 1.2 (`Plot.svelte:292-295`).
  The two curves are the same weight, both solid, both on the intensity
  axis, and `y_fit` includes the detection envelope (`gui/peaks.py:395`), so
  they sit at the same counts. Neither has a legend entry.
- The plot is an editing surface **only while the Peaks tab is active**
  (WP-1027), but the layer is drawn in every tab.
- `hidden` is an exception list and unpersisted (`Plot.svelte:124-126`), so
  a curve a later build adds arrives drawn (WP-1032).
- The phase palette rotates in OKLab at a distance floor (WP-1029).

## Non-goals

- Candidate cells on the plot (WP-1211); jitter (WP-1212).

## Tasks

- [x] `curveToggles` grows `peaks` and `peak fit` when a list exists;
      `Plot.svelte` guards `peakTraces` with `shows()`; a **data only**
      button that hides every id but `obs` and restores on second click.
- [x] Tokens `--plot-peak` and `--plot-peakfit` in `app.css`, both themes,
      validated against every other plot token in OKLab (the phase-palette
      floor, asserted in `plot.test.ts`); the fit curve dashed and named in
      the legend and the hover; unusable markers on a tone that is not
      `--plot-calc`.
- [x] The layer drawn only while the Peaks tab is active (a prop from App),
      with the layer's absence stated in the curve toggles.
- [x] Browser pass with a result and a peak list: four distinguishable
      curves in both themes; dist.

## Acceptance

```sh
npm --prefix gui test && npm --prefix gui run check
```

A light and a dark screenshot with obs, calc, bkg, peak fit and markers all
present and each identifiable without the legend.

## References

- WP-1032 (hiding is by exception), WP-1029 (OKLab distance).

## Handover log

### 2026-08-27 — the layer has its own colours, its own tab and a way off

Three complaints about the peak layer turned out to be one defect with three
faces, and the sharpest of them was exactly true rather than approximately:
the picked-peak fit curve and the model really were the same colour, because
the layer had no colours of its own and borrowed the app's chrome, which on
the light theme *is* the difference and calculated curves to the last digit.
The layer now has two tokens, is drawn only on the tab where a marker can be
edited, can be switched off like any other curve, and one button clears the
plot to the measured points and puts the picture back. What a reader gets is
a plot where every mark can be named without consulting the legend — and a
gate that will refuse the next panel WP a colour that collides with one
already there.

The part worth carrying: **the plot's free hue space is nearly spent**.
Measured while choosing this pair, only magenta and green clear the phase
palette's 0.13 OKLab floor against the shipped set — violet lands 0.10-0.12
from the difference curve and the obvious alert tone for an unusable marker,
`--warn`, is 0.053 from calculated. Magenta is now taken. A future mark should
plan to spend *no* colour and carry its identity on the mark, which is what
this layer does for peak state (hollow = unusable, diamond = human-placed)
rather than spending a third.

**Done.** All four tasks. `curveToggles` grows `peaks`/`peak fit` from a
`PeakLayer` passed beside the window payload; `dataOnlyHidden`/`isDataOnly`
are pure and over the same unpersisted `hidden` exception list, with
`Plot.svelte` holding the previous list so the second press restores rather
than showing everything. `--plot-peak`/`--plot-peakfit` in all three theme
blocks, one hue family (334°) in two tones, the fit curve dashed and named in
the legend and the hover, unusable markers on the recessive ink the masked
channels already use. The layer is gated on `peaksActive`, and its two toggles
are listed and **disabled carrying the reason** when it is away.

**Measured**, all darwin/arm64 on this worktree's own venv, `[dev]` — jax and
torch absent. gui: **475 passed**, against WP-1209's recorded 467, so +8 (5 in
`plot.test.ts`, 3 in `App.test.ts`); `svelte-check` 0 errors / 0 warnings over
378 files. Python fast selection `-m "not slow"`: **3148 passed / 117 skipped**
in 152.71 s, against 1209's **3138 / 117** on the same extras and platform —
exactly the ten `tests/test_gui_palette.py` adds, and **no new skip**. The full
selection was **not** run and should not have been: nothing here can move a
refinement number (root CLAUDE.md § Numbers).

Browser pass in Chrome on the NAC example, fitted in the served session (Rwp
0.0932, 86 lines picked / 74 usable), both themes. Light — markers `#8c257e`,
fit `#c158b0` dashed, unusable `#6b6b66`, against calc `#c23b22` and Δ/σ
`#1f5fa8`. Dark — `#e687d5` / `#b156a2` / `#9a9a94` against `#e56a52` and
`#5897dd`. `data only` leaves exactly `observed`; the second press restores,
a hand-hidden phase still hidden. On the Report tab the layer is absent and
its toggles disabled with the sentence.

**Gotchas**, all three costing time here.

- **`peaksActive` is a drawing input.** The tab gate looked complete and did
  nothing: nothing repainted on a tab change, so the layer stayed on screen
  from the previous paint. It belongs in the repaint effect beside the knobs.
  `App.test.ts`'s hover-link test is what caught it — the ring stopped being
  the last trace — which is also why `ringAt` is now found by name.
- **A served session holds no result on open.** A result is not persisted,
  only history state, so a browser pass wanting calc/bkg/Δ must run the fit
  *through the server*; fitting in a preparing process leaves the page on the
  raw view and looks like a drawing bug.
- **`POST /api/settings` takes `{"ui": {"theme": …}}`.** A bare `{"theme": …}`
  is a 400, which reads as "the theme did not apply" when driving a browser.
  Drive it with `--state-dir` at a scratch path too, or the pass rewrites the
  person's own theme.

**Not repaired, and predating this WP:** with the residual hidden its subplot
keeps its domain, so `data only` leaves a quarter of the plot empty. Hiding
`Δ/σ` alone has always done that; filed into WP-1212, which is the WP that
touches this layout.

**Where the OKLab assertion lives, and why it is not where the WP said.** The
task named `plot.test.ts`; it is `tests/test_gui_palette.py` instead, reading
`app.css` and using `structure3d._oklab_distance` — the one distance this
package has, where a TypeScript port would have been a second answer to it.
`plot.test.ts` asserts the plumbing (`curveColors` reads each property, falls
back per property), which is the half that belongs in a client test. The
Python file also **names the two pairs the shipped palette already misses**
(light bkg/diff 0.129, dark obs/diff 0.124) rather than exempting them
quietly, holds them at 0.12 so they cannot get worse, and fails if a third
appears — retuning a shipped curve colour was not this WP's.

*Next.* WP-1210 is closed; the successor is [WP-1211](1211-candidate-overlay.md)
(the candidate overlay), whose `### Inherited` now carries the data-only
seam, the hue-space measurement and the tab-gating rule. WP-1212 and WP-1213
have their own notes — 1212's matter most, since this WP moved the line
numbers its findings quote and added a new occasion for the autorange it is
chasing.

- **2026-08-25** — created from the v1.2 triage.

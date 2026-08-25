# WP-1210 — The peak layer: hide it, tell it apart, data-only

Milestone: v1.2 · Status: ⬜
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

- [ ] `curveToggles` grows `peaks` and `peak fit` when a list exists;
      `Plot.svelte` guards `peakTraces` with `shows()`; a **data only**
      button that hides every id but `obs` and restores on second click.
- [ ] Tokens `--plot-peak` and `--plot-peakfit` in `app.css`, both themes,
      validated against every other plot token in OKLab (the phase-palette
      floor, asserted in `plot.test.ts`); the fit curve dashed and named in
      the legend and the hover; unusable markers on a tone that is not
      `--plot-calc`.
- [ ] The layer drawn only while the Peaks tab is active (a prop from App),
      with the layer's absence stated in the curve toggles.
- [ ] Browser pass with a result and a peak list: four distinguishable
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

- **2026-08-25** — created from the v1.2 triage.

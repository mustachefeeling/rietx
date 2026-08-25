# WP-1213 — The hover readout

Milestone: v1.2 · Status: ⬜
Depends on: WP-1212

## Goal

The plot's hover information never covers the data: it is a readout strip
under the plot, with a spike line on the plot marking the 2θ.

## Context

The user: "The tooltip frequently covers a large part of the data. Consider
where to put it so it's visible and useful but not in the way."

Findings (2026-08-25): `hovermode: "x unified"` with a `hoverlabel` from the
theme tokens (`Plot.svelte:210-211`, `lib/plot.ts:63-72`); per-trace
`hovertemplate`s for observed, masked, calculated, background, ticks and
peaks (`Plot.svelte:273-436`); the `diff` and raw-residual traces have
neither template nor `hoverinfo`, so they add plotly's default line to the
box. There is no positioning: plotly offers none for the unified box beyond
`hoverlabel.align`, so "put it elsewhere" is not a setting.

Decision (the plan, 2026-08-25): a readout strip. `hovermode: "x"` with
`showspikes` on the x axis and `hoverinfo: "none"` on every trace; a
`plotly_hover` handler fills a strip of the plot's control rows with 2θ, d,
obs, calc, bkg, the chosen residual, the nearest tick per phase and the
nearest peak (with its index). The strip is under the plot, so it is a
control row under a canvas: the `ResizeObserver` rule (WP-1015/1029) holds.
`plotly_unhover` clears it. The series panel's plot is SVG and keeps its own
hover (WP-1016); this WP is `Plot.svelte` only.

## Non-goals

- The peak-row hover link (the ring, WP-1212).
- The series plot.

## Tasks

- [ ] `lib/plot.ts`: `readout(w, x, ticks, peaks) -> Readout` (pure; nearest
      index by binary search; tested).
- [ ] `Plot.svelte`: hover mode and spikes; the strip; every `hovertemplate`
      and `hoverlabel` deleted; the strip's height in the resize path.
- [ ] Browser pass: hover across a peak cluster in both themes; no box over
      the data; dist.

## Acceptance

```sh
npm --prefix gui test && npm --prefix gui run check
grep -c "hovertemplate\|hoverlabel" gui/src/panels/Plot.svelte   # 0
```

## References

- WP-1029 (the residual and scale knobs the strip reads).

## Handover log

- **2026-08-25** — created from the v1.2 triage.

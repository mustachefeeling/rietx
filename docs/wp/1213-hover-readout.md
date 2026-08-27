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

### What the strip has to carry

Folded in from the four WPs that shipped under it (their `Inherited` notes,
consumed 2026-08-27):

- **Every number reads as its table reads it.** A position is
  `formatPosition(tt, esd)` (`lib/peaks.ts`: four places, esd in the last place
  below `POSITION_ESD_MAX_DEG` = 1°, nothing above) and an intensity is
  `formatIntensity(I, imax, flags)` over `imax = intensityScale(rows)` — the
  raw area is in counting units and means nothing on its own, so a readout
  printing `1.2e+3` beside a table saying `100.0` is two answers (WP-1209). For
  a value with an esd, `formatValue`/`formatEsd` write `35.09 ±110` where the
  esd has swallowed the value and `12346(56)` otherwise.
- **The strip names every curve**, which is a *requirement* carried from
  WP-1210 rather than a nicety: the picked-peak fit curve stopped being
  `hoverinfo: "skip"` and started naming itself in the unified box, because a
  reader had no way to tell it from the model. Deleting the templates for a
  strip means the strip says which curve is which.
- **The peak layer is drawn only on the Peaks tab**, so a readout that quotes a
  hovered peak has nothing to quote elsewhere: the strip's content is
  tab-dependent because the plot's is (WP-1210). A peak's state is said in the
  corpus's words (`peak_origins`/`peak_flags` labels, WP-1209), never in a
  third spelling or a colour key.
- **The candidate overlay's `hkl` and `line` are already served and
  deliberately not drawn** (WP-1211): `GET /api/index/ticks` returns
  `two_theta`, `hkl` and `line` as parallel arrays sorted by 2θ, so "the line
  under the pointer is (1 0 4)" needs no new wire surface. Under `hovermode: "x
  unified"` a candidate row would appear in the box at every pointer position,
  which is exactly why the overlay has no hover today and why a strip of its own
  is the right place. Two honesty rules ride with it: past
  `MAX_CANDIDATE_TICKS` the drawn set is thinned by rank, so a readout quotes no
  ordinal and no count (the status line owns both), and the overlay sits on
  `yaxis4` at y ∈ [0, 1] — this layer's `y` means nothing and only its `x` does.

### Constraints from the layer under it (WP-1212)

- **The axes are explicit after every paint** (`pinPatch`, `movedAxes`,
  `userRanges`), so a hover cannot move them however it is drawn, and
  `autorange === false` no longer answers "has the user zoomed". A pixel→2θ
  conversion reads `drawnRange(ax)`, not `ax.range`, which can be stale on a
  fresh plot.
- **The hover ring is a plain `scatter`, not `scattergl`**: every gl trace on a
  subplot shares one `_scene` whose batches are indexed by position, an *empty*
  gl trace is given no index, and a select drag then threw once per pointer
  move. Any new trace that is empty most of the time — a spike marker, a
  readout cursor — takes the same treatment.
- **A hover already costs a `react` where a candidate is concerned**: running
  the pointer down six candidate rows costs 11 reacts at 19-33 ms, while a
  peaks-table hover costs a single `restyle`. If the readout gives the overlay a
  hover of its own, the cheap shape is WP-1032's: one trace whose coordinates
  move.
- **The residual subplot's empty quarter is still owed.** 1212 decided against
  collapsing it (the shared x axis is anchored to `y2` and the tick band's
  domain is the gap between the panels, so collapsing moves three domains and an
  anchor together). This WP adds a strip under the plot, which is the next time
  that space is worth arguing about.
- **`.select-outline` is the panel's precedent for a stylesheet rule reaching
  into plotly's own nodes** for something other than a cursor, and it carries
  `!important` because plotly writes `fill-opacity: 0` inline. If the readout
  restyles any plotly-owned node, that is the precedent and the trap.

### A declined finding, inherited (WP-1209)

`INTENSITY_UNMEASURED_FLAGS` (`no_intensity`, `fit_failed`) is a TypeScript
literal held to the corpus vocabulary by name only. `gui/CLAUDE.md`'s rule is
that a flag's *meaning* is served, never re-derived — `unusable_flags` rides on
`/api/peaks` for that reason — so a python flag added later meaning "the area is
a bound, not a measurement" would be used as Imax and printed as a real relative
intensity, and the name-only test stays green. The fix is a
`PEAK_INTENSITY_UNMEASURED_FLAGS` constant in `schemas/indexing.py` served
beside `unusable_flags` and read by `formatIntensity`; 1209 declined it as a
wire-contract change outside a table WP, and it stays declined here for the same
reason — this WP quotes `formatIntensity`, it does not touch it.

Method (from `gui/CLAUDE.md`): **measure first**, in Chrome via
playwright-core; when a claim is about an event, count the events.

## Non-goals

- The peak-row hover link (the ring, WP-1212).
- The series plot.

## Tasks

- [x] `lib/plot.ts`: `readout(w, x, ticks, peaks) -> Readout` (pure; nearest
      index by binary search; tested).
- [ ] The two facts the strip needs and no route serves it: the source's
      wavelengths (d = λ/2 sin θ, and which line a candidate tick belongs to)
      on `project_doc`'s data arm, and the served `hkl`/`line` carried through
      `CandidateOverlay` in `App.svelte`.
- [ ] `Plot.svelte`: hover mode and spikes; the strip; every `hovertemplate`
      and `hoverlabel` deleted; the strip's height in the resize path.
- [ ] Browser pass: hover across a peak cluster in both themes; no box over
      the data; dist.
- [ ] `gui/CLAUDE.md`: the rule this WP leaves (one clause plus the
      measurement pointer).

## Acceptance

```sh
npm --prefix gui test && npm --prefix gui run check
grep -c "hovertemplate\|hoverlabel" gui/src/panels/Plot.svelte   # 0
```

## References

- WP-1029 (the residual and scale knobs the strip reads).

## Handover log

- **2026-08-25** — created from the v1.2 triage.

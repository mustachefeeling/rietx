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

### Inherited

From **WP-1209** (2026-08-27, shipped):

- A hovered peak's position and intensity should read as the table does:
  `formatPosition(tt, esd)` (`lib/peaks.ts` — four places, esd in the last
  place below `POSITION_ESD_MAX_DEG` = 1°, nothing above) and
  `formatIntensity(I, imax, flags)` with `imax = intensityScale(rows)`. The
  raw area is in counting units and means nothing on its own; a readout
  printing `1.2e+3` beside a table saying `100.0` is two answers.
- For a parameter with an esd, `formatValue`/`formatEsd` now write
  `35.09 ±110` where the esd has swallowed the value (`esdSwallowsValue`) and
  `12346(56)` otherwise — one pair of functions for every readout.
- **A declined review finding, yours if you touch `formatIntensity`:**
  `INTENSITY_UNMEASURED_FLAGS` (`no_intensity`, `fit_failed`) is a TypeScript
  literal, held to the corpus vocabulary by name only. `gui/CLAUDE.md`'s rule
  is that a flag's *meaning* is served, never re-derived — `unusable_flags`
  rides on `/api/peaks` for that reason — so a python flag added later
  meaning "the area is a bound, not a measurement" would be used as Imax
  and printed as a real relative intensity, and the name-only test stays
  green. The fix is a `PEAK_INTENSITY_UNMEASURED_FLAGS` constant in
  `schemas/indexing.py` served beside `unusable_flags` and read by
  `formatIntensity`; 1209 declined it as a wire-contract change outside a
  table WP.

From **WP-1210** (2026-08-27, shipped):

- **There is one more `hovertemplate` than this WP's findings list, and it is
  deliberate**: the picked-peak fit curve used to be `hoverinfo: "skip"` and now
  names itself in the unified box, because a reader had no way to tell it from
  the model. When this WP deletes every template for a strip of its own, that
  naming is a *requirement* carried over, not a template to drop silently — the
  strip has to say which curve is which by name.
- **The peak layer is drawn only on the Peaks tab.** A readout that quotes a
  hovered peak therefore has nothing to quote elsewhere, and the strip's content
  is tab-dependent for that reason rather than by choice.
- The whisker cap note above (3×FWHM on the plot against `POSITION_ESD_MAX_DEG`
  = 1° in the table) is unchanged by 1210: the cap is still on the plot and the
  hollow marker is still what says "degenerate". The readout quoting the
  table's form remains the right answer.
- **The state of a peak is carried by its mark, not by a colour** — hollow for
  unusable, diamond for human-placed, one hue for the layer. A readout naming a
  peak should say the same thing in the corpus's words (`peak_origins` labels,
  the 1209 note above), never introduce a third spelling or a colour key.

From **WP-1211** (2026-08-27, shipped):

- **The candidate overlay's `hkl` is already served and deliberately not
  drawn**, and it is this WP's to draw. `GET /api/index/ticks` returns
  `two_theta`, `hkl` and `line` as parallel arrays sorted by 2θ, so "the line
  under the pointer is (1 0 4), Kα2, from the cell in row 3" needs no new wire
  surface. The reason it has none now is exactly this WP's subject: under
  `hovermode: "x unified"` plotly snaps *every* trace to its nearest point in
  x, so a candidate row would appear in the box at every pointer position — in
  the same box the peak hover link reads. A strip of its own does not have that
  problem, which is what makes it the right place.
- **Read `n_total` before quoting a count.** Past `MAX_CANDIDATE_TICKS` the
  drawn set is a sample thinned by rank, so "the 743rd predicted line" is a
  statement about the sample and not about the cell. The plot's status line
  already prints both numbers; a readout that names one line has to be honest
  the same way or say nothing.
- **The overlay is on `yaxis4`, at `y` ∈ [0, 1] in its own coordinates.** A
  readout doing its own hit-testing by pixel or by data coordinate needs to
  know that this layer's `y` means nothing — only its `x` does.

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

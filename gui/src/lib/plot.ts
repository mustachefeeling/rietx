/**
 * What the pattern plot draws, as pure functions (WP-1029).
 *
 * Two knobs the plot never had: **which residual** and **which y-scaling**.
 * Both are drawing choices, so both live in the client — but the residuals
 * themselves do not: `/api/result/window` sends all three, because what a
 * residual *is* depends on whether the file brought an esd column, and because
 * cumulative χ² has to be accumulated over every point and decimated afterwards
 * rather than summed from the decimated subset (which would understate it by
 * whatever the dropped points contributed). This module only *chooses*.
 */

import {
  formatHkl,
  formatIntensity,
  formatPosition,
  intensityScale,
  nearestPeak,
  type GroupCurve,
  type PeakRow,
} from "./peaks";
import { formatValue } from "./table";

export type ResidualKind = "delta" | "weighted" | "cumulative";
export type Scale = "linear" | "sqrt" | "log";

/**
 * The five curve colours, read from the custom properties `app.css` themes.
 *
 * The plot samples these at *draw* time — a theme change restyles the page by
 * CSS alone, but a canvas keeps whatever colours it was painted with, which is
 * why the panel repaints on the resolved theme (WP-1029 q) and why no hex may
 * live in the component: a fixed `#1f5fa8` difference curve was near-invisible
 * on the dark surface, and correct repainting cannot fix a colour that never
 * changes.  The fallbacks are the light values, for a page with no stylesheet
 * (jsdom); `read` is injected so this stays a pure function.
 */
export function curveColors(read: (name: string) => string): {
  obs: string; calc: string; bkg: string; diff: string; zero: string;
  mask: string; edge: string; peak: string; peakfit: string; candidate: string;
} {
  const pick = (name: string, fallback: string) => read(name).trim() || fallback;
  return {
    obs: pick("--plot-obs", "#8a8a8a"),
    calc: pick("--plot-calc", "#c23b22"),
    bkg: pick("--plot-bkg", "#6b7280"),
    diff: pick("--plot-diff", "#1f5fa8"),
    zero: pick("--plot-zero", "#88888888"),
    // The peak layer's two (WP-1210).  It had none: the markers took `--accent`
    // and the fitted curve `--bad`, which on the light theme *are* `--plot-diff`
    // and `--plot-calc` to the last digit — so the picked-peak fit and the model
    // were one colour, which is what the report said.  One hue family and two
    // tones, because the layer is one thing; what tells the marks apart is the
    // mark.  Each value's separation from every other plot colour is asserted
    // in `tests/test_gui_palette.py`, against the same OKLab floor the phase
    // palette uses.
    peak: pick("--plot-peak", "#8c257e"),
    peakfit: pick("--plot-peakfit", "#c158b0"),
    // The candidate overlay's one (WP-1211).  It could not share the peak
    // layer's: both are up on the same tab at the same time, and telling them
    // apart *is* the question — which of the picked lines does this cell
    // account for.
    candidate: pick("--plot-candidate", "#1a8f45"),
    // the two protocol colours (WP-1033).  `mask` is a wash rather than a
    // curve colour because what it marks is *absence from the residual*, and
    // `edge` is the boundary, which has to stay readable when the wash is
    // off-screen — a fit range shows only its edges once you zoom inside it.
    mask: pick("--plot-mask", "#1b1b1b14"),
    edge: pick("--muted", "#6b6b66"),
  };
}

/**
 * The hover box, themed from the same custom properties everything else reads.
 *
 * plotly's default hover box is a **light** surface, and nothing in this app
 * ever styled it: `hovermode: "x unified"` was set and every trace given a
 * `hovertemplate`, while `layout.font.color` was the themed `--fg`. On the dark
 * theme that is light-grey ink on a white box, which is what the report said.
 * Both plotly surfaces take it — the pattern plot and the structure viewer — so
 * it lives here rather than in either component, and neither learns a hex value
 * (WP-1032; the fallbacks are the light palette's, for a page with no
 * stylesheet).
 *
 * `bordercolor` is `--line` and not the trace colour: `x unified` draws **one**
 * box for every trace at that 2θ, so a per-trace border would be a colour picked
 * from whichever trace plotly happened to put first.
 */
export function hoverLabel(read: (name: string) => string): {
  bgcolor: string; bordercolor: string; font: { color: string; size: number };
} {
  const pick = (name: string, fallback: string) => read(name).trim() || fallback;
  return {
    bgcolor: pick("--panel", "#ffffff"),
    bordercolor: pick("--line", "#dcdcd6"),
    font: { color: pick("--fg", "#1b1b1b"), size: 11 },
  };
}

export interface Window {
  two_theta: number[];
  y_obs: number[];
  y_calc: number[];
  y_background?: number[];
  delta?: number[];
  delta_raw?: number[];
  cumulative_chi2?: number[];
  /** σ was *measured* (the file's esd column), not the Poisson fallback */
  weighted?: boolean;
  /** the measured points the protocol masks — never in the residual, and not
   *  in the result at all, which is why the server sends them separately */
  excluded?: { two_theta: number[]; y_obs: number[] };
  n_excluded?: number;
  /** the curves on screen were fitted over a different channel set */
  stale?: boolean;
}

/**
 * What is being fitted — the protocol, not a drawing choice (WP-1033).
 *
 * Both fields are `ProjectDoc`'s, both persist on the verb that sets them, and
 * both change the answer: excluded channels never enter the residual, so they
 * never enter Rwp or χ² either. That is the whole reason they may not wear the
 * same clothes as the residual selector and the intensity scale beside them —
 * those are session-local and deliberately unpersisted (WP-1015), because
 * storing one would make a *picture* the project's opinion.
 */
export interface Protocol {
  limits: [number, number] | null;
  regions: [number, number][];
}

/**
 * The shapes that shade what is not being fitted.
 *
 * `yref: "paper"` on purpose, and it is the load-bearing choice: a band in data
 * coordinates would have to be recomputed for every intensity scale (a rectangle
 * in log space is not the rectangle in linear space), and the reflection ticks
 * already own the only free y-domain there was — `TICK_BAND` at [0.225, 0.275].
 * In paper coordinates one rectangle spans both subplots *and* the tick band,
 * which is also the truth: an excluded channel is missing from the residual, not
 * only from the pattern.
 *
 * **Every shape is clipped to the measured range**, and that is a browser
 * finding rather than tidiness: a shape bound to a data axis takes part in
 * plotly's autorange, so bands drawn past the data to cover any future zoom-out
 * (the obvious implementation, and the first one here) *became* the range — on
 * the 0.5–59.99° NAC pattern the axis came back reading −40 to 100 with the
 * data squeezed into a fifth of the width. Clipping is also the truthful shape:
 * outside the measured pattern there are no channels to exclude, so there is
 * nothing there to shade.
 *
 * `layer: "below"` keeps the wash under the traces — a shaded band that dims the
 * points it covers would be saying something about the data rather than about
 * the protocol.
 */
export function maskShapes(protocol: Protocol, extent: [number, number],
                           colors: { mask: string; edge: string }): any[] {
  const [lo, hi] = extent;
  const band = (x0: number, x1: number) => (x1 <= lo || x0 >= hi ? null : {
    type: "rect", xref: "x", yref: "paper",
    x0: Math.max(x0, lo), x1: Math.min(x1, hi), y0: 0, y1: 1,
    fillcolor: colors.mask, line: { width: 0 }, layer: "below",
  });
  const edge = (x: number) => (x < lo || x > hi ? null : {
    type: "line", xref: "x", yref: "paper", x0: x, x1: x, y0: 0, y1: 1,
    line: { color: colors.edge, width: 1, dash: "dot" }, layer: "below",
  });
  const shapes: (any | null)[] = [];
  if (protocol.limits) {
    const [a, b] = protocol.limits;
    shapes.push(band(lo, a), band(b, hi), edge(a), edge(b));
  }
  for (const [a, b] of protocol.regions) shapes.push(band(a, b), edge(a), edge(b));
  return shapes.filter(Boolean);
}

/**
 * The axis ranges the user has dragged to, read back off plotly.
 *
 * **A redraw is not a reason to move the axes**, and before this every redraw
 * did: the layout handed to `react` carried no `range`, so plotly re-autoranged
 * over *everything drawn* — and what is drawn is not only the window. The peak
 * markers span the whole pattern (the list is not windowed) and so do the mask
 * shapes, which are `xref: "x"` and therefore take part in the autorange, the
 * same property `maskShapes` clips against above. Measured in Chrome on the
 * synthetic fixture, a drag to 9.97–14.66° came back as:
 *
 * | also on the plot            | axis after the refetch |
 * |-----------------------------|------------------------|
 * | nothing                     | 9.97–14.66 ✓           |
 * | a peak list                 | 4.57–24.85             |
 * | an excluded region at 4–5°  | 3.99–24.88             |
 * | a fitted range of 8–18°     | 3.00–24.94             |
 *
 * — so the zoom worked only on a plot with nothing else on it, which is why the
 * report was "horizontal zoom does not work when there are excluded regions".
 * The same react is what threw the view away on every peak edit: a toggle
 * repaints, and on the raw view there is not even a window fetch to land back
 * in (measured: 9.97–14.66 → the full 1.74–25.25 on one shift-click).
 *
 * This is WP-1015's rule for the 3D camera one panel over — `react` rebuilds
 * the scene, so **the view must be handed back on every draw** — and it is read
 * from `_fullLayout` immediately before the react for that rule's reason too: a
 * drag, a double-click and the modebar all move it, so a copy kept here would
 * be a second answer.
 *
 * `autorange === false` was read as "the user has said" until WP-1212, and that
 * is where the rule leaked: plotly sets the flag on a zoom or a pan and nowhere
 * else, so on a plot nobody had zoomed there was nothing to keep and every
 * redraw re-fitted the axes. It now means "explicit", full stop — `pinPatch`
 * below makes every axis explicit after each paint, and `movedAxes` is what
 * answers the other half. `live` is the caller's: a y axis is only the same
 * axis while it is still drawing the same thing, and a √ or log scaling
 * re-means `yaxis` while another residual re-means `yaxis2` (Σχ² runs to
 * hundreds of thousands where Δ/σ runs to ±5).
 */
export interface Ranges {
  xaxis?: [number, number];
  yaxis?: [number, number];
  yaxis2?: [number, number];
}

/**
 * The range an axis is **drawing** with, which is not always `ax.range`.
 *
 * A browser finding, and the one that decides whether pinning is safe at all
 * (WP-1212). On the first plot of a fresh div — the raw pattern view, which is
 * the state a project is in before any fit — `_fullLayout.xaxis.range` was
 * still plotly's empty-axis default `[-1, 6]` with `autorange: true` while the
 * axis was drawing 0-60°: the tick labels, `_length`/`_offset` and `p2d` all
 * agreed on −3.07-63.56 and only `range` did not. Plotly keeps the resolved
 * pair in `ax._rl`, which is what its pixel map is built from, so `_rl` is the
 * honest read and `range` is the one that can be stale. The two are the same
 * number whenever `range` is fresh, log axes included (both are in log units).
 *
 * Reading any of this back off `_fullLayout` is WP-1044's rule, and WP-1015's
 * before it; this only names which field inside it answers the question.
 */
export function drawnRange(ax: any): [number, number] | null {
  for (const pair of [ax?._rl, ax?.range]) {
    if (!Array.isArray(pair) || pair.length !== 2) continue;
    const out: [number, number] = [Number(pair[0]), Number(pair[1])];
    if (out.every(Number.isFinite)) return out;
  }
  return null;
}

export function heldRanges(full: any, live: { yaxis: boolean; yaxis2: boolean }): Ranges {
  const out: Ranges = {};
  const keep = (key: keyof Ranges, ok: boolean) => {
    const ax = full?.[key];
    if (!ok || ax?.autorange !== false) return;
    const pair = drawnRange(ax);
    if (pair) out[key] = pair;
  };
  keep("xaxis", true);
  keep("yaxis", live.yaxis);
  keep("yaxis2", live.yaxis2);
  return out;
}

/** A `range` key, or nothing at all — an absent one is what leaves plotly
 *  autoranging, and `range: null` would not (it is a value like any other). */
export function span(range?: [number, number]): { range?: [number, number] } {
  return range ? { range } : {};
}

/**
 * The axes this panel pins, and why the other two are not among them.
 *
 * `yaxis3` is the reflection tick band and `yaxis4` the candidate overlay:
 * each is declared with a range of its own (`TICK_BAND`, `CANDIDATE_AXIS`) and
 * neither ever autoranges, so pinning them would be a claim about an axis
 * nobody can move.
 */
export const PINNED_AXES = ["xaxis", "yaxis", "yaxis2"] as const;

/** One flag per pinnable axis — used for "a person moved this one by hand". */
export type AxisFlags = Record<(typeof PINNED_AXES)[number], boolean>;

export function noAxes(): AxisFlags {
  return { xaxis: false, yaxis: false, yaxis2: false };
}

/**
 * The relayout patch that turns every autoranging axis into an explicit one.
 *
 * **`autorange === false` is the whole repair, and a redraw cannot reach it.**
 * `heldRanges` above keeps an axis only once plotly has set that flag, which it
 * does on a zoom or a pan and nowhere else — so on a plot the user has not
 * zoomed, every axis stays autoranging and *everything* moves it. Measured on
 * the NAC example (WP-1212): a hover over the peaks table costs no `react` at
 * all and still moves `yaxis` by 1.03 % of its span, because `drawRing`'s
 * `restyle` puts a `marker.size: 16` ring on the axis and scatter autorange
 * pads by marker size. The same hover on a *zoomed* plot moves nothing, which
 * is why the WP-1044 repair read as complete.
 *
 * So the axes are made explicit as soon as they have a range worth keeping:
 * after every paint, whatever plotly autoranged is written back as a `range`,
 * and from then on a `react` or a `restyle` has nothing left to re-derive.
 * The values are plotly's own — this reads the range it computed rather than
 * computing one, because reproducing autorange padding (marker sizes, error
 * bars, log ticks, the tick band's domain) is a second answer to a question
 * plotly has already answered correctly.
 *
 * Returns `{}` when there is nothing to pin, which is the common case: on the
 * second and later paints of a payload every axis is already explicit.
 *
 * `skip` names the axes the caller is **not** drawing anything on, and it is a
 * guard rather than a repair — said plainly, because the review that asked for
 * it described a defect that does not reproduce. Chrome drops an unused axis
 * from `_fullLayout` altogether: hide the difference curve and `yaxis2` is
 * *absent*, so there is nothing to pin, and letting a run land while it is
 * hidden leaves it absent and brings it back at the residual's own range
 * (measured: −81.76-61.68 → absent → −81.76-61.68). What made it look like a
 * defect is the jsdom stub, which synthesises every axis unconditionally. The
 * guard stays because "pin what plotly fitted" should not depend on plotly
 * choosing to drop what it could not fit, and an empty axis left autoranging is
 * the honest state — there is nothing on it for a redraw to move.
 */
export function pinPatch(full: any, skip: readonly string[] = []):
    Record<string, [number, number]> {
  const patch: Record<string, [number, number]> = {};
  for (const key of PINNED_AXES) {
    const ax = full?.[key];
    if (!ax?.autorange || skip.includes(key)) continue;
    // `drawnRange`, never `ax.range`: on the first plot of a fresh div the two
    // disagree, and pinning `range` there froze plotly's empty-axis default
    // over a pattern spanning 0-60°. That is what made the raw view blank; the
    // fitted view escaped it only because the run that followed re-fitted the
    // axes anyway (measured both ways).
    const pair = drawnRange(ax);
    if (pair) patch[`${key}.range`] = pair;
  }
  return patch;
}

/**
 * Which axes a `plotly_relayout` event says a person moved by hand.
 *
 * Once every axis carries an explicit range, `autorange === false` no longer
 * answers "has the user said?" — it is true of every axis on every plot, and
 * the two questions that used to share that flag come apart. This is the other
 * one, and plotly reports it per gesture: a drag emits `<axis>.range[0]` and
 * `[1]`, while a double-click (`doubleClick: "autosize"`) emits
 * `<axis>.autorange`, which hands *every* axis back and is therefore a reset
 * rather than a move.
 *
 * A patch this panel writes itself is not a gesture and must not arrive here;
 * the caller gates on that rather than on the key spelling, because
 * `relayout({"xaxis.range": pair})` and a drag differ only in `[0]`/`[1]` and
 * that is far too fine a thing to rest a rule on.
 */
export function movedAxes(ev: Record<string, any> | null | undefined):
    { moved: (typeof PINNED_AXES)[number][]; reset: boolean } {
  const moved: (typeof PINNED_AXES)[number][] = [];
  let reset = false;
  for (const key of PINNED_AXES) {
    if (ev?.[`${key}.autorange`]) reset = true;
    else if (typeof ev?.[`${key}.range[0]`] === "number") moved.push(key);
  }
  return { moved, reset };
}

/**
 * The ranges to hand back when a paint is allowed to re-fit the axes.
 *
 * Two paints are: the first of a new payload (a run, a checkout — the numbers
 * are different ones and a range from the old set would clip them) and the one
 * after a double-click. Everything else — a hover, a tab change, an exclusion,
 * a peak edit, a theme change — hands back all of them, which is the rule this
 * whole module exists for.
 *
 * What survives a re-fit is what the *person* set: a zoom is not thrown away by
 * a run finishing, which is WP-1044's rule and the reason this is a filter and
 * not an empty object.
 */
/**
 * A knob that re-means an axis un-says whatever was said about it.
 *
 * `userSet` remembers that a person dragged an axis, and it has to be forgotten
 * when that axis stops drawing the same thing: a range dragged on Δ/σ is not a
 * range on Σχ², which runs to hundreds of thousands, and it would otherwise
 * survive into the next re-fit as though it had been chosen there.
 * `heldRanges`' `live` gate hides this *within* a paint — an axis that changed
 * meaning is not handed back — and does nothing across the payload change that
 * licenses a re-fit, which is where the stale flag would be read.
 *
 * The same argument as `live`, one step later: that one decides what this paint
 * hands back, this one decides what the *next* re-fit is allowed to keep.
 */
export function forget(user: AxisFlags, live: { yaxis: boolean; yaxis2: boolean }): AxisFlags {
  return {
    xaxis: user.xaxis,
    yaxis: user.yaxis && live.yaxis,
    yaxis2: user.yaxis2 && live.yaxis2,
  };
}

export function userRanges(ranges: Ranges, user: AxisFlags): Ranges {
  const out: Ranges = {};
  for (const key of PINNED_AXES) if (user[key] && ranges[key]) out[key] = ranges[key];
  return out;
}

/** A drawn interval as an ordered pair, or null if it is a point. */
export function normalizeRegion(pair: [number, number]): [number, number] | null {
  const [a, b] = pair;
  if (!Number.isFinite(a) || !Number.isFinite(b) || a === b) return null;
  return a < b ? [a, b] : [b, a];
}

/**
 * The region list with `add` folded in: sorted, and with overlaps merged.
 *
 * Merging is a **presentation** decision that provably changes nothing about
 * what is fitted — `PatternData.in_range_mask` removes the union of the
 * regions, so two overlapping entries and their merged one mask exactly the
 * same channels (asserted that way in `plot.test.ts`, over a grid, rather than
 * by re-deriving the union). What it buys is a chip list a user can read: three
 * drags over one peak are one exclusion, not three.
 *
 * Touching intervals merge too, because the mask is inclusive at both ends.
 */
export function mergeRegions(regions: readonly [number, number][],
                             add?: [number, number] | null): [number, number][] {
  const all = [...regions, ...(add ? [add] : [])]
    .map((r) => normalizeRegion(r as [number, number]))
    .filter((r): r is [number, number] => r !== null)
    .sort((p, q) => p[0] - q[0]);
  const out: [number, number][] = [];
  for (const [a, b] of all) {
    const last = out[out.length - 1];
    if (last && a <= last[1]) last[1] = Math.max(last[1], b);
    else out.push([a, b]);
  }
  return out;
}

/** Is 2θ inside any region?  The client's copy of the server's mask test, and
 *  the only thing `plot.test.ts` compares a merge against. */
export function masked(regions: readonly [number, number][], twoTheta: number): boolean {
  return regions.some(([a, b]) => twoTheta >= a && twoTheta <= b);
}

/** One decimal place more than the data resolves — a region is a protocol
 *  statement, so its chip shows what would be sent, not a rounded story. */
export function formatRegion([a, b]: [number, number]): string {
  return `${a.toFixed(3)}–${b.toFixed(3)}°`;
}

/**
 * The reflection ticks get an axis of their own, in the gap between the plots.
 *
 * They used to ride on the residual axis at `y = −0.5 − row·0.9`, which made
 * their visibility a property of **which residual is selected**: under Δ/σ they
 * sat near the middle, and under cumulative χ² — whose values run to hundreds of
 * thousands (measured on the NAC fit: y2 spanned −59 253 to 658 029) — they were
 * pinned at the floor as an invisible line. A tick is a statement about the
 * *model*, so it cannot be drawn in a coordinate system owned by the residual.
 *
 * The gap `[0.22, 0.28]` between the two subplots was already free (`yaxis`
 * starts at 0.28), so this needed no room made for it. The range is fixed in
 * rows, one per phase, and `fixedrange` keeps a stray drag from zooming a band
 * whose vertical coordinate means nothing.
 */
export const TICK_BAND: [number, number] = [0.225, 0.275];

export function tickBand(nPhases: number): { axis: any; rows: number[] } | null {
  if (nPhases <= 0) return null;
  const rows: number[] = [];
  for (let i = 0; i < nPhases; i++) rows.push(-(i + 0.5));
  return {
    axis: {
      domain: TICK_BAND,
      anchor: "x",
      range: [-nPhases, 0],
      fixedrange: true,
      showticklabels: false,
      showgrid: false,
      zeroline: false,
      showline: false,
    },
    rows,
  };
}

/**
 * An indexing candidate's predicted lines, as the plot needs them (WP-1211).
 *
 * `label` is built here rather than served: the panel already renders the cell,
 * and a server that formatted one would be a second opinion about how a cell
 * reads. `n_total` is the half of the server's cap that keeps it honest — over
 * `MAX_CANDIDATE_TICKS` the answer is thinned by rank in 2θ, so
 * `two_theta.length < n_total` means a sample was drawn and not a set.
 *
 * It is *not* a `CurveToggle`, and that is a decision rather than an omission:
 * a toggle would be a second control for a thing whose control is already the
 * candidate row, and pressing it would leave a row looking selected with
 * nothing on the plot. What the toggle row would have said, the status line
 * under the plot says instead.
 */
export interface CandidateOverlay {
  label: string;
  two_theta: number[];
  n_total: number;
  /** the reflection each drawn line is, parallel to `two_theta` (WP-1213) —
   *  served since WP-1211 and drawn nowhere until the readout strip */
  hkl?: number[][];
  /** which emission line each drawn position belongs to, as an index into the
   *  source's own list: a Kα2 line sits at a different 2θ for the same hkl */
  line?: number[];
}

/**
 * Full-height lines through the data, as one null-separated trace.
 *
 * One trace and not N: the peak layer's `joinCurves` established the idiom here
 * (sixty windows as sixty traces is a legend, not a layer), and at this WP's cap
 * the alternative is two thousand of them. Shapes were the other candidate and
 * are worse for the same reason plus one: a `xref: "x"` shape takes part in the
 * autorange (WP-1033), and two thousand SVG paths are re-laid-out on every
 * zoom.
 */
export function candidateLines(twoTheta: readonly number[]): {
  x: (number | null)[]; y: (number | null)[];
} {
  const x: (number | null)[] = [];
  const y: (number | null)[] = [];
  for (const t of twoTheta) {
    x.push(t, t, null);
    y.push(0, 1, null);
  }
  return { x, y };
}

/**
 * The axis those lines are drawn against: the data panel's, pinned to [0, 1].
 *
 * An **overlaying** axis, which is what makes "full height" mean the height of
 * the plot rather than the height of the data — it takes `yaxis`'s domain and
 * keeps its own range, so the lines span the upper subplot whatever the
 * intensity scale is doing and whatever the user has zoomed the y axis to.
 * That is also why they are not on `y3`, the tick band: a tick belongs to a
 * fitted model and sits in its own strip, while these are a hypothesis laid
 * *over* the data to be compared with it.
 *
 * `fixedrange` because a vertical coordinate that means nothing must not be
 * zoomable — `tickBand`'s reasoning, one axis over. The x axis is shared, and
 * the lines cannot widen it: the server clips them to the measured range.
 */
export const CANDIDATE_AXIS = {
  overlaying: "y",
  anchor: "x",
  range: [0, 1],
  fixedrange: true,
  showticklabels: false,
  showgrid: false,
  zeroline: false,
  showline: false,
};

/** A curve the plot can be asked to stop drawing. */
export interface CurveToggle {
  id: string;
  label: string;
  title: string;
  /** Why this curve is not on screen whatever the toggle says (WP-1210) — the
   *  peak layer away from the Peaks tab. A curve that *could* be drawn leaves
   *  this undefined; one that carries it is listed and disabled, because the
   *  honest answer to "where did my markers go" is a sentence, not a gap. */
  absent?: string;
}

/**
 * The picked-peak layer, as the toggle row needs to know it (WP-1210).
 *
 * It is not part of the window payload — a peak list belongs to the project and
 * outlives every fit — so it arrives beside one rather than inside it.
 */
export interface PeakLayer {
  /** picked lines in the list */
  n: number;
  /** fitted group curves riding with them */
  groups: number;
  /** the Peaks tab is up, which is the only tab the layer is drawn on */
  active: boolean;
}

/**
 * Which curves this window actually has, in drawing order (WP-1032).
 *
 * A *drawing* choice, so nothing here is persisted — WP-1015's rule one panel
 * over: storing one would make a picture the project's opinion. The list is
 * derived from the payload rather than fixed, because "background" is a curve
 * only when the model has one and a phase row exists only per phase.
 *
 * The reported item was "make it possible to toggle the background on", and the
 * measurement says which repair that is: the background trace is drawn
 * *unconditionally* whenever `y_background` is non-empty, so nothing was
 * missing — what was missing is the control to turn a forced curve **off**.
 */
export function curveToggles(w: Window & { raw?: boolean; ticks?: Record<string, unknown> },
                             residualLabel = "Δ",
                             layer?: PeakLayer | null): CurveToggle[] {
  const out: CurveToggle[] = [
    { id: "obs", label: "obs", title: "the measured points" },
  ];
  if (w.excluded?.two_theta?.length) {
    // a *curve* toggle for the excluded points, not for the shading: hiding
    // them is a drawing choice, while the region itself is protocol and is
    // switched off only by removing it (WP-1033)
    out.push({ id: "masked", label: "masked",
      title: "the measured points outside the fit range or inside an excluded "
        + "region — drawn recessively, and in no residual" });
  }
  if (!w.raw) {
    out.push({ id: "calc", label: "calc", title: "the model" });
    if (w.y_background?.length) {
      out.push({ id: "bkg", label: "bkg", title: "the background, drawn additively — "
        + "it is held or co-refined, never subtracted from the data" });
    }
    out.push({ id: "diff", label: residualLabel,
      title: "the residual in the lower panel" });
    for (const phase of Object.keys(w.ticks ?? {})) {
      out.push({ id: `ticks:${phase}`, label: phase,
        title: `reflection positions for ${phase} — every emission line, `
          + "so a Kα2 tick is a tick and not an impurity" });
    }
  }
  // Last, because the layer draws over everything else — and outside the
  // `raw` branch, since a peak list is what a project has *before* a fit.
  if (layer?.n) {
    const absent = layer.active
      ? undefined
      : "drawn on the Peaks tab, where a marker can be moved, excluded or "
        + "removed — a click on this plot means something else here";
    out.push({ id: "peaks", label: "peaks", absent,
      title: "the picked lines, at the measured intensity under each position — "
        + "hollow where the line is not used" });
    if (layer.groups) {
      out.push({ id: "peakfit", label: "peak fit", absent,
        title: "the profile fitted to each group of picked lines, dashed — it is "
          + "what the positions were measured from, not the refined model" });
    }
  }
  return out;
}

/**
 * "Data only": every curve hidden but the measured points (WP-1210).
 *
 * Over *every* id **the payload offers when it is pressed**, absent ones
 * included — so a layer that is listed but undrawable (the peak layer away from
 * its tab) is hidden too, and switching to that tab does not undo the button.
 *
 * What it deliberately does not cover, because `hidden` is an exception list
 * and this returns a value rather than arming a mode: a curve that comes into
 * *existence* later is not in the list and therefore draws. Press this with
 * hand-placed peaks and no fitted groups, then refit, and the dashed peak-fit
 * curve appears on a cleared plot. Fixing it means an armed mode that keeps
 * re-hiding, which then has to decide what a manual toggle underneath it means
 * — a bigger design than this button (WP-1210's log; found in review, not use).
 */
export function dataOnlyHidden(toggles: readonly CurveToggle[]): string[] {
  return toggles.filter((curve) => curve.id !== "obs").map((curve) => curve.id);
}

/** Is the plot showing the data and nothing else?  The button's own state. */
export function isDataOnly(toggles: readonly CurveToggle[],
                           hidden: readonly string[]): boolean {
  return toggles.length > 1
    && shows(hidden, "obs")
    && dataOnlyHidden(toggles).every((id) => hidden.includes(id));
}

/** Is `id` drawn?  Hidden is the exception list, so a new curve arrives shown. */
export function shows(hidden: readonly string[], id: string): boolean {
  return !hidden.includes(id);
}

/** Toggle one id in an exception list, returning a new one. */
export function toggleCurve(hidden: readonly string[], id: string): string[] {
  return hidden.includes(id) ? hidden.filter((h) => h !== id) : [...hidden, id];
}

export interface Residual {
  values: number[];
  /** the y2 axis title — it names what is plotted, never what was hoped for */
  title: string;
  label: string;
  /** cumulative χ² only rises, so a zero line through it says nothing */
  zeroline: boolean;
}

export const RESIDUAL_KINDS: { id: ResidualKind; label: string; title: string }[] = [
  { id: "weighted", label: "Δ/σ", title: "the weighted residual the fit actually minimises" },
  { id: "delta", label: "Δ", title: "observed − calculated, in counts" },
  { id: "cumulative", label: "Σχ²", title: "χ² accumulated across the window — a flat "
    + "stretch contributed nothing, a step is where the misfit is" },
];

export const SCALES: { id: Scale; label: string; title: string }[] = [
  { id: "linear", label: "lin", title: "intensity as measured" },
  { id: "sqrt", label: "√", title: "square root — the weak peaks a strong one hides, "
    + "with the axis still labelled in intensity" },
  { id: "log", label: "log", title: "logarithmic; non-positive points are not drawable "
    + "and are dropped" },
];

/**
 * The chosen residual, and an axis title that says which σ it is over.
 *
 * `delta` is *always* Δ/σ: the fit always weighted by something, so there is
 * always a weighted residual to draw (WP-1029 (s)). `weighted` does not say
 * whether σ exists — it says whether σ was **measured**, i.e. whether the file
 * brought an esd column or the server fell back to Poisson √max(y,1). That
 * changes only the axis title, never which curve is plotted.
 *
 * This used to switch the *curve*, dropping to raw Δ when `weighted` was false.
 * It never fired: the server derived the flag from the result rather than from
 * the data reference, so it was pinned true and a Poisson fit was labelled
 * `(obs−calc)/σ` as if its σ had been measured.
 */
export function residual(kind: ResidualKind, w: Window): Residual {
  const measured = w.weighted !== false;
  if (kind === "cumulative") {
    return {
      values: w.cumulative_chi2 ?? [],
      title: "Σχ²",
      label: "Σχ²",
      zeroline: false,
    };
  }
  if (kind === "weighted") {
    return {
      values: w.delta ?? [],
      // an assumed σ is still a σ, but the axis has to admit which one it is
      title: measured ? "(obs−calc)/σ" : "(obs−calc)/σ (Poisson σ)",
      label: "Δ/σ",
      zeroline: true,
    };
  }
  return {
    values: w.delta_raw ?? w.delta ?? [],
    title: "obs−calc",
    label: "Δ",
    zeroline: true,
  };
}

/** √ is applied to the *data*, because plotly has no such axis type. */
export function scaleValues(scale: Scale, values: number[] | undefined): number[] | undefined {
  if (!values || scale !== "sqrt") return values;
  // negatives happen — a background-subtracted point, a noisy low-count channel
  // — and √(negative) is NaN, which loses the trace rather than the point
  return values.map((v) => (v > 0 ? Math.sqrt(v) : 0));
}

/**
 * Ticks that read in **intensity** even when the data has been square-rooted.
 *
 * Without this the axis would be labelled in √counts, which is a unit nobody
 * measures in and which makes the scaling look like a different dataset rather
 * than a different view of one. `null` means "let plotly decide", which is the
 * right answer for linear and log.
 */
export function sqrtTicks(hi: number, n = 6): { tickvals: number[]; ticktext: string[] } | null {
  if (!Number.isFinite(hi) || hi <= 0) return null;
  const vals: number[] = [];
  for (let i = 0; i <= n; i++) {
    const y = (hi * i) / n;
    vals.push(y);
  }
  return {
    tickvals: vals.map((y) => Math.sqrt(y)),
    ticktext: vals.map((y) => (y >= 1000 ? y.toPrecision(3) : String(Number(y.toPrecision(3))))),
  };
}

// ----------------------------------------------------------------------
// the readout strip (WP-1213)
// ----------------------------------------------------------------------
/**
 * The index of the value nearest `x` in an ascending array — binary search.
 *
 * The plot's one nearest-channel question, asked by the readout and by the peak
 * layer's marker heights. `-1` when there is nothing to look in.
 */
export function nearestIndex(xs: readonly number[], x: number): number {
  if (!xs.length) return -1;
  let lo = 0;
  let hi = xs.length - 1;
  while (hi - lo > 1) {
    const mid = (lo + hi) >> 1;
    if (xs[mid] < x) lo = mid;
    else hi = mid;
  }
  return Math.abs(xs[lo] - x) <= Math.abs(xs[hi] - x) ? lo : hi;
}

/** Which plot ink a readout row is about, so the strip can say it in the mark's
 *  own colour as well as by name. `curveColors`' keys, and no others. */
export type ReadoutInk = "obs" | "calc" | "bkg" | "diff" | "peak" | "peakfit"
  | "candidate";

/** One labelled field of the strip. `value` is already formatted: the strip
 *  prints it and decides nothing. */
export interface ReadoutRow {
  /** stable across hovers, so the strip's slots keep their order */
  id: string;
  label: string;
  value: string;
  ink?: ReadoutInk;
}

export interface Readout {
  /** the drawn channel under the pointer, at four places with its degree sign */
  position: string;
  /** `d = λ/(2 sin θ)` there, empty where the source's λ is not in hand */
  d: string;
  rows: ReadoutRow[];
}

export interface ReadoutInputs {
  /** which residual the lower panel is drawing — the strip names the one on
   *  screen, never all three */
  kind: ResidualKind;
  /** the source's emission lines, primary first: `d` is the primary's, and a
   *  candidate line names its own */
  wavelengths?: readonly number[] | null;
  /** the picked lines, and whether their layer is on the plot at all — it is
   *  drawn only on the Peaks tab (WP-1210), so elsewhere there is no row */
  peaks?: readonly PeakRow[] | null;
  peaksActive?: boolean;
  /** how near a picked line has to be to be the one under the pointer, in ° 2θ:
   *  the caller's, because the pixel↔2θ map is the caller's — the same
   *  `grabToleranceDeg` radius the pointer verbs aim with */
  peakTolerance?: number;
  /** the fitted group profiles, so the dashed curve can say what it is worth */
  groups?: readonly GroupCurve[] | null;
  /** the candidate overlay on screen, if any, and the same question for it */
  candidate?: CandidateOverlay | null;
  candidateTolerance?: number;
  /** the curves switched off (`curveToggles`' ids): the strip names what is
   *  **drawn**, so `data only` empties it down to the points — the same
   *  exception list, read the same way */
  hidden?: readonly string[];
}

/** What a field with nothing in it prints — one spelling, so an empty strip
 *  and an empty field are the same mark. */
const EMPTY = "—";

/**
 * `+0.0035°` / `-0.0035°` — an offset, signed and always signed.
 *
 * An ASCII minus, deliberately: the strip prints `formatValue`'s numbers beside
 * these, and those come out of `toPrecision`, so a typographic `−` here put two
 * spellings of minus in one row (seen in Chrome). The rule the app already
 * follows unwritten is that **prose takes `−` and numbers take `-`** — the
 * residual's axis title is `obs−calc` and its values are not. `formatHkl` is
 * the exception that proves it: an index is a label standing in for an overbar,
 * not a measurement.
 */
function offset(delta: number): string {
  return `${delta < 0 ? "-" : "+"}${Math.abs(delta).toFixed(4)}°`;
}

/**
 * Everything the plot knows at one 2θ, as the strip under it prints it.
 *
 * **Why a strip and not a hover box** (the report: "the tooltip frequently
 * covers a large part of the data"): plotly offers no positioning for the
 * unified box beyond `hoverlabel.align`, so "put it somewhere else" is not a
 * setting — the box has to go, and what replaces it is a row of the plot's own
 * controls. That also settles something the box could not do: under
 * `hovermode: "x unified"` plotly snaps *every* trace to its nearest point in
 * x, so the candidate overlay would have put a row in the box at every pointer
 * position, which is why WP-1211 gave it `hoverinfo: "skip"` and left its
 * served `hkl` undrawn. Here it is one more row.
 *
 * Pure, and every value is formatted here rather than in the component, because
 * what makes a readout right is that it reads as the table beside it reads:
 * `formatPosition`/`formatIntensity` are `lib/peaks.ts`' (WP-1209), and the
 * intensities are `formatValue`'s six significant figures — which is what the
 * deleted `hovertemplate`s printed, `%{customdata:.6g}` over the **unscaled**
 * value, so a √ view still reads in intensity.
 *
 * A row a payload cannot fill is **absent, not empty**: there is a row per
 * curve that is *drawn*, which makes the strip's shape a property of the
 * payload, the tab and the curve toggles — never of where the pointer happens
 * to be. Everything that varies with the pointer keeps its slot and empties it
 * instead: the three "nearest something" rows, and `x === null` for the pointer
 * being off the plot altogether, which is most of the time. A strip that grew a
 * field on hover would resize the canvas above it once per entry, and that is
 * the jitter WP-1212 spent itself removing, arriving through the repair for it.
 *
 * The one place this reads two arms is the **masked** channels: they are in no
 * result, so they arrive beside it (WP-1033), and a pointer inside an excluded
 * region is over one of them. The nearest channel is therefore taken over both
 * arms, and a masked one has no model to quote — which is also how the strip
 * says where the pointer is, without a field that changes width to say it.
 */
export function readout(
  w: (Window & { raw?: boolean; ticks?: Record<string, number[]> }) | null,
  x: number | null,
  inputs: ReadoutInputs,
): Readout | null {
  if (!w) return null;
  const hidden = inputs.hidden ?? [];
  const fitted = w.two_theta ?? [];
  // The masked channels are a *separate arm* (WP-1033: they are in no result,
  // so the server sends them beside it), and they are measured points like any
  // other — a pointer inside an excluded region is over one of them. Without
  // this the readout snapped to the nearest surviving channel and printed its
  // numbers under a pointer that could be a whole region away.
  const maskedOn = shows(hidden, "masked");
  const excluded = maskedOn ? w.excluded?.two_theta ?? [] : [];
  if (!fitted.length && !excluded.length) return null;
  // `null` is the pointer being off the plot, which is most of the time: the
  // strip keeps its fields and empties them, because a strip that grew fields
  // on hover would resize the canvas above it once per entry (WP-1032 measured
  // a resize at ~111 ms; WP-1212 spent itself on smaller movements than that).
  const live = x != null && Number.isFinite(x);
  const kf = live ? nearestIndex(fitted, x!) : -1;
  const kx = live ? nearestIndex(excluded, x!) : -1;
  const masked = kf < 0
    || (kx >= 0 && Math.abs(excluded[kx] - x!) < Math.abs(fitted[kf] - x!));
  const k = masked ? kx : kf;
  const at = k < 0 ? null : (masked ? excluded[k] : fitted[k]);
  const lam = inputs.wavelengths?.[0];
  const rows: ReadoutRow[] = [];
  const value = (v: number | undefined | null) =>
    at == null || v == null || !Number.isFinite(v) ? EMPTY : formatValue(v, null);
  // a masked channel is in no result, so there is no model at it to quote —
  // which is also how the strip says the pointer is inside a region
  const fit = (v: number | undefined | null) => (masked ? EMPTY : value(v));

  if (shows(hidden, "obs")) {
    rows.push({ id: "obs", label: "obs", ink: "obs",
      value: masked ? value(w.excluded?.y_obs?.[k]) : value(w.y_obs?.[k]) });
  }
  if (!w.raw) {
    if (shows(hidden, "calc")) {
      rows.push({ id: "calc", label: "calc", value: fit(w.y_calc?.[k]), ink: "calc" });
    }
    if (w.y_background?.length && shows(hidden, "bkg")) {
      rows.push({ id: "bkg", label: "bkg", value: fit(w.y_background[k]), ink: "bkg" });
    }
    if (shows(hidden, "diff")) {
      const res = residual(inputs.kind, w);
      rows.push({ id: "diff", label: res.label, value: fit(res.values[k]), ink: "diff" });
    }
  }

  // the fitted group profile, named because a reader had no other way to tell
  // the dashed curve from the model (WP-1210's own repair, carried here)
  if (inputs.peaksActive && inputs.groups?.length && shows(hidden, "peakfit")) {
    const group = at == null ? undefined : inputs.groups.find(
      (g) => g.two_theta.length && g.two_theta[0] <= at
        && g.two_theta[g.two_theta.length - 1] >= at);
    const j = group ? nearestIndex(group.two_theta, at!) : -1;
    rows.push({ id: "peakfit", label: "peak fit", ink: "peakfit",
      value: group && j >= 0 ? formatValue(group.y_fit[j], null) : EMPTY });
    if (w.raw) {
      // on the raw view the lower subplot is the groups' own residual, and it
      // is a drawn curve like any other
      rows.push({ id: "peakdelta", label: "(y−fit)/σ", ink: "peakfit",
        value: group && j >= 0 ? formatValue(group.delta[j], null) : EMPTY });
    }
  }

  // the nearest tick per phase, as an offset: the position is this readout's
  // own 2θ plus it, and an offset is the number that says "there is a
  // reflection right here" without arithmetic
  for (const [phase, ticks] of Object.entries(w.ticks ?? {})) {
    if (!shows(hidden, `ticks:${phase}`)) continue;
    const j = at == null ? -1 : nearestIndex(ticks, at);
    rows.push({ id: `ticks:${phase}`, label: phase,
      value: j < 0 ? EMPTY : offset(ticks[j] - at!) });
  }

  // the picked line under the pointer, printed as the panel's table prints it
  if (inputs.peaksActive && inputs.peaks?.length && shows(hidden, "peaks")) {
    const hit = at == null ? null
      : nearestPeak(inputs.peaks, at, inputs.peakTolerance ?? Infinity);
    const row = hit === null ? null : inputs.peaks.find((p) => p.index === hit);
    const pos = row ? formatPosition(row.two_theta, row.two_theta_esd) : null;
    rows.push({ id: "peaks", label: "peak", ink: "peak",
      value: row && pos
        ? `#${row.index} ${pos.value}${pos.esd}° · I ${
            formatIntensity(row.intensity, intensityScale(inputs.peaks), row.flags)}`
        : EMPTY });
  }

  // …and the candidate's, which is the hkl WP-1211 serves and does not draw.
  // No ordinal and no count: past `MAX_CANDIDATE_TICKS` the drawn set is a
  // sample thinned by rank, so "the 743rd line" would be a statement about the
  // sample. The status line under the plot is where the count is honest. No
  // `hidden` gate either: the overlay has no curve toggle, because its control
  // is the candidate row (WP-1211).
  const lines = inputs.candidate?.two_theta ?? [];
  if (lines.length) {
    const j = at == null ? -1 : nearestIndex(lines, at);
    const near = j >= 0
      && Math.abs(lines[j] - at!) <= (inputs.candidateTolerance ?? Infinity);
    const hkl = inputs.candidate?.hkl?.[j];
    const li = inputs.candidate?.line?.[j];
    const lineLam = li == null ? undefined : inputs.wavelengths?.[li];
    rows.push({ id: "candidate", label: "candidate", ink: "candidate",
      value: near && hkl
        ? [formatHkl(hkl), lineLam == null ? null : `λ ${lineLam.toFixed(4)} Å`]
            .filter(Boolean).join(" · ")
        : EMPTY });
  }

  const theta = at == null ? 0 : Math.sin((at * Math.PI) / 360);
  return {
    position: at == null ? EMPTY : `${at.toFixed(4)}°`,
    d: at != null && lam && theta > 0 ? `${(lam / (2 * theta)).toFixed(4)} Å` : EMPTY,
    rows,
  };
}

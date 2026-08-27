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
 * `autorange === false` is exactly "the user has said": plotly sets it on a zoom
 * or pan drag and puts it back on a double-click, which is what keeps
 * reset-to-all reachable. `live` is the caller's half of the question — a y axis
 * is only the same axis while it is still drawing the same thing, and a √ or log
 * scaling re-means `yaxis` while another residual re-means `yaxis2` (Σχ² runs to
 * hundreds of thousands where Δ/σ runs to ±5).
 */
export interface Ranges {
  xaxis?: [number, number];
  yaxis?: [number, number];
  yaxis2?: [number, number];
}

export function heldRanges(full: any, live: { yaxis: boolean; yaxis2: boolean }): Ranges {
  const out: Ranges = {};
  const keep = (key: keyof Ranges, ok: boolean) => {
    const ax = full?.[key];
    if (!ok || ax?.autorange !== false || !Array.isArray(ax.range)) return;
    const pair: [number, number] = [Number(ax.range[0]), Number(ax.range[1])];
    if (pair.every(Number.isFinite)) out[key] = pair;
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

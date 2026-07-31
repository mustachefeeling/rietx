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

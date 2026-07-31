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
 * The chosen residual, or the nearest thing the payload can support.
 *
 * A window from a project with no esd column carries `weighted: false`, and its
 * `delta` is already the unweighted difference — so asking for Δ/σ there gets Δ
 * with an axis that *says* Δ. The old plot labelled that axis `(obs−calc)/σ`
 * unconditionally, which was a lie on exactly those projects.
 */
export function residual(kind: ResidualKind, w: Window): Residual {
  const weighted = w.weighted !== false;
  if (kind === "cumulative") {
    return {
      values: w.cumulative_chi2 ?? [],
      title: "Σχ²",
      label: "Σχ²",
      zeroline: false,
    };
  }
  if (kind === "weighted" && weighted) {
    return { values: w.delta ?? [], title: "(obs−calc)/σ", label: "Δ/σ", zeroline: true };
  }
  // raw Δ — either because it was asked for, or because there is no σ to divide by
  return {
    values: w.delta_raw ?? w.delta ?? [],
    title: weighted ? "obs−calc" : "obs−calc (no σ)",
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

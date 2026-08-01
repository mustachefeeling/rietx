/**
 * Peak-picker and candidate-table logic, as pure functions (WP-1027).
 *
 * The rules that must not be re-decided in a component live here, and two of
 * them are the server's: which flags make a peak unusable comes from the
 * `unusable_flags` arm of `/api/peaks`, and which caveats *refute* a candidate
 * comes from the `refuting_caveats` arm of `/api/index/result` — both quoted
 * from package constants, so the colouring cannot drift when a vocabulary
 * grows (the `held_because` rule, applied to chips).
 */

export interface PeakRow {
  index: number;
  two_theta: number;
  two_theta_esd: number;
  d: number;
  intensity: number;
  fwhm: number;
  group: number;
  n_in_group: number;
  chi2_red: number;
  flags: string[];
  origin: "fitted" | "manual" | "edited";
  usable: boolean;
}

export interface GroupCurve {
  group: number;
  two_theta: number[];
  y_fit: number[];
  y_env: number[];
  delta: number[];
  chi2_red: number;
  n_components: number;
}

export interface PeaksPayload {
  peaks: PeakRow[] | null;
  pattern: { two_theta: number[]; y_obs: number[]; n_total: number };
  groups?: GroupCurve[];
  diagnostics?: Array<{ level: string; code: string; message: string }>;
  flag_vocabulary: string[];
  unusable_flags: string[];
  n_total?: number;
  n_usable?: number;
  source?: "fitted" | "positions";
  wavelength?: number;
  api_call?: string;
}

/** A flag chip's tone: the unusable set reads as "this line is out". */
export function flagTone(flag: string, unusable: readonly string[]): "out" | "note" {
  return unusable.includes(flag) ? "out" : "note";
}

/**
 * The peak nearest `tt`, or null when none is within `tol` (° 2θ).
 *
 * Hit-testing for the plot's pointer interactions. The tolerance is handed in
 * as degrees because the caller owns the pixel↔2θ mapping — this function must
 * stay testable without a layout engine.
 */
export function nearestPeak(
  peaks: readonly { index: number; two_theta: number }[],
  tt: number,
  tol: number,
): number | null {
  let best: number | null = null;
  let dist = tol;
  for (const p of peaks) {
    const d = Math.abs(p.two_theta - tt);
    if (d <= dist) {
      best = p.index;
      dist = d;
    }
  }
  return best;
}

/**
 * The grab radius for the *move* gesture, in ° 2θ: the smaller of the pixel
 * radius and 1.5× the median fitted FWHM.
 *
 * A pixel radius alone is a screen constant applied to a physics axis, and at
 * the survey view it is destructive: on the corundum pattern (0.19°/px, 64
 * lines over 145°) 10 px is ±1.9°, the 9-px markers themselves tile ~75 % of
 * the axis, and a measured zoom drag starting 0.9° from a line silently moved
 * that line 11° instead of zooming. The FWHM cap says when a drag may *mean*
 * "move this line": once 10 px covers more than ~a line width, the line is
 * subpixel and precision-editing it is not what any drag can express — so the
 * drag falls through to plotly's zoom, which is the survey view's gesture.
 * The coarse pixel radius stays right for the non-destructive gestures
 * (shift-toggle, right-click refit target a *labelled* thing) and for
 * click-to-add, whose final position comes from the group refit, not the
 * pixel.
 */
export function grabToleranceDeg(
  peaks: readonly { fwhm: number }[],
  degPerPx: number,
  pxRadius = 10,
): number {
  const px = pxRadius * degPerPx;
  const widths = peaks.map((p) => p.fwhm).filter((w) => w > 0).sort((a, b) => a - b);
  if (!widths.length) return px;
  return Math.min(px, 1.5 * widths[widths.length >> 1]);
}

/**
 * Group-curve arrays joined into one plotable trace, windows separated by null.
 *
 * One trace instead of one per group: sixty groups as sixty scattergl traces is
 * a measurable legend and draw cost, and the gaps between fit windows are real
 * — a null point breaks the line exactly where the model ends.
 */
export function joinCurves(
  groups: readonly GroupCurve[],
  pick: (g: GroupCurve) => number[],
): { x: (number | null)[]; y: (number | null)[] } {
  const x: (number | null)[] = [];
  const y: (number | null)[] = [];
  for (const g of groups) {
    if (x.length) {
      x.push(null);
      y.push(null);
    }
    x.push(...g.two_theta);
    y.push(...pick(g));
  }
  return { x, y };
}

// ----------------------------------------------------------------------
// candidates
// ----------------------------------------------------------------------
export interface Candidate {
  cell: number[];
  cell_esd: number[];
  system: string;
  centring: string;
  lattice_group: string;
  volume: number;
  n_indexed: number;
  n_lines: number;
  fom: Array<{ name: string; value: number; n_lines: number; blind_spot: string }>;
  found_by: string[];
  confidence: "high" | "medium" | "low";
  confidence_caveats: string[];
  ambiguity: Array<{
    cell: number[];
    index: number;
    system: string;
    discriminating_two_theta: number[];
  }>;
  lebail: {
    rwp: number;
    predicted_but_absent: number;
    n_reflections: number;
    status: string;
  } | null;
  diagnostics: Array<{ level: string; code: string; message: string }>;
}

export interface AdoptVerdict {
  allowed: boolean;
  why: string;
}

/**
 * The FoM columns to show: the union of panel members over all candidates, in
 * first-seen order. A member can be absent on a candidate (what could be
 * computed varies), so the cell is looked up by name, never by position.
 */
export function fomColumns(candidates: readonly Candidate[]): string[] {
  const seen: string[] = [];
  for (const c of candidates) {
    for (const f of c.fom ?? []) {
      if (!seen.includes(f.name)) seen.push(f.name);
    }
  }
  return seen;
}

export function fomOf(candidate: Candidate, name: string): number | null {
  for (const f of candidate.fom ?? []) {
    if (f.name === name) return f.value;
  }
  return null;
}

/** Red for a caveat that refutes, amber for one that merely caps. */
export function caveatTone(caveat: string, refuting: readonly string[]): "bad" | "warn" {
  return refuting.includes(caveat) ? "bad" : "warn";
}

/** `4.7594(3) 4.7594(3) 12.992(1)` style cell summary — lengths only. */
export function cellText(cell: readonly number[]): string {
  const lengths = cell.slice(0, 3).map((v) => v.toFixed(4)).join(" ");
  const angles = cell.slice(3, 6).map((v) => v.toFixed(2)).join(" ");
  return `${lengths} Å · ${angles}°`;
}

/**
 * The furthest discriminating 2θ of a candidate's partners, or null.
 *
 * WP-1024: what survives ambiguity screening is separated only *beyond* the
 * measured range, so the actionable rendering is "collect to here".
 */
export function collectTo(candidate: Candidate): number | null {
  let hi: number | null = null;
  for (const partner of candidate.ambiguity ?? []) {
    for (const tt of partner.discriminating_two_theta ?? []) {
      if (hi === null || tt > hi) hi = tt;
    }
  }
  return hi;
}

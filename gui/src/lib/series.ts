/**
 * What the series panel draws and sends, as pure functions (WP-1016).
 *
 * A series is N separate refinements chained by a warm start, and the two things
 * a panel over it must not get wrong are both about honesty rather than layout.
 *
 * **The order is the series**, so every edit — reorder, remove, a typed
 * coordinate — produces the whole list and one `PUT /api/series` sends it. The
 * arithmetic of "move this one up" is here because it is the only part of that a
 * test can judge without a DOM.
 *
 * **A smooth curve is exactly what a poisoned chain produces** (WP-0505's
 * measured lesson), so `SEQUENTIAL_PATH_DEPENDENT` is the headline and a flagged
 * trajectory is drawn differently rather than annotated in a footnote: the
 * panel gives a flagged parameter the warning colour, dashes its line
 * (`trajectoryLegend`), and — when `direction="both"` ran — draws the backward
 * chain beside it,
 * because the disagreement *is* the evidence and describing it in words would be
 * asking the reader to take it on trust.
 */

export interface SeriesPattern {
  upload: string;
  filename: string;
  label: string;
  x: number | null;
  reader: string;
  /** the *effective* reader keywords this member was read with */
  reader_options: Record<string, string>;
  n_points: number;
  two_theta_range: [number, number];
  /** the *file* carried esds — a mixed series is fitted under two weightings */
  has_sigma: boolean;
}

export interface SeriesSettings {
  carry: string[];
  refit: string;
  direction: string;
  x_label: string;
}

export interface SeriesSetup {
  patterns: SeriesPattern[];
  n_patterns: number;
  settings: SeriesSettings;
  choices: { refit: string[]; direction: string[] };
  carry_help: string;
  defaults: SeriesSettings;
  protocol: { mode: string; plan: string | null; n_stages: number };
  has_x: boolean;
  sigma_mixed: boolean;
  has_result: boolean;
  running: boolean;
}

export interface Trajectory {
  path: string;
  x: number[];
  x_label: string;
  value: number[];
  stderr: Array<number | null>;
  labels: string[];
  path_dependent: boolean;
  discontinuous: boolean;
  /** the backward chain's values, aligned with `x`, when `direction="both"` ran */
  backward: number[] | null;
  /** the largest forward/backward difference in combined σ; `null` when neither
   *  chain estimated an esd, which is where the fence itself abstains */
  n_sigma: number | null;
}

export interface SeriesEntry {
  index: number;
  label: string;
  x: number | null;
  status: string;
  statistics: { rwp: number; gof: number } | null;
  n_iterations: number;
  reseeded: boolean;
  rwp_warm: number | null;
  /** which attempt of the escalation ladder produced these values (WP-1051);
   *  the first pattern of a chain is always `"cold"`, having nothing to warm
   *  from, so this is *not* the same question as `reseeded` */
  rung: string;
  /** every rung attempted on this pattern, in ladder order */
  rungs_tried: string[];
  node_id: string | null;
  tree_id: string | null;
  diagnostics: Array<{ level: string; code: string; message: string }>;
}

/** What the panel sends as one member of the list. */
export function asRequest(patterns: SeriesPattern[]): Array<Record<string, unknown>> {
  return patterns.map((p) => ({
    upload: p.upload, label: p.label,
    // `null` and `undefined` are the same answer here — no coordinate — and the
    // server reads a missing key as "index is the axis"
    ...(p.x === null ? {} : { x: p.x }),
    ...(p.reader_options && Object.keys(p.reader_options).length
      ? { reader_options: p.reader_options } : {}),
  }));
}

/**
 * Move one member by `delta`, clamped — the list unchanged if it cannot move.
 *
 * Returning the same array reference when nothing moves is what lets a caller
 * skip the round trip: reordering the first item upward is a no-op, and a PUT
 * for it would rewrite the server's list to what it already holds and re-read
 * every file to do it.
 */
export function moveBy(patterns: SeriesPattern[], index: number,
                       delta: number): SeriesPattern[] {
  const to = index + delta;
  if (index < 0 || index >= patterns.length || to < 0 || to >= patterns.length) {
    return patterns;
  }
  const next = [...patterns];
  const [moved] = next.splice(index, 1);
  next.splice(to, 0, moved);
  return next;
}

/** Sort the whole list by its coordinate — the ramp a user meant, not the order
 *  a file picker happened to hand over.  Members with no coordinate keep their
 *  places at the end, because inventing one is what `x` being `null` refuses. */
export function sortByX(patterns: SeriesPattern[]): SeriesPattern[] {
  const withX = patterns.filter((p) => p.x !== null);
  const without = patterns.filter((p) => p.x === null);
  return [...withX.sort((a, b) => (a.x as number) - (b.x as number)), ...without];
}

/**
 * The trajectories worth showing first: the path-dependent ones, then the rest.
 *
 * Ranked on `n_sigma` **inside the flagged group only**, which is why the server
 * computes it — a `Diagnostic` carries `where` and no magnitude, so "which
 * parameter disagrees *most*" is not answerable from the fences alone (WP-1012 hit
 * the same wall; the answer was to compute it from the two chains rather than to
 * grow the schema).
 *
 * Sorting the *unflagged* ones by σ too was the first version and a browser
 * showed why not: on a clean ramp nothing is flagged, every distance is under
 * 5e-4 σ, and ordering 15 parameters by that noise put `phases.0.cell.a` — the
 * one anybody opens a ramp to look at — eighth, in an order that reads as random.
 * Below the fence there is nothing to rank, so the series' own first-seen order
 * stands (`Array.prototype.sort` is stable).
 */
export function rankTrajectories(trajectories: Trajectory[]): Trajectory[] {
  const score = (t: Trajectory) => (t.path_dependent ? 2 : t.discontinuous ? 1 : 0);
  return [...trajectories].sort((a, b) => {
    const diff = score(b) - score(a);
    if (diff !== 0) return diff;
    if (!a.path_dependent) return 0;
    return (b.n_sigma ?? 0) - (a.n_sigma ?? 0);
  });
}

/**
 * One trajectory's y-axis title: the parameter's **leaf**, not its path.
 *
 * Measured in a browser, and the reason it is not a character-count threshold
 * like `viz/plots.py:plot_trajectory`'s: a *rotated* title competes with the tick
 * labels for the same fixed left margin, so `phases.0.cell.a` — fifteen
 * characters, well under matplotlib's cut — rendered as `aes.0.cell.a` beside
 * `4.161`-style ticks. The width that clips is the plot's margin, not the string,
 * and the leaf is what a y-axis wants anyway; the full path is the heading
 * directly above.
 *
 * A derived curve keeps its metric on the axis rather than stripping to the
 * leaf: `qpa.LaB6` is a weight percentage, and `r_bragg.`/`r_f.` are the two
 * McCusker residuals (fractions, not percentages). Their leaf alone is the bare
 * phase name — `LaB6` — which carries no unit, reads as a parameter named after
 * the phase, and is identical between the two residuals; naming the metric is
 * what keeps R_Bragg and R_F apart and off a plain leaf.
 */
export function axisTitle(traj: Trajectory | null): string {
  if (!traj) return "";
  if (traj.path.startsWith("qpa.")) return `${traj.path.slice(4)} (wt %)`;
  if (traj.path.startsWith("r_bragg.")) return `${traj.path.slice(8)} R_Bragg`;
  if (traj.path.startsWith("r_f.")) return `${traj.path.slice(4)} R_F`;
  return traj.path.split(".").at(-1) ?? traj.path;
}

/** A one-line reading of a trajectory's standing — the panel's caption. */
export function trajectoryNote(traj: Trajectory | null, sigmaBar: number): string {
  if (!traj) return "";
  if (traj.path_dependent) {
    const n = traj.n_sigma === null ? "" : ` by up to ${traj.n_sigma.toFixed(1)}σ`;
    return `the forward and backward chains disagree${n} (over ${sigmaBar}σ): this `
      + "trajectory depends on the order the series was refined in, so it is not "
      + "determined by the data alone — hold the parameter, restrain it, or quote "
      + "the between-chain spread as its uncertainty";
  }
  if (traj.discontinuous) {
    return "a step far larger than this parameter's own scatter: either the "
      + "specimen changed here or the chain failed and carried the error onward "
      + "— open that pattern's own fit before reading the jump as physics";
  }
  if (traj.backward !== null) {
    return "the forward and backward chains agree within their esds";
  }
  return "";
}

/** One legend entry: the mark it toggles, what it says, and the custom property
 *  its swatch is drawn in, so a theme switch restyles it by CSS alone. */
export interface LegendEntry {
  id: string;
  label: string;
  ink: string;
  mark: "line" | "dash" | "dot" | "ring" | "cross";
}

/**
 * What the trajectory's legend offers — the marks `rxplot.trajectory` draws.
 *
 * A flagged parameter's forward chain wears `--warn` and is dashed, and its
 * name says why: the disagreement between the chains is the evidence, so it is
 * drawn rather than described. The backward chain is offered only when
 * `direction="both"` ran.
 *
 * Reseeded points are ringed and never dropped: the fit is good, but its
 * starting values did not come from its neighbour, so it is not evidence that
 * the trajectory is continuous there (`SEQUENTIAL_RESEED`). A point no rung of
 * the ladder recovered is **crossed** instead (`SEQUENTIAL_UNRECOVERED`,
 * WP-1051). The two marks say opposite things: a ring is a good fit reached
 * from a different starting model, a cross a diverged fit whose value is not a
 * measurement. The crossed point is still plotted, because a gap reads as data
 * nobody collected.
 *
 * A point with no esd carries no whisker at all, which the figure owns. A
 * well-determined trajectory then shows no visible whisker, and that is the
 * data rather than a defect: on the synthetic ramp under `mccusker_default`,
 * σ(a) is 6.5e-6 Å against a 4.8e-3 Å axis over 189 px, so a 2σ whisker is
 * 0.5 px. Scaling it up to be seen would be WP-1029's "an exaggeration is not
 * a probability" one panel over.
 */
export function trajectoryLegend(traj: Trajectory, reseeded: boolean[] = [],
                                 unrecovered: boolean[] = []): LegendEntry[] {
  const flagged = traj.path_dependent;
  const tone = flagged ? "--warn" : "--plot-diff";
  const out: LegendEntry[] = [
    { id: "forward", label: flagged ? "forward (path-dependent)" : "forward",
      ink: tone, mark: flagged ? "dash" : "line" },
  ];
  if (traj.stderr.some((e) => typeof e === "number" && Number.isFinite(e))) {
    out.push({ id: "esd", label: "esd", ink: tone, mark: "line" });
  }
  if (traj.backward) {
    out.push({ id: "backward", label: "backward", ink: "--muted", mark: "dot" });
  }
  if (reseeded.some(Boolean)) {
    out.push({ id: "rings", label: "reseeded", ink: "--warn", mark: "ring" });
  }
  if (unrecovered.some(Boolean)) {
    out.push({ id: "crosses", label: "unrecovered", ink: "--warn", mark: "cross" });
  }
  return out;
}

/** `v` to `n` significant figures, with no trailing zeros. */
const sig = (v: number, n: number) => String(Number(v.toPrecision(n)));

/**
 * What the pointer on one point says: the pattern, its coordinate, and the
 * value, with its esd when the fit gave one. The value takes six significant
 * figures, as the hover did under plotly (`%{y:.6g}`), and the esd two, as an
 * esd is quoted. A backward point is named as the backward chain's, since
 * both chains share every coordinate.
 */
export function pointText(traj: Trajectory, i: number,
                          chain: "forward" | "backward"): string {
  const where = `${traj.labels[i] ?? i} · ${sig(traj.x[i], 6)}`;
  if (chain === "backward") return `${where}: ${sig(traj.backward![i], 6)} (backward)`;
  const e = traj.stderr[i];
  const esd = typeof e === "number" && Number.isFinite(e) ? ` ± ${sig(e, 2)}` : "";
  return `${where}: ${sig(traj.value[i], 6)}${esd}`;
}

/**
 * What a member's pattern chart offers: the fitted points, the masked ones
 * when the protocol masked any, the model, the background and the residual.
 * `rxplot.pattern`'s ids, over its own inks.
 */
export function memberLegend(masked: boolean): LegendEntry[] {
  return [
    { id: "obs", label: "obs", ink: "--plot-obs", mark: "dot" },
    ...(masked ? [{ id: "masked", label: "excluded", ink: "--muted", mark: "dot" } as LegendEntry] : []),
    { id: "calc", label: "calc", ink: "--plot-calc", mark: "line" },
    { id: "bkg", label: "background", ink: "--plot-bkg", mark: "dash" },
    { id: "diff", label: "Δ/σ", ink: "--plot-diff", mark: "line" },
  ];
}

/** Which series entries carry a flag, by trajectory position.
 *
 * A trajectory skips patterns where its path is absent (`SeriesResult.trajectory`
 * does not fill gaps), so the flags are matched on **label** rather than on
 * index — the two are the same list only when every pattern carried the path. */
function flagsFor(traj: Trajectory, entries: SeriesEntry[],
                  flagged: (e: SeriesEntry) => boolean): boolean[] {
  const marked = new Set(entries.filter(flagged).map((e) => e.label));
  return traj.labels.map((label) => marked.has(label));
}

/** Which entries the reseed fence refitted cold. */
export function reseededFlags(traj: Trajectory, entries: SeriesEntry[]): boolean[] {
  return flagsFor(traj, entries, (e) => e.reseeded);
}

/** Which entries no rung of the ladder recovered (WP-1051).
 *
 * Read off `status` rather than a flag of its own, exactly as the library's
 * diagnostic is: "diverged after the last rung" and "diverged" are the same
 * statement once the chain has run, and a second field could disagree with it. */
export function unrecoveredFlags(traj: Trajectory,
                                 entries: SeriesEntry[]): boolean[] {
  return flagsFor(traj, entries, (e) => e.status === "diverged");
}

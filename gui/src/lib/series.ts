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
 * trajectory is drawn differently rather than annotated in a footnote:
 * `trajectoryTraces` gives a flagged parameter the warning colour, dashes its
 * line, and — when `direction="both"` ran — draws the backward chain beside it,
 * because the disagreement *is* the evidence and describing it in words would be
 * asking the reader to take it on trust.
 */

export interface SeriesPattern {
  upload: string;
  filename: string;
  label: string;
  x: number | null;
  reader: string;
  block: string | null;
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
    ...(p.block ? { block: p.block } : {}),
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
 */
export function axisTitle(traj: Trajectory | null): string {
  if (!traj) return "";
  if (traj.path.startsWith("qpa.")) return `${traj.path.slice(4)} (wt %)`;
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

/**
 * plotly traces for one trajectory — value ± esd, and the other chain beside it.
 *
 * Error bars come from `stderr` with the missing entries **dropped rather than
 * zeroed**: a `null` there means that pattern did not estimate one (the parameter
 * was not free in that fit, or a stage returned no covariance), and a zero-length
 * bar is a claim of infinite precision. plotly takes `null` in an
 * `error_y.array`, so the gap stays a gap.
 *
 * Reseeded points are ringed, never dropped: the fit is good, but its starting
 * values did not come from its neighbour, so it is not evidence that the
 * trajectory is continuous there (`SEQUENTIAL_RESEED`).
 */
export function trajectoryTraces(traj: Trajectory, colors: {
  ok: string; warn: string; muted: string;
}, reseeded: boolean[] = []): any[] {
  const flagged = traj.path_dependent;
  const traces: any[] = [{
    type: "scatter",
    mode: "lines+markers",
    name: flagged ? "forward (path-dependent)" : "forward",
    x: traj.x,
    y: traj.value,
    error_y: { type: "data", array: traj.stderr, visible: true, thickness: 1,
               width: 3, color: flagged ? colors.warn : colors.ok },
    line: { color: flagged ? colors.warn : colors.ok, width: 1.4,
            dash: flagged ? "dash" : "solid" },
    marker: { size: 6, color: flagged ? colors.warn : colors.ok },
    hovertemplate: "%{x}: %{y:.6g}<extra>%{text}</extra>",
    text: traj.labels,
  }];
  if (traj.backward) {
    traces.push({
      type: "scatter",
      mode: "lines+markers",
      name: "backward",
      x: traj.x,
      y: traj.backward,
      line: { color: colors.muted, width: 1, dash: "dot" },
      marker: { size: 4, color: colors.muted, symbol: "diamond-open" },
      hovertemplate: "%{x}: %{y:.6g}<extra>backward</extra>",
    });
  }
  const rings = traj.x.filter((_, i) => reseeded[i]);
  if (rings.length) {
    traces.push({
      type: "scatter",
      mode: "markers",
      name: "reseeded",
      x: rings,
      y: traj.value.filter((_, i) => reseeded[i]),
      marker: { size: 13, symbol: "circle-open", color: colors.warn,
                line: { width: 1.4 } },
      hoverinfo: "skip",
    });
  }
  return traces;
}

/** Which series entries the reseed fence refitted cold, by trajectory position.
 *
 * A trajectory skips patterns where its path is absent (`SeriesResult.trajectory`
 * does not fill gaps), so the flags are matched on **label** rather than on
 * index — the two are the same list only when every pattern carried the path. */
export function reseededFlags(traj: Trajectory, entries: SeriesEntry[]): boolean[] {
  const cold = new Set(entries.filter((e) => e.reseeded).map((e) => e.label));
  return traj.labels.map((label) => cold.has(label));
}

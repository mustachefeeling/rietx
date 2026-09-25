/**
 * The pattern panel drawn by the chart module (WP-1461's pilot).
 *
 * `Plot.svelte` loads this module only under `?chart=uplot`, so the plotly
 * renderer stays the default and its boot path is unchanged until the pilot
 * says go. It turns the curves route's payload (D4) into `rxplot.pattern`'s
 * figure and draws what only this panel has on it: the protocol's shading, the
 * candidate's lines, the picked peaks and their fitted profiles, and the hover
 * ring. The figure itself (panes, gestures, markers, ticks) is `rxplot.mjs`'s.
 */

import uPlot from "uplot";
import "uplot/dist/uPlot.min.css";
import { pattern, unpack, vlines, type Curves, type Pattern } from "rxplot";

import { api } from "../api";
import { joinCurves, type GroupCurve, type PeakRow } from "./peaks";
import {
  curveColors,
  maskShapes,
  nearestIndex,
  type CandidateOverlay,
  type Protocol,
  type ResidualKind,
  type Scale,
} from "./plot";

export type { Curves };

/** The project's curves, every channel once (D4). Before a fit, the pattern alone. */
export async function fetchCurves(): Promise<Curves> {
  return unpack(await api.curves());
}

/** Two payloads over the same channels, so a view on one is a view on the other. */
export function sameGrid(a: Curves | null, b: Curves): boolean {
  const x = a?.arrays.two_theta, y = b.arrays.two_theta;
  return !!x && x.length === y.length && x[0] === y[0] && x[x.length - 1] === y[y.length - 1];
}

/**
 * The payload in the shape the plotly renderer's window had.
 *
 * The readout, the curve toggles and the peak markers' heights all read that
 * shape (`lib/plot.ts`), and this pilot changes none of them: the fitted
 * channels on the arrays, and the masked ones on `excluded`. The difference is
 * that nothing here is decimated.
 */
export function windowOf({ header, arrays }: Curves): any {
  const tt = arrays.two_theta, y = arrays.y_obs, kept = arrays.kept;
  const pick = (a: ArrayLike<number>, at: ArrayLike<number>) => Array.from(at, (i) => a[i]);
  const inKept = new Uint8Array(tt.length);
  for (const i of kept) inKept[i] = 1;
  const out: number[] = [];
  for (let i = 0; i < tt.length; i++) if (!inKept[i]) out.push(i);
  const excluded = { two_theta: pick(tt, out), y_obs: pick(y, out) };
  const common = { weighted: header.weighted, excluded, n_excluded: out.length };
  if (!header.fit) return { raw: true, two_theta: pick(tt, kept), y_obs: pick(y, kept), ...common };
  const on = (key: string) => (arrays[key] ? Array.from(arrays[key]) : []);
  return {
    ...common,
    two_theta: pick(tt, arrays.fitted), y_obs: pick(y, arrays.fitted),
    y_calc: on("y_calc"), y_background: on("y_background"), delta: on("delta"),
    delta_raw: on("delta_raw"), cumulative_chi2: on("cumulative_chi2"),
    ticks: header.ticks ?? {}, tick_hkl: header.tick_hkl ?? {}, stale: header.stale,
  };
}

/** What this panel lays over the figure, read at every draw. */
export interface Overlay {
  protocol: Protocol;
  extent: [number, number] | null;
  peaks: readonly PeakRow[] | null;
  groups: readonly GroupCurve[] | null;
  /** the Peaks tab is up: only there are the markers, their fit and the candidate drawn */
  peaksActive: boolean;
  candidate: CandidateOverlay | null;
  hidden: readonly string[];
  /** the payload in window shape (`windowOf`), for a marker's height */
  held: any;
}

export interface ChartOptions {
  scale: Scale;
  kind: ResidualKind;
  labels: { y: () => string; resid: () => string };
}

const Y: Record<Scale, "lin" | "sqrt" | "log"> = { linear: "lin", sqrt: "sqrt", log: "log" };

/** The pattern figure with this panel's layers on it. */
export class PatternChart {
  readonly fig: Pattern;
  private colors: ReturnType<typeof curveColors>;
  private overlay: Overlay;
  private ringAt: number | null = null;
  private readonly ringEl: HTMLDivElement;

  constructor(host: HTMLElement, curves: Curves, overlay: Overlay, opts: ChartOptions) {
    this.overlay = overlay;
    this.colors = readColors();
    this.ringEl = document.createElement("div");
    this.ringEl.className = "rx-ring";
    const shade = (u: any) => this.shade(u);
    this.fig = pattern(uPlot, host, curves, {
      colors: () => ({ ...this.colors, masked: this.colors.edge }),
      y: Y[opts.scale],
      residual: opts.kind,
      hidden: overlay.hidden,
      labels: opts.labels,
      layers: {
        main: { under: [shade, (u) => this.candidateLines(u)],
                over: [(u) => this.peakFit(u), (u) => this.peakMarkers(u), (u) => this.placeRing(u)] },
        ticks: { under: [shade] },
        resid: { under: [shade] },
      },
    });
  }

  /** Re-read the theme's colours and repaint. One microtask first: the shell
   *  stamps the theme in an effect of the same flush (gui/CLAUDE.md). */
  async retheme(): Promise<void> {
    await Promise.resolve();
    this.colors = readColors();
    this.fig.redraw();
  }

  /** New layer inputs; a repaint, never a refetch. */
  update(overlay: Overlay): void {
    this.overlay = overlay;
    this.fig.redraw();
  }

  /** The 2θ under a pointer at `clientX`, or null off the plot area. */
  thetaOf(clientX: number): number | null {
    const u = this.fig.panes.main, box = u.over.getBoundingClientRect();
    const px = clientX - box.left;
    return px < 0 || px > box.width ? null : u.posToVal(px, "x");
  }

  /** Degrees of 2θ per CSS pixel at the current zoom. */
  degPerPx(): number {
    const u = this.fig.panes.main, { min, max } = u.scales.x;
    return u.over.clientWidth ? Math.abs(max - min) / u.over.clientWidth : 0.01;
  }

  /** Put the hover ring on the line at 2θ `at`, or take it off. A DOM move,
   *  never a repaint of the pattern (WP-1032's rule, a step cheaper than
   *  plotly's `restyle`). */
  ring(at: number | null): void {
    this.ringAt = at;
    this.placeRing(this.fig.panes.main);
  }

  destroy(): void {
    this.fig.destroy();
  }

  // -- layers -----------------------------------------------------------

  private shade(u: any): void {
    const { protocol, extent } = this.overlay;
    if (!extent) return;
    const { ctx, bbox } = u, dpr = devicePixelRatio;
    const at = (x: number) => u.valToPos(x, "x", true);
    ctx.save();
    for (const s of maskShapes(protocol, extent, this.colors)) {
      if (s.type === "rect") {
        const l = Math.max(bbox.left, at(s.x0)), r = Math.min(bbox.left + bbox.width, at(s.x1));
        if (r <= l) continue;
        ctx.fillStyle = s.fillcolor;
        ctx.fillRect(l, bbox.top, r - l, bbox.height);
      } else {
        const x = Math.round(at(s.x0)) + 0.5;
        if (x < bbox.left || x > bbox.left + bbox.width) continue;
        ctx.strokeStyle = s.line.color;
        ctx.lineWidth = dpr;
        ctx.setLineDash([2 * dpr, 2 * dpr]);
        ctx.beginPath();
        ctx.moveTo(x, bbox.top);
        ctx.lineTo(x, bbox.top + bbox.height);
        ctx.stroke();
      }
    }
    ctx.restore();
  }

  private candidateLines(u: any): void {
    const lines = this.overlay.candidate?.two_theta;
    if (lines?.length) vlines(u, lines, u.bbox.top, u.bbox.height, this.colors.candidate);
  }

  /** Each group's fitted profile, dashed, on its own channels (D8). */
  private peakFit(u: any): void {
    const { groups, peaksActive, hidden } = this.overlay;
    if (!peaksActive || !groups?.length || hidden.includes("peakfit")) return;
    const { ctx } = u, dpr = devicePixelRatio, fit = joinCurves(groups, (g) => g.y_fit);
    ctx.save();
    ctx.strokeStyle = this.colors.peakfit;
    ctx.lineWidth = 1.4 * dpr;
    ctx.setLineDash([4 * dpr, 3 * dpr]);
    ctx.beginPath();
    let pen = false;
    for (let i = 0; i < fit.x.length; i++) {
      const x = fit.x[i], y = fit.y[i];
      if (x == null || y == null || !(y > 0 || u.scales.y.distr !== 3)) { pen = false; continue; }
      const X = u.valToPos(x, "x", true), Y = u.valToPos(y, "y", true);
      if (pen) ctx.lineTo(X, Y); else ctx.moveTo(X, Y);
      pen = true;
    }
    ctx.stroke();
    ctx.restore();
  }

  /**
   * The picked lines, at the measured intensity nearest each: a circle where
   * the picker fitted it and a diamond where a person placed it, hollow where
   * it is not used. The whisker is capped at 3×FWHM (WP-1027).
   */
  private peakMarkers(u: any): void {
    const { peaks, peaksActive, hidden } = this.overlay;
    if (!peaksActive || !peaks?.length || hidden.includes("peaks")) return;
    const { ctx } = u, dpr = devicePixelRatio, r = 4.5 * dpr, cap = 3 * dpr;
    const { min, max } = u.scales.x;
    ctx.save();
    ctx.strokeStyle = ctx.fillStyle = this.colors.peak;
    ctx.lineWidth = 1.2 * dpr;
    // uPlot leaves the last series' dash on the context (the background's)
    ctx.setLineDash([]);
    for (const p of peaks) {
      if (p.two_theta < min || p.two_theta > max) continue;
      const h = this.height(p.two_theta);
      if (h == null) continue;
      const X = u.valToPos(p.two_theta, "x", true), Y = u.valToPos(h, "y", true);
      const w = Math.min(p.two_theta_esd, 3 * p.fwhm);
      if (w > 0) {
        const a = u.valToPos(p.two_theta - w, "x", true), b = u.valToPos(p.two_theta + w, "x", true);
        ctx.beginPath();
        ctx.moveTo(a, Y); ctx.lineTo(b, Y);
        ctx.moveTo(a, Y - cap); ctx.lineTo(a, Y + cap);
        ctx.moveTo(b, Y - cap); ctx.lineTo(b, Y + cap);
        ctx.stroke();
      }
      ctx.beginPath();
      if (p.origin === "fitted") ctx.arc(X, Y, r, 0, 2 * Math.PI);
      else { ctx.moveTo(X, Y - r); ctx.lineTo(X + r, Y); ctx.lineTo(X, Y + r); ctx.lineTo(X - r, Y); ctx.closePath(); }
      if (p.usable) ctx.fill(); else ctx.stroke();
    }
    ctx.restore();
  }

  /** The measured intensity at the channel nearest 2θ, or null on a log axis at or under zero. */
  private height(tt: number): number | null {
    const w = this.overlay.held, k = nearestIndex(w?.two_theta ?? [], tt);
    const v = k < 0 ? 0 : w.y_obs[k];
    return this.fig.panes.main.scales.y.distr === 3 && !(v > 0) ? null : v;
  }

  private placeRing(u: any): void {
    const el = this.ringEl;
    if (el.parentNode !== u.over) u.over.appendChild(el);
    const at = this.ringAt, h = at == null ? null : this.height(at);
    if (at == null || h == null || at < u.scales.x.min || at > u.scales.x.max) {
      el.style.display = "none";
      return;
    }
    el.style.display = "block";
    el.style.left = `${u.valToPos(at, "x")}px`;
    el.style.top = `${u.valToPos(h, "y")}px`;
    el.style.borderColor = this.colors.peak;
  }
}

function readColors(): ReturnType<typeof curveColors> {
  const style = getComputedStyle(document.body);
  return curveColors((name) => style.getPropertyValue(name));
}

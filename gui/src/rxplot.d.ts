// The types of `src/rietx/viz/static/rxplot.mjs`, which is javascript because
// `rietx watch` and `rietx compare` serve it to a page as it is (WP-1461, D3).
// `vite.config.ts` aliases the name to the file. What is declared here is what
// the GUI calls, so a new use of the module declares its part here first.

declare module "rxplot" {
  /** An unpacked curves payload (D4): the header, and a view per array. */
  export interface Curves {
    header: Record<string, any>;
    arrays: Record<string, Float64Array | Int32Array>;
  }

  export function unpack(buffer: ArrayBuffer): Curves;
  export function lower(xs: ArrayLike<number>, v: number): number;
  export function chi2Base(cum: ArrayLike<number>, xs: ArrayLike<number>, lo: number): number;
  export function token(name: string, el?: Element): string;
  export function vlines(u: any, xs: ArrayLike<number>, top: number, height: number,
                         color: string): void;

  export interface Hit { key: string; idx: number; x: number; left: number; top: number }

  export interface Group {
    panes: Record<string, any>;
    mode: "zoom" | "select";
    onSelect: ((lo: number, hi: number, key: string) => void) | null;
    onCursor: ((hit: Hit | null) => void) | null;
    setX(lo: number, hi: number): void;
    setMode(mode: "zoom" | "select"): void;
    reset(): void;
    unpin(key?: string): void;
    redraw(): void;
    destroy(): void;
  }

  export interface PatternColors {
    obs: string; masked: string; calc: string; bkg: string; diff: string; zero: string;
    phase: string[];
  }

  export type Layer = (u: any) => void;

  export interface PatternSpec {
    colors: () => PatternColors;
    y?: "lin" | "sqrt" | "log";
    residual?: "weighted" | "delta" | "cumulative";
    hidden?: readonly string[];
    labels?: { y?: () => string; resid?: () => string };
    layers?: Record<string, { under?: Layer[]; over?: Layer[] }>;
    rawResidual?: () => ArrayLike<number | null> | null;
  }

  export interface Pattern extends Group {
    setCurves(curves: Curves, keep?: boolean): void;
    setY(kind: "lin" | "sqrt" | "log"): void;
    setResidual(kind: "weighted" | "delta" | "cumulative"): void;
    setHidden(ids: readonly string[]): void;
    refreshResidual(): void;
    chi2Base(): number;
  }

  export function pattern(uPlot: any, host: HTMLElement, curves: Curves,
                          spec: PatternSpec): Pattern;
}

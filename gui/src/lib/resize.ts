/**
 * Drag-to-resize arithmetic, as pure functions.
 *
 * `Console.svelte` (WP-1010) shipped the whole rule inline — a grip on one edge,
 * a floor the drag cannot cross, a neighbour that must survive it, and **one
 * write per drag rather than one per pixel**.  WP-1029 needs the same rule on
 * the plot/sidebar split and on the model pane's columns, so the numbers move
 * here and the grip moves to `panels/Splitter.svelte`.
 *
 * Splitting it this way is not tidiness: jsdom has no layout, so a splitter's
 * *effect* is a screenshot question and only its arithmetic can be asserted.
 * Everything a test can judge is in this file.
 */

/** Which way the pointer travels to make the pane on the grip's side *bigger*. */
export type Grow = "up" | "down" | "left" | "right";

/**
 * Run `work` at most once at a time, and once more if it was asked while busy.
 *
 * The plot's `ResizeObserver` called `Plotly.Plots.resize` once per callback,
 * and a drag delivers one callback per pointer move. Measured on the shipped
 * build (WP-1032 task 1, 22 003-point NAC pattern decimated to 7347 drawn
 * points, five traces): **one resize costs ~111 ms** and a 60-move drag issued
 * **60 of them**, whose latencies climbed 117, 134, 151, 168 … ms — a queue
 * draining at ~17 ms per item while new work arrived every ~17 ms — so the last
 * resolved **1.10 s** after it was asked for. The page never dropped a frame
 * (median 16.7 ms, zero long tasks): plotly's work is chunked, so the defect is
 * not stutter but a canvas that *trails the grip by a second* and keeps
 * redrawing after the mouse is up.
 *
 * Collapsing to "one in flight plus at most one queued" is what makes the last
 * redraw the final size rather than the 60th of a queue. The trailing re-run is
 * the half that matters: dropping the extras outright would leave the plot at
 * whatever size it was when the last accepted call started.
 *
 * A promise-returning `work` is awaited; a synchronous one completes at once.
 */
export function coalesce(work: () => unknown): () => void {
  let running = false;
  let queued = false;
  const done = () => {
    running = false;
    if (queued) {
      queued = false;
      go();
    }
  };
  const go = () => {
    if (running) {
      queued = true;
      return;
    }
    running = true;
    let out: unknown;
    try {
      out = work();
    } catch (error) {
      done();
      throw error;
    }
    if (out && typeof (out as Promise<unknown>).then === "function") {
      (out as Promise<unknown>).then(done, done);
    } else {
      done();
    }
  };
  return go;
}

const AXIS = { up: "y", down: "y", left: "x", right: "x" } as const;
const SIGN = { up: -1, down: 1, left: -1, right: 1 } as const;

/** The pointer coordinate a grip reads; the other one is noise during a drag. */
export function axisOf(grow: Grow): "x" | "y" {
  return AXIS[grow];
}

/** The size a pointer now at `at` asks for, having grabbed at `from` on a pane
 *  that was `start` px.  Sign only: the clamping is the next function's. */
export function dragged(start: number, from: number, at: number, grow: Grow): number {
  return start + SIGN[grow] * (at - from);
}

/**
 * Clamp to the floor, and to whatever must survive of the pane next door.
 *
 * `available` is the extent the two panes share.  Zero (or anything too small to
 * hold `min + keep`) means nothing is measurable — jsdom, or a drag before the
 * first layout — and then only the floor applies, which is the fallback
 * `Console.svelte` shipped with.
 */
export function clampSize(value: number, min: number, keep: number, available: number): number {
  const ceiling = available > keep + min ? available - keep : Number.POSITIVE_INFINITY;
  return Math.round(Math.min(Math.max(value, min), ceiling));
}

/**
 * Fit stored column widths into the space there actually is.
 *
 * A drag clamps against the extent it was performed in; **a stored width has to
 * be clamped against the extent it is being rendered in**, and no drag is
 * present to do it. Found in a browser: widths saved at 1500 px reopened at
 * 1000 px left the third column **24 px wide** — a 3D scene in a sliver. The
 * sidebar covers the same case with a CSS `max-width`, which a row of N sized
 * columns cannot express, so this is that guard as arithmetic.
 *
 * Shrinks proportionally rather than truncating the last column, because the
 * user's *relative* choice is the part worth keeping when their absolute one no
 * longer fits. `available <= 0` means nothing is measurable (jsdom, or before
 * layout) and the widths pass through, which is the same fallback `clampSize`
 * makes.
 */
/**
 * What each of the model pane's three columns needs, in px.
 *
 * `structure` is **measured**, not chosen (WP-1034 task 1): the atom table's
 * `min-content` on the NAC project — six atoms, four species, an aniso tensor on
 * every site — is 448 px, and the column adds 24 px of padding. Below 472 the
 * table cannot show its eight columns at all. `form` and `view` are
 * `Model.svelte`'s own `COL_MIN` and `VIEW_KEEP`, restated here so the threshold
 * below is arithmetic rather than a number somebody liked.
 */
export const MODEL_MIN = { structure: 472, form: 200, view: 260 } as const;

/**
 * Does the model pane have to become one stacked column?
 *
 * Three columns side by side need the structure column's floor plus a form
 * column plus what the 3D view keeps — 932 px. Below that something is being
 * squeezed under its minimum, and the thing that loses is the atom table, which
 * side-scrolls *the whole column* and takes the cell row and the headings with
 * it (measured at 860 px: `10.25710.25790` where a, b, c should be).
 *
 * Zero means nothing is measurable (jsdom, or before the first layout), and
 * then the flex defaults hold — the same fallback `clampSize` and `fitColumns`
 * make.
 */
export function modelStacks(available: number): boolean {
  return available > 0
    && available < MODEL_MIN.structure + MODEL_MIN.form + MODEL_MIN.view;
}

export function fitColumns(widths: number[] | null | undefined, available: number,
                           min = 200, keep = 260): number[] | null {
  if (!widths || !widths.length || available <= 0) return widths ?? null;
  const room = available - keep;
  const total = widths.reduce((a, b) => a + b, 0);
  if (total <= room) return widths;
  const floor = min * widths.length;
  if (room <= floor) return widths.map(() => min);
  const factor = room / total;
  return widths.map((w) => Math.max(min, Math.round(w * factor)));
}

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

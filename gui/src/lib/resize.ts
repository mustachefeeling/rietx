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

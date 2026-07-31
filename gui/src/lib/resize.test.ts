/**
 * The splitter's arithmetic (WP-1029).
 *
 * jsdom has no layout, so a splitter's *effect* is a screenshot question and
 * only this half can be asserted — which is exactly why it was pulled out of
 * `Console.svelte` into pure functions rather than generalised in place.
 */
import { describe, expect, it } from "vitest";

import { axisOf, clampSize, dragged, fitColumns } from "./resize";

describe("which coordinate a grip reads", () => {
  it("is the one its pane grows along", () => {
    expect(axisOf("up")).toBe("y");
    expect(axisOf("down")).toBe("y");
    expect(axisOf("left")).toBe("x");
    expect(axisOf("right")).toBe("x");
  });
});

describe("the size a drag asks for", () => {
  it("grows a top-edge grip when the pointer moves up", () => {
    // Console.svelte's case: the log is below the grip, so dragging *up* makes
    // it taller — the sign that has to be per-edge rather than global
    expect(dragged(150, 400, 340, "up")).toBe(210);
    expect(dragged(150, 400, 460, "up")).toBe(90);
  });

  it("grows a left-edge grip when the pointer moves left", () => {
    // the sidebar: its grip is on its left edge and the pane is to the right
    expect(dragged(420, 900, 820, "left")).toBe(500);
    expect(dragged(420, 900, 980, "left")).toBe(340);
  });

  it("grows a right-edge grip when the pointer moves right", () => {
    // the model pane's columns: each grip is on the right edge of the column
    // it sizes, so the two directions are both in use in one app
    expect(dragged(300, 300, 380, "right")).toBe(380);
  });
});

describe("clamping", () => {
  it("holds the floor", () => {
    expect(clampSize(10, 26, 120, 800)).toBe(26);
  });

  it("leaves the neighbour what it must keep", () => {
    expect(clampSize(999, 26, 120, 800)).toBe(680);
  });

  it("applies the floor alone when nothing is measurable", () => {
    // jsdom, or a drag before the first layout: `available` of 0 must not
    // clamp every pane to a negative ceiling, which is what a naive
    // `available - keep` would do
    expect(clampSize(400, 26, 120, 0)).toBe(400);
    // …and the same when the container is too small to hold both
    expect(clampSize(400, 26, 120, 100)).toBe(400);
  });

  it("rounds, so a style attribute is a whole number of pixels", () => {
    expect(clampSize(210.6, 26, 120, 0)).toBe(211);
  });
});

describe("fitting stored columns into the window they are reopened in", () => {
  it("passes them through when they fit", () => {
    expect(fitColumns([400, 380], 1400, 200, 260)).toEqual([400, 380]);
  });

  it("shrinks them proportionally when they do not", () => {
    // measured in a browser: widths chosen at 1500 px reopened at 1000 px left
    // the third column **24 px** wide.  A drag clamps against the extent it was
    // performed in; a stored width has to be clamped against the one it is
    // rendered in, and no drag is present to do it.
    const fitted = fitColumns([920, 393], 1000, 200, 260)!;
    expect(fitted[0] + fitted[1]).toBeLessThanOrEqual(1000 - 260);
    // the *relative* choice survives, which is the part still worth keeping
    expect(fitted[0] / fitted[1]).toBeCloseTo(920 / 393, 1);
  });

  it("stops at the floor rather than shrinking to nothing", () => {
    expect(fitColumns([900, 900], 500, 200, 260)).toEqual([200, 200]);
  });

  it("leaves them alone when nothing is measurable", () => {
    expect(fitColumns([920, 393], 0)).toEqual([920, 393]);
    expect(fitColumns(null, 1200)).toBeNull();
  });
});

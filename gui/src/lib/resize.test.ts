/**
 * The splitter's arithmetic (WP-1029).
 *
 * jsdom has no layout, so a splitter's *effect* is a screenshot question and
 * only this half can be asserted — which is exactly why it was pulled out of
 * `Console.svelte` into pure functions rather than generalised in place.
 */
import { describe, expect, it } from "vitest";

import { axisOf, clampSize, coalesce, dragged, fitColumns } from "./resize";

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

describe("coalescing the work a drag asks for sixty times", () => {
  /** A worker that finishes when the test says so. */
  function gated() {
    const gates: Array<() => void> = [];
    let started = 0;
    const work = () => {
      started += 1;
      return new Promise<void>((resolve) => gates.push(resolve));
    };
    return { work, gates, started: () => started };
  }

  it("runs the first ask immediately", () => {
    const g = gated();
    coalesce(g.work)();
    expect(g.started()).toBe(1);
  });

  it("collapses every ask made while busy into exactly one more", async () => {
    // the measured case: 60 pointer moves against a 111 ms redraw.  Before this,
    // all 60 were issued and the last resolved 1.10 s after the drag ended.
    const g = gated();
    const ask = coalesce(g.work);
    for (let i = 0; i < 60; i++) ask();
    expect(g.started()).toBe(1);

    g.gates[0]();                       // the first redraw finishes
    await Promise.resolve();
    await Promise.resolve();
    expect(g.started()).toBe(2);        // one trailing run, not 59

    g.gates[1]();
    await Promise.resolve();
    await Promise.resolve();
    expect(g.started()).toBe(2);        // and nothing left queued
  });

  it("runs the trailing one, so the last size drawn is the final size", async () => {
    // dropping the extras outright would leave the plot at whatever size the
    // last *accepted* call started with — the drag's beginning, not its end
    const sizes: number[] = [];
    let release: (() => void) | null = null;
    let current = 0;
    const ask = coalesce(() => {
      sizes.push(current);
      return new Promise<void>((resolve) => (release = resolve));
    });
    current = 100;
    ask();
    for (let px = 101; px <= 160; px++) {
      current = px;
      ask();
    }
    release!();
    await Promise.resolve();
    await Promise.resolve();
    expect(sizes).toEqual([100, 160]);
  });

  it("accepts a synchronous worker, and is re-armed after a throw", () => {
    let n = 0;
    const ask = coalesce(() => {
      n += 1;
      if (n === 1) throw new Error("first one fails");
    });
    expect(ask).toThrow("first one fails");
    ask();
    expect(n).toBe(2);   // a throw must not latch the gate shut for ever
  });
});

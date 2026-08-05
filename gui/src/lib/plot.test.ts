/** The pattern plot's two new choices (WP-1029). */
import { describe, expect, it } from "vitest";

import {
  TICK_BAND,
  curveColors,
  curveToggles,
  formatRegion,
  heldRanges,
  hoverLabel,
  maskShapes,
  masked,
  mergeRegions,
  normalizeRegion,
  residual,
  scaleValues,
  shows,
  span,
  sqrtTicks,
  tickBand,
  toggleCurve,
  type Window,
} from "./plot";

const WEIGHTED: Window = {
  two_theta: [1, 2, 3],
  y_obs: [100, 400, 900],
  y_calc: [98, 405, 890],
  delta: [0.2, -0.25, 0.33],
  delta_raw: [2, -5, 10],
  cumulative_chi2: [0.04, 0.1025, 0.2114],
  weighted: true,
};

describe("choosing a residual", () => {
  it("gives each kind its own axis title", () => {
    expect(residual("weighted", WEIGHTED).title).toBe("(obs−calc)/σ");
    expect(residual("delta", WEIGHTED).title).toBe("obs−calc");
    expect(residual("cumulative", WEIGHTED).title).toBe("Σχ²");
    expect(residual("delta", WEIGHTED).values).toEqual([2, -5, 10]);
  });

  it("names the σ as assumed when it was not measured, and still draws Δ/σ", () => {
    // WP-1029 (s): the fit weighted by Poisson σ, so Δ/σ is exactly what it
    // minimised and is the honest curve to draw — the axis says which σ it is
    const poisson = { ...WEIGHTED, weighted: false };
    const res = residual("weighted", poisson);
    expect(res.title).toBe("(obs−calc)/σ (Poisson σ)");
    expect(res.values).toEqual(WEIGHTED.delta);
  });

  it("labels raw Δ the same either way — it is the same curve", () => {
    const poisson = { ...WEIGHTED, weighted: false };
    expect(residual("delta", poisson).title).toBe("obs−calc");
    expect(residual("delta", poisson).values).toEqual([2, -5, 10]);
  });

  it("drops the zero line under a curve that only rises", () => {
    expect(residual("cumulative", WEIGHTED).zeroline).toBe(false);
    expect(residual("weighted", WEIGHTED).zeroline).toBe(true);
  });
});

describe("scaling the intensity axis", () => {
  it("leaves the data alone unless it is √ — plotly has an axis type for log", () => {
    expect(scaleValues("linear", [1, 4, 9])).toEqual([1, 4, 9]);
    expect(scaleValues("log", [1, 4, 9])).toEqual([1, 4, 9]);
    expect(scaleValues("sqrt", [1, 4, 9])).toEqual([1, 2, 3]);
  });

  it("floors a negative rather than making it NaN", () => {
    // √(negative) is NaN, and one NaN loses the trace rather than the point —
    // the structure viewer's ellipsoid lesson, on a curve
    expect(scaleValues("sqrt", [-3, 0, 4])).toEqual([0, 0, 2]);
  });

  it("labels the √ axis in intensity, not in √counts", () => {
    const ticks = sqrtTicks(900, 3)!;
    expect(ticks.ticktext).toEqual(["0", "300", "600", "900"]);
    expect(ticks.tickvals[3]).toBeCloseTo(30, 12);
    expect(sqrtTicks(0)).toBeNull();
  });
});

describe("the curve colours (WP-1029 q)", () => {
  it("reads each custom property and falls back per property, trimmed", () => {
    const set: Record<string, string> = {
      "--plot-obs": " #112233 ", // getPropertyValue keeps the leading space
      "--plot-diff": "#abc",
    };
    const colors = curveColors((name) => set[name] ?? "");
    expect(colors.obs).toBe("#112233");
    expect(colors.diff).toBe("#abc");
    // the un-set ones fall back to the light values — a page with no
    // stylesheet still draws the shipped plot
    expect(colors.calc).toBe("#c23b22");
    expect(colors.bkg).toBe("#6b7280");
    expect(colors.zero).toBe("#88888888");
  });

  it("reads the mask wash and its edge from properties too (WP-1033)", () => {
    // the edge is `--muted`, not a sixth plot colour: it is chrome for a
    // boundary, and it has to match the ink the strip below the plot uses
    const set: Record<string, string> = { "--plot-mask": "#00000022", "--muted": "#9a9a94" };
    const colors = curveColors((name) => set[name] ?? "");
    expect(colors.mask).toBe("#00000022");
    expect(colors.edge).toBe("#9a9a94");
    expect(curveColors(() => "").mask).toBe("#1b1b1b14");
  });
});

describe("shading what is not fitted (WP-1033)", () => {
  const COLORS = { mask: "#1b1b1b14", edge: "#6b6b66" };
  const EXTENT: [number, number] = [3, 24];

  it("draws nothing when the whole pattern is being fitted", () => {
    expect(maskShapes({ limits: null, regions: [] }, EXTENT, COLORS)).toEqual([]);
  });

  it("shades the *outside* of the fit range, clipped to the measured data", () => {
    // measured in a browser: a shape bound to a data axis takes part in the
    // autorange, so bands drawn past the data to cover a zoom-out *became* the
    // range — the 0.5–59.99° NAC pattern came back reading −40 to 100
    const shapes = maskShapes({ limits: [8, 19], regions: [] }, EXTENT, COLORS);
    const bands = shapes.filter((s) => s.type === "rect");
    expect(bands.map((s) => [s.x0, s.x1])).toEqual([[3, 8], [19, 24]]);
  });

  it("draws no band where a limit is already outside the data", () => {
    // …and no edge either: both are bound to the x axis, so either one placed
    // out there would drag the view with it
    const shapes = maskShapes({ limits: [1, 40], regions: [[30, 33]] }, EXTENT, COLORS);
    expect(shapes).toEqual([]);
  });

  it("puts every shape in paper coordinates, which is what survives a scale", () => {
    // a rectangle in log space is not the rectangle in linear space, and the
    // only free y-domain — TICK_BAND — belongs to the reflection ticks
    const shapes = maskShapes({ limits: [8, 19], regions: [[13, 16]] }, EXTENT, COLORS);
    expect(shapes.every((s) => s.yref === "paper" && s.y0 === 0 && s.y1 === 1)).toBe(true);
    expect(shapes.every((s) => s.xref === "x")).toBe(true);
    // …and under the traces: a wash that dimmed the points would be saying
    // something about the data rather than about the protocol
    expect(shapes.every((s) => s.layer === "below")).toBe(true);
  });

  it("gives every region a band and both its edges", () => {
    const shapes = maskShapes({ limits: null, regions: [[13, 16], [20, 21]] },
                              EXTENT, COLORS);
    expect(shapes.filter((s) => s.type === "rect").map((s) => [s.x0, s.x1]))
      .toEqual([[13, 16], [20, 21]]);
    expect(shapes.filter((s) => s.type === "line").map((s) => s.x0))
      .toEqual([13, 16, 20, 21]);
  });
});

describe("the region list (WP-1033)", () => {
  it("orders a backwards drag and refuses a zero-width one", () => {
    expect(normalizeRegion([19, 8])).toEqual([8, 19]);
    expect(normalizeRegion([8, 19])).toEqual([8, 19]);
    expect(normalizeRegion([8, 8])).toBeNull();
    expect(normalizeRegion([NaN, 19])).toBeNull();
  });

  it("merges overlapping and touching entries, and sorts", () => {
    expect(mergeRegions([[20, 21], [3, 5]])).toEqual([[3, 5], [20, 21]]);
    expect(mergeRegions([[3, 5]], [4, 9])).toEqual([[3, 9]]);
    // touching merges because the mask is inclusive at both ends
    expect(mergeRegions([[3, 5]], [5, 9])).toEqual([[3, 9]]);
    expect(mergeRegions([[3, 9]], [4, 5])).toEqual([[3, 9]]);
  });

  it("merging changes the chip list and provably not the mask", () => {
    // the reason merging is allowed at all: `in_range_mask` removes the *union*
    // of the regions, so this is a presentation change — asserted against the
    // mask over a grid rather than by re-deriving the union in the assertion
    const drawn: [number, number][] = [[13, 16], [15.5, 17], [4, 4.5], [17, 18]];
    const merged = mergeRegions(drawn);
    expect(merged).toEqual([[4, 4.5], [13, 18]]);
    for (let x = 3; x <= 24; x += 0.05) {
      expect(masked(merged, x)).toBe(masked(drawn, x));
    }
  });

  it("labels a chip with what would be sent, not a rounded story", () => {
    expect(formatRegion([13.0004, 16])).toBe("13.000–16.000°");
  });
});

describe("the hover box (WP-1032)", () => {
  it("takes its surface, border and ink from the theme's own properties", () => {
    // nothing themed it before: `hovermode: "x unified"` and a hovertemplate on
    // every trace, over plotly's default *light* box, with `layout.font.color`
    // already themed — light-grey ink on white, on the dark page
    const dark: Record<string, string> = {
      "--panel": " #1e1e1e ", "--line": "#333333", "--fg": "#e6e6e2",
    };
    expect(hoverLabel((name) => dark[name] ?? "")).toEqual({
      bgcolor: "#1e1e1e", bordercolor: "#333333",
      font: { color: "#e6e6e2", size: 11 },
    });
  });

  it("falls back per property to the light palette, as the curve colours do", () => {
    expect(hoverLabel(() => "")).toEqual({
      bgcolor: "#ffffff", bordercolor: "#dcdcd6",
      font: { color: "#1b1b1b", size: 11 },
    });
  });
});

describe("the reflection ticks' own band (WP-1032)", () => {
  it("sits in the gap the two subplots already leave", () => {
    // yaxis2 ends at 0.22 and yaxis starts at 0.28, so this needed no room made
    const band = tickBand(2)!;
    expect(band.axis.domain).toEqual(TICK_BAND);
    expect(TICK_BAND[0]).toBeGreaterThanOrEqual(0.22);
    expect(TICK_BAND[1]).toBeLessThanOrEqual(0.28);
  });

  it("gives every phase a row, in a range that cannot be zoomed away", () => {
    // on the residual axis the rows were at y = −0.5 − row·0.9, so under a
    // cumulative χ² curve running to 6.6e5 (measured on the NAC fit) they were a
    // line on the floor.  Here the coordinate is the band's own.
    const band = tickBand(3)!;
    expect(band.rows).toEqual([-0.5, -1.5, -2.5]);
    expect(band.axis.range).toEqual([-3, 0]);
    expect(band.axis.fixedrange).toBe(true);
    expect(band.axis.showticklabels).toBe(false);
  });

  it("is absent when there is nothing to tick", () => {
    // the raw/peaks view has no reflections at all — an empty axis would still
    // take its slice of the plot's height
    expect(tickBand(0)).toBeNull();
  });
});

describe("which curves are drawn (WP-1032)", () => {
  const FITTED = { ...WEIGHTED, y_background: [3, 3, 3], ticks: { NAC: [1], CaF2: [2] } };

  it("offers the background only when the payload has one", () => {
    // the reported item was "make it possible to toggle the background on"; the
    // trace was already unconditional, so what was missing is the control to
    // turn a *forced* curve off
    expect(curveToggles(FITTED).map((t) => t.id))
      .toEqual(["obs", "calc", "bkg", "diff", "ticks:NAC", "ticks:CaF2"]);
    expect(curveToggles({ ...FITTED, y_background: [] }).map((t) => t.id))
      .toEqual(["obs", "calc", "diff", "ticks:NAC", "ticks:CaF2"]);
  });

  it("offers only the observed points on the raw view", () => {
    // no fit, so there is no calculated curve, no background and no reflection
    // to tick — the state a project is in while peaks are picked
    expect(curveToggles({ ...FITTED, raw: true } as any).map((t) => t.id)).toEqual(["obs"]);
  });

  it("names the difference button whatever the residual knob chose", () => {
    expect(curveToggles(FITTED, "Σχ²").find((t) => t.id === "diff")!.label).toBe("Σχ²");
  });

  it("offers the masked points only when the protocol masks some (WP-1033)", () => {
    // the *points* are a drawing choice and get a toggle; the shading is not,
    // and is switched off only by removing the region that causes it
    const withMask = { ...FITTED, excluded: { two_theta: [3, 4], y_obs: [1, 2] } };
    expect(curveToggles(withMask).map((t) => t.id))
      .toEqual(["obs", "masked", "calc", "bkg", "diff", "ticks:NAC", "ticks:CaF2"]);
    expect(curveToggles({ ...withMask, excluded: { two_theta: [], y_obs: [] } })
      .map((t) => t.id)).not.toContain("masked");
    // and on the raw view, which is the only place a fit range can be seen
    // before there is a fit at all
    expect(curveToggles({ ...withMask, raw: true } as any).map((t) => t.id))
      .toEqual(["obs", "masked"]);
  });

  it("hides by exception, so a curve this build does not know about is drawn", () => {
    expect(shows([], "bkg")).toBe(true);
    expect(shows(["bkg"], "bkg")).toBe(false);
    expect(toggleCurve([], "bkg")).toEqual(["bkg"]);
    expect(toggleCurve(["bkg", "obs"], "bkg")).toEqual(["obs"]);
  });
});

describe("handing the view back (WP-1043)", () => {
  const LIVE = { yaxis: true, yaxis2: true };
  const full = (over: Record<string, any> = {}) => ({
    xaxis: { autorange: false, range: [9.97, 14.66] },
    yaxis: { autorange: false, range: [0, 4200] },
    yaxis2: { autorange: false, range: [-5, 5] },
    yaxis3: { autorange: false, range: [-2, 0] },   // the tick band — ours already
    ...over,
  });

  it("keeps every axis the user has moved", () => {
    expect(heldRanges(full(), LIVE)).toEqual({
      xaxis: [9.97, 14.66], yaxis: [0, 4200], yaxis2: [-5, 5],
    });
  });

  it("leaves an autoranging axis alone, which is what a double-click restores", () => {
    // plotly puts `autorange` back on a double-click, so the *absence* of a
    // range key is how "show me all of it" survives the next redraw
    expect(heldRanges(full({ xaxis: { autorange: true, range: [1.7, 25.3] } }), LIVE))
      .not.toHaveProperty("xaxis");
    expect(heldRanges({}, LIVE)).toEqual({});
    expect(heldRanges(undefined, LIVE)).toEqual({});
  });

  it("never hands back the tick band — it is not the user's axis", () => {
    expect(heldRanges(full(), LIVE)).not.toHaveProperty("yaxis3");
  });

  it("drops a y range whose axis no longer means the same thing", () => {
    // a √ or log scaling re-means `yaxis`, and another residual re-means
    // `yaxis2` (Σχ² runs to hundreds of thousands where Δ/σ runs to ±5)
    expect(heldRanges(full(), { yaxis: false, yaxis2: true }))
      .toEqual({ xaxis: [9.97, 14.66], yaxis2: [-5, 5] });
    expect(heldRanges(full(), { yaxis: true, yaxis2: false }))
      .toEqual({ xaxis: [9.97, 14.66], yaxis: [0, 4200] });
  });

  it("refuses a range that is not two numbers", () => {
    expect(heldRanges(full({ xaxis: { autorange: false, range: ["2020-01-01", 3] } }), LIVE))
      .not.toHaveProperty("xaxis");
    expect(heldRanges(full({ xaxis: { autorange: false } }), LIVE)).not.toHaveProperty("xaxis");
  });

  it("emits a range key only when there is one — an absent key is the autorange", () => {
    expect(span([1, 2])).toEqual({ range: [1, 2] });
    expect(span()).toEqual({});
    expect("range" in span()).toBe(false);
  });
});

/** The pattern plot's two new choices (WP-1029). */
import { describe, expect, it } from "vitest";

import {
  CANDIDATE_AXIS,
  TICK_BAND,
  candidateLines,
  curveColors,
  curveToggles,
  dataOnlyHidden,
  drawnRange,
  formatRegion,
  forget,
  heldRanges,
  hoverLabel,
  isDataOnly,
  maskShapes,
  masked,
  mergeRegions,
  movedAxes,
  nearestIndex,
  noAxes,
  normalizeRegion,
  pinPatch,
  readout,
  residual,
  scaleValues,
  shows,
  span,
  sqrtTicks,
  tickBand,
  toggleCurve,
  userRanges,
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

  it("reads the peak layer's two, which are not `--accent` and `--bad` (WP-1210)", () => {
    // the plumbing only.  *How far apart* these values are is asserted in
    // `tests/test_gui_palette.py`, over `app.css` itself and through the one
    // OKLab distance this package has — a port here would be a second answer.
    const set: Record<string, string> = {
      "--plot-peak": "#8c257e", "--plot-peakfit": "#c158b0",
      "--accent": "#1f5fa8", "--bad": "#c23b22",
    };
    const colors = curveColors((name) => set[name] ?? "");
    expect(colors.peak).toBe("#8c257e");
    expect(colors.peakfit).toBe("#c158b0");
    expect(colors.peak).not.toBe(set["--accent"]);
    expect(colors.peakfit).not.toBe(set["--bad"]);
    // a page with no stylesheet still draws the layer in its own colours
    expect(curveColors(() => "").peak).toBe("#8c257e");
    expect(curveColors(() => "").peakfit).toBe("#c158b0");
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

  describe("the peak layer's own two (WP-1210)", () => {
    const LAYER = { n: 3, groups: 2, active: true };

    it("offers them last, and the fit only when a group was fitted", () => {
      // last because the layer draws over everything else, and offered on the
      // raw view too: a peak list is what a project has *before* a fit
      expect(curveToggles(FITTED, "Δ", LAYER).map((t) => t.id))
        .toEqual(["obs", "calc", "bkg", "diff", "ticks:NAC", "ticks:CaF2",
                  "peaks", "peakfit"]);
      expect(curveToggles({ ...FITTED, raw: true } as any, "Δ", LAYER).map((t) => t.id))
        .toEqual(["obs", "peaks", "peakfit"]);
      expect(curveToggles(FITTED, "Δ", { ...LAYER, groups: 0 }).map((t) => t.id))
        .not.toContain("peakfit");
      expect(curveToggles(FITTED, "Δ", { ...LAYER, n: 0 }).map((t) => t.id))
        .not.toContain("peaks");
      expect(curveToggles(FITTED, "Δ").map((t) => t.id)).not.toContain("peaks");
    });

    it("states the absence rather than dropping the button", () => {
      // "where did my markers go" has an answer — the tab they can be edited
      // on — and a button that is simply not there is not it
      const away = curveToggles(FITTED, "Δ", { ...LAYER, active: false });
      const peaks = away.find((t) => t.id === "peaks")!;
      expect(peaks.absent).toContain("Peaks tab");
      expect(away.find((t) => t.id === "peakfit")!.absent).toBe(peaks.absent);
      // and every other curve is drawable, so none of them carries a reason
      expect(away.filter((t) => t.absent).map((t) => t.id)).toEqual(["peaks", "peakfit"]);
      expect(curveToggles(FITTED, "Δ", LAYER).filter((t) => t.absent)).toEqual([]);
    });
  });

  describe("data only (WP-1210)", () => {
    const LAYER = { n: 3, groups: 2, active: false };

    it("hides every id but the measured points, absent ones included", () => {
      // an absent layer left out here would arrive drawn the moment its tab
      // came up, which is the button's meaning quietly lapsing
      const toggles = curveToggles(FITTED, "Δ", LAYER);
      expect(dataOnlyHidden(toggles))
        .toEqual(["calc", "bkg", "diff", "ticks:NAC", "ticks:CaF2", "peaks", "peakfit"]);
      expect(isDataOnly(toggles, dataOnlyHidden(toggles))).toBe(true);
    });

    it("is not on while anything else is drawn, or while obs is not", () => {
      const toggles = curveToggles(FITTED, "Δ", LAYER);
      expect(isDataOnly(toggles, [])).toBe(false);
      expect(isDataOnly(toggles, ["calc"])).toBe(false);
      // obs hidden as well is *nothing* drawn, which is not the same claim
      expect(isDataOnly(toggles, [...dataOnlyHidden(toggles), "obs"])).toBe(false);
      // a lone `obs` cannot be "data only": there is nothing else to be without
      expect(isDataOnly([{ id: "obs", label: "obs", title: "" }], [])).toBe(false);
    });
  });
});

describe("an indexing candidate's lines (WP-1211)", () => {
  it("draws each position as its own full-height segment", () => {
    // one trace with null gaps, not N traces: sixty windows as sixty traces is
    // a legend rather than a layer (the peak layer's rule), and at the server's
    // cap the alternative is two thousand of them
    const { x, y } = candidateLines([20.49, 25.58]);
    expect(x).toEqual([20.49, 20.49, null, 25.58, 25.58, null]);
    expect(y).toEqual([0, 1, null, 0, 1, null]);
  });

  it("draws nothing from nothing", () => {
    expect(candidateLines([])).toEqual({ x: [], y: [] });
  });

  it("hangs them on an overlaying axis pinned to [0, 1]", () => {
    // overlaying `y` is what makes "full height" the height of the *plot*: the
    // axis takes yaxis's domain and keeps its own range, so a zoomed intensity
    // axis or a √ scaling cannot shorten a predicted line.  And fixedrange, for
    // tickBand's reason — a vertical coordinate that means nothing must not be
    // zoomable.
    expect(CANDIDATE_AXIS.overlaying).toBe("y");
    expect(CANDIDATE_AXIS.range).toEqual([0, 1]);
    expect(CANDIDATE_AXIS.fixedrange).toBe(true);
    expect(CANDIDATE_AXIS.showticklabels).toBe(false);
  });

  it("has a colour of its own, not the peak layer's", () => {
    // both layers are up on the same tab at the same time, and telling them
    // apart *is* the question the overlay answers — which of the picked lines
    // does this cell account for (WP-1210's rule, at its sharpest)
    const colors = curveColors(() => "");
    expect(colors.candidate).toBe("#1a8f45");
    expect(colors.candidate).not.toBe(colors.peak);
    expect(colors.candidate).not.toBe(colors.peakfit);
    expect(curveColors((n) => (n === "--plot-candidate" ? "#0f0" : "")).candidate)
      .toBe("#0f0");
  });

  it("is not a curve toggle, so `data only` cannot hide it", () => {
    // its control is the candidate row.  A toggle would be a second one, and
    // pressing it would leave a row looking selected with nothing on the plot.
    const toggles = curveToggles(
      { ...WEIGHTED, ticks: { NAC: [1] } }, "Δ", { n: 1, groups: 0, active: true });
    expect(toggles.map((t) => t.id)).not.toContain("candidate");
    expect(dataOnlyHidden(toggles)).not.toContain("candidate");
  });
});

describe("handing the view back (WP-1044)", () => {
  const LIVE = { yaxis: true, yaxis2: true };
  const full = (over: Record<string, any> = {}) => ({
    xaxis: { autorange: false, range: [9.97, 14.66] },
    yaxis: { autorange: false, range: [0, 4200] },
    yaxis2: { autorange: false, range: [-5, 5] },
    yaxis3: { autorange: false, range: [-2, 0] },   // the tick band — ours already
    ...over,
  });

  it("keeps every axis that carries an explicit range", () => {
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

describe("a redraw never moves the axes (WP-1212)", () => {
  const full = (over: Record<string, any> = {}) => ({
    xaxis: { autorange: true, range: [-3.07, 63.56] },
    yaxis: { autorange: true, range: [-18597.7, 283838.2] },
    yaxis2: { autorange: true, range: [-81.8, 61.7] },
    yaxis3: { autorange: false, range: [-2, 0] },
    yaxis4: { autorange: false, range: [0, 1] },
    ...over,
  });

  describe("pinning what plotly autoranged", () => {
    it("writes every autoranging axis back as an explicit range", () => {
      expect(pinPatch(full())).toEqual({
        "xaxis.range": [-3.07, 63.56],
        "yaxis.range": [-18597.7, 283838.2],
        "yaxis2.range": [-81.8, 61.7],
      });
    });

    it("is empty once they are explicit, so a repaint costs no relayout", () => {
      expect(pinPatch(full({
        xaxis: { autorange: false, range: [-3.07, 63.56] },
        yaxis: { autorange: false, range: [-18597.7, 283838.2] },
        yaxis2: { autorange: false, range: [-81.8, 61.7] },
      }))).toEqual({});
      expect(pinPatch({})).toEqual({});
      expect(pinPatch(undefined)).toEqual({});
    });

    it("leaves the tick band and the candidate axis out of it", () => {
      // both are declared with a range of their own and neither autoranges, so
      // pinning either would be a claim about an axis nobody can move (WP-1211)
      const patch = pinPatch(full({
        yaxis3: { autorange: true, range: [-2, 0] },
        yaxis4: { autorange: true, range: [0, 1] },
      }));
      expect(patch).not.toHaveProperty("yaxis3.range");
      expect(patch).not.toHaveProperty("yaxis4.range");
    });

    it("refuses a range that is not two finite numbers", () => {
      expect(pinPatch(full({ xaxis: { autorange: true, range: ["a", 3] } })))
        .not.toHaveProperty("xaxis.range");
      expect(pinPatch(full({ xaxis: { autorange: true } })))
        .not.toHaveProperty("xaxis.range");
    });

    it("leaves an axis with nothing drawn on it autoranging", () => {
      // A guard, not a repair: Chrome drops an unused axis from `_fullLayout`
      // altogether, so there is nothing there to pin (measured — hiding the
      // residual makes `yaxis2` *absent*, and it comes back at its own range).
      // What made it look like a defect is this suite's own stub, which
      // synthesises every axis whether or not a trace is on it.
      expect(pinPatch(full(), ["yaxis2"])).toEqual({
        "xaxis.range": [-3.07, 63.56], "yaxis.range": [-18597.7, 283838.2],
      });
      expect(pinPatch(full(), ["xaxis", "yaxis", "yaxis2"])).toEqual({});
    });

    it("pins the range the axis is drawing with, not the one it is carrying", () => {
      // On the first plot of a fresh div the two disagree: `range` was still
      // plotly's empty-axis default while the ticks, the pixel map and `_rl`
      // all said 0-60° (WP-1212, measured on the raw view). Pinning `range`
      // there froze a blank plot.
      expect(pinPatch(full({
        xaxis: { autorange: true, range: [-1, 6], _rl: [-3.07, 63.56] },
      }))["xaxis.range"]).toEqual([-3.07, 63.56]);
      expect(drawnRange({ range: [-1, 6], _rl: [-3.07, 63.56] })).toEqual([-3.07, 63.56]);
      expect(drawnRange({ range: [9.97, 14.66] })).toEqual([9.97, 14.66]);
      expect(drawnRange({ _rl: ["a", 3], range: [1, 2] })).toEqual([1, 2]);
      expect(drawnRange({})).toBeNull();
      expect(drawnRange(undefined)).toBeNull();
    });
  });

  it("hands back the drawn range too, so a stale one cannot survive a redraw", () => {
    expect(heldRanges({ xaxis: { autorange: false, range: [-1, 6], _rl: [10, 14] } },
                      { yaxis: true, yaxis2: true })).toEqual({ xaxis: [10, 14] });
  });

  describe("which axes a person moved", () => {
    it("reads a drag off the range keys plotly emits", () => {
      expect(movedAxes({ "xaxis.range[0]": 9.97, "xaxis.range[1]": 14.66 }))
        .toEqual({ moved: ["xaxis"], reset: false });
    });

    it("takes a box zoom as both axes at once", () => {
      expect(movedAxes({
        "xaxis.range[0]": 9.97, "xaxis.range[1]": 14.66,
        "yaxis.range[0]": 0, "yaxis.range[1]": 4200,
      })).toEqual({ moved: ["xaxis", "yaxis"], reset: false });
    });

    it("reads a double-click as a reset, never as a move", () => {
      // `doubleClick: \"autosize\"` hands every axis back at once, which is the
      // one gesture that undoes what the user said rather than restating it
      expect(movedAxes({ "xaxis.autorange": true, "yaxis.autorange": true }))
        .toEqual({ moved: [], reset: true });
    });

    it("is silent about anything else, an empty event included", () => {
      expect(movedAxes({ dragmode: "select" })).toEqual({ moved: [], reset: false });
      expect(movedAxes({})).toEqual({ moved: [], reset: false });
      expect(movedAxes(null)).toEqual({ moved: [], reset: false });
      expect(movedAxes(undefined)).toEqual({ moved: [], reset: false });
    });

    it("ignores the tick band's own axis", () => {
      expect(movedAxes({ "yaxis3.range[0]": -2, "yaxis3.range[1]": 0 }))
        .toEqual({ moved: [], reset: false });
    });
  });

  describe("what survives a re-fit", () => {
    const ranges = { xaxis: [9.97, 14.66], yaxis: [0, 4200], yaxis2: [-5, 5] } as const;

    it("keeps the zoom a person made and drops the pin this panel wrote", () => {
      expect(userRanges(ranges as any, { xaxis: true, yaxis: false, yaxis2: false }))
        .toEqual({ xaxis: [9.97, 14.66] });
    });

    it("keeps nothing when nobody has moved anything", () => {
      // the first paint of a payload on a plot nobody has touched: every axis
      // re-fits, which is the one paint that is allowed to
      expect(userRanges(ranges as any, noAxes())).toEqual({});
    });

    it("cannot invent an axis the layout did not resolve", () => {
      expect(userRanges({ xaxis: [1, 2] }, { xaxis: true, yaxis: true, yaxis2: true }))
        .toEqual({ xaxis: [1, 2] });
    });

    it("forgets a y axis a knob has re-meant, and only that one", () => {
      // A range dragged on Δ/σ is not a range on Σχ², which runs to hundreds of
      // thousands. `heldRanges`' `live` gate covers the paint the knob causes;
      // this covers the *next* re-fit, which is the one that would read the
      // stale flag and keep a range nobody chose for the curve now on the axis.
      const all = { xaxis: true, yaxis: true, yaxis2: true };
      expect(forget(all, { yaxis: true, yaxis2: false }))
        .toEqual({ xaxis: true, yaxis: true, yaxis2: false });
      expect(forget(all, { yaxis: false, yaxis2: true }))
        .toEqual({ xaxis: true, yaxis: false, yaxis2: true });
      // the 2θ axis means the same thing under every knob this panel has
      expect(forget(all, { yaxis: false, yaxis2: false }).xaxis).toBe(true);
      // and it never *grants* one: a knob cannot say a person zoomed
      expect(forget(noAxes(), { yaxis: true, yaxis2: true })).toEqual(noAxes());
    });
  });
});

describe("the readout strip (WP-1213)", () => {
  const FITTED = {
    ...WEIGHTED,
    y_background: [3, 4, 5],
    ticks: { NAC: [1.002, 2.5], CaF2: [2.9] },
  };
  const PEAKS = [
    { index: 0, two_theta: 2.0004, two_theta_esd: 0.0003, d: 4.4, intensity: 50,
      fwhm: 0.1, group: 0, n_in_group: 1, chi2_red: 1, flags: [],
      origin: "fitted" as const, usable: true },
    { index: 1, two_theta: 2.9, two_theta_esd: 0.0002, d: 3.1, intensity: 100,
      fwhm: 0.1, group: 1, n_in_group: 1, chi2_red: 1, flags: [],
      origin: "manual" as const, usable: true },
  ];
  const GROUPS = [
    { group: 0, two_theta: [1.9, 2.0, 2.1], y_fit: [10, 400, 11],
      y_env: [0, 0, 0], delta: [0.1, -0.2, 0.3], chi2_red: 1, n_components: 1 },
  ];
  const value = (r: ReturnType<typeof readout>, id: string) =>
    r!.rows.find((row) => row.id === id)?.value;

  it("reads the channel nearest the pointer, not the pointer", () => {
    // the curves are drawn at channels, so a readout quoting a 2θ between two
    // of them would print one position and another channel's intensities
    const out = readout(FITTED, 1.9, { kind: "weighted" })!;
    expect(out.position).toBe("2.0000°");
    expect(value(out, "obs")).toBe("400");
    expect(value(out, "calc")).toBe("405");
    expect(value(out, "bkg")).toBe("4");
  });

  it("finds the nearest channel by halving, over a long ascending axis", () => {
    const xs = Array.from({ length: 1001 }, (_, i) => 5 + i * 0.01);
    expect(nearestIndex(xs, 5)).toBe(0);
    expect(nearestIndex(xs, 15)).toBe(1000);
    expect(nearestIndex(xs, 9.997)).toBe(500);   // 10.00 is nearer than 9.99
    expect(nearestIndex(xs, -3)).toBe(0);        // off the end, both ways
    expect(nearestIndex(xs, 99)).toBe(1000);
    expect(nearestIndex([], 1)).toBe(-1);
  });

  it("names the residual on screen, and only that one", () => {
    expect(value(readout(FITTED, 3, { kind: "weighted" }), "diff")).toBe("0.33");
    const cumulative = readout(FITTED, 3, { kind: "cumulative" })!;
    expect(cumulative.rows.find((r) => r.id === "diff")!.label).toBe("Σχ²");
    expect(cumulative.rows.filter((r) => r.id === "diff")).toHaveLength(1);
  });

  it("quotes the unscaled intensity at six figures, as the deleted templates did", () => {
    // `%{customdata:.6g}` over `w.y_obs`, never the √ of it: a strip that read
    // in √counts beside an axis labelled in intensity is two answers
    const big = { ...FITTED, y_obs: [1234567.89, 400, 900] };
    expect(value(readout(big, 1, { kind: "weighted" }), "obs")).toBe("1234570");
  });

  it("computes d from the source's primary line, and omits it without one", () => {
    // λ/(2 sin θ) at 2θ = 2°, λ = 1.5406 Å
    expect(readout(FITTED, 2, { kind: "weighted", wavelengths: [1.5406] })!.d)
      .toBe("44.1372 Å");
    expect(readout(FITTED, 2, { kind: "weighted" })!.d).toBe("");
  });

  it("gives every drawn curve a row and every undrawn one none", () => {
    // the strip's shape follows the payload and the tab, never the pointer:
    // a row that appeared and vanished under one sweep would reflow it
    expect(readout(FITTED, 2, { kind: "weighted" })!.rows.map((r) => r.id))
      .toEqual(["obs", "calc", "bkg", "diff", "ticks:NAC", "ticks:CaF2"]);
    expect(readout({ ...FITTED, y_background: [] }, 2, { kind: "weighted" })!
      .rows.map((r) => r.id)).not.toContain("bkg");
    // the raw view: no model, no background, no ticks
    expect(readout({ ...FITTED, raw: true, ticks: {} } as any, 2, { kind: "weighted" })!
      .rows.map((r) => r.id)).toEqual(["obs"]);
  });

  it("gives each row the ink of the mark it names", () => {
    const inks = Object.fromEntries(
      readout(FITTED, 2, { kind: "weighted" })!.rows.map((r) => [r.id, r.ink]));
    expect(inks).toMatchObject({ obs: "obs", calc: "calc", bkg: "bkg", diff: "diff" });
    // a phase's tick row has no ink: the ticks are one colour per phase from
    // plotly's own cycle, and naming one here would be a second palette
    expect(inks["ticks:NAC"]).toBeUndefined();
  });

  it("says how far the nearest reflection of each phase is, signed", () => {
    const out = readout(FITTED, 1, { kind: "weighted" })!;
    expect(value(out, "ticks:NAC")).toBe("+0.0020°");
    expect(value(out, "ticks:CaF2")).toBe("+1.9000°");
    expect(value(readout(FITTED, 3, { kind: "weighted" }), "ticks:CaF2")).toBe("−0.1000°");
  });

  it("prints a picked line as the peak table prints it (WP-1209)", () => {
    const out = readout(FITTED, 2, {
      kind: "weighted", peaks: PEAKS, peaksActive: true, peakTolerance: 0.05 });
    // four places, esd in the last of them, and I relative to the strongest
    // *measured* line — the raw area means nothing on its own
    expect(value(out, "peak")).toBe("#0 2.0004(3)° · I 50.0");
  });

  it("keeps the picked-line slot with an em dash when none is in reach", () => {
    const out = readout(FITTED, 1, {
      kind: "weighted", peaks: PEAKS, peaksActive: true, peakTolerance: 0.05 });
    expect(value(out, "peak")).toBe("—");
  });

  it("has no peak row at all away from the tab that draws the layer (WP-1210)", () => {
    const out = readout(FITTED, 2, { kind: "weighted", peaks: PEAKS, groups: GROUPS });
    expect(out!.rows.map((r) => r.id)).not.toContain("peak");
    expect(out!.rows.map((r) => r.id)).not.toContain("peakfit");
  });

  it("names the fitted group profile, which is why it stopped being skipped", () => {
    // WP-1210 gave the dashed curve a hover so a reader could tell it from the
    // model; deleting the templates means the strip carries that naming
    const out = readout(FITTED, 2, {
      kind: "weighted", groups: GROUPS, peaksActive: true });
    expect(out!.rows.find((r) => r.id === "peakfit")!.label).toBe("peak fit");
    expect(value(out, "peakfit")).toBe("400");
    // outside every fitted window there is no curve to quote
    expect(value(readout(FITTED, 3, {
      kind: "weighted", groups: GROUPS, peaksActive: true }), "peakfit")).toBe("—");
  });

  it("adds the groups' own residual only on the raw view, where it is drawn", () => {
    const raw = { ...FITTED, raw: true, ticks: {} } as any;
    expect(readout(raw, 2, { kind: "weighted", groups: GROUPS, peaksActive: true })!
      .rows.map((r) => r.id)).toEqual(["obs", "peakfit", "peakdelta"]);
    expect(readout(FITTED, 2, { kind: "weighted", groups: GROUPS, peaksActive: true })!
      .rows.map((r) => r.id)).not.toContain("peakdelta");
  });

  it("names the candidate line by hkl and by the λ it belongs to (WP-1211)", () => {
    const candidate = {
      label: "4.7 4.7 12.9 Å", n_total: 3, two_theta: [1.0, 2.001, 2.9],
      hkl: [[1, 0, 0], [1, 0, -4], [1, 1, 0]], line: [0, 1, 0],
    };
    const out = readout(FITTED, 2, {
      kind: "weighted", candidate, candidateTolerance: 0.05,
      wavelengths: [1.5406, 1.5444] });
    expect(value(out, "candidate")).toBe("(1 0 −4) · λ 1.5444 Å · +0.0010°");
  });

  it("quotes no ordinal and no count, because the drawn set can be a sample", () => {
    // past `MAX_CANDIDATE_TICKS` the server thins by rank, so "the 743rd line"
    // would be a statement about the sample; the status line owns the count
    const candidate = {
      label: "c", n_total: 92103, two_theta: [2.0], hkl: [[1, 0, 0]], line: [0] };
    const text = value(readout(FITTED, 2, {
      kind: "weighted", candidate, wavelengths: [1.5406] }), "candidate")!;
    expect(text).not.toMatch(/92103|#|\bof\b/);
  });

  it("keeps the candidate slot when nothing is near, and drops it with no overlay", () => {
    const candidate = { label: "c", n_total: 1, two_theta: [1.0],
                        hkl: [[1, 0, 0]], line: [0] };
    expect(value(readout(FITTED, 3, {
      kind: "weighted", candidate, candidateTolerance: 0.05 }), "candidate")).toBe("—");
    expect(readout(FITTED, 3, { kind: "weighted" })!.rows.map((r) => r.id))
      .not.toContain("candidate");
  });

  it("answers nothing where there is nothing to read", () => {
    expect(readout(null, 2, { kind: "weighted" })).toBeNull();
    expect(readout(FITTED, NaN, { kind: "weighted" })).toBeNull();
    expect(readout({ ...FITTED, two_theta: [] }, 2, { kind: "weighted" })).toBeNull();
  });
});

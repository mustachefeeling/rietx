/** The pattern plot's two new choices (WP-1029). */
import { describe, expect, it } from "vitest";

import {
  TICK_BAND,
  curveColors,
  curveToggles,
  hoverLabel,
  residual,
  scaleValues,
  shows,
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

  it("hides by exception, so a curve this build does not know about is drawn", () => {
    expect(shows([], "bkg")).toBe(true);
    expect(shows(["bkg"], "bkg")).toBe(false);
    expect(toggleCurve([], "bkg")).toEqual(["bkg"]);
    expect(toggleCurve(["bkg", "obs"], "bkg")).toEqual(["obs"]);
  });
});

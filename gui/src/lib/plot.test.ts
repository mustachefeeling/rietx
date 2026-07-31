/** The pattern plot's two new choices (WP-1029). */
import { describe, expect, it } from "vitest";

import { residual, scaleValues, sqrtTicks, type Window } from "./plot";

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

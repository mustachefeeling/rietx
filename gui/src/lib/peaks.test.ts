/**
 * WP-1027 — the peak-picker logic that must hold without a DOM.
 *
 * The two colour splits (unusable flags, refuting caveats) are asserted to be
 * *data-driven*: the functions take the server's list and never carry one of
 * their own, which is what keeps the chips honest when a vocabulary grows.
 */
import { describe, expect, it } from "vitest";

import {
  caveatTone,
  cellText,
  collectTo,
  flagTone,
  fomColumns,
  fomOf,
  grabToleranceDeg,
  joinCurves,
  nearestPeak,
  type Candidate,
  type GroupCurve,
} from "./peaks";

describe("flag and caveat tones come from the served lists", () => {
  it("marks a flag as out only when the server says it is unusable", () => {
    const unusable = ["ghost_kbeta", "excluded", "not_separable"];
    expect(flagTone("excluded", unusable)).toBe("out");
    expect(flagTone("not_separable", unusable)).toBe("out");
    expect(flagTone("sigma_assumed", unusable)).toBe("note");
    // a grown vocabulary changes nothing here — the split is the argument
    expect(flagTone("some_future_flag", [...unusable, "some_future_flag"])).toBe("out");
  });

  it("colours a caveat red only when the served refuting set holds it", () => {
    const refuting = ["predicted_but_absent", "validation_failed"];
    expect(caveatTone("predicted_but_absent", refuting)).toBe("bad");
    expect(caveatTone("shift_allowance_assumed", refuting)).toBe("warn");
  });
});

describe("nearestPeak", () => {
  const peaks = [
    { index: 0, two_theta: 10.0 },
    { index: 3, two_theta: 10.05 },
    { index: 7, two_theta: 25.0 },
  ];

  it("returns the closest peak inside the tolerance, by its index field", () => {
    expect(nearestPeak(peaks, 10.04, 0.1)).toBe(3);
    expect(nearestPeak(peaks, 9.99, 0.1)).toBe(0);
    expect(nearestPeak(peaks, 25.4, 0.5)).toBe(7);
  });

  it("returns null when nothing is inside the tolerance", () => {
    expect(nearestPeak(peaks, 17.0, 0.2)).toBeNull();
    expect(nearestPeak([], 10.0, 1.0)).toBeNull();
  });

  it("can hit index 0 — the ?? -1 trap at the call site is real", () => {
    expect(nearestPeak(peaks, 10.0, 0.01)).toBe(0);
  });
});

describe("grabToleranceDeg — the move gesture's radius is readable, not a screen constant", () => {
  const lab = Array.from({ length: 5 }, (_, i) => ({ fwhm: 0.2 + 0.01 * i })); // median 0.22

  it("caps the pixel radius at 1.5× the median FWHM at the survey view", () => {
    // corundum's measured survey view: 0.19 °/px → 10 px would be 1.9°, and a
    // zoom drag starting 0.9° from a line moved it 11°; the cap refuses that
    expect(grabToleranceDeg(lab, 0.19)).toBeCloseTo(1.5 * 0.22, 12);
  });

  it("keeps the 10 px rule once zoomed in enough for the line to be visible", () => {
    expect(grabToleranceDeg(lab, 0.01)).toBeCloseTo(0.1, 12);
  });

  it("scales with the pattern: a synchrotron list caps far tighter", () => {
    const sharp = [{ fwhm: 0.01 }, { fwhm: 0.012 }, { fwhm: 0.014 }];
    expect(grabToleranceDeg(sharp, 0.01)).toBeCloseTo(1.5 * 0.012, 12);
  });

  it("falls back to the pixel rule when no width is known", () => {
    expect(grabToleranceDeg([], 0.05)).toBeCloseTo(0.5, 12);
    expect(grabToleranceDeg([{ fwhm: 0 }], 0.05)).toBeCloseTo(0.5, 12);
  });
});

describe("joinCurves", () => {
  const groups: GroupCurve[] = [
    { group: 0, two_theta: [1, 2], y_fit: [10, 20], y_env: [1, 1],
      delta: [0, 1], chi2_red: 1, n_components: 1 },
    { group: 2, two_theta: [5, 6], y_fit: [30, 40], y_env: [2, 2],
      delta: [2, 3], chi2_red: 1, n_components: 1 },
  ];

  it("separates fit windows with a null so the line breaks between them", () => {
    const { x, y } = joinCurves(groups, (g) => g.y_fit);
    expect(x).toEqual([1, 2, null, 5, 6]);
    expect(y).toEqual([10, 20, null, 30, 40]);
  });

  it("joins any picked field the same way", () => {
    expect(joinCurves(groups, (g) => g.delta).y).toEqual([0, 1, null, 2, 3]);
  });
});

const CANDIDATE: Candidate = {
  cell: [4.7594, 4.7594, 12.992, 90, 90, 120],
  cell_esd: [3e-4, 3e-4, 1e-3, 0, 0, 0],
  system: "hexagonal",
  centring: "R",
  lattice_group: "R -3 m",
  volume: 254.9,
  n_indexed: 20,
  n_lines: 20,
  fom: [
    { name: "M20", value: 43.1, n_lines: 20, blind_spot: "oversized cells" },
    { name: "F20", value: 80.2, n_lines: 20, blind_spot: "" },
  ],
  found_by: ["dichotomy", "trial_error"],
  confidence: "medium",
  confidence_caveats: ["shift_allowance_assumed"],
  ambiguity: [],
  lebail: { rwp: 0.21, predicted_but_absent: 0, n_reflections: 28, status: "converged" },
  diagnostics: [],
};

describe("the candidate table's shape", () => {
  it("collects FoM columns as the union over candidates, first seen first", () => {
    const other = { ...CANDIDATE, fom: [
      { name: "M20", value: 12, n_lines: 20, blind_spot: "" },
      { name: "coverage", value: 0.9, n_lines: 20, blind_spot: "" },
    ] };
    expect(fomColumns([CANDIDATE, other])).toEqual(["M20", "F20", "coverage"]);
    expect(fomColumns([])).toEqual([]);
  });

  it("looks a member up by name, never by position", () => {
    expect(fomOf(CANDIDATE, "F20")).toBe(80.2);
    expect(fomOf(CANDIDATE, "coverage")).toBeNull();
  });

  it("summarises a cell as lengths and angles", () => {
    expect(cellText(CANDIDATE.cell)).toBe("4.7594 4.7594 12.9920 Å · 90.00 90.00 120.00°");
  });

  it("finds the furthest discriminating 2θ — the collect-to-here annotation", () => {
    expect(collectTo(CANDIDATE)).toBeNull();
    const ambiguous = { ...CANDIDATE, ambiguity: [
      { cell: [1, 1, 1, 90, 90, 90], index: 2, system: "cubic",
        discriminating_two_theta: [158.2, 161.7] },
      { cell: [2, 2, 2, 90, 90, 90], index: 4, system: "cubic",
        discriminating_two_theta: [155.0] },
    ] };
    expect(collectTo(ambiguous)).toBe(161.7);
  });
});

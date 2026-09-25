import { describe, expect, it } from "vitest";

import {
  asRequest,
  axisTitle,
  memberLegend,
  moveBy,
  pointText,
  rankTrajectories,
  reseededFlags,
  sortByX,
  trajectoryLegend,
  trajectoryNote,
  unrecoveredFlags,
  type LegendEntry,
  type SeriesEntry,
  type SeriesPattern,
  type Trajectory,
} from "./series";

const member = (over: Partial<SeriesPattern> = {}): SeriesPattern => ({
  upload: "tok", filename: "p.xye", label: "p", x: null, reader: "xy",
  reader_options: {}, n_points: 10, two_theta_range: [3, 24], has_sigma: true, ...over,
});

const traj = (over: Partial<Trajectory> = {}): Trajectory => ({
  path: "phases.0.cell.a", x: [300, 400, 500], x_label: "T",
  value: [4.1, 4.2, 4.3], stderr: [1e-4, null, 1e-4],
  labels: ["a", "b", "c"], path_dependent: false, discontinuous: false,
  backward: null, n_sigma: null, ...over,
});


describe("the staged list", () => {
  it("sends the coordinate only when there is one", () => {
    const sent = asRequest([member({ upload: "a", x: 300 }),
                            member({ upload: "b", x: null })]);
    // a missing key is the server's "the index is the axis"; sending `null`
    // would be a coordinate whose value is null, which is a different claim
    expect(sent[0]).toEqual({ upload: "a", label: "p", x: 300 });
    expect(sent[1]).toEqual({ upload: "b", label: "p" });
  });

  it("returns the same array when a member cannot move", () => {
    const list = [member({ upload: "a" }), member({ upload: "b" })];
    // identity, not equality: the caller skips the PUT on it, and a PUT that
    // rewrote the server's list to what it already holds would re-read every
    // file to prove nothing
    expect(moveBy(list, 0, -1)).toBe(list);
    expect(moveBy(list, 1, 1)).toBe(list);
    expect(moveBy(list, 9, -1)).toBe(list);
    expect(moveBy(list, 1, -1).map((m) => m.upload)).toEqual(["b", "a"]);
    expect(moveBy(list, 0, 1).map((m) => m.upload)).toEqual(["b", "a"]);
    expect(list.map((m) => m.upload)).toEqual(["a", "b"]);   // not mutated
  });

  it("sorts by the coordinate and leaves the uncoordinated at the end", () => {
    const list = [member({ upload: "c", x: 500 }), member({ upload: "none" }),
                  member({ upload: "a", x: 300 }), member({ upload: "b", x: 400 })];
    // inventing a coordinate for the member that has none is exactly what `null`
    // refuses, so it keeps its place rather than sorting as 0
    expect(sortByX(list).map((m) => m.upload)).toEqual(["a", "b", "c", "none"]);
  });
});

describe("ranking trajectories", () => {
  it("puts the path-dependent first, then the discontinuous, then by σ", () => {
    const rows = [
      traj({ path: "quiet" }),
      traj({ path: "jump", discontinuous: true }),
      traj({ path: "unstable.small", path_dependent: true, n_sigma: 3.4 }),
      traj({ path: "unstable.big", path_dependent: true, n_sigma: 11.2 }),
    ];
    expect(rankTrajectories(rows).map((t) => t.path)).toEqual([
      "unstable.big", "unstable.small", "jump", "quiet"]);
    // the input is untouched: the panel's select and its plot read the same list
    expect(rows.map((t) => t.path)).toEqual(
      ["quiet", "jump", "unstable.small", "unstable.big"]);
  });

  it("does not rank a null σ as agreement", () => {
    // `n_sigma: null` is where the fence itself abstains (no esd in either
    // chain), so it must not outrank a measured small disagreement *or* be
    // treated as a large one
    const rows = [traj({ path: "unknown", path_dependent: true, n_sigma: null }),
                  traj({ path: "measured", path_dependent: true, n_sigma: 4 })];
    expect(rankTrajectories(rows).map((t) => t.path)).toEqual(
      ["measured", "unknown"]);
  });

  it("leaves the unflagged in the series' own order", () => {
    // Found in a browser: on a clean ramp nothing is flagged and every distance
    // is under 5e-4 σ, so ranking the unflagged ones by σ too ordered fifteen
    // parameters by noise and put the cell edge eighth.
    const rows = [
      traj({ path: "phases.0.cell.a", n_sigma: 4.3e-4 }),
      traj({ path: "phases.0.scale", n_sigma: 0 }),
      traj({ path: "instrument.zero_shift", n_sigma: 3.2e-4 }),
      traj({ path: "qpa.LaB6", n_sigma: null }),
    ];
    expect(rankTrajectories(rows).map((t) => t.path)).toEqual(
      ["phases.0.cell.a", "phases.0.scale", "instrument.zero_shift", "qpa.LaB6"]);
    // …and a flagged one still jumps the queue from wherever it was
    const flagged = [...rows];
    flagged[2] = traj({ path: "instrument.zero_shift", path_dependent: true,
                        n_sigma: 5.2 });
    expect(rankTrajectories(flagged)[0].path).toBe("instrument.zero_shift");
  });
});

describe("what a trajectory says about itself", () => {
  it("names the order-dependence, with the magnitude, when it is flagged", () => {
    const note = trajectoryNote(
      traj({ path_dependent: true, n_sigma: 5.2 }), 3);
    expect(note).toContain("5.2σ");
    expect(note).toContain("over 3σ");
    expect(note).toContain("not\n    determined by the data alone".replace(/\s+/g, " "));
  });

  it("says the chains agree only when both were run", () => {
    expect(trajectoryNote(traj(), 3)).toBe("");
    expect(trajectoryNote(traj({ backward: [1, 2, 3] }), 3))
      .toContain("agree within their esds");
  });

  it("names a discontinuity as two possibilities, never one", () => {
    const note = trajectoryNote(traj({ discontinuous: true }), 3);
    expect(note).toContain("specimen changed");
    expect(note).toContain("chain failed");
  });

  it("titles a QPA trajectory as a weight percentage", () => {
    expect(axisTitle(traj({ path: "qpa.corundum" }))).toBe("corundum (wt %)");
  });

  it("names the residual on an agreement trajectory, keeping the two apart", () => {
    // gui/series.py serves `r_bragg.<phase>`/`r_f.<phase>` rows.  Stripped to
    // the leaf both would read `LaB6` — no unit, a residual disguised as a
    // parameter named after the phase, and identical between the two metrics.
    expect(axisTitle(traj({ path: "r_bragg.LaB6" }))).toBe("LaB6 R_Bragg");
    expect(axisTitle(traj({ path: "r_f.LaB6" }))).toBe("LaB6 R_F");
    expect(axisTitle(traj({ path: "r_bragg.LaB6" })))
      .not.toBe(axisTitle(traj({ path: "r_f.LaB6" })));
  });

  it("titles the y axis with the leaf, because the margin is what clips", () => {
    // Measured in a browser: a *rotated* title shares the fixed left margin with
    // the tick labels, so `phases.0.cell.a` — fifteen characters, under
    // matplotlib's 24-character cut — came out as `aes.0.cell.a`.  The full path
    // is the heading above the plot.
    expect(axisTitle(traj({ path: "phases.0.cell.a" }))).toBe("a");
    expect(axisTitle(traj({ path: "phases.0.atoms.3.adp.2" }))).toBe("2");
    expect(axisTitle(traj({ path: "instrument.background.c11" }))).toBe("c11");
  });
});

describe("the legend", () => {
  const ids = (rows: LegendEntry[]) => rows.map((e) => e.id);

  it("offers a whisker only where some point has an esd to draw", () => {
    // a point with no esd has no whisker at all (`rxplot.trajectory`); a
    // zero-length one would claim it was measured exactly
    expect(ids(trajectoryLegend(traj()))).toEqual(["forward", "esd"]);
    expect(ids(trajectoryLegend(traj({ stderr: [null, null, null] }))))
      .toEqual(["forward"]);
  });

  it("names the flagged trajectory, in the warning ink and dashed", () => {
    const [forward] = trajectoryLegend(traj({ path_dependent: true }));
    expect(forward).toEqual({ id: "forward", label: "forward (path-dependent)",
                              ink: "--warn", mark: "dash" });
    // …and the plain one is not shouting
    const [plain] = trajectoryLegend(traj());
    expect(plain).toEqual({ id: "forward", label: "forward", ink: "--plot-diff",
                            mark: "line" });
  });

  it("offers the backward chain only when there is one", () => {
    expect(ids(trajectoryLegend(traj({ backward: [4.11, 4.21, 4.31] }))))
      .toEqual(["forward", "esd", "backward"]);
  });

  it("rings and crosses are offered where the flags put one", () => {
    // a ring is a good fit reached from a different starting model; a cross is
    // a fit that diverged on every rung, so its value is not a measurement at
    // all (WP-1051) — the same mark for both would collapse the two into "odd"
    const rows = trajectoryLegend(traj(), [false, true, false], [false, false, true]);
    expect(rows.slice(-2).map((e) => [e.id, e.label, e.mark]))
      .toEqual([["rings", "reseeded", "ring"], ["crosses", "unrecovered", "cross"]]);
    expect(ids(trajectoryLegend(traj(), [false, false, false], [false, false, false])))
      .toEqual(["forward", "esd"]);
  });

  it("offers a member's masked points only when the protocol masked any", () => {
    expect(ids(memberLegend(false))).toEqual(["obs", "calc", "bkg", "diff"]);
    expect(ids(memberLegend(true))).toEqual(["obs", "masked", "calc", "bkg", "diff"]);
  });
});

describe("what the pointer says", () => {
  it("names the pattern, its coordinate and the value with its esd", () => {
    expect(pointText(traj(), 0, "forward")).toBe("a · 300: 4.1 ± 0.0001");
    // no esd, no ±: the fit estimated nothing, so nothing is claimed
    expect(pointText(traj(), 1, "forward")).toBe("b · 400: 4.2");
  });

  it("names a backward point as the backward chain's", () => {
    const both = traj({ backward: [4.11, 4.21, 4.31] });
    expect(pointText(both, 2, "backward")).toBe("c · 500: 4.31 (backward)");
  });

  it("gives the value six significant figures and its esd two", () => {
    // six as the hover did under plotly; two as an esd is quoted, where six
    // printed `± 0.0000889554` in a browser
    expect(pointText(traj({ value: [4.123456789, 0, 0],
                            stderr: [0.0000889554, null, null] }), 0, "forward"))
      .toBe("a · 300: 4.12346 ± 0.000089");
  });
});

describe("matching the reseed flags to a trajectory", () => {
  const entries = (over: Array<Partial<SeriesEntry>>): SeriesEntry[] =>
    over.map((o, i) => ({
      index: i, label: `p${i}`, x: null, status: "converged",
      statistics: { rwp: 0.1, gof: 1 }, n_iterations: 1, reseeded: false,
      rwp_warm: null, rung: "warm", rungs_tried: ["warm"], node_id: null,
      tree_id: null, diagnostics: [], ...o,
    }));

  it("matches on the label, because a trajectory skips the patterns it misses", () => {
    // `SeriesResult.trajectory` does not fill gaps: a parameter absent from
    // pattern 0 makes the trajectory start at pattern 1, so index alignment
    // would ring the wrong point
    const rows = entries([{ label: "p0" }, { label: "p1", reseeded: true },
                          { label: "p2" }]);
    const partial = traj({ labels: ["p1", "p2"], x: [400, 500],
                           value: [4.2, 4.3], stderr: [null, null] });
    expect(reseededFlags(partial, rows)).toEqual([true, false]);
    const whole = traj({ labels: ["p0", "p1", "p2"] });
    expect(reseededFlags(whole, rows)).toEqual([false, true, false]);
  });

  it("reads unrecovered off the status, not off a flag of its own", () => {
    // "diverged after the last rung" and "diverged" are the same statement once
    // the chain has run, so a second field could only disagree with this one
    const rows = entries([{}, { status: "diverged", reseeded: false },
                          { status: "max_iter" }]);
    expect(unrecoveredFlags(traj({ labels: ["p0", "p1", "p2"] }), rows))
      .toEqual([false, true, false]);
  });
});

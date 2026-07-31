/**
 * The DAG's geometry and labels, asserted without a DOM.
 *
 * The shapes tested are the ones this history actually grows: a straight run of
 * stages, a fork (running a stage from a node that already has a child — which is
 * the *only* way a branch appears here, since there are no moving refs), and a
 * merge. Lane reuse after a merge is asserted because the alternative is a log
 * that widens forever down a long session.
 */
import { describe, expect, it } from "vitest";

import { diffRows, layout, nodeLabel, rwpDelta, type HistoryNode } from "./history";

function node(id: string, parents: string[], over: Partial<HistoryNode> = {}): HistoryNode {
  return {
    id, parents, children: [], label: "", created_utc: "2026-07-30T00:00:00Z",
    kind: "stage", name: id, action: { kind: "stage", turn_on: [], turn_off: [] },
    api_call: `ref.run_stage(data, pr.Stage('${id}', []))`,
    status: "converged", n_iterations: 4, rwp: null, gof: null, n_free: null,
    n_diagnostics: 0, diagnostics: [], tags: [], scores: {}, notes: {},
    ...over,
  };
}

describe("lane layout", () => {
  it("keeps a linear history in one lane", () => {
    const { placed, edges, lanes } = layout([
      node("n0000", [], { kind: "root" }),
      node("n0001", ["n0000"]),
      node("n0002", ["n0001"]),
    ]);
    expect(placed.map((p) => p.lane)).toEqual([0, 0, 0]);
    expect(placed.map((p) => p.row)).toEqual([0, 1, 2]);
    expect(edges).toHaveLength(2);
    expect(lanes).toBe(1);
  });

  it("opens a lane for the second child of a node — where a fork appears", () => {
    const { placed, lanes } = layout([
      node("n0000", [], { kind: "root" }),
      node("n0001", ["n0000"]),
      node("n0002", ["n0001"]),
      node("n0003", ["n0001"]), // ran a stage from n0001 again: a fork
      node("n0004", ["n0003"]),
    ]);
    expect(placed.map((p) => p.lane)).toEqual([0, 0, 0, 1, 1]);
    expect(lanes).toBe(2);
  });

  it("frees the lane a merge consumed, so a long log does not widen forever", () => {
    const { placed, edges } = layout([
      node("n0000", [], { kind: "root" }),
      node("n0001", ["n0000"]),
      node("n0002", ["n0000"]),
      node("n0003", ["n0001", "n0002"], { kind: "merge" }),
      node("n0004", ["n0003"]),
      node("n0005", ["n0003"]), // a fork after the merge reuses lane 1
    ]);
    expect(placed.map((p) => p.lane)).toEqual([0, 0, 1, 0, 0, 1]);
    const merge = edges.filter((e) => e.to === "n0003");
    expect(merge).toHaveLength(2);
    expect(merge.every((e) => e.merge)).toBe(true);
  });

  it("draws no edge to a parent outside the payload", () => {
    const { edges } = layout([node("n0009", ["n0008"])]);
    expect(edges).toEqual([]);
  });
});

describe("node labels and badges", () => {
  it("says what the action was, not what the node is called", () => {
    expect(nodeLabel(node("n0", [], { kind: "root" }))).toBe("root");
    expect(nodeLabel(node("n1", [], { kind: "stage", name: "cell" }))).toBe("cell");
    expect(nodeLabel(node("n2", [], {
      kind: "set_vary", action: { turn_on: ["a", "b", "c"], turn_off: [] },
    }))).toBe("free 3 paths");
    expect(nodeLabel(node("n3", [], {
      kind: "set_vary", action: { turn_on: [], turn_off: ["a"] },
    }))).toBe("fix 1 path");
    expect(nodeLabel(node("n4", [], {
      kind: "set_value", action: { values: { a: 1, b: 2 } },
    }))).toBe("set 2 values");
    expect(nodeLabel(node("n5", [], { kind: "edit_model", name: "zero guess" })))
      .toBe("zero guess");
  });

  it("compares Rwp against the first parent only", () => {
    const nodes = [
      node("n0", [], { kind: "root" }),
      node("n1", ["n0"], { rwp: 0.2 }),
      node("n2", ["n1"], { rwp: 0.12 }),
      node("n3", ["n2", "n1"], { kind: "merge", rwp: 0.11 }),
    ];
    const by = new Map(nodes.map((n) => [n.id, n]));
    expect(rwpDelta(nodes[1], by)).toBeNull();          // the root has no Rwp
    expect(rwpDelta(nodes[2], by)).toBeCloseTo(-0.08, 12);
    // the merge's second parent is a rival strategy, not a predecessor
    expect(rwpDelta(nodes[3], by)).toBeCloseTo(-0.01, 12);
  });
});

describe("the two-node diff", () => {
  it("ranks by relative move and puts an appearing parameter first", () => {
    const rows = diffRows({
      "phases.0.cell.a": [4.1566, 4.1568],
      "instrument.profile.w": [0.00025, 0.0005],
      "phases.1.scale": [null, 0.001],
    });
    expect(rows.map((r) => r.path)).toEqual([
      "phases.1.scale",          // absent on one side: Infinity, sorts first
      "instrument.profile.w",    // +100 %
      "phases.0.cell.a",         // +5e-5
    ]);
    expect(rows[0].delta).toBeNull();
    expect(rows[1].delta).toBeCloseTo(0.00025, 12);
  });

  it("reads a non-finite value that crossed the wire as a string", () => {
    const [row] = diffRows({ "instrument.profile.y": ["-Infinity", 0] });
    expect(row.a).toBe(-Infinity);
    expect(row.delta).toBe(Infinity);
  });

  it("filters by path substring", () => {
    const diff = { "phases.0.cell.a": [1, 2], "instrument.zero_shift": [0, 0.01] };
    expect(diffRows(diff, "cell").map((r) => r.path)).toEqual(["phases.0.cell.a"]);
    expect(diffRows(diff, "nothing")).toEqual([]);
  });
});

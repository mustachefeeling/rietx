/**
 * The DAG's geometry and labels, asserted without a DOM.
 *
 * The shapes tested are the ones this history actually grows: a straight run of
 * stages, a fork (running a stage from a node that already has a child — which is
 * the *only* way a branch appears here, since there are no moving refs), and a
 * merge. Lane reuse after a merge is asserted because the alternative is a log
 * that widens forever down a long session.
 */
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

import {
  DIFF_CAP, LANE_HUES, PATH_CHARS, PERCENT_CHARS, PLACES, VALUE_CHARS, diffRows,
  edgeSegments, formatDelta, formatFor, formatPercent, formatSide, laneColor,
  layout, nodeLabel, rwpDelta, type Edge, type HistoryNode,
} from "./history";

function node(id: string, parents: string[], over: Partial<HistoryNode> = {}): HistoryNode {
  return {
    id, parents, children: [], label: "", created_utc: "2026-07-30T00:00:00Z",
    kind: "stage", name: id, action: { kind: "stage", turn_on: [], turn_off: [] },
    api_call: `ref.run_stage(data, rx.Stage('${id}', []))`,
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
    // only the *second* parent is dashed: the first is the lineage, and dashing
    // both put three dashed rows in the middle of the trunk (WP-1217, seen in a
    // browser once the runs stopped being curves)
    expect(merge.map((e) => [e.from, e.merge]))
      .toEqual([["n0001", false], ["n0002", true]]);
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

/** A straight run of `n` stages under a root, plus whatever forks are asked for. */
function chain(n: number, forks: Array<[string, string]> = []): HistoryNode[] {
  const nodes = [node("n0000", [], { kind: "root" })];
  for (let i = 1; i <= n; i += 1) {
    nodes.push(node(`n${String(i).padStart(4, "0")}`,
                    [`n${String(i - 1).padStart(4, "0")}`]));
  }
  for (const [id, parent] of forks) nodes.push(node(id, [parent]));
  return nodes;
}

describe("edge segments", () => {
  it("never leans over more than one row, whatever the gap", () => {
    // the user's report: "if nodes are very far away, the shallow line is ugly
    // and hard to read".  The old `edgePath` drew one Bézier over the whole
    // vertical gap, so a fork from n0001 landing ten rows down was a diagonal
    // across ten rows.
    const { edges, placed } = layout(chain(10, [["n0011", "n0001"]]));
    const fork = edges.find((e) => e.to === "n0011") as Edge;
    expect(fork.toRow - fork.fromRow).toBe(10);
    for (const edge of edges) {
      for (const part of edgeSegments(edge)) {
        const diagonal = part.fromLane !== part.toLane;
        expect(diagonal ? Math.abs(part.toRow - part.fromRow) : 1).toBe(1);
      }
    }
    // every edge's `toLane` was a `-1` placeholder until the child was placed,
    // and a lane of −1 is drawn off the rail rather than raising
    const laneOf = new Map(placed.map((p) => [p.node.id, p.lane]));
    for (const edge of edges) expect(edge.toLane).toBe(laneOf.get(edge.to));
    // and the pieces still join the two nodes end to end
    const parts = edgeSegments(fork);
    expect([parts[0].fromLane, parts[0].fromRow]).toEqual([fork.fromLane, fork.fromRow]);
    const last = parts[parts.length - 1];
    expect([last.toLane, last.toRow]).toEqual([fork.toLane, fork.toRow]);
    expect(placed[11].lane).toBe(1);
  });

  it("crosses below the parent for a fork and above the child for a merge", () => {
    // which end it steps at is the lane algorithm's answer, not a second rule:
    // an edge leaves the lane that goes on without it
    const forked = layout(chain(3, [["n0004", "n0001"]]));
    const fork = forked.edges.find((e) => e.to === "n0004") as Edge;
    expect(edgeSegments(fork)).toEqual([
      { fromLane: 0, fromRow: 1, toLane: 1, toRow: 2 },   // step out at once
      { fromLane: 1, fromRow: 2, toLane: 1, toRow: 4 },   // then straight down
    ]);

    const merged = layout([
      node("n0000", [], { kind: "root" }),
      node("n0001", ["n0000"]),
      node("n0002", ["n0000"]),
      node("n0003", ["n0001"]),
      node("n0004", ["n0003", "n0002"], { kind: "merge" }),
    ]);
    const merge = merged.edges.find((e) => e.from === "n0002") as Edge;
    expect(edgeSegments(merge)).toEqual([
      { fromLane: 1, fromRow: 2, toLane: 1, toRow: 3 },   // down its own lane
      { fromLane: 1, fromRow: 3, toLane: 0, toRow: 4 },   // and in at the last row
    ]);
  });

  it("leaves an arc's lane alone until it arrives, so no line crosses a dot", () => {
    // the reservation is what makes the one-row crossing drawable at all: a
    // tip-following pass frees a lane the moment its node is drawn, and a fork
    // ten rows later could be handed the lane an edge was still travelling down.
    const { placed, edges } = layout(chain(10, [["n0011", "n0001"], ["n0012", "n0002"]]));
    const dots = new Set(placed.map((p) => `${p.lane}:${p.row}`));
    const ends = new Map(placed.map((p) => [p.node.id, p]));
    for (const edge of edges) {
      for (const part of edgeSegments(edge)) {
        if (part.fromLane !== part.toLane) continue;
        for (let row = part.fromRow; row <= part.toRow; row += 1) {
          const own = ends.get(edge.from)?.row === row || ends.get(edge.to)?.row === row;
          expect(own || !dots.has(`${part.fromLane}:${row}`))
            .toBe(true);
        }
      }
    }
  });
});

describe("lane colours", () => {
  it("rotates hue and repeats rather than crowding the wheel", () => {
    // five, 72° apart: at `--lane-c` a sixth would land inside the phase
    // palette's 0.13 floor (`tests/test_gui_palette.py` does that arithmetic)
    expect(LANE_HUES).toHaveLength(5);
    for (let i = 1; i < LANE_HUES.length; i += 1) {
      expect((LANE_HUES[i] - LANE_HUES[i - 1] + 360) % 360).toBe(72);
    }
    expect(laneColor(0)).toBe("oklch(var(--lane-l) var(--lane-c) 250)");
    expect(laneColor(5)).toBe(laneColor(0));
    expect(laneColor(-1)).toBe(laneColor(4));
  });
});

const CORPUS = JSON.parse(
  readFileSync(fileURLToPath(new URL("../../../tests/data/gui/help_keys.json",
                                    import.meta.url)), "utf-8"),
) as { keys: string[] };

/** A concrete path of the family `glob` names — every `*` filled in. */
function sample(glob: string): string {
  return glob.replace(/\.\*\./g, ".0.").replace(/\*$/, "0");
}

describe("the compare table's numbers", () => {
  it("declares a format for every parameter family and no others", () => {
    // the fnmatch/help mechanism: python owns the vocabulary, TypeScript proves
    // it can state it.  A new family fails here until it is given a format, and
    // a renamed one cannot leave an entry behind describing a name that is gone.
    const families = CORPUS.keys
      .filter((key) => key.startsWith("parameters:"))
      .map((key) => key.slice("parameters:".length));
    expect(Object.keys(PLACES).sort()).toEqual([...families].sort());
  });

  it("lands a real path on its own family", () => {
    for (const glob of Object.keys(PLACES)) {
      expect(formatFor(sample(glob)), glob).toBe(PLACES[glob]);
    }
    expect(formatFor("pawley.0.intensity")).toBe("exp");   // outside the vocabulary
  });

  it("keeps the column's width whatever the magnitude", () => {
    // the width is the promise `--w-val` hands to the CSS, so the formatter has
    // to keep it: a background term of 1e5 at three places is thirteen
    // characters, and the answer is exponential rather than a pushed column
    const spread = [0, 1e-9, 1.5e-4, 0.5, 4.15678, 999.999, 1.2345e5, 6.7e12];
    for (const glob of Object.keys(PLACES)) {
      const path = sample(glob);
      for (const magnitude of spread) {
        for (const value of [magnitude, -magnitude]) {
          expect(formatSide(path, value).length, `${path} ${value}`)
            .toBeLessThanOrEqual(VALUE_CHARS);
          expect(formatDelta(path, value).length, `${path} Δ${value}`)
            .toBeLessThanOrEqual(VALUE_CHARS);
          expect(formatPercent(4.1566, value).length, `${path} %${value}`)
            .toBeLessThanOrEqual(PERCENT_CHARS);
        }
      }
    }
  });

  it("writes a family at one width, so its decimal points line up", () => {
    expect(formatSide("phases.0.cell.a", 4.1566)).toBe("4.15660");
    expect(formatSide("phases.0.cell.a", 4.1568)).toBe("4.15680");
    expect(formatSide("phases.0.atoms.0.biso", 0.5)).toBe("0.500");
    expect(formatSide("phases.0.scale", 0.000123456)).toBe("1.2346e-4");
    expect(formatSide("phases.0.cell.a", null)).toBe("—");
    expect(formatSide("instrument.profile.w", -Infinity)).toBe("-Infinity");
  });

  it("signs the difference and says nothing where there is none to say", () => {
    expect(formatDelta("phases.0.cell.a", 0.0002)).toBe("+0.00020");
    expect(formatDelta("phases.0.cell.a", -0.0002)).toBe("-0.00020");
    expect(formatDelta("phases.0.cell.a", null)).toBe("new");
  });

  it("gives the percentage enough figures to show a refinement", () => {
    // 12 ppm on a cell length is a real result and `0.00%` is not a way to
    // say it — three significant figures, exponential outside [1e-3, 1e3)
    expect(formatPercent(4.1566, 0.0002)).toBe("+0.00481%");
    expect(formatPercent(0.00025, 0.00025)).toBe("+100%");
    expect(formatPercent(4.1566, -0.0002)).toBe("-0.00481%");
    expect(formatPercent(1, 1e-9)).toBe("+1.00e-7%");
    // of |a|, so the two marks cannot disagree about which way it went
    expect(formatPercent(-0.0002, 0.0026)).toBe("+1.30e+3%");
    expect(formatPercent(0, 0.5)).toBe("—");        // every move is infinite
    expect(formatPercent(4.1566, null)).toBe("—");  // a parameter that appeared
    expect(formatPercent(null, 0.5)).toBe("—");
  });

  it("hands the panel its widths rather than letting it write them", () => {
    // WP-1215's rule and WP-1216's arithmetic, at this table's scale: the
    // number is stated in `lib/history.ts` and the CSS reads it, so the two
    // cannot go stale against each other
    const svelte = readFileSync(
      fileURLToPath(new URL("../panels/History.svelte", import.meta.url)), "utf-8");
    expect(svelte).toContain('style:--w-val="{VALUE_CHARS}ch"');
    expect(svelte).toContain('style:--w-pct="{PERCENT_CHARS}ch"');
    expect(svelte).toContain('style:--w-path="{PATH_CHARS}ch"');
    expect(svelte).toContain("rows.slice(0, DIFF_CAP)");
    expect(DIFF_CAP).toBe(200);
    expect(PATH_CHARS).toBeGreaterThan(0);
  });
});

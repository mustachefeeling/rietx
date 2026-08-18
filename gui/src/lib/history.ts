/** The history DAG's geometry and labels, as pure functions.
 *
 * The panel is a *view* over `GET /api/history` — no new history semantics, and
 * no graph library: this DAG is thirty nodes of one project, so lane assignment
 * is a dozen lines and drawing it is two SVG paths per edge.  Separated from the
 * component for the reason the parameter table's logic is: "which lane does this
 * node sit in" and "what does this node's badge say" are questions with answers
 * that can be asserted without a DOM.
 *
 * Two facts from the server shape everything here.  The node list arrives in
 * `tree.order`, which is **insertion order and therefore topological** — ids are
 * sequential and a parent is always appended before its children — so lanes can
 * be assigned in one forward pass with no sorting.  And a node carries no state:
 * `rwp`/`gof`/`n_free` are its cached metrics and a parameter value is not in the
 * payload at all, which is why the compare view asks `/api/history/diff` instead
 * of subtracting two node states the client does not have.
 */

import { num } from "./table";

export interface HistoryNode {
  id: string;
  parents: string[];
  children: string[];
  label: string;
  created_utc: string;
  kind: string;
  name: string;
  action: Record<string, any>;
  api_call: string;
  status: string | null;
  n_iterations: number | null;
  rwp: number | null;
  gof: number | null;
  n_free: number | null;
  n_diagnostics: number;
  diagnostics: Array<{ level: string; code: string; message: string; where: string[] }>;
  tags: string[];
  scores: Record<string, number>;
  notes: Record<string, string>;
}

export interface Placed {
  node: HistoryNode;
  /** index into the node list, top to bottom */
  row: number;
  /** which vertical rail the node's dot sits on */
  lane: number;
}

export interface Edge {
  from: string;
  to: string;
  fromRow: number;
  toRow: number;
  fromLane: number;
  toLane: number;
  /** true when `to` has more than one parent — a merge, drawn dashed */
  merge: boolean;
}

/**
 * Assign every node a row and a lane, git-graph style.
 *
 * A lane is a branch being continued: a node takes the lane of whichever parent
 * still holds a tip, and a node whose parent's lane was already claimed by an
 * earlier child starts a new one — which is exactly where a fork appears in this
 * DAG.  There are no moving refs here (only `head` and tags, WP-1008), so a lane
 * is a *drawn* thing rather than a named one; `laneOf` never invents a branch
 * that does not exist, it only shows where the tree divided.
 *
 * A merge clears the lanes of its other parents, so lanes are reused rather than
 * growing without bound down a long log.
 */
export function layout(nodes: readonly HistoryNode[]) {
  const tips: Array<string | null> = [];
  const placed: Placed[] = [];

  nodes.forEach((node, row) => {
    let lane = tips.findIndex((tip) => tip !== null && node.parents.includes(tip));
    if (lane === -1) {
      lane = tips.findIndex((tip) => tip === null);
      if (lane === -1) lane = tips.length;
    }
    tips[lane] = node.id;
    for (let i = 0; i < tips.length; i++) {
      const tip = tips[i];
      if (i !== lane && tip !== null && node.parents.includes(tip)) tips[i] = null;
    }
    placed.push({ node, row, lane });
  });

  const at = new Map(placed.map((p) => [p.node.id, p]));
  const edges: Edge[] = [];
  for (const p of placed) {
    for (const parent of p.node.parents) {
      const from = at.get(parent);
      if (!from) continue; // a parent outside this payload: draw nothing, invent nothing
      edges.push({
        from: parent, to: p.node.id,
        fromRow: from.row, toRow: p.row,
        fromLane: from.lane, toLane: p.lane,
        merge: p.node.parents.length > 1,
      });
    }
  }
  return { placed, edges, lanes: Math.max(1, tips.length) };
}

/** What a node's row says it is — the action, not the id.
 *
 * `set_vary` prints how many paths it moved rather than the paths themselves: a
 * bulk free is one node carrying a glob's worth of hits (WP-1011), and the glob
 * is on the node's `api_call` for anyone who wants it. */
export function nodeLabel(node: HistoryNode): string {
  const action = node.action ?? {};
  const on = (action.turn_on ?? []).length;
  const off = (action.turn_off ?? []).length;
  switch (node.kind) {
    case "root":
      return "root";
    case "stage":
      return node.name || "stage";
    case "set_vary":
      return on ? `free ${on} path${on === 1 ? "" : "s"}`
                : `fix ${off} path${off === 1 ? "" : "s"}`;
    case "set_value": {
      const n = Object.keys(action.values ?? {}).length;
      return `set ${n} value${n === 1 ? "" : "s"}`;
    }
    case "edit_model":
      return node.name || node.label || "model edited";
    default:
      return node.kind;
  }
}

/**
 * Rwp change against the node's first parent, or `null` when either lacks one.
 *
 * Against the *first* parent because that is the lineage `Refinement.lineage`
 * follows, and because a merge's second parent is a rival strategy rather than a
 * predecessor — reading "improved by 0.03" against a branch nobody was on would
 * be a comparison of two different things.
 *
 * A node's metrics are **as-optimised**: measured on the model the stage *started*
 * from (CLAUDE.md), so a small disagreement with a replay is a staleness signal
 * and not a regression — which is why this returns the difference and nothing
 * about whether it is significant.
 */
export function rwpDelta(node: HistoryNode,
                         by: Map<string, HistoryNode>): number | null {
  if (node.rwp === null || node.rwp === undefined) return null;
  const parent = by.get(node.parents[0] ?? "");
  if (!parent || parent.rwp === null || parent.rwp === undefined) return null;
  return num(node.rwp) - num(parent.rwp);
}

export interface DiffRow {
  path: string;
  a: number | null;
  b: number | null;
  delta: number | null;
  /** |Δ| relative to the larger magnitude — what the rows are ranked by */
  relative: number;
}

/**
 * `GET /api/history/diff`'s payload as ranked rows.
 *
 * The route returns **only** the paths that differ (`RefinementTree.diff` at
 * rtol 1e-12), so there is no changed-only filter to offer here — every row is a
 * change, and the panel says so rather than showing a toggle that does nothing.
 * A path present in one node and absent in the other (a phase added, an ADP block
 * declared) comes back with a `null` on that side and sorts to the top, because
 * a parameter appearing is a bigger event than one moving.
 */
export function diffRows(diff: Record<string, Array<number | string | null>>,
                         query = ""): DiffRow[] {
  const want = query.trim().toLowerCase();
  const rows: DiffRow[] = [];
  for (const [path, pair] of Object.entries(diff ?? {})) {
    if (want && !path.toLowerCase().includes(want)) continue;
    const a = pair?.[0] == null ? null : num(pair[0]);
    const b = pair?.[1] == null ? null : num(pair[1]);
    const delta = a === null || b === null ? null : b - a;
    const scale = Math.max(Math.abs(a ?? 0), Math.abs(b ?? 0), 1e-30);
    rows.push({
      path, a, b, delta,
      relative: delta === null ? Infinity : Math.abs(delta) / scale,
    });
  }
  return rows.sort((x, y) => y.relative - x.relative || x.path.localeCompare(y.path));
}

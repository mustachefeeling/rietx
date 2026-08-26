/** The parameter table's logic, as pure functions — grouping, filtering,
 * pending edits and the virtual window.
 *
 * Separated from the component for the reason the session is separated from the
 * server: a Pawley fit puts thousands of rows through this, and "which rows does
 * this glob select" and "which slice is on screen" are questions with answers
 * that can be asserted without a DOM.  `table.test.ts` is that assertion.
 *
 * Two rules here are the API's, not this table's.  A glob is the unit of a bulk
 * free/fix because `Refinement.set_vary` takes one and records **one** history
 * node for it; a value edit is batched into a dict because `set_values` takes
 * one and does the same (WP-1004).  So the filter box is the selection — there
 * is no second selection model, because a per-row multi-select would have to be
 * sent as N globs and would bury the history log under N nodes.
 */

export interface TieSpec {
  sources: string[];
  coefficients?: number[];
  offset?: number;
}

/** One row of `GET /api/params` — `ParameterRow` plus the two properties the
 * session adds back after `model_dump` drops them (they are the whole point). */
export interface ParamRow {
  path: string;
  value: number;
  vary: boolean;
  lo: number;
  hi: number;
  transform: string;
  tie: TieSpec | null;
  locked: boolean;
  esd: number | null;
  mode_fixed: boolean;
  refinable: boolean;
  held_because: string;
  /** the corpus family glob this path belongs to (WP-1202), or null when no
   *  family claims it.  Matched server-side by `help_key_for`, so a client
   *  never re-derives it — the row holds the key rather than the entry because
   *  an entry describes a family and inlining one repeats a paragraph per
   *  atom. */
  help_key: string | null;
}

import { fnmatch } from "./fnmatch";

/**
 * Read a numeric field that may have crossed the wire as `"Infinity"`.
 *
 * Nearly every row has an infinite bound, and JSON has no way to spell one — so
 * this package spells it as a string (`ser_json_inf_nan="strings"`, the schemas'
 * rule since v0.2) and the GUI server follows suit, because the alternative,
 * Python's bare `Infinity` token, is not JSON at all and `JSON.parse` refuses
 * the whole response.  `Number("Infinity")` is the inverse, and `Number(null)`
 * is 0, so a genuine null is kept as `null` rather than silently becoming zero.
 */
export function num(value: unknown): number {
  if (typeof value === "number") return value;
  if (typeof value === "string") return Number(value);
  return NaN;
}

/** A `/api/params` payload's rows, with their numeric fields made numeric. */
export function normalize(rows: readonly any[]): ParamRow[] {
  return rows.map((row) => ({
    ...row,
    value: num(row.value),
    lo: num(row.lo),
    hi: num(row.hi),
    esd: row.esd == null ? null : num(row.esd),
  }));
}

/** Which of the three reasons holds this row, as a class name — or "" if free.
 *
 * Read off the row's own flags in `ParameterRow.held_because`'s order, and kept
 * as three states rather than "greyed": `mode_fixed` comes back when the mode
 * changes, and a Le Bail phase's mandatory dummy atom is exactly the row a user
 * must not read as structurally fixed (WP-1004). */
export function heldKind(row: ParamRow): "" | "locked" | "tied" | "mode" {
  if (row.locked) return "locked";
  if (row.tie) return "tied";
  if (row.mode_fixed) return "mode";
  return "";
}

/**
 * The group a path belongs to: the path minus its leaf, and minus one more when
 * the leaf is a bare index.
 *
 * That second clause is what puts an atom's coordinate DOFs, its `biso` and its
 * ADP components under one heading — `phases.0.atoms.3.dof.1` and
 * `phases.0.atoms.3.biso` both group as `phases.0.atoms.3` — rather than
 * scattering one atom across three headings named `dof`, `adp` and the atom.
 */
export function groupOf(path: string): string {
  const parts = path.split(".");
  if (parts.length < 2) return path;
  const leaf = parts[parts.length - 1];
  const drop = /^\d+$/.test(leaf) && parts.length > 2 ? 2 : 1;
  return parts.slice(0, parts.length - drop).join(".");
}

/**
 * The glob a filter box's text means.
 *
 * A query carrying a glob metacharacter is used verbatim; anything else is
 * wrapped as a substring search.  One function rather than two code paths
 * because the *same* string is both the preview predicate and what `PATCH
 * /api/params` sends — a filter that previewed with `includes()` and applied
 * with fnmatch would select two different sets.
 */
export function asGlob(query: string): string {
  const text = query.trim();
  if (!text) return "*";
  return /[*?[]/.test(text) ? text : `*${text}*`;
}

export function matches(rows: readonly ParamRow[], glob: string): ParamRow[] {
  return glob === "*" ? [...rows] : rows.filter((row) => fnmatch(row.path, glob));
}

/** What a bulk free/fix would do, for the count beside the button.
 *
 * `freeable` excludes locked and tied rows because `set_vary` never matches
 * them however broad the glob — showing "free 214" and having 41 move is how a
 * preview loses its meaning. `mode_fixed` rows *are* counted: they can be freed
 * and are dropped again when a stage runs, which is a different fact. */
export function selection(rows: readonly ParamRow[], glob: string) {
  const hit = matches(rows, glob);
  const freeable = hit.filter((row) => !row.locked && !row.tie);
  return {
    glob,
    matched: hit.length,
    freeable: freeable.length,
    toFree: freeable.filter((row) => !row.vary).length,
    toFix: freeable.filter((row) => row.vary).length,
  };
}

export type Item =
  | { kind: "group"; key: string; label: string; n: number; free: number }
  | { kind: "row"; key: string; row: ParamRow };

export interface FlattenOptions {
  /** the filter glob (`asGlob` of the box's text) */
  glob?: string;
  /** group keys the user collapsed */
  collapsed?: ReadonlySet<string>;
  /** Simple mode: hide rows nothing can free, and say how many were hidden */
  simple?: boolean;
}

/** Rows → the flat list a virtual scroller indexes, headers included.
 *
 * Group order and row order are the server's, which is the θ-vector order — the
 * order a stage plan frees things in, and the order the text document prints.
 * Sorting alphabetically here would make three views of one table disagree. */
export function flatten(rows: readonly ParamRow[], options: FlattenOptions = {}) {
  const { glob = "*", collapsed = new Set<string>(), simple = false } = options;
  const visible = matches(rows, glob);
  const held = simple ? visible.filter((row) => !row.refinable).length : 0;
  const kept = simple ? visible.filter((row) => row.refinable) : visible;

  const order: string[] = [];
  const byGroup = new Map<string, ParamRow[]>();
  for (const row of kept) {
    const key = groupOf(row.path);
    let bucket = byGroup.get(key);
    if (bucket === undefined) {
      bucket = [];
      byGroup.set(key, bucket);
      order.push(key);
    }
    bucket.push(row);
  }

  const items: Item[] = [];
  for (const key of order) {
    const bucket = byGroup.get(key)!;
    items.push({
      kind: "group",
      key,
      label: key,
      n: bucket.length,
      free: bucket.filter((row) => row.vary).length,
    });
    if (collapsed.has(key)) continue;
    for (const row of bucket) items.push({ kind: "row", key: row.path, row });
  }
  return { items, groups: order, shown: kept.length, hidden: held };
}

/** The slice of a fixed-height list that a viewport shows, plus its padding.
 *
 * Fixed row height on purpose: measuring rows would mean rendering them, which
 * is the cost virtualization exists to avoid. `overscan` rows above and below
 * keep a fast scroll from showing blank bands. */
export function windowSlice(
  count: number,
  scrollTop: number,
  viewport: number,
  rowHeight: number,
  overscan = 6,
) {
  const first = Math.max(0, Math.floor(scrollTop / rowHeight) - overscan);
  const visible = Math.ceil(viewport / rowHeight) + 2 * overscan;
  const end = Math.min(count, first + visible);
  const start = Math.min(first, Math.max(0, end - visible));
  return {
    start,
    end,
    padTop: start * rowHeight,
    padBottom: Math.max(0, (count - end) * rowHeight),
  };
}

/**
 * Why this typed value cannot be sent, or `""` if it can.
 *
 * Checked here because the row carries its own bounds and `set_values` refuses
 * an out-of-bounds value (WP-1004) — a round trip to be told what the row
 * already said is a slow way to render a red border.  The *refusals that only
 * the server can make* (a tied path, a locked one) are not duplicated: those
 * rows have no editable cell at all.
 */
export function validateEdit(row: ParamRow, text: string): string {
  const value = Number(text);
  if (text.trim() === "" || !Number.isFinite(value)) return "not a number";
  if (value < row.lo) return `below the lower bound ${row.lo}`;
  if (value > row.hi) return `above the upper bound ${row.hi}`;
  return "";
}

export interface EditState {
  /** the `{path: value}` body of one `set_values` call */
  values: Record<string, number>;
  /** paths whose typed text cannot be sent, with the reason */
  invalid: Array<{ path: string; why: string }>;
  /** how many cells the user has touched — invalid ones included, so the
   *  Revert affordance exists for the edit that most needs it */
  touched: number;
}

/**
 * What the grid's pending edits amount to.
 *
 * A cell counts as changed when its text differs from the **rendered** value,
 * not from the stored float — WP-1009's rule for the text document, and for the
 * same reason: values are displayed at the precision their esd justifies, so
 * comparing against the full float would turn "the user clicked into a cell and
 * clicked out again" into a `set_values` that quietly truncates the parameter.
 */
export function editState(
  rows: readonly ParamRow[],
  edits: ReadonlyMap<string, string>,
  varyCount = 0,
): EditState {
  const byPath = new Map(rows.map((row) => [row.path, row]));
  const values: Record<string, number> = {};
  const invalid: Array<{ path: string; why: string }> = [];
  let touched = varyCount;
  for (const [path, text] of edits) {
    const row = byPath.get(path);
    if (!row) continue;
    const why = validateEdit(row, text);
    if (why) {
      invalid.push({ path, why });
      touched += 1;
    } else if (text.trim() !== formatValue(row.value, row.esd)) {
      values[path] = Number(text);
      touched += 1;
    }
  }
  return { values, invalid, touched };
}

/** A value with its esd, at the precision the esd justifies.
 *
 * One significant figure on the esd sets the value's last place — the
 * crystallographic convention, and the reason a table showing `4.156780000` for
 * a parameter known to ±0.0002 is worse than useless. Without an esd the value
 * is shown at 6 significant figures, which is a display choice and says nothing. */
export function formatValue(value: number, esd: number | null | undefined): string {
  if (!Number.isFinite(value)) return String(value);
  if (esd == null || !Number.isFinite(esd) || esd <= 0) {
    return String(Number(value.toPrecision(6)));
  }
  const places = Math.max(0, Math.min(12, -Math.floor(Math.log10(esd))));
  return value.toFixed(places);
}

/**
 * The part of a dot-path a group heading has not already shown.
 *
 * The last segment alone is enough for `…cell.a` and useless for
 * `phases.0.atoms.0.adp.0`, which renders as **`0`** — measured in a browser on
 * NAC, where the parameter table listed five rows called `0`, `1`, `2`, `3` and
 * `occ` under one heading (WP-1029). A purely numeric leaf is an index into
 * something, so it keeps the thing it indexes.
 */
export function leafName(path: string, group = ""): string {
  const rest = group && path.startsWith(`${group}.`) ? path.slice(group.length + 1) : path;
  const parts = rest.split(".");
  const last = parts[parts.length - 1];
  if (parts.length > 1 && /^\d+$/.test(last)) return parts.slice(-2).join(".");
  return last;
}

/** `4.15678(19)` — the esd in units of the value's last decimal place. */
export function formatEsd(value: number, esd: number | null | undefined): string {
  if (esd == null || !Number.isFinite(esd) || esd <= 0) return "";
  const places = Math.max(0, Math.min(12, -Math.floor(Math.log10(esd))));
  const digits = Math.round(esd * 10 ** places);
  return `(${digits})`;
}

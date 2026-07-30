/**
 * The parameter table's logic, asserted without a DOM.
 *
 * Rows are built from the *same* committed vocabulary the glob fixture uses, so
 * the grouping rule is exercised against the path shapes the package actually
 * produces — an ADP component, a Stephens DOF, a second emission line's weight —
 * rather than against three paths someone invented while writing the rule.
 */
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

import {
  asGlob,
  flatten,
  formatEsd,
  formatValue,
  groupOf,
  heldKind,
  pendingValues,
  selection,
  validateEdit,
  windowSlice,
  type ParamRow,
} from "./table";

const PATHS: string[] = JSON.parse(
  readFileSync(
    fileURLToPath(new URL("../../../tests/data/gui/fnmatch_cases.json", import.meta.url)),
    "utf-8",
  ),
).paths;

function row(path: string, over: Partial<ParamRow> = {}): ParamRow {
  const base: ParamRow = {
    path,
    value: 1,
    vary: false,
    lo: -Infinity,
    hi: Infinity,
    transform: "identity",
    tie: null,
    locked: false,
    esd: null,
    mode_fixed: false,
    refinable: true,
    held_because: "",
    ...over,
  };
  base.refinable = !base.locked && base.tie === null && !base.mode_fixed;
  return base;
}

const ROWS = PATHS.map((path) => row(path));

describe("grouping", () => {
  it("drops the leaf, and one more when the leaf is a bare index", () => {
    expect(groupOf("phases.0.cell.a")).toBe("phases.0.cell");
    expect(groupOf("instrument.profile.w")).toBe("instrument.profile");
    expect(groupOf("phases.0.scale")).toBe("phases.0");
    // one atom, one heading — its DOFs, its ADP components and its biso together
    expect(groupOf("phases.0.atoms.3.dof.1")).toBe("phases.0.atoms.3");
    expect(groupOf("phases.0.atoms.3.adp.0")).toBe("phases.0.atoms.3");
    expect(groupOf("phases.0.atoms.3.biso")).toBe("phases.0.atoms.3");
    expect(groupOf("phases.0.microstrain.dof.2")).toBe("phases.0.microstrain");
    expect(groupOf("instrument.source.lines.1.weight")).toBe("instrument.source.lines.1");
  });

  it("keeps the server's order, which is the θ-vector order", () => {
    const { items, groups } = flatten(ROWS);
    // groups appear where their first row does, and rows never move: three
    // views of one table (this, the text document, a stage plan) would
    // otherwise disagree about the order things are freed in
    const firstAppearance: string[] = [];
    for (const path of PATHS) {
      const key = groupOf(path);
      if (!firstAppearance.includes(key)) firstAppearance.push(key);
    }
    expect(groups).toEqual(firstAppearance);
    expect(groups[0]).toBe("phases.0.cell");
    // grouping is the *only* reordering: rows are gathered under the heading
    // that appeared first and are otherwise in the order the server sent them
    const expected = [...PATHS].sort((a, b) =>
      firstAppearance.indexOf(groupOf(a)) - firstAppearance.indexOf(groupOf(b)));
    const paths = items.filter((i) => i.kind === "row").map((i) => i.key);
    expect(paths).toEqual(expected);
  });

  it("collapses a group to its header without losing the count", () => {
    const full = flatten(ROWS);
    const collapsed = flatten(ROWS, { collapsed: new Set(["phases.0.cell"]) });
    const header = collapsed.items.find((i) => i.kind === "group" && i.key === "phases.0.cell");
    expect(header).toMatchObject({ n: 6, free: 0 });
    expect(collapsed.items.length).toBe(full.items.length - 6);
  });

  it("counts free rows per group, so a header says what is refining", () => {
    const rows = ROWS.map((r) => (r.path.startsWith("phases.0.cell") ? { ...r, vary: true } : r));
    const header = flatten(rows).items.find((i) => i.kind === "group" && i.key === "phases.0.cell");
    expect(header).toMatchObject({ n: 6, free: 6 });
  });
});

describe("the filter is the selection", () => {
  it("wraps a bare word and passes a glob through untouched", () => {
    expect(asGlob("cell")).toBe("*cell*");
    expect(asGlob("  ")).toBe("*");
    expect(asGlob("phases.*.cell.*")).toBe("phases.*.cell.*");
    expect(asGlob("instrument.background.c?")).toBe("instrument.background.c?");
  });

  it("previews with the very string the PATCH will send", () => {
    // the point of asGlob: preview and apply cannot select different sets
    const glob = asGlob("cell");
    const { shown } = flatten(ROWS, { glob });
    expect(shown).toBe(selection(ROWS, glob).matched);
    expect(shown).toBe(6);
  });

  it("excludes locked and tied rows from a free/fix count", () => {
    const rows = [
      row("phases.0.cell.a", { vary: true }),
      row("phases.0.cell.b", { tie: { sources: ["phases.0.cell.a"] } }),
      row("phases.0.cell.alpha", { locked: true }),
      row("phases.0.cell.c", { tie: { sources: ["phases.0.cell.a"] } }),
    ];
    // set_vary never matches a locked or tied entry however broad the glob, so
    // a preview that counted them would promise four and deliver one
    expect(selection(rows, "phases.*.cell.*")).toMatchObject({
      matched: 4,
      freeable: 1,
      toFree: 0,
      toFix: 1,
    });
  });

  it("counts a mode-fixed row as freeable, because set_vary does free it", () => {
    const rows = [row("phases.0.atoms.0.biso", { mode_fixed: true })];
    expect(selection(rows, "*biso*")).toMatchObject({ freeable: 1, toFree: 1 });
  });
});

describe("the three held states", () => {
  it("names each one separately — mode_fixed is not locked", () => {
    expect(heldKind(row("a", { locked: true }))).toBe("locked");
    expect(heldKind(row("a", { tie: { sources: ["b"] } }))).toBe("tied");
    expect(heldKind(row("a", { mode_fixed: true }))).toBe("mode");
    expect(heldKind(row("a"))).toBe("");
  });

  it("hides them in Simple mode and reports how many", () => {
    const rows = [
      row("phases.0.cell.a"),
      row("phases.0.cell.b", { tie: { sources: ["phases.0.cell.a"] } }),
      row("phases.0.cell.alpha", { locked: true }),
    ];
    const simple = flatten(rows, { simple: true });
    expect(simple.shown).toBe(1);
    expect(simple.hidden).toBe(2);   // a count, not a silent truncation
    expect(flatten(rows).hidden).toBe(0);
  });
});

describe("the virtual window", () => {
  it("covers the viewport and pads to the full scroll height", () => {
    const rowHeight = 22;
    const slice = windowSlice(5000, 4400, 600, rowHeight);
    expect(slice.start).toBeLessThanOrEqual(200);            // 4400/22
    expect(slice.end).toBeGreaterThanOrEqual(200 + 600 / rowHeight);
    expect(slice.padTop + (slice.end - slice.start) * rowHeight + slice.padBottom)
      .toBe(5000 * rowHeight);
  });

  it("clamps at both ends without going negative", () => {
    expect(windowSlice(5000, 0, 600, 22)).toMatchObject({ start: 0, padTop: 0 });
    const bottom = windowSlice(5000, 5000 * 22, 600, 22);
    expect(bottom.end).toBe(5000);
    expect(bottom.padBottom).toBe(0);
    // a list shorter than the viewport is one slice, not a negative pad
    expect(windowSlice(3, 0, 600, 22)).toMatchObject({ start: 0, end: 3, padBottom: 0 });
  });
});

describe("pending edits", () => {
  const bounded = row("instrument.profile.w", { value: 0.004, lo: 0, hi: 1 });

  it("refuses out-of-bounds and non-numbers before the round trip", () => {
    expect(validateEdit(bounded, "0.006")).toBe("");
    expect(validateEdit(bounded, "-1")).toContain("lower bound");
    expect(validateEdit(bounded, "2")).toContain("upper bound");
    expect(validateEdit(bounded, "abc")).toBe("not a number");
    expect(validateEdit(bounded, "")).toBe("not a number");
  });

  it("batches into one set_values body, dropping unchanged and invalid text", () => {
    const rows = [bounded, row("phases.0.cell.a", { value: 4.1568 })];
    const edits = new Map([
      ["instrument.profile.w", "0.004"],        // unchanged
      ["phases.0.cell.a", "4.157"],             // changed
      ["nope", "1"],                            // not a row
    ]);
    expect(pendingValues(rows, edits)).toEqual({ "phases.0.cell.a": 4.157 });
  });
});

describe("value formatting", () => {
  it("shows a value to the place its esd justifies", () => {
    // 4.1568(2) — one significant figure of the esd sets the last place, the
    // crystallographic convention; `4.156783000` for something known to ±0.0002
    // is a number pretending to a precision the fit never had
    expect(formatValue(4.156783, 0.00019)).toBe("4.1568");
    expect(formatEsd(4.156783, 0.00019)).toBe("(2)");
    expect(formatValue(4.15678312, 0.000002)).toBe("4.156783");
    expect(formatEsd(4.15678312, 0.000002)).toBe("(2)");
  });

  it("falls back to six significant figures without an esd", () => {
    expect(formatValue(4.15678312, null)).toBe("4.15678");
    expect(formatEsd(4.15678312, null)).toBe("");
    expect(formatEsd(4.15678312, 0)).toBe("");
  });
});

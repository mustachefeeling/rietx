/**
 * WP-1045 — the GUI's leg of the three-chair bijection.
 *
 * The corpus is written by `tests/test_search_controls.py` from the live
 * `SearchSpecSpec`/`IndexingControls` models and the live vocabularies
 * (engines, systems, centrings, presets, shift templates), committed so this
 * suite runs on a machine that never installed the package.  A field added to
 * the python model regenerates the corpus and fails here until the form
 * states it; a field stated here that the model lost fails the other way.
 */
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

import {
  CONTROL_FIELDS,
  SEARCH_FIELDS,
  controlsDigest,
  foldSnapshots,
  parsePriorCell,
  priorCellText,
  statedFieldNames,
  type IndexingControls,
} from "./controls";

interface Corpus {
  search_fields: string[];
  control_fields: string[];
  enums: {
    engines: string[];
    systems: string[];
    centrings: Record<string, string[]>;
    presets: string[];
    shift_templates: string[];
  };
}

const corpus: Corpus = JSON.parse(
  readFileSync(
    fileURLToPath(
      new URL("../../../tests/data/gui/index_controls.json", import.meta.url)),
    "utf-8",
  ),
);

describe("the form states the whole model", () => {
  it("covers every SearchSpecSpec field, and no invented ones", () => {
    const stated = statedFieldNames();
    expect([...stated.search].sort()).toEqual([...corpus.search_fields].sort());
    expect([...stated.controls].sort()).toEqual(
      [...corpus.control_fields].sort());
  });

  it("gives every control a label and a help title (no mute fields)", () => {
    // WP-1029's rule: `title=` is these forms' only help mechanism — the
    // assertion that found ten mute fields the day it was written
    for (const field of [...SEARCH_FIELDS, ...CONTROL_FIELDS]) {
      expect(field.label, field.name).toBeTruthy();
      expect(field.title.length, field.name).toBeGreaterThan(20);
    }
  });

  it("carries the vocabularies the widgets need", () => {
    // the widgets render from /api/capabilities at runtime; the corpus pins
    // that the registries the server quotes are non-empty and complete
    expect(corpus.enums.engines.length).toBeGreaterThanOrEqual(3);
    expect(corpus.enums.systems[0]).toBe("cubic"); // order IS information
    expect(corpus.enums.presets).toContain("quick");
    for (const system of corpus.enums.systems) {
      expect(corpus.enums.centrings[system]?.length,
             system).toBeGreaterThanOrEqual(1);
    }
  });
});

describe("prior-cell parsing", () => {
  it("accepts six numbers with any separators", () => {
    expect(parsePriorCell("4.76 4.76, 12.99  90 90 120")).toEqual(
      [4.76, 4.76, 12.99, 90, 90, 120]);
  });

  it("refuses the malformed with a reason, never a throw", () => {
    expect(parsePriorCell("4.76 4.76 12.99 90 90")).toMatch(/six numbers/);
    expect(parsePriorCell("0 4 5 90 90 90")).toMatch(/positive/);
    expect(parsePriorCell("4 4 5 90 190 90")).toMatch(/\(0, 180\)/);
    expect(parsePriorCell("a b c d e f")).toMatch(/six numbers/);
  });

  it("round-trips through the chip text readably", () => {
    expect(priorCellText([4.7594, 4.7594, 12.9917, 90, 90, 120]))
      .toBe("4.7594 4.7594 12.9917 · 90 90 120");
  });
});

describe("the collapsed digest", () => {
  const base: IndexingControls = {
    search: {
      systems: null, centrings: null, min_d_axis: 2, max_d_axis: 25,
      min_volume: 15, max_volume: null, n_unindexed: 2, n_search_lines: 20,
      k_sigma: 3, shift_allowance_deg: 0, shift_template: null,
      budget_seconds: 30, total_budget_seconds: null, preset: null,
      max_candidates: 12, seed: 0, prior_cells: null, prior_spacegroups: null,
    },
    engines: null, validate_candidates: true, check_top: null,
  };

  it("names the preset that will govern, custom budgets and priors", () => {
    expect(controlsDigest(base, "quick")).toBe("quick");
    const custom = structuredClone(base);
    custom.search.total_budget_seconds = 300;
    expect(controlsDigest(custom, "quick")).toBe("custom budget");
    const steered = structuredClone(base);
    steered.search.systems = ["cubic", "tetragonal"];
    steered.search.prior_cells = [[4.76, 4.76, 12.99, 90, 90, 120]];
    steered.engines = ["svd"];
    steered.validate_candidates = false;
    expect(controlsDigest(steered, "quick")).toBe(
      "quick · 1 engine · 2 systems · 1 prior · no validation");
  });
});

describe("streamed per-system shortlists", () => {
  it("keeps the newest snapshot per system, in completion order", () => {
    const folded = foldSnapshots([
      { consensus: true, system: "cubic", n_candidates: 1,
        candidates: [{ cell: [1] }] },
      { engine: "svd", provisional: [] },               // not a snapshot
      { consensus: true, system: "tetragonal", n_candidates: 0,
        candidates: [] },
      { consensus: true, system: "cubic", n_candidates: 2,
        candidates: [{ cell: [1] }, { cell: [2] }] },
    ]);
    expect(folded.map((s) => s.system)).toEqual(["tetragonal", "cubic"]);
    expect(folded[1].n_candidates).toBe(2);
  });
});

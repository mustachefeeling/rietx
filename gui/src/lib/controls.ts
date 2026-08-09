/** WP-1045 — the indexing control surface: one spec, rendered.
 *
 * The field inventory here is held against the committed corpus
 * (`tests/data/gui/index_controls.json`, written by
 * `tests/test_search_controls.py` from the live `SearchSpecSpec`) by
 * `controls.test.ts` — the fnmatch-corpus mechanism: python owns the model
 * and the vocabularies, this file proves the form can state every field.  A
 * field added to the model shows up as a vitest failure here until the form
 * states it, which is the GUI's leg of the three-chair bijection.
 *
 * Values come from `ProjectDoc.indexing` **verbatim** — the server serves the
 * block complete (pydantic defaults filled), so this file carries no second
 * copy of any default.  Vocabularies (engines, systems, centrings, presets,
 * shift templates) come from `/api/capabilities`, never from literals.
 */

export interface SearchValues {
  systems: string[] | null;
  centrings: Record<string, string[]> | null;
  min_d_axis: number;
  max_d_axis: number;
  min_volume: number;
  max_volume: number | null;
  n_unindexed: number;
  n_search_lines: number;
  k_sigma: number;
  shift_allowance_deg: number;
  shift_template: string | null;
  budget_seconds: number;
  total_budget_seconds: number | null;
  preset: string | null;
  max_candidates: number;
  seed: number;
  prior_cells: number[][] | null;
  prior_spacegroups: string[] | null;
}

export interface IndexingControls {
  search: SearchValues;
  engines: string[] | null;
  validate_candidates: boolean;
  check_top: number | null;
}

/** How one control is stated in the form. */
export interface ControlField {
  name: string;
  /** which widget states it — every kind is rendered by the panel */
  kind:
    | "systems"        // checkbox per crystal system, with centring chips
    | "centrings"      // stated inside the systems widget, per system
    | "number"         // a float input
    | "int"            // an integer input
    | "select"         // a vocabulary select (preset, shift template)
    | "prior_cells"    // the analogue-cell list editor
    | "list"           // comma-separated names (prior space groups)
    | "engines"        // checkbox per registered engine
    | "toggle";        // a checkbox
  label: string;
  /** the `title=` help — WP-1029's rule: no mute fields, pinned by test */
  title: string;
  /** null/absent means "package default" and is sent as null */
  optional?: boolean;
}

/** Every `SearchSpecSpec` field, in display order. */
export const SEARCH_FIELDS: ControlField[] = [
  {
    name: "systems", kind: "systems", label: "crystal systems",
    title: "systems to search, run highest-symmetry first (a cubic answer "
      + "costs seconds, a triclinic search minutes). A restricted search is "
      + "not a verdict: the result reports systems_searched rather than "
      + "concluding anything about the specimen",
  },
  {
    name: "centrings", kind: "centrings", label: "centrings",
    title: "Bravais centrings to try in this system; unticking one narrows "
      + "the search and is recorded in spec_notes. At least one must stay",
  },
  {
    name: "preset", kind: "select", label: "preset", optional: true,
    title: "the whole-run ceiling's name. quick (default): every engine and "
      + "system under a measured ceiling, truncation reported loudly; full: "
      + "unbounded. A typed total budget overrides it and records 'custom'",
  },
  {
    name: "total_budget_seconds", kind: "number", label: "total budget (s)",
    optional: true,
    title: "wall-clock ceiling for the whole run — search, probe and "
      + "validation together. Empty leaves it to the preset; setting it "
      + "overrides the preset's and the result records preset='custom'",
  },
  {
    name: "budget_seconds", kind: "number", label: "budget / slice (s)",
    title: "wall clock per (engine × crystal system) slice, not per run. An "
      + "engine stopped by it reports search_complete=false for the system, "
      + "and a negative result there is not evidence",
  },
  {
    name: "min_d_axis", kind: "number", label: "min axis (Å)",
    title: "shortest principal d-spacing to consider — a bound on d(100), "
      + "slightly stronger than a bound on a for oblique cells",
  },
  {
    name: "max_d_axis", kind: "number", label: "max axis (Å)",
    title: "longest principal d-spacing; raising it costs exponentially — "
      + "domain size is what an exhaustive search pays for",
  },
  {
    name: "min_volume", kind: "number", label: "min volume (Å³)",
    title: "smallest cell volume a candidate may have",
  },
  {
    name: "max_volume", kind: "number", label: "max volume (Å³)",
    optional: true,
    title: "cell-volume ceiling, taken verbatim. Empty takes Smith's "
      + "per-system envelope from the data-quality report (with the "
      + "calibration slack the engines apply to a mean line)",
  },
  {
    name: "n_unindexed", kind: "int", label: "unindexed allowed",
    title: "search lines a cell may leave unindexed and still be accepted. "
      + "Raising it MANUFACTURES cells — every tolerated line is one more "
      + "coincidence a wrong metric is allowed — so 2 is a default and 4 is "
      + "a statement about the specimen",
  },
  {
    name: "n_search_lines", kind: "int", label: "search lines",
    title: "observed lines the search is DRIVEN by (the strongest N). Not "
      + "free to raise: a cell must index all but the allowance of THESE, "
      + "so every extra foreign line can refute the true cell (measured: a "
      + "68-line list loses its certified lattice at 32)",
  },
  {
    name: "k_sigma", kind: "number", label: "k·σ window",
    title: "matching window in units of each line's own σ; 3 is a "
      + "calibrated 99.7 % window, not a knob",
  },
  {
    name: "shift_allowance_deg", kind: "number", label: "shift allowance (°)",
    title: "a MEASURED systematic 2θ allowance — the shift's amplitude a "
      + "window must span (ShiftScreen.allowance_deg), never the residual "
      + "scatter a template leaves: the two differ 4.3× on a certified "
      + "pattern and declaring the scatter finds no cell at all. 0 = let "
      + "the engines assume 0.05° and cap confidence",
  },
  {
    name: "shift_template", kind: "select", label: "shift template",
    optional: true,
    title: "the physical cause of the 2θ shift, if you know it — a "
      + "surviving candidate is re-fitted with this column, which is what "
      + "stops a widened search reporting a biased cell",
  },
  {
    name: "max_candidates", kind: "int", label: "max candidates",
    title: "how many candidates the reported list holds, after the engines "
      + "are merged and ranked — and what prices validation, since each "
      + "reported candidate costs a Le Bail fit. Each engine hands the merge "
      + "five times this many, so the cap never decides a rank",
  },
  {
    name: "seed", kind: "int", label: "seed",
    title: "the stochastic engine's RNG seed, recorded in every result so a "
      + "run is reproducible from what it reports",
  },
  {
    name: "prior_cells", kind: "prior_cells", label: "analogue cells",
    title: "structural-analogue cells (a b c α β γ) to try first — the "
      + "system jumps the queue, the metric seeds the stochastic engine, "
      + "and the cell itself is checked against the lines. A prior steers, "
      + "never gates: a wrong one costs time, not truth, and "
      + "INDEX_PRIOR_USED records what it changed",
  },
  {
    name: "prior_spacegroups", kind: "list", label: "analogue space groups",
    title: "space-group symbols from an analogue (e.g. R -3 c): each "
      + "contributes its crystal system to the queue jump and, beside a "
      + "matching prior cell, its centring",
  },
];

/** The `IndexingControls` fields beside `search`, in display order. */
export const CONTROL_FIELDS: ControlField[] = [
  {
    name: "engines", kind: "engines", label: "engines",
    title: "which searches run; all of them is the default to keep — high "
      + "confidence MEANS every engine that ran found the same lattice, so "
      + "a subset narrows what the answer can say",
  },
  {
    name: "validate_candidates", kind: "toggle", label: "Le Bail validation",
    title: "whole-profile validation of the top candidates; turning it off "
      + "caps every candidate at medium, so do it only to save time on a "
      + "first look",
  },
  {
    name: "check_top", kind: "int", label: "check top", optional: true,
    title: "candidates given the expensive per-candidate checks (ambiguity "
      + "+ Le Bail). Empty = the package default plus every candidate the "
      + "gate could promote",
  },
];

/** The names this form states, for the corpus test. */
export function statedFieldNames(): { search: string[]; controls: string[] } {
  return {
    search: SEARCH_FIELDS.map((f) => f.name),
    controls: CONTROL_FIELDS.map((f) => f.name),
  };
}

/** `doc.indexing` verbatim — the server serves the block complete. */
export function controlsFromDoc(doc: any): IndexingControls | null {
  return doc?.indexing ?? null;
}

/** Parse an "a b c α β γ" line into a prior cell, or return the complaint. */
export function parsePriorCell(text: string): number[] | string {
  const parts = text.trim().split(/[\s,]+/).filter(Boolean).map(Number);
  if (parts.length !== 6 || parts.some((v) => !Number.isFinite(v))) {
    return "a prior cell is six numbers: a b c α β γ";
  }
  const [a, b, c, al, be, ga] = parts;
  if (Math.min(a, b, c) <= 0) return "axes must be positive";
  if ([al, be, ga].some((x) => x <= 0 || x >= 180)) {
    return "angles must lie in (0, 180)°";
  }
  return parts;
}

/** `4.7594 4.7594 12.9917 · 90 90 120` — the chip text for one prior cell. */
export function priorCellText(cell: readonly number[]): string {
  const lengths = cell.slice(0, 3).map((v) => Number(v.toPrecision(6)));
  const angles = cell.slice(3, 6).map((v) => Number(v.toPrecision(5)));
  return `${lengths.join(" ")} · ${angles.join(" ")}`;
}

/** A short digest for the collapsed summary line. */
export function controlsDigest(controls: IndexingControls | null,
                               defaultPreset: string): string {
  if (!controls) return "";
  const s = controls.search;
  const bits: string[] = [];
  bits.push(s.total_budget_seconds != null ? "custom budget"
    : (s.preset ?? defaultPreset));
  if (controls.engines?.length) bits.push(`${controls.engines.length} engine${controls.engines.length === 1 ? "" : "s"}`);
  if (s.systems?.length) bits.push(`${s.systems.length} system${s.systems.length === 1 ? "" : "s"}`);
  const priors = (s.prior_cells?.length ?? 0) + (s.prior_spacegroups?.length ?? 0);
  if (priors) bits.push(`${priors} prior${priors === 1 ? "" : "s"}`);
  if (!controls.validate_candidates) bits.push("no validation");
  return bits.join(" · ");
}

/** One streamed per-system shortlist (WP-1042's `consensus:<system>` unit),
 * newest per system, in the order systems completed. */
export interface SystemSnapshot {
  system: string;
  n_candidates: number;
  candidates: Array<Record<string, any>>;
}

export function foldSnapshots(datas: ReadonlyArray<Record<string, any>>
                              ): SystemSnapshot[] {
  const bySystem = new Map<string, SystemSnapshot>();
  for (const d of datas) {
    if (!d?.consensus || typeof d.system !== "string") continue;
    bySystem.delete(d.system);
    bySystem.set(d.system, {
      system: d.system,
      n_candidates: Number(d.n_candidates ?? d.candidates?.length ?? 0),
      candidates: d.candidates ?? [],
    });
  }
  return [...bySystem.values()];
}

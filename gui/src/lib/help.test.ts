/**
 * The help corpus resolved and placed (WP-1203).
 *
 * Two halves that fail differently.  **Resolution** is a vocabulary question,
 * so it is held to `tests/data/gui/help_keys.json` — the committed key set
 * written from the live registry by `tests/test_gui_help.py`, the same device
 * `fnmatch.test.ts` uses — and every literal `<Help for=…>` in the app is
 * crossed against it: a key naming nothing renders "not yet described" under a
 * real control while nothing goes red.  **Placement** is arithmetic, and it is
 * asserted on numbers because jsdom has no layout: every
 * `getBoundingClientRect` there is zeros, so a popover positioned in a
 * component test would be "correct" wherever it went.
 */
import { readFileSync, readdirSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

import {
  ARMS,
  HELP_GAP,
  HELP_MARGIN,
  manualUrl,
  paramKey,
  place,
  resolve,
  splitKey,
  type HelpCorpus,
} from "./help";

const SRC = fileURLToPath(new URL("../", import.meta.url));
const FIXTURE = JSON.parse(
  readFileSync(fileURLToPath(new URL("../../../tests/data/gui/help_keys.json",
                                    import.meta.url)), "utf-8"),
) as { docs_url: string; arms: string[]; keys: string[] };

/** A corpus of the shape the route serves, small enough to read. */
function corpus(): HelpCorpus {
  const entry = (title: string, extra: Record<string, unknown> = {}) => ({
    title, description: `what ${title} is`, unit: null, default: null,
    typical: null, anchor: null, ...extra,
  });
  return {
    parameters: [
      { paths: ["phases.*.cell.a", "phases.*.cell.b", "phases.*.cell.c"],
        ...entry("Cell edge", { unit: "Å", anchor: "peak-positions.html#lattice" }) },
      { paths: ["instrument.zero_shift"], ...entry("Zero-point shift") },
    ],
    peak_flags: { excluded: entry("Excluded") },
    peak_diagnostics: { PEAK_LIST_TOO_SHORT: entry("Too few lines") },
    stage_fields: { seed: entry("Stage seed"), max_iter: entry("Iteration cap") },
    reader_options: { block: entry("Data block") },
    instrument_fields: { radiation: entry("Anode") },
    search_fields: { seed: entry("Random seed"), preset: entry("Search preset") },
    plans: { profile_only: entry("Profile only", { modes: ["rietveld"] }) },
    docs_url: "https://rietx.org",
  };
}

describe("a key names its arm", () => {
  it("splits `arm:name` and refuses anything else", () => {
    expect(splitKey("stage_fields:max_iter"))
      .toEqual({ arm: "stage_fields", name: "max_iter" });
    // a parameter name contains dots and stars; only the FIRST colon splits
    expect(splitKey("parameters:phases.*.cell.a"))
      .toEqual({ arm: "parameters", name: "phases.*.cell.a" });
    expect(splitKey("max_iter")).toBeNull();
    expect(splitKey("nonsense:max_iter")).toBeNull();
    expect(splitKey(":max_iter")).toBeNull();
  });

  it("resolves the same bare name differently in two arms", () => {
    // the whole reason a key carries its arm: `seed` is a stage field and a
    // search control, and a bare key would answer by declaration order
    const c = corpus();
    expect(resolve(c, "stage_fields:seed")!.title).toBe("Stage seed");
    expect(resolve(c, "search_fields:seed")!.title).toBe("Random seed");
  });

  it("matches a parameter key against the globs of its family", () => {
    const c = corpus();
    expect(resolve(c, "parameters:phases.*.cell.b")!.title).toBe("Cell edge");
    // a *path* is not a key: the row carries the glob, and matching here would
    // be a second fnmatch implementation for a question the server answered
    expect(resolve(c, "parameters:phases.0.cell.b")).toBeNull();
  });

  it("returns null for an unknown name, an unknown arm and no corpus", () => {
    const c = corpus();
    expect(resolve(c, "stage_fields:no_such_field")).toBeNull();
    expect(resolve(c, "no_such_arm:seed")).toBeNull();
    expect(resolve(null, "stage_fields:seed")).toBeNull();
  });

  it("builds a parameter key from a row's help_key, and nothing from none", () => {
    expect(paramKey("phases.*.cell.a")).toBe("parameters:phases.*.cell.a");
    expect(paramKey(null)).toBeNull();
    expect(paramKey("")).toBeNull();
  });
});

describe("the manual link", () => {
  it("joins the served base to the entry's page and heading", () => {
    const c = corpus();
    expect(manualUrl(c, resolve(c, "parameters:phases.*.cell.a")))
      .toBe("https://rietx.org/peak-positions.html#lattice");
  });

  it("is null where the entry names no chapter", () => {
    const c = corpus();
    expect(manualUrl(c, resolve(c, "stage_fields:seed"))).toBeNull();
    expect(manualUrl(c, null)).toBeNull();
  });

  it("does not double the slash when the base carries one", () => {
    const c = { ...corpus(), docs_url: "https://rietx.org/" };
    expect(manualUrl(c, resolve(c, "parameters:phases.*.cell.a")))
      .toBe("https://rietx.org/peak-positions.html#lattice");
  });
});

describe("where the popover goes", () => {
  const viewport = { width: 1200, height: 800 };
  const size = { width: 320, height: 200 };
  const anchor = (left: number, top: number) =>
    ({ left, top, right: left + 60, bottom: top + 16 });

  it("sits below its anchor, left edges aligned", () => {
    expect(place(anchor(400, 300), viewport, size))
      .toEqual({ left: 400, top: 316 + HELP_GAP, flipped: false });
  });

  it("flips above when below would leave the viewport", () => {
    // bottom 716 + 6 + 200 = 922 > 800 - 8, so above: 700 - 6 - 200
    expect(place(anchor(400, 700), viewport, size))
      .toEqual({ left: 400, top: 494, flipped: true });
  });

  it("does not flip a popover taller than the viewport", () => {
    // neither side fits: staying below and clamping to the top margin shows
    // the first line, where flipping would show the last
    const tall = { width: 320, height: 900 };
    expect(place(anchor(400, 700), viewport, tall))
      .toEqual({ left: 400, top: HELP_MARGIN, flipped: false });
  });

  it("clamps to the right margin rather than overflowing", () => {
    expect(place(anchor(1100, 300), viewport, size).left)
      .toBe(1200 - 320 - HELP_MARGIN);
  });

  it("clamps to the left margin for an anchor at the window edge", () => {
    expect(place(anchor(0, 300), viewport, size).left).toBe(HELP_MARGIN);
  });

  it("keeps a popover wider than the viewport at the left margin", () => {
    const wide = { width: 2000, height: 200 };
    expect(place(anchor(400, 300), viewport, wide).left).toBe(HELP_MARGIN);
  });
});

describe("every key the app writes down names something", () => {
  /** `App.svelte` and the panels — where a literal `for=` can be written. */
  function markup(): Array<[string, string]> {
    const files = ["App.svelte",
                   ...readdirSync(`${SRC}panels`).filter((f) => f.endsWith(".svelte"))
                     .sort().map((f) => `panels/${f}`)];
    return files.map((rel) => [rel, readFileSync(`${SRC}${rel}`, "utf-8")]);
  }

  it("declares the arms the registry has", () => {
    expect([...ARMS]).toEqual(FIXTURE.arms);
  });

  it("resolves every literal <Help for=…> against the committed key set", () => {
    const known = new Set(FIXTURE.keys);
    const unknown: string[] = [];
    for (const [rel, source] of markup()) {
      for (const m of source.matchAll(/<Help\b[^>]*?\bfor="([^"{}]+)"/g)) {
        if (!known.has(m[1])) unknown.push(`${rel}: ${m[1]}`);
      }
    }
    // A key naming nothing is silent at runtime — the popover says "not yet
    // described" under a control that has a perfectly good entry with a
    // slightly different name.
    expect(unknown).toEqual([]);
  });
});

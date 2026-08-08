/**
 * The import wizard's logic, and the one cross-language pin it needs.
 *
 * The fixture is written by `tests/test_gui_server.py` from
 * `gui.imports.INSTRUMENT_PRESETS` — which is itself pinned to
 * `inspect.signature(Instrument.<preset>)` — so a field this form offers that
 * the constructor does not take fails here rather than as a 400 the first time
 * someone imports a project.
 */
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

import { GEOMETRIES, instrumentFields } from "./model";
import {
  PRESET_FIELDS,
  blocked,
  createBody,
  emptyWizard,
  instrumentArgument,
  patternSummary,
  presetSpec,
  structureSummary,
} from "./wizard";

const presets: Record<string, string[]> = JSON.parse(
  readFileSync(
    fileURLToPath(new URL("../../../tests/data/gui/instrument_presets.json",
                          import.meta.url)),
    "utf-8",
  ),
);

function staged(): ReturnType<typeof emptyWizard> {
  const state = emptyWizard();
  state.pattern = {
    upload: "p1", n_points: 4200, two_theta_range: [10, 90], has_sigma: true,
    format: { name: "xy", title: "Two/three-column ASCII (.xy / .xye)" },
  };
  state.structure = {
    upload: "c1",
    phases: [{ name: "LaB6", space_group: "P m -3 m", cell: [4.1566, 4.1566, 4.1566],
               n_atoms: 2, species: ["B", "La"] }],
  };
  state.path = "/tmp/lab6.pxrd";
  state.values = { radiation: "CuKa" };
  return state;
}

describe("the preset forms are the constructors' arguments", () => {
  it("offers every argument each preset takes, and no others", () => {
    expect(Object.keys(PRESET_FIELDS).sort()).toEqual(Object.keys(presets).sort());
    for (const [name, args] of Object.entries(presets)) {
      const offered = PRESET_FIELDS[name].map((field) => field.name).sort();
      expect(offered, name).toEqual([...args].sort());
    }
  });
});

describe("presetSpec", () => {
  it("sends a decision, not a wavelength", () => {
    const state = staged();
    expect(presetSpec(state)).toEqual({ preset: "bragg_brentano", radiation: "CuKa" });
  });

  it("drops empty fields rather than nulling a constructor default", () => {
    const state = staged();
    state.values = { radiation: "CuKa", goniometer_radius_mm: "", mu_t: "  " };
    expect(presetSpec(state)).toEqual({ preset: "bragg_brentano", radiation: "CuKa" });
  });

  it("makes numbers numbers and leaves an anode a name", () => {
    const state = staged();
    state.values = { radiation: "MoKa", goniometer_radius_mm: "240", ka2_ratio: "0.48" };
    expect(presetSpec(state)).toEqual({
      preset: "bragg_brentano", radiation: "MoKa",
      goniometer_radius_mm: 240, ka2_ratio: 0.48,
    });
  });

  it("prefers an uploaded profile over the form", () => {
    const state = staged();
    state.instrument = { upload: "i1" };
    expect(instrumentArgument(state)).toEqual({ upload: "i1" });
  });
});

describe("createBody", () => {
  it("commits tokens, never paths", () => {
    const body = createBody(staged()) as any;
    expect(body.pattern).toEqual({ upload: "p1" });
    expect(body.structure).toEqual({ upload: "c1", aniso: false });
    expect(JSON.stringify(body)).not.toContain("/api/upload");
  });

  it("carries the reader options only when one was picked", () => {
    const state = staged();
    expect(createBody(state).reader_options).toBeUndefined();
    state.readerOptions = { block: "meas" };
    expect(createBody(state).reader_options).toEqual({ block: "meas" });
    // a cleared control is not a request — it must not reach the server as ""
    state.readerOptions = { block: "" };
    expect(createBody(state).reader_options).toBeUndefined();
  });

  it("carries the aniso opt-in as chosen", () => {
    const state = staged();
    state.aniso = true;
    expect((createBody(state).structure as any).aniso).toBe(true);
  });
});

describe("blocked", () => {
  it("names the missing step, in order", () => {
    const state = emptyWizard();
    expect(blocked(state)).toMatch(/pattern/);
    state.pattern = staged().pattern;
    expect(blocked(state)).toMatch(/CIF/);
    state.structure = staged().structure;
    state.values = { radiation: "CuKa" };
    expect(blocked(state)).toMatch(/project directory/);
    state.path = "/tmp/lab6";
    expect(blocked(state)).toMatch(/\.pxrd/);
    state.path = "/tmp/lab6.pxrd";
    expect(blocked(state)).toBe("");
  });

  it("asks for the one field a preset cannot default", () => {
    const state = staged();
    state.preset = "debye_scherrer";
    state.values = {};
    expect(blocked(state)).toMatch(/wavelength/);
    state.values = { wavelength: "0.4139" };
    expect(blocked(state)).toBe("");
  });

  it("catches a typed non-number before the round trip", () => {
    const state = staged();
    state.values = { radiation: "CuKa", goniometer_radius_mm: "wide" };
    expect(blocked(state)).toMatch(/not a number/);
  });

  it("stops asking for preset fields once a profile is uploaded", () => {
    const state = staged();
    state.preset = "debye_scherrer";
    state.values = {};
    state.instrument = { upload: "i1" };
    expect(blocked(state)).toBe("");
  });
});

describe("the step summaries quote the reader rather than the extension", () => {
  it("says which weights the fit will use", () => {
    expect(patternSummary(staged().pattern)).toContain("σ from the file");
    const poisson = { ...staged().pattern, has_sigma: false };
    expect(patternSummary(poisson)).toContain("Poisson fallback");
    expect(patternSummary(null)).toBe("");
  });

  it("summarises a phase without inventing anything", () => {
    expect(structureSummary(staged().structure)).toBe(
      "LaB6 · P m -3 m · 4.1566 4.1566 4.1566 Å · 2 atoms (B, La)");
  });
});

describe("no form field without help (WP-1032)", () => {
  /** Every geometry the instrument editor can be showing, so its whole field
   *  vocabulary is reachable from one assertion. */
  const INSTRUMENTS = GEOMETRIES.map((kind) => ({
    zero_shift: { value: 0 },
    source: { polarization: { value: 0.5 },
              lines: [{ wavelength: 1.54, weight: { value: 1 } },
                      { wavelength: 1.544, weight: { value: 0.5 } }] },
    profile: { shape: "tchz_pv", u: {}, v: {}, w: {}, x: {}, y: {} },
    geometry: { kind },
  }));

  it("titles every preset field the wizard offers", () => {
    // `title=` is this form's *only* help mechanism, and `packing` — the field
    // the report named — was offered in three places with none of them.
    const bare = Object.entries(PRESET_FIELDS).flatMap(([preset, fields]) =>
      fields.filter((f) => !f.title?.trim()).map((f) => `${preset}.${f.name}`));
    expect(bare).toEqual([]);
  });

  it("titles every field the instrument editor offers, in every geometry", () => {
    const bare = INSTRUMENTS.flatMap((instrument) =>
      instrumentFields(instrument)
        .filter((f) => !f.title?.trim())
        .map((f) => `${instrument.geometry.kind}:${f.path}`));
    expect(bare).toEqual([]);
  });

  it("explains packing the same way wherever it is offered", () => {
    // one wording, quoted from `schemas/instrument.py` — two forms explaining
    // one quantity two ways is how a form starts disagreeing with the package
    const titles = new Set<string>();
    for (const fields of Object.values(PRESET_FIELDS)) {
      for (const f of fields) if (f.name === "packing_fraction") titles.add(f.title!);
    }
    for (const instrument of INSTRUMENTS) {
      for (const f of instrumentFields(instrument)) {
        if (f.path === "geometry.packing_fraction") titles.add(f.title!);
      }
    }
    expect(titles.size).toBe(1);
    expect([...titles][0]).toContain("never refinable");
  });
});

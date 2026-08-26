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
  presetHelp,
  presetSpec,
  structureSummary, applyInstrumentHint, scanCount } from "./wizard";

const presets: Record<string, string[]> = JSON.parse(
  readFileSync(
    fileURLToPath(new URL("../../../tests/data/gui/instrument_presets.json",
                          import.meta.url)),
    "utf-8",
  ),
);

/** The corpus's key set, written from the live registry by
 *  `tests/test_gui_help.py` — the second cross-language pin this file needs
 *  now that the explanations live in `rietx.help` rather than beside the
 *  fields. */
const HELP_KEYS = JSON.parse(
  readFileSync(
    fileURLToPath(new URL("../../../tests/data/gui/help_keys.json",
                          import.meta.url)),
    "utf-8",
  ),
) as { keys: string[] };

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
  state.path = "/tmp/lab6.rex";
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
    expect(blocked(state)).toMatch(/\.rex/);
    state.path = "/tmp/lab6.rex";
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

  it("gives every preset field a help key that resolves (no mute fields)", () => {
    // WP-1029's rule, retargeted by WP-1203: the explanation is an entry in
    // `rietx.help` rather than a `title=` beside the field, so what has to hold
    // is that every key names one.  `packing` — the field WP-1032 was reported
    // against, offered in three places with a title in none — is covered by
    // construction now: the key is the field's own name.
    const known = new Set(HELP_KEYS.keys);
    const mute = Object.entries(PRESET_FIELDS).flatMap(([preset, fields]) =>
      fields.filter((f) => !known.has(presetHelp(f))).map((f) => `${preset}.${f.name}`));
    expect(mute).toEqual([]);
  });

  it("gives every instrument-editor field a help key or a stated exception", () => {
    // Two fields have no corpus entry and say so in `lib/model.ts`:
    // `geometry.kind` and `profile.shape` are model *choices*, not named
    // quantities, and neither has a vocabulary the corpus is keyed by.  Naming
    // them here rather than allowing any `title` keeps the exception countable
    // — a third one fails until it is either described or added to this list.
    const known = new Set(HELP_KEYS.keys);
    const NO_ENTRY = ["geometry.kind", "profile.shape"];
    const bare: string[] = [];
    const exceptions = new Set<string>();
    for (const instrument of INSTRUMENTS) {
      for (const f of instrumentFields(instrument)) {
        if (f.help && known.has(f.help)) continue;
        if (NO_ENTRY.includes(f.path) && f.title?.trim()) {
          exceptions.add(f.path);
          continue;
        }
        bare.push(`${instrument.geometry.kind}:${f.path}`);
      }
    }
    expect(bare).toEqual([]);
    // …and the exception list may not outlive its members
    expect([...exceptions].sort()).toEqual([...NO_ENTRY].sort());
  });

  it("explains packing the same way wherever it is offered", () => {
    // One wording, and now by construction rather than by comparison: both
    // forms name the same corpus entry, so the two cannot drift.  The
    // assertion is that they name the *same* one — a wizard field pointing at
    // `instrument_fields:packing_fraction` and an editor field pointing
    // anywhere else would be the same defect in a new shape.
    const keys = new Set<string>();
    for (const fields of Object.values(PRESET_FIELDS)) {
      for (const f of fields) if (f.name === "packing_fraction") keys.add(presetHelp(f));
    }
    for (const instrument of INSTRUMENTS) {
      for (const f of instrumentFields(instrument)) {
        if (f.path === "geometry.packing_fraction") keys.add(f.help!);
      }
    }
    expect([...keys]).toEqual(["instrument_fields:packing_fraction"]);
  });
});

describe("applyInstrumentHint", () => {
  it("seeds the preset and its fields from what the file knew", () => {
    const state = applyInstrumentHint(emptyWizard(), {
      preset: "bragg_brentano", radiation: "CuKa1",
      goniometer_radius_mm: 280, why: "…",
    });
    expect(state.preset).toBe("bragg_brentano");
    expect(state.values.radiation).toBe("CuKa1");
    expect(state.values.goniometer_radius_mm).toBe("280");
    // the spec the form will actually post carries them, not just the display
    expect(presetSpec(state)).toMatchObject(
      { preset: "bragg_brentano", radiation: "CuKa1", goniometer_radius_mm: 280 });
  });

  it("switches geometry when the file's wavelength is no Kα line", () => {
    const state = applyInstrumentHint(emptyWizard(), {
      preset: "debye_scherrer", wavelength: 0.413909, why: "…",
    });
    expect(state.preset).toBe("debye_scherrer");
    expect(presetSpec(state)).toMatchObject(
      { preset: "debye_scherrer", wavelength: 0.413909 });
  });

  it("leaves the form untouched when there is no hint", () => {
    // a header whose name and wavelength disagree sends null rather than a
    // guess, and an empty form beats one that looks like it was read
    const before = emptyWizard();
    for (const hint of [null, undefined, {}, { preset: "not_a_preset" }]) {
      expect(applyInstrumentHint(before, hint)).toEqual(before);
    }
  });
});

describe("scanCount", () => {
  it("reads the preview's own metadata and defaults to one", () => {
    expect(scanCount({ metadata: { scan_count: "3" } })).toBe(3);
    expect(scanCount({ metadata: {} })).toBe(1);
    expect(scanCount(null)).toBe(1);
  });
});

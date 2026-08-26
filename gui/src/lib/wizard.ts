/** The import wizard's logic: three previews, one create (WP-1014).
 *
 * The flow is two-phase by construction — pattern, structure and instrument are
 * *previewed* first and only tokens are committed — so what is left here is the
 * bookkeeping between the steps and the one judgement the client is allowed to
 * make: whether the project can be created yet, and if not, which step is
 * missing. `blocked()` returns that sentence; nothing here decides anything the
 * server would decide differently.
 *
 * The instrument step sends a **decision**, not a model: a geometry and (for a
 * lab instrument) an anode name. The package owns the physics that follows — the
 * emission wavelengths come from its NIST-scale table (WP-0507), the doublet from
 * the anode, the polarization constant from the monochromator angle. A form that
 * posted a whole `Instrument` would be a second copy of all three, kept in
 * TypeScript, and the wavelengths are the exact quantity a ~100 ppm cell error
 * hides in.
 *
 * `PRESET_FIELDS` is held to the constructors' own signatures across the language
 * boundary by `tests/data/gui/instrument_presets.json`, the same device the glob
 * corpus uses: written from `gui.imports.INSTRUMENT_PRESETS` by pytest, replayed
 * by `wizard.test.ts`. A field this form offers that the constructor does not
 * take is a control whose only outcome is a 400.
 */

export type PresetFieldKind = "number" | "optnumber" | "anode";

export interface PresetField {
  name: string;
  label: string;
  kind: PresetFieldKind;
  unit?: string;
  /** prefilled when the step opens; "" means "leave it to the constructor" */
  initial?: string;
}

/**
 * The corpus key that describes one preset field (WP-1203).
 *
 * Derived from the field's own name, not stored beside it: the
 * `instrument_fields` arm is keyed by the union of `INSTRUMENT_PRESETS`, which
 * is the same list `PRESET_FIELDS` is already held to across the language
 * boundary, so a second list could only be a way for the two to disagree.
 *
 * `packing_fraction` was the field WP-1032 was reported against — offered in
 * three places with no `title` in any of them, on a form whose only help
 * mechanism *was* `title=`.  It has an entry now, and so does every other
 * field here, crossed both ways by `tests/test_help.py`.
 */
export function presetHelp(field: PresetField): string {
  return `instrument_fields:${field.name}`;
}

/** The three geometries, and the arguments each one takes. */
export const PRESET_FIELDS: Record<string, PresetField[]> = {
  debye_scherrer: [
    { name: "wavelength", label: "wavelength", kind: "number", unit: "Å" },
    { name: "polarization", label: "polarization", kind: "optnumber" },
    { name: "goniometer_radius_mm", label: "radius", kind: "optnumber", unit: "mm" },
    { name: "capillary_radius_mm", label: "capillary r", kind: "optnumber",
      unit: "mm" },
    { name: "mu_r", label: "µR", kind: "optnumber" },
    { name: "packing_fraction", label: "packing", kind: "optnumber" },
  ],
  bragg_brentano: [
    { name: "radiation", label: "anode", kind: "anode", initial: "CuKa" },
    { name: "goniometer_radius_mm", label: "radius", kind: "optnumber", unit: "mm" },
    { name: "monochromator_two_theta", label: "2θ monochromator", kind: "optnumber",
      unit: "°" },
    { name: "ka2_ratio", label: "Kα2/Kα1", kind: "optnumber" },
    { name: "mu_t", label: "µt", kind: "optnumber" },
    { name: "thickness_mm", label: "thickness", kind: "optnumber", unit: "mm" },
  ],
  flat_plate_transmission: [
    { name: "radiation", label: "anode", kind: "anode", initial: "CuKa1" },
    { name: "mu_t", label: "µt", kind: "optnumber" },
    { name: "thickness_mm", label: "thickness", kind: "optnumber", unit: "mm" },
    { name: "packing_fraction", label: "packing", kind: "optnumber" },
    { name: "ka2_ratio", label: "Kα2/Kα1", kind: "optnumber" },
  ],
};

export const PRESET_TITLES: Record<string, string> = {
  debye_scherrer: "Capillary / synchrotron (Debye-Scherrer)",
  bragg_brentano: "Lab flat plate, reflection (Bragg-Brentano)",
  flat_plate_transmission: "Flat plate, transmission",
};

export interface WizardState {
  /** `POST /api/upload/pattern`'s answer, or null before a file is chosen */
  pattern: any | null;
  /** the reader keywords this format offers, by name — `block`, `scan`, … */
  readerOptions: Record<string, string>;
  /** `POST /api/upload/cif`'s answer */
  structure: any | null;
  aniso: boolean;
  /** an uploaded instrument profile takes precedence over the preset form */
  instrument: any | null;
  preset: string;
  values: Record<string, string>;
  path: string;
  mode: string;
  plan: string;
}

export function emptyWizard(): WizardState {
  return seedPreset({ pattern: null, readerOptions: {}, structure: null, aniso: false,
                      instrument: null, preset: "bragg_brentano", values: {},
                      path: "", mode: "rietveld", plan: "mccusker_default" },
                    "bragg_brentano");
}

/**
 * Switch preset, filling in the initial values the form will *show*.
 *
 * Seeded rather than left blank so the anode the select displays is the anode the
 * body carries.  Leaving it unset would also work — the constructor's default is
 * `CuKa` — and that is exactly the problem: the form would be showing a value it
 * was not sending, and the two would agree only for as long as nobody changed the
 * default.
 */
export function seedPreset(state: WizardState, preset: string): WizardState {
  const values = { ...state.values };
  for (const field of PRESET_FIELDS[preset] ?? []) {
    if (field.initial && values[field.name] === undefined) {
      values[field.name] = field.initial;
    }
  }
  return { ...state, preset, values };
}

/**
 * Pre-fill the instrument form from what the pattern file already knows.
 *
 * The *matching* happened on the server (`imports.suggest_instrument`), because
 * deciding that 1.5418 Å is a Cu doublet is a physics judgement against the
 * package's radiation table and a copy of that table in TypeScript would be a
 * second authority on wavelengths. What arrives here is already a decision, so
 * this only has to seed the form with it — and a `null` hint (the header
 * contradicts itself) leaves the form exactly as it was, because a wrong
 * pre-fill is worse than an empty one: it looks like it was read.
 */
export function applyInstrumentHint(state: WizardState, hint: any): WizardState {
  if (!hint || typeof hint !== "object" || !PRESET_FIELDS[hint.preset]) return state;
  const seeded = seedPreset({ ...state, values: { ...state.values } }, hint.preset);
  const values = { ...seeded.values };
  for (const field of PRESET_FIELDS[hint.preset]) {
    if (hint[field.name] !== undefined && hint[field.name] !== null) {
      values[field.name] = String(hint[field.name]);
    }
  }
  return { ...seeded, values };
}

/** How many measurements the staged pattern holds — 1 when it does not say.
 *
 * From the preview's own metadata, which the single read already carried, so
 * asking costs nothing. What each scan *is* costs a second walk and is fetched
 * separately, only when someone opens the picker.
 */
export function scanCount(pattern: any): number {
  const n = Number(pattern?.metadata?.scan_count);
  return Number.isFinite(n) && n > 0 ? n : 1;
}

/** The preset arguments, empty fields dropped and numbers made numbers.
 *
 * Dropping an empty field rather than sending `null` is the point: every one of
 * these has a constructor default that is a *decision* (217.5 mm, 0.5, no
 * monochromator, no thickness), and sending null would overwrite it with
 * something nobody chose — which for `mu_t` is not even a legal instrument.
 */
export function presetSpec(state: WizardState): Record<string, unknown> {
  const spec: Record<string, unknown> = { preset: state.preset };
  for (const field of PRESET_FIELDS[state.preset] ?? []) {
    const text = (state.values[field.name] ?? "").trim();
    if (!text) continue;
    spec[field.name] = field.kind === "anode" ? text : Number(text);
  }
  return spec;
}

/** The instrument argument: an uploaded profile if there is one, else the form. */
export function instrumentArgument(state: WizardState): Record<string, unknown> {
  return state.instrument
    ? { upload: state.instrument.upload }
    : presetSpec(state);
}

/** The `POST /api/project/new` body — tokens, not paths. */
export function createBody(state: WizardState): Record<string, unknown> {
  const body: Record<string, unknown> = {
    path: state.path.trim(),
    pattern: { upload: state.pattern?.upload },
    structure: { upload: state.structure?.upload, aniso: state.aniso },
    instrument: instrumentArgument(state),
    mode: state.mode,
    plan: state.plan,
  };
  const options = Object.fromEntries(
    Object.entries(state.readerOptions).filter(([, v]) => v !== ""));
  if (Object.keys(options).length) body.reader_options = options;
  return body;
}

/** Why this cannot be created yet, or "" — one sentence, naming the step. */
export function blocked(state: WizardState): string {
  if (!state.pattern) return "Choose a pattern file.";
  if (!state.structure) return "Choose a CIF for the starting structure.";
  if (!state.instrument) {
    for (const field of PRESET_FIELDS[state.preset] ?? []) {
      const missing = field.kind === "number"
        && !(state.values[field.name] ?? "").trim();
      if (missing) return `The ${PRESET_TITLES[state.preset]} preset needs ${field.label}.`;
      const text = (state.values[field.name] ?? "").trim();
      if (text && field.kind !== "anode" && !Number.isFinite(Number(text))) {
        return `${field.label} is not a number.`;
      }
    }
  }
  if (!state.path.trim()) return "Name the project directory.";
  if (!state.path.trim().endsWith(".rex")) {
    return "A project directory's name ends in .rex.";
  }
  return "";
}

/** A one-line summary of a staged pattern, for the step header. */
export function patternSummary(preview: any): string {
  if (!preview) return "";
  const [lo, hi] = preview.two_theta_range ?? [0, 0];
  return `${preview.format.title} · ${preview.n_points} points · `
    + `${lo}–${hi}°2θ · σ ${preview.has_sigma ? "from the file" : "Poisson fallback"}`;
}

/** …and of a staged CIF. */
export function structureSummary(preview: any): string {
  if (!preview) return "";
  const phase = preview.phases?.[0];
  if (!phase) return "";
  const cell = phase.cell.slice(0, 3).map((v: number) => v.toFixed(4)).join(" ");
  return `${phase.name} · ${phase.space_group} · ${cell} Å · `
    + `${phase.n_atoms} atoms (${phase.species.join(", ")})`;
}

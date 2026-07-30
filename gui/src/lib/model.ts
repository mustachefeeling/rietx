/** Structure and instrument editing, as pure functions (WP-1014).
 *
 * The founding rule here is a split, and it is the one that keeps this editor
 * from becoming a second parameter table: **if the parameter table has the path,
 * the parameter table owns it.**  A cell edge, an occupancy, a profile term, a
 * coordinate DOF — all of those are rows in `GET /api/params`, so this editor
 * sends them through `PATCH /api/params`, where the tie/lock/mode rules and the
 * bounds already live and where the refusal is the verb's own words.  What is
 * left for `PATCH /api/structure` / `PATCH /api/instrument` is everything that is
 * *not* a number in θ: a species, a label, an atom added or removed, a geometry
 * declared, a wavelength, a background family.  Those change what the parameter
 * table *contains*, which is exactly why the model routes take a whole validated
 * model rather than a field patch (WP-1008).
 *
 * Two consequences worth stating, because they look like limitations and are the
 * design.  A coordinate is never typed as x/y/z: `x` is an affine tie onto
 * `…dof.k` and typing into it is refused by name, so the editor offers the DOFs
 * and a site-symmetry violation is *unrepresentable* rather than caught.  And a
 * cell edge on a cubic phase refuses with "follows … as an affine tie" — the same
 * sentence the text pane and the parameter grid show, because it is the same call.
 *
 * The delta is computed against a **freshly read** model, not the one on screen —
 * WP-1009's rule, third outing.  A whole-model PATCH built from a stale read
 * would silently revert every field it did not touch.
 */

import { formatValue, num, type ParamRow } from "./table";

export type FieldKind = "number" | "optnumber" | "text" | "choice";

/** One editable field of a model, as data.
 *
 * Declared rather than hand-written into the markup so the same list drives the
 * form, the delta and the tests — a field that renders but is not in the delta is
 * a control that does nothing, and that is the failure this shape makes
 * impossible.
 */
export interface Field {
  /** dot-path inside the model JSON (`profile.u`, `geometry.mu_t`) */
  path: string;
  label: string;
  kind: FieldKind;
  unit?: string;
  title?: string;
  choices?: string[];
  /** shown only in Advanced disclosure */
  advanced?: boolean;
}

/** Walk a dot-path, returning the node or `undefined`. */
export function at(model: any, path: string): any {
  let node = model;
  for (const part of path.split(".")) {
    if (node == null) return undefined;
    node = node[part];
  }
  return node;
}

/** True when this node is a `Parameter` — the schema's `{value, vary, min, max}`. */
export function isParameter(node: any): boolean {
  return node != null && typeof node === "object" && !Array.isArray(node)
    && "value" in node && "vary" in node;
}

/** The value at a path, unwrapping a `Parameter`. */
export function readValue(model: any, path: string): any {
  const node = at(model, path);
  return isParameter(node) ? num(node.value) : node;
}

/** What the field shows — and therefore what a typed edit is compared against.
 *
 * WP-1009's rule: values render at a readable precision, so comparing typed text
 * against the full float would turn clicking into a cell and out again into an
 * edit that quietly truncates.  An absent optional (`mu_t` unset) renders empty,
 * which is how "no thickness declared" is typed: not as 0, which for `mu_t` is a
 * specimen of zero thickness and raises (CLAUDE.md).
 */
export function renderField(model: any, field: Field): string {
  const value = readValue(model, field.path);
  if (value == null) return "";
  if (typeof value === "number") return formatValue(value, null);
  return String(value);
}

/** Why this typed text cannot be sent for this field, or "". */
export function validateField(field: Field, text: string): string {
  const trimmed = text.trim();
  if (field.kind === "optnumber" && trimmed === "") return "";
  if (field.kind === "number" || field.kind === "optnumber") {
    if (trimmed === "" || !Number.isFinite(Number(trimmed))) return "not a number";
  }
  if (field.kind === "choice" && !(field.choices ?? []).includes(trimmed)) {
    return `not one of ${(field.choices ?? []).join(", ")}`;
  }
  if (field.kind === "text" && trimmed === "") return "cannot be empty";
  return "";
}

function coerce(field: Field, text: string): any {
  const trimmed = text.trim();
  if (field.kind === "optnumber") return trimmed === "" ? null : Number(trimmed);
  if (field.kind === "number") return Number(trimmed);
  return trimmed;
}

/** Set a dot-path in place, writing through a `Parameter` to its `value`. */
export function writeField(model: any, field: Field, text: string): void {
  const parts = field.path.split(".");
  const leaf = parts.pop() as string;
  let node = model;
  for (const part of parts) node = node?.[part];
  if (node == null) return;
  const current = node[leaf];
  if (isParameter(current)) current.value = coerce(field, text);
  else node[leaf] = coerce(field, text);
}

/** The parameter-table path a model field corresponds to, or "" if it has none.
 *
 * The instrument's rows are prefixed (`instrument.profile.u`), the structure's
 * are not (`phases.0.cell.a`) — one function so the prefix is written once.
 */
export function paramPath(kind: "structure" | "instrument", path: string): string {
  return kind === "instrument" ? `instrument.${path}` : path;
}

/**
 * What a field's cell shows — the parameter row's value when the table owns it.
 *
 * Load-bearing, and the same rule twice over.  A parameter is displayed at the
 * precision its esd justifies (`4.1568(2)`, not `4.15678123`), so a cell that
 * *rendered* from the row and *compared* against the model would treat clicking
 * in and out again as an edit — and send a truncated value (WP-1011's trap, which
 * is why the two are one function here rather than two call sites that agree
 * today).
 */
export function fieldText(model: any, field: Field,
                          rows: ReadonlyMap<string, ParamRow>,
                          kind: "structure" | "instrument"): string {
  const row = rows.get(paramPath(kind, field.path));
  return row ? formatValue(row.value, row.esd) : renderField(model, field);
}

export interface ModelDelta {
  /** paths the parameter table owns → the number to `set_values` */
  values: Record<string, number>;
  /** fields that are not in θ, applied to a freshly read model */
  fields: Field[];
  /** typed text that cannot be sent, with the reason */
  invalid: Array<{ path: string; why: string }>;
  /** how many cells the user has touched, invalid ones included */
  touched: number;
}

/**
 * Split an edit buffer into "the parameter table's" and "the model's".
 *
 * `rows` is `GET /api/params`, and membership in it is the whole test — no list
 * of which fields happen to be parameters is maintained here, because that list
 * is derived from the schema at run time and would go stale the moment a field
 * became refinable.  A held row (locked, tied, mode-fixed) is still the parameter
 * table's: it must refuse in the verb's own words rather than be quietly written
 * into the model behind the tie's back.
 */
export function splitEdits(
  model: any,
  fields: readonly Field[],
  edits: ReadonlyMap<string, string>,
  rows: readonly ParamRow[],
  kind: "structure" | "instrument",
): ModelDelta {
  const byField = new Map(fields.map((field) => [field.path, field]));
  const byPath = new Map(rows.map((row) => [row.path, row]));
  const delta: ModelDelta = { values: {}, fields: [], invalid: [], touched: 0 };
  for (const [path, text] of edits) {
    const field = byField.get(path);
    if (!field) continue;
    const why = validateField(field, text);
    if (why) {
      delta.invalid.push({ path, why });
      delta.touched += 1;
      continue;
    }
    // against what the cell *shows*, never against the stored float
    if (text.trim() === fieldText(model, field, byPath, kind)) continue;
    delta.touched += 1;
    const owned = byPath.has(paramPath(kind, path));
    if (owned && (field.kind === "number" || field.kind === "optnumber")) {
      delta.values[paramPath(kind, path)] = Number(text);
    } else {
      delta.fields.push(field);
    }
  }
  return delta;
}

/**
 * A deep copy of a model — a JSON round trip, deliberately not `structuredClone`.
 *
 * Found in a real browser and invisible to vitest: a model held in a Svelte 5
 * `$state` rune is a **Proxy**, and `structuredClone` throws
 * `#<Object> could not be cloned` on one.  Under test the same functions are
 * handed plain objects and pass.  A JSON round trip reads *through* the proxy and
 * is exact here for the reason this is safe at all — every model in this panel
 * arrived as JSON over the wire, so there is nothing in it JSON cannot express.
 */
export function clone<T>(model: T): T {
  return JSON.parse(JSON.stringify(model));
}

/** A deep copy of a model with the non-parameter edits written into it. */
export function applyFields(model: any, fields: readonly Field[],
                            edits: ReadonlyMap<string, string>): any {
  const next = clone(model);
  for (const field of fields) writeField(next, field, edits.get(field.path) ?? "");
  return next;
}

// ----------------------------------------------------------------------
// the instrument form
// ----------------------------------------------------------------------
export const GEOMETRIES = ["debye_scherrer", "bragg_brentano",
                           "flat_plate_transmission"] as const;

/** The instrument's fields, for the instrument this project actually has.
 *
 * Geometry-dependent on purpose: `mu_r` applies only to a capillary and `mu_t`
 * only to a flat plate — the schema *raises* on the wrong pairing, so offering
 * both would be offering a field whose only outcome is a refusal.  And the two
 * absorption fields are not the same kind of "off": µR = 0 is no capillary
 * absorption, while `mu_t` **absent** is the thick-specimen case and `mu_t = 0`
 * is a specimen of zero thickness, which raises (CLAUDE.md).  Hence `optnumber`
 * rather than a number defaulting to 0.
 */
export function instrumentFields(instrument: any): Field[] {
  const geometry = instrument?.geometry?.kind ?? "debye_scherrer";
  const fields: Field[] = [
    { path: "geometry.kind", label: "geometry", kind: "choice",
      choices: [...GEOMETRIES],
      title: "changes which corrections apply and which parameters exist" },
    { path: "zero_shift", label: "zero", kind: "number", unit: "°2θ" },
    { path: "source.polarization", label: "polarization", kind: "number",
      title: "GSAS POLA convention; K = 1/(1+cos²2θ_m) for a monochromator" },
  ];
  const lines = instrument?.source?.lines ?? [];
  lines.forEach((_: unknown, i: number) => {
    fields.push({ path: `source.lines.${i}.wavelength`, label: `λ${i + 1}`,
                  kind: "number", unit: "Å" });
    if (i > 0) {
      fields.push({ path: `source.lines.${i}.weight`, label: `w${i + 1}`,
                    kind: "number",
                    title: "relative to line 1, which is locked at 1" });
    }
  });
  fields.push(
    { path: "profile.shape", label: "shape", kind: "choice",
      choices: ["tchz_pv", "voigt"], advanced: true },
    { path: "profile.u", label: "U", kind: "number", unit: "deg²" },
    { path: "profile.v", label: "V", kind: "number", unit: "deg²" },
    { path: "profile.w", label: "W", kind: "number", unit: "deg²" },
    { path: "profile.x", label: "X", kind: "number",
      title: "Lorentzian 1/cosθ — size broadening" },
    { path: "profile.y", label: "Y", kind: "number",
      title: "Lorentzian tanθ — strain broadening" },
    { path: "geometry.axial_sl", label: "S/L", kind: "number",
      title: "FCJ axial divergence: sample length / goniometer radius" },
    { path: "geometry.axial_hl", label: "H/L", kind: "number",
      title: "FCJ axial divergence: detector slit length / goniometer radius" },
    { path: "geometry.sample_displacement", label: "displacement", kind: "number",
      unit: "mm" },
  );
  if (geometry === "bragg_brentano") {
    fields.push(
      { path: "geometry.goniometer_radius_mm", label: "radius", kind: "number",
        unit: "mm" },
      { path: "geometry.sample_transparency", label: "transparency", kind: "number" },
      { path: "geometry.mu_t", label: "µt", kind: "optnumber",
        title: "leave empty for a thick specimen — µt = 0 is a specimen of zero "
               + "thickness and raises" },
      { path: "geometry.thickness_mm", label: "thickness", kind: "optnumber",
        unit: "mm" },
    );
  } else if (geometry === "flat_plate_transmission") {
    fields.push(
      { path: "geometry.mu_t", label: "µt", kind: "optnumber" },
      { path: "geometry.thickness_mm", label: "thickness", kind: "optnumber",
        unit: "mm" },
      { path: "geometry.packing_fraction", label: "packing", kind: "number",
        advanced: true },
    );
  } else {
    fields.push(
      { path: "geometry.mu_r", label: "µR", kind: "optnumber",
        title: "capillary absorption; exactly a reparameterisation of "
               + "{scale, Biso}, so Rwp cannot move" },
      { path: "geometry.capillary_radius_mm", label: "capillary r", kind: "optnumber",
        unit: "mm" },
      { path: "geometry.packing_fraction", label: "packing", kind: "number",
        advanced: true },
    );
  }
  return fields;
}

/**
 * The FCJ warning, or "".
 *
 * The FCJ profile has a genuine corner at S/L = H/L, and both apertures start
 * *equal* in the shipped defaults: the two Jacobian columns are then identical,
 * the correlation guard reports ρ = +1.000, and two solvers escape it in two
 * unprincipled directions (measured in WP-0601).  Surfaced rather than defaulted
 * away, because the defaults are the shipped ones and changing them silently
 * would be a different instrument.
 *
 * Silent on the one equal pair that is *not* a hazard: both at zero and both
 * held, which is axial divergence switched off rather than a degenerate start.
 * That is every freshly created lab instrument, and a warning on all of them
 * would be a warning nobody reads.
 */
export function axialWarning(instrument: any): string {
  const geometry = instrument?.geometry ?? {};
  const sl = num(geometry.axial_sl?.value);
  const hl = num(geometry.axial_hl?.value);
  if (!Number.isFinite(sl) || !Number.isFinite(hl) || sl !== hl) return "";
  const free = Boolean(geometry.axial_sl?.vary || geometry.axial_hl?.vary);
  if (sl === 0 && !free) return "";
  return `S/L = H/L = ${sl}: the FCJ profile has a corner there and the two `
    + `columns are identical (ρ = +1.000)${free ? " — and at least one is free" : ""}.`;
}

/** Whether a value cell may be typed into: the two refusals `set_values` makes.
 *
 * `mode_fixed` is deliberately *not* here — a Le Bail phase's atom values can
 * still be set, they simply will not be varied, and greying them would be the
 * "locked" story told about a row that is not locked (WP-1004). */
export function editableValue(row: ParamRow | undefined): boolean {
  return !row || (!row.locked && !row.tie);
}

// ----------------------------------------------------------------------
// the structure form
// ----------------------------------------------------------------------
/** One row of `GET /api/structure`'s `sites` arm. */
export interface Site {
  path: string;
  phase: number;
  atom: number;
  site_symmetry_order: number;
  special: boolean;
  dof_paths: string[];
  dof_directions: number[][];
  adp_paths: string[];
  adp_patterns: number[][];
  aniso: boolean;
}

export interface AtomRow {
  phase: number;
  index: number;
  base: string;
  atom: any;
  site: Site | null;
  /** the coordinate DOFs that move this atom, as parameter rows */
  dofs: ParamRow[];
  /** the allowed U^ij patterns, as parameter rows (empty unless aniso) */
  adps: ParamRow[];
  /** x, y, z as they stand — read-only, because they are ties onto the DOFs */
  xyz: number[];
  /** "" when the atom can move, else why it cannot */
  frozen: string;
}

/**
 * The atom table: the model's atoms joined to what symmetry allows and to θ.
 *
 * `frozen` is the message a read-only coordinate cell carries, and it is derived
 * from the *site*, not from the parameter rows: a fully fixed special position
 * has no DOFs at all, so there is nothing to grey out — there is nothing to show.
 */
export function atomRows(structure: any, sites: readonly Site[],
                         rows: readonly ParamRow[], phase = 0): AtomRow[] {
  const byPath = new Map(rows.map((row) => [row.path, row]));
  const bySite = new Map(sites.map((site) => [site.path, site]));
  const atoms = structure?.phases?.[phase]?.atoms ?? [];
  return atoms.map((atom: any, index: number) => {
    const base = `phases.${phase}.atoms.${index}`;
    const site = bySite.get(base) ?? null;
    const pick = (paths: string[]) =>
      paths.map((path) => byPath.get(path)).filter(Boolean) as ParamRow[];
    return {
      phase, index, base, atom, site,
      dofs: pick(site?.dof_paths ?? []),
      adps: pick(site?.adp_paths ?? []),
      xyz: [num(atom.x?.value), num(atom.y?.value), num(atom.z?.value)],
      frozen: site && site.dof_paths.length === 0
        ? `fully fixed special position (site symmetry of order ${site.site_symmetry_order})`
        : "",
    };
  });
}

/** A new atom at the origin, in the shape `Structure` validates.
 *
 * Everything but the position is a default the schema would have supplied; the
 * position is asked for because it is the one thing that *decides* something —
 * the site symmetry, and with it how many DOFs the atom will have.
 */
export function newAtom(label: string, species: string,
                        xyz: readonly number[] = [0, 0, 0]): any {
  return {
    label, species,
    x: { value: xyz[0] }, y: { value: xyz[1] }, z: { value: xyz[2] },
    occ: { value: 1.0, min: 0.0, max: 1.5 },
    biso: { value: 0.5, min: 0.0, max: 25.0, unit: "A^2" },
  };
}

/** A structure with one atom added / removed — a deep copy, never a mutation. */
export function withAtom(structure: any, phase: number, atom: any): any {
  const next = clone(structure);
  next.phases[phase].atoms.push(atom);
  return next;
}

export function withoutAtom(structure: any, phase: number, index: number): any {
  const next = clone(structure);
  next.phases[phase].atoms.splice(index, 1);
  return next;
}

/**
 * Every editable field of a structure, in the order the editor shows them.
 *
 * The cell edges are here even though every one of them is a parameter — that is
 * the split working: `splitEdits` sends them to `set_values`, where a crystal
 * system's ties are enforced and a refused edge names the edge it follows.  A
 * form that "knew" which edges are tied would be a second copy of the crystal
 * systems.
 */
export function structureFields(structure: any): Field[] {
  const out: Field[] = [];
  (structure?.phases ?? []).forEach((phase: any, i: number) => {
    out.push({ path: `phases.${i}.name`, label: "phase", kind: "text" });
    for (const edge of ["a", "b", "c"]) {
      out.push({ path: `phases.${i}.cell.${edge}`, label: edge, kind: "number",
                 unit: "Å" });
    }
    for (const angle of ["alpha", "beta", "gamma"]) {
      out.push({ path: `phases.${i}.cell.${angle}`, label: angle, kind: "number",
                 unit: "°" });
    }
    out.push({ path: `phases.${i}.scale`, label: "scale", kind: "number" });
    (phase.atoms ?? []).forEach((_: unknown, j: number) => {
      out.push(...atomFields(i, j), ...atomParamFields(i, j));
    });
  });
  return out;
}

/** The atom fields this editor types directly — the ones that are not in θ. */
export function atomFields(phase: number, index: number): Field[] {
  return [
    { path: `phases.${phase}.atoms.${index}.label`, label: "label", kind: "text" },
    { path: `phases.${phase}.atoms.${index}.species`, label: "species", kind: "text",
      title: "scattering species — an ion falls back to the neutral atom" },
  ];
}

/** …and the ones it types *through the parameter table*. */
export function atomParamFields(phase: number, index: number): Field[] {
  return [
    { path: `phases.${phase}.atoms.${index}.occ`, label: "occ", kind: "number" },
    { path: `phases.${phase}.atoms.${index}.biso`, label: "Biso", kind: "number",
      unit: "Å²" },
  ];
}

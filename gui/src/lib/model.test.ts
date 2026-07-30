/**
 * The model editor's logic — and above all the split it rests on.
 *
 * `splitEdits` is where this panel decides whether an edit is the parameter
 * table's business or the model's, and getting it wrong is not cosmetic in
 * either direction: a cell edge sent as a whole-model PATCH would write past its
 * crystal-system tie, and a species sent to `set_values` would be a number that
 * is not one. Membership in `GET /api/params` is the whole test, which is why
 * these cases are built from rows rather than from a list of field names.
 */
import { describe, expect, it } from "vitest";

import {
  applyFields,
  atomRows,
  axialWarning,
  editableValue,
  fieldText,
  instrumentFields,
  newAtom,
  paramPath,
  readValue,
  renderField,
  splitEdits,
  validateField,
  withAtom,
  withoutAtom,
  type Field,
  type Site,
} from "./model";
import { normalize, type ParamRow } from "./table";

function row(path: string, extra: Partial<ParamRow> = {}): ParamRow {
  return normalize([{
    path, value: 1, vary: false, lo: "-Infinity", hi: "Infinity",
    transform: "identity", tie: null, locked: false, esd: null,
    mode_fixed: false, refinable: true, held_because: "", ...extra,
  }])[0];
}

function instrument(): any {
  return {
    zero_shift: { value: 0.01, vary: false },
    source: {
      polarization: { value: 0.5, vary: false },
      lines: [{ wavelength: 1.5405929, weight: { value: 1, vary: false } },
              { wavelength: 1.5444274, weight: { value: 0.5, vary: false } }],
    },
    profile: { shape: "tchz_pv", u: { value: 0.002, vary: false },
               v: { value: 0, vary: false }, w: { value: 0.004, vary: false },
               x: { value: 0, vary: false }, y: { value: 0, vary: false } },
    geometry: { kind: "bragg_brentano", goniometer_radius_mm: 217.5,
                sample_displacement: { value: 0, vary: false },
                sample_transparency: { value: 0, vary: false },
                axial_sl: { value: 0.002, vary: false },
                axial_hl: { value: 0.002, vary: false },
                mu_t: null, thickness_mm: null },
    background: { kind: "chebyshev", coefficients: [{ value: 1 }, { value: 0 }] },
  };
}

function structure(): any {
  return {
    phases: [{
      name: "LaB6", space_group: "P m -3 m",
      cell: { a: { value: 4.1566 }, b: { value: 4.1566 }, c: { value: 4.1566 },
              alpha: { value: 90 }, beta: { value: 90 }, gamma: { value: 90 } },
      atoms: [
        { label: "La", species: "La", x: { value: 0 }, y: { value: 0 },
          z: { value: 0 }, occ: { value: 1 }, biso: { value: 0.5 }, aniso: null },
        { label: "B", species: "B", x: { value: 0.1993 }, y: { value: 0.5 },
          z: { value: 0.5 }, occ: { value: 1 }, biso: { value: 0.4 }, aniso: null },
      ],
    }],
  };
}

const SITES: Site[] = [
  { path: "phases.0.atoms.0", phase: 0, atom: 0, site_symmetry_order: 48,
    special: true, dof_paths: [], dof_directions: [], adp_paths: [],
    adp_patterns: [[1, 1, 1, 0, 0, 0]], aniso: false },
  { path: "phases.0.atoms.1", phase: 0, atom: 1, site_symmetry_order: 8,
    special: true, dof_paths: ["phases.0.atoms.1.dof.0"],
    dof_directions: [[1, 0, 0]], adp_paths: [], adp_patterns: [], aniso: false },
];

describe("reading a field", () => {
  it("unwraps a Parameter and leaves a plain value alone", () => {
    const ins = instrument();
    expect(readValue(ins, "profile.u")).toBe(0.002);
    expect(readValue(ins, "geometry.kind")).toBe("bragg_brentano");
    expect(readValue(ins, "source.lines.1.wavelength")).toBe(1.5444274);
  });

  it("renders an absent optional as empty rather than as zero", () => {
    // µt absent is the thick-specimen case; µt = 0 is a specimen of no
    // thickness, which raises — so these must not render alike
    const field: Field = { path: "geometry.mu_t", label: "µt", kind: "optnumber" };
    expect(renderField(instrument(), field)).toBe("");
    const declared = instrument();
    declared.geometry.mu_t = 0.5;
    expect(renderField(declared, field)).toBe("0.5");
  });
});

describe("validateField", () => {
  const number: Field = { path: "profile.u", label: "U", kind: "number" };
  const optional: Field = { path: "geometry.mu_t", label: "µt", kind: "optnumber" };
  const choice: Field = { path: "geometry.kind", label: "geometry", kind: "choice",
                          choices: ["debye_scherrer", "bragg_brentano"] };
  const text: Field = { path: "phases.0.atoms.0.species", label: "species",
                        kind: "text" };

  it("refuses what the server would refuse, and allows an empty optional", () => {
    expect(validateField(number, "")).toBe("not a number");
    expect(validateField(number, "wide")).toBe("not a number");
    expect(validateField(number, "-0.5")).toBe("");
    expect(validateField(optional, "  ")).toBe("");
    expect(validateField(choice, "kappa")).toMatch(/not one of/);
    expect(validateField(choice, "debye_scherrer")).toBe("");
    expect(validateField(text, " ")).toBe("cannot be empty");
  });
});

describe("splitEdits — the parameter table owns what it has", () => {
  const fields = instrumentFields(instrument());

  it("routes a Parameter through set_values, with the instrument prefix", () => {
    const rows = [row("instrument.profile.u"), row("instrument.zero_shift")];
    const delta = splitEdits(instrument(), fields,
                             new Map([["profile.u", "0.005"]]), rows, "instrument");
    expect(delta.values).toEqual({ "instrument.profile.u": 0.005 });
    expect(delta.fields).toEqual([]);
    expect(delta.touched).toBe(1);
  });

  it("routes a geometry declaration through the model patch", () => {
    const rows = [row("instrument.profile.u")];
    const delta = splitEdits(instrument(), fields,
                             new Map([["geometry.kind", "debye_scherrer"],
                                      ["geometry.goniometer_radius_mm", "240"]]),
                             rows, "instrument");
    expect(delta.values).toEqual({});
    expect(delta.fields.map((f) => f.path))
      .toEqual(["geometry.kind", "geometry.goniometer_radius_mm"]);
  });

  it("sends a cell edge to set_values even though it is tied", () => {
    // the refusal is the verb's own ("follows … as an affine tie"), and it must
    // reach the user rather than be pre-empted by writing past the tie here
    const rows = [row("phases.0.cell.a"),
                  row("phases.0.cell.b", { tie: { sources: ["phases.0.cell.a"] } })];
    const delta = splitEdits(structure(),
                             [{ path: "phases.0.cell.b", label: "b", kind: "number" }],
                             new Map([["phases.0.cell.b", "4.2"]]), rows, "structure");
    expect(delta.values).toEqual({ "phases.0.cell.b": 4.2 });
  });

  it("ignores a cell clicked into and out of again", () => {
    const rows = [row("instrument.profile.u", { value: 0.002 })];
    const delta = splitEdits(instrument(), fields,
                             new Map([["profile.u", "0.002"]]), rows, "instrument");
    expect(delta.values).toEqual({});
    expect(delta.touched).toBe(0);
  });

  it("compares against the *rendered* value, esd and all", () => {
    // the cell shows `4.15678` for a parameter known to ±0.00019; comparing the
    // typed text against the stored float would make clicking in and out again a
    // `set_values` that truncates the parameter (WP-1011's trap)
    const rows = [row("phases.0.cell.a", { value: 4.1567812, esd: 0.00019 })];
    const fields: Field[] = [{ path: "phases.0.cell.a", label: "a", kind: "number" }];
    const shown = fieldText(structure(), fields[0], new Map(rows.map((r) => [r.path, r])),
                            "structure");
    expect(shown).toBe("4.1568");
    expect(splitEdits(structure(), fields, new Map([["phases.0.cell.a", shown]]),
                      rows, "structure").values).toEqual({});
    expect(splitEdits(structure(), fields, new Map([["phases.0.cell.a", "4.2"]]),
                      rows, "structure").values).toEqual({ "phases.0.cell.a": 4.2 });
  });

  it("falls back to the model for a field the table does not have", () => {
    const field: Field = { path: "geometry.goniometer_radius_mm", label: "r",
                           kind: "number" };
    expect(fieldText(instrument(), field, new Map(), "instrument")).toBe("217.5");
  });

  it("collects an unsendable value instead of sending it", () => {
    const delta = splitEdits(instrument(), fields,
                             new Map([["profile.u", "big"]]), [], "instrument");
    expect(delta.invalid).toEqual([{ path: "profile.u", why: "not a number" }]);
    expect(delta.values).toEqual({});
  });

  it("prefixes only the instrument's paths", () => {
    expect(paramPath("instrument", "profile.u")).toBe("instrument.profile.u");
    expect(paramPath("structure", "phases.0.cell.a")).toBe("phases.0.cell.a");
  });
});

describe("applyFields", () => {
  it("writes into a copy, through a Parameter to its value", () => {
    const before = instrument();
    const next = applyFields(before, [
      { path: "geometry.kind", label: "", kind: "choice", choices: ["debye_scherrer"] },
      { path: "profile.u", label: "", kind: "number" },
      { path: "geometry.mu_t", label: "", kind: "optnumber" },
    ], new Map([["geometry.kind", "debye_scherrer"], ["profile.u", "0.01"],
                ["geometry.mu_t", ""]]));
    expect(next.geometry.kind).toBe("debye_scherrer");
    expect(next.profile.u.value).toBe(0.01);
    expect(next.geometry.mu_t).toBeNull();
    expect(before.geometry.kind).toBe("bragg_brentano");   // untouched
  });
});

describe("the instrument form follows the geometry it is editing", () => {
  it("offers µR to a capillary and µt to a flat plate, never both", () => {
    const capillary = instrument();
    capillary.geometry.kind = "debye_scherrer";
    const paths = (model: any) => instrumentFields(model).map((f) => f.path);
    expect(paths(capillary)).toContain("geometry.mu_r");
    expect(paths(capillary)).not.toContain("geometry.mu_t");
    expect(paths(instrument())).toContain("geometry.mu_t");
    expect(paths(instrument())).not.toContain("geometry.mu_r");
  });

  it("offers one row per emission line, and no weight for the locked first", () => {
    const paths = instrumentFields(instrument()).map((f) => f.path);
    expect(paths).toContain("source.lines.0.wavelength");
    expect(paths).toContain("source.lines.1.weight");
    expect(paths).not.toContain("source.lines.0.weight");
  });
});

describe("axialWarning", () => {
  it("fires on the FCJ corner, and says when one of the pair is free", () => {
    const ins = instrument();
    expect(axialWarning(ins)).toMatch(/corner/);
    expect(axialWarning(ins)).not.toMatch(/at least one is free/);
    ins.geometry.axial_sl.vary = true;
    expect(axialWarning(ins)).toMatch(/at least one is free/);
    ins.geometry.axial_hl.value = 0.003;
    expect(axialWarning(ins)).toBe("");
  });

  it("says nothing about the equal pair that is not a hazard", () => {
    // both zero and both held is axial divergence *off*, which is every freshly
    // created lab instrument — warning there would be warning nobody reads
    const ins = instrument();
    ins.geometry.axial_sl.value = ins.geometry.axial_hl.value = 0;
    expect(axialWarning(ins)).toBe("");
    ins.geometry.axial_hl.vary = true;      // …but freeing one makes it live
    expect(axialWarning(ins)).toMatch(/corner/);
  });
});

describe("editableValue", () => {
  it("is the two refusals set_values makes, and not the third", () => {
    expect(editableValue(row("phases.0.cell.a"))).toBe(true);
    expect(editableValue(row("x", { locked: true }))).toBe(false);
    expect(editableValue(row("x", { tie: { sources: ["a"] } }))).toBe(false);
    // a mode-fixed row can still be *set*; it simply will not be varied
    expect(editableValue(row("x", { mode_fixed: true }))).toBe(true);
    expect(editableValue(undefined)).toBe(true);
  });
});

describe("atomRows", () => {
  const rows = [row("phases.0.atoms.1.dof.0"), row("phases.0.atoms.0.biso"),
                row("phases.0.atoms.1.biso")];

  it("gives a fixed special position no coordinate control and a reason", () => {
    const [la, b] = atomRows(structure(), SITES, rows);
    expect(la.dofs).toEqual([]);
    expect(la.frozen).toMatch(/fully fixed special position/);
    expect(la.frozen).toContain("48");
    expect(b.frozen).toBe("");
    expect(b.dofs.map((r) => r.path)).toEqual(["phases.0.atoms.1.dof.0"]);
    expect(b.xyz).toEqual([0.1993, 0.5, 0.5]);
  });

  it("survives a site arm that has not caught up with an added atom", () => {
    const grown = withAtom(structure(), 0, newAtom("O1", "O", [0.25, 0.25, 0.25]));
    const [, , added] = atomRows(grown, SITES, rows);
    expect(added.site).toBeNull();
    expect(added.dofs).toEqual([]);
    expect(added.frozen).toBe("");
  });
});

describe("adding and removing an atom", () => {
  it("returns a new structure and leaves the old one alone", () => {
    const before = structure();
    const grown = withAtom(before, 0, newAtom("O1", "O"));
    expect(grown.phases[0].atoms).toHaveLength(3);
    expect(before.phases[0].atoms).toHaveLength(2);
    expect(grown.phases[0].atoms[2].species).toBe("O");
    const shrunk = withoutAtom(grown, 0, 0);
    expect(shrunk.phases[0].atoms.map((a: any) => a.label)).toEqual(["B", "O1"]);
  });

  it("places a new atom where it was asked for, since that decides its DOFs", () => {
    const atom = newAtom("O1", "O", [0.25, 0.5, 0]);
    expect([atom.x.value, atom.y.value, atom.z.value]).toEqual([0.25, 0.5, 0]);
    expect(atom.occ.value).toBe(1);
  });
});

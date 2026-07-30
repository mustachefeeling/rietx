/**
 * The structure viewer's arithmetic (WP-1015).
 *
 * There is deliberately no crystallography to test here — the orbit, the
 * metric, the eigen-decomposition and the bond rule are all in
 * `src/pxrdref/gui/structure3d.py` and asserted in `tests/test_structure3d.py`.
 * What *is* here is the part that can silently draw the right numbers wrongly:
 * the matrix-vector convention (the payload's 3×3 has the principal axes as
 * **columns**, so transposing it would rotate every ellipsoid to a plausible
 * but wrong orientation), a mesh whose face indices must be offset per atom, and
 * a polyline whose nulls are what keep bonds from being joined end to end.
 */
import { describe, expect, it } from "vitest";

import {
  DEFAULT_CAMERA,
  atomLabel,
  atomTransform,
  atomTraces,
  axisTrace,
  bondTrace,
  caption,
  cellTrace,
  layout,
  legend,
  traces,
  transform,
  unitSphere,
  type Geometry,
  type Site,
} from "./structure3d";

function site(extra: Partial<Site> = {}): Site {
  return {
    index: 0, path: "phases.0.atoms.0", label: "La", species: "La",
    element: "La", color: "#aabbcc", radius: 2.0, metal: true, occ: 1,
    biso: 0.5, u_iso: 0.006, aniso: false, multiplicity: 1, special: true,
    npd: false, ...extra,
  };
}

/** Two sites, three drawn atoms, one bond — small enough to count by hand. */
function geometry(extra: Partial<Geometry> = {}): Geometry {
  return {
    phase: 0, phases: ["cubic"], name: "cubic", space_group: "P m -3 m",
    cell: [4, 4, 4, 90, 90, 90], volume: 64,
    lattice: [[4, 0, 0], [0, 4, 0], [0, 0, 4]],
    corners: [[0, 0, 0], [4, 0, 0], [0, 4, 0], [4, 4, 0],
              [0, 0, 4], [4, 0, 4], [0, 4, 4], [4, 4, 4]],
    edges: [[0, 1], [2, 3], [4, 5], [6, 7], [0, 2], [1, 3],
            [4, 6], [5, 7], [0, 4], [1, 5], [2, 6], [3, 7]],
    sites: [site(), site({ index: 1, path: "phases.0.atoms.1", label: "B",
                           species: "B", element: "B", color: "#e0a080",
                           radius: 0.84, metal: false, multiplicity: 2,
                           aniso: true })],
    atoms: [
      { site: 0, frac: [0, 0, 0], pos: [0, 0, 0], boundary: false,
        ellipsoid: [[0.1, 0, 0], [0, 0.1, 0], [0, 0, 0.1]],
        rms: [0.1, 0.1, 0.1], npd: false },
      { site: 0, frac: [1, 0, 0], pos: [4, 0, 0], boundary: true,
        ellipsoid: [[0.1, 0, 0], [0, 0.1, 0], [0, 0, 0.1]],
        rms: [0.1, 0.1, 0.1], npd: false },
      { site: 1, frac: [0.5, 0.5, 0.2], pos: [2, 2, 0.8], boundary: false,
        // deliberately not symmetric: a transpose would go unnoticed otherwise
        ellipsoid: [[0.2, 0, 0], [0, 0.1, 0], [0.05, 0, 0.1]],
        rms: [0.1, 0.1, 0.2], npd: false },
    ],
    bonds: [{ i: 0, j: 2, a: [0, 0, 0], b: [2, 2, 0.8], d: 3.0 }],
    probability: 0.5, probability_levels: { "0.5": 1.5382, "0.9": 2.5003 },
    scale: 1.5382, ball_fraction: 0.32, bond_tolerance: 1.15,
    bond_metals: false, note: "", ...extra,
  };
}

describe("the unit sphere", () => {
  it("closes: every edge is shared by exactly two triangles", () => {
    const { vertices, faces } = unitSphere(6, 10);
    // Euler for a closed triangulated sphere: V − E + F = 2, with 3F = 2E
    expect(vertices.length).toBe(2 + 5 * 10);
    expect(faces.length).toBe(2 * 10 + 4 * 10 * 2);
    expect(vertices.length - (3 * faces.length) / 2 + faces.length).toBe(2);
  });

  it("is a unit sphere", () => {
    for (const v of unitSphere(8, 16).vertices) {
      expect(Math.hypot(v[0], v[1], v[2])).toBeCloseTo(1, 12);
    }
  });

  it("indexes no vertex it does not have", () => {
    const { vertices, faces } = unitSphere(5, 7);
    for (const face of faces) {
      for (const index of face) {
        expect(index).toBeGreaterThanOrEqual(0);
        expect(index).toBeLessThan(vertices.length);
      }
    }
  });
});

describe("the transform", () => {
  it("reads the matrix by rows, so the payload's columns stay the axes", () => {
    // the payload's convention: column k is the k-th principal axis, so the
    // matrix below must send x̂ to (1, 0, 2) — a transposed reading sends it to
    // (1, 0, 0) and every anisotropic ellipsoid is silently mis-oriented
    const m = [[1, 0, 0], [0, 1, 0], [2, 0, 1]];
    expect(transform(m, [1, 0, 0])).toEqual([1, 0, 2]);
    expect(transform(m, [0, 0, 1])).toEqual([0, 0, 1]);
  });

  it("scales the ellipsoid by k(p) and the ball by the covalent radius", () => {
    const geo = geometry();
    const ellipsoid = atomTransform(geo, geo.atoms[2], "ellipsoid");
    expect(ellipsoid[2][0]).toBeCloseTo(0.05 * 1.5382, 12);
    const ball = atomTransform(geo, geo.atoms[2], "ball");
    expect(ball).toEqual([[0.32 * 0.84, 0, 0], [0, 0.32 * 0.84, 0],
                          [0, 0, 0.32 * 0.84]]);
  });

  it("draws an anisotropic site as a ball in ball mode", () => {
    // the two modes answer different questions; a ball-and-stick that quietly
    // showed thermal motion would make the toggle mean nothing
    const geo = geometry();
    const ball = atomTransform(geo, geo.atoms[2], "ball");
    expect(ball[0][0]).toBe(ball[1][1]);
    expect(ball[2][0]).toBe(0);
  });
});

describe("the traces", () => {
  it("groups atoms into one mesh per species, with per-atom face offsets", () => {
    const geo = geometry();
    const sphere = unitSphere(4, 6);
    const meshes = atomTraces(geo, "ball", sphere);
    expect(meshes.map((m) => m.name)).toEqual(["La", "B"]);
    // La is drawn twice (the corner and its boundary image), B once
    expect(meshes[0].x.length).toBe(2 * sphere.vertices.length);
    expect(meshes[1].x.length).toBe(sphere.vertices.length);
    expect(meshes[0].i.length).toBe(2 * sphere.faces.length);
    // the second atom's faces must point into the second atom's vertices
    const second = meshes[0].i.slice(sphere.faces.length);
    expect(Math.min(...second)).toBeGreaterThanOrEqual(sphere.vertices.length);
    expect(Math.max(...meshes[0].i)).toBeLessThan(meshes[0].x.length);
  });

  it("puts each atom's own hover text on each of its vertices", () => {
    const meshes = atomTraces(geometry(), "ellipsoid", unitSphere(4, 6));
    expect(new Set(meshes[0].text).size).toBe(2);   // corner and boundary image
    expect(meshes[0].text[0]).toContain("La (La)");
    expect(meshes[1].text[0]).toContain("RMS");
  });

  it("hides the species the legend switched off, and the boundary images", () => {
    const geo = geometry();
    const sphere = unitSphere(4, 6);
    expect(atomTraces(geo, "ball", sphere, new Set(["La"])).map((m) => m.name))
      .toEqual(["B"]);
    const inner = atomTraces(geo, "ball", sphere, new Set(), false);
    expect(inner[0].x.length).toBe(sphere.vertices.length);   // one La, not two
  });

  it("breaks the bond and cell polylines with nulls", () => {
    const geo = geometry();
    const bonds = bondTrace(geo, "#888");
    expect(bonds.x).toEqual([0, 2, null]);
    expect(bonds.text[0]).toContain("La–B");
    expect(bonds.text[0]).toContain("3.000 Å");

    const cell = cellTrace(geo, "#ccc");
    expect(cell.x.length).toBe(12 * 3);
    // exactly one null per edge: without them plotly joins edge to edge and
    // draws a scribble that reads as a cell
    expect(cell.x.filter((v: number | null) => v === null).length).toBe(12);
  });

  it("draws the cell behind the bonds behind the atoms", () => {
    const all = traces(geometry(), "ball", unitSphere(4, 6),
                       { cell: "#ccc", bond: "#888" });
    expect(all.map((t) => t.name)).toEqual(["cell", "axes", "bonds", "La", "B"]);
  });

  it("labels the cell's own axes, clear of the corner atoms", () => {
    // the frame of reference is a, b, c — nothing here happens in x, y, z —
    // and a letter placed exactly on the corner would be inside the corner atom
    const axes = axisTrace(geometry(), "#1f5fa8");
    expect(axes.text).toEqual(["a", "b", "c"]);
    expect(axes.x).toEqual([4 * 1.08, 0, 0]);
    expect(axes.y).toEqual([0, 4 * 1.08, 0]);
    expect(axes.z).toEqual([0, 0, 4 * 1.08]);
  });
});

describe("the legend", () => {
  it("merges the sites that share a species and keeps declaration order", () => {
    const geo = geometry({
      sites: [site({ index: 0, label: "F1", species: "F1-", element: "F",
                     color: "#48d860" }),
              site({ index: 1, label: "Ca1", species: "Ca2+", element: "Ca",
                     color: "#40c060" }),
              site({ index: 2, label: "F2", species: "F1-", element: "F",
                     color: "#48d860" })],
      atoms: [], bonds: [],
    });
    const entries = legend(geo);
    expect(entries.map((e) => e.species)).toEqual(["F1-", "Ca2+"]);
    expect(entries[0].sites.map((s) => s.label)).toEqual(["F1", "F2"]);
  });
});

describe("the caption and the layout", () => {
  it("says what is drawn and at which thresholds", () => {
    const text = caption(geometry(), "ellipsoid");
    expect(text).toContain("2 atoms in the cell");
    expect(text).toContain("+ 1 image outside it");
    expect(text).toContain("1 bond segment at 1.15×");
    expect(text).toContain("metal–metal contacts not bonded");
    expect(text).toContain("ellipsoids at 50 %");
    expect(caption(geometry(), "ball")).toContain("0.32× the covalent radius");
  });

  it("marks an image whose tensor is not positive definite", () => {
    const geo = geometry();
    geo.atoms[2].npd = true;
    expect(atomLabel(geo, geo.atoms[2], "ellipsoid"))
      .toContain("not positive definite");
    // …and only in the mode that draws it
    expect(atomLabel(geo, geo.atoms[2], "ball")).not.toContain("positive");
  });

  it("keeps one Å the same length on all three axes", () => {
    // without `aspectmode: "data"` plotly stretches the box to a cube, which
    // draws a monoclinic cell as an orthogonal one — the whole content of the
    // picture for a low-symmetry phase.  It is also what makes `axisCamera`
    // legal: the data→scene map is then a uniform scale.
    expect(layout("#111").scene.aspectmode).toBe("data");
    expect(layout("#111").uirevision).toBe("structure3d");
  });

  it("draws a crystal, not a plot: parallel projection, no Cartesian box", () => {
    const scene = layout("#111").scene;
    // perspective converges the far edges of the cell, so a cubic cell does not
    // look cubic; every crystallographic figure is a parallel projection
    expect(scene.camera.projection.type).toBe("orthographic");
    // turntable pins `up` to +z and rewrites any camera that disagrees — and
    // `cartesian_basis` is upper triangular, so c ∥ ẑ for every orthogonal cell
    // and "view down c" would be a degenerate lookAt
    expect(scene.dragmode).toBe("orbit");
    for (const key of ["xaxis", "yaxis", "zaxis"]) {
      expect(scene[key].visible).toBe(false);
    }
  });

  it("takes the camera from its caller, defaulting to the opening view", () => {
    // The caller owns it because plotly does not keep it: every redraw here
    // builds new trace objects, and replacing a `mesh3d` rebuilds the gl3d
    // scene from the layout.  Isolated in a browser and measured by comparing
    // screenshots — reading `layout.scene.camera` back reports whatever was
    // last passed *in*, so it says a rotation was preserved when it was not.
    expect(layout("#111").scene.camera).toEqual(DEFAULT_CAMERA);
    const held = { eye: { x: 0.2, y: 2.1, z: 0.4 } };
    // by identity: merging anything into the caller's camera here — the
    // projection included — would be a second authority on the view
    expect(layout("#111", held).scene.camera).toBe(held);
    expect(layout("#111").scene.uirevision).toBe("structure3d");
  });
});

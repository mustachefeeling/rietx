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
  LIGHTING,
  LIGHT_POSITION,
  STICK_FLOOR,
  STICK_RADIUS,
  atomLabel,
  atomTransform,
  atomTraces,
  axisCamera,
  axisTrace,
  bondTraces,
  caption,
  cellTrace,
  dim,
  layout,
  legend,
  stickRadius,
  stickTransform,
  traces,
  transform,
  unitCylinder,
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
    scale: 1.5382, ball_fraction: 0.40, bond_tolerance: 1.15,
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

describe("the unit cylinder", () => {
  it("is a tube of unit radius running z = 0 to z = 1", () => {
    const { vertices, faces } = unitCylinder(6);
    expect(vertices.length).toBe(12);
    expect(faces.length).toBe(12);        // two triangles per segment
    for (const v of vertices) {
      expect(Math.hypot(v[0], v[1])).toBeCloseTo(1, 12);
      expect(v[2] === 0 || v[2] === 1).toBe(true);
    }
    for (const face of faces) {
      for (const index of face) expect(index).toBeLessThan(vertices.length);
    }
  });

  it("wraps: the last segment closes onto the first", () => {
    const { faces } = unitCylinder(5);
    expect(faces[faces.length - 1].some((i) => i < 2)).toBe(true);
  });
});

describe("the stick transform", () => {
  it("sends the cylinder's axis to the segment and its rim to the radius", () => {
    const t = stickTransform([1, 0, 0], [1, 0, 3], 0.08);
    // z spans the segment itself…
    expect(transform(t, [0, 0, 1])).toEqual([0, 0, 3]);
    // …and x̂, ŷ are perpendicular to it, at exactly the radius
    for (const v of [[1, 0, 0], [0, 1, 0]]) {
      const p = transform(t, v);
      expect(Math.hypot(p[0], p[1], p[2])).toBeCloseTo(0.08, 12);
      expect(p[2]).toBeCloseTo(0, 12);
    }
  });

  it("does not degenerate for a bond along any axis", () => {
    // a chain along c is the common case, not the rare one, and a perpendicular
    // built against a fixed ẑ would be a zero cross product — i.e. a NaN tube
    for (const to of [[1, 0, 0], [0, 1, 0], [0, 0, 1], [1, 1, 1]]) {
      const t = stickTransform([0, 0, 0], to, 0.1);
      for (const row of t) for (const value of row) expect(value).not.toBeNaN();
      const u = transform(t, [1, 0, 0]);
      const dot = u[0] * to[0] + u[1] * to[1] + u[2] * to[2];
      expect(dot).toBeCloseTo(0, 12);
      expect(Math.hypot(u[0], u[1], u[2])).toBeCloseTo(0.1, 12);
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
    expect(ball).toEqual([[0.40 * 0.84, 0, 0], [0, 0.40 * 0.84, 0],
                          [0, 0, 0.40 * 0.84]]);
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
  it("groups atoms per species and per side of the cell wall, with face offsets", () => {
    const geo = geometry();
    const sphere = unitSphere(4, 6);
    const meshes = atomTraces(geo, "ball", sphere);
    // two buffers for La — one inside the cell, one for its boundary image,
    // which is drawn dimmer (WP-1029) — and one for B, which has no image
    expect(meshes.map((m) => m.name)).toEqual(["La", "La", "B"]);
    expect(meshes[1].color).toBe(dim(meshes[0].color));
    for (const mesh of meshes) {
      expect(mesh.x.length).toBe(sphere.vertices.length);
      expect(mesh.i.length).toBe(sphere.faces.length);
      expect(Math.max(...mesh.i)).toBeLessThan(mesh.x.length);
    }
  });

  it("puts each atom's own hover text on each of its vertices", () => {
    const meshes = atomTraces(geometry(), "ellipsoid", unitSphere(4, 6));
    expect(meshes[0].text[0]).toContain("La (La)");
    expect(meshes[1].text[0]).toContain("La (La)");   // the image, same atom
    expect(meshes[2].text[0]).toContain("RMS");
  });

  it("hides the species the legend switched off, and the boundary images", () => {
    const geo = geometry();
    const sphere = unitSphere(4, 6);
    expect(atomTraces(geo, "ball", sphere, new Set(["La"])).map((m) => m.name))
      .toEqual(["B"]);
    const inner = atomTraces(geo, "ball", sphere, new Set(), false);
    expect(inner[0].x.length).toBe(sphere.vertices.length);   // one La, not two
  });

  it("lights every mesh with the one fixed screen-space key", () => {
    // plotly's `lightposition` is read in the *projection's* frame, not the
    // data's (measured on plotly.js 3.7.0 — WP-1029's reopened log), so a
    // fixed value follows the camera by construction and there is nothing to
    // recompute per draw.  Two facts are worth pinning because each was
    // shipped wrong once: z must not be positive — a z-dominant light sits
    // behind the scene and the whole visible side renders ambient-flat, which
    // is what "desaturated, dark and flat" was — and the ambient floor is what
    // keeps the unlit side of a sphere readable rather than near-black.
    expect(LIGHT_POSITION.z).toBeLessThanOrEqual(0);
    expect(LIGHTING.ambient).toBeGreaterThanOrEqual(0.5);
    const geo = geometry();
    const meshes = [...atomTraces(geo, "ball", unitSphere(4, 6)),
                    ...bondTraces(geo, unitCylinder(6))];
    for (const mesh of meshes) {
      // the same key and the same surface on every solid — the sticks and the
      // balls must not disagree about where the light is
      expect(mesh.lightposition).toEqual(LIGHT_POSITION);
      expect(mesh.lighting).toEqual(LIGHTING);
    }
  });

  it("sizes the stick for the mode it is drawn in", () => {
    const geo = geometry();
    // ball mode: the fixed radius, pinned below BALL_FRACTION on the smallest
    // covalent radius there is, so no species is a lump on a rod
    expect(stickRadius(geo, "ball")).toBe(STICK_RADIUS);

    // ellipsoid mode: an atom's size is √U·k(p) and has nothing to do with a
    // covalent radius, so the stick follows the smallest semi-axis drawn.  The
    // fixture's is 0.1 Å at k = 1.5382 → 0.1538, half of which is under the
    // fixed radius, so the stick thins rather than swallowing the atom.
    const thin = stickRadius(geo, "ellipsoid");
    expect(thin).toBeCloseTo(0.5 * 0.1 * 1.5382, 12);
    expect(thin).toBeLessThan(STICK_RADIUS);
    // the burial is a proof, not a hope: r ≤ ½·min semi-axis puts the rim
    // inside the ellipsoid's inscribed sphere, hence inside it in every
    // direction — which is what `unitCylinder` going uncapped now rests on
    expect(thin).toBeLessThanOrEqual(0.5 * 0.1 * geo.scale);

    // it never *grows* past the fixed radius, however big the exaggeration
    expect(stickRadius(geo, "ellipsoid", 8)).toBe(STICK_RADIUS);
    // …and never vanishes, however small
    expect(stickRadius(geo, "ellipsoid", 0.001)).toBe(STICK_FLOOR);
  });

  it("dims an image outside the cell rather than drawing it identically", () => {
    expect(dim("#ffffff", 0.5)).toBe("#808080");
    expect(dim("#48d860")).toBe("#2d863c");   // 0.62 of each channel, rounded
    expect(dim("not a colour")).toBe("not a colour");
  });

  it("breaks the cell polyline with nulls", () => {
    const cell = cellTrace(geometry(), "#ccc");
    expect(cell.x.length).toBe(12 * 3);
    // exactly one null per edge: without them plotly joins edge to edge and
    // draws a scribble that reads as a cell
    expect(cell.x.filter((v: number | null) => v === null).length).toBe(12);
  });

  it("splits a bond at its midpoint and colours each half by its own atom", () => {
    const geo = geometry();
    const tube = unitCylinder(6);
    const sticks = bondTraces(geo, tube);
    expect(sticks.map((t) => t.name)).toEqual(["bonds:La", "bonds:B"]);
    expect(sticks.map((t) => t.color)).toEqual(["#aabbcc", "#e0a080"]);
    // one half each, and both carry the whole bond's hover
    for (const half of sticks) {
      expect(half.x.length).toBe(tube.vertices.length);
      expect(half.i.length).toBe(tube.faces.length);
      expect(Math.max(...half.i)).toBeLessThan(half.x.length);
      expect(half.text[0]).toContain("La–B");
      expect(half.text[0]).toContain("3.000 Å");
    }
    // La's half runs from La's own position to the midpoint, and no further
    const mid = [1, 1, 0.4];
    for (const k of [0, 1, 2]) {
      const axis = [sticks[0].x, sticks[0].y, sticks[0].z][k];
      expect(Math.min(...axis)).toBeGreaterThanOrEqual(-0.09);
      expect(Math.max(...axis)).toBeLessThanOrEqual(mid[k] + 0.09);
    }
  });

  it("takes a species' half-sticks with it when the legend switches it off", () => {
    // a half belongs to its atom: hiding La and leaving its stub would be a
    // coloured spike ending in mid-air
    const sticks = bondTraces(geometry(), unitCylinder(6), new Set(["La"]));
    expect(sticks.map((t) => t.name)).toEqual(["bonds:B"]);
  });

  it("draws the cell behind the bonds behind the atoms", () => {
    const all = traces(geometry(), "ball", unitSphere(4, 6), unitCylinder(6),
                       "#ccc");
    expect(all.map((t) => t.name))
      .toEqual(["cell", "axes", "bonds:La", "bonds:B", "La", "La", "B"]);
  });

  it("labels the cell's own axes, clear of the corner atoms", () => {
    // The frame of reference is a, b, c — nothing here happens in x, y, z.  The
    // clearance is in Å and set by the largest ball, because a corner site is
    // drawn at all eight corners: a percentage of the edge put every letter
    // inside an atom on the first structure it was tried on.
    const axes = axisTrace(geometry(), "#1f5fa8");
    expect(axes.text).toEqual(["a", "b", "c"]);
    const clear = 0.35 + 0.4 * 2.0;               // the fixture's largest radius
    expect(axes.x).toEqual([4 + clear, 0, 0]);
    expect(axes.y).toEqual([0, 4 + clear, 0]);
    expect(axes.z).toEqual([0, 0, 4 + clear]);
    // …and it clears the ball itself, whatever the cell edge is
    const small = axisTrace(geometry({ cell: [1, 1, 1, 90, 90, 90],
                                       lattice: [[1, 0, 0], [0, 1, 0], [0, 0, 1]] }),
                            "#1f5fa8");
    expect(small.x[0] - 1).toBeGreaterThan(0.4 * 2.0);
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
    expect(caption(geometry(), "ball")).toContain("0.40× the covalent radius");
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

  it("looks down a lattice vector with the next one but one up", () => {
    // down a puts c up and b right, and so round: the three projections a
    // structure is normally drawn in
    const geo = geometry({
      // monoclinic, β = 110°, so `up` is genuinely not a lattice vector
      lattice: [[5, 0, 0], [0, 9, 0], [7 * Math.cos((110 * Math.PI) / 180), 0,
                                       7 * Math.sin((110 * Math.PI) / 180)]],
    });
    const down = axisCamera(geo, 0);
    expect(down.eye.y).toBeCloseTo(0, 12);
    expect(down.eye.z).toBeCloseTo(0, 12);
    expect(down.eye.x).toBeGreaterThan(0);
    // up is c, with the part along a taken out — an up parallel to the eye is a
    // singular lookAt, and in a triclinic cell no two axes are perpendicular
    const up = down.up!;
    expect(up.x * down.eye.x + up.y * down.eye.y + up.z * down.eye.z)
      .toBeCloseTo(0, 12);
    expect(Math.hypot(up.x, up.y, up.z)).toBeCloseTo(1, 12);
    expect(up.z).toBeGreaterThan(0);            // c's own side of the plane

    // the projection follows, and the distance is the caller's — so choosing a
    // view keeps whatever zoom the user had
    expect(down.projection).toEqual(DEFAULT_CAMERA.projection);
    const held = { eye: { x: 0, y: 0, z: 4 } };
    const eye = axisCamera(geo, 2, held).eye;
    expect(Math.hypot(eye.x, eye.y, eye.z)).toBeCloseTo(4, 12);
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

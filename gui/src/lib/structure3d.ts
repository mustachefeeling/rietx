/** The structure viewer's geometry, as pure functions (WP-1015).
 *
 * **No crystallography crosses the wire.**  `GET /api/structure3d` returns
 * Cartesian points in Å, 3×3 matrices and index pairs; everything here is the
 * arithmetic that turns those into plotly traces — a unit sphere pushed through
 * a matrix, a polyline broken by nulls, a legend grouped by species.  The
 * symmetry expansion, the metric, the eigen-decomposition and the bond rule are
 * all server-side, which is the same refusal WP-1010 made about decimation: two
 * answers to "where is this atom" is one more than a viewer may have.
 *
 * The one design fact worth stating here is why an ellipsoid is a **mesh** and a
 * ball is the same mesh.  Plotly's `scatter3d` markers are sized in *pixels*, so
 * a ball-and-stick drawn with them does not scale with zoom and cannot be
 * compared with the cell around it; `mesh3d` is in data coordinates, so one code
 * path — `pos + T·v` over a unit sphere — serves both modes and the only
 * difference between them is which `T` is used.  A ball is `f·r·I`, an
 * ellipsoid is `k(p)·T` from the payload, and neither the sphere nor the loop
 * knows which it is drawing.
 */

export interface Site {
  index: number;
  path: string;
  label: string;
  species: string;
  element: string;
  color: string;
  radius: number;
  metal: boolean;
  occ: number;
  biso: number;
  u_iso: number;
  aniso: boolean;
  multiplicity: number;
  special: boolean;
  npd: boolean;
}

export interface DrawnAtom {
  site: number;
  frac: number[];
  pos: number[];
  boundary: boolean;
  /** columns are the principal axes at one RMS displacement (Å) */
  ellipsoid: number[][];
  rms: number[];
  npd: boolean;
}

export interface Bond {
  i: number;
  j: number;
  a: number[];
  b: number[];
  d: number;
}

export interface Geometry {
  phase: number;
  phases: string[];
  name: string;
  space_group: string;
  cell: number[];
  volume: number;
  lattice: number[][];
  corners: number[][];
  edges: number[][];
  sites: Site[];
  atoms: DrawnAtom[];
  bonds: Bond[];
  probability: number;
  probability_levels: Record<string, number>;
  scale: number;
  ball_fraction: number;
  bond_tolerance: number;
  bond_metals: boolean;
  note: string;
}

export type Mode = "ball" | "ellipsoid";

/**
 * One surface for every solid in the scene — balls, ellipsoids and sticks — so
 * the three cannot drift apart.
 *
 * plotly's `lightposition` is a fixed point in **data** space, not a light that
 * follows the camera, and this component deliberately does not redraw while the
 * user drags: so whatever the far side of the scene looks like after a rotation
 * is what it looks like until something else redraws.  The answer is therefore a
 * surface that never needs the key light — mostly ambient, little diffuse — and
 * a specular low enough that 400 identical spheres do not read as a tray of
 * plastic beads.  The light itself sits over the opening view's shoulder rather
 * than at the equator, which is the most a static light can do.
 */
export const LIGHTING = {
  ambient: 0.75, diffuse: 0.55, specular: 0.08, roughness: 0.5, fresnel: 0.1,
};

export const LIGHT_POSITION = { x: 1e5, y: 1e5, z: 1e5 };

export interface Mesh {
  vertices: number[][];
  faces: number[][];
}

/**
 * A unit sphere as vertices and triangles — built once and reused for every atom.
 *
 * Latitude/longitude rather than a subdivided icosahedron: the triangles bunch
 * at the poles, which a subdivided icosahedron avoids, but at this resolution
 * the difference is invisible and the construction is one that can be read.
 *
 * Twelve rings by twenty-four is 266 vertices and 528 triangles per atom, so
 * the budget at `MAX_ATOMS` = 400 is 106 k vertices — an order below what plotly
 * ships in an isosurface, and comfortably inside 32-bit mesh indices.  Sixteen
 * segments left a 22.5° facet on every ball, which is what a sphere looks like
 * when it is a polygon.
 */
export function unitSphere(rings = 12, segments = 24): Mesh {
  const vertices: number[][] = [[0, 0, 1]];
  for (let r = 1; r < rings; r += 1) {
    const theta = (Math.PI * r) / rings;
    for (let s = 0; s < segments; s += 1) {
      const phi = (2 * Math.PI * s) / segments;
      vertices.push([Math.sin(theta) * Math.cos(phi),
                     Math.sin(theta) * Math.sin(phi),
                     Math.cos(theta)]);
    }
  }
  vertices.push([0, 0, -1]);
  const bottom = vertices.length - 1;
  const ring = (r: number, s: number) => 1 + (r - 1) * segments + (s % segments);

  const faces: number[][] = [];
  for (let s = 0; s < segments; s += 1) {
    faces.push([0, ring(1, s), ring(1, s + 1)]);
    faces.push([bottom, ring(rings - 1, s + 1), ring(rings - 1, s)]);
  }
  for (let r = 1; r < rings - 1; r += 1) {
    for (let s = 0; s < segments; s += 1) {
      const a = ring(r, s), b = ring(r, s + 1);
      const c = ring(r + 1, s), d = ring(r + 1, s + 1);
      faces.push([a, c, d], [a, d, b]);
    }
  }
  return { vertices, faces };
}

/**
 * A unit cylinder along +z: radius 1, from z = 0 to z = 1, **open at both ends**.
 *
 * Caps would be triangles nobody ever sees — the two halves of a bond butt
 * against each other at the midpoint, and the far end is buried inside its own
 * atom, whose ball is larger than the stick for every element there is.
 *
 * Six segments: a hexagonal prism with averaged normals is indistinguishable
 * from round at the three or four pixels a bond is ever drawn at, and the
 * budget is real — at `MAX_BONDS` this is 4000 × 2 halves × 24 vertices.
 */
export function unitCylinder(segments = 6): Mesh {
  const vertices: number[][] = [];
  for (let s = 0; s < segments; s += 1) {
    const phi = (2 * Math.PI * s) / segments;
    vertices.push([Math.cos(phi), Math.sin(phi), 0],
                  [Math.cos(phi), Math.sin(phi), 1]);
  }
  const faces: number[][] = [];
  for (let s = 0; s < segments; s += 1) {
    const a = 2 * s, b = a + 1;
    const c = (2 * s + 2) % (2 * segments), d = c + 1;
    faces.push([a, c, d], [a, d, b]);
  }
  return { vertices, faces };
}

function cross(a: number[], b: number[]): number[] {
  return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2],
          a[0] * b[1] - a[1] * b[0]];
}

/**
 * The 3×3 one half-stick is drawn through: columns `(r·u, r·v, w)`.
 *
 * The same convention `atomTransform` uses — columns are the axes — so a
 * cylinder goes through the *same* `transform()` a sphere does, and
 * `(cos φ, sin φ, t)` lands at `from + r·cos φ·u + r·sin φ·v + t·w`: a tube of
 * radius `r` running from `from` to `to`.  That is this module's one code path
 * earning its keep a second time.
 *
 * `u` is built against the coordinate axis the stick is *least* aligned with.  A
 * fixed choice like ẑ is exactly parallel for a bond down c — a chain along the
 * c axis is the common case, not the rare one — and the cross product would be
 * zero, which is a NaN tube.
 */
export function stickTransform(from: number[], to: number[],
                               radius: number): number[][] {
  const w = [to[0] - from[0], to[1] - from[1], to[2] - from[2]];
  const n = Math.hypot(w[0], w[1], w[2]) || 1;
  const d = [w[0] / n, w[1] / n, w[2] / n];
  const k = Math.abs(d[0]) <= Math.abs(d[1])
    ? (Math.abs(d[0]) <= Math.abs(d[2]) ? 0 : 2)
    : (Math.abs(d[1]) <= Math.abs(d[2]) ? 1 : 2);
  const pick = [0, 0, 0];
  pick[k] = 1;
  const raw = cross(d, pick);
  const length = Math.hypot(raw[0], raw[1], raw[2]) || 1;
  const u = raw.map((c) => c / length);
  const v = cross(d, u);        // unit, since d ⟂ u and both are unit
  return [[radius * u[0], radius * v[0], w[0]],
          [radius * u[1], radius * v[1], w[1]],
          [radius * u[2], radius * v[2], w[2]]];
}

/** `T·v` for a 3×3 whose **columns** are the axes — the payload's convention. */
export function transform(matrix: number[][], v: number[]): number[] {
  return [
    matrix[0][0] * v[0] + matrix[0][1] * v[1] + matrix[0][2] * v[2],
    matrix[1][0] * v[0] + matrix[1][1] * v[1] + matrix[1][2] * v[2],
    matrix[2][0] * v[0] + matrix[2][1] * v[1] + matrix[2][2] * v[2],
  ];
}

/** The matrix one atom's sphere is drawn through, in the given mode.
 *
 * `ball` is deliberately isotropic even for an anisotropic site: the two modes
 * answer different questions, and a ball-and-stick that quietly showed thermal
 * motion would make the ellipsoid toggle mean nothing.
 */
export function atomTransform(geometry: Geometry, atom: DrawnAtom,
                              mode: Mode): number[][] {
  if (mode === "ellipsoid") {
    const k = geometry.scale;
    return atom.ellipsoid.map((row) => row.map((value) => value * k));
  }
  const r = geometry.ball_fraction * geometry.sites[atom.site].radius;
  return [[r, 0, 0], [0, r, 0], [0, 0, r]];
}

/** One hover line per atom: what it is, where it is, and how it is displaced. */
export function atomLabel(geometry: Geometry, atom: DrawnAtom, mode: Mode): string {
  const site = geometry.sites[atom.site];
  const frac = atom.frac.map((v) => v.toFixed(4)).join(", ");
  const parts = [`${site.label} (${site.species})`, `(${frac})`];
  if (site.occ !== 1) parts.push(`occ ${site.occ.toFixed(3)}`);
  if (mode === "ellipsoid") {
    const rms = atom.rms.map((v) => v.toFixed(3)).join(" / ");
    parts.push(atom.npd ? `RMS ${rms} Å — not positive definite`
                        : `RMS ${rms} Å`);
  }
  if (atom.boundary) parts.push("image outside the cell");
  return parts.join("  ·  ");
}

/** Species → its legend entry, in the order the sites are declared. */
export function legend(geometry: Geometry): Array<{ species: string; color: string;
                                                    sites: Site[] }> {
  const out: Array<{ species: string; color: string; sites: Site[] }> = [];
  const seen = new Map<string, number>();
  for (const site of geometry.sites) {
    const at = seen.get(site.species);
    if (at === undefined) {
      seen.set(site.species, out.length);
      out.push({ species: site.species, color: site.color, sites: [site] });
    } else {
      out[at].sites.push(site);
    }
  }
  return out;
}

/**
 * One `mesh3d` per species — every atom of that species, in one vertex buffer.
 *
 * Per species rather than per atom because a trace is what plotly draws in one
 * call and what the legend toggles; a 90-atom cell would otherwise be 90 legend
 * entries and 90 draw calls for six distinct colours.  `hidden` is the set of
 * species the legend has switched off, applied here rather than through
 * plotly's own legend so it survives a redraw the same way every other bit of
 * state in this app does.
 */
export function atomTraces(geometry: Geometry, mode: Mode, sphere: Mesh,
                           hidden: ReadonlySet<string> = new Set(),
                           showBoundary = true): any[] {
  const traces: any[] = [];
  for (const entry of legend(geometry)) {
    if (hidden.has(entry.species)) continue;
    const indices = new Set(entry.sites.map((site) => site.index));
    const x: number[] = [], y: number[] = [], z: number[] = [];
    const i: number[] = [], j: number[] = [], k: number[] = [];
    const text: string[] = [];
    for (const atom of geometry.atoms) {
      if (!indices.has(atom.site)) continue;
      if (atom.boundary && !showBoundary) continue;
      const matrix = atomTransform(geometry, atom, mode);
      const label = atomLabel(geometry, atom, mode);
      const offset = x.length;
      for (const v of sphere.vertices) {
        const p = transform(matrix, v);
        x.push(atom.pos[0] + p[0]);
        y.push(atom.pos[1] + p[1]);
        z.push(atom.pos[2] + p[2]);
        text.push(label);
      }
      for (const face of sphere.faces) {
        i.push(offset + face[0]);
        j.push(offset + face[1]);
        k.push(offset + face[2]);
      }
    }
    if (!x.length) continue;
    traces.push({
      type: "mesh3d", name: entry.species, x, y, z, i, j, k, text,
      color: entry.color, flatshading: false, showlegend: false,
      lighting: LIGHTING, lightposition: LIGHT_POSITION,
      hovertemplate: "%{text}<extra></extra>",
    });
  }
  return traces;
}

/** Half a bond is 0.08 Å thick.
 *
 * These are *covalent* radii, which is what makes the number smaller than it
 * looks beside VESTA's: at `ball_fraction` even hydrogen (r = 0.31 Å) keeps a
 * ball wider than its own stick, so no species is drawn as a lump on a rod.
 */
export const STICK_RADIUS = 0.08;

/**
 * Bonds as two-tone cylinders, one `mesh3d` per species.
 *
 * A `scatter3d` line is sized in **pixels**, which is the objection the atoms
 * already answered: at any zoom but the one it was tuned for, a 4 px stick is a
 * hairline or a drainpipe, and it cannot be compared with the cell around it.
 * A cylinder is in Å like everything else in the picture.
 *
 * Split at the midpoint and coloured by the atom each half leaves — the
 * convention every other viewer uses, and the thing that makes a bond say which
 * two species it joins without a hover.  It also gives the legend a rule it did
 * not have: **a half belongs to its atom**, so switching a species off takes its
 * own halves with it rather than leaving coloured stubs in mid-air.
 */
export function bondTraces(geometry: Geometry, cylinder: Mesh,
                           hidden: ReadonlySet<string> = new Set()): any[] {
  const buckets = new Map<string, any>();
  for (const bond of geometry.bonds) {
    const mid = [0, 1, 2].map((k) => (bond.a[k] + bond.b[k]) / 2);
    const ends: Array<[number[], number]> = [[bond.a, bond.i], [bond.b, bond.j]];
    const label = `${geometry.sites[geometry.atoms[bond.i].site].label}–`
      + `${geometry.sites[geometry.atoms[bond.j].site].label}  ${bond.d.toFixed(3)} Å`;
    for (const [from, index] of ends) {
      const site = geometry.sites[geometry.atoms[index].site];
      if (hidden.has(site.species)) continue;
      let bucket = buckets.get(site.species);
      if (!bucket) {
        bucket = {
          type: "mesh3d", name: `bonds:${site.species}`,
          x: [], y: [], z: [], i: [], j: [], k: [], text: [],
          color: site.color, flatshading: false, showlegend: false,
          lighting: LIGHTING, lightposition: LIGHT_POSITION,
          hovertemplate: "%{text}<extra></extra>",
        };
        buckets.set(site.species, bucket);
      }
      const matrix = stickTransform(from, mid, STICK_RADIUS);
      const offset = bucket.x.length;
      for (const v of cylinder.vertices) {
        const p = transform(matrix, v);
        bucket.x.push(from[0] + p[0]);
        bucket.y.push(from[1] + p[1]);
        bucket.z.push(from[2] + p[2]);
        bucket.text.push(label);
      }
      for (const face of cylinder.faces) {
        bucket.i.push(offset + face[0]);
        bucket.j.push(offset + face[1]);
        bucket.k.push(offset + face[2]);
      }
    }
  }
  // legend order, so the trace list is the same one twice running
  return legend(geometry).map((entry) => buckets.get(entry.species))
    .filter((bucket) => bucket !== undefined);
}

/** The cell frame: the twelve edges the payload names, as one polyline. */
export function cellTrace(geometry: Geometry, color: string): any {
  const x: Array<number | null> = [], y: Array<number | null> = [];
  const z: Array<number | null> = [];
  for (const [a, b] of geometry.edges) {
    x.push(geometry.corners[a][0], geometry.corners[b][0], null);
    y.push(geometry.corners[a][1], geometry.corners[b][1], null);
    z.push(geometry.corners[a][2], geometry.corners[b][2], null);
  }
  return {
    type: "scatter3d", mode: "lines", name: "cell", x, y, z,
    line: { width: 2, color }, showlegend: false,
    hoverinfo: "skip",
  };
}

/**
 * "a", "b", "c" at the far end of the three cell edges leaving the origin.
 *
 * This is the scene's frame of reference, and it replaces plotly's Cartesian
 * box: nothing in the picture happens in x, y or z, and the box's tick labels
 * churn on every frame of a drag.  `lattice`'s rows *are* those three edges
 * (corner `1 << k` is `lattice[k]`), pushed 8 % past the corner because a corner
 * site is drawn at all eight corners and would otherwise swallow the letter.
 */
export function axisTrace(geometry: Geometry, color: string): any {
  const ends = [0, 1, 2].map((k) => geometry.lattice[k].map((v) => v * 1.08));
  return {
    type: "scatter3d", mode: "text", name: "axes",
    x: ends.map((p) => p[0]), y: ends.map((p) => p[1]), z: ends.map((p) => p[2]),
    text: ["a", "b", "c"], textposition: "middle center",
    textfont: { color, size: 12 }, showlegend: false, hoverinfo: "skip",
  };
}

/** Everything, in draw order: cell and its letters behind, sticks, then atoms. */
export function traces(geometry: Geometry, mode: Mode, sphere: Mesh,
                       cylinder: Mesh, cell: string,
                       hidden: ReadonlySet<string> = new Set(),
                       showBoundary = true): any[] {
  return [cellTrace(geometry, cell), axisTrace(geometry, cell),
          ...bondTraces(geometry, cylinder, hidden),
          ...atomTraces(geometry, mode, sphere, hidden, showBoundary)];
}

/** A camera in the scene's coordinates.  Typed rather than `any` so a wrong
 *  argument to `layout` is a `svelte-check` failure and not a silently
 *  perspective scene. */
export interface Camera {
  eye: { x: number; y: number; z: number };
  up?: { x: number; y: number; z: number };
  center?: { x: number; y: number; z: number };
  projection?: { type: "orthographic" | "perspective" };
}

/**
 * The opening view — down the body diagonal, so no axis is edge-on, and
 * **orthographic**.
 *
 * plotly's default is perspective, under which the far face of a cell is drawn
 * smaller than the near one and parallel edges converge: a cubic cell does not
 * look cubic, which is the one thing a picture of a cell is for.  Every
 * crystallographic figure is a parallel projection (VESTA calls it that and
 * offers both).  The projection must survive the component's camera capture —
 * changing it disposes and re-initialises the whole gl plot, so losing the field
 * would be a scene teardown per redraw rather than a cosmetic slip.
 */
export const DEFAULT_CAMERA: Camera = {
  eye: { x: 1.35, y: 1.35, z: 0.95 },
  up: { x: 0, y: 0, z: 1 },
  center: { x: 0, y: 0, z: 0 },
  projection: { type: "orthographic" },
};

/**
 * The camera looking straight down one lattice vector.
 *
 * `eye` is in the scene's coordinates rather than in Å — but under
 * `aspectmode: "data"` plotly's data→scene map is a *uniform* scale, so a
 * direction in Å is the same direction there.  That is the second job that
 * setting does, and it is what makes this function legal at all.
 *
 * `up` is the lattice vector two steps on cyclically: down **a** puts **c** up
 * and **b** right, down **b** puts **a** up and **c** right, down **c** puts
 * **b** up and **a** right, since `right = cross(−n, up)` on a right-handed
 * a, b, c.  Those are the three projections a crystallographer draws.  It is
 * Gram-Schmidted against the view direction because in a triclinic cell no two
 * lattice vectors are perpendicular, and an `up` parallel to the eye is a
 * singular `lookAt` — which is also why `layout` sets `dragmode: "orbit"`:
 * turntable would overwrite this `up` with +z, and c ∥ ẑ for every orthogonal
 * cell.
 *
 * The distance comes from the camera passed in, so choosing a projection keeps
 * whatever zoom the user had.
 */
export function axisCamera(geometry: Geometry, axis: number,
                           camera: Camera = DEFAULT_CAMERA): Camera {
  const unit = (v: number[]) => {
    const n = Math.hypot(v[0], v[1], v[2]) || 1;
    return [v[0] / n, v[1] / n, v[2] / n];
  };
  const n = unit(geometry.lattice[axis]);
  const raw = geometry.lattice[(axis + 2) % 3];
  const along = raw[0] * n[0] + raw[1] * n[1] + raw[2] * n[2];
  const up = unit([raw[0] - along * n[0], raw[1] - along * n[1],
                   raw[2] - along * n[2]]);
  const r = Math.hypot(camera.eye.x, camera.eye.y, camera.eye.z) || 2.06;
  return {
    eye: { x: n[0] * r, y: n[1] * r, z: n[2] * r },
    up: { x: up[0], y: up[1], z: up[2] },
    center: { x: 0, y: 0, z: 0 },
    projection: DEFAULT_CAMERA.projection,
  };
}

/**
 * The scene layout.
 *
 * `aspectmode: "data"` keeps one Å the same length on all three axes — without
 * it plotly stretches the box to a cube and a monoclinic cell is drawn as an
 * orthogonal one, which is the whole *content* of the picture for a
 * low-symmetry phase.  It does a second job that `axisCamera` depends on: the
 * data→scene map becomes a *uniform* scale, so a direction in Å is the same
 * direction in camera coordinates.
 *
 * **`dragmode: "orbit"` is load-bearing, not a preference.**  Turntable — which
 * is what gl3d picks when no `camera.up` is supplied, i.e. what this scene used
 * to be — pins `up` to +z and *rewrites* any camera that disagrees.  The
 * server's `cartesian_basis` is an upper-triangular Cholesky factor, so **c ∥ ẑ
 * for every orthogonal cell**, and "view down c" under turntable would put the
 * eye exactly on the up axis: a degenerate `lookAt`, i.e. a blank scene.  Orbit
 * is also how Jmol and VESTA rotate, and the a/b/c buttons are the cure for the
 * roll it allows.
 *
 * **The caller supplies the camera, and must supply the live one.**  This is the
 * part that took a screenshot comparison to establish, because plotly's stored
 * `layout.scene.camera` keeps saying whatever was *passed in* while the view is
 * somewhere else entirely — read it back and it reports a rotation as preserved
 * when it has been thrown away.  Isolated in the browser, three cases:
 * `Plots.resize` keeps the view; `react` with the *same* trace objects and a
 * fresh layout keeps it; `react` with **fresh trace objects** does not, because
 * replacing a `mesh3d` tears the gl3d scene down and rebuilds it from the layout.
 * Every redraw here builds new traces, so `uirevision` cannot save it and the
 * only durable answer is for the component to own the camera — captured from
 * `plotly_relayout` and handed back in — which is what
 * `panels/Structure3D.svelte` does.
 */
export function layout(fg: string, camera: Camera = DEFAULT_CAMERA): any {
  // No Cartesian box: `axisTrace` labels the frame of reference this picture
  // actually has.  `visible: false` takes plotly's wholesale branch — ticks,
  // labels, title, grid, zeroline and background off in one flag.
  const axis = { visible: false };
  return {
    margin: { l: 0, r: 0, t: 0, b: 0 },
    showlegend: false,
    font: { color: fg, size: 11 },
    paper_bgcolor: "rgba(0,0,0,0)",
    scene: {
      aspectmode: "data",
      dragmode: "orbit",
      xaxis: axis, yaxis: axis, zaxis: axis,
      camera,
      uirevision: "structure3d",
    },
    uirevision: "structure3d",
  };
}

/** The sentence under the plot: what is drawn, at what thresholds. */
export function caption(geometry: Geometry, mode: Mode): string {
  const real = geometry.atoms.filter((a) => !a.boundary).length;
  const ghosts = geometry.atoms.length - real;
  const parts = [
    `${real} atom${real === 1 ? "" : "s"} in the cell`
      + (ghosts ? ` + ${ghosts} image${ghosts === 1 ? "" : "s"} outside it` : ""),
    `${geometry.bonds.length} bond segment${geometry.bonds.length === 1 ? "" : "s"}`
      + ` at ${geometry.bond_tolerance.toFixed(2)}×(rᵢ+rⱼ)`,
  ];
  if (!geometry.bond_metals) parts.push("metal–metal contacts not bonded");
  parts.push(mode === "ellipsoid"
    ? `ellipsoids at ${(geometry.probability * 100).toFixed(0)} % (k = ${geometry.scale.toFixed(3)})`
    : `balls at ${geometry.ball_fraction.toFixed(2)}× the covalent radius`);
  return parts.join(" · ");
}

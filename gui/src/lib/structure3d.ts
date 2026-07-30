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

export interface Mesh {
  vertices: number[][];
  faces: number[][];
}

/**
 * A unit sphere as vertices and triangles — built once and reused for every atom.
 *
 * Latitude/longitude rather than a subdivided icosahedron: the triangles bunch
 * at the poles, which a subdivided icosahedron avoids, but at eight rings the
 * difference is invisible and the construction is one that can be read.
 */
export function unitSphere(rings = 8, segments = 16): Mesh {
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
      lighting: { ambient: 0.62, diffuse: 0.82, specular: 0.18, roughness: 0.55 },
      hovertemplate: "%{text}<extra></extra>",
    });
  }
  return traces;
}

/** Bonds as one null-broken polyline; the hover carries the distance. */
export function bondTrace(geometry: Geometry, color: string): any {
  const x: Array<number | null> = [], y: Array<number | null> = [];
  const z: Array<number | null> = [], text: Array<string | null> = [];
  for (const bond of geometry.bonds) {
    const label = `${geometry.sites[geometry.atoms[bond.i].site].label}–`
      + `${geometry.sites[geometry.atoms[bond.j].site].label}  ${bond.d.toFixed(3)} Å`;
    x.push(bond.a[0], bond.b[0], null);
    y.push(bond.a[1], bond.b[1], null);
    z.push(bond.a[2], bond.b[2], null);
    text.push(label, label, null);
  }
  return {
    type: "scatter3d", mode: "lines", name: "bonds", x, y, z, text,
    line: { width: 4, color }, showlegend: false,
    hovertemplate: "%{text}<extra></extra>",
  };
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
    line: { width: 1.6, color, dash: "dot" }, showlegend: false,
    hoverinfo: "skip",
  };
}

/** Everything, in draw order: cell behind, bonds, then atoms. */
export function traces(geometry: Geometry, mode: Mode, sphere: Mesh,
                       colors: { cell: string; bond: string },
                       hidden: ReadonlySet<string> = new Set(),
                       showBoundary = true): any[] {
  return [cellTrace(geometry, colors.cell), bondTrace(geometry, colors.bond),
          ...atomTraces(geometry, mode, sphere, hidden, showBoundary)];
}

/**
 * The scene layout.
 *
 * Two settings are load-bearing.  `aspectmode: "data"` keeps one Å the same
 * length on all three axes — without it plotly stretches the box to a cube and
 * a monoclinic cell is drawn as an orthogonal one, which is the whole
 * *content* of the picture for a low-symmetry phase.  And `uirevision` is what
 * lets a redraw keep the camera: the payload is refetched on every head move,
 * so without it the view would snap back to the default angle every time a
 * parameter changed.
 */
export function layout(fg: string, muted: string): any {
  const axis = {
    showspikes: false, showbackground: false,
    gridcolor: muted, zerolinecolor: muted,
    titlefont: { size: 10 }, tickfont: { size: 9 },
  };
  return {
    margin: { l: 0, r: 0, t: 0, b: 0 },
    showlegend: false,
    font: { color: fg, size: 11 },
    paper_bgcolor: "rgba(0,0,0,0)",
    scene: {
      aspectmode: "data",
      xaxis: { ...axis, title: { text: "x (Å)" } },
      yaxis: { ...axis, title: { text: "y (Å)" } },
      zaxis: { ...axis, title: { text: "z (Å)" } },
      camera: { eye: { x: 1.35, y: 1.35, z: 0.95 } },
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

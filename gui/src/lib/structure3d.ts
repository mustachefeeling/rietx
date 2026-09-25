/** The structure viewer's geometry, as pure functions (WP-1015, WP-1462).
 *
 * **No crystallography crosses the wire.**  `GET /api/structure3d` returns
 * Cartesian points in Å, 3×3 matrices and index pairs; everything here is the
 * arithmetic that turns those into a `Scene` the renderer draws and a `View`
 * it draws it from.  The symmetry expansion, the metric, the
 * eigen-decomposition and the bond rule are all server-side, which is the same
 * refusal WP-1010 made about decimation: two answers to "where is this atom"
 * is one more than a viewer may have.
 *
 * The one design fact worth stating here is why a ball and an ellipsoid are
 * one code path.  Every atom is `pos + M·v` over the unit sphere `v`, and the
 * renderer ray-casts that quadric exactly (`lib/gl3d.ts`), so the only
 * difference between the modes is which `M` is used: a ball is `f·r·I`, an
 * ellipsoid is `k(p)·T` from the payload.  Everything is in Å, so a ball can be
 * compared with the cell around it, which is what plotly's pixel-sized markers
 * could not do and why WP-1015 drew meshes.
 *
 * The same equation the shader solves is solved here for the pointer
 * (`pickAtom`, `pickHalf`), since the browser already holds every position and
 * matrix — so hover needs no id buffer and no pixel read-back (WP-1462 D4).
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

/** A 3×3 matrix, **row-major**, nine numbers. */
export type Mat3 = number[];

/**
 * A colour scaled toward black — the second depth cue, for images outside the
 * cell.
 *
 * Not decoration and not only a depth cue: a boundary atom is the *same* atom
 * seen at the opposite face (or a bonded neighbour just outside), so drawing it
 * dimmer says what it is. It also separates the case the complaint was really
 * about — two same-coloured spheres overlapping at a cell face, one of which is
 * an image of the other.
 */
export function dim(color: string, factor = 0.62): string {
  if (!/^#[0-9a-f]{6}$/i.test(color)) return color;
  const channel = (at: number) =>
    Math.round(parseInt(color.slice(at, at + 2), 16) * factor)
      .toString(16).padStart(2, "0");
  return `#${channel(1)}${channel(3)}${channel(5)}`;
}

/** `#rrggbb` as three channels in 0..1; anything else is mid-grey. */
export function rgb(color: string): number[] {
  if (!/^#[0-9a-f]{6}$/i.test(color)) return [0.5, 0.5, 0.5];
  return [1, 3, 5].map((at) => parseInt(color.slice(at, at + 2), 16) / 255);
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
                              mode: Mode, exaggeration = 1): number[][] {
  if (mode === "ellipsoid") {
    // k(p) and the exaggeration multiply here and are *named* separately
    // everywhere they are shown: k is a probability, the other is not one
    const k = geometry.scale * exaggeration;
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

/** One hover line per bond: the two sites and the length. */
export function bondLabel(geometry: Geometry, bond: Bond): string {
  const name = (index: number) => geometry.sites[geometry.atoms[index].site].label;
  return `${name(bond.i)}–${name(bond.j)}  ${bond.d.toFixed(3)} Å`;
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

/** Half a bond is 0.08 Å thick.
 *
 * These are *covalent* radii, which is what makes the number smaller than it
 * looks beside VESTA's: at `ball_fraction` even hydrogen (r = 0.31 Å) keeps a
 * ball wider than its own stick, so no species is drawn as a lump on a rod.
 */
export const STICK_RADIUS = 0.08;

/** How much of the smallest drawn semi-axis a stick may take in ellipsoid mode. */
export const STICK_OF_SEMI_AXIS = 0.5;

/** Below this a stick is a hairline at any zoom, so it stops shrinking. */
export const STICK_FLOOR = 0.02;

/**
 * How thick a half-bond is drawn, in Å, **for the mode it is drawn in**.
 *
 * In ball mode this is `STICK_RADIUS`, pinned by test below `BALL_FRACTION` on
 * the smallest covalent radius there is, so every ball is wider than its own
 * stick.  In ellipsoid mode an atom's size is `√U·k(p)·e` and has nothing to do
 * with a covalent radius, so the same fixed number made the sticks nearly as
 * thick as the atoms — measured on NAC, the smallest semi-axis at the default
 * 50 % is 0.130 Å against a 0.08 Å stick, and the *shipped* 10 % level put the
 * atom inside the stick at 0.065 Å.
 *
 * So in ellipsoid mode the radius is half the smallest semi-axis actually
 * drawn, which makes the burial a proof rather than a hope: a rim of radius
 * `r ≤ ½·min semi-axis` lies inside the ellipsoid's inscribed sphere, hence
 * inside the ellipsoid in every direction. It never *grows* past
 * `STICK_RADIUS`, because a fat stick is a fat stick whatever it is buried in.
 */
export function stickRadius(geometry: Geometry, mode: Mode, exaggeration = 1): number {
  if (mode !== "ellipsoid") return STICK_RADIUS;
  const semi = geometry.atoms.flatMap((atom) => atom.rms).filter((v) => v > 0);
  if (!semi.length) return STICK_RADIUS;
  const smallest = Math.min(...semi) * geometry.scale * exaggeration;
  return Math.max(STICK_FLOOR, Math.min(STICK_RADIUS, STICK_OF_SEMI_AXIS * smallest));
}

/**
 * A drawn semi-axis below this is drawn at this, in Å.
 *
 * A tensor that is not positive definite arrives with its non-positive axes at
 * **zero** (the server's rule: visibly flat, never a NaN).  The ray-caster
 * solves through `M⁻¹`, which a zero column does not have, so the column is
 * kept at a thousandth of an Å: still a disc at any zoom a person uses.
 */
export const FLAT_AXIS = 1e-3;

/** The cell frame's width, in CSS pixels (WP-1462 D9) — plotly's `line.width`
 *  was 2, and a WebGL line is one *device* pixel, half that at DPR 2. */
export const CELL_WIDTH_PX = 2;

/** One atom as the renderer draws it. */
export interface SceneAtom {
  /** index into `geometry.atoms`, for the hover text */
  index: number;
  pos: number[];
  /** `pos + M·v` over the unit sphere, row-major */
  shape: Mat3;
  inverse: Mat3;
  color: number[];
  /** draw the three principal ellipses: an anisotropic site, in ellipsoid mode */
  rings: boolean;
}

/** One half of a bond: a cylinder from its atom to the midpoint. */
export interface SceneHalf {
  bond: number;
  from: number[];
  to: number[];
  radius: number;
  color: number[];
}

/** A segment drawn at a width in CSS pixels. */
export interface SceneLine {
  a: number[];
  b: number[];
  color: number[];
  width: number;
}

export interface SceneLabel {
  text: string;
  pos: number[];
}

/** Everything the renderer draws, in Å — and nothing it has to derive. */
export interface Scene {
  atoms: SceneAtom[];
  halves: SceneHalf[];
  lines: SceneLine[];
  labels: SceneLabel[];
  /** the centre of the cell and its atoms, and the radius the view fits */
  center: number[];
  radius: number;
  /** how far from the centre anything drawn reaches, Å: the depth range */
  depth: number;
}

export interface SceneOptions {
  mode: Mode;
  hidden?: ReadonlySet<string>;
  showBoundary?: boolean;
  exaggeration?: number;
  /** the cell frame's colour, `#rrggbb` */
  cell?: string;
}

function toRowMajor(m: number[][]): Mat3 {
  return [m[0][0], m[0][1], m[0][2], m[1][0], m[1][1], m[1][2],
          m[2][0], m[2][1], m[2][2]];
}

/** The inverse of a row-major 3×3; `null` when it is singular. */
export function invert3(m: Mat3): Mat3 | null {
  const [a, b, c, d, e, f, g, h, i] = m;
  const A = e * i - f * h, B = -(d * i - f * g), C = d * h - e * g;
  const det = a * A + b * B + c * C;
  if (!Number.isFinite(det) || Math.abs(det) < 1e-300) return null;
  return [A / det, -(b * i - c * h) / det, (b * f - c * e) / det,
          B / det, (a * i - c * g) / det, -(a * f - c * d) / det,
          C / det, -(a * h - b * g) / det, (a * e - b * d) / det];
}

/** `a·b` for row-major 3×3s. */
export function mul3(a: Mat3, b: Mat3): Mat3 {
  const o = new Array(9);
  for (let r = 0; r < 3; r += 1) {
    for (let c = 0; c < 3; c += 1) {
      o[3 * r + c] = a[3 * r] * b[c] + a[3 * r + 1] * b[3 + c] + a[3 * r + 2] * b[6 + c];
    }
  }
  return o;
}

/** `m·v` for a row-major 3×3. */
export function apply3(m: Mat3, v: number[]): number[] {
  return [m[0] * v[0] + m[1] * v[1] + m[2] * v[2],
          m[3] * v[0] + m[4] * v[1] + m[5] * v[2],
          m[6] * v[0] + m[7] * v[1] + m[8] * v[2]];
}

export function transpose3(m: Mat3): Mat3 {
  return [m[0], m[3], m[6], m[1], m[4], m[7], m[2], m[5], m[8]];
}

/** An atom's drawn shape with every column at least `FLAT_AXIS` long. */
function drawable(m: number[][]): Mat3 {
  const out = toRowMajor(m);
  for (let c = 0; c < 3; c += 1) {
    const length = Math.hypot(out[c], out[3 + c], out[6 + c]);
    if (length >= FLAT_AXIS) continue;
    // a zero column has no direction left, so a flat axis takes the one the
    // other two leave free
    const u = [out[(c + 1) % 3], out[3 + (c + 1) % 3], out[6 + (c + 1) % 3]];
    const v = [out[(c + 2) % 3], out[3 + (c + 2) % 3], out[6 + (c + 2) % 3]];
    let n = [u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0]];
    const nn = Math.hypot(n[0], n[1], n[2]);
    n = nn > 0 ? n.map((x) => x / nn) : [c === 0 ? 1 : 0, c === 1 ? 1 : 0, c === 2 ? 1 : 0];
    out[c] = FLAT_AXIS * n[0];
    out[3 + c] = FLAT_AXIS * n[1];
    out[6 + c] = FLAT_AXIS * n[2];
  }
  return out;
}

/**
 * The scene for one payload, in the given mode.
 *
 * `hidden` is the set of species the legend has switched off, and **a half
 * belongs to its atom**: switching a species off takes its own halves with it
 * rather than leaving coloured stubs in mid-air.  `showBoundary` hides the
 * images outside the cell and keeps the bonds to them, which then end in
 * mid-air — what the checkbox says it does.
 *
 * Bonds are split at the midpoint and each half is coloured by the atom it
 * leaves — the convention every other viewer uses, and the thing that makes a
 * bond say which two species it joins without a hover.
 */
export function buildScene(geometry: Geometry, options: SceneOptions): Scene {
  const { mode, hidden = new Set<string>(), showBoundary = true,
          exaggeration = 1, cell = "#1f5fa8" } = options;
  const atoms: SceneAtom[] = [];
  geometry.atoms.forEach((atom, index) => {
    const site = geometry.sites[atom.site];
    if (hidden.has(site.species)) return;
    if (atom.boundary && !showBoundary) return;
    const shape = drawable(atomTransform(geometry, atom, mode, exaggeration));
    atoms.push({
      index,
      pos: atom.pos,
      shape,
      inverse: invert3(shape)!,
      color: rgb(atom.boundary ? dim(site.color) : site.color),
      // an isotropic site's T is √U·I, whose axes are x, y and z: rings there
      // would claim an orientation the site does not have
      rings: mode === "ellipsoid" && site.aniso,
    });
  });
  const radius = stickRadius(geometry, mode, exaggeration);
  const halves: SceneHalf[] = [];
  geometry.bonds.forEach((bond, index) => {
    const mid = [0, 1, 2].map((k) => (bond.a[k] + bond.b[k]) / 2);
    for (const [from, at] of [[bond.a, bond.i], [bond.b, bond.j]] as const) {
      const site = geometry.sites[geometry.atoms[at].site];
      if (hidden.has(site.species)) continue;
      halves.push({ bond: index, from, to: mid, radius, color: rgb(site.color) });
    }
  });
  const ink = rgb(cell);
  const lines: SceneLine[] = geometry.edges.map(([a, b]) => ({
    a: geometry.corners[a], b: geometry.corners[b], color: ink, width: CELL_WIDTH_PX,
  }));
  // the fit reads positions and ball sizes only, so neither a mode nor a
  // legend click moves the zoom; the depth range holds whatever is drawn
  const points = [...geometry.corners, ...geometry.atoms.map((a) => a.pos)];
  const lo = [0, 1, 2].map((k) => Math.min(...points.map((p) => p[k])));
  const hi = [0, 1, 2].map((k) => Math.max(...points.map((p) => p[k])));
  const center = [0, 1, 2].map((k) => (lo[k] + hi[k]) / 2);
  // the half-diagonal of the box holds the scene in *every* orientation, so a
  // rotation never pushes an atom off the canvas
  const half = Math.hypot(hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2]) / 2;
  const ball = geometry.ball_fraction * Math.max(0, ...geometry.sites.map((s) => s.radius));
  const reach = Math.max(ball, ...atoms.map((a) => [0, 1, 2].reduce((m, c) =>
    Math.max(m, Math.hypot(a.shape[c], a.shape[3 + c], a.shape[6 + c])), 0)));
  return { atoms, halves, lines, labels: axisLabels(geometry), center,
           radius: Math.max(half + ball, 1), depth: half + reach + 1 };
}

/**
 * "a", "b", "c" just beyond the far end of the three cell edges leaving the
 * origin.
 *
 * This is the scene's frame of reference, in place of a Cartesian box: nothing
 * in the picture happens in x, y or z.  `lattice`'s rows *are* those three
 * edges (corner `1 << k` is `lattice[k]`).
 *
 * The clearance is **in Å and set by the largest ball**, not a percentage of the
 * cell edge.  A fraction is the wrong shape for the problem: a corner site is
 * drawn at all eight corners, so the letter has to clear a *ball*, and 8 % of
 * LaB6's 4.16 Å edge is 0.33 Å against a lanthanum drawn at 0.83 — every letter
 * was inside an atom, which is what a browser showed and jsdom cannot.
 */
export function axisLabels(geometry: Geometry): SceneLabel[] {
  const largest = Math.max(0, ...geometry.sites.map((site) => site.radius));
  const clear = 0.35 + geometry.ball_fraction * largest;
  const origin = geometry.corners[0] ?? [0, 0, 0];
  return ["a", "b", "c"].map((text, k) => {
    const v = geometry.lattice[k];
    const length = Math.hypot(v[0], v[1], v[2]) || 1;
    return { text, pos: v.map((c, i) => origin[i] + c * (1 + clear / length)) };
  });
}

// ----------------------------------------------------------------------
// the view
// ----------------------------------------------------------------------

/**
 * Where the scene is seen from: a rotation, a zoom and a pan.
 *
 * `rotation`'s rows are the screen's x (right), y (up) and z (toward the
 * viewer) in the scene's Å, so a point's view coordinates are
 * `rotation·(p − center)`.  The projection is **parallel**: perspective
 * converges a cubic cell's far edges, and a picture of a cell is for seeing its
 * shape (every crystallographic figure is a parallel projection).
 * `pan` is in Å along the screen's x and y; `zoom` multiplies the fit.
 */
export interface View {
  rotation: Mat3;
  zoom: number;
  pan: number[];
}

/** The rotation that looks *from* `eye` toward the centre with `up` up. */
export function lookFrom(eye: number[], up: number[]): Mat3 {
  const unit = (v: number[]) => {
    const n = Math.hypot(v[0], v[1], v[2]) || 1;
    return [v[0] / n, v[1] / n, v[2] / n];
  };
  const z = unit(eye);
  const along = up[0] * z[0] + up[1] * z[1] + up[2] * z[2];
  const y = unit([up[0] - along * z[0], up[1] - along * z[1], up[2] - along * z[2]]);
  const x = [y[1] * z[2] - y[2] * z[1], y[2] * z[0] - y[0] * z[2], y[0] * z[1] - y[1] * z[0]];
  return [...x, ...y, ...z];
}

/**
 * The opening view — down the body diagonal, so no axis is edge-on, with the
 * Cartesian z (which is c for every orthogonal cell) up.  The eye plotly's
 * viewer opened at, kept so the first picture does not move.
 */
export function openingView(): View {
  return { rotation: lookFrom([1.35, 1.35, 0.95], [0, 0, 1]), zoom: 1, pan: [0, 0] };
}

/**
 * The view looking straight down one lattice vector.
 *
 * The lattice vector points at the viewer and the next one but one is up:
 * down **a** puts **c** up and **b** right, down **b** puts **a** up and **c**
 * right, down **c** puts **b** up and **a** right, since `right = up × toward`
 * on a right-handed a, b, c.  Those are the three projections a
 * crystallographer draws.  `up` is Gram-Schmidted against the view direction
 * because in a triclinic cell no two lattice vectors are perpendicular.
 *
 * The zoom comes from the view passed in, so choosing a projection keeps the
 * zoom the user had; the pan goes, because a pan is relative to a direction.
 */
export function axisView(geometry: Geometry, axis: number, view: View = openingView()): View {
  return {
    rotation: lookFrom(geometry.lattice[axis], geometry.lattice[(axis + 2) % 3]),
    zoom: view.zoom,
    pan: [0, 0],
  };
}

/**
 * The view after a drag of `dx`, `dy` CSS pixels: a trackball.
 *
 * The rotation is about the screen axis perpendicular to the drag, applied in
 * the screen's frame, so the front of the scene follows the pointer whatever
 * the current orientation — the free rotation plotly's `orbit` mode gave, with
 * no up vector to pin (turntable would pin +z, and c ∥ z for every orthogonal
 * cell, so "down c" would be a degenerate view).
 */
export function rotateBy(view: View, dx: number, dy: number, radiansPerPx = 0.008): View {
  const angle = Math.hypot(dx, dy) * radiansPerPx;
  if (!(angle > 0)) return view;
  const [x, y] = [dy / Math.hypot(dx, dy), dx / Math.hypot(dx, dy)];
  const c = Math.cos(angle), s = Math.sin(angle), t = 1 - c;
  // Rodrigues about (x, y, 0)
  const turn: Mat3 = [t * x * x + c, t * x * y, s * y,
                      t * x * y, t * y * y + c, -s * x,
                      -s * y, s * x, c];
  return { ...view, rotation: orthonormal(mul3(turn, view.rotation)) };
}

/** Re-orthonormalise a rotation, so a long drag cannot shear the picture. */
function orthonormal(m: Mat3): Mat3 {
  const unit = (v: number[]) => {
    const n = Math.hypot(v[0], v[1], v[2]) || 1;
    return v.map((c) => c / n);
  };
  const x = unit(m.slice(0, 3));
  let y = m.slice(3, 6);
  const along = x[0] * y[0] + x[1] * y[1] + x[2] * y[2];
  y = unit([y[0] - along * x[0], y[1] - along * x[1], y[2] - along * x[2]]);
  const z = [x[1] * y[2] - x[2] * y[1], x[2] * y[0] - x[0] * y[2], x[0] * y[1] - x[1] * y[0]];
  return [...x, ...y, ...z];
}

/** Pixels per Å for a canvas of `width` × `height` CSS pixels. */
export function pixelsPerAngstrom(scene: Scene, view: View, width: number,
                                  height: number): number {
  return view.zoom * Math.min(width, height) / (2 * scene.radius);
}

/** A scene point in view coordinates, Å: x right, y up, z toward the viewer. */
export function toView(scene: Scene, view: View, p: number[]): number[] {
  const v = apply3(view.rotation, [p[0] - scene.center[0], p[1] - scene.center[1],
                                   p[2] - scene.center[2]]);
  return [v[0] - view.pan[0], v[1] - view.pan[1], v[2]];
}

/** A scene point on the canvas, in CSS pixels from its top-left corner. */
export function project(scene: Scene, view: View, width: number, height: number,
                        p: number[]): number[] {
  const s = pixelsPerAngstrom(scene, view, width, height);
  const v = toView(scene, view, p);
  return [width / 2 + v[0] * s, height / 2 - v[1] * s, v[2]];
}

/** A canvas point, CSS pixels, back to view coordinates in Å (x, y only). */
function unproject(scene: Scene, view: View, width: number, height: number,
                   px: number, py: number): number[] {
  const s = pixelsPerAngstrom(scene, view, width, height);
  return [(px - width / 2) / s, (height / 2 - py) / s];
}

/**
 * The atom under a canvas point, or `null`: the nearest to the viewer of those
 * whose ellipsoid the ray meets.
 *
 * The ray is `(x, y, z)` with `z` free, which in an atom's unit-sphere frame is
 * `u = q + t·e` — the shader's equation, solved once per atom here.
 */
export function pickAtom(scene: Scene, view: View, width: number, height: number,
                         px: number, py: number): { atom: number; z: number } | null {
  const [x, y] = unproject(scene, view, width, height, px, py);
  const back = transpose3(view.rotation);
  let best: { atom: number; z: number } | null = null;
  for (const [i, atom] of scene.atoms.entries()) {
    const c = toView(scene, view, atom.pos);
    const minv = mul3(atom.inverse, back);
    const q = apply3(minv, [x - c[0], y - c[1], 0]);
    const e = [minv[2], minv[5], minv[8]];
    const a = e[0] * e[0] + e[1] * e[1] + e[2] * e[2];
    const b = q[0] * e[0] + q[1] * e[1] + q[2] * e[2];
    const disc = b * b - a * (q[0] * q[0] + q[1] * q[1] + q[2] * q[2] - 1);
    if (disc < 0 || a <= 0) continue;
    const z = c[2] + (-b + Math.sqrt(disc)) / a;
    if (!best || z > best.z) best = { atom: i, z };
  }
  return best;
}

/** The bond half under a canvas point, or `null` — the shader's finite
 *  cylinder, solved for one ray. */
export function pickHalf(scene: Scene, view: View, width: number, height: number,
                         px: number, py: number): { half: number; z: number } | null {
  const [x, y] = unproject(scene, view, width, height, px, py);
  let best: { half: number; z: number } | null = null;
  for (const [i, half] of scene.halves.entries()) {
    const A = toView(scene, view, half.from), B = toView(scene, view, half.to);
    const ba = [B[0] - A[0], B[1] - A[1], B[2] - A[2]];
    // the ray starts far in front and runs down −z
    const oc = [x - A[0], y - A[1], 1e4 - A[2]];
    const baba = ba[0] * ba[0] + ba[1] * ba[1] + ba[2] * ba[2];
    const bard = -ba[2];
    const baoc = ba[0] * oc[0] + ba[1] * oc[1] + ba[2] * oc[2];
    const k2 = baba - bard * bard;
    if (k2 < 1e-12) continue;
    const k1 = baba * -oc[2] - baoc * bard;
    const k0 = baba * (oc[0] * oc[0] + oc[1] * oc[1] + oc[2] * oc[2])
      - baoc * baoc - half.radius * half.radius * baba;
    const h = k1 * k1 - k2 * k0;
    if (h < 0) continue;
    const t = (-k1 - Math.sqrt(h)) / k2;
    const along = baoc + t * bard;
    if (along < 0 || along > baba) continue;
    const z = 1e4 - t;
    if (!best || z > best.z) best = { half: i, z };
  }
  return best;
}

/** The sentence under the plot: what is drawn, at what thresholds. */
export function caption(geometry: Geometry, mode: Mode, exaggeration = 1): string {
  const real = geometry.atoms.filter((a) => !a.boundary).length;
  const ghosts = geometry.atoms.length - real;
  const parts = [
    `${real} atom${real === 1 ? "" : "s"} in the cell`
      + (ghosts ? ` + ${ghosts} image${ghosts === 1 ? "" : "s"} outside it` : ""),
    `${geometry.bonds.length} bond segment${geometry.bonds.length === 1 ? "" : "s"}`
      + ` at ${geometry.bond_tolerance.toFixed(2)}×(rᵢ+rⱼ)`,
  ];
  if (!geometry.bond_metals) parts.push("metal–metal contacts not bonded");
  if (mode === "ellipsoid") {
    // The probability and the exaggeration are stated **separately**, always.
    // A probability cannot exceed 1 — k(p) = √χ²₃(p) diverges as p → 1, and
    // `probability_scale(1.0)` raises — so "bigger so I can see it" is not a
    // higher probability, and a viewer that drew 1.5·k(0.5) under a "50 %"
    // label would be claiming a surface it is not drawing.  An ORTEP figure
    // quotes a probability because the surface *means* something.
    let text = `ellipsoids at ${(geometry.probability * 100).toFixed(0)} %`
      + ` (k = ${geometry.scale.toFixed(3)})`;
    if (exaggeration !== 1) {
      text += ` × ${exaggeration.toFixed(2)} exaggeration — a drawing scale,`
        + " not a probability: no surface encloses more at this size";
    }
    parts.push(text);
  } else {
    parts.push(`balls at ${geometry.ball_fraction.toFixed(2)}× the covalent radius`);
  }
  parts.push(`sticks ${stickRadius(geometry, mode, exaggeration).toFixed(3)} Å`);
  return parts.join(" · ");
}

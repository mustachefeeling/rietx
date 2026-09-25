// Prototype: the structure viewer as a hand-written WebGL2 impostor renderer.
// Draws the /api/structure3d payload as ray-cast quadrics: one quad per atom
// (sphere or ellipsoid, one code path through M = k·T) and one per bond half.
// No dependencies.  View space: x right, y up, the viewer at +z.

const ATOM_VS = `#version 300 es
in vec2 aCorner;
in vec3 aCenter;
in vec3 aM0; in vec3 aM1; in vec3 aM2;
in vec3 aI0; in vec3 aI1; in vec3 aI2;
in vec4 aColor;
uniform mat3 uR; uniform vec3 uTarget; uniform vec2 uScale; uniform float uDepth; uniform float uPad;
out vec2 vXY;
flat out vec3 vC; flat out mat3 vMinv; flat out vec4 vColor;
void main() {
  mat3 M = uR * mat3(aM0, aM1, aM2);
  vec3 c = uR * (aCenter - uTarget);
  // the projected ellipsoid's exact half-extents: the norms of M's first two rows
  vec2 h = vec2(length(vec3(M[0][0], M[1][0], M[2][0])),
                length(vec3(M[0][1], M[1][1], M[2][1]))) + uPad;
  vXY = c.xy + aCorner * h;
  vC = c;
  vMinv = mat3(aI0, aI1, aI2) * transpose(uR);
  vColor = aColor;
  gl_Position = vec4(vXY * uScale, 0.0, 1.0);
}`;

const ATOM_FS = `#version 300 es
precision highp float;
in vec2 vXY;
flat in vec3 vC; flat in mat3 vMinv; flat in vec4 vColor;
uniform float uDepth; uniform float uRing; uniform vec3 uLight;
out vec4 frag;
void main() {
  // ray (x, y, z) with z free; in the unit-sphere frame u = q + s·e, s = z - c.z
  vec3 q = vMinv * vec3(vXY - vC.xy, 0.0);
  vec3 e = vMinv[2];
  float a = dot(e, e), b = dot(q, e), cc = dot(q, q) - 1.0;
  float disc = b * b - a * cc;
  if (disc < 0.0) discard;
  float s = (-b + sqrt(disc)) / a;           // the root nearer the viewer
  vec3 u = q + s * e;
  vec3 n = normalize(transpose(vMinv) * u);
  float z = vC.z + s;
  gl_FragDepth = 0.5 - z / (2.0 * uDepth);
  float diffuse = max(dot(n, uLight), 0.0);
  float spec = pow(max(dot(reflect(-uLight, n), vec3(0.0, 0.0, 1.0)), 0.0), 48.0);
  vec3 col = vColor.rgb * (0.38 + 0.62 * diffuse) + 0.22 * spec;
  if (uRing > 0.0 && vColor.a > 0.5) {
    // the three principal ellipses: T's columns are the principal axes, so a
    // ring is one unit-frame coordinate near zero
    float m = min(abs(u.x), min(abs(u.y), abs(u.z)));
    float w = fwidth(m);
    col = mix(col * 0.25, col, smoothstep(uRing, uRing + w, m));
  }
  frag = vec4(col, 1.0);
}`;

const BOND_VS = `#version 300 es
in vec2 aCorner;              // x in {0, 1} along the bond, y in {-1, 1} across it
in vec3 aA; in vec3 aB; in vec3 aColor; in float aRadius;
uniform mat3 uR; uniform vec3 uTarget; uniform vec2 uScale;
out vec2 vXY;
flat out vec3 vA; flat out vec3 vB; flat out vec3 vColor; flat out float vR;
void main() {
  vec3 A = uR * (aA - uTarget), B = uR * (aB - uTarget);
  vec2 d = B.xy - A.xy;
  float l = length(d);
  vec2 dir = l > 1e-6 ? d / l : vec2(1.0, 0.0);
  vec2 perp = vec2(-dir.y, dir.x);
  vXY = mix(A.xy, B.xy, aCorner.x) + dir * (2.0 * aCorner.x - 1.0) * aRadius + perp * aCorner.y * aRadius;
  vA = A; vB = B; vColor = aColor; vR = aRadius;
  gl_Position = vec4(vXY * uScale, 0.0, 1.0);
}`;

const BOND_FS = `#version 300 es
precision highp float;
in vec2 vXY;
flat in vec3 vA; flat in vec3 vB; flat in vec3 vColor; flat in float vR;
uniform float uDepth; uniform vec3 uLight;
out vec4 frag;
void main() {
  // the ray (x, y, z) with z free against the finite cylinder A-B: with the
  // parts along the axis w removed, the radius is |q + z·e|
  float len = length(vB - vA);
  if (len < 1e-9) discard;
  vec3 w = (vB - vA) / len;
  vec3 o = vec3(vXY, 0.0) - vA;
  vec3 dz = vec3(0.0, 0.0, 1.0);
  vec3 q = o - dot(o, w) * w, e = dz - dot(dz, w) * w;
  float a = dot(e, e);
  if (a < 1e-9) discard;
  float b = dot(q, e), disc = b * b - a * (dot(q, q) - vR * vR);
  if (disc < 0.0) discard;
  float z = (-b + sqrt(disc)) / a;
  float along = dot(o, w) + z * dot(dz, w);
  if (along < 0.0 || along > len) discard;
  vec3 n = (q + z * e) / vR;
  gl_FragDepth = 0.5 - z / (2.0 * uDepth);
  float diffuse = max(dot(n, uLight), 0.0);
  frag = vec4(vColor * (0.38 + 0.62 * diffuse), 1.0);
}`;

const LINE_VS = `#version 300 es
in vec3 aPos;
uniform mat3 uR; uniform vec3 uTarget; uniform vec2 uScale; uniform float uDepth;
void main() {
  vec3 p = uR * (aPos - uTarget);
  gl_Position = vec4(p.xy * uScale, -p.z / uDepth, 1.0);
}`;

const LINE_FS = `#version 300 es
precision highp float;
uniform vec3 uColor;
out vec4 frag;
void main() { frag = vec4(uColor, 1.0); }`;

// Polyhedra are ordinary triangles: flat faces, lit two-sided, blended.
const POLY_VS = `#version 300 es
in vec3 aPos; in vec3 aNormal; in vec4 aColor;
uniform mat3 uR; uniform vec3 uTarget; uniform vec2 uScale; uniform float uDepth;
out vec3 vN; out vec4 vColor;
void main() {
  vec3 p = uR * (aPos - uTarget);
  vN = uR * aNormal; vColor = aColor;
  gl_Position = vec4(p.xy * uScale, -p.z / uDepth, 1.0);
}`;

const POLY_FS = `#version 300 es
precision highp float;
in vec3 vN; in vec4 vColor;
uniform vec3 uLight;
out vec4 frag;
void main() {
  vec3 n = normalize(gl_FrontFacing ? vN : -vN);
  frag = vec4(vColor.rgb * (0.45 + 0.55 * max(dot(n, uLight), 0.0)), vColor.a);
}`;

const POLY_ALPHA = 0.55;
const STICK_RADIUS = 0.08;
const LIGHT = normalize([-0.45, 0.55, 0.7]);

function normalize(v) { const l = Math.hypot(...v); return v.map((x) => x / l); }
function hex(c) { const n = parseInt(c.slice(1), 16); return [(n >> 16) / 255, ((n >> 8) & 255) / 255, (n & 255) / 255]; }

// 3×3 matrices are row-major arrays of 9 here; GLSL wants column-major.
function mul(a, b) {
  const o = new Array(9);
  for (let i = 0; i < 3; i++) for (let j = 0; j < 3; j++)
    o[3 * i + j] = a[3 * i] * b[j] + a[3 * i + 1] * b[3 + j] + a[3 * i + 2] * b[6 + j];
  return o;
}
function colMajor(m) { return [m[0], m[3], m[6], m[1], m[4], m[7], m[2], m[5], m[8]]; }
function rotation(axis, angle) {
  const [x, y, z] = normalize(axis), c = Math.cos(angle), s = Math.sin(angle), t = 1 - c;
  return [t * x * x + c, t * x * y - s * z, t * x * z + s * y,
          t * x * y + s * z, t * y * y + c, t * y * z - s * x,
          t * x * z - s * y, t * y * z + s * x, t * z * z + c];
}
function invert3(m) {
  const [a, b, c, d, e, f, g, h, i] = m;
  const A = e * i - f * h, B = -(d * i - f * g), C = d * h - e * g;
  const det = a * A + b * B + c * C;
  return [A / det, -(b * i - c * h) / det, (b * f - c * e) / det,
          B / det, (a * i - c * g) / det, -(a * f - c * d) / det,
          C / det, -(a * h - b * g) / det, (a * e - b * d) / det];
}
function apply(m, v) {
  return [m[0] * v[0] + m[1] * v[1] + m[2] * v[2], m[3] * v[0] + m[4] * v[1] + m[5] * v[2],
          m[6] * v[0] + m[7] * v[1] + m[8] * v[2]];
}

function program(gl, vs, fs) {
  const p = gl.createProgram();
  for (const [type, src] of [[gl.VERTEX_SHADER, vs], [gl.FRAGMENT_SHADER, fs]]) {
    const s = gl.createShader(type);
    gl.shaderSource(s, src); gl.compileShader(s);
    if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(s));
    gl.attachShader(p, s);
  }
  gl.linkProgram(p);
  if (!gl.getProgramParameter(p, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(p));
  const u = {};
  const n = gl.getProgramParameter(p, gl.ACTIVE_UNIFORMS);
  for (let i = 0; i < n; i++) { const { name } = gl.getActiveUniform(p, i); u[name] = gl.getUniformLocation(p, name); }
  return { p, u };
}

// One VAO: a static per-vertex corner buffer plus interleaved per-instance floats.
function instanced(gl, prog, corners, layout, data) {
  const vao = gl.createVertexArray();
  gl.bindVertexArray(vao);
  const cb = gl.createBuffer();
  gl.bindBuffer(gl.ARRAY_BUFFER, cb);
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(corners), gl.STATIC_DRAW);
  const loc = gl.getAttribLocation(prog.p, "aCorner");
  gl.enableVertexAttribArray(loc);
  gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);
  const ib = gl.createBuffer();
  gl.bindBuffer(gl.ARRAY_BUFFER, ib);
  gl.bufferData(gl.ARRAY_BUFFER, data, gl.STATIC_DRAW);
  const stride = layout.reduce((s, [, n]) => s + n, 0) * 4;
  let off = 0;
  for (const [name, n] of layout) {
    const l = gl.getAttribLocation(prog.p, name);
    if (l >= 0) {
      gl.enableVertexAttribArray(l);
      gl.vertexAttribPointer(l, n, gl.FLOAT, false, stride, off);
      gl.vertexAttribDivisor(l, 1);
    }
    off += n * 4;
  }
  gl.bindVertexArray(null);
  return { vao, buffers: [cb, ib] };
}

const ATOM_LAYOUT = [["aCenter", 3], ["aM0", 3], ["aM1", 3], ["aM2", 3], ["aI0", 3], ["aI1", 3], ["aI2", 3], ["aColor", 4]];
const BOND_LAYOUT = [["aA", 3], ["aB", 3], ["aColor", 3], ["aRadius", 1]];

// The drawn shape of one atom as a row-major 3×3: pos + M·v over the unit sphere.
function shapeOf(geometry, atom, mode, exaggeration) {
  const site = geometry.sites[atom.site];
  if (mode === "ball") {
    const r = geometry.ball_fraction * site.radius;
    return [r, 0, 0, 0, r, 0, 0, 0, r];
  }
  const k = geometry.scale * exaggeration;
  const T = atom.ellipsoid;
  const m = [];
  for (let i = 0; i < 3; i++) for (let j = 0; j < 3; j++) m.push(k * T[i][j]);
  // a zero semi-axis (a non-positive-definite tensor) has no inverse; draw it as
  // a disc of 1 mÅ rather than lose the atom
  for (let j = 0; j < 3; j++) {
    const len = Math.hypot(m[j], m[3 + j], m[6 + j]);
    if (len < 1e-3) { m[j] = 1e-3; m[3 + j] = 0; m[6 + j] = 0; }
  }
  return m;
}

export function createViewer(canvas, overlay) {
  const gl = canvas.getContext("webgl2", { antialias: true, alpha: false });
  if (!gl) throw new Error("WebGL2 unavailable");
  const atomProg = program(gl, ATOM_VS, ATOM_FS);
  const bondProg = program(gl, BOND_VS, BOND_FS);
  const lineProg = program(gl, LINE_VS, LINE_FS);
  const polyProg = program(gl, POLY_VS, POLY_FS);
  let R = [1, 0, 0, 0, 1, 0, 0, 0, 1];
  let target = [0, 0, 0], extent = 10, zoom = 1, depth = 20;
  let geometry = null, mode = "ball", exaggeration = 1, showPoly = false;
  let atoms = null, bonds = null, frame = null, poly = null, polyEdges = null, shapes = [], hidden = new Set();
  let background = [1, 1, 1], accent = [0.1, 0.35, 0.8];
  const labels = ["a", "b", "c"].map((t) => {
    const el = document.createElement("div");
    el.textContent = t; el.className = "axis-label";
    overlay.appendChild(el);
    return el;
  });

  function release(obj) {
    if (!obj) return;
    gl.deleteVertexArray(obj.vao);
    for (const b of obj.buffers) gl.deleteBuffer(b);
  }

  function upload() {
    release(atoms); release(bonds); release(frame);
    shapes = geometry.atoms.map((a) => shapeOf(geometry, a, mode, exaggeration));
    const shown = geometry.atoms.map((a) => !hidden.has(geometry.sites[a.site].species));
    const ad = new Float32Array(geometry.atoms.length * 25);
    let n = 0;
    geometry.atoms.forEach((a, i) => {
      if (!shown[i]) return;
      const m = shapes[i], inv = invert3(m), site = geometry.sites[a.site];
      ad.set([...a.pos, ...colMajor(m), ...colMajor(inv), ...hex(site.color), site.aniso ? 1 : 0], 25 * n++);
    });
    atoms = { ...instanced(gl, atomProg, [-1, -1, 1, -1, -1, 1, 1, 1], ATOM_LAYOUT, ad.subarray(0, 25 * n)), count: n };
    const bd = [];
    for (const b of geometry.bonds) {
      const mid = [0, 1, 2].map((k) => (b.a[k] + b.b[k]) / 2);
      const ends = [[b.a, geometry.atoms[b.i]], [b.b, geometry.atoms[b.j]]];
      for (const [end, atom] of ends) {
        if (!shown[geometry.atoms.indexOf(atom)]) continue;
        bd.push(...end, ...mid, ...hex(geometry.sites[atom.site].color), STICK_RADIUS);
      }
    }
    bonds = { ...instanced(gl, bondProg, [0, -1, 1, -1, 0, 1, 1, 1], BOND_LAYOUT, new Float32Array(bd)), count: bd.length / 10 };
    const vao = gl.createVertexArray();
    gl.bindVertexArray(vao);
    const buf = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, buf);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(geometry.edges.flatMap(([i, j]) => [...geometry.corners[i], ...geometry.corners[j]])), gl.STATIC_DRAW);
    const l = gl.getAttribLocation(lineProg.p, "aPos");
    gl.enableVertexAttribArray(l);
    gl.vertexAttribPointer(l, 3, gl.FLOAT, false, 0, 0);
    gl.bindVertexArray(null);
    frame = { vao, buffers: [buf], count: 24 };
    uploadPolyhedra(shown);
  }

  // One flat-shaded triangle list for every polyhedron, each owning a range so a
  // frame can draw them back to front; and their edges as lines in a darker ink.
  function uploadPolyhedra(shown) {
    release(poly); release(polyEdges);
    poly = polyEdges = null;
    const list = (geometry.polyhedra || []).filter((p) => shown[p.center]);
    if (!showPoly || !list.length) return;
    const tri = [], lines = [], ranges = [];
    for (const p of list) {
      const col = [...hex(p.color), POLY_ALPHA];
      const first = tri.length / 10;
      for (const [i, j, k] of p.faces) {
        const [a, b, c] = [p.vertices[i], p.vertices[j], p.vertices[k]];
        const u = b.map((x, m) => x - a[m]), v = c.map((x, m) => x - a[m]);
        const n = normalize([u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0]]);
        for (const q of [a, b, c]) tri.push(...q, ...n, ...col);
      }
      const centroid = [0, 1, 2].map((m) => p.vertices.reduce((s, q) => s + q[m], 0) / p.vertices.length);
      ranges.push({ first, count: tri.length / 10 - first, centroid });
      for (const [i, j] of p.edges) lines.push(...p.vertices[i], ...p.vertices[j]);
    }
    const mk = (prog, data, layout) => {
      const vao = gl.createVertexArray();
      gl.bindVertexArray(vao);
      const buf = gl.createBuffer();
      gl.bindBuffer(gl.ARRAY_BUFFER, buf);
      gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(data), gl.STATIC_DRAW);
      const stride = layout.reduce((s, [, n]) => s + n, 0) * 4;
      let off = 0;
      for (const [name, n] of layout) {
        const l = gl.getAttribLocation(prog.p, name);
        gl.enableVertexAttribArray(l);
        gl.vertexAttribPointer(l, n, gl.FLOAT, false, stride, off);
        off += n * 4;
      }
      gl.bindVertexArray(null);
      return { vao, buffers: [buf] };
    };
    poly = { ...mk(polyProg, tri, [["aPos", 3], ["aNormal", 3], ["aColor", 4]]), ranges };
    polyEdges = { ...mk(lineProg, lines, [["aPos", 3]]), count: lines.length / 3 };
  }

  function uniforms(prog, W, H) {
    const s = zoom * Math.min(W, H) / (2 * extent);     // px per Å
    gl.useProgram(prog.p);
    gl.uniformMatrix3fv(prog.u.uR, false, colMajor(R));
    gl.uniform3fv(prog.u.uTarget, target);
    gl.uniform2f(prog.u.uScale, 2 * s / W, 2 * s / H);
    if (prog.u.uDepth) gl.uniform1f(prog.u.uDepth, depth);
    if (prog.u.uPad) gl.uniform1f(prog.u.uPad, 1.5 / s);
    if (prog.u.uLight) gl.uniform3fv(prog.u.uLight, LIGHT);
    return s;
  }

  function draw() {
    if (!geometry) return;
    const dpr = window.devicePixelRatio || 1;
    const W = Math.round(canvas.clientWidth * dpr), H = Math.round(canvas.clientHeight * dpr);
    if (canvas.width !== W || canvas.height !== H) { canvas.width = W; canvas.height = H; }
    gl.viewport(0, 0, W, H);
    gl.clearColor(...background, 1);
    gl.enable(gl.DEPTH_TEST);
    gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
    uniforms(atomProg, W, H);
    gl.uniform1f(atomProg.u.uRing, mode === "ellipsoid" ? 0.035 : 0);
    gl.bindVertexArray(atoms.vao);
    gl.drawArraysInstanced(gl.TRIANGLE_STRIP, 0, 4, atoms.count);
    uniforms(bondProg, W, H);
    gl.bindVertexArray(bonds.vao);
    gl.drawArraysInstanced(gl.TRIANGLE_STRIP, 0, 4, bonds.count);
    const s = uniforms(lineProg, W, H);
    gl.uniform3fv(lineProg.u.uColor, accent);
    gl.bindVertexArray(frame.vao);
    gl.drawArrays(gl.LINES, 0, frame.count);
    if (poly) {
      gl.uniform3fv(lineProg.u.uColor, [0.25, 0.25, 0.25]);
      gl.bindVertexArray(polyEdges.vao);
      gl.drawArrays(gl.LINES, 0, polyEdges.count);
      // translucent faces last: depth-tested against everything opaque, writing
      // no depth, farthest polyhedron first and each one's back faces first
      uniforms(polyProg, W, H);
      gl.enable(gl.BLEND);
      gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);
      gl.depthMask(false);
      gl.enable(gl.CULL_FACE);
      gl.bindVertexArray(poly.vao);
      const z = (r) => R[6] * (r.centroid[0] - target[0]) + R[7] * (r.centroid[1] - target[1]) + R[8] * (r.centroid[2] - target[2]);
      for (const r of [...poly.ranges].sort((p, q) => z(p) - z(q))) {
        gl.cullFace(gl.FRONT); gl.drawArrays(gl.TRIANGLES, r.first, r.count);
        gl.cullFace(gl.BACK); gl.drawArrays(gl.TRIANGLES, r.first, r.count);
      }
      gl.disable(gl.CULL_FACE);
      gl.depthMask(true);
      gl.disable(gl.BLEND);
    }
    gl.bindVertexArray(null);
    // a, b, c as DOM text at each edge's end, beyond the origin corner
    const cw = canvas.clientWidth, ch = canvas.clientHeight, sc = s / dpr;
    geometry.lattice.forEach((v, k) => {
      const len = Math.hypot(...v);
      const p = apply(R, geometry.corners[0].map((x, i) => x + v[i] * (1 + 0.6 / len) - target[i]));
      labels[k].style.transform = `translate(${cw / 2 + p[0] * sc}px, ${ch / 2 - p[1] * sc}px) translate(-50%, -50%)`;
    });
  }

  let pending = 0;
  function schedule() { if (!pending) pending = requestAnimationFrame(() => { pending = 0; draw(); }); }

  function fit() {
    const pts = geometry.atoms.map((a) => a.pos).concat(geometry.corners);
    const lo = [0, 1, 2].map((k) => Math.min(...pts.map((p) => p[k])));
    const hi = [0, 1, 2].map((k) => Math.max(...pts.map((p) => p[k])));
    target = [0, 1, 2].map((k) => (lo[k] + hi[k]) / 2);
    extent = 0.55 * Math.hypot(...hi.map((h, k) => h - lo[k]));
    depth = 2 * extent + 4;
  }

  // The atom or bond half under a CSS pixel: the same quadric, solved on the CPU.
  function pick(px, py) {
    const dpr = window.devicePixelRatio || 1;
    const W = canvas.clientWidth * dpr, H = canvas.clientHeight * dpr;
    const s = zoom * Math.min(W, H) / (2 * extent) / dpr;
    const x = (px - canvas.clientWidth / 2) / s, y = (canvas.clientHeight / 2 - py) / s;
    const Rt = [R[0], R[3], R[6], R[1], R[4], R[7], R[2], R[5], R[8]];
    let best = null;
    geometry.atoms.forEach((a, i) => {
      if (hidden.has(geometry.sites[a.site].species)) return;
      const c = apply(R, a.pos.map((v, k) => v - target[k]));
      const Minv = mul(invert3(shapes[i]), Rt);
      const q = apply(Minv, [x - c[0], y - c[1], 0]);
      const e = [Minv[2], Minv[5], Minv[8]];
      const A = e[0] ** 2 + e[1] ** 2 + e[2] ** 2, B = q[0] * e[0] + q[1] * e[1] + q[2] * e[2];
      const disc = B * B - A * (q[0] ** 2 + q[1] ** 2 + q[2] ** 2 - 1);
      if (disc < 0) return;
      const z = c[2] + (-B + Math.sqrt(disc)) / A;
      if (!best || z > best.z) best = { z, kind: "atom", index: i };
    });
    return best;
  }

  let drag = null;
  canvas.addEventListener("pointerdown", (ev) => { drag = [ev.clientX, ev.clientY]; canvas.setPointerCapture(ev.pointerId); });
  canvas.addEventListener("pointerup", () => { drag = null; });
  canvas.addEventListener("pointermove", (ev) => {
    if (!drag) return;
    const dx = ev.clientX - drag[0], dy = ev.clientY - drag[1];
    drag = [ev.clientX, ev.clientY];
    const angle = Math.hypot(dx, dy) * 0.008;
    if (angle > 0) { R = mul(rotation([dy, dx, 0], angle), R); schedule(); }
  });
  canvas.addEventListener("wheel", (ev) => { ev.preventDefault(); zoom *= Math.exp(-ev.deltaY * 0.0015); schedule(); }, { passive: false });
  const ro = new ResizeObserver(schedule);
  ro.observe(canvas);

  return {
    set(g, opts = {}) {
      const first = !geometry;
      geometry = g;
      mode = opts.mode ?? mode;
      exaggeration = opts.exaggeration ?? exaggeration;
      showPoly = opts.poly ?? showPoly;
      if (first) fit();
      upload();
      draw();
    },
    setMode(m) { mode = m; upload(); schedule(); },
    toggle(species) { hidden.has(species) ? hidden.delete(species) : hidden.add(species); upload(); schedule(); },
    rotate(axis, angle) { R = mul(rotation(axis, angle), R); },
    zoom(f) { zoom *= f; },
    draw,
    pick,
    png() { draw(); return canvas.toDataURL("image/png"); },
    counts() { return { atoms: atoms.count, bondHalves: bonds.count }; },
    destroy() {
      ro.disconnect();
      release(atoms); release(bonds); release(frame); release(poly); release(polyEdges);
      for (const p of [atomProg, bondProg, lineProg, polyProg]) gl.deleteProgram(p.p);
      gl.getExtension("WEBGL_lose_context")?.loseContext();
      for (const l of labels) l.remove();
    },
  };
}

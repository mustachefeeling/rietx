// rxplot: the chart module rietx's browser pages draw with (WP-1461, D3).
//
// Two halves. The pure half touches no DOM and no uPlot, and
// `tests/rxplot.test.mjs` runs it under `node --test`. The drawing half stacks
// uPlot panes on one shared x, and `tests/test_rxplot_browser.py` drives it in
// chromium.
//
// uPlot is passed in, never imported. The GUI bundles it, and the Python pages
// serve the copy vendored beside this file (`uPlot.iife.min.js`), so the module
// runs under either without knowing which.

// ---------------------------------------------------------------- pure half

/** The first index whose value is at least `v`, in an ascending array. */
export function lower(xs, v) {
  let lo = 0, hi = xs.length;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if (xs[mid] < v) lo = mid + 1; else hi = mid;
  }
  return lo;
}

/**
 * The index of the entry nearest `v`, or -1 when none is within `radius`.
 * Distance is measured in pixels through `toPx`, since a pointer's reach is a
 * screen distance at every zoom.
 */
export function nearest(xs, v, toPx, radius) {
  const i = lower(xs, v), at = toPx(v);
  let best = -1, dist = Infinity;
  for (const j of [i - 1, i]) {
    if (j < 0 || j >= xs.length) continue;
    const d = Math.abs(toPx(xs[j]) - at);
    if (d < dist) { dist = d; best = j; }
  }
  return dist <= radius ? best : -1;
}

/**
 * Ticks for a √ axis, evenly spaced in √ space and rounded to half a decade
 * of the gap to the next tick. uPlot spaces ticks in value space, which on a √
 * scale printed one label for the whole axis (finding 2). Rounding to the
 * value's own decade did the same inside a narrow zoom: 1000 to 1010 all
 * rounded to 1000.
 */
export function sqrtSplits(min, max, n = 6) {
  const a = Math.sqrt(Math.max(min, 0)), b = Math.sqrt(Math.max(max, 0)), out = [];
  if (!(b > a)) return out;
  const at = (k) => (a + (b - a) * k / n) ** 2;
  for (let k = 0; k <= n; k++) {
    const v = at(k), half = 10 ** Math.floor(Math.log10(at(k + 1) - v)) / 2;
    const t = Math.round(v / half) * half;
    if (t >= min && t <= max) out.push(t);
  }
  return [...new Set(out)];
}

/** The smallest gap between neighbouring ticks, skipping the nulls uPlot filters out. */
function tickStep(splits) {
  const ticks = splits.filter((v) => v != null);
  let step = Infinity;
  for (let i = 1; i < ticks.length; i++) {
    const gap = Math.abs(ticks[i] - ticks[i - 1]);
    if (gap > 0 && gap < step) step = gap;
  }
  return step;
}

/**
 * How many decimals neighbouring ticks need to read differently. uPlot's
 * default follows the magnitude of the values, so a refined cell edge spanning
 * 1e-4 Å printed `10.251` five times (finding 3). This follows the step, and
 * then every tick, since a √ axis's ticks are not multiples of the smallest gap
 * and 1003.5 printed as `1004` beside a step of 2.
 */
export function tickDecimals(splits) {
  const step = tickStep(splits);
  if (!Number.isFinite(step)) return 0;
  const values = [step, ...splits.filter((v) => v != null)];
  let d = Math.max(0, -Math.floor(Math.log10(step)));
  // a step of 0.25 needs two decimals where its magnitude says one
  while (d < 15) {
    const f = 10 ** d, slack = 1e-6 * step * f;
    if (values.every((v) => Math.abs(Math.round(v * f) - v * f) <= slack)) break;
    d++;
  }
  return d;
}

/** Labels for `splits` at the precision their step needs. */
export function tickLabels(splits) {
  const d = tickDecimals(splits), step = tickStep(splits);
  // a tick that should be zero can arrive as 1e-17, and would print as "-0.000"
  const zero = Number.isFinite(step) ? step * 1e-9 : 0;
  return splits.map((v) => (v == null ? "" : (Math.abs(v) <= zero ? 0 : v).toFixed(d)));
}

/**
 * `values` placed at `index` in an array of `n` nulls.
 *
 * A uPlot chart has one x array (finding 10), so every series is drawn over
 * the pattern's own channel list. The fit's arrays cover only the channels it
 * kept, and `index` says which those are. A null is a gap uPlot does not draw.
 */
export function scatter(n, index, values) {
  const out = new Array(n).fill(null);
  for (let q = 0; q < index.length; q++) out[index[q]] = values[q];
  return out;
}

/**
 * `y` split in two over the same channels: the ones `index` names, and the
 * rest. Each is null where the other is drawn, so the observed pattern draws
 * as the fitted points and the masked ones in two styles on one x.
 */
export function partition(y, index) {
  const inside = new Array(y.length).fill(null), outside = Array.from(y);
  for (let q = 0; q < index.length; q++) {
    const i = index[q];
    inside[i] = y[i];
    outside[i] = null;
  }
  return [inside, outside];
}

// ---------------------------------------------------------------- drawing half

/** A CSS custom property's value on `el`, read at the moment of the call. */
export function token(name, el = document.documentElement) {
  return getComputedStyle(el).getPropertyValue(name).trim();
}

/** The drag threshold, in CSS pixels, below which a box zoom becomes one axis. plotly's is 20. */
export const UNI = 20;

/**
 * The distance, in CSS pixels, a press must travel to be a drag. plotly's is 8.
 * Below `UNI` uPlot forces a drag onto one axis and spans the other, so without
 * this a click that moved one pixel zoomed x to a one-pixel window.
 */
export const CLICK = 8;

const TYPES = ["lin", "sqrt", "log"];

function yScale(uPlot, kind, pinned, fixed) {
  // a band of rows, like the reflection ticks, has a range of its own and no zoom
  if (fixed) return { range: () => fixed };
  if (!TYPES.includes(kind)) throw new Error(`rxplot: no y scale "${kind}"; one of ${TYPES.join(", ")}`);
  const auto = kind === "log"
    ? (u, min, max) => uPlot.rangeLog(min, max, 10, true)
    : (u, min, max) => uPlot.rangeNum(min, max, 0.1, true);
  // a y range the reader zoomed to is held across every x zoom until a reset
  const range = (u, min, max) => pinned() ?? auto(u, min, max);
  if (kind === "log") return { distr: 3, log: 10, range };
  if (kind === "sqrt") {
    return { distr: 100, range,
             fwd: (v) => Math.sign(v) * Math.sqrt(Math.abs(v)),
             bwd: (v) => Math.sign(v) * v * v };
  }
  return { range };
}

function axes(spec, gutter) {
  const ink = () => token("--fg"), line = () => token("--line");
  const x = { stroke: ink, grid: { stroke: line, width: 1 }, ticks: { stroke: line } };
  if (!spec.xLabels) Object.assign(x, { values: (u, s) => s.map(() => ""), size: 6 });
  const y = { stroke: ink, grid: { stroke: line, width: 1 }, ticks: { stroke: line }, size: gutter };
  if (spec.y === "sqrt") {
    y.splits = (u, i, min, max) => sqrtSplits(min, max);
    // uPlot filters labels for a log axis on `distr >= 3`, which a √ scale's 100
    // is, so without this every label but a power of ten printed blank
    y.filter = (u, splits) => splits;
  }
  if (spec.y !== "log") y.values = (u, splits) => tickLabels(splits);
  return [x, y];
}

/**
 * Panes stacked in `host`, sharing one x.
 *
 * `spec.x` is the one x array. Each of `spec.panes` is `{ key, series, data }`
 * plus optional `height` (CSS px), `y` ("lin", "sqrt" or "log"), `range` (a
 * fixed y range, which no drag zooms), `xLabels`, and `hooks` merged into
 * uPlot's.
 * `series` and `data` leave out the x, which the group supplies.
 *
 * The group answers the gestures every page shares:
 *
 * - A drag zooms the pane it starts in: x only when it is flat, y only when it
 *   is narrow, both when it is a box. A y range the reader chose holds across x
 *   zooms until a double-click resets every pane.
 * - The wheel zooms x around the pointer. Shift-wheel and alt-drag pan.
 * - In "select" mode a drag calls `onSelect(lo, hi, key)` once, from the pane it
 *   started in, and zooms nothing.
 * - The pointer calls `onCursor({ key, idx, x, left, top })`, or `onCursor(null)`
 *   as it leaves. Only the pane under the pointer calls it.
 * - A `ResizeObserver` on `host` widens every pane in the frame the host changed.
 *
 * The panes share their cursor through uPlot's sync, and nothing else: a drag's
 * mousedown and mouseup stay in their own pane. Synced, a drag selected in every
 * pane at once, and a select handler ran once per pane (finding 1). The x range
 * is copied by value rather than by sync, and never onto a pane already at it,
 * because every `setScale` repaints its pane (finding 12).
 */
export function panes(uPlot, host, spec) {
  const gutter = spec.gutter ?? 64, sync = spec.sync ?? `rx-${Math.random().toString(36).slice(2)}`;
  const group = { panes: {}, mode: "zoom", onSelect: null, onCursor: null };
  const pins = {}, divs = {}, specs = {};
  let pointer = null;

  group.setX = (lo, hi) => {
    for (const u of Object.values(group.panes)) {
      if (u.scales.x.min !== lo || u.scales.x.max !== hi) u.setScale("x", { min: lo, max: hi });
    }
  };

  function zoom(u, key) {
    const s = u.select, w = u.over.clientWidth, h = u.over.clientHeight;
    const xs = !(s.left <= 0 && s.width >= w - 0.5);
    const ys = !(s.top <= 0 && s.height >= h - 0.5) && !specs[key].range;
    if (ys) {
      const lo = u.posToVal(s.top + s.height, "y"), hi = u.posToVal(s.top, "y");
      pins[key] = [lo, hi];
      u.setScale("y", { min: lo, max: hi });
    }
    if (xs) group.setX(u.posToVal(s.left, "x"), u.posToVal(s.left + s.width, "x"));
  }

  function onSelect(u) {
    const key = u.__rxKey, s = u.select;
    if (group.mode === "select") {
      group.onSelect?.(u.posToVal(s.left, "x"), u.posToVal(s.left + s.width, "x"), key);
    } else {
      zoom(u, key);
    }
    u.setSelect({ left: 0, top: 0, width: 0, height: 0 }, false);
  }

  function onCursor(u) {
    if (u.__rxKey !== pointer || !group.onCursor) return;
    const { left, top, idx } = u.cursor;
    if (left == null || left < 0 || idx == null) { group.onCursor(null); return; }
    group.onCursor({ key: u.__rxKey, idx, x: u.posToVal(left, "x"), left, top });
  }

  function gestures(u, key) {
    u.over.addEventListener("wheel", (e) => {
      e.preventDefault();
      const { min, max } = u.scales.x;
      if (e.shiftKey || Math.abs(e.deltaX) > Math.abs(e.deltaY)) {
        const d = (max - min) * (e.deltaX || e.deltaY) / 1000;
        group.setX(min + d, max + d);
      } else {
        const x = u.posToVal(e.offsetX, "x"), f = Math.exp(e.deltaY * 0.002);
        group.setX(x - (x - min) * f, x + (max - x) * f);
      }
    }, { passive: false });
    // alt-drag pans; in the capture phase, so uPlot never starts a select
    u.root.addEventListener("mousedown", (e) => {
      if (!e.altKey) return;
      e.stopPropagation();
      e.preventDefault();
      const x0 = e.clientX, { min, max } = u.scales.x, perPx = (max - min) / u.over.clientWidth;
      const move = (ev) => { const d = (ev.clientX - x0) * perPx; group.setX(min - d, max - d); };
      const up = () => { removeEventListener("mousemove", move); removeEventListener("mouseup", up); };
      addEventListener("mousemove", move);
      addEventListener("mouseup", up);
    }, true);
    u.over.addEventListener("dblclick", () => group.reset());
    u.over.addEventListener("mouseenter", () => { pointer = key; });
    u.over.addEventListener("mouseleave", () => { pointer = null; group.onCursor?.(null); });
  }

  function build(p) {
    const key = p.key;
    const hooks = { ...(p.hooks ?? {}) };
    const extend = (name, fn) => { hooks[name] = [...(hooks[name] ?? []), fn]; };
    extend("setScale", (u, k) => { if (k === "x") group.setX(u.scales.x.min, u.scales.x.max); });
    extend("setSelect", onSelect);
    extend("setCursor", onCursor);
    const u = new uPlot({
      width: host.clientWidth, height: p.height ?? 200, legend: { show: false },
      scales: { x: { time: false }, y: yScale(uPlot, p.y ?? "lin", () => pins[key] ?? null, p.range) },
      axes: axes(p, gutter),
      series: [{}, ...p.series],
      cursor: {
        sync: { key: sync, setSeries: false, scales: ["x", null],
                filters: { pub: (type) => type !== "mousedown" && type !== "mouseup" && type !== "dblclick" } },
        drag: { x: true, y: group.mode === "zoom", uni: UNI, dist: CLICK, setScale: false },
        bind: { dblclick: () => null },
        points: { show: false }, y: false, focus: { prox: -1 },
      },
      hooks,
    }, [spec.x, ...p.data], divs[key]);
    u.__rxKey = key;
    group.panes[key] = u;
    gestures(u, key);
    return u;
  }

  for (const p of spec.panes) {
    divs[p.key] = host.appendChild(document.createElement("div"));
    specs[p.key] = p;
    build(p);
  }

  /** "zoom" or "select"; a select drag is x only. */
  group.setMode = (mode) => {
    group.mode = mode;
    for (const u of Object.values(group.panes)) u.cursor.drag.y = mode === "zoom";
  };

  /** Every pane back to the whole x range, and every y range back to its data. */
  group.reset = () => {
    for (const k of Object.keys(pins)) delete pins[k];
    for (const u of Object.values(group.panes)) u.setData(u.data, true);
  };

  /**
   * New numbers for one pane, the reader's zoom kept. `setData(…, false)`
   * re-ranges nothing, so an unzoomed y kept the old numbers' range. Setting x
   * at itself re-ranges y through its range function, which holds a pinned y.
   */
  group.setData = (key, data) => {
    const u = group.panes[key];
    u.setData([spec.x, ...data], false);
    u.setScale("x", { min: u.scales.x.min, max: u.scales.x.max });
  };

  /** Repaint every pane. Colours are functions read at each draw, so this is a theme switch (finding 5). */
  group.redraw = () => { for (const u of Object.values(group.panes)) u.redraw(false, true); };

  /**
   * A pane rebuilt on another y scale. uPlot takes its scales at construction
   * (finding 5), so a scale switch is a new pane, placed where the old one was
   * and shown at the same x.
   */
  group.setY = (key, kind) => {
    const old = group.panes[key], lo = old.scales.x.min, hi = old.scales.x.max, data = old.data.slice(1);
    old.destroy();
    delete pins[key];
    specs[key] = { ...specs[key], y: kind, data };
    build(specs[key]);
    group.setX(lo, hi);
  };

  // uPlot has no autosize. A ResizeObserver runs after layout and before paint,
  // and setSize commits in the microtask after it, so a new size shows in the
  // same frame, with no timer.
  const observer = new ResizeObserver(() => {
    for (const u of Object.values(group.panes)) {
      if (u.width !== host.clientWidth) u.setSize({ width: host.clientWidth, height: u.height });
    }
  });
  observer.observe(host);

  group.destroy = () => {
    observer.disconnect();
    for (const u of Object.values(group.panes)) u.destroy();
    for (const d of Object.values(divs)) d.remove();
  };
  return group;
}

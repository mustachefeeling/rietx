// The `rietx watch` page, the half that touches no DOM (WP-1430).
//
// Split out so the suite can run it: `tests/watch_core.test.mjs` imports this
// file under `node --test`, while `watch.mjs` imports it as a module script
// and owns every element on the page. Nothing here reads the document,
// localStorage or the network.
//
// The whole page was a python string until WP-1430, so none of this was ever
// called by a test — the two defects the track shipped (WP-1402's stray escape,
// WP-1405's invisible sheet) were both found by a person looking at a page.

// the Δ/σ panel's range is one of these, ±L: the one dimension on the page
// that is the fit's rather than the data's, so it may step, and only by a
// rung, only at a stage boundary
export const LADDER = [3, 5, 10, 20, 50, 100, 200, 500, 1000];

export function esc(s) {
  return String(s).replace(/[&<>"]/g, c =>
    ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
}

// One palette colour at an opacity, so a ground can sit over a curve without
// becoming a second authority for what that ground is. The legend moved inside
// the paper in WP-1426 and an opaque box there hid the tallest peak on a narrow
// panel. Anything that is not `#rgb` or `#rrggbb` comes back unchanged: a
// palette is data off the wire, and a colour this cannot read is better drawn
// as itself than dropped.
export function withAlpha(hex, alpha) {
  const m = /^#([0-9a-f]{3}|[0-9a-f]{6})$/i.exec(String(hex).trim());
  if (!m) return hex;
  const h = m[1].length === 3 ? m[1].replace(/./g, c => c + c) : m[1];
  const n = parseInt(h, 16);
  return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${alpha})`;
}

export function ago(t) {
  if (!t) return '—';
  const s = Date.now()/1000 - t;
  if (s < 60) return Math.max(0, Math.round(s)) + 's ago';
  if (s < 3600) return Math.round(s/60) + 'm ago';
  if (s < 86400) return Math.round(s/3600) + 'h ago';
  return Math.round(s/86400) + 'd ago';
}

// a non-finite Rwp round-trips as the string "NaN" (ser_json_inf_nan), and
// "NaN".toFixed would throw and cost the whole table its render
export function num(v, d) {
  return (typeof v === 'number' && isFinite(v)) ? v.toFixed(d) : '—';
}

// Δ/σ either way — it is what the fit minimised — and the flag changes only
// what the axis is called (WP-1029)
export function deltaTitle(weighted) {
  if (weighted === true) return 'Δ/σ  (σ from file)';
  if (weighted === false) return 'Δ/σ  (σ = √max(y,1))';
  return 'Δ/σ';
}

export function finiteOf(values) {
  return values.filter(v => v !== null && isFinite(v));
}

export function extent(values) {
  let lo = Infinity, hi = -Infinity;
  for (const v of values) { if (v < lo) lo = v; if (v > hi) hi = v; }
  return isFinite(lo) ? [lo, hi] : [0, 1];
}

// Every range is a function of the snapshot and nothing else, and two of the
// three are functions of the *data* part of it: the decimation keeps the
// first and last point and every bucket's extremes, so the 2θ span and the
// observed range read off the decimated arrays are the pattern's own, and
// they do not move while the fit does. The Δ/σ range is the fit's; it takes
// the ladder above, off the 99.9th percentile so one spiked point does not
// set the scale for a run while a misfitted peak of ten points still does.
export function rangesOf(snap) {
  const tt = snap.two_theta;
  const x0 = tt[0], x1 = tt[tt.length - 1], xs = (x1 - x0) || 1;
  const [lo, hi] = extent(finiteOf(snap.y_obs));
  const ys = (hi - lo) || 1;
  const d = finiteOf(snap.delta).map(Math.abs).sort((a, b) => a - b);
  const q = d.length ? d[Math.min(d.length - 1, Math.floor(0.999 * d.length))] : 0;
  const L = LADDER.find(v => v >= q) || Math.ceil(q);
  return {x: [x0 - 0.01 * xs, x1 + 0.01 * xs],
          y: [lo - 0.03 * ys, hi + 0.05 * ys], y2: [-L, L]};
}

// ------------------------------------------------------------- panels
// The stored panel state, and the one rule that moves it. `watch.mjs` owns
// the storage and the document; what is here is the reading and the rule.
//
// Two defaults in one expression: an absent key and a key holding anything
// unreadable both mean two open panels, and `!== false` means a stored state
// naming only one panel leaves the other open.
export function parsePanels(raw) {
  try {
    const saved = JSON.parse(raw || '{}');
    return {runs: saved.runs !== false, run: saved.run !== false};
  } catch (err) {
    return {runs: true, run: true};
  }
}

// A new state, never the one passed in: the caller reads its own copy back
// out of storage on the next click, and a reducer that mutates its argument
// is one refactor away from disagreeing with what was stored.
export function nextPanels(p, which) {
  const next = {runs: p.runs, run: p.run};
  next[which] = !next[which];
  // closing the last open panel opens the other: a page with neither is a
  // bar over nothing
  if (!next.runs && !next.run) next[which === 'runs' ? 'run' : 'runs'] = true;
  return next;
}

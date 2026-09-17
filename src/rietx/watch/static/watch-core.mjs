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

/**
 * The plot's colours, read from the custom properties `tokens.css` declares.
 *
 * The same shape as the GUI's `curveColors` (`gui/src/lib/plot.ts`) and for the
 * same reasons: the plot samples these at *draw* time, because a theme change
 * restyles the page by CSS alone while a canvas keeps whatever colours it was
 * painted with, and `read` is injected so this stays a pure function.
 *
 * No fallbacks, which is where it differs. The GUI's are for jsdom, a page with
 * no stylesheet at all; this page has one or is unstyled, and a fallback here
 * would be a fourth copy of the light palette for a case where every other
 * colour on the page is missing too.
 *
 * `grid` is `--line` and not `--plot-zero`: the GUI draws its gridlines in the
 * chrome's rule colour and keeps `--plot-zero` for the residual's zero, which
 * is a mark about the data. `band` is `--ok` — the ±3σ rectangle says the
 * residual is inside expectation, and the GUI has no counterpart to quote.
 */
export function paletteFrom(read) {
  const pick = (name) => (read(name) || '').trim();
  return {
    obs: pick('--plot-obs'), calc: pick('--plot-calc'), bkg: pick('--plot-bkg'),
    diff: pick('--plot-diff'), zero: pick('--plot-zero'), grid: pick('--line'),
    fg: pick('--fg'), ground: pick('--bg'), band: pick('--ok'),
    // One colour per phase, from the stylesheet like everything else here
    // (WP-1436). They used to ride on the poll's own payload, which meant the
    // page drew a *light* pattern's tick rows in the dark theme's list — the
    // server sent one list for both. These four do not follow the theme at
    // all, so there is no list to choose and no reason to send one.
    phase: [pick('--phase-0'), pick('--phase-1'),
            pick('--phase-2'), pick('--phase-3')].filter(Boolean),
  };
}

/**
 * The ink a phase's tick row is drawn in — the GUI's `phaseInk`, ported.
 *
 * A single phase takes the observed curve's neutral rather than the first
 * phase colour: colour is for telling rows apart, and one row has nothing to
 * be told apart from. Past the fourth the palette cycles, four being where
 * rows stop being nameable by colour.
 */
export function phaseInk(hue, index, count) {
  if (count <= 1 || !hue.phase.length) return hue.obs;
  return hue.phase[index % hue.phase.length];
}

// One palette colour at an opacity, so a ground can sit over a curve without
// becoming a second authority for what that ground is. The legend moved inside
// the paper in WP-1426 and an opaque box there hid the tallest peak on a narrow
// panel. Anything that is not `#rgb` or `#rrggbb` comes back unchanged: the
// colour is whatever the root element says it is now (WP-1429), and one this
// cannot read is better drawn as itself than dropped.
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

// An R factor is a percentage everywhere a person reads one: the GUI prints
// it that way in its report, its series table and its peak list, and so does
// every other Rietveld code. The fraction is the report layers' form, because
// they are quoted into prose. A list row is the GUI's series table, so it
// takes two decimals from there (`Series.svelte`) rather than inventing a
// third spelling.
export function pct(v, d) {
  return (typeof v === 'number' && isFinite(v))
    ? (v * 100).toFixed(d) + '%' : '—';
}

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

// The clock time a reader can match against their own terminal, and the
// column that tells forty rows of one batch apart (WP-1424). A batch names
// every run the same thing, so the second a run started is the first fact
// about it that differs — which is what the run directory is named after.
//
// Seconds only for a run started today. A time of day with no date on it is
// a lie about a run from last week, and the date is what a reader wants of
// one anyway; `ago` is still there, in the tooltip, for "how long ago".
export function clock(t, now) {
  if (!t) return '—';
  const d = new Date(t * 1000);
  const today = new Date((now === undefined ? Date.now() / 1000 : now) * 1000);
  const two = n => String(n).padStart(2, '0');
  const sameDay = d.getFullYear() === today.getFullYear()
    && d.getMonth() === today.getMonth() && d.getDate() === today.getDate();
  return sameDay
    ? `${two(d.getHours())}:${two(d.getMinutes())}:${two(d.getSeconds())}`
    : `${d.getDate()} ${MONTHS[d.getMonth()]}`;
}

// What a run is called. `label` is the working directory's name or the
// project's (`RunRecorder._default_label`), and `legacy` means there was no
// `meta.json` to read one from.
export function runLabel(run) {
  return run.label + (run.legacy ? ' · legacy' : '');
}

// What a run is called in a *list*, where it is one of many. Two sources, and
// the series label wins because it is the more specific of them.
//
// `label` is the caller's word when they passed one (WP-1431) and the working
// directory's or the project's when they did not. Unnamed, a batch driven from
// one directory gives every run the same label and a column of them names
// nothing — which is what the keyword exists for, and why what this returns is
// worth a column at all.
//
// `status.series_label` — which pattern this run fitted — stays ahead of it:
// one series is one run, so a caller's label there names the whole chain while
// the series label names the row. It replaces rather than joins, a
// `ramp-A · 250C` cut to `ramp-A…` by the column having shown the reader the
// half they already knew. The strip has a slot of its own for the series and
// so keeps the plain label in its label slot.
export function rowName(run) {
  return (run.status || {}).series_label || runLabel(run);
}

// Everything the record knows about which run this is, for the row's tooltip:
// the label, the directory it was written to (`YYYYMMDD-HHMMSS-<pid>`, which
// is the second it started), the command line that launched it, and where
// that was run. A reader scanning identical rows hovers one of them, and this
// is the answer.
export function runTitle(run) {
  const meta = run.meta || {};
  const stamp = String(run.path).split('/').pop();
  const lines = [`${runLabel(run)} · ${stamp}`];
  if (meta.command) lines.push(meta.command);
  if (meta.cwd) lines.push('in ' + meta.cwd);
  lines.push(run.path);
  return lines.join('\n');
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
// the ladder above, off a cut that drops the worst few points so one spiked
// point does not set the scale while a misfitted peak of ten still does.
//
// The cut is a **count**, not a fraction, which is WP-1426 correcting what
// WP-1430 found and pinned. Written as the 0.999 quantile it cut nothing at
// all below 1001 points, because a tenth of a percent of a short pattern is
// less than one point — so on a 1000-point pattern a lone 900σ spike put a
// residual of ±1 on a ±1000 axis, which is the panel showing nothing, and
// exactly what the quantile was there to prevent. `max(1, …)` is the whole
// fix: at least one point is always dropped, and above 1000 the count is the
// same few the quantile was dropping.
export function rangesOf(snap) {
  const tt = snap.two_theta;
  const x0 = tt[0], x1 = tt[tt.length - 1], xs = (x1 - x0) || 1;
  const [lo, hi] = extent(finiteOf(snap.y_obs));
  const ys = (hi - lo) || 1;
  const d = finiteOf(snap.delta).map(Math.abs).sort((a, b) => a - b);
  const cut = Math.max(1, Math.round(0.001 * d.length));
  const q = d.length ? d[Math.max(0, d.length - 1 - cut)] : 0;
  const L = LADDER.find(v => v >= q) || Math.ceil(q);
  return {x: [x0 - 0.01 * xs, x1 + 0.01 * xs],
          y: [lo - 0.03 * ys, hi + 0.05 * ys], y2: [-L, L]};
}

// ------------------------------------------------------------ splitters
// The drag arithmetic, ported from the GUI's `gui/src/lib/resize.ts`
// (WP-1029). The page cannot import TypeScript, so this is a copy, and a copy
// that is not pinned is a copy that drifts: `tests/watch_core.test.mjs` runs
// the GUI's own cases against these three, character for character, and
// `tests/test_watch_app.py` fails when the two case tables stop matching.
//
// Only what the page needs came over. `fitColumns`, `MODEL_MIN`, `GRIP`,
// `modelStacks` and `seriesCompact` are the GUI's own furniture and would
// rot here unread.

/** Which way the pointer travels to make the pane on the grip's side bigger. */
const AXIS = {up: 'y', down: 'y', left: 'x', right: 'x'};
const SIGN = {up: -1, down: 1, left: -1, right: 1};

// The pointer coordinate a grip reads; the other one is noise during a drag.
export function axisOf(grow) {
  return AXIS[grow];
}

// The size a pointer now at `at` asks for, having grabbed at `from` on a pane
// that was `start` px. Sign only: the clamping is the next function's.
export function dragged(start, from, at, grow) {
  return start + SIGN[grow] * (at - from);
}

// Clamp to the floor, and to whatever must survive of the pane next door.
//
// `available` is the extent the two panes share. Zero, or anything too small
// to hold `min + keep`, means nothing is measurable — a drag before the first
// layout — and then only the floor applies.
export function clampSize(value, min, keep, available) {
  const ceiling = available > keep + min ? available - keep : Number.POSITIVE_INFINITY;
  return Math.round(Math.min(Math.max(value, min), ceiling));
}

// Run `work` at most once at a time, and once more if it was asked while busy.
//
// The GUI measured the case this exists for (WP-1032 task 1): a 60-move drag
// issued 60 `Plotly.Plots.resize` calls against a ~111 ms redraw, and the last
// resolved 1.10 s after the drag ended, so the canvas trailed the grip by a
// second. The trailing re-run is the half that matters. Dropping the extras
// outright would leave the plot at whatever size the last accepted call
// started with, which on a drag is its beginning.
//
// `Plots.resize` returns a promise, so this awaits one; a synchronous `work`
// completes at once.
export function coalesce(work) {
  let running = false;
  let queued = false;
  const done = () => {
    running = false;
    if (queued) {
      queued = false;
      go();
    }
  };
  const go = () => {
    if (running) {
      queued = true;
      return;
    }
    running = true;
    let out;
    try {
      out = work();
    } catch (error) {
      done();
      throw error;
    }
    if (out && typeof out.then === 'function') {
      out.then(done, done);
    } else {
      done();
    }
  };
  return go;
}

// ---------------------------------------------------------------- layout
// What the reader chose about the two seams and the run pane, and the rule
// that moves it. `watch.mjs` owns the storage, the document and the pointer;
// what is here is the reading and the arithmetic.
//
// A seam's `size` is the px size of the pane the grip sizes, and `null` means
// *no choice made* — which is not the same as a number, because the CSS
// defaults (`80ch`, `30%`) are font- and window-relative and a px default
// would freeze them. `open` is the collapse.

//: The stored state of a page nobody has dragged.
//:
//: `run` is not a seam: no grip sizes it, so its `size` is always null and
//: only `open` moves (WP-1436). It is here rather than in a second key for
//: the reason the two seams are — one stored object, one reader, one shape.
export const LAYOUT_DEFAULT = Object.freeze({
  list: Object.freeze({size: null, open: true}),
  console: Object.freeze({size: null, open: true}),
  run: Object.freeze({size: null, open: true}),
});

// A size is a number or it is nothing. `Number('420')` is 420, and this is
// the page's own JSON, so a string here is corruption rather than a value in
// another spelling.
function seam(saved) {
  const size = saved ? saved.size : null;
  const ok = typeof size === 'number' && Number.isFinite(size) && size > 0;
  return {size: ok ? size : null, open: !(saved && saved.open === false)};
}

// Two defaults in one expression, as `parsePanels` had: an absent key and a
// key holding anything unreadable both mean open panes at their declared
// sizes, and a stored state naming only one of them leaves the others alone.
//
// `legacy` is WP-1423's `{runs, run}` under the old key, and both halves have
// a home again now that the run pane collapses (WP-1436). It is consulted only
// when this page has stored nothing itself, and the caller drops the old key
// once it has.
export function parseLayout(raw, legacy) {
  let saved = {};
  try {
    saved = JSON.parse(raw || '{}') || {};
  } catch (err) {
    saved = {};
  }
  const out = {list: seam(saved.list), console: seam(saved.console),
               run: seam(saved.run)};
  if (!saved.list && legacy) {
    try {
      const old = JSON.parse(legacy || '{}') || {};
      if (old.runs === false) out.list.open = false;
      if (old.run === false) out.run.open = false;
    } catch (err) {}
  }
  return out;
}

// A new layout, never the one passed in — `nextPanels`' rule, and for the
// same reason: the caller reads its own copy back out of storage next time,
// and a reducer that mutates its argument is one refactor away from
// disagreeing with what was stored.
export function nextLayout(layout, which, patch) {
  const next = {list: {...layout.list}, console: {...layout.console},
                run: {...layout.run}};
  next[which] = {...next[which], ...patch};
  return next;
}

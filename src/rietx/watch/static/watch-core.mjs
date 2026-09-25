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
 * The chart module reads the chrome's own colours, the axis ink and the grid,
 * itself (`rxplot.token`), so this names only the marks about the data.
 * `band` is `--ok`: the ±3σ rectangle says the residual is inside
 * expectation, and the GUI has no counterpart to quote.
 */
export function paletteFrom(read) {
  const pick = (name) => (read(name) || '').trim();
  return {
    obs: pick('--plot-obs'), calc: pick('--plot-calc'), bkg: pick('--plot-bkg'),
    diff: pick('--plot-diff'), zero: pick('--plot-zero'), band: pick('--ok'),
    // One colour per phase, from the stylesheet like everything else here
    // (WP-1438). They used to ride on the poll's own payload, which meant the
    // page drew a *light* pattern's tick rows in the dark theme's list — the
    // server sent one list for both. These four do not follow the theme at
    // all, so there is no list to choose and no reason to send one.
    phase: PHASE_TOKENS.map(pick).filter(Boolean),
  };
}

// The tick rows' colours, in the order a row takes them. The canvas reads
// their values (`paletteFrom`) and the legend names the properties
// (`legendOf`), so the two agree on which row wears which by construction.
export const PHASE_TOKENS = ['--phase-0', '--phase-1', '--phase-2', '--phase-3'];

/**
 * The legend's entries for a snapshot, in the order they are drawn.
 *
 * `id` is the chart's name for the curve (`rxplot.pattern`'s `hidden`),
 * `ink` the custom property it is drawn in, and `mark` the swatch's shape.
 * Each entry names a property rather than a colour, so a theme switch
 * restyles the legend by CSS alone.
 *
 * An all-zero background is no background, and gets no entry. A tick row
 * takes the observed points' neutral when it is the only one: colour tells
 * rows apart, and one row has nothing to be told from. That is the GUI's
 * `phaseInk` (`gui/src/lib/plot.ts`), which the chart module draws the rows
 * with. A capped row says so in its label, because a silent cap reads as
 * coverage.
 */
export function legendOf(snap) {
  const out = [
    {id: 'obs', label: 'observed', ink: '--plot-obs', mark: 'dot'},
    {id: 'calc', label: 'calculated', ink: '--plot-calc', mark: 'line'},
  ];
  if (hasBackground(snap)) {
    out.push({id: 'bkg', label: 'background', ink: '--plot-bkg', mark: 'dash'});
  }
  out.push({id: 'diff', label: 'Δ/σ', ink: '--plot-diff', mark: 'line'});
  const names = Object.keys(snap.ticks || {});
  names.forEach((name, i) => {
    const row = snap.ticks[name];
    const label = row.n_total > row.two_theta.length
      ? `hkl: ${name} (${row.two_theta.length} of ${row.n_total})`
      : `hkl: ${name}`;
    out.push({id: `ticks:${name}`, label: label, mark: 'tick',
              ink: names.length <= 1 ? '--plot-obs'
                : PHASE_TOKENS[i % PHASE_TOKENS.length]});
  });
  return out;
}

/** Whether a stage has a background to draw: a free background is never all zero. */
export function hasBackground(snap) {
  return (snap.y_bkg || []).some(v => v);
}

/**
 * A snapshot as a curves payload (`rxplot.unpack`'s shape), which is what the
 * chart module draws.
 *
 * A snapshot holds the fitted channels alone, so every channel it carries is
 * both kept and fitted, and the model's arrays are already on its grid. The
 * arrays stay the JSON's own: a `null` in them is a gap the chart must not
 * draw, and a typed array would make it a zero.
 */
export function curvesOf(snap) {
  const n = snap.two_theta.length;
  const every = Int32Array.from({length: n}, (_, i) => i);
  const ticks = {};
  for (const [name, row] of Object.entries(snap.ticks || {})) {
    ticks[name] = row.two_theta;
  }
  return {
    header: {fit: true, weighted: snap.weighted, ticks: ticks},
    arrays: {two_theta: snap.two_theta, y_obs: snap.y_obs, kept: every,
             fitted: every, y_calc: snap.y_calc, y_background: snap.y_bkg,
             delta: snap.delta},
  };
}

/**
 * What the pointer on tick `j` of `row` says: its Miller index over its 2θ.
 *
 * A row written before WP-1438 has positions and no indices, since `rietx
 * watch` opens directories somebody else wrote. It says its 2θ alone, rather
 * than a label reading `undefined`.
 */
export function tickText(row, j) {
  const at = `${row.two_theta[j].toFixed(4)}°`;
  const indexed = Array.isArray(row.hkl)
    && row.hkl.length === row.two_theta.length;
  return indexed ? `${hklLabel(row.hkl[j])}\n${at}` : at;
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
// Why a run offers no GUI command, or `null` when it offers one — and `null`
// too when *no* run does, because then the reason is not about this run.
//
// A cell that is simply empty is an answer the reader has to guess at
// (WP-1076's rule from the page's side): a run recorded by a bare `fit()`
// sits in the list beside one a project recorded, and the difference between
// them showed only as a missing button.
export function guiReason(run, canOpen) {
  if (!canOpen) return null;
  if (run && run.gui_command) return null;
  return 'No project to open. This run was recorded outside a .rex project, '
    + 'so there is no project directory for the GUI to copy. A fit records '
    + 'into a project when it is run through one.';
}

// A Miller index as a reader writes one: `(1 0 −1)`.
//
// Spaced, because `(10-4)` is what `join('')` makes of `[1, 0, -4]` and a
// two-digit index makes it worse. The minus goes in front of the digit
// rather than over it: the crystallographer's overbar needs a combining
// mark per digit, and a hover box is not the place to find out whether the
// reader's font has one. It is U+2212, which is the minus the rest of this
// page's prose uses.
//
// The twin of `gui/src/lib/peaks.ts`'s `formatHkl`, and `plot.test.ts`
// holds the two equal over a table of cases. Neither can import the other
// — this file ships in the wheel and `gui/src` is a build input that does
// not — so the guard is that table, run against both. Two pages showing
// one reflection two ways is the shape `viz/theme.py` exists to stop.
export function hklLabel(hkl) {
  if (!Array.isArray(hkl) || hkl.length !== 3) return '';
  return `(${hkl.map(v => (v < 0 ? `−${Math.abs(v)}` : String(v))).join(' ')})`;
}

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

// The intensity range is the *data*'s: the observed points' extent over
// `values`, the channels in view, padded -3 % and +5 %. The model is left
// out, so a stage whose calculated curve overshoots the pattern tenfold does
// not shrink the pattern to a line along the axis, and the range moves only
// when the view does. The decimation keeps every bucket's extremes, so the
// whole pattern's range read off a snapshot is the pattern's own.
export function intensityRange(values) {
  const [lo, hi] = extent(finiteOf(values));
  const ys = (hi - lo) || 1;
  return [lo - 0.03 * ys, hi + 0.05 * ys];
}

// The Δ/σ range is the fit's. It takes the ladder above, off a cut that drops
// the worst few points, so one spiked point does not set the scale while a
// misfitted peak of ten still does. It is read over the whole snapshot and not
// the view, so a zoom does not re-scale the residual under the reader: the
// band at ±3 is the reference, and it stays the same size.
//
// The cut is a **count**, not a fraction, which is WP-1426 correcting what
// WP-1430 found and pinned. Written as the 0.999 quantile it cut nothing at
// all below 1001 points, because a tenth of a percent of a short pattern is
// less than one point — so on a 1000-point pattern a lone 900σ spike put a
// residual of ±1 on a ±1000 axis, which is the panel showing nothing, and
// exactly what the quantile was there to prevent. `max(1, …)` is the whole
// fix: at least one point is always dropped, and above 1000 the count is the
// same few the quantile was dropping.
export function deltaRange(delta) {
  const d = finiteOf(delta).map(Math.abs).sort((a, b) => a - b);
  const cut = Math.max(1, Math.round(0.001 * d.length));
  const q = d.length ? d[Math.max(0, d.length - 1 - cut)] : 0;
  const L = LADDER.find(v => v >= q) || Math.ceil(q);
  return [-L, L];
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
//: only `open` moves (WP-1438). It is here rather than in a second key for
//: the reason the two seams are — one stored object, one reader, one shape.
export const LAYOUT_DEFAULT = Object.freeze({
  list: Object.freeze({size: null, stackedSize: null, open: true}),
  console: Object.freeze({size: null, open: true}),
  run: Object.freeze({size: null, open: true}),
});

// A size is a number or it is nothing. `Number('420')` is 420, and this is
// the page's own JSON, so a string here is corruption rather than a value in
// another spelling.
function size(saved, key) {
  const value = saved ? saved[key] : null;
  const ok = typeof value === 'number' && Number.isFinite(value) && value > 0;
  return ok ? value : null;
}

// `stacks` is the list and only the list, which is the one pane that changes
// what its size *means* when the window turns (WP-1438). It keeps a second
// number rather than reinterpreting the first: a px width is not a px height,
// so one number for both arrangements hands the reader a pane they never
// asked for the moment the window narrows. Chrome DevTools keeps a setting
// per orientation for the same reason.
//
// The other two have no key rather than a null one — a field nothing ever
// reads is a declared name with no writer (WP-1076).
function seam(saved, {stacks = false} = {}) {
  const out = {size: size(saved, 'size'),
               open: !(saved && saved.open === false)};
  if (stacks) out.stackedSize = size(saved, 'stackedSize');
  return out;
}

// Two defaults in one expression, as `parsePanels` had: an absent key and a
// key holding anything unreadable both mean open panes at their declared
// sizes, and a stored state naming only one of them leaves the others alone.
//
// `legacy` is WP-1423's `{runs, run}` under the old key, and both halves have
// a home again now that the run pane collapses (WP-1438). It is consulted only
// when this page has stored nothing itself, and the caller drops the old key
// once it has.
export function parseLayout(raw, legacy) {
  let saved = {};
  try {
    saved = JSON.parse(raw || '{}') || {};
  } catch (err) {
    saved = {};
  }
  const out = {list: seam(saved.list, {stacks: true}),
               console: seam(saved.console), run: seam(saved.run)};
  if (!saved.list && legacy) {
    try {
      const old = JSON.parse(legacy || '{}') || {};
      if (old.runs === false) out.list.open = false;
      if (old.run === false) out.run.open = false;
    } catch (err) {}
  }
  return out;
}

// Which field of a seam holds the size that is in force. The collapse is one
// fact about the list whichever way the panes sit, so it is not keyed; the
// size is two.
export function sizeField(which, isStacked) {
  return (which === 'list' && isStacked) ? 'stackedSize' : 'size';
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

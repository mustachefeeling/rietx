// The `rietx watch` page, the half that owns the document (WP-1430).
//
// A module script, so nothing here is a global and the page's own functions
// cannot collide with plotly's. The functions that touch no DOM are next door
// in `watch-core.mjs`, where the suite can call them.
import {ago, deltaTitle, esc, nextPanels, num, parsePanels, rangesOf,
        withAlpha} from './watch-core.mjs';

const $ = id => document.getElementById(id);
let SINGLE = null;          // set when the served directory is itself a run
let CAN_CANCEL = false;     // false under --read-only: no button is drawn
// what the strip says after a stop was asked for, or after one was refused.
// A fit does not stop the instant the button is clicked — a cadence plus the
// residual evaluation in flight, which on a large pattern is the larger term —
// and a page that showed nothing in between would read as one that had missed
// the click
let notice = null;
let timer = null;
let tail = {offset: 0, inode: null, id: null};
// what the run panel was built for: the run, which kind of picture it has
// ('json', a legacy 'html' page, or 'none'), and which write we have drawn
let shell = {id: null, kind: null, mtime: null};
// the last list the server sent, by id: the run panel reads its run from
// here rather than fetching it again
let rows = new Map();
let newest = null;
// plotly is fetched once per page, on the first run that needs it — never
// for the run list alone, which would be 4 MB to draw a table
let plotlyPromise = null;
// What this build is called and what it draws with, read off the first
// `api/runs` (WP-1430). They were `@TOKEN@` substitutions into the page's text
// while the page was a python string; a file cannot carry those, and a literal
// here would be a second authority for a fact `_about.py` and
// `viz/plots.PALETTES` already own.
let HUE = null;             // PALETTES['dark'] — one answer for three pages
let DIST = '';              // the distribution name
// the console is a tail and not an archive; the log on disk is the archive
const MAX_LINES = 2000;
const PANELS_KEY = 'rietx-watch-panels';

// text is written only when it changed: assigning the same string still
// replaces the node, and a replaced node is a layout
function setText(el, s) {
  if (el.textContent !== s) el.textContent = s;
}
function setAttr(el, name, value) {
  if (value === null || value === undefined) {
    if (el.hasAttribute(name)) el.removeAttribute(name);
  } else if (el.getAttribute(name) !== String(value)) {
    el.setAttribute(name, value);
  }
}
function setPill(el, live) {
  setText(el, live.state);
  setAttr(el, 'class', 'state ' + live.state);
  setAttr(el, 'title', live.evidence);
}

// ---------------------------------------------------------------- list
function makeRow(run) {
  const tr = document.createElement('tr');
  tr.className = 'run';
  tr.dataset.id = run.run_id;
  tr.innerHTML = '<td><span class="state"></span></td><td></td><td></td>' +
    '<td class="num"></td><td class="num"></td><td class="muted"></td>';
  tr.onclick = () => { location.hash = '#/run/' + run.run_id; };
  return tr;
}

function fillRow(tr, run) {
  const st = run.status || {};
  const td = tr.children;
  setPill(td[0].firstElementChild, run.liveness);
  setText(td[1], run.label + (run.legacy ? ' · legacy' : ''));
  setAttr(td[1], 'title', run.path);
  setText(td[2], st.stage || '—');
  setText(td[3], num(st.rwp, 4));
  setText(td[4], num(st.gof, 2));
  setText(td[5], ago(run.created));
  tr.classList.toggle('selected', run.run_id === currentId());
}

// Patched, never rebuilt: a row is keyed by its run id and moved into the
// server's order, so a list longer than the window keeps its scroll and a
// row the pointer is on keeps its hover. Rebuilding the table on every poll
// threw both away twenty-one times in a 25 s probe (WP-1423).
// The first row the reader can still see, or null when the list is at its top.
// Chosen by rectangle, which is what "on screen" means, and reported as an
// `offsetTop`, which is a position in the flow and so survives the scrolling
// this is about to do.
function visibleAnchor(tbody, box) {
  if (box.scrollTop <= 0) return null;
  const top = box.getBoundingClientRect().top;
  return [...tbody.children].find(tr =>
    tr.getBoundingClientRect().bottom > top) || null;
}

function patchList(runs) {
  const tbody = $('rows');
  const box = $('runs');
  // Hold the reader's place across an arrival. A new run is prepended, so
  // every row below it moves down a row's height and the whole list shifts
  // under the eye: one arrival on a scrolled list scored 0.0134 of layout
  // shift across four rows (WP-1426). The chat-log answer is to anchor on a
  // row the reader can see and move the scroll by however far that row moved.
  // Insertions above it are then compensated exactly, and an insertion below
  // it, which moves it not at all, is left alone. A list already at its top is
  // also left alone: there the arriving run is the thing being watched for,
  // and holding the viewport would scroll it straight out of sight.
  const anchor = visibleAnchor(tbody, box);
  const was = anchor ? anchor.offsetTop : 0;
  const want = new Set(runs.map(r => r.run_id));
  for (const tr of [...tbody.children]) {
    if (!want.has(tr.dataset.id)) tr.remove();
  }
  runs.forEach((run, i) => {
    let tr = tbody.querySelector(`tr[data-id="${run.run_id}"]`);
    if (!tr) tr = makeRow(run);
    const at = tbody.children[i] || null;
    if (at !== tr) tbody.insertBefore(tr, at);
    fillRow(tr, run);
  });
  $('empty').hidden = runs.length > 0;
  // a row the walk dropped cannot say where it went, and the reader has lost
  // that place whatever we do
  if (anchor && anchor.isConnected && anchor.offsetTop !== was) {
    box.scrollTop += anchor.offsetTop - was;
  }
}

// -------------------------------------------------------------- run
function pictureKind(run) {
  if (run.has_snapshot) return 'json';
  if (run.has_legacy_snapshot) return 'html';
  return 'none';
}

// The picture alone. A run that had no snapshot when it was opened grows one
// at its first stage boundary, and the kind changing from 'none' to 'json' is
// what brings us back here.
function buildPicture(run, kind) {
  const picture = $('picture');
  const old = $('plot');
  // a scattergl plot holds a WebGL context; dropping the div leaks it
  if (old && old.tagName === 'DIV' && window.Plotly) window.Plotly.purge(old);
  picture.innerHTML = kind === 'json'
    ? '<div id="plot"></div>'
    : kind === 'html'
      ? `<iframe id="plot" src="${legacySrc(run)}"></iframe>`
      : '<div id="noplot">no picture here — this run wrote only its log</div>';
  $('run').classList.toggle('full', kind === 'none');
  // mtime null, never the run's: the shell is empty until something draws
  // into it, and carrying the run's write time here would say it had
  shell = {id: run.run_id, kind: kind, mtime: null};
  setText($('s-where'), whereOf(run));
}

// The console belongs to the run, not to the picture, so a tail is reset when
// the log it is following changes and not when the picture is rebuilt. The two
// shared a builder until WP-1426: a run opened before its first snapshot had
// its console wiped and re-fetched from offset 0 at that first stage boundary,
// 121 lines out and 121 back for no change, and a reader who had scrolled up
// to read was dropped at the bottom. The other reset is the route's, in
// `pumpEvents`, where a log that is a different file says so.
function resetTail(id) {
  tail = {offset: 0, inode: null, id: id};
  $('console').textContent = '';
}

// the mtime is in the URL rather than a cache-buster of its own: the same
// page keeps the same src, so the frame reloads exactly when the file was
// rewritten and not once a second
function legacySrc(run) {
  return `api/run/${run.run_id}/legacy?t=` + (run.snapshot_mtime || 0);
}

// One fetch per page, shared by every run the reader opens. The script tag is
// built here rather than sitting in the head because the run list needs no
// plotting library and 4 MB to draw a table is 4 MB wasted.
function ensurePlotly() {
  if (plotlyPromise) return plotlyPromise;
  plotlyPromise = new Promise(resolve => {
    const tag = document.createElement('script');
    tag.src = 'plotly.js';
    tag.onload = () => resolve(window.Plotly || null);
    tag.onerror = () => resolve(null);   // no plotly installed: say so, once
    document.head.appendChild(tag);
  });
  return plotlyPromise;
}

// Every mark below is `viz/html.py`'s, mode for mode and width for width.
// This page and the emailable one are two pictures of one fit, and a reader
// who flips between them must not have to relearn which curve is which.
function snapshotTraces(snap) {
  const tt = snap.two_theta;
  const traces = [
    {x: tt, y: snap.y_obs, name: 'observed', mode: 'markers',
     type: 'scattergl', marker: {size: 3, color: HUE.obs}},
    {x: tt, y: snap.y_calc, name: 'calculated', mode: 'lines',
     type: 'scattergl', line: {width: 1.2, color: HUE.calc}},
  ];
  if (snap.y_bkg.some(v => v)) {
    traces.push({x: tt, y: snap.y_bkg, name: 'background', mode: 'lines',
                 type: 'scattergl',
                 line: {width: 1, dash: 'dash', color: HUE.bkg}});
  }
  traces.push({x: tt, y: snap.delta, name: 'Δ/σ', mode: 'lines',
               type: 'scattergl', yaxis: 'y2',
               line: {width: 1, color: HUE.diff}});
  // the rows live on an axis of their own under the Δ/σ panel, one unit a
  // row: they are read against the residual above them and must not move
  // when it does
  const names = Object.keys(snap.ticks || {});
  names.forEach((name, i) => {
    const row = snap.ticks[name];
    // one row has nothing to be told apart from, so colour stays for when
    // there are several
    const colour = names.length === 1 ? HUE.tick
                                      : HUE.phase[i % HUE.phase.length];
    // the cap is in the legend, because a silent cap reads as coverage
    const label = row.n_total > row.two_theta.length
      ? `hkl: ${name} (${row.two_theta.length} of ${row.n_total})`
      : `hkl: ${name}`;
    traces.push({
      x: row.two_theta, y: row.two_theta.map(() => -i), name: label,
      mode: 'markers', type: 'scattergl', yaxis: 'y3', hoverinfo: 'x',
      marker: {symbol: 'line-ns-open', size: 7, color: colour},
    });
  });
  return traces;
}

// True when this write is dealt with — drawn, or deliberately given up on
// (no plotly, the reader moved on). False is "not drawn yet", and the caller
// leaves the write uncommitted so the next poll tries again: a dropped fetch
// on the last stage of a fit would otherwise leave the previous stage's
// picture up for good, there being no later write to notice.
async function drawSnapshot(id) {
  // a poll can reach here before the first `api/runs` has answered, and an
  // undrawn write is what `false` already means: the next poll draws it,
  // rather than this one throwing on a colour that is not in yet
  if (!HUE) return false;
  const plotly = await ensurePlotly();
  const div = $('plot');
  if (!div || currentId() !== id) return true;
  if (!plotly) {
    div.outerHTML = '<div id="noplot">this page draws with plotly: ' +
      `<code>pip install '${DIST}[viz]'</code></div>`;
    return true;
  }
  let snap;
  try {
    const r = await fetch(`api/run/${id}/snapshot`, {cache: 'no-store'});
    if (!r.ok) return false;
    snap = await r.json();
  } catch (err) {
    return false;                      // the console tail is not the plot's
  }
  if (currentId() !== id || !$('plot')) return true;
  const range = rangesOf(snap);
  const nrows = Math.max(1, Object.keys(snap.ticks || {}).length);
  // react, never newPlot: it keeps the reader's zoom across a stage, which is
  // the whole reason the picture stopped being a page that reloads
  plotly.react(div, snapshotTraces(snap), {
    margin: {l: 58, r: 14, t: 8, b: 56},   // room for the 2θ title
    // expectation 1 under a correct model, so the residual reads on an
    // absolute statistical scale (Toby 2024) — the same band `viz/html.py`
    // draws
    shapes: [{type: 'rect', xref: 'paper', yref: 'y2', x0: 0, x1: 1,
              y0: -3, y1: 3, line: {width: 0}, fillcolor: HUE.band,
              opacity: 0.15, layer: 'below'}],
    paper_bgcolor: HUE.ground, plot_bgcolor: HUE.ground,
    font: {color: HUE.fg, family: 'ui-monospace, Menlo, monospace', size: 11},
    xaxis: {anchor: 'y3', title: {text: '2θ (°)'}, gridcolor: HUE.zero,
            zeroline: false, range: range.x, autorange: false},
    yaxis: {domain: [0.41, 1], title: {text: 'intensity'},
            gridcolor: HUE.zero, zeroline: false, range: range.y,
            autorange: false},
    yaxis2: {domain: [0.10, 0.36], anchor: 'x',
             title: {text: deltaTitle(snap.weighted)},
             gridcolor: HUE.zero, zerolinecolor: HUE.zero,
             range: range.y2, autorange: false},
    yaxis3: {domain: [0, 0.07], anchor: 'x', visible: false,
             range: [0.5 - nrows, 0.5], autorange: false, fixedrange: true},
    // Inside the paper at a fixed anchor, never above it. A legend anchored
    // in the top margin makes plotly grow that margin to fit, so the picture
    // moves whenever the legend gains a row. Two ways it gains one, both
    // measured on this page (WP-1426): the window narrows and the row wraps,
    // taking the plot area's top from 46 px to 139 px across 1400 → 700; or a
    // stage frees the background, and one new entry takes it 45 → 64. The
    // second is a stage boundary moving the whole picture, and no layout-shift
    // entry reports it, the div's own box never having changed. Anchored here
    // the area's top is the declared 8 px margin at every width, and the
    // picture is 38 px taller at 1400 and 131 px at 700. `bgcolor` is the
    // ground the paper already carries, at an opacity: opaque, the five rows
    // it wraps to on a narrow panel hid the tallest peak behind them.
    legend: {orientation: 'h', y: 1, yanchor: 'top', x: 0, xanchor: 'left',
             bgcolor: withAlpha(HUE.ground, 0.72)},
    // one revision per run: a redraw of the same run keeps the zoom, and
    // opening a different run starts fresh
    uirevision: id,
  }, {displaylogo: false, responsive: true});
  setText($('s-where'), `${snap.n_drawn} of ${snap.n_points} pts drawn · ` +
                        whereOf(rows.get(id)));
  return true;
}

function whereOf(run) {
  if (!run) return '';
  return run.gui_command ? `${run.gui_command} · ${run.path}` : run.path;
}

function fillStrip(run) {
  const st = run.status || {};
  setPill($('s-state'), run.liveness);
  setText($('s-label'), run.label);
  setAttr($('s-label'), 'title', run.path);
  setText($('s-series'), st.series_index != null
    ? `pattern ${st.series_index + 1}/${st.series_n || '?'} ` +
      `${st.series_label || ''} ${st.series_pass || ''}`.trim()
    : '');
  setText($('s-stage'), st.stage
    ? (st.index != null ? `stage ${st.index}/${st.n_stages || '?'} ` : 'stage ')
      + st.stage
    : '');
  setText($('s-rwp'), st.rwp != null ? 'Rwp ' + num(st.rwp, 4) : '');
  setText($('s-gof'), st.gof != null ? 'GoF ' + num(st.gof, 2) : '');
  setText($('s-free'), st.n_free != null ? st.n_free + ' free' : '');
  setText($('s-notice'), notice ? notice.text : '');
  // Drawn only for a run being written *here*: a terminal one has nothing
  // to stop, and 'unknown' covers both another host and a writer that keeps
  // no lock, where a request would sit in the directory doing nothing. The
  // route refuses the same set, so this is the courtesy and not the check.
  $('stop').hidden = !(CAN_CANCEL && !notice
                       && run.liveness.state === 'running');
}

function clearStrip() {
  setPill($('s-state'), {state: 'unknown', evidence: 'no run'});
  for (const id of ['s-label', 's-series', 's-stage', 's-rwp', 's-gof',
                    's-free', 's-where', 's-notice']) setText($(id), '');
  setText($('s-label'), 'no run');
  $('stop').hidden = true;
  if (shell.id !== null) {
    if ($('plot') && $('plot').tagName === 'DIV' && window.Plotly) {
      window.Plotly.purge($('plot'));
    }
    $('picture').innerHTML = '';
    shell = {id: null, kind: null, mtime: null};
    // the tail goes with the console it was filling, or a reader who came
    // back to this run would meet an empty console no poll ever refilled
    resetTail(null);
  }
}

async function drawRun(id) {
  const run = rows.get(id);
  if (!run) {                          // gone from the walk, or never in it
    if (location.hash) location.hash = '';
    clearStrip();
    return;
  }
  // a notice belongs to one run and one moment: the stop one stands until the
  // fit stops, a refusal clears on its own clock, and neither follows the
  // reader to another run
  if (notice && (notice.id !== id || Date.now() > notice.expires
                 || (notice.stop && run.liveness.state !== 'running'))) {
    notice = null;
  }
  // a running fit rewrites its snapshot per stage, and a run that had none
  // when it was opened grows one at its first
  const kind = pictureKind(run);
  if (tail.id !== id) resetTail(id);
  if (shell.id !== id || shell.kind !== kind) buildPicture(run, kind);
  fillStrip(run);
  // the write is recorded once it is on the page, never before: a draw that
  // did not happen must stay outstanding for the next poll
  if (kind !== 'none' && run.snapshot_mtime !== shell.mtime) {
    if (kind === 'json') {
      if (await drawSnapshot(id)) shell.mtime = run.snapshot_mtime;
    } else {
      shell.mtime = run.snapshot_mtime;
      const frame = $('plot');
      if (frame) frame.src = legacySrc(run);
    }
  }
  await pumpEvents(id);
}

// ----------------------------------------------------------------- stop
// Two clicks, and no keyboard shortcut of any kind: nothing takes focus when
// this opens, and neither Enter nor Escape reaches either button. Confirming
// raises an exception in a process the reader cannot see, and a stray
// keystroke must not be able to do that.
function openConfirm(run) {
  const st = run.status || {};
  const box = $('confirm');
  $('box-what').textContent =
    'Stop ' + run.label + (st.stage ? ', in stage ' + st.stage : '')
    + ', in the process that is running it?';
  $('box-no').onclick = () => { box.hidden = true; };
  $('box-yes').onclick = () => {
    box.hidden = true;
    stopRun(run.run_id);
  };
  box.hidden = false;
}

async function stopRun(id) {
  let payload = null, ok = false;
  try {
    const r = await fetch(`api/run/${id}/cancel`, {method: 'POST'});
    ok = r.ok;
    payload = await r.json();
  } catch (err) {
    payload = {error: String(err)};
  }
  notice = ok
    ? {id: id, text: 'stopping at the next evaluation …', stop: true,
       expires: Infinity}
    : {id: id, text: (payload && payload.error) || 'the stop was refused',
       stop: false, expires: Date.now() + 8000};
  refresh();
}

async function pumpEvents(id) {
  const q = new URLSearchParams({offset: tail.offset});
  if (tail.inode !== null) q.set('inode', tail.inode);
  const r = await fetch(`api/run/${id}/events?` + q, {cache: 'no-store'});
  if (!r.ok) return;
  const payload = await r.json();
  // an in-flight tail of the run we just left must not renumber this one
  if (tail.id !== id || currentId() !== id) return;
  const pane = $('console');
  if (payload.reset) pane.textContent = '';   // a different log; do not renumber
  tail.offset = payload.offset;
  tail.inode = payload.inode;
  if (!payload.events.length) return;
  // the tail follows the log only while the reader is at its end; a reader
  // who scrolled up to read is left where they are
  const atBottom = pane.scrollTop + pane.clientHeight >= pane.scrollHeight - 30;
  const html = payload.events.map(e => {
    const t = new Date(e.t * 1000).toLocaleTimeString();
    const data = Object.entries(e.data || {}).map(([k, v]) =>
      `${k}=${typeof v === 'number' ? +v.toPrecision(6)
              : Array.isArray(v) ? `[${v.length}]` : JSON.stringify(v)}`
    ).join(' ');
    return `<div class="line"><span class="ev">${t}</span> <span class="k">${esc(
      String(e.kind).padEnd(11))}</span> ${esc(data)}</div>`;
  }).join('');
  // append, never re-serialize: `innerHTML +=` reparses every line already
  // there, so a fit emitting an event per residual evaluation would pay for
  // its whole history on every poll
  pane.insertAdjacentHTML('beforeend', html);
  while (pane.childElementCount > MAX_LINES) pane.firstElementChild.remove();
  if (atBottom) pane.scrollTop = pane.scrollHeight;
}

// ------------------------------------------------------------- panels
function panels() {
  let raw = null;
  // reading it can throw as well as come back empty (a private window, site
  // data blocked), and both mean the same thing: no choice stored
  try { raw = localStorage.getItem(PANELS_KEY); } catch (err) {}
  return parsePanels(raw);
}
function applyPanels(p) {
  document.body.dataset.runs = p.runs ? 'open' : 'closed';
  document.body.dataset.run = p.run ? 'open' : 'closed';
  $('toggle-runs').setAttribute('aria-pressed', String(p.runs));
  $('toggle-run').setAttribute('aria-pressed', String(p.run));
  try { localStorage.setItem(PANELS_KEY, JSON.stringify(p)); } catch (err) {}
  // the plot's width just changed under it, and `responsive` only follows
  // the window
  const plot = $('plot');
  if (p.run && plot && plot.tagName === 'DIV' && window.Plotly) {
    window.Plotly.Plots.resize(plot);
  }
}
function togglePanel(which) {
  applyPanels(nextPanels(panels(), which));
}

// ------------------------------------------------------------- routing
// A run named in the URL is pinned. With none the page follows the newest,
// so opening `rietx watch` beside an agent's job shows what is happening
// now, and the row the reader clicks is the one that stays.
function currentId() {
  const m = location.hash.match(/^#\/run\/([0-9a-f]+)$/);
  return m ? m[1] : (SINGLE || newest);
}
// The page's constants, off whichever `api/runs` answers first. Once, and
// from any of them rather than only the boot fetch: every poll carries them,
// and a boot fetch that fails would otherwise leave `HUE` null for the life of
// the tab, with `drawSnapshot` declining every write while the list and the
// log recovered on the next poll.
function readPage(payload) {
  if (HUE || !payload.page) return;
  HUE = payload.page.palette;
  DIST = payload.page.dist;
  setText($('empty-suffix'), payload.page.suffix);
}

let refreshing = false;
async function refresh() {
  if (refreshing) return;              // a slow poll is not two polls
  refreshing = true;
  try {
    const r = await fetch('api/runs', {cache: 'no-store'});
    if (!r.ok) return;
    const payload = await r.json();
    readPage(payload);
    setText($('root'), 'scanned ' + payload.root);
    rows = new Map(payload.runs.map(run => [run.run_id, run]));
    newest = payload.runs.length ? payload.runs[0].run_id : null;
    patchList(payload.runs);
    const id = currentId();
    if (id) await drawRun(id); else clearStrip();
  } finally {
    refreshing = false;
  }
}
function schedule() {
  if (timer) clearInterval(timer);
  // polling stops when nobody is looking: a hidden tab costs the fit nothing
  timer = setInterval(() => { if (!document.hidden) refresh(); }, 1200);
}
window.addEventListener('hashchange', () => refresh());
document.addEventListener('visibilitychange', () => {
  if (!document.hidden) refresh();
});
$('toggle-runs').onclick = () => togglePanel('runs');
$('toggle-run').onclick = () => togglePanel('run');
$('stop').onclick = () => {
  const run = rows.get(currentId());
  if (run) openConfirm(run);
};

(async () => {
  const meta = await (await fetch('api/runs', {cache: 'no-store'})).json();
  SINGLE = meta.single_run_id;
  CAN_CANCEL = meta.can_cancel === true;
  readPage(meta);
  if (SINGLE) document.body.dataset.single = '';
  applyPanels(panels());
  await refresh();
  schedule();
})();

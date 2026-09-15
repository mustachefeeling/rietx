"""``rietx watch`` — a window into the refinements under a directory.

With no argument it scans the working directory and lists every run beneath it,
live ones and finished ones together, and opening one shows its plot and its
event log. With a directory argument that *is* a run it opens straight onto
that run, so ``rietx watch live/`` keeps working exactly as it did.

This module is **transport only**, the split ``gui/server.py`` declares for
itself. Finding runs, deciding whether one is still being written and tailing
its log are :mod:`rietx.runs`, which has no HTTP in it and which
``gui/session.py`` can import when it attaches to a foreign run.

**The watcher has one verb, and it is stop** (WP-1405). Everything else reads:
it opens no project, constructs no refinement, and offers the GUI as a command
to copy rather than a thing it launches. Stopping is the exception because it
is the one thing a reader cannot do from the other side, and it stays honest by
being the *only* one — ``POST /api/run/<id>/cancel`` writes
:data:`~rietx.runs.CANCEL_FILE` into a directory the walk already offered, and
the fit's own token is what acts on it. ``--read-only`` serves without it, for
a reader who is not the person who should be stopping things.

**A click here raises in another process.** That is the sharpest fact in this
module: a fit that did not ask to be cancellable is cancellable, and a script
that does not catch ``RefinementCancelled`` prints a traceback. It is why the
button takes two clicks, why the dialog says so in as many words, and why it
has no keyboard shortcut.

Run the refinement in one process::

    ref.fit(data, events=LiveSession("live/"))

and the viewer in another::

    rietx watch                  # every run under the working directory
    rietx watch live/            # straight onto one
"""

from __future__ import annotations

import functools
import http.server
import json
import os
import threading
import time
import urllib.parse
from pathlib import Path

from . import runs as runs_mod
from ._about import DIST_NAME, LIVE_DIR_NAME, PROJECT_SUFFIX
from .viz.plotlyjs import CONTENT_TYPE as PLOTLY_CONTENT_TYPE
from .viz.plotlyjs import plotly_js
from .viz.plots import PALETTES

_PAGE_TEMPLATE = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>rietx watch</title>
<style>
  :root { color-scheme: dark; }
  body { margin:0; font-family: ui-monospace, Menlo, monospace; font-size:12px;
         background:#111; color:#cdc; display:flex; flex-direction:column;
         height:100vh; }
  a { color:#9ad; text-decoration:none; }
  a:hover { text-decoration:underline; }
  #bar { background:#1c1c1c; border-bottom:1px solid #2c2c2c; padding:7px 12px;
         display:flex; gap:14px; align-items:center; flex:0 0 auto; }
  #root { color:#777; }
  #body { flex:1 1 auto; overflow:auto; }
  table { border-collapse:collapse; width:100%; }
  th { text-align:left; color:#777; font-weight:normal; padding:6px 12px;
       border-bottom:1px solid #2c2c2c; position:sticky; top:0;
       background:#151515; }
  td { padding:6px 12px; border-bottom:1px solid #1e1e1e; }
  tr.run:hover { background:#181818; cursor:pointer; }
  .state { padding:1px 7px; border-radius:9px; font-size:11px; }
  .running   { background:#14361d; color:#6ede8a; }
  .done      { background:#1b2d3d; color:#79b8e8; }
  .failed    { background:#3d1b1b; color:#e88; }
  .cancelled { background:#332b16; color:#e8b339; }
  .abandoned { background:#332b16; color:#c9a227; }
  .unknown   { background:#242424; color:#888; }
  .num { text-align:right; font-variant-numeric: tabular-nums; }
  .muted { color:#666; }
  #empty { padding:28px 12px; color:#777; }
  #detail { display:flex; flex-direction:column; height:100%; }
  #plot { flex:1 1 68%; border:0; min-height:180px; }
  /* a pre-WP-1402 run left a self-contained page behind; it still opens, in
     the frame it was always shown in */
  iframe#plot { background:#fff; }
  /* a GUI project's run has no picture and never will, so the note is a
     line and the log gets the room rather than the other way round */
  #noplot { flex:0 0 auto; padding:7px 12px; color:#666;
            border-bottom:1px solid #2c2c2c; }
  #console { flex:0 0 30%; overflow-y:auto; background:#181818; font-size:11px;
             padding:6px 10px; white-space:pre; }
  #console.full { flex:1 1 auto; }
  .k { color:#e8b339; }
  .ev { color:#888; }
  code { background:#1c1c1c; padding:1px 5px; border-radius:3px; color:#9ad; }
  button { font: inherit; color:#cdc; background:#242424; cursor:pointer;
           border:1px solid #3a3a3a; border-radius:4px; padding:3px 9px; }
  button:hover { background:#2c2c2c; }
  #stop { border-color:#5a2c2c; color:#e88; }
  #stop:hover { background:#3d1b1b; }
  /* the overlay sits outside #body, which the 1.2 s poll rewrites whole */
  #confirm { position:fixed; inset:0; background:rgba(0,0,0,0.62);
             display:flex; align-items:center; justify-content:center;
             z-index:10; }
  /* an id selector outranks the browser's own `[hidden] {display:none}`, so
     without this the closed dialog is an invisible sheet over the whole page
     swallowing every click — including the one that opens it */
  #confirm[hidden] { display:none; }
  #box { background:#1a1a1a; border:1px solid #3a3a3a; border-radius:6px;
         max-width:33em; padding:16px 18px; line-height:1.5; }
  #box h3 { margin:0 0 9px; font-size:13px; font-weight:normal; color:#e88; }
  #box p { margin:0 0 9px; color:#bbb; }
  #box .row { display:flex; gap:9px; justify-content:flex-end;
              margin-top:14px; }
</style></head><body>
<div id="bar">
  <strong>rietx watch</strong>
  <span id="crumb"></span>
  <span id="root"></span>
</div>
<div id="body"><div id="empty">scanning …</div></div>
<div id="confirm" hidden><div id="box">
  <h3 id="box-what"></h3>
  <p>This raises <code>RefinementCancelled</code> in the process running the
     fit, at its next residual evaluation. A script that does not catch it
     prints a traceback and exits.</p>
  <p>The stages that already finished are kept, and the working state stands
     at the last of them.</p>
  <p>The stage in flight is abandoned: no history node, no committed
     parameters, and the model goes back to where that stage found it.</p>
  <div class="row">
    <button id="box-no">Keep running</button>
    <button id="box-yes">Stop the fit</button>
  </div>
</div></div>
<script>
const body = document.getElementById('body');
const crumb = document.getElementById('crumb');
const rootEl = document.getElementById('root');
let SINGLE = null;          // set when the served directory is itself a run
let CAN_CANCEL = false;     // false under --read-only: no button is drawn
// what the crumb says after a stop was asked for, or after one was refused.
// A fit does not stop the instant the button is clicked — a cadence plus the
// residual evaluation in flight, which on a large pattern is the larger term —
// and a page that showed nothing in between would read as one that had missed
// the click
let notice = null;
let timer = null;
let tail = {offset: 0, inode: null, id: null};
// what the detail shell was built for: the run, which kind of picture it has
// ('json', a legacy 'html' page, or 'none'), and which write we have drawn
let shell = {id: null, kind: null, mtime: null};
// plotly is fetched once per page, on the first detail view that needs it —
// never for the run list, which would be 4 MB to draw a table
let plotlyPromise = null;
// how much of the pattern the last draw showed, kept across polls
let drawn = '';
const HUE = @HUE@;
// the console is a tail and not an archive; the log on disk is the archive
const MAX_LINES = 2000;

function esc(s) {
  return String(s).replace(/[&<>"]/g, c =>
    ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
}
function ago(t) {
  if (!t) return '—';
  const s = Date.now()/1000 - t;
  if (s < 60) return Math.max(0, Math.round(s)) + 's ago';
  if (s < 3600) return Math.round(s/60) + 'm ago';
  if (s < 86400) return Math.round(s/3600) + 'h ago';
  return Math.round(s/86400) + 'd ago';
}
// a non-finite Rwp round-trips as the string "NaN" (ser_json_inf_nan), and
// "NaN".toFixed would throw and cost the whole table its render
function num(v, d) {
  return (typeof v === 'number' && isFinite(v)) ? v.toFixed(d) : '—';
}

// ---------------------------------------------------------------- list
async function drawList() {
  const r = await fetch('api/runs', {cache: 'no-store'});
  if (!r.ok) return;
  const payload = await r.json();
  rootEl.textContent = 'scanned ' + payload.root;
  crumb.textContent = '';
  if (!payload.runs.length) {
    body.innerHTML = '<div id="empty">No runs under this directory. ' +
      'A run is a directory holding an <code>events.jsonl</code> — pass one ' +
      'to <code>LiveSession</code>, or open a <code>@SUFFIX@</code> project in ' +
      'the GUI.</div>';
    return;
  }
  const rows = payload.runs.map(run => {
    const st = run.status || {};
    const gui = run.gui_command
      ? `<code>${esc(run.gui_command)}</code>` : '<span class="muted">—</span>';
    return `<tr class="run" data-id="${run.run_id}">
      <td><span class="state ${run.liveness.state}" title="${esc(run.liveness.evidence)}"
          >${run.liveness.state}</span></td>
      <td><a href="#/run/${run.run_id}">${esc(run.label)}</a>
          ${run.legacy ? '<span class="muted"> · legacy</span>' : ''}</td>
      <td>${esc(st.stage || '—')}</td>
      <td class="num">${num(st.rwp, 4)}</td>
      <td class="num">${num(st.gof, 2)}</td>
      <td class="muted">${ago(run.created)}</td>
      <td>${gui}</td></tr>`;
  }).join('');
  body.innerHTML = `<table><thead><tr>
    <th>state</th><th>run</th><th>stage</th><th class="num">Rwp</th>
    <th class="num">GoF</th><th>started</th><th>open in the GUI</th>
    </tr></thead><tbody>${rows}</tbody></table>`;
  for (const tr of body.querySelectorAll('tr.run')) {
    tr.onclick = ev => {
      if (ev.target.tagName !== 'CODE') location.hash = '#/run/' + tr.dataset.id;
    };
  }
}

// -------------------------------------------------------------- detail
function pictureKind(run) {
  if (run.has_snapshot) return 'json';
  if (run.has_legacy_snapshot) return 'html';
  return 'none';
}

function detailShell(run, kind) {
  const plot = kind === 'json'
    ? '<div id="plot"></div>'
    : kind === 'html'
      ? `<iframe id="plot" src="${legacySrc(run)}"></iframe>`
      : '<div id="noplot">no picture here — this run wrote only its log</div>';
  const cls = kind === 'none' ? ' class="full"' : '';
  body.innerHTML = `<div id="detail">${plot}<div id="console"${cls}></div></div>`;
  // mtime null, never the run's: the shell is empty until something draws
  // into it, and carrying the run's write time here would say it had
  shell = {id: run.run_id, kind: kind, mtime: null};
  tail = {offset: 0, inode: null, id: run.run_id};
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

// Δ/σ either way — it is what the fit minimised — and the flag changes only
// what the axis is called (WP-1029)
function deltaTitle(weighted) {
  if (weighted === true) return 'Δ/σ  (σ from file)';
  if (weighted === false) return 'Δ/σ  (σ = √max(y,1))';
  return 'Δ/σ';
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

  // the rows live in the lower panel, under the Δ/σ trace, spaced in its
  // units: the residual is read against the peaks that caused it, so nothing
  // comes between them
  const finite = snap.delta.filter(v => v !== null && isFinite(v));
  const lo = Math.min(-3, ...finite);
  const hi = Math.max(3, ...finite);
  const span = (hi - lo) || 1;
  const base = lo - 0.14 * span, step = 0.09 * span;
  const names = Object.keys(snap.ticks || {});
  names.forEach((name, i) => {
    const row = snap.ticks[name];
    const y = base - i * step;
    // one row has nothing to be told apart from, so colour stays for when
    // there are several
    const colour = names.length === 1 ? HUE.tick
                                      : HUE.phase[i % HUE.phase.length];
    // the cap is in the legend, because a silent cap reads as coverage
    const label = row.n_total > row.two_theta.length
      ? `hkl: ${name} (${row.two_theta.length} of ${row.n_total})`
      : `hkl: ${name}`;
    traces.push({
      x: row.two_theta, y: row.two_theta.map(() => y), name: label,
      mode: 'markers', type: 'scattergl', yaxis: 'y2', hoverinfo: 'x',
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
  const plotly = await ensurePlotly();
  const div = document.getElementById('plot');
  if (!div || currentId() !== id) return true;
  if (!plotly) {
    div.outerHTML = '<div id="noplot">this page draws with plotly: ' +
      "<code>pip install '@DIST@[viz]'</code></div>";
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
  if (currentId() !== id || !document.getElementById('plot')) return true;
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
    xaxis: {anchor: 'y2', title: {text: '2θ (°)'}, gridcolor: HUE.zero,
            zeroline: false},
    yaxis: {domain: [0.34, 1], title: {text: 'intensity'},
            gridcolor: HUE.zero, zeroline: false},
    yaxis2: {domain: [0, 0.28], anchor: 'x',
             title: {text: deltaTitle(snap.weighted)},
             gridcolor: HUE.zero, zerolinecolor: HUE.zero},
    legend: {orientation: 'h', y: 1.02, yanchor: 'bottom', x: 0},
    // one revision per run: a redraw of the same run keeps the zoom, and
    // opening a different run starts fresh
    uirevision: id,
  }, {displaylogo: false, responsive: true});
  // kept on the page, not only in the span: `drawDetail` rewrites the crumb
  // on every poll and would throw the note away between redraws
  drawn = `${snap.n_drawn} of ${snap.n_points} pts drawn`;
  const note = document.getElementById('drawn');
  if (note) note.textContent = drawn;
  return true;
}

async function drawDetail(id, first) {
  const r = await fetch('api/run/' + id, {cache: 'no-store'});
  if (!r.ok) { location.hash = ''; return; }
  const run = await r.json();
  if (currentId() !== id) return;      // the hash moved while we were waiting
  const st = run.status || {};
  // a notice belongs to one run and one moment: the stop one stands until the
  // fit stops, a refusal clears on its own clock, and neither follows the
  // reader to another run
  if (notice && (notice.id !== id || Date.now() > notice.expires
                 || (notice.stop && run.liveness.state !== 'running'))) {
    notice = null;
  }
  // the count belongs to the run it was measured on, so it is dropped before
  // the crumb is written and not after — the crumb carries it
  const kind = pictureKind(run);
  if (shell.id !== id) drawn = '';
  rootEl.textContent = run.path;
  crumb.innerHTML = (SINGLE ? '' : '<a href="#">all runs</a> · ') +
    `<span class="state ${run.liveness.state}" title="${esc(run.liveness.evidence)}"
     >${run.liveness.state}</span> ` + esc(run.label) +
    (st.stage ? ` · stage ${esc(st.stage)}` : '') +
    (st.rwp != null ? ` · Rwp ${num(st.rwp, 4)}` : '') +
    (st.gof != null ? ` · GoF ${num(st.gof, 2)}` : '') +
    (st.n_free != null ? ` · ${st.n_free} free` : '') +
    ` <span id="drawn" class="muted">${esc(drawn)}</span>` +
    stopControl(run);
  wireStop(run);
  // a running fit rewrites its snapshot per stage, and a run that had none
  // when it was opened grows one at its first
  if (first || shell.id !== id || shell.kind !== kind) detailShell(run, kind);
  // the write is recorded once it is on the page, never before: a draw that
  // did not happen must stay outstanding for the next poll
  if (kind !== 'none' && run.snapshot_mtime !== shell.mtime) {
    if (kind === 'json') {
      if (await drawSnapshot(id)) shell.mtime = run.snapshot_mtime;
    } else {
      shell.mtime = run.snapshot_mtime;
      const frame = document.getElementById('plot');
      if (frame) frame.src = legacySrc(run);
    }
  }
  await pumpEvents(id);
}

// ----------------------------------------------------------------- stop
// Drawn only for a run being written *here*: a terminal one has nothing to
// stop, and 'unknown' covers both another host and a writer that keeps no
// lock, where a request would sit in the directory doing nothing. The route
// refuses the same set, so this is the courtesy and not the check.
function stopControl(run) {
  if (notice) return ' <span class="muted">· ' + esc(notice.text) + '</span>';
  if (!CAN_CANCEL || run.liveness.state !== 'running') return '';
  return ' <button id="stop">stop</button>';
}

function wireStop(run) {
  const btn = document.getElementById('stop');
  if (btn) btn.onclick = () => openConfirm(run);
}

// Two clicks, and no keyboard shortcut of any kind: nothing takes focus when
// this opens, and neither Enter nor Escape reaches either button. Confirming
// raises an exception in a process the reader cannot see, and a stray
// keystroke must not be able to do that.
function openConfirm(run) {
  const st = run.status || {};
  const box = document.getElementById('confirm');
  document.getElementById('box-what').textContent =
    'Stop ' + run.label + (st.stage ? ', in stage ' + st.stage : '')
    + ', in the process that is running it?';
  document.getElementById('box-no').onclick = () => { box.hidden = true; };
  document.getElementById('box-yes').onclick = () => {
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
  refresh(false);
}

async function pumpEvents(id) {
  const q = new URLSearchParams({offset: tail.offset});
  if (tail.inode !== null) q.set('inode', tail.inode);
  const r = await fetch(`api/run/${id}/events?` + q, {cache: 'no-store'});
  if (!r.ok) return;
  const payload = await r.json();
  // an in-flight tail of the run we just left must not renumber this one
  if (tail.id !== id || currentId() !== id) return;
  const pane = document.getElementById('console');
  if (!pane) return;
  if (payload.reset) pane.textContent = '';   // a different log; do not renumber
  tail.offset = payload.offset;
  tail.inode = payload.inode;
  if (!payload.events.length) return;
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

// ------------------------------------------------------------- routing
function currentId() {
  const m = location.hash.match(/^#\\/run\\/([0-9a-f]+)$/);
  return m ? m[1] : (SINGLE || null);
}
async function refresh(first) {
  const id = currentId();
  if (id) await drawDetail(id, first);
  else await drawList();
}
function schedule() {
  if (timer) clearInterval(timer);
  // polling stops when nobody is looking: a hidden tab costs the fit nothing
  timer = setInterval(() => { if (!document.hidden) refresh(false); }, 1200);
}
window.addEventListener('hashchange', () => refresh(true));
document.addEventListener('visibilitychange', () => {
  if (!document.hidden) refresh(false);
});

(async () => {
  const meta = await (await fetch('api/runs', {cache: 'no-store'})).json();
  SINGLE = meta.single_run_id;
  CAN_CANCEL = meta.can_cancel === true;
  await refresh(true);
  schedule();
})();
</script></body></html>
"""

#: What a missing plotly says, in the pane the plot would have filled. Each
#: page that serves plotly owns its own fallback (``viz/plotlyjs.py``), and
#: this one has a shell worth keeping: the run list and the event log work
#: without a plotting library, so only the plot pane reports the absence.
_NO_PLOTLY_JS = (f"console.error('{DIST_NAME} watch: plotly is not installed "
                 f"\u2014 pip install \\'{DIST_NAME}[viz]\\'');")

#: The page, with its tokens filled in from their one authorities. A literal
#: ``.rex`` here would be invisible to every test in the suite (``_about.py``),
#: and literal colours would make this the second answer to which curve is
#: which — a reader flipping between the watcher, the GUI and a saved figure
#: must not have to relearn it (``viz/plots.PALETTES``).
_PAGE = (_PAGE_TEMPLATE
         .replace("@SUFFIX@", PROJECT_SUFFIX)
         .replace("@DIST@", DIST_NAME)
         .replace("@HUE@", json.dumps(PALETTES["dark"])))


#: How long a walk's result stands before the next request pays for another.
#: Shorter than the page's poll, so an open tab still sees a new run within a
#: poll or two, and short enough that a human refreshing by hand never waits.
INDEX_TTL_SECONDS = 1.0


class _RunIndex:
    """One walk shared by the requests that arrive together.

    The detail page asks for the run and then for its events, so an uncached
    :func:`~rietx.runs.discover` would walk the whole tree twice per poll, per
    open tab — and the walk is the expensive half of every route here. One
    shared result behind a lock is also what stops a burst of parallel requests
    on :class:`~http.server.ThreadingHTTPServer` from starting a walk each.
    """

    def __init__(self, root: Path, ttl: float = INDEX_TTL_SECONDS):
        self.root = root
        self.ttl = ttl
        self._lock = threading.Lock()
        self._runs: list | None = None
        self._at = 0.0

    def runs(self) -> list:
        with self._lock:
            now = time.monotonic()
            if self._runs is None or now - self._at >= self.ttl:
                self._runs = runs_mod.discover(self.root)
                self._at = now
            return self._runs


class _Handler(http.server.SimpleHTTPRequestHandler):
    """Routes, and a static fallback rooted at the scanned directory.

    The fallback is what keeps ``rietx watch live/`` working for anything that
    already links at ``fit.html`` or ``events.jsonl`` by their bare names — a
    run recorded before WP-1402 included.
    """

    def __init__(self, *args, scan_root: Path, index: _RunIndex,
                 allow_cancel: bool = True, **kwargs):
        # set before super().__init__, which handles the request inline
        self.scan_root = scan_root
        self.index = index
        self.allow_cancel = allow_cancel
        super().__init__(*args, **kwargs)

    def _send(self, body: bytes, content_type: str, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, payload, status: int = 200) -> None:
        self._send(json.dumps(payload).encode("utf-8"),
                   "application/json; charset=utf-8", status)

    def _runs(self) -> list:
        return self.index.runs()

    def _find(self, run_id: str):
        """An id is looked up in what the walk offered, never decoded into a
        path. That is why a request cannot name a directory we did not choose
        to serve."""
        for run in self._runs():
            if run.run_id == run_id:
                return run
        return None

    def _row(self, run) -> dict:
        live = runs_mod.liveness_of(run)
        row = run.as_dict()
        row["liveness"] = {"state": live.state, "evidence": live.evidence,
                           "heartbeat_age": live.heartbeat_age}
        # the picture is rewritten per stage, so the page needs to know when to
        # redraw rather than sit on the one it opened with.  The mtime is of
        # whichever file this run actually has: a legacy run's is its page's.
        name = (runs_mod.SNAPSHOT_FILE if run.has_snapshot
                else runs_mod.LEGACY_SNAPSHOT_FILE)
        try:
            row["snapshot_mtime"] = (run.path / name).stat().st_mtime
        except OSError:
            row["snapshot_mtime"] = None
        # a command a human can copy, not a verb this app performs: launching
        # the GUI is a process boundary and stays one (WP-1401 § the decision)
        project = run.path.parent
        row["gui_command"] = None
        if (run.path.name == LIVE_DIR_NAME
                and project.name.endswith(PROJECT_SUFFIX)):
            # the path as typed from where the scan started, not the bare name:
            # a project one directory down is not `rietx gui sample.rex` from
            # here
            try:
                where = os.path.relpath(project, self.scan_root)
            except ValueError:                      # pragma: no cover - Windows
                where = str(project)
            row["gui_command"] = f"{DIST_NAME} gui {where}"
        return row

    def do_GET(self):  # noqa: N802 - http.server API
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        if path in ("/", "/index.html"):
            self._send(_PAGE.encode("utf-8"), "text/html; charset=utf-8")
            return

        if path == "/plotly.js":
            # out of the installed package, so the page works air-gapped and
            # nothing vendors a copy (viz/plotlyjs.py)
            self._send(plotly_js(_NO_PLOTLY_JS).encode("utf-8"),
                       PLOTLY_CONTENT_TYPE)
            return

        if path == "/api/runs":
            found = self._runs()
            single = (found[0].run_id
                      if len(found) == 1 and found[0].path == self.scan_root
                      else None)
            self._json({"root": str(self.scan_root),
                        "single_run_id": single,
                        # the page draws no button under --read-only; the route
                        # refuses anyway, and a button that only ever 403s
                        # would be a worse answer than no button
                        "can_cancel": self.allow_cancel,
                        "runs": [self._row(r) for r in found]})
            return

        parts = [p for p in path.split("/") if p]
        if len(parts) >= 3 and parts[0] == "api" and parts[1] == "run":
            run = self._find(parts[2])
            if run is None:
                self._json({"error": "no such run"}, status=404)
                return
            rest = parts[3] if len(parts) > 3 else ""
            if rest == "":
                self._json(self._row(run))
                return
            if rest == "events":
                def _int(name):
                    try:
                        return int(query.get(name, [""])[0])
                    except (TypeError, ValueError):
                        return None
                tail = runs_mod.tail_events(
                    run.path / runs_mod.EVENTS_FILE,
                    _int("offset") or 0, inode=_int("inode"))
                self._json({"events": tail.events, "offset": tail.offset,
                            "inode": tail.inode, "reset": tail.reset,
                            "bad_lines": tail.bad_lines, "size": tail.size})
                return
            if rest in ("snapshot", "legacy"):
                # served as bytes, never parsed here: the reader constructs
                # nothing, and a half-written file is the writer's to make
                # atomic (it does)
                name = (runs_mod.SNAPSHOT_FILE if rest == "snapshot"
                        else runs_mod.LEGACY_SNAPSHOT_FILE)
                kind = ("application/json; charset=utf-8" if rest == "snapshot"
                        else "text/html; charset=utf-8")
                try:
                    body = (run.path / name).read_bytes()
                except OSError:
                    self._send(b"no snapshot yet", "text/plain; charset=utf-8",
                               status=404)
                    return
                self._send(body, kind)
                return
            self._json({"error": "no such route"}, status=404)
            return

        super().do_GET()

    def do_POST(self):  # noqa: N802 - http.server API
        """The one verb (WP-1405): ``/api/run/<id>/cancel``.

        POST and never GET. A GET that cancels is one prefetching browser, one
        link preview or one crawler away from stopping somebody's overnight
        refinement, and the static fallback below serves GET to a whole tree.

        ``SimpleHTTPRequestHandler`` has no ``do_POST`` at all, so defining one
        means every other POST is answered here rather than by a 501 from the
        base class.
        """
        # drained before anything is written back, or a keep-alive connection
        # reads the unread body as the next request line
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = 0
        if length > 0:
            self.rfile.read(min(length, 1 << 16))

        parts = [p for p in urllib.parse.urlparse(self.path).path.split("/")
                 if p]
        if len(parts) == 4 and parts[:2] == ["api", "run"] and parts[3] == "cancel":
            self._cancel(parts[2])
            return
        self._json({"error": "no such route"}, status=404)

    def _cancel(self, run_id: str) -> None:
        """Ask one run to stop, or say why not.

        The id is looked up in what the walk offered (:meth:`_find`), so this
        route inherits WP-1401's property rather than restating it: a run id is
        never decoded into a path, and a request can only ever name a directory
        this server chose to serve. ``SimpleHTTPRequestHandler`` handles
        traversal for static files and a hand-written JSON route does not get
        that for free, which is why the lookup is the mechanism and not a
        check bolted beside one.

        Only a run that is **running here** is stoppable. ``unknown`` covers
        both another host and a writer that keeps no lock, and a request into
        either would lie in the directory until somebody deleted it.
        """
        if not self.allow_cancel:
            self._json({"error": "this watcher is serving read-only"},
                       status=403)
            return
        run = self._find(run_id)
        if run is None:
            self._json({"error": "no such run"}, status=404)
            return
        live = runs_mod.liveness_of(run)
        if live.state != "running":
            self._json({"error": f"this run reads {live.state} — "
                                 f"{live.evidence}", "state": live.state},
                       status=409)
            return
        # A latched recorder is still holding its lock and still reads running,
        # and it is the thing that would have read the request. Refusing says
        # so; writing the file would leave a button that did nothing.
        if run.status is not None and run.status.error:
            self._json({"error": "this run stopped recording, so nothing is "
                                 "reading requests: " + run.status.error,
                        "state": live.state}, status=409)
            return
        try:
            runs_mod.request_cancel(run.path, who=f"{DIST_NAME} watch")
        except OSError as exc:
            self._json({"error": f"could not write the request: {exc}"},
                       status=500)
            return
        self._json({"requested": True, "run_id": run_id, "state": live.state})

    def log_message(self, *args):  # quiet: polling floods the terminal
        pass


def serve(directory: str | Path | None = None, *, port: int = 8899,
          open_browser: bool = False, block: bool = True,
          allow_cancel: bool = True):
    """Serve the runs under ``directory`` (default: the working directory).

    Returns the server when ``block=False``. A directory that is itself a run
    is served as one and the page opens straight onto it.

    ``allow_cancel=False`` serves without the stop verb, and the page draws no
    button (``--read-only``).

    **Stopping is on by default, and that was the decision** (WP-1405). The
    argument for the other way is real: a click here raises in a process the
    reader cannot see, and making that a deliberate act by requiring a flag is
    cheap. Three things settled it the other way. The server binds
    ``127.0.0.1``, so the only person who can click is the person at the
    machine the fit is running on — who can already reach it with Ctrl-C, which
    raises in that process too. A flag you have to have set *in advance* is not
    there when a runaway starts, and killing the watcher to restart it with the
    flag is the moment you needed it. And the dialog already makes it a
    deliberate act, twice over. ``--read-only`` covers the case the argument is
    really about: a reader who is not the person who should be stopping things,
    which is a situation you know about beforehand.
    """
    directory = Path.cwd() if directory is None else Path(directory)
    if not directory.is_dir():
        raise FileNotFoundError(f"{directory} is not a directory")
    directory = directory.resolve()

    # `directory` is the static-file root SimpleHTTPRequestHandler wants;
    # `scan_root` is what the routes walk. Per instance, so two servers in one
    # process (the tests run several) cannot take each other's root.
    index = _RunIndex(directory)
    handler = functools.partial(_Handler, directory=str(directory),
                                scan_root=directory, index=index,
                                allow_cancel=allow_cancel)
    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
    url = f"http://127.0.0.1:{server.server_address[1]}/"
    found = index.runs()
    print(f"rietx watch: {len(found)} run(s) under {directory}")
    print(f"             {url}  (Ctrl-C to stop)")
    if not allow_cancel:
        print("             read-only: no stop button")
    if open_browser:
        import webbrowser

        webbrowser.open(url)
    if not block:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        return server
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return server


def main(argv: list[str] | None = None) -> None:
    import argparse

    parser = argparse.ArgumentParser(
        prog="rietx watch",
        description="list and watch the refinement runs under a directory")
    parser.add_argument("directory", nargs="?", default=None,
                        help="directory to scan (default: the working "
                             "directory); a directory that is itself a run "
                             "opens straight onto it")
    parser.add_argument("--port", type=int, default=8899)
    parser.add_argument("--open", action="store_true", help="open a browser")
    parser.add_argument("--read-only", action="store_true",
                        help="serve without the stop button: the page offers "
                             "no way to cancel a running fit, and the route "
                             "refuses")
    args = parser.parse_args(argv)
    serve(args.directory, port=args.port, open_browser=args.open,
          allow_cancel=not args.read_only)


if __name__ == "__main__":  # python -m rietx.watch [dir]
    main()

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
  /* Two rules keep this page still (WP-1423). Nothing here is rewritten
     wholesale: rows, slots and the plot are patched, so the scroll, hover
     and zoom the reader holds survive a poll. And no dimension is derived
     from the stage being drawn: columns and slots are declared widths, the
     bar and the strip are one clipped line each, and the plot's axes come
     from the data. */
  body { margin:0; font-family: ui-monospace, Menlo, monospace; font-size:12px;
         background:#111; color:#cdc; display:flex; flex-direction:column;
         height:100vh; overflow:hidden; }
  a { color:#9ad; text-decoration:none; }
  a:hover { text-decoration:underline; }
  #bar { background:#1c1c1c; border-bottom:1px solid #2c2c2c; padding:0 12px;
         display:flex; gap:12px; align-items:center; flex:0 0 auto;
         height:29px; white-space:nowrap; }
  #root { color:#777; flex:1 1 auto; min-width:0; overflow:hidden;
          text-overflow:ellipsis; }
  button { font: inherit; color:#cdc; background:#242424; cursor:pointer;
           border:1px solid #3a3a3a; border-radius:4px; padding:2px 9px; }
  button:hover { background:#2c2c2c; }
  .toggle[aria-pressed="true"] { background:#2a3140; border-color:#3d4a66; }
  #main { flex:1 1 auto; display:flex; min-height:0; }
  /* the list is one panel and the run the other; a closed one gives the
     other its width, and the choice is the reader's (localStorage) */
  #runs { flex:0 0 72ch; overflow:auto; scrollbar-gutter:stable;
          border-right:1px solid #2c2c2c; }
  #run { flex:1 1 auto; min-width:0; display:flex; flex-direction:column; }
  body[data-runs="closed"] #runs, body[data-run="closed"] #run,
  body[data-single] #runs, body[data-single] #toggle-runs { display:none; }
  table { border-collapse:collapse; width:100%; table-layout:fixed; }
  col.c-state { width:12ch; } col.c-stage { width:15ch; }
  col.c-rwp { width:8ch; } col.c-gof { width:6ch; } col.c-started { width:8ch; }
  th { text-align:left; color:#777; font-weight:normal; padding:6px 7px;
       border-bottom:1px solid #2c2c2c; position:sticky; top:0;
       background:#151515; }
  td { padding:6px 7px; border-bottom:1px solid #1e1e1e; white-space:nowrap;
       overflow:hidden; text-overflow:ellipsis; }
  tr.run { cursor:pointer; }
  tr.run:hover { background:#181818; }
  tr.run.selected { background:#1b2130; }
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
  /* the strip is a grid of declared slots: a stage name, an Rwp or a
     pattern label changes its text and never its neighbour's place */
  #strip { flex:0 0 auto; height:29px; padding:0 12px; gap:0 12px;
           border-bottom:1px solid #2c2c2c; display:grid; align-items:center;
           white-space:nowrap; font-variant-numeric: tabular-nums;
           grid-template-columns: 11ch minmax(0,16ch) minmax(0,30ch)
             minmax(0,26ch) 11ch 9ch 8ch minmax(0,1fr) auto auto; }
  #strip > * { min-width:0; overflow:hidden; text-overflow:ellipsis; }
  #strip .state { justify-self:start; }
  #picture { flex:1 1 68%; min-height:180px; position:relative; }
  #plot { position:absolute; inset:0; border:0; width:100%; height:100%; }
  /* a pre-WP-1402 run left a self-contained page behind; it still opens, in
     the frame it was always shown in */
  iframe#plot { background:#fff; }
  /* a GUI project's run has no picture and never will, so the note is a
     line and the log gets the room rather than the other way round */
  #noplot { padding:7px 12px; color:#666; }
  #run.full #picture { flex:0 0 auto; min-height:0; }
  #console { flex:0 0 30%; overflow:auto; background:#181818; font-size:11px;
             padding:6px 10px; white-space:pre; }
  #run.full #console { flex:1 1 auto; }
  .k { color:#e8b339; }
  .ev { color:#888; }
  code { background:#1c1c1c; padding:1px 5px; border-radius:3px; color:#9ad; }
  #stop { border-color:#5a2c2c; color:#e88; }
  #stop:hover { background:#3d1b1b; }
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
  <button id="toggle-runs" class="toggle" aria-pressed="true"
          title="show or hide the run list">runs</button>
  <button id="toggle-run" class="toggle" aria-pressed="true"
          title="show or hide the selected run">run</button>
  <span id="root"></span>
</div>
<div id="main">
  <aside id="runs">
    <table><colgroup>
      <col class="c-state"><col><col class="c-stage"><col class="c-rwp">
      <col class="c-gof"><col class="c-started">
    </colgroup><thead><tr>
      <th>state</th><th>run</th><th>stage</th><th class="num">Rwp</th>
      <th class="num">GoF</th><th>started</th>
    </tr></thead><tbody id="rows"></tbody></table>
    <div id="empty" hidden>No runs under this directory. A run is a directory
      holding an <code>events.jsonl</code> — pass one to
      <code>LiveSession</code>, or open a <code>@SUFFIX@</code> project in the
      GUI.</div>
  </aside>
  <section id="run">
    <div id="strip">
      <span id="s-state" class="state unknown">scanning</span>
      <span id="s-label"></span>
      <span id="s-series" class="muted"></span>
      <span id="s-stage"></span>
      <span id="s-rwp" class="num"></span>
      <span id="s-gof" class="num"></span>
      <span id="s-free" class="num"></span>
      <span id="s-where" class="muted"></span>
      <span id="s-notice" class="muted"></span>
      <button id="stop" hidden>stop</button>
    </div>
    <div id="picture"></div>
    <div id="console"></div>
  </section>
</div>
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
const HUE = @HUE@;
// the console is a tail and not an archive; the log on disk is the archive
const MAX_LINES = 2000;
// the Δ/σ panel's range is one of these, ±L: the one dimension on the page
// that is the fit's rather than the data's, so it may step, and only by a
// rung, only at a stage boundary
const LADDER = [3, 5, 10, 20, 50, 100, 200, 500, 1000];
const PANELS_KEY = 'rietx-watch-panels';

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
function patchList(runs) {
  const tbody = $('rows');
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
}

// -------------------------------------------------------------- run
function pictureKind(run) {
  if (run.has_snapshot) return 'json';
  if (run.has_legacy_snapshot) return 'html';
  return 'none';
}

function buildShell(run, kind) {
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
  tail = {offset: 0, inode: null, id: run.run_id};
  $('console').textContent = '';
  setText($('s-where'), whereOf(run));
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

function finiteOf(values) {
  return values.filter(v => v !== null && isFinite(v));
}
function extent(values) {
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
function rangesOf(snap) {
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
  const plotly = await ensurePlotly();
  const div = $('plot');
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
    legend: {orientation: 'h', y: 1.02, yanchor: 'bottom', x: 0},
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
    $('console').textContent = '';
    shell = {id: null, kind: null, mtime: null};
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
  const kind = pictureKind(run);
  // a running fit rewrites its snapshot per stage, and a run that had none
  // when it was opened grows one at its first
  if (shell.id !== id || shell.kind !== kind) buildShell(run, kind);
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
  try {
    const saved = JSON.parse(localStorage.getItem(PANELS_KEY) || '{}');
    return {runs: saved.runs !== false, run: saved.run !== false};
  } catch (err) {
    return {runs: true, run: true};
  }
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
  const p = panels();
  p[which] = !p[which];
  // closing the last open panel opens the other: a page with neither is a
  // bar over nothing
  if (!p.runs && !p.run) p[which === 'runs' ? 'run' : 'runs'] = true;
  applyPanels(p);
}

// ------------------------------------------------------------- routing
// A run named in the URL is pinned. With none the page follows the newest,
// so opening `rietx watch` beside an agent's job shows what is happening
// now, and the row the reader clicks is the one that stays.
function currentId() {
  const m = location.hash.match(/^#\\/run\\/([0-9a-f]+)$/);
  return m ? m[1] : (SINGLE || newest);
}
let refreshing = false;
async function refresh() {
  if (refreshing) return;              // a slow poll is not two polls
  refreshing = true;
  try {
    const r = await fetch('api/runs', {cache: 'no-store'});
    if (!r.ok) return;
    const payload = await r.json();
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
  if (SINGLE) document.body.dataset.single = '';
  applyPanels(panels());
  await refresh();
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

#: The hosts a request carrying the one verb may claim to come from — the same
#: set ``gui/server.py`` keeps, and kept separately for the same reason the two
#: servers are separate modules. Binding ``127.0.0.1`` is not on its own enough:
#: any page the reader happens to have open can send a cross-origin ``POST``
#: with no preflight, and a hostile domain whose DNS answers ``127.0.0.1``
#: becomes same-origin, at which point the run ids are readable too.
_ALLOWED_HOSTS = frozenset({"127.0.0.1", "localhost", "[::1]", "::1"})


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

    def _origin_ok(self) -> bool:
        """Whether a write may be honoured — ``gui/server.py``'s check, here.

        Only the verb asks. Reading is served to whoever reaches the port, as
        it was before WP-1405, and the reason this exists is that the verb
        raises in another process: without it, any page the reader has open
        could ``POST`` ``/api/run/<id>/cancel`` and stop an overnight
        refinement. A same-origin fetch sends no ``Origin``, so an absent
        header is not a failure; ``Host`` is checked as well because ``Host``
        alone is what DNS rebinding defeats.
        """
        for header in ("Origin", "Referer"):
            value = self.headers.get(header)
            if not value:
                continue
            if (urllib.parse.urlparse(value).hostname or "") not in _ALLOWED_HOSTS:
                return False
        host = (self.headers.get("Host") or "").rsplit(":", 1)[0]
        return host in _ALLOWED_HOSTS

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

        POST is not enough on its own, which is what :meth:`_origin_ok` is for:
        a cross-origin POST with no body needs no preflight, so a page the
        reader has open in another tab can send this one. Binding
        ``127.0.0.1`` does not help there, and DNS rebinding hands that page
        the run ids as well.
        """
        # drained before anything is written back, or a keep-alive connection
        # reads the unread body as the next request line
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = 0
        if length > 0:
            capped = min(length, 1 << 16)
            self.rfile.read(capped)
            if capped < length:
                # the cap stops a declared gigabyte becoming this process's
                # memory, and then the connection has to go: the rest of that
                # body is still in the socket, and reusing the connection would
                # parse it as the next request — the desync this drain exists
                # to prevent
                self.close_connection = True

        if not self._origin_ok():
            self._json({"error": "this request did not come from the page "
                                 f"{DIST_NAME} watch serves"}, status=403)
            return

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

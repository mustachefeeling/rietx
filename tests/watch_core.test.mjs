// WP-1430 — the `rietx watch` page's pure half, under `node --test`.
//
// Run by `tests/test_watch_app.py::test_the_pure_half_of_the_page_is_unit_tested`,
// which is what keeps it from going quiet; `node --test tests/watch_core.test.mjs`
// from the repository root runs it by hand. No dependency and no install: the
// runner has been in node since 18.
//
// Every case here is a claim the page made and nothing checked, because until
// WP-1430 none of this was importable. The Δ/σ ladder, the residual's outlier
// cut and the "NaN" guard were each written against a real defect and each
// verified by looking at a browser.

import assert from 'node:assert/strict';
import {test} from 'node:test';

import {
  LADDER, LAYOUT_DEFAULT, ago, axisOf, clampSize, clock, coalesce, deltaTitle,
  dragged, esc, extent, finiteOf, nextLayout, num, parseLayout, pct, rangesOf,
  paletteFrom, phaseInk, rowName, runLabel, runTitle, withAlpha,
} from '../src/rietx/watch/static/watch-core.mjs';

// A pattern the page would draw: 1000 points, and a residual the caller
// chooses. Observed is a ramp, so the intensity range is exactly 0..999 and
// the padding is readable off it.
function snapshot(delta, {points = 1000, from = 10, to = 80} = {}) {
  const tt = [];
  const obs = [];
  // `|| 1` so a one-point pattern is a point and not a NaN: the short-pattern
  // cases below ask for one, and a NaN 2θ would make them assert over a
  // snapshot no reader could ever be shown
  for (let i = 0; i < points; i++) {
    tt.push(from + (to - from) * i / ((points - 1) || 1));
    obs.push(i);
  }
  return {two_theta: tt, y_obs: obs, delta: delta};
}

// ------------------------------------------------------------------ esc
test('esc closes the four characters that would end an attribute or a tag',
  () => {
    assert.equal(esc('<b title="x" & y>'),
                 '&lt;b title=&quot;x&quot; &amp; y&gt;');
    // an event's data is whatever the fit put there, including a number
    assert.equal(esc(42), '42');
  });

// ------------------------------------------------------------------ ago
test('ago steps units and never reports a negative age', () => {
  const now = Date.now() / 1000;
  assert.equal(ago(0), '—');                       // never started
  assert.equal(ago(null), '—');
  assert.equal(ago(now), '0s ago');
  assert.equal(ago(now - 30), '30s ago');
  assert.equal(ago(now - 90), '2m ago');
  assert.equal(ago(now - 7200), '2h ago');
  assert.equal(ago(now - 3 * 86400), '3d ago');
  // a clock that disagrees with the writer's must not read "-4s ago"
  assert.equal(ago(now + 4), '0s ago');
});

// ------------------------------------------------------------------ pct
test('pct is the GUI series table\'s form, and declines a non-number', () => {
  assert.equal(pct(0.1734, 2), '17.34%');
  assert.equal(pct(1, 2), '100.00%');
  assert.equal(pct(0.0512, 2), '5.12%');
  // the widest string the column has to hold, which is what its width is
  // declared from
  assert.equal(pct(1, 2).length, 7);
  // "NaN" off the wire, the same guard `num` carries
  assert.equal(pct('NaN', 2), '—');
  assert.equal(pct(null, 2), '—');
  assert.equal(pct(undefined, 2), '—');
});

// ---------------------------------------------------------------- clock
test('clock is a time today and a date before that', () => {
  const noon = new Date(2026, 8, 16, 14, 20, 7).getTime() / 1000;
  const now = new Date(2026, 8, 16, 17, 5, 0).getTime() / 1000;
  assert.equal(clock(noon, now), '14:20:07');
  // the seconds are the point: two runs of one batch differ in nothing else
  assert.equal(clock(noon + 1, now), '14:20:08');
  // midnight is a time, not a falsy hour
  assert.equal(clock(new Date(2026, 8, 16, 0, 0, 0).getTime() / 1000, now),
               '00:00:00');
  // yesterday is a date: a bare 14:20 on a run from last week is a lie the
  // tooltip would have to correct
  const before = new Date(2026, 8, 15, 14, 20, 7).getTime() / 1000;
  assert.equal(clock(before, now), '15 Sep');
  assert.equal(clock(new Date(2025, 11, 31, 9, 0).getTime() / 1000, now),
               '31 Dec');
  // and the same "never started" answer every other formatter here gives
  assert.equal(clock(0, now), '—');
  assert.equal(clock(null, now), '—');
});

// --------------------------------------- rowName, runLabel, runTitle
test('a row is named by what separates it from its neighbours', () => {
  const run = {label: 'campaign', legacy: false, path: '/w/20260916-142000-90',
               status: {}};
  assert.equal(rowName(run), 'campaign');
  // a caller may name the run itself (WP-1431), and then the label is the
  // thing that separates the rows rather than the word they share
  assert.equal(rowName({...run, label: 'candidate-07 rutile'}),
               'candidate-07 rutile');
  // a series member knows which pattern it fitted, and stays ahead of both:
  // one series is one run, so a caller's label there names the whole chain
  // while this names the row. It replaces rather than joins — a
  // `campaign · cpd-1e` that the column cuts at `campaign…` has shown the
  // reader the half they already knew.
  assert.equal(rowName({...run, status: {series_label: 'cpd-1e'}}), 'cpd-1e');
  assert.equal(rowName({...run, label: 'the ramp',
                        status: {series_label: '250C'}}), '250C');
  // the strip's own label slot is the plain label, the series having a slot
  // of its own beside it
  assert.equal(runLabel({...run, status: {series_label: 'cpd-1e'}}),
               'campaign');
  // a run with no meta.json still says so
  assert.equal(runLabel({...run, legacy: true}), 'campaign · legacy');
  // and a status that is absent, not merely empty, is the ordinary case for
  // a run whose writer has not reached its first stage
  assert.equal(rowName({label: 'campaign', path: '/w/x'}), 'campaign');
});

test('runTitle answers "which run is this one" from the record alone', () => {
  const run = {label: 'campaign', path: '/w/runs/20260916-142000-90',
               meta: {command: 'python fit_one.py candidate-3',
                      cwd: '/Users/someone/work'}};
  assert.equal(runTitle(run), 'campaign · 20260916-142000-90\n'
    + 'python fit_one.py candidate-3\nin /Users/someone/work\n'
    + '/w/runs/20260916-142000-90');
  // a legacy directory has no meta.json at all, and the two facts it does
  // have are still worth a tooltip
  assert.equal(runTitle({label: 'x', legacy: true, path: '/w/runs/old-07'}),
               'x · legacy · old-07\n/w/runs/old-07');
});

// ------------------------------------------------------------------ num
test('num survives a non-finite statistic instead of throwing on it', () => {
  // `ser_json_inf_nan="strings"` puts the string "NaN" on the wire, and
  // "NaN".toFixed is a TypeError that would cost the whole table its render
  assert.equal(num('NaN', 4), '—');
  assert.equal(num('Infinity', 4), '—');
  assert.equal(num(undefined, 4), '—');
  assert.equal(num(null, 2), '—');
  assert.equal(num(Infinity, 4), '—');
  assert.equal(num(0.123456, 4), '0.1235');
  assert.equal(num(2, 2), '2.00');
});

// ----------------------------------------------------------- deltaTitle
test('the residual axis is Δ/σ either way, and says which σ', () => {
  assert.equal(deltaTitle(true), 'Δ/σ  (σ from file)');
  assert.equal(deltaTitle(false), 'Δ/σ  (σ = √max(y,1))');
  assert.equal(deltaTitle(undefined), 'Δ/σ');     // a run that did not say
  assert.equal(deltaTitle(null), 'Δ/σ');
});

// ------------------------------------------------------- finiteOf/extent
test('a hole in the data is dropped, and an empty extent is not [±∞]', () => {
  assert.deepEqual(finiteOf([1, null, NaN, 2, Infinity, -Infinity]), [1, 2]);
  assert.deepEqual(extent([3, -1, 7]), [-1, 7]);
  assert.deepEqual(extent([]), [0, 1]);
});

// ----------------------------------------------------------- rangesOf: x, y
test('the 2θ span and the intensity range are the data\'s, with padding',
  () => {
    const {x, y} = rangesOf(snapshot(new Array(1000).fill(0)));
    // 1 % of the span either side
    assert.deepEqual(x.map(v => +v.toFixed(6)), [9.3, 80.7]);
    // -3 % / +5 % of the observed range: asymmetric, so the legend at the top
    // has room and the baseline sits off the axis
    assert.deepEqual(y.map(v => +v.toFixed(6)), [-29.97, 1048.95]);
  });

test('a pattern with no span still gets a range', () => {
  const flat = {two_theta: [20, 20], y_obs: [5, 5], delta: [0, 0]};
  const {x, y} = rangesOf(flat);
  assert.deepEqual(x, [19.99, 20.01]);            // the `|| 1` fallback
  assert.deepEqual(y.map(v => +v.toFixed(6)), [4.97, 5.05]);
});

// ------------------------------------------------------- rangesOf: the ladder
test('the Δ/σ range is a ladder rung, symmetric, and never below the data',
  () => {
    const rung = d => rangesOf(snapshot(d)).y2;
    // the smallest rung that covers the residual, so the band at ±3 stays
    // legible on a converged fit
    assert.deepEqual(rung(new Array(1000).fill(2)), [-3, 3]);
    assert.deepEqual(rung(new Array(1000).fill(4)), [-5, 5]);
    assert.deepEqual(rung(new Array(1000).fill(11)), [-20, 20]);
    // sign does not matter: it is |Δ/σ| that sets the scale
    assert.deepEqual(rung(new Array(1000).fill(-4)), [-5, 5]);
    // past the top rung it stops being a rung and becomes the number itself
    assert.deepEqual(rung(new Array(1000).fill(1400)), [-1400, 1400]);
  });

test('one spiked point does not set the scale, and ten misfitted ones do',
  () => {
    // a snapshot's arrays are the decimation's, up to `MAX_POINTS` = 4000
    const points = 4000;
    const base = new Array(points).fill(1);
    // a single 900σ point is inside the cut of four and never reaches the scale
    const spike = base.slice();
    spike[2000] = 900;
    assert.deepEqual(rangesOf(snapshot(spike, {points})).y2, [-3, 3]);
    // ten of them are a misfitted peak, and the reader must see it
    const peak = base.slice();
    for (let i = 1600; i < 1610; i++) peak[i] = 40;
    assert.deepEqual(rangesOf(snapshot(peak, {points})).y2, [-50, 50]);
  });

test('the cut is a count, so a short pattern gets one too', () => {
  // WP-1430 measured that `floor(0.999 * n)` is `n - 1` for every n ≤ 1000,
  // pinned the consequence and handed the call to WP-1426, which took it: a
  // tenth of a percent of a short pattern is less than one point, so the
  // quantile cut nothing and a lone spike put a ±1 residual on a ±1000 axis.
  // These are the same three lengths, now answering the same way.
  for (const points of [600, 1000, 1001]) {
    const spike = new Array(points).fill(1);
    spike[Math.floor(points / 2)] = 900;
    assert.deepEqual(rangesOf(snapshot(spike, {points})).y2, [-3, 3],
                     `one spike set the scale at ${points} points`);
  }
});

test('a pattern too short to have an outlier still gets a scale', () => {
  // one point is not a spike among others, so it is the scale; two is the
  // smaller of them. Neither may come back undefined, which would take the
  // axis with it.
  assert.deepEqual(rangesOf(snapshot([900], {points: 1})).y2, [-1000, 1000]);
  assert.deepEqual(rangesOf(snapshot([4, 900], {points: 2})).y2, [-5, 5]);
});

test('the ladder is rungs, so a stage can only step between them', () => {
  assert.deepEqual(LADDER, [3, 5, 10, 20, 50, 100, 200, 500, 1000]);
  for (let i = 1; i < LADDER.length; i++) {
    assert.ok(LADDER[i] > LADDER[i - 1]);
  }
});

test('a residual of nothing but holes does not make an empty axis', () => {
  const {y2} = rangesOf(snapshot([null, NaN, null].concat(
    new Array(997).fill(null))));
  assert.deepEqual(y2, [-3, 3]);
});

// ------------------------------------------------------------- layout
test('an unreadable or absent layout means two open panes at their declared sizes',
  () => {
    for (const raw of [null, '', '{oh no', 'null', '[]']) {
      assert.deepEqual(parseLayout(raw), LAYOUT_DEFAULT, String(raw));
    }
  });

test('a size of null is not a size, and neither is a number that is not one',
  () => {
    // `null` means *no choice made*, which leaves the stylesheet's `72ch` and
    // `30%` in force. A px default here would freeze a size that is font- and
    // window-relative on purpose.
    assert.equal(parseLayout('{"list":{"size":null}}').list.size, null);
    for (const bad of ['"420"', 'NaN', '0', '-40', 'true', '{}']) {
      assert.equal(parseLayout(`{"list":{"size":${bad}}}`).list.size, null,
                   bad);
    }
    assert.equal(parseLayout('{"list":{"size":420}}').list.size, 420);
    assert.equal(parseLayout('{"list":{"size":420.5}}').list.size, 420.5);
  });

test('a layout naming one seam leaves the other at its default', () => {
  const got = parseLayout('{"console":{"size":120,"open":false}}');
  assert.deepEqual(got.list, {size: null, open: true});
  assert.deepEqual(got.console, {size: 120, open: false});
});

test('only an explicit false closes a pane', () => {
  // the same `!== false` rule `parsePanels` had: a stored state that says
  // nothing about `open` is a stored size, not a collapsed pane
  assert.equal(parseLayout('{"list":{"size":420}}').list.open, true);
  assert.equal(parseLayout('{"list":{"open":0}}').list.open, true);
  assert.equal(parseLayout('{"list":{"open":false}}').list.open, false);
});

test('the old panel key gives up both its bits and nothing else', () => {
  // WP-1423 stored `{runs, run}`. Both halves have a home again since
  // WP-1438 gave the run pane a collapse of its own.
  assert.equal(parseLayout(null, '{"runs":false,"run":true}').list.open, false);
  assert.equal(parseLayout(null, '{"runs":true,"run":false}').list.open, true);
  assert.equal(parseLayout(null, '{"runs":true,"run":false}').run.open, false);
  assert.deepEqual(parseLayout(null, '{"runs":false}').console,
                   {size: null, open: true});
  // ...and it is only consulted when this page has stored nothing itself
  assert.equal(parseLayout('{"list":{"size":500}}', '{"runs":false}').list.open,
               true);
  // an unreadable old key is no worse than an absent one
  assert.deepEqual(parseLayout(null, '{oh no'), LAYOUT_DEFAULT);
});

test('the run pane is a collapse and never a size', () => {
  // no grip sizes it, so `size` has nothing to hold and only `open` moves
  // (WP-1438). It rides in the same stored object as the two seams because
  // one reader reading one shape is the point of that object.
  assert.deepEqual(parseLayout('{"run":{"open":false}}').run,
                   {size: null, open: false});
  assert.equal(parseLayout('{"run":{"open":false}}').list.open, true);
  assert.equal(parseLayout(null).run.open, true);
  const next = nextLayout(parseLayout(null), 'run', {open: false});
  assert.equal(next.run.open, false);
  assert.equal(next.list.open, true);
  assert.equal(next.console.open, true);
});

test('nextLayout leaves the layout it was handed alone', () => {
  // `nextPanels`' rule, and for the same reason: the caller reads its own copy
  // back out of storage next time
  const before = parseLayout(null);
  const after = nextLayout(before, 'list', {size: 500, open: false});
  assert.deepEqual(before, LAYOUT_DEFAULT);
  assert.deepEqual(after.list, {size: 500, open: false});
  assert.deepEqual(after.console, {size: null, open: true});
  assert.notEqual(after.console, before.console);
});

test('a patch touches the keys it names and no others', () => {
  const sized = nextLayout(parseLayout(null), 'console', {size: 140});
  assert.deepEqual(sized.console, {size: 140, open: true});
  const closed = nextLayout(sized, 'console', {open: false});
  assert.deepEqual(closed.console, {size: 140, open: false},
                   'collapsing keeps the size to restore to');
});


// ----------------------------------------------------------- paletteFrom
// WP-1429: the plot's colours are the GUI's custom properties, read off the
// root element at draw time. `read` is injected, so the page's answer to
// "which colour is the calculated curve" is testable without a browser.

test('every plot colour comes from the property that owns it', () => {
  const declared = {
    '--plot-obs': '#8a8a8a', '--plot-calc': '#c23b22', '--plot-bkg': '#6b7280',
    '--plot-diff': '#1f5fa8', '--plot-zero': '#88888888', '--line': '#dcdcd6',
    '--fg': '#1b1b1b', '--bg': '#fbfbfa', '--ok': '#2e8b57',
    '--phase-0': '#009e73', '--phase-1': '#cc79a7', '--phase-2': '#56b4e9',
    '--phase-3': '#f0e442',
  };
  assert.deepEqual(paletteFrom(name => declared[name]), {
    obs: '#8a8a8a', calc: '#c23b22', bkg: '#6b7280', diff: '#1f5fa8',
    zero: '#88888888', grid: '#dcdcd6', fg: '#1b1b1b', ground: '#fbfbfa',
    band: '#2e8b57',
    phase: ['#009e73', '#cc79a7', '#56b4e9', '#f0e442'],
  });
});

// ------------------------------------------------------------- phaseInk
// WP-1438: the tick rows' colours stopped riding on the poll's payload, which
// sent one list whatever the theme. They are `--phase-N` now, and which row
// takes which is the GUI's rule ported, `gui/src/lib/plot.ts:phaseInk`.

test('a phase keeps its colour whatever else is drawn', () => {
  const hue = { obs: '#8a8a8a', phase: ['#009e73', '#cc79a7', '#56b4e9'] };
  assert.equal(phaseInk(hue, 0, 3), '#009e73');
  assert.equal(phaseInk(hue, 1, 3), '#cc79a7');
  assert.equal(phaseInk(hue, 2, 3), '#56b4e9');
  // past the last it cycles rather than handing back undefined
  assert.equal(phaseInk(hue, 3, 4), '#009e73');
});

test('one row has nothing to be told apart from, so it takes the neutral', () => {
  const hue = { obs: '#8a8a8a', phase: ['#009e73', '#cc79a7'] };
  assert.equal(phaseInk(hue, 0, 1), '#8a8a8a');
});

test('an unstyled page still draws its ticks in something', () => {
  // `paletteFrom` drops empty properties, so a page with no stylesheet has no
  // phase list at all — and a tick row with no colour is a row plotly colours
  // by trace order, which is the defect this replaced
  const hue = { obs: '', phase: [] };
  assert.equal(phaseInk(hue, 2, 4), '');
});

test('a browser hands back a leading space, and it is not part of the colour',
  () => {
    // `getComputedStyle().getPropertyValue()` keeps the whitespace after the
    // colon, and plotly takes the string as given
    assert.equal(paletteFrom(() => ' #e56a52 ').calc, '#e56a52');
  });

test('a property nobody declared is empty, never the word undefined', () => {
  // an unstyled page draws in plotly's own colours; `'undefined'` would be a
  // colour plotly rejects trace by trace, which looks like a plotting bug
  const hue = paletteFrom(() => undefined);
  assert.equal(hue.calc, '');
  assert.equal(Object.values(hue).join(''), '');
});

// ------------------------------------------------------------- withAlpha
// The legend moved inside the paper in WP-1426, so its ground sits over the
// data and has to be part-transparent. The colour is still the palette's.

test('a palette colour comes back as rgba at the opacity asked for', () => {
  assert.equal(withAlpha('#1d1813', 0.72), 'rgba(29, 24, 19, 0.72)');
  assert.equal(withAlpha('#000000', 1), 'rgba(0, 0, 0, 1)');
  assert.equal(withAlpha('#ffffff', 0), 'rgba(255, 255, 255, 0)');
});

test('the three-digit form is the six-digit one', () => {
  assert.equal(withAlpha('#abc', 0.5), withAlpha('#aabbcc', 0.5));
  assert.equal(withAlpha('#f00', 1), 'rgba(255, 0, 0, 1)');
});

test('case and surrounding space are not what a colour is', () => {
  assert.equal(withAlpha('#1D1813', 0.72), withAlpha('#1d1813', 0.72));
  assert.equal(withAlpha('  #1d1813  ', 0.72), withAlpha('#1d1813', 0.72));
});

test('anything it cannot read comes back as itself', () => {
  // The palette arrives off the wire, so this is a real input, not a
  // hypothetical one. Handing plotly a colour it may still understand beats
  // handing it `undefined`, which draws no ground at all.
  for (const v of ['rgba(0,0,0,0.5)', 'red', '#12345', '#1d18134', '',
                   'not a colour', null, undefined]) {
    assert.equal(withAlpha(v, 0.5), v);
  }
});

// ------------------------------------------------------------ splitters
// The drag arithmetic is the GUI's, ported into `watch-core.mjs` because the
// page cannot import TypeScript (WP-1425). The table below is the GUI's own
// case table, copied character for character from
// `gui/src/lib/resize.test.ts`; the copy is what makes the port a port rather
// than a second opinion, and `tests/test_watch_app.py` compares the two blocks
// as text. Do not edit it here. Edit the GUI's, then copy it over.

// --- ported cases: the table below is copied verbatim into
// tests/watch_core.test.mjs, because `rietx watch`'s page cannot import this
// module and a copy that is not pinned is a copy that drifts. The two blocks
// are compared character for character by
// tests/test_watch_app.py::test_the_ported_drag_arithmetic_keeps_the_guis_cases,
// so a case edited here fails the page's copy until it follows. Keep the block
// free of types: it has to parse as plain JavaScript too.
const PORTED = [
  // axisOf(grow) — the coordinate a grip reads is the one its pane grows along
  ["axisOf", ["up"], "y"],
  ["axisOf", ["down"], "y"],
  ["axisOf", ["left"], "x"],
  ["axisOf", ["right"], "x"],
  // dragged(start, from, at, grow) — sign only, and the sign is per-edge.
  // Console.svelte's case: the log is below the grip, so dragging *up* makes
  // it taller.
  ["dragged", [150, 400, 340, "up"], 210],
  ["dragged", [150, 400, 460, "up"], 90],
  // the sidebar: its grip is on its left edge and the pane is to the right
  ["dragged", [420, 900, 820, "left"], 500],
  ["dragged", [420, 900, 980, "left"], 340],
  // the model pane's columns: each grip is on the right edge of the column it
  // sizes, so the two directions are both in use in one app
  ["dragged", [300, 300, 380, "right"], 380],
  // clampSize(value, min, keep, available) — the floor
  ["clampSize", [10, 26, 120, 800], 26],
  // and whatever must survive of the pane next door
  ["clampSize", [999, 26, 120, 800], 680],
  // jsdom, or a drag before the first layout: `available` of 0 must not clamp
  // every pane to a negative ceiling, which is what a naive `available - keep`
  // would do — and the same when the container is too small to hold both
  ["clampSize", [400, 26, 120, 0], 400],
  ["clampSize", [400, 26, 120, 100], 400],
  // rounds, so a style attribute is a whole number of pixels
  ["clampSize", [210.6, 26, 120, 0], 211],
];
// --- end ported cases ---

const PORTED_FNS = {axisOf, clampSize, dragged};

test('the ported drag arithmetic answers every one of the GUI\'s cases', () => {
  for (const [name, args, want] of PORTED) {
    assert.equal(PORTED_FNS[name](...args), want,
                 `${name}(${args.join(', ')})`);
  }
});

// `coalesce` came over with them, and its contract is the trailing run: the
// GUI measured a 60-move drag issuing 60 plotly resizes, the last landing
// 1.10 s after the mouse came up. Dropping the extras outright would leave the
// plot at the size the drag *started* at, so the queued one has to run.
test('coalesce runs one now and at most one more, and the last is the final size',
  async () => {
    const seen = [];
    let release = null;
    let current = 0;
    const ask = coalesce(() => {
      seen.push(current);
      return new Promise(resolve => { release = resolve; });
    });
    current = 100;
    ask();
    for (let px = 101; px <= 160; px++) {
      current = px;
      ask();
    }
    release();
    await Promise.resolve();
    await Promise.resolve();
    assert.deepEqual(seen, [100, 160]);
  });

test('coalesce is re-armed after a throw, so one failure is not a latch', () => {
  let n = 0;
  const ask = coalesce(() => {
    n += 1;
    if (n === 1) throw new Error('first one fails');
  });
  assert.throws(ask, /first one fails/);
  ask();
  assert.equal(n, 2);
});

// WP-1430 — the `rietx watch` page's pure half, under `node --test`.
//
// Run by `tests/test_watch_app.py::test_the_pure_half_of_the_page_is_unit_tested`,
// which is what keeps it from going quiet; `node --test tests/watch_core.test.mjs`
// from the repository root runs it by hand. No dependency and no install: the
// runner has been in node since 18.
//
// Every case here is a claim the page made and nothing checked, because until
// WP-1430 none of this was importable. The Δ/σ ladder, the 99.9th-percentile
// cut and the "NaN" guard were each written against a real defect and each
// verified by looking at a browser.

import assert from 'node:assert/strict';
import {test} from 'node:test';

import {
  LADDER, ago, deltaTitle, esc, extent, finiteOf, nextPanels, num,
  parsePanels, rangesOf, withAlpha,
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
    // a single 900σ point is above the 99.9th percentile and is cut
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

// ------------------------------------------------------------- panels
test('an unreadable or absent panel state means both panels open', () => {
  assert.deepEqual(parsePanels(null), {runs: true, run: true});
  assert.deepEqual(parsePanels(''), {runs: true, run: true});
  assert.deepEqual(parsePanels('{oh no'), {runs: true, run: true});
  assert.deepEqual(parsePanels('null'), {runs: true, run: true});
  // a state naming one panel leaves the other where it was
  assert.deepEqual(parsePanels('{"run":false}'), {runs: true, run: false});
  assert.deepEqual(parsePanels('{"runs":false,"run":false}'),
                   {runs: false, run: false});
});

test('closing the last open panel opens the other', () => {
  const both = {runs: true, run: true};
  assert.deepEqual(nextPanels(both, 'runs'), {runs: false, run: true});
  // ...and closing the survivor reopens the one just closed, either way round
  assert.deepEqual(nextPanels({runs: false, run: true}, 'run'),
                   {runs: true, run: false});
  assert.deepEqual(nextPanels({runs: true, run: false}, 'runs'),
                   {runs: false, run: true});
  // reopening a closed panel leaves the other alone
  assert.deepEqual(nextPanels({runs: false, run: true}, 'runs'), both);
});

test('the reducer leaves the state it was handed alone', () => {
  const before = {runs: true, run: true};
  nextPanels(before, 'run');
  assert.deepEqual(before, {runs: true, run: true});
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

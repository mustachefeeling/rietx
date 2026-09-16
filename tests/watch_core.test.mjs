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
  parsePanels, rangesOf,
} from '../src/rietx/watch/static/watch-core.mjs';

// A pattern the page would draw: 1000 points, and a residual the caller
// chooses. Observed is a ramp, so the intensity range is exactly 0..999 and
// the padding is readable off it.
function snapshot(delta, {points = 1000, from = 10, to = 80} = {}) {
  const tt = [];
  const obs = [];
  for (let i = 0; i < points; i++) {
    tt.push(from + (to - from) * i / (points - 1));
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

test('the percentile cuts nothing below 1001 points, and the spike shows',
  () => {
    // `floor(0.999 * n)` is `n - 1` for every n ≤ 1000, so on a short pattern
    // the "99.9th percentile" is the maximum and one spiked point does set
    // the scale. Nothing is wrong with the ladder here; this is the edge the
    // page has, pinned so a later WP moving it does so on purpose.
    const spike = new Array(1000).fill(1);
    spike[500] = 900;
    assert.deepEqual(rangesOf(snapshot(spike, {points: 1000})).y2,
                     [-1000, 1000]);
    // one point more and the cut starts biting
    const longer = new Array(1001).fill(1);
    longer[500] = 900;
    assert.deepEqual(rangesOf(snapshot(longer, {points: 1001})).y2, [-3, 3]);
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

// WP-1461: the pure half of `src/rietx/viz/static/rxplot.mjs`, under `node --test`.
//
// Run by `tests/test_rxplot.py::test_the_pure_half_is_unit_tested`, which is what
// keeps it from going quiet. `node --test tests/rxplot.test.mjs` from the
// repository root runs it by hand. The drawing half needs a canvas, so
// `tests/test_rxplot_browser.py` covers it in chromium.

import assert from 'node:assert/strict';
import {test} from 'node:test';

import {
  lower, nearest, partition, scatter, sqrtSplits, tickDecimals, tickLabels,
} from '../src/rietx/viz/static/rxplot.mjs';

// ------------------------------------------------------------------ lookups
test('lower is the first index at or above the value', () => {
  const xs = [1, 2, 2, 3];
  assert.equal(lower(xs, 0), 0);
  assert.equal(lower(xs, 2), 1);
  assert.equal(lower(xs, 2.5), 3);
  assert.equal(lower(xs, 9), 4);
});

test('nearest picks the closer neighbour and refuses one out of reach', () => {
  const xs = [10, 20, 30], px = (v) => v;   // one unit, one pixel
  assert.equal(nearest(xs, 14, px, 5), 0);
  assert.equal(nearest(xs, 16, px, 5), 1);
  assert.equal(nearest(xs, 25, px, 4), -1);
  assert.equal(nearest(xs, 99, px, 100), 2);
});

// ------------------------------------------------------------------ finding 2
test('a √ axis gets several ticks, not one', () => {
  const ticks = sqrtSplits(0, 12000);
  assert.ok(ticks.length >= 4, `${ticks}`);
  for (let i = 1; i < ticks.length; i++) assert.ok(ticks[i] > ticks[i - 1], `${ticks}`);
  assert.ok(ticks.every((t) => t >= 0 && t <= 12000), `${ticks}`);
  // evenly spaced in √ space means the low end is crowded in value space
  assert.ok(ticks[1] - ticks[0] < ticks.at(-1) - ticks.at(-2), `${ticks}`);
});

test('a √ axis zoomed to a narrow window keeps several ticks', () => {
  // rounded to the value's own decade, every tick from 1000 to 1010 was 1000
  for (const [lo, hi] of [[1000, 1010], [0, 0.04], [5e5, 5.0002e5]]) {
    const ticks = sqrtSplits(lo, hi);
    assert.ok(ticks.length >= 4, `${lo}-${hi}: ${ticks}`);
    // and each label prints its own tick, which is not a multiple of the smallest gap
    assert.deepEqual(tickLabels(ticks).map(Number), ticks.map((t) => +t.toPrecision(12)),
                     `${lo}-${hi}: ${tickLabels(ticks)}`);
  }
});

// ------------------------------------------------------------------ finding 3
test('ticks over a narrow range read differently from each other', () => {
  // a trajectory spanning 1e-4 Å printed `10.251` five times under uPlot's default
  const splits = [10.2510, 10.2512, 10.2514, 10.2516, 10.2518];
  assert.deepEqual(tickLabels(splits), ['10.2510', '10.2512', '10.2514', '10.2516', '10.2518']);
});

test('the precision follows the step, not the magnitude', () => {
  assert.equal(tickDecimals([0, 0.25, 0.5]), 2);
  assert.equal(tickDecimals([0, 5, 10]), 0);
  assert.equal(tickDecimals([1000, 1200, 1400]), 0);
  // float noise in uPlot's splits does not add digits
  assert.equal(tickDecimals([10.251000000000001, 10.2512, 10.2514]), 4);
});

test('a zero tick prints as zero and a filtered tick as nothing', () => {
  assert.deepEqual(tickLabels([-0.5, -1e-17, 0.5]), ['-0.5', '0.0', '0.5']);
  assert.deepEqual(tickLabels([1, null, 3]), ['1', '', '3']);
});

// ------------------------------------------------------------------ finding 10
test('a fitted array lands on the pattern grid by index, null elsewhere', () => {
  assert.deepEqual(scatter(6, [1, 3, 4], ['a', 'b', 'c']), [null, 'a', null, 'b', 'c', null]);
  assert.deepEqual(scatter(3, Int32Array.from([0]), Float64Array.from([7])), [7, null, null]);
});

test('the observed pattern splits into fitted and masked over one grid', () => {
  const [inside, outside] = partition([1, 2, 3, 4, 5, 6], Int32Array.from([1, 3]));
  assert.deepEqual(inside, [null, 2, null, 4, null, null]);
  assert.deepEqual(outside, [1, null, 3, null, 5, 6]);
});

// WP-1461 — the `rietx compare` page's pure half, under `node --test`.
//
// Run by `tests/test_compare_ui.py::test_the_pure_half_is_unit_tested`, which
// is what keeps it from going quiet; `node --test tests/compare_core.test.mjs`
// from the repository root runs it by hand.

import assert from 'node:assert/strict';
import {test} from 'node:test';

import {
  diagnosticsHtml, esc, fmt, num, paramsHtml, sameGrid, statsHtml, usable,
  valueText,
} from '../src/rietx/compare_app/static/compare-core.mjs';

const title = k => ({baseline: 'Baseline', voigt: 'Voigt <true>'})[k] || k;
const color = () => '#000000';

function record(extra = {}) {
  return {status: 'converged', error: null, rwp: 0.1, rp: 0.08, gof: 1.2,
          chi2: 1.4, durbin_watson: 1.9, esd_inflation: 1.5, n_free: 10,
          seconds: 2.25, diagnostics: [], parameters: [], ...extra};
}

test('esc makes server text safe to put in markup', () => {
  assert.equal(esc('a < b & "c" > d'), 'a &lt; b &amp; &quot;c&quot; &gt; d');
  assert.equal(esc(null), '');
});

test('num prints a dash for a number the fit did not give', () => {
  assert.equal(num(0.123456, 3), '0.123');
  // a failed fit's statistics arrive as null, never as NaN (`RunRecord.summary`)
  for (const v of [null, undefined, NaN, Infinity, 'x']) assert.equal(num(v, 3), '—');
});

test('fmt takes the decimals its size needs, and the esd beside it', () => {
  assert.equal(fmt(123.4567891, null), '123.457');
  assert.equal(fmt(4.7591234, 1.2e-4), '4.75912 <span class="esd">±0.00012</span>');
  assert.equal(fmt(0.01234567, 0), '0.012346');
  // a NaN value reaches the page as null, and must not print as 0.000000
  assert.equal(fmt(null, null), '—');
});

test('valueText gives four figures and never an exponent', () => {
  assert.equal(valueText(1.234567), '1.235');
  assert.equal(valueText(-0.00123456), '-0.001235');
  assert.equal(valueText(12345.6), '12346');
  assert.equal(valueText(999.95), '1000');
  assert.equal(valueText(null), '—');
});

test('usable is a record with a fit behind it', () => {
  assert.equal(usable(record()), true);
  assert.equal(usable(record({error: 'RuntimeError: no'})), false);
  assert.equal(usable(undefined), false);
});

test('sameGrid is one set of channels, value for value', () => {
  const a = Float64Array.of(10, 10.5, 11);
  assert.equal(sameGrid(a, Float64Array.of(10, 10.5, 11)), true);
  assert.equal(sameGrid(a, Float64Array.of(10, 10.5)), false);
  assert.equal(sameGrid(a, Float64Array.of(10, 10.6, 11)), false);
});

test('the statistics bold the best Rwp and run a failure across its row', () => {
  const records = {baseline: record({rwp: 0.2}), voigt: record({rwp: 0.1}),
                   fails: record({error: 'ValueError: x < y', rwp: null})};
  const html = statsHtml(['baseline', 'voigt', 'fails', 'unrun'], records, title, color);
  assert.match(html, /<td class="best">0\.10000<\/td>/);
  assert.doesNotMatch(html, /class="best">0\.20000/);
  assert.match(html, /<td colspan="9" class="warn">ValueError: x &lt; y<\/td>/);
  assert.match(html, /Voigt &lt;true&gt;/);
  // a variant with no record yet has no row
  assert.equal((html.match(/<tr>/g) || []).length, 4);
  assert.match(statsHtml(['unrun'], records, title, color), /Nothing run yet/);
});

test('a table with only failed fits bolds nothing', () => {
  const html = statsHtml(['fails'], {fails: record({error: 'no', rwp: null})}, title, color);
  assert.doesNotMatch(html, /class="best"/);
});

test('the diagnostics name their variant and escape their message', () => {
  const records = {voigt: record({diagnostics: [
    {level: 'info', code: 'BOUND_HIT', where: ['phases.0.biso'], message: 'a < b'}]})};
  const html = diagnosticsHtml(['baseline', 'voigt'], records, title);
  assert.match(html, /<p class="note variant">Voigt &lt;true&gt;<\/p>/);
  assert.match(html, /<div class="diag info"><code>BOUND_HIT<\/code> <i>phases\.0\.biso<\/i> — a &lt; b<\/div>/);
  assert.match(diagnosticsHtml(['baseline'], {}, title), /No diagnostics raised/);
});

test('the parameters are every path any variant refined, sorted, a dash where one did not', () => {
  const records = {
    baseline: record({parameters: [{path: 'phases.0.scale', value: 2.5, stderr: 0.01}]}),
    voigt: record({parameters: [{path: 'phases.0.cell.a', value: 4.759, stderr: null},
                                {path: 'phases.0.scale', value: 2.4, stderr: 0.02}]}),
  };
  const html = paramsHtml(['baseline', 'voigt'], records, title);
  const rows = html.split('<tr>').slice(2).map(r => r.match(/<td>([^<]+)<\/td>/)[1]);
  assert.deepEqual(rows, ['phases.0.cell.a', 'phases.0.scale']);
  assert.match(html, /<td>phases\.0\.cell\.a<\/td><td>—<\/td><td>4\.75900<\/td>/);
  assert.equal(paramsHtml(['baseline'], {baseline: record({error: 'no'})}, title), '');
});

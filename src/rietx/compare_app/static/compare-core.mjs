// The compare page's half that touches no DOM (WP-1461), run by
// `tests/compare_core.test.mjs` under `node --test`. It imports nothing,
// because node runs it from its own directory, where `rxplot.mjs` is not.

// Text from the server, made safe to put in markup. A diagnostic's message
// can hold a `<` or an `&`, and markup built from it would print wrong.
export function esc(text) {
  return String(text ?? '').replace(/[&<>"]/g, ch => (
    {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[ch]));
}

// A number to `digits` decimals, or a dash for one the fit did not give.
export function num(value, digits) {
  return (typeof value === 'number' && Number.isFinite(value))
    ? value.toFixed(digits) : '—';
}

// A refined value to the decimals its size needs, and its esd beside it.
export function fmt(value, stderr) {
  const mag = Math.abs(value);
  const digits = mag >= 100 ? 3 : mag >= 1 ? 5 : 6;
  const v = Number(value).toFixed(digits);
  return stderr ? `${v} <span class="esd">±${Number(stderr).toPrecision(2)}</span>` : v;
}

// A value under the pointer, to four figures and never in exponent form.
export function valueText(value) {
  if (typeof value !== 'number' || !Number.isFinite(value)) return '—';
  return Math.abs(value) >= 1000 ? value.toFixed(0) : value.toPrecision(4);
}

// A record with a fit behind it. A failed fit and a registry error both
// carry `error`, and neither has curves to draw.
export function usable(record) {
  return !!record && !record.error;
}

// Two fits on one set of channels. Every variant of a standard is, since a
// variant changes the model and never the data or its limits, and the Δχ²
// is a subtraction only while that holds.
export function sameGrid(a, b) {
  if (a.length !== b.length) return false;
  for (let i = 0; i < a.length; i++) if (a[i] !== b[i]) return false;
  return true;
}

const swatch = color => `<span class="swatch" style="background:${color}"></span>`;

// The statistics table: one row per variant with a record, the best Rwp in
// bold, and a failed variant's error across the row.
export function statsHtml(keys, records, title, color) {
  const rows = keys.filter(k => records[k]);
  if (!rows.length) return '<p class="note">Nothing run yet.</p>';
  const rwps = rows.filter(k => usable(records[k]) && Number.isFinite(records[k].rwp))
    .map(k => records[k].rwp);
  const best = rwps.length ? Math.min(...rwps) : null;
  let html = '<table><tr><th>variant</th><th>Rwp</th><th>Rp</th><th>GoF</th>'
    + '<th>χ²</th><th>DW</th><th>esd×</th><th>free</th><th>status</th>'
    + '<th>time</th></tr>';
  for (const k of rows) {
    const r = records[k];
    const name = `<td>${swatch(color(k))}${esc(title(k))}</td>`;
    if (r.error) {
      html += `<tr>${name}<td colspan="9" class="warn">${esc(r.error)}</td></tr>`;
      continue;
    }
    const cls = best !== null && Math.abs(r.rwp - best) < 1e-12 ? ' class="best"' : '';
    html += `<tr>${name}<td${cls}>${num(r.rwp, 5)}</td><td>${num(r.rp, 5)}</td>`
      + `<td>${num(r.gof, 3)}</td><td>${num(r.chi2, 3)}</td>`
      + `<td>${num(r.durbin_watson, 3)}</td><td>${num(r.esd_inflation, 2)}</td>`
      + `<td>${r.n_free}</td><td>${esc(r.status)}</td><td>${num(r.seconds, 1)} s</td></tr>`;
  }
  return html + '</table>';
}

// Each variant's diagnostics under its name, or a line saying there are none.
export function diagnosticsHtml(keys, records, title) {
  let html = '';
  for (const k of keys) {
    const r = records[k];
    if (!r || !r.diagnostics || !r.diagnostics.length) continue;
    html += `<p class="note variant">${esc(title(k))}</p>`;
    for (const d of r.diagnostics) {
      const where = d.where.length ? `<i>${esc(d.where.join(', '))}</i> — ` : '';
      html += `<div class="diag ${esc(d.level)}"><code>${esc(d.code)}</code> `
        + `${where}${esc(d.message)}</div>`;
    }
  }
  return html || '<p class="note">No diagnostics raised (or nothing run yet).</p>';
}

// The refined parameters, one row per path any variant refined, sorted.
export function paramsHtml(keys, records, title) {
  const rows = keys.filter(k => usable(records[k]));
  if (!rows.length) return '';
  const paths = [...new Set(rows.flatMap(k => records[k].parameters.map(p => p.path)))].sort();
  let html = '<table><tr><th>parameter</th>'
    + rows.map(k => `<th>${esc(title(k))}</th>`).join('') + '</tr>';
  for (const path of paths) {
    html += `<tr><td>${esc(path)}</td>`;
    for (const k of rows) {
      const p = records[k].parameters.find(x => x.path === path);
      html += '<td>' + (p ? fmt(p.value, p.stderr) : '—') + '</td>';
    }
    html += '</tr>';
  }
  return html + '</table>';
}

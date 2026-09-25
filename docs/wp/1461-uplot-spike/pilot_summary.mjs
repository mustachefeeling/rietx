// The pilot's logs as ranges: one row per engine, dataset, devicePixelRatio,
// renderer and gesture, over every run. `node pilot_summary.mjs` prints what
// the WP quotes from `results/pilot_*.txt`.
import { fileURLToPath } from "node:url";
import fs from "node:fs";
import path from "node:path";

const DIR = path.join(fileURLToPath(new URL(".", import.meta.url)), "results");
const rows = new Map(), notes = new Map();
const get = (key) => { if (!rows.has(key)) rows.set(key, { work: [], wrapped: [], p95: [], max: [], loaf: [], fetch: [] }); return rows.get(key); };
const note = (key, text) => { if (!notes.has(key)) notes.set(key, []); notes.get(key).push(text); };
const nums = (s) => (s.match(/-?\d+(\.\d+)?/g) ?? []).map(Number);

for (const file of fs.readdirSync(DIR).filter((f) => /^pilot_.*\.txt$/.test(f)).sort()) {
  for (const line of fs.readFileSync(path.join(DIR, file), "utf8").split("\n")) {
    const m = line.match(/^\[(\w+) (\S+) dpr(\d) run\d+\] (\w+): (.*)$/);
    if (!m) continue;
    const [, engine, ds, dpr, renderer, rest] = m;
    const base = `${engine} ${ds.startsWith("lab6") ? "lab6" : ds} dpr${dpr} ${renderer}`;
    let g;
    if ((g = rest.match(/^(\S+)\s+work (\S+) ms\/event, wrapped (\S+); frame p95 (\S+) max (\S+) ms; long frames (\[.*?\]); fetches (\[.*\])$/))) {
      const r = get(`${base} ${g[1]}`);
      if (g[2] !== "—") r.work.push(+g[2]);
      r.wrapped.push(+g[3]); r.p95.push(+g[4]); r.max.push(+g[5]);
      r.loaf.push(...JSON.parse(g[6]).map((l) => l.dur));
      r.fetch.push(JSON.parse(g[7]).filter((u) => /window|curves/.test(u)).length);
    } else if ((g = rest.match(/^boot long frames (\[.*\])$/))) {
      const frames = JSON.parse(g[1]);
      const chart = frames.filter((l) => l.scripts.some((s) => /plotly|vendor-uplot|pattern\.js/.test(s)));
      note(`${base} boot`, `${frames.map((l) => l.dur).join("/") || "none"} (chart library ${chart.map((l) => l.dur).join("/") || "none"})`);
    } else if ((g = rest.match(/^resize, the app's work (.*) ms; the chart's own (.*) ms; wrapped (.*) ms$/))) {
      const r = get(`${base} resize`);
      r.work.push(...nums(g[1])); r.wrapped.push(...nums(g[3]));
      r.own = [...(r.own ?? []), ...nums(g[2])];
    } else if ((g = rest.match(/^page errors (\[.*\])/))) {
      if (g[1] !== "[]") note(`${base} errors`, g[1]);
    } else if ((g = rest.match(/^the drag moved a line: (\w+)/))) {
      if (g[1] !== "true") note(`${base} peak`, "a drag moved no line");
    }
  }
}

const span = (xs, d = 1) => (xs.length ? (Math.min(...xs) === Math.max(...xs) ? Math.min(...xs).toFixed(d)
  : `${Math.min(...xs).toFixed(d)}-${Math.max(...xs).toFixed(d)}`) : "—");
for (const [key, r] of rows) {
  const loaf = r.loaf.length ? `${r.loaf.length} long (${Math.max(...r.loaf)} ms)` : "0 long";
  const own = r.own ? ` own ${span(r.own)}` : "";
  const fetched = r.fetch.length && Math.max(...r.fetch) ? ` fetch ${span(r.fetch, 0)}` : "";
  console.log(`${key.padEnd(34)} work ${span(r.work, 2).padEnd(11)} wrapped ${span(r.wrapped, 2).padEnd(11)}${own} `
    + `p95 ${span(r.p95)} max ${span(r.max)} ${loaf}${fetched}`);
}
for (const [key, list] of notes) console.log(`${key.padEnd(34)} ${list.join(" · ")}`);

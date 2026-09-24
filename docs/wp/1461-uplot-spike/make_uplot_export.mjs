// The same figure `write_html` draws (obs, calc, background, offset difference, tick rows under it,
// a legend that hides a curve on click) as one self-contained page with uPlot inlined.
import fs from "node:fs";
import path from "node:path";

const DIR = new URL(".", import.meta.url).pathname;
const a = JSON.parse(fs.readFileSync(path.join(DIR, "arrays.json"), "utf8"));
const js = fs.readFileSync(path.join(DIR, "node_modules/uplot/dist/uPlot.iife.min.js"), "utf8");
const css = fs.readFileSync(path.join(DIR, "node_modules/uplot/dist/uPlot.min.css"), "utf8");
const page = `<!doctype html><html><head><meta charset="utf-8"><title>rietx fit</title>
<style>${css} body{margin:0;font:12px system-ui;background:#fff}</style></head><body><div id="fig"></div>
<script>${js}</script>
<script>
const D = ${JSON.stringify(a)};
const n = D.x.length, lo = Math.min(...D.obs.map((v, i) => v - D.calc[i])), off = -Math.max(...D.obs) * 0.08;
const diff = D.obs.map((v, i) => v - D.calc[i] + off - Math.max(0, -lo));
const lower = (xs, v) => { let l = 0, h = xs.length; while (l < h) { const m = (l + h) >> 1; if (xs[m] < v) l = m + 1; else h = m; } return l; };
const pal = ["#9467bd", "#8c564b", "#e377c2", "#7f7f7f"], names = Object.keys(D.ticks);
function markers(u, si, i0, i1) {
  const xs = u.data[0], ys = u.data[si], s = 3 * devicePixelRatio, p = new Path2D(); let c = NaN, mnY = 0, mxY = 0, mn = 0, mx = 0;
  const flush = () => { if (c === c) { p.rect(c - s / 2, mnY - s / 2, s, s); if (mxY !== mnY) p.rect(c - s / 2, mxY - s / 2, s, s); } };
  for (let i = i0; i <= i1; i++) { const X = Math.round(u.valToPos(xs[i], "x", true)), y = ys[i], Y = u.valToPos(y, "y", true);
    if (X !== c) { flush(); c = X; mn = mx = y; mnY = mxY = Y; } else { if (y < mn) { mn = y; mnY = Y; } if (y > mx) { mx = y; mxY = Y; } } }
  flush(); return { stroke: null, fill: p, clip: null, band: null, gaps: null, flags: 0 };
}
function ticks(u) {
  const { ctx, bbox, scales } = u, base = u.valToPos(Math.min(...diff) , "y", true) + 8 * devicePixelRatio, rh = 9 * devicePixelRatio;
  names.forEach((k, r) => { const xs = D.ticks[k]; ctx.strokeStyle = pal[r % pal.length]; ctx.beginPath(); let last = -1;
    for (let i = lower(xs, scales.x.min); i < xs.length && xs[i] <= scales.x.max; i++) { const X = Math.round(u.valToPos(xs[i], "x", true)) + 0.5; if (X === last) continue; last = X; ctx.moveTo(X, base + r * rh); ctx.lineTo(X, base + r * rh + rh - 2); }
    ctx.stroke(); });
}
const u = new uPlot({ width: Math.min(innerWidth - 20, 1200), height: 560, title: "synthetic, 22 003 points",
  scales: { x: { time: false }, y: { range: (u, mn, mx) => [mn - 0.1 * (mx - mn), mx] } },
  cursor: { drag: { x: true, y: true, uni: 40 }, points: { show: false } },
  series: [{ label: "2θ (deg)" },
    { label: "observed", stroke: "#1f77b4", fill: "#1f77b4", paths: markers, points: { show: false } },
    { label: "calculated", stroke: "#d62728", width: 1.2 },
    { label: "background", stroke: "#2ca02c", width: 1, dash: [4, 3] },
    { label: "obs − calc", stroke: "#555", width: 1 }],
  axes: [{ label: "2θ (deg)" }, { label: "intensity", size: 64 }],
  hooks: { draw: [ticks] } },
  [D.x, D.obs, D.calc, D.bkg, diff], document.getElementById("fig"));
u.over.addEventListener("wheel", (e) => { e.preventDefault(); const { min, max } = u.scales.x, x = u.posToVal(e.offsetX, "x"), f = Math.exp(e.deltaY * 0.002);
  u.setScale("x", { min: x - (x - min) * f, max: x + (max - x) * f }); }, { passive: false });
</script></body></html>`;
fs.writeFileSync(path.join(DIR, "uplot_export.html"), page);
console.log("uplot_export.html", page.length);

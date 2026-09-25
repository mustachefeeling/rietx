// Drive proto.html with real input and measure what each gesture costs the main thread.
//   per-event = (Δ TaskDuration − idle rate × wall) / events      (CDP Performance metrics)
//   frames    = rAF intervals during the gesture (p50/p95/max) + long animation frames (> 50 ms)
import { fileURLToPath } from "node:url";
import { chromium } from "playwright-core";
import http from "node:http";
import fs from "node:fs";
import path from "node:path";
import os from "node:os";

const DIR = fileURLToPath(new URL(".", import.meta.url));
const OUT = path.join(DIR, "shots"); fs.mkdirSync(OUT, { recursive: true });
const EXE = os.homedir() + "/Library/Caches/ms-playwright/chromium-1223/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing";
const TYPES = { ".html": "text/html", ".js": "text/javascript", ".mjs": "text/javascript", ".css": "text/css", ".json": "application/json" };
const server = http.createServer((q, r) => {
  const f = path.join(DIR, decodeURIComponent(q.url.split("?")[0]));
  if (!f.startsWith(DIR) || !fs.existsSync(f)) { r.writeHead(404); return r.end(); }
  r.writeHead(200, { "content-type": TYPES[path.extname(f)] ?? "application/octet-stream" }); fs.createReadStream(f).pipe(r);
}).listen(0, "127.0.0.1");
await new Promise((r) => server.once("listening", r));
const BASE = `http://127.0.0.1:${server.address().port}/`;

const browser = await chromium.launch({ executablePath: EXE, headless: true, args: ["--use-angle=metal", "--enable-gpu", "--ignore-gpu-blocklist"] });
const DPR2 = process.argv[2] === "dpr2";
const ctx = await browser.newContext({ viewport: { width: 1300, height: 1000 }, deviceScaleFactor: DPR2 ? 2 : 1 });
await ctx.grantPermissions(["clipboard-read", "clipboard-write"], { origin: BASE.slice(0, -1) });
const page = await ctx.newPage();
page.on("pageerror", (e) => console.error("PAGEERROR", e.message));
page.on("console", (m) => { if (m.type() === "error") console.error("CONSOLE", m.text()); });
const cdp = await ctx.newCDPSession(page);
await cdp.send("Performance.enable");
const task = async () => (await cdp.send("Performance.getMetrics")).metrics.find((m) => m.name === "TaskDuration").value * 1000;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// ALLMARKERS=1 draws every marker (proto.html?all) instead of thinning per pixel column
await page.goto(BASE + "proto.html" + (process.env.ALLMARKERS ? "?all" : ""));
await page.evaluate(() => {
  window.__f = []; window.__loaf = [];
  const loop = (t) => { window.__f.push(t); requestAnimationFrame(loop); }; requestAnimationFrame(loop);
  new PerformanceObserver((l) => { for (const e of l.getEntries()) window.__loaf.push(e.duration); }).observe({ type: "long-animation-frame" });
});

// idle rate: what the rAF recorder and the page cost with nothing happening
async function idleRate() { const t0 = await task(), w0 = Date.now(); await sleep(1500); return ((await task()) - t0) / (Date.now() - w0); }

const rows = [];
async function measure(name, events, fn, idle) {
  await page.evaluate(() => { window.__f = []; window.__loaf = []; });
  const t0 = await task(), w0 = Date.now();
  const extra = await fn();
  await sleep(120);
  const wall = Date.now() - w0, busy = (await task()) - t0 - idle * wall;
  const fr = await page.evaluate(() => {
    const iv = []; for (let i = 1; i < window.__f.length; i++) iv.push(window.__f[i] - window.__f[i - 1]);
    iv.sort((a, b) => a - b); const q = (p) => iv.length ? iv[Math.min(iv.length - 1, Math.floor(p * iv.length))] : NaN;
    return { p50: q(0.5), p95: q(0.95), max: iv.length ? iv[iv.length - 1] : NaN, loaf: window.__loaf.length, loafMax: Math.max(0, ...window.__loaf) };
  });
  const row = { name, events, perEvent: busy / events, ...fr, extra };
  rows.push(row);
  console.log(`${name.padEnd(44)} ${String(events).padStart(4)} ev  ${row.perEvent.toFixed(2).padStart(6)} ms/ev   frames p50 ${fr.p50.toFixed(1)} p95 ${fr.p95.toFixed(1)} max ${fr.max.toFixed(1)}   LoAF ${fr.loaf}${fr.loaf ? " (max " + fr.loafMax.toFixed(0) + ")" : ""}${extra ? "   " + JSON.stringify(extra) : ""}`);
  return row;
}
// a programmatic call timed in-page: the call plus the microtask uPlot commits its draw in
const timed = (expr) => page.evaluate(async (e) => { const t0 = performance.now(); await (0, eval)(e); await Promise.resolve(); await Promise.resolve(); return performance.now() - t0; }, expr);

async function suite(N) {
  console.log(`\n=== N = ${N} points ===`);
  const mountMs = await timed(`P.mount(${N})`);
  console.log("mount (three panes, first draw)", mountMs.toFixed(1), "ms");
  await sleep(300);
  const idle = await idleRate();
  const R = await page.evaluate(() => ({ main: P.rect("main"), ticks: P.rect("ticks"), resid: P.rect("resid") }));
  const at = (r, fx, fy) => [r.x + fx * r.w, r.y + fy * r.h];

  await measure("hover sweep, main pane", 120, async () => {
    for (let i = 0; i < 120; i++) { await page.mouse.move(...at(R.main, 0.02 + 0.96 * i / 119, 0.5)); await sleep(16); }
  }, idle);
  await page.mouse.move(...at(R.main, 0.5, 0.5));
  await page.locator("#wrap").screenshot({ path: `${OUT}/hover-main-${N}.png` });
  await measure("hover sweep, tick pane (hkl lookup)", 60, async () => {
    for (let i = 0; i < 60; i++) { await page.mouse.move(...at(R.ticks, 0.3 + 0.1 * i / 59, 0.5)); await sleep(16); }
  }, idle);
  await page.locator("#wrap").screenshot({ path: `${OUT}/hover-ticks-${N}.png` });

  await measure("drag-zoom (5 drags x 20 moves)", 110, async () => {
    for (let d = 0; d < 5; d++) {
      const [x1, y] = at(R.main, 0.3 + d * 0.02, 0.5), [x2] = at(R.main, 0.7 - d * 0.02, 0.5);
      await page.mouse.move(x1, y); await page.mouse.down();
      for (let i = 1; i <= 20; i++) { await page.mouse.move(x1 + (x2 - x1) * i / 20, y); await sleep(16); }
      await page.mouse.up(); await sleep(30);
    }
  }, idle);
  const zoomed = await page.evaluate(() => P.xRange());
  await measure("double-click reset", 1, async () => { await page.mouse.dblclick(...at(R.main, 0.5, 0.5)); }, idle);
  const reset = await page.evaluate(() => P.xRange());
  console.log("  zoomed to", zoomed.map((v) => v.toFixed(3)), "reset to", reset.map((v) => v.toFixed(3)));

  await page.mouse.move(...at(R.main, 0.4, 0.5));
  await measure("wheel zoom in+out (120 events)", 120, async () => {
    for (let i = 0; i < 60; i++) { await page.mouse.wheel(0, -60); await sleep(16); }
    for (let i = 0; i < 60; i++) { await page.mouse.wheel(0, 60); await sleep(16); }
  }, idle);
  await page.evaluate(() => P.setX(20, 25));
  await measure("wheel pan (60 events)", 60, async () => { for (let i = 0; i < 60; i++) { await page.mouse.wheel(40, 0); await sleep(16); } }, idle);
  await measure("alt-drag pan (40 moves)", 40, async () => {
    const [x, y] = at(R.main, 0.6, 0.5); await page.mouse.move(x, y); await page.keyboard.down("Alt"); await page.mouse.down();
    for (let i = 1; i <= 40; i++) { await page.mouse.move(x - 8 * i, y); await sleep(16); }
    await page.mouse.up(); await page.keyboard.up("Alt");
  }, idle);
  console.log("  after pans", (await page.evaluate(() => P.xRange())).map((v) => v.toFixed(3)));
  await page.mouse.dblclick(...at(R.main, 0.5, 0.5));

  await page.evaluate(() => P.setMode("select"));
  const ex0 = (await page.evaluate(() => P.excluded())).length;
  await measure("exclude-region drags (5 x 20 moves)", 110, async () => {
    for (let d = 0; d < 5; d++) {
      const [x1, y] = at(R.main, 0.1 + d * 0.17, 0.5), [x2] = at(R.main, 0.14 + d * 0.17, 0.5);
      await page.mouse.move(x1, y); await page.mouse.down();
      for (let i = 1; i <= 20; i++) { await page.mouse.move(x1 + (x2 - x1) * i / 20, y); await sleep(16); }
      await page.mouse.up(); await sleep(30);
    }
  }, idle);
  const ex1 = await page.evaluate(() => P.excluded());
  console.log(`  excluded regions ${ex0} -> ${ex1.length}; range still ${(await page.evaluate(() => P.xRange())).map((v) => v.toFixed(2))}`);
  await page.locator("#wrap").screenshot({ path: `${OUT}/excluded-${N}.png` });

  await page.evaluate(() => { P.setMode("peaks"); P.setX(20, 30); });
  await sleep(50);
  const pk0 = await page.evaluate(() => P.peaks());
  // pick a peak on screen and find its pixel
  const target = await page.evaluate(() => {
    const [lo, hi] = P.xRange(); return P.peaks().findIndex((p) => p.x > lo + 0.5 && p.x < hi - 0.5);
  });
  // a peak's pixel, through the ring's own placement: the same maths the page uses
  const pxOf = (i) => page.evaluate((i) => {
    const r = P.rect("main"), ring = document.querySelector("#main .ring");
    window.hoverPeak(i); return [r.x + parseFloat(ring.style.left), r.y + parseFloat(ring.style.top)];
  }, i);
  const [px0, py0] = await pxOf(target);
  await measure("peak drag-move (60 moves)", 60, async () => {
    await page.mouse.move(px0, py0); await page.mouse.down();
    for (let i = 1; i <= 60; i++) { await page.mouse.move(px0 + 2 * i, py0); await sleep(16); }
    await page.mouse.up();
  }, idle);
  const pk1 = await page.evaluate(() => P.peaks());
  console.log(`  peak ${target} moved ${pk0[target].x.toFixed(4)} -> ${pk1[target].x.toFixed(4)}`);
  await measure("peak click-add (10 clicks)", 10, async () => {
    for (let i = 0; i < 10; i++) { await page.mouse.click(...at(R.main, 0.05 + 0.09 * i, 0.9)); await sleep(30); }
  }, idle);
  const pk2 = await page.evaluate(() => P.peaks());
  const [px1, py1] = await pxOf(target);
  await page.keyboard.down("Shift"); await page.mouse.click(px1, py1); await page.keyboard.up("Shift");
  const pk3 = await page.evaluate(() => P.peaks());
  await page.mouse.click(px1, py1, { button: "right" });
  const pk4 = await page.evaluate(() => P.peaks());
  console.log(`  peaks ${pk1.length} -> add ${pk2.length}; shift-click excl ${pk2[target].excl} -> ${pk3[target].excl}; right-click remove -> ${pk4.length}`);
  await page.locator("#wrap").screenshot({ path: `${OUT}/peaks-${N}.png` });
  await page.evaluate(() => P.setMode("zoom"));

  await measure("table -> plot hover ring (120)", 120, () => page.evaluate(async () => {
    for (let i = 0; i < 120; i++) { window.hoverPeak(i % 40); await new Promise((r) => requestAnimationFrame(r)); }
  }), idle);
  await measure("legend toggle (10)", 10, () => page.evaluate(async () => {
    for (let i = 0; i < 10; i++) { window.toggleSeries(3); await new Promise((r) => requestAnimationFrame(r)); }
  }), idle);

  const ms = {};
  ms.sqrt = await timed(`P.setScale("sqrt")`); await page.locator("#wrap").screenshot({ path: `${OUT}/sqrt-${N}.png` });
  ms.log = await timed(`P.setScale("log")`); await page.locator("#wrap").screenshot({ path: `${OUT}/log-${N}.png` });
  ms.lin = await timed(`P.setScale("lin")`);
  ms.dark = await timed(`P.theme("dark")`); await page.locator("#wrap").screenshot({ path: `${OUT}/dark-${N}.png` });
  ms.light = await timed(`P.theme("light")`);
  await page.evaluate(() => P.setX(20, 22));
  const st = []; for (let i = 0; i < 10; i++) st.push(await timed(`P.stage()`));
  ms.stage = Math.max(...st); ms.stageKeepsZoom = (await page.evaluate(() => P.xRange())).map((v) => +v.toFixed(3));
  const rs = []; for (let i = 0; i < 10; i++) rs.push(await timed(`P.resize(${i % 2 ? 1200 : 1000})`));
  ms.resize = Math.max(...rs);
  await page.evaluate(() => P.setX(5, 60));
  ms.cand426 = await timed(`P.candidates(426)`);
  await page.locator("#wrap").screenshot({ path: `${OUT}/cand426-${N}.png` });
  ms.cand92k = await timed(`P.candidates(92103)`);
  console.log("  programmatic (max of reps where repeated), ms:", JSON.stringify(Object.fromEntries(Object.entries(ms).map(([k, v]) => [k, Array.isArray(v) ? v : +v.toFixed(2)]))));
  await measure("hover sweep with 92,103 candidate lines", 60, async () => {
    for (let i = 0; i < 60; i++) { await page.mouse.move(...at(R.main, 0.1 + 0.8 * i / 59, 0.5)); await sleep(16); }
  }, idle);
  await measure("wheel zoom with 92,103 candidate lines", 60, async () => {
    for (let i = 0; i < 60; i++) { await page.mouse.wheel(0, -60); await sleep(16); }
  }, idle);
  await page.evaluate(() => { P.candidates(0); P.setX(5, 60); });

  const png = await page.evaluate(() => P.copyPNG());
  const back = await page.evaluate(async () => { const it = await navigator.clipboard.read(); const b = await it[0].getType("image/png"); return { types: it[0].types, bytes: b.size }; });
  console.log("  copy PNG", JSON.stringify(png), "clipboard read back", JSON.stringify(back));
  const tsvAll = await page.evaluate(() => P.copyTSV());
  const backT = await page.evaluate(async () => (await navigator.clipboard.readText()).length);
  await page.evaluate(() => P.setX(20, 22));
  const tsvZoom = await page.evaluate(() => P.copyTSV());
  console.log("  copy TSV full", JSON.stringify(tsvAll), "read back chars", backT, "| zoomed", JSON.stringify(tsvZoom));
}

const ONLY = /^n=(\d+)$/.exec(process.argv[2] ?? "");
if (ONLY) { await suite(+ONLY[1]); await browser.close(); server.close(); process.exit(0); }
await suite(22003);
if (DPR2) { console.log("devicePixelRatio", await page.evaluate(() => devicePixelRatio)); await browser.close(); server.close(); process.exit(0); }
await suite(200000);

// ---- SVG export of a zoomed window, and the arrays the standalone-page comparison is built from
console.log("\n=== SVG export, N = 22003, window 20-30 ===");
await page.evaluate(() => { P.mount(22003); P.setX(20, 30); });
await sleep(100);
const svg = await page.evaluate(() => P.exportSVG());
svg.svgs.forEach((s, i) => fs.writeFileSync(path.join(OUT, `export-${i}.svg`), s));
console.log(`  export ${svg.ms.toFixed(1)} ms, sizes ${svg.svgs.map((s) => (s.length / 1024).toFixed(0) + " kB").join(" / ")}`);
const view = await ctx.newPage();
await view.setContent(`<body style="margin:0;background:#fff">${svg.svgs.map((s) => `<div>${s}</div>`).join("")}</body>`);
await view.screenshot({ path: `${OUT}/export-svg.png`, fullPage: true }); await view.close();
const arrays = await page.evaluate(() => ({ x: Array.from(D.x), obs: Array.from(D.obs), calc: Array.from(D.calc), bkg: Array.from(D.bkg),
  ticks: Object.fromEntries(T.map((t, i) => ["phase " + i, Array.from(t.x)])) }));
fs.writeFileSync(path.join(DIR, "arrays.json"), JSON.stringify(arrays));

// ---- the other surfaces
console.log("\n=== Series trajectory, compare overlay, in-situ map ===");
const p2 = await ctx.newPage();
p2.on("pageerror", (e) => console.error("PAGEERROR2", e.message));
await p2.goto(BASE + "proto2.html");
await p2.evaluate(() => { window.__f = []; window.__loaf = []; const loop = (t) => { window.__f.push(t); requestAnimationFrame(loop); }; requestAnimationFrame(loop);
  new PerformanceObserver((l) => { for (const e of l.getEntries()) window.__loaf.push(e.duration); }).observe({ type: "long-animation-frame" }); });
const cdp2 = await ctx.newCDPSession(p2); await cdp2.send("Performance.enable");
const task2 = async () => (await cdp2.send("Performance.getMetrics")).metrics.find((m) => m.name === "TaskDuration").value * 1000;
async function measure2(name, events, fn) {
  await p2.evaluate(() => { window.__f = []; window.__loaf = []; });
  const t0 = await task2(), w0 = Date.now(); await fn(); await sleep(120);
  const busy = (await task2()) - t0, wall = Date.now() - w0;
  const fr = await p2.evaluate(() => { const iv = []; for (let i = 1; i < window.__f.length; i++) iv.push(window.__f[i] - window.__f[i - 1]); iv.sort((a, b) => a - b);
    return { p95: iv[Math.floor(0.95 * iv.length)], max: iv[iv.length - 1], loaf: window.__loaf.length }; });
  console.log(`${name.padEnd(44)} ${String(events).padStart(4)} ev  ${(busy / events).toFixed(2).padStart(6)} ms/ev (gross)  frames p95 ${fr.p95.toFixed(1)} max ${fr.max.toFixed(1)}  LoAF ${fr.loaf}  wall ${wall} ms`);
}
const sweep = (sel, n, y = 0.5) => async () => { const b = await p2.locator(`${sel} .u-over`).boundingBox();
  for (let i = 0; i < n; i++) { await p2.mouse.move(b.x + b.width * (0.02 + 0.96 * i / (n - 1)), b.y + b.height * y); await sleep(16); } };
const wheelAt = (sel, n, dy, dx = 0) => async () => { const b = await p2.locator(`${sel} .u-over`).boundingBox(); await p2.mouse.move(b.x + b.width * 0.4, b.y + b.height * 0.5);
  for (let i = 0; i < n; i++) { await p2.mouse.wheel(dx, dy); await sleep(16); } };
console.log("  traj mount ms", (await p2.evaluate(() => { const t = performance.now(); Q.traj(); return performance.now() - t; })).toFixed(1));
await measure2("trajectory hover (tooltip, esd)", 60, sweep("#traj", 60));
await p2.locator("#traj").screenshot({ path: `${OUT}/traj.png` });
console.log("  compare mount ms", (await p2.evaluate(() => { const t = performance.now(); Q.cmp(); return performance.now() - t; })).toFixed(1));
await measure2("compare hover, 10 x 22,003 (focus)", 60, sweep("#cmp", 60, 0.3));
await p2.locator("#cmp").screenshot({ path: `${OUT}/cmp.png` });
await measure2("compare wheel zoom", 60, wheelAt("#cmp", 60, -60));
const film = await p2.evaluate(() => Q.film());
console.log("  film build", JSON.stringify(film));
await measure2("map 200 x 22,003: wheel zoom", 60, wheelAt("#film", 60, -60));
await measure2("map: wheel pan", 60, wheelAt("#film", 60, 0, 40));
await measure2("map: hover readout", 60, sweep("#film", 60));
await p2.locator("#film").screenshot({ path: `${OUT}/film-zoomed.png` });
await p2.evaluate(() => Q.filmU.setScale("x", { min: 5, max: 60 })); await sleep(100);
await p2.locator("#film").screenshot({ path: `${OUT}/film-full.png` });
fs.writeFileSync(path.join(DIR, "proto_rows.json"), JSON.stringify(rows, null, 1));
await browser.close(); server.close();

// (1) SVG export with the live panes isolated; (2) standalone page: write_html (plotly) vs uPlot;
// (3) the same gestures in today's GUI (plotly), measured the way proto_driver measures uPlot.
import { fileURLToPath } from "node:url";
import { chromium } from "playwright-core";
import { spawn } from "node:child_process";
import http from "node:http";
import fs from "node:fs";
import path from "node:path";
import os from "node:os";

const DIR = fileURLToPath(new URL(".", import.meta.url)), OUT = path.join(DIR, "shots");
const EXE = os.homedir() + "/Library/Caches/ms-playwright/chromium-1223/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing";
const TYPES = { ".html": "text/html", ".js": "text/javascript", ".mjs": "text/javascript", ".css": "text/css" };
const server = http.createServer((q, r) => { const f = path.join(DIR, decodeURIComponent(q.url.split("?")[0]));
  if (!f.startsWith(DIR) || !fs.existsSync(f) || fs.statSync(f).isDirectory()) { r.writeHead(404); return r.end(); }
  r.writeHead(200, { "content-type": TYPES[path.extname(f)] ?? "application/octet-stream" }); fs.createReadStream(f).pipe(r); }).listen(0, "127.0.0.1");
await new Promise((r) => server.once("listening", r));
const BASE = `http://127.0.0.1:${server.address().port}/`;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const browser = await chromium.launch({ executablePath: EXE, headless: true, args: ["--use-angle=metal", "--enable-gpu", "--ignore-gpu-blocklist"] });
const ctx = await browser.newContext({ viewport: { width: 1500, height: 1000 } });

// ---------------------------------------------------------------- (1)
{
  const page = await ctx.newPage(); const errs = []; page.on("pageerror", (e) => errs.push(e.message));
  await page.goto(BASE + "proto.html");
  await page.evaluate(() => { P.mount(22003); P.setX(20, 30); }); await sleep(100);
  const svg = await page.evaluate(() => P.exportSVG());
  const after = await page.evaluate(() => P.xRange());
  svg.svgs.forEach((s, i) => fs.writeFileSync(path.join(OUT, `export-${i}.svg`), s));
  console.log(`SVG export: ${svg.ms.toFixed(0)} ms, ${svg.svgs.map((s) => (s.length / 1024).toFixed(0) + " kB").join(" / ")}; page errors ${errs.length}; live window after ${after.map((v) => v.toFixed(2))}`);
  await page.close();
}

// ---------------------------------------------------------------- (2)
for (const f of ["plotly_export.html", "uplot_export.html"]) {
  const size = fs.statSync(path.join(DIR, f)).size, ts = [];
  for (let i = 0; i < 3; i++) {
    const page = await ctx.newPage(); page.on("pageerror", (e) => console.error(f, e.message));
    await page.goto(BASE + f, { waitUntil: "load" });
    await page.waitForSelector("canvas");
    ts.push(await page.evaluate(() => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(() => r(performance.now()))))));
    if (i === 0) await page.screenshot({ path: `${OUT}/${f.replace(".html", ".png")}` });
    await page.close();
  }
  console.log(`${f.padEnd(20)} ${(size / 1024 / 1024).toFixed(2)} MB   navigation to drawn ${ts.map((t) => t.toFixed(0)).join(", ")} ms`);
}

// ---------------------------------------------------------------- (3)
const PORT = 8799, GUI = `http://127.0.0.1:${PORT}`;
// A fresh state dir per run: the example project is built once into it and kept, so a shared
// one hands each run the last run's excluded regions (the exclude drags below make some).
const freshState = () => { fs.mkdirSync(path.join(DIR, "state"), { recursive: true }); return fs.mkdtempSync(path.join(DIR, "state", "driver3-")); };
const RIETX = process.env.RIETX ?? fileURLToPath(new URL("../../../.venv/bin/rietx", import.meta.url));
const srv = spawn(RIETX, ["gui", "--no-open", "--machine", "--port", String(PORT), "--state-dir", freshState()], { stdio: ["ignore", "pipe", "inherit"] });
await new Promise((r) => srv.stdout.once("data", r));
const api = async (p, body) => (await fetch(GUI + p, body === undefined ? {} : { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) })).json();
try {
  await api("/api/examples/open", { name: "nac" });
  await api("/api/run", { kind: "fit" });
  for (;;) { const s = await api("/api/run/state"); if (s.state !== "running") break; await sleep(500); }
  const page = await ctx.newPage(); page.on("pageerror", (e) => console.error("gui", e.message));
  await page.addInitScript(() => {
    window.__log = []; const f = window.fetch;
    window.fetch = async (...a) => { const s = performance.now(); const r = await f(...a); window.__log.push({ k: "fetch", url: String(a[0]).split("?")[0], s, e: performance.now() }); return r; };
    const wrap = () => { const P = window.Plotly; if (!P || P.__w) return; P.__w = true;
      for (const [o, n] of [[P, "react"], [P, "relayout"], [P, "restyle"], [P.Plots, "resize"]]) { const g = o[n]; o[n] = async function (...a) { const s = performance.now(); const r = await g.apply(this, a); window.__log.push({ k: n, s, e: performance.now() }); return r; }; } };
    setInterval(wrap, 5);
  });
  await page.goto(GUI + "/");
  await page.waitForFunction(() => window.__log.some((l) => l.k === "react"), null, { timeout: 60000 }); await sleep(1500);
  await page.evaluate(() => { window.__f = []; window.__loaf = []; const loop = (t) => { window.__f.push(t); requestAnimationFrame(loop); }; requestAnimationFrame(loop);
    new PerformanceObserver((l) => { for (const e of l.getEntries()) window.__loaf.push(e.duration); }).observe({ type: "long-animation-frame" }); });
  const cdp = await ctx.newCDPSession(page); await cdp.send("Performance.enable");
  const task = async () => (await cdp.send("Performance.getMetrics")).metrics.find((m) => m.name === "TaskDuration").value * 1000;
  const t0i = await task(), w0i = Date.now(); await sleep(1500); const idle = ((await task()) - t0i) / (Date.now() - w0i);
  const box = await page.locator(".js-plotly-plot .draglayer .xy .nsewdrag").first().boundingBox();
  const at = (fx, fy) => [box.x + fx * box.width, box.y + fy * box.height];
  async function measure(name, events, fn) {
    await page.evaluate(() => { window.__f = []; window.__loaf = []; window.__mark = window.__log.length; });
    const t0 = await task(), w0 = Date.now(); await fn(); await sleep(800);
    const wall = Date.now() - w0, busy = (await task()) - t0 - idle * wall;
    const r = await page.evaluate(() => { const iv = []; for (let i = 1; i < window.__f.length; i++) iv.push(window.__f[i] - window.__f[i - 1]); iv.sort((a, b) => a - b);
      const calls = {}; for (const l of window.__log.slice(window.__mark)) { calls[l.k] = (calls[l.k] ?? []); calls[l.k].push(Math.round(l.e - l.s)); }
      return { p50: iv[iv.length >> 1], p95: iv[Math.floor(0.95 * iv.length)], max: iv[iv.length - 1], loaf: window.__loaf.length, loafMax: Math.max(0, ...window.__loaf), calls }; });
    console.log(`GUI ${name.padEnd(40)} ${String(events).padStart(4)} ev  ${(busy / events).toFixed(2).padStart(6)} ms/ev   frames p50 ${r.p50.toFixed(1)} p95 ${r.p95.toFixed(1)} max ${r.max.toFixed(1)}   LoAF ${r.loaf}${r.loaf ? " (max " + r.loafMax.toFixed(0) + ")" : ""}   ${JSON.stringify(r.calls)}`);
  }
  console.log("idle rate", idle.toFixed(3), "ms/ms; plot box", JSON.stringify(box));
  await measure("hover sweep, main plot", 120, async () => { for (let i = 0; i < 120; i++) { await page.mouse.move(...at(0.02 + 0.96 * i / 119, 0.5)); await sleep(16); } });
  await measure("drag-zoom (5 drags x 20 moves)", 110, async () => {
    for (let d = 0; d < 5; d++) { const [x1, y] = at(0.3 + d * 0.02, 0.5), [x2] = at(0.7 - d * 0.02, 0.5);
      await page.mouse.move(x1, y); await page.mouse.down(); for (let i = 1; i <= 20; i++) { await page.mouse.move(x1 + (x2 - x1) * i / 20, y); await sleep(16); }
      await page.mouse.up(); await sleep(300); } });
  await measure("double-click reset", 1, async () => { await page.mouse.dblclick(...at(0.5, 0.5)); });
  await page.getByRole("button", { name: "✂ exclude" }).click(); await sleep(300);
  await measure("exclude-region drags (3 x 20 moves)", 66, async () => {
    for (let d = 0; d < 3; d++) { const [x1, y] = at(0.1 + d * 0.3, 0.5), [x2] = at(0.14 + d * 0.3, 0.5);
      await page.mouse.move(x1, y); await page.mouse.down(); for (let i = 1; i <= 20; i++) { await page.mouse.move(x1 + (x2 - x1) * i / 20, y); await sleep(16); }
      await page.mouse.up(); await sleep(400); } });
  await page.screenshot({ path: `${OUT}/gui-after.png` });
  await page.close();
} finally { srv.kill(); }
await browser.close(); server.close();

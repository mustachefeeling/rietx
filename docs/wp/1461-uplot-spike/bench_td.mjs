// Library head-to-head as main-thread WORK, not promise latency (the review's blocker):
// Plotly.Plots.resize waits on a 100 ms setTimeout before its relayout, so timing the
// promise measured the timer. Here every step is (Δ CDP TaskDuration − idle rate × wall),
// with a 300 ms settle after each call so deferred work lands inside the window.
import { fileURLToPath } from "node:url";
import { chromium } from "playwright-core";
import http from "node:http";
import fs from "node:fs";
import path from "node:path";
import os from "node:os";

const DIR = fileURLToPath(new URL(".", import.meta.url));
const EXE = os.homedir() + "/Library/Caches/ms-playwright/chromium-1223/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing";
const server = http.createServer((q, r) => { const f = path.join(DIR, decodeURIComponent(q.url.split("?")[0]));
  if (!f.startsWith(DIR) || !fs.existsSync(f)) { r.writeHead(404); return r.end(); }
  r.writeHead(200, { "content-type": f.endsWith(".html") ? "text/html" : "text/javascript" }); fs.createReadStream(f).pipe(r); }).listen(0, "127.0.0.1");
await new Promise((r) => server.once("listening", r));
const BASE = `http://127.0.0.1:${server.address().port}/`;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const browser = await chromium.launch({ executablePath: EXE, headless: true, args: ["--use-angle=metal", "--enable-gpu", "--ignore-gpu-blocklist"] });
const SETTLE = 300, REPS = 11;

async function one(lib, N) {
  const page = await browser.newPage({ viewport: { width: 1300, height: 800 } });
  page.on("pageerror", (e) => console.error(lib, e.message));
  await page.goto(BASE + "bench.html");
  const cdp = await page.context().newCDPSession(page); await cdp.send("Performance.enable");
  const td = async () => (await cdp.send("Performance.getMetrics")).metrics.find((m) => m.name === "TaskDuration").value * 1000;
  let a = await td(), w = Date.now(); await sleep(1000); const idle = ((await td()) - a) / (Date.now() - w);
  const step = async (fn, reps = 1) => { const t0 = await td(), w0 = Date.now();
    for (let i = 0; i < reps; i++) { await fn(i); await sleep(SETTLE); }
    return ((await td()) - t0 - idle * (Date.now() - w0)) / reps; };
  const out = { lib, N, idle };
  out.load = await step(() => page.evaluate((l) => load(LIBS[l].src), lib));
  await page.evaluate((n) => { window.__a = pattern(n, 7); window.__b = pattern(n, 11); }, N);
  out.first = await step(() => page.evaluate((l) => LIBS[l].build(window.__a), lib));
  out.update = await step((i) => page.evaluate(([l, i]) => LIBS[l].update(i % 2 ? window.__a : window.__b), [lib, i]), REPS);
  out.zoom = await step((i) => page.evaluate(([l, i]) => LIBS[l].zoom(10 + i, 14 + i), [lib, i]), REPS);
  out.resize = await step((i) => page.evaluate(([l, i]) => LIBS[l].resize(i % 2 ? 1200 : 1000), [lib, i]), REPS);
  if (lib === "plotly") {   // the same resize without Plots.resize's timer: an explicit size through relayout
    out.resizeRelayout = await step((i) => page.evaluate((i) => Plotly.relayout(LIBS.plotly.el, { width: i % 2 ? 1200 : 1000, height: 600 }), i), REPS);
    out.resizeLatency = await page.evaluate(async () => { const el = LIBS.plotly.el; el.style.width = "1100px"; const t = performance.now(); await Plotly.Plots.resize(el); return performance.now() - t; });
  }
  await page.close();
  return out;
}
const rows = [];
for (const N of [22003, 59498]) for (const lib of ["plotly", "uplot"]) for (let r = 0; r < 3; r++) {
  const o = await one(lib, N); rows.push(o);
  console.log(`${lib.padEnd(7)} ${String(N).padEnd(6)} load ${o.load.toFixed(1).padStart(6)}  first ${o.first.toFixed(1).padStart(6)}  update ${o.update.toFixed(2).padStart(6)}  zoom ${o.zoom.toFixed(2).padStart(6)}  resize ${o.resize.toFixed(2).padStart(6)}` +
    (o.resizeRelayout !== undefined ? `  resize-by-relayout ${o.resizeRelayout.toFixed(2)}  Plots.resize latency ${o.resizeLatency.toFixed(0)}` : "") + `   (idle ${o.idle.toFixed(4)} ms/ms)`);
}
await browser.close(); server.close();

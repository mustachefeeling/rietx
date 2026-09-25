// Today's GUI (plotly) measured as main-thread WORK, with the latency beside it, and the
// numbers D4 and D8 need: the full-resolution payload, its parse, and one shared x axis
// built from the fitted and masked grids. One fresh state dir per run, so no run
// inherits the last one's excluded regions.  Usage: node gui_td.mjs <run-index>
import { fileURLToPath } from "node:url";
import { chromium } from "playwright-core";
import { spawn } from "node:child_process";
import path from "node:path";
import os from "node:os";

const DIR = fileURLToPath(new URL(".", import.meta.url)), RUN = process.argv[2] ?? "0";
const EXE = os.homedir() + "/Library/Caches/ms-playwright/chromium-1223/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing";
const RIETX = process.env.RIETX ?? fileURLToPath(new URL("../../../.venv/bin/rietx", import.meta.url));
const PORT = 8799, GUI = `http://127.0.0.1:${PORT}`;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const srv = spawn(RIETX, ["gui", "--no-open", "--machine", "--port", String(PORT), "--state-dir", path.join(DIR, "state", "run" + RUN)], { stdio: ["ignore", "pipe", "inherit"] });
await new Promise((r) => srv.stdout.once("data", r));
const api = async (p, body) => (await fetch(GUI + p, body === undefined ? {} : { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) })).json();
const browser = await chromium.launch({ executablePath: EXE, headless: true, args: ["--use-angle=metal", "--enable-gpu", "--ignore-gpu-blocklist"] });
try {
  await api("/api/examples/open", { name: "nac" });
  await api("/api/run", { kind: "fit" });
  for (;;) { const s = await api("/api/run/state"); if (s.state !== "running") break; await sleep(500); }
  const page = await browser.newPage({ viewport: { width: 1500, height: 1000 } });
  page.on("pageerror", (e) => console.error("gui", e.message));
  await page.addInitScript(() => {
    window.__log = []; window.__loaf = [];
    new PerformanceObserver((l) => { for (const e of l.getEntries()) window.__loaf.push({ at: e.startTime, dur: e.duration,
      scripts: (e.scripts ?? []).map((s) => `${s.invoker} ${Math.round(s.duration)}ms ${(s.sourceURL || "").split("/").pop()}:${s.sourceFunctionName || ""}`) }); })
      .observe({ type: "long-animation-frame", buffered: true });
    const wrap = () => { const P = window.Plotly; if (!P || P.__w) return; P.__w = true;
      for (const [o, n] of [[P, "react"], [P, "newPlot"], [P.Plots, "resize"]]) { const g = o[n]; o[n] = async function (...a) {
        const s = performance.now(), traces = (a[1] ?? []).map((t) => t.type).filter((v, i, xs) => xs.indexOf(v) === i).join("+");
        const r = await g.apply(this, a); window.__log.push({ k: n, s, e: performance.now(), traces }); return r; }; } };
    setInterval(wrap, 5);
  });
  // `boot` mode: no CDP Performance domain, which measurably slows script evaluation
  // (first plot 810-842 ms without it, 1573-1857 ms with it), so absolute boot numbers come from here
  const BOOT = process.argv[3] === "boot";
  const cdp = await page.context().newCDPSession(page); if (!BOOT) await cdp.send("Performance.enable");
  const td = async () => (await cdp.send("Performance.getMetrics")).metrics.find((m) => m.name === "TaskDuration").value * 1000;
  await page.goto(GUI + "/");
  await page.waitForFunction(() => window.__log.some((l) => l.k === "react"), null, { timeout: 60000 });
  const firstReact = await page.evaluate(() => window.__log.find((l) => l.k === "react").e);
  await sleep(2000);
  if (BOOT) {
    const loaf = await page.evaluate(() => window.__loaf.map((l) => ({ at: Math.round(l.at), dur: Math.round(l.dur), top: l.scripts.slice(0, 1) })));
    const calls = await page.evaluate(() => window.__log.map((l) => `${l.k}[${l.traces}] ${Math.round(l.s)}-${Math.round(l.e)}`));
    console.log(`run ${RUN} (uninstrumented boot): first react at ${firstReact.toFixed(0)} ms; long frames ${JSON.stringify(loaf)}; plotly calls ${JSON.stringify(calls)}`);
    process.exitCode = 0; throw new Error("boot-only run done");
  }
  const bootTD = await td();
  const bootLoaf = await page.evaluate(() => window.__loaf.map((l) => ({ at: Math.round(l.at), dur: Math.round(l.dur), top: l.scripts.slice(0, 2) })));
  console.log(`run ${RUN}: boot first react at ${firstReact.toFixed(0)} ms; main-thread work to boot+2 s ${bootTD.toFixed(0)} ms; boot long frames ${JSON.stringify(bootLoaf)}`);
  const bootCalls = await page.evaluate(() => window.__log.map((l) => `${l.k}[${l.traces}] ${Math.round(l.s)}-${Math.round(l.e)}`));
  console.log(`run ${RUN}: boot plotly calls ${JSON.stringify(bootCalls)}`);

  let a = await td(), w = Date.now(); await sleep(1500); const idle = ((await td()) - a) / (Date.now() - w);
  const box = await page.locator(".js-plotly-plot .draglayer .xy .nsewdrag").first().boundingBox();
  const at = (fx, fy) => [box.x + fx * box.width, box.y + fy * box.height];

  // hover sweep, with every long frame attributed to its scripts
  await page.evaluate(() => { window.__loaf = []; });
  let t0 = await td(), w0 = Date.now();
  for (let i = 0; i < 120; i++) { await page.mouse.move(...at(0.02 + 0.96 * i / 119, 0.5)); await sleep(16); }
  await sleep(300);
  const hover = ((await td()) - t0 - idle * (Date.now() - w0)) / 120;
  const hoverLoaf = await page.evaluate(() => window.__loaf.map((l) => ({ dur: Math.round(l.dur), scripts: l.scripts.slice(0, 3) })));
  console.log(`run ${RUN}: hover ${hover.toFixed(2)} ms/event; long frames ${JSON.stringify(hoverLoaf)}`);

  // resize: work vs latency, the viewport moved and the app's own ResizeObserver path left to run
  const works = [], lats = [];
  for (let i = 0; i < 5; i++) {
    await page.evaluate(() => { window.__mark = window.__log.length; });
    t0 = await td(); w0 = Date.now();
    await page.setViewportSize({ width: i % 2 ? 1500 : 1300, height: 1000 }); await sleep(600);
    works.push((await td()) - t0 - idle * (Date.now() - w0));
    lats.push(...await page.evaluate(() => window.__log.slice(window.__mark).filter((l) => l.k === "resize").map((l) => Math.round(l.e - l.s))));
  }
  console.log(`run ${RUN}: viewport resize, main-thread work per resize ${works.map((v) => v.toFixed(1)).join(", ")} ms; Plots.resize latency ${lats.join(", ")} ms`);

  // D4 + D8: the full-resolution window, its parse, and one x axis over both grids
  const d4 = await page.evaluate(async () => {
    const out = {};
    for (const mp of [4000, 200000]) {
      const t0 = performance.now(); const r = await fetch(`/api/result/window?max_points=${mp}`); const txt = await r.text(); const t1 = performance.now();
      const j = JSON.parse(txt); const t2 = performance.now();
      out[mp] = { bytes: txt.length, fetch_ms: +(t1 - t0).toFixed(1), parse_ms: +(t2 - t1).toFixed(1), n_fitted: j.two_theta?.length, n_masked: j.excluded?.two_theta?.length ?? 0,
        arrays: Object.entries(j).filter(([, v]) => Array.isArray(v)).map(([k, v]) => `${k}:${v.length}`) };
      if (mp === 200000) {   // merge two sorted grids and null-pad each series onto the union
        const a = j.two_theta, b = j.excluded?.two_theta ?? [], t3 = performance.now();
        const x = new Float64Array(a.length + b.length), ia = new Int32Array(a.length), ib = new Int32Array(b.length);
        let i = 0, k = 0, n = 0;
        while (i < a.length || k < b.length) { if (k >= b.length || (i < a.length && a[i] <= b[k])) { ia[i] = n; x[n++] = a[i++]; } else { ib[k] = n; x[n++] = b[k++]; } }
        const pad = (src, idx) => { const o = new Array(n).fill(null); for (let q = 0; q < idx.length; q++) o[idx[q]] = src[q]; return o; };
        const series = [pad(j.y_obs, ia), pad(j.y_calc, ia), pad(j.y_background ?? [], ia), pad(j.excluded?.y_obs ?? [], ib)];
        out.union = { n, ms: +(performance.now() - t3).toFixed(1), series: series.length };
      }
    }
    return out;
  });
  console.log(`run ${RUN}: window payload ${JSON.stringify(d4)}`);
  await page.close();
} finally { await browser.close(); srv.kill(); }

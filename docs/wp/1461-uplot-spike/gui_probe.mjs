// Time a zoom, a resize and a boot in the real `rietx gui`, split into
// server fetch vs plotly work, on the NAC example fitted through the server.
import { fileURLToPath } from "node:url";
import { chromium } from "playwright-core";
import { spawn } from "node:child_process";
import fs from "node:fs";
import os from "node:os";

const EXE = os.homedir() + "/Library/Caches/ms-playwright/chromium-1223/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing";
const SCRATCH = fileURLToPath(new URL(".", import.meta.url));
const PORT = 8799, BASE = `http://127.0.0.1:${PORT}`;
// A fresh state dir per run, so no run opens a project another driver already edited.
const freshState = () => { fs.mkdirSync(SCRATCH + "state", { recursive: true }); return fs.mkdtempSync(SCRATCH + "state/gui_probe-"); };
const RIETX = process.env.RIETX ?? fileURLToPath(new URL("../../../.venv/bin/rietx", import.meta.url));
const srv = spawn(RIETX,
  ["gui", "--no-open", "--machine", "--port", String(PORT), "--state-dir", freshState()],
  { stdio: ["ignore", "pipe", "inherit"] });
await new Promise((r) => srv.stdout.once("data", r));
const api = async (path, body) => (await fetch(BASE + path, body === undefined ? {} :
  { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) })).json();
try {
  const ex = await api("/api/examples");
  const list = ex.examples ?? ex;
  const nac = list.find((e) => /nac/i.test(e.name));
  console.log("example:", nac.name);
  await api("/api/examples/open", { name: nac.name });
  await api("/api/run", { kind: "fit" });
  for (;;) { const s = await api("/api/run/state"); if (s.state !== "running") break; await new Promise((r) => setTimeout(r, 500)); }

  const browser = await chromium.launch({ executablePath: EXE, headless: true,
    args: ["--use-angle=metal", "--enable-gpu", "--ignore-gpu-blocklist"] });
  const page = await browser.newPage({ viewport: { width: 1500, height: 950 } });
  page.on("pageerror", (e) => console.error("pageerror", e.message));
  // instrument before any app code runs: fetch timings, and plotly calls once it loads
  await page.addInitScript(() => {
    window.__log = []; const t0 = performance.now();
    const f = window.fetch;
    window.fetch = async (...a) => { const s = performance.now(); const r = await f(...a);
      const body = await r.clone().arrayBuffer();
      window.__log.push({ k: "fetch", url: String(a[0]).split("?")[0], s, e: performance.now(), bytes: body.byteLength }); return r; };
    const wrap = () => { const P = window.Plotly; if (!P || P.__w) return; P.__w = true;
      for (const [obj, name] of [[P, "react"], [P, "newPlot"], [P, "relayout"], [P.Plots, "resize"]]) {
        const orig = obj[name]; obj[name] = async function (...a) { const s = performance.now();
          const r = await orig.apply(this, a); window.__log.push({ k: name, s, e: performance.now() }); return r; }; } };
    setInterval(wrap, 5);
  });
  const nav = Date.now();
  await page.goto(BASE + "/");
  await page.waitForFunction(() => window.__log.some((l) => l.k === "react"), null, { timeout: 60000 });
  await page.waitForTimeout(1500);
  const boot = await page.evaluate(() => ({ nav: performance.timing.navigationStart,
    firstReact: window.__log.find((l) => l.k === "react").e,
    plotlyFetch: performance.getEntriesByType("resource").filter((r) => r.name.endsWith("/plotly.js"))
      .map((r) => ({ dur: r.duration, start: r.startTime, end: r.responseEnd, size: r.encodedBodySize })) }));
  console.log("boot: first react resolved at", boot.firstReact.toFixed(0), "ms after navigation; plotly.js resource", JSON.stringify(boot.plotlyFetch));

  // zooms: programmatic relayout fires the app's plotly_relayout handler, which refetches the window
  const zooms = [];
  for (const [lo, hi] of [[10, 14], [20, 22], [5, 30], [12, 12.8], [30, 40], [8, 9]]) {
    const r = await page.evaluate(async ([lo, hi]) => {
      const div = [...document.querySelectorAll(".js-plotly-plot")].find((d) => d.offsetParent && d._fullLayout?.yaxis2);
      const mark = window.__log.length; const s = performance.now();
      await window.Plotly.relayout(div, { "xaxis.range[0]": lo, "xaxis.range[1]": hi });
      // wait until a react lands after the window fetch, or 3 s
      for (let i = 0; i < 300; i++) { await new Promise((r) => setTimeout(r, 10));
        const after = window.__log.slice(mark);
        if (after.some((l) => l.k === "react") && after.some((l) => l.k === "fetch")) break; }
      await new Promise((r) => setTimeout(r, 300));
      const after = window.__log.slice(mark);
      return { total: Math.max(...after.map((l) => l.e)) - s,
        items: after.map((l) => `${l.k}${l.url ? " " + l.url : ""}${l.bytes ? " " + (l.bytes / 1024).toFixed(0) + "kB" : ""} ${(l.e - l.s).toFixed(1)}ms`) };
    }, [lo, hi]);
    zooms.push(r); console.log(`zoom ${lo}-${hi}: total ${r.total.toFixed(0)} ms |`, r.items.join(" | "));
  }
  // resizes: change the viewport and let the app's ResizeObserver + coalesce drive Plots.resize
  for (const w of [1200, 1500, 1100, 1500]) {
    const mark = await page.evaluate(() => window.__log.length);
    await page.setViewportSize({ width: w, height: 950 });
    await page.waitForTimeout(1200);
    const items = await page.evaluate((m) => window.__log.slice(m).map((l) => `${l.k}${l.url ? " " + l.url : ""} ${(l.e - l.s).toFixed(1)}ms`), mark);
    console.log(`resize to ${w}:`, items.join(" | "));
  }
  await page.screenshot({ path: SCRATCH + "gui.png" });
  await browser.close();
} finally { srv.kill(); }

// Where a hover's main-thread time goes, per renderer: one chromium trace of a
// 120-move sweep over the fitted NAC example, summed by trace event.
//
//   node hover_trace.mjs [plotly|chart]...
//
// Top-level events only (a task's children are counted in the task's own row
// too), so the rows are the kinds of work a move costs, not a partition of it.
import { fileURLToPath } from "node:url";
import { spawn, execSync } from "node:child_process";
import path from "node:path";
import os from "node:os";
import { chromium } from "playwright-core";

const DIR = fileURLToPath(new URL(".", import.meta.url));
const CFT = os.homedir() + "/Library/Caches/ms-playwright/chromium-1223/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing";
const RIETX = process.env.RIETX ?? fileURLToPath(new URL("../../../.venv/bin/rietx", import.meta.url));
const PORT = 8789, GUI = `http://127.0.0.1:${PORT}`;
const QUERY = { plotly: "", chart: "?chart=uplot" };
const renderers = process.argv.slice(2).length ? process.argv.slice(2) : ["plotly", "chart"];
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const state = path.join(DIR, "state", "hover-trace");
execSync(`rm -rf "${state}"`);
const srv = spawn(RIETX, ["gui", "--no-open", "--machine", "--port", String(PORT), "--state-dir", state],
                  { stdio: ["ignore", "pipe", "inherit"] });
await new Promise((r) => srv.stdout.once("data", r));
const api = (p, body) => fetch(GUI + p, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) });
const browser = await chromium.launch({ executablePath: CFT, headless: true });
try {
  await api("/api/examples/open", { name: "nac" });
  await api("/api/run", { kind: "fit" });
  for (;;) { const s = await (await fetch(GUI + "/api/run/state")).json(); if (s.state !== "running") break; await sleep(300); }
  for (const r of renderers) {
    const page = await browser.newPage({ viewport: { width: 1500, height: 1000 } });
    await page.goto(GUI + "/" + QUERY[r]);
    await page.waitForSelector(r === "plotly" ? ".js-plotly-plot .main-svg" : ".plot .u-over");
    if (process.env.CSS) await page.addStyleTag({ content: process.env.CSS });
    await sleep(2000);
    const box = await (r === "plotly" ? page.locator(".js-plotly-plot .draglayer .xy .nsewdrag").first()
                                      : page.locator(".plot .u-over").first()).boundingBox();
    const cdp = await page.context().newCDPSession(page);
    const events = [];
    cdp.on("Tracing.dataCollected", (d) => events.push(...d.value));
    const done = new Promise((res) => cdp.once("Tracing.tracingComplete", res));
    await cdp.send("Tracing.start", { categories: "devtools.timeline,disabled-by-default-devtools.timeline", transferMode: "ReportEvents" });
    for (let i = 0; i < 120; i++) { await page.mouse.move(box.x + (0.02 + 0.96 * i / 119) * box.width, box.y + box.height / 2); await sleep(16); }
    await cdp.send("Tracing.end");
    await done;
    const main = events.find((e) => e.name === "TracingStartedInBrowser")?.args?.data?.frames?.[0]?.processId;
    const sums = {};
    for (const e of events) {
      if (e.ph !== "X" || !e.dur || (main && e.pid !== main)) continue;
      sums[e.name] = (sums[e.name] ?? 0) + e.dur / 1000;
    }
    const top = Object.entries(sums).sort((a, b) => b[1] - a[1]).slice(0, 14)
      .map(([k, v]) => `${k} ${(v / 120).toFixed(2)}`).join(", ");
    console.log(`${r}: ms per move, by event: ${top}`);
    // which rectangles repaint, by size, so a paint can be traced to what moved
    const rects = {};
    for (const e of events) {
      if (e.name !== "Paint" || !e.args?.data?.clip) continue;
      const c = e.args.data.clip, w = Math.round(c[2] - c[0]), h = Math.round(c[5] - c[1]);
      const k = `${w}x${h}@${Math.round(c[0])},${Math.round(c[1])}`;
      rects[k] = rects[k] ?? { n: 0, ms: 0 };
      rects[k].n++;
      rects[k].ms += (e.dur ?? 0) / 1000;
    }
    const worst = Object.entries(rects).sort((a, b) => b[1].ms - a[1].ms).slice(0, 6)
      .map(([k, v]) => `${k} ×${v.n} ${v.ms.toFixed(0)} ms`).join("; ");
    console.log(`${r}: repainted rectangles (w×h@x,y, count, total): ${worst}`);
    await page.close();
  }
} finally {
  await browser.close();
  srv.kill();
}

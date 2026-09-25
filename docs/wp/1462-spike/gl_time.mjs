// How much main-thread time the viewer's WebGL calls take when the Model tab
// first opens in a fresh browser, beside the long animation frames of that
// opening (Chromium).  Every WebGL2 method is wrapped and timed.
//   node gl_time.mjs <project.rex>
import { chromium } from "playwright-core";
import { spawn } from "node:child_process";
import { mkdirSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const repo = resolve(here, "../../..");
const [project] = process.argv.slice(2);
const state = join(here, "shots", "gltime-state");
mkdirSync(state, { recursive: true });
const server = spawn(join(repo, ".venv/bin/rietx"), ["gui", project, "--scratch", "--no-open",
  "--port", "8794", "--state-dir", state], { stdio: "ignore" });
for (let k = 0; k < 120; k += 1) {
  try { if ((await fetch("http://127.0.0.1:8794/")).ok) break; } catch { /* not up yet */ }
  await new Promise((ok) => setTimeout(ok, 250));
}
const browser = await chromium.launch({ headless: process.env.HEADED !== "1" });
const page = await browser.newPage({ deviceScaleFactor: 2, viewport: { width: 1500, height: 950 } });
await page.addInitScript(() => {
  window.__gl = {};
  const proto = WebGL2RenderingContext.prototype;
  for (const name of Object.getOwnPropertyNames(proto)) {
    const d = Object.getOwnPropertyDescriptor(proto, name);
    if (!d || typeof d.value !== "function") continue;
    const orig = d.value;
    proto[name] = function (...args) {
      const t = performance.now();
      try { return orig.apply(this, args); } finally {
        const e = window.__gl[name] ?? (window.__gl[name] = { n: 0, ms: 0 });
        e.n += 1;
        e.ms += performance.now() - t;
      }
    };
  }
  window.__loaf = [];
  new PerformanceObserver((list) => {
    for (const e of list.getEntries()) window.__loaf.push({ start: Math.round(e.startTime), duration: Math.round(e.duration) });
  }).observe({ type: "long-animation-frame", buffered: true });
  const get = HTMLCanvasElement.prototype.getContext;
  HTMLCanvasElement.prototype.getContext = function (...args) {
    const t = performance.now();
    try { return get.apply(this, args); } finally {
      if (args[0] === "webgl2") window.__getContext = (window.__getContext ?? 0) + performance.now() - t;
    }
  };
});
await page.goto("http://127.0.0.1:8794/");
await page.waitForTimeout(2000);
const t0 = await page.evaluate(() => performance.now());
await page.getByRole("button", { name: "Model", exact: true }).click();
await page.waitForTimeout(2500);
const out = await page.evaluate((t) => ({
  loaf: window.__loaf.filter((e) => e.start >= t),
  getContext: Math.round(window.__getContext ?? 0),
  gl: Object.entries(window.__gl).sort((a, b) => b[1].ms - a[1].ms).slice(0, 8)
    .map(([k, v]) => `${k} ×${v.n} ${v.ms.toFixed(1)} ms`),
  total: Object.values(window.__gl).reduce((s, v) => s + v.ms, 0).toFixed(1),
}), t0);
console.log(JSON.stringify(out));
await browser.close();
server.kill();

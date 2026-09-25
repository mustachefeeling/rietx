// Which script a long animation frame on opening the Model tab belongs to
// (Chromium's long-animation-frame entries name their scripts).
//   node loaf_attribution.mjs <project.rex>
import { chromium } from "playwright-core";
import { spawn } from "node:child_process";
import { mkdirSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const repo = resolve(here, "../../..");
const [project] = process.argv.slice(2);
const state = join(here, "shots", "loaf-state");
mkdirSync(state, { recursive: true });
const server = spawn(join(repo, ".venv/bin/rietx"), ["gui", project, "--scratch", "--no-open",
  "--port", "8795", "--state-dir", state], { stdio: "ignore" });
for (let k = 0; k < 120; k += 1) {
  try { if ((await fetch("http://127.0.0.1:8795/")).ok) break; } catch { /* not up yet */ }
  await new Promise((ok) => setTimeout(ok, 250));
}
const browser = await chromium.launch({ headless: process.env.HEADED !== "1" });
const page = await browser.newPage({ deviceScaleFactor: 2, viewport: { width: 1500, height: 950 } });
await page.addInitScript(() => {
  window.__loaf = [];
  new PerformanceObserver((list) => {
    for (const e of list.getEntries()) {
      window.__loaf.push({
        start: Math.round(e.startTime), duration: Math.round(e.duration),
        render: Math.round(e.renderStart ? e.startTime + e.duration - e.renderStart : 0),
        scripts: e.scripts.map((s) => ({
          invoker: s.invoker, source: (s.sourceURL || "").split("/").pop(),
          fn: s.sourceFunctionName, duration: Math.round(s.duration),
        })),
      });
    }
  }).observe({ type: "long-animation-frame", buffered: true });
});
await page.goto("http://127.0.0.1:8795/");
await page.waitForTimeout(2000);
const t = await page.evaluate(() => performance.now());
await page.getByRole("button", { name: "Model", exact: true }).click();
await page.waitForTimeout(2500);
const frames = await page.evaluate((t0) => window.__loaf.filter((e) => e.start >= t0), t);
console.log("viewer open:", JSON.stringify(frames));
// the same opening with the viewer closed, if the closed state survives a reload
await page.getByRole("button", { name: "3D", exact: true }).click();
await page.waitForTimeout(800);
await page.reload();
await page.waitForTimeout(2000);
const t2 = await page.evaluate(() => performance.now());
await page.getByRole("button", { name: "Model", exact: true }).click();
await page.waitForTimeout(2500);
const closed = await page.evaluate(() => document.querySelector(".viewer canvas") === null);
const frames2 = await page.evaluate((t0) => window.__loaf.filter((e) => e.start >= t0), t2);
console.log(`viewer ${closed ? "closed" : "STILL OPEN"}:`, JSON.stringify(frames2));
await browser.close();
server.kill();

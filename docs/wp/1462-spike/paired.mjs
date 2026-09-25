// The structure viewer, whichever build the GUI serves, measured the way a
// person meets it: time from opening the Model tab to a drawn picture, frame
// intervals and long animation frames over a trackball drag, and over a hover
// sweep.  Run once against each build on the same machine and load.
//   node paired.mjs <project.rex> <engine> <label> [runs]
// Appends one line per run to results/paired_<engine>_<label>.txt.
import { chromium, firefox, webkit } from "playwright-core";
import { spawn } from "node:child_process";
import { appendFileSync, mkdirSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { cpus, loadavg } from "node:os";

const here = dirname(fileURLToPath(import.meta.url));
const repo = resolve(here, "../../..");
const [project, engine = "chromium", label = "new", runsArg = "3"] = process.argv.slice(2);
const log = join(here, "results", `paired_${engine}_${label}.txt`);
const state = join(here, "shots", "paired-state");
mkdirSync(state, { recursive: true });
const q = (xs, p) => { const s = [...xs].sort((a, b) => a - b); return s.length ? s[Math.min(s.length - 1, Math.floor(p * s.length))] : NaN; };

for (let run = 0; run < Number(runsArg); run += 1) {
  const server = spawn(join(repo, ".venv/bin/rietx"), ["gui", project, "--scratch", "--no-open",
    "--port", "8796", "--state-dir", state], { stdio: "ignore" });
  await new Promise((ok) => setTimeout(ok, 2500));
  const browser = await { chromium, firefox, webkit }[engine].launch({ headless: process.env.HEADED !== "1" });
  const page = await browser.newPage({ deviceScaleFactor: 2, viewport: { width: 1500, height: 950 } });
  await page.addInitScript(() => {
    window.__loaf = [];
    try {
      new PerformanceObserver((list) => {
        for (const e of list.getEntries()) window.__loaf.push({ t: e.startTime, d: e.duration });
      }).observe({ type: "long-animation-frame", buffered: true });
    } catch { /* not Chromium */ }
    window.__gaps = null;
    window.__watch = () => {
      window.__gaps = [];
      let last = performance.now();
      const tick = () => {
        const now = performance.now();
        window.__gaps.push(now - last);
        last = now;
        if (window.__gaps) requestAnimationFrame(tick);
      };
      requestAnimationFrame(tick);
    };
    window.__stop = () => { const g = window.__gaps; window.__gaps = null; return g; };
  });
  await page.goto("http://127.0.0.1:8796/");
  await page.waitForTimeout(2000);
  const shown = await page.evaluate(() => performance.now());
  await page.getByRole("button", { name: "Model", exact: true }).click();
  // the picture: poll the plot until it holds a drawn structure
  const plot = page.locator(".viewer .plot");
  let firstFrame = NaN;
  for (let k = 0; k < 200; k += 1) {
    try {
      const png = await plot.screenshot({ timeout: 2000 });
      // count dark-ish pixels cheaply on the PNG bytes' decoded size proxy:
      // the drawn structure makes the file several times larger than a blank box
      if (png.length > 20000) {
        firstFrame = (await page.evaluate(() => performance.now())) - shown;
        break;
      }
    } catch { /* not laid out yet */ }
    await page.waitForTimeout(25);
  }
  const loafOpen = await page.evaluate((t) => window.__loaf.filter((e) => e.t >= t)
    .map((e) => Math.round(e.d)), shown);
  // a trackball drag: 60 moves
  const box = await plot.boundingBox();
  const cx = box.x + box.width / 2, cy = box.y + box.height / 2;
  await page.waitForTimeout(500);
  const before = await page.evaluate(() => performance.now());
  await page.evaluate(() => window.__watch());
  await page.mouse.move(cx - 90, cy);
  await page.mouse.down();
  for (let k = 0; k < 60; k += 1) await page.mouse.move(cx - 90 + 3 * k, cy + Math.sin(k / 6) * 20);
  await page.mouse.up();
  const drag = await page.evaluate(() => window.__stop());
  const loafDrag = await page.evaluate((t) => window.__loaf.filter((e) => e.t >= t).length, before);
  // a hover sweep: 60 moves, no button
  const before2 = await page.evaluate(() => performance.now());
  await page.evaluate(() => window.__watch());
  for (let k = 0; k < 60; k += 1) await page.mouse.move(cx - 90 + 3 * k, cy - 30 + k);
  const hover = await page.evaluate(() => window.__stop());
  const loafHover = await page.evaluate((t) => window.__loaf.filter((e) => e.t >= t).length, before2);
  const line = `${new Date().toISOString()} ${engine} ${label} run ${run}`
    + ` | first frame ${Math.round(firstFrame)} ms, long frames while opening ${JSON.stringify(loafOpen)}`
    + ` | drag gap p50 ${q(drag, 0.5).toFixed(1)} p95 ${q(drag, 0.95).toFixed(1)} ms over ${drag.length}, long frames ${loafDrag}`
    + ` | hover gap p95 ${q(hover, 0.95).toFixed(1)} ms, long frames ${loafHover}`
    + ` | load ${loadavg()[0].toFixed(1)} on ${cpus().length} cpus`;
  console.log(line);
  appendFileSync(log, line + "\n");
  await browser.close();
  server.kill();
  await new Promise((ok) => setTimeout(ok, 500));
}

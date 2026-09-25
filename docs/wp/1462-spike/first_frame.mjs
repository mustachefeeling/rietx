// Does the viewer's first frame show, and when?  Counts draw calls and canvas
// sizes, and screenshots the canvas at a few delays after the Model tab opens.
//   node first_frame.mjs <project.rex> <engine> <out-dir>
import { chromium, firefox, webkit } from "playwright-core";
import { spawn } from "node:child_process";
import { mkdirSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const repo = resolve(here, "../../..");
const [project, engine = "firefox", outArg] = process.argv.slice(2);
const out = resolve(outArg ?? join(here, "shots"));
mkdirSync(join(out, "state"), { recursive: true });
const server = spawn(join(repo, ".venv/bin/rietx"), ["gui", project, "--scratch", "--no-open",
  "--port", "8797", "--state-dir", join(out, "state")], { stdio: "ignore" });
await new Promise((ok) => setTimeout(ok, 2500));
const browser = await { chromium, firefox, webkit }[engine].launch({ headless: process.env.HEADED !== "1" });
const page = await browser.newPage({ deviceScaleFactor: 2, viewport: { width: 1500, height: 950 } });
await page.addInitScript(() => {
  window.__draws = [];
  const orig = WebGL2RenderingContext.prototype.drawArraysInstanced;
  WebGL2RenderingContext.prototype.drawArraysInstanced = function (...args) {
    const c = this.canvas;
    window.__draws.push({ t: Math.round(performance.now()), w: c.width, h: c.height,
                          cw: c.clientWidth, n: args[3] });
    return orig.apply(this, args);
  };
});
await page.goto("http://127.0.0.1:8797/");
await page.waitForTimeout(1500);
await page.getByRole("button", { name: "Model", exact: true }).click();
const t0 = await page.evaluate(() => performance.now());
for (const wait of [300, 1200, 3000]) {
  await page.waitForTimeout(wait);
  const shot = join(out, `${engine}-first-${wait}.png`);
  await page.locator(".viewer canvas").screenshot({ path: shot });
}
const draws = await page.evaluate(() => window.__draws);
console.log(engine, "Model opened at", Math.round(t0), "ms; draws:", JSON.stringify(draws.slice(0, 12)));
await browser.close();
server.kill();

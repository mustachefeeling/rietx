// The real GUI's structure viewer in a browser: screenshots, a drag, a hover,
// both PNG exports, WebGL contexts across toggles, and any /plotly.js request.
//   node gui_viewer.mjs <project.rex> [chromium|firefox|webkit] [out-dir]
// Starts `rietx gui --scratch` on port 8798 from the repository's .venv.
import { chromium, firefox, webkit } from "playwright-core";
import { spawn } from "node:child_process";
import { mkdirSync, writeFileSync, readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const repo = resolve(here, "../../..");
const [project, engine = "chromium", outArg] = process.argv.slice(2);
const out = resolve(outArg ?? join(here, "shots"));
mkdirSync(out, { recursive: true });
const rietx = process.env.RIETX ?? join(repo, ".venv/bin/rietx");
const state = join(out, "state");
mkdirSync(state, { recursive: true });

const server = spawn(rietx, ["gui", project, "--scratch", "--no-open", "--port", "8798",
                             "--state-dir", state], { stdio: ["ignore", "pipe", "pipe"] });
await new Promise((ok) => setTimeout(ok, 2500));

const browser = await { chromium, firefox, webkit }[engine].launch({ headless: process.env.HEADED !== "1" });
const ctx = await browser.newContext({ deviceScaleFactor: 2, viewport: { width: 1500, height: 950 },
                                       acceptDownloads: true });
const page = await ctx.newPage();
const plotly = [];
const errors = [];
page.on("request", (r) => { if (r.url().includes("plotly")) plotly.push(r.url()); });
const failed = [];
page.on("response", (r) => { if (r.status() >= 400) failed.push(`${r.status()} ${r.request().method()} ${r.url()}`); });
page.on("pageerror", (e) => errors.push(e.message));
page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
// count WebGL2 contexts made and lost, across the page's life
await page.addInitScript(() => {
  window.__gl = { made: 0, lost: 0 };
  const get = HTMLCanvasElement.prototype.getContext;
  HTMLCanvasElement.prototype.getContext = function (kind, ...rest) {
    const c = get.call(this, kind, ...rest);
    if (kind === "webgl2" && c && !this.__counted) {
      this.__counted = true;
      window.__gl.made += 1;
      this.addEventListener("webglcontextlost", () => { window.__gl.lost += 1; });
    }
    return c;
  };
});
await page.goto("http://127.0.0.1:8798/");
await page.waitForTimeout(1500);
await page.getByRole("button", { name: "Model", exact: true }).click();
const canvas = page.locator(".viewer canvas");
await canvas.waitFor();
await page.waitForTimeout(800);
const viewer = page.locator(".viewer");
await viewer.screenshot({ path: join(out, `${engine}-gui-ball.png`) });

const box = await canvas.boundingBox();
const cx = box.x + box.width / 2, cy = box.y + box.height / 2;
// a hover sweep until the readout says something
let reading = "";
for (let dx = -60; dx <= 60 && !reading; dx += 6) {
  await page.mouse.move(cx + dx, cy + dx / 3);
  await page.waitForTimeout(30);
  reading = (await page.locator(".viewer .reading").textContent()).trim();
}
// a drag
await page.mouse.move(cx, cy);
await page.mouse.down();
for (let k = 1; k <= 20; k += 1) await page.mouse.move(cx + 4 * k, cy + 1.5 * k);
await page.mouse.up();
await page.waitForTimeout(300);
await viewer.screenshot({ path: join(out, `${engine}-gui-dragged.png`) });
await page.getByRole("button", { name: "ellipsoids", exact: true }).click();
await page.waitForTimeout(400);
await viewer.screenshot({ path: join(out, `${engine}-gui-ellipsoid.png`) });

// the two exports
const exportsMade = [];
for (const transparent of [false, true]) {
  if (transparent) {
    await page.getByRole("button", { name: /drawing/ }).click();
    await page.locator(".drawer label", { hasText: "transparent PNG" }).locator("input").check();
  }
  const [download] = await Promise.all([
    page.waitForEvent("download", { timeout: 20000 }),
    page.getByRole("button", { name: "PNG", exact: true }).click(),
  ]);
  const file = join(out, `${engine}-export${transparent ? "-transparent" : ""}.png`);
  await download.saveAs(file);
  const png = readFileSync(file);
  // IHDR: width, height, bit depth, colour type (2 = RGB, 6 = RGBA)
  exportsMade.push({ transparent, bytes: png.length, width: png.readUInt32BE(16),
                     height: png.readUInt32BE(20), colourType: png[25] });
}

// toggle the viewer off and on: every context made should be given back
for (let k = 0; k < 5; k += 1) {
  await page.getByRole("button", { name: "3D", exact: true }).click();
  await page.waitForTimeout(150);
  await page.getByRole("button", { name: "3D", exact: true }).click();
  await page.waitForTimeout(300);
}
const gl = await page.evaluate(() => window.__gl);

const result = { engine, reading, exports: exportsMade, contexts: gl, plotlyRequests: plotly,
                 failed, errors };
console.log(JSON.stringify(result, null, 1));
writeFileSync(join(out, `${engine}-gui.json`), JSON.stringify(result, null, 1));
await browser.close();
server.kill();

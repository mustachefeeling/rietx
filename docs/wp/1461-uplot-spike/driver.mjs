import { chromium } from "playwright-core";
import os from "node:os";

const EXE = os.homedir() + "/Library/Caches/ms-playwright/chromium-1223/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing";
const url = new URL("./bench.html", import.meta.url).href;
const gpu = process.argv[2] !== "nogpu";
const browser = await chromium.launch({ executablePath: EXE, headless: true,
  args: gpu ? ["--use-angle=metal", "--enable-gpu", "--ignore-gpu-blocklist"] : ["--disable-gpu"] });
const rows = [];
for (const N of [7347, 22003]) {
  for (const lib of ["plotly", "uplot", "echarts"]) {
    for (let rep = 0; rep < 3; rep++) {
      // a fresh page per run, so each library pays its own load and nothing is warm
      const page = await browser.newPage({ viewport: { width: 1300, height: 800 } });
      page.on("pageerror", (e) => console.error(lib, e.message));
      await page.goto(url);
      rows.push(await page.evaluate(([l, n]) => window.run(l, n), [lib, N]));
      await page.close();
    }
  }
}
await browser.close();
const f = (v) => v.toFixed(1).padStart(7);
console.log("gpu flags:", gpu);
console.log("lib      N      load   first  update   zoom  resize  renderer");
for (const r of rows)
  console.log(r.lib.padEnd(8), String(r.N).padEnd(6), f(r.loadMs), f(r.firstMs), f(r.updateMs), f(r.zoomMs), f(r.resizeMs), " ", r.renderer);

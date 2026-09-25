// Drive the prototype page in chromium, firefox and webkit: timings, rotation, picking, screenshots.
import { chromium, firefox, webkit } from "playwright-core";
import { createServer } from "node:http";
import { readFileSync } from "node:fs";
import { dirname, join, extname } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const types = { ".html": "text/html", ".js": "text/javascript", ".json": "application/json" };
const server = createServer((req, res) => {
  const path = join(here, new URL(req.url, "http://x").pathname);
  try { const body = readFileSync(path); res.writeHead(200, { "content-type": types[extname(path)] || "text/plain" }); res.end(body); }
  catch { res.writeHead(404); res.end(); }
}).listen(8823);

const engines = { chromium, firefox, webkit };
const wanted = process.argv[2] ? process.argv[2].split(",") : Object.keys(engines);
const cases = [["lab6", "ball"], ["nac", "ellipsoid"], ["fap", "ball"], ["nac", "ball"], ["nac", "ball", "poly"]];
const q = (xs, p) => { const s = [...xs].sort((a, b) => a - b); return s[Math.min(s.length - 1, Math.floor(p * s.length))]; };

for (const name of wanted) {
  const browser = await engines[name].launch({ headless: process.env.HEADED !== "1" });
  for (const dpr of [2]) {
    const ctx = await browser.newContext({ deviceScaleFactor: dpr, viewport: { width: 700, height: 560 } });
    for (const [s, mode, extra = ""] of cases) {
      const label = extra ? `${mode}+${extra}` : mode;
      const page = await ctx.newPage();
      const errors = [];
      page.on("pageerror", (e) => errors.push(e.message));
      page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
      await page.goto(`http://127.0.0.1:8823/index.html?s=${s}&mode=${mode}${extra ? "&" + extra : ""}&rot=${process.env.ROT || 0.6}`);
      await page.waitForFunction(() => window.ready === true, null, { timeout: 30000 });
      const t = await page.evaluate(() => window.timings);
      const gpu = await page.evaluate(() => {
        const gl = document.createElement("canvas").getContext("webgl2");
        const ext = gl && gl.getExtension("WEBGL_debug_renderer_info");
        return ext ? gl.getParameter(ext.UNMASKED_RENDERER_WEBGL) : gl ? gl.getParameter(gl.RENDERER) : "none";
      });
      await page.locator("#wrap").screenshot({ path: join(here, "shots", `${name}_${s}_${label}_dpr${dpr}.png`) });
      const spin = await page.evaluate(() => window.spin(240));
      const pick = await page.evaluate(() => window.pickBench(2000));
      // a real hover: move to the canvas centre and read the tooltip
      await page.mouse.move(350, 280);
      const tip = await page.evaluate(() => document.getElementById("tip").textContent);
      console.log(`${name.padEnd(8)} dpr${dpr} ${s.padEnd(4)} ${label.padEnd(9)} atoms ${t.counts.atoms} halves ${t.counts.bondHalves}` +
        ` | import ${t.import.toFixed(1)} create ${t.create.toFixed(1)} set ${t.set.toFixed(1)} data→frame ${t.toFrame.toFixed(1)} ms` +
        ` | draw p50 ${q(spin.work, 0.5).toFixed(2)} p95 ${q(spin.work, 0.95).toFixed(2)} ms, gap p95 ${q(spin.gaps, 0.95).toFixed(1)} ms` +
        ` | pick ${(pick.perPick * 1000).toFixed(1)} µs (${pick.hits} hits) | tip "${tip}" | ${errors.length ? "ERR " + errors.join("; ") : "ok"}`);
      if (s === "lab6") console.log(`         gpu: ${gpu}`);
      await page.close();
    }
    await ctx.close();
  }
  await browser.close();
}
server.close();

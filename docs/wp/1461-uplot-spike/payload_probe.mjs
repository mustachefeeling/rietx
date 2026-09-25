// WP-1461 task 2, the browser's half: fetch, decode, parse and grid union for every payload
// payloads.py wrote, in Chrome for Testing or the installed Firefox.
//   node payload_probe.mjs chrome|firefox        needs `node serve.mjs 8811` running
// Each file is fetched REPS+1 times with the cache off; the first is a warm-up and is dropped.
// "union" builds what the pattern panel's panes draw from: one x, and five series null-padded
// onto it (observed fitted, observed masked, calc, background, delta).
//   A (today's shape): merge the fitted and masked grids, then pad each series by position.
//   B (proposed): the pattern's own grid is the union, and the fitted index places the model.
import puppeteer from "puppeteer-core";
import os from "node:os";
import fs from "node:fs";
import { fileURLToPath } from "node:url";

const [BROWSER = "chrome"] = process.argv.slice(2), REPS = 5;
const DIR = fileURLToPath(new URL(".", import.meta.url));
const manifest = JSON.parse(fs.readFileSync(DIR + "payloads/manifest.json", "utf8"));
const browser = await puppeteer.launch(BROWSER === "firefox"
  // Firefox rounds performance.now() to 1 ms unless told not to
  ? { browser: "firefox", executablePath: "/Applications/Firefox.app/Contents/MacOS/firefox", headless: true,
      extraPrefsFirefox: { "privacy.reduceTimerPrecision": false } }
  : { executablePath: os.homedir() + "/Library/Caches/ms-playwright/chromium-1223/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing",
      headless: true });
const page = await browser.newPage();
page.on("pageerror", (e) => console.error("PAGEERROR", e.message));
await page.goto("http://127.0.0.1:8811/index.html");
console.log(`${BROWSER} ${await browser.version()}, load ${os.loadavg().map((l) => l.toFixed(1)).join(" ")}`);

for (const m of manifest) {
  const runs = await page.evaluate(async (m, reps) => {
    const TYPES = { "<f8": Float64Array, "<f4": Float32Array, "<i4": Int32Array };
    const merge = (j) => {
      const a = j.two_theta, ex = j.excluded ?? { two_theta: [], y_obs: [] }, b = ex.two_theta;
      const x = new Float64Array(a.length + b.length), ia = new Int32Array(a.length), ib = new Int32Array(b.length);
      let i = 0, k = 0, n = 0;
      while (i < a.length || k < b.length) {
        if (k >= b.length || (i < a.length && a[i] <= b[k])) { ia[i] = n; x[n++] = a[i++]; } else { ib[k] = n; x[n++] = b[k++]; }
      }
      const pad = (src, idx) => { const o = new Array(n).fill(null); for (let q = 0; q < idx.length; q++) o[idx[q]] = src[q]; return o; };
      return [x, pad(j.y_obs, ia), pad(ex.y_obs, ib), pad(j.y_calc, ia), pad(j.y_background, ia), pad(j.delta, ia)];
    };
    const scatter = (j) => {
      const n = j.two_theta.length, fit = j.fitted, y = j.y_obs;
      const obs = new Array(n).fill(null), masked = Array.from(y), calc = new Array(n).fill(null);
      const bkg = new Array(n).fill(null), delta = new Array(n).fill(null);
      for (let q = 0; q < fit.length; q++) {
        const i = fit[q]; obs[i] = y[i]; masked[i] = null; calc[i] = j.y_calc[q]; bkg[i] = j.y_background[q]; delta[i] = j.delta[q];
      }
      return [j.two_theta, obs, masked, calc, bkg, delta];
    };
    const out = [];
    for (let r = 0; r <= reps; r++) {
      const t0 = performance.now();
      const buf = await (await fetch("/payloads/" + m.file, { cache: "no-store" })).arrayBuffer();
      const t1 = performance.now();
      let j, decode = 0;
      if (m.file.endsWith(".json")) {
        const txt = new TextDecoder().decode(buf); decode = performance.now() - t1; j = JSON.parse(txt);
      } else {
        const h = new DataView(buf).getUint32(0, true);
        j = JSON.parse(new TextDecoder().decode(new Uint8Array(buf, 4, h)));
        for (const a of j.arrays) j[a.name] = new TYPES[a.dtype](buf, 4 + h + a.offset, a.length);
      }
      const t2 = performance.now();
      const drawn = m.kind === "A_json" ? merge(j) : m.kind.startsWith("B_") ? scatter(j) : null;
      const t3 = performance.now();
      if (r) out.push({ fetch: t1 - t0, decode, parse: t2 - t1 - decode, union: drawn ? t3 - t2 : null, n: drawn?.[0].length });
    }
    return out;
  }, m, REPS);
  const rng = (k) => { const v = runs.map((x) => x[k]); return `${Math.min(...v).toFixed(1)}-${Math.max(...v).toFixed(1)}`; };
  const union = runs[0].union == null ? "" : `, union onto ${runs[0].n} ${rng("union")}`;
  console.log(`${m.file.padEnd(22)} ${(m.bytes / 1e6).toFixed(2).padStart(5)} MB  fetch ${rng("fetch")}, decode ${rng("decode")}, parse ${rng("parse")}${union} ms`);
}
await browser.close();

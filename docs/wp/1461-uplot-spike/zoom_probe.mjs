// Count the paints behind one zoom, and time them, in Chrome for Testing or the installed Firefox.
//   node zoom_probe.mjs chrome|firefox [dpr] [echo]      needs `node serve.mjs 8810` running
// `echo` puts back the link proto.html had before 2026-09-25: every setScale hook set the other
// panes unconditionally, and the flag meant to stop the echo was clear before the hooks ran.
// The paint timer hooks every pane: drawClear first → draw last, with drawAxes and drawSeries
// marks between, so a slow paint prints which series it spent the time in.
import puppeteer from "puppeteer-core";
import os from "node:os";

const [BROWSER = "chrome", DPR = "2", ECHO = ""] = process.argv.slice(2), N = 59498;
const browser = await puppeteer.launch(BROWSER === "firefox"
  ? { browser: "firefox", executablePath: "/Applications/Firefox.app/Contents/MacOS/firefox", headless: true,
      extraPrefsFirefox: { "layout.css.devPixelsPerPx": DPR }, defaultViewport: { width: 1300, height: 1000 } }
  : { executablePath: os.homedir() + "/Library/Caches/ms-playwright/chromium-1223/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing",
      headless: true, args: ["--use-angle=metal", "--enable-gpu", "--ignore-gpu-blocklist"], defaultViewport: { width: 1300, height: 1000, deviceScaleFactor: +DPR } });
const page = await browser.newPage();
page.on("pageerror", (e) => console.error("PAGEERROR", e.message));
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
await page.goto(`http://127.0.0.1:8810/proto.html?n=${N}`);
await page.evaluate((n) => P.mount(n), N);
await page.evaluate((echo) => {
  if (echo) {
    const link = (u, key) => { if (key === "x") for (const k of ["main", "ticks", "resid"]) if (U[k] !== u) U[k].setScale("x", { min: u.scales.x.min, max: u.scales.x.max }); };
    for (const k of ["main", "ticks", "resid"]) U[k].hooks.setScale = [link];
  }
  window.__paint = { main: [], ticks: [], resid: [] }; window.__slow = [];
  for (const k of ["main", "ticks", "resid"]) {
    const h = U[k].hooks; let t0 = 0, marks = [];
    h.drawClear.unshift(() => { t0 = performance.now(); marks = []; });
    (h.drawAxes ??= []).push(() => marks.push(["axes", performance.now()]));
    (h.drawSeries ??= []).push((u, si) => marks.push([u.series[si].label, performance.now()]));
    (h.draw ??= []).push(() => {
      const t1 = performance.now(); window.__paint[k].push(t1 - t0); if (t1 - t0 <= 20) return;
      let prev = t0; window.__slow.push(`${k} ${(t1 - t0).toFixed(0)} ms: ` + [...marks, ["hooks", t1]].map(([n, t]) => { const d = t - prev; prev = t; return `${n} ${d.toFixed(0)}`; }).join(", "));
    });
  }
}, ECHO);
const reset = () => page.evaluate(() => { for (const k in window.__paint) window.__paint[k] = []; });
const paints = () => page.evaluate(() => structuredClone(window.__paint));
const r = await page.evaluate(() => { const b = U.main.over.getBoundingClientRect(); return { x: b.left, y: b.top, w: b.width, h: b.height }; });
const sum = (a) => a.reduce((s, v) => s + v, 0), KS = ["main", "ticks", "resid"];
const counts = (p, n) => KS.map((k) => `${k} ${(p[k].length / n).toFixed(1)}`).join(", ");

console.log(`${BROWSER} ${(await browser.version())}, devicePixelRatio ${DPR}, ${N} points, ${ECHO ? "echo put back" : "proto.html as committed"}`);
const DRAGS = 12, per = [], all = { main: [], ticks: [], resid: [] };
for (let g = 0; g < DRAGS; g++) {   // the same drag each time, from the full range
  await page.mouse.click(r.x + r.w / 2, r.y + r.h / 2, { clickCount: 2 }); await sleep(150);
  await page.mouse.move(r.x + 300, r.y + 200); await page.mouse.down();
  for (let s = 1; s <= 8; s++) await page.mouse.move(r.x + 300 + s * 30, r.y + 200);
  await sleep(100); await reset(); await page.mouse.up(); await sleep(250);
  const p = await paints(); for (const k of KS) all[k].push(...p[k]); per.push(KS.map((k) => sum(p[k]).toFixed(0)).join("/"));
}
console.log(`drag zoom   paints per zoom: ${counts(all, DRAGS)}`);
console.log(`            paint ms per drag, main/ticks/resid: ${per.join("  ")}`);
await page.mouse.click(r.x + r.w / 2, r.y + r.h / 2, { clickCount: 2 }); await sleep(150);
await page.mouse.move(r.x + r.w / 2, r.y + 200); await sleep(100); await reset();
const WHEELS = 30;
for (let i = 0; i < WHEELS; i++) { await page.mouse.wheel({ deltaY: i < 15 ? -60 : 60 }); await sleep(20); }
await sleep(250);
const w = await paints();
console.log(`wheel zoom  paints per zoom: ${counts(w, WHEELS)}; paint ms per zoom ${(sum(KS.map((k) => sum(w[k]))) / WHEELS).toFixed(1)} (${KS.map((k) => `${k} ${(sum(w[k]) / WHEELS).toFixed(1)}`).join(", ")})`);
const slow = await page.evaluate(() => window.__slow);
console.log(slow.length ? "paints over 20 ms:\n  " + slow.join("\n  ") : "no paint over 20 ms");
await browser.close();

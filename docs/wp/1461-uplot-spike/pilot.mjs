// WP-1461's pilot probe: the real GUI's pattern panel, plotly against the chart
// module, measured the same way on the same server. Acceptance 1-3 and 7.
//
//   node pilot.mjs <engine> <dataset> <dpr> <run> <renderer>...
//
// engine: chromium (Chrome for Testing 1223, CDP work), firefox or webkit
// (playwright's builds, work from wrapped callbacks). dataset: nac, or a path to
// a .rex project to open (make_lab6.py builds the 132 992-channel one).
// renderer: plotly or chart (the chart module; until D5 was decided, `uplot`
// drew every marker and `thin` each pixel column's extremes). One server
// and one fit per call, a fresh page per renderer, so the renderers of one call
// are measured side by side.
//
// With RIETX_PLOTLY set, the plotly renderer is served by that command, a second
// server with a fit of its own ten ports up, and the chart by RIETX. That is
// task 14's pairing: the final tree has no plotly renderer, so plotly comes from a
// build of 58f7dbce, the last commit that had one. Both servers stay up for the
// call, so its renderers are still measured side by side.
//
// Work, per event: the change in CDP TaskDuration less the page's idle rate over
// the same wall time (chromium), and the time inside every listener, microtask,
// timer, frame and ResizeObserver callback the page registered (every engine;
// the `wrapped` figure). Frames: requestAnimationFrame intervals and, in
// chromium, the long-animation-frame entries.
import { fileURLToPath } from "node:url";
import { spawn, execSync } from "node:child_process";
import path from "node:path";
import os from "node:os";
import { chromium, firefox, webkit } from "playwright-core";

const DIR = fileURLToPath(new URL(".", import.meta.url));
const [ENGINE = "chromium", DATASET = "nac", DPR = "1", RUN = "0", ...RENDERERS] = process.argv.slice(2);
const renderers = RENDERERS.length ? RENDERERS : ["plotly", "chart"];
const CFT = os.homedir() + "/Library/Caches/ms-playwright/chromium-1223/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing";
const RIETX = process.env.RIETX ?? fileURLToPath(new URL("../../../.venv/bin/rietx", import.meta.url));
const PORT = 8790 + Number(RUN) % 9;
const SPLIT = !!process.env.RIETX_PLOTLY;
const QUERY = { plotly: "", chart: SPLIT ? "" : "?chart=uplot" };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const load = () => os.loadavg().map((v) => v.toFixed(1)).join(" ");
const say = (line) => console.log(`[${ENGINE} ${DATASET.split("/").pop()} dpr${DPR} run${RUN}] ${line}`);

// ------------------------------------------------------------------ the page's own instruments
// Installed before any script of the app runs (gui/CLAUDE.md: instrument before the library loads).
function instruments() {
  // playwright's WebKit synthesises every mouse move with movementX and movementY
  // at 0, and uPlot drops a zero-movement move while dragging (a guard for a
  // Chrome-on-Windows phantom move), so no drag works there. A real mouse in
  // Safari reports the movement, so the probe supplies it from clientX/Y.
  if (/AppleWebKit/.test(navigator.userAgent) && !/Chrome/.test(navigator.userAgent)) {
    const moved = new WeakMap(), native = Object.getOwnPropertyDescriptor(MouseEvent.prototype, "movementX");
    const nativeY = Object.getOwnPropertyDescriptor(MouseEvent.prototype, "movementY");
    let lx = null, ly = null;
    window.addEventListener("mousemove", (e) => {
      if (lx !== null) moved.set(e, [e.clientX - lx, e.clientY - ly]);
      lx = e.clientX; ly = e.clientY;
    }, true);
    Object.defineProperty(MouseEvent.prototype, "movementX", { get() { return native.get.call(this) || (moved.get(this)?.[0] ?? 0); } });
    Object.defineProperty(MouseEvent.prototype, "movementY", { get() { return nativeY.get.call(this) || (moved.get(this)?.[1] ?? 0); } });
  }
  const raf = window.requestAnimationFrame.bind(window), now = () => performance.now();
  const W = (window.__w = { work: 0, depth: 0, frames: [], loaf: [], fetches: [], errors: [] });
  // frame intervals, from an untimed loop
  let last = now();
  const tick = (t) => { W.frames.push(t - last); last = t; raf(tick); };
  raf(tick);
  try {
    new PerformanceObserver((list) => {
      for (const e of list.getEntries()) {
        W.loaf.push({ at: e.startTime, dur: e.duration,
          scripts: (e.scripts ?? []).map((s) => ({ dur: Math.round(s.duration), url: (s.sourceURL || "").split("/").pop(),
                                                   fn: s.sourceFunctionName || "", invoker: s.invoker })) });
      }
    }).observe({ type: "long-animation-frame", buffered: true });
  } catch { /* not this engine */ }
  // every callback the page hands the platform, timed once at the outermost level
  const timed = (fn) => function (...a) {
    if (W.depth++) try { return fn.apply(this, a); } finally { W.depth--; }
    const t = now();
    try { return fn.apply(this, a); } finally { W.work += now() - t; W.depth--; }
  };
  const wrapped = new WeakMap();
  const add = EventTarget.prototype.addEventListener, remove = EventTarget.prototype.removeEventListener;
  EventTarget.prototype.addEventListener = function (type, fn, opts) {
    if (!fn) return add.call(this, type, fn, opts);
    let w = wrapped.get(fn);
    if (!w) { w = typeof fn === "function" ? timed(fn) : { handleEvent: timed((e) => fn.handleEvent(e)) }; wrapped.set(fn, w); }
    return add.call(this, type, w, opts);
  };
  EventTarget.prototype.removeEventListener = function (type, fn, opts) {
    return remove.call(this, type, (fn && wrapped.get(fn)) ?? fn, opts);
  };
  for (const name of ["setTimeout", "queueMicrotask", "requestAnimationFrame"]) {
    const orig = window[name].bind(window);
    window[name] = (fn, ...rest) => orig(typeof fn === "function" ? timed(fn) : fn, ...rest);
  }
  const RO = window.ResizeObserver;
  window.ResizeObserver = class extends RO { constructor(cb) { super(timed(cb)); } };
  // Promise continuations are the one entry this cannot reach; a fetch's are timed from their listener side
  const f = window.fetch.bind(window);
  window.fetch = (input, init) => { W.fetches.push({ at: now(), url: String(input) }); return f(input, init); };
}

// ------------------------------------------------------------------ server
// One server per build, started and fitted before the first renderer it serves.
const servers = {};
async function serve(renderer) {
  const key = SPLIT && renderer === "plotly" ? "plotly" : "chart";
  if (servers[key]) return servers[key];
  const port = PORT + (key === "plotly" ? 10 : 0), gui = `http://127.0.0.1:${port}`;
  const state = path.join(DIR, "state", `pilot-${ENGINE}-${RUN}-${key}`);
  execSync(`rm -rf "${state}"`);
  const bin = key === "plotly" ? process.env.RIETX_PLOTLY : RIETX;
  const srv = spawn(bin, ["gui", "--no-open", "--machine", "--port", String(port), "--state-dir", state],
                    { stdio: ["ignore", "pipe", "inherit"] });
  servers[key] = { srv };
  await new Promise((r) => srv.stdout.once("data", r));
  const api = async (p, body) => (await fetch(gui + p, body === undefined ? {} : {
    method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) })).json();
  if (DATASET === "nac") await api("/api/examples/open", { name: "nac" });
  else await api("/api/project/open", { path: path.resolve(DATASET) });
  const t = Date.now();
  await api("/api/run", { kind: "fit" });
  for (;;) { const s = await api("/api/run/state"); if (s.state !== "running") break; await sleep(500); }
  say(`${key} build fitted in ${((Date.now() - t) / 1000).toFixed(0)} s; load ${load()}`);
  return Object.assign(servers[key], { gui, api });
}
const engines = { chromium, firefox, webkit };
const browser = await engines[ENGINE].launch(ENGINE === "chromium" ? { executablePath: CFT, headless: true } : { headless: true });

try {
  for (const r of renderers) await measure(r);
} finally {
  await browser.close();
  for (const { srv } of Object.values(servers)) srv.kill();
}

// ------------------------------------------------------------------ one renderer
async function measure(renderer) {
  const { gui: GUI, api } = await serve(renderer);
  await api("/api/peaks", {});   // a fresh list: the last renderer's peak drags moved lines
  const peaks = (await (await fetch(GUI + "/api/peaks")).json()).peaks;
  const context = await browser.newContext({ viewport: { width: 1500, height: 1000 }, deviceScaleFactor: Number(DPR) });
  const page = await context.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.addInitScript(instruments);
  const cdp = ENGINE === "chromium" ? await context.newCDPSession(page) : null;
  if (cdp) await cdp.send("Performance.enable");
  const td = async () => (cdp ? (await cdp.send("Performance.getMetrics")).metrics.find((m) => m.name === "TaskDuration").value * 1000 : 0);
  const out = { renderer, load: load() };

  // -- 1. opening
  const nav = Date.now();
  await page.goto(GUI + "/" + QUERY[renderer]);
  const drawn = renderer === "plotly" ? ".js-plotly-plot .main-svg" : ".plot .u-over";
  await page.waitForSelector(drawn, { timeout: 120000 });
  await sleep(2500);
  out.boot = { shown_after_ms: null, loaf: await page.evaluate(() => window.__w.loaf.map((l) => ({
    dur: Math.round(l.dur), scripts: l.scripts.filter((s) => s.dur >= 5).map((s) => `${s.url}:${s.fn} ${s.dur}ms`) }))) };
  out.boot.chartFrames = out.boot.loaf.filter((l) => l.scripts.some((s) => /plotly|vendor-uplot|pattern\.js|rxplot\.js/.test(s)));
  say(`${renderer}: boot long frames ${JSON.stringify(out.boot.loaf)}`);

  // idle rate, for the subtraction
  let a = await td(), w = Date.now();
  await sleep(1500);
  const idle = cdp ? ((await td()) - a) / (Date.now() - w) : 0;

  const area = async () => (renderer === "plotly"
    ? page.locator(".js-plotly-plot .draglayer .xy .nsewdrag").first().boundingBox()
    : page.locator(".plot .u-over").first().boundingBox());
  let box = await area();
  const at = (fx, fy = 0.5) => [box.x + fx * box.width, box.y + fy * box.height];

  async function gesture(name, n, act) {
    await page.evaluate(() => { const W = window.__w; W.mark = { frames: W.frames.length, loaf: W.loaf.length, fetches: W.fetches.length, work: W.work }; });
    const t0 = await td(), w0 = Date.now();
    await act();
    await sleep(400);
    const wall = Date.now() - w0;
    const work = cdp ? ((await td()) - t0 - idle * wall) / n : null;
    const got = await page.evaluate(() => {
      const W = window.__w, m = W.mark, f = W.frames.slice(m.frames).sort((x, y) => x - y);
      return { wrapped: W.work - m.work, p95: f[Math.floor(0.95 * (f.length - 1))] ?? null, max: f.at(-1) ?? null,
               loaf: W.loaf.slice(m.loaf).map((l) => ({ dur: Math.round(l.dur), top: l.scripts.slice(0, 2).map((s) => `${s.url}:${s.fn} ${s.dur}ms`) })),
               fetches: W.fetches.slice(m.fetches).map((x) => x.url.replace(/\?.*/, "")) };
    });
    const row = { work, wrapped: got.wrapped / n, p95: got.p95, max: got.max, loaf: got.loaf, fetches: got.fetches };
    out[name] = row;
    say(`${renderer}: ${name.padEnd(12)} work ${work == null ? "—" : work.toFixed(2)} ms/event, wrapped ${row.wrapped.toFixed(2)}; `
        + `frame p95 ${row.p95?.toFixed(1)} max ${row.max?.toFixed(1)} ms; long frames ${JSON.stringify(row.loaf)}; fetches ${JSON.stringify(row.fetches)}`);
    return row;
  }
  const reset = async () => { await page.mouse.dblclick(...at(0.5)); await sleep(700); box = await area(); };

  // -- 2. gestures
  await gesture("hover", 120, async () => {
    for (let i = 0; i < 120; i++) { await page.mouse.move(...at(0.02 + 0.96 * i / 119)); await sleep(16); }
  });
  // the readout strip is the hover's whole answer (WP-1213): a number under the pointer
  out.readout = await page.locator(".readout .field").first().innerText();
  say(`${renderer}: the readout under the pointer reads ${JSON.stringify(out.readout)}`);
  await gesture("drag-zoom", 5 * 14, async () => {
    for (let k = 0; k < 5; k++) {
      await page.mouse.move(...at(0.2 + 0.1 * k, 0.5));
      await page.mouse.down();
      await page.mouse.move(...at(0.3 + 0.1 * k, 0.55), { steps: 12 });
      await page.mouse.up();
      await sleep(500);
      if (k < 4) { await reset(); }
    }
  });
  await reset();
  await gesture("exclude", 3 * 14, async () => {
    for (let k = 0; k < 3; k++) {
      await page.getByRole("button", { name: /exclude$/ }).click();
      await page.mouse.move(...at(0.55 + 0.1 * k, 0.5));
      await page.mouse.down();
      await page.mouse.move(...at(0.6 + 0.1 * k, 0.5), { steps: 12 });
      await page.mouse.up();
      await sleep(1200);
    }
  });
  // the three regions go again, outside any window
  for (let k = 0; k < 3; k++) { await page.getByRole("button", { name: /^stop excluding/ }).first().click(); await sleep(1200); }
  box = await area();

  if (renderer !== "plotly") {
    await gesture("wheel-zoom", 20, async () => {
      await page.mouse.move(...at(0.4));
      for (let i = 0; i < 20; i++) { await page.mouse.wheel(0, i < 10 ? -100 : 100); await sleep(16); }
    });
    // both pans start zoomed in, outside the window, so there is somewhere to pan to
    const zoomIn = async () => {
      await reset();
      await page.mouse.move(...at(0.4));
      for (let i = 0; i < 10; i++) { await page.mouse.wheel(0, -100); await sleep(16); }
      await sleep(300);
    };
    await zoomIn();
    await gesture("wheel-pan", 20, async () => {
      await page.keyboard.down("Shift");
      for (let i = 0; i < 20; i++) { await page.mouse.wheel(0, 100); await sleep(16); }
      await page.keyboard.up("Shift");
    });
    await zoomIn();
    await gesture("alt-pan", 14, async () => {
      await page.keyboard.down("Alt");
      await page.mouse.move(...at(0.5));
      await page.mouse.down();
      await page.mouse.move(...at(0.3), { steps: 12 });
      await page.mouse.up();
      await page.keyboard.up("Alt");
    });
    await reset();
  }

  // -- the peak drag, on the Peaks tab, zoomed so a marker is wider than a pixel
  await page.getByRole("button", { name: /^Peaks/ }).first().click();
  await sleep(1000);
  box = await area();
  const target = peaks[Math.floor(peaks.length / 2)];
  const pxOf = async (tt) => page.evaluate(([tt, plotly]) => {
    if (plotly) {
      const gd = document.querySelector(".js-plotly-plot"), xa = gd._fullLayout.xaxis;
      return gd.getBoundingClientRect().left + xa._offset + xa.d2p(tt);
    }
    return null;
  }, [tt, renderer === "plotly"]);
  const ringX = async () => {
    // hovering the table row puts the ring on the line (the hover link); its box is the line's place
    await page.locator("tr", { hasText: target.two_theta.toFixed(4) }).first().dispatchEvent("mouseenter");
    await sleep(200);
    const b = await page.locator(".plot .rx-ring").boundingBox();
    return b ? b.x + b.width / 2 : null;
  };
  const xNow = async () => (renderer === "plotly" ? pxOf(target.two_theta) : ringX());
  let x0 = await xNow();
  await page.mouse.move(x0 - 25, box.y + 0.5 * box.height);
  await page.mouse.down();
  await page.mouse.move(x0 + 25, box.y + 0.5 * box.height, { steps: 6 });
  await page.mouse.up();
  await sleep(800);
  x0 = await xNow();
  await gesture("peak-drag", 14, async () => {
    await page.mouse.move(x0, box.y + 0.6 * box.height);
    await page.mouse.down();
    await page.mouse.move(x0 + 40, box.y + 0.6 * box.height, { steps: 12 });
    await page.mouse.up();
    await sleep(1500);
  });
  const moved = (await (await fetch(GUI + "/api/peaks")).json()).peaks.some((p) => Math.abs(p.two_theta - target.two_theta) > 1e-6 && p.origin === "edited");
  say(`${renderer}: the drag moved a line: ${moved}`);
  out.peakMoved = moved;

  // -- 3. resizing: the app's work, and the chart library's own from a CPU profile
  const works = [], own = [], wrapped = [];
  if (cdp) {
    await cdp.send("Profiler.enable");
    await cdp.send("Profiler.setSamplingInterval", { interval: 100 });
  }
  for (let i = 0; i < 6; i++) {
    if (cdp) await cdp.send("Profiler.start");
    const t0 = await td(), w0 = Date.now(), c0 = await page.evaluate(() => window.__w.work);
    await page.setViewportSize({ width: i % 2 ? 1500 : 1300, height: 1000 });
    await sleep(500);
    works.push((await td()) - t0 - idle * (Date.now() - w0));
    wrapped.push((await page.evaluate(() => window.__w.work)) - c0);
    if (cdp) own.push(libraryTime((await cdp.send("Profiler.stop")).profile, renderer));
  }
  out.resize = { app: works, chart: own, wrapped };
  const list = (xs) => xs.map((v) => v.toFixed(1)).join(", ");
  say(`${renderer}: resize, the app's work ${list(works)} ms; the chart's own ${list(own)} ms; wrapped ${list(wrapped)} ms`);
  say(`${renderer}: page errors ${JSON.stringify(errors)}; load ${load()}`);
  await context.close();
  return out;
}

/**
 * The sampled time whose stack passes through the chart library's files: its
 * own code and everything it called, canvas drawing and the page's draw hooks
 * included. A sample's time is the gap to the next one.
 */
function libraryTime(profile, renderer) {
  const lib = renderer === "plotly" ? /plotly\.js/ : /vendor-uplot|pattern\.js|rxplot\.js/;
  const parent = new Map(), byId = new Map();
  for (const node of profile.nodes) {
    byId.set(node.id, node);
    for (const c of node.children ?? []) parent.set(c, node.id);
  }
  const inLib = new Map();
  const through = (id) => {
    if (inLib.has(id)) return inLib.get(id);
    const node = byId.get(id), p = parent.get(id);
    const hit = lib.test(node.callFrame.url ?? "") || (p !== undefined && through(p));
    inLib.set(id, hit);
    return hit;
  };
  let total = 0;
  for (let i = 0; i < profile.samples.length - 1; i++) {
    if (through(profile.samples[i])) total += profile.timeDeltas[i + 1] / 1000;
  }
  return total;
}

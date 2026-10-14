// Run every notebook of a built JupyterLite site in headless Chromium (WP-1963).
//
//   PW=<path to the playwright package> node docs/lite/smoke.mjs SITE_DIR [--pyodide DIR] [--only NAME]
//
// Serves SITE_DIR on 127.0.0.1, opens each notebook in the Notebook app, runs all
// cells and waits for the kernel to go idle with every cell executed.  It prints
// one line per notebook (wall clock, cells run, figures drawn) and every error
// or stderr output, and exits 1 if any notebook raised.
//
// --pyodide serves a local copy of Pyodide's full distribution (the
// pyodide-<version>.tar.bz2 release asset, unpacked) at /_pyodide/, for a machine
// that cannot reach cdn.jsdelivr.net, and points the kernel at it by rewriting
// the root jupyter-lite.json as it is served; the files on disk are untouched.
// Request interception cannot do this: the kernel imports Pyodide from a worker
// under JupyterLite's service worker, whose requests bypass Playwright's routes.
import { createRequire } from "node:module";
import fs from "node:fs";
import http from "node:http";
import path from "node:path";

const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PW || "playwright");

const args = process.argv.slice(2);
const site = path.resolve(args[0]);
const opt = (name) => (args.includes(name) ? args[args.indexOf(name) + 1] : null);
const pyodideDir = opt("--pyodide");
const only = opt("--only");

const TYPES = {
  ".html": "text/html", ".js": "text/javascript", ".mjs": "text/javascript",
  ".json": "application/json", ".css": "text/css", ".wasm": "application/wasm",
  ".svg": "image/svg+xml", ".png": "image/png", ".ico": "image/x-icon",
  ".woff2": "font/woff2", ".woff": "font/woff", ".ttf": "font/ttf",
  ".whl": "application/octet-stream", ".zip": "application/zip", ".ipynb": "application/json",
};

const KERNEL = "@jupyterlite/pyodide-kernel-extension:kernel";
let base = "";
const server = http.createServer((req, res) => {
  let rel = decodeURIComponent(new URL(req.url, "http://x").pathname);
  if (rel.endsWith("/")) rel += "index.html";
  const local = pyodideDir && rel.startsWith("/_pyodide/");
  const root = local ? path.resolve(pyodideDir) : site;
  const file = path.join(root, local ? rel.slice("/_pyodide/".length) : rel);
  if (!file.startsWith(root + path.sep) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) {
    res.writeHead(404).end();
    return;
  }
  res.writeHead(200, { "Content-Type": TYPES[path.extname(file)] || "application/octet-stream" });
  if (pyodideDir && rel === "/jupyter-lite.json") {
    const config = JSON.parse(fs.readFileSync(file, "utf8"));
    const settings = (config["jupyter-config-data"].litePluginSettings ??= {});
    (settings[KERNEL] ??= {}).pyodideUrl = `${base}/_pyodide/pyodide.mjs`;
    res.end(JSON.stringify(config));
    return;
  }
  fs.createReadStream(file).pipe(res);
});
await new Promise((ok) => server.listen(0, "127.0.0.1", ok));
base = `http://127.0.0.1:${server.address().port}`;

let books = fs.readdirSync(path.join(site, "files")).filter((f) => f.endsWith(".ipynb")).sort();
if (only) books = books.filter((b) => b.startsWith(only));

// The kernel installs `comm` (and rietx, unless the site serves it) from PyPI,
// and Chromium reads no proxy variable of its own accord.  Playwright proxies
// loopback too unless told not to, which would send this server's pages to it.
const proxy = process.env.HTTPS_PROXY || process.env.https_proxy;
if (proxy) process.env.PLAYWRIGHT_DISABLE_FORCED_CHROMIUM_PROXIED_LOOPBACK = "1";
const browser = await chromium.launch(proxy ? { proxy: { server: proxy, bypass: "<local>" } } : {});
const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });

let failed = false;
for (const book of books) {
  const page = await context.newPage();
  page.on("pageerror", (e) => console.log(`  [page error] ${e.message}`));
  if (process.env.DEBUG) {  // the page's and the kernel worker's consoles
    page.on("console", (m) => console.log(`  [console] ${m.text().slice(0, 300)}`));
    page.on("worker", (w) => w.on("console", (m) => console.log(`  [worker] ${m.text().slice(0, 300)}`)));
    page.on("response", (r) => r.status() >= 400 && console.log(`  [http ${r.status()}] ${r.url()}`));
  }
  const t0 = Date.now();
  await page.goto(`${base}/notebooks/index.html?path=${book}`);
  await page.waitForFunction(() => window.jupyterapp?.shell?.currentWidget?.sessionContext, null,
    { timeout: 120_000 });
  await page.evaluate(() => window.jupyterapp.shell.currentWidget.sessionContext.ready);
  const kernelReady = (Date.now() - t0) / 1000;
  const t1 = Date.now();
  await page.evaluate(() => window.jupyterapp.commands.execute("notebook:run-all-cells"));
  // Done when the kernel is idle and no code cell is still queued or running.
  await page.waitForFunction(() => {
    const panel = window.jupyterapp.shell.currentWidget;
    const status = panel.sessionContext.session?.kernel?.status;
    const cells = [...panel.content.widgets].filter((c) => c.model.type === "code");
    const pending = cells.some((c) => c.promptNode?.textContent?.includes("*"));
    return status === "idle" && !pending;
  }, null, { timeout: 1_800_000, polling: 1000 });
  const ran = (Date.now() - t1) / 1000;
  const report = await page.evaluate(() => {
    const panel = window.jupyterapp.shell.currentWidget;
    const out = { cells: 0, executed: 0, figures: 0, errors: [], stderr: [] };
    // A traceback's frames are ANSI-coloured; the last "File" line is where it raised.
    const plain = (s) => s.replace(/\u001b\[[0-9;]*m/g, "");
    for (const cell of panel.content.model.cells) {
      if (cell.type !== "code") continue;
      out.cells += 1;
      if (cell.executionCount) out.executed += 1;
      for (const o of cell.outputs.toJSON()) {
        if (o.output_type === "error") {
          const frames = (o.traceback || []).map(plain).join("\n").split("\n")
            .filter((l) => /^\s*File "|^\s*Cell In/.test(l));
          out.errors.push(`code cell ${out.cells}: ${o.ename}: ${o.evalue}`
            + (frames.length ? `\n      at ${frames[frames.length - 1].trim()}` : ""));
        }
        if (o.output_type === "stream" && o.name === "stderr") out.stderr.push([].concat(o.text).join(""));
        if (o.data && o.data["image/png"]) out.figures += 1;
      }
    }
    return out;
  });
  const ok = report.errors.length === 0 && report.executed === report.cells;
  failed ||= !ok;
  console.log(`${ok ? "ok  " : "FAIL"} ${book}: kernel ${kernelReady.toFixed(0)} s, cells ${ran.toFixed(0)} s,`
    + ` ${report.executed}/${report.cells} cells run, ${report.figures} figures`);
  for (const e of report.errors) console.log(`  [error] ${e}`);
  for (const s of report.stderr) console.log(`  [stderr] ${s.trim().slice(0, 600)}`);
  if (process.env.SHOTS) await page.screenshot({ path: path.join(process.env.SHOTS, `${book}.png`), fullPage: false });
  await page.close();
}
await browser.close();
server.close();
process.exit(failed ? 1 : 0);

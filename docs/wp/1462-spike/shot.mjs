// One screenshot of the prototype: node shot.mjs <engine> <query> <out.png>
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
}).listen(8824);
const [engine, query, out] = process.argv.slice(2);
const browser = await { chromium, firefox, webkit }[engine].launch({ headless: process.env.HEADED !== "1" });
const page = await browser.newPage({ deviceScaleFactor: Number(process.env.DPR || 2), viewport: { width: 700, height: 560 } });
await page.goto(`http://127.0.0.1:8824/index.html?${query}`);
await page.waitForFunction(() => window.ready === true);
await page.locator("#wrap").screenshot({ path: join(here, "shots", out) });
await browser.close();
server.close();

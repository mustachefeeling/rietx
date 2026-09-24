// Serve this directory on localhost for a person to try the demos: node serve.mjs [port]
// localhost is a secure context, which the clipboard exports need.
import http from "node:http";
import fs from "node:fs";
import path from "node:path";

const DIR = new URL(".", import.meta.url).pathname, PORT = +(process.argv[2] ?? 8810);
const TYPES = { ".html": "text/html; charset=utf-8", ".js": "text/javascript", ".mjs": "text/javascript", ".css": "text/css", ".png": "image/png", ".svg": "image/svg+xml" };
http.createServer((q, r) => {
  const rel = decodeURIComponent(q.url.split("?")[0]).replace(/^\/$/, "/index.html");
  const f = path.join(DIR, rel);
  if (!f.startsWith(DIR) || !fs.existsSync(f) || fs.statSync(f).isDirectory()) { r.writeHead(404); return r.end("not found"); }
  r.writeHead(200, { "content-type": TYPES[path.extname(f)] ?? "application/octet-stream" }); fs.createReadStream(f).pipe(r);
}).listen(PORT, "127.0.0.1", () => console.log(`http://127.0.0.1:${PORT}/`));

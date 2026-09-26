// The pilot's whole matrix, one pilot.mjs call at a time, each call's lines
// appended to results/pilot_<engine>_<dataset>_dpr<n>.txt. The renderers'
// order turns each run, so none is always measured first.
//
//   node pilot_matrix.mjs <lab6 .rex path> [filter]
//
// PILOT_PREFIX names the logs (`pilot` by default; task 14's acceptance run is
// `acceptance`). RIETX_PLOTLY reaches each call through the environment.
//
// `filter` keeps the rows whose name contains it ("chromium", "lab6", ...).
import { fileURLToPath } from "node:url";
import { spawn } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const DIR = fileURLToPath(new URL(".", import.meta.url));
const [LAB6, FILTER = ""] = process.argv.slice(2);
const PREFIX = process.env.PILOT_PREFIX ?? "pilot";
const ORDERS = [["plotly", "chart"], ["chart", "plotly"]];
const rows = [];
for (const [engine, dataset, dpr, runs] of [
  ["chromium", "nac", 1, 3], ["chromium", "nac", 2, 3], ["chromium", "lab6", 1, 3], ["chromium", "lab6", 2, 1],
  ["firefox", "nac", 1, 3], ["firefox", "lab6", 1, 1], ["webkit", "nac", 1, 3], ["webkit", "lab6", 1, 1],
]) {
  for (let run = 0; run < runs; run++) rows.push({ engine, dataset, dpr, run });
}
for (const r of rows) {
  const name = `${PREFIX}_${r.engine}_${r.dataset}_dpr${r.dpr}`;
  if (!name.includes(FILTER)) continue;
  const log = path.join(DIR, "results", `${name}.txt`);
  fs.appendFileSync(log, `\n# ${new Date().toISOString()} run ${r.run}, load ${os.loadavg().map((v) => v.toFixed(1)).join(" ")}\n`);
  const args = [path.join(DIR, "pilot.mjs"), r.engine, r.dataset === "nac" ? "nac" : LAB6, String(r.dpr), String(r.run),
                ...ORDERS[r.run % 2]];
  await new Promise((resolve) => {
    const child = spawn(process.execPath, args, { stdio: ["ignore", "pipe", "pipe"] });
    child.stdout.on("data", (d) => fs.appendFileSync(log, d));
    child.stderr.on("data", (d) => fs.appendFileSync(log, d));
    child.on("close", (code) => { fs.appendFileSync(log, `# exit ${code}\n`); resolve(); });
  });
  console.log(`${name} run ${r.run} done`);
}

"""Per-RB MANIFEST.tsv and README for the HRPD Mantid batch (2026-11-06), from the task summaries and rietx reads.

usage: python3 build_manifest.py <job dir>   (reads runs.json, calib_rows.json, out/focus/*.json, out/rietx/*.json;
       writes <RB folder>/mantid_focus_20261106/MANIFEST.tsv and README (README.md, or README_batch_20261106.md where
       a canary README.md is already there); prints a JSON summary per RB)
"""
import glob
import json
import os
import sys
from collections import defaultdict

job = sys.argv[1]
runs = json.load(open(f"{job}/runs.json"))
rows = json.load(open(f"{job}/calib_rows.json"))
focus, rietx = {}, {}
for f in glob.glob(f"{job}/out/focus/*.json"):
    s = json.load(open(f))
    for r in s["runs"]:
        r["_task"] = s["task"]
        r["_d_range"] = s["d_range_per_bank"]
        focus[r["path"]] = r
for f in glob.glob(f"{job}/out/rietx/*.json"):
    s = json.load(open(f))
    for r in s["runs"]:
        rietx[r["run"] + "|" + os.path.dirname(r["gss"])] = r
        rx_version = s["rietx_version"]

by_folder = defaultdict(list)
for r in runs:
    by_folder[r["folder"]].append(r)


def temps(t):
    parts = [f"{k} {v[0]:g}" for k, v in t.items() if v[0] != 0]
    return "; ".join(parts) if parts else ""


summary = {}
for folder, rr in sorted(by_folder.items()):
    out = folder + "/mantid_focus_20261106"
    os.makedirs(out, exist_ok=True)
    lines = ["\t".join(["run", "title", "T_logs_median", "window_ms", "calib_row", "confidence", "d_b1", "d_b2", "d_b3",
                        "status", "peaks_b1", "peaks_b2", "peaks_b3", "rietx_read", "note"])]
    counts = defaultdict(int)
    for r in sorted(rr, key=lambda x: x["path"]):
        lab = os.path.splitext(os.path.basename(r["path"]))[0].lower()
        f = focus.get(r["path"], {})
        x = rietx.get(lab + "|" + out, {})
        st = f.get("status", "not run")
        counts[st] += 1
        dr = [f"{b['d_range'][0]:.4f}-{b['d_range'][1]:.4f}" for b in f.get("banks", [])] or ["", "", ""]
        pk = [str(b.get("n_peaks", "")) for b in x.get("banks", [])] or ["", "", ""]
        ok = x.get("read_ok")
        counts["read_ok" if ok else "read_not_ok"] += 1
        note = f.get("error", "") or x.get("error", "") or x.get("note", "")
        gss = out + "/" + lab + ".gss"
        if os.path.exists(gss):
            npos, ntot, b = defaultdict(int), defaultdict(int), None
            for line in open(gss, encoding="latin1"):
                if line.startswith("BANK"):
                    b = int(line.split()[1])
                    continue
                p = line.split()
                if b is not None and len(p) == 3:
                    ntot[b] += 1
                    npos[b] += float(p[2]) > 0
            low = [f"bank {k}: {npos[k]}/{ntot[k]}" for k in sorted(ntot) if npos[k] < 0.95 * ntot[k]]
            if low:
                counts["runs_with_zero_sigma_points"] += 1
                note = (note + "; " if note else "") + ("points with sigma > 0 (rietx drops the rest; all zero = bank empty): "
                                                        + ", ".join(low))
        lines.append("\t".join([lab, r["title"].replace("\t", " "), temps(r["temps"]), r["window"], r["row"],
                                r["confidence"], *dr[:3], st, *pk[:3], "ok" if ok else "no", note.replace("\t", " ")]))
    open(out + "/MANIFEST.tsv", "w").write("\n".join(lines) + "\n")
    used = sorted({(r["row"], r["window"], r["confidence"], r["reason"]) for r in rr})
    readme = out + ("/README_batch_20261106.md" if os.path.exists(out + "/README.md") and
                    "canary" in open(out + "/README.md").read().lower() else "/README.md")
    rb = os.path.basename(folder)
    txt = [f"# {rb}: HRPD runs focused with Mantid 6.15.0 (batch of 2026-11-06)", "",
           "Focused with Mantid 6.15.0 run as a black box; no Mantid source was opened.", "",
           f"- {len(rr)} runs; focus status: " + ", ".join(f"{k} {v}" for k, v in sorted(counts.items())
                                                           if k in ("ok", "fail", "not run")),
           f"- rietx {rx_version} (~/rietx @ e09e601e) read every bank: {counts['read_ok']} runs read OK, "
           f"{counts['read_not_ok']} not (a failed focus has no .gss).",
           "- Files: per run `<run>.gss` (GSAS FXYE, TOF, 3 banks, written by SaveGSS RALF with MultiplyByBinWidth) and "
           "`<run>_log.json` (every Mantid call, the V calls shared by its task, inputs, crop, d ranges); `MANIFEST.tsv`.",
           "- Recipe: `dev/mantid/batch/focus_hrpd_batch.py` in mustachefeeling/rietx (the single-run recipe "
           "`dev/mantid/focus_hrpd.py` with a per-bank crop, the V processed once per task, and a cross-cycle "
           "V-empty rebinned onto the V's bins).",
           "- Crop: each bank keeps the longest contiguous d range where the 51-bin running median of the focused V exceeds "
           "10 % of its bank median.",
           "- Banks: 1 (168°) and 2 (90°) are the usable ones; bank 3 (30°) is low value (see dev/mantid/README.md).",
           "- The headers carry geometric DIFC only. The facility's Si calibration (DIFC/DIFA/ZERO) is not applied; peak "
           "positions in d are about +0.1 % off a Si cell in banks 1 and 2 until one is (see dev/mantid/README.md).",
           "- `T_logs_median` is the median of each TEMPn channel in the run's own text log, units and sensor as logged.",
           "", "## Calibration rows used", "",
           "| Row | Window (ms) | V | V-empty | Confidence | Why |", "|---|---|---|---|---|---|"]
    for row, win, conf, why in used:
        R = rows[row]
        txt.append(f"| {row} | {win} | {R['van']} ({R['van_start'][:10]}) | {R['vempty']} ({R['vempty_start'][:10]}) | "
                   f"{conf} | {why} |")
    txt += ["", "Recipe, pitfalls and provenance: `dev/mantid/README.md` in mustachefeeling/rietx. The `.cal` is the facility's "
            "`hrpd_new_072_01_corr.cal` (in the CC BY 4.0 LaTaO4 thesis dataset); the IDF is "
            "`HRPD_Definition_pre20210301.xml`.", ""]
    open(readme, "w").write("\n".join(txt))
    summary[rb] = dict(runs=len(rr), **counts, readme=readme)
print(json.dumps(summary, indent=1))

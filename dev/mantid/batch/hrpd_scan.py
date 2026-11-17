"""Header scan of every HRPD raw run (stage 1 of BRIEF_hrpd_mantid_batch_20261106.md).

Mantid 6.15.0 is run as a black box: LoadRaw of one detector spectrum gives the title, start time, proton charge
and the TOF axis of the run (the window is taken from the axis, never from the title). Temperatures come from the
run's own text logs (<run>.log, or <run>_TEMPn.txt), parsed here in plain Python. No Mantid source was opened.

usage: python hrpd_scan.py <list of raw paths, one per line> <out.jsonl> [--full N]
  --full N: also load the whole of the first N runs of each RB (spectrum count and detector-id range)
"""
import json
import os
import re
import sys
import time

import numpy as np
from mantid import config
from mantid.simpleapi import DeleteWorkspace, LoadRaw, mtd

config["default.facility"] = "ISIS"
config["default.instrument"] = "HRPD"
config["MultiThreaded.MaxCores"] = "1"

paths = [p.strip() for p in open(sys.argv[1]) if p.strip()]
out = sys.argv[2]
nfull = int(sys.argv[sys.argv.index("--full") + 1]) if "--full" in sys.argv else 0
done = set()
if os.path.exists(out):
    for line in open(out):
        done.add(json.loads(line)["path"])
fh = open(out, "a")
full_seen = {}


def temps(path):
    d = os.path.dirname(path)
    stem = os.path.splitext(os.path.basename(path))[0]
    vals = {}
    combined = os.path.join(d, stem + ".log")
    if os.path.exists(combined):
        for line in open(combined, errors="replace"):
            p = line.split("\t")
            if len(p) >= 3 and re.match(r"^TEMP\d$", p[1].strip()):
                try:
                    vals.setdefault(p[1].strip(), []).append(float(p[2]))
                except ValueError:
                    pass
    else:
        for f in os.listdir(d):
            m = re.match(re.escape(stem) + r"_(TEMP\d)\.txt$", f, re.I)
            if m:
                for line in open(os.path.join(d, f), errors="replace"):
                    p = line.split()
                    if len(p) >= 2:
                        try:
                            vals.setdefault(m.group(1).upper(), []).append(float(p[-1]))
                        except ValueError:
                            pass
    return {k: [round(float(np.median(v)), 2), round(float(np.min(v)), 2), round(float(np.max(v)), 2), len(v)]
            for k, v in sorted(vals.items()) if v}


for path in paths:
    if path in done:
        continue
    rb = path.split("/")[-2]
    rec = {"path": path, "rb_dir": rb}
    t0 = time.time()
    try:
        LoadRaw(Filename=path, OutputWorkspace="h", SpectrumMin=100, SpectrumMax=100, LoadMonitors="Exclude",
                LoadLogFiles=False)
        ws = mtd["h"]
        r = ws.getRun()
        x = ws.readX(0)
        rec.update(title=ws.getTitle().strip(),
                   run_start=r.getProperty("run_start").value if r.hasProperty("run_start") else None,
                   run_end=r.getProperty("run_end").value if r.hasProperty("run_end") else None,
                   uAh=round(float(r.getProtonCharge()), 3), tof_min=float(x[0]), tof_max=float(x[-1]),
                   nbins=len(x) - 1, dt_t_med=float(np.median(np.diff(x) / x[:-1])))
        DeleteWorkspace("h")
        if full_seen.get(rb, 0) < nfull:
            LoadRaw(Filename=path, OutputWorkspace="f", LoadMonitors="Separate", LoadLogFiles=False)
            wf = mtd["f"]
            ids = [wf.getSpectrum(i).getDetectorIDs() for i in range(wf.getNumberHistograms())]
            flat = [d for s in ids for d in s]
            rec.update(nspec=wf.getNumberHistograms(), ndet=len(flat), det_min=int(min(flat)), det_max=int(max(flat)))
            full_seen[rb] = full_seen.get(rb, 0) + 1
            for w in list(mtd.getObjectNames()):
                DeleteWorkspace(w)
        rec["temps"] = temps(path)
        rec["status"] = "ok"
    except Exception as e:  # noqa: BLE001 - the error text goes in the record
        rec["status"] = "error"
        rec["error"] = str(e)[:300]
    rec["scan_s"] = round(time.time() - t0, 3)
    fh.write(json.dumps(rec) + "\n")
    fh.flush()
print("scanned", len(paths), "->", out)

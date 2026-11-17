"""rietx read check of every .gss one focus task wrote (stage 3 of BRIEF_hrpd_mantid_batch_20261106.md).

For each run of the task: rietx.read_pattern(path, bank=n) for banks 1-3; the axis must be TOF (two_theta None), every
sigma > 0, and the read diagnostics are recorded. A peak count per bank comes from rietx.pick_peaks on a pseudo-2θ axis
(λ = min(1 Å, 1.95 d_min), d = TOF / DIFC from the file header), as in the canary's read_check.py. A failure to read is a result, not an
exception: it is counted.

usage: python read_batch.py <spec.json> <out.json>
"""
import json
import math
import os
import re
import sys
import time

import numpy as np
import rietx as rx

spec = json.load(open(sys.argv[1]))
out = sys.argv[2]
res = {"task": spec["task"], "rietx_version": rx.__version__, "rietx_file": rx.__file__, "runs": []}
t_task = time.time()
for path in spec["samples"]:
    label = os.path.splitext(os.path.basename(path))[0].lower()
    gss = os.path.join(spec["out"], label + ".gss")
    row = {"run": label, "gss": gss, "read_ok": False, "banks": []}
    t0 = time.time()
    if not os.path.exists(gss):
        row["note"] = "no .gss (focus failed; see the run's _log.json)"
        res["runs"].append(row)
        continue
    try:
        geo, cur = {}, None
        for line in open(gss, encoding="latin1"):
            m = re.search(r"Total flight path ([0-9.]+)m, tth ([0-9.]+)deg, DIFC ([0-9.]+)", line)
            if m:
                cur = tuple(float(v) for v in m.groups())
            if line.startswith("BANK"):
                geo[int(line.split()[1])] = cur
        ok = True
        for b in sorted(geo):
            diags = []
            rb = {"bank": b, "difc_header": geo[b][2]}
            row["banks"].append(rb)
            try:
                p = rx.read_pattern(gss, bank=b, diagnostics=diags)
            except Exception as e:  # noqa: BLE001 - a refused bank is a read failure, counted
                rb.update(axis_tof=False, n=0, n_sigma_le0=None, read_diagnostics=[], read_error=repr(e)[:300])
                ok = False
                continue
            tof = np.asarray(p.tof, float) if p.tof is not None else None
            y = np.asarray(p.intensity, float)
            s = np.asarray(p.sigma, float)
            difc = geo[b][2]
            rb.update(axis_tof=tof is not None and p.two_theta is None, n=int(len(y)), n_sigma_le0=int((s <= 0).sum()),
                      read_diagnostics=[d.code for d in diags])
            ok = ok and rb["axis_tof"] and rb["n"] > 0
            if tof is None:
                continue
            rb["d_range"] = [round(float(tof[0] / difc), 4), round(float(tof[-1] / difc), 4)]
            # peak count on a pseudo-2θ axis; the fictitious wavelength keeps 2θ below about 160° at the bank's d_min
            try:
                keep = s > 0
                d = tof[keep] / difc
                lam = min(1.0, 1.95 * float(d.min()))
                tt = np.degrees(2 * np.arcsin(lam / (2 * d)))
                o = np.argsort(tt)
                data = rx.PatternData(two_theta=tt[o].tolist(), intensity=y[keep][o].tolist(), sigma=s[keep][o].tolist())
                pl = rx.pick_peaks(data, rx.Instrument.debye_scherrer(lam))
                pos = [float(getattr(pk, "two_theta", getattr(pk, "position", np.nan))) for pk in getattr(pl, "peaks", pl)]
                rb["n_peaks"] = len(pos)
                rb["pseudo_lambda"] = lam
                rb["peak_d_top"] = sorted(round(lam / (2 * math.sin(math.radians(x / 2))), 4) for x in pos
                                          if np.isfinite(x))[::-1][:60]
            except Exception as e:  # noqa: BLE001 - the peak count is a side product; its failure is recorded
                rb["pick_peaks_error"] = repr(e)[:200]
        row["read_ok"] = bool(ok) and len(geo) == 3
    except Exception as e:  # noqa: BLE001 - a read failure is counted
        row["error"] = repr(e)[:300]
    row["wall_s"] = round(time.time() - t0, 2)
    res["runs"].append(row)
res["wall_s"] = round(time.time() - t_task, 2)
os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
json.dump(res, open(out, "w"), indent=1)
print("read", sum(r["read_ok"] for r in res["runs"]), "/", len(res["runs"]), "ok;", res["rietx_version"])

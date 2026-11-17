"""Mantid arm of the per-era HRPD Si calibration: PDCalibration, run as a black box, on a focused Si run.

Written 2026-11-06 for BRIEF_hrpd_si_calibration_20261106.md. The algorithm and its properties are taken from Mantid's
user documentation only (docs.mantidproject.org, PDCalibration v1, 6.15 page) and the run-time property list. No Mantid
source was opened.

Input: the focused Si TOF workspace kept by focus_si.py (<label>_tof.nxs, SaveNexusProcessed of the exact workspace
SaveGSS wrote to <label>.gss), so the calibration is fitted to the batch's own focused data and focused geometry.

Per bank (one PDCalibration call per bank, StartWorkspaceIndex = StopWorkspaceIndex = bank - 1):
  * TofBinning = [first edge, -dt/t of the bank, last edge], i.e. the bank's own logarithmic binning;
  * PeakPositions = the allowed Si reflections (diamond, Fd-3m: h,k,l all odd, or all even with h+k+l = 4n) at the
    certified cell `a_cert`, inside the bank's d range, one entry per distinct d;
  * PeakWindow = 2N boundaries, asymmetric (left 4 FWHM, right 8 FWHM for the moderator tail), each clipped at 0.45 of the
    gap to the neighbouring reflection; reflections whose clipped window is under 2 FWHM left or 3 FWHM right are left out;
  * CalibrationParameters = 'DIFC+TZERO+DIFA', UseChiSq = True (weights 1/sigma^2 of the fitted centres, and the
    _fiterror diagnostic is produced);
  * with PeakFunction 'Gaussian' and 'BackToBackExponential'. For the latter, when the spec gives "b2b_fixed", A and B
    are declared FIXED per bank at the GSAS type-3 laws alpha = alp/d and beta = bet0 + bet1/d^4, and S is started at
    sqrt(sig1 d^2 + sig2 d^4). These are loaded as instrument fitting
    parameters (LoadParameterFile, ParameterXML; syntax from the Instrument Definition File concept page, "Using fitting
    <parameter>") on the bank components, and whether 6.15 holds them fixed is read back from _fitparam (6.15 has no RespectFixedPeakParameters property;
    the 7.0 page adds it).
    The laws used are the facility's own 2018 file (Cyc_182_mantid3.hrpd, PRCF set 1), so the Mantid arm takes no
    input from our own peak fits. MEASURED (dev run 2026-11-06 ~18:00Z): Mantid 6.15.0 PDCalibration does NOT hold
    them fixed - the fitted A/B leave the law by factors 0.3-30 on many peaks - so they act as starting values only.
Every call and its arguments, the output calibration rows for the bank's spectrum, and every diagnostic workspace's
values for that spectrum are written to <out>/<task>_pdcal.json.

usage: python pdcal_si.py <spec.json>
spec: {"task", "nxs", "a_cert", "out", "maxcores", "fwhm_rel": [b1, b2, b3], "functions": [...],
       "min_peak_height": 0.0, "max_chisq": 100}
"""
import json
import os
import sys
import time

import numpy as np
from mantid import config
from mantid.simpleapi import ConvertUnits, LoadNexusProcessed, LoadParameterFile, PDCalibration, mtd
import mantid
os.environ["TZ"] = "UTC"; time.tzset()  # every time written is UTC

spec = json.load(open(sys.argv[1]))
config["MultiThreaded.MaxCores"] = str(spec.get("maxcores", 4))
os.makedirs(spec["out"], exist_ok=True)
t0 = time.time()
A = float(spec["a_cert"])
FW = [float(x) for x in spec.get("fwhm_rel", [1.0e-3, 2.5e-3, 8.0e-3])]
out = {"task": spec["task"], "spec": spec, "mantid_version": mantid.__version__,
       "config_maxcores": config["MultiThreaded.MaxCores"],
       "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "calls": [], "banks": []}


def si_reflections(dmin, dmax):
    """Distinct d of the allowed Si reflections (diamond structure) in [dmin, dmax], with their N = h^2+k^2+l^2."""
    seen = {}
    nmax = int((A / dmin) ** 2) + 1
    r = int(np.sqrt(nmax)) + 1
    for h in range(0, r + 1):
        for k in range(0, h + 1):
            for l in range(0, k + 1):
                n = h * h + k * k + l * l
                if n == 0 or n > nmax:
                    continue
                odd = h % 2 == 1 and k % 2 == 1 and l % 2 == 1
                even = h % 2 == 0 and k % 2 == 0 and l % 2 == 0 and (h + k + l) % 4 == 0
                if not (odd or even):
                    continue
                d = A / np.sqrt(n)
                if dmin <= d <= dmax:
                    seen.setdefault(n, []).append((h, k, l))
    return sorted(((A / np.sqrt(n), n, v) for n, v in seen.items()), reverse=False)


def table_rows(ws):
    names = ws.getColumnNames()
    return [{c: (ws.cell(c, i) if not isinstance(ws.cell(c, i), (np.generic,)) else ws.cell(c, i).item())
             for c in names} for i in range(ws.rowCount())]


def ws_dump(ws, index):
    """Values of one spectrum (matrix) or the rows (table) of a diagnostic workspace."""
    kind = ws.id()
    if "Table" in kind:
        rows = table_rows(ws)
        if rows and "detid" in rows[0]:
            rows = rows[:1]  # one row per detector ID, all of one focused spectrum: identical, keep one
        return {"kind": kind, "columns": ws.getColumnNames(), "rows": [{k: (float(v) if isinstance(v, (int, float)) else str(v))
                                                                         for k, v in r.items()} for r in rows]}
    if hasattr(ws, "getNumberHistograms"):
        i = index if ws.getNumberHistograms() > index else 0
        return {"kind": kind, "nspec": ws.getNumberHistograms(), "index_used": i,
                "x": [float(v) for v in ws.readX(i)], "y": [float(v) for v in ws.readY(i)],
                "e": [float(v) for v in ws.readE(i)]}
    return {"kind": kind}


LoadNexusProcessed(Filename=spec["nxs"], OutputWorkspace="si")
out["calls"].append({"alg": "LoadNexusProcessed", "Filename": spec["nxs"], "OutputWorkspace": "si"})
BANK_COMPONENT = ["bank_bsk", "bank_90degnew", "bank_la"]
if spec.get("b2b_fixed"):
    parts = ['<?xml version="1.0" encoding="UTF-8" ?>',
             '<parameter-file instrument="HRPD" valid-from="1900-01-31 23:59:59">']
    for b, comp in enumerate(BANK_COMPONENT):
        q = spec["b2b_fixed"][str(b + 1)]
        parts += [f'<component-link name="{comp}">',
                  f'<parameter name="BackToBackExponential:A" type="fitting"><formula eq="{q["alp"]}/centre" unit="dSpacing"/><fixed/></parameter>',
                  f'<parameter name="BackToBackExponential:B" type="fitting"><formula eq="{q["bet0"]}+{q["bet1"]}/centre^4" unit="dSpacing"/><fixed/></parameter>',
                  f'<parameter name="BackToBackExponential:S" type="fitting"><formula eq="sqrt({q["sig1"]}*centre^2+{q["sig2"]}*centre^4)" unit="dSpacing"/></parameter>',
                  '</component-link>']
    parts.append('</parameter-file>')
    xml = "\n".join(parts)
    LoadParameterFile(Workspace="si", ParameterXML=xml)
    out["calls"].append({"alg": "LoadParameterFile", "Workspace": "si", "ParameterXML": xml})
ConvertUnits(InputWorkspace="si", OutputWorkspace="si_d", Target="dSpacing")
si, sid = mtd["si"], mtd["si_d"]
for i in range(si.getNumberHistograms()):
    x = np.asarray(si.readX(i), float)
    xd = np.asarray(sid.readX(i), float)
    dtt = float(np.median(x[1:] / x[:-1]) - 1.0)
    dmin, dmax = float(xd[0]), float(xd[-1])
    difc_geom = float(np.median(x / xd))
    refl = si_reflections(dmin * 1.004, dmax / 1.004)
    ds = [r[0] for r in refl]
    pos, win, kept = [], [], []
    fw = FW[i]
    for j, (d, n, hkls) in enumerate(refl):
        gap_lo = d - ds[j - 1] if j > 0 else d - dmin
        gap_hi = ds[j + 1] - d if j + 1 < len(ds) else dmax - d
        wl = min(4 * fw * d, 0.45 * gap_lo)
        wr = min(8 * fw * d, 0.45 * gap_hi)
        if wl < 2 * fw * d or wr < 3 * fw * d:
            continue
        pos.append(float(d))
        win += [float(d - wl), float(d + wr)]
        kept.append({"d": float(d), "N": int(n), "hkl": [list(h) for h in hkls]})
    bank = {"bank": i + 1, "dtt": dtt, "tof_edges": [float(x[0]), float(x[-1])], "d_range": [dmin, dmax],
            "difc_geom": difc_geom, "n_reflections_in_range": len(refl), "peaks": kept, "runs": []}
    for label in spec.get("functions", ["Gaussian", "BackToBackExponential"]):
        func = "BackToBackExponential" if label.startswith("BackToBack") else label
        tag = f"{spec['task']}_b{i + 1}_{label}"
        kw = dict(InputWorkspace="si", StartWorkspaceIndex=i, StopWorkspaceIndex=i,
                  TofBinning=[float(x[0]), -dtt, float(x[-1])], PeakFunction=func, BackgroundType="Linear",
                  PeakPositions=pos, PeakWindow=win, PeakWidthPercent=fw,
                  MinimumPeakHeight=float(spec.get("min_peak_height", 0.0)), MaxChiSq=float(spec.get("max_chisq", 100)),
                  CalibrationParameters="DIFC+TZERO+DIFA", UseChiSq=True,
                  OutputCalibrationTable=tag + "_cal", DiagnosticWorkspaces=tag + "_diag")
        run = {"function": label, "call": {"alg": "PDCalibration", **{k: v for k, v in kw.items()
                                                                      if k not in ("PeakPositions", "PeakWindow")},
                                          "n_peaks": len(pos)}}
        t1 = time.time()
        try:
            PDCalibration(**kw)
            cal = table_rows(mtd[tag + "_cal"])
            run["cal_rows_n"] = len(cal)
            # the focused spectrum carries many detector IDs; keep the distinct (difc, difa, tzero) rows
            uniq = {}
            for r in cal:
                key = tuple(round(float(r.get(c, 0.0)), 6) for c in ("difc", "difa", "tzero"))
                uniq.setdefault(key, {**{k: (float(v) if isinstance(v, (int, float)) else str(v)) for k, v in r.items()},
                                      "n_detids": 0})
                uniq[key]["n_detids"] += 1
            run["cal_distinct"] = list(uniq.values())
            run["cal_columns"] = mtd[tag + "_cal"].getColumnNames()
            diag = mtd[tag + "_diag"]
            run["diagnostics"] = {}
            for k in range(diag.getNumberOfEntries()):
                w = diag.getItem(k)
                run["diagnostics"][w.name().replace(tag + "_diag", "").replace(tag, "")] = ws_dump(w, i)
            run["status"] = "ok"
        except Exception as e:  # noqa: BLE001 - recorded, the next function/bank carries on
            run["status"] = "fail"
            run["error"] = repr(e)[:800]
        run["wall_s"] = round(time.time() - t1, 2)
        bank["runs"].append(run)
        print(json.dumps({"bank": i + 1, "function": label, "status": run["status"],
                          "cal": run.get("cal_distinct", [None])[:1], "error": run.get("error")}), flush=True)
    out["banks"].append(bank)

out["wall_s"] = round(time.time() - t0, 2)
with open(os.path.join(spec["out"], spec["task"] + "_pdcal.json"), "w") as fh:
    json.dump(out, fh, indent=1, default=str)
print("pdcal", spec["task"], "done in", out["wall_s"], "s")

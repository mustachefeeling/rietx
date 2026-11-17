"""Focus a group of ISIS HRPD .raw runs (one RB, one TOF window, one calibration row) with Mantid, run as a black box.

Written 2026-11-06 for BRIEF_hrpd_mantid_batch_20261106.md. It is the canary recipe (hrpd_mantid_canary_20261106/
focus_hrpd.py) turned into a batch task:
  * the vanadium (V minus V-empty, cylinder absorption, focus, StripVanadiumPeaks, SmoothData) is processed once per task,
    and every sample run of the task is divided by it;
  * per-bank crop: each bank keeps the longest contiguous d range where the focused vanadium (51-bin running median)
    exceeds CROP_FRAC of the bank median (0.10 chosen 2026-11-06: 0.30 cut the V's own smooth Maxwellian decline well
    inside the frame, e.g. 30-130 ms bank 1 at 113 ms and 10-210 ms bank 1 at 149 ms, while 0.10 stops at the sharp
    coverage edges and reproduces the facility's own 2018 30-130 ms bank 1-2 TOF ranges to about 1 ms; the contiguity
    rule drops the frame-edge spikes at 100-101 ms and 208-212 ms); the canary used first/last bin above 2 %;
  * if the V-empty comes from another cycle, it is put on the vanadium's TOF bins with RebinToWorkspace before Minus;
  * Mantid's thread pool is capped (MultiThreaded.MaxCores) to the task's declared cpus;
  * one .gss (SaveGSS RALF/FXYE, MultiplyByBinWidth) and one <label>_log.json (every call) per run; a run that fails is
    logged with its error and the task carries on.
Algorithms are from docs.mantidproject.org and the run-time property lists only. No Mantid source was opened.

usage: python focus_hrpd_batch.py <spec.json>
spec: {"task": id, "rb": .., "row": calibration-row id, "window": "30-130", "van": path, "vempty": path, "vrad_cm": 0.3,
       "vheight_cm": 2.0, "cal": path, "idf": path, "out": dir, "samples": [paths], "maxcores": 4,
       "crop_frac": 0.10, "dtt": [0.0003, 0.0007, 0.0012], "smooth": 51, "summary": path}
"""
import json
import os
import sys
import time
import traceback

import numpy as np
from mantid import config
from mantid.simpleapi import (AlignAndFocusPowder, CloneWorkspace, ConvertUnits, CylinderAbsorption, DeleteWorkspace,
                              Divide, ExtractSingleSpectrum, LoadInstrument, LoadRaw, Minus, NormaliseByCurrent,
                              RebinToWorkspace, SaveFocusedXYE, SaveGSS, SmoothData, StripVanadiumPeaks, mtd)
import mantid
os.environ["TZ"] = "UTC"; time.tzset()  # every time written is UTC

spec = json.load(open(sys.argv[1]))
config["default.facility"] = "ISIS"
config["default.instrument"] = "HRPD"
config["MultiThreaded.MaxCores"] = str(spec.get("maxcores", 4))
CROP = float(spec.get("crop_frac", 0.10))
dtt = [float(x) for x in spec.get("dtt", [0.0003, 0.0007, 0.0012])]
SMOOTH = int(spec.get("smooth", 51))
os.makedirs(spec["out"], exist_ok=True)
t_task = time.time()
shared_calls = []
summary = {"task": spec["task"], "rb": spec["rb"], "row": spec["row"], "window": spec["window"],
           "mantid_version": mantid.__version__, "config_maxcores": config["MultiThreaded.MaxCores"],
           "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "runs": []}


def clean(v):
    return v if isinstance(v, (int, float, str, list, bool, type(None))) else str(v)


def rec(calls, name, **kw):
    calls.append({"alg": name, **{k: clean(v) for k, v in kw.items()}})


def load(path, name, calls):
    LoadRaw(Filename=path, OutputWorkspace=name, LoadMonitors="Exclude", LoadLogFiles=False)
    rec(calls, "LoadRaw", Filename=path, OutputWorkspace=name, LoadMonitors="Exclude", LoadLogFiles=False)
    LoadInstrument(Workspace=name, Filename=spec["idf"], RewriteSpectraMap=False)
    rec(calls, "LoadInstrument", Workspace=name, Filename=spec["idf"], RewriteSpectraMap=False)
    NormaliseByCurrent(InputWorkspace=name, OutputWorkspace=name)
    rec(calls, "NormaliseByCurrent", InputWorkspace=name, OutputWorkspace=name)
    ws = mtd[name]
    r = ws.getRun()
    return {"file": os.path.basename(path), "title": ws.getTitle().strip(),
            "run_start": r.getProperty("run_start").value if r.hasProperty("run_start") else None,
            "proton_charge_uAh": float(r.getProtonCharge()), "nspec": ws.getNumberHistograms(),
            "tof_range": [float(ws.readX(0)[0]), float(ws.readX(0)[-1])]}


def running_median(y, n):
    h = n // 2
    yp = np.pad(y, h, mode="edge")
    return np.array([np.median(yp[i:i + n]) for i in range(len(y))])


# ---- vanadium, once per task
inputs = {}
inputs["van"] = load(spec["van"], "van", shared_calls)
inputs["vem"] = load(spec["vempty"], "vem", shared_calls)
xv, xe = mtd["van"].readX(0), mtd["vem"].readX(0)
if len(xv) != len(xe) or not np.allclose(xv, xe):
    RebinToWorkspace(WorkspaceToRebin="vem", WorkspaceToMatch="van", OutputWorkspace="vem", PreserveEvents=False)
    rec(shared_calls, "RebinToWorkspace", WorkspaceToRebin="vem", WorkspaceToMatch="van", OutputWorkspace="vem")
Minus(LHSWorkspace="van", RHSWorkspace="vem", OutputWorkspace="van")
rec(shared_calls, "Minus", LHSWorkspace="van", RHSWorkspace="vem", OutputWorkspace="van")
ConvertUnits(InputWorkspace="van", OutputWorkspace="van", Target="Wavelength")
rec(shared_calls, "ConvertUnits", InputWorkspace="van", OutputWorkspace="van", Target="Wavelength")
absp = dict(AttenuationXSection=5.1, ScatteringXSection=5.08, SampleNumberDensity=0.072,
            CylinderSampleHeight=float(spec.get("vheight_cm", 2.0)), CylinderSampleRadius=float(spec.get("vrad_cm", 0.3)),
            NumberOfSlices=10, NumberOfAnnuli=10, NumberOfWavelengthPoints=100, ExpMethod="Normal")
CylinderAbsorption(InputWorkspace="van", OutputWorkspace="vabs", **absp)
rec(shared_calls, "CylinderAbsorption", InputWorkspace="van", OutputWorkspace="vabs", **absp)
Divide(LHSWorkspace="van", RHSWorkspace="vabs", OutputWorkspace="van")
rec(shared_calls, "Divide", LHSWorkspace="van", RHSWorkspace="vabs", OutputWorkspace="van")
ConvertUnits(InputWorkspace="van", OutputWorkspace="van", Target="TOF")
rec(shared_calls, "ConvertUnits", InputWorkspace="van", OutputWorkspace="van", Target="TOF")
DeleteWorkspace("vabs")
DeleteWorkspace("vem")

# pass 1: the covered d range of each bank (CROP_FRAC of the bank median, running median of 51 bins, contiguous)
p1 = dict(Dspacing=True, DMin=[0.2] * 3, DMax=[25.0] * 3, DeltaRagged=[-x for x in dtt], CalFileName=spec["cal"])
AlignAndFocusPowder(InputWorkspace="van", OutputWorkspace="v_p1", **p1)
rec(shared_calls, "AlignAndFocusPowder", InputWorkspace="van", OutputWorkspace="v_p1", **p1)
ConvertUnits(InputWorkspace="v_p1", OutputWorkspace="v_p1", Target="dSpacing")
rec(shared_calls, "ConvertUnits", InputWorkspace="v_p1", OutputWorkspace="v_p1", Target="dSpacing")
v1 = mtd["v_p1"]
dmin, dmax = [], []
for i in range(v1.getNumberHistograms()):
    x = v1.readX(i)
    y = np.asarray(v1.readY(i), float)
    xc = 0.5 * (x[1:] + x[:-1])
    ys = running_median(y, 51)
    med = np.median(ys[ys > 0])
    good = ys > CROP * med
    # longest contiguous run of good bins
    best, cur, start, bs = 0, 0, 0, 0
    for j, g in enumerate(good):
        if g:
            if cur == 0:
                start = j
            cur += 1
            if cur > best:
                best, bs = cur, start
        else:
            cur = 0
    dmin.append(float(xc[bs] * 1.002))
    dmax.append(float(xc[bs + best - 1] / 1.002))
if spec.get("dump_v_p1"):  # diagnostic only: the pass-1 focused vanadium, to choose the crop
    SaveFocusedXYE(InputWorkspace="v_p1", Filename=spec["dump_v_p1"], SplitFiles=True, IncludeHeader=True)
d_range = [[round(a, 5), round(b, 5)] for a, b in zip(dmin, dmax)]
summary["d_range_per_bank"] = d_range
summary["crop_rule"] = f"contiguous d range where the 51-bin running median of the focused V exceeds {CROP} x its bank median"
DeleteWorkspace("v_p1")

p2 = dict(Dspacing=True, DMin=dmin, DMax=dmax, DeltaRagged=[-x for x in dtt], CalFileName=spec["cal"])
AlignAndFocusPowder(InputWorkspace="van", OutputWorkspace="van_f", **p2)
rec(shared_calls, "AlignAndFocusPowder", InputWorkspace="van", OutputWorkspace="van_f", **p2)
ConvertUnits(InputWorkspace="van_f", OutputWorkspace="van_f", Target="dSpacing")
rec(shared_calls, "ConvertUnits", InputWorkspace="van_f", OutputWorkspace="van_f", Target="dSpacing")
CloneWorkspace(InputWorkspace="van_f", OutputWorkspace="van_s")
for i in range(mtd["van_f"].getNumberHistograms()):
    ExtractSingleSpectrum(InputWorkspace="van_f", OutputWorkspace="vb", WorkspaceIndex=i)
    StripVanadiumPeaks(InputWorkspace="vb", OutputWorkspace="vb")
    SmoothData(InputWorkspace="vb", OutputWorkspace="vb", NPoints=[SMOOTH])
    mtd["van_s"].dataY(i)[:] = mtd["vb"].readY(0)
    mtd["van_s"].dataE(i)[:] = mtd["vb"].readE(0)
rec(shared_calls, "per bank: ExtractSingleSpectrum -> StripVanadiumPeaks -> SmoothData, copied into CloneWorkspace(van_f)",
    NPoints=[SMOOTH], StripVanadiumPeaks="defaults (FWHM=7, Tolerance=4, BackgroundType=Linear)")
for w in ("van", "van_f", "vb"):
    DeleteWorkspace(w)
summary["vanadium_s"] = round(time.time() - t_task, 2)
summary["inputs"] = inputs

# ---- samples
for path in spec["samples"]:
    t0 = time.time()
    label = os.path.splitext(os.path.basename(path))[0].lower()
    stem = os.path.join(spec["out"], label)
    calls = []
    log = {"task": spec["task"], "rb": spec["rb"], "calibration_row": spec["row"], "window": spec["window"],
           "spec": {k: v for k, v in spec.items() if k != "samples"}, "mantid_version": mantid.__version__,
           "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "vanadium_calls_shared_by_task": shared_calls, "vanadium_inputs": inputs, "d_range_per_bank": d_range,
           "crop_rule": summary["crop_rule"], "calls": calls}
    row = {"run": label, "path": path, "status": "fail"}
    try:
        log["sample"] = load(path, "sam", calls)
        row.update(title=log["sample"]["title"], run_start=log["sample"]["run_start"],
                   uAh=log["sample"]["proton_charge_uAh"], tof_range=log["sample"]["tof_range"])
        if log["sample"]["proton_charge_uAh"] <= 0:
            raise RuntimeError("proton charge is 0: nothing to normalise")
        AlignAndFocusPowder(InputWorkspace="sam", OutputWorkspace="sam_f", **p2)
        rec(calls, "AlignAndFocusPowder", InputWorkspace="sam", OutputWorkspace="sam_f", **p2)
        ConvertUnits(InputWorkspace="sam_f", OutputWorkspace="sam_f", Target="dSpacing")
        rec(calls, "ConvertUnits", InputWorkspace="sam_f", OutputWorkspace="sam_f", Target="dSpacing")
        Divide(LHSWorkspace="sam_f", RHSWorkspace="van_s", OutputWorkspace="res_d")
        rec(calls, "Divide", LHSWorkspace="sam_f", RHSWorkspace="van_s", OutputWorkspace="res_d")
        res = mtd["res_d"]
        nbad = 0
        for i in range(res.getNumberHistograms()):
            y = res.dataY(i)
            e = res.dataE(i)
            bad = ~np.isfinite(y) | ~np.isfinite(e)
            nbad += int(bad.sum())
            y[bad] = 0.0
            e[bad] = 0.0
        log["nonfinite_bins_zeroed"] = nbad
        ConvertUnits(InputWorkspace="res_d", OutputWorkspace="res_tof", Target="TOF")
        rec(calls, "ConvertUnits", InputWorkspace="res_d", OutputWorkspace="res_tof", Target="TOF")
        if os.path.exists(stem + ".gss"):
            os.remove(stem + ".gss")
        gss = dict(Filename=stem + ".gss", SplitFiles=False, Append=False, Bank=1, Format="RALF", DataFormat="FXYE",
                   MultiplyByBinWidth=True)
        SaveGSS(InputWorkspace="res_tof", **gss)
        rec(calls, "SaveGSS", InputWorkspace="res_tof", **gss)
        rt = mtd["res_tof"]
        si = rt.spectrumInfo()
        banks = []
        for i in range(rt.getNumberHistograms()):
            xt = rt.readX(i)
            xd = res.readX(i)
            banks.append({"bank": i + 1, "nbins": len(xt) - 1, "tof_range": [float(xt[0]), float(xt[-1])],
                          "d_range": [float(xd[0]), float(xd[-1])], "difc_eff": float(np.median(xt / xd)),
                          "l2": float(si.l2(i)), "tth_deg": float(np.degrees(si.twoTheta(i)))})
        log["banks"] = banks
        row.update(status="ok", nonfinite_zeroed=nbad, banks=[{k: b[k] for k in ("bank", "nbins", "d_range")} for b in banks])
    except Exception as e:  # noqa: BLE001 - logged and reported; the task carries on with the next run
        log["error"] = repr(e)[:600]
        log["traceback_tail"] = traceback.format_exc()[-1200:]
        row["error"] = repr(e)[:300]
    for w in ("sam", "sam_f", "res_d", "res_tof"):
        if mtd.doesExist(w):
            DeleteWorkspace(w)
    log["status"] = row["status"]
    log["wall_s"] = round(time.time() - t0, 3)
    row["wall_s"] = log["wall_s"]
    with open(stem + "_log.json", "w") as fh:
        json.dump(log, fh, indent=1)
    summary["runs"].append(row)
    print(json.dumps({k: row.get(k) for k in ("run", "status", "wall_s", "error")}), flush=True)

summary["wall_s"] = round(time.time() - t_task, 2)
with open(spec["summary"], "w") as fh:
    json.dump(summary, fh, indent=1)
print("task", spec["task"], "done:", sum(r["status"] == "ok" for r in summary["runs"]), "/", len(summary["runs"]), "ok")

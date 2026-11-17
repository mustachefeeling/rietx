"""Focus one ISIS HRPD .raw run to its three banks with Mantid, run as a black box.

Written 2026-11-06 for the HRPD Mantid canary.
Algorithms were chosen from Mantid's user documentation (docs.mantidproject.org) only; no Mantid
source was opened. Every Mantid call and parameter is in this file and is echoed to <out>/<label>_log.json.

Recipe
  sample, vanadium, vanadium-empty (and optionally a sample-empty) are each:
    LoadRaw(LoadMonitors=Exclude) -> LoadInstrument(IDF given, RewriteSpectraMap=False) -> NormaliseByCurrent
  vanadium: Minus(V, V-empty) -> ConvertUnits(Wavelength) -> CylinderAbsorption(V rod) -> Divide -> ConvertUnits(TOF)
  grouping: --cal  -> AlignAndFocusPowder(CalFileName=<.cal>)   (offsets + mask + grouping from the file)
            no cal -> CreateGroupingWorkspace(GroupNames=bank_bsk,bank_90degnew,bank_la), IDF geometry DIFC
  pass 1  : AlignAndFocusPowder of the vanadium over a wide d range, to find each bank's covered d range
            (first/last bin with vanadium counts > 2 % of the bank median)
  pass 2  : AlignAndFocusPowder(Dspacing=True, DMin/DMax per bank, DeltaRagged = -dt/t per bank) of V and sample
            (it returns TOF; ConvertUnits(dSpacing) follows)
  vanadium: StripVanadiumPeaks -> SmoothData(NPoints)
  sample / smoothed V -> ConvertUnits(TOF) -> SaveGSS(RALF, FXYE, MultiplyByBinWidth) and SaveFocusedXYE (TOF and d)
"""
import argparse
import json
import os
import time

import numpy as np
from mantid import config
from mantid.simpleapi import (AlignAndFocusPowder, ConvertUnits, CloneWorkspace, CreateGroupingWorkspace, CylinderAbsorption,
                              Divide, ExtractSingleSpectrum, LoadInstrument, LoadRaw, Minus, NormaliseByCurrent, SaveFocusedXYE, SaveGSS,
                              SmoothData, StripVanadiumPeaks, mtd)
os.environ["TZ"] = "UTC"; time.tzset()  # every time written is UTC

ap = argparse.ArgumentParser()
ap.add_argument("--sample", required=True)
ap.add_argument("--van", required=True)
ap.add_argument("--vempty", required=True)
ap.add_argument("--sempty", default=None, help="optional sample-environment empty, subtracted from the sample")
ap.add_argument("--cal", default=None, help="optional facility .cal (offsets, select, group)")
ap.add_argument("--idf", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--label", required=True)
ap.add_argument("--dtt", default="0.0003,0.0007,0.0012", help="log bin dt/t per bank (the facility pref's values)")
ap.add_argument("--vrad", type=float, default=0.3, help="V rod radius, cm (facility pref VRadius)")
ap.add_argument("--vheight", type=float, default=2.0, help="V rod height, cm (facility pref VHeight)")
ap.add_argument("--smooth", type=int, default=51)
args = ap.parse_args()

config["default.facility"] = "ISIS"
config["default.instrument"] = "HRPD"
os.makedirs(args.out, exist_ok=True)
log = {"args": vars(args), "calls": [], "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
t0 = time.time()


def rec(name, **kw):
    log["calls"].append({"alg": name, **{k: (v if isinstance(v, (int, float, str, list, bool, type(None))) else str(v))
                                          for k, v in kw.items()}})


def load(path, name):
    LoadRaw(Filename=path, OutputWorkspace=name, LoadMonitors="Exclude", LoadLogFiles=False)
    rec("LoadRaw", Filename=path, OutputWorkspace=name, LoadMonitors="Exclude", LoadLogFiles=False)
    ws = mtd[name]
    auto = {"valid_from": str(ws.getInstrument().getValidFromDate()),
            "l2_0": ws.spectrumInfo().l2(0), "tth_0": float(np.degrees(ws.spectrumInfo().twoTheta(0)))}
    LoadInstrument(Workspace=name, Filename=args.idf, RewriteSpectraMap=False)
    rec("LoadInstrument", Workspace=name, Filename=args.idf, RewriteSpectraMap=False)
    ws = mtd[name]
    after = {"valid_from": str(ws.getInstrument().getValidFromDate()),
             "l2_0": ws.spectrumInfo().l2(0), "tth_0": float(np.degrees(ws.spectrumInfo().twoTheta(0)))}
    NormaliseByCurrent(InputWorkspace=name, OutputWorkspace=name)
    rec("NormaliseByCurrent", InputWorkspace=name, OutputWorkspace=name)
    r = ws.getRun()
    info = {"file": os.path.basename(path), "title": ws.getTitle().strip(),
            "run_start": r.getProperty("run_start").value if r.hasProperty("run_start") else None,
            "proton_charge_uAh": float(r.getProtonCharge()), "nspec": ws.getNumberHistograms(),
            "tof_range": [float(ws.readX(0)[0]), float(ws.readX(0)[-1])],
            "idf_auto": auto, "idf_loaded": after}
    log.setdefault("inputs", {})[name] = info
    return name


sam = load(args.sample, "sam")
van = load(args.van, "van")
vem = load(args.vempty, "vem")
if args.sempty:
    sem = load(args.sempty, "sem")
    Minus(LHSWorkspace=sam, RHSWorkspace=sem, OutputWorkspace=sam)
    rec("Minus", LHSWorkspace=sam, RHSWorkspace=sem, OutputWorkspace=sam)

# vanadium: subtract its empty, then the rod's absorption (cylinder, the facility pref's dimensions)
Minus(LHSWorkspace=van, RHSWorkspace=vem, OutputWorkspace=van)
rec("Minus", LHSWorkspace=van, RHSWorkspace=vem, OutputWorkspace=van)
ConvertUnits(InputWorkspace=van, OutputWorkspace=van, Target="Wavelength")
absp = dict(AttenuationXSection=5.1, ScatteringXSection=5.08, SampleNumberDensity=0.072,
            CylinderSampleHeight=args.vheight, CylinderSampleRadius=args.vrad,
            NumberOfSlices=10, NumberOfAnnuli=10, NumberOfWavelengthPoints=100, ExpMethod="Normal")
CylinderAbsorption(InputWorkspace=van, OutputWorkspace="vabs", **absp)
rec("CylinderAbsorption", InputWorkspace=van, OutputWorkspace="vabs", **absp)
Divide(LHSWorkspace=van, RHSWorkspace="vabs", OutputWorkspace=van)
rec("Divide", LHSWorkspace=van, RHSWorkspace="vabs", OutputWorkspace=van)
ConvertUnits(InputWorkspace=van, OutputWorkspace=van, Target="TOF")

group_kw = {}
if args.cal:
    group_kw["CalFileName"] = args.cal
else:
    CreateGroupingWorkspace(InputWorkspace=sam, GroupNames="bank_bsk,bank_90degnew,bank_la", OutputWorkspace="grp")
    rec("CreateGroupingWorkspace", InputWorkspace=sam, GroupNames="bank_bsk,bank_90degnew,bank_la",
        OutputWorkspace="grp")
    group_kw["GroupingWorkspace"] = "grp"
dtt = [float(x) for x in args.dtt.split(",")]

# pass 1: where does each bank have vanadium counts?
p1 = dict(Dspacing=True, DMin=[0.2] * 3, DMax=[20.0] * 3, DeltaRagged=[-x for x in dtt], **group_kw)
AlignAndFocusPowder(InputWorkspace=van, OutputWorkspace="v_p1", **p1)
rec("AlignAndFocusPowder", InputWorkspace=van, OutputWorkspace="v_p1", **p1)
log["aafp_output_unit"] = mtd["v_p1"].getAxis(0).getUnit().unitID()
ConvertUnits(InputWorkspace="v_p1", OutputWorkspace="v_p1", Target="dSpacing")  # AlignAndFocusPowder returns TOF
v1 = mtd["v_p1"]
dmin, dmax = [], []
for i in range(v1.getNumberHistograms()):
    x = v1.readX(i)
    y = v1.readY(i)
    xc = 0.5 * (x[1:] + x[:-1])
    ok = np.where(y > 0.02 * np.median(y[y > 0]))[0]
    dmin.append(float(xc[ok[0]] * 1.002))
    dmax.append(float(xc[ok[-1]] / 1.002))
log["d_range_per_bank"] = list(zip(dmin, dmax))

p2 = dict(Dspacing=True, DMin=dmin, DMax=dmax, DeltaRagged=[-x for x in dtt], **group_kw)
for w in (van, sam):
    AlignAndFocusPowder(InputWorkspace=w, OutputWorkspace=w + "_f", **p2)
    rec("AlignAndFocusPowder", InputWorkspace=w, OutputWorkspace=w + "_f", **p2)
    ConvertUnits(InputWorkspace=w + "_f", OutputWorkspace=w + "_f", Target="dSpacing")
    rec("ConvertUnits", InputWorkspace=w + "_f", OutputWorkspace=w + "_f", Target="dSpacing")
# StripVanadiumPeaks refuses a ragged workspace (and ConjoinWorkspaces refuses unequal bins), so each bank is
# stripped and smoothed on its own and its Y/E copied back into a clone of the ragged focused vanadium
CloneWorkspace(InputWorkspace="van_f", OutputWorkspace="van_s")
for i in range(mtd["van_f"].getNumberHistograms()):
    ExtractSingleSpectrum(InputWorkspace="van_f", OutputWorkspace="vb", WorkspaceIndex=i)
    StripVanadiumPeaks(InputWorkspace="vb", OutputWorkspace="vb")
    SmoothData(InputWorkspace="vb", OutputWorkspace="vb", NPoints=[args.smooth])
    mtd["van_s"].dataY(i)[:] = mtd["vb"].readY(0)
    mtd["van_s"].dataE(i)[:] = mtd["vb"].readE(0)
rec("per bank: ExtractSingleSpectrum -> StripVanadiumPeaks -> SmoothData, copied into CloneWorkspace(van_f)",
    NPoints=[args.smooth], StripVanadiumPeaks="defaults (FWHM=7, Tolerance=4, BackgroundType=Linear)")
Divide(LHSWorkspace="sam_f", RHSWorkspace="van_s", OutputWorkspace="res_d")
rec("Divide", LHSWorkspace="sam_f", RHSWorkspace="van_s", OutputWorkspace="res_d")
# a bin where the smoothed vanadium is zero gives inf/nan: zero it
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
rec("ConvertUnits", InputWorkspace="res_d", OutputWorkspace="res_tof", Target="TOF")

stem = os.path.join(args.out, args.label)
for f in (stem + ".gss",):
    if os.path.exists(f):
        os.remove(f)
gss = dict(Filename=stem + ".gss", SplitFiles=False, Append=False, Bank=1, Format="RALF", DataFormat="FXYE",
           MultiplyByBinWidth=True)
SaveGSS(InputWorkspace="res_tof", **gss)
rec("SaveGSS", InputWorkspace="res_tof", **gss)
SaveFocusedXYE(InputWorkspace="res_tof", Filename=stem + "_tof.xye", SplitFiles=True, IncludeHeader=True)
rec("SaveFocusedXYE", InputWorkspace="res_tof", Filename=stem + "_tof.xye", SplitFiles=True)
SaveFocusedXYE(InputWorkspace="res_d", Filename=stem + "_d.xye", SplitFiles=True, IncludeHeader=True)
rec("SaveFocusedXYE", InputWorkspace="res_d", Filename=stem + "_d.xye", SplitFiles=True)

# effective DIFC of each focused spectrum, as ConvertUnits applied it (TOF / d, bin centre by bin centre)
banks = []
rt = mtd["res_tof"]
si = rt.spectrumInfo()
for i in range(rt.getNumberHistograms()):
    xt = rt.readX(i)
    xd = res.readX(i)
    ratio = xt / xd
    banks.append({"bank": i + 1, "nbins": len(xt) - 1, "tof_range": [float(xt[0]), float(xt[-1])],
                  "d_range": [float(xd[0]), float(xd[-1])],
                  "difc_eff": float(np.median(ratio)), "difc_eff_spread": float(np.ptp(ratio)),
                  "l1": float(si.l1()), "l2": float(si.l2(i)), "tth_deg": float(np.degrees(si.twoTheta(i)))})
log["banks"] = banks
log["wall_s"] = time.time() - t0
import mantid
log["mantid_version"] = mantid.__version__
with open(stem + "_log.json", "w") as fh:
    json.dump(log, fh, indent=1)
print(json.dumps({"banks": banks, "d_range": log["d_range_per_bank"], "wall_s": log["wall_s"],
                  "inputs": log["inputs"]}, indent=1))

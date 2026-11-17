"""Build the calibration rows, the per-task specs and tasks.jsonl for the HRPD Mantid batch (2026-11-06).

Inputs: the stage-1 header scan (scan/scan.jsonl, Mantid LoadRaw of one spectrum per run + the run's text logs).
Every run is assigned to one calibration row by (RB, TOF window from the data axis). Rows and confidences are the ones
argued in HRPD_CALIBRATION_CHOICE_20261106.md.
usage: python3 make_tasks.py <scan.jsonl> <outdir>   (writes <outdir>/specs/*.json, tasks.jsonl, calib_rows.json, runs.json)
"""
import json
import os
import sys
from collections import defaultdict

H = os.path.expanduser("~")  # run on the workstation: every path below is a path there
JOB = H + "/wsjobs/hrpd_focus_1106"
CAL = H + ("/data/public_tests/howieson2023_latao4_standrews/thesis_dataset/Diffraction_Data/Powder_Neutron_Diffraction/"
           "LaTaO4_Oct18/hrpd_new_072_01_corr.cal")
IDF = H + "/data/public_tests/_instruments/mantid_hrpd_20261106/HRPD_Definition_pre20210301.xml"
CHUNK = 60

recs = [json.loads(l) for l in open(sys.argv[1])]
outdir = sys.argv[2]
P = {r["path"].split("/")[-1].upper().split(".")[0]: r for r in recs}

ROWS = {
    "R08-10": dict(van="HRP39191", vempty="HRP39187", vrad_cm=0.4, window="10-110"),
    "R08-30": dict(van="HRP39192", vempty="HRP39186", vrad_cm=0.4, window="30-130"),
    "R08-100": dict(van="HRP39193", vempty="HRP39188", vrad_cm=0.4, window="100-200"),
    "R08-10210": dict(van="HRP39322", vempty="HRP39323", vrad_cm=0.4, window="10-210"),
    "R13-10": dict(van="HRP58470", vempty="HRP70709", vrad_cm=0.3, window="10-110"),
    "R13-30": dict(van="HRP58472", vempty="HRP70710", vrad_cm=0.3, window="30-130"),
    "R18-30": dict(van="HRP70713", vempty="HRP70710", vrad_cm=0.3, window="30-130"),
    "R18-100": dict(van="HRP70714", vempty="HRP70711", vrad_cm=0.3, window="100-200"),
}
for k, v in ROWS.items():
    for f in ("van", "vempty"):
        r = P[v[f]]
        v[f + "_path"] = r["path"]
        v[f + "_title"] = r["title"]
        v[f + "_start"] = r["run_start"]
        assert f"{r['tof_min'] / 1e3:.0f}-{r['tof_max'] / 1e3:.0f}" == v["window"], (k, f, r["tof_min"], r["tof_max"])

# (RB, window) -> (row, confidence, reason)
ASSIGN = {
    ("720381", "10-110"): ("R08-10", "good", "in-RB V, V-empty and NBS Si; .cal checked on the RB's own Si"),
    ("720381", "30-130"): ("R08-30", "good", "in-RB V, V-empty and NBS Si; .cal checked on the RB's own Si"),
    ("720381", "100-200"): ("R08-100", "good", "in-RB V and V-empty; .cal checked on the RB's own Si (other windows)"),
    ("720381", "10-210"): ("R08-10210", "good", "in-RB 8 mm V rod and empty tank in this window; .cal checked on the RB's Si"),
    ("720381", "30-50"): ("R08-30", "poor", "quiet count (no sample); no V in the 30-50 ms window, the 30-130 ms V is used"),
    ("920183", "30-130"): ("R08-30", "provisional", "V and V-empty from RB720381, 388 days earlier; .cal checked on 2008 Si"),
    ("1120110", "30-130"): ("R13-30", "provisional", "V from RB1320048 (+1.7 yr), V-empty borrowed from 2018 (+6.2 yr)"),
    ("1120110", "100-200"): ("R08-100", "poor", "V and V-empty from RB720381, 3.7 years earlier"),
    ("1320048", "10-110"): ("R13-10", "provisional", "in-RB V/Nb and SRM640c Si; no in-RB V-empty (2018 empty, +4.5 yr)"),
    ("1320048", "30-130"): ("R13-30", "provisional", "in-RB V/Nb; Si checked in 10-110; no in-RB V-empty (2018 empty, +4.5 yr)"),
    ("1410098", "30-130"): ("R13-30", "provisional", "V from RB1320048 (242 days earlier), V-empty borrowed from 2018"),
    ("1620319", "30-130"): ("R18-30", "provisional", "V and V-empty from cycle 18/1, 1.6 years later"),
    ("1620319", "100-200"): ("R18-100", "provisional", "V and V-empty from cycle 18/1, 1.6 years later"),
    ("1820307", "30-130"): ("R18-30", "good", "canary-validated against the facility's own focus; V 130 days earlier"),
    ("1900046", "30-130"): ("R18-30", "good", "V 116 days earlier; same .cal epoch as the canary"),
    ("1900046", "100-200"): ("R18-100", "good", "V 116 days earlier; same .cal epoch as the canary"),
    ("1910341", "100-200"): ("R18-100", "provisional", "V from 18/1 (0.8-1.3 yr earlier); .cal checked only bank 1 vs bank 2"),
    ("1990160", "30-130"): ("R18-30", "provisional", "V from 18/1 (1.3 yr earlier); .cal checked only bank 1 vs bank 2"),
    ("2000133", "30-130"): ("R18-30", "provisional", "V from 18/1 (1.7 yr earlier); .cal checked only bank 1 vs bank 2"),
    ("2000133", "100-200"): ("R18-100", "provisional", "V from 18/1 (1.7 yr earlier); .cal checked only bank 1 vs bank 2"),
}

runs = []
groups = defaultdict(list)
for r in recs:
    if "/isis_hrpd_calibration/" in r["path"]:
        continue
    win = f"{r['tof_min'] / 1e3:.0f}-{r['tof_max'] / 1e3:.0f}"
    rb = r["rb_dir"]
    row, conf, why = ASSIGN[(rb, win)]
    folder = os.path.dirname(os.path.dirname(r["path"]))
    if rb == "1820307":
        folder = H + "/data/public_tests/howieson2023_latao4_standrews"
    out = folder + "/mantid_focus_20261106"
    runs.append(dict(path=r["path"], rb=rb, folder=folder, out=out, window=win, row=row, confidence=conf, reason=why,
                     title=r["title"], run_start=r["run_start"], uAh=r["uAh"], temps=r.get("temps", {})))
    groups[(folder, row)].append(r["path"])

os.makedirs(outdir + "/specs", exist_ok=True)
tasks = []
for (folder, row), paths in sorted(groups.items()):
    paths.sort()
    rb = os.path.basename(folder)
    for i in range(0, len(paths), CHUNK):
        chunk = paths[i:i + CHUNK]
        tid = f"{rb}_{row}_{i // CHUNK:02d}"
        R = ROWS[row]
        spec = dict(task=tid, rb=rb, row=row, window=R["window"], van=R["van_path"], vempty=R["vempty_path"],
                    vrad_cm=R["vrad_cm"], vheight_cm=2.0, cal=CAL, idf=IDF, out=folder + "/mantid_focus_20261106",
                    samples=chunk, maxcores=4, crop_frac=0.10, dtt=[0.0003, 0.0007, 0.0012], smooth=51,
                    summary=f"{JOB}/out/focus/{tid}.json")
        json.dump(spec, open(f"{outdir}/specs/{tid}.json", "w"), indent=1)
        cmd = (f"$HOME/opt/micromamba/bin/micromamba run -n mantid python focus_hrpd_batch.py specs/{tid}.json; rc=$?; "
               f"$HOME/venvs/rietx-py312/bin/python read_batch.py specs/{tid}.json out/rietx/{tid}.json; exit $rc")
        tasks.append(dict(id=tid, cmd=cmd, cwd=JOB, env={"MAMBA_ROOT_PREFIX": H + "/opt/micromamba/root"},
                          threads=4, cpus=4, mem_gb=(4.0 if row == "R08-10210" else 3.0), est_s=int(10 + 3 * len(chunk)), timeout_s=1800))
with open(outdir + "/tasks.jsonl", "w") as fh:
    for t in tasks:
        fh.write(json.dumps(t) + "\n")
json.dump(ROWS, open(outdir + "/calib_rows.json", "w"), indent=1)
json.dump(runs, open(outdir + "/runs.json", "w"), indent=1)
print(len(runs), "runs,", len(tasks), "tasks")
for t in tasks:
    print(" ", t["id"], len(json.load(open(f"{outdir}/specs/{t['id']}.json"))["samples"]))

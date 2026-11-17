"""Tabulate and compare the two arms of the HRPD Si calibration (written 2026-11-06, BRIEF_hrpd_si_calibration_20261106).

Reads <root>/mantid_pdcal/*_pdcal.json (Mantid 6.15.0 PDCalibration, black box) and <root>/own_fit/*_ownfit.json (our own
clean-room peak fits) and writes <out>/calibration_table.json and <out>/calibration_table.tsv, plus figures.

Curve comparisons: two calibrations are compared through the TOF they predict over the d span the Si peaks cover
(first to last peak used by the own b2b_fac fit; the facility comparison is also made over the batch's 30-130 ms d range),
dT/T(d) = (T_a(d) - T_b(d)) / T_b(d), which is the Delta d/d of a peak converted with one instead of the other (sign: a
positive value means calibration a gives a SMALLER d for the same TOF). sigma(dT) at each d comes from each
calibration's covariance (J C J^T with J = [d, d^2, 1]); z = max |dT| / sigma over the grid.

Mantid arm uncertainties: PDCalibration 6.15 returns no uncertainty. sigma is from our own weighted LSQ of Mantid's
fitted peak centres (_fitparam) and their errors (_fiterror), with the same constants as PDCalibration returned
(it returns the lowest reduced chi^2 of DIFC / DIFC+TZERO / DIFC+TZERO+DIFA, documented), the covariance scaled by
the reduced chi^2 when > 1. Peaks with error <= 0, non-finite, > 1e3 us or chi2 >= MaxChiSq are left out, as PDCalibration
itself leaves them out of its own fit (checked: the 3-parameter LSQ reproduces PDCalibration's constants when it
returns three).

usage: python analyse_calibration.py <root> <out>
"""
import json
import os
import sys
from glob import glob

import numpy as np

FAC = {1: (48275.36, 3.75, 8.00), 2: (34816.50, -1.17, -6.13), 3: (12760.76, 13.61, 8.00)}  # Cyc_182_mantid3.hrpd ICONS
D_30_130 = {1: (0.654, 2.614), 2: (0.875, 3.935), 3: (2.47, 10.73)}  # the batch's 30-130 ms crop (d, A)
META = {"si08_10": ("2008", "10-110", "HRP39182", "NBS Si (SRM not named) -> 640e assumed"),
        "si08_30": ("2008", "30-130", "HRP39183", "NBS Si (SRM not named) -> 640e assumed"),
        "si13_10": ("2013", "10-110", "HRP58469", "SRM 640c"),
        "si18_10": ("2018", "10-110", "HRP70715", "SRM 640e"),
        "si18a_10": ("2018 (April, pre HT repair)", "10-110", "HRP69935", "SRM 640e")}


def tof(c, d):
    return c[0] * d + c[1] * d * d + c[2]


def sig_tof(cov, d):
    J = np.vstack([d, d * d, np.ones_like(d)]).T
    return np.sqrt(np.einsum("ij,jk,ik->i", J, np.asarray(cov), J))


def compare(ca, cova, cb, covb, dgrid):
    ta, tb = tof(ca, dgrid), tof(cb, dgrid)
    s = np.sqrt(sig_tof(cova, dgrid) ** 2 + sig_tof(covb, dgrid) ** 2)
    rel = (ta - tb) / tb
    z = np.abs(ta - tb) / s
    return {"rel_ppm_grid": [round(float(x) * 1e6, 1) for x in rel], "max_abs_rel_ppm": round(float(np.max(np.abs(rel)) * 1e6), 1),
            "max_z": round(float(np.max(z)), 2), "sigma_rel_ppm_grid": [round(float(x) * 1e6, 1) for x in s / tb]}


def lsq(d, t, e, model):
    cols = {"DIFC": [0], "DIFC+TZERO": [0, 2], "DIFC+TZERO+DIFA": [0, 1, 2]}[model]
    M = np.vstack([d, d * d, np.ones_like(d)]).T[:, cols]
    W = 1 / e ** 2
    cov0 = np.linalg.inv(M.T @ (M * W[:, None]))
    p = cov0 @ (M.T @ (W * t))
    res = t - M @ p
    chi2r = float(np.sum(W * res ** 2) / max(len(t) - len(cols), 1))
    cov = np.zeros((3, 3))
    full = np.zeros(3)
    for i, ci in enumerate(cols):
        full[ci] = p[i]
        for j, cj in enumerate(cols):
            cov[ci, cj] = cov0[i, j] * max(chi2r, 1.0)
    return full, cov, chi2r, res


def mantid_arm(pd, bank, func):
    b = [x for x in pd["banks"] if x["bank"] == bank][0]
    r = [x for x in b["runs"] if x["function"] == func][0]
    if r["status"] != "ok":
        return {"status": r["status"], "error": r.get("error")}
    cd = r["cal_distinct"][0]
    c = (cd["difc"], cd["difa"], cd["tzero"])
    model = "DIFC+TZERO+DIFA" if cd["difa"] != 0 else ("DIFC+TZERO" if cd["tzero"] != 0 else "DIFC")
    fp, fe = r["diagnostics"]["_fitparam"]["rows"], r["diagnostics"]["_fiterror"]["rows"]
    ck = "X0" if "X0" in fp[0] else "PeakCentre"
    ds = np.array([p["d"] for p in b["peaks"]])
    t = np.array([x[ck] for x in fp]); e = np.array([x[ck] for x in fe]); c2 = np.array([x["chi2"] for x in fp])
    ok = (e > 0) & np.isfinite(e) & (e < 1e3) & (c2 < pd["spec"].get("max_chisq", 100)) & (t > 0)
    try:
        p, cov, chi2r, res = lsq(ds[ok], t[ok], e[ok], model)
        p3, _, _, _ = lsq(ds[ok], t[ok], e[ok], "DIFC+TZERO+DIFA")
    except np.linalg.LinAlgError:
        return {"status": "returned, but too few usable centres for an uncertainty", "difc": None,
                "returned": list(c), "model_returned": model, "n_used": int(ok.sum()), "n_peaks": len(ds)}
    return {"status": "ok", "difc": c[0], "difa": c[1], "tzero": c[2], "model_returned": model,
            "sig_difc": float(np.sqrt(cov[0, 0])), "sig_difa": float(np.sqrt(cov[1, 1])), "sig_tzero": float(np.sqrt(cov[2, 2])),
            "cov": cov.tolist(), "chi2r": chi2r, "n_used": int(ok.sum()), "n_peaks": len(ds),
            "rms_resid_ppm": float(1e6 * np.sqrt(np.mean((res / t[ok]) ** 2))),
            "lsq_reproduces_returned": bool(np.allclose(p, c, rtol=1e-6, atol=1e-3)),
            "lsq3": [float(x) for x in p3],
            "resid": [{"d": float(dd), "resid_us": float(rr), "err": float(ee)} for dd, rr, ee in zip(ds[ok], res, e[ok])]}


def main():
    root, outd = sys.argv[1], sys.argv[2]
    os.makedirs(outd, exist_ok=True)
    rows = []
    for f in sorted(glob(os.path.join(root, "own_fit", "*_ownfit.json"))):
        own = json.load(open(f))
        task = own["task"]
        pd = json.load(open(os.path.join(root, "mantid_pdcal", task + "_pdcal.json")))
        for b in own["banks"]:
            bank = b["bank"]
            dmin, dmax = b["d_range"]
            # compare over the d span the Si peaks actually cover (own b2b_fac peaks used); outside it every
            # calibration is an extrapolation
            used = [p["d"] for p in b["b2b_fac"].get("peaks_used", []) if p["kept"]] if b["b2b_fac"].get("status") == "ok" else []
            dlo, dhi = (min(used), max(used)) if used else (dmin, dmax)
            dgrid = np.linspace(dlo, dhi, 41)
            row = {"task": task, "era": META[task][0], "window": META[task][1], "si_run": META[task][2],
                   "srm": META[task][3], "a_cert": own["spec"]["a_cert"], "bank": bank, "d_range": [dmin, dmax],
                   "difc_header": b["difc_header"], "tth_header": b["tth_header"], "profile_laws": b.get("profile_laws"),
                   "own": {}, "mantid": {}, "cmp": {}}
            for arm in ("b2b_fac", "b2b_free", "gauss"):
                c = b[arm]
                if c.get("status") == "ok":
                    row["own"][arm] = {k: c[k] for k in ("difc", "difa", "tzero", "sig_difc", "sig_difa", "sig_tzero", "cov",
                                                          "chi2r", "n_used", "n_rejected", "rms_resid_ppm", "max_abs_resid_ppm")}
                    row["own"][arm]["resid"] = [{"d": p["d"], "resid_us": p["resid_us"], "err": p["err"], "kept": p["kept"]}
                                                for p in c["peaks_used"]]
                else:
                    row["own"][arm] = {"status": c.get("status"), "n": c.get("n")}
            for func in ("Gaussian", "BackToBackExponential"):
                row["mantid"][func] = mantid_arm(pd, bank, func)

            def cc(x):
                return (x["difc"], x["difa"], x["tzero"]), x["cov"]
            pairs = [("mantid_gauss_vs_own_gauss", row["mantid"]["Gaussian"], row["own"]["gauss"]),
                     ("mantid_b2b_vs_own_b2b_free", row["mantid"]["BackToBackExponential"], row["own"]["b2b_free"]),
                     ("mantid_b2b_vs_own_b2b_fac", row["mantid"]["BackToBackExponential"], row["own"]["b2b_fac"]),
                     ("own_gauss_vs_own_b2b_fac", row["own"]["gauss"], row["own"]["b2b_fac"])]
            for name, a, bb in pairs:
                if a.get("difc") is not None and bb.get("difc") is not None:
                    (ca, cva), (cb, cvb) = cc(a), cc(bb)
                    row["cmp"][name] = compare(ca, cva, cb, cvb, dgrid)
            if row["own"]["b2b_fac"].get("difc") is not None:
                ca, cva = cc(row["own"]["b2b_fac"])
                fac = FAC[bank]
                row["cmp"]["own_b2b_fac_vs_facility"] = compare(ca, cva, fac, np.zeros((3, 3)), dgrid)
                lo, hi = D_30_130[bank]
                row["cmp"]["own_b2b_fac_vs_facility_30_130"] = compare(ca, cva, fac, np.zeros((3, 3)), np.linspace(lo, hi, 41))
                if row["mantid"]["BackToBackExponential"].get("difc") is not None:
                    cm, cvm = cc(row["mantid"]["BackToBackExponential"])
                    row["cmp"]["mantid_b2b_vs_facility"] = compare(cm, cvm, fac, np.zeros((3, 3)), dgrid)
            row["dgrid"] = [float(x) for x in dgrid]
            row["d_si_span"] = [float(dlo), float(dhi)]
            rows.append(row)
    json.dump(rows, open(os.path.join(outd, "calibration_table.json"), "w"), indent=1)

    # TSV: one line per task x bank x arm
    with open(os.path.join(outd, "calibration_table.tsv"), "w") as fh:
        fh.write("task\tera\twindow\tsi_run\tbank\tarm\tconvention\tDIFC\tsDIFC\tDIFA\tsDIFA\tTZERO\tsTZERO\tchi2r\tn_peaks\t"
                 "rms_resid_ppm\n")
        for r in rows:
            for arm, conv in (("b2b_fac", "B2B location, facility alpha/beta"), ("b2b_free", "B2B location, alpha/beta free"),
                              ("gauss", "Gaussian centre")):
                x = r["own"][arm]
                if x.get("difc") is None:
                    continue
                fh.write(f"{r['task']}\t{r['era']}\t{r['window']}\t{r['si_run']}\t{r['bank']}\town_{arm}\t{conv}\t"
                         f"{x['difc']:.2f}\t{x['sig_difc']:.2f}\t{x['difa']:.2f}\t{x['sig_difa']:.2f}\t{x['tzero']:.2f}\t"
                         f"{x['sig_tzero']:.2f}\t{x['chi2r']:.2f}\t{x['n_used']}\t{x['rms_resid_ppm']:.0f}\n")
            for func, conv in (("Gaussian", "Gaussian centre"), ("BackToBackExponential", "B2B location, A/B/S free")):
                x = r["mantid"][func]
                if x.get("difc") is None:
                    continue
                fh.write(f"{r['task']}\t{r['era']}\t{r['window']}\t{r['si_run']}\t{r['bank']}\tmantid_{func}\t{conv} "
                         f"[{x['model_returned']}]\t{x['difc']:.2f}\t{x['sig_difc']:.2f}\t{x['difa']:.2f}\t{x['sig_difa']:.2f}\t"
                         f"{x['tzero']:.2f}\t{x['sig_tzero']:.2f}\t{x['chi2r']:.2f}\t{x['n_used']}\t{x['rms_resid_ppm']:.0f}\n")
    # short print
    for r in rows:
        o = r["own"]["b2b_fac"]
        c = r["cmp"]
        s = f"{r['task']:9s} b{r['bank']} own_fac "
        if o.get("difc") is not None:
            s += f"{o['difc']:.2f}({o['sig_difc']:.2f})/{o['difa']:.2f}({o['sig_difa']:.2f})/{o['tzero']:.2f}({o['sig_tzero']:.2f}) chi {o['chi2r']:.1f} n {o['n_used']} rms {o['rms_resid_ppm']:.0f}"
        for k in ("mantid_gauss_vs_own_gauss", "mantid_b2b_vs_own_b2b_free", "mantid_b2b_vs_own_b2b_fac",
                  "own_gauss_vs_own_b2b_fac", "own_b2b_fac_vs_facility", "own_b2b_fac_vs_facility_30_130"):
            if k in c:
                s += f" | {k.replace('_vs_', '~')}: max {c[k]['max_abs_rel_ppm']:.0f} ppm z {c[k]['max_z']:.1f}"
        print(s)


if __name__ == "__main__":
    main()

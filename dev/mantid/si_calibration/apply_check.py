"""Apply-and-check: re-express non-Si batch runs with the per-era Si calibration and compare bank 1 with bank 2
(written 2026-11-06, BRIEF_hrpd_si_calibration_20261106). Clean room: numpy/scipy and our own peak model only.

For each run: isolated peaks are picked in bank 1 inside the d range bank 2 also covers, fitted in TOF with the same
model and convention as the calibration (back-to-back exponentials x Gaussian, alpha/beta held at the facility 2018
laws, sigma free, linear background; own_fit_si.fit_peak), then the same reflection is found and fitted in bank 2.
Each fitted T0 is turned into d two ways:
  geometric:  d = T0 / DIFC_header  (the batch files as they are, no calibration)
  calibrated: d = d_from_tof(T0) with the era's DIFC/DIFA/TZERO (the file the CALIBRATION_MAP names)
and the bank 2 - bank 1 difference Delta d/d = d2/d1 - 1 is reported per peak, with its median and IQR per run.
The .gss files are only read; nothing is written next to them.

usage: python apply_check.py <calibration_table.json> <out.json> [--conv=gauss] <run.gss>=<task> [...]
--conv=gauss: Gaussian centres with the own gauss (peak-maximum) calibration instead, the convention the batch's own
bank-to-bank check used (its geometric numbers are then directly comparable).
"""
import json
import sys

import numpy as np

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from own_fit_si import fit_peak, read_gss  # noqa: E402

FAC = {"alp": 0.174216, "bet0": 0.0247928, "bet1": 0.00694837}
DTT = {1: 0.0003, 2: 0.0007}
FW = {1: 1.0e-3, 2: 4.8e-3}


def d_from_tof(c, t):
    d = (t - c[2]) / c[0]
    for _ in range(50):
        d = (t - c[1] * d * d - c[2]) / c[0]
    return d


def pick(x, y, fw, dlo, dhi, difc):
    """Local maxima of a 5-bin running mean that stand > 8 sigma above a 101-bin running median and are the highest
    point within +-3 FWHM (isolation)."""
    k = 5
    ys = np.convolve(y, np.ones(k) / k, mode="same")
    h = 50
    yp = np.pad(y, h, mode="edge")
    bg = np.array([np.median(yp[i:i + 2 * h + 1]) for i in range(len(y))])
    out = []
    for i in range(3, len(x) - 3):
        d = x[i] / difc
        if not (dlo < d < dhi):
            continue
        if ys[i] < ys[i - 1] or ys[i] < ys[i + 1]:
            continue
        w = np.abs(x - x[i]) < 3 * fw * x[i]
        if ys[i] < np.max(ys[w]):
            continue
        noise = np.sqrt(max(np.median(np.abs(np.diff(y[w]))) ** 2, 1e-30))
        if ys[i] - bg[i] > 8 * noise:
            out.append(i)
    return out


SIG = {}  # per bank (sig0, sig1, sig2) of the era's calibration, set in main()
CONV = {"arm": "b2b_fac"}  # "b2b_fac" (B2B T0 + the b2b_fac calibration) or "gauss" (Gaussian centre + the gauss one)


def _fit_fixed(x, y, e, bank, t0g):
    d = t0g / (48236.8 if bank == 1 else 34789.9)  # header DIFC: d to 0.1 %, enough for the alpha/beta laws
    a = FAC["alp"] / d
    b = FAC["bet0"] + FAC["bet1"] / d ** 4
    s0, s1, s2 = SIG[bank]
    s_law = float(np.sqrt(s0 + s1 * d * d + s2 * d ** 4))
    # a sample line may be broader than Si (size/strain), but not 4x: wider fits are overlaps
    if CONV["arm"] == "gauss":
        p = fit_peak(x, y, e, DTT[bank], t0g, "gauss")
        p["s_law"] = 1.5 * s_law  # a Gaussian on the asymmetric line is wider than the B2B sigma
        return p
    p = fit_peak(x, y, e, DTT[bank], t0g, "b2b", fixed=(a, b), s_start=s_law, s_max=4 * s_law)
    p["s_law"] = s_law
    return p


def good(p, fw_t, chi2_max=50):
    """chi2_max is 50 in bank 1; bank 2 (4x coarser) sees most sample lines as unresolved blends, so it allows 200."""
    return (p is not None and p["success"] and np.isfinite(p["err_T0"]) and 0 < p["err_T0"] < 0.15 * fw_t
            and p["I"] > 10 * p["err_I"] and p["chi2r"] < chi2_max and not p["at_bound"] and p["s"] < 3.9 * p["s_law"])


def main():
    rows = json.load(open(sys.argv[1]))
    args = sys.argv[3:]
    if args and args[0].startswith("--conv="):
        CONV["arm"] = args.pop(0).split("=")[1]
    R = {(r["task"], r["bank"]): r for r in rows}
    res = []
    for arg in args:
        path, task = arg.split("=")
        data = read_gss(path)
        hdr = [l for l in open(path, encoding="latin-1") if l.startswith("#") and "DIFC" in l]
        dg = {i + 1: float(l.split("DIFC")[1]) for i, l in enumerate(hdr)}
        arm = CONV["arm"]
        cal = {b: (R[(task, b)]["own"][arm]["difc"], R[(task, b)]["own"][arm]["difa"],
                   R[(task, b)]["own"][arm]["tzero"]) for b in (1, 2)}
        span = {b: R[(task, b)]["d_si_span"] for b in (1, 2)}
        for b in (1, 2):
            pl = R[(task, b)]["profile_laws"]
            SIG[b] = (pl.get("sig0", 0.0), pl.get("sig1", 0.0), pl.get("sig2", 0.0))
        (x1, y1, e1), (x2, y2, e2) = [tuple(np.asarray(v)[np.asarray(data[b][2]) > 0] for v in data[b]) for b in (1, 2)]
        dlo = max(x1[0] / dg[1], x2[0] / dg[2]) * 1.01
        dhi = min(x1[-1] / dg[1], x2[-1] / dg[2]) / 1.01
        pairs = []
        for i in pick(x1, y1, FW[1], dlo, dhi, dg[1]):
            t1g = x1[i]
            m = (x1 > t1g * (1 - 3 * FW[1])) & (x1 < t1g * (1 + 6 * FW[1]))
            p1 = _fit_fixed(x1[m], y1[m], e1[m], 1, t1g) if m.sum() >= 12 else None
            if not good(p1, 2.355 * (p1 or {"s": 1})["s"]):
                continue
            dgeo1 = p1["T0"] / dg[1]
            t2g = dgeo1 * dg[2]
            w2 = np.abs(x2 - t2g) < 1.5 * FW[2] * t2g
            if w2.sum() < 3:
                continue
            # bank 2 isolation: the highest point within +-1.5 FWHM must be the only strong one within +-3 FWHM
            ys2 = np.convolve(y2, np.ones(5) / 5, mode="same")
            j = np.where(w2)[0][np.argmax(ys2[w2])]
            dist = np.abs(x2 - x2[j]) / (FW[2] * x2[j])
            ring = np.where((dist > 1.5) & (dist < 3))[0]
            near_other = [k for k in ring if ys2[k] > 0.5 * ys2[j]
                          and ys2[k] >= ys2[max(k - 1, 0)] and ys2[k] >= ys2[min(k + 1, len(ys2) - 1)]]
            if near_other:
                continue
            m2 = (x2 > x2[j] * (1 - 3 * FW[2])) & (x2 < x2[j] * (1 + 6 * FW[2]))
            p2 = _fit_fixed(x2[m2], y2[m2], e2[m2], 2, x2[j]) if m2.sum() >= 12 else None
            if not good(p2, 2.355 * (p2 or {"s": 1})["s"], chi2_max=200):
                continue
            geo = (p2["T0"] / dg[2]) / dgeo1 - 1
            if abs(geo) > 5e-3:
                continue
            c1, c2 = d_from_tof(cal[1], p1["T0"]), d_from_tof(cal[2], p2["T0"])
            pairs.append({"d1_geo": dgeo1, "d1_cal": float(c1), "d2_cal": float(c2), "geo": float(geo),
                          "cal": float(c2 / c1 - 1),
                          "inside_si_span": bool(span[1][0] <= c1 <= span[1][1] and span[2][0] <= c2 <= span[2][1]),
                          "err": float(np.hypot(p1["err_T0"] / p1["T0"], p2["err_T0"] / p2["T0"]))})
        g = np.array([p["geo"] for p in pairs]); c = np.array([p["cal"] for p in pairs])
        q = lambda v: [float(np.percentile(v, 25)), float(np.percentile(v, 75))] if len(v) else None
        r = {"run": path.rsplit("/", 1)[-1], "task_calibration": task, "convention": CONV["arm"], "n_pairs": len(pairs),
             "geo_median": float(np.median(g)) if len(g) else None, "geo_iqr": q(g),
             "cal_median": float(np.median(c)) if len(c) else None, "cal_iqr": q(c),
             "n_inside_si_span": int(sum(p["inside_si_span"] for p in pairs)), "pairs": pairs}
        res.append(r)
        print(f"{r['run']:14s} cal {task:8s} n {len(pairs):3d} (inside Si span {r['n_inside_si_span']}) | bank2-bank1 "
              f"geometric {np.median(g) if len(g) else float('nan'):+.2e} -> calibrated "
              f"{np.median(c) if len(c) else float('nan'):+.2e}  (IQR {q(c)})")
    json.dump(res, open(sys.argv[2], "w"), indent=1)


if __name__ == "__main__":
    main()

"""Own, clean-room arm of the per-era HRPD Si calibration: single-peak fits in TOF on the focused Si .gss, then a
weighted least-squares fit of TOF = DIFC*d + DIFA*d^2 + TZERO against the certified Si d-spacings.

Written 2026-11-06 for BRIEF_hrpd_si_calibration_20261106.md. Nothing here comes from Mantid, GSAS-II, FullProf, Jana2006
or TOPAS source. numpy/scipy only; the .gss is parsed here (GSAS FXYE: X = TOF bin centre in us, Y, E).

Peak shape, from the literature: a back-to-back pair of exponentials convolved with a Gaussian (Von Dreele, Jorgensen &
Windsor 1982, J. Appl. Cryst. 15, 581-589), unit area, location T0:
    H(t) = N [exp(u) erfc(y) + exp(v) erfc(z)],  N = a b / (2 (a + b)),  D = t - T0,
    u = a/2 (a s^2 + 2D),  y = (a s^2 + D) / (sqrt2 s),  v = b/2 (b s^2 - 2D),  z = (b s^2 - D) / (sqrt2 s).
Evaluated stably: exp(u) erfc(y) = exp(-D^2 / 2s^2) erfcx(y) for y >= 0 (u - y^2 = -D^2/2s^2), and directly for y < 0,
where u < 0. Each bin is averaged over 5 points across its width (log binning, dt/t of the bank).
The d-dependence used to tie weak peaks, as in GSAS profile function 3 (alpha = alp/d, beta = bet0 + bet1/d^4,
sigma^2 = sig0 + sig1 d^2 + sig2 d^4; GSAS Technical Manual, Larson & Von Dreele 2004, LAUR 86-748, p. 148):
  pass 1: every peak free (I, T0, a, b, s, linear background);
  pass 2: every peak refitted with alpha and beta HELD at the facility's own 2018 type-3 laws (spec "b2b_fixed",
          from Cyc_182_mantid3.hrpd: alpha = alp/d, beta = bet0 + bet1/d^4), I, T0, sigma and background free;
          a sigma law sigma^2 = sig0 + sig1 d^2 + sig2 d^4 is then fitted per bank for the profile record.
Three calibrations per bank, one per peak-position convention:
  b2b_fac  - pass-2 T0 (the facility's profile convention; this is the one written to the instrument files);
  b2b_free - pass-1 T0 (alpha, beta free per peak: no profile law assumed; weak peaks carry large errors);
  gauss    - Gaussian centre (the peak-maximum convention a symmetric-profile fit measures).
A Gaussian-centre variant (Gaussian + linear background, same windows) is also run, so the Mantid Gaussian arm has an
own counterpart in its own peak-position convention.

Calibration: weighted LSQ of T0 against d_cert (weights 1/sigma_T0^2; sigma_T0 from the fit covariance scaled by the
peak's reduced chi^2 when > 1); the parameter covariance is scaled by the calibration's reduced chi^2 when > 1. Peaks are
rejected, one at a time and worst first, while |residual| / sigma > 5 (each rejection is recorded).

usage: python own_fit_si.py <spec.json>   spec: {"task", "gss", "a_cert", "srm", "out", "fwhm_rel": [..3], "dtt": [..3]}
"""
import json
import os
import sys
import time

import numpy as np
from scipy.optimize import least_squares
from scipy.special import erfc, erfcx

SQ2 = np.sqrt(2.0)


def read_gss(path):
    """{bank: (x, y, e)} from a GSAS FXYE file (BANK records, then 3 numbers per line)."""
    banks, cur = {}, None
    for line in open(path, encoding="latin-1"):
        if line.startswith("BANK"):
            cur = int(line.split()[1])
            banks[cur] = []
            continue
        if cur is None or line.startswith("#"):
            continue
        p = line.split()
        if len(p) >= 3:
            try:
                banks[cur].append([float(p[0]), float(p[1]), float(p[2])])
            except ValueError:
                pass
    return {b: tuple(np.asarray(v, float).T) for b, v in banks.items()}


def b2b(t, t0, a, b, s):
    D = t - t0
    y = (a * s * s + D) / (SQ2 * s)
    z = (b * s * s - D) / (SQ2 * s)
    g = np.exp(-D * D / (2 * s * s))
    with np.errstate(over="ignore", invalid="ignore"):
        t1 = np.where(y >= 0, g * erfcx(np.maximum(y, 0)), np.exp(np.minimum(a / 2 * (a * s * s + 2 * D), 0)) * erfc(y))
        t2 = np.where(z >= 0, g * erfcx(np.maximum(z, 0)), np.exp(np.minimum(b / 2 * (b * s * s - 2 * D), 0)) * erfc(z))
    return a * b / (2 * (a + b)) * (t1 + t2)


def gauss(t, t0, s):
    return np.exp(-(t - t0) ** 2 / (2 * s * s)) / (np.sqrt(2 * np.pi) * s)


OFFS = np.array([-0.4, -0.2, 0.0, 0.2, 0.4])


def binavg(f, t, dtt, *p):
    w = t * dtt
    return np.mean([f(t + o * w, *p) for o in OFFS], axis=0)


def si_reflections(A, dmin, dmax):
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
                if (odd or even) and dmin <= A / np.sqrt(n) <= dmax:
                    seen.setdefault(n, []).append((h, k, l))
    return sorted((A / np.sqrt(n), n, v) for n, v in seen.items())


def fit_peak(t, y, e, dtt, t0g, kind, fixed=None, d=1.0, s_start=None, s_max=None):
    """Least-squares fit of one peak + linear background. Returns dict with values, errors, chi2r."""
    tm = np.mean(t)
    bg0 = np.percentile(y, 10)
    area0 = max(np.sum((y - bg0) * t * dtt), 1e-6)
    s0 = max(2.0 * t0g * 4e-4, 2.0) if s_start is None else s_start  # s_start/s_max: used by apply_check only
    if kind == "gauss":
        names = ["I", "T0", "s", "b0", "b1"]
        p0 = [area0, t0g, s0, bg0, 0.0]
        lo = [0, t0g - 0.02 * t0g, 0.2, -np.inf, -np.inf]
        hi = [np.inf, t0g + 0.02 * t0g, 0.02 * t0g, np.inf, np.inf]

        def model(p):
            return p[0] * binavg(gauss, t, dtt, p[1], p[2]) + p[3] + p[4] * (t - tm)
    elif fixed is None:
        names = ["I", "T0", "a", "b", "s", "b0", "b1"]
        p0 = [area0, t0g, 0.2 / d, 0.03, s0, bg0, 0.0]
        lo = [0, t0g - 0.02 * t0g, 1e-4, 1e-4, 0.2, -np.inf, -np.inf]
        hi = [np.inf, t0g + 0.02 * t0g, 10.0, 5.0, 0.02 * t0g, np.inf, np.inf]

        def model(p):
            return p[0] * binavg(b2b, t, dtt, p[1], p[2], p[3], p[4]) + p[5] + p[6] * (t - tm)
    else:
        fa, fb = fixed
        names = ["I", "T0", "s", "b0", "b1"]
        p0 = [area0, t0g, s0, bg0, 0.0]
        lo = [0, t0g - 0.02 * t0g, 0.2, -np.inf, -np.inf]
        hi = [np.inf, t0g + 0.02 * t0g, 0.02 * t0g if s_max is None else s_max, np.inf, np.inf]

        def model(p):
            return p[0] * binavg(b2b, t, dtt, p[1], fa, fb, p[2]) + p[3] + p[4] * (t - tm)
    lo, hi = np.array(lo, float), np.array(hi, float)
    eps = 1e-9 * np.maximum(1.0, np.abs(np.where(np.isfinite(lo), lo, 0.0)))
    p0 = np.clip(np.array(p0, float), np.where(np.isfinite(lo), lo + eps, -np.inf), np.where(np.isfinite(hi), hi - eps, np.inf))
    r = least_squares(lambda p: (model(p) - y) / e, p0, bounds=(lo, hi), x_scale="jac", max_nfev=4000)
    n, k = len(t), len(names)
    chi2r = float(np.sum(r.fun ** 2) / max(n - k, 1))
    try:
        cov = np.linalg.inv(r.jac.T @ r.jac) * max(chi2r, 1.0)
        err = np.sqrt(np.diag(cov))
    except np.linalg.LinAlgError:
        err = np.full(k, np.nan)
    out = {nm: float(v) for nm, v in zip(names, r.x)}
    out.update({"err_" + nm: float(v) for nm, v in zip(names, err)})
    out.update(chi2r=chi2r, n=n, success=bool(r.success), at_bound=bool(np.any(r.active_mask != 0)))
    return out


def calib_fit(d, t, et, nsig=5.0):
    """Weighted LSQ for DIFC, DIFA, TZERO with iterative worst-first rejection beyond nsig."""
    keep = np.ones(len(d), bool)
    rejected = []
    while True:
        M = np.vstack([d[keep], d[keep] ** 2, np.ones(keep.sum())]).T
        W = 1 / et[keep] ** 2
        cov0 = np.linalg.inv(M.T @ (M * W[:, None]))
        p = cov0 @ (M.T @ (W * t[keep]))
        resid_all = t - (p[0] * d + p[1] * d * d + p[2])
        dof = keep.sum() - 3
        chi2r = float(np.sum(resid_all[keep] ** 2 / et[keep] ** 2) / max(dof, 1))
        z = np.abs(resid_all) / (et * np.sqrt(max(chi2r, 1.0)))
        z[~keep] = 0
        j = int(np.argmax(z))
        if z[j] > nsig and keep.sum() > 5:
            keep[j] = False
            rejected.append({"d": float(d[j]), "resid_us": float(resid_all[j]), "z": float(z[j])})
            continue
        cov = cov0 * max(chi2r, 1.0)
        return {"difc": float(p[0]), "difa": float(p[1]), "tzero": float(p[2]),
                "sig_difc": float(np.sqrt(cov[0, 0])), "sig_difa": float(np.sqrt(cov[1, 1])),
                "sig_tzero": float(np.sqrt(cov[2, 2])), "cov": cov.tolist(), "chi2r": chi2r, "n_used": int(keep.sum()),
                "n_rejected": len(rejected), "rejected": rejected,
                "rms_resid_ppm": float(1e6 * np.sqrt(np.mean((resid_all[keep] / t[keep]) ** 2))),
                "max_abs_resid_ppm": float(1e6 * np.max(np.abs(resid_all[keep] / t[keep]))),
                "keep": keep.tolist(), "resid_us": resid_all.tolist()}


def wfit(M, y, w):
    """Weighted linear LSQ: parameters, covariance (scaled by chi2r when > 1), chi2r."""
    cov0 = np.linalg.inv(M.T @ (M * w[:, None]))
    p = cov0 @ (M.T @ (w * y))
    chi2r = float(np.sum(w * (y - M @ p) ** 2) / max(len(y) - M.shape[1], 1))
    return p, cov0 * max(chi2r, 1.0), chi2r


def main():
    spec = json.load(open(sys.argv[1]))
    t_start = time.time()
    A = float(spec["a_cert"])
    FW = spec.get("fwhm_rel", [1.0e-3, 2.5e-3, 8.0e-3])
    DTT = spec.get("dtt", [0.0003, 0.0007, 0.0012])
    data = read_gss(spec["gss"])
    hdr = [l for l in open(spec["gss"], encoding="latin-1") if "DIFC" in l and l.startswith("#")]
    difc_geom = [float(l.split("DIFC")[1]) for l in hdr]
    tth = [float(l.split("tth")[1].split("deg")[0]) for l in hdr]
    out = {"task": spec["task"], "spec": spec, "difc_header": difc_geom, "tth_header": tth, "banks": []}
    banks = []
    # ---- pass 1, every bank: each peak with I, T0, alpha, beta, sigma and background free
    for b in sorted(data):
        x, y, e = data[b]
        good = e > 0
        x, y, e = x[good], y[good], e[good]
        dtt, fw, dg = DTT[b - 1], FW[b - 1], difc_geom[b - 1]
        dmin, dmax = x[0] / dg, x[-1] / dg
        refl = si_reflections(A, dmin * 1.004, dmax / 1.004)
        ds = [r[0] for r in refl]
        peaks = []
        for j, (d, n, hkls) in enumerate(refl):
            gap_lo = d - ds[j - 1] if j > 0 else d - dmin
            gap_hi = ds[j + 1] - d if j + 1 < len(ds) else dmax - d
            wl, wr = min(4 * fw * d, 0.45 * gap_lo), min(8 * fw * d, 0.45 * gap_hi)
            if wl < 2 * fw * d or wr < 3 * fw * d:
                continue
            # geometric DIFC plus the +0.1 % the batch measured, only to centre the window; T0 then starts at the max
            tc = dg * 1.001 * d
            m = (x > tc * (1 - wl / d)) & (x < tc * (1 + wr / d))
            if m.sum() < 12:
                continue
            tt, yy, ee = x[m], y[m], e[m]
            core = np.abs(tt - tc) < 2.5 * fw * tc
            t0g = float(tt[core][np.argmax(yy[core])]) if core.any() else tc
            pk = {"d": float(d), "N": int(n), "hkl": [list(h) for h in hkls], "lambda": float(2 * d * np.sin(np.radians(tth[b - 1]) / 2)),
                  "window_us": [float(tt[0]), float(tt[-1])]}
            pk["p1"] = fit_peak(tt, yy, ee, dtt, t0g, "b2b", d=d)
            pk["gauss"] = fit_peak(tt, yy, ee, dtt, t0g, "gauss")
            pk["_data"] = (tt, yy, ee, t0g)
            peaks.append(pk)
        banks.append({"bank": b, "dtt": dtt, "difc_header": dg, "tth_header": tth[b - 1], "d_range": [dmin, dmax],
                      "peaks": peaks})

    fac = spec["b2b_fixed"]  # the facility's own 2018 type-3 laws (Cyc_182_mantid3.hrpd PRCF set 1)
    out["b2b_fixed_source"] = spec.get("b2b_fixed_source")

    def usable(p, key="T0"):
        fwhm = 2.355 * p["s"] if "s" in p else 1
        return (p["success"] and np.isfinite(p["err_" + key]) and p["err_" + key] > 0 and p["I"] > 5 * p["err_I"]
                and p["err_" + key] < 0.3 * fwhm and p["chi2r"] < 200)

    for bk in banks:
        b, dtt = bk["bank"], bk["dtt"]
        q = fac[str(b)]
        bl = {"alpha0": 0.0, "alpha1": q["alp"], "beta0": q["bet0"], "beta1": q["bet1"], "source": "facility 2018 PRCF"}
        for pk in bk["peaks"]:
            tt, yy, ee, t0g = pk.pop("_data")
            fa = q["alp"] / pk["d"]
            fb = q["bet0"] + q["bet1"] / pk["d"] ** 4
            pk["p2"] = fit_peak(tt, yy, ee, dtt, t0g, "b2b", fixed=(fa, fb))
            pk["p2"].update(a_fixed=fa, b_fixed=fb)
        # sigma law for the profile record: sigma^2 = sig0 + sig1 d^2 + sig2 d^4 over the usable pass-2 peaks
        su = [pk for pk in bk["peaks"] if usable(pk["p2"])]
        if len(su) >= 4:
            dd = np.array([pk["d"] for pk in su]); ss = np.array([pk["p2"]["s"] for pk in su])
            es = np.array([pk["p2"]["err_s"] for pk in su])
            ps, cs, xs = wfit(np.vstack([np.ones_like(dd), dd ** 2, dd ** 4]).T, ss ** 2, 1 / (2 * ss * es) ** 2)
            if ps[0] < 0 or ps[2] < 0:  # keep the variance law non-negative: drop the offending term(s)
                cols = [k for k in range(3) if not (k in (0, 2) and ps[k] < 0)]
                M = np.vstack([np.ones_like(dd), dd ** 2, dd ** 4]).T[:, cols]
                pp, _, xs = wfit(M, ss ** 2, 1 / (2 * ss * es) ** 2)
                ps = np.zeros(3); ps[cols] = pp
            bl.update(sig0=float(ps[0]), sig1=float(ps[1]), sig2=float(ps[2]), sig_chi2r=float(xs))
        bk["profile_laws"] = bl
        for arm, key in (("b2b_fac", "p2"), ("b2b_free", "p1"), ("gauss", "gauss")):
            use = [pk for pk in bk["peaks"] if usable(pk[key])]
            if len(use) < 4:
                bk[arm] = {"status": "too few peaks", "n": len(use)}
                continue
            d = np.array([pk["d"] for pk in use]); t = np.array([pk[key]["T0"] for pk in use])
            et = np.array([pk[key]["err_T0"] for pk in use])
            c = calib_fit(d, t, et)
            c["status"] = "ok"
            c["peaks_used"] = [{"d": float(dd_), "T0": float(tt_), "err": float(e_), "kept": bool(k_), "resid_us": float(r_)}
                               for dd_, tt_, e_, k_, r_ in zip(d, t, et, c["keep"], c["resid_us"])]
            for kk in ("keep", "resid_us"):
                c.pop(kk)
            bk[arm] = c
        out["banks"].append(bk)
        print(json.dumps({"bank": b, "n_peaks": len(bk["peaks"]), "profile": bl,
                          **{arm: {k: bk[arm].get(k) for k in ("difc", "difa", "tzero", "sig_difc", "sig_difa", "sig_tzero",
                                                                "chi2r", "n_used", "rms_resid_ppm")}
                             for arm in ("b2b_fac", "b2b_free", "gauss")}}),
              flush=True)
    out["wall_s"] = round(time.time() - t_start, 2)
    os.makedirs(spec["out"], exist_ok=True)
    with open(os.path.join(spec["out"], spec["task"] + "_ownfit.json"), "w") as fh:
        json.dump(out, fh, indent=1)


if __name__ == "__main__":
    main()

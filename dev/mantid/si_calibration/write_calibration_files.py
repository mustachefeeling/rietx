"""Write the per-era HRPD Si calibrations as instrument files rietx main reads (written 2026-11-06).

For each era x window with a Si run, from the own-arm b2b_fac calibration (analysis/calibration_table.json):
  * HRPD_<era>_<window>.iparm - GSAS-I instrument parameter file, all 3 banks, strict 80-column records laid out as
    rietx.read_gsas_tof_iparm reads them (GSAS Technical Manual p. 221-223, as quoted in rietx's reader docstring and in
    docs/docs/reference/instrument-files.md): BANK (I5 in 13-17), HTYPE (2X,A4: PNTR in 15-18), FPATH1, per bank ICONS
    (3F10.0 in 13-42), BNKPAR (DIST 13-22, TTHETA 23-32), I HEAD (text, dropped by the reader), PRCF1 header
    (PTYP 3, NCOF 21, CTOF) and PRCF11-PRCF16 (4E15.6 each, the 21 type-3 coefficients in the manual's order);
  * HRPD_<era>_<window>_bank<b>.instprm - GSAS-II time-of-flight .instprm, one bank per file (the format is one bank
    per file in rietx's reader), key:value lines with the keys rietx's reader maps.
Profile: alpha = alp/d, beta = bet-0 + bet-1/d^4 are the facility 2018 values (Cyc_182_mantid3.hrpd PRCF set 1),
which is the convention the peak positions were fitted in; sig-0/1/2 are our own per-bank law; gam = 0 (no Lorentzian
was fitted). A calibration and its profile belong together: TZERO/DIFA move with the alpha/beta assumed.

usage: python write_calibration_files.py <calibration_table.json> <out_dir>
"""
import json
import os
import sys

L1 = 95.0
L2 = {1: 0.89, 2: 1.80, 3: 4.054}  # focused secondary paths from the focus log (Total flight path - 95 m)
FILES = {  # era/window file -> (task giving banks 1-2, task giving bank 3, note)
    "HRPD_2008_10-110": ("si08_10", "si08_10", "HRP39182 NBS Si 10-110 ms, 2008-07-04; SRM not named, 640e cell assumed"),
    "HRPD_2008_30-130": ("si08_30", "si08_10", "HRP39183 NBS Si 30-130 ms, 2008-07-05 (bank 3 from HRP39182 10-110 ms: "
                                               "too few Si peaks in bank 3 at 30-130); SRM not named, 640e assumed"),
    "HRPD_2013_10-110": ("si13_10", "si13_10", "HRP58469 SRM640c 10-110 ms, 2013-11-18"),
    "HRPD_2018_10-110": ("si18_10", "si18_10", "HRP70715 SRM640e 10-110 ms, 2018-06-06 (post HT repair)"),
}


def f10(v, dec):
    s = f"{v:10.{dec}f}"
    if len(s) != 10:
        raise ValueError(f"value {v} does not fit F10.{dec}")
    return s


def e15(v):
    s = f"{v:15.6E}"
    if len(s) != 15:
        raise ValueError(v)
    return s


def rec(key, payload=""):
    line = (key + payload).ljust(80)
    if len(key) != 12 or len(line) != 80:
        raise ValueError(repr(line))
    return line


def main():
    rows = json.load(open(sys.argv[1]))
    out = sys.argv[2]
    os.makedirs(out, exist_ok=True)
    R = {(r["task"], r["bank"]): r for r in rows}
    index = []
    for stem, (t12, t3, note) in FILES.items():
        lines = [rec("            ", "123456789012345678901234567890123456789012345678901234567890"),
                 rec("INS   BANK  ", f"{3:5d}"),
                 rec("INS   HTYPE ", "  PNTR"),
                 rec("INS   FPATH1", f"{L1:10.4f}")]
        for b in (1, 2, 3):
            r = R[(t12 if b < 3 else t3, b)]
            o = r["own"]["b2b_fac"]
            pl = r["profile_laws"]
            coef = [pl["alpha1"], pl["beta0"], pl["beta1"], pl.get("sig0", 0.0), pl.get("sig1", 0.0), pl.get("sig2", 0.0)]
            coef += [0.0] * (21 - len(coef))
            head = (f"{stem} b{b} {r['si_run']} DIFC {o['difc']:.2f}({o['sig_difc']:.2f}) DIFA {o['difa']:.2f}"
                    f"({o["sig_difa"]:.2f}) ZERO {o["tzero"]:.2f}({o["sig_tzero"]:.2f})")[:67]
            bb = f"{b:2d}"
            lines += [rec(f"INS {bb} ICONS", f10(o["difc"], 2) + f10(o["difa"], 3) + f10(o["tzero"], 3)),
                      rec(f"INS {bb}BNKPAR", f10(L2[b], 4) + f10(r["tth_header"], 4)),
                      rec(f"INS {bb}I HEAD", " " + head),
                      rec(f"INS {bb}PRCF1 ", f"{3:5d}{21:5d}{0.001:10.5f}")]
            for k in range(6):
                lines.append(rec(f"INS {bb}PRCF1{k + 1}", "".join(e15(v) for v in (coef[4 * k:4 * k + 4] + [0.0] * 4)[:4])))
            # one-bank GSAS-II .instprm
            ip = [f"#GSAS-II instrument parameter file; do not add/delete items!",
                  f"# {stem} bank {b}: per-era Si calibration, BRIEF_hrpd_si_calibration_20261106 (own arm, b2b_fac)",
                  f"# Si run {r['si_run']} ({r['srm']}), a_cert {r['a_cert']} A; fitted d span {r['d_si_span'][0]:.3f}-"
                  f"{r['d_si_span'][1]:.3f} A",
                  f"# sigma: DIFC {o['sig_difc']:.3f}  DIFA {o['sig_difa']:.3f}  Zero {o['sig_tzero']:.3f} (us; chi2r "
                  f"{o['chi2r']:.2f}, {o['n_used']} Si peaks, rms {o['rms_resid_ppm']:.0f} ppm)",
                  "# alpha, beta-0, beta-1: facility 2018 profile (Cyc_182_mantid3.hrpd), the convention the positions "
                  "were fitted in; sig-*: own law",
                  "Type:PNT", "Bank:%d.0" % b, f"fltPath:{L1 + L2[b]:.4f}", f"2-theta:{r['tth_header']:.4f}",
                  f"difC:{o['difc']:.4f}", f"difA:{o['difa']:.4f}", "difB:0.0", f"Zero:{o['tzero']:.4f}",
                  f"alpha:{pl['alpha1']}", f"beta-0:{pl['beta0']}", f"beta-1:{pl['beta1']}",
                  f"sig-0:{pl.get('sig0', 0.0):.6f}", f"sig-1:{pl.get('sig1', 0.0):.6f}", f"sig-2:{pl.get('sig2', 0.0):.6f}"]
            fn = f"{stem}_bank{b}.instprm"
            open(os.path.join(out, fn), "w").write("\n".join(ip) + "\n")
            index.append({"file": fn, "format": "GSAS-II .instprm (Type PNT)", "bank": b, "task": r["task"], "si_run": r["si_run"],
                          "difc": o["difc"], "difa": o["difa"], "tzero": o["tzero"], "sig_difc": o["sig_difc"],
                          "sig_difa": o["sig_difa"], "sig_tzero": o["sig_tzero"], "cov": o["cov"], "d_si_span": r["d_si_span"]})
        open(os.path.join(out, stem + ".iparm"), "w").write("\n".join(lines) + "\n")
        index.append({"file": stem + ".iparm", "format": "GSAS-I .iparm (strict columns)", "note": note})
    json.dump(index, open(os.path.join(out, "calibration_files_index.json"), "w"), indent=1)
    print("\n".join(sorted(os.listdir(out))))


if __name__ == "__main__":
    main()

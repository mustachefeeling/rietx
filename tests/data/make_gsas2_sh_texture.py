"""Generate `gsas2_sh_texture.json`, GSAS-II's spherical-harmonics texture golden.

Run under GSAS-II 5.8.4's own interpreter, never this package's:

    <GSAS-II>/pixi/.pixi/envs/default/bin/python -I tests/data/make_gsas2_sh_texture.py OUT.json

It calls GSAS-II and ports none of it (ATTRIBUTION.md: GSAS-II is a
behavioural reference). For each case, a Laue class in one setting with a
generic cell, it records over every hkl with |h|, |k|, |l| <= 2 taken once per
Friedel pair:

- `phi`, `beta`: the reflection's polar and azimuthal angles in GSAS-II's
  crystal frame (`GSASIIlattice.CrsAng`);
- `kcl`: GSAS-II's crystal harmonic K_l^n(h) for every coefficient it allows
  up to order 8 (`GSASIIlattice.GetKcl`), one row per coefficient;
- `orbit`: an index shared by symmetry-equivalent reflections
  (`GSASIIspc.GenHKLf`, Friedel mates joined);
- `noninvariant`: each coefficient whose K takes more than one value on some
  orbit, with the largest spread, measured over the full +-hkl set. Such a
  K is a function of which representative GSAS-II is handed, not of the
  reflection, so no basis can match it;
- `p`: the multiplier `GSASIIstrMath.SHPOcal` returns for the case's seeded
  coefficients under `Bragg` and under `Debye` at zero goniometer angles,
  with the sample angle `psi` each one used (`GSASIIlattice.SamAng`).

The harmonics need `pytexture.pyqlmninit()` before the first call. GSAS-II's
refinement driver makes that call; a direct call without it returns 0.0.
`pytexture` computes in single precision, so the numbers agree with an exact
evaluation to about 1e-7 relative, never to the last digit. The script
asserts that `SHPOcal`'s P equals 1 + sum(C * Lnorm * Kcl * Ksl) and differs
from 1, which ties the recorded harmonics to the refinement's own path.
"""

import datetime
import itertools
import json
import platform
import sys

import numpy as np
from GSASII import GSASIIlattice as G2lat
from GSASII import GSASIIspc as G2spc
from GSASII import GSASIIstrMath as G2stM

WAVELENGTH = 1.5406
ORDER = 8
SEED = 1960

# One generic cell per case: every free metric parameter away from a special value.
CASES = [
    ("-1", "P -1", (5.1, 6.3, 7.4, 82.0, 97.0, 104.0)),
    ("2/m unique a", "P 2/m 1 1", (5.1, 6.3, 7.4, 103.0, 90.0, 90.0)),
    ("2/m unique b", "P 1 2/m 1", (5.1, 6.3, 7.4, 90.0, 103.0, 90.0)),
    ("2/m unique c", "P 1 1 2/m", (5.1, 6.3, 7.4, 90.0, 90.0, 103.0)),
    ("mmm", "P m m m", (5.1, 6.3, 7.4, 90.0, 90.0, 90.0)),
    ("4/m", "P 4/m", (5.1, 5.1, 7.4, 90.0, 90.0, 90.0)),
    ("4/mmm", "P 4/m m m", (5.1, 5.1, 7.4, 90.0, 90.0, 90.0)),
    ("-3 hexagonal axes", "P -3", (5.1, 5.1, 7.4, 90.0, 90.0, 120.0)),
    ("-3 rhombohedral axes", "R -3 R", (5.5, 5.5, 5.5, 55.0, 55.0, 55.0)),
    ("-3m1", "P -3 m 1", (5.1, 5.1, 7.4, 90.0, 90.0, 120.0)),
    ("-31m", "P -3 1 m", (5.1, 5.1, 7.4, 90.0, 90.0, 120.0)),
    ("-3m rhombohedral axes", "R -3 m R", (5.5, 5.5, 5.5, 55.0, 55.0, 55.0)),
    ("6/m", "P 6/m", (5.1, 5.1, 7.4, 90.0, 90.0, 120.0)),
    ("6/mmm", "P 6/m m m", (5.1, 5.1, 7.4, 90.0, 90.0, 120.0)),
    ("m-3", "P m -3", (5.1, 5.1, 5.1, 90.0, 90.0, 90.0)),
    ("m-3m", "P m -3 m", (5.1, 5.1, 5.1, 90.0, 90.0, 90.0)),
]


def all_hkls():
    return [hkl for hkl in itertools.product(range(-2, 3), repeat=3) if hkl != (0, 0, 0)]


def is_friedel_representative(hkl):
    return next(x for x in hkl if x) > 0


def noninvariant(names, kcl, orbit):
    """Each coefficient's largest spread of K over one orbit, Friedel mates included."""
    out = {}
    for name, row in zip(names, kcl):
        spread = max(float(np.ptp(row[np.asarray(orbit) == o])) for o in set(orbit))
        if spread > 1e-5:
            out[name] = round(spread, 4)
    return out


def orbit_ids(hkls, sgdata):
    key_to_id, ids = {}, []
    for hkl in hkls:
        uniq = G2spc.GenHKLf(list(hkl), sgdata)[2]
        members = {tuple(int(round(x)) for x in u) for u in uniq}
        members |= {tuple(-x for x in m) for m in members}
        key = min(members)
        ids.append(key_to_id.setdefault(key, len(key_to_id)))
    return ids


def sig(x):
    """Nine significant digits: past single precision, so nothing GSAS-II computed is lost."""
    return float(f"{x:.9g}")


def case_record(label, symbol, cell, rng):
    err, sgdata = G2spc.SpcGroup(symbol)
    if err:
        raise ValueError(f"{symbol}: {G2spc.SGErrors(err)}")
    laue = sgdata["SGLaue"]
    names = G2lat.GenSHCoeffT(laue, "0", ORDER, IfLMN=False)
    full = all_hkls()
    G, g = G2lat.cell2Gmat(cell)
    H_full = np.array(full, dtype=float)
    phi_full, beta_full = G2lat.CrsAng(H_full, cell, sgdata)
    kcl_full = []
    for name in names:
        L, N = eval(name.strip("C"))
        kcl_full.append(np.atleast_1d(G2lat.GetKcl(L, N, laue, phi_full, beta_full)).astype(float))
    orbit_full = orbit_ids(full, sgdata)
    spread = noninvariant(names, kcl_full, orbit_full)

    keep = [i for i, hkl in enumerate(full) if is_friedel_representative(hkl)]
    hkls = [full[i] for i in keep]
    H = H_full[keep]
    kcl = [row[keep] for row in kcl_full]
    d = np.array([G2lat.calc_rDsq2(h, G) ** -0.5 for h in H])
    if np.any(d < WAVELENGTH / 2):
        raise ValueError(f"{label}: a reflection lies beyond 2theta = 180")
    tth = 2.0 * np.degrees(np.arcsin(WAVELENGTH / (2.0 * d)))
    coefficients = {name: float(round(rng.uniform(-0.3, 0.3), 4)) for name in names}

    p, psi = {}, {}
    for inst in ("Bragg", "Debye"):
        controls = {":0:histType": "PXC", ":0:instType": inst, "0:0:SHnames": names}
        parms = {":0:Azimuth": 0.0, ":0:Phi": 0.0, ":0:Chi": 0.0, ":0:Omega": 0.0}
        parms.update({"0:0:" + n: c for n, c in coefficients.items()})
        p_inst, psi_inst = [], []
        for i, h in enumerate(H):
            refl = np.array([h[0], h[1], h[2], 0.0, 0.0, tth[i]])
            value = float(G2stM.SHPOcal(refl, 0, g, "0:0:", ":0:", sgdata, controls, parms))
            gangls = [0.0, 90.0, 0.0, 0.0] if inst == "Bragg" else [0.0, 0.0, 0.0, 0.0]
            s_psi = float(G2lat.SamAng(tth[i] / 2.0, gangls, [0.0, 0.0, 0.0], inst == "Bragg")[0])
            rebuilt = 1.0
            for j, name in enumerate(names):
                L = eval(name.strip("C"))[0]
                ksl = float(np.atleast_1d(G2lat.GetKsl(L, 0, "0", s_psi, 0.0)[0])[0])
                rebuilt += coefficients[name] * G2lat.Lnorm(L) * kcl[j][i] * ksl
            if abs(value - rebuilt) > 1e-5 * max(1.0, abs(value)):
                raise AssertionError(f"{label} {inst} {hkls[i]}: SHPOcal {value} != rebuilt {rebuilt}")
            p_inst.append(sig(value))
            psi_inst.append(sig(s_psi))
        if max(abs(x - 1.0) for x in p_inst) < 1e-3:
            raise AssertionError(f"{label} {inst}: P is 1 everywhere; the harmonics did not load")
        p[inst], psi[inst] = p_inst, psi_inst

    return {
        "label": label,
        "symbol": symbol,
        "laue": laue,
        "unique_axis": sgdata.get("SGUniq", ""),
        "cell": list(cell),
        "names": names,
        "noninvariant": spread,
        "coefficients": coefficients,
        "hkl": [list(h) for h in hkls],
        "orbit": [orbit_full[i] for i in keep],
        "two_theta": [sig(x) for x in tth],
        "phi": [sig(x) for x in np.atleast_1d(phi_full)[keep]],
        "beta": [sig(x) for x in np.atleast_1d(beta_full)[keep]],
        "kcl": [[sig(x) for x in row] for row in kcl],
        "psi": psi,
        "p": p,
    }


def main(out_path):
    G2lat.ptx.pyqlmninit()
    rng = np.random.default_rng(SEED)
    record = {
        "provenance": {
            "generator": "tests/data/make_gsas2_sh_texture.py",
            "gsas2_version": "5.8.4",
            "python": platform.python_version(),
            "platform": f"{platform.system()} {platform.machine()}",
            "date": datetime.date.today().isoformat(),
            "wavelength": WAVELENGTH,
            "order": ORDER,
            "seed": SEED,
            "precision": "GSAS-II's pytexture is single precision: about 1e-7 relative",
        },
        "cases": [case_record(label, symbol, cell, rng) for label, symbol, cell in CASES],
    }
    with open(out_path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(record, fh, separators=(",", ":"))
        fh.write("\n")


if __name__ == "__main__":
    main(sys.argv[1])

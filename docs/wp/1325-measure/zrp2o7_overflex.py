"""WP-1325, the over-flexible arm on the ZrP2O7 ramp: how often is a right form rejected?

    .venv/bin/python docs/wp/1325-measure/zrp2o7_overflex.py \
        > docs/wp/1325-measure/zrp2o7_overflex_results.txt

Run from the repository root (about five minutes, one process; the data from
``python -m tests.local_data durham-topas/zrp2o7``).  Model, protocol and fits
are ``zrp2o7_model.py``'s.

A polynomial of clearly excessive degree is a right form wherever the cell has
no structure on a few-pattern scale, so every rejection of one is a false
alarm on real, serially correlated residuals.  Per leg (heating 303-1173 K,
cooling 1152-304 K, disjoint subsets), one joint fit each:

* ``Q5``: a quintic in the set temperature on Si a, Al2O3 a and Al2O3 c over
  each leg; on ZrP2O7 a a quintic over each leg's high-temperature field
  (553-1173 K, 552-1152 K), since its cell steps at the phase transition
  between them (``zrp2o7_form.py``), and a cubic over each leg's five
  low-field patterns, one term past the quadratic the chain's points chose.
* ``Q4``: the same with quartics.  Its ZrP2O7 low-field laws are Q5's, so
  those two p-values repeat.

``zrp2o7_form.py``'s chain chose degree 1 for Si a and Al2O3 c, 2 for Al2O3 a,
3 for ZrP2O7 a's high field and 2 for its low field, so every law here carries
two to four terms the chain's points do not ask for.

Printed: every reading (the verdict, others-freed; the tied; the joint), each
also without the f² divisor (statistic × f², p from χ²'s tail); the count
rejected at 95 %; and a Kolmogorov-Smirnov test of the verdict p-values
against Uniform(0, 1).  Ten verdicts a fit is a small sample: at n = 10 the
two-sided KS 5 % critical distance is 0.41, so only a gross departure shows,
and the two fits share their data, so their p-values are not independent.
The same forms through the chain's points (weighted χ², the trajectory check)
are printed beside each law.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import numpy as np  # noqa: E402
from scipy.stats import chi2 as chi2_dist  # noqa: E402
from scipy.stats import kstest  # noqa: E402
from zrp2o7_form import TRANSITION_K, wls  # noqa: E402
from zrp2o7_model import TARGETS, load, machine, poly_tie, run_chain, run_joint  # noqa: E402

LOW_FIELD_DEGREE = 3


def ties(data: dict, degree: int) -> list:
    t = data["temps"]
    out = []
    for leg in ("heat", "cool"):
        idx = data[leg]
        lo = [k for k in idx if t[k] < TRANSITION_K]
        hi = [k for k in idx if t[k] > TRANSITION_K]
        out.append(poly_tie(f"zrp_a_lo_{leg}", "zrp_a", LOW_FIELD_DEGREE, lo))
        out.append(poly_tie(f"zrp_a_hi_{leg}", "zrp_a", degree, hi))
        for key in ("si_a", "al_a", "al_c"):
            out.append(poly_tie(f"{key}_{leg}", key, degree, idx))
    return out


def raw(r, f2: float) -> tuple[float, float]:
    """The reading without the f² divisor: statistic × f² and its χ² tail."""
    if r is None or r.statistic is None:
        raise SystemExit(f"a reading was not tested: {r!r}")
    s = r.statistic * f2
    return s, float(chi2_dist.sf(s, r.dof))


def ks(label: str, p: list[float]) -> None:
    p = [x for x in p if np.isfinite(x)]
    res = kstest(p, "uniform")
    print(f"  {label:44} n {len(p):2d}: rejected at 95 % {sum(x < 0.05 for x in p):2d}; "
          f"median p {np.median(p):.3f}; KS D {res.statistic:.3f}, p {res.pvalue:.3g}")


def main() -> None:
    data = load()
    t = data["temps"]
    print("WP-1325, the over-flexible arm on the ZrP2O7 ramp (Durham TOPAS tutorial 9.5)")
    for m in machine():
        print(m)
    print(flush=True)
    t0 = time.perf_counter()
    chain = run_chain(data)
    print(f"chain     {chain['seconds']:.1f} s (load {os.getloadavg()[0]:.1f}); status "
          f"{sorted(set(chain['status']))}", flush=True)
    collected: dict[str, dict[str, list[float]]] = {}
    for name, degree in (("Q5", 5), ("Q4", 4)):
        fit = run_joint(data, chain, ties(data, degree))
        r = fit["result"]
        f2 = fit["inflation"] ** 2
        print()
        print(f"arm {name}: {fit['seconds']:.1f} s (load {os.getloadavg()[0]:.1f}), status {r.status}; "
              f"χ² {fit['chi2']:.1f} with {fit['n_free']} free, χ²r {fit['chi2r']:.4f}, "
              f"f {fit['inflation']:.3f}")
        print(f"  {'law':16} {'deg':>3} {'tested':>6} | {'freed (verdict)':^34} | "
              f"{'freed, no f²':^16} | {'tied':^22} | {'tied, no f²':^11} | chain points")
        got = collected.setdefault(name, {k: [] for k in ("freed", "freed_raw", "tied", "tied_raw",
                                                          "chain")})
        resolved = {x.name: x for x in fit["fit"].parametric}
        for ft in r.parametric_form:
            tie = resolved[ft.tie]
            o, ti = ft.others_freed, ft.tied
            so, po = raw(o, f2)
            st, pt = raw(ti, f2)
            key = next(k for k, p in TARGETS.items() if p == tie.target)
            v, e = chain["traj"][key]
            idx = list(tie.patterns)
            m = len(tie.terms)
            c, _ = wls(t[idx], v[idx], e[idx], m - 1)
            pc = float(chi2_dist.sf(c, len(idx) - m))
            got["freed"].append(o.p_value)
            got["freed_raw"].append(po)
            got["tied"].append(ti.p_value)
            got["tied_raw"].append(pt)
            got["chain"].append(pc)
            print(f"  {ft.tie:16} {m - 1:3d} {ft.n_patterns:3d}/{ft.n_subset:<2d} | "
                  f"{o.statistic:6.1f}/{o.dof:2d} p {o.p_value:6.3f} {'REJECT' if o.rejected else 'keep  '}"
                  f"    | {so:6.1f} p {po:6.3f} | {ti.statistic:6.1f}/{ti.dof:2d} p {ti.p_value:6.3f} | "
                  f"p {pt:6.3f}    | χ²r {c / (len(idx) - m):5.2f} p {pc:6.3f}")
        j = r.parametric_form_joint
        sj, pj = raw(j, f2)
        got.setdefault("joint", []).append(j.p_value)
        got.setdefault("joint_raw", []).append(pj)
        print(f"  {'joint':16} {'':3} {'':6} | {j.statistic:6.1f}/{j.dof:2d} p {j.p_value:6.3f} "
              f"{'REJECT' if j.rejected else 'keep  '}    | {sj:6.1f} p {pj:6.3f} |")
        print(f"  mean statistic per dof, freed: "
              f"{np.mean([x.others_freed.statistic / x.others_freed.dof for x in r.parametric_form]):.3f}"
              f" (f² {f2:.3f}); joint {j.statistic / j.dof:.3f}")
        print(f"  diagnostics {sorted({d.code for d in r.diagnostics})}", flush=True)

    print()
    print("p-values against Uniform(0, 1)")
    for name, got in collected.items():
        ks(f"{name} verdicts (freed)", got["freed"])
        ks(f"{name} freed without f²", got["freed_raw"])
        ks(f"{name} tied", got["tied"])
        ks(f"{name} chain points, same form", got["chain"])
        print(f"  {name + ' joint':44}      p {got['joint'][0]:.3f}; without f² p {got['joint_raw'][0]:.3f}")
    pooled = [p for g in collected.values() for p in g["freed"]]
    pooled_raw = [p for g in collected.values() for p in g["freed_raw"]]
    ks("Q5 and Q4 verdicts pooled (shared data)", pooled)
    ks("Q5 and Q4 pooled, without f²", pooled_raw)
    print()
    for name, got in collected.items():
        print(f"{name} verdict p-values: " + " ".join(f"{p:.3f}" for p in got["freed"]))
        print(f"{name} without f²:       " + " ".join(f"{p:.3f}" for p in got["freed_raw"]))
    print()
    print(f"total     {time.perf_counter() - t0:.0f} s; load at end {os.getloadavg()}")


if __name__ == "__main__":
    main()

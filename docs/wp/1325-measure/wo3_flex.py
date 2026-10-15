"""WP-1325, the form test's false-alarm rate on real residuals: over-flexible equations on WO3.

    .venv/bin/python docs/wp/1325-measure/wo3_flex.py [--size=20] [--degree=4]
        [--windows=all] > docs/wp/1325-measure/wo3_flex_results.txt
    .venv/bin/python docs/wp/1325-measure/wo3_flex.py --size=10 --degree=3
        > docs/wp/1325-measure/wo3_flex10_results.txt

``wo3_pvalues.py`` pools the two runs' readings and reads them three ways.

Run from the repository root after ``wo3_ramp.py``, whose cached chain seeds
every fit.  Model and protocol: ``wo3_ramp.py``'s docstring; joint-fit
windows and seeding: ``wo3_form.joint``.

**The arm.**  The 100 patterns are cut into disjoint windows of ``size``
consecutive patterns, transitions included (WO3's three phases coexist over
the whole ramp, so no window avoids one).  In each window every refinable cell
parameter of every phase, edges and angles alike, fourteen targets, gets a
polynomial of ``degree`` in T over that window alone.  A degree-4 polynomial
over 20 patterns 2 K apart contains any smooth truth to well inside a
pattern's esd, so a rejection is a false alarm unless the cell has real
structure on a few-pattern scale.  ``--windows`` picks windows by index
(comma-separated) when the whole set is too long for one run.

One tied joint fit per window: the windows share no parameter (every phase
path and the instrument are per pattern), so this is the fit with every
window's equations at once, split into independent blocks.  Each fit's form test is
recorded per equation (the others-freed reading, the verdict, and the tied one) and
jointly.  At the end: how many readings reject at 95 %, the p-values
themselves, and a Kolmogorov-Smirnov test of each set against Uniform(0, 1).
A calibrated test gives uniform p-values on true equations; real, serially
correlated residuals are what the f² divisor is meant to absorb.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import numpy as np  # noqa: E402
from scipy.stats import chi2 as chi2_dist  # noqa: E402
from scipy.stats import kstest  # noqa: E402
from wo3_form import JOINT_PLAN, joint, joint_plan, reading  # noqa: E402
from wo3_ramp import SCRATCH, best_chain, load, machine, parse_args, targets  # noqa: E402

import rietx as rx  # noqa: E402


def window_equations(degree: int) -> list[rx.ParametricEquation]:
    """Every cell target as a polynomial of ``degree`` in T over the fit's patterns."""
    terms = [["T"] * j for j in range(degree + 1)]
    return [rx.ParametricEquation(name=key, target=path, basis="polynomial", terms=terms)
            for key, path in targets().items()]


def main() -> None:
    args = parse_args(sys.argv[1:], {"size": 20, "degree": 4, "windows": "all",
                                     "plan": "staged"})
    JOINT_PLAN["kind"] = args["plan"]
    data = load(0, 99)
    chain = best_chain()
    if chain is None:
        raise SystemExit("run wo3_ramp.py first (both directions): this reads its cached chains")
    n, size, degree = len(data["window"]), args["size"], args["degree"]
    windows = [list(range(s, min(s + size, n))) for s in range(0, n, size)]
    picked = (range(len(windows)) if args["windows"] == "all"
              else [int(w) for w in str(args["windows"]).split(",")])

    print("WP-1325 out of sample: over-flexible equations on the WO3 ramp (false-alarm arm)")
    for line in machine():
        print(line)
    print(f"arm       {len(windows)} windows of {size} patterns; degree {degree} in T on all "
          f"{len(targets())} cell targets per window; windows run {list(picked)}")
    print(f"joint     plan {[s.name for s in joint_plan().stages]}; seeds from the better of "
          f"the two chains per pattern; B held at the chain's")
    print(flush=True)

    p_freed, p_tied, p_joint, p_freed_nof, p_joint_nof = [], [], [], [], []
    rows = []
    for w in picked:
        idx = windows[w]
        t = data["temps"][idx]
        one = joint(data, chain, window_equations(degree), subset=idx)
        r = one["result"]
        s = r.statistics
        f2 = one["inflation"] ** 2
        print(f"window {w}: patterns {idx[0]}..{idx[-1]}, T {t.max():.0f}-{t.min():.0f} K; "
              f"{one['seconds']:.1f} s; status {r.status}; iters {one['iters']}; "
              f"Rwp {100 * s.rwp:.3f} %; χ²r {one['chi2r']:.3f}, f {one['inflation']:.3f}",
              flush=True)
        for ft in r.parametric_form or []:
            verdict = {True: "REJECTED", False: "kept", None: "untested"}[ft.rejected]
            print(f"  {ft.equation:8} patterns {ft.n_patterns:3d} of {ft.n_subset:3d}  {verdict}")
            print(f"  {'':8} freed  {reading(ft.others_freed)}")
            print(f"  {'':8} tied   {reading(ft.tied)}")
            for read, bucket in ((ft.others_freed, p_freed), (ft.tied, p_tied)):
                if read is not None and read.p_value is not None:
                    bucket.append(read.p_value)
            o = ft.others_freed
            nof = (None if o is None or o.statistic is None
                   else float(chi2_dist.sf(o.statistic * f2, o.dof)))
            if nof is not None:
                p_freed_nof.append(nof)
            rows.append((w, ft.equation, ft.n_patterns, ft.rejected,
                         None if o is None else o.p_value,
                         None if ft.tied is None else ft.tied.p_value, nof))
        j = r.parametric_form_joint
        print(f"  joint    {reading(j)}", flush=True)
        if j is not None and j.p_value is not None:
            p_joint.append(j.p_value)
            p_joint_nof.append(float(chi2_dist.sf(j.statistic * f2, j.dof)))
        for d in r.diagnostics:
            if d.code == "PARAMETRIC_TARGET_UNSEEN":
                print(f"  diag {d.code}: {d.message[:200]}")
        print(flush=True)

    print("SUMMARY (p over χ²_red·f², the shipped test; 'no f²' divides by χ²_red alone)")
    for label, ps in (("per-equation freed (the verdict)", p_freed), ("per-equation tied", p_tied),
                      ("joint, one per window", p_joint),
                      ("per-equation freed, no f²", p_freed_nof), ("joint, no f²", p_joint_nof)):
        ps = np.array(ps)
        if ps.size == 0:
            print(f"  {label}: none")
            continue
        ks = kstest(ps, "uniform")
        print(f"  {label}: {int((ps < 0.05).sum())} of {ps.size} reject at 95 % "
              f"(expected {0.05 * ps.size:.1f}); KS D {ks.statistic:.3f}, p {ks.pvalue:.3g}; "
              f"median p {np.median(ps):.3f}")
        print("    p: " + " ".join(f"{p:.3g}" for p in sorted(ps)))
    print()
    print("per equation (window, equation, patterns tested, verdict, freed p, tied p, freed p no f²):")
    for w, equation, npat, rej, pf, pt, pn in rows:
        print(f"  {w} {equation:8} {npat:3d} {str(rej):5} "
              f"{'—' if pf is None else f'{pf:.3g}':>8} {'—' if pt is None else f'{pt:.3g}':>8} "
              f"{'—' if pn is None else f'{pn:.3g}':>9}")
    out = SCRATCH / f"flex_p_{size}_{degree}.json"
    out.write_text(json.dumps(dict(freed=p_freed, tied=p_tied, joint=p_joint,
                                   freed_nof=p_freed_nof, joint_nof=p_joint_nof, rows=rows)),
                   encoding="utf-8")


if __name__ == "__main__":
    main()

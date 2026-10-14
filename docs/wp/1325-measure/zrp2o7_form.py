"""WP-1325, the form test out of sample: cell laws on the ZrP2O7 ramp.

    .venv/bin/python docs/wp/1325-measure/zrp2o7_form.py \
        > docs/wp/1325-measure/zrp2o7_form_results.txt

Run from the repository root (2942 s on 2026-10-14 at load averages of 4 to
67, most of it the 18 single-law refits; one process; the data from
``python -m tests.local_data durham-topas/zrp2o7``).  The model, protocol and
fits are ``zrp2o7_model.py``'s.  This script prints, in this order:

1. **The chain** over all 37 patterns (303 K -> 1173 K -> 304 K), warm-started
   in measurement order, and its diagnostics.
2. **The degree of each law, chosen from the chain's points.**  Per target and
   per leg, a weighted least-squares polynomial through the chain's values and
   esds, with a sequential F-test: a term is added while it is significant at
   95 % against the larger fit's residual, and the first that is not stops the
   search.  The declared degree is the larger of the two legs'.  ZrP2O7 a steps
   by 0.02 Å at its phase transition, between 503 and 553 K heating and 552
   and 502 K cooling (the chain's ``SEQUENTIAL_DISCONTINUITY``), so its degree
   is also chosen per phase field, split at ``TRANSITION_K``.
3. **The verdicts, recorded before any comparison.**  Four declared arms,
   each one joint fit seeded from the chain under
   ``SharingMap(per_histogram=["phases.*"])``:

   * ``A``: one law per cell edge over all 37 patterns, heating and cooling as
     one.  ZrP2O7 a's law crosses the transition, so it is a known-wrong form,
     the positive control.
   * ``A'``: as A, with ZrP2O7 a one law per phase field, both legs in each.
   * ``B``: one law per leg per cell edge, on disjoint subsets (eight laws).
   * ``B'``: as B, with ZrP2O7 a one law per leg per phase field (ten laws).

   Per law: patterns tested of the subset, the others-freed reading, the tied
   reading, the verdict; then the joint reading.  Each reading is also given
   without the f² divisor (statistic × f², p from χ²'s tail), since that
   divisor was settled on one ramp.
4. **The comparisons.**  Each law against the chain's trajectory (the same form
   fitted through the chain's points of the subset: χ²_red and p); each arm
   against the refit (the untied joint fit's χ² gain over the arm, as
   ``form_score.py``); each law alone refitted against the untied fit (one
   joint fit per distinct law); A' against B', the nested test of one law per
   leg against one over both; and the leg offset per target, from B''s laws.
   A figure of the trajectories with each arm's laws goes to the scratch
   directory passed as ``--plots=DIR`` (none by default).
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
from scipy.stats import f as f_dist  # noqa: E402
from zrp2o7_model import (  # noqa: E402
    TARGETS,
    load,
    machine,
    poly_tie,
    run_chain,
    run_joint,
)

#: between the last low-field and the first high-field set temperature, on
#: both legs (503/553 K heating, 552/502 K cooling)
TRANSITION_K = 528.0
MAX_DEGREE = 5


# -- the degree, from the chain's points --------------------------------------

def wls(t: np.ndarray, v: np.ndarray, e: np.ndarray, degree: int) -> tuple[float, np.ndarray]:
    """χ² of a weighted polynomial through the points, on u = (T - mid)/half-range."""
    u = (t - 0.5 * (t.min() + t.max())) / (0.5 * (t.max() - t.min()))
    x = np.column_stack([u ** j for j in range(degree + 1)])
    w = 1.0 / e ** 2
    beta = np.linalg.solve(x.T @ (w[:, None] * x), x.T @ (w * v))
    r = v - x @ beta
    return float(r @ (w * r)), beta


def choose_degree(t, v, e) -> tuple[int, list[str]]:
    """The sequential F rule: add a term while it is significant at 95 %."""
    n = len(t)
    cells = []
    chosen = None
    prev = wls(t, v, e, 0)[0]
    for d in range(1, min(MAX_DEGREE, n - 2) + 1):
        c = wls(t, v, e, d)[0]
        dof = n - d - 1
        p = f_dist.sf((prev - c) / (c / dof), 1, dof)
        cells.append(f"d{d} χ²r {c / dof:7.2f} p+ {p:.2g}")
        if chosen is None and p >= 0.05:
            chosen = d - 1
        prev = c
    return (MAX_DEGREE if chosen is None else chosen), cells


def degrees(data: dict, chain: dict) -> dict[str, int]:
    t = data["temps"]
    legs = {"heat": data["heat"], "cool": data["cool"]}
    fields = {"": None, "_lo": lambda T: T < TRANSITION_K, "_hi": lambda T: T > TRANSITION_K}
    out: dict[str, int] = {}
    print("degree    sequential F through the chain's points, per leg; declared = the larger")
    for key in TARGETS:
        for suffix, keep in fields.items():
            if suffix and key != "zrp_a":
                continue
            v, e = chain["traj"][key]
            chosen = []
            for leg, idx in legs.items():
                idx = [k for k in idx if keep is None or keep(t[k])]
                d, cells = choose_degree(t[idx], v[idx], e[idx])
                chosen.append(d)
                print(f"  {key + suffix:9} {leg} n {len(idx):2d}: chosen {d} | " + " | ".join(cells))
            out[key + suffix] = max(chosen)
            print(f"  {key + suffix:9} declared degree {out[key + suffix]}")
    print(flush=True)
    return out


# -- the arms ----------------------------------------------------------------

def arms(data: dict, deg: dict[str, int]) -> dict[str, list]:
    t = data["temps"]
    every = list(range(len(t)))
    heat, cool = data["heat"], data["cool"]

    def field(idx, lo):
        return [k for k in idx if (t[k] < TRANSITION_K) == lo]

    smooth = [k for k in TARGETS if k != "zrp_a"]
    a = [poly_tie(k, k, deg[k], None) for k in TARGETS]
    a2 = ([poly_tie("zrp_a_lo", "zrp_a", deg["zrp_a_lo"], field(every, True)),
           poly_tie("zrp_a_hi", "zrp_a", deg["zrp_a_hi"], field(every, False))]
          + [poly_tie(k, k, deg[k], None) for k in smooth])
    b = [poly_tie(f"{k}_{leg}", k, deg[k], idx)
         for k in TARGETS for leg, idx in (("heat", heat), ("cool", cool))]
    b2 = ([poly_tie(f"zrp_a_{f}_{leg}", "zrp_a", deg[f"zrp_a_{f}"], field(idx, f == "lo"))
           for f in ("lo", "hi") for leg, idx in (("heat", heat), ("cool", cool))]
          + [poly_tie(f"{k}_{leg}", k, deg[k], idx)
             for k in smooth for leg, idx in (("heat", heat), ("cool", cool))])
    return {"A": a, "A'": a2, "B": b, "B'": b2}


def subset_label(tie, n: int) -> str:
    return "all" if tie.patterns is None else f"{len(tie.patterns)} of {n}"


def reading_line(r, f2: float) -> str:
    if r is None or r.statistic is None:
        return "not tested"
    raw = r.statistic * f2
    return (f"{r.statistic:7.1f}/{r.dof:3d} p {r.p_value:6.3g} {'REJECT' if r.rejected else 'keep  '}"
            f" [no f²: {raw:7.1f} p {chi2_dist.sf(raw, r.dof):6.3g}]")


def print_verdicts(name: str, fit: dict, n: int) -> None:
    r = fit["result"]
    f2 = fit["inflation"] ** 2
    print(f"arm {name}: {fit['seconds']:.1f} s (load {os.getloadavg()[0]:.1f}), status {r.status}; "
          f"χ² {fit['chi2']:.1f} with {fit['n_free']} free, χ²r {fit['chi2r']:.4f}, f {fit['inflation']:.3f}")
    ties = {t.name: t for t in fit["fit"].parametric}
    for ft in r.parametric_form or []:
        tie = ties[ft.tie]
        print(f"  {ft.tie:16} {tie.target:16} deg {len(tie.terms) - 1} subset {subset_label(tie, n):9} "
              f"tested {ft.n_patterns}/{ft.n_subset} verdict {'REJECT' if ft.rejected else 'keep'}")
        print(f"  {'':16} freed {reading_line(ft.others_freed, f2)}")
        print(f"  {'':16} tied  {reading_line(ft.tied, f2)}")
    print(f"  {'joint':16} {reading_line(r.parametric_form_joint, f2)}")
    codes = sorted({d.code for d in r.diagnostics})
    print(f"  diagnostics {codes}", flush=True)


# -- the comparisons -----------------------------------------------------------

def trajectory_check(fit: dict, chain: dict, data: dict) -> None:
    """The same form through the chain's points of the subset."""
    t = data["temps"]
    for tie in fit["fit"].parametric:
        key = next(k for k, p in TARGETS.items() if p == tie.target)
        idx = list(range(len(t))) if tie.patterns is None else list(tie.patterns)
        v, e = chain["traj"][key]
        m = len(tie.terms)
        c, _ = wls(t[idx], v[idx], e[idx], m - 1)
        dof = len(idx) - m
        p = chi2_dist.sf(c, dof) if dof > 0 else float("nan")
        verdict = next(ft.rejected for ft in fit["result"].parametric_form if ft.tie == tie.name)
        print(f"  {tie.name:16} chain points χ² {c:8.1f}/{dof:3d} = {c / max(dof, 1):7.2f}, "
              f"p {p:6.3g} | form test {'REJECT' if verdict else 'keep'}")


def refit_line(label: str, tied: dict, untied: dict) -> str:
    dchi2 = tied["chi2"] - untied["chi2"]
    dfree = untied["n_free"] - tied["n_free"]
    denom = untied["chi2r"] * untied["inflation"] ** 2
    stat = dchi2 / denom
    raw = dchi2 / untied["chi2r"]
    return (f"{label:16} refit Δχ² {dchi2:8.1f} for {dfree:3d}: F/f² {stat / dfree:5.2f} "
            f"p {chi2_dist.sf(stat, dfree):6.3g} [no f²: F {raw / dfree:5.2f} p "
            f"{chi2_dist.sf(raw, dfree):6.3g}]; {tied['seconds']:.0f} s {tied['result'].status}")


def leg_offsets(fit: dict, data: dict) -> None:
    """Cooling's law minus heating's at common temperatures, in Å and in K."""
    r = fit["result"]
    names = [t.name for t in fit["fit"].parametric]
    for name in names:
        if not name.endswith("_heat"):
            continue
        other = name.replace("_heat", "_cool")
        ties = {t.name: t for t in fit["fit"].parametric}
        lo = max(min(data["temps"][k] for k in ties[n].patterns) for n in (name, other))
        hi = min(max(data["temps"][k] for k in ties[n].patterns) for n in (name, other))
        cells = []
        for T in np.linspace(lo, hi, 4):
            vh = r.parametric_value(name, {"T": float(T)})
            vc = r.parametric_value(other, {"T": float(T)})
            slope = (r.parametric_value(name, {"T": float(T) + 1}).value
                     - r.parametric_value(name, {"T": float(T) - 1}).value) / 2
            d = vc.value - vh.value
            esd = float(np.hypot(vh.esd, vc.esd))
            cells.append(f"{T:5.0f} K: {1e4 * d:+6.2f}({1e4 * esd:.2f})e-4 Å = {d / slope:+6.1f}"
                         f"({esd / abs(slope):.1f}) K")
        print(f"  {name[:-5]:10} cool - heat | " + " | ".join(cells))


def plot(path: Path, data: dict, chain: dict, fits: dict) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    t = data["temps"]
    heat, cool = data["heat"], data["cool"]
    fig, axs = plt.subplots(2, 4, figsize=(17, 7), sharex=True,
                            gridspec_kw={"height_ratios": [2, 1]})
    for j, (key, target) in enumerate(TARGETS.items()):
        v, e = chain["traj"][key]
        top, bot = axs[0, j], axs[1, j]
        top.errorbar(t[heat], v[heat], e[heat], fmt="o", ms=3, color="C3", label="heating (chain)")
        top.errorbar(t[cool], v[cool], e[cool], fmt="s", ms=3, color="C0", mfc="none",
                     label="cooling (chain)")
        for arm, style in (("A", ":"), ("A'", "-"), ("B'", "--")):
            r = fits[arm]["result"]
            for tie in fits[arm]["fit"].parametric:
                if tie.target != target:
                    continue
                idx = range(len(t)) if tie.patterns is None else tie.patterns
                tt = np.linspace(min(t[k] for k in idx), max(t[k] for k in idx), 200)
                yy = [r.parametric_value(tie.name, {"T": float(x)}).value for x in tt]
                color = "C3" if tie.name.endswith("_heat") else "C0" if tie.name.endswith("_cool") else "k"
                top.plot(tt, yy, style, color=color, lw=1)
                if arm == "A'":
                    res = [(v[k] - r.parametric_value(tie.name, {"T": float(t[k])}).value) / e[k]
                           for k in idx]
                    kk = list(idx)
                    hk = [i for i, k in enumerate(kk) if k in heat]
                    ck = [i for i, k in enumerate(kk) if k in cool]
                    bot.plot(t[[kk[i] for i in hk]], [res[i] for i in hk], "o", ms=3, color="C3")
                    bot.plot(t[[kk[i] for i in ck]], [res[i] for i in ck], "s", ms=3, color="C0",
                             mfc="none")
        bot.axhline(0, color="0.6", lw=0.8)
        top.set_title(f"{key} ({target})")
        bot.set_xlabel("set T (K)")
    axs[0, 0].set_ylabel("Å")
    axs[1, 0].set_ylabel("(chain - law A') / esd")
    axs[0, 0].legend(fontsize=7)
    fig.suptitle("chain points; laws A (dotted), A' (solid), B' (dashed: red heat, blue cool)")
    fig.tight_layout()
    fig.savefig(path, dpi=90)


def main() -> None:
    plots = next((Path(a.split("=", 1)[1]) for a in sys.argv[1:] if a.startswith("--plots=")), None)
    data = load()
    n = len(data["temps"])
    print("WP-1325, the form test out of sample: cell laws on the ZrP2O7 ramp "
          "(Durham TOPAS tutorial 9.5)")
    for m in machine():
        print(m)
    print(f"window    37 ranges, TOPAS's 1..871 subset (0-based scans {data['proto']['scans'][:3]}…); "
          f"heating {len(data['heat'])} patterns 303-1173 K, cooling {len(data['cool'])} 1152-304 K; "
          f"2θ {data['proto']['limits']}")
    print("model     ZrP2O7 Pa-3, silicon Fd-3m:1, Al2O3 R-3c:H; per pattern: 3 scales, 18-term "
          "background, displacement, 4 cell edges, 12 broadening terms, 7 Biso, P x")
    print(flush=True)

    t0 = time.perf_counter()
    chain = run_chain(data)
    rwp = chain["rwp"]
    print(f"chain     {chain['seconds']:.1f} s (load {os.getloadavg()[0]:.1f}); status "
          f"{sorted(set(chain['status']))}; Rwp {100 * min(rwp):.2f}-{100 * max(rwp):.2f} %; "
          f"Σχ² {chain['chi2']:.1f} with {chain['n_free']} free over {chain['n_points']} points")
    for d in chain["result"].diagnostics:
        if d.code in ("SEQUENTIAL_DISCONTINUITY", "SEQUENTIAL_UNRECOVERED"):
            print(f"  {d.code}: {d.message}")
    free = sorted({e.statistics.n_free_parameters for e in chain["result"].entries})
    print(f"  free per pattern {free}: no phase held in any pattern")
    print(flush=True)

    deg = degrees(data, chain)
    untied = run_joint(data, chain, [])
    print(f"untied    {untied['seconds']:.1f} s (load {os.getloadavg()[0]:.1f}); status "
          f"{untied['result'].status}; Rwp {100 * untied['rwp']:.3f} % (TOPAS 31.56 %); "
          f"χ² {untied['chi2']:.1f} with {untied['n_free']} free; χ²r {untied['chi2r']:.4f}, "
          f"f {untied['inflation']:.3f}")
    print(flush=True)

    print("=" * 100)
    print("VERDICTS (recorded before any comparison)")
    print("=" * 100)
    fits = {}
    for name, ties in arms(data, deg).items():
        fits[name] = run_joint(data, chain, ties)
        print_verdicts(name, fits[name], n)
        print(flush=True)

    print("=" * 100)
    print("COMPARISONS")
    print("=" * 100)
    print("against the chain's trajectory: the same form through the chain's points of the subset")
    for name, fit in fits.items():
        print(f" arm {name}")
        trajectory_check(fit, chain, data)
    print(flush=True)

    print("against the refit: the untied joint fit's χ² gain over each arm, over its χ²r·f²")
    for name, fit in fits.items():
        print("  " + refit_line(f"arm {name}", fit, untied))
    a2, b2 = fits["A'"], fits["B'"]
    dchi2 = a2["chi2"] - b2["chi2"]
    dfree = b2["n_free"] - a2["n_free"]
    stat = dchi2 / (b2["chi2r"] * b2["inflation"] ** 2)
    print(f"  A' against B' (one law per leg nests one law over both): Δχ² {dchi2:.1f} for {dfree}, "
          f"/χ²r·f² {stat:.1f}, p {chi2_dist.sf(stat, dfree):.3g} "
          f"[no f²: p {chi2_dist.sf(dchi2 / b2['chi2r'], dfree):.3g}]")
    print(flush=True)

    print("each law alone, refitted against the untied fit (one joint fit per distinct law), beside "
          "the freed reading's gain")
    alone: dict[tuple, dict] = {}
    for name, fit in fits.items():
        print(f" arm {name}")
        f2arm = fit["chi2r"] * fit["inflation"] ** 2
        for tie in fit["fit"].parametric:
            spec = (tie.name, tie.target, len(tie.terms), tuple(tie.patterns or ()))
            if spec not in alone:
                key = next(k for k, p in TARGETS.items() if p == tie.target)
                alone[spec] = run_joint(data, chain, [poly_tie(tie.name, key, len(tie.terms) - 1,
                                                              tie.patterns)])
            one = alone[spec]
            ft = next(x for x in fit["result"].parametric_form if x.tie == tie.name)
            o = ft.others_freed
            gain = o.statistic * f2arm if o is not None and o.statistic is not None else float("nan")
            dchi2 = one["chi2"] - untied["chi2"]
            print(f"  {refit_line(tie.name, one, untied)} | freed gain {gain:8.1f} "
                  f"({gain / dchi2 if dchi2 else float('nan'):5.2f} of the refit's)", flush=True)
    print()

    print("leg offsets from arm B''s laws (cooling minus heating, esds combined as independent; "
          "in K through the heating law's slope)")
    leg_offsets(b2, data)
    print()
    print(f"total     {time.perf_counter() - t0:.0f} s; load at end {os.getloadavg()}")

    print()
    print("chain trajectories (T, value, esd):")
    for key in TARGETS:
        v, e = chain["traj"][key]
        print(f"  {key}: " + " ".join(f"{T:.0f}:{x:.5f}({s:.5f})"
                                       for T, x, s in zip(data["temps"], v, e)))
    if plots is not None:
        plots.mkdir(parents=True, exist_ok=True)
        plot(plots / "zrp2o7_laws.png", data, chain, fits)


if __name__ == "__main__":
    main()

"""WP-1325, the form test out of sample: TOPAS's own laws on the WO3 ramp.

    .venv/bin/python docs/wp/1325-measure/wo3_form.py [--first=0] [--last=99]
        [--each=] [--plan=staged] > docs/wp/1325-measure/wo3_form_results.txt

Run from the repository root after ``wo3_ramp.py`` both ways (forward, and
``--direction=backward --name=wo3_chain_back``): every joint fit starts from
each pattern's better chain answer (``wo3_ramp.best_chain``).  Model, protocol
and departures from TOPAS: ``wo3_ramp.py``'s docstring.  ``--first``/``--last``
pick a window of the 100 patterns (0-based, inclusive).

**The laws** are ``parametric_05.inp``'s, one per refinable cell parameter of
each phase, fourteen in all, each over every pattern of the window:

* each cell edge, a₀ + g/(exp(θ_E/T) − 1), all nine with TOPAS's refined
  Einstein temperature θ_E = 125.370423 K **held**, since no linear basis
  refines it (WP-1964).  So each is a ``design`` law with the two columns
  1 and 1/(exp(θ_E/T) − 1), coefficients a₀ and g in Å;
* each angle, a quadratic in T (``polynomial``, rietx's centred form; TOPAS
  writes it c₀(1 + c₁T + c₂T²), the same space).

**A joint fit** shares nothing across patterns
(``SharingMap(per_histogram=["phases.*"])``, the instrument per pattern by
default), holds B at the chain's value, and widens every cell window to
TOPAS's own per-pattern ones (``widened``).  ``--plan=single`` frees
everything in one stage from the chain's answer; ``staged`` runs the chain's
stages without B.

**The order of the output is the measurement's protocol.**  The form test's
verdicts are printed first, off the all-laws fit alone (per law the freed
reading, the tied reading and the verdict; then the joint reading).  Only
after them come the comparisons: the all-laws fit against the untied joint fit
as a nested refit, each law against the chain's trajectory (the weighted χ²_red
of the chain's points about the law's curve), and with ``--each=a,b`` (or
``all``) those laws each alone refitted against the untied fit, whose χ² gain
over the untied fit's χ²_red·f² is the refit the freed reading predicts
(``form_freed.py``).  A figure of every trajectory with its law goes to the
scratch directory.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import numpy as np  # noqa: E402
from scipy.stats import chi2 as chi2_dist  # noqa: E402
from wo3_ramp import (  # noqa: E402
    ANGLE_WINDOWS,
    PHASES,
    SCRATCH,
    _total_chi2,
    best_chain,
    einstein,
    load,
    machine,
    parse_args,
    plan,
    targets,
    topas_law,
)

import rietx as rx  # noqa: E402
from rietx.params.multi import SharingMap  # noqa: E402
from rietx.strategy.staged import RefinementPlan, Stage  # noqa: E402

TOPAS_RWP = "TOPAS: 12.87 % for 184 parameters over 11 patterns, 12.81 % for 1163 over 100"
#: a joint fit's cell windows: TOPAS's per-pattern ``tol`` of 1.1 on an edge,
#: and its angle windows widened by 2° (``wo3_ramp.ANGLE_WINDOWS``)
EDGE_TOL, ANGLE_PAD = 1.1, 2.0
#: which joint plan ``joint`` runs; ``main`` sets it from ``--plan``
JOINT_PLAN = {"kind": "staged"}


def joint_plan() -> RefinementPlan:
    if JOINT_PLAN["kind"] == "staged":
        return plan(False)
    return RefinementPlan(stages=[Stage(name="all", max_iter=200, turn_on=[
        g for s in plan(False).stages for g in s.turn_on])])


def topas_laws(temps: np.ndarray, theta: float, keys: list[str] | None = None
               ) -> list[rx.ParametricTie]:
    """``parametric_05.inp``'s fourteen laws over every pattern of a fit."""
    out = []
    for key, path in targets().items():
        if keys is not None and key not in keys:
            continue
        name = key.split("_", 1)[1]
        if name in "abc":
            out.append(rx.ParametricTie(
                name=key, target=path, basis="design",
                design=[[1.0, einstein(float(t), theta)] for t in temps]))
        else:
            out.append(rx.ParametricTie(
                name=key, target=path, basis="polynomial", terms=[[], ["T"], ["T", "T"]]))
    return out


def widened(structures: list[rx.Structure]) -> list[rx.Structure]:
    """The chain's models with every cell window widened, for a joint fit.

    A law's coefficients are free columns whose box cannot keep a tied target
    inside the target's own bounds, and a target pushed outside them is
    refused at write-back (``ParameterTable.apply_to_models``).  The chain's
    ±1.5 % sat binding on weak-phase cells, so a law seeded through those
    points broke it on the first trial.  Tied and untied fits take the same
    wider windows, so the nested comparison stays nested.
    """
    out = []
    for s in structures:
        s = s.model_copy(deep=True)
        for i, phase in enumerate(s.phases):
            for name in PHASES[i][2]:
                p = getattr(phase.cell, name)
                if name in "abc":
                    p.min, p.max = p.value / EDGE_TOL, p.value * EDGE_TOL
                else:
                    lo, hi = ANGLE_WINDOWS[(i, name)]
                    p.min, p.max = lo - ANGLE_PAD, hi + ANGLE_PAD
        out.append(s)
    return out


def joint(data: dict, chain: dict, ties: list[rx.ParametricTie],
          subset: list[int] | None = None) -> dict:
    """One joint fit over ``subset`` of the 100 patterns, seeded from the chain."""
    idx = list(range(len(data["patterns"]))) if subset is None else subset
    t0 = time.perf_counter()
    fit = rx.MultiHistogramRefinement(
        widened([chain["structures"][k] for k in idx]),
        [chain["instruments"][k] for k in idx],
        sharing=SharingMap(per_histogram=["phases.*"]),
        coordinates=rx.CoordinateTable(columns={"T": data["temps"][idx].tolist()},
                                       units={"T": "K"}),
        parametric=ties or None)
    result = fit.fit([data["patterns"][k] for k in idx], plan=joint_plan(),
                     two_theta_limits=data["proto"]["limits"])
    s = result.statistics
    return dict(fit=fit, result=result, seconds=time.perf_counter() - t0,
                chi2=_total_chi2(s), n_free=s.n_free_parameters, chi2r=s.chi2,
                inflation=s.esd_inflation,
                iters=[st.n_iterations for st in result.stages])


def reading(r) -> str:
    if r is None:
        return "—"
    if r.statistic is None:
        return f"dof {r.dof}, no statistic"
    verdict = "REJECT" if r.rejected else "keep"
    return (f"{r.statistic:8.1f} / {r.dof:3d} dof (cut {r.cut:6.1f}, {r.statistic / r.dof:5.2f}/dir, "
            f"p {r.p_value:.3g}) {verdict}")


def print_verdicts(result) -> None:
    print("FORM TEST VERDICTS (recorded before any comparison)")
    for t in result.parametric_form or []:
        verdict = {True: "REJECTED", False: "kept", None: "untested"}[t.rejected]
        print(f"  {t.tie:8} {t.target:22} patterns {t.n_patterns:3d} of {t.n_subset:3d}  verdict {verdict}")
        print(f"  {'':8} freed  {reading(t.others_freed)}")
        print(f"  {'':8} tied   {reading(t.tied)}")
    print(f"  joint    {reading(result.parametric_form_joint)}")
    for d in result.diagnostics:
        if d.code.startswith("PARAMETRIC"):
            print(f"  diag {d.code}: {d.message[:240]}")
    print(flush=True)


def nested(label: str, tied: dict, untied: dict) -> str:
    dchi2 = tied["chi2"] - untied["chi2"]
    dfree = untied["n_free"] - tied["n_free"]
    stat = dchi2 / (untied["chi2r"] * untied["inflation"] ** 2)
    return (f"{label:10} {tied['seconds']:7.1f} s {tied['result'].status:9} iters {tied['iters']} "
            f"Rwp {100 * tied['result'].statistics.rwp:.3f} % | refit Δχ² {dchi2:9.1f} for "
            f"{dfree:4d} fewer free; F/f² {stat / max(dfree, 1):5.2f}, "
            f"p {chi2_dist.sf(stat, max(dfree, 1)):.3g}")


def law_curve(result, key: str, temps: np.ndarray, theta: float) -> tuple[np.ndarray, np.ndarray]:
    vals, esds = [], []
    for t in temps:
        if key.split("_", 1)[1] in "abc":
            v = result.parametric_value(key, row=[1.0, einstein(float(t), theta)])
        else:
            v = result.parametric_value(key, {"T": float(t)})
        vals.append(v.value)
        esds.append(v.esd if v.esd is not None else np.nan)
    return np.array(vals), np.array(esds)


def per_pattern(result, path: str, n: int) -> tuple[np.ndarray, np.ndarray]:
    v, e = np.full(n, np.nan), np.full(n, np.nan)
    rows = {p.path: p for p in result.parameters}
    for k in range(n):
        p = rows.get(f"hist.{k}.{path}")
        if p is not None and p.stderr is not None:
            v[k], e[k] = p.value, p.stderr
    return v, e


def figure(path: Path, proto: dict, temps: np.ndarray, traj: dict, untied, tied,
           theta: float, title: str) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    keys = list(targets())
    fig, axes = plt.subplots(4, 4, figsize=(15, 12))
    for ax, key in zip(axes.flat, keys):
        v, e = traj[key]
        ax.errorbar(temps, v, yerr=e, fmt="o", ms=2.5, lw=0.6, color="black", label="chain")
        if untied is not None:
            uv, ue = per_pattern(untied, targets()[key], len(temps))
            ax.errorbar(temps + 0.6, uv, yerr=ue, fmt="s", ms=2, lw=0.5, color="tab:blue",
                        alpha=0.6, label="untied joint")
        lv, le = law_curve(tied, key, temps, theta)
        ax.plot(temps, lv, "-", color="tab:orange", lw=1.4, label="law (joint)")
        ax.fill_between(temps, lv - le, lv + le, color="tab:orange", alpha=0.3, lw=0)
        i = int(targets()[key].split(".")[1])
        name = key.split("_", 1)[1]
        ax.plot(temps, [topas_law(proto, i, name, float(t)) for t in temps], "--",
                color="grey", lw=1, label="TOPAS law")
        form = next(t for t in tied.parametric_form if t.tie == key)
        fr = form.others_freed or form.tied
        tag = "untested" if fr is None or fr.statistic is None else (
            f"freed p {fr.p_value:.2g} {'REJECT' if fr.rejected else 'keep'}")
        ax.set_title(f"{PHASES[i][1]} {name}: {tag}", fontsize=9)
        finite = v[np.isfinite(v)]
        if finite.size:
            lo, hi = np.nanmin(np.r_[finite, lv]), np.nanmax(np.r_[finite, lv])
            pad = 0.1 * (hi - lo + 1e-9)
            ax.set_ylim(lo - pad, hi + pad)
        ax.tick_params(labelsize=7)
    axes.flat[0].legend(fontsize=6)
    for ax in list(axes.flat)[len(keys):]:
        ax.axis("off")
    fig.suptitle(title, fontsize=11)
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)


def main() -> None:
    args = parse_args(sys.argv[1:], {"first": 0, "last": 99, "each": "", "plan": "staged"})
    JOINT_PLAN["kind"] = args["plan"]
    data = load(0, 99)
    chain = best_chain()
    if chain is None:
        raise SystemExit("run wo3_ramp.py first (both directions): this reads its cached chains")
    idx = list(range(args["first"], args["last"] + 1))
    temps = data["temps"][idx]
    traj = {k: (v[idx], e[idx]) for k, (v, e) in chain["traj"].items()}
    n = len(idx)
    theta = data["proto"]["theta"]
    print("WP-1325 out of sample: TOPAS's laws on the WO3 ramp, the form test first")
    for line in machine():
        print(line)
    print(f"window    patterns {idx[0]}..{idx[-1]} (0-based), {n} patterns, "
          f"T {temps.max():.0f} -> {temps.min():.0f} K")
    src = [chain["source"][k] for k in idx]
    print(f"seeds     per pattern the better chain: {src.count('wo3_chain')} forward, "
          f"{src.count('wo3_chain_back')} backward; Σχ² {sum(chain['chi2'][k] for k in idx):.1f}; "
          f"Rwp {100 * min(chain['rwp'][k] for k in idx):.2f}-"
          f"{100 * max(chain['rwp'][k] for k in idx):.2f} %")
    print(f"laws      9 edges a0 + g/(exp(θ/T)-1), θ {theta:.6f} K held; 5 angles quadratic in T; "
          f"joint plan {[s.name for s in joint_plan().stages]}, B held at the chain's")
    print(f"anchor    {TOPAS_RWP}")
    print(flush=True)

    tied = joint(data, chain, topas_laws(temps, theta), subset=idx)
    r = tied["result"]
    s = r.statistics
    print(f"all laws  {tied['seconds']:.1f} s; status {r.status}; iters {tied['iters']}; "
          f"Rwp {100 * s.rwp:.3f} %; χ² {tied['chi2']:.1f} with {tied['n_free']} free; "
          f"χ²r {tied['chi2r']:.3f}, f {tied['inflation']:.3f}", flush=True)
    print()
    print_verdicts(r)

    print("VISIBILITY, from the seeding chain: per target, the patterns whose fit held the "
          "phase unseen, and those whose cell sat on the chain's window (±1.5 % edge, TOPAS's "
          "angle window)")
    for key, path in targets().items():
        i, name = int(path.split(".")[1]), key.split("_", 1)[1]
        unseen = [int(temps[j]) for j, k in enumerate(idx) if i in chain["unseen"][k]]
        on = []
        for j, k in enumerate(idx):
            p = getattr(chain["structures"][k].phases[i].cell, name)
            if np.isclose(p.value, p.min, atol=1e-6) or np.isclose(p.value, p.max, atol=1e-6):
                on.append(int(temps[j]))
        print(f"  {key:8} unseen {len(unseen):3d}; on a bound {len(on):3d}"
              + (f" at T {on}" if on else ""))
    print()

    print("COMPARISONS")
    untied = joint(data, chain, [], subset=idx)
    u = untied["result"]
    print(f"untied    {untied['seconds']:.1f} s; status {u.status}; iters {untied['iters']}; "
          f"Rwp {100 * u.statistics.rwp:.3f} %; χ² {untied['chi2']:.1f} with "
          f"{untied['n_free']} free; χ²r {untied['chi2r']:.3f}, f {untied['inflation']:.3f}")
    print(nested("all laws", tied, untied))
    j = r.parametric_form_joint
    if j is not None and j.statistic is not None:
        own = tied["chi2r"] * tied["inflation"] ** 2
        print(f"          joint reading's gain {j.statistic * own:9.1f} for {j.dof} "
              f"(refit Δχ² {tied['chi2'] - untied['chi2']:.1f} for "
              f"{untied['n_free'] - tied['n_free']})")
    print("diagnostics, all laws:", sorted({d.code for d in r.diagnostics}))
    print("diagnostics, untied:  ", sorted({d.code for d in u.diagnostics}))
    held = sorted({p for st in r.stages for p in st.held})
    print(f"held in the all-laws fit ({len(held)}):", held[:10], "…" if len(held) > 10 else "")
    print()

    print("coefficients (all-laws fit) beside TOPAS's")
    prm = data["proto"]["prm"]
    for c in r.parametric or []:
        esd = c.esd if c.esd is not None else float("nan")
        print(f"  {c.tie:8} {c.term:6} {c.value:14.7g} ± {esd:.3g}")
    print("  TOPAS edges (a0 + g): " + ", ".join(
        f"{k}: {prm['zero_' + k[0] + k[2]]:.5f} + {prm['grad_' + k[0] + k[2]]:.5f}"
        for k in targets() if k.split('_', 1)[1] in 'abc'))
    print()

    print("each law against the chain's trajectory: weighted χ²_red of the chain points about "
          "the law's curve (points with an esd only)")
    for key in targets():
        v, e = traj[key]
        lv, _ = law_curve(r, key, temps, theta)
        ok = np.isfinite(v) & np.isfinite(e) & (e > 0)
        z = (v[ok] - lv[ok]) / e[ok]
        m = 2 if key.split("_", 1)[1] in "abc" else 3
        dof = max(int(ok.sum()) - m, 1)
        print(f"  {key:8} n {int(ok.sum()):3d}  χ²_red {float(z @ z) / dof:8.2f}  "
              f"max |z| {np.max(np.abs(z)) if z.size else float('nan'):6.2f}  "
              f"mean chain esd {np.mean(e[ok]) if ok.any() else float('nan'):.5f}")
    print(flush=True)

    stem = f"form_trajectories_{idx[0]}_{idx[-1]}.png"
    figure(SCRATCH / stem, data["proto"], temps, traj, u, r, theta,
           f"WO3, patterns {idx[0]}-{idx[-1]}: chain (black), untied joint (blue), "
           f"TOPAS-form law (orange), TOPAS's law (grey dashed)")
    print(f"figure    {stem} in the scratch directory")

    keys = (list(targets()) if args["each"] == "all"
            else [k for k in str(args["each"]).split(",") if k])
    if keys:
        print()
        print("each law alone, refitted, against the untied fit (the freed reading's refit)")
        freed = {t.tie: t.others_freed for t in r.parametric_form}
        for key in keys:
            one = joint(data, chain, topas_laws(temps, theta, keys=[key]), subset=idx)
            t1 = one["result"].parametric_form[0]
            print(nested(key, one, untied) + f" | alone {reading(t1.tied)} | "
                  f"all-laws freed {reading(freed.get(key))}", flush=True)


if __name__ == "__main__":
    main()

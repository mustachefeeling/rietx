"""WP-1325: does a score test at the tied answer give the refit's verdict?

The nested test of § Measured on real data refits the joint model with no law
and divides the χ² it gains by χ²_red·f².  A score test reads the same gain
off the tied answer alone: each subset pattern's own target column is
appended to its block, and one linear least-squares step with every other
column refitted says how much χ² freeing the targets would buy
(``optimize.blocked.added_columns_gain``).  It needs the tied fit's Jacobian
and residual only, so it costs no refit.

Run on ``real_ramp.py``'s window and protocol.  For every law of that script
(the three targets together, each alone, the cubic quadratic), it prints the
score's gain beside the refit's Δχ², and both statistics: the refit's F/f²,
over the untied fit's χ²_red and f, and the score's, over the tied fit's
χ²_red and f, the textbook score test's restricted estimate.  Columns the
tied fit left on a bound are held out of both sides of the score, as a refit
holds them; the gain with them left free is printed beside it.

``python docs/wp/1325-measure/form_score.py`` (about ten minutes, one
process; the data from ``python -m tests.local_data``).
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import numpy as np  # noqa: E402
from real_ramp import (  # noqa: E402
    DATASET,
    INP,
    RAW,
    TARGETS,
    _total_chi2,
    instrument,
    machine,
    plan,
    protocol,
    run_chain,
    structure,
)
from scipy.stats import chi2 as chi2_dist  # noqa: E402

import rietx as rx  # noqa: E402
from rietx.multi import _PHASE_PREFIX, _joint_unsupported_phases  # noqa: E402
from rietx.optimize import least_squares as lsq  # noqa: E402
from rietx.optimize.blocked import added_columns_gain  # noqa: E402
from rietx.optimize.statistics import berar_lelann_factor  # noqa: E402
from rietx.params.multi import SharingMap  # noqa: E402
from rietx.params.parametric import target_columns  # noqa: E402
from tests import local_data  # noqa: E402


def joint(patterns, chain, temps, limits, laws: dict[str, int]) -> dict:
    """One joint fit, ``laws`` mapping a target key to its polynomial degree."""
    series = chain["series"]
    ties = [rx.ParametricTie(name=key, target=TARGETS[key], basis="polynomial",
                             terms=[["T"] * j for j in range(degree + 1)])
            for key, degree in laws.items()]
    t0 = time.perf_counter()
    fit = rx.MultiHistogramRefinement(
        list(series.fitted_structures), list(series.fitted_instruments),
        sharing=SharingMap(per_histogram=["phases.*"]),
        coordinates=rx.CoordinateTable(columns={"T": list(temps)}, units={"T": "K"}),
        parametric=ties or None)
    result = fit.fit(patterns, plan=plan(), two_theta_limits=limits)
    s = result.statistics
    return dict(fit=fit, result=result, seconds=time.perf_counter() - t0,
                chi2=_total_chi2(s), n_free=s.n_free_parameters, chi2r=s.chi2,
                inflation=s.esd_inflation)


def score(fit, names: list[str] | None) -> dict:
    """The score test at ``fit``'s answer, freeing the targets of ``names``
    (every law when ``None``) per pattern."""
    mt = fit.mtable
    t0 = time.perf_counter()
    residual, jacobian, n_data = lsq._multi_closures(fit._models, mt, layout="blocked")
    x = mt.x0()
    r, bj = residual(x), jacobian(x)
    t_eval = time.perf_counter() - t0
    extra: list[list[np.ndarray]] = [[] for _ in range(bj.n_blocks)]
    absent = _joint_unsupported_phases(fit._models, mt)
    drop: list[int] = []
    for res in mt.parametric:
        if names is not None and res.name not in names:
            continue
        # where an untied fit would hold the target: its phase unseen there
        m = _PHASE_PREFIX.match(res.target)
        skip = (frozenset() if m is None or res.target.endswith(".scale")
                else frozenset(k for k in res.patterns if int(m.group(1)) in absent[k]))
        cols = target_columns(res, bj, mt.free_paths, skip)
        for h, c in enumerate(cols):
            if c is not None:
                extra[h].append(c)
        drop += [mt.free_paths.index(p) for p in res.paths]
    stacked = [np.hstack(e) if e else None for e in extra]
    # the columns the LM driver left on a bound: it lands exactly on one
    lo, hi = mt.bounds()
    active = np.flatnonzero((x <= lo) | (x >= hi))
    t1 = time.perf_counter()
    gain, rank = added_columns_gain(bj, r, stacked, drop, active)
    t_score = time.perf_counter() - t1
    free_gain, free_rank = added_columns_gain(bj, r, stacked, drop)
    rd = r[:n_data]
    chi2r = float(rd @ rd) / (n_data - len(x))
    f = berar_lelann_factor(rd)
    return dict(gain=gain, rank=rank, t_eval=t_eval, t_score=t_score,
                stat=gain / (chi2r * f ** 2), free_gain=free_gain, free_rank=free_rank,
                n_active=len(active), f=f, chi2r=chi2r)


def line(label: str, tied: dict, untied: dict, sc: dict) -> None:
    dchi2 = tied["chi2"] - untied["chi2"]
    dfree = untied["n_free"] - tied["n_free"]
    nested = dchi2 / dfree / untied["chi2r"] / untied["inflation"] ** 2
    k = sc["rank"]
    print(f"{label:12} {tied['seconds']:6.1f} s {tied['result'].status:9} | refit Δχ² {dchi2:8.1f} "
          f"for {dfree:3d}, F/f² {nested:5.2f} p {chi2_dist.sf(nested * dfree, dfree):.3g} | "
          f"score gain {sc['gain']:8.1f} for {k:3d} ({sc['gain'] / dchi2:5.3f} of refit), "
          f"F/f² {sc['stat'] / k:5.2f} p {chi2_dist.sf(sc['stat'], k):.3g} | "
          f"{sc['n_active']} on a bound; left free, gain {sc['free_gain']:8.1f} for "
          f"{sc['free_rank']} | f {sc['f']:.3f}, untied {untied['inflation']:.3f} | "
          f"J {sc['t_eval']:.2f} s, score {sc['t_score']:.2f} s", flush=True)


def main() -> None:
    where = local_data.dataset(DATASET)
    if where is None:
        raise SystemExit(f"{DATASET} is not on this machine: python -m tests.local_data {DATASET}")
    text = (where / INP).read_text(encoding="utf-8", errors="replace")
    proto = protocol(text)
    radius = rx.read_topas_inp(where / INP).goniometer_radius_mm or 217.5
    window = range(35, 68)
    temps = [proto["temps"][k] for k in window]
    limits = proto["limits"]
    patterns = [rx.read_pattern(where / RAW, scan=k) for k in window]
    start = (structure(where / INP), instrument(proto, radius))

    print("WP-1325: the score test against the refit, on the ZrMo2O8 ramp")
    for m in machine():
        print(m)
    print(f"window    ranges 35..67 (0-based), {len(window)} patterns; level for p: χ² tail")
    print(flush=True)
    chain = run_chain(patterns, start, temps, limits)
    print(f"chain     {chain['seconds']:.1f} s", flush=True)
    untied = joint(patterns, chain, temps, limits, {})
    print(f"untied    {untied['seconds']:.1f} s; χ² {untied['chi2']:.1f} with "
          f"{untied['n_free']} free; χ²r {untied['chi2r']:.3f}, f {untied['inflation']:.3f}",
          flush=True)

    every = joint(patterns, chain, temps, limits, dict.fromkeys(TARGETS, 1))
    line("all three", every, untied, score(every["fit"], None))
    # each law scored at the all-three answer, the other two still tied: what
    # a fit with several laws would report per law
    for key in TARGETS:
        sc = score(every["fit"], [key])
        print(f"  {key:10} at the all-three answer: score gain {sc['gain']:8.1f} for "
              f"{sc['rank']}, F/f² {sc['stat'] / sc['rank']:.2f} "
              f"p {chi2_dist.sf(sc['stat'], sc['rank']):.3g}", flush=True)
    for key in TARGETS:
        one = joint(patterns, chain, temps, limits, {key: 1})
        line(key, one, untied, score(one["fit"], None))
    quad = joint(patterns, chain, temps, limits, {"cubic_a": 2})
    line("cubic_a ^2", quad, untied, score(quad["fit"], None))


if __name__ == "__main__":
    main()

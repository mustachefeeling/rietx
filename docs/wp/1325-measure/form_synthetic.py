"""WP-1325: how often the form test fires, on ramps whose truth is known.

``kernel_ramp.py``'s ten-pattern ramp: LaB6 beside a minor CaF2 phase whose
cell follows a line, a curve or a kink, in the weak (W) or overlapped (O)
regime that script describes.  Per seed: the chain, for starting values; the
joint fit with a straight-line equation on the minor cell (``tie``); the same joint
fit with no equation (``untied``); and the score test at the equation's answer
(``form_score.score``).  A line truth measures how often the test fires on a
right form, and the curve and kink how often it fires on a wrong one.

Each test is read three ways, at the 95 % point of χ² for its degrees of
freedom: the refit's Δχ² and the score's gain over χ²_red·f², and the score's
gain over χ²_red alone.  Poisson noise is white, and white residuals put the
Bérar-Lelann factor near 1.127, not 1 (``statistics.berar_lelann_factor``), so
here the f² reading is conservative by about 1.27.

``python docs/wp/1325-measure/form_synthetic.py [--seeds=N]`` (about ten
seconds a seed per regime and truth).
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

SEEDS = int(next((a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--seeds=")), 20))

import kernel_ramp  # noqa: E402
import numpy as np  # noqa: E402
from form_score import score  # noqa: E402
from kernel_ramp import (  # noqa: E402
    MINOR,
    REGIMES,
    TEMPS,
    N,
    a_major,
    calibrate,
    minor_truth,
    simulate,
    start_models,
)
from scipy.stats import chi2 as chi2_dist  # noqa: E402

import rietx as rx  # noqa: E402
from rietx.optimize import least_squares as lsq  # noqa: E402
from rietx.params.multi import SharingMap  # noqa: E402
from rietx.sequential import SequentialRefinement  # noqa: E402

# kernel_ramp appends its prior rows by replacing the joint closures on import;
# nothing here declares a prior, so the package's own are put back
lsq._multi_closures = kernel_ramp._ORIGINAL_CLOSURES

LEVEL = 0.95


def _total(s) -> float:
    return s.chi2 * max(s.n_points - s.n_free_parameters, 1)


def joint(series, patterns, equation: bool):
    equations = [rx.ParametricEquation(name="am", target=MINOR, basis="polynomial",
                             terms=[[], ["T"]])] if equation else None
    fit = rx.MultiHistogramRefinement(
        list(series.fitted_structures), list(series.fitted_instruments),
        sharing=SharingMap(per_histogram=["phases.*"]),
        coordinates=rx.CoordinateTable(columns={"T": TEMPS.tolist()}, units={"T": "K"}),
        parametric=equations)
    result = fit.fit(patterns, plan="mccusker_default")
    return fit, result


def one(regime: str, truth: str, seed: int, scales: list[float]) -> dict:
    spec = REGIMES[regime]
    a_min = minor_truth(truth, spec["rm"])
    a_maj = a_major(TEMPS)
    patterns = [simulate(a_maj[k], a_min[k], scales[k], spec["lor"], 1000 * seed + k)
                for k in range(N)]
    series = SequentialRefinement(*start_models(a_min[0], scales[0], spec["lor"]))
    series.fit(patterns, x=TEMPS.tolist(), x_label="T (K)", plan="mccusker_default")
    t0 = time.perf_counter()
    tie_fit, tie = joint(series, patterns, True)
    t_tie = time.perf_counter() - t0
    _, untied = joint(series, patterns, False)
    sc = score(tie_fit, None)
    st, su = tie.statistics, untied.statistics
    dchi2 = _total(st) - _total(su)
    dfree = su.n_free_parameters - st.n_free_parameters
    return dict(dchi2=dchi2, dfree=dfree,
                refit=dchi2 / (su.chi2 * su.esd_inflation ** 2),
                gain=sc["gain"], rank=sc["rank"], score=sc["stat"],
                plain=sc["gain"] / sc["chi2r"], f=sc["f"], t_tie=t_tie,
                t_score=sc["t_eval"] + sc["t_score"],
                held=len({p for s in tie.stages for p in s.held}),
                status=(tie.status, untied.status))


def main() -> None:
    print(f"WP-1325: the form test's rate on kernel_ramp's synthetic ramps, {SEEDS} seeds, "
          f"level {LEVEL}")
    for regime in REGIMES:
        scales = calibrate(REGIMES[regime])
        for truth in ("line", "curve", "kink"):
            rows = []
            for seed in range(SEEDS):
                try:
                    rows.append(one(regime, truth, seed, scales))
                except Exception as exc:  # noqa: BLE001 - a failed seed is reported, not fatal
                    print(f"  {regime}/{truth} seed {seed}: {type(exc).__name__}: {exc}",
                          flush=True)
                    continue
                r = rows[-1]
                print(f"  {regime}/{truth} seed {seed:2d}: refit Δχ² {r['dchi2']:7.2f} for "
                      f"{r['dfree']}, score gain {r['gain']:7.2f} for {r['rank']}; "
                      f"refit/f² {r['refit']:6.2f}, score/f² {r['score']:6.2f}, "
                      f"plain {r['plain']:6.2f}; f {r['f']:.3f}; held {r['held']}; "
                      f"{r['status']}", flush=True)
            if not rows:
                continue

            def rate(key: str, dof: str) -> str:
                hits = sum(r[key] > chi2_dist.ppf(LEVEL, max(r[dof], 1)) for r in rows)
                return f"{hits}/{len(rows)}"

            ratio = np.array([r["gain"] / r["dchi2"] for r in rows if r["dchi2"] > 0] or [np.nan])
            print(f"{regime}/{truth}: fired refit/f² {rate('refit', 'dfree')}, "
                  f"score/f² {rate('score', 'rank')}, score plain {rate('plain', 'rank')}; "
                  f"gain ÷ refit Δχ² {np.median(ratio):.3f} median "
                  f"[{ratio.min():.3f}, {ratio.max():.3f}]; ranks "
                  f"{sorted({r['rank'] for r in rows})}, refit dfree "
                  f"{sorted({r['dfree'] for r in rows})}; score {np.median([r['t_score'] for r in rows]):.2f} s "
                  f"against tie {np.median([r['t_tie'] for r in rows]):.2f} s (medians)",
                  flush=True)


if __name__ == "__main__":
    main()

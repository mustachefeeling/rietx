"""WP-1325: does a one-direction test for the next term earn a place?

The form test's alternative frees the target in every pattern, n − m
directions for an equation of m coefficients over n patterns.  Against smooth
curvature most of those directions carry only noise, and a score test on the
next polynomial term alone spends one.  That is how a statistician picks an
order: a nested F-test, or AIC/BIC across orders.

On ``test_parametric_series``'s ten-pattern LaB6 ramp (a line in T, the
instrument's zero and profile shared), the truth is the line plus a bend of
``bow`` times the line's half-excursion, in two shapes:

- ``curve``: (u² − 1) at u = (T − 750)/450, the next term exactly;
- ``kink``: (|u| − 1), a slope change at mid-ramp that no polynomial holds.

A straight line is declared.  Three readings per fit:

1. ``form``: the shipped form test (``result.parametric_form``), χ²_8.
2. ``next``: the score for one added column, the next term's, Σ_k u_k² times
   pattern k's own target column (``target_columns``).  Dense: one projection
   of the free columns at the answer, columns on a bound held out of both
   sides as the form test holds them, over the same χ²_red·f², against χ²_1.
3. ``refit``: the oracle, a quadratic equation refitted; its χ² drop over the
   quadratic fit's χ²_red·f², against χ²_1.

The ``check`` line rebuilds the form statistic densely from per-pattern
columns, so ``next`` is read with the plumbing the shipped test is.

    .venv/bin/python docs/wp/1325-measure/next_term.py [--reps=8]
        > docs/wp/1325-measure/next_term_results.txt
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO))

import numpy as np  # noqa: E402
from real_ramp import machine  # noqa: E402
from scipy.stats import chi2 as chi2_dist  # noqa: E402

import rietx as rx  # noqa: E402
from rietx.optimize import least_squares as lsq  # noqa: E402
from rietx.optimize.blocked import BlockJacobian  # noqa: E402
from rietx.optimize.statistics import berar_lelann_factor  # noqa: E402
from rietx.params.multi import SharingMap  # noqa: E402
from rietx.params.parametric import target_columns  # noqa: E402
from tests.test_sequential import A0, RAMP, _simulate, _start_models  # noqa: E402

TEMPS = np.array([300.0 + 100.0 * k for k in range(10)])
U = (TEMPS - 750.0) / 450.0
SHAPES = {"curve": U * U - 1.0, "kink": np.abs(U) - 1.0}
BOWS = [2e-3, 1e-3, 7e-4, 5e-4, 3e-4, 2e-4, 0.0]
CUT1 = float(chi2_dist.ppf(0.95, 1))


def ramp(shape: str, bow: float, rep: int):
    a = A0 * (1.0 + RAMP * (TEMPS - 300.0) / 100.0) + bow * A0 * RAMP * 4.5 * SHAPES[shape]
    return [_simulate(float(a[k]), seed=1000 * rep + k) for k in range(10)]


def fit(patterns, degree: int):
    structure, ins = _start_models()
    ref = rx.MultiHistogramRefinement(
        structure, [ins] * 10,
        sharing=SharingMap(shared=["instrument.zero_shift", "instrument.profile.*"]),
        coordinates=rx.CoordinateTable(columns={"T": TEMPS.tolist()}, units={"T": "K"}),
        parametric=[rx.ParametricEquation(name="a", target="phases.0.cell.a", basis="polynomial",
                                          terms=[["T"] * j for j in range(degree + 1)])])
    return ref, ref.fit(patterns, plan="mccusker_default")


def _perp(m: np.ndarray, v: np.ndarray) -> np.ndarray:
    """``v`` less its least-squares projection on ``m``'s columns."""
    beta, *_ = np.linalg.lstsq(m, v, rcond=None)
    return v - m @ beta


def readings(ref, result) -> dict:
    mt = ref.mtable
    residual, jacobian, n_data = lsq._multi_closures(ref._models, mt, layout="blocked")
    x = mt.x0()
    r, bj = residual(x), jacobian(x)
    rd = r[:n_data]
    scale = float(rd @ rd) / (n_data - len(x)) * berar_lelann_factor(rd) ** 2
    (res,) = mt.parametric
    cols = target_columns(res, bj, mt.free_paths)
    lo, hi = mt.bounds()
    held = set(np.flatnonzero((x <= lo) | (x >= hi)).tolist())
    dense = bj.toarray()
    keep = [j for j in range(bj.n_cols) if j not in held]
    coef = [mt.free_paths.index(p) for p in res.paths]
    j_null = dense[:, keep]
    r_perp = _perp(j_null, r)
    # the next term: one column shared by every pattern, u_k² times its own
    u = res.phi[:, 1]
    shared = BlockJacobian([(u[k] ** 2) * cols[k] for k in range(bj.n_blocks)],
                           [np.array([0])] * bj.n_blocks, bj.n_data, bj.n_pen, 1).toarray()
    c = _perp(j_null, shared[:, 0])
    gain_next = float(c @ r_perp) ** 2 / float(c @ c)
    # the form test rebuilt the same way: per-pattern columns for the coefficients
    own = BlockJacobian([cols[k] for k in range(bj.n_blocks)],
                        [np.array([k]) for k in range(bj.n_blocks)],
                        bj.n_data, bj.n_pen, bj.n_blocks).toarray()
    alt = np.hstack([dense[:, [j for j in keep if j not in coef]], own])
    r_alt = _perp(alt, r)
    gain_form = float(r_perp @ r_perp) - float(r_alt @ r_alt)
    (form,) = result.parametric_form
    return dict(form=form.tied, next=gain_next / scale, check=gain_form / scale)


def main() -> None:
    reps = 8
    for arg in sys.argv[1:]:
        key, _, value = arg.removeprefix("--").partition("=")
        if key != "reps":
            raise SystemExit(f"unknown argument {arg!r}")
        reps = int(value)
    print("WP-1325: a one-direction next-term test against the form test")
    for m in machine():
        print(m)
    print(f"ramp      10 LaB6 patterns, 300-1200 K, a line declared; {reps} noise "
          f"draws a cell; cuts χ²_8 {chi2_dist.ppf(0.95, 8):.2f}, χ²_1 {CUT1:.2f}")
    t0 = time.perf_counter()
    for shape in SHAPES:
        for bow in BOWS:
            rows = []
            for rep in range(reps):
                patterns = ramp(shape, bow, rep)
                ref, result = fit(patterns, 1)
                rd = readings(ref, result)
                _, quad = fit(patterns, 2)
                s1, s2 = result.statistics, quad.statistics
                n = s1.n_points
                drop = s1.chi2 * (n - s1.n_free_parameters) - s2.chi2 * (n - s2.n_free_parameters)
                rd["refit"] = drop / (s2.chi2 * s2.esd_inflation ** 2)
                rows.append(rd)
            form = np.array([r["form"].statistic for r in rows])
            check = np.array([r["check"] for r in rows])
            nxt = np.array([r["next"] for r in rows])
            refit = np.array([r["refit"] for r in rows])
            cut8 = rows[0]["form"].cut
            print(f"{shape:5} bow {bow:6.1e}  reject: form {np.sum(form > cut8):2d}/{reps}  "
                  f"next {np.sum(nxt > CUT1):2d}/{reps}  refit {np.sum(refit > CUT1):2d}/{reps}"
                  f"   median: form {np.median(form):8.1f}  next {np.median(nxt):8.1f}  "
                  f"refit {np.median(refit):8.1f}  check/form "
                  f"[{np.min(check / form):.4f}, {np.max(check / form):.4f}]", flush=True)
    print(f"wall      {time.perf_counter() - t0:.0f} s")


if __name__ == "__main__":
    main()

"""Share of a fit spent in the scalar-chain columns, scatter excluded.

usage: shareprobe.py REPO CASE   -- one wrapper, so the overhead is ~1 µs a column
"""
import os
import sys
import time

repo, case = sys.argv[1], sys.argv[2]
sys.path.insert(0, os.path.join(repo, "examples"))
sys.path.insert(0, os.path.join(repo, "tests"))
os.environ.setdefault("RIETX_TELEMETRY", "0")

import rietx as rx  # noqa: E402
import rietx.optimize.least_squares as lsq  # noqa: E402
import bench_refinement as br  # noqa: E402

setup = {c.key: c for c in br.CASES}[case].build()
orig_col, orig_acc = lsq._peak_chain_column, lsq._accumulate
clock = {"col": 0.0, "acc": 0.0, "n": 0, "in": False}


def w_col(*a, **k):
    clock["in"] = True
    t0 = time.perf_counter()
    try:
        return orig_col(*a, **k)
    finally:
        clock["col"] += time.perf_counter() - t0
        clock["n"] += 1
        clock["in"] = False


def w_acc(*a, **k):
    if not clock["in"]:
        return orig_acc(*a, **k)
    t0 = time.perf_counter()
    try:
        return orig_acc(*a, **k)
    finally:
        clock["acc"] += time.perf_counter() - t0


lsq._peak_chain_column, lsq._accumulate = w_col, w_acc
for rep in range(3):
    clock.update(col=0.0, acc=0.0, n=0)
    ref = rx.Refinement(setup.structure.model_copy(deep=True),
                        setup.instrument.model_copy(deep=True), history=False)
    t0 = time.perf_counter()
    ref.fit(setup.data, plan=setup.plan, mode=setup.mode,
            two_theta_limits=setup.limits)
    wall = time.perf_counter() - t0
    if rep:
        s = clock["col"] - clock["acc"]
        print(f"{case} rep {rep}: fit {wall:.2f} s, {clock['n']} columns, "
              f"column work {s:.3f} s ({100 * s / wall:.1f} %), "
              f"their scatter {clock['acc']:.3f} s")

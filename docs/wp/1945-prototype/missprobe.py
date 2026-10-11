"""Why do lor_size columns rebuild the cell block?  On the first few misses of
the 'cell' slot inside a lor_size column, print the requested key against
the keys the slot holds, and which positions differ.

usage: missprobe.py REPO CASE
"""
import os
import sys

repo, case = sys.argv[1], sys.argv[2]
sys.path.insert(0, os.path.join(repo, "examples"))
sys.path.insert(0, os.path.join(repo, "tests"))
os.environ.setdefault("RIETX_TELEMETRY", "0")

import rietx as rx  # noqa: E402
import rietx.optimize.least_squares as lsq  # noqa: E402
from rietx.model.forward import CompiledModel  # noqa: E402
import bench_refinement as br  # noqa: E402

setup = {c.key: c for c in br.CASES}[case].build()
state = {"path": None, "shown": 0, "seq": []}
orig_col, orig_memo = lsq._peak_chain_column, CompiledModel._memo
orig_jac_for = lsq._jacobian_for


def w_col(model, table, bases, theta, values, c, path, *a, **k):
    state["path"] = path
    state["seq"].append(path)
    try:
        return orig_col(model, table, bases, theta, values, c, path, *a, **k)
    finally:
        state["path"] = None


def w_memo(self, cp, slot, key_fn, build):
    path = state["path"]
    if (path and path.endswith("lor_size") and slot == "cell"
            and state["shown"] < 4 and cp.scalar_cache is not None):
        key = key_fn()
        held = cp.scalar_cache.get(slot) or []
        if all(h[0] != key for h in held):
            state["shown"] += 1
            print(f"miss in {path}; columns so far this Jacobian:")
            print("   ", state["seq"][-12:])
            for i, (hk, _v) in enumerate(held):
                diff = [(j, hk[j], key[j]) for j in range(min(len(hk), len(key)))
                        if hk[j] != key[j]]
                print(f"  held[{i}] differs at {diff}")
    return orig_memo(self, cp, slot, key_fn, build)


def jac_for(model, table, backend):
    inner = orig_jac_for(model, table, backend)

    def jacobian(theta):
        state["seq"] = []
        return inner(theta)

    return jacobian


lsq._peak_chain_column, lsq._jacobian_for = w_col, jac_for
CompiledModel._memo = w_memo
ref = rx.Refinement(setup.structure.model_copy(deep=True),
                    setup.instrument.model_copy(deep=True), history=False)
ref.fit(setup.data, plan=setup.plan, mode=setup.mode,
        two_theta_limits=setup.limits)

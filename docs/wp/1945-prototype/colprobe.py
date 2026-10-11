"""Break the Jacobian's scalar-chain column seam down by parameter family.

usage: colprobe.py REPO CASE

Per family: columns, phase_peaks calls, seconds in the column, and inside it
the decode, each memo slot's block builds, and phase_peaks' remainder (key
building, lookups, the per-line intensity assembly).  Wrappers, not cProfile.
"""
import os
import re
import sys
import time
from collections import defaultdict

repo, case = sys.argv[1], sys.argv[2]
sys.path.insert(0, os.path.join(repo, "examples"))
sys.path.insert(0, os.path.join(repo, "tests"))
os.environ.setdefault("RIETX_TELEMETRY", "0")

import rietx as rx  # noqa: E402
import rietx.optimize.least_squares as lsq  # noqa: E402
from rietx.model.forward import CompiledModel  # noqa: E402
from rietx.params.vector import ParameterTable  # noqa: E402
import bench_refinement as br  # noqa: E402

setup = {c.key: c for c in br.CASES}[case].build()
if os.environ.get("MEMO_DEPTH"):
    import rietx.model.forward as fwd
    fwd._MEMO_DEPTH = int(os.environ["MEMO_DEPTH"])
    print(f"_MEMO_DEPTH = {fwd._MEMO_DEPTH}")
if os.environ.get("MEMO_SCAN"):
    # _memo with the lookup scanning every held entry (the shipped one
    # compares held[0] and held[1] only), a hit promoted to the front
    import rietx.model.forward as fwd

    def scan_memo(self, cp, slot, key_fn, build):
        cache = cp.scalar_cache
        if cache is None or fwd.get_backend().name != "numpy":
            return build()
        key = key_fn()
        held = cache.get(slot)
        if held is not None:
            for i, (k, v) in enumerate(held):
                if k == key:
                    if i:
                        held.insert(0, held.pop(i))
                    return v
        value = build()
        fwd._freeze(value)
        if held is None:
            cache[slot] = [(key, value)]
        else:
            held.insert(0, (key, value))
            del held[fwd._MEMO_DEPTH:]
        return value

    CompiledModel._memo = scan_memo
    print("lookup scans every held entry")

state = {"fam": None}
col_t = defaultdict(float)
col_n = defaultdict(int)
peaks_t = defaultdict(float)
peaks_n = defaultdict(int)
dec_t = defaultdict(float)
build_t = defaultdict(float)   # (family, slot) -> s
build_n = defaultdict(int)
acc_t = defaultdict(float)


def family(path):
    return re.sub(r"\.\d+(?=\.|$)", ".*", path)


orig_col = lsq._peak_chain_column
orig_peaks = CompiledModel.phase_peaks
orig_memo = CompiledModel._memo
orig_dec = ParameterTable.decode
orig_acc = lsq._accumulate


def w_col(model, table, bases, theta, values, c, path, *a, **k):
    fam = family(path)
    state["fam"] = fam
    t0 = time.perf_counter()
    try:
        return orig_col(model, table, bases, theta, values, c, path, *a, **k)
    finally:
        col_t[fam] += time.perf_counter() - t0
        col_n[fam] += 1
        state["fam"] = None


def w_peaks(self, *a, **k):
    fam = state["fam"]
    if fam is None:
        return orig_peaks(self, *a, **k)
    t0 = time.perf_counter()
    try:
        return orig_peaks(self, *a, **k)
    finally:
        peaks_t[fam] += time.perf_counter() - t0
        peaks_n[fam] += 1


def w_memo(self, cp, slot, key_fn, build):
    fam = state["fam"]
    if fam is None:
        return orig_memo(self, cp, slot, key_fn, build)

    def timed_build():
        t0 = time.perf_counter()
        try:
            return build()
        finally:
            build_t[(fam, slot)] += time.perf_counter() - t0
            build_n[(fam, slot)] += 1

    return orig_memo(self, cp, slot, key_fn, timed_build)


def w_dec(self, theta):
    fam = state["fam"]
    if fam is None:
        return orig_dec(self, theta)
    t0 = time.perf_counter()
    try:
        return orig_dec(self, theta)
    finally:
        dec_t[fam] += time.perf_counter() - t0


def w_acc(*a, **k):
    fam = state["fam"]
    if fam is None:
        return orig_acc(*a, **k)
    t0 = time.perf_counter()
    try:
        return orig_acc(*a, **k)
    finally:
        acc_t[fam] += time.perf_counter() - t0


def fit():
    ref = rx.Refinement(setup.structure.model_copy(deep=True),
                        setup.instrument.model_copy(deep=True), history=False)
    t0 = time.perf_counter()
    ref.fit(setup.data, plan=setup.plan, mode=setup.mode,
            two_theta_limits=setup.limits)
    return time.perf_counter() - t0


fit()  # warm, unwrapped
lsq._peak_chain_column = w_col
CompiledModel.phase_peaks = w_peaks
CompiledModel._memo = w_memo
ParameterTable.decode = w_dec
lsq._accumulate = w_acc
wall = fit()

tot = sum(col_t.values())
print(f"{case}: fit {wall:.2f} s, scalar-chain columns {tot:.3f} s "
      f"({100 * tot / wall:.0f} %), {sum(col_n.values())} columns")
slots = sorted({s for _f, s in build_t})
print("| family | cols | peaks calls | col s | decode | accum | peaks other | "
      + " | ".join(f"build {s}" for s in slots) + " | col rest |")
for fam in sorted(col_t, key=lambda f: -col_t[f]):
    builds = [build_t.get((fam, s), 0.0) for s in slots]
    other = peaks_t[fam] - sum(builds)
    rest = col_t[fam] - peaks_t[fam] - dec_t[fam] - acc_t[fam]
    cells = " | ".join(
        f"{b:.3f} ({build_n.get((fam, s), 0)})" if b else "-"
        for s, b in zip(slots, builds))
    print(f"| {fam} | {col_n[fam]} | {peaks_n[fam]} | {col_t[fam]:.3f} | "
          f"{dec_t[fam]:.3f} | {acc_t[fam]:.3f} | {other:.3f} | {cells} | "
          f"{rest:.3f} |")
allb = sum(build_t.values())
print(f"\ntotals: decode {sum(dec_t.values()):.3f}  accum {sum(acc_t.values()):.3f}  "
      f"block builds {allb:.3f}  peaks other "
      f"{sum(peaks_t.values()) - allb:.3f}  column rest "
      f"{tot - sum(peaks_t.values()) - sum(dec_t.values()) - sum(acc_t.values()):.3f}")

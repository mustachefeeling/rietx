"""WP-1325, the maintainer's question: would another Rust kernel speed the joint fit?

    .venv/bin/python docs/wp/1325-measure/jacobian_profile.py [--n=60] [--repeats=5]
        > docs/wp/1325-measure/jacobian_profile_results.txt

Run from the repository root, alone on the machine (every figure is a wall
clock).  The library is ``scaling.py``'s: ``tests/test_parametric_series.py``'s
``library(n)``, the cell one four-term ``polynomial`` over (x, y), each pattern
with its own zero, profile and background, fitted **blocked** under
``mccusker_default``.  ``scaling.py`` found the per-pattern Jacobian loop at
45 % of a 300-pattern fit; this asks what that loop's time is made of.

Four measurements:

1. **the fit, plain**, with the joint Jacobian and residual closures timed, and
   **the same fit under cProfile**: the share of the ``rietx_kernels`` calls
   in it, and of ``_peak_chain_column`` inside the Jacobian;
2. **at the answer**, the per-pattern Jacobian and residual loops run serially
   and over a thread pool of 2 and of 4 — whether the patterns parallelise
   under the GIL;
3. which columns reach the peak chain in the last stage;
4. the Jacobian loop with each **repeated peak-chain path computed once per
   pattern**: a tie's coefficient columns all arrive under their target's name,
   so this is what computing ∂y/∂(target) once and scaling it by Φ would save.
   **Timing only** — the cached column is returned unscaled, so its values are
   wrong.

Every repeat moves θ by a relative 1e-10, as a fit moves it every iteration:
``phase_peaks`` memoises on the cell, and a repeated θ would time the cache
(it did: an early draft of (4) read 6.2× where the honest figure is 1.5×).
Base and deduplicated repeats are interleaved so drift lands on both.
"""

from __future__ import annotations

import cProfile
import os
import pstats
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

os.environ.setdefault("RIETX_TELEMETRY", "0")

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(HERE))

import numpy as np  # noqa: E402
import scaling  # noqa: E402
from scaling import head, machine, src_fingerprint  # noqa: E402

from rietx.multi import MultiHistogramRefinement  # noqa: E402
from rietx.optimize import blocked  # noqa: E402
from rietx.optimize import least_squares as ls  # noqa: E402
from tests.test_parametric_series import library  # noqa: E402
from tests.test_sequential import _start_models  # noqa: E402

# scaling.py runs its workers as children, so it skips only its own pid; this
# runs under the shell that launched it, whose command line names this file
# too, perhaps through a wrapper (``timeout``, ``uv run``): skip every ancestor
_others = scaling.others_running


def _ancestors() -> set[str]:
    out, pid = set(), os.getppid()
    while pid > 1:
        out.add(str(pid))
        try:
            pid = int(Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[1])
        except (OSError, ValueError, IndexError):
            break
    return out


scaling.others_running = lambda: [ln for ln in _others()
                                  if ln.split(None, 1)[0] not in _ancestors()]

# -- the closures, captured as the joint path builds them ---------------------

_closures = ls._multi_closures
_make_residual = ls._make_residual
_jacobian_for = ls._jacobian_for
_peak_chain = ls._peak_chain_column
captured: dict = {}
building: dict = {"res": [], "jac": []}
spent = {"jacobian": 0.0, "residual": 0.0}
calls = {"jacobian": 0, "residual": 0}


def _timed(fn, key):
    def wrapped(*a, **kw):
        t = time.perf_counter()
        try:
            return fn(*a, **kw)
        finally:
            spent[key] += time.perf_counter() - t
            calls[key] += 1
    return wrapped


def _residual_spy(m, t):
    f = _make_residual(m, t)
    building["res"].append(f)
    return f


def _jacobian_spy(m, t, backend):
    f = _jacobian_for(m, t, backend)
    building["jac"].append(f)
    return f


def _closures_spy(models, mtable, **kw):
    building["res"].clear()
    building["jac"].clear()
    residual, jacobian, n_data = _closures(models, mtable, **kw)
    captured.update(mtable=mtable, res=list(building["res"]), jac=list(building["jac"]))
    return _timed(residual, "residual"), _timed(jacobian, "jacobian"), n_data


ls._multi_closures = _closures_spy
ls._make_residual = _residual_spy
ls._jacobian_for = _jacobian_spy


def fit(n: int, profile: cProfile.Profile | None = None):
    patterns, coords, tie = library(n)
    blocked.set_layout("blocked")
    s, ins = _start_models()
    ref = MultiHistogramRefinement(s, [ins] * n, coordinates=coords, parametric=[tie])
    for k in spent:
        spent[k], calls[k] = 0.0, 0
    t = time.perf_counter()
    if profile is not None:
        profile.enable()
    result = ref.fit(patterns, plan="mccusker_default")
    if profile is not None:
        profile.disable()
    return result, time.perf_counter() - t


# -- (1) the profile ----------------------------------------------------------

def profile_shares(st: pstats.Stats) -> dict:
    def where(pred):
        return [(k, v) for k, v in st.stats.items() if pred(k)]

    kernels = where(lambda k: k[0] == "~" and "rietx_kernels" in k[2])
    chain = where(lambda k: k[0].endswith("least_squares.py")
                  and k[2] == "_peak_chain_column")
    joint = where(lambda k: k[0].endswith("least_squares.py")
                  and k[2] == "block_jacobian")
    return {
        "total": st.total_tt,
        "kernels": sum(v[2] for _, v in kernels),
        "kernel_rows": sorted(((k[2], v[1], v[2]) for k, v in kernels),
                              key=lambda r: -r[2]),
        "chain_cum": sum(v[3] for _, v in chain),
        "chain_calls": sum(v[1] for _, v in chain),
        "joint_cum": sum(v[3] for _, v in joint),
        "joint_calls": sum(v[1] for _, v in joint),
    }


# -- (2)-(4) at the answer ----------------------------------------------------

class AtAnswer:
    def __init__(self):
        self.mt = captured["mtable"]
        # from each committed sub-table, never ``mt.x0()``: the combined vector
        # is cached at the stage's start and a commit leaves it there
        # (``multi.py``'s ``_stage_end_rows`` docstring)
        self.theta = np.empty(len(self.mt.free_paths), dtype=float)
        for h, table in enumerate(self.mt.tables):
            self.theta[self.mt.col_map(h)] = table.x0()
        self.res, self.jac = captured["res"], captured["jac"]
        self.n = len(self.jac)
        self.rep = 0

    def fresh(self) -> list[np.ndarray]:
        self.rep += 1
        return self.mt.split(self.theta * (1.0 + 1e-10 * self.rep))

    def serial(self, fns, before=None) -> float:
        ths = self.fresh()
        t = time.perf_counter()
        for h in range(self.n):
            if before is not None:
                before()
            fns[h](ths[h])
        return time.perf_counter() - t

    def pooled(self, fns, k: int) -> float:
        with ThreadPoolExecutor(k) as pool:
            ths = self.fresh()
            list(pool.map(lambda h: fns[h](ths[h]), range(self.n)))  # warm the pool
            ths = self.fresh()
            t = time.perf_counter()
            list(pool.map(lambda h: fns[h](ths[h]), range(self.n)))
            return time.perf_counter() - t

    def chain_paths(self) -> list[str]:
        seen: list[str] = []

        def spy(model, table, bases, theta_t, values, c, path, *a, **kw):
            seen.append(path)
            return _peak_chain(model, table, bases, theta_t, values, c, path, *a, **kw)

        ls._peak_chain_column = spy
        try:
            self.jac[0](self.fresh()[0])
        finally:
            ls._peak_chain_column = _peak_chain
        return seen

    def dedup(self, repeats: int) -> tuple[list[float], list[float]]:
        memo: dict = {}

        def once(model, table, bases, theta_t, values, c, path, *a, **kw):
            if path not in memo:
                memo[path] = _peak_chain(model, table, bases, theta_t, values, c, path,
                                         *a, **kw)
            return memo[path]  # unscaled: timing only

        base, dd = [], []
        for _ in range(repeats):
            base.append(self.serial(self.jac))
            ls._peak_chain_column = once
            try:
                dd.append(self.serial(self.jac, before=memo.clear))
            finally:
                ls._peak_chain_column = _peak_chain
        return base, dd


def ms(xs: list[float]) -> str:
    lo, hi = min(xs) * 1e3, max(xs) * 1e3
    return f"{lo:.1f}" if len(xs) == 1 else f"{lo:.1f}-{hi:.1f}"


def main(n: int, repeats: int) -> None:
    from rietx.model import compiled

    fp = src_fingerprint()
    print(f'WP-1325, "would another Rust kernel help?": where a blocked joint fit\'s '
          f"Jacobian time goes, N = {n}.\n")
    for line in machine():
        print(line)
    print(f"kernels   {compiled.n_threads()} pool threads; " + ", ".join(
        f"{v}={os.environ.get(v, '(unset)')}" for v in (
            "RIETX_COMPILED_THREADS", "OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS")))
    print(f"tree      HEAD {head()} at start, src/ fingerprint {fp}")
    print("library   tests' library(n): 3000 points a pattern, cell = four-term "
          "polynomial over (x, y), 10 own columns a pattern, blocked layout\n")

    result, wall = fit(n)
    print(f"== (1) the fit: {result.status}, Rwp {result.statistics.rwp:.6f}")
    print(f"  plain      wall {wall:.2f} s; joint Jacobian {spent['jacobian']:.2f} s over "
          f"{calls['jacobian']} calls ({spent['jacobian'] / wall:.0%}), joint residual "
          f"{spent['residual']:.2f} s over {calls['residual']} calls "
          f"({spent['residual'] / wall:.0%})")
    prof = cProfile.Profile()
    _, pwall = fit(n, prof)
    sh = profile_shares(pstats.Stats(prof))
    print(f"  cProfile   wall {pwall:.2f} s, {sh['total']:.2f} s profiled "
          "(the profiler inflates python, not the kernels: a python share is "
          "read against python, a kernel's against the plain wall)")
    print(f"    rietx_kernels calls: {sh['kernels']:.3f} s = "
          f"{sh['kernels'] / sh['total']:.1%} of the profiled fit, "
          f"{sh['kernels'] / wall:.1%} of the plain wall (an upper estimate)")
    for name, nc, tt in sh["kernel_rows"]:
        print(f"      {name:55s} {nc:6d} calls {tt:.3f} s")
    print(f"    joint Jacobian (block_jacobian): {sh['joint_cum']:.2f} s over "
          f"{sh['joint_calls']} calls = {sh['joint_cum'] / sh['total']:.0%} of the fit")
    print(f"    _peak_chain_column: {sh['chain_cum']:.2f} s over {sh['chain_calls']} "
          f"calls = {sh['chain_cum'] / sh['joint_cum']:.0%} of the joint Jacobian, "
          f"{sh['chain_calls'] / (sh['joint_calls'] * n):.1f} a pattern a Jacobian")

    at = AtAnswer()
    print(f"\n== (2) at the answer, {at.n} patterns, last stage's "
          f"{len(at.mt.free_paths)} columns; min over {repeats} repeats, each at a new θ")
    for name, fns in (("Jacobian", at.jac), ("residual", at.res)):
        at.serial(fns)
        ts = [at.serial(fns) for _ in range(repeats)]
        print(f"  {name:9s} serial      {ms(ts):>12s} ms   "
              f"({min(ts) / at.n * 1e3:.2f} ms a pattern)")
        for k in (2, 4):
            tp = [at.pooled(fns, k) for _ in range(repeats)]
            print(f"  {name:9s} {k} threads   {ms(tp):>12s} ms   "
                  f"speedup {min(ts) / min(tp):.2f}x")

    paths = at.chain_paths()
    print(f"\n== (3) peak-chain columns of one pattern's Jacobian, last stage: {len(paths)}")
    for p in dict.fromkeys(paths):
        print(f"  {paths.count(p)} x {p}")

    base, dd = at.dedup(repeats)
    print("\n== (4) each repeated peak-chain path once per pattern (timing only)")
    print(f"  Jacobian loop {ms(base)} ms -> {ms(dd)} ms = {min(base) / min(dd):.2f}x "
          "(min against min)")

    print()
    for line in machine()[3:]:
        print(line.replace("at start", "at end"))
    after = src_fingerprint()
    print(f"tree      HEAD {head()} at end; src/ fingerprint {after}, "
          f"{'unchanged' if after == fp else 'CHANGED'} during the run")


if __name__ == "__main__":
    args = dict(a.lstrip("-").split("=", 1) for a in sys.argv[1:] if "=" in a)
    main(int(args.get("n", "60")), int(args.get("repeats", "5")))

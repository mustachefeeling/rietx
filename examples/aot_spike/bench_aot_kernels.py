"""WP-1939: the ahead-of-time kernel candidates against the shipped numba tier.

Run: ``.venv/bin/python examples/aot_spike/bench_aot_kernels.py [--repeats N]``

Builds first (each needs its own toolchain; the WP file has the commands):

- ``rietx_kernels_rs`` — ``rust/``, PyO3 + rust-numpy, ``maturin build --release``
  then ``uv pip install`` the abi3 wheel;
- ``rietx_kernels_cy`` and ``rietx_kernels_cy_default`` — ``cython/``, built
  in place twice by its ``setup.py``, with ``-ffp-contract=off`` and with the
  compiler's default; ``rietx_kernels_cy_abi3`` a third time, against the
  Limited API (``RIETX_SPIKE_ABI3=1``).

Every candidate exposes the five numba kernels under the numba names and
signatures, so ``compiled._KERNELS`` holds one in place of the other and the
rest of the package cannot tell.  Three measurements:

1. **Agreement, per call, inside a real fit.**  One fit runs on numba with every
   kernel call shadowed: the outputs are snapshotted, each candidate is run on
   the same inputs, and its outputs are compared to numba's bit for bit.  Serial
   (the pool's worker count forced to 1), so the per-call seconds summed beside the
   comparison are a serial kernel-time ratio.  The order the implementations
   run in rotates per call, so no one of them always meets a warm cache.
2. **End to end.**  ``_KERNELS`` swapped wholesale, the whole fit timed, arms
   interleaved (bench_refinement rule 2), on the default thread count.  The
   final parameter vector is compared to numba's: identical, or the largest
   difference in esd units.
3. **Startup**: import, and numba's cached and cold compile, each in a fresh
   process.

Wall clock is a range, never a figure (bench_refinement rule 1).
"""

from __future__ import annotations

import argparse
import importlib
import os
import platform
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("RIETX_TELEMETRY", "0")

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(REPO / "examples"))
sys.path.insert(0, str(REPO / "tests"))
sys.path.insert(0, str(HERE / "cython"))

import numpy as np  # noqa: E402

import rietx as rx  # noqa: E402
from rietx.model import compiled  # noqa: E402

#: positional indices of each kernel's *output* arrays
OUTPUTS = {
    "accum": (0,),
    "omega_sym": (0,),
    "omega_fcj": (0,),
    "bases_sym": (0, 1, 2, 3),
    "bases_fcj": (0, 1, 2, 3, 4, 5),
}

CANDIDATES = ("rietx_kernels_rs", "rietx_kernels_cy", "rietx_kernels_cy_abi3",
              "rietx_kernels_cy_default", "rietx_kernels_cy_default_abi3")
LABEL = {"numba": "numba", "rietx_kernels_rs": "rust",
         "rietx_kernels_cy": "cython (contract off)",
         "rietx_kernels_cy_abi3": "cython abi3 (contract off)",
         "rietx_kernels_cy_default": "cython (clang default)",
         "rietx_kernels_cy_default_abi3": "cython abi3 (clang default)"}


def _candidates() -> dict[str, dict]:
    out = {}
    for mod in CANDIDATES:
        try:
            m = importlib.import_module(mod)
        except ImportError as exc:
            print(f"  {mod}: not built ({exc})")
            continue
        out[mod] = {k: getattr(m, k) for k in OUTPUTS}
    return out


def _cases():
    import bench_refinement as br

    return {"trigger": br._trigger, "cpd-1a": br._cpd_1a, "nac": br._nac}


def _fit(setup):
    ref = rx.Refinement(setup.structure.model_copy(deep=True),
                        setup.instrument.model_copy(deep=True), history=False)
    t0 = time.perf_counter()
    result = ref.fit(setup.data, plan=setup.plan, mode=setup.mode,
                     two_theta_limits=setup.limits)
    return time.perf_counter() - t0, result


def _ordered(a: np.ndarray) -> np.ndarray:
    """Doubles as int64s that sort the way the values do (−0.0 maps to +0.0)."""
    i = a.view(np.int64)
    return np.where(i < 0, np.int64(np.iinfo(np.int64).min) - i, i)


def _max_ulps(a: np.ndarray, b: np.ndarray) -> float:
    """Largest ulp distance between two planes, exact across a sign change.

    Subtracting raw bit patterns wraps when the signs differ, so the distance
    is taken on the ordered integers, in uint64, where it cannot overflow.
    """
    oa, ob = _ordered(a), _ordered(b)
    hi = np.maximum(oa, ob).view(np.uint64)
    lo = np.minimum(oa, ob).view(np.uint64)
    return float((hi - lo).max())


def _theta_gap(ref: dict, got: dict) -> str:
    """How far one arm's final parameters sit from numba's.

    A path present on one side only, or a value differing where no positive
    esd exists to scale it, is counted rather than dropped, so a difference
    never reads as 0 esd.
    """
    if got == ref:
        return "bit-identical"
    worst, unscaled = 0.0, 0
    for path, (v, e) in ref.items():
        if path not in got:
            continue
        gv = got[path][0]
        if gv == v:
            continue
        gap = abs(gv - v) / e if e and e > 0 else float("nan")
        if gap != gap:
            unscaled += 1
        else:
            worst = max(worst, gap)
    out = f"max {worst:.1e} esd"
    missing = len(ref.keys() - got.keys()) + len(got.keys() - ref.keys())
    if unscaled:
        out += f", {unscaled} differing with no esd to scale (or NaN)"
    if missing:
        out += f", {missing} paths on one side only"
    return out


class _Shadow:
    """Per-kernel call counts, mismatches, max |Δ| in ulps, serial seconds."""

    def __init__(self, numba: dict, cands: dict[str, dict]):
        self.numba, self.cands = numba, cands
        self.names = ["numba", *cands]
        self.calls: dict[str, int] = {}
        self.secs: dict[tuple[str, str], float] = {}
        self.bad: dict[tuple[str, str], int] = {}
        self.ulps: dict[tuple[str, str], float] = {}
        self.rot = 0

    def wrap(self, kname: str):
        outs = OUTPUTS[kname]

        def call(*args):
            self.calls[kname] = self.calls.get(kname, 0) + 1
            before = [args[i].copy() for i in outs]
            order = self.names[self.rot:] + self.names[:self.rot]
            self.rot = (self.rot + 1) % len(self.names)
            results = {}
            for name in order:
                for i, b in zip(outs, before):
                    args[i][...] = b
                fn = (self.numba if name == "numba" else self.cands[name])[kname]
                t0 = time.perf_counter()
                fn(*args)
                self.secs[(kname, name)] = (self.secs.get((kname, name), 0.0)
                                            + time.perf_counter() - t0)
                results[name] = [args[i].copy() for i in outs]
            ref = results["numba"]
            for name in self.cands:
                # a call differs once, however many of its planes do
                differs = False
                for a, b in zip(ref, results[name]):
                    if not np.array_equal(a.view(np.int64), b.view(np.int64)):
                        differs = True
                        self.ulps[(kname, name)] = max(
                            self.ulps.get((kname, name), 0), _max_ulps(a, b))
                if differs:
                    self.bad[(kname, name)] = self.bad.get((kname, name), 0) + 1
            for i, a in zip(outs, ref):
                args[i][...] = a

        return call


def agreement(case: str, numba: dict, cands: dict[str, dict]) -> None:
    print(f"\n## 1. Agreement and serial kernel time inside one {case} fit "
          "(threads = 1)\n")
    shadow = _Shadow(numba, cands)
    setup = _cases()[case]()
    compiled._KERNELS = {k: shadow.wrap(k) for k in OUTPUTS}
    try:
        _fit(setup)
    finally:
        compiled._KERNELS = numba
    names = list(cands)
    head = " | ".join(f"{LABEL[n]}: s · ×numba · calls differing (max ulp)"
                      for n in names)
    print(f"| kernel | calls | numba s | {head} |")
    print("|---|---|---|" + "---|" * len(names))
    tot = {n: 0.0 for n in ["numba", *names]}
    for k in OUTPUTS:
        if k not in shadow.calls:
            continue
        nb = shadow.secs[(k, "numba")]
        tot["numba"] += nb
        cells = []
        for n in names:
            s = shadow.secs[(k, n)]
            tot[n] += s
            bad = shadow.bad.get((k, n), 0)
            ulp = f" ({shadow.ulps[(k, n)]:.0f})" if bad else ""
            cells.append(f"{s:.3f} · {nb / s:.2f}× · {bad}{ulp}")
        print(f"| {k} | {shadow.calls[k]} | {nb:.3f} | " + " | ".join(cells) + " |")
    print(f"| **all** | | {tot['numba']:.3f} | "
          + " | ".join(f"{tot[n]:.3f} · {tot['numba'] / tot[n]:.2f}×" for n in names)
          + " |")


def end_to_end(case: str, numba: dict, cands: dict[str, dict], repeats: int) -> None:
    print(f"\n## 2. End to end, {case}, {repeats} interleaved repeats "
          f"(threads = {compiled.n_threads()})\n")
    setup = _cases()[case]()
    arms = {"numpy": None, "numba": numba, **cands}
    walls: dict[str, list[float]] = {a: [] for a in arms}
    finals: dict[str, list[dict[str, tuple[float, float | None]]]] = {
        a: [] for a in arms}
    rwp: dict[str, float] = {}
    for rep in range(repeats):
        order = list(arms)
        order = order[rep % len(order):] + order[:rep % len(order)]
        for arm in order:
            if arms[arm] is None:
                was = compiled.set_enabled(False)
            else:
                compiled._KERNELS = arms[arm]
                was = compiled.set_enabled(True)
            try:
                wall, res = _fit(setup)
            finally:
                compiled.set_enabled(was)
                compiled._KERNELS = numba
            walls[arm].append(wall)
            finals[arm].append({p.path: (p.value, p.stderr) for p in res.parameters})
            rwp[arm] = res.statistics.rwp
    # every repeat against numba's first, so an arm that varies run to run
    # (numba's own repeats included) cannot pass on its last repeat alone
    ref = finals["numba"][0]
    print("| arm | wall min–max s | median | ×numba (median) | Rwp | final θ vs numba |")
    print("|---|---|---|---|---|---|")
    med_nb = statistics.median(walls["numba"])
    for arm, ws in walls.items():
        gaps = sorted({_theta_gap(ref, got) for got in finals[arm]})
        same = " / ".join(gaps)
        print(f"| {LABEL.get(arm, arm)} | {min(ws):.2f}–{max(ws):.2f} | "
              f"{statistics.median(ws):.2f} | {med_nb / statistics.median(ws):.2f}× | "
              f"{rwp[arm]:.6f} | {same} |")


def _time_subprocess(code: str, env: dict | None = None, n: int = 5) -> list[float]:
    out = []
    for _ in range(n):
        t0 = time.perf_counter()
        subprocess.run([sys.executable, "-c", code], check=True,
                       env={**os.environ, **(env or {})}, cwd=HERE / "cython")
        out.append(time.perf_counter() - t0)
    return out


def startup() -> None:
    print("\n## 3. Startup, fresh process each (s, min–max of 5)\n")
    base = _time_subprocess("import numpy")
    rows = [("python + numpy", base)]
    for mod in CANDIDATES:
        try:
            importlib.import_module(mod)
        except ImportError:
            continue
        rows.append((f"+ import {mod}", _time_subprocess(f"import numpy, {mod}")))
    warm = ("from rietx.model import compiled; "
            "compiled.warm(block=True); assert compiled._KERNELS")
    rows.append(("+ rietx, numba warm (cache hit)", _time_subprocess(warm)))
    with tempfile.TemporaryDirectory() as d:
        cold = []
        for i in range(3):
            cold += _time_subprocess(warm, {"NUMBA_CACHE_DIR": f"{d}/{i}"}, n=1)
    rows.append(("+ rietx, numba warm (cold cache)", cold))
    rows.append(("+ rietx, tier off", _time_subprocess(
        "import rietx.model.compiled", {"RIETX_COMPILED": "0"})))
    for label, ts in rows:
        print(f"| {label} | {min(ts):.3f}–{max(ts):.3f} |")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repeats", type=int, default=5)
    ap.add_argument("--cases", default="trigger,cpd-1a")
    ap.add_argument("--skip", default="", help="comma list of 1,2,3")
    args = ap.parse_args(argv)
    skip = set(filter(None, args.skip.split(",")))
    import numba

    print(f"# WP-1939 AOT kernel spike — {platform.platform()}, python "
          f"{platform.python_version()}, numpy {np.__version__}, numba "
          f"{numba.__version__}, rietx {rx.__version__}")
    compiled.set_enabled(True)
    compiled.warm(block=True)
    numba_k = compiled._KERNELS
    cands = _candidates()
    for case in args.cases.split(","):
        if "1" not in skip:
            # serial: ``_spread`` runs a kernel inline when the pool it reads
            # has one worker, and it reads the count the pool was built with
            pool = compiled._pool()
            compiled._POOL_WORKERS = 1
            try:
                agreement(case, numba_k, cands)
            finally:
                compiled._POOL_WORKERS = pool._max_workers
        if "2" not in skip:
            end_to_end(case, numba_k, cands, args.repeats)
    if "3" not in skip:
        startup()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

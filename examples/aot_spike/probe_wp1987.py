"""WP-1987 probe (fork-only branch, never merged): does the numpy path
reproduce itself on the macOS Intel runner, and which BLAS call moves.

usage: probe_wp1987.py CASE N
"""
from __future__ import annotations

import hashlib
import os
import platform
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bench_aot_kernels as b  # noqa: E402
import numpy as np  # noqa: E402
import scipy  # noqa: E402
import scipy.linalg  # noqa: E402
from rietx.model import compiled  # noqa: E402


def sh(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True).stdout.strip()
    except Exception as e:  # noqa: BLE001
        return f"<{e}>"


def env_report():
    print(f"platform {platform.platform()} machine {platform.machine()} "
          f"python {platform.python_version()} numpy {np.__version__} "
          f"scipy {scipy.__version__} cpus {os.cpu_count()}")
    print("cpu:", sh(["sysctl", "-n", "machdep.cpu.brand_string"]))
    print("leaf7:", sh(["sysctl", "-n", "machdep.cpu.leaf7_features"]))
    for k in ("VECLIB_MAXIMUM_THREADS", "OPENBLAS_NUM_THREADS",
              "OMP_NUM_THREADS"):
        print(f"env {k}={os.environ.get(k)}")
    try:
        cfg = np.show_config(mode="dicts")
        bl = cfg["Build Dependencies"]["blas"]
        print("numpy blas:", bl.get("name"), bl.get("version"))
    except Exception as e:  # noqa: BLE001
        print("numpy blas: ?", e)
    try:
        cfg = scipy.show_config(mode="dicts")
        bl = cfg["Build Dependencies"]["blas"]
        print("scipy blas:", bl.get("name"), bl.get("version"))
    except Exception as e:  # noqa: BLE001
        print("scipy blas: ?", e)
    try:
        import threadpoolctl
        for d in threadpoolctl.threadpool_info():
            print("threadpool:", d.get("internal_api"), d.get("num_threads"),
                  d.get("version"), Path(d.get("filepath", "")).name)
    except Exception as e:  # noqa: BLE001
        print("threadpoolctl:", e)


def digest(a):
    return hashlib.sha1(np.ascontiguousarray(a).tobytes()).hexdigest()[:12]


def shifted(a, k):
    """a copy of ``a`` whose data starts k*8 bytes past a 64-byte boundary"""
    buf = np.empty(a.size + 16, dtype=np.float64)
    off = (-(buf.ctypes.data // 8) % 8) + k
    out = buf[off:off + a.size].reshape(a.shape)
    out[...] = a
    return out


def micro(reps=40):
    rng = np.random.default_rng(1987)
    J = rng.standard_normal((7000, 30)) * np.logspace(0, 6, 30)
    r = rng.standard_normal(7000)
    ops = {
        "J.T@J": lambda A: A.T @ A,
        "J.T@r": lambda A: A.T @ r,
        "np.lstsq": lambda A: np.linalg.lstsq(A, r, rcond=None)[0],
        "np.svd": lambda A: np.linalg.svd(A, full_matrices=False)[1],
        "sp.svd": lambda A: scipy.linalg.svd(A, full_matrices=False)[1],
        "np.eigh(JTJ)": lambda A: np.linalg.eigh(A.T @ A)[0],
        "np.solve(JTJ)": lambda A: np.linalg.solve(A.T @ A + np.eye(30),
                                                   A.T @ r),
        "np.norm": lambda A: np.array([np.linalg.norm(A[:, 0])]),
    }
    for name, f in ops.items():
        same_align = {digest(f(shifted(J, 0))) for _ in range(reps)}
        any_align = {digest(f(shifted(J, i % 8))) for i in range(reps)}
        print(f"micro {name:14s} distinct at one alignment: "
              f"{len(same_align)}/{reps}; across 8 alignments: "
              f"{len(any_align)}/{reps}")


def main():
    case, n = sys.argv[1], int(sys.argv[2])
    env_report()
    micro()
    sys.stdout.flush()
    compiled.set_enabled(True)
    wheel = compiled._kernels()
    print("wheel loaded:", wheel is not None)
    if wheel is not None:
        compiled._pool()
    compiled._POOL_WORKERS = 1
    compiled.set_enabled(False)
    fits = []
    for i in range(n):
        w, res = b._fit(b._cases()[case]())
        fin = {p.path: (p.value, p.stderr) for p in res.parameters}
        fits.append(fin)
        h = hashlib.sha1(repr(sorted(fin.items())).encode()).hexdigest()[:12]
        gap = b._theta_gap(fits[0], fin) if i else "(reference)"
        print(f"fit {i} {case} {w:.0f}s digest {h} vs fit 0: {gap}",
              flush=True)
    distinct = {repr(sorted(f.items())) for f in fits}
    print(f"RESULT {case} {os.environ.get('ARM')}: {len(distinct)} distinct "
          f"outcomes in {n} numpy-path fits")


if __name__ == "__main__":
    main()

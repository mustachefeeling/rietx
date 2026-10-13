"""Issue #780's monoclinic search, at a ceiling, with its wall and peak memory (WP-1924).

    python -m tests.repro_780 [CEILING] [--engines dichotomy,svd] [--cpu-clock]
                              [--trace]

The case is the WP's synthetic one: P 1 2/m 1, a = 4.541, b = 4.884,
c = 10.198 Å, β = 98.22° (V = 224 Å³), its 61 lines to 55° 2θ at Cu Kα1,
searched as monoclinic only with ``max_volume=600`` and no validation.
``CEILING`` (default 120 s) is both the whole-run ceiling and each unit's
slice, so a unit that overruns it shows in the wall.  The reporter's run was
``budget_seconds=900`` and took 1967 s and 9.0 GB on Linux x86-64.

It prints the wall, the process's peak memory (:func:`memory_bytes`), each
unit's clock, box count and completeness, and candidate 0; ``--trace`` adds
the sampled curve.  ``tracemalloc`` hides this peak (the WP's Context), so
nothing here traces allocations.

Wall clock moves with machine load a great deal, so quote it as a range with
the load named.  A ceiling cuts a search by the clock, so on a loaded machine
a unit reaches fewer boxes and a lower peak.  ``--cpu-clock`` counts the
ceiling in this process's CPU seconds instead (:func:`cpu_clock`), so two runs
under different load do the same work and their peaks compare.
"""

from __future__ import annotations

import os

if __name__ == "__main__":
    for _var in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
        os.environ.setdefault(_var, "1")
    os.environ.setdefault("RIETX_TELEMETRY", "0")

import argparse  # noqa: E402
import sys  # noqa: E402
import threading  # noqa: E402
import time  # noqa: E402

SPACE_GROUP = "P 1 2/m 1"
CELL = (4.541, 4.884, 10.198, 90.0, 98.22, 90.0)
TWO_THETA_MAX = 55.0
MAX_VOLUME = 600.0


def peaks():
    """The 61 exact positions to 55° 2θ, σ declared at 0.005°, built as the
    engine tests build theirs (``synthetic_peaks``, Cu Kα1)."""
    from tests.test_indexing_engines import synthetic_peaks

    peak_list, _cell = synthetic_peaks("monoclinic", sg=SPACE_GROUP, cell=CELL,
                                       two_theta_max=TWO_THETA_MAX)
    return peak_list


def spec(ceiling: float):
    from rietx.indexing.engines import SearchSpec

    return SearchSpec(systems=("monoclinic",), max_volume=MAX_VOLUME,
                      budget_seconds=ceiling, total_budget_seconds=ceiling)


def _darwin_rusage() -> tuple[int, int] | None:
    """(phys footprint, lifetime peak footprint) from ``proc_pid_rusage``, macOS.

    On macOS the resident set leaves out compressed pages, so under memory
    pressure ``ru_maxrss`` reads a fraction of what the process holds: a 500 MB
    array measured 369 MB resident and 518 MB of footprint on a loaded 16 GB
    machine.  The footprint is what Activity Monitor calls Memory.
    """
    import ctypes

    class _Info(ctypes.Structure):           # rusage_info_v4, padded
        _fields_ = [("uuid", ctypes.c_uint8 * 16), ("f", ctypes.c_uint64 * 64)]

    try:
        lib = ctypes.CDLL("/usr/lib/libSystem.B.dylib")
        buf = _Info()
        if lib.proc_pid_rusage(os.getpid(), 4, ctypes.byref(buf)) != 0:
            return None
    except OSError:
        return None
    # ri_phys_footprint and ri_lifetime_max_phys_footprint
    return int(buf.f[7]), int(buf.f[28])


def memory_bytes() -> tuple[int | None, int]:
    """(current, peak) memory of this process, the honest reading per platform.

    macOS: the physical footprint and its lifetime peak (:func:`_darwin_rusage`).
    Elsewhere: the resident set through psutil when it imports, and
    ``ru_maxrss``, the kernel's high-water mark, for the peak.
    """
    if sys.platform == "darwin":
        got = _darwin_rusage()
        if got is not None:
            return got
    try:
        import resource  # POSIX only
    except ImportError:
        peak = 0
    else:
        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        peak = int(peak if sys.platform == "darwin" else peak * 1024)
    try:
        import psutil
    except ImportError:
        return None, peak
    now = int(psutil.Process().memory_info().rss)
    return now, max(peak, now)


class MemorySampler:
    """Current memory every ``period`` seconds (:func:`memory_bytes`)."""

    def __init__(self, period: float = 0.5):
        self.period = period
        self.samples: list[tuple[float, int]] = []
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def _run(self) -> None:
        t0 = time.perf_counter()
        while not self._stop.is_set():
            now, _peak = memory_bytes()
            if now is not None:
                self.samples.append((time.perf_counter() - t0, now))
            self._stop.wait(self.period)

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, *exc):
        self._stop.set()
        self._thread.join()


def cpu_clock() -> None:
    """Make every indexing budget count this process's CPU seconds, not wall.

    A shared machine starves a search of CPU, so a wall-clock ceiling there
    covers a fraction of the boxes it covers on an idle one.  Under this clock
    a ceiling buys the same work under any load, which is what comparing two
    peaks needs.  Only ``engines``' own clock reads are swapped (``Budget``,
    ``Deadline``, ``Progress``); single-threaded BLAS keeps CPU time one core's.
    """
    import types

    from rietx.indexing import engines

    class _CpuTime(types.ModuleType):
        """``time`` itself, with ``monotonic`` read off the CPU clock."""

        monotonic = staticmethod(time.process_time)

        def __getattr__(self, name):
            return getattr(time, name)

    engines.time = _CpuTime("time")


def run(ceiling: float, engines: tuple[str, ...] | None = None) -> dict:
    """One ``index_pattern`` call on the case; returns what :func:`main` prints."""
    from rietx.indexing.workflow import index_pattern

    pk = peaks()
    with MemorySampler() as sampler:
        t0, c0 = time.perf_counter(), time.process_time()
        result = index_pattern(pk, spec=spec(ceiling), preset="full",
                               engines=engines, validate=False)
        wall, cpu = time.perf_counter() - t0, time.process_time() - c0
    return {"result": result, "wall": wall, "cpu": cpu,
            "peak": memory_bytes()[1], "samples": sampler.samples,
            "n_lines": len(pk.q())}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("ceiling", nargs="?", type=float, default=120.0)
    parser.add_argument("--engines", default=None,
                        help="comma-separated engine names (default: all)")
    parser.add_argument("--cpu-clock", action="store_true",
                        help="count the ceiling in CPU seconds (cpu_clock)")
    parser.add_argument("--trace", action="store_true",
                        help="print the sampled memory curve")
    args = parser.parse_args(argv)
    engines = tuple(args.engines.split(",")) if args.engines else None
    if args.cpu_clock:
        cpu_clock()

    out = run(args.ceiling, engines)
    res = out["result"]
    gb = 1024.0 ** 3
    print(f"lines {out['n_lines']}  ceiling {args.ceiling:g} s"
          f"{' (cpu)' if args.cpu_clock else ''}  wall {out['wall']:.1f} s  "
          f"cpu {out['cpu']:.1f} s  peak memory {out['peak'] / gb:.2f} GB  "
          f"load {_load()}")
    for key, value in sorted(res.engine_stats.items()):
        print(f"  {key}: {value:g}")
    print("search_complete:", res.search_complete)
    if res.candidates:
        c = res.candidates[0]
        print("candidate 0:", tuple(round(v, 4) for v in c.cell), c.system,
              c.centring, "found by", sorted(c.found_by))
    print("codes:", sorted({d.code for d in res.diagnostics}))
    if args.trace:
        for t, now in out["samples"]:
            print(f"  {t:7.1f} s  {now / gb:6.2f} GB")
    return 0


def _load() -> str:
    """The one-minute load average, or ``n/a`` where the OS has none (Windows)."""
    getloadavg = getattr(os, "getloadavg", None)
    return f"{getloadavg()[0]:.0f}" if getloadavg is not None else "n/a"


if __name__ == "__main__":
    sys.exit(main())

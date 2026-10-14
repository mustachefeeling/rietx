"""WP-1325 task "Scaling measured": dense against blocked joint Jacobian, N = 10, 70, 300.

    .venv/bin/python docs/wp/1325-measure/scaling.py [--sizes=10,70,300] [--repeats=2]
        > docs/wp/1325-measure/scaling_results.txt

Run from the repository root, alone on the machine (every figure is a wall
clock or a peak RSS).  The library is ``tests/test_parametric_series.py``'s
``library(n)``: n LaB6 patterns of 3 000 points (λ = 0.4139 Å, Poisson
noise, ``tests/test_sequential.py``'s ``_simulate``) at random positions on a
[0, 1]² wafer, the cell on a known surface a(x, y) = A0·(1 + 2e-3·x +
1.5e-3·y + 1e-3·x·y), refined as one ``polynomial`` ``ParametricTie`` with
terms 1, x, y, x·y.  The instrument is **per pattern**: under
``mccusker_default`` each pattern frees ten own columns (scale, three
background terms, zero, U, V, W, X, Y) beside the four shared coefficients,
n = 4 + 10·N, the WP's "20 shared + 10 private" shape with four shared.
Every fit starts at ``_start_models()`` (cell 0.1 % long, scale ×1.5, W ×1.5,
no zero shift, a flat background).

Each case (N, layout, repeat) runs in a subprocess of its own: the measuring
process starts one worker and reads ``resource.getrusage(RUSAGE_CHILDREN)``
after it, so the peak RSS is that worker's alone.  The worker also reports
its RSS before the fit (library simulated, models not yet compiled), and
splits its fit's wall clock into the per-pattern Jacobians, the normal
equations (A = JᵀJ, b = −Jᵀr), the LM step solve (BVLS or projected CG), and
the covariance — the split that decides between the WP's route (i) and
route (ii).  The layout is forced with ``blocked.set_layout``.

Dense at N = 300 is not run: its Jacobian alone is 21.6 GB against the
machine's total, so the script prints the bytes instead of handing the case to
the OOM killer.  ``RIETX_TELEMETRY=0`` keeps every fit from writing a run
directory.
"""

from __future__ import annotations

import json
import os
import platform
import resource
import subprocess
import sys
import time
from pathlib import Path

os.environ.setdefault("RIETX_TELEMETRY", "0")

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

import numpy as np  # noqa: E402

N_POINTS = 3000
N_SHARED = 4
N_OWN = 10


def dense_bytes(n: int) -> int:
    return 8 * N_POINTS * n * (N_SHARED + N_OWN * n)


def mem_total() -> int:
    for line in Path("/proc/meminfo").read_text().splitlines():
        if line.startswith("MemTotal:"):
            return int(line.split()[1]) * 1024
    return 0


def vm(field: str) -> int:
    """``/proc/self/status``'s ``field`` (VmRSS, VmHWM) in bytes."""
    for line in Path("/proc/self/status").read_text().splitlines():
        if line.startswith(field + ":"):
            return int(line.split()[1]) * 1024
    return 0


# -- the worker: one fit ------------------------------------------------------

def worker(n: int, layout: str) -> dict:
    from rietx.multi import MultiHistogramRefinement
    from rietx.optimize import blocked, lm
    from rietx.optimize import least_squares as ls
    from tests.test_parametric_series import library, library_truth
    from tests.test_sequential import _start_models

    split = {"jacobian": 0.0, "normal_equations": 0.0, "step": 0.0, "covariance": 0.0}
    counts = {"jacobian": 0, "step": 0}

    def timed(fn, key):
        def wrapped(*a, **kw):
            t = time.perf_counter()
            try:
                return fn(*a, **kw)
            finally:
                split[key] += time.perf_counter() - t
                if key in counts:
                    counts[key] += 1
        return wrapped

    lm._normal_equations = timed(lm._normal_equations, "normal_equations")
    lm._solve_step = timed(lm._solve_step, "step")
    ls._guarded_covariance = timed(ls._guarded_covariance, "covariance")
    closures = ls._multi_closures

    def multi_closures(*a, **kw):
        residual, jacobian, n_data = closures(*a, **kw)
        return residual, timed(jacobian, "jacobian"), n_data

    ls._multi_closures = multi_closures

    class Probe(MultiHistogramRefinement):
        def _build_result(self, models, outcome, *args, **kwargs):
            self.outcome_ = outcome
            t = time.perf_counter()
            try:
                return super()._build_result(models, outcome, *args, **kwargs)
            finally:
                self.build_seconds = time.perf_counter() - t

    t = time.perf_counter()
    patterns, coords, tie = library(n)
    simulate = time.perf_counter() - t
    rss_before = vm("VmRSS")
    blocked.set_layout(layout)
    s, ins = _start_models()
    ref = Probe(s, [ins] * n, coordinates=coords, parametric=[tie])
    t = time.perf_counter()
    result = ref.fit(patterns, plan="mccusker_default")
    wall = time.perf_counter() - t
    truth = library_truth(result.parametric[0].reference)
    return {
        "n": n, "layout": layout, "recorded_layout": ref.outcome_.jacobian_layout,
        "n_cols": len(ref.mtable.free_paths), "points": len(patterns[0].two_theta),
        "status": result.status, "rwp": result.statistics.rwp,
        "iterations": [st.n_iterations for st in result.stages],
        "wall": wall, "simulate": simulate, "build_result": ref.build_seconds,
        "split": split, "counts": counts, "rss_before": rss_before,
        "rss_self_peak": vm("VmHWM"),
        "coefficients": [{"term": c.term, "value": c.value, "esd": c.esd,
                          "truth": truth[c.term]} for c in result.parametric],
        "reference": result.parametric[0].reference,
    }


# -- the measuring process: one worker, its peak ------------------------------

def measure(n: int, layout: str) -> dict:
    proc = subprocess.run([sys.executable, __file__, f"--worker={n},{layout}"],
                          capture_output=True, text=True, check=False, cwd=REPO)
    peak = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss * 1024
    if proc.returncode != 0:
        return {"n": n, "layout": layout, "error": proc.stderr[-2000:],
                "returncode": proc.returncode, "rss_peak": peak}
    out = json.loads(proc.stdout.strip().splitlines()[-1])
    out["rss_peak"] = peak
    return out


def run_case(n: int, layout: str) -> dict:
    """One case, measured in a fresh process so ``RUSAGE_CHILDREN`` is its own."""
    proc = subprocess.run([sys.executable, __file__, f"--measure={n},{layout}"],
                          capture_output=True, text=True, check=False, cwd=REPO)
    if proc.returncode != 0:
        return {"n": n, "layout": layout, "error": proc.stderr[-2000:]}
    return json.loads(proc.stdout.strip().splitlines()[-1])


# -- the report ---------------------------------------------------------------

def others_running() -> list[str]:
    ps = subprocess.run(["ps", "-eo", "pid,etime,args"], capture_output=True, text=True,
                        check=False).stdout.splitlines()
    mine = str(os.getpid())
    return [ln.strip() for ln in ps
            if ("python" in ln and ("pytest" in ln or "1325-measure" in ln
                                    or "kernel_ramp" in ln))
            and "scaling.py" not in ln and "ps -eo" not in ln
            and not ln.strip().startswith(mine)]


def machine() -> list[str]:
    import rietx
    from rietx.model import compiled

    cpu = ""
    for line in Path("/proc/cpuinfo").read_text().splitlines():
        if line.startswith("model name"):
            cpu = line.split(":", 1)[1].strip()
            break
    load = os.getloadavg()
    running = others_running()
    return [
        f"machine   {platform.system()} {platform.machine()}, {os.cpu_count()} CPUs "
        f"({cpu}), {mem_total() / 2**30:.1f} GiB RAM, no swap",
        f"python    {platform.python_version()}, numpy {np.__version__} "
        f"({np.show_config(mode='dicts')['Build Dependencies']['blas']['name']})",
        f"rietx     {rietx.__version__} from {Path(rietx.__file__).parent} ([dev] venv), "
        f"compiled kernels {'on' if compiled.enabled() else 'off'}",
        f"load      {load[0]:.2f} {load[1]:.2f} {load[2]:.2f} (1/5/15 min) at start; "
        f"other measuring or test processes running: {len(running)}",
        *[f"          {ln}" for ln in running],
    ]


def gib(x: float) -> str:
    return f"{x / 2**30:6.2f}"


def span(xs: list[float]) -> str:
    return f"{min(xs):.1f}" if len(xs) == 1 else f"{min(xs):.1f}-{max(xs):.1f}"


def head() -> str:
    return subprocess.run(["git", "-C", str(REPO), "rev-parse", "--short", "HEAD"],
                          capture_output=True, text=True, check=False).stdout.strip()


def src_fingerprint() -> str:
    """sha256 over every ``src/`` python file, the code each worker imports
    afresh: another session editing the tree mid-run shows here."""
    import hashlib

    h = hashlib.sha256()
    for p in sorted((REPO / "src").rglob("*.py")):
        h.update(str(p.relative_to(REPO)).encode())
        h.update(p.read_bytes())
    return h.hexdigest()[:12]


tree_note = ""


def main(sizes: list[int], repeats: int) -> None:
    global tree_note
    print(__doc__.split("\n\n")[0])
    print()
    for line in machine():
        print(line)
    start = src_fingerprint()
    print(f"tree      HEAD {head()} at start, src/ fingerprint {start}")
    print(f"library   {N_POINTS} points a pattern, n = {N_SHARED} + {N_OWN}·N columns; "
          f"dense J = 8·{N_POINTS}·N·n bytes")
    print()
    rows: dict[tuple[int, str], list[dict]] = {}
    total = mem_total()
    for n in sizes:
        for layout in ("dense", "blocked"):
            if layout == "dense" and dense_bytes(n) > 0.6 * total:
                rows[n, layout] = []
                print(f"[skip] N={n} dense: J alone {gib(dense_bytes(n))} GiB of "
                      f"{gib(total)} GiB", flush=True)
                continue
            for k in range(repeats):
                r = run_case(n, layout)
                rows.setdefault((n, layout), []).append(r)
                if "error" in r:
                    print(f"[fail] N={n} {layout} #{k}: {r['error'][-400:]}", flush=True)
                else:
                    print(f"[done] N={n} {layout} #{k}: wall {r['wall']:.1f} s, "
                          f"peak {gib(r['rss_peak'])} GiB, {r['status']}, "
                          f"load {os.getloadavg()[0]:.2f}", flush=True)
    end = src_fingerprint()
    tree_note = (f"src/ fingerprint {end}, unchanged during the run" if end == start
                 else f"src/ CHANGED during the run ({start} → {end}): a later case "
                      "imported other code than an earlier one")
    print()
    print("== wall clock (s, range over repeats) and peak RSS (GiB) per case ==")
    print("   N  layout    cols  dense-J GiB   fit wall     jacobian   normal-eq"
          "    step        covariance  result   peak RSS  RSS before fit")
    for n in sizes:
        for layout in ("dense", "blocked"):
            tried = rows.get((n, layout), [])
            rs = [r for r in tried if "error" not in r]
            if not rs:
                why = ("failed, above" if tried
                       else f"not run: J alone is {gib(dense_bytes(n)).strip()} GiB, "
                            f"over 60 % of {gib(total).strip()} GiB")
                print(f"{n:4d}  {layout:8s}  {N_SHARED + N_OWN * n:5d}  "
                      f"{gib(dense_bytes(n))}   {why}")
                continue
            sp = [r["split"] for r in rs]
            print(f"{n:4d}  {layout:8s}  {rs[0]['n_cols']:5d}  {gib(dense_bytes(n))}"
                  f"   {span([r['wall'] for r in rs]):>10s}"
                  f"   {span([s['jacobian'] for s in sp]):>9s}"
                  f"   {span([s['normal_equations'] for s in sp]):>9s}"
                  f"   {span([s['step'] for s in sp]):>9s}"
                  f"   {span([s['covariance'] for s in sp]):>9s}"
                  f"   {span([r['build_result'] for r in rs]):>7s}"
                  f"   {gib(max(r['rss_peak'] for r in rs))}"
                  f"   {gib(max(r['rss_before'] for r in rs))}")
    print()
    print("== counts per fit (identical across repeats) ==")
    for (n, layout), rs in rows.items():
        rs = [r for r in rs if "error" not in r]
        if rs:
            r = rs[0]
            print(f"{n:4d}  {layout:8s}  recorded {r['recorded_layout']:7s}  {r['status']}, "
                  f"Rwp {r['rwp']:.6f}, stage iterations {r['iterations']}, "
                  f"{r['counts']['jacobian']} joint Jacobians, "
                  f"{r['counts']['step']} step solves")
    print()
    print("== the surface recovered (Å, per unit x and y about the reference) ==")
    for n in sizes:
        for layout in ("dense", "blocked"):
            rs = [r for r in rows.get((n, layout), []) if "error" not in r]
            if not rs:
                continue
            r = rs[0]
            ref = ", ".join(f"{k}={v:.4f}" for k, v in r["reference"].items())
            print(f"{n:4d}  {layout:8s}  reference {ref}")
            for c in r["coefficients"]:
                z = (c["value"] - c["truth"]) / c["esd"]
                print(f"        {c['term']:4s}  {c['value']:.8f} ± {c['esd']:.2e}"
                      f"   truth {c['truth']:.8f}   (fit − truth)/esd {z:+.2f}")
    print()
    print("== dense against blocked on the same library ==")
    for n in sizes:
        d = [r for r in rows.get((n, "dense"), []) if "error" not in r]
        b = [r for r in rows.get((n, "blocked"), []) if "error" not in r]
        if d and b:
            dz = max(abs(x["value"] - y["value"]) / x["esd"]
                     for x, y in zip(d[0]["coefficients"], b[0]["coefficients"],
                                     strict=True))
            de = max(abs(x["esd"] - y["esd"]) / x["esd"]
                     for x, y in zip(d[0]["coefficients"], b[0]["coefficients"],
                                     strict=True))
            print(f"{n:4d}  coefficients: worst |blocked − dense|/esd {dz:.1e}, "
                  f"worst esd ratio − 1 {de:.1e}; wall dense/blocked "
                  f"{min(r['wall'] for r in d) / min(r['wall'] for r in b):.1f}x")
    print()
    print("== where dense stops being possible, and what blocked holds instead ==")
    ratio = None
    for n in sizes:
        d = [r for r in rows.get((n, "dense"), []) if "error" not in r]
        if d:
            peak = max(r["rss_peak"] for r in d)
            base = max(r["rss_before"] for r in d)
            ratio = (peak - base) / dense_bytes(n)
            print(f"{n:4d}  dense:   peak − RSS before fit = {gib(peak - base)} GiB "
                  f"= {ratio:.2f} × J")
    for n in sizes:
        b = [r for r in rows.get((n, "blocked"), []) if "error" not in r]
        if b:
            peak = max(r["rss_peak"] for r in b)
            base = max(r["rss_before"] for r in b)
            cols = b[0]["n_cols"]
            print(f"{n:4d}  blocked: peak − RSS before fit = {gib(peak - base)} GiB "
                  f"= {(peak - base) / (8 * cols * cols):.1f} × one n × n array "
                  f"({8 * cols * cols / 2**20:.0f} MiB at n = {cols})")
    alone = max(n for n in range(1, 5000) if dense_bytes(n) <= total)
    print(f"      J alone passes the machine's {gib(total).strip()} GiB at N = {alone + 1} "
          f"({gib(dense_bytes(alone + 1)).strip()} GiB)")
    if ratio is not None:
        base = max((r["rss_before"] for rs in rows.values() for r in rs
                    if "error" not in r), default=0)
        n_max = max(n for n in range(1, 5000) if ratio * dense_bytes(n) + base <= total)
        print(f"      at the largest dense case's {ratio:.2f} × J over the "
              f"{gib(base).strip()} GiB the library and interpreter hold, a dense fit "
              f"fits up to N ≈ {n_max} ({gib(dense_bytes(n_max)).strip()} GiB of J; an "
              f"extrapolation, not run); N = 300 would need "
              f"{gib(ratio * dense_bytes(300) + base).strip()} GiB")
    print()
    for line in machine()[3:]:
        print(line.replace("at start", "at end"))
    print(f"tree      HEAD {head()} at end; {tree_note}")


if __name__ == "__main__":
    args = dict(a.lstrip("-").split("=", 1) for a in sys.argv[1:] if "=" in a)
    if "worker" in args:
        n, layout = args["worker"].split(",")
        print(json.dumps(worker(int(n), layout)))
    elif "measure" in args:
        n, layout = args["measure"].split(",")
        print(json.dumps(measure(int(n), layout)))
    else:
        main([int(x) for x in args.get("sizes", "10,70,300").split(",")],
             int(args.get("repeats", "2")))

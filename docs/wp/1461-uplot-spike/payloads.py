"""WP-1461 task 2: D4 and D8 on real payloads, the server's half.

Builds three real answers:

- the NAC example fitted through a ``GuiSession``, as the GUI fits it;
- the ``nac`` compare standard under the first four variants its catalog lists;
- the QPA sample-1 series, chained under the acceptance suite's protocol.

For each it builds the payload today's route sends, the same shape at full
resolution, and the proposed shape. The proposal sends the whole measured
pattern once, the index of the channels the fit kept, and the model's arrays
on those channels. It is written as JSON, as JSON at seven significant digits,
and as float64 and float32 binary. This script times building and serialising
each one; ``payload_probe.mjs`` times the browser's half from the files it
writes to ``payloads/``.

Also checked here, because the proposal rests on them: the fitted grid is an
exact subset of the pattern's own grid, the result's ``y_obs`` is the
pattern's own intensity on it, and every compare variant fits the same
channels.

    PYTHONPATH=. .venv/bin/python docs/wp/1461-uplot-spike/payloads.py [nac|compare[:standard]|series|sizes ...]
"""
from __future__ import annotations

import os

os.environ.setdefault("RIETX_TELEMETRY", "0")

import json  # noqa: E402
import struct  # noqa: E402
import sys  # noqa: E402
import tempfile  # noqa: E402
import time  # noqa: E402
from dataclasses import asdict, replace  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
OUT = HERE / "payloads"
REPS = 7
FULL = 10**9   # a max_points no pattern reaches: the routes return every channel

import rietx as rx  # noqa: E402
from rietx.gui.server import _dumps  # noqa: E402
from rietx.gui.session import GuiSession, curve_window  # noqa: E402
from rietx.project import fitted_mask  # noqa: E402
from rietx.viz import compare as cmp  # noqa: E402

MANIFEST: list[dict] = []
LINES: list[str] = []


def say(line: str = "") -> None:
    print(line, flush=True)
    LINES.append(line)


def timed(fn):
    """Run ``fn`` REPS times; return its last answer and the times after the first."""
    out, ts = None, []
    for _ in range(REPS):
        t0 = time.perf_counter()
        out = fn()
        ts.append((time.perf_counter() - t0) * 1e3)
    return out, ts[1:]


def span(ts) -> str:
    return f"{min(ts):.1f}-{max(ts):.1f} ms"


def pack(header: dict, arrays: dict[str, np.ndarray]) -> bytes:
    """uint32 header length, a JSON header padded to 8 bytes, then 8-aligned arrays.

    Offsets in the header are from the first array. Little-endian, which is what
    every browser's typed arrays read on the machines rietx runs on.
    """
    specs, blobs, off = [], [], 0
    for name, a in arrays.items():
        raw = np.ascontiguousarray(a).tobytes()
        specs.append({"name": name, "dtype": a.dtype.str, "offset": off,
                      "length": len(a)})
        pad = -len(raw) % 8
        blobs.append(raw + b"\0" * pad)
        off += len(raw) + pad
    head = json.dumps({**header, "arrays": specs}).encode()
    head += b" " * (-(4 + len(head)) % 8)
    return struct.pack("<I", len(head)) + head + b"".join(blobs)


def json7(header: dict, arrays: dict[str, np.ndarray]) -> bytes:
    """The same JSON with every float at seven significant digits."""
    body = []
    for name, a in arrays.items():
        fmt = "{:d}" if a.dtype.kind in "iu" else "{:.7g}"
        body.append(f'"{name}":[' + ",".join(map(fmt.format, a.tolist())) + "]")
    head = json.dumps(header)[1:-1]
    return ("{" + ",".join(body) + ("," + head if head else "") + "}").encode()


def write(name: str, body: bytes, kind: str, **extra) -> None:
    (OUT / name).write_bytes(body)
    MANIFEST.append({"file": name, "kind": kind, "bytes": len(body), **extra})


def f32_error(arrays: dict[str, np.ndarray]) -> str:
    """The largest relative error float32 puts on each array, as a reader would see it."""
    out = []
    for name, a in arrays.items():
        if a.dtype.kind != "f":
            continue
        b = a.astype(np.float32).astype(np.float64)
        scale = np.maximum(np.abs(a), 1e-300)
        out.append(f"{name} {np.max(np.abs(b - a) / scale):.1e}")
    return ", ".join(out)


def rebase_error(cum: np.ndarray) -> str:
    """Σχ² over a window as cum[j] − cum[i−1], in float32 against float64.

    D4 re-bases the cumulative curve at each client zoom, and float32 loses the
    low digits of a large running sum first.
    """
    rng = np.random.default_rng(0)
    c32 = cum.astype(np.float32).astype(np.float64)
    n, worst = len(cum), {}
    for frac in (0.001, 0.01, 0.1):
        w = max(2, int(n * frac))
        errs = []
        for i in rng.integers(1, n - w, 200):
            exact = cum[i + w] - cum[i - 1]
            errs.append(abs((c32[i + w] - c32[i - 1]) - exact) / exact)
        worst[frac] = max(errs)
    return ", ".join(f"{f:.1%} of the pattern {e:.1e}" for f, e in worst.items())


def proposed(stem: str, tt_all, y_all, keep, res, *, weighted: bool) -> dict:
    """The proposed payload for one fitted pattern, in four encodings.

    Checks the two facts it rests on before building anything: the result's
    grid is the pattern's own grid under ``keep``, bit for bit, and so is its
    ``y_obs``.
    """
    idx = np.flatnonzero(keep)
    tt_fit = np.asarray(res.two_theta, dtype=float)
    grid_ok = np.array_equal(tt_all[idx], tt_fit)
    obs_ok = np.array_equal(y_all[idx], np.asarray(res.y_obs, dtype=float))
    say(f"  fitted grid is the pattern's grid under the mask: {grid_ok}; "
        f"y_obs is the pattern's intensity there: {obs_ok}")

    def build():
        y_obs = np.asarray(res.y_obs, dtype=float)
        y_calc = np.asarray(res.y_calc, dtype=float)
        sigma = res.sig()
        raw = y_obs - y_calc
        delta = raw / sigma
        return {"two_theta": tt_all, "y_obs": y_all,
                "fitted": idx.astype(np.int32),
                "y_calc": y_calc,
                "y_background": np.asarray(res.y_background, dtype=float),
                "delta": delta, "delta_raw": raw,
                "cumulative_chi2": np.cumsum(delta**2)}

    arrays, t_build = timed(build)
    header = {"weighted": weighted, "ticks": res.ticks, "tick_hkl": res.tick_hkl,
              "n_total": len(tt_all), "n_fitted": len(idx)}
    say(f"  proposed: {len(tt_all)} channels, {len(idx)} fitted; arrays built in "
        f"{span(t_build)}")

    def as_json():
        return _dumps({**header, **{k: v.tolist() for k, v in arrays.items()}}).encode()

    encodings = {
        "json": as_json,
        "json7": lambda: json7(header, arrays),
        "f64": lambda: pack(header, arrays),
        "f32": lambda: pack(header, {k: v.astype(np.float32) if v.dtype.kind == "f"
                                     else v for k, v in arrays.items()}),
    }
    for enc, fn in encodings.items():
        body, ts = timed(fn)
        write(f"{stem}_B_{enc}.{'bin' if enc.startswith('f') else 'json'}", body,
              f"B_{enc}", n=len(tt_all), n_fitted=len(idx))
        say(f"    B {enc:5s} {len(body)/1e6:6.2f} MB, serialised in {span(ts)}")
    say(f"  float32's largest relative error: {f32_error(arrays)}")
    say(f"  Σχ² re-based in float32: {rebase_error(arrays['cumulative_chi2'])}")
    return arrays


def run_nac() -> None:
    say("== NAC example, fitted through a GuiSession")
    state = Path(tempfile.mkdtemp(prefix="wp1461-payloads-"))
    s = GuiSession(state_dir=state)
    s.example_open({"name": "nac"})
    t0 = time.perf_counter()
    s.run({"kind": "fit"})
    while s.run_state()["state"] != "idle":
        time.sleep(0.2)
    say(f"  fit took {time.perf_counter() - t0:.0f} s")
    p = s.project
    res = p.refinement.result_
    for label, mp in (("today, one window", 4000), ("today's shape, every channel", FULL)):
        payload, t_build = timed(lambda mp=mp: s.result_window(None, None, mp))
        body, t_ser = timed(lambda payload=payload: _dumps(payload).encode())
        stem = "nac_A_4000" if mp == 4000 else "nac_A_full"
        write(f"{stem}.json", body, "A_json", n_fitted=len(payload["two_theta"]),
              n_masked=len(payload["excluded"]["two_theta"]))
        say(f"  {label}: {len(payload['two_theta'])} fitted + "
            f"{len(payload['excluded']['two_theta'])} masked points, "
            f"{len(body)/1e6:.2f} MB; built {span(t_build)}, serialised {span(t_ser)}")
    proposed("nac", p.data.tt(), p.data.y(), p.fitted_mask(), res,
             weighted=p.data_ref.has_sigma)


def run_compare(key: str = "nac", n_variants: int = 4) -> None:
    say(f"== compare standard `{key}`")
    cat = cmp.catalog()
    std = next(x for x in cat["standards"] if x["key"] == key)
    variants = std["variants"][:n_variants]
    say(f"  variants: {', '.join(variants)}")
    recs = {}
    for v in variants:
        t0 = time.perf_counter()
        recs[v] = cmp.run(key, v, max_points=FULL)
        say(f"  {v}: {recs[v].status}, {len(recs[v].two_theta)} channels, "
            f"{time.perf_counter() - t0:.0f} s")
    first = recs[variants[0]]
    same_tt = all(np.array_equal(first.two_theta, r.two_theta) for r in recs.values())
    same_obs = all(np.array_equal(first.y_obs, r.y_obs) for r in recs.values())
    say(f"  every variant fits the same channels: {same_tt}; the same y_obs: {same_obs}")

    def decimated(rec):
        tt = np.asarray(rec.two_theta)
        idx = cmp.decimation_index(
            tt, [np.asarray(rec.y_obs), np.asarray(rec.y_calc), np.asarray(rec.delta)], 4000)
        cut = {k: np.asarray(getattr(rec, k))[idx].tolist() for k in (
            "two_theta", "y_obs", "y_calc", "y_background", "delta", "cumulative_chi2")}
        return replace(rec, **cut)

    log = [f"  {key} / {v}: done" for v in variants]
    for label, stem, recs_ in (("today, 4000 a variant", f"cmp_{key}_A_4000",
                                {v: decimated(r) for v, r in recs.items()}),
                               ("today's shape, every channel", f"cmp_{key}_A_full", recs)):
        snap = {"records": {v: asdict(r) for v, r in recs_.items()}, "queued": [],
                "busy": False, "log": log}
        body, ts = timed(lambda snap=snap: json.dumps(snap).encode())
        write(f"{stem}.json", body, "cmp_json", n_variants=len(recs_))
        say(f"  /api/state {label}, {len(recs_)} variants: {len(body)/1e6:.2f} MB, "
            f"serialised {span(ts)}; sent on every 700 ms poll")
    scalars = {"records": {v: {k: val for k, val in asdict(r).items() if not isinstance(val, list)
                               or k in ("diagnostics", "parameters")}
                           for v, r in recs.items()}, "queued": [], "busy": False, "log": log}
    body = json.dumps(scalars).encode()
    say(f"  /api/state without the curves: {len(body)/1e3:.1f} kB")

    def arrays(rec, dtype):
        return {k: np.asarray(getattr(rec, k), dtype=dtype) for k in (
            "two_theta", "y_obs", "y_calc", "y_background", "delta", "cumulative_chi2")}

    for enc, dtype in (("f64", np.float64), ("f32", np.float32)):
        body, ts = timed(lambda dtype=dtype: pack({}, arrays(first, dtype)))
        write(f"cmp_{key}_B_{enc}.bin", body, f"cmp_{enc}", n=len(first.two_theta))
        say(f"  one variant's curves, {enc}: {len(body)/1e6:.2f} MB, serialised {span(ts)}; "
            f"fetched once, when the variant lands")
    say(f"  Σχ² re-based in float32: {rebase_error(np.asarray(first.cumulative_chi2))}")


def run_series() -> None:
    from rietx.gui import series as series_mod
    from tests.test_acceptance_sequential import (
        CARRY,
        SAMPLE1,
        _patterns,
        _phases,
        _seed_hook,
        qarr_instrument,
        qpa_plan,
    )

    say("== QPA sample-1 series, the acceptance protocol")
    patterns = _patterns()
    runner = rx.SequentialRefinement(rx.Structure(phases=_phases()), qarr_instrument(),
                                     carry=CARRY)
    t0 = time.perf_counter()
    result = runner.fit(patterns, labels=list(SAMPLE1), plan=qpa_plan(), prepare=_seed_hook)
    say(f"  {len(patterns)} patterns chained in {time.perf_counter() - t0:.0f} s")
    payload = series_mod.result_payload(result, None, running=False,
                                        curves=[True] * len(patterns))
    body, ts = timed(lambda: _dumps(payload).encode())
    write("series_result.json", body, "series_result")
    say(f"  /api/series/result (entries and trajectories): {len(body)/1e3:.1f} kB, "
        f"serialised {span(ts)}")
    data, res = patterns[0], runner.results_[0]
    keep = fitted_mask(data, None)
    for mp in (4000, FULL):
        win, t_build = timed(lambda mp=mp: curve_window(res, None, None, mp, weighted=False))
        body, t_ser = timed(lambda win=win: _dumps(win).encode())
        stem = "series0_A_4000" if mp == 4000 else "series0_A_full"
        write(f"{stem}.json", body, "A_json", n_fitted=len(win["two_theta"]), n_masked=0)
        say(f"  member 0, max_points {mp}: {len(win['two_theta'])} points, "
            f"{len(body)/1e6:.2f} MB; built {span(t_build)}, serialised {span(t_ser)}")
    proposed("series0", data.tt(), data.y(), keep, res, weighted=False)


def run_sizes() -> None:
    """Channel counts of every pattern this repository reads, for the ceiling."""
    say("== channel counts of the patterns on disk")
    seen = []
    roots = [ROOT / "tests" / "data", ROOT / "tests" / "data" / "qarr",
             ROOT / "src" / "rietx" / "data" / "examples", cmp.default_data_dir()]
    for root in dict.fromkeys(roots):
        if not root.is_dir():
            continue
        for f in sorted(root.iterdir()):
            if not f.is_file() or f.suffix.lower() in {".cif", ".prm", ".json", ".md", ".txt",
                                                        ".inst", ".instprm", ".gpx", ".exp",
                                                        ".dat", ".py", ".png", ".rd"}:
                continue
            try:
                n = len(rx.read_pattern(f).two_theta)
            except Exception as exc:  # a non-pattern, or one needing options
                n = f"refused ({type(exc).__name__})"
            seen.append((f.relative_to(ROOT) if f.is_relative_to(ROOT) else f, n))
    for f, n in seen:
        say(f"  {n!s:>24}  {f}")


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    wanted = sys.argv[1:] or ["nac", "compare", "series", "sizes"]
    say(f"payloads.py {' '.join(wanted)}  (numpy {np.__version__}, "
        f"rietx {rx.__version__}, {REPS - 1} timed runs after one warm-up)")
    for part in wanted:
        name, _, arg = part.partition(":")
        fn = {"nac": run_nac, "compare": run_compare, "series": run_series,
              "sizes": run_sizes}[name]
        fn(arg) if arg else fn()
    old = json.loads((OUT / "manifest.json").read_text()) if (OUT / "manifest.json").exists() else []
    names = {m["file"] for m in MANIFEST}
    (OUT / "manifest.json").write_text(json.dumps(
        [m for m in old if m["file"] not in names] + MANIFEST, indent=1))

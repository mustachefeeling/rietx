"""Replay indexing engine units to completion and digest them (WP-1519).

    python -m tests.unit_replay capture DIR [DATASET ...]
    python -m tests.unit_replay replay DIR [UNIT ...] [--save] [--count]
    python -m tests.unit_replay pool DIR DATASET

The bar every indexing speed-up since WP-1508 has been held to: each finished
unit's candidates bit for bit, never a green suite.  WP-1508, 1509 and 1518
each rebuilt this in session scratch; this is the fourth build, committed.

**capture** swaps every entry of ``engines._REGISTRY`` for a recorder and runs
``index_pattern`` once per dataset, its spec at a :data:`BUDGET` no unit
reaches.  A recorder keeps (engine, peaks, spec, quality, kwargs) and returns
an empty result, so a capture costs the peak pick and nothing else.  One
pickle per (dataset, engine, system) unit lands in DIR.  A dataset that names
its engine skips ``index_pattern`` (:data:`DATASETS`).

**replay** runs a captured unit's engine to completion (no token, no progress)
and prints its digest, the sha256 of ``np.array([[*cell, n_indexed] …],
float64).tobytes()`` (first 8 hex), its wall, and the wall spent inside
``engines._dedup_groups``.  ``--count`` also counts the χ² tests dedup asked of
``reduce.equal_reduced``, at the cost of a wrapper on every one.  ``--save``
keeps the result for **pool**, which folds a dataset's saved units per engine
(``merge_engine_units``), pools them as ``consensus.merge_engine_candidates``
does, times ``dedup_groups`` over the pool and digests its groups.

**A digest belongs to a platform** (WP-1518): it hashes the cells' bits, and
none of WP-1509's Linux x86-64 digests reproduced on macOS arm64.  One BLAS
thread is set below unless the caller set one, because every timing quoted
against these units was taken that way.
"""

from __future__ import annotations

import os

for _var in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_var, "1")
os.environ.setdefault("RIETX_TELEMETRY", "0")

import argparse  # noqa: E402
import hashlib  # noqa: E402
import pickle  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402
from dataclasses import replace  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402

#: A budget no unit reaches, so a replay is a finished search (WP-1509's 1e5 s).
BUDGET = 1e5


def _qarr_dataset(name: str, systems: tuple[str, ...], max_volume: float) -> dict:
    """An IUCr round-robin phase, picked and specified as the acceptance suite does."""
    from rietx.indexing.engines import SearchSpec
    from rietx.indexing.pick import pick_peaks
    from tests.test_acceptance_indexing import REAL_DATA_N_UNINDEXED, _qarr

    data, ins = _qarr(f"{name}.prn")
    spec = SearchSpec(systems=systems, max_volume=max_volume, budget_seconds=BUDGET,
                      n_unindexed=REAL_DATA_N_UNINDEXED)
    return {"peaks": pick_peaks(data, ins), "data": data, "instrument": ins,
            "spec": spec}


def _brucite() -> dict:
    # tests/test_acceptance_indexing.py: _index_qarr_phase("brucite", …)
    return _qarr_dataset("brucite", ("trigonal", "hexagonal"), 700.0)


def _corundum() -> dict:
    # tests/test_acceptance_indexing.py: _index_corundum
    from tests.test_acceptance_indexing import REAL_DATA_SYSTEMS
    return _qarr_dataset("corundum", REAL_DATA_SYSTEMS, 600.0)


def _synthetic_monoclinic(engine: str | None) -> dict:
    # tests/test_indexing_engines.py: test_dichotomy_recovers_a_monoclinic_cell
    from tests.test_indexing_engines import spec_for, synthetic_peaks

    peaks, _cell = synthetic_peaks("monoclinic")
    out = {"peaks": peaks, "spec": spec_for("monoclinic", budget_seconds=BUDGET)}
    return out if engine is None else {**out, "engine": engine}


#: A dataset naming an ``engine`` is that engine's unit called directly, with
#: no ``quality`` (the engine assesses its own), which is what WP-1509's
#: ``fc4d2b0b`` digested.  The others go through ``index_pattern``.
DATASETS = {"brucite": _brucite, "corundum": _corundum,
            "synthmono": lambda: _synthetic_monoclinic("dichotomy"),
            "synthmono_ip": lambda: _synthetic_monoclinic(None)}


def digest(cands) -> str:
    rows = np.array([[*c.cell, c.n_indexed] for c in cands], dtype=np.float64)
    return hashlib.sha256(rows.tobytes()).hexdigest()[:8]


def groups_digest(groups) -> str:
    rows = np.array([[g, *c.cell, c.n_indexed] for g, group in enumerate(groups)
                     for c in group], dtype=np.float64)
    return hashlib.sha256(rows.tobytes()).hexdigest()[:8]


def capture(out: Path, datasets: list[str]) -> list[str]:
    """Record the units ``index_pattern`` hands the engines, one pickle each."""
    from rietx.indexing import engines
    from rietx.indexing.engines import EngineResult
    from rietx.indexing.workflow import index_pattern

    out.mkdir(parents=True, exist_ok=True)
    written = []
    for name in datasets:
        kwargs = DATASETS[name]()
        if "engine" in kwargs:
            unit = {"engine": kwargs["engine"], "peaks": kwargs["peaks"],
                    "spec": kwargs["spec"], "quality": None, "kwargs": {}}
            key = f"{name}.{unit['engine']}.{unit['spec'].systems[0]}"
            (out / f"{key}.unit.pkl").write_bytes(pickle.dumps(unit))
            written.append(key)
            continue
        sink: list[dict] = []

        def recorder(engine: str):
            def record(peaks, *, spec, quality, cancel=None, progress=None, **kw):
                sink.append({"engine": engine, "peaks": peaks, "spec": spec,
                             "quality": quality, "kwargs": kw})
                return EngineResult(engine=engine)
            return record

        real = dict(engines._REGISTRY)
        engines._REGISTRY.update({e: recorder(e) for e in real})
        try:
            index_pattern(kwargs.pop("peaks"), preset="full", **kwargs)
        finally:
            engines._REGISTRY.update(real)
        for unit in sink:
            (system,) = unit["spec"].systems
            key = f"{name}.{unit['engine']}.{system}"
            (out / f"{key}.unit.pkl").write_bytes(pickle.dumps(unit))
            written.append(key)
    return written


class _DedupClock:
    """Wall inside ``engines._dedup_groups`` and, optionally, its χ² test count."""

    def __init__(self, count: bool = False):
        self.seconds, self.calls, self.tests, self._count = 0.0, 0, 0, count

    def __enter__(self):
        from rietx.indexing import engines, reduce

        self._engines, self._reduce = engines, reduce
        self._real = engines._dedup_groups
        self._real_test = reduce.equal_reduced

        def timed(*args, **kwargs):
            t0 = time.perf_counter()
            try:
                return self._real(*args, **kwargs)
            finally:
                self.seconds += time.perf_counter() - t0
                self.calls += 1

        def counted(*args, **kwargs):
            self.tests += 1
            return self._real_test(*args, **kwargs)

        engines._dedup_groups = timed
        if self._count:
            reduce.equal_reduced = counted
        return self

    def __exit__(self, *exc):
        self._engines._dedup_groups = self._real
        self._reduce.equal_reduced = self._real_test


def replay(out: Path, key: str, *, save: bool, count: bool) -> dict:
    from rietx.indexing import engines

    unit = pickle.loads((out / f"{key}.unit.pkl").read_bytes())
    spec = replace(unit["spec"], budget_seconds=BUDGET)
    fn = engines._REGISTRY[unit["engine"]]
    with _DedupClock(count) as clock:
        t0 = time.perf_counter()
        res = fn(unit["peaks"], spec=spec, quality=unit["quality"], cancel=None,
                 progress=None, **unit["kwargs"])
        wall = time.perf_counter() - t0
    if save:
        (out / f"{key}.result.pkl").write_bytes(pickle.dumps(res))
    return {"unit": key, "digest": digest(res.candidates),
            "candidates": len(res.candidates), "complete": res.complete,
            "wall": round(wall, 2), "dedup": round(clock.seconds, 2),
            "dedup_calls": clock.calls,
            **({"chi2_tests": clock.tests} if count else {})}


def pool(out: Path, dataset: str, *, count: bool) -> dict:
    from rietx.indexing.engines import dedup_groups, merge_engine_units

    by_engine: dict[str, list] = {}
    for path in sorted(out.glob(f"{dataset}.*.unit.pkl")):
        key = path.name[: -len(".unit.pkl")]
        unit = pickle.loads(path.read_bytes())
        result = out / f"{key}.result.pkl"
        if not result.exists():
            raise SystemExit(f"{key} has no saved result: replay it with --save")
        by_engine.setdefault(unit["engine"], []).append(
            (unit["spec"].systems[0], pickle.loads(result.read_bytes())))
    from rietx.indexing.engines import SYSTEM_ORDER

    cands = []
    for engine in by_engine:  # capture order is index_pattern's engine order
        units = [r for _s, r in sorted(by_engine[engine],
                                       key=lambda sr: SYSTEM_ORDER.index(sr[0]))]
        cands.extend(merge_engine_units(units).candidates)
    with _DedupClock(count) as clock:
        groups = dedup_groups(cands)
    return {"pool": dataset, "candidates": len(cands), "groups": len(groups),
            "digest": groups_digest(groups), "dedup": round(clock.seconds, 2),
            **({"chi2_tests": clock.tests} if count else {})}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m tests.unit_replay")
    sub = ap.add_subparsers(dest="verb", required=True)
    c = sub.add_parser("capture")
    c.add_argument("dir", type=Path)
    c.add_argument("datasets", nargs="*", default=list(DATASETS))
    r = sub.add_parser("replay")
    r.add_argument("dir", type=Path)
    r.add_argument("units", nargs="*")
    r.add_argument("--save", action="store_true")
    r.add_argument("--count", action="store_true")
    p = sub.add_parser("pool")
    p.add_argument("dir", type=Path)
    p.add_argument("dataset")
    p.add_argument("--count", action="store_true")
    args = ap.parse_args(argv)
    if args.verb == "capture":
        for key in capture(args.dir, args.datasets):
            print(key)
    elif args.verb == "replay":
        keys = args.units or sorted(p.name[: -len(".unit.pkl")]
                                    for p in args.dir.glob("*.unit.pkl"))
        for key in keys:
            print(replay(args.dir, key, save=args.save, count=args.count), flush=True)
    else:
        print(pool(args.dir, args.dataset, count=args.count))
    return 0


if __name__ == "__main__":
    sys.exit(main())

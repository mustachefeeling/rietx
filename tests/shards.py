"""Which files a CI shard runs: the fast tier split in N by recorded seconds.

A fast leg ran 21-31 min on GitHub's two-core runner, where the worker count is
not a lever (WP-1547).  So each leg runs as N jobs, one ``--shard K/N`` each,
and ``conftest.pytest_collection_modifyitems`` keeps shard K's files.  A shard
takes files whole.  Files that share an ``xdist_group`` go to one shard
together, so a group's shared fixture is still built once, on one runner.  A
whole file also builds each of its module fixtures once.

Units go longest first, each to the least-loaded shard (Graham's LPT rule), by
the seconds in ``shard_times.json``.  The answer depends only on the collected
files, their groups and the record.  It has to: xdist's controller collects
nothing, and every worker selects its shard for itself.  A file the record does
not hold weighs the median recorded file, so a new file lands somewhere sensible
until the record is rewritten.

    python -m tests.shards DIR [SOURCE]

rewrites the record from one CI run's junit files, fetched with ``gh run
download RUN -p 'junit-*' -D DIR``.  Each subdirectory is one job, named
``junit-<leg>`` or ``junit-<leg>-<shard>``, and a leg's shards sum together.  A
file's seconds sum its cases, leaving out skipped ones.  The record holds two
profiles, because the jax leg's costs differ from the others' file by file
(``test_cross_backend.py`` ~390 s there against ~15 s on numpy).  ``numpy`` is
each file's median share of a Python leg times the median Python leg, since one
run's legs differ by up to 1.6× on the same tree.  ``jax`` is the jax leg's
seconds.  SOURCE names the run in the record.
"""

from __future__ import annotations

import importlib.util
import json
import math
import re
import statistics
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from collections.abc import Iterable, Mapping
from pathlib import Path

RECORD = Path(__file__).with_name("shard_times.json")
_SPEC = re.compile(r"\s*(\d+)\s*/\s*(\d+)\s*")
#: ``junit-py3.11`` is leg ``py3.11``, and so is its shard ``junit-py3.11-2``.
_JOB = re.compile(r"junit-(.+?)(?:-(\d+))?")


def parse(spec: str) -> tuple[int, int]:
    """``(K, N)`` from ``"K/N"``, or ``ValueError`` saying what is wrong."""
    m = _SPEC.fullmatch(spec)
    if not m:
        raise ValueError(f"--shard takes K/N, such as 1/2, not {spec!r}")
    k, n = int(m[1]), int(m[2])
    if not 1 <= k <= n:
        raise ValueError(f"--shard {spec}: K must run from 1 to N")
    return k, n


def profile() -> str:
    """The record's profile for this environment: does jax import here?"""
    return "jax" if importlib.util.find_spec("jax") is not None else "numpy"


def recorded_seconds(which: str | None = None, path: Path = RECORD) -> dict[str, float]:
    """One profile of the record, keyed by repo-relative POSIX file path."""
    record = json.loads(path.read_text(encoding="utf-8"))
    return record[which or profile()]


def units(pairs: Iterable[tuple[str, str | None]]) -> list[frozenset[str]]:
    """The files that must share a shard, from ``(file, group)`` per item.

    Files sharing a group name merge, transitively.  An item in several groups
    gives a pair for each.  The answer is a set of sets, so it cannot depend on
    the order the items came in, though the list's own order does."""
    parent: dict[tuple[str, str], tuple[str, str]] = {}

    def root(x: tuple[str, str]) -> tuple[str, str]:
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for file, group in pairs:
        f = root(("file", file))
        if group is not None:
            g = root(("group", group))
            if f != g:
                parent[max(f, g)] = min(f, g)
    members: dict[tuple[str, str], set[str]] = defaultdict(set)
    for kind, name in list(parent):
        if kind == "file":
            members[root((kind, name))].add(name)
    return [frozenset(files) for files in members.values()]


def assign(parts: Iterable[frozenset[str]], seconds: Mapping[str, float],
           n: int) -> list[tuple[frozenset[str], float]]:
    """Each shard's files and estimated seconds, units placed longest first.

    Ties break on the unit's sorted file names and then on the lowest shard
    index, so every process given the same units gets the same shards.  The
    largest shard exceeds an even split by at most the largest unit."""
    default = statistics.median(seconds.values()) if seconds else 1.0

    def weight(unit: frozenset[str]) -> float:
        return math.fsum(seconds.get(f, default) for f in sorted(unit))

    order = sorted(((weight(u), sorted(u)) for u in parts), key=lambda wu: (-wu[0], wu[1]))
    files: list[set[str]] = [set() for _ in range(n)]
    loads = [0.0] * n
    for w, unit in order:
        i = min(range(n), key=lambda j: (loads[j], j))
        files[i].update(unit)
        loads[i] += w
    return [(frozenset(f), load) for f, load in zip(files, loads, strict=True)]


def _file_of(classname: str) -> str | None:
    """``tests/test_x.py`` from ``tests.test_x`` or ``tests.test_x.TestK``."""
    parts = classname.split(".") if classname else []
    while parts and parts[-1][:1].isupper():
        parts.pop()                 # a test class, which pytest names Test*
    return "/".join(parts) + ".py" if parts else None


def leg_seconds(directory: Path) -> dict[str, dict[str, float]]:
    """Each leg's seconds per file, a leg's shards summed.

    A file whose every case skipped is kept at zero, which is what it cost.  A
    module skipped at import has no classname and no items, and is left out.
    A leg missing a shard that another leg has is refused: a shard that timed
    out uploads no file, and its files would read as costing nothing."""
    legs: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    shards_of: dict[str, set[int]] = defaultdict(set)
    for junit in sorted(directory.glob("junit-*/junit.xml")):
        m = _JOB.fullmatch(junit.parent.name)
        if m is None:
            continue
        if m[2] is not None:
            shards_of[m[1]].add(int(m[2]))
        leg = legs[m[1]]
        for case in ET.parse(junit).iter("testcase"):
            file = _file_of(case.get("classname", ""))
            if file is None:
                continue
            leg[file] += 0.0 if case.find("skipped") is not None else float(case.get("time", "0"))
    want = set(range(1, max(map(max, shards_of.values()), default=0) + 1))
    if short := {name: sorted(want - got) for name, got in shards_of.items() if got != want}:
        raise SystemExit(f"shards missing under {directory}: {short}")
    return {name: dict(files) for name, files in legs.items()}


def record(directory: Path, source: str) -> dict:
    """The record's contents: both profiles from one run's junit files."""
    legs = leg_seconds(directory)
    python = {name: files for name, files in legs.items() if name.startswith("py")}
    if not python:
        raise SystemExit(f"no junit-py* leg under {directory}")
    totals = {name: math.fsum(files.values()) for name, files in python.items()}
    scale = statistics.median(totals.values())
    numpy = {
        f: round(statistics.median(files.get(f, 0.0) / totals[name]
                                   for name, files in python.items()) * scale, 1)
        for f in set().union(*python.values())}
    jax = {f: round(s, 1) for f, s in legs.get("jax", {}).items()}
    return {"source": source, "numpy": numpy, "jax": jax}


def main(argv: list[str]) -> int:
    if not 1 <= len(argv) <= 2:
        print(__doc__, file=sys.stderr)
        return 2
    directory = Path(argv[0])
    source = argv[1] if len(argv) == 2 else directory.name
    out = record(directory, source)
    RECORD.write_text(json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    for which in ("numpy", "jax"):
        print(f"{which}: {len(out[which])} files, {math.fsum(out[which].values()):.0f} s")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

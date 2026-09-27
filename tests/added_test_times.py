"""Per-test seconds for the tests a branch adds, read from a pytest junit file.

The fast tier grows by its tail: on 2026-09-27 its 50 slowest tests took 52 %
of its worker-seconds (WP-1506).  A wall-clock assertion would be a load sensor
(tests/CLAUDE.md § Budgets in tests), so the guard is this report, which
``/wp-handover`` reads.

    python -m tests.added_test_times JUNIT [BASE]

JUNIT comes from a run with ``--junitxml=JUNIT -o junit_duration_report=total``:
the handover's own fast run, or a CI leg's ``junit-*`` artifact.  BASE defaults
to ``origin/main``.  A test counts as added when the working tree adds its
``def`` line since the fork from BASE, so a renamed test is listed too.  Each row sums setup, call and teardown
over the test's parameter cases.  A shared fixture's setup lands on whichever
test used it first, on that worker.
"""

from __future__ import annotations

import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict

_FILE = re.compile(r"^diff --git a/\S+ b/(tests/\S+)\.py$")
_DEF = re.compile(r"^\+\s*(?:async\s+)?def (test_\w+)\(")


def added_tests(diff: str) -> set[tuple[str, str]]:
    """``(module, name)`` for each test function whose ``def`` line a diff adds."""
    out: set[tuple[str, str]] = set()
    module = None
    for line in diff.splitlines():
        if line.startswith("diff --git "):
            m = _FILE.match(line)
            module = m.group(1).replace("/", ".") if m else None
        elif module and (m := _DEF.match(line)):
            out.add((module, m.group(1)))
    return out


def times(junit: str, added: set[tuple[str, str]]) -> dict[tuple[str, str], list[float]]:
    """Each added test's per-case seconds in a junit file, keyed as ``added`` is."""
    rows: dict[tuple[str, str], list[float]] = defaultdict(list)
    for case in ET.parse(junit).iter("testcase"):
        name = case.get("name", "").split("[", 1)[0]
        classname = case.get("classname", "")
        for module, test in added:
            if name == test and (classname == module or classname.startswith(module + ".")):
                rows[(module, test)].append(float(case.get("time", "0")))
    return dict(rows)


def main(argv: list[str]) -> int:
    if not 1 <= len(argv) <= 2:
        print(__doc__, file=sys.stderr)
        return 2
    base = argv[1] if len(argv) == 2 else "origin/main"
    fork = subprocess.run(["git", "merge-base", base, "HEAD"],
                          capture_output=True, encoding="utf-8", check=True).stdout.strip()
    diff = subprocess.run(["git", "diff", "--no-renames", "-U0", fork, "--", "tests/"],
                          capture_output=True, encoding="utf-8", check=True).stdout
    added = added_tests(diff)
    rows = times(argv[0], added)
    for (module, test), ts in sorted(rows.items(), key=lambda kv: -sum(kv[1])):
        where = f"{module.replace('.', '/')}.py::{test}"
        print(f"{sum(ts):8.2f} s  {where}  ({len(ts)} case{'' if len(ts) == 1 else 's'})")
    for module, test in sorted(added - rows.keys()):
        print(f"{'absent':>10}  {module.replace('.', '/')}.py::{test}  (not in this run)")
    print(f"{sum(map(sum, rows.values())):8.2f} s  over {len(rows)} added tests")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

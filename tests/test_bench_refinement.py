"""The v1.1 benchmark harness is a script that runs (WP-1111).

`examples/bench_refinement.py` is the **measurement authority** every later
speed WP quotes for its before/after, so a harness that has silently stopped
building one of its cases is worse than no harness: the missing row reads as a
case that was covered.  These tests are the guard against that, and they are
carefully *not* an acceptance suite.

**What is asserted, and what deliberately is not.**  Nothing here asserts a
wall-clock number.  A budget in a test is a runaway guard, never a timer
(CLAUDE.md § Commands), and the harness's whole point is that its numbers are
machine-relative — a CI box asserting one would be pinning the box, not the
package.  What is asserted is *structure*: every case key is distinct, the
registry's builders are reachable, the simulated trigger case still carries the
peak count that is its reason to exist, and the counting scaffold puts back the
name it patched.

**Why only the cheap cases are built.**  Building a case is not free — `nac`
runs a Le Bail fit to make its warm start, and `trigger-series` simulates ten
4 165-point patterns — so this module builds the two that cost about a second
and checks the rest by construction.  Running every case is what running the
harness *is*, and that belongs to a session that means to measure something.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

import rietx as rx
from rietx.model.forward import compile_model

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "examples" / "bench_refinement.py"


@pytest.fixture(scope="module")
def bench():
    """The harness imported as a module.

    By path rather than by package, because `examples/` is not one — the same
    reason `test_examples.py` runs its scripts as subprocesses.  The import
    itself is the first assertion: the module inserts `tests/` on `sys.path`
    at import time so its case builders can reach the acceptance fixtures, and
    a broken insert would fail here rather than in a bench run nobody is
    watching.
    """
    spec = importlib.util.spec_from_file_location("bench_refinement", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["bench_refinement"] = module
    spec.loader.exec_module(module)
    return module


def test_case_keys_are_distinct_and_listable(bench):
    keys = [case.key for case in bench.CASES]
    assert len(keys) == len(set(keys)), f"duplicate case key in {keys}"
    assert all(case.blurb for case in bench.CASES)
    # `--list` is the only path a reader takes before committing 20 minutes
    assert bench.main(["--list"]) == 0


def test_an_unknown_case_is_refused_by_name(bench):
    """A typo must not silently select every case — the failure mode is a
    20-minute run the person did not ask for."""
    with pytest.raises(SystemExit):
        bench.main(["--cases", "nac,not-a-case"])


def test_the_trigger_case_carries_the_trigger_peak_count(bench):
    """Case 4's reason to exist is its shape, so its shape is what is pinned.

    WP-1109's trigger was ~4 165 points and roughly an order of magnitude more
    peaks than any shipped baseline; the WP's acceptance is "~1000+ (line,
    reflection) pairs".  Compiled here without fitting, which is cheap — the
    expensive half of building this case is evaluating the truth model to make
    the pattern, and a peak count needs no intensities.
    """
    structure = rx.Structure(phases=bench._trigger_phases())
    instrument = bench._trigger_instrument(truth=True)
    tt = bench._TRIGGER_TT
    blank = rx.PatternData(two_theta=tt.tolist(),
                           intensity=np.ones_like(tt).tolist())
    model = compile_model(structure, instrument, blank)

    assert len(tt) == 4165, "the trigger grid is 4 165 points by construction"
    pairs = sum(int(ph.win.shape[0] * ph.win.shape[1]) for ph in model.phases)
    assert pairs > 1000, f"trigger case carries only {pairs} (line, reflection) pairs"
    assert len(model.phases) == 4
    # Cu Kα doublet, both lines windowed — a single-line trigger case would
    # halve the pair count without changing the phase list
    assert all(ph.win.shape[0] == 2 for ph in model.phases)


def test_the_trigger_pattern_is_deterministic(bench):
    """Same seed, same counts — otherwise two "repeats" are two datasets and
    the wall-clock range is not a range of anything."""
    a = bench._trigger_pattern(seed=7, drift=0.0)
    b = bench._trigger_pattern(seed=7, drift=0.0)
    assert np.array_equal(np.asarray(a.intensity), np.asarray(b.intensity))
    c = bench._trigger_pattern(seed=8, drift=0.0)
    assert not np.array_equal(np.asarray(a.intensity), np.asarray(c.intensity))


def test_a_baseline_case_builds_a_compiled_model(bench):
    """`cpd-1a` is the cheapest real-data case to build: a read plus the scale
    seeding.  Compiling its setup is what every timed repeat starts from."""
    try:
        setup = bench._cpd_1a()
    except (FileNotFoundError, OSError) as exc:
        pytest.skip(str(exc))
    pts, pairs, width = bench._shape(setup)
    assert pts == 7251
    assert pairs > 0 and width > 0
    assert setup.patterns is None, "cpd-1a is a single fit, not a series"


def test_the_series_case_is_declared_as_one(bench):
    """A series case is recognised by `Setup.patterns`, which is what routes it
    to `refine_sequential` instead of `fit` — so the flag, not the key name, is
    the thing to pin."""
    series = [c for c in bench.CASES if c.key.endswith("-series")]
    assert series, "no series case in the registry"
    # built lazily: constructing it simulates ten patterns (~50 s), which is a
    # measurement, not a smoke test.  What is checked here is that the runner
    # dispatches on the declared flag.
    src = SCRIPT.read_text(encoding="utf-8")
    assert "if setup.patterns is not None:" in src
    assert "refine_sequential" in src


def test_the_counting_scaffold_restores_the_name_it_patched(bench):
    """The harness wraps `optimize.least_squares`'s scipy entry point to read
    `nfev`/`njev`.  A wrapper left in place after an exception would stack one
    wrapper per failed case and quietly double-count, so the restore is tested
    on both exits.
    """
    from rietx.optimize import least_squares as mod

    original = mod.least_squares
    with bench._counting(bench._Counts()):
        assert mod.least_squares is not original
    assert mod.least_squares is original

    with pytest.raises(RuntimeError):
        with bench._counting(bench._Counts()):
            raise RuntimeError("case blew up")
    assert mod.least_squares is original

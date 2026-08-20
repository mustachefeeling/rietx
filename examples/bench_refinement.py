"""WP-1111: the v1.1 refinement benchmark harness.

Run: ``.venv/bin/python examples/bench_refinement.py``

One command prints the table the **v1.1 milestone is judged by** — named
cases, wall-clock ranges, evaluation counts, per-stage iterations — so every
later speed WP quotes *this* harness for its before/after instead of inventing
its own measurement.  Nothing here changes production code, and that is a
requirement rather than an accident: a harness that lands in the same commit as
an optimisation can no longer measure it.

Read these four rules before quoting any number this script prints.

1. **Wall clock is a range, never a figure** (CLAUDE.md § Commands).  Each case
   is run ``--repeats`` times (default 3) and the *min and max* are printed.  A
   single number would invite comparison against a remembered one, and machine
   state moves these further than most changes do: a concurrent ``pytest -n
   auto`` inflated a 1.24 s fit to 4.78 s — 3.9× — during WP-1109.  **Run this
   on an idle machine, alone.**
2. **Never compare across machines**, and never against a figure whose venv and
   platform are not stamped beside it.  This script stamps its own header with
   both, plus the package version and the numpy build, so a pasted table
   carries its own provenance.
3. **Rwp is an identity check, not the metric.**  It is printed so that two
   runs of the same case can be seen to be the *same fit*, and the repeats are
   compared for it; a speed change that moves Rwp is not a speed change.  The
   metric is wall clock, and the diagnostics are the evaluation counts.
4. **The counts come from scipy, the wall clock from this process.**  ``nfev``
   and ``njev`` are read off the ``OptimizeResult`` that
   ``rietx.optimize.least_squares`` gets back, by wrapping the module-level
   ``least_squares`` name for the duration of a run (see ``_counting``).  This
   is a measurement scaffold, not an API: the package records ``nfev`` per
   stage as ``StageResult.n_iterations`` and records ``njev`` nowhere, which is
   WP-1113's ground.  The wrapper costs one attribute read per solve and does
   not perturb the timing.

Cases
-----
The first three are the baselines WP-1109 ranked its candidates on, rebuilt
from the acceptance suites' own fixtures rather than from restated protocols —
so that when a number here disagrees with one there, the protocol is not among
the candidate explanations.

``nac-lebail`` 11-BM NAC, 1 phase, ``profile_only``, Le Bail mode, 22 003
             points.
``nac``      The Rietveld leg built on it: 2 phases, 6 stages, same points.  No
             FCJ (Debye-Scherrer at 0.414 Å), so windows are symmetric and the
             peak loop is dispatch-bound rather than node-bound.  Its Le Bail
             seed is built **once**, at setup, and is not timed.
             **WP-1109's 1.5-1.8 s NAC row is the two legs together** — split
             here because timing only the Rietveld leg against that row shows a
             2.4× discrepancy that is not a speed change.
``cpd-1a``   IUCr CPD round-robin sample 1a, 3 phases, Cu Kα doublet + FCJ,
             ``qpa_plan`` (8 stages), 7 251 points.  The FCJ-heavy small-cell
             case.
``cpd-2``    The same instrument on sample 2 under the **QPA acceptance
             protocol** — 4 phases, 9 stages with texture — i.e.
             ``test_sample2_brucite_march_dollase``'s own fit.  This is the
             case WP-1109 profiled at 534 residual + 425 Jacobian evaluations,
             and it is *not* the same fit as the 4-phase ``mccusker_default``
             row in that WP's opening table.  Quote them separately.

Columns
-------
``pairs`` is the (emission line, reflection) pair count summed over phases —
the quantity peak-loop cost scales with, and the reason the shipped baselines
under-weight the trigger case: they carry a few hundred where it carries
~1000+.  ``win`` is the mean window width in points.  ``free`` is the union of
what the plan's stages actually freed, read off the result rather than
re-derived from the globs.  ``nfev``/``njev`` are whole-fit totals across every
stage; the per-stage ``n_iterations`` breakdown (scipy's nfev per stage) prints
under each case.

``--profile`` re-runs each selected case **once** under cProfile and prints the
top 10 by tottime.  Profiled wall clock is inflated and is never quoted as a
timing; the ranking is what it is for.
"""

from __future__ import annotations

import argparse
import cProfile
import io
import platform
import pstats
import sys
import time
from dataclasses import dataclass, field
from importlib.metadata import version
from pathlib import Path
from typing import Callable

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tests"))

import rietx as rx  # noqa: E402
from rietx import _about  # noqa: E402
from rietx.model.forward import compile_model  # noqa: E402

# -- the counting scaffold -------------------------------------------------

class _Counts:
    """Whole-fit ``nfev``/``njev``, accumulated across a run's stages."""

    def __init__(self) -> None:
        self.nfev = 0
        self.njev = 0


class _counting:
    """Wrap ``optimize.least_squares``'s scipy entry point for one run.

    Reads ``nfev``/``njev`` off each returned ``OptimizeResult``.  Restores the
    original name on exit, including on an exception, so a failed case cannot
    leave the package patched for the next one.  ``solver="lm"`` does not route
    through this name (it has its own driver), which is why the printed count
    says ``-`` rather than 0 when nothing was seen.
    """

    def __init__(self, counts: _Counts) -> None:
        self.counts = counts

    def __enter__(self) -> _Counts:
        from rietx.optimize import least_squares as mod

        self._mod = mod
        self._orig = mod.least_squares

        def wrapper(*args, **kwargs):
            res = self._orig(*args, **kwargs)
            self.counts.nfev += int(getattr(res, "nfev", 0) or 0)
            self.counts.njev += int(getattr(res, "njev", 0) or 0)
            return res

        mod.least_squares = wrapper
        return self.counts

    def __exit__(self, *exc) -> None:
        self._mod.least_squares = self._orig


# -- cases -----------------------------------------------------------------

@dataclass
class Setup:
    """One case, built once: pristine templates plus the plan that fits them.

    ``structure``/``instrument`` are deep-copied per repeat, because a fit
    mutates them and a warm second repeat would not be the same measurement.
    """

    title: str
    data: rx.PatternData
    structure: rx.Structure
    instrument: rx.Instrument
    plan: rx.RefinementPlan
    limits: tuple[float, float] | None = None
    mode: str = "rietveld"
    notes: str = ""


@dataclass
class Case:
    key: str
    build: Callable[[], Setup]
    blurb: str


def _nac_inputs():
    from test_acceptance_nac import DATA, build_nac_inputs

    if not (DATA / "11BM_NAC.fxye").exists():
        raise FileNotFoundError("11-BM NAC dataset not present")
    return build_nac_inputs()


def _nac_lebail() -> Setup:
    """The single-phase Le Bail leg the acceptance module opens with.

    A case in its own right because WP-1109's 1.5-1.8 s NAC row is **this leg
    plus the next one**, and a reader comparing against that row while timing
    only the Rietveld leg finds a 2.4× discrepancy that is not a speed change.
    Measured here 2026-08-20, the two legs are ~0.66 s and ~0.64 s.
    """
    from test_acceptance_nac import LIMITS

    data, structure, instrument = _nac_inputs()
    return Setup("11-BM NAC Le Bail leg, 1 phase, profile_only (5 stages)",
                 data, structure, instrument,
                 rx.RefinementPlan.profile_only(), limits=LIMITS, mode="lebail")


def _nac() -> Setup:
    """11-BM NAC: the acceptance module's Rietveld leg, on its Le Bail seed.

    Only the Rietveld leg is timed.  The Le Bail pass is a warm start, not part
    of this case; it is timed separately as ``nac-lebail``, and running it
    inside the timed region would measure a *third* thing again.
    """
    from test_acceptance_nac import LIMITS, _caf2_phase

    data, structure, instrument = _nac_inputs()
    ref_lb = rx.Refinement(structure, instrument, history=False)
    ref_lb.fit(data, mode="lebail", two_theta_limits=LIMITS)

    structure2 = ref_lb.fitted_structure.model_copy(deep=True)
    instrument2 = ref_lb.fitted_instrument.model_copy(deep=True)
    structure2.phases[0].scale.value = 1e-6
    structure2.phases.append(_caf2_phase())

    plan = rx.RefinementPlan.mccusker_default()
    plan.stages.append(rx.Stage("biso", ["phases.*.atoms.*.biso"]))
    return Setup("11-BM NAC Rietveld leg, 2 phases, synchrotron (no FCJ)",
                 data, structure2, instrument2, plan, limits=LIMITS,
                 notes="Le Bail warm start built once at setup, not timed; "
                       "WP-1109's 1.5-1.8 s row is this leg PLUS nac-lebail")


def _cpd_1a() -> Setup:
    from test_acceptance_qpa_roundrobin import (
        DATA,
        corundum_phase,
        fluorite_phase,
        qarr_instrument,
        qpa_plan,
        seed_scales,
        zincite_phase,
    )

    if not DATA.exists():
        raise FileNotFoundError("IUCr QPA round-robin dataset not present")
    data = rx.read_pattern(DATA / "cpd-1a.prn")
    structure = rx.Structure(phases=[corundum_phase(), zincite_phase(),
                                     fluorite_phase()])
    instrument = qarr_instrument()
    seed_scales(structure, instrument, data)
    return Setup("IUCr cpd-1a, 3 phases, Cu Kα + FCJ, qpa_plan (8 stages)",
                 data, structure, instrument, qpa_plan())


def _cpd_2() -> Setup:
    """``test_sample2_brucite_march_dollase``'s protocol, stage for stage."""
    from test_acceptance_qpa_roundrobin import (
        DATA,
        brucite_phase,
        corundum_phase,
        fluorite_phase,
        qarr_instrument,
        qpa_plan,
        seed_scales,
        zincite_phase,
    )

    if not DATA.exists():
        raise FileNotFoundError("IUCr QPA round-robin dataset not present")
    data = rx.read_pattern(DATA / "cpd-2.prn")
    structure = rx.Structure(phases=[corundum_phase(), zincite_phase(),
                                     fluorite_phase(),
                                     brucite_phase(textured=True)])
    instrument = qarr_instrument()
    seed_scales(structure, instrument, data)
    biso = ("phases.0.atoms.*.biso", "phases.1.atoms.*.biso",
            "phases.2.atoms.*.biso", "phases.3.atoms.0.biso",
            "phases.3.atoms.1.biso")
    return Setup(
        "qarr cpd-2, 4 phases, QPA acceptance protocol (9 stages, texture)",
        data, structure, instrument,
        qpa_plan(biso_globs=biso, texture=True))


CASES: tuple[Case, ...] = (
    Case("nac-lebail", _nac_lebail, "22 003 pts, 1 phase — the Le Bail seed leg"),
    Case("nac", _nac, "22 003 pts, no FCJ — the dispatch-light case"),
    Case("cpd-1a", _cpd_1a, "7 251 pts, FCJ, 3 phases — the FCJ-heavy small case"),
    Case("cpd-2", _cpd_2, "7 251 pts, FCJ, 4 phases + texture — WP-1109's profile"),
)


# -- measurement -----------------------------------------------------------

@dataclass
class Run:
    wall: float
    rwp: float
    nfev: int
    njev: int
    free: int
    stages: list[tuple[str, int]] = field(default_factory=list)
    status: str = ""


def _shape(setup: Setup) -> tuple[int, int, float]:
    """(fitted points, (line, reflection) pairs, mean window width in points).

    Compiled at the case's *starting* model with no ``moving_paths`` claim, so
    the pair count is the one the first stage sees.
    """
    model = compile_model(setup.structure, setup.instrument, setup.data,
                          mode=setup.mode, two_theta_limits=setup.limits)
    pairs = 0
    widths: list[np.ndarray] = []
    for ph in model.phases:
        pairs += int(ph.win.shape[0] * ph.win.shape[1])
        widths.append((ph.win[..., 1] - ph.win[..., 0]).ravel())
    width = float(np.mean(np.concatenate(widths))) if widths else 0.0
    return len(model.tt), pairs, width


def _run_once(setup: Setup) -> Run:
    counts = _Counts()
    ref = rx.Refinement(setup.structure.model_copy(deep=True),
                        setup.instrument.model_copy(deep=True),
                        history=False)
    with _counting(counts):
        t0 = time.perf_counter()
        result = ref.fit(setup.data, plan=setup.plan, mode=setup.mode,
                         two_theta_limits=setup.limits)
        wall = time.perf_counter() - t0
    freed: set[str] = set()
    for stage in result.stages:
        freed |= set(stage.freed)
    return Run(wall, result.statistics.rwp, counts.nfev, counts.njev,
               len(freed), [(s.name, s.n_iterations) for s in result.stages],
               result.status)


def _profile(setup: Setup) -> str:
    prof = cProfile.Profile()
    prof.enable()
    _run_once(setup)
    prof.disable()
    buf = io.StringIO()
    pstats.Stats(prof, stream=buf).sort_stats("tottime").print_stats(10)
    return buf.getvalue()


def _header(repeats: int) -> str:
    return (f"{_about.DIST_NAME} {version(_about.DIST_NAME)} · "
            f"numpy {np.__version__} · python {platform.python_version()} · "
            f"{platform.system().lower()}/{platform.machine()} · "
            f"venv {Path(sys.prefix)}\n"
            f"best-of-{repeats}, wall clock as a RANGE — run idle, alone; "
            f"never compare across machines")


HEAD = (f"  {'case':10s} {'pts':>6s} {'pairs':>6s} {'win':>5s} {'free':>5s} "
        f"{'wall (s)':>13s} {'nfev':>6s} {'njev':>6s} {'Rwp':>8s}  status")


def _report(case: Case, setup: Setup, runs: list[Run]) -> None:
    pts, pairs, width = _shape(setup)
    walls = [r.wall for r in runs]
    rwps = {round(r.rwp, 6) for r in runs}
    last = runs[-1]
    njev = f"{last.njev}" if last.njev else "-"
    rng = f"{min(walls):.2f}-{max(walls):.2f}"
    print(f"  {case.key:10s} {pts:6d} {pairs:6d} {width:5.0f} {last.free:5d} "
          f"{rng:>13s} {last.nfev:6d} {njev:>6s} {last.rwp:8.5f}  {last.status}")
    print(f"    {setup.title}")
    if setup.notes:
        print(f"    ({setup.notes})")
    if len(rwps) > 1:
        print(f"    !! Rwp differs between repeats {sorted(rwps)} — these are "
              f"not the same fit, so the wall-clock range is not one either")
    print("    per-stage nfev: " + "  ".join(f"{n}={i}" for n, i in last.stages))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="v1.1 refinement benchmark harness")
    ap.add_argument("--cases", default="", help="comma-separated case keys "
                    f"(default all: {','.join(c.key for c in CASES)})")
    ap.add_argument("--repeats", type=int, default=3,
                    help="timed repeats per case (default 3)")
    ap.add_argument("--profile", action="store_true",
                    help="also cProfile each case once, top 10 by tottime")
    ap.add_argument("--list", action="store_true", help="list the cases and exit")
    args = ap.parse_args(argv)

    if args.list:
        for case in CASES:
            print(f"  {case.key:10s} {case.blurb}")
        return 0

    wanted = [c.strip() for c in args.cases.split(",") if c.strip()]
    unknown = set(wanted) - {c.key for c in CASES}
    if unknown:
        ap.error(f"unknown case(s): {', '.join(sorted(unknown))}")
    selected = [c for c in CASES if not wanted or c.key in wanted]

    print(_header(args.repeats))
    print()
    print(HEAD)

    for case in selected:
        try:
            setup = case.build()
        except (FileNotFoundError, OSError) as exc:        # dataset absent
            print(f"  {case.key:10s} skipped ({exc})")
            continue
        runs = [_run_once(setup) for _ in range(args.repeats)]
        _report(case, setup, runs)
        if args.profile:
            print(_profile(setup))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

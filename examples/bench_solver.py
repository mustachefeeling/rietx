"""WP-0601: scipy TRF against the bounded LM driver, on the real protocols.

Run: ``.venv/bin/python examples/bench_solver.py``

**Read the ceiling before the table.**  The normal-equation solve is a
minority of this package's runtime — ``derivative_bases`` costs ~2× the
forward evaluation, and Coelho (2005) measured his own N = 1325 case dropping
the *solve* from 484 s to 2.86 s while the whole refinement only went
2441 s → 1785 s.  So a solver that halved every solve would buy ≈1.25× overall,
and the reason this WP exists is constraint vocabulary, not speed.

Three things this script is careful about, each because it would otherwise
produce a misleading number:

1. **Both drivers are timed in the same process against the same current
   main.**  Every pre-WP-0605 wall-clock figure in this repo is stale — task 0
   of that WP (the FCJ node memo plus the ``axial_derivs`` skip) was worth
   1.23× on the SRM 660c protocol — so quoting an old TRF baseline would
   credit this WP with that speedup.
2. **The stopping rule is fixed before anything is compared.**  Coelho (2018)
   §2.4.2 flags that a loose termination criterion favours the more erratic
   updater; both drivers here get the same ``ftol`` and the same per-stage
   iteration cap from the same plan.
3. **The quality column is ΔBIC, not Hamilton and not Δ Rwp.**  On the 7251-
   channel round-robin patterns Hamilton's F test at α = 0.05 blesses a 0.13 %
   χ² improvement as readily as a real 6.9 % one (WP-0503); ΔBIC separated the
   same pair by +488 against −17.  Here the parameter count is identical
   between drivers, so ΔBIC reduces to N·ln(χ²_trf/χ²_lm) — positive means the
   LM found the better minimum.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tests"))

import rietx as rx  # noqa: E402
from rietx.report.layer2 import delta_bic  # noqa: E402

SOLVERS = ("trf", "lm")


def _srm660c():
    from test_acceptance_srm660c import _nist_calibrated_plan, build_srm_inputs

    data, structure, instrument = build_srm_inputs()
    return ("SRM 660c LaB6 (lab CuKα)", data, structure, instrument,
            _nist_calibrated_plan(), None)


def _nac_11bm():
    """11-BM NAC, single-phase Rietveld over the acceptance suite's range.

    The suite's own case is a Le Bail pass followed by a two-phase Rietveld;
    this uses the same data and instrument with the default plan, because a
    driver comparison wants one solve chain, not a warm start whose first leg
    would be timed under only one of them.
    """
    from test_acceptance_nac import DATA, LIMITS, WAVELENGTH

    data = rx.read_pattern(DATA / "11BM_NAC.fxye")
    structure = rx.Structure.from_cif(str(DATA / "cod_1000236.cif"))
    instrument = rx.Instrument.debye_scherrer(wavelength=WAVELENGTH)
    instrument.profile.w.value = 2e-5
    instrument.profile.x.value = 2e-3
    from rietx.schemas.instrument import BackgroundChebyshev

    instrument.background = BackgroundChebyshev.with_terms(6)
    return ("11-BM NAC (synchrotron)", data, structure, instrument,
            rx.RefinementPlan.mccusker_default(), LIMITS)


def _corundum():
    from test_acceptance_qpa_roundrobin import (
        DATA,
        corundum_phase,
        qarr_instrument,
        seed_scales,
    )
    from test_acceptance_stephens import _plan

    data = rx.read_pattern(DATA / "corundum.prn")
    structure = rx.Structure(phases=[corundum_phase()])
    instrument = qarr_instrument()
    seed_scales(structure, instrument, data)
    return ("corundum (round robin, lab)", data, structure, instrument,
            _plan(texture=False, stephens=False), None)


def _cpd2_qpa():
    """cpd-2 under the QPA acceptance protocol — WP-1113's basin counterexample.

    The one shipped protocol measured so far on which the drivers can part
    company on the *answer*, not merely the corner detail: the width stages
    walk a degenerate (U,V,W,X,Y × per-phase size/strain) valley, both
    drivers converge at equivalent Rwp before the texture stage, and whether
    brucite's March-Dollase basin (r ≈ 0.67, Rwp 0.133 vs 0.245) is downhill
    from there depends on *which* point of the valley the upstream stages
    stopped at.  Measured 2026-08-21: from the LM path's biso state, a TRF
    polish of the same final stage also stays at Rwp 0.244 — a genuine local
    minimum, so this is basin selection on a degenerate valley, not a driver
    defect (WP-1113's file has the bisection).

    ``max_iter`` is raised to 400 here because at the shipped per-stage cap
    the LM's ``cell`` stage happens to be *truncated* out of the path that
    leads to the bad valley point — the answer then depends on a runaway
    guard, which is exactly the dependence WP-1109's budget rule forbids
    reading as convergence.  The raised cap gives both drivers room to stop
    where their own criteria say, which is the comparison this bench is for.
    """
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

    data = rx.read_pattern(DATA / "cpd-2.prn")
    structure = rx.Structure(phases=[corundum_phase(), zincite_phase(),
                                     fluorite_phase(),
                                     brucite_phase(textured=True)])
    instrument = qarr_instrument()
    seed_scales(structure, instrument, data)
    biso = ("phases.0.atoms.*.biso", "phases.1.atoms.*.biso",
            "phases.2.atoms.*.biso", "phases.3.atoms.0.biso",
            "phases.3.atoms.1.biso")
    plan = qpa_plan(biso_globs=biso, texture=True)
    for stage in plan.stages:
        stage.max_iter = 400
    return ("cpd-2 QPA protocol (4 phases, texture)", data, structure,
            instrument, plan, None)


CASES = (_srm660c, _nac_11bm, _corundum, _cpd2_qpa)


def run(case) -> None:
    try:
        name, data, structure, instrument, plan, limits = case()
    except Exception as exc:                      # dataset absent
        print(f"  skipped ({exc})")
        return

    out = {}
    for solver in SOLVERS:
        t0 = time.perf_counter()
        ref = rx.Refinement(structure.model_copy(deep=True),
                            instrument.model_copy(deep=True),
                            solver=solver, history=False)
        result = ref.fit(data, plan=plan, two_theta_limits=limits)
        out[solver] = {
            "t": time.perf_counter() - t0,
            "rwp": result.statistics.rwp,
            "chi2": result.statistics.chi2,
            "n": result.statistics.n_points,
            "iters": sum(s.n_iterations for s in result.stages),
            "status": result.status,
        }

    trf, lm = out["trf"], out["lm"]
    # identical parameter counts, so ΔBIC is the pure goodness comparison
    dbic = delta_bic(trf["chi2"], lm["chi2"], trf["n"], 0)
    print(f"\n{name}   ({trf['n']} channels)")
    print(f"  {'driver':6s} {'wall (s)':>9s} {'residual evals':>15s} {'Rwp':>9s} "
          f"{'chi2red':>9s}  status")
    for solver in SOLVERS:
        r = out[solver]
        print(f"  {solver:6s} {r['t']:9.2f} {r['iters']:15d} {r['rwp']:9.5f} "
              f"{r['chi2']:9.4f}  {r['status']}")
    print(f"  speed  LM/TRF = {trf['t'] / lm['t']:.2f}×      "
          f"ΔBIC (favouring LM if > 0) = {dbic:+.1f}")


def main() -> None:
    print(__doc__.split("Three things")[0].strip())
    print("\nnumpy", np.__version__, "| both drivers, same process, same plan\n")
    for case in CASES:
        run(case)
    print("\nRead the ΔBIC column with the WP-0503 caution in mind: a driver "
          "that finds a\nlower χ² has not necessarily found a better answer. "
          "On SRM 660c the LM lands\n0.25 % higher in χ² and 1.3 µm closer to "
          "the NIST-certified specimen displacement,\nbecause the two part "
          "company in the ill-conditioned axial corner where the FCJ\nprofile "
          "has a corner at S/L = H/L — which is exactly where the default "
          "instrument\nstarts both apertures.  On cpd-2 the large negative "
          "ΔBIC is the real thing: the\nLM path stops at a width-valley point "
          "from which the texture basin is out of\nreach (see _cpd2_qpa's "
          "docstring, and WP-1113 for the bisection).")


if __name__ == "__main__":
    main()

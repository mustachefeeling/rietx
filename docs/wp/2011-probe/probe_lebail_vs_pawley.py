"""Le Bail against Pawley as the indexer's whole-pattern cell check.

Replays ``validate_by_lebail`` (src/rietx/indexing/workflow.py) with the fit's
``mode`` as the only variable: same scaffold structure, same width seeding, same
four-stage plan with the cell held, same two detectors.  Two questions:

1. cost: wall seconds per check, three repeats, per candidate and mode;
2. magnetite: does a Pawley fit keep the primitive rival's background above zero,
   so the absent-reflection count can see what Le Bail's fit hid?

Run from the worktree root with its venv:  .venv/bin/python <this file> [magnetite|lab6|all]
"""
from __future__ import annotations

import json
import math
import os
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path.cwd()))     # the worktree root, for tests.*

from rietx.indexing.peaks import predicted_fwhm
from rietx.indexing.workflow import (
    ABSENT_SIGMA,
    absent_reflections,
    seed_widths,
    structure_from_candidate,
    validate_by_lebail,
    validation_plan,
)
from rietx.refine import Refinement
from rietx.report.layer0 import build_layer0

OUT = Path(os.environ.get("WP2011_OUT",
                          Path(tempfile.gettempdir()) / "wp2011-probe"))
OUT.mkdir(parents=True, exist_ok=True)
REPEATS = 3


def check(candidate, data, ins, *, peaks=None, mode):
    structure = structure_from_candidate(candidate)
    i = ins
    if peaks is not None:
        i, _ = seed_widths(i, peaks)
    plan = validation_plan(candidate, i, two_theta_max=float(np.max(data.tt())))
    ref = Refinement(structure, i, history=False)
    t0 = time.perf_counter()
    result = ref.fit(data, mode=mode, plan=plan, telemetry=False)
    secs = time.perf_counter() - t0
    rows = [r for r in ref.reflection_table() if r.line == 0]
    pos = np.array([r.two_theta for r in rows], dtype=np.float64)
    absent, _ = absent_reflections(
        np.asarray(result.two_theta), np.asarray(result.y_obs),
        np.asarray(result.y_background), np.asarray(result.sigma),
        pos, predicted_fwhm(pos, ref.fitted_instrument), k_sigma=ABSENT_SIGMA)
    layer0 = build_layer0(result)
    unmatched = [u for u in layer0.unmatched if u.kind == "unmatched_obs"]
    bkg = np.asarray(result.y_background)
    net = np.asarray(result.y_obs) - bkg
    sig = np.asarray(result.sigma)
    return dict(
        mode=mode, secs=secs, rwp=float(result.statistics.rwp),
        gof=float(result.statistics.gof), n_refl=len(rows),
        absent=len(absent), unmatched=len(unmatched),
        bkg_mean=float(bkg.mean()), net_over_3sig=float(np.mean(net > 3 * sig)),
        y_obs_p5=float(np.percentile(np.asarray(result.y_obs), 5)),
        status=result.status,
        iters=[s.n_iterations for s in result.stages],
        codes=sorted({d.code for d in result.diagnostics}),
    ), result


def run_case(label, candidate, data, ins, peaks, rows):
    # the replica must reproduce the shipped function before its Pawley twin
    # means anything
    shipped = validate_by_lebail(candidate, data, ins, peaks=peaks)
    for mode in ("lebail", "pawley"):
        times = []
        for k in range(REPEATS):
            rec, result = check(candidate, data, ins, peaks=peaks, mode=mode)
            times.append(rec["secs"])
            if k == 0:
                first = rec
                np.savez(OUT / f"{label}_{mode}.npz",
                         tt=np.asarray(result.two_theta),
                         y_obs=np.asarray(result.y_obs),
                         y_calc=np.asarray(result.y_calc),
                         y_bkg=np.asarray(result.y_background))
        first["secs_min"], first["secs_max"] = min(times), max(times)
        first.pop("secs")
        first["case"] = label
        if mode == "lebail":
            first["shipped_rwp"] = shipped.rwp
            first["shipped_absent"] = shipped.predicted_but_absent
            first["shipped_unmatched"] = shipped.unmatched_observed
        rows.append(first)
        print(json.dumps(first), flush=True)


def lab6(rows):
    from tests.test_indexing_consensus import (
        TRUE_A,
        _candidate,
        _instrument,
        _true_models,
    )
    from rietx.model.forward import compile_model
    from rietx.params.vector import ParameterTable
    from rietx.schemas.pattern import PatternData

    # the module fixture's body, verbatim (pytest fixtures cannot be called)
    structure, instrument = _true_models()
    tt = np.arange(15.0, 145.0, 0.02)
    blank = PatternData(two_theta=tt.tolist(), intensity=np.zeros_like(tt).tolist())
    model = compile_model(structure, instrument, blank, mode="rietveld")
    table = ParameterTable(structure, instrument)
    y = model.evaluate(table.decode(table.x0()))
    y = np.random.default_rng(11).poisson(np.maximum(y, 1.0)).astype(float)
    data = PatternData(two_theta=model.tt.tolist(), intensity=y.tolist())

    for name, factor in (("lab6_truth", 1.0), ("lab6_doubled", 2.0),
                         ("lab6_a_sqrt5", math.sqrt(5.0)),
                         ("lab6_metric_1pc", 1.01), ("lab6_tripled", 3.0)):
        run_case(name, _candidate(TRUE_A * factor), data, _instrument(), None, rows)


def magnetite(rows):
    from tests.test_acceptance_indexing import (
        REAL_DATA_BUDGET_SECONDS,
        REAL_DATA_N_UNINDEXED,
        _qarr,
    )
    from rietx.indexing import index_pattern
    from rietx.indexing.engines import SearchSpec
    from rietx.indexing.pick import pick_peaks
    from rietx.schemas.indexing import CellCandidate

    data, ins = _qarr("magnetit.prn")
    peaks = pick_peaks(data, ins)
    cached = OUT / "magnetite_candidates.json"
    if cached.exists():
        cands = [CellCandidate.model_validate(c) for c in json.loads(cached.read_text(encoding="utf-8"))]
    else:
        spec = SearchSpec(systems=("cubic",), max_volume=700.0,
                          budget_seconds=REAL_DATA_BUDGET_SECONDS,
                          n_unindexed=REAL_DATA_N_UNINDEXED)
        res = index_pattern(peaks, data=data, instrument=ins, spec=spec, preset="full")
        best = res.candidates[0]
        rival = [c for c in res.candidates[1:] if c.centring == "P"
                 and abs(c.cell[0] / best.cell[0] - 1.0) < 1e-3][0]
        cands = [best, rival]
        cached.write_text(json.dumps([c.model_dump(mode="json") for c in cands]),
                          encoding="utf-8")
    best, rival = cands
    print(f"magnetite truth {best.centring} a={best.cell[0]:.5f}  "
          f"rival {rival.centring} a={rival.cell[0]:.5f}", flush=True)
    run_case("magnetite_truth_F", best, data, ins, peaks, rows)
    run_case("magnetite_rival_P", rival, data, ins, peaks, rows)


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    rows: list[dict] = []
    if which in ("magnetite", "all"):
        magnetite(rows)
    if which in ("lab6", "all"):
        lab6(rows)
    (OUT / f"rows_{which}.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")

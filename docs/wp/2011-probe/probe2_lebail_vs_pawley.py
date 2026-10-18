"""Robustness of probe 1: noise seeds, cost at larger cells, true cells on real data.

Run from the worktree root:  .venv/bin/python <this file> seeds|scale|truths
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path.cwd()))
sys.path.insert(0, str(Path(__file__).parent))

from probe_lebail_vs_pawley import OUT, check  # noqa: E402

from rietx.indexing.workflow import seed_widths, structure_from_candidate  # noqa: E402
from rietx.refine import Refinement  # noqa: E402
from rietx.schemas.indexing import CellCandidate  # noqa: E402


def lab6_data(seed):
    from tests.test_indexing_consensus import _true_models
    from rietx.model.forward import compile_model
    from rietx.params.vector import ParameterTable
    from rietx.schemas.pattern import PatternData

    structure, instrument = _true_models()
    tt = np.arange(15.0, 145.0, 0.02)
    blank = PatternData(two_theta=tt.tolist(), intensity=np.zeros_like(tt).tolist())
    model = compile_model(structure, instrument, blank, mode="rietveld")
    table = ParameterTable(structure, instrument)
    y = model.evaluate(table.decode(table.x0()))
    y = np.random.default_rng(seed).poisson(np.maximum(y, 1.0)).astype(float)
    return PatternData(two_theta=model.tt.tolist(), intensity=y.tolist())


def emit(rows, rec, **tags):
    rec.update(tags)
    rows.append(rec)
    print(json.dumps({k: rec[k] for k in (*tags, "mode", "n_refl", "rwp", "absent",
                                          "unmatched", "bkg_mean", "secs", "status")}),
          flush=True)


def seeds(rows):
    from tests.test_indexing_consensus import TRUE_A, _candidate, _instrument
    for seed in (11, 12, 13, 14, 15):
        data = lab6_data(seed)
        for name, f in (("truth", 1.0), ("doubled", 2.0), ("a_sqrt5", math.sqrt(5)),
                        ("metric_1pc", 1.01)):
            for mode in ("lebail", "pawley"):
                rec, _ = check(_candidate(TRUE_A * f), data, _instrument(), mode=mode)
                emit(rows, rec, case=name, seed=seed)


def scale(rows):
    from tests.test_indexing_consensus import TRUE_A, _candidate, _instrument
    data = lab6_data(11)
    for f in (3.0, 4.0, 5.0):
        for mode in ("lebail", "pawley"):
            for rep in range(2):
                rec, _ = check(_candidate(TRUE_A * f), data, _instrument(), mode=mode)
                emit(rows, rec, case=f"x{f:g}", rep=rep)


def _cell_of(ref):
    cell = ref.structure.phases[0].cell
    return tuple(float(getattr(cell, k).value)
                 for k in ("a", "b", "c", "alpha", "beta", "gamma"))


def truths(rows):
    from tests.test_acceptance_fap import build_fap_inputs
    from tests.test_acceptance_indexing import _qarr
    from tests.test_acceptance_nac import build_nac_inputs
    from tests.test_acceptance_srm660c import build_srm_inputs
    from rietx.indexing.pick import pick_peaks

    hexa = (90.0, 90.0, 120.0)
    right = (90.0, 90.0, 90.0)
    sets = [
        ("srm660c", lambda: build_srm_inputs()[::2], "cubic", "P", (4.15678,) * 3 + right),
        ("nac", lambda: build_nac_inputs()[::2], "cubic", "I", (10.2510,) * 3 + right),
        ("fap", lambda: build_fap_inputs()[::2], "hexagonal", "P", (9.3717, 9.3717, 6.8859) + hexa),
        ("corundum", lambda: _qarr("corundum.prn"), "trigonal", "R", (4.7589, 4.7589, 12.991) + hexa),
        ("brucite", lambda: _qarr("brucite.prn"), "trigonal", "P", (3.142, 3.142, 4.766) + hexa),
        ("zincite", lambda: _qarr("zincite.prn"), "hexagonal", "P", (3.2498, 3.2498, 5.2066) + hexa),
        ("zircon", lambda: _qarr("zircon.prn"), "tetragonal", "I", (6.6042, 6.6042, 5.9796) + right),
        ("fluorite", lambda: _qarr("fluorite.prn"), "cubic", "F", (5.4630,) * 3 + right),
        ("magnetite", lambda: _qarr("magnetit.prn"), "cubic", "F", (8.3941,) * 3 + right),
    ]
    for name, load, system, centring, cell0 in sets:
        data, ins = load()
        peaks = pick_peaks(data, ins)
        start = CellCandidate(cell=cell0, cell_esd=(0.0,) * 6, system=system,
                              centring=centring)
        # one neutral cell refinement so a literature cell's lab d-scale error
        # does not decide the comparison; both modes then judge this cell
        seeded, _ = seed_widths(ins, peaks)
        ref = Refinement(structure_from_candidate(start), seeded, history=False)
        ref.fit(data, mode="lebail", plan="profile_only", telemetry=False)
        ref.fit(data, mode="lebail", plan="profile_only", telemetry=False)
        cell = _cell_of(ref)
        cand = CellCandidate(cell=cell, cell_esd=(0.0,) * 6, system=system,
                             centring=centring)
        print(f"{name}: start {cell0[:3]} refined {tuple(round(v, 5) for v in cell[:3])}",
              flush=True)
        for mode in ("lebail", "pawley"):
            rec, result = check(cand, data, ins, peaks=peaks, mode=mode)
            emit(rows, rec, case=name)
            np.savez(OUT / f"truth_{name}_{mode}.npz",
                     tt=np.asarray(result.two_theta), y_obs=np.asarray(result.y_obs),
                     y_calc=np.asarray(result.y_calc),
                     y_bkg=np.asarray(result.y_background))


if __name__ == "__main__":
    which = sys.argv[1]
    rows: list[dict] = []
    {"seeds": seeds, "scale": scale, "truths": truths}[which](rows)
    (OUT / f"rows2_{which}.json").write_text(json.dumps(rows, indent=1, default=str), encoding="utf-8")

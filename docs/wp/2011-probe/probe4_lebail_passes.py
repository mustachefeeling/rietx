"""Option C: the indexer's check with Le Bail run to a fixed point
(RefinementPlan.lebail_passes, WP-1323's alternation), against one-pass Le Bail
and one-pass Pawley, on the wrong and true cells where the two disagreed."""
import json
import math
import sys
import time
from dataclasses import replace
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path.cwd()))
sys.path.insert(0, str(Path(__file__).parent))

import probe_lebail_vs_pawley as p1  # noqa: E402
from probe2_lebail_vs_pawley import lab6_data  # noqa: E402

from rietx.indexing import workflow  # noqa: E402
from rietx.indexing.pick import pick_peaks  # noqa: E402
from rietx.schemas.indexing import CellCandidate  # noqa: E402

OUT = p1.OUT
original_plan = workflow.validation_plan


def run(label, cand, data, ins, peaks):
    for mode, passes in (("lebail", 1), ("lebail", 5), ("lebail", 10), ("pawley", 1)):
        p1.validation_plan = (lambda c, i, two_theta_max=None, _n=passes:
                              replace(original_plan(c, i, two_theta_max=two_theta_max),
                                      lebail_passes=_n))
        rec, res = p1.check(cand, data, ins, peaks=peaks, mode=mode)
        stop = [d.message[:90] for d in res.diagnostics
                if d.code == "LEBAIL_ALTERNATION_STOPPED"]
        print(json.dumps(dict(case=label, mode=f"{mode}x{passes}", n=rec["n_refl"],
                              bkg=round(rec["bkg_mean"], 1), missing=rec["absent"],
                              unmatched=rec["unmatched"], rwp=round(rec["rwp"], 3),
                              secs=round(rec["secs"], 2), stop=stop)), flush=True)


from tests.test_acceptance_fap import build_fap_inputs  # noqa: E402
from tests.test_acceptance_indexing import _qarr  # noqa: E402
from tests.test_acceptance_nac import build_nac_inputs  # noqa: E402
from tests.test_indexing_consensus import TRUE_A, _candidate, _instrument  # noqa: E402

data = lab6_data(11)
for name, f in (("lab6_a_sqrt5", math.sqrt(5)), ("lab6_metric_1pc", 1.01)):
    run(name, _candidate(TRUE_A * f), data, _instrument(), None)

mdata, mins = _qarr("magnetit.prn")
rival = CellCandidate.model_validate(
    json.loads((OUT / "magnetite_candidates.json").read_text(encoding="utf-8"))[1])
run("magnetite_rival_P", rival, mdata, mins, pick_peaks(mdata, mins))

hexa, right = (90.0, 90.0, 120.0), (90.0, 90.0, 90.0)
for name, load, system, centring, cell in (
        ("fap", lambda: build_fap_inputs()[::2], "hexagonal", "P", (9.3716, 9.3716, 6.88586) + hexa),
        ("corundum", lambda: _qarr("corundum.prn"), "trigonal", "R", (4.75782, 4.75782, 12.987) + hexa),
        ("zircon", lambda: _qarr("zircon.prn"), "tetragonal", "I", (6.60384, 6.60384, 5.98995) + right),
        ("nac", lambda: build_nac_inputs()[::2], "cubic", "I", (10.25124,) * 3 + right)):
    d, i = load()
    run(f"truth_{name}", CellCandidate(cell=cell, cell_esd=(0.0,) * 6, system=system,
                                       centring=centring), d, i, pick_peaks(d, i))

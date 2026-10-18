"""Ordinary Le Bail (profile_only, cell free) against Pawley (pawley_default) on
true cells, three passes each: does the width floor seen in the validation fit
also stall the fit a tutorial runs?"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))

from rietx.indexing.pick import pick_peaks
from rietx.indexing.workflow import seed_widths, structure_from_candidate
from rietx.refine import Refinement
from rietx.schemas.indexing import CellCandidate
from tests.test_acceptance_fap import build_fap_inputs
from tests.test_acceptance_indexing import _qarr

hexa, right = (90.0, 90.0, 120.0), (90.0, 90.0, 90.0)
cases = [
    ("fap", lambda: build_fap_inputs()[::2], "hexagonal", "P", (9.3716, 9.3716, 6.88586) + hexa),
    ("zircon", lambda: _qarr("zircon.prn"), "tetragonal", "I", (6.60384, 6.60384, 5.98995) + right),
    ("corundum", lambda: _qarr("corundum.prn"), "trigonal", "R", (4.75782, 4.75782, 12.987) + hexa),
]
for name, load, system, centring, cell in cases:
    data, ins = load()
    cand = CellCandidate(cell=cell, cell_esd=(0.0,) * 6, system=system, centring=centring)
    seeded, _ = seed_widths(ins, pick_peaks(data, ins))
    for mode, plan in (("lebail", "profile_only"), ("pawley", "pawley_default")):
        ref = Refinement(structure_from_candidate(cand), seeded, history=False)
        out = []
        for k in range(3):
            r = ref.fit(data, mode=mode, plan=plan, telemetry=False)
            fl = sorted({p.split(".")[-1] for d in r.diagnostics
                         if d.code == "FLOOR_HIT" for p in d.where})
            out.append(f"pass{k + 1} rwp {r.statistics.rwp:.3f} floor {fl}")
        print(f"{name:8s} {mode:6s} {plan:14s} | " + " | ".join(out), flush=True)

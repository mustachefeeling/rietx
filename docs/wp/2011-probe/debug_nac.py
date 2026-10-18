"""Which NAC reflections does the Pawley check call absent on the true cell, and
how strong does the published structure make them?"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path.cwd()))

from rietx.indexing.peaks import predicted_fwhm
from rietx.indexing.pick import pick_peaks
from rietx.indexing.workflow import (
    ABSENT_SIGMA,
    absent_reflections,
    seed_widths,
    structure_from_candidate,
    validation_plan,
)
from rietx.refine import Refinement
from rietx.schemas.indexing import CellCandidate
from tests.test_acceptance_nac import build_nac_inputs

data, structure, ins = build_nac_inputs()
peaks = pick_peaks(data, ins)
a = 10.25124
cand = CellCandidate(cell=(a, a, a, 90.0, 90.0, 90.0), cell_esd=(0.0,) * 6,
                     system="cubic", centring="I")

# relative |F|^2-based intensity of every reflection from the true structure
true_ref = Refinement(structure, ins, history=False)
true_ref.fit(data, mode="rietveld", plan="profile_only", telemetry=False)
row0 = [r for r in true_ref.reflection_table() if r.line == 0]
print("row fields:", [k for k in vars(row0[0])] if hasattr(row0[0], "__dict__") else row0[0])
true_pos = np.array([r.two_theta for r in row0])
true_int = np.array([r.intensity for r in row0])
med = float(np.median(true_int))
def true_at(x):
    m = np.abs(true_pos - x) < 2e-3
    return float(true_int[m].sum()) / med, int(m.sum())

for mode in ("lebail", "pawley"):
    i, _ = seed_widths(ins, peaks)
    ref = Refinement(structure_from_candidate(cand), i, history=False)
    res = ref.fit(data, mode=mode,
                  plan=validation_plan(cand, i, two_theta_max=float(np.max(data.tt()))),
                  telemetry=False)
    rows = [r for r in ref.reflection_table() if r.line == 0]
    pos = np.array([r.two_theta for r in rows])
    bad, ratio = absent_reflections(np.asarray(res.two_theta), np.asarray(res.y_obs),
                                    np.asarray(res.y_background), np.asarray(res.sigma),
                                    pos, predicted_fwhm(pos, ref.fitted_instrument),
                                    k_sigma=ABSENT_SIGMA)
    print(f"\n== {mode}: {len(bad)} absent of {len(rows)}; 2θ range "
          f"{min(res.two_theta):.2f}-{max(res.two_theta):.2f}; bkg mean "
          f"{np.mean(res.y_background):.1f}")
    by_pos = {round(r.two_theta, 4): r for r in rows}
    for x, q in zip(bad, ratio):
        r = by_pos.get(round(x, 4))
        hkl = (r.h, r.k, r.l) if r is not None else None
        rel, n = true_at(x)
        print(f"  2θ {x:7.3f}  hkl {hkl}  net/σ {q:5.1f}  "
              f"true intensity / median {rel:.3g} ({n} orbits)")

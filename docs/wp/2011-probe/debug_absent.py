"""Per-reflection view of the absent test on magnetite's P rival, both modes."""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path.cwd()))

from rietx.indexing.peaks import predicted_fwhm
from rietx.indexing.pick import pick_peaks
from rietx.indexing.workflow import (
    ABSENT_SIGMA,
    ABSENT_WINDOW_FWHM,
    seed_widths,
    structure_from_candidate,
    validation_plan,
)
from rietx.refine import Refinement
from rietx.schemas.indexing import CellCandidate
from tests.test_acceptance_indexing import _qarr

sys.path.insert(0, str(Path(__file__).parent))
from probe_lebail_vs_pawley import OUT  # noqa: E402
data, ins = _qarr("magnetit.prn")
peaks = pick_peaks(data, ins)
cands = [CellCandidate.model_validate(c)
         for c in json.loads((OUT / "magnetite_candidates.json").read_text(encoding="utf-8"))]
rival = cands[1]
for mode in ("lebail", "pawley"):
    i, seeded = seed_widths(ins, peaks)
    ref = Refinement(structure_from_candidate(rival), i, history=False)
    plan = validation_plan(rival, i, two_theta_max=float(np.max(data.tt())))
    res = ref.fit(data, mode=mode, plan=plan, telemetry=False)
    fi = ref.fitted_instrument
    p = fi.profile
    print(f"\n== {mode}: seeded={seeded} u,v,w,x,y = "
          f"{p.u.value:.4g} {p.v.value:.4g} {p.w.value:.4g} {p.x.value:.4g} {p.y.value:.4g}")
    rows = [r for r in ref.reflection_table() if r.line == 0]
    pos = np.array([r.two_theta for r in rows])
    fw = predicted_fwhm(pos, fi)
    tt = np.asarray(res.two_theta)
    net = np.asarray(res.y_obs) - np.asarray(res.y_background)
    sig = np.asarray(res.sigma)
    print(f"data 2θ {tt.min():.2f}-{tt.max():.2f}, step {np.median(np.diff(tt)):.4f}")
    print(" hkl            2θ     FWHM  n_ch  net/σ   I_fit")
    for r, x, w in zip(rows, pos, fw):
        inside = np.abs(tt - x) <= ABSENT_WINDOW_FWHM * max(float(w), 1e-6)
        if not inside.any():
            continue
        ratio = net[inside].sum() / np.sqrt((sig[inside] ** 2).sum())
        if x < 46:
            h = tuple(r.hkl) if hasattr(r, "hkl") else "?"
            inten = getattr(r, "intensity", float("nan"))
            flag = "ABSENT" if ratio < ABSENT_SIGMA else ""
            print(f" {str(h):12s} {x:7.3f} {w:7.4f} {inside.sum():4d} {ratio:7.1f} {inten:9.3g} {flag}")

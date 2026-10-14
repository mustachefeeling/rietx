"""WP-1325: the over-flexible arm on the ZrMo2O8 ramp, the form test's denominator.

ZrP2O7 and WO3 each fitted laws that must hold any smooth truth, and with
the shipped χ²_red·f² divisor their readings piled toward p = 1, while over
χ²_red alone they read near nominal (``zrp2o7_overflex_results.txt``,
``wo3_pvalues_results.txt``).  The divisor was chosen on this ramp, which
had no such arm.  Here are two, on ``real_ramp.py``'s window and protocol
(33 patterns, the cubic cell a and the trigonal a and c):

1. ``windows``: the 33 patterns in three windows of 11, a cubic in T on
   each target in each window, nine laws in one fit;
2. ``quintic``: a quintic in T on each target over all 33.

Each reading prints over χ²_red·f² (shipped), over χ²_red alone (the
statistic times f²), and over 1 (times χ²_red·f²), with its p-value.

The joint fits widen each cell's window from ``real_ramp.py``'s ±1.5 % to
±5 % of the chain's value.  At ±1.5 % the windowed cubic's seed, fitted
through eleven chain points, put the trigonal c at 12.276 Å against its
bound 12.263 Å, and the fit refused before its first iteration (the error
WO3's lane met too; the WP's in-step-bounds task).

    .venv/bin/python docs/wp/1325-measure/zrmo2o8_overflex.py
        > docs/wp/1325-measure/zrmo2o8_overflex_results.txt
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from real_ramp import (  # noqa: E402
    DATASET,
    INP,
    RAW,
    TARGETS,
    instrument,
    machine,
    plan,
    protocol,
    run_chain,
    structure,
)
from scipy.stats import chi2 as chi2_dist  # noqa: E402

import rietx as rx  # noqa: E402
from rietx.params.multi import SharingMap  # noqa: E402
from tests import local_data  # noqa: E402

WINDOWS = [range(0, 11), range(11, 22), range(22, 33)]


WIDEN = 0.05


def widened(structures):
    """Copies with every cell edge's window ±``WIDEN`` about its value."""
    out = []
    for st in structures:
        st = st.model_copy(deep=True)
        for phase in st.phases:
            for name in "abc":
                p = getattr(phase.cell, name)
                p.min, p.max = p.value * (1 - WIDEN), p.value * (1 + WIDEN)
        out.append(st)
    return out


def joint(patterns, chain, temps, limits, ties) -> dict:
    series = chain["series"]
    t0 = time.perf_counter()
    fit = rx.MultiHistogramRefinement(
        widened(series.fitted_structures), list(series.fitted_instruments),
        sharing=SharingMap(per_histogram=["phases.*"]),
        coordinates=rx.CoordinateTable(columns={"T": list(temps)}, units={"T": "K"}),
        parametric=ties)
    result = fit.fit(patterns, plan=plan(), two_theta_limits=limits)
    return dict(result=result, seconds=time.perf_counter() - t0)


def line(label: str, r, f2: float, chi2r: float) -> str:
    if r is None or r.statistic is None:
        return f"  {label:22} not tested"
    out = [f"  {label:22} {r.statistic:7.1f}/{r.dof:3d} p {r.p_value:7.3g}"
           f" {'REJECT' if r.rejected else 'keep  '}"]
    for name, factor in (("no f²", f2), ("over 1", chi2r * f2)):
        s = r.statistic * factor
        p = float(chi2_dist.sf(s, r.dof))
        out.append(f"| {name} {s:8.1f} ({s / r.dof:5.2f}/dir) p {p:7.3g}"
                   f" {'REJECT' if p < 0.05 else 'keep  '}")
    return " ".join(out)


def report(name: str, run: dict) -> None:
    res = run["result"]
    s = res.statistics
    f2 = s.esd_inflation ** 2
    print(f"{name}: {run['seconds']:.1f} s {res.status}; χ²r {s.chi2:.3f}, f {s.esd_inflation:.3f}"
          f" (χ²r·f² {s.chi2 * f2:.3f})", flush=True)
    for t in res.parametric_form:
        print(f"  {t.tie} tested {t.n_patterns}/{t.n_subset}")
        print(line("freed", t.others_freed, f2, s.chi2))
        print(line("tied", t.tied, f2, s.chi2))
    print(line("joint", res.parametric_form_joint, f2, s.chi2), flush=True)


def main() -> None:
    where = local_data.dataset(DATASET)
    if where is None:
        raise SystemExit(f"{DATASET} is not on this machine: python -m tests.local_data {DATASET}")
    text = (where / INP).read_text(encoding="utf-8", errors="replace")
    proto = protocol(text)
    radius = rx.read_topas_inp(where / INP).goniometer_radius_mm or 217.5
    window = range(35, 68)
    temps = [proto["temps"][k] for k in window]
    limits = proto["limits"]
    patterns = [rx.read_pattern(where / RAW, scan=k) for k in window]
    start = (structure(where / INP), instrument(proto, radius))

    print("WP-1325: over-flexible laws on the ZrMo2O8 ramp")
    for m in machine():
        print(m)
    print(f"window    ranges 35..67 (0-based), {len(window)} patterns", flush=True)
    chain = run_chain(patterns, start, temps, limits)
    print(f"chain     {chain['seconds']:.1f} s", flush=True)

    ties = [rx.ParametricTie(name=f"{key}_w{w}", target=path, basis="polynomial",
                             terms=[["T"] * j for j in range(4)], patterns=list(rng))
            for key, path in TARGETS.items() for w, rng in enumerate(WINDOWS)]
    report("windows (cubic, 3 × 11)", joint(patterns, chain, temps, limits, ties))
    ties = [rx.ParametricTie(name=f"{key}_q5", target=path, basis="polynomial",
                             terms=[["T"] * j for j in range(6)])
            for key, path in TARGETS.items()]
    report("quintic (33)", joint(patterns, chain, temps, limits, ties))


if __name__ == "__main__":
    main()

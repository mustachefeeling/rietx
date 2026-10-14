"""WP-1325: each law tested with the other laws freed, against the refits.

At an answer with several laws, ``ParametricFormTest`` reads each law twice:
with the other laws still tied (the reading ``form_score.py`` found weaker,
the cubic line 1.37 per direction against 1.57 alone), and with every other
tested law's targets freed (``ParametricFormTest.others_freed``).  The second
is the gain with every law swapped less the gain with only the others
swapped, so it should be the χ² a refit holding only this law gains over the
untied fit: 576.1, 181.7 and 204.7 on this ramp, 1.58, 0.50 and 0.56 per
direction over the untied fit's χ²_red·f² (``form_score_results.txt``).

Prints, per law, both readings off the three-law answer's own
``parametric_form``, and the second's gain over the untied fit's denominator
beside the refit's recorded figure.  Then the joint reading of all three
(``parametric_form_joint``), whose gain should be the 839.3 the untied fit
removed from the three-law fit.  Run on ``real_ramp.py``'s window and
protocol: ``python docs/wp/1325-measure/form_freed.py`` (about five minutes,
one process; the data from ``python -m tests.local_data``).
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from form_score import joint  # noqa: E402
from real_ramp import (  # noqa: E402
    DATASET,
    INP,
    RAW,
    TARGETS,
    instrument,
    machine,
    protocol,
    run_chain,
    structure,
)

import rietx as rx  # noqa: E402
from tests import local_data  # noqa: E402

#: each law alone, refitted against the untied fit (``form_score_results.txt``)
REFIT = {"cubic_a": (576.1, 1.58), "trig_a": (181.7, 0.50), "trig_c": (204.7, 0.56)}
#: the untied fit's χ² gain over the three-law fit (``form_score_results.txt``)
REFIT_ALL = 839.3


def reading(r) -> str:
    if r is None or r.statistic is None:
        return "not tested"
    verdict = "REJECT" if r.rejected else "keep"
    return (f"{r.statistic:7.1f} for {r.dof:3d} ({r.statistic / r.dof:4.2f}/dir, "
            f"p {r.p_value:.3g}) {verdict}")


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

    print("WP-1325: each law with the other laws freed, on the ZrMo2O8 ramp")
    for m in machine():
        print(m)
    print(f"window    ranges 35..67 (0-based), {len(window)} patterns", flush=True)
    chain = run_chain(patterns, start, temps, limits)
    print(f"chain     {chain['seconds']:.1f} s", flush=True)
    untied = joint(patterns, chain, temps, limits, {})
    denom = untied["chi2r"] * untied["inflation"] ** 2
    print(f"untied    {untied['seconds']:.1f} s; χ²r {untied['chi2r']:.3f}, "
          f"f {untied['inflation']:.3f}", flush=True)
    every = joint(patterns, chain, temps, limits, dict.fromkeys(TARGETS, 1))
    result = every["result"]
    s = result.statistics
    own = s.chi2 * s.esd_inflation ** 2
    print(f"all three {every['seconds']:.1f} s {result.status}; χ²r {s.chi2:.3f}, "
          f"f {s.esd_inflation:.3f}; the readings divide by χ²r·f² {own:.3f}, "
          f"the untied fit's is {denom:.3f}", flush=True)
    for t in result.parametric_form:
        print(f"  {t.tie:8} tied   {reading(t.tied)}")
        print(f"  {'':8} freed  {reading(t.others_freed)}")
        o = t.others_freed
        if o is not None and o.statistic is not None:
            gain = o.statistic * own
            dchi2, per = REFIT[t.tie]
            print(f"  {'':8} freed gain {gain:7.1f} ({gain / dchi2:4.2f} of the refit's "
                  f"{dchi2}); over the untied denominator {gain / denom / o.dof:4.2f}/dir "
                  f"against the refit's {per}", flush=True)
    j = result.parametric_form_joint
    print(f"  joint    {reading(j)}")
    if j is not None and j.statistic is not None:
        gain = j.statistic * own
        print(f"  {'':8} joint gain {gain:7.1f} ({gain / REFIT_ALL:4.2f} of the untied "
              f"refit's {REFIT_ALL}); over the untied denominator "
              f"{gain / denom / j.dof:4.2f}/dir", flush=True)
    t0 = time.perf_counter()
    rx.RefinementResult.model_validate_json(result.model_dump_json())
    print(f"round trip {time.perf_counter() - t0:.2f} s")
    print(str(result).split("parametric coefficients")[1])


if __name__ == "__main__":
    main()

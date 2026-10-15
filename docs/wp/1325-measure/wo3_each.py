"""WP-1325: chosen TOPAS equations on WO3 refitted alone, against the untied fit.

    .venv/bin/python docs/wp/1325-measure/wo3_each.py [--keys=m_c,t_a,t_beta,p_c]
        > docs/wp/1325-measure/wo3_each_results.txt

As run on 2026-10-14, at a load of 50-110, the keys were split over two
processes to finish the same evening: ``--keys=m_c,t_a`` (the first process,
stopped once t_a printed, its comparison then appended by
``--compare=wo3_each_results.txt >> wo3_each_results.txt``, which fits
nothing) and ``--keys=t_beta,p_c`` into ``wo3_each2_results.txt``, stopped
the same way once t_beta printed, so p_c was never refitted alone.

Run from the repository root after ``wo3_form.py``, whose untied fit is the
reference and whose all-equations readings are compared: both are read back from
``wo3_form_results.txt`` rather than refitted (each 100-pattern joint fit took
36 minutes at a load of 8-100).  Same window (all 100 patterns), seeds, plan
and widened windows as ``wo3_form.py``.

An equation alone, refitted, against the untied fit is the χ² its freed reading
predicts: the untied fit frees every target, the equation-alone fit frees all but
this one (``form_freed.py``'s comparison on ZrMo₂O₈).  The statistic is that
Δχ² over the untied fit's χ²_red·f², on the directions the equation removes.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from scipy.stats import chi2 as chi2_dist  # noqa: E402
from wo3_form import joint, reading, topas_equations  # noqa: E402
from wo3_ramp import best_chain, load, machine, parse_args  # noqa: E402

FORM = HERE / "wo3_form_results.txt"


def untied_from_results() -> dict:
    text = FORM.read_text(encoding="utf-8")
    m = re.search(r"^untied .*?χ² ([\d.]+) with (\d+) free; χ²r ([\d.]+), f ([\d.]+)", text, re.M)
    if m is None:
        raise SystemExit(f"{FORM.name} has no untied line yet")
    return dict(chi2=float(m.group(1)), n_free=int(m.group(2)), chi2r=float(m.group(3)),
                inflation=float(m.group(4)))


def freed_from_results(key: str) -> str:
    text = FORM.read_text(encoding="utf-8")
    m = re.search(rf"^  {key} .*\n +freed +(.*)$", text, re.M)
    return m.group(1).strip() if m else "—"


def all_equations_scale() -> float:
    """The all-equations fit's χ²_red·f², which turns a freed statistic into χ²."""
    text = FORM.read_text(encoding="utf-8")
    # the record wo3_form_results.txt was written when the line said "all laws"
    m = re.search(r"^all (?:laws|equations)  .*?χ²r ([\d.]+), f ([\d.]+)", text, re.M)
    return float(m.group(1)) * float(m.group(2)) ** 2


def compare(rows: list[tuple[str, float, int, str]]) -> None:
    """Each equation-alone refit (key, χ², free, its own reading) against the untied fit."""
    untied = untied_from_results()
    denom = untied["chi2r"] * untied["inflation"] ** 2
    scale = all_equations_scale()
    print(f"against the untied fit read from {FORM.name}: χ² {untied['chi2']:.1f} with "
          f"{untied['n_free']} free, χ²r·f² {denom:.3f}; the all-equations fit's χ²r·f² {scale:.3f}")
    for key, chi2, n_free, alone in rows:
        dchi2 = chi2 - untied["chi2"]
        dfree = untied["n_free"] - n_free
        stat = dchi2 / denom
        freed = freed_from_results(key)
        m = re.match(r"([\d.]+) /", freed)
        gain = float(m.group(1)) * scale if m else float("nan")
        print(f"  {key:8} refit Δχ² {dchi2:9.1f} for {dfree:3d}: {stat:7.1f} "
              f"({stat / max(dfree, 1):.2f}/dir, p {chi2_dist.sf(stat, max(dfree, 1)):.3g})")
        print(f"  {'':8} all-equations freed {freed}; its gain {gain:9.1f} "
              f"({gain / dchi2:.2f} of the refit)")
        print(f"  {'':8} the equation-alone fit's own reading {alone}")


def compare_only(path: Path) -> None:
    """``compare`` on the per-equation lines a stopped run left in ``path``."""
    rows = []
    for m in re.finditer(r"^([a-z]_[a-z]+) .*?χ² ([\d.]+) with (\d+) free; alone (.*)$",
                         path.read_text(encoding="utf-8"), re.M):
        rows.append((m.group(1), float(m.group(2)), int(m.group(3)), m.group(4).strip()))
    print()
    print(f"the comparison, from the per-equation lines in {path.name}")
    compare(rows)


def main() -> None:
    args = parse_args(sys.argv[1:], {"keys": "m_c,t_a,t_beta,p_c", "compare": ""})
    if args["compare"]:
        compare_only(HERE / str(args["compare"]))
        return
    keys = [k for k in str(args["keys"]).split(",") if k]
    data = load(0, 99)
    chain = best_chain()
    if chain is None:
        raise SystemExit("run wo3_ramp.py first (both directions): this reads its cached chains")
    idx = list(range(100))
    theta = data["proto"]["theta"]
    print("WP-1325 out of sample: TOPAS equations on WO3 refitted alone, against the untied fit")
    for line in machine():
        print(line)
    print(f"equations      {keys}, each alone over all 100 patterns", flush=True)
    rows = []
    for key in keys:
        one = joint(data, chain, topas_equations(data["temps"][idx], theta, keys=[key]), subset=idx)
        alone = reading(one["result"].parametric_form[0].tied)
        rows.append((key, one["chi2"], one["n_free"], alone))
        print(f"{key:8} {one['seconds']:7.1f} s {one['result'].status} iters {one['iters']}; "
              f"χ² {one['chi2']:.1f} with {one['n_free']} free; alone {alone}", flush=True)
    print()
    compare(rows)


if __name__ == "__main__":
    main()

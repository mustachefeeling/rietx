"""WP-1325: the over-flexible arm's p-values on WO3, pooled and read three ways.

    .venv/bin/python docs/wp/1325-measure/wo3_pvalues.py wo3_flex_results.txt [more…]
        > docs/wp/1325-measure/wo3_pvalues_results.txt

Reads the per-equation and joint readings ``wo3_flex.py`` printed (file names are
relative to this directory) and each window's χ²_red and f, and gives every
reading's p-value under three denominators for the χ² its alternative would
remove:

* χ²_red·f², the shipped test (``params.parametric.form_tests``);
* χ²_red alone, without the serial-correlation factor;
* 1, the raw χ² gain against counting noise, as if the weights were exact.

For each set: how many reject at 95 %, the median p, and a Kolmogorov-Smirnov
test against Uniform(0, 1).  A test of the right size gives uniform p-values
on equations that contain the truth; p-values piled at 1 mean a conservative test,
piled at 0 an anti-conservative one.  The over-flexible equations are the right
form by construction, so the shipped column measures the false-alarm rate
decision 4 asks about, and the other two say how much of the margin the
denominator spends.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import numpy as np
from scipy.stats import chi2 as chi2_dist
from scipy.stats import kstest

HERE = Path(__file__).resolve().parent
WINDOW = re.compile(r"^window (\d+): .*?χ²r ([\d.]+), f ([\d.]+)")
READ = re.compile(r"^\s+(freed|tied|joint)\s+([\d.]+) /\s+(\d+) dof")
EQUATION = re.compile(r"^  ([a-z]_[a-z]+) +patterns +(\d+) of +(\d+)")


def parse(path: Path) -> list[dict]:
    """Every reading in one results file, with its window's χ²_red and f."""
    out, chi2r, f, equation, window = [], None, None, None, None
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("SUMMARY"):
            break
        m = WINDOW.match(line)
        if m:
            window, chi2r, f = int(m.group(1)), float(m.group(2)), float(m.group(3))
            continue
        m = EQUATION.match(line)
        if m:
            equation = m.group(1)
            continue
        m = READ.match(line)
        if m and chi2r is not None:
            kind = m.group(1)
            out.append(dict(file=path.name, window=window, equation=None if kind == "joint" else equation,
                            kind=kind, stat=float(m.group(2)), dof=int(m.group(3)),
                            chi2r=chi2r, f=f))
    return out


def summary(label: str, ps: np.ndarray) -> None:
    if ps.size == 0:
        print(f"  {label}: none")
        return
    ks = kstest(ps, "uniform")
    print(f"  {label:34} {int((ps < 0.05).sum()):3d} of {ps.size:3d} reject at 95 % "
          f"(expected {0.05 * ps.size:4.1f}); median p {np.median(ps):.3f}; "
          f"KS D {ks.statistic:.3f}, p {ks.pvalue:.3g}")


def main() -> None:
    files = [HERE / name for name in sys.argv[1:]] or [HERE / "wo3_flex_results.txt"]
    rows = [r for path in files for r in parse(path)]
    print("WP-1325: the over-flexible arm's p-values on WO3, read three ways")
    print(f"files     {[p.name for p in files]}; {len(rows)} readings")
    for path in files:
        windows = sorted({(r['window'], r['chi2r'], r['f']) for r in rows if r['file'] == path.name})
        print(f"  {path.name}: windows (index, χ²_red, f) {windows}")
    print()
    for kind in ("freed", "tied", "joint"):
        sel = [r for r in rows if r["kind"] == kind]
        if not sel:
            continue
        stat = np.array([r["stat"] for r in sel])
        dof = np.array([r["dof"] for r in sel])
        f2 = np.array([r["f"] ** 2 for r in sel])
        c2r = np.array([r["chi2r"] for r in sel])
        print(f"{kind} readings ({len(sel)}): statistic per direction, median "
              f"{np.median(stat / dof):.3f}, range {np.min(stat / dof):.3f}-{np.max(stat / dof):.3f}"
              f" (≈1 under a right equation and a right denominator)")
        summary("over χ²_red·f² (shipped)", chi2_dist.sf(stat, dof))
        summary("over χ²_red (no f²)", chi2_dist.sf(stat * f2, dof))
        summary("over 1 (raw gain)", chi2_dist.sf(stat * f2 * c2r, dof))
        print(f"    raw gain per direction: median {np.median(stat * f2 * c2r / dof):.3f}, "
              f"range {np.min(stat * f2 * c2r / dof):.3f}-{np.max(stat * f2 * c2r / dof):.3f}")
        print()
    print("per equation, freed: file, window, equation, statistic/dof, p shipped, p no f², p raw")
    for r in rows:
        if r["kind"] != "freed":
            continue
        s, d, f2, c = r["stat"], r["dof"], r["f"] ** 2, r["chi2r"]
        print(f"  {r['file']:24} {r['window']} {r['equation']:8} {s / d:6.3f} "
              f"{chi2_dist.sf(s, d):8.3g} {chi2_dist.sf(s * f2, d):8.3g} "
              f"{chi2_dist.sf(s * f2 * c, d):8.3g}")


if __name__ == "__main__":
    main()

"""Fluorapatite Ca₅(PO₄)₃F on a laboratory Cu Kα diffractometer.

The walkthrough the landing page quotes (`docs/landing/`): read a pattern, read
a structure, pick an instrument, run a staged plan, read what the fit could not
determine. Seven atomic sites in P 6₃/m, so it is a structural refinement rather
than a cell fit, and it is still a page of code.

Data: GSAS-II tutorials `LabData`, `FAP.XRA` (GSAS STD, counts only, 5753 points
over 15–130.04° 2θ). Structure: `fluorapatite.cif`, the starting model
transcribed from the same tutorial's `FAP.EXP`, which descends from Hughes,
Cameron & Crowley (1989), *Am. Mineral.* **74**, 870-876. Provenance and licence
for both: `tests/data/README.md`.

**This script is a walkthrough, not the acceptance test.** What the numbers are
pinned against — GSAS's own converged fit of the same file, under the same
protocol — is `tests/test_acceptance_fap.py`, which builds its structure from
`FAP.EXP`'s records rather than from the CIF and holds what this one leaves
free. Two authorities, and this is not the one that decides a number.
"""

from pathlib import Path

import rietx as rx

DATA = Path(__file__).resolve().parent.parent / "tests" / "data"
HERE = Path(__file__).resolve().parent


def run() -> rx.RefinementResult:
    """The refinement itself, so anything else that needs this result reuses the
    script rather than keeping a second copy of the walkthrough."""
    data = rx.read_pattern(DATA / "FAP.XRA")
    structure = rx.Structure.from_cif(str(DATA / "fluorapatite.cif"))

    instrument = rx.Instrument.bragg_brentano(radiation="CuKa")
    # Axial divergence: the asymmetry that makes low-angle lab peaks lean. The
    # pair is the Finger-Cox-Jephcoat S/L and H/L; 0.02 is a narrow slit.
    instrument.geometry.axial_sl.value = 0.02
    instrument.geometry.axial_hl.value = 0.02
    instrument.background = rx.BackgroundChebyshev.with_terms(6)

    ref = rx.Refinement(structure, instrument)
    result = ref.fit(data, plan="mccusker_structural", two_theta_limits=(15, 130))

    print(f"{result.status}  Rwp={result.statistics.rwp:.4f}  "
          f"GoF={result.statistics.gof:.2f}")
    for name in ("a", "c"):
        p = result.parameter(f"phases.0.cell.{name}")
        print(f"  {name} = {p.value:.5f} +/- {p.stderr:.5f} A")
    for d in result.diagnostics:
        print(f"  [{d.level}] {d.code}: {d.message}")

    report = rx.build_report(result)
    print(report.summary)
    return result


if __name__ == "__main__":
    result = run()
    # Beside this script, from its own __file__, so running it from any cwd
    # writes to the same place (tests/test_examples.py relies on that).
    out = HERE / "fap_fit.png"
    try:
        result.plot(path=str(out))   # returns the figure, not the path
        print(f"wrote {out.name}")
    except ImportError:
        print("matplotlib not installed — skipped the plot")

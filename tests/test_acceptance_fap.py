"""v0.2 second lab acceptance: fluorapatite, GSAS-II "LabData" tutorial.

Cu Kα doublet on a conventional laboratory Bragg-Brentano diffractometer,
15-130° 2θ, 5753 points, counts only (Poisson σ).  Unlike the SRM 660c test —
which anchors to a NIST *certificate* — this one is a **cross-code
consistency check** against GSAS's own converged refinement of the same data,
with tolerances that respect legitimate inter-code convention differences
(docs/ROADMAP.md, "Testing & validation policy").

The protocol is read off GSAS's converged ``FAP.EXP``, so both codes refine
the same parameter set:

* zero point held at 0 (``ICONS`` third field is 0.0 and carries no refine
  flag); the specimen **displacement** refines instead (GSAS's ``shft``
  profile coefficient, converged 4.90166);
* instrument Caglioti ``GU, GV, GW`` held at the ``INST_XRY.PRM`` starting
  values (2, −2, 5 centideg² = 2e-4, −2e-4, 5e-4 deg²) — GSAS's refine flags
  for them are ``N``;
* the **sample** Lorentzian terms ``LX``, ``LY`` refine (GSAS flags ``Y``,
  converged 3.35183 and 2.48803 centideg = 0.0335 and 0.0249 deg) — i.e.
  exactly the instrument ⊕ sample profile split this milestone added;
* Kα2/Kα1 held at 0.5 (``ICONS`` ratio field, unrefined);
* 2θ > 130° excluded (GSAS's ``EXC 2`` record) — which reproduces its point
  count of 5750 exactly, so the agreement indices below are computed over the
  same channels.

**Measured result** (2026-07-22, recorded in docs/ROADMAP.md):
Rwp = 9.73 % against GSAS's 10.05 % and Rp = 7.76 % against its 7.66 %, on an
identical 5750 channels — the two codes agree on fit quality to ~1 % relative.
Refined sample broadening lands on GSAS's too: Lorentzian size 0.0323° vs its
LX = 0.0335°.  The cell is a = 9.372807 Å, c = 6.886642 Å against GSAS's
9.371724(36) and 6.885867(37): **+116 and +113 ppm**.  That the two axes are
offset by the *same relative* amount is the diagnostic — a uniform d-scale
(peak-position convention) difference, not a shape or structural disagreement;
GSAS's ``shft`` converges to the opposite sign from our refined displacement,
which is the same statement seen from the other side.  ±300 ppm is therefore
the honest consistency band here.  Certificate-grade accuracy is claimed only
by the SRM 660c test; neither code's cell is "truth" for this specimen.
"""

from pathlib import Path

import numpy as np
import pytest

import pxrdref as pr
from pxrdref.schemas.instrument import BackgroundChebyshev, EmissionLine, Source

DATA = Path(__file__).parent / "data"
pytestmark = pytest.mark.slow

# GSAS's converged values for this dataset (FAP.EXP: CRS1 ABC / ABCSIG, RPOWD)
A_GSAS, A_GSAS_ESD = 9.371724, 0.000036
C_GSAS, C_GSAS_ESD = 6.885867, 0.000037
RWP_GSAS, RP_GSAS = 0.1005, 0.0766

_EIGHT_PI2 = 8.0 * np.pi**2
#: label, species, x, y, z, Uiso — the CRS1 AT records of FAP.EXP
_ATOMS = [
    ("Ca1", "Ca", 0.333333, 0.666667, 0.001913, 0.006079),
    ("Ca2", "Ca", 0.241976, 0.992603, 0.250000, 0.004561),
    ("P3", "P", 0.397416, 0.367704, 0.250000, 0.003978),
    ("F4", "F", 0.000000, 0.000000, 0.250000, 0.013850),
    ("O5", "O", 0.325053, 0.484763, 0.250000, 0.004916),
    ("O6", "O", 0.591494, 0.469954, 0.250000, 0.006609),
    ("O7", "O", 0.339510, 0.258126, 0.070641, 0.006713),
]


@pytest.fixture(scope="module")
def fap_inputs():
    path = DATA / "FAP.XRA"
    if not path.exists():
        pytest.skip("GSAS-II LabData tutorial dataset not present")
    raw = pr.read_pattern(path)
    # GSAS's own excluded region (FAP.EXP "EXC 2  130.000 1000.000"); the file
    # runs to 130.04° and that last channel is a detector artefact
    data = pr.PatternData(
        two_theta=raw.two_theta, intensity=raw.intensity, sigma=raw.sigma,
        excluded_regions=[(129.99, 1000.0)], metadata=raw.metadata)

    cell = pr.Cell(
        a=pr.Parameter(value=9.3717, min=1.0), b=pr.Parameter(value=9.3717, min=1.0),
        c=pr.Parameter(value=6.8859, min=1.0),
        alpha=pr.Parameter(value=90.0), beta=pr.Parameter(value=90.0),
        gamma=pr.Parameter(value=120.0))
    structure = pr.Structure(phases=[pr.Phase(
        name="fluorapatite", space_group="P 63/m", cell=cell,
        atoms=[pr.Atom(label=lab, species=sp,
                       x=pr.Parameter(value=x), y=pr.Parameter(value=y),
                       z=pr.Parameter(value=z),
                       biso=pr.Parameter(value=u * _EIGHT_PI2, min=0.0, max=25.0))
               for lab, sp, x, y, z, u in _ATOMS],
        scale=pr.Parameter(value=1e-3, min=0.0, transform="softplus"),
        # GSAS LX, LY starting values (centideg → deg)
        lor_size=pr.Parameter(value=0.0335, min=0.0, transform="softplus"),
        lor_strain=pr.Parameter(value=0.0249, min=0.0, transform="softplus"))])

    instrument = pr.Instrument.bragg_brentano()
    # the tutorial's own wavelengths, not our NIST/Hölzer preset: a 60 ppm
    # wavelength difference would map straight onto the cell being compared
    instrument.source = Source(
        lines=[EmissionLine(wavelength=1.5405),
               EmissionLine(wavelength=1.5443,
                            weight=pr.Parameter(value=0.5, min=0.0, max=1.0))],
        polarization=pr.Parameter(value=0.5, min=0.0, max=1.0))
    instrument.profile.u.value = 2e-4     # GSAS GU, held
    instrument.profile.v.value = -2e-4    # GSAS GV, held
    instrument.profile.w.value = 5e-4     # GSAS GW, held
    # S/L and H/L are near-degenerate (see Geometry docstring); refine one
    instrument.geometry.axial_sl.value = 0.02
    instrument.geometry.axial_hl.value = 0.02
    instrument.background = BackgroundChebyshev.with_terms(6)
    return data, structure, instrument


def _gsas_protocol_plan() -> pr.RefinementPlan:
    """The parameter set GSAS refined for this tutorial (see module docstring)."""
    return pr.RefinementPlan(stages=[
        pr.Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"]),
        pr.Stage("disp", ["instrument.geometry.sample_displacement"]),
        pr.Stage("cell", ["phases.*.cell.*"]),
        pr.Stage("sample_lor", ["phases.*.lor_size", "phases.*.lor_strain"]),
        pr.Stage("axial", ["instrument.geometry.axial_sl"]),
        pr.Stage("biso", ["phases.*.atoms.*.biso"]),
    ])


def test_fap_lab_rietveld_matches_gsas(fap_inputs):
    data, structure, instrument = fap_inputs
    assert len(data.two_theta) == 5753
    assert data.sigma is None            # counts only ⇒ Poisson fallback

    ref = pr.Refinement(structure, instrument)
    result = ref.fit(data, plan=_gsas_protocol_plan())

    assert result.status == "converged"
    # the exclusion reproduces GSAS's channel count exactly, so the agreement
    # indices below are computed over the same data GSAS used
    assert result.statistics.n_points == 5750
    # both indices within 10 % (relative) of GSAS's on identical channels
    assert result.statistics.rwp == pytest.approx(RWP_GSAS, rel=0.10)
    assert result.statistics.rp == pytest.approx(RP_GSAS, rel=0.10)
    assert result.statistics.gof < 2.0

    phase = ref.fitted_structure.phases[0]
    a, c = phase.cell.a.value, phase.cell.c.value
    # cross-code consistency band, NOT a certificate: see module docstring
    assert abs(a / A_GSAS - 1.0) < 3e-4
    assert abs(c / C_GSAS - 1.0) < 3e-4
    # hexagonal tie: b tracks a exactly, c is independent
    assert phase.cell.b.value == pytest.approx(a, rel=1e-12)
    assert abs(c / a - C_GSAS / A_GSAS) < 1e-4

    # the offset is a uniform d-scale difference, not an axis-specific one —
    # this is the assertion that distinguishes "convention" from "wrong"
    assert abs((a / A_GSAS) - (c / C_GSAS)) < 1e-4

    # refined sample broadening agrees with GSAS's LX to ~5 % (its LY is
    # split differently between the two codes' strain conventions, so only
    # the physical range is checked there)
    assert phase.lor_size.value == pytest.approx(0.0335, rel=0.20)
    assert 0.0 <= phase.lor_strain.value < 0.15
    # the instrument resolution function was held, as in GSAS
    assert ref.fitted_instrument.profile.u.value == pytest.approx(2e-4)
    assert ref.fitted_instrument.profile.w.value == pytest.approx(5e-4)
    assert ref.fitted_instrument.zero_shift.value == 0.0

    # esds are Bérar-Lelann inflated; GSAS's are not, so ours must be larger
    a_esd = result.parameter("phases.0.cell.a").stderr
    assert a_esd is not None and A_GSAS_ESD < a_esd < 20 * A_GSAS_ESD
    assert result.statistics.esd_inflation > 1.0

    # FitReport must digest a real lab pattern end to end
    report = ref.report(plan=_gsas_protocol_plan())
    assert report.summary and report.n_regions_total > 10

    from pxrdref.viz.plots import plot_for_vlm, plot_result
    out = Path(__file__).parent / "output"
    out.mkdir(exist_ok=True)
    plot_result(result, path=str(out / "fap_fit.png"))
    plot_result(result, path=str(out / "fap_fit_lowangle.png"),
                two_theta_range=(15.0, 35.0))
    plot_for_vlm(result, report, path=str(out / "fap_vlm.png"))

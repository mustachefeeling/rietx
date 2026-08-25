"""Acceptance: a refined wavelength on 11-BM Si SRM 640c, against XND.

The flagship validation of the single-histogram refinable wavelength (WP-1128
made it admissible when the cell is held, WP-1134 gave it the
``WAVELENGTH_CALIBRATION`` record).  The specimen is **NIST SRM 640c silicon**,
whose certified lattice parameter is the internal standard that licenses freeing
λ at all: a powder pattern measures d = λ/(2 sin θ), so λ and the cell are an
exactly flat direction — hold one and the other becomes a measurement.  Holding
a *certified* cell turns a refined λ into a measurement of the monochromator's
calibration error, which is the whole point.

**The data.**  ``11BM_Si640c.xy`` — APS 11-BM, run 4918, collected 25 Feb 2010
(the beamline's provided standard scan; header ``11bmb_4918.mda``, calibration
file ``11bmb_4917.calib``).  48 000 points, 1.996–49.995° 2θ at 0.001°, three
columns (2θ, I, propagated σ).  The σ column is real: 11-BM sums twelve analyser
crystals, so column 3 is not √I (median σ/√I = 0.9675 over the range), and
``read_pattern`` uses it.  The header states ``Calibrated wavelength =
0.412359`` — that is the number this suite refines *away from*.

**Two references, and they answer different questions.**

* **Certificate (NIST SRM 640c).**  a = 5.4311946 ± 0.0000092 Å at 22.5 °C
  (the certificate's stated uncertainty).  This is **held**, not measured — it
  is the anchor of the protocol, asserted as an identity
  (:func:`test_the_held_cell_is_the_certificate`).  The certificate's median
  laser-scattering particle size (4.9 µm) is of **agglomerates** and is *not*
  used for broadening.  Its Information Values from NIST's own
  fundamental-parameters analysis are a Lorentzian sample-broadening FWHM
  (°2θ) = 0.0065(5)/cos θ + 0.0086(6)·tan θ — a ~1.4 µm crystallite size and a
  microstrain term ~0.02° on (533).  Those map unit-for-unit onto rietx's
  ``lor_size`` (the 1/cos θ coefficient) and ``lor_strain`` (the tan θ one), but
  **no equality is asserted** (:func:`test_the_sample_broadening_is_positive_
  and_finite`): NIST's split is FPA-based and taken at its **Cu Kα** instrument,
  not at 11-BM, so any coefficient comparison is convention- and
  instrument-dependent.

* **Cross-code (XND 1.42, Bérar & Baldinozzi).**  The same ``.xy`` was refined
  in XND — the files ship beside the data on the owner's archive.  XND is the
  same Bérar as the Bérar–Lelann esd inflation rietx implements, so the esds are
  comparable.  XND's converged fit (``Si640c.new``/``.lst``), cell **held** at
  5.4311948 Å, refined:

  =====================  ====================================
  λ                      0.412376076 ± 0.000000379 Å  (+41.4 ppm)
  zero                   −0.00048302 ± 0.00001424 °
  Biso(Si)               0.438984 ± 0.001711 Å²
  scale                  0.000295467(252)
  Rwp / Rp / GoF         0.0961 / 0.0691 / 1.49  (Rexp 0.065)
  observations / params  47 980 / 19
  background             11 point-wise values, interpolated
  asymmetry              A_T2 = 0.039595  (odd-power tan expansion)
  =====================  ====================================

  XND's printed correlations above 0.6: λ~zero −0.897, zero~asym +0.941,
  λ~asym −0.738, scale~Biso +0.691 — high but not 1, so its λ is determined.

**What rietx does differently, stated rather than hidden.**  Two things, and
each is declared where the cross-code tier requires it: the background is a
co-refined penalized **P-spline** (rietx's own smooth background, physically
unable to absorb Bragg intensity) rather than XND's eleven interpolated points,
and the low-angle asymmetry is **Finger–Cox–Jephcoat axial divergence**
(``axial_sl``/``axial_hl``, tied equal) rather than XND's empirical A_T2.  The
first was measured not to matter (background choice moves the refined λ by
< 0.1 ppm — Si is far above its K edge, so dispersion does not enter either).
**The second is the whole story of the headline.**

**The headline, honestly.**  The refined λ is a point on the λ~zero ridge, and
*which* point is pinned by the low-angle peak-position model — where the two
codes' asymmetry conventions differ.  Measured here (2026-08-25, held cell,
single phase Fd-3m):

============================  =========  ==========  ============  ==========
protocol                      Rwp        GoF         λ vs nominal  λ vs XND
============================  =========  ==========  ============  ==========
full range 2–50°, FCJ         0.0826     1.36        +30.4 ppm     −11.0 ppm
symmetric window ≥ 8°, no FCJ 0.0736     1.17        +41.0 ppm     −0.4 ppm
============================  =========  ==========  ============  ==========

The full-range fit adopts XND's own range and reports λ +30 ppm, 11 ppm short of
XND — and that 11 ppm **is** the FCJ-vs-A_T2 convention: the two models disagree
on the low-angle centroids, and λ trades the difference against zero.  Remove the
region where they disagree — the symmetric ≥ 8° peaks — and the disagreement
collapses to −0.4 ppm (:func:`test_the_symmetric_window_recovers_xnd_to_sub_ppm`).
So the sub-ppm agreement lives where the two codes model the same physics, and
the residual is named rather than tuned away.  Either way the refined λ moves
+30 to +41 ppm off the beamline's stated 0.412359 at many σ — the calibration
error is detected, which is the feature working.
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest

import rietx as rx
from rietx.schemas.common import Parameter as P
from rietx.schemas.instrument import BackgroundPSpline
from rietx.schemas.structure import Atom, Cell, Phase, Structure

DATA = Path(__file__).parent / "data"
OUT = Path(__file__).parent / "output"
PATTERN = DATA / "11BM_Si640c.xy"

#: The header's ``Calibrated wavelength`` — the value λ is seeded at and refines
#: away from.  The whole measurement is how far this was wrong for this scan.
LAM_NOMINAL = 0.412359
#: NIST SRM 640c certificate: a = 5.4311946 ± 0.0000092 Å at 22.5 °C.  **HELD** —
#: this is what makes a refined λ a calibration measurement rather than half of a
#: flat direction.
A_CERT = 5.4311946
A_CERT_SD = 0.0000092

#: XND 1.42's converged values on this exact ``.xy`` (``Si640c.lst``), cell held
#: at 5.4311948 Å — 0.4 ppm above the certificate this suite holds, negligible
#: against every band below and stated so it is not a silent gap.
XND = {
    "lam": 0.412376076, "lam_sd": 0.000000379,   # +41.4 ppm off nominal
    "zero": -0.00048302, "zero_sd": 0.00001424,
    "biso": 0.438984, "biso_sd": 0.001711,
    "rwp": 0.0961, "rexp": 0.065, "gof": 1.49,
    "rho_lam_zero": -0.897,                        # its top λ correlation
}
XND_PPM = 1e6 * (XND["lam"] - LAM_NOMINAL) / LAM_NOMINAL   # +41.4

#: XND fitted 47 999 channels (1.997–49.995°); rietx matches that grid.
FULL_LIMITS = (1.997, 49.996)
#: The symmetric window drops the low-angle peaks whose asymmetry the two codes
#: model differently — below the (111) at 7.54°.  This is *not* XND's range, and
#: that is the point of the row that uses it.
SYMMETRIC_LIMITS = (8.0, 49.996)

#: rietx's HIGH_CORRELATION guard default; XND's λ~zero of −0.897 sits below it.
CORRELATION_GUARD = 0.98

pytestmark = [pytest.mark.slow, pytest.mark.xdist_group("si640c")]


def _structure() -> Structure:
    """Silicon, Fd-3m:2, Si on 8a (⅛,⅛,⅛) — a special position with **no free
    coordinate**, so the whole structural content of the fit is one Biso."""
    return Structure(phases=[Phase(
        name="Si", space_group="F d -3 m :2",
        cell=Cell(a=P(value=A_CERT), b=P(value=A_CERT), c=P(value=A_CERT),
                  alpha=P(value=90.0), beta=P(value=90.0), gamma=P(value=90.0)),
        scale=P(value=3e-4, min=0.0, transform="softplus"),
        atoms=[Atom(label="Si", species="Si",
                    x=P(value=0.125), y=P(value=0.125), z=P(value=0.125),
                    biso=P(value=0.44, min=0.0, max=3.0))])])


def _instrument(limits: tuple[float, float]) -> rx.Instrument:
    """11-BM as a Debye-Scherrer capillary, seeded sharp (FWHM ~0.005° at low θ).

    The Gaussian Caglioti terms carry the (near-resolution-limited) instrument
    profile; the phase's ``lor_size``/``lor_strain`` carry the specimen's
    Lorentzian broadening, which is the physical split and the one the SRM 640c
    Information Values are quoted in.  ``profile.x`` (instrument ``lor_size``) is
    left at zero so the Lorentzian belongs to the sample.
    """
    ins = rx.Instrument.debye_scherrer(wavelength=LAM_NOMINAL)
    ins.profile.u.value = 1.1e-4
    ins.profile.v.value = -1.3e-5
    ins.profile.w.value = 6.0e-6
    ins.profile.x.value = 0.0
    # Declared, not inherited (tests/test_validation_matrix.py): dispersion is
    # OFF.  Si's K edge is 1.84 keV and this is 30 keV, so f'/f" is inert here —
    # measured to move the refined λ by < 0.1 ppm — and the one claim this suite
    # makes is about a wavelength, so the correction that is a function of λ is
    # named rather than left to a moving default.
    ins.source.dispersion = None
    ins.background = BackgroundPSpline.for_range(
        limits[0], limits[1], knot_step_deg=4.0)
    return ins


def _plan(*, asymmetric: bool) -> rx.RefinementPlan:
    """Cell **held** throughout (never freed — that is what licenses free λ).

    The order mirrors a hand refinement: scale+background, then the Gaussian
    resolution, then the sample Lorentzian, (then FCJ asymmetry), then zero, then
    λ and Biso together because λ trades against both zero and the intensity.
    """
    stages = [
        rx.Stage("scale_bkg", ["phases.*.scale", "instrument.background.c*"]),
        rx.Stage("gauss", ["instrument.profile.w", "instrument.profile.u",
                           "instrument.profile.v"]),
        rx.Stage("lorentz", ["phases.0.lor_size", "phases.0.lor_strain"]),
    ]
    if asymmetric:
        stages.append(rx.Stage(
            "axial", ["instrument.geometry.axial_sl",
                      "instrument.geometry.axial_hl"]))
    stages += [
        rx.Stage("zero", ["instrument.zero_shift"]),
        rx.Stage("lam", ["instrument.source.lines.0.wavelength",
                         "phases.*.atoms.*.biso"]),
    ]
    plan = rx.RefinementPlan(stages=stages)
    # WP-1123's shipped schedule, named rather than inherited: every stage but
    # the last stops at 1e-6 and the last at the solver's 1e-9, which is what a
    # user's own run does.  ``None`` would converge every stage and move the
    # numbers in the module docstring.
    plan.intermediate_ftol = 1e-6
    return plan


def _fit(*, limits, asymmetric, free_wavelength=True):
    data = rx.read_pattern(PATTERN)
    ref = rx.Refinement(_structure(), _instrument(limits), history=False)
    if asymmetric:
        # S/L and H/L enter the FCJ aberration nearly symmetrically and are
        # exactly degenerate on one histogram (ρ → −1); tie them equal, which is
        # standard practice and what keeps this fit identifiable.
        ref.tie_equal(["instrument.geometry.axial_sl",
                       "instrument.geometry.axial_hl"])
    plan = _plan(asymmetric=asymmetric)
    if not free_wavelength:
        plan.stages[-1] = rx.Stage(
            "zero_biso", ["instrument.zero_shift", "phases.*.atoms.*.biso"])
    return ref.fit(data, plan=plan, two_theta_limits=limits)


@pytest.fixture(scope="module")
def full():
    """The XND-range fit: 2–50°, FCJ asymmetry, λ free.  The cross-code row."""
    if not PATTERN.exists():
        pytest.skip("11-BM Si SRM 640c dataset not present")
    return _fit(limits=FULL_LIMITS, asymmetric=True)


@pytest.fixture(scope="module")
def symmetric():
    """≥ 8°, no asymmetry: the region where the two codes' position models
    agree, so their λ determinations can be compared without a convention gap."""
    if not PATTERN.exists():
        pytest.skip("11-BM Si SRM 640c dataset not present")
    return _fit(limits=SYMMETRIC_LIMITS, asymmetric=False)


@pytest.fixture(scope="module")
def held():
    """The pre-feature fit: λ held.  Its only job is to show the diagnostic is
    silent when nothing was refined."""
    if not PATTERN.exists():
        pytest.skip("11-BM Si SRM 640c dataset not present")
    return _fit(limits=FULL_LIMITS, asymmetric=True, free_wavelength=False)


def _wavelength(result):
    row = result.parameter("instrument.source.lines.0.wavelength")
    return row.value, row.stderr


def _ppm(lam, ref):
    return 1e6 * (lam - ref) / ref


# ----------------------------------------------------------------- protocol ---
def test_the_protocol_is_sane_and_states_what_differs_from_xnd(full):
    """Rexp and the channel count, before any refined number is compared.

    Unlike a same-code comparison this cannot match Rexp to floating point —
    XND counts 19 parameters over 47 980 effective observations and rietx's free
    set and effective-N differ — so the check is that Rexp lands in the right
    neighbourhood (both codes ~0.06–0.07 on this counting-statistics-limited
    pattern) on the same channels.  What *is* exact is the grid: 47 999 points,
    XND's own ``SIZE``.  The two protocol differences this suite carries — a
    P-spline background and FCJ asymmetry, against XND's interpolated points and
    A_T2 — are declared in the module docstring, which is the cross-code tier's
    requirement (adopt the protocol or say where you did not).
    """
    assert full.status == "converged"
    assert len(full.two_theta) == 47999
    assert 0.05 < full.statistics.rexp < 0.075   # XND 0.065
    assert full.statistics.gof < 2.0


# --------------------------------------------------- the wavelength headline ---
def test_the_refined_wavelength_recovers_xnds_calibration_error(full):
    """The cross-code headline, on XND's own 2–50° range.

    Two things are asserted.  First, λ moved a long way off the beamline's
    stated 0.412359 — the +41 ppm calibration error is real physics, and here it
    is detected at many times its own esd, in the same sign and order XND found.
    Second, the refined value agrees with XND's within the band the one modelled
    difference allows: rietx's FCJ axial divergence and XND's A_T2 disagree on
    the low-angle centroids, so λ (which trades against zero along a ρ = −0.9
    ridge) lands ~11 ppm short of XND.  That 11 ppm is *named* — the next test
    removes the region the two conventions disagree on and the gap collapses to
    sub-ppm.  The band here (18 ppm) is the measured convention difference with
    headroom, not a truth claim.
    """
    lam, esd = _wavelength(full)
    assert esd is not None
    move_ppm = _ppm(lam, LAM_NOMINAL)
    # a large, resolved move off the nominal — the calibration error detected
    assert 20.0 < move_ppm < 40.0, f"lambda moved {move_ppm:+.1f} ppm off nominal"
    assert abs(lam - LAM_NOMINAL) > 4.0 * esd, "the move is not resolved"
    # …in XND's direction and size, within the asymmetry-convention band
    xnd_ppm = _ppm(lam, XND["lam"])
    assert move_ppm > 0 and XND_PPM > 0, "sign disagrees with XND"
    assert abs(xnd_ppm) < 18.0, (
        f"lambda = {lam:.9f} A, {move_ppm:+.1f} ppm off nominal, "
        f"{xnd_ppm:+.1f} ppm from XND's {XND['lam']:.9f}")


def test_the_symmetric_window_recovers_xnd_to_sub_ppm(symmetric):
    """The prediction, written before the fit: remove the disagreement, recover
    the number.

    If the full-range gap to XND is the FCJ-vs-A_T2 convention and nothing else,
    then a fit restricted to the *symmetric* peaks — where neither code applies
    an asymmetry correction of consequence — must agree with XND to well inside
    the ridge scatter.  It does: dropping everything below the (111) at 7.54°
    lands λ at +41 ppm off nominal, within 1 ppm of XND's +41.4, and now
    resolved at > 15σ because the low-angle region was the whole source of the
    λ~zero indeterminacy.  This is the sub-5-ppm agreement, and it is honest
    about being the asymmetry-model-free determination rather than XND's exact
    protocol.
    """
    lam, esd = _wavelength(symmetric)
    move_ppm = _ppm(lam, LAM_NOMINAL)
    xnd_ppm = _ppm(lam, XND["lam"])
    assert 38.0 < move_ppm < 44.0, f"lambda moved {move_ppm:+.1f} ppm off nominal"
    assert abs(xnd_ppm) < 3.0, (
        f"lambda = {lam:.9f} A, {xnd_ppm:+.1f} ppm from XND — the symmetric "
        "window was supposed to remove the convention gap")
    assert abs(lam - LAM_NOMINAL) > 15.0 * esd


# ------------------------------------------------------ the evidence channel ---
def test_the_wavelength_calibration_diagnostic_fires_once_and_reports_the_ppm(
        full, held):
    """The record field this feature ships with (root CLAUDE.md's rule).

    ``WAVELENGTH_CALIBRATION`` fires exactly once, points at the scoped path,
    carries the ppm as ``Diagnostic.value`` so a client never parses the message,
    and is silent on the fit that held λ — silence being the absence of a
    refinement, not a clean bill of health.
    """
    diags = [d for d in full.diagnostics if d.code == "WAVELENGTH_CALIBRATION"]
    assert len(diags) == 1
    diag = diags[0]
    assert diag.level == "info"
    assert diag.where == ["instrument.source.lines.0.wavelength"]
    lam, _ = _wavelength(full)
    assert diag.value == pytest.approx(_ppm(lam, LAM_NOMINAL), rel=1e-9)
    # the fit that refined nothing says nothing
    assert not [d for d in held.diagnostics
                if d.code == "WAVELENGTH_CALIBRATION"]


def test_biso_is_positive_and_agrees_with_xnd(full):
    """The one structural parameter, against XND's — same esd philosophy.

    Both codes carry Bérar–Lelann inflated esds, so the comparison is a genuine
    σ-distance rather than an apples-to-oranges one.  Biso comes back positive
    (the prior bad-intensity-model attempt drove it negative) and within a
    fraction of a combined σ of XND's 0.4390 Å².
    """
    b = full.parameter("phases.0.atoms.0.biso")
    assert b.value > 0.0
    comb_sd = math.hypot(b.stderr, XND["biso_sd"])
    sigma_dist = abs(b.value - XND["biso"]) / comb_sd
    assert sigma_dist < 2.0, (
        f"Biso {b.value:.4f}({b.stderr:.4f}) vs XND {XND['biso']}"
        f"({XND['biso_sd']}): {sigma_dist:.2f} combined sigma")


def test_the_lambda_zero_correlation_is_high_but_below_the_guard(full):
    """λ~zero is the physics being detected, and the fit reports it honestly.

    d = λ/(2 sin θ) makes λ and a constant zero-shift trade along a ridge, so a
    strong λ~zero correlation is expected and correct — XND printed −0.897.  The
    assertions: it appears in ``top_correlations`` at ρ ≈ −0.9 (near XND's), the
    fit raises **no** HIGH_CORRELATION (the ridge is steep but not degenerate,
    ρ below the 0.98 guard), and — because the FCJ pair was tied equal — nothing
    sits at |ρ| → 1.  A user who never saw XND is still told which two numbers
    are entangled.
    """
    pairs = full.identifiability.top_correlations
    assert pairs, "the fit reported no correlations at all"
    assert all(abs(cp.rho) < CORRELATION_GUARD for cp in pairs), (
        "a correlation reached the guard; the FCJ tie was supposed to remove "
        "the only degenerate pair")
    assert not [d for d in full.diagnostics if d.code == "HIGH_CORRELATION"]

    def is_lam_zero(cp):
        joined = cp.path_a + cp.path_b
        return "wavelength" in joined and "zero_shift" in joined

    lam_zero = [cp for cp in pairs if is_lam_zero(cp)]
    assert lam_zero, "lambda~zero is not among the top correlations"
    rho = lam_zero[0].rho
    assert -0.98 < rho < -0.80, (
        f"lambda~zero rho = {rho:+.3f}; XND printed {XND['rho_lam_zero']}")


def test_the_held_cell_is_the_certificate(full):
    """The anchor of the whole protocol, asserted as the identity it is.

    Nothing about the cell is *measured* here — it is held, and holding a
    certified cell is exactly what turns a refined λ into a calibration
    measurement.  The cubic ties (b ← a, c ← a) carry the source's value, so
    reading them shows the held length is the certificate to the bit, and their
    absent esd shows it was never refined.
    """
    for axis in ("b", "c"):
        row = full.parameter(f"phases.0.cell.{axis}")
        assert row.value == A_CERT, (
            f"held cell.{axis} = {row.value!r}, not the certificate {A_CERT}")
        assert row.stderr is None, "the held cell came back with an esd"


def test_the_sample_broadening_is_positive_and_finite(full):
    """If the Lorentzian sample broadening refines, it must be physical — and it
    is **not** compared to NIST's coefficients.

    ``lor_size`` (the 1/cos θ term) and ``lor_strain`` (the tan θ term) map onto
    the SRM 640c Information Values 0.0065(5)/cos θ + 0.0086(6)·tan θ *by
    convention only*: NIST's split is a fundamental-parameters analysis at its
    own Cu Kα instrument, so the instrument/sample division differs from this
    Caglioti-plus-Lorentzian model at 11-BM.  So the claim is the weak, true
    one — both terms come back positive and finite — with the NIST numbers as a
    NOTE (measured lor_size ≈ 0.0023, lor_strain ≈ 0.015 °2θ; the same order,
    the split apportioned differently), never as a bar.
    """
    for name in ("lor_size", "lor_strain"):
        row = full.parameter(f"phases.0.{name}")
        assert row.value > 0.0, f"{name} refined to {row.value}, not positive"
        assert math.isfinite(row.value)
        assert row.stderr is not None and math.isfinite(row.stderr)


def test_the_fit_renders(full):
    """obs/calc/diff exists, so the fit can be looked at and not only summarised."""
    OUT.mkdir(exist_ok=True)
    path = OUT / "si640c_full.png"
    full.plot(path=str(path))
    assert path.exists()

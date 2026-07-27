"""Cylindrical (capillary) absorption — WP-0501.

The correction is Rouse, Cooper, York & Chakera (1970), *Acta Cryst.* A26, 682,
eq. (2).  Its ground truth here is two-layered and deliberately so:

* ``tests/data/absorption_cylinder_rouse.dat`` — the paper's own Table 1, the
  published anchor;
* ``_itc_exact_A`` below — a quadrature of *International Tables* Vol. C
  eq. (6.3.3.4), the exact cylinder transmission integral, which shares no
  constant with the implementation.

The second layer is not redundant.  The scan this WP was written from prints the
b₂ coefficient as "−0·0375" when it is −0·3750, and that error is **invisible**
against the sin²θ = 0 column of the published table (which constrains only a₁
and a₂) while being 0.0821 wrong at µR = 1.  Anything checking this expression
must span sin²θ.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from pydantic import ValidationError

from pxrdref.crystallography.attenuation import linear_attenuation, packed_mu_r
from pxrdref.model.absorption import (
    cylinder_absorption,
    cylinder_absorption_and_dmur,
    equivalent_delta_biso,
    mu_r_identifiable_fraction,
)
from pxrdref.optimize.qpa import estimate_capillary_mu_r
from pxrdref.params.vector import ParameterTable
from pxrdref.refine import estimate_mu_r
from pxrdref.schemas.common import Parameter
from pxrdref.schemas.instrument import Geometry, Instrument

DATA = Path(__file__).parent / "data" / "absorption_cylinder_rouse.dat"


# -- the independent physics: ITC Vol. C eq. (6.3.3.4) ------------------


def _itc_exact_A(mu_r: float, theta_deg: float,
                 n_r: int = 200, n_phi: int = 720) -> float:
    """A = (1/πR²)∫exp(−µ(ℓ_in + ℓ_out))dA over the unit disc.

    The transmission coefficient of ITC Vol. C eq. (6.3.3.1) specialised to a
    cylinder in the equatorial plane, eq. (6.3.3.4).  Written as the plain 2-D
    area integral rather than ITC's cosh-folded form: for a point p the exit
    distance along a unit direction û is

        ℓ(p, û) = −p·û + √(R² − |p|² + (p·û)²)

    and the incident path is the exit distance along −û_i.  Gauss-Legendre in
    r² (so the nodes are uniform in *area*) × midpoint in φ.  Validated by the
    µR → 0 limit, which must reproduce the mean chord of a circle, 16/(3π).
    """
    th = np.radians(theta_deg)
    ui = np.array([1.0, 0.0])
    ud = np.array([np.cos(2.0 * th), np.sin(2.0 * th)])
    x, w = np.polynomial.legendre.leggauss(n_r)
    r = np.sqrt(0.5 * (x + 1.0))
    phi = (np.arange(n_phi) + 0.5) * 2.0 * np.pi / n_phi
    p = r[:, None] * np.stack([np.cos(phi), np.sin(phi)])[:, None, :]
    pu_i = -(p[0] * ui[0] + p[1] * ui[1])
    pu_d = p[0] * ud[0] + p[1] * ud[1]
    rr = r[:, None] ** 2
    l_in = -pu_i + np.sqrt(np.maximum(1.0 - rr + pu_i ** 2, 0.0))
    l_out = -pu_d + np.sqrt(np.maximum(1.0 - rr + pu_d ** 2, 0.0))
    return float((w * 0.5) @ np.exp(-mu_r * (l_in + l_out)).mean(axis=1))


def _theta_of_s(s):
    """Bragg angle θ in degrees from sin²θ."""
    return np.degrees(np.arcsin(np.sqrt(np.clip(s, 0.0, 1.0))))


def _load_rouse():
    mu, s, a = np.loadtxt(DATA, comments="#", unpack=True)
    return mu, s, a


# -- the quadrature is itself anchored ---------------------------------


def test_itc_quadrature_reproduces_the_mean_chord_of_a_circle():
    """As µR → 0, −ln A / µR is the mean chord through the disc = 16/(3π).

    This is the only check the quadrature gets that does not come from a
    table, so it is what licenses using it as the primary gate.
    """
    slope = -np.log(_itc_exact_A(1e-6, 0.0)) / 1e-6
    assert slope == pytest.approx(16.0 / (3.0 * np.pi), rel=1e-5)


def test_itc_quadrature_matches_the_published_rouse_table():
    """Two independent representations of the same physics agree.

    Bounds the transcription risk in the fixture: 1.7e-4, inside the table's
    own four-decimal resolution.
    """
    mu, s, a = _load_rouse()
    q = np.array([_itc_exact_A(m, t) for m, t in zip(mu, _theta_of_s(s))])
    assert np.abs(q - a).max() < 5e-4


# -- schema ------------------------------------------------------------


def test_capillary_geometry_defaults_are_off():
    geom = Geometry(kind="debye_scherrer")
    assert geom.mu_r is None
    assert geom.capillary_radius_mm is None
    assert geom.packing_fraction == 0.6


def test_capillary_fields_are_plain_floats_not_parameters():
    """µR and the packing fraction must never become refinable.

    µR is *exactly* a linear combination of the scale and Biso columns (the
    Rouse expression factors into a constant times exp(c·sin²θ)), and the
    packing fraction is exactly degenerate with µR.  Promoting either to a
    ``Parameter`` would add a singular direction to the normal equations, so
    the type itself is the guard.
    """
    geom = Geometry(kind="debye_scherrer", mu_r=0.5, capillary_radius_mm=0.25)
    for name in ("mu_r", "capillary_radius_mm", "packing_fraction"):
        assert not isinstance(getattr(geom, name), Parameter)
        assert isinstance(getattr(geom, name), float)


def test_capillary_fields_round_trip_through_json():
    geom = Geometry(kind="debye_scherrer", mu_r=0.75,
                    capillary_radius_mm=0.3, packing_fraction=0.45)
    back = Geometry.model_validate_json(geom.model_dump_json())
    assert back.mu_r == 0.75
    assert back.capillary_radius_mm == 0.3
    assert back.packing_fraction == 0.45


@pytest.mark.parametrize("kwargs", [
    {"mu_r": 0.5},
    {"capillary_radius_mm": 0.25},
])
def test_capillary_fields_rejected_under_bragg_brentano(kwargs):
    with pytest.raises(ValidationError, match="debye_scherrer"):
        Geometry(kind="bragg_brentano", goniometer_radius_mm=217.5, **kwargs)


@pytest.mark.parametrize("kwargs, match", [
    ({"mu_r": -0.1}, "non-negative"),
    ({"capillary_radius_mm": 0.0}, "positive"),
    ({"packing_fraction": 0.0}, "greater than 0"),
    ({"packing_fraction": 1.5}, "less than or equal to 1"),
])
def test_capillary_fields_reject_unphysical_values(kwargs, match):
    with pytest.raises(ValidationError, match=match):
        Geometry(kind="debye_scherrer", **kwargs)


def test_debye_scherrer_preset_leaves_absorption_off_by_default():
    """The preset's historical meaning must not change under callers' feet.

    Every existing acceptance test builds its instrument this way; if the
    default acquired a µR their numbers would move.
    """
    ins = Instrument.debye_scherrer(wavelength=1.5406)
    assert ins.geometry.mu_r is None
    assert ins.geometry.capillary_radius_mm is None


def test_debye_scherrer_preset_passes_capillary_fields_through():
    ins = Instrument.debye_scherrer(wavelength=1.5406, capillary_radius_mm=0.25,
                                    packing_fraction=0.5, mu_r=0.8)
    assert ins.geometry.capillary_radius_mm == 0.25
    assert ins.geometry.packing_fraction == 0.5
    assert ins.geometry.mu_r == 0.8


# -- the correction vs its two ground truths ---------------------------


def test_cylinder_absorption_matches_the_published_rouse_table():
    mu, s, a = _load_rouse()
    # cylinder_absorption takes 2theta; the fixture is indexed by sin^2(theta)
    got = np.array([cylinder_absorption(np.array([2.0 * t]), m)[0]
                    for m, t in zip(mu, _theta_of_s(s))])
    assert np.abs(got - a).max() < 3.5e-3
    assert (s > 0.5).any(), "fixture must span sin^2(theta), or b1/b2 go unchecked"


def test_cylinder_absorption_matches_exact_physics_across_mu_r_and_theta():
    """The gate that a constant-θ slice cannot provide.

    Spans sin²θ from 0 to 1 as well as µR, because the b₂ coefficient is
    invisible at fixed θ — that is exactly how a digit transposition survived
    a check against the published table.  The bound is the paper's own claimed
    fit accuracy, 0.0035, and the implementation meets it with nothing to spare,
    which is itself the evidence that the coefficients are the right ones.
    """
    mus = np.arange(0.05, 1.0001, 0.05)
    s = np.linspace(0.0, 1.0, 11)
    tt = 2.0 * _theta_of_s(s)
    err = np.array([np.abs(cylinder_absorption(tt, m)
                           - np.array([_itc_exact_A(m, t) for t in _theta_of_s(s)]))
                    for m in mus])
    assert err.max() < 3.5e-3
    # the test would be vacuous if a wrong b2 also passed
    worst_s = np.abs(cylinder_absorption(tt, 1.0)
                     - np.array([_itc_exact_A(1.0, t) for t in _theta_of_s(s)]))
    assert worst_s.max() > 1e-4, "tolerance is far looser than the true agreement"


def test_a_wrong_b2_would_fail_the_exact_check():
    """Guards the guard: pin that the sin²θ span is what gives the test power.

    With b₂ mis-transcribed as −0.0375 the error against exact physics is
    ~0.08, more than 20× the bound — but only once sin²θ is varied.
    """
    s = np.linspace(0.0, 1.0, 11)
    th = _theta_of_s(s)
    exact = np.array([_itc_exact_A(1.0, t) for t in th])
    bad = np.exp(-(1.7133 - 0.0368 * s) * 1.0 - (-0.0927 - 0.0375 * s) * 1.0)
    assert np.abs(bad - exact).max() > 0.05
    at_zero_theta = abs(bad[0] - exact[0])
    assert at_zero_theta < 3.5e-3, "the bad coefficients agree at sin^2(theta)=0"


def test_absorption_is_exactly_the_identity_when_mu_r_is_zero():
    """Bit-for-bit, not merely close — this protects the backend goldens."""
    tt = np.linspace(5.0, 150.0, 64)
    assert np.array_equal(cylinder_absorption(tt, 0.0), np.ones_like(tt))


def test_derivative_matches_central_finite_difference():
    tt = np.linspace(5.0, 150.0, 17)
    for mu in (0.05, 0.3, 0.7, 1.0):
        h = 1e-6
        fd = (cylinder_absorption(tt, mu + h) - cylinder_absorption(tt, mu - h)) / (2 * h)
        _, dan = cylinder_absorption_and_dmur(tt, mu)
        assert dan == pytest.approx(fd, rel=1e-6)


def test_direction_and_range_conventions():
    """A ≤ 1, falls with µR, and *rises* with 2θ.

    The last one is the convention guard: the mean path through a cylinder is
    longest in forward scattering, so transmission improves toward backscatter.
    Swap sin²θ for cos²θ, or return A* instead of A, and this inverts while the
    µR = 0 identity test stays green.
    """
    tt = np.linspace(5.0, 175.0, 64)
    for mu in (0.1, 0.5, 1.0):
        a = cylinder_absorption(tt, mu)
        assert np.all(a > 0.0) and np.all(a <= 1.0)
        assert np.all(np.diff(a) > 0.0), "A must increase with 2theta"
    for tt_one in (10.0, 90.0, 170.0):
        seq = [cylinder_absorption(np.array([tt_one]), m)[0]
               for m in np.linspace(0.0, 1.0, 21)]
        assert np.all(np.diff(seq) < 0.0), "A must decrease with muR"


def test_mu_r_carries_no_information_a_free_scale_and_biso_lack():
    """The standing proof behind ``Geometry.mu_r`` not being a ``Parameter``.

    ∂lnA/∂µR lies exactly in span{1, sin²θ} — the subspace a free phase scale
    and a free Biso already span — so a µR column would be an exactly singular
    direction in the normal equations.  If this ever stops holding, the design
    decision has to be revisited deliberately rather than by accident.
    """
    tt = np.linspace(5.0, 150.0, 128)
    for mu in (0.1, 0.5, 1.0):
        assert mu_r_identifiable_fraction(tt, mu) < 1e-12


def test_equivalent_delta_biso_matches_a_direct_debye_waller_fit():
    """ΔB is the whole physical content, so it is checked against the model.

    Fits exp(−2ΔB·sin²θ/λ²) to 1/A and requires the closed form to agree.
    """
    lam = 1.5406
    tt = np.linspace(5.0, 150.0, 200)
    s = np.sin(np.radians(tt / 2.0)) ** 2
    for mu, expect in ((0.5, 0.1331), (1.0, 0.4887)):
        a = cylinder_absorption(tt, mu)
        slope = np.polyfit(s, np.log(a), 1)[0]          # ln A = const + c*s
        assert equivalent_delta_biso(mu, lam) == pytest.approx(slope * lam ** 2 / 2,
                                                               rel=1e-10)
        assert equivalent_delta_biso(mu, lam) == pytest.approx(expect, abs=5e-4)
    assert equivalent_delta_biso(0.0, lam) == 0.0


# -- the µR estimator --------------------------------------------------


def _lab6():
    from tests.test_schemas import make_lab6
    return make_lab6()


#: the cell make_lab6 uses, needed for the by-hand mu cross-check
_LAB6_A = 4.1566


def test_packed_mu_r_scales_linearly_with_radius_and_packing():
    base = packed_mu_r([100.0], [1.0], radius_mm=0.5, packing_fraction=0.6)
    assert packed_mu_r([100.0], [1.0], 1.0, 0.6) == pytest.approx(2 * base)
    assert packed_mu_r([100.0], [1.0], 0.5, 0.3) == pytest.approx(0.5 * base)
    # mu = 100/cm, R = 0.05 cm, f = 0.6  ->  muR = 3.0
    assert base == pytest.approx(3.0)


def test_packed_mu_r_weights_phases_by_volume_fraction():
    mixed = packed_mu_r([100.0, 300.0], [0.25, 0.75], 0.5, 1.0)
    assert mixed == pytest.approx(packed_mu_r([250.0], [1.0], 0.5, 1.0))


@pytest.mark.parametrize("kwargs, match", [
    ({"radius_mm": 0.0}, "radius must be positive"),
    ({"packing_fraction": 0.0}, "packing fraction"),
    ({"packing_fraction": 1.5}, "packing fraction"),
])
def test_packed_mu_r_rejects_unphysical_inputs(kwargs, match):
    args = {"radius_mm": 0.5, "packing_fraction": 0.6, **kwargs}
    with pytest.raises(ValueError, match=match):
        packed_mu_r([100.0], [1.0], **args)


def test_estimate_mu_r_reproduces_the_underlying_linear_attenuation():
    """µR is exactly f_pack · µ · R, and that is asserted against µ directly."""
    ins = Instrument.debye_scherrer(wavelength=1.5406, capillary_radius_mm=0.5,
                                    packing_fraction=0.6)
    mu_r = estimate_mu_r(_lab6(), ins)
    mu_cm = linear_attenuation({"La": 1.0, "B": 6.0}, _LAB6_A ** 3, 1.5406)
    assert mu_r == pytest.approx(0.6 * mu_cm * 0.05)   # 0.5 mm = 0.05 cm


def test_estimate_mu_r_spans_the_regimes_a_real_capillary_experiment_does():
    """The estimator's job is to tell a user which regime they are in.

    LaB6 is the worked case because it is the standard everyone owns and it is
    brutally absorbing at Cu Kα.  µ falls roughly as λ³ away from edges, so the
    same specimen moves from far outside the Rouse fit to comfortably inside it
    on the two axes an experimenter actually controls:

        Cu Kα, R = 0.5 mm  →  µR ≈ 34    unusable; the beam barely gets through
        Cu Kα, R = 0.1 mm  →  µR ≈ 6.8   still outside the model
        0.414 Å, R = 0.5 mm →  µR ≈ 1.0   at the edge of validity
        0.414 Å, R = 0.1 mm →  µR ≈ 0.20  fine, and the correction is small

    That last row is why the 11-BM acceptance pattern needs no absorption term,
    and the first is why an estimate is worth reporting even when the model
    then declines to use it.
    """
    lab6 = _lab6()

    def mu_r(lam, r):
        return estimate_mu_r(lab6, Instrument.debye_scherrer(
            wavelength=lam, capillary_radius_mm=r))

    assert mu_r(1.5406, 0.5) == pytest.approx(34.1, rel=0.02)
    assert mu_r(1.5406, 0.1) == pytest.approx(6.82, rel=0.02)
    assert mu_r(0.4139090, 0.5) == pytest.approx(1.01, rel=0.02)
    assert mu_r(0.4139090, 0.1) == pytest.approx(0.20, rel=0.02)
    # the wavelength lever is the strong one
    assert mu_r(0.4139090, 0.5) < mu_r(1.5406, 0.5) / 20.0


def test_estimate_mu_r_is_none_without_a_capillary_radius():
    assert estimate_mu_r(_lab6(), Instrument.debye_scherrer(wavelength=1.5406)) is None


def test_estimate_mu_r_is_none_for_bragg_brentano():
    assert estimate_mu_r(_lab6(), Instrument.bragg_brentano()) is None


def test_estimator_degrades_to_a_reason_rather_than_raising():
    """Edge straddling and missing elements are specimen facts, not bugs.

    The attenuation tables refuse to interpolate across an absorption edge;
    that must surface as a reason a caller can report, exactly as the Brindley
    path does, not as an exception out of the middle of a refinement.
    """
    lab6 = _lab6()
    table = ParameterTable(lab6, Instrument.debye_scherrer(wavelength=1.5406))
    values = table.decode(table.x0())
    # 1.5 A is fine; 0.05 A is far outside the 2-120 keV tabulation
    mu_r, reason = estimate_capillary_mu_r(lab6, values, 0.05, 0.5, 0.6)
    assert mu_r is None and reason is not None
    assert "attenuation unavailable" in reason
    mu_r, reason = estimate_capillary_mu_r(lab6, values, 1.5406, 0.5, 0.6)
    assert mu_r is not None and reason is None

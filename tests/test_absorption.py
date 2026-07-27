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

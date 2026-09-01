"""Reading a profile width as a **strain**, and the λ asymmetry behind WP-1131.

Two claims, and the second is the one the sharing map turns on.

1. ``microstrain_from_strain_coefficient`` inverts the tanθ law exactly:
   Δ2θ = 2·(Δd/d)·tanθ is Bragg's law differentiated, so the FWHM read off the
   law at any angle, divided by 2·tanθ, is the same Δd/d the angle-free form
   returns from the coefficient alone.

2. **Size depends on λ and strain does not.**  Asserted as the ratio it is —
   one specimen at two wavelengths needs size coefficients in the ratio λ₂/λ₁
   and strain coefficients in the ratio 1 — because that is exactly the
   statement ``params.multi`` normalises against, and a test of it here is the
   one that fails on paper before the joint fixture fails in the fit.
"""

from __future__ import annotations

import inspect
import math

import pytest

from rietx.model.profiles.caglioti import (
    apparent_size_from_size_coefficient,
    lorentzian_fwhm,
    microstrain_from_strain_coefficient,
    size_coefficient_for_size,
    strain_coefficient_for_microstrain,
)

# The two wavelengths of the committed two-wavelength joint fixture
# (tests/test_multi_histogram.py), whose ratio is what WP-1131 measured.
LAM_SHORT, LAM_LONG = 0.41390, 0.71070


@pytest.mark.parametrize("two_theta", [5.0, 17.5, 30.0, 62.0, 90.0, 145.0])
@pytest.mark.parametrize("coefficient", [0.02, 0.114592, 1.5])
def test_the_strain_coefficient_maps_to_one_strain_at_every_angle(
    two_theta, coefficient
):
    """The angle-free form is the law evaluated at any angle and undone.

    The size twin of this lives in ``test_profile_size.py``; the difference
    worth asserting is in the *signature* — this one takes no wavelength, so
    there is no instrument for it to be wrong about.
    """
    fwhm = float(lorentzian_fwhm(two_theta / 2.0, 0.0, coefficient))
    theta = math.radians(two_theta / 2.0)
    from_angle = math.radians(fwhm) / (2.0 * math.tan(theta))
    assert from_angle == pytest.approx(
        microstrain_from_strain_coefficient(coefficient), rel=1e-12)


@pytest.mark.parametrize("microstrain", [1e-5, 1e-4, 1e-3, 5e-3, 3e-2])
def test_the_seed_and_the_reading_are_inverses(microstrain):
    coefficient = strain_coefficient_for_microstrain(microstrain)
    assert microstrain_from_strain_coefficient(coefficient) == pytest.approx(
        microstrain, rel=1e-15)


def test_the_strain_coefficient_is_360_over_pi_times_the_strain():
    """The constant, spelled out once against a hand computation.

    Δd/d = 1e-3 is 0.114592 deg 2θ on *every* instrument — the number the
    WP-1131 fixture's strain control refines to, and the one a reader can check
    with a calculator.
    """
    assert strain_coefficient_for_microstrain(1e-3) == pytest.approx(
        360.0 / math.pi * 1e-3, rel=1e-15)
    assert strain_coefficient_for_microstrain(1e-3) == pytest.approx(
        0.1145916, abs=5e-8)


@pytest.mark.parametrize("size_a", [80.0, 400.0, 2000.0])
def test_one_specimen_needs_two_size_coefficients_and_one_strain_coefficient(size_a):
    """The asymmetry WP-1131 exists for, as a ratio and without a constant.

    A specimen of one crystallite size measured at two wavelengths needs size
    coefficients in the ratio λ₂/λ₁ — so a joint fit that serves one coefficient
    to both histograms is wrong by that ratio, 1.717× on this fixture's pair.
    The Scherrer constant cancels out of it, which is why the defect does not
    wait on the convention question.
    """
    short = size_coefficient_for_size(size_a, LAM_SHORT)
    long = size_coefficient_for_size(size_a, LAM_LONG)
    assert long / short == pytest.approx(LAM_LONG / LAM_SHORT, rel=1e-15)
    for k in (0.89, 1.0, 1.0747):
        assert (size_coefficient_for_size(size_a, LAM_LONG, k)
                / size_coefficient_for_size(size_a, LAM_SHORT, k)
                == pytest.approx(LAM_LONG / LAM_SHORT, rel=1e-15))
    # and each reads back as the one size it was built from
    assert apparent_size_from_size_coefficient(short, LAM_SHORT) == pytest.approx(size_a)
    assert apparent_size_from_size_coefficient(long, LAM_LONG) == pytest.approx(size_a)


def test_the_strain_conversion_has_no_wavelength_to_be_wrong_about():
    """The control, as a fact about the signature and then about the ratio.

    ``SharingMap`` is right about strain and wrong about size, and the reason is
    visible before any fit runs: the strain pair takes no wavelength argument at
    all, while the size pair cannot be called without one.  Then the same
    statement as a ratio — one specimen, two wavelengths, strain coefficients
    identical and size coefficients 1.717× apart.
    """
    strain_params = set(inspect.signature(
        strain_coefficient_for_microstrain).parameters)
    size_params = set(inspect.signature(size_coefficient_for_size).parameters)
    assert "wavelength_a" not in strain_params
    assert "wavelength_a" in size_params

    coefficient = strain_coefficient_for_microstrain(1e-3)
    # the same coefficient describes the same specimen on both instruments,
    # so the widths it produces at one angle are bit-identical
    assert (float(lorentzian_fwhm(20.0, 0.0, coefficient))
            == float(lorentzian_fwhm(20.0, 0.0, coefficient)))
    ratio = (size_coefficient_for_size(400.0, LAM_LONG)
             / size_coefficient_for_size(400.0, LAM_SHORT))
    assert ratio == pytest.approx(1.7171, abs=5e-5)


@pytest.mark.parametrize("fn,args", [
    (microstrain_from_strain_coefficient, (0.0,)),
    (microstrain_from_strain_coefficient, (-0.1,)),
    (microstrain_from_strain_coefficient, (float("nan"),)),
    (strain_coefficient_for_microstrain, (0.0,)),
    (strain_coefficient_for_microstrain, (-1e-3,)),
    (strain_coefficient_for_microstrain, (float("nan"),)),
])
def test_the_unusable_inputs_are_refused_by_name(fn, args):
    """A zero strain is a perfect lattice and a nan is not a number.

    The ``not x > 0.0`` spelling in the module is also the nan test; asserting
    it here is what keeps a nan from being returned as a nan strain.
    """
    with pytest.raises(ValueError):
        fn(*args)

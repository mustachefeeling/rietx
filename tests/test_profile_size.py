"""Reading a profile width as a crystallite size, and why degrees cannot do it.

The claim under test is the module docstring's (3)/(4) in
``model/profiles/caglioti.py``: Scherrer broadening is constant in Q, so a
width judged as a size is transferable between instruments where a width judged
in degrees is not, and because the size law *is* 1/cosθ the conversion from a
size **coefficient** needs no reference angle.

That last part is the load-bearing one — it is what lets a diagnostic quote one
number for a whole pattern — so it is asserted as an identity across the
angular range rather than trusted on paper.
"""

from __future__ import annotations

import math

import pytest

from rietx.model.profiles.caglioti import (
    SCHERRER_K,
    apparent_size,
    apparent_size_from_size_coefficient,
    delta_q_fwhm,
    lorentzian_fwhm,
    size_coefficient_for_size,
)

# λ spanning the instruments this package is used on: a Cu lab tube, a Mo tube,
# and APS 11-BM (tests/data/11BM_NAC.fxye's .prm value).
CU, MO, SYNCHROTRON = 1.5406, 0.7107, 0.4139090


@pytest.mark.parametrize("two_theta", [5.0, 17.5, 30.0, 62.0, 90.0, 145.0])
@pytest.mark.parametrize("wavelength", [CU, MO, SYNCHROTRON])
@pytest.mark.parametrize("coefficient", [0.02, 0.15, 1.0])
def test_the_size_coefficient_maps_to_one_size_at_every_angle(
    two_theta, wavelength, coefficient
):
    """(4) is (3) with the cosθ cancelled — so the angle must not matter.

    Evaluating the 1/cosθ law at ``two_theta`` and putting *that* FWHM through
    the general Scherrer must return what the angle-free form returns from the
    coefficient alone.  Both sides are float arithmetic over the same
    quantities, so the bar is tight; the residual is the ``cos`` round-tripping
    through radians and back.
    """
    fwhm = float(lorentzian_fwhm(two_theta / 2.0, coefficient, 0.0))
    from_angle = apparent_size(fwhm, two_theta, wavelength)
    angle_free = apparent_size_from_size_coefficient(coefficient, wavelength)
    assert from_angle == pytest.approx(angle_free, rel=1e-12)


@pytest.mark.parametrize("wavelength", [CU, MO, SYNCHROTRON])
@pytest.mark.parametrize("two_theta", [12.0, 40.0, 110.0])
def test_delta_q_is_scherrer_in_q_whatever_the_instrument(wavelength, two_theta):
    """ΔQ = 2π·K/L, the form that carries no λ and no θ.

    This is the sense in which the judgement is instrument-independent: the same
    size gives the same Q width on every instrument in the table, even though
    the *degrees* differ by a factor of nearly four (the test below).
    """
    size_a = 120.0
    coefficient = size_coefficient_for_size(size_a, wavelength)
    fwhm = float(lorentzian_fwhm(two_theta / 2.0, coefficient, 0.0))
    assert delta_q_fwhm(fwhm, two_theta, wavelength) == pytest.approx(
        2.0 * math.pi * SCHERRER_K / size_a, rel=1e-12
    )


def test_one_number_of_degrees_is_three_different_crystallites():
    """The motivation, pinned: why issue #102's bound cannot be stated in deg².

    ``profile.w`` and ``profile.u`` carry ``max = 1.0`` deg², i.e. ~1.0 deg
    FWHM.  Read as a size at 2θ = 30, that one bound is an ordinary
    nanocrystalline lab specimen on Cu and a crystallite of ~4 unit cells on
    11-BM — so a single deg² cap either refuses legitimate lab data or admits
    synchrotron nonsense, and cannot do both.  Values are this expression's,
    quoted to 2 dp; the ratio is the point, not the digits.
    """
    sizes = {name: apparent_size(1.0, 30.0, lam) / 10.0  # Å -> nm
             for name, lam in (("cu", CU), ("mo", MO), ("synchrotron", SYNCHROTRON))}
    assert sizes["cu"] == pytest.approx(8.22, abs=0.01)
    assert sizes["mo"] == pytest.approx(3.79, abs=0.01)
    assert sizes["synchrotron"] == pytest.approx(2.21, abs=0.01)
    # The spread *is* the argument: same degrees, 3.7x the physics.
    assert sizes["cu"] / sizes["synchrotron"] == pytest.approx(CU / SYNCHROTRON,
                                                              rel=1e-12)


@pytest.mark.parametrize("wavelength", [CU, MO, SYNCHROTRON])
@pytest.mark.parametrize("size_a", [15.0, 80.0, 500.0, 5000.0])
def test_the_seed_and_the_reading_are_inverses(wavelength, size_a):
    """A width seeded from a known size must read back as that size."""
    coefficient = size_coefficient_for_size(size_a, wavelength)
    assert apparent_size_from_size_coefficient(coefficient, wavelength) == (
        pytest.approx(size_a, rel=1e-12)
    )


def test_k_is_an_argument_and_scales_the_answer_linearly():
    """Shape enters only through K, so a caller who knows it can say so."""
    a = apparent_size_from_size_coefficient(0.2, CU, k=0.89)
    b = apparent_size_from_size_coefficient(0.2, CU, k=1.0747)
    assert b / a == pytest.approx(1.0747 / 0.89, rel=1e-12)


@pytest.mark.parametrize(
    ("fn", "args"),
    [
        (apparent_size, (0.0, 30.0, CU)),          # zero width -> infinite size
        (apparent_size, (-0.1, 30.0, CU)),
        (apparent_size, (0.5, 0.0, CU)),           # 2theta outside (0, 180)
        (apparent_size, (0.5, 180.0, CU)),
        (apparent_size, (0.5, 30.0, 0.0)),
        (apparent_size_from_size_coefficient, (0.0, CU)),
        (apparent_size_from_size_coefficient, (0.2, -1.0)),
        (size_coefficient_for_size, (0.0, CU)),
        (size_coefficient_for_size, (100.0, 0.0)),
    ],
)
def test_the_unusable_inputs_are_refused_by_name(fn, args):
    """A zero width is an infinite size: true, and no use to a caller.

    Refused rather than returned as ``inf``, so the caller finds out here
    instead of downstream — the package's "refuse, do not normalise" shape.
    """
    with pytest.raises(ValueError):
        fn(*args)

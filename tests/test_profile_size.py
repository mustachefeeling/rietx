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
    gaussian_fwhm,
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
    """The motivation, pinned: a width in degrees is not a transferable number.

    ``profile.w`` carries ``max = 1.0`` deg², and being the *constant* term of
    the Gaussian variance that is 1.0 deg FWHM at every angle — so reading it as
    a size needs no more than the wavelength.  Read at 2θ = 30 that one bound is
    an ordinary nanocrystalline lab specimen on Cu and a crystallite of ~4 unit
    cells on 11-BM, so a single deg² cap either refuses legitimate lab data or
    admits synchrotron nonsense and cannot do both.  Values are this
    expression's, quoted to 2 dp; the ratio is the point, not the digits.

    ``profile.u`` is **not** in this statement, whatever its own cap: it is the
    tan²θ term, so 1.0 deg² there is 1.0 deg only at 2θ = 90 (the test below
    pins the whole row).  Only ``w`` is one number of degrees at every angle,
    and only the 1/cosθ coefficients are a *size* — see
    ``test_the_instrument_size_bound_is_two_different_crystallites``.
    """
    sizes = {name: apparent_size(1.0, 30.0, lam) / 10.0  # Å -> nm
             for name, lam in (("cu", CU), ("mo", MO), ("synchrotron", SYNCHROTRON))}
    assert sizes["cu"] == pytest.approx(8.22, abs=0.01)
    assert sizes["mo"] == pytest.approx(3.79, abs=0.01)
    assert sizes["synchrotron"] == pytest.approx(2.21, abs=0.01)
    # The cosθ, which is what the λ ratio above cannot see: L = Kλ/(β cosθ), so
    # the *same* 1.0 deg read at 145 instead of 30 is a 3.2x larger crystallite.
    # An assertion on the λ ratio alone passes whatever this does with the
    # angle — it is dimensional bookkeeping, not a measurement of the law.
    assert (apparent_size(1.0, 145.0, CU) / apparent_size(1.0, 30.0, CU)
            == pytest.approx(math.cos(math.radians(15.0))
                             / math.cos(math.radians(72.5)), rel=1e-12))


@pytest.mark.parametrize(
    ("two_theta", "gamma_g"),
    [(30.0, 0.268), (60.0, 0.577), (90.0, 1.000), (145.0, 3.172)],
)
def test_the_u_term_is_one_degree_only_at_two_theta_90(two_theta, gamma_g):
    """``u`` = 1.0 deg² is 1.0 deg FWHM at exactly one angle, and it is 2θ = 90.

    Γ_G² = u·tan²θ + v·tanθ + w, so ``u`` alone gives Γ_G = tanθ: 0.268 deg at
    2θ = 30 and 3.172 deg at 2θ = 145, a factor of twelve across an ordinary
    pattern.  Pinned because the sentence "``u`` and ``w`` are ~1.0 deg FWHM"
    read as though it covered both, and it is true of ``w`` only — a bound
    stated on ``u`` is a bound whose width depends on where you read it, which
    is the reference-angle problem one level below the one this module removes.
    """
    assert float(gaussian_fwhm(two_theta / 2.0, 1.0, 0.0, 0.0)) == pytest.approx(
        gamma_g, abs=5e-4
    )


def test_the_instrument_size_bound_is_two_different_crystallites():
    """The same argument on the parameter that actually *is* a size term.

    ``instrument.profile.x`` is the Lorentzian 1/cosθ coefficient and carries
    ``max = 1.0`` deg, which the angle-free (4) reads with no reference angle at
    all: 79.4 Å on Cu Kα against 21.3 Å on 11-BM.  One declared cap, a 3.7×
    spread in the physics it admits — and 21 Å is about four unit cells, i.e.
    outside Scherrer's own domain rather than merely small.

    The sample side is the stronger case and has no number to pin: ``lor_size``
    and ``gauss_size`` carry ``min = 0.0`` and no ``max``, so there is no bound
    there to read as a size.
    """
    assert apparent_size_from_size_coefficient(1.0, CU) == pytest.approx(79.44, abs=0.01)
    assert apparent_size_from_size_coefficient(1.0, SYNCHROTRON) == pytest.approx(
        21.34, abs=0.01
    )
    # the Gaussian variance coefficient enters through its square root, so a
    # ``gauss_size`` of 0.25 deg² is a 0.5 deg coefficient and twice the size
    assert apparent_size_from_size_coefficient(
        math.sqrt(0.25), CU) == pytest.approx(2.0 * 79.44, abs=0.02)


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

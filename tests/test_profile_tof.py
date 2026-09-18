"""The time-of-flight peak profiles — every claim against an outside reference.

``model/profiles/tof.py`` is a closed form for a convolution, so the test that
matters is the convolution itself: each shape is compared point by point with
a brute-force quadrature of the *definition* (the back-to-back exponential
against a Gaussian, then against a Thompson-Cox-Hastings pseudo-Voigt built
from the sibling module), over triples spanning the ranges real TOF
diffractometers work in.  Nothing here compares one spelling of the closed
form with another.

The rest is the same discipline one level down: e^z·E₁(z) against
``scipy.special``, the analytic partials against finite differences, the
limits (σ → 0, α,β → ∞) against the shapes they must become, unit area and
the first moment against their derived values, and the sign convention
against the side the tail has to be on.  Two guards are *negative* controls
and are expected to disagree with the brute force: swapping α and β, and the
p-sign the GSAS manual publishes for profile type 3.
"""

from __future__ import annotations

import numpy as np
import pytest
from scipy.integrate import quad

from rietx.model.profiles.pseudovoigt import pseudo_voigt, tch_gamma_eta
from rietx.model.profiles.tof import (
    SERIES_LOSS_EXPONENT,
    back_to_back_exponential,
    back_to_back_gaussian,
    back_to_back_gaussian_derivs,
    back_to_back_pseudovoigt,
    back_to_back_pseudovoigt_derivs,
    d_from_tof,
    scaled_exp1,
    tof_alpha,
    tof_beta,
    tof_from_d,
    tof_gamma,
    tof_pseudovoigt_widths,
    tof_sigma_sq,
)
from rietx.model.profiles.voigt import GAUSS_FWHM_TO_SIGMA

#: the ranges the arm-A sweep draws from, in this module's units (µs, µs⁻¹):
#: α and β bracket the moderator rise/decay rates of a real spallation source,
#: σ the resolution of a backscattering bank (~5 µs) through a 45° one on a
#: long flight path (~300 µs).
ALPHA_RANGE = (0.05, 1.0)
BETA_RANGE = (0.01, 0.1)
SIGMA_RANGE = (5.0, 300.0)
#: worst deviation allowed between the closed form and the brute-force
#: convolution, on every sampled point of every triple.  It is a bar on the
#: *mathematics*, not on the quadrature: the measured worst case is ~1e-12
#: (printed by the tests below), and the residue is `quad`'s.
CONVOLUTION_RTOL = 1e-9
#: relative to the point's own value, or to this fraction of the peak,
#: whichever is larger.  The far tails of a 300 µs / 0.01 µs⁻¹ triple are
#: 1e-100 of the peak and below, where "relative" is a statement about
#: `quad`'s last bits rather than about the closed form.
PEAK_FLOOR = 1e-12


def _triples(n: int = 24) -> list[tuple[float, float, float]]:
    """``n`` (α, β, σ) triples, log-spread over the ranges above."""
    rng = np.random.default_rng(20260905)
    out = []
    for _ in range(n):
        out.append(tuple(
            float(10 ** rng.uniform(np.log10(lo), np.log10(hi)))
            for lo, hi in (ALPHA_RANGE, BETA_RANGE, SIGMA_RANGE)
        ))
    return out


def _sample_offsets(alpha: float, beta: float, sigma: float) -> np.ndarray:
    """ΔT points spanning the peak: several σ each way plus both tails."""
    reach = max(4.0 * sigma, 4.0 / alpha, 4.0 / beta)
    return np.array([-2.0, -1.0, -0.45, -0.15, 0.0, 0.15, 0.45, 1.0, 2.0]) * reach


def _convolve(x: float, alpha: float, beta: float, kernel) -> float:
    """∫E(τ)·kernel(x − τ) dτ by quadrature — the definition, brute-forced.

    The exponential pair is truncated at 60 e-foldings each way, which is an
    exponentially small tail whatever the kernel does, and the integrand is
    split at its two kinks (τ = 0, where the pair meets, and τ = x, where a
    Lorentzian kernel peaks) so `quad` never has to find them.
    """
    def integrand(t):
        return back_to_back_exponential(t, alpha, beta) * kernel(x - t)

    lo, hi = -60.0 / alpha, 60.0 / beta
    edges = sorted({lo, hi} | {p for p in (0.0, x) if lo < p < hi})
    return float(sum(
        quad(integrand, a, b, limit=800, epsabs=1e-18, epsrel=1e-12)[0]
        for a, b in zip(edges[:-1], edges[1:])
    ))


def _gaussian_kernel(sigma: float):
    return lambda s: np.exp(-0.5 * (s / sigma) ** 2) / (sigma * np.sqrt(2.0 * np.pi))


def _pseudovoigt_kernel(sigma: float, gamma: float):
    """The TCH pseudo-Voigt of the sibling module, at the combined width.

    Built from ``pseudovoigt.tch_gamma_eta`` and ``pseudo_voigt`` directly, so
    the reference convolution shares nothing with ``tof.py`` but the two
    numbers TCH defines.
    """
    fwhm, eta = tch_gamma_eta(GAUSS_FWHM_TO_SIGMA * sigma, gamma)
    return lambda s: pseudo_voigt(s, fwhm, eta)


def _worst_relative(closed, brute) -> float:
    """Worst deviation, relative to the point or to ``PEAK_FLOOR``·peak."""
    closed, brute = np.asarray(closed), np.asarray(brute)
    scale = np.maximum(np.abs(brute), PEAK_FLOOR * np.max(np.abs(brute)))
    return float(np.max(np.abs(closed - brute) / scale))


# ----------------------------------------------------------------------
# arm A — the closed forms against a brute-force convolution
# ----------------------------------------------------------------------
def test_type1_matches_a_brute_force_gaussian_convolution(capsys):
    """GSAS TOF profile type 1 *is* the Gaussian convolution of the pair.

    24 (α, β, σ) triples over the declared ranges, nine ΔT each spanning the
    peak and both tails; the closed erfc form of Von Dreele, Jorgensen &
    Windsor (1982) must reproduce the quadrature on every point.
    """
    worst, worst_at = 0.0, None
    for alpha, beta, sigma in _triples():
        dt = _sample_offsets(alpha, beta, sigma)
        closed = back_to_back_gaussian(dt, alpha, beta, sigma)
        brute = [_convolve(x, alpha, beta, _gaussian_kernel(sigma)) for x in dt]
        rel = _worst_relative(closed, brute)
        if rel > worst:
            worst, worst_at = rel, (alpha, beta, sigma)
    with capsys.disabled():
        print(f"\n  type 1 vs quadrature: worst rel = {worst:.2e} at {worst_at}")
    assert worst < CONVOLUTION_RTOL


def test_type3_matches_a_brute_force_pseudovoigt_convolution(capsys):
    """The same for type 3, against a convolution with the TCH pseudo-Voigt.

    This is the assertion that decides the sign of p in the Lorentzian half —
    see ``test_the_gsas_published_p_sign_fails_this_same_comparison``, which
    is the negative control for it.
    """
    worst, worst_at = 0.0, None
    for alpha, beta, sigma in _triples():
        gamma = 0.7 * GAUSS_FWHM_TO_SIGMA * sigma      # a genuinely mixed shape
        dt = _sample_offsets(alpha, beta, sigma)
        closed = back_to_back_pseudovoigt(dt, alpha, beta, sigma, gamma)
        brute = [_convolve(x, alpha, beta, _pseudovoigt_kernel(sigma, gamma)) for x in dt]
        rel = _worst_relative(closed, brute)
        if rel > worst:
            worst, worst_at = rel, (alpha, beta, sigma, gamma)
    with capsys.disabled():
        print(f"  type 3 vs quadrature: worst rel = {worst:.2e} at {worst_at}")
    assert worst < CONVOLUTION_RTOL


# ----------------------------------------------------------------------
# the negative controls
# ----------------------------------------------------------------------
def test_swapping_alpha_and_beta_fails_the_same_comparison(capsys):
    """The control for arm A: α ↔ β mirrors the peak, so it must disagree.

    A comparison that cannot fail confirms whatever it was pointed at.  This
    runs the arm-A comparison once with the two rates exchanged in the closed
    form only, and records how badly it misses — if this ever passes, arm A is
    measuring something that does not depend on the asymmetry at all.
    """
    alpha, beta, sigma = 0.35, 0.03, 40.0
    dt = _sample_offsets(alpha, beta, sigma)
    swapped = back_to_back_gaussian(dt, beta, alpha, sigma)
    brute = [_convolve(x, alpha, beta, _gaussian_kernel(sigma)) for x in dt]
    rel = _worst_relative(swapped, brute)
    with capsys.disabled():
        print(f"  control (α↔β): worst rel = {rel:.3g}  (bar is {CONVOLUTION_RTOL:g})")
    assert rel > 1.0                       # off by more than the value itself


def test_the_gsas_published_p_sign_fails_this_same_comparison(capsys):
    """The GSAS type-3 Lorentzian argument, as published, is not this integral.

    Larson & Von Dreele (2004) define p for profile type 3 by reference to
    profile type 2, i.e. p = −α·ΔT + iαΓ/2, and ``epsvoigt.for`` implements
    that (``RXA = -ALP*DT``).  With that sign the two wings differ only in
    their rate, so the term is invariant under α ↔ β — which the convolution
    of an *asymmetric* pulse cannot be.  This pins the size of the
    disagreement so the claim in ``tof.py``'s header is executable rather than
    an assertion, and so that a future reader can see what adopting
    GSAS-refined type-3 γ coefficients would cost.
    """
    alpha, beta, sigma = 0.35, 0.045, 12.0
    gamma = 2.0 * GAUSS_FWHM_TO_SIGMA * sigma
    fwhm, eta, _ = tof_pseudovoigt_widths(sigma, gamma)
    dt = np.array([-6.0, -2.0, -0.6, 0.0, 0.6, 2.0, 6.0]) * fwhm
    n = 0.5 * alpha * beta / (alpha + beta)

    published = -(2.0 * n / np.pi) * (
        np.imag(scaled_exp1(alpha * (-dt + 0.5j * fwhm)))
        + np.imag(scaled_exp1(beta * (-dt + 0.5j * fwhm)))
    )
    gaussian = back_to_back_gaussian(dt, alpha, beta, fwhm / GAUSS_FWHM_TO_SIGMA)
    as_published = eta * published + (1.0 - eta) * gaussian
    brute = [_convolve(x, alpha, beta, _pseudovoigt_kernel(sigma, gamma)) for x in dt]
    ours = back_to_back_pseudovoigt(dt, alpha, beta, sigma, gamma)

    peak = float(np.max(np.abs(brute)))
    published_err = float(np.max(np.abs(as_published - brute))) / peak
    our_err = float(np.max(np.abs(ours - brute))) / peak
    with capsys.disabled():
        print(f"  GSAS p = −αΔT: worst error = {published_err:.2%} of the peak; "
              f"p = +αΔT: {our_err:.2e}")
    assert published_err > 5e-3            # percent-level, not round-off
    assert our_err < 1e-12
    # and the published form's signature: symmetric in the two rates
    swapped = -(2.0 * n / np.pi) * (
        np.imag(scaled_exp1(beta * (-dt + 0.5j * fwhm)))
        + np.imag(scaled_exp1(alpha * (-dt + 0.5j * fwhm)))
    )
    assert np.allclose(published, swapped, rtol=0, atol=0)


# ----------------------------------------------------------------------
# arm B — the limits, the area and the moment
# ----------------------------------------------------------------------
def test_sigma_zero_recovers_the_bare_double_exponential():
    """σ → 0 is the unconvoluted pulse, reached continuously and at zero."""
    dt = np.linspace(-500.0, 900.0, 1401)
    bare = back_to_back_exponential(dt, 0.3, 0.05)
    assert np.array_equal(back_to_back_gaussian(dt, 0.3, 0.05, 0.0), bare)
    for sigma in (1e-1, 1e-2, 1e-3):
        smeared = back_to_back_gaussian(dt, 0.3, 0.05, sigma)
        # away from the kink at ΔT = 0 the two agree to O(σ²)
        off = np.abs(dt) > 50.0 * sigma
        assert np.max(np.abs(smeared[off] / bare[off] - 1.0)) < 1e-3


def test_large_rates_recover_the_gaussian_and_the_pseudovoigt():
    """α, β → ∞ leaves the resolution function alone.

    The pulse becomes a δ at the peak, so type 1 must become the unit Gaussian
    of standard deviation σ and type 3 the TCH pseudo-Voigt of the combined
    width — the two shapes ``profiles/pseudovoigt.py`` already owns.
    """
    sigma, gamma = 25.0, 60.0
    dt = np.linspace(-300.0, 300.0, 601)
    gauss = np.exp(-0.5 * (dt / sigma) ** 2) / (sigma * np.sqrt(2.0 * np.pi))
    fwhm, eta = tch_gamma_eta(GAUSS_FWHM_TO_SIGMA * sigma, gamma)
    for rate in (1e3, 1e5):
        assert np.max(np.abs(
            back_to_back_gaussian(dt, rate, rate, sigma) / gauss - 1.0
        )) < 50.0 / rate
        assert np.max(np.abs(
            back_to_back_pseudovoigt(dt, rate, rate, sigma, gamma)
            / pseudo_voigt(dt, fwhm, eta) - 1.0
        )) < 50.0 / rate


def test_both_shapes_carry_unit_area():
    """∫Ω dΔT = 1 to 1e-6, so intensity enters only through the prefactor.

    The window has to be very wide for type 3, and the tail grid *logarithmic*.
    A Lorentzian of FWHM Γ leaves ≈ Γ/(πW) of its area outside ±W, so a linear
    ±4e7 µs window — already 5 000 times the peak width — still misses 2.5e-6
    of the area at the second triple below and fails this bar; the same reason
    ``test_voigt.py`` integrates onto 2e5 for a much narrower peak.  Geometric
    spacing in the tails costs nothing (the integrand there is a smooth 1/ΔT²)
    and buys three more decades of window.
    """
    core = np.linspace(-8000.0, 8000.0, 800_001)
    tail = np.geomspace(8000.0, 1e11, 400_001)
    grid = np.unique(np.concatenate([-tail[::-1], core, tail]))
    for alpha, beta, sigma in ((0.3, 0.05, 30.0), (0.08, 0.02, 120.0)):
        area = np.trapezoid(back_to_back_gaussian(grid, alpha, beta, sigma), grid)
        assert abs(area - 1.0) < 1e-6
        gamma = GAUSS_FWHM_TO_SIGMA * sigma
        area3 = np.trapezoid(
            back_to_back_pseudovoigt(grid, alpha, beta, sigma, gamma), grid
        )
        assert abs(area3 - 1.0) < 1e-6


def test_the_first_moment_is_the_pulse_asymmetry():
    """⟨ΔT⟩ = 1/β − 1/α, and a symmetric kernel does not move it.

    For the bare pair, ∫τE(τ)dτ = C(1/β² − 1/α²) with C = αβ/(α+β), which is
    (α − β)/(αβ) = 1/β − 1/α.  With ΔT = channel − peak and β < α the shift is
    **positive** — the centroid sits at longer flight time than the nominal
    position, which is the same statement as the tail being on the long-TOF
    side.  Convolution adds the kernel's own mean, and a Gaussian's is zero.

    Only type 1 is checked: a pseudo-Voigt has a Lorentzian half and therefore
    no finite first moment at all, so the same claim about type 3 would be a
    statement about where the integration window was cut.
    """
    core = np.linspace(-12000.0, 12000.0, 1_200_001)
    tail = np.geomspace(12000.0, 1e8, 200_001)
    grid = np.unique(np.concatenate([-tail[::-1], core, tail]))
    for alpha, beta, sigma in ((0.3, 0.05, 30.0), (0.5, 0.02, 8.0)):
        shape = back_to_back_gaussian(grid, alpha, beta, sigma)
        moment = np.trapezoid(grid * shape, grid) / np.trapezoid(shape, grid)
        expected = 1.0 / beta - 1.0 / alpha
        assert abs(moment - expected) < 1e-6 * expected


def test_the_tail_is_on_the_long_tof_side_when_beta_is_the_smaller_rate():
    """The sign convention, asserted rather than described.

    β < α means the decay is slower than the rise, and with ΔT = channel −
    peak that decay must be at ΔT > 0.  Checked by mass on either side of the
    peak, which no symmetry of the formula can fake.
    """
    grid = np.linspace(-4000.0, 4000.0, 800_001)
    shape = back_to_back_gaussian(grid, 0.4, 0.02, 20.0)
    long_side = np.trapezoid(shape[grid > 0.0], grid[grid > 0.0])
    short_side = np.trapezoid(shape[grid < 0.0], grid[grid < 0.0])
    assert long_side > 4.0 * short_side
    # and the mirror image of the statement
    mirrored = back_to_back_gaussian(-grid, 0.02, 0.4, 20.0)
    assert np.allclose(shape, mirrored, rtol=1e-12, atol=0.0)


def test_gamma_zero_reduces_type3_to_type1_bit_for_bit():
    """Not "to within round-off": the fifth root is short-circuited so that a
    Lorentzian-free type-3 refinement is the same arithmetic as type 1."""
    dt = np.linspace(-800.0, 1600.0, 2401)
    for alpha, beta, sigma in ((0.3, 0.05, 30.0), (0.9, 0.011, 6.0)):
        assert np.array_equal(
            back_to_back_pseudovoigt(dt, alpha, beta, sigma, 0.0),
            back_to_back_gaussian(dt, alpha, beta, sigma),
        )


# ----------------------------------------------------------------------
# e^z E₁(z)
# ----------------------------------------------------------------------
def test_scaled_exp1_matches_scipy_where_scipy_can_be_asked(capsys):
    """The two-branch e^z·E₁(z) against ``scipy.special.exp1``.

    Scanned at 60 angles over |z| ∈ [1e-3, 300], the part of the upper
    half-plane where the *unscaled* E₁ is still a representable double: past
    |Re z| ≈ 700 one of e^z and E₁(z) is an overflow and the other an
    underflow, so scipy cannot be the reference there and
    ``test_scaled_exp1_matches_its_asymptotic_series_far_out`` takes over.

    The bar is 1e-12 rather than the ~1e-14 this module reaches, because the
    residual around |z| ≈ 4.5 is **scipy's**: adjudicated against mpmath at 40
    digits, at z = 4.173 + 1.634i the module is 1.6e-15 from the true value and
    ``scipy.special.exp1`` is 3.3e-13 (scipy 1.18.1).  Loosening a bar because
    the reference is the looser side is only honest with that measurement
    written down, so it is.
    """
    exp1 = pytest.importorskip("scipy.special").exp1
    radii = 10.0 ** np.linspace(-3.0, np.log10(300.0), 40)
    angles = np.linspace(5e-4, np.pi - 5e-4, 60)
    z = (radii[:, None] * np.exp(1j * angles)[None, :]).ravel()
    reference = np.exp(z) * exp1(z)
    assert np.all(np.isfinite(reference)) and np.all(reference != 0.0)
    rel = np.abs(scaled_exp1(z) - reference) / np.abs(reference)
    with capsys.disabled():
        print(f"  e^z·E₁(z) vs scipy: worst rel = {rel.max():.2e}")
    assert rel.max() < 1e-12


def test_scaled_exp1_matches_its_asymptotic_series_far_out(capsys):
    """|z| ≥ 1e3: against Σ(−1)^k k!/z^{k+1} (Abramowitz & Stegun 5.1.51).

    A divergent series, but its truncation error is bounded by the first term
    dropped, and at |z| = 1000 twenty terms are ~1e-40 — an independent
    reference of far higher accuracy than the thing being checked, and one
    that does not go through a floating-point exponential at all.
    """
    radii = 10.0 ** np.linspace(3.0, 4.0, 12)
    angles = np.linspace(5e-4, np.pi - 5e-4, 60)
    z = (radii[:, None] * np.exp(1j * angles)[None, :]).ravel()
    reference = np.zeros_like(z)
    term = 1.0 / z
    for k in range(20):
        reference = reference + term
        term = term * (-(k + 1.0)) / z
    rel = np.abs(scaled_exp1(z) - reference) / np.abs(reference)
    with capsys.disabled():
        print(f"  e^z·E₁(z) vs the asymptotic series: worst rel = {rel.max():.2e}")
    assert rel.max() < 1e-13


def test_scaled_exp1_uses_both_branches_and_is_continuous_across_the_seam():
    """The seam is a real switch, and it does not show.

    Both branches must actually be exercised by the scan above (a criterion
    that silently sends everything one way would test one algorithm twice),
    and the two must agree where they meet — the criterion is a *cancellation*
    bound, not a convergence one, so the crossing carries no jump.
    """
    radii = 10.0 ** np.linspace(-3.0, 4.0, 43)
    angles = np.linspace(5e-4, np.pi - 5e-4, 60)
    z = (radii[:, None] * np.exp(1j * angles)[None, :]).ravel()
    series_side = (np.abs(z) + z.real) <= SERIES_LOSS_EXPONENT
    assert 0.05 < series_side.mean() < 0.95, "the branch criterion is degenerate"
    # walk across the seam along a ray and check the step is at round-off
    ray = np.exp(1j * 2.0) * np.linspace(3.0, 5.0, 4001)
    values = scaled_exp1(ray)
    step = np.max(np.abs(np.diff(values)))
    smooth = np.max(np.abs(np.diff(values[:2000])))
    assert step < 10.0 * smooth


# ----------------------------------------------------------------------
# derivatives
# ----------------------------------------------------------------------
def _central(f, value, h):
    return (f(value + h) - f(value - h)) / (2.0 * h)


def test_type1_partials_match_finite_differences():
    """(∂/∂ΔT, ∂/∂α, ∂/∂β, ∂/∂σ) of type 1, against central differences."""
    dt = np.array([-160.0, -40.0, -5.0, 0.0, 5.0, 40.0, 160.0, 600.0])
    alpha, beta, sigma = 0.3, 0.05, 30.0
    omega, d_dt, d_a, d_b, d_s = back_to_back_gaussian_derivs(dt, alpha, beta, sigma)
    assert np.allclose(omega, back_to_back_gaussian(dt, alpha, beta, sigma), rtol=0, atol=0)
    checks = (
        (d_dt, lambda v: back_to_back_gaussian(dt + v, alpha, beta, sigma), 0.0, 1e-3),
        (d_a, lambda v: back_to_back_gaussian(dt, v, beta, sigma), alpha, 1e-6),
        (d_b, lambda v: back_to_back_gaussian(dt, alpha, v, sigma), beta, 1e-7),
        (d_s, lambda v: back_to_back_gaussian(dt, alpha, beta, v), sigma, 1e-4),
    )
    for analytic, f, at, h in checks:
        numeric = _central(f, at, h)
        assert np.allclose(analytic, numeric, rtol=2e-6, atol=1e-14 * np.max(omega))


def test_type3_partials_match_finite_differences():
    """(∂/∂ΔT, ∂/∂α, ∂/∂β, ∂/∂σ, ∂/∂γ) of type 3 — the chain through TCH too.

    σ and γ both move the combined width Γ and γ also moves the mixing η, so
    these two partials are the ones a hand-derived Jacobian gets wrong; they
    are checked at a genuinely mixed shape (η ≈ 0.5), not at a limit.
    """
    dt = np.array([-160.0, -40.0, -5.0, 0.0, 5.0, 40.0, 160.0, 600.0])
    alpha, beta, sigma, gamma = 0.3, 0.05, 30.0, 70.0
    _, eta, _ = tof_pseudovoigt_widths(sigma, gamma)
    assert 0.3 < float(eta) < 0.7
    omega, d_dt, d_a, d_b, d_s, d_g = back_to_back_pseudovoigt_derivs(
        dt, alpha, beta, sigma, gamma
    )
    assert np.allclose(
        omega, back_to_back_pseudovoigt(dt, alpha, beta, sigma, gamma), rtol=0, atol=0
    )
    checks = (
        (d_dt, lambda v: back_to_back_pseudovoigt(dt + v, alpha, beta, sigma, gamma), 0.0, 1e-3),
        (d_a, lambda v: back_to_back_pseudovoigt(dt, v, beta, sigma, gamma), alpha, 1e-6),
        (d_b, lambda v: back_to_back_pseudovoigt(dt, alpha, v, sigma, gamma), beta, 1e-7),
        (d_s, lambda v: back_to_back_pseudovoigt(dt, alpha, beta, v, gamma), sigma, 1e-4),
        (d_g, lambda v: back_to_back_pseudovoigt(dt, alpha, beta, sigma, v), gamma, 1e-4),
    )
    for analytic, f, at, h in checks:
        numeric = _central(f, at, h)
        assert np.allclose(analytic, numeric, rtol=2e-6, atol=1e-14 * np.max(omega))


# ----------------------------------------------------------------------
# the TOF ↔ d map and the width laws
# ----------------------------------------------------------------------
def test_tof_and_d_round_trip_with_and_without_difa():
    d = np.array([0.5, 1.0, 1.6374, 1.9202, 3.1355, 8.0])
    for difc, difa, tzero in ((7000.0, 0.0, 0.0), (6911.21, -2.79, -19.42),
                              (16292.82, 4.28, 0.29)):
        back = d_from_tof(tof_from_d(d, difc, difa, tzero), difc, difa, tzero)
        assert np.allclose(back, d, rtol=1e-13, atol=0.0)


def test_d_from_tof_refuses_a_non_monotonic_map():
    """A DIFA large enough to turn T(d) inside the range has no inverse.

    dT/dd = DIFC + 2·DIFA·d turns at d = −DIFC/(2·DIFA); a negative DIFA of
    the size below puts that turning point at 2.5 Å, in the middle of a normal
    d range, and the quadratic then has two positive roots.  Refusing is the
    only honest answer: choosing one silently would place reflections at
    d-spacings the diffractometer never measured.
    """
    d = np.linspace(1.0, 4.0, 31)
    difc, difa = 5000.0, -1000.0
    with pytest.raises(ValueError, match="not monotonic"):
        d_from_tof(tof_from_d(d, difc, difa), difc, difa)
    with pytest.raises(ValueError, match="no real root"):
        d_from_tof(np.array([1e7]), difc, difa)
    with pytest.raises(ValueError, match="DIFC must be positive"):
        d_from_tof(np.array([1e4]), 0.0)


def test_the_width_laws_are_the_gsas_ones():
    """Each law against its own algebra, and σ's coefficients against the trap.

    ``sig-0/1/2`` are variances and enter unsquared — the manual writes them
    σ₀², σ₁², σ₂² because that is what each *is*.  Squaring what an instrument
    file supplies is the mistake this row exists to catch, so the assertion is
    written as the difference the two readings produce.
    """
    d = np.array([0.8, 1.6374, 3.1355])
    assert np.allclose(tof_alpha(d, 0.2, 1.5), 0.2 + 1.5 / d)
    assert np.allclose(tof_beta(d, 0.03, 0.02), 0.03 + 0.02 / d**4)
    assert np.allclose(tof_gamma(d, 1.0, 2.0, 3.0), 1.0 + 2.0 * d + 3.0 * d**2)
    sig0, sig1, sig2 = 0.0234, 0.0, 353.349
    assert np.allclose(tof_sigma_sq(d, sig0, sig1, sig2), sig0 + sig1 * d**2 + sig2 * d**4)
    squared = sig0**2 + sig1**2 * d**2 + sig2**2 * d**4
    assert np.min(np.abs(tof_sigma_sq(d, sig0, sig1, sig2) / squared)) < 1e-2

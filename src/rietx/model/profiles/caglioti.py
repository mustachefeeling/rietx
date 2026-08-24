"""Angular dependence of profile widths — instrument ⊕ sample split.

Gaussian *variance* (variances add under convolution):

    Γ_G²(θ) = (U + Us)·tan²θ + V·tanθ + W + P/cos²θ     [deg² 2θ]

U, V, W are the instrument resolution function (Caglioti, Paoletti & Ricci,
1958, Nucl. Instrum. 3, 223); the sample adds a Gaussian microstrain term
Us·tan²θ and a Gaussian size term P/cos²θ (the GSAS ``P``; Larson & Von
Dreele, 2004, GSAS manual; Thompson, Cox & Hastings, 1987, J. Appl. Cryst.
20, 79).

Lorentzian FWHM (Lorentzian convolution adds FWHMs):

    Γ_L(θ) = (X + Xs)/cosθ + (Y + Ys)·tanθ              [deg 2θ]

The 1/cosθ (and 1/cos²θ variance) terms carry Scherrer crystallite-size
broadening and the tanθ (tan²θ) terms microstrain broadening.  Note the
letter conventions differ between codes (GSAS: X=size, Y=strain; FullProf
swaps them) — this module documents the *physics* via argument names.

Reading a width as a size
-------------------------
The width laws above are in deg 2θ, which is the unit the pattern arrives in
and the wrong unit to *judge* a width in: the same 1.0 deg FWHM is a 8.2 nm
crystallite on Cu Kα and a 2.2 nm one on 11-BM's 0.4139 Å (computed below,
pinned in ``tests/test_profile_size.py``).  A number of degrees is therefore
not transferable between instruments, while the crystallite size it implies is
— which is the same statement as working in Q, since Scherrer broadening is
*constant* in Q:

    Q = 4π·sinθ/λ,  so  dQ/d(2θ) = 2π·cosθ/λ,  and with
    β(2θ) = K·λ/(L·cosθ)                                     [Scherrer, rad]
    ΔQ = (2π·cosθ/λ)·β = 2π·K/L                               [Å⁻¹]     (3)

independent of both λ and θ.  Hence :func:`apparent_size`, and the exact
consequence that makes it cheap: because the size law *is* 1/cosθ, the cosθ of
(3) cancels the cosθ of the law and a size **coefficient** maps to one size
with no reference angle at all —

    L = (180/π)·K·λ / x_size                                             (4)

for the Lorentzian ``x_size``, and the same with √``gauss_size`` for the
Gaussian variance coefficient.  :func:`apparent_size_from_size_coefficient` is
(4) and :func:`size_coefficient_for_size` is its inverse, which is what seeds a
width from a known specimen.

**Which parameters this reaches**, since it is the point of reading a width as
a size at all: exactly the two size coefficients of the laws above, and no
others.  ``x_size`` is ``instrument.profile.x + phases.N.lor_size``,
``gauss_size`` is ``phases.N.gauss_size``, and their declared bounds are where
the deg-versus-Å question bites:

* ``instrument.profile.x`` carries ``max = 1.0`` deg — 79.4 Å on Cu Kα against
  21.3 Å on 11-BM.  One cap, a 3.7× spread in the physics it admits.
* ``Phase.lor_size`` and ``Phase.gauss_size`` carry ``min = 0.0`` and **no max
  at all**, so on the sample side an unbounded specimen width is not capped
  badly — it is not capped.

The Caglioti ``u`` and ``w`` are **not** size terms and have no size to read:
``w`` is constant in θ and ``u`` goes as tan²θ, neither of them 1/cosθ.  A
number of degrees taken off either is a number at one chosen angle, which is
the reference angle this module exists to remove.  Report in degrees by all
means; decide in size.
"""

from __future__ import annotations

import math

import numpy as np

from ...backend import get_backend

_MIN_GAMMA_G2 = 1e-8  # deg²; keeps Γ_G real when U,V,W make the quadratic dip

#: Scherrer constant for a **FWHM** and roughly isotropic crystallites
#: (Scherrer, 1918, Nachr. Ges. Wiss. Göttingen, Math.-Phys. Kl. 1918, 98-100 —
#: the primary record's volume is the year, not the "26" the constant is usually
#: quoted with; Langford & Wilson, 1978, J. Appl. Cryst. 11, 102-113 tabulate K
#: by crystallite shape *and* by which width measure is used — 0.89 for the FWHM
#: of a sphere against 1.0747 for its integral breadth).  Shape moves it by
#: ~10-20 %, so an apparent size is an order-of-magnitude statement and never a
#: quotable two-figure one; K is an argument everywhere below so a caller with a
#: known morphology can say so.
SCHERRER_K = 0.9


def delta_q_fwhm(fwhm_deg: float, two_theta_deg: float,
                 wavelength_a: float) -> float:
    """The width ``fwhm_deg`` (deg 2θ FWHM) as a Q width, Å⁻¹.

    ``dQ/d(2θ) = 2π·cosθ/λ`` — the local Jacobian of Q = 4π·sinθ/λ, so this is
    a *linearisation* and is the honest conversion only while the width is
    small against the angle it sits at.  It is exact in the limit and within a
    percent for anything a Rietveld profile calls a peak.

    A scalar helper for reporting and diagnostics, not a hot-path function: it
    is plain python float arithmetic and does not route through the backend.
    """
    theta = math.radians(two_theta_deg / 2.0)
    return 2.0 * math.pi * math.cos(theta) * math.radians(fwhm_deg) / wavelength_a


def apparent_size(fwhm_deg: float, two_theta_deg: float, wavelength_a: float,
                  k: float = SCHERRER_K) -> float:
    """Scherrer crystallite size, Å, from a FWHM at one angle.

    ``L = K·λ / (β·cosθ)`` with β the FWHM in radians of 2θ (Scherrer, 1918;
    the K convention is :data:`SCHERRER_K`'s).  Equivalently ``L = 2π·K/ΔQ``
    with ΔQ from :func:`delta_q_fwhm` — the module docstring's (3), and the
    reason this is the instrument-independent way to read a width.

    This is the **whole** width, so the size it returns is a lower bound on the
    crystallite size unless the instrumental contribution has already been
    taken out: strain, the instrument function and the specimen all broaden,
    and Scherrer attributes everything it is handed to size.  Use it to ask
    "could size *alone* explain this width?", never to report a size from a
    total width.

    Raises ``ValueError`` on a non-positive width, angle or wavelength — a zero
    width is an infinite size, which is true and not a number a caller can do
    anything with.
    """
    if not fwhm_deg > 0.0:
        raise ValueError(f"fwhm_deg must be positive, got {fwhm_deg!r}")
    if not wavelength_a > 0.0:
        raise ValueError(f"wavelength_a must be positive, got {wavelength_a!r}")
    if not 0.0 < two_theta_deg < 180.0:
        raise ValueError(f"two_theta_deg must lie in (0, 180), got {two_theta_deg!r}")
    return 2.0 * math.pi * k / delta_q_fwhm(fwhm_deg, two_theta_deg, wavelength_a)


def apparent_size_from_size_coefficient(coefficient_deg: float,
                                        wavelength_a: float,
                                        k: float = SCHERRER_K) -> float:
    """Scherrer size, Å, from a **1/cosθ size coefficient** — no angle needed.

    The module docstring's (4).  ``coefficient_deg`` is the Lorentzian
    ``x_size`` — ``instrument.profile.x + phases.N.lor_size`` — directly, or
    ``sqrt(phases.N.gauss_size)`` for the Gaussian variance coefficient, both in
    the deg-2θ FWHM units :func:`lorentzian_fwhm` and :func:`gaussian_fwhm` use.
    Those are the only two parameters this inverts exactly; the Caglioti ``u``
    and ``w`` are tan²θ and constant terms and have no size to read.

    Angle-free because the law and Scherrer are the *same* 1/cosθ: this is
    :func:`apparent_size` evaluated at any 2θ whatever, and
    ``tests/test_profile_size.py`` asserts that identity across the pattern
    range rather than trusting the cancellation on paper.  That is the whole
    argument for judging a width as a size — there is no reference angle to
    choose and therefore none to get wrong.
    """
    if not coefficient_deg > 0.0:
        raise ValueError(f"coefficient_deg must be positive, got {coefficient_deg!r}")
    if not wavelength_a > 0.0:
        raise ValueError(f"wavelength_a must be positive, got {wavelength_a!r}")
    return math.degrees(k * wavelength_a / coefficient_deg)


def size_coefficient_for_size(size_a: float, wavelength_a: float,
                              k: float = SCHERRER_K) -> float:
    """Inverse of :func:`apparent_size_from_size_coefficient`: deg 2θ per Å.

    What seeds a width from a specimen one already knows something about — a
    micrograph, a synthesis, a previous refinement — rather than from the
    package's synchrotron-linewidth default, which a lab pattern's frozen
    windows cannot recover from.

    Seeds ``instrument.profile.x`` or ``phases.N.lor_size`` directly, and
    ``phases.N.gauss_size`` as the square of what it returns.
    """
    if not size_a > 0.0:
        raise ValueError(f"size_a must be positive, got {size_a!r}")
    if not wavelength_a > 0.0:
        raise ValueError(f"wavelength_a must be positive, got {wavelength_a!r}")
    return math.degrees(k * wavelength_a / size_a)


def gaussian_fwhm(theta_deg: np.ndarray, u: float, v: float, w: float,
                  gauss_size: float = 0.0, gauss_strain: float = 0.0) -> np.ndarray:
    """Γ_G(θ) from the Caglioti law + sample Gaussian size/strain variances;
    input θ (NOT 2θ) in degrees."""
    xp = get_backend()
    th = xp.radians(theta_deg)
    t = xp.tan(th)
    g2 = (u + gauss_strain) * t * t + v * t + w
    # unconditional (purity (b)): gauss_size = 0 adds an exact ±0, and the
    # variance floor below absorbs any −0.0 sign flip
    c = xp.cos(th)
    g2 = g2 + gauss_size / (c * c)
    return xp.sqrt(xp.maximum(g2, _MIN_GAMMA_G2))


def lorentzian_fwhm(theta_deg: np.ndarray, x_size: float, y_strain: float,
                    aniso_strain=0.0) -> np.ndarray:
    """Γ_L(θ) = x_size/cosθ + (y_strain + aniso_strain)·tanθ; θ in degrees.

    ``aniso_strain`` is Λ(hkl) from the Stephens anisotropic-strain model
    (:mod:`rietx.crystallography.stephens`) — a **per-reflection** array in
    the same deg-2θ FWHM units as ``y_strain``, which is why it enters the same
    tanθ slot rather than getting a law of its own.  It defaults to an exact
    ±0, so a phase without a microstrain block is bit-identical.
    """
    xp = get_backend()
    th = xp.radians(theta_deg)
    return x_size / xp.cos(th) + (y_strain + aniso_strain) * xp.tan(th)

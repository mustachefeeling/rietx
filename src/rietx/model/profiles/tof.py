"""Time-of-flight neutron peak profiles — back-to-back exponentials.

A TOF powder pattern is collected in flight time rather than in angle, and its
peak shape is dominated by the *moderator pulse*: a fast rise as neutrons of
one wavelength start to leak out, a slow decay as the last of them do.  Von
Dreele, Jorgensen & Windsor (1982), J. Appl. Cryst. 15, 581, model that pulse
as two back-to-back exponentials and convolute it with the resolution
function, which gives the two shapes implemented here (GSAS profile types 1
and 3; Larson & Von Dreele, 2004, GSAS manual LAUR 86-748).  The physical
reading of the two rates — moderator emission time constants — is Ikeda &
Carpenter (1985), Nucl. Instrum. Methods A 239, 536; their full pulse-shape
function (GSAS types 2 and 4) is *not* implemented here.

This module is a **standalone sibling** of ``pseudovoigt.py`` / ``voigt.py`` /
``fcj.py``: pure functions of the peak-local offset and the shape parameters,
arrays in and arrays out.  Nothing in the forward model calls it yet — the
TOF *axis* is a schema change on the data seam and is not this module's to
make — so every convention below is stated rather than inherited.

Units — stated, because unit mixing is how a TOF profile goes wrong
-------------------------------------------------------------------
========================  ==========================================
quantity                  unit
========================  ==========================================
flight time ``T``, ΔT     **microseconds** (µs), never ms
d-spacing ``d``           Å
``DIFC``                  µs/Å      (``DIFA`` µs/Å², ``TZERO`` µs)
``alpha``, ``beta``       µs⁻¹      (rates, not times)
``sigma``                 µs — the Gaussian **standard deviation**
``gamma``                 µs — the Lorentzian **FWHM**
========================  ==========================================

The two width arguments deliberately do *not* share a convention, because
GSAS's do not: its ``sig-0/1/2`` coefficients sum to the **variance** σ²
(:func:`tof_sigma_sq` returns that variance, so a caller passes its square
root here) while its ``gam-0/1/2`` sum to a full width.  ``gamma`` here is
therefore *twice* the ``gamma`` of :func:`~rietx.model.profiles.voigt.voigt`,
which takes a Lorentzian HWHM; the mixing with the Gaussian is the same
Thompson-Cox-Hastings construction either way and is reused from
``pseudovoigt.tch_gamma_eta``.

Sign — ΔT is **channel minus peak**
-----------------------------------
``dt`` = T(channel) − T(peak).  With that sign, ``alpha`` is the rise on the
**short**-TOF side (dt < 0) and ``beta`` the decay on the **long**-TOF side
(dt > 0), so β < α — the usual case, a decay slower than the rise — puts the
tail at long flight time, which is where a moderator puts it.  A profile with
the tail on the short-TOF side means the two rates have been swapped.

Two notes on the sources, both measured rather than assumed:

* the GSAS manual's *prose* says ΔT is "the difference in TOF between the
  reflection position, T_ph, and the profile point, T", which reads
  T_ph − T — the opposite of its own formulae (its y = (ασ² + ΔT)/√(2σ²) is
  the short-TOF wing only under channel − peak) and the opposite of GSAS-II,
  which calls the profile with ``xdata - pos``.  The formulae and the code
  agree with each other; the sentence is the odd one out.
* the GSAS manual's Lorentzian term for profile type 3, and ``epsvoigt.for``
  which implements it, both use p = −α·ΔT + iαΓ/2 for the *rise* wing.  That
  is the argument the type-2 (Ikeda-Carpenter) function needs, where both
  exponentials decay forward in time; the back-to-back rise wing runs
  backwards and needs p = +α·ΔT + iαΓ/2.  As published, the type-3 Lorentzian
  is symmetric under α ↔ β alone, which the exact convolution cannot be.
  This module uses the sign the convolution requires;
  ``tests/test_profile_tof.py`` measures both against a brute-force
  convolution and pins the size of the disagreement (0.81 % of the peak at a
  mixed shape).  A γ coefficient refined by GSAS against the published
  function is therefore not directly transferable.

The closed forms
----------------
Write N = αβ/(2(α+β)) and let the bare pulse be E(τ) = 2N·e^{ατ} (τ < 0),
2N·e^{−βτ} (τ ≥ 0), which has unit area.  Convoluting with a Gaussian of
variance σ² gives GSAS type 1,

    Ω(ΔT) = N[e^u·erfc(y) + e^v·erfc(z)]
    u = (α/2)(ασ² + 2ΔT)      y = (ασ² + ΔT)/√(2σ²)
    v = (β/2)(βσ² − 2ΔT)      z = (βσ² − ΔT)/√(2σ²)

and because u − y² = v − z² = −ΔT²/(2σ²) *identically*, the pair evaluates
without overflow as one Gaussian factor times two scaled complementary error
functions, e^{−ΔT²/2σ²}·[erfcx(y) + erfcx(z)] — which is what GSAS's own
``HFUNC`` does and what :func:`_hwing` does here, through the Faddeeva w(z)
already in ``faddeeva.py`` (erfcx(t) = w(it) for t ≥ 0, Weideman 1994).

Convoluting instead with a pseudo-Voigt of the same two widths gives GSAS
type 3: the Gaussian half is the above evaluated at the *combined* TCH width,
and the Lorentzian half is

    Ω_L(ΔT) = −(2N/π)·(Im[e^p E₁(p)] + Im[e^q E₁(q)])
    p = α(ΔT + iΓ/2),   q = β(−ΔT + iΓ/2)

with E₁ the exponential integral and Γ the TCH combined FWHM.  E₁ is a
genuinely different function from erfc — the Faddeeva w(z) cannot supply it —
so :func:`scaled_exp1` implements e^z·E₁(z) here (§ below).

At γ = 0 the TCH mixing gives η = 0 and Γ = Γ_G, and
:func:`back_to_back_pseudovoigt` returns :func:`back_to_back_gaussian`
bit-for-bit: the reduction is exact, not merely close.
"""

from __future__ import annotations

import numpy as np

from ...backend import get_backend
from .faddeeva import faddeeva_w
from .pseudovoigt import _TCH_ETA, _TCH_GAMMA, tch_gamma_eta
from .voigt import GAUSS_FWHM_TO_SIGMA

_SQRT2 = np.sqrt(2.0)
_TWO_OVER_SQRT_PI = 2.0 / np.sqrt(np.pi)
#: Euler-Mascheroni γ, for the E₁ power series
_EULER = 0.5772156649015328606

# --- e^z·E₁(z): where each branch is used, and why -------------------------
#
# Two classical algorithms cover the plane and each fails where the other
# works, so the split is by *cancellation*, not by |z| alone.  The power
# series E₁(z) = −γ − ln z + Σ(−1)^{k+1} z^k/(k·k!) has its largest term
# ~e^{|z|} against a result ~e^{−Re z}, so it loses roughly e^{|z| + Re z}:
# exact on the negative real axis at any size, useless on the positive one
# past |z| ≈ 5.  The continued fraction (Abramowitz & Stegun 5.1.22, by
# modified Lentz) is the reverse — ~1e-15 for |z| ≳ 30 at every angle, arg z
# → π included, and hopeless both for small |z| and for moderate |z| close to
# the cut (measured: 1.3e-3 relative at z = −8 + 0.5i, at any term count).
#
# Hence *two* conditions, and the radius is not a convergence bound: the
# series must own the near-cut wedge until |z| is large enough for the
# fraction to be safe there, and must hand back before its own rotation-driven
# cancellation bites (which is worse than e^{|z| + Re z} predicts once the
# terms turn).  Both thresholds sit in a flat region — the measured worst case
# over |z| ∈ [1e-3, 1e4] × 240 angles is 1.3e-14 relative at (4.0, 38.0) and
# stays under 3.3e-14 for any loss in [3, 5] and radius in [35, 40], while
# radius 30 costs three orders (9.5e-12, at |z| just above it, on the cut).
#: series while the cancellation loss e^{|z| + Re z} stays under ~e^4 …
SERIES_LOSS_EXPONENT = 4.0
#: … and |z| is inside the radius the continued fraction is not yet safe over.
SERIES_RADIUS = 38.0
#: fixed term/iteration counts — never data-dependent, so the residual stays
#: smooth for finite-difference and autodiff Jacobians (the same rule the FCJ
#: quadrature follows in ``fcj.py``).
SERIES_TERMS = 100
CONTINUED_FRACTION_TERMS = 50
#: arguments substituted into the branch that is *not* selected, so neither
#: evaluation can produce a NaN that ``where`` would then have to hide
_SERIES_SAFE = -1.0 + 0.0j
_CF_SAFE = 10.0 + 0.0j
#: modified-Lentz guards (Numerical Recipes' FPMIN role)
_LENTZ_BIG = 1.0e300
_LENTZ_TINY = 1.0e-300


# ----------------------------------------------------------------------
# the TOF ↔ d map
# ----------------------------------------------------------------------
def tof_from_d(d, difc, difa=0.0, tzero=0.0, difb=0.0):
    """T = DIFC·d + DIFA·d² + TZERO + DIFB/d — flight time in µs from d in Å.

    The diffractometer constants of Von Dreele, Jorgensen & Windsor (1982),
    J. Appl. Cryst. 15, 581: DIFC is the geometric constant (µs/Å, equal to
    252.777·L·2·sinθ for a total flight path L in m), DIFA a small empirical
    curvature (µs/Å²) absorbing sample-position and detector-depth effects,
    and TZERO (µs) the electronic time offset.

    ``difb`` (µs·Å) is GSAS-II's fourth term, ``GSASIIlattice.Dsp2pos`` — not
    in the GSAS manual's relation and 0 in most projects, which is why it is
    the last argument with a zero default.  **At difb = 0 the returned array is
    bit-identical to the three-term form**: ``0.0 / d`` is ``+0.0`` for every
    positive d and ``x + 0.0 == x`` exactly in IEEE-754 for every finite x, so
    adding the term unconditionally costs one flop and changes no bit.  Written
    that way rather than behind an ``if`` because a branch on a *value* is
    exactly what the residual must not contain (the module header's purity
    note): on a traced backend ``difb`` may be a tracer.

    (Added by the time-of-flight forward model, which needs the four-term
    relation on the backend op set with the constants coming from θ;
    ``TOFSource.tof_from_d`` is the same relation on a *stored* calibration and
    reads ``.value`` off the parameters, which a traced residual cannot do.)
    """
    xp = get_backend()
    dd = xp.asarray(d, dtype=np.float64)
    return difc * dd + difa * dd * dd + tzero + difb / dd


def d_from_tof(tof, difc, difa=0.0, tzero=0.0):
    """The exact inverse of :func:`tof_from_d`, on the physical branch.

    Solving DIFA·d² + DIFC·d + (TZERO − T) = 0 for the root that tends to
    (T − TZERO)/DIFC as DIFA → 0 gives, in the form that does not cancel,

        d = 2(T − TZERO) / (DIFC + √(DIFC² + 4·DIFA·(T − TZERO)))

    which is also the DIFA = 0 answer with no branch.  Raises ``ValueError``
    when the requested flight times do not lie on one monotonic branch of the
    map — a negative discriminant, or a turning point (dT/dd = DIFC + 2·DIFA·d
    changing sign) inside the range — because a non-monotonic map has no
    inverse to choose and silently picking a root would put reflections at
    d-spacings the instrument cannot have produced.
    """
    xp = get_backend()
    t = xp.asarray(tof, dtype=np.float64)
    if difc <= 0.0:
        raise ValueError(f"DIFC must be positive (got {difc})")
    shifted = t - tzero
    disc = difc * difc + 4.0 * difa * shifted
    if bool(np.any(np.asarray(disc) < 0.0)):
        raise ValueError(
            "TOF outside the range this (DIFC, DIFA, TZERO) can reach: the "
            "quadratic T(d) has no real root there"
        )
    d = 2.0 * shifted / (difc + xp.sqrt(disc))
    slope = difc + 2.0 * difa * d
    if bool(np.any(np.asarray(slope) <= 0.0)):
        raise ValueError(
            "T(d) is not monotonic over the requested range: DIFA = "
            f"{difa} turns the map at d = {-difc / (2.0 * difa):.4g} Å"
        )
    return d


# ----------------------------------------------------------------------
# the d-dependence of the shape parameters (GSAS's own names)
# ----------------------------------------------------------------------
def tof_alpha(d, alpha0=0.0, alpha1=0.0):
    """α(d) = α₀ + α₁/d [µs⁻¹] — the moderator rise rate.

    Larson & Von Dreele (2004), GSAS manual, TOF profile function 1
    (coefficients ``alp-0``, ``alp-1``).  **Profile type 3 drops α₀** and
    refines the single coefficient it names ``alp``: pass ``alpha0=0`` for
    type-3-compatible behaviour, which is also what GSAS-II computes
    (``getTOFalpha`` returns ``alpha/dsp``).  The rate is physically the
    moderator's fast emission constant (Ikeda & Carpenter, 1985, Nucl.
    Instrum. Methods A 239, 536), which is why it scales as 1/d ∝ energy.
    """
    xp = get_backend()
    dd = xp.asarray(d, dtype=np.float64)
    return alpha0 + alpha1 / dd


def tof_beta(d, beta0=0.0, beta1=0.0):
    """β(d) = β₀ + β₁/d⁴ [µs⁻¹] — the moderator decay rate.

    Larson & Von Dreele (2004), GSAS manual (``bet-0``, ``bet-1``); the slow
    constant of Ikeda & Carpenter (1985).  GSAS-II carries an extra ``beta-q``
    term in 1/d²; it is not part of the published parameterisation and is not
    implemented.
    """
    xp = get_backend()
    dd = xp.asarray(d, dtype=np.float64)
    return beta0 + beta1 / dd**4


def tof_sigma_sq(d, sig0=0.0, sig1=0.0, sig2=0.0):
    """σ²(d) = σ₀² + σ₁²·d² + σ₂²·d⁴ [µs²] — the Gaussian **variance**.

    Larson & Von Dreele (2004), GSAS manual, TOF profile functions 1 and 3.

    **The coefficients are not squared here, and this is the trap in the
    formula.**  The manual writes the three symbols as σ₀², σ₁², σ₂² because
    each *is* a variance-like quantity; the refined parameters GSAS names
    ``sig-0``, ``sig-1``, ``sig-2`` are those quantities themselves, and
    GSAS-II's ``getTOFsig`` is literally ``sig-0 + sig-1·d² + sig-2·d⁴``.
    Reading the superscripts as an instruction to square what the instrument
    file supplies inflates every width by the value of the coefficient.
    Variances add under convolution, which is why this law is written for σ²
    while the Lorentzian one below is written for a width.
    """
    xp = get_backend()
    dd = xp.asarray(d, dtype=np.float64)
    return sig0 + sig1 * dd**2 + sig2 * dd**4


def tof_gamma(d, gam0=0.0, gam1=0.0, gam2=0.0):
    """γ(d) = γ₀ + γ₁·d + γ₂·d² [µs] — the Lorentzian **FWHM**.

    Larson & Von Dreele (2004), GSAS manual, TOF profile function 3
    (``gam-0``, ``gam-1``, ``gam-2``).  Documented by physics rather than by
    letter, as the constant-wavelength widths in ``caglioti.py`` are: constant
    Δd/d is microstrain and gives ΔT ∝ d, so **γ₁ is strain**; constant ΔQ is
    Scherrer size and gives Δd ∝ d², so **γ₂ is size**.

    The letters are worth stating because GSAS-II renames these three to X, Y,
    Z (γ = Z + X·d + Y·d²) — and its X is the *size* coefficient in the
    constant-wavelength law and the *strain* one here, with Y the other way
    round.  One code, one pair of letters, two opposite meanings; transfer a
    number by matching the power of d, never the letter.
    """
    xp = get_backend()
    dd = xp.asarray(d, dtype=np.float64)
    return gam0 + gam1 * dd + gam2 * dd**2


def tof_sample_gamma(d, difc, size_per_a=0.0, strain=0.0):
    """The **specimen's** Lorentzian FWHM on a bank, µs — ``tof_gamma``'s peer.

        ΔT_L = DIFC·(``size_per_a``·d² + ``strain``·d)

    Both terms are one line of Bragg's law in flight time.  A bank's
    calibration is T = DIFC·d, so a fractional spread in d is the same
    fractional spread in T and ΔT = DIFC·d·(Δd/d):

    * **microstrain** is a constant Δd/d = ε, so ΔT = DIFC·ε·d — the d¹ law;
    * **crystallite size** is a constant ΔQ = 2πK/L, i.e. Δd/d = (K/L)·d
      (:mod:`rietx.model.profiles.caglioti`'s (7)), so ΔT = DIFC·(K/L)·d² —
      the d² law.

    ``size_per_a`` is therefore K/L in **Å⁻¹** and ``strain`` is Δd/d
    **dimensionless**, both as FWHMs, and neither carries a wavelength or an
    angle: they are the specimen's own numbers and are the quantities a joint
    constant-wavelength + time-of-flight fit shares.  Lorentzian FWHMs add
    under convolution, so the two add linearly and the sum adds to the
    instrument's γ(d).  Zero coefficients give an exact ``0.0``, so a phase
    that declares no sample broadening leaves the instrument's γ bit for bit.

    These are the same two powers of d the *instrument*'s :func:`tof_gamma`
    already carries in γ₁ and γ₂ — deliberately, and it is why the sample terms
    need no new container in the profile: the instrument ⊕ sample split here is
    the same one ``caglioti.py`` draws on the angular arm, calibrated on a
    standard and frozen, with the specimen's contribution the part refined.

    Identical to GSAS-II's ``GetSampleSigGam`` TOF branch
    (``GSASIIstrMath.py``; Toby & Von Dreele, 2013, J. Appl. Cryst. 46, 544)
    with its units substituted: its ``Sgam = 1e-4·DIFC·d²/Size;i`` is the first
    term with Size;i in µm and K = 1, and its
    ``Mgam = 1e-6·DIFC·d·Mustrain;i`` is the second with
    Mustrain;i = 10⁶·Δd/d.  **That Mustrain convention is GSAS-II's own and it
    is not the one its constant-wavelength branch uses**: there
    ``Mgam = 0.018·Mustrain;i·tanθ/π`` centidegrees is Δ2θ = 10⁻⁶·Mustrain·tanθ
    radians, against the Stokes-Wilson Δ2θ = 2·(Δd/d)·tanθ, i.e.
    Mustrain = 2·10⁶·Δd/d — a factor of two away from the flight-time branch.
    rietx has one convention, Δd/d as a FWHM, in both arms
    (:func:`~rietx.model.profiles.caglioti.microstrain_from_strain_coefficient`),
    so a Mustrain transferred from GSAS-II must be read with the branch it came
    from.

    **DIFA and DIFB do not enter.**  The exact width would use
    |dT/dd| = DIFC + 2·DIFA·d − DIFB/d², and GSAS-II uses DIFC alone; this
    follows GSAS-II so that a width transferred between the two codes is the
    same width, and the difference is exactly zero on any bank whose DIFA and
    DIFB are zero — which is every bank rietx has been measured on.
    """
    xp = get_backend()
    dd = xp.asarray(d, dtype=np.float64)
    return difc * (size_per_a * dd**2 + strain * dd)


def tof_sample_sigma_sq(d, difc, size_var=0.0, strain_var=0.0):
    """The specimen's Gaussian **variance** on a bank, µs² — ``tof_sigma_sq``'s peer.

        σ² = DIFC²·(``size_var``·d⁴ + ``strain_var``·d²)/(8 ln 2)

    The same two laws as :func:`tof_sample_gamma`, squared, because Gaussian
    *variances* add under convolution where Lorentzian widths do: the two
    mechanisms combine in quadrature, which is GSAS-II's
    ``sig = [Sgam² + Mgam²]/ateln2`` written with the squares taken on the
    coefficients instead of on the widths.

    So the arguments are **variances**, not widths: ``size_var`` is (K/L)² in
    Å⁻² and ``strain_var`` is (Δd/d)², which is exactly the convention
    ``phases.N.gauss_size`` and ``gauss_strain`` are already stored in
    (:mod:`rietx.model.profiles.caglioti`).  Writing it this way is not a
    rearrangement for its own sake — it takes **no square root of a refined
    parameter**, which matters because the derivative of √x at the zero
    default is infinite and an autodiff backend returns a nan for it where
    finite differences quietly return a number.

    The 1/(8 ln 2) is **one over**
    :data:`~rietx.model.profiles.voigt.GAUSS_FWHM_TO_SIGMA` squared — that
    constant is Γ_G/σ = 2√(2 ln 2), so a variance divides by its square where a
    standard deviation divides by it once.  GSAS-II keeps the same number the
    other way up and calls it ``ateln2``; multiplying by it here instead of
    dividing would inflate every Gaussian sample variance by 8 ln 2 ≈ 5.5, and
    ``tests/test_tof_sample_broadening.py`` checks the direction against
    (8 ln 2)⁻¹ written out rather than against this name.  Zero coefficients
    give an exact ``0.0``.
    """
    xp = get_backend()
    dd = xp.asarray(d, dtype=np.float64)
    return (difc**2 * (size_var * dd**4 + strain_var * dd**2)
            / GAUSS_FWHM_TO_SIGMA**2)


# ----------------------------------------------------------------------
# e^z·E₁(z)
# ----------------------------------------------------------------------
def _exp1_series(z):
    """e^z·E₁(z) by the power series (Abramowitz & Stegun 5.1.11)."""
    xp = get_backend()
    total = xp.zeros_like(z)
    term = xp.zeros_like(z) + 1.0
    for k in range(1, SERIES_TERMS + 1):
        term = term * (-z) / k          # (−z)^k / k!
        total = total - term / k        # Σ (−1)^{k+1} z^k / (k·k!)
    return xp.exp(z) * (-_EULER - xp.log(z) + total)


def _exp1_continued_fraction(z):
    """e^z·E₁(z) by modified Lentz on A&S 5.1.22's continued fraction.

    The fraction converges *to* e^z·E₁(z) directly, so this branch needs no
    exponential at all and cannot overflow for large Re z.
    """
    xp = get_backend()
    b = z + 1.0
    c = xp.zeros_like(z) + _LENTZ_BIG
    d = 1.0 / b
    h = d
    for i in range(1, CONTINUED_FRACTION_TERMS + 1):
        a = -float(i * i)
        b = b + 2.0
        d = 1.0 / (a * d + b + _LENTZ_TINY)
        c = b + a / (c + _LENTZ_TINY)
        h = h * (c * d)
    return h


def scaled_exp1(z):
    """e^z·E₁(z) for complex ``z`` off the negative real axis.

    The scaled form is the one the profile needs and the one that stays
    bounded: E₁(z) itself overflows as Re z → −∞ and underflows as Re z → +∞,
    while e^z·E₁(z) → −1/z at both ends.  Branch selection and its measured
    accuracy are in this module's header comment; both branches are evaluated
    on safe arguments so neither can put a NaN into the ``where``.
    """
    xp = get_backend()
    zc = xp.asarray(z, dtype=np.complex128)
    az = xp.abs(zc)
    use_series = ((az + xp.real(zc)) <= SERIES_LOSS_EXPONENT) & (az <= SERIES_RADIUS)
    return xp.where(
        use_series,
        _exp1_series(xp.where(use_series, zc, _SERIES_SAFE)),
        _exp1_continued_fraction(xp.where(use_series, _CF_SAFE, zc)),
    )


# ----------------------------------------------------------------------
# the bare pulse and its Gaussian convolution
# ----------------------------------------------------------------------
def back_to_back_exponential(dt, alpha, beta):
    """The unmoderated pulse E(ΔT) — two back-to-back exponentials, unit area.

    Von Dreele, Jorgensen & Windsor (1982), J. Appl. Cryst. 15, 581.  Rise
    e^{α·ΔT} at short TOF, decay e^{−β·ΔT} at long TOF, normalised by
    αβ/(α+β).  This is the σ → 0 limit of :func:`back_to_back_gaussian` and
    the shape whose asymmetry the sign convention in the module header is
    about.
    """
    xp = get_backend()
    x = xp.asarray(dt, dtype=np.float64)
    # the exponent is chosen *before* exponentiating: both spellings are
    # negative on their own side, so neither branch can overflow
    return (alpha * beta / (alpha + beta)) * xp.exp(
        xp.where(x < 0.0, alpha * x, -beta * x)
    )


def _erfcx(t):
    """e^{t²}·erfc(t) for t ≥ 0, as w(it) — the Faddeeva already in the tree.

    w(z) = e^{−z²}erfc(−iz) on Im z ≥ 0 (``faddeeva.py``; Weideman 1994), so
    z = it with t ≥ 0 gives exactly the scaled complementary error function.
    Reusing it keeps one approximation in the package rather than two that
    can drift apart, and is why this module adds no erfc of its own.
    """
    return get_backend().real(faddeeva_w(1j * t))


def _hwing(exponent, y):
    """e^{exponent}·erfcx(y) for either sign of y, without overflow.

    The identity behind the whole profile is that the Gaussian exponent and
    the erfc argument satisfy u − y² = −ΔT²/2σ², so the huge e^u and the tiny
    erfc(y) are never formed separately.  For y < 0 the reflection
    erfcx(y) = 2e^{y²} − erfcx(−y) is used, and there ``exponent + y²`` (the
    GSAS u or v) is provably ≤ 0, so the substituted branch cannot overflow
    either.  Same construction as GSAS's ``HFUNC``.
    """
    xp = get_backend()
    kept = xp.exp(exponent) * _erfcx(xp.abs(y))
    reflected = 2.0 * xp.exp(xp.minimum(exponent + y * y, 0.0)) - kept
    return xp.where(y < 0.0, reflected, kept)


def _gaussian_parts(dt, alpha, beta, sigma):
    """(N, H₁, H₂, e^{E}, y₁, y₂, σ_safe) — written once, used by both forms.

    :func:`back_to_back_gaussian` and :func:`back_to_back_gaussian_derivs`
    build Ω from these same values, so the value a Jacobian caller sees is
    bit-identical to the value the residual sees.  ``pseudovoigt.py`` and
    ``voigt.py`` carry a deliberate 1-2 ulp split between their two spellings
    for a caller that has to reproduce one of them; nothing consumes this
    module yet, so there is no such caller and no reason to create the split.
    """
    xp = get_backend()
    x = xp.asarray(dt, dtype=np.float64)
    s = xp.asarray(sigma, dtype=np.float64)
    safe = xp.where(s > 0.0, s, 1.0)
    var = safe * safe
    root = safe * _SQRT2
    y1 = (alpha * var + x) / root
    y2 = (beta * var - x) / root
    exponent = -0.5 * (x / safe) ** 2
    n = 0.5 * alpha * beta / (alpha + beta)
    return n, _hwing(exponent, y1), _hwing(exponent, y2), xp.exp(exponent), y1, y2, safe


def back_to_back_gaussian(dt, alpha, beta, sigma):
    """GSAS TOF profile type 1: back-to-back exponentials ⊗ Gaussian.

    Von Dreele, Jorgensen & Windsor (1982), J. Appl. Cryst. 15, 581, in the
    closed erfc form; parameterisation as Larson & Von Dreele (2004), GSAS
    manual.  Unit area in ΔT, so a reflection's intensity enters purely
    through the prefactor, exactly as for the constant-wavelength shapes.

    ``dt`` is channel − peak in µs, ``alpha``/``beta`` are rates in µs⁻¹ and
    ``sigma`` is the Gaussian standard deviation in µs (the square root of
    :func:`tof_sigma_sq`).  σ = 0 returns the bare
    :func:`back_to_back_exponential` rather than a division by zero.
    """
    xp = get_backend()
    s = xp.asarray(sigma, dtype=np.float64)
    n, h1, h2, _e, _y1, _y2, _safe = _gaussian_parts(dt, alpha, beta, s)
    return xp.where(
        s > 0.0, n * (h1 + h2), back_to_back_exponential(dt, alpha, beta)
    )


def back_to_back_gaussian_derivs(dt, alpha, beta, sigma):
    """(Ω, ∂Ω/∂ΔT, ∂Ω/∂α, ∂Ω/∂β, ∂Ω/∂σ) — closed forms for the Jacobian.

    With H = e^{E}·erfcx(y) and dH/dy = 2y·H − (2/√π)e^{E},

        ∂Ω/∂ΔT = N(αH₁ − βH₂)        — the two erfc terms cancel exactly
        ∂Ω/∂α  = Ω·β/(α(α+β)) + N·(σ/√2)·dH₁/dy₁
        ∂Ω/∂β  = Ω·α/(β(α+β)) + N·(σ/√2)·dH₂/dy₂
        ∂Ω/∂σ² = Ω·ΔT²/(2σ⁴)
                 + N[dH₁/dy₁·(ασ² − ΔT) + dH₂/dy₂·(βσ² + ΔT)]/(2σ²)^{3/2}

    and ∂Ω/∂σ = 2σ·∂Ω/∂σ².  Note the *offset* convention: the derivative with
    respect to the peak **position** is the negative of ∂Ω/∂ΔT, since
    ΔT = channel − peak.  Slots into the ``(Ω, ∂/∂x, ∂/∂w…)`` shape of
    ``pseudovoigt.pseudo_voigt_derivs``.

    σ > 0 is required: the σ = 0 limit is the bare exponential pair, whose
    ∂/∂σ does not exist (it is the one-sided start of a σ² law), so unlike
    :func:`back_to_back_gaussian` this function does not substitute for it.
    """
    xp = get_backend()
    x = xp.asarray(dt, dtype=np.float64)
    n, h1, h2, expo, y1, y2, s = _gaussian_parts(dt, alpha, beta, sigma)
    omega = n * (h1 + h2)
    dh1 = 2.0 * y1 * h1 - _TWO_OVER_SQRT_PI * expo
    dh2 = 2.0 * y2 * h2 - _TWO_OVER_SQRT_PI * expo
    var = s * s
    d_ddt = n * (alpha * h1 - beta * h2)
    d_dalpha = omega * beta / (alpha * (alpha + beta)) + n * (s / _SQRT2) * dh1
    d_dbeta = omega * alpha / (beta * (alpha + beta)) + n * (s / _SQRT2) * dh2
    root3 = (2.0 * var) ** 1.5
    d_dvar = omega * (x * x) / (2.0 * var * var) + n * (
        dh1 * (alpha * var - x) + dh2 * (beta * var + x)
    ) / root3
    return omega, d_ddt, d_dalpha, d_dbeta, 2.0 * s * d_dvar


# ----------------------------------------------------------------------
# the pseudo-Voigt convolution (GSAS type 3)
# ----------------------------------------------------------------------
def tof_pseudovoigt_widths(sigma, gamma):
    """(Γ, η, σ_eff) for :func:`back_to_back_pseudovoigt`.

    The Thompson-Cox-Hastings (1987, J. Appl. Cryst. 20, 79) combination of
    ``pseudovoigt.tch_gamma_eta``, entered with the Gaussian FWHM
    Γ_G = 2√(2 ln2)·σ and the Lorentzian FWHM γ, and read back out as the
    combined FWHM Γ, the mixing η, and the standard deviation Γ/(2√(2 ln2))
    that the Gaussian half of the pseudo-Voigt is evaluated at.  γ = 0 is
    forced to Γ = Γ_G exactly, so the type-3 shape reduces to type 1 without a
    last-digit shift from the fifth root.
    """
    xp = get_backend()
    g = xp.asarray(gamma, dtype=np.float64)
    fwhm_g = GAUSS_FWHM_TO_SIGMA * xp.asarray(sigma, dtype=np.float64)
    fwhm, eta = tch_gamma_eta(fwhm_g, g)
    fwhm = xp.where(g > 0.0, fwhm, fwhm_g)
    return fwhm, eta, fwhm / GAUSS_FWHM_TO_SIGMA


def _lorentzian_parts(dt, alpha, beta, fwhm):
    """(N, e^p E₁(p), e^q E₁(q), p, q) for the Lorentzian half.

    p = α(ΔT + iΓ/2), q = β(−ΔT + iΓ/2) — the arguments the convolution of
    the back-to-back pair with a Lorentzian of FWHM Γ produces.  Γ = 0 is
    substituted away because the caller multiplies this half by η, which is
    exactly zero there; the substituted value never reaches the result.
    """
    xp = get_backend()
    x = xp.asarray(dt, dtype=np.float64)
    g = xp.asarray(fwhm, dtype=np.float64)
    safe = xp.where(g > 0.0, g, 1.0)
    p = alpha * (x + 0.5j * safe)
    q = beta * (-x + 0.5j * safe)
    n = 0.5 * alpha * beta / (alpha + beta)
    return n, scaled_exp1(p), scaled_exp1(q), p, q


def _lorentzian(dt, alpha, beta, fwhm):
    xp = get_backend()
    n, a, b, _p, _q = _lorentzian_parts(dt, alpha, beta, fwhm)
    return -(2.0 * n / xp.pi) * (xp.imag(a) + xp.imag(b))


def back_to_back_pseudovoigt(dt, alpha, beta, sigma, gamma):
    """GSAS TOF profile type 3: back-to-back exponentials ⊗ pseudo-Voigt.

    Von Dreele, Jorgensen & Windsor (1982), J. Appl. Cryst. 15, 581, for the
    exponential pair; Thompson, Cox & Hastings (1987), J. Appl. Cryst. 20, 79,
    for the pseudo-Voigt it is convoluted with; Larson & Von Dreele (2004),
    GSAS manual, for the parameterisation.  ``gamma`` is the Lorentzian FWHM
    in µs — see this module's header on why that differs from
    ``voigt.voigt``'s half-width, and on the sign of p that this
    implementation does *not* take from the manual.

    Unit area in ΔT.  At γ = 0 this is :func:`back_to_back_gaussian` exactly.
    """
    xp = get_backend()
    fwhm, eta, sigma_eff = tof_pseudovoigt_widths(sigma, gamma)
    gaussian = back_to_back_gaussian(dt, alpha, beta, sigma_eff)
    lorentzian = _lorentzian(dt, alpha, beta, fwhm)
    return xp.where(
        xp.asarray(gamma, dtype=np.float64) > 0.0,
        eta * lorentzian + (1.0 - eta) * gaussian,
        gaussian,
    )


def _tch_slopes(fwhm_g, gamma, fwhm):
    """(∂Γ/∂Γ_G, ∂Γ/∂γ, dη/dq) at the Γ ``tch_gamma_eta`` already returned.

    Differentiating TCH's Γ⁵ = Σ c_i Γ_G^{5−i} γ^i and η = Σ e_j q^j term by
    term.  The *values* stay ``tch_gamma_eta``'s, so this adds slopes to the
    sibling's answer rather than a second copy of it.
    """
    xp = get_backend()
    gg = xp.asarray(fwhm_g, dtype=np.float64)
    gl = xp.asarray(gamma, dtype=np.float64)
    coeffs = (1.0, *_TCH_GAMMA, 1.0)
    d_dgg = xp.zeros_like(gg * gl)
    d_dgl = xp.zeros_like(gg * gl)
    for i, c in enumerate(coeffs):
        if i < 5:
            d_dgg = d_dgg + (5 - i) * c * gg ** (4 - i) * gl**i
        if i > 0:
            d_dgl = d_dgl + i * c * gg ** (5 - i) * gl ** (i - 1)
    five_g4 = 5.0 * fwhm**4
    e1, e2, e3 = _TCH_ETA
    q = gl / fwhm
    return d_dgg / five_g4, d_dgl / five_g4, e1 + 2.0 * e2 * q + 3.0 * e3 * q**2


def back_to_back_pseudovoigt_derivs(dt, alpha, beta, sigma, gamma):
    """(Ω, ∂Ω/∂ΔT, ∂Ω/∂α, ∂Ω/∂β, ∂Ω/∂σ, ∂Ω/∂γ) for the type-3 Jacobian.

    The Lorentzian half differentiates cleanly through
    d/dz[e^z E₁(z)] = e^z E₁(z) − 1/z: writing A = e^p E₁(p), B = e^q E₁(q),

        ∂Ω_L/∂ΔT = −(2N/π)(α·Im A − β·Im B)
        ∂Ω_L/∂α  = Ω_L·β/(α(α+β)) − (2N/πα)·Im(pA)
        ∂Ω_L/∂β  = Ω_L·α/(β(α+β)) − (2N/πβ)·Im(qB)
        ∂Ω_L/∂Γ  = −(N/π)(α·Re A + β·Re B)

    where in each case the −1/z pieces of the two wings cancel identically —
    a cancellation that only happens with the p sign this module uses, and
    which GSAS's published derivatives carry as extra ΔT/(ΔT² + Γ²/4) terms.
    The two width partials then run through TCH: σ and γ both move Γ, and γ
    also moves η, so ∂Ω/∂σ = 2√(2ln2)·∂Ω/∂Γ_G with the mixing chain included.
    """
    xp = get_backend()
    g = xp.asarray(gamma, dtype=np.float64)
    fwhm, eta, sigma_eff = tof_pseudovoigt_widths(sigma, gamma)
    fwhm_g = GAUSS_FWHM_TO_SIGMA * xp.asarray(sigma, dtype=np.float64)

    tg, dtg_ddt, dtg_da, dtg_db, dtg_dsig = back_to_back_gaussian_derivs(
        dt, alpha, beta, sigma_eff
    )
    n, a, b, p, q = _lorentzian_parts(dt, alpha, beta, fwhm)
    tl = -(2.0 * n / xp.pi) * (xp.imag(a) + xp.imag(b))
    dtl_ddt = -(2.0 * n / xp.pi) * (alpha * xp.imag(a) - beta * xp.imag(b))
    dtl_da = tl * beta / (alpha * (alpha + beta)) - (
        2.0 * n / (xp.pi * alpha)
    ) * xp.imag(p * a)
    dtl_db = tl * alpha / (beta * (alpha + beta)) - (
        2.0 * n / (xp.pi * beta)
    ) * xp.imag(q * b)
    dtl_dfwhm = -(n / xp.pi) * (alpha * xp.real(a) + beta * xp.real(b))

    # ∂/∂Γ at fixed η — the Gaussian half sees Γ only through σ_eff = Γ/K
    d_dfwhm = eta * dtl_dfwhm + (1.0 - eta) * dtg_dsig / GAUSS_FWHM_TO_SIGMA
    d_deta = tl - tg
    dgam_dgg, dgam_dgl, deta_dq = _tch_slopes(fwhm_g, g, fwhm)
    qq = g / fwhm
    dq_dgl = (1.0 - qq * dgam_dgl) / fwhm
    dq_dgg = -qq * dgam_dgg / fwhm

    omega = eta * tl + (1.0 - eta) * tg
    d_ddt = eta * dtl_ddt + (1.0 - eta) * dtg_ddt
    d_dalpha = eta * dtl_da + (1.0 - eta) * dtg_da
    d_dbeta = eta * dtl_db + (1.0 - eta) * dtg_db
    d_dgg = d_dfwhm * dgam_dgg + d_deta * deta_dq * dq_dgg
    d_dgamma = d_dfwhm * dgam_dgl + d_deta * deta_dq * dq_dgl
    d_dsigma = GAUSS_FWHM_TO_SIGMA * d_dgg
    return omega, d_ddt, d_dalpha, d_dbeta, d_dsigma, d_dgamma

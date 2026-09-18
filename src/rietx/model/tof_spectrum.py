"""What varies with wavelength inside one time-of-flight histogram.

Two quantities live here, and they are together because they are the two
things a white beam makes *functions* where a constant-wavelength experiment
has constants: the **incident spectrum** the moderator delivers, and the
**linear attenuation** of the specimen.

The incident spectrum
---------------------
A time-of-flight bank counts neutrons of every wavelength the moderator emits,
so the number arriving in a channel is the product of the sample's scattering
power and the source's own output at that flight time.  GSAS measures the
latter with a null coherent scatterer (Larson & Von Dreele, 2004, *GSAS —
General Structure Analysis System*, LAUR 86-748, GSAS Technical Manual
PAGE 127, verbatim: *"The incident intensity, I_i, for a time of flight (TOF)
powder diffractometer can be measured by placing a null coherent scatterer such
as vanadium in the normal sample position"*), fits it with one of five
functions, and stores the type in an instrument-parameter file's ``ITYP``
record and the coefficients in its ``ICOFF`` block.

**The argument is the flight time in milliseconds, not a wavelength and not an
energy.**  This is stated three ways and they agree.  The manual, PAGE 128,
verbatim: *"The 'ITYP 1' function is a sum of exponentials of TOF (T) in
milliseconds or 2θ in degrees"*, and again for type 2, *"again TOF is in
milliseconds"*, and again for type 4 on PAGE 129, *"Again T is TOF in
milliseconds"*.  The Chebyshev types get a consistency check of their own from
the manual's own note beside ``X = (2/T) - 1``: *"Given that the usual range of
TOF is 1 to 100 millisec and 2θ is from 2° to 175° then X ranges from about -1
to +1"* — true in milliseconds and false by three orders in microseconds.  And
GSAS-II's transcription writes the conversion in a comment
(``GSASIIpwd.calcIncident``: ``x = xdata/1000.  #expressions are in ms``), with
its reader turning the ``ITYP`` record's window fields into microseconds by
multiplying by 1000 (``GSASIIfiles.GetInstFile``).  Every function here
therefore takes **microseconds** at its public door and converts once, so no
caller has to remember: the unit trap this track carries is that the ``.iparm``
speaks milliseconds while the pattern speaks microseconds.

The five functions, transcribed from PAGE 128-129 (P₁… are 1-based as the
manual numbers them; the arrays here are 0-based, so ``P[k-1]`` is Pₖ):

===== ===================================================================
ITYP  I_i(T), T in ms
===== ===================================================================
0     ``1`` exactly, no coefficients.  PAGE 129, verbatim: *"For constant
      wavelength data with no incident spectrum, a 'ITYP 0' incident
      spectrum is used and has no coefficients; this gives Ii = 1.0 for all
      data points"*.  This is what a reduction that already divided by a
      vanadium spectrum leaves behind, and it is what ISIS GEM writes.
1     ``P₁ + Σ_{k=1..5} P_{2k}·exp(−P_{2k+1}·T^k)`` — a sum of exponentials,
      ≤ 11 coefficients.
2     type 1 with its **second term replaced by a Maxwellian**:
      ``P₁ + P₂·exp(−P₃/T²)/T⁵ + Σ_{k=2..5} P_{2k}·exp(−P_{2k+1}·T^k)``,
      ≤ 11 coefficients.
3     ``Σ_{j=1..12} P_j·T_{j-1}(X)``, X = 2/T − 1 — a 12-term Chebyshev
      polynomial of the first kind.
4     the Maxwellian plus the Chebyshev tail:
      ``P₁ + P₂·exp(−P₃/T²)/T⁵ + Σ_{j=4..12} P_j·T_{j-3}(X)``, X = 2/T − 1,
      ≤ 12 coefficients.
5     type 3 with ``X = T/10`` instead.  PAGE 129, verbatim: *"The 'ITYP 5'
      function is the same as 'TYPE 3' except that X is defined as X =
      T/10"*.
===== ===================================================================

**Cross-checked against GSAS-II, which agrees where it speaks.**
``GSASIIpwd.calcIncident``'s ``IfunAdv`` implements types 1, 2 and 4 (its
``Itypes`` list leaves the 3rd and 5th entries empty and its reader accepts
``Ityp in [1,2,4]``), and its arithmetic is term-for-term the manual's: the
exponential loop ``for i in [1,3,5,7,9]: YI += Icoef[i]*exp(-Icoef[i+1] *
x**((i+1)/2))`` is Σ P_{2k} exp(−P_{2k+1} T^k) with k = (i+1)/2 = 1…5; the
Maxwellian is ``Icoef[1]*exp(-Icoef[2]/x**2)/x**5``; and the Chebyshev arm runs
the standard recurrence from ``Ccof[1] = T`` and adds ``Ccof[i]*Icoef[i+2]`` for
i = 1…9, i.e. Σ_{j=4} P_j T_{j-3}, skipping T₀ because P₁ is already the
constant.  **Nothing was copied**; the two were read and compared.  Types 3 and
5 have no GSAS-II transcription to compare against and rest on the manual
alone, which is recorded rather than glossed.

Where the factor goes
---------------------
GSAS divides the **observed** counts: PAGE 127, verbatim, *"The general
expressions for the intensity of TOF data are I_o = I'_o / W I_i … where I'_o
is the number of counts observed in a channel of width W, I_i is the incident
intensity"*.  ``rietx`` leaves the data exactly as the file gave it and
multiplies the **calculated Bragg** intensity by I_i instead, per channel.
Three consequences, all deliberate:

* the observed pattern, its σ and therefore every weight stay the data's own,
  so Rwp and χ² are computed against counts a person can go and look at;
* the **background is not multiplied**.  It is fitted in the observed space, so
  whatever the spectrum does to it is already in the coefficients the
  background refines; multiplying it as well would apply the shape twice;
* an ``ITYP 0`` bank multiplies by nothing at all rather than by an array of
  ones — :meth:`~rietx.model.forward_tof.CompiledTOFModel.incident_spectrum`
  returns ``None`` there, so a pattern that never had a spectrum is
  bit-identical to the build before this one.

The specimen's attenuation
--------------------------
µ is a function of λ for a neutron because absorption follows the 1/v law while
scattering does not, so a bank spanning 0.4-5 Å spans a factor of ten in the
absorbing part.  :func:`neutron_attenuation_terms` splits it into the two
constants that make it linear in λ, from the formula WP-1132 specifies for the
constant-wavelength case (``docs/wp/1132-neutron-specimen-absorption.md``) over
the Sears table this package already ships:

    µ(λ) = Σᵢ nᵢ·[σ_abs,ᵢ·(λ/1.798) + σ_coh,ᵢ + σ_inc,ᵢ] / V

**This function belongs to WP-1132 and lives here on loan.**  When that WP
lands it should move to ``crystallography/neutron.py`` as
``linear_attenuation_neutron`` beside ``b_coh`` and ``properties``, and this
module should import it; it is here now only because WP-1132 is unscheduled,
its own scope note excludes time of flight, and this arm needs the number.
Nothing in ``refine.py``'s constant-wavelength µ estimator fence was touched.

References
----------
Larson, A. C. & Von Dreele, R. B. (2004). *GSAS — General Structure Analysis
System*, LAUR 86-748, GSAS Technical Manual PAGE 127-129 (the incident
spectrum) and PAGE 134-135 (the powder absorption factor).  Sears, V. F.
(1992). *Neutron News* **3**(3), 26-37 — the cross-sections, through
:mod:`rietx.crystallography.neutron`.
"""

from __future__ import annotations

import numpy as np

from ..backend import get_backend
from ..crystallography.neutron import properties

__all__ = [
    "COEFFICIENT_COUNTS",
    "SPECTRUM_TYPES",
    "THERMAL_WAVELENGTH",
    "incident_spectrum",
    "neutron_attenuation_terms",
    "neutron_linear_attenuation",
]

#: Every ``ITYP`` the GSAS manual defines, and what each one is.  A closed
#: vocabulary read from the manual's PAGE 128-129, and the authority the
#: refusals quote: an ``ITYP`` outside it is refused **by name and by number**
#: rather than treated as 0, because "a spectrum function this reader does not
#: know" and "no spectrum at all" are different claims and only one of them is
#: safe to assume.
SPECTRUM_TYPES: dict[int, str] = {
    0: "no incident spectrum: I_i = 1 for every point, and no coefficients "
       "(the state a reduction that already divided by a vanadium spectrum "
       "leaves behind)",
    1: "a sum of exponentials of the flight time in milliseconds",
    2: "type 1 with its second term replaced by a Maxwellian",
    3: "a 12-term Chebyshev polynomial of the first kind in X = 2/T − 1",
    4: "a Maxwellian plus the Chebyshev tail of type 3",
    5: "type 3 with X = T/10 in place of X = 2/T − 1",
}

#: ``ITYP 10`` is defined by the manual and is **not** in
#: :data:`SPECTRUM_TYPES`, because it is not a function: PAGE 129, verbatim,
#: *"Alternatively, one can use a point-by-point measured incident spectrum,
#: 'ITYP 10', instead of the fitted one; the file containing this spectrum is
#: read along with the corresponding powder pattern"*.  It has no coefficients
#: to carry and names a second file this reader is never handed, so it is
#: refused by name with that reason rather than met with a generic "unknown
#: type".
ITYP_MEASURED = 10

#: How many coefficients each type uses, from the manual's own counts (PAGE
#: 128: *"This function has a maximum of 11 coefficients"* for type 1,
#: *"Again there is a maximum of 11 coefficients"* for type 2; PAGE 129:
#: *"The 'ITYP 3', 'ITYP 4' and 'ITYP 5' functions have a maximum of 12
#: coefficients"*).  These are exact requirements here rather than maxima:
#: GSAS's ``ICOFF`` block is always three records of four numbers, so a file
#: carrying fewer meaningful coefficients writes zeros, and a **list whose
#: length disagrees with the declared type is refused rather than padded** —
#: padding would be a guess about which end the missing ones belong to.
COEFFICIENT_COUNTS: dict[int, int] = {0: 0, 1: 11, 2: 11, 3: 12, 4: 12, 5: 12}

#: Å.  The wavelength of a 2200 m/s neutron, at which Sears tabulates σ_abs.
#: The 1/v law scales it: σ_abs(λ) = σ_abs(1.798 Å)·λ/1.798.
THERMAL_WAVELENGTH = 1.798

#: Number of Chebyshev terms the two polynomial types carry.
_N_CHEBYSHEV = 12


def _as_ms(tof_us):
    """Flight time in **milliseconds**, the unit every ``ITYP`` function takes.

    One conversion, at the module's door, because the pattern's abscissa is in
    microseconds everywhere in this package and the manual's expressions are in
    milliseconds everywhere in GSAS — see the module docstring for the three
    independent statements of that.
    """
    xp = get_backend()
    return xp.asarray(tof_us, dtype=np.float64) / 1000.0


def _exponential_terms(xp, p, t, first_k: int):
    """Σ_{k=first_k..5} P_{2k}·exp(−P_{2k+1}·T^k), with ``p`` 0-based.

    P_{2k} is ``p[2k-1]`` and P_{2k+1} is ``p[2k]``.  The loop bound is a
    constant, not a length: a type-1/2 block is exactly eleven coefficients and
    five exponential slots, and a missing term is written as a zero amplitude
    by the file rather than by a short list.
    """
    out = xp.zeros_like(t)
    for k in range(first_k, 6):
        out = out + p[2 * k - 1] * xp.exp(-p[2 * k] * t ** k)
    return out


def _maxwellian(xp, p, t):
    """P₂·exp(−P₃/T²)/T⁵ — the second term of types 2 and 4.

    The manual, PAGE 128, calls the coefficient it contains a moderator
    temperature: *"The coefficient P3 in this function and the 'ITYP 4'
    function shown below can be used to calculate an effective moderator
    temperature"*.  Nothing here computes that temperature; it is recorded
    because it is what fixes P₃ as the quantity inside the exponential's 1/T²
    and P₂ as the amplitude, i.e. which of the two is which.
    """
    return p[1] * xp.exp(-p[2] / t ** 2) / t ** 5


def _chebyshev_basis(xp, x):
    """T₀(X)…T₁₁(X) by the standard recurrence, as a list of arrays.

    Chebyshev polynomials of the first kind, which the manual names by their
    source (PAGE 128, verbatim: *"a 12 term Chebyschev polynomial of the first
    kind ("Handbook of Mathematical Functions," M. Abramowitz and I.A. Stegun,
    Eds., Ch. 22)"*, with the coefficients *"taken from Table 22.3, p 795"*).
    Table 22.3 lists the *monomial* coefficients of each Tₙ; the three-term
    recurrence Tₙ = 2X·Tₙ₋₁ − Tₙ₋₂ generates the same polynomials and is what
    GSAS-II uses (``Ccof[i] = 2*T*Ccof[i-1]-Ccof[i-2]``).  Evaluating the
    recurrence rather than the monomial sum matters: X reaches ±1, where the
    monomial form of T₁₁ cancels eleven terms of order 1024 to a result of
    order 1.

    Returned as a list rather than stacked so the caller pays for no array it
    does not use, and so this is one expression on every backend.
    """
    # ``full_like(x, 1.0)`` rather than ``ones_like``: the backend op set
    # carries the first and not the second (``backend.api._OP_NAMES``).
    basis = [xp.full_like(x, 1.0), x]
    for _ in range(2, _N_CHEBYSHEV):
        basis.append(2.0 * x * basis[-1] - basis[-2])
    return basis


def _chebyshev_argument(itype: int, xp, t):
    """X for the polynomial types: 2/T − 1 (types 3, 4) or T/10 (type 5).

    The manual, PAGE 128, verbatim: *"The TOF or 2θ (T) is converted to X to
    make the Chebyschev polynomial orthogonal by X = (2/T) - 1"*, with the
    range note *"Given that the usual range of TOF is 1 to 100 millisec … then
    X ranges from about -1 to +1 that is the orthogonal range for this
    function"*.  Type 5's ``X = T/10`` (PAGE 129) covers 0-10 ms on the same
    orthogonal interval, which is what makes it the choice for a short-flight
    -path instrument where 2/T never comes down off its pole.
    """
    return t / 10.0 if itype == 5 else 2.0 / t - 1.0


def incident_spectrum(itype: int, coefficients, tof_us):
    """I_i(T) for one GSAS incident-spectrum type, on a flight-time grid in µs.

    ``coefficients`` are P₁…P_N in the file's order, 0-based here; ``tof_us`` is
    the abscissa in **microseconds** and is converted to milliseconds once,
    inside (module docstring, "The argument is the flight time in
    milliseconds").  Returns an array of the same shape, or the scalar ``1.0``
    for :data:`ITYP 0 <SPECTRUM_TYPES>`.

    Pure: no schema, no instrument, no parameter dictionary.  The refinable
    wiring is :class:`~rietx.schemas.instrument.IncidentSpectrum` and
    :meth:`~rietx.model.forward_tof.CompiledTOFModel.incident_spectrum`; this
    function is the transcription and is what the tests pin against the manual.

    Larson & Von Dreele (2004), LAUR 86-748, GSAS Technical Manual
    PAGE 128-129.
    """
    xp = get_backend()
    if itype == 0:
        if len(coefficients):
            raise ValueError(_type_zero_message(len(coefficients)))
        return 1.0
    want = COEFFICIENT_COUNTS.get(itype)
    if want is None:
        raise ValueError(_unknown_type_message(itype))
    if len(coefficients) != want:
        raise ValueError(
            f"incident_spectrum(): ITYP {itype} uses {want} coefficients and "
            f"{len(coefficients)} were given. GSAS writes the ICOFF block as "
            f"three records of four numbers whatever the type, so a file with "
            f"fewer meaningful coefficients writes zeros; a short list is "
            f"padded here by nobody, because which end the missing ones belong "
            f"to is not stated anywhere.")

    p = [xp.asarray(c, dtype=np.float64) for c in coefficients]
    t = _as_ms(tof_us)

    if itype == 1:
        return p[0] + _exponential_terms(xp, p, t, 1)
    if itype == 2:
        return p[0] + _maxwellian(xp, p, t) + _exponential_terms(xp, p, t, 2)

    x = _chebyshev_argument(itype, xp, t)
    basis = _chebyshev_basis(xp, x)
    if itype == 4:
        # P₁ + the Maxwellian + Σ_{j=4..12} P_j·T_{j-3}: nine Chebyshev terms
        # starting at T₁, because T₀ ≡ 1 is already P₁ and the two would be
        # exactly degenerate.  GSAS-II's ``for i in range(1,10)`` is the same
        # nine terms.
        out = p[0] + _maxwellian(xp, p, t)
        for j in range(4, 13):
            out = out + p[j - 1] * basis[j - 3]
        return out
    # types 3 and 5: Σ_{j=1..12} P_j·T_{j-1}, T₀ included and carrying P₁
    out = xp.zeros_like(t)
    for j in range(1, _N_CHEBYSHEV + 1):
        out = out + p[j - 1] * basis[j - 1]
    return out


def _type_zero_message(n: int) -> str:
    """Why a type 0 carrying coefficients is refused.

    Shared with :class:`~rietx.schemas.instrument.IncidentSpectrum`'s validator
    so the schema and the evaluator make the same complaint about the same
    file: "no spectrum" and "a spectrum whose block is the wrong length" are
    different findings, and the second would send a reader looking for a
    truncation that is not there.
    """
    return (
        f"ITYP 0 takes no coefficients and {n} were given. The manual (PAGE "
        f"129) states it as 'has no coefficients; this gives Ii = 1.0 for all "
        f"data points' — a type 0 carrying numbers is a file whose type and "
        f"whose ICOFF block disagree, not a spectrum to evaluate.")


def _unknown_type_message(itype: int) -> str:
    """Why an ``ITYP`` is refused, naming what the manual does define.

    Separate from its raise sites so the reader and the evaluator say the same
    thing about the same number: an unknown type reaching one of them and not
    the other is how a file gets read as something it is not.
    """
    if itype == ITYP_MEASURED:
        return (
            f"ITYP {ITYP_MEASURED} is a point-by-point *measured* incident "
            f"spectrum, not a fitted function: the manual (PAGE 129) says the "
            f"spectrum lives in a separate file 'read along with the "
            f"corresponding powder pattern', and this reader is handed one "
            f"instrument-parameter file and no second file. There are no "
            f"coefficients to carry and nothing to evaluate. Supply the "
            f"spectrum yourself, or use a reduction that has already divided "
            f"it out (which is what ITYP 0 records).")
    known = ", ".join(str(k) for k in sorted(SPECTRUM_TYPES))
    return (
        f"ITYP {itype} is not an incident-spectrum function the GSAS manual "
        f"defines. It gives five ({known} — PAGE 128-129) plus ITYP "
        f"{ITYP_MEASURED} for a measured spectrum in a separate file. Reading "
        f"an unknown type as 0 would be treating 'a function this build cannot "
        f"evaluate' as 'no spectrum at all', and those two produce patterns "
        f"that differ by two orders of magnitude across a bank.")


# ---------------------------------------------------------------------------
# µ(λ): WP-1132's formula, on loan (see the module docstring)
# ---------------------------------------------------------------------------
def neutron_attenuation_terms(element_counts: dict[str, float],
                              volume: float) -> tuple[float, float]:
    """``(a, b)`` with µ(λ) = a·λ + b in cm⁻¹, λ in Å.

    The split is the physics, not an optimisation: **absorption follows the 1/v
    law and scattering does not**, so µ is exactly affine in λ over a thermal
    bank and the two constants can be frozen once at compile while λ stays a
    per-reflection quantity.  From WP-1132's formula
    (``docs/wp/1132-neutron-specimen-absorption.md``),

        µ(λ) = Σᵢ nᵢ·[σ_abs,ᵢ·(λ/1.798) + σ_coh,ᵢ + σ_inc,ᵢ] / V

    so ``a = Σ nᵢ σ_abs,ᵢ / (1.798·V)`` and ``b = Σ nᵢ (σ_coh,ᵢ + σ_inc,ᵢ) / V``.

    ``element_counts`` maps species to occupancy-weighted atom counts per unit
    cell and ``volume`` is the cell volume in Å³.  σ arrives in barn from
    :func:`rietx.crystallography.neutron.properties` (Sears, 1992, *Neutron
    News* **3**(3), 26-37), and barn/Å³ is cm⁻¹ exactly — 10⁻²⁴ cm² over 10⁻²⁴
    cm³ — which is why no unit constant appears here and why the X-ray twin
    (:func:`rietx.crystallography.attenuation.linear_attenuation`) has none
    either.

    **Not the X-ray table, and the difference is in kind.** WP-1132's own table
    lists it: X-ray µ/ρ goes as λ³ between edges where σ_abs goes as λ¹; it
    rises with Z where the neutron value has no trend in Z at all; and hydrogen
    is nearly transparent to X-rays and one of the strongest neutron
    attenuators there is (σ_inc = 80.27 barn).  Running the X-ray compilation
    on a neutron bank does not give a rough answer, it gives an unrelated one.

    Raises ``KeyError`` for a species Sears does not tabulate — the caller
    decides whether that is a refusal or a skipped correction, exactly as
    ``optimize.qpa`` does for the X-ray case.
    """
    if volume <= 0.0:
        raise ValueError(f"cell volume must be positive, got {volume}")
    absorbing = scattering = 0.0
    for species, count in element_counts.items():
        row = properties(species)
        absorbing += count * row["xs_abs_barn"]
        scattering += count * (row["xs_coh_barn"] + row["xs_inc_barn"])
    return (absorbing / (THERMAL_WAVELENGTH * volume), scattering / volume)


def neutron_linear_attenuation(element_counts: dict[str, float],
                               volume: float, wavelength: float) -> float:
    """µ in cm⁻¹ at one wavelength — :func:`neutron_attenuation_terms` evaluated.

    The constant-wavelength shape of the same number, kept because it is the
    form WP-1132's checklist names (``linear_attenuation_neutron``) and the form
    a published µ is quoted in.  Sears (1992), *Neutron News* **3**(3), 26-37.
    """
    a, b = neutron_attenuation_terms(element_counts, volume)
    return a * wavelength + b

"""A phase's profile coefficients read as a coherent domain size and a Δd/d.

WP-1131's reporting half, and the peer of :mod:`rietx.model.geometry`: that one
turns refined coordinates into bond lengths with esds, this one turns refined
widths into a length and a dimensionless strain with esds.  Both are
**evidence, never a verdict** — nothing here says a domain size is reasonable.

Three rules, all of them borrowed rather than invented:

* **The conversions live in one place and it is not here.**
  :mod:`rietx.model.profiles.caglioti` owns Scherrer and the tanθ law in both
  directions; this module calls them and states no constant of its own.
* **A quantity that cannot be measured is absent, not zero** (WP-1072).  A
  coefficient at its off state, a source with no wavelength and a column that
  measured nothing are three different absences and each names itself in
  ``MicrostructureTerm.unavailable``.
* **The propagation is exact and single-parameter.**  Each reading is a
  function of one coefficient — ``L = (180/π)·K·λ/x`` and
  ``Δd/d = (π/360)·y`` — so J·Cov·Jᵀ is one variance and there is no
  cross-term to drop.  That is *why* the Gaussian and Lorentzian readings are
  reported separately and compared rather than combined into one number: a
  combined size is a function of two correlated columns, and this module would
  then be quoting a covariance it is not given.

**What the size is a size of.**  The phase's *own* coefficient, not
``instrument.profile.x + phases.N.lor_size``: under the instrument ⊕ sample
split the instrument terms are calibrated on a standard and frozen, so the
sample term is the specimen's whole contribution and reading it alone is the
point of the split.  A fit that never calibrated the instrument has put
instrument width into the sample term, and the size that comes back is a lower
bound — which is Scherrer's usual caveat, not a new one.
"""

from __future__ import annotations

import math

from ..schemas.results import MicrostructureTerm, PhaseMicrostructure
from ..schemas.structure import Structure
from .profiles.caglioti import (
    SCHERRER_K,
    apparent_size_from_d_size_coefficient,
    apparent_size_from_size_coefficient,
    microstrain_from_strain_coefficient,
)

#: coefficient name → (kind, whether the stored number is a *variance*).  The
#: Gaussian pair are variances, so the FWHM coefficient behind them is the
#: square root and an esd carries the factor 2 that differentiating it gives.
_TERMS = {
    "lor_size": ("size", False),
    "gauss_size": ("size", True),
    "lor_strain": ("strain", False),
    "gauss_strain": ("strain", True),
}


def _reading(kind: str, coefficient: float, variance: bool,
             sigma: float | None, wavelength: float | None,
             k: float, tof: bool = False) -> tuple[float | None, float | None,
                                                   str | None]:
    """(value, esd, unavailable) for one coefficient.

    ``coefficient`` is the stored number — a FWHM coefficient, or its square
    for the Gaussian pair.  The relative esd is where the two shapes differ and
    it is one line: for a FWHM coefficient ``σ_value/value = σ_c/c``, and for a
    variance ``σ_value/value = σ_v/(2v)``, because the FWHM behind it is √v.
    Both readings are inversely proportional (size) or proportional (strain) to
    that FWHM, so the *relative* esd is the same either way and the sign never
    matters — an esd is a magnitude.

    ``tof`` says the stored size pair is in the **d-space** units a bank holds
    them in (K/L in Å⁻¹, and its square), where the size reads with no
    wavelength at all — the relative esd, and therefore this function's whole
    second half, is unchanged, because L = K/c is inversely proportional to c
    exactly as L = (180/π)·K·λ/c is.
    """
    if not coefficient > 0.0:
        return None, None, "at_zero"
    if kind == "size":
        fwhm_coefficient = math.sqrt(coefficient) if variance else coefficient
        if tof:
            value = apparent_size_from_d_size_coefficient(fwhm_coefficient, k)
        elif wavelength is None or not wavelength > 0.0:
            return None, None, "no_wavelength"
        else:
            value = apparent_size_from_size_coefficient(fwhm_coefficient,
                                                        wavelength, k)
    else:
        fwhm_coefficient = math.sqrt(coefficient) if variance else coefficient
        value = microstrain_from_strain_coefficient(fwhm_coefficient)
    if sigma is None or not sigma >= 0.0:
        return value, None, "not_measured"
    relative = sigma / (2.0 * coefficient) if variance else sigma / coefficient
    return value, value * relative, None


def microstructure_table(structure: Structure, values: dict[str, float], *,
                         wavelength: float | None,
                         esds: dict[str, float] | None = None,
                         k: float = SCHERRER_K,
                         tof: bool = False) -> list[PhaseMicrostructure]:
    """One :class:`PhaseMicrostructure` per phase, in phase order.

    ``values`` is a decoded parameter dict (the forward model's own), ``esds``
    the *physical* esds ``ParameterTable.stderr_physical`` returns — which
    already omits every row that measured nothing, so a missing key here is
    the WP-1110 answer "this column has no esd" and arrives as
    ``unavailable="not_measured"`` rather than as a zero.

    ``wavelength`` is the caller's, because "which emission line" is decided
    once for the whole package in
    :func:`~rietx.optimize.least_squares._longest_line_wavelength` and this
    module must not have a second opinion.  ``None`` is a source that declares
    none: the strains still read, the sizes do not.

    ``tof`` says the values came off a **time-of-flight bank**, where the size
    pair is stored as K/L in Å⁻¹ rather than as a width in deg 2θ
    (:func:`~rietx.model.forward_tof.sample_broadening_terms`).  It changes
    only which inverse is taken: the block's ``wavelength`` is then ``None``
    and stays ``None`` — a bank has no primary wavelength and this module must
    not report one — while all four rows read, because L in Å and Δd/d are
    axis-free.  Until T-3c a bank abstained on both size rows with
    ``no_wavelength``, which was true of the *coefficient* it was handed and is
    not true of the specimen.

    Never raises on a phase whose coefficients are all at zero — the common
    case, since none of them is freed by default — it returns four terms each
    saying ``at_zero``, which is the honest empty state and is not the same
    statement as "no microstructure block".
    """
    esds = esds or {}
    out: list[PhaseMicrostructure] = []
    for ip, phase in enumerate(structure.phases):
        terms: list[MicrostructureTerm] = []
        for name, (kind, variance) in _TERMS.items():
            path = f"phases.{ip}.{name}"
            coefficient = values.get(path)
            if coefficient is None:
                continue
            value, esd, why = _reading(kind, float(coefficient), variance,
                                       esds.get(path), wavelength, k, tof)
            terms.append(MicrostructureTerm(
                path=path, kind=kind, coefficient=float(coefficient),
                value=value, esd=esd, unavailable=why))
        block = PhaseMicrostructure(
            phase_index=ip, phase_name=phase.name,
            wavelength=wavelength, scherrer_k=k, terms=terms)
        block.size_agreement = _agreement(block, "gauss_size", "lor_size")
        block.strain_agreement = _agreement(block, "gauss_strain", "lor_strain")
        out.append(block)
    return out


def _agreement(block: PhaseMicrostructure, numerator: str,
               denominator: str) -> float | None:
    """Gaussian reading ÷ Lorentzian reading, or ``None`` if either is absent.

    WP-1131 Finding 5: rietx registers the Gaussian and Lorentzian halves of
    each mechanism as **independent** columns, where GSAS-II refines one
    magnitude and a mixing coefficient that splits it.  The independent model
    is the more general one and this module does not argue against it — it
    measures the consistency the constrained model would have imposed, which
    was previously unmeasured.  Far from 1 means the two describe different
    specimens and neither is quotable alone.
    """
    top, bottom = block.term(numerator), block.term(denominator)
    if top is None or bottom is None:
        return None
    if top.value is None or bottom.value is None or not bottom.value > 0.0:
        return None
    return top.value / bottom.value

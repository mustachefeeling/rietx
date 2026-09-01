"""X-ray atomic form factors.

f0(k) is the 5-Gaussian parameterisation of Waasmaier & Kirfel (1995),
Acta Cryst. A51, 416-431:

    f0(k) = Σ_{i=1..5} a_i · exp(−b_i k²) + c,     k = sin(θ)/λ  [Å⁻¹]

valid for k ≤ 6 Å⁻¹ — a wider range than the older 4-Gaussian Cromer-Mann
form.  Coefficients are read from the DABAX file ``f0_WaasKirf.dat`` (ESRF
DABAX collection; see ATTRIBUTION.md).

This module is the **angle-dependent, wavelength-independent** half of the
scattering factor.  The anomalous corrections f′ + i·f″ are angle-independent
and wavelength-dependent, live in :mod:`rietx.crystallography.dispersion`,
and are applied by the structure factor rather than here — which is why the
form-factor lookup is keyed by ion (``La3+``) and the dispersion lookup by
element (``La``).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from importlib import resources

import gemmi
import numpy as np

from .._about import DATA_PACKAGE as _DATA_PACKAGE
from ..backend import get_backend

_DATA_FILE = "f0_WaasKirf.dat"


@lru_cache(maxsize=1)
def _load_table() -> dict[str, np.ndarray]:
    """Parse the DABAX file into {species: [a1..a5, c, b1..b5]}."""
    text = (resources.files(_DATA_PACKAGE) / _DATA_FILE).read_text(encoding="utf-8")
    table: dict[str, np.ndarray] = {}
    species: str | None = None
    expecting = False
    for line in text.splitlines():
        if line.startswith("#S"):
            # e.g. "#S  57  La" or "#S  57  La3+"
            parts = line.split()
            species = parts[2] if len(parts) >= 3 else None
            expecting = True
        elif expecting and line.strip() and not line.startswith("#"):
            vals = np.array([float(v) for v in line.split()], dtype=np.float64)
            if species is not None and len(vals) == 11:
                table[species] = vals
            expecting = False
    if not table:
        raise RuntimeError("failed to parse Waasmaier-Kirfel coefficient table")
    return table


def normalize_species(species: str) -> str:
    """Map a CIF type symbol to a table key, falling back to the neutral atom.

    ``"La3+"`` stays ``"La3+"`` if tabulated; ``"LA"`` → ``"La"``;
    ``"O2-"`` falls back to ``"O"`` only if the ion is missing from the table.
    """
    table = _load_table()
    s = species.strip()
    if s in table:
        return s
    m = re.match(r"^([A-Za-z]{1,2})(\d*[+-])?$", s)
    if m:
        elem = m.group(1).capitalize()
        ion = m.group(2) or ""
        for candidate in (elem + ion, elem):
            if candidate in table:
                return candidate
    raise KeyError(f"no Waasmaier-Kirfel coefficients for species {species!r}")


#: A well-formed ion label: 1-2 letters, an optional explicit charge digit
#: (``"1"`` in ``"Ag1+"`` is written out, never omitted, in this table's own
#: keys), then the sign.  Deliberately the same shape :func:`normalize_species`
#: parses, so a label this does not match is either a bare element (no
#: fallback is possible) or malformed (``normalize_species`` already raises on
#: those, which is not this function's job to repeat).
_ION_RE = re.compile(r"^([A-Za-z]{1,2})(\d*)([+-])$")


@dataclass(frozen=True)
class SpeciesFallback:
    """One ion :func:`normalize_species` could not find, reported instead of
    swallowed (issue #202).

    ``true_electrons`` is Z minus the signed formal charge — the ion's own
    electron count, derived rather than tabulated so nothing here duplicates
    a second copy of periodic-table data.  ``returned_electrons`` is what the
    fallback actually supplies: ``f0(element, k=0)`` of the neutral atom the
    substitution used, which is *approximately* Z (the Gaussian fit reproduces
    the sum rule to a few parts in 10⁴, not exactly — ``f0("Y", 0) ==
    38.980795``, not ``39``) and is read off the same table `f0` reads rather
    than assumed to equal Z, so the two are on the same footing as the number
    a real refinement would see.
    """

    species: str            # the raw label, e.g. "Y3+"
    element: str            # the neutral atom substituted, e.g. "Y"
    charge: int             # signed formal charge parsed from `species`
    true_electrons: float   # Z - charge
    returned_electrons: float  # f0(element, 0), what the fallback supplies

    @property
    def delta_frac(self) -> float:
        """Fractional error the substitution puts on the scattering power."""
        return (self.returned_electrons - self.true_electrons) / self.true_electrons


def detect_fallback(species: str) -> SpeciesFallback | None:
    """Whether normalizing ``species`` silently substituted the neutral atom.

    ``None`` covers every case that is *not* the #202 defect: a bare element
    (``"Fe"``), an ion the table carries in full (``"O2-"``), and a malformed
    label — ``normalize_species`` already raises cleanly on those, and this
    function never widens that: it only re-derives, from the same regex
    grammar, whether a **well-formed** ion's charge survived resolution.  Any
    exception ``normalize_species`` raises here (an element absent from the
    table under any form) is swallowed the same way, because a totally
    unknown species is a different, already-loud failure — this function's
    only job is the quiet one.
    """
    s = species.strip()
    m = _ION_RE.match(s)
    if not m:
        return None
    elem, digits, sign = m.groups()
    elem = elem.capitalize()
    charge = int(digits or "1") * (1 if sign == "+" else -1)
    try:
        resolved = normalize_species(s)
    except KeyError:
        return None
    if resolved != elem:
        return None  # the ion itself is tabulated -- no fallback happened
    z = gemmi.Element(elem).atomic_number
    true_electrons = float(z - charge)
    returned_electrons = float(f0(elem, np.array([0.0]))[0])
    return SpeciesFallback(species=s, element=elem, charge=charge,
                           true_electrons=true_electrons,
                           returned_electrons=returned_electrons)


def f0(species: str, k: np.ndarray) -> np.ndarray:
    """Elastic form factor at k = sin(θ)/λ (Å⁻¹).

    Waasmaier & Kirfel (1995) Eq. (1): f0(k) = Σ a_i exp(−b_i k²) + c.
    """
    xp = get_backend()
    coeffs = _load_table()[normalize_species(species)]
    a = xp.asarray(coeffs[0:5], dtype=np.float64)
    c = coeffs[5]
    # lifted, not left as a numpy view: b sits on the *left* of the broadcast
    # product below, which torch will not accept against a traced operand
    b = xp.asarray(coeffs[6:11], dtype=np.float64)
    k2 = xp.asarray(k, dtype=np.float64) ** 2
    # b ⊗ k² as a broadcast product (np.outer cannot take a traced operand)
    return xp.einsum("i,in->n", a, xp.exp(-(b[:, None] * k2[None, :]))) + c

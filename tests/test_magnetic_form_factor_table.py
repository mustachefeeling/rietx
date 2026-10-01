"""The magnetic form-factor table as a whole: self-consistency, a fingerprint, the rows a fix touched.

``tests/test_magnetic.py`` pins the dipole expression and a handful of rows. Until 2026-10-01 nothing compared the
*whole* table with anything, and the Ni³⁺ pair had been CrysFML's rather than Brown's since the table was written
(issue #593). The tests here need no second copy of the table:

* **physics the coefficients must obey** (checks A-D of the verification), derived from the small-s expansions of
  Brown's eq. 4.4.5.1, j₀(x) = 1 − x²/6 + … and j₂(x) = x²/15 + …, with x = 4πs·r. They fail on a wrong prefactor,
  a ⟨j₂⟩ row taken from another ion, a transposed exponent, an ion-shifted pair and a wrong charge label;
* **a fingerprint** of every coefficient, which fails on any edit to any digit, including the one-digit exponent
  change that none of the physics checks can see;
* **the two rows the fix replaced**, as printed, so the fingerprint is not the only thing that knows them.

The bands below were measured on the ITC Vol. C 2004 print (not on this table) on 2026-10-01; the probe scripts and
their logs are kept with the verification record, outside this repository.
"""

from __future__ import annotations

import hashlib
import math

import gemmi
import numpy as np
import pytest

from rietx.crystallography.magnetic import form_factor as ff
from rietx.crystallography.magnetic.scattering import _three_gaussian


def _block(ion: str) -> str:
    z = gemmi.Element(ff._element(ion)[0]).atomic_number
    if 21 <= z <= 29:
        return "3d"
    if 39 <= z <= 46:
        return "4d"
    if 58 <= z <= 71:
        return "4f"
    return "5f"


def _r2_from_j0(c) -> float:
    """⟨r²⟩ in Å² from the ⟨j₀⟩ slope: ⟨j₀⟩ ≈ 1 − (Aa + Bb + Cc)s², and 1 − (4πs)²⟨r²⟩/6."""
    A, a, B, b, C, cc, _ = c
    return 3.0 * (A * a + B * b + C * cc) / (8.0 * math.pi ** 2)


def _r2_from_j2(c) -> float:
    """⟨r²⟩ in Å² from the ⟨j₂⟩ amplitude: ⟨j₂⟩ ≈ (A + B + C + D)s², and (4πs)²⟨r²⟩/15."""
    A, _, B, _, C, _, D = c
    return 15.0 * (A + B + C + D) / (16.0 * math.pi ** 2)


# ============================================================= A. normalisation

def test_every_j0_row_is_normalised_to_browns_fit_residual():
    """A + B + C + D = 1 to Brown's own residual, 0.0023 at worst (Ti, Ti⁺, Cr⁺, Co, Rh in the print).

    Catches a prefactor digit off by ≥ 0.003 (Mn²⁺ A 0.4220 → 0.4420 gives 1.019). It cannot see an exponent.
    """
    bad = {ion: round(sum(ff._J0[ion][::2]), 4) for ion in ff._J0 if abs(sum(ff._J0[ion][::2]) - 1.0) > 2.5e-3}
    assert bad == {}


# ============================================================= B. the j0/j2 pair

#: median and sd of ⟨r²⟩(⟨j₀⟩) / ⟨r²⟩(⟨j₂⟩) per block over the 95 print pairs. Brown fitted the two orders
#: separately, over a finite range, so the ratio is not 1; its spread is the fit's.
_PAIR_BAND = {"3d": (1.0197, 0.0276), "4d": (1.0416, 0.0151), "4f": (0.9953, 0.0085), "5f": (1.0095, 0.0098)}


def test_each_ions_j0_and_j2_rows_describe_the_same_radial_extent():
    """Both rows of an ion give ⟨r²⟩; the ratio must sit within 4 sd of its block.

    4 sd, not 3: at 3 sd one correct print pair (Nd²⁺, 1.0215 against an edge of 1.0208) is flagged. At 4 sd
    every planted swap is still caught: Tb³⁺ ⟨j₂⟩ ← Gd³⁺ 0.946, Fe³⁺ ← Fe²⁺ 0.817, Mn³⁺ ← Mn⁴⁺ 1.141,
    Ni³⁺ ← Ni⁴⁺ 1.154, a transposed exponent (Mn²⁺ a 17.684 → 71.684) 3.06. It cannot see a wrong *pair*: the old
    Ni³⁺ rows gave 0.992. That is what the ionisation test is for.
    """
    bad = {}
    for ion, c2 in ff._J2.items():
        med, sd = _PAIR_BAND[_block(ion)]
        r = _r2_from_j0(ff._J0[ion]) / _r2_from_j2(c2)
        if abs(r - med) > 4.0 * sd:
            bad[ion] = round(r, 4)
    assert bad == {}


# ============================================================= C. ionisation, 3d

@pytest.mark.parametrize("order", [0, 2])
def test_3d_ions_contract_by_the_usual_step_per_unit_of_charge(order):
    """⟨r²⟩ falls 12-20 % from 2+ to 3+ and 10-16 % from 3+ to 4+, for every 3d element, from either order.

    Measured on the print: 2+→3+ −14 to −19 %, 3+→4+ −11 to −15 %, Ti to Cu. The CrysFML Ni³⁺ rows this table
    carried until issue #593 gave −28 % then +0.7 % (⟨j₀⟩) and −25 % then 0.0 % (⟨j₂⟩): a pair internally
    consistent, an ion out of place.
    """
    table, r2 = (ff._J0, _r2_from_j0) if order == 0 else (ff._J2, _r2_from_j2)
    bands = {(2, 3): (-0.20, -0.12), (3, 4): (-0.16, -0.10)}
    bad, n = [], 0
    for el in ("Ti", "V", "Cr", "Mn", "Fe", "Co", "Ni", "Cu"):
        for (q1, q2), (lo, hi) in bands.items():
            k1, k2 = f"{el}{q1}+", f"{el}{q2}+"
            if k1 in table and k2 in table:
                n += 1
                step = r2(table[k2]) / r2(table[k1]) - 1.0
                if not lo <= step <= hi:
                    bad.append((k1, k2, round(100 * step, 1)))
    assert n == 15
    assert bad == []


# ============================================================= D. lanthanide contraction

_LN = ("Ce", "Pr", "Nd", "Pm", "Sm", "Eu", "Gd", "Tb", "Dy", "Ho", "Er", "Tm", "Yb")


def test_the_lanthanide_contraction_holds_except_where_it_is_known_not_to():
    """⟨r²⟩ falls with Z within each charge, and a 2+ ion is larger than its own 3+.

    Two rows break it, and both are known (issue #593):

    * **"Ce2+"** (1.291 a.u.) is smaller than Nd²⁺ (1.372). Brown's row labelled Ce²⁺ is Freeman & Desclaux's
      Ce³⁺: it reproduces their Ce³⁺ values at Brown's printed fit error in all four orders, and they computed no
      Ce²⁺. The label is a misprint in the print and in Brown's file alike.
    * **Pr³⁺** (1.076 a.u.) is smaller than Nd³⁺ (1.114). Its row is a fit to a non-relativistic calculation
      (it matches Lisher & Forsyth's Pr³⁺ to 0.05 %), so it is on a different footing from its Dirac-Fock neighbours.

    The test pins exactly those two. A fix to either must update this set; a new violation fails it.
    """
    violations = set()
    for q in (2, 3):
        seq = [(f"{el}{q}+", _r2_from_j0(ff._J0[f"{el}{q}+"])) for el in _LN if f"{el}{q}+" in ff._J0]
        for (k1, v1), (k2, v2) in zip(seq, seq[1:]):
            if not v2 < v1:
                violations.add((k1, k2))
    for el in _LN:
        if f"{el}2+" in ff._J0 and f"{el}3+" in ff._J0:
            if not _r2_from_j0(ff._J0[f"{el}2+"]) > _r2_from_j0(ff._J0[f"{el}3+"]):
                violations.add((f"{el}2+", f"{el}3+"))
    assert violations == {("Ce2+", "Nd2+"), ("Pr3+", "Nd3+")}


# ============================================================= H. smoke test on the fit range

def test_every_row_is_well_behaved_inside_browns_fit_range():
    """Inside s ≤ 1.2 (4f) or 1.5 Å⁻¹ (others), ⟨j₀⟩ stays in [−0.1, 1.003] and ⟨j₂⟩ in [−0.01, 0.6].

    A weak test (a sign error on a small term passes it) kept as a smoke test against a factor-of-ten slip.
    Beyond the range the fits are not constrained: Cr²⁺'s a = −0.005 and D = −1.2218 cancel inside it and
    diverge past s ≈ 3.
    """
    bad = []
    for ion in ff._J0:
        smax = 1.2 if _block(ion) == "4f" else 1.5
        s = np.linspace(0.0, smax, 151)
        v0 = np.asarray(ff.j0(ion, s))
        if not (v0.min() >= -0.1 and v0.max() <= 1.003):
            bad.append((ion, "j0", float(v0.min()), float(v0.max())))
        if ff.has_j2(ion):
            v2 = np.asarray(ff.j2(ion, s))
            if not (v2.min() >= -0.01 and v2.max() <= 0.6):
                bad.append((ion, "j2", float(v2.min()), float(v2.max())))
    assert bad == []


# ============================================================= the fingerprint

#: SHA-256 of every coefficient, verified 2026-10-01 against ITC Vol. C (2004) Tables 4.4.5.1-4.4.5.8,
#: pp. 454-457 (page image) and against P. J. Brown's data file (2013-09-19), row by row as curves on Brown's fit
#: ranges (issue #593). Any edit to any digit fails here. Re-derive it only together with a stated
#: verification of the edited rows, and say which in the commit.
_TABLE_SHA256 = "7e847d79888af7a550b3ec6fae580ea3c968466bfbb87d2f76e0ac4df6473b13"


def _canonical_table() -> bytes:
    lines = [f"{name} {ion} {tuple(repr(float(x)) for x in c)}"
             for name, table in (("j0", ff._J0), ("j2", ff._J2)) for ion, c in sorted(table.items())]
    return "\n".join(lines).encode()


def test_the_table_is_the_verified_table():
    assert (len(ff._J0), len(ff._J2)) == (96, 95)
    assert hashlib.sha256(_canonical_table()).hexdigest() == _TABLE_SHA256


# ============================================================= the rows the fix replaced

def test_ni3_rows_are_browns_as_printed():
    """Ni³⁺, ITC Vol. C (2004) Table 4.4.5.1 p. 454 (⟨j₀⟩) and Table 4.4.5.5 p. 456 (⟨j₂⟩), as printed.

    These replaced CrysFML's rows (via ``periodictable`` 2.1.0), whose ⟨j₂⟩ was Brown's Ni⁴⁺ row. With the old pair
    |F_M|² came out 6 % high at s = 0.2 and 25 % high at s = 0.5 Å⁻¹, so a fitted Ni³⁺ moment came out low by a few
    per cent. The ⟨j₂⟩ row keeps the print's order of the B and C terms; Brown's data file has them the other way
    round, which leaves the curve unchanged.
    """
    j0, j2 = ff.coefficients("Ni3+")
    assert j0 == (0.0012, 35.000, 0.3468, 11.987, 0.6667, 4.252, -0.0148)
    assert j2 == (1.4683, 8.671, 0.1794, 1.106, 1.1068, 3.257, -0.0023)
    assert j2 != ff.coefficients("Ni4+")[1]


def test_v_j2_is_the_printed_row():
    """V ⟨j₂⟩, Table 4.4.5.5 p. 456. CrysFML carries a refit within 5 × 10⁻⁴ of it in f; the print is what is cited."""
    assert ff.coefficients("V")[1] == (3.7600, 21.831, 2.4026, 7.546, 0.4464, 2.663, 0.0017)


def test_the_two_evaluators_of_the_table_agree_on_every_row():
    """``form_factor`` and the forward model's ``scattering`` each evaluate the same tuples; pin them together."""
    s = np.linspace(0.0, 1.5, 10)
    for ion in ff._J0:
        c0, c2 = ff.coefficients(ion)
        np.testing.assert_allclose(_three_gaussian(c0, s * s, stol2_factor=False), np.asarray(ff.j0(ion, s)),
                                   rtol=0, atol=1e-14)
        if c2 is not None:
            np.testing.assert_allclose(_three_gaussian(c2, s * s, stol2_factor=True), np.asarray(ff.j2(ion, s)),
                                       rtol=0, atol=1e-14)

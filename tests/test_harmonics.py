"""crystallography/harmonics.py: the symmetrised harmonics of WP-1960's texture correction."""

import json
from pathlib import Path

import gemmi
import numpy as np
import pytest

from rietx.crystallography import harmonics as H
from rietx.crystallography.symmetry import complete_cell, free_cell_names, rotation_matrices

DATA = Path(__file__).parent / "data"

#: One setting per Laue class, the three monoclinic axes and both rhombohedral-axes classes.
CLASSES = {
    "-1": "P -1", "2/m unique a": "P 2/m 1 1", "2/m unique b": "P 1 2/m 1",
    "2/m unique c": "P 1 1 2/m", "mmm": "P m m m", "4/m": "P 4/m", "4/mmm": "P 4/m m m",
    "-3 hexagonal axes": "P -3", "-3 rhombohedral axes": "R -3:R", "-3m1": "P -3 m 1",
    "-31m": "P -3 1 m", "-3m rhombohedral axes": "R -3 m:R", "6/m": "P 6/m",
    "6/mmm": "P 6/m m m", "m-3": "P m -3", "m-3m": "P m -3 m",
}

#: Generic values for whichever cell parameters a setting leaves free.
FREE = {"a": 5.1, "b": 6.3, "c": 7.4, "alpha": 82.0, "beta": 97.0, "gamma": 104.0}


def generic_cell(sg: gemmi.SpaceGroup, scale: float = 1.0) -> tuple[float, ...]:
    values = {name: FREE[name] * (scale if name in "abc" else 1.0)
              for name in free_cell_names(sg)}
    if sg.ext == "R":
        values["alpha"] = 55.0
    return tuple(complete_cell(sg, values).values())


def directions(hkl, basis, cell):
    return H.reflection_directions(hkl, basis.rule, cell)


def test_real_harmonics_are_orthonormal_over_the_sphere():
    x, w = np.polynomial.legendre.leggauss(40)
    beta = np.linspace(0.0, 2 * np.pi, 80, endpoint=False)
    z = np.repeat(x, beta.size)
    s = np.sqrt(1.0 - z * z)
    u = np.column_stack([s * np.cos(np.tile(beta, x.size)), s * np.sin(np.tile(beta, x.size)), z])
    weight = np.repeat(w, beta.size) * (2 * np.pi / beta.size)
    for degree in range(0, 11):
        y = H.real_harmonics(degree, u)
        gram = (y * weight[:, None]).T @ y
        assert np.allclose(gram, np.eye(2 * degree + 1), atol=1e-12), degree


def test_real_harmonics_carry_no_condon_shortley_phase():
    # Bunge 14.39: P̄_1^1 = +(√3/2)·sin φ, so the cos β function is positive on +x.
    y = H.real_harmonics(1, np.array([[1.0, 0.0, 0.0]]))[0]
    assert y[2] == pytest.approx(np.sqrt(3.0 / (4.0 * np.pi)), rel=1e-15)
    # And the n = 0 function is √((2l+1)/4π)·P_l at the pole (Bunge 14.54).
    for degree in (2, 4, 6, 8):
        pole = H.real_harmonics(degree, np.array([[0.0, 0.0, 1.0]]))[0]
        assert pole[degree] == pytest.approx(np.sqrt((2 * degree + 1) / (4 * np.pi)), rel=1e-14)
        assert np.allclose(np.delete(pole, degree), 0.0, atol=1e-15)


@pytest.mark.parametrize("label", sorted(CLASSES))
def test_counts_follow_the_character_formula(label):
    sg = gemmi.SpaceGroup(CLASSES[label])
    cell = generic_cell(sg)
    basis = H.texture_basis(sg.xhm(), 12, cell)
    rots = H.frame_rotations(rotation_matrices(sg), basis.rule, cell)
    omega = np.arccos(np.clip([(np.trace(q) - 1.0) / 2.0 for q in rots], -1.0, 1.0))
    for degree in range(2, 13, 2):
        chi = [2 * degree + 1 if w < 1e-9 else np.sin((2 * degree + 1) * w / 2) / np.sin(w / 2)
               for w in omega]
        expected = round(float(np.mean(chi)))
        assert sum(t.degree == degree for t in basis.terms) == expected, (label, degree)


def _all_settings():
    return [sg for sg in gemmi.spacegroup_table()]


@pytest.mark.parametrize("sg", _all_settings(), ids=lambda sg: sg.xhm())
def test_every_setting_is_invariant_and_spans_the_orbit_average(sg):
    """The Rᵀ check: the orbit average of any harmonic under h → Rᵀh is in the span.

    The untransposed action is a group too, so a basis built from it has the
    right dimension in every class (module docstring).  Only the orbit average
    computed from the hkl action itself can tell them apart.
    """
    cell = generic_cell(sg)
    basis = H.texture_basis(sg.xhm(), 6, cell)
    # Centring repeats each rotation once per translation; the action needs it once.
    rots = np.unique(np.rint(rotation_matrices(sg)).astype(int), axis=0)
    rng = np.random.default_rng(1960)
    hkl = rng.integers(-4, 5, size=(40, 3))
    hkl = hkl[np.any(hkl != 0, axis=1)]
    k = basis.at_reflections(hkl, cell)
    for r in rots:
        image = hkl @ r  # rows: (Rᵀh)ᵀ = hᵀR
        assert np.allclose(basis.at_reflections(image, cell), k, atol=1e-10)
    for degree in (2, 4, 6):
        coef = rng.normal(size=2 * degree + 1)
        average = np.mean([H.real_harmonics(degree, directions(hkl @ r, basis, cell)) @ coef
                           for r in rots], axis=0)
        cols = [i for i, t in enumerate(basis.terms) if t.degree == degree]
        if not cols:
            assert np.allclose(average, 0.0, atol=1e-10)
            continue
        fit, *_ = np.linalg.lstsq(k[:, cols], average, rcond=None)
        assert np.allclose(k[:, cols] @ fit, average, atol=1e-9), degree


def test_the_untransposed_action_is_not_invariant():
    """The guard above can fail: under h → Rh a hexagonal basis is not invariant."""
    sg = gemmi.SpaceGroup("P 6/m m m")
    cell = generic_cell(sg)
    basis = H.texture_basis(sg.xhm(), 6, cell)
    hkl = np.array([[1, 2, 3], [2, 1, 1], [3, 0, 2]])
    k = basis.at_reflections(hkl, cell)
    worst = max(np.max(np.abs(basis.at_reflections(hkl @ np.rint(r).astype(int).T, cell) - k))
                for r in rotation_matrices(sg))
    assert worst > 1e-2


@pytest.mark.parametrize("label", sorted(CLASSES))
def test_the_basis_does_not_depend_on_the_free_cell_values(label):
    sg = gemmi.SpaceGroup(CLASSES[label])
    one = H.texture_basis(sg.xhm(), 8, generic_cell(sg))
    two = H.texture_basis(sg.xhm(), 8, generic_cell(sg, scale=1.37))
    assert one.names == two.names
    for a, b in zip(one.coefficients, two.coefficients):
        assert np.allclose(a, b, atol=1e-12)


def test_the_cubic_functions_meet_bunges_printed_values():
    # Bunge (1982) 14.284-14.287 print |K_l(100)| to six decimals, within half a unit.
    cell = (5.0, 5.0, 5.0, 90.0, 90.0, 90.0)
    basis = H.texture_basis("P m -3 m", 10, cell)
    k = basis.at_reflections(np.array([[1, 0, 0]]), cell)[0]
    printed = {"c4_1": 0.646360, "c6_1": 0.359601, "c8_1": 0.835193, "c10_1": 0.531858}
    for name, value in printed.items():
        assert abs(k[basis.names.index(name)]) == pytest.approx(value, abs=1.5e-6)


def test_m3_has_the_term_gsas2_lacks():
    cell = (5.0, 5.0, 5.0, 90.0, 90.0, 90.0)
    m3 = H.texture_basis("P m -3", 6, cell)
    m3m = H.texture_basis("P m -3 m", 6, cell)
    assert m3.names == ("c4_1", "c6_1", "c6_2")
    assert m3m.names == ("c4_1", "c6_1")
    for name in m3m.names:  # m-3 shares m-3m's functions, as GSAS-II's are
        i, j = m3.names.index(name), m3m.names.index(name)
        assert np.allclose(m3.coefficients[i], m3m.coefficients[j], atol=1e-12)


def test_the_order_is_even_and_at_least_two():
    cell = (5.0, 5.0, 7.0, 90.0, 90.0, 90.0)
    for bad in (0, 1, 3, 5):
        with pytest.raises(ValueError, match="even and at least 2"):
            H.texture_basis("P 4/m m m", bad, cell)
    assert H.lowest_order("P m -3 m") == 4
    assert H.lowest_order("P m -3") == 4
    assert H.lowest_order("P -1") == 2
    assert H.texture_basis("P m -3 m", 2, (5.0,) * 3 + (90.0,) * 3).terms == ()


def test_names_follow_gsas2():
    cell = generic_cell(gemmi.SpaceGroup("P -3"))
    assert H.texture_basis("P -3", 4, cell).names == (
        "c2_0", "c4_neg3", "c4_0", "c4_3")
    cell = generic_cell(gemmi.SpaceGroup("P -3 1 m"))
    assert H.texture_basis("P -3 1 m", 4, cell).names == ("c2_0", "c4_0", "c4_3")


# ----------------------------------------------------------------------
# GSAS-II 5.8.4's golden (tests/data/gsas2_sh_texture.json)
# ----------------------------------------------------------------------
#: Classes where GSAS-II puts one coefficient on cos nβ + sin nβ, of norm² 2.
_MIRROR_FREE = {"-1", "2/m", "4/m", "3", "3R", "6/m"}

#: GSAS-II's pytexture is single precision: 7.4e-7 measured, on values of order 1.
_SINGLE = 2e-6


def _golden():
    with open(DATA / "gsas2_sh_texture.json", encoding="utf-8") as fh:
        return json.load(fh)["cases"]


def _gsas2_norm(laue: str, n: int) -> float:
    return np.sqrt(2.0) if laue in _MIRROR_FREE and n != 0 else 1.0


def _parse(name: str) -> tuple[int, int]:
    degree, n = name.strip("C()").split(",")
    return int(degree), int(n)


@pytest.mark.parametrize("case", _golden(), ids=lambda c: c["label"])
def test_each_invariant_gsas2_function_is_ours_divided_by_its_norm(case):
    cell = tuple(case["cell"])
    basis = H.texture_basis(CLASSES[case["label"]], 8, cell)
    k = basis.at_reflections(np.array(case["hkl"]), cell)
    names = [H.term_name(*_parse(g)) for g in case["names"]]
    assert set(names) <= set(basis.names)
    compared = 0
    for gname, name, row in zip(case["names"], names, case["kcl"]):
        if gname in case["noninvariant"]:
            continue
        norm = _gsas2_norm(case["laue"], _parse(gname)[1])
        assert np.allclose(np.array(row), norm * k[:, basis.names.index(name)], atol=_SINGLE)
        compared += 1
    # Every case keeps its n = 0 terms, except rhombohedral axes, where none survive.
    assert compared > 0 or case["laue"] in ("3R", "3mR")


@pytest.mark.parametrize("case", [c for c in _golden() if not c["noninvariant"]],
                         ids=lambda c: c["label"])
def test_gsas2s_multiplier_is_ours_through_the_conversion(case):
    """P under GSAS-II's `Bragg` (ψ = 90°) is rietx's `bragg_brentano` (ψ = 0°).

    C_rietx = C_GSAS·‖K_GSAS‖·P_l(0), WP-1960 § Pinned by Task 1.  Under
    `Debye` GSAS-II's ψ is θ, which no rietx geometry has; the sample
    harmonic at that ψ checks the rest of the formula.
    """
    cell = tuple(case["cell"])
    basis = H.texture_basis(CLASSES[case["label"]], 8, cell)
    k = basis.at_reflections(np.array(case["hkl"]), cell)
    p_bragg = np.ones(len(case["hkl"]))
    p_debye = np.ones(len(case["hkl"]))
    cos_psi = np.cos(np.radians(case["psi"]["Debye"]))
    for gname, c_gsas in case["coefficients"].items():
        degree, n = _parse(gname)
        legendre = np.polynomial.legendre.Legendre.basis(degree)
        c = c_gsas * _gsas2_norm(case["laue"], n)
        column = (4 * np.pi / (2 * degree + 1)) * k[:, basis.names.index(H.term_name(degree, n))]
        k_sample = np.sqrt((2 * degree + 1) / (4 * np.pi))
        p_bragg += c * legendre(0.0) * column * k_sample * legendre(1.0)
        p_debye += c * column * k_sample * legendre(cos_psi)
    assert np.allclose(p_bragg, case["p"]["Bragg"], atol=_SINGLE * 10)
    assert np.allclose(p_debye, case["p"]["Debye"], atol=_SINGLE * 10)

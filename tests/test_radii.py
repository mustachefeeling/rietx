"""Shannon (1976) ionic/crystal radii and Pyykkö & Atsumi (2009) covalent radii.

The spot values below are written out from the printed pages, not read from
the bundled files, so a corrupted or truncated table fails here instead of
agreeing with itself. Three of them are cells where a widely used digital copy
is wrong, so a table rebuilt from that copy fails too. The whole-file checks
are Shannon's own relation between his two scales and the printed row counts,
each with an arm showing it can fail.
"""

from __future__ import annotations

from collections import Counter
from importlib.resources import files

import pytest

from rietx.crystallography import radii
from rietx.crystallography.radii import IonicRadius, covalent_radius, ionic_radius


def _text(name: str) -> str:
    return (files("rietx.data") / name).read_text(encoding="utf-8")


def _shannon_cells(text: str) -> list[list[str]]:
    return [line.split() for line in text.splitlines()
            if line.strip() and not line.lstrip().startswith("#")]


# --- spot rows against the page ---------------------------------------------
#
# (species, cn, spin, CR, IR, flags), from Shannon (1976) Table 1, pp. 752-753,
# each read off the page image. The first three are where a digital copy
# disagrees with the page: the Imperial College database prints Cr2+ VI HS as
# R*, and Wikipedia's "Ionic radius" gives Pa3+ VI CR 1.16 and Gd3+ VI IR
# 0.935.
_PAGE_ROWS = [
    ("Cr2+", "VI", "HS", 0.94, 0.80, "R"),       # Imperial DB: R*
    ("Pa3+", "VI", None, 1.18, 1.04, "E"),       # Wikipedia CR: 1.16
    ("Gd3+", "VI", None, 1.078, 0.938, "R"),     # Wikipedia IR: 0.935
    ("Cs+", "XII", None, 2.02, 1.88, ""),
    ("Cu2+", "IVSQ", None, 0.71, 0.57, "*"),
    ("Fe3+", "VI", "HS", 0.785, 0.645, "R*"),
    ("Mn3+", "VI", "LS", 0.72, 0.58, "R"),
    ("N5+", "III", None, 0.044, -0.104, ""),     # the one row off the 0.14 rule
    ("No2+", "VI", None, 1.24, 1.1, "E"),        # IR printed with one decimal
    ("Ni3+", "VI", "LS", 0.70, 0.56, "R*"),
    ("O2-", "VI", None, 1.26, 1.40, ""),         # the scale's own anchor
    ("Sb3+", "V", None, 0.94, 0.80, ""),         # IR(V) > IR(VI) 0.76, printed so
    ("Zr4+", "VIII", None, 0.98, 0.84, "*"),
]


@pytest.mark.parametrize("species, cn, spin, cr, ir, flags", _PAGE_ROWS)
def test_shannon_rows_match_the_printed_page(species, cn, spin, cr, ir, flags):
    ionic = ionic_radius(species, cn, spin=spin)
    crystal = ionic_radius(species, cn, spin=spin, kind="crystal")
    assert (ionic.radius, ionic.crystal_radius, ionic.flags) == (ir, cr, flags)
    assert (crystal.radius, crystal.ionic_radius, crystal.kind) == (cr, ir, "crystal")


def test_the_digital_copies_errors_are_not_in_the_table():
    """The three cells where a copy is wrong, stated as the wrong value."""
    assert ionic_radius("Cr2+", 6, spin="HS").flags != "R*"
    assert ionic_radius("Pa3+", 6, kind="crystal").radius != 1.16
    assert ionic_radius("Gd3+", 6).radius != 0.935


# (element, r1 pm, r2 pm or None), Pyykkö & Atsumi (2009a) Fig. 2 and
# (2009b) Fig. 3, read off the figures.
_PYYKKO = [
    ("H", 32, None), ("B", 85, 78), ("C", 75, 67), ("O", 63, 57),
    ("Na", 155, 160),        # r2 > r1, one of the paper's "apparent anomalies"
    ("Fe", 116, 109), ("La", 180, 139), ("Cn", 122, 137), ("Og", 157, None),
]


@pytest.mark.parametrize("element, r1, r2", _PYYKKO)
def test_pyykko_radii_match_the_printed_figures(element, r1, r2):
    assert covalent_radius(element) == pytest.approx(r1 / 100, abs=1e-12)
    if r2 is None:
        with pytest.raises(KeyError, match=f"no r2 for {element}"):
            covalent_radius(element, order=2)
    else:
        assert covalent_radius(element, order=2) == pytest.approx(r2 / 100, abs=1e-12)


# --- whole-table checks -----------------------------------------------------


def test_shannon_row_counts_match_the_print():
    """497 rows, in six column blocks of 83 except the last (82)."""
    cells = _shannon_cells(_text("r_ion_Shannon.dat"))
    assert len(cells) == len(radii._shannon_rows()) == 497
    assert Counter(c[9] for c in cells) == {
        "2.1": 83, "2.2": 83, "2.3": 83, "3.1": 83, "3.2": 83, "3.3": 82}
    assert Counter(c[8] for c in cells) == {"752": 249, "753": 248}
    # the CN distribution, which the Imperial College copy shares exactly
    assert Counter(c[3] for c in cells) == {
        "VI": 197, "VIII": 73, "IV": 63, "VII": 35, "IX": 32, "V": 25,
        "XII": 18, "X": 13, "II": 10, "IVSQ": 10, "III": 9, "XI": 5,
        "IIIPY": 3, "IVPY": 2, "I": 1, "XIV": 1}
    keys = [(c[0], c[1], c[3], c[4]) for c in cells]
    assert len(set(keys)) == len(keys)


def test_pyykko_row_counts_match_the_print():
    table = radii._pyykko_rows()
    assert len(table) == 118
    assert sum(r2 == r2 for _, r2 in table.values()) == 108      # nan != nan
    zs = [int(line.split()[1]) for line in _text("r_cov_Pyykko.dat").splitlines()
          if line.strip() and not line.startswith("#")]
    assert zs == list(range(1, 119))


def _off_the_014_rule(text: str) -> list[tuple[str, int, str, float]]:
    """Rows breaking CR = IR + 0.14 (cations) / IR - 0.14 (anions), to the
    printed digits (Shannon pp. 759-760)."""
    off = []
    for ion, charge, _ec, cn, _spin, cr, ir, *_ in _shannon_cells(text):
        gap = (float(cr) - float(ir)) * (1 if int(charge) > 0 else -1)
        if round(gap, 4) != 0.14:
            off.append((ion, int(charge), cn, round(gap, 4)))
    return off


def test_crystal_and_ionic_radii_differ_by_014_except_where_printed():
    """Shannon: "crystal radii differ from traditional radii only by a
    constant factor of 0.14 A". One printed row breaks it, N5+ III
    (.044 / -.104), and it is pinned as the exception it is."""
    assert _off_the_014_rule(_text("r_ion_Shannon.dat")) == [("N", 5, "III", 0.148)]


def test_the_014_check_catches_a_digit_swap():
    """Positive arm: the commonest OCR error on this table, a 4 read as 6,
    in one cell (Fe3+ VI HS IR 0.645 -> 0.665) is caught."""
    text = _text("r_ion_Shannon.dat")
    line = next(row for row in text.splitlines() if row.startswith("Fe    3") and " HS " in row
                and "0.785" in row)
    broken = text.replace(line, line.replace("0.645", "0.665"))
    assert ("Fe", 3, "VI", 0.12) in _off_the_014_rule(broken)


def test_each_data_file_states_its_source_and_status_where_it_ships():
    """A file entering the wheel says what it is (CLAUDE.md, licensing)."""
    for name, dois in (("r_ion_Shannon.dat", ["10.1107/S0567739476001551"]),
                       ("r_cov_Pyykko.dat", ["10.1002/chem.200800987",
                                             "10.1002/chem.200901472"])):
        head = _text(name).split("\n\n")[0]
        assert "# CITE:" in head and "# STATUS:" in head
        for doi in dois:
            assert doi in head


# --- lookups ----------------------------------------------------------------


def test_charge_spellings_resolve_to_one_row():
    assert ionic_radius("Fe+3", 6, spin="HS") == ionic_radius("Fe3+", 6, spin="HS")
    assert ionic_radius("F-", 6).radius == ionic_radius("F1-", 6).radius == 1.33
    assert ionic_radius("OH-", 4).ion == "OH"
    assert ionic_radius("Os4+", 6).ion == "Os"
    assert ionic_radius("D+", 2) == ionic_radius("2H+", 2)
    assert ionic_radius("D+", 2).radius == -0.10           # printed negative
    assert ionic_radius("H+", 2).radius == -0.18


def test_an_integer_cn_reaches_a_lone_suffixed_row():
    """Pd2+ at 4 is printed only as IVSQ, and the label says so."""
    r = ionic_radius("Pd2+", 4)
    assert (r.cn, r.coordination, r.radius) == ("IVSQ", 4, 0.64)


def test_flags_travel_with_the_value():
    estimated = ionic_radius("Pa3+", 6)
    assert isinstance(estimated, IonicRadius)
    assert estimated.estimated and not estimated.reliable
    assert ionic_radius("Zr4+", 8).reliable
    assert ionic_radius("Cs+", 12).flags == ""


# --- refusals ---------------------------------------------------------------


def test_an_untabulated_cn_is_refused_naming_the_tabulated_ones():
    # VII sits between two tabulated CNs; it is not interpolated
    with pytest.raises(KeyError, match=r"Fe3\+ at CN IV, V, VI, VIII only, not VII"):
        ionic_radius("Fe3+", 7)
    with pytest.raises(KeyError, match="no radius is interpolated"):
        ionic_radius("La3+", "XIV")


def test_a_spin_shannon_does_not_print_is_refused():
    with pytest.raises(KeyError, match=r"Mn4\+ VI with no spin state, not HS"):
        ionic_radius("Mn4+", 6, spin="HS")
    with pytest.raises(KeyError, match=r"Fe2\+ IV only in HS, not LS"):
        ionic_radius("Fe2+", "IV", spin="LS")


def test_where_both_spins_are_printed_the_caller_chooses():
    with pytest.raises(ValueError, match=r"Co2\+ VI in HS and LS"):
        ionic_radius("Co2+", 6)
    assert ionic_radius("Co2+", 6, spin="LS").radius == 0.65
    assert ionic_radius("Co2+", 6, spin="HS").radius == 0.745


def test_a_plain_and_a_suffixed_row_at_one_cn_is_ambiguous():
    with pytest.raises(ValueError, match="IV and IVSQ"):
        ionic_radius("Cu2+", 4)
    assert ionic_radius("Cu2+", "IV").radius == 0.57


@pytest.mark.parametrize("species, error, match", [
    ("Fe", ValueError, "no oxidation state"),
    ("Fe7+", KeyError, r"Fe only at charge \+2, \+3, \+4, \+6, not \+7"),
    ("He2+", KeyError, "no row for He"),
    ("Xx3+", ValueError, "unrecognised element"),
])
def test_an_ion_shannon_does_not_tabulate_is_refused(species, error, match):
    with pytest.raises(error, match=match):
        ionic_radius(species, 6)


def test_bad_arguments_are_refused():
    with pytest.raises(ValueError, match="kind"):
        ionic_radius("O2-", 6, kind="effective")
    with pytest.raises(ValueError, match="spin"):
        ionic_radius("Fe3+", 6, spin="high")
    with pytest.raises(ValueError, match="coordination number"):
        ionic_radius("O2-", "six")
    with pytest.raises(ValueError, match="order"):
        covalent_radius("C", order=3)

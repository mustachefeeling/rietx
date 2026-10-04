"""WP-1510 — what the chemist knows reaches the search: a formula's volume.

Three things are pinned.  A formula-unit volume is Hofmann's (2002) sum of
average atomic volumes, with its esd.  ``SearchSpec.from_formula`` turns it
into a volume window the caller declares.  And ``index_pattern(formula=...)``
reports a candidate whose volume holds a fractional number of formula units,
without removing it.
"""

from __future__ import annotations

import pytest

from rietx.crystallography.atomic_volume import (
    HOFMANN_VOLUMES,
    VOLUME_RATIO_BOUNDS,
    formula_unit_volume,
)
from rietx.indexing import index_pattern
from rietx.indexing.diagnostics import Z_INTEGER_TOLERANCE, candidate_diagnostics
from rietx.indexing.engines import DEFAULT_MIN_VOLUME, SearchSpec
from rietx.schemas.indexing import CellCandidate
from tests.test_indexing_engines import synthetic_peaks

#: Benzoic acid, C7H6O2, from Hofmann's Table 2 at 298 K:
#: 7 × 13.87 + 6 × 5.08 + 2 × 11.39 Å³, and eq. (13)'s esd
#: 7 × 0.05 + 6 × 0.04 + 2 × 0.17 Å³.
BENZOIC = "C7H6O2"
BENZOIC_V = 150.35
BENZOIC_ESD = 0.93


def test_a_formula_unit_volume_is_hofmanns_sum_with_its_esd():
    volume, esd = formula_unit_volume(BENZOIC)
    assert volume == pytest.approx(BENZOIC_V, abs=1e-9)
    assert esd == pytest.approx(BENZOIC_ESD, abs=1e-9)
    # a CIF _chemical_formula_sum reads the same
    assert formula_unit_volume("C7 H6 O2") == (volume, esd)
    # eq. (1): (1 + ᾱT)/(1 + ᾱ·298 K) with ᾱ = 0.95e-4 K⁻¹, so 1.8 % smaller
    # at 100 K, and the expansion term now adds to the esd
    cold, cold_esd = formula_unit_volume(BENZOIC, temperature=100.0)
    assert cold == pytest.approx(BENZOIC_V * (1 + 0.95e-2) / (1 + 0.95e-4 * 298))
    assert cold_esd > BENZOIC_ESD * cold / BENZOIC_V
    # Kempster & Lipson's rule puts 18 Å³ on each non-hydrogen atom, and the
    # table lands near it
    assert 15.0 < volume / 9 < 18.0


def test_an_element_with_no_mean_error_has_no_esd():
    assert HOFMANN_VOLUMES["Am"] == (17.0, None)
    volume, esd = formula_unit_volume("AcCl3")
    assert volume == pytest.approx(74.0 + 3 * 25.8)
    assert esd is None


@pytest.mark.parametrize("formula,expected", [
    ("CH3CH2OH", {"C": 2, "H": 6, "O": 1}),
    ("Cu(C2H3O2)2", {"Cu": 1, "C": 4, "H": 6, "O": 4}),
    ("CuSO4·5H2O", {"Cu": 1, "S": 1, "O": 9, "H": 10}),
])
def test_brackets_and_adducts_count(formula, expected):
    volume, _ = formula_unit_volume(formula)
    assert volume == pytest.approx(
        sum(n * HOFMANN_VOLUMES[el][0] for el, n in expected.items()))


@pytest.mark.parametrize("formula,named", [
    ("He", "no average volume for He"),
    ("Xx2", "'Xx' is not an element"),
    ("C(H2", "never closed"),
    ("", "empty part"),
])
def test_a_formula_the_table_cannot_read_raises_naming_why(formula, named):
    with pytest.raises(ValueError, match=named):
        formula_unit_volume(formula)


def test_the_window_holds_z_units_widened_to_hofmanns_bounds():
    low, high = VOLUME_RATIO_BOUNDS
    assert (low, high) == (0.8, 1.25)
    spec = SearchSpec.from_formula(BENZOIC, z=4, max_d_axis=32.0)
    assert spec.min_volume == pytest.approx(4 * BENZOIC_V * 0.8)
    assert spec.max_volume == pytest.approx(4 * BENZOIC_V * 1.25)
    assert spec.max_d_axis == 32.0
    ranged = SearchSpec.from_formula(BENZOIC, z=(2, 8))
    assert (ranged.min_volume, ranged.max_volume) == pytest.approx(
        (2 * BENZOIC_V * 0.8, 8 * BENZOIC_V * 1.25))
    # no Z: the floor of one formula unit, and the envelope keeps the ceiling
    floor_only = SearchSpec.from_formula(BENZOIC)
    assert floor_only.min_volume == pytest.approx(BENZOIC_V * 0.8)
    assert floor_only.max_volume is None
    # two lower bounds, the larger binds
    assert SearchSpec.from_formula("H2").min_volume == DEFAULT_MIN_VOLUME


@pytest.mark.parametrize("z", [0, (4, 2), 2.5])
def test_a_z_that_is_not_a_whole_count_raises(z):
    with pytest.raises(ValueError, match="whole number"):
        SearchSpec.from_formula(BENZOIC, z=z)


def _candidate(volume: float) -> CellCandidate:
    a = volume ** (1.0 / 3.0)
    return CellCandidate(cell=(a, a, a, 90.0, 90.0, 90.0), cell_esd=(0.0,) * 6,
                         system="cubic", volume=volume)


def _z_checks(volume: float, formula: str | None = BENZOIC):
    return [d for d in candidate_diagnostics(_candidate(volume), formula=formula)
            if d.code == "INDEX_Z_NOT_INTEGER"]


@pytest.mark.parametrize("z", [8 / 3, 2.5, 0.6])
def test_the_z_check_fires_on_a_fractional_cell(z):
    (diag,) = _z_checks(z * BENZOIC_V)
    assert diag.level == "warning"
    assert diag.value == pytest.approx(z)
    assert f"{z:.2f} formula units of {BENZOIC}" in diag.message
    assert f"formula {BENZOIC}" in diag.where


@pytest.mark.parametrize("z", [4.0, 4.0 * 1.07, 2.8])
def test_the_z_check_is_silent_within_twice_the_scatter(z):
    # 2.8 sits 6.7 % from 3, inside the 8 % that twice Hofmann's 4.00 %
    # scatter of one crystal allows, so it is not evidence of a fractional Z
    assert Z_INTEGER_TOLERANCE == pytest.approx(0.08)
    assert _z_checks(z * BENZOIC_V) == []


def test_no_formula_no_z_check():
    assert _z_checks(2.5 * BENZOIC_V, formula=None) == []


def test_index_pattern_reports_the_z_and_keeps_the_candidate():
    # methanol's 45.58 Å³ against the synthetic cubic cell's 71.8 Å³: Z = 1.58,
    # 21 % from 2, so the true cell is reported and still ranked
    peaks, true_cell = synthetic_peaks("cubic")
    spec = SearchSpec(systems=("cubic",), min_d_axis=2.0, max_d_axis=12.0,
                      max_volume=1500.0, shift_allowance_deg=1e-9)
    res = index_pattern(peaks, spec=spec, preset="full",
                        engines=("trial_error",), formula="CH3OH")
    truth = next(c for c in res.candidates
                 if c.cell[0] == pytest.approx(true_cell[0], rel=1e-3))
    (diag,) = [d for d in truth.diagnostics if d.code == "INDEX_Z_NOT_INTEGER"]
    v_fu, _ = formula_unit_volume("CH3OH")
    assert diag.value == pytest.approx(truth.volume / v_fu)


def test_index_pattern_refuses_a_bad_formula_before_any_work():
    peaks, _ = synthetic_peaks("cubic")
    with pytest.raises(ValueError, match="not an element"):
        index_pattern(peaks, formula="Qq2")

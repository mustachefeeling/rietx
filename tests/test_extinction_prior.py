"""Declared facts as a member filter on the extinction screen, and the Laue fork.

A powder pattern cannot separate the members of an extinction class, so the
choice inside one is chemistry — and ``restrict=`` is where the chemistry is
declared.  The claims, each with an arm that must come out a known way:

* **the vocabulary is derived** — Sohncke, centrosymmetric and polar are read
  off each group's operators, never transcribed; the polar test reproduces the
  ten polar crystal classes over gemmi's whole table;
* **a declared chirality is used** — on a P 2₁ specimen the screen's class is
  ``P 1 21 1`` = {P 2₁, P 2₁/m}; declared enantiopure, the answer is P 2₁ alone,
  with P 2₁/m named as excluded;
* **a wrong declaration is visible** — on a P 2₁/c specimen the same declaration
  empties the class the data prefer decisively, and the screen abstains with a
  warning instead of obeying it;
* **the Laue fork** — a class whose admitted members fall in two Laue classes
  says so (``LAUE_CLASS_NOT_SEPARABLE``), and one that does not, does not.

The specimens are the synthetic monoclinic of ``test_extinction_symbol.py``.
"""

from __future__ import annotations

import gemmi
import pytest

from rietx import determine_extinction_symbol
from rietx.indexing.diagnostics import extinction_diagnostics
from rietx.indexing.extinction import admits, is_polar, laue_classes
from rietx.schemas.indexing import (
    ExtinctionCandidate,
    ExtinctionPrior,
    ExtinctionScreen,
)
from tests.test_extinction_symbol import (
    MONO_CELL,
    MONO_RANGE,
    _candidate,
    _mono_models,
    _pattern,
)

pytestmark = pytest.mark.xdist_group("extinction-prior")

ENANTIOPURE = ExtinctionPrior(sohncke=True)


def _codes(screen):
    return [d.code for d in screen.diagnostics]


def _screen(space_group: str, **kw):
    structure, instrument = _mono_models(space_group)
    return determine_extinction_symbol(
        _pattern(structure, instrument), _candidate(MONO_CELL, "monoclinic"),
        instrument, two_theta_limits=MONO_RANGE, **kw)


# ----------------------------------------------------------------------
# the vocabulary
# ----------------------------------------------------------------------
def test_the_polar_test_reproduces_the_ten_polar_classes():
    found = {sg.point_group_hm() for sg in gemmi.spacegroup_table() if is_polar(sg)}
    assert found == {"1", "2", "m", "mm2", "4", "4mm", "3", "3m", "6", "6mm"}


def test_an_enantiopure_declaration_admits_exactly_the_sohncke_types():
    numbers = {sg.number for sg in gemmi.spacegroup_table()
               if admits(ENANTIOPURE, sg)}
    assert len(numbers) == 65
    assert not any(admits(ENANTIOPURE, sg) for sg in gemmi.spacegroup_table()
                   if sg.is_centrosymmetric())


def test_a_contradictory_declaration_is_refused():
    with pytest.raises(ValueError, match="Sohncke"):
        ExtinctionPrior(sohncke=True, centrosymmetric=True)
    with pytest.raises(ValueError, match="inversion"):
        ExtinctionPrior(polar=True, centrosymmetric=True)
    assert ExtinctionPrior().declared() == {}


# ----------------------------------------------------------------------
# a declared chirality is used
# ----------------------------------------------------------------------
@pytest.fixture(scope="module")
def p21_screens():
    return (_screen("P 1 21 1"), _screen("P 1 21 1", restrict={"sohncke": True}))


def test_a_declared_chirality_removes_the_centrosymmetric_partner(p21_screens):
    plain, declared = p21_screens
    best = plain.best_or_none()
    assert best is not None and best.symbol == "P 1 21 1"
    assert best.space_groups == ["P 1 21 1", "P 1 21/m 1"]
    assert "EXTINCTION_GROUPS_NOT_SEPARABLE" in _codes(plain)

    best = declared.best_or_none()
    assert best is not None and best.symbol == "P 1 21 1"
    assert best.space_groups == ["P 1 21 1"]
    assert best.excluded_groups == ["P 1 21/m 1"]
    assert declared.prior == ENANTIOPURE
    note = next(d for d in declared.diagnostics
                if d.code == "EXTINCTION_PRIOR_APPLIED")
    assert note.level == "info"
    assert any(w.startswith("P 1 21 1: excluded P 1 21/m 1") for w in note.where)
    assert "EXTINCTION_GROUPS_NOT_SEPARABLE" not in _codes(declared)


def test_the_declaration_moves_no_number_the_data_produced(p21_screens):
    plain, declared = p21_screens
    assert [c.symbol for c in plain.candidates] == \
           [c.symbol for c in declared.candidates]
    for a, b in zip(plain.candidates, declared.candidates, strict=True):
        assert (a.delta_bic, a.n_testable, a.refuted) == \
               (b.delta_bic, b.n_testable, b.refuted)
        assert sorted(a.space_groups) == sorted(b.space_groups + b.excluded_groups)


def test_a_declaration_the_data_contradict_makes_the_screen_abstain():
    """P 2₁/c declared enantiopure: the data's class has no admissible member,
    and it leads the first admissible class by more than the decisive margin."""
    screen = _screen("P 1 21/c 1", restrict=ENANTIOPURE)
    lead = screen.candidates[0]
    assert lead.symbol == "P 1 21/c 1" and lead.space_groups == []
    assert lead.excluded_groups == ["P 1 21/c 1"]
    assert screen.best_or_none() is None
    note = next(d for d in screen.diagnostics if d.code == "EXTINCTION_PRIOR_APPLIED")
    assert note.level == "warning"
    ambiguous = next(d for d in screen.diagnostics
                     if d.code == "EXTINCTION_SYMBOL_AMBIGUOUS")
    assert "excludes" in ambiguous.message


# ----------------------------------------------------------------------
# the Laue fork
# ----------------------------------------------------------------------
def test_laue_classes_partition_a_class_by_which_reflections_are_equivalent():
    assert laue_classes(["P 63", "P 63/m", "P 63 2 2"]) == {
        "6/m": ["P 63", "P 63/m"], "6/mmm": ["P 63 2 2"]}
    assert laue_classes(["P 1 21 1", "P 1 21/m 1"]) == {
        "2/m": ["P 1 21 1", "P 1 21/m 1"]}


def _one_class_screen(groups: list[str]) -> ExtinctionScreen:
    lead = ExtinctionCandidate(symbol="lead", representative=groups[-1],
                               space_groups=groups, laue_classes=laue_classes(groups),
                               n_absent=3, n_testable=3, screened=True,
                               delta_bic=-300.0)
    ref = ExtinctionCandidate(symbol="ref", representative="ref",
                              space_groups=["P 6/m m m"],
                              laue_classes=laue_classes(["P 6/m m m"]),
                              screened=True, delta_bic=0.0)
    return ExtinctionScreen(candidates=[lead, ref], system="hexagonal")


def test_a_class_spanning_two_laue_classes_says_so():
    diagnostics = extinction_diagnostics(_one_class_screen(["P 63", "P 63/m",
                                                           "P 63 2 2"]))
    fork = next(d for d in diagnostics if d.code == "LAUE_CLASS_NOT_SEPARABLE")
    assert fork.where == ["6/m: P 63, P 63/m", "6/mmm: P 63 2 2"]


def test_a_class_inside_one_laue_class_does_not(p21_screens):
    plain, _ = p21_screens
    assert "LAUE_CLASS_NOT_SEPARABLE" not in _codes(plain)
    diagnostics = extinction_diagnostics(_one_class_screen(["P 63", "P 63/m"]))
    assert "LAUE_CLASS_NOT_SEPARABLE" not in [d.code for d in diagnostics]


# ----------------------------------------------------------------------
# the diagnostics name the right classes once a prior empties the leader
# ----------------------------------------------------------------------
def _cand(symbol: str, groups: list[str], delta_bic: float, excluded=()):
    return ExtinctionCandidate(
        symbol=symbol, representative=(groups or list(excluded))[0],
        space_groups=groups, excluded_groups=list(excluded),
        laue_classes=laue_classes(groups), n_absent=3, n_testable=3,
        screened=True, delta_bic=delta_bic)


def _prior_screen(candidates):
    return ExtinctionScreen(candidates=candidates, system="monoclinic",
                            prior=ENANTIOPURE)


def test_the_runners_up_exclude_the_leading_class_and_name_the_emptied_one():
    screen = _prior_screen([
        _cand("emptied", [], -300.0, excluded=["P 1 21/c 1"]),
        _cand("top", ["P 1 21 1"], -100.0),
        _cand("rival", ["P 1 1 21"], -98.0),
        _cand("third", ["P 1 1 2"], -50.0)])
    ambiguous = next(d for d in extinction_diagnostics(screen)
                     if d.code == "EXTINCTION_SYMBOL_AMBIGUOUS")
    assert ambiguous.where[0] == "leading: top"
    assert [w.split(" (")[0] for w in ambiguous.where[1:]] == [
        "then: rival", "then: third", "excluded by the prior: emptied"]


def test_a_prior_that_empties_every_class_does_not_call_one_admitted():
    screen = _prior_screen([
        _cand("emptied", [], -300.0, excluded=["P 1 21/c 1"]),
        _cand("also", [], -100.0, excluded=["P 1 21/m 1"])])
    note = next(d for d in extinction_diagnostics(screen)
                if d.code == "EXTINCTION_PRIOR_APPLIED")
    assert note.level == "warning"
    assert "first class the declaration admits" not in note.message
    assert "no admissible answer" in note.message


def test_the_polar_test_is_the_floating_origin_basis():
    from rietx.crystallography.wyckoff import floating_origin_basis
    for sg in gemmi.spacegroup_table():
        assert is_polar(sg) == (len(floating_origin_basis(sg)) > 0)

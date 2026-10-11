"""One number rule for every CIF this build writes (WP-1319 C-b, issue #756 § 1).

A value with an su is written by ``format_su`` (two significant figures,
``SU_REFERENCE`` in ``test_exporters.py``); a value without one as the shortest
``repr`` that reads back as the same double; a non-finite value is refused,
and so is whitespace in a tag the dictionary types as a single word.  Both
round trips below failed on the four-decimal writer this replaced: β came back
``90.0`` and the occupancy ``0.3333``.
"""

from __future__ import annotations

import math

import gemmi
import pytest

import rietx as rx
from rietx.io.cif import numbers
from rietx.io.cif.registry import TAGS
from rietx.schemas.common import Parameter
from rietx.schemas.structure import Atom, Cell, Phase


def _monoclinic(*, beta=90.00004, occ=0.33333, label="Mn1"):
    return rx.Structure(phases=[Phase(
        name="mono", space_group="P 1 21/c 1",
        cell=Cell(a=Parameter(value=5.0), b=Parameter(value=6.0),
                  c=Parameter(value=7.0), alpha=Parameter(value=90.0),
                  beta=Parameter(value=beta), gamma=Parameter(value=90.0)),
        atoms=[Atom(label=label, species="Mn", x=Parameter(value=0.1),
                    y=Parameter(value=0.2), z=Parameter(value=0.3),
                    occ=Parameter(value=occ), biso=Parameter(value=0.5))])])


def test_a_free_angle_and_an_occupancy_round_trip_bit_identically(tmp_path):
    path = tmp_path / "mono.cif"
    _monoclinic().to_cif(str(path))
    back = rx.Structure.from_cif(str(path)).phases[0]
    assert back.cell.beta.value == 90.00004
    assert back.atoms[0].occ.value == 0.33333


def test_a_value_with_an_su_is_format_su_and_one_without_is_repr():
    assert numbers.number("_cell_length_a", 4.5937, 0.00025) == "4.59370(25)"
    assert numbers.number("_cell_angle_beta", 90.00004) == "90.00004"
    assert numbers.number("_atom_site_occupancy", 1.0) == "1.0"
    assert numbers.number("_atom_site_fract_x", 1e-5) == "1e-05"
    for value in (0.1 + 0.2, 1 / 3, 5.0200000000000005, -2.5e-17):
        assert gemmi.cif.as_number(numbers.number("_atom_site_fract_x",
                                                  value)) == value


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_a_non_finite_value_is_refused_naming_the_tag_and_the_value(value):
    with pytest.raises(ValueError, match=rf"_atom_site_fract_x .*{value!r}"):
        numbers.number("_atom_site_fract_x", value)


def test_a_nan_coordinate_is_refused_before_any_file_is_written(tmp_path):
    """A ``Parameter`` validates its value, so a NaN arrives the way a
    diverged fit's write-back does, through ``model_copy``, which does not."""
    structure = _monoclinic()
    atom = structure.phases[0].atoms[0]
    structure.phases[0].atoms[0] = atom.model_copy(
        update={"x": atom.x.model_copy(update={"value": math.nan})})
    path = tmp_path / "nan.cif"
    with pytest.raises(ValueError, match=r"_atom_site_fract_x of 'Mn1' is nan"):
        structure.to_cif(str(path))
    assert not path.exists()


def test_a_label_with_a_space_is_refused_naming_the_tag_and_the_label(tmp_path):
    path = tmp_path / "space.cif"
    with pytest.raises(ValueError, match=r"_atom_site_label .*'Mn 1'"):
        _monoclinic(label="Mn 1").to_cif(str(path))
    assert not path.exists()


def test_whitespace_is_quoted_in_a_text_tag_and_refused_in_a_word_tag():
    assert numbers.text("_space_group_symop_operation_xyz", "x, y, z") == \
        "'x, y, z'"
    assert numbers.text("_atom_site_label", "O1") == "O1"
    assert numbers.text("_atom_site_label", "_O1") == "'_O1'"
    for value in ("O 1", "O\t1", ""):
        with pytest.raises(ValueError, match="_atom_site_label"):
            numbers.text("_atom_site_label", value)


def test_every_word_tag_is_one_the_dictionary_types_as_a_word():
    """The rule reads the registry, so a Word tag is one the dictionary says
    is; ``test_cif_registry`` checks each row's contents against it."""
    words = {name for name, tag in TAGS.items() if tag.contents == "Word"}
    assert {"_atom_site_label", "_atom_site_type_symbol",
            "_atom_site_aniso_label", "_atom_site_moment.label"} <= words

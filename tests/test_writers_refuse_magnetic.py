"""The foreign project writers refuse a magnetic phase by name (issue #470).

Before this, ``topas``, ``gsas`` and ``fullprof`` wrote the MnF₂ phase from
``test_magnetic`` as a nuclear one — moments and magnetic group gone, no
exception, no warning — and ``gsas2`` wrote the magCIF loops into a file whose
target reads them back as a nuclear phase (GSAS-II 5.6.3's scriptable
``add_phase``, measured on this file: ``General.Type`` ``nuclear``, no
magnetic group, every spin +1, no warning).  Each writer now raises, naming the phase,
and a moment-free phase writes exactly as before.

**Except TOPAS, since WP-1328**: its writer now *writes* the moment
(`mag_space_group`, `mlx mly mlz` in TOPAS's measured fractional basis), so
it leaves `WRITERS` for `REFUSING` below and its round trips live in
`test_projects_topas.py`.  What it still refuses is its own list, by name;
`_mnf2()` itself is one of them, its species (`Mn`) and ion (`Mn2+`)
being two fields TOPAS states as one.
"""

from __future__ import annotations

import importlib

import pytest

from rietx.crystallography.symmetry import refuse_magnetic_phase
from rietx.schemas.structure import Structure
from tests.test_magnetic import _mnf2

WRITERS = {
    "topas": ("write_topas_inp", "a TOPAS `.inp`"),
    "gsas": ("write_gsas_exp", "a GSAS `.EXP`"),
    "fullprof": ("write_fullprof_pcr", "a FullProf `.pcr`"),
    "gsas2": ("write_gsas2_phase_cif", "a GSAS-II phase CIF"),
}

#: The writers that still write no magnetic records: every one but TOPAS.
REFUSING = {k: v for k, v in WRITERS.items() if k != "topas"}

#: What each format would call a moment or a magnetic group, lower-cased: the
#: issue's own probe, plus the magCIF tag stem ``magn``.
MAGNETIC_TOKENS = ("mlx", "moment", "mag_space", "magnetic", "mxyz", "magn")


def _module(fmt):
    return importlib.import_module(f"rietx.io.projects.{fmt}")


@pytest.mark.parametrize("fmt", sorted(REFUSING))
def test_a_magnetic_phase_is_refused_by_name(fmt, tmp_path):
    _, name = WRITERS[fmt]
    with pytest.raises(ValueError) as err:
        _module(fmt).from_structure(Structure(phases=[_mnf2()]))
    message = str(err.value)
    assert "'MnF2'" in message
    assert name in message
    assert "BNS 136.499" in message
    assert "moments on 1 of 2 sites" in message
    assert "nuclear phase" in message


@pytest.mark.parametrize("fmt", sorted(WRITERS))
def test_a_refused_magnetic_phase_leaves_no_file(fmt, tmp_path):
    write = getattr(_module(fmt), WRITERS[fmt][0])
    out = tmp_path / "out"
    with pytest.raises(ValueError, match="'MnF2' cannot be written"):
        write(Structure(phases=[_mnf2()]), out)
    assert not out.exists()


@pytest.mark.parametrize("fmt", sorted(WRITERS))
def test_the_same_phase_without_a_moment_writes_as_a_nuclear_phase(fmt):
    text = _module(fmt).from_structure(Structure(phases=[_mnf2(moment=None)]))
    assert "MnF2" in text
    assert not any(k in text.lower() for k in MAGNETIC_TOKENS)


def test_gsas2_names_the_import_that_drops_the_moments():
    """The gsas2 file does carry the loops; the reason is the importer's."""
    with pytest.raises(ValueError, match="GSAS-II's CIF import drops"):
        _module("gsas2").from_structure(Structure(phases=[_mnf2()]))


def test_a_moment_without_a_group_is_refused_too():
    """The schema refuses this pair, and the writer does not lean on that."""
    phase = _mnf2()
    stripped = phase.model_copy(update={"magnetic_symmetry": None})
    with pytest.raises(ValueError, match=r"no magnetic group; moments on 1 "):
        refuse_magnetic_phase(stripped, "a TOPAS `.inp`")


def test_a_group_without_a_moment_is_refused_too():
    phase = _mnf2()
    bare = phase.model_copy(update={"atoms": [
        a.model_copy(update={"moment": None}) for a in phase.atoms]})
    with pytest.raises(ValueError, match=r"BNS 136.499; moments on 0 of 2"):
        refuse_magnetic_phase(bare, "a TOPAS `.inp`")


def test_topas_writes_the_moment_where_the_others_refuse(tmp_path):
    """The flip of #521's TOPAS row: the same MnF₂, with its species set to
    its ion, writes a `.inp` carrying `mag_space_group` and `mlx`."""
    phase = _mnf2()
    mn = phase.atoms[0].model_copy(update={"species": "Mn2+"})
    text = _module("topas").from_structure(Structure(phases=[
        phase.model_copy(update={"atoms": [mn, phase.atoms[1]]})]))
    assert "mag_space_group 136.499" in text
    assert "mlz @ " in text

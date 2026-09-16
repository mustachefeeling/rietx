"""``read_gsas2_instprm``/``write_gsas2_instprm``: GSAS-II's text instrument file.

Two fixtures are **vendored**, unlike the GSAS-I ``.prm`` pair's: the GSAS-II
tutorials carry a redistribution grant where this WP's other corpora are
private (``tests/data/README.md`` § GSAS-II).  They are the two ends of what
the corpus holds — a constant-wavelength neutron calibration that reads end to
end, and an X-ray one that is **refused** for a negative ``X``, which 2 of the
corpus's 4 constant-wavelength files carry.

What no real file here covers is written by hand, which is the same split
``test_projects_gsas2.py`` makes: no ``.instprm`` in the corpus states a Kα
doublet, a ``Diff-type`` or a goniometer radius, and the doublet key names are
corroborated instead by ``gsas2_pbso4.gpx``, whose two histograms carry
``INSTPRM_CW_SINGLE`` and ``INSTPRM_CW_DOUBLET`` exactly.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import rietx as rx
from rietx.io.instrument_profile import (
    INSTPRM_SHL_FLOOR,
    from_instrument_gsas2,
    read_gsas2_instprm,
)
from rietx.io.projects.gsas2 import (
    INSTPRM_CW_DOUBLET,
    INSTPRM_CW_SINGLE,
    read_instprm,
)

DATA = Path(__file__).parent / "data"
BNL = DATA / "gsas2_bnl.instprm"
HB2A = DATA / "gsas2_hb2a.instprm"


def _calibrated() -> rx.Instrument:
    """An instrument shaped like a converged ``lab_calibrate``, doublet and all.

    The same shape ``test_gsas_prm.py`` writes for the ``.prm`` writer, so the
    two formats' round trips are comparable.
    """
    inst = rx.Instrument.debye_scherrer(wavelength=1.5405929, polarization=0.99)
    inst.source.lines.append(rx.EmissionLine(
        wavelength=1.5444274, weight=rx.Parameter(value=0.5, min=0.0, max=2.0)))
    inst.profile.u.value = 1.163e-4
    inst.profile.v.value = -0.126e-4
    inst.profile.w.value = 0.063e-4
    inst.profile.x.value = 0.173e-2
    inst.profile.y.value = 0.0
    inst.geometry.axial_sl.value = 0.0015
    inst.geometry.axial_hl.value = 0.0015
    inst.zero_shift.value = -0.0043
    return inst


# ----------------------------------------------------------------- the grammar


def test_the_grammar_reads_the_items_gsas_ii_writes():
    """One bank, keys and values as strings, spaces stripped from both."""
    (bank,) = read_instprm(HB2A.read_text())
    assert bank.number is None
    assert bank.items["Type"] == "PNC"
    assert bank.items["Lam"] == "2.4062686168735197"


def test_several_items_may_share_a_line_and_spaces_are_stripped():
    """``;`` separates items on one line and every space goes, which is what
    makes GSAS-II's own ``Gonio. radius`` arrive as ``Gonio.radius``."""
    text = ("#GSAS-II instrument parameter file; do not add/delete items!\n"
            "Type:PXC; Lam:1.5405\n"
            "Gonio. radius:217.5\n")
    (bank,) = read_instprm(text)
    assert bank.items == {"Type": "PXC", "Lam": "1.5405",
                          "Gonio.radius": "217.5"}


def test_a_triple_quoted_value_runs_to_its_delimiter():
    """GSAS-II writes a multi-line value that way, and a reader that split it
    on ``:`` would take its second line for an item."""
    text = ("#GSAS-II instrument parameter file; do not add/delete items!\n"
            "InstrName:'''a beamline\nwith a note: two lines'''\n"
            "Type:PXC\n")
    (bank,) = read_instprm(text)
    assert bank.items["Type"] == "PXC"
    assert "two lines" in bank.items["InstrName"]


def test_a_file_without_the_marker_is_refused():
    """GSAS-II's own file test is ``'GSAS-II' in the first line`` and nothing
    else, so this reader makes the same one."""
    with pytest.raises(ValueError, match="GSAS-II"):
        read_instprm("#some other program's parameters\nType:PXC\n")


def test_banks_are_split_on_their_headers():
    text = ("#Bank 1: GSAS-II instrument parameter file; do not add/delete items!\n"
            "  Type:PXC\n  Lam:1.0\n"
            "#Bank 2: GSAS-II instrument parameter file; do not add/delete items!\n"
            "  Type:PXC\n  Lam:2.0\n")
    banks = read_instprm(text)
    assert [b.number for b in banks] == [1, 2]
    assert banks[1].items["Lam"] == "2.0"


# ------------------------------------------------------------------ the reader


def test_a_real_neutron_calibration_reads_end_to_end():
    """``gsas2_hb2a.instprm``, HFIR's HB-2A: the corpus file that reads.

    Its numbers are the file's own, converted through the ``.gpx`` reader's
    centidegree factors: U, V and W are centidegrees squared and X, Y
    centidegrees, while ``Zero`` is already degrees.
    """
    instrument = read_gsas2_instprm(HB2A)
    assert instrument.source.kind == "neutron_cw"
    assert instrument.source.wavelength.value == pytest.approx(
        2.4062686168735197, rel=1e-15)
    assert instrument.profile.u.value == pytest.approx(798.889 / 1e4, rel=1e-15)
    assert instrument.profile.v.value == pytest.approx(-444.367 / 1e4, rel=1e-15)
    assert instrument.profile.w.value == pytest.approx(242.406 / 1e4, rel=1e-15)
    assert instrument.zero_shift.value == pytest.approx(
        -0.009602591470493875, rel=1e-15)
    # SH/L = 0.09 is GSAS-II's combined (S+H)/L
    assert instrument.geometry.axial_sl.value == pytest.approx(0.045, rel=1e-15)
    assert instrument.geometry.axial_hl.value == pytest.approx(0.045, rel=1e-15)


def test_everything_comes_back_frozen():
    """A calibration is not a starting guess — :func:`load_instrument_profile`'s
    contract, which both foreign importers here keep."""
    instrument = read_gsas2_instprm(HB2A)
    assert not instrument.profile.u.vary
    assert not instrument.profile.w.vary
    assert not instrument.zero_shift.vary
    assert not instrument.geometry.axial_sl.vary


def test_the_neutron_read_says_what_it_assumed_and_what_it_dropped():
    diagnostics: list = []
    read_gsas2_instprm(HB2A, diagnostics=diagnostics)
    codes = {d.code for d in diagnostics}
    assert codes == {"GSAS2_INSTPRM_CONVENTION_ASSUMED",
                     "GSAS2_INSTPRM_GEOMETRY_ASSUMED",
                     "GSAS2_INSTPRM_FIELD_NOT_READ"}
    (dropped,) = [d for d in diagnostics
                  if d.code == "GSAS2_INSTPRM_FIELD_NOT_READ"]
    # inert in GSAS-II too: it applies the factor to an XC or XB type only
    assert "Polariz." in dropped.message
    assert "K = 1" in dropped.message


def test_a_real_x_ray_calibration_is_refused_for_its_negative_x():
    """``gsas2_bnl.instprm``: a converged GSAS-II fit with ``X`` = −0.0978.

    GSAS-II bounds none of U V W X Y Z and this package's Lorentzian terms are
    softplus-bounded at zero, where ``to_internal`` clamps a non-positive value
    to 1e-12 — so reading it would answer from a model the file does not
    describe.  Two of the corpus's four constant-wavelength files carry one,
    so this is the ordinary case rather than a corner.
    """
    with pytest.raises(ValueError, match="softplus-bounded at zero"):
        read_gsas2_instprm(BNL)


def test_a_time_of_flight_bank_is_refused_by_name(tmp_path):
    path = tmp_path / "tof.instprm"
    path.write_text("#GSAS-II instrument parameter file; do not add/delete items!\n"
                    "Type:PNT\ndifC:22583.9\n")
    with pytest.raises(ValueError, match="time-of-flight"):
        read_gsas2_instprm(path)


def test_a_non_zero_z_is_refused(tmp_path):
    """``ProfileTCHZ`` is u, v, w, x, y exactly, and ``Z`` is zero in all 95
    constant-wavelength histograms of the ``.gpx`` corpus."""
    path = tmp_path / "z.instprm"
    path.write_text("#GSAS-II instrument parameter file; do not add/delete items!\n"
                    "Type:PXC\nLam:1.5405\nZ:0.4\n")
    with pytest.raises(ValueError, match="constant Lorentzian"):
        read_gsas2_instprm(path)


def test_a_non_zero_azimuth_is_refused(tmp_path):
    """At a non-zero azimuth GSAS-II mixes the two polarization components, so
    ``Polariz.`` no longer means this package's K."""
    path = tmp_path / "azm.instprm"
    path.write_text("#GSAS-II instrument parameter file; do not add/delete items!\n"
                    "Type:PXC\nLam:1.5405\nAzimuth:90.0\n")
    with pytest.raises(ValueError, match="azimuth"):
        read_gsas2_instprm(path)


def test_a_doublet_without_its_ratio_is_refused(tmp_path):
    path = tmp_path / "pair.instprm"
    path.write_text("#GSAS-II instrument parameter file; do not add/delete items!\n"
                    "Type:PXC\nLam1:1.5405\nLam2:1.5444\n")
    with pytest.raises(ValueError, match="I\\(L2\\)/I\\(L1\\)"):
        read_gsas2_instprm(path)


def test_a_neutron_bank_stating_a_doublet_is_refused(tmp_path):
    """A monochromator selects one wavelength, so ``NeutronSource`` holds one
    and picking between the pair would be this reader's guess."""
    path = tmp_path / "npair.instprm"
    path.write_text("#GSAS-II instrument parameter file; do not add/delete items!\n"
                    "Type:PNC\nLam1:1.5405\nLam2:1.5444\nI(L2)/I(L1):0.5\n")
    with pytest.raises(ValueError, match="NeutronSource holds"):
        read_gsas2_instprm(path)


def _two_banks() -> str:
    return ("#Bank 1: GSAS-II instrument parameter file; do not add/delete items!\n"
            "  Type:PXC\n  Lam:1.5405\n  W:1.0\n"
            "#Bank 2: GSAS-II instrument parameter file; do not add/delete items!\n"
            "  Type:PXC\n  Lam:0.4139\n  W:4.0\n")


def test_a_multi_bank_file_needs_a_bank(tmp_path):
    """The selection rule ``read_pattern``'s ``scan=`` makes: reading the first
    of several would pick a detector rather than read one.  Three of the
    corpus's twelve files are multi-bank."""
    path = tmp_path / "gem.instprm"
    path.write_text(_two_banks())
    with pytest.raises(ValueError, match="bank=N"):
        read_gsas2_instprm(path)

    chosen = read_gsas2_instprm(path, bank=2)
    assert chosen.source.lines[0].wavelength.value == pytest.approx(0.4139)
    assert chosen.profile.w.value == pytest.approx(4.0 / 1e4, rel=1e-15)


def test_a_bank_the_file_does_not_state_is_refused(tmp_path):
    path = tmp_path / "gem.instprm"
    path.write_text(_two_banks())
    with pytest.raises(ValueError, match="states 1, 2"):
        read_gsas2_instprm(path, bank=7)


def test_a_repeated_bank_number_is_refused(tmp_path):
    """Three of the corpus's twelve files write ``#Bank 6`` twice, so a number
    can name two calibrations in one file."""
    path = tmp_path / "twice.instprm"
    path.write_text(_two_banks().replace("#Bank 2:", "#Bank 1:"))
    with pytest.raises(ValueError, match="names two calibrations"):
        read_gsas2_instprm(path, bank=1)


def test_a_stated_geometry_is_read_rather_than_assumed(tmp_path):
    path = tmp_path / "bb.instprm"
    path.write_text("#GSAS-II instrument parameter file; do not add/delete items!\n"
                    "Type:PXC\nLam:1.5405\nDiff-type:Bragg-Brentano\n"
                    "Gonio. radius:217.5\n")
    diagnostics: list = []
    instrument = read_gsas2_instprm(path, diagnostics=diagnostics)
    assert instrument.geometry.kind == "bragg_brentano"
    assert instrument.geometry.goniometer_radius_mm == pytest.approx(217.5)
    assert not [d for d in diagnostics
                if d.code == "GSAS2_INSTPRM_GEOMETRY_ASSUMED"]


# ------------------------------------------------------------------ the writer


def test_the_writer_round_trips_a_doublet_calibration(tmp_path):
    """Every number the reader maps comes back, through the one centidegree
    conversion rather than a second copy of it."""
    inst = _calibrated()
    out = tmp_path / "written.instprm"
    rx.write_gsas2_instprm(inst, out)
    back = read_gsas2_instprm(out)

    assert len(back.source.lines) == 2
    assert back.source.lines[0].wavelength.value == pytest.approx(1.5405929, rel=1e-15)
    assert back.source.lines[1].wavelength.value == pytest.approx(1.5444274, rel=1e-15)
    assert back.source.lines[1].weight.value == pytest.approx(0.5, rel=1e-15)
    assert back.source.polarization.value == pytest.approx(0.99, rel=1e-15)
    for key in ("u", "v", "w", "x", "y"):
        assert getattr(back.profile, key).value == pytest.approx(
            getattr(inst.profile, key).value, rel=1e-12)
    assert back.geometry.axial_sl.value == pytest.approx(0.0015, rel=1e-15)
    assert back.geometry.axial_hl.value == pytest.approx(0.0015, rel=1e-15)
    assert back.zero_shift.value == pytest.approx(-0.0043, rel=1e-15)
    assert back.geometry.kind == "debye_scherrer"


def test_a_single_line_source_writes_lam_and_not_the_pair(tmp_path):
    inst = rx.Instrument.debye_scherrer(wavelength=0.4139090, polarization=0.99)
    out = tmp_path / "mono.instprm"
    rx.write_gsas2_instprm(inst, out)
    assert "\nLam:" in out.read_text()
    back = read_gsas2_instprm(out)
    assert len(back.source.lines) == 1
    assert back.source.primary_wavelength == pytest.approx(0.4139090, rel=1e-15)


def test_a_neutron_instrument_round_trips(tmp_path):
    """The one radiation the ``.prm`` pair refuses outright: GSAS-II states it
    as ``PNC`` and this package has held a ``NeutronSource`` since v1.4."""
    inst = rx.Instrument.constant_wavelength_neutron(wavelength=1.5401)
    inst.profile.w.value = 0.02
    out = tmp_path / "neutron.instprm"
    rx.write_gsas2_instprm(inst, out)
    assert "\nType:PNC\n" in out.read_text()
    back = read_gsas2_instprm(out)
    assert back.source.kind == "neutron_cw"
    assert back.source.wavelength.value == pytest.approx(1.5401, rel=1e-15)
    assert back.profile.w.value == pytest.approx(0.02, rel=1e-15)


def test_the_written_keys_are_the_formats_own_list(tmp_path):
    """The two key tuples are the specification's order, and the writer is the
    one caller that depends on it."""
    doublet = read_instprm(from_instrument_gsas2(_calibrated()))[0]
    assert tuple(doublet.items)[:len(INSTPRM_CW_DOUBLET)] == INSTPRM_CW_DOUBLET

    mono = rx.Instrument.debye_scherrer(wavelength=1.0)
    single = read_instprm(from_instrument_gsas2(mono))[0]
    assert tuple(single.items)[:len(INSTPRM_CW_SINGLE)] == INSTPRM_CW_SINGLE
    # GSAS-II's own file test, made on a file this package wrote
    assert from_instrument_gsas2(mono).splitlines()[0].startswith("#GSAS-II")


def test_an_uneven_axial_pair_is_merged_and_the_merge_is_named(tmp_path):
    """``io/CLAUDE.md`` § Project writers' narrower-field rule, met on a value:
    GSAS-II models one ``(S+H)/L``, so the sum crosses and the split does not."""
    inst = _calibrated()
    inst.geometry.axial_sl.value = 0.0010
    inst.geometry.axial_hl.value = 0.0020
    diagnostics: list = []
    out = tmp_path / "uneven.instprm"
    rx.write_gsas2_instprm(inst, out, diagnostics=diagnostics)

    (row,) = [d for d in diagnostics if d.code == "GSAS2_INSTPRM_VALUE_MERGED"]
    assert row.value == pytest.approx(0.0030, rel=1e-12)
    back = read_gsas2_instprm(out)
    assert back.geometry.axial_sl.value == pytest.approx(0.0015, rel=1e-12)
    assert back.geometry.axial_hl.value == pytest.approx(0.0015, rel=1e-12)


def test_an_axial_sum_below_gsas_ii_own_floor_is_named(tmp_path):
    """The one class this round trip cannot catch: GSAS-II floors ``SH/L`` at
    0.002 when it evaluates a profile, so a smaller one is written faithfully
    and modelled as the floor by the program the file is for."""
    inst = _calibrated()
    inst.geometry.axial_sl.value = 0.0005
    inst.geometry.axial_hl.value = 0.0005
    diagnostics: list = []
    rx.write_gsas2_instprm(inst, tmp_path / "small.instprm",
                           diagnostics=diagnostics)
    (row,) = [d for d in diagnostics if d.code == "GSAS2_INSTPRM_VALUE_FLOORED"]
    assert row.value == pytest.approx(0.001, rel=1e-12)
    assert str(INSTPRM_SHL_FLOOR) in row.message


def test_the_written_file_says_what_it_could_not_state(tmp_path):
    inst = _calibrated()
    inst.profile.u.vary = True
    diagnostics: list = []
    rx.write_gsas2_instprm(inst, tmp_path / "said.instprm",
                           diagnostics=diagnostics)
    (row,) = [d for d in diagnostics
              if d.code == "GSAS2_INSTPRM_FIELD_NOT_WRITTEN"]
    assert row.level == "warning"
    assert "the background" in row.message
    assert "every refine flag" in row.message


def test_the_writer_refuses_a_geometry_gsas_ii_cannot_state():
    """``Diff-type`` names two sample kinds and transmission is not one of
    them; writing either would hand over a different experiment."""
    inst = rx.Instrument.flat_plate_transmission()
    with pytest.raises(ValueError, match="Diff-type"):
        from_instrument_gsas2(inst)


def test_the_writer_refuses_more_lines_than_a_bank_holds():
    inst = _calibrated()
    inst.source.lines.append(rx.EmissionLine(
        wavelength=1.39222, weight=rx.Parameter(value=0.1, min=0.0, max=2.0)))
    with pytest.raises(ValueError, match="emission lines"):
        from_instrument_gsas2(inst)


def test_the_writer_refuses_a_declared_harmonic():
    """A λ/n component changes the spectrum and a constant-wavelength bank has
    no term for one."""
    inst = rx.Instrument.constant_wavelength_neutron(wavelength=1.5,
                                                    harmonics=True)
    with pytest.raises(ValueError, match="harmonic"):
        from_instrument_gsas2(inst)


def test_the_writer_refuses_a_non_finite_value():
    """``repr`` spells it ``inf`` and no real program parses that — the same
    refusal all five writers here make."""
    inst = _calibrated()
    inst.profile.y.max = float("inf")
    inst.profile.y.value = float("inf")
    with pytest.raises(ValueError, match="inf"):
        from_instrument_gsas2(inst)


def test_the_written_values_are_the_real_files_own_spelling(tmp_path):
    """The check a round trip cannot make, made against a real file.

    ``float()`` here would read a value GSAS-II spells differently, so the
    ``.EXP`` writer had to compare its cards against ``FAP.EXP``'s own
    spelling (``io/CLAUDE.md`` § Project writers).  A token format lets that be
    exact: reading ``gsas2_hb2a.instprm`` and writing it back reproduces every
    item it states, character for character.
    """
    out = tmp_path / "again.instprm"
    rx.write_gsas2_instprm(read_gsas2_instprm(HB2A), out)
    (original,) = read_instprm(HB2A.read_text())
    (written,) = read_instprm(out.read_text())
    assert original.items == {k: v for k, v in written.items.items()
                              if k in original.items}
    assert len(original.items) == 13


def test_an_item_the_format_declares_and_a_file_omits_is_named(tmp_path):
    """GSAS-II writes every item and its header says not to delete any, so a
    missing one is a hand-edited file — and the value used is this package's
    default rather than the file's."""
    path = tmp_path / "thin.instprm"
    path.write_text("#GSAS-II instrument parameter file; do not add/delete items!\n"
                    "Type:PXC\nLam:1.5405\n")
    diagnostics: list = []
    read_gsas2_instprm(path, diagnostics=diagnostics)
    (row,) = [d for d in diagnostics
              if d.code == "GSAS2_INSTPRM_VALUE_DEFAULTED"]
    assert "SH/L" in row.message and "Polariz." in row.message

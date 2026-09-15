"""The GSAS-I ``.EXP`` reader, against a real converged refinement.

``tests/data/FAP.EXP`` is GSAS's own fluorapatite fit — the file every constant
in ``test_acceptance_fap.py`` used to be read out of by hand — so the rows here
check the reader against a protocol somebody already verified independently.

**The load-bearing row is the last one.** ``REFN GDNFT`` states the number of
variables the refinement had, in words, in a record the reader does not use to
build anything; the refine flags are stated separately, spread across the cell
record, seven atom records, the background header, the scale record and the
profile header.  Reconstructing 28 from the flags is therefore a check of the
whole protocol recovery against a number the file states somewhere else — the
one assertion here that no single-field bug can pass.

Fixtures for the refusal rows are written inline rather than vendored: the
shapes they test (a magnetic phase, an unnamed profile function) are not in any
file this repo may carry, and a synthetic 80-column card is self-describing.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import rietx as rx
from rietx.io.projects.gsas import (
    CW_CENTIDEG_POWER,
    CW_PROFILE_COEFFICIENTS,
    GsasExpError,
    read_gsas_exp,
    to_structure,
)

DATA = Path(__file__).parent / "data"
FAP = DATA / "FAP.EXP"


@pytest.fixture(scope="module")
def fap():
    return read_gsas_exp(FAP)


# --------------------------------------------------------------- what it says

def test_overall_records(fap):
    assert fap.title == "fluoroapatite"
    assert fap.version == 6
    assert fap.rwp == pytest.approx(0.1005)
    assert fap.rp == pytest.approx(0.0766)
    assert fap.n_observations == 5750
    assert fap.n_variables == 28


def test_gdnft_is_reduced_chi_squared_not_its_root(fap):
    """The record says "Reduced CHI**2" in words, and it is not a GoF.

    Issue #103 brought this from a GSAS-II ``.gpx`` campaign, where
    ``Rvals['GOF']`` is the same convention; reading either as a
    goodness-of-fit reports the square of the number meant.
    """
    assert fap.reduced_chi2 == pytest.approx(3.224)


def test_phase_cell_and_esds(fap):
    (phase,) = fap.phases
    assert phase.name == "fap"
    assert phase.space_group == "P 63/m"
    assert phase.kind == 1
    cell = phase.cell
    assert cell.a == pytest.approx(9.371724)
    assert cell.c == pytest.approx(6.885867)
    assert (cell.alpha, cell.beta, cell.gamma) == (90.0, 90.0, 120.0)
    assert cell.esd_a == pytest.approx(3.6e-5)
    assert cell.esd_c == pytest.approx(3.7e-5)
    assert cell.refined is True
    # CELVOL is 2F15.3 in the file against the manual's printed 2F10.3, and
    # reading it at the printed width gives 52.0 -- a plausible number, so the
    # file is the authority and this row is what holds it there.
    assert cell.volume == pytest.approx(523.755)


def test_atoms_carry_the_files_own_refine_flags(fap):
    (phase,) = fap.phases
    assert [a.label for a in phase.atoms] == [
        "CA1", "CA2", "P3", "F4", "O5", "O6", "O7"]
    ca1 = phase.atoms[0]
    assert ca1.species == "CA"          # the file's spelling, not yet IUCr's
    assert (ca1.x, ca1.y, ca1.z) == pytest.approx((0.333333, 0.666667, 0.001913))
    assert ca1.occupancy == pytest.approx(1.0)
    assert ca1.multiplicity == 4
    assert ca1.uiso == pytest.approx(0.006079)
    assert ca1.uij is None and not ca1.anisotropic
    # 'I XU' on the B record: isotropic; occupancy held; coordinates and
    # displacement free.  A blank letter is the file saying held.
    assert (ca1.refine_xyz, ca1.refine_u, ca1.refine_occupancy) == (True, True, False)
    assert all(a.refine_xyz and a.refine_u and not a.refine_occupancy
               for a in phase.atoms)


def test_histogram_icons_is_read_by_column(fap):
    """``ICONS``' trailing fields are positional, and 0.5 is not the ratio.

    Both the polarization fraction and a Kα2/Kα1 ratio are conventionally 0.5,
    so a reader that took the wrong field would agree with the right one on
    this file and disagree on the next.  ``FAP.EXP`` states POLA and leaves
    KRATIO blank; ``INST_XRY.PRM`` beside it states POLA 0.7 *and* KRATIO 0.5
    in the same slots, which is what fixes the order.
    """
    (hist,) = fap.histograms
    assert hist.kind == "PXC"
    assert hist.wavelengths == pytest.approx((1.5405, 1.5443))
    assert hist.zero == 0.0 and hist.refine_zero is False
    assert hist.polarization == pytest.approx(0.5)
    assert hist.polarization_type == 0
    assert hist.ka2_ratio is None       # blank field: the file states no ratio
    assert hist.anode == "Cu"           # IRAD 3
    assert hist.data_file == "fap.xra"
    assert hist.bank == 1


def test_histogram_ranges_and_channel_counts(fap):
    (hist,) = fap.histograms
    # the degenerate 0-0 low-side pair GSAS always writes is not a region
    assert hist.excluded_regions == ((130.0, 1000.0),)
    assert hist.two_theta_range == pytest.approx((15.0, 129.98))
    assert hist.n_channels_used == 5750
    assert hist.n_channels_total == 5753
    assert hist.scale == pytest.approx(96.636) and hist.refine_scale is True


def test_background_is_carried_but_not_converted(fap):
    (hist,) = fap.histograms
    bkg = hist.background
    assert bkg.function == 5            # a reciprocal-Q expansion, not a polynomial
    assert bkg.n_coefficients == 3
    assert bkg.coefficients == pytest.approx((41.8073, 702.33, 3.40611))
    assert bkg.refined is True


def test_profile_names_come_from_the_function_type(fap):
    """Type 2's coefficient 4 is LX, and its 8 is shft rather than GP.

    The manual's own function-2 paragraph lists the eighteen coefficients twice
    and transposes positions 8 and 9 between the two lists.  GSAS's EXPEDT
    listing prints ``#8(shft)``, and this file's converged sample displacement
    sits at index 8, which is what settles it.
    """
    profile = fap.profile()
    assert profile.function == 2
    assert profile.n_coefficients == 18
    terms = profile.by_name()
    assert terms["LX"].index == 4
    assert terms["shft"].index == 8
    assert terms["GP"].index == 9
    assert terms["GU"].value == pytest.approx(2.0)
    assert terms["shft"].value == pytest.approx(4.90166)


def test_centidegree_conversion(fap):
    """A variance term is centideg², a width or a shift is centideg."""
    terms = fap.profile().by_name()
    assert terms["GU"].degrees == pytest.approx(2e-4)
    assert terms["GV"].degrees == pytest.approx(-2e-4)
    assert terms["GW"].degrees == pytest.approx(5e-4)
    assert terms["LX"].degrees == pytest.approx(0.0335183)
    assert terms["LY"].degrees == pytest.approx(0.0248803)
    assert terms["shft"].degrees == pytest.approx(0.0490166)
    # a compound unit is not converted, and says so rather than returning the
    # file's number as though it were degrees
    assert terms["L11"].degrees is None


def test_the_refined_profile_terms_are_the_protocol(fap):
    assert fap.profile().refined_names == ("LX", "LY", "shft")


def test_the_default_profile_is_the_instrument_files_starting_point(fap):
    """``HST``'s own ``PRCF`` set is where the histogram started, not where it
    ended; the refined values live on the ``HAP`` record."""
    (hist,) = fap.histograms
    (default,) = hist.default_profiles
    assert [t.value for t in default.terms] == pytest.approx(
        [2.0, -2.0, 5.0, 1.0, 1.0, 0.0])
    assert not any(t.refined for t in default.terms)


# ----------------------------------------------------------- what it builds

def test_to_structure_carries_the_flags_and_converts_uiso(fap):
    notes: list = []
    structure = to_structure(fap, diagnostics=notes)
    (phase,) = structure.phases
    assert phase.space_group == "P 63/m"
    assert phase.cell.a.vary is True and phase.cell.a.value == pytest.approx(9.371724)
    ca1 = phase.atoms[0]
    assert ca1.species == "Ca"          # normalised, and reported
    assert ca1.biso.value == pytest.approx(0.006079 * 8.0 * 3.141592653589793**2)
    assert ca1.biso.vary is True
    assert ca1.occ.vary is False
    assert any(n.code == "GSAS_SPECIES_NORMALISED" for n in notes)


def test_a_zero_freedom_site_does_not_get_a_vary_it_cannot_honour(fap):
    """GSAS's X flag means "as permitted by symmetry", and F4 has none.

    Carrying the flag onto x/y/z directly makes ``ParameterTable`` refuse the
    whole import of a file GSAS refined happily, so the flag goes through the
    site-symmetry basis GSAS was speaking about.
    """
    notes: list = []
    structure = to_structure(fap, diagnostics=notes)
    f4 = next(a for a in structure.phases[0].atoms if a.label == "F4")
    assert f4.x.vary is False
    assert f4.biso.vary is True         # the U flag is unaffected
    assert any(n.code == "GSAS_COORDINATES_SYMMETRY_FIXED" for n in notes)
    # and the structure is one the package will actually build a table for
    rx.Refinement(structure, rx.Instrument.bragg_brentano())


def test_the_recovered_protocol_reproduces_gsas_own_variable_count(fap):
    """21 structural + 1 scale + 3 background + 3 profile = the file's own 28.

    The flags are spread over eleven records and the count is stated in a
    twelfth that the reader never consults.  This is the row that no
    single-field misreading survives.
    """
    structure = to_structure(fap)
    ref = rx.Refinement(structure, rx.Instrument.bragg_brentano())
    structural = sum(1 for r in ref.parameters() if r.refinable and r.vary)
    assert structural == 21             # cell a and c, 12 coordinate DOFs, 7 Biso

    (hist,) = fap.histograms
    total = (structural
             + (1 if hist.refine_scale else 0)
             + (hist.background.n_coefficients if hist.background.refined else 0)
             + len(fap.profile().refined_names)
             + (1 if fap.hap[(1, 1)].refine_phase_fraction else 0))
    assert total == fap.n_variables == 28


# ------------------------------------------------------------- what it refuses

def _card(key: str, payload: str = "") -> str:
    return f"{key:<12}{payload:<68}"


def _exp(tmp_path: Path, name: str, *cards: str) -> Path:
    path = tmp_path / name
    path.write_text("\r\n".join(cards) + "\r\n", encoding="latin-1")
    return path


_MINIMAL = (
    _card("     VERSION", "    6"),
    _card("      DESCR ", "  a phase"),
    _card(" EXPR NPHAS ", "    1"),
    _card("CRS1    PNAM", "  one"),
    _card("CRS1  ABC   ", "  4.000000  4.000000  4.000000    Y    0"),
    _card("CRS1  ANGLES", "   90.0000   90.0000   90.0000"),
    _card("CRS1  SG SYM", "  P m -3 m"),
    _card("CRS1  AT  1A", "  NA        0.000000  0.000000  0.000000  1.000000NA1        1 000"),
    _card("CRS1  AT  1B", "  0.010000                                                    I  U"),
)


def test_a_file_with_no_experiment_records_is_refused_by_name(tmp_path):
    path = tmp_path / "notes.txt"
    path.write_text("this is not a GSAS experiment file\n")
    with pytest.raises(GsasExpError, match="holds no GSAS experiment records"):
        read_gsas_exp(path)


def test_an_empty_file_is_refused(tmp_path):
    path = tmp_path / "empty.EXP"
    path.write_bytes(b"")
    with pytest.raises(GsasExpError, match="the file is empty"):
        read_gsas_exp(path)


def test_records_without_line_terminators_still_read(tmp_path):
    """Some writers emit the 80-character cards with no line breaks at all."""
    path = tmp_path / "flat.EXP"
    path.write_text("".join(_MINIMAL), encoding="latin-1")
    model = read_gsas_exp(path)
    assert model.phases[0].name == "one"
    assert model.phases[0].cell.a == pytest.approx(4.0)


def test_a_record_after_the_terminator_is_still_read(tmp_path):
    path = _exp(tmp_path, "tail.EXP", *_MINIMAL,
                _card("ZZZZZZZZZZZZ", "  Last EXP file record"),
                _card("    HSTRY 17", " GENLES appended after the end marker"))
    model = read_gsas_exp(path)
    assert model.phases[0].name == "one"


def test_an_unnamed_profile_function_is_refused_rather_than_read_positionally(tmp_path):
    """Function 4's coefficient list is "14 to 27 … S400, etc." in the manual.

    Reading it under function 2's names would put ``LX`` on a coefficient that
    is ``ptec``, which is a plausible wrong width rather than an error.
    """
    path = _exp(tmp_path, "fn4.EXP", *_MINIMAL,
                _card(" EXPR  HTYP1", "  PXC"),
                _card("HST  1 ICONS", "  1.540500  1.544300       0.0         0       0.5    0"),
                _card("HAP1 1PRCF  ", "    4   14   0.01000    0NNNNNNNNNNNNNN"),
                _card("HAP1 1PRCF 1", "   0.200000E+01   0.000000E+00   0.000000E+00   0.000000E+00"))
    with pytest.raises(GsasExpError, match="profile function 4"):
        read_gsas_exp(path)


def test_the_named_functions_all_have_a_unit_for_every_coefficient():
    """Every name in the coefficient table either converts or says it does not.

    A name reachable from :data:`CW_PROFILE_COEFFICIENTS` but absent from
    :data:`CW_CENTIDEG_POWER` returns ``degrees=None``, which is the honest
    answer only where the unit really is compound.  This pins which those are,
    so a new function type cannot quietly add a fourth.
    """
    named = {n for names in CW_PROFILE_COEFFICIENTS.values() for n in names}
    unconverted = sorted(named - set(CW_CENTIDEG_POWER))
    assert unconverted == ["L11", "L12", "L13", "L22", "L23", "L33"]


def test_a_magnetic_phase_is_refused_by_name(tmp_path):
    cards = list(_MINIMAL)
    cards[2] = _card(" EXPR NPHAS ", "    2")
    path = _exp(tmp_path, "mag.EXP", *cards)
    model = read_gsas_exp(path)
    assert model.phases[0].magnetic
    with pytest.raises(GsasExpError, match="magnetic"):
        to_structure(model)


def test_an_anisotropic_site_is_refused_until_a_file_settles_the_convention(tmp_path):
    cards = list(_MINIMAL)
    cards[-1] = _card(
        "CRS1  AT  1B",
        "  0.010000  0.010000  0.010000  0.000000  0.000000  0.000000  A  U")
    path = _exp(tmp_path, "aniso.EXP", *cards)
    model = read_gsas_exp(path)
    assert model.phases[0].atoms[0].anisotropic
    assert model.phases[0].atoms[0].uij == pytest.approx(
        (0.01, 0.01, 0.01, 0.0, 0.0, 0.0))
    with pytest.raises(GsasExpError, match="off-diagonal convention"):
        to_structure(model)


def test_a_multi_phase_file_refuses_to_pick_one(tmp_path):
    cards = [*_MINIMAL,
             _card("CRS2    PNAM", "  two"),
             _card("CRS2  ABC   ", "  5.000000  5.000000  5.000000    N    0"),
             _card("CRS2  ANGLES", "   90.0000   90.0000   90.0000"),
             _card("CRS2  SG SYM", "  P m -3 m"),
             _card("CRS2  AT  1A", "  CL        0.000000  0.000000  0.000000  1.000000CL1        1 000"),
             _card("CRS2  AT  1B", "  0.010000                                                    I  U")]
    cards[2] = _card(" EXPR NPHAS ", "    1    1")
    model = read_gsas_exp(_exp(tmp_path, "two.EXP", *cards))
    assert len(model.phases) == 2
    with pytest.raises(GsasExpError, match="pass phase=N"):
        to_structure(model)
    assert to_structure(model, phase=2).phases[0].name == "two"


def test_a_missing_atom_b_record_is_refused_rather_than_defaulted(tmp_path):
    path = _exp(tmp_path, "half.EXP", *_MINIMAL[:-1])
    with pytest.raises(GsasExpError, match="no matching 'B' record"):
        read_gsas_exp(path)

"""The legacy LANSCE ``.iparm`` bolt-on, :func:`rietx.io.legacy.read_lansce_iparm`.

Synthetic files written column by column with the strict reader's own fixture
helpers (``tests/test_instrument_tof.py``), so a record here is laid out
exactly as a spec-legal one is and differs only by the deviation under test.
The one real fixture is the NPDF run 7245 calibration's instrument records
(below, with its provenance).  The slot destinations and the fifth-pair
exponent these tests pin were measured against GSAS-II v5.8.2 run as a black
box; the run is recorded in the module docstring of
:mod:`rietx.io.legacy.lansce_iparm`, and GSAS-II is not needed to run them.
"""

from __future__ import annotations

import pytest

from rietx.io.instrument_tof import (
    _INSTPRM_PROFILE,
    _PRCF_TO_PROFILE,
    read_gsas_tof_iparm,
)
from rietx.io.legacy import read_lansce_iparm
from rietx.io.legacy.lansce_iparm import (
    GSAS2_PRCF1_DESTINATIONS,
    LANSCE_FIFTH_PAIR_EXPONENT,
    LEGACY_PRCF1_SLOT_NAMES,
)
from tests.test_instrument_tof import (
    TYPE1,
    bank,
    iparm,
    prcf,
    rec,
    spectrum_records,
    write,
)

#: A distinct number in each of the first seven slots; slot 8 is ``s1ec``, an
#: anisotropic term the strict body refuses non-zero, so it stays 0 here.
SENTINELS = [0.0011, 0.2222, 0.0333, 0.0044, 5.5, 666.0, 77.0, 0.0]
EXPECTED = {"alpha0": 0.0011, "alpha1": 0.2222, "beta0": 0.0333,
            "beta1": 0.0044, "sig0": 5.5, "sig1": 666.0, "sig2": 77.0}


def legacy_bank(b=1, slots=SENTINELS, spectrum=()):
    return bank(b, profile=prcf(b, 1, 1, slots), spectrum=spectrum)


def profile_values(instrument) -> dict[str, float]:
    p = instrument.source.profile_tof
    return {k: getattr(p, k).value for k in EXPECTED}


# ------------------------------------------------ deviation 1: the PRCF block
def test_an_eight_slot_type_one_block_lands_under_the_confirmed_names(tmp_path):
    """Each slot of the 8-coefficient block lands under the documented name of
    the same slot of the twelve; one ``GSAS_IPARM_LEGACY_LAYOUT`` per file,
    level info, naming every bank that carried the block."""
    notes = []
    banks = read_lansce_iparm(write(tmp_path, iparm(legacy_bank(1), legacy_bank(2))),
                              diagnostics=notes)
    assert sorted(banks) == [1, 2]
    for b in (1, 2):
        assert profile_values(banks[b]) == EXPECTED
        assert not any(getattr(banks[b].source.profile_tof, k).vary for k in EXPECTED)
    (legacy,) = [n for n in notes if n.code == "GSAS_IPARM_LEGACY_LAYOUT"]
    assert legacy.level == "info"
    assert legacy.where == ["bank 1", "bank 2", "PRCF1"]
    assert "slots 1, 5, 8 under no name" in legacy.message


def test_the_slot_names_agree_with_gsas2s_destinations_through_both_readers():
    """The oracle's table, crossed against the package's two readers: every slot
    GSAS-II places, it places under the ``.instprm`` key the strict reader maps
    onto the same ``ProfileTOF`` field as the slot's documented name; the three
    it places nowhere are ``alp-0``, ``sig-0`` and ``s1ec``."""
    assert LEGACY_PRCF1_SLOT_NAMES == ("alp-0", "alp-1", "bet-0", "bet-1",
                                       "sig-0", "sig-1", "sig-2", "s1ec")
    assert len(GSAS2_PRCF1_DESTINATIONS) == len(LEGACY_PRCF1_SLOT_NAMES)
    unplaced = []
    for name, dest in zip(LEGACY_PRCF1_SLOT_NAMES, GSAS2_PRCF1_DESTINATIONS):
        if dest is None:
            unplaced.append(name)
        else:
            assert _INSTPRM_PROFILE[dest] == _PRCF_TO_PROFILE[1][name], name
    assert unplaced == ["alp-0", "sig-0", "s1ec"]


def test_the_eighth_slot_is_s1ec_and_a_nonzero_one_is_refused(tmp_path):
    """Restated, slot 8 is ``s1ec``: the strict body's anisotropic-term refusal
    applies to it unchanged."""
    slots = SENTINELS[:7] + [0.5]
    with pytest.raises(ValueError, match="s1ec = 0.5 is non-zero"):
        read_lansce_iparm(write(tmp_path, iparm(legacy_bank(1, slots=slots))))


def test_a_legacy_block_in_any_other_record_shape_is_refused(tmp_path):
    """The observed layout is two coefficient records, PRCF11 and PRCF12; one
    record, or a third, is not that layout and is refused rather than
    restated."""
    short = prcf(1, 1, 1, SENTINELS[:4], ncof=8)
    with pytest.raises(ValueError, match=r"records \[1\]; the legacy LANSCE layout"):
        read_lansce_iparm(write(tmp_path, iparm(bank(1, profile=short))))
    long = prcf(1, 1, 1, SENTINELS + [0.0] * 4, ncof=8)
    with pytest.raises(ValueError, match=r"records \[1, 2, 3\]"):
        read_lansce_iparm(write(tmp_path, iparm(bank(1, profile=long))))


def test_a_legacy_block_keeps_the_strict_column_checks(tmp_path):
    """The restated records go through the strict body, so a coefficient that
    runs across a field boundary is refused exactly as it is in a documented
    file."""
    b = legacy_bank(1)
    i = next(k for k, line in enumerate(b) if line.startswith("INS  1PRCF12"))
    b[i] = rec("INS  1PRCF12", (13, f"{5.5:15.6E}"), (26, "666.000"))
    with pytest.raises(ValueError, match="runs across the boundary"):
        read_lansce_iparm(write(tmp_path, iparm(b)))


# --------------------------------------------- deviation 2: the fifth ICOFF pair
@pytest.mark.parametrize("itype", [1, 2])
def test_a_nonzero_fifth_pair_is_refused_naming_the_measured_exponent(tmp_path, itype):
    """k = 5 is measured (GSAS-II's spectrum, fitted), and it is the power the
    model evaluates; the model refuses a non-zero P10/P11, so the bank is
    refused and the message names both facts."""
    assert LANSCE_FIFTH_PAIR_EXPONENT == 5
    coeffs = [4.5, 787.5, 0.11, 895.4, 0.0045, 0.0, 0.0, 0.0, 0.0, 5.0, 1e-3]
    text = iparm(legacy_bank(1, spectrum=spectrum_records(1, itype, coeffs)))
    with pytest.raises(ValueError) as err:
        read_lansce_iparm(write(tmp_path, text))
    msg = str(err.value)
    assert f"bank 1: ITYP {itype} carries a non-zero fifth ICOFF pair" in msg
    assert "P10*exp(-P11*T^5)" in msg
    assert "_refuse_inferred_pair" in msg


def test_the_fifth_pair_refusal_speaks_after_every_other_refusal(tmp_path):
    """A file wrong in some other way is refused for that reason first: the
    fifth pair is only refused once the rest of the file has been read."""
    coeffs = [1.0] + [0.0] * 8 + [5.0, 1e-3]
    text = iparm(legacy_bank(1, spectrum=spectrum_records(1, 1, coeffs)), htype="PNCR")
    with pytest.raises(ValueError, match="HTYPE 'PNCR'"):
        read_lansce_iparm(write(tmp_path, text))


# ------------------------------------------------- pass-through and the opt-in
@pytest.mark.parametrize("profile", ["type3", "type1_12", "spectrum"])
def test_a_spec_legal_file_reads_identically_through_both_readers(tmp_path, profile):
    """Anything the strict reader accepts, the bolt-on hands to it: the same
    ``Instrument``s, serialised byte for byte, and the same diagnostics."""
    if profile == "type3":
        banks = [bank(1), bank(2)]
    elif profile == "type1_12":
        banks = [bank(1, profile=prcf(1, 1, 1, TYPE1))]
    else:
        coeffs = [4.5, 787.5, 0.11, 895.4, 0.0045, 1086.2, 5.2e-4, -1397.0, 3.4e-4]
        banks = [bank(1, spectrum=spectrum_records(1, 1, coeffs, esds=[0.1] * 9))]
    path = write(tmp_path, iparm(*banks))
    strict_notes, legacy_notes = [], []
    strict = read_gsas_tof_iparm(path, diagnostics=strict_notes)
    legacy = read_lansce_iparm(path, diagnostics=legacy_notes)
    assert strict.keys() == legacy.keys()
    for b in strict:
        assert legacy[b].model_dump_json() == strict[b].model_dump_json()
    assert [n.model_dump() for n in legacy_notes] == [n.model_dump() for n in strict_notes]


def test_without_the_bolt_on_the_strict_refusal_stands(tmp_path):
    """Off by default: the strict reader refuses the legacy block, and its one
    added sentence names the reader that accepts it."""
    with pytest.raises(ValueError, match="with 8 coefficients") as err:
        read_gsas_tof_iparm(write(tmp_path, iparm(legacy_bank(1))))
    assert str(err.value).endswith(
        "An 8-coefficient type-1 block is the legacy LANSCE layout, read on "
        "request by rietx.io.legacy.read_lansce_iparm")


def test_a_strict_refusal_that_is_not_a_legacy_deviation_is_the_strict_readers(tmp_path):
    """A malformed record is refused with the strict reader's message, never
    a legacy one."""
    b = bank(1)
    b[1] = rec("INS  1BNKPAR", (13, f"{2.5:10.4f}"), (30, "46.60"))
    for reader in (read_gsas_tof_iparm, read_lansce_iparm):
        with pytest.raises(ValueError, match="runs across the boundary between TTHETA"):
            reader(write(tmp_path, iparm(b)))


# ------------------------------------------------------------ the real records
#: Instrument records (ICONS, BNKPAR, ITYP, ICOFF, PRCF set 1) of the LANSCE
#: NPDF run 7245 Si-standard calibration, from Michael Gaultois's 2014 NPDF
#: beamtime — publishable instrument metadata, copied verbatim column for
#: column except ITYP's CHKSUM field, left blank.  Labels, file names, the
#: IECOF/IECOR records and the other PRCF set are not carried.
NPDF_7245 = {
    1: """\
INS  1 ICONS   6911.21 -2.79     -19.420
INS  1BNKPAR      2.50       46.60
INS  1I ITYP    1    8.0000   49.0000
INS  1ICOFF1   0.449188E+01   0.787522E+03   0.111159E+00   0.895364E+03
INS  1ICOFF2   0.448643E-02   0.108620E+04   0.521265E-03  -0.139701E+04
INS  1ICOFF3   0.341671E-03   0.702966E+05   0.100000E+00   0.000000E+00
INS  1PRCF1     1    8   0.01000
INS  1PRCF11   0.000000E+00   0.146061E+00   0.434277E-01   0.233696E-01
INS  1PRCF12   0.000000E+00   0.353349E+03   0.000000E+00   0.000000E+00""",
    2: """\
INS  2 ICONS  11974.73   -2.3500   -3.6200
INS  2BNKPAR      1.50       90.
INS  2I ITYP    1    8.0000   45.0000
INS  2ICOFF1   0.109878E+02   0.970381E+04   0.165101E+00   0.505955E+04
INS  2ICOFF2   0.880267E-02  -0.109476E+04   0.341586E-03  -0.190635E+04
INS  2ICOFF3   0.159619E-03  -0.285890E+04   0.521191E-04   0.000000E+00
INS  2PRCF1     1    8   0.01000
INS  2PRCF11   0.000000E+00   0.446556E+00   0.549619E-01   0.276371E-02
INS  2PRCF12   0.000000E+00   0.299511E+03   0.000000E+00   0.000000E+00""",
    3: """\
INS  3 ICONS  14594.35   0.01    3.57
INS  3BNKPAR      1.50      119.
INS  3I ITYP    1    8.0000   45.0000
INS  3ICOFF1   0.613761E+02   0.691851E+05   0.168724E+00   0.244430E+05
INS  3ICOFF2   0.101438E-01  -0.133261E+06   0.473261E-02   0.554446E+05
INS  3ICOFF3   0.610942E-03   0.000000E+00   0.000000E+00   0.000000E+00
INS  3PRCF1     1    8   0.01000
INS  3PRCF11   0.000000E+00   0.518818E-01   0.355876E-01   0.309258E-02
INS  3PRCF12   0.000000E+00   0.198915E+03   0.000000E+00   0.000000E+00""",
    4: """\
INS  4 ICONS  16292.82   -4.2800    0.2900
INS  4BNKPAR      1.50      148.
INS  4I ITYP    1    8.0000   45.0000
INS  4ICOFF1   0.551915E+02   0.557738E+05   0.160750E+00   0.265429E+05
INS  4ICOFF2   0.972714E-02  -0.109071E+06   0.508520E-02   0.579425E+06
INS  4ICOFF3   0.138607E-02   0.000000E+00   0.000000E+00   0.000000E+00
INS  4PRCF1     1    8   0.01000
INS  4PRCF11   0.719136E-03   0.777253E-01   0.455314E-01   0.213342E-02
INS  4PRCF12   0.000000E+00   0.118693E+03   0.000000E+00   0.000000E+00""",
}


def npdf_file(*numbers, renumber=False) -> str:
    lines = [rec("INS   BANK  ", (13, f"{len(numbers):5d}")), rec("INS   HTYPE ", (15, "PNTR"))]
    for new, old in enumerate(numbers, start=1):
        block = NPDF_7245[old]
        if renumber:
            block = block.replace(f"INS {old:2d}", f"INS {new:2d}")
        lines.extend(block.splitlines())
    return "\n".join(lines) + "\n"


def test_the_real_calibration_reads_under_gsas2s_names(tmp_path):
    """NPDF 7245 banks 3 and 4 (the two whose fifth pair is zero and whose
    columns are aligned), renumbered 1-2: each coefficient GSAS-II v5.8.2
    printed for them lands on the field its name maps to.  Bank 4's slot 1
    (``alp-0`` by the manual's order) is read, where GSAS-II carries it under
    no name."""
    banks = read_lansce_iparm(write(tmp_path, npdf_file(3, 4, renumber=True)))
    three, four = banks[1].source, banks[2].source
    assert (three.difc.value, three.difa.value, three.tzero.value) == (14594.35, 0.01, 3.57)
    assert three.two_theta_bank_deg == 119.0 and four.two_theta_bank_deg == 148.0
    # GSAS-II: alpha, beta-0, beta-1, sig-1 (sig-0 and sig-2 read as 0)
    for src, gsas2 in ((three, (0.0518818, 0.0355876, 0.00309258, 198.915)),
                       (four, (0.0777253, 0.0455314, 0.00213342, 118.693))):
        p = src.profile_tof
        assert (p.alpha1.value, p.beta0.value, p.beta1.value, p.sig1.value) == gsas2
        assert p.sig0.value == 0.0 and p.sig2.value == 0.0
    assert three.profile_tof.alpha0.value == 0.0
    assert four.profile_tof.alpha0.value == 0.000719136
    assert four.incident_spectrum.itype == 1
    assert four.incident_spectrum.coefficients[3].value == 26542.9


def test_the_real_calibration_as_written_is_refused_for_its_bank_one_angle(tmp_path):
    """All four banks verbatim: bank 1 writes TTHETA ``46.60`` one column too
    wide (columns 30-34), which is not one of the two legacy deviations, so the
    strict column check refuses it through both readers — before the fifth
    pairs of banks 1 and 2 are reached."""
    path = write(tmp_path, npdf_file(1, 2, 3, 4))
    for reader in (read_gsas_tof_iparm, read_lansce_iparm):
        with pytest.raises(ValueError, match=r"'46\.60' in columns 30-34"):
            reader(path)

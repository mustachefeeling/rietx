"""The TOF instrument-parameter readers, on synthetic files written column by
column from the GSAS Technical Manual's FORTRAN formats (p. 221-223).

Every fixture is built here by :func:`rec`, which places each field in the
columns its format gives, so a test reads as the record layout it pins.  Each
test names the specification section it pins.
"""

from __future__ import annotations

import pytest

from rietx.io.instrument_tof import (
    read_gsas2_instprm,
    read_gsas_iparm,
    read_gsas_tof_iparm,
    read_instprm,
)
from rietx.schemas.instrument import ProfileTOF


def rec(key: str, *fields: tuple[int, str]) -> str:
    """An 80-column record: the 12-character key, then (start column, text)."""
    line = list(key.ljust(12)[:12].ljust(80))
    for col, text in fields:
        for k, ch in enumerate(text):
            line[col - 1 + k] = ch
    return "".join(line).rstrip()


def f10(x: float) -> str:
    return f"{x:10.4f}"


def e15(x: float) -> str:
    return f"{x:15.6E}"


def e15_block(key: str, values) -> str:
    return rec(key, *((13 + 15 * k, e15(v)) for k, v in enumerate(values)))


def icons(bank: int, difc: float, difa: float, zero: float, tail: str = "") -> str:
    fields = [(13, f10(difc)), (23, f10(difa)), (33, f10(zero))]
    if tail:
        fields.append((53, tail))
    return rec(f"INS {bank:2d} ICONS", *fields)


def bnkpar(bank: int, dist: float, ttheta: float) -> str:
    return rec(f"INS {bank:2d}BNKPAR", (13, f10(dist)), (23, f10(ttheta)))


def prcf(bank: int, n: int, ptyp: int, coeffs, ctof: float = 0.01, ncof=None) -> list[str]:
    ncof = len(coeffs) if ncof is None else ncof
    out = [rec(f"INS {bank:2d}PRCF{n} ", (13, f"{ptyp:5d}"), (18, f"{ncof:5d}"),
               (23, f"{ctof:10.5f}"))]
    for c in range(0, len(coeffs), 4):
        out.append(e15_block(f"INS {bank:2d}PRCF{n}{c // 4 + 1}", coeffs[c:c + 4]))
    return out


TYPE1 = [0.005, 0.146061, 0.0434277, 0.0233696, 7.0, 353.349, 11.0] + [0.0] * 5
TYPE3 = [0.45, 0.055, 0.003, 1.0, 300.0, 2.0, 0.5, 1.5, 0.25] + [0.0] * 12


def iparm(*bank_records: list[str], nbank: int | None = None, htype="PNTR") -> str:
    nbank = len(bank_records) if nbank is None else nbank
    lines = [rec("INS   BANK  ", (13, f"{nbank:5d}")), rec("INS   HTYPE ", (15, htype))]
    for block in bank_records:
        lines.extend(block)
    return "\n".join(lines) + "\n"


def bank(b=1, profile=None, extra=(), spectrum=()):
    lines = [icons(b, 6911.21, -2.79, -19.42), bnkpar(b, 2.5, 46.6)]
    lines += list(spectrum)
    lines += prcf(b, 1, 3, TYPE3) if profile is None else list(profile)
    return lines + list(extra)


def spectrum_records(b, itype, coeffs, esds=None, tmin=8.0, tmax=49.0):
    out = [rec(f"INS {b:2d}I ITYP", (13, f"{itype:5d}"), (18, f"{tmin:10.4f}"),
               (28, f"{tmax:10.4f}"), (38, f"{37556:10d}"))]
    padded = list(coeffs) + [0.0] * (12 - len(coeffs))
    for c in range(3):
        out.append(e15_block(f"INS {b:2d}ICOFF{c + 1}", padded[4 * c:4 * c + 4]))
    if esds is not None:
        pe = list(esds) + [0.0] * (12 - len(esds))
        for c in range(3):
            out.append(e15_block(f"INS {b:2d}IECOF{c + 1}", pe[4 * c:4 * c + 4]))
    return out


def write(tmp_path, text, name="bank.iparm"):
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return p


# ---------------------------------------------------------------- § 6.1 GSAS-I
def test_icons_gives_difc_difa_zero_for_a_pntr_bank(tmp_path):
    """SPEC § 6.1 / § 7.9: an ICONS record on a PNTR bank yields (DIFC, DIFA,
    ZERO); BNKPAR's TTHETA is the bank angle; everything arrives held."""
    banks = read_gsas_tof_iparm(write(tmp_path, iparm(bank(1), bank(2))))
    assert sorted(banks) == [1, 2]
    src = banks[1].source
    assert (src.difc.value, src.difa.value, src.tzero.value) == (6911.21, -2.79, -19.42)
    assert src.difb.value == 0.0          # GSAS-I has no DIFB field
    assert src.two_theta_bank_deg == 46.6
    assert src.l2_m == 2.5
    assert not any(getattr(src, n).vary for n in ("difc", "difa", "tzero", "difb"))
    assert read_gsas_iparm(write(tmp_path, iparm(bank(1)))).keys() == {1}


def test_icons_with_polarisation_columns_is_refused_on_a_neutron_bank(tmp_path):
    """SPEC § 6.1 / § 7.9: POLA, IPOLA, KRATIO are absent for neutron data, so
    non-blank columns 53-77 are refused."""
    b = bank(1)
    b[0] = icons(1, 6911.21, -2.79, -19.42, tail=f"{0.99:10.4f}")
    with pytest.raises(ValueError, match="columns 53-77"):
        read_gsas_tof_iparm(write(tmp_path, iparm(b)))


def test_the_default_type_three_block_is_read_in_the_manuals_order(tmp_path):
    """SPEC § 6.1: set 1 is the default; function 3's 21 coefficients map in the
    p. 148 order, alp → alpha1 (α = α₁/d), sig-* used as written (variances);
    the diagnostic names the order as an assumption and reports CTOF unused."""
    notes = []
    prof = read_gsas_tof_iparm(write(tmp_path, iparm(bank(1))),
                               diagnostics=notes)[1].source.profile_tof
    assert (prof.alpha0.value, prof.alpha1.value) == (0.0, 0.45)
    assert (prof.beta0.value, prof.beta1.value) == (0.055, 0.003)
    assert (prof.sig0.value, prof.sig1.value, prof.sig2.value) == (1.0, 300.0, 2.0)
    assert (prof.gam0.value, prof.gam1.value, prof.gam2.value) == (0.5, 1.5, 0.25)
    assert not any(getattr(prof, f).vary for f in ProfileTOF.model_fields)
    (read,) = [n for n in notes if n.code == "GSAS_IPARM_PROFILE_READ"]
    assert "assumption" in read.message and "CTOF" in read.message
    assert "alp, bet-0, bet-1, sig-0" in read.message


def test_a_type_one_block_maps_its_gaussian_terms(tmp_path):
    """SPEC § 6.1: function 1's 12 coefficients (p. 144), γ left at zero."""
    prof = read_gsas_tof_iparm(write(tmp_path, iparm(bank(1, profile=prcf(1, 1, 1, TYPE1)))))[1] \
        .source.profile_tof
    assert (prof.alpha0.value, prof.alpha1.value) == (0.005, 0.146061)
    assert prof.sig1.value == 353.349 and prof.sig2.value == 11.0
    assert (prof.gam0.value, prof.gam1.value, prof.gam2.value) == (0.0, 0.0, 0.0)


@pytest.mark.parametrize(("ptyp", "ncof"), [(1, 8), (1, 13), (3, 20), (2, 12)])
def test_a_prcf_block_with_the_wrong_ncof_is_refused_by_name(tmp_path, ptyp, ncof):
    """SPEC § 6.1 / § 7.9: NCOF must be 12 / 15 / 21 for PTYP 1 / 2 / 3; a short
    block is not padded and a long one is not truncated."""
    coeffs = [0.1] * ncof
    text = iparm(bank(1, profile=prcf(1, 1, ptyp, coeffs)))
    with pytest.raises(ValueError, match=f"function {ptyp} with {ncof} coefficients"):
        read_gsas_tof_iparm(write(tmp_path, text))


def test_a_non_zero_anisotropic_term_is_refused_not_dropped(tmp_path):
    """SPEC § 6.1 / § 8.2: s1ec etc. belong with the microstructure machinery."""
    coeffs = list(TYPE1)
    coeffs[7] = 0.25                       # s1ec
    with pytest.raises(ValueError, match="s1ec = 0.25"):
        read_gsas_tof_iparm(write(tmp_path, iparm(bank(1, profile=prcf(1, 1, 1, coeffs)))))


@pytest.mark.parametrize("ptyp", [2, 4, 5])
def test_a_default_set_of_a_function_not_evaluated_is_refused(tmp_path, ptyp):
    """SPEC § 1.2 / § 6.1: PTYP 4 and 5 (and the Ikeda-Carpenter PTYP 2) are
    refused by name, PTYP in the message, when they are the default."""
    coeffs = [0.1] * (15 if ptyp == 2 else 12)
    with pytest.raises(ValueError, match=f"PTYP = {ptyp}"):
        read_gsas_tof_iparm(write(tmp_path, iparm(bank(1, profile=prcf(1, 1, ptyp, coeffs)))))


def test_a_non_default_set_is_reported_and_skipped(tmp_path):
    """SPEC § 6.1: the first set is the default regardless of PTYP; the rest are
    not read (here a type-4 alternative, which is also not evaluated)."""
    notes = []
    profile = prcf(1, 1, 3, TYPE3) + prcf(1, 2, 4, [0.3] * 12)
    got = read_gsas_tof_iparm(write(tmp_path, iparm(bank(1, profile=profile))),
                              diagnostics=notes)[1].source.profile_tof
    assert got.alpha1.value == 0.45
    declined = [n for n in notes if n.code == "GSAS_IPARM_PROFILE_DECLINED"]
    assert len(declined) == 1 and "set 2" in declined[0].message


def test_prcf_set_numbers_must_be_the_documented_ones(tmp_path):
    """SPEC § 6.1: n = 1 … NTYP; a blank or zero set number is not a documented
    key, and without set 1 the default is unstated."""
    blank = [line.replace("PRCF1", "PRCF ") for line in prcf(1, 1, 3, TYPE3)]
    with pytest.raises(ValueError, match="set number"):
        read_gsas_tof_iparm(write(tmp_path, iparm(bank(1, profile=blank))))
    with pytest.raises(ValueError, match="without set 1"):
        read_gsas_tof_iparm(write(tmp_path, iparm(bank(1, profile=prcf(1, 2, 3, TYPE3)))))


def test_the_profile_is_the_same_whether_or_not_diagnostics_were_asked_for(tmp_path):
    """What a reader returns never depends on the diagnostics channel."""
    p = write(tmp_path, iparm(bank(1)))
    assert (read_gsas_tof_iparm(p)[1].model_dump()
            == read_gsas_tof_iparm(p, diagnostics=[])[1].model_dump())


@pytest.mark.parametrize("htype", ["PXCR", "PNCR", "WHAT"])
def test_an_htype_not_beginning_pnt_is_refused(tmp_path, htype):
    """SPEC § 6.1 / § 7.9: only a neutron TOF powder bank (PNT…) is read."""
    with pytest.raises(ValueError, match="HTYPE"):
        read_gsas_tof_iparm(write(tmp_path, iparm(bank(1), htype=htype)))


def test_a_bank_with_no_angle_is_refused(tmp_path):
    """SPEC § 6.1 (and GM p. 222: BNKPAR is 'not needed for CW instruments' —
    it is a TOF bank's record): without TTHETA there is no bank angle."""
    b = [line for line in bank(1) if "BNKPAR" not in line]
    with pytest.raises(ValueError, match="no BNKPAR record"):
        read_gsas_tof_iparm(write(tmp_path, iparm(b)))


def _with(b, key, line):
    """``b`` with the record whose key contains ``key`` replaced by ``line``."""
    return [line if key in old[:12] else old for old in b]


def test_a_number_running_across_a_field_boundary_is_refused(tmp_path):
    """Module docstring § Column overrun: the phase-C fixture wrote TTHETA
    ``46.60`` in columns 30-34, so TTHETA's own columns 23-32 held ``46.``
    and read 46.0 with no word said.  It is refused, naming the record, both
    fields' columns and the raw text."""
    b = _with(bank(1), "BNKPAR", rec("INS  1BNKPAR", (13, f10(2.5)), (30, "46.60")))
    with pytest.raises(ValueError, match=r"'INS  1BNKPAR'.*'46\.60' in columns "
                                         r"30-34.*TTHETA \(columns 23-32\).*TILT "
                                         r"\(columns 33-42\)"):
        read_gsas_tof_iparm(write(tmp_path, iparm(b)))


def test_the_right_aligned_phase_c_record_reads_its_angle(tmp_path):
    """The same record right-aligned, as the corrected fixture writes it."""
    b = _with(bank(1), "BNKPAR", "INS  1BNKPAR      2.50     46.60")
    src = read_gsas_tof_iparm(write(tmp_path, iparm(b)))[1].source
    assert (src.two_theta_bank_deg, src.l2_m) == (46.60, 2.5)


def test_packed_full_width_fields_are_two_numbers(tmp_path):
    """A right-aligned field whose first column is occupied is full, so two
    fields touching with no blank anywhere in the right one are read as two —
    the class the check cannot tell from an overrun ending on a boundary."""
    b = _with(bank(1), "BNKPAR", rec("INS  1BNKPAR", (13, f10(2.5)),
                                     (23, "46.6000000")))
    coeffs = [0.45, 0.055, 0.003, 1.0]
    full = rec("INS  1PRCF11", *((13 + 15 * k, f"{v:15.9E}")
                                 for k, v in enumerate(coeffs)))
    assert all(len(f"{v:15.9E}") == 15 for v in coeffs)
    b = _with(b, "PRCF11", full)
    src = read_gsas_tof_iparm(write(tmp_path, iparm(b)))[1].source
    assert src.two_theta_bank_deg == 46.6
    assert (src.profile_tof.alpha1.value, src.profile_tof.sig0.value) == (0.45, 1.0)


def test_a_blank_field_still_reads_as_zero(tmp_path):
    """The check is about occupied columns; a blank DIST keeps the FORTRAN
    reading of zero, which the reader carries as no flight path."""
    b = _with(bank(1), "BNKPAR", rec("INS  1BNKPAR", (23, f10(46.6))))
    src = read_gsas_tof_iparm(write(tmp_path, iparm(b)))[1].source
    assert (src.two_theta_bank_deg, src.l2_m) == (46.6, None)


@pytest.mark.parametrize("key, line, fields", [
    ("BANK", rec("INS   BANK  ", (17, "12")), "NBANK"),
    (" ICONS", rec("INS  1 ICONS", (13, "   6911.21"), (23, "3"), (33, f10(-19.42))),
     "DIFC"),
    (" ICONS", rec("INS  1 ICONS", (13, f10(6911.21)), (23, f10(-2.79)),
                   (38, "-19.42")), "ZERO .columns 33-42. and the 10X skip"),
    ("BNKPAR", rec("INS  1BNKPAR", (13, f10(2.5)), (23, f10(46.6)), (63, "    1"),
                   (68, "    12"), (74, "3")), "ITUBE"),
    ("PRCF1 ", rec("INS  1PRCF1 ", (13, "    3"), (18, "   21"), (23, "0.01")),
     "NCOF .columns 18-22. and CTOF"),
    ("PRCF11", rec("INS  1PRCF11", (13, e15(0.45)), (28, e15(0.055)),
                   (43, "3.000000E-03"), (58, e15(1.0))), "coefficient field 2"),
])
def test_every_parsed_record_is_checked(tmp_path, key, line, fields):
    """Every fixed-column record the reader parses carries the check, the
    columns after the last field included."""
    text = iparm(bank(1)).splitlines()
    text = [line if key in old[:12] else old for old in text]
    with pytest.raises(ValueError, match=f"runs across the boundary.*{fields}"):
        read_gsas_tof_iparm(write(tmp_path, "\n".join(text) + "\n"))


def test_the_spectrum_records_are_checked(tmp_path):
    """I ITYP and the ICOFF block (spectrum records) carry the check too."""
    spec = spectrum_records(1, 1, ELEVEN)
    spec[0] = rec("INS  1I ITYP", (13, "    1"), (18, "   8.00001"), (28, "5"))
    with pytest.raises(ValueError, match="runs across.*TMIN"):
        read_gsas_tof_iparm(write(tmp_path, iparm(bank(1, spectrum=spec))))
    spec = spectrum_records(1, 1, ELEVEN)
    spec[1] = spec[1][:72] + "12"
    with pytest.raises(ValueError, match="runs across.*coefficient field 4.*after "
                                         "the last field"):
        read_gsas_tof_iparm(write(tmp_path, iparm(bank(1, spectrum=spec))))


def test_nbank_and_the_banks_present_must_agree(tmp_path):
    """SPEC § 6.1: the per-bank records repeat for each of NBANK banks."""
    with pytest.raises(ValueError, match="bank 2 has no ICONS"):
        read_gsas_tof_iparm(write(tmp_path, iparm(bank(1), nbank=2)))
    with pytest.raises(ValueError, match="NBANK is 1"):
        read_gsas_tof_iparm(write(tmp_path, iparm(bank(1), bank(2), nbank=1)))


# ------------------------------------------------------ § 6.1 incident spectrum
ELEVEN = [5.0, 0.8, 0.11, 0.9, 0.0045, 1.0, 5e-4, -1.4, 3.4e-4, 0.0, 0.0]


def test_ityp_and_icoff_are_read_in_milliseconds_with_their_esds(tmp_path):
    """SPEC § 4.3 / § 6.1: ITYP's TMIN/TMAX are ms (carried in µs), ICOFF are
    the coefficients (in ms units), IECOF their esds; IECOR and CHKSUM have no
    slot and are reported dropped."""
    notes = []
    spec_recs = spectrum_records(1, 1, ELEVEN, esds=[0.1] * 11)
    spec_recs.append(rec("INS  1IECOR1", (13, " 1.000-0.110")))
    src = read_gsas_tof_iparm(write(tmp_path, iparm(bank(1, spectrum=spec_recs))),
                              diagnostics=notes)[1].source
    sp = src.incident_spectrum
    assert sp.itype == 1
    assert (sp.tof_min_us, sp.tof_max_us) == (8000.0, 49000.0)
    assert [p.value for p in sp.coefficients] == pytest.approx(ELEVEN)
    assert len(sp.coefficients) == 11
    assert sp.coefficients[0].stderr == pytest.approx(0.1)
    assert not any(p.vary for p in sp.coefficients)
    (dropped,) = [n for n in notes if n.code == "GSAS_IPARM_FIELD_DROPPED"]
    assert "IECOR1" in dropped.where and "CHKSUM" in dropped.where


def test_no_ityp_record_is_no_spectrum(tmp_path):
    """SPEC § 6.1: a bank declaring no ITYP carries none (ITYP 0)."""
    sp = read_gsas_tof_iparm(write(tmp_path, iparm(bank(1))))[1].source.incident_spectrum
    assert sp.itype == 0 and sp.coefficients == []


def test_a_spectrum_block_that_disagrees_with_its_type_is_refused(tmp_path):
    """SPEC § 4.3 / § 6.1: a short block, a non-zero unused slot, the inferred
    fifth pair non-zero, ITYP 10 and an undefined ITYP — each refused by name."""
    good = spectrum_records(1, 1, ELEVEN)
    short = [r for r in good if "ICOFF3" not in r]
    with pytest.raises(ValueError, match="holds"):
        read_gsas_tof_iparm(write(tmp_path, iparm(bank(1, spectrum=short))))
    gap = [r for r in good if "ICOFF2" not in r]
    with pytest.raises(ValueError, match="consecutive run"):
        read_gsas_tof_iparm(write(tmp_path, iparm(bank(1, spectrum=gap))))
    with pytest.raises(ValueError, match="P12 = 0.7"):
        read_gsas_tof_iparm(write(tmp_path, iparm(bank(1, spectrum=spectrum_records(
            1, 1, ELEVEN + [0.7])))))
    with pytest.raises(ValueError, match="P10 = 70000.0 is non-zero"):
        read_gsas_tof_iparm(write(tmp_path, iparm(bank(1, spectrum=spectrum_records(
            1, 1, ELEVEN[:9] + [70000.0, 0.1])))))
    with pytest.raises(ValueError, match="point-by-point"):
        read_gsas_tof_iparm(write(tmp_path, iparm(bank(1, spectrum=spectrum_records(
            1, 10, [])))))
    with pytest.raises(ValueError, match="ITYP 7 is not an incident-spectrum"):
        read_gsas_tof_iparm(write(tmp_path, iparm(bank(1, spectrum=spectrum_records(
            1, 7, ELEVEN)))))


# -------------------------------------------------------------- § 6.2 GSAS-II
INSTPRM = """\
#GSAS-II instrument parameter file
Type:PNT
Bank:1.0
fltPath:63.183
2-theta:90.0
Azimuth:0.0
difC:22586.9009385
difA:-0.981525860367
difB:0.0
Zero:0.0
alpha:4.0
beta-0:0.001
beta-1:3.63
beta-q:0.0
sig-0:0.0
sig-1:10.0
sig-2:403.353978439
sig-q:0.0
X:0.0
Y:0.0
Z:0.0
"""


def test_an_instprm_reads_the_named_keys(tmp_path):
    """SPEC § 6.2: difC/difA/difB/Zero, alpha → alpha1, beta-0/1, sig-0/1/2;
    the named-but-lawless keys at 0 and the metadata are reported dropped."""
    notes = []
    ins = read_gsas2_instprm(write(tmp_path, INSTPRM, "b.instprm"), diagnostics=notes)
    src = ins.source
    assert src.difc.value == pytest.approx(22586.9009385)
    assert src.difa.value == pytest.approx(-0.981525860367)
    assert src.two_theta_bank_deg == 90.0
    prof = src.profile_tof
    assert (prof.alpha0.value, prof.alpha1.value) == (0.0, 4.0)
    assert (prof.beta0.value, prof.beta1.value) == (0.001, 3.63)
    assert prof.sig2.value == pytest.approx(403.353978439)
    (dropped,) = [n for n in notes if n.code == "GSAS2_INSTPRM_FIELD_DROPPED"]
    assert {"beta-q", "sig-q", "Z", "X", "Y", "Bank", "fltPath"} <= set(dropped.where)
    assert read_instprm(write(tmp_path, INSTPRM, "c.instprm")).model_dump() == ins.model_dump()


def test_an_unknown_instprm_key_is_refused_with_the_key_in_the_message(tmp_path):
    """SPEC § 6.2 / § 7.9: never read an unrecognised key as zero."""
    with pytest.raises(ValueError, match="'alpha-7'"):
        read_gsas2_instprm(write(tmp_path, INSTPRM + "alpha-7:0.0\n", "b.instprm"))


@pytest.mark.parametrize("key", ["beta-q", "sig-q", "Z", "X", "Y"])
def test_a_non_zero_coefficient_with_no_published_law_is_refused(tmp_path, key):
    """SPEC § 6.2 / § 8.4: beta-q, sig-q, Z and the TOF laws of X, Y are not
    published, so a non-zero value is refused by name."""
    text = INSTPRM.replace(f"\n{key}:0.0\n", f"\n{key}:0.31\n")
    with pytest.raises(ValueError, match=f"{key} is 0.31"):
        read_gsas2_instprm(write(tmp_path, text, "b.instprm"))


def test_difb_is_carried(tmp_path):
    """SPEC § 3.3 / § 6.2: a non-zero difB is read, never silently dropped."""
    src = read_gsas2_instprm(write(tmp_path, INSTPRM.replace("difB:0.0", "difB:-24.5"),
                                   "b.instprm")).source
    assert src.difb.value == -24.5


def test_the_unpublished_grammar_is_refused_outside_its_observed_subset(tmp_path):
    """SPEC § 6.2: a line without ':' or a repeated key (how a second bank would
    appear) is refused with a message that says the grammar is not published."""
    with pytest.raises(ValueError, match="not published"):
        read_gsas2_instprm(write(tmp_path, INSTPRM + "garbage line\n", "b.instprm"))
    with pytest.raises(ValueError, match="appears twice"):
        read_gsas2_instprm(write(tmp_path, INSTPRM + "difC:1.0\n", "b.instprm"))


def test_a_non_tof_instprm_and_a_negative_variance_are_refused(tmp_path):
    """SPEC § 6.2: Type must be PNT; sig-* are variance coefficients."""
    with pytest.raises(ValueError, match="Type PXC"):
        read_gsas2_instprm(write(tmp_path, INSTPRM.replace("Type:PNT", "Type:PXC"), "b.instprm"))
    with pytest.raises(ValueError, match="negative"):
        read_gsas2_instprm(write(tmp_path, INSTPRM.replace("sig-1:10.0", "sig-1:-10.0"),
                                 "b.instprm"))

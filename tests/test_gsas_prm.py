"""``read_gsas_prm``: the GSAS-I ``.prm`` instrument-parameter importer.

Every fixture here is **hand-written**, not vendored — the corpus this reader
was built and verified against lives outside the repository (WP campaign
archive), never as a committed file, real sample name or collaborator path.
``_prm`` below reproduces the *shapes* real files take (a plain dominant-case
bank, the same shape with inline coefficient labels, a short counted block,
a synthetic time-of-flight bank mimicking ``BNKPAR``/per-bank ``PRCF``) with
invented numbers, so nothing here proves a real calibration — only that the
parser reads what the manual says and refuses what it does not.
"""

from __future__ import annotations

import pytest

import rietx as rx
from rietx.io.instrument_profile import read_gsas_prm


def _prm(*, htype="PXCR", bank=1, icons="0.5000000    0.0000    0.0000"
                                        "               0.990    0     0.500",
         prcf_type=3, ncoef=19, cutoff="0.00100",
         coeffs=(1.0, -0.5, 0.2, 0.0, 0.15, 0.0, 0.0011, 0.0022,
                 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
         labels=None, per_line=4, extra_headers=()) -> str:
    """Build a synthetic ``.prm`` text, one dominant-case bank by default.

    ``coeffs`` are packed across ``PRCF11``..``PRCF1n`` continuation lines,
    ``per_line`` values to a line (the real corpus's own packing) — a
    **counted** layout: the header states ``ncoef`` and that is what a
    correct reader consumes, so a test can freely pass fewer ``coeffs`` than
    the header claims to exercise the short-file refusal, or more to exercise
    truncation.  ``labels`` optionally maps a 1-based coefficient position to
    an inline GSAS label token (``{1: "GU", 2: "GV", ...}``), reproducing the
    2-in-1500 real files that print one.  ``extra_headers`` inserts
    additional ``INS 1PRCF1 ...`` header lines *before* the coefficient lines
    of the (single) block built here, to exercise the "declared twice"
    refusal.
    """
    labels = labels or {}
    lines = [
        "INS   BANK  " + str(bank),
        "INS   HTYPE   " + htype,
        f"INS  1 ICONS {icons}",
        "INS  1 IRAD     0",
        "INS  1I HEAD  synthetic test fixture",
        "INS  1I ITYP    0    0.0000  180.0000         1",
    ]
    for h in extra_headers:
        lines.append(h)
    lines.append(f"INS  1PRCF1     {prcf_type}   {ncoef}   {cutoff}")
    for start in range(0, len(coeffs), per_line):
        chunk = coeffs[start:start + per_line]
        toks = []
        for i, v in enumerate(chunk, start=start + 1):
            if i in labels:
                toks.append(f"{labels[i]} {v:.6f}")
            else:
                toks.append(f"{v:.6f}")
        idx = start // per_line + 1
        lines.append(f"INS  1PRCF1{idx}   " + "   ".join(toks))
    return "\n".join(lines) + "\n"


def _synthetic_pntr(path):
    """A synthetic time-of-flight bank, shaped like the two real ``PNTR``
    files (``BNKPAR``, per-bank ``PRCF`` with a space before the coefficient
    index rather than the CW ``PRCF1n`` concatenation) but with invented
    numbers throughout.
    """
    text = (
        "INS   BANK  1\n"
        "INS   HTYPE   PNTR\n"
        "INS  1 ICONS    500.00     -0.10     -1.00\n"
        "INS  1BNKPAR    2.0000      9.00      0.00    .00000     .3000    1    1\n"
        "INS  1PRCF      2   15   0.00100\n"
        "INS  1PRCF 1   0.000000E+00   0.200000E+00   0.300000E+02   0.500000E+02\n"
        "INS  1PRCF 2   0.000000E+00   0.150000E+03   0.000000E+00   0.000000E+00\n"
        "INS  1PRCF 3   0.000000E+00   0.000000E+00   0.000000E+00   0.000000E+00\n"
        "INS  1PRCF 4   0.000000E+00   0.000000E+00   0.000000E+00\n"
    )
    path.write_text(text, encoding="utf-8")
    return path


# --------------------------------------------------------------- dominant case

def test_reads_the_dominant_case(tmp_path):
    """A single-bank PXCR / profile-type-3 file — the case the corpus is
    almost entirely made of (1499/1508 read successfully in the campaign's
    corpus run) — returns an ``Instrument`` with every field this reader maps.
    """
    p = tmp_path / "synthetic.prm"
    p.write_text(_prm(), encoding="utf-8")
    inst = read_gsas_prm(p)

    assert inst.source.primary_wavelength == pytest.approx(0.5)
    assert inst.source.polarization.value == pytest.approx(0.990)
    # GU/GV/GW: centidegrees^2 -> degrees^2 is /1e4; LX/LY: centidegrees -> degrees is /1e2
    assert inst.profile.u.value == pytest.approx(1.0 / 1e4)
    assert inst.profile.v.value == pytest.approx(-0.5 / 1e4)
    assert inst.profile.w.value == pytest.approx(0.2 / 1e4)
    assert inst.profile.x.value == pytest.approx(0.15 / 1e2)
    assert inst.profile.y.value == pytest.approx(0.0)
    assert inst.geometry.axial_sl.value == pytest.approx(0.0011)
    assert inst.geometry.axial_hl.value == pytest.approx(0.0022)
    assert inst.geometry.kind == "debye_scherrer"


def test_every_parameter_comes_back_frozen(tmp_path):
    """A ``.prm`` is a beamline calibration, not a starting guess — the same
    ``vary=False`` contract :func:`load_instrument_profile` gives its native
    JSON profiles.
    """
    p = tmp_path / "synthetic.prm"
    p.write_text(_prm(), encoding="utf-8")
    inst = read_gsas_prm(p)

    assert inst.zero_shift.vary is False
    assert inst.source.polarization.vary is False
    assert inst.profile.u.vary is False
    assert inst.profile.v.vary is False
    assert inst.profile.w.vary is False
    assert inst.profile.x.vary is False
    assert inst.profile.y.vary is False
    assert inst.geometry.axial_sl.vary is False
    assert inst.geometry.axial_hl.vary is False


def test_inline_coefficient_labels_are_prose_not_coefficients(tmp_path):
    """2 of 1500 real files print ``GU``/``GV``/``GW``/``LX``/``S/L``/``H/L``
    beside the numbers on the ``PRCF11``/``PRCF12`` lines.  The header's
    coefficient count is a count of **numbers**, so a label token must be
    skipped rather than consumed as one of them — otherwise every coefficient
    after the first label shifts by one position and the file reads as a
    different (wrong) instrument while raising nothing.
    """
    labelled = _prm(labels={1: "GU", 2: "GV", 3: "GW", 5: "LX",
                            7: "S/L", 8: "H/L"})
    bare = _prm()
    p1, p2 = tmp_path / "labelled.prm", tmp_path / "bare.prm"
    p1.write_text(labelled, encoding="utf-8")
    p2.write_text(bare, encoding="utf-8")

    a, b = read_gsas_prm(p1), read_gsas_prm(p2)
    assert a.profile.u.value == pytest.approx(b.profile.u.value)
    assert a.profile.v.value == pytest.approx(b.profile.v.value)
    assert a.profile.w.value == pytest.approx(b.profile.w.value)
    assert a.profile.x.value == pytest.approx(b.profile.x.value)
    assert a.geometry.axial_sl.value == pytest.approx(b.geometry.axial_sl.value)
    assert a.geometry.axial_hl.value == pytest.approx(b.geometry.axial_hl.value)


def test_short_counted_block_without_a_fifth_continuation_line(tmp_path):
    """The block is a **counted** layout: ``ncoef`` says how many numbers
    follow, not how many ``PRCF1n`` lines are present.  A file whose count
    only needs four continuation lines (no ``PRCF15``) must read exactly as
    well as a five-line one — the count governs, never the line that happens
    to be last.
    """
    coeffs = (1.0, -0.5, 0.2, 0.0, 0.15, 0.0, 0.0011, 0.0022,
              0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)  # 16 values, 4 lines of 4
    p = tmp_path / "short.prm"
    p.write_text(_prm(ncoef=16, coeffs=coeffs), encoding="utf-8")
    inst = read_gsas_prm(p)
    assert inst.profile.w.value == pytest.approx(0.2 / 1e4)
    assert inst.geometry.axial_hl.value == pytest.approx(0.0022)


def test_short_file_missing_declared_coefficients_raises(tmp_path):
    """The header claims more coefficients than the file actually supplies —
    a truncated write, or a hand edit that deleted a continuation line.
    Padding the missing values or reading whatever is present are both a
    plausible wrong instrument; raising is the only answer that is not.
    """
    p = tmp_path / "truncated.prm"
    # the header says 19, only 3 are given
    p.write_text(_prm(ncoef=19, coeffs=(1.0, -0.5, 0.2)), encoding="utf-8")
    with pytest.raises(ValueError, match="declares 19 coefficients but only"):
        read_gsas_prm(p)


# ----------------------------------------------------------------- refusals

def test_pntr_time_of_flight_is_refused_by_name(tmp_path):
    p = _synthetic_pntr(tmp_path / "tof.prm")
    with pytest.raises(ValueError, match="(?i)time-of-flight"):
        read_gsas_prm(p)


@pytest.mark.parametrize("prof_type", [1, 2, 4])
def test_unsupported_prcf_profile_types_are_refused_by_name(tmp_path, prof_type):
    """Types 1, 2 and 4 each have their own, independently-defined Fortran
    coefficient layout in the GSAS manual — none is a truncation or extension
    of type 3's — and no real (non-template) file of any of them was found in
    the corpus this reader was built against, so none is read.
    """
    p = tmp_path / f"type{prof_type}.prm"
    p.write_text(_prm(prcf_type=prof_type, ncoef=6,
                      coeffs=(1.0, -0.5, 0.2, 0.0, 0.15, 0.0)),
                 encoding="utf-8")
    with pytest.raises(ValueError, match=str(prof_type)):
        read_gsas_prm(p)


def test_unrecognised_htype_is_refused_by_name(tmp_path):
    p = tmp_path / "mystery.prm"
    p.write_text(_prm(htype="QSTEP"), encoding="utf-8")
    with pytest.raises(ValueError, match="QSTEP"):
        read_gsas_prm(p)


def test_a_file_with_no_bank_or_htype_record_raises(tmp_path):
    """Junk that merely carries a ``.prm`` suffix (5 of the 1508 real
    filenames scanned in the campaign's corpus run turned out to be unrelated
    tab-separated data, one a raw resource-fork attachment) must not be
    silently accepted as an empty or default instrument."""
    p = tmp_path / "not_really_a_prm.prm"
    p.write_text("just some\ntext\tfile\t1\t2\t3\n" * 5, encoding="utf-8")
    with pytest.raises(ValueError, match="not a GSAS-I instrument-parameter file"):
        read_gsas_prm(p)


def test_multi_bank_pxcr_is_refused(tmp_path):
    """Every real ``PXCR`` file in the corpus declares exactly one bank; a
    declared bank count of anything else has no real fixture behind it, so
    reading only the first bank (silently dropping the rest) is refused."""
    p = tmp_path / "multibank.prm"
    p.write_text(_prm(bank=2), encoding="utf-8")
    with pytest.raises(ValueError, match="BANK 2"):
        read_gsas_prm(p)


def test_duplicate_prcf1_header_for_one_bank_is_refused(tmp_path):
    """The one real file that declares its profile function twice under one
    bank (a stock GSAS example stacking types 2/3/4 with placeholder values)
    is ambiguous about which applies — refused rather than picking the first
    or the last silently."""
    p = tmp_path / "duplicate.prm"
    p.write_text(_prm(extra_headers=("INS  1PRCF1     3   19   0.00100",
                                     "INS  1PRCF11   0.0   0.0   0.0   0.0",
                                     "INS  1PRCF12   0.0   0.0   0.0   0.0",
                                     "INS  1PRCF13   0.0   0.0   0.0   0.0",
                                     "INS  1PRCF14   0.0   0.0   0.0   0.0",
                                     "INS  1PRCF15   0.0   0.0   0.0")),
                 encoding="utf-8")
    with pytest.raises(ValueError, match="more than once"):
        read_gsas_prm(p)


def test_icons_with_an_unexpected_field_count_is_refused(tmp_path):
    """The one real corpus file with a 7-field ICONS record (a stock GSAS
    example carrying a real Kα1/Kα2 doublet) is refused rather than guessing
    which of the 6 established fields is missing or which is the extra one."""
    p = tmp_path / "sevenfield.prm"
    p.write_text(_prm(icons="1.5405  1.5443  0.0  0  0.7  0  0.5"), encoding="utf-8")
    with pytest.raises(ValueError, match="7 fields"):
        read_gsas_prm(p)


def test_nonzero_second_wavelength_is_refused(tmp_path):
    p = tmp_path / "doublet.prm"
    p.write_text(_prm(icons="0.5  1.5443  0.0  0.990  0  0.5"), encoding="utf-8")
    with pytest.raises(ValueError, match="second wavelength"):
        read_gsas_prm(p)


def test_nonzero_zero_point_is_refused(tmp_path):
    """ICONS field 3 (GSAS ``ZERO``) has a disputed unit convention
    (``io/recipe.py``'s ``_read_zero_shift``) and no real file in the corpus
    has a non-zero value to settle it against — refused rather than mapped on
    either guess."""
    p = tmp_path / "nonzero_zero.prm"
    p.write_text(_prm(icons="0.5  0.0  0.0123  0.990  0  0.5"), encoding="utf-8")
    with pytest.raises(ValueError, match="ZERO"):
        read_gsas_prm(p)


def test_nonzero_reserved_icons_field_is_refused(tmp_path):
    p = tmp_path / "reserved.prm"
    p.write_text(_prm(icons="0.5  0.0  0.0  0.990  7  0.5"), encoding="utf-8")
    with pytest.raises(ValueError, match="field 5"):
        read_gsas_prm(p)


def test_nonzero_gp_coefficient_is_refused(tmp_path):
    """PRCF position 4 (GSAS ``GP``) is always 0 in every real file this
    reader was built against and has no mapping onto ``ProfileTCHZ`` — a
    non-zero value is refused rather than silently dropped."""
    coeffs = (1.0, -0.5, 0.2, 0.9, 0.15, 0.0, 0.0011, 0.0022,
              0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    p = tmp_path / "nonzero_gp.prm"
    p.write_text(_prm(coeffs=coeffs), encoding="utf-8")
    with pytest.raises(ValueError, match="'GP'"):
        read_gsas_prm(p)


def test_nonzero_reserved_prcf_term_is_refused(tmp_path):
    """Every coefficient past position 8 (``trns``/``shft``/``sfec`` and
    further reserved slots) is 0 in every real type-3 file this reader was
    checked against (1499/1499 in the campaign's corpus scan) — a non-zero
    one here is unidentified, not dropped."""
    coeffs = (1.0, -0.5, 0.2, 0.0, 0.15, 0.0, 0.0011, 0.0022,
              0.0, 0.0, 0.4, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    p = tmp_path / "nonzero_reserved.prm"
    p.write_text(_prm(coeffs=coeffs), encoding="utf-8")
    with pytest.raises(ValueError, match="coefficient 11 of 19"):
        read_gsas_prm(p)


def test_read_gsas_prm_is_exported_at_top_level():
    assert rx.read_gsas_prm is read_gsas_prm

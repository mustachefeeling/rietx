"""The pattern readers: dispatch, the option vocabulary, and what they repair.

Three things are asserted here that nothing else can see once a file is read.

**A repair is only allowed where it can be reported.**  Root CLAUDE.md's rule is
that a silent correction is a reader's to make, and only where the deviation is
a *report* rather than a *contradiction*.  ``ascending`` is that rule applied to
2θ ordering, and the tests below are one per row of its table — including the
two rows that **raise**, which are the load-bearing half: a file whose ranges are
stitched or whose duplicate points disagree has more than one defensible reading,
and picking one silently is exactly what this package refuses.

**A dropped reader option is not the same as a typo'd one.**  The first is
normal (a form carries a value across a change of file) and is reported; the
second is a caller error and raises.  Both are ``reader_options_for``'s.

**A sniff is bounded.**  ``head`` reads a fixed prefix, so the cost of asking ten
formats "is this yours?" does not scale with the pattern.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import pxrdref as pr
from pxrdref.io.formats import (
    METADATA_KEYS,
    PATTERN_FORMATS,
    head,
    metadata,
    multiscan_default,
)
from pxrdref.io.formats.base import PatternFormat, ascending, reader_options_for
from pxrdref.io.readers import identify_format, list_scans


def write_xy(path, tt, y, sig=None):
    rows = ([f"{a} {b}" for a, b in zip(tt, y)] if sig is None
            else [f"{a} {b} {c}" for a, b, c in zip(tt, y, sig)])
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return path


# ----------------------------------------------------------------- ascending
def test_a_scan_stored_high_to_low_is_reversed_and_says_so(tmp_path):
    """The same measurement, stored backwards — reversing loses nothing.

    Several vendor formats write a scan measured high→low, and ``PatternData``
    requires strictly increasing 2θ, so before this the file simply did not
    open.  The reversal is a *report*: no datum is invented, dropped or chosen.
    """
    p = write_xy(tmp_path / "down.xy", [30.0, 20.0, 10.0], [3.0, 2.0, 1.0])
    notes: list = []
    data = pr.read_pattern(p, diagnostics=notes)

    assert data.two_theta == [10.0, 20.0, 30.0]
    assert data.intensity == [1.0, 2.0, 3.0]     # carried with its own 2θ
    assert [d.code for d in notes] == ["PATTERN_SCAN_REVERSED"]
    # and with no list to report into it still reads: the channel is optional
    assert pr.read_pattern(p).two_theta == [10.0, 20.0, 30.0]


def test_the_esd_column_is_reversed_with_the_points_it_belongs_to(tmp_path):
    """σ is per point, so a reversal that moved only 2θ and y would silently
    re-pair every weight with the wrong channel — invisible in every plot."""
    p = write_xy(tmp_path / "down.xye", [3.0, 2.0, 1.0], [30.0, 20.0, 10.0],
                 [3.3, 2.2, 1.1])
    data = pr.read_pattern(p)
    assert data.two_theta == [1.0, 2.0, 3.0]
    assert data.sigma == [1.1, 2.2, 3.3]


def test_a_repeated_point_with_the_same_intensity_is_dropped(tmp_path):
    """A format artefact: the repeat carries no measurement the first lacks."""
    p = write_xy(tmp_path / "dup.xy", [10.0, 20.0, 20.0, 30.0],
                 [1.0, 2.0, 2.0, 3.0])
    notes: list = []
    data = pr.read_pattern(p, diagnostics=notes)

    assert data.two_theta == [10.0, 20.0, 30.0]
    assert [d.code for d in notes] == ["PATTERN_DUPLICATE_POINTS"]


def test_a_repeated_point_with_a_different_intensity_is_refused(tmp_path):
    """A contradiction, not a report — and the difference is the whole rule.

    Averaging the two invents a datum that was never measured; dropping one
    picks a measurement arbitrarily.  Both are choices the caller has to make,
    so the reader names the 2θ and stops.
    """
    p = write_xy(tmp_path / "clash.xy", [10.0, 20.0, 20.0, 30.0],
                 [1.0, 2.0, 7.0, 3.0])
    with pytest.raises(ValueError, match=r"20.*appears twice"):
        pr.read_pattern(p)


def test_stitched_ranges_are_refused_rather_than_sorted_or_concatenated(tmp_path):
    """GSAS-II concatenates, which mixes two step sizes and two counting times
    into one weighting regime.  Here the three readings are three different
    measurements and choosing between them is the caller's."""
    p = write_xy(tmp_path / "stitch.xy", [10.0, 11.0, 12.0, 10.5, 11.5],
                 [1.0, 2.0, 3.0, 4.0, 5.0])
    with pytest.raises(ValueError, match="does not run in one direction"):
        pr.read_pattern(p)


def test_the_scan_option_is_named_only_by_a_format_that_has_one(tmp_path):
    """Telling someone to select a scan in a file that cannot hold several is a
    wrong instruction, not a vague one — so ``ascending`` takes the format."""
    tt, y = [10.0, 11.0, 10.5], [1.0, 2.0, 3.0]
    with pytest.raises(ValueError) as plain:
        ascending(tt, y, path=tmp_path / "a.xy", fmt=PATTERN_FORMATS[-1])
    assert "scan=" not in str(plain.value)

    multi = PatternFormat(
        name="multi", title="Multi", extensions=(), sniff="", sigma="",
        matches=lambda p: False, read=lambda p: None, options=("scan",))
    with pytest.raises(ValueError, match="name one with scan="):
        ascending(tt, y, path=tmp_path / "a.multi", fmt=multi)


def test_a_non_constant_step_is_neither_repaired_nor_refused(tmp_path):
    """SRM 660c is 24 stitched *regions* of differing step and is entirely
    legal; only the *direction* is a question the reader may ask."""
    p = write_xy(tmp_path / "vary.xy", [10.0, 10.1, 10.3, 10.6, 11.0],
                 [1.0, 2.0, 3.0, 4.0, 5.0])
    notes: list = []
    data = pr.read_pattern(p, diagnostics=notes)
    assert len(data.two_theta) == 5 and notes == []


def test_every_registered_reader_passes_through_the_same_policy():
    """One helper, not a rule restated per format — otherwise the fourth reader
    is the one that quietly sorts instead of refusing."""
    import inspect

    from pxrdref.io.formats import chi, gsas, pdcif, ras, xy

    for module in (chi, gsas, pdcif, ras, xy):
        body = inspect.getsource(module)
        assert "ascending(" in body, f"{module.__name__} does not use ascending()"
        assert "diagnostics" in body


def test_the_axis_policy_is_one_function_and_one_code():
    """The same rule for the *other* thing four readers now decide.

    Factored at the fourth consumer, which is where ``io/CLAUDE.md`` said the
    trigger was: the three-way verdict (read / refuse / assume-and-say-so) is
    ``base.check_axis`` and the code is ``PATTERN_X_AXIS_ASSUMED``.  What is
    deliberately *not* shared is the classifying — four formats state their axis
    in four shapes — so this asserts the policy, not the vocabularies.
    """
    import inspect
    import re

    from pxrdref.io.formats import base, chi, ras, uxd

    emits = re.compile(r'code\s*=\s*"[A-Z_]*X_AXIS_ASSUMED"')
    for module in (chi, ras, uxd):
        body = inspect.getsource(module)
        assert "check_axis(" in body, f"{module.__name__} decides an axis alone"
        assert not emits.search(body), (
            f"{module.__name__} spells its own axis code; there is one, and it "
            "lives in base.check_axis")
    assert inspect.getsource(base).count('code="PATTERN_X_AXIS_ASSUMED"') == 1


# ------------------------------------------------------------- reader options
def test_an_option_this_format_does_not_take_is_dropped_but_reported(tmp_path):
    """A UI carries a value across a change of file and that is normal; an API
    caller who passed it believed they had selected something."""
    p = write_xy(tmp_path / "plain.xy", [10.0, 20.0], [1.0, 2.0])
    notes: list = []
    pr.read_pattern(p, block="_meas", diagnostics=notes)

    assert [d.code for d in notes] == ["READER_OPTION_IGNORED"]
    assert notes[0].where == ["block"] and notes[0].level == "info"


def test_an_option_no_format_takes_is_a_typo_and_raises(tmp_path):
    p = write_xy(tmp_path / "plain.xy", [10.0, 20.0], [1.0, 2.0])
    with pytest.raises(ValueError, match="unknown reader option 'blcok'"):
        pr.read_pattern(p, blcok="_meas")


def test_none_means_unspecified_rather_than_a_value():
    """``read_pattern(p, block=None)`` still reads the first block that parses,
    which is what every caller threading an absent setting through relies on."""
    pdcif = next(f for f in PATTERN_FORMATS if f.name == "pdcif")
    assert reader_options_for(pdcif, {"block": None}) == {}
    assert reader_options_for(pdcif, {"block": "_meas"}) == {"block": "_meas"}


def test_an_int_option_arrives_as_an_int_however_it_was_stored():
    """``DataRef.options`` is dict[str, str], so a scan round-trips through a
    project as "2" and has to reach the reader as the integer 2."""
    from pxrdref.io.formats.base import ReaderOption

    assert ReaderOption(name="scan", kind="int", help="").coerce("2") == 2
    with pytest.raises(ValueError, match="scan= takes an integer"):
        ReaderOption(name="scan", kind="int", help="").coerce("first")


def test_the_default_scan_is_never_a_silent_one(tmp_path):
    """Reading one of a file's scans is a choice, and a default only the GUI
    preview reveals leaves the API and the CLI blind — ``INDEX_SHIFT_ALLOWANCE``
    one seam over: an assumed selection must not look like a deliberate one."""
    notes: list = []
    multiscan_default(3, None, path=tmp_path / "m.ras", diagnostics=notes)
    assert [d.code for d in notes] == ["PATTERN_MULTISCAN_DEFAULTED"]
    assert "scan 0 of 3" in notes[0].message

    quiet: list = []
    multiscan_default(3, 1, path=tmp_path / "m.ras", diagnostics=quiet)   # chosen
    multiscan_default(1, None, path=tmp_path / "m.ras", diagnostics=quiet)  # only one
    assert quiet == []


# ---------------------------------------------------------------------- chi
def write_chi(path, x_label, tt, y, *, declared=None, n_datasets=1):
    count = len(tt) if declared is None else declared
    head_lines = [path.stem + ".tif", x_label, "Intensity",
                  f"       {count}" + (f"  {n_datasets}" if n_datasets else "")]
    rows = [f"  {a:.6f}  {b:.6f}" for a, b in zip(tt, y)]
    path.write_text("\n".join(head_lines + rows) + "\n", encoding="utf-8")
    return path


def test_the_chi_point_count_line_is_no_longer_read_as_a_data_point(tmp_path):
    """The regression this reader exists for.

    ``.chi`` line 4 is ``<npoints> [<ndatasets>]``, and ``2000 1`` is a
    perfectly good pair of floats — so the ASCII-column fallback appended it as
    a point at x = 2000, y = 1.  A phantom datum thousands of degrees outside
    the pattern, which survives every plot and quietly widens the fitted range.
    """
    tt = [10.0, 10.01, 10.02]
    p = write_chi(tmp_path / "ceo2.chi", "2-Theta Angle (Degrees)", tt,
                  [1.0, 2.0, 3.0], n_datasets=1)

    assert identify_format(p).name == "chi"
    data = pr.read_pattern(p)
    assert data.two_theta == tt              # three points, not four
    assert 3.0 not in data.two_theta         # the count line is not a datum

    # and the fallback really would have taken it: the same bytes, read as xy
    from pxrdref.io.formats.xy import read_xy
    assert len(read_xy(p).two_theta) == len(tt) + 1


@pytest.mark.parametrize("label,what", [
    ("q (nm^-1)", "scattering vector"),
    ("Q_A^-1", "scattering vector"),
    ("d (Angstrom)", "d-spacing"),
    ("d-spacing", "d-spacing"),
])
def test_an_axis_that_is_recognisably_not_two_theta_is_refused(tmp_path, label, what):
    """Reading a q axis as 2θ gives a confident wrong cell from values that
    parse perfectly — the exact failure class this package refuses.  The
    conversion needs a wavelength the file does not carry, so inventing one
    would be worse than declining."""
    p = write_chi(tmp_path / "int.chi", label, [1.0, 2.0], [1.0, 2.0])
    with pytest.raises(ValueError) as exc:
        pr.read_pattern(p)
    assert repr(label) in str(exc.value) and what in str(exc.value)


def test_a_two_theta_label_wins_over_the_d_in_degrees(tmp_path):
    """"2-Theta Angle (Degrees)" must not be read as a d axis by its own
    spelling — which is why the 2θ recogniser is consulted first."""
    p = write_chi(tmp_path / "ok.chi", "2-Theta Angle (Degrees)", [1.0, 2.0],
                  [1.0, 2.0])
    notes: list = []
    pr.read_pattern(p, diagnostics=notes)
    assert notes == []


def test_an_unrecognisable_axis_is_read_as_two_theta_and_says_so(tmp_path):
    """Unrecognisable is not the same as recognisably wrong: most files really
    are 2θ, so this reads — but the assumption is stated, with the label."""
    p = write_chi(tmp_path / "odd.chi", "Angle", [1.0, 2.0], [1.0, 2.0])
    notes: list = []
    data = pr.read_pattern(p, diagnostics=notes)

    assert [d.code for d in notes] == ["PATTERN_X_AXIS_ASSUMED"]
    assert "'Angle'" in notes[0].message
    assert data.metadata["x_label"] == "Angle"   # verbatim, never normalised


def test_the_count_gate_is_what_keeps_an_xy_with_a_prose_header_out(tmp_path):
    """The shape gate alone is not decisive — a three-line prose header over a
    lone integer passes it — so line 4's own claim is checked against the rows
    that follow.  That read is O(N) and is the one stated exemption to the
    bounded-head rule; it runs only behind the shape gate."""
    tt, y = [10.0, 10.01, 10.02], [1.0, 2.0, 3.0]
    honest = write_chi(tmp_path / "real.chi", "2-Theta", tt, y)
    lying = write_chi(tmp_path / "prose.xy", "2-Theta", tt, y, declared=999)

    assert identify_format(honest).name == "chi"
    assert identify_format(lying).name == "xy"   # falls through, as it should


# ---------------------------------------------------------------------- dif
PEAK_LIST = """\
Quartz, SiO2
  D-SPACING   INTENSITY   H  K  L
     4.25510      16.29    1  0  0
     3.34350     100.00    1  0  1
     2.45680       9.15    1  1  0
     2.28150       8.09    1  0  2
     2.23670       4.29    1  1  1
"""


def test_a_peak_list_is_refused_by_name_rather_than_refined_against(tmp_path):
    """~30 delta functions are not a profile, and Rwp will not say so.

    The ASCII fallback reads a ``.dif`` perfectly happily; the refinement that
    follows fits every background coefficient, every width and every scale to a
    picture of a diffractogram.  So the file is claimed *in order to be
    declined*, and the refusal names what to do instead.
    """
    p = tmp_path / "quartz.dif"
    p.write_text(PEAK_LIST, encoding="utf-8")

    fmt = identify_format(p)
    assert fmt.name == "dif_peaklist" and fmt.refuses
    with pytest.raises(ValueError) as exc:
        pr.read_pattern(p)
    assert "quartz.dif" in str(exc.value) and "peak list" in str(exc.value)
    assert "index_pattern" in str(exc.value)   # the tool that does take positions


def test_the_evidence_is_the_hkl_columns_not_the_suffix(tmp_path):
    """A real profile someone named ``.dif`` still opens: the suffix is a
    filename and the Miller indices are the format."""
    p = tmp_path / "actually_a_scan.dif"
    p.write_text("\n".join(f"{10 + i * 0.02:.4f} {i}" for i in range(60)),
                 encoding="utf-8")

    assert identify_format(p).name == "xy"
    assert len(pr.read_pattern(p).two_theta) == 60


def test_a_peak_list_under_another_suffix_is_not_claimed(tmp_path):
    """The converse, stated so the pair is symmetric: matching needs *both*, so
    this reader cannot start claiming ASCII files with integer columns."""
    p = tmp_path / "quartz.txt"
    p.write_text(PEAK_LIST, encoding="utf-8")
    assert identify_format(p).name != "dif_peaklist"


def test_a_refusal_is_an_entry_in_capabilities_not_a_side_table():
    """``reader_formats`` would mean two things if refusals lived elsewhere; the
    field says which an entry is, so a client can tell "we can open this" from
    "we know what this is and it is the wrong kind of file"."""
    caps = pr.capabilities()
    by_name = {r.name: r for r in caps.reader_formats}
    assert by_name["dif_peaklist"].refuses
    assert all(by_name[f.name].refuses is None
               for f in PATTERN_FORMATS if f.refuses is None)


# --------------------------------------------------------------------- head
def test_the_head_read_is_bounded_and_reports_the_mark(tmp_path):
    """A sniff may not cost O(file): the predecessor decoded a whole file and
    then sliced 4 kB off it, once per registered format."""
    p = tmp_path / "big.xy"
    p.write_text("BANK 1\n" + "0.0 1.0\n" * 40_000, encoding="utf-8")
    h = head(p)
    assert len(h.raw) == 4096 and h.encoding == "utf-8" and h.bom is False
    assert h.text.startswith("BANK 1")


@pytest.mark.parametrize("mark,codec", [
    (b"\xef\xbb\xbf", "utf-8-sig"),
    (b"\xff\xfe", "utf-16"),
    (b"\xfe\xff", "utf-16"),
])
def test_a_byte_order_mark_names_the_codec_and_strips_itself(tmp_path, mark, codec):
    """Load-bearing beyond the encoding: ASCII-range UTF-16LE is *valid* UTF-8
    with interleaved NULs, so the mark is what will separate a Windows vendor
    export from a binary file when ``xy`` stops being total."""
    body = "BANK 1"
    raw = mark + (body.encode("utf-16-le") if mark == b"\xff\xfe"
                  else body.encode("utf-16-be") if mark == b"\xfe\xff"
                  else body.encode("utf-8"))
    p = tmp_path / "marked.txt"
    p.write_bytes(raw)
    h = head(p)
    assert h.encoding == codec and h.bom is True
    assert h.text == body          # the mark itself is not part of the text


def test_head_is_not_cached_because_restage_re_reads_the_same_path(tmp_path):
    """A path-keyed cache would be a correctness hazard for exactly the file a
    user just replaced — which is what the GUI's restage does."""
    p = tmp_path / "same.xy"
    p.write_text("first\n", encoding="utf-8")
    assert head(p).text.startswith("first")
    p.write_text("second\n", encoding="utf-8")
    assert head(p).text.startswith("second")


# ----------------------------------------------------------------- dispatch
def test_a_gsas_file_is_claimed_by_content_not_by_suffix(tmp_path):
    """``.raw`` is a GSAS extension *and* Bruker's binary one; the two are held
    disjoint by construction (a BANK record against magic bytes), so the name
    on the file never decides."""
    p = tmp_path / "misnamed.dat"
    p.write_text("BANK 1 3 3 CONS 1000.0 100.0 0 0 STD\n  1  2  3\n",
                 encoding="utf-8")
    assert identify_format(p).name == "gsas"


def test_a_project_keeps_the_repairs_in_memory_and_out_of_project_json(tmp_path):
    """They are a deterministic function of bytes + reader + options, and
    ``DataRef`` records all three — so a ``project.json`` field would be a
    second authority.  Putting the repairs in the reader also puts them under
    the fingerprint check, which is what says "a reader change, not a corrupt
    project" if one ever changes."""
    from tests.test_refine_synthetic import perturbed_models

    p = write_xy(tmp_path / "down.xy", [30.0, 20.0, 10.0], [3.0, 2.0, 1.0])
    structure, ins = perturbed_models()
    project = pr.Project.create(tmp_path / "rev.pxrd", pattern=p,
                                structure=structure, instrument=ins)

    assert [d.code for d in project.data_diagnostics] == ["PATTERN_SCAN_REVERSED"]
    stored = (tmp_path / "rev.pxrd" / "project.json").read_text(encoding="utf-8")
    assert "PATTERN_SCAN_REVERSED" not in stored
    # …and re-reading reproduces them, because the bytes and the reader did
    assert [d.code for d in pr.Project.open(project.path).data_diagnostics] == [
        "PATTERN_SCAN_REVERSED"]


def test_a_binary_file_is_refused_by_name_rather_than_by_traceback(tmp_path):
    """The failure this seam exists to remove.

    ``xy`` used to be the *total* fallback, so opening a Bruker binary reached
    ``read_text`` and raised a bare ``UnicodeDecodeError`` — a message about
    codecs, from a user who asked to open a diffraction pattern.  Now nothing
    claims it and the refusal names the formats this build does read, built
    from the registry so a format added tomorrow appears in it.
    """
    p = tmp_path / "d8.raw"
    p.write_bytes(b"RAW4.00\x00" + bytes(range(256)) * 8)

    with pytest.raises(ValueError) as refusal:
        pr.read_pattern(p)
    message = str(refusal.value)
    assert "d8.raw" in message and "looks binary" in message
    for fmt in PATTERN_FORMATS:
        assert fmt.title in message


def test_a_byte_order_mark_means_text_even_though_utf16_is_full_of_nuls(tmp_path):
    """The one carve-out, and it is not hypothetical: ASCII-range UTF-16LE is
    *valid* UTF-8 with interleaved NULs, and Windows vendor software exports it.
    Before this such a file died with "no numeric data found", so the reach is
    strictly new."""
    p = tmp_path / "windows.xy"
    p.write_bytes("﻿10 1\n20 2\n30 3\n".encode("utf-16-le"))

    assert identify_format(p).name == "xy"
    assert pr.read_pattern(p).two_theta == [10.0, 20.0, 30.0]


def test_the_registry_order_is_the_dispatch_order():
    """The first format whose ``matches`` returns True reads the file, so the
    tuple's order is behaviour and ``xy`` being last is the whole of why
    anything else is ever reached."""
    names = [f.name for f in PATTERN_FORMATS]
    assert names[-1] == "xy"
    assert len(set(names)) == len(names)


# ---------------------------------------------------------------------- ras
DATA = Path(__file__).parent / "data"


def write_ras(path, rows, *, axis="TwoThetaTheta", unit_y="counts",
              step=None, speed=None, speed_unit=None, comment=None, extra=()):
    """One-scan ``.ras`` bytes.  Text format, so a writer module would buy the
    round-trip nothing — the circularity the binary formats need it for is in
    packing *offsets*, and there are none here."""
    header = [f'*MEAS_SCAN_AXIS_X "{axis}"', f'*MEAS_SCAN_UNIT_Y "{unit_y}"']
    for key, value in (("MEAS_SCAN_STEP", step), ("MEAS_SCAN_SPEED", speed),
                       ("MEAS_SCAN_SPEED_UNIT", speed_unit),
                       ("FILE_COMMENT", comment)):
        if value is not None:
            header.append(f'*{key} "{value}"')
    header.extend(extra)
    body = ["*RAS_INT_START"]
    body += [" ".join(f"{v}" for v in row) for row in rows]
    body.append("*RAS_INT_END")
    lines = (["*RAS_DATA_START", "*RAS_HEADER_START", *header, "*RAS_HEADER_END"]
             + body + ["*RAS_DATA_END"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def test_the_real_scan_reads_and_carries_the_anode_its_header_names(tmp_path):
    """The fixture is a real SmartLab export (NIMS M-DaC_XRD, MIT), and what it
    proves that a synthetic file cannot is that these header keys are spelled
    the way an instrument actually spells them."""
    data = pr.read_pattern(DATA / "rigaku_nims.ras")

    assert identify_format(DATA / "rigaku_nims.ras").name == "ras"
    assert len(data.two_theta) == 3501
    assert (data.two_theta[0], data.two_theta[-1]) == (25.0, 60.0)
    assert data.metadata["anode"] == "Cu"
    assert data.metadata["wavelength"] == "1.540593"
    assert data.metadata["scan_count"] == "1"


def test_whole_counts_get_the_poisson_fallback_rather_than_an_invented_sigma():
    """``sigma is None`` is the *correct* answer here, not a missing one: the
    fallback √max(y,1) is exactly right for a raw count, and the file's
    intensities are integers to the last of 3501 points."""
    data = pr.read_pattern(DATA / "rigaku_nims.ras")

    assert data.sigma is None
    assert all(float(v).is_integer() for v in data.intensity)
    assert data.metadata["intensity_unit"] == "counts"      # and it agrees


def test_a_rate_gets_a_sigma_derived_from_the_counts_it_was_a_rate_of(tmp_path):
    """20 counts in 0.3 s is 66.6667 cps, and its σ is √20/0.3 — not √66.6667.
    The counting time comes from the header's own step and speed."""
    counts = [20, 31, 47, 53]
    t = 0.3
    p = write_ras(tmp_path / "rate.ras",
                  [(10.0 + 0.03 * i, round(c / t, 4)) for i, c in enumerate(counts)],
                  unit_y="cps", step=0.03, speed=6.0, speed_unit="deg/min")

    notes: list = []
    data = pr.read_pattern(p, diagnostics=notes)

    assert data.metadata["count_time_s"] == "0.3"
    assert data.sigma is not None
    for got, n in zip(data.sigma, counts):
        assert got == pytest.approx(n ** 0.5 / t, rel=1e-4)
    assert "PATTERN_INTENSITY_SCALED" not in [d.code for d in notes]


def test_the_speed_unit_is_read_because_deg_per_minute_is_not_deg_per_second(tmp_path):
    """The same numbers with the unit changed are a different counting time by a
    factor of 60, hence a σ wrong by √60. So the unit is read, and a header that
    does not state one leaves the time *unknown* rather than assumed."""
    rows = [(10.0 + 0.03 * i, round(c / 0.3, 4)) for i, c in enumerate([20, 31, 47, 53])]

    per_second = pr.read_pattern(write_ras(tmp_path / "s.ras", rows, unit_y="cps",
                                           step=0.03, speed=6.0, speed_unit="deg/sec"))
    unstated = pr.read_pattern(write_ras(tmp_path / "u.ras", rows, unit_y="cps",
                                         step=0.03, speed=6.0))

    # 0.005 s per step makes y·t nowhere near whole, so nothing is established
    assert per_second.sigma is None and unstated.sigma is None
    assert "count_time_s" not in unstated.metadata


def test_the_declared_intensity_unit_is_a_claim_and_does_not_decide_sigma(tmp_path):
    """Measured on real files: ``rigaku-xrd-analysis``'s ``example.ras`` declares
    counts and stores 84.3047, which no scale makes integral. Trusting the label
    there would apply √y to a quantity that is not a count, so the label is
    recorded and the arithmetic decides."""
    p = write_ras(tmp_path / "lying.ras",
                  [(10.0 + 0.004 * i, v) for i, v in
                   enumerate([84.3047, 84.1685, 73.4107, 75.6654])],
                  unit_y="counts", step=0.004, speed=2.0, speed_unit="deg/min")

    notes: list = []
    data = pr.read_pattern(p, diagnostics=notes)

    assert data.sigma is None
    assert data.metadata["intensity_unit"] == "counts"          # recorded verbatim
    scaled = [d for d in notes if d.code == "PATTERN_INTENSITY_SCALED"]
    assert len(scaled) == 1 and "wrong by √t" in scaled[0].message


def test_a_rocking_curve_is_refused_rather_than_refined_as_a_pattern(tmp_path):
    """An ω scan is a real, common export whose points parse perfectly. Reading
    one as 2θ is the confident-wrong-cell class, so it is refused by name — the
    ``.chi`` axis policy one module over, applied to a header key."""
    p = write_ras(tmp_path / "rock.ras", [(15.55 + 0.004 * i, 84.0) for i in range(4)],
                  axis="Omega")

    with pytest.raises(ValueError) as refusal:
        pr.read_pattern(p)
    assert "rock.ras" in str(refusal.value) and "rocking curve" in str(refusal.value)


def test_an_unrecognised_axis_is_read_as_two_theta_and_says_so(tmp_path):
    p = write_ras(tmp_path / "odd.ras", [(10.0 + i, 5.0) for i in range(4)],
                  axis="TwoThetaChi")

    notes: list = []
    data = pr.read_pattern(p, diagnostics=notes)

    assert len(data.two_theta) == 4
    assert [d.code for d in notes if d.code == "PATTERN_X_AXIS_ASSUMED"]
    assert "*MEAS_SCAN_AXIS_X" in notes[0].message


def test_a_scan_is_selected_never_concatenated(tmp_path):
    """Two passes generally differ in step and counting time, so merging them
    puts two weighting regimes in one residual. ``scan=`` picks; nothing joins."""
    path = DATA / "rigaku_multiscan.ras"

    first = pr.read_pattern(path, scan=0)
    second = pr.read_pattern(path, scan=1)

    assert first.two_theta == [10.0, 10.5, 11.0]
    assert second.two_theta == [20.0, 20.5, 21.0]
    assert second.metadata["scan"] == "1"
    assert second.metadata["scan_count"] == "2"


def test_the_defaulted_scan_says_so_on_a_real_multi_scan_file():
    notes: list = []
    pr.read_pattern(DATA / "rigaku_multiscan.ras", diagnostics=notes)
    chosen: list = []
    pr.read_pattern(DATA / "rigaku_multiscan.ras", scan=1, diagnostics=chosen)

    assert "PATTERN_MULTISCAN_DEFAULTED" in [d.code for d in notes]
    assert "PATTERN_MULTISCAN_DEFAULTED" not in [d.code for d in chosen]


def test_a_scan_the_file_does_not_have_is_refused_by_number():
    with pytest.raises(ValueError, match="holds 2 scan"):
        pr.read_pattern(DATA / "rigaku_multiscan.ras", scan=7)


def test_listing_scans_labels_them_with_what_the_file_calls_them():
    """A picker showing "Scan 0" and "Scan 1" has told the user nothing they did
    not already know."""
    scans = list_scans(DATA / "rigaku_multiscan.ras")

    assert [s.label for s in scans] == ["Low angle scan", "High angle scan"]
    assert [s.two_theta_range for s in scans] == [(10.0, 11.0), (20.0, 21.0)]
    assert [s.n_points for s in scans] == [3, 3]


def test_listing_scans_of_a_format_that_has_none_is_a_refusal_not_an_empty_list():
    """"This file has one scan" and "this format has no scan structure" are
    different answers, and only the second is true of a pdCIF."""
    with pytest.raises(ValueError, match="one measurement per file"):
        list_scans(DATA / "nist_srm660c_100a.cif")


def test_an_attenuator_column_is_reported_and_never_applied():
    """No specification states whether column 2 is already corrected for it, and
    applying it twice or not at all are both wrong — so the reader matches the
    convention the other codes use and says which points it affects."""
    notes: list = []
    data = pr.read_pattern(DATA / "rigaku_three_column.ras", diagnostics=notes)

    assert data.intensity == [250.0, 310.5, 480.2, 390.7]     # column 2, untouched
    found = [d for d in notes if d.code == "RAS_ATTENUATOR_PRESENT"]
    assert len(found) == 1
    assert "10–11.5" in found[0].message and "σ is affected" in found[0].message


def test_choosing_a_scan_and_enumerating_them_are_two_halves_of_one_fact():
    """The biconditional: a format that lets a caller choose a scan must be able
    to say what there is to choose between, and one that cannot hold several has
    nothing to enumerate."""
    for fmt in PATTERN_FORMATS:
        assert ("scan" in fmt.options) == (fmt.scans is not None), fmt.name


def test_every_key_a_reader_writes_is_one_the_vocabulary_declares():
    """Two consumers *match* on these keys — the wizard's anode pre-selection and
    the scan count in a preview — and neither can match on a name each reader
    spells for itself."""
    for fixture in ("rigaku_nims.ras", "11BM_NAC.fxye", "qarr/corundum.prn",
                    "nist_srm660c_100a.cif"):
        keys = set(pr.read_pattern(DATA / fixture).metadata)
        assert keys <= set(METADATA_KEYS), (fixture, keys - set(METADATA_KEYS))
    assert all(prose for prose in METADATA_KEYS.values())

    with pytest.raises(ValueError, match="undeclared pattern metadata key"):
        metadata(source_file="a.ras", detector_serial="XYZ")


def test_the_schema_is_a_parser_boundary_like_any_other(tmp_path):
    """A ``PatternData`` validator is the last boundary a reader crosses, and its
    refusal must name the file like every other one.

    Found by the truncation harness rather than by reading: a ``.XRA`` cut short
    enough to lose its ``BANK`` record fell through to ``xy``, parsed one point,
    and raised pydantic's report — which passed "the refusal names the file"
    only because pydantic *echoed* the metadata dict, filename included. One
    more metadata key pushed the name past that echo's truncation and the
    invariant failed, having never held.
    """
    p = write_xy(tmp_path / "onepoint.xy", [15.0], [3.0])

    with pytest.raises(ValueError) as refusal:
        pr.read_pattern(p)
    message = str(refusal.value)
    assert "onepoint.xy" in message and "at least 2 points" in message
    assert "pydantic" not in message and "validation error" not in message


# ---------------------------------------------------------------------- uxd
def write_uxd(path, ranges, *, anode="Cu", wl1=1.540600, radius=250.0):
    """A ``.uxd`` of one or more ranges.  No real ``.uxd`` could be vendored —
    the only obtainable ones are GPL or carry no licence at all — so these are
    synthesized, and every structural claim they make was verified against a
    real file first (`tests/data/README.md` names which)."""
    lines = ["; written by tests", "_FILEVERSION=2", f"_ANODE='{anode}'",
             f"_WL1={wl1:.6f}", f"_GONIOMETER_RADIUS={radius:.6f}"]
    for n, r in enumerate(ranges, start=1):
        lines.append(f"; (Data for Range number {n})")
        lines.append(f"_DRIVE='{r['drive']}'")
        for key in ("STEPTIME", "STEPSIZE", "START", "2THETA"):
            if key.lower() in r:
                lines.append(f"_{key}={r[key.lower()]:.6f}")
        lines.append(r["marker"])
        for row in r["rows"]:
            lines.append("   " + "      ".join(f"{v}" for v in row))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def test_the_block_marker_is_read_as_two_facts_not_looked_up_as_a_name(tmp_path):
    """``_2THETA`` means "there is a position column"; ``COUNTS``/``CPS`` is the
    unit.  Independent, so the four spellings are two bits rather than a table."""
    counts = [3, 5, 8, 6]
    paired = write_uxd(tmp_path / "paired.uxd", [dict(
        drive="COUPLED", marker="_2THETACOUNTS", steptime=1.0,
        rows=[(10.0 + 0.02 * i, c) for i, c in enumerate(counts)])])
    implied = write_uxd(tmp_path / "implied.uxd", [dict(
        drive="COUPLED", marker="_COUNTS", steptime=1.0, stepsize=0.02,
        start=10.0, rows=[(c,) for c in counts])])

    a, b = pr.read_pattern(paired), pr.read_pattern(implied)
    assert a.two_theta == pytest.approx(b.two_theta)     # start + i·step
    assert a.intensity == b.intensity == [3.0, 5.0, 8.0, 6.0]
    assert a.metadata["intensity_unit"] == "counts" and a.sigma is None


def test_a_cps_block_gets_its_sigma_from_steptime(tmp_path):
    """Structural, so it is trusted: unlike ``.ras``'s free-text unit field, the
    unit here is the token that opens the block and cannot disagree with it."""
    p = write_uxd(tmp_path / "rate.uxd", [dict(
        drive="COUPLED", marker="_2THETACPS", steptime=4.0,
        rows=[(10.0 + 0.02 * i, c / 4.0) for i, c in enumerate([12, 20, 33, 41])])])

    data = pr.read_pattern(p)

    assert data.metadata["intensity_unit"] == "cps"
    assert data.metadata["count_time_s"] == "4.0"
    for got, n in zip(data.sigma, [12, 20, 33, 41]):
        assert got == pytest.approx(n ** 0.5 / 4.0, rel=1e-9)


def test_a_cps_block_without_a_steptime_withholds_sigma_and_says_so(tmp_path):
    p = write_uxd(tmp_path / "nortime.uxd", [dict(
        drive="COUPLED", marker="_2THETACPS",
        rows=[(10.0 + 0.02 * i, 3.5 * i + 1) for i in range(4)])])

    notes: list = []
    data = pr.read_pattern(p, diagnostics=notes)

    assert data.sigma is None
    assert [d.code for d in notes] == ["PATTERN_INTENSITY_SCALED"]


def test_the_drive_decides_the_axis_because_the_marker_name_lies(tmp_path):
    """The finding this reader is built around: a rocking curve and a pole figure
    are both stored under a marker called ``_2THETACOUNTS``. Four of the five
    real ``.uxd`` files read while writing this are not 2θ scans at all."""
    rocking = write_uxd(tmp_path / "rock.uxd", [dict(
        drive="THETA", marker="_2THETACOUNTS", steptime=1.0,
        rows=[(-1.0 + 0.04 * i, 100) for i in range(4)])])

    with pytest.raises(ValueError) as refusal:
        pr.read_pattern(rocking)
    assert "rock.uxd" in str(refusal.value) and "rocking curve" in str(refusal.value)
    assert "_2THETACOUNTS" in str(refusal.value)     # the trap, named in the refusal


def test_a_detector_scan_reads_because_two_theta_is_what_it_steps(tmp_path):
    p = write_uxd(tmp_path / "det.uxd", [dict(
        drive="2THETA", marker="_2THETACOUNTS", steptime=1.0,
        rows=[(10.0 + 0.02 * i, 100 + i) for i in range(4)])], radius=350.0)

    data = pr.read_pattern(p)

    assert data.metadata["scan_axis"] == "2THETA"
    assert data.metadata["goniometer_radius_mm"] == "350.0"


def test_ranges_of_different_counting_time_are_selected_never_joined(tmp_path):
    """Not academic: one real 153-range file carries ``_STEPTIME`` of both 2 s
    and 20 s. Concatenating those puts measurements a factor of ten apart in
    counting statistics under one Poisson assumption."""
    p = write_uxd(tmp_path / "two.uxd", [
        dict(drive="COUPLED", marker="_2THETACOUNTS", steptime=2.0,
             rows=[(10.0 + 0.1 * i, 40 + i) for i in range(4)]),
        dict(drive="COUPLED", marker="_2THETACOUNTS", steptime=20.0,
             rows=[(20.0 + 0.1 * i, 400 + i) for i in range(4)]),
    ])

    notes: list = []
    first = pr.read_pattern(p, diagnostics=notes)
    second = pr.read_pattern(p, scan=1)

    assert first.two_theta[0] == 10.0 and second.two_theta[0] == 20.0
    assert first.metadata["count_time_s"] == "2.0"
    assert second.metadata["count_time_s"] == "20.0"
    assert "PATTERN_MULTISCAN_DEFAULTED" in [d.code for d in notes]
    assert [s.label for s in list_scans(p)] == ["COUPLED 10–10.3°", "COUPLED 20–20.3°"]


def test_counts_with_no_position_column_and_no_step_is_refused(tmp_path):
    """``_COUNTS`` puts the whole x axis in ``_START`` and ``_STEPSIZE``. Without
    them there is no axis — and a default step of 1 would be an invented one."""
    p = write_uxd(tmp_path / "bare.uxd", [dict(
        drive="COUPLED", marker="_COUNTS", steptime=1.0,
        rows=[(c,) for c in (3, 5, 8, 6)])])

    with pytest.raises(ValueError, match="no 2θ axis to read"):
        pr.read_pattern(p)


def test_an_unknown_block_marker_is_named_rather_than_skipped(tmp_path):
    p = tmp_path / "odd.uxd"
    p.write_text("_FILEVERSION=2\n_DRIVE='COUPLED'\n_INTENSITIES\n10.0 5\n11.0 6\n",
                 encoding="utf-8")

    with pytest.raises(ValueError, match="_INTENSITIES"):
        pr.read_pattern(p)


# -------------------------------------------------------------------- xrdml
#: FAIRmat's own reader output for the same file, vendored beside it — an
#: independent implementation's answer, which is what makes it an oracle rather
#: than a transcription of ours.  It records array *shapes* and the header
#: metadata; the intensities themselves it does not carry.
def _oracle(stem: str) -> dict:
    import json

    return json.loads((DATA / f"{stem}.json").read_text(encoding="utf-8"))


def test_the_real_powder_scan_matches_its_independent_oracle():
    """Every field the oracle carries, against the reader — not a sample of them.

    The oracle is FAIRmat's ``readers-xrd`` output for this exact file
    (Apache-2.0, vendored with it), so agreement is a cross-implementation
    check on the element paths, not a round-trip through our own understanding.
    """
    oracle = _oracle("panalytical_powder.xrdml")
    data = pr.read_pattern(DATA / "panalytical_powder.xrdml")

    assert len(data.two_theta) == int(oracle["2Theta"].strip("(),"))
    assert len(data.intensity) == int(oracle["intensity"].strip("(),"))
    assert data.metadata["scan_axis"] == oracle["metadata"]["scan_axis"]
    assert data.metadata["anode"] == oracle["metadata"]["source"]["anode_material"]
    assert float(data.metadata["wavelength"]) == float(
        oracle["metadata"]["source"]["kAlpha1"])
    assert float(data.metadata["wavelength_alpha2"]) == float(
        oracle["metadata"]["source"]["kAlpha2"])
    assert data.metadata["scan_count"] == "1"
    # not in the oracle, and the reason the reader bothers: two of the four
    # bragg_brentano numbers need not be typed when the file already knows them
    assert data.metadata["goniometer_radius_mm"] == "240.0"


def test_raw_counts_get_no_sigma_because_the_poisson_fallback_is_right():
    """``sigma=None`` here is the *correct* answer, not a missing one — the
    stored values are the detector's own integers."""
    data = pr.read_pattern(DATA / "panalytical_powder.xrdml")

    assert data.sigma is None
    assert data.metadata["intensity_unit"] == "counts"
    assert all(float(v).is_integer() for v in data.intensity)


def test_the_beam_attenuator_is_applied_and_sigma_goes_through_it():
    """The finding this reader is built around, on the file that established it.

    A single point of the GaAs 004 substrate reflection was measured behind a
    188× foil, and the raw series *dips* there — 1341, 14602, **1877**, 13749 —
    which is the attenuation and not a profile.  So the stored counts are the
    attenuated ones, the reported intensity is their product, and σ is
    √counts·a rather than √y: the case GSAS-II gets wrong by weighting 1/y.
    """
    notes: list = []
    data = pr.read_pattern(DATA / "panalytical_attenuator.xrdml", diagnostics=notes)

    apex = max(range(len(data.intensity)), key=lambda i: data.intensity[i])
    assert data.intensity[apex] == 1877.0 * 188.0
    assert data.intensity[apex - 1] == 14602.0 and data.intensity[apex + 1] == 13749.0
    assert data.sigma is not None
    assert data.sigma[apex] == pytest.approx(1877.0 ** 0.5 * 188.0)
    # and nowhere else: an unattenuated point's σ is what the fallback would be
    assert data.sigma[apex - 1] == pytest.approx(14602.0 ** 0.5)
    assert [d.code for d in notes] == ["XRDML_ATTENUATOR_APPLIED"]
    assert "66.1" in notes[0].message and "188" in notes[0].message


def test_a_reciprocal_space_map_is_scans_and_says_which_one_it_read():
    """101 scans in one file, so the default is a choice and is never silent."""
    notes: list = []
    data = pr.read_pattern(DATA / "panalytical_mesh.xrdml", diagnostics=notes)

    assert data.metadata["scan_count"] == "101"
    assert data.metadata["scan"] == "0"
    assert [d.code for d in notes] == ["PATTERN_MULTISCAN_DEFAULTED"]
    assert pr.read_pattern(DATA / "panalytical_mesh.xrdml",
                           scan=100).metadata["scan"] == "100"


def test_a_stack_of_identical_ranges_is_labelled_by_what_differs():
    """``ScanInfo.label`` may not be invented, and "2Theta 67.45–69.95°" a
    hundred and one times tells a picker nothing.  What separates the scans is
    the axis each was fixed at, which is knowable only across the whole list."""
    scans = list_scans(DATA / "panalytical_mesh.xrdml")

    assert len(scans) == 101
    assert len({s.label for s in scans}) == 101
    assert all("Omega" in s.label for s in scans)
    assert all(s.n_points == 255 for s in scans)


def test_the_position_list_form_is_read_as_written():
    """Three forms exist and the mesh uses the third: 2θ written out per point
    rather than as a start and an end."""
    data = pr.read_pattern(DATA / "panalytical_mesh.xrdml", scan=0)

    assert len(data.two_theta) == 255
    assert data.two_theta[0] == pytest.approx(67.45053915)
    assert data.two_theta[-1] == pytest.approx(69.95146085)


def test_both_schema_versions_are_claimed_because_nothing_matches_the_namespace():
    """1.6 and 2.1 are both current in the wild; keying on either would refuse
    half the files a lab owns."""
    versions = set()
    for stem in ("panalytical_powder", "panalytical_attenuator", "panalytical_mesh"):
        path = DATA / f"{stem}.xrdml"
        assert identify_format(path).name == "xrdml"
        versions.add(path.read_text(encoding="utf-8")
                     .split('xmlns="', 1)[1].split('"', 1)[0])
    assert len(versions) == 2


def write_xrdml(path: Path, *, scan_axis="Gonio", start=10.0, end=13.0,
                counts=(10, 20, 30, 40), element="counts", unit="counts",
                attenuation=None, count_time="1.0", root="xrdMeasurements",
                namespace="http://www.xrdml.com/XRDMeasurement/2.1") -> Path:
    """A minimal but schema-shaped ``.xrdml`` — for the cases no fixture holds."""
    attn = ("" if attenuation is None else
            f"<beamAttenuationFactors>{' '.join(map(str, attenuation))}"
            "</beamAttenuationFactors>")
    time = "" if count_time is None else (
        f'<commonCountingTime unit="seconds">{count_time}</commonCountingTime>')
    path.write_text(
        f'<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<{root} xmlns="{namespace}">'
        f'<sample><id>S1</id><name></name></sample>'
        f'<xrdMeasurement measurementType="Scan">'
        f'<usedWavelength><kAlpha1 unit="Angstrom">1.5405980</kAlpha1>'
        f'<kAlpha2 unit="Angstrom">1.5444260</kAlpha2></usedWavelength>'
        f'<incidentBeamPath><radius unit="mm">240.00</radius>'
        f'<xRayTube><anodeMaterial>Cu</anodeMaterial></xRayTube>'
        f'</incidentBeamPath>'
        f'<scan scanAxis="{scan_axis}" status="Completed"><dataPoints>'
        f'<positions axis="2Theta" unit="deg">'
        f'<startPosition>{start}</startPosition>'
        f'<endPosition>{end}</endPosition></positions>'
        f'{time}{attn}'
        f'<{element} unit="{unit}">{" ".join(map(str, counts))}</{element}>'
        f'</dataPoints></scan></xrdMeasurement></{root}>',
        encoding="utf-8")
    return path


def test_a_rocking_curve_is_refused_by_the_axis_it_names(tmp_path):
    p = write_xrdml(tmp_path / "rock.xrdml", scan_axis="Omega")

    with pytest.raises(ValueError) as refusal:
        pr.read_pattern(p)
    assert "rock.xrdml" in str(refusal.value)
    assert "rocking curve" in str(refusal.value)


def test_a_rate_gets_a_derived_sigma_from_the_files_own_counting_time(tmp_path):
    p = write_xrdml(tmp_path / "rate.xrdml", element="intensities", unit="cps",
                    counts=(10.0, 20.0, 30.0, 40.0), count_time="4.0")

    data = pr.read_pattern(p)

    assert data.sigma is not None
    assert data.sigma[0] == pytest.approx((10.0 * 4.0) ** 0.5 / 4.0)
    assert data.metadata["count_time_s"] == "4.0"


def test_a_rate_with_no_counting_time_withholds_sigma_and_says_why(tmp_path):
    p = write_xrdml(tmp_path / "bare.xrdml", element="intensities", unit="cps",
                    count_time=None)

    notes: list = []
    data = pr.read_pattern(p, diagnostics=notes)

    assert data.sigma is None
    assert [d.code for d in notes] == ["PATTERN_INTENSITY_SCALED"]
    assert "√t" in notes[0].message


def test_a_fixed_two_theta_is_not_a_pattern_however_the_scan_axis_is_spelled(
        tmp_path):
    """``scanAxis`` can say ``Gonio`` on a scan whose 2θ never moved — a φ or χ
    scan written by software that did not update the attribute.  The positions
    are the authority when they contradict it."""
    p = tmp_path / "fixed.xrdml"
    p.write_text(
        '<?xml version="1.0"?><xrdMeasurements '
        'xmlns="http://www.xrdml.com/XRDMeasurement/2.1"><xrdMeasurement>'
        '<scan scanAxis="Gonio"><dataPoints>'
        '<positions axis="2Theta"><commonPosition>33.0</commonPosition></positions>'
        '<positions axis="Phi"><startPosition>0</startPosition>'
        '<endPosition>90</endPosition></positions>'
        '<counts unit="counts">1 2 3 4</counts>'
        '</dataPoints></scan></xrdMeasurement></xrdMeasurements>', encoding="utf-8")

    with pytest.raises(ValueError, match="single fixed position"):
        pr.read_pattern(p)


def test_a_position_list_that_disagrees_with_the_data_is_refused(tmp_path):
    p = tmp_path / "short.xrdml"
    p.write_text(
        '<?xml version="1.0"?><xrdMeasurements '
        'xmlns="http://www.xrdml.com/XRDMeasurement/2.1"><xrdMeasurement><scan '
        'scanAxis="2Theta"><dataPoints><positions axis="2Theta">'
        '<listPositions>10 11 12</listPositions></positions>'
        '<counts unit="counts">1 2 3 4</counts>'
        '</dataPoints></scan></xrdMeasurement></xrdMeasurements>', encoding="utf-8")

    with pytest.raises(ValueError, match="3 positions for 4"):
        pr.read_pattern(p)


def test_xml_that_is_not_an_xrdml_is_not_claimed_by_this_reader(tmp_path):
    """The sniff is the **root element**, not the suffix: a `.xrdml`-named
    something-else keeps falling down the registry rather than being parsed as a
    measurement it is not.  It lands on the text catch-all, which refuses it by
    name — which is the whole point of the catch-all being a reader and not a
    fallback that guesses."""
    p = tmp_path / "other.xrdml"
    p.write_text('<?xml version="1.0"?><plotData><x>1</x></plotData>',
                 encoding="utf-8")

    assert identify_format(p).name == "xy"
    with pytest.raises(ValueError) as refusal:
        pr.read_pattern(p)
    assert "other.xrdml" in str(refusal.value)


def test_a_prefixed_root_element_is_still_claimed(tmp_path):
    """A default namespace is what the real files use, but a prefix is legal —
    and a sniff that reads ``<x:xrdMeasurements>`` as an element named ``x`` is
    the kind of near-miss that shows up only on somebody else's export."""
    p = tmp_path / "prefixed.xrdml"
    p.write_text('<?xml version="1.0"?><x:xrdMeasurements '
                 'xmlns:x="http://www.xrdml.com/XRDMeasurement/1.6">'
                 '<x:xrdMeasurement><x:scan scanAxis="Gonio"><x:dataPoints>'
                 '<x:positions axis="2Theta"><x:startPosition>10</x:startPosition>'
                 '<x:endPosition>13</x:endPosition></x:positions>'
                 '<x:counts unit="counts">1 2 3 4</x:counts>'
                 '</x:dataPoints></x:scan></x:xrdMeasurement></x:xrdMeasurements>',
                 encoding="utf-8")

    assert identify_format(p).name == "xrdml"
    assert len(pr.read_pattern(p).two_theta) == 4


def test_a_comment_before_the_root_does_not_decide_the_sniff(tmp_path):
    """A comment may legally contain angle brackets, so it is stripped before the
    first element is looked for — otherwise a `<scan>` mentioned in prose wins."""
    p = tmp_path / "commented.xrdml"
    p.write_text('<?xml version="1.0"?><!-- written by <scan> exporter -->'
                 '<xrdMeasurements xmlns="http://www.xrdml.com/XRDMeasurement/1.6">'
                 '<xrdMeasurement><scan scanAxis="Gonio"><dataPoints>'
                 '<positions axis="2Theta"><startPosition>10</startPosition>'
                 '<endPosition>13</endPosition></positions>'
                 '<counts unit="counts">1 2 3 4</counts>'
                 '</dataPoints></scan></xrdMeasurement></xrdMeasurements>',
                 encoding="utf-8")

    assert identify_format(p).name == "xrdml"
    assert len(pr.read_pattern(p).two_theta) == 4


# --------------------------------------------------------------------- rasx
def write_rasx(path: Path, scans, *, manifest_only=(), omit_conditions=False,
               root_extra="") -> Path:
    """A minimal but manifest-shaped ``.rasx`` — the cases no fixture holds.

    A zip of text files, so the circularity a binary writer has to manage does
    not arise here: what this restates from the reader's understanding is the
    *manifest convention*, and that is written down in the reader's docstring
    from four real archives.
    """
    import zipfile

    groups, members = [], {}
    for i, scan in enumerate(scans):
        profile = f"Profile{i}.txt"
        conditions = f"MesurementConditions{i}.xml"
        rows = "\n".join("\t".join(f"{v}" for v in row) for row in scan["rows"])
        members[f"Data{i}/{profile}"] = "﻿" + rows + "\n"
        listed = f'<ContentHashList Name="{profile}" ContentHash="0" />'
        if not omit_conditions:
            members[f"Data{i}/{conditions}"] = (
                '﻿<?xml version="1.0" encoding="utf-8"?><MeasurementConditions>'
                f'<HWConfigurations><XrayGenerator><TargetName>Cu</TargetName>'
                f'<WavelengthKalpha1>1.540593</WavelengthKalpha1>'
                f'</XrayGenerator></HWConfigurations><ScanInformation>'
                f'<AxisName>{scan.get("axis", "TwoTheta")}</AxisName>'
                f'<Step>{scan.get("step", 0.02)}</Step>'
                f'<Speed>{scan.get("speed", 1.0)}</Speed>'
                f'<SpeedUnit>deg/min</SpeedUnit>'
                f'<IntensityUnit>{scan.get("unit", "counts")}</IntensityUnit>'
                f'<SampleName>{scan.get("sample", "")}</SampleName>'
                '</ScanInformation></MeasurementConditions>')
            listed += f'<ContentHashList Name="{conditions}" ContentHash="0" />'
        groups.append(f'<Data{i} Type="Profile">{listed}</Data{i}>')

    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("root.xml", '﻿<?xml version="1.0" encoding="utf-8"?>'
                         f'<Root Version="1.1.0.0">{"".join(groups)}{root_extra}'
                         "</Root>")
        for name, text in members.items():
            archive.writestr(name, text.encode("utf-8"))
        for name in manifest_only:
            archive.writestr(name, "not a profile\n")
    return path


def test_the_real_rasx_powder_scan_reads_whole():
    data = pr.read_pattern(DATA / "rigaku_powder.rasx")

    assert len(data.two_theta) == 2726
    assert data.two_theta[0] == 10.0 and data.two_theta[-1] == 119.0
    assert data.metadata["scan_axis"] == "TwoTheta"
    assert data.metadata["anode"] == "Cu"
    assert data.metadata["wavelength"] == "1.540593"
    assert data.metadata["count_time_s"] == "2.4"      # 0.04° ÷ 1 deg/min × 60


def test_the_declared_unit_is_refuted_by_arithmetic_in_this_container_too():
    """A correction to this WP's own premise, which recorded cps as *verified by
    fixture* for `.rasx`.

    Two of the three real files declare ``<IntensityUnit>counts</IntensityUnit>``
    and store values like 170.55354309082 that no scale makes integral; the
    third declares counts and *is* integral to the last of 7001 points.  So this
    is the same free-text lie ``.ras`` tells, and the same arithmetic settles it
    — which is why both formats call one function.
    """
    lying: list = []
    liar = pr.read_pattern(DATA / "rigaku_powder.rasx", diagnostics=lying)
    honest: list = []
    truth = pr.read_pattern(DATA / "rigaku_zno_counts.rasx", diagnostics=honest)

    assert liar.metadata["intensity_unit"] == truth.metadata["intensity_unit"]
    assert [d.code for d in lying] == ["PATTERN_INTENSITY_SCALED"]
    assert liar.sigma is None       # withheld, and said so
    assert honest == [] and truth.sigma is None   # withheld, and correct
    assert all(float(v).is_integer() for v in truth.intensity)


def test_the_manifest_is_the_authority_not_the_name_list(tmp_path):
    """A zip may carry anything; ``root.xml`` is what says which members are
    scans and in which order."""
    p = write_rasx(tmp_path / "two.rasx",
                   [dict(rows=[(10.0, 5.0), (10.02, 6.0), (10.04, 7.0)]),
                    dict(rows=[(20.0, 1.0), (20.02, 2.0), (20.04, 3.0)])],
                   manifest_only=("Data9/Profile9.txt", "thumbnail.png"))

    assert [s.index for s in list_scans(p)] == [0, 1]
    assert pr.read_pattern(p, scan=1).two_theta == [20.0, 20.02, 20.04]


def test_the_default_scan_of_a_rasx_is_never_silent(tmp_path):
    p = write_rasx(tmp_path / "two.rasx",
                   [dict(rows=[(10.0, 5.0), (10.02, 6.0)]),
                    dict(rows=[(20.0, 1.0), (20.02, 2.0)])])
    notes: list = []
    data = pr.read_pattern(p, diagnostics=notes)

    assert data.metadata["scan_count"] == "2"
    assert [d.code for d in notes] == ["PATTERN_MULTISCAN_DEFAULTED"]


def test_a_manifest_naming_a_member_the_archive_lacks_is_refused_by_name(tmp_path):
    """The other half of "the manifest is the authority": a real profile member
    is present, so the sniff claims the file, and the manifest still points
    somewhere else.  Following the name list instead would read it happily."""
    import zipfile

    p = tmp_path / "hollow.rasx"
    with zipfile.ZipFile(p, "w") as archive:
        archive.writestr("root.xml", '<Root><Data0 Type="Profile">'
                         '<ContentHashList Name="Profile7.txt" /></Data0></Root>')
        archive.writestr("Data0/Profile0.txt", "10 1\n11 2\n")

    assert identify_format(p).name == "rasx"
    with pytest.raises(ValueError, match="internally inconsistent"):
        pr.read_pattern(p)


def test_a_member_past_the_cap_is_refused_rather_than_materialised(tmp_path,
                                                                   monkeypatch):
    """``ZipInfo.file_size`` is a number in the archive's own header, so it is
    the one a bomb lies about — hence ``read(cap + 1)`` and a length test rather
    than a size check before reading."""
    from pxrdref.io.formats import rasx

    p = write_rasx(tmp_path / "big.rasx",
                   [dict(rows=[(10.0 + 0.01 * i, 5.0) for i in range(200)])])
    monkeypatch.setattr(rasx, "MAX_MEMBER_BYTES", 64)

    with pytest.raises(ValueError, match="larger than"):
        pr.read_pattern(p)


def test_a_zip_that_is_not_a_rasx_is_not_claimed(tmp_path):
    """Zip magic says "an archive"; only a ``Data<N>/Profile<N>.txt`` member says
    whose.  Other zip-container formats sit in the same registry, so the sniff
    has to be about the manifest and never about the magic alone."""
    import zipfile

    p = tmp_path / "other.rasx"
    with zipfile.ZipFile(p, "w") as archive:
        archive.writestr("notes.txt", "not a diffraction file at all")

    with pytest.raises(ValueError) as refusal:
        pr.read_pattern(p)
    assert "other.rasx" in str(refusal.value)
    assert "Supported" in str(refusal.value)


def test_the_attenuator_column_is_reported_here_exactly_as_in_ras(tmp_path):
    """One vendor's unstated convention, not one format's — so the two
    containers share the contract and the code."""
    p = write_rasx(tmp_path / "attn.rasx", [dict(
        rows=[(10.0, 5.0, 1.0), (10.02, 6.0, 10.0), (10.04, 7.0, 1.0)])])

    notes: list = []
    data = pr.read_pattern(p, diagnostics=notes)

    assert data.intensity == [5.0, 6.0, 7.0]          # never applied
    assert "RAS_ATTENUATOR_PRESENT" in [d.code for d in notes]


def test_a_rocking_curve_in_a_rasx_is_refused_on_the_vendors_vocabulary(tmp_path):
    p = write_rasx(tmp_path / "rock.rasx", [dict(
        axis="Omega", rows=[(10.0, 5.0), (10.02, 6.0), (10.04, 7.0)])])

    with pytest.raises(ValueError, match="rocking curve"):
        pr.read_pattern(p)


def test_the_scan_information_block_wins_over_a_like_named_leaf_elsewhere(
        tmp_path):
    """``Step`` and ``Speed`` are generic enough for an optics or alignment block
    to carry one, and a first-wins flatten over the whole document would then
    derive the counting time — and every σ with it — from somebody else's step."""
    import zipfile

    p = write_rasx(tmp_path / "shadow.rasx", [dict(
        step=0.02, speed=1.0, unit="cps",
        rows=[(10.0 + 0.02 * i, 1.5) for i in range(4)])])
    with zipfile.ZipFile(p) as archive:
        names = archive.namelist()
        members = {n: archive.read(n) for n in names}
    conditions = next(n for n in names if "Conditions" in n)
    members[conditions] = members[conditions].replace(
        b"<ScanInformation>",
        b"<Optics><Step>99</Step><Speed>99</Speed></Optics><ScanInformation>")
    with zipfile.ZipFile(p, "w") as archive:
        for name, raw in members.items():
            archive.writestr(name, raw)

    # 0.02° ÷ 1 deg/min × 60 = 1.2 s, not 99/99
    assert pr.read_pattern(p).metadata["count_time_s"] == "1.2"


def test_a_group_with_no_conditions_still_yields_its_points(tmp_path):
    """The points are the pattern and the header is metadata, so losing the
    second is a thinner answer rather than no answer."""
    p = write_rasx(tmp_path / "bare.rasx",
                   [dict(rows=[(10.0, 5.0), (10.02, 6.0), (10.04, 7.0)])],
                   omit_conditions=True)

    notes: list = []
    data = pr.read_pattern(p, diagnostics=notes)

    assert data.two_theta == [10.0, 10.02, 10.04]
    assert "anode" not in data.metadata
    # …and the axis is unknown rather than assumed silently
    assert [d.code for d in notes] == ["PATTERN_X_AXIS_ASSUMED"]


# --------------------------------------------------------------------- brml
def write_brml(path: Path, scans, *, manifest=None, unit="Counts") -> Path:
    """A minimal but view-shaped ``.brml`` — the cases no vendorable file holds.

    The column layout is written *from* ``DataViews`` here exactly as the reader
    reads it back, which is the honest limit of a synthesized fixture: what it
    exercises is the failure paths, not the format.  The two real files are what
    established the layout, and `tests/data/README.md` records what each showed.
    """
    import zipfile

    members, refs = {}, []
    for i, scan in enumerate(scans):
        rows = "".join(f"<Datum>{','.join(str(v) for v in row)}</Datum>"
                       for row in scan["rows"])
        recorded = scan.get("recorded_length", 1)
        names = scan.get("axes", ("TwoTheta", "Theta"))
        axes = "".join(f'<FieldDefinitions FieldName="{a}" AxisId="{a}" />'
                       for a in names)
        # the recorded channel sits after the two fixed ones and every axis —
        # computed rather than fixed, which is the reader's own rule applied to
        # the writer, and the only way a one-axis scan can be written at all
        recorded_start = 2 + len(names)
        name = f"Experiment0/RawData{i}.xml"
        members[name] = (
            '<?xml version="1.0"?><RawData '
            'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
            '<TubeMaterial>Cu</TubeMaterial><WaveLength Unit="Å" Value="1.5406" />'
            f'<DataRoutes><DataRoute RouteFlag="{scan.get("flag", "Measured")}">'
            f'<ScanInformation ScanName="{scan.get("scan_name", "TwoThetaOmegaScan")}" />'
            f'{rows}<DataViews>'
            '<RawDataView xsi:type="FixedRawDataView" Start="0" Length="1" '
            'LogicName="MeasuredTime" Unit="s" />'
            '<RawDataView xsi:type="FixedRawDataView" Start="1" Length="1" '
            'LogicName="AbsorptionFactor" Unit="" />'
            f'<RawDataView xsi:type="VaryingRawDataView" Start="2" '
            f'Length="{len(names)}">'
            f'<Varying>{axes}</Varying></RawDataView>'
            f'<RawDataView xsi:type="RecordedRawDataView" '
            f'Start="{recorded_start}" '
            f'Length="{recorded}"><Recording>'
            f'<Unit Prefix="None" Base="{unit}" /></Recording></RawDataView>'
            '</DataViews></DataRoute></DataRoutes></RawData>')
        refs.append(f"<string>{name}</string>")

    listed = "".join(refs) if manifest is None else manifest
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("Experiment0/DataContainer.xml",
                         '<?xml version="1.0"?><DataContainer '
                         f'RawDataLength="{len(scans)}">'
                         f"<RawDataReferenceList>{listed}</RawDataReferenceList>"
                         "</DataContainer>")
        for name, text in members.items():
            archive.writestr(name, text)
    return path


def test_the_real_brml_reads_through_its_own_channel_description():
    """No index is counted: in this file 2θ is column 2 and the intensity is
    column **7**, which is why GSAS-II's fixed ``entry[2]``/``entry[4]`` is a
    coincidence of one layout rather than the format."""
    data = pr.read_pattern(DATA / "bruker_absorber.brml")

    assert len(data.two_theta) == 2001
    assert data.two_theta[0] == 44.0 and data.two_theta[-1] == 48.0
    assert data.metadata["scan_axis"] == "TwoThetaOmegaScan"
    assert data.metadata["anode"] == "Cu"
    assert data.metadata["wavelength"] == "1.5406"
    assert data.metadata["intensity_unit"] == "Counts"
    assert data.metadata["count_time_s"] == "1.0"


def test_the_bruker_absorber_is_already_applied_so_only_sigma_goes_through_it():
    """The third answer from a third vendor, and the same structural test.

    In this file ``y`` is not integral, ``y × a`` is not, and ``y / a`` **is**;
    and the stored series runs continuously across the point where the absorber
    engages while ``y / a`` steps by a factor of seven.  So Bruker stores the
    corrected intensity — nothing is multiplied — but the Poisson quantity is
    still ``y / a``, so σ = √(y/a)·a.
    """
    notes: list = []
    data = pr.read_pattern(DATA / "bruker_absorber.brml", diagnostics=notes)

    apex = max(range(len(data.intensity)), key=lambda i: data.intensity[i])
    assert data.intensity[apex] == 495559.8          # stored, not multiplied
    assert data.sigma is not None
    assert data.sigma[apex] == pytest.approx((495559.8 / 8.3) ** 0.5 * 8.3)
    # the counted quantity really is y/a: whole numbers, to the last point
    assert all(abs(v / 8.3 - round(v / 8.3)) < 1e-3 or abs(v - round(v)) < 1e-3
               for v in data.intensity)
    assert [d.code for d in notes] == ["BRML_ABSORBER_ENGAGED"]
    assert "8.3" in notes[0].message


def test_a_detector_frame_is_refused_rather_than_read_as_a_profile(tmp_path):
    """``EJZ060_13_004_RSM.brml`` records 1280 channels per row and still claims
    ``AxisId="TwoTheta"`` in its ``ScanAxes``, so the axis check passes and only
    the recorded view's own ``Length`` says what the rows are."""
    p = write_brml(tmp_path / "psd.brml", [dict(
        recorded_length=1280,
        rows=[(1, 1, 44.0 + 0.01 * i, 18.0) + tuple(range(1280))
              for i in range(4)])])

    with pytest.raises(ValueError) as refusal:
        pr.read_pattern(p)
    assert "psd.brml" in str(refusal.value)
    assert "position-sensitive-detector frame" in str(refusal.value)


def test_a_scan_with_no_two_theta_axis_is_refused_by_what_it_does_step(tmp_path):
    p = write_brml(tmp_path / "rock.brml", [dict(
        axes=("Theta",), scan_name="RockingCurveScan",
        rows=[(1, 1, 18.0 + 0.01 * i, 5) for i in range(4)])])   # 2θ never moves

    with pytest.raises(ValueError) as refusal:
        pr.read_pattern(p)
    assert "rocking curve" in str(refusal.value)


def test_the_manifest_orders_the_scans_because_the_name_list_does_not(tmp_path):
    """A real 801-scan archive stores its members …20, 22, 21,
    experimentCollection.xml, 23…, so the zip's own order is not the scans'."""
    p = write_brml(tmp_path / "many.brml",
                   [dict(rows=[(1, 1, 10.0 + 0.01 * i, 5.0, 100 + i)
                               for i in range(4)]),
                    dict(rows=[(1, 1, 30.0 + 0.01 * i, 5.0, 200 + i)
                               for i in range(4)])])
    notes: list = []

    first = pr.read_pattern(p, diagnostics=notes)
    second = pr.read_pattern(p, scan=1)

    assert first.two_theta[0] == 10.0 and second.two_theta[0] == 30.0
    assert [d.code for d in notes] == ["PATTERN_MULTISCAN_DEFAULTED"]
    assert [s.index for s in list_scans(p)] == [0, 1]


def _with_extra_route(path: Path, flag: str) -> Path:
    """The same ``.brml`` with a second ``DataRoute`` spliced in."""
    import zipfile

    with zipfile.ZipFile(path) as archive:
        container = archive.read("Experiment0/DataContainer.xml").decode()
        raw = archive.read("Experiment0/RawData0.xml").decode()
    doubled = raw.replace("</DataRoutes>",
                          f'<DataRoute RouteFlag="{flag}"><Datum>1,1,90,45,7'
                          "</Datum></DataRoute></DataRoutes>")
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("Experiment0/DataContainer.xml", container)
        archive.writestr("Experiment0/RawData0.xml", doubled)
    return path


def test_a_processed_route_beside_the_measured_one_is_not_what_gets_fitted(
        tmp_path):
    """A processed route is somebody else's background subtraction; refining
    against it unasked is the silent substitution this package refuses.  Where
    exactly one route says ``Measured``, that is the answer and the rest are
    ignored — where two do, choosing is the file's job and the reader stops."""
    rows = [(1, 1, 10.0 + 0.01 * i, 5.0, 100 + i) for i in range(4)]

    ignored = _with_extra_route(
        write_brml(tmp_path / "one.brml", [dict(rows=rows)]), "Processed")
    assert pr.read_pattern(ignored).two_theta[0] == 10.0

    ambiguous = _with_extra_route(
        write_brml(tmp_path / "two.brml", [dict(rows=rows)]), "Measured")
    with pytest.raises(ValueError, match="not exactly one marked Measured"):
        pr.read_pattern(ambiguous)


def test_the_xsi_prefix_is_resolved_rather_than_matched_as_text(tmp_path):
    """The prefix is the document's to choose — ``xsi:`` here, ``xs:`` in the
    next file — and ElementTree resolves it away, so matching the literal string
    would break on a file this reader must still open."""
    import zipfile

    p = write_brml(tmp_path / "prefixed.brml",
                   [dict(rows=[(1, 1, 10.0 + 0.01 * i, 5.0, 100 + i)
                               for i in range(4)])])
    with zipfile.ZipFile(p) as archive:
        container = archive.read("Experiment0/DataContainer.xml").decode()
        raw = archive.read("Experiment0/RawData0.xml").decode()
    renamed = raw.replace("xmlns:xsi=", "xmlns:zz=").replace("xsi:type=", "zz:type=")
    with zipfile.ZipFile(p, "w") as archive:
        archive.writestr("Experiment0/DataContainer.xml", container)
        archive.writestr("Experiment0/RawData0.xml", renamed)

    assert len(pr.read_pattern(p).two_theta) == 4


def test_a_manifest_naming_a_missing_raw_data_is_refused_by_name(tmp_path):
    p = write_brml(tmp_path / "hollow.brml",
                   [dict(rows=[(1, 1, 10.0, 5.0, 100)])],
                   manifest="<string>Experiment0/RawData9.xml</string>")

    assert identify_format(p).name == "brml"
    with pytest.raises(ValueError, match="internally inconsistent"):
        pr.read_pattern(p)

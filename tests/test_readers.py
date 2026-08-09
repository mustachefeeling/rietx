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

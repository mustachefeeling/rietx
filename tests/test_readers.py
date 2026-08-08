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

import pytest

import pxrdref as pr
from pxrdref.io.formats import PATTERN_FORMATS, head, multiscan_default
from pxrdref.io.formats.base import PatternFormat, ascending, reader_options_for
from pxrdref.io.readers import identify_format


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

    from pxrdref.io.formats import gsas, pdcif, xy

    for module in (gsas, pdcif, xy):
        body = inspect.getsource(module)
        assert "ascending(" in body, f"{module.__name__} does not use ascending()"
        assert "diagnostics" in body


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
    assert reader_options_for(PATTERN_FORMATS[0], {"block": None}) == {}
    assert reader_options_for(PATTERN_FORMATS[0], {"block": "_meas"}) == {"block": "_meas"}


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


def test_the_registry_order_is_the_dispatch_order():
    """The first format whose ``matches`` returns True reads the file, so the
    tuple's order is behaviour and ``xy`` being last is the whole of why
    anything else is ever reached."""
    names = [f.name for f in PATTERN_FORMATS]
    assert names[-1] == "xy"
    assert len(set(names)) == len(names)

"""What the readers do to files that are *wrong*, not merely unfamiliar.

Every reader in this package is handed bytes somebody else wrote — increasingly
so, since the vendor formats are containers (zip members, XML trees, binary TLV
segments) written by instrument software this project does not own.  A container
parser's natural failure mode is its *library's* exception: ``struct.error``,
``zipfile.BadZipFile``, ``ET.ParseError``.  None of those is a
``ValueError``/``OSError``, and ``ET.ParseError`` subclasses ``SyntaxError``, so
one escaping a reader is a traceback on an API caller and a 500 on the GUI's
upload route rather than "this file could not be read".

So there is one cross-cutting invariant, asserted here rather than trusted:

    **a reader raises ``ValueError`` or ``OSError``, and names the file.**

The harness that earns its keep is truncation — the cheapest way to produce a
file that is *structurally* broken at an arbitrary depth rather than merely
odd, which is what a half-finished copy, an interrupted download and a
network-mounted instrument share drive all produce for real.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import pxrdref as pr
from pxrdref.io.readers import identify_format

DATA = Path(__file__).parent / "data"

#: Every *real* fixture a pattern reader claims, with the reader that claims it.
#: One per reader rather than one per file: the point is to exercise each
#: parser's failure paths, and thirty round-robin ``.prn`` files share one.
REAL_FIXTURES = [
    ("11BM_NAC.fxye", "gsas"),            # GSAS FXYE, 2.5 MB, esd column
    ("FAP.XRA", "gsas"),                  # GSAS STD, fixed-format, Poisson
    ("nist_srm660c_100a.cif", "pdcif"),   # pdCIF through gemmi, two blocks
    ("qarr/corundum.prn", "xy"),          # two-column ASCII
    ("rigaku_nims.ras", "ras"),           # Rigaku text, marked sections
    ("panalytical_powder.xrdml", "xrdml"),      # XRDML 1.6, one scan, counts
    ("panalytical_mesh.xrdml", "xrdml"),        # XRDML 2.1, 101 scans, listPositions
    ("rigaku_powder.rasx", "rasx"),             # a zip container: BOM'd members
]

#: Formats with **no vendorable real file**, built here instead.  Kept apart from
#: the list above rather than mixed into it, because a synthesized file exercises
#: the parser's failure paths and says nothing about the format: it is written
#: from the same understanding the reader was, so the two agree by construction.
#: ``.uxd`` is here because every obtainable real one is GPL or carries no
#: licence at all; ``.rasx`` for a different reason — a real one is vendored and
#: truncated above, but the only real *multi-scan* archive is 2.3 MB, so the
#: several-groups failure paths are reached synthetically
#: (``tests/data/README.md`` names both).
SYNTHETIC_FIXTURES = ["uxd", "rasx"]


def _synthesize(kind: str, path: Path) -> Path:
    from tests.test_readers import write_rasx, write_uxd

    if kind == "uxd":
        return write_uxd(path, [dict(drive="COUPLED", marker="_2THETACOUNTS",
                                     steptime=1.0,
                                     rows=[(10.0 + 0.02 * i, 500 + i % 7)
                                           for i in range(400)])])
    assert kind == "rasx"
    # two groups, so a cut lands inside a manifest, a member and the central
    # directory at different depths
    return write_rasx(path, [dict(rows=[(10.0 + 0.02 * i, 500 + i % 7)
                                        for i in range(200)]),
                             dict(rows=[(40.0 + 0.02 * i, 300 + i % 5)
                                        for i in range(200)])])


#: Where to cut.  Fractions rather than byte counts so the same set of offsets
#: means the same thing on a 3 kB file and a 5 MB one, and deliberately dense
#: near the start, where a header is still being consumed and a parser is most
#: likely to index into something it has not read.
CUTS = (0.0, 0.0005, 0.001, 0.002, 0.004, 0.008, 0.015, 0.03, 0.05, 0.08,
        0.12, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.999)


def test_the_offsets_are_the_twenty_the_docstring_claims():
    assert len(CUTS) == 20 and CUTS == tuple(sorted(set(CUTS)))


@pytest.mark.parametrize("fixture,reader", REAL_FIXTURES)
def test_the_fixture_reads_whole_and_is_claimed_by_the_reader_named(fixture, reader):
    """The control: without this, a harness that truncates a file nothing reads
    would pass by asserting nothing."""
    path = DATA / fixture
    assert identify_format(path).name == reader
    assert len(pr.read_pattern(path).two_theta) > 100


@pytest.mark.parametrize("fixture,reader", REAL_FIXTURES)
def test_every_truncation_fails_as_a_value_or_os_error_naming_the_file(
        fixture, reader, tmp_path):
    """Twenty depths per fixture; each one may parse, but may not *crash*.

    A truncation that still parses is a legitimate outcome — half an ``.xy`` is
    a shorter ``.xy`` — so the assertion is on the *kind* of failure, never on
    there being one.
    """
    raw = (DATA / fixture).read_bytes()
    name = Path(fixture).name
    for cut in CUTS:
        stub = tmp_path / f"{int(cut * 1e6):07d}_{name}"
        stub.write_bytes(raw[:int(len(raw) * cut)])
        try:
            pr.read_pattern(stub)
        except (ValueError, OSError) as exc:
            assert stub.name in str(exc) or name in str(exc), (
                f"{fixture} cut at {cut}: refusal does not name the file: {exc}")
        except Exception as exc:                       # noqa: BLE001 - the point
            raise AssertionError(
                f"{fixture} cut at {cut} raised {type(exc).__module__}."
                f"{type(exc).__name__}, which is neither ValueError nor OSError "
                f"— a reader must convert its parser's exception at its own "
                f"boundary: {exc}") from exc


@pytest.mark.parametrize("fixture,_reader", REAL_FIXTURES)
def test_a_fixture_with_a_nul_spliced_in_is_refused_rather_than_decoded(
        fixture, _reader, tmp_path):
    """The other half of "not merely odd": bytes that are *not* text at all.

    A NUL early in the file is what a binary vendor format looks like to the
    dispatch, and the answer must be the refusal that names the readable
    formats — not a decoder error from whichever reader claimed it anyway.
    """
    raw = bytearray((DATA / fixture).read_bytes()[:8192])
    raw[100:110] = b"\x00" * 10
    stub = tmp_path / Path(fixture).name
    stub.write_bytes(bytes(raw))
    try:
        pr.read_pattern(stub)
    except (ValueError, OSError) as exc:
        assert stub.name in str(exc)
    except Exception as exc:                           # noqa: BLE001 - the point
        raise AssertionError(
            f"{fixture} with a NUL spliced in raised {type(exc).__name__}") from exc


def test_a_directory_is_an_os_error_not_a_confusing_parse(tmp_path):
    """``read_pattern`` is handed paths from a CLI and a project document, and
    a directory is the commonest wrong one — a ``.pxrd`` project passed where
    its pattern was meant."""
    (tmp_path / "project.pxrd").mkdir()
    with pytest.raises(OSError):
        pr.read_pattern(tmp_path / "project.pxrd")


def test_a_missing_file_says_so_before_any_reader_sees_it(tmp_path):
    with pytest.raises(OSError):
        pr.read_pattern(tmp_path / "nope.xy")


def test_an_empty_file_is_refused_by_name(tmp_path):
    """Zero bytes claims nothing and parses as nothing; the refusal has to come
    from the dispatch or the reader, never from numpy reshaping an empty array."""
    p = tmp_path / "empty.xy"
    p.write_bytes(b"")
    with pytest.raises(ValueError) as exc:
        pr.read_pattern(p)
    assert "empty.xy" in str(exc.value)


@pytest.mark.parametrize("kind", SYNTHETIC_FIXTURES)
def test_every_truncation_of_a_synthesized_fixture_fails_the_same_way(kind, tmp_path):
    """The same invariant for a format that has no real fixture to truncate.

    Weaker evidence and deliberately labelled as such — the file agrees with the
    reader by construction — but a truncation still cuts mid-number, mid-marker
    and mid-header, which is where an ASCII parser indexes into what it has not
    read.
    """
    raw = _synthesize(kind, tmp_path / f"whole.{kind}").read_bytes()
    for cut in CUTS:
        stub = tmp_path / f"{int(cut * 1e6):07d}.{kind}"
        stub.write_bytes(raw[:int(len(raw) * cut)])
        try:
            pr.read_pattern(stub)
        except (ValueError, OSError) as exc:
            assert stub.name in str(exc), (
                f"{kind} cut at {cut}: refusal does not name the file: {exc}")
        except Exception as exc:                       # noqa: BLE001 - the point
            raise AssertionError(
                f"synthesized {kind} cut at {cut} raised "
                f"{type(exc).__module__}.{type(exc).__name__}: {exc}") from exc

"""Writers for the **binary** vendor formats, which have no vendorable fixture.

The text formats' writers live inline in ``test_readers.py``: writing a
``.uxd`` or a ``.ras`` is writing lines, and a line is self-describing.  A
binary format is not, and packing one raises a circularity the text ones never
face — a fixture built from the reader's own understanding agrees with the
reader by construction and proves nothing about the format.  Three rules keep
that from being what these writers are:

1. **The offsets here are written literally, and are not shared with the
   reader.**  Not an import, not a constant, not a helper: if
   ``bruker_raw.py``'s field table drifts, these functions keep packing the old
   one and the tests fail.  A writer that consulted the reader could only ever
   confirm that the reader agrees with itself.
2. **The offsets were cross-checked against a second, independent
   description.**  For Bruker RAW v4 the two that agree are (a) the real file
   ``tests/data/bruker_raw4_scrambled.raw``, walked byte by byte and reported in
   ``tests/data/README.md``, and (b) GSAS-II's ``G2pwd_BrukerRAW.py``, read as a
   specification only.  Where a third description exists — FAIRmat's
   ``bruker_raw_parser.py`` — it is not independent: it hard-codes absolute
   offsets taken from that same file.
3. **The reader carries a self-consistency gate**, so a wrong parse raises
   rather than returning plausible garbage: a range header's nested segment
   chain must end *exactly* on the declared ``hdrSize``, and
   ``data + datumSize·nSteps`` must land on the next range or on EOF.  These
   writers exist partly to violate those gates on purpose.

So what a synthesized file exercises is the reader's **failure paths and its
options** — a second range, a narrower datum, a drive that is not 2θ, a header
that overruns — never the format itself.  The real fixture is the only evidence
about the format, and it is evidence about structure alone (its intensities are
scrambled; ``tests/data/README.md`` has the measurement).
"""

from __future__ import annotations

import struct
from pathlib import Path

#: Bruker RAW v4, packed from the literal field table — see rule 1 above.
_V4_MAGIC = b"RAW4.00\x00"
_V4_SEGMENT_START = 61


def _fixed(text: str, width: int) -> bytes:
    """A NUL-padded fixed-width field, refusing text that would not fit."""
    raw = text.encode("latin-1")
    if len(raw) >= width:
        raise ValueError(f"{text!r} does not fit a {width}-byte field")
    return raw + b"\x00" * (width - len(raw))


def _keyvalue(key: str, value: str) -> bytes:
    """A type-10 segment: uint32 type, uint32 length, 4 unused, key[24], value."""
    body = value.encode("latin-1") + b"\x00"
    return (struct.pack("<III", 10, 36 + len(body), 0) + _fixed(key, 24) + body)


def _source(anode: str, waves: tuple[float, float, float, float, float]) -> bytes:
    """A type-30 segment: 64 unused, then Kα-mean/Kα1/Kα2/Kβ/ratio, 4, anode[4]."""
    body = (b"\x00" * 64 + struct.pack("<5d", *waves) + b"\x00" * 4
            + _fixed(anode, 4))
    return struct.pack("<II", 30, 8 + len(body) + 12) + body + b"\x00" * 12


def _drive(name: str, position: float, flag: int) -> bytes:
    """A type-50 segment, 92 bytes: flag, name[24], 20 unused, position."""
    body = (struct.pack("<I", flag) + _fixed(name, 24) + b"\x00" * 20
            + struct.pack("<d", position))
    return struct.pack("<II", 50, 92) + body + b"\x00" * (92 - 8 - len(body))


def write_raw4(path: Path, ranges, *, sample="Synthesized", comment="",
               anode="Cu", waves=(1.5418, 1.5406, 1.5444, 1.3922, 0.5),
               marker=0, header_overrun=0) -> Path:
    """A Bruker RAW v4 file holding ``ranges``.

    Each range is a dict: ``start``, ``step``, ``intensity`` (the values, in
    order), and optionally ``scan_type``, ``drives`` (``(name, position, flag)``
    triples, defaulting to a locked-coupled θ/2θ pair with 2Theta flagged),
    ``datum_size`` (4 or more, a multiple of 4) and ``step_time_ms``.

    ``header_overrun`` mis-states ``hdrSize`` by that many bytes without moving
    the data, which is what the reader's "the chain must end exactly here" gate
    is for; ``marker`` picks which of the two range markers to write.
    """
    out = bytearray(_V4_MAGIC + struct.pack("<I", 0xFFEF)
                    + _fixed("04/07/2025", 12) + _fixed("20:48:56", 10))
    out += b"\x00" * (_V4_SEGMENT_START - len(out))
    out += _keyvalue("USER", "Administrator")
    out += _keyvalue("SAMPLEID", sample)
    out += _keyvalue("COMMENT", comment)
    out += _source(anode, waves)

    for spec in ranges:
        drives = spec.get("drives", (("2Theta", spec["start"], 0),
                                     ("Theta", spec["start"] / 2, 0),
                                     ("2Theta", spec["start"], 2)))
        datum = spec.get("datum_size", 8)
        header = b"".join(_drive(*d) for d in drives)
        y = list(spec["intensity"])

        out += struct.pack("<I", marker)
        out += b"\x00" * 28
        out += _fixed(spec.get("scan_type", "Locked Coupled"), 24)
        out += b"\x00" * 16
        out += struct.pack("<dd", spec["start"], spec["step"])
        out += struct.pack("<I", len(y))
        out += struct.pack("<f", spec.get("step_time_ms", 310.0))
        out += b"\x00" * 4
        out += struct.pack("<ff", 40.0, 40.0)
        out += b"\x00" * 4
        out += struct.pack("<d", waves[1])
        out += b"\x00" * 16
        out += struct.pack("<II", datum, len(header) + header_overrun)
        out += b"\x00" * 16
        out += header
        for value in y:
            out += struct.pack("<f", value) + b"\x00" * (datum - 4)

    path.write_bytes(bytes(out))
    return path

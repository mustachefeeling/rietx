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
   offsets taken from that same file.  For **v3** there are three that agree —
   GSAS-II, ``bracerino/xrd-file-converter`` (MIT) and ``reductus/reductus``
   (Unlicense), the last a field-by-field transcription of Bruker's own header
   definition — and **no** file at all, which is why v3's gates in the reader
   are the strict ones.
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


#: Bruker RAW v3 (`RAW1.01`), packed from its own literal field table.
_V3_MAGIC = b"RAW1.01\x00"
_V3_HEADER = 712
#: the range header's own declared length here.  The format lets it vary — the
#: reader reads the declared value — so the writer picks a size that is not the
#: minimum, which is what makes "data starts at header + extras" testable.
_V3_RANGE_HEADER = 304


def _v3_extra(record_type: int, length: int) -> bytes:
    """One optional record between a range header and its data.

    These are what `total_size_of_extra_records` counts, and what GSAS-II's
    literal `+40` is standing in for. Content is irrelevant to a pattern reader;
    only the `(type, length)` pair and the total are.
    """
    return struct.pack("<ii", record_type, length) + b"\x00" * (length - 8)


def write_raw3(path: Path, ranges, *, sample="Synthesized", anode="Cu",
               radius=250.0, trailing=b"") -> Path:
    """A Bruker RAW v3 file holding `ranges`.

    Each range is a dict: `start`, `step`, `intensity`, and optionally
    `scan_type` (the enumerated code, default 0 = locked coupled), `step_time`,
    `wavelength`, `extras` (a list of `(type, length)` optional records) and
    `two_theta` (measured positions, which set the varying-2θ bit and put a
    float64 column in every datum).

    `trailing` appends bytes past the last range, which the reader's
    "the declared ranges must account for the file" gate is for.
    """
    header = bytearray(b"\x00" * _V3_HEADER)
    header[0:8] = _V3_MAGIC
    header[12:16] = struct.pack("<i", len(ranges))
    header[16:26] = _fixed("04/07/25", 10)
    header[26:36] = _fixed("20:48:56", 10)
    header[326:386] = _fixed(sample, 60)
    header[564:568] = struct.pack("<f", radius)
    header[608:612] = _fixed(anode, 4)
    out = bytearray(header)

    for spec in ranges:
        y = list(spec["intensity"])
        measured = spec.get("two_theta")
        columns = 1 if measured is not None else 0
        varying = 1 if measured is not None else 0
        record_length = 4 + 8 * columns
        extras = b"".join(_v3_extra(t, ln) for t, ln in spec.get("extras", ()))

        block = bytearray(b"\x00" * _V3_RANGE_HEADER)
        block[0:4] = struct.pack("<i", _V3_RANGE_HEADER)
        block[4:8] = struct.pack("<i", len(y))
        block[8:16] = struct.pack("<d", spec["start"] / 2)          # θ start
        block[16:24] = struct.pack("<d", spec["start"])             # 2θ start
        block[176:184] = struct.pack("<d", spec["step"])
        block[192:196] = struct.pack("<f", spec.get("step_time", 1.0))
        block[196:200] = struct.pack("<i", spec.get("scan_type", 0))
        block[212:216] = struct.pack("<f", spec.get("temperature", 0.0))
        block[240:248] = struct.pack("<d", spec.get("wavelength", 1.5406))
        block[248:252] = struct.pack("<i", spec.get("varying", varying))
        block[252:256] = struct.pack("<i", spec.get("record_length",
                                                    record_length))
        block[256:260] = struct.pack("<i", len(extras))
        out += block + extras

        for i, value in enumerate(y):
            out += struct.pack("<f", value)
            if measured is not None:
                out += struct.pack("<d", measured[i])

    out += trailing
    path.write_bytes(bytes(out))
    return path

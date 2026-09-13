"""Philips PC-APD ``.rd`` / ``.sd`` — the binary scan, and its packed counts.

Spec: the offsets, the three enumerated code tables and the intensity rule were
measured here on **28 real files** — the IUCr CPD round-robin kit's own "Binary
Philips RD format (Original logged files)" column — and corroborated against
xylib's ``philips_raw.cpp`` (LGPL, from a vendor-supplied specification) and
PyXRD's ``rd_parser.py`` (BSD-2).  ``ATTRIBUTION.md`` § Format specifications
records which source each fact came from; ``tests/data/README.md`` § Philips
carries the full offset table and the measurements behind every claim here.

**The stored ``uint16`` is not a count.**  It is √-compressed, and this is the
whole reason the format is dangerous rather than merely unfamiliar::

    counts = v * v // 100

Read raw, a ``.rd`` gives a profile with every peak in exactly the right place
and every intensity wrong — peak-to-background ratios compressed by a square
root — which is precisely the plausible wrong pattern no reader can detect from
its own output.  Four things establish the rule: the committed
``qarr/*.prn`` conversions of these very scans, which it reproduces **bit for
bit**; the kit's second, independent converter (the ``.xda`` column), which
agrees on the quantity for 27 of 27 files; four of the 28 files holding counts
above 65535, which a raw ``uint16`` cannot represent at all; and xylib.  **The
permissive description is the one that gets it wrong** — PyXRD omits the decode
entirely, drops the last point (``int((max-min)/step)``) and offsets the
abscissa by half a step.  All three are refuted by the files.

Truncation is deliberate rather than rounding: it is what xylib does and what
the kit's own ``.prn`` converter did, so it is the reading two of the three
independent conversions share.

**Three gates, and they are the format's own redundancy rather than invented
checks.**  Each holds on all 28 real files:

* ``len(file) == data_start + 2·n``, with ``n`` from the header's angle triple;
* ``n == round((end - start) / step) + 1``;
* the ``uint16`` at offset 136 equals ``max(v)`` — a field in no published
  description, found here, and the sharpest of the three because a wrong data
  offset fails it immediately.

**V5 is read on the length gate alone, and that is stated rather than implied.**
All 28 real files are ``V3RD``.  The only V5-specific fact in any source is that
its data begins at 810 instead of 250, and the three places that state it are
one description copied: xylib, then PyXRD and ``Yohko/importtool`` reproducing
its code tables verbatim.  That would ordinarily be the Bruker ``.raw`` v2
footing — one uncorroborated description and no file — and therefore a refusal.
It is read here because the gate is **decisive** in a way v2's never was:
``n`` is derived from header fields, so ``len == 810 + 2·n`` tests the header
offsets *and* the data start jointly, and any error in either fails it rather
than shifting the pattern silently.  A V5 file that fails it is refused by name.

``.sd`` is not a separate format and is not refused by name: xylib's own title
line is "Philips RD raw scan format V3 (.rd) and V5 (.sd)", so the extension
names the version and both are claimed by magic like any other member.
"""

from __future__ import annotations

import math
import struct
from pathlib import Path

import numpy as np

from ...schemas.common import Diagnostic
from ...schemas.pattern import PatternData
from .base import PatternFormat, ascending, head, pattern_data

#: The magic at offset 0, and where that version's intensities begin.  V3's 250
#: was derived here from ``len(file) - 2·n`` on 28 files *and* is what both
#: descriptions state; V5's 810 has only the descriptions (see the module note).
_DATA_START: dict[bytes, int] = {b"V3RD": 250, b"V5RD": 810}

#: Offsets of the header fields this reader uses.  Specification facts, tabled
#: before the parser was written; ``tests/writers_xrd.py`` packs them literally
#: rather than importing them, so the writer cannot drift with the reader.
_ANODE_AT = 85
_WAVELENGTHS_AT = 94       # 3 × float64: λα1, λα2, α2/α1 ratio
_MAX_VALUE_AT = 136        # uint16, equal to max(v) in all 28 real files
_FILE_NAME_AT = 138        # 8 bytes
_SAMPLE_AT = 146           # 20 bytes
_SCAN_AT = 214             # 3 × float64: step, start 2θ, end 2θ

#: The anode code table, from the two descriptions and confirmed on the real
#: files: all 28 read 0, and the kit's own prose independently says a Cu tube.
#:
#: The header carries two neighbouring enumerated fields as well — a
#: diffractometer model at 84 and a tube focus type at 86, which decode to
#: "PW3710 based system" and "LFF" on all 28 and agree with the same prose, so
#: the three together check the published *tables* rather than one file.  They
#: are **not** read into the pattern: no ``METADATA_KEYS`` entry means an
#: instrument model, nothing would consume one, and a declared name with no
#: reader is the claim WP-1076 is about.  The corroboration is recorded where
#: evidence belongs, in ``tests/data/README.md`` § Philips.
_ANODES: dict[int, str] = {0: "Cu", 1: "Mo", 2: "Fe", 3: "Cr"}


def _unpack(fmt: str, buf: bytes, at: int, *, path: Path, what: str) -> tuple:
    """``struct.unpack_from`` that refuses by naming the file, never ``struct.error``."""
    try:
        return struct.unpack_from(fmt, buf, at)
    except struct.error:
        raise ValueError(
            f"{path.name}: the file ends inside {what} — it wants "
            f"{struct.calcsize(fmt)} bytes at offset {at} and holds "
            f"{len(buf)}. The file is truncated or is not the format its magic "
            "bytes claim") from None


def _text(buf: bytes, at: int, length: int) -> str:
    """A fixed-width NUL-padded field, decoded permissively.

    ``latin-1`` for the same reason the Bruker reader uses it: these are
    operator strings from 1990s Windows software and a degree sign in a sample
    name must not make the file unreadable.
    """
    return buf[at:at + length].split(b"\0")[0].decode("latin-1").strip()


def read_philips_rd(path: str | Path, *,
                    diagnostics: list[Diagnostic] | None = None) -> PatternData:
    p = Path(path)
    buf = p.read_bytes()
    magic = buf[:4]
    data_at = _DATA_START.get(magic)
    if data_at is None:
        raise ValueError(f"{p.name} does not begin V3RD or V5RD, so it is not a "
                         "Philips PC-APD scan")

    step, start, end = _unpack("<3d", buf, _SCAN_AT, path=p,
                               what="the scan range record")
    # the span is asked for finiteness, not only for sign: a damaged header can
    # hold an infinity or a denormal step, and ``round()`` answers those with an
    # OverflowError that names neither the file nor the field (io/CLAUDE.md
    # § Refusals).  ``nan`` compares False against everything, so a NaN in any
    # of the three fails ``step > 0.0`` / ``end > start`` and lands here too
    span = (end - start) / step if step > 0.0 else float("nan")
    if not math.isfinite(span) or not end > start:
        raise ValueError(
            f"{p.name}: the header gives a step of {step:g}° over "
            f"{start:g}→{end:g}°, which is not a scan. Either the file is not a "
            "Philips scan or its header is damaged")
    n = round(span) + 1

    # the length gate, and for V5 it is the *whole* of the evidence: n comes
    # from the header, so this tests the header offsets and the data start at
    # once, and a wrong 810 cannot shift the pattern silently
    expected = data_at + 2 * n
    if len(buf) != expected:
        version = magic.decode("ascii", "replace")
        why = ("" if magic == b"V3RD" else
               " No V5 file was obtainable anywhere, so this gate is the whole "
               "of what this build knows about V5: its data offset rests on one "
               "description and nothing has ever checked it against a file. "
               "Rather than read your intensities from a guessed offset, it "
               "refuses.")
        raise ValueError(
            f"{p.name} is {version} and its header describes {start:g}→{end:g}° "
            f"in steps of {step:g}°, which is {n} points — so the file should be "
            f"{expected} bytes and it is {len(buf)}.{why} Re-export it as .udf, "
            ".xy or .xrdml, all of which this build reads")

    packed = np.frombuffer(buf, dtype="<u2", count=n, offset=data_at)
    stated_max, = _unpack("<H", buf, _MAX_VALUE_AT, path=p,
                          what="the maximum-value field")
    if stated_max != int(packed.max()):
        raise ValueError(
            f"{p.name}: the header records a maximum stored value of "
            f"{stated_max} and the data block's largest is {int(packed.max())}. "
            "The file states that number twice and the two disagree, so the "
            "intensities are being read from the wrong offset or the file is "
            "damaged — and a .rd read at the wrong offset still looks like a "
            "diffraction pattern, so it is refused rather than returned")

    # the √ decode, in integer arithmetic so the truncation is exact and the
    # committed .prn oracle is reproduced bit for bit rather than to a tolerance
    counts = (packed.astype(np.int64) ** 2) // 100
    two_theta = start + step * np.arange(n, dtype=np.float64)

    lam1, lam2, _ratio = _unpack("<3d", buf, _WAVELENGTHS_AT, path=p,
                                 what="the wavelength record")
    # the anode is the one code with a consumer — ``suggest_instrument`` matches
    # on it — and decoding it makes the file state its anode *twice*, since λα1
    # says the same thing and a disagreement suppresses the hint
    anode = _ANODES.get(buf[_ANODE_AT])
    sample = _text(buf, _SAMPLE_AT, 20) or _text(buf, _FILE_NAME_AT, 8)

    tt, y, sig = ascending(two_theta, counts.astype(np.float64), None, path=p,
                           fmt=PHILIPS_RD, diagnostics=diagnostics)
    # the decoded quantity *is* a count, so σ is the package's Poisson fallback
    # and no arithmetic test is needed: the file's own encoding says what it is
    return pattern_data(
        p, tt, y, sig, source_file=p.name, format="philips_rd",
        sample=sample or None, anode=anode,
        wavelength=lam1 if lam1 > 0.0 else None,
        wavelength_alpha2=lam2 if lam2 > 0.0 else None)


def looks_philips_rd(p: Path) -> bool:
    """Magic bytes and nothing else.

    Disjoint from ``bruker_raw`` in both directions by construction: that format
    is claimed by ``RAW4.00``/``RAW1.01``/``RAW2``/``RAW `` at offset 0, none of
    which can be ``V3RD`` or ``V5RD``.  So a Philips file named ``.raw`` still
    reaches this reader and a Bruker file named ``.rd`` still reaches that one —
    which matters here more than usual, because ``.raw`` is written by six
    unrelated vendors and ``.rd`` by two.
    """
    return head(p, 4).raw[:4] in _DATA_START


PHILIPS_RD = PatternFormat(
    name="philips_rd",
    title="Philips PC-APD binary scan (.rd, .sd)",
    extensions=(".rd", ".sd"),
    sniff=("the file begins V3RD or V5RD. Its intensities are √-compressed, so "
           "counts = v²//100; the header states its length twice and its "
           "maximum value once, and all three are checked before the pattern is "
           "returned"),
    sigma=("the Poisson fallback: the decoded quantity is a detector count, "
           "which the file's own √ encoding establishes without an arithmetic "
           "test"),
    matches=looks_philips_rd,
    read=read_philips_rd,
)

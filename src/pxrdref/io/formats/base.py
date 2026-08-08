"""Shared machinery for the pattern-format readers.

There is one module per format in this package, because a format's spec
citation, its parser, its ``sniff``/``sigma`` prose, its reader options and its
**licence fence** are one fact each and belong adjacent — ten fences in one file
drift.  What lives *here* is what more than one of them needs: the registry
entry they each construct, and the bounded head read every text sniff shares.
"""

from __future__ import annotations

import codecs
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from ...schemas.pattern import PatternData


@dataclass(frozen=True)
class PatternFormat:
    """One format :func:`pxrdref.read_pattern` accepts, and how it is recognised.

    A registry rather than a chain of ``if``s inside ``read_pattern`` because
    three consumers need the *same* facts and each would otherwise restate them:
    the dispatch itself, ``capabilities()`` (which must say what this package
    can actually open — WP-1007), and a project's ``DataRef``, which records
    *which reader claimed the file* so re-opening reproduces the reader call and
    not merely the bytes (WP-1005).

    ``options`` names the reader keywords a caller may have supplied, because
    those have to be recorded and replayed too: a pdCIF holding both a ``_meas``
    and a ``_calc`` block (the NIST SRM certification files do) reads as a
    different pattern depending on ``block``.
    """

    name: str
    title: str
    #: conventional suffixes — informational except where ``sniff`` uses them
    extensions: tuple[str, ...]
    #: how the format is recognised, in words a UI can show
    sniff: str
    #: where per-point σ comes from, or how the Poisson fallback is reached
    sigma: str
    matches: Callable[[Path], bool]
    read: Callable[..., PatternData]
    options: tuple[str, ...] = field(default_factory=tuple)


#: How much of a file a *sniff* may look at.  Every text dispatch goes through
#: :func:`head`, so the cost of asking "is this yours?" is bounded no matter how
#: many formats are registered or how large the pattern is.
HEAD_BYTES = 4096

#: Byte-order marks worth recognising, longest-first.  ``utf-16`` (rather than
#: an explicit endianness) is the codec on purpose: it reads the mark to pick
#: LE or BE *and* strips it, which is what a caller decoding the whole file
#: wants.  UTF-32 is deliberately absent — no diffractometer writes it, and
#: guessing at one more encoding would buy nothing but a wrong guess.
_BOMS: tuple[tuple[bytes, str], ...] = (
    (codecs.BOM_UTF8, "utf-8-sig"),
    (codecs.BOM_UTF16_LE, "utf-16"),
    (codecs.BOM_UTF16_BE, "utf-16"),
)


@dataclass(frozen=True)
class Head:
    """The first :data:`HEAD_BYTES` of a file, read once and decoded once."""

    #: the bytes actually read, byte-order mark included
    raw: bytes
    #: :attr:`raw` decoded with :attr:`encoding`; undecodable bytes are dropped,
    #: so a *sniff* may always search it and a binary file simply matches nothing
    text: str
    #: the codec to decode the whole file with — the one the mark names, else UTF-8
    encoding: str
    #: whether a byte-order mark was actually found.  Load-bearing beyond the
    #: encoding: ASCII-range UTF-16LE is *valid* UTF-8 with interleaved NULs, so
    #: a mark is what separates "Windows vendor export" from "binary".
    bom: bool


def head(path: str | Path, n: int = HEAD_BYTES) -> Head:
    """The first ``n`` bytes of ``path``, decoded for a sniff.

    Bounded on purpose.  The predecessor of this function decoded a whole file
    and then sliced 4 kB off it, which is an O(N) decode per dispatch on a 60 MB
    pattern.  It is deliberately **not** cached either: ``restage`` re-reads the
    same path, so a path-keyed cache would be a correctness hazard for exactly
    the file a user just replaced.
    """
    with open(path, "rb") as fh:
        raw = fh.read(n)
    encoding, bom = "utf-8", False
    for mark, codec in _BOMS:
        if raw.startswith(mark):
            encoding, bom = codec, True
            break
    return Head(raw=raw, text=raw.decode(encoding, errors="ignore"),
                encoding=encoding, bom=bom)

"""Pattern file readers — the front door.

The parsers themselves live one per module in :mod:`pxrdref.io.formats`; this
module is the entry point every caller uses (:func:`read_pattern`,
:func:`identify_format`) plus the re-exports that keep ``pxrdref.io.readers``
the address it has always been for ``PatternFormat``, ``PATTERN_FORMATS`` and
:func:`read_pdcif`.

Which formats, and how each is recognised, is :mod:`pxrdref.io.formats`'
business — including why the registry's *order* is behaviour rather than
presentation.  When the file carries per-point esds (or least-squares weights,
from which σ = 1/√w) they are stored in ``PatternData.sigma`` — never overridden
by the Poisson fallback (review finding M5).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..schemas.pattern import PatternData
from .formats import (
    PATTERN_FORMATS,
    READER_OPTIONS,
    PatternFormat,
    ReaderOption,
    read_pdcif,
    reader_options_for,
)

__all__ = [
    "PATTERN_FORMATS",
    "READER_OPTIONS",
    "PatternFormat",
    "ReaderOption",
    "identify_format",
    "read_pattern",
    "read_pdcif",
    "reader_options_for",
]


def read_pattern(path: str | Path, **options: Any) -> PatternData:
    """Read any supported pattern file, dispatching on *content* first.

    GSAS raw files are recognised by their ``BANK`` record rather than by
    suffix — the format is written with a zoo of extensions (``.fxye``,
    ``.gsas``, ``.gda``, ``.xra``, ``.raw``, …) and the record is unambiguous.

    ``options`` are the reader keywords in :data:`READER_OPTIONS` — ``block``
    for a pdCIF's data block, and later the ``scan`` a multi-scan vendor file
    holds several of.  They are named rather than positional precisely so a
    caller (or a project reopening its own pattern) need not know which reader
    will claim the file: an option this format does not take is dropped, while
    an option *no* format takes is a typo and raises.  See
    :func:`~pxrdref.io.formats.base.reader_options_for` for that distinction.
    """
    p = Path(path)
    fmt = identify_format(p)
    return fmt.read(p, **reader_options_for(fmt, options))


def identify_format(path: str | Path) -> PatternFormat:
    """Which registered format claims ``path`` — the dispatch, written once."""
    p = Path(path)
    for fmt in PATTERN_FORMATS:
        if fmt.matches(p):
            return fmt
    raise ValueError(f"no reader claims {p}")  # pragma: no cover - xy is total

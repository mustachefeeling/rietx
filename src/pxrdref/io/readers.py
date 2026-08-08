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

from ..schemas.common import Diagnostic
from ..schemas.pattern import PatternData
from .formats import (
    PATTERN_FORMATS,
    READER_OPTIONS,
    PatternFormat,
    ReaderOption,
    head,
    looks_binary,
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


def read_pattern(path: str | Path, *, diagnostics: list[Diagnostic] | None = None,
                 **options: Any) -> PatternData:
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

    ``diagnostics``, when a list is passed, collects what the reader **repaired
    or assumed** — a scan stored high→low and reversed, a duplicated point
    dropped, an option that did not apply.  It is the same channel
    :func:`~pxrdref.crystallography.cif.structure_from_cif` takes and exists
    for the same reason: a reader is the one layer that may silently correct a
    stranger's file, and it may only do so where it can say that it did.
    Returning a bare :class:`PatternData` was an accident, not a design.
    """
    p = Path(path)
    fmt = identify_format(p)
    kwargs = reader_options_for(fmt, options, diagnostics=diagnostics)
    return fmt.read(p, diagnostics=diagnostics, **kwargs)


def identify_format(path: str | Path) -> PatternFormat:
    """Which registered format claims ``path`` — the dispatch, written once.

    Reachable as a refusal since ``xy`` stopped being total: a file no format
    claims is one this build cannot read, and saying **which formats it can**
    is the whole difference between a message and a traceback.  Built from the
    registry rather than written out, so a format added tomorrow appears in it.
    """
    p = Path(path)
    for fmt in PATTERN_FORMATS:
        if fmt.matches(p):
            return fmt
    why = " (it looks binary)" if looks_binary(head(p)) else ""
    known = ", ".join(f"{f.title} [{', '.join(f.extensions) or 'any'}]"
                      for f in PATTERN_FORMATS)
    raise ValueError(
        f"{p.name} is not a powder pattern this build can read{why}. "
        f"Supported: {known}")

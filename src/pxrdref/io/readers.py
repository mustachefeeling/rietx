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

from ..schemas.pattern import PatternData
from .formats import PATTERN_FORMATS, PatternFormat, read_pdcif

__all__ = [
    "PATTERN_FORMATS",
    "PatternFormat",
    "identify_format",
    "read_pattern",
    "read_pdcif",
]


def read_pattern(path: str | Path, *, block: str | None = None) -> PatternData:
    """Read any supported pattern file, dispatching on *content* first.

    GSAS raw files are recognised by their ``BANK`` record rather than by
    suffix — the format is written with a zoo of extensions (``.fxye``,
    ``.gsas``, ``.gda``, ``.xra``, ``.raw``, …) and the record is unambiguous.

    ``block`` is passed through to :func:`read_pdcif` and ignored by the other
    formats, so a caller (or a project reopening its own pattern) can name the
    data block without having to know which reader will claim the file.
    """
    p = Path(path)
    fmt = identify_format(p)
    return fmt.read(p, block=block) if "block" in fmt.options else fmt.read(p)


def identify_format(path: str | Path) -> PatternFormat:
    """Which registered format claims ``path`` — the dispatch, written once."""
    p = Path(path)
    for fmt in PATTERN_FORMATS:
        if fmt.matches(p):
            return fmt
    raise ValueError(f"no reader claims {p}")  # pragma: no cover - xy is total

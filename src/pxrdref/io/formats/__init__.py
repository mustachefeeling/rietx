"""The pattern-format registry — one module per format, ordered for dispatch.

:data:`PATTERN_FORMATS` is the single ordered list every consumer reads: the
dispatch in :func:`pxrdref.io.readers.identify_format`, ``capabilities()``
(WP-1007, which must say what this build can actually open), and a project's
``DataRef`` (WP-1005, which records *which reader claimed the file*).

**The order is behaviour, not presentation** — the first format whose ``matches``
returns True reads the file — and it runs strongest evidence first:

1. **magic bytes** and container manifests, which no other format can imitate;
2. a **required first line** or XML root element, which the format's own spec
   mandates;
3. **suffix**, where the format has no in-band marker (pdCIF);
4. a **loose text sniff** (GSAS's ``BANK`` record anywhere in the first 4 kB);
5. the two/three-column ASCII catch-all, **last**.

Binary-claiming formats go first so nothing tries to decode their bytes as text.
"""

from __future__ import annotations

from .base import (
    HEAD_BYTES,
    READER_OPTIONS,
    Head,
    PatternFormat,
    ReaderOption,
    ascending,
    head,
    looks_binary,
    multiscan_default,
    reader_options_for,
)
from .gsas import GSAS, read_gsas
from .pdcif import PDCIF, read_pdcif
from .xy import XY, read_xy

#: Every format ``read_pattern`` accepts, **in dispatch order** (see above).
PATTERN_FORMATS: tuple[PatternFormat, ...] = (PDCIF, GSAS, XY)

__all__ = [
    "HEAD_BYTES",
    "PATTERN_FORMATS",
    "READER_OPTIONS",
    "Head",
    "PatternFormat",
    "ReaderOption",
    "ascending",
    "head",
    "looks_binary",
    "multiscan_default",
    "read_gsas",
    "read_pdcif",
    "read_xy",
    "reader_options_for",
]

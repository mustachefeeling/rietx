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
    METADATA_KEYS,
    READER_OPTIONS,
    Head,
    PatternFormat,
    ReaderOption,
    ScanInfo,
    ascending,
    head,
    looks_binary,
    metadata,
    multiscan_default,
    pattern_data,
    reader_options_for,
    sigma_from_cps,
)
from .chi import CHI, read_chi
from .dif import DIF, read_dif
from .gsas import GSAS, read_gsas
from .pdcif import PDCIF, read_pdcif
from .ras import RAS, read_ras
from .xy import XY, read_xy

#: Every format ``read_pattern`` accepts, **in dispatch order** (see above).
#: ``RAS`` sits above the suffix and loose-text sniffs because it is recognised
#: by a first line its own spec requires, which is stronger evidence than either.
PATTERN_FORMATS: tuple[PatternFormat, ...] = (RAS, PDCIF, GSAS, CHI, DIF, XY)

__all__ = [
    "HEAD_BYTES",
    "METADATA_KEYS",
    "PATTERN_FORMATS",
    "READER_OPTIONS",
    "Head",
    "PatternFormat",
    "ReaderOption",
    "ScanInfo",
    "ascending",
    "head",
    "looks_binary",
    "metadata",
    "multiscan_default",
    "pattern_data",
    "read_chi",
    "read_dif",
    "read_gsas",
    "read_pdcif",
    "read_ras",
    "read_xy",
    "reader_options_for",
    "sigma_from_cps",
]

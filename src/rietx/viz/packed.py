"""Curves for a browser chart, as a JSON header and typed arrays (WP-1461, D4).

A chart that zooms in the browser needs every channel once. As JSON that costs
the server 52-57 ms of ``json.dumps`` and the browser 4-9 ms of parse on the
11-BM NAC pattern, and both fall to under 2 ms as raw float64 at 57 % of the
bytes (the WP's § The payload behind a client zoom). Float64 rather than
float32, because a Σχ² re-based at a zoom as ``cum[j] − cum[i−1]`` loses 1.2e-3
of itself in float32 over a narrow window.

The body is a little-endian uint32 header length, the JSON header padded with
spaces to an 8-byte boundary, then each array padded to 8 bytes. The header's
``arrays`` lists each one's ``name``, ``dtype``, ``offset`` (from the first
array) and ``length``, so a reader makes a typed-array view with no copy.
``rxplot.mjs``'s ``unpack`` is the browser's reader and :func:`unpack` is
Python's.
"""

from __future__ import annotations

import json
import struct
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import numpy as np

#: What a route serves a packed body as.
MEDIA_TYPE = "application/octet-stream"

#: About the most channels a packed payload carries (D4 and D5). The chart
#: paints each pixel column's lowest and highest point, and the pilot measured
#: that at 132 992 channels, the largest pattern the repository reads, with no
#: long frame. The spike's 200 000 had one, so a pattern past this is
#: decimated by ``viz.compare.decimation_index`` first, whose count is a
#: budget: a bucket's minimum and maximum can bring it a channel over. The GUI's
#: curves routes and ``rietx compare`` both send under it.
CURVES_CEILING = 150_000

#: The two dtypes a browser reads as a typed array with no conversion.
_FLOAT, _INT = "<f8", "<i4"


@dataclass(frozen=True)
class Packed:
    """A header and named arrays, packed only when a transport asks.

    A session verb returns one, so the verb knows nothing of the wire. The GUI
    server calls :meth:`to_bytes` where it would call ``json.dumps``.
    """

    header: dict[str, Any]
    arrays: dict[str, np.ndarray]

    def to_bytes(self, dumps: Callable[[Any], str] = json.dumps) -> bytes:
        return pack(self.header, self.arrays, dumps)


def _typed(name: str, values) -> np.ndarray:
    a = np.asarray(values)
    if a.dtype.kind == "f":
        return a.astype(_FLOAT, copy=False)
    if a.dtype.kind in "iub":
        if a.size and (a.min() < -2**31 or a.max() >= 2**31):
            raise ValueError(f"{name}: an index past int32 has no typed array to read it")
        return a.astype(_INT, copy=False)
    raise ValueError(f"{name}: dtype {a.dtype} is neither a float nor an integer")


def pack(header: dict[str, Any], arrays: dict[str, Any],
         dumps: Callable[[Any], str] = json.dumps) -> bytes:
    """The body for ``header`` and ``arrays``. Floats go as float64, integers as int32."""
    if "arrays" in header:
        raise ValueError("'arrays' is the packed format's own header key")
    specs, blobs, offset = [], [], 0
    for name, values in arrays.items():
        a = _typed(name, values)
        raw = np.ascontiguousarray(a).tobytes()
        specs.append({"name": name, "dtype": a.dtype.str, "offset": offset,
                      "length": int(a.size)})
        pad = -len(raw) % 8
        blobs.append(raw + b"\0" * pad)
        offset += len(raw) + pad
    head = dumps({**header, "arrays": specs}).encode("utf-8")
    head += b" " * (-(4 + len(head)) % 8)
    return struct.pack("<I", len(head)) + head + b"".join(blobs)


def unpack(body: bytes) -> Packed:
    """The header and arrays of a packed body, the arrays copied out of it."""
    (n,) = struct.unpack_from("<I", body, 0)
    header = json.loads(body[4:4 + n])
    base, arrays = 4 + n, {}
    for spec in header.pop("arrays"):
        start = base + spec["offset"]
        arrays[spec["name"]] = np.frombuffer(
            body, dtype=spec["dtype"], count=spec["length"], offset=start).copy()
    return Packed(header, arrays)

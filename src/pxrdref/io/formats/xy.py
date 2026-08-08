"""Two/three-column ASCII — the format everything can be exported to.

No spec: the shape *is* the format.  Rows of ``2θ y [σ]``, comment lines
starting ``#``/``!``/``'``/``/``, whitespace or comma separated.  Because there
is nothing to recognise, this reader is the last entry in the dispatch order and
claims whatever is left — which is **not** the same as everything: a file whose
first 4 kB holds a NUL is binary and is not claimed, so it reaches
``identify_format``'s refusal by name rather than this reader's decoder.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from ...schemas.common import Diagnostic
from ...schemas.pattern import PatternData
from .base import PatternFormat, ascending, head, looks_binary


def read_xy(path: str | Path, *,
            diagnostics: list[Diagnostic] | None = None) -> PatternData:
    p = Path(path)
    rows = []
    # the mark decides the codec, so a UTF-16 export from Windows vendor
    # software reads instead of dying on "no numeric data found"
    for line in p.read_text(encoding=head(p).encoding, errors="replace").splitlines():
        s = line.strip()
        if not s or s.startswith(("#", "!", "'", "/")):
            continue
        parts = s.replace(",", " ").split()
        try:
            vals = [float(v) for v in parts[:3]]
        except ValueError:
            continue
        if len(vals) >= 2:
            rows.append(vals)
    if not rows:
        raise ValueError(f"no numeric data found in {p}")
    n_cols = min(len(r) for r in rows)
    arr = np.array([r[:n_cols] for r in rows], dtype=np.float64)
    sigma = arr[:, 2] if n_cols >= 3 and np.any(arr[:, 2] > 0) else None
    tt, y, sig = ascending(arr[:, 0], arr[:, 1], sigma, path=p, fmt=XY,
                           diagnostics=diagnostics)
    return PatternData(two_theta=tt.tolist(), intensity=y.tolist(),
                       sigma=None if sig is None else sig.tolist(),
                       metadata={"source_file": p.name})


XY = PatternFormat(
    name="xy",
    title="Two/three-column ASCII (.xy / .xye)",
    extensions=(".xy", ".xye", ".dat", ".prn", ".txt"),
    sniff="any text file left over that parses as numeric rows",
    sigma="the third column when present and positive, else the Poisson fallback",
    # last, but no longer *total*: a file with a NUL in its first 4 kB is not
    # claimed, so a binary vendor pattern reaches identify_format's refusal —
    # which names the formats this build reads — instead of reaching
    # ``read_text`` and dying as a bare UnicodeDecodeError.  "Does this format
    # claim the file" already lives in ``matches``; a separate guard would be a
    # second place that knows about binary files.
    matches=lambda p: not looks_binary(head(p)),
    read=read_xy,
)

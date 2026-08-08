"""Two/three-column ASCII — the format everything can be exported to.

No spec: the shape *is* the format.  Rows of ``2θ y [σ]``, comment lines
starting ``#``/``!``/``'``/``/``, whitespace or comma separated.  Because there
is nothing to recognise, this reader is the last entry in the dispatch order and
claims whatever is left — see :mod:`pxrdref.io.formats` for why "whatever is
left" is not the same as "everything".
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from ...schemas.pattern import PatternData
from .base import PatternFormat


def read_xy(path: str | Path) -> PatternData:
    p = Path(path)
    rows = []
    for line in p.read_text(encoding="utf-8").splitlines():
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
    sigma = arr[:, 2].tolist() if n_cols >= 3 and np.any(arr[:, 2] > 0) else None
    return PatternData(two_theta=arr[:, 0].tolist(), intensity=arr[:, 1].tolist(),
                       sigma=sigma, metadata={"source_file": p.name})


XY = PatternFormat(
    name="xy",
    title="Two/three-column ASCII (.xy / .xye)",
    extensions=(".xy", ".xye", ".dat", ".prn", ".txt"),
    sniff="anything else that parses as numeric rows",
    sigma="the third column when present and positive, else the Poisson fallback",
    matches=lambda p: True,
    read=read_xy,
)

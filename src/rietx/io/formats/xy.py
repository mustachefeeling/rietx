"""Two/three-column ASCII — the format everything can be exported to.

No spec: the shape *is* the format.  Rows of ``2θ y [σ]``, comment lines
starting ``#``/``!``/``'``/``/``, whitespace or comma separated.  Because there
is nothing to recognise, this reader is the last entry in the dispatch order and
claims whatever is left — which is **not** the same as everything: a file whose
first 4 kB holds a NUL is binary and is not claimed, so it reaches
``identify_format``'s refusal by name rather than this reader's decoder.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import numpy as np

from ...schemas.common import Diagnostic
from ...schemas.pattern import PatternData
from .base import PatternFormat, ascending, head, looks_binary, pattern_data


def read_xy(path: str | Path, *,
            diagnostics: list[Diagnostic] | None = None) -> PatternData:
    """Rows of ``2θ y [σ]``, read by position.

    **A row is data only if it has the file's usual column count** (issue
    #266).  A header line that starts with a digit parses on its first three
    tokens: PDFgetX2's detector table put a point at (0, 1) on every file one
    reporter had.  So each row keeps its token count, the most common count
    is the file's, and a row with any other is dropped and reported as
    ``PATTERN_ROWS_DROPPED``.  A tie goes to the count of the last row,
    because a header sits above its data.  A header row with the data's own
    count is out of this check's reach; the axis check in ``read_pattern``
    still sees one landing at or below 0°.
    """
    p = Path(path)
    rows: list[tuple[int, list[str], list[float]]] = []
    # the mark decides the codec, so a UTF-16 export from Windows vendor
    # software reads instead of dying on "no numeric data found"
    text = p.read_text(encoding=head(p).encoding, errors="replace")
    for n, line in enumerate(text.splitlines(), 1):
        s = line.strip()
        if not s or s.startswith(("#", "!", "'", "/")):
            continue
        parts = s.replace(",", " ").split()
        try:
            vals = [float(v) for v in parts[:3]]
        except ValueError:
            continue
        if len(vals) >= 2:
            rows.append((n, parts, vals))
    if not rows:
        raise ValueError(f"no numeric data found in {p}")
    counts = Counter(len(parts) for _, parts, _ in rows)
    arity = max(counts, key=lambda k: (counts[k], k == len(rows[-1][1])))
    dropped = [(n, parts) for n, parts, _ in rows if len(parts) != arity]
    if dropped and diagnostics is not None:
        shown = "; ".join(f"line {n}: {' '.join(parts)!r}"
                          for n, parts in dropped[:3])
        more = f", and {len(dropped) - 3} more" if len(dropped) > 3 else ""
        diagnostics.append(Diagnostic(
            level="warning", code="PATTERN_ROWS_DROPPED",
            message=(
                f"{p.name}: {len(dropped)} numeric row(s) have a column count "
                f"other than the file's {arity}, and were not read as data "
                f"({shown}{more})."),
            where=[f"line {n}" for n, _ in dropped],
            suggestion=(
                "A header table or a limits row reads this way. If a dropped "
                "row is a measured point, the file mixes column counts: "
                "re-export it with one count on every row."),
            value=float(len(dropped)),
        ))
    # one column count, so every kept row parsed the same number of values
    arr = np.array([vals for _, parts, vals in rows if len(parts) == arity],
                   dtype=np.float64)
    n_cols = arr.shape[1]
    sigma = arr[:, 2] if n_cols >= 3 and np.any(arr[:, 2] > 0) else None
    tt, y, sig = ascending(arr[:, 0], arr[:, 1], sigma, path=p, fmt=XY,
                           diagnostics=diagnostics)
    return pattern_data(p, tt, y, sig, source_file=p.name, format="xy")


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

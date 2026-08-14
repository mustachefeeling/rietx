"""``.dif`` — a **peak list**, recognised in order to be refused.

Bruker DIFFRAC-AT writes ``.dif``, and so does the RRUFF project's calculated
powder output; both are tables of *reflections* — a position, an intensity and
an hkl triple, a few dozen rows — not a measured profile.

This package refines a model against a measured profile.  Handed a peak list,
the ASCII-column fallback reads it perfectly happily and the refinement then
runs against ~30 delta functions: every background coefficient, every profile
width and every scale is fitted to a picture of a diffractogram rather than to
one.  Rwp will even look plausible.  So the file is claimed **in order to be
declined**, by a reader whose whole job is to say what it is and what would be
needed instead.

Matched on **evidence, not suffix**.  A real profile that someone named
``.dif`` still falls through to the ASCII reader and opens, because the suffix
alone is a filename and the hkl columns are the format.
"""

from __future__ import annotations

import re
from pathlib import Path

from ...schemas.pattern import PatternData
from .base import PatternFormat, head

#: A reflection row: a position, an intensity, an optional third number, then
#: an **integer hkl triple**.  That triple is the evidence — a profile point
#: has no Miller indices, and no ASCII pattern export invents three small
#: integers per row.
_HKL_ROW = re.compile(
    r"^\s*[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?\s+"
    r"[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?\s+"
    r"(?:[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?\s+)?"
    r"-?\d+\s+-?\d+\s+-?\d+(?:\s|$)")

#: The other evidence: the column names, where the writer emitted them.
_HKL_HEADER = re.compile(
    r"\bh\b[\s,|]+\bk\b[\s,|]+\bl\b|d[\s-]?spacing.*\bintensity\b", re.I)

#: How many reflection rows before it is a peak list rather than a coincidence.
_MIN_ROWS = 3


def looks_dif(p: Path) -> bool:
    if p.suffix.lower() != ".dif":
        return False
    text = head(p).text
    if _HKL_HEADER.search(text):
        return True
    return sum(1 for line in text.splitlines() if _HKL_ROW.match(line)) >= _MIN_ROWS


def read_dif(path: str | Path, *, diagnostics=None) -> PatternData:
    """Always raises — the refusal *is* the behaviour (see the module docstring).

    One implementation rather than a special case in ``read_pattern``: every
    path that opens a pattern goes through ``fmt.read``, so putting it here
    means the CLI, the agent surface and the GUI's upload route all get the
    same sentence, and ``identify_format`` can still answer truthfully what the
    file is.
    """
    p = Path(path)
    raise ValueError(
        f"{p.name} is a peak list (a table of reflections with hkl indices), "
        "not a measured profile, and this package refines against a profile. "
        "Reading it would fit every background coefficient, width and scale to "
        "about thirty delta functions and report a plausible Rwp for it. "
        "Export the raw scan from the instrument software instead — or, if you "
        "want the cell from these positions, index the peak list with "
        "rietx.index_pattern, which takes positions and is the right tool "
        "for it")


DIF = PatternFormat(
    name="dif_peaklist",
    title="Peak list (.dif — DIFFRAC-AT / RRUFF)",
    extensions=(".dif",),
    sniff=("the .dif suffix together with hkl columns — evidence, not the name, "
           "so a real profile misnamed .dif still opens as ASCII columns"),
    sigma="none — the file is refused before any σ question arises",
    refuses=("a table of reflections rather than a measured profile; refining "
             "against it would fit the whole model to about thirty delta "
             "functions and report a plausible Rwp"),
    matches=looks_dif,
    read=read_dif,
)

"""``.pks`` / ``.udi`` — peak lists, declined on their name and saying so.

Stoe writes ``.pks`` and PANalytical writes ``.udi``; both are tables of
*reflections* rather than measured profiles, which is the same objection
``dif.py`` makes and for the same reason: refining against a few dozen delta
functions fits every background coefficient, width and scale to a picture of a
diffractogram and reports a plausible Rwp for it.

**What is different here is the evidence, and it is worth being explicit
about.**  ``.dif`` is matched on *content* — an hkl triple per row — because
real ``.dif`` files were available to write that test against.  No ``.pks`` or
``.udi`` sample could be obtained from anywhere, so the positive test cannot be
written and this entry matches on the **suffix**.  That is a weaker claim and
the refusal says so rather than implying a content test it did not do.

**The escape is kept, because a suffix is a filename.**  ``dif.py``'s docstring
is explicit that "a real profile that someone named ``.dif`` still falls
through to the ASCII reader and opens", and dropping that here would make a
genuine two-column scan a lab happened to name ``.pks`` unopenable.  So the
gate is negative: refuse on the suffix **unless** the file reads as a plain
two-column profile, in which case nothing is claimed and it reaches ``xy``.
"Plain" is the whole of the test — every non-comment line in the bounded head
being a row of two or three numbers — and a peak list fails it on its header
alone.

Revisit the day a real ``.pks`` or ``.udi`` turns up: with a sample the match
can become content-based like ``.dif``'s, and this module's whole reason for
being different disappears.
"""

from __future__ import annotations

import re
from pathlib import Path

from ...schemas.pattern import PatternData
from .base import PatternFormat, head, looks_binary

#: The suffixes claimed.  ``.pks`` is Stoe's and ``.udi`` PANalytical's; the
#: refusal is one decision, so they are one entry rather than two modules.
_SUFFIXES = (".pks", ".udi")

#: A row of two or three plain numbers — what a two-column profile is made of.
_NUMERIC_ROW = re.compile(
    r"^\s*[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?"
    r"(?:[\s,]+[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?){1,2}\s*$")

#: How many such rows before the head is a profile rather than a coincidence.
#: Low on purpose: the gate's job is to let a real profile *out*, and a peak
#: list is excluded by its header long before this number matters.
_MIN_ROWS = 8


def _reads_as_plain_columns(p: Path) -> bool:
    """Whether every non-comment line in the bounded head is a numeric row."""
    h = head(p)
    if looks_binary(h):
        return False
    lines = [s for s in (line.strip() for line in h.text.splitlines()) if s]
    # the last line of a bounded read is usually cut mid-number, so it is not
    # evidence either way
    rows = lines[:-1] if len(lines) > 1 else lines
    if len(rows) < _MIN_ROWS:
        return False
    return all(_NUMERIC_ROW.match(s) for s in rows)


def looks_peaklist(p: Path) -> bool:
    if p.suffix.lower() not in _SUFFIXES:
        return False
    return not _reads_as_plain_columns(p)


def read_peaklist(path: str | Path, *, diagnostics=None) -> PatternData:
    """Always raises — the refusal *is* the behaviour (see the module docstring)."""
    p = Path(path)
    vendor = "Stoe" if p.suffix.lower() == ".pks" else "PANalytical"
    raise ValueError(
        f"{p.name} has a {p.suffix.lower()} suffix, which is a {vendor} **peak "
        "list** — a table of reflection positions and heights, not a measured "
        "profile, and this package refines against a profile. Refining against "
        "a few dozen delta functions fits every background coefficient, width "
        "and scale to a picture of a diffractogram and reports a plausible Rwp "
        "for it. This file was declined on its name: no such file was "
        "obtainable to write a content test against, so unlike .dif the check "
        "is the suffix and not the columns. If it really is a profile, it will "
        "open under any other name once it is plain two-column text — and if "
        "you want the cell from these positions, rietx.index_pattern takes "
        "positions and is the right tool for it")


PEAK_LIST = PatternFormat(
    name="peak_list",
    title="Peak list (.pks — Stoe, .udi — PANalytical)",
    extensions=_SUFFIXES,
    sniff=("the suffix alone, unless the file reads as a plain two-column "
           "profile — no .pks or .udi sample was obtainable to write a content "
           "test against, so unlike .dif this claims nothing about the "
           "contents, and a real profile misnamed .pks still opens"),
    sigma="none — the file is refused before any σ question arises",
    refuses=("a table of reflections rather than a measured profile. Matched on "
             "the suffix, not on evidence, because no sample of either format "
             "could be obtained"),
    matches=looks_peaklist,
    read=read_peaklist,
)

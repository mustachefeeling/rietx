"""PANalytical ``.udf`` — the ASCII scan a benchtop still writes today.

Not a legacy format.  A PANalytical Aeris, on sale now, writes it; the newest
of the 56 real files this reader was measured against is dated 12 June 2025.

Spec: the key vocabulary, the ``RawScan`` marker and the block shape were read
off those 56 files (two labs, two instrument vintages), corroborated by PyXRD's
``udf_parser.py`` (BSD-2) and psidata's ``xrd_panalytical.py`` (Apache-2.0).
``ATTRIBUTION.md`` § Format specifications records which source each fact came
from; ``tests/data/README.md`` § Philips carries the 19-key table.

The shape::

    Key,Value,/          one per line, 19 of them in every real file
    RawScan              a bare marker line
    3819,    3775, …     comma-separated integers, eight to a line
    …,      425,/        terminated by ``/``

Four things about it are worth knowing before touching the parser.

**A value may contain commas, so a line is split on the *first* one only.**
``DivergenceSlit,Fixed, 1/2,/`` is two fields, and ``Title1`` runs to **ten** in
the real corpus.  Splitting on every comma is the obvious parse and it is wrong.

**An empty value is not an absent key.**  ``Title2,,/`` occurs in nearly every
file; the key is present and says the field is blank.  ``ReceivingSlit`` goes
further and writes the sentinel ``UNDEFINED``.

**The abscissa is reconstructed, and the file states the count twice.**  No 2θ
is stored per point: the axis is ``DataAngleRange`` plus ``ScanStepSize``.  That
makes ``round((end - start) / step) + 1 == len(values)`` a real self-consistency
gate rather than a guess, and it holds on all 56 real files with no exceptions —
so a disagreement is a contradiction and is **refused**, not repaired.  (The
residue ``(end-start)/step - round(...)`` reaches 2.5e-4 of a step in the real
corpus, so the stated end angle is not an exact multiple and rounding is the
only correct reconstruction.)

**``ScanStepTime`` is not seconds per step and nothing is derived from it.**
The Aeris pairs ``ScanStepTime, 18.87`` with a scan its own file name calls
eight minutes over 5246 points; 5246 × 18.87 s is 27 hours.  These are
PIXcel-class position-sensitive detectors, where the effective counting time per
point is not the drive's dwell.  The value is not recorded as ``count_time_s``,
because that key means seconds per step and this number is not that.

**The format declares no scanned axis**, so unlike ``.uxd``, ``.ras``, ``.chi``,
``.xrdml`` and ``.raw`` there is nothing for :func:`base.check_axis` to
classify and no ``PATTERN_X_AXIS_ASSUMED`` is emitted.  That is a deliberate
difference from those five rather than an omission: ``ScanType`` is a timing
mode (``CONTINUOUS``), not an axis, and a warning that fires on 100 % of a
format's files says nothing.  The evidence that the assumption is safe is the
corpus — all 56 real files are powder scans over classic 2θ ranges (3–60,
10–80, 5–90° at 0.011–0.026° steps), against the ``.uxd`` corpus where four of
five were pole figures or rocking curves.  The ``sniff`` string says the axis is
assumed, so the claim is visible where a UI shows it.
"""

from __future__ import annotations

import math
import re
from pathlib import Path

import numpy as np

from ...schemas.common import Diagnostic
from ...schemas.pattern import PatternData
from .base import (
    PatternFormat,
    ascending,
    head,
    looks_binary,
    pattern_data,
    sigma_by_arithmetic,
)

#: A ``Key,Value,/`` header line.  The key is the only part with a grammar; the
#: value is whatever follows the first comma, commas included.
_HEADER_LINE = re.compile(r"^([A-Za-z][A-Za-z0-9_]*),(.*),/$")

#: The two keys a file must carry, because without both there is no abscissa.
#: Everything else is optional: the vendorable PyXRD fixture carries 5 of the
#: 19 keys the real files all carry, and it is a legal ``.udf``.
_REQUIRED = ("DataAngleRange", "ScanStepSize")


def _header(lines: list[str]) -> tuple[dict[str, str], str, int]:
    """``{key: value}``, the data marker, and the line the block starts on."""
    keys: dict[str, str] = {}
    for i, line in enumerate(lines):
        s = line.strip()
        if not s:
            continue
        hit = _HEADER_LINE.match(s)
        if hit is None:
            return keys, s, i + 1
        # first occurrence wins; no real file repeats a key, and choosing the
        # later one would be a silent repair of a file that contradicts itself
        keys.setdefault(hit.group(1), hit.group(2).strip())
    return keys, "", len(lines)


def _values(lines: list[str], *, path: Path) -> np.ndarray:
    """The numbers of the ``RawScan`` block, up to its ``/`` terminator.

    The terminator is ``/``, and whether a comma precedes it is *not* fixed:
    every real file ends ``425,/`` and the vendorable PyXRD fixture ends ``0/``.
    Cutting at the ``/`` and then splitting handles both without a special case.
    """
    body = "\n".join(lines)
    end = body.find("/")
    if end < 0:
        raise ValueError(f"{path.name}: the data block is not terminated by '/'. "
                         "A .udf ends its RawScan block with one, so the file is "
                         "truncated or is not a .udf")
    tokens = [t for t in body[:end].replace("\n", ",").split(",") if t.strip()]
    try:
        return np.array([float(t) for t in tokens], dtype=np.float64)
    except ValueError:
        bad = next(t for t in tokens if not _is_number(t))
        raise ValueError(f"{path.name}: the data block holds {bad.strip()!r}, "
                         "which is not a number") from None


def _is_number(token: str) -> bool:
    try:
        float(token)
    except ValueError:
        return False
    return True


def _floats(value: str, *, key: str, path: Path) -> list[float]:
    try:
        return [float(f) for f in value.split(",")]
    except ValueError:
        raise ValueError(f"{path.name}: {key} is {value!r}, which is not a "
                         "number or a list of them") from None


def read_udf(path: str | Path, *,
             diagnostics: list[Diagnostic] | None = None) -> PatternData:
    p = Path(path)
    lines = p.read_text(encoding=head(p).encoding, errors="replace").splitlines()
    keys, marker, start = _header(lines)

    missing = [k for k in _REQUIRED if k not in keys]
    if missing:
        raise ValueError(f"{p.name}: no {' or '.join(missing)} line. A .udf states "
                         "its range and step as header keys, because it stores no "
                         "2θ per point — without them there is no abscissa")
    if not marker:
        raise ValueError(f"{p.name}: the header is not followed by a data block. "
                         "A .udf opens its intensities with a marker line "
                         "(RawScan in every file seen)")

    angles = _floats(keys["DataAngleRange"], key="DataAngleRange", path=p)
    if len(angles) != 2:
        raise ValueError(f"{p.name}: DataAngleRange is "
                         f"{keys['DataAngleRange']!r}, which is not a start and "
                         "an end")
    lo, hi = angles
    step = _floats(keys["ScanStepSize"], key="ScanStepSize", path=p)[0]
    # a **non-finite** span is as much "not a scan" as a zero step, and has to
    # be caught in the same breath: ``round()`` raises OverflowError on an
    # infinity and a bare ValueError on a NaN, and neither names the file, which
    # is the one thing a reader's refusal must do (io/CLAUDE.md § Refusals).
    # ``nan`` compares False against everything, so finiteness is asked first
    span = float("nan") if step == 0.0 else (hi - lo) / step
    if not math.isfinite(span) or span <= 0.0:
        raise ValueError(f"{p.name}: DataAngleRange {lo:g}→{hi:g}° and "
                         f"ScanStepSize {step:g}° do not describe a scan")

    y = _values(lines[start:], path=p)
    expected = round(span) + 1
    if len(y) != expected:
        raise ValueError(
            f"{p.name}: the header says {lo:g}→{hi:g}° in steps of {step:g}°, "
            f"which is {expected} points, but the data block holds {len(y)}. "
            "The file states its length twice and the two disagree, so the 2θ of "
            "every point is in doubt — reconstructing an axis from one of them "
            "would be a guess, not a repair")

    two_theta = lo + step * np.arange(len(y), dtype=np.float64)
    # the declared unit is *nothing* — .udf states none anywhere — so arithmetic
    # is all there is, and it is decisive here: every intensity in all 56 real
    # files is a whole number, which is counts, whose σ is the Poisson fallback
    sigma = sigma_by_arithmetic(y, None, "", path=p, diagnostics=diagnostics)
    tt, y, sig = ascending(two_theta, y, sigma, path=p, fmt=UDF,
                           diagnostics=diagnostics)
    return pattern_data(
        p, tt, y, sig, source_file=p.name, format="udf",
        title=keys.get("Title1") or None, sample=keys.get("SampleIdent") or None,
        anode=keys.get("Anode") or None,
        wavelength=keys.get("LabdaAlpha1") or None,
        wavelength_alpha2=keys.get("LabdaAlpha2") or None)


def looks_udf(p: Path) -> bool:
    """Both abscissa keys present as ``Key,Value,/`` lines, in the bounded head.

    Keyed on the two keys the *parser* requires rather than on the marker or on
    the 19-key vocabulary: the vendorable fixture carries five keys and is a
    legal file, so a vocabulary test would reject the only fixture that can
    ship.  A real header is under 700 bytes, so both keys are always inside
    ``head()``'s 4 kB.
    """
    h = head(p)
    if looks_binary(h):
        return False
    keys = {hit.group(1) for hit in
            (_HEADER_LINE.match(line.strip()) for line in h.text.splitlines())
            if hit is not None}
    return all(k in keys for k in _REQUIRED)


UDF = PatternFormat(
    name="udf",
    title="PANalytical scan (.udf)",
    extensions=(".udf",),
    sniff=("Key,Value,/ header lines carrying both DataAngleRange and "
           "ScanStepSize, followed by a marker line and a comma-separated block "
           "of intensities. The format declares no scanned axis, so 2θ is "
           "assumed; its 2θ is reconstructed from the range and the step, and a "
           "point count disagreeing with them is refused"),
    sigma=("the Poisson fallback: the format declares no intensity unit, and "
           "every value in every real file measured is a whole number, which is "
           "counts. Values that are not whole numbers say so and withhold σ"),
    matches=looks_udf,
    read=read_udf,
)

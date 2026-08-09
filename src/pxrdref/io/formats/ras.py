"""Rigaku ``.ras`` — the text export SmartLab and MiniFlex write.

Spec: the format is self-describing ASCII and its structure was read off real
files plus the format notes in ``garrekstemo/RigakuFiles.jl`` (MIT) and
``nims-mdpf/M-DaC_XRD`` (MIT).  Section markers and header keys are interface
facts — there is exactly one spelling of ``*RAS_INT_START`` — so they are
written down here and the parser below is this package's own::

    *RAS_DATA_START
    *RAS_HEADER_START                 one per scan
    *KEY "VALUE"                      … the header, all values quoted
    *RAS_HEADER_END
    *RAS_INT_START
    2theta intensity [attenuator]     the points, two or three columns
    *RAS_INT_END
    *RAS_DATA_END                     after the last scan

A file holds **several scans** — a low-angle and a high-angle pass, a survey
and a slow rescan — each with its own complete header.  They are selected with
``scan=``, never concatenated: two passes generally differ in step size and
counting time, and merging them puts two weighting regimes in one residual.

Three of this format's facts cost more than parsing it, and each is settled by
measuring the file rather than by quoting a convention.

**The x axis is not always 2θ.**  ``*MEAS_SCAN_AXIS_X`` names the goniometer
axis, and an ω rocking curve — a real, common export — parses perfectly as a
pattern and refines to a confidently wrong cell.  Same three-way policy as the
``.chi`` axis label one module over: recognisably 2θ reads, recognisably
something else is refused by name, anything unrecognised reads with a
diagnostic saying it was assumed.

**The declared intensity unit is a claim, not a measurement.**  Both
``*MEAS_SCAN_UNIT_Y "counts"`` and ``"cps"`` occur, and the header can simply
be wrong: of the real files checked while writing this, ``XRD_RIGAKU.ras``
declares counts and holds integers (true), while ``rigaku-xrd-analysis``'s
``example.ras`` declares counts and holds values like 84.3047 that no scale
makes integral (false).  So the header is recorded as metadata and never
decides σ.  What decides is arithmetic: counts are integers, so all-integer
intensities *are* counts; and where the header gives a counting time, all-
integer ``y·t`` says the stored quantity is that count divided by the time.
Where neither test is decisive the σ is not supplied and
``PATTERN_INTENSITY_SCALED`` says the Poisson fallback is being applied to a
quantity whose scale could not be verified — wrong by √t if it is a rate.

**The third column is an attenuator factor and this reader does not apply it.**
No source states whether column 2 is already corrected for it, and the
structural test that would settle it — whether the raw series or the product is
the continuous one — needs a file where the column varies.  Every obtainable
file has it constant (five checked: 1.0 in four, 0.0 in one synthetic).  So the
reader matches the convention both other codes use, reads column 2, and says so
whenever the column is not identically 1 (``RAS_ATTENUATOR_PRESENT``) —
including that σ is affected, since √counts·attn ≠ √y.  Guessing here corrupts
exactly the strong peaks Rietveld weights most.
"""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np

from ...schemas.common import Diagnostic
from ...schemas.pattern import PatternData
from .base import (
    PatternFormat,
    ScanInfo,
    ascending,
    head,
    multiscan_default,
    pattern_data,
    sigma_from_cps,
)

#: The first line of every ``.ras``; the format's own required marker, and what
#: makes the sniff evidence rather than suffix.
_MAGIC = "*RAS_DATA_START"

_HEADER_LINE = re.compile(r'^\*(\S+)\s+"(.*)"\s*$')

#: Axis names whose x column is a diffraction angle 2θ.  ``TwoThetaTheta`` is
#: the coupled θ–2θ scan, ``TwoThetaOmega`` the same with an offset; both step
#: the detector through 2θ, which is all this package needs.
_TWO_THETA_AXES = frozenset({"twotheta", "twothetatheta", "twothetaomega"})

#: Axes that are recognisably **not** 2θ, with what each one measures — so the
#: refusal can say what the file holds rather than only what it lacks.
_OTHER_AXES: dict[str, str] = {
    "omega": "a rocking curve (ω), which measures crystal misorientation at one "
             "fixed 2θ",
    "theta": "a θ scan with the detector fixed, not a coupled θ–2θ pattern",
    "chi": "a χ (tilt) scan, one point of a pole figure",
    "phi": "a φ (in-plane rotation) scan, one point of a pole figure",
    "z": "a specimen-height scan, used to set the sample surface",
    "alpha": "an incident-angle scan",
    "beta": "an exit-angle scan",
}

#: ``*MEAS_SCAN_SPEED_UNIT`` → seconds per unit of the speed's denominator.
#: Read rather than assumed: real files say ``deg/min``, so treating the speed
#: as deg/s would make every derived counting time 60× too short — and σ = √(y/t)
#: wrong by a factor of ~8.
_SPEED_UNIT_SECONDS: dict[str, float] = {
    "deg/min": 60.0, "degree/min": 60.0,
    "deg/sec": 1.0, "deg/s": 1.0, "degree/sec": 1.0,
}

#: How close to an integer a value must be to count as one.  Counts are written
#: as ``13.0000``, so the test is exact up to the decimal text; the tolerance is
#: for the ``y·t`` product, where the file's four stored decimals are multiplied.
_INTEGRAL_TOL = 1e-3


def _blocks(path: Path) -> list[tuple[dict[str, str], np.ndarray]]:
    """Every ``(header, points)`` pair in the file, in file order.

    Raises rather than returning what it managed to read: this format states its
    own structure, so an unterminated block means the bytes are incomplete — the
    interrupted-copy case — and half a scan is not a shorter scan.
    """
    p = Path(path)
    text = p.read_text(encoding=head(p).encoding, errors="replace")

    out: list[tuple[dict[str, str], np.ndarray]] = []
    header: dict[str, str] = {}
    rows: list[list[float]] | None = None
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        if line.startswith("*RAS_HEADER_START"):
            header = {}
        elif line.startswith("*RAS_INT_START"):
            rows = []
        elif line.startswith("*RAS_INT_END"):
            if rows is None:
                raise ValueError(f"{p.name}: line {number} closes a block of "
                                 "points that was never opened")
            # narrowest row wins, so a file that stops writing the attenuator
            # part-way through is two columns rather than a ragged array
            width = min((len(r) for r in rows), default=2)
            out.append((header, np.array([r[:width] for r in rows],
                                         dtype=np.float64)
                        if rows else np.empty((0, 2))))
            header, rows = {}, None
        elif rows is not None:
            parts = line.split()
            try:
                values = [float(v) for v in parts[:3]]
            except ValueError:
                raise ValueError(
                    f"{p.name}: line {number} is inside a block of points but is "
                    f"not a row of numbers: {line!r}") from None
            if len(values) < 2:
                raise ValueError(f"{p.name}: line {number} has one column; a "
                                 "point is 2θ and an intensity")
            rows.append(values[:3])
        elif (found := _HEADER_LINE.match(line)) is not None:
            header[found.group(1)] = found.group(2)

    if rows is not None:
        raise ValueError(f"{p.name}: the file ends inside a block of points — "
                         "*RAS_INT_START is never closed by *RAS_INT_END, so "
                         "the file is incomplete")
    if not out:
        raise ValueError(f"{p.name}: {_MAGIC} is present but the file holds no "
                         "block of points (*RAS_INT_START … *RAS_INT_END)")
    return out


def _float(header: dict[str, str], key: str) -> float | None:
    try:
        return float(header[key])
    except (KeyError, ValueError):
        return None


def _count_time_s(header: dict[str, str]) -> float | None:
    """Seconds per step, or ``None`` when the header does not settle it.

    ``None`` rather than a default, because the unit is what makes this number
    mean anything: a speed whose unit the file did not state could be per minute
    or per second, and a σ derived from the wrong one is wrong by √60.
    """
    step, speed = _float(header, "MEAS_SCAN_STEP"), _float(header, "MEAS_SCAN_SPEED")
    seconds = _SPEED_UNIT_SECONDS.get(header.get("MEAS_SCAN_SPEED_UNIT", "").lower())
    if step is None or speed is None or seconds is None or step <= 0 or speed <= 0:
        return None
    return step / speed * seconds


def _integral(values: np.ndarray) -> bool:
    return bool(values.size) and bool(
        np.all(np.abs(values - np.round(values)) < _INTEGRAL_TOL))


def _sigma(y: np.ndarray, header: dict[str, str], *, path: Path,
           diagnostics: list[Diagnostic] | None) -> tuple[np.ndarray | None, float | None]:
    """σ, and the counting time it was derived from — by measurement, not by label.

    Three outcomes, in the order the evidence decides them.  All-integer
    intensities are counts, whose σ is the Poisson fallback the package already
    applies, so ``None`` here is the *correct* answer and not a missing one.  An
    all-integer ``y·t`` says the stored quantity is a rate, and its σ is derived.
    Anything else is undecided, and says so.
    """
    t = _count_time_s(header)
    declared = header.get("MEAS_SCAN_UNIT_Y", "").strip() or "nothing"
    if _integral(y):
        return None, t
    if t is not None and _integral(y * t):
        return sigma_from_cps(y, t), t
    if diagnostics is not None:
        derived = ("no counting time either: the header gives no scan speed with "
                   "a unit" if t is None else
                   f"a counting time of {t:.6g} s per step does not make them "
                   "whole numbers either")
        diagnostics.append(Diagnostic(
            level="warning", code="PATTERN_INTENSITY_SCALED",
            message=(f"{path.name} declares its intensity unit as {declared} but "
                     f"the stored values are not whole numbers, and {derived}. "
                     "The scale could not be verified, so no σ was supplied and "
                     "the Poisson fallback √max(y,1) will be applied to a "
                     "quantity that may already be divided by a counting time — "
                     "in which case the weights are wrong by √t"),
            where=["sigma"],
            suggestion=("export the scan in counts, or supply the esds yourself; "
                        "the fit will run either way but its esds and χ² are "
                        "only as good as the weights")))
    return None, t


def _attenuator(rows: np.ndarray, *, path: Path,
                diagnostics: list[Diagnostic] | None) -> None:
    """Say so when a third column is present and not identically 1.

    Never applied — see the module docstring.  The message names the 2θ range
    because that is what tells a user whether the affected points are the peaks
    they care about.
    """
    if rows.shape[1] < 3 or diagnostics is None:
        return
    off = rows[:, 2] != 1.0
    if not off.any():
        return
    affected = rows[off, 0]
    diagnostics.append(Diagnostic(
        level="warning", code="RAS_ATTENUATOR_PRESENT",
        message=(f"{path.name} carries an attenuator factor that is not 1 over "
                 f"{int(off.sum())} point(s), 2θ = {affected.min():.4g}–"
                 f"{affected.max():.4g}°, taking {len(np.unique(rows[off, 2]))} "
                 "distinct value(s). It was **not** applied: no specification "
                 "states whether the intensity column is already corrected for "
                 "it, and applying it twice or not at all are both wrong. σ is "
                 "affected too — √counts·attn is not √y"),
        where=["intensity", "sigma"],
        suggestion=("check the export against the instrument software before "
                    "trusting the relative intensities of the points named")))


def _axis(header: dict[str, str], *, path: Path,
          diagnostics: list[Diagnostic] | None) -> str | None:
    """Refuse an axis that is recognisably not 2θ; report one that is unknown."""
    axis = header.get("MEAS_SCAN_AXIS_X", "").strip()
    key = axis.lower().replace(" ", "").replace("-", "").replace("_", "")
    if key in _TWO_THETA_AXES:
        return axis or None
    if (what := _OTHER_AXES.get(key)) is not None:
        raise ValueError(
            f"{path.name}: the scanned axis is {axis!r}, which is {what} — not a "
            "powder pattern in 2θ. Its points parse perfectly and would refine "
            "to a cell that is confidently wrong, so it is refused rather than "
            "read. Export the θ–2θ scan instead")
    if diagnostics is not None:
        named = f"names its scanned axis {axis!r}" if axis else "names no scanned axis"
        diagnostics.append(Diagnostic(
            level="warning", code="RAS_X_AXIS_ASSUMED",
            message=(f"{path.name} {named}, which is not one this reader "
                     "recognises; the x column was read as 2θ in degrees"),
            where=["two_theta"],
            suggestion=("check *MEAS_SCAN_AXIS_X in the file — an ω or χ scan "
                        "read as 2θ gives a cell that is wrong by a geometry, "
                        "not by a tolerance")))
    return axis or None


def _label(header: dict[str, str], index: int, points: np.ndarray) -> str:
    """What the file calls this scan, else its own range — never "Scan N"."""
    for key in ("FILE_COMMENT", "FILE_SAMPLE", "FILE_MEMO"):
        if (value := header.get(key, "").strip()):
            return value
    if points.size:
        return (f"{header.get('MEAS_SCAN_AXIS_X', '2θ')} "
                f"{points[0, 0]:.4g}–{points[-1, 0]:.4g}°")
    return f"scan {index}"


def read_ras(path: str | Path, *, scan: int | None = None,
             diagnostics: list[Diagnostic] | None = None) -> PatternData:
    p = Path(path)
    blocks = _blocks(p)
    multiscan_default(len(blocks), scan, path=p, diagnostics=diagnostics)

    index = 0 if scan is None else scan
    if not 0 <= index < len(blocks):
        raise ValueError(f"{p.name} holds {len(blocks)} scan(s), numbered 0 to "
                         f"{len(blocks) - 1}; scan={index} is not one of them")
    header, rows = blocks[index]
    if rows.size == 0:
        raise ValueError(f"{p.name}: scan {index} declares a block of points that "
                         "is empty")

    axis = _axis(header, path=p, diagnostics=diagnostics)
    _attenuator(rows, path=p, diagnostics=diagnostics)
    sigma, count_time = _sigma(rows[:, 1], header, path=p, diagnostics=diagnostics)
    tt, y, sig = ascending(rows[:, 0], rows[:, 1], sigma, path=p, fmt=RAS,
                           diagnostics=diagnostics)
    return pattern_data(
        p, tt, y, sig,
        source_file=p.name, format="ras", scan=index, scan_count=len(blocks),
        scan_axis=axis, sample=header.get("FILE_SAMPLE") or None,
        title=header.get("FILE_COMMENT") or None,
        anode=header.get("HW_XG_TARGET_NAME") or None,
        wavelength=_float(header, "HW_XG_WAVE_LENGTH_ALPHA1"),
        wavelength_alpha2=_float(header, "HW_XG_WAVE_LENGTH_ALPHA2"),
        intensity_unit=header.get("MEAS_SCAN_UNIT_Y") or None,
        count_time_s=count_time)


def list_ras_scans(path: str | Path) -> list[ScanInfo]:
    p = Path(path)
    return [ScanInfo(index=i, label=_label(h, i, d), n_points=len(d),
                     two_theta_range=((float(d[:, 0].min()), float(d[:, 0].max()))
                                      if d.size else (0.0, 0.0)))
            for i, (h, d) in enumerate(_blocks(p))]


def looks_ras(p: Path) -> bool:
    """The format's own required first line, inside the bounded head read."""
    return head(p).text.lstrip("﻿").lstrip().startswith(_MAGIC)


RAS = PatternFormat(
    name="ras",
    title="Rigaku SmartLab / MiniFlex scan (.ras)",
    extensions=(".ras",),
    sniff=f"the first line is {_MAGIC}, which the format requires",
    sigma=("derived as √(y·t)/t where the header's counting time shows the "
           "intensities are a rate; the Poisson fallback where they are whole "
           "counts; withheld, with PATTERN_INTENSITY_SCALED, where neither is "
           "established — the declared unit is a claim and is not trusted"),
    matches=looks_ras,
    read=read_ras,
    options=("scan",),
    scans=list_ras_scans,
)

"""PANalytical/Malvern ``.xrdml`` — the XML an Empyrean or X'Pert writes.

Spec: the XRDML schema itself (``http://www.xrdml.com/XRDMeasurement/1.x`` and
``/2.x``), read off three real files plus the element paths named in
``paruch-group/xrdtools`` (MIT) and FAIRmat's ``readers-xrd`` (Apache-2.0).
Element paths and attribute names are interface facts — there is exactly one
spelling of ``beamAttenuationFactors`` — so they are written down here and the
parser below is this package's own::

    xrdMeasurements                       the root, in a versioned namespace
      xrdMeasurement                      one per measurement, several allowed
        usedWavelength/kAlpha1 kAlpha2
        incidentBeamPath/radius           the goniometer radius, in mm
        incidentBeamPath/xRayTube/anodeMaterial
        scan  @scanAxis @mode @status     one per scan — a file holds several
          dataPoints
            positions @axis @unit         one per goniometer axis
              startPosition/endPosition   … or listPositions, or commonPosition
            commonCountingTime            … or countingTimes, one per point
            beamAttenuationFactors        optional, one per point
            counts | intensities @unit    the data

**The namespace is versioned, so nothing matches on it.**  The two real
generations here are ``/1.6`` and ``/2.1`` and both are current in the wild; a
reader keyed on either would refuse half the files a lab owns.  Every lookup in
this module is by *local* name.

**The beam attenuator is applied here, and that is the opposite of the ``.ras``
decision one module over.**  A PANalytical attenuator drops a foil in front of
the detector for the few points that would saturate it, and
``beamAttenuationFactors`` records the factor per point.  Whether the stored
series is already corrected is exactly the question ``.ras``'s third column
could not answer — but here a real file answers it.  In
``panalytical_attenuator.xrdml`` a single point of the GaAs 004 substrate
reflection carries a factor of 188, and its raw neighbourhood runs

    1341 → 14602 → **1877** → 13749 → 1667

which is a *dip* at what must be a peak maximum: the attenuation itself, not a
profile.  Multiplying by the factor restores a monotone peak (352876 at the
apex), so the stored ``counts`` are the attenuated ones and the correction is
the format's own arithmetic rather than a guess.  FAIRmat's reader computes the
same product independently.  So this reader applies it, derives σ through it
(√counts·a, which is *not* √y — the case GSAS-II gets wrong by weighting 1/y
regardless), and says it did (``XRDML_ATTENUATOR_APPLIED``).

**σ comes from one composition rather than three cases.**  Whatever the file
stores, the Poisson quantity is the raw detector count ``c`` and the stored
value is ``y = c·s`` for a scale ``s`` this reader can name: the attenuation
factor, times ``1/t`` when the declared unit is a rate.  ``s ≡ 1`` is raw counts
and the Poisson fallback is then exactly right, so no σ is supplied; anything
else gets σ = √max(y/s, 1)·s.  A unit of ``cps`` with no counting time cannot
form ``s`` at all, and that is ``PATTERN_INTENSITY_SCALED`` — the weights would
be wrong by √t and the caveat says so.

The unit is trusted, on the ``.uxd`` side of that argument rather than the
``.ras`` side: it is a schema-enumerated attribute *on the element carrying the
data*, not a free-text header field beside it.  Verified anyway — every
intensity in both real single-scan fixtures is integral.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import numpy as np

from ...schemas.common import Diagnostic
from ...schemas.pattern import PatternData
from .base import (
    PatternFormat,
    ScanInfo,
    ascending,
    check_axis,
    head,
    multiscan_default,
    pattern_data,
    sigma_from_scaled,
)

#: The root element's local name — the format's own required root, and what
#: makes the sniff evidence rather than suffix.
_ROOT = "xrdMeasurements"

#: The first element in a document, ignoring the XML declaration, a DOCTYPE and
#: processing instructions.  Comments are stripped before this runs, because a
#: comment may legally contain angle brackets.
_FIRST_ELEMENT = re.compile(r"<(?![?!])\s*([\w.\-]+)")
_COMMENT = re.compile(r"<!--.*?-->", re.S)

#: ``scan/@scanAxis`` values whose stepped axis is the diffraction angle 2θ.
#: ``Gonio`` is PANalytical's name for the coupled θ–2θ scan a powder pattern is
#: measured with; ``2Theta`` is a detector scan at fixed ω, which steps 2θ too.
_TWO_THETA_AXES = frozenset({"gonio", "2theta", "2thetaomega", "omega2theta"})

#: Axes that are recognisably **not** 2θ, with what each one measures.
_OTHER_AXES: dict[str, str] = {
    "omega": "a rocking curve (ω), which measures crystal misorientation at one "
             "fixed 2θ",
    "phi": "a φ (in-plane rotation) scan, one ring of a pole figure",
    "chi": "a χ (tilt) scan, one arc of a pole figure",
    "psi": "a ψ tilt, as measured for residual stress",
    "x": "a specimen translation in x, used to position the sample",
    "y": "a specimen translation in y, used to position the sample",
    "z": "a specimen height scan, used to set the sample surface",
    "reciprocalspace": "a reciprocal-space map, which is a stack of scans and "
                       "not one profile",
}

#: The two intensity units the schema enumerates, and the scale each implies
#: relative to raw counts.  ``None`` marks the one that needs the file's own
#: counting time and so cannot be a constant.
_COUNTS, _CPS = "counts", "cps"


def _local(tag: str) -> str:
    """An element's name without its namespace — every lookup here uses this."""
    return tag.rpartition("}")[2]


def _kids(element: ET.Element, name: str) -> list[ET.Element]:
    return [c for c in element if _local(c.tag) == name]


def _kid(element: ET.Element | None, *names: str) -> ET.Element | None:
    """Descend by local name, or ``None`` as soon as a step is missing."""
    for name in names:
        if element is None:
            return None
        element = next(iter(_kids(element, name)), None)
    return element


def _text(element: ET.Element | None) -> str | None:
    if element is None or element.text is None:
        return None
    return element.text.strip() or None


def _number(element: ET.Element | None) -> float | None:
    if (text := _text(element)) is None:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _numbers(element: ET.Element | None, *, path: Path, what: str) -> np.ndarray | None:
    """A whitespace-separated array of floats, or a refusal naming the file.

    ``np.array(text.split())`` rather than ``np.fromstring(text, sep=" ")``: the
    latter stops at the first token it cannot parse and returns the short array
    **without an error**, which turns a file truncated mid-number into a pattern
    quietly missing its tail.
    """
    if element is None or element.text is None:
        return None
    try:
        return np.array(element.text.split(), dtype=np.float64)
    except ValueError:
        raise ValueError(f"{path.name}: <{what}> holds something that is not a "
                         "list of numbers, so the file is not readable as "
                         "written — most often a copy that was interrupted "
                         "mid-element") from None


def _tree(path: Path) -> ET.Element:
    """The document root, with the XML parser's exception converted at this
    boundary — ``ET.ParseError`` subclasses ``SyntaxError``, so one escaping a
    reader is a traceback on an API caller and a 500 on the GUI's upload route.
    """
    try:
        return ET.parse(str(path)).getroot()
    except ET.ParseError as exc:
        raise ValueError(f"{path.name} is not readable as XML ({exc}); a "
                         ".xrdml that stops mid-element is usually a copy that "
                         "was interrupted") from None


def _scans(root: ET.Element, path: Path) -> list[tuple[ET.Element, ET.Element]]:
    """Every ``(measurement, scan)`` pair in document order.

    Paired rather than flattened because the wavelength, the tube and the
    goniometer radius live on the *measurement* and a file may hold several —
    the root element is ``xrdMeasurements``, plural, and taking the first
    measurement's tube for a later measurement's scan would be a quiet lie.
    """
    if _local(root.tag) != _ROOT:
        raise ValueError(f"{path.name}: the root element is <{_local(root.tag)}>, "
                         f"not <{_ROOT}>, so this is XML but not an XRDML "
                         "measurement")
    out = [(m, s) for m in _kids(root, "xrdMeasurement") for s in _kids(m, "scan")]
    if not out:
        raise ValueError(f"{path.name}: <{_ROOT}> holds no <scan> with data — "
                         "an XRDML carrying only a configuration or an aborted "
                         "measurement has no pattern in it")
    return out


def _intensity(points: ET.Element, *, path: Path) -> tuple[np.ndarray, str, bool]:
    """The stored series, its declared unit, and whether it is *raw* counts.

    ``<counts>`` is the detector's own number and ``<intensities>`` the reported
    one, which is why only the first is multiplied by the attenuation: the
    format has already done it to the second.
    """
    for name, raw in (("intensities", False), ("counts", True)):
        element = _kid(points, name)
        if element is not None:
            values = _numbers(element, path=path, what=name)
            if values is None or values.size == 0:
                raise ValueError(f"{path.name}: a <{name}> element is present but "
                                 "empty, so the scan holds no points")
            return values, (element.get("unit") or _COUNTS).strip().lower(), raw
    raise ValueError(f"{path.name}: a scan's <dataPoints> carries neither "
                     "<counts> nor <intensities>, so there is nothing to read "
                     "as a pattern")


def _positions(points: ET.Element, axis: str, n: int, *,
               path: Path) -> np.ndarray | float | None:
    """One axis's positions in whichever of the three forms the file used.

    A scalar comes back as a float rather than an ``n``-long constant array: it
    is what identifies a *fixed* axis, which is how a scan in a stack is told
    apart from its neighbours (see :func:`list_xrdml_scans`).
    """
    element = next((p for p in _kids(points, "positions")
                    if (p.get("axis") or "") == axis), None)
    if element is None:
        return None
    if (listed := _kid(element, "listPositions")) is not None:
        values = _numbers(listed, path=path, what=f"listPositions for {axis}")
        if values is None or values.size != n:
            raise ValueError(
                f"{path.name}: the {axis} axis lists "
                f"{0 if values is None else values.size} positions for {n} "
                "intensities. A position list and its data are one measurement "
                "and must be the same length")
        return values
    start, end = _number(_kid(element, "startPosition")), _number(
        _kid(element, "endPosition"))
    if start is not None and end is not None:
        return np.linspace(start, end, n)
    return _number(_kid(element, "commonPosition"))


def _count_time(points: ET.Element, n: int, *, path: Path) -> np.ndarray | float | None:
    """Seconds per step — one number, or one per point for a pre-set-counts scan."""
    if (common := _number(_kid(points, "commonCountingTime"))) is not None:
        return common
    values = _numbers(_kid(points, "countingTimes"), path=path,
                      what="countingTimes")
    if values is None:
        return None
    if values.size != n:
        raise ValueError(f"{path.name}: {values.size} counting times for {n} "
                         "intensities; a per-point counting time is one per point")
    return values


def _scale(unit: str, attenuation: np.ndarray | None,
           count_time: np.ndarray | float | None, *, path: Path,
           diagnostics: list[Diagnostic] | None) -> np.ndarray | float | None:
    """``s`` in ``y = counts·s``, or ``None`` when the file does not settle it.

    One composition rather than a case per element: the attenuation multiplies
    whatever the unit divided by, so the two compose, and ``s ≡ 1`` is the raw
    counts for which the Poisson fallback is exactly right.
    """
    scale: np.ndarray | float = 1.0 if attenuation is None else attenuation
    if unit == _CPS:
        if count_time is None or not np.all(np.asarray(count_time) > 0):
            if diagnostics is not None:
                diagnostics.append(Diagnostic(
                    level="warning", code="PATTERN_INTENSITY_SCALED",
                    message=(f"{path.name} declares its intensities as counts "
                             "per second but carries no usable counting time "
                             "(<commonCountingTime> or <countingTimes>) to undo "
                             "the division. No σ was supplied, so the Poisson "
                             "fallback √max(y,1) will be applied to a rate and "
                             "the weights are wrong by √t"),
                    where=["sigma"],
                    suggestion=("re-export with counts, or supply the esds; the "
                                "fit runs either way but its esds and χ² are "
                                "not quotable")))
            return None
        scale = scale / np.asarray(count_time, dtype=np.float64)
    elif unit != _COUNTS:
        if diagnostics is not None:
            diagnostics.append(Diagnostic(
                level="warning", code="PATTERN_INTENSITY_SCALED",
                message=(f"{path.name} declares its intensity unit as {unit!r}, "
                         f"which is neither {_COUNTS!r} nor {_CPS!r}. The scale "
                         "could not be established, so no σ was supplied and the "
                         "Poisson fallback √max(y,1) is being applied to a "
                         "quantity that may already be divided by something"),
                where=["sigma"],
                suggestion="re-export in counts, or supply the esds yourself"))
        return None
    return scale


def _attenuator(attenuation: np.ndarray, two_theta: np.ndarray, *, path: Path,
                diagnostics: list[Diagnostic] | None) -> None:
    """Say so when a non-unit attenuation was applied — it is a 100× correction."""
    off = attenuation != 1.0
    if not off.any() or diagnostics is None:
        return
    affected = two_theta[off] if two_theta.size == attenuation.size else two_theta
    diagnostics.append(Diagnostic(
        level="info", code="XRDML_ATTENUATOR_APPLIED",
        message=(f"{path.name} carries a beam attenuation factor over "
                 f"{int(off.sum())} point(s), 2θ = {affected.min():.4g}–"
                 f"{affected.max():.4g}°, up to {attenuation.max():.6g}×, and it "
                 "**was** applied: the stored counts are what the detector saw "
                 "behind the foil, so the reported intensity is counts × factor "
                 "and σ is √counts × factor, not √y. Unlike the Rigaku .ras "
                 "attenuator column, this one is settled — a real file shows the "
                 "raw series dipping at exactly the attenuated point of a "
                 "substrate reflection"),
        where=["intensity", "sigma"],
        suggestion=("nothing to do; the note exists because the correction is "
                    "large and invisible in the file's own numbers")))


def _axis(scan: ET.Element, *, path: Path,
          diagnostics: list[Diagnostic] | None) -> str | None:
    """``scan/@scanAxis`` classified; :func:`base.check_axis` decides."""
    axis = (scan.get("scanAxis") or "").strip()
    key = axis.lower().replace(" ", "").replace("-", "").replace("_", "")
    return check_axis(axis, path=path, field="scan/@scanAxis",
                      two_theta=key in _TWO_THETA_AXES,
                      other=_OTHER_AXES.get(key),
                      remedy="Export the coupled θ–2θ (Gonio) scan instead.",
                      diagnostics=diagnostics)


def _read_scan(measurement: ET.Element, scan: ET.Element, *, path: Path,
               diagnostics: list[Diagnostic] | None,
               ) -> tuple[np.ndarray, np.ndarray, np.ndarray | None, dict[str, Any]]:
    """One scan's 2θ, intensity, σ and the metadata that came with it."""
    points = _kid(scan, "dataPoints")
    if points is None:
        raise ValueError(f"{path.name}: a <scan> carries no <dataPoints>")

    axis = _axis(scan, path=path, diagnostics=diagnostics)
    y, unit, raw_counts = _intensity(points, path=path)
    n = y.size

    two_theta = _positions(points, "2Theta", n, path=path)
    if two_theta is None:
        raise ValueError(f"{path.name}: the scan gives no <positions axis="
                         '"2Theta">, so there is no diffraction angle to read '
                         "— the file may hold only the axes it moved")
    if not isinstance(two_theta, np.ndarray):
        raise ValueError(f"{path.name}: 2θ is a single fixed position "
                         f"({two_theta:.6g}°) across {n} points, so this scan "
                         "stepped some other axis at one detector angle. It is "
                         "not a powder pattern however its scanAxis is spelled")

    attenuation = _numbers(_kid(points, "beamAttenuationFactors"), path=path,
                           what="beamAttenuationFactors")
    if attenuation is not None:
        if attenuation.size != n:
            raise ValueError(f"{path.name}: {attenuation.size} attenuation "
                             f"factors for {n} intensities; the factor is per "
                             "point and must be one per point")
        if not np.all(attenuation > 0):
            raise ValueError(f"{path.name}: a beam attenuation factor is not "
                             "positive, so it cannot be the factor an intensity "
                             "was divided by")
        if raw_counts:
            y = y * attenuation
        _attenuator(attenuation, two_theta, path=path, diagnostics=diagnostics)

    count_time = _count_time(points, n, path=path)
    scale = _scale(unit, attenuation, count_time, path=path,
                   diagnostics=diagnostics)
    # ``s ≡ 1`` is raw counts, whose σ the Poisson fallback already gets right;
    # None means the scale could not be established and was reported as such
    sigma = (sigma_from_scaled(y, scale)
             if scale is not None and np.any(np.asarray(scale) != 1.0) else None)

    meta: dict[str, Any] = dict(
        scan_axis=axis,
        anode=_text(_kid(measurement, "incidentBeamPath", "xRayTube",
                         "anodeMaterial")),
        wavelength=_number(_kid(measurement, "usedWavelength", "kAlpha1")),
        wavelength_alpha2=_number(_kid(measurement, "usedWavelength", "kAlpha2")),
        intensity_unit=unit,
        count_time_s=(float(np.asarray(count_time).flat[0])
                      if count_time is not None
                      and np.all(np.asarray(count_time) ==
                                 np.asarray(count_time).flat[0]) else None),
        goniometer_radius_mm=_number(_kid(measurement, "incidentBeamPath",
                                          "radius")),
    )
    return two_theta, y, sigma, meta


def read_xrdml(path: str | Path, *, scan: int | None = None,
               diagnostics: list[Diagnostic] | None = None) -> PatternData:
    p = Path(path)
    root = _tree(p)
    pairs = _scans(root, p)
    multiscan_default(len(pairs), scan, path=p, diagnostics=diagnostics)

    index = 0 if scan is None else scan
    if not 0 <= index < len(pairs):
        raise ValueError(f"{p.name} holds {len(pairs)} scan(s), numbered 0 to "
                         f"{len(pairs) - 1}; scan={index} is not one of them")
    measurement, element = pairs[index]
    x, y, sigma, meta = _read_scan(measurement, element, path=p,
                                   diagnostics=diagnostics)
    # the sample sits on the *root*, beside the measurements rather than in one
    sample = _kid(root, "sample")
    tt, y, sig = ascending(x, y, sigma, path=p, fmt=XRDML, diagnostics=diagnostics)
    return pattern_data(p, tt, y, sig, source_file=p.name, format="xrdml",
                        scan=index, scan_count=len(pairs),
                        sample=_text(_kid(sample, "name")) or
                        _text(_kid(sample, "id")), **meta)


def list_xrdml_scans(path: str | Path) -> list[ScanInfo]:
    """What there is to choose between — labelled by what actually differs.

    A reciprocal-space map is 101 scans over the *same* 2θ range, so "2Theta
    67.45–69.95°" repeated 101 times tells a picker nothing.  What separates
    them is the axis they were each fixed at, which is knowable only across the
    whole list — so the fixed positions are collected first and only the ones
    that vary reach the labels.
    """
    p = Path(path)
    pairs = _scans(_tree(p), p)

    ranges: list[tuple[str, np.ndarray]] = []
    fixed: list[dict[str, float]] = []
    for _measurement, element in pairs:
        points = _kid(element, "dataPoints")
        if points is None:
            raise ValueError(f"{p.name}: a <scan> carries no <dataPoints>")
        y, _unit, _raw = _intensity(points, path=p)
        here: dict[str, float] = {}
        stepped: np.ndarray | None = None
        for positions in _kids(points, "positions"):
            axis = positions.get("axis") or "?"
            value = _positions(points, axis, y.size, path=p)
            if isinstance(value, np.ndarray):
                if axis == "2Theta":
                    stepped = value
            elif value is not None:
                here[axis] = value
        ranges.append(((element.get("scanAxis") or "2θ"),
                       stepped if stepped is not None else np.array([0.0])))
        fixed.append(here)

    varying = sorted({axis for axis in set().union(*fixed) if
                      len({f.get(axis) for f in fixed}) > 1}) if fixed else []
    out: list[ScanInfo] = []
    for i, (axis, x) in enumerate(ranges):
        at = "".join(f", {a} {fixed[i][a]:.4g}°" for a in varying if a in fixed[i])
        out.append(ScanInfo(index=i, label=f"{axis} {x.min():.4g}–{x.max():.4g}°{at}",
                            n_points=int(x.size),
                            two_theta_range=(float(x.min()), float(x.max()))))
    return out


def looks_xrdml(p: Path) -> bool:
    """The document's first element, from the bounded head read.

    Not the suffix and not the namespace: the namespace carries the schema
    *version* (1.6 and 2.1 are both current in the wild) and keying on either
    would refuse half the files a lab owns.
    """
    text = _COMMENT.sub("", head(p).text)
    found = _FIRST_ELEMENT.search(text)
    return found is not None and found.group(1).rpartition(":")[2] == _ROOT


XRDML = PatternFormat(
    name="xrdml",
    title="PANalytical/Malvern XRDML measurement (.xrdml)",
    extensions=(".xrdml",),
    sniff=f"the document's first element is <{_ROOT}>, in any schema version",
    sigma=("derived through the scale the file names — the beam attenuation "
           "factor, and the counting time when the unit is cps — as "
           "√max(y/s,1)·s; the Poisson fallback where the stored values are raw "
           "counts, which is exactly right; withheld, with "
           "PATTERN_INTENSITY_SCALED, where a rate carries no counting time"),
    matches=looks_xrdml,
    read=read_xrdml,
    options=("scan",),
    scans=list_xrdml_scans,
)

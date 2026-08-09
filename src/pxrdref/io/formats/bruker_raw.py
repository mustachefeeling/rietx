"""Bruker/Siemens ``.raw`` — the binary DIFFRAC formats, v1 to v4.

Spec: written down as a table of offsets *before* any parser was opened, from
two descriptions that agree — the real file measured byte by byte here, and
GSAS-II's ``imports/G2pwd_BrukerRAW.py`` (spec only; its licence carries a
grant-back clause, so nothing is ported).  ``ATTRIBUTION.md`` § Format
specifications records which fact came from which.  A third description exists
(FAIRmat's ``bruker_raw_parser.py``, MIT) and is **not** independent: it
hard-codes absolute offsets lifted from one file, so it is useful only as a
cross-check — every one of its constants lands where the structural walk puts
them.

Four magic numbers, one reader::

    RAW      v1 — refused; no description of it is obtainable
    RAW2     v2
    RAW1.01  v3   (the version numbering is the vendor's, not a typo)
    RAW4.00  v4

**v4 is a walk, not a table of offsets.**  After a fixed 61-byte preamble the
file is a chain of ``(uint32 type, uint32 length)`` segments; a type of 0 or 160
is not a segment but the marker that a *range* follows, and a range is a header
(itself ending in a nested chain of segments, of declared total size
``hdrSize``) followed by ``nSteps`` records of ``datumSize`` bytes each, of
which the leading float32 is the intensity.  Then the chain resumes.  Two bugs
in the other two readers are what make the walk worth stating:

* **stride by ``datumSize``.**  GSAS-II reads the field and then reads ``nSteps``
  *consecutive* float32s anyway; FAIRmat hard-codes an 8-byte stride it
  describes as "interleaved float32 pairs".  Both are right on a file with
  ``datumSize == 8`` and wrong on one with 4.  The real fixture has 8, and the
  trailing four bytes of each of its 7134 records are ``int32 == 1`` — a field
  whose meaning is unknown, so it is stepped over rather than guessed at.
* **walk to EOF; never count.**  GSAS-II counts occurrences of ``b'2Theta'`` in
  the whole file to decide how many banks there are.  ``2Theta`` occurs
  **twice** in the single-range real fixture — once as a drive record and once
  as the scan-axis record — so that count reports two ranges where there is one.

**Which drive was scanned is read, not assumed.**  The range header's nested
chain carries one type-50 record per drive, each with a name, a flag and the
position it sat at.  The scanned one is the record whose flag is non-zero *and*
whose position equals the range's own start angle — two independent statements
that must agree, because one real file is not enough to trust the flag alone.
Where they do not, the ``ScanType`` string decides, and where that is unfamiliar
too the axis is assumed and said so.  This is the same three-way policy the
other four formats use (:func:`base.check_axis`); the vocabulary is this
format's own.

**σ has to be measured, because v4 declares no intensity unit at all.**  The
range header does give the counting time — ``stepTime``, in **milliseconds**:
the fixture's 310.003 over 7134 steps is a 37-minute scan, where seconds would
make it 25 days.  So :func:`base.sigma_by_arithmetic` decides, exactly as for
the two Rigaku formats: integral values are counts and the Poisson fallback is
correct, an integral ``y·t`` is a rate whose σ is derived, and anything else
withholds σ and says the scale could not be verified.

**The real fixture proves structure and metadata, never values.**  See
``tests/data/README.md``: its header is intact and its intensities are not the
measurement.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path

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
    sigma_by_arithmetic,
)

#: The four magic strings, longest first so ``RAW1.01`` is not read as ``RAW ``
#: would be if the test were four bytes for every version.  The value is the
#: version number this package uses in its own messages.
_MAGIC: tuple[tuple[bytes, int], ...] = (
    (b"RAW1.01", 3),
    (b"RAW4.00", 4),
    (b"RAW2", 2),
    (b"RAW ", 1),
)

#: Where the v4 segment chain begins — the only fixed offset in the format past
#: the preamble's date and time strings.
_V4_SEGMENTS = 61

#: Segment "types" that are not segments: each marks the start of a range.
_RANGE_MARKERS = frozenset({0, 160})

#: Segment payload layouts, as offsets from the segment's own start.
_SEG_KEYVALUE = 10          # uint32 skip, char[24] key, char[len-36] value
_SEG_SOURCE = 30            # 64 skip, then Kα-mean/Kα1/Kα2/Kβ/ratio, then anode
_SEG_DRIVE = 50             # uint32 flag, char[24] name, 20 skip, float64 position

#: A datum is at least one float32; anything smaller cannot hold an intensity.
_MIN_DATUM = 4

#: Drive names whose stepped axis is the diffraction angle 2θ.
_TWO_THETA_DRIVES = frozenset({"2theta", "twotheta"})

#: Drive names that are recognisably **not** 2θ, with what each one measures.
#: The vocabulary is the set of drive names these files carry (``Theta``,
#: ``2Theta``, ``Chi``, ``Phi``, ``BeamTranslation``, ``Z-Drive``, ``Divergence
#: Slit``), classified by what the goniometer does when each is the scanned one.
_OTHER_DRIVES: dict[str, str] = {
    "theta": "a rocking curve about θ with the detector fixed",
    "omega": "a rocking curve about ω with the detector fixed",
    "phi": "a φ rotation — one ring of a pole figure",
    "chi": "a χ tilt — one arc of a pole figure",
    "khi": "a χ tilt — one arc of a pole figure",
    "psi": "a ψ tilt, as measured for residual stress",
    "zdrive": "a specimen height scan, used to set the sample surface",
    "z": "a specimen height scan, used to set the sample surface",
    "beamtranslation": "a translation of the beam across the specimen",
    "divergenceslit": "a divergence-slit opening scan, not a diffraction scan",
}

#: ``ScanType`` values whose abscissa is 2θ, used only when the drive records do
#: not agree with each other.  ``Detector Scan`` moves the detector alone and
#: ``Locked``/``Unlocked Coupled`` move θ and 2θ together; all three step 2θ.
_TWO_THETA_SCAN_TYPES = frozenset({"locked coupled", "unlocked coupled",
                                   "detector scan"})


def _key(name: str) -> str:
    return name.lower().replace(" ", "").replace("-", "").replace("_", "")


@dataclass(frozen=True)
class _Drive:
    """One goniometer axis as a range header records it."""

    name: str
    #: non-zero on exactly one record in the real fixture — the scanned drive.
    #: Not trusted alone: see :func:`_scan_axis`
    flag: int
    position: float


@dataclass(frozen=True)
class _Range:
    """One measurement inside a v4 file, located but not yet decoded."""

    scan_type: str
    start: float
    step: float
    n_points: int
    #: seconds per step, or ``None`` where the file's milliseconds are unusable
    count_time_s: float | None
    generator_kv: float
    generator_ma: float
    wavelength: float
    datum_size: int
    drives: tuple[_Drive, ...]
    #: where the intensity records begin, and where the range as a whole ends
    data_at: int
    end: int

    @property
    def two_theta(self) -> np.ndarray:
        return self.start + self.step * np.arange(self.n_points, dtype=np.float64)


def _unpack(fmt: str, buf: bytes, at: int, *, path: Path, what: str) -> tuple:
    """``struct.unpack_from`` that refuses by naming the file, never ``struct.error``."""
    try:
        return struct.unpack_from(fmt, buf, at)
    except struct.error:
        raise ValueError(
            f"{path.name}: the file ends inside {what} — it wants "
            f"{struct.calcsize(fmt)} bytes at offset {at} and holds "
            f"{len(buf)}. The file is truncated or is not the format its magic "
            "bytes claim") from None


def _text(buf: bytes, at: int, length: int) -> str:
    """A fixed-width NUL-padded field, decoded permissively.

    ``latin-1`` rather than UTF-8 because these are Windows-written operator
    strings — a sample name with a degree sign in it must not make the file
    unreadable — and ``errors`` cannot help a codec that would reject nothing.
    """
    return buf[at:at + length].split(b"\0")[0].decode("latin-1").strip()


def _segment(buf: bytes, at: int, *, path: Path) -> tuple[int, int]:
    """The ``(type, length)`` at ``at``, with length clamped and bounds checked."""
    kind, declared = _unpack("<II", buf, at, path=path, what="a segment header")
    length = max(declared, 8)
    if at + length > len(buf):
        raise ValueError(
            f"{path.name}: a segment of type {kind} at offset {at} declares "
            f"{length} bytes but only {len(buf) - at} remain. The file is "
            "truncated")
    return kind, length


def _drives(buf: bytes, at: int, size: int, *, path: Path) -> tuple[_Drive, ...]:
    """Every drive record in a range header's nested chain of ``size`` bytes.

    The chain must land **exactly** on the declared end.  That is the
    self-consistency gate this format needs most: a mis-parsed length walks off
    into the intensity records and finds plausible-looking segments there, so
    "ended where it said it would" is the difference between a parse and a
    coincidence.
    """
    out: list[_Drive] = []
    cursor, end = at, at + size
    if end > len(buf):
        raise ValueError(f"{path.name}: the range header declares {size} bytes of "
                         f"drive records at offset {at}, past the end of a "
                         f"{len(buf)}-byte file")
    while cursor < end:
        kind, length = _segment(buf, cursor, path=path)
        if kind == _SEG_DRIVE:
            flag, = _unpack("<I", buf, cursor + 8, path=path, what="a drive flag")
            position, = _unpack("<d", buf, cursor + 56, path=path,
                                what="a drive position")
            out.append(_Drive(name=_text(buf, cursor + 12, 24), flag=flag,
                              position=position))
        cursor += length
    if cursor != end:
        raise ValueError(
            f"{path.name}: the range header's segments overrun the {size} bytes "
            f"it declares — they end at offset {cursor}, {cursor - end} byte(s) "
            "past. The header is not the layout this reader knows")
    return tuple(out)


def _read_range(buf: bytes, marker: int, *, path: Path) -> _Range:
    """One range, located from its marker at ``marker`` — the field table.

    Offsets are relative to ``p``, the start angle, which sits 72 bytes past the
    marker: 4 for the marker word itself, 28 unread, 24 of ``ScanType`` and 16
    more unread.
    """
    scan_type = _text(buf, marker + 32, 24)
    p = marker + 72
    start, step = _unpack("<dd", buf, p, path=path, what="a range's start and step")
    n_points, = _unpack("<I", buf, p + 16, path=path, what="a range's point count")
    step_time_ms, = _unpack("<f", buf, p + 20, path=path, what="a range's step time")
    kv, ma = _unpack("<ff", buf, p + 28, path=path, what="the generator settings")
    wavelength, = _unpack("<d", buf, p + 40, path=path, what="the wavelength")
    datum_size, hdr_size = _unpack("<II", buf, p + 64, path=path,
                                   what="the datum and header sizes")

    if n_points < 1:
        raise ValueError(f"{path.name}: a range declares {n_points} points")
    if datum_size < _MIN_DATUM or datum_size % 4:
        raise ValueError(
            f"{path.name}: a range declares a datum of {datum_size} bytes; an "
            f"intensity is a float32, so a datum is a multiple of 4 and at "
            f"least {_MIN_DATUM}")
    if step == 0.0 or not np.isfinite(step) or not np.isfinite(start):
        raise ValueError(f"{path.name}: a range steps by {step!r} from {start!r}, "
                         "which is not a scan this reader can put on an axis")

    drives = _drives(buf, p + 88, hdr_size, path=path)
    data_at = p + 88 + hdr_size
    end = data_at + datum_size * n_points
    if end > len(buf):
        raise ValueError(
            f"{path.name}: a range declares {n_points} points of {datum_size} "
            f"bytes from offset {data_at}, which needs {end} bytes and the file "
            f"holds {len(buf)}. The file is truncated")

    # milliseconds, and a scan whose step time is zero or absurd tells us nothing
    # about its counting statistics — so no counting time rather than a wrong one
    time_s = step_time_ms / 1000.0 if 0.0 < step_time_ms < 1e9 else None
    return _Range(scan_type=scan_type, start=start, step=step, n_points=n_points,
                  count_time_s=time_s, generator_kv=kv, generator_ma=ma,
                  wavelength=wavelength, datum_size=datum_size, drives=drives,
                  data_at=data_at, end=end)


@dataclass(frozen=True)
class _File:
    """A v4 file's file-level header and every range in it, located."""

    keys: dict[str, str]
    anode: str | None
    wavelengths: tuple[float, ...]
    ranges: tuple[_Range, ...]


def _read_v4(buf: bytes, *, path: Path) -> _File:
    """Walk the whole file: segments until a range marker, a range, repeat.

    To EOF rather than to a count, because there is no count to read — and the
    one other reader that invents one gets it wrong on the only real file.
    """
    keys: dict[str, str] = {}
    anode: str | None = None
    waves: tuple[float, ...] = ()
    ranges: list[_Range] = []

    cursor = _V4_SEGMENTS
    while cursor + 4 <= len(buf):
        kind, = _unpack("<I", buf, cursor, path=path, what="a segment type")
        if kind in _RANGE_MARKERS:
            found = _read_range(buf, cursor, path=path)
            ranges.append(found)
            cursor = found.end
            continue
        kind, length = _segment(buf, cursor, path=path)
        if kind == _SEG_KEYVALUE:
            keys[_text(buf, cursor + 12, 24).upper()] = _text(buf, cursor + 36,
                                                              length - 36)
        elif kind == _SEG_SOURCE:
            base = cursor + 72
            waves = _unpack("<5d", buf, base, path=path, what="the tube wavelengths")
            anode = _text(buf, base + 44, 4) or None
        cursor += length

    if not ranges:
        raise ValueError(
            f"{path.name}: the header parses as Bruker RAW4 but the file holds "
            "no measurement range. It is either truncated before its data or is "
            "a settings file rather than a scan")
    return _File(keys=keys, anode=anode, wavelengths=waves, ranges=tuple(ranges))


def _version(p: Path) -> int:
    """Which of the four RAW formats ``p`` is, by magic bytes."""
    raw = head(p, 8).raw
    for magic, version in _MAGIC:
        if raw.startswith(magic):
            return version
    raise ValueError(f"{p.name}: not a Bruker RAW file — its first bytes are "
                     f"{raw[:8]!r}")


def _v4_or_refuse(p: Path) -> bytes:
    """The file's bytes, or a refusal naming the version and why it is declined."""
    version = _version(p)
    if version == 4:
        return p.read_bytes()
    raise ValueError(
        f"{p.name} is Bruker RAW version {version}, which this build does not "
        "read yet — only version 4 (magic RAW4.00). Re-export it from DIFFRAC "
        "as RAW4, or convert it to .uxd, .xy or GSAS .fxye, all of which this "
        "build reads")


def _scan_axis(found: _Range, *, path: Path,
               diagnostics: list[Diagnostic] | None) -> str | None:
    """Which drive was stepped, from two statements that have to agree.

    A drive record's flag is non-zero on exactly one record in the only real
    file, and that record's stored position is also the range's start angle.
    One file is not enough to trust either statement alone, so the scanned drive
    is the one both pick out.  A ``Locked Coupled`` scan moves θ and 2θ together
    and the flagged record is ``2Theta``, whose 10.0° is the start angle while
    ``Theta`` sits at 5.0 — so the position test is what separates the abscissa
    from the drives that merely moved.
    """
    candidates = [d for d in found.drives
                  if d.flag and np.isclose(d.position, found.start, atol=1e-6)]
    if len(candidates) != 1:
        # fall back to what the file calls the *kind* of scan.  Less specific —
        # it names the coupling rather than the axis — but it is a statement the
        # file makes about the same thing, and it is what GSAS-II validates on
        key = found.scan_type.lower()
        return check_axis(
            found.scan_type, path=path, field="ScanType",
            two_theta=key in _TWO_THETA_SCAN_TYPES,
            other=None,
            note=(" No single drive record is flagged as the scanned one at the "
                  "range's start angle, so the scan type had to answer instead."),
            diagnostics=diagnostics)
    scanned = candidates[0].name
    return check_axis(
        scanned, path=path, field="the scanned drive",
        two_theta=_key(scanned) in _TWO_THETA_DRIVES,
        other=_OTHER_DRIVES.get(_key(scanned)),
        remedy="Export the coupled θ–2θ range instead.",
        note=f" The file calls this scan a {found.scan_type!r}.",
        diagnostics=diagnostics)


def read_bruker_raw(path: str | Path, *, scan: int | None = None,
                    diagnostics: list[Diagnostic] | None = None) -> PatternData:
    p = Path(path)
    buf = _v4_or_refuse(p)
    parsed = _read_v4(buf, path=p)
    multiscan_default(len(parsed.ranges), scan, path=p, diagnostics=diagnostics)

    index = 0 if scan is None else scan
    if not 0 <= index < len(parsed.ranges):
        raise ValueError(f"{p.name} holds {len(parsed.ranges)} range(s), numbered "
                         f"0 to {len(parsed.ranges) - 1}; scan={index} is not one "
                         "of them")
    found = parsed.ranges[index]

    axis = _scan_axis(found, path=p, diagnostics=diagnostics)
    # stride by the declared datum, reading only its leading float32: the rest of
    # a wider datum is a field whose meaning no description gives
    records = np.frombuffer(buf, dtype=np.uint8, offset=found.data_at,
                            count=found.datum_size * found.n_points,
                            ).reshape(found.n_points, found.datum_size)
    y = np.ascontiguousarray(records[:, :4]).view("<f4").reshape(-1)
    y = np.asarray(y, dtype=np.float64)
    if not np.all(np.isfinite(y)):
        raise ValueError(f"{p.name}: {int((~np.isfinite(y)).sum())} of "
                         f"{y.size} intensities are not finite numbers, so the "
                         "data block is not float32 at the stride the header "
                         "declares")

    sigma = sigma_by_arithmetic(y, found.count_time_s, "", path=p,
                                diagnostics=diagnostics)
    tt, y, sig = ascending(found.two_theta, y, sigma, path=p, fmt=BRUKER_RAW,
                           diagnostics=diagnostics)
    alpha2 = parsed.wavelengths[2] if len(parsed.wavelengths) > 2 else 0.0
    return pattern_data(
        p, tt, y, sig,
        source_file=p.name, format="bruker_raw", scan=index,
        scan_count=len(parsed.ranges), scan_axis=axis,
        sample=parsed.keys.get("SAMPLEID") or None,
        title=parsed.keys.get("COMMENT") or None,
        anode=parsed.anode,
        wavelength=found.wavelength or None,
        wavelength_alpha2=alpha2 or None,
        count_time_s=found.count_time_s)


def list_bruker_raw_scans(path: str | Path) -> list[ScanInfo]:
    p = Path(path)
    parsed = _read_v4(_v4_or_refuse(p), path=p)
    out: list[ScanInfo] = []
    for i, found in enumerate(parsed.ranges):
        stepped = found.two_theta
        low, high = float(min(stepped[0], stepped[-1])), float(max(stepped[0],
                                                                  stepped[-1]))
        drive = next((d.name for d in found.drives
                      if d.flag and np.isclose(d.position, found.start, atol=1e-6)),
                     found.scan_type or "?")
        out.append(ScanInfo(index=i, label=f"{drive} {low:.4g}–{high:.4g}°",
                            n_points=found.n_points, two_theta_range=(low, high)))
    return out


def looks_bruker_raw(p: Path) -> bool:
    """Magic bytes, and nothing else — the strongest evidence in the registry.

    Disjoint from GSAS raw by construction: that format is claimed by a ``BANK``
    record, so a GSAS file named ``.raw`` still reaches it and a Bruker file
    named ``.gsas`` still reaches this one.
    """
    raw = head(p, 8).raw
    return any(raw.startswith(magic) for magic, _ in _MAGIC)


BRUKER_RAW = PatternFormat(
    name="bruker_raw",
    title="Bruker/Siemens DIFFRAC binary (.raw, v4)",
    extensions=(".raw",),
    sniff="the file begins RAW4.00 (or RAW1.01/RAW2/'RAW ', which are named "
          "and refused as the versions this build does not read)",
    sigma=("measured per file: integral intensities are counts and take the "
           "Poisson fallback, an integral y·t is a rate whose σ is derived from "
           "the header's step time, and anything else withholds σ — v4 declares "
           "no intensity unit anywhere"),
    matches=looks_bruker_raw,
    read=read_bruker_raw,
    options=("scan",),
    scans=list_bruker_raw_scans,
)

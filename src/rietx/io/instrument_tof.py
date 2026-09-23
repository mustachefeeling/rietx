"""Time-of-flight instrument-parameter files: one frozen ``Instrument`` per bank.

A calibration, not a model and not a pattern: each reader returns
:class:`~rietx.schemas.instrument.Instrument` objects whose
:class:`~rietx.schemas.instrument.TOFSource` carries DIFC/DIFA/ZERO(/DIFB), the
bank angle, the profile coefficients and the incident spectrum — every
parameter ``vary=False``, because a value read from an instrument file was
refined against a standard.  No writer exists for either format.

GSAS-I ``.iparm`` / ``.prm`` / ``.inst`` — :func:`read_gsas_tof_iparm`
---------------------------------------------------------------------
Larson & Von Dreele (2004), *GSAS — General Structure Analysis System*,
LAUR 86-748, GSAS Technical Manual p. 221-223: 80-character records with a
12-character key, read **by column** from the manual's FORTRAN formats, the
bank number ``bb`` in columns 5-6.

* ``INS   BANK  `` (I5, NBANK) and ``INS   HTYPE `` (2X,A4) are required.  The
  histogram type must begin ``PNT`` — powder, neutron, time-of-flight
  (manual p. 182, 222); anything else is refused by name.
* ``INS bb ICONS`` (3F10.0,10X,F10.0,I5,F10.0) holds DIFC, DIFA, ZERO in µs
  units for a TOF bank and **nothing else**: POLA, IPOLA and KRATIO "are absent
  for neutron data" (p. 222), so non-blank columns 53-77 are refused.  There is
  no DIFB field in GSAS-I; ``difb`` is 0.
* ``INS bbBNKPAR`` (5F10.0,2I5) gives DIST and TTHETA; TTHETA is the bank's
  scattering angle 2Θ in degrees and is required (DIFC alone cannot give it
  back), DIST is carried as ``l2_m`` — the field's name is its only
  definition, so that mapping is an inference and is metadata only.
* ``INS bbI ITYP`` (I5,2F10.4,I10) — ITYP, TMIN, TMAX, CHKSUM.  TMIN/TMAX are
  in **milliseconds** (p. 223) and are carried in µs.  CHKSUM's algorithm is
  not published: it is read and never recomputed or checked, and since the
  schema has no slot for it, it is reported as dropped.
* ``INS bbICOFFc`` (4E15.6, c = 1…3) — the twelve coefficient slots, in
  TOF-in-milliseconds (p. 223); ``INS bbIECOFc`` their esds, carried as each
  coefficient's ``stderr``.  A block that disagrees with its ITYP — a missing
  or out-of-sequence record, a non-zero slot the type does not read, a
  non-zero ITYP 1/2 fifth pair whose exponent is unpublished, ITYP 10 (the
  spectrum is in another file), an undefined ITYP — is refused by name
  (:mod:`rietx.model.tof_spectrum`).  ``IECOR`` has no slot and is dropped.
  No ``ITYP`` record at all is read as no spectrum.
* ``INS bbPRCFn `` (2I5,F10.5; PTYP, NCOF, CTOF) and ``INS bbPRCFnc``
  (4E15.6) — the NTYP profile sets; **set n = 1 is the default** whatever its
  PTYP (p. 223) and is the only set read.

**Named assumption — PRCF coefficient order.**  The manual lists each
function's coefficients "respectively" against their GSAS names (function 1,
p. 144: ``alp-0 alp-1 bet-0 bet-1 sig-0 sig-1 sig-2 s1ec s2ec rstr rsta rsca``;
function 2, p. 147: fifteen; function 3, p. 148: ``alp bet-0 bet-1 sig-0 sig-1
sig-2 gam-0 gam-1 gam-2 g1ec g2ec gsf rstr rsta rsca L11 L22 L33 L12 L13 L23``)
but never says that is the order in the record.  It is the only ordering the
documentation offers and it is adopted as such.  A block whose NCOF is not the
documented 12 / 15 / 21 for PTYP 1 / 2 / 3 is refused, never padded or
truncated.  Profile functions 2 (Ikeda-Carpenter), 4 and 5 are documented but
not evaluated by this package: a default set of one of them is refused by
name; a non-default one is reported and skipped.  The anisotropic and
peak-shift coefficients of functions 1 and 3 belong with the microstructure
machinery, so a non-zero one is refused rather than dropped.  ``CTOF`` is "a
cutoff factor" (p. 223) and nothing more in the manual: it is read, reported,
and never used to set a window.

**Column overrun.**  Reading by column, a value written one field too wide
is silently *truncated*: ``46.60`` placed in columns 30-34 leaves ``46.`` in
TTHETA's columns 23-32, which reads as 46.0.  So every parsed record (BANK,
ICONS, BNKPAR, I ITYP, ICOFF/IECOF, the default PRCF set's header and
coefficient records) is tested at each field boundary, a ``10X`` skip and the
columns after the last field (to 80) counting as spans a right-aligned
writer leaves blank.  At a boundary where the left span's last column **and**
the right span's first column are both non-blank, the pair is two packed
full-width fields only if the right span holds no blank at all — a
right-aligned field whose first column is occupied is full.  Any blank in
the right span means a token began on the left and stopped inside the right
span, which no right-aligned field produces, and the record is refused
naming its key, both fields' columns and the raw text.  Blank fields keep
their FORTRAN reading of zero.

What this cannot see, stated rather than hidden:

* **an overrun that ends exactly on a field boundary** — ``       46.`` then
  ``6000000000`` is, character for character, two full-width fields, and the
  two halves read as 46.0 and 6000000000;
* **a whole-field shift** — a value placed entirely inside the wrong field,
  left- or right-aligned, crosses no boundary and reads as a well-formed
  number in the wrong slot (a TTHETA moved into TILT's columns reads TTHETA
  as blank, i.e. zero);
* **mixed alignment is refused though FORTRAN would read it**: a full
  right-aligned field followed by a *left*-aligned one (``      2.5046.60``)
  is legal FORTRAN input (blanks in a numeric field are null by default),
  but on the page it is the overrun's signature, and right-aligning the
  second value costs nothing.

``HTYPE`` is text, not a number, and is not tested; a shifted histogram type
already fails the ``PNT`` test.  The ``.instprm`` reader splits ``key:value``
lines and slices no columns, so none of this applies to it.

GSAS-II ``.instprm`` — :func:`read_gsas2_instprm`
------------------------------------------------
The published GSAS-II documentation names the TOF parameters
(``alpha, beta-0, beta-1, beta-q, sig-0, sig-1, sig-2, sig-q, difA, difB,
difC, Zero``, with ``X``/``Y`` for Lorentzian sample broadening) and gives
``TOF = C·d + A·d² + B/d + Z``, but it does **not** publish the file's grammar,
nor the d-laws of ``beta-q``, ``sig-q``, ``Z``, ``X`` or ``Y``.  So the grammar
read here is an *observed* subset, not a specification:

* one bank per file; a line is either blank, a comment starting ``#``, or
  ``key:value`` split at the first colon, both sides stripped; a repeated key
  is refused (it is how a second bank would appear, and multi-bank delimiting
  is not published);
* ``Type`` must be present and begin ``PNT``; ``2-theta`` (the bank angle in
  degrees, the key's own spelling being its only definition) must be present;
* mapped: ``difC``→difc, ``difA``→difa, ``difB``→difb, ``Zero``→tzero,
  ``alpha``→**alpha1** (GSAS profile function 3 has α = α₁/d, manual p. 148;
  alpha0 = 0), ``beta-0``, ``beta-1``, ``sig-0``, ``sig-1``, ``sig-2`` (the
  last three variance coefficients, used as written);
* named but unmappable — ``beta-q``, ``sig-q``, ``Z``, ``X``, ``Y`` and the
  constant-wavelength names ``SH/L``, ``Polariz.``, ``Lam`` — are accepted
  only at exactly 0 (reported as dropped) and refused otherwise;
* observed metadata ``Bank``, ``fltPath``, ``Azimuth`` are reported as
  dropped;
* **any other key is refused, spelled out** — never read as zero.

Every refusal names the file.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import ValidationError

from ..model.tof_spectrum import (
    COEFFICIENT_COUNTS,
    _refuse_inferred_pair,
    _unknown_type_message,
)
from ..schemas.common import Diagnostic, Parameter
from ..schemas.instrument import IncidentSpectrum, Instrument, ProfileTOF, TOFSource
from .projects.gsas import split_records

#: Documented coefficient names, in the manual's "respectively" order (p. 144,
#: 147, 148) — the only ordering the documentation offers (module docstring).
PRCF_COEFFICIENT_NAMES: dict[int, tuple[str, ...]] = {
    1: ("alp-0", "alp-1", "bet-0", "bet-1", "sig-0", "sig-1", "sig-2",
        "s1ec", "s2ec", "rstr", "rsta", "rsca"),
    2: ("alp-0", "alp-1", "beta", "switch", "sig-0", "sig-1", "sig-2",
        "gam-0", "gam-1", "gam-2", "stec", "ptec", "difc", "difa", "zero"),
    3: ("alp", "bet-0", "bet-1", "sig-0", "sig-1", "sig-2", "gam-0", "gam-1",
        "gam-2", "g1ec", "g2ec", "gsf", "rstr", "rsta", "rsca",
        "L11", "L22", "L33", "L12", "L13", "L23"),
}

#: Which documented names land on which :class:`ProfileTOF` field.
_PRCF_TO_PROFILE: dict[int, dict[str, str]] = {
    1: {"alp-0": "alpha0", "alp-1": "alpha1", "bet-0": "beta0", "bet-1": "beta1",
        "sig-0": "sig0", "sig-1": "sig1", "sig-2": "sig2"},
    3: {"alp": "alpha1", "bet-0": "beta0", "bet-1": "beta1", "sig-0": "sig0",
        "sig-1": "sig1", "sig-2": "sig2", "gam-0": "gam0", "gam-1": "gam1",
        "gam-2": "gam2"},
}

#: Documented profile functions this package does not evaluate, and why.
_PRCF_NOT_EVALUATED: dict[int, str] = {
    2: "the Ikeda-Carpenter function (manual p. 145-147), a causal shape with a "
       "different peak origin from the back-to-back pair",
    4: "profile function 4 (manual p. 149)",
    5: "profile function 5 (manual p. 155)",
}

#: Each parsed record's FORTRAN layout as contiguous ``(first, last, name)``
#: column spans (GSAS Technical Manual p. 221-223; SPEC § 6.1) — what
#: :meth:`_Record.check_columns` tests for a number crossing a boundary.  A
#: ``10X`` skip is a span too: a right-aligned writer leaves it blank.
_BANK_FIELDS = ((13, 17, "NBANK"),)
_ICONS_FIELDS = ((13, 22, "DIFC"), (23, 32, "DIFA"), (33, 42, "ZERO"),
                 (43, 52, "the 10X skip"), (53, 62, "POLA"), (63, 67, "IPOLA"),
                 (68, 77, "KRATIO"))
_BNKPAR_FIELDS = ((13, 22, "DIST"), (23, 32, "TTHETA"), (33, 42, "TILT"),
                  (43, 52, "SEPN"), (53, 62, "HGHT"), (63, 67, "NTUBE"),
                  (68, 72, "ITUBE"))
_ITYP_FIELDS = ((13, 17, "ITYP"), (18, 27, "TMIN"), (28, 37, "TMAX"),
                (38, 47, "CHKSUM"))
_PRCF_FIELDS = ((13, 17, "PTYP"), (18, 22, "NCOF"), (23, 32, "CTOF"))
_E15_FIELDS = tuple((13 + 15 * k, 27 + 15 * k, f"coefficient field {k + 1}")
                    for k in range(4))

#: .instprm keys mapped onto the schema.
_INSTPRM_SOURCE = {"difC": "difc", "difA": "difa", "difB": "difb", "Zero": "tzero"}
_INSTPRM_PROFILE = {"alpha": "alpha1", "beta-0": "beta0", "beta-1": "beta1",
                    "sig-0": "sig0", "sig-1": "sig1", "sig-2": "sig2"}
#: Named in the documentation but with no d-law (or no TOF meaning) published.
_INSTPRM_ZERO_ONLY = ("beta-q", "sig-q", "Z", "X", "Y", "SH/L", "Polariz.", "Lam")
_INSTPRM_METADATA = ("Bank", "fltPath", "Azimuth")


def _note(diagnostics, level, code, message, where=()):
    if diagnostics is not None:
        diagnostics.append(Diagnostic(level=level, code=code, message=message,
                                      where=list(where)))


class _Record:
    """One 80-column record, with 1-based column access and a located error.

    Records are numbered as :func:`_read_records` returns them (blank lines
    are not records), which is the number an error message quotes.
    """

    def __init__(self, path: Path, number: int, text: str):
        self.path = path
        self.number_in_file = number
        self.text = text.rstrip("\r\n").ljust(80)

    def cols(self, a: int, b: int) -> str:
        return self.text[a - 1:b]

    def fail(self, message: str) -> ValueError:
        return ValueError(f"{self.path}: record {self.number_in_file} "
                          f"({self.text[:12].rstrip()!r}): {message}")

    def number(self, a: int, b: int, what: str) -> float:
        s = self.cols(a, b).strip()
        if not s:
            return 0.0          # a blank FORTRAN numeric field reads as zero
        try:
            return float(s.replace("D", "E").replace("d", "e"))
        except ValueError:
            raise self.fail(f"{what} in columns {a}-{b} is {s!r}, which is not "
                            f"a number") from None

    def integer(self, a: int, b: int, what: str) -> int:
        s = self.cols(a, b).strip()
        if not s:
            return 0
        try:
            return int(s)
        except ValueError:
            raise self.fail(f"{what} in columns {a}-{b} is {s!r}, which is not "
                            f"an integer") from None

    def e15_block(self) -> list[str]:
        """The four 4E15.6 fields (columns 13-72), raw."""
        self.check_columns(_E15_FIELDS)
        return [self.cols(13 + 15 * k, 27 + 15 * k) for k in range(4)]

    def check_columns(self, fields: tuple[tuple[int, int, str], ...]) -> None:
        """Refuse a number that runs across a field boundary (module docstring,
        § Column overrun).

        ``fields`` is the record's FORTRAN layout as contiguous ``(first, last,
        name)`` spans from column 13; the columns after the last field, to 80,
        are one more span a right-aligned writer leaves blank.  At each
        boundary, a non-blank last column on the left beside a non-blank first
        column on the right is two full fields only if the right span holds no
        blank at all; any blank in it means a token began on the left and
        stopped short of the right span's end, which no right-aligned field
        produces.
        """
        spans = list(fields)
        if spans[-1][1] < 80:
            spans.append((spans[-1][1] + 1, 80, "the columns after the last field"))
        for (a1, b1, n1), (a2, b2, n2) in zip(spans, spans[1:]):
            left, right = self.cols(a1, b1), self.cols(a2, b2)
            if left[-1] == " " or right[0] == " " or " " not in right:
                continue
            start = b1
            while start > a1 and self.text[start - 2] != " ":
                start -= 1
            end = a2 + right.index(" ") - 1
            raise self.fail(
                f"the text {self.text[start - 1:end]!r} in columns {start}-{end} "
                f"runs across the boundary between {n1} (columns {a1}-{b1}) and "
                f"{n2} (columns {a2}-{b2}). Read by column, {n1} would be "
                f"{left.strip()!r} and {n2} would begin {right.strip()!r} — a "
                f"misaligned field, refused rather than read as a truncated "
                f"number; right-align each value inside its columns")


def _read_records(path: Path) -> list[tuple[str, str]]:
    """The file's ``(12-character key, payload)`` records, in file order.

    The splitting is the package's one GSAS card-index grammar,
    :func:`rietx.io.projects.gsas.split_records` (80-character records, a
    12-character key, the payload from column 13 — GSAS Technical Manual
    p. 221, the same columns as SPEC § 6.1), so a column means the same thing
    here as in the experiment-file and constant-wavelength ``.prm`` readers.
    Only the splitting is shared: every field is read below by this module's
    own column parser, which refuses a non-numeric field rather than reading
    it as blank.
    """
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise OSError(f"{path}: cannot be read ({exc})") from exc
    return split_records(raw.decode("latin-1"))


def _read_lines(path: Path) -> list[str]:
    """An ``.instprm``'s lines (the grammar :func:`read_gsas2_instprm` states)."""
    try:
        return path.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError:
        return path.read_text(encoding="latin-1").splitlines()
    except OSError as exc:
        raise OSError(f"{path}: cannot be read ({exc})") from exc


# ---------------------------------------------------------------------------
# GSAS-I
# ---------------------------------------------------------------------------
def _htype_refusal(path: Path, htype: str) -> ValueError:
    kinds = {"P": "powder", "S": "single-crystal"}
    rads = {"N": "neutron", "X": "x-ray"}
    data = {"T": "time-of-flight", "C": "constant-wavelength",
            "E": "energy-dispersive"}
    h = htype.ljust(4)
    if h[0] in kinds and h[1] in rads and h[2] in data:
        extra = (" A constant-wavelength powder .prm is read by "
                 "rietx.read_gsas_prm." if h[2] == "C" and h[0] == "P" else "")
        return ValueError(
            f"{path}: HTYPE {htype!r} is a {kinds[h[0]]} {rads[h[1]]} "
            f"{data[h[2]]} histogram type (GSAS Technical Manual p. 182); this "
            f"reader reads only neutron time-of-flight powder banks, HTYPE "
            f"PNT….{extra}")
    return ValueError(f"{path}: unrecognised GSAS HTYPE {htype!r}; a neutron "
                      f"time-of-flight powder bank is PNTR (GSAS Technical "
                      f"Manual p. 182, 222)")


def _sequence(path: Path, bank: int, name: str, recs: dict[int, _Record],
              want: int) -> list[str]:
    """The raw E15 fields of records ``name1 … name<want>``, strictly in order."""
    tags = sorted(recs)
    if tags and tags != list(range(1, len(tags) + 1)):
        raise ValueError(
            f"{path}: bank {bank}'s {name} records are tagged {tags}; they must "
            f"be the consecutive run 1…{want} (GSAS Technical Manual p. 223), "
            f"and a gap would shift every later coefficient into the wrong slot")
    fields: list[str] = []
    for c in tags:
        fields.extend(recs[c].e15_block())
    if len(tags) != want:
        held = sum(1 for f in fields if f.strip())
        raise ValueError(
            f"{path}: bank {bank}'s {name} block holds {held} coefficients in "
            f"{len(tags)} records; the manual writes {want} records of four "
            f"(GSAS Technical Manual p. 223), and a short block is refused "
            f"rather than padded")
    return fields


def _e15_values(path: Path, bank: int, name: str, fields: list[str]) -> list[float]:
    out = []
    for k, f in enumerate(fields):
        s = f.strip()
        try:
            out.append(float(s.replace("D", "E")) if s else 0.0)
        except ValueError:
            raise ValueError(f"{path}: bank {bank}'s {name} slot {k + 1} is "
                             f"{s!r}, which is not a number") from None
    return out


def _spectrum(path: Path, bank: int, ityp_rec: _Record | None,
              icoff: dict[int, _Record], iecof: dict[int, _Record],
              dropped: list[str]) -> IncidentSpectrum:
    if ityp_rec is None:
        if icoff:
            raise ValueError(f"{path}: bank {bank} has ICOFF records and no "
                             f"'I ITYP' record to say which function they are")
        return IncidentSpectrum()
    ityp_rec.check_columns(_ITYP_FIELDS)
    itype = ityp_rec.integer(13, 17, "ITYP")
    tmin = ityp_rec.number(18, 27, "TMIN")
    tmax = ityp_rec.number(28, 37, "TMAX")
    ityp_rec.integer(38, 47, "CHKSUM")       # read, carried nowhere, never checked
    dropped.append("CHKSUM")
    if itype not in COEFFICIENT_COUNTS:
        raise ValueError(f"{path}: bank {bank}: {_unknown_type_message(itype)}")
    want = COEFFICIENT_COUNTS[itype]
    lo = tmin * 1000.0 if tmin > 0.0 else None
    hi = tmax * 1000.0 if tmax > 0.0 else None
    if want == 0:
        if icoff:
            vals = _e15_values(path, bank, "ICOFF",
                               _sequence(path, bank, "ICOFF", icoff, 3))
            if any(v != 0.0 for v in vals):
                raise ValueError(f"{path}: bank {bank} declares ITYP 0 (no "
                                 f"incident spectrum) and carries non-zero "
                                 f"ICOFF coefficients")
        if lo is not None and hi is not None and not lo < hi:
            lo = hi = None
        return IncidentSpectrum(itype=0, tof_min_us=lo, tof_max_us=hi)
    vals = _e15_values(path, bank, "ICOFF", _sequence(path, bank, "ICOFF", icoff, 3))
    for k in range(want, 12):
        if vals[k] != 0.0:
            raise ValueError(
                f"{path}: bank {bank}: ITYP {itype} uses {want} coefficients and "
                f"slot P{k + 1} = {vals[k]!r} is non-zero; a number in a slot the "
                f"declared function does not read is refused")
    try:
        _refuse_inferred_pair(itype, vals)
    except ValueError as exc:
        raise ValueError(f"{path}: bank {bank}: {exc}") from None
    esds: list[float | None] = [None] * want
    if iecof:
        evals = _e15_values(path, bank, "IECOF",
                            _sequence(path, bank, "IECOF", iecof, 3))
        esds = evals[:want]
    coefficients = [Parameter(value=v, vary=False, stderr=e)
                    for v, e in zip(vals[:want], esds)]
    try:
        return IncidentSpectrum(itype=itype, coefficients=coefficients,
                                tof_min_us=lo, tof_max_us=hi)
    except ValidationError as exc:
        raise ValueError(f"{path}: bank {bank}: {exc}") from None


def _profile(path: Path, bank: int, headers: dict[int, _Record],
             conts: dict[int, dict[int, _Record]], diagnostics) -> ProfileTOF:
    if not headers:
        if conts:
            raise ValueError(f"{path}: bank {bank} has PRCF coefficient records "
                             f"and no PRCF header")
        _note(diagnostics, "warning", "GSAS_IPARM_PROFILE_DECLINED",
              f"bank {bank}: no PRCF profile set, so the profile coefficients "
              f"are left at zero; a fit refuses such a bank by name",
              where=[f"bank {bank}"])
        return ProfileTOF()
    if 1 not in headers:
        raise ValueError(
            f"{path}: bank {bank}'s PRCF sets are numbered {sorted(headers)}; "
            f"the manual numbers them n = 1 … NTYP and makes set 1 the default "
            f"(GSAS Technical Manual p. 223), so without set 1 the file does not "
            f"say which function is in force")
    for n in sorted(conts):
        if n not in headers:
            raise ValueError(f"{path}: bank {bank} has PRCF{n} coefficient "
                             f"records and no PRCF{n} header")
    chosen: ProfileTOF | None = None
    for n in sorted(headers):
        rec = headers[n]
        rec.check_columns(_PRCF_FIELDS)
        ptyp = rec.integer(13, 17, "PTYP")
        ncof = rec.integer(18, 22, "NCOF")
        ctof = rec.number(23, 32, "CTOF")
        if ptyp not in PRCF_COEFFICIENT_NAMES and ptyp not in _PRCF_NOT_EVALUATED:
            raise rec.fail(f"PRCF set {n} declares profile function {ptyp}, which "
                           f"the GSAS Technical Manual does not define")
        if ptyp in PRCF_COEFFICIENT_NAMES:
            want = len(PRCF_COEFFICIENT_NAMES[ptyp])
            if ncof != want:
                raise rec.fail(
                    f"PRCF set {n} declares profile function {ptyp} with {ncof} "
                    f"coefficients; the manual documents {want} for function "
                    f"{ptyp}, and a block of another length is refused — never "
                    f"zero-padded or truncated — because the order of its "
                    f"slots would be a guess")
        if n != 1:
            _note(diagnostics, "info", "GSAS_IPARM_PROFILE_DECLINED",
                  f"bank {bank}: PRCF set {n} (profile function {ptyp}) is not "
                  f"read — set 1 is the default whatever its function (GSAS "
                  f"Technical Manual p. 223)", where=[f"bank {bank}", f"PRCF{n}"])
            continue
        if ptyp in _PRCF_NOT_EVALUATED:
            raise rec.fail(
                f"the default PRCF set declares PTYP = {ptyp}, "
                f"{_PRCF_NOT_EVALUATED[ptyp]}, which this package does not "
                f"evaluate; refused rather than mapped onto the back-to-back "
                f"coefficients")
        fields = _sequence(path, bank, f"PRCF{n}", conts.get(n, {}),
                           1 + (ncof - 1) // 4)
        values = _e15_values(path, bank, f"PRCF{n}", fields)
        for k in range(ncof, len(values)):
            if values[k] != 0.0:
                raise rec.fail(f"PRCF set {n} declares {ncof} coefficients and "
                               f"slot {k + 1} beyond them holds {values[k]!r}")
        names = PRCF_COEFFICIENT_NAMES[ptyp]
        mapping = _PRCF_TO_PROFILE[ptyp]
        kwargs: dict[str, float] = {}
        for name, value in zip(names, values[:ncof]):
            if name in mapping:
                kwargs[mapping[name]] = value
            elif value != 0.0:
                raise rec.fail(
                    f"PRCF set {n}, profile function {ptyp}: {name} = {value!r} "
                    f"is non-zero. It is an anisotropic-broadening or peak-shift "
                    f"coefficient (GSAS Technical Manual p. 144, 148) that "
                    f"belongs with the microstructure machinery and has no slot "
                    f"on ProfileTOF; refused rather than dropped")
        for field in ("sig0", "sig1", "sig2"):
            if kwargs.get(field, 0.0) < 0.0:
                raise rec.fail(f"PRCF set {n}: {field} = {kwargs[field]!r} is a "
                               f"variance coefficient and is negative")
        try:
            chosen = ProfileTOF(**kwargs)
        except ValidationError as exc:
            raise rec.fail(str(exc)) from None
        _note(diagnostics, "info", "GSAS_IPARM_PROFILE_READ",
              f"bank {bank}: PRCF set 1, profile function {ptyp} with {ncof} "
              f"coefficients, read in the order the GSAS Technical Manual lists "
              f"them ({', '.join(names)}). The manual lists them 'respectively' "
              f"against those names but never states that this is the record "
              f"order, so the order is an assumption. CTOF = {ctof!r} is read "
              f"and not used: the manual calls it 'a cutoff factor' and defines "
              f"it no further.", where=[f"bank {bank}", "PRCF1"])
    assert chosen is not None
    return chosen


def read_gsas_tof_iparm(path: str | Path, *,
                        diagnostics: list[Diagnostic] | None = None
                        ) -> dict[int, Instrument]:
    """Read a GSAS-I TOF instrument-parameter file: ``{bank number: Instrument}``.

    Every bank the file declares comes back, keyed by the number its records
    carry — several banks are what a TOF instrument *is*, so none is picked.
    Records, columns and refusals are the module docstring's.  ``diagnostics``,
    when given, receives ``GSAS_IPARM_PROFILE_READ`` (the profile set read, the
    order assumption it rests on, CTOF), ``GSAS_IPARM_PROFILE_DECLINED`` (a set
    not read) and ``GSAS_IPARM_FIELD_DROPPED`` (records and fields with no slot
    in the schema); what is *returned* never depends on whether it was given.
    """
    path = Path(path)
    nbank: int | None = None
    htype: str | None = None
    whole_dropped: list[str] = []
    banks: dict[int, dict] = {}

    for number, (key, payload) in enumerate(_read_records(path), start=1):
        line = key + payload
        if not line.startswith("INS "):
            continue
        rec = _Record(path, number, line)
        bb = rec.cols(5, 6)
        name = rec.cols(7, 12)
        if not bb.strip():
            key = name.strip()
            if key == "BANK":
                rec.check_columns(_BANK_FIELDS)
                nbank = rec.integer(13, 17, "NBANK")
            elif key == "HTYPE":
                htype = rec.cols(15, 18).strip()
            elif key not in whole_dropped:
                whole_dropped.append(key)
            continue
        if not bb.strip().isdigit():
            raise rec.fail(f"columns 5-6 hold {bb!r}, not a bank number")
        bank = banks.setdefault(int(bb), {
            "icons": None, "bnkpar": None, "ityp": None, "icoff": {},
            "iecof": {}, "prcf": {}, "prcf_c": {}, "dropped": [], "bad_key": None})
        if name == " ICONS":
            bank["icons"] = rec
        elif name == "BNKPAR":
            bank["bnkpar"] = rec
        elif name == "I ITYP":
            bank["ityp"] = rec
        elif name[:5] in ("ICOFF", "IECOF") and name[5].isdigit():
            bank["icoff" if name[:5] == "ICOFF" else "iecof"][int(name[5])] = rec
        elif name.startswith("PRCF"):
            n, c = name[4], name[5]
            if not n.isdigit() or n == "0":
                # refused when this bank is processed, so the file-level
                # refusals (HTYPE, NBANK) and earlier banks speak first
                bank["bad_key"] = bank["bad_key"] or rec.fail(
                    f"the PRCF set number in column 11 is {n!r}; the manual "
                    f"numbers the sets n = 1 … NTYP (GSAS Technical Manual "
                    f"p. 223), and a key spelled otherwise is not a documented "
                    f"record")
            elif c == " ":
                bank["prcf"][int(n)] = rec
            elif c.isdigit():
                bank["prcf_c"].setdefault(int(n), {})[int(c)] = rec
            else:
                bank["bad_key"] = bank["bad_key"] or rec.fail(
                    f"column 12 of a PRCF key is {c!r}; it is blank on a header "
                    f"and a digit on a coefficient record")
        else:
            key = name.strip()
            if key not in bank["dropped"]:
                bank["dropped"].append(key)

    if htype is None:
        raise ValueError(f"{path}: no 'INS   HTYPE ' record; the manual requires "
                         f"one (GSAS Technical Manual p. 221-222)")
    if not htype.startswith("PNT"):
        raise _htype_refusal(path, htype)
    if nbank is None:
        raise ValueError(f"{path}: no 'INS   BANK  ' record; the manual requires "
                         f"one (GSAS Technical Manual p. 221)")
    stray = sorted(b for b in banks if not 1 <= b <= nbank)
    if stray:
        raise ValueError(f"{path}: NBANK is {nbank} and records name bank(s) "
                         f"{stray}")

    out: dict[int, Instrument] = {}
    dropped_all: list[str] = list(whole_dropped)
    for b in range(1, nbank + 1):
        bank = banks.get(b)
        if bank is None or bank["icons"] is None:
            raise ValueError(f"{path}: NBANK is {nbank} and bank {b} has no "
                             f"ICONS record")
        icons = bank["icons"]
        icons.check_columns(_ICONS_FIELDS)
        difc = icons.number(13, 22, "DIFC")
        difa = icons.number(23, 32, "DIFA")
        zero = icons.number(33, 42, "ZERO")
        if icons.cols(53, 77).strip():
            raise icons.fail(
                f"columns 53-77 hold {icons.cols(53, 77).strip()!r}; POLA, IPOLA "
                f"and KRATIO are absent for neutron data (GSAS Technical Manual "
                f"p. 222), so a neutron-TOF ICONS record carrying them is not "
                f"the record this reader was told it is")
        if bank["bnkpar"] is None:
            raise ValueError(f"{path}: bank {b} has no BNKPAR record, so its "
                             f"scattering angle is unknown — DIFC alone is one "
                             f"number from two and does not give the angle back")
        bnkpar = bank["bnkpar"]
        bnkpar.check_columns(_BNKPAR_FIELDS)
        dist = bnkpar.number(13, 22, "DIST")
        ttheta = bnkpar.number(23, 32, "TTHETA")
        dropped = list(bank["dropped"])
        spectrum = _spectrum(path, b, bank["ityp"], bank["icoff"], bank["iecof"],
                             dropped)
        if bank["bad_key"] is not None:
            raise bank["bad_key"]
        profile = _profile(path, b, bank["prcf"], bank["prcf_c"], diagnostics)
        try:
            source = TOFSource(difc=difc, difa=difa, tzero=zero,
                               two_theta_bank_deg=ttheta,
                               l2_m=dist if dist > 0.0 else None,
                               profile_tof=profile, incident_spectrum=spectrum)
        except ValidationError as exc:
            raise ValueError(f"{path}: bank {b}: {exc}") from None
        out[b] = Instrument(source=source)
        for key in dropped:
            if key not in dropped_all:
                dropped_all.append(key)
    if dropped_all:
        _note(diagnostics, "info", "GSAS_IPARM_FIELD_DROPPED",
              f"{path.name}: records or fields with no slot in the schema were "
              f"read and not carried: {', '.join(dropped_all)}. IECOR (the "
              f"spectrum's correlation matrix) and CHKSUM (whose algorithm is "
              f"not published) have nowhere to go; the others are not among the "
              f"records the GSAS Technical Manual p. 221-223 gives a TOF bank a "
              f"use for here.", where=dropped_all)
    return out


def read_gsas_iparm(path: str | Path, *,
                    diagnostics: list[Diagnostic] | None = None
                    ) -> dict[int, Instrument]:
    """:func:`read_gsas_tof_iparm` under the name the specification uses."""
    return read_gsas_tof_iparm(path, diagnostics=diagnostics)


# ---------------------------------------------------------------------------
# GSAS-II
# ---------------------------------------------------------------------------
def _grammar_refusal(path: Path, lineno: int, line: str, why: str) -> ValueError:
    return ValueError(
        f"{path}: line {lineno} ({line.strip()!r}): {why}. The .instprm grammar "
        f"is not published; this reader accepts only blank lines, '#' comments "
        f"and one 'key:value' per line for a single bank")


def read_gsas2_instprm(path: str | Path, *,
                       diagnostics: list[Diagnostic] | None = None) -> Instrument:
    """Read a GSAS-II time-of-flight ``.instprm`` as one frozen ``Instrument``.

    Only the observed grammar and the keys the module docstring lists are
    read; any other key is refused with the key in the message, never read
    as zero.  ``diagnostics``, when given, receives one
    ``GSAS2_INSTPRM_FIELD_DROPPED`` naming the keys read and not carried.
    """
    path = Path(path)
    items: dict[str, tuple[int, str]] = {}
    for lineno, line in enumerate(_read_lines(path), start=1):
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if ":" not in s:
            raise _grammar_refusal(path, lineno, line, "no ':' separator")
        key, value = (part.strip() for part in s.split(":", 1))
        if not key:
            raise _grammar_refusal(path, lineno, line, "an empty key")
        if key in items:
            raise _grammar_refusal(
                path, lineno, line,
                f"{key!r} appears twice (first on line {items[key][0]}); how "
                f"several banks are delimited is not published")
        items[key] = (lineno, value)

    def number(key: str) -> float:
        lineno, value = items[key]
        try:
            return float(value)
        except ValueError:
            raise ValueError(f"{path}: line {lineno}: {key} is {value!r}, which "
                             f"is not a number") from None

    known = (set(_INSTPRM_SOURCE) | set(_INSTPRM_PROFILE) | set(_INSTPRM_ZERO_ONLY)
             | set(_INSTPRM_METADATA) | {"Type", "2-theta"})
    for key, (lineno, _value) in items.items():
        if key not in known:
            raise ValueError(
                f"{path}: line {lineno}: key {key!r} is not one this reader can "
                f"name; an unrecognised .instprm key is refused rather than read "
                f"as zero, because a silent zero is a silently wrong profile")

    if "Type" not in items:
        raise ValueError(f"{path}: no 'Type' key, so the file does not say it "
                         f"is a time-of-flight bank")
    htype = items["Type"][1]
    if not htype.startswith("PNT"):
        data = {"PXC": "powder constant-wavelength x-ray",
                "PNC": "powder constant-wavelength neutron"}.get(htype[:3])
        what = f"Type {htype} is {data}" if data else f"Type {htype!r} is unrecognised"
        raise ValueError(f"{path}: {what}; this reader reads only a neutron "
                         f"time-of-flight bank (Type PNT). A constant-wavelength "
                         f".instprm is read by rietx.read_gsas2_instprm.")
    for key in ("difC", "2-theta"):
        if key not in items:
            raise ValueError(f"{path}: no {key!r} key; a time-of-flight bank "
                             f"needs its DIFC and its scattering angle")

    dropped: list[str] = []
    for key in _INSTPRM_ZERO_ONLY:
        if key in items:
            value = number(key)
            if value != 0.0:
                raise ValueError(
                    f"{path}: {key} is {value!r}: its law is not published "
                    f"(the GSAS-II documentation names it and gives no "
                    f"d-dependence or unit for a TOF bank), so a non-zero value "
                    f"is refused rather than dropped")
            dropped.append(key)
    dropped.extend(k for k in _INSTPRM_METADATA if k in items)

    source_kw = {field: number(key) for key, field in _INSTPRM_SOURCE.items()
                 if key in items}
    profile_kw = {field: number(key) for key, field in _INSTPRM_PROFILE.items()
                  if key in items}
    for field in ("sig0", "sig1", "sig2"):
        if profile_kw.get(field, 0.0) < 0.0:
            raise ValueError(f"{path}: {field.replace('sig', 'sig-')} = "
                             f"{profile_kw[field]!r} is a variance coefficient "
                             f"and is negative")
    try:
        profile = ProfileTOF(**profile_kw)
        source = TOFSource(two_theta_bank_deg=number("2-theta"),
                           profile_tof=profile, **source_kw)
    except ValidationError as exc:
        raise ValueError(f"{path}: {exc}") from None
    if dropped:
        _note(diagnostics, "info", "GSAS2_INSTPRM_FIELD_DROPPED",
              f"{path.name}: keys read and not carried: {', '.join(dropped)} — "
              f"metadata with no slot, or named coefficients whose law is not "
              f"published and whose value here is 0.", where=dropped)
    return Instrument(source=source)


def read_instprm(path: str | Path, *,
                 diagnostics: list[Diagnostic] | None = None) -> Instrument:
    """:func:`read_gsas2_instprm` under the name the specification uses."""
    return read_gsas2_instprm(path, diagnostics=diagnostics)

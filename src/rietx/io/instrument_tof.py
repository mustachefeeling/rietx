"""Time-of-flight instrument-parameter files: GSAS-I ``.iparm``/``.prm`` and GSAS-II ``.instprm``.

The *calibration* half of the time-of-flight track.  A TOF bank's peak
positions are not in the data file — a GSAS ``BANK`` record carries binning
constants and nothing else — so a pattern without its instrument-parameter file
is an axis in microseconds with no way back to a d-spacing.  These two readers
are that way back, and they return the same thing
:func:`rietx.io.instrument_profile.load_instrument_profile` does: an
:class:`~rietx.schemas.instrument.Instrument` whose parameters are all
``vary=False``, because an instrument-parameter file is a beamline calibration
refined against a standard and not a starting guess.

**A new module rather than more of ``instrument_profile.py``**, because the two
formats overlap in their record grammar and in nothing else: a GSAS-I
constant-wavelength ``.prm`` states a wavelength, a Caglioti resolution
function and a polarisation, and a GSAS-I time-of-flight ``.iparm`` states
DIFC/DIFA/ZERO, a flight path and a back-to-back-exponential pulse shape, with
no field in common but the ``INS`` record itself.  Sharing a parser between
them would be sharing a *shape*, not a meaning.

**Records are read by column, not by regular expression.**  GSAS writes the
``INS`` record as a Fortran fixed format — ``INS``, the bank number in three
columns, a six-character record name, then the data — and the record name
carries meaning in its blanks: bank 1's profile block is ``PRCF1 `` with
continuations ``PRCF11``/``PRCF12`` in one real file (LANSCE NPDF) and ``PRCF ``
with continuations ``PRCF 1``…``PRCF 4`` in another (ISIS GEM).  Those are the
same record written with a different sequence tag, and a whitespace-tolerant
pattern reads them as two unrelated names.

**What is read and what is declined.**  The four calibration constants and the
bank geometry are read and *verified*: LANSCE NPDF's four banks convert their
own Si standard to d-spacings matching Si to 7 × 10⁻⁴ rms, which is the check
that a DIFC/DIFA/ZERO triple either passes or does not.  The GSAS-I **profile
coefficients** are read for exactly **one** layout and declined by type for
every other, and the reason for declining is the one ``io/formats/gsas.py``
gives for ``ALT``: each GSAS TOF profile function has its own
independently-defined coefficient layout (the manual's type 1 has 12, type 3
has 15, type 4 has 14-27), and reading one off another's description would be a
guess by position.

The layout that *is* read is **type 1 with 8 coefficients**
(:data:`_PRCF1_LAYOUT`), which is what every real type-1 block obtainable here
declares — the manual's twelve is not a count any file writes.  It is read
because the order was **corroborated** rather than assumed, twice over: the
physics it produces (Δd/d improving monotonically across NPDF's four bank
angles; a predicted 58.8 µs FWHM against 62.4 µs observed) and GSAS-II's own
reader agreeing field for field.  A block whose slot 8 (GSAS's ``s1ec``,
which :class:`~rietx.schemas.instrument.ProfileTOF` has no term for) is
non-zero, or whose variance slots are negative, is declined instead: both say
the block is not the layout its header declares.  When a bank declares
**several** profile functions — NPDF declares type 1 and type 4 — the file does
not say which was in force, so only the lowest-numbered block is read, which is
GSAS-II's own selection rule.

Declining is a **diagnostic and not a refusal**, because the calibration is
what a caller needs to convert the pattern at all and a declined profile leaves
``ProfileTOF`` at its all-zero state, which
``model.forward_tof.compile_tof_model`` refuses **by name** rather than
evaluating.  So a declined block cannot mislead a fit by being absent; it can
only stop one, loudly.  A GSAS-II ``.instprm`` names each coefficient, so there
is nothing to guess and its profile *is* read.

**The incident spectrum is read.**  ``I ITYP``, ``ICOFF`` and ``IECOF`` give
:class:`~rietx.schemas.instrument.IncidentSpectrum` — which function, its
coefficients and their esds — and the forward model applies it, because unlike
the profile block these have a stated layout that does not depend on a
coefficient count the file and the manual disagree about.  ``ITYP 0``, which is
what an already-normalised reduction writes, is the default and means none.

Spec: Larson & Von Dreele (2004), *GSAS — General Structure Analysis System*,
LAUR 86-748, GSAS Technical Manual pp. 127-152 (``ATTRIBUTION.md``:
manual-as-spec, no code taken); and, for the ``.instprm`` key names, GSAS-II's
own published parameter list (Toby & Von Dreele, 2013, *J. Appl. Cryst.* **46**,
544), read as a vocabulary.
"""

from __future__ import annotations

from pathlib import Path

from ..model.tof_spectrum import COEFFICIENT_COUNTS, SPECTRUM_TYPES, _unknown_type_message
from ..schemas.common import Diagnostic, Parameter
from ..schemas.instrument import IncidentSpectrum, Instrument, ProfileTOF, TOFSource

# ---------------------------------------------------------------------------
# GSAS-I .iparm / .prm
# ---------------------------------------------------------------------------

#: The fixed columns of a GSAS ``INS`` record: ``INS`` (1-3), the bank number
#: right-justified in 4-6 (blank for a file-level record), the record name in
#: 7-12, the data from 13 on.  A specification fact, and the reason this module
#: does not use a whitespace regex — see the module docstring.
_INS_BANK_COLS = slice(3, 6)
_INS_NAME_COLS = slice(6, 12)
_INS_DATA_COLS = slice(12, None)

#: ``HTYPE`` for powder neutron time-of-flight — the one this reader reads.
_HTYPE_PNTR = "PNTR"

#: The other ``HTYPE`` values and where each one belongs instead.  Named rather
#: than met with a generic "not a TOF file", because both of these have a
#: reader (or a documented absence of one) and saying which is the difference
#: between a refusal a caller can act on and one they cannot.
_HTYPE_REFUSALS: dict[str, str] = {
    "PXCR": ("powder constant-wavelength X-ray. Its ICONS record is a "
             "wavelength, a zero point and a polarisation, not a "
             "DIFC/DIFA/ZERO triple — read it with "
             "rietx.io.instrument_profile.read_gsas_prm instead"),
    "PNCR": ("powder constant-wavelength neutron. Its resolution function is "
             "the Caglioti/TCH one ProfileTCHZ holds, not a "
             "back-to-back-exponential pulse shape, and its ICONS record is a "
             "wavelength rather than a DIFC/DIFA/ZERO triple"),
}

#: Per-bank ``INS`` record names this reader *reads* rather than drops, other
#: than the ``PRCF`` family (handled by prefix) and the ``ICOFF``/``IECOF``
#: blocks (handled by their sequence tags).  Listed so the drop diagnostic is
#: the complement of what is read and cannot fall out of step with it.
_READ_RECORDS: frozenset[str] = frozenset({"ICONS", "BNKPAR", "I ITYP"})

#: GSAS TOF profile-function types, and how many coefficients the **manual**
#: says each carries.  Used only to say what a declined block was, never to
#: read one: the count in the file's own header is what a reader would trust,
#: and the disagreements below are exactly why no layout is guessed at.  Real
#: files measured: LANSCE NPDF declares type 1 with 8 coefficients (the manual
#: says 12) and type 4 with 12 (the manual says 14-27); ISIS GEM declares type
#: 2 with 15.  Type 3 — the one whose 15 coefficients the manual lists in
#: order, and the one :class:`~rietx.schemas.instrument.ProfileTOF` is shaped
#: for — appears in neither.
_PRCF_TYPES: dict[str, str] = {
    "1": "back-to-back exponentials convoluted with a Gaussian (manual "
         "p. 143-144, 12 coefficients)",
    "2": "the Ikeda-Carpenter moderator pulse convoluted with a pseudo-Voigt "
         "(manual p. 144-146)",
    "3": "the Ikeda-Carpenter form with a d-spacing-dependent width law "
         "(manual p. 147-148, 15 coefficients: alpha-0/1, beta-0/1, "
         "sig-0/1/2, gam-0/1/2, two anisotropic terms, then DIFC/DIFA/ZERO)",
    "4": "back-to-back exponentials with the Stephens rank-4 microstrain "
         "expansion (manual p. 149-152, 14-27 coefficients)",
}

#: The one ``PRCF`` layout this reader **reads**: GSAS TOF profile function 1
#: written with **8** coefficients, in this order, onto these
#: :class:`~rietx.schemas.instrument.ProfileTOF` fields.  ``None`` is a slot
#: read and not carried.
#:
#: **The layout is corroborated, not documented** — the manual says type 1 has
#: twelve coefficients and every real type-1 block obtainable declares eight,
#: so this is a reading established from evidence rather than transcribed:
#:
#: * **Physics.**  Under it LANSCE NPDF's four banks give
#:   σ/d = √sig-1 = 18.8, 17.3, 14.1, 10.9 µs/Å, i.e. Δd/d (FWHM) = 0.64 %,
#:   0.34 %, 0.23 %, 0.16 % at bank angles 46.6°, 90°, 119°, 148° —
#:   monotonically improving with scattering angle, which is what a
#:   time-of-flight diffractometer does and what a wrong field order would not
#:   produce.  Second, independent check on bank 4's (220): the predicted FWHM
#:   from the exponential pair plus the Gaussian is 58.8 µs against an observed
#:   62.4 µs.
#: * **The reference implementation agrees, field for field.**  GSAS-II's
#:   ``GetPowderIparm`` reads an ``abs(pfType) == 1`` block's first
#:   continuation fields 2, 3, 4 as ``alpha``, ``beta-0``, ``beta-1`` and its
#:   second continuation's fields 2, 3 as ``sig-1``, ``sig-2`` (``GSASIIfiles``,
#:   permissively licensed and read here as a *fact* about the format per
#:   ``ATTRIBUTION.md`` § Format specifications — no line transcribed).  Its
#:   lone ``alpha`` is a 1/d coefficient, so it is this container's ``alpha1``,
#:   which is what puts ``alp-0`` in slot 1.  GSAS-II carries no ``alp-0`` term
#:   at all and hard-codes ``sig-0`` to zero rather than reading slot 5; both
#:   are zero in every obtainable file, so the two readings cannot be told
#:   apart on the data and this one carries more of the file.
#:
#: Slot 8 is GSAS's ``s1ec``, which :class:`ProfileTOF` has no term for.  It is
#: zero in every obtainable type-1 block; a **non-zero** value there says this
#: block is not the layout being assumed, so the whole block is declined rather
#: than read past — ``read_gsas_prm``'s rule for an unmapped key, with a
#: diagnostic instead of a raise for this module's own reason (the calibration
#: is what a caller needs, § the module docstring).
_PRCF1_LAYOUT: tuple[str | None, ...] = (
    "alpha0", "alpha1", "beta0", "beta1", "sig0", "sig1", "sig2", None)

#: The profile-function type whose block :data:`_PRCF1_LAYOUT` describes, and
#: the coefficient count the real files declare it with.  Both are matched: the
#: manual's own type-1 count is twelve, and a twelve-coefficient type-1 block
#: is a layout no obtainable file establishes, so it stays declined.
_PRCF1_TYPE = "1"
_PRCF1_NCOEF = 8


def _ins_records(text: str) -> list[tuple[str, str, str]]:
    """Every ``INS`` record as ``(bank, name, data)``, by column.

    ``bank`` is the record's three columns stripped — ``""`` for a file-level
    record such as ``HTYPE`` or ``FPATH1``.  ``name`` keeps its blanks, because
    they are what distinguishes a ``PRCF`` header from its ``PRCF 1``
    continuation (§ the module docstring).
    """
    out = []
    for raw in text.splitlines():
        if not raw.startswith("INS"):
            continue
        line = raw.rstrip("\n")
        out.append((line[_INS_BANK_COLS].strip(), line[_INS_NAME_COLS],
                    line[_INS_DATA_COLS]))
    return out


def _prcf_headers(names: list[str]) -> set[str]:
    """Which of a bank's ``PRCF*`` record names are **headers**, structurally.

    A continuation's name is its header's name plus a right-justified index in
    whatever columns are left, so a header is a ``PRCF`` name that no *other*
    ``PRCF`` name is a proper prefix of.  That reads both real spellings
    (``PRCF1``→``PRCF11``, ``PRCF``→``PRCF 1``) off the record grammar rather
    than off the values, which is what keeps a header whose coefficients happen
    to look like a count from being mistaken for one.
    """
    stripped = {n.rstrip() for n in names}
    return {n for n in stripped
            if not any(other != n and n.startswith(other) for other in stripped)}


def _prcf_continuation_values(rows: list[tuple[str, str]],
                              header: str) -> list[float] | None:
    """One ``PRCF`` header's continuation coefficients, concatenated in order.

    Read by **sequence tag off the written name**, never off a stripped one:
    ``PRCF1 ``'s continuations are ``PRCF11``/``PRCF12`` and ``PRCF  ``'s are
    ``PRCF 1``…``PRCF 4``, and both strip to names the other spelling also
    produces — ``PRCF 1`` stripped is ``PRCF1``, which is a *header* in the
    first file and a *continuation* in the second.  That collision is the whole
    reason this module reads records by column (§ the module docstring).

    The tags are required to be the consecutive run ``1…n``, for
    :func:`_spectrum_block`'s reason: a gap would shift coefficients into the
    wrong slots, and every slot here is a different power of d.  ``None`` when
    the header has no continuations or the run has a hole.
    """
    blocks: dict[int, str] = {}
    for name, data in rows:
        written = name.rstrip()
        if written == header or not written.startswith(header):
            continue
        tag = written[len(header):].strip()
        if tag.isdigit():
            blocks[int(tag)] = data
    if not blocks or sorted(blocks) != list(range(1, max(blocks) + 1)):
        return None
    out: list[float] = []
    for i in sorted(blocks):
        for token in blocks[i].split():
            try:
                out.append(float(token))
            except ValueError:
                return None
    return out


def _read_prcf1(rows: list[tuple[str, str]], header: str, kind: str,
                ncoef: str, headers: list[str]) -> tuple[ProfileTOF | None, str]:
    """A type-1 8-coefficient ``PRCF`` block as a :class:`ProfileTOF`, or why not.

    Returns ``(profile, note)``; ``profile`` is ``None`` whenever the block is
    declined, and ``note`` is the sentence the diagnostic carries either way.
    The gates, each one a thing that would otherwise be assumed:

    * the header's own **type and count** are the pair
      :data:`_PRCF1_LAYOUT` was established on — a type-1 block written with
      the manual's twelve coefficients is a layout no obtainable file
      establishes, and stays declined;
    * this block is the bank's **lowest-numbered** ``PRCF`` record, which is
      GSAS-II's own selection rule (it reads ``PRCF1 ``/``PRCF  `` and nothing
      else) and matters because an ``.iparm`` may declare several profile
      functions — LANSCE NPDF declares type 1 *and* type 4 — and does not say
      which one a project had selected;
    * the continuations are present, consecutive and numeric
      (:func:`_prcf_continuation_values`);
    * slot 8, GSAS's ``s1ec``, is **zero** — a value there says the block is
      not this layout;
    * the three variance coefficients are **non-negative**, which is what
      :class:`ProfileTOF` stores them as since T-1d.  A negative one is
      refused as a layout signal rather than clipped: GSAS-II itself puts no
      sign constraint on ``sig-1``/``sig-2``, so a file carrying one is
      either a different layout or a model this container cannot hold, and
      neither is a number to guess at.
    """
    if kind != _PRCF1_TYPE or ncoef != str(_PRCF1_NCOEF):
        return None, ("Its coefficients were not read: each GSAS TOF profile "
                      "function has its own independently-defined layout, and "
                      f"the one layout established here is type {_PRCF1_TYPE} "
                      f"written with {_PRCF1_NCOEF} coefficients")
    if headers and header != min(headers):
        return None, (f"Its coefficients were not read: this bank also declares "
                      f"{', '.join(h for h in sorted(headers) if h != header)}, "
                      f"and the file does not say which profile function was in "
                      f"force. GSAS-II reads the lowest-numbered block, which "
                      f"is not this one")
    values = _prcf_continuation_values(rows, header)
    if values is None or len(values) < _PRCF1_NCOEF:
        return None, ("Its coefficients were not read: its continuation "
                      "records are not the consecutive numeric run a PRCF "
                      "block is written as, so which slot each coefficient "
                      "belongs to is not established")
    slots = values[:_PRCF1_NCOEF]
    unread = [(i + 1, v) for i, (v, field)
              in enumerate(zip(slots, _PRCF1_LAYOUT, strict=True))
              if field is None and v != 0.0]
    if unread:
        return None, ("Its coefficients were not read: slot(s) "
                      + ", ".join(f"P{i} = {v!r}" for i, v in unread)
                      + " hold a non-zero value and are slots this container "
                        "has no term for (GSAS's s1ec), which says the block "
                        "is not the layout its header declares")
    mapped = {field: v for v, field in zip(slots, _PRCF1_LAYOUT, strict=True)
              if field is not None}
    negative = {k: v for k, v in mapped.items() if k.startswith("sig") and v < 0.0}
    if negative:
        return None, ("Its coefficients were not read: "
                      + ", ".join(f"{k} = {v!r}" for k, v in negative.items())
                      + " is negative, and these three slots are Gaussian "
                        "**variance** coefficients in µs², µs²/Å² and µs²/Å⁴. "
                        "A negative one is either a different layout or a "
                        "model ProfileTOF cannot hold")
    return ProfileTOF(**mapped), (
        "Its eight coefficients were read as (alp-0, alp-1, bet-0, bet-1, "
        "sig-0, sig-1, sig-2, s1ec) — a layout **corroborated, not "
        "documented**: the manual gives type 1 twelve coefficients and every "
        "real block declares eight, so the order is established from the "
        "physics it produces (Δd/d improving monotonically with bank angle "
        "across four banks; a 58.8 µs predicted FWHM against 62.4 µs "
        "observed) and from GSAS-II's own reader agreeing field for field. "
        "s1ec has no term here and was zero")


def read_gsas_tof_iparm(path: str | Path, *,
                        diagnostics: list[Diagnostic] | None = None,
                        ) -> dict[int, Instrument]:
    """A GSAS-I TOF instrument-parameter file, **one Instrument per bank**.

    Returns ``{bank number: Instrument}`` and never a single one, because a TOF
    diffractometer *is* several banks — LANSCE NPDF writes four, ISIS GEM six —
    and each has its own DIFC, its own scattering angle and its own profile.
    Picking one silently is the failure
    :func:`rietx.io.instrument_profile.read_gsas_prm` refuses a multi-bank file
    to avoid; here the answer is to return all of them and let the caller index.
    They meet again in a multi-histogram fit, one instrument per histogram.

    What each bank's records give:

    ==============  ===========================================================
    record          read as
    ==============  ===========================================================
    ``HTYPE``       must be ``PNTR``; every other value refused **by name**
    ``FPATH1``      the primary flight path L₁ in m (file-level, all banks)
    ``ICONS``       ``DIFC DIFA ZERO`` — µs/Å, µs/Å², µs.  The manual, p. 141:
                    *"The three parameters DIFC, DIFA and ZERO are
                    characteristic of a given counter bank"*
    ``BNKPAR``      fields 1-2: L₂ in m and the bank's fixed 2θ in degrees
    ``PRCF*``       a **type-1, 8-coefficient** block is read onto
                    ``source.profile_tof`` (``GSAS_IPARM_PROFILE_READ``, and
                    the diagnostic says the layout is corroborated rather than
                    documented); every other type, and a type-1 block whose
                    unread slot or variance signs disagree with it, is
                    **declined** with a diagnostic naming the type and its
                    count (§ the module docstring)
    ==============  ===========================================================

    ``I ITYP`` (which incident-spectrum function, and over what flight-time
    window in **milli**seconds), ``ICOFF`` (its coefficients) and ``IECOF``
    (their esds) are read into
    :class:`~rietx.schemas.instrument.IncidentSpectrum` and applied by the
    forward model.  ``IECOR``, ``BNKNAM``, ``MFIL`` and ``HEAD`` are dropped
    and named once in a ``GSAS_IPARM_FIELD_DROPPED`` diagnostic; the last three
    are labels, and ``IECOR``'s reason is its consumer, not its content — it is
    the coefficients' correlation matrix, and GSAS uses it to propagate the
    spectrum's *own* uncertainty into the **weight** of every profile point
    (PAGE 128: *"This esd is used to adjust the weight assigned to each profile
    point for the uncertainty in the calculated incident intensity"*).  This
    package's weights are the data's own σ, so a covariance whose only use is a
    reweighting scheme nothing here performs would be carried and never read.
    The per-coefficient esds *are* kept, on each ``Parameter``'s ``stderr``,
    because they say which coefficients the vanadium run actually determined.

    Measured, against LANSCE NPDF run 7245 (Si standard in a helium
    displex, 4 banks × 6537 channels, Michael Gaultois's beamtime): the four
    banks' constants convert their own bank of that file to d-spacings whose
    strongest lines match Si to an rms Δd/d of 7 × 10⁻⁴, and zeroing DIFA and
    ZERO degrades that by an order of magnitude — the negative control that
    makes the positive one mean something.
    """
    p = Path(path)
    records = _ins_records(p.read_text(encoding="utf-8", errors="ignore"))
    if not records:
        raise ValueError(
            f"{p.name}: not a GSAS-I instrument-parameter file — no INS record "
            f"found at all (Larson & Von Dreele, LAUR 86-748)")

    htype = next((d.strip().upper() for b, n, d in records
                  if n.strip() == "HTYPE"), None)
    if htype is None:
        raise ValueError(
            f"{p.name}: this GSAS-I instrument-parameter file states no HTYPE, "
            f"so what kind of instrument it describes — and therefore what its "
            f"ICONS record holds — is not established at all")
    if htype != _HTYPE_PNTR:
        what = _HTYPE_REFUSALS.get(htype)
        if what is not None:
            raise ValueError(f"{p.name}: HTYPE {htype} is {what}.")
        raise ValueError(
            f"{p.name}: unrecognised GSAS HTYPE {htype!r} — this reader reads "
            f"PNTR (powder neutron time-of-flight) only. "
            f"{', '.join(sorted(_HTYPE_REFUSALS))} are recognised and refused "
            f"by name; this is not one of those either, so what this file's "
            f"ICONS record holds is not established at all.")

    l1 = next((_one_float(d, "FPATH1", p) for b, n, d in records
               if n.strip() == "FPATH1"), None)

    # {bank number: [(record name as written, data)]}.  The name keeps its
    # blanks — ``PRCF 1`` and ``PRCF1 `` are different records and the blanks
    # are what says so (§ the module docstring) — so the list is walked rather
    # than keyed on a normalised name that would merge the two spellings.
    by_bank: dict[int, list[tuple[str, str]]] = {}
    for bank, name, data in records:
        if not bank:
            continue
        try:
            k = int(bank)
        except ValueError:
            continue
        by_bank.setdefault(k, []).append((name, data))
    if not by_bank:
        raise ValueError(
            f"{p.name}: HTYPE {htype} is a time-of-flight file, and it carries "
            f"no per-bank INS record at all — no bank's DIFC/DIFA/ZERO to read")

    out: dict[int, Instrument] = {}
    dropped: set[str] = set()
    for k in sorted(by_bank):
        rows = by_bank[k]

        def named(record: str, rows=rows) -> list[str]:
            """Every data field-block of ``rows`` whose record name is ``record``."""
            return [d for n, d in rows if n.strip() == record]

        icons = named("ICONS")
        if len(icons) != 1:
            raise ValueError(
                f"{p.name}: bank {k} has {len(icons)} ICONS records, not "
                f"one — DIFC/DIFA/ZERO declared more than once (or not at all) "
                f"is ambiguous, not a richer calibration")
        fields = icons[0].split()
        if len(fields) != 3:
            raise ValueError(
                f"{p.name}: bank {k}'s ICONS record has {len(fields)} fields "
                f"({fields!r}), not the 3 (DIFC DIFA ZERO) a PNTR bank carries "
                f"(Larson & Von Dreele, LAUR 86-748, GSAS Technical Manual "
                f"p. 141). Reading a subset would be a guess about which is "
                f"missing")
        try:
            difc, difa, zero = (float(f) for f in fields)
        except ValueError:
            raise ValueError(
                f"{p.name}: bank {k}'s ICONS record holds a token that is not "
                f"a number ({fields!r}); the three fields are DIFC, DIFA and "
                f"ZERO and all three are numeric in every real file") from None

        bnkpar = named("BNKPAR")
        if not bnkpar:
            raise ValueError(
                f"{p.name}: bank {k} has no BNKPAR record, so its fixed "
                f"scattering angle is not stated. DIFC alone does not give it "
                f"back — DIFC = (m_N/h)(L1 + L2)·2 sin(theta) is one number "
                f"from two — and a TOF bank without its angle cannot carry an "
                f"absorption or a Lorentz correction later")
        geom = bnkpar[0].split()
        if len(geom) < 2:
            raise ValueError(
                f"{p.name}: bank {k}'s BNKPAR record has {len(geom)} field(s) "
                f"({geom!r}); its first two are the secondary flight path in "
                f"metres and the bank's 2θ in degrees, and both are needed")
        l2, two_theta = float(geom[0]), float(geom[1])

        spectrum = _incident_spectrum(named, p, k)
        source = TOFSource(difc=difc, difa=difa, tzero=zero,
                           two_theta_bank_deg=two_theta,
                           l1_m=l1, l2_m=l2,
                           incident_spectrum=spectrum)
        # The ``PRCF`` blocks, read *before* the Instrument is built rather
        # than reported after it: since T-1d one layout is read into a
        # ``ProfileTOF`` and a profile is a constructor argument, so the walk
        # cannot be inside the ``diagnostics is not None`` guard the report
        # used to live in — what a reader *returns* must not depend on whether
        # anyone asked it to explain itself.
        prcf_notes: list[tuple[str, str, str, str, bool]] = []
        profile: ProfileTOF | None = None
        prcf = [n for n, _ in rows if n.strip().startswith("PRCF")]
        headers = sorted(_prcf_headers(prcf))
        for header in headers:
            head_row = next(d for n, d in rows if n.rstrip() == header)
            parts = head_row.split()
            kind = parts[0] if parts else "?"
            ncoef = parts[1] if len(parts) > 1 else "?"
            read, note = _read_prcf1(rows, header, kind, ncoef, headers)
            if read is not None:
                profile = read
            prcf_notes.append((header, kind, ncoef, note, read is not None))
        instrument = Instrument.tof_neutron_bank(
            difc=source.difc.value, difa=source.difa.value,
            tzero=source.tzero.value, two_theta_bank_deg=two_theta,
            l1_m=l1, l2_m=l2, profile=profile)
        # Attached before ``_freeze`` rather than passed through
        # ``tof_neutron_bank`` — that constructor keeps its four-constant
        # signature — and *before* rather than after so the same walk that
        # fixes DIFC fixes these.  They arrive fixed anyway; relying on that
        # would make the ordering load-bearing and invisible.
        instrument.source.incident_spectrum = spectrum
        _freeze(instrument)
        out[k] = instrument

        if diagnostics is not None:
            for header, kind, ncoef, note, read in prcf_notes:
                diagnostics.append(Diagnostic(
                    level="info",
                    code=("GSAS_IPARM_PROFILE_READ" if read
                          else "GSAS_IPARM_PROFILE_DECLINED"),
                    message=(
                        f"{p.name}: bank {k}'s {header.strip()} record declares "
                        f"GSAS TOF profile function {kind} with {ncoef} "
                        f"coefficients — "
                        f"{_PRCF_TYPES.get(kind, 'a profile function this reader has no description of')}"
                        f". {note}. "
                        f"The bank's DIFC/DIFA/ZERO calibration was read and "
                        f"is what converts this bank's flight times to "
                        f"d-spacings"),
                    where=[f"bank {k}", "instrument.source.profile_tof"],
                    suggestion=(
                        ("check the coefficients against the bank's own "
                         "resolution before refining: the layout is "
                         "corroborated by physics and by GSAS-II's reader, "
                         "not stated by the manual")
                        if read else
                        "declare the profile by hand on "
                        "instrument.source.profile_tof, or export the bank's "
                        "parameters from GSAS-II as a .instprm, whose keys "
                        "are named")))
            dropped.update(n.strip() for n, _ in rows
                           if n.strip() and not n.strip().startswith("PRCF")
                           and n.strip() not in _READ_RECORDS
                           and not n.strip().startswith(("ICOFF", "IECOF")))

    if diagnostics is not None and dropped:
        diagnostics.append(Diagnostic(
            level="info", code="GSAS_IPARM_FIELD_DROPPED",
            message=(
                f"{p.name}: the records {', '.join(sorted(dropped))} were not "
                f"read. IECOR is the correlation matrix of the "
                f"incident-spectrum coefficients, and what GSAS does with it "
                f"is reweight every profile point for the uncertainty in the "
                f"calculated incident intensity (Larson & Von Dreele, LAUR "
                f"86-748, GSAS Technical Manual p. 128); this package's weights "
                f"are the data's own sigma, so a covariance whose only consumer "
                f"is a reweighting scheme nothing here performs would be "
                f"carried and never read. The per-coefficient esds beside it "
                f"(IECOF) *are* kept, on each coefficient's stderr. BNKNAM, "
                f"MFIL and HEAD are labels"),
            where=sorted(dropped)))
    return out


def _incident_spectrum(named, p: Path, bank: int) -> IncidentSpectrum:
    """One bank's ``I ITYP``/``ICOFF``/``IECOF`` block as an
    :class:`~rietx.schemas.instrument.IncidentSpectrum`.

    ``I ITYP`` carries the function number and the flight-time window the
    spectrum was fitted over, **in milliseconds** — the one place in this track
    where the unit is not microseconds, converted here so nothing downstream
    has to remember (the same direction GSAS-II converts it,
    ``GSASIIfiles``: ``float(s[1])*1000.``).

    ``ICOFF`` is always three records of four numbers, i.e. twelve slots,
    whatever the type; types 1 and 2 use eleven, so the twelfth is a slot the
    function does not read.  **A non-zero value in an unread slot is refused**
    rather than discarded: it is the one observable sign that the layout is not
    what the ``ITYP`` says it is, and dropping it silently is how a file gets
    read as a different file.

    No block at all — which is what ISIS GEM writes, ``ITYP 0`` and nothing
    else — gives the default container, i.e. no spectrum.  A file with *no*
    ``I ITYP`` record at all gives the same, and that is a real difference from
    "ITYP 0 declared": both mean the reader applies nothing, and only the first
    is a statement by the file.  They are not distinguished here because
    nothing downstream can act on the distinction.
    """
    ityp = named("I ITYP")
    if not ityp:
        return IncidentSpectrum()
    if len(ityp) != 1:
        raise ValueError(
            f"{p.name}: bank {bank} has {len(ityp)} 'I ITYP' records, not one — "
            f"which incident-spectrum function this bank carries is declared "
            f"more than once (or not at all), which is ambiguous rather than a "
            f"richer declaration")
    fields = ityp[0].split()
    if len(fields) < 3:
        raise ValueError(
            f"{p.name}: bank {bank}'s I ITYP record has {len(fields)} field(s) "
            f"({fields!r}); its first three are the function number and the "
            f"flight-time window in milliseconds the spectrum was fitted over, "
            f"and all three are present in every real file")
    try:
        itype = int(fields[0])
        t_lo_ms, t_hi_ms = float(fields[1]), float(fields[2])
    except ValueError:
        raise ValueError(
            f"{p.name}: bank {bank}'s I ITYP record holds a token that is not a "
            f"number ({fields[:3]!r}); the three fields are the function "
            f"number and the two window bounds in milliseconds") from None
    # A fourth field is present in every LANSCE file measured (a large integer,
    # 37556 on bank 1 of run 7245) and GSAS-II reads only the first three.
    # What it counts is not stated in the manual, so it is left where it is
    # rather than given a name this reader made up.

    if itype == 0:
        return IncidentSpectrum(tof_min_us=t_lo_ms * 1000.0,
                                tof_max_us=t_hi_ms * 1000.0)
    want = COEFFICIENT_COUNTS.get(itype)
    if want is None:
        raise ValueError(f"{p.name}: bank {bank}: {_unknown_type_message(itype)}")

    values = _spectrum_block(named, "ICOFF", p, bank, itype)
    esds = _spectrum_block(named, "IECOF", p, bank, itype)
    if esds is not None and len(esds) != len(values or ()):
        raise ValueError(
            f"{p.name}: bank {bank} declares {len(values or ())} ICOFF "
            f"coefficients and {len(esds)} IECOF esds. The two blocks are the "
            f"same twelve slots written twice and a mismatch means one of them "
            f"was truncated")
    if values is None:
        raise ValueError(
            f"{p.name}: bank {bank} declares ITYP {itype} "
            f"({SPECTRUM_TYPES[itype]}) and carries no ICOFF record. A "
            f"non-zero ITYP without its coefficients is a spectrum that cannot "
            f"be evaluated; ITYP 0 is how a file says there is none")

    extra = [(i, v) for i, v in enumerate(values[want:], start=want + 1)
             if v != 0.0]
    if extra:
        raise ValueError(
            f"{p.name}: bank {bank} declares ITYP {itype}, which uses {want} "
            f"coefficients, and its ICOFF block carries a non-zero value in "
            f"slot(s) the function does not read: "
            f"{', '.join(f'P{i} = {v!r}' for i, v in extra)}. GSAS writes ICOFF "
            f"as three records of four numbers whatever the type, so the unused "
            f"slots are zero in every file where the type and the block agree; "
            f"a number there says this block is not the layout ITYP {itype} "
            f"describes, and reading the first {want} anyway would be a guess")

    coefficients = [
        Parameter(value=float(v), vary=False,
                  stderr=None if esds is None else float(esds[i]))
        for i, v in enumerate(values[:want])]
    return IncidentSpectrum(itype=itype, coefficients=coefficients,
                            tof_min_us=t_lo_ms * 1000.0,
                            tof_max_us=t_hi_ms * 1000.0)


def _spectrum_block(named, prefix: str, p: Path, bank: int,
                    itype: int) -> list[float] | None:
    """``ICOFF1``…``ICOFF3`` (or the ``IECOF`` twin) concatenated, or ``None``.

    Read by *sequence tag* rather than by position in the file, and the records
    are required to be the consecutive run ``1, 2, 3, …`` from 1: a file
    missing ``ICOFF2`` would otherwise silently shift four coefficients into
    the wrong slots, and every coefficient of a spectrum is a different power
    of the flight time.
    """
    rows = {}
    for i in range(1, 10):
        block = named(f"{prefix}{i}")
        if not block:
            continue
        if len(block) != 1:
            raise ValueError(
                f"{p.name}: bank {bank} has {len(block)} {prefix}{i} records, "
                f"not one")
        rows[i] = block[0]
    if not rows:
        return None
    # Every tag from 1 to the highest present, with none missing.  Scanned to
    # the end rather than stopped at the first gap: stopping there would report
    # a *short* block, which is a different and less useful complaint about the
    # same file, and the count would look like a truncation rather than a hole.
    if any(i not in rows for i in range(1, max(rows) + 1)):
        raise ValueError(
            f"{p.name}: bank {bank}'s {prefix} records are not the consecutive "
            f"run 1…{max(rows)} — {sorted(rows)} is what the file carries, and "
            f"a gap would shift the coefficients into the wrong slots, every "
            f"one of which is a different power of the flight time")
    out: list[float] = []
    for i in sorted(rows):
        try:
            out.extend(float(f) for f in rows[i].split())
        except ValueError:
            raise ValueError(
                f"{p.name}: bank {bank}'s {prefix}{i} record holds a token "
                f"that is not a number ({rows[i].split()!r})") from None
    want = COEFFICIENT_COUNTS[itype]
    if len(out) < want:
        raise ValueError(
            f"{p.name}: bank {bank} declares ITYP {itype}, which uses {want} "
            f"coefficients, and its {prefix} block holds {len(out)}. A short "
            f"block is refused rather than padded: which end the missing "
            f"coefficients belong to is not stated anywhere")
    return out


def _one_float(data: str, name: str, p: Path) -> float:
    fields = data.split()
    if len(fields) != 1:
        raise ValueError(
            f"{p.name}: the {name} record has {len(fields)} fields "
            f"({fields!r}), not the one number it states")
    return float(fields[0])


# ---------------------------------------------------------------------------
# GSAS-II .instprm
# ---------------------------------------------------------------------------

#: The first line of a GSAS-II instrument-parameter file, verbatim, and the
#: only thing that recognises the format: it is otherwise a bare ``key:value``
#: list that any number of things could be.
_INSTPRM_MARKER = "#GSAS-II instrument parameter file"

#: ``Type`` values.  ``PNT`` is powder neutron time-of-flight; the others are
#: GSAS-II's constant-wavelength codes and belong to a different reader.
_INSTPRM_TYPE_PNT = "PNT"
_INSTPRM_TYPE_REFUSALS: dict[str, str] = {
    "PXC": "powder constant-wavelength X-ray",
    "PNC": "powder constant-wavelength neutron",
    "PNB": "powder neutron with a Bragg-edge parameterisation",
    "PXE": "powder energy-dispersive X-ray",
}

#: GSAS-II's TOF key → where it lands.  Every one of these is a *named* key, so
#: unlike the GSAS-I ``PRCF`` block there is nothing to infer from position and
#: the profile is read rather than declined.  The width laws GSAS-II evaluates
#: (``GSASIImath.getTOFsig``/``getTOFgamma``/``getTOFbeta``/``getTOFalpha``) are
#: what fixes which of its letters is which power of d:
#: σ² = sig-0 + sig-1·d² + sig-2·d⁴ (+ sig-q·d), γ = Z + X·d + Y·d²,
#: β = beta-0 + beta-1/d⁴ (+ beta-q/d²), α = alpha/d — so its lone ``alpha`` is
#: a **1/d** coefficient and belongs on ``alpha1``, and its ``Z``/``X``/``Y``
#: are the d⁰/d¹/d² Lorentzian terms.
_INSTPRM_PROFILE: dict[str, str] = {
    "alpha": "alpha1", "beta-0": "beta0", "beta-1": "beta1",
    "sig-0": "sig0", "sig-1": "sig1", "sig-2": "sig2",
    "Z": "gam0", "X": "gam1", "Y": "gam2",
}

#: Keys GSAS-II carries that :class:`~rietx.schemas.instrument.ProfileTOF` has
#: no term for, with what each one is.  Dropped at their identity (0) with a
#: diagnostic and **refused when non-zero**, the rule ``read_gsas_prm`` states:
#: a value at the model's identity changes nothing, and a value away from it
#: changes every peak in the pattern.
_INSTPRM_UNMAPPED: dict[str, str] = {
    "beta-q": "GSAS-II's 1/d² term of beta",
    "sig-q": "GSAS-II's d¹ term of sigma²",
    "Azimuth": "the detector bank's azimuthal angle in degrees",
}


def read_gsas2_instprm(path: str | Path, *,
                       diagnostics: list[Diagnostic] | None = None,
                       ) -> Instrument:
    """A GSAS-II ``.instprm`` time-of-flight bank, as a **frozen** Instrument.

    One bank per file — that is what GSAS-II writes — so this returns a single
    :class:`~rietx.schemas.instrument.Instrument` where
    :func:`read_gsas_tof_iparm` returns one per bank.

    All four calibration constants are read, ``difB`` included.  That fourth
    term is the reason this reader exists rather than a three-key one:
    GSAS-II's own position relation is
    ``TOF = difC·d + difA·d² + difB/d + Zero`` (``GSASIIlattice.Dsp2pos``),
    while the GSAS manual and Mantid both document three terms, so a reader
    built to the documented relation would drop a non-zero ``difB``
    **silently** and put every peak of that project in the wrong place.

    ``fltPath`` is GSAS-II's **total** flight path L₁ + L₂, which
    :class:`~rietx.schemas.instrument.TOFSource` cannot store as either of its
    two legs — the file does not say where the sample is — so it is reported
    as dropped with its value rather than assigned to one of them.  ``Bank``
    is likewise reported and not used: the Magnetic-V tutorial's own
    ``Bank 2.instprm`` and ``Bank 4.instprm`` both say ``Bank:1.0``, so the key
    is not a reliable identifier and the file name is not the file's to
    promise.
    """
    p = Path(path)
    text = p.read_text(encoding="utf-8", errors="ignore")
    lines = text.splitlines()
    if not lines or not lines[0].startswith(_INSTPRM_MARKER):
        raise ValueError(
            f"{p.name}: not a GSAS-II instrument-parameter file — its first "
            f"line is not {_INSTPRM_MARKER!r}. The format is otherwise a bare "
            f"key:value list, so that marker is the only thing that "
            f"establishes what this file is")
    entries: dict[str, str] = {}
    for raw in lines[1:]:
        line = raw.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, _, value = line.partition(":")
        entries[key.strip()] = value.strip()

    kind = entries.get("Type", "").upper()
    if kind != _INSTPRM_TYPE_PNT:
        what = _INSTPRM_TYPE_REFUSALS.get(kind)
        if what is not None:
            raise ValueError(
                f"{p.name}: Type {kind} is {what}, and this reader reads PNT "
                f"(powder neutron time-of-flight) only — a constant-wavelength "
                f"file states a wavelength where this one states difC/difA/"
                f"difB/Zero")
        raise ValueError(
            f"{p.name}: unrecognised GSAS-II instrument Type {kind!r} — this "
            f"reader reads PNT (powder neutron time-of-flight) only. "
            f"{', '.join(sorted(_INSTPRM_TYPE_REFUSALS))} are recognised and "
            f"refused by name; this is not one of those either, so what this "
            f"file's keys mean is not established at all")

    def number(key: str, *, required: bool = False) -> float | None:
        if key not in entries:
            if required:
                raise ValueError(
                    f"{p.name}: a PNT instrument-parameter file states no "
                    f"{key!r}, and without it this bank's flight times cannot "
                    f"be converted to d-spacings at all")
            return None
        try:
            return float(entries[key])
        except ValueError:
            raise ValueError(
                f"{p.name}: {key} is {entries[key]!r}, which is not a number") \
                from None

    two_theta = number("2-theta", required=True)
    instrument = Instrument.tof_neutron_bank(
        difc=number("difC", required=True),
        difa=number("difA") or 0.0,
        tzero=number("Zero") or 0.0,
        difb=number("difB") or 0.0,
        two_theta_bank_deg=float(two_theta))
    profile = instrument.source.profile_tof
    for key, field in _INSTPRM_PROFILE.items():
        value = number(key)
        if value is None:
            continue
        # The variance floor (:class:`ProfileTOF`) is a *schema* bound, so
        # assigning past it raises pydantic's own message — and a reader owes
        # a ValueError naming the file, never its parser's exception
        # (``io/CLAUDE.md`` § Dispatch).  Refused rather than clipped for the
        # reason the unmapped keys below are: GSAS-II puts no sign constraint
        # on ``sig-1``/``sig-2``, so a file carrying a negative one describes a
        # model this container cannot hold, and clipping it to zero would
        # change every peak width in the pattern silently.
        if field.startswith("sig") and value < 0.0:
            raise ValueError(
                f"{p.name}: {key} is {value!r}, and it is a Gaussian "
                f"**variance** coefficient of σ²(d) = sig-0 + sig-1·d² + "
                f"sig-2·d⁴. ProfileTOF floors all three at zero, because a "
                f"free coefficient walking negative killed a real refinement "
                f"at compile time mid-plan; GSAS-II puts no such constraint "
                f"on them, so this file's model is one rietx cannot hold "
                f"rather than one it mis-read. Clipping it to zero would "
                f"change every peak width in this bank without saying so")
        getattr(profile, field).value = value

    for key, what in _INSTPRM_UNMAPPED.items():
        value = number(key)
        if value:
            raise ValueError(
                f"{p.name}: {key} is {value!r}, not 0 — it is {what}, and "
                f"ProfileTOF has no term for it. A value at 0 changes nothing "
                f"and is dropped; a value away from 0 moves or reshapes every "
                f"peak in the pattern, so it is refused rather than discarded")

    _freeze(instrument)
    if diagnostics is not None:
        unmapped = sorted(k for k in _INSTPRM_UNMAPPED if k in entries)
        extra = sorted(set(entries) - set(_INSTPRM_PROFILE) - set(_INSTPRM_UNMAPPED)
                       - {"difC", "difA", "difB", "Zero", "2-theta", "Type"})
        if unmapped or extra:
            diagnostics.append(Diagnostic(
                level="info", code="GSAS2_INSTPRM_FIELD_DROPPED",
                message=(
                    f"{p.name}: {', '.join(unmapped + extra)} "
                    f"{'was' if len(unmapped + extra) == 1 else 'were'} not "
                    f"carried onto the Instrument. "
                    + "; ".join(f"{k} = {entries[k]} ({_INSTPRM_UNMAPPED[k]}, "
                                f"at its identity)" for k in unmapped)
                    + ("; " if unmapped and extra else "")
                    + "; ".join(f"{k} = {entries[k]}" for k in extra)
                    + ". fltPath is the *total* flight path L1 + L2 and the "
                      "file does not say where the sample sits, so it is not "
                      "assigned to either leg; Bank is not a reliable "
                      "identifier (the Magnetic-V tutorial ships two banks "
                      "both declaring Bank:1.0)"),
                where=unmapped + extra))
    return instrument


def _freeze(instrument: Instrument) -> None:
    """Every parameter of a TOF instrument held fixed.

    An instrument-parameter file is a calibration refined against a standard,
    which is what :func:`rietx.io.instrument_profile.load_instrument_profile`'s
    contract says and the reason it says it: freeing DIFC beside a free cell
    re-opens the same flat direction a free wavelength does, one axis over.
    """
    source = instrument.source
    for name in ("difc", "difa", "tzero", "difb"):
        getattr(source, name).vary = False
    profile: ProfileTOF = source.profile_tof
    for field in ProfileTOF.model_fields:
        param = getattr(profile, field)
        if isinstance(param, Parameter):
            param.vary = False
    # The incident spectrum is a calibration too — GSAS refined it against a
    # vanadium run and wrote its esds in the same file — and it has a second
    # reason to start held that DIFC does not: a smooth envelope in λ is
    # degenerate with an isotropic displacement parameter, so freeing it
    # against an unknown structure trades one wrong answer for another.
    for param in source.incident_spectrum.coefficients:
        param.vary = False

"""GSAS raw powder data — the FXYE / ESD / STD bank formats.

Spec: Larson & Von Dreele (2004), *GSAS — General Structure Analysis System*,
LAUR 86-748, §"Powder data file formats".

Recognised by its ``BANK`` record rather than by suffix: the format is written
with a zoo of extensions (``.fxye``, ``.gsas``, ``.gda``, ``.xra``, ``.raw``, …)
and the record is unambiguous.  That is also what keeps it disjoint from the
Bruker binary ``.raw``, which is claimed by magic bytes — a GSAS file named
``.raw`` still reaches this reader, and a Bruker file named ``.gsas`` does not.

**The bank record makes two independent declarations and they are read as two.**
The **bintype** says how the x axis is computed; the **type flag** (``STD``,
``ESD``, ``FXYE``, and also ``ALT`` and ``FXY``) says how one data record is laid
out.  Nothing couples them — an ``ESD`` record holds (intensity, esd) pairs
whichever bintype it sits under — so a reader that lets one decide the other
returns a wrong pattern rather than a refusal.  This one did: a non-``CONS`` bank
was *forced* into the FXYE branch behind a divisible-by-three check on its value
count, which a ``RALF`` bank carrying ESD data passes whenever its pair count is
a multiple of three.

**``CONS``/``CONST`` is the only bintype whose x axis is 2θ, so it is the only
one read; every other one is refused by name.**  The two spellings are one rule
— a start angle and a step, both in centidegrees — and that rule is what the
centidegree fold below rests on.  The manual's other eight put something else
entirely on the x axis: a flight time (``RALF``, ``SLOG``, ``LOG6``,
``TIME_MAP``), a d-spacing (``COND``), a Q (``CONQ``), a detector position
(``LPSD``) or a photon energy (``EDS``).  Refusing them is the third row of the
axis policy (``io/CLAUDE.md`` § The axis is never trusted) reached through the
bintype instead of through an axis label — *recognisably something else, so raise
naming what the file actually holds* — and it is a matter of **scope** rather
than of evidence: ``PatternData`` carries 2θ, so supporting any of these is a
schema change before it is a parser change.

The match is **exact and never a prefix**, because ``COND`` and ``CONQ`` share
three characters with ``CONS`` and are two of the axes this refuses.

Real files are not scarce, which is why none of this is hypothetical: GSAS-II's
own tutorial data ships ``SLOG`` and ``RALF`` banks, and on the code this
replaces several read as plausible wrong 2θ patterns — an ISIS PEARL ``RALF``
bank came back as a flawless-looking 2528-point scan from 15.00° to 194.88°,
which no caller could have told from a real one.  **The reference implementation
has the same bug**: the manual says an FXYE x column is *"centidegrees for CW
data or microseconds for TOF data"*, and GSAS-II's ``G2pwd_fxye`` divides by 100
unconditionally, with no bintype branch anywhere in the module.  So "implement it
the way GSAS-II does" was never available — it would have shipped this exact
wrong answer.

**And only ``STD``/``ESD``/``FXYE`` records are read, with every other flag
refused by name.**  ``STD`` is also what a bank that states *no* flag means —
four obtainable real files write the record that way — and that default is why an
unrecognised flag was silent: an ``ALT`` or ``FXY`` bank fell through to
counts-only with an axis synthesized from ``c1``/``c2``, so its own x column
entered the intensity array and a wrong axis took its place.  The symptom was
visible in the output all along: the pattern came back tagged ``gsas-alt``, the
reader having used the flag as a label rather than as a decision.

Neither layout is *implemented*, and here the reason really is the fixture.
Every ``ALT`` file obtainable is also a ``RALF`` bank, so it is refused one
decision earlier for its bintype and cannot exercise an ``ALT`` reader at all;
and no ``FXY`` file was found anywhere.  A record layout is exactly the kind of
fact a fixture is for, so both are named and declined rather than written against
a description.

**And the three layouts that are read differ in whether a field has a position
or only a separator** — behaviour, not style, because it decides whether a
full-width value can fuse with its neighbour:

- **ESD** is positional, written by a Fortran ``FORMAT``: ten 8-character
  fields to an 80-column record, five (intensity, esd) pairs.  Three
  descriptions agree and so does every real file (§ ``_esd_fields``).
- **FXYE** / **FXY** are free-format, one point to a line, and are read by
  splitting on whitespace.  That is the spec's word (GSAS-II splits them) and
  the fixtures corroborate it: ``mg090.fxye``'s tokens are 9 and 10 characters
  wide and its lines run 31–34 characters, so 8-character slicing would
  destroy it.
- **STD** is positional too, but its 8-character field is a 2-character repeat
  count followed by a 6-character value, so a value can never reach the field's
  left edge and **fusion is structurally impossible** in a bank GSAS could have
  written.  Whitespace splitting therefore reads an uncompressed STD bank
  exactly, which is what ``FAP.XRA`` is; the compressed variant is a separate
  question no obtainable file answers, and it is not silently guessed at here.
"""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np

from ...schemas.common import Diagnostic
from ...schemas.pattern import PatternData
from .base import PatternFormat, ascending, head, pattern_data

#: The bintypes read: a start angle and a step, both in centidegrees.  The
#: manual's token is ``CONS`` and real files write both spellings; they are the
#: same rule, so they are one entry's worth of fact rather than two.  Matched
#: **exactly** — ``COND`` and ``CONQ`` below share three characters with these
#: and are different axes, so a prefix test would swallow them.
_ANGLE_BINTYPES = frozenset({"CONS", "CONST"})

#: Every other bintype the manual defines, and what each one actually puts on the
#: x axis.  None is 2θ, which is the whole reason they are refused: they are out
#: of **scope** for a package whose ``PatternData`` carries 2θ, not short of
#: evidence — real files are abundant (§ the module docstring).  Sources for the
#: descriptions, since a wrong one in a refusal is still a wrong statement: the
#: bintype list and each definition are the GSAS manual's (LAUR 86-748,
#: §"Powder data file formats"), corroborated by real bank records where one was
#: obtainable.  ``SLOG``'s third coefficient is 4e-4 … 3e-3 across four
#: independent files and the channel ratio matches it, so it really is Δt/t and
#: not Δt.  ``RALF`` is deliberately *not* called log-step: it is constant-width
#: at short flight times and only pseudo-Δt/t beyond a coefficient that says
#: where.  A ``TIME_MAP`` bank carries a map *number* where the others carry
#: coefficients (``BANK 1 7550 755 TIME_MAP 1 STD``), so its steps are tabulated
#: elsewhere in the file.  And ``EDS`` is energy-dispersive, not time-of-flight,
#: which is why this is one table of eight rather than a "TOF" set.
_NON_ANGLE_BINTYPES = {
    "COND": "a constant-Δd binning, so its x axis is a d-spacing",
    "CONQ": "a constant-ΔQ binning, so its x axis is a Q",
    "EDS": "an energy-dispersive binning, so its x axis is a photon energy",
    "LOG6": "a logarithmic time-of-flight binning for the Los Alamos Model 6 "
            "clock, so its x axis is a flight time",
    "LPSD": "a linear position-sensitive-detector binning, so its x axis is a "
            "detector position",
    "RALF": "a time-of-flight binning (constant step at short flight times, "
            "pseudo-constant Δt/t beyond), so its x axis is a flight time",
    "SLOG": "a constant-Δt/t (log-step) time-of-flight binning, so its x axis "
            "is a flight time",
    "TIME_MAP": "a time-of-flight binning whose step table is a separate "
                "TIME_MAP record elsewhere in the file",
}

#: The record layouts read.  A bank that states **no** flag is legal and means
#: ``STD``; that default is the reason an unrecognised flag was silent, since
#: falling through to it looks exactly like a file that declared nothing.
_TYPE_FLAGS = frozenset({"STD", "ESD", "FXYE"})

#: The type flags named and refused, and what each one holds.  Both are a layout
#: this parser does not have, and both were read as *counts only* by the STD
#: branch — an ``ALT`` record's x and error columns entering the intensity array,
#: an ``FXY`` record's x column doing the same while the axis is synthesized from
#: ``c1``/``c2`` in its place.  Neither is implemented, and here the reason is
#: the fixture: every obtainable ``ALT`` file is also a ``RALF`` bank, so it is
#: refused one decision earlier and cannot exercise an ``ALT`` reader at all, and
#: no ``FXY`` file was found anywhere.  The shapes are *known* — the manual gives
#: ALT as four ``(x, intensity, error)`` points to an 80-column record on a
#: 20-character stride, ``NREC = ceil(NCHAN/4)``, and FXY as two free-format
#: values — and knowing a shape is still not having a fixture to test it against.
#: Which matters here more than usual: for ALT the manual's own Fortran format
#: and GSAS-II's scale factors **disagree**, by 100× on x and 10× on y and esd,
#: so there is no reading of the two sources that is safe without a file.
_UNIMPLEMENTED_FLAGS = {
    "ALT": "an x, intensity and error triple on a fixed stride",
    "FXY": "an x and intensity pair with no esd",
}


_SNIFF_BANK_RE = re.compile(r"^BANK\s+\d+", re.M)
_SNIFF_TIME_MAP_RE = re.compile(r"^TIME_MAP", re.M)

#: A ``TIME_MAP`` step table is written *before* the bank it feeds, and a long
#: one pushes the first ``BANK`` record past the 4 kB ``head`` window the sniff
#: reads — a real HIPD@LANSCE file (``vnb5053.dat`` from the GSAS distribution's
#: own examples) carries a 71-row ``(10I8)`` table and its first bank sits at
#: byte 6068, so the sniff missed it and the file fell to the ``xy`` catch-all,
#: which read its fixed-format records as columns and refused with the wrong
#: cause (a 2θ axis the file never had).  The ``TIME_MAP`` token is itself
#: GSAS-shaped evidence and it *does* land in the first 4 kB (it opens the
#: table), so a file showing it is read once more up to this bound to look past
#: the table for the bank.  This is the ``.chi`` count-check discipline
#: (``io/CLAUDE.md`` § Dispatch): an extra read only behind a shape gate a random
#: pattern never trips, never a widened window for every file.  A table larger
#: than this stays unsniffed — the same bounded tradeoff the 4 kB window itself
#: makes, one order of magnitude further out.
_GSAS_TIME_MAP_SCAN_BYTES = 64 * 1024


def looks_gsas(p: Path) -> bool:
    h = head(p)
    if _SNIFF_BANK_RE.search(h.text):
        return True
    # No bank in the first 4 kB, but a TIME_MAP table — which is what pushes the
    # bank past that window — leaves its own token there.  One more bounded read.
    if _SNIFF_TIME_MAP_RE.search(h.text):
        return bool(_SNIFF_BANK_RE.search(head(p, _GSAS_TIME_MAP_SCAN_BYTES).text))
    return False


def read_gsas(path: str | Path, *,
              diagnostics: list[Diagnostic] | None = None) -> PatternData:
    """GSAS raw powder data, a CONS/CONST bank in its STD, ESD or FXYE flavour.

    The bintype and the type flag are two independent decisions and are taken
    as two: ``_check_bintype`` settles the x axis, the flag the record layout.
    """
    p = Path(path)
    lines = p.read_text(encoding="utf-8", errors="ignore").splitlines()
    # The bank record is found and its *bintype* read from a loose header match
    # — bank number, channel count, record count, bintype — because that prefix
    # is common to every bintype while the coefficients that follow are not: a
    # CONS bank writes a start angle and a step, but a TIME_MAP bank writes a
    # lone map number.  The strict CONS parse below needs two coefficients, so
    # matching *first* with it would skip a TIME_MAP bank entirely and report a
    # missing BANK record — the wrong cause again — for a file that plainly has
    # one.  So the axis decision is taken off the header, before the layout.
    bank_head_re = re.compile(r"^BANK\s+(\d+)\s+(\d+)\s+(\d+)\s+(\w+)")
    bank_re = re.compile(
        r"^BANK\s+(\d+)\s+(\d+)\s+(\d+)\s+(\w+)\s+([\d.Ee+-]+)\s+([\d.Ee+-]+)"
        # the flag is a keyword and must begin with a letter: it is the *last*
        # field, after up to four bintype coefficients, so a record writing an
        # odd number of them leaves a coefficient where the flag would be, and
        # ``\w*`` captured that digit as a flag (``BANK 1 4 4 CONST 1000 20 0``
        # tagged its pattern ``gsas-0``).  A number here is absence, not a flag.
        r"(?:\s+([\d.Ee+-]+)\s+([\d.Ee+-]+))?\s*([A-Za-z]\w*)?")
    head_m = None
    bank_line = None
    data_start = None
    for i, line in enumerate(lines):
        m = bank_head_re.match(line)
        if m:
            head_m = m
            bank_line = line
            data_start = i + 1
            break
    if head_m is None:
        raise ValueError(f"no BANK record found in {p}")

    nchan = int(head_m.group(2))
    # decision one: how the x axis is computed.  Refused before the data is
    # parsed, since a bintype nobody can read is not made readable by its rows —
    # and refused off the header, so a bintype whose coefficient count is not the
    # CONS two (TIME_MAP writes one) is named for what it is rather than lost as
    # an unparseable record.
    _check_bintype(head_m.group(4).upper(), p)
    # only CONS/CONST reaches here; now the strict start-angle-and-step layout
    bank = bank_re.match(bank_line)
    if bank is None:
        raise ValueError(
            f"{p.name}: this is a CONS/CONST bank but its record could not be "
            f"read for a start angle and step — {bank_line.strip()!r}")
    c1, c2 = float(bank.group(5)), float(bank.group(6))
    # decision two, and independent of the first: how one record is laid out
    type_flag = _type_flag(bank.group(9), p)

    body: list[str] = []
    for line in lines[data_start:]:
        if line.startswith("BANK"):
            break
        body.append(line)

    # An ESD bank is positional and is read as such (§ ``_esd_fields``); FXYE
    # and STD are free-format and split on whitespace.  Each flavour tokenises
    # its own body, so the ESD path — the big one — never pays for the ~99 000
    # throwaway tokens a whole-body split would build for a branch it never
    # takes.  ``_check_bintype`` above has already refused every non-2θ
    # bintype, so a bank reaching here is CONS/CONST and only the flag decides.
    if type_flag == "FXYE":
        # FXYE: explicit x column (centidegrees), then y, esd
        values = _floats([t for line in body for t in line.split()], p, type_flag)
        arr = _reshape(values, 3, p, type_flag)
        tt = arr[:, 0] / 100.0  # centidegrees → degrees
        y = arr[:, 1]
        sig = arr[:, 2]
    elif type_flag == "ESD":
        arr = _reshape(_esd_fields(body, p), 2, p, type_flag)
        tt = (c1 + c2 * np.arange(len(arr))) / 100.0
        y, sig = arr[:, 0], arr[:, 1]
    else:  # STD: counts only, Poisson esd
        values = _floats([t for line in body for t in line.split()], p, type_flag)
        y = np.array(values, dtype=np.float64)[:nchan]
        tt = (c1 + c2 * np.arange(len(y))) / 100.0
        sig = None

    n = min(len(tt), nchan) if type_flag != "FXYE" else len(tt)
    tt, y = tt[:n], y[:n]
    sigma = None
    if sig is not None:
        sig = sig[:n]
        sigma = sig.tolist() if np.any(sig > 0) else None
    # drop zero-esd leading/trailing channels (detector gaps)
    if sigma is not None:
        good = np.asarray(sigma) > 0
        tt, y = tt[good], y[good]
        sigma = np.asarray(sigma)[good].tolist()
    tt, y, sig = ascending(tt, y, sigma, path=p, fmt=GSAS, diagnostics=diagnostics)
    return pattern_data(p, tt, y, sig, source_file=p.name,
                   format=f"gsas-{type_flag.lower()}")


def _check_bintype(bintype: str, p: Path) -> None:
    """Pass a ``CONS``/``CONST`` bank; refuse any other bintype **by name**.

    This is the x-axis decision and nothing else — the type flag is read
    separately, because a bank's binning says nothing about how its records are
    packed.  Conflating the two is what let a ``RALF`` bank holding ESD pairs be
    read as three-column FXYE whenever its pair count divided by three.
    """
    if bintype in _ANGLE_BINTYPES:
        return
    what = _NON_ANGLE_BINTYPES.get(bintype)
    if what is not None:
        raise ValueError(
            f"{p.name}: this is a GSAS {bintype} bank — {what}, not a 2θ.  "
            f"CONS/CONST (a constant 2θ step) is the only bintype read, because "
            f"it is the only one whose axis is an angle: this package holds 2θ "
            f"patterns, so there is nowhere for that quantity to go, and "
            f"reading it as an angle anyway is a plausible wrong answer rather "
            f"than a near miss.  Convert the pattern to 2θ first.")
    raise ValueError(
        f"{p.name}: unrecognised GSAS bintype {bintype!r} in the bank record — "
        f"only CONS/CONST (a constant 2θ step) is read.  The manual's other "
        f"bintypes ({', '.join(sorted(_NON_ANGLE_BINTYPES))}) are recognised "
        f"and refused, each naming what its x axis holds; this is not one of "
        f"those either, so what this file's x axis means is not established at "
        f"all.")


def _type_flag(token: str | None, p: Path) -> str:
    """The record layout the bank declares; a flag not implemented **is named**.

    This is the layout decision and nothing else — the bintype is checked
    separately.  Two cases have to stay apart, and only one of them is a
    refusal:

    * **No flag at all** is legal and means ``STD``, counts only.  Real fixtures
      and the inline writers both write the record that way, so the default
      stays.
    * **A flag this parser has no layout for** used to reach that same default
      silently, so an ``ALT`` or ``FXY`` bank was read as counts-only with an
      axis synthesized from ``c1``/``c2`` — a plausible wrong pattern out of a
      file that said, in the record, exactly what it was.  The old code even
      tagged the result ``gsas-alt``: the reader knew the name and used it as a
      label rather than as a decision.
    """
    if not token:
        return "STD"
    flag = token.upper()
    if flag in _TYPE_FLAGS:
        return flag
    needs = _UNIMPLEMENTED_FLAGS.get(flag)
    if needs is not None:
        raise ValueError(
            f"{p.name}: this bank's type flag is {flag} — {needs}, which this "
            f"reader has no layout for.  Only STD, ESD and FXYE records are "
            f"read (a bank stating no flag at all is STD).  {flag} is declined "
            f"rather than guessed at: through the STD branch it would put this "
            f"file's own x column into the intensities and synthesize an axis "
            f"from the bank record in its place, which is a plausible wrong "
            f"pattern and not an error.")
    raise ValueError(
        f"{p.name}: unrecognised GSAS bank type flag {flag!r} — only STD, ESD "
        f"and FXYE records are read, and a bank stating no flag at all is STD.  "
        f"{', '.join(sorted(_UNIMPLEMENTED_FLAGS))} are recognised and refused; "
        f"this is not one of those either, so how its records are laid out is "
        f"not established at all.")


#: Width of one field of an **ESD** bank's data record, in characters.  A
#: specification fact, and three descriptions state it: the beamline that wrote
#: the files this fixes — APS 11-BM, *Data Formats*
#: (https://11bm.xray.aps.anl.gov/users/filetypes), "*the intensities and their
#: uncertainties (esd) are alternated with five pair of numbers per line (8
#: characters per number), as described in the GSAS manual*"; the manual it
#: points at, Larson & Von Dreele (2004), LAUR 86-748, §"Powder data file
#: formats"; and GSAS-II's own ``G2pwd_fxye.py``, whose ESD reader takes
#: ``S[i:i+8]`` and ``S[i+8:i+16]`` on a 16-character stride — read as a *fact*
#: from a permissively-licensed code, per ``ATTRIBUTION.md`` § Format
#: specifications, with no line of it transcribed.  The files agree
#: independently: every data record of all six real ESD/STD banks obtainable
#: here is exactly 80 characters holding exactly ten non-blank fields.
ESD_FIELD_CHARS = 8


def _esd_fields(body: list[str], p: Path) -> list[float]:
    """An ESD bank's numbers, read **positionally** rather than by separator.

    Splitting on whitespace is right until a value fills its field.  An
    intensity of 100000.0 or more occupies all eight characters, leaves no
    separating space, and fuses with the esd in front of it — real APS 11-BM
    standards patterns do this (``11BM_LaB6.raw`` line 1050 pairs an esd of
    298.5 with an intensity of 101641.3 as ``298.5101641.3``), and the line
    then yields nine numbers instead of ten.  Whichever way that lands — a
    refusal on the two dots, or a plausible wrong number on a bank whose
    values carry no decimal point — the row has lost a value and every channel
    after it is shifted.  So the field's *position* is what is read.

    Blank fields: a data record is padded with explicit zeros in every real
    file (measured on all six), so a blank field is only ever a truncated or
    short final record and is skipped rather than read as a Fortran zero —
    there is no obtainable file in which an interior field is blank, and
    inventing a datum for a hole is the one repair a reader may not make.
    """
    out: list[float] = []
    for lineno, raw in enumerate(body, start=1):
        line = raw.rstrip()
        for start in range(0, len(line), ESD_FIELD_CHARS):
            field = line[start:start + ESD_FIELD_CHARS].strip()
            if not field:
                continue
            try:
                out.append(float(field))
            except ValueError:
                raise ValueError(
                    f"{p.name}: characters {start + 1}-"
                    f"{start + ESD_FIELD_CHARS} of data record {lineno} of the "
                    f"ESD bank hold {field!r}, which is not a number — the "
                    f"record is not the {ESD_FIELD_CHARS}-character fixed "
                    "format an ESD bank is written in") from None
    return out


def _floats(tokens: list[str], p: Path, flag: str) -> list[float]:
    """``tokens`` as floats, or a refusal that names the file.

    ``float()``'s own complaint is ``could not convert string to float:
    '298.5101641.3'`` — true, and it names neither the file nor the format, so
    it reaches ``preview_pattern`` as a refusal a user cannot act on.  The
    general rule (a reader raises ``ValueError`` **naming the file**) applied
    at this parser's free-format boundary.
    """
    out: list[float] = []
    for token in tokens:
        try:
            out.append(float(token))
        except ValueError:
            raise ValueError(
                f"{p.name}: the {flag} bank holds {token!r} where a number "
                "was expected") from None
    return out


def _reshape(values: list[float], width: int, p: Path, flag: str) -> np.ndarray:
    """``values`` as N rows of ``width``, or a refusal that names the file.

    numpy's own complaint is ``cannot reshape array of size 527 into shape
    (3)`` — a true statement about an array, from a user who asked to open a
    diffraction pattern.  Converting here is the general rule (a reader raises
    ``ValueError``/``OSError`` **naming the file**) applied at this parser's own
    boundary; a truncated file is the ordinary way to reach it.
    """
    if width and len(values) % width:
        raise ValueError(
            f"{p.name}: the {flag} bank holds {len(values)} numbers, which is "
            f"not a whole number of {width}-column rows — the file is truncated "
            "or its bank record disagrees with its data")
    return np.array(values, dtype=np.float64).reshape(-1, width)


GSAS = PatternFormat(
    name="gsas",
    title="GSAS raw powder data (FXYE / ESD / STD)",
    extensions=(".fxye", ".gsas", ".gda", ".xra", ".raw"),
    sniff="a BANK record in the first 4 kB — by content, not by suffix — or, "
          "when a TIME_MAP step table (which is what pushes the first bank past "
          "that window) leaves its token there, one more bounded read further "
          "in. Only a CONS/CONST (constant 2θ step) bank holding STD, ESD or "
          "FXYE records is then read, and every time-of-flight bintype "
          "(TIME_MAP included) and every other type flag (ALT, FXY) is named "
          "and refused",
    sigma=("the third column (FXYE) or second (ESD); an STD bank — which is "
           "also what a bank stating no type flag is — carries counts only and "
           "takes the Poisson fallback"),
    matches=looks_gsas,
    read=read_gsas,
)

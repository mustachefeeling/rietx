"""Shared machinery for the pattern-format readers.

There is one module per format in this package, because a format's spec
citation, its parser, its ``sniff``/``sigma`` prose, its reader options and its
**licence fence** are one fact each and belong adjacent — ten fences in one file
drift.  What lives *here* is what more than one of them needs: the registry
entry they each construct, and the bounded head read every text sniff shares.
"""

from __future__ import annotations

import codecs
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import numpy as np

from ...schemas.common import Diagnostic
from ...schemas.pattern import PatternData


@dataclass(frozen=True)
class PatternFormat:
    """One format :func:`pxrdref.read_pattern` accepts, and how it is recognised.

    A registry rather than a chain of ``if``s inside ``read_pattern`` because
    three consumers need the *same* facts and each would otherwise restate them:
    the dispatch itself, ``capabilities()`` (which must say what this package
    can actually open — WP-1007), and a project's ``DataRef``, which records
    *which reader claimed the file* so re-opening reproduces the reader call and
    not merely the bytes (WP-1005).

    ``options`` names the reader keywords a caller may have supplied, because
    those have to be recorded and replayed too: a pdCIF holding both a ``_meas``
    and a ``_calc`` block (the NIST SRM certification files do) reads as a
    different pattern depending on ``block``.
    """

    name: str
    title: str
    #: conventional suffixes — informational except where ``sniff`` uses them
    extensions: tuple[str, ...]
    #: how the format is recognised, in words a UI can show
    sniff: str
    #: where per-point σ comes from, or how the Poisson fallback is reached
    sigma: str
    matches: Callable[[Path], bool]
    read: Callable[..., PatternData]
    options: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ReaderOption:
    """One keyword :func:`pxrdref.read_pattern` accepts, declared as data.

    Two levels exist because an option is rarely one format's — the ``scan`` of
    a multi-scan vendor file will mean the same thing in five of them — and
    because a caller should not have to know which reader will claim a file in
    order to name one.  So the *vocabulary* lives here and each
    :class:`PatternFormat` names the subset it honours.

    That split is what makes a **typo** distinguishable from an option this
    particular file's format does not take.  The first is a caller error and
    raises; the second is normal — a UI carries a value across a file change —
    and is dropped, but *reported* (``READER_OPTION_IGNORED``), because an API
    caller who passed ``scan=2`` against a single-scan format believed they had
    selected something.

    ``kind`` exists because ``DataRef.options`` is ``dict[str, str]``: a scan
    round-trips through a project as ``"2"`` and has to reach the reader as the
    integer 2.
    """

    name: str
    kind: Literal["str", "int"]
    #: what the option does, in words a UI can put beside its control
    help: str

    def coerce(self, value: Any) -> Any:
        """``value`` as this option's type, or a refusal naming the option."""
        if self.kind == "int":
            try:
                return int(value)
            except (TypeError, ValueError):
                raise ValueError(f"reader option {self.name}= takes an integer, "
                                 f"got {value!r}") from None
        return str(value)


#: Every keyword ``read_pattern`` accepts, across all formats — the allowlist.
#: A meta-test pins it equal to the union of every ``PatternFormat.options``, so
#: neither half can grow an entry the other does not know about.
READER_OPTIONS: dict[str, ReaderOption] = {
    "block": ReaderOption(
        name="block", kind="str",
        help="the data block to read, by substring match on its name — a pdCIF "
             "carrying both a _meas and a _calc block is a different pattern "
             "depending on it"),
}


def reader_options_for(fmt: PatternFormat, requested: dict[str, Any], *,
                       diagnostics: list[Diagnostic] | None = None) -> dict[str, Any]:
    """The options ``fmt`` will actually be called with — coerced and filtered.

    One authority, because three callers ask the same question and each would
    otherwise answer it slightly differently: :func:`pxrdref.read_pattern`
    before dispatching, ``Project`` when recording what the parse *used*, and
    the GUI when a staged file is re-read.  ``None`` means "not specified" and
    is dropped, so ``block=None`` still reads the first block that parses.

    A dropped option is **reported, not silent**: a GUI is free to ignore
    ``READER_OPTION_IGNORED`` (carrying a value across a change of file is what
    a form does), and an API caller who passed ``scan=2`` against a single-scan
    format is not, because they believed they had selected something.
    """
    out: dict[str, Any] = {}
    for name, value in requested.items():
        option = READER_OPTIONS.get(name)
        if option is None:
            raise ValueError(f"unknown reader option {name!r}; read_pattern takes "
                             f"{sorted(READER_OPTIONS)}")
        if value is None:
            continue
        if name not in fmt.options:
            if diagnostics is not None:
                diagnostics.append(Diagnostic(
                    level="info", code="READER_OPTION_IGNORED",
                    message=(f"{name}={value!r} was not applied: {fmt.title} takes "
                             f"{list(fmt.options) or 'no reader options'}, so the "
                             "file was read as if it had not been given"),
                    where=[name],
                    suggestion=("drop the option, or check that the file is the "
                                "format you meant to open — identify_format names "
                                "the reader that claimed it")))
            continue
        out[name] = option.coerce(value)
    return out


def multiscan_default(n_scans: int, requested: int | None, *, path: str | Path,
                      diagnostics: list[Diagnostic] | None = None) -> None:
    """Say so when scan 0 of several was taken because nobody chose.

    Reading one of a file's scans is a *choice*, and a default that only the GUI
    preview reveals leaves the API and the CLI blind.  Same rule as
    ``INDEX_SHIFT_ALLOWANCE`` one seam over: an assumed selection must never
    look like a deliberate one.  Silent when the file holds one scan (there is
    nothing to choose) or when ``scan`` was given (the choice was made).
    """
    if n_scans <= 1 or requested is not None or diagnostics is None:
        return
    diagnostics.append(Diagnostic(
        level="warning", code="PATTERN_MULTISCAN_DEFAULTED",
        message=(f"{Path(path).name} holds {n_scans} scans and none was named; "
                 f"scan 0 of {n_scans} was read. The others are not in this "
                 "pattern"),
        where=["scan"],
        suggestion=(f"pass scan=<0…{n_scans - 1}> to choose, or list_scans(path) "
                    "to see what each one is")))


#: How much of a file a *sniff* may look at.  Every text dispatch goes through
#: :func:`head`, so the cost of asking "is this yours?" is bounded no matter how
#: many formats are registered or how large the pattern is.
HEAD_BYTES = 4096

#: Byte-order marks worth recognising, longest-first.  ``utf-16`` (rather than
#: an explicit endianness) is the codec on purpose: it reads the mark to pick
#: LE or BE *and* strips it, which is what a caller decoding the whole file
#: wants.  UTF-32 is deliberately absent — no diffractometer writes it, and
#: guessing at one more encoding would buy nothing but a wrong guess.
_BOMS: tuple[tuple[bytes, str], ...] = (
    (codecs.BOM_UTF8, "utf-8-sig"),
    (codecs.BOM_UTF16_LE, "utf-16"),
    (codecs.BOM_UTF16_BE, "utf-16"),
)


@dataclass(frozen=True)
class Head:
    """The first :data:`HEAD_BYTES` of a file, read once and decoded once."""

    #: the bytes actually read, byte-order mark included
    raw: bytes
    #: :attr:`raw` decoded with :attr:`encoding`; undecodable bytes are dropped,
    #: so a *sniff* may always search it and a binary file simply matches nothing
    text: str
    #: the codec to decode the whole file with — the one the mark names, else UTF-8
    encoding: str
    #: whether a byte-order mark was actually found.  Load-bearing beyond the
    #: encoding: ASCII-range UTF-16LE is *valid* UTF-8 with interleaved NULs, so
    #: a mark is what separates "Windows vendor export" from "binary".
    bom: bool


def ascending(two_theta: Any, intensity: Any, sigma: Any = None, *,
              path: str | Path, fmt: PatternFormat | None = None,
              diagnostics: list[Diagnostic] | None = None,
              ) -> tuple[np.ndarray, np.ndarray, np.ndarray | None]:
    """``PatternData``'s strictly-increasing 2θ, or a refusal — never a guess.

    Several formats store a scan measured high→low, and the root CLAUDE.md rule
    fixes what to do about it: a silent correction is a reader's to make, and
    only where the deviation is a **report** rather than a **contradiction**.
    Applied case by case, that is the whole of this function:

    ==============================  ==============  ==========================
    deviation                       verdict         action
    ==============================  ==============  ==========================
    strictly descending             report          reverse; the measurement is
                                                    the same one, stored
                                                    backwards, and reversing is
                                                    lossless
    duplicate 2θ, equal intensity   report          drop the repeat — a format
                                                    artefact, no datum lost
    duplicate 2θ, different y       contradiction   raise: averaging invents a
                                                    datum and dropping picks one
    non-monotone (stitched ranges,  contradiction   raise: concatenate, sort or
    restarts)                                       separate is the caller's
                                                    call, not the reader's
    non-constant step               neither         nothing — SRM 660c is 24
                                                    stitched regions and legal
    ==============================  ==============  ==========================

    The non-monotone refusal names the ``scan`` option **only for a format that
    has one**, which is why it takes ``fmt``: telling someone to select a scan
    in a file that cannot hold several is a wrong instruction, not a vague one.
    """
    tt = np.asarray(two_theta, dtype=np.float64)
    y = np.asarray(intensity, dtype=np.float64)
    sig = None if sigma is None else np.asarray(sigma, dtype=np.float64)
    name = Path(path).name

    step = np.diff(tt)
    # ``<= 0`` with at least one strict descent, so that a descending scan which
    # also repeats a point is reversed and *then* meets the duplicate rule below
    # — the mirror of an ascending one, handled by the same code
    if tt.size > 1 and np.all(step <= 0) and np.any(step < 0):
        tt, y = tt[::-1], y[::-1]
        sig = None if sig is None else sig[::-1]
        step = np.diff(tt)
        if diagnostics is not None:
            diagnostics.append(Diagnostic(
                level="info", code="PATTERN_SCAN_REVERSED",
                message=(f"{name} stores its points from high 2θ to low; they "
                         "were reversed. The same measurement, stored backwards "
                         "— reversing loses nothing"),
                where=["two_theta"]))

    if tt.size > 1 and not np.all(step > 0):
        repeat = np.flatnonzero(step == 0.0)
        if repeat.size and np.all(step >= 0):
            differing = repeat[y[repeat] != y[repeat + 1]]
            if differing.size:
                i = int(differing[0])
                raise ValueError(
                    f"{name}: 2θ = {tt[i]:.6g}° appears twice with different "
                    f"intensities ({y[i]:.6g} and {y[i + 1]:.6g}), and "
                    f"{differing.size} such point(s) in all. Averaging them "
                    "would invent a datum and dropping one would pick a "
                    "measurement arbitrarily, so neither is the reader's to do")
            keep = np.ones(tt.size, dtype=bool)
            keep[repeat + 1] = False
            tt, y = tt[keep], y[keep]
            sig = None if sig is None else sig[keep]
            if diagnostics is not None:
                diagnostics.append(Diagnostic(
                    level="info", code="PATTERN_DUPLICATE_POINTS",
                    message=(f"{name} repeats {int(repeat.size)} 2θ value(s) with "
                             "the same intensity; the repeats were dropped"),
                    where=["two_theta"]))
        else:
            i = int(np.flatnonzero(step <= 0)[0])
            extra = (" — if these are separate ranges, name one with scan="
                     if fmt is not None and "scan" in fmt.options else "")
            raise ValueError(
                f"{name}: 2θ does not run in one direction — it goes "
                f"{tt[i]:.6g}° → {tt[i + 1]:.6g}° at point {i}. Concatenating, "
                "sorting or separating such ranges are three different "
                f"measurements and choosing between them is yours{extra}")

    return tt, y, sig


def looks_binary(h: Head) -> bool:
    """Whether ``h`` came from a file no text reader should try to decode.

    A NUL byte in the first :data:`HEAD_BYTES` — the test every ``file(1)``-like
    heuristic starts from, and enough here because the alternative is not "guess
    better" but "fall through to the ASCII-column reader", which is what turned
    a Bruker binary into a bare ``UnicodeDecodeError``.

    **One carve-out: a byte-order mark means text, never binary.**  ASCII-range
    UTF-16LE decodes as *valid* UTF-8 with interleaved NULs, Windows vendor
    software genuinely exports it, and calling such a file binary would be the
    confidently-wrong-message class this seam exists to remove.
    """
    return b"\x00" in h.raw and not h.bom


def head(path: str | Path, n: int = HEAD_BYTES) -> Head:
    """The first ``n`` bytes of ``path``, decoded for a sniff.

    Bounded on purpose.  The predecessor of this function decoded a whole file
    and then sliced 4 kB off it, which is an O(N) decode per dispatch on a 60 MB
    pattern.  It is deliberately **not** cached either: ``restage`` re-reads the
    same path, so a path-keyed cache would be a correctness hazard for exactly
    the file a user just replaced.
    """
    with open(path, "rb") as fh:
        raw = fh.read(n)
    encoding, bom = "utf-8", False
    for mark, codec in _BOMS:
        if raw.startswith(mark):
            encoding, bom = codec, True
            break
    return Head(raw=raw, text=raw.decode(encoding, errors="ignore"),
                encoding=encoding, bom=bom)

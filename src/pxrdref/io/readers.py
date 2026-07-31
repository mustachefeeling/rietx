"""Pattern file readers.

Supported: two/three-column ASCII (``.xy`` / ``.xye``), the GSAS ESD/STD raw
powder formats (``.fxye``/``.gsas``, as written by APS 11-BM), and powder CIF
(pdCIF, ``.cif``) as distributed with e.g. the NIST SRM certification data.
When the file carries per-point esds (or least-squares weights, from which
σ = 1/√w) they are stored in ``PatternData.sigma`` — never overridden by the
Poisson fallback (review finding M5).
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from ..schemas.pattern import PatternData


@dataclass(frozen=True)
class PatternFormat:
    """One format :func:`read_pattern` accepts, and how it is recognised.

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


def read_pattern(path: str | Path, *, block: str | None = None) -> PatternData:
    """Read any supported pattern file, dispatching on *content* first.

    GSAS raw files are recognised by their ``BANK`` record rather than by
    suffix — the format is written with a zoo of extensions (``.fxye``,
    ``.gsas``, ``.gda``, ``.xra``, ``.raw``, …) and the record is unambiguous.

    ``block`` is passed through to :func:`read_pdcif` and ignored by the other
    formats, so a caller (or a project reopening its own pattern) can name the
    data block without having to know which reader will claim the file.
    """
    p = Path(path)
    fmt = identify_format(p)
    return fmt.read(p, block=block) if "block" in fmt.options else fmt.read(p)


def identify_format(path: str | Path) -> PatternFormat:
    """Which registered format claims ``path`` — the dispatch, written once."""
    p = Path(path)
    for fmt in PATTERN_FORMATS:
        if fmt.matches(p):
            return fmt
    raise ValueError(f"no reader claims {p}")  # pragma: no cover - xy is total


#: pdCIF tag alternatives, in preference order (IUCr pdCIF dictionary,
#: Toby 2003, "CIF applications: powder diffraction", J. Appl. Cryst. 36)
_PDCIF_TT = ("_pd_proc_2theta_corrected", "_pd_meas_2theta_scan",
             "_pd_meas_2theta_range_inc")
_PDCIF_Y = ("_pd_proc_intensity_total", "_pd_meas_intensity_total",
            "_pd_meas_counts_total")
_PDCIF_SU = ("_pd_proc_intensity_total_su", "_pd_proc_intensity_total_esd",
             "_pd_meas_intensity_total_su", "_pd_meas_intensity_total_esd")


def read_pdcif(path: str | Path, *, block: str | None = None) -> PatternData:
    """Read a powder pattern from a pdCIF file.

    ``block`` selects a data block by substring match on its name (a pdCIF
    often carries several — e.g. the NIST SRM certification files hold both a
    ``…_meas`` and a ``…_calc`` block with identical tags); by default the
    first block containing a recognised 2θ + intensity loop is used.

    σ handling: an explicit ``…_su``/``…_esd`` column wins; otherwise
    ``_pd_proc_ls_weight`` is interpreted as the least-squares weight
    w = 1/σ² (its pdCIF definition), so σ = 1/√w.  With neither present,
    ``sigma`` is left unset and the Poisson fallback applies downstream.
    """
    import gemmi

    p = Path(path)
    doc = gemmi.cif.read(str(p))
    chosen = None
    for b in doc:
        if block is not None and block not in b.name:
            continue
        if _first_loop(b, _PDCIF_TT) is not None and _first_loop(b, _PDCIF_Y) is not None:
            chosen = b
            break
    if chosen is None:
        what = "pattern block" if block is None else f"pattern block matching {block!r}"
        raise ValueError(f"no pdCIF {what} found in {p}")

    tt = _first_loop(chosen, _PDCIF_TT)
    y = _first_loop(chosen, _PDCIF_Y)
    if len(tt) != len(y):
        raise ValueError(f"2θ and intensity loops differ in length in {p}")

    sigma = None
    su = _first_loop(chosen, _PDCIF_SU)
    if su is not None and len(su) == len(y):
        sigma = su
    else:
        wt = _first_loop(chosen, ("_pd_proc_ls_weight",))
        if wt is not None and len(wt) == len(y) and np.all(wt > 0):
            sigma = 1.0 / np.sqrt(wt)

    return PatternData(
        two_theta=tt.tolist(), intensity=y.tolist(),
        sigma=None if sigma is None else sigma.tolist(),
        metadata={"source_file": p.name, "format": "pdcif", "block": chosen.name},
    )


def _first_loop(b, tags: tuple[str, ...]) -> np.ndarray | None:
    """First present loop column among ``tags``, parsed as float (esds stripped)."""
    import gemmi

    for tag in tags:
        col = b.find_loop(tag)
        if len(col) > 0:
            return np.array([gemmi.cif.as_number(v) for v in col], dtype=np.float64)
    return None


def _looks_gsas(p: Path) -> bool:
    head = p.read_text(encoding="utf-8", errors="ignore")[:4000]
    return bool(re.search(r"^BANK\s+\d+", head, re.M))


def _read_xy(p: Path) -> PatternData:
    rows = []
    for line in p.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith(("#", "!", "'", "/")):
            continue
        parts = s.replace(",", " ").split()
        try:
            vals = [float(v) for v in parts[:3]]
        except ValueError:
            continue
        if len(vals) >= 2:
            rows.append(vals)
    if not rows:
        raise ValueError(f"no numeric data found in {p}")
    n_cols = min(len(r) for r in rows)
    arr = np.array([r[:n_cols] for r in rows], dtype=np.float64)
    sigma = arr[:, 2].tolist() if n_cols >= 3 and np.any(arr[:, 2] > 0) else None
    return PatternData(two_theta=arr[:, 0].tolist(), intensity=arr[:, 1].tolist(),
                       sigma=sigma, metadata={"source_file": p.name})


def _read_gsas(p: Path) -> PatternData:
    """GSAS raw powder data, CONST or ESD/FXYE variants (Larson & Von Dreele,
    2004, GSAS manual §'Powder data file formats')."""
    lines = p.read_text(encoding="utf-8", errors="ignore").splitlines()
    bank = None
    bank_re = re.compile(
        r"^BANK\s+(\d+)\s+(\d+)\s+(\d+)\s+(\w+)\s+([\d.Ee+-]+)\s+([\d.Ee+-]+)"
        r"(?:\s+([\d.Ee+-]+)\s+([\d.Ee+-]+))?\s*(\w*)")
    data_start = None
    for i, line in enumerate(lines):
        m = bank_re.match(line)
        if m:
            bank = m
            data_start = i + 1
            break
    if bank is None:
        raise ValueError(f"no BANK record found in {p}")

    nchan = int(bank.group(2))
    bintype = bank.group(4).upper()
    c1, c2 = float(bank.group(5)), float(bank.group(6))
    type_flag = (bank.group(9) or "STD").upper()

    values: list[float] = []
    for line in lines[data_start:]:
        if line.startswith("BANK"):
            break
        # FXYE files are free-format; STD files are fixed 8-column format
        values.extend(float(v) for v in line.split())

    if bintype not in ("CONS", "CONST"):
        # FXYE: explicit x column (centidegrees), then y, esd
        if type_flag != "FXYE" and len(values) % 3 != 0:
            raise ValueError(f"unsupported GSAS bintype {bintype!r} in {p}")
        type_flag = "FXYE"

    if type_flag == "FXYE":
        arr = np.array(values, dtype=np.float64).reshape(-1, 3)
        tt = arr[:, 0] / 100.0  # centidegrees → degrees
        y = arr[:, 1]
        sig = arr[:, 2]
    elif type_flag == "ESD":
        arr = np.array(values, dtype=np.float64).reshape(-1, 2)
        tt = (c1 + c2 * np.arange(len(arr))) / 100.0
        y, sig = arr[:, 0], arr[:, 1]
    else:  # STD: counts only, Poisson esd
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
    return PatternData(two_theta=tt.tolist(), intensity=y.tolist(), sigma=sigma,
                       metadata={"source_file": p.name, "format": f"gsas-{type_flag.lower()}"})


#: Every format ``read_pattern`` accepts, **in dispatch order** — the first
#: whose ``matches`` returns True reads the file, and ``xy`` is the total
#: fallback, so the order is part of the behaviour rather than presentation.
PATTERN_FORMATS: tuple[PatternFormat, ...] = (
    PatternFormat(
        name="pdcif",
        title="Powder CIF (pdCIF)",
        extensions=(".cif",),
        sniff="the .cif suffix, then a recognised 2θ + intensity loop",
        sigma=("an explicit …_su/…_esd loop, else _pd_proc_ls_weight read as "
               "w = 1/σ², else the Poisson fallback"),
        matches=lambda p: p.suffix.lower() == ".cif",
        read=read_pdcif,
        options=("block",),
    ),
    PatternFormat(
        name="gsas",
        title="GSAS raw powder data (FXYE / ESD / STD)",
        extensions=(".fxye", ".gsas", ".gda", ".xra", ".raw"),
        sniff="a BANK record in the first 4 kB — by content, not by suffix",
        sigma=("the third column (FXYE) or second (ESD); an STD bank carries "
               "counts only and takes the Poisson fallback"),
        matches=_looks_gsas,
        read=_read_gsas,
    ),
    PatternFormat(
        name="xy",
        title="Two/three-column ASCII (.xy / .xye)",
        extensions=(".xy", ".xye", ".dat", ".prn", ".txt"),
        sniff="anything else that parses as numeric rows",
        sigma="the third column when present and positive, else the Poisson fallback",
        matches=lambda p: True,
        read=_read_xy,
    ),
)

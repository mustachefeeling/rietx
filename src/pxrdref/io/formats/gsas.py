"""GSAS raw powder data — the FXYE / ESD / STD bank formats.

Spec: Larson & Von Dreele (2004), *GSAS — General Structure Analysis System*,
LAUR 86-748, §"Powder data file formats".

Recognised by its ``BANK`` record rather than by suffix: the format is written
with a zoo of extensions (``.fxye``, ``.gsas``, ``.gda``, ``.xra``, ``.raw``, …)
and the record is unambiguous.  That is also what keeps it disjoint from the
Bruker binary ``.raw``, which is claimed by magic bytes — a GSAS file named
``.raw`` still reaches this reader, and a Bruker file named ``.gsas`` does not.
"""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np

from ...schemas.common import Diagnostic
from ...schemas.pattern import PatternData
from .base import PatternFormat, ascending, head, pattern_data


def looks_gsas(p: Path) -> bool:
    return bool(re.search(r"^BANK\s+\d+", head(p).text, re.M))


def read_gsas(path: str | Path, *,
              diagnostics: list[Diagnostic] | None = None) -> PatternData:
    """GSAS raw powder data, CONST or ESD/FXYE variants."""
    p = Path(path)
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
        arr = _reshape(values, 3, p, type_flag)
        tt = arr[:, 0] / 100.0  # centidegrees → degrees
        y = arr[:, 1]
        sig = arr[:, 2]
    elif type_flag == "ESD":
        arr = _reshape(values, 2, p, type_flag)
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
    tt, y, sig = ascending(tt, y, sigma, path=p, fmt=GSAS, diagnostics=diagnostics)
    return pattern_data(p, tt, y, sig, source_file=p.name,
                   format=f"gsas-{type_flag.lower()}")


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
    sniff="a BANK record in the first 4 kB — by content, not by suffix",
    sigma=("the third column (FXYE) or second (ESD); an STD bank carries "
           "counts only and takes the Poisson fallback"),
    matches=looks_gsas,
    read=read_gsas,
)

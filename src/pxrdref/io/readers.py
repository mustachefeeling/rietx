"""Pattern file readers.

Supported: two/three-column ASCII (``.xy`` / ``.xye``) and the GSAS ESD/STD
raw powder formats (``.fxye``/``.gsas``, as written by APS 11-BM).  When the
file carries per-point esds they are stored in ``PatternData.sigma`` — never
overridden by the Poisson fallback (review finding M5).
"""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np

from ..schemas.pattern import PatternData


def read_pattern(path: str | Path) -> PatternData:
    p = Path(path)
    suffix = p.suffix.lower()
    if suffix in (".fxye", ".gsas", ".gss", ".gda", ".raw") and _looks_gsas(p):
        return _read_gsas(p)
    return _read_xy(p)


def _looks_gsas(p: Path) -> bool:
    head = p.read_text(errors="ignore")[:4000]
    return bool(re.search(r"^BANK\s+\d+", head, re.M))


def _read_xy(p: Path) -> PatternData:
    rows = []
    for line in p.read_text().splitlines():
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
    lines = p.read_text(errors="ignore").splitlines()
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

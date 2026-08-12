"""Powder CIF (pdCIF) — the IUCr interchange format for a measured profile.

Spec: IUCr pdCIF dictionary; Toby (2003), "CIF applications. XIII. CIFtbx and
pdCIF", J. Appl. Cryst. **36**, 1240.  Parsed through gemmi, so the CIF grammar
is not this package's problem; what is, is which of the alternative tags to
prefer and how a weight becomes a σ.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from ...schemas.common import Diagnostic
from ...schemas.pattern import PatternData
from .base import PatternFormat, ascending, pattern_data

#: pdCIF tag alternatives, in preference order
_PDCIF_TT = ("_pd_proc_2theta_corrected", "_pd_meas_2theta_scan",
             "_pd_meas_2theta_range_inc")
_PDCIF_Y = ("_pd_proc_intensity_total", "_pd_meas_intensity_total",
            "_pd_meas_counts_total")
_PDCIF_SU = ("_pd_proc_intensity_total_su", "_pd_proc_intensity_total_esd",
             "_pd_meas_intensity_total_su", "_pd_meas_intensity_total_esd")


def read_pdcif(path: str | Path, *, block: str | None = None,
               diagnostics: list[Diagnostic] | None = None) -> PatternData:
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

    tt, y, sigma = ascending(tt, y, sigma, path=p, fmt=PDCIF,
                             diagnostics=diagnostics)
    return pattern_data(p, tt, y, sigma,
                   source_file=p.name, format="pdcif", block=chosen.name)


def _first_loop(b, tags: tuple[str, ...]) -> np.ndarray | None:
    """First present loop column among ``tags``, parsed as float (esds stripped)."""
    import gemmi

    for tag in tags:
        col = b.find_loop(tag)
        if len(col) > 0:
            return np.array([gemmi.cif.as_number(v) for v in col], dtype=np.float64)
    return None


PDCIF = PatternFormat(
    name="pdcif",
    title="Powder CIF (pdCIF)",
    extensions=(".cif",),
    sniff="the .cif suffix, then a recognised 2θ + intensity loop",
    sigma=("an explicit …_su/…_esd loop, else _pd_proc_ls_weight read as "
           "w = 1/σ², else the Poisson fallback"),
    matches=lambda p: p.suffix.lower() == ".cif",
    read=read_pdcif,
    options=("block",),
)

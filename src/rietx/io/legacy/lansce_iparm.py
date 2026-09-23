"""The legacy LANSCE ``.iparm`` layout: :func:`read_lansce_iparm`.

The LANSCE NPDF instrument files this package's authors hold deviate from the
layout the GSAS Technical Manual documents (Larson & Von Dreele 2004,
LAUR 86-748, p. 221-223) in two ways, both on every file obtained and neither
described there.  :func:`rietx.io.instrument_tof.read_gsas_tof_iparm` refuses
both by name and stays that way.  This reader accepts them on request:

1. **An 8-coefficient type-1 ``PRCF`` block** — the default set declares
   ``PTYP 1, NCOF 8`` in two coefficient records, where the manual documents
   twelve names for profile function 1 (p. 144: ``alp-0 alp-1 bet-0 bet-1
   sig-0 sig-1 sig-2 s1ec s2ec rstr rsta rsca``).  **Read as slots 1-8 of the
   documented twelve**, slots 9-12 zero, by restating the header's ``NCOF`` as
   12 and adding a ``PRCFn3`` record of zeros, then handing the records to the
   strict reader's own body — so every column check, the anisotropic-term
   refusal (slot 8 is ``s1ec``) and the variance-sign check apply unchanged.
   Emits ``GSAS_IPARM_LEGACY_LAYOUT``.
2. **A non-zero fifth ``ICOFF`` pair of ITYP 1/2** — P₁₀·exp(−P₁₁·Tᵏ), whose
   exponent the manual does not print.  **k = 5 is now measured**
   (:data:`LANSCE_FIFTH_PAIR_EXPONENT`), and it is the power
   :mod:`rietx.model.tof_spectrum` already evaluates — but
   :class:`~rietx.schemas.instrument.IncidentSpectrum` refuses a non-zero
   P₁₀/P₁₁ at construction and :func:`~rietx.model.tof_spectrum.incident_spectrum`
   at evaluation (``tof_spectrum._refuse_inferred_pair``), and this module does
   not change the model.  So a bank carrying one is **refused**, naming the
   measured exponent and the refusal that would have to be lifted; no schema
   field is missing, only that rule.  The refusal is raised after every other
   check has run on the file, so a file wrong in some other way is refused for
   that reason first.

A file carrying neither deviation is read by the strict reader and returned
exactly as it returns it.

**How the layout was confirmed — GSAS-II as a black box, nothing read.**
GSAS-II v5.8.2 (revision 5841), run under its own interpreter
(``~/.local/gsas2/bin/python``) on 2026-09-23 through its public scripting API
only: ``G2sc.G2Project(newgpx=…)``, ``.add_powder_histogram(flat.xye, file.prm,
fmthint="xye", instbank=b)``, then ``hist.data["Instrument Parameters"]`` and
``hist.getdata("X")``/``("Yobs")``.  On the NPDF run 7245 Si-standard
calibration, bank 1 (DIFC 6911.21, DIFA −2.79, ZERO −19.42, 2θ 46.60°) came
back ``alpha 0.146061, beta-0 0.0434277, beta-1
0.0233696, sig-0 0, sig-1 353.349, sig-2 0`` — slots 2, 3, 4, 6, 7 of its
8-slot block.  Synthetic files with a distinct sentinel in one slot at a time
place every slot (:data:`GSAS2_PRCF1_DESTINATIONS`): slots 2, 3, 4, 6, 7 land
under ``alpha, beta-0, beta-1, sig-1, sig-2``, and slots 1, 5, 8 under no name
at all — and a 12-slot type-1 block gives the same destinations slot for slot.
So GSAS-II reads the 8-slot block as the 12-slot block cut short, which is the
restatement above; the names of slots 1, 5 and 8 rest on the manual's order
alone, exactly as they do for a 12-slot file in the strict reader.  For the
spectrum, a flat synthetic pattern (y = 1000 everywhere) comes back as
1000/I_i(T), so GSAS-II's own incident spectrum is observable on its grid: it
equals this package's ITYP 1/2 law at GSAS-II's bin-centre ``X`` to 2e-16
relative, and a least-squares fit of the fifth term alone gives k = 5.000000
at three decades of P₁₁ (log-log residual ≤ 2e-11), on ITYP 1 and ITYP 2, and
on the real bank 2 (P₁₁ = 5.21191e-5; the term is 17 % of I_i there), residual
2e-13 and doubled by Δk ≈ 1.5e-15.  GSAS-II is an oracle for the file layout
and the incident spectrum only: its time-of-flight profile function has a known
Lorentzian-sign defect, so nothing here is checked against a peak shape it
computes.
"""

from __future__ import annotations

from pathlib import Path

from ...schemas.common import Diagnostic
from ...schemas.instrument import Instrument
from ..instrument_tof import (
    _E15_FIELDS,
    _ITYP_FIELDS,
    _PRCF_FIELDS,
    PRCF_COEFFICIENT_NAMES,
    _banks_from_records,
    _note,
    _read_records,
    _Record,
    read_gsas_tof_iparm,
)

#: The legacy block's declared coefficient count for profile function 1.
LEGACY_PRCF1_NCOF = 8

#: The eight slots, named as slots 1-8 of the documented twelve (GSAS
#: Technical Manual p. 144) — confirmed by GSAS-II v5.8.2 reading an 8-slot and
#: a 12-slot block slot for slot alike (module docstring, 2026-09-23).
LEGACY_PRCF1_SLOT_NAMES: tuple[str, ...] = PRCF_COEFFICIENT_NAMES[1][:LEGACY_PRCF1_NCOF]

#: Where GSAS-II v5.8.2 puts each of the eight slots, measured one sentinel at
#: a time (module docstring); ``None`` is a slot it carries under no name.
GSAS2_PRCF1_DESTINATIONS: tuple[str | None, ...] = (
    None, "alpha", "beta-0", "beta-1", None, "sig-1", "sig-2", None)

#: k in the ITYP 1/2 fifth term P₁₀·exp(−P₁₁·Tᵏ), T in ms.  Measured against
#: GSAS-II v5.8.2's incident spectrum on 2026-09-23: 5.000000 on three
#: synthetic decades of P₁₁ and on the real NPDF 7245 bank 2, residual 2e-13,
#: doubled by Δk ≈ 1.5e-15 (module docstring).
LANSCE_FIFTH_PAIR_EXPONENT = 5

_ZERO_E15 = f"{0.0:15.6E}"


def _legacy_prcf1(path: Path, number: int, line: str) -> bool:
    rec = _Record(path, number, line)
    rec.check_columns(_PRCF_FIELDS)
    return (rec.integer(13, 17, "PTYP"), rec.integer(18, 22, "NCOF")) == (
        1, LEGACY_PRCF1_NCOF)


def _fifth_pair(path: Path, number: int, line: str) -> tuple[float, float]:
    fields = _Record(path, number, line).e15_block()
    out = []
    for f in fields[1:3]:
        s = f.strip()
        try:
            out.append(float(s.replace("D", "E")) if s else 0.0)
        except ValueError:
            out.append(0.0)       # the strict reader names a non-number itself
    return out[0], out[1]


def _scan(path: Path, records: list[tuple[str, str]]):
    """Which banks carry which deviation: ``(legacy PRCF banks, PRCF1
    continuation tags per bank, ITYP per bank, ICOFF3 record number per bank,
    non-zero fifth pairs per bank)``."""
    legacy_banks: list[int] = []
    conts: dict[int, list[int]] = {}
    fifth: dict[int, tuple[float, float]] = {}
    ityp: dict[int, int] = {}
    icoff3: dict[int, int] = {}
    for number, (key, payload) in enumerate(records, start=1):
        line = key + payload
        bb, name = line[4:6], line[6:12]
        if not line.startswith("INS ") or not bb.strip().isdigit():
            continue           # the strict reader refuses a bad bank field
        b = int(bb)
        if name == "PRCF1 " and _legacy_prcf1(path, number, line):
            legacy_banks.append(b)
        elif name.startswith("PRCF1") and name[5].isdigit():
            conts.setdefault(b, []).append(int(name[5]))
        elif name == "I ITYP":
            rec = _Record(path, number, line)
            rec.check_columns(_ITYP_FIELDS)
            ityp[b] = rec.integer(13, 17, "ITYP")
        elif name == "ICOFF3":
            icoff3[b] = number
    for b, number in icoff3.items():
        if ityp.get(b) in (1, 2):
            pair = _fifth_pair(path, number, "".join(records[number - 1]))
            if pair != (0.0, 0.0):
                fifth[b] = pair
    return legacy_banks, conts, ityp, icoff3, fifth


def read_lansce_iparm(path: str | Path, *,
                      diagnostics: list[Diagnostic] | None = None
                      ) -> dict[int, Instrument]:
    """Read a GSAS-I TOF ``.iparm`` that may carry the legacy LANSCE layout.

    Returns what :func:`rietx.read_gsas_tof_iparm` returns — ``{bank number:
    Instrument}``, every parameter ``vary=False`` — and is that function,
    unchanged, on a file carrying neither deviation the module docstring
    names.  An 8-coefficient type-1 default ``PRCF`` set is read as slots 1-8
    of the documented twelve and reported as ``GSAS_IPARM_LEGACY_LAYOUT``
    (level ``info``, once per file, naming the banks); a non-zero ITYP 1/2
    fifth ``ICOFF`` pair is refused, because the model refuses it.  Anything
    else the strict reader refuses is refused by it, with its message.
    """
    path = Path(path)
    records = _read_records(path)
    try:
        legacy_banks, conts, ityp, icoff3, fifth = _scan(path, records)
    except ValueError:
        # a record this scan cannot read is the strict reader's to name, in
        # its own order; should it read the file after all, the scan's
        # refusal stands
        read_gsas_tof_iparm(path)
        raise

    if not legacy_banks and not fifth:
        return read_gsas_tof_iparm(path, diagnostics=diagnostics)

    restated = list(records)
    for b in legacy_banks:
        if sorted(conts.get(b, [])) != [1, 2]:
            raise ValueError(
                f"{path}: bank {b}'s PRCF set 1 declares profile function 1 with "
                f"{LEGACY_PRCF1_NCOF} coefficients and carries coefficient "
                f"records {sorted(conts.get(b, []))}; the legacy LANSCE layout "
                f"this reader accepts is exactly two records, PRCF11 and PRCF12, "
                f"and any other shape is refused rather than restated")
        for i, (key, payload) in enumerate(restated):
            if key == f"INS {b:2d}PRCF1 ":
                line = (key + payload).ljust(22)
                restated[i] = (key, (line[:17] + f"{12:5d}" + line[22:])[12:])
        restated.append((f"INS {b:2d}PRCF13", _ZERO_E15 * 4))

    if fifth:
        # every other refusal speaks first: run the strict body on a copy
        # whose fifth pairs are zero, discard its answer, then refuse
        probe = list(restated)
        for b in fifth:
            key, payload = probe[icoff3[b] - 1]
            line = (key + payload).ljust(80)
            a, z = _E15_FIELDS[1][0], _E15_FIELDS[2][1]
            probe[icoff3[b] - 1] = (key, (line[:a - 1] + _ZERO_E15 * 2 + line[z:])[12:])
        _banks_from_records(path, probe, None)
        b = min(fifth)
        p10, p11 = fifth[b]
        raise ValueError(
            f"{path}: bank {b}: ITYP {ityp[b]} carries a non-zero fifth ICOFF "
            f"pair (P10 = {p10!r}, P11 = {p11!r}). Its law is established — "
            f"GSAS-II v5.8.2 evaluates it as P10*exp(-P11*T^"
            f"{LANSCE_FIFTH_PAIR_EXPONENT}), T in ms, measured as a black box — "
            f"and it is the power rietx.model.tof_spectrum already evaluates, "
            f"but rietx.schemas.instrument.IncidentSpectrum refuses a non-zero "
            f"P10/P11 (tof_spectrum._refuse_inferred_pair) and this legacy "
            f"reader does not change the model, so the bank is refused rather "
            f"than read without its term")

    out = _banks_from_records(path, restated, diagnostics)
    names = " ".join(LEGACY_PRCF1_SLOT_NAMES)
    _note(diagnostics, "info", "GSAS_IPARM_LEGACY_LAYOUT",
          f"{path.name}: bank(s) {', '.join(map(str, legacy_banks))}: PRCF set 1 "
          f"is the legacy LANSCE layout, profile function 1 with "
          f"{LEGACY_PRCF1_NCOF} coefficients. It was read as slots 1-8 of the "
          f"documented twelve ({names}; slots 9-12 zero) and handed to the "
          f"strict reader, whose GSAS_IPARM_PROFILE_READ describes that "
          f"restated 12-slot block. GSAS-II v5.8.2 reads an 8-slot and a "
          f"12-slot type-1 block slot for slot alike: slots 2, 3, 4, 6, 7 land "
          f"under alpha, beta-0, beta-1, sig-1, sig-2, and slots 1, 5, 8 under "
          f"no name, so those three rest on the manual's order alone.",
          where=[f"bank {b}" for b in legacy_banks] + ["PRCF1"])
    return out

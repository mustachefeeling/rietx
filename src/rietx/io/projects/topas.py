"""Read a TOPAS ``.inp`` refinement input into a rietx model.

Format: Bruker TOPAS (Academic/v4-v7) input files. TOPAS itself is closed
source; this reader is written from the *file syntax* only, as
``ATTRIBUTION.md``'s fence requires — no TOPAS code or macro library is used,
and the emission-profile macros (``CuKa5`` and friends) are deliberately **not**
expanded here: only the anode is reported, and the caller supplies the
wavelengths from :data:`rietx.schemas.instrument._RADIATIONS`.

Why this belongs in the package: a ``.inp`` carries the whole solved model —
phases, sites, cell, instrument geometry, and the converged ``r_wp`` — so it is
the cheapest possible source of a *validated* refinement to test against. The
alternative is hunting CIFs that may not match what was actually fitted.

Four properties of these files cause silent, not loud, failures, and each is
handled explicitly below. All four were found by refining real archives, not by
reading the syntax:

1. **Dead text outnumbers live text.** ``/* … */`` blocks and ``'`` line
   comments routinely disable several instrument blocks per file. Reading a
   wavelength without stripping them picks up whichever block was commented out.
2. **``#ifdef`` gates real content.** A phase inside a disabled branch is not in
   the model. Nesting is shallow but real.
3. **A coordinate is not always a literal.** Special positions are conventionally
   written as equations (``x = 1/3;``), and refinable values carry a *name*
   before the number (``y ph1_o_y 0.24625```). A parser that demands a bare
   number silently drops the first and mis-reads the second — dropping two heavy
   atoms out of seven cost a 98 wt% phase-fraction error with a *better* Rwp,
   which is why :func:`read_topas_inp` counts sites and raises.
4. **Symbols use TOPAS spellings.** Space-group origin choices are letter
   suffixes (``Pn-3mZ``), and ionic charge is written sign-first (``Cu+1``).
   Both are translated; the origin one matters because dropping the suffix
   silently selects the *other* origin.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

#: TOPAS origin/axis suffixes → the Hermann-Mauguin extension gemmi wants.
#: ``Z`` is *Zentrum*, the centrosymmetric origin (choice 2); ``S`` is the
#: site-symmetry origin (choice 1). Dropping the letter is not harmless: for
#: #224 a bare ``Pn-3m`` resolves to choice **1**, so a Cu2O described on
#: choice 2 (Cu at 0,0,0; O at ¼,¼,¼) would be given the wrong origin's
#: symmetry with nothing raised.
_SG_SUFFIX: dict[str, str] = {"Z": ":2", "S": ":1", "R": ":R", "H": ":H"}

_NUM = r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?"


class TopasInpError(ValueError):
    """Raised naming the file and the offending line, never a bare regex miss."""


@dataclass
class TopasSite:
    label: str
    species: str
    x: float
    y: float
    z: float
    occupancy: float = 1.0
    beq: float = 0.5


@dataclass
class TopasPhase:
    name: str
    space_group: str
    cell: dict = field(default_factory=dict)
    cell_limits: dict = field(default_factory=dict)
    sites: list = field(default_factory=list)
    scale: float | None = None
    weight_percent: float | None = None


@dataclass
class TopasModel:
    """What a ``.inp`` states. Deliberately not a :class:`Structure` yet — the
    caller decides which phases to keep and how to seed what the file omits."""

    phases: list = field(default_factory=list)
    anode: str | None = None          # "CuKa" from a CuKa5(...) macro
    emission_macro: str | None = None  # "CuKa5" verbatim, for provenance
    wavelength: float | None = None    # only if written as an explicit la/lo
    goniometer_radius_mm: float | None = None
    geometry: str | None = None
    r_wp: float | None = None
    gof: float | None = None
    data_files: list = field(default_factory=list)
    background_terms: int | None = None


def strip_comments(text: str) -> str:
    """Remove ``/* */`` blocks and ``'`` line comments (rule 1)."""
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return "\n".join(line.split("'")[0] for line in text.split("\n"))


def resolve_ifdefs(text: str) -> str:
    """Keep only ``#ifdef``/``#ifndef`` branches that are actually live (rule 2).

    Symbols are collected first because TOPAS permits a ``#define`` after its
    own use; the stack keeps nesting honest.
    """
    defined = set(re.findall(r"^\s*#define\s+(\w+)", text, re.M))
    out: list[str] = []
    stack: list[list[bool]] = []          # [keeping_here, branch_already_taken]
    for line in text.split("\n"):
        s = line.strip()
        if m := re.match(r"#ifn?def\s+(\w+)", s):
            live = (m.group(1) in defined) != s.startswith("#ifndef")
            stack.append([live, live])
            continue
        if s.startswith("#else"):
            if stack:
                stack[-1] = [not stack[-1][1], True]
            continue
        if s.startswith("#endif"):
            if stack:
                stack.pop()
            continue
        if all(frame[0] for frame in stack):
            out.append(line)
    return "\n".join(out)


def normalize_species(species: str) -> str:
    """``Cu+1`` → ``Cu1+`` (rule 4). IUCr order is digit-first."""
    s = re.sub(r"[^A-Za-z0-9+-]", "", species)
    if m := re.fullmatch(r"([A-Za-z]{1,2})([+-])(\d*)", s):
        element, sign, magnitude = m.groups()
        return f"{element}{magnitude or ''}{sign}"
    return s


def normalize_space_group(symbol: str) -> str:
    """``Pn-3mZ`` → ``Pn-3m:2`` (rule 4, and see :data:`_SG_SUFFIX`)."""
    s = symbol.strip()
    if s.endswith(tuple(_SG_SUFFIX)) and not s.endswith(":"):
        stem, suffix = s[:-1], s[-1]
        # only a real suffix, not the final letter of a symbol like "Fm-3m"
        if re.search(r"[a-z\-0-9/]$", stem):
            return stem + _SG_SUFFIX[suffix]
    return s


def _value(token: str) -> float:
    """Strip TOPAS's decoration: ``@``/``!`` flags, a trailing refined-marker
    backtick, and ``_LIMIT_*`` annotations."""
    token = re.sub(r"_LIMIT_[A-Z_]*[\d.]*", "", token.strip().lstrip("@!").rstrip("`"))
    if m := re.search(_NUM, token):
        return float(m.group(0))
    raise ValueError(token)


def _field(name: str, line: str) -> float | None:
    """One ``site`` field, in either spelling (rule 3).

    Self-contained rational arithmetic in the equation form is evaluated;
    an equation referencing another parameter (``z = 1-x;``) returns None so
    the caller raises rather than inventing a coordinate.
    """
    if m := re.search(rf"\b{name}\s*=\s*([^;\n]+);", line):
        expr = m.group(1).strip()
        if not re.fullmatch(r"[\d\s./*+-]+", expr):
            return None
        try:
            return float(eval(expr, {"__builtins__": {}}, {}))  # noqa: S307
        except Exception:
            return None
    if m := re.search(rf"\b{name}\s+(?:[A-Za-z_]\w*\s+)?(@?!?\s*{_NUM}`?)", line):
        try:
            return _value(m.group(1))
        except ValueError:
            return None
    return None


def read_topas_inp(path: str | Path) -> TopasModel:
    """Parse a ``.inp``. Raises :class:`TopasInpError` naming the file and line."""
    path = Path(path)
    try:
        raw = path.read_text(errors="ignore")
    except OSError as exc:
        raise TopasInpError(f"{path}: cannot read: {exc}") from exc
    active = resolve_ifdefs(strip_comments(raw))
    model = TopasModel()

    if m := re.search(rf"r_wp\s+({_NUM})", active):
        model.r_wp = float(m.group(1))
    if m := re.search(rf"\bgof\s+({_NUM})", active):
        model.gof = float(m.group(1))
    if m := re.search(r"\b((?:Cu|Co|Cr|Fe|Mo|Ag)Ka\d?)\s*\(", active):
        model.emission_macro = m.group(1)
        model.anode = re.sub(r"\d$", "", m.group(1))
    if lo := re.findall(rf"\bla\s+{_NUM}\s+lo\s+({_NUM})", active):
        model.wavelength = float(lo[0])
    if m := re.search(rf"Radius\(\s*({_NUM})", active):
        model.goniometer_radius_mm = float(m.group(1))
    model.geometry = ("debye_scherrer"
                      if re.search(r"Cylindrical_|capillary|Debye", active, re.I)
                      else "bragg_brentano")
    if m := re.search(rf"bkg\s*((?:\s*@?\s*{_NUM}`?)+)", active):
        model.background_terms = len(re.findall(_NUM, m.group(1)))
    model.data_files = [d.strip() for d in re.findall(r'xdd\s+"?([^"\n]+)', active)]

    for chunk in re.split(r"^\s*str\s*$", active, flags=re.M)[1:]:
        name = re.search(r'phase_name\s+"?([^"\n]+)', chunk)
        sg = re.search(r'space_group\s+"?([^"\n]+)', chunk)
        if not (name and sg):
            continue
        phase = TopasPhase(name=name.group(1).strip(),
                           space_group=normalize_space_group(sg.group(1)))
        for key in ("a", "b", "c", "al", "be", "ga"):
            m = re.search(rf"^\s*{key}\s+(?:\w+\s+)?(@?!?\s*{_NUM}`?)([^\n]*)",
                          chunk, re.M)
            if not m:
                continue
            try:
                phase.cell[key] = _value(m.group(1))
            except ValueError:
                continue
            # TOPAS bounds a cell explicitly (`min 3.61 max 3.66;`). Those are
            # part of the author's model: without them a phase the data cannot
            # see is a flat direction and its cell runs away.
            lo = re.search(rf"\bmin\s*=?\s*({_NUM})", m.group(2))
            hi = re.search(rf"\bmax\s*=?\s*({_NUM})", m.group(2))
            if lo or hi:
                phase.cell_limits[key] = (float(lo.group(1)) if lo else None,
                                          float(hi.group(1)) if hi else None)
        if m := re.search(rf"Cubic_?\(\s*\w*\s*({_NUM})", chunk):
            if "a" not in phase.cell:
                v = float(m.group(1))
                phase.cell.update(a=v, b=v, c=v, al=90.0, be=90.0, ga=90.0)
        if m := re.search(rf"scale\s+\w*\s*@?\s*({_NUM})", chunk):
            phase.scale = float(m.group(1))
        if m := re.search(rf"weight_percent\s+\w*\s*({_NUM})", chunk):
            phase.weight_percent = float(m.group(1))

        site_lines = [ln for ln in chunk.split("\n") if re.match(r"\s*site\s", ln)]
        for line in site_lines:
            label = re.match(r"\s*site\s+(\S+)", line)
            occ = re.search(r"\bocc\s+(\S+)\s+(\S+)", line)
            if not (label and occ):
                raise TopasInpError(
                    f"{path}: {phase.name}: no label/occ in site line: {line.strip()!r}")
            coords = {}
            for axis in "xyz":
                v = _field(axis, line)
                if v is None:
                    raise TopasInpError(
                        f"{path}: {phase.name}: cannot read {axis} from "
                        f"site line: {line.strip()!r}")
                coords[axis] = v
            beq = _field("beq", line)
            phase.sites.append(TopasSite(
                label=label.group(1), species=normalize_species(occ.group(1)),
                occupancy=_value(occ.group(2)),
                beq=beq if beq is not None else 0.5, **coords))
        # A dropped site is a silently wrong structure factor, so the count is
        # an invariant rather than something the regex is trusted to get right.
        if len(phase.sites) != len(site_lines):
            raise TopasInpError(
                f"{path}: {phase.name}: parsed {len(phase.sites)} sites from "
                f"{len(site_lines)} site lines")
        model.phases.append(phase)
    return model


def to_structure(model: TopasModel, *, cell_limits: bool = True):
    """Build a :class:`~rietx.schemas.Structure` from a parsed model.

    ``beq`` is TOPAS's B and rietx's ``biso`` is also B — no 8π² conversion.
    ``cell_limits`` applies the file's own ``min``/``max`` where it stated them.
    """
    import rietx as rx

    phases = []
    for ph in model.phases:
        if "a" not in ph.cell:
            continue
        c = ph.cell

        def _p(key: str, default: float):
            lo, hi = ph.cell_limits.get(key, (None, None)) if cell_limits else (None, None)
            kw = {}
            if lo is not None:
                kw["min"] = lo
            if hi is not None:
                kw["max"] = hi
            return rx.Parameter(value=c.get(key, default), **kw)

        cell = rx.Cell(a=_p("a", c["a"]), b=_p("b", c["a"]), c=_p("c", c["a"]),
                       alpha=_p("al", 90.0), beta=_p("be", 90.0), gamma=_p("ga", 90.0))
        atoms = [rx.Atom(label=s.label, species=s.species,
                         x=rx.Parameter(value=s.x), y=rx.Parameter(value=s.y),
                         z=rx.Parameter(value=s.z),
                         occupancy=rx.Parameter(value=s.occupancy),
                         biso=rx.Parameter(value=max(s.beq, 0.0), min=0.0, max=25.0))
                 for s in ph.sites]
        phases.append(rx.Phase(
            name=ph.name, space_group=ph.space_group, cell=cell, atoms=atoms,
            scale=rx.Parameter(value=ph.scale or 1e-4, min=0.0,
                               transform="softplus")))
    return rx.Structure(phases=phases)

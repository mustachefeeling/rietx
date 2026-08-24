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
4. **The refine flags are the payload, not the numbers** (WP-1118). A control
   file says which parameters were free and which were held, and that is the
   part a person cannot reconstruct from a CIF plus a pattern — it is also what
   decides whether a cross-code comparison means anything. ``!`` is held, ``@``
   is refined, and a trailing backtick means TOPAS wrote the value back after
   refining it; the *absence* of that backtick is the inference WP-1110's agent
   round named as the hardest single thing about transcribing an ``.inp`` by
   hand. :func:`refined` is that reading, and it is a tri-state: a file that
   says nothing is not a file that said "held".
5. **Symbols use TOPAS spellings.** Space-group origin choices are letter
   suffixes (``Pn-3mZ``), and ionic charge is written sign-first (``Cu+1``).
   Both are translated; the origin one matters because dropping the suffix
   silently selects the *other* origin.
"""

from __future__ import annotations

import ast
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

#: A TOPAS parameter name. Leading character is deliberately **not** ``\w``:
#: ``\w`` matches a digit, so ``(?:\w+\s+)?`` in front of a value silently eats
#: the integer part of a *nameless* one — ``weight_percent 97.9`` came back
#: 0.9, a wrong number with nothing raised, which is the whole failure class
#: this reader exists to avoid.
_NAME = r"[A-Za-z_]\w*"

#: Refinement flags, in every spelling the archive actually contains: ``@``
#: (refine), ``!`` (fix), and either followed by a comma — ``@, 0.0013`` is
#: how TOPAS writes a refined value it did not name, and appears on 100+ files
#: here. Flags may sit before the name, after it, or both.
_FLAG = r"(?:[@!]\s*,?\s*)"

#: The one grammar every scalar in a ``.inp`` follows:
#: ``<keyword> [flags] [name] [flags] <number>[`][_esd][_LIMIT_…]``.
#: Written once because five ad-hoc spellings of it disagreed on real files —
#: `scale @, 0.0013` and `weight_percent !ph3_wtpct 100.0` were read as *absent*
#: by two of them, which `to_structure` then replaced with a default scale.
_PRM = rf"{_FLAG}?(?:{_NAME}\s+{_FLAG}?)?({_NUM})"

#: An equation *and the value TOPAS evaluated it to*: ``= 1/4 + Fe1_1_dx;: 0.25``.
#: The ``;:`` tail is the most authoritative number in the file — it is what the
#: converged refinement actually used, so it is preferred over re-evaluating the
#: expression here, which would need every symbol the expression reaches.
_EVALUATED = rf"=\s*[^;\n]*;\s*:\s*({_NUM})"


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
    #: Which of this site's parameters the file records as having been free.
    #: Keyed by field name (``"x"``, ``"beq"``, …); a key is absent where the
    #: file said nothing, which is not the same as "held" — see :func:`refined`.
    vary: dict = field(default_factory=dict)


@dataclass
class TopasPhase:
    name: str
    space_group: str
    cell: dict = field(default_factory=dict)
    cell_limits: dict = field(default_factory=dict)
    sites: list = field(default_factory=list)
    scale: float | None = None
    weight_percent: float | None = None
    #: The phase-level half of the same protocol, keyed as the cell dict is
    #: (``"a"``, ``"be"``, …) plus ``"scale"``.
    vary: dict = field(default_factory=dict)


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


def refined(name: str, text: str) -> bool | None:
    """Was this parameter free in the refinement the file records?

    **The refine flags are the payload, not the numbers** (WP-1118): a control
    file says which parameters were free, which were held and what was
    excluded, and that is the part a person cannot reconstruct from a CIF plus
    a pattern. It is also the part that decides whether a cross-code comparison
    means anything — DESIGN.md's v0.2 lesson, that a guessed protocol gave
    Rwp 16 % and +390 ppm on fluorapatite against 9.73 % for the mirrored one.

    Three signals, in decreasing order of authority:

    * ``!`` before the value or its name — explicitly **held**.
    * ``@`` before either — explicitly **refined**.
    * a trailing backtick — TOPAS wrote this value back after refining it, so
      it was free. Its *absence* is the inference WP-1110's agent round named
      as the hardest single thing about transcribing an ``.inp`` by hand.

    None means the file says nothing either way, which is not the same as
    "fixed" and is why this is a tri-state rather than a bool.
    """
    m = re.search(rf"\b{name}\s+({_FLAG}?(?:{_NAME}\s+{_FLAG}?)?){_NUM}(`?)", text)
    if not m:
        return None
    flags, tick = m.group(1) or "", m.group(2)
    if "!" in flags:
        return False
    if "@" in flags or tick == "`":
        return True
    return None


def _value(token: str) -> float | None:
    """Strip TOPAS's decoration: ``@``/``!`` flags, a trailing refined-marker
    backtick, and ``_LIMIT_*`` annotations.

    Returns None rather than raising on a token holding no number. The caller
    is the only place that knows whether that is fatal — a missing coordinate
    is, a missing occupancy is not — and a bare ``ValueError`` from here
    escaped as the parser's own exception, which this package's readers may
    never do (root ``CLAUDE.md``: a reader raises naming the file).
    """
    token = re.sub(r"_LIMIT_[A-Z_]*[\d.]*", "", token.strip().lstrip("@!").rstrip("`"))
    m = re.search(_NUM, token)
    return float(m.group(0)) if m else None


_AST_OPS = (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.USub, ast.UAdd)


def _arith(expr: str) -> float | None:
    """Evaluate the rational arithmetic TOPAS writes for a special position.

    ``ast`` rather than ``eval``: the charset gate this replaces admitted
    ``**``, so ``9**9**9`` in a malformed file was an unbounded computation
    inside a reader. Only the five operators a coordinate equation needs are
    walked, and anything else — a name, a call, a power — returns None.
    """
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError:
        return None

    def walk(node):
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, _AST_OPS):
            v = walk(node.operand)
            return None if v is None else (-v if isinstance(node.op, ast.USub) else v)
        if isinstance(node, ast.BinOp) and isinstance(node.op, _AST_OPS):
            a, b = walk(node.left), walk(node.right)
            if a is None or b is None:
                return None
            if isinstance(node.op, ast.Add):
                return a + b
            if isinstance(node.op, ast.Sub):
                return a - b
            if isinstance(node.op, ast.Mult):
                return a * b
            return None if b == 0 else a / b
        return None

    return walk(tree.body)


def symbol_table(text: str) -> dict[str, float]:
    """Every ``<name> <value>`` parameter binding in the file.

    Needed because a coordinate equation routinely *references another
    parameter* rather than being self-contained: ``y = ph1_O1_x;`` is how a
    tetragonal Cr2WO6 oxygen says y is tied to x. Refusing those cost 14 of the
    606 archive files, the tier-1 Cr2WO6 references among them, so the
    reference is resolved instead — and an unresolvable one still returns None
    and still raises, because inventing a coordinate is the one outcome worse
    than refusing to read the file.
    """
    out: dict[str, float] = {}
    # `prm Fe1_1_x = 1/4 + Fe1_1_dx;: 0.25000` — bind the evaluated value, which
    # is the whole reason the deeper chain (`Fe1_1_dx`) never has to be walked.
    for name, tok in re.findall(rf"\b({_NAME})\s*{_EVALUATED}", text):
        out.setdefault(name, float(tok))
    for name, tok in re.findall(rf"\b({_NAME})\s+{_FLAG}?({_NUM})", text):
        out.setdefault(name, float(tok))
    return out


def _resolve(expr: str, symbols: dict[str, float]) -> float | None:
    """An equation's value: substitute named parameters, then evaluate.

    Longest name first, so a name that is a prefix of another is never
    half-replaced (``Fe1_1_x`` inside ``Fe1_1_x2``).
    """
    for sym in sorted(symbols, key=len, reverse=True):
        if sym in expr:
            expr = re.sub(rf"\b{re.escape(sym)}\b", repr(symbols[sym]), expr)
    return _arith(expr)


def _field(name: str, line: str, symbols: dict[str, float] | None = None) -> float | None:
    """One ``site`` field, in every spelling the archive contains (rule 3).

    Four forms, all real: a plain or flagged number (``z 0.5``, ``beq @, 0.58``),
    a *named* value with the flag on either side (``z !ph1_cr1_z 0.33489``), an
    equation (``x = 1/3;``, ``x Zr1_x =1/2;``), and the ``A1(name, value, esd)``
    macro TOPAS writes for a refined coordinate.
    """
    symbols = symbols or {}
    #: A1/A2/A3 are x/y/z; checked first because the axis letter does not appear.
    axis_macro = {"x": "A1", "y": "A2", "z": "A3"}.get(name)
    if axis_macro and (m := re.search(
            rf"\b{axis_macro}\(\s*{_FLAG}?{_NAME}\s*,\s*({_NUM})", line)):
        return float(m.group(1))
    # TOPAS's own evaluated value first, where the file states one.
    if m := re.search(rf"\b{name}\s+(?:{_NAME}\s*)?{_EVALUATED}", line):
        return float(m.group(1))
    if m := re.search(rf"\b{name}\s+(?:{_NAME}\s*)?=\s*([^;\n]+);", line):
        return _resolve(m.group(1).strip(), symbols)
    if m := re.search(rf"\b{name}\s+{_FLAG}?(?:{_NAME}\s+{_FLAG}?)?({_NUM}`?)", line):
        return _value(m.group(1))
    return None


#: Keywords that can follow ``occ`` on a site line. They bound the occupancy's
#: text, which is what makes an *absent* occupancy different from one whose
#: value is the next keyword's: ``occ Sr+2 beq 0.765`` is a full occupancy and a
#: B of 0.765, and reading the token after the species gave it occupancy 0.765.
_SITE_KEYWORDS = r"\b(?:beq|ADPs|vcocc|rand_xyz|num_posns|u\d\d|site)\b"


def _occupancy(rest: str, symbols: dict[str, float]) -> float | None:
    """The occupancy from the text after ``occ <species>``, or None if absent.

    None means TOPAS's own default of full occupancy, not a parse failure: the
    keyword is optional in the format. Distinguishing the two is why the search
    is bounded by :data:`_SITE_KEYWORDS` rather than being a scan to end of line.
    """
    tail = re.split(_SITE_KEYWORDS, rest, maxsplit=1)[0]
    if m := re.match(rf"\s*{_EVALUATED}", tail):
        return float(m.group(1))
    if m := re.match(r"\s*=\s*([^;\n]+);", tail):
        return _resolve(m.group(1).strip(), symbols)
    if m := re.match(rf"\s*{_PRM}", tail):
        return _value(m.group(1))
    return None


def read_topas_inp(path: str | Path) -> TopasModel:
    """Parse a ``.inp``. Raises :class:`TopasInpError` naming the file and line."""
    path = Path(path)
    try:
        raw = path.read_text(encoding="utf-8", errors="ignore")
    except OSError as exc:
        raise TopasInpError(f"{path}: cannot read: {exc}") from exc
    active = resolve_ifdefs(strip_comments(raw))
    model = TopasModel()
    symbols = symbol_table(active)

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
            m = re.search(rf"^\s*{key}\s+{_FLAG}?(?:{_NAME}\s+{_FLAG}?)?({_NUM}`?)([^\n]*)",
                          chunk, re.M)
            if not m:
                continue
            value = _value(m.group(1))
            if value is None:
                continue
            phase.cell[key] = value
            if (free := refined(key, m.group(0))) is not None:
                phase.vary[key] = free
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
        phase.scale = _field("scale", chunk, symbols)
        phase.weight_percent = _field("weight_percent", chunk, symbols)
        if (free := refined("scale", chunk)) is not None:
            phase.vary["scale"] = free

        site_lines = [ln for ln in chunk.split("\n") if re.match(r"\s*site\s", ln)]
        for line in site_lines:
            label = re.match(r"\s*site\s+(\S+)", line)
            occ = re.search(r"\bocc\s+(\S+)", line)
            if not (label and occ):
                raise TopasInpError(
                    f"{path}: {phase.name}: no label/occ in site line: {line.strip()!r}")
            coords = {}
            for axis in "xyz":
                v = _field(axis, line, symbols)
                if v is None:
                    raise TopasInpError(
                        f"{path}: {phase.name}: cannot read {axis} from "
                        f"site line: {line.strip()!r}")
                coords[axis] = v
            beq = _field("beq", line, symbols)
            occupancy = _occupancy(line[occ.end():], symbols)
            vary = {f: free for f in ("x", "y", "z", "beq", "occ")
                    if (free := refined(f, line)) is not None}
            phase.sites.append(TopasSite(
                label=label.group(1), species=normalize_species(occ.group(1)),
                occupancy=occupancy if occupancy is not None else 1.0,
                beq=beq if beq is not None else 0.5, vary=vary, **coords))
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
            value = c.get(key, default)
            kw = {}
            # A stated bound that excludes the stated value is dropped, not
            # enforced. The two disagree in real files — TOPAS writes the
            # converged value back into the .inp, so an edited or re-run bound
            # can end up on the wrong side of it — and the *value* is the
            # measurement while the bound is the author's search window. Keeping
            # both raised a pydantic error out of a reader, which this package's
            # readers may not do.
            if lo is not None and value >= lo:
                kw["min"] = lo
            if hi is not None and value <= hi:
                kw["max"] = hi
            if (free := ph.vary.get(key)) is not None:
                kw["vary"] = free
            return rx.Parameter(value=value, **kw)

        cell = rx.Cell(a=_p("a", c["a"]), b=_p("b", c["a"]), c=_p("c", c["a"]),
                       alpha=_p("al", 90.0), beta=_p("be", 90.0), gamma=_p("ga", 90.0))
        def _sp(site, field_: str, value: float, **kw):
            """A site parameter, carrying the file's own refine flag."""
            if (free := site.vary.get(field_)) is not None:
                kw["vary"] = free
            return rx.Parameter(value=value, **kw)

        atoms = [rx.Atom(label=s.label, species=s.species,
                         x=_sp(s, "x", s.x), y=_sp(s, "y", s.y), z=_sp(s, "z", s.z),
                         occ=_sp(s, "occ", s.occupancy),
                         biso=_sp(s, "beq", max(s.beq, 0.0), min=0.0, max=25.0))
                 for s in ph.sites]
        phases.append(rx.Phase(
            name=ph.name, space_group=ph.space_group, cell=cell, atoms=atoms,
            scale=rx.Parameter(value=ph.scale or 1e-4, min=0.0,
                               transform="softplus",
                               **({"vary": ph.vary["scale"]}
                                  if "scale" in ph.vary else {}))))
    return rx.Structure(phases=phases)

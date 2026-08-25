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
   A ``'`` inside a ``"…"`` string is *not* a comment, though: cutting there
   turned ``xdd "C:\\data\\o'brien.xy"`` into ``C:\\data\\o`` and a phase called
   ``d'Alembert`` into ``d``, a silently mislabelled phase.
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

**A silent default or a clamp is the same bug as a wrong parse.** Four places
answered where they should have refused, and each returned a number no file
states: a *stated* cell key that could not be read fell back on ``c["a"]`` or
90° (so a monoclinic phase arrived orthorhombic — see
:func:`read_topas_inp`'s cell loop); a ``str`` chunk that ran into the next
block took the neighbour's cell, scale and weight_percent (:data:`_BLOCK`); a
schema refusal raised above the boundary that converts it; and a negative
``beq`` was moved to zero (:func:`to_structure`). ``STR(...)`` is the same
class one level up — a phase the reader cannot expand is refused by name
(:data:`_STR_MACRO`), never answered with "this file has no phases".

**One grammar, read once, and it carries the flag with the value.** Every scalar
in a ``.inp`` — a coordinate, a cell edge, a scale, an occupancy, a lattice
macro's argument — is the same four spellings of one production, so
:func:`_read_tail` is the only place that knows them and every caller goes
through it. Five ad-hoc spellings of it disagreed on real files before WP-1118;
a *sixth*, the cell loop's own regex, then disagreed with the unified one about
the ``= expr;: value`` tail and cost **320 phases in 15 archive files**. The
flag travels with the value for the same reason: a second regex re-reading the
line for the flag alone lost it wherever the two grammars disagreed, and a lost
tri-state reads as "held", which is a confident wrong protocol.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path

from ..formats.base import decode

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
#: 0.9, and ``Cubic_(4.15689)`` came back 0.15689, a wrong number with nothing
#: raised, which is the whole failure class this reader exists to avoid.
_NAME = r"[A-Za-z_]\w*"

#: Refinement flags, in every spelling the archive actually contains: ``@``
#: (refine), ``!`` (fix), and either followed by a comma — ``@, 0.0013`` is
#: how TOPAS writes a refined value it did not name, and appears on 100+ files
#: here. Flags may sit before the name, after it, or both.
_FLAG = r"(?:[@!]\s*,?\s*)"


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
    #: TOPAS's B, exactly as the file states it — ``None`` where the site line
    #: gives no ``beq`` (WP-1118). :class:`TopasModel` is "what a ``.inp``
    #: states", and a seeded 0.5 a caller cannot tell from a stated 0.5 is the
    #: silent-default class this reader exists to avoid; the 0.5 seed a builder
    #: needs is applied in :func:`to_structure`, not stored here. ``occ``'s 1.0
    #: default stays — it is the *format's* own default, measured on three
    #: files, not a value this reader invents.
    beq: float | None = None
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
class SkippedBlock:
    """A ``str`` block this reader saw but could not read as a phase — it stated
    no ``phase_name`` or no ``space_group``, so naming it would be the
    neighbour's-name bleed :data:`_BLOCK` fixes. Recorded rather than passed
    over in silence (WP-1118), and recording *what it lacked and what it did
    carry*, so :func:`to_structure` can tell a block that plainly states a cell
    or a site — a phase in all but its name, whose loss unbalances the weight
    fractions — from an empty one."""

    lacked: str                       # "phase_name", "space_group", or both
    n_sites: int
    cell: dict = field(default_factory=dict)
    scale: float | None = None
    weight_percent: float | None = None

    def __str__(self) -> str:
        carried = []
        if self.cell:
            carried.append("a cell (" + ", ".join(sorted(self.cell)) + ")")
        if self.scale is not None:
            carried.append(f"scale {self.scale}")
        if self.weight_percent is not None:
            carried.append(f"weight_percent {self.weight_percent}")
        tail = f", carrying {', '.join(carried)}" if carried else ""
        return (f"a `str` block stating {self.n_sites} site line"
                f"{'' if self.n_sites == 1 else 's'} but no {self.lacked}{tail}")


@dataclass
class TopasModel:
    """What a ``.inp`` states. Deliberately not a :class:`Structure` yet — the
    caller decides which phases to keep and how to seed what the file omits."""

    phases: list = field(default_factory=list)
    #: The file this was read from, so :func:`to_structure` can name it in a
    #: refusal — a reader raises naming the file, never its parser's exception,
    #: and pydantic's report names a field rather than a file.
    path: str | None = None
    anode: str | None = None          # "CuKa" from a CuKa5(...) macro
    emission_macro: str | None = None  # "CuKa5" verbatim, for provenance
    wavelength: float | None = None    # only if written as an explicit la/lo
    goniometer_radius_mm: float | None = None
    geometry: str | None = None
    r_wp: float | None = None
    gof: float | None = None
    data_files: list = field(default_factory=list)
    background_terms: int | None = None
    #: One :class:`SkippedBlock` per ``str`` block that states no ``phase_name``
    #: or no ``space_group``, saying what it lacked and what it did carry (its
    #: cell, scale and weight_percent). Such a
    #: block cannot be read as a phase and is not one this reader may name —
    #: taking the name from the next block is exactly the bleed :data:`_BLOCK`
    #: fixes. But *silence* about it is the other half of that bug, because the
    #: zero-phase refusal then reports "a Pawley or indexing-only .inp is legal
    #: and has none" about a file carrying a cell and two sites. So it is
    #: recorded, and :func:`to_structure` quotes it instead.
    skipped_blocks: list = field(default_factory=list)


def strip_comments(text: str) -> str:
    """Remove ``/* */`` blocks and ``'`` line comments (rule 1).

    A ``'`` inside a ``"…"`` string is a character, not a comment opener: TOPAS
    quotes file paths and phase names, and both may hold an apostrophe. Cutting
    at the first ``'`` regardless read ``xdd "C:\\data\\o'brien.xy"`` as the
    data file ``C:\\data\\o`` and named a phase ``d`` — a truncated path is a
    loud failure later, but a truncated ``phase_name`` is a silently
    mislabelled phase, which is the class this reader exists to avoid. Nothing
    in the 606-file archive carries one, so this is latent rather than measured.

    The block and line comments are stripped in **one pass**, not block-first,
    because the two interact: the ``'/*`` idiom comments out the block-comment
    *delimiter itself*, so the phase between a ``'/*`` and a ``'*/`` is **live**
    (real, measured — ``TOF neutron input LSF.inp`` in the ORNL NOMAD archive
    uses it to enable one of three refinements). Stripping ``/* */`` first with
    a regex read the ``/*`` in ``'/*`` as opening a block and deleted that live
    phase. So a ``/*`` or ``*/`` preceded on its line by an unquoted ``'`` is
    itself comment text and opens/closes nothing: the ``'`` line comment is
    seen first, char by char, and the delimiter never reached.
    """
    out_lines: list[str] = []
    in_block = False
    for line in text.split("\n"):
        result: list[str] = []
        i, n, quoted = 0, len(line), False
        while i < n:
            if in_block:
                end = line.find("*/", i)
                if end == -1:
                    i = n
                else:
                    in_block = False
                    i = end + 2
                continue
            ch = line[i]
            if ch == '"':
                quoted = not quoted
                result.append(ch)
                i += 1
            elif quoted:
                result.append(ch)
                i += 1
            elif ch == "'":
                break  # line comment: the rest of the line is dead
            elif line.startswith("/*", i):
                in_block = True
                i += 2
            else:
                result.append(ch)
                i += 1
        out_lines.append("".join(result))
    return "\n".join(out_lines)


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


def _resolve(expr: str, symbols: dict[str, float]) -> float | None:
    """An equation's value: substitute named parameters, then evaluate.

    Longest name first, so a name that is a prefix of another is never
    half-replaced (``Fe1_1_x`` inside ``Fe1_1_x2``).
    """
    for sym in sorted(symbols, key=len, reverse=True):
        if sym in expr:
            expr = re.sub(rf"\b{re.escape(sym)}\b", repr(symbols[sym]), expr)
    return _arith(expr)


# --------------------------------------------------------------- one grammar

#: An equation *and the value TOPAS evaluated it to*: ``= 1/4 + Fe1_1_dx;: 0.25``.
#: The ``;:`` tail is the most authoritative number in the file — it is what the
#: converged refinement actually used, so it is preferred over re-evaluating the
#: expression here, which would need every symbol the expression reaches. The
#: write-back backtick sits *after* that tail, which is where a flag regex
#: reading the line a second time could not reach it.
_TAIL_EVALUATED = re.compile(
    rf"\s*(?P<pre>{_FLAG})?(?:(?P<name>{_NAME})\s*)?(?P<post>{_FLAG})?"
    rf"=\s*[^;\n]*;\s*:\s*(?P<value>{_NUM})(?P<tick>`?)")

#: An equation with no evaluated tail — ``x = 1/3;``, ``x Zr1_x =1/2;``,
#: ``a = mlpa;``. This reader has to evaluate it itself, against
#: :func:`symbol_table`, and an unresolvable one is None and still raises.
_TAIL_EQUATION = re.compile(
    rf"\s*(?P<pre>{_FLAG})?(?:(?P<name>{_NAME})\s*)?(?P<post>{_FLAG})?"
    rf"=\s*(?P<expr>[^;\n]+);")

#: A stated number: ``[flags] [name] [flags] <number>[`]``. The trailing
#: ``_esd`` and ``_LIMIT_*`` annotations need no stripping, because ``_`` ends
#: :data:`_NUM` — ``5.17632205e-006_3.88e-006_LIMIT_MIN_1e-015`` is one match.
_TAIL_VALUE = re.compile(
    rf"\s*(?P<pre>{_FLAG})?(?:(?P<name>{_NAME})\s+(?P<post>{_FLAG})?)?"
    rf"(?P<value>{_NUM})(?P<tick>`?)")

#: A1/A2/A3 are x/y/z, written as a macro because the axis letter does not
#: appear on the line at all. The flag sits *inside* the parenthesis, which is
#: the one place the flag grammar could not follow the value grammar.
_AXIS_MACROS = {
    axis: re.compile(rf"\b{macro}\(\s*(?P<pre>{_FLAG})?(?P<name>{_NAME})\s*,\s*"
                     rf"(?P<value>{_NUM})(?P<tick>`?)")
    for axis, macro in (("x", "A1"), ("y", "A2"), ("z", "A3"))}


@dataclass(frozen=True)
class _Read:
    """One scalar exactly as the file states it.

    ``value`` is None only where an equation could not be resolved — the caller
    is the only place that knows whether that is fatal. ``vary`` is the
    tri-state :func:`refined` returns. ``name`` is the parameter's own name
    where the file gave one, which is what makes the value a *declaration*
    another equation can reference. ``rest`` is the text after the number,
    where a ``min``/``max`` window sits.
    """

    value: float | None
    vary: bool | None
    name: str | None = None
    rest: str = ""


def _flag(*tokens: str | None) -> bool | None:
    """The refine tri-state a set of flag tokens and a write-back tick state.

    ``!`` outranks everything: TOPAS writes the converged value back into a
    *held* parameter too, so a backtick beside a ``!`` is a write, not a claim
    that the parameter moved.
    """
    joined = "".join(t or "" for t in tokens)
    if "!" in joined:
        return False
    if "@" in joined or "`" in joined:
        return True
    return None


def _read_tail(tail: str, symbols: dict[str, float]) -> _Read | None:
    """The one grammar, applied to the text that follows a keyword.

    Three forms, all real, in decreasing order of authority: TOPAS's own
    evaluated tail (preferred, because it is what the converged refinement
    used), an equation this reader has to evaluate itself, and a stated number.
    The fourth spelling — the ``A1(…)`` coordinate macro — is not a tail at all
    and is handled by :func:`_read`. Each form yields the value *and* its flag
    off a single match, which is what stops the two grammars drifting apart.
    """
    if m := _TAIL_EVALUATED.match(tail):
        return _Read(float(m["value"]), _flag(m["pre"], m["post"], m["tick"]),
                     m["name"], tail[m.end():])
    if m := _TAIL_EQUATION.match(tail):
        return _Read(_resolve(m["expr"].strip(), symbols),
                     _flag(m["pre"], m["post"]), m["name"], tail[m.end():])
    if m := _TAIL_VALUE.match(tail):
        return _Read(float(m["value"]), _flag(m["pre"], m["post"], m["tick"]),
                     m["name"], tail[m.end():])
    return None


#: Keywords that can follow ``occ`` on a site line. They bound the occupancy's
#: text, which is what makes an *absent* occupancy different from one whose
#: value is the next keyword's: ``occ Sr+2 beq 0.765`` is a full occupancy and a
#: B of 0.765, and reading the token after the species gave it occupancy 0.765.
_SITE_KEYWORDS = r"\b(?:beq|ADPs|vcocc|rand_xyz|num_posns|u\d\d|site)\b"


def _read(name: str, text: str, symbols: dict[str, float] | None = None) -> _Read | None:
    """What ``text`` states for the keyword ``name``, value and flag together.

    Two keywords are not simply "name then value" and both are handled here
    rather than by a second grammar:

    * ``x``/``y``/``z`` may be written as the ``A1(…)``/``A2(…)``/``A3(…)``
      macro, whose flag is inside the parenthesis.
    * ``occ``'s next token is a **species**, not a parameter name. The grammar
      has one name slot and on an ``occ`` line the species consumes it, so
      ``occ Ca @ 0.6`` used to work by accident while ``occ Ca+2 @ 0.6`` and
      ``occ Ca !n 0.6`` both lost their flag — 38 real site lines, including a
      Si/Ge solid solution deliberately held at 0.8/0.2. Widening
      :data:`_NAME` to admit ``+``/``-`` is not the fix: it is load-bearing
      everywhere else, and a held-by-default occupancy cannot be told from a
      held-by-file one.
    """
    symbols = symbols or {}
    if (macro := _AXIS_MACROS.get(name)) and (m := macro.search(text)):
        return _Read(float(m["value"]), _flag(m["pre"], m["tick"]), m["name"],
                     text[m.end():])
    for m in re.finditer(rf"\b{re.escape(name)}\b", text):
        tail = text[m.end():]
        if name == "occ":
            if not (species := re.match(r"\s*\S+", tail)):
                continue
            tail = re.split(_SITE_KEYWORDS, tail[species.end():], maxsplit=1)[0]
        if (read := _read_tail(tail, symbols)) is not None:
            return read
    return None


#: An occupancy value is bounded by the **next ``occ``** as well as by the site
#: keywords, so each ``occ`` token on a mixed site reads its own value and no
#: other's — ``occ Al+3 0.9 occ Cr+3 0.1`` is two pairs, not one value read off
#: whichever match a separate walk reached first.
_OCC_TERMINATOR = re.compile(r"\bocc\b|" + _SITE_KEYWORDS)


def _site_occupancies(text: str, symbols: dict[str, float]) -> list[tuple[str, "_Read | None"]]:
    """Every ``(species, value-read)`` the ``occ`` tokens of a site segment state,
    in file order (WP-1118, findings 2 and 3).

    A mixed site is written either as two ``site`` lines sharing a label or as
    **one** line carrying several ``occ`` tokens — ``occ Al+3 0.9 occ Cr+3 0.1``.
    The predecessor read the species off the *first* ``\\bocc\\b`` match and the
    value off a *separate* walk that returned the first tail to parse, so three
    things went wrong at once: every species after the first was dropped, and
    ``occ Al+3 occ Cr+3 0.1`` gave **Al** the 0.1 that is Cr's (species from
    match one, value from match two). Here each ``occ`` token is read **once**:
    its species is the token immediately after it, and its value travels with
    that same species, bounded by the next ``occ`` or site keyword so one pair's
    value can never be read off the next.

    The second element is ``None`` where the token states no value at all
    (``occ Al+3`` with nothing after) — the format's own 1.0 default, established
    in round two. A :class:`_Read` whose ``value`` is ``None`` is a *stated*
    value that could not be resolved (``occ Na+1 =mystery;``), which the site
    loop refuses rather than defaulting (finding 4).
    """
    out: list[tuple[str, "_Read | None"]] = []
    for m in re.finditer(r"\bocc\b", text):
        tail = text[m.end():]
        if not (species := re.match(r"\s*(\S+)", tail)):
            continue
        rest = _OCC_TERMINATOR.split(tail[species.end():], maxsplit=1)[0]
        out.append((species.group(1), _read_tail(rest, symbols)))
    return out


def _field(name: str, line: str, symbols: dict[str, float] | None = None) -> float | None:
    """One field's value, or None where the line does not state one (rule 3).

    The value half of :func:`_read`, kept as a name because most callers want
    only the number — the flag half is :func:`refined`, and both come off the
    same match rather than from two regexes over the same line.
    """
    read = _read(name, line, symbols)
    return read.value if read else None


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

    Read off the **same match as the value**, through :func:`_read`, rather
    than by a second regex over the line: the value grammar was unified before
    the flag grammar was, and wherever the two disagreed — the ``A1(@xO3, …)``
    macro, a backtick after a ``;:`` tail, any ``occ`` with a species — the
    flag came back None, which ``rx.Parameter`` then defaults to
    ``vary=False``. The tri-state collapsed to "held" at the one boundary
    where the file had been explicit.
    """
    read = _read(name, text)
    return read.vary if read else None


# -------------------------------------------------------- symbol declarations

#: The keywords this reader reads a value for, and therefore the only places a
#: **name slot** can sit. ``x ph1_O1_x 0.29935`` declares ``ph1_O1_x``, which
#: ``y = ph1_O1_x;`` two tokens later references; refusing that cost 14 of the
#: 606 archive files, the tier-1 Cr2WO6 references among them. ``prm`` and
#: ``local`` are TOPAS's explicit declarations.
#:
#: The *keyword* slot is never a declaration, and that is the whole narrowing:
#: the predecessor swept every ``<name> <number>`` pair in the file, which on a
#: realistic 30-line file bound 21 symbols including ``beq``, ``bkg``, ``gof``,
#: ``min``, ``max``, ``r_wp``, ``x``, ``y``, ``z``. Nothing raises when one is
#: substituted into an equation — ``_resolve`` substitutes and ``_arith``
#: returns a plausible number — and ``setdefault`` meant a real ``prm x 0.9999``
#: lost to an earlier site's ``x 0.1111``.
_DECLARING_KEYWORDS = ("prm", "local", "a", "b", "c", "al", "be", "ga",
                       "x", "y", "z", "beq", "occ", "scale", "weight_percent")

_DECLARATION = re.compile(rf"\b(?P<kw>{'|'.join(_DECLARING_KEYWORDS)})\b")

#: A macro's *named* argument is a declaration too — ``CS_L(csl1, 210.4)`` names
#: a crystallite size an equation elsewhere may reach, and ``Cubic_(lpa …)``
#: names a lattice parameter. Comma- or space-separated, because TOPAS writes
#: both, and bounded by the separator so a nameless argument cannot be read as
#: a name.
_DECLARED_ARG = re.compile(
    rf"[(,]\s*(?:{_FLAG})?(?P<name>{_NAME})\s*[,\s]\s*(?:{_FLAG})?"
    rf"(?P<value>{_NUM})")


def symbol_table(text: str) -> dict[str, float]:
    """Every parameter the file **declares**, by name.

    Needed because a coordinate equation routinely *references another
    parameter* rather than being self-contained: ``y = ph1_O1_x;`` is how a
    tetragonal Cr2WO6 oxygen says y is tied to x. Refusing those cost 14 of the
    606 archive files, so the reference is resolved instead — and an
    unresolvable one still returns None and still raises, because inventing a
    coordinate is the one outcome worse than refusing to read the file.

    A *declaration*, never any ``<name> <number>`` pair: see
    :data:`_DECLARING_KEYWORDS` for what that bought and what it cost.
    """
    out: dict[str, float] = {}
    for m in _DECLARATION.finditer(text):
        tail = text[m.end():]
        if m["kw"] == "occ":
            # `occ La 1.` puts the *species* where the name slot is, so the old
            # sweep bound `La` to 1.0 and a `prm La` would silently have got
            # lanthanum's occupancy. Read past the species, as `_read` does.
            if not (species := re.match(r"\s*\S+", tail)):
                continue
            tail = tail[species.end():]
        read = _read_tail(tail, {})
        # `prm Fe1_1_x = 1/4 + Fe1_1_dx;: 0.25000` binds the evaluated value,
        # which is the whole reason the deeper chain never has to be walked.
        if read is not None and read.name and read.value is not None:
            out.setdefault(read.name, read.value)
    for m in _DECLARED_ARG.finditer(text):
        out.setdefault(m["name"], float(m["value"]))
    return out


# ------------------------------------------------------------ lattice macros

#: The lattice macros this reader implements, keyed to the angles they imply.
#: A macro name and its argument order are **specification facts** (`io/
#: CLAUDE.md`'s rule 2), so each was read off a real archive line rather than
#: guessed: ``Cubic(@ 4.15692`)`` (LaB6_Riet_TCHZ_01.inp:54),
#: ``Tetragonal(@ 4.594290`, @ 2.958587`)`` (d5_05005_pawley_01.inp:38),
#: ``Hexagonal(@ 3.613074`, @ 12.037126`)`` (BL104_B_1.inp:87) and
#: ``Trigonal( 12.695126, 37.972985)`` (AT027-23_…-mythen_summed_rf_fin:90).
#: One argument means a = b = c; two mean a = b and c, in that order.
_LATTICE_MACROS: dict[str, tuple[float, float, float]] = {
    "Cubic": (90.0, 90.0, 90.0),
    "Tetragonal": (90.0, 90.0, 90.0),
    "Hexagonal": (90.0, 90.0, 120.0),
    "Trigonal": (90.0, 90.0, 120.0),
}

#: Lattice macros TOPAS has that no archive file *uses*. Each appears only
#: inside a ``'`` comment — ``'Rhombohedral(@ #, @ #)`` in `D20.inp`'s template
#: is a length and an angle in an order nothing here fixes — so the argument
#: order is unevidenced, and a wrong order is a wrong cell with nothing raised.
#: Refused by name rather than parsed on a guess, and only where the macro is
#: the phase's *only* cell: beside explicit ``a``/``b``/``c`` lines there is
#: nothing left to get wrong.
_UNEVIDENCED_MACROS = ("Rhombohedral", "Orthorhombic", "Monoclinic", "Triclinic")

#: What **ends** a ``str`` block. A `.inp` has no closing brace, so a phase's
#: text runs to the next block opener — and splitting on ``str`` alone made a
#: trailing ``hkl_Is``/``xo_Is`` Pawley block part of the phase above it, so
#: `_read` swept the neighbour's numbers: `W02_DR_11bmb_3858_pawley_Nb2O5.inp`
#: gave tungsten b = 3.814 and c = 19.299 off the Nb2O5 ``load hkl_m_d_th2 I``
#: table (a d-spacing column, read as a cell edge), and a `scale` or a
#: `weight_percent` the ``str`` block itself omits is still read off the block
#: below with nothing raised. Each opener is a **specification fact**
#: (`io/CLAUDE.md`'s rule 2) and the ones with a count are what the archive
#: states at the start of a line: ``str`` (1601), ``xdd`` (609),
#: ``xo_Is`` (277), ``hkl_Is`` (139), ``STR`` (7), ``fit_obj`` (2).
#: ``d_Is``, ``xdd_scr`` and ``xdd_sum`` occur in no file here and are listed
#: because they open a block of the same two kinds — a peak-phase and a
#: dataset — so leaving them out could only re-create the bleed. ``macro`` is
#: **not** here (WP-1118): it opens no phase and no dataset — it is a reusable
#: *definition* — so treating it as an opener truncated any ``str`` a ``macro
#: dummy { 1 }`` sat inside, dropping every site below it, and the per-phase
#: count guard was blind to it because both sides of that guard read the same
#: truncated chunk. Macro definitions are excised whole by
#: :func:`_excise_macro_defs` before the file is split, braces and body and all.
_BLOCK_OPENERS = ("str", "hkl_Is", "xo_Is", "d_Is", "xdd_scr", "xdd_sum",
                  "xdd", "fit_obj", "STR")

#: ``xdd`` must follow ``xdd_scr``/``xdd_sum`` in the alternation above, and the
#: pattern is anchored with ``[ \t]`` rather than ``\s`` because ``\s`` matches
#: the newline and would let one match span two lines.
_BLOCK = re.compile(rf"^[ \t]*(?P<kw>{'|'.join(_BLOCK_OPENERS)})\b", re.M)

#: TOPAS's ``STR(...)`` macro expands to a whole ``str`` block. Its definition
#: lives in a macro library this reader does not have and may not reproduce
#: (``ATTRIBUTION.md``'s fence), so the phases such a file states cannot be
#: read — and *saying nothing* is the F2 failure again: the file plainly
#: contains ``STR(``, and answering "a Pawley or indexing-only .inp is legal
#: and has none" is a confident wrong diagnosis about it. Refused by name.
_STR_MACRO = re.compile(r"^[ \t]*STR\s*\(([^)\n]*)\)", re.M)

#: What declares a capillary (Debye-Scherrer) geometry, as the archive spells
#: it: the two ``Cylindrical_…`` correction macros and TOPAS's ``capillary_…``
#: keywords (``capillary_diameter_mm``, ``capillary_parallel_beam``,
#: ``capillary_divergent_beam``, ``capillary_u_cm_inv``), which is how the 26
#: capillary files here say it. Anchored to the start of a line because a
#: geometry is a **statement**: the predecessor matched
#: ``Cylindrical_|capillary|Debye`` case-insensitively over the whole file, so a
#: phase called ``Debye_test_material`` flipped a file carrying ``Radius(217.5)``
#: and ``LP_Factor(26.4)`` — unambiguously Bragg-Brentano — and so did a data
#: file named ``debye_run3.xy`` and a ``prm capillary_diam``. ``Debye`` itself is
#: gone: it names no TOPAS keyword and occurs in none of the 606 files.
_CAPILLARY = re.compile(r"^[ \t]*(?:capillary_\w+|Cylindrical_\w*\s*\()", re.M)


def _lattice_macro(chunk: str, symbols: dict[str, float]) -> tuple[dict, dict] | None:
    """The cell and refine flags a lattice macro states, or None if it states no
    complete one. The first macro in :data:`_LATTICE_MACROS` that reads
    completely wins, which is deterministic and only ever matters in a chunk
    holding two."""
    for name, angles in _LATTICE_MACROS.items():
        if not (m := re.search(rf"\b{name}_?\(([^)\n]*)\)", chunk)):
            continue
        reads = [_read_tail(arg, symbols) for arg in m.group(1).split(",")]
        lengths = [r for r in reads if r is not None and r.value is not None]
        if not lengths or (name != "Cubic" and len(lengths) < 2):
            continue
        a, c = lengths[0], lengths[-1]
        cell = {"a": a.value, "b": a.value, "c": c.value,
                "al": angles[0], "be": angles[1], "ga": angles[2]}
        vary = {key: read.vary
                for keys, read in (("ab", a), ("c", c))
                for key in keys if read.vary is not None}
        return cell, vary
    return None


# --------------------------------------------------- whitespace-insensitive scan

#: A ``macro name [(...)] { ... }`` definition head. The body is brace-balanced
#: and excised by :func:`_excise_macro_defs`, so this only has to find the open.
_MACRO_DEF = re.compile(r"\bmacro\b\s*\w*\s*(?:\([^)]*\))?\s*\{")


def _blank(text: str) -> str:
    """Replace every non-newline character with a space, so a span can be
    removed from a token scan without moving any line or shifting any offset."""
    return re.sub(r"[^\n]", " ", text)


def _excise_macro_defs(text: str) -> str:
    """Blank ``macro name [(...)] { ...balanced... }`` definitions (WP-1118).

    A macro definition is neither a phase nor a dataset, so it must not open or
    end a block — and its body's ``site`` and cell tokens must not be swept into
    whatever phase held it. Removed here, before the file is split, with a
    brace counter rather than a regex because a macro body may itself nest
    braces. An unterminated definition (a truncated file) blanks to EOF, which
    is a loud absence rather than a bad parse.
    """
    out: list[str] = []
    i, n = 0, len(text)
    while i < n:
        m = _MACRO_DEF.search(text, i)
        if not m:
            out.append(text[i:])
            break
        out.append(text[i:m.start()])
        depth, j = 0, m.end() - 1          # j points at the opening '{'
        while j < n:
            if text[j] == "{":
                depth += 1
            elif text[j] == "}":
                depth -= 1
                if depth == 0:
                    j += 1
                    break
            j += 1
        out.append(_blank(text[m.start():j]))
        i = j
    return "".join(out)


#: A cell key at the **start of its own line** — where the real cell edges
#: resume below a site block. It ends a ``site`` segment (see :func:`_blank_sites`):
#: a continuation like ``beq b 0.5`` starts with ``beq`` and is site text, while
#: ``b 6.0`` starts with the edge itself and is the cell. The two-letter keys
#: precede the one-letter ones so ``\b`` never truncates ``al``/``be``/``ga``.
_CELL_LINE_START = re.compile(r"(?m)^[ \t]*(?:al|be|ga|a|b|c)\b")


def _masked(text: str) -> str:
    """**The** masked text every token scan reads (WP-1118).

    The scan is token-oriented — a key wherever it sits, because TOPAS is
    whitespace-insensitive and ``a 5.4 b 6.1 c 7.2`` is a whole cell on one
    line. With the line anchor gone, the *only* safety is that every span a key
    (or a ``site`` token) must not be read from is blanked first, once, into a
    text every scan shares — the cell-key scan, the site split, and the
    file-level site count — so a span nobody blanked cannot be read by one scan
    while another is safe. The unmasked text stays for the messages, which quote
    the original line. Blanked here, offset-for-offset (:func:`_blank`):

    * a ``"…"`` string, so the ``a`` in ``space_group "P21/a"``, or the word in
      ``xdd "C:\\data\\site\\run1.xy"``, or a phase name, is not a token;
    * a macro's parenthesised arguments, so a named ``a`` in ``Cubic_(a, …)`` is
      the macro's argument and ``site`` in ``Out_X_Ycalc("site.xy")`` is not a
      site (the reason the cell scan's line anchor once existed);
    * a ``prm``/``local`` declaration to end of line, so ``prm a 0.9`` declares a
      symbol and is not an ``a`` line;
    * the ``space_group`` and ``phase_name`` **values**, over the same span the
      reader's own value-regexes consume, so an unquoted Hermann-Mauguin symbol
      ``P 1 21/c 1`` does not read ``/c 1`` as ``c = 1.0`` — legal, and the
      reader's own regex accepts it, so the mask has to know the spelling too.

    A ``site`` **segment** is not blanked here — the site split and the count
    need the ``site`` tokens to survive. :func:`_blank_sites` blanks the segments
    on top of this, for the cell scan alone.
    """
    masked = re.sub(r'"[^"\n]*"', lambda m: _blank(m.group()), text)
    masked = re.sub(r"\w+\([^)]*\)", lambda m: _blank(m.group()), masked)
    masked = re.sub(r"\b(?:prm|local)\b[^\n]*", lambda m: _blank(m.group()),
                    masked)
    # `[ \t]+`, not `\s+`: the reader's own value-regex (`\s+`) never crosses a
    # newline on the original text, because a quote or the symbol's first letter
    # follows the space — but here the value has already been quote-blanked to
    # spaces, so `\s+` would run through the newline and blank the next line's
    # `a 5.0`. Confined to one line, this blanks exactly the span the reader reads.
    for kw in ("space_group", "phase_name"):
        masked = re.sub(rf'(\b{kw}[ \t]+"?)([^"\n]+)',
                        lambda m: m.group(1) + _blank(m.group(2)), masked)
    return masked


def _blank_sites(masked: str) -> str:
    """``masked`` with each ``site`` **segment** blanked, for the cell-key scan.

    A ``site`` declaration does not end at the newline: its fields may continue
    on the next line (``beq b 0.5`` on its own), and the ``b`` there naming the
    ``beq`` parameter is not the cell edge ``b`` (WP-1118). So the segment runs
    from a ``site`` token to the next ``site``, the chunk end, **or** the next
    line that begins with a cell edge — whichever comes first. The last of those
    is the one refinement to the reviewer's "to the next site or block end":
    where the site block sits *above* the cell lines, "block end" would blank the
    real ``a``/``b``/``c`` below it and default the cell, so the segment stops
    where the edges resume at a line start instead.
    """
    site_pos = [m.start() for m in re.finditer(r"\bsite\b", masked)]
    if not site_pos:
        return masked
    cell_pos = [m.start() for m in _CELL_LINE_START.finditer(masked)]
    chars = list(masked)
    for i, start in enumerate(site_pos):
        nxt_site = site_pos[i + 1] if i + 1 < len(site_pos) else len(masked)
        nxt_cell = next((p for p in cell_pos if p > start), len(masked))
        for j in range(start, min(nxt_site, nxt_cell)):
            if chars[j] != "\n":
                chars[j] = " "
    return "".join(chars)


def _cell_search_text(chunk: str) -> str:
    """The cell-scan view of a chunk: :func:`_masked` with the ``site`` segments
    blanked on top (:func:`_blank_sites`). Kept as a named successor so a test
    can pin what survives a chunk without a whole file per hole."""
    return _blank_sites(_masked(chunk))


_CELL_KEYS = ("a", "b", "c", "al", "be", "ga")


def _cell_reads(cell_scan: str, symbols: dict[str, float]) -> dict[str, float]:
    """Best-effort ``{key: value}`` for the cell keys an *already cell-masked*
    text states, raising nothing — for recording what a :class:`SkippedBlock`
    carried."""
    out: dict[str, float] = {}
    for key in _CELL_KEYS:
        for line in cell_scan.split("\n"):
            if re.search(rf"\b{key}\b", line):
                read = _read(key, line, symbols)
                if read is not None and read.value is not None:
                    out[key] = read.value
                    break
    return out


def read_topas_inp(path: str | Path) -> TopasModel:
    """Parse a ``.inp``. Raises :class:`TopasInpError` naming the file and line."""
    path = Path(path)
    try:
        raw_bytes = path.read_bytes()
    except OSError as exc:
        raise TopasInpError(f"{path}: cannot read: {exc}") from exc
    # `base.decode` is the seam `head()` already goes through, shared rather
    # than duplicated: a `read_text(encoding="utf-8")` on a UTF-16 export gave
    # zero phases and `to_structure` then reported "a Pawley or indexing-only
    # .inp is legal and has none" — a confident wrong diagnosis of a decode
    # failure, which is the class this reader exists to remove.
    raw, codec, _bom = decode(raw_bytes)
    # What a mark cannot name is refused, per `io/CLAUDE.md`'s `xy` row:
    # ASCII-range UTF-16 is *valid* UTF-8 with interleaved NULs, so a surviving
    # NUL means no byte-order mark said which of LE and BE this is. Guessing is
    # a repair this reader could not say it made.
    if "\x00" in raw:
        raise TopasInpError(
            f"{path}: not text this reader can decode — NUL bytes survive a "
            f"{codec} decode, which is what an ASCII-range UTF-16 export with "
            f"no byte-order mark looks like. Re-save it as UTF-8.")
    # Macro definitions are excised before anything reads the text: they open no
    # block (so they may not end a `str`), and their bodies' `site`/cell tokens
    # are not any phase's — see `_excise_macro_defs`.
    active = _excise_macro_defs(resolve_ifdefs(strip_comments(raw)))
    # THE masked text, built once and sliced by every token scan below (the
    # cell-key scan, the site split, the file-level site count) — offset-for-
    # offset with `active`, so a slice of one indexes the other. The mask is the
    # invariant that keeps a token-oriented scan honest; see `_masked`.
    masked = _masked(active)
    model = TopasModel(path=str(path))
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
    model.geometry = ("debye_scherrer" if _CAPILLARY.search(active)
                      else "bragg_brentano")
    if m := re.search(rf"bkg\s*((?:\s*@?\s*{_NUM}`?)+)", active):
        model.background_terms = len(re.findall(_NUM, m.group(1)))
    model.data_files = [d.strip() for d in re.findall(r'xdd\s+"?([^"\n]+)', active)]

    # A phase this reader cannot read is refused by name, never left out: the
    # five archive files whose every phase opens `STR(R-3)` came back with zero
    # phases and were then diagnosed as legal Pawley inputs.
    if m := _STR_MACRO.search(active):
        n = len(_STR_MACRO.findall(active))
        raise TopasInpError(
            f"{path}: {n} phase{'' if n == 1 else 's'} here open with TOPAS's "
            f"`STR(...)` macro (first: STR({m.group(1).strip()})), which expands "
            f"to a whole `str` block from a macro library this reader does not "
            f"have and may not reproduce. Reading on would report no phase at "
            f"all — 'a Pawley or indexing-only .inp is legal and has none' — "
            f"about a file that plainly states {n}.")

    # A `str` block ends at the next block opener of any kind, not at the next
    # `str`: see `_BLOCK_OPENERS` for the numbers, and `test_projects_topas.py`
    # for the neighbour's cell, scale and weight_percent this stops arriving on
    # the phase above.
    openers = list(_BLOCK.finditer(active))
    parsed_site_tokens = 0        # site *tokens* read into phases, not atoms
    for index, opener in enumerate(openers):
        if opener["kw"] != "str":
            continue
        end = (openers[index + 1].start() if index + 1 < len(openers)
               else len(active))
        chunk = active[opener.end():end]
        mchunk = masked[opener.end():end]      # the same span of THE masked text
        name = re.search(r'phase_name\s+"?([^"\n]+)', chunk)
        sg = re.search(r'\bspace_group\s+"?([^"\n]+)', chunk)
        # A *magnetic* space group is a construct this package has no model for,
        # and dropping it silently would return a nuclear-only structure that
        # looks complete. WP-1118's rule: report or refuse, never drop. Caught
        # here rather than by the regex because `mag_space_group 62.448` used to
        # match the unanchored `space_group` and arrive as the symbol "62.448".
        if mag := re.search(r"\bmag_space_group\s+(\S+)", chunk):
            raise TopasInpError(
                f"{path}: {name.group(1).strip() if name else '?'}: magnetic space "
                f"group {mag.group(1)!r} has no counterpart in rietx; reading this "
                f"phase would return a nuclear-only model that looks complete")
        if not (name and sg):
            # Recorded rather than passed over in silence: `simulate_Nb_Cu.inp`
            # has a `str` block stating a cell and two sites and no
            # `phase_name`, and it used to arrive named "CaO" with scale 1.0 —
            # both read off the `hkl_Is` block below it. Naming it is the
            # neighbour's number again; saying nothing about it is the
            # confident wrong diagnosis. It records what it lacked *and* what it
            # carried (cell/scale/weight_percent), because that is what lets
            # `to_structure` tell a phase in all but its name from an empty
            # block — and `to_structure` refuses where such a block is dropped.
            n_sites = len(re.findall(r"\bsite\b", mchunk))
            lacks = " or ".join(w for w, got in
                                (("phase_name", name), ("space_group", sg))
                                if not got)
            scale_read = _read("scale", chunk, symbols)
            model.skipped_blocks.append(SkippedBlock(
                lacked=lacks, n_sites=n_sites,
                cell=_cell_reads(_blank_sites(mchunk), symbols),
                scale=scale_read.value if scale_read else None,
                weight_percent=_field("weight_percent", chunk, symbols)))
            continue
        phase = TopasPhase(name=name.group(1).strip(),
                           space_group=normalize_space_group(sg.group(1)))
        # The cell keys are read token-wise (WP-1118): the grammar is unified per
        # keyword but the scan was still per line, and TOPAS is whitespace-
        # insensitive, so `a 5.4 b 6.1 c 7.2` on one line read only `a` and built
        # a=b=c — an orthorhombic phase arrived cubic with nothing raised, and
        # `al 90 be 90 ga 120` read only `al` so a P6/mmm built with gamma 90.
        # The line anchor existed to keep `lpa` inside `Cubic_(lpa …)` off the
        # `a` scan; that job is THE mask's now — `_blank_sites(mchunk)` is the
        # shared masked span with the `site` segments blanked on top, so the key
        # is read wherever it sits in what is left and no `beq b`/`space_group`
        # letter is read as a cell edge.
        masked_lines = list(zip(chunk.split("\n"),
                                _blank_sites(mchunk).split("\n")))
        for key in _CELL_KEYS:
            stated = [(orig, mask) for orig, mask in masked_lines
                      if re.search(rf"\b{key}\b", mask)]
            read = None
            for _orig, mask in stated:
                if (read := _read(key, mask, symbols)) is not None \
                        and read.value is not None:
                    break
                read = None
            if read is None:
                # A **stated** key that could not be read refuses, naming the
                # key and the line. Defaulting it is `to_structure` putting
                # `c["a"]` in for a length or 90° in for an angle, so whether
                # the cell is right turns on whether the author happened to
                # *name* the edge — which no caller can see. `c = a*1.633;`
                # unnamed came back 3.0 for a stated 4.899 (63 % low), and an
                # unresolvable `be = …;` made a monoclinic phase orthorhombic.
                # An *absent* line is a different fact and keeps its default.
                if stated:
                    raise TopasInpError(
                        f"{path}: {phase.name}: cannot read {key} from cell "
                        f"line: {stated[0][0].strip()!r} — the phase states {key} "
                        f"and this reader could not resolve its value, so "
                        f"building it would substitute "
                        f"{'90 deg' if key in ('al', 'be', 'ga') else 'a'} for "
                        f"a number the file states. A phase that states no "
                        f"{key} at all is a different fact and keeps its "
                        f"default.")
                continue
            phase.cell[key] = read.value
            if read.vary is not None:
                phase.vary[key] = read.vary
            # TOPAS bounds a cell explicitly (`min 3.61 max 3.66;`). Those
            # are part of the author's model: without them a phase the data
            # cannot see is a flat direction and its cell runs away.
            lo = re.search(rf"\bmin\s*=?\s*({_NUM})", read.rest)
            hi = re.search(rf"\bmax\s*=?\s*({_NUM})", read.rest)
            if lo or hi:
                phase.cell_limits[key] = (float(lo.group(1)) if lo else None,
                                          float(hi.group(1)) if hi else None)
        if "a" not in phase.cell:
            if macro := _lattice_macro(chunk, symbols):
                phase.cell.update(macro[0])
                phase.vary.update(macro[1])
            elif bad := [n for n in _UNEVIDENCED_MACROS
                         if re.search(rf"\b{n}_?\(", chunk)]:
                raise TopasInpError(
                    f"{path}: {phase.name}: {bad[0]} states this phase's only "
                    f"cell and no file establishes which of its arguments is "
                    f"which, so reading it would be a guess at a cell — write "
                    f"the a/b/c/al/be/ga lines out instead")
        read = _read("scale", chunk, symbols)
        phase.scale = read.value if read else None
        if read is not None and read.vary is not None:
            phase.vary["scale"] = read.vary
        phase.weight_percent = _field("weight_percent", chunk, symbols)

        # Sites are split token-wise, not per line (WP-1118): TOPAS is
        # whitespace-insensitive, so `site A1 … beq b 0.5 site B1 x 0.5 …` is
        # two atoms on one line and a per-line scan read one, dropping the
        # second silently — `_SITE_KEYWORDS` already lists `site` as an
        # occupancy terminator, so the grammar half knew. The boundaries come
        # off THE masked chunk, so a `site` inside a quoted path or a macro
        # (`Out_X_Ycalc("site.xy")`) is not one; the segments are sliced from the
        # *original* chunk, so an `x`/`y`/`z` written as an `A1(…)` coordinate
        # macro — which the mask blanks — is still there to read.
        site_pos = [m.start() for m in re.finditer(r"\bsite\b", mchunk)]
        bounds = site_pos + [len(chunk)]
        site_texts = [chunk[site_pos[i]:bounds[i + 1]]
                      for i in range(len(site_pos))]
        for text in site_texts:
            label = re.match(r"\s*site\s+(\S+)", text)
            occs = _site_occupancies(text, symbols)
            if not (label and occs):
                raise TopasInpError(
                    f"{path}: {phase.name}: no label/occ in site: {text.strip()!r}")
            # One read per field, so the value and its flag come off one match.
            reads: dict[str, _Read] = {}
            for axis in "xyz":
                read = _read(axis, text, symbols)
                if read is None or read.value is None:
                    raise TopasInpError(
                        f"{path}: {phase.name}: cannot read {axis} from "
                        f"site line: {text.strip()!r}")
                reads[axis] = read
            # A **stated** `beq` the reader cannot resolve refuses, naming the
            # line, exactly as `x` on the same line already does — defaulting it
            # is seeding 0.5 for a number the file states, the silent-default
            # class this reader exists to avoid (WP-1118, finding 4). A site that
            # states no `beq` at all is a different fact: it keeps the None that
            # becomes the 0.5 seed at build time, so `model.phases` stays "what
            # the file states" and a caller can tell a seed from a stated value.
            beq_read = _read("beq", text, symbols)
            if re.search(r"\bbeq\b", text) and (beq_read is None
                                                or beq_read.value is None):
                raise TopasInpError(
                    f"{path}: {phase.name}: cannot read beq from site line: "
                    f"{text.strip()!r} — the site states beq and this reader "
                    f"could not resolve its value, so building it would seed 0.5 "
                    f"for a number the file states. A site that states no beq at "
                    f"all is a different fact and keeps that seed.")
            if beq_read is not None:
                reads["beq"] = beq_read
            beq = beq_read.value if beq_read is not None else None
            # A site carrying several `occ` tokens is a **mixed** site: one atom
            # per species, sharing this site's label, coordinates and B, exactly
            # as the two-`site`-line spelling already builds (WP-1118, finding 2).
            # The species and its occupancy travel together off
            # `_site_occupancies`, so `occ Al+3 occ Cr+3 0.1` no longer gives Al
            # the value that is Cr's (finding 3); a species stating no value at
            # all keeps the format's own 1.0.
            base_vary = {f: r.vary for f, r in reads.items() if r.vary is not None}
            for species, occ_read in occs:
                # A stated occupancy the reader cannot resolve refuses too — the
                # 1.0 default is for an occupancy the file *omits*, not for one it
                # states and this reader could not read (finding 4).
                if occ_read is not None and occ_read.value is None:
                    raise TopasInpError(
                        f"{path}: {phase.name}: cannot read occ for species "
                        f"{species!r} from site line: {text.strip()!r} — the "
                        f"site states this occupancy and this reader could not "
                        f"resolve its value, so building it would substitute the "
                        f"format's 1.0 default for a number the file states. An "
                        f"occupancy the file omits is a different fact and keeps "
                        f"1.0.")
                occupancy = occ_read.value if occ_read is not None else None
                vary = dict(base_vary)
                if occ_read is not None and occ_read.vary is not None:
                    vary["occ"] = occ_read.vary
                phase.sites.append(TopasSite(
                    label=label.group(1), species=normalize_species(species),
                    occupancy=occupancy if occupancy is not None else 1.0,
                    beq=beq, vary=vary,
                    **{axis: reads[axis].value for axis in "xyz"}))
        # A site token that read no atom is a silently wrong structure factor, so
        # every segment produced at least one atom above or raised; the count of
        # site *tokens* landed in phases is what the file-level guard balances.
        parsed_site_tokens += len(site_texts)
        model.phases.append(phase)

    # A file-level count of `site` tokens, computed over THE masked text and so
    # independent of how the file was split into blocks (WP-1118). A splitter
    # error — a `macro` truncating a `str`, a `str` chunk cut short — that drops
    # sites is invisible to a per-phase count read off that same truncated chunk;
    # this one is not: every `site` token the reader saw must land in a phase (as
    # one or more atoms) or be recorded on a skipped block. Over the mask, not
    # `active`, so a `site` inside a quoted path (`xdd "C:\data\site\run1.xy"`)
    # or a macro is not counted and does not refuse a file that dropped nothing.
    # Counted in `site` **tokens**, not atoms: a mixed site (`occ A occ B`) is
    # one token and several atoms (WP-1118, finding 2), so the balance is over
    # the tokens landed in phases (`parsed_site_tokens`), not `len(ph.sites)`.
    declared = len(re.findall(r"\bsite\b", masked))
    parsed = parsed_site_tokens
    skipped = sum(sb.n_sites for sb in model.skipped_blocks)
    if declared != parsed + skipped:
        raise TopasInpError(
            f"{path}: counted {declared} `site` tokens in the file but read "
            f"{parsed} into phases and recorded {skipped} on blocks that could "
            f"not be named as phases — the {declared - parsed - skipped} "
            f"unaccounted for are sites dropped by how the file split into "
            f"blocks. Read `model.phases` for what was parsed.")
    return model


def to_structure(model: TopasModel, *, cell_limits: bool = True):
    """Build a :class:`~rietx.schemas.Structure` from a parsed model.

    ``beq`` is TOPAS's B and rietx's ``biso`` is also B — no 8π² conversion. A
    site that states no ``beq`` gets a **0.5 seed here**, at build time, not on
    ``model.phases`` — the model is "what the ``.inp`` states", and a seed a
    caller cannot tell from a stated value is the silent-default class this
    reader avoids (WP-1118).
    ``cell_limits`` applies the file's own ``min``/``max`` where it stated them.

    A **negative** ``beq`` is refused, naming the site. It is not a parse error:
    a slightly negative refined B is an ordinary outcome of a converged
    refinement (the column absorbs absorption and normalisation error), and 75
    sites across 11 archive files state one. But rietx's :class:`~rietx.Atom`
    declares ``biso`` on [0, 25] Å², and ``max(beq, 0.0)`` moved the file's
    −0.42 to 0 with nothing said — a *repair the reader cannot say it made*,
    which changes every high-Q intensity. The number stays readable on
    ``model.phases``. The refusal is the same one a sibling structure reader
    (say a FullProf ``.pcr`` reader) follows for the same value, so a caller
    meeting a negative B gets one story whichever code wrote the file — stated
    as the rule a future reader keeps rather than as a claim about a file, since
    no such sibling exists on this tree yet (WP-1076: a declared name is a
    claim).
    """
    import rietx as rx

    # The window is `Atom.biso`'s own declaration, read off the schema rather
    # than restated here: the bound this refusal quotes must not be the reader's
    # invention, which is half of what was wrong with clamping to it.
    biso_default = rx.Atom.model_fields["biso"].default_factory()
    biso_window = {"min": biso_default.min, "max": biso_default.max}

    phases = []
    for ph in model.phases:
        # Report or refuse, never drop. A phase whose cell could not be read
        # used to be skipped here with nothing said, while `model.phases` still
        # carried its `weight_percent` — so the QPA numbers looked complete with
        # a phase missing from the `Structure`, which is worse than the dropped-
        # *site* case this reader already makes a hard error.
        if "a" not in ph.cell:
            raise TopasInpError(
                f"{model.path or '<model>'}: phase {ph.name!r} states no cell, "
                f"so it cannot be built — and dropping it would leave its "
                f"weight_percent reporting for a phase the Structure lacks. "
                f"Read `model.phases` for what the file does state.")
        for s in ph.sites:
            if s.beq is not None and s.beq < biso_window["min"]:
                raise TopasInpError(
                    f"{model.path or '<model>'}: phase {ph.name!r}: site "
                    f"{s.label!r} has beq = {s.beq}, and rietx bounds biso at "
                    f"{biso_window['min']}. A negative B is an ordinary outcome "
                    f"of a converged refinement — the column absorbs absorption "
                    f"and normalisation error — but moving it to "
                    f"{biso_window['min']} changes every high-Q intensity, so it "
                    f"is a contradiction rather than a deviation a reader may "
                    f"repair. Read `model.phases` for the file's own number.")
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

        def _sp(site, field_: str, value: float, **kw):
            """A site parameter, carrying the file's own refine flag."""
            if (free := site.vary.get(field_)) is not None:
                kw["vary"] = free
            return rx.Parameter(value=value, **kw)

        # Every schema refusal from here is converted at this boundary: a
        # reader raises naming the file, and pydantic's report names a field.
        # Reached in practice by a phase whose site lines all sat inside a
        # disabled #ifdef branch, which arrives as "phase has no atoms".
        #
        # `rx.Cell(...)` and the `atoms` comprehension used to sit *above* this
        # try, one line up from the only handler that converts them — so
        # `beq bA 26.0` left as a raw `pydantic_core.ValidationError`. The
        # truncation pin cannot catch that class: a ragged cut rarely leaves a
        # well-formed line carrying an out-of-range number, so the case has its
        # own test.
        try:
            cell = rx.Cell(a=_p("a", c["a"]), b=_p("b", c["a"]), c=_p("c", c["a"]),
                           alpha=_p("al", 90.0), beta=_p("be", 90.0),
                           gamma=_p("ga", 90.0))
            atoms = [rx.Atom(label=s.label, species=s.species,
                             x=_sp(s, "x", s.x), y=_sp(s, "y", s.y),
                             z=_sp(s, "z", s.z),
                             occ=_sp(s, "occ", s.occupancy),
                             # The file's own number, not `max(beq, 0.0)`: a
                             # negative one is refused above rather than moved.
                             # A site that stated none is seeded 0.5 here, at
                             # build time — the model keeps it as None.
                             biso=_sp(s, "beq",
                                      0.5 if s.beq is None else s.beq,
                                      **biso_window))
                     for s in ph.sites]
            phases.append(rx.Phase(
                name=ph.name, space_group=ph.space_group, cell=cell, atoms=atoms,
                # `or 1e-4` substituted the seed for a *stated* zero: 20 real
                # phases across 9 files record `scale 0`, a phase refined to
                # absent, and this repo already treats that as a real state
                # (`weight_percent cBN_wtpct 0.000`). None is the only absence.
                scale=rx.Parameter(value=1e-4 if ph.scale is None else ph.scale,
                                   min=0.0, transform="softplus",
                                   **({"vary": ph.vary["scale"]}
                                      if "scale" in ph.vary else {}))))
        except TopasInpError:
            raise
        except Exception as exc:
            raise TopasInpError(
                f"{model.path or '<model>'}: phase {ph.name!r}: {exc}") from exc

    # Report or refuse, never drop — the skipped-block half (WP-1118). A `str`
    # block that could not be read as a phase but *plainly states a cell or a
    # site* is a phase in all but its name, and `skipped_blocks` was quoted only
    # in the zero-phase branch below — so when another phase read, the nameless
    # one vanished and the weight fractions no longer summed, silently. There is
    # no diagnostics channel on this branch to report through on a successful
    # return (io/CLAUDE.md: a reader repairs only where it can say it did), so
    # the choice consistent with "report or refuse, never drop" and with the
    # dropped-site and no-cell hard errors this reader already raises is to
    # refuse, naming what was dropped.
    carrying = [sb for sb in model.skipped_blocks if sb.cell or sb.n_sites]
    if phases and carrying:
        raise TopasInpError(
            f"{model.path or '<model>'}: {len(carrying)} `str` block"
            f"{'' if len(carrying) == 1 else 's'} here state"
            f"{'s' if len(carrying) == 1 else ''} a cell or a site "
            f"but no phase_name/space_group, so they cannot be built — and "
            f"dropping them while {len(phases)} other phase"
            f"{'' if len(phases) == 1 else 's'} build"
            f"{'s' if len(phases) == 1 else ''} would leave the weight "
            f"fractions no longer summing. " + "; ".join(str(sb) for sb in carrying)
            + ". Read `model.phases` for what the file does state.")

    if not phases:
        # Never "this file has no phases" about a file whose `str` blocks this
        # reader saw and could not name: that is the same confident wrong
        # diagnosis a UTF-16 decode and a `STR(` macro used to get.
        why = ("A Pawley or indexing-only .inp is legal and has none"
               if not model.skipped_blocks else
               f"{len(model.skipped_blocks)} `str` block"
               f"{'' if len(model.skipped_blocks) == 1 else 's'} here could not "
               f"be read as a phase — "
               + "; ".join(str(sb) for sb in model.skipped_blocks))
        raise TopasInpError(
            f"{model.path or '<model>'}: no phase carries a cell, so there is no "
            f"structure to build. {why} — read `model.phases` directly for what "
            f"it does state.")
    try:
        return rx.Structure(phases=phases)
    except Exception as exc:
        # e.g. a phase whose site lines were all inside a disabled #ifdef branch
        raise TopasInpError(f"{model.path or '<model>'}: {exc}") from exc

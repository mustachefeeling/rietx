"""CIF import/export via gemmi (MPL-2.0 dependency, isolated to this module)."""

from __future__ import annotations

import math
import os
import re
from pathlib import Path

import gemmi

from ..schemas.common import Diagnostic, Parameter
from ..schemas.structure import (
    AnisoU,
    Atom,
    Cell,
    Phase,
    Structure,
)
from . import magcif
from .adp import U_NAMES, u_equivalent
from .magnetic.scattering import check_group_is_structure_symmetry
from .symmetry import (
    OperatorGroup,
    site_orbit,
    snap_diagnostics,
    split_group_label,
)


def _strip_su(value: str) -> float:
    """Parse a CIF number, dropping the standard uncertainty: '10.257(1)' → 10.257."""
    return float(re.sub(r"\(\d+\)", "", value))


#: Largest disagreement between a stored cell angle and the value its space
#: group fixes that :func:`structure_from_cif` will **correct and record**
#: rather than leave for ``ParameterTable`` to refuse (WP-1028 §(j)).
#:
#: Chosen by what the two cases look like, not by comfort.  Below it the
#: deviation is the size of a *reported* angle — an experimenter quoting a
#: refined β = 90.002(3) under an orthorhombic symbol is reporting a
#: measurement, not a mistake, and at 0.1° the d-spacing consequence is 830 ppm
#: (linear in the deviation; see ``symmetry.SYMMETRY_ANGLE_TOL_DEG``, which
#: sizes it at 8.3 ppm per 1e-3°).  Above it the disagreement is *structural* —
#: the case WP-1036 found in the wild was a monoclinic β = 93.2° under an
#: orthorhombic symbol, 3.2° out — and there the symbol and the angle
#: contradict each other with no way for a reader to know which is wrong.  So a
#: large deviation is left exactly as written and still raises where it always
#: did, because choosing between "the angle is wrong" and "the symbol is wrong"
#: is the caller's to make.
CIF_ANGLE_CORRECT_MAX_DEG = 0.1

#: the grammar both form-factor lookups parse: an element symbol plus an
#: optional *trailing* charge (``Cl1-``) — see ``scattering.normalize_species``
#: and ``dispersion.normalize_element``, which share it deliberately
_CANONICAL_SPECIES = re.compile(r"^([A-Za-z]{1,2})(\d*[+-])?$")
_SIGN_FIRST_CHARGE = re.compile(r"^([A-Za-z]{1,2})([+-])(\d+)$")
_SITE_LABEL = re.compile(r"^([A-Za-z]{1,2})(\d+)$")


def _correct_symmetry_angles(sg, angles: dict[str, float], path: str,
                             diagnostics: list[Diagnostic] | None,
                             ) -> dict[str, float]:
    """Snap a symmetry-fixed cell angle onto its exact value, recording it.

    ``ParameterTable`` **refuses** a symmetry-fixed angle that disagrees with
    its space group, and rightly: it has no diagnostics channel, so an edit
    there could not be made visible, and an invisible edit to a stored cell is
    worse than a raise (WP-1036).  A *reader* does have that channel, which is
    why the correction belongs here — the same argument, and the same
    mechanism, as :func:`normalize_cif_species` one field over.

    Only deviations up to :data:`CIF_ANGLE_CORRECT_MAX_DEG` are corrected.  A
    larger one is left exactly as written, so it still raises where it always
    did: past that size the symbol and the angle contradict each other, and
    which of the two is wrong is not a reader's call.
    """
    from .symmetry import SYMMETRY_ANGLE_TOL_DEG, cell_constraints

    out = dict(angles)
    for name, target in cell_constraints(sg).fixed_angles.items():
        delta = out[name] - target
        if abs(delta) <= SYMMETRY_ANGLE_TOL_DEG:
            continue
        if abs(delta) > CIF_ANGLE_CORRECT_MAX_DEG:
            continue                      # structural disagreement — leave it
        out[name] = target
        if diagnostics is not None:
            diagnostics.append(Diagnostic(
                level="warning", code="CIF_CELL_ANGLE_CORRECTED",
                where=[f"phases.0.cell.{name}"],
                message=(f"{path} stores {name} = {angles[name]}° under space "
                         f"group {sg.xhm()!r}, whose symmetry fixes it at "
                         f"{target}°; read as {target}° "
                         f"({delta:+.6g}° corrected)"),
                suggestion="the deviation is information about the specimen or "
                           "the refinement that produced this file, not noise: "
                           "if it is real, the symmetry is lower than the "
                           "symbol claims and the phase wants the space group "
                           "that leaves this angle free",
            ))
    return out


def normalize_cif_species(species: str) -> tuple[str, str | None]:
    """Map the two wild CIF type-symbol forms onto the canonical grammar.

    Both form-factor lookups parse an element symbol with an optional
    *trailing* charge (``"Cl1-"``); two forms found in real repositories fail
    that grammar: a **sign-first charge** (``"O-2"``, ``"Ni+3"`` — ICSD
    exports) and a **site label in the type-symbol column** (``"O1"``,
    ``"Cl1"`` — AMCSD-derived files).  This rewrites those onto the canonical
    form, keeping the ion when one was written (``"O-2"`` → ``"O2-"``, so an
    ionic f₀ still resolves) and only when the result actually resolves in
    the Waasmaier-Kirfel table — a symbol this function cannot help
    (``"Wat"``, ``"Xx1"``) passes through verbatim to fail with the lookup's
    own message rather than be half-rewritten. ``"D1"`` reads as deuterium
    (an isotope is its element to X-rays, issue #552), but ``"T1"`` is never
    read as tritium: ``T1``, ``T2`` are the tetrahedral-site labels of every
    zeolite framework, so the rewrite would make a Si/Al site hydrogen.

    Returns ``(species, note)`` where ``note`` names the form that was
    rewritten, or is ``None`` when the input is untouched.  Lives here rather
    than in the lookups because the CIF reader is where a substitution can be
    recorded as provenance; ``scattering.normalize_species`` and
    ``dispersion.normalize_element`` stay strict for hand-built structures.
    """
    from .scattering import normalize_species

    s = species.strip()
    if _CANONICAL_SPECIES.match(s):
        return species, None
    if m := _SIGN_FIRST_CHARGE.match(s):
        candidate = f"{m.group(1).capitalize()}{m.group(3)}{m.group(2)}"
        note = "sign-first charge"
    elif m := _SITE_LABEL.match(s):
        candidate = m.group(1).capitalize()
        if candidate == "T":   # a zeolite T-site label, not tritium (above)
            return species, None
        note = "site label in the type-symbol column"
    else:
        return species, None
    try:
        normalize_species(candidate)
    except KeyError:
        return species, None
    return candidate, note


def species_spelling_hint(species: str) -> str:
    """A refusal-message suffix naming the spelling that would resolve, or ``""``.

    Only the **sign-first charge** form (``"O-2"``, ``"Cu+1"`` — what ICSD
    exports and TOPAS writes) earns a hint: it is by far the commonest wild
    spelling reaching a hand-built structure, and the fix is unambiguous
    (``O2-``, ``Cu1+``).  Everything else returns empty — a three-letter typo
    (``"Wat"``) or a bare label (``"O1"``) has no single obvious correction to
    offer.

    Delegates to :func:`normalize_cif_species` rather than matching the pattern
    again, so the rewrite is **resolved before it is offered**.  Matching alone
    would hand out spellings that fail exactly as the input did — ``"Xx+2"`` →
    ``"Xx2+"`` is no more readable than ``"Xx+2"``, and ``"Og+2"`` → ``"Og2+"``
    names a real element with no row in either table — sending the caller to
    edit a file for nothing.  The two functions then cannot disagree on the same
    input, because there is one decision, made once.

    The division of labour across that one decision:
    :func:`normalize_cif_species` *repairs* this form at read (with a
    ``CIF_SPECIES_NORMALISED`` diagnostic to record it, per ``io/CLAUDE.md``:
    repair only where you can say that you did), and the model-compile boundary
    — which has no diagnostics channel, so it raises rather than repairs —
    reuses the same resolved candidate only to *name* the fix in its refusal.

        >>> species_spelling_hint("Cu+1")
        '; the charge is written after the digits, so Cu1+'
        >>> species_spelling_hint("Xx+2"), species_spelling_hint("O1")
        ('', '')
    """
    candidate, note = normalize_cif_species(species)
    if note != "sign-first charge":
        return ""
    return f"; the charge is written after the digits, so {candidate}"


def _gemmi_or_value_error(call, path: str, what: str):
    """Run a gemmi call, converting **any** exception into a named ``ValueError``.

    `io/CLAUDE.md`'s rule for every reader in this package: it raises
    ``ValueError``/``OSError`` and **names the file**, never its parser's
    exception. gemmi's small-structure reader breaks that on a file that is not
    a CIF at all — an empty or truncated one raises a bare
    ``IndexError('vector')`` from the C++ side, which is a traceback on an API
    caller and a 500 on the GUI's upload route rather than "this file could not
    be read".

    Found by WP-1328's truncation arm in ``tests/test_readers_robust.py``,
    which until then covered the *pattern* readers only — so the structure
    reader had never been handed a file cut mid-token. Pre-existing: measured
    identically on the parent commit, on a plain nuclear CIF, so it is nothing
    the magnetic arm introduced.
    """
    try:
        return call()
    except (ValueError, OSError) as exc:
        raise type(exc)(f"{path}: {what}: {exc}") from exc
    except Exception as exc:                        # noqa: BLE001 - the point
        raise ValueError(
            f"{path}: {what}: {type(exc).__name__}: {exc} — this file does not "
            f"read as a CIF (an empty, truncated or non-CIF file reaches here)"
        ) from exc


#: Characters a CIF value takes from a word processor rather than a keyboard:
#: the typographic quotes, which look like delimiters and are not ones.
_TYPOGRAPHIC_QUOTES = "\u2018\u2019\u201c\u201d"


def _syntax_fault(path: str, message: str) -> str | None:
    """What is at the place gemmi stopped, in words, or ``None``.

    gemmi reports a syntax error as ``file:line:column(offset): parse error``
    and nothing else.  On the MAGNDATA mirror (2026-10-06 sweep) every such
    stop is a malformed file, and nearly all have a cause that can be named
    from the bytes of that line: a byte that is not UTF-8 (a MacRoman or
    Latin-1 en dash in a CIF 2.0 file, which must be UTF-8), a typographic
    quote standing where a CIF quote was meant, a control character, or a
    quoted string not closed on its line.  Naming it turns "parse error" into
    the one edit that fixes the file.
    """
    m = re.search(r":(\d+):(\d+)\(\d+\): (.*)$", message)
    if m is None:
        return None
    line_no = int(m.group(1))
    try:
        lines = Path(path).read_bytes().split(b"\n")
    except OSError:
        return None
    if not 0 < line_no <= len(lines):
        return None
    raw = lines[line_no - 1].rstrip(b"\r")
    where = f"line {line_no}"
    try:
        line = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        byte = raw[exc.start]
        return (f"{where}, column {exc.start + 1}: byte 0x{byte:02X} is not "
                f"UTF-8 (a CIF 2.0 file must be UTF-8, and a CIF 1.1 file "
                f"ASCII; 0x{byte:02X} is typically a character saved in a "
                f"legacy encoding such as MacRoman or Latin-1, an en dash or "
                f"an accented letter). Re-save the file as UTF-8, or replace "
                f"the character")
    quotes = [c for c in line if c in _TYPOGRAPHIC_QUOTES]
    if quotes:
        return (f"{where}: the value uses typographic quotes "
                f"({' '.join(f'U+{ord(c):04X}' for c in sorted(set(quotes)))}), "
                f"which CIF does not read as delimiters. Replace them with "
                f"plain ' or \" quotes")
    control = [c for c in line if ord(c) < 32 and c != "\t"]
    if control:
        return (f"{where}: the line holds a control character "
                f"({' '.join(f'U+{ord(c):04X}' for c in sorted(set(control)))}), "
                f"which no CIF value may contain. Delete it")
    if "unterminated" in m.group(3):
        return (f"{where}: a quoted value is not closed on this line. A CIF "
                f"quoted string ends at a matching quote followed by "
                f"whitespace on the same line; a value that runs over lines "
                f"goes in a ;-delimited text field")
    words = line.split()
    if (len(words) >= 3 and words[0].startswith("_")
            and words[1][:1] not in ("'", '"', "[", "{")):
        return (f"{where}: the value of {words[0]} holds whitespace and is not "
                f"quoted. Quote it so it reads as one "
                f"value")
    if (words and not words[0].startswith(("_", "#", "'", '"', ";"))
            and words[0].lower() not in ("loop_", "global_")
            and not words[0].lower().startswith(("data_", "save_"))
            and re.fullmatch(r"[A-Za-z][\w.\-]*_[\w.\-]+", words[0])):
        return (f"{where}: {words[0]!r} stands where a tag is expected, and a "
                f"CIF tag starts with '_' — it looks like a tag that lost its "
                f"underscore")
    if any(ord(c) > 127 for c in line):
        return (f"{where}: the line holds a non-ASCII character outside a "
                f"quoted string; quote the value (CIF 2.0, UTF-8) or replace "
                f"the character")
    return None


def _number_fault(path: str, block, tags, label: str | None = None) -> None:
    """Raise naming a numeric item gemmi read as NaN, which is a malformed number.

    gemmi returns NaN for a number it cannot parse (``5.12(3`` with the
    parenthesis unclosed, ``8.6l(2)`` with a letter for a digit), and the NaN
    then reached the schema as "value nan lies outside bounds" with no file,
    tag or value in the message.  Called only once a NaN has been found.
    """
    for tag in tags:
        values = ([block.find_value(tag)] if label is None else
                  [row[1] for row in block.find("_atom_site_", ["label",
                                                                tag[11:]])
                   if row.str(0) == label])
        for value in values:
            if value is None or value in ("?", "."):
                continue
            if math.isnan(gemmi.cif.as_number(value)):
                where = "" if label is None else f" for site {label!r}"
                raise ValueError(
                    f"{path}: {tag}{where} is {value!r}, which is not a CIF "
                    f"number (digits, an optional exponent and an optional "
                    f"standard uncertainty in parentheses, as in '5.4307(2)')")


def _magnetic_content(text: str) -> bool:
    """Whether a CIF's text states a magnetic construct of any kind.

    The gate on the magnetic arm of :func:`structure_from_cif`, and a
    deliberately *textual* test: it decides whether this file is one the
    magnetic vocabulary applies to at all, so a nuclear CIF takes exactly the
    path it always did — including a displacively modulated one, whose average
    structure this reader has always returned and which is WP-1319's to fence,
    not this rung's.
    """
    if re.search(r"(?m)^\s*_atom_site_moment[._]", text):
        return True
    if re.search(r"(?m)^\s*_space_group_(?:symop_)?magn[._]", text):
        return True
    return bool(re.search(r"(?m)^\s*_space_group\.magn_", text))


def structure_from_cif(path: str | os.PathLike[str], *, phase_name: str | None = None,
                       aniso: bool = False,
                       moment_ions: dict[str, str] | None = None,
                       moment_g: dict[str, float] | None = None,
                       nuclear_group: str = "auto",
                       diagnostics: list[Diagnostic] | None = None) -> Structure:
    """Read the first data block of a CIF into a single-phase :class:`Structure`.

    Uses gemmi's small-molecule reader, which resolves the space group from
    the recorded H-M (or Hall) symbol and carries fractional coordinates,
    occupancies, and isotropic/equivalent displacement parameters.

    ``aniso=True`` keeps ``_atom_site_aniso_U_ij`` as an
    :class:`~rietx.schemas.structure.AnisoU` block on each site that has
    one, instead of collapsing it to U_eq.  It is opt-in for the same reason
    the schema field is: reading a file must not silently change which
    parameters a refinement plan will free.  Sites without an aniso loop keep
    their isotropic value either way, so a mixed file yields a mixed
    structure.

    Species are passed through :func:`normalize_cif_species`, so the two wild
    type-symbol forms (``"O1"``, ``"O-2"``) arrive refinable instead of
    failing at the first stage compile.  Pass ``diagnostics=`` a list to
    record what changed: each distinct rewritten form appends one
    ``CIF_SPECIES_NORMALISED`` diagnostic naming the substitution, with
    ``where`` carrying every affected atom path.

    A **bracketed** H-M label beside an operation loop is a phase carrying its
    own operation list (what :func:`write_structure_block` writes for one), and
    comes back as that list in the file's order under that label — never as
    whatever symbol gemmi finds for the operations, which would drop the label
    and reorder the list a symmetry code indexes.

    **A magCIF** — a file carrying ``_space_group_symop_magn_operation.xyz``
    and an ``_atom_site_moment`` loop, which is what MAGNDATA, ISODISTORT and
    k-SUBGROUPSMAG emit — arrives as WP-1327's model: the operator list with
    its time-reversal signs on ``Phase.magnetic_symmetry``, the moments in
    crystal-axis components on the sites they name, and the BNS/OG symbol as
    metadata.  The nuclear space group's type comes from
    ``_parent_space_group.name_H-M_alt``, because a magCIF has no ordinary
    ``_space_group_name_H-M_alt`` at all and gemmi therefore resolves no space
    group for one; its setting is checked against the file's own operators
    (:func:`~rietx.crystallography.magcif.resolve_nuclear_symmetry`).  Two magnetic constructs are **refused by name** rather than
    half-read: a modulated structure (any ``_atom_site_moment_Fourier`` or
    special-function loop) and a structure stated in a *supercell* of its
    parent (the generic commensurate k ≠ 0 record) — see
    :mod:`rietx.crystallography.magcif`, which owns the vocabulary and both
    refusals.

    ``moment_ions`` and ``moment_g`` state, per site label, the two quantities
    no magnetic dictionary carries: the ion whose form factor the moment
    scatters with (``{"Mn1": "Mn3+"}``) and the Landé g a 4f moment needs.
    Where ``moment_ions`` says nothing the site's own type symbol is used and a
    ``CIF_MAGNETIC_ION_UNCHARGED`` diagnostic reports it, because MAGNDATA
    writes a bare ``Mn`` for a site that is chemically Mn³⁺ and the two form
    factors differ.  A key of either that names no ``_atom_site_moment`` row is
    refused (:class:`~rietx.crystallography.magcif.MagCifError`), since a
    misspelled label would leave its site on that default in silence.

    ``nuclear_group`` chooses which group a magCIF's atom *positions* refine
    under (the moments always refine under the file's magnetic group).
    ``"auto"`` takes the highest tabulated group the file's atoms satisfy — the
    parent where it contains the file's operators and keeps every site's
    orbit, reported by ``CIF_MAGNETIC_NUCLEAR_GROUP``, else the file's own
    family group, reported by ``CIF_MAGNETIC_NUCLEAR_SETTING`` (issue #457) —
    in its tabulated setting, or, where no tabulated setting has exactly its
    operations, as its own operation list under a bracketed label
    (``Phase.symmetry_operations``); ``"file"`` always takes the file's own group; ``"parent"`` always takes the
    parent and raises by name where it cannot carry the file's atoms.  It acts
    where the nuclear group is derived from ``_parent_space_group``, and a file
    with no magnetic block ignores it
    (:func:`~rietx.crystallography.magcif.resolve_nuclear_symmetry`).
    """
    # gemmi's readers take a str only, so a pathlib.Path is turned into one
    # here, once, before any reader or message sees it.
    path = os.fspath(path)
    if nuclear_group not in magcif.NUCLEAR_GROUP_CHOICES:
        raise ValueError(
            f"nuclear_group={nuclear_group!r}: expected one of "
            f"{', '.join(map(repr, magcif.NUCLEAR_GROUP_CHOICES))}")
    try:
        small = _gemmi_or_value_error(
            lambda: gemmi.read_small_structure(path), path,
            "could not be read as a small-molecule CIF")
    except ValueError as exc:
        fault = _syntax_fault(path, str(exc))
        if fault is None:
            raise
        raise ValueError(f"{exc}. {fault}") from exc
    if not small.sites:
        raise ValueError(f"no atom sites found in {path}")
    cell_values = (small.cell.a, small.cell.b, small.cell.c,
                   small.cell.alpha, small.cell.beta, small.cell.gamma)
    if any(math.isnan(v) for v in cell_values):
        _number_fault(path, gemmi.cif.read(path).sole_block(),
                      [f"_cell_{n}" for n in ("length_a", "length_b",
                                              "length_c", "angle_alpha",
                                              "angle_beta", "angle_gamma")])
    for site in small.sites:
        if any(math.isnan(v) for v in (site.fract.x, site.fract.y,
                                       site.fract.z, site.occ)):
            _number_fault(path, gemmi.cif.read(path).sole_block(),
                          ["_atom_site_fract_x", "_atom_site_fract_y",
                           "_atom_site_fract_z", "_atom_site_occupancy"],
                          label=site.label)
    text = Path(path).read_text(encoding="utf-8", errors="replace")

    # The magnetic arm's two refusals run **before** anything is built and
    # whether or not the file also states an ordinary space group: a magCIF
    # from ISODISTORT can carry both, and a refusal that fires only on the
    # branch where the nuclear symbol is missing is a construct dropped
    # exactly where the file was most complete.
    block = None
    magnetic_symmetry = None
    if _magnetic_content(text):
        block = _gemmi_or_value_error(
            lambda: gemmi.cif.read(path).sole_block(), path,
            "states a magnetic construct and has no single data block")
        magcif.refuse_modulation(text, path)
        magcif.refuse_a_magnetic_supercell(block, text, path)
        magnetic_symmetry = magcif.read_magnetic_symmetry(
            block, text, path, diagnostics=diagnostics)

    listed = None
    if split_group_label(small.spacegroup_hm or "") is not None and small.symops:
        listed = [str(op) for op in small.symops]
    sg = (OperatorGroup(label=small.spacegroup_hm.strip(), xyz=tuple(listed))
          if listed else small.spacegroup)
    if sg is None:
        # fall back on the raw H-M string in the file, then on the magCIF
        # parent symbol: a magCIF states no ordinary H-M symbol at all — the
        # magnetic block replaces it — so gemmi resolves no space group for
        # one, and the *nuclear* group is the parent's.  The magnetic operator
        # list cannot supply it: a type-III group is an index-2 subgroup of the
        # parent, so the nuclear symmetry is strictly higher than the
        # operators state.
        doc_block = block if block is not None else _gemmi_or_value_error(
            lambda: gemmi.cif.read(path).sole_block(), path,
            "has no single data block to read a space group from")
        hm = (doc_block.find_value("_symmetry_space_group_name_H-M")
              or doc_block.find_value("_space_group_name_H-M_alt")
              or (magcif.parent_space_group(doc_block) if block is not None
                  else None))
        if hm is None and block is not None:
            raise magcif.MagCifError(
                f"{path} states a magnetic structure and no space group this "
                f"reader can resolve: neither an ordinary "
                f"_space_group_name_H-M_alt nor the magCIF "
                f"_parent_space_group.name_H-M_alt. The magnetic operator list "
                f"alone cannot supply it — a type-III magnetic group is an "
                f"index-2 subgroup of the parent, so the nuclear symmetry is "
                f"strictly *higher* than the operators state, and a phase "
                f"built from them would carry the wrong absences and the wrong "
                f"site multiplicities.")
        if hm is None:
            raise ValueError(f"CIF {path} has no resolvable space group")
        if block is not None and magnetic_symmetry is not None:
            # The nuclear group of a magCIF is derived from the file's own
            # magnetic operators (time reversal dropped), never from the H-M
            # symbol alone: gemmi's tabulated operator set for a symbol can
            # sit at a different origin than the setting this file's cell,
            # coordinates and moments are actually stated in (measured on
            # Ima2/space group 46). The parent is kept where it contains the
            # file's operators and gives every site its own orbit; otherwise the
            # tabulated setting the operators state is taken, or else the
            # file's own operation list under a bracketed label (magcif.resolve_nuclear_symmetry, tier 3).
            sg = magcif.resolve_nuclear_symmetry(
                hm, magnetic_symmetry, path, diagnostics=diagnostics,
                nuclear_group=nuclear_group,
                sites=[(site.label, (site.fract.x, site.fract.y, site.fract.z))
                       for site in small.sites])
            if isinstance(sg, OperatorGroup):
                listed = list(sg.xyz)
        else:
            sg = gemmi.find_spacegroup_by_name(hm.strip("'\""))
            if sg is None:
                raise ValueError(f"unrecognised space group {hm!r} in {path}")

    cell = small.cell
    atoms: list[Atom] = []
    rewrites: dict[str, tuple[str, str, list[str]]] = {}
    # CIF tags are case-insensitive, so the gate that spares an ordered file its
    # second parse is too
    disorder = (_disorder_columns(path, small.name)
                if re.search(r"(?i)_atom_site_disorder", text) else {})
    stated = _site_statements(path, small.name)
    for j, site in enumerate(small.sites):
        has_aniso = site.aniso.nonzero()
        u_iso = site.u_iso
        said = stated.get(site.label, {})
        # a displacement parameter the file states is the file's, zero included:
        # `0.000(75)` is a number at the floor, not an absent column
        if not u_iso and not said.get("iso"):
            # U_eq from the trace is an approximation (the exact form weights
            # by the metric — adp.u_equivalent); it only feeds the isotropic
            # fallback, where the tensor is being discarded anyway
            u_eq = (site.aniso.u11 + site.aniso.u22 + site.aniso.u33) / 3.0
            u_iso = u_eq if u_eq > 0 else 0.5 / (8.0 * math.pi ** 2)
        b_iso = u_iso * 8.0 * math.pi ** 2
        raw = site.type_symbol or site.element.name
        species, note = normalize_cif_species(raw)
        if note is not None:
            rewrites.setdefault(raw, (species, note, []))[2].append(
                f"phases.0.atoms.{j}.species")
        atoms.append(Atom(
            label=site.label,
            species=species,
            x=Parameter(value=site.fract.x),
            y=Parameter(value=site.fract.y),
            z=Parameter(value=site.fract.z),
            occ=Parameter(value=(site.occ if site.occ or said.get("occ")
                                 else 1.0), min=0.0, max=1.5),
            biso=Parameter(value=b_iso, unit="A^2"),
            aniso=(AnisoU.from_values([site.aniso.u11, site.aniso.u22, site.aniso.u33,
                                       site.aniso.u12, site.aniso.u13, site.aniso.u23])
                   if aniso and has_aniso else None),
            disorder_assembly=disorder.get(site.label, (None, None))[0],
            disorder_group=disorder.get(site.label, (None, None))[1],
        ))

    stated_diagnostics = _snap_to_stated_multiplicity(sg, atoms, stated, path=path)
    if diagnostics is not None:
        diagnostics.extend(stated_diagnostics)
        for raw, (canonical, note, where) in rewrites.items():
            diagnostics.append(Diagnostic(
                level="info", code="CIF_SPECIES_NORMALISED",
                message=(f"species {raw!r} in {path} read as "
                         f"{canonical!r} ({note})"),
                where=where))
        diagnostics.extend(snap_diagnostics(
            sg, [(a.label, (a.x.value, a.y.value, a.z.value)) for a in atoms],
            source=path, prefix="phases.0"))

    angles = {"alpha": cell.alpha, "beta": cell.beta, "gamma": cell.gamma}
    angles = _correct_symmetry_angles(sg, angles, path, diagnostics)

    if block is not None:
        cell6 = (cell.a, cell.b, cell.c,
                 angles["alpha"], angles["beta"], angles["gamma"])
        written_ions, written_g = magcif.read_private_moment_items(block)
        ions = {**written_ions, **(moment_ions or {})}
        g_factors = {**written_g, **(moment_g or {})}
        moments = magcif.read_moments(block, cell6, path, ions=ions,
                                      g_factors=g_factors)
        by_label = {a.label: (j, a) for j, a in enumerate(atoms)}
        unmatched = sorted(set(moments) - set(by_label))
        if unmatched:
            raise magcif.MagCifError(
                f"{path}: the _atom_site_moment loop names "
                f"{', '.join(repr(u) for u in unmatched)}, which is not an "
                f"_atom_site_label in this block "
                f"({', '.join(repr(k) for k in by_label)}). A moment whose "
                f"site cannot be found is refused rather than dropped — it is "
                f"the whole magnetic contribution of that site.")
        # A caller's key that names no moment row is a misspelling, and a
        # misspelled ion would leave its site on the neutral atom's form
        # factor with nothing said -- the TOPAS arm refuses a misspelled
        # phase name for the same reason (review of #478, follow-up)
        for argument, stated in (("moment_ions", moment_ions),
                                 ("moment_g", moment_g)):
            stray = sorted(set(stated or {}) - set(moments))
            if stray:
                raise magcif.MagCifError(
                    f"{path}: {argument} names "
                    f"{', '.join(repr(k) for k in stray)}, which "
                    f"{'is' if len(stray) == 1 else 'are'} not a label in this "
                    f"file's _atom_site_moment loop "
                    f"({', '.join(repr(k) for k in moments) or 'no moments'}). "
                    f"A misspelled label would leave that site's moment on the "
                    f"file's own default with nothing said, so it is refused.")
        if moments and magnetic_symmetry is None:
            raise magcif.MagCifError(
                f"{path} states moments on "
                f"{', '.join(repr(k) for k in moments)} and no "
                f"_space_group_symop_magn_operation.xyz loop. A moment is only "
                f"meaningful under a magnetic space group — it is what gives "
                f"the moment an allowed subspace and an orbit — so the "
                f"operator list is not optional here.")
        from .magnetic import form_factor

        assumed_ions: dict[str, tuple[str, str]] = {}
        assumed_g: dict[str, float] = {}
        group = magnetic_symmetry.group()
        for label, (moment, row) in moments.items():
            j, atom = by_label[label]
            # A moment the operators constrain, printed to fewer decimals than
            # the constraint needs, sits just off its allowed subspace; within
            # half a unit in each printed place it is put on it, and said so
            # (``CIF_MAGNETIC_MOMENT_ON_ALLOWED``), the moment counterpart of a
            # site snapped onto its special position.  Beyond the print, the
            # phase's own check refuses it as before.
            moved = magcif.moment_within_print(
                moment, row,
                group.allowed_moment_basis((atom.x.value, atom.y.value,
                                            atom.z.value)))
            if moved is not None:
                components, shift = moved
                before = moment.values()
                moment = moment.model_copy(update={
                    f"crystalaxis_{a}": getattr(moment, f"crystalaxis_{a}")
                    .model_copy(update={"value": v})
                    for a, v in zip("xyz", components)})
                if diagnostics is not None:
                    diagnostics.append(Diagnostic(
                        level="info", code="CIF_MAGNETIC_MOMENT_ON_ALLOWED",
                        where=[f"phases.0.atoms.{j}.moment"], value=shift,
                        message=(
                            f"{path}: site {label!r}'s moment "
                            f"{[round(v, 6) for v in before]} mu_B lies off "
                            f"the subspace its site symmetry allows by no more "
                            f"than the file's printed precision, and was put "
                            f"on it: {[round(v, 6) for v in components]} "
                            f"(largest component moved {shift:.2g} mu_B)"),
                        suggestion=(
                            "nothing to change: the file printed the "
                            "components to fewer decimals than the symmetry "
                            "relation between them needs")))
            # The ion is the one quantity a magCIF cannot state (there is no
            # such item in ``cif_mag.dic``), so it falls back on the site's own
            # type symbol and ``magnetic_diagnostics`` reports that it did. A
            # bare element symbol this table cannot resolve *neutrally* -- every
            # lanthanide/actinide it carries only ionic <j0> curves for -- gets
            # one further fallback: the element's majority oxidation state that
            # is magnetic (WP-1327 D1; issue-magnetic-form-factor option (b)),
            # reported as MAGNETIC_ION_ASSUMED rather than
            # CIF_MAGNETIC_ION_UNCHARGED, since it is a stronger substitution
            # than the neutral-atom one.
            ion = moment.ion or atom.species
            g = moment.g
            if not moment.ion and not form_factor.has_ion(ion):
                assumed = form_factor.resolve_assumed_ion(ion)
                if assumed is not None:
                    assumed_ions[label] = assumed
                    ion = assumed[0]
                    # g is the second quantity magCIF cannot state, and the
                    # same reasoning applies one step further: an ion this
                    # module *assumed* (never one a caller stated) that turns
                    # out to need an explicit g (every lanthanide/actinide
                    # here does) gets its free-ion Hund's-rule g_J defaulted
                    # too, rather than refusing on a quantity the file could
                    # never have carried either way (WP-1327 D-lande-g).
                    if g is None and form_factor.needs_explicit_g(ion):
                        default_g = form_factor.assumed_lande_g(ion)
                        if default_g is not None:
                            assumed_g[label] = default_g
                            g = default_g
            atoms[j] = atom.model_copy(update={
                "moment": moment.model_copy(update={"ion": ion, "g": g})})
        if diagnostics is not None and magnetic_symmetry is not None:
            diagnostics.extend(magcif.magnetic_diagnostics(
                path, {k: (atoms[by_label[k][0]].moment, row)
                       for k, (_m, row) in moments.items()},
                magnetic_symmetry,
                {a.label: (j, a) for j, a in enumerate(atoms)}, cell6,
                assumed_ions=assumed_ions, assumed_g=assumed_g))

    phase = Phase(
        name=phase_name or (small.name or "phase_1"),
        space_group=sg.xhm(),
        symmetry_operations=listed,
        cell=Cell(
            # bounds deliberately left open: a cell length's default window
            # is anchored per stage on the value that stage starts from
            # (params.vector.cell_window), and a finite bound here would read
            # as a claim by the caller and suppress it.  0.1 Å was never a
            # meaningful floor anyway — cell_window's is 1.5 Å.
            a=Parameter(value=cell.a),
            b=Parameter(value=cell.b),
            c=Parameter(value=cell.c),
            alpha=Parameter(value=angles["alpha"]),
            beta=Parameter(value=angles["beta"]),
            gamma=Parameter(value=angles["gamma"]),
        ),
        atoms=atoms,
        magnetic_symmetry=magnetic_symmetry,
    )
    check_group_is_structure_symmetry(phase)
    structure = Structure(phases=[phase])
    return structure


def format_su(value: float, esd: float | None, *, decimals: int = 6) -> str:
    """A number with its standard uncertainty in ``value(su)`` notation.

    The su carries **two significant figures** and the value is quoted to
    exactly that precision — ``4.59370(25)``, not ``4.593700(250)`` — the
    crystallographic convention (IUCr; Schwarzenbach et al., 1989, Acta Cryst.
    A45, 63): an esd of 2.5·10⁻⁴ says the sixth decimal is not knowledge.  The
    esd therefore sets the number of decimals; ``decimals`` governs only the
    no-esd case.

    Three traps this handles:

    - **Decade boundary.**  An esd like 0.0999 rounds *up* to two figures as
      ``100``; that is renormalised to ``0.10`` → ``value(10)`` with one fewer
      decimal, never the spurious three-figure ``(100)``.
    - **esd ≥ 1.**  The value loses decimals and the su keeps its trailing
      magnitude: 123.4 ± 2.5 → ``123.4(25)``; 12345 ± 250 → ``12340(250)``.
    - **No esd** (``None``, non-positive, or non-finite — a fixed parameter or
      one the fit could not estimate): the plain number is written, never an
      implied uncertainty.
    """
    if esd is None or not (esd > 0.0) or not math.isfinite(esd):
        return f"{value:.{decimals}f}"
    p = math.floor(math.log10(esd))       # decade of the esd's leading digit
    ndp = 1 - p                            # decimals so the su shows two figures
    su = round(esd * 10 ** ndp)            # 2-figure integer, normally 10..99
    if su >= 100:                          # rounded up across a decade (99.6→100)
        su //= 10
        ndp -= 1
    if su <= 0:                            # esd underflowed the printable range
        return f"{value:.{decimals}f}"
    if ndp > 0:
        return f"{value:.{ndp}f}({su})"
    scale = 10 ** (-ndp)                    # esd ≥ ~10: su carries trailing zeros
    return f"{round(value / scale) * scale:.0f}({su * scale})"


#: How far :func:`structure_from_cif` will move a site to reach the special
#: position the file's own ``_atom_site_symmetry_multiplicity`` states.  A site
#: quoted to four decimals can sit 2e-4 from it, each coordinate rounded on its
#: own (the 6e site of rhombohedral-axes hematite: x + y = 1.5002), which the
#: orbit tolerance (``symmetry.SITE_TOL``, 1e-4) reads as a general position
#: of twice the multiplicity.  Three decimals is as coarse as a CIF is quoted.
CIF_STATED_MULTIPLICITY_SNAP_TOL = 1e-3


def _site_statements(path: str, name: str) -> dict[str, dict]:
    """What each site label's row states, per column, where gemmi cannot say.

    ``small.sites`` holds ``u_iso = 0`` and ``occ = 1`` for a column the file
    does not carry and for one that states them, so "stated zero" and "absent"
    are not told apart there.  Returns ``{label: {"iso": bool, "occ": bool,
    "multiplicity": int | None}}`` read from the block itself; a null (``.``
    or ``?``) is not a statement.  The multiplicity comes from
    ``_atom_site_symmetry_multiplicity``, else the number leading a
    ``_atom_site_Wyckoff_symbol`` (``6e``).
    """
    doc = gemmi.cif.read(path)
    block = doc.find_block(name) or doc[0]
    table = block.find("_atom_site_", [
        "label", "?U_iso_or_equiv", "?B_iso_or_equiv", "?occupancy",
        "?symmetry_multiplicity", "?Wyckoff_symbol"])
    out: dict[str, dict] = {}
    for row in table:
        def stated(k):
            return row.has(k) and not gemmi.cif.is_null(row[k])
        multiplicity = None
        if stated(4):
            digits = re.match(r"\d+", gemmi.cif.as_string(row[4]).strip())
            multiplicity = int(digits.group()) if digits else None
        if multiplicity is None and stated(5):
            digits = re.match(r"\d+", gemmi.cif.as_string(row[5]).strip())
            multiplicity = int(digits.group()) if digits else None
        out.setdefault(gemmi.cif.as_string(row[0]), {
            "iso": stated(1) or stated(2), "occ": stated(3),
            "multiplicity": multiplicity})
    return out


def _snap_to_stated_multiplicity(sg, atoms: list[Atom], stated: dict[str, dict],
                                 *, path: str) -> list[Diagnostic]:
    """Put a site on the special position its own row says it occupies.

    Where the file states a multiplicity smaller than the one the stored
    coordinates give, and moving the site by at most
    :data:`CIF_STATED_MULTIPLICITY_SNAP_TOL` makes the orbit exactly the stated
    size, the coordinates are **moved** there: left alone, the forward model
    would put a multiple of the stated atoms in the cell (twice the oxygen of
    hematite, absorbed by a displacement parameter nobody questions).  The
    move is a statement of the file's own, recorded as
    ``SITE_SNAPPED_TO_SPECIAL_POSITION``.  Where the file's multiplicity is not
    reachable, or is larger than the computed one, nothing moves and
    ``CIF_SITE_MULTIPLICITY_DISAGREES`` names the site: the coordinates and the
    stated multiplicity are telling different things.
    """
    import numpy as np

    moved: list[tuple[str, float, int, str]] = []
    disagree: list[tuple[str, int, int, str]] = []
    for j, atom in enumerate(atoms):
        want = stated.get(atom.label, {}).get("multiplicity")
        if want is None:
            continue
        xyz = np.array([atom.x.value, atom.y.value, atom.z.value])
        try:
            have = site_orbit(sg, xyz).multiplicity
        except ValueError:
            continue
        if have == want:
            continue
        where = f"phases.0.atoms.{j}"
        if want < have:
            try:
                near = site_orbit(sg, xyz, tol=CIF_STATED_MULTIPLICITY_SNAP_TOL)
            except ValueError:
                near = None
            if near is not None and near.multiplicity == want:
                delta = near.position - xyz
                delta -= np.rint(delta)
                new = xyz + delta
                for axis, value in zip(("x", "y", "z"), new, strict=True):
                    setattr(atom, axis, getattr(atom, axis).model_copy(
                        update={"value": float(value)}))
                moved.append((atom.label, float(np.max(np.abs(delta))), want,
                              where))
                continue
        disagree.append((atom.label, want, have, where))
    out: list[Diagnostic] = []
    if moved:
        named = ", ".join(f"{lbl} ({shift:.1e} → multiplicity {m})"
                          for lbl, shift, m, _ in moved[:4])
        if len(moved) > 4:
            named += f", and {len(moved) - 4} more"
        out.append(Diagnostic(
            level="warning", code="SITE_SNAPPED_TO_SPECIAL_POSITION",
            where=[w for *_, w in moved],
            message=(f"{len(moved)} site(s) in {path} state a multiplicity "
                     f"their coordinates did not reach, and were moved onto "
                     f"the special position that does: {named}. Largest shift "
                     f"{max(s for _, s, _, _ in moved):.2e} in fractional "
                     f"coordinates"),
            suggestion="the stored coordinates are now the special position's "
                       "own, as the file's `_atom_site_symmetry_multiplicity` "
                       "(or Wyckoff symbol) states; each coordinate of the "
                       "file was rounded on its own, so the shift is within "
                       "what its quoted precision allows"))
    if disagree:
        named = ", ".join(f"{lbl} (file {want}, computed {have})"
                          for lbl, want, have, _ in disagree[:4])
        if len(disagree) > 4:
            named += f", and {len(disagree) - 4} more"
        out.append(Diagnostic(
            level="warning", code="CIF_SITE_MULTIPLICITY_DISAGREES",
            where=[w for *_, w in disagree],
            message=(f"{len(disagree)} site(s) in {path} state a multiplicity "
                     f"that differs from the one their coordinates give under "
                     f"the stated space group, and moving them by at most "
                     f"{CIF_STATED_MULTIPLICITY_SNAP_TOL:g} does not reach it: "
                     f"{named}"),
            suggestion="the coordinates and the stated multiplicity (or the "
                       "space group's setting) tell different things, and the "
                       "number of atoms in the cell, hence ZMV and every "
                       "weight fraction, follows the coordinates. Check the "
                       "setting and the site against the source"))
    return out


def _disorder_columns(path: str, name: str) -> dict[str, tuple[str | None, str | None]]:
    """Each site label's ``(_atom_site_disorder_assembly, _atom_site_disorder_group)``.

    Read from the block itself, since gemmi's small-structure site keeps the
    group as an integer and the assembly not at all, and the dictionary types
    both as a ``Word``.  A null (``.`` or ``?``) is ``None``, an ordered site.
    """
    doc = gemmi.cif.read(path)
    block = doc.find_block(name) or doc[0]
    table = block.find("_atom_site_", ["label", "?disorder_assembly", "?disorder_group"])
    out: dict[str, tuple[str | None, str | None]] = {}
    for row in table:
        values = tuple(None if not row.has(k) or gemmi.cif.is_null(row[k])
                       else gemmi.cif.as_string(row[k]) for k in (1, 2))
        out.setdefault(gemmi.cif.as_string(row[0]), values)
    return out


def _fmt(p: Parameter, decimals: int) -> str:
    """A CIF number from a :class:`Parameter`, su included when known."""
    return format_su(p.value, p.stderr, decimals=decimals)


def write_structure_block(block, phase: Phase, *,
                          moment_magnitude_esds: dict[str, float] | None = None,
                          ) -> None:
    """Write one phase's cell, sites and ADP loops into a gemmi CIF ``block``.

    A phase carrying its own operation list also gets a
    ``_space_group_symop_operation_xyz`` loop in its own order, which
    :func:`structure_from_cif` reads back under the bracketed label.

    Anisotropic sites get an ``_atom_site_aniso_*`` loop in the CIF U^ij
    convention — the same numbers :class:`~rietx.schemas.structure.AnisoU`
    stores — and their ``_atom_site_B_iso_or_equiv`` carries the equivalent
    B_eq = 8π²·U_eq computed from the tensor and cell, so a reader that
    ignores the aniso loop still sees the right isotropic magnitude rather
    than a stale starting estimate.  Standard uncertainties are written for
    any parameter whose ``stderr`` is set (see
    ``ParameterTable.apply_to_models``).  Shared with the refinement exporter
    (``io/exporters.py``), which appends refinement + pattern loops to the
    same block.
    """
    c = phase.cell
    cell6 = c.lengths_angles()
    for name in ("a", "b", "c"):
        block.set_pair(f"_cell_length_{name}", _fmt(getattr(c, name), 6))
    for name in ("alpha", "beta", "gamma"):
        block.set_pair(f"_cell_angle_{name}", _fmt(getattr(c, name), 4))
    block.set_pair("_symmetry_space_group_name_H-M", gemmi.cif.quote(phase.space_group))
    if phase.symmetry_operations is not None:
        # the list is the group, in the order a symmetry code indexes; a
        # bracketed label alone names nothing a reader can expand.  The
        # refinement exporter's geometry loop rewrites the same loop from the
        # same list (``resolve_group``), so the two cannot disagree.
        ops = block.init_loop("_space_group_symop_", ["id", "operation_xyz"])
        for idx, triplet in enumerate(phase.symmetry_operations):
            ops.add_row([str(idx + 1), gemmi.cif.quote(triplet)])
    # the two disorder columns only when a site declares one, so a file of an
    # ordered structure is byte-identical to what this writer wrote before
    disorder = [k for k in ("disorder_assembly", "disorder_group")
                if any(getattr(a, k) is not None for a in phase.atoms)]
    loop = block.init_loop("_atom_site_", [
        "label", "type_symbol", "fract_x", "fract_y", "fract_z",
        "occupancy", "B_iso_or_equiv", "adp_type", *disorder,
    ])
    for a in phase.atoms:
        if a.aniso is None:
            b_eq, kind = _fmt(a.biso, 4), "Biso"
        else:
            b_eq = f"{8.0 * math.pi ** 2 * u_equivalent(a.aniso.values(), cell6):.4f}"
            kind = "Uani"
        loop.add_row([
            a.label, a.species,
            _fmt(a.x, 6), _fmt(a.y, 6), _fmt(a.z, 6),
            _fmt(a.occ, 4), b_eq, kind,
            *("." if getattr(a, k) is None else gemmi.cif.quote(getattr(a, k))
              for k in disorder),
        ])
    aniso = [a for a in phase.atoms if a.aniso is not None]
    if aniso:
        uloop = block.init_loop("_atom_site_aniso_", [
            "label", "U_11", "U_22", "U_33", "U_12", "U_13", "U_23",
        ])
        for a in aniso:
            uloop.add_row([a.label] + [_fmt(getattr(a.aniso, n), 5)
                                       for n in U_NAMES])
    # The magnetic half, when the phase carries one: the operator and centring
    # loops, the BNS/OG metadata and the moments with their esds
    # (``crystallography.magcif``).  Not the parent k: a supercell phase is
    # written as a k = 0 structure in its own cell, and
    # ``MagneticSymmetry.propagation_vector_parent`` does not survive the file
    # (``test_a_magnetic_supercell_phase_round_trips_in_its_own_cell``).  Nothing at all is written for a phase with
    # no ``magnetic_symmetry``, so every file this writer produced before this
    # rung is byte-identical — the one property a writer change inside a
    # function shared by ``structure_to_cif`` and the refinement exporter has
    # to have.
    magcif.write_magnetic_block(block, phase,
                                magnitude_esds=moment_magnitude_esds)


def structure_to_cif(structure: Structure, path: str | os.PathLike[str]) -> None:
    """Write phases to a minimal CIF (cell, positions, occupancies, ADPs).

    One data block per phase.  See :func:`write_structure_block` for the ADP
    and standard-uncertainty conventions.
    """
    doc = gemmi.cif.Document()
    for phase in structure.phases:
        block = doc.add_new_block(re.sub(r"\W+", "_", phase.name))
        write_structure_block(block, phase)
    # gemmi's writer takes a str only, as its readers do (structure_from_cif).
    doc.write_file(os.fspath(path))

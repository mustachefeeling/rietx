"""CIF import/export via gemmi (MPL-2.0 dependency, isolated to this module)."""

from __future__ import annotations

import math
import re

import gemmi

from ..schemas.common import Diagnostic, Parameter
from ..schemas.structure import AnisoU, Atom, Cell, Phase, Structure
from .adp import U_NAMES, u_equivalent


def _strip_su(value: str) -> float:
    """Parse a CIF number, dropping the standard uncertainty: '10.257(1)' → 10.257."""
    return float(re.sub(r"\(\d+\)", "", value))


#: the grammar both form-factor lookups parse: an element symbol plus an
#: optional *trailing* charge (``Cl1-``) — see ``scattering.normalize_species``
#: and ``dispersion.normalize_element``, which share it deliberately
_CANONICAL_SPECIES = re.compile(r"^([A-Za-z]{1,2})(\d*[+-])?$")
_SIGN_FIRST_CHARGE = re.compile(r"^([A-Za-z]{1,2})([+-])(\d+)$")
_SITE_LABEL = re.compile(r"^([A-Za-z]{1,2})(\d+)$")


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
    (``"Wat"``, ``"D"``) passes through verbatim to fail with the lookup's
    own message rather than be half-rewritten.

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
        note = "site label in the type-symbol column"
    else:
        return species, None
    try:
        normalize_species(candidate)
    except KeyError:
        return species, None
    return candidate, note


def structure_from_cif(path: str, *, phase_name: str | None = None,
                       aniso: bool = False,
                       diagnostics: list[Diagnostic] | None = None) -> Structure:
    """Read the first data block of a CIF into a single-phase :class:`Structure`.

    Uses gemmi's small-molecule reader, which resolves the space group from
    the recorded H-M (or Hall) symbol and carries fractional coordinates,
    occupancies, and isotropic/equivalent displacement parameters.

    ``aniso=True`` keeps ``_atom_site_aniso_U_ij`` as an
    :class:`~pxrdref.schemas.structure.AnisoU` block on each site that has
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
    """
    small = gemmi.read_small_structure(path)
    if not small.sites:
        raise ValueError(f"no atom sites found in {path}")

    sg = small.spacegroup
    if sg is None:
        # fall back on the raw H-M string in the file
        doc = gemmi.cif.read(path)
        block = doc.sole_block()
        hm = (block.find_value("_symmetry_space_group_name_H-M")
              or block.find_value("_space_group_name_H-M_alt"))
        if hm is None:
            raise ValueError(f"CIF {path} has no resolvable space group")
        sg = gemmi.find_spacegroup_by_name(hm.strip("'\""))
        if sg is None:
            raise ValueError(f"unrecognised space group {hm!r} in {path}")

    cell = small.cell
    atoms: list[Atom] = []
    rewrites: dict[str, tuple[str, str, list[str]]] = {}
    for j, site in enumerate(small.sites):
        has_aniso = site.aniso.nonzero()
        u_iso = site.u_iso
        if not u_iso:
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
            occ=Parameter(value=site.occ if site.occ else 1.0, min=0.0, max=1.5),
            biso=Parameter(value=b_iso, min=0.0, max=25.0, unit="A^2"),
            aniso=(AnisoU.from_values([site.aniso.u11, site.aniso.u22, site.aniso.u33,
                                       site.aniso.u12, site.aniso.u13, site.aniso.u23])
                   if aniso and has_aniso else None),
        ))

    if diagnostics is not None:
        for raw, (canonical, note, where) in rewrites.items():
            diagnostics.append(Diagnostic(
                level="info", code="CIF_SPECIES_NORMALISED",
                message=(f"species {raw!r} in {path} read as "
                         f"{canonical!r} ({note})"),
                where=where))

    phase = Phase(
        name=phase_name or (small.name or "phase_1"),
        space_group=sg.xhm(),
        cell=Cell(
            a=Parameter(value=cell.a, min=0.1),
            b=Parameter(value=cell.b, min=0.1),
            c=Parameter(value=cell.c, min=0.1),
            alpha=Parameter(value=cell.alpha),
            beta=Parameter(value=cell.beta),
            gamma=Parameter(value=cell.gamma),
        ),
        atoms=atoms,
    )
    return Structure(phases=[phase])


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


def _fmt(p: Parameter, decimals: int) -> str:
    """A CIF number from a :class:`Parameter`, su included when known."""
    return format_su(p.value, p.stderr, decimals=decimals)


def write_structure_block(block, phase: Phase) -> None:
    """Write one phase's cell, sites and ADP loops into a gemmi CIF ``block``.

    Anisotropic sites get an ``_atom_site_aniso_*`` loop in the CIF U^ij
    convention — the same numbers :class:`~pxrdref.schemas.structure.AnisoU`
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
    loop = block.init_loop("_atom_site_", [
        "label", "type_symbol", "fract_x", "fract_y", "fract_z",
        "occupancy", "B_iso_or_equiv", "adp_type",
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
        ])
    aniso = [a for a in phase.atoms if a.aniso is not None]
    if aniso:
        uloop = block.init_loop("_atom_site_aniso_", [
            "label", "U_11", "U_22", "U_33", "U_12", "U_13", "U_23",
        ])
        for a in aniso:
            uloop.add_row([a.label] + [_fmt(getattr(a.aniso, n), 5)
                                       for n in U_NAMES])


def structure_to_cif(structure: Structure, path: str) -> None:
    """Write phases to a minimal CIF (cell, positions, occupancies, ADPs).

    One data block per phase.  See :func:`write_structure_block` for the ADP
    and standard-uncertainty conventions.
    """
    doc = gemmi.cif.Document()
    for phase in structure.phases:
        block = doc.add_new_block(re.sub(r"\W+", "_", phase.name))
        write_structure_block(block, phase)
    doc.write_file(path)

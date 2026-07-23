"""CIF import/export via gemmi (MPL-2.0 dependency, isolated to this module)."""

from __future__ import annotations

import math
import re

import gemmi

from ..schemas.common import Parameter
from ..schemas.structure import AnisoU, Atom, Cell, Phase, Structure
from .adp import U_NAMES, u_equivalent


def _strip_su(value: str) -> float:
    """Parse a CIF number, dropping the standard uncertainty: '10.257(1)' → 10.257."""
    return float(re.sub(r"\(\d+\)", "", value))


def structure_from_cif(path: str, *, phase_name: str | None = None,
                       aniso: bool = False) -> Structure:
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
    for site in small.sites:
        has_aniso = site.aniso.nonzero()
        u_iso = site.u_iso
        if not u_iso:
            # U_eq from the trace is an approximation (the exact form weights
            # by the metric — adp.u_equivalent); it only feeds the isotropic
            # fallback, where the tensor is being discarded anyway
            u_eq = (site.aniso.u11 + site.aniso.u22 + site.aniso.u33) / 3.0
            u_iso = u_eq if u_eq > 0 else 0.5 / (8.0 * math.pi ** 2)
        b_iso = u_iso * 8.0 * math.pi ** 2
        species = site.type_symbol or site.element.name
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


def _fmt(p: Parameter, decimals: int) -> str:
    """A CIF number, with the standard uncertainty in parentheses if known.

    The su carries two significant digits and the value is quoted to exactly
    that precision — ``4.59370(25)``, not ``4.593700(250)`` — which is the
    crystallographic convention: an esd of 2.5·10⁻⁴ says the sixth decimal is
    not knowledge.  The esd therefore sets the number of decimals, overriding
    ``decimals``, which only governs the no-esd case.  When the esd is absent
    or non-positive the plain number is written: a refinement that could not
    estimate an esd must not imply one.
    """
    if p.stderr is None or not (p.stderr > 0.0) or not math.isfinite(p.stderr):
        return f"{p.value:.{decimals}f}"
    dec = max(-math.floor(math.log10(p.stderr)) + 1, 0)
    su = round(p.stderr * 10 ** dec)
    if su <= 0:  # esd far below the printed precision
        return f"{p.value:.{decimals}f}"
    return f"{p.value:.{dec}f}({su})"


def structure_to_cif(structure: Structure, path: str) -> None:
    """Write phases to a minimal CIF (cell, positions, occupancies, ADPs).

    Anisotropic sites get an ``_atom_site_aniso_*`` loop in the CIF U^ij
    convention — the same numbers :class:`~pxrdref.schemas.structure.AnisoU`
    stores — and their ``_atom_site_B_iso_or_equiv`` carries the equivalent
    B_eq = 8π²·U_eq computed from the tensor and cell, so a reader that
    ignores the aniso loop still sees the right isotropic magnitude rather
    than a stale starting estimate.  Standard uncertainties are written for
    any parameter whose ``stderr`` is set (see
    ``ParameterTable.apply_to_models``).
    """
    doc = gemmi.cif.Document()
    for phase in structure.phases:
        block = doc.add_new_block(re.sub(r"\W+", "_", phase.name))
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
    doc.write_file(path)

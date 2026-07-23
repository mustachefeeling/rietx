"""CIF import/export via gemmi (MPL-2.0 dependency, isolated to this module)."""

from __future__ import annotations

import math
import re

import gemmi

from ..schemas.common import Parameter
from ..schemas.structure import AnisoU, Atom, Cell, Phase, Structure


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


def structure_to_cif(structure: Structure, path: str) -> None:
    """Write phases to a minimal CIF (positions, occupancies, Biso, cell)."""
    doc = gemmi.cif.Document()
    for phase in structure.phases:
        block = doc.add_new_block(re.sub(r"\W+", "_", phase.name))
        c = phase.cell
        block.set_pair("_cell_length_a", f"{c.a.value:.6f}")
        block.set_pair("_cell_length_b", f"{c.b.value:.6f}")
        block.set_pair("_cell_length_c", f"{c.c.value:.6f}")
        block.set_pair("_cell_angle_alpha", f"{c.alpha.value:.4f}")
        block.set_pair("_cell_angle_beta", f"{c.beta.value:.4f}")
        block.set_pair("_cell_angle_gamma", f"{c.gamma.value:.4f}")
        block.set_pair("_symmetry_space_group_name_H-M", gemmi.cif.quote(phase.space_group))
        loop = block.init_loop("_atom_site_", [
            "label", "type_symbol", "fract_x", "fract_y", "fract_z",
            "occupancy", "B_iso_or_equiv",
        ])
        for a in phase.atoms:
            loop.add_row([
                a.label, a.species,
                f"{a.x.value:.6f}", f"{a.y.value:.6f}", f"{a.z.value:.6f}",
                f"{a.occ.value:.4f}", f"{a.biso.value:.4f}",
            ])
    doc.write_file(path)

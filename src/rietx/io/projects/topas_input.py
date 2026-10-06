"""A TOPAS ``.inp`` that refines what the fit refined, tied as the model is.

:func:`~rietx.io.projects.topas.write_topas_inp` on its own writes the ``str``
blocks with each ``Parameter``'s stored flag. This module is what it calls when
it is given more:

* ``free=`` — a ``Refinement`` (or its ``parameters()``, a ``RefinementResult``,
  a list of paths): the free set and the ties, written as TOPAS names and
  equations (:mod:`.topas_refined`, issues #722 and #721 item 3);
* ``scale="topas"`` with ``instrument=`` — the scale in TOPAS's convention,
  stated in a comment (#722).

Everything here was written from the TOPAS Technical Reference (its keywords
and its § 2 parameter grammar) and from TOPAS 6 runs as a black box; no TOPAS
code or macro body was read.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from .topas_refined import (
    Affine,
    Expr,
    RefinedSet,
    Slot,
    number,
    render_slots,
    topas_scale_factor,
)

_CELL_KEYS = (("a", "a"), ("b", "b"), ("c", "c"), ("al", "alpha"),
              ("be", "beta"), ("ga", "gamma"))
_ADP_KEYS = ("u11", "u22", "u33", "u12", "u13", "u23")
_MOMENT_KEYS = ("mlx", "mly", "mlz")


def _p(ip: int, rest: str) -> str:
    return f"phases.{ip}.{rest}"


def _a(ip: int, ia: int, rest: str) -> str:
    return f"phases.{ip}.atoms.{ia}.{rest}"


# ----------------------------------------------------------------- moments

def _moment_component_items(phase, ip, ia, atom, refined: RefinedSet,
                            rotation: np.ndarray | None = None) -> list:
    """``mlx … mly … mlz …`` for one written site, as slots over the DOFs.

    The moment block's freedom is ``…moment.dof<k>`` (a signed modulus on a
    one-dimensional subspace, a modulus and angles on a larger one;
    ``crystallography.magnetic.moments``), so each written component is that
    function of the DOFs, carried to the image by ``rotation`` (the axial matrix
    of a copy) and divided by its edge (TOPAS's fractional basis, measured:
    crystal-axis μ_B = ``mlx``·a). With every angle held it is linear in the
    modulus and written as an affine equation; otherwise through ``Sin``/``Cos``.
    A component the site's symmetry forbids has no term and is written held,
    which is what TOPAS needs ("cannot be refined as it has no derivative").
    """
    from ...crystallography.magnetic.moments import (
        dofs_from_moment,
        moment_frame,
        moment_from_dofs,
    )

    cell = phase.cell
    edges = (cell.a.value, cell.b.value, cell.c.value)
    group = phase.magnetic_symmetry.group()
    xyz = (atom.x.value, atom.y.value, atom.z.value)
    cell6 = cell.lengths_angles()
    frame = moment_frame(group.allowed_moment_basis(xyz), cell6)
    rot = np.eye(3) if rotation is None else np.asarray(rotation, dtype=float)
    n = len(frame)
    m_now = rot @ np.asarray(atom.moment.values(), dtype=float)
    seed = (dofs_from_moment(frame, cell6, atom.moment.values()) if n
            else np.zeros(0))
    dof_aff = []
    for k in range(n):
        path = _a(ip, ia, f"moment.dof{k}")
        value = (refined.rows[path].value if refined.rows is not None
                 and path in refined.rows else float(seed[k]))
        dof_aff.append(refined.affine(path, value))
    angles_held = all(not a.terms for a in dof_aff[1:])
    out = []
    if n and angles_held:
        unit = rot @ moment_from_dofs(frame, [1.0] + [a.const for a in dof_aff[1:]])
    for i, key in enumerate(_MOMENT_KEYS):
        if n == 0:
            out += [f" {key} ", Slot(Affine({}, 0.0), 1.0 / edges[i], 0.0)]
        elif angles_held:
            out += [f" {key} ", Slot(dof_aff[0] * float(unit[i]), 1.0 / edges[i],
                                     float(m_now[i]), carry=False)]
        else:
            e = frame @ rot.T
            c = [number(e[k][i] / edges[i]) for k in range(n)]
            if n == 2:
                tpl = f"= {{0}}*(({c[0]})*Cos({{1}}) + ({c[1]})*Sin({{1}}));"
            else:
                tpl = (f"= {{0}}*(({c[0]})*Sin({{1}})*Cos({{2}}) + "
                       f"({c[1]})*Sin({{1}})*Sin({{2}}) + ({c[2]})*Cos({{1}}));")
            out += [f" {key} ", Expr(tpl, dof_aff)]
    if atom.moment.g is not None:
        out.append(f" mg ! {number(atom.moment.g)}")
    return out


# ----------------------------------------------------------------- one phase

def _site_items(phase, ip, ia, atom, refined, *, label, species, xyz_aff, xyz_now,
                occ_aff, biso_aff, aniso, moment_rotation, with_moment):
    from .topas import _number  # the legacy writer's refusal of a non-finite value

    items: list = [f"  site {label}"]
    for key, aff, now in zip(("x", "y", "z"), xyz_aff, xyz_now):
        items += [f" {key} ", Slot(aff, 1.0, now,
                                   path=None if moment_rotation is not None
                                   or label != atom.label else _a(ip, ia, key))]
    items += [f" occ {species} ", Slot(occ_aff, 1.0, atom.occ.value)]
    if aniso is not None:
        items.append(f" beq ! {_number(atom.biso.value)}")
        for key, (aff, now) in zip(_ADP_KEYS, aniso):
            items += [f" {key} ", Slot(aff, 1.0, now)]
    else:
        items += [" beq ", Slot(biso_aff, 1.0, atom.biso.value)]
    if with_moment and atom.moment is not None:
        items += _moment_component_items(phase, ip, ia, atom, refined, moment_rotation)
    items.append("\n")
    return items


def _aniso_affines(refined, ip, ia, atom):
    if atom.aniso is None:
        return None
    return [(refined.affine(_a(ip, ia, k), getattr(atom.aniso, k).value),
             getattr(atom.aniso, k).value) for k in _ADP_KEYS]


def phase_items(structure, ip, phase, refined: RefinedSet, *, scale_factor: float,
                header: list[str], species_of) -> list:
    """One ``str``, every number a :class:`~.topas_refined.Slot`."""
    items: list = ["str\n"]
    items += [f"  {h}\n" for h in header]
    items += ["  scale ", Slot(refined.affine(_p(ip, "scale"), phase.scale.value),
                                scale_factor, phase.scale.value), "\n"]
    for key, attr in _CELL_KEYS:
        param = getattr(phase.cell, attr)
        items += [f"  {key} ", Slot(refined.affine(_p(ip, f"cell.{attr}"), param.value),
                                     1.0, param.value), "\n"]
    for ia, atom in enumerate(phase.atoms):
        items += _site_items(
            phase, ip, ia, atom, refined, label=atom.label,
            species=species_of(atom, True),
            xyz_aff=[refined.affine(_a(ip, ia, k), getattr(atom, k).value)
                     for k in ("x", "y", "z")],
            xyz_now=[atom.x.value, atom.y.value, atom.z.value],
            occ_aff=refined.affine(_a(ip, ia, "occ"), atom.occ.value),
            biso_aff=refined.affine(_a(ip, ia, "biso"), atom.biso.value),
            aniso=_aniso_affines(refined, ip, ia, atom),
            moment_rotation=None, with_moment=True)
    return items


# ----------------------------------------------------------------- the file

def refined_text(structure, *, refined: RefinedSet, scale: str, instrument,
                 species_of, magnetic_numbers: dict[int, str | None],
                 provenance: str) -> str:
    """The ``.inp`` text: the header (what the scale is), the ``prm``
    declarations the ties need, and one ``str`` per phase."""
    from ...crystallography.symmetry import get_spacegroup

    notes: list[str] = []
    factor = 1.0
    if scale == "topas":
        if instrument is None:
            raise ValueError("scale='topas' needs instrument= (the constant depends "
                             "on the radiation)")
        factor = topas_scale_factor(instrument)
        notes.append(
            f"scale: TOPAS convention (LP_Factor, |F|^2 in "
            f"{'barn' if instrument.source.kind == 'neutron_cw' else 'electrons^2'})"
            f" = rietx Phase.scale x {number(factor)}")
    else:
        notes.append("scale: rietx's own Phase.scale, NOT TOPAS's convention "
                     "(TOPAS's is x100 for neutrons, xK for X-rays)")
    if refined.rows is None and refined.free_paths is not None:
        notes.append("free set given without ties: a tied copy refines as its own "
                     "parameter (pass the Refinement to free= for the ties)")
    body: list = []
    for ip, phase in enumerate(structure.phases):
        header = [f'phase_name "{phase.name}"']
        mag_number = magnetic_numbers.get(ip)
        if mag_number is None:
            header.append(f'space_group "{get_spacegroup(phase.space_group).xhm()}"')
        else:
            header.append(f"mag_space_group {mag_number}")
        if phase.extinction.value != 0.0:
            notes.append(f"phase {phase.name!r}: extinction "
                         f"{number(phase.extinction.value)} is not written (a "
                         f"TOPAS str has no keyword for it)")
        body += phase_items(structure, ip, phase, refined, scale_factor=factor,
                            header=header, species_of=species_of)
    declarations = render_slots(body, refined)
    head = [f"' Written by {provenance}"]
    head += [f"' {n}" for n in notes]
    head += declarations
    return "\n".join(head) + "\n" + "".join(str(i) for i in body)


def from_structure_refined(structure, *, free: Any = None, scale: str | None = None,
                           instrument=None, names: dict | None = None) -> str:
    """The refined-set path of :func:`~rietx.io.projects.topas.from_structure`."""
    from ..._about import DIST_NAME
    from .topas import _magnetic_group_line, _sign_first, refuse_operation_list, topas_species

    if scale is None:
        scale = "topas" if instrument is not None else "rietx"
    if scale not in ("rietx", "topas"):
        raise ValueError(f"scale must be 'rietx' or 'topas', not {scale!r}")
    magnetic_numbers: dict[int, str | None] = {}
    for ip, phase in enumerate(structure.phases):
        if '"' in phase.name or "\n" in phase.name or "\r" in phase.name:
            raise ValueError(f"phase name {phase.name!r} cannot be written to a TOPAS "
                             f"`.inp`: it carries a double quote or a line break")
        refuse_operation_list(phase, "a TOPAS `.inp`")
        magnetic_numbers[ip] = _magnetic_group_line(phase)
        for atom in phase.atoms:
            if any(ch.isspace() or ch == "'" for ch in atom.label + atom.species):
                raise ValueError(
                    f"phase {phase.name!r}: atom label {atom.label!r} / species "
                    f"{atom.species!r} carries whitespace or a single quote, which a "
                    f"`site` line cannot carry")
    refined = RefinedSet(free, structure)

    def species_of(atom, with_moment):
        # a magnetic site keeps its ion, as the legacy writer does
        return (topas_species(atom.species) if atom.moment is None
                else _sign_first(atom.species))

    text = refined_text(structure, refined=refined, scale=scale, instrument=instrument,
                        species_of=species_of, magnetic_numbers=magnetic_numbers,
                        provenance=f"{DIST_NAME}.io.projects.topas.write_topas_inp")
    if names is not None:
        names.update(refined.carriers)
    return text

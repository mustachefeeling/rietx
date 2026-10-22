"""The one verb that puts a site's coinciding images on its special position (#1007).

:func:`~.symmetry.site_twin_merge` is the rule; this is where a ``Structure``
meets it, from every boundary that can say so.  The schema is strict and has no
diagnostics channel (root ``CLAUDE.md``: *a silent correction is a reader's to
make, never a table's*), so ``Phase`` validation moves nothing.  Instead each
boundary that builds or changes a structure calls :func:`merge_site_twins` and
reports on its own channel: ``structure_from_cif`` (as ``CIF_SITE_TWINS_MERGED``,
through its own message), the project readers' ``to_structure``,
``RefinementTree.load``, and the ``Refinement`` verbs that take a structure in
(construction, ``edit``, ``set_values``, ``checkout``), which carry the finding
to the next result they return.
"""

from __future__ import annotations

import numpy as np

from ..schemas.common import Diagnostic
from ..schemas.structure import Structure
from .symmetry import TWIN_DISTANCE, TwinMerge, resolve_group, site_twin_merge
from .wyckoff import adp_basis, coordinate_basis, stabilizer_rotations


def _num(v: float) -> str:
    return f"{v:.4g}"


def _content_change(occ: float, merge: TwinMerge) -> tuple[str, str]:
    """The merge's atoms per cell both ways, and how to keep a split pair's content.

    Returns ``(observation, keep)``: two sentences for the message and one for
    the suggestion.  The merge keeps the stated occupancy (#765's reading: the
    occupancy is the special position's), so the site's content goes from
    ``before × occ`` to ``after × occ`` atoms per cell.  That is right for a
    special position stated off by rounding.  For a split pair of
    part-atoms that a fit or a file left within 0.02 Å of its own image it
    divides the content by ``before/after`` (#1088), so where that reading is
    possible (occupancy below 1, and the pair's summed occupancy ``occ ×
    before/after`` not above 1) the message says so, and ``keep`` gives the
    occupancy that restores it.  Otherwise ``keep`` is empty.
    """
    ratio = merge.before / merge.after
    sentences = (f"Atoms per cell (multiplicity × occupancy): {merge.before} × {_num(occ)} = "
                 f"{_num(merge.before * occ)} → {merge.after} × {_num(occ)} = "
                 f"{_num(merge.after * occ)}.")
    restated = occ * ratio
    if not (occ < 1.0 and round(restated, 6) <= 1.0):
        return sentences, ""
    how = "halved" if merge.before == 2 * merge.after else f"divided by {_num(ratio)}"
    sentences += (f" If the site was a split pair of part-atoms rather than "
                  f"one atom stated off its position, the merge {how} its "
                  f"content.")
    keep = (f"To keep a split pair's content, restate the site on the "
            f"special position at occupancy {_num(restated)}, or state it at "
            f"least {_num(TWIN_DISTANCE)} Å from its own images.")
    return sentences, keep


def _fixed_by_symmetry(atom, sg, position: np.ndarray, diagnostics_note: list[str]):
    """``atom``'s coordinates and tensor as the special position ``position`` allows them.

    What the merge moves onto a position, the parameter table then checks
    against that position, and refuses what it did not allow before the move:
    a coordinate with ``vary=True`` where the site symmetry allows no positional
    freedom, and an anisotropic tensor outside the allowed subspace.  So the
    merge clears ``vary`` on exactly the coordinates
    :meth:`~rietx.refine.Refinement.fix_special_positions` would, and projects
    the tensor onto the allowed patterns (least squares in U^ij, the table's own
    test), each said in ``diagnostics_note``.
    """
    rotations = stabilizer_rotations(sg, position)
    update: dict = {}
    coords = {}
    for n, v in zip("xyz", position, strict=True):
        param = getattr(atom, n).model_copy(update={"value": float(v)})
        coords[n] = param
    if len(coordinate_basis(rotations)) == 0 and any(p.vary for p in coords.values()):
        for p in coords.values():
            p.vary = False
        diagnostics_note.append(
            "Its coordinates were set to vary=False: the position allows no "
            "positional freedom.")
    update.update(coords)
    if atom.aniso is not None:
        basis = adp_basis(rotations).astype(np.float64)
        u0 = np.array(atom.aniso.values(), dtype=np.float64)
        coef, *_ = np.linalg.lstsq(basis.T, u0, rcond=None)
        u1 = basis.T @ coef
        change = float(np.abs(u1 - u0).max())
        if change > 1e-6 * max(float(np.abs(u0).max()), 1e-6):
            aniso = atom.aniso.model_copy(update={
                name: getattr(atom.aniso, name).model_copy(update={"value": float(v)})
                for name, v in zip(("u11", "u22", "u33", "u12", "u13", "u23"),
                                   u1, strict=True)})
            update["aniso"] = aniso
            diagnostics_note.append(
                f"Its anisotropic tensor was projected onto the tensors the "
                f"position allows (largest change {change:.2g} Å²).")
    return update


def _kept_message(atom, phase, source: str | None, xyz, merge: TwinMerge,
                  position: list[float]) -> tuple[str, str]:
    """Message and suggestion for a site left as stored, whose merge would lose content."""
    occ = atom.occ.value
    ratio = merge.before / merge.after
    message = (
        f"{source + ': ' if source else ''}site {atom.label!r} of phase "
        f"{phase.name!r} is stated at {[round(float(v), 6) for v in xyz]}, "
        f"where it puts {merge.before} positions in the cell in pairs "
        f"{merge.gap:.2g} Å apart; nothing was moved. The coordinates cannot "
        f"say which of two things this is. One atom stated off its special "
        f"position {[round(v, 6) for v in position]} ({merge.after} positions) "
        f"holds {merge.after} × {_num(occ)} = {_num(merge.after * occ)} atoms "
        f"per cell there, at occupancy {_num(occ)}. A split pair of part-atoms "
        f"holds {merge.before} × {_num(occ)} = {_num(merge.before * occ)} as "
        f"stored, and {merge.after} × {_num(occ * ratio)} = "
        f"{_num(merge.before * occ)} on the position, at occupancy "
        f"{_num(occ * ratio)}. The model is left as stored and counts the "
        f"second.")
    suggestion = (
        f"state the site on the special position at occupancy {_num(occ)} if "
        f"it is one atom stated off its position, or at occupancy "
        f"{_num(occ * ratio)} if it is a split pair; or state it at least "
        f"{_num(TWIN_DISTANCE)} Å from its own images to say it is split.")
    return message, suggestion


def merge_site_twins(structure: Structure, *,
                     diagnostics: list[Diagnostic] | None = None,
                     source: str | None = None,
                     keep_part_occupied: bool = False) -> Structure:
    """``structure`` with every site whose own images coincide moved onto its position.

    A site whose images are closer than
    :data:`~.symmetry.TWIN_DISTANCE` is one atom counted twice; it is
    moved to the special position its orbit collapses to, and one
    ``SITE_TWINS_MERGED`` warning per site is appended to ``diagnostics``.  A
    split site (images ≥ 0.20 Å apart), a site already on its position and a
    rigid-body atom (the body's pose writes it; a body across a symmetry
    element is the body's own question, #876) are left alone.  Returns the
    argument itself when nothing moved, and never mutates it.

    A moved site is also made fit for its new position: coordinates the
    position fixes lose ``vary``, and an anisotropic tensor is projected onto
    the allowed patterns, each said in the message (otherwise the parameter
    table refuses the merged model, #1014).

    ``keep_part_occupied`` is the stance of a boundary that holds a *model*
    rather than reads a file (``RefinementTree.load`` and the ``Refinement``
    verbs).  Where occupancy × (images before / images after) is at most 1, the
    stated numbers read both as one atom off its position and as a split pair
    of part-atoms (#1088), and no other code merges a fit-made coordinate by
    default (GSAS-II drops an image only within 2e-4 fractional, FullProf and
    BGMN not at all, TOPAS only on request).  There the site is **left as
    stored** and ``SITE_TWINS_KEPT`` gives both readings.  Above 1 the unmerged
    model puts more than one atom at one place, so the merge is physics and
    happens either way.  A file reader keeps the occupancy the file states per
    site and merges as before.

    ``source`` prefixes the message (a file path, as the readers' messages do).

    The rule and its references are :func:`~.symmetry.site_twin_merge`'s:
    International Tables for Crystallography vol. A (Wyckoff positions) and
    Grosse-Kunstleve & Adams (2002), Acta Cryst. A58, 60.
    """
    phases = list(structure.phases)
    changed = False
    for i, phase in enumerate(phases):
        try:
            sg = resolve_group(phase.space_group, phase.symmetry_operations)
        except (ValueError, RuntimeError):
            continue             # the symbol's own refusal is someone else's
        bodied = {label for body in phase.rigid_bodies for label in body.atoms}
        cell = phase.cell.lengths_angles()
        atoms = list(phase.atoms)
        moved_any = False
        for j, atom in enumerate(atoms):
            if atom.label in bodied:
                continue
            xyz = np.array([atom.x.value, atom.y.value, atom.z.value])
            try:
                merge = site_twin_merge(sg, cell, xyz)
            except ValueError:
                continue         # an orbit refusal speaks at compile
            if merge is None:
                continue
            position = [float(v) for v in merge.position]
            if keep_part_occupied and round(
                    atom.occ.value * merge.before / merge.after, 6) <= 1.0:
                if diagnostics is not None:
                    message, suggestion = _kept_message(
                        atom, phase, source, xyz, merge, position)
                    diagnostics.append(Diagnostic(
                        level="warning", code="SITE_TWINS_KEPT",
                        where=[f"phases.{i}.atoms.{j}"], value=merge.gap,
                        message=message, suggestion=suggestion))
                continue
            notes: list[str] = []
            atoms[j] = atom.model_copy(update=_fixed_by_symmetry(
                atom, sg, np.array(position), notes))
            moved_any = True
            if diagnostics is not None:
                content, keep = _content_change(atom.occ.value, merge)
                diagnostics.append(Diagnostic(
                    level="warning", code="SITE_TWINS_MERGED",
                    where=[f"phases.{i}.atoms.{j}"], value=merge.gap,
                    message=(
                        f"{source + ': ' if source else ''}site "
                        f"{atom.label!r} of phase {phase.name!r} was given at "
                        f"{[round(float(v), 6) for v in xyz]}, where it puts "
                        f"{merge.before} positions in the cell in pairs "
                        f"{merge.gap:.2g} Å apart; it was moved onto the "
                        f"special position {[round(v, 6) for v in position]}, "
                        f"{merge.after} positions, with its occupancy unchanged. "
                        f"{content}" + "".join(" " + n for n in notes)),
                    suggestion=(
                        "check the coordinate against its source: a special "
                        "position stated a few 1e-5 off (a hand edit, a "
                        "rounded project file) is the usual cause. "
                        + (keep or f"To keep a genuinely displaced atom, state "
                           f"it at least {_num(TWIN_DISTANCE)} Å from its own "
                           f"images."))))
        if moved_any:
            # model_copy skips validation on purpose: the move is the repair,
            # and an assignment would re-run every validator of the phase
            phases[i] = phase.model_copy(update={"atoms": atoms})
            changed = True
    if not changed:
        return structure
    return structure.model_copy(update={"phases": phases})

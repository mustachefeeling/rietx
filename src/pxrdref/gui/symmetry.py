"""Symmetry, surfaced and editable (WP-1035).

The GUI quoted a phase's space group as one read-only string in three places and
explained it nowhere, while everything the symmetry *does* — a tied ``b``, a
locked angle, a site with two coordinate DOFs instead of three, an ADP basis of
four patterns — showed up in the parameter table as an effect with no named
cause.  This module is the cause, and the verb that changes it.

**Two tiers, and the split is a measurement rather than a taste.**

* The **phase facts** are one ``get_spacegroup`` call — number, setting, crystal
  system, Laue class, point group, centring, and the ``CellConstraints`` that
  decide which cell edges are tied and which angles are held.  Free, so they ride
  on ``GET /api/structure``, which is refetched on every head move.
* The **Wyckoff letter** is a spglib search per atom.  Measured here rather than
  assumed (the ``/api/structure`` docstring said "expensive" and nobody had
  timed it): ``site_constraints`` costs **1.8-8.7 ms per atom** on this machine
  — 13 ms for NAC's six sites, 13 ms for LaB₆'s two — so a 40-atom structure is
  ~0.1-0.3 s *per head move* on a route that also moves for a ``set_vary``.  It
  therefore lives on ``GET /api/structure/symmetry``, opened deliberately, which
  is the escape ``structure()``'s own docstring already named.

The letter earns that route twice over: it brings the **oriented site-symmetry
symbol** (``.3.``, ``4m.m``) with it, which is the one form of "which symmetry
element is responsible" that is actually a symmetry element rather than a count.

**The preview duplicates no rule.**  ``preview`` copies the structure, swaps the
symbol, and builds a :class:`~pxrdref.params.vector.ParameterTable` from the
candidate: the refusals *are* the incompatibility list, in the package's own
words including the nearest-allowed values they already compute, and the entry
diff *is* the tie/lock story.  Construction stops at the first incompatible item,
so the per-atom pass probes one atom at a time — a real table each time, never a
second copy of the compatibility rules.

Three failures the table diff cannot see get their own answers, because none of
them raises today:

1. **A setting change reinterprets every coordinate while still resolving.**
   ``R -3 c:H`` and ``R -3 c:R`` are the same group on different axes; nothing
   here converts between them.
2. **Orbit collisions.**  ``select_orbit_ops`` dedups images *within* one atom's
   orbit, so two asymmetric-unit atoms that a higher symmetry maps onto each
   other double-count in F and nothing checks it.
3. **Renumbered DOFs.**  ``…dof.k`` and ``…adp.k`` are *positional*, so after a
   group change ``dof.0`` can exist with a different direction and
   ``_prepare_table(restore=True)`` frees it without comment.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from ..crystallography.adp import U_NAMES, cartesian_basis
from ..crystallography.symmetry import (
    cell_constraints,
    check_cell_angles,
    expand_positions,
    get_spacegroup,
    rotation_matrices,
)
from ..crystallography.wyckoff import adp_basis, coordinate_basis, stabilizer_rotations
from ..params.vector import ParameterTable
from ..schemas.structure import Structure

#: How close two asymmetric-unit atoms' symmetry orbits may come, as a fraction
#: of a cell edge, before the pair is reported as a collision.  The same 1e-3
#: separation ``wyckoff.site_constraints`` uses to keep its probe atoms apart:
#: below it the two sites are the same site as far as any symmetry search is
#: concerned, which is exactly when F starts double-counting.
ORBIT_COLLISION_TOL = 1e-3

#: Cell-angle glyphs.  The *path* keeps the spelled-out name — it is a parameter
#: path — so this is display only, as it is in the frontend.
_ANGLE_GLYPH = {"alpha": "α", "beta": "β", "gamma": "γ"}

#: The ``entries`` arm's keys, so "nothing moved" and "nothing was computed" have
#: the same *shape* on the wire — a client renders one answer either way.
_EMPTY_ENTRIES: dict[str, list[str]] = {
    "added": [], "removed": [], "tied": [], "untied": [],
    "locked": [], "unlocked": []}


# ----------------------------------------------------------------------
# the free tier: what one gemmi lookup knows
# ----------------------------------------------------------------------
def _clean(text: Any) -> str:
    """gemmi spells "no extension" as ``'\\x00'`` and "not monoclinic" as ``' '``."""
    return str(text or "").replace("\x00", "").strip()


def setting_phrase(sg) -> str:
    """``"I a -3 d is cubic"`` — the subject of every cause sentence below.

    It names the **setting**, not the crystal system, because three settings
    disagree with the system alone (WP-1036) and a summary that shows the system
    but not the unique axis or the R axes is showing something that does not
    determine what the reader is looking at.
    """
    system = sg.crystal_system_str()
    if system == "monoclinic":
        return f"{sg.xhm()} is monoclinic with unique axis {_clean(sg.monoclinic_unique_axis())}"
    if system == "trigonal":
        axes = "rhombohedral" if _clean(sg.ext) == "R" else "hexagonal"
        return f"{sg.xhm()} is trigonal on {axes} axes"
    return f"{sg.xhm()} is {system}"


def phase_facts(phase, index: int) -> dict:
    """Everything one ``get_spacegroup`` call yields, for one phase.

    An unresolvable symbol comes back as an ``error`` row rather than raising:
    this arm rides on a read route, and a model that cannot resolve its own
    symbol is exactly the state a user needs the panel to keep rendering in.
    """
    try:
        sg = get_spacegroup(phase.space_group)
    except (ValueError, RuntimeError) as exc:
        return {"phase": index, "space_group": phase.space_group, "error": str(exc)}
    try:
        cons = cell_constraints(sg)
    except ValueError as exc:                # a system with no tie rule here
        cons = None
        tie_error = str(exc)
    else:
        tie_error = ""
    facts = {
        "phase": index,
        "space_group": phase.space_group,
        "xhm": sg.xhm(),
        "number": sg.number,
        "hall": sg.hall,
        "short_name": sg.short_name(),
        "ext": _clean(sg.ext),
        "qualifier": _clean(sg.qualifier),
        "crystal_system": sg.crystal_system_str(),
        "laue_class": sg.laue_str(),
        "point_group": sg.point_group_hm(),
        "centring": _clean(sg.centring_type()),
        "unique_axis": _clean(sg.monoclinic_unique_axis()),
        "centrosymmetric": bool(sg.is_centrosymmetric()),
        "sohncke": bool(sg.is_sohncke()),
        "enantiomorphic": bool(sg.is_enantiomorphic()),
        "symmorphic": bool(sg.is_symmorphic()),
        "reference_setting": bool(sg.is_reference_setting()),
        "setting": setting_phrase(sg),
        "ties": dict(cons.ties) if cons else {},
        "fixed_angles": dict(cons.fixed_angles) if cons else {},
        "tie_error": tie_error,
    }
    facts["constraints"] = _constraint_phrase(facts)
    return facts


def _constraint_phrase(facts: dict) -> str:
    """``"b = a, c = a · α = β = γ = 90°"`` — what the setting costs the cell."""
    ties = ", ".join(f"{k} = {v}" for k, v in facts["ties"].items())
    groups: dict[float, list[str]] = {}
    for name, value in facts["fixed_angles"].items():
        groups.setdefault(value, []).append(_ANGLE_GLYPH.get(name, name))
    held = " · ".join(" = ".join(names) + f" = {value:g}°"
                      for value, names in groups.items())
    parts = [p for p in (ties, held) if p]
    return " · ".join(parts) if parts else "every cell parameter is free"


def phase_summary(structure: Structure) -> list[dict]:
    """:func:`phase_facts` for every phase — the arm ``GET /api/structure`` adds."""
    return [phase_facts(phase, i) for i, phase in enumerate(structure.phases)]


# ----------------------------------------------------------------------
# what site symmetry allows each atom (moved here from session.py, WP-1035)
# ----------------------------------------------------------------------
def site_rows(structure: Structure) -> list[dict]:
    """Per atom: the DOF paths that move it, and what its site symmetry allows.

    Derived through the *same* functions ``ParameterTable`` uses
    (``stabilizer_rotations`` → ``coordinate_basis`` / ``adp_basis``), never a
    second rule.  The Wyckoff letter is deliberately absent — see the module
    docstring for what it costs and which route carries it.
    """
    rows: list[dict] = []
    for i, phase in enumerate(structure.phases):
        try:
            sg = get_spacegroup(phase.space_group)
        except (ValueError, RuntimeError) as exc:
            rows.append({"path": f"phases.{i}", "error": str(exc)})
            continue
        for j, atom in enumerate(phase.atoms):
            xyz = [atom.x.value, atom.y.value, atom.z.value]
            rots = stabilizer_rotations(sg, xyz)
            coord = coordinate_basis(rots)
            adp = adp_basis(rots)
            base = f"phases.{i}.atoms.{j}"
            rows.append({
                "path": base, "phase": i, "atom": j,
                # the stabilizer's order is the site symmetry's; 1 is a general
                # position, and anything above it is why a coordinate may not
                # be typed directly
                "site_symmetry_order": len(rots),
                "special": len(rots) > 1,
                "dof_paths": [f"{base}.dof.{k}" for k in range(len(coord))],
                "dof_directions": coord.tolist(),
                "adp_paths": ([f"{base}.adp.{k}" for k in range(len(adp))]
                              if atom.aniso is not None else []),
                "adp_patterns": adp.tolist(),
                "aniso": atom.aniso is not None,
            })
    return rows


# ----------------------------------------------------------------------
# naming the cause of a held row
# ----------------------------------------------------------------------
def held_causes(structure: Structure, rows: list[dict] | None = None,
                letters: dict[str, dict] | None = None) -> dict[str, str]:
    """``path → why symmetry holds it``, for the rows symmetry is responsible for.

    The parameter table already says a row is tied or locked, and
    ``ParameterRow.held_because`` says *that* it is "structurally fixed by
    symmetry or by the model" — a sentence with no subject.  This supplies the
    subject wherever the subject is symmetry, and stays silent everywhere else:
    a locked ``lor_strain`` is held by the Stephens block, not by a symmetry
    element, and claiming otherwise would be worse than the anonymous version.

    ``letters`` is the optional Wyckoff arm (``{path: {wyckoff, site_symmetry}}``
    from :func:`site_letters`); with it the atom sentences name the oriented site
    symmetry instead of only the stabiliser's order.  Without it they are still
    true, which is what lets the free tier carry them.
    """
    rows = site_rows(structure) if rows is None else rows
    by_path = {row["path"]: row for row in rows if "error" not in row}
    causes: dict[str, str] = {}
    for i, phase in enumerate(structure.phases):
        try:
            sg = get_spacegroup(phase.space_group)
            cons = cell_constraints(sg)
        except (ValueError, RuntimeError):
            continue
        where = setting_phrase(sg)
        for name, source in cons.ties.items():
            causes[f"phases.{i}.cell.{name}"] = f"{where}, so {name} follows {source}"
        for name, value in cons.fixed_angles.items():
            glyph = _ANGLE_GLYPH.get(name, name)
            causes[f"phases.{i}.cell.{name}"] = (
                f"{where}, so {glyph} is fixed at {value:g}°")
        _strain_causes(causes, f"phases.{i}", sg, phase)
        for j, atom in enumerate(phase.atoms):
            base = f"phases.{i}.atoms.{j}"
            row = by_path.get(base)
            if row is None:
                continue
            site = _site_phrase(row, (letters or {}).get(base))
            _coordinate_causes(causes, base, row, site)
            if atom.aniso is not None:
                _adp_causes(causes, base, row, site)
    return causes


def _site_phrase(row: dict, letter: dict | None) -> str:
    """``"Wyckoff 8a, site symmetry .3."`` when known, else the order alone."""
    if letter and letter.get("wyckoff"):
        return (f"Wyckoff {letter['wyckoff']}, site symmetry "
                f"{letter.get('site_symmetry') or '?'}")
    return f"a site symmetry of order {row['site_symmetry_order']}"


def _coordinate_causes(causes: dict, base: str, row: dict, site: str) -> None:
    n = len(row["dof_paths"])
    for axis in ("x", "y", "z"):
        if n == 0:
            causes[f"{base}.{axis}"] = (
                f"{site} allows no displacement at all — a fully fixed special "
                f"position, so {axis} cannot move")
        else:
            causes[f"{base}.{axis}"] = (
                f"{site} allows {n} direction(s), so {axis} is moved by "
                f"{base}.dof.* rather than typed")


def _adp_causes(causes: dict, base: str, row: dict, site: str) -> None:
    patterns = np.asarray(row["adp_patterns"], dtype=float).reshape(-1, 6)
    for v, name in enumerate(U_NAMES):
        if patterns.size and np.any(patterns[:, v]):
            causes[f"{base}.{name}"] = (
                f"{site} allows {len(patterns)} U^ij pattern(s), so {name.upper()} "
                f"follows {base}.adp.*")
        else:
            causes[f"{base}.{name}"] = f"{site} forces {name.upper()} to zero"
    causes[f"{base}.biso"] = (
        "this atom declares an anisotropic tensor, which owns the displacement "
        "channel outright — Biso is held so the two cannot both act")


def _strain_causes(causes: dict, base: str, sg, phase) -> None:
    """Stephens coefficients: the same story one rank up, keyed on the Laue class."""
    if phase.microstrain is None:
        return
    from ..crystallography.stephens import S_NAMES, strain_basis

    basis = strain_basis(rotation_matrices(sg))
    laue = sg.laue_str()
    for v, name in enumerate(S_NAMES):
        path = f"{base}.microstrain.{name}"
        if basis.size and np.any(basis[:, v]):
            causes[path] = (f"Laue class {laue} allows {len(basis)} Stephens "
                            f"pattern(s), so {name} follows {base}.microstrain.dof.*")
        else:
            causes[path] = f"Laue class {laue} forces {name} to zero"


# ----------------------------------------------------------------------
# the deliberately-opened tier: Wyckoff letters
# ----------------------------------------------------------------------
def site_letters(structure: Structure, phase: int) -> list[dict]:
    """Wyckoff letter and oriented site symmetry for one phase's atoms.

    One spglib search per atom (see the module docstring for the measured cost),
    which is why this is not an arm of ``GET /api/structure``.  A site spglib
    cannot place comes back with its ``error`` rather than sinking the route: the
    search fails when the coordinates are in a setting the operators disagree
    with, which is a *finding* about the model, not a server fault.
    """
    from ..crystallography.wyckoff import site_constraints

    try:
        block = structure.phases[phase]
    except IndexError:
        raise IndexError(f"no phase {phase} (the model has "
                         f"{len(structure.phases)})") from None
    rows: list[dict] = []
    for j, atom in enumerate(block.atoms):
        base = f"phases.{phase}.atoms.{j}"
        xyz = [atom.x.value, atom.y.value, atom.z.value]
        try:
            sc = site_constraints(block.space_group, xyz)
        except (ValueError, RuntimeError) as exc:
            rows.append({"path": base, "atom": j, "label": atom.label,
                         "error": str(exc)})
            continue
        rows.append({"path": base, "atom": j, "label": atom.label,
                     "wyckoff": sc.wyckoff, "site_symmetry": sc.site_symmetry,
                     "multiplicity": sc.multiplicity})
    return rows


# ----------------------------------------------------------------------
# the preview
# ----------------------------------------------------------------------
def with_symbol(structure: Structure, phase: int, symbol: str) -> Structure:
    """A deep copy of ``structure`` with one phase's space group replaced.

    The symbol is stored as gemmi's canonical ``xhm()``, which is what
    ``structure_from_cif`` stores — so a symbol typed as ``R -3 c`` and one read
    from a file end up spelled the same way, and the ``:H``/``:R`` extension a
    setting depends on is never dropped on the way in.
    """
    sg = get_spacegroup(symbol)
    candidate = structure.model_copy(deep=True)
    try:
        candidate.phases[phase].space_group = sg.xhm()
    except IndexError:
        raise IndexError(f"no phase {phase} (the model has "
                         f"{len(structure.phases)})") from None
    return candidate


def preview(structure: Structure, instrument, phase: int, symbol: str, *,
            free_paths: list[str] | None = None) -> dict:
    """What changing phase ``phase``'s space group to ``symbol`` would do.

    ``blocked`` is the gate the apply verb reads: it is true when the candidate
    model cannot build a parameter table, and when the change would put two
    asymmetric-unit atoms on one orbit at a *combined occupancy past 1* — the
    only reading of a shared orbit that is unambiguously a double count.
    Everything else — a setting change, a centring change, an orbit
    multiplicity, a free path that would be dropped or renumbered — is a
    **note**: each is a legitimate thing to intend, and refusing them would make
    the verb unable to *fix* a mis-declared setting, which is the commonest
    reason to reach for it.

    A **refused** candidate is given no consequences at all: its orbits and its
    centring would be computed from operators the model cannot carry, so only the
    refusal and the note explaining it are reported.

    Raises ``ValueError`` for an unresolvable symbol and ``IndexError`` for a
    phase that does not exist; the session maps both onto its own refusals.
    """
    candidate = with_symbol(structure, phase, symbol)
    before = phase_facts(structure.phases[phase], phase)
    after = phase_facts(candidate.phases[phase], phase)

    refusals = _refusals(candidate, instrument, phase)
    if refusals:
        return {
            "phase": phase, "from": before, "to": after,
            "changed": before.get("xhm") != after.get("xhm"),
            "blocked": True, "refusals": refusals,
            "notes": _cause_notes(before, after, phase),
            "entries": _EMPTY_ENTRIES.copy(), "sites": [],
        }
    # one orbit expansion per atom per side, shared by the collision check and
    # the site diff — the expensive half of this verb, and the reason it is one
    orbits = (_orbits(structure, phase), _orbits(candidate, phase))
    collisions = _collisions(structure, candidate, phase, orbits)
    multiplicity = ([len(o) for o in orbits[0]], [len(o) for o in orbits[1]])
    notes = _notes(structure, candidate, phase, before, after, free_paths or [],
                   multiplicity)
    notes.extend(collisions)
    return {
        "phase": phase,
        "from": before,
        "to": after,
        "changed": before.get("xhm") != after.get("xhm"),
        "blocked": any(n["kind"] == "orbit_collision" for n in collisions),
        "refusals": refusals,
        "notes": notes,
        "entries": _table_diff(structure, candidate, instrument),
        "sites": _site_diff(structure, candidate, phase, multiplicity),
    }


def _refusals(candidate: Structure, instrument, phase: int) -> list[dict]:
    """Every incompatible item, in the package's own words.

    A ``ParameterTable`` stops at the **first** refusal, so this probes the phase
    once (cell angles and the Stephens block, which are collected before any
    atom) and then once per atom, each against a real table.  The alternative —
    reading the message and neutralising what it names — would be a parser for
    sentences this module does not own.
    """
    block = candidate.phases[phase]
    try:
        check_cell_angles(get_spacegroup(block.space_group),
                          {n: getattr(block.cell, n).value
                           for n in ("alpha", "beta", "gamma")})
    except ValueError as exc:
        # the cell itself cannot carry the symbol: no atom probe would add
        # anything, because every one of them would report the same sentence
        return [{"where": f"phases.{phase}.cell", "message": str(exc)}]

    out: list[dict] = []
    if block.microstrain is not None:
        probe = _probe(candidate, phase, atoms=block.atoms[:1], microstrain=True)
        message = _build_error(probe, instrument)
        if message and message.split(":")[0] == "phases.0.microstrain":
            out.append({"where": f"phases.{phase}.microstrain",
                        "message": _relabel(message, phase, 0)})
    for j, atom in enumerate(block.atoms):
        probe = _probe(candidate, phase, atoms=[atom], microstrain=False)
        message = _build_error(probe, instrument)
        if message:
            out.append({"where": f"phases.{phase}.atoms.{j}",
                        "message": _relabel(message, phase, j)})
    return out


def _probe(candidate: Structure, phase: int, *, atoms, microstrain: bool) -> Structure:
    """A one-phase, one-atom structure — the smallest thing the real rule reads."""
    block = candidate.phases[phase].model_copy(deep=True)
    block.atoms = [a.model_copy(deep=True) for a in atoms]
    if not microstrain:
        block.microstrain = None
    probe = candidate.model_copy(deep=True)
    probe.phases = [block]
    return probe


def _relabel(message: str, phase: int, atom: int) -> str:
    """Put the probe's ``phases.0.atoms.0`` back where the caller's path is.

    The probe is one phase and one atom, so every path the refusal quotes is
    numbered from zero.  Rewriting is the price of getting the sentence *from*
    the real rule instead of restating it.
    """
    return (message.replace("phases.0.atoms.0", f"phases.{phase}.atoms.{atom}")
                   .replace("phases.0.microstrain", f"phases.{phase}.microstrain"))


def _build_error(probe: Structure, instrument) -> str:
    try:
        ParameterTable(probe, instrument)
    except ValueError as exc:
        return str(exc)
    return ""


def _table_diff(current: Structure, candidate: Structure, instrument) -> dict:
    """Which entries gain or lose a tie or a lock, and which appear or vanish.

    Nothing is recomputed here: ``Entry`` already carries ``tie`` and ``locked``,
    and the diff of two tables *is* the answer.  A current model whose own table
    cannot build (the state a pre-WP-1035 bad edit leaves the head in) diffs
    against nothing rather than failing — which is what lets this verb be the way
    *out* of that state.  The candidate's table is known to build: a caller that
    got here has already run :func:`_refusals`.
    """
    try:
        now = {e.path: e for e in ParameterTable(current, instrument).entries}
    except ValueError:
        return _EMPTY_ENTRIES.copy()
    then = {e.path: e for e in ParameterTable(candidate, instrument).entries}
    out = {k: list(v) for k, v in _EMPTY_ENTRIES.items()}
    out["added"] = sorted(then.keys() - now.keys())
    out["removed"] = sorted(now.keys() - then.keys())
    for path in sorted(now.keys() & then.keys()):
        a, b = now[path], then[path]
        if (a.tie is None) != (b.tie is None):
            out["tied" if b.tie is not None else "untied"].append(path)
        if a.locked != b.locked:
            out["locked" if b.locked else "unlocked"].append(path)
    return out


def _site_diff(current: Structure, candidate: Structure, phase: int,
               multiplicity: tuple[list[int], list[int]]) -> list[dict]:
    """Per atom, only where something moved: DOF count, ADP patterns, order —
    **and the orbit multiplicity**, which is none of those.

    The multiplicity is here because a browser pass caught the diff being silent
    about it: NAC's ``I 21 3`` → ``I 41 3 2`` leaves every stabiliser and every
    DOF exactly as it was (order 2/3/1, one or three directions) while every
    orbit doubles — 12 → 24, 8 → 16, 24 → 48 — so the cell holds twice as many
    atoms, F is computed over twice as many, and the phase scale means something
    else.  No parameter appears, no tie moves, and the preview read "no parameter
    gains or loses a tie".  It costs an orbit expansion per atom (0.4-1.3 ms,
    measured), which is why it is computed here and not on ``/api/structure``.
    """
    now = {r["path"]: r for r in site_rows(current) if "error" not in r}
    then = {r["path"]: r for r in site_rows(candidate) if "error" not in r}
    mult_now, mult_then = multiplicity
    out = []
    for j, atom in enumerate(candidate.phases[phase].atoms):
        base = f"phases.{phase}.atoms.{j}"
        a, b = now.get(base), then.get(base)
        if a is None or b is None:
            continue
        m_a = mult_now[j] if j < len(mult_now) else 0
        m_b = mult_then[j] if j < len(mult_then) else 0
        if (a["site_symmetry_order"] == b["site_symmetry_order"]
                and a["dof_directions"] == b["dof_directions"]
                and a["adp_patterns"] == b["adp_patterns"] and m_a == m_b):
            continue
        out.append({
            "path": base, "atom": j, "label": atom.label,
            "from": {"order": a["site_symmetry_order"], "multiplicity": m_a,
                     "dofs": len(a["dof_paths"]), "adps": len(a["adp_paths"]),
                     "dof_directions": a["dof_directions"]},
            "to": {"order": b["site_symmetry_order"], "multiplicity": m_b,
                   "dofs": len(b["dof_paths"]), "adps": len(b["adp_paths"]),
                   "dof_directions": b["dof_directions"]},
        })
    return out


def _notes(current: Structure, candidate: Structure, phase: int, before: dict,
           after: dict, free_paths: list[str],
           multiplicity: tuple[list[int], list[int]]) -> list[dict]:
    """The consequences of a change that *can* happen — see :func:`preview`."""
    notes: list[dict] = []
    n_before, n_after = sum(multiplicity[0]), sum(multiplicity[1])
    if n_before != n_after and n_before and n_after:
        # the second thing the entry diff is blind to, and the one a browser
        # pass caught: NAC's I 21 3 → I 41 3 2 moves no parameter at all and
        # doubles every orbit (see _site_diff)
        notes.append({
            "kind": "multiplicity_change",
            "where": [f"phases.{phase}.space_group"],
            "message": (
                f"the cell would hold {n_after} atoms instead of {n_before}: "
                f"every site's orbit is regenerated under the new operators. F "
                f"is computed over a different number of atoms, so the phase "
                f"scale — and any QPA fraction derived from it — no longer means "
                f"what it did, whatever the parameter table says below."),
        })
    notes.extend(_cause_notes(before, after, phase))
    if (before.get("centring") != after.get("centring")
            and not before.get("error") and not after.get("error")):
        # the one big change the entry diff is structurally blind to: centring
        # extinguishes reflections, and no parameter appears or disappears for it
        notes.append({
            "kind": "centring_change",
            "where": [f"phases.{phase}.space_group"],
            "message": (
                f"the lattice centring changes {before['centring']} → "
                f"{after['centring']}, which changes the reflection *list* and "
                "not one parameter — the systematic absences are recomputed at "
                "the next stage compile, so Rwp will move even though nothing "
                "below says anything did."),
        })
    notes.extend(_free_path_notes(current, candidate, phase, free_paths))
    return notes


def _cause_notes(before: dict, after: dict, phase: int) -> list[dict]:
    """The notes that explain the *request* rather than its consequences.

    A setting change survives a refusal because it is usually what caused one: a
    ``R -3 c:R`` typed over a hexagonal-axes cell is refused on γ, and the
    sentence a reader needs is "these are the same group on different axes".
    """
    if (before.get("number") != after.get("number")
            or before.get("xhm") == after.get("xhm")):
        return []
    return [{
        "kind": "setting_change",
        "where": [f"phases.{phase}.space_group"],
        "message": (
            f"{before['xhm']} and {after['xhm']} are the same space group "
            f"(No. {after['number']}) in different settings — "
            f"{before['setting']}, {after['setting']}. Every coordinate and "
            "every cell edge is read on the other axes; nothing here converts "
            "them, so the numbers must already be in the setting you are "
            "choosing."),
    }]


def _free_path_notes(current: Structure, candidate: Structure, phase: int,
                     free_paths: list[str]) -> list[dict]:
    """What the restore of ``_free_paths`` would drop, and what it would misread.

    ``…dof.k`` and ``…adp.k`` are **positional**.  A path that vanishes at least
    warns (``_prepare_table`` emits a ``UserWarning`` nothing in the GUI shows);
    a path that survives with a *different direction behind it* does not even do
    that — it is silently freed as something else.
    """
    if not free_paths:
        return []
    now = {r["path"]: r for r in site_rows(current) if "error" not in r}
    then = {r["path"]: r for r in site_rows(candidate) if "error" not in r}
    prefix = f"phases.{phase}."
    dropped, renumbered = [], []
    for path in free_paths:
        if not path.startswith(prefix):
            continue
        head, _, tail = path.rpartition(".")
        base, _, kind = head.rpartition(".")
        if kind not in ("dof", "adp") or base not in then:
            continue
        key = "dof_directions" if kind == "dof" else "adp_patterns"
        index = int(tail) if tail.isdigit() else -1
        old = now.get(base, {}).get(key, [])
        new = then[base][key]
        if index < 0 or index >= len(new):
            dropped.append(path)
        elif index < len(old) and old[index] != new[index]:
            renumbered.append(path)
    notes = []
    if dropped:
        notes.append({
            "kind": "free_paths_dropped", "where": dropped,
            "message": (f"{len(dropped)} refined parameter(s) would stop "
                        f"existing and be dropped from the free set: "
                        f"{', '.join(dropped[:5])}"
                        f"{'…' if len(dropped) > 5 else ''}")})
    if renumbered:
        notes.append({
            "kind": "free_paths_renumbered", "where": renumbered,
            "message": (f"{len(renumbered)} refined parameter(s) keep their path "
                        f"and change meaning — the DOF index is positional, so "
                        f"the next run would free a different direction: "
                        f"{', '.join(renumbered[:5])}"
                        f"{'…' if len(renumbered) > 5 else ''}")})
    return notes


def _orbits(structure: Structure, phase: int) -> list[np.ndarray]:
    """Each asymmetric-unit atom's symmetry orbit, or ``[]`` if the symbol fails.

    The expensive part of the preview — 0.4-1.3 ms an atom, measured — so it is
    computed once and handed to both readers (the collision check and the
    multiplicity half of the site diff) rather than twice.
    """
    block = structure.phases[phase]
    try:
        sg = get_spacegroup(block.space_group)
    except (ValueError, RuntimeError):
        return []
    return [np.asarray(expand_positions(sg, np.array(
        [a.x.value, a.y.value, a.z.value])), dtype=float) for a in block.atoms]


def orbit_collisions(structure: Structure, phase: int,
                     orbits: list[np.ndarray] | None = None
                     ) -> list[tuple[int, int, float]]:
    """Asymmetric-unit atom pairs whose symmetry orbits coincide.

    ``structure_factor.select_orbit_ops`` dedups images *within* one atom's
    orbit; two atoms the symmetry maps onto each other are two full orbits at the
    same places, so F counts the site twice and no existing check says so.  The
    distance is returned in Å, through the cell's own metric, because a
    fractional tolerance means three different things in three different cells.
    """
    block = structure.phases[phase]
    basis = cartesian_basis(*block.cell.lengths_angles())
    orbits = _orbits(structure, phase) if orbits is None else orbits
    out = []
    for i in range(len(orbits)):
        for j in range(i + 1, len(orbits)):
            delta = orbits[i][:, None, :] - orbits[j][None, :, :]
            delta = ((delta + 0.5) % 1.0) - 0.5
            if float(np.abs(delta).max(axis=-1).min()) > ORBIT_COLLISION_TOL:
                continue
            gap = float(np.linalg.norm(delta.reshape(-1, 3) @ basis.T, axis=1).min())
            out.append((i, j, gap))
    return out


def _collisions(current: Structure, candidate: Structure, phase: int,
                orbits: tuple[list[np.ndarray], list[np.ndarray]]) -> list[dict]:
    """Collisions the change *creates*, and whether each one is an error.

    A shared orbit is **not** automatically a bug: a mixed site — Na at occ 0.5
    beside Ca at occ 0.5 on the same 12b — is standard modelling, and F is right
    for it, because each atom contributes its own occupancy-weighted orbit.  What
    is wrong is the *same site counted twice*, and the criterion for that is
    physical rather than a guess about the crystallographer's intent: the
    occupancies on the shared orbit sum past 1.  So over-occupancy blocks and a
    legal mixed site is reported as a note.

    A collision that exists **before** the change is never this edit's, so it is
    reported as its own kind and never blocks — otherwise a project with a mixed
    site could not change its symmetry at all.
    """
    try:
        before = {(i, j) for i, j, _ in orbit_collisions(current, phase, orbits[0])}
        found = orbit_collisions(candidate, phase, orbits[1])
    except (ValueError, RuntimeError):
        return []
    atoms = candidate.phases[phase].atoms
    symbol = candidate.phases[phase].space_group
    notes = []
    for i, j, gap in found:
        share = atoms[i].occ.value + atoms[j].occ.value
        pair = f"{atoms[i].label} and {atoms[j].label}"
        where = [f"phases.{phase}.atoms.{i}", f"phases.{phase}.atoms.{j}"]
        if (i, j) in before:
            notes.append({
                "kind": "orbit_collision_existing", "where": where,
                "message": (f"{pair} already share an orbit ({gap:.3g} Å) before "
                            f"this change, at a combined occupancy of {share:g} — "
                            f"not caused by the symbol, and not changed by it.")})
        elif share > 1.0 + 1e-6:
            notes.append({
                "kind": "orbit_collision", "where": where,
                "message": (
                    f"{pair} become symmetry-equivalent under {symbol}: their "
                    f"orbits coincide to {gap:.3g} Å at a combined occupancy of "
                    f"{share:g}, so the structure factor would count that site "
                    f"{share:g} times over. Remove one of the two atoms and give "
                    f"the survivor the occupancy they should share.")})
        else:
            notes.append({
                "kind": "orbit_collision_shared", "where": where,
                "message": (
                    f"{pair} become symmetry-equivalent under {symbol} ({gap:.3g} "
                    f"Å apart), at a combined occupancy of {share:g}. That is a "
                    f"legal mixed site and F is right for it — but if they were "
                    f"meant to be two independent sites, this symbol has just "
                    f"merged them.")})
    return notes

"""Interatomic distances and angles, with esds from the full covariance (WP-1072).

McCusker *et al.* (1999), *J. Appl. Cryst.* **32**, 36, names this twice.  §11
makes it one of the two "most important criteria for judging the quality of a
Rietveld refinement" — "Interatomic distances (both bonding and nonbonding)
should be reasonable, bond angles sensible" — and §10 says how the numbers
beside them must be computed: "The whole correlation matrix, not just the
diagonal elements, should be included in the calculation" of a derived
quantity's e.s.d.

Both halves are here.  The table is built at fit close because **the covariance
is never serialized** — it is read off the final Jacobian, the
:class:`~rietx.schemas.results.Identifiability` carrier argument — so a
distance's esd is measured here or lost.  A replayed or loaded result carries
what was stored, or ``None``; nothing downstream recomputes a diagonal-only
esd and calls it the answer.

**Reuse, not re-derivation.**  A bond distance is d = √(Δxᵀ·G·Δx) and an angle
is its arccos twin — exactly the soft restraints of :mod:`.restraints`, whose
``_bond_row_partials`` / ``_angle_row_partials`` already implement the
derivative chain through the coordinate DOFs' affine ties (p = C·θ + d,
WP-0301) *and* the six cell parameters.  So a geometry row **is** a restraint
row with σ = 1 and weight = 1, and its partials come from the function the
Jacobian itself uses.  :func:`~rietx.optimize.qpa.weight_fractions` is the
propagation precedent: J·Cov·Jᵀ with the diagonal-only number returned beside
it, so the difference §10 warns about is visible rather than asserted.

**What is listed.**  For each phase, every image of every atom within reach of
each asymmetric-unit atom, generated over that atom's *frozen* orbit ops (the
subsets :class:`~rietx.crystallography.structure_factor.PhaseSites` gave the
forward model — the geometry table and the structure factors count the same
orbits) crossed with a lattice shell wide enough for the cutoff.  A pair is a
**bond** when d ≤ r_cov(i) + r_cov(j) + :data:`BOND_SLACK_ANG` and a
**contact** otherwise, out to :data:`CONTACT_MAX_ANG`.

**Every asymmetric-unit atom gets its whole environment**, and nothing is
deduplicated against anything else.  A bond between two different sites
therefore appears twice, once from each end — which is *not* the CIF
convention, and is deliberate: the two directions are not the same list.  In
α-quartz Si has four O neighbours while each O has two Si (the relation is
4·3 = 2·6 over the two multiplicities), so a table listing only one direction
makes the other atom's coordination number unreadable without multiplicity
arithmetic — and coordination is exactly what §11 asks a reader to check.  The
CIF exporter drops one direction on its way out, where the audience is a
parser rather than a chemist.

The same reasoning settles the same-site case, which has no direction to drop:
x and S(x) and x and S⁻¹(x) are two *different* bonds that both touch x, so
both are listed, and the neighbour count is the coordination number.  Angles
are listed at each vertex over that vertex's complete bonded environment.
"""

from __future__ import annotations

import math

import gemmi
import numpy as np

from ..crystallography.symmetry import get_spacegroup
from .restraints import (
    _COS_CLAMP,
    CompiledRestraints,
    _Angle,
    _Bond,
    _metric_g,
    _xyz_np,
    restraint_partials,
)

#: A pair is *bonded* when its distance is at most the sum of the two covalent
#: radii plus this slack, in Å.  The radii are gemmi's
#: ``gemmi.Element.covalent_r``, which reproduces Cordero *et al.* (2008),
#: *Dalton Trans.*, 2832 ("Covalent radii revisited") — checked against 30
#: single-valued entries of its Table 1, agreeing to < 5·10⁻³ Å throughout, so
#: the citation is a measurement rather than a remembered attribution.
#:
#: The slack is **not** a physical constant and is cited to nobody: 0.4 Å is
#: the tolerance bond-perception software conventionally allows, and it decides
#: which *loop* a row is listed in and nothing else — a pair past it is still
#: reported, as a contact.  It travels on ``GeometryTable.bond_slack`` so a
#: reader never has to guess which value produced a table.
BOND_SLACK_ANG = 0.40

#: A radius criterion is not evidence of a metal-metal bond, so a pair of two
#: metals (``gemmi.Element.is_metal``) is listed as a contact whatever its
#: distance.  Without this the covalent radii make α-Al₂O₃'s face- and
#: edge-sharing Al···Al pairs at 2.65 and 2.79 Å "bonds" — the sum plus the
#: slack is 2.82 Å — and every angle at an Al then carries them as arms.  The
#: distances are still reported; only the loop they land in changes.
DEMOTE_METAL_METAL = True

#: Non-bonded contacts are searched out to this distance, in Å.  McCusker §11
#: asks for "both bonding and nonbonding" distances without naming a range.
#: This is a **search radius**, not a physical constant: 3.5 Å reaches the
#: second coordination sphere of the oxides and framework solids powder
#: Rietveld is usually about (ZnO's nearest Zn···Zn and O···O are both the
#: 3.25 Å a axis), and is short enough that the row count stays readable.  It
#: is recorded on the table, so a row can be read without guessing it.
CONTACT_MAX_ANG = 3.5

#: Contacts kept per asymmetric-unit atom, nearest first.  Bonds and angles are
#: uncapped — chemistry bounds them — but the contact count grows with the
#: cutoff volume, and a table nobody can read is not evidence.  Whatever this
#: drops is counted in ``GeometryTable.notes``, never dropped in silence: a
#: firing cap is also the one thing that breaks the orbit-count relation the
#: search is checked with, since it can truncate one direction of a pair and
#: not the other.
MAX_CONTACTS_PER_ATOM = 24

#: Phases with more asymmetric-unit atoms than this are skipped, and said in
#: ``GeometryTable.notes`` to be skipped.  The search is O(n²·m·shell³) and
#: runs at fit close, where a minute spent on a table is a minute stolen from
#: the refinement.
MAX_ASYM_ATOMS = 200

#: A CIF symmetry code ``n_klm`` encodes each lattice translation as one digit
#: offset by 5, so it can express shifts in −4…+4 only.  An image needing more
#: (reachable only when a stored fractional coordinate sits several cells out)
#: carries ``None`` here and ``?`` in the exported loop; the distance and its
#: esd are unaffected.
SYMMETRY_CODE_MAX_SHIFT = 4

#: A variance this small a fraction of its own quadratic form's absolute terms
#: is cancellation, not a measurement, and the esd is reported as absent.
#: **This is a floating-point floor, not a threshold on the physics.**  A
#: symmetry-constrained quantity has *exactly* zero variance — rutile's
#: O–Ti–O angle stays at 90° however the one free DOF moves — but its partials
#: against the individual x, y, z entries are not zero, so gᵀ·Cov·g reaches
#: zero by cancelling terms and lands on roundoff.  Left alone that prints as
#: ``90.00000000000(43)``, an uncertainty of 4·10⁻¹² degrees quoted with a
#: straight face.  The test is self-scaling (var against Σ|terms|, so it means
#: the same for a 2 Å distance and a 180° angle) and sits four orders above
#: fp64's own epsilon and five below the smallest esd a powder refinement
#: produces.
VARIANCE_CANCELLATION_FLOOR = 1e-12

#: How close to 0° or 180° an angle may come and still carry an esd, in
#: degrees — **derived** from the clamp :mod:`.restraints` applies to cos θ,
#: not chosen, so the two cannot drift apart.  Inside it the partials that come
#: back are the clamp's rather than the geometry's, and the linearisation
#: J·Cov·Jᵀ rests on is invalid anyway: a straight angle is a stationary point
#: of the coordinates (it can only bend one way), so it has no first-order
#: variance to propagate.  The angle itself is still exact — only its esd is
#: withheld.
ANGLE_LINEARISATION_LIMIT_DEG = math.degrees(math.acos(_COS_CLAMP))

#: an image closer than this (Å²) to the reference atom is the atom itself
_COINCIDENT_D2 = 1e-6

_CELL_NAMES = ("a", "b", "c", "alpha", "beta", "gamma")
_XYZ = ("x", "y", "z")


# ----------------------------------------------------------------------
# neighbour generation
# ----------------------------------------------------------------------
def _shell(g: np.ndarray, cutoff: float) -> np.ndarray:
    """Integer lattice shifts covering ``cutoff`` around a centred image.

    The perpendicular spacing of the (100) planes is 1/√(G\\*₁₁), so a cutoff
    of ``c`` reaches ``ceil(c·√(G*₁₁))`` cells along **a**, and likewise for
    **b** and **c**; the extra cell absorbs the ≤ ½-cell offset left by
    centring each image on the reference atom.
    """
    gstar = np.linalg.inv(g)
    reach = [int(math.ceil(cutoff * math.sqrt(gstar[k, k]))) + 1 for k in range(3)]
    grids = np.meshgrid(*[np.arange(-r, r + 1) for r in reach], indexing="ij")
    return np.stack([grid.ravel() for grid in grids], axis=1).astype(np.float64)


def symmetry_operations(space_group: str) -> list[str]:
    """The ``x,y,z`` triplets of ``space_group``, in gemmi's listing order.

    A symmetry code is an index into a listed order, so it means nothing
    without one: the CIF exporter writes this loop whenever it writes a code
    (:func:`~rietx.io.exporters.refinement_cif_doc`), rather than leaving a
    reader to re-derive the order from the Hermann-Mauguin symbol and hope it
    matches.
    """
    return [op.triplet() for op in get_spacegroup(space_group).operations()]


def _symop_table(space_group: str) -> list[tuple[np.ndarray, np.ndarray]]:
    """(R, t) of every operation of ``space_group``, in the same order."""
    return [(np.array(op.rot, dtype=np.float64) / gemmi.Op.DEN,
             np.array(op.tran, dtype=np.float64) / gemmi.Op.DEN)
            for op in get_spacegroup(space_group).operations()]


def _symop_index(symops, rot: np.ndarray, tran: np.ndarray) -> int | None:
    """Index of ``(rot, tran)`` in the space group's operation list, or None.

    Exact comparison is right here: both sides come from the same gemmi ops
    divided by the same ``Op.DEN``, so the frozen orbit subset holds bit-equal
    copies of the listed operations rather than reconstructions of them.
    """
    for idx, (r, t) in enumerate(symops):
        if np.array_equal(r, rot) and np.array_equal(t, tran):
            return idx
    return None


def _symmetry_code(index: int | None, shift: np.ndarray) -> str | None:
    """CIF ``n_klm`` code for operation ``index`` plus lattice ``shift``."""
    if index is None:
        return None
    n = [int(round(float(v))) for v in shift]
    if any(abs(v) > SYMMETRY_CODE_MAX_SHIFT for v in n):
        return None
    if index == 0 and not any(n):
        return "."
    return f"{index + 1}_{5 + n[0]}{5 + n[1]}{5 + n[2]}"


def _neighbours(sites, values, ip: int, i: int, g: np.ndarray,
                shifts: np.ndarray, cutoff: float) -> list[tuple]:
    """``(j, R, t, n, d)`` for every image within ``cutoff`` of atom ``i``.

    Vectorised over (orbit op × lattice shift) per neighbour site, because the
    scalar loop is O(n²·m·shell³) and this runs at fit close.  Each image is
    first centred on the reference atom (``round(x_i − image)``), so ``shifts``
    only has to cover the cutoff rather than wherever the stored coordinates
    happen to sit.
    """
    x_i = _xyz_np(values, ip, i)
    out = []
    for j in range(sites.n_asym):
        ops_r, ops_t = sites.ops[j]
        x_j = _xyz_np(values, ip, j)
        img0 = np.einsum("mab,b->ma", ops_r, x_j) + ops_t          # (m, 3)
        base = np.round(x_i - img0)                                # (m, 3)
        dx = (img0 + base)[:, None, :] + shifts[None, :, :] - x_i  # (m, s, 3)
        d2 = np.einsum("msa,ab,msb->ms", dx, g, dx)
        for m, s in np.argwhere((d2 > _COINCIDENT_D2) & (d2 <= cutoff * cutoff)):
            out.append((j, ops_r[m], ops_t[m], base[m] + shifts[s],
                        math.sqrt(float(d2[m, s]))))
    out.sort(key=lambda row: row[4])
    return out


# ----------------------------------------------------------------------
# per-phase assembly
# ----------------------------------------------------------------------
def _element(species: str) -> gemmi.Element:
    """The element behind a scattering species (``"Zn2+"`` → Zn).

    ``optimize.qpa.element_symbol`` is the one parser — it already rejects the
    symbols gemmi maps to its placeholder element, and a covalent radius of
    1.0 Å for a mis-parsed species would silently reclassify every one of its
    contacts.
    """
    from ..optimize.qpa import element_symbol

    return gemmi.Element(element_symbol(species))


def _angle_degrees(item: _Angle, values: dict) -> float:
    """The angle at ``item``'s vertex, stable at 0° and 180°.

    ``restraints._angle_value_np`` clamps cos θ just inside [−1, 1] because a
    restraint's derivative goes as 1/sin θ there; that is right for a residual
    row and wrong for a reported number — it turns fluorite's linear F–Ca–F
    into 179.997°.  The half-angle form θ = 2·atan2(‖û − v̂‖, ‖û + v̂‖) (Kahan)
    needs no clamp and is exact at both ends, with the norms taken in the
    direct metric because the arms are fractional.
    """
    ip = item.phase
    g = _metric_g(tuple(values[f"phases.{ip}.cell.{k}"] for k in _CELL_NAMES))
    u = item.Ri @ _xyz_np(values, ip, item.i) + item.ti + item.ni \
        - _xyz_np(values, ip, item.j)
    v = item.Rk @ _xyz_np(values, ip, item.k) + item.tk + item.nk \
        - _xyz_np(values, ip, item.j)

    def norm(w):
        return math.sqrt(max(float(w @ (g @ w)), 0.0))

    nu, nv = norm(u), norm(v)
    if nu <= 0.0 or nv <= 0.0:
        return float("nan")
    uh, vh = u / nu, v / nv
    return math.degrees(2.0 * math.atan2(norm(uh - vh), norm(uh + vh)))


def _phase_items(phase, sites, values, ip: int, notes: list[str]):
    """``(labels, bonds, contacts, angles)`` descriptors for one phase.

    Bonds and contacts are ``(reference atom, neighbour entry)`` pairs; an
    angle is ``(vertex, entry, entry)``.  An entry carries what the ``_Bond``
    and ``_Angle`` items built from it cannot: the distance, and the symmetry
    code of the image.
    """
    cell = tuple(values[f"phases.{ip}.cell.{k}"] for k in _CELL_NAMES)
    g = _metric_g(cell)
    shifts = _shell(g, CONTACT_MAX_ANG)
    symops = _symop_table(phase.space_group)
    elements = [_element(a.species) for a in phase.atoms]
    radii = [float(e.covalent_r) for e in elements]
    metal = [bool(e.is_metal) for e in elements]
    labels = [a.label for a in phase.atoms]

    bonds, contacts, angles = [], [], []
    dropped = 0
    for i in range(sites.n_asym):
        bonded, near = [], []
        for j, rot, tran, shift, d in _neighbours(sites, values, ip, i, g,
                                                  shifts, CONTACT_MAX_ANG):
            entry = (j, rot, tran, shift, d,
                     _symmetry_code(_symop_index(symops, rot, tran), shift))
            if (d <= radii[i] + radii[j] + BOND_SLACK_ANG
                    and not (DEMOTE_METAL_METAL and metal[i] and metal[j])):
                bonded.append(entry)
            else:
                near.append(entry)
        if len(near) > MAX_CONTACTS_PER_ATOM:
            dropped += len(near) - MAX_CONTACTS_PER_ATOM
            near = near[:MAX_CONTACTS_PER_ATOM]
        bonds.extend((i, e) for e in bonded)
        contacts.extend((i, e) for e in near)
        for a in range(len(bonded)):
            for b in range(a + 1, len(bonded)):
                angles.append((i, bonded[a], bonded[b]))
    if dropped:
        notes.append(f"{phase.name}: {dropped} contact(s) beyond the nearest "
                     f"{MAX_CONTACTS_PER_ATOM} per atom are not listed")
    return labels, bonds, contacts, angles


def _bond_item(ip: int, i: int, entry) -> _Bond:
    j, rot, tran, shift, _d, _code = entry
    return _Bond(ip, i, j, rot, tran, shift, target=0.0, sigma=1.0, weight=1.0)


def _angle_item(ip: int, vertex: int, first, second) -> _Angle:
    ja, rot_a, tran_a, shift_a, _da, _ca = first
    jb, rot_b, tran_b, shift_b, _db, _cb = second
    return _Angle(ip, ja, vertex, jb, rot_a, tran_a, shift_a,
                  rot_b, tran_b, shift_b,
                  target_deg=0.0, sigma=1.0, weight=1.0)


# ----------------------------------------------------------------------
# esds: J·Cov·Jᵀ through the full covariance (McCusker §10)
# ----------------------------------------------------------------------
def _phase_paths(ip: int, n_atoms: int) -> list[str]:
    """Every table entry a distance or angle of phase ``ip`` can touch."""
    return ([f"phases.{ip}.atoms.{j}.{c}" for j in range(n_atoms) for c in _XYZ]
            + [f"phases.{ip}.cell.{k}" for k in _CELL_NAMES])


def _sigmas(items, values, table, ip: int, n_atoms: int, cov) -> list[tuple]:
    """``(σ_full, σ_diagonal)`` per item, or ``(None, None)`` without a covariance.

    σ² = gᵀ·Cov·g with g the row of ∂(value)/∂p over the phase's coordinate and
    cell entries — the same partials the Jacobian chains through the affine
    constraint block, so a coordinate refined as a site-symmetry DOF propagates
    through its tie rather than around it.

    ``cov`` is the pair (full, diagonal-only), both built by
    ``ParameterTable.physical_covariance`` — the second by handing it no
    correlation matrix, which is exactly §10's "just the diagonal elements".
    What is zeroed is the **refined parameters'** correlation, not the entry
    covariance: a crystal-system tie or a site-symmetry DOF is a constraint
    rather than a correlation, and dropping it would compare against a number
    nobody computes.  With uncorrelated parameters the two therefore agree
    exactly, which is what the test asserts.

    A row whose variance comes out zero — or only as far above zero as
    :data:`VARIANCE_CANCELLATION_FLOOR` allows — reports ``None``.  Either it
    touches nothing that was refined (every coordinate symmetry-fixed, the
    cell held: fluorite) or symmetry holds it fixed while its individual
    partials do not vanish (rutile's 90° O–Ti–O).  That is
    ``weight_fractions``' rule — an all-zero block is absence of information,
    never σ = 0 — with the cancelling case counted as the same thing, because
    it is.

    A fifth way to have no number arrived with WP-1110 item 14: a row drawing
    on an entry that was refined and **measured nothing**.  Its column is
    zeroed in ``Cov_free`` rather than carried as the infinity it is, since one
    infinity NaNs every product against a zero coefficient — so without the
    mask such a row reports the variance of its *other* sources and reads as a
    measurement.  A row whose partials touch nothing blind is unaffected, which
    is the case that matters: an unmeasured profile term must not cost a bond
    length its esd.
    """
    if not items:
        return []
    if cov is None:
        return [(None, None)] * len(items)
    cov_full, cov_diag, blind = cov
    rows = restraint_partials(CompiledRestraints(items=items), values, table)
    cols = [table._paths[p] for p in _phase_paths(ip, n_atoms)]
    g = rows[:, cols]
    var_full = np.einsum("ra,ab,rb->r", g, cov_full, g)
    var_diag = np.einsum("ra,ab,rb->r", g, cov_diag, g)
    scale = np.einsum("ra,ab,rb->r", np.abs(g), np.abs(cov_full), np.abs(g))
    floor = VARIANCE_CANCELLATION_FLOOR * scale
    touches_blind = (np.abs(g[:, blind]) > 0.0).any(axis=1) if blind.any() \
        else np.zeros(len(items), dtype=bool)
    return [(None, None) if (b or f <= max(fl, 0.0)) else
            (math.sqrt(f), math.sqrt(max(float(d), 0.0)))
            for f, d, fl, b in zip(var_full, var_diag, floor, touches_blind,
                                   strict=True)]


def geometry_table(model, table, theta: np.ndarray, structure, *,
                   stderr_internal=None, correlation=None):
    """The converged model's distances and angles, or ``None``.

    ``None`` outside Rietveld mode, where the mandatory dummy atom of a Le Bail
    or Pawley phase is not a structure to measure.  Without ``stderr_internal``
    (a replay, an evaluate-only pass) the geometry is still reported and every
    esd is ``None`` — the values are recomputable from the model, the
    covariance is not.
    """
    from ..schemas.results import GeometryAngle, GeometryDistance, GeometryTable

    if model.mode != "rietveld":
        return None
    values = table.decode(theta)
    notes: list[str] = []
    distances: list[GeometryDistance] = []
    angles: list[GeometryAngle] = []
    for ip, cp in enumerate(model.phases):
        phase = structure.phases[ip]
        if cp.sites.n_asym > MAX_ASYM_ATOMS:
            notes.append(f"{phase.name}: {cp.sites.n_asym} asymmetric-unit atoms "
                         f"exceeds the {MAX_ASYM_ATOMS}-atom search limit; no "
                         "geometry listed for this phase")
            continue
        labels, bonds, contacts, angle_rows = _phase_items(
            phase, cp.sites, values, ip, notes)
        n_atoms = len(phase.atoms)
        cov = None
        if stderr_internal is not None:
            paths = _phase_paths(ip, n_atoms)
            cov = (table.physical_covariance(theta, stderr_internal,
                                             correlation, paths),
                   table.physical_covariance(theta, stderr_internal,
                                             None, paths),
                   table.unmeasured_rows(theta, stderr_internal,
                                         [table._paths[q] for q in paths]))
        pairs = ([(i, e, True) for i, e in bonds]
                 + [(i, e, False) for i, e in contacts])
        pair_items = [_bond_item(ip, i, e) for i, e, _ in pairs]
        angle_items = [_angle_item(ip, v, a, b) for v, a, b in angle_rows]
        pair_sigma = _sigmas(pair_items, values, table, ip, n_atoms, cov)
        angle_sigma = _sigmas(angle_items, values, table, ip, n_atoms, cov)
        for (i, entry, is_bond), (sig, sig_d) in zip(pairs, pair_sigma,
                                                     strict=True):
            j, _rot, _tran, _shift, d, code = entry
            distances.append(GeometryDistance(
                phase_index=ip, atom_1=labels[i], atom_2=labels[j],
                atom_index_1=i, atom_index_2=j,
                distance=d, stderr=sig, stderr_diagonal=sig_d,
                symmetry_2=code, bonded=is_bond))
        for (v, a, b), item, (sig, sig_d) in zip(angle_rows, angle_items,
                                                 angle_sigma, strict=True):
            degrees = _angle_degrees(item, values)
            if min(degrees, 180.0 - degrees) < ANGLE_LINEARISATION_LIMIT_DEG:
                sig = sig_d = None
            angles.append(GeometryAngle(
                phase_index=ip, atom_1=labels[a[0]], atom_2=labels[v],
                atom_3=labels[b[0]], atom_index_1=a[0], atom_index_2=v,
                atom_index_3=b[0], angle=degrees,
                stderr=sig, stderr_diagonal=sig_d,
                symmetry_1=a[5], symmetry_3=b[5]))
    return GeometryTable(distances=distances, angles=angles,
                         bond_slack=BOND_SLACK_ANG, contact_max=CONTACT_MAX_ANG,
                         notes=notes)

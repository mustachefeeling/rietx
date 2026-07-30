"""The structure as drawable geometry — symmetry expansion, bonds, ellipsoids.

WP-1015.  Everything here is *crystallography*, and that is the whole reason the
module exists on this side of the wire: the browser receives Cartesian points,
3×3 matrices and index pairs, and draws them.  It never sees a space group, a
metric tensor or a U^ij.  The rule is WP-1010's one rank up — the frontend does
not re-derive what the package already computes, because two answers to "where
is this atom" is one more than a viewer may have.

Three things are computed here that ``GET /api/structure`` cannot say, which is
what earns the route its place beside it (WP-1008's test for a new route):

* **the orbit** — every symmetry image of every asymmetric-unit atom, from
  :func:`~pxrdref.crystallography.symmetry.expand_orbit`, *with* the rotation
  that produced it, because a displacement ellipsoid transforms as
  U\\* → R·U\\*·Rᵀ and an image drawn with its parent's tensor is drawn wrong
  in every non-orthogonal setting;
* **bonds**, by a radius-sum cutoff over the 27 nearest lattice translations, so
  a bond that leaves the cell is drawn leaving it rather than silently missing;
* **the cell frame**, as eight Cartesian corners and the twelve index pairs that
  join them.

**The ellipsoid is a diagnostic, not decoration.**  Its axes are refined
quantities: an over-flexible background inflates ADPs (CLAUDE.md's block
projection R², which Rwp *improves* through), and that arrives here as balloons.
A tensor that is not positive definite — the existing
``ADP_NOT_POSITIVE_DEFINITE`` diagnostic — is a physical impossibility rather
than a large number, so it is flagged and its non-positive semi-axes are drawn
at **zero**: the ellipsoid collapses to a disc or a needle, which is visibly
degenerate and is not a NaN.  ``√(negative)`` would be, and a NaN vertex takes
the whole mesh with it.

Representations follow ``crystallography/adp.py`` exactly: stored **U^ij**,
fractional **U\\***, and **U_cart** where the eigenvalues are the physical
mean-square displacements.  The isotropic limit is written out here rather than
routed through :func:`~pxrdref.crystallography.adp.isotropic_u6` because it is
exactly a sphere and the algebra says so: U^ij = Uiso·G*ᵢⱼ/(a*ᵢa*ⱼ) gives
U\\* = Uiso·G*, and U_cart = M·(Uiso·G*)·Mᵀ = Uiso·M·(MᵀM)⁻¹·Mᵀ = Uiso·I.
"""

from __future__ import annotations

import math
import re
from typing import Any

import gemmi
import numpy as np

from ..crystallography.adp import cartesian_basis, reciprocal_axis_lengths, ustar_from_ucif
from ..crystallography.symmetry import expand_orbit, get_spacegroup

#: Semi-axes are drawn at ``k(p)·√λ``.  ``k`` is the radius of the sphere of
#: probability ``p`` for a trivariate normal, i.e. ``√χ²₃(p)`` — the ORTEP
#: convention (Johnson, 1965, ORNL-3794).  Offered as a table rather than a free
#: number because these are the levels crystallography quotes, and because the
#: client can then change level without a refetch.
PROBABILITY_LEVELS: tuple[float, ...] = (0.10, 0.25, 0.50, 0.75, 0.90, 0.99)

DEFAULT_PROBABILITY = 0.50

#: A bond is drawn when ``d ≤ BOND_TOLERANCE·(r_i + r_j)`` on gemmi's covalent
#: radii.  1.15 is the usual slack: it keeps ionic contacts (Na–Cl at 2.82 Å
#: against a 2.68 Å radius sum) while staying below the second coordination
#: shell.  Not refinable, not physics — a **drawing threshold**, which is why it
#: rides on the query string and is echoed back in the payload: a large-radius
#: cation makes any fixed value wrong somewhere (LaB6 at 1.15 draws La–B at
#: 3.05 Å and looks like a hairball; at 1.00 it draws the B₆ octahedra alone),
#: and the honest answer to that is a control, not a better constant.
BOND_TOLERANCE = 1.15

#: Segments, not pairs — see :func:`_bonds`.  Reported in ``note`` when it bites.
MAX_BONDS = 4000

#: Below this, two "atoms" are the same atom (a duplicated boundary image, or a
#: disordered pair sharing a site) and no stick is drawn between them.
BOND_MIN = 0.4

#: Ball-and-stick spheres are drawn at this fraction of the covalent radius —
#: small enough that the sticks are visible, large enough to read as atoms.
BALL_FRACTION = 0.32

#: How many drawn atoms (symmetry images and boundary duplicates included) the
#: payload will carry.  A cap rather than a promise: it is reported in ``note``
#: when it bites, because a silently truncated cell reads as a wrong structure.
MAX_ATOMS = 400

#: Fractional tolerance for "this atom is on the cell boundary", which is what
#: earns it a duplicate at the far face — the corner atom that appears eight
#: times in every textbook drawing of a unit cell.
BOUNDARY_TOL = 1e-3

# ----------------------------------------------------------------------
# species → element, colour, radius
# ----------------------------------------------------------------------
_SPECIES = re.compile(r"^([A-Za-z]{1,2})(\d*[+-])?$")

#: The elements the **CPK convention** actually names (Corey & Pauling, 1953,
#: Rev. Sci. Instrum. 24, 621; Koltun, 1965, US Patent 3,170,246): hydrogen
#: white, carbon black, nitrogen blue, oxygen red, sulfur yellow, phosphorus
#: orange, halogens green, noble gases cyan, and iron a dark orange.  The
#: *assignments* are that convention; the hex values are chosen here for
#: contrast against both a light and a dark page — pure white and pure black
#: both vanish into one of them — so nothing is transcribed from another
#: implementation's table (CLAUDE.md, Licensing).
_CPK: dict[str, str] = {
    "H": "#d8d8d8", "C": "#383838", "N": "#3050f8", "O": "#e02020",
    "F": "#48d860", "Cl": "#28c828", "Br": "#a02020", "I": "#8020c0",
    "He": "#40e0e0", "Ne": "#40c8d8", "Ar": "#40b8d0", "Kr": "#3ca8c0",
    "Xe": "#3898b0", "P": "#ff8000", "S": "#e8d040", "B": "#e0a080",
    "Fe": "#c05000", "Ti": "#909090", "Na": "#8040e0", "Ca": "#40c060",
}


def element_symbol(species: str) -> str:
    """The bare element of a scattering species: ``"La3+"`` → ``"La"``.

    Same grammar :func:`~pxrdref.crystallography.scattering.normalize_species`
    parses, and for the same reason — a charge is a scattering detail, while
    radius and colour are properties of the element.  gemmi's own
    ``Element("O2-")`` answers ``X``, so the charge is stripped here first.
    """
    match = _SPECIES.match(species.strip())
    if match is None:
        return "X"
    symbol = match.group(1).capitalize()
    return symbol if gemmi.Element(symbol).atomic_number else "X"


def element_color(element: str) -> str:
    """A stable colour for an element: CPK where the convention names one.

    Everything else is **derived** rather than looked up — hue at the golden
    angle in the atomic number, at a fixed saturation and lightness that reads
    on both themes.  A derived fallback is the same device ``capabilities()``
    uses for its ``features`` flags: it cannot go stale, and a new element is
    never an unrendered atom.
    """
    if element in _CPK:
        return _CPK[element]
    z = gemmi.Element(element).atomic_number
    if not z:
        return "#909090"
    hue = (z * 137.508) % 360.0
    return _hsl_hex(hue, 0.42, 0.55)


def _hsl_hex(hue: float, sat: float, light: float) -> str:
    def channel(n: float) -> int:
        k = (n + hue / 30.0) % 12.0
        a = sat * min(light, 1.0 - light)
        return round(255 * (light - a * max(-1.0, min(k - 3.0, 9.0 - k, 1.0))))

    return "#{:02x}{:02x}{:02x}".format(channel(0), channel(8), channel(4))


def element_radius(element: str) -> float:
    """gemmi's covalent radius (Å) — the bond cutoff's and the ball's scale."""
    return float(gemmi.Element(element).covalent_r)


def is_metal(element: str) -> bool:
    """gemmi's metal flag — the one chemical distinction the bond rule needs."""
    return bool(gemmi.Element(element).is_metal)


def bonds_between_metals(elements) -> bool:
    """Whether metal–metal contacts should be drawn as bonds in this phase.

    A pure radius-sum rule draws the wrong picture at both ends of chemistry,
    and the failure is not subtle: gemmi's covalent radius for lanthanum is
    2.07 Å, so in LaB6 (a = 4.158 Å) *every cell edge* becomes an La–La stick
    and the boron framework disappears into a cage.

    The distinction that fixes it is chemical rather than geometric — in a
    structure that contains a non-metal, a metal–metal contact is a lattice
    distance and not a bond, while in one that does not (an alloy, an
    elemental metal) it is the only bond there is.  So the rule is: bond metals
    to metals **only when the phase has no non-metal in it**.  Stated as a
    predicate over the phase rather than a per-pair exception, because that is
    what makes it answerable — and derived from the composition, so an
    intermetallic never has to be special-cased by hand.
    """
    return all(is_metal(element) for element in elements)


def probability_scale(probability: float) -> float:
    """``k(p) = √χ²₃(p)`` — the ellipsoid's semi-axis scale at probability ``p``.

    50 % is 1.5382 and 90 % is 2.5003, the numbers ORTEP prints.  scipy is a
    core dependency, so this is a lookup rather than a table of magic constants
    that would have to be checked by hand.
    """
    from scipy.stats import chi2

    p = float(probability)
    if not 0.0 < p < 1.0:
        raise ValueError(f"probability must be in (0, 1), not {probability!r}")
    return float(math.sqrt(chi2.ppf(p, 3)))


# ----------------------------------------------------------------------
# the payload
# ----------------------------------------------------------------------
def build(structure, phase: int = 0, *, probability: float = DEFAULT_PROBABILITY,
          bond_tolerance: float = BOND_TOLERANCE,
          max_atoms: int = MAX_ATOMS) -> dict[str, Any]:
    """Drawable geometry for one phase of ``structure``.

    The returned dict is the wire format of ``GET /api/structure3d``; its shape
    is documented field by field in the sections below, and every coordinate in
    it is **Cartesian in Å** unless the name says ``frac``.
    """
    phases = list(structure.phases)
    if not 0 <= phase < len(phases):
        raise IndexError(f"no phase {phase} (this structure has {len(phases)})")
    ph = phases[phase]
    cell = ph.cell.lengths_angles()
    basis = cartesian_basis(*cell)            # lattice vectors as columns, Å
    astar = reciprocal_axis_lengths(*cell)
    sg = get_spacegroup(ph.space_group)

    sites, atoms, notes = _expand(ph, phase, sg, basis, astar, max_atoms)
    positions = np.array([a["pos"] for a in atoms], dtype=np.float64).reshape(-1, 3)
    radii = np.array([sites[a["site"]]["radius"] for a in atoms], dtype=np.float64)
    metal = np.array([sites[a["site"]]["metal"] for a in atoms], dtype=bool)
    alloy = bonds_between_metals(s["element"] for s in sites)
    bonds = _bonds(positions, radii, basis, bond_tolerance,
                   None if alloy else metal)
    if len(bonds) > MAX_BONDS:
        notes.append(f"{len(bonds)} bond segments trimmed to {MAX_BONDS}; lower "
                     "the bond tolerance to see a picture rather than a cage")
        bonds = bonds[:MAX_BONDS]
    partners = _partners(atoms, bonds, basis)
    room = max(max_atoms - len(atoms), 0)
    if len(partners) > room:
        notes.append(f"{len(partners) - room} bonded neighbour(s) outside the cell "
                     "are not drawn; their bonds end in mid-air")
        partners = partners[:room]
    atoms.extend(partners)

    corners = _corners(basis)
    return {
        "phase": phase,
        "phases": [p.name for p in phases],
        "name": ph.name,
        "space_group": sg.xhm(),
        "cell": list(cell),
        "volume": float(abs(np.linalg.det(basis))),
        "lattice": basis.T.tolist(),          # rows a, b, c as Cartesian vectors
        "corners": corners.tolist(),
        # twelve index pairs into ``corners``; the client joins them with the
        # nulls plotly wants, so "12 edges" is a fact of the payload and not of
        # whichever polyline convention the renderer happens to use
        "edges": _EDGES,
        "sites": sites,
        "atoms": atoms,
        "bonds": bonds,
        "probability": float(probability),
        "probability_levels": {f"{p:g}": probability_scale(p)
                               for p in PROBABILITY_LEVELS},
        "scale": probability_scale(probability),
        "ball_fraction": BALL_FRACTION,
        "bond_tolerance": float(bond_tolerance),
        "bond_metals": alloy,
        "note": " · ".join(notes),
    }


#: The twelve edges of a parallelepiped, as index pairs into the eight corners
#: ``_corners`` emits (in binary order over the a, b, c coefficients).
_EDGES: list[list[int]] = [[i, i ^ bit] for bit in (1, 2, 4)
                           for i in range(8) if not i & bit]


def _corners(basis: np.ndarray) -> np.ndarray:
    """The eight cell corners in Cartesian Å, in binary (a, b, c) order."""
    frac = np.array([[(i >> 0) & 1, (i >> 1) & 1, (i >> 2) & 1] for i in range(8)],
                    dtype=np.float64)
    return frac @ basis.T


def _expand(ph, phase: int, sg, basis: np.ndarray, astar: np.ndarray,
            max_atoms: int) -> tuple[list[dict], list[dict], list[str]]:
    """The asymmetric unit → per-site records and every drawn image of each.

    Two kinds of image are drawn and the payload distinguishes them, because
    only one of them counts: a **symmetry** image is a member of the orbit, so
    the number of non-``boundary`` atoms on a site *is* its multiplicity, while
    a **boundary** duplicate is the same atom seen at the opposite face and is
    there so a corner atom appears at all eight corners.  :func:`_partners` adds
    a third kind under the same flag — a bonded neighbour just outside the cell —
    for the same reason: it is an image, not a cell member.
    """
    sites: list[dict] = []
    atoms: list[dict] = []
    notes: list[str] = []
    for j, atom in enumerate(ph.atoms):
        element = element_symbol(atom.species)
        xyz = np.array([atom.x.value, atom.y.value, atom.z.value], dtype=np.float64)
        orbit = expand_orbit(sg, xyz)
        uiso = atom.biso.value / (8.0 * math.pi ** 2)
        ustar = (None if atom.aniso is None
                 else ustar_from_ucif(np.asarray(atom.aniso.values()), astar))
        site = {
            "index": j,
            # the atom's own dot-path, so a click here reaches the row the
            # parameter table already owns rather than a second identity for it
            "path": f"phases.{phase}.atoms.{j}",
            "label": atom.label,
            "species": atom.species,
            "element": element,
            "color": element_color(element),
            "radius": element_radius(element),
            "metal": is_metal(element),
            "occ": float(atom.occ.value),
            "biso": float(atom.biso.value),
            "u_iso": float(uiso),
            "aniso": atom.aniso is not None,
            "multiplicity": len(orbit),
            "special": len(orbit) < len(sg.operations()),
            "npd": False,
        }
        sites.append(site)
        for frac, rot in orbit:
            transform, rms, npd = _ellipsoid(ustar, uiso, rot, basis)
            site["npd"] = site["npd"] or npd
            for shift in _boundary_shifts(frac):
                image = frac + shift
                atoms.append({
                    "site": j,
                    "frac": image.tolist(),
                    "pos": (basis @ image).tolist(),
                    "boundary": bool(shift.any()),
                    "ellipsoid": transform.tolist(),
                    "rms": rms.tolist(),
                    "npd": npd,
                })
    if len(atoms) > max_atoms:
        notes.append(f"{len(atoms)} drawn atoms trimmed to {max_atoms}; "
                     "the cell is larger than this viewer draws")
        atoms = atoms[:max_atoms]
    if any(s["npd"] for s in sites):
        notes.append("a displacement tensor is not positive definite — its "
                     "non-positive axes are drawn at zero, so that ellipsoid is "
                     "flat by construction")
    return sites, atoms, notes


def _partners(atoms: list[dict], bonds: list[dict], basis: np.ndarray) -> list[dict]:
    """The atoms a bond leaves the cell to reach, so no stick ends on nothing.

    Found by looking at the picture rather than at the payload: a bond drawn to
    a translated image is *correct* and reads as broken, because the eye sees a
    stick going into empty space.  So each out-of-cell endpoint gets its atom
    drawn — flagged ``boundary``, since it is an image and not a cell member, so
    the multiplicity count is untouched.

    Exactly **one** level, and that is a stopping rule rather than an omission:
    completing the added atoms' own bonds would complete theirs in turn, which
    is a packing diagram (this WP's explicit non-goal).  What one level buys is
    the property that matters — every atom of the cell shows its full
    coordination.
    """
    known = {tuple(np.round(a["pos"], 6)) for a in atoms}
    inverse = np.linalg.inv(basis)
    out: list[dict] = []
    for bond in bonds:
        key = tuple(np.round(bond["b"], 6))
        if key in known:
            continue
        known.add(key)
        source = atoms[bond["j"]]
        # a lattice translation moves an atom and leaves its tensor alone, so
        # the image carries the source's ellipsoid unchanged; the fractional
        # coordinate is recovered rather than left blank, because it is what
        # says *which* image the hover is over (−0.20 rather than 0.80)
        out.append({**source, "pos": list(bond["b"]), "boundary": True,
                    "frac": (inverse @ np.asarray(bond["b"])).tolist()})
    return out


def _boundary_shifts(frac: np.ndarray) -> list[np.ndarray]:
    """``[0]`` plus the +1 translations along every axis this atom sits on.

    An atom at x ≈ 0 is also at x = 1: the same atom, drawn twice, which is what
    puts a corner site at all eight corners and a face site at both faces.
    """
    axes = [k for k in range(3) if frac[k] < BOUNDARY_TOL]
    shifts = [np.zeros(3)]
    for mask in range(1, 1 << len(axes)):
        shift = np.zeros(3)
        for bit, axis in enumerate(axes):
            if mask >> bit & 1:
                shift[axis] = 1.0
        shifts.append(shift)
    return shifts


def _ellipsoid(ustar: np.ndarray | None, uiso: float, rot: np.ndarray,
               basis: np.ndarray) -> tuple[np.ndarray, np.ndarray, bool]:
    """``(T, rms, npd)`` for one image: ``pos + k·T·v`` over the unit sphere ``v``.

    ``T = V·diag(√λ)`` from the eigen-decomposition of U_cart, so its columns
    are the principal axes at one RMS displacement and the client's only job is
    a matrix-vector product.  The rotation is applied in **fractional** space
    (U\\* → R·U\\*·Rᵀ), which is the representation that transforms that way —
    see ``adp.py``.

    Isotropic sites take the closed form rather than the eigen path: U_cart is
    exactly Uiso·I there (module docstring), so ``T = √Uiso·I`` and no symmetry
    image can rotate a sphere.
    """
    if ustar is None:
        rms = np.full(3, math.sqrt(max(uiso, 0.0)))
        return np.diag(rms), rms, False
    rotated = rot @ ustar @ rot.T
    u_cart = basis @ rotated @ basis.T
    values, vectors = np.linalg.eigh(u_cart)
    npd = bool(values[0] <= 0.0)
    # √(negative) is NaN and one NaN vertex loses the whole mesh; zero is the
    # honest value — "no positive mean-square displacement along this axis" —
    # and it collapses the ellipsoid visibly instead
    rms = np.sqrt(np.clip(values, 0.0, None))
    return vectors * rms, rms, npd


def _bonds(positions: np.ndarray, radii: np.ndarray, basis: np.ndarray,
           tolerance: float = BOND_TOLERANCE,
           metal: np.ndarray | None = None) -> list[dict]:
    """Bond **segments** between drawn atoms, over the 27 nearest translations.

    Segments rather than pairs, and the distinction is the design: a bond that
    leaves the cell is emitted with its far end outside, so an atom shows every
    contact it has instead of only those whose partner happens to be drawn
    inside the box.  The same contact therefore appears twice — once leaving
    each partner — which is what makes both atoms look correctly coordinated.

    ``metal`` suppresses metal–metal sticks (see :func:`bonds_between_metals`);
    ``None`` draws them, which is the alloy case.
    """
    n = len(positions)
    if n == 0:
        return []
    cutoff = float(tolerance) * (radii[:, None] + radii[None, :])
    if metal is not None:
        cutoff = np.where(metal[:, None] & metal[None, :], -1.0, cutoff)
    shifts = np.array([[i - 1, j - 1, k - 1] for i in range(3) for j in range(3)
                       for k in range(3)], dtype=np.float64) @ basis.T
    out: list[dict] = []
    for shift in shifts:
        home = not shift.any()
        delta = (positions[None, :, :] + shift) - positions[:, None, :]
        dist = np.sqrt((delta ** 2).sum(axis=2))
        hit = (dist <= cutoff) & (dist >= BOND_MIN)
        if home:
            hit &= np.triu(np.ones_like(hit, dtype=bool), 1)  # each pair once
        for i, j in zip(*np.nonzero(hit)):
            out.append({"i": int(i), "j": int(j),
                        "a": positions[i].tolist(),
                        "b": (positions[j] + shift).tolist(),
                        "d": float(dist[i, j])})
    return out

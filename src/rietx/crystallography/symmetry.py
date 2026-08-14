"""Space-group symmetry via gemmi: operators, absences, unique hkl generation.

gemmi (MPL-2.0, used as a dependency) owns the symbol → operators mapping, the
systematic-absence test, and centring information.  Reflection multiplicities
are computed here by explicit orbit counting under the **Laue** group (the
point group of the diffraction pattern, i.e. the crystal point group plus
inversion), so ±h are always merged into one orbit.

**Merging ±h is exact with or without anomalous scattering, but for two
different reasons — do not "fix" it when dispersion is on.**  Without f″,
|F(h)|² = |F(−h)|² (Friedel's law) and the two are literally the same number.
With f″ they differ in a non-centrosymmetric group, but a powder cannot
separate them either way: d(h) = d(−h), so the pair lands in one peak and what
the peak measures is the *orbit average*.  ``structure_factor`` returns exactly
that average in closed form (⟨|F|²⟩ = |A|² + |B|², see its module docstring),
which is why one representative per Laue orbit remains the correct — not the
approximate — thing to enumerate here.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import gemmi
import numpy as np

from .lattice import d_spacings, two_theta_deg

#: ceiling on the (2h+1)(2k+1)(2l+1) enumeration grid ``generate_reflections``
#: may allocate — ~30M points is ≈ 1 GB of transient int64, far above any
#: physical powder problem (a 100 Å cell at d_min = 1 Å needs 8.1e6) and far
#: below the PiB-scale grids a collapsed cell implies
MAX_HKL_GRID_POINTS = 30_000_000


def get_spacegroup(symbol: str) -> gemmi.SpaceGroup:
    """Resolve an H-M symbol (or IT number given as a string) via gemmi."""
    sg = gemmi.find_spacegroup_by_name(symbol)
    if sg is None:
        try:
            sg = gemmi.find_spacegroup_by_number(int(symbol))
        except (ValueError, TypeError):
            sg = None
    if sg is None:
        raise ValueError(f"unknown space group symbol: {symbol!r}")
    return sg


#: Largest deviation of a symmetry-fixed cell angle from its exact value that
#: :func:`cell_constraints` accepts, in degrees.  Chosen by consequence, not by
#: float tolerance: at 1e-3° the worst-case d-spacing bias is **8.3 ppm**
#: (measured on a=5, b=6, c=7 Å over h0l/hk l reflections; the coupling is
#: linear, 825 ppm at 0.1°), an order of magnitude under the tightest cell
#: assertion in the acceptance suite — SRM 660c's a = 4.15678 ± 2e-4 Å, i.e.
#: 48 ppm.  And it clears, by a **measured 7e10 ×**, the round-off an indexing
#: candidate arrives with: ``refine_candidate`` solves A..F *inside* the symmetry
#: subspace, so the derived angles come back within 1.4e-14° of exactly 90/120
#: across all five constrained systems.  That matters because
#: ``validate_by_lebail`` builds a ``ParameterTable`` from every candidate — a
#: tolerance anywhere near the conversion noise would make the indexer refuse its
#: own answers.
SYMMETRY_ANGLE_TOL_DEG = 1e-3

#: The exact angle a hexagonal/trigonal γ takes on hexagonal axes.
_GAMMA_HEX = 120.0


@dataclass(frozen=True)
class CellConstraints:
    """Which cell parameters a space-group **setting** leaves free.

    ``ties`` maps a dependent cell parameter to the one it equals (``"b" → "a"``,
    and on rhombohedral axes ``"beta" → "alpha"`` as well); ``fixed_angles`` maps
    an angle to the value its symmetry *demands*, in degrees.  Everything not
    named in either is refinable.

    **The crystal system is not enough** — the setting is, and three of them
    disagree with the system alone (WP-1036):

    * monoclinic has three unique-axis choices, and gemmi knows which
      (:meth:`gemmi.SpaceGroup.monoclinic_unique_axis`).  Assuming ``b`` inverts
      the answer on a ``c``-unique symbol: γ, the one angle the setting leaves
      free, gets held, and β, which symmetry fixes at 90°, is left to refine.
    * an R lattice on **rhombohedral** axes (``sg.ext == 'R'``) needs
      a = b = c and α = β = γ, not the hexagonal-axes ``b ← a`` with c free.
      ``read_small_structure`` picks the setting from the *cell*, so a bare
      ``R -3 c`` over a rhombohedral cell arrives here as ``R -3 c:R`` — no
      non-standard symbol required.
    * the ``:1``/``:2`` extensions on cubic, tetragonal and orthorhombic groups
      are origin choices and do not touch the metric, which is why only ``'R'``
      is tested for.

    **A degrees-of-freedom count cannot check any of this.** Both monoclinic
    subspaces have four free parameters and both trigonal ones have two; the
    wrong table has the right dimension and the wrong subspace, exactly as the
    transposed-rotation trap did one rank up (see
    :func:`~rietx.indexing.qspace.metric_basis`).  The test that does check it
    asserts the *true* metric of each setting lies in the span the constraints
    describe — ``tests/test_wyckoff.py`` runs it over gemmi's whole table.

    The values in ``fixed_angles`` are **new knowledge**: nothing else in this
    package knows a hexagonal γ "should be" 120°.  They live here so that no
    call site can open-code them.
    """

    ties: dict[str, str]
    fixed_angles: dict[str, float]


def cell_constraints(sg: gemmi.SpaceGroup) -> CellConstraints:
    """Cell ties and symmetry-fixed angles for one space-group **setting**.

    Raises ``ValueError`` naming the symbol and the setting if the group is one
    this package cannot serve.  See :class:`CellConstraints` for why the crystal
    system alone is the wrong key.
    """
    system = sg.crystal_system_str()
    right = {"alpha": 90.0, "beta": 90.0, "gamma": 90.0}
    if system == "cubic":
        return CellConstraints({"b": "a", "c": "a"}, right)
    if system == "tetragonal":
        return CellConstraints({"b": "a"}, right)
    if system == "hexagonal":
        return CellConstraints({"b": "a"}, right | {"gamma": _GAMMA_HEX})
    if system == "orthorhombic":
        return CellConstraints({}, right)
    if system == "triclinic":
        return CellConstraints({}, {})
    if system == "trigonal":
        if sg.ext == "R":  # rhombohedral axes: one length, one angle
            return CellConstraints({"b": "a", "c": "a", "beta": "alpha",
                                    "gamma": "alpha"}, {})
        return CellConstraints({"b": "a"}, right | {"gamma": _GAMMA_HEX})
    if system == "monoclinic":
        axis = sg.monoclinic_unique_axis()
        free = {"a": "alpha", "b": "beta", "c": "gamma"}.get(axis)
        if free is None:
            raise ValueError(
                f"space group {sg.xhm()!r}: monoclinic with unique axis "
                f"{axis!r}, which is not one of a, b, c — this package cannot "
                f"decide which angle its symmetry fixes")
        return CellConstraints({}, {k: v for k, v in right.items() if k != free})
    raise ValueError(
        f"space group {sg.xhm()!r}: crystal system {system!r} has no cell-tie "
        f"rule in this package")


def check_cell_angles(sg: gemmi.SpaceGroup,
                      angles: dict[str, float]) -> None:
    """Raise if a symmetry-fixed angle disagrees with the value symmetry demands.

    ``angles`` maps ``"alpha"``/``"beta"``/``"gamma"`` to the stored value in
    degrees.  Tolerance is :data:`SYMMETRY_ANGLE_TOL_DEG`.

    **Refusing, rather than normalising, is the deliberate choice** (WP-1036).
    A fixed angle is *held at its stored value*, so before this check a
    monoclinic β = 93.2° survived under an orthorhombic symbol and every
    d-spacing was computed from it — silently, because nothing in the package
    knew what the angle should have been.  Normalising it instead would move a
    number the user supplied, and the one place this is called from
    (``ParameterTable``) has no diagnostics channel to report a model edit
    through; an invisible edit to a stored cell is worse than a refusal.

    Putting the check on that hot path is safe for a reason worth stating: a
    symmetry-fixed angle is **locked**, so it cannot drift while a fit runs.
    The table is rebuilt at every stage boundary and on every ``set_vary`` /
    ``set_values``, but the answer here is the same at each rebuild — a
    refinement that starts can never fail this mid-flight.
    """
    for name, target in cell_constraints(sg).fixed_angles.items():
        value = angles[name]
        if abs(value - target) > SYMMETRY_ANGLE_TOL_DEG:
            raise ValueError(
                f"space group {sg.xhm()!r} fixes {name} at {target}° by "
                f"symmetry, but the cell stores {value}° — off by "
                f"{value - target:+.6g}°, {SYMMETRY_ANGLE_TOL_DEG}° allowed. "
                f"Correct the cell, or use a space group whose symmetry leaves "
                f"{name} free.")


def rotation_matrices(sg: gemmi.SpaceGroup) -> np.ndarray:
    """Integer rotation parts of all symmetry operations, shape (M, 3, 3).

    gemmi stores rotations scaled by Op.DEN (=24).
    """
    ops = sg.operations()
    mats = []
    for op in ops:
        r = np.array(op.rot, dtype=np.float64) / gemmi.Op.DEN
        mats.append(r)
    return np.array(mats)


def expand_orbit(sg: gemmi.SpaceGroup, xyz: np.ndarray, *, tol: float = 1e-4
                 ) -> list[tuple[np.ndarray, np.ndarray]]:
    """Orbit of one fractional position, **with the rotation that produced each image**.

    Returns ``(position, R)`` pairs — the position wrapped into [0,1) and the
    fractional-space rotation part of the operation that generated it.  The
    rotation is what a caller needs when the site carries something that
    *transforms* rather than merely moves: a displacement ellipsoid is
    U\\* → R·U\\*·Rᵀ (see ``adp.py``), so an image drawn with the parent's tensor
    is drawn wrong in every non-orthogonal setting.  Deduplication is by position
    with tolerance ``tol``, so a special position keeps the first operation that
    reached it — any of the stabiliser's members leaves the site's own tensor
    invariant, which is why "the first" is well defined here rather than
    arbitrary.
    """
    ops = sg.operations()
    seen: list[tuple[np.ndarray, np.ndarray]] = []
    for op in ops:
        r = np.array(op.rot, dtype=np.float64) / gemmi.Op.DEN
        t = np.array(op.tran, dtype=np.float64) / gemmi.Op.DEN
        p = (r @ np.asarray(xyz, dtype=np.float64) + t) % 1.0
        dup = False
        for q, _ in seen:
            diff = np.abs(p - q)
            diff = np.minimum(diff, 1.0 - diff)  # periodic distance
            if np.all(diff < tol):
                dup = True
                break
        if not dup:
            seen.append((p, r))
    return seen


def expand_positions(sg: gemmi.SpaceGroup, xyz: np.ndarray, *, tol: float = 1e-4
                     ) -> list[np.ndarray]:
    """Orbit of one fractional position under the space group.

    Returns the distinct equivalent positions (each wrapped into [0,1)); the
    orbit length is the site multiplicity.  Coincident images (special
    positions) are deduplicated with tolerance ``tol``.
    """
    return [p for p, _ in expand_orbit(sg, xyz, tol=tol)]


@dataclass
class ReflectionSet:
    """Unique reflections in a d-range, frozen for one refinement stage.

    Attributes
    ----------
    hkl : (N, 3) int array — one representative per orbit.
    multiplicity : (N,) int — orbit size under the Laue group (Friedel incl.).
    d : (N,) float — d-spacings at the cell used for generation (refresh with
        :meth:`update_positions` when the cell moves during refinement).
    """

    hkl: np.ndarray
    multiplicity: np.ndarray
    d: np.ndarray
    spacegroup: str = ""
    extra: dict = field(default_factory=dict)

    def __len__(self) -> int:
        return len(self.hkl)

    def two_theta(self, cell: tuple[float, float, float, float, float, float],
                  wavelength: float) -> np.ndarray:
        d = d_spacings(self.hkl, *cell)
        return two_theta_deg(d, wavelength)


def reflection_orbits(sg_symbol: str, hkl_reps: np.ndarray) -> list[np.ndarray]:
    """Distinct symmetry+Friedel equivalents of each representative reflection.

    Returns one ``(m_k, 3)`` integer array per row of ``hkl_reps``, listing the
    Laue-group orbit (Friedel mates included) — the same set ``generate_reflections``
    counts to get the multiplicity, so ``len(orbit) == multiplicity``.  The
    reciprocal-space action is the **transposed** rotation (see the comment in
    ``generate_reflections``); this is the frozen discrete object the
    March-Dollase correction averages over, computed once per stage.
    """
    rots = rotation_matrices(get_spacegroup(sg_symbol))
    rot_int = np.rint(np.transpose(rots, (0, 2, 1))).astype(np.int64)
    orbits: list[np.ndarray] = []
    for h in np.asarray(hkl_reps, dtype=np.int64):
        images = np.einsum("mij,j->mi", rot_int, h)
        images = np.vstack([images, -images])  # Friedel mates
        uniq = sorted({tuple(map(int, im)) for im in images})
        orbits.append(np.array(uniq, dtype=np.int64))
    return orbits


def generate_reflections(sg_symbol: str,
                         cell: tuple[float, float, float, float, float, float],
                         wavelength: float,
                         two_theta_max: float,
                         two_theta_min: float = 0.0) -> ReflectionSet:
    """Enumerate the symmetry-unique, absence-allowed reflections in range.

    Strategy: enumerate all integer hkl in the sphere d ≥ d_min =
    λ/(2 sin(θ_max)), drop systematic absences (gemmi), group the survivors
    into Laue-group orbits (including Friedel mates), and keep one
    representative per orbit with its orbit size as the multiplicity.
    """
    sg = get_spacegroup(sg_symbol)
    ops = sg.operations()

    d_min = wavelength / (2.0 * np.sin(np.radians(two_theta_max / 2.0)))
    a, b, c = cell[0], cell[1], cell[2]
    hmax = int(np.floor(a / d_min)) + 1
    kmax = int(np.floor(b / d_min)) + 1
    lmax = int(np.floor(c / d_min)) + 1

    # refuse before allocating: a collapsed or mis-scaled cell (or a
    # wavelength typed in the wrong unit) implies index ranges whose grid
    # would be petabytes — measured 63747 × 63747 × 81527 = 2.35 PiB on a
    # real external CIF (WP-1028 §(b)), which killed the process instead of
    # naming the cause
    n_grid = (2 * hmax + 1) * (2 * kmax + 1) * (2 * lmax + 1)
    if n_grid > MAX_HKL_GRID_POINTS:
        raise ValueError(
            f"refusing to enumerate reflections for cell a={a:g}, b={b:g}, "
            f"c={c:g} Å at d_min={d_min:.4g} Å (λ={wavelength:g} Å, "
            f"2θ_max={two_theta_max:g}°): index ranges ±{hmax}, ±{kmax}, "
            f"±{lmax} span {n_grid:.2e} grid points "
            f"(limit {MAX_HKL_GRID_POINTS:.0e}). A cell this large relative "
            f"to d_min usually means a collapsed or mis-scaled cell, or a "
            f"wavelength/2θ range implying an unphysical resolution.")

    rng_h = np.arange(-hmax, hmax + 1)
    rng_k = np.arange(-kmax, kmax + 1)
    rng_l = np.arange(-lmax, lmax + 1)
    H, K, L = np.meshgrid(rng_h, rng_k, rng_l, indexing="ij")
    hkl = np.column_stack([H.ravel(), K.ravel(), L.ravel()]).astype(np.int64)
    hkl = hkl[~np.all(hkl == 0, axis=1)]

    d = d_spacings(hkl, *cell)
    keep = d >= d_min * 0.999
    if two_theta_min > 0.0:
        d_max = wavelength / (2.0 * np.sin(np.radians(max(two_theta_min, 1e-3) / 2.0)))
        keep &= d <= d_max * 1.001
    hkl, d = hkl[keep], d[keep]

    # systematic absences via gemmi GroupOps (vectorised where available)
    try:
        absent = np.asarray(ops.systematic_absences(hkl), dtype=bool)
    except (AttributeError, TypeError):
        absent = np.array([ops.is_systematically_absent(list(map(int, h))) for h in hkl])
    hkl, d = hkl[~absent], d[~absent]

    # Laue-group orbits.  A real-space operation x' = Rx + t acts on Miller
    # indices (column form) as h' = Rᵀ h; the orbit therefore uses the
    # transposed rotations.  ({Rᵀ} ≠ {R} as a set outside cubic/orthogonal
    # settings — e.g. trigonal threefold axes — so the transpose matters.)
    # Friedel mates ±h are merged.  Exact with or without anomalous
    # scattering — the powder measures the ±h average and structure_factor
    # returns it in closed form; see the module docstring.
    rots = rotation_matrices(sg)
    rot_int = np.rint(np.transpose(rots, (0, 2, 1))).astype(np.int64)
    canon: dict[tuple[int, int, int], int] = {}
    order: list[tuple[int, int, int]] = []
    counts: dict[tuple[int, int, int], set[tuple[int, int, int]]] = {}
    for h in hkl:
        images = np.einsum("mij,j->mi", rot_int, h)
        images = np.vstack([images, -images])  # Friedel
        keys = [tuple(map(int, im)) for im in images]
        rep = max(keys)  # canonical representative: lexicographically largest
        if rep not in canon:
            canon[rep] = len(order)
            order.append(rep)
            counts[rep] = set()
        counts[rep].update(keys)

    reps = np.array(order, dtype=np.int64)
    mult = np.array([len(counts[tuple(r)]) for r in reps], dtype=np.int64)
    d_reps = d_spacings(reps, *cell)
    sort = np.argsort(-d_reps)  # ascending 2θ = descending d
    return ReflectionSet(hkl=reps[sort], multiplicity=mult[sort], d=d_reps[sort],
                         spacegroup=sg.xhm())

"""The magnetic structure factor of a powder reflection, and its Laue-orbit average.

For a reflection at Q (FullProf manual eqs 3.47-3.50; Halpern & Johnson, 1939,
*Phys. Rev.* **55**, 898, for the interaction vector):

    F_m(Q) = p · Σ_j occ_j · f_j(s) · T_j · Σ_s ε_s·det(R_s)·R_s·m_j
                                            · exp(2πi Q·(R_s x_j + t_s))
    I_mag ∝ ⟨ |F_m|² − |Q̂·F_m|² ⟩          p = γr₀/2 = 0.2695×10⁻¹² cm / μ_B

s runs over the magnetic operators, ε_s = ±1 is the operator's time-reversal
sign, and det(R_s)·R_s is the action on an *axial* vector.  Only the component
of F_m perpendicular to Q scatters, which is the ``− |Q̂·F_m|²``.

**Three things this expression is easy to get wrong, and what stops each.**

*The axial action.*  hkl transforms by Rᵀ, a tensor by R·U·Rᵀ, and a moment by
det(R)·R with ε on top.  The transposed set is a group too, so a dimension
count passes with the wrong action in every crystal system; the guard is a
*span* test on a known moment, and it lives one module over in
:func:`~rietx.crystallography.magnetic.operators.in_span`.  Nothing here builds
a second axial action: the per-operation matrices are M-5's
``MagneticOperator.moment_matrix()``, resolved onto the **nuclear** operation
subset so the magnetic orbit and the nuclear one are literally the same
positions.

*The orbit average.*  |F_⊥|² is **not** constant over the nuclear Laue orbit of
Q, because the moment direction breaks the Laue symmetry.  "One representative
times the multiplicity" — which is right for |F_N|² — is wrong here, and it is
wrong in a way that only shows on a non-collinear or low-symmetry structure, so
it survives a cubic test.  This module therefore takes the average over the
whole orbit (Friedel mates included), the same shape ``structure_factors_
squared`` takes for the ±h average under dispersion, and the same frozen
``orbit_layout`` the March-Dollase correction already averages over.  After
that average a cubic collinear structure's intensity is independent of the
moment direction (Shirane, 1959, *Acta Cryst.* **12**, 282) — which is a
*result* here, measured to fp64 in the tests, not an assumption.

*The units.*  p = 2.695 fm per μ_B and a Sears b in fm, so p·m and b are the
same unit and |F_m|² adds to |F_N|² under **one** scale.  A separate magnetic
scale is the easiest route to a plausible fit and a wrong moment, and it is not
offered.

**What is frozen per stage** (:class:`MagneticSites`): the operation subset and
its ε·det(R)·R matrices, the form-factor coefficients, g, and the moment frame.
What moves with θ: the coordinates, the occupancies, the Debye-Waller factors,
the cell (hence the crystal-axis→Cartesian matrix and Q̂), and the moment DOFs.
That is the same split ``PhaseSites.f_anom`` takes one module over.

References
----------
* Halpern, O. & Johnson, M. H. (1939). *Phys. Rev.* **55**, 898 — the magnetic
  interaction vector.
* Shirane, G. (1959). *Acta Cryst.* **12**, 282 — what a powder average
  determines of a moment direction.
* Rodríguez-Carvajal, J. (1993). *Physica B* **192**, 55 — FullProf; the
  manual's eqs 3.47-3.54 are the form above.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import gemmi
import numpy as np

from ..adp import cartesian_basis
from ..symmetry import SITE_TOL, ReflectionSet, as_group, generate_reflections
from .form_factor import approximation_name, coefficients, resolve_g
from .moments import moment_frame, moment_from_dofs

#: p = γ·r₀/2, the magnetic scattering length of one Bohr magneton, in **fm**
#: — the unit ``crystallography.neutron``'s Sears table gives b in, which is
#: what lets |F_m|² and |F_N|² share one scale (issue #257 A6 iv).  0.2695 ×
#: 10⁻¹² cm is 2.695 fm; the two spellings are the same number and the fm one
#: is the one this package computes in.
P_MAGNETIC_FM = 2.695

#: The source kinds whose histograms carry the magnetic term, and the ones that
#: do not.  One table, two readers: ``model.forward.magnetic_wanted`` dispatches
#: on it (and refuses a kind in neither set by name), and
#: ``capabilities.RadiationCapability.magnetic_scattering`` is derived from it,
#: so the arm a client reads cannot disagree with what the forward model does.
#: A neutron couples to the magnetization density through its own moment; an
#: X-ray of a laboratory or ordinary synchrotron experiment does not, to many
#: orders of magnitude.
MAGNETIC_SOURCE_KINDS = frozenset({"neutron_cw"})
NON_MAGNETIC_SOURCE_KINDS = frozenset({"xray_cw"})


@dataclass
class MagneticSites:
    """Frozen magnetic data for one phase, beside :class:`PhaseSites`.

    ``mom_mat[j]`` is ``(m_j, 3, 3)``: for each operation of atom ``j``'s
    frozen nuclear subset, the axial action ε·det(R)·R that carries the
    asymmetric-unit moment onto that image.  Resolved by matching the nuclear
    operation's (R, t mod 1) against the magnetic group, so image *k* of the
    magnetic model is image *k* of the nuclear one — not a parallel orbit that
    could drift out of correspondence.

    ``carries[j]`` says whether atom ``j`` has a moment at all; a phase may mix
    magnetic and non-magnetic sites, and the non-magnetic ones contribute
    nothing to F_m while still contributing to F_N.
    """

    mom_mat: list[np.ndarray | None]
    #: the *nuclear* operation subsets, ``PhaseSites.ops`` — carried by
    #: reference rather than copied, so image k here is image k there by
    #: construction and no correspondence has to be maintained
    ops: list[tuple[np.ndarray, np.ndarray]]
    frames: list[np.ndarray | None]
    ions: list[str | None]
    g_factors: list[float | None]
    #: per-atom name of the approximation in force, for the report
    approximations: list[str | None]
    #: (n_asym,) bool, ``carries[j] == (mom_mat[j] is not None)``
    carries: list[bool] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.carries:
            self.carries = [m is not None for m in self.mom_mat]

    @property
    def n_asym(self) -> int:
        return len(self.mom_mat)

    def n_dofs(self, j: int) -> int:
        frame = self.frames[j]
        return 0 if frame is None else len(frame)

    def named_approximations(self) -> dict[str, str]:
        """``{ion: approximation}`` for every magnetic species of the phase."""
        return {ion: name for ion, name in zip(self.ions, self.approximations,
                                               strict=True)
                if ion is not None and name is not None}


def compile_magnetic_sites(phase, ops) -> MagneticSites | None:
    """Freeze the per-atom magnetic data for one stage, or ``None`` if there is none.

    ``ops`` is ``PhaseSites.ops`` — the *nuclear* operation subsets, already
    chosen so each site's orbit images appear exactly once.  Every one of those
    images must be reachable by an operation of the magnetic group, and the
    axial matrix stored for it is that operation's ε·det(R)·R (M-5's
    ``MagneticOperator.moment_matrix``, never a second implementation).

    **The match is on the image, not on the operation**, and that is what lets
    a magnetic space group with *fewer* rotations than the nuclear one be
    stated at all — the case every cubic collinear antiferromagnet is.  There
    the magnetic order picks out one axis, its magnetic group is a tetragonal
    or rhombohedral subgroup of the cubic parent, and the crystal breaks into
    domains; each nuclear image still gets one moment, because the magnetic
    group's orbit of the site still covers the nuclear orbit.  The domain
    average is then the Laue-orbit average this module already takes —
    measured by the isotropy rung (M-7 arm F): the domain sum over a complete
    shell is a constant multiple of the single-domain sum, to 1e-9 relative.

    Where the magnetic orbit is genuinely *smaller* than the nuclear one, some
    nuclear atoms have no moment the stated group determines, and that is
    refused by name: the structure has to be stated in the magnetic space
    group's own asymmetric unit, which is what a magCIF gives.
    """
    if phase.magnetic_symmetry is None:
        return None
    if not any(a.moment is not None for a in phase.atoms):
        return None
    group = phase.magnetic_symmetry.group()
    cell = phase.cell.lengths_angles()
    mom_mat: list[np.ndarray | None] = []
    frames: list[np.ndarray | None] = []
    ions: list[str | None] = []
    gs: list[float | None] = []
    names: list[str | None] = []
    for j, atom in enumerate(phase.atoms):
        if atom.moment is None:
            mom_mat.append(None)
            frames.append(None)
            ions.append(None)
            gs.append(None)
            names.append(None)
            continue
        xyz = np.array([atom.x.value, atom.y.value, atom.z.value])
        rot, tran = ops[j]
        mom_mat.append(_axial_matrices(group, xyz, rot, tran,
                                       phase.name, atom.label))
        frames.append(moment_frame(group.allowed_moment_basis(xyz), cell))
        ions.append(atom.moment.ion)
        gs.append(resolve_g(atom.moment.ion, atom.moment.g))
        names.append(approximation_name(atom.moment.ion, atom.moment.g))
    return MagneticSites(mom_mat=mom_mat, ops=list(ops), frames=frames,
                         ions=ions, g_factors=gs, approximations=names)


def _axial_matrices(group, xyz, rot, tran, phase_name, label) -> np.ndarray:
    """``(m, 3, 3)`` ε·det(R)·R, one per nuclear image of the site.

    Several magnetic operations may reach one image — the site's magnetic
    stabiliser — and using any one of them is correct for a *general*
    position: they all carry the moment to the same place, because that is
    exactly what makes the moment lie in the site's allowed subspace, which
    the schema has already checked.  On a **special** position this is not
    true of every matching operation individually — a stabiliser element
    whose axial matrix disagrees with the identity there is exactly what
    forces a moment component to zero (:func:`~.operators.
    allowed_moment_basis`) — but it is still true of the group's own
    identity operation, which always matches an atom's own (k=0, itself)
    image and is what this function must pick for that image. So "any one
    match" is really "the *first* match", by convention, not "any of them
    interchangeably" — see the note below on why that is safe.

    **Order (small-fixes-20260917, item 1).** "The first match" used to mean
    "whichever operation ``group.all_operations()`` happens to iterate to
    first" — a property of that tuple's *order*. Two callers that built the
    same group from the same operation *set* enumerated in a different
    order (``_candidate_group``'s seed dict, or ``_close_operations``'s
    closure-discovery order, both in ``isotropy.py``) used to get back a
    ``MagneticGroup`` whose ``all_operations()`` iterated in a different
    order, and Q23 measured this reach exactly this function: reordering
    could pick a different first match — and so a different sign — for an
    image with more than one stabiliser (measured on
    ``test_epsilon_bookkeeping.py::test_moment_path_is_clean_by_design``
    with an unordered ``set()`` in ``_close_operations``). This is now moot:
    ``operators.MagneticGroup.from_operations`` sorts canonically by
    ``(rotation, translation, time_reversal)`` before choosing coset
    representatives, so ``all_operations()`` is bit-identical for any input
    order of the same set, and "the first match" is now a property of the
    *image*, never of the caller's enumeration order (see
    ``tests/test_operator_order_independence.py``, which checks this
    end to end through ``compile_magnetic_sites``).
    """
    ops_all = group.all_operations()
    images = [op.act_on_site(xyz) for op in ops_all]
    mats = np.empty((len(rot), 3, 3), dtype=np.float64)
    for k, (r, t) in enumerate(zip(rot, tran, strict=True)):
        want = np.asarray(r, dtype=np.float64) @ xyz + np.asarray(t, dtype=np.float64)
        for op, image in zip(ops_all, images, strict=True):
            delta = np.abs(image - want)
            if np.all(np.minimum(delta, 1.0 - delta) <= SITE_TOL):
                mats[k] = op.moment_matrix()
                break
        else:
            raise ValueError(
                f"phase {phase_name!r} atom {label!r}: the nuclear space group "
                f"puts an image of this site at "
                f"{np.round(want % 1.0, 4).tolist()}, and no operation of the "
                f"declared magnetic symmetry sends the site there — so the "
                f"stated group does not determine a moment for that atom. "
                f"State the structure in the magnetic space group's own "
                f"asymmetric unit (and, for a k != 0 structure, in its "
                f"magnetic supercell), which is what a magCIF from MAGNDATA, "
                f"ISODISTORT or k-SUBGROUPSMAG already gives you")
    return mats


# ---------------------------------------------------------------------------
# the reflections a magnetic space group needs and a nuclear one does not
# ---------------------------------------------------------------------------
def magnetic_reflections(sg_symbol,
                         cell: tuple[float, float, float, float, float, float],
                         wavelength: float, two_theta_max: float,
                         two_theta_min: float = 0.0, *,
                         magnetic_group=None) -> ReflectionSet:
    """The reciprocal-lattice points the **nuclear** structure factor forbids.

    A k = 0 magnetic structure puts intensity exactly where the parent's glide
    and screw operations kill the nuclear structure factor, because its
    magnetic space group generally does not carry those operations — WP-1326
    measured it on Cr₂WO₆, whose two strongest 4 K residual peaks are the
    systematically absent (0 0 1) and (1 0 2).  Those reflections are **not in
    the nuclear reflection list at all**, so a magnetic phase needs them added
    or its strongest peaks are simply not computed.

    **Centring conditions are applied, except the ones the magnetic group
    reverses.**  A parent centring translation t forbids every h with
    h·t ∉ ℤ, and an ordinary magnetic group carries t unprimed, so its
    magnetic structure factor obeys the same condition and those rows would
    only be zero-intensity rows reaching every consumer :func:`merge_magnetic`
    names.  A black-white lattice (BNS type IV) carries t *primed* — an
    anti-centring, the moment reversed on translation — and there the
    magnetic intensity sits exactly at h·t ∈ ℤ + ½, on the rows the nuclear
    centring forbids.  So each parent centring is applied unless
    ``magnetic_group`` holds it with time reversal −1.  ``magnetic_group``
    ``None`` applies every centring, which is the ordinary case.  (gemmi's
    ``systematic_absences`` is where the centring test lives, and skipping it
    to keep the glide and screw rows skipped the centring with them; this
    function applies it itself.)

    Glide and screw absences are not applied.  The Laue multiplicity is the
    parent group's, because that is what makes two reflections coincide in a
    powder pattern; the fact that the *magnetic* symmetry is lower is exactly
    why the intensity is an orbit average rather than one representative's
    value.

    Magnetic absences are not applied either, and are not needed: |F_m|² is
    identically zero where the magnetic group forbids the reflection, so the
    extinction comes out of the arithmetic instead of a second table.
    """
    everything = generate_reflections(sg_symbol, cell, wavelength,
                                      two_theta_max=two_theta_max,
                                      two_theta_min=two_theta_min,
                                      apply_absences=False)
    allowed = generate_reflections(sg_symbol, cell, wavelength,
                                   two_theta_max=two_theta_max,
                                   two_theta_min=two_theta_min)
    keep = {tuple(map(int, h)) for h in allowed.hkl}
    mask = np.array([tuple(map(int, h)) not in keep for h in everything.hkl],
                    dtype=bool)
    centrings = applied_centrings(as_group(sg_symbol), magnetic_group)
    if len(centrings) and len(everything):
        # h·t for every centring t, in 1/DEN units: integral iff divisible
        phase = everything.hkl.astype(np.int64) @ centrings.T
        mask &= np.all(phase % gemmi.Op.DEN == 0, axis=1)
    return ReflectionSet(hkl=everything.hkl[mask],
                         multiplicity=everything.multiplicity[mask],
                         d=everything.d[mask],
                         spacegroup=everything.spacegroup)


def applied_centrings(group, magnetic_group=None) -> np.ndarray:
    """``(n, 3)`` int — the parent's non-trivial centrings a magnetic row must obey.

    In gemmi's 1/``Op.DEN`` units.  Every centring translation of ``group``
    except the identity and except any the magnetic group carries as an
    **anti**-centring (time reversal −1): under that one the magnetic
    structure factor changes sign on translation, so the condition it imposes
    is h·t ∈ ℤ + ½ rather than h·t ∈ ℤ, and the rows the nuclear centring
    forbids are exactly the magnetic ones — the black-white lattices of the
    type-IV groups (Litvin, 2013, *Magnetic Group Tables*, IUCr, § 1.3 on the
    BNS lattice types).
    """
    den = gemmi.Op.DEN
    anti = set()
    if magnetic_group is not None:
        for op in magnetic_group.centerings:
            if op.time_reversal == -1:
                anti.add(tuple(int(round(float(c) * den)) % den
                               for c in op.translation))
    kept = [tuple(int(c) % den for c in t)
            for t in group.operations().cen_ops]
    kept = [t for t in kept if any(t) and t not in anti]
    return np.array(kept, dtype=np.int64).reshape(-1, 3)


def merge_magnetic(nuclear: ReflectionSet, extra: ReflectionSet
                   ) -> tuple[ReflectionSet, np.ndarray]:
    """One reflection list carrying both, and the (N,) 1/0 nuclear mask.

    The same merge WP-1326 makes for satellites and for the same reason: every
    consumer downstream — the frozen windows, the FCJ node counts, the Le Bail
    partition, the Pawley block, the tick list, the observation count — is
    written over "the phase's reflections", and a magnetically-allowed lattice
    point is one of those.  What distinguishes them is the mask, which is
    **exact** rather than a tolerance: on those rows the nuclear structure
    factor is identically zero by the glide or screw condition, so masking it
    is the arithmetic the symmetry already implies and not an approximation.
    """
    if len(extra) == 0:
        return nuclear, np.ones(len(nuclear), dtype=np.float64)
    hkl = np.concatenate([nuclear.hkl.astype(np.int64), extra.hkl.astype(np.int64)])
    mult = np.concatenate([nuclear.multiplicity, extra.multiplicity])
    d = np.concatenate([nuclear.d, extra.d])
    nuc = np.concatenate([np.ones(len(nuclear)), np.zeros(len(extra))])
    sort = np.argsort(-d, kind="stable")
    merged = ReflectionSet(hkl=hkl[sort], multiplicity=mult[sort], d=d[sort],
                           spacegroup=nuclear.spacegroup,
                           extra=dict(nuclear.extra))
    return merged, nuc[sort].astype(np.float64)


# ---------------------------------------------------------------------------
# the structure factor
# ---------------------------------------------------------------------------
def reciprocal_cartesian_basis(cell) -> np.ndarray:
    """M⁻ᵀ — the matrix taking integer hkl to a Cartesian reciprocal vector.

    The same Cartesian frame ``moment_to_cartesian`` puts a moment in
    (``adp.cartesian_basis``'s Cholesky convention), because the perpendicular
    projection below takes an angle between the two and an angle needs one
    frame.  Only the *direction* of Q is used, so the 2π convention does not
    enter.
    """
    return np.linalg.inv(np.asarray(cartesian_basis(*cell), dtype=np.float64)).T


def magnetic_f2(members, seg, counts, stol, msites: MagneticSites, cell,
                xyz, occ, biso, dofs: list[np.ndarray]):
    """``(N,)`` p²·⟨|F_⊥|²⟩ in fm², the orbit average over each reflection's Laue orbit.

    ``members`` (M_total, 3), ``seg`` (M_total,) and ``counts`` (N,) are the
    frozen orbit layout (``model.preferred_orientation.orbit_layout``) — every
    reflection's symmetry equivalents, Friedel mates included, stacked and
    segmented.  ``stol`` is (N,) s = sinθ/λ = 1/2d, the same argument the
    nuclear structure factor evaluates its form factors at.  ``dofs[j]`` is atom
    ``j``'s moment DOF vector, or an empty array where it carries no moment.

    Adds to ⟨|F_N|²⟩ directly: both are in fm², so the phase's one scale
    multiplies both.

    **Host numpy, deliberately.**  Two pieces of this are not expressible on a
    traced backend as the package's ``xp`` protocol stands — the Cholesky
    factorisation behind the Cartesian frame, and the crystal-axis→Cartesian
    solve — and rather than approximate either by freezing it against a cell
    that is still refining, the traced twin **declines by name**
    (``backend.traced.make_traced_residual``) and jax/torch fall back to the
    host path for a magnetic phase.  The numpy answer is exact and the
    Jacobian column for a moment DOF is the peak chain's, which re-runs the
    forward model at a perturbed θ and needs no tracing at all.
    """
    m_hkl = np.asarray(members, dtype=np.float64)
    seg_i = np.asarray(seg, dtype=np.int64)
    n = len(counts)
    stol_mem = np.asarray(stol, dtype=np.float64)[seg_i]              # (M_total,)

    cart = _crystalaxis_to_cartesian(cell)                      # (3, 3)
    total = np.zeros((len(seg_i), 3), dtype=np.complex128)
    for j in range(msites.n_asym):
        if not msites.carries[j]:
            continue
        m_crystal = moment_from_dofs(msites.frames[j], dofs[j])          # (3,)
        images = np.asarray(msites.mom_mat[j]) @ m_crystal               # (m, 3)
        m_cart = images @ cart.T                                         # (m, 3)
        rot, tran = msites.ops[j]
        positions = np.asarray(rot) @ np.asarray(xyz[j], dtype=np.float64) \
            + np.asarray(tran, dtype=np.float64)                         # (m, 3)
        phase = np.exp(2.0j * np.pi * (positions @ m_hkl.T))             # (m, M)
        amp = (float(occ[j]) * _form_factor(msites, j, stol_mem)
               * np.exp(-float(biso[j]) * stol_mem * stol_mem))                # (M,)
        contrib = np.einsum("km,kc->mc", phase, m_cart.astype(np.complex128))
        total = total + amp[:, None] * contrib

    q = m_hkl @ reciprocal_cartesian_basis(cell).T                       # (M, 3)
    qhat = q / np.sqrt((q * q).sum(axis=1))[:, None]
    # only the component of F_m perpendicular to Q scatters (Halpern & Johnson
    # 1939): |F_⊥|² = |F|² − |Q̂·F|², and F is complex, so the subtracted term
    # is the squared modulus of a complex projection and not (Q̂·Re F)²
    parallel = (qhat.astype(np.complex128) * total).sum(axis=1)          # (M,)
    f2 = (np.real(total * np.conj(total)).sum(axis=1)
          - np.real(parallel * np.conj(parallel)))
    summed = np.zeros(n, dtype=np.float64)
    np.add.at(summed, seg_i, f2)
    return (P_MAGNETIC_FM ** 2) * summed / np.asarray(counts, dtype=np.float64)


def _form_factor(msites: MagneticSites, j: int, stol):
    """f_j(s) for the atom's ion and g, evaluated on the member-shaped ``stol``."""
    ion = msites.ions[j]
    g = msites.g_factors[j]
    c0, c2 = coefficients(ion)
    stol2 = stol * stol
    f = _three_gaussian(c0, stol2, stol2_factor=False)
    weight = 2.0 / g - 1.0
    if weight == 0.0:
        return f
    if c2 is None:  # pragma: no cover - the schema refuses this combination
        raise KeyError(f"no ⟨j2⟩ for {ion!r}")
    return f + weight * _three_gaussian(c2, stol2, stol2_factor=True)


def _three_gaussian(coef, stol2, *, stol2_factor: bool):
    a0, a1, b0, b1, c0, c1, d = coef
    out = (a0 * np.exp(-a1 * stol2) + b0 * np.exp(-b1 * stol2)
           + c0 * np.exp(-c1 * stol2) + d)
    return stol2 * out if stol2_factor else out


def _crystalaxis_to_cartesian(cell) -> np.ndarray:
    """M·diag(1/a, 1/b, 1/c) — one authority with ``operators.moment_to_cartesian``."""
    from .operators import _crystalaxis_to_cartesian_matrix

    return _crystalaxis_to_cartesian_matrix(cell)


def magnetic_orbit(group, xyz, moment, *, tol: float = SITE_TOL):
    """The site's magnetic orbit — positions and the moment carried on each.

    A thin re-export of M-5's ``MagneticGroup.site_orbit`` so that a caller who
    wants the orbit for a *report* does not have to know which module owns the
    axial action.  Nothing in the forward model uses it: there the orbit comes
    from the nuclear operation subset, so that the magnetic and the nuclear
    images are the same array of positions.
    """
    return group.site_orbit(xyz, moment, tol=tol)

"""How a moment enters θ: a modulus and the angles the site symmetry leaves free.

A moment is stored as crystal-axis components (``Atom.moment``) and refined
through ``phases.i.atoms.j.moment.dof<k>``.  The DOFs are **not** the components
and not their coefficients on the allowed basis either, and the reason is the
one thing a powder cannot do.

**Why modulus and angles.**  After the Laue-orbit average a powder measures
|m| for a cubic collinear structure and nothing at all about its direction
(Shirane, G., 1959, *Acta Cryst.* **12**, 282); for a uniaxial structure it
measures |m| and the angle to the unique axis, and nothing about the azimuth.
Those are *flat directions of θ*, and the package already has one rule for a
flat direction: an equilibrated normal matrix, a gradient-free column named by
``ParameterTable.unmeasured_rows``, and an esd that is **absent** rather than
zero.  For that rule to fire, the undeterminable quantity has to *be a column*.
Parameterising by components — or by coefficients on the allowed basis — puts
the flat direction along a rotation that no single column owns, so every
component comes back unmeasured and the magnitude, which the data *does*
determine, comes back with no esd at all.  Modulus-and-angles splits them:
the modulus is a column with a gradient and an esd, the angles are columns
without one exactly when the powder cannot see them.

**The frame.**  The allowed subspace is M-5's
:func:`~rietx.crystallography.magnetic.operators.allowed_moment_basis` — an
integer basis of crystal-axis directions, ∩ ker(ε·det(R)·R − I) over the site's
magnetic stabiliser.  It is *not* orthonormal, and the crystal-axis basis is
oblique whenever the cell is, so the frame here is Gram-Schmidt **in the
magCIF unit-vector metric** (ones on the diagonal, cos of the cell angles off
it).  That is what makes the modulus equal |m| in the sense the CIF defines it:
on hexagonal axes the moment (1, 1, 0) is 1 μ_B, not √2.

**The frame is frozen per stage.**  It depends on the cell through that metric,
and the cell refines; recomputing it inside the residual would make the DOF-to-
component map a function of θ.  So it is built once from the stage's declared
cell — the same freeze the symmetry-operation subsets take — and the parameter
table and the forward model call this module with the *same* cell so there is
exactly one frame per site per stage.  A monoclinic β that moves during a stage
therefore shifts the frame at the next compile, which is where the components
written back at the end of a stage are re-projected.

**Dimension by dimension.**

===  ===================================  ==========================
n    DOFs                                 what the site allows
===  ===================================  ==========================
0    none                                 no moment at all
1    (μ,)                                 one direction, signed
2    (μ, φ)                               a plane
3    (μ, θ, φ)                            any direction
===  ===================================  ==========================

μ is signed for n = 1 — the sign is the only way to state that two independent
sites order antiparallel along the same axis, and there is no angle to carry it
— and unsigned by construction for n ≥ 2, where the antipode is an angle away.
Nothing bounds it either way; ``abs(μ)`` is the magnitude, and the floor that
decides whether the block is supported is on ``abs(μ)``
(:data:`~rietx.schemas.structure.MOMENT_FLOOR_MU_B`).

References
----------
* Shirane, G. (1959). *Acta Cryst.* **12**, 282 — what a powder average
  determines of a moment direction.
* COMCIFS ``magnetic_dic``, ``_atom_site_moment.crystalaxis_*`` — the unit-
  vector basis the metric below belongs to.
"""

from __future__ import annotations

import numpy as np

from ..lattice import direct_metric_tensor

#: Parameter names of the moment DOFs, by subspace dimension.  Data rather
#: than a formula because the *report* reads it: "the angle a powder cannot
#: determine" has to have a name a person recognises.
DOF_NAMES: dict[int, tuple[str, ...]] = {
    0: (),
    1: ("modulus",),
    2: ("modulus", "azimuth"),
    3: ("modulus", "polar", "azimuth"),
}

#: Units of those DOFs, in the same order.
DOF_UNITS: dict[int, tuple[str, ...]] = {
    0: (),
    1: ("mu_B",),
    2: ("mu_B", "rad"),
    3: ("mu_B", "rad", "rad"),
}


def unit_metric(cell) -> np.ndarray:
    """G of the magCIF ``crystalaxis`` basis: ones on the diagonal, cosines off.

    The direct metric tensor with each row and column divided by its axis
    length, which is what "a right-handed basis of unit vectors parallel to the
    unit-cell basis vectors" means as a metric.  |m|² = mᵀ·G·m.
    """
    a, b, c = float(cell[0]), float(cell[1]), float(cell[2])
    return direct_metric_tensor(*cell) / np.outer([a, b, c], [a, b, c])


def moment_frame(basis, cell) -> np.ndarray:
    """Orthonormal frame of the allowed subspace, ``(n, 3)`` crystal-axis rows.

    Gram-Schmidt on ``basis``'s rows in the unit-vector metric, so
    ``E @ G @ E.T`` is the identity and a vector's coefficients on the frame
    are ``E @ G @ m``.  Deterministic, because the input basis is M-5's
    deterministic smallest-integer one and the orthogonalisation walks it in
    order — two runs of the same stage give the same frame, which is what lets
    a DOF value be compared between them.

    Raises when a row is linearly dependent on its predecessors, which cannot
    happen for a basis and is therefore a corrupted one rather than a case to
    handle.
    """
    b = np.asarray(basis, dtype=np.float64).reshape(-1, 3)
    g = unit_metric(cell)
    rows: list[np.ndarray] = []
    for raw in b:
        v = raw.copy()
        for e in rows:
            v = v - float(e @ g @ raw) * e
        norm = float(np.sqrt(max(v @ g @ v, 0.0)))
        if norm <= 1e-9:
            raise ValueError(
                f"the allowed-moment basis {b.tolist()} is not a basis: row "
                f"{raw.tolist()} is a combination of the rows before it")
        rows.append(v / norm)
    return np.asarray(rows, dtype=np.float64).reshape(len(b), 3)


def n_dofs(basis) -> int:
    """How many DOFs a site with this allowed basis contributes."""
    return len(np.asarray(basis, dtype=np.float64).reshape(-1, 3))


def moment_from_dofs(frame, dofs) -> np.ndarray:
    """Crystal-axis components (μ_B) from ``(μ, angles…)``.

    The inverse of :func:`dofs_from_moment` up to the branch cuts of ``atan2``
    and ``arccos``, which is all a parameterisation can promise: (μ, φ) and
    (−μ, φ + π) are the same moment and the fit may land on either.
    """
    e = np.asarray(frame, dtype=np.float64).reshape(-1, 3)
    n = len(e)
    if n == 0:
        return np.zeros(3, dtype=np.float64)
    d = np.asarray(dofs, dtype=np.float64).reshape(-1)
    if len(d) != n:
        raise ValueError(f"a {n}-dimensional moment subspace takes {n} DOFs, "
                         f"got {len(d)}")
    return _coefficients(d) @ e


def _coefficients(d: np.ndarray) -> np.ndarray:
    """``(n,)`` coefficients on the frame from the ``(n,)`` DOF vector."""
    mu = d[0]
    if len(d) == 1:
        return np.array([mu])
    if len(d) == 2:
        phi = d[1]
        return mu * np.array([np.cos(phi), np.sin(phi)])
    theta, phi = d[1], d[2]
    st = np.sin(theta)
    return mu * np.array([st * np.cos(phi), st * np.sin(phi), np.cos(theta)])


def dofs_from_moment(frame, cell, moment) -> np.ndarray:
    """``(μ, angles…)`` from crystal-axis components — the seed at stage start.

    The moment is assumed to lie in the frame's span; the schema refuses one
    that does not (``Phase._moments_are_stateable``), so anything out of plane
    here is a corrupted table rather than a user error to symmetrise.  μ comes
    back **signed** for a one-dimensional subspace and non-negative otherwise.
    """
    e = np.asarray(frame, dtype=np.float64).reshape(-1, 3)
    n = len(e)
    if n == 0:
        return np.zeros(0, dtype=np.float64)
    g = unit_metric(cell)
    c = e @ g @ np.asarray(moment, dtype=np.float64).reshape(3)
    if n == 1:
        return np.array([c[0]])
    mu = float(np.linalg.norm(c))
    phi = float(np.arctan2(c[1], c[0]))
    if n == 2:
        return np.array([mu, phi])
    theta = 0.0 if mu == 0.0 else float(np.arccos(np.clip(c[2] / mu, -1.0, 1.0)))
    return np.array([mu, theta, phi])


def d_moment_d_dofs(frame, dofs) -> np.ndarray:
    """``(n, 3)`` — ∂(crystal-axis components)/∂DOF, analytic.

    Not used by the forward model, which takes the whole-model finite-
    difference column for a moment DOF under the ``_make_jacobian`` gate; it is
    here so that a finite-difference check has something exact to be checked
    *against*, and so the analytic branch, when it lands, has one authority for
    the chain rule rather than a second derivation.
    """
    e = np.asarray(frame, dtype=np.float64).reshape(-1, 3)
    n = len(e)
    d = np.asarray(dofs, dtype=np.float64).reshape(-1)
    if n == 0:
        return np.zeros((0, 3), dtype=np.float64)
    mu = d[0]
    if n == 1:
        dc = np.array([[1.0]])
    elif n == 2:
        phi = d[1]
        dc = np.array([[np.cos(phi), np.sin(phi)],
                       [-mu * np.sin(phi), mu * np.cos(phi)]])
    else:
        theta, phi = d[1], d[2]
        st, ct, sp, cp = np.sin(theta), np.cos(theta), np.sin(phi), np.cos(phi)
        dc = np.array([
            [st * cp, st * sp, ct],
            [mu * ct * cp, mu * ct * sp, -mu * st],
            [-mu * st * sp, mu * st * cp, 0.0],
        ])
    return dc @ e

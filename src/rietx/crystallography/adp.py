"""Anisotropic displacement parameters: representations and conversions.

Three representations of the same physical tensor appear in the literature;
this module names them explicitly rather than letting "U" mean whichever one
the caller had in mind (nomenclature per Trueblood, Bürgi, Burzlaff, Dunitz,
Gramaccioli, Schulz, Shmueli & Abrahams, 1996, Acta Cryst. A52, 770):

* **U^ij** (Å²) — the CIF ``_atom_site_aniso_U_ij`` convention, defined by

      T(h) = exp(−2π² Σ_ij U^ij h_i h_j a*_i a*_j),

  and the representation stored in :class:`~rietx.schemas.structure.AnisoU`
  (so that what goes into a CIF is what came out of one).
* **U\\*** (dimensionless) — U*_ij = U^ij·a*_i·a*_j, giving T = exp(−2π² hᵀU*h).
  U* is the mean-square displacement tensor expressed in **fractional direct**
  coordinates, U*_ij = ⟨u_i u_j⟩, which is why it transforms as U* → R·U*·Rᵀ
  under a symmetry rotation R acting on fractional coordinates — and hence why
  evaluating the *image* atom's factor at h is identical to evaluating the
  parent's at Rᵀh (the reciprocal-space action; see ``symmetry.py``).  This is
  the form the structure factor uses.
* **U_cart** (Å²) — U_cart = M·U*·Mᵀ with M the direct lattice vectors as
  columns of a Cartesian frame.  Its eigenvalues are the mean-square
  displacements (Å²) along the principal axes of the displacement ellipsoid
  and U_eq = tr(U_cart)/3 (Fischer & Tillmanns, 1988, Acta Cryst. C44, 775).

Positive-definiteness is a property of the physical tensor U_cart, but all
three are related by congruences with invertible matrices, so by Sylvester's
law of inertia they share the *signs* of their eigenvalues: the guard can test
whichever representation is at hand (the magnitudes are only physical in
U_cart).

Component order throughout is the Voigt-like **(U11, U22, U33, U12, U13, U23)**
used by ``crystallography.wyckoff``.
"""

from __future__ import annotations

import numpy as np

from ..backend import get_backend
from .lattice import direct_metric_tensor, reciprocal_metric_tensor

#: Field/parameter names in storage order.
U_NAMES: tuple[str, ...] = ("u11", "u22", "u33", "u12", "u13", "u23")

#: Index pairs matching :data:`U_NAMES`.
VOIGT: tuple[tuple[int, int], ...] = ((0, 0), (1, 1), (2, 2), (0, 1), (0, 2), (1, 2))


def tensor_from_voigt(u6) -> np.ndarray:
    """(6,) component vector → symmetric (3,3) matrix."""
    u = np.asarray(u6, dtype=np.float64)
    out = np.empty((3, 3), dtype=np.float64)
    for v, (i, j) in enumerate(VOIGT):
        out[i, j] = out[j, i] = u[v]
    return out


def voigt_from_tensor(u33) -> np.ndarray:
    """Symmetric (3,3) matrix → (6,) component vector (symmetry not checked)."""
    u = np.asarray(u33, dtype=np.float64)
    return np.array([u[i, j] for i, j in VOIGT], dtype=np.float64)


def reciprocal_axis_lengths(a: float, b: float, c: float,
                            alpha: float, beta: float, gamma: float) -> np.ndarray:
    """(a*, b*, c*) in Å⁻¹ — the diagonal of the reciprocal metric, rooted."""
    xp = get_backend()
    gstar = reciprocal_metric_tensor(a, b, c, alpha, beta, gamma)
    return xp.sqrt(gstar.diagonal())


def ustar_from_ucif(u6, astar) -> np.ndarray:
    """U*_ij = U^ij·a*_i·a*_j — the (3,3) tensor the structure factor wants.

    On the θ-dependent path (u6 refines), so the symmetric tensor is stacked
    from its components rather than written into a buffer, and the a*⊗a* outer
    product is a broadcast multiply.
    """
    xp = get_backend()
    s = xp.asarray(astar, dtype=np.float64)
    u = xp.asarray(u6, dtype=np.float64)
    tensor = xp.stack([xp.stack([u[0], u[3], u[4]]),
                       xp.stack([u[3], u[1], u[5]]),
                       xp.stack([u[4], u[5], u[2]])])
    return tensor * (s[:, None] * s[None, :])


def cartesian_basis(a: float, b: float, c: float,
                    alpha: float, beta: float, gamma: float) -> np.ndarray:
    """Direct lattice vectors as columns of a Cartesian frame, M (Å).

    Any M with MᵀM = G works — the choice of Cartesian orientation cancels in
    every quantity reported here (eigenvalues, trace) — so the Cholesky factor
    is used instead of a hand-written a-along-x convention.
    """
    g = direct_metric_tensor(a, b, c, alpha, beta, gamma)
    return np.linalg.cholesky(g).T


def u_cartesian(u6, cell) -> np.ndarray:
    """U_cart (Å²) from CIF U^ij and a (a, b, c, α, β, γ) tuple."""
    m = cartesian_basis(*cell)
    ustar = ustar_from_ucif(u6, reciprocal_axis_lengths(*cell))
    return m @ ustar @ m.T


def u_equivalent(u6, cell) -> float:
    """U_eq = tr(U_cart)/3 (Å²) — the isotropic equivalent (Fischer 1988)."""
    return float(np.trace(u_cartesian(u6, cell)) / 3.0)


def principal_values(u6, cell) -> np.ndarray:
    """Ascending eigenvalues of U_cart (Å²): the ellipsoid's semi-axes².

    Negative entries mean the ellipsoid is not an ellipsoid — see
    :func:`is_positive_definite`.
    """
    return np.linalg.eigvalsh(u_cartesian(u6, cell))


def min_eigenvalue(u6) -> float:
    """Smallest eigenvalue of the U^ij matrix itself.

    Its *sign* answers the physical question (congruence preserves inertia,
    see the module docstring), so this needs no cell; its magnitude is not a
    mean-square displacement — use :func:`principal_values` for that.
    """
    return float(np.linalg.eigvalsh(tensor_from_voigt(u6))[0])


def is_positive_definite(u6, *, tol: float = 0.0) -> bool:
    """Whether the displacement ellipsoid is physical (all eigenvalues > tol)."""
    return min_eigenvalue(u6) > tol


def isotropic_u6(uiso: float, cell) -> np.ndarray:
    """The U^ij tensor equivalent to a single isotropic Uiso (Å²).

    The isotropic factor is exp(−2π²·Uiso/d²) and 1/d² = hᵀG*h, so the
    equivalent anisotropic tensor is the one with U*_ij = Uiso·G*_ij, i.e.

        U^ij = Uiso · G*_ij / (a*_i·a*_j)

    — **not** Uiso·δ_ij, which only coincides with it when the reciprocal axes
    are orthogonal (cubic, tetragonal, orthorhombic).  The off-diagonal terms
    are Uiso·cos(reciprocal axis angle); for a hexagonal cell (γ = 120°,
    γ* = 60°) that is U12 = Uiso/2, the familiar hexagonal ADP constraint.
    """
    gstar = reciprocal_metric_tensor(*cell)
    s = np.sqrt(np.diag(gstar))
    return voigt_from_tensor(float(uiso) * gstar / np.outer(s, s))

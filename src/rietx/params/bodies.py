"""The rigid-body derived block (WP-1805): a body's atoms from its pose.

One :class:`~rietx.params.derived.DerivedBlock` per ``RigidBody``.  Inputs, in
this order: the phase's six cell entries (live, WP-1803's record), the body's
origin x, y, z (fractional; themselves anchored rows on the origin's site
basis), and the k rotation DOFs θ (rad).  Outputs: x, y, z of every member
atom, in template order.  The map is

    x_i = o + M⁻¹(cell) · Exp(E·θ) · R₀ · T_i,

with δω = E·θ the rotation increment in the Cartesian frame.  **k is the
template's inertia rank** (``fragments.Fragment.body_frame``): three, with
E = I, for any body that is not linear; two for a linear one, with E's columns
the two lab directions perpendicular to its axis R₀·u, since a rotation about
the axis moves nothing and a third DOF would be a flat direction that blinds
every atom's esd.

Its Jacobian is closed-form, block by block (the design report's § 2.2):

* ∂x_i/∂o = I;
* ∂x_i/∂θ_j = Σ_k M⁻¹ · ∂R/∂δω_k · T_i · E_kj, with ∂R/∂δω_k from
  ``rotation.d_matrix_d_vector`` (Solà et al. 2018, eqs. 72, 145);
* ∂x_i/∂cell_q = −M⁻¹ · ∂M/∂cell_q · (x_i − o), from
  ``derived.d_cartesian_frame_d_cell``.

**The increment composes at commit** (:meth:`RigidBodyBlock.commit_rotation`,
the record in ``docs/DESIGN.md``): R₀ ← Exp(δω)·R₀ and θ ← 0, so every stage
starts at the identity of the exponential map, where its Jacobian is never
singular (Triggs, McLauchlan, Hartley & Fitzgibbon 2000, *Bundle adjustment —
a modern synthesis*, LNCS 1883, § 2.2).  The same call returns the k × k
matrix ∂θ_old/∂θ_new that carries a solver outcome into the composed chart.

TOPAS states the same chain for a body's esds (Coelho, *TOPAS-Academic V6
Technical Reference*, § 10.22.8): every body atom's coordinate is a function of
the body's parameters and its esd comes through them.
"""

from __future__ import annotations

import numpy as np

from ..backend import get_backend
from ..crystallography import rotation
from ..crystallography.fragments import Fragment
from .derived import DerivedBlock, d_cartesian_frame_d_cell, fractional_frame

CELL_NAMES = ("a", "b", "c", "alpha", "beta", "gamma")


def compose_rotation(omega: np.ndarray, r0: np.ndarray) -> np.ndarray:
    """Exp(ω)·R₀, the re-exponentiation a commit performs (numpy).

    A module function so that a test can replace it with what skipping the
    re-exponentiation would do — (I + [ω]×)·R₀, or R₀ unchanged — and see the
    commit-time guard refuse the result.
    """
    return np.asarray(rotation.matrix_from_vector(np.asarray(omega, dtype=np.float64)),
                      dtype=np.float64) @ r0


def rotation_axes(template: np.ndarray) -> np.ndarray:
    """The template-frame rotation axes that move the body, (3, k) columns.

    The rows of ``Fragment.body_frame().rotation_axes`` (WP-1802): the
    identity for any body that is not linear (k = 3), the plane perpendicular
    to the axis for a linear one (k = 2).  A template whose points coincide has
    no rotation at all and is refused, naming why.
    """
    pts = np.asarray(template, dtype=np.float64)
    axes = Fragment(species=("X",) * len(pts), xyz=pts).body_frame().rotation_axes
    if axes.shape[0] < 2:
        raise ValueError(
            "a rigid body whose template points coincide has no orientation "
            "to refine; give its atoms distinct template positions")
    return np.array(axes.T, dtype=np.float64)


class RigidBodyBlock(DerivedBlock):
    """x_i = o + M⁻¹·Exp(δω)·R₀·T_i for one body; see the module docstring."""

    #: inputs before the body's own: the six cell entries
    N_CELL = 6

    def __init__(self, *, phase_base: str, body_base: str, atom_bases: list[str],
                 template: np.ndarray, q0):
        self.template = np.asarray(template, dtype=np.float64)
        #: the template-frame axes the rotation DOFs turn about, (3, k)
        self.body_axes = rotation_axes(self.template)
        self._set_anchor(np.asarray(q0, dtype=np.float64))
        self.inputs = (
            *(f"{phase_base}.cell.{n}" for n in CELL_NAMES),
            *(f"{body_base}.origin.{c}" for c in "xyz"),
            *self.rotation_paths(body_base),
        )
        self.outputs = tuple(f"{a}.{c}" for a in atom_bases for c in "xyz")

    @property
    def n_rot(self) -> int:
        """The number of rotation DOFs: the template's inertia rank, 2 or 3."""
        return int(self.body_axes.shape[1])

    def rotation_paths(self, body_base: str) -> tuple[str, ...]:
        return tuple(f"{body_base}.rotation.{k}" for k in range(self.n_rot))

    def _set_anchor(self, q0: np.ndarray, r0: np.ndarray | None = None) -> None:
        """R₀ from its record, and the lab-frame increment basis E it implies.

        ``q0`` is the canonical unit quaternion the model stores; ``r0`` the
        matrix when it is already in hand.  E = I for k = 3, so the increment's
        components are the Cartesian frame's; for a linear body E = R₀·A, the
        template-frame perpendicular axes A carried into the lab, so E moves
        with every composition and stays perpendicular to the axis.
        """
        self.q0 = q0
        self.r0 = (np.asarray(rotation.matrix_from_quaternion(q0), dtype=np.float64)
                   if r0 is None else r0)
        self.axes = np.eye(3) if self.n_rot == 3 else self.r0 @ self.body_axes

    def omega(self, theta_rot) -> np.ndarray:
        """δω = E·θ (rad, Cartesian) from the k rotation DOFs."""
        return self.axes @ np.asarray(theta_rot, dtype=np.float64)

    # -- the template (WP-1808 widens this with torsions) ---------------
    def body_points(self, x: np.ndarray) -> np.ndarray:
        """The template in the body frame, before the pose (n, 3), numpy."""
        return self.template

    def body_tangents(self, x: np.ndarray) -> np.ndarray:
        """∂(body points)/∂(extra inputs), (n_extra, n, 3); none here."""
        return np.zeros((0, len(self.template), 3))

    def body_points_traced(self, x):
        xp = get_backend()
        return [xp.asarray(t) for t in self.template]

    # -- the map ---------------------------------------------------------
    def _pose(self, x: np.ndarray):
        cell = tuple(float(v) for v in x[:6])
        o, w = x[6:9], self.omega(x[9:9 + self.n_rot])
        minv = np.asarray(fractional_frame(cell), dtype=np.float64)
        rot = np.asarray(rotation.matrix_from_vector(np.asarray(w)),
                         dtype=np.float64) @ self.r0
        return cell, o, w, minv, rot

    def evaluate(self, x):
        x = np.asarray(x, dtype=np.float64)
        _, o, _, minv, rot = self._pose(x)
        pts = self.body_points(x)
        return (o + pts @ (minv @ rot).T).ravel()

    def jacobian(self, x):
        x = np.asarray(x, dtype=np.float64)
        cell, o, w, minv, rot = self._pose(x)
        pts = self.body_points(x)
        n = len(pts)
        jac = np.zeros((3 * n, len(self.inputs)), dtype=np.float64)
        rel = pts @ (minv @ rot).T                        # x_i − o, fractional
        dm = d_cartesian_frame_d_cell(cell)
        for q in range(6):
            jac[:, q] = -(rel @ (minv @ dm[q]).T).ravel()
        for c in range(3):
            jac[c::3, 6 + c] = 1.0
        dr = np.asarray(rotation.d_matrix_d_vector(np.asarray(w), self.r0),
                        dtype=np.float64)
        # d_matrix_d_vector includes R₀; the body points are pre-R₀ coordinates
        k = self.n_rot
        dw = np.stack([(pts @ (minv @ dr[c]).T).ravel() for c in range(3)], axis=1)
        jac[:, 9:9 + k] = dw @ self.axes
        tangents = self.body_tangents(x)
        for t in range(len(tangents)):
            jac[:, 9 + k + t] = (tangents[t] @ (minv @ rot).T).ravel()
        return jac

    def evaluate_traced(self, x):
        xp = get_backend()
        cell = tuple(x[:6])
        o = xp.stack(list(x[6:9]))
        w = xp.matmul(xp.asarray(self.axes, dtype=np.float64),
                      xp.stack(list(x[9:9 + self.n_rot])))
        minv = fractional_frame(cell)
        frame = xp.matmul(minv, xp.matmul(rotation.matrix_from_vector(w),
                                          xp.asarray(self.r0)))
        out = []
        for p in self.body_points_traced(x):
            v = o + xp.matmul(frame, p)
            out.extend([v[0], v[1], v[2]])
        return out

    def reach_pattern(self):
        pattern = np.zeros((len(self.outputs), len(self.inputs)), dtype=bool)
        pattern[:, :9 + self.n_rot] = True
        return pattern

    # -- the record --------------------------------------------------------
    def orientation(self, theta_rot) -> np.ndarray:
        """The pose's quaternion, canonical, at rotation DOFs ``theta_rot``.

        Exactly the record R₀ came from where θ = 0, which is every value a
        commit leaves; elsewhere (a value set by hand and not yet committed)
        the pose Exp(E·θ)·R₀ it describes.
        """
        w = self.omega(theta_rot)
        if not w.any():
            return self.q0
        return np.asarray(rotation.canonical_quaternion(
            rotation.quaternion_from_matrix(compose_rotation(w, self.r0))),
            dtype=np.float64)

    def commit_rotation(self, theta_rot) -> np.ndarray | None:
        """Compose the increment into the anchor: R₀ ← Exp(E·θ)·R₀, θ ← 0.

        Returns ∂θ_old/∂θ_new at the committed pose (k × k), the matrix that
        restates a solver outcome in the new chart, or ``None`` when θ = 0 and
        nothing moved.  Derivation (Solà et al. 2018, eq. 72): the old chart
        reaches R = Exp(ω_old)·R₀ and the new one R = Exp(ω_new)·R*, with
        R* = Exp(ω*)·R₀; near the pose Exp(ω* + δ)·R₀ = Exp(J_l(ω*)·δ)·R*, so
        δω_old = J_l(ω*)⁻¹·δω_new.  For k = 3 that is the answer.  For a linear
        body ω lives on E's plane, and J_l⁻¹·E_new·δθ_new leaves it by a
        component along n = J_l(ω*)⁻¹·R*·u, the old chart's null direction
        (a turn about the axis moves no atom), so the matrix is the E_old part
        of the solve [E_old | n]·[c; d] = J_l⁻¹·E_new.

        The new anchor is left as the raw product, not yet canonicalised, so
        the caller's rigidity guard reads the very rotation the atoms will be
        written from; :meth:`settle_anchor` turns it into the record.
        """
        theta_rot = np.asarray(theta_rot, dtype=np.float64)
        if not theta_rot.any():
            return None
        w = self.omega(theta_rot)
        axes_old = self.axes
        r_new = compose_rotation(w, self.r0)
        jl_inv = np.linalg.inv(np.asarray(rotation.left_jacobian(w), dtype=np.float64))
        self.r0 = r_new
        self.axes = np.eye(3) if self.n_rot == 3 else r_new @ self.body_axes
        if self.n_rot == 3:
            return jl_inv
        axis = r_new @ np.cross(self.body_axes[:, 0], self.body_axes[:, 1])
        basis = np.column_stack([axes_old, jl_inv @ axis])
        return np.linalg.solve(basis, jl_inv @ self.axes)[:2]

    def settle_anchor(self) -> None:
        """Store the committed R₀ as its canonical quaternion record.

        R₀ is re-read from that quaternion, so a table rebuilt from the
        written-back model anchors on the identical matrix.
        """
        q = np.asarray(rotation.canonical_quaternion(
            rotation.quaternion_from_matrix(self.r0)), dtype=np.float64)
        self._set_anchor(q)

    def restore_anchor(self, q0, r0, axes) -> None:
        """Put back an anchor a commit replaced (a collapsed phase's restore)."""
        self.q0, self.r0, self.axes = q0, r0, axes

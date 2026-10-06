"""The rigid-body derived block (WP-1805): a body's atoms from its pose.

One :class:`~rietx.params.derived.DerivedBlock` per ``RigidBody``.  Inputs, in
this order: the phase's six cell entries (live, WP-1803's record), the body's
origin x, y, z (fractional; themselves anchored rows on the origin's site
basis), and the three components of the rotation increment δω (rad).  Outputs:
x, y, z of every member atom, in template order.  The map is

    x_i = o + M⁻¹(cell) · Exp(δω) · R₀ · T_i,

and its Jacobian is closed-form, block by block (the design report's § 2.2):

* ∂x_i/∂o = I;
* ∂x_i/∂δω_k = M⁻¹ · ∂R/∂δω_k · T_i, with ∂R/∂δω_k from
  ``rotation.d_matrix_d_vector`` (Solà et al. 2018, eqs. 72, 145);
* ∂x_i/∂cell_q = −M⁻¹ · ∂M/∂cell_q · (x_i − o), from
  ``derived.d_cartesian_frame_d_cell``.

TOPAS states the same chain for a body's esds (Coelho, *TOPAS-Academic V6
Technical Reference*, § 10.22.8): every body atom's coordinate is a function of
the body's parameters and its esd comes through them.
"""

from __future__ import annotations

import numpy as np

from ..backend import get_backend
from ..crystallography import rotation
from .derived import DerivedBlock, d_cartesian_frame_d_cell, fractional_frame

CELL_NAMES = ("a", "b", "c", "alpha", "beta", "gamma")


class RigidBodyBlock(DerivedBlock):
    """x_i = o + M⁻¹·Exp(δω)·R₀·T_i for one body; see the module docstring."""

    #: inputs before the body's own: the six cell entries
    N_CELL = 6

    def __init__(self, *, phase_base: str, body_base: str, atom_bases: list[str],
                 template: np.ndarray, r0: np.ndarray):
        self.template = np.asarray(template, dtype=np.float64)
        self.r0 = np.asarray(r0, dtype=np.float64)
        self.inputs = (
            *(f"{phase_base}.cell.{n}" for n in CELL_NAMES),
            *(f"{body_base}.origin.{c}" for c in "xyz"),
            *(f"{body_base}.rotation.{k}" for k in range(3)),
        )
        self.outputs = tuple(f"{a}.{c}" for a in atom_bases for c in "xyz")

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
        o, w = x[6:9], x[9:12]
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
        for k in range(3):
            jac[:, 9 + k] = (pts @ (minv @ dr[k]).T).ravel()
        tangents = self.body_tangents(x)
        for t in range(len(tangents)):
            jac[:, 12 + t] = (tangents[t] @ (minv @ rot).T).ravel()
        return jac

    def evaluate_traced(self, x):
        xp = get_backend()
        cell = tuple(x[:6])
        o = xp.stack(list(x[6:9]))
        w = xp.stack(list(x[9:12]))
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
        pattern[:, :12] = True
        return pattern

    # -- the record --------------------------------------------------------
    def orientation(self, w) -> np.ndarray:
        """R = Exp(δω)·R₀ at the increment ``w`` (rad), for the write-back."""
        return np.asarray(rotation.matrix_from_vector(np.asarray(w, dtype=np.float64)),
                          dtype=np.float64) @ self.r0

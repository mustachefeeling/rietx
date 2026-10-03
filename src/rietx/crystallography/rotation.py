"""Rotations in 3-D: rotation vector ↔ matrix ↔ unit quaternion, and ∂R/∂δω.

The mathematics a rigid body's orientation needs (WP-1801, the first rung of
rigid-bodies; issue #561), and nothing of the body itself.  The authority for every formula is Solà, J., Deray, J. &
Atchuthan, D. (2018), *A micro Lie theory for state estimation in robotics*,
arXiv:1812.01537 (v9, 2021); equation numbers below are that paper's.

**Three representations of one rotation.**

* **Rotation vector** ω = θu (rad), the Cartesian tangent space of SO(3) at the
  identity — θ the angle, u the unit axis (§ B, p. 15).
* **Rotation matrix** R ∈ SO(3), acting on a column vector as x' = R·x
  (eq. 137): the *active* rotation by θ about u, right-handed.
* **Unit quaternion** q = (w, x, y, z), Hamilton's convention
  i² = j² = k² = ijk = −1 (text after eq. 131), acting as x' = q·x·q*
  (eq. 136).  q and −q are the same rotation (the double cover, p. 15), so a
  stored quaternion is put in the **canonical form w ≥ 0**, and where w = 0
  exactly, the first nonzero of (x, y, z) positive.  The form is a sign
  choice only, so applying it twice changes no bit.

The maps between them are Exp (eqs. 132, 134), Log (eqs. 133, 135) and
eq. (138), R(q).  The angle is in **radians** throughout.  CONTRIBUTING's
degrees rule is for user-facing angles, and nothing here is one: this module
is internal, like the moment DOFs (``magnetic/moments.py`` declares them
``"rad"``), and a reported orientation converts at the report.

**How a refinement uses it.**  An orientation is refined as an *anchored*
increment δω about the stage's starting matrix R₀, the left-plus of eq. (27):
R = Exp(δω)·R₀.  δω starts at 0 on every stage, so the refinement never
meets a gimbal lock.  Exp is smooth everywhere, and its Jacobian J_l
(eq. 145) is singular only at |δω| = 2π, 4π, … (its two transverse singular
values are |sin(θ/2)|/(θ/2)), so the increment stays full rank through
|δω| = π and beyond; |δω| = π matters only to Log, on the record side.
:func:`d_matrix_d_vector` is ∂R/∂δω_k, analytic, through the left Jacobian
(eqs. 71, 72, 145).

**Backend ops throughout.**  Every map is written in the backend namespace's
ops (``get_backend()``: ``sin``, ``cos``, ``arcsin``, ``arccos``, ``sqrt``,
``where``, ``sum``, ``stack``, ``concatenate``, ``matmul``, all already in
``backend.api._OP_NAMES``), with no frozen numpy constant on the left of an
operator.  :func:`skew`, :func:`matrix_from_vector`, :func:`left_jacobian`
and :func:`d_matrix_d_vector` sit on the path from θ to atom coordinates;
the quaternion maps, Log and composition are used at a seed, a commit and a
report, and are written the same way so that any of them can be traced.
Every branch is a ``where`` over both sides with the unselected argument
kept finite (``sqrt`` of 1 on the series side, a divisor of 1 on the
unselected quaternion candidates), so an autodiff backend never
differentiates 0/0.  The refusals of a wrong input run on numpy only.

**The small-angle branch.**  Three coefficients carry every θ-path formula:

    A(θ) = sin θ / θ,   B(θ) = (1 − cos θ) / θ²,   C(θ) = (θ − sin θ) / θ³.

All three are 0/0 at θ = 0, and C's closed form loses about 6ε/θ² of its
relative precision to cancellation.  Below :data:`SERIES_THRESHOLD` each is
its Maclaurin series through θ¹⁰, whose first omitted term is below 1e-16
relative at the threshold; above it, the closed form, with B written as
2 sin²(θ/2)/θ² (the same number, without the cancellation of 1 − cos θ).
C's closed form is then good to about 1e-14 relative at the threshold, and C
multiplies [ω]ײ, which is O(θ²), so its contribution to J_l is good to
about 1e-16 absolute.  ``tests/test_rotation.py`` checks all three against a
60-digit Decimal evaluation on both sides of the threshold.

**Log near |ω| = π.**  Log goes through the quaternion: w and ‖v‖ are both
well conditioned from R (the component whose square is largest is taken
from the diagonal, the other three from the off-diagonal sums and
differences), and θ = 2·atan2(‖v‖, w) (eq. 133, evaluated as arcsin ‖v‖ or
arccos w, whichever argument is ≤ 1/√2) keeps full precision near 0 and near
π, where eq. (135)'s arccos and 1/sin θ do not.  At exactly
θ = π the two vectors ±πu are one rotation; the canonical form's tie-break
picks the one whose first nonzero component is positive.  A vector with
|ω| > π comes back as the equivalent vector with |ω| ≤ π: Log is the inverse
of Exp on the ball |ω| < π only.
"""

from __future__ import annotations

import numpy as np

from ..backend import get_backend

#: |ω| (rad) below which A, B and C are evaluated by their series (module
#: docstring, "The small-angle branch").  At 0.25 rad the first omitted
#: series term is < 1e-16 relative, and C's closed form just above it is good
#: to ~1e-14 relative, i.e. ~1e-16 absolute in J_l.
SERIES_THRESHOLD: float = 0.25

#: How far ‖q‖ may sit from 1, or RᵀR from I, before an input is refused
#: rather than read as a rotation.  A stored record carries 15 digits, so a
#: legitimate input is within ~1e-15; 1e-9 refuses a wrong object, not noise.
UNIT_TOLERANCE: float = 1e-9

# Maclaurin coefficients through θ¹⁰ (in powers of θ²), lowest first:
#   A = Σ (−1)ᵏ θ²ᵏ/(2k+1)!,  B = Σ (−1)ᵏ θ²ᵏ/(2k+2)!,  C = Σ (−1)ᵏ θ²ᵏ/(2k+3)!
_A_SERIES = (1.0, -1.0 / 6, 1.0 / 120, -1.0 / 5040, 1.0 / 362880, -1.0 / 39916800)
_B_SERIES = (1.0 / 2, -1.0 / 24, 1.0 / 720, -1.0 / 40320, 1.0 / 3628800,
             -1.0 / 479001600)
_C_SERIES = (1.0 / 6, -1.0 / 120, 1.0 / 5040, -1.0 / 362880, 1.0 / 39916800,
             -1.0 / 6227020800)

# a quaternion's vector norm below which atan2(n, w)/n is taken by its series
_LOG_SERIES_NORM = 1e-8


def _horner(coeffs, t):
    """Σ coeffs[k]·tᵏ, highest power innermost."""
    acc = coeffs[-1] + 0.0 * t
    for c in coeffs[-2::-1]:
        acc = acc * t + c
    return acc


def _coefficients(theta_sq):
    """(A, B, C) of the module docstring at θ² — the small-angle branch.

    Both branches are evaluated and one is selected, so the closed form's θ is
    ``sqrt(1)`` wherever the series is taken: no 0/0 reaches a derivative.
    """
    xp = get_backend()
    small = theta_sq < SERIES_THRESHOLD ** 2
    theta = xp.sqrt(xp.where(small, 1.0, theta_sq))
    s = xp.sin(theta)
    half = xp.sin(0.5 * theta)
    closed_a = s / theta
    closed_b = 2.0 * half * half / (theta * theta)
    closed_c = (theta - s) / (theta * theta * theta)
    return (xp.where(small, _horner(_A_SERIES, theta_sq), closed_a),
            xp.where(small, _horner(_B_SERIES, theta_sq), closed_b),
            xp.where(small, _horner(_C_SERIES, theta_sq), closed_c))


def skew(v):
    """[v]× — the skew-symmetric matrix with [v]×·x = v × x (Solà 2018, Ex. 3, p. 5)."""
    xp = get_backend()
    v = xp.asarray(v, dtype=np.float64)
    zero = 0.0 * v[0]
    return xp.stack([xp.stack([zero, -v[2], v[1]]),
                     xp.stack([v[2], zero, -v[0]]),
                     xp.stack([-v[1], v[0], zero])])


def matrix_from_vector(omega):
    """R = Exp(ω), the Rodrigues formula (Solà, Deray & Atchuthan 2018, eq. 134).

    Written in the vector ω = θu rather than in u, which is eq. (134) with
    [u]× = [ω]×/θ: R = I + A(θ)[ω]× + B(θ)[ω]ײ.  Exact at ω = 0 through the
    series branch (:data:`SERIES_THRESHOLD`).  ω in radians.
    """
    xp = get_backend()
    omega = xp.asarray(omega, dtype=np.float64)
    a, b, _ = _coefficients(xp.sum(omega * omega))
    k = skew(omega)
    eye = xp.asarray(np.eye(3), dtype=np.float64)
    return eye + a * k + b * xp.matmul(k, k)


def left_jacobian(omega):
    """J_l(ω) = I + B(θ)[ω]× + C(θ)[ω]ײ (Solà, Deray & Atchuthan 2018, eq. 145).

    Defined by eq. (71) and used through eq. (72), Exp(ω + δ) ≈ Exp(J_l·δ)·Exp(ω):
    a small change δ of the rotation vector is the rotation J_l·δ applied on
    the left.  J_l = J_rᵀ (eq. 147), and J_l(0) = I.
    """
    xp = get_backend()
    omega = xp.asarray(omega, dtype=np.float64)
    _, b, c = _coefficients(xp.sum(omega * omega))
    k = skew(omega)
    eye = xp.asarray(np.eye(3), dtype=np.float64)
    return eye + b * k + c * xp.matmul(k, k)


def d_matrix_d_vector(omega, r0=None):
    """∂R/∂ω_k for R = Exp(ω)·R₀, stacked on the first axis: shape (3, 3, 3).

    From eq. (72) (Solà, Deray & Atchuthan 2018), Exp(ω + h·e_k) =
    Exp(h·J_l(ω)e_k)·Exp(ω) + O(h²), and Exp(h·j) = I + h[j]× + O(h²), so

        ∂R/∂ω_k = [J_l(ω)·e_k]× · Exp(ω) · R₀,

    with J_l from eq. (145).  At ω = 0 this is [e_k]×·R₀, which is never
    singular: the anchored increment has a full-rank Jacobian at the point
    every stage starts from.  ``r0`` defaults to the identity.
    """
    xp = get_backend()
    omega = xp.asarray(omega, dtype=np.float64)
    rot = matrix_from_vector(omega)
    if r0 is not None:
        rot = xp.matmul(rot, xp.asarray(r0, dtype=np.float64))
    jl = left_jacobian(omega)
    return xp.stack([xp.matmul(skew(jl[:, k]), rot) for k in range(3)])


# --- quaternions, Log, composition ------------------------------------------
#
# Written in the same backend ops as the θ path, with every branch a ``where``
# over both sides, so an autodiff backend can differentiate any of them.  The
# refusals (a zero, non-unit or improper input) read values, so they run on the
# numpy backend only: under an autodiff backend the input is a traced value the
# maps above produced, and ``float()`` would collapse it to a constant.


def _checks_run() -> bool:
    """Whether inputs can be checked by value: the numpy backend, not a trace."""
    return get_backend().name == "numpy"


def canonical_quaternion(q):
    """q or −q, whichever has w > 0; where w = 0, the first nonzero of (x, y, z) > 0.

    A sign choice only (q and −q are one rotation, Solà, Deray & Atchuthan
    2018, p. 15), so it is exact and idempotent to the bit; −0.0 comes back as
    +0.0, so the stored bits are unique.  It does not normalise.  A zero
    quaternion is refused.
    """
    xp = get_backend()
    q = xp.asarray(q, dtype=np.float64).reshape(4)
    if _checks_run() and not np.any(q != 0.0):
        raise ValueError("the zero quaternion is not a rotation")
    lead = xp.where(q[0] != 0.0, q[0],
                    xp.where(q[1] != 0.0, q[1], xp.where(q[2] != 0.0, q[2], q[3])))
    return q * xp.where(lead < 0.0, -1.0, 1.0) + 0.0     # + 0.0: −0.0 → +0.0


def _check_unit_quaternion(q) -> None:
    q = np.asarray(q, dtype=np.float64)
    norm = float(np.sqrt(q @ q))
    if not abs(norm - 1.0) <= UNIT_TOLERANCE:
        raise ValueError(f"not a unit quaternion: |q| = {norm!r}")


def quaternion_from_vector(omega):
    """q = Exp(ω) = (cos(θ/2), u·sin(θ/2)), canonical (Solà, Deray & Atchuthan 2018, eq. 132).

    Both parts come from the small-angle coefficients at θ/2: the vector part
    is ω·sin(θ/2)/θ = ω·A(θ/2)/2, and w = cos(θ/2) = 1 − (θ/2)²·B(θ/2), the
    same number without a ``cos(sqrt(θ²))`` whose derivative is 0/0 at ω = 0.
    For |ω| ≤ π, w ≥ 0 already; beyond it the canonical form flips the sign.
    """
    xp = get_backend()
    omega = xp.asarray(omega, dtype=np.float64).reshape(3)
    quarter_sq = 0.25 * xp.sum(omega * omega)          # (θ/2)²
    a_half, b_half, _ = _coefficients(quarter_sq)
    w = 1.0 - quarter_sq * b_half
    return canonical_quaternion(xp.concatenate([xp.stack([w]), 0.5 * a_half * omega]))


def vector_from_quaternion(q):
    """ω = Log(q) = 2·v·atan2(‖v‖, w)/‖v‖ (Solà, Deray & Atchuthan 2018, eq. 133).

    The paper's own guard is applied first: q is put in the canonical form, so
    w ≥ 0 and θ = |ω| ∈ [0, π].  The half-angle atan2(‖v‖, w) is taken, after
    normalising q, as arcsin ‖v‖ where ‖v‖ ≤ w and as arccos w otherwise, so
    each is used only where its argument is ≤ 1/√2 and it is well conditioned
    (the backend namespace has no atan2).  At ‖v‖ below 1e-8 the factor
    2·atan2(‖v‖, w)/‖v‖ is its series 2/w·(1 − x²/3 + x⁴/5), x = ‖v‖/w, since
    the closed form is 0/0 at ‖v‖ = 0.  At θ = π exactly, the sign of the
    returned vector is the canonical tie-break's.
    """
    xp = get_backend()
    q = canonical_quaternion(q)
    if _checks_run():
        _check_unit_quaternion(q)
    q = q / xp.sqrt(xp.sum(q * q))
    w, v = q[0], q[1:]
    n_sq = xp.sum(v * v)
    small = n_sq < _LOG_SERIES_NORM ** 2
    n = xp.sqrt(xp.where(small, 1.0, n_sq))      # 1 on the series side: no 0/0
    by_asin = n_sq <= w * w
    half = xp.where(by_asin, xp.arcsin(xp.where(by_asin, n, 0.0)),
                    xp.arccos(xp.where(by_asin, 0.0, w)))
    w_safe = xp.where(small, w, 1.0)
    x2 = n_sq / (w_safe * w_safe)
    factor = xp.where(small, 2.0 / w_safe * (1.0 - x2 / 3.0 + x2 * x2 / 5.0),
                      2.0 * half / n)
    return factor * v


def matrix_from_quaternion(q):
    """R(q), Solà, Deray & Atchuthan 2018, eq. (138) — the matrix of x' = q·x·q*.

    q must be a unit quaternion to :data:`UNIT_TOLERANCE`, since one that is
    not is a wrong object; within it, q is normalised before R is built, as
    :func:`vector_from_quaternion` does.  R scales as ‖q‖², so RᵀR as ‖q‖⁴:
    unnormalised, a q passing at ‖q‖ − 1 = 9e-10 gave a matrix that
    :func:`quaternion_from_matrix` refused at max|RᵀR − I| = 3.6e-9 under the
    same tolerance.  Normalising keeps R orthonormal to rounding, so the round
    trip holds wherever the first check passes, and the matrix bar stays the
    one a stored record needs rather than being widened by 4.
    """
    xp = get_backend()
    q = xp.asarray(q, dtype=np.float64).reshape(4)
    if _checks_run():
        _check_unit_quaternion(q)
    q = q / xp.sqrt(xp.sum(q * q))
    w, x, y, z = q[0], q[1], q[2], q[3]
    return xp.stack([
        xp.stack([w * w + x * x - y * y - z * z, 2 * (x * y - w * z), 2 * (x * z + w * y)]),
        xp.stack([2 * (x * y + w * z), w * w - x * x + y * y - z * z, 2 * (y * z - w * x)]),
        xp.stack([2 * (x * z - w * y), 2 * (y * z + w * x), w * w - x * x - y * y + z * z]),
    ])


def _check_rotation_matrix(r) -> None:
    r = np.asarray(r, dtype=np.float64)
    err = float(np.max(np.abs(r.T @ r - np.eye(3))))
    if not err <= UNIT_TOLERANCE:
        raise ValueError(f"not orthonormal: max |RᵀR − I| = {err!r}")
    if np.linalg.det(r) < 0.0:
        raise ValueError("det R = −1: an improper rotation is not an orientation")


def quaternion_from_matrix(r):
    """The canonical unit quaternion of R — eq. (138) of Solà, Deray & Atchuthan (2018), inverted.

    From eq. (138) with w² + x² + y² + z² = 1, the diagonal gives each square
    (4w² = 1 + r₁₁ + r₂₂ + r₃₃, 4x² = 1 + r₁₁ − r₂₂ − r₃₃, and so on) and the
    off-diagonal gives each product (4wx = r₃₂ − r₂₃, 4xy = r₂₁ + r₁₂, …).
    The component with the largest square (the first, on a tie) is taken from
    the diagonal and the other three are divided by four times it.  The four
    squares sum to 1, so the largest is ≥ ¼, the component ≥ ½, and no divisor
    is below 2; this is what keeps Log exact near θ = π, where w → 0.  All
    four candidates are built and one selected, with the other three's squares
    replaced by 1, so no unselected branch divides by zero.  The result is
    renormalised (it differs from 1 by rounding only) and canonical.
    """
    xp = get_backend()
    r = xp.asarray(r, dtype=np.float64).reshape(3, 3)
    if _checks_run():
        _check_rotation_matrix(r)
    s0 = 1.0 + r[0, 0] + r[1, 1] + r[2, 2]
    s1 = 1.0 + r[0, 0] - r[1, 1] - r[2, 2]
    s2 = 1.0 - r[0, 0] + r[1, 1] - r[2, 2]
    s3 = 1.0 - r[0, 0] - r[1, 1] + r[2, 2]
    # the first largest, as argmax picks it
    pick0 = (s0 >= s1) & (s0 >= s2) & (s0 >= s3)
    pick1 = ~pick0 & (s1 >= s2) & (s1 >= s3)
    pick2 = ~pick0 & ~pick1 & (s2 >= s3)
    wx = r[2, 1] - r[1, 2]
    wy = r[0, 2] - r[2, 0]
    wz = r[1, 0] - r[0, 1]
    xy = r[1, 0] + r[0, 1]
    xz = r[0, 2] + r[2, 0]
    yz = r[2, 1] + r[1, 2]
    pick3 = ~pick0 & ~pick1 & ~pick2
    big = [0.5 * xp.sqrt(xp.where(pick, s, 1.0))       # |component i|, ≥ 1/2
           for pick, s in ((pick0, s0), (pick1, s1), (pick2, s2), (pick3, s3))]
    cand = [xp.stack([big[0], wx / (4.0 * big[0]), wy / (4.0 * big[0]), wz / (4.0 * big[0])]),
            xp.stack([wx / (4.0 * big[1]), big[1], xy / (4.0 * big[1]), xz / (4.0 * big[1])]),
            xp.stack([wy / (4.0 * big[2]), xy / (4.0 * big[2]), big[2], yz / (4.0 * big[2])]),
            xp.stack([wz / (4.0 * big[3]), xz / (4.0 * big[3]), yz / (4.0 * big[3]), big[3]])]
    q = xp.where(pick0, cand[0], xp.where(pick1, cand[1], xp.where(pick2, cand[2], cand[3])))
    return canonical_quaternion(q / xp.sqrt(xp.sum(q * q)))


def vector_from_matrix(r):
    """ω = Log(R), |ω| ∈ [0, π] — via the quaternion (module docstring, "Log near |ω| = π").

    The same map as Solà, Deray & Atchuthan (2018) eq. (135), computed as
    eq. (133) of eq. (138) inverted, because eq. (135)'s arccos and 1/sin θ
    lose precision near θ = 0 and θ = π.
    """
    return vector_from_quaternion(quaternion_from_matrix(r))


def quaternion_product(qa, qb):
    """qa·qb, Hamilton's product (i² = j² = k² = ijk = −1; Solà, Deray & Atchuthan 2018, p. 15).

    Composition: R(qa·qb) = R(qa)·R(qb), the group product of eq. (1) on
    both representations.  Returned as computed, not canonicalised: the
    product is the group's, and the sign convention belongs to the record, so
    canonicalise the result where it is stored.
    """
    xp = get_backend()
    qa = xp.asarray(qa, dtype=np.float64).reshape(4)
    qb = xp.asarray(qb, dtype=np.float64).reshape(4)
    aw, ax, ay, az = qa[0], qa[1], qa[2], qa[3]
    bw, bx, by, bz = qb[0], qb[1], qb[2], qb[3]
    return xp.stack([aw * bw - ax * bx - ay * by - az * bz,
                     aw * bx + ax * bw + ay * bz - az * by,
                     aw * by - ax * bz + ay * bw + az * bx,
                     aw * bz + ax * by - ay * bx + az * bw])


def compose_vectors(omega_a, omega_b):
    """Log(Exp(ω_a)·Exp(ω_b)) — rotation b first, then a, as one rotation vector.

    Through the quaternion product (Solà, Deray & Atchuthan 2018, eqs. 132,
    133 and the Hamilton product); |result| ∈ [0, π].
    """
    return vector_from_quaternion(quaternion_product(quaternion_from_vector(omega_a),
                                                     quaternion_from_vector(omega_b)))

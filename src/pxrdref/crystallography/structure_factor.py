"""Kinematic structure factors for powder reflections.

F(hkl) = Σ_j occ_j · f_j(k) · exp(−B_j k²) · Σ_m exp(2πi h·(R_m x_j + t_m))

where the inner sum runs over a per-atom subset of symmetry operations chosen
once per refinement stage so that special-position images are not double
counted (the *operation subset* is frozen — a discrete object — while the
positions it produces remain smooth functions of the refined coordinates),
f_j is the Waasmaier-Kirfel form factor with k = sin(θ)/λ, and the
Debye-Waller factor uses B_iso (International Tables C).  Intensities use
|F|² with the reflection multiplicity applied separately (Rietveld, 1969,
J. Appl. Cryst. 2, 65).
"""

from __future__ import annotations

from dataclasses import dataclass

import gemmi
import numpy as np

from ..schemas.structure import Phase
from .scattering import f0, normalize_species
from .symmetry import get_spacegroup


@dataclass
class PhaseSites:
    """Frozen symmetry-operation subsets for one phase.

    For asymmetric-unit atom ``j``, ``ops[j]`` is a pair of arrays
    ``(R (m_j,3,3), t (m_j,3))`` — the operations that generate *distinct*
    orbit images at the atom's compile-time coordinates.  ``m_j`` is the site
    multiplicity.
    """

    ops: list[tuple[np.ndarray, np.ndarray]]
    species: list[str]

    @property
    def n_asym(self) -> int:
        return len(self.species)


def select_orbit_ops(sg: gemmi.SpaceGroup, xyz: np.ndarray, *, tol: float = 1e-4
                     ) -> tuple[np.ndarray, np.ndarray]:
    """Choose the operation subset giving distinct images of ``xyz``.

    On a general position this is all operations; on a special position,
    coincident images are dropped so each orbit member appears exactly once.
    """
    rots, trans, seen = [], [], []
    for op in sg.operations():
        r = np.array(op.rot, dtype=np.float64) / gemmi.Op.DEN
        t = np.array(op.tran, dtype=np.float64) / gemmi.Op.DEN
        p = (r @ np.asarray(xyz, dtype=np.float64) + t) % 1.0
        dup = False
        for q in seen:
            diff = np.abs(p - q)
            diff = np.minimum(diff, 1.0 - diff)
            if np.all(diff < tol):
                dup = True
                break
        if not dup:
            seen.append(p)
            rots.append(r)
            trans.append(t)
    return np.asarray(rots), np.asarray(trans)


def compile_phase_sites(phase: Phase) -> PhaseSites:
    sg = get_spacegroup(phase.space_group)
    ops: list[tuple[np.ndarray, np.ndarray]] = []
    species: list[str] = []
    for atom in phase.atoms:
        xyz = np.array([atom.x.value, atom.y.value, atom.z.value])
        ops.append(select_orbit_ops(sg, xyz))
        species.append(normalize_species(atom.species))
    return PhaseSites(ops=ops, species=species)


def structure_factors_squared(
    hkl: np.ndarray,
    d: np.ndarray,
    sites: PhaseSites,
    xyz: np.ndarray,
    occ: np.ndarray,
    biso: np.ndarray,
) -> np.ndarray:
    """|F(hkl)|² for each reflection.

    Parameters
    ----------
    hkl, d : (N,3) reflection indices and current d-spacings (Å).
    sites : frozen per-atom symmetry-operation subsets.
    xyz : (n_asym, 3) current fractional coordinates.
    occ, biso : (n_asym,) occupancies and isotropic B (Å²).
    """
    k = 1.0 / (2.0 * np.asarray(d, dtype=np.float64))  # sinθ/λ = 1/(2d)
    n_refl = len(hkl)
    h = np.asarray(hkl, dtype=np.float64)

    F = np.zeros(n_refl, dtype=np.complex128)
    for j in range(sites.n_asym):
        rot, tran = sites.ops[j]
        positions = rot @ xyz[j] + tran  # (m_j, 3)
        geometric = np.exp(2.0j * np.pi * (positions @ h.T)).sum(axis=0)  # (N,)
        dw = np.exp(-biso[j] * k * k)  # exp(−B (sinθ/λ)²)
        F += occ[j] * f0(sites.species[j], k) * dw * geometric
    return (F * F.conj()).real


def d_f2_d_xyz(
    hkl: np.ndarray,
    d: np.ndarray,
    sites: PhaseSites,
    xyz: np.ndarray,
    occ: np.ndarray,
    biso: np.ndarray,
    j: int,
) -> np.ndarray:
    """Analytic ∂|F|²/∂x_j over the frozen op subsets, shape (N, 3).

    With F = Σ_j' A_j'·G_j' (A_j the real occ·f₀·Debye-Waller prefactor) and
    G_j = Σ_m exp(2πi h·(R_m x_j + t_m)),

        ∂F/∂x_jc = A_j · 2πi Σ_m (R_mᵀ h)_c · exp(2πi h·(R_m x_j + t_m))

    — the reciprocal-space action is the **transposed** rotation (see
    ``symmetry.py``) — and ∂|F|²/∂x_jc = 2·Re(F̄ · ∂F/∂x_jc) (structure-
    factor derivatives per Rietveld, 1969, J. Appl. Cryst. 2, 65).  The op
    subsets are the same frozen ``sites.ops`` the forward model uses, so the
    gradient is exact for the model as compiled.
    """
    k = 1.0 / (2.0 * np.asarray(d, dtype=np.float64))
    h = np.asarray(hkl, dtype=np.float64)
    F = np.zeros(len(h), dtype=np.complex128)
    dF = np.zeros((len(h), 3), dtype=np.complex128)
    for jj in range(sites.n_asym):
        rot, tran = sites.ops[jj]
        positions = rot @ xyz[jj] + tran  # (m, 3)
        phase = np.exp(2.0j * np.pi * (positions @ h.T))  # (m, N)
        amp = occ[jj] * f0(sites.species[jj], k) * np.exp(-biso[jj] * k * k)  # (N,)
        F += amp * phase.sum(axis=0)
        if jj == j:
            rth = np.einsum("nk,mkc->mnc", h, rot)  # (R_mᵀ h)_c, shape (m, N, 3)
            dF = amp[:, None] * (2.0j * np.pi) * (phase[:, :, None] * rth).sum(axis=0)
    return 2.0 * (np.conj(F)[:, None] * dF).real

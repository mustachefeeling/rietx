"""Geometrical ambiguity — enumerated and **reported, never resolved**.

A powder pattern carries only the *length* of each reciprocal vector, so distinct
lattices can produce calculated patterns with identical line positions (Mighell,
A. D. & Santoro, A. (1975), *J. Appl. Cryst.* **8**, 372-374).  No amount of
counting statistics separates them: the information is absent from the
measurement, not buried in noise.  This module therefore does three things and
stops.

1. **Enumerate** the derivative lattices of index 2-4 exactly, as integer
   matrices in Hermite normal form.  The closed sets have 7, 13 and 35 members —
   which is a *self-check*, not a comment: :func:`hnf_matrices` reproduces those
   counts in ``tests/test_indexing_reduce.py``, so an enumeration bug shows up as
   a count mismatch rather than as a silently missing partner.
2. **Test** each against the observed lines, and keep only those that explain
   them as well as the parent does.  A derivative lattice that predicts extra
   lines *where lines were observed to be absent* is excluded by the data; one
   whose extra lines fall outside the measured range, or wherever nothing was
   looked for, is not — and that distinction is the whole content of the report.
3. **Say what would break the tie.**  ``discriminating_reflections`` carries the
   hkl and the 2θ where the partner and the parent differ, so the report is
   actionable rather than merely honest — the structural twin of Layer 2's
   "extend the fit range".

A setting change is *not* an ambiguity: derivative lattices that Niggli-reduce to
the parent are dropped, which is what keeps this question distinct from dedup
(``reduce.same_lattice``).
"""

from __future__ import annotations

from itertools import product

import numpy as np

from ..schemas.indexing import AmbiguityPartner
from .fom import match_lines, predicted_lines
from .reduce import reduce_cell, same_lattice

#: Highest derivative-lattice index enumerated.  A fence, recorded rather than
#: attempted: the HNF count grows (7, 13, 35 at index 2, 3, 4) and so does the
#: chance that a high-index partner is a numerical coincidence rather than a
#: geometrical one.  Mighell & Santoro's tabulated cases are low-index.
MAX_AMBIGUITY_INDEX = 4
#: How much worse a partner's mean |ΔQ| may be than the parent's and still count
#: as explaining the data equally well.  Not a statistical threshold — it is a
#: deliberately *permissive* screen, because the cost of reporting a partner that
#: is in fact distinguishable is a caller checking one extra reflection, while the
#: cost of missing one is a cell quoted with a confidence it has not earned.
AMBIGUITY_DISCREPANCY_SLACK = 1.5
#: Most discriminating reflections listed per partner.  The strongest evidence is
#: at low angle (where lines are sparse and well resolved), so the list is the
#: lowest-2θ differences rather than a sample.
MAX_DISCRIMINATING = 6


def hnf_matrices(index: int) -> list[np.ndarray]:
    """Every sublattice of Z³ of the given index, as an upper-triangular HNF.

        H = [[a, b, c], [0, d, e], [0, 0, f]],  a·d·f = index,
        0 ≤ b < d,  0 ≤ c < f,  0 ≤ e < f

    which enumerates each sublattice exactly once (Hermite normal form is
    canonical).  Counts: 7, 13, 35 for index 2, 3, 4.
    """
    if index < 1:
        raise ValueError("index must be a positive integer")
    out: list[np.ndarray] = []
    for a in range(1, index + 1):
        if index % a:
            continue
        rest = index // a
        for d in range(1, rest + 1):
            if rest % d:
                continue
            f = rest // d
            for b, c, e in product(range(d), range(f), range(f)):
                out.append(np.array([[a, b, c], [0, d, e], [0, 0, f]],
                                    dtype=np.int64))
    return out


def transform_cell(cell: tuple[float, ...], matrix: np.ndarray
                   ) -> tuple[float, float, float, float, float, float]:
    """The cell of the lattice whose basis is ``matrix @ basis``.

    Works on the metric rather than on cell parameters: G' = H·G·Hᵀ, which is
    exact for any integer H and needs no Cartesian realisation of the basis.
    """
    from ..crystallography.lattice import direct_metric_tensor
    from .qspace import af_from_gstar, cell_from_af

    g = np.asarray(direct_metric_tensor(*cell), dtype=np.float64)
    h = np.asarray(matrix, dtype=np.float64)
    g_new = h @ g @ h.T
    return cell_from_af(af_from_gstar(np.linalg.inv(g_new)))


def derivative_cells(cell: tuple[float, ...], *,
                     max_index: int = MAX_AMBIGUITY_INDEX):
    """(index, H, cell) for every derivative lattice that is not the parent.

    Both directions are generated: ``H`` gives a **superlattice** in direct space
    (a larger cell, denser reciprocal lattice) and its inverse-transpose analogue
    the **sublattice**.  Only the direct-space superlattices are enumerated here
    and the sublattice case is reached by running the same enumeration from the
    partner's point of view, which is what an engine does when it proposes both.
    Partners reducing to the parent are dropped — that is a setting change, i.e.
    dedup's business, not ambiguity's.
    """
    from .qspace import af_from_cell

    parent_af = af_from_cell(cell)
    out = []
    for index in range(2, max_index + 1):
        for h in hnf_matrices(index):
            try:
                child = transform_cell(cell, h)
            except (ValueError, np.linalg.LinAlgError):
                continue
            equal, _ = same_lattice(parent_af, af_from_cell(child))
            if equal:
                continue
            out.append((index, h, child))
    return out


def ambiguity_partners(cell: tuple[float, ...], system: str, centring: str,
                       q_obs: np.ndarray, q_esd: np.ndarray, wavelength: float,
                       two_theta_max: float, *,
                       max_index: int = MAX_AMBIGUITY_INDEX,
                       ) -> list[AmbiguityPartner]:
    """Derivative lattices this data cannot distinguish from ``cell``.

    The test is empirical rather than taxonomic: a partner is reported when it
    indexes at least as many observed lines as the parent with a mean discrepancy
    no more than :data:`AMBIGUITY_DISCREPANCY_SLACK` times worse.  What makes the
    entry useful is ``discriminating_reflections`` — the lowest-angle positions
    where the two lattices differ, with the 2θ a line would have to appear at (or
    be absent from) to settle it.
    """
    from ..crystallography.lattice import cell_volume

    obs = np.asarray(q_obs, dtype=np.float64)
    esd = np.asarray(q_esd, dtype=np.float64)
    _hkl, q_parent = predicted_lines(cell, system, centring, wavelength,
                                     two_theta_max)
    idx_parent, dq_parent = match_lines(obs, esd, q_parent)
    n_parent = int(np.count_nonzero(idx_parent >= 0))
    base = dq_parent[np.isfinite(dq_parent)]
    mean_parent = float(np.mean(base)) if len(base) else float("inf")

    out: list[AmbiguityPartner] = []
    for index, h, child in derivative_cells(cell, max_index=max_index):
        try:
            hkl_c, q_child = predicted_lines(child, "triclinic", "P", wavelength,
                                             two_theta_max)
        except (ValueError, RuntimeError):
            continue
        idx_c, dq_c = match_lines(obs, esd, q_child)
        n_child = int(np.count_nonzero(idx_c >= 0))
        finite = dq_c[np.isfinite(dq_c)]
        mean_child = float(np.mean(finite)) if len(finite) else float("inf")
        if n_child < n_parent:
            continue
        if not (mean_child <= AMBIGUITY_DISCREPANCY_SLACK * max(mean_parent,
                                                                1e-300)):
            continue
        refl, tt = _discriminating(q_parent, hkl_c, q_child, esd, wavelength)
        out.append(AmbiguityPartner(
            cell=child, transformation=[[int(v) for v in row] for row in h],
            index=index, system="triclinic",
            volume=float(cell_volume(*child)),
            discriminating_reflections=refl, discriminating_two_theta=tt))
    return out


def _discriminating(q_parent: np.ndarray, hkl_child: np.ndarray,
                    q_child: np.ndarray, q_esd: np.ndarray, wavelength: float):
    """The partner's predictions the parent does not share, lowest angle first.

    Tolerance is the *median* observed σ(Q): a difference smaller than the data's
    own precision would not settle anything, so it is not evidence and does not
    belong in a list of things to go and look at.
    """
    tol = float(np.median(q_esd)) if len(q_esd) else 0.0
    if not len(q_parent):
        keep = np.ones(len(q_child), dtype=bool)
    else:
        d = np.min(np.abs(q_child[:, None] - q_parent[None, :]), axis=1)
        keep = d > max(tol, 1e-12)
    order = np.argsort(q_child[keep])[:MAX_DISCRIMINATING]
    hkl_keep = np.asarray(hkl_child)[keep][order]
    q_keep = q_child[keep][order]
    tt = np.degrees(2.0 * np.arcsin(np.clip(wavelength * np.sqrt(q_keep) / 2.0,
                                            -1.0, 1.0)))
    return ([tuple(int(v) for v in row) for row in hkl_keep],
            [float(v) for v in tt])


__all__ = ["AMBIGUITY_DISCREPANCY_SLACK", "MAX_AMBIGUITY_INDEX",
           "MAX_DISCRIMINATING", "ambiguity_partners", "derivative_cells",
           "hnf_matrices", "reduce_cell", "transform_cell"]

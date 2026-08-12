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

**Step 2's exclusion was stated here from the start and not implemented until
WP-1024, and the gap was not cosmetic.**  A superlattice's reciprocal lattice
strictly *contains* the parent's, so it indexes every observed line exactly and
ties the parent on every forward-looking figure — which meant the original screen
(compare ``n_indexed``, compare the mean discrepancy) reported **every** derivative
lattice as a partner: measured, 28 partners for a certified cubic cell on exact
synthetic positions, 20-35 across systems.  The consequence is one rank up: WP-1024's
confidence gate refuses ``high`` to any candidate with an ambiguity partner, so the
indexer could never have answered at all.  And the answer was already in the
docstring — a doubled cubic cell predicts lines at half the parent's d-spacings,
those lines are *not there*, and their absence is data.  ``predicted_seen_fraction``
exists one module over for exactly this reason; this is the same measurement asked
about one lattice instead of a ranking.

The exclusion is **asymmetric on purpose** and the asymmetry is what makes it
sound: it tests the partner's *extra* predictions, never the parent's own absent
ones.  A correct lattice routinely predicts reflections nothing is observed at
(space-group extinctions, not yet determined while indexing runs, and lines too weak to
detect — the truth showed 56.5 % of its own predicted lines in this repo's §D
data), so a symmetric rule would exclude the truth first.  What the data can rule
out is a line a *rival* lattice needs and the parent does not.

**Why excluding a supercell is crystallography and not convenience.**  A 2a cell
whose odd reflections are *identically* zero is not a lattice statement at all: a
structure with no superlattice intensity has the a-translation, so the lattice
*is* the a-lattice and the 2a cell is a cell choice.  Indexing determines the
lattice, so the small cell is the answer and the supercell is not a rival
hypothesis about it.  What this exclusion genuinely gets wrong is the *weak*
case — a partially-ordered superstructure whose superlattice reflections are
non-zero but below the peak picker's detection floor.  That case is not lost,
it moves: the whole-profile Le Bail validation (WP-1024's
``predicted_but_absent``) asks the same question of the **pattern** rather than of
the peak list, where a line an order below the detection threshold still shows,
and ``discriminating_reflections`` says where to count longer.  Read a partner
list, therefore, as "positions alone cannot separate these", never as "no
supercell is possible".
"""

from __future__ import annotations

from itertools import product

import numpy as np

from ..schemas.indexing import AmbiguityPartner, q_of_two_theta
from .fom import MATCH_SIGMA, match_lines, predicted_lines
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
#: Permissive is safe **because the absence test is not**: this comparison decides
#: whether a partner explains the observed lines, and
#: :func:`extras_absent_in_range` decides whether the data refute it.  Before that
#: second test existed this slack was the only screen, and a screen that a
#: superlattice passes by construction is not one.
AMBIGUITY_DISCREPANCY_SLACK = 1.5
#: Most discriminating reflections listed per partner.  The strongest evidence is
#: at low angle (where lines are sparse and well resolved), so the list is the
#: lowest-2θ differences rather than a sample.
MAX_DISCRIMINATING = 6
#: How far past the measured 2θ range a partner's reflections are predicted, as a
#: factor on ``two_theta_max``.  Needed because a *surviving* partner is by
#: definition one whose extra lines inside the range all coincide with observed
#: ones — so its discriminating reflections lie **outside** the range, and
#: predicting only as far as the data reach would leave every ambiguity report
#: with nothing actionable in it.  1.5 rather than the physical limit (2θ → 180°)
#: because "collect 50 % further" is advice a diffractometer can take, and the
#: reflections just past the edge are the cheapest ones to go and look for.
AMBIGUITY_EXTEND_FACTOR = 1.5


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


def extras_absent_in_range(q_extra: np.ndarray, q_obs: np.ndarray,
                           q_esd: np.ndarray, q_lo: float, q_hi: float, *,
                           k_sigma: float = MATCH_SIGMA) -> int:
    """How many of a partner's **extra** predictions land in the measured range
    with no observed line there.

    Any one of them excludes the partner: it needs a reflection the pattern
    demonstrably does not have.  The window is the *observed* line's own σ, the
    same reversal :func:`~anatase.indexing.fom.predicted_seen_fraction` makes —
    the precision belongs to the measurement, so it stays attached to the
    observation even when the loop runs the other way.
    """
    extra = np.asarray(q_extra, dtype=np.float64)
    inside = extra[(extra >= q_lo) & (extra <= q_hi)]
    if not len(inside):
        return 0
    obs = np.asarray(q_obs, dtype=np.float64)
    if not len(obs):
        return int(len(inside))
    sig = np.maximum(np.asarray(q_esd, dtype=np.float64), 1e-300)
    d = np.abs(inside[:, None] - obs[None, :])
    j = np.argmin(d, axis=1)
    seen = d[np.arange(len(inside)), j] <= k_sigma * sig[j]
    return int(np.count_nonzero(~seen))


def ambiguity_partners(cell: tuple[float, ...], system: str, centring: str,
                       q_obs: np.ndarray, q_esd: np.ndarray, wavelength: float,
                       two_theta_max: float, *,
                       two_theta_min: float = 0.0,
                       max_index: int = MAX_AMBIGUITY_INDEX,
                       k_sigma: float = MATCH_SIGMA,
                       ) -> list[AmbiguityPartner]:
    """Derivative lattices this data cannot distinguish from ``cell``.

    The test is empirical rather than taxonomic, and it is two-sided:

    * the partner must **explain** the observed lines at least as well as the
      parent — at least as many indexed, a mean discrepancy no more than
      :data:`AMBIGUITY_DISCREPANCY_SLACK` times worse;
    * and the data must not **refute** it — a single extra prediction inside the
      measured 2θ range with no observed line at it (:func:`extras_absent_in_range`)
      drops the partner, because that is a reflection the pattern says is not
      there.

    Only the second half distinguishes a genuine geometrical ambiguity from an
    ordinary supercell (see the module docstring for what happened without it).

    What makes a surviving entry useful is ``discriminating_reflections`` — and
    note where they now are: a partner that survived has no absent extras *inside*
    the range, so the lines that would settle it lie **outside** it, up to
    :data:`AMBIGUITY_EXTEND_FACTOR`·``two_theta_max`` (or below
    ``two_theta_min``).  The report is therefore literally "collect here and
    look", the structural twin of Layer 2's "extend the fit range".
    """
    from ..crystallography.lattice import cell_volume

    obs = np.asarray(q_obs, dtype=np.float64)
    esd = np.asarray(q_esd, dtype=np.float64)
    tt_ext = min(float(two_theta_max) * AMBIGUITY_EXTEND_FACTOR, 179.0)
    q_lo = float(q_of_two_theta(np.array([max(two_theta_min, 0.0)]),
                                wavelength)[0])
    q_hi = float(q_of_two_theta(np.array([two_theta_max]), wavelength)[0])
    _hkl, q_parent = predicted_lines(cell, system, centring, wavelength, tt_ext)
    q_parent_in = q_parent[q_parent <= q_hi]
    idx_parent, dq_parent = match_lines(obs, esd, q_parent_in)
    n_parent = int(np.count_nonzero(idx_parent >= 0))
    base = dq_parent[np.isfinite(dq_parent)]
    mean_parent = float(np.mean(base)) if len(base) else float("inf")
    tol = float(np.median(esd)) if len(esd) else 0.0

    out: list[AmbiguityPartner] = []
    for index, h, child in derivative_cells(cell, max_index=max_index):
        try:
            hkl_c, q_child = predicted_lines(child, "triclinic", "P", wavelength,
                                             tt_ext)
        except (ValueError, RuntimeError):
            continue
        in_range = q_child <= q_hi
        idx_c, dq_c = match_lines(obs, esd, q_child[in_range])
        n_child = int(np.count_nonzero(idx_c >= 0))
        finite = dq_c[np.isfinite(dq_c)]
        mean_child = float(np.mean(finite)) if len(finite) else float("inf")
        if n_child < n_parent:
            continue
        # Floored at the median σ(Q), exactly as ``m20`` floors its ⟨ΔQ⟩ and for
        # the same reason: a discrepancy below the measurement precision is not
        # knowable.  Without the floor this comparison is a ratio of fp noise on
        # exact positions (both means ~1e-16), so which partner survives depends
        # on summation order rather than on the data.
        if not (mean_child <= AMBIGUITY_DISCREPANCY_SLACK * max(mean_parent,
                                                                tol, 1e-300)):
            continue
        extra = _extra_mask(q_child, q_parent, tol)
        if extras_absent_in_range(q_child[extra], obs, esd, q_lo, q_hi,
                                  k_sigma=k_sigma):
            continue                      # refuted by the absent reflections
        refl, tt = _discriminating(hkl_c[extra], q_child[extra], q_lo, q_hi,
                                   wavelength)
        out.append(AmbiguityPartner(
            cell=child, transformation=[[int(v) for v in row] for row in h],
            index=index, system="triclinic",
            volume=float(cell_volume(*child)),
            discriminating_reflections=refl, discriminating_two_theta=tt))
    return out


def _extra_mask(q_child: np.ndarray, q_parent: np.ndarray,
                tol: float) -> np.ndarray:
    """Which of the partner's predictions the parent does not share.

    Tolerance is the *median* observed σ(Q): a difference smaller than the data's
    own precision would not settle anything, so a prediction that close to a
    parent line is the same line and not an extra.
    """
    if not len(q_parent):
        return np.ones(len(q_child), dtype=bool)
    d = np.min(np.abs(q_child[:, None] - q_parent[None, :]), axis=1)
    return d > max(tol, 1e-12)


def _discriminating(hkl_extra: np.ndarray, q_extra: np.ndarray, q_lo: float,
                    q_hi: float, wavelength: float):
    """The partner's extra predictions **outside** the measured range, nearest
    edge first.

    Inside the range there are none to report — an extra in range with nothing
    observed at it already excluded the partner, and one *with* a line at it is
    not discriminating.  So this is the "measure further" list, ordered by how far
    the diffractometer would have to go: the reflections just past the edge are
    the cheapest evidence, exactly as the lowest-angle ones were before the
    exclusion moved the question outward.
    """
    outside = (q_extra < q_lo) | (q_extra > q_hi)
    hkl_keep, q_keep = np.asarray(hkl_extra)[outside], q_extra[outside]
    # distance past whichever edge it sits beyond, in Q — a total order over both
    # directions, so a low-angle partner line is not ranked behind every
    # high-angle one merely because Q is small there
    beyond = np.where(q_keep > q_hi, q_keep - q_hi, q_lo - q_keep)
    order = np.argsort(beyond)[:MAX_DISCRIMINATING]
    hkl_keep, q_keep = hkl_keep[order], q_keep[order]
    tt = np.degrees(2.0 * np.arcsin(np.clip(wavelength * np.sqrt(q_keep) / 2.0,
                                            -1.0, 1.0)))
    return ([tuple(int(v) for v in row) for row in hkl_keep],
            [float(v) for v in tt])


__all__ = ["AMBIGUITY_DISCREPANCY_SLACK", "AMBIGUITY_EXTEND_FACTOR",
           "MAX_AMBIGUITY_INDEX",
           "MAX_DISCRIMINATING", "ambiguity_partners", "derivative_cells",
           "extras_absent_in_range",
           "hnf_matrices", "reduce_cell", "transform_cell"]

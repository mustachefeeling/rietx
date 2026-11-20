"""The k-search: K1a's grid ranked against its own null, with a gated verdict (WP-1418 M-8, K1b).

:mod:`rietx.indexing.kvector` gives every step of a propagation-vector search as a
call that ranks nothing.  :func:`search_kvector` composes those calls with the
defaults a search needs and answers with a :class:`KSearchResult`: every grid k
**ranked** by its local chance score, the per-pattern shuffle null measured over
exactly the strata searched, and two warnings.  It is K1a's machinery and
nothing else: every number here is read off a public K1a record.

**The result has no** ``k`` **and no** ``best``.  As
:class:`~rietx.schemas.indexing.IndexingResult` does for a cell, it carries a
gated :meth:`KSearchResult.best_or_none`, which returns the top row only when

* its score clears the null's ``percentile``-th percentile by
  :data:`K_SEARCH_MARGIN_DECADES`, and
* no **partner tie** holds: no row scoring within that margin of the top lies
  within :data:`K_SEARCH_PARTNER_STEPS` grid steps of an image of the top k
  under a near-symmetry of the metric (``K_SEARCH_PARTNER``, from
  :func:`~rietx.indexing.kvector.kvector_equivalents` at
  :data:`K_SEARCH_PARTNER_TOL`), counting only rows outside the top k's own
  neighbourhood of that many steps.  Positions alone cannot say which of two
  such k the peaks belong to (Mighell, A. D. & Santoro, A. (1975), *J. Appl.
  Cryst.* **8**, 372-374, one rank over: the geometrical ambiguity of a cell).

**Neither warning refuses.**  ``K_SEARCH_AT_CHANCE`` fires when the top score is
within the margin of the null; ``K_SEARCH_FEW_PEAKS`` fires when the list holds
fewer peaks than :func:`k_search_floor` asks for the strata searched at the
radius used.  The ranked list is returned and printed as hypotheses either way:
a caller who knows k from elsewhere still gets the scores.

**Measured on one family, untested beyond it.**  The margin, the floor and the
partner neighbourhood were measured on synthetic CW-neutron patterns (Pnma,
5.74 × 7.70 × 5.54 Å, λ 2.41 Å, 10-140° 2θ, a 0.12° match radius; issue #795 and
WP-1418's K1a and K1b handovers).  No other family, instrument or radius has
been measured.

**The default strata order** is K1a's listing order, points, then lines, then
planes, then the general stratum, after Wills, A. S. (2009), *Z. Kristallogr.
Suppl.* **30**, 39-44, § 3.1, which searches special points before lines before
planes so that a high-symmetry k is not read as a lower-symmetry one.  That is
all this module takes from Wills: the paper tests each trial k by refining
moment orientations against the full profile and gives no statistic,
threshold, grid step or peak floor; the score here is a position chance score
(de Wolff, P. M. (1968), *J. Appl. Cryst.* **1**, 108-113, for the chance rate
it descends from).  Rows of equal score keep that order, so a point outranks a
general k it ties.

Clean room: the literature above and our own design spikes only (issue #795).
No other program's source was read.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from functools import lru_cache

import numpy as np

from ..crystallography.representation.irreps import K_MAX_DENOMINATOR, KVector
from ..crystallography.satellites import (
    format_kvector,
    lattice_two_theta,
    reciprocal_lattice_mask,
)
from ..crystallography.symmetry import get_spacegroup
from ..report.schemas import VALIDITY_RADIUS_FWHM
from ..schemas.common import Diagnostic
from .engines import DEFAULT_SEARCH_PRESET, SEARCH_PRESETS, Budget, Deadline
from .kvector import (
    KEquivalents,
    KGridPositions,
    KGridRow,
    KNull,
    KParent,
    KPeaks,
    KStratum,
    as_kpeaks,
    kgrid_null,
    kgrid_positions,
    kgrid_strata,
    kvector_equivalents,
    score_kgrid,
)

__all__ = [
    "K_SEARCH_GRID_DENOMINATOR",
    "K_SEARCH_MARGIN_DECADES",
    "K_SEARCH_FLOOR_BASE",
    "K_SEARCH_FLOOR_PER_FREE",
    "K_SEARCH_FLOOR_CONTAMINATION",
    "K_SEARCH_FLOOR_MEASURED",
    "K_SEARCH_PARTNER_TOL",
    "K_SEARCH_PARTNER_STEPS",
    "KSearchResult",
    "k_search_floor",
    "search_kvector",
]

#: The grid's denominator: every k component a multiple of 1/64.  It is
#: :data:`~rietx.crystallography.representation.irreps.K_MAX_DENOMINATOR`, the
#: commensurate door's own bound, with no factor of its own; its use as the
#: search *step* is a choice, which every result reports as ``grid_step``
#: (issue #795, decision 2: no claim about any k off the grid).
K_SEARCH_GRID_DENOMINATOR: int = K_MAX_DENOMINATOR

#: How far, in decades of the chance score, the top row must clear the null's
#: percentile before :meth:`KSearchResult.best_or_none` returns it, and within
#: how much of it ``K_SEARCH_AT_CHANCE`` fires.  One decade: on the synthetic
#: CW-neutron family a planted line k with ten clean peaks clears the 99 %
#: by +4.5 decades on the 1/64 grid, and 100 shuffles place the 99th
#: percentile itself only to about half a decade (WP-1418 K1a handover,
#: follow-up 2).
K_SEARCH_MARGIN_DECADES: float = 1.0

#: The few-peaks floor for one free component of k, on a search restricted to
#: its stratum, at the 0.12° radius (K report § 13.4).
K_SEARCH_FLOOR_BASE: int = 4
#: What each further free component of the strata searched adds to the floor.
K_SEARCH_FLOOR_PER_FREE: int = 2
#: What unmatched (contaminating) peaks beside the top row add to the floor.
K_SEARCH_FLOOR_CONTAMINATION: int = 2

#: The few-peaks floor as **measured** (K report § 13.4, synthetic CW neutrons,
#: Pnma, λ 2.41 Å): (match radius in °, free components of the top row's
#: stratum, the most free components among the strata searched) → (clean,
#: contaminated).  Where a measured cell exists it decides; elsewhere the rule
#: over the three constants above does (:func:`k_search_floor`).  At 0.06° the
#: general row was measured as 4-6 clean, and the upper end is kept.
K_SEARCH_FLOOR_MEASURED: dict[tuple[float, int, int], tuple[int, int]] = {
    (0.12, 1, 1): (4, 6),
    (0.12, 1, 3): (6, 10),
    (0.12, 3, 3): (8, 10),
    (0.06, 1, 1): (4, 6),
    (0.06, 1, 3): (4, 8),
    (0.06, 3, 3): (6, 8),
}

#: The metric tolerance at which the top k's near-symmetric partners are listed
#: for the tie rule.  At 0.08 the x ↔ z image on a 5.74 × 7.70 × 5.54 Å Pnma
#: cell is listed (relative deviation 0.0735) and none on a 5.74 × 7.70 × 6.40 Å
#: one (WP-1418 K1a, V6).
K_SEARCH_PARTNER_TOL: float = 0.08

#: The partner's neighbourhood, in steps of the 1/:data:`K_SEARCH_GRID_DENOMINATOR`
#: grid (Chebyshev, modulo the reciprocal lattice), so a fixed distance in k of
#: 4/64 whatever grid a caller searched: the satellites of a partner's exact image are moved by
#: the metric's deviation, so the grid k matching them best sits a few steps
#: away.  Four: on the pseudo-tetragonal cell above the best grid k within four
#: steps of the image matched 8 of 10 planted peaks where the image matched 2
#: (WP-1418 K1a, V6).
K_SEARCH_PARTNER_STEPS: int = 4

# The 0.06° and 0.12° radii the floor was measured at, split at their
# geometric mean.
_FLOOR_RADII: tuple[float, float] = (0.06, 0.12)


def k_search_floor(n_free_top: int, n_free_searched: int, *, contaminated: bool,
                   radius: float) -> int:
    """How many unexplained peaks a k-search needs to stand above chance.

    ``n_free_top`` is the free components of the hypothesis (the top row's
    stratum), ``n_free_searched`` the most free components among the strata
    searched, ``contaminated`` whether the top row leaves peaks unmatched, and
    ``radius`` the match radius used.

    The measured table :data:`K_SEARCH_FLOOR_MEASURED` decides where it has a
    cell; the radius is read as the nearer of its two (0.06°, 0.12°, split at
    their geometric mean).  Elsewhere the rule: :data:`K_SEARCH_FLOOR_BASE` for
    the first free component of the strata searched plus
    :data:`K_SEARCH_FLOOR_PER_FREE` for each further one, plus
    :data:`K_SEARCH_FLOOR_CONTAMINATION` when contaminated, and two fewer at the
    0.06° radius, never below the base (or below base + contamination when
    contaminated).  The rule and the table disagree on the line-on-the-wedge
    row (rule 8 / 10, measured 6 / 10) and the table wins there.

    Measured on synthetic CW-neutron patterns (Pnma, λ 2.41 Å) at those two
    radii only: a radius above 0.12° or below 0.06° reads the nearer row, and
    neither is tested.  The floor is a prior; the score is the measurement.
    """
    ref = (_FLOOR_RADII[0] if float(radius) <= math.sqrt(_FLOOR_RADII[0] * _FLOOR_RADII[1])
           else _FLOOR_RADII[1])
    top, searched = int(n_free_top), max(int(n_free_searched), int(n_free_top))
    cell = K_SEARCH_FLOOR_MEASURED.get((ref, top, searched))
    if cell is not None:
        return cell[1] if contaminated else cell[0]
    floor = K_SEARCH_FLOOR_BASE + K_SEARCH_FLOOR_PER_FREE * max(searched - 1, 0)
    if contaminated:
        floor += K_SEARCH_FLOOR_CONTAMINATION
    if ref == _FLOOR_RADII[0]:
        floor -= 2
    least = K_SEARCH_FLOOR_BASE + (K_SEARCH_FLOOR_CONTAMINATION if contaminated else 0)
    return max(floor, least)


# --------------------------------------------------------------------------
# the result
# --------------------------------------------------------------------------

@dataclass(frozen=True, repr=False)
class KSearchResult:
    """The ranked k-search (:func:`search_kvector`).  **No** ``k``, **no** ``best``.

    ``rows`` are K1a's :class:`~rietx.indexing.kvector.KGridRow` records,
    sorted by score, highest first; rows of equal score keep the strata order
    (points before lines before planes before the general stratum).  Each row
    is a **hypothesis**: its exact rational k, its stratum, its score
    (−log₁₀ of its own chance probability), the peaks it matches and leaves,
    and its structural ``equivalents``.

    ``null`` is the per-pattern shuffle null over exactly ``strata_searched``
    (one :class:`~rietx.indexing.kvector.KNull`, its sample the grid maximum
    of every shuffle over those strata); ``null_threshold`` its percentile.
    ``radius`` and ``radius_source`` say which match radius scored the rows and
    where it came from (``"caller"``, ``"residual census"`` or
    ``"nuclear lines"``); ``exclude`` the null's exclusion windows.  The grid
    facts are K1a's: ``grid_step``, ``strata_searched``, ``strata_left`` and
    ``coverage``, which claims nothing about any k off the grid.  ``preset``
    is ``"quick"``, ``"full"`` or ``"custom"`` (a caller's own budget).

    ``floor`` is :func:`k_search_floor` for the top row, ``partners`` the top
    k's :func:`~rietx.indexing.kvector.kvector_equivalents` at
    :data:`K_SEARCH_PARTNER_TOL`, and ``partner_tie`` the row that ties the
    top through a partner, or ``None``.  ``diagnostics`` carries
    ``K_SEARCH_AT_CHANCE``, ``K_SEARCH_FEW_PEAKS`` and the partners'
    ``K_SEARCH_PARTNER``.
    """

    parent: KParent
    peaks: KPeaks
    rows: tuple[KGridRow, ...]
    radius: float
    radius_source: str
    band_deg: float
    harmonics: tuple[int, ...]
    null: KNull
    exclude: tuple[tuple[float, float], ...]
    margin_decades: float
    grid_step: float
    strata_searched: tuple[str, ...]
    strata_left: tuple[str, ...]
    coverage: str
    preset: str
    budget_seconds: float | None
    budget_expired: bool
    elapsed_seconds: float
    n_free_searched: int
    floor: int | None
    partners: KEquivalents | None
    partner_tie: KGridRow | None
    diagnostics: tuple[Diagnostic, ...]

    @property
    def null_threshold(self) -> float:
        return self.null.threshold

    @property
    def n_shuffles(self) -> int:
        return self.null.n_shuffles

    @property
    def n_peaks(self) -> int:
        return len(self.peaks)

    @property
    def margin(self) -> float | None:
        """The top score minus the null threshold, in decades (``None`` with no rows)."""
        if not self.rows or not math.isfinite(self.null.threshold):
            return None
        return self.rows[0].score - self.null.threshold

    def best_or_none(self) -> KGridRow | None:
        """The top row, or ``None``.

        Returns ``rows[0]`` only when its score clears ``null_threshold`` by
        ``margin_decades`` and no partner ties it (``partner_tie`` is ``None``,
        definition in the module docstring).  Every other case, at chance or
        tied, returns ``None``; the reason is in :attr:`diagnostics`, and the
        ranked rows stay hypotheses either way.  The margin is re-read here
        rather than from the diagnostics, so this method is the one place the
        rule is guaranteed.
        """
        margin = self.margin
        if margin is None or margin < self.margin_decades:
            return None
        return None if self.partner_tie is not None else self.rows[0]

    def __repr__(self) -> str:
        top = (f"top k = {format_kvector(self.rows[0].k)} at {self.rows[0].score:.2f}"
               if self.rows else "no rows")
        codes = ", ".join(d.code for d in self.diagnostics) or "no diagnostics"
        return (f"KSearchResult(N={self.n_peaks}, {len(self.rows)} rows ranked, {top}; "
                f"null {self.null.percentile:g}% {self.null.threshold:.2f} over "
                f"{self.null.n_shuffles} shuffles; radius {self.radius:.3f}° "
                f"({self.radius_source}); {len(self.strata_searched)} strata searched, "
                f"{len(self.strata_left)} left; {codes})")


# --------------------------------------------------------------------------
# the search
# --------------------------------------------------------------------------

def _median_width(values) -> float | None:
    if values is None:
        return None
    arr = np.asarray([np.nan if v is None else v for v in np.atleast_1d(values)],
                     dtype=np.float64)
    arr = arr[np.isfinite(arr) & (arr > 0)]
    return float(np.median(arr)) if arr.size else None


def _resolve_radius(kp: KPeaks, radius, nuclear_fwhm) -> tuple[float, str]:
    if radius is not None:
        r = float(radius)
        if not (math.isfinite(r) and r > 0):
            raise ValueError(f"radius must be a positive number of degrees, got {radius!r}")
        return r, "caller"
    census = _median_width(kp.fwhm)
    nuclear = _median_width(nuclear_fwhm)
    if census is None and nuclear is None:
        raise ValueError(
            "no width to set the match radius from: pass radius= in ° 2θ, give the peaks "
            "their fitted fwhm (a PeakList carries it), or pass nuclear_fwhm=, the nuclear "
            "lines' FWHM at the peaks")
    if census is not None and (nuclear is None or census >= nuclear):
        return VALIDITY_RADIUS_FWHM * census, "residual census"
    return VALIDITY_RADIUS_FWHM * nuclear, "nuclear lines"


def _resolve_budget(budget) -> tuple[Budget | None, str]:
    if budget is None or isinstance(budget, str):
        name = DEFAULT_SEARCH_PRESET if budget is None else budget
        if name not in SEARCH_PRESETS:
            raise ValueError(f"unknown preset {name!r}; one of {sorted(SEARCH_PRESETS)}, or "
                             "pass a Budget")
        seconds = SEARCH_PRESETS[name]
        return (None if seconds is None else Deadline(seconds)), name
    if isinstance(budget, Budget):
        return budget, "custom"
    raise TypeError(f"budget is None, a preset name or a Budget, got {type(budget).__name__}")


@lru_cache(maxsize=64)
def _lattice_shifts(xhm: str) -> np.ndarray:
    """The reciprocal-lattice vectors with components in [-2, 2]."""
    g = np.array(np.meshgrid(*[np.arange(-2, 3)] * 3, indexing="ij")).reshape(3, -1).T
    return g[reciprocal_lattice_mask(get_spacegroup(xhm), g)].astype(np.float64)


def _steps_apart(xhm: str, a: Sequence[KVector], b: KVector, n: int) -> float:
    """Fewest grid steps (Chebyshev, modulo L*) from any k in ``a`` to ``b``."""
    shifts = _lattice_shifts(xhm)
    bb = np.array([float(c) for c in b])
    best = math.inf
    for k in a:
        d = np.array([float(c) for c in k]) - bb
        best = min(best, float(np.min(np.max(np.abs(d[None, :] - shifts), axis=1))) * n)
    return best


def _partner_tie(parent: KParent, rows: tuple[KGridRow, ...], partners: KEquivalents,
                 margin: float, n: int) -> KGridRow | None:
    top = rows[0]
    images = [e.k for e in partners.rows if e.relation == "partner"]
    if not images:
        return None
    xhm = parent.space_group
    own = top.equivalents
    for row in rows[1:]:
        if row.score < top.score - margin:
            break
        if _steps_apart(xhm, row.equivalents, top.k, n) <= K_SEARCH_PARTNER_STEPS:
            continue
        if any(_steps_apart(xhm, row.equivalents, img, n) <= K_SEARCH_PARTNER_STEPS
               and _steps_apart(xhm, own, img, n) > K_SEARCH_PARTNER_STEPS
               for img in images):
            return row
    return None


def search_kvector(peaks, parent: KParent, radius: float | None = None,
                   harmonics: Sequence[int] = (1,), budget=None, *,
                   nuclear_fwhm=None,
                   strata: Sequence[KStratum] | KGridPositions | None = None,
                   exclude=None,
                   band_deg: float = 5.0,
                   n_shuffles: int = 100,
                   percentile: float = 99.0,
                   seed: int = 20261112) -> KSearchResult:
    """Rank every k of the grid against ``peaks`` and judge the top against chance.

    ``peaks`` are the unexplained peaks (positions in ° 2θ, a
    :class:`~rietx.indexing.kvector.KPeaks` or a ``PeakList``); which peaks
    are unexplained is the caller's sort, never this function's.  ``parent``
    is the known parent.

    Defaults, each recorded on the result:

    * ``radius=None``: :data:`~rietx.report.schemas.VALIDITY_RADIUS_FWHM` ×
      the median FWHM the peaks themselves carry (the residual census), floored
      at the median of ``nuclear_fwhm`` (the nuclear lines' FWHM at the peaks,
      a number or one per peak) when given; ``radius_source`` says which
      bound.  A radius read off the nuclear lines alone drops broad satellites
      into "unmatched"; one read off the census under-reads where sharp
      impurity lines sit beside broad satellites, so pass ``radius=`` there.
      With no width anywhere it raises.
    * ``strata=None``: every stratum of the 1/:data:`K_SEARCH_GRID_DENOMINATOR`
      grid in K1a's order (points, lines, planes, general; Wills 2009 § 3.1);
      a sequence of :class:`~rietx.indexing.kvector.KStratum` or a
      :class:`~rietx.indexing.kvector.KGridPositions` built from them is
      searched in its own order (the second skips the position build).
    * ``exclude=None``: the null's exclusion windows are the parent's nuclear
      lines (:func:`~rietx.crystallography.satellites.lattice_two_theta`) at ±
      the radius used.
    * ``budget=None``: the indexing package's ``"quick"`` preset, a whole-run
      :class:`~rietx.indexing.engines.Deadline` of
      ``SEARCH_PRESETS["quick"]`` seconds; ``"full"`` is unbounded and a
      :class:`~rietx.indexing.engines.Budget` is the caller's.  It is read
      between strata, so a binding budget cuts trailing strata from the scores
      and the null alike, and ``strata_left`` names them.
    * ``band_deg=5.0``, ``n_shuffles=100``, ``percentile=99.0``,
      ``seed=20261112``: the local score's band and the null's size,
      percentile and seed, the values the design measured.  The same seed
      gives the same shuffles whatever strata are searched.

    Each stratum is scored (:func:`~rietx.indexing.kvector.score_kgrid`) and
    shuffled (:func:`~rietx.indexing.kvector.kgrid_null`) from one position
    build, and the null's sample is the per-shuffle maximum over the strata
    searched, so the scores and their null always cover the same grid.

    Two warnings, neither of which refuses (module docstring):
    ``K_SEARCH_AT_CHANCE`` and ``K_SEARCH_FEW_PEAKS``.  Their thresholds were
    measured on synthetic CW-neutron patterns (Pnma, λ 2.41 Å) and are
    untested beyond them.
    """
    kp = as_kpeaks(peaks)
    r, source = _resolve_radius(kp, radius, nuclear_fwhm)
    deadline, preset = _resolve_budget(budget)
    if strata is None:
        strata = kgrid_strata(parent.space_group, denominator=K_SEARCH_GRID_DENOMINATOR)
    built = strata if isinstance(strata, KGridPositions) else None
    strata_ = tuple(built.strata if built is not None else strata)
    if not strata_:
        raise ValueError("no strata given: pass the strata to search, or None for the grid")
    orders = tuple(built.harmonics) if built is not None else tuple(harmonics)
    if exclude is None:
        nuclear = lattice_two_theta(parent.group, parent.cell, parent.wavelength,
                                    parent.two_theta_max, parent.two_theta_min)
        exclude = [(float(x), r) for x in nuclear]

    rows: list[KGridRow] = []
    nulls: list[KNull] = []
    searched: list[KStratum] = []
    left: list[str] = []
    elapsed = 0.0
    for i, st in enumerate(strata_):
        if deadline is not None and deadline.expired():
            left.extend(s.name for s in strata_[i:])
            break
        if built is not None:
            src = KGridPositions(parent=parent, strata=(st,), harmonics=built.harmonics,
                                 positions=(built.positions[i],), build_seconds=0.0)
        else:
            src = kgrid_positions(parent, (st,), harmonics=orders)
            elapsed += src.build_seconds
        grid = score_kgrid(kp, parent, src, radius=r, band_deg=band_deg, harmonics=orders)
        nul = kgrid_null(kp, parent, src, radius=r, band_deg=band_deg, exclude=exclude,
                         n_shuffles=n_shuffles, percentile=percentile, seed=seed,
                         harmonics=orders)
        elapsed += grid.elapsed_seconds + nul.elapsed_seconds
        rows.extend(grid.rows)
        nulls.append(nul)
        searched.append(st)

    null = _combined_null(nulls, searched, left, deadline, elapsed)
    ranked = tuple(sorted(rows, key=lambda row: -row.score))
    n_free_searched = max((s.n_free for s in searched), default=0)
    by_name = {s.name: s for s in strata_}

    diags: list[Diagnostic] = []
    floor = partners = tie = None
    if ranked:
        top = ranked[0]
        n_free_top = by_name[top.stratum].n_free
        floor = k_search_floor(n_free_top, n_free_searched, contaminated=bool(top.unmatched),
                               radius=r)
        partners = kvector_equivalents(parent, top.k, tol=K_SEARCH_PARTNER_TOL)
        tie = _partner_tie(parent, ranked, partners, K_SEARCH_MARGIN_DECADES,
                           K_SEARCH_GRID_DENOMINATOR)
        if top.score < null.threshold + K_SEARCH_MARGIN_DECADES:
            diags.append(Diagnostic(
                level="warning", code="K_SEARCH_AT_CHANCE",
                message=(f"The best propagation vector, k = {format_kvector(top.k)}, scores "
                         f"{top.score:.1f} decades against a chance level of "
                         f"{null.threshold:.1f} measured by shuffling these {len(kp)} peaks: "
                         "nothing in this list is established by positions."),
                where=[f"k = {format_kvector(top.k)}"],
                suggestion=("Treat every row as a hypothesis for a moment or modulation "
                            "model; add peaks (longer counting, a paired pattern, a "
                            "temperature series) or state k from elsewhere."),
                value=top.score - null.threshold))
        if len(kp) < floor:
            diags.append(Diagnostic(
                level="warning", code="K_SEARCH_FEW_PEAKS",
                message=(f"The k-search ran on {len(kp)} unexplained peaks. At this "
                         f"resolution (match radius {r:.2f}°) a propagation vector with "
                         f"{n_free_top} free components needs about {floor} peaks to stand "
                         "above chance (measured on synthetic CW-neutron patterns: 4 for a "
                         "symmetry line with the stratum known, 8 for a general k, two more "
                         "with contaminating peaks). The ranked list is a set of hypotheses; "
                         "the top row is not evidence of magnetic or modulated order."),
                where=[f"k = {format_kvector(top.k)}"],
                value=float(len(kp))))
        diags.extend(partners.diagnostics)

    return KSearchResult(
        parent=parent, peaks=kp, rows=ranked, radius=r, radius_source=source,
        band_deg=float(band_deg), harmonics=null.harmonics, null=null,
        exclude=null.exclude, margin_decades=K_SEARCH_MARGIN_DECADES,
        grid_step=null.grid_step, strata_searched=null.strata_searched,
        strata_left=null.strata_left, coverage=null.coverage, preset=preset,
        budget_seconds=null.budget_seconds, budget_expired=null.budget_expired,
        elapsed_seconds=elapsed, n_free_searched=n_free_searched, floor=floor,
        partners=partners, partner_tie=tie, diagnostics=tuple(diags))


def _coverage_text(searched: list[KStratum], left: list[str]) -> str:
    dens = sorted({s.denominator for s in searched})
    grid = " and ".join(f"1/{d}" for d in dens)
    return (f"rational k on the {grid} grid (step {max(1.0 / d for d in dens):.4g} in "
            f"conventional reciprocal coordinates) in {len(searched)} stratum(s) searched; "
            f"{len(left)} stratum(s) left unsearched. No claim is made about any k off this "
            "grid: a general or incommensurate k between grid points was not searched.")


def _combined_null(nulls: list[KNull], searched: list[KStratum], left: list[str], deadline,
                   elapsed: float) -> KNull:
    """One :class:`KNull` over every stratum searched: the per-shuffle maximum.

    Every per-stratum null drew the same shuffles (same seed, peak count and
    exclusions), so the elementwise maximum of their samples is the grid
    maximum of each shuffle over the strata searched, and the count of the k
    reaching it comes from the first stratum, in search order, that set it.
    """
    if not nulls:
        raise RuntimeError("the budget had expired before the first stratum, so nothing was "
                           "searched; pass a budget that has not run out")
    first = nulls[0]
    best = np.array(first.sample, dtype=np.float64)
    at_best = np.array(first.matched_at_max, dtype=np.int64)
    most = np.array(first.max_matched, dtype=np.int64)
    for nul in nulls[1:]:
        if nul.shuffles != first.shuffles:
            raise RuntimeError("the per-stratum nulls drew different shuffles")
        s = np.array(nul.sample, dtype=np.float64)
        up = s > best
        best = np.where(up, s, best)
        at_best = np.where(up, np.array(nul.matched_at_max, dtype=np.int64), at_best)
        most = np.maximum(most, np.array(nul.max_matched, dtype=np.int64))
    threshold = float(np.percentile(best, first.percentile))
    names = [s.name for s in searched]
    return KNull(
        parent=first.parent, n_peaks=first.n_peaks, radius=first.radius,
        band_deg=first.band_deg, harmonics=first.harmonics, exclude=first.exclude,
        seed=first.seed, n_shuffles=first.n_shuffles, percentile=first.percentile,
        threshold=threshold, sample=tuple(float(x) for x in best),
        matched_at_max=tuple(int(x) for x in at_best),
        max_matched=tuple(int(x) for x in most), shuffles=first.shuffles,
        grid_step=max(s.grid_step for s in searched),
        denominators=tuple(s.denominator for s in searched),
        strata_searched=tuple(names), strata_left=tuple(left),
        coverage=_coverage_text(searched, left),
        budget_seconds=None if deadline is None else float(deadline.seconds),
        budget_expired=bool(left), elapsed_seconds=elapsed)

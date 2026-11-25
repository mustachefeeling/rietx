"""The k-search: K1a's grid ranked against Boole's bound, from peak positions (WP-1418 M-8, K1b).

:mod:`rietx.indexing.kvector` gives every step of a propagation-vector search as a
call that ranks nothing.  :func:`search_kvector` composes those calls with the
defaults a search needs and answers with a :class:`KSearchResult`: every grid k
**ranked** by its family-wise adjusted chance probability, the chance level of
:func:`~rietx.indexing.kvector.kgrid_bound` at ``alpha``, a crowding statistic, and
the warnings.  Every number here is read off a public K1a record or computed from
the peaks and the windows.

**The result has no** ``k`` **and no** ``best``, **and** :meth:`KSearchResult.best_or_none`
**returns** ``None`` **for every search here.**  The search ranks k from peak
positions alone, and a k is confirmed by refinement: a moment or modulation model
refined against the whole profile tests one trial k at a time (Wills, A. S. (2009),
*Z. Kristallogr. Suppl.* **30**, 39-44, § 3.2).  Indexing holds an unvalidated
cell the same way (``not_validated``,
:meth:`~rietx.schemas.indexing.IndexingResult.best_or_none`).  The reasons are on
:attr:`KSearchResult.withheld`, a field rather than a diagnostic, since they hold
on every call.  ``None`` here is not "no k": read :attr:`KSearchResult.withheld`,
the rows and their adjusted p.

**The chance level is Boole's bound** (:func:`~rietx.indexing.kvector.kgrid_bound`,
``weighting="flat"``: every k scored is held to log₁₀(N/α)), with no shuffle, no
margin and no free factor.  Every row carries its adjusted p, min(1, P·nₛ/wₛ), so a
reader can re-read the ranking at another α without a rerun; with ``"flat"`` that
is N·P.  ``alpha`` is a stated convention, 0.01, not a measurement: a series of n
patterns searched at α expects about α·n chance k.

**The windows.**  By default every nuclear line is excluded at ± one local
nuclear FWHM (:data:`~rietx.indexing.fom.RESOLUTION_FWHM` FWHM, the width indexing
reads as the measured resolution), the peaks inside a window are sorted out
before scoring, and the same windows are the bound's ``exclude``.  A satellite
within that window cannot be told from a nuclear shoulder by position alone, so
a k whose satellites all fall inside the windows (a long period, a few grid steps
from Γ) cannot be found from these peaks; ``coverage`` says so.  The window does
not stop a profile misfit's shoulders that sit further out; the crowding row
reports those.

**The crowding row** (:class:`KCrowding`): a one-sided Kolmogorov-Smirnov test of
each kept peak's distance to its nearest nuclear line (in window units) against
uniform placement on the 2θ range outside the windows (Kolmogorov, A. N. (1933),
*G. Ist. Ital. Attuari* **4**, 83-91; Smirnov, N. (1948), *Ann. Math. Stat.*
**19**, 279-281; the one-sided exact distribution, Birnbaum, Z. W. & Tingey, F. H.
(1951), *Ann. Math. Stat.* **22**, 592-596, through :func:`scipy.stats.kstest`).
Peaks crowding the nuclear lines are what a profile misfit leaves; so is a real
k whose satellites sit near nuclear lines, which is why the row warns
(``K_SEARCH_CROWDED`` when p < ``alpha``) and withholds nothing.

**Measured on one family, untested beyond it.**  The windows, the crowding row
and the bound were exercised on synthetic CW-neutron patterns (Pnma, 5.74 × 7.70
× 5.54 Å, λ 2.41 Å, 10-140° 2θ; issue #795 and WP-1418's K1a and K1b handovers).

**The default strata order** is K1a's listing order, points, then lines, then
planes, then the general stratum, after Wills (2009) § 3.1, which searches special
points before lines before planes so that a high-symmetry k is not read as a
lower-symmetry one.  That is all this module takes from Wills for the ranking:
the score is a position chance score (de Wolff, P. M. (1968), *J. Appl. Cryst.*
**1**, 108-113, for the chance rate it descends from).  Rows of equal adjusted p
and score keep that order.

Clean room: the literature above and our own design spikes only (issue #795).
No other program's source was read.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from functools import lru_cache

import numpy as np
from scipy.stats import kstest

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
from .fom import RESOLUTION_FWHM
from .kvector import (
    KBound,
    KEquivalents,
    KGridPositions,
    KGridRow,
    KParent,
    KPeaks,
    KStratum,
    Weighting,
    as_kpeaks,
    kgrid_bound,
    kgrid_strata,
    kvector_equivalents,
    score_kgrid,
)

__all__ = [
    "K_SEARCH_GRID_DENOMINATOR",
    "K_SEARCH_NEAR_FWHM",
    "K_SEARCH_PARTNER_TOL",
    "K_SEARCH_PARTNER_STEPS",
    "KCrowding",
    "KSearchResult",
    "search_kvector",
]

#: The grid's denominator: every k component a multiple of 1/64.  It is
#: :data:`~rietx.crystallography.representation.irreps.K_MAX_DENOMINATOR`, the
#: commensurate door's own bound, with no factor of its own; its use as the
#: search *step* is a choice, which every result reports as ``grid_step``
#: (issue #795, decision 2: no claim about any k off the grid).
K_SEARCH_GRID_DENOMINATOR: int = K_MAX_DENOMINATOR

#: The distance, in local nuclear FWHM, inside which :attr:`KCrowding.n_near`
#: counts a kept peak: a number reported beside the crowding p, read by no rule.
#: Twice the window, so it counts the peaks in the first FWHM outside it.
K_SEARCH_NEAR_FWHM: float = 2.0

#: The metric tolerance at which the top k's near-symmetric partners are listed
#: (``K_SEARCH_PARTNER``, :func:`~rietx.indexing.kvector.kvector_equivalents`).
#: At 0.08 the x ↔ z image on a 5.74 × 7.70 × 5.54 Å Pnma cell is listed
#: (relative deviation 0.0735) and none on a 5.74 × 7.70 × 6.40 Å one (WP-1418
#: K1a, V6).
K_SEARCH_PARTNER_TOL: float = 0.08

#: The partner's neighbourhood, in steps of the 1/:data:`K_SEARCH_GRID_DENOMINATOR`
#: grid (Chebyshev, modulo the reciprocal lattice), so a fixed distance in k of
#: 4/64 whatever grid a caller searched: the satellites of a partner's exact image
#: are moved by the metric's deviation, so the grid k matching them best sits a
#: few steps away.  Four: on the pseudo-tetragonal cell above the best grid k
#: within four steps of the image matched 8 of 10 planted peaks where the image
#: matched 2 (WP-1418 K1a, V6).
K_SEARCH_PARTNER_STEPS: int = 4

#: Why :meth:`KSearchResult.best_or_none` returns ``None``, by the reason code
#: :attr:`KSearchResult.withheld` carries.
_WITHHELD: dict[str, str] = {
    "position_only": (
        "ranked from peak positions only; a k is confirmed by refinement (a moment or "
        "modulation model fitted to the intensities), as a cell is by a whole-profile fit"),
    "search_cut": (
        "the budget stopped the search before it covered every stratum, so a k in the part "
        "left could outrank the top row; pass budget=\"full\""),
}


# --------------------------------------------------------------------------
# the result
# --------------------------------------------------------------------------

@dataclass(frozen=True, repr=False)
class KCrowding:
    """How strongly the kept peaks crowd the nuclear lines (:func:`search_kvector`).

    ``p_value`` is the one-sided Kolmogorov-Smirnov p of the peaks' distances to
    their nearest nuclear line against uniform placement on the 2θ range outside
    the windows; ``statistic`` is its D⁺.  ``n_peaks`` is N, the kept peaks it
    is taken over.  ``n_near`` counts the peaks within
    :data:`K_SEARCH_NEAR_FWHM` local nuclear FWHM of a line, ``None`` when no
    width was known (a caller's radius or windows alone).  ``form`` names the
    test in words.  A small p is what a profile misfit's shoulders give, and also
    what a real k with satellites near nuclear lines gives: it is a statistic,
    not a verdict.
    """

    p_value: float
    statistic: float
    n_peaks: int
    n_near: int | None
    form: str

    def __repr__(self) -> str:
        near = "" if self.n_near is None else f", {self.n_near} within {K_SEARCH_NEAR_FWHM:g} FWHM"
        return f"KCrowding(p={self.p_value:.3g}, N={self.n_peaks}{near})"


@dataclass(frozen=True, repr=False)
class KSearchResult:
    """The ranked k-search (:func:`search_kvector`).  **No** ``k``, **no** ``best``.

    ``rows`` are K1a's :class:`~rietx.indexing.kvector.KGridRow` records,
    sorted by ``p_adjusted`` (its family-wise adjusted chance probability under
    ``bound``), smallest first, then by score; rows that tie on both keep the
    strata order (points before lines before planes before the general
    stratum).  With ``"flat"`` weighting that is the score order.  Each row is
    a **hypothesis**: its exact rational k, its stratum, its score (−log₁₀ of
    its own chance probability), the peaks it matches and leaves, and its
    structural ``equivalents``.  ``p_adjusted[i]`` belongs to ``rows[i]``.

    ``bound`` is :func:`~rietx.indexing.kvector.kgrid_bound` over the k
    scored; ``alpha`` and ``weighting`` are its.  A row **clears** when its
    adjusted p is at most ``alpha`` (its score reaches its stratum's
    threshold); ``n_cleared`` counts them.

    ``peaks`` are the peaks scored, the caller's peaks less those inside a
    window: ``kept`` and ``sorted_out`` are their indices in the caller's list,
    and a row's ``matched``/``unmatched`` index ``peaks``.  ``exclude`` holds
    the windows (centre, half-width) in ° 2θ and ``exclude_source`` where their
    width came from (``"nuclear_fwhm"``, ``"residual census"``, ``"radius"``:
    a caller's radius with no width, or ``"caller"``: the caller's own
    ``exclude``).  ``peak_distance_fwhm`` gives each kept peak's distance to its
    nearest nuclear line in local nuclear FWHM, ``None`` when no width was
    known.  ``crowding`` is the :class:`KCrowding` row, ``None`` with no
    windows or no peaks.

    ``radius`` and ``radius_source`` say which match radius scored the rows
    and where it came from (``"caller"``, ``"residual census"`` or
    ``"nuclear lines"``).  The grid facts are K1a's: ``grid_step``,
    ``strata_searched``, ``strata_cut``, ``strata_left`` and ``coverage``, which
    claims nothing about any k off the grid and names the windows' blind zone.
    ``preset`` is ``"quick"``, ``"full"`` or ``"custom"`` (a caller's own
    budget).

    ``partners`` are the top k's
    :func:`~rietx.indexing.kvector.kvector_equivalents` at
    :data:`K_SEARCH_PARTNER_TOL`, and ``partner_tie`` the best row near a
    partner image (outside the top's own neighbourhood) that also clears
    ``alpha`` while the top does, or ``None``: positions alone then cannot
    say which of the two the peaks belong to (Mighell, A. D. & Santoro, A.
    (1975), *J. Appl. Cryst.* **8**, 372-374, one rank over: the geometrical
    ambiguity of a cell).

    ``withheld`` holds the reason codes :meth:`best_or_none` reads
    (``"position_only"`` always; ``"search_cut"`` when a budget cut the
    search), and ``withheld_reasons`` their sentences.  ``diagnostics``
    carries ``K_SEARCH_AT_CHANCE``, ``K_SEARCH_FEW_PEAKS``, ``K_SEARCH_CUT``,
    ``K_SEARCH_CROWDED`` and the partners' ``K_SEARCH_PARTNER``.
    """

    parent: KParent
    peaks: KPeaks
    kept: tuple[int, ...]
    sorted_out: tuple[int, ...]
    rows: tuple[KGridRow, ...]
    p_adjusted: tuple[float, ...]
    bound: KBound
    radius: float
    radius_source: str
    band_deg: float
    harmonics: tuple[int, ...]
    exclude: tuple[tuple[float, float], ...]
    exclude_source: str
    peak_distance_fwhm: tuple[float, ...] | None
    crowding: KCrowding | None
    grid_step: float
    strata_searched: tuple[str, ...]
    strata_cut: tuple[tuple[str, int, int], ...]
    strata_left: tuple[str, ...]
    coverage: str
    preset: str
    budget_seconds: float | None
    budget_expired: bool
    elapsed_seconds: float
    partners: KEquivalents | None
    partner_tie: KGridRow | None
    withheld: tuple[str, ...]
    diagnostics: tuple[Diagnostic, ...]

    @property
    def alpha(self) -> float:
        return self.bound.alpha

    @property
    def weighting(self) -> str:
        return self.bound.weighting

    @property
    def n_peaks(self) -> int:
        return len(self.peaks)

    @property
    def n_cleared(self) -> int:
        """How many rows clear ``alpha`` (adjusted p ≤ ``alpha``)."""
        return sum(1 for p in self.p_adjusted if p <= self.alpha)

    def threshold(self, row: KGridRow) -> float:
        """The score ``row``'s stratum is held to under ``bound``."""
        return dict(zip(self.bound.strata, self.bound.thresholds))[row.stratum]

    @property
    def margin(self) -> float | None:
        """The top score minus its stratum's threshold, in decades (``None`` with
        no rows).  Reported; no rule reads it."""
        if not self.rows:
            return None
        return self.rows[0].score - self.threshold(self.rows[0])

    @property
    def withheld_reasons(self) -> tuple[str, ...]:
        return tuple(_WITHHELD[c] for c in self.withheld)

    def best_or_none(self) -> KGridRow | None:
        """``None``, for every search :func:`search_kvector` runs.

        The search ranks k from peak positions alone, and a k is confirmed by
        refinement, so no row is picked (``withheld`` names the reasons:
        ``"position_only"``, and ``"search_cut"`` when a budget cut the
        search).  **``None`` is not "no k"**: the ranking, each row's adjusted
        p, ``n_cleared`` and the warnings are the answer.  Read ``rows[0]``
        as the first hypothesis to refine when it clears ``alpha`` and no
        warning fires.  The method exists, as indexing's does, so that the
        rule is guaranteed in one place.
        """
        return None if self.withheld else self.rows[0] if self.rows else None

    def __repr__(self) -> str:
        top = (f"top k = {format_kvector(self.rows[0].k)} at {self.rows[0].score:.2f} "
               f"(adjusted p {self.p_adjusted[0]:.3g})" if self.rows else "no rows")
        codes = ", ".join(d.code for d in self.diagnostics) or "no diagnostics"
        return (f"KSearchResult(N={self.n_peaks} ({len(self.sorted_out)} sorted out), "
                f"{len(self.rows)} rows ranked, {top}; {self.n_cleared} clear alpha "
                f"{self.alpha:g} ({self.weighting}); radius {self.radius:.3f}° "
                f"({self.radius_source}); {len(self.strata_searched)} strata searched, "
                f"{len(self.strata_cut)} cut, {len(self.strata_left)} left; "
                f"best_or_none: None ({', '.join(self.withheld)}); {codes})")


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


def _width_function(nuclear_fwhm) -> Callable[[np.ndarray], np.ndarray] | None:
    """``nuclear_fwhm`` as a function of 2θ, checked before any work."""
    if nuclear_fwhm is None:
        return None
    if callable(nuclear_fwhm):
        fn = nuclear_fwhm
    elif isinstance(nuclear_fwhm, (int, float, np.integer, np.floating)) and not isinstance(
            nuclear_fwhm, bool):
        value = float(nuclear_fwhm)
        fn = lambda tt: np.full(np.shape(tt), value)  # noqa: E731
    else:
        raise TypeError(
            f"nuclear_fwhm is the nuclear lines' FWHM in ° 2θ: a number, or a function of "
            f"2θ such as an instrument's Caglioti curve; got {type(nuclear_fwhm).__name__}. "
            "A list cannot say which line each value belongs to")

    def checked(tt) -> np.ndarray:
        out = np.asarray(fn(np.asarray(tt, dtype=np.float64)), dtype=np.float64)
        out = np.broadcast_to(out, np.shape(tt)).astype(np.float64)
        if out.size and not (np.all(np.isfinite(out)) and np.all(out > 0)):
            raise ValueError("nuclear_fwhm must give a positive, finite FWHM in ° 2θ at "
                             "every nuclear line and peak")
        return out

    return checked


def _resolve_radius(kp: KPeaks, radius, width, lines) -> tuple[float, str]:
    if radius is not None:
        r = float(radius)
        if not (math.isfinite(r) and r > 0):
            raise ValueError(f"radius must be a positive number of degrees, got {radius!r}")
        return r, "caller"
    census = _median_width(kp.fwhm)
    at = np.asarray(kp.two_theta, dtype=np.float64)
    nuclear = (None if width is None
               else _median_width(width(at if at.size else np.asarray(lines))))
    if census is None and nuclear is None:
        raise ValueError(
            "no width to set the match radius from: pass radius= in ° 2θ, give the peaks "
            "their fitted fwhm (a PeakList carries it), or pass nuclear_fwhm=, the nuclear "
            "lines' FWHM (a number or a function of 2θ)")
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


def _windows(parent: KParent, exclude, width, kp: KPeaks, radius: float,
             radius_source: str):
    """The windows as (centres, half-widths, FWHM per line or None, source)."""
    if exclude is not None:
        arr = np.asarray(exclude, dtype=np.float64).reshape(-1, 2) if len(exclude) else \
            np.zeros((0, 2))
        return arr[:, 0], arr[:, 1], None, "caller"
    lines = np.asarray(lattice_two_theta(parent.group, parent.cell, parent.wavelength,
                                         parent.two_theta_max, parent.two_theta_min),
                       dtype=np.float64)
    if width is not None:
        fw, source = width(lines), "nuclear_fwhm"
    elif radius_source == "residual census" or _median_width(kp.fwhm) is not None:
        fw, source = np.full(lines.shape, _median_width(kp.fwhm)), "residual census"
    else:
        return lines, np.full(lines.shape, radius), None, "radius"
    return lines, RESOLUTION_FWHM * fw, fw, source


def _union_length(c: np.ndarray, h: np.ndarray, t: float, lo: float, hi: float) -> float:
    """The length of ∪ [cᵢ − t·hᵢ, cᵢ + t·hᵢ] inside [lo, hi]."""
    a = np.clip(c - t * h, lo, hi)
    b = np.clip(c + t * h, lo, hi)
    o = np.argsort(a, kind="stable")
    a, b = a[o], b[o]
    reach = np.maximum.accumulate(b)
    start = np.ones(len(a), dtype=bool)
    start[1:] = a[1:] > reach[:-1]
    first = np.flatnonzero(start)
    last = np.append(first[1:] - 1, len(a) - 1)
    return float(np.sum(reach[last] - a[first]))


def _crowding(tt: np.ndarray, c: np.ndarray, h: np.ndarray, fw, lo: float,
              hi: float) -> tuple[KCrowding | None, tuple[float, ...] | None]:
    """The crowding row and the per-peak distance in local FWHM."""
    if not len(c) or not len(tt):
        return None, (None if fw is None else ())
    rel = np.abs(tt[:, None] - c[None, :])
    d = np.min(rel / h[None, :], axis=1)                   # window units, ≥ 1 once sorted
    dist = None if fw is None else tuple(float(x) for x in np.min(rel / fw[None, :], axis=1))
    inside = _union_length(c, h, 1.0, lo, hi)
    free = (hi - lo) - inside
    if free <= 0.0:
        return None, dist
    # F0(d): the share of the allowed range lying within d window units of a line,
    # exactly, as the length of a union of intervals (no sampling grid)
    u = np.array([(_union_length(c, h, float(t), lo, hi) - inside) / free for t in d])
    test = kstest(np.clip(u, 0.0, 1.0), "uniform", alternative="greater", method="exact")
    near = None if dist is None else int(sum(x < K_SEARCH_NEAR_FWHM for x in dist))
    form = ("one-sided Kolmogorov-Smirnov (exact) of each peak's distance to its nearest "
            "nuclear line, in window half-widths, against uniform placement on the 2θ range "
            "outside the windows")
    return KCrowding(p_value=float(test.pvalue), statistic=float(test.statistic),
                     n_peaks=int(len(tt)), n_near=near, form=form), dist


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


def _partner_tie(parent: KParent, rows: tuple[KGridRow, ...], p_adjusted: Sequence[float],
                 alpha: float, partners: KEquivalents, n: int) -> KGridRow | None:
    """The best row near a partner image of the top that also clears ``alpha``.

    Read only when the top clears; rows inside the top's own neighbourhood of
    :data:`K_SEARCH_PARTNER_STEPS` steps are its own class's, never a partner's.
    """
    if not rows or p_adjusted[0] > alpha:
        return None
    images = [e.k for e in partners.rows if e.relation == "partner"]
    if not images:
        return None
    top = rows[0]
    xhm = parent.space_group
    own = top.equivalents
    for row, p in zip(rows[1:], p_adjusted[1:]):
        if p > alpha:
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
                   alpha: float = 0.01,
                   weighting: Weighting = "flat") -> KSearchResult:
    """Rank every k of the grid against ``peaks``, from positions alone.

    ``peaks`` are the unexplained peaks (positions in ° 2θ, a
    :class:`~rietx.indexing.kvector.KPeaks` or a ``PeakList``); which peaks
    are unexplained is the caller's sort.  ``parent`` is the known parent.
    The answer ranks hypotheses and picks none: :meth:`KSearchResult.best_or_none`
    is ``None`` for every call (a k is confirmed by refinement), and the rows
    with their adjusted p, ``n_cleared`` and the warnings are the answer.

    Defaults, each recorded on the result:

    * ``radius=None``: :data:`~rietx.report.schemas.VALIDITY_RADIUS_FWHM` ×
      the median FWHM the peaks themselves carry (the residual census), floored
      at the median nuclear FWHM at the peaks when ``nuclear_fwhm`` is given;
      ``radius_source`` says which bound.  With no width anywhere it raises.
    * ``nuclear_fwhm=None``: the nuclear lines' FWHM in ° 2θ, a number or a
      function of 2θ (an instrument's Caglioti curve).  It sets the windows'
      width line by line.
    * ``exclude=None``: every nuclear line
      (:func:`~rietx.crystallography.satellites.lattice_two_theta`) at ±
      :data:`~rietx.indexing.fom.RESOLUTION_FWHM` local nuclear FWHM, from
      ``nuclear_fwhm``, else from the peaks' census width, else (a caller's
      radius with no width anywhere) at ± the radius; ``exclude_source`` says
      which.  Peaks inside a window are sorted out before scoring and listed
      in ``sorted_out``; the same windows are the bound's exclusions.  A
      caller's ``exclude`` ((centre, half-width) pairs) is used as given.
    * ``strata=None``: every stratum of the 1/:data:`K_SEARCH_GRID_DENOMINATOR`
      grid in K1a's order (points, lines, planes, general; Wills 2009 § 3.1);
      a sequence of :class:`~rietx.indexing.kvector.KStratum` or a
      :class:`~rietx.indexing.kvector.KGridPositions` built from them is
      searched in its own order (the second skips the position build).  A
      caller's ``strata`` is a restriction, not a cut.
    * ``budget=None``: the indexing package's ``"quick"`` preset, a whole-run
      :class:`~rietx.indexing.engines.Deadline` of ``SEARCH_PRESETS["quick"]``
      seconds; ``"full"`` is unbounded and a
      :class:`~rietx.indexing.engines.Budget` is the caller's.  It is read
      before every block of k inside a stratum
      (:func:`~rietx.indexing.kvector.score_kgrid`), so it bounds the search;
      a cut is reported in ``strata_cut`` and ``strata_left`` and by
      ``K_SEARCH_CUT``.
    * ``band_deg=5.0``: the local chance band of each row's score.
    * ``alpha=0.01``: the family-wise level of Boole's bound, a stated
      convention; ``weighting="flat"`` holds every k scored to log₁₀(N/α)
      (:func:`~rietx.indexing.kvector.kgrid_bound`; ``"stratum"`` gives each
      stratum an equal share).

    Warnings, none of which refuses or removes a row:
    ``K_SEARCH_AT_CHANCE`` (no row clears ``alpha``), ``K_SEARCH_FEW_PEAKS``
    (no row clears although the top matches every peak),
    ``K_SEARCH_CUT`` (a budget cut the search) and ``K_SEARCH_CROWDED`` (the
    crowding p is under ``alpha``).

    Likeliest misuse: reading ``best_or_none() is None`` as "no magnetic or
    modulated order".  It is ``None`` on every call; read ``withheld``.
    """
    a = float(alpha)
    if not 0.0 < a < 1.0:
        raise ValueError(f"alpha must lie in (0, 1), got {alpha!r}")
    if weighting not in ("flat", "stratum"):
        raise ValueError(f"weighting must be 'flat' or 'stratum', got {weighting!r}")
    kp_in = as_kpeaks(peaks)
    width = _width_function(nuclear_fwhm)
    deadline, preset = _resolve_budget(budget)
    if strata is None:
        strata = kgrid_strata(parent.space_group, denominator=K_SEARCH_GRID_DENOMINATOR)
    built = strata if isinstance(strata, KGridPositions) else None
    if not tuple(built.strata if built is not None else strata):
        raise ValueError("no strata given: pass the strata to search, or None for the grid")
    lines = lattice_two_theta(parent.group, parent.cell, parent.wavelength,
                              parent.two_theta_max, parent.two_theta_min)
    r, source = _resolve_radius(kp_in, radius, width, lines)
    c, h, fw, ex_source = _windows(parent, exclude, width, kp_in, r, source)

    # sort the peaks off the windows (strictly inside, as score_kgrid refuses)
    tt_in = np.asarray(kp_in.two_theta, dtype=np.float64)
    inside = (np.any(np.abs(tt_in[:, None] - c[None, :]) < h[None, :], axis=1)
              if len(c) and len(tt_in) else np.zeros(len(tt_in), dtype=bool))
    kept = tuple(int(i) for i in np.flatnonzero(~inside))
    out = tuple(int(i) for i in np.flatnonzero(inside))

    def _take(values):
        return None if values is None else tuple(values[i] for i in kept)

    kp = KPeaks(two_theta=tuple(kp_in.two_theta[i] for i in kept), fwhm=_take(kp_in.fwhm),
                tags=_take(kp_in.tags))
    pairs = tuple((float(x), float(w)) for x, w in zip(c, h))

    grid = score_kgrid(kp, parent, strata, radius=r, band_deg=band_deg, harmonics=harmonics,
                       budget=deadline, exclude=pairs)
    if not grid.rows:
        raise RuntimeError("the budget had expired before the first block, so nothing was "
                           "searched; pass a budget that has not run out")
    bound = kgrid_bound(grid, alpha=a, weighting=weighting)
    factor = {s: n / w for s, n, w in zip(bound.strata, bound.n_scored, bound.weights)}
    padj = [min(1.0, row.p_value * factor[row.stratum]) for row in grid.rows]
    order = sorted(range(len(grid.rows)), key=lambda i: (padj[i], -grid.rows[i].score))
    ranked = tuple(grid.rows[i] for i in order)
    p_adjusted = tuple(float(padj[i]) for i in order)
    tt = np.asarray(kp.two_theta, dtype=np.float64)
    crowding, distance = _crowding(tt, c, h, fw, parent.two_theta_min, parent.two_theta_max)
    coverage = grid.coverage + _blind_zone(ex_source, len(out))

    diags: list[Diagnostic] = []
    top = ranked[0]
    where = [f"k = {format_kvector(top.k)}"]
    bar = dict(zip(bound.strata, bound.thresholds))[top.stratum]
    cleared = p_adjusted[0] <= a
    partners = kvector_equivalents(parent, top.k, tol=K_SEARCH_PARTNER_TOL)
    tie = _partner_tie(parent, ranked, p_adjusted, a, partners, K_SEARCH_GRID_DENOMINATOR)
    law = (f"Boole's bound over the {bound.n_total} k scored at alpha = {a:g}, "
           f"{bound.weighting} weighting")
    if not cleared:
        diags.append(Diagnostic(
            level="warning", code="K_SEARCH_AT_CHANCE",
            message=(f"The best propagation vector, k = {format_kvector(top.k)}, scores "
                     f"{top.score:.1f} decades against a chance threshold of {bar:.1f} "
                     f"({law}; adjusted p {p_adjusted[0]:.2g}): no k in this list stands "
                     f"above chance from the positions of these {len(kp)} peaks."),
            where=where,
            suggestion=("Treat every row as a hypothesis for a moment or modulation "
                        "model; add peaks (longer counting, a paired pattern, a "
                        "temperature series) or state k from elsewhere."),
            value=top.score - bar))
        if top.n_matched == len(kp):
            diags.append(Diagnostic(
                level="warning", code="K_SEARCH_FEW_PEAKS",
                message=(f"The top k, {format_kvector(top.k)}, matches all {len(kp)} peaks "
                         f"kept and still scores {top.score:.1f} decades, under the chance "
                         f"threshold of {bar:.1f}: over the {bound.n_total} k scored at a "
                         f"{r:.2f}° radius, a k with as many satellite lines in range as this "
                         f"one matches {len(kp)} peaks this well by chance, so these peaks "
                         "neither find such a k nor rule it out."),
                where=where, value=float(len(kp))))
    if grid.strata_cut or grid.strata_left:
        cut = "; ".join(f"stratum {n} cut after {s} of {t} points"
                        for n, s, t in grid.strata_cut)
        left = ", ".join(grid.strata_left)
        diags.append(Diagnostic(
            level="warning", code="K_SEARCH_CUT",
            message=("The budget stopped the k-search before it covered the grid: "
                     + "; ".join(x for x in (cut, f"strata left unsearched: {left}" if left
                                             else "") if x)
                     + ". A k in the part not searched could outrank every row listed."),
            where=where,
            suggestion='Rerun with budget="full", or restrict strata= to the strata wanted.',
            value=float(len(grid.strata_left) + len(grid.strata_cut))))
    if crowding is not None and crowding.p_value < a:
        near = ("" if crowding.n_near is None else
                f", {crowding.n_near} within {K_SEARCH_NEAR_FWHM:g} local FWHM of a line")
        diags.append(Diagnostic(
            level="warning", code="K_SEARCH_CROWDED",
            message=(f"The {crowding.n_peaks} peaks searched crowd the nuclear lines (one-sided "
                     f"Kolmogorov-Smirnov p = {crowding.p_value:.2g} < alpha = {a:g}{near}): "
                     "a profile misfit leaves shoulders there, and a k scored on them is the "
                     "misfit's. A real k whose satellites sit near nuclear lines (a long "
                     "period, a few grid steps from Γ) crowds them too, so this does not rule "
                     "such a k out."),
            where=where,
            suggestion=("Refine the nuclear profile (widths, shape, asymmetry, zero) until the "
                        "residue is flat beside the nuclear lines, then search again; or test "
                        "the k by refinement."),
            value=crowding.p_value))
    diags.extend(partners.diagnostics)

    withheld = ("position_only",) + (("search_cut",) if grid.strata_cut or grid.strata_left
                                     else ())
    return KSearchResult(
        parent=parent, peaks=kp, kept=kept, sorted_out=out, rows=ranked, p_adjusted=p_adjusted,
        bound=bound, radius=r, radius_source=source, band_deg=float(grid.band_deg),
        harmonics=grid.harmonics, exclude=grid.exclude, exclude_source=ex_source,
        peak_distance_fwhm=distance, crowding=crowding, grid_step=grid.grid_step,
        strata_searched=grid.strata_searched, strata_cut=grid.strata_cut,
        strata_left=grid.strata_left, coverage=coverage, preset=preset,
        budget_seconds=grid.budget_seconds, budget_expired=grid.budget_expired,
        elapsed_seconds=grid.elapsed_seconds, partners=partners, partner_tie=tie,
        withheld=withheld, diagnostics=tuple(diags))


def _blind_zone(source: str, n_out: int) -> str:
    if source == "caller":
        return (f" {n_out} peak(s) inside the caller's exclude windows were sorted out; a k "
                "whose satellites all fall inside those windows cannot be found from these "
                "peaks.")
    width = ("± the match radius (no width was given)" if source == "radius" else
             f"± {RESOLUTION_FWHM:g} local nuclear FWHM ({source})")
    return (f" Peaks within {width} of a nuclear line were sorted out ({n_out} here), so a k "
            "whose satellites all fall that close to nuclear lines (a long period, a few grid "
            "steps from Γ) cannot be found from these peaks.")

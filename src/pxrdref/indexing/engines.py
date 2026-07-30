"""What every search engine shares: the registry, the option surface, the
budget, the crash guard, and the shape of an answer.

Three engines search for a cell (WP-1021 dichotomy, WP-1022 trial and error,
WP-1023 Monte Carlo) and their **agreement** is the confidence WP-1024 reports —
the same device as ``sequential.py``'s ``direction="both"`` and the cross-backend
Jacobian matrix.  That only works if they are genuinely independent *searches*
that answer in one vocabulary, so everything shared but non-searching lives here:

* :class:`SearchSpec` — one option object, so a caller sets ``max_volume`` once
  and every engine means the same thing by it;
* :class:`EngineCandidate` / :class:`EngineResult` — the answer shape, carrying
  the ``CandidateFit`` (hence ``cov_af``, hence WP-1020's χ² dedup) rather than
  only the schema object, because consensus needs the covariance;
* :func:`register_engine` / :func:`engine_names` — the **live registry**
  WP-1024's agent schema quotes, so a fourth engine cannot be absent from the
  exported tool definition (the WP-0602 meta-test pattern);
* :class:`Budget` and ``search_complete`` — an engine that ran out of time must
  say so per system, because *silence is only evidence when the search finished*;
* :func:`reflection_ceiling_ok` — the crash guard.

**The crash guard is not a quality guard, and it is the most load-bearing
function here.**  Measured in this repo's own prior art (tag ``guillemot-study``,
``audit_tools.py`` check B): a runaway cell on a 1.7 wt % phase made the
reflection generator ask for **1.6 PiB**.  ``generate_reflections`` enumerates a
box ``hmax = floor(a/d_min) + 1`` per axis, so the count goes as the volume, and a
search that *proposes* cells — all three of these do — will eventually propose one
big enough to exhaust memory.  Every path that reaches ``generate_reflections``
from a trial cell goes through :func:`reflection_ceiling_ok` first.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

import numpy as np

from ..schemas.common import Diagnostic
from ..schemas.indexing import (
    METRIC_DOF,
    CellCandidate,
    PeakList,
)
from .fom import MATCH_SIGMA, fom_panel, lattice_group, match_lines
from .qspace import CandidateFit, design_matrix, refine_candidate, trial_hkl

#: Systems in decreasing lattice-point-group order — the order every engine
#: searches in.  Highest symmetry first is not a preference, it is a cost
#: statement: the metric has 1 degree of freedom in cubic and 6 in triclinic, so
#: a cubic answer costs seconds while a triclinic search costs minutes, and a
#: caller who gets the cubic answer first can stop.
SYSTEM_ORDER: tuple[str, ...] = ("cubic", "hexagonal", "trigonal", "tetragonal",
                                 "orthorhombic", "monoclinic", "triclinic")

#: Bravais centrings each system admits, in the conventional setting.  A search
#: over metrics alone would miss every centred lattice whose *primitive* cell is
#: not in the same system — a body-centred cubic lattice has a rhombohedral
#: primitive cell, so a cubic-subspace search that assumed P would never see it.
#: Centring costs nothing to carry: it is a filter on the trial hkl set, and a
#: filtered set is *harder* to satisfy, so it prunes rather than adds work.
CENTRINGS: dict[str, tuple[str, ...]] = {
    "cubic": ("P", "I", "F"),
    "hexagonal": ("P",),
    "trigonal": ("P", "R"),
    "tetragonal": ("P", "I"),
    "orthorhombic": ("P", "C", "I", "F"),
    "monoclinic": ("P", "C"),
    "triclinic": ("P",),
}

#: Predicted reflections above which a trial cell is refused rather than
#: enumerated.  Two million integer triples is ~48 MB of hkl plus the d-spacing
#: pass — large enough that no legitimate cell in a bounded search reaches it
#: (SRM 660c to 90° 2θ predicts 24) and small enough to be an instant, survivable
#: refusal.  See the module docstring for the 1.6 PiB that motivated it.
MAX_PREDICTED_REFLECTIONS = 2_000_000
#: Relative agreement in reduced-cell volume below which two candidates are worth
#: comparing properly.  A gate, not a test: two lattices whose volumes differ by
#: more than this cannot pass the χ² metric equality, so the gate only skips
#: comparisons whose answer is already known — which is what keeps a dedup pass
#: over thousands of raw candidates from being O(N²) pinv solves.
DEDUP_VOLUME_RTOL = 0.01

#: Default shortest principal d-spacing (Å) a search will consider.  A bound on
#: *d(100)*, not on *a*: for an oblique cell d(100) = a·sin β < a, so this is
#: slightly the stronger statement, and it is the one the Q-space box actually
#: constrains (A = 1/d(100)²).
DEFAULT_MIN_D_AXIS = 2.0
#: Default longest principal d-spacing (Å).  25 Å covers small-molecule organics
#: (the bethanechol benchmark's longest axis is 15.9 Å); a caller with a protein
#: or a layered phase raises it and pays for it in search volume.
DEFAULT_MAX_D_AXIS = 25.0
#: Smallest unit-cell volume (Å³) a search will report.  Below this the "cell" is
#: smaller than a single atom's exclusion volume, so it is a numerical artefact
#: of the metric cone rather than a lattice.
DEFAULT_MIN_VOLUME = 15.0
#: Observed lines a search is *driven* by, lowest Q first.  Twenty because that
#: is what the figures of merit are defined on and what the literature searches
#: use; scoring afterwards uses **every** usable line, so a candidate that
#: explains the first twenty and nothing else is ranked down rather than hidden.
DEFAULT_SEARCH_LINES = 20
#: Lines a search may leave unindexed and still accept a cell.  DICVOL06's own
#: reported gain, and the single most valuable option here: without it one
#: impurity line prunes the true box and the engine returns nothing, confidently.
#: **Raising it manufactures cells** — every extra tolerated line is one more
#: coincidence a wrong metric is allowed to have, so 2 is a default and 4 is a
#: statement about the specimen, not a knob to turn when nothing is found.
DEFAULT_N_UNINDEXED = 2
#: Systematic 2θ allowance (degrees) added in quadrature to every line's fitted σ
#: when **no shift has been measured** — which is the normal state at index time,
#: because a shift is only identifiable against a reference and there is no cell
#: yet (``quality.py``).
#:
#: **Why it exists is measured; its value is a policy, and the gap between the two
#: is recorded rather than hidden.**  Fitted per-line σ on the bundled qarr corundum
#: pattern has a median of 0.0056° 2θ, while the pattern's lines sit a median
#: **0.060°** from the certified cell's positions — a cos θ specimen displacement of
#: −0.065°, i.e. an **11σ** systematic.  At σ_eff = fitted σ the certified cell
#: therefore indexes *zero* lines and both engines return nothing, measured on a
#: pattern whose answer is known.  That is the whole reason a global "position
#: tolerance" of ~0.03° 2θ is the literature's default, and 0.05 is that number with
#: margin.
#:
#: **It is not enough to index that pattern, and that is an open result, not a
#: solved one.**  At 0.05 the trial-and-error engine still finds nothing and
#: dichotomy ranks a wrong 618 Å³ cell first; at 0.08 trial-and-error recovers
#: a = 4.7659 Å against the certified 4.7593 (+1400 ppm, the shift absorbed into the
#: cell).  Widening further costs specificity in both directions, so the remedy is
#: not a bigger number: it is fitting the shift template, which
#: :func:`refine_with_shift` does *after* a candidate survives — because a shift is
#: only identifiable against reference positions and a candidate cell is what
#: supplies them.  Closing the loop on real data is WP-1026's acceptance work; every
#: result records which allowance it used and says so with
#: ``INDEX_SHIFT_ALLOWANCE``.
DEFAULT_UNKNOWN_SHIFT_DEG = 0.05
#: Wall-clock seconds a single system may consume before the engine gives up on
#: it and reports ``search_complete[system] = False``.
DEFAULT_BUDGET_SECONDS = 30.0
#: Candidates an engine returns per system after dedup.  A cap, not a ranking:
#: the panel ranks, and 1024 consensus-merges.
DEFAULT_MAX_CANDIDATES = 12


@dataclass(frozen=True)
class SearchSpec:
    """Everything a search needs that is not the peak list itself.

    One object rather than a dozen keyword arguments per engine, because the
    three engines must mean the *same* thing by ``max_volume`` and
    ``n_unindexed`` for their agreement to be evidence of anything.

    ``max_volume`` is a **per-system** dict when it comes from
    :func:`~pxrdref.indexing.quality.assess_peak_list` (Smith's envelope differs
    by up to 96× across systems), a float when a caller declares one, and ``None``
    to take the envelope from the data-quality report.
    """

    systems: tuple[str, ...] = SYSTEM_ORDER
    centrings: dict[str, tuple[str, ...]] | None = None
    min_d_axis: float = DEFAULT_MIN_D_AXIS
    max_d_axis: float = DEFAULT_MAX_D_AXIS
    min_volume: float = DEFAULT_MIN_VOLUME
    max_volume: float | dict[str, float] | None = None
    n_unindexed: int = DEFAULT_N_UNINDEXED
    n_search_lines: int = DEFAULT_SEARCH_LINES
    k_sigma: float = MATCH_SIGMA
    sigma_sys_deg: float = 0.0
    shift_template: str | None = None
    budget_seconds: float = DEFAULT_BUDGET_SECONDS
    max_candidates: int = DEFAULT_MAX_CANDIDATES
    #: seeded RNG for the stochastic engine; recorded in every result so a run
    #: is reproducible from what it reports
    seed: int = 0

    def centrings_for(self, system: str) -> tuple[str, ...]:
        if self.centrings is not None and system in self.centrings:
            return self.centrings[system]
        return CENTRINGS.get(system, ("P",))

    def volume_limit(self, system: str, fallback: float) -> float:
        if self.max_volume is None:
            return fallback
        if isinstance(self.max_volume, dict):
            return float(self.max_volume.get(system, fallback))
        return float(self.max_volume)


@dataclass
class EngineCandidate:
    """One cell an engine proposes, with the fit and the assignment behind it.

    Carries the :class:`~pxrdref.indexing.qspace.CandidateFit` rather than only
    the schema object because everything downstream needs what the schema drops:
    ``cov_af`` is what makes dedup a χ² test rather than a percentage
    (``reduce.same_lattice``), and the assignment is what a Le Bail validation
    (WP-1024) starts from.
    """

    fit: CandidateFit
    system: str
    centring: str
    engine: str
    #: hkl assigned to the indexed lines, and which usable lines those were
    hkl: np.ndarray
    line_index: np.ndarray
    #: usable lines the engine was offered — the denominator of ``n_indexed``
    n_lines: int
    #: the FoM panel, filled by :func:`rank_candidates` (which is what ranks) so
    #: ``to_cell_candidate`` does not enumerate the same reflections twice
    fom: list = field(default_factory=list)
    #: hkl the engine *assumed* for its base lines, where it assumed any
    #: (WP-1022).  Kept because it is the evidence a dominant zone is reported
    #: from: a solution whose base indices sit at the table's edge is one the table
    #: nearly excluded.
    base_hkl: np.ndarray | None = None
    #: every engine that produced **this lattice**, filled by WP-1024's consensus
    #: merge from :func:`dedup_groups`.  Empty means "not merged yet", and
    #: :func:`to_cell_candidate` then reports ``[engine]`` — so a single-engine run
    #: needs no merge step and the field can never disagree with ``engine``.
    found_by: list[str] = field(default_factory=list)

    @property
    def n_indexed(self) -> int:
        return int(len(self.line_index))

    @property
    def cell(self) -> tuple[float, float, float, float, float, float]:
        return self.fit.cell

    @property
    def volume(self) -> float:
        return self.fit.volume


@dataclass
class EngineResult:
    """One engine's answer: candidates, what it covered, and what it did not.

    ``search_complete`` is the half that makes a *negative* result meaningful.
    An exhaustive engine that finishes a system and finds nothing has said
    something ("no cell of that symmetry and volume fits these lines"); the same
    engine stopped by its budget has said nothing at all, and the difference must
    survive into the report rather than being inferred from an empty list.
    """

    engine: str
    candidates: list[EngineCandidate] = field(default_factory=list)
    systems_searched: tuple[str, ...] = ()
    search_complete: dict[str, bool] = field(default_factory=dict)
    stats: dict[str, float] = field(default_factory=dict)
    diagnostics: list[Diagnostic] = field(default_factory=list)

    @property
    def complete(self) -> bool:
        return all(self.search_complete.values())


# ----------------------------------------------------------------------
# Registry
# ----------------------------------------------------------------------
#: name → callable.  Populated by each engine module at import; read by
#: ``index_pattern`` and by ``agent.tool_definition()``, which must quote it
#: **live** so a new engine cannot be missing from the exported schema.
_REGISTRY: dict[str, Callable[..., EngineResult]] = {}
#: name → one line of what the engine is for, quoted into the agent schema and
#: the CLI help.  Kept beside the callable so an engine cannot register without
#: saying what it does.
_DESCRIPTIONS: dict[str, str] = {}


def register_engine(name: str, fn: Callable[..., EngineResult], description: str,
                    ) -> Callable[..., EngineResult]:
    """Register a search engine under ``name`` (idempotent per name)."""
    if name in _REGISTRY and _REGISTRY[name] is not fn:
        raise ValueError(f"engine {name!r} is already registered")
    _REGISTRY[name] = fn
    _DESCRIPTIONS[name] = description
    return fn


def engine_names() -> tuple[str, ...]:
    """Registered engines, in registration order."""
    return tuple(_REGISTRY)


def engine_descriptions() -> dict[str, str]:
    return dict(_DESCRIPTIONS)


def get_engine(name: str) -> Callable[..., EngineResult]:
    if name not in _REGISTRY:
        raise ValueError(f"unknown indexing engine {name!r}; registered: "
                         f"{sorted(_REGISTRY)}")
    return _REGISTRY[name]


# ----------------------------------------------------------------------
# Budget
# ----------------------------------------------------------------------
class Budget:
    """A wall-clock deadline, read cooperatively between units of search work.

    Deliberately the same posture as ``optimize.cancel.CancelToken`` (which it
    also carries): nothing is interrupted, the loop is simply not asked for more.
    ``expired()`` is cheap enough to call per box.
    """

    __slots__ = ("seconds", "_start", "_cancel")

    def __init__(self, seconds: float, cancel=None) -> None:
        self.seconds = float(seconds)
        self._start = time.monotonic()
        self._cancel = cancel

    def restart(self) -> "Budget":
        self._start = time.monotonic()
        return self

    @property
    def elapsed(self) -> float:
        return time.monotonic() - self._start

    def expired(self) -> bool:
        if self._cancel is not None and bool(self._cancel):
            return True
        return self.seconds > 0.0 and self.elapsed >= self.seconds


# ----------------------------------------------------------------------
# The crash guard
# ----------------------------------------------------------------------
def predicted_reflection_count(cell: Sequence[float], wavelength: float,
                               two_theta_max: float) -> int:
    """How many hkl ``generate_reflections`` would enumerate for this cell.

    Not an estimate of the *answer* — an exact count of the integer box that
    function allocates: ``hmax = floor(a/d_min) + 1`` per axis over ±hmax, so
    ``(2h+1)(2k+1)(2l+1)``.  Reproducing the generator's own arithmetic is the
    point: a guard computed a different way would drift from the thing it guards
    (``tests/test_indexing_engines.py`` pins the two together).
    """
    d_min = wavelength / (2.0 * np.sin(np.radians(max(two_theta_max, 1e-6) / 2.0)))
    n = 1.0
    for axis in tuple(cell)[:3]:
        n *= 2.0 * (np.floor(float(axis) / d_min) + 1.0) + 1.0
        if n > 1e18:                      # saturate rather than overflow int64
            return int(1e18)
    return int(n)


def reflection_ceiling_ok(cell: Sequence[float], wavelength: float,
                          two_theta_max: float, *,
                          ceiling: int = MAX_PREDICTED_REFLECTIONS) -> bool:
    """Is this cell safe to hand to ``generate_reflections``?

    Call it **before** every such call that a search reached: the alternative,
    measured, is a 1.6 PiB allocation request from a cell that ran away.
    """
    return predicted_reflection_count(cell, wavelength, two_theta_max) <= ceiling


# ----------------------------------------------------------------------
# Shared scoring / assignment
# ----------------------------------------------------------------------
def assign_lines(q_obs: np.ndarray, sigma: np.ndarray, hkl: np.ndarray,
                 af: np.ndarray, *, k_sigma: float = MATCH_SIGMA,
                 design: np.ndarray | None = None,
                 ) -> tuple[np.ndarray, np.ndarray]:
    """Give each observed line the hkl whose Q is nearest, within k·σ.

    Returns ``(line_index, hkl_assigned)`` over the lines that matched.  The
    window is per line, which is the whole contract ``schemas/indexing.py``
    establishes: a strong sharp line and a weak shoulder are not held to the same
    tolerance.

    ``design`` is ``design_matrix(hkl)`` when the caller already has it — a
    search calls this once per accepted cell over the same trial set, and
    rebuilding the (N, 6) matrix each time is the difference between a matvec and
    a matrix build in the engine's warm path.
    """
    dm = design_matrix(hkl) if design is None else design
    q_pred = dm @ np.asarray(af, dtype=np.float64)
    # Drop predictions outside the observed Q range **before** matching.  The
    # trial set is sized for the whole search domain, so on any one cell most of
    # it is far out of range, and ``match_lines`` costs an (observed × predicted)
    # matrix: measured on an orthorhombic search, filtering first took a rejected
    # leaf from ~30 ms to well under one, and leaf rejection was 90 % of the run.
    window = k_sigma * float(np.max(sigma)) if len(sigma) else 0.0
    inside = ((q_pred >= float(np.min(q_obs)) - window)
              & (q_pred <= float(np.max(q_obs)) + window))
    q_pred, hkl_in = q_pred[inside], np.asarray(hkl)[inside]
    if not len(q_pred):
        return np.zeros(0, dtype=np.int64), np.zeros((0, 3), dtype=np.int64)
    order = np.argsort(q_pred)
    idx, _ = match_lines(q_obs, sigma, q_pred[order], k_sigma=k_sigma)
    hit = idx >= 0
    return np.flatnonzero(hit), hkl_in[order][idx[hit]]


def effective_sigma_sys(spec: SearchSpec, quality=None) -> tuple[float, bool]:
    """The systematic allowance to use, and whether it was **assumed**.

    Three cases, in priority order: the caller declared one; the data-quality
    report *measured* one (``shift.source == "measured"``, which needs reference
    positions and so is unusual at index time); or neither, in which case
    :data:`DEFAULT_UNKNOWN_SHIFT_DEG` is assumed and the second return value says
    so.  An assumed precision must never be reported as a measured one — the same
    rule ``PeakList.from_positions`` follows.
    """
    if spec.sigma_sys_deg > 0.0:
        return float(spec.sigma_sys_deg), False
    if (quality is not None and quality.shift is not None
            and quality.shift.source == "measured"
            and quality.shift.sigma_sys_deg > 0.0):
        return float(quality.shift.sigma_sys_deg), False
    return DEFAULT_UNKNOWN_SHIFT_DEG, True


def shift_allowance_diagnostic(sigma_sys: float) -> Diagnostic:
    """``INDEX_SHIFT_ALLOWANCE`` — the search widened its own tolerance, and by how
    much.  Reported because it is the difference between a cell and no cell, and
    because it biases the cell it finds."""
    return Diagnostic(
        level="info", code="INDEX_SHIFT_ALLOWANCE",
        message=(f"no systematic 2θ shift has been measured, so {sigma_sys:.3f}° "
                 "was added in quadrature to every line's fitted σ.  Measured on "
                 "a certified pattern, the fitted σ alone is ~11× too tight: the "
                 "true cell indexed no lines at all and the search returned "
                 "nothing"),
        where=[f"σ_sys = {sigma_sys:.3f}° 2θ (assumed)"],
        suggestion=("the cell a widened search finds absorbs the shift, so refine "
                    "the winner with a shift template "
                    "(refine_candidate(..., shift_template=...), or pass "
                    "shift_template in the SearchSpec) and quote *that* cell; "
                    "supply reference positions to assess_peak_list if you have "
                    "an internal standard"))


def refine_with_shift(fit, spec: SearchSpec, system: str, q_all: np.ndarray,
                      sigma: np.ndarray, two_theta: np.ndarray,
                      wavelength: float, line_index: np.ndarray,
                      hkl: np.ndarray):
    """Re-fit an accepted candidate with a shift column, if one was asked for.

    **This is what stops a widened search from reporting a biased cell.**  The
    search has to open its tolerance to cover an unmeasured systematic
    (:data:`DEFAULT_UNKNOWN_SHIFT_DEG`), and a cell fitted inside that window
    absorbs the shift: measured on the qarr corundum pattern, the trial-and-error
    engine returned a = 4.7659 Å against a certified 4.7593 (+1400 ppm) with the
    shift left in.  Fitting the template *after* the candidate survives is the order
    WP-1020 prescribes — a shift is only identifiable against reference positions,
    and a candidate cell is what supplies them.

    Returns the original fit unchanged when no template was requested, or when the
    shifted fit is worse (a template that does not help must not be forced on).
    """
    if spec.shift_template is None:
        return fit
    try:
        shifted = refine_candidate(
            q_all[line_index], sigma[line_index], hkl, system=system,
            two_theta=two_theta[line_index], wavelength=wavelength,
            shift_template=spec.shift_template)
    except (ValueError, np.linalg.LinAlgError):
        return fit
    return shifted if shifted.chi2_red <= fit.chi2_red else fit


def indexes_the_search_lines(line_index: np.ndarray, search: np.ndarray,
                             n_unindexed: int) -> bool:
    """Did this candidate index the lines the search was **driven by**?

    The acceptance bar has to be "all but ``n_unindexed`` of the *search* lines",
    not "at least that many lines somewhere in the pattern".  The two are wildly
    different once a pattern has more lines than the search uses: measured on a
    75-line monoclinic list, the second reading kept **17 607** candidates, because
    a 4-parameter metric indexes 18 of 75 lines by coincidence without difficulty.
    The first reading is also the honest one — those are the lines whose failure
    the tolerated-unindexed count was chosen against.
    """
    if not len(search):
        return True
    hit = int(np.count_nonzero(np.isin(search, line_index)))
    return hit >= len(search) - n_unindexed


def to_cell_candidate(cand: EngineCandidate, peaks: PeakList, *,
                      k_sigma: float = MATCH_SIGMA, n_unindexed: int = 0,
                      diagnostics: Sequence[Diagnostic] = (),
                      ) -> CellCandidate:
    """Score a candidate with the whole FoM panel and pack it for reporting.

    The panel — never a member — is what a candidate is ranked on: measured on
    this repo's own data, ``indexed_fraction`` alone put a 390-line wrong phase
    above the truth (``fom.py``'s module docstring).  This function is where an
    engine's internal answer becomes a comparable one, so it is also where the
    reflection ceiling is checked one last time: ``fom_panel`` enumerates.
    """
    fit = cand.fit
    tt, tt_esd = peaks.two_theta(), peaks.two_theta_esd()
    q, q_esd = peaks.q(), peaks.q_esd()
    inten = peaks.intensity()
    tt_max = float(np.max(tt)) if len(tt) else 90.0
    panel = cand.fom
    if not panel and reflection_ceiling_ok(fit.cell, peaks.wavelength, tt_max):
        panel = fom_panel(q, q_esd, inten, tt, tt_esd, fit.cell, cand.system,
                          cand.centring, peaks.wavelength, k_sigma=k_sigma,
                          n_unindexed=n_unindexed)
    esd = np.asarray(fit.cell_esd, dtype=np.float64)
    vol_esd = _volume_esd(fit)
    return CellCandidate(
        cell=tuple(float(v) for v in fit.cell),
        cell_esd=tuple(float(v) for v in esd),
        system=cand.system, centring=cand.centring,
        lattice_group=lattice_group(cand.system, cand.centring),
        volume=float(fit.volume), volume_esd=vol_esd,
        af=tuple(float(v) for v in fit.af),
        n_indexed=cand.n_indexed, n_lines=cand.n_lines,
        chi2_red=float(fit.chi2_red),
        shift_template=fit.shift_template,
        shift_coefficient=float(fit.shift_coefficient),
        shift_esd=float(fit.shift_esd),
        fom=panel, found_by=list(cand.found_by) or [cand.engine],
        diagnostics=list(diagnostics))


def _volume_esd(fit: CandidateFit) -> float:
    """σ(V) by the delta method through ∂V/∂(A..F).

    V = 1/√det G*, so ∂V/∂G* = −(V/2)·(G*)⁻ᵀ by Jacobi's formula — analytic for
    the same reason ``cell_jacobian`` is: the number is used to decide whether two
    candidates are the same lattice, not merely to print.
    """
    from .qspace import gstar_from_af

    gstar = gstar_from_af(fit.af)
    det = float(np.linalg.det(gstar))
    if det <= 0.0:
        return 0.0
    vol = det ** -0.5
    inv = np.linalg.inv(gstar)
    # d(det)/dG*_ij = det·inv_ji; A..F carry a factor 2 on the off-diagonals, so
    # the chain to (A..F) divides by that factor and counts the symmetric pair
    grad = np.array([
        -0.5 * vol * inv[0, 0], -0.5 * vol * inv[1, 1], -0.5 * vol * inv[2, 2],
        -0.5 * vol * inv[1, 2], -0.5 * vol * inv[0, 2], -0.5 * vol * inv[0, 1]])
    return float(np.sqrt(max(grad @ np.asarray(fit.cov_af) @ grad, 0.0)))


def dedup_groups(cands: Sequence[EngineCandidate],
                 ) -> list[list[EngineCandidate]]:
    """Group candidates that are the same lattice, best-fitting member first.

    WP-1020's χ² equality on the **Niggli-reduced** A..F, so a setting change is
    equality rather than an ambiguity — but keyed within a centring, because the
    same metric with two different centrings is two different *lattices* (one
    predicts half the lines of the other) and merging them would silently drop a
    hypothesis the figures of merit are there to choose between.

    The *groups*, not just the survivors, because WP-1024's consensus needs to
    know **which engines** produced one lattice: agreement is the confidence, so
    the membership is the answer and not a by-product.  :func:`dedup_candidates`
    is this function's first column.
    """
    from .reduce import equal_reduced, reduced_af

    #: reduce **once** per candidate, not once per comparison
    prepared: list[tuple[EngineCandidate, np.ndarray, float]] = []
    for cand in sorted(cands, key=lambda c: (-c.n_indexed, c.fit.chi2_red)):
        try:
            red = reduced_af(cand.fit.af)
        except (ValueError, np.linalg.LinAlgError, RuntimeError):
            continue
        prepared.append((cand, red, _reduced_volume(red)))

    kept: list[tuple[list[EngineCandidate], np.ndarray, float]] = []
    for cand, red, volume in prepared:
        for group, other_red, other_volume in kept:
            # volume gate first: two lattices whose reduced volumes differ by more
            # than a per-cent cannot pass a χ² test on their metrics, and this is
            # what keeps the pass from being N² pinv solves as well as N² reductions
            if abs(volume - other_volume) > DEDUP_VOLUME_RTOL * max(volume,
                                                                    other_volume):
                continue
            other = group[0]
            if other.centring != cand.centring or other.system != cand.system:
                continue
            try:
                same, _chi2 = equal_reduced(red, other_red,
                                            cov_a=cand.fit.cov_af,
                                            cov_b=other.fit.cov_af)
            except (ValueError, np.linalg.LinAlgError):
                same = False
            if same:
                group.append(cand)
                break
        else:
            kept.append(([cand], red, volume))
    return [group for group, _red, _vol in kept]


def dedup_candidates(cands: Sequence[EngineCandidate],
                     ) -> list[EngineCandidate]:
    """The best-fitting member of each distinct lattice — :func:`dedup_groups`
    with the membership dropped."""
    return [group[0] for group in dedup_groups(cands)]


def _reduced_volume(red: np.ndarray) -> float:
    from .qspace import gstar_from_af
    det = float(np.linalg.det(gstar_from_af(red)))
    return det ** -0.5 if det > 0.0 else float("inf")


def rank_candidates(cands: Sequence[EngineCandidate], peaks: PeakList, *,
                    k_sigma: float = MATCH_SIGMA,
                    n_unindexed: int = 0,
                    max_candidates: int = DEFAULT_MAX_CANDIDATES,
                    shortlist: int = 4,
                    ) -> list[EngineCandidate]:
    """Dedup, score with the FoM panel, and rank by Borda over the whole panel.

    **Ranking happens here rather than in each engine, and it is not on a
    member.**  ``indexed_fraction`` alone put a 390-line wrong phase above the
    truth on this repo's own data (``fom.py``); on synthetic data the same shape
    appears as supercells, which index every observed line *exactly* and so tie
    the truth on every forward-looking figure — they lose only on
    ``predicted_seen_fraction``, and only a panel sees that.

    The panel costs a reflection enumeration per candidate, so a cheap pre-rank
    picks the shortlist: **most indexed lines first, then smallest volume**. That
    order is conservative in the direction that matters — a supercell can tie the
    truth on lines indexed but never beat it, and it is larger by construction,
    so the truth cannot be shortlisted out by its own supercell.
    """
    kept = dedup_candidates(cands)
    kept.sort(key=lambda c: (-c.n_indexed, c.volume))
    kept = kept[:max(shortlist * max_candidates, max_candidates)]
    if not kept:
        return []
    for cand in kept:
        cand.fom = _panel_for(cand, peaks, k_sigma, n_unindexed)
    scored = [c for c in kept if c.fom]
    unscored = [c for c in kept if not c.fom]
    if scored:
        from .fom import borda_scores
        scores = borda_scores([c.fom for c in scored])
        scored = [c for _s, _i, c in sorted(
            ((-float(s), i, c) for i, (s, c) in enumerate(zip(scores, scored))))]
    return (scored + unscored)[:max_candidates]


def _panel_for(cand: EngineCandidate, peaks: PeakList, k_sigma: float,
               n_unindexed: int = 0):
    tt, tt_esd = peaks.two_theta(), peaks.two_theta_esd()
    tt_max = float(np.max(tt)) if len(tt) else 90.0
    if not reflection_ceiling_ok(cand.cell, peaks.wavelength, tt_max):
        return []
    try:
        return fom_panel(peaks.q(), peaks.q_esd(), peaks.intensity(), tt, tt_esd,
                         cand.cell, cand.system, cand.centring, peaks.wavelength,
                         k_sigma=k_sigma, n_unindexed=n_unindexed)
    except (ValueError, RuntimeError):
        return []


def incomplete_diagnostic(engine: str, systems: Sequence[str],
                          seconds: float) -> Diagnostic:
    """``INDEX_SEARCH_INCOMPLETE`` — the budget ran out before the domain did.

    Its whole content is that a *negative* result from these systems is not
    evidence: an exhaustive engine's silence means "no such cell" only when it
    finished.
    """
    return Diagnostic(
        level="warning", code="INDEX_SEARCH_INCOMPLETE",
        message=(f"the {engine} search did not finish "
                 f"{', '.join(systems)} within {seconds:g} s per system, so "
                 "finding no cell there is not evidence that none exists"),
        where=list(systems),
        suggestion=("raise budget_seconds, or narrow the search — a smaller "
                    "max_volume or a shorter d-axis range costs exponentially "
                    "less than more time buys.  Cost grows with the metric "
                    "degrees of freedom (" +
                    ", ".join(f"{s} {METRIC_DOF[s]}" for s in systems
                              if s in METRIC_DOF) + ")"))


__all__ = ["CENTRINGS", "DEFAULT_BUDGET_SECONDS", "DEFAULT_MAX_CANDIDATES",
           "DEFAULT_MAX_D_AXIS", "DEFAULT_MIN_D_AXIS", "DEFAULT_MIN_VOLUME",
           "DEFAULT_N_UNINDEXED", "DEFAULT_SEARCH_LINES",
           "MAX_PREDICTED_REFLECTIONS", "SYSTEM_ORDER", "Budget",
           "EngineCandidate", "EngineResult", "SearchSpec", "assign_lines",
           "DEFAULT_UNKNOWN_SHIFT_DEG", "dedup_candidates", "dedup_groups",
           "effective_sigma_sys", "engine_descriptions", "engine_names",
           "indexes_the_search_lines", "refine_with_shift",
           "shift_allowance_diagnostic",
           "get_engine", "incomplete_diagnostic", "predicted_reflection_count",
           "reflection_ceiling_ok", "register_engine", "to_cell_candidate",
           "trial_hkl"]

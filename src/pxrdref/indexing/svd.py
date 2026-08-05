"""Engine C — SVD-Index: propose a metric at random, then let the *assignment*
converge.

*Source*: Coelho, A. A. (2003), *J. Appl. Cryst.* **36**, 86-95, "Indexing of
powder diffraction patterns by iterative use of singular value decomposition".
**Papers only** — TOPAS is closed source and none of it was consulted (CLAUDE.md).

**Where it sits between the other two.**  WP-1021's dichotomy *bounds* Q over
boxes of metrics and is exhaustive; WP-1022's trial and error *assumes* the hkl of
a few base lines and solves the metric exactly.  This one does neither: it starts
from a random metric and alternates two steps that are each trivial —

    assign every observed line to its nearest calculated line;
    re-solve A..F from that assignment by linear least squares

— until the assignment stops changing (Coelho's Table 1, ~3-9 iterations here).
Neither step needs a tolerance, which is the property Coelho advertises over the
dichotomy method: *"it does not require errors in the input d-spacings as input"*.
So its failure mode is a third one again — not a wide domain, not a poisoned base
line, but a **starting metric in the wrong basin** — and that is what makes its
agreement with the other two worth something (``engines.py``).

**WP-1023's Monte Carlo no-go does not fence this, and the distinction is the
whole reason the WP exists.**  That spike scored *raw random cells*.  Both working
Monte Carlo indexers refine every proposal: SVD-Index iterates to a fixed hkl
assignment (this module), and McMaille takes 200-5000 local steps per proposal
(Le Bail 2004 §III).  WP-1023's number stands for what it measured — unrefined
random-cell scoring does not rank — and says nothing about a refined one.

## What was measured before this module was written (WP-1040 task 0)

On the known-cell corpus, one random start per call, calls to Table 1 before the
true lattice is first reached (``reduce.same_lattice``), median of five seeded
runs.  Coelho's own averages are quoted beside them, on simulated 20-line sets:

=================  ==========  =============  ===========
dataset            system      calls to truth  Coelho avg
=================  ==========  =============  ===========
SRM 660c LaB6      cubic        1              1.3
11-BM NAC          cubic        6              1.3
qarr zincite       hexagonal    107            8.3
qarr zircon        tetragonal   150            26.1
GSAS-II FAP        hexagonal    389            8.3
bethanechol F      monoclinic   ~15 000        78
qarr corundum      trigonal     **never**      —
=================  ==========  =============  ===========

Two of those rows are the reason the WP is a go rather than a curiosity.
**bethanechol set F is reached at all**: it is the benchmark the milestone bar is
written on, and ``tests/test_acceptance_indexing.py`` records that an exhaustive
dichotomy over the paper's own domain returns **0 candidates and never finishes**
at 240 s *and* at 900 s.  And the wall clock is a different order: a Table 1 call
is 0.2-3 ms, so the whole ladder is seconds where dichotomy is minutes.

The corpus is also where the four rules below were measured, each of which
contradicts something reasoned from the algorithm's structure.

**1. The N_c/N_o gate is a volume *window*, computable before the search.**
Coelho uses step (ii) as a per-trial abort and step (iv)(a) as a stopping rule
discovered during the sweep.  But N_c — distinct calculated d-spacings inside the
observed sphere — is proportional to the cell volume at fixed Q_max, system and
centring, so one probe measures κ = N_c/V and the gate *is* a bound on V:

    V ∈ [N_o/(3κ), 4·N_o/κ]

a factor-12 window, i.e. 27 rungs of Coelho's ν₁ = 1.1 ladder.  Measured on all
nine corpus datasets, **the window contains the true volume every time**, and
placing the ladder inside it rather than sweeping from an arbitrary floor is what
takes the searches to the seconds above.  See :func:`volume_window`.

**2. N_c counts distinct calculated d-spacings, not hkl** — Table 1's caption says
one and §2's prose the other, and only the prose can be right: LaB6 to 149° 2θ has
~244 Friedel-unique hkl inside its own sphere against 20 driven lines, so an hkl
count puts N_c/N_o at ~12 and the gate refuses the certified cubic cell outright.

**3. The impurity cut belongs in the last pass only, and Coelho says so.**  §2.4
runs Table 1 three times per random start and drops far-lying observed lines only
in the third.  Reasoning from real data says the opposite — our peak lists carry
artifacts that no iteration will index — and the corpus says the reasoning is
wrong: moving the cut into the first pass takes zincite from 5/5 seeded runs to
1/5 and zircon and FAP from 5/5 to **0/5**.  A random starting metric predicts
lines nowhere near the observed ones, so a cut applied there removes nearly
everything and the call dies before it can iterate anywhere.

**4. One line below the lattice's longest d-spacing destroys the eq. (4)
weighting entirely** — and this is the failure simulated data cannot show.  The
qarr corundum list opens at 5.17° 2θ (d = 17 Å) where the pattern itself starts at
5.00°, an edge artifact the acceptance suite already tolerates with
``n_unindexed = 3``.  Corundum's longest real d is 4.33 Å, so that line is 3.9×
beyond anything the lattice can produce; W = d_o⁴·|Δ2θ|·I_o then weights it ~10⁴
above the shortest line, the solve answers with c ≈ 51 Å, and the N_c gate kills
the call.  Measured: **0 convergences in 4000 random starts**, against 3293 with
that one line removed.  Coelho's own impurity test (Table 6) places impurity
d-spacings between the smallest observed d and 1.5× the largest, so it never
reaches this case.  The fallback is :data:`TRIM_RETRY` and it is a *retry*, not a
default, because a budgeted trim rescues corundum and costs every other dataset
(zircon 58 → 1 hits per 3000 starts, zincite 317 → 205, bethanechol F 1 → 0).
"""

from __future__ import annotations

from functools import lru_cache

import numpy as np

from ..schemas.common import Diagnostic
from ..schemas.indexing import PeakList
from .engines import (
    SYSTEM_ORDER,
    Budget,
    EngineCandidate,
    EngineResult,
    SearchSpec,
    assign_lines,
    dedup_candidates,
    effective_sigma_sys,
    incomplete_diagnostic,
    indexes_the_search_lines,
    rank_candidates,
    refine_with_shift,
    reflection_ceiling_ok,
    register_engine,
    search_line_order,
    shift_allowance_diagnostic,
)
from .fom import LINE_COINCIDENCE_RTOL
from .qspace import (
    af_from_cell,
    cell_from_af,
    design_matrix,
    metric_basis,
    refine_candidate,
    sigma_effective,
    trial_hkl,
)

#: Iterations of Table 1 step (iv) before a call gives up.  Coelho's N_T1 = 20,
#: and it is generous: the corpus converges in 3-9, and his §2.4 reports ~5 for
#: the first pass and ~1 for the second and third.
MAX_ITERATIONS = 20
#: Table 1 step (ii): the ratio of calculated to observed lines outside which a
#: trial is abandoned.  Coelho's own reading of what it costs — *"this condition
#: may cause failure if more than 75 % of the observed d-spacings are missing or
#: if more than 33 % of the observed d-spacings are impurity lines"*.
NC_NO_LO, NC_NO_HI = 1.0 / 3.0, 4.0
#: ν₁ of Coelho eq. (3) — the factor the volume ladder grows by per rung.
VOLUME_LADDER_RATIO = 1.1
#: Coelho Table 3 (captioned "Table 2" in the scan): (N₁, N₂) per crystal system.
#: N₁ random starts per volume rung, then N₂ − 1 further rounds perturbing the
#: best.  The small values at high symmetry are not a shortcut — a cubic metric
#: has one free parameter and a triclinic one has six.
CONTROL: dict[str, tuple[int, int]] = {
    "cubic": (1, 1),
    "hexagonal": (10, 2),
    "trigonal": (10, 2),
    "tetragonal": (10, 2),
    "orthorhombic": (200, 2),
    "monoclinic": (200, 2),
    "triclinic": (200, 3),
}
#: Exponent m of the weighting function W = d_o^m·|Δ2θ|·I_o (Coelho eq. 4).
#:
#: **Four, fixed — and the range this package does *not* randomise it over is a
#: correction to the WP's own reading of the paper.**  §3.2 randomises m between
#: **0 and 6** (the "0-4" in WP-1040's context section is a misreading; 4 is where
#: "an optimum setting for m occurs", a different sentence).  His 4.4 → 8.4 →
#: 11.8 % "decomposition" is likewise two experiments rather than one: 4.4 % is
#: the triclinic Δ = 0.3 perturbation rate of §3.1, while 8.4 and 11.8 are
#: single-pass Table 2 runs from §3.2.  Measured here on the corpus, randomising m
#: is not free either way — it helps LaB6 at large Δ and hurts NAC (100 % → 51-67
#: % at every Δ) — so the fixed optimum is kept and the randomisation is recorded
#: as unreproduced rather than adopted on the paper's word.
WEIGHT_EXPONENT = 4.0
#: Lines dropped, at most, when a search that found nothing is retried.  See rule
#: 4 in the module docstring: this rescues one corpus dataset and costs every
#: other, so it runs only after silence, the same posture as ``trial_error``'s
#: dominant-zone probe.
TRIM_RETRY = 1
#: Largest |h| the per-iteration enumeration will build a box for.  A crash guard
#: in the same family as ``engines.reflection_ceiling_ok`` and needed for the same
#: reason: the loop re-enumerates from the *current* trial metric, and a metric
#: that has run away asks for a box that will not fit in memory.
MAX_BOX_INDEX = 40
#: Random starts the κ probe averages over, and the reference volume it uses.
#: Twenty-four is enough for a median that moves the window's endpoints by under a
#: per cent, and the window is a factor of twelve wide.
KAPPA_PROBES, KAPPA_VOLUME = 24, 500.0
#: Angle range random triclinic and monoclinic starts are drawn from — Coelho §3's
#: own test-lattice generation (90-130°).
ANGLE_LO, ANGLE_HI = 90.0, 130.0


@lru_cache(maxsize=32)
def _hkl_box(max_index: int, centring: str) -> np.ndarray:
    """``trial_hkl`` memoised: the loop re-enumerates once per iteration and the
    box usually does not change between them."""
    hkl = trial_hkl(max_index, centring)
    hkl.setflags(write=False)
    return hkl


def _predicted(af: np.ndarray, basis: np.ndarray, centring: str, q_max: float):
    """Distinct calculated ``(Q, hkl)`` inside the observed sphere.

    The box is sized from the *current* metric — ``hmax = floor(a·√Q_max) + 1``
    per axis, the arithmetic ``engines.predicted_reflection_count`` guards — so
    the enumeration tracks the trial cell rather than covering the whole domain.

    Merged to distinct **lines** at :data:`~pxrdref.indexing.fom.LINE_COINCIDENCE_RTOL`,
    which is what makes ``len(q)`` the N_c the gate wants (module docstring, rule 2).
    """
    try:
        cell = cell_from_af(af)
    except ValueError:
        return np.zeros(0), np.zeros((0, 3), dtype=np.int64)
    hmax = int(np.floor(max(cell[:3]) * np.sqrt(max(q_max, 1e-12)))) + 1
    if hmax > MAX_BOX_INDEX:
        return np.zeros(0), np.zeros((0, 3), dtype=np.int64)
    hkl = _hkl_box(hmax, centring)
    q = design_matrix(hkl) @ np.asarray(af, dtype=np.float64)
    inside = (q > 0.0) & (q <= q_max)
    q, hkl = q[inside], hkl[inside]
    if not len(q):
        return q, hkl
    order = np.argsort(q)
    q, hkl = q[order], hkl[order]
    keep = np.ones(len(q), dtype=bool)
    keep[1:] = np.diff(q) > LINE_COINCIDENCE_RTOL * np.maximum(q[1:], 1e-300)
    return q[keep], hkl[keep]


def _nearest_assignment(q_obs: np.ndarray, intensity: np.ndarray,
                        q_cal: np.ndarray) -> np.ndarray:
    """Table 1 step (iii): each observed line takes its nearest calculated one.

    Returns an index into ``q_cal`` per observed line, ``-1`` where the line is
    left un-indexed.  **There is no tolerance window here at all** — that is the
    whole of Coelho's "does not require errors in the input d-spacings as input",
    and it is why this engine's silence means something different from
    dichotomy's.

    A calculated line claimed by more than one observed keeps the observed with
    the smallest 1/(d_o²·I_o), i.e. the largest I_o/Q_o; the rest are un-indexed,
    which is *"the key factor in determining impurity lines"* (§2).  This is also
    the only place in any of the three engines where an observed **intensity**
    changes what the search does.
    """
    if not len(q_cal):
        return np.full(len(q_obs), -1, dtype=np.int64)
    pos = np.searchsorted(q_cal, q_obs)
    lo = np.clip(pos - 1, 0, len(q_cal) - 1)
    hi = np.clip(pos, 0, len(q_cal) - 1)
    nearest = np.where(np.abs(q_cal[hi] - q_obs) < np.abs(q_cal[lo] - q_obs),
                       hi, lo)
    out = np.full(len(q_obs), -1, dtype=np.int64)
    claimed: set[int] = set()
    for i in np.argsort(-intensity / np.maximum(q_obs, 1e-300)):
        c = int(nearest[i])
        if c not in claimed:
            claimed.add(c)
            out[i] = c
    return out


def svd_iterate(af0: np.ndarray, q_obs: np.ndarray, two_theta: np.ndarray,
                intensity: np.ndarray, basis: np.ndarray, centring: str,
                wavelength: float, *, m: float = WEIGHT_EXPONENT,
                sigma: np.ndarray | None = None, trim: int = 0,
                max_iterations: int = MAX_ITERATIONS,
                ) -> tuple[np.ndarray, bool, int, str]:
    """One call to Coelho's Table 1.  Returns ``(af, converged, iterations, why)``.

    The weighting is eq. (4), ``W = d_o^m·|Δ2θ|·I_o``, applied to both sides of the
    quadratic form.  Note that it deliberately weights the *worst-fitting* lines
    **up**: §2.2's argument is that a large discrepancy is where the information
    about how to move is, and the paper measures the choice rather than asserting
    it (per-trial success 4.4 → 11.8 % on triclinic simulations).  It is the
    opposite of a least-squares weight, which is why the fitted cell this returns
    is a *starting point* and never the answer — ``search_svd`` re-fits every
    survivor through :func:`~pxrdref.indexing.qspace.refine_candidate`, on 1/σ(Q),
    to get a cell and a covariance anyone may quote.

    **Convergence is tested against every assignment seen, not only the previous
    one.**  Coelho's step (iv) says "the same as in the previous iteration", which
    a 2-cycle never satisfies — measured on four of the nine corpus datasets,
    where the loop reached the true metric and then burned all twenty iterations
    alternating between two assignments before reporting failure.
    """
    af = np.asarray(af0, dtype=np.float64).copy()
    q_max = float(q_obs.max())
    n_o = len(q_obs)
    n_free = basis.shape[0]
    seen: set[bytes] = set()
    for it in range(1, max_iterations + 1):
        q_cal, hkl_cal = _predicted(af, basis, centring, q_max)
        if not (NC_NO_LO <= len(q_cal) / n_o <= NC_NO_HI):
            return af, False, it, "gate"
        assign = _nearest_assignment(q_obs, intensity, q_cal)
        idx = np.flatnonzero(assign >= 0)
        if trim > 0 and len(idx) - trim >= n_free + 1:
            dq = np.abs(q_obs[idx] - q_cal[assign[idx]])
            scale = (np.asarray(sigma)[idx] if sigma is not None
                     else np.maximum(q_obs[idx], 1e-300))
            idx = idx[np.argsort(dq / np.maximum(scale, 1e-300))][:len(idx) - trim]
        if len(idx) < n_free + 1:
            return af, False, it, "too-few-indexed"

        hkl = hkl_cal[assign[idx]]
        key = hkl.tobytes() + idx.tobytes()
        if key in seen:
            return af, True, it, "converged"
        seen.add(key)

        q_i = q_obs[idx]
        rows = design_matrix(hkl) @ basis.T
        d_o = 1.0 / np.sqrt(np.maximum(q_i, 1e-300))
        tt_cal = np.degrees(2.0 * np.arcsin(np.clip(
            wavelength * np.sqrt(np.maximum(q_cal[assign[idx]], 0.0)) / 2.0,
            -1.0, 1.0)))
        dtt = np.abs(two_theta[idx] - tt_cal)
        # |Δ2θ| = 0 would delete the row rather than merely stop it pulling, and
        # deleting a row changes the *rank* of the system, which is a different
        # claim about what the lines determine.  Floored well below the smallest
        # real discrepancy instead.
        floor = float(dtt[dtt > 0.0].min()) * 1e-3 if np.any(dtt > 0.0) else 1e-9
        w = d_o ** m * np.maximum(dtt, floor) * intensity[idx]
        w = np.where(np.isfinite(w) & (w > 0.0), w, 0.0)
        if not np.any(w > 0.0):
            return af, False, it, "degenerate-weights"
        try:
            theta, *_ = np.linalg.lstsq(rows * w[:, None], q_i * w, rcond=None)
        except np.linalg.LinAlgError:
            return af, False, it, "lstsq-failed"
        af_new = basis.T @ theta
        if not np.all(np.isfinite(af_new)):
            return af, False, it, "non-finite"
        af = af_new
    return af, False, max_iterations, "max-iterations"


# ----------------------------------------------------------------------
# The gate, read as a volume window
# ----------------------------------------------------------------------
def _random_af(system: str, rng, d_lo: float, d_hi: float) -> np.ndarray:
    """(A..F) of a random conventional cell of ``system`` with axes in range."""
    a, b, c = rng.uniform(d_lo, d_hi, size=3)
    if system == "cubic":
        cell = (a, a, a, 90.0, 90.0, 90.0)
    elif system == "tetragonal":
        cell = (a, a, c, 90.0, 90.0, 90.0)
    elif system in ("hexagonal", "trigonal"):
        cell = (a, a, c, 90.0, 90.0, 120.0)
    elif system == "orthorhombic":
        cell = (a, b, c, 90.0, 90.0, 90.0)
    elif system == "monoclinic":
        cell = (a, b, c, 90.0, float(rng.uniform(ANGLE_LO, ANGLE_HI)), 90.0)
    else:
        ang = rng.uniform(ANGLE_LO, ANGLE_HI, size=3)
        cell = (a, b, c, float(ang[0]), float(ang[1]), float(ang[2]))
    return af_from_cell(cell)


def _project(af: np.ndarray, basis: np.ndarray) -> np.ndarray:
    return basis.T @ np.linalg.lstsq(basis.T, af, rcond=None)[0]


def scale_to_volume(af: np.ndarray, volume: float) -> np.ndarray:
    """Scale (A..F) so the real-space cell volume is ``volume`` — Table 2 step (i).

    ``V ∝ det(G*)^(-1/2)`` and det scales as s³ under ``A..F → s·(A..F)``, so
    ``V → V·s^(-3/2)``.
    """
    from ..crystallography.lattice import cell_volume
    try:
        v0 = float(cell_volume(*cell_from_af(af)))
    except ValueError:
        return af
    if not np.isfinite(v0) or v0 <= 0.0 or volume <= 0.0:
        return af
    return af * (v0 / volume) ** (2.0 / 3.0)


def volume_window(n_observed: int, system: str, centring: str, q_max: float,
                  seed: int = 0) -> tuple[float, float]:
    """The volume range Coelho's N_c/N_o gate admits, computed **before** the search.

    N_c is proportional to V at fixed Q_max, system and centring — one reciprocal
    lattice point per reciprocal-cell volume, divided by the multiplicity of the
    coincidences a symmetric lattice has — so a handful of probe cells measure
    κ = N_c/V and the gate becomes a bound on volume rather than a per-trial
    verdict:

        V ∈ [N_o/(3κ), 4·N_o/κ]

    always a factor of twelve, so the value is in *where* it sits, not how wide it
    is.  Measured on all nine of WP-1040's corpus datasets, it contains the true
    volume every time — and a ladder placed inside it rather than swept from an
    arbitrary floor is most of why this engine costs seconds (module docstring).

    Returns ``(0.0, inf)`` when no probe cell produced a usable prediction, so a
    caller's own bounds decide and the window never *excludes*: the one failure a
    search bound may not have is excluding the true cell (WP-1019's envelope).
    """
    basis = metric_basis(system)
    rng = np.random.default_rng(seed)
    kappas = []
    for _ in range(KAPPA_PROBES):
        af = _project(scale_to_volume(_random_af(system, rng, 2.0, 25.0),
                                      KAPPA_VOLUME), basis)
        q_cal, _hkl = _predicted(af, basis, centring, q_max)
        if len(q_cal):
            kappas.append(len(q_cal) / KAPPA_VOLUME)
    if not kappas:
        return 0.0, float("inf")
    kappa = float(np.median(kappas))
    if kappa <= 0.0:
        return 0.0, float("inf")
    return (n_observed * NC_NO_LO / kappa, n_observed * NC_NO_HI / kappa)


# ----------------------------------------------------------------------
# The engine
# ----------------------------------------------------------------------
def search_svd(peaks: PeakList, *, spec: SearchSpec | None = None,
               quality=None, cancel=None, progress=None) -> EngineResult:
    """Propose metrics at random over a volume ladder; iterate each to a fixed
    assignment; keep what explains the driven lines.

    **Stochastic, and the seed is part of the answer.**  ``SearchSpec.seed`` is
    recorded in the result's stats, so a run is reproducible from what it reports
    — the one thing the other two engines, which are deterministic, never had to
    say.  Coelho's own note applies and is worth passing on: *"the Monte Carlo
    nature of Table 2 implies different results every time SVD-Index is run"*, so
    running it again searches more of the space rather than repeating itself.
    """
    spec = spec or SearchSpec()
    q_all = peaks.q()
    tt_all = peaks.two_theta()
    sigma_sys, assumed = effective_sigma_sys(spec, quality)
    sigma = sigma_effective(peaks.q_esd(), tt_all, peaks.wavelength, sigma_sys)
    inten = peaks.intensity()
    tt_max = float(peaks.two_theta_max)

    result = EngineResult(engine="svd")
    if len(q_all) < 2:
        result.diagnostics.append(Diagnostic(
            level="error", code="INDEX_DATA_INSUFFICIENT",
            message="a lattice cannot be constrained by fewer than two lines",
            where=[f"{len(q_all)} usable lines"],
            suggestion="run assess_peak_list before searching"))
        return result

    search_lines = search_line_order(peaks, spec)
    systems = [s for s in SYSTEM_ORDER if s in spec.systems]
    raw: list[EngineCandidate] = []
    incomplete: list[str] = []

    for system in systems:
        # not started ⇒ not claimed — the rule both other engines follow, and what
        # keeps "not reached" distinct from "truncated" (WP-1037)
        if cancel is not None and bool(cancel):
            break
        result.systems_searched += (system,)
        if progress is not None:
            progress.start(f"svd:{system}", engine="svd", system=system)
        budget = Budget(spec.budget_seconds, cancel)
        found, stats, complete = _search_system(
            peaks, system, spec, budget, q_all, sigma, tt_all, inten, tt_max,
            search_lines, quality)
        if not found and not budget.expired():
            # The retry that explains a silence, and it pays for itself only when
            # there is a silence to explain (module docstring, rule 4).  It shares
            # the system's **existing** budget rather than taking a fresh one: a
            # second Budget here would make the engine cost 2·budget_seconds per
            # system and quietly falsify ``engines.estimate_ceiling``, whose whole
            # claim is that the per-system budgets are hard ceilings the engines
            # enforce.  So the retry runs on what the search left over, and gets
            # nothing when the search used it all — which is the right answer.
            more, more_stats, _c = _search_system(
                peaks, system, spec, budget, q_all,
                sigma, tt_all, inten, tt_max, search_lines, quality,
                trim=TRIM_RETRY)
            found = more
            for key, value in more_stats.items():
                stats[f"trim.{key}"] = value
        raw.extend(found)
        result.search_complete[system] = complete
        for key, value in stats.items():
            result.stats[f"{system}.{key}"] = value
        if not complete:
            incomplete.append(system)
        if progress is not None:
            progress.end(f"svd:{system}", engine="svd", system=system,
                         n_candidates=len(found), complete=complete)

    result.candidates = rank_candidates(raw, peaks, k_sigma=spec.k_sigma,
                                        n_unindexed=spec.n_unindexed,
                                        max_candidates=spec.max_candidates,
                                        q_match=sigma)
    result.stats["candidates.raw"] = float(len(raw))
    result.stats["sigma_sys_deg"] = round(sigma_sys, 5)
    result.stats["seed"] = float(spec.seed)
    if assumed:
        result.diagnostics.append(shift_allowance_diagnostic(sigma_sys))
    if incomplete:
        result.diagnostics.append(
            incomplete_diagnostic("svd", incomplete, spec.budget_seconds))
    return result


def _search_system(peaks: PeakList, system: str, spec: SearchSpec,
                   budget: Budget, q_all: np.ndarray, sigma: np.ndarray,
                   tt_all: np.ndarray, inten: np.ndarray, tt_max: float,
                   search_lines: np.ndarray, quality, *, trim: int = 0):
    """Coelho's Table 2 over one crystal system: the volume ladder.

    ``search_complete`` is **False whenever the ladder was not walked to its
    end** — by the budget or by the caller's token.  A stochastic engine's
    silence is weaker evidence than an exhaustive one's even when it *did*
    finish, so this flag is the floor of what may be claimed, not the ceiling:
    consensus reads it, and ``EngineResult.complete`` is what stops an absence
    being read as "no such cell".
    """
    basis = metric_basis(system)
    n1, n2 = CONTROL.get(system, (200, 2))
    q_search = q_all[search_lines]
    tt_search = tt_all[search_lines]
    i_search = inten[search_lines]
    sig_search = sigma[search_lines]
    q_max = float(q_search.max())

    # **Not** ``hash(system)``: python salts string hashes per process, so a run
    # seeded from ``SearchSpec.seed`` would still not reproduce — which is the one
    # promise a stochastic engine has to keep.  The system's position in
    # ``SYSTEM_ORDER`` is a stable integer and decorrelates the systems' streams.
    rng = np.random.default_rng(
        (int(spec.seed), SYSTEM_ORDER.index(system), int(trim)))
    fallback = (float(quality.volume_envelope[system])
                if quality is not None and system in quality.volume_envelope
                else 8000.0)
    found: list[EngineCandidate] = []
    seen: set[tuple[int, ...]] = set()
    calls = 0
    complete = True

    for centring in spec.centrings_for(system):
        gate_lo, gate_hi = volume_window(len(q_search), system, centring, q_max,
                                         seed=spec.seed)
        v_lo = max(spec.min_volume, gate_lo)
        v_hi = min(spec.volume_limit(system, fallback), gate_hi)
        if not (v_lo < v_hi):
            continue
        v1 = v_lo
        best_af, best_score = None, -np.inf
        while v1 <= v_hi:
            if budget.expired():
                return found, {"calls": float(calls),
                               "seconds": round(budget.elapsed, 3)}, False
            for _ in range(n1):
                af0 = _project(scale_to_volume(
                    _random_af(system, rng, spec.min_d_axis, spec.max_d_axis),
                    v1), basis)
                af, converged, _it, _why = svd_iterate(
                    af0, q_search, tt_search, i_search, basis, centring,
                    peaks.wavelength, sigma=sig_search, trim=trim)
                calls += 1
                if not converged:
                    continue
                score = _keep(af, basis, system, centring, spec, peaks, q_all,
                              sigma, tt_all, tt_max, search_lines, seen, found,
                              v_hi)
                if score > best_score:
                    best_af, best_score = af, score
            for _ in range(n2 - 1):
                if best_af is None or budget.expired():
                    break
                theta = np.linalg.lstsq(basis.T, best_af, rcond=None)[0]
                for k in range(n1):
                    # Coelho Table 2 step (ii): R uniform on
                    # [0.99 − 0.49·k/N₁, 1.5 + 0.49·k/N₁], widening as the round
                    # goes on.  Drawn **per free metric parameter** rather than
                    # per X_nn: scaling A..F independently leaves the crystal
                    # system's subspace, so a cubic A = B = C would not survive it.
                    lo = 0.99 - 0.49 * k / max(n1, 1)
                    hi = 1.50 + 0.49 * k / max(n1, 1)
                    af0 = basis.T @ (theta * rng.uniform(lo, hi,
                                                         size=theta.shape))
                    af, converged, _it, _why = svd_iterate(
                        af0, q_search, tt_search, i_search, basis, centring,
                        peaks.wavelength, sigma=sig_search, trim=trim)
                    calls += 1
                    if converged:
                        _keep(af, basis, system, centring, spec, peaks, q_all,
                              sigma, tt_all, tt_max, search_lines, seen, found,
                              v_hi)
            v1 *= VOLUME_LADDER_RATIO
        if len(found) > 2000:
            found = dedup_candidates(found)
    return (found, {"calls": float(calls), "seconds": round(budget.elapsed, 3)},
            complete)


def _keep(af, basis, system, centring, spec, peaks, q_all, sigma, tt_all,
          tt_max, search_lines, seen, found, vol_max) -> float:
    """Re-fit a converged metric properly, then apply the shared acceptance bar.

    The SVD loop's own cell is fitted under eq. (4)'s deliberately perverse
    weighting, so it is never the cell reported: this re-assigns with the
    package's per-line window and re-fits on 1/σ(Q) through ``refine_candidate``,
    which is also what supplies the ``cov_af`` consensus dedup needs.  The bar
    afterwards is ``indexes_the_search_lines`` — the same absolute budget both
    other engines are held to, so three engines' candidates mean the same thing.
    """
    try:
        cell = cell_from_af(af)
    except ValueError:
        return -np.inf
    if not reflection_ceiling_ok(cell, peaks.wavelength, tt_max):
        return -np.inf
    key = _solution_key(af)
    if key in seen:
        return -np.inf
    seen.add(key)

    d_max = spec.max_d_axis
    q_hi = float(q_all.max() + spec.k_sigma * sigma.max())
    max_index = int(np.ceil(d_max * np.sqrt(max(q_hi, 1e-12)))) + 1
    hkl_full = trial_hkl(max_index, centring)
    dm_full = design_matrix(hkl_full)

    fit = None
    previous: bytes | None = None
    for _pass in range(3):
        line_index, assigned = assign_lines(q_all, sigma, hkl_full, af,
                                            k_sigma=spec.k_sigma, design=dm_full)
        if len(line_index) < basis.shape[0] + 1:
            return -np.inf
        stamp = line_index.tobytes()
        if stamp == previous:
            break
        previous = stamp
        try:
            fit = refine_candidate(q_all[line_index], sigma[line_index], assigned,
                                   system=system)
        except (ValueError, np.linalg.LinAlgError):
            return -np.inf
        af = fit.af
    if fit is None or fit.chi2_red > spec.k_sigma ** 2:
        return -np.inf
    if not indexes_the_search_lines(line_index, search_lines, spec.n_unindexed):
        return -np.inf
    fit = refine_with_shift(fit, spec, system, q_all, sigma, tt_all,
                            peaks.wavelength, line_index, assigned)
    if not (spec.min_volume <= fit.volume <= vol_max):
        return -np.inf
    found.append(EngineCandidate(
        fit=fit, system=system, centring=centring, engine="svd", hkl=assigned,
        line_index=line_index, n_lines=len(q_all)))
    return float(len(line_index)) - float(fit.chi2_red)


#: Relative grid a solved metric is hashed on before it is re-fitted.  A real cell
#: is reached by many different random starts, and re-fitting each of them is the
#: cost this avoids.
SAME_SOLUTION_RTOL = 1e-3


def _solution_key(af: np.ndarray) -> tuple[int, ...]:
    """A scale-**dependent** hash of a metric.

    The obvious form — ``round(af / (max|af| · rtol))`` — is scale *invariant*,
    and for a one-dimensional metric that is fatal rather than merely lossy:
    every cubic cell is ``(A, A, A, 0, 0, 0)``, so dividing by ``max|af|`` maps
    all of them to the same key and the first random start on the volume ladder
    silently blocks every later one.  Measured while writing this module: a clean
    synthetic cubic pattern returned **0 candidates** from 72 starts that
    included the truth.  So the quantised scale goes into the key too, on a
    logarithmic grid of the same relative width.
    """
    a = np.asarray(af, dtype=np.float64)
    scale = float(np.max(np.abs(a)))
    if not np.isfinite(scale) or scale <= 0.0:
        return (0,) * (len(a) + 1)
    decade = int(np.round(np.log(scale) / np.log1p(SAME_SOLUTION_RTOL)))
    return (decade, *np.round(a / (scale * SAME_SOLUTION_RTOL)).astype(np.int64))


register_engine(
    "svd", search_svd,
    "proposes metrics at random over a volume ladder and iterates SVD until the "
    "hkl assignment stops changing; needs no tolerance to search with, and is "
    "stochastic, so its failure mode is a bad starting basin rather than a wide "
    "domain or a bad base line")

__all__ = ["CONTROL", "MAX_ITERATIONS", "NC_NO_HI", "NC_NO_LO", "TRIM_RETRY",
           "VOLUME_LADDER_RATIO", "WEIGHT_EXPONENT", "scale_to_volume",
           "search_svd", "svd_iterate", "volume_window"]

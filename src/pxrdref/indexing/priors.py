"""Analogue priors — a stated cell or space group *steers* the search (WP-1045).

An agent (or a human with a database hit) often holds a structural analogue:
an isostructural compound whose cell and space group are approximately right.
The package's premise — a reasoning consumer given good surfaces beats a
mechanical rule — says give the reasoner a way to *state* that knowledge,
under three rules, each pinned by test:

1. **A prior reorders and seeds; it never injects a candidate past the
   engines.**  Its crystal system jumps the ``SYSTEM_ORDER`` queue in the
   system-major scheduler, and its metric seeds the stochastic engine's
   starting basin (``search_svd`` — the one engine that *has* a start; an
   exhaustive box and an exact enumeration do not).  A prior cell that is
   real is then *found* by the engines from the seeded start, so ``found_by``
   and ``grade`` keep their meaning.  The prior cell itself is additionally
   checked against the peak list through the same machinery the engines use
   (assign → refine → ``indexes_the_search_lines``), and what survives enters
   consensus as finder ``"prior"`` — merged into an engine candidate when
   they are one lattice (``found_by`` gains a member, the rank untouched), or
   **appended after the ranked list** when no engine agrees, which is what
   makes "a wrong prior changes no rank and no grade" structural rather than
   statistical: prior-only candidates never take part in the Borda ranking.
2. **A prior narrows *order*, never the box.**  No system is added or
   dropped, no range tightened or widened: a prior whose system the caller
   excluded, or whose cell lies outside the declared box, is reported as
   unusable rather than smuggled in.
3. **A prior used is recorded** — ``INDEX_PRIOR_USED`` names what was
   supplied and what it changed — because assumed knowledge must never look
   like measured knowledge (the ``INDEX_SHIFT_ALLOWANCE`` precedent).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..schemas.common import Diagnostic
from ..schemas.indexing import PeakList
from .engines import (
    SYSTEM_ORDER,
    EngineCandidate,
    SearchSpec,
    assign_lines,
    effective_shift_allowance,
    indexes_the_search_lines,
    refine_with_shift,
    search_line_order,
    search_volume_ceiling,
    trial_hkl,
)
from .qspace import af_from_cell, refine_candidate, sigma_effective

#: The finder name a prior-confirmed candidate carries in ``found_by``.
#: Deliberately **not** a registered engine: it never appears in
#: ``engines_run``, so a prior-only candidate fails the ``found_by ⊇
#: engines_run`` agreement test naturally (``engines_disagree``, capping) and
#: the gate needs no new vocabulary — stated, shift-consistent, unconfirmed.
PRIOR_FINDER = "prior"

#: Relative tolerance on axis equality and absolute tolerance (deg) on angle
#: equality when classifying a prior cell's crystal system.  Loose on purpose:
#: an analogue cell is approximate by declaration, and the cost of a wrong
#: *classification* is only search order — the candidate check below refines
#: in the classified system and simply fails if the metric cannot live there.
CLASSIFY_RTOL = 2e-3
CLASSIFY_ATOL_DEG = 0.25

#: Assign→refine passes a prior cell gets before its assignment is taken as
#: settled — the same small number the engines' own leaves use.
MAX_PRIOR_PASSES = 4

#: Trial-index grid guard: a prior whose longest axis needs more than this
#: many indices to reach the observed Q range is outside anything a powder
#: search can check (the ``MAX_TRIAL_HKL`` precedent, refused loudly rather
#: than capped silently).
MAX_PRIOR_INDEX = 40

#: Largest relative volume drift the check may take from the stated cell.
#: The assign→refine loop is svd's own local iteration, and iterating it from
#: a *wrong* prior can migrate basins — measured while writing the pin test:
#: a (5.31, 5.31, 13.72) tetragonal prior on cubic 4.157 Å data walked to the
#: true lattice and reported itself "confirmed".  A check that drifted this
#: far has stopped checking the stated cell and started searching, which is
#: the engines' job (the seeded svd start reaches the same basin *as an
#: engine*, so nothing is lost — only the provenance stays honest).  10 % in
#: volume is ~3 % per axis, generous for a structural analogue.
PRIOR_DRIFT_MAX = 0.10


def cell_systems(cell) -> tuple[str, ...]:
    """The crystal systems a cell's *shape* is consistent with, most symmetric
    first.

    A hexagonal metric (a = b, γ = 120°) is returned as ``("hexagonal",
    "trigonal")`` — the two systems share it and only the extinctions choose —
    and a rhombohedral shape (a = b = c, α = β = γ ≠ 90°) as ``("trigonal",)``.
    Classification is by consequence loose (:data:`CLASSIFY_RTOL`): a wrong
    call costs search order, never truth.
    """
    a, b, c, al, be, ga = (float(v) for v in cell)

    def eq(x, y):
        return abs(x - y) <= CLASSIFY_RTOL * max(abs(x), abs(y))

    def ang(x, y):
        return abs(x - y) <= CLASSIFY_ATOL_DEG

    right = ang(al, 90.0), ang(be, 90.0), ang(ga, 90.0)
    if all(right):
        if eq(a, b) and eq(b, c):
            return ("cubic",)
        if eq(a, b) or eq(b, c) or eq(a, c):
            return ("tetragonal",)
        return ("orthorhombic",)
    if right[0] and right[1] and ang(ga, 120.0) and eq(a, b):
        return ("hexagonal", "trigonal")
    if eq(a, b) and eq(b, c) and ang(al, be) and ang(be, ga):
        return ("trigonal",)
    if sum(right) == 2:
        return ("monoclinic",)
    return ("triclinic",)


def spacegroup_prior(symbol: str) -> tuple[str, str]:
    """(crystal system, centring letter) of a prior space-group symbol.

    Raises ``ValueError`` on an unknown symbol — the ``SearchSpecSpec``
    validator quotes this, so a typo is refused at declaration rather than
    silently steering nothing.
    """
    from ..crystallography.symmetry import get_spacegroup

    sg = get_spacegroup(symbol)
    system = sg.crystal_system_str()
    centring = sg.centring_type()
    if system not in SYSTEM_ORDER:
        raise ValueError(f"space group {symbol!r} has crystal system "
                         f"{system!r}, which this package does not search")
    return system, centring


def prior_systems(spec: SearchSpec) -> list[str]:
    """The systems the priors name, in ``SYSTEM_ORDER`` order — the queue jump.

    Only systems the caller asked for at all: a prior never widens the box,
    so a system outside ``spec.systems`` is not resurrected here (it is named
    in the diagnostic instead).
    """
    named: set[str] = set()
    for cell in spec.prior_cells:
        named.update(cell_systems(cell))
    for symbol in spec.prior_spacegroups:
        named.add(spacegroup_prior(symbol)[0])
    return [s for s in SYSTEM_ORDER if s in named and s in spec.systems]


def prior_seed_afs(spec: SearchSpec, system: str) -> list[np.ndarray]:
    """The A..F metrics to seed a stochastic search of ``system`` with."""
    return [af_from_cell(tuple(cell)) for cell in spec.prior_cells
            if system in cell_systems(cell)]


@dataclass
class PriorReport:
    """One prior's fate, the raw material of ``INDEX_PRIOR_USED``."""

    label: str                      # "cell (a, b, c, …)" or "space group X"
    systems: tuple[str, ...]        # what it classified as
    candidate: EngineCandidate | None   # survived the check, or None
    reason: str = ""                # why not, when candidate is None


def _centring_choices(spec: SearchSpec, system: str,
                      sg_centrings: dict[str, str]) -> tuple[str, ...]:
    """Centrings to try for a prior cell in ``system`` — the space-group
    prior's, when one names this system, else every one the caller allows."""
    if system in sg_centrings:
        allowed = spec.centrings_for(system)
        c = sg_centrings[system]
        if c in allowed:
            return (c,)
    return spec.centrings_for(system)


def build_prior_candidates(peaks: PeakList, spec: SearchSpec, quality
                           ) -> tuple[list[EngineCandidate], list[PriorReport]]:
    """Check each prior cell against the peak list, the engines' own way.

    assign → refine (to a settled assignment) → shift re-fit →
    ``indexes_the_search_lines``: the same bar every engine's candidate is
    held to, so a surviving prior means exactly what a found cell means —
    except for who found it (:data:`PRIOR_FINDER`).  A prior that fails is a
    :class:`PriorReport` with the reason, never an exception: a wrong prior
    costs time, not truth, and the record is the point.
    """
    reports: list[PriorReport] = []
    if not spec.prior_cells and not spec.prior_spacegroups:
        return [], reports

    sg_centrings: dict[str, str] = {}
    for symbol in spec.prior_spacegroups:
        system, centring = spacegroup_prior(symbol)
        sg_centrings.setdefault(system, centring)
        reports.append(PriorReport(
            label=f"space group {symbol}", systems=(system,), candidate=None,
            reason=("queue jump" if system in spec.systems
                    else "its system is not in the requested search")))

    q_all = peaks.q()
    tt_all = peaks.two_theta()
    allowance, _assumed = effective_shift_allowance(spec, quality)
    sigma = sigma_effective(peaks.q_esd(), tt_all, peaks.wavelength, allowance)
    search = search_line_order(peaks, spec)
    q_max = float(q_all.max()) if len(q_all) else 0.0

    out: list[EngineCandidate] = []
    for cell in spec.prior_cells:
        label = ("cell (" + ", ".join(f"{v:g}" for v in cell) + ")")
        systems = cell_systems(cell)
        report = PriorReport(label=label, systems=systems, candidate=None)
        reports.append(report)

        searchable = [s for s in systems if s in spec.systems]
        if not searchable:
            report.reason = "its system is not in the requested search"
            continue
        axes = (float(cell[0]), float(cell[1]), float(cell[2]))
        if not (spec.min_d_axis <= min(axes)
                and max(axes) <= spec.max_d_axis):
            report.reason = (f"outside the declared axis range "
                             f"{spec.min_d_axis:g}-{spec.max_d_axis:g} Å — a "
                             "prior never widens the box")
            continue
        n_max = int(np.ceil(max(axes) * np.sqrt(max(q_max, 1e-12)))) + 1
        if n_max > MAX_PRIOR_INDEX:
            report.reason = (f"needs trial indices up to {n_max}, past the "
                             f"searchable {MAX_PRIOR_INDEX}")
            continue

        best: EngineCandidate | None = None
        for system in searchable:
            vol_max = search_volume_ceiling(spec, quality, system)
            for centring in _centring_choices(spec, system, sg_centrings):
                cand = _check_one(cell, system, centring, spec, peaks, q_all,
                                  sigma, tt_all, search, n_max, vol_max)
                if cand is None:
                    continue
                if best is None or cand.n_indexed > best.n_indexed:
                    best = cand
        if best is None:
            report.reason = (
                "does not index the search lines at the stated metric — "
                "checked, refuted (the check follows a stated cell only "
                f"{PRIOR_DRIFT_MAX:.0%} in volume; a cell reachable only by "
                "drifting further is the engines' to find)")
        else:
            report.candidate = best
            out.append(best)
    return out, reports


def _check_one(cell, system: str, centring: str, spec: SearchSpec,
               peaks: PeakList, q_all, sigma, tt_all, search, n_max: int,
               vol_max: float) -> EngineCandidate | None:
    hkl_all = trial_hkl(n_max, centring)
    af = af_from_cell(tuple(cell))
    line_index, hkl = assign_lines(q_all, sigma, hkl_all, af,
                                   k_sigma=spec.k_sigma)
    fit = None
    for _ in range(MAX_PRIOR_PASSES):
        if len(line_index) < 2:
            return None
        try:
            fit = refine_candidate(q_all[line_index], sigma[line_index], hkl,
                                   system=system)
        except (ValueError, np.linalg.LinAlgError):
            return None
        new_index, new_hkl = assign_lines(q_all, sigma, hkl_all, fit.af,
                                          k_sigma=spec.k_sigma)
        if (len(new_index) == len(line_index)
                and bool(np.all(new_index == line_index))):
            break
        line_index, hkl = new_index, new_hkl
    if fit is None or not np.all(np.isfinite(fit.cell)):
        return None
    from ..crystallography.lattice import cell_volume

    v_stated = cell_volume(*cell)
    if abs(fit.volume - v_stated) > PRIOR_DRIFT_MAX * v_stated:
        return None
    if not (spec.min_volume <= fit.volume <= vol_max):
        return None
    if not indexes_the_search_lines(line_index, search, spec.n_unindexed):
        return None
    fit = refine_with_shift(fit, spec, system, q_all, sigma, tt_all,
                            peaks.wavelength, line_index, hkl)
    return EngineCandidate(fit=fit, system=system, centring=centring,
                           engine=PRIOR_FINDER, hkl=hkl,
                           line_index=line_index,
                           n_lines=len(peaks.usable()))


def prior_used_diagnostic(reports: list[PriorReport], jumped: list[str],
                          candidates) -> Diagnostic:
    """``INDEX_PRIOR_USED`` — what was assumed, and what it changed.

    One diagnostic for the whole run rather than one per prior, because the
    reader's question is "was this answer steered, and how" — and the answer
    must never look like a measurement (the ``INDEX_SHIFT_ALLOWANCE``
    precedent).  ``candidates`` is the final ranked list, which is what says
    whether a stated cell ended up *found* (engines agree), merely *entered*
    (prior-only, after the ranked list), or neither.
    """
    from .reduce import same_lattice

    lines: list[str] = []
    for report in reports:
        if report.candidate is not None:
            fate = "refuted in consensus"
            own = af_from_cell(report.candidate.cell)
            for cand in candidates:
                if PRIOR_FINDER not in cand.found_by:
                    continue
                equal, _ = same_lattice(own, af_from_cell(cand.cell))
                if not equal:
                    continue
                finders = [f for f in cand.found_by if f != PRIOR_FINDER]
                fate = (f"confirmed by {', '.join(finders)}" if finders
                        else "entered unconfirmed (prior-only, after the "
                             "ranked candidates)")
                break
            lines.append(f"{report.label}: {fate}")
        else:
            lines.append(f"{report.label}: {report.reason}")
    message = (
        "the search was steered by "
        f"{len(reports)} declared prior(s) — "
        + ("systems " + " → ".join(jumped) + " jumped the queue; "
           if jumped else "no queue change; ")
        + "; ".join(lines)
        + ". A prior reorders and seeds the search; it never injects a "
          "candidate past the engines, and no range was changed by it")
    return Diagnostic(
        level="info", code="INDEX_PRIOR_USED", message=message,
        where=[r.label for r in reports],
        suggestion=("read a prior-only candidate as stated-and-unconfirmed: "
                    "the engines did not find it, and its grade says so"))


__all__ = ["MAX_PRIOR_INDEX", "PRIOR_FINDER", "PriorReport",
           "build_prior_candidates", "cell_systems", "prior_seed_afs",
           "prior_systems", "prior_used_diagnostic", "spacegroup_prior"]

"""Consensus between engines, and the confidence gate.

**Agreement is the confidence.**  Two engines that share only the tolerance model
and the form of Q are genuinely independent *searches* — ``search_dichotomy``
bounds Q over boxes and its failure mode is a domain too wide,
``search_trial_error`` assumes the indices of a few base lines and solves exactly
and its failure mode is a bad base line — so a lattice both of them reach is
evidence in a way no single figure of merit is.  The device is
``sequential.py``'s ``direction="both"`` and ``tests/test_cross_backend.py``'s
per-column agreement matrix, one rank up.

**Two engines is the ceiling, and that is a result rather than a shortfall.**
WP-1023's whole-profile Monte Carlo is a measured no-go: its tier-2 re-scoring is
affordable (13-15 ms per state) and discriminating (Rwp 1.29 for the certified
cell against 7.25 for one 1 % off), but tier-1 **cannot rank** — on the certified
qarr corundum pattern the true cell scores exactly 0.0000 and ranks 29 053 of
200 001, because the pattern's 0.060° cos θ displacement is 11σ of the fitted
per-line σ; widening the window puts the truth at rank 4 and simultaneously lets
coincidence-rich large cells outscore it.  So a Le Bail *re-scorer* is worth
having as validation (:mod:`pxrdref.indexing.workflow`, which owns it) and
``found_by`` must never contain one: a re-scorer is not an independent opinion,
it is the same opinion measured again.

**The gate's shape.**  ``high`` requires *no* caveats at all, and
:data:`~pxrdref.schemas.indexing.INDEX_REFUTING_CAVEATS` splits the rest in two:
a refuting caveat is positive evidence against the cell (or evidence that the
data cannot choose between it and another) and drops it to ``low``; the others cap
it at ``medium``.  Everything else with at least two engines behind it is
``medium``.

One consequence is worth stating rather than discovering: **on real data with no
measured systematic shift, ``high`` is currently unreachable, by design.** Both
engines widen their matching window by an *assumed*
``DEFAULT_UNKNOWN_SHIFT_DEG`` when no shift has been measured, which raises
``shift_allowance_assumed`` — and a cell found inside a widened window absorbs the
shift (measured, +1400 ppm on a certified pattern).  Declaring a calibrated
``shift_allowance_deg``, or handing ``assess_peak_list`` reference positions from an
internal standard, is what makes the caveat go away.  That is the same posture as
Layer 1's abstention: the ceiling moves when the evidence arrives, not when the
constant is raised.  Closing it on real data is WP-1026.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

import numpy as np

from ..schemas.common import Diagnostic
from ..schemas.indexing import (
    INDEX_MIN_INDEXED_FRACTION,
    INDEX_REFUTING_CAVEATS,
    BravaisOpinion,
    CellCandidate,
    Confidence,
    DataQualityReport,
    IndexCaveat,
    PeakList,
)
from .engines import (
    DEFAULT_MAX_CANDIDATES,
    DEFAULT_MIN_VOLUME,
    EngineCandidate,
    EngineResult,
    SearchSpec,
    candidates_truncated_diagnostic,
    dedup_groups,
    match_window,
    rank_candidates,
    to_cell_candidate,
)
from .fom import fom_panel_disagrees

# Re-exported from its WP-1045 home beside ``volume_envelope`` itself: the
# engines' search ceiling and this module's ``volume_unphysical`` flag apply
# the *same* slack, so a cell the search could reach is never flagged for
# having been reached — the flag fires only when a caller widened
# ``max_volume`` past the slack too.
from .quality import VOLUME_ENVELOPE_SLACK

#: Candidates that get the **expensive** per-candidate checks — geometrical
#: ambiguity (which enumerates 55 derivative lattices and predicts reflections for
#: each) and Le Bail validation (a refinement, ~0.6 s measured).  Three, plus
#: every candidate an engine consensus could promote, so the cap never removes a
#: candidate the gate might otherwise call ``high``: see :func:`checked_indices`,
#: which is one rule read by both call sites so "which candidates were checked"
#: has exactly one answer.
CONSENSUS_CHECK_TOP = 3


@dataclass
class ConsensusOutcome:
    """Ranked candidates and the result-level facts the gate needs.

    Separate from :class:`~pxrdref.schemas.indexing.IndexingResult` because this
    is the *pre-validation* answer: :func:`consensus` stops before the Le Bail
    fits so ``index_pattern`` can decide which candidates to spend a refinement
    on, and :func:`apply_gate` runs after.
    """

    candidates: list[CellCandidate] = field(default_factory=list)
    engines_run: list[str] = field(default_factory=list)
    systems_searched: list[str] = field(default_factory=list)
    search_complete: dict[str, bool] = field(default_factory=dict)
    engine_stats: dict[str, float] = field(default_factory=dict)
    #: candidates whose geometrical-ambiguity enumeration actually ran — the
    #: ``checked`` the gate must be given.  Identical to ``checked_indices``
    #: except under a fired token (WP-1037), where the enumeration is the
    #: measured long pole (12 × 3.75 s on the corundum run) and is skipped for
    #: the remaining candidates — which must then read "not enumerated"
    #: (a capping caveat), never "no ambiguity found"
    ambiguity_checked: list[int] = field(default_factory=list)
    fom_panel_disagrees: bool = False
    #: was any engine's tolerance widened by an *assumed* systematic?  Read from
    #: the engines' own ``INDEX_SHIFT_ALLOWANCE`` diagnostic rather than
    #: re-derived, so the gate and the message can never disagree
    shift_allowance_assumed: bool = False
    diagnostics: list[Diagnostic] = field(default_factory=list)


def merge_engine_candidates(results: Sequence[EngineResult],
                            ) -> list[EngineCandidate]:
    """Pool every engine's candidates and merge the ones that are one lattice.

    The kept member of each group carries ``found_by`` — every engine that
    reached that lattice — which is the raw material of the whole gate.  Note
    what is *not* merged: two centrings of the same metric stay separate, because
    they are two lattices predicting different numbers of lines and the panel
    exists to choose between them (``engines.dedup_groups``).
    """
    pool: list[EngineCandidate] = []
    for result in results:
        pool.extend(result.candidates)
    kept: list[EngineCandidate] = []
    for group in dedup_groups(pool):
        best = group[0]
        # sorted, not insertion-ordered: `found_by` is compared against
        # `engines_run` as a set, and a stable order makes the reported list
        # reproducible whatever order the engines happened to run in
        best.found_by = sorted({c.engine for c in group})
        kept.append(best)
    return kept


def bravais_opinion(cell: Sequence[float], centring: str,
                    cell_esd: Sequence[float] | float = 1e-3,
                    ) -> BravaisOpinion | None:
    """Run WP-1020's two-opinion Bravais screen and pack it for reporting.

    ``None`` when the screen raises — a metric so degenerate that gemmi or spglib
    refuses it is not a lattice symmetry statement, and inventing "triclinic"
    would be one.
    """
    from .reduce import bravais_screen

    try:
        screen = bravais_screen(tuple(cell), centring, cell_esd=cell_esd)
    except Exception:                       # noqa: BLE001 — third-party refusal
        return None
    return BravaisOpinion(
        system=screen.system, system_loosest=screen.system_loosest,
        system_gemmi=screen.system_gemmi, system_spglib=screen.system_spglib,
        ambiguous=screen.ambiguous, methods_disagree=screen.methods_disagree,
        reduced_cell=tuple(float(v) for v in screen.reduced.cell))


def checked_indices(candidates: Sequence[CellCandidate],
                    engines_run: Sequence[str], *,
                    top: int = CONSENSUS_CHECK_TOP) -> list[int]:
    """Which candidates get the expensive checks, in rank order.

    The union of two sets, and the second is what makes the cap safe: the top
    ``top`` by Borda rank, **plus every candidate that every engine found**.  A
    candidate the engines agree on is the only kind the gate can promote to
    ``high``, so skipping one would silently convert a cap on cost into a cap on
    the answer — and a candidate that is checked but ranked eleventh is a cheap
    thing to allow, since the pool is already capped at
    ``SearchSpec.max_candidates``.

    One function rather than two similar loops because ambiguity enumeration and
    Le Bail validation must cover the *same* candidates: a candidate validated but
    not checked for ambiguity could reach ``high`` with an unenumerated partner.
    """
    want = set(range(min(top, len(candidates))))
    engines = set(engines_run)
    for i, cand in enumerate(candidates):
        if engines and set(cand.found_by) >= engines:
            want.add(i)
    return sorted(want)


def consensus(results: Sequence[EngineResult], peaks: PeakList, *,
              spec: SearchSpec | None = None,
              quality: DataQualityReport | None = None,
              top: int = CONSENSUS_CHECK_TOP,
              cancel=None, ambiguity: bool = True,
              priors: Sequence[EngineCandidate] = ()) -> ConsensusOutcome:
    """Merge, rank, classify and enumerate ambiguity — everything but validation.

    Order matters and it is the WP's: reduce and merge (so ``found_by`` is
    complete before anything is ranked), then Borda over the **whole** figure-of-
    merit panel (never a member — measured, ``indexed_fraction`` alone put a
    390-line wrong phase above the truth), then the two-opinion Bravais screen and
    the geometrical-ambiguity enumeration on the checked subset.

    ``cancel`` (WP-1037) is read between ambiguity enumerations only — merging,
    ranking and the Bravais screen always run, because they are what turns raw
    engine output into an answer at all and they are cheap (the enumeration was
    measured at 45 of a 105 s ceiling-bound corundum run; everything else here
    is noise).  A skipped candidate stays out of ``ambiguity_checked``, which
    is what makes the gate read it honestly.

    ``ambiguity=False`` (WP-1042) skips the enumeration entirely — it is what
    makes this callable per **completed system** mid-run, since everything else
    here is the cheap part.  ``ambiguity_checked`` then stays empty and the
    gate reads every candidate as unchecked (a capping caveat), so a streamed
    grade is conservative: it can rise when the full consensus runs, never
    fall.

    ``priors`` (WP-1045) are checked prior cells (finder ``"prior"``, from
    ``priors.build_prior_candidates``).  They join the *merge* — a prior that
    is an engine candidate's lattice adds a ``found_by`` member and nothing
    else — but a prior-only lattice **never enters the Borda ranking**: it is
    ranked among its own kind and appended after the engine candidates.
    Borda violates independence of irrelevant alternatives, so this is what
    makes "a wrong prior changes no rank" structural rather than an empirical
    hope.  ``"prior"`` is deliberately absent from ``engines_run``, so the
    ordinary agreement caveat grades a prior-only candidate down with no new
    gate vocabulary.
    """
    from .priors import PRIOR_FINDER

    spec = spec or SearchSpec()
    carrier: list[EngineResult] = []
    if priors:
        holder = EngineResult(engine=PRIOR_FINDER)
        holder.candidates = list(priors)
        carrier = [holder]
    merged = merge_engine_candidates([*results, *carrier])
    prior_only = [c for c in merged if c.found_by == [PRIOR_FINDER]]
    merged = [c for c in merged if c.found_by != [PRIOR_FINDER]]
    # the same window the engines assigned with, re-derived from the same two
    # inputs — ranking candidates in a *tighter* one judges them by a criterion
    # they were never selected under (``fom.fom_panel``)
    q_match = match_window(peaks, spec, quality)
    reported = spec.max_candidates or DEFAULT_MAX_CANDIDATES
    # ``shortlist=None``: every merged lattice is scored, not the cheap
    # pre-rank's top ``4 × max_candidates`` (WP-1046).  What arrives here is
    # already bounded by each unit's ``engine_pool``, so there is no harvest to
    # protect against — and tying the panel's reach to the number the answer
    # reports is the same defect as truncating in the units.
    ranked = rank_candidates(merged, peaks, k_sigma=spec.k_sigma,
                             n_unindexed=spec.n_unindexed,
                             max_candidates=reported,
                             shortlist=None, q_match=q_match)
    out = ConsensusOutcome(
        engines_run=[r.engine for r in results],
        fom_panel_disagrees=fom_panel_disagrees([c.fom for c in ranked
                                                 if c.fom]))
    systems: list[str] = []
    for result in results:
        for system in result.systems_searched:
            if system not in systems:
                systems.append(system)
        for key, value in result.stats.items():
            out.engine_stats[f"{result.engine}.{key}"] = float(value)
        # deduplicated on (code, message): every engine widens its window by the
        # same assumed allowance and says so in the same words, and N identical
        # copies of one statement reads as N problems.  Two engines that say
        # different things about the same code (different systems incomplete, say)
        # keep both messages, which is why the message is part of the key.
        for diag in result.diagnostics:
            if not any(d.code == diag.code and d.message == diag.message
                       for d in out.diagnostics):
                out.diagnostics.append(diag)
        if any(d.code == "INDEX_SHIFT_ALLOWANCE" for d in result.diagnostics):
            out.shift_allowance_assumed = True
    out.systems_searched = systems
    # what the reported list left out, at the one layer that can state it
    # exactly (WP-1046).  ``merged`` is post-dedup, so the difference counts
    # *lattices*, not repeats; the pool clause is a flag read from the stat each
    # unit sets when its own hand-off bound bound.
    capped = sorted(f"{r.engine}:{key.split('.')[0]}"
                    for r in results for key, value in r.stats.items()
                    if key.endswith(".pool_capped") and value)
    if len(merged) > reported or capped:
        out.diagnostics.append(candidates_truncated_diagnostic(
            len(merged), min(reported, len(merged)), capped,
            spec.engine_pool()))
    # a system is complete only if **every** engine that ran both entered it
    # and exhausted its domain (WP-1042).  The second half is the new one:
    # under the system-major scheduler a deadline can stop the run with a
    # system entered by some engines and never reached by another, and that
    # engine's silence there is not evidence — before this rule such a system
    # read "searched to completion" whenever the engines that did enter it
    # finished, and the budget diagnostic had nothing to name.
    out.search_complete = {
        s: all(bool(r.search_complete.get(s, False)) for r in results)
        for s in systems}

    out.candidates = [
        to_cell_candidate(c, peaks, k_sigma=spec.k_sigma,
                          n_unindexed=spec.n_unindexed, q_match=q_match)
        for c in ranked]
    if prior_only:
        # ranked among their own kind only, appended after every engine
        # candidate: a prior may not displace what the engines found
        tail = rank_candidates(prior_only, peaks, k_sigma=spec.k_sigma,
                               n_unindexed=spec.n_unindexed,
                               max_candidates=spec.max_candidates
                               or DEFAULT_MAX_CANDIDATES,
                               shortlist=None, q_match=q_match)
        out.candidates += [
            to_cell_candidate(c, peaks, k_sigma=spec.k_sigma,
                              n_unindexed=spec.n_unindexed, q_match=q_match)
            for c in tail]
    for cand in out.candidates:
        cand.bravais = bravais_opinion(cand.cell, cand.centring,
                                       cell_esd=np.asarray(cand.cell_esd))
    if ambiguity:
        enumerate_ambiguity(out, peaks, top=top, cancel=cancel)
    return out


def enumerate_ambiguity(outcome: ConsensusOutcome, peaks: PeakList, *,
                        top: int = CONSENSUS_CHECK_TOP, cancel=None) -> None:
    """The geometrical-ambiguity pass over the checked candidates, in place.

    Split out of :func:`consensus` in WP-1045 so ``index_pattern`` can run it
    **after** the budgeted validation: whole-profile validation is the
    mandatory check, and this enumeration — measured at 45 s of a
    ceiling-bound corundum run, with one candidate's 55-lattice sweep
    uninterruptible — consumed the whole validation reserve whenever it ran
    first.  ``cancel`` is read between candidates; one the clock stops before
    stays out of ``ambiguity_checked``, which the gate reads as an unasked
    question (capping), never a clean answer.
    """
    checked = set(checked_indices(outcome.candidates, outcome.engines_run,
                                  top=top))
    for i, cand in enumerate(outcome.candidates):
        if i in checked and i not in outcome.ambiguity_checked \
                and not (cancel is not None and bool(cancel)):
            cand.ambiguity = _partners(cand, peaks)
            outcome.ambiguity_checked.append(i)


def _partners(cand: CellCandidate, peaks: PeakList):
    from .ambiguity import ambiguity_partners

    try:
        return ambiguity_partners(cand.cell, cand.system, cand.centring,
                                  peaks.q(), peaks.q_esd(), peaks.wavelength,
                                  float(peaks.two_theta_max),
                                  two_theta_min=float(peaks.two_theta_min))
    except (ValueError, RuntimeError, np.linalg.LinAlgError):
        return []


# ----------------------------------------------------------------------
# the gate
# ----------------------------------------------------------------------
def caveats_for(cand: CellCandidate, *, engines_run: Sequence[str],
                panel_disagrees: bool, validated: bool,
                search_complete: dict[str, bool],
                shift_allowance_assumed: bool,
                checked: bool = True,
                panel_reduced: bool = False,
                min_indexed_fraction: float = INDEX_MIN_INDEXED_FRACTION,
                volume_max: float | None = None) -> list[IndexCaveat]:
    """Every reason this candidate is not ``"high"``, from the closed vocabulary.

    Collected in one place and graded in another (:func:`grade`) for the same
    reason ``indexing/diagnostics.py`` is separate from the fitter: the facts and
    what they are worth are different decisions, and a threshold should move
    without touching the code that measures.

    **``unmatched_observed`` is deliberately not read here, and it was measured
    rather than overlooked** (WP-1041).  A caveat is an absolute verdict on one
    candidate, and that count has no absolute scale: across 21 validated
    candidates on six known-cell datasets it runs 10 to 188 *for correct cells*,
    because its level is set by how much of the specimen the candidate's phase is
    not — 11-BM NAC's own truth leaves 188 unmatched against a CaF₂ impurity.
    Within one pattern it does discriminate, and there it is nearly the number
    the fit already reports: Spearman ρ against Rwp is +0.80 to +1.00 on the five
    datasets with enough candidates to rank, against +0.44 pooled across them.
    So it is a comparative instrument, and reading it as a per-candidate verdict
    is the same mistake as scoring the FoM panel absolutely
    (:func:`~pxrdref.indexing.fom.log_sum_scores`).
    """
    out: list[IndexCaveat] = []
    engines = set(engines_run)
    if engines and not set(cand.found_by) >= engines:
        out.append("engines_disagree")
    if cand.ambiguity:
        out.append("geometric_ambiguity")
    elif not checked:
        # not enumerated is not "none found"; the honest reading is that the
        # question was not asked, and it must not read as a clean answer
        out.append("geometric_ambiguity")
    if panel_disagrees:
        out.append("fom_panel_disagrees")
    if panel_reduced:
        # below the scoring bar (WP-1043): the panel that ranked this candidate
        # lacks the classical figures, so ``high`` stays exactly as unreachable
        # as the old abstention made it — capping, because a short list is not
        # evidence against the cell
        out.append("fom_panel_reduced")
    if not validated or cand.lebail is None:
        out.append("not_validated")
    elif cand.lebail.status in ("failed", "diverged"):
        out.append("validation_failed")
    elif cand.lebail.predicted_but_absent:
        out.append("predicted_but_absent")
    fraction = cand.fom_value("indexed_fraction")
    if fraction is None or fraction < min_indexed_fraction:
        out.append("indexed_fraction_low")
    if not search_complete.get(cand.system, True):
        out.append("search_incomplete")
    if shift_allowance_assumed:
        out.append("shift_allowance_assumed")
    if cand.bravais is None or cand.bravais.ambiguous or \
            cand.bravais.methods_disagree:
        out.append("bravais_ambiguous")
    if cand.volume < DEFAULT_MIN_VOLUME or (
            volume_max is not None
            and cand.volume > VOLUME_ENVELOPE_SLACK * volume_max):
        out.append("volume_unphysical")
    return out


def grade(caveats: Sequence[str], found_by: Sequence[str],
          engines_run: Sequence[str]) -> Confidence:
    """The three-level verdict, and the whole of it is four lines.

    * ``low`` — fewer than two engines behind it, or **any** refuting caveat.
      One engine is not agreement, and a refuting caveat is evidence against the
      cell rather than a qualification of it.
    * ``high`` — every engine that ran found this lattice and there is *nothing*
      to qualify.
    * ``medium`` — everything else: at least two independent searches agree and
      the only outstanding caveats are ones that cap rather than refute.

    The WP's "≥2 engines, or all with one caveat" is this, read with the first
    clause as the fallback: caveat *count* is not what separates medium from low,
    because two capping caveats (an assumed tolerance and an unvalidated
    candidate) are the ordinary state of a peaks-only run and would otherwise
    make every answer ``low`` — which would empty the vocabulary of meaning.
    """
    if len(set(found_by)) < 2 or any(c in INDEX_REFUTING_CAVEATS
                                     for c in caveats):
        return "low"
    if not caveats and set(found_by) >= set(engines_run):
        return "high"
    return "medium"


def apply_gate(candidates: Sequence[CellCandidate], *,
               engines_run: Sequence[str], panel_disagrees: bool,
               validated: bool, search_complete: dict[str, bool],
               shift_allowance_assumed: bool,
               checked: Sequence[int] | None = None,
               quality: DataQualityReport | None = None,
               min_indexed_fraction: float = INDEX_MIN_INDEXED_FRACTION,
               ) -> list[CellCandidate]:
    """Write ``confidence`` and ``confidence_caveats`` onto every candidate.

    Mutates in place and returns the same list: the candidates are this
    function's output, and copying them would leave two objects that could
    disagree about a verdict there is only one of.
    """
    was_checked = set(range(len(candidates)) if checked is None else checked)
    panel_reduced = quality is not None and bool(quality.fom_undefined)
    for i, cand in enumerate(candidates):
        volume_max = None
        if quality is not None:
            volume_max = quality.volume_envelope.get(cand.system)
        cand.confidence_caveats = caveats_for(
            cand, engines_run=engines_run, panel_disagrees=panel_disagrees,
            validated=validated, search_complete=search_complete,
            shift_allowance_assumed=shift_allowance_assumed,
            checked=i in was_checked, panel_reduced=panel_reduced,
            min_indexed_fraction=min_indexed_fraction, volume_max=volume_max)
        cand.confidence = grade(cand.confidence_caveats, cand.found_by,
                                engines_run)
    return list(candidates)


__all__ = ["CONSENSUS_CHECK_TOP", "VOLUME_ENVELOPE_SLACK", "ConsensusOutcome",
           "apply_gate", "bravais_opinion", "caveats_for", "checked_indices",
           "consensus", "grade", "merge_engine_candidates"]

"""The FitReport: agent-native fit assessment in three gated layers.

``build_report(result)`` alone gives Layer 0 (model-free, always
trustworthy).  Pass the compiled model — most easily via
``Refinement.report()`` — to add Layer 1 (gated linear misfit attribution)
and Layer 2 (typed suggested actions).  See :mod:`.schemas` for the contract
and the pinned thresholds, and docs/DESIGN.md for the design rationale.
"""

from __future__ import annotations

from ..schemas.results import RefinementResult
from .apply import RECIPES, Recipe, describe_action, recipe, stage_for
from .background import assess_background
from .identifiability import (
    assess_identifiability,
    identifiability_clause,
    is_exchangeable,
)
from .layer0 import (
    background_clause,
    build_layer0,
    lebail_gap,
    too_flexible,
    too_stiff,
)
from .layer1 import (
    abstention_flavour,
    analyse_trends,
    attribute_regions,
    contents_signature,
    maturity_gate,
)
from .layer2 import (
    apply_strategy_veto,
    background_actions,
    cap_texture_crosstalk,
    compare_rivals,
    delta_bic,
    estimate_delta_chi2,
    hamilton_justified,
    layer0_actions,
    note_background_crosstalk,
    predict_then_verify,
    reindex_action,
    suggest_actions,
    texture_actions,
)
from .schemas import (
    LEBAIL_GAP_NOTABLE,
    RIVAL_DECISIVE_MIN_CHI2_RATIO,
    THRESHOLDS_VERSION,
    TRAJECTORY_MAX_ACTIONS,
    BackgroundEvidence,
    BasisCoefficient,
    ExchangeFinding,
    FitReport,
    IdentifiabilityEvidence,
    LeBailGap,
    Region,
    RegionAttribution,
    RivalComparison,
    RivalFit,
    StageReport,
    StrainAnalysis,
    SuggestedAction,
    TextureAnalysis,
    TrendAnalysis,
    TrendTemplate,
    UnmatchedPeak,
    VerificationOutcome,
)
from .strain import analyse_strain
from .texture import analyse_texture

__all__ = [
    "RECIPES",
    "RIVAL_DECISIVE_MIN_CHI2_RATIO",
    "THRESHOLDS_VERSION",
    "TRAJECTORY_MAX_ACTIONS",
    "BackgroundEvidence",
    "BasisCoefficient",
    "ExchangeFinding",
    "FitReport",
    "IdentifiabilityEvidence",
    "LeBailGap",
    "Recipe",
    "Region",
    "RegionAttribution",
    "RivalComparison",
    "RivalFit",
    "StageReport",
    "StrainAnalysis",
    "SuggestedAction",
    "TextureAnalysis",
    "TrendAnalysis",
    "TrendTemplate",
    "UnmatchedPeak",
    "VerificationOutcome",
    "abstention_flavour",
    "analyse_strain",
    "analyse_texture",
    "analyse_trends",
    "apply_strategy_veto",
    "assess_background",
    "assess_identifiability",
    "attribute_regions",
    "background_actions",
    "background_clause",
    "build_layer0",
    "build_report",
    "cap_texture_crosstalk",
    "compare_rivals",
    "contents_signature",
    "delta_bic",
    "describe_action",
    "estimate_delta_chi2",
    "hamilton_justified",
    "identifiability_clause",
    "is_exchangeable",
    "layer0_actions",
    "lebail_gap",
    "maturity_gate",
    "note_background_crosstalk",
    "predict_then_verify",
    "recipe",
    "reindex_action",
    "stage_for",
    "suggest_actions",
    "texture_actions",
    "too_flexible",
    "too_stiff",
]


def build_report(result: RefinementResult, *, model=None, values=None,
                 plan=None, free_paths: list[str] | None = None,
                 top_n: int = 15, match_tol_deg: float = 0.08,
                 min_peak_sigma: float = 5.0) -> FitReport:
    """Build the report, going as deep as the inputs allow.

    Parameters
    ----------
    result:
        The refinement result (Layer 0 needs nothing else).
    model, values:
        A :class:`~rietx.model.forward.CompiledModel` and its parameter
        value dict.  Supplying both enables Layers 1-2; without them the
        report is Layer 0 and ``layer1_available`` stays False.
        ``Refinement.report()`` fills these in for you.
    plan, free_paths:
        Used by the Layer-2 strategy veto: actions the plan already performs,
        or parameters already free, are marked inactive.
    """
    report = build_layer0(result, top_n=top_n, match_tol_deg=match_tol_deg,
                          min_peak_sigma=min_peak_sigma)
    # Soft-restraint deviations are model-free (carried from the result), so they
    # surface even at Layer 0 — a restraint fighting the data is worth reporting
    # regardless of whether the fit is mature enough to linearise.
    report.restraints = result.restraints
    # Bonding geometry rides through on the same terms and for the same reason
    # (WP-1072): it is measured against the structure, not against the fit's
    # maturity, and "are these distances chemically sensible" is exactly the
    # question a reader asks first when Layer 1 abstains.
    report.geometry = result.geometry
    # The identifiability section (WP-1056) is likewise read from the stored
    # result plus what the fit screened at Jacobian time, never linearised —
    # and an exchangeable held parameter is exactly the evidence a *converged*
    # report must not withhold, so it speaks on every branch, abstention
    # included.
    report.identifiability = assess_identifiability(result)
    clause = identifiability_clause(report.identifiability)
    if clause is not None:
        report.summary += "; " + clause
    if model is None or values is None:
        return report

    attributions = attribute_regions(model, values, report.regions)
    report.attribution = attributions
    # March-Dollase texture and Stephens anisotropic strain are computed before
    # the maturity gate: an uncorrected intensity or width *direction* is a
    # common *cause* of an immature fit, so these must still speak when the rest
    # of Layer 1 abstains.
    report.texture = analyse_texture(model, values)
    report.strain = analyse_strain(model, values)
    # The Le Bail gap is measured, never linearised, so it too speaks on both
    # branches (None outside Rietveld mode — absent for cause).  The summary
    # quotes it only when notable: a converged fit reads ratio ≲ 1 and saying
    # so every time would be noise.
    report.lebail_gap = lebail_gap(model, values,
                                   rwp_rietveld=result.statistics.rwp)
    gap = report.lebail_gap
    if gap is not None and gap.ratio >= LEBAIL_GAP_NOTABLE:
        report.summary += (
            f"; a Le Bail partition at the frozen converged state reaches "
            f"Rwp={gap.rwp_lebail:.4f} against the Rietveld "
            f"Rwp={gap.rwp_rietveld:.4f} (×{gap.ratio:.1f}): positions and "
            f"profile account for the pattern — the intensity model carries "
            f"the misfit, and phase ID does not rest on it")

    ticks = [t for positions in result.ticks.values() for t in positions]
    reason = maturity_gate(result.statistics.rwp, attributions)
    if reason is not None:
        # Abstain from *parameter-level* statements: keep the per-region
        # evidence, publish no trends.  Model-free actions (an unindexed peak
        # is unindexed regardless of maturity — and is a common reason for it)
        # still stand, and the veto still applies to them.  Since WP-1054 the
        # position-family pointer stands here too: validity-radius failures
        # are exactly the evidence abstention rests on, and before it the one
        # state that most needed reindex_or_recheck_cell was the one state
        # that could not receive it.
        kind, extra = abstention_flavour(result.statistics.rwp, attributions)
        if extra is not None:
            reason += " — " + extra
        report.abstained_reason = reason
        report.abstained_kind = kind
        actions = layer0_actions(report.unmatched, attributions, ticks=ticks)
        reindex = reindex_action(attributions)
        if reindex is not None:
            actions.append(reindex)
        actions += texture_actions(report.texture)
        # the background hypotheses stand here for the same reason texture
        # does: their evidence never linearised anything, and an over-flexible
        # or over-stiff background is a *cause* of an immature fit
        actions += background_actions(report.background)
        actions = cap_texture_crosstalk(actions, report.texture,
                                        report.unmatched)
        actions = note_background_crosstalk(actions, report.background)
        if plan is not None or free_paths is not None:
            actions = apply_strategy_veto(actions, plan, free_paths=free_paths)
        actions.sort(key=lambda a: -a.confidence)
        report.suggested_actions = actions
        report.summary += f"; Layer 1 abstained — {reason}"
        return report

    report.layer1_available = True
    report.trends = analyse_trends(attributions, model.wavelength)
    # The contents-type clause (WP-1057): sign-alternating intensity misfit
    # with no angular trend is the one signature the trend templates are
    # structurally blind to, and the honest zero-action report it produces
    # left the expert inference unstated.  Evidence stays in attribution and
    # trends; this names what they support, and points at the gap that
    # decides it.
    clause = contents_signature(report.trends, attributions)
    if clause is not None:
        if report.lebail_gap is not None:
            clause += (f"; the Le Bail gap (×{report.lebail_gap.ratio:.1f}) "
                       f"is the deciding statistic")
        report.summary += "; " + clause
    actions = suggest_actions(attributions, report.trends, report.unmatched,
                              rwp=result.statistics.rwp, ticks=ticks)
    predicted = estimate_delta_chi2(result, attributions)
    for action in actions:
        action.expected_delta_chi2 = predicted
    # texture and background actions join after the Δχ² stamp: their evidence
    # is per-reflection or whole-pattern, not the gated region attribution the
    # estimate covers — and off-region misfit is by definition outside every
    # region the estimate sums over
    actions += texture_actions(report.texture)
    actions += background_actions(report.background)
    actions = cap_texture_crosstalk(actions, report.texture, report.unmatched)
    actions = note_background_crosstalk(actions, report.background)
    if plan is not None or free_paths is not None:
        actions = apply_strategy_veto(actions, plan, free_paths=free_paths)
    actions.sort(key=lambda a: -a.confidence)
    report.suggested_actions = actions

    n_active = sum(1 for a in actions if a.active)
    report.summary += (f"; Layer 1 on {len([a for a in attributions if a.gates_passed])}"
                       f"/{len(attributions)} regions, {n_active} active suggestion(s)")
    return report

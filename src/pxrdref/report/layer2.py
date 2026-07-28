"""FitReport Layer 2: typed suggested actions — **advisory only**.

Layer 1 says *what* is wrong in physical terms (peaks 0.01° low, 5 % weak).
Layer 2 maps that onto a closed, versioned vocabulary of things a refinement
can actually do, each with a confidence, the alternatives it could not rule
out, and a predicted Δχ².  Three rules keep it honest:

1. **The strategy engine holds the veto.**  :func:`apply_strategy_veto` marks
   any action the staged plan already performs (or a guard forbids); a vetoed
   action stays in the report — silently dropping it would hide the reasoning
   — but ``active`` is False and an agent must not execute it.
2. **Ambiguity is reported, never resolved by fiat.**  Over a short 2θ range
   the position templates (zero / displacement / cell) and the width templates
   (size / strain — the Williamson-Hall problem) are collinear.  When Layer 1
   says the templates are not separable, the competing actions all appear in
   ``alternatives`` and confidence is capped.
3. **Predict, then verify.**  ``expected_delta_chi2`` comes from a linear
   model and is optimistic by construction; :func:`predict_then_verify`
   actually runs the stage and rolls back when the measured improvement does
   not materialise, so a wrong suggestion costs time, not correctness.

New *parameters* additionally need statistical justification before they are
suggested: :func:`hamilton_justified` implements the Hamilton (1965) R-factor
ratio test and ΔBIC, so "add a parameter" is never proposed on the strength of
a cosmetic χ² drop alone.
"""

from __future__ import annotations

import math

import numpy as np

from ..schemas.results import RefinementResult
from .schemas import (
    MIN_COEF_SIGNIFICANCE,
    ActionKind,
    RegionAttribution,
    SuggestedAction,
    TrendAnalysis,
    UnmatchedPeak,
    VerificationOutcome,
)

#: template name → (action, parameter path) for position and width trends
_POSITION_ACTIONS: dict[str, tuple[ActionKind, str]] = {
    "constant": ("refine_zero_shift", "instrument.zero_shift"),
    "cos_theta": ("refine_sample_displacement",
                  "instrument.geometry.sample_displacement"),
    "sin_2theta": ("refine_sample_transparency",
                   "instrument.geometry.sample_transparency"),
    "tan_theta": ("refine_cell", "phases.*.cell.*"),
}
_WIDTH_ACTIONS: dict[str, tuple[ActionKind, str]] = {
    "inv_cos_theta": ("refine_sample_size_broadening", "phases.*.lor_size"),
    "tan_theta": ("refine_sample_strain_broadening", "phases.*.lor_strain"),
}

#: an unmatched observed peak this strong is worth proposing a phase for
IMPURITY_SIGMA = 8.0


def hamilton_justified(chi2_restricted: float, chi2_full: float,
                       n_points: int, n_free_restricted: int,
                       n_added: int, *, alpha: float = 0.05) -> bool:
    """Hamilton's R-factor ratio test for adding ``n_added`` parameters.

    Hamilton (1965), Acta Cryst. 18, 502: under the null hypothesis that the
    added parameters are unnecessary, ℛ = √(χ²_restricted/χ²_full) follows
    the ℛ-distribution, equivalent to the F test

        F = [(χ²_r − χ²_f)/n_added] / [χ²_f/(N − P_f)]

    compared against F(n_added, N − P_f) at ``alpha``.  Returns True when the
    improvement justifies the parameters.
    """
    dof = n_points - n_free_restricted - n_added
    if n_added <= 0 or dof <= 0 or chi2_full <= 0:
        return False
    f = ((chi2_restricted - chi2_full) / n_added) / (chi2_full / dof)
    if f <= 0:
        return False
    from scipy.stats import f as f_dist

    return bool(f > f_dist.ppf(1.0 - alpha, n_added, dof))


def delta_bic(chi2_restricted: float, chi2_full: float,
              n_points: int, n_added: int) -> float:
    """BIC difference (restricted − full); positive favours the fuller model.

    ΔBIC = N·ln(χ²_r/χ²_f) − n_added·ln(N)  (Schwarz 1978, Gaussian errors).
    """
    if chi2_full <= 0 or chi2_restricted <= 0:
        return 0.0
    return (n_points * math.log(chi2_restricted / chi2_full)
            - n_added * math.log(max(n_points, 2)))


def _significant(templates, name: str) -> tuple[float, float] | None:
    for t in templates:
        if t.name == name and t.stderr > 0 and abs(t.coefficient) > MIN_COEF_SIGNIFICANCE * t.stderr:
            return t.coefficient, t.stderr
    return None


def _trend_actions(trend: TrendAnalysis,
                   mapping: dict[str, tuple[ActionKind, str]],
                   unit: str) -> list[SuggestedAction]:
    """Turn one trend analysis into actions, capping confidence on ambiguity."""
    hits = []
    for name, (kind, path) in mapping.items():
        sig = _significant(trend.templates, name)
        if sig is not None:
            hits.append((name, kind, path, sig[0], sig[1]))
    if not hits:
        return []

    quality = max(0.0, min(1.0, max((t.r2 for t in trend.templates), default=0.0)))
    best = max(trend.templates, key=lambda t: t.r2).name
    # importance, not just significance: an observable carrying 2 % of the
    # misfit cannot be a high-confidence call however many σ it stands at
    importance = min(1.0, trend.misfit_share / 0.25)
    peers: list[ActionKind] = [h[1] for h in hits]
    actions: list[SuggestedAction] = []
    for name, kind, path, coef, err in hits:
        alternatives = [k for k in peers if k != kind]
        confidence = (quality * importance
                      * min(1.0, abs(coef) / (MIN_COEF_SIGNIFICANCE * err) / 2.0))
        if name != best:
            confidence *= 0.5      # a runner-up template is not the headline
        rationale = (f"{trend.observable} error follows the {name} template "
                     f"({coef:+.4g} ± {err:.2g} {unit}, R²={quality:.2f}, "
                     f"{trend.misfit_share:.0%} of χ², "
                     f"{trend.n_regions_used} regions)")
        if not trend.separable:
            # collinear over this range: keep every candidate, trust none
            confidence = min(confidence, 0.3)
            alternatives = [k for k in peers if k != kind]
            rationale += ("; templates are collinear over the 2θ range measured "
                          f"(|r|={trend.max_template_collinearity:.3f}) — this "
                          "attribution is NOT separable from its alternatives")
        actions.append(SuggestedAction(
            kind=kind, confidence=round(float(confidence), 3), rationale=rationale,
            parameter_paths=[path], alternatives=alternatives))
    return actions


def layer0_actions(unmatched: list[UnmatchedPeak],
                   attributions: list[RegionAttribution] | None = None
                   ) -> list[SuggestedAction]:
    """Actions justified by **model-free** evidence alone.

    These survive a Layer-1 abstention: an unindexed peak is an unindexed
    peak whether or not the rest of the model is mature enough to linearise
    — indeed a missing phase is a common *reason* for immaturity.

    One correction: a peak-position error also produces residual peaks with
    no tick on top of them (the model's peak sits beside the observed one),
    which would masquerade as an impurity.  Unmatched peaks falling inside a
    region whose fitted position offset is significant are therefore
    attributed to the shift, not to a new phase.
    """
    shifted_regions = [
        a for a in (attributions or [])
        if any(c.kind == "position" and c.significant for c in a.coefficients)
    ]

    def explained_by_shift(u: UnmatchedPeak) -> bool:
        # a mispositioned peak leaves a derivative-shaped residual whose lobes
        # sit up to ~1 FWHM outside the region, so the region is padded before
        # the containment test
        for a in shifted_regions:
            pad = max(a.mean_fwhm, 0.05)
            if a.two_theta_lo - pad <= u.two_theta <= a.two_theta_hi + pad:
                return True
        return False

    strong = [u for u in unmatched
              if u.kind == "unmatched_obs"
              and u.height_over_sigma > IMPURITY_SIGMA
              and not explained_by_shift(u)]
    if not strong:
        return []
    worst = max(strong, key=lambda u: u.height_over_sigma)
    return [SuggestedAction(
        kind="add_impurity_phase",
        confidence=min(0.9, 0.3 + 0.1 * len(strong)),
        rationale=(f"{len(strong)} observed peak(s) have no calculated "
                   f"reflection nearby and are not accounted for by a peak-"
                   f"position error, the strongest at {worst.two_theta:.3f}° "
                   f"at {worst.height_over_sigma:.0f}σ"),
        alternatives=["reindex_or_recheck_cell"],
        two_theta_range=(worst.two_theta, worst.two_theta))]


#: a runner-up axis explaining at least this fraction of the best axis's R²
#: means the axis is not cleanly resolved — the action is still worth taking
#: (the *presence* of texture is established) but its confidence is capped and
#: both axes are named, per the never-a-confident-wrong-singleton rule
TEXTURE_AXIS_AMBIGUITY = 0.8


def texture_actions(texture) -> list[SuggestedAction]:
    """Actions from the March-Dollase texture diagnostic (the WP-0307 orphan,
    claimed by WP-0602).

    Emitted from :attr:`FitReport.texture` entries with ``detected=True`` —
    in the abstained branch too, because uncorrected texture is a common
    *cause* of an immature fit (the same reasoning that computes the analysis
    before the maturity gate).  ``parameter_paths`` names the phase's March
    coefficient whether or not a ``preferred_orientation`` block is declared:
    the strategy veto marks the declared-and-planned case, and on an
    undeclared phase ``predict_then_verify`` frees nothing and rolls back —
    the rationale carries the axis and r so the agent knows what block to
    declare first.  No ``expected_delta_chi2``: the estimate comes from the
    gated region attribution, and this analysis is per-reflection, not
    per-region.
    """
    out: list[SuggestedAction] = []
    for t in texture or []:
        if not t.detected or t.best_axis is None:
            continue
        axis = tuple(int(v) for v in t.best_axis)
        ambiguous = (t.runner_up_axis is not None
                     and t.runner_up_r2 >= TEXTURE_AXIS_AMBIGUITY * t.r2)
        confidence = min(0.85, float(t.r2))
        rationale = (f"per-reflection intensity corrections of phase "
                     f"{t.phase_index} follow a March-Dollase model along "
                     f"{axis} (r={t.march_coefficient:.3f}, R²={t.r2:.2f}, "
                     f"{t.n_reflections_used} reflections)")
        if ambiguous:
            confidence = min(confidence, 0.4)
            runner = tuple(int(v) for v in t.runner_up_axis)
            rationale += (f"; the axis is not cleanly resolved — {runner} "
                          f"fits R²={t.runner_up_r2:.2f}, so refine r but do "
                          "not report the axis as measured")
        rationale += ("; if the phase declares no preferred_orientation block, "
                      "add one with this axis before freeing r")
        out.append(SuggestedAction(
            kind="refine_preferred_orientation",
            confidence=round(confidence, 3), rationale=rationale,
            parameter_paths=[f"phases.{t.phase_index}.preferred_orientation.r"]))
    return out


def suggest_actions(attributions: list[RegionAttribution],
                    trends: list[TrendAnalysis],
                    unmatched: list[UnmatchedPeak],
                    *, rwp: float) -> list[SuggestedAction]:
    """Build the typed action list from Layers 0-1."""
    actions: list[SuggestedAction] = []
    by_obs = {t.observable: t for t in trends}

    if "position" in by_obs:
        actions += _trend_actions(by_obs["position"], _POSITION_ACTIONS, "deg")
    if "width" in by_obs:
        actions += _trend_actions(by_obs["width"], _WIDTH_ACTIONS, "deg")

    # intensity trend vs sin²θ/λ² is the ADP signature; its constant term is
    # a scale error
    intensity = by_obs.get("intensity")
    if intensity is not None and intensity.templates:
        importance = min(1.0, intensity.misfit_share / 0.25)
        best = max(intensity.templates, key=lambda t: t.r2).name
        quality = max(0.0, min(1.0, max(t.r2 for t in intensity.templates)))

        def _conf(name: str) -> float:
            c = quality * importance
            return round(float(c if name == best else 0.5 * c), 3)

        adp = _significant(intensity.templates, "sin2_over_lambda2")
        if adp is not None:
            actions.append(SuggestedAction(
                kind="refine_biso", confidence=_conf("sin2_over_lambda2"),
                rationale=(f"relative intensity error trends with sin²θ/λ² "
                           f"({adp[0]:+.3g} ± {adp[1]:.2g} Å⁻²·rel, "
                           f"{intensity.misfit_share:.0%} of χ²) — the atomic "
                           "displacement-parameter signature"),
                parameter_paths=["phases.*.atoms.*.biso"],
                alternatives=["increase_background_flexibility", "refine_scale"]))
        const = _significant(intensity.templates, "constant")
        if const is not None:
            actions.append(SuggestedAction(
                kind="refine_scale", confidence=_conf("constant"),
                rationale=(f"intensities are uniformly {const[0]:+.1%} off across "
                           f"the pattern ({intensity.misfit_share:.0%} of χ²) — "
                           "an angle-independent scale error"),
                parameter_paths=["phases.*.scale"],
                alternatives=["refine_biso"]))

    # asymmetry: a significant coefficient in the low-angle regions
    low = [a for a in attributions if a.gates_passed and a.mean_two_theta < 40.0]
    asym = [c for a in low for c in a.coefficients
            if c.kind == "asymmetry" and c.significant]
    if asym:
        actions.append(SuggestedAction(
            kind="refine_axial_asymmetry", confidence=0.5,
            rationale=(f"axial-divergence shape term is significant in "
                       f"{len(asym)} low-angle region(s)"),
            parameter_paths=["instrument.geometry.axial_sl",
                             "instrument.geometry.axial_hl"],
            two_theta_range=(min(a.two_theta_lo for a in low),
                             max(a.two_theta_hi for a in low))))

    actions += layer0_actions(unmatched, attributions)

    # regions that failed the validity radius: the model is far enough off that
    # linearising is wrong — say so instead of proposing a small correction
    far = [a for a in attributions
           if any("validity_radius" in f for f in a.gate_failures)]
    if far and rwp > 0.2:
        actions.append(SuggestedAction(
            kind="reindex_or_recheck_cell", confidence=0.4,
            rationale=(f"{len(far)} region(s) have peak offsets beyond the "
                       "linearisation radius — the cell or indexing is wrong "
                       "enough that shift-based corrections do not apply"),
            parameter_paths=["phases.*.cell.*"]))

    actions.sort(key=lambda a: -a.confidence)
    return actions


def apply_strategy_veto(actions: list[SuggestedAction], plan, *,
                        free_paths: list[str] | None = None
                        ) -> list[SuggestedAction]:
    """Mark actions the staged plan already covers.  **The engine wins.**

    An action whose parameters the plan refines (in any stage) is redundant;
    one whose parameters are already free in the current fit is likewise not
    news.  Both are annotated rather than removed, so the report still shows
    *why* the engine thinks the misfit is explained.
    """
    import fnmatch

    planned: set[str] = set()
    for stage in getattr(plan, "stages", []):
        planned.update(stage.turn_on)
    free = set(free_paths or [])

    for action in actions:
        for path in action.parameter_paths:
            if any(fnmatch.fnmatchcase(g, path) or fnmatch.fnmatchcase(path, g)
                   for g in planned):
                action.vetoed_by = f"already refined by the staged plan ({path})"
                break
            if any(fnmatch.fnmatchcase(f, path) for f in free):
                action.vetoed_by = f"already free in this refinement ({path})"
                break
    return actions


def predict_then_verify(refinement, data, action: SuggestedAction, *,
                        min_improvement: float = 0.01) -> VerificationOutcome:
    """Try an action on a branch, keep it only if χ² actually improves.

    Runs on a *branch* of the refinement history when one is available, so a
    rejected action leaves no trace in the working state — the rollback is
    structural, not a manual undo.  ``min_improvement`` is the fractional χ²
    reduction required to accept.
    """
    from ..strategy.staged import Stage

    if refinement.result_ is None:
        raise RuntimeError("run a fit before verifying an action")
    before = refinement.result_.statistics.chi2
    if not action.parameter_paths:
        return VerificationOutcome(
            kind=action.kind, predicted_delta_chi2=action.expected_delta_chi2,
            observed_delta_chi2=0.0, accepted=False,
            reason="action carries no refinable parameter paths")

    trial = refinement.branch() if refinement.history is not None else refinement
    stage = Stage(f"verify:{action.kind}", list(action.parameter_paths))
    try:
        after = trial.run_stage(data, stage).statistics.chi2
    except Exception as exc:  # a failed trial is a rejection, not a crash
        return VerificationOutcome(
            kind=action.kind, predicted_delta_chi2=action.expected_delta_chi2,
            observed_delta_chi2=0.0, accepted=False,
            reason=f"trial refinement failed: {exc}")

    observed = before - after
    accepted = observed > min_improvement * abs(before)
    return VerificationOutcome(
        kind=action.kind, predicted_delta_chi2=action.expected_delta_chi2,
        observed_delta_chi2=float(observed), accepted=bool(accepted),
        reason=(f"χ² {before:.4g} → {after:.4g} "
                f"({observed / abs(before):+.2%}); "
                f"{'accepted' if accepted else 'rolled back'}"))


def estimate_delta_chi2(result: RefinementResult,
                        attributions: list[RegionAttribution]) -> float | None:
    """Optimistic χ² reduction if every gated region's misfit were removed.

    Upper bound by construction (it assumes the linear model is exact and the
    corrections are mutually compatible); reported so an agent can rank
    actions, never as a promise.
    """
    usable = [a for a in attributions if a.gates_passed]
    if not usable:
        return None
    share = sum(a.chi2_share * max(min(a.r2, 1.0), 0.0) for a in usable)
    return float(share * result.statistics.chi2 * np.clip(result.statistics.n_points, 1, None)
                 / max(result.statistics.n_points, 1))

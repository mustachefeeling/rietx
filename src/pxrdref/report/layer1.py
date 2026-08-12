"""FitReport Layer 1: gated linear misfit attribution.

For each region the residual Δ = y_obs − y_calc is projected onto a
**shape-derivative basis** built analytically from the profile itself — not
from the parameter Jacobian, so the answer is "the peaks here are 0.01° low
and 5 % too weak", independent of which parameters happen to be free:

    Δ(2θ) ≈ a_I·Σ_k I_k Ω_k        (relative intensity error)
          + a_p·Σ_k I_k ∂Ω_k/∂pos  (Δ2θ, degrees)
          + a_w·Σ_k I_k ∂Ω_k/∂Γ    (ΔΓ, degrees)
          + a_η·Σ_k I_k ∂Ω_k/∂η    (Δη)
          + a_S·Σ_k I_k ∂Ω_k/∂(S/L)(axial asymmetry)

The five columns are **not orthogonal**, so they are fitted in one joint
weighted solve and the Gram matrix's condition number is reported alongside;
independent dot-products would cross-contaminate (a width error partly reads
as an intensity error and vice versa).

Nothing here is trustworthy unconditionally, hence the gates
(:mod:`.schemas` pins the thresholds):

* **local R²** — does this basis explain the region's misfit at all?
* **validity radius** — a linearised shift is meaningful only well inside the
  peak.  A peak 5 FWHM away must produce "re-detect, don't linearise", never a
  confident small-offset reading.
* **resolvability** — Gram condition number and per-coefficient significance.
* **global maturity** — if the fit is immature the whole layer *abstains*
  rather than attributing structure to what is really a bad starting model.

On top of the per-region view, :func:`analyse_trends` regresses the region
coefficients against the angular templates that per-region views structurally
miss (position vs constant / cosθ / sin2θ / tanθ, width vs 1/cosθ and tanθ,
intensity vs sin²θ/λ² — the ADP signature), reporting the inter-template
collinearity *over the range actually sampled* so an unseparable pair is
declared unseparable instead of resolved into a confident wrong singleton.
"""

from __future__ import annotations

import numpy as np

from ..model.forward import CompiledModel, DerivativeBases
from .schemas import (
    MATURITY_MAX_RWP,
    MATURITY_MIN_EXPLAINED_FRACTION,
    MATURITY_MIN_MISFIT_SHARE,
    MAX_GRAM_CONDITION,
    MIN_COEF_SIGNIFICANCE,
    MIN_REGION_CHI2_RED,
    MIN_REGION_R2,
    REINDEX_MIN_FAR_FRACTION,
    REINDEX_MIN_FAR_REGIONS,
    RESOLUTION_LIMITED_MIN_FRACTION,
    RESOLUTION_LIMITED_MIN_R2,
    RESOLUTION_LIMITED_MIN_REGIONS,
    SEPARABILITY_MIN_SS_RATIO,
    VALIDITY_RADIUS_FWHM,
    BasisCoefficient,
    Region,
    RegionAttribution,
    TrendAnalysis,
    TrendTemplate,
)

_KINDS = ("intensity", "position", "width", "mixing", "asymmetry")


def _region_columns(model: CompiledModel, bases: DerivativeBases,
                    lo: float, hi: float
                    ) -> tuple[np.ndarray, np.ndarray, float, float, int]:
    """Assemble the (5, n_points_in_region) basis for one region.

    Every peak whose *centre* lies in the region contributes; its full frozen
    window is used, clipped to the region, so a peak's tail outside the region
    is simply not scored (regions are cut between peaks).
    """
    m = (model.tt >= lo) & (model.tt <= hi)
    idx = np.nonzero(m)[0]
    if len(idx) == 0:
        return np.zeros((5, 0)), idx, 0.0, 0.0, 0
    i_start, i_stop = int(idx[0]), int(idx[-1]) + 1
    cols = np.zeros((5, i_stop - i_start), dtype=np.float64)

    n_refl = 0
    tt_sum = fwhm_sum = weight_sum = 0.0
    for ip, rows in enumerate(bases.entries):
        for (il, k, w0, w1, omega, d_pos, d_gamma, d_eta, d_sl, _d_hl) in rows:
            pos, gamma, _eta, intensity = bases.peaks[ip][il]
            centre = pos[k]
            if not (lo <= centre <= hi):
                continue
            n_refl += 1
            weight = abs(float(intensity[k]))
            tt_sum += weight * float(centre)
            fwhm_sum += weight * float(gamma[k])
            weight_sum += weight
            a, b = max(w0, i_start), min(w1, i_stop)
            if b <= a:
                continue
            sl_a, sl_b = a - w0, b - w0
            dst_a, dst_b = a - i_start, b - i_start
            amp = float(intensity[k])
            cols[0, dst_a:dst_b] += amp * omega[sl_a:sl_b]
            cols[1, dst_a:dst_b] += amp * d_pos[sl_a:sl_b]
            cols[2, dst_a:dst_b] += amp * d_gamma[sl_a:sl_b]
            cols[3, dst_a:dst_b] += amp * d_eta[sl_a:sl_b]
            if d_sl is not None:
                cols[4, dst_a:dst_b] += amp * d_sl[sl_a:sl_b]

    mean_tt = tt_sum / weight_sum if weight_sum > 0 else 0.5 * (lo + hi)
    mean_fwhm = fwhm_sum / weight_sum if weight_sum > 0 else 0.0
    return cols, np.arange(i_start, i_stop), mean_tt, mean_fwhm, n_refl


def attribute_region(model: CompiledModel, bases: DerivativeBases,
                     region: Region, delta: np.ndarray, sqrt_w: np.ndarray
                     ) -> RegionAttribution | None:
    """Joint weighted solve of one region's residual against the shape basis."""
    cols, idx, mean_tt, mean_fwhm, n_refl = _region_columns(
        model, bases, region.two_theta_lo, region.two_theta_hi)
    if len(idx) == 0 or n_refl == 0:
        return None

    sw = sqrt_w[idx]
    a = (cols * sw).T                       # (n_points, 5)
    b = delta[idx] * sw
    live = np.nonzero(np.linalg.norm(a, axis=0) > 0.0)[0]
    if len(live) == 0 or len(idx) <= len(live):
        return None
    a = a[:, live]

    gram = a.T @ a
    # Resolvability is about the *angles* between the basis columns, not their
    # units: ∂Ω/∂pos is ~1/FWHM times larger than Ω, which alone puts cond(G)
    # near 10⁴ in every region.  Condition the scale-normalised Gram (a
    # correlation matrix, cf. Belsley-Kuh-Welsch) so the number means
    # collinearity — measured range 17 … 6×10⁴ on the same data where the raw
    # number sat at 7×10³ … 1×10⁶ regardless of separability.
    scale = np.linalg.norm(a, axis=0)
    normed = a / scale
    cond = float(np.linalg.cond(normed.T @ normed))
    coef, *_ = np.linalg.lstsq(a, b, rcond=None)
    resid = b - a @ coef
    ss_tot = float(b @ b)
    r2 = float(1.0 - (resid @ resid) / ss_tot) if ss_tot > 0 else 0.0

    # Gram covariance, scaled by the region's own residual variance
    dof = max(len(idx) - len(live), 1)
    sigma2 = float(resid @ resid) / dof
    cov = np.linalg.pinv(gram) * sigma2
    err = np.sqrt(np.maximum(np.diag(cov), 0.0))

    # relative importance of each term: how much signal its fitted amplitude
    # actually puts into the region, not merely whether it is nonzero
    contribution = (np.abs(coef) * scale) ** 2
    total_contribution = float(contribution.sum())

    coefficients: list[BasisCoefficient] = []
    for slot, c, e, contrib in zip(live, coef, err, contribution, strict=True):
        coefficients.append(BasisCoefficient(
            kind=_KINDS[slot], value=float(c), stderr=float(e),
            significant=bool(abs(c) > MIN_COEF_SIGNIFICANCE * e) if e > 0 else False,
            share=float(contrib / total_contribution) if total_contribution > 0 else 0.0))

    # is there anything to attribute?  On a region already fitted to the
    # counting noise the basis legitimately explains nothing (R² ≈ 0), which
    # must not be reported as a failed gate.
    chi2_red = ss_tot / max(len(idx), 1)
    has_misfit = chi2_red > MIN_REGION_CHI2_RED

    failures: list[str] = []
    if not has_misfit:
        failures.append(f"no_significant_misfit(χ²_red={chi2_red:.2f})")
    else:
        if r2 < MIN_REGION_R2:
            failures.append(f"local_r2={r2:.2f}<{MIN_REGION_R2}")
        if cond > MAX_GRAM_CONDITION:
            failures.append(f"gram_condition={cond:.1e}>{MAX_GRAM_CONDITION:.0e}")
        shift = next((c.value for c in coefficients if c.kind == "position"), 0.0)
        if mean_fwhm > 0 and abs(shift) > VALIDITY_RADIUS_FWHM * mean_fwhm:
            failures.append(
                f"outside_validity_radius(|Δ2θ|={abs(shift):.3f}°>"
                f"{VALIDITY_RADIUS_FWHM}·FWHM={VALIDITY_RADIUS_FWHM * mean_fwhm:.3f}°)"
                " — re-detect the peak rather than linearising")

    return RegionAttribution(
        two_theta_lo=region.two_theta_lo, two_theta_hi=region.two_theta_hi,
        n_reflections=n_refl, chi2_share=region.chi2_share,
        mean_two_theta=mean_tt, mean_fwhm=mean_fwhm,
        coefficients=coefficients, r2=r2, gram_condition=cond,
        chi2_reduced=float(chi2_red), has_significant_misfit=bool(has_misfit),
        gates_passed=not failures, gate_failures=failures,
    )


def attribute_regions(model: CompiledModel, values: dict[str, float],
                      regions: list[Region]) -> list[RegionAttribution]:
    """Layer-1 attribution for every region (gates evaluated per region)."""
    y_calc = model.evaluate(values)
    delta = model.y_obs - y_calc
    sqrt_w = 1.0 / model.sigma
    bases = model.derivative_bases(values)
    out = []
    for region in regions:
        att = attribute_region(model, bases, region, delta, sqrt_w)
        if att is not None:
            out.append(att)
    return out


def maturity_gate(rwp: float, attributions: list[RegionAttribution]
                  ) -> str | None:
    """Global abstention check.  Returns a reason, or None when Layer 1 may speak.

    Attributing a *bad model* to specific small parameter errors is the
    failure mode this prevents: with Rwp of 50 % the residual is dominated by
    something the shape basis cannot represent at all, and any coefficient it
    returns is an artefact of projecting onto the wrong space.

    A fit with **no** significantly-misfitting region does not abstain: there
    is simply nothing to attribute, which is a legitimate (and common) answer
    that Layer 1 should be able to give.  Abstention is only for the case
    where real misfit exists but cannot be read reliably.
    """
    if rwp > MATURITY_MAX_RWP:
        return (f"fit is immature (Rwp={rwp:.3f} > {MATURITY_MAX_RWP}); "
                "Layer 1 abstains — fix the model/starting values first")

    misfitting = [a for a in attributions if a.has_significant_misfit]
    misfit_share = sum(a.chi2_share for a in misfitting)
    if misfit_share <= MATURITY_MIN_MISFIT_SHARE:
        return None            # nothing substantial to attribute

    usable_share = sum(a.chi2_share for a in misfitting if a.gates_passed)
    if usable_share < MATURITY_MIN_EXPLAINED_FRACTION * misfit_share:
        return (f"regions carrying {misfit_share:.0%} of χ² misfit, but only "
                f"{usable_share / misfit_share:.0%} of that sits in regions "
                f"the local gates accept (need "
                f"{MATURITY_MIN_EXPLAINED_FRACTION:.0%}); Layer 1 abstains")
    return None


def abstention_flavour(rwp: float, attributions: list[RegionAttribution]
                       ) -> tuple[str, str | None]:
    """Classify an abstention :func:`maturity_gate` has already decided.

    Returns ``(kind, extra)``: ``kind`` is the
    :attr:`~pxrdref.report.schemas.FitReport.abstained_kind` value and
    ``extra``, when set, is the resolution-limited sentence appended to the
    reason.  Purely a *reading* of the per-region gate evidence — no
    threshold that decides abstention is consulted, so the abstain/speak
    boundary cannot move here (WP-1057).

    The order of the arms is the argument (measured grounds on the schema
    constants): widespread validity failure is position-family model error
    and must win even though a wrong cell fails the Gram gate widely too;
    only past it can Gram-dominance with high local R² be read as "the data's
    resolution limits attribution", the state broad-peak specimens
    (nanoparticles, MOFs) live in permanently.
    """
    if rwp > MATURITY_MAX_RWP:
        return "immature", None
    misfitting = [a for a in attributions if a.has_significant_misfit]
    failing = [a for a in misfitting if not a.gates_passed]
    far = [a for a in failing
           if any("validity_radius" in f for f in a.gate_failures)]
    if (len(far) >= REINDEX_MIN_FAR_REGIONS
            and len(far) >= REINDEX_MIN_FAR_FRACTION * len(misfitting)):
        return "unreadable", None    # reindex_action carries this story
    gram = [a for a in failing
            if any("gram_condition" in f for f in a.gate_failures)]
    gram_only = [a for a in failing if a.gate_failures
                 and all("gram_condition" in f for f in a.gate_failures)]
    if (failing and len(gram) >= RESOLUTION_LIMITED_MIN_FRACTION * len(failing)
            and len(gram_only) >= RESOLUTION_LIMITED_MIN_REGIONS):
        median_r2 = float(np.median([a.r2 for a in gram_only]))
        if median_r2 >= RESOLUTION_LIMITED_MIN_R2:
            extra = (
                f"the failures are collinearity on merged peaks, not "
                f"unexplained misfit ({len(gram)} of {len(failing)} "
                f"gate-failing region(s) fail the Gram condition; the "
                f"{len(gram_only)} failing nothing else carry median local "
                f"R²={median_r2:.2f}, so the shape basis explains the misfit "
                f"but its edit directions are indistinguishable at this "
                f"resolution).  Resolution-limited, not evidence the model "
                f"is wrong: the misfit is readable in aggregate (Rwp, the "
                f"Le Bail gap), not attributable per kind — on broad-peak "
                f"data this can be a legitimate stopping point")
            return "resolution_limited", extra
    return "unreadable", None


# ----------------------------------------------------------------------
# hkl-grouped angular trends
# ----------------------------------------------------------------------
def _templates(observable: str, two_theta: np.ndarray, wavelength: float
               ) -> dict[str, np.ndarray]:
    theta = np.radians(two_theta / 2.0)
    if observable == "position":
        return {
            "constant": np.ones_like(theta),          # zero-point error
            "cos_theta": np.cos(theta),               # specimen displacement
            "sin_2theta": np.sin(2.0 * theta),        # transparency
            "tan_theta": np.tan(theta),               # cell (Δd/d)
        }
    if observable == "width":
        return {
            "inv_cos_theta": 1.0 / np.cos(theta),     # crystallite size
            "tan_theta": np.tan(theta),               # microstrain
        }
    # intensity: I_obs/I_calc ~ exp(−2ΔB·sin²θ/λ²) ⇒ relative error linear
    # in sin²θ/λ² near ΔB = 0
    return {
        "constant": np.ones_like(theta),
        "sin2_over_lambda2": (np.sin(theta) / wavelength) ** 2,
    }


def analyse_trends(attributions: list[RegionAttribution], wavelength: float
                   ) -> list[TrendAnalysis]:
    """Fit the angular templates to the per-region coefficients.

    Only regions that passed their local gates contribute — a coefficient the
    gates rejected is not evidence.  Each observable is fitted jointly across
    its templates (they are correlated by construction), and the collinearity
    actually present over the sampled angles decides ``separable``.
    """
    kind_for = {"position": "position", "width": "width", "intensity": "intensity"}
    out: list[TrendAnalysis] = []
    usable = [a for a in attributions if a.gates_passed]

    for observable, coef_kind in kind_for.items():
        pts = []
        shares = []
        for att in usable:
            c = next((c for c in att.coefficients
                      if c.kind == coef_kind and c.stderr > 0), None)
            if c is not None:
                pts.append((att.mean_two_theta, c.value, c.stderr))
                shares.append(att.chi2_share * c.share)
        if len(pts) < 3:
            out.append(TrendAnalysis(observable=observable, n_regions_used=len(pts)))
            continue

        tt = np.array([p[0] for p in pts])
        val = np.array([p[1] for p in pts])
        w = 1.0 / np.array([p[2] for p in pts])

        templates = _templates(observable, tt, wavelength)
        names = list(templates)
        design = np.vstack([templates[n] for n in names])
        if len(pts) <= 2:
            out.append(TrendAnalysis(observable=observable, n_regions_used=len(pts)))
            continue

        # Nested model comparison, one template at a time — NOT a joint fit.
        # Jointly fitting collinear templates is numerically ill-posed and
        # returns physically absurd amplitudes (measured: a 0.02° zero-point
        # error came back as a 1.8° "constant" cancelled by a −1.8° "cosθ").
        # Each template is therefore scored alone, and the ambiguity is
        # expressed by how close the runners-up come.
        b = val * w
        # through-origin fits (a template with no intercept), so R² is
        # measured against the uncentred total — "how much of the observed
        # trend does this single physical cause account for"
        ss_tot = float(b @ b)
        fitted: list[TrendTemplate] = []
        for name in names:
            col = (templates[name] * w)[:, None]
            coef, *_ = np.linalg.lstsq(col, b, rcond=None)
            resid = b - col @ coef
            r2 = float(1.0 - (resid @ resid) / ss_tot) if ss_tot > 0 else 0.0
            dof = max(len(pts) - 1, 1)
            var = float(resid @ resid) / dof / max(float(col.ravel() @ col.ravel()), 1e-300)
            fitted.append(TrendTemplate(name=name, coefficient=float(coef[0]),
                                        stderr=float(np.sqrt(max(var, 0.0))),
                                        r2=r2))

        # collinearity between templates over the angles actually sampled
        norm = design / np.maximum(np.linalg.norm(design, axis=1, keepdims=True), 1e-300)
        gram = np.abs(norm @ norm.T)
        np.fill_diagonal(gram, 0.0)
        collinearity = float(gram.max()) if len(names) > 1 else 0.0

        ranked = sorted(fitted, key=lambda t: -t.r2)
        if len(ranked) > 1:
            # residual-SS ratio: how much more the runner-up leaves unexplained
            best_ss = max(1.0 - ranked[0].r2, 1e-12)
            ratio = (1.0 - ranked[1].r2) / best_ss
        else:
            ratio = np.inf
        out.append(TrendAnalysis(
            observable=observable, n_regions_used=len(pts),
            templates=fitted,
            max_template_collinearity=collinearity,
            separability_ratio=float(min(ratio, 1e6)),
            separable=bool(ratio > SEPARABILITY_MIN_SS_RATIO),
            misfit_share=float(sum(shares)),
        ))
    return out

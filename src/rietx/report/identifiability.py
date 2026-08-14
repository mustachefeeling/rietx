"""FitReport identifiability section — is the converged answer the only one?

Everything here is read from the stored result (statistics, parameter values
and esds, the residual arrays for δR) plus the parameter-space evidence the
fit screened onto :class:`~rietx.schemas.results.Identifiability` (the
Jacobian is never serialized).  Nothing is linearised and no region is
consulted, so the section speaks on an abstained report too.

The contract, the reading and the citations are the
:class:`~rietx.report.schemas.IdentifiabilityEvidence` and
:class:`~rietx.report.schemas.ExchangeFinding` docstrings; this module is
how the numbers are computed, and the predicates the summary clause and the
protocol reading share.

**Measured separations** (LaB₆ fixtures, 2026-08-12; thresholds in
:mod:`~rietx.report.schemas`, the spike table in the WP-1056 handover):

=====================================  ========  =============  ==========
state                                  R²(disp)   partner σ      softest λ
=====================================  ========  =============  ==========
E2 (planted displacement, held)        0.999945   zero: 127.7    1.21e-02
clean reference, full window           0.999945   zero: 1.6      1.21e-02
20-56° window (E8-shaped, converged)   1.000000   zero: 1.2      6.68e-04
=====================================  ========  =============  ==========

R² and the soft spectrum are *identical* between E2 and clean — both are
design-matrix properties of the sampled range — so each clause requires the
half a design matrix cannot supply: the exchange clause a partner
significantly off its null, the soft-mode clause an eigenvalue below what
every full-window TCHZ fit carries anyway (the u/v/w family combination,
softer than its worst pair shows, 1.21e-02 on the clean control).
"""

from __future__ import annotations

import numpy as np
from scipy.special import ndtri

from ..optimize.identifiability import NULL_IDENTITY
from ..schemas.results import ExchangeRow, RefinementResult
from .schemas import (
    EXCHANGE_PARTNER_MIN_SIGNIFICANCE,
    EXCHANGEABLE_MIN_R2,
    RIVAL_DECISIVE_MIN_CHI2_RATIO,
    SOFT_MODE_NOTABLE_EIGENVALUE,
    ExchangeFinding,
    IdentifiabilityEvidence,
    SoftMode,
)


def is_exchangeable(r2: float, partner_significance: float | None) -> bool:
    """The two-condition discriminator — the one predicate the summary
    clause, the ``exchangeable`` field and AGENT_PROTOCOL's reading share.

    Both halves are required because either alone fires on a clean fit:
    R² is a design-matrix property (measured identical on E2 and its clean
    reference), and a significant partner with a low R² is just a fitted
    parameter with nothing to exchange against.
    """
    return (r2 >= EXCHANGEABLE_MIN_R2
            and partner_significance is not None
            and partner_significance >= EXCHANGE_PARTNER_MIN_SIGNIFICANCE)


def _delta_r(result: RefinementResult) -> tuple[float, float] | None:
    """Slope and intercept of the δR normal-probability plot.

    Sorted Δ/σ against normal order-statistic quantiles (Blom's plotting
    positions, (i − 3/8)/(n + 1/4)), least-squares line.  Abrahams & Keve
    (1971): Gaussian residuals on honest σ read slope 1, intercept 0.
    """
    if len(result.y_obs) < 8 or len(result.y_calc) != len(result.y_obs):
        return None
    delta = ((np.asarray(result.y_obs, dtype=np.float64)
              - np.asarray(result.y_calc, dtype=np.float64)) / result.sig())
    n = delta.size
    q = ndtri((np.arange(1, n + 1) - 0.375) / (n + 0.25))
    slope, intercept = np.polyfit(q, np.sort(delta), 1)
    return float(slope), float(intercept)


def _assess_exchange(row: ExchangeRow,
                     fitted: dict[str, tuple[float, float | None]],
                     ) -> ExchangeFinding:
    """One carrier row + the significance half from the stored parameters.

    The partner is the most-loaded one with a defined null; loadings are the
    fit-time reconstruction coefficients, so no re-measurement happens here —
    only a lookup of the partner's fitted value and esd.
    """
    partner = None
    for path in sorted(row.partners, key=lambda p: -abs(row.partners[p])):
        if path in NULL_IDENTITY and path in fitted:
            partner = path
            break
    if partner is None:
        return ExchangeFinding(held=row.held, r2=row.r2,
                               partners=dict(row.partners))
    null = NULL_IDENTITY[partner]
    value, esd = fitted[partner]
    significance = abs(value - null) / esd if esd else None
    return ExchangeFinding(
        held=row.held, r2=row.r2, partners=dict(row.partners),
        partner=partner, partner_null=null, partner_value=value,
        partner_esd=esd, partner_significance=significance,
        exchangeable=is_exchangeable(row.r2, significance))


def assess_identifiability(result: RefinementResult
                           ) -> IdentifiabilityEvidence | None:
    """Assemble the section; ``None`` only for a result with no channels."""
    if not result.y_obs:
        return None
    dr = _delta_r(result)
    carrier = result.identifiability
    exchanges = None
    top = None
    modes = None
    if carrier is not None:
        top = list(carrier.top_correlations) or None
        modes = list(carrier.soft_modes) or None
        if carrier.exchangeability:
            fitted = {p.path: (p.value, p.stderr) for p in result.parameters}
            exchanges = [_assess_exchange(row, fitted)
                         for row in carrier.exchangeability]
    return IdentifiabilityEvidence(
        chi2_reduced=result.statistics.chi2,
        esd_inflation=result.statistics.esd_inflation,
        durbin_watson=result.statistics.durbin_watson,
        delta_r_slope=dr[0] if dr else None,
        delta_r_intercept=dr[1] if dr else None,
        top_correlations=top, soft_modes=modes, exchanges=exchanges)


def _render_mode(mode: SoftMode) -> str:
    """A soft mode as the named combination, largest loading first."""
    parts = []
    for path, v in sorted(mode.loadings.items(), key=lambda kv: -abs(kv[1])):
        sign = "−" if v < 0 else ("+" if parts else "")
        parts.append(f"{sign}{abs(v):.2f}·{path}")
    return " ".join(parts)


def identifiability_clause(evidence: IdentifiabilityEvidence | None
                           ) -> str | None:
    """The summary's identifiability clause(s), or None when nothing crosses
    a comment threshold.

    At most two statements: the strongest firing exchange (others counted,
    never listed — the exchanges table has them), and the softest notable
    mode.  Thresholds decide where the *comment* starts, never what the
    section carries.

    **The exchange sentence makes a claim about this *fit*, and names the
    experiment** (WP-1063).  Both halves are corrections, each with its own
    measurement behind it:

    - *the level*.  "The data cannot tell" is false where the data can: on
      real SRM 660c the R² 0.9977 zero↔displacement pair is separated
      decisively by fitting each rival alone with the other at its null —
      Rwp 0.09361 / χ² 4.0752 against 0.08661 / 3.4890 on 5332 points, and
      the zero-only model biases *a* by +100 ppm.  R² is a **geometric**
      measure of column overlap; at these counting statistics the 0.23 % it
      leaves unexplained decides.  So the sentence says what is true of the
      fit in hand, and points at the measurement that settles it.
    - *the action*.  Naming a degeneracy without naming what to do about it
      is read as an invitation to free the rival.  Measured over 30 real
      agent runs (WP-1059): seven of the twenty position-episode cells
      answered this sentence by freeing **both** parameters onto the ridge
      the manual forbids, and in six of the seven the clause was in the
      agent's context before it wrote that overlay
      (``tests/eval_report_agent/mine_transcripts.py``).  Only two of the
      seven ever quoted it — a reader acts on this sentence without echoing
      it, which is why the fix is the sentence and not its prominence.

    - *the license* (WP-1065).  Naming the experiment without saying what
      its outcome licenses reproduces the same failure one step later:
      round 3 of the report eval measured a real decisive state (SRM 660c,
      knocked displacement, rivals separated at χ² ratio 1.1679) going 0/7
      valid — cells ran the swap, won it, and had nowhere to read that
      winning it is an answer, so they declined or hedged a solved fit.  The
      continuation states **both** branches — decisive (the data has chosen;
      the winning rival's fit is the answer, quoted without caveat) and tie
      (protocol, or the declared stand-off) — because round 2 measured the
      cost of naming the degeneracy without the action and round 3 the cost
      of naming the experiment without the license, and stating only the
      decisive branch would recreate the asymmetry a third time, on ties.
      The strength grade is :data:`~rietx.report.schemas
      .RIVAL_DECISIVE_MIN_CHI2_RATIO`, quoted live rather than restated; no
      verdict token enters the summary — the license is stated, the verdict
      stays the reader's.

    It names the experiment, never the API: :func:`~rietx.report.layer2
    .compare_rivals` runs exactly this and AGENT_PROTOCOL §9 names it, but a
    summary string that named a function would be advice a non-python
    consumer cannot take.
    """
    if evidence is None:
        return None
    clauses = []
    firing = [e for e in (evidence.exchanges or []) if e.exchangeable]
    if firing:
        worst = max(firing, key=lambda e: e.r2)
        others = (f" (and {len(firing) - 1} more held candidate(s), "
                  f"see identifiability.exchanges)" if len(firing) > 1 else "")
        clauses.append(
            f"fitted {worst.partner} = {worst.partner_value:.6g} stands "
            f"{worst.partner_significance:.0f}σ from {worst.partner_null:g} "
            f"but is exchangeable with the held {worst.held} "
            f"(R² = {worst.r2:.4f}){others} — this fit cannot tell which is "
            f"physical; resolve it by measurement, never by freeing both into "
            f"one fit (that is a ridge): fit each of the pair alone with the "
            f"other held at its null and compare χ²; a χ² gap of "
            f"≥ {RIVAL_DECISIVE_MIN_CHI2_RATIO - 1:.0%} means the data has "
            f"chosen — the winning rival's fit is the answer, quoted without "
            f"caveat; a smaller gap means the pair is genuinely unresolved: "
            f"fix it by protocol (a calibrant-fixed zero, a wider window) or "
            f"say the data has not chosen")
    softest = min((m for m in (evidence.soft_modes or [])
                   if m.eigenvalue < SOFT_MODE_NOTABLE_EIGENVALUE),
                  key=lambda m: m.eigenvalue, default=None)
    if softest is not None:
        clauses.append(
            f"the combination {_render_mode(softest)} is unconstrained at "
            f"the {softest.eigenvalue:.1e} level — these parameters trade "
            f"freely and their individual esds are not independent")
    return "; ".join(clauses) if clauses else None

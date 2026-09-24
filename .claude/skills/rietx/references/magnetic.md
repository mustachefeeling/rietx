# 7j. The magnetic family: a stated moment

Load it when a magnetic `Diagnostic` fired — from `analyse_moments` on a fit's `FitReport.magnetic` rows.

*A reference file of the `rietx` skill. The body it belongs to is [`SKILL.md`](../SKILL.md); section numbers are the ones the body cites.*

The magnetic diagnostic family lives in this one file rather than in §7's tables (`references/diagnostics.md`; maintainer ruling, issue #286): one order-parameter question, one file. **Moment codes** are about a refined moment (WP-1327) and ride on the report's `MomentEvidence` rows (`analyse_moments`, `FitReport.magnetic`), and each row says which channel it takes.

## Moment codes

| code | what you must not assume, and what to do |
|---|---|
| `MOMENT_PAIR_DEGENERATE` | (info — from `report.magnetic.moment_pair_diagnostics` over `analyse_moments`' rows) Read either site's own `MomentEvidence.magnitude` for a paired row. The powder measures only the pair's quadrature sum, `sqrt(m_a^2 + m_b^2)` (`MomentEvidence.paired_magnitude` and `.paired_magnitude_esd`, `paired_with` naming the other site) — the two moduli are correlated in the fit and not separately determined, so either one's raw magnitude is an artefact of that correlation rather than a measurement |

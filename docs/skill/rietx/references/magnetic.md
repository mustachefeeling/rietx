# 7j. The magnetic family: a stated moment and the child group it implies

Load it when a magnetic `Diagnostic` fired — from `analyse_moments` on a fit's `FitReport.magnetic` rows, or from `magnetic_supercell`'s returned statement.

*A reference file of the `rietx` skill. The body it belongs to is [`SKILL.md`](../SKILL.md); section numbers are the ones the body cites.*

The magnetic diagnostic family lives in this one file rather than in §7's tables (`references/diagnostics.md`; maintainer ruling, issue #286): one order-parameter question, one file. **The channel varies by table**, and each row says which:

* **Moment codes** are about a refined moment (WP-1327) and ride on the report's `MomentEvidence` rows (`analyse_moments`, `FitReport.magnetic`).
* **Candidate codes** are not on `result.diagnostics` at all: they are on the `SupercellStatement` `magnetic_supercell` returns, because the question — does a Hermann-Mauguin symbol name the child group this cell carries — is settled before a fit exists, the same way a project reader's own codes are.

## Moment codes

| code | what you must not assume, and what to do |
|---|---|
| `MOMENT_PAIR_DEGENERATE` | (info — from `report.magnetic.moment_pair_diagnostics` over `analyse_moments`' rows) Read either site's own `MomentEvidence.magnitude` for a paired row. The powder measures only the pair's quadrature sum, `sqrt(m_a^2 + m_b^2)` (`MomentEvidence.paired_magnitude` and `.paired_magnitude_esd`, `paired_with` naming the other site) — the two moduli are correlated in the fit and not separately determined, so either one's raw magnitude is an artefact of that correlation rather than a measurement |

## Candidate codes

| code | what you must not assume, and what to do |
|---|---|
| `CHILD_GROUP_UNNAMED` | (info — from `magnetic_supercell`, on the returned statement rather than on a `FitReport`) Read the child's `space_group` as a symbol. It is a **label**: the bracketed form `'Pm [unnamed in 2a,b,a+c]'` says that no Hermann-Mauguin symbol generates this group in this cell — a parent glide's ½ along a doubled axis is a ¼ in the child, which is in no tabulated operation list — so the leading symbol names the closest *type* and generates a different group. The group is `phase.symmetry_operations`, and every orbit, multiplicity and systematic absence comes from it; the cell's metric constraints come from the closest type's point group and lattice, which are this group's own. Quote the operation list, or the type **with the cell transform beside it**. Two things such a group does not have: a Wyckoff letter (`site_constraints(...).wyckoff` is empty) and a `SPACE_GROUP_SETTING_ASSUMED` warning, both being properties of a tabulated setting. A published symbol for the same superstructure is naming a type in some other cell: check the transform before comparing |

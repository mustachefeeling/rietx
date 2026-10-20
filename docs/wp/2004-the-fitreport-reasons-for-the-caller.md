# WP-2004 — The FitReport reasons for the caller: its gates, actions and thresholds

Milestone: generality · Status: ⬜
Track: The audits
Depends on: 2002, 2003
Priority: P2 2026-10-18 — the report is what an agent reads first; waits on 2002 because its rival fits run the holds, and on 2003 because the one `THRESHOLDS_VERSION` bump carries its rulings

## Goal

Every gate, action kind, template and threshold in `src/rietx/report/` is in the audit
table with a tier. The four Layer-1 gates and the share-based maturity are either evidenced
on three families or demoted to numbers the report states. `THRESHOLDS_VERSION` is bumped
once, here, carrying 2003's width-growth rulings too.

## Context

The rule is `../milestones/generality.md` § The rule. This WP applies it to `report/`
(`layer0.py` 266 lines, `layer1.py` 517, `layer2.py` 1 250, `body_misfit.py`,
`background.py`, `identifiability.py`, `localisation.py`, `strain.py`, `texture.py`,
`magnetic.py`, `satellites.py`, `schemas.py`) and to `optimize/statistics.py`'s report-facing
constants.

**What the report decides.** Root CLAUDE.md's invariant "the FitReport must never return a
confident wrong singleton" is right and stays. Its four gates are the question: resolvability
on the scale-normalised Gram, a 0.4·FWHM validity radius, local-χ²_red significance, and
share-based global maturity. `report/schemas.py` carries 18 `ActionKind` members, 4
`GateCode`s, 3 `AbstentionKind`s, and `THRESHOLDS_VERSION = "1.12"` (~line 270) over a
block of constants, some of which (`WIDTH_GROWTH_*` in `sequential.py`) belong to 2003's
seam. ΔBIC's effective sample size N/f² (~lines 255–262) is rietx's own under a cited
statistic: tier the statistic 2 and the threshold on its own evidence.

**The suggestions are the report's ranking.** DESIGN.md's purpose has the report say what
was refined, how well, and what to look at next. Rule 1's second kind ranks alternatives
with their evidence and picks none. The report's suggestions are already a ranking
(`schemas.py`: "active suggestions, ranked as the report ranked them, capped"). So this WP
tiers the ranking's order and its caps, and the purpose settles whether the report
suggests at all.

**The report runs fits.** `layer2.py` (~lines 1098, 1216) and `body_misfit.py` (~line 184)
run rival fits through `fit(telemetry=False)`, which runs `_run_stage` and its holds. That
is why this waits on 2002: a gate measured against a rival fit that a hold has since
stopped altering is a different gate.

**Three screens with thresholds that are quoted, not tuned**, per root CLAUDE.md:
`background_absorption`'s R², `effective_observations`' two bands (Altomare 1995),
`background.diagnostics`' five-to-ten steps per FWHM (McCusker 1999). Tier 2 if the paper
sets the band; check the paper, since "quoted from the papers" is a claim the open could
not confirm for most constants (about 8 of 127 cite one in their comment block).

**What a demotion looks like here.** A Layer-1 statement that fails a gate today is
withheld. Demoted, the report states the number and the gate's reading ("validity radius
0.4·FWHM; this template sits at 0.7"), with what to look at next where the reading names
it (DESIGN.md § Rules, 3), and lets the caller decide. That is Rule 1's third kind, and it
is also what the v1.3 eval found agents use: seven of eight stopped on a stated criterion.
So a demotion that removes a *stated* criterion is contested by definition and goes through
`tests/eval_report_agent` before it lands (the record § A contested demotion; the spend
is approved per session). A poor result sends the explanation back for work and one more
round; the demotion lands either way.

**Fences with open WPs.** WP-1341 (a joint fit has no report) is in flight and owns the
report's *shape* for a joint fit; this WP touches no joint-fit code and no
`multi.py` reader. WP-1133 (a diagnostic names its view) adds a field to `Diagnostic`;
no conflict, but both touch `schemas/common.py`, so merge main before the schema commit.
WP-1339 (where the improvement lives) and 1335 (the report costs more than the fit) are
open under the same track; neither tiers a gate.

### Inherited

- **From WP-2002 (2026-10-20, PR #1050): `Statistics.esd_inflation` is not the factor the esds carry.** It re-measures the Bérar-Lelann f at the result's own compile, while the esds carry the f of the solve's last residual (now `LSQOutcome.esd_inflation`; on any row it is `RefinedParameter.stderr / stderr_uncorrected`). Measured 2026-10-20: 0.07 % apart on NAC Rietveld, 0.75 % on NAC Le Bail, 4 % on a joint fit weighted 1:4. Two readers treat it as the applied factor: the CIF exporter (`io/exporters.py:458-461`, "multiplied by") and `examples/srm660c_lab.py:96`. Making the statistic the solve's factor moves the profile-interval cut and `solve_magnetic`'s N/f² count slightly; the maintainer has not ruled.
- **From WP-2002 (2026-10-20, PR #1050): `report.layer2.predict_then_verify` runs on `_trial()`.** It used `branch()`; the change keeps a rival fit from paying the automatic moment-angle interval, and the trial leaves no history node.
- **From WP-2001 (2026-10-19, PR #1047).** The table is `src/rietx/_audit.py`; this WP's rows are the ones `_audit.WALKED` and `_audit.DEFAULT_SEATS` map to 2004, plus the codes and suggestion rows of its subsystem. Auditing a row means giving it a tier and evidence in place and deleting its line from `UNAUDITED_BASELINE`; `tests/test_audit_table.py` fails until both are done. The walk sees module-level numbers and tuples of numbers only, so a number held in a dict, list or array is audited here by hand: `report.texture._R_GRID` is one.

- **From WP-2002 (2026-10-19, PR #1050).** 2002's batch class B13 proposes handing 15 rows to this WP, pending the maintainer's ruling: seven `background.diagnostics` constants that feed `diagnose()`'s fields and no code (`COVERAGE_*`, `CUTOFF_*` except `CUTOFF_MIN_DEG`), the four `optimize.identifiability` report caps, `refine.MAGNETIC_TICK_PURITY` (its comment at `refine.py` ~768 disagrees with its code at ~7020), and `optimize.statistics.EFFECTIVE_OBS_ALPHA`, `OBS_PER_PARAMETER_MIN` and `OBS_PER_PARAMETER_PREFERRED`. The table: `2002-batch/batch.md` § The B13 hand-off table.

## Non-goals

- The holds the rival fits run: 2002.
- The width-growth thresholds' *rulings*: 2003 measures, this WP bumps the version.
- The joint-fit report: 1341.
- `Diagnostic` codes raised outside `report/` (`refine.py`'s 61): 2005.
- A new Layer-1 template or a new action kind.

## Tasks

- [ ] Inventory: one row per gate, action kind, abstention kind, template and constant
      under `THRESHOLDS_VERSION`, with what it withholds or asserts and what the caller
      sees without it.
- [ ] Tier each row per part; for the three quoted screens, open the paper and record
      whether it sets the band or the band is ours.
- [ ] Register and run the `eval_report_agent` round for the contested demotions
      (`tests/eval_report_agent/PROTOCOL.md` § Episode validity: expected answers checked
      against the data first), after the maintainer approves the spend. Where agents do
      worse, rework the number's explanation and run once more; the demotion is not held.
- [ ] The clash table: gates that read the same misfit, the background screen against the
      Layer-0 peak-cluster regions (WP-1055), abstention against maturity.
- [ ] The batch to the maintainer, each brief opening with its stakes line (the record
      § The rule, 2026-10-20); rulings dated into the table.
- [ ] Approved demotions; the `THRESHOLDS_VERSION` bump once, with 2003's rulings folded
      in; the eval fixtures that pin the version updated in the same commit.
- [ ] Goldens re-pinned only if no further from reference; the FAP report golden and the
      slow NAC golden regenerated once, on the final tree.
- [ ] Tests + PNGs; the fast count moved by exactly the tests added.
- [ ] Skill: none here. List each `references/judging.md` (5 546 words) and
      `diagnostics-reading.md` row that names a demoted gate, for 2008 (DESIGN.md § Rules,
      3; the record § Decisions, the skill's role).

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_audit_table.py -q          # no report/ row at unaudited
.venv/bin/python -m pytest tests/test_fitreport_layers.py tests/test_report*.py tests/test_localisation.py tests/test_body_misfit.py -q
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m pytest -n auto --dist loadgroup                # once, final tree
```

The handover carries the eval round's cells (registered first, reported split where
split) and the version bump's diff.

## References

- `docs/milestones/generality.md`; WP-1055, 1069, 1071, 1072, 1076, 1118 (the gates'
  history); 1303 (the v1.3 eval); 1985 (the explanations).
- Altomare, A. et al. (1995). J. Appl. Cryst. 28, 738–744; McCusker, L. B. et al. (1999).
  J. Appl. Cryst. 32, 36–50; Kass & Raftery (1995); Schwarz (1978).

## Handover log

- **2026-10-18** — created, from the milestone's opening session. 1341, 1339, 1335 and
  1133 are open under the report; none tiers a gate, and the fences above say what each
  owns.

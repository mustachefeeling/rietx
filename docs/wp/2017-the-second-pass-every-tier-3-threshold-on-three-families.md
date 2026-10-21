# WP-2017 — The second pass: every surviving tier-3 threshold measured on three families

Milestone: generality · Status: ⬜
Track: The audits
Depends on: 2002
Priority: P2 2026-10-20 — split from WP-2002 by the maintainer; the evidence every tier-3 approval in the single-fit audit was granted on the promise of

## Goal

Every tier-3 threshold the single-fit audit kept is measured on three unrelated dataset
families, against an independent reference where one exists. Each one either holds (its
evidence line gains the families and the reference distance), moves to tier 1 or
`invariant` (a test now bounds it), or goes back to the maintainer as a ruling with the
measurement that failed it.

## Context

**Where this came from.** WP-2002 audited what one fit decides by itself and ruled in two
passes, in the record's order (`docs/milestones/generality.md` § The order): first the
judgement ground for every action, then the mechanical ground, three families, only for
the thresholds of actions that survived. The first pass is done: all sixteen classes
ruled (`docs/wp/2002-batch/rulings.md`, four rounds). The maintainer split this second
pass out on 2026-10-20 so that 2002 could close on its owed tests and B14's lifts.

**What waits on it.** In `src/rietx/_audit.py`, 18 rows name the second pass in their
evidence or grounds and 26 say refits are owed "on either side" (2026-10-20 counts; grep
both phrases for the list). They group by the fits they share, so the work is perhaps
ten to fifteen fit campaigns, not one per row:

- **The solver path.** Twelve stop constants (Coelho's LM rules `_M_HI`, `_M_LO`,
  `_Q_TRIGGER`, `_Q_WINDOW`, `_LAMBDA_FAIL_*`, `lm._CONVERGED_RUNS`; BCCG's
  `_CONVERGED_*`, `_SMALL_*`; `_CAUCHY_ARMIJO`) and seven solver-path switches (B10's six
  and `DENSE_JACOBIAN_MAX_BYTES`), all approved at tier 3 until refits of three families
  on either side give one answer.
- **`auto_background`'s pick** (`HUMP_TRIGGER`, the two knot steps,
  `AIR_SCATTER_TRIGGER`). Measured on seven crystalline patterns (WP-2002's 2nd session
  of 2026-10-20). The generality judge rated the hump switch weak: its target case, a
  real amorphous hump under Bragg peaks (a glass capillary, an amorphous binder), is
  untested, and the air trigger was never checked against qarr's weighed compositions.
- **The absent-phase hold** (`PHASE_SUPPORT_SIGMA`). Mike Gaultois's second read of the
  batch (PR #1050, B1.1) named the case to gate the default on: an in-situ minor phase one
  peak width off its database cell, whose scale reads under 3σ and whose held cell keeps
  it there.
- **The cell window** (`CELL_WINDOW_*`, tier 3 since 2026-10-20): count the stages where it
  binds; if none, remove it from single fits (B8's ruling).
- **The position bounds' removal** (2026-10-20). One family, 11-BM NAC, where the bound
  acted as a prior that held. Owed: a flat-plate lab family with zero and displacement
  free over a narrow range.
- **Le Bail and Pawley refining the lines** (2026-10-20). One standard, SRM 660c; Le
  Bail's Kα2/Kα1 sat 1.7σ from Rietveld's. Owed: a second standard and a tabulated
  reference ratio.
- **`MODEL_FAR_FROM_DATA_RWP`** (B12.13). A sparse-count family: a true model's Rwp is
  0.77-0.83 at 0.5-1 counts a channel. Mike's proposal: Rwp against the background-only
  model's, or Rwp/Rexp, with no tuned number.
- **The magnetic solve's** `SOLVE_MINIMUM_RTOL`, `SOLVE_TOP_K`, `SOLVE_K_TRIALS` (B12,
  B12.8), and `SCALE_B_SEPARATION_FLOOR`, `_COS_CLAMP`, the two `*_CAP_RANGE_FRACTION`
  factors, `SCHERRER_K`, `BOND_SLACK_ANG` and `STEPS_PER_FWHM_*` (the judge's 2026-10-20
  reading).

**The held-out family stays held out.** The Nd₂Ru₂O₇ pair (`tests/data/mg090*`: 11-BM
X-ray and NCNR BT-1 neutron, one specimen, a published joint refinement) is evidence for no
audit; it is run once at the milestone's close (`generality.md` § Acceptance).

**Families on disk** (WP-2002 § Context): the four round-robin standards and the qarr
set (weighed compositions), 11-BM NAC and SRM 660c, the FAP suite, the Durham tutorials
under `~/rietx-local-data` (`python -m tests.local_data`), the magnetic fixtures (Cr₂WO₆,
LaMnO₃). A family is a specimen type with its own instrument, not a pattern.

### Inherited

- **From WP-2002 (2026-10-21, 5th session, PR #1085).** The sixth round landed: the four intermediate-tolerance rows at tier 3 (within 0.042 plain esd on four protocols behind the closing stage, 0.185 on cpd-1a with an absent zircon), `HARMONIC_WEIGHT_SEED` invariant, `CLOSING_WINDOW_TOL` tier 1 on three of four families. At the closing stage's windows `REFLECTION_MARGIN_DEG` errs 0.186σ and 0.124σ at the last points of FAP and cpd-1a (answers 0.026 and 0.043 esd). The sixth round's Q1 proposed the closing stage's rule (tight where the answer is computed) for the six other failing numerical settings (the FCJ node rule, the margin, the axial and magnetic sizing floors, `A5_CLIP`, the texture sampling); not built, and the maintainer has not ruled on it. Ruled and built on 2026-10-21, the seventh round (`2002-batch/rulings.md`, `waiting.md` § B10): the FCJ closing rule, `A5_CLIP` and the texture polish at tier 1, the magnetic floor invariant behind the closing stage on one family; the margin's edge rule at the closing windows was built and reverted (it freed a scale-B ridge on `tests/test_scale_b_ridge.py`'s synthetic narrow scan, `waiting.md` § B10), so the margin still errs 0.186σ and 0.124σ there; the axial floor still misses on cpd-1a (0.138 plain esd behind the closing stage), and the declared stages' FCJ, margin and window constants stay tier 3. This WP's second pass inherits the three-family evidence for each.
- **From WP-2002 (2026-10-21, PR #1085).** (1) The absent-phase hold flips with the intermediate tolerance: cpd-1a with zircon declared (a phase the sample lacks), LM, the QPA protocol. At `intermediate_ftol` 1e-6 the last stage holds nine zircon structural paths and `PHASE_UNCONSTRAINED` fires; at 1e-9 nothing is held, the zircon cell walks, and `lines_axial` hits its 400-evaluation budget. Zircon's scale sits near 2σ in plain esd, by `PHASE_SUPPORT_SIGMA`'s 3σ, so it is a case for that threshold's three families. (2) The CPD QPA protocol (`qpa_plan`) frees instrument and sample width terms that pair exactly (x with `lor_size`, y with `lor_strain`, zero with displacement), so the start picks the split; read those rows as one sum. (3) A staged plan's answer carries a path-dependent scatter of up to about 0.16 esd (0.5 in a background term) from the last stage's frozen compile, and one extra stage recompiled at the answer removes most of it. A refit on either side of a threshold should polish both arms from one common start, or it measures the scatter. Measurements in `docs/wp/2002-batch/waiting.md` § B7 and § B8 and B9.

## Non-goals

- New actions or new thresholds. A measurement that suggests one goes to the maintainer.
- The chain actions (WP-2003) and the report's verdicts (WP-2004), which run their own
  second passes.

## Tasks

- [ ] The list: every row whose evidence or grounds name the second pass or refits on
      either side, grouped by the fits they share, written to a table in this file.
- [ ] Per group, the three families and the reference each is measured against, chosen
      before running (a family chosen after seeing its answer is not evidence).
- [ ] Run each group; per row, the answer either side of the threshold and the reference
      distance, with obs/calc/diff PNGs to `tests/output/` for each refit used.
- [ ] Each row's evidence line updated; a row a test now bounds moves to tier 1 or
      `invariant` with the test named; a row that fails goes to a batch for the maintainer.
- [ ] The batch, in the register of `~/.claude/CLAUDE.md`, if any row failed.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_audit_table.py
.venv/bin/python -m tests.audit_delta
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m pytest -n auto --dist loadgroup      # once, on the final tree
```

No row this WP lists still names the second pass as owed.

## References

- WP-2002 and `docs/wp/2002-batch/` (`batch.md`, `rulings.md`, `waiting.md`).
- `docs/milestones/generality.md` § The order, § Acceptance.
- PR #1050's second read of the batch (Mike Gaultois, 2026-10-20).

## Handover log

- **2026-10-20** — Filed by WP-2002's session at the maintainer's request ("split"): the second pass moves here so that 2002 closes on its owed tests and B14's lifts. Nothing measured yet.

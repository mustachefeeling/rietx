# WP-2002 — The single-fit actions: what one stage decides for the caller

Milestone: generality · Status: 🔄 2026-10-20 — all 16 classes ruled; 110 more rows tiered and seven ruled changes built; 16 rows wait, five questions with the maintainer
Track: The audits
Depends on: 2001
Priority: P2 2026-10-19 — 2001 closed, so nothing blocks it; upstream of 2003 and 2004 (every fit runs these), and the seam the maintainer named first

## Goal

Every automatic action a single fit takes is in the audit table with a tier: the three
holds, the release and the collapse restore, the bound test, the phase-significance test,
the seeds, the always-on corrections, and the thresholds they rest on. Each tier-3 action
carries its two grounds and the maintainer's dated approval, and each tier-2 action its
judgement ground and approval. An action that fails is demoted by its kind of ambiguity
(DESIGN.md § Rules, 1): to a ranking with evidence where the data can rank the
alternatives, otherwise to the number in a record field with its meaning. The clash table
names every pair that interact.

## Context

The rule is `../milestones/generality.md` § The rule; 2001 restates it. This WP applies it
to `Refinement._run_stage` (`src/rietx/refine.py`, ~line 3795) and what it calls, and to
`src/rietx/strategy/` (`staged.py`, `magnetic.py`, `fraction_profile.py`,
`parameter_interval.py`, `suggest.py`), five files the first plan left unowned. The six
codes `strategy/magnetic.py` (five) and `strategy/fraction_profile.py` (one) raise are
this WP's too, since no code audit's seam reaches `strategy/`. Two of the five,
`LANDE_G_ASSUMED` and `MAGNETIC_ION_ASSUMED`, are also raised in
`crystallography/magcif.py`; this WP tiers them on both raise sites and 2006 reads the
row rather than writing one (fourth review).

**Why first.** `_run_stage` runs inside every fit the package makes, including the ones it
makes for itself: the report's rival fits (`report/layer2.py`, `report/body_misfit.py`),
the extinction screen (`indexing/extinction.py`), `strategy/magnetic.py`'s trials, and
every pattern of a chain. So 2003 and 2004 read a tree this WP has settled.

**The inventory, from the record fields** (the house rule makes every action leave one;
keyword counts over the source are mostly comments and were discarded at the open):

- `StageResult.held` / `held_reach`: the absent-phase hold (WP-1301, `_answer_significance`
  at ~line 1690: a scale under 3σ of its counting-noise esd), the moment hold (WP-1327),
  and the scale–B ridge hold (WP-1534, `SCALE_B_SEPARATION_FLOOR = 2·√PINV_RCOND` at
  ~line 542, which inherits `PINV_RCOND`'s tier). All three at ~lines 3938–3962.
- `StageResult.released` and the collapse restore: a phase that appeared is released; one
  that collapsed while solving is restored to where the stage found it and held, one extra
  solve (WP-1301).
- `StageResult.blocked_by_hold`: a user hold blocking a plan glob (WP-1435). Tier 1 by
  inspection (the user asked), but confirm.
- `StageResult.seeded`, `Stage.seed`, `Stage.strain_seed`: a row on a floor lifted before
  the solve; the Stephens isotropic seed (tier 1: at S ≡ 0 the √ has unbounded slope).
- `staged.bound_findings`, `at_bound`, `BOUND_HIT` / `FLOOR_HIT` (WP-1434, WP-1929): exact
  where the LM active set is exact; elsewhere "within a hundredth of an esd *and*
  `residual_cosine` not orthogonal", both measured into a window on one or two suites.
- `RefinementPlan.intermediate_ftol` (1e-6 vs 1e-9, WP-1123): a schedule, bounded for one
  fit at ≤ 0.03 esd; candidate for the answer-invariant class if the bound holds, tier 3
  otherwise.
- `background/auto.py`'s `auto_background` and `select.py`'s order scan: a verb whose job
  is the pick, returning its score table beside the choice. The record § A pick on top of
  a ranking allows that while no default path calls the verb; confirm it (no caller in
  `refine.py` or `strategy/` on 2026-10-18), then tier `AIR_SCATTER_TRIGGER`,
  `HUMP_TRIGGER` and the whiteness stop as the pick's thresholds.
- The flat-plate thickness test (`ABSORPTION_PLATE_THICKNESS`, an inline `< 0.7` at ~line
  6819) and the other inline literals near it: 2005 owns the codes, this WP owns any
  literal that gates an *action*.
- Always-on corrections with no switch, threshold or record field of their own, which no
  walk finds: the Bérar–Lelann esd inflation (`optimize/least_squares.py`, applied to
  every reported esd, 7 to 10 on WP-1417's synchrotron fits before v1.6 lowered it
  12–21 %; GSAS-II's source never mentions it), the √max(y,1) weight fallback, and
  anomalous dispersion on by default (`Source.dispersion`, also a declared seat). Walk
  root CLAUDE.md § Invariants for the rest. Each is an action row, tier 2 where a paper
  or a program stands behind it, and faces the judgement ground like any other (the
  record § The rule, tier 2, ruled 2026-10-19).
- Every constant in `refine.py` and `strategy/` from 2001's AST walk that a hold, release,
  seed or bound test reads; and the constants of `optimize/statistics.py` that are not
  report-facing (`PINV_RCOND`, `COLUMN_SAFE_EXPONENT`, `MAX_SHIFT_CONVERGED`) plus
  `optimize/lm.py`'s `BVLS_MAX_COLUMNS`, which the bound test rests on. 2001's walk
  enters all of these at `unaudited` (`optimize/` and `background/` are on `_audit.WALKED`);
  this WP owns every `background/` constant and every `optimize/` constant that is not
  report-facing, 2004 the report-facing ones (2001 § The seams, the partition by
  directory). Never add a row by hand for a name the walk already entered.
- `CORRELATION_GUARD` = 0.98 has three rows (the constant and the `PlanSpec` and
  `run_stage` defaults), tiered together. GSAS-II 5.8.4 lists pairs from
  max(0.95, 0.99 × the worst |ρ|) by default (`GSASIImath.setHcorr`, checked in
  `rietx-bench/tools/gsas2` by 2001's judge), so rietx is silent between 0.95 and 0.98;
  no source for 0.98 was found.
- `RefinementResult.sigma` holds two automatic choices, the √max(y,1) fallback and a
  floor at 10⁻³ × the median esd (`schemas/pattern.py`, inline). No field says which
  fired, so the field stays in `OTHER_RECORD_FIELDS` until a flag exists, and both are
  hand rows under the always-on corrections.
- The final stage's 1e-9 tolerance, which `StageSpec.ftol=None` resolves to, is a literal
  in signatures that are not seats (`optimize/least_squares.py`, `optimize/lm.py`), so
  the walk does not see it; it is a hand row beside `intermediate_ftol`.

**How the table works** (from 2001). The table is `src/rietx/_audit.py`; this WP's rows
are the ones `_audit.WALKED` and `_audit.DEFAULT_SEATS` map to 2002, plus the codes and
suggestion rows of `strategy/`. Auditing a row means giving it a tier and evidence in place
and deleting its line from `UNAUDITED_BASELINE`; `tests/test_audit_table.py` fails until
both are done. The walk sees module-level numbers and tuples of numbers only, so a number
held in a dict, list or array is audited here by hand.

**The two cases the second review named, to anchor the batch.** The absent-phase hold is
the one the rule keeps: a cell 14.9 Å from truth over 13 sub-onset patterns when free
(the v1.3 row), invisible in the outputs because Rwp does not move. The clash the review
found: WP-1320 chose the fraction profile's axis because the collapse rule fought it
(`strategy/fraction_profile.py` ~lines 13–22). A clash table is part of this WP's output.

**Evidence on disk.** Families for the mechanical ground: the four round-robin standards
(`tests/data/qarr`), the Durham tutorials (`~/rietx-local-data`, `python -m
tests.local_data`), the FAP suite, the private corpus files (cited by number, map in
`yue-here/rietx-corpus-map`). Tier-2 evidence: GSAS-II 5.8.4 source in
`~/Code/rietx-bench/tools/gsas2`, FullProf `fp2k` in `tools/fullprof`, the TOPAS
technical reference (memory `foreign-code-sources-on-disk`). "GSAS-II computes it" is not
"GSAS-II acts on it by default".

### Inherited

- **From WP-2001 (2026-10-19, PR #1047).** The table is `src/rietx/_audit.py`; this WP's rows are the ones `_audit.WALKED` and `_audit.DEFAULT_SEATS` map to 2002, plus the codes and suggestion rows of its subsystem. Auditing a row means giving it a tier and evidence in place and deleting its line from `UNAUDITED_BASELINE`; `tests/test_audit_table.py` fails until both are done. The walk sees module-level numbers and tuples of numbers only, so a number held in a dict, list or array is audited here by hand. From the generality judge's first run: (1) `CORRELATION_GUARD` = 0.98 has three rows (the constant and the `PlanSpec` and `run_stage` defaults), so tier them together; GSAS-II 5.8.4 lists pairs from max(0.95, 0.99 × the worst |ρ|) by default (`GSASIImath.setHcorr`, checked in `rietx-bench/tools/gsas2`), so rietx is silent between 0.95 and 0.98, and no source for 0.98 was found. (2) `RefinementResult.sigma` holds two automatic choices, the √max(y,1) fallback and a floor at 10⁻³ × the median esd (`schemas/pattern.py`, inline), and no field says which fired, so it stays in `OTHER_RECORD_FIELDS` until a flag exists. (3) The final stage's 1e-9 tolerance, which `StageSpec.ftol=None` resolves to, is a literal in signatures that are not seats (`optimize/least_squares.py`, `optimize/lm.py`). (4) `RefinementResult.geometry` truncates at 24 contacts per atom and skips phases over 200 atoms (`model/geometry.py`, noted in `GeometryTable.notes`); report-only, left out of the action rows.
- **From [2014](2014-a-heuristic-meets-the-judge-on-every-path.md)'s close (2026-10-20, PR #1070).** CI's lint job gains `tests/audit_delta.py`, which prints every row a PR adds, renames, changes or deletes and fails only a name new to the table at `unaudited`; a row returned to `unaudited` passes. Run on this WP's branch against its merge base (2026-10-20): 7 added, 1 renamed (`PHASE_SUPPORT_SIGMA`, `model.forward` to `schemas.plan`), 234 changed, 9 deleted, no failure, and `_audit.py` merges clean with 2014's. `project.py` joins the walk under 2002 with no number in it today. `/steward` now sends a fix to a row's tier, evidence or value back through the judge before the push.

## Non-goals

- `RefinementResult.geometry`'s truncation at 24 contacts per atom and its skip of phases
  over 200 atoms (`model/geometry.py`, noted in `GeometryTable.notes`): report-only, so
  no action row; its constants still take a tier.

- The chain: rungs, quarantine, the reseed fence, the moment-floor carry
  (`sequential._floor_unsupported_moments`), `_prefer`/`_better`. 2003.
- The FitReport's gates and the report's rival fits as *consumers* of the holds. 2004.
- `refine.py`'s 61 diagnostic codes as codes. 2005. A literal that gates an action is
  this WP's; one that gates a diagnostic is 2005's.
- Redesigning a hold. An action the batch rejects is demoted; a replacement is a
  follow-up WP filed from the table.

## Tasks

- [x] Inventory: one row per action and per constant it reads, from the record fields and
      2001's walk, with the file and line, what it decides, and what the caller sees
      without it. Lanes read disjoint files; the lead assembles. *2026-10-19:
      `2002-batch/inventory.json`, 402 proposals from six readers.*
- [ ] Tier each row per part (statistic, threshold, action), with evidence: the citation,
      the program and its default behaviour, or the families measured. Where the families
      are fewer than three, run the missing ones (the fits are cheap; a chain family is
      2003's). *157 rows needing no approval landed 2026-10-19; the rest wait on the batch.
      2026-10-20: the ruled rows landed; 16 still wait, each with what it waits on, in
      `2002-batch/waiting.md`. The second pass (three families per surviving threshold)
      has not run.*
- [ ] The clash table: every pair of actions that read or move the same parameter, with
      the measured interaction (Rwp and the parameter, both orderings). *38 candidate pairs
      found, none measured: `2002-batch/clashes.md`.*
- [x] The batch to the maintainer, in the register of `~/.claude/CLAUDE.md`: per tier-3
      row the two grounds answered, and per tier-2 action the judgement ground (for the
      judgement ground, the dissenting caller named or declared absent), the Rule 1 kind it falls to if demoted, the case against
      drafted by the `generality-review` agent, and a recommendation. Rows resting on one evidence base are grouped and ruled as a class
      (record § Decisions); rulings dated into the table. *Drafted and reviewed 2026-10-19:
      `2002-batch/batch.md`, 16 classes. Ruled 2026-10-19: B7, B10, B12, B14, and B1
      confirmed. The other nine re-briefed in `2002-batch/rulings.md`, awaiting answers.
      All sixteen ruled by 2026-10-20 (`rulings.md`, three rounds; B2 and B14 re-asked).*
- [ ] Approved demotions: the action removed, and its number left in the record field (or
      its ranking returned) with its meaning in the package's own output; the code's
      `level` to `info`, or, where the threshold was its trigger, the code replaced by an
      `info` record with no threshold (the record § Demotion). Each as its own commit.
      *2026-10-20, built: the cell reset (B8), the size floor and the chosen limits (B8,
      B9), the stationary angle's interval (B2), the hold's threshold as a plan setting
      (B1), `stderr_uncorrected` and its manual (B4), the pick verbs (B12). Left: B14's
      lifts, B3's and B9's two-start tests, B7's and B11's invariance and margin tests,
      the FCJ node cap (B10).*
- [ ] Goldens: every pinned number that moved, re-pinned only if no further from its
      reference; old, new, dataset and reference distance in the handover. A number that
      moved away goes back through the two grounds.
- [ ] `intermediate_ftol` and any other candidate for the answer-invariant class: the
      invariance test, or the row tiered.
- [ ] `tests/test_compare_ui.py` and `rietx compare`: a demoted action is a variant the
      comparison can show; add a row where a standard exercises it.
- [ ] Tests + obs/calc/diff PNGs to `tests/output/` for every refit used as evidence.
- [ ] Skill: none here. A demoted verdict's meaning goes into the package's own output and
      never into a skill row (DESIGN.md § Rules, 3; the record § Decisions, the skill's
      role). List each skill row that named a demoted verdict, for 2008.

## The batch (2026-10-19)

The rulings received so far, the maintainer's words, and the second-round briefs for the
items still open are in [`2002-batch/rulings.md`](2002-batch/rulings.md). Read it before
`batch.md`: three of its picks replace the batch's (B4, B5, B9).

The rulings this WP waits on are in [`2002-batch/batch.md`](2002-batch/batch.md): 16
classes covering the 247 rows still at `unaudited`, each with the author's brief, the
case against from a fresh-context judge, and the lead's pick revised after that review.
`2002-batch/inventory.json` holds every reader's per-row proposal (file and line, what it
decides, tier, evidence line, provenance, the batch class), so landing a ruled row means
copying its evidence line into `src/rietx/_audit.py` with `grounds` and the ruling's date
in `approved`. `fcj_low_angle.py` and `i740.json` are the two pieces of evidence the
batch cites that were made this session.

Three choices the opening session made, each reversible:

- **Two passes, in the record's order** (§ The order). The batch asks the judgement
  ground of every action and acting default. The mechanical ground (three families) is
  measured afterwards, and only for the thresholds of actions that survive. Chosen over
  measuring every threshold first, which would spend fits on actions the ruling demotes.
- **The held-out family is the Nd₂Ru₂O₇ pair** (`tests/data/mg090*`: 11-BM X-ray and
  NCNR BT-1 neutron, one specimen, a published joint refinement as the reference). No
  audit uses it as evidence; at close the standards' protocol is run on it. Chosen
  because its reference validates and its neutron half tests whether X-ray-tuned
  thresholds carry over. The alternative, the Durham tutorials, is WP-2003's chain
  family.
- **Diagnostic-only constants are handed to the audit of their code** (batch class B13):
  34 to WP-2005, 15 to WP-2004, 9 to WP-2007, from this WP's own non-goal. Until ruled,
  they stay `unaudited` here, and this file's acceptance line below reads "no
  action-gating row at unaudited".

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_audit_table.py -q          # no action-gating refine.py/strategy row at unaudited
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m pytest -n auto --dist loadgroup                # once, on the final tree: goldens
.venv/bin/python -m ruff check src tests examples
```

The handover carries the clash table and the batch's rulings; the record's acceptance
row "no tier-3 action runs by default without its approval" is checked against the table
for every row this WP owns.

## References

- `docs/milestones/generality.md`; WP-1301, 1327, 1534 (the holds); 1434, 1929 (the bound
  test); 1123 (`intermediate_ftol`); 1320 (the clash); 1523 (`_answer_significance`).
- McCusker, L. B. et al. (1999). J. Appl. Cryst. 32, 36–50 (the guidelines several
  thresholds quote).

## Handover log

### 2026-10-20 — all sixteen classes ruled, and seven of the rulings built

The maintainer has ruled on every class, and most rulings now run in the code. A fit puts a
runaway cell back where its stage found it, where it used to stop it at an invented 15 %
edge. Crystallite size, occupancy, texture and the line and harmonic weights refine
wherever they stay physical, and an occupancy above one warns. A moment angle that sits on
a symmetric direction carries a likelihood interval, where it used to carry no uncertainty
and read as exact. The caller can set or switch off the absent-phase hold. Every refined
row reports, beside rietx's esd, the smaller number GSAS-II and FullProf print, and the
manual explains the difference. The pick verbs show their evidence and abstain on a tie.
One measurement narrowed a ruling: freeing the peak-position bounds let the 11-BM NAC cell
drift 5129 ppm against 1117 ppm, so those bounds stay until the maintainer rules again.

*Done.* Rulings, in `2002-batch/rulings.md` (three rounds, all dated): B1 on by default as a
plan setting; B2 the turn kept and, re-asked after this session found its first brief
misstated the cost, the stationary-angle test kept with the angle given its interval
(option 2); B3, B11, B16 as recommended; B4 keep f and report the uncorrected esd; B5 fix
the obviously wrong, warn at ingestion, an option to correct (forwarded to WP-1952); B6,
B13, B15 yes; B7 with two additions and B9's unstated geometry (filed as WP-2015); B8 the
window tier 2 on TOPAS, the clamp a reset-and-hold, the 2 nm floor removed; B9 no chosen
limit on a physical quantity; B14 option 3, re-explained and confirmed. Built, one commit
each: the audit rows the rulings settle (62 by the lane and by hand, then each change's
own); the cell reset (`StageResult.cell_reset`); the limits (`OCCUPANCY_ABOVE_ONE` new;
`MARCH_R_MIN` 0.15 → 1e-6; the harmonic, emission-line, axial and occupancy ceilings and
the 2 nm floor gone; readers and the GUI no longer write the old ceilings); the angle's
interval (`RefinedParameter.interval`, a new `IntervalStop` "period" that stops a side
half a turn out); `phase_support_sigma` (project format 1.5, `.rxt` `support`);
`stderr_uncorrected` with the theory and three switching pages; the pick verbs
(`BackgroundChoice`, N/f², no R tie-break, `QPA_FRACTION_RANGE`). `2002-batch/waiting.md`
lists the 16 rows still at `unaudited`, each with what it waits on. No Inherited section
to prune. Forward references to 2003, 2004, 2005, 2008 and 1327 (`SOLVE_D_MIN` folded
there, no new WP); 1952's B5 entry rewritten to the ruling.

*Code review* (`high --fix`, this session's range): nine findings, six fixed in
`20674c4c` (a stale Jacobian after a late cell reset; the magnetic solve's plans dropping
`phase_support_sigma`; the N/f² caveat claiming f = 1.00 on raw N; an interval
precondition error escaping a finished fit; the quickstart tutorial). Three declined as
design choices, now Next items 1-2 and in 2003: internal trials run at the default 3σ, the
threshold is not recorded for a cherry-pick, and a series' discarded rungs pay the
interval.

*Measured.* Fast selection on this branch merged with `origin/main` (`7646e7a6`), `[dev]`,
darwin/arm64, no other suite running: 10 868 passed, 191 skipped, 2 xfailed, 1 failed, the
failure the stale WP index this handover then regenerated (`test_docs_consistency.py` 25
passed after). The branch adds 52 test cases (51 in the fast selection; one is `slow`),
33.2 s together locally, the largest 11.0 s in `test_stationary_moment_angle.py`; none
joins the tail. Full suite on the same merged tree, `[dev]`, darwin/arm64, alone: 11 181 passed, 202 skipped, 2 xfailed, 1 failed in 24:49. The failure was `test_lebail_alternation.py`'s wander test, which pinned "Pass 3 of 4 was kept": its cell stage runs away, and since the B8 reset the wander keeps pass 2 of 3. The test now asserts its invariant (the next fit continues from the kept pass) and passes alone in 64 s. Every bit-identity golden passed. The automatic interval costs 20-32 refits an angle,
2.6-16.7 s on test fits of 0.2-1.2 s; a moment the data no longer saw walked to ±1e12 rad
over 120 refits before the half-turn stop (15.9 s, now 1.7 s). `Statistics.esd_inflation`
differs from the factor the esds carry by 0.07 % (NAC Rietveld), 0.75 % (NAC Le Bail) and
4 % (a joint fit weighted 1:4). N/f² moved `solve_magnetic`'s winning margins 1682 → 143
(Cr₂WO₆ 4 K) and 1704 → 164 (LaMnO₃ 50 K) and no verdict. Lanes: seven, every one
laned under 6c (context 270-465K), the whole table from `session_usage.py lanes`:

| lane | est | requests | main at dispatch | lane $ | in-session $ | saved $ |
|---|---|---|---|---|---|---|
| land-ruled-audit-rows | 40 | 50 | 270K | 3.98 | 12.65 | +6.36 |
| cell-clamp-restore-and-hold | 35 | 144 | 335K | 10.73 | 26.27 | +15.13 |
| chosen-limits-size-floor-and-b9 | 40 | 213 | 356K | 18.11 | 39.50 | +21.09 |
| stationary-angle-interval | 35 | 160 | 404K | 11.24 | 22.48 | +6.36 |
| phase-support-sigma-seat | 25 | 182 | 439K | 14.17 | 27.71 | +8.68 |
| b4-textbook-esd-and-manual | 30 | 169 | 450K | 10.31 | 24.16 | +8.65 |
| b12-pick-verbs | 35 | 181 | 465K | 16.77 | 30.10 | +9.50 |

Trial row appended to `process.md`; estimates ran short by 5.17×. The baseline replay's
selective policy (lane when main > 150K and item ≥ 20 requests): -16 % over 217 sessions.

*Generality* (the `generality-review` judge, fresh context, on the 242 rows both sessions
added or retiered and six heuristics the table cannot see; tables condensed to the rows it
did not find holding, its full text in this session's transcript):

| Item | Case against | Verdict | Author's answer |
|---|---|---|---|
| Tier-2 stop rules (Coelho's `_M_HI`, `_M_LO`, `_Q_*`, `_LAMBDA_FAIL_*`, `lm._CONVERGED_RUNS`, the five `bccg` stops; `_CAUCHY_ARMIJO`, `SCHERRER_K`, `BOND_SLACK_ANG`, `STEPS_PER_FWHM_*`) | a paper defining an algorithm does not validate its constants on rietx's problems; they decide where a stage stops, the class B10 held at tier 3 | weak | agreed: re-tier to tier 3 with either-side refits owed, as B10's switches, next session |
| `PARAMETER_INTERVAL_*` at `caller` | `fit` and `run_stage` now call the interval (B2 option 2) | fails | agreed: this session made it a default path; re-tier under the B2 ruling next session |
| `FRACTION_PROFILE_FWHM_MIN`, `_N_FWHM` at `caller` | the skill sends every agent to `profile_fraction`, and B12 ruled a skill instruction a default path | fails | agreed; re-tier next session |
| `SCALE_B_SEPARATION_FLOOR`, `_COS_CLAMP`, the two `*_CAP_RANGE_FRACTION` at tier 1 | each carries a chosen factor; with the 2 nm floor gone the range backstop is the only size bound | weak | the 2 and the 1.0 go to the second pass as thresholds |
| `A6_MAX_ITER` invariant | its test asserts eq 21 is met, not the margin to 2000 | weak | a margin assertion is owed |
| B2 `MOMENT_ANGLE_STATIONARY` evidence | one angle's cut is the one-sided 2.706, so a single passing angle's interval always contains the direction; the suggestion's "excludes" branch is reachable only for sets | rows hold, text weak | fix the evidence line and the suggestion's wording next session |
| B3 Stephens seed | the ruling asks the seed recorded in the result; `seeded` records only the roughness seed | weak | B14's field for the strain seed is the fix |
| B8 cell window | the ten iterations per stage is a threshold of its own, untiered | weak | the ten goes to the second pass |
| B9 `EXTRA_PEAK_FWHM_MAX` tier 1 | the 0.5° is a choice; a broad impurity peak modelled as an extra peak dissents | weak | kept: a finite max sizes the frozen window; widening is the design change named in waiting.md |
| B9 `Source:polarization` kind 3 | it acts (fits at 0.5) and nothing records the assumption yet | weak | WP-2015 records it |
| B10 `DENSE_JACOBIAN_MAX_BYTES` | landed on the solver-switch grounds, but the ruling names six switches and not this one | fails | agreed: back to `unaudited` for the maintainer next session |
| B12 `auto_background` constants, `:kind`, `:seed` | the pick rests on visibility, which the rule rejects; `:kind` was never shown to the maintainer; rietx's unseeded start is 0.0, not GSAS-II's (1, 0, 0) | fails | a question for the maintainer below; the rows go back to `unaudited` until answered |
| B12 `SOLVE_MINIMUM_RTOL`, `SOLVE_TOP_K` | the rare-feature clause keeps a measured value; these have no source and no measurement | weak | second pass |
| B12 `MODEL_FAR_FROM_DATA_RWP` | at 1-2 counts a channel a correct model's Rwp is about 0.7-0.8 | weak | second pass, with a sparse family |
| (b) peak-position bounds kept | one family; a recessed lab holder or a weak absorber dissents | your ruling | question below |
| (c) `_auto_intervals` on in a series | every pattern, and discarded rungs, pay | weak | forwarded to 2003 |
| (d) `OCCUPANCY_ABOVE_ONE` with no gate | 1.032(25) is a full site; a warning on noise is a verdict the data do not support | weak | question below |
| (e) `stderr_uncorrected` | right, but the result does not record the applied factor and the interval cut reads the other one | holds, record weak | forwarded to 2004 |
| (f) parsimony tie-break | "a ΔBIC tie abstains"; BIC already charges parameters | fails against the ruling | question below |

Held without comment: tier 1 bar the four rows above, the defaults with GSAS-II lines,
the other `caller` rows, the invariant rows bar `A6_MAX_ITER`; B1, B4, B6, B7, B8's cell
reset, B9's `MARCH_R_MIN`, B11, B16, the ΔBIC rows, the Pawley pair, `QPA_FRACTION_RANGE`,
and the half-turn stop.

*Questions for the maintainer* (five need a judgement; the briefs are in this session's
report and short):
1. The peak-position bounds (zero shift ±0.5°, displacement and both capillary offsets
   ±1 mm, transparency ≤ 0.05): keep them as guards on a degenerate walk, or widen them
   under B9?
2. `OCCUPANCY_ABOVE_ONE`: gate it on significance (above 1 by some number of esds), make
   it an info record, or keep it as a warning on any value above 1?
3. `TCHZ_BOUNDS`: WP-1312 ruled "the bound stays" on 2026-09-11; B9 says chosen U/V floors
   and ceilings go. Which holds?
4. The parsimony tie-break in `solve_magnetic`: drop it too, so every ΔBIC tie abstains?
5. `auto_background`'s pick: kept as a tier-3 pick, or does it abstain without a clear
   winner, now that the skill makes it a default path?
Confirmations: the emission-line weight widened (TOPAS's `la` limit is per iteration);
`QPA_FRACTION_UNDETERMINED` renamed `QPA_FRACTION_RANGE`; the automatic interval's cost.

*Gotchas.* A lane applied B9's principle to every box, including the peak-position bounds;
the lead put those back after measuring the NAC drift, so read a ruling's reach against
the measured consequence before landing a widening. `Statistics.esd_inflation` is not the
factor the esds carry; use `stderr / stderr_uncorrected` on a row. The worktree is still
named `wp2001-rule-table-guard`.

*Next.* (1) Make `phase_support_sigma` reach the package's internal trials (interval walk,
fraction profile, rival fits) and record it on `StageResult`/`NodeAction`, so a
cherry-pick replays what ran; `correlation_guard` has the same gap. (2) The judge's
re-tiers: the `PARAMETER_INTERVAL_*` and fraction-profile rows, `DENSE_JACOBIAN_MAX_BYTES`
and the `auto_background` rows back to `unaudited`, the Coelho stop rules to tier 3, the
stationary evidence line. (3) B14's lifts (about 20 constants, 8 seats, the fields for the
collapse restore, the Stephens seed and the σ rule) and the ~50-guard list to the judge.
(4) The owed tests: B3's and B9's two-start tests, B7's invariance, B11's margin, B10's
domain tests and the FCJ node cap. (5) The second pass, the clash table, goldens and
`test_compare_ui` rows. The maintainer's answers to the five questions decide (2)'s
`auto_background` rows and three of the code changes.

### 2026-10-19 (2nd session) — four classes ruled, the rest re-briefed in plain words

The maintainer ruled four of the sixteen classes and confirmed the absent-phase hold. The
declared geometry now picks the default plan. A numerical setting is tier 1 when a test
bounds its error over its domain. The three pick verbs are fixed as proposed, and the inline
numbers that could change an answer become named constants. The other nine items came back
as questions, so this session rewrote them in plain words and asked again
(`2002-batch/rulings.md`). Asked what is scientifically accurate, it reversed the batch on
the esd factor. The textbook esd is too small on correlated residuals and shrinks with step
size, so the pick is now to keep the Bérar-Lelann inflation and report the textbook esd
beside it. Nothing in the code or the audit table has moved.

*Done.* `2002-batch/rulings.md`: the rulings with the maintainer's words, the nine
second-round briefs, and the six open questions. Three picks changed from `batch.md`'s
revised picks. B4 keeps f (option 1, the textbook esd reported beside it). B5 drops and
reports a non-positive esd (option 3, built in WP-1952). B9 adds a "geometry not stated"
state, joining the B7 follow-up. No Inherited section to prune. No forward reference: the
B7 follow-up has no owner (grep over `docs/wp/` for `Geometry.kind` and
`lab_bragg_brentano` found closed WPs and WP-1421, which is unrelated), and it is filed
once B9's geometry question is ruled, so that both land in one WP.

*Checked this session.* Bérar & Lelann (1991) and McCusker et al. (1999) are not in the
Zotero library (title search over a copy of the sqlite, and file names under storage).
`berar_lelann_factor`'s docstring gives f ≈ 1.127 on white residuals
(E[S'']/E[S] = 1.2694). `Geometry.kind` defaults to `debye_scherrer` and has no unstated
value. `mccusker_default` frees zero but no displacement, and `lab_bragg_brentano` frees
displacement, the Kα2 weight and the axial terms (`strategy/staged.py` ~351-425).

*Not done.* The handover's code review was skipped, since this session's one commit is
prose. No test ran beyond the handover's own checks. The generality judge is owed on the
148 rows the first session landed in `_audit.py`. `batch.md` carries the judge's case
against each unruled class, but the first entry has no *Generality* table for the landed
rows. This session added no row, so it did not dispatch one at this context.

*Gotchas.* The branch is checked out in the `wp2001-rule-table-guard` worktree, and its
session (pid 52389) was still open. This session committed from a detached HEAD in the
`happy-watching-squirrel` tree and pushed to the branch. That other tree's local branch is
one commit behind origin, so run `git pull --ff-only` there before working. B14's yes was
given on a misreading ("the demotion tests"). The substance is unchanged, but confirm in a
line.

*Next.* (1) The maintainer answers the six questions in `rulings.md` § Still open. (2) Land
every ruled row in `_audit.py` with `grounds` and `approved` 2026-10-19: B1, B7's plan rows,
B10 (plus its sentence in `generality.md` § The rule), B12 and B14's lifts. (3) File the
follow-up WP for the geometry-chosen plan once B9 is ruled. (4) Run the generality judge on
the 148 landed rows. (5) Then the first entry's Next items 3-6: the 17 unread citations,
the second pass, the clash table, and the demotions with their goldens.

- **2026-10-19** — the inventory, 148 rows tiered, and the decision batch (PR #1050).

  Every automatic decision a single rietx fit makes now has a proposed tier with its
  evidence. The 148 that need no approval are in the audit table. The other 256 are grouped
  into 16 classes in a decision batch that waits on the maintainer (`2002-batch/batch.md`).
  Nothing has been demoted yet, so no fitted number has moved. Two findings stand whatever
  the rulings. The axial-divergence quadrature's node cap leaves an error of 2.8 % of peak
  height at 3° 2θ on lab Bragg-Brentano data. And the default Bérar-Lelann inflation makes
  every rietx esd 1.13 to 8 times what GSAS-II would report on the same fit.

  *Done.* Inherited pruned: 2001's four notes folded into Context and Non-goals, none
  stale. Six read-only readers (refine.py; strategy/ and schemas/plan.py; optimize/;
  model/; background/; params/ and the schemas) proposed a tier for each of the 299 walked
  rows plus the strategy codes, 402 proposals in all (`2002-batch/inventory.json`). 157 rows
  needing no approval landed (tier 1, tier-2 thresholds, `caller`, and the
  observation-channel defaults as `invariant`). The handover's code review sent nine back
  to `unaudited` and fixed four (batch § Added after the handover's code review), so 148
  stand. `tests/test_answer_invariant_defaults.py` (8 cases) asserts that the event stream,
  progress stream, cancel token, label, run recorder, per-stage reports and history tree
  leave a fit's answer bit-identical, and that the recorder actually ran. One Opus agent
  drafted the batch and checked the readers' claims; a fresh-context judge wrote the case
  against each class; the lead corrected the six sentences the judge found wrong and wrote
  a revised pick per class. Held-out family named (§ The batch). Forward references went
  to 2003, 2004, 2005, 2006, 2007, 1952, 1542 and 1467.

  *Measured.* FCJ node cap (`model/profiles/fcj.py` `MAX_NODES` = 64) against a 512-node
  reference, S/L = H/L = 0.025, FWHM 0.07°: 0.19 % of peak height at 5°, 0.71 % at 4°,
  2.8 % at 3°, under 0.06 % uncapped (`2002-batch/fcj_low_angle.py`). Issue #740's Le Bail
  cycles: Rwp 4.56 % at 3, a plateau of 1.62 % from 100 to 400, 1.09 % for the true
  structure (`2002-batch/i740.json`). Proposed demotions on the judgement question: about
  15 rows, from 18 in the draft (the milestone asks each audit for this count; it is final
  only after the rulings). None measured yet on the mechanical question. Subagent spend:
  six readers 2.22 M tokens, drafter 0.50 M, judge 0.35 M, code review 0.19 M. No lane in
  the `/wp-start` 6c sense ran, so there is no lane table. Fast suite on the final tree, `[dev]` venv, darwin/arm64, nothing else running: 10 834 passed, 191 skipped, 2 xfailed, 4:41 wall; the 8 added cases cost 3.06 s together (one local run). The full suite was not run: the branch changes no library code, only the table's data, one test file and docs.

  *Questions for the maintainer.* Full briefs in `2002-batch/batch.md` § Bn, each with the
  case against and a revised pick. Eight need a judgement:
  1. B4: stop multiplying every esd by the Bérar-Lelann factor, and report the factor
     beside it? (pick: yes)
  2. B5: demote the floor that raises a zero esd to 10⁻³ of the median, and leave its
     replacement to WP-1952? (pick: yes)
  3. B7: the default plan `mccusker_default` frees no specimen displacement on
     Bragg-Brentano data, where rietx's own `lab_bragg_brentano` does. Keep it at tier 3
     and compare the two presets on three families, or choose the preset from the
     geometry in a follow-up? (pick: compare first)
  4. B8: remove the per-stage cell window if a count shows it never binds; make the cell
     clamp restore-and-hold; keep the 2 nm size floor at tier 3? (pick: yes to all three)
  5. B9: judge each default box on unanimity, widening chosen caps with a named dissenter
     (occupancy ≤ 1.5, March r ≥ 0.15) unless a source is found, and record
     `Geometry.kind`, polarisation and the Kα2 ratio as assumptions? (pick: yes)
  6. B10: read the rule for numerical settings as "tier 1 when a test bounds the error
     over the claimed domain", with solver switches kept only by either-side refits?
     Adds one sentence to `generality.md` § The rule. (pick: yes)
  7. B12: `auto_background` returns its evidence beside its pick; `solve_magnetic` uses
     N/f² and drops its R tie-break; `profile_fraction`'s warning becomes an info record;
     and is the skill's instruction a default path? (pick: yes; yes, it is)
  8. B14: lift the rows a retune could change into named constants, seats and record
     fields, and list the tier-1 floors in this file? (pick: yes)

  Five ask a confirmation (B1 absent-phase hold, B2 moment turn, with the angle test
  measured first, B3 seeds by test, B11 Le Bail cycles converge-with-cap in WP-1542, B16
  bound test). Three are plain (B6 dispersion kept, B13 hand-off of 58 diagnostic-only rows
  to 2004, 2005 and 2007, B15 the assumed ion split by element).

  *Gotchas.* A hand row cannot enter `_audit.ROWS`, because the table's test holds every row
  equal to something the walk sees; that is B14. The `generality-review` agent did not load
  as an agent type in this session, so it ran as a general-purpose agent told to follow
  `.claude/agents/generality-review.md`. The scratchpad does not survive a session, so
  everything the next session needs is in `2002-batch/`. This worktree is named
  `wp2001-rule-table-guard` and carries `wp2002-single-fit-actions`; the claim is recorded
  with `wp_claim.py`. 17 tier-2 rows rest on unread citations (batch, same section): check
  them against the corpus before building on them.

  *Next.* (1) The maintainer rules on the batch. (2) Land the ruled rows: each row's
  evidence line is in `inventory.json`; add `grounds` and the ruling's date in `approved`.
  (3) Check the 17 tier-2 citations. (4) The second pass: three families for the
  thresholds of surviving actions, with the held-out family excluded. (5) Measure the
  clash table (`2002-batch/clashes.md`; C1 is WP-1320's, C3 the window, hold and clamp
  triple). (6) Demotions, one commit each, then goldens; the owed invariance tests
  (`intermediate_ftol`, the budgets, the starts) and the FCJ cap fix sit with B10.
- **2026-10-18** — created, from the milestone's opening session (WP-2001's log has the
  measurements and the two reviews). No open WP owns the holds as a class: 1301 and 1534
  each shipped one and are closed. 1327, which shipped the moment hold, is still in flight
  (its analytic moment branch remains), so merge main before touching that hold and read
  1327's handover for what its branch moves.

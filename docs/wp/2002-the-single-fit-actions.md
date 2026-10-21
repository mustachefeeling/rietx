# WP-2002 — The single-fit actions: what one stage decides for the caller

Milestone: generality · Status: 🔄 2026-10-21 — fifth round built (Q4-Q6, tier 2 widened, two search defects fixed); Q1-Q3 re-briefed with seven programs' practice and wait (rulings.md § Sixth round); B14's lifts and two domain tests remain
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
held in a dict, list or array is audited here by hand. `project.py` joined the walk under
2002 with WP-2014 (2026-10-20), with no number in it today.

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
      has not run. 2026-10-20 (2nd session): the fourth round's rows landed (the
      auto_background pick kept, the cell window, the interval and width-grid settings,
      twelve solver stop constants and the seventh solver switch, all tier 3). The second
      pass moved to [2017](2017-the-second-pass-every-tier-3-threshold-on-three-families.md)
      on 2026-10-20 (the maintainer's split); this item closes with the owed tests and
      B14's lifts. 3rd session (2026-10-21): the owed tests ran (`2002-batch/waiting.md`).
      Landed: B11's three budgets (on the shipped schedule) and two internal splits
      invariant, `MAX_NODES` tier 3. The window slack and the three geometry caps stay
      tier 3 after the judge's review, and every setting that failed its domain test
      stays tier 3 for the fifth round. Still owed: the
      interval and width-grid domain tests. 4th session: the three geometry caps and the
      restraint image shell to tier 1, under the rule's new cap and numerical-setting
      clauses; the fourteen tier-2 rows resting on a program default checked against
      seven programs (`2002-batch/practice.md`).*
- [x] The clash table: every pair of actions that read or move the same parameter, with
      the measured interaction (Rwp and the parameter, both orderings). *38 candidate pairs
      found, none measured: `2002-batch/clashes.md`. Moved to
      [2018](2018-the-clash-table-measured.md) on 2026-10-20 (the maintainer's split).*
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
      the FCJ node cap (B10). 2nd session: the peak-position bounds removed,
      `OCCUPANCY_ABOVE_ONE` an info record, every ΔBIC tie an abstention. 3rd session:
      the two-start, invariance, margin and domain tests ran; what passed landed, and what
      failed waits on the fifth round (`2002-batch/rulings.md`). Left: B14's lifts, the
      fifth round's builds, the restraint image-shell fix. 4th session: Q5's width
      ceilings removed, Q4's switched-off roughness said in its warning, Q6's cap clause,
      both search defects fixed. Left: Q1-Q3's builds (the sixth round) and B14's lifts.*
- [ ] Goldens: every pinned number that moved, re-pinned only if no further from its
      reference; old, new, dataset and reference distance in the handover. A number that
      moved away goes back through the two grounds. *2026-10-20 (2nd session): one moved
      away, the NAC capillary pair's cell (`test_capillary_displacement.py`, offsets
      free), 1097 → 5109 ppm from the acceptance band's centre 10.2510 Å, esd 2612 → 2579
      ppm; back through the grounds by the judge: the bound had one family and a named
      dissenter, so the removal stands. No bit-identity golden moved. 3rd session: no
      source behaviour changed (one comment), so nothing moved. 4th session: the ceiling
      removal and the two search fixes moved no bit-identity golden (darwin/arm64).*
- [ ] `intermediate_ftol` and any other candidate for the answer-invariant class: the
      invariance test, or the row tiered. *3rd session: the test ran and failed in plain
      esds (0.033-0.074 on cpd-1a) and a hold flips with the tolerance; the rows wait on
      the fifth round. B11's budgets passed and landed invariant. 4th session: re-briefed
      as the sixth round's Q2, with a closing stage measured (`rulings.md` § Sixth round).*
- [ ] `tests/test_compare_ui.py` and `rietx compare`: a demoted action is a variant the
      comparison can show; add a row where a standard exercises it.
- [ ] Tests + obs/calc/diff PNGs to `tests/output/` for every refit used as evidence.
      *3rd session: done for every refit it ran (`tests/output/b3_*`, `b9_*`, `b10*`,
      `b7b11_*`, `seed_invariance_*`, `window_domain_*`, `fd_step_*`). 4th session: the
      0.5 % window polishes wrote `window_domain_*` PNGs; the last-stage, closing-stage and
      Biso-start measurements are scratch scripts with no figure, their numbers in
      `rulings.md` § Sixth round.*
- [ ] Skill: none here. A demoted verdict's meaning goes into the package's own output and
      never into a skill row (DESIGN.md § Rules, 3; the record § Decisions, the skill's
      role). List each skill row that named a demoted verdict, for 2008. *2nd session:
      `references/magnetic.md`'s abstained row and `api-magnetic.md`'s criterion (from
      `make_api_index.py`) rewritten for the tie ruling; `OCCUPANCY_ABOVE_ONE`'s row
      unchanged in words, now at info.*

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

The handover carries the batch's rulings; the record's acceptance row "no tier-3 action
runs by default without its approval" is checked against the table for every row this WP
owns. The three-family evidence behind those approvals is
[2017](2017-the-second-pass-every-tier-3-threshold-on-three-families.md)'s, and the
clash table [2018](2018-the-clash-table-measured.md)'s, both split out 2026-10-20.

## References

- `docs/milestones/generality.md`; WP-1301, 1327, 1534 (the holds); 1434, 1929 (the bound
  test); 1123 (`intermediate_ftol`); 1320 (the clash); 1523 (`_answer_significance`).
- McCusker, L. B. et al. (1999). J. Appl. Cryst. 32, 36–50 (the guidelines several
  thresholds quote).

## Handover log

### 2026-10-21 — the owed tests: the budgets and two starts pass, most numerical settings fail a bar tied to the data's noise

This session ran the tests the batch owed. It asked whether a starting value changes the answer, whether stopping early stages early does, whether the iteration budgets leave room, and whether each numerical setting stays accurate over the range it claims. The iteration budgets, the Suortti roughness start, the peak-width start and two internal splits pass, and are now recorded as not affecting the answer. Most numerical settings fail a bar set at a tenth of the data's own noise. The largest is the peak window, which drops 2 % of each peak's area and moves refined values by up to one esd on lab data; fixing it costs 1.2 to 3.5 times the fit time. The session also found that a staged plan's answer depends on its path by up to about 0.16 esd, because its last stage runs on a model frozen where the earlier stages stopped, and that the absent-phase hold can flip with the intermediate tolerance. No package behaviour changed. Six questions wait on the maintainer (`2002-batch/rulings.md` § Fifth round).

*Done.* Inherited pruned on arrival: 2001's entry was already in Context, and 2014's `project.py` note was folded in. WP-2003's missing entry was reconstructed by hand from 5c8810091, a docs commit already merged through #1050, so the full repair handover had nothing to review. Then one commit per class: B3's two-start tests (093612546); B9's starting values (030aa05ea); B10's FCJ domain test (020c4365b) and the node-split measurement (39a4f73ff); B7 and B11 (fad1f0ad8); B10's windows and identities (d499b4e64); B10's last eight settings (5f5b943c9); the code review's fixes (186c68004); the image-shell sweep marked slow (996f9fd80). Rows landed: B11's three budgets (on the shipped schedule), `_BASES_CHUNK_ROWS` and `_DENSE_EIGEN_MAX` invariant; `MAX_NODES` tier 3. `WINDOW_MIN_DEG`, `window_slack_deg` and the three geometry caps went to tier 1 and back to tier 3 on the judge's review (below), with the evidence corrections it asked for in the same commit. Every failing setting stays tier 3 with its measured error in the row and a strict xfail in its test. `StageResult.seeded`, `SUGGEST_SEED_ROUGHNESS`, `HARMONIC_WEIGHT_SEED` and the four intermediate-tolerance rows stay unaudited, each with what it waits on in `waiting.md`.

*Measured.* Every number is in `waiting.md` by class and in the new tests' docstrings; the headlines, all `[dev]`, darwin/arm64:

- B3: Suortti's b from 0 and from 0.3 agrees to 2.7e-3 esd on five lab patterns from three laboratories; Pitschke's c does not (CPD zincite from 0: scale ×2.1, out of regime). The Stephens seed's second family (CPD brucite) favoured 1000 ppm, χ² 7.77 against 8.32.
- B9: the width start is invariant from w, x = 1e-4 to 1e-2. Biso 0.5 and the harmonic seed move answers by up to 0.16 and 0.15 esd, through the frozen last-stage compile: one recompiled stage brings them within 0.012.
- B7: 1e-6 against 1e-9 stays within 0.03 plain esd on every fit but cpd-1a's QPA protocol (0.033 LM, 0.074 TRF); with an absent zircon declared, the hold fires at 1e-6 and not at 1e-9.
- B11: worst stage 49 of 400 evaluations, 1.79 evaluations an iteration against 4, 9 LM trials against 18, on nine configurations from four laboratories.
- B10: the window area tolerance misdraws up to 2.15σ at a point and a converged refit moves non-background rows up to 0.97 esd; the four FCJ constants each miss over part of the domain, worst for Lorentzian-rich peaks (5.6e-3 of the peak maximum against 7.2e-4) and where the node cap binds at low angle (0.21-0.26); a length-proportional node split is unsafe when frozen; the reflection margin, the axial and magnetic sizing floors, the origin clip and the texture sampling fail by smaller amounts; the restraint image shell misses neighbours in unreduced monoclinic cells (a defect). The SRM 660c and cpd-1a answers end with high-angle reflections on the Gaussian-variance floor, where an FD column is 2.2e-2 off (forwarded to 1467).
- Practice checked: GSAS-II 5.8.4 computes each peak over 50 FWHM below and 75 above, recomputed at every evaluation (`GSASIIpwd.getWidthsCW`), and has no Pitschke roughness model.
- Tests. The touched files collect +71 fast and +41 slow tests against `origin/main` (05ac4bac6); one fast domain sweep (5 cases) then moved to slow, so the fast tier gains 66. The fast selection, run once before that move with one other pytest on the machine: 10 937 passed, 191 skipped, 32 xfailed, 1 failed in 4:28, the failure the stale WP index (fixed, `test_docs_consistency.py` 25 passed). Passed+skipped+xfailed+failed is 11 161, which is 71 above the 11 090 of the last handover's merged tree. The 30 new xfails are strict and each names a measured failure. The added fast tests take 2.4 s together without the moved sweep, the largest 1.66 s (`test_every_fd_column_meets_a_converged_oracle`, 21 cases); the sweep took 7.24 s. The full suite did not run: the branch changes tests, the audit table's text and one comment, so it cannot move a measured number. Every slow test it adds ran in its own file.
- Lanes (`session_usage.py lanes`): seven lanes, none kept in main, re-read median 0K, 12 main requests per lane, 20K left in main, actual over estimated requests 2.77, six fixed by main afterwards and none redone, saved $29.49 (37 % of the session). The selective policy's baseline over all sessions: −11 %.

| lane | est | requests | main at dispatch | lane $ | saved $ |
|---|---|---|---|---|---|
| B3 two-start | 30 | 49 | 163K | 3.01 | +1.68 |
| B9 starting values | 30 | 83 | 205K | 4.94 | +3.69 |
| B10 FCJ domain test | 30 | 82 | 229K | 4.38 | +3.72 |
| FCJ segment split | 20 | 72 | 258K | 3.30 | +3.09 |
| B7+B11 tolerance and budgets | 40 | 69 | 273K | 3.72 | +3.35 |
| B10 windows and identities | 35 | 125 | 296K | 9.61 | +6.19 |
| B10 remaining settings | 35 | 141 | 320K | 10.46 | +7.76 |

*Code review* (`high --fix 05ac4bac6..HEAD`): eight findings. The review fixed four: the FCJ domain cases now stay inside 2-160°, the window test shares one cached fit, the Richardson oracle takes one pass, and FD_STEP's evidence reads 2.5e-4. Three more fixed here: the LM trial margin is 2× not 3× (a stage's last iteration tried up to 9), TRF's per-iteration margin is asserted at 1.5× since 2.2× was measured on one platform, and the window polish now fails if it does not settle (all settle today). Declined: sharing the three caches of the same protocol fits across modules, which moves tests between xdist groups and so changes the longest group.

*Generality* (the `generality-review` judge, fresh context, on every row in `tests.audit_delta`'s list; its sections unedited but for heading levels, the author's answer under each weak verdict):

**Item 1a. `rietx.optimize.least_squares.NFEV_PER_ITERATION` and `rietx.schemas.plan.StageSpec:max_iter` (unaudited → invariant)**

**Weak.** The case for invariance is strong on the shipped schedule. Under `intermediate_ftol=None`, a setting callers can choose, the margin is 1.24x and the budget fired once, so the unconditional label claims more than was measured. (`intermediate_ftol=None` converges every stage to 1e-9. The root CLAUDE.md says goldens declare it, and B7, the intermediate-tolerance class still awaiting a ruling, could make it the default.)

| Question | Author's answer (where) | What I found | Verdict |
|---|---|---|---|
| 1. What it decides | "the stage budget is max_iter x 4 evaluations" (`_audit.py:1573`); "caps evaluations ... never iterations" (`:2250`) | It stops a stage after 400 residual evaluations. Neither driver counts iterations: one stage ran 110 iterations at max_iter 100 (test docstring, `tests/test_budget_and_tolerance_invariance.py:42-46`). | agrees |
| 2. Kind | max_iter row: `ambiguity=1`; NFEV row has none | Kind 1 (every refiner stops a runaway), as long as a converging fit never reaches the cap. | agrees |
| 3. Case against acting | "every stage at 1e-9 leaves LM 1.24x, and a cell walking unheld bound it once" (`:1573`) | Under `intermediate_ftol=None` on cpd-1a with zircon (a phase the sample lacks), `lines_axial` spent 400 of 400 evaluations and reported `STAGE_MAX_ITER`. The next stage converged at 323 of 400. Nobody measured whether the final answer depends on the budget there. A single all-free stage at 1e-9 (the shape `run_stage` runs) used 107 evaluations: 3.7x, with no test. | the 1.24x is disclosed but the tier does not condition on it |
| 4. Case for acting | 8.2x (LM) and 8.5x (TRF) worst over nine configurations; the answer is bit-identical at max_iter 25 under both solvers | Confirmed in the test: margins asserted at 4x on evaluations and 1.5x on the per-iteration rate, plus a bit-identical refit at a quarter of the budget, both solvers. | strong on the shipped schedule |
| 5. Tier and test | invariant, B11 ruling (`rulings.md:61-62`) | `test_a_converging_fit_stays_inside_every_budget` and `test_the_answer_is_the_same_with_the_evaluation_budget_cut_to_its_margin`, both `slow`, so they run nightly and not per PR. Both fit only cpd-1a under its QPA protocol (the quantitative-phase-analysis plan). The nine-configuration figures are scratch measurements quoted in the docstring. | meets the record's test for this class, on one schedule |
| 6. Families | "nine configurations from four laboratories" | SRM 660c (NIST), FAP, CPD (CSIRO), 11-BM NAC: four for the margin. One (cpd-1a) for the asserted invariance. Reference: the shipped-budget answer, bit for bit (verification only). | adequate for this class |
| 7. What says it fired | none given in the row | `STAGE_MAX_ITER` (warning) and `StageResult.status` | exists |
| Baseline | NFEV and max_iter removed from `UNAUDITED_BASELINE` | The list shrinks. | fine |

Would change the verdict: the row's evidence states "on the shipped schedule (intermediate_ftol 1e-6)" and names B7's ruling as a re-measure trigger. Or a refit of cpd-1a with zircon under `None` at max_iter 100 and 200 gives the same final answer.

> Author: done as the judge asked. Both rows now say the invariance is the shipped schedule's and that B7's ruling triggers a re-measure; `waiting.md` § B7 says the same.

**Item 1b. `rietx.optimize.lm._INNER_MAX` (unaudited → invariant)**

**Holds**, on a thin margin. The evidence for invariance is stronger than any case against it. The one comment this session changed overstates a guarantee.

| Question | Author's answer (where) | What I found | Verdict |
|---|---|---|---|
| 1. What it decides | "inner (Levenberg-Marquardt) iterations per outer iteration before giving up" (`lm.py:129`) | When the 18 damped trials run out, LM ends the stage as converged (`termination="no_descent"`, `status=1`, `n_stalled=18`; `lm.py:593-607`). | agrees |
| 2. Kind | none on the row | Kind 1 while it never binds. | — |
| 3. Case against acting | "at 4 the answer changes" (`:1638`) | The true margin lies between 2x (measured: 9 of 18) and 4.5x (a cut to 4 trials changed the answer). The new comment says "from λ = 0 the 18th trial runs at λ = 1e16 ... if nothing downhill exists there, none exists". That ignores the curvature gate: at λ ≥ 100 a curvature measurement can reset λ to its value at the start of the iteration (`lm.py:565-576`). So 18 trials need not reach 1e16. A cap that fires then reads as convergence. | comment overstated; behaviour measured fine |
| 4. Case for acting | "an iteration that took a step tried at most 6 damped trials and a stage's last iteration up to 9 (2.0x)"; bit-identical at 9 | Confirmed: `test_the_answer_is_the_same_with_lm_trials_cut_to_their_margin` and the 2x margin assertion. No stage ended on `no_descent` in nine configurations. The precedent `FIRST_RUNG_FACTOR` was kept at 2.3x. | holds |
| 5. Tier and test | invariant, B11 | The two tests above (slow). TRF has no such loop, as the grounds say. | holds |
| 6. Families | nine configurations, four labs | Same as 1a. In the test, cpd-1a sits at 6 trials against a limit of 9. | adequate |
| 7. What says it fired | none given | `n_stalled` and `termination` on the solver outcome. The stage still reads "converged". I did not check whether `StageResult` carries `n_stalled`. | weak record |

Would change the verdict: a configuration whose stepping iteration needs 9 or more trials. Separately, the comment should say that λ can be reset below 1e16 by the curvature gate.

> Author: the comment now says the curvature gate can reset λ, and that a cap that fires reads as convergence (`no_descent`).

**Item 2. `rietx.model.forward._BASES_CHUNK_ROWS` and `rietx.optimize.blocked._DENSE_EIGEN_MAX` (tier 3 → invariant)**

**Holds** for both. Each has an identity test that was made to fail once. No case against was found beyond a measure-zero edge for the eigen-switch.

| Question | Author's answer (where) | What I found | Verdict |
|---|---|---|---|
| 1. What it decides | chunking of the derivative bases (`:1312`); dense eigensolve against Lanczos (an iterative solver for the largest eigenvalue) for \|λ\|max, which "only places the pseudo-inverse cut" (`:1548`) | Both are internal splits of the computation. | agrees |
| 3. Case against acting | none stated | `_BASES_CHUNK_ROWS`: none found. No row reads another, so identity holds by construction. The test switches the compiled tier off (module fixture, lines 55-57), so `tchz_pv` does reach the chunk loop. `_DENSE_EIGEN_MAX`: an eigenvalue within 1e-6 relative of the cut would be discarded on one side of the switch and kept on the other. The test asserts that no eigenvalue sits there (`test_parametric_series.py:1112`). The measured gap is 2.4e10x the cut. | negligible |
| 4. Case for acting | bit-identical at 1, 7, 128 and 4096 rows, tchz_pv and voigt; \|λ\|max agrees to 3.7e-14, esds bit-identical | Confirmed in `test_the_fcj_chunk_size_leaves_every_plane_bit_identical` and `test_the_eigenvalue_switch_moves_only_the_cut` (random and library cases, 83-84 and 204 columns). | holds |
| 5. Tier and test | invariant, B10 option 2 | the tests above | holds |
| 6. Families | n/a | Identity claims; families are not required. | n/a |
| 7. What says it fired | n/a | Nothing fires. | n/a |

Would change the verdict: a real fit with an eigenvalue within the Lanczos tolerance of the cut.

**Item 3. `rietx.model.forward.WINDOW_MIN_DEG` and `rietx.schemas.plan.StageSpec:window_slack_deg` (tier 3 → 1)**

**Weak.** The test bounds in-stage movement only from starts near each protocol's answer. The constant's own comment claims a wider domain, and the margin is 1.4x.

| Question | Author's answer (where) | What I found | Verdict |
|---|---|---|---|
| 1. What it decides | "the room a peak has to move within one stage" (`:1305`) | The comment at `forward.py:197-200` claims cover for "zero-shift, displacement and the cell" moving a peak within a stage. | — |
| 3. Case against acting | none given | The cold start tested is the zero 0.1° off. NAC is excluded from the cold start (test docstring lines 70-73). No start has a cell off its answer. My arithmetic, not run: a literature cell 0.3 % off moves a 120° peak about 0.6°, twice the slack (2·tanθ·Δd/d). A solid solution or a structure from another temperature is a common first fit. Past the slack, the frozen window clips the peak for that stage, and nothing reports it. "Slack 0 and 1 deg move nothing" was measured at the converged tolerance (5e-5), where windows are wide. It says nothing about the shipped 2e-2 windows. | substantive |
| 4. Case for acting | largest move 0.21° over 7 cells, warm and cold (`:1305`) | Confirmed: `test_window_min_deg_covers_every_stages_movement`, made to fail at 0.1. The next stage recompiles, so a clip affects the path, not necessarily the final answer. That last point is unmeasured. | real but narrow |
| 5. Tier and test | tier 1 under B10 ("a test bounds its error over the claimed domain") | The test covers the starts it ran, not the domain the comment states. `window_slack_deg`: `test_a_stage_without_window_slack_compiles_the_window_min_deg_windows` shows `None` is the constant bit for bit, so its inheritance holds. | weak |
| 6. Families | SRM 660c, FAP, cpd-1a, NAC | Four labs and instruments. The reference is the start-of-stage peak position (verification). | adequate in count, narrow in starts |
| 7. What says it fired | none given | none found. A peak leaving its window mid-stage is silent. | none |

Would change the verdict: a cold start with the cell 0.3-1 % off on two families shows the final answer within the 0.1 plain-esd bar (plain esd: without the Bérar-Lelann inflation). Or the comment narrows its claim to zero and displacement.

> Author: both rows back to tier 3, the evidence naming the untested cell start and the silent clip; the cold start with the cell off is owed with the interval and width-grid tests.

**Item 4a. `rietx.model.geometry.CONTACT_MAX_ANG` (tier 3 → 1, "a report scope the output states")**

**Weak.** The radius also cuts bonds that the module's own criterion calls bonds, and no note says so. The grounds' "exact disclosure beyond it in GeometryTable.notes" is not true for this row.

| Question | Author's answer (where) | What I found | Verdict |
|---|---|---|---|
| 1. What it decides | "the contact search is complete within 3.5 A" (`:1331`) | The neighbour search itself stops at 3.5 Å (`geometry.py:309, 322`), so bonds beyond 3.5 Å are never found. Yet the docstring at `geometry.py:103` says "Bonds and angles are uncapped — chemistry bounds them". | broader than stated |
| 3. Case against acting | none given | A refiner of a heavy-cation halide would dissent. With Cordero radii (recalled: Cs 2.44, Cl 1.02, I 1.39) plus the 0.4 Å slack, Cs–Cl at about 3.57 Å in CsCl and Cs–I in CsPbI₃ are bonds by the criterion but lie beyond 3.5 Å. So Cs gets no bonds, angles or coordination number. The only disclosure is `GeometryTable.contact_max`. No note fires. I derived this from the code and recalled cells; I did not run it. | substantive |
| 4. Case for acting | tests assert completeness within 3.5 Å in an unreduced cell | Confirmed: `test_the_contact_search_is_complete_in_an_unreduced_cell` (a β = 150° cell, checked against brute-force enumeration). Nothing downstream acts on the table: report, CIF export and GUI only. | holds within its scope |
| 5. Tier | tier 1, "a report scope" | `generality.md` § The rule has no "report scope" class. 3.5 Å is rietx's own choice ("short enough that the row count stays readable", `geometry.py:98`), so it is not physics or arithmetic. The maintainer should rule on the new category. | not tier 1 as written |
| 6. Families | tests/data structures | none relevant | — |
| 7. What says it fired | "GeometryTable.notes" | Only `contact_max` on the table. No note fires. | grounds misstated |

Would change the verdict: the search radius rises to the largest bond criterion for the phase's species, or a note counts the criterion-bonds beyond 3.5 Å. Then "report scope" holds.

> Author: back to tier 3 with the bond cut in its evidence; the category is the fifth round's Q6, and the bond cut is a defect for the next session.

**Item 4b. `rietx.model.geometry.MAX_ASYM_ATOMS`**

**Weak.** The skip is disclosed, but 200 has no cost measurement and the caller has no way to override it.

| Question | Author's answer (where) | What I found | Verdict |
|---|---|---|---|
| 3. Case against acting | none given | `geometry_table` takes no limit argument, so a caller with a phase over 200 asymmetric atoms (a Z' > 1 pharmaceutical with hydrogens) cannot get McCusker §11's distances (the 1999 Rietveld guidelines' call for bond lengths and angles) at all. | dissenter nameable, rare |
| 4. Case for acting | "a phase past it is skipped and GeometryTable.notes says so"; "tests/data reach 32 atoms" (`:1338`) | Disclosure is confirmed by `test_a_phase_too_large_to_search_says_so`. The 32-atom figure shows the cap is never exercised. It does not justify 200. The docstring's "a minute spent" (`geometry.py:113`) is not measured. | weak |
| 5. Tier | tier 1, report scope | as 4a | needs a ruling |
| 7. What says it fired | `GeometryTable.notes` | Confirmed. | holds |

Would change the verdict: a timing of the search at 200 atoms, or a caller override.

> Author: back to tier 3, the evidence saying the time at 200 is unmeasured and a caller cannot raise it.

**Item 4c. `rietx.model.geometry.MAX_CONTACTS_PER_ATOM`**

**Holds.** It keeps the nearest contacts, never bonds, and counts exactly what it drops.

| Question | Author's answer (where) | What I found | Verdict |
|---|---|---|---|
| 3. Case against acting | none given | none found. Short contacts are the nearest, so they are never dropped. | — |
| 4. Case for acting | "the note counts exactly what the cap drops and the kept contacts are the nearest" (`:1345`) | Confirmed by `test_the_contact_cap_note_counts_exactly_what_it_dropped`. Bond counts are unchanged under the cap. | holds |
| 7. What says it fired | `GeometryTable.notes` | Confirmed. | holds |

Would change the verdict: a consumer that reads contacts as complete.

> Author: kept at tier 3 beside its two siblings, since its tier 1 rested on the same uncreated category (Q6).

**Item 5. The fourteen settings kept or landed at tier 3 with a failing domain test**

**Holds** on keeping tier 3: every row states what failed and against what. The bar is defensible in kind and weak as calibrated: it is pinned to the most precise patterns on disk, not to the data being fitted, and its 0.1-esd answer half is looser than the bars this WP uses elsewhere.

**The bar** ("a tenth of σ/peak at the strongest peak of FAP.XRA and 11BM_NAC"; per point σ for the window rows):

- **For it.** Numerical error well under the counting noise, checked twice: at fixed parameters and at the answer. One anchor ties it to answers: SRM 660c's (100) at 6.3e-4 of the peak, with a 512-node refit moving no parameter past 0.04 esd (`test_lab_instrument.py:497-500`). The window tests use each point's own σ, which adapts to the data.
- **Against it, first.** The FCJ bar is fixed at FAP.XRA's 19 693 counts (`test_lab_instrument.py:491-495`). FCJ is the Finger-Cox-Jephcoat axial-divergence asymmetry. A pattern with ten or a hundred times those counts, routine on a strip detector (recalled, not measured here), makes the lab bar 0.3-1σ of that pattern's own noise. The bar should either be written relative to σ/peak, as the window test does, or state the count ceiling it covers.
- **Against it, second.** The answer half (0.1 plain esd) is 3-10x looser than the bars set in this WP for the same question: B3's seed test at 0.01 esd and B7's tolerance test at 0.03. At 0.03, the FCJ anchor's own 0.04 esd would fail. This is rulings.md's fifth-round Q2, and it decides this class too.
- **Against it, third.** "Adds 1 % to that point's χ²" is a per-point argument. A shape error spans a whole peak with one sign, so it biases parameters more than independent noise would. The answer test is what catches that, and for the FCJ constants it ran on one family.

| Row | What the evidence states | Gap I found |
|---|---|---|
| `fcj.MAX_NODES` (`:1417`, unaudited → 3) | lab fails 0.21-0.26 of the peak below about 6.2° 2θ; synchrotron fails at η 0.5 and 1 | The synchrotron figures (4.2e-4 and 9.9e-4 at 2°) and the 512-node reference are in the test, not the row. Lab data rarely reach below 6°. `approved` carries B10's date, though this row joined the class this session. |
| `fcj.MIN_NODES` (`:1425`) | passes lab η ≤ 0.5; fails lab η 1 (7.9e-4) and synchrotron | `waiting.md:90` says any value ≤ 8 is inert, since `max(n//2, 4)` floors every reflection at 8 images. The row should say that only a rise changes anything. |
| `fcj.NODES_PER_FWHM` (`:1433`) | 2.4e-3 and 5.6e-3 lab, every η synchrotron | none |
| `fcj.SKIP_EXTENT_FWHM_RATIO` (`:1442`) | 9.5e-3, error ≈ 0.48 × extent/FWHM | none; the bound is analytic |
| `forward.WINDOW_AREA_TOL` (`:1296`) | 0.71-2.15σ, 0.17-0.97 esd, four families; 1e-3 passes at 1.2-3.5x fit time | Omits `waiting.md:98`'s counterpoint (FAP χ² 110 higher with converged tails). Omits the constant's earlier validation against weighed QPA truth (`forward.py:186-188`). Omits that GSAS-II drops about 0.6 % of a Lorentzian (`rulings.md:176-179`). |
| `forward.REFLECTION_MARGIN_DEG` (`:1288`) | 0.124 and 0.119σ, 0.103 esd | Fails by 1.2x and 1.03x. Cost of 5° not stated. |
| `forward.AXIAL_SIZING_FLOOR` (`:1256`) | 0.27 of the peak maximum, 19.5 % area | Omits the answer effect the test records: the two floors' fixed points differ by 0.16 esd at χ² 0.008 apart (`test_lab_instrument.py:689-693`). The 0.27 is transient, since the next stage recompiles. |
| `forward.MAGNETIC_SIZING_FLOOR` (`:1265`) | 3.2-4.1 % of a peak, 0.031 esd preset, "one family" | none |
| `least_squares.FD_STEP` (`:1561`) | 23 configurations within 2.5e-4; fails on the variance floor, "1e-8 does not cure it" | The failure belongs to the clamp, not the step. On its smooth domain the step passes, so tier 1 is arguable once WP-1467 (the open fix for that clamp) lands. Keeping tier 3 now is honest. |
| `caglioti._MIN_GAMMA_G2` (`:1399`) | binds only on SRM 660c's and cpd-1a's answers; 1.2 esd on U under a 1e-10 floor | "4.4e-4 ... and 1.6e-4 ... within the lab and synchrotron bars" means respectively (the test's lines 349-352). Read the other way, 4.4e-4 fails the synchrotron bar. Add "respectively". |
| `origin.A5_CLIP` (`:1361`) | 1.40 % against 1 %, 1200 synthetic matrices | The bar (an esd's sampling error at N − P = 5000) is defensible. NAC's N − P of about 22 000 would set it near 0.5 %. |
| `preferred_orientation.TEXTURE_SPHERE_SAMPLES` (`:1385`) | misses by 2.0e-3 to 7.9e-3 against "the digit TEXTURE_NOT_POSITIVE prints" | Wrong frame. The sampled minimum feeds a guard (`forward.py:1520`, "a record and a guard read it"), and sampling can only miss a dip, never invent one. So the question is how deep a dip can stay unreported (up to 7.9e-3), not the printed digit. `TEXTURE_NOT_POSITIVE` is the warning that the texture's pole density has gone negative somewhere. |
| `restraints.MIN_IMAGE_SHELL` (`:1466`) | misses 72 of 2518 pairs within 4 Å at β 135-150° | A defect with a named fix. The row does not say whether any missed pair lies at bond length (under about 2.5 Å). |

Would change the verdict on the bar: stating it relative to each pattern's own σ/peak, and a ruling on Q2 that sets one esd bar across B3, B7 and B10.

> Author: corrected in the rows: "respectively", `MIN_NODES`'s inert range, the texture frame (an unreported dip), `WINDOW_AREA_TOL`'s counterpoint and GSAS-II's 0.6 %, the axial floor's answer effect. The bar's calibration joins Q1 and Q2 for the maintainer. Not done: whether a missed restraint pair lies at bond length, which the image-shell fix makes moot.

**Item 6. `rietx.strategy.suggest.SUGGEST_SEED_STEPHENS` (tier 3, evidence updated)**

**Weak.** The new evidence measures the plan's solve seed, not the suggestion probe this row governs. Neither new comparison sets 1000 ppm against a distinct non-zero start.

| Question | Author's answer (where) | What I found | Verdict |
|---|---|---|---|
| 1. What it decides | "= lab_sample_refine's strain_seed" (`:2216`) | The constant is the start `Refinement.suggest` uses to score a Stephens candidate (`refine.py:3595`; Stephens is the anisotropic-strain model). The solve seed is a separate hand row (`:2271-2273`). `waiting.md:23-25` leaves `SUGGEST_SEED_ROUGHNESS` unaudited for exactly this reason: whether `suggest`'s ranking moves with the start. | evidence answers a different seat |
| 3. Case against acting | "brucite tests only a near-zero start" | Brucite compares 1000 ppm against 0.35 ppm. That is the square-root singularity, the forced case the grounds already cite. Corundum compares 903 against 1000 ppm, nearly the same start. Only WP-1467's pattern 41 compared a distinct start (the previous stage's strain), and lost. | the second family does not discriminate |
| 4. Case for acting | "1000 ppm reached the lower or equal minimum in all three comparisons" | True as stated. 800 ppm agreed to 0.01 esd on brucite: local robustness. GSAS-II's isotropic 1000 µstrain is a Reset button, not a default (`1467:217`). | weak |
| 5. Tier | tier 3, B3 (`rulings.md:49-51`) | B3 asked for "a second dataset compares the starts". CPD brucite and CPD corundum come from one lab and one instrument. | partly met |
| 6. Families | WP-1467 pattern 41; CPD | Two at most. The reference is the lower χ², which is not independent of the fit. | weak |
| 7. What says it fired | none given | It is a probe start, so nothing fires. | n/a |

Would change the verdict: the suggestion's ranking of the Stephens candidate compared at 1000 ppm and at a distinct non-zero start (such as the phase's isotropic strain on pattern 41, or patterns 0 and 16), as WP-1467's seed task asks.

> Author: the row now says these are the solve seed's measurements and the probe's start is unmeasured, as `SUGGEST_SEED_ROUGHNESS`'s is; it stays tier 3.

**The rows left at unaudited**

**Holds** for all of them. Each waits on a measurement or a ruling it names. Two notes:

- **`INTERMEDIATE_FTOL` and its three siblings.** The hold flip already refutes invariance under any esd bar. At 1e-6 the absent zircon is held; at 1e-9 it is not and its cell walks (`waiting.md:41-46`). So Q2 decides only between tier 3 and demotion. The waiting note should say that. Item 1a's budget invariance also rests on this ruling: the 1.24x margin is the `None` schedule's. If that becomes the default, the three B11 rows need re-measuring.
- **`SUGGEST_SEED_ROUGHNESS`.** It is left unaudited because the probe start was not measured. `SUGGEST_SEED_STEPHENS` (item 6) has the same gap and sits at tier 3. The two should be treated alike: the Stephens row's evidence should say the probe is unmeasured.

`StageResult.seeded` (one literal seeds both Suortti's b, which is invariant, and Pitschke's c, which is not) and `HARMONIC_WEIGHT_SEED` (one synthetic family, failing at 0.01 esd by the plan's mechanism) wait correctly on Q3 and Q2. No name was added to `UNAUDITED_BASELINE`. Four were removed, so the list shrank.

Would change this: a Q2 ruling, after which the `INTERMEDIATE_FTOL` group has nothing left to wait on.

> Author: `waiting.md` § B7 now says both.

*Decided on the maintainer's behalf.* The domain tests' bar: a tenth of σ at a point, or of σ/peak at the strongest peak of FAP (lab) and 11-BM NAC (synchrotron), which adds 1 % to that point's expected χ²; a strict bar, chosen so a pass means the setting is invisible in the data. No constant changed, even where the measured fix was cheap, because each moves every fit that reaches it.

*Gotchas.* LaB6 under the NIST protocol has two minima 46.7 χ² apart, nearly S/L ↔ H/L mirrors, and LM and TRF land in different ones; its polish fixed points are not unique either. A comparison of two arms should polish both from one common start. An odd FCJ node count gives the same answer as one fewer (n//2 a segment). The worktree guard refuses a heredoc whose text it cannot parse; write the script to the scratchpad and run it.

*Next.* (1) The fifth round's answers, then their builds: each constant change moves every fit that reaches it, so goldens are re-pinned in the same commit, and `docs/docs/theory/profiles.md:511` hard-codes the FCJ clamp "[8, 64]". (2) Two defect fixes needing no ruling: the restraint image shell sized by `geometry._shell(g, d)`, and the bond search freed from the 3.5 Å contact radius (or a note counting what it cuts). (3) B14's lifts with the ~50-guard list to the judge. (4) The interval and width-grid domain tests. (5) B7 and B9 re-measured once the window ruling lands, since window truncation is part of the frozen-compile scatter.

- **2026-10-20** — Split at the maintainer's request after the 2nd session's handover. The second pass (three families per surviving tier-3 threshold) moves to [2017](2017-the-second-pass-every-tier-3-threshold-on-three-families.md) and the clash table's 38 pairs to [2018](2018-the-clash-table-measured.md), each with the context this file held. This WP now closes on two sessions' work: the owed tests (two-start, invariance, margin, domain, the FCJ node cap), then B14's lifts with the ~50-guard list to the judge, with the goldens and `test_compare_ui` rows on the way. The maintainer's estimate question was "how many more sessions in 2002": about five or six unsplit, two now.

### 2026-10-20 (2nd session) — the last five questions ruled, a contributor's second read built, and the position limits gone

Every question the batch left open is now answered, and the answers run in the code. The
peak-position corrections (zero shift, displacement, the capillary offsets, transparency's
ceiling) have no default limits any more: on 11-BM NAC the fit reports the degeneracy
either way, and the limit only acted as a prior that the mount is aligned, which belongs to
a caller who knows the mount. A refined occupancy above 1 is an info record, a tie between
magnetic models abstains instead of crowning the simpler one, and `auto_background` keeps
its pick because the near-threshold choices measurably move nothing. Mike Gaultois's second
read of the batch found three real defects, all fixed: Le Bail and Pawley could not refine
a wavelength or the Kα2 ratio, a history replay turned an explicit 0 into the default, and
the CIF quoted a slightly wrong esd factor. Building the first exposed a fourth:
`suggest()` silently dropped a held wavelength in every mode.

*Done.* Rulings recorded in `2002-batch/rulings.md` § fourth round, with the maintainer's
words where given. Asked "check other codes": GSAS-II 5.8.4 and FullProf bound none of the
position corrections nor U, V, W, X, Y; TOPAS v9 § 2.17 Table 2-1 has no row for either
(its macros' limits live in `Topas.inc`, not on this machine), lists `occ` 0 to 2·Val + 1,
and moves a, b, c within ±(0.5 % + 0.05 Å) per iteration. Built, one commit each: the
position bounds removed, the NAC test asserting the report instead of `BOUND_HIT`
(3d63e9db5); Le Bail and Pawley refine `.source.lines.` (84b9e87a2); a held azimuth is
never turned (d02cbfe6d, test); cherry-pick replays an explicit 0 (ce1961d7b); the CIF
quotes the carried factor (6a72cc225); `suggest` scores a held wavelength against the held
cell (ed72edd12); `OCCUPANCY_ABOVE_ONE` at info (da9d30d02); every ΔBIC tie abstains,
listed fewest moment parameters first, the reported nuclear reference staying the ΔBIC
leader's (58534d7a2, 5e986acef); the auto_background rows kept at tier 3 with the
measurement; the cell window, twelve solver stop constants and `DENSE_JACOBIAN_MAX_BYTES`
to tier 3 (approved); the profile walk's and the width grid's settings from `caller` to
tier 3 under B10; `phase_support_sigma` and `correlation_guard` reach the package's own
trials (a56ba4d26) and are recorded on `NodeAction` so a cherry-pick replays them
(761f899c7); the line columns' Jacobian checked under both intensity models (9ecf7b2cb);
main merged twice, this branch's WP-2013 renumbered WP-2015 after main took 2013; the new
manual pages main's WP-1986 had copied before this branch's edits brought up to date
(c406fe513); WP-2016 filed (a CIF U^ij off its site symmetry only by rounding); B5.2's
warning proposal forwarded to WP-1952. The reply to Mike is on PR #1050. Q3, the TCHZ
box, waits for the next session by ruling.

*Measured.* Other codes and the background measurement as in `rulings.md`. 11-BM NAC, zero
and both capillary offsets free (R = 1000 mm, `test_capillary_displacement.py`'s
protocol), cell from the acceptance band's centre 10.2510 Å: offsets held +21 ppm (esd 6);
bounded −1097 ppm (esd 2612), seven warnings; unbounded −5109 ppm (esd 2579), six, two of
them `FLAT_DIRECTION` naming the cell and an offset. SRM 660c Kα2/Kα1: 0.5126 ± 0.0048
Rietveld, 0.5145 ± 0.0036 Pawley, 0.5224 ± 0.0033 Le Bail; Le Bail with the cell held
refines λ to 1.540605 ± 3e-6 Å against the declared 1.5405929. Line columns against
central differences on a Cu Kα doublet: 5e-10 (weight) and 3e-7 (wavelength) relative in
all three modes. auto_background on 30 real patterns: hump score 0.036-0.067 on five
synchrotron or low-background, 0.10-2.3 on all 25 lab; air gain within 0.06 of 0.3 on 6;
seven patterns refitted four ways moved no cell, scale or Biso past 0.8 esd except FAP with
its air term left out (scale 2 esd, Lorentzian size and strain 3 esd), a choice the pick
does not make. Suites on this branch merged with `origin/main` at `0d6d5a441`, `[dev]`, darwin/arm64, no other suite running: fast 10 895 passed, 191 skipped, 2 xfailed, 2 failed in 4:21; full 11 210 passed, 200 skipped, 2 xfailed, 2 failed in 20:30. The two failures were this session's own and are fixed in 89b343fe4 (the root CLAUDE.md one line over its cap, and "Lelann" added to the generated accept list rather than its source); both files then passed alone, 46 passed. The full suite was not re-run after that fix, which touches no code. Every bit-identity golden passed. Against the lane's fast run on the tree before the review fixes (10 894 passed, 191 skipped), passed+skipped+failed moved by exactly the three tests the review added. The full selection has two fewer skips than an earlier full run this session (202), not traced. The branch adds 64 tests to the fast tier, 27.5 s together locally, the largest 7.0 s (`test_stationary_moment_angle.py`, an earlier session's); this session's largest is 1.3 s (`test_magnetic.py`'s held azimuth), so none joins the tail. Lanes: none dispatched under `/wp-start` 6c's `lane:`
form, so 3b does not apply; four helper agents ran (other codes, background impact, the
manual port, the plan-settings item).

*Code review* (`high --fix`, in two ranges to keep main's merged diff out). Post-merge
range, eight findings, four fixed: the old refining chapter's tie sentence (372b18803);
`api_call` compares against the live constants (9b0170182); a tie reports the ΔBIC
leader's nuclear reference, and the reorder uses an id set (5e986acef). Declined: trials
taking the carried settings as their `run_stage` default (a public default change, the
lane's decision 1 below); the `approved` dates of the six B10 re-tiers (traced in
`rulings.md` instead); the repeated grounds text (`tests/audit_delta.py` reads row fields
by `ast.literal_eval`, so a shared constant would break it). The missing direct
assertion for the wavelength in `suggest` is the Le Bail count check, which failed before
the fix (18 against 19). Pre-merge range, nine findings, eight fixed: the CIF compares
factors before rounding (975c707ba); the `.instprm` reader's dead zero widening
(3311ea5cf); the capillary check's docstring and the force-fix comment (df04e74c7); the
cross-backend stage harness asks `mode_fixed_path` (88931ec04); the line columns' Jacobian
test (9ecf7b2cb); the rulebook's 11-BM clause and the summary's esd factor (d51b73397).
Declined: the repeated audit evidence text, as above.

*Generality* (the `generality-review` judge, fresh context, on this session's 13 items;
its full text in this session's transcript; verdicts and the author's answers):

| Item | Verdict | Case the judge found | Author's answer |
|---|---|---|---|
| `AIR_SCATTER_TRIGGER` | holds | three families, no independent reference (qarr's weighed compositions unused) | second pass, against the weighed values |
| `HUMP_TRIGGER`, the two knot steps | weak | the target case, a real amorphous hump, is untested; the score cannot see one | next: a real hump (glass capillary, an amorphous binder) at 3° and 8° |
| the cell window to tier 3 | holds | may never bind under the hold | the second pass counts it |
| `OCCUPANCY_ABOVE_ONE` at info | holds | — | — |
| `MOMENT_ANGLE_STATIONARY` wording | weak | "always" overclaims: the test's linear refit sits up to 1.5 from the full one, the cuts 1.13 apart | reworded "nearly always" (98e07a9e7) |
| interval and width-grid settings | holds | domain tests owed | owed |
| twelve stop constants | holds | `_CAUCHY_ARMIJO`'s grounds overstated | reworded (98e07a9e7) |
| `DENSE_JACOBIAN_MAX_BYTES` | holds | one case | second pass |
| position bounds removed | holds | the change described the NAC measurement wrongly: the bound hid nothing, it was a prior that held there; one family | reworded in the schema comment, reference page and test (98e07a9e7); a flat-plate lab family owed |
| Le Bail/Pawley lines | holds | one standard, no reference ratio; Le Bail 1.7σ from Rietveld | a second standard owed |
| `suggest` ordering | holds | — | — |
| ties abstain | holds | `trials[0]` is no winner; a careless caller could read it as one | `best` is `None` and the reason says so |
| plan settings inherited | holds | `StageResult` carries neither setting | lane decision 2, below |
| CIF factor | holds | the TOPAS clause said more than its reference | reworded (98e07a9e7) |

*Decided on the maintainer's behalf* (the plan-settings lane): `run_stage`'s public defaults
stay 3σ and 0.98, so a bare `ref.run_stage` after a fit with the hold off still holds at
3σ; the alternative is a sentinel that inherits the last fit's, as `mode` and
`two_theta_limits` do. `StageResult` got no field (nothing replays from a result, and
`PHASE_UNCONSTRAINED` quotes the threshold). A guard a plan set before this change was
never recorded, so those nodes replay at 0.98.

*Gotchas.* main's WP-1986 copies an old chapter into `docs/docs/` and leaves the old page
standing, so a branch that edited the old page merges clean and the new page keeps the old
text; only a vanished substitution or xref fails the build. After a merge, grep the new
tree for each fact the branch changed. `set_vary`'s wavelength refusal is per row and
order-dependent within one call, so a caller freeing a mixed set reads its return or splits
the call. A Jacobian check against a blank pattern under an intensity model measures noise:
the extracted intensities are zero. `vale` needs `vale sync` once in a fresh worktree.

*Next.* (1) The owed tests, smallest first: B3's two-start tests (roughness and Stephens
seeds), B9's starting values (Biso 0.5, the TCHZ starts, the harmonic seed), B7's
intermediate-tolerance invariance in plain esds, B11's iteration-budget margins under both
solvers, B10's domain tests and the FCJ node cap below 6.5° 2θ. Each moves a tier-3 row to
tier 1 or invariant, or finds a defect. (2) B14's lifts (about 20 constants, 8 seats, the
fields for the collapse restore, the Stephens seed and the σ rule) and the ~50-guard list
to the judge. (3) The second pass, three families per surviving threshold, which also
decides the twelve stop constants and seven switches now at tier 3; it includes a real
amorphous hump for the knot switch, a flat-plate family for the position bounds' removal,
and a second standard for the Le Bail line ratio. (4) The clash table's 38 pairs, goldens,
`test_compare_ui` rows. (5) Q3, the TCHZ box, whose open part is the upper limits (Y ≤ 1°
caps Lorentzian size near 8 nm at Cu Kα under the default plan); and the lane's decision
1, if the maintainer wants `run_stage` to inherit the last fit's plan settings.

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

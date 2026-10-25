# WP-2003 decision batch: what a series decides between patterns

This batch asks your rulings on the 83 WP-2003 entries that still need one: 49 rows of the
audit table and 34 row-less entries, each proposed for a row or for none. WP-2003 audits every
action `refine_sequential` and the joint fit take between patterns. The inventory holds 111
entries. 28 needed no approval and are not asked here: 17 were written into `src/rietx/_audit.py`
on 2026-10-24 and 11 were tiered by the session before (`"applied": true` and
`"status": "tiered 2026-10-24"` in `rows.json` beside this file). The 83 fall into eleven
classes. Three need a real judgement: C1, C3 and C9. Two ask you to confirm that an action
passes: C2 and C8. Four ask you to approve a demotion that the record's § Demotion already
implies: C4, C5, C6 and C7 (C7's constants go to WP-2004). Two are plain: C10 and C11. Each
brief opens with its stakes line (the record § The rule, 2026-10-20). Answer each class by its
numbered questions and option letters; the rulings are dated into `rows.json` and the table
afterwards.

*How this was made.* A survey of the seven programs' series defaults (`docs/practice.md`
§ Sequential refinement, 2026-10-24). A tiering pass over the inventory (`inventory.json` →
`rows.json`, drafted by class in `classes.md`). A reseed measurement on eight families under
three triggers, the Rwp fence (`on`), status only (`status`, the fence at infinity) and
`reseed=False` (`off`), against cold independent fits (`ref`) (`reseed.md`, `reseed/*.json`).
A clash pass over fifteen pairs of actions, most of them measured (`clashes.md`, X1-X15). A
fourth trigger arm, `status_maxiter`, run on all eight families after the clash pass
(2026-10-24, CPD finishing 2026-10-25). The lead session's review. The picks below are revised from `classes.md` by the clash table and the
new arm, and each section names what changed. Every figure quoted from `reseed/` was
re-projected from the JSONs for this batch (python reads only: a `rungs_tried` longer than one
is an escalation, `n_iterations` summed is the evaluations).

**Vocabulary** (as WP-2002's batch). Tier 1 is physics or arithmetic; tier 2 a validating
citation or the same default in one of the seven programs; tier 3 rietx's own, kept only with
your dated approval. `invariant`: the setting changes cost and leaves the accepted answer
alone, and a test asserts it. `caller`: only the caller turns it on. Kind 2 ranks alternatives
with their evidence and picks none; kind 3 reports the number with its meaning. `covered`: a
row-less joint-fit act whose record field already has a 2002 row and ruling. The "warm rung"
is the collapsed warm refit a pattern tries first; "the closing stage" is WP-2002's, which ends
every plan and which `_collapse` carries into each warm refit.

**The families.** Two are real, from different laboratories, instruments and materials. None
of the three families offered on PR #1150 had landed when tiering started (WP Context), so no
tier-3 threshold here meets the mechanical ground's three-family bar, and the picks lean on the
judgement ground and on demotion.

| Family | What it is | Patterns |
|---|---|---|
| CPD | IUCr CPD sample 1, 1a-1h, lab Cu Kα: eight weighed mixtures of corundum, zincite and fluorite (`tests/data/README.md:142-149`). A tray, not a ramp: corundum goes from 1.6 to 94.3 wt % between 1a and 1b | 8; the two newer arms run the first 2 |
| CPD, closing off | the same with `closing_window_tol=None` | 8 |
| Cr₂WO₆ | HB-2A neutron pair, 4 K then 150 K, nuclear plus magnetic | 2 |
| planted | synthetic perovskite cooling ramp, four planted events: background step at T050, blank frame at T087, unmodelled phase from T124, cubic → tetragonal at T186 (`tests/planted_series.py`) | 248 |
| planted null | its twin with no event | 248 |
| trigger | `examples/bench_refinement.py` `_trigger_series`: four phases, a cell ramp of 100 ppm a step | 10 |
| tut05-jump, tut05-broken | tutorial 05's LaB₆ ramp, 300-900 K, the 700 K cell × 1.02 or × 1.05 | 7 each |

| Class | Rows (pending of all) | What you decide | My pick |
|---|---|---|---|
| C1 What triggers the ladder | 11 of 11 | Whether the Rwp fence stays a trigger; what else sends a warm fit up | The fence becomes a reported ratio; escalate on diverged, raised or `max_iter` (measured on all eight families); one arm of a cell-guard trigger could replace it |
| C2 Ladder, quarantine, kept attempt | 11 of 13 | Confirm the protection; two ranking questions | Pass; a finite truncated attempt beats a diverged one; `max_iter` keeps tying `converged`; `seeded_from` lands |
| C3 First-rung budget | 4 of 4 | It moved an accepted value at its default: remove, keep as tier 3, or widen | Default `None` (caller opt-in), with its two defects fixed |
| C4 Discontinuity scan | 7 of 7 | Approve the demotion; what `verify_discontinuities` refits | Demote to `SeriesResult.steps`; the caller names the pairs or *k* |
| C5 Path dependence | 3 of 6 | Approve demoting the 3σ verdict to a field of gaps | Demote; split the incomplete-check code; each gap carries both walks' rung |
| C6 Persistent-finding summary | 5 of 5 | Approve demoting the half cut to a field of counts | Demote, after the agent harness |
| C7 Width growth | 6 of 6 | A ruling to hand WP-2004 | A field; the three constants to 2004 |
| C8 Moment carry | 5 of 5 | Confirm under the rare-feature clause | Pass; `floored` names the kept attempt; split the onset code |
| C9 Carry policy, closing stage | 8 of 10 | `carry`'s tier; whether a warm refit runs the closing stage | `carry` tier 2 with GSAS-II's dissent; keep the closing stage, recorded after X13's CPD arm |
| C10 Joint fit | 20 of 26 | Confirm 2002's rows cover the joint holds | Covered; the form test's hold waits for X14 |
| C11 Caller and invariant | 3 of 18 | Plain | `x`, `x_label`, `labels` invariant once their test arms land |

---

## C1. What sends a warm fit up the ladder

**Stakes.** Every value of an escalated pattern. On disk the fence acted on one real pattern,
CPD 1b with the closing stage on: unescalated, corundum read 86.7(129) wt % against 94.31
weighed, and its *a* 4.987(88) Å, 4.8 % from the independent fit's 4.75809(38); escalated, it
kept 94.24 wt % and 4.75804(38) Å, 0.07 wt % and 0.13 esd from them. Dissenter named: a
refiner whose series gains a lasting misfit, or loses counts under a right model. Planted from
T124 is that case: 114 patterns above the fence, 4.34× the evaluations, no accepted value moved
past 7.2e-4 esd.

**Rows.** `RESEED_FACTOR`, `fit:reseed_factor`, `fit:reseed`, `_reseed_needed` (row-less),
`SEQUENTIAL_RESEED` (+ suggestion), `SeriesEntry.reseeded`, `SeriesEntry.rwp_fence`,
`SEQUENTIAL_RWP_OUTLIER` (+ suggestion), `_chain.rwp_outlier_carve_out` (row-less).

**The decision.** Two questions.

1. Does the Rwp fence stay a trigger by default? The fence is `reseed_factor` (1.25) × the
   median Rwp of the patterns accepted so far (`sequential.py:171`, `:1992-2009`).
   (a) Yes, as today. (b) No: it becomes a reported number, and a caller who wants it as a
   trigger passes a factor of their own.
2. If (b), what sends a warm fit up besides divergence and a raise? (i) Nothing else.
   (ii) The result's status `max_iter`, which since WP-2002 is the closing stage's
   (`refine.py:5171`). (iii) The warm rung's own cell guard firing (`CELL_RUNAWAY`, the
   record of WP-2002's B8 clamp).

**Evidence.** The four trigger arms, by family: escalated patterns, then summed evaluations.
The last column compares `status_maxiter` with `status` pattern by pattern on `values_sha`.

| Family | on (fence) | status | off | status_maxiter | status_maxiter's values against status |
|---|---|---|---|---|---|
| trigger | 0, 269 | 0, 269 | 0, 269 | 0, 269 | identical, 10 of 10 |
| tut05-jump | 0, 551 | 0, 551 | 0, 551 | 0, 551 | identical, 7 of 7 |
| tut05-broken | 1, 157 | 0, 135 | 0, 135 | 0, 135 | identical, 7 of 7 |
| planted null | 0, 2 080 | 0, 2 080 | 0, 2 080 | 0, 2 080 | identical, 248 of 248 |
| Cr₂WO₆ | 0, 873 | 0, 873 | 0, 873 | 1, 2 582 | 150 K differs: largest gap 0.087 esd (`phases.0.atoms.2.x`), anchored DOFs left out (WP-1333) |
| planted | 115, 11 790 | 1, 2 716 | 1, 2 716 | 1, 2 716 | identical, 248 of 248 |
| CPD, closing off | 0, 708 | 0, 708 | 0, 708 | 0, 708 | identical, 8 of 8 |
| CPD, first 2, closing on | 1 (1b), 796 | 0, 703 | 0, 703 | 1 (1b), 796 | 1b differs: (ii) keeps the rescue, status the runaway; identical to `on`, 2 of 2 |

The CPD closing-on `on` arm ran all eight patterns (1 escalation, 987 evaluations); 796 is its
first two. Planted's one escalation in the last three arms is T087, forced by the first-rung
bound (C3; in the `off` arm, against the switch). On Cr₂WO₆ the one esd-less row that moved is
the angle of an unsupported moment (|m| 0.046(49) μB), −3.126 to −3.141.

What the arms show:

- **The fence's one rescue is of a runaway the closing stage made on a warm refit** (X3). On
  CPD 1b the warm stage converged in 136 evaluations, then the closing stage ran to `max_iter`
  at 400: Rwp 0.7652, zero shift 18.0(74)°, `CELL_RUNAWAY`. With the closing stage off, the
  same warm rung converged in 410 evaluations at Rwp 0.1633 (0.1393 cold), corundum's cell held
  and absent from the result, corundum 94.84(27) wt % against 94.31 weighed, `CELL_RUNAWAY` and
  `PHASE_UNCONSTRAINED` firing. It passes the fence (0.2095) and every other trigger.
- **The fence's other firings bought nothing.** Planted: 115 escalations (114 above the fence
  from the unmodelled phase on, plus T087), 11 790 evaluations against 2 716, no value past
  7.2e-4 esd. tut05-broken: scan12 (cell × 1.05) climbed all three rungs and kept the cold one
  at the same Rwp, 0.9687, 19× its fence.
- **Option (ii) reproduces the fence's one rescue bit for bit.** On CPD's first two patterns
  with the closing stage on, 1b climbed `[warm, warm_staged]` and kept `warm_staged`,
  converged, Rwp 0.13779, 629 evaluations: the `on` arm's rungs, evaluations and
  `values_sha`. Across the eight families (ii) skips the fence's 116 idle escalations and adds
  one. Like the fence, it misses CPD 1b with the closing stage off.
- **The one it adds is Cr₂WO₆ 150 K, at 3× for nothing** (X4). The warm stage converged in 24
  evaluations and the closing stage ended `max_iter` at 800, in every arm. Under (ii) the
  pattern climbed all three rungs, each closing stage again at 800, and kept the cold rung,
  still `max_iter`, at Rwp 0.099228 against 0.099230: 2 533 evaluations against 824 (3.07×),
  47 s against 14 s, no value past 0.087 esd. Reading the warm stage's status instead escalates
  neither CPD 1b nor Cr₂WO₆.
- **Option (iii) is a projection from the JSONs, not a run.** Across the status arms, 520
  patterns kept a warm rung. `CELL_RUNAWAY` fires on exactly one of them, CPD 1b, in both
  closing configurations, and on none of trigger, tut05, planted, its null twin or Cr₂WO₆. No
  arm has escalated on it, so whether the next rung recovers CPD 1b with the closing stage off
  is unknown.
- No program restarts a pattern by itself (`docs/practice.md` § Sequential refinement, last
  paragraph), so every trigger beyond divergence is tier 3.
- The fence's median is one or two values for the first patterns (X8): accepted Rwp
  [0.30, 0.10] gives a fence of 0.25, against 0.125 for [0.10, 0.10].
- `SEQUENTIAL_RESEED` fires only when the cold rung is kept (49 on planted, 1 on tut05-broken,
  1 on Cr₂WO₆ under (ii)); CPD 1b's rescue to `warm_staged` is on `SeriesEntry.rung`,
  `.rungs_tried` and `.rwp_warm` alone.

**The case against (b).** It needs a replacement for the one rescue. (i) keeps CPD 1b's
runaway. (ii) has its own dissenter on disk: Cr₂WO₆ 150 K, a closing stage that ran out of
iterations at a good answer, restarted twice for 3.07× the evaluations; neither reading of
"unfinished" separates that from a runaway (X4). (iii) is unmeasured. And the fence's
over-firing costs evaluations, not answers, because `_prefer` keeps the lower Rwp.

**The case against (a).** Its dissenter is on disk: planted from T124 is a lasting misfit, and
the fence costs it 4.34× for nothing. Rwp tracks Rexp, so a fence on Rwp fires on falling
counts under a right model (WP-1469's 24-pattern ramp: +55 % iterations), which is why the
width screen reads GoF (`sequential.py:283-287`). And the fence misses a degraded warm fit that
stays inside it: CPD 1b with the closing stage off.

**My pick.** 1 (b) and 2 (ii): the fence becomes a reported ratio, and a warm rung escalates
when it diverged, raised, or its result ends `max_iter`. It is the one replacement measured on
all eight families, and it keeps the only rescue on disk at a fraction of the fence's cost
(planted 2 716 evaluations against 11 790; Cr₂WO₆ 2 582 against 873). One arm is still worth
running: (iii) on CPD's first two patterns with the closing stage on and off (about 40 minutes
each), then planted and Cr₂WO₆ (minutes). I would change my mind, to (iii) in place of (ii),
if that arm keeps the CPD 1b rescue with the closing stage on, also catches the degraded
closing-off fit (corundum within 1 esd of weighed), and leaves Cr₂WO₆ alone. Changed from the
draft: the draft picked (ii) "once one cheap arm is measured" and kept the fence as an opt-in
trigger at 1.25. The arm is measured; and § Demotion leaves no diagnostic where the threshold
decides existence, as 1.25 does for `SEQUENTIAL_RWP_OUTLIER`, so the fence becomes a field and
the caller names any factor of their own.

**Rows that follow.**
- 1 (b): `RESEED_FACTOR` removed. `fit:reseed_factor` loses its default and becomes the
  caller's opt-in fence (caller; the package names no number). `SEQUENTIAL_RWP_OUTLIER` and
  its suggestion removed; the statistic becomes each pattern's Rwp over the median of those
  accepted before it, under a name that asserts no verdict, replacing `SeriesEntry.rwp_fence`.
  Its `rietx.help` entry says the first patterns are judged against a median of one or two.
  `_chain.rwp_outlier_carve_out` lapses, having no default fence to carve out of.
- With any answer: `_reseed_needed` tier 3 on the trigger ruled. `SEQUENTIAL_RESEED` tier 3,
  response `warning` (the package restarted the chain), suggestion tier 1.
  `SeriesEntry.reseeded` tier 3, the record of the kept action. `fit:reseed` tier 3, the
  ladder's switch, approved with C2.
- 1 (a): every part tier 3 with approval. `RESEED_FACTOR` (1.25, no provenance) and
  `SEQUENTIAL_RWP_OUTLIER` with response `warning`. The carve-out tier 3 (an above-fence
  pattern is not quarantined; no dissenter, as it acts on no value). The fence armed only after
  a minimum of accepted patterns, as the first-rung bound waits for `FIRST_RUNG_SAMPLES` (X8).

---

## C2. The ladder, the quarantine and the kept attempt

**Stakes.** The quarantine moves every successor of a diverged pattern: none on disk (no arm on
the eight families quarantined anything; its kept case is the injected divergence at
`tests/test_sequential.py:1158`); dissenter none found. The ranking moves the pattern's own
values: on disk once, planted T087, where `_prefer` kept `warm_staged` at Rwp 0.048071 over the
truncated warm rung at 0.047958, and T087's phase scale sits 39.3 esd from the unbounded
chain's (X1, X5; the cut is C3's). Dissenter for the ranking none found; for
`on_error="carry"`, GSAS-II and MAUD, where a failure ends the chain.

**Rows.** `_ladder`, `_prefer`, `_chain.quarantine`, `_chain.on_error_carry` (all row-less),
`SeriesEntry.rung`, `.rungs_tried`, `.rungs_raised`, `SEQUENTIAL_UNRECOVERED` (+ suggestion),
`fit:on_error`, `fit:refit`. Applied already: `SERIES_PATTERN_FAILED` (+ suggestion, tier 1).

**The decision.** Two of Rule 1's four protections are here (keep the best attempt; seed no
successor from a diverged fit), judged as those protections, with their criteria still tiered.

1. Does the quarantine pass, and with it the ladder's parts: three rungs (collapsed warm
   refit, the staged plan from the warm state, the staged plan cold; `RUNGS`,
   `sequential.py:362`), that order, and giving up after the cold rung?
2. Should a finite truncated attempt beat a diverged completed one? Today `_prefer` asks
   "truncated?" before `_better` asks "diverged?" (`sequential.py:1960-1990`). Under a forced
   escalation, a diverged `warm_staged` rung is then kept over a truncated first rung with a
   finite Rwp, and the pattern is quarantined.
3. Does `max_iter` rank below `converged`? Today the two tie and Rwp decides.
4. `on_error="carry"` and `refit="single"` at tier 2, the first with its dissent named?

**Evidence.**
- The rungs cost 838-904, 1 623 and 2 863 iterations on CPD sample 1 (WP-1051,
  `sequential.py:550-555`). A diverged kept attempt seeds no successor, joins no median and
  gives no first-rung sample (`:1685-1724`). EasyDiffraction moves its start values only on a
  successful fit (checked); GSAS-II and MAUD end the chain (`docs/practice.md`).
- The record names the pattern and its rung, not the state that seeded each successor
  (`README.md` § Quarantine's record); `SeriesEntry.seeded_from` lands whatever the ruling
  (task 3).
- Question 2 has no case on disk; the one truncation, T087, escalated to a converged rung.
- Question 3 decided nothing on disk: on CPD 1b the converged rung also had the lower Rwp
  (0.1378 against 0.7652), and on Cr₂WO₆ 150 K under (ii) every rung ended `max_iter`. Since
  WP-2002 `max_iter` is the closing stage's verdict (X4), and on Cr₂WO₆ it marks a closing
  stage that ran out of iterations at a good answer.
- `on_error="carry"`: EasyDiffraction carries on past a failed file without seeding from it
  (checked). `"raise"` keeps what converged (`sequential.py:1622-1638`), so the choice is
  finishing the batch or stopping at the first failure, not lost work.
- `refit="single"`: GSAS-II and EasyDiffraction fit every pattern with one vary list
  (checked); the dissent is on cost only (trigger: staged 1 253 evaluations, collapsed 1 603).

**The case against.** The rungs and their order rest on one real family's iteration counts,
and the give-up point on an injected divergence. A refiner whose model makes the staged plan
the cheaper first rung would order it first; `refit="stages"` is that caller's way. On
question 3, a refiner ranks an unfinished fit below a finished one.

**My pick.** 1: pass. 2: yes, test `diverged` before `truncated`. No refiner keeps a diverged
fit over a finite one, and today's order quarantines a pattern that had a usable attempt.
3: keep the tie. The lower weighted residual is the better fit by the objective's definition,
and a `max_iter` status can now mean the closing stage's last iterations at a good answer;
ranking it below would keep a converged attempt at higher Rwp over it. I would change my mind
if a `max_iter` attempt with the lower Rwp is found farther from its family's reference than a
converged one. Changed from the draft: the draft ranked `max_iter` below `converged`, before X4
showed what the status now reads. 4: tier 2 each, GSAS-II's and MAUD's dissent named on
`on_error`.

**Rows that follow.** `_chain.quarantine` and `_ladder` tier 3, kind 1, grounds naming the
injected case. `SEQUENTIAL_UNRECOVERED` tier 3, response `warning`; its suggestion tier 1.
`SeriesEntry.rung`, `.rungs_tried`, `.rungs_raised` tier 3, the ladder's records. `_prefer`
tier 1 for its Rwp step; its truncated and diverged steps tier 3, in the order ruled in 2.
`fit:on_error`, `_chain.on_error_carry`, `fit:refit` tier 2. `seeded_from` tier 1, a record.
If 1 fails, the ladder becomes the caller's (`reseed=False` by default) and the quarantine
stays, since it does not depend on `reseed` (`sequential.py:1699`).

---

## C3. The first-rung budget

**Stakes.** Every value of a pattern whose winning first rung the bound cuts. On disk at the
default, 3.0, in every arm: planted T087, the blank frame, whose phase scale sits 39.3 esd from
the unbounded chain's; 4 values moved more than 1 esd and 11 more than 1e-3 esd, all T087's but
one of T088's (9.8e-4 esd). T087's distance from the planted truth was not measured. At factor
0.5 on the thermal ramp, a hidden truncation kept answers within 8e-4 esd (X1). Dissenter
named: a refiner on a chain where one pattern's winning rung costs several times its
neighbours'. T087's cost 6.7× the running maximum, against the worst ratio of 1.29 that the
constant was calibrated on (`sequential.py:198`).

**Rows.** `FIRST_RUNG_FACTOR`, `FIRST_RUNG_SAMPLES`, `fit:first_rung_factor`,
`_first_rung_budget` (row-less).

**The decision.** The record put this bound in the answer-invariant class on two chains (0 of
1 030 and 0 of 392 accepted values moved, 2.3× margin). X1 shows it is not invariant as built:

- Since the closing stage, a truncated warm stage that the closing stage then converges reads
  `converged` (`refine.py:5171`). Neither the forced escalation (`sequential.py:1563`) nor
  `_prefer` sees the truncation.
- `closing_stage()` copies the last stage's `max_iter` (`strategy/staged.py:392`), so the cap
  reaches the closing stage too, stage by stage, while the budget's sample sums the warm and
  closing stages (`sequential.py:1604`). On planted the cut fell on T087's closing stage (43
  evaluations against a cap of 32; inferred from the counts).
- With both fixed, T087's winning rung (24 + 43 evaluations) is still 6.7× the running
  maximum, past any margin at 3.0. The ratio, not the defects, breaks invariance.

So: (a) default `None`, no bound unless a caller asks, which makes `first_rung_factor` the
caller's; (b) keep 3.0 at tier 3 and judge it on the ground, since it moves values; (c) fix the
defects and raise the factor until planted is covered, then `invariant` with a biting arm in
the test. And under `reseed=False`, should a bound apply at all?

**Evidence.** Where it binds, the bound was worth 1.36× the whole chain's evaluations
(`sequential.py:1102`), measured under the fence, where a losing warm rung cost about 400. On
planted it saved 102 of 2 818 evaluations (3.6 %). Kept first rungs cost 27-64 evaluations on
trigger and 25-107 on CPD (WP-1127). Both invariance tests assert bit-identity and every kept
first rung under its budget, so they see neither outcome. Under `reseed=False` a bitten first
rung escalates anyway (`sequential.py:1563`, `:1571-1573`), against the docstring at
`:1079-1085`; on planted that is T087 in the `off` arm (X2).

**The case against (a).** It gives up WP-1127's saving where a losing rung is expensive. Under
C1's pick, though, a warm rung loses only by diverging, raising or ending `max_iter`, and a
plan-capped rung already stops at its own `max_iter`; the bound would be a second, tighter cap
on a rung that has not failed, and one that moves values.

**The case against (c).** Any factor above 6.7 is fitted to T087, the data it would be tuned
on.

**My pick.** (a), with both defects fixed so an opt-in bound does what its docstring says: read
the truncation off the rung's own stages, and cap and sample one quantity. Under
`reseed=False`, no budget (X2). Changed from the draft: the draft read X1 as fixable and kept
the class invariant; the planted arm shows the ratio is what breaks it. I would change my mind
if the fixed bound at 3.0, re-run on planted and on both invariance families, moved no accepted
value.

**Rows that follow.** (a): `fit:first_rung_factor` caller; `FIRST_RUNG_FACTOR` removed (the
caller names the factor); `FIRST_RUNG_SAMPLES` stays inside the opt-in at tier 3, or becomes a
second caller argument; `_first_rung_budget` rides the caller's row. (b): all four tier 3 with
approval, both docstrings corrected. (c): all four `invariant`, the fast test gaining planted
and an arm where the bound bites a winner.

---

## C4. The discontinuity scan

**Stakes.** No value: the scan reports, and `verify_discontinuities` refits only when asked. On
disk it flagged planted's background step (T050) and blank frame (T087), did not flag its
unmodelled phase (from T124) or its transition (T186), flagged CPD 1a → 1b with the closing
stage off (corundum's scale, where the weighed fraction goes 1.6 → 94.3 wt % by design), flagged
three steps on tut05-jump, and flagged tut05-broken only under an infinite fence. Dissenter
named: the maintainer's own example, a jump that is a transition, a sample shift, a beam dump
or a wrong model.

**Rows.** `SEQUENTIAL_DISCONTINUITY` (+ suggestion), `DISCONTINUITY_FACTOR`,
`DISCONTINUITY_SIGMA`, `MIN_POINTS_FOR_DISCONTINUITY`, `_verify_discontinuities` (row-less),
`_relative_paths` (row-less).

**The decision.**
1. Approve the demotion the WP's Context states: the code, its suggestion and its three
   constants go. The statistic becomes `SeriesResult.steps`: every step in esds, largest first,
   no threshold. Its `rietx.help` entry carries the reading (what a jump can be, and that a
   symmetry-mode refinement separates the cases), and the trajectory block gets one line naming
   it.
2. With no flagged pair left, what does `verify_discontinuities=True` refit? (i) The pairs the
   caller names. (ii) The largest *k* steps, *k* the caller's. (iii) The largest *k* with a
   package default *k*, which is a package number inside an opt-in switch and would be tiered
   here before it lands (WP Context).

**Evidence.** The thresholds (5× the median step and 3σ, from 5 points; `sequential.py:228-229`,
`:249`; no measurement) decide whether the diagnostic exists, so § Demotion leaves none. Three
readers of the flagged pairs move: `SeriesResult.discontinuities`, the trajectory plot's
shading, and `_verify_discontinuities` (`sequential.py:1813-1903`). The cold-refit ratio lives
in the removed code's `Diagnostic.value`, so it needs a field (`SeriesStep.cold_ratio`, name to
choose). Each verify refit pays the automatic profile interval (X10; a fix below).
`_relative_paths` is arithmetic.

**The case against.** Agents stop on stated criteria (v1.3: 7 of 8), and `steps` states none.
The record's answer: a contested demotion is measured on agents and lands whatever the result,
the explanation reworked if the result is poor.

**My pick.** 1: yes. 2: (i) or (ii), both the caller's; not (iii). Unchanged from the draft.

**Rows that follow.** `SEQUENTIAL_DISCONTINUITY`, its suggestion and the three constants
removed, the reading moving to the help entry of `SeriesResult.steps` (tier 1, a record).
`_verify_discontinuities` caller; `_relative_paths` tier 1; `fit:verify_discontinuities`
re-read as caller once 2 lands. If 1 is refused, the three constants are tier 3 and owe the
mechanical ground, which two real families cannot meet.

---

## C5. Path dependence

**Stakes.** No value: the reported entries are the forward chain's either way. None on disk in
this WP's reseed arms, which ran no `direction="both"`; on three synthetic families the largest
gap was 0.351σ (trigger, `phases.1.lor_strain`), with no flag (X12). Dissenter named: a refiner
reading n paths × m patterns at 3σ, where chance flags are expected; the largest flags on record
were axis relabellings (81.5σ in Fddd, `docs/skill/rietx/references/series.md:136-150`).

**Rows.** `PATH_DEPENDENCE_SIGMA`, `SEQUENTIAL_PATH_DEPENDENT` (+ suggestion). Applied already:
`NOISE_FLOOR_REL` (tier 1), `SEQUENTIAL_PATH_CHECK_INCOMPLETE` (+ suggestion, caller).

**The decision.** The switch is the caller's (`fit:direction`, caller since 2026-10-24), but 3σ
is a package number used once it is on. It has no provenance (`sequential.py:245`) and decides
whether the code exists. 1: approve demoting it to a record field of each path's
forward-backward gap in combined esds, per pattern, largest first, with each walk's `rung`
beside each gap (X15: one pattern can be kept cold in one walk and warm in the other, and the
gap then measures the ladder). 2: split `SEQUENTIAL_PATH_CHECK_INCOMPLETE` into a `warning`
code (the comparison did not run) and an `info` one (it ran on fewer patterns), so each takes
one literal response.

**Evidence.** X12: with the closing stage the gaps shrink 17× and 37× on the two toy ramps and
7 % on trigger, at 1.2-1.35× the evaluations; no flag appears or vanishes. CPD with
`direction="both"` was not run (about two hours an arm). X15 is unmeasured; planted with
`direction="both"` would test it (about five minutes an arm).

**The case against.** As C4's: a field states no criterion to stop on.

**My pick.** 1 and 2: yes. Unchanged from the draft, plus the `rung` column from X15.

**Rows that follow.** `SEQUENTIAL_PATH_DEPENDENT` and `PATH_DEPENDENCE_SIGMA` removed; the
suggestion's three alternatives move to the field's help entry; the field tier 1.
`fit:direction` stays caller. If 1 is refused: 3σ tier 3 with approval, the code at response
`warning`.

---

## C6. The persistent-finding summary

**Stakes.** No value. It fired 34 times on trigger, 26 on CPD with the closing stage on, 25
with it off, twice on each tut05 family, and never on planted or its twin. On planted,
`FLOOR_HIT` fired on 63 of 248 patterns, 62 of them from T124 on, where the unmodelled phase is
planted; at 25 % the summary stays silent (whether those hits are the impurity's doing was not
traced). Dissenter named: a refiner whose impurity appears in the last 40 % of a ramp, hidden
by "more than half".

**Rows.** `SEQUENTIAL_PERSISTENT_FINDING` (+ suggestion), `MIN_POINTS_FOR_PERSISTENCE`,
`_persistent_diagnostics.half` (row-less), `NOT_A_SERIES_FINDING` (row-less).

**The decision.** The count is arithmetic. The half cut and the five-pattern minimum
(`sequential.py:256`, `_persistent_diagnostics` at `:2445`) decide whether the code exists, and
its level is the worst occurrence's, computed at run time (`:2505`), so it can take no literal
response. Approve demoting it to a record field of counts: each per-pattern code and path with
its count, n and worst level, largest first, and one report line per top count naming the code
and the path?

**Evidence.** Origin: WP-1110's 68-pattern series, 425 `BOUND_HIT` read as "42 of 68". The
field also answers the WP's one-line-form cost: with no deliverable the code prints as one line
that no longer says which per-pattern code persisted (tutorial 05, cells 19 and 34). The
suggestion ("change the model or the plan") also fires on a declared `info` choice.

**The case against.** "42 of 68" is a stated criterion agents act on, and the field states
none. A contested demotion of a stated criterion runs the agent harness before it lands.

**My pick.** Demote, after the agent harness. Unchanged from the draft.

**Rows that follow.** The code, its suggestion, `MIN_POINTS_FOR_PERSISTENCE` and the half cut
removed; the field tier 1. If the code stays: the half cut and the minimum tier 3 with
approval, and `NOT_A_SERIES_FINDING` tier 1 by its own rule.

---

## C7. Width growth (a ruling for WP-2004)

**Stakes.** No value. Silent on CPD (real); fires on issue #451's synthetic soak; #451's
operando chain is not on disk. Dissenter named: a refiner whose strain grows for real while
GoF rises for a second, independent reason; the suggestion names only the missing component.

**Rows.** `SEQUENTIAL_WIDTH_GROWTH` (+ suggestion), `WIDTH_GROWTH_FACTOR`,
`WIDTH_GROWTH_GOF_FACTOR`, `WIDTH_GROWTH_SIGMA` (`sequential.py:281`, `:299`, `:305`),
`_WIDTH_SUFFIXES` (row-less, tier 1).

**The decision.** Three tier-3 thresholds decide whether the code exists, on one real family.
Hand WP-2004 the ruling that it becomes a record field: per phase width, its ratio to its first
measured value with that ratio's esd, the growth in esds, the GoF ratio and the pattern's
`rung`, largest first, with a help entry naming both readings?

**Evidence.** X6: on the soak, three trigger arms. With the fence on, all four soaked patterns
climbed all three rungs (254 evaluations against 71), and every value lay within 5.1e-5 esd of
the other arms; the finding was identical in all three (3.6× from fB = 0.00 to 0.10 with GoF
3.1×, 6.8× at 0.20). The ladder can only lower a pattern's GoF, so it cannot create a finding.

**My pick.** Yes; the three constants go to WP-2004's `### Inherited` with that ruling, and
nothing is bumped here. Unchanged from the draft, plus the `rung` column from X6.

**Rows that follow.** The code, its suggestion and the three constants are WP-2004's to remove
under `THRESHOLDS_VERSION`; their rows record the ruling and the hand-off. `_WIDTH_SUFFIXES`
tier 1, no row.

---

## C8. The moment carry (rare feature)

**Stakes.** The floor moves a successor's starting modulus, never an entry's own value. None on
disk: Cr₂WO₆ 150 K fires `SEQUENTIAL_MOMENT_HOLD` in every arm, but it is the last pattern and
seeds no successor. Dissenter none found (an ascent out of the floor terminates at once,
`tests/test_magnetic_series.py:23-27`).

**Rows.** `_floor_unsupported_moments` (row-less), `SEQUENTIAL_MOMENT_HOLD` (+ suggestion),
`SEQUENTIAL_MOMENT_ONSET` (+ suggestion).

**The decision.** 1: does the floor pass under the rare-feature clause (one synthetic ramp, one
real neutron pair), tier 3 with grounds saying so? 2: split `SEQUENTIAL_MOMENT_ONSET`, which
raises at a computed level and again through `model_copy` (`sequential.py:2699`, `:2784-2858`),
into an `info` bracket and a `warning` code for an unconverged supported side or two chains
that disagree?

**Evidence.** `floored[k]` is written at the start of pattern k, before its ladder runs
(`sequential.py:1531-1532`). If k then keeps its cold rung, which starts from the initial
models, `floored` still lists it and `SEQUENTIAL_MOMENT_HOLD`'s "reseeded to its floor on N
successor patterns" counts it (`:2656-2674`; X7). A quarantined pattern's moments seed nothing:
the floor passes through it to the next pattern (comment `:1495-1501`). No test combines a
floor with an escalation or a quarantine.

**My pick.** 1 and 2: yes. `SeriesEntry.floored` (task 3) is set where the kept attempt started
from the floor, so the message can stop cutting its list at four labels (`:2666-2673`).
Unchanged from the draft, plus X7's placement of `floored`. Test to add: the magnetic ramp with
an injected divergence on the pattern after an unsupported one.

**Rows that follow.** `_floor_unsupported_moments` tier 3, rare feature, keyed on
`SeriesEntry.floored` (tier 1, a record). `SEQUENTIAL_MOMENT_HOLD` tier 3, response `warning`;
its suggestion tier 1. `SEQUENTIAL_MOMENT_ONSET` split: the bracket tier 1, response `info`
(read off the per-pattern verdicts, never the values); the warning half tier 3 on WP-2004's
`MOMENT_SUPPORT_SIGMA`. If 1 fails, the floor goes and a successor warm-starts from the
unsupported modulus, reported through the onset bracket.

---

## C9. The carry policy and the closing stage on a warm refit

**Stakes.** The warm start moves every value of a chain. On CPD with the closing stage on, the
chain sits 7.05-14.2 esd from the independent fits, the worst path a `lor_strain` each time
(the 2026-10-24 handover); CPD 1b, even escalated, sits 8.7 esd from its independent fit on
corundum's `lor_strain`. The closing stage on a warm refit made CPD 1b's runaway (X3).
Dissenter named: GSAS-II's default, where each histogram starts from its own values unless
`Copy2Next` is ticked.

**Rows.** `refine_sequential:carry`, `:carry_hkl_intensities`, `fit:plan`, `_carry_into`,
`_reanchor_carried`, `_carry_variables`, `_collapse`, `_fit_one.declared_wavelengths` (the last
five row-less). Applied already: `fit:mode`, `fit:two_theta_limits` (tier 2).

**The decision.**
1. `carry=("*",)` at tier 2, GSAS-II's dissent named and approved as the series verb's own act?
2. `carry_hkl_intensities=True` at tier 3, pending a Le Bail and a Pawley chain run carried and
   not?
3. `fit:plan` at tier 3, by extending B7's approval to the series seat?
4. Does a warm refit run the closing stage (`_collapse`, `sequential.py:470`, carrying
   `closing_window_tol`)? (a) Yes, as today. (b) No.

**Evidence.**
- The warm start is EasyDiffraction's (checked) and FullProf's cyclic mode's (inferred).
  rietx carries every entry where GSAS-II and EasyDiffraction carry the varied ones; the two
  differ only where a fixed value changes during the chain. No program carries extracted
  intensities by default; GSAS-II does under its opt-in `Copy2Next` (`docs/practice.md`).
- Question 4, from X3: with the closing stage, CPD 1b's warm stage stopped at 136 evaluations
  (at `intermediate_ftol` 1e-6) and the closing stage ran away from there; without it, the warm
  stage ran 410 evaluations at 1e-9 to a degraded fit that no trigger catches (C1). X12: the
  closing stage narrows the path-dependence gaps (17×, 37×, 7 %) at 1.2-1.35× the evaluations.
  X13: `intermediate_ftol` adds at most 2.7e-4 esd along three synthetic chains, set by pattern
  0 and not amplified. Whether the looser warm stop is what let the closing stage run away on
  CPD is X13's open arm: CPD's first two patterns, closing on, `intermediate_ftol=None` (about
  40 minutes). The closing stage's cost along a chain is WP-2036's.
- X11: with the width twin hold, a chain carrying everything but the scales averages Rwp 0.1282
  on CPD 1a-1h, against 0.1256 carrying everything and 0.1258 independent (a strict xfail,
  `tests/test_acceptance_sequential.py:229-259`). Values and fractions were not compared. The
  default carry is not the one that degrades; a caller's narrower carry is.

**The case against.** For 4 (b): the closing stage is what every single fit now ends with, and
dropping it from the warm refit leaves CPD 1b degraded and uncaught. For 4 (a): it is what made
the runaway, and its chain cost is unmeasured.

**My pick.** 1: yes. 2: tier 3, pending. 3: yes. 4: (a), recorded after X13's CPD arm. Under
C1 (ii), 4 (a) is also what makes CPD 1b catchable at all: with the closing stage the bad warm
rung ends `max_iter` and escalates to the rescue; without it, it converges degraded and no
measured trigger sees it. Changed from the draft: the draft left the closing stage's row to
WP-2036; X3 and the CPD `status_maxiter` arm tie it to C1's ruling. For
X11, measure QPA against weighed for the two carry policies on CPD 1a-1h (about an hour an arm)
before touching the twin hold. Candidate design: on a chain, hold the twin columns at pattern
0's instrument-only value, the series form of fixing the instrument from a standard
(`docs/practice.md` § Instrument and specimen widths refined together).

**Rows that follow.** `carry` tier 2; `_carry_into` tier 2 with it, keyed on `seeded_from`;
`carry_hkl_intensities` tier 3; `fit:plan` tier 3 on B7's approval; `_reanchor_carried`,
`_carry_variables` and `declared_wavelengths` tier 1, no row (no choice beyond `carry`'s, or a
diagnostic's reference); `_collapse` tier 3 for its details (no stage seed, the plan's largest
`max_iter`, the closing stage carried), after the two arms. If 4 (b): `_collapse` drops
`closing_window_tol`, and every chain number in this batch measured with the closing stage on
is re-run.

---

## C10. The joint fit

**Stakes.** The joint holds move the shared columns they hold. None on disk beyond the
synthetic fixtures; dissenter none found beyond those of the 2002 rulings they inherit.

**Rows.** Proposed with a row: `PARAMETRIC_TARGET_UNSEEN` (tier 3 on B1's threshold, response
`warning`), `PARAMETRIC_FORM_REJECTED` (tier 2 on `FORM_TEST_LEVEL` once X14 is measured,
response `warning`), and their suggestions (tier 1). Sixteen row-less entries. Applied already:
`SIZE_NORMALISED_ACROSS_WAVELENGTHS` and `STAGE_FREED_NOTHING` (tier 1), `PARAMETRIC_OUT_OF_RANGE`
(caller), each with its suggestion.

**The decision.** Confirm that 2002's rows cover the joint holds, each of which writes the
single runner's record field: `_hold_unsupported_phases_multi` → `StageResult.held` (B1,
approved 2026-10-23); `_rehold_multi` → `released`, `collapsed` (B1); `_hold_scale_b_ridges_multi`
→ `scale_b_held` (tier 1); `_hold_flat_moments_multi` → `moment_flat_axes` (tier 1) and
`moment_turned` (B2); `_hold_width_twins_multi` → `width_twins_held` (approved 2026-10-23);
`_reset_cell_runaway_multi` → `cell_reset` (B8); `_run_plan.seed` → `seeded` (approved
2026-10-21); `_freeze_cell_windows_multi` → the single runner's cell-window row (B8, approved
2026-10-20). The joint fit refuses Le Bail and Pawley, so no force-fix exists here.

**Evidence.** Tier 1, no row: `size_value_scales` (Scherrer), `bound_intersection` (a shared
column satisfies every histogram's box), `_joint_unmeasured_phases` (the joint face of
`RefinementResult.qpa`'s row), `_freeze_strain_cap_multi` (the strain cap's rule over the
union of ranges; no test names it). `fit:weights` (1.0: the joint χ² is the sum of each
histogram's own) and `SharingMap.is_shared` (Von Dreele 1997, cited at `multi.py:6`, not read
here) sit at no `DEFAULT_SEATS` seat. `_ticks.extra_components` decides nothing.
`_parametric_form_tests.at_bound_hold` (tier 3) holds `staged.bound_findings`' columns on their
bounds in both fits of the form test (`multi.py:2422-2444`); a joint fit can pass
`BVLS_MAX_COLUMNS` (128) and leave the exact active set, where B16's margin was not measured
(X14).

**My pick.** Covered as listed; `PARAMETRIC_FORM_REJECTED` and `at_bound_hold` wait for X14's
measurement (a joint parametric fit above 128 columns, its at-bound set checked against a
≤ 128-column refit of the same problem). The `vars.X` escape is a fix below; the support
statistic and the Stephens seed are findings in the appendix.

**Rows that follow.** The eight holds `covered`, no row of their own. The four tier-1 entries
no row. `PARAMETRIC_TARGET_UNSEEN` tier 3, response `warning`. `fit:weights` and `is_shared`:
a hand row each, or a `DEFAULT_SEATS` seat for `MultiHistogramRefinement.fit`.

---

## C11. Caller and invariant rows

**Stakes.** None: no reported value moves. Dissenter none found.

**Rows.** Proposed: `fit:x`, `fit:x_label`, `fit:labels`. Already tiered: the eleven caller rows
of 2026-10-24 and, applied, `SEQUENTIAL_CANCELLED` (+ suggestion), `fit:prepare`,
`fit:constrain`.

**The decision.** `x`, `x_label` and `labels` are `invariant` once an arm each joins
`test_a_series_observed_is_the_series_unobserved` (`tests/test_answer_invariant_defaults.py:171`);
`labels` needs a label-blind compare, since `chain_answer` carries the labels.

**My pick.** Yes. `fit:direction` and `fit:verify_discontinuities` are re-read when C5 and C4
land.

---

## Fixes that need no ruling

Each contradicts the package's own docstring or invariant and moves no reported value. Where a
fix would move one, it is in its class instead: no budget under `reseed=False` and the two
budget defects (C3), `diverged` before `truncated` in `_prefer` (C2), and aligning the joint
fit's support statistic (appendix).

1. **`first_rung_factor`'s docstring and `FIRST_RUNG_FACTOR`'s comment.** "A bound that bites
   costs an escalation and never an answer" (`sequential.py:1104-1107`) and "cannot reach the
   answer" (`:202-212`) are false twice: a hidden truncation costs no escalation (X1, outcome
   1) and planted T087 cost an answer. Rewritten to whatever C3 rules. Moves nothing.
2. **`reseed`'s docstring** (`sequential.py:1079-1085`): "Switching it off leaves each pattern
   with its first rung" is broken by the forced escalation (X2). Rewritten with C3's answer.
   Moves nothing by itself.
3. **`_ladder`'s and `_better`'s docstrings** (`sequential.py:559-561`, `:1961`) say
   "convergence first"; `_better` prefers a non-diverged fit, and `max_iter` ties `converged`
   (X5). `docs/practice.md`'s rietx row says the same ("convergence before Rwp"). Moves
   nothing.
4. **`reseed_factor` is not validated** (`sequential.py:1030`). `inf` or `nan` turns off the
   fence, `SEQUENTIAL_RWP_OUTLIER` and the scan's above-fence drop together (X9: four outlier
   findings to none on the soak, a discontinuity gained on tut05-broken); zero or a negative
   factor escalates every warm rung. Refuse non-finite and non-positive values. It lands with
   C1's answer, since today `inf` is the only way to ask for status-only (the measurement uses
   it); under C1 (b) the parameter loses its default anyway, and any floor above zero is C1's.
5. **Every rejected rung and every verify refit pays the automatic profile interval** (X10).
   `_fit_one` builds a plain `Refinement`, whose `_auto_intervals` defaults to `True`
   (`refine.py:2334`); the trial path sets it `False` (`:2608`); `sequential.py` never mentions
   it. Cr₂WO₆ 4 K: 49 evaluations recorded against 270 run, in 31 solver calls; 150 K under
   (ii): 2 533 against 2 681. Set it `False` in `_fit_one` and run
   `attach_stationary_intervals` once on the kept attempt after the ladder decides. The interval
   never moves a value (`refine.py:5199-5208`); the test should assert the kept attempt's
   interval is unchanged.
6. **A `vars.X`-driven cell escape in a joint fit is neither reset nor named.**
   `_cell_runaway_diagnostic(cell_runaway)` at `multi.py:1632` never folds
   `refine._vars_driven_cell_escapes` (`refine.py:1705`), which the single runner folds into
   `CELL_RUNAWAY` at `refine.py:4481` and `:4711`. The single runner names such an escape and
   never resets it, since resetting the driver would move whatever else it drives
   (`refine.py:1664-1670`). Folding it in the joint fit adds a finding and moves no value.
7. **`SEQUENTIAL_MOMENT_HOLD` overcounts** (X7): it counts a floored pattern whose kept attempt
   started cold (`sequential.py:2656-2674`, `floored[k]` written at `:1531-1532`), and cuts its
   list at four labels (`:2666-2673`). Fixed by setting `SeriesEntry.floored` on the kept
   attempt (C8) and reading the message from it. Moves nothing.

---

## Appendix: findings that are not decisions

- **`SeriesEntry.n_iterations` leaves out the interval refits** (X10): Cr₂WO₆ 4 K records 49
  against 270 evaluations run. Every evaluation count in this batch is the recorded one, so
  real cost is higher wherever an interval ran (any pattern with a stationary moment angle).
- **The joint runner judges support by `CompiledModel.phase_support`** (`multi.py:413-417`), never
  by WP-1523's scale significance, so the two runners call a phase unseen by different
  statistics under one ruling (B1). Aligning them would move which phases a joint fit holds, so
  it is a ruling when proposed, owed with B1's second pass; no joint case on disk differs.
- **The joint runner seeds no Stephens block** where the single runner does
  (`Stage.strain_seed`; WP Context).
- **CPD 1b with the closing stage off reports its majority phase with its cell held.** Corundum,
  94.84(27) wt %, has no cell rows in the warm rung's result, and `PHASE_UNCONSTRAINED` fires. The
  warm start carries scales from 1a, where corundum is 1.6 wt %. Not traced; if the support test
  at the warm stage's start is reading the carried scale, it is a carry × absent-phase-hold clash
  the clash table does not list.
- **The middle rung's Rwp is recorded nowhere** (`rwp_of` is local, `sequential.py:1545`); only
  the first rung's (`rwp_warm`) and the kept one's are.

Line numbers are this tree's at `dd13648`, where `src/` matches `clashes.md`'s `ded5c3f`;
`classes.md`'s have drifted by a few lines.

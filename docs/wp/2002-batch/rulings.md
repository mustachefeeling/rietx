# WP-2002 rulings, and the second round of briefs

The maintainer answered the batch (`batch.md`) on 2026-10-19. Four classes are ruled and
B1 is confirmed. For nine items the answer was a question back. This file records the
rulings, then the plain-language briefs written in reply to those questions. The briefs
are the text the maintainer read before answering. The next session reads the answers
against this wording. Three picks changed from `batch.md`'s revised picks: B4 (keep f), B5
(drop and report) and B9 (a "geometry not stated" state). Each is marked.

"Second pass" means measuring a threshold on three unrelated dataset families after the
ruling (`batch.md`, opening paragraph).

## Rulings received (2026-10-19)

- **B1** (absent-phase hold, release, collapse restore): confirmed ("yes I think"), with
  a request to restate what the hold is. The restatement is below; it changes nothing.
  `PHASE_SUPPORT_SIGMA` stays tier 3 for the second pass.
- **B7** (default plan): the declared geometry picks the plan. "If the user knows it's BB
  geometry, that information should lead to the preset. If unknown, we should not free
  factors which might not be appropriate for a given refinement." So a Bragg-Brentano
  instrument gets displacement freed with the zero, and an unknown geometry gets
  `mccusker_default`, which frees nothing geometry-specific. It is built in a follow-up
  WP, not yet filed (see B9's geometry question). That WP must keep a calibrated
  instrument's Kα2 ratio and axial terms fixed, since `lab_bragg_brentano` frees those.
  The intermediate-tolerance half of B7 was not asked separately: the batch's option 1
  (invariance test in plain esds) stands as the plan.
- **B10** (numerical settings): "yes, tier 1". A numerical setting is tier 1 when a test
  bounds its error over the claimed domain. The six solver-path switches stay tier 3
  until refits of three families on either side give one answer. One sentence goes into
  `docs/milestones/generality.md` § The rule, under tier 1.
- **B12** (pick and opt-in verbs): "yes to all". 1(a) `auto_background` returns its
  evidence beside the pick. 2(a) `solve_magnetic` uses N/f². 2(b) its R tie-break is
  dropped, so a ΔBIC tie abstains. 3(a) `profile_fraction`'s warning becomes an info
  record. The skill's instruction is a default path. The four ΔBIC rows stay tier 3, and
  `SOLVE_D_MIN` goes to a form-factor follow-up (the revised pick).
- **B14** (hand rows): option 3, "yes if I understand correctly: you want to make more
  variables visible to the demotion tests?". The reply corrected the reading. The test is
  the audit table's own (`tests/test_audit_table.py`), and demotion is a separate step.
  The substance the maintainer agreed to is unchanged. The next session should confirm
  in a line that the yes stands.

## Rulings received, second round (2026-10-19)

- **B4**: option 1. "We should report the more accurate number, but also report the one
  comparable to other codes." f stays on every reported esd, and the textbook esd is
  reported beside it. The manual must explain the two numbers plainly, with a comparison
  against GSAS-II, FullProf (SCOR) and TOPAS, and the "switching from another code" pages
  must say it too.
- **B3**: Suortti seed agreed (two-start test, then GSAS-II's 0 unless 0.3 is closer to a
  reference). Stephens seed agreed (tier 3 until a second dataset compares the starts; the
  seed recorded in the result).
- **B8, cell clamp**: agreed. On a runaway the cell goes back to its stage-start value and
  is held for that stage, with a record entry.
- **B9, limits**: "no need to impose chosen limits on quantities that remain physical.
  Unlimited occupancy is fine. We can give a warning. The flexibility can be useful." So
  occupancy loses its 1.5 ceiling and a warning fires above 1. The session reads the
  principle as covering March-Dollase r too: its 0.15 floor goes, and r keeps only the
  pole floor `MARCH_R_MIN`. A limit that keeps a value physical or away from a pole stays.
- **B9, geometry**: a "geometry not stated" state, which also tells the user to state the
  geometry. It joins the B7 follow-up WP.
- **B11**: agreed (Le Bail converge-with-cap in WP-1542; budgets treated as not affecting
  the answer once a test confirms the margin under both solvers).
- **B16**: agreed (both numbers tier 3, a third dataset under TRF in the second pass).
- **B1**: "yes, but it should be an option, not mandatory. A caller should be able to set a
  different threshold." Asked whether other codes do this.

Asked back, answered in § Third round below: B5 (what is accurate, the root cause, other
codes), B8's cell window (tier 2?) and size floor (a warning instead?), B7 (does the
session agree with the geometry take?), B2 (is the turn common enough to keep; is the
stationary-angle test a demotion?). Not yet answered: B6, B13, B15, and the B14 confirmation.

## Rulings received, third round (2026-10-19)

Answers to § Third round below.

- **B5**: "usually this is often not a big deal, as the other codes evidently show. We
  should fix anything obviously wrong, warn during ingestion, and give the option to
  correct. Don't spend too much effort on this." So option 4's classifier is not built.
  The obviously wrong part is today's floor, which hands a σ ≤ 0 channel about a million
  times its neighbours' weight. The ruling as the lead reads it: a σ ≤ 0 channel takes no
  weight by default (GSAS-II's fxye rule), the reader warns with the count and the lines,
  and a reader option keeps such channels at σ of one count instead. Built in WP-1952,
  forwarded there.
- **B1**: on by default. The threshold and an off switch become a caller's option
  (`phase_support_sigma`, a plan field, `None` for off).
- **B2**: keep the turn (tier 3, approved). The stationary-angle test was first ruled a
  demotion on a brief that misstated its cost. The session then found two errors in that
  brief (WP-1929's record): without the test the moment sizes' esds become stopping-point
  artefacts (0.0015 and 0.0011 μB with the angle columns left out; 0.031 and 0.159 μB with
  them in, and 0.0035 to 0.47 μB as the convergence tolerance moved), and near the
  direction the ordinary esd can exclude the symmetric direction when the χ² ridge to it is
  too low to. Re-asked, ruled **option 2** (2026-10-19): keep the test and its effect on
  the other esds; the angle reports its distance from the symmetric direction with the
  likelihood interval (`profile_interval`, run automatically on the answer-producing stage
  for each angle the test passes) in place of no esd.
- **B7**: agreed, with the two additions; in WP-2015.
- **B8**: agreed. The cell window is tier 2 (TOPAS, Tech Ref § 2.17). The 2 nm size floor
  is removed; the range backstop stays; `SIZE_UNUSUALLY_SMALL`'s message gains the
  Bragg-model caveat.
- **B9**: the reading is correct for March r. Its 0.15 floor goes, `MARCH_R_MIN` stays.
- **B6**: yes. **B13**: yes. **B15**: yes.
- **B14**: asked to explain again, and re-explained in the session (the table's scanner
  sees module-level numbers, listed seats and record fields; option 3 lifts what a retune
  could turn into a different answer). Asked whether option 1 was better, the lead said
  no: the scanner still misses the next inline number, so option 1 is complete only for
  today's 91, and its ~50 extra rows are guards that dilute review. The risk in option 3
  is misclassification; the list of ~50 goes to the generality reviewer at handover, and a
  flagged row moves to the lifted set. **Option 3 confirmed** (2026-10-20). The lead would
  switch to option 1 if that review finds several misclassified rows.

## Rulings received, fourth round (2026-10-20)

The previous session's handover left five questions and three confirmations. This round's
briefs are in the session transcript; the measurements behind them are summarised here.

- **Confirmations.** The emission-line weight widening stands, and so does the rename of
  `QPA_FRACTION_UNDETERMINED` to `QPA_FRACTION_RANGE`. The interval's cost was re-explained
  and is not yet confirmed.
- **The peak-position limits** (zero shift ±0.5°, displacement and both capillary offsets
  ±1 mm, transparency ≤ 0.05). Asked "check other codes": GSAS-II 5.8.4 and FullProf set no
  default limit on any of them, and TOPAS v9's Table 2-1 has no row for them (its macros'
  own limits, in `Topas.inc`, are not on this machine). The brief recommended keeping them,
  saying a removal traded a flagged 1117 ppm cell error for an unflagged 5129 ppm one. The
  maintainer: "This sounds like the type of overfitting we're trying to avoid. Shouldn't we
  not limit, but loudly report degeneracies?" Measured in reply (11-BM NAC, zero and both
  capillary offsets free, R = 1000 mm): bounded, the cell lands −1097 ppm from the
  acceptance band's centre with an esd of 2612 ppm and seven warnings; unbounded, −5109 ppm
  with an esd of 2579 ppm and six warnings, among them two `FLAT_DIRECTION` findings naming
  the cell and an offset. So the brief's "unflagged" was wrong, and the bound only made the
  cell look 4.6 times closer than the data support. **Removed**: the four position
  corrections are unbounded; transparency keeps its physical floor of 0.
- **The TCHZ width limits.** "Keep until next session. Check what other codes do." Checked:
  GSAS-II and FullProf bound none of U, V, W, X, Y; GSAS-II floors the computed Gaussian
  variance and Lorentzian width at each reflection, as rietx does; FullProf substitutes a
  default width when one goes negative; TOPAS's table has no TCHZ row. Next session.
- **`auto_background`'s pick**: option 1, keep the pick at tier 3. Measured before asking:
  the hump score separates lab from synchrotron data rather than detecting a hump (0.10-2.3
  on all 25 lab patterns, 0.036-0.067 on five synchrotron or low-background ones), and on
  seven real patterns refitted four ways no near-trigger choice moved a cell, scale or Biso
  past 0.8 esd. The one choice that mattered (FAP's air term left out, score 0.75) is one the
  pick does not make, and `AIR_SCATTER_UNDECLARED` fires when it is made.
- **Mike Gaultois's second read of the batch** (PR #1050, 2026-10-20): agreed. The cell
  window goes to tier 3 (TOPAS bounds every phase's cell each iteration; rietx bounds a
  barely-seen phase's once per stage, ten iterations' worth). Two premises it named are
  checked: TOPAS's default occupancy limit is 0 to 2·Val + 1 (Table 2-1), so the B9 brief's
  "no default occupancy limit is recalled" was wrong and the removal stands on the
  principle alone; the 0.3-10 000 nm size range is in v9 § 2.17's prose about `CS_L`, not in
  its table, so the citation holds for v9.
- **Answered the same day** (three short questions after the briefs): `OCCUPANCY_ABOVE_ONE`
  is an info record, with no significance gate; every ΔBIC tie in `solve_magnetic`
  abstains, the tied classes listed fewest moment parameters first; the stationary angle's
  automatic interval stays automatic at 20-32 refits an angle. All three as recommended.
- **Two re-tiers the generality reviewer asked for, approved the same day ("yes", "yes").**
  The twelve solver stop constants (Coelho's LM rules `_M_HI`, `_M_LO`, `_Q_TRIGGER`,
  `_Q_WINDOW`, `_LAMBDA_FAIL_FACTOR`, `_LAMBDA_FAIL_FLOOR`, `lm._CONVERGED_RUNS`; BCCG's
  `_CONVERGED_FRACTION`, `_CONVERGED_RUNS`, `_SMALL_FACTOR`, `_SMALL_RUNS`; `_CAUCHY_ARMIJO`)
  move from tier 2 to tier 3 with refits of three families on either side owed, as B10's
  switches. `DENSE_JACOBIAN_MAX_BYTES` joins the six as the seventh solver-path switch.
  `SCHERRER_K`, `BOND_SLACK_ANG` and `STEPS_PER_FWHM_*`, which the reviewer listed beside
  them, were not asked and stay at tier 2 for the second pass.

## Still open (first round's list, kept for the record)

1. B4: keep f, and report the textbook esd beside it?
2. B5: drop and report zero and negative esds, built in WP-1952?
3. B8: count and then remove the window; put the cell back and hold it after a runaway;
   keep the 2 nm floor?
4. B9: the reading below, plus a "geometry not stated" state in the B7 follow-up?
5. B2, B3, B11, B16: as recommended below?
6. B6, B13, B15: yes?

---

## B4. Which esd is scientifically accurate (pick changed)

**The decision.** Whether rietx keeps multiplying every reported esd by the Bérar-Lelann
factor f. The batch recommended stopping. Asked what is scientifically accurate, the
second-round pick is to keep it.

**Context.** The textbook least-squares esd assumes each point's residual is independent
of its neighbours. Rietveld residuals are not independent. When the model misfits a
peak's shape, the misfit runs across many consecutive points with the same sign. Two
things follow.

The textbook esd is too small. It counts each point as separate information.

It also depends on how finely you stepped. Collect the same total counts in steps half as
wide. The summed misfit over the peak stays the same, but the point count doubles. χ²_red
halves, and every esd shrinks by √2, though the specimen and the information are
unchanged. That is arithmetic from the formula. Hill & Madsen (1984, J. Appl. Cryst. 17,
297) reported the step-width effect (recalled). Fine-stepped synchrotron scans show it
most: the 11-BM NAC example has 22 003 points against 132 reflections.

f measures how often neighbouring residuals share a sign, and scales the esd up to
compensate. Measured values are 1.13 on residuals with no correlation, 2.15 on the FAP lab
example and 8.07 on NAC. The 1.13 is a known property of the paper's formula, because
same-sign neighbours happen by chance (`optimize/statistics.py`, `berar_lelann_factor`'s
docstring). So on a perfect fit, rietx's esds are 13 % above the textbook value.

Neither number covers systematic error. With f applied, SRM 660c's refined cell still sits
4.9 esds from its certificate. Without f it would sit 4.9 × f esds away.

**Aim.** Report the esd closest to the true uncertainty, and keep a comparison with
GSAS-II easy.

**Options.**
1. Keep f, and report the textbook esd beside it. Today's esds do not change. A user
   comparing with GSAS-II reads one more field. Cost: one field and its writer. Undoable.
2. Stop multiplying, and report f beside the esd (the batch's pick). Every esd shrinks by
   1/f: to 0.89 of today's on uncorrelated residuals, 0.47 on FAP, 0.12 on NAC. Esd
   goldens are re-pinned, and the bound test's margin (B16) is re-measured. Undoable.
3. Do nothing. Esds stay as they are, and nothing tells a GSAS-II user why rietx's are
   larger.

**Practice.** GSAS-II 5.8.4 does not apply it. Its esds are the covariance times GOF²
(source checked by the first session). FullProf computes the same factor as SCOR and
leaves its own esds unmultiplied. It then prints "A better estimate of the accuracy of
structural parameters is obtained multiplying sigmas by the parameter SCOR" (the binary's
strings, checked by the first session). TOPAS was not checked. Bérar & Lelann (1991,
J. Appl. Cryst. 24, 1) and McCusker et al. (1999) are not in the Zotero library (searched
2026-10-19). So practice computes f and leaves the multiplication to the user, and
FullProf's own advice is to multiply.

**Recommendation.** Option 1. On correlated residuals the textbook esd is too small, by an
amount set by the step size. That error has a known direction, and f corrects most of it.
The batch picked option 2 because GSAS-II users would dissent. That is a question of
convention, and the extra field answers it. It stays at tier 3 on the maintainer's dated
approval, since GSAS-II does not do it by default.

The strongest case against: f is one number for every parameter, while correlation affects
a peak position and a scale differently. It also overstates by 13 % when there is no
correlation. The pick would change if repeated scans of one specimen scatter by about the
textbook esd. That is the direct test of a precision estimate, and no such set is on disk.

---

## B5. What a zero esd should become (pick changed)

**The decision.** What rietx does when a file's esd column holds a zero or a negative
number.

**Context.** Today such an esd is raised to a thousandth of the column's median esd
(`schemas/pattern.py`, `_floor_sigma`). Issue #897 (a reporter's two-column file) had one
zero among esds of 3.0. That point got σ = 0.003 and a weight a million times its
neighbours', since weight goes as 1/σ². One point can then pull the whole fit, and nothing
reported it.

What is accurate depends on what the zero means, and the file rarely says.
- A raw count of zero, where the writer computed √0. A zero count still carries an
  uncertainty of about one count. rietx already uses that convention when a file has no
  esd column.
- A masked or unmeasured channel. Some neutron reduction writes these as y = 0, e = 0
  (recalled for Mantid, not checked). The point holds no measurement and should not be
  fitted.
- A negative esd has no meaning.

The current floor is wrong in all three cases.

**Options.**
1. Keep the floor.
2. GSAS-II's xye reader: a channel with y ≤ 0 gets zero weight, whatever its esd (checked
   by the first session).
3. Drop every channel with a non-positive esd from the fit, and report which channels were
   dropped and why.
4. Refuse the file and name the lines.

**Recommendation.** Option 3. It invents no number and cannot go wrong in units, and the
rest of the file stays usable. Its cost is a small bias where a raw file holds many genuine
zero counts, such as a sparse neutron background, because those points leave the fit. It is
built in WP-1952 (the WP for plain x-y files), which already plans a per-line report. That
WP also establishes what a zero marks in each format. It may restore genuine zero counts at
σ = 1 count where a file is known to hold raw counts. Until it lands the floor stays, and
the table names WP-1952 as its replacement. The pick would change if WP-1952 finds a format
where a zero esd marks good data.

---

## B8. Three limits that act on every fit

**The cell window.** For a phase the data barely see, each stage limits its cell to ±5 % of
the starting lengths (plus 0.05 Å) and ±2° on angles. It was built after an unseen phase's
cell ran to 39 293 Å on a 68-pattern in-situ series. Later the absent-phase hold (B1)
arrived, and it freezes the whole cell of exactly those phases. The window now matters in
one corner only: a held phase whose cell is tied to a visible phase's cell. There the
visible phase pins it anyway, and the window is expected never to act. **Recommendation:**
count the stages across the test suites where it binds. If the count is zero, remove it
from single fits; chain fits belong to WP-2003. The case against is TOPAS. It bounds every
cell by default (per rietx's docstring, not checked).

**The cell clamp.** After each stage, a cell length that moved more than 15 % from the
stage start is pulled back to the 15 % edge (6° for an angle). Honest moves within a stage
are about 0.03 %, 500 times smaller. It fires only on a runaway. The measured case is a
visible phase sharing its cell with a 2 % trace copy; its cell ran from 4.16 Å to 3803 Å in
one stage. When it fires, the user gets a cell 15 % off. No fit produced that value, and
its esds come from the runaway point. Only the `CELL_RUNAWAY` diagnostic says so.
**Recommendation:** on a runaway, put the cell back to its stage-start value and hold it
for that stage, with a record entry. A refiner would do the same. The code already does
this for a collapsing phase (B1), so it reuses that path. It fired in none of 104 fits in
WP-1523's sweep, so ordinary fits do not change.

**The 2 nm size floor.** Crystallite size from peak broadening may not go below 2 nm.
Below a few nanometres a crystallite is a cluster of a few unit cells. Broadened Bragg
peaks no longer describe its pattern, and the Debye scattering equation is needed
(recalled). The number itself comes from one private archive of 606 TOPAS refinements.
Without it, the only fence left is a peak wider than the scan. That fence is about 13 times
looser. **Recommendation:** keep 2 nm at tier 3, with its single-archive evidence stated in
the row. When it binds, `BOUND_HIT` already reports it.

---

## B9. Limits and defaults inside features you turn on (geometry pick changed)

A "box" here is a pair of limits on one parameter, a lower and an upper bound. For example,
occupancy may not leave 0 to 1.5. It has nothing to do with the unit cell; the batch should
have said "limits".

**The decision.** How to judge 21 defaults of this sort. They sit inside features the
caller switches on, such as preferred orientation, extra peaks and humps. Or they sit on
parameters no default plan frees, such as occupancy and specimen offsets.

**Recommendation** (the batch's revised pick):
- A limit that keeps a parameter out of an unphysical region, or away from a pole in the
  model, stays. Occupancy ≥ 0 and March-Dollase r > 0 are this kind.
- A chosen limit that a competent refiner would need to pass needs a source, or it widens.
  Two have a named dissenter. Occupancy ≤ 1.5: a mineralogist who declares Mg on a mixed
  Fe-Mg site and refines occupancy as site scattering needs 2.2 for full Fe. March
  r ≥ 0.15: a pressed clay or mica plate can need less. The 0.15 was also chosen on an Rwp
  comparison, which the house rules reject as evidence. No default occupancy limit is
  recalled in GSAS-II, FullProf or TOPAS.
- Starting values, such as Biso 0.5 and the peak-width starts, get a two-start test. If fits
  from two starts agree, the start does not matter.
- Instrument facts the package assumes are recorded in the result as assumed. These are the
  geometry, the polarisation (0.99 in the capillary preset, 0.5 with no preset) and the
  Kα2/Kα1 ratio of 0.5.

**The geometry question from the B7 ruling.** Today an `Instrument` built without naming a
geometry is treated as a capillary (`Geometry.kind` defaults to `debye_scherrer`,
`schemas/instrument.py` ~line 1207). The B7 principle, that an unknown geometry frees
nothing that might not apply, suggests a third state: geometry not stated. Under it the
default plan frees nothing geometry-specific, and the report suggests no geometry-specific
correction. Today the report suggests capillary corrections for such an instrument
(`report/layer2._POSITION_ACTIONS_BY_GEOMETRY`). The presets (`Instrument.bragg_brentano`,
`Instrument.debye_scherrer` and the transmission one) already state their geometry, so only
hand-built instruments change. Old project files store the geometry explicitly and should
open unchanged (inferred, to be checked). The recommendation is to put this in the same
follow-up WP as B7, since both read the same field.

---

## B1. The absent-phase hold, restated

A fit sometimes contains a phase the data barely show. It may be an impurity that has not
yet formed in an in-situ ramp, or one too weak to see. Its peaks are so small that changing
its cell, positions, peak widths or B leaves the calculated pattern unchanged. Least
squares then lets those parameters wander anywhere. On one ramp such a phase's cell walked
14.9 Å from the truth while Rwp did not move.

So at the start of each stage, rietx asks of each phase whether its scale is at least three
times its counting-noise esd. If not, it holds the phase's cell, positions, widths and B for
that stage. The scale stays free, so the phase can still appear. At the end of the stage the
test runs again. A phase that now passes is released, and the stage solves once more. A
phase that fell below the line during the stage is put back where the stage found it and
held, with one more solve. `StageResult.held` and `StageResult.released` list each one.

It passes because it touches only parameters the data cannot determine, so it cannot move
an answer the data support. A GSAS-II, FullProf or TOPAS user does the same by hand when a
phase vanishes. The weak point is the 3σ line. A weak phase that appears with its cell more
than a peak width from its CIF (thermal expansion, a solid solution) could stay under 3σ
because its peaks sit in the wrong place. The hold would then freeze the wrong cell. So the
threshold stays tier 3. The second pass tests a weighed phase at 0.1-1 wt % and a minor
phase started one peak width off its cell.

---

## B2. Magnetic moment directions

**The moment turn.** In some magnetic structures, rotating a moment about one axis leaves
the powder pattern unchanged, because the powder average cannot see that angle. Like the
absent phase's cell, the angle then sits wherever the start put it. Without the turn, one
answer reported 27.84° against a reference of 10.20°. The turn rotates the moment about
that invisible axis to a conventional reference direction and checks the pattern is
unchanged. It then holds the angle and records the turn in `StageResult.moment_turned`. A
refiner would fix such an angle by convention too. **Recommendation:** keep it.

**The stationary-angle test.** After the fit, it asks whether each moment angle sits on a
direction the symmetry singles out, such as along an axis, using a χ² test at 95 %. If so,
the angle keeps its value and loses its esd. A parameter sitting on such a direction makes
the covariance ill-defined and inflates the other esds. The review found the test too
lenient. On LaMnO₃ (NIST BT-1 data) a polar angle stopped 5.2° (0.091 rad) from 90°. The
test could not tell it from 90°, so the angle lost its 3.5° (0.0608 rad) esd. No refiner
would quote an off-axis angle without its esd. **Recommendation:** measure before ruling.
Fit simulated weak moments tilted 1-3σ off the axis, and count how often the test drops an
esd it should keep. If it drops ones a refiner would quote, demote it: report the test's
number and keep the esd.

---

## B3. Starting values for parameters that sit at zero

A seed is the value a stage gives a parameter before solving, when it would otherwise start
at its floor. The start can decide which minimum the fit finds, so a seed can change the
answer.

**Surface roughness.** The roughness stage starts Suortti's b at 0.3. Roughness lowers
low-angle intensity and Biso can mimic it, so the start may decide which of the two takes
the effect. GSAS-II starts at 0. **Recommendation:** refit three lab datasets from 0 and
from 0.3. If both land in the same place, the seed does not matter and needs no approval.
If not, report where each lands, and switch to GSAS-II's 0 unless 0.3 is closer to a
reference.

**Anisotropic strain (Stephens).** The width formula has a square root with infinite slope
at zero, so the solver cannot move a block that starts at exactly zero. Some start is
forced. rietx uses 1000 ppm isotropic, GSAS-II's isotropic microstrain default. On one
pattern the start changed the minimum found: χ² 1.160 from 1000 ppm against 1.482 from the
previous stage's strain (WP-1467). **Recommendation:** keep it at tier 3 until a second
dataset compares the starts. Record the seed in the result, which nothing does today.

---

## B11. When a fit stops

**Iteration budgets.** A stage stops after at most 100 iterations (400 evaluations). These
guard against a runaway, and a converging fit stays about ten times inside them.
**Recommendation:** treat them as not affecting the answer, once a test confirms that
margin under both solvers. Those are the default LM and the optional TRF, and under TRF
three test fixtures do hit the limit.

**Le Bail cycles.** Le Bail alternates between extracting peak intensities and refitting
everything else, three times per stage. Issue #740 used a synthetic pattern with the cell
and profile at the truth. It reached Rwp 4.56 % after 3 cycles and 1.62 % from 100 to 400
cycles, against 1.09 % for the true structure. GSAS-II runs 10 cycles, and FullProf's manual
suggests about 10. **Recommendation:** repeat until the intensities stop changing, with a
cap, built in WP-1542 (the WP that owns #740). Le Bail fits then reach a lower Rwp at some
extra cost. The remaining gap, 1.62 % against 1.09 %, is a separate problem WP-1542 also
owns.

---

## B16. The test that says a limit stopped a parameter

When a parameter ends at a limit, such as Biso at 0, rietx decides whether the limit
actually stopped it. The answer feeds the `BOUND_HIT` and `FLOOR_HIT` diagnostics and the
`at_bound` field. Under the default solver with up to 128 free parameters, the solver knows
which limits were active, and rietx reads its list. Otherwise rietx asks two things. Is the
value within a hundredth of an esd of the limit? And does the residual still push against
it? Over 32 measured cases on two datasets, the 0.01-esd line sits 13 times above the
largest real gap and 236 times below a fit that stopped early. In a default fit it only
reports. **Recommendation:** keep both numbers at tier 3, and add a third dataset under TRF
in the second pass. If f is kept (B4, option 1), the margin stays as measured.

---

## Three plain ones

- **B6:** anomalous dispersion (f′, f″) stays on by default. GSAS-II applies the same table
  to every X-ray pattern with no switch.
- **B13:** 58 numbers that only decide whether a diagnostic message appears move to the WPs
  auditing those messages (2004, 2005 and 2007). If 2005-2007 are cancelled at their gate,
  43 of them need a new home.
- **B15:** a magnetic site naming a bare element, with no charge, gets an assumed ion for its
  form factor. Keep the assumption where the element has a single magnetic ion (Ce, Eu,
  Yb), and for the other lanthanides once a citation is added. Sm waits for a citation,
  since its free-ion form is known to be poor. For U, Np and Pu, stop guessing and ask the
  caller to name the ion, listing the candidates. GSAS-II's bare U is U³⁺, where rietx
  picks U⁴⁺.

---

## Third round: answers to the questions sent back (2026-10-19)

Foreign-code behaviour below was read this session. GSAS-II 5.8.4 from its source in
`rietx-bench/tools/gsas2` (lines checked by the lead where marked). TOPAS from the
Technical Reference Version 9 (2 October 2026), decoded from topas-academic.com. FullProf
8.20 from its manual, the binary's strings and runs on its PbSO₄ example. Three Sonnet
agents read the sources; the lead checked each load-bearing line marked "checked".

### B2. The moment turn, and the stationary-angle test

**Is the turn common enough to keep?** It is needed in a narrower case than the hold it
serves, but the case includes textbook structures, and a caller cannot do it by hand.

The hold itself is common. Any collinear magnet whose magnetic cell is uniaxial
(tetragonal, hexagonal, trigonal) or cubic has a moment direction the powder average cannot
see (Shirane 1959). The hold fixes that angle.

The turn is needed only when the invisible rotation is a mix of rietx's two moment angles.
That happens when the site's coordinate frame does not have its pole along the unique axis.
Two families do this: R groups on rhombohedral axes, and the general-direction description
of the k = ½½½ rock-salt antiferromagnets (MnO, NiO, CoO). The second is the classic
textbook case of powder indeterminacy.

Without the turn there are two outcomes, and both give a wrong answer.
- Hold one angle where it started. The other angle then sweeps a circle that may never
  reach the right angle to the unique axis. Measured: the fit stopped at ψ = 27.84°
  against a true 10.20° (`tests/test_magnetic.py:1810-1823`). ψ is the one angle the
  powder can measure.
- Hold nothing. The covariance is singular. On 2 of 16 noise seeds the esd of ψ came out
  as 448° and 20 490°, where the other 14 gave 0.7-0.9° (issue #599).

A caller cannot easily do it themselves. They would have to rotate the site's frame so that
one angle is the invisible rotation. rietx derives that frame from the site symmetry and
has no verb for choosing another.

Other codes do nothing here. GSAS-II has no powder-indeterminacy logic; a flat moment column
falls to its generic rule, which drops a column with norm below 1e-14 for that cycle and
prints "Parameter(s) dropped" (`GSASIImath.py:263-268`). TOPAS stops with "cannot be
refined as it has no derivative" only when symmetry makes a moment component exactly zero
(Tech Ref § 14.1). FullProf's manual does not mention the case, and the program has no
handling for it (manual p. 20, the binary's strings). None of the three handles the
powder-only case.

**Recommendation: keep the turn** at tier 3, with the measured failure as its ground. It
moves the moment only along a rotation the pattern cannot see, checks that the pattern is
unchanged before accepting, and records the turn in `StageResult.moment_turned`.

**Is the stationary-angle test a demotion?** Yes. The batch asked for a measurement first,
but the LaMnO₃ case already decides it: the test removed a 3.5° esd from an angle 5.2° off
the axis, which a refiner would quote as 84.8(35)°. Rule 1 lets the package act alone only
where every competent refiner would. One counter-example of that kind fails it, so how
often it happens does not change the ruling.

What the demotion loses is small. Near a symmetric direction the textbook esd is too large,
because the pattern depends on the square of the offset there. Too large is the safe side.
An angle exactly on the axis has a zero Jacobian column, and the general covariance rule
already reports no esd for that (`statistics.normal_covariance`, WP-1110). Demoted, the
angle keeps its esd. The test's Δχ² to the symmetric direction goes in a record field, and
`MOMENT_ANGLE_STATIONARY` becomes an info record with that number. Neither GSAS-II nor
TOPAS has such a test; each prints the esd as computed.

### B7. The geometry take

**Agreed, with two additions.**

1. Under "geometry not stated" the report must not go quiet about a peak-position error it
   can see. A Bragg-Brentano specimen's displacement error leaves a cos θ-shaped misfit,
   which leaks into the cell if nothing absorbs it. Today the report suggests a capillary
   correction for such an instrument. Under the new state it should say that a
   position error of that shape is present, and ask the user to state the geometry.
2. "Not stated" needs a reading at every place that uses the geometry: 70 references in 15
   files, among them the forward model, absorption, preferred orientation, the report, the
   exporters and the FullProf and GSAS-II importers. The follow-up WP audits every reader
   before writing the new state. This is the rule the extra-components union taught
   (root `CLAUDE.md`): its counts and builders were right only while there was one kind.

Practice backs the take. TOPAS assumes no geometry. A correction applies only when a macro
names it, so nothing geometry-specific is refined unless stated (Tech Ref § 1.3, § 22.1.7).
GSAS-II always picks one. It reads Bragg-Brentano when the instrument file has a Kα1/Kα2
pair or its source text says "lab data", and Debye-Scherrer otherwise
(`GSASIIfiles.py:509-519`, `GSASIIdataGUI.py:2075-2081`). The choice changes which position
and absorption terms it offers. FullProf's geometry flag `Ilo` defaults to 0, one setting
for both Debye-Scherrer and Bragg-Brentano, and refines displacement and transparency only
when the user frees them (manual p. 70). So GSAS-II guesses from the wavelength, as rietx's
capillary default does in effect. TOPAS and FullProf refine nothing geometry-specific
unless asked, which is the take.

### B8. The cell window and the size floor

**The cell window: tier 2, agreed.** TOPAS bounds every cell by default (Tech Ref Version 9,
§ 2.17, Table 2-1, checked this session): a, b, c within 0.995·Val − 0.05 to
1.005·Val + 0.05 Å, angles within ±0.2°. Val is the current value, recalculated each
iteration, so in TOPAS it is a limit on each step rather than on the answer. rietx's solver
takes one fixed pair of bounds per stage, so the window is TOPAS's step limit compounded
over a stage: 0.5 % per iteration is 5.1 % over ten (`params/vector.py:593-613`). It also
applies only to phases the data cannot see, because a bound changes the solver's steps even
when not reached. GSAS-II has no cell bound of any kind (`GSASIIstrMain.py:1198-1230` acts
only on user limits), nor has FullProf (bounds on request only, manual p. 125). One program doing it by default meets tier 2. The count the batch
proposed is no longer needed, since the window costs nothing where it does not act.

**The 2 nm size floor: agreed, a warning is enough.**

- Physics. Below about 2 nm a crystallite is a few unit cells, and broadened Bragg peaks
  stop describing its pattern; the Debye scattering equation does. But the size is still a
  physical quantity. Under the B9 principle a chosen limit should not block it.
- Numerics. The floor guards against a runaway: a phase's peaks widening until they behave
  like background. A second fence already covers the end where that becomes meaningless,
  a peak wider than the fitted range (`size_cap`'s range backstop). On a Cu 10-80° scan
  that fence sits at about 0.15 nm.
- Practice. TOPAS's crystallite-size macro limits size to 0.3-10 000 nm (Tech Ref § 2.17).
  GSAS-II clamps the stored size to 0.001-10 µm after each refinement, silently
  (`GSASIIstrIO.py:3531-3540`, checked). FullProf has no size limit and no small-size
  warning, and says its apparent size carries no physical interpretation (manual pp. 21,
  25). So the codes that floor size do so at 0.3-1 nm, below rietx's 2 nm.
- The warning exists. `SIZE_UNUSUALLY_SMALL` fires below 5 nm today.

**Recommendation.** Remove the 2 nm floor. Keep the range backstop, since a peak wider than
the scan is not measured by it. Add to `SIZE_UNUSUALLY_SMALL`'s message that below about
2 nm the Bragg-peak model may not describe the pattern. Two tests pin the 2 nm number and
change with it (`tests/test_strain_cap.py:348`, `tests/test_help.py:667`). The flag's own
5 nm threshold goes to WP-2005 with the other diagnostic thresholds (B13).

### B1. The absent-phase hold as an option, and what other codes do

**Other codes.** None holds a vanishing phase's structural parameters automatically.
- GSAS-II floors every phase scale at 1e-12, silently (`GSASIIstrMath.py:3178`, checked),
  and has no significance test. A column that goes exactly flat (norm under 1e-14) is
  dropped for that cycle with a printed warning (`GSASIImath.py:263-268`, checked). A
  user can fix a phase's fraction, cell, Uiso and moments in a sequential run by hand
  ("Fix FXU").
- TOPAS floors scale at 1e-11 by default (Tech Ref § 2.17, Table 2-1). Its nearest feature
  is opt-in: `Remove_Phase(0.3, 0.5)` deletes a phase whose weight percent is below 0.3 %
  and whose esd exceeds half its value, at the end of a cycle, and prints "Deleting phase"
  (Tech Ref § 20.19). Both numbers are the caller's.
- FullProf 8.20 resets a negative scale to 10⁻¹⁰ each cycle, halves its shifts and prints
  "Scale factor <0, fixed to 1.E-10" (a run and the binary's strings, checked). It never
  removes the phase or holds its other parameters.

So the closest practice, TOPAS's, is an opt-in removal with caller-set thresholds. rietx's
hold is on by default, which no program does. It stays tier 3 on the maintainer's
approval, ruled "yes" on 2026-10-19.

**Reading of the ruling.** "An option, not mandatory": today the hold has no switch, so it
is mandatory. The session reads the ruling as on by default at 3σ, with a caller able to
switch it off or set another threshold. The other reading is off by default, as TOPAS's
removal is. On by default is the more accurate default. An unseen phase's free cell walked
14.9 Å from the truth on the in-situ ramp while Rwp did not move. In a chain that wandered
cell seeds the next pattern, so the phase is in the wrong place when it appears.

**Where the switch lives.** One number, read in five places (`refine.py:513, 1571, 1719`,
`multi.py:405`, and the cell window's screen through `CompiledModel.phase_support`). The
proposal is a plan field, `RefinementPlan.phase_support_sigma`, default 3.0, `None` for no
hold, carried by `PlanSpec` so the GUI and `.rxt` see it. `PHASE_UNCONSTRAINED` reads the
same number, so the diagnostic follows the caller's choice. This is a B14 lift into a seat.

### B5. Zero and negative esds: what is accurate

**An esd of zero is never a measurement.** It claims the intensity is exact, which no
counted quantity is. A negative esd has no meaning. So every such value is an artefact of
whatever wrote the file. There are four causes, and they need different treatment.

1. **√0 of a zero count.** The writer computed σ = √N on raw counts, and N was 0. The
   √N estimate of Poisson variance fails at zero: the true variance is the expected count,
   which is above zero. The point is a real measurement and belongs in the fit with σ of
   about one count. This is the case when counts are low: neutron data, high-angle tails,
   short scans.
2. **A channel with no measurement.** Masked pixels, the beamstop shadow, gaps between
   detector modules, and bins beyond the detector edge after integration. Integration
   software writes these as y = 0, σ = 0 (recalled for pyFAI and Mantid, not checked). The
   point carries no information and must leave the fit.
3. **A processing error.** Subtraction or scaling that zeroed or negated the column. A
   negative esd is always this.
4. **Rounding.** A normalised pattern with σ near 10⁻⁴ printed to three decimals reads 0.

What a file cannot tell a reader is which one it holds. It can tell case 1 apart in one
common situation. Where the esd column is Poisson on one scale, σ²/y is the same constant c
on every channel with counts (c = 1 for raw counts). Then a zero esd at y = 0 is a zero
count, and its σ is √c, one count on the file's scale. That matches rietx's own fallback
for a file with no esd column, √max(y, 1), and TOPAS's default weighting 1/Max(Yobs, 1)
(Tech Ref § 6.2).

**Why not drop every zero.** Dropping genuine zero counts biases the background upward.
At a mean of one count per channel, 37 % of channels read zero, and the survivors average
1.58 counts. At three counts the bias is 5 %, and at ten it is negligible. That is
arithmetic on the Poisson distribution. GSAS-II's xye reader zero-weights every channel
with y ≤ 0, so it carries this bias on sparse data.

**Other codes.**
- GSAS-II 5.8.4 depends on the reader, and none reports anything (all checked). The xye
  reader zero-weights y ≤ 0, skips a line whose esd is negative, and replaces an esd of
  0 with Poisson 1/y (`imports/G2pwd_xye.py:170-186`). The skip has a defect: the 2θ value
  is appended before the skip, so every later point is paired with the wrong angle. The
  fxye reader zero-weights a channel when y ≤ 0 or σ ≤ 0 (`G2pwd_fxye.py:86-91`). The CIF
  reader raises every esd below 1 to 1 (`G2pwd_CIF.py:280-292`, agent-read).
- TOPAS weights by 1/σ² whenever the file has σ, otherwise 1/Max(Yobs, 1) (Tech Ref § 6.2,
  § 21.10). The reference is silent on σ ≤ 0. A zero σ would divide by zero (inferred).
- FullProf 8.20 is silent and inconsistent (runs on its PbSO₄ example, agent-run). An esd
  of 0 acted as σ = 1, a hundred times the weight of its σ = 10 neighbours. A negative esd
  acted as its absolute value. A channel with y ≤ 0 got weight 1 whatever its esd. A file
  with no esd column was weighted 1/y, although the manual says σ = y (p. 74). The manual
  mentions none of this.

**Options.**
1. Keep today's floor (σ raised to 10⁻³ × the median esd). Wrong in all four cases: it
   gives the point about a million times its neighbours' weight.
2. Drop every channel with σ ≤ 0 and report it. Never invents a number. Biases sparse
   backgrounds as above.
3. GSAS-II's xye rule. Silent, and drops genuine zero counts.
4. Classify. A zero esd at y = 0 in a column that is Poisson on one scale becomes a zero
   count at σ = √c. Every other σ ≤ 0 drops the channel. Both are reported, by line.

**Recommendation.** Option 4, built in WP-1952 (the WP for plain x-y files). It is the
only option correct in case 1 and in cases 2-3. The constant-ratio test costs one median.
Case 4 (rounding) falls to the drop, which loses a few points and reports them. Until
WP-1952 lands the floor stays, and the table names WP-1952 as its replacement.

The case against: the ratio test may misfire on a column that is nearly Poisson. Examples
are counts with a dead-time correction, or a sum of two detector banks. There a zero count
would get a slightly wrong σ. That is still far better than today's 10⁻³ floor. The pick
would change if WP-1952 finds a format where a zero esd marks good data.

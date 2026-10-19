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

## Still open

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

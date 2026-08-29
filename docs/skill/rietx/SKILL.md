# Refinement protocol for agents

**Audience: an LLM agent driving `rietx` to refine real powder diffraction
data.** Not a tutorial and not an API reference — a *protocol*: what to do, in
what order, what to check before believing a number, and where this package
will tell you that your answer is wrong even though it looks right.

Read this before your first `fit()`. Sections 1–4 are ordinary Rietveld
discipline that would apply in any code; sections 5–10 are specific to running
it without a human at the plot, and were learned by building this one.

> **Orientation for the impatient.** Rwp is not the objective function of your
> job. A Rietveld refinement can converge, report an excellent Rwp, and return
> displacement parameters biased by 100 %, phase fractions wrong by 5 wt %, and
> a cell that is right for the wrong reason. Every section below exists because
> one of those happened and was measured. The package's job is to hand you the
> numbers that reveal it; your job is to look at them.

## 1. Before you refine: what the method can and cannot do

Rietveld refinement **fits a structural model you already believe** to a whole
powder pattern. It is a local, gradient-based optimisation of a strongly
non-convex, strongly correlated problem. It is not structure solution, not
phase identification, and not a search.

Preconditions, all of which must hold before `fit()` is meaningful:

| Requirement | How to satisfy it | If you cannot |
|---|---|---|
| Every crystalline phase present is in the model | `Structure.from_cif` per phase | An unmodelled phase's peaks land in the residual; Layer 0's `unmatched_obs` list is how you find them |
| The starting cell is within ~1 % | from the CIF, or from `index_pattern` when the phase is unknown (§7d) | The peaks are outside their frozen evaluation windows and the refinement cannot walk there; Layer 2 says so with `reindex_or_recheck_cell` rather than reporting a small shift (§6) |
| The wavelength is right | from the beamline `.prm`, the file header, or `Instrument.bragg_brentano(radiation=...)` — `"CrKa"`, `"FeKa"`, `"CoKa"`, `"CuKa"`, `"MoKa"`, `"AgKa"`, or any of them suffixed `1` for a Kα1-only monochromated beam | Every cell you report is wrong by the same scale factor and *nothing in the fit will tell you*. Do not hand-enter a wavelength from a textbook to "match" one of these: the table is one scale end to end (§8.11) and mixing scales is a ~100 ppm cell error |
| The geometry is right | `Instrument.debye_scherrer` vs `.bragg_brentano` | The aberration model is wrong; displacement/transparency/roughness/absorption are geometry-gated and silently absent |
| The intensities are un-manipulated counts, with esds if available | `read_pattern` reads the file's esd column when present | Weights are wrong ⇒ every esd and every χ² is wrong |
| The starting peak **width** is within a factor of ~2 | measure it: median FWHM of the dozen most prominent peaks, then `W ≈ (FWHM/2)²`, `X ≈ FWHM` | `ProfileTCHZ`'s `W = 1e-3 deg²` default is a *synchrotron* line (FWHM ≈ 0.03°). On lab data with 0.15-0.40° peaks the frozen evaluation windows are an order of magnitude narrower than the lines, and nothing recovers from that — see §2 and §6 |

**Never subtract a background before refining.** Subtraction invalidates the
counting-statistics weights and can make intensities negative. Hold an
estimated background *additively* (`BackgroundFixedPlusChebyshev`) or co-refine
it under a smoothness penalty (`BackgroundPSpline`). `background.auto_background(data)`
does the right thing.

---

## 2. The turn-on order, and why it is not negotiable

Free parameters in groups, cumulatively, in a stable order (McCusker, Von
Dreele, Cox, Louër & Scardi, 1999, *J. Appl. Cryst.* **32**, 36). Each group
runs to convergence before the next is freed. The reason is not tradition: the
correlations between groups are severe, and a simultaneous release from a poor
starting point walks into a local minimum that a staged release avoids. Toby
(2024, *J. Appl. Cryst.* **57**, 175 — the "recipe problem") states the
mechanism plainly: once parameters have refined to unphysical values, adding
more parameters no longer lets the fit recover.

The plans in `strategy/staged.py` encode this. Use them; do not hand-roll a
free set unless you have a reason you can state. The staged *discipline* is
what is not negotiable; the preset *sequence* is a default, because the right
next group depends on the data and the current values (Toby, 2024) — and
`Refinement.suggest` answers that question at the current state, one
analytic-Jacobian evaluation ranking every held parameter by predicted Δχ²
(no fit, no mutation, safe between fits).

```python
plan="mccusker_default"      # scale+bkg → zero → cell → W → U,V,X,Y      (profile only)
plan="mccusker_structural"   # …then coordinates → displacement → PO → extinction → roughness
plan="lab_bragg_brentano"    # …with sample displacement, Kα2 ratio, FCJ axial
plan="lab_calibrate"         # instrument calibration on a standard, certified cell HELD
plan="lab_sample_refine"     # sample against a frozen calibrated instrument
plan="profile_only"          # Le Bail
plan="pawley_default"        # Pawley
```

Three ordering rules that carry more weight than they look like. None of the
three is in the guidelines — each is this package's own measured finding, a
house rule labeled as one (the audits: [the v1.0 record](milestones/v1.0.md)
§ Appendix found the manual attributing them to the paper;
[the v1.1 record](milestones/v1.1.md) § Appendix holds the protocol's own
grounding grid):

- **Widths last among the profile terms, `W` before `U,V,X,Y`.** `W` is the
  constant term; freeing the tanθ and 1/cosθ terms first lets them absorb a
  constant offset and then fight it.
- **Intensity-scaling corrections go last, after the structure has settled.**
  Preferred orientation, extinction and surface roughness all rescale
  intensities in a Q-dependent way, and so do the scale, the occupancies and
  the displacement parameters. Freeing a correction early lets it eat structure
  that belongs to the structure. This is why `_ROUGHNESS_STAGE` is the final
  stage of every plan that carries it.
- **Anisotropic strain is freed *inside* the sample-broadening stage, not
  after.** A Stephens block locks `lor_strain` — its isotropic direction *is*
  that column — so deferring it would leave the isotropic width unrefined right
  up to the moment fifteen correlated coefficients turn on at once.

**Structure-free first when you can.** Le Bail (`mode="lebail"`) extracts
intensities from the data instead of computing them, so it converges the cell,
zero and profile without any structural assumption. Do that first, then switch
to Rietveld with the converged cell/profile. It is the single most reliable way
to avoid a structural minimum that is really a profile error.

Two things about Le Bail that the API does not tell you, both measured on
third-party lab data (2026-07-29):

- **Iterate the whole plan to a fixed point; one `fit()` is not enough.** The
  extracted per-hkl intensities are frozen inside each least-squares run (the
  frozen-per-stage invariant), so intensities and profile converge only by
  *alternating*. On PbSO4 pass 1 stops at Rwp 20.756 % with an unphysical
  Caglioti **V = +0.0615**; passes 2-4 reach 10.247 % with the curve sane. Re-run
  the plan until Rwp stops moving — and **keep the best pass, not the last**: the
  alternation is not a descent on one objective, so a later pass can come back
  worse (seen on Tb2BaCoO5, 17.3 % → 18.7 %).
- **Seed the background before the first pass, always — and this is the one
  that bites hardest.** `auto_background` chooses the knot spacing or the
  Chebyshev *order* but starts every coefficient at **0.0**, so the modelled
  background is identically zero, and the first `lebail_update` runs *before*
  the background has ever been fitted. The partition is then handed
  `max(y_obs − 0, 0)` — the whole pedestal — and gives it to the Bragg
  reflections. Measured on a synthetic pattern whose background is 5× its
  strongest peak: cycle one claims **571×** the true Bragg intensity. Seed the
  constant term (a low percentile of `y_obs`) before a Le Bail run.

**Multi-phase Le Bail was broken until v1.0 and is now supported** (WP-1028
§(g), fixed 2026-08-07). This section used to say "do not use it above one
phase", and the reason was a defect rather than the method: `lebail_update`
built its partition denominator per phase, so each phase claimed the entire
observed excess in its own windows and overlapping phases were issued the same
counts twice. The shares now sum to 1 across all phases at every channel —
measured Σ calculated / Σ observed excess **1.79 → 1.0000** on LaB₆ + CaF₂,
with the single-phase path bit-identical. Two caveats survive the fix and are
about the method, not the bug: the intensities of two phases whose reflections
*coincide* are not separately determined by the data (the partition splits them
by the current model, which is a starting value and not a measurement), and the
Rwp figures the old note quoted (742-9 281 % at two phases) were the overcount
compounding through the later profile stages, so treat a high multi-phase Le
Bail Rwp as a reason to look at the seeding above, not as this defect returning.

---

## 3. The degeneracies. Memorise these

Almost every wrong-but-good-looking Rietveld result is one of these. They are
not bugs; they are the geometry of the problem.

| Degenerate group | Their angular signatures | Consequence of getting it wrong |
|---|---|---|
| zero shift · sample displacement · cell | const · cosθ · tanθ | Over a narrow 2θ range these are collinear. A cell "refined" against a free zero on 20° of data is not measured. Bragg-Brentano only — the two flat-plate aberrations are held fixed on any other geometry. |
| zero shift · the two capillary offsets · cell | const · sin2θ · cos2θ · tanθ | The same trap in Debye-Scherrer's own shapes (McCusker eq 4, §8.18). Separable over 5–160°, not over 5–25°: the unit-column Gram's smallest eigenvalue is 5.2e-2 against 1.1e-5, a factor of ~4600. |
| crystallite size · microstrain | 1/cosθ · tanθ | Williamson-Hall separability. Over a short range they are one parameter, not two. |
| phase scale · Biso/ADPs · background · absorption · surface roughness · extinction | all smooth in Q | This is the big one. Every member depresses or lifts intensity as a smooth function of angle. Any of them can absorb any other. |
| capillary µR · phase scale · Biso | exp(c·sin²θ) — *exactly* | Not "correlated": singular. µR is computed from the specimen and never refined, and the fit is identical with and without it (§8.1). |
| flat-plate µt · phase scale · Biso | mostly, but not exactly | 60–99 % absorbable, so it is also computed rather than refined — but the remainder does move Rwp, and a wrong thickness lands partly in the fit and partly in the ADPs (§8.12). |
| preferred orientation · site occupancy | both rescale specific hkl | An occupancy refined against uncorrected texture is a texture measurement. |
| overlapped reflection intensities (Pawley/Le Bail) | identical | The *sum* is determined; the split is not. |

Two practical consequences:

1. **Do not free the second member of a group without checking the first is
   pinned by something outside the fit.** The `lab_calibrate` workflow exists
   for exactly this: refining a certified standard with its **cell held fixed**
   is what decorrelates zero from displacement from cell, because the cell is
   supplied rather than fitted.

2. **A correlation of 0.98+ means you refined one parameter and reported two.**
   The package raises `HIGH_CORRELATION` for you. The correct response is
   almost never "widen the bounds"; it is to fix one, or to extend the data
   range until the signatures separate.

3. **Where chemistry says two quantities are one quantity, constrain them
   rather than refining both.** `ref.tie_equal([paths])` makes an equality
   group, `ref.tie(path, source, scale=, offset=)` the general affine form
   (`occ₁ = 1 − occ₀` on a mixed site is `scale=-1, offset=1`), `ref.untie`
   releases them. A constraint *removes* a parameter — unlike a restraint,
   which adds a weighted observation and leaves the count alone — so it is the
   one move that raises the observation-to-parameter ratio.

   The two cases worth reaching for are the ones McCusker names: equal
   displacement parameters across atoms in the same environment, and
   occupancies summing to a known total. Measured on fluorapatite's three
   phosphate oxygens: 20 → 18 free parameters, 287.5 → 319.4 observations per
   parameter, and B(O) 0.2763(1810) / 0.5279(1911) / 0.4149(1282) Å² free
   against 0.4138(899) Å² tied — tighter than the best of the three.

   **Check the premise before you tie, and do not check it with Rwp.** Rwp
   moved by 0.05 % of itself there, so it can tell you neither that the
   constraint helped nor that it hurt. The check is in the free refinement: if
   each free value lies within its own esd of the others, the data does not
   contradict the claim that they are one parameter. Where they disagree by
   more than their esds, the atoms are saying they are *not* in the same
   environment, and tying them replaces a measurement with an assumption.

   Every tie is recorded as a `set_tie` history node and restored by a
   checkout, so a constrained protocol replays as one. Symmetry always
   outranks a user tie: a cell axis the space group already ties, a coordinate
   behind its site-symmetry direction, and a `lebail`/`pawley` mode-fixed path
   are refused by name rather than silently ignored.

---

## 4. Judging a fit — and what Rwp is actually for

Rwp compares your model to the *data you have*, weighted by counting
statistics. It is dominated by the strongest peaks and by the background level.
It is a useful *relative* number between two fits of the same data over the
same channels, and a nearly useless absolute one. That is the literature's own
verdict, stated and then measured: Toby (2006, *Powder Diffr.* **21**, 67) —
"no simple way to distinguish a good fit from one that is just plain wrong
based on R factors" — and the IUCr round robin, where 18 refinements of one
identical PbSO₄ dataset returned Rwp 8.2–20.0 % (Hill, 1992, *J. Appl.
Cryst.* **25**, 589).

Judge a fit in this order:

1. **Status and guards.** `result.status`, then `result.diagnostics`. A warning
   here outranks any statistic. `statistics.max_shift_over_esd` is the measured
   quantity behind "converged" (McCusker 1999 §7: converged when ≤ 0.1, a band
   quoted from the paper and gating nothing): a converged solve satisfies it a
   fortiori, so read it on the other branch — where a stage stopped on
   `STAGE_MAX_ITER`, its magnitude says *how far* the solve was still moving
   in esd units, which separates "nearly there" (just over the band) from a
   fit that stopped mid-flight (measured ≈14 on one starved iteration).
2. **The shape of the difference curve**, region by region — not its size.
   Layer 0 gives you this as numbers: `report.regions` with per-region local
   Rwp and χ² share, and `cumulative_chi2_breakpoints` locating where the model
   starts failing.
3. **Unmatched peaks.** `report.unmatched` with `kind="unmatched_obs"` is an
   impurity or missing phase; `"unmatched_calc"` is a phase you modelled that
   is not there, or an absence error.
4. **Whether the refined values are physically possible.** Negative Biso.
   Occupancies above 1. A cell that moved 0.5 %. An ADP tensor that is not an
   ellipsoid. These are all reported, but you have to read them.

   **And the geometry, which is the same question asked of the structure
   rather than of a parameter.** `result.geometry` (also `report.geometry`)
   is a `GeometryTable`: `bonds` and `contacts` — McCusker et al. 1999 §11
   asks for "both bonding and nonbonding" — and `angles` at every vertex.
   This is the paper's criterion (ii), which it ranks *with* the profile fit
   and above every R value, so read it before step 8 and not after. Nothing
   in the package scores it; a Si–O at 1.75 Å or a 60° O–M–O is yours to
   recognise. Each row lists the whole environment of each asymmetric-unit
   atom, so **the number of rows naming an atom is its coordination number**,
   and a bond between two sites appears twice, once from each end.

   Two things about the esd. `stderr` is propagated through the *whole*
   covariance, which §10 requires of any derived quantity, and
   `stderr_diagonal` beside it is what ignoring the correlations would have
   given — quote the first, and use the pair when you need to say how much
   the correlations mattered. And `None` never means zero: it means the row
   had no covariance behind it (an evaluate-only pass) or is fixed by
   symmetry, and an esd of 0 on a symmetry-fixed 90° angle would be a claim
   about precision rather than a statement about constraint.
   `write_refinement_cif` writes the whole table as `_geom_bond_*`,
   `_geom_contact_*` and `_geom_angle_*` loops, with the symmetry codes
   resolvable against the `_space_group_symop_operation_xyz` loop it writes
   beside them.
5. **The esds, with their inflation.** `statistics.esd_inflation` is the
   Bérar-Lelann factor for serial correlation. Note it has an expected value of
   ≈1.51 even for perfectly white residuals — a house derivation, not the
   paper's (chance same-sign runs give E[χ²′]/χ² = 1 + 4/π;
   `optimize.statistics.berar_lelann_factor`, simulation-verified) — so treat
   it as an upper bound on the damage, not a measurement of it.
   `report.identifiability` quotes the
   qualifying trio side by side — raw χ²_red, the inflation (already in every
   quoted esd, dividable back out), Durbin-Watson — plus the δR line
   (`delta_r_slope`/`delta_r_intercept`: sorted Δ/σ against normal quantiles;
   slope ≈ 1, intercept ≈ 0 on honest σ, slope > 1 when σ is underestimated).
   Report the ingredients with any esd you quote onward; scaling variances by
   GoF² alone is the practice Schwarzenbach et al. (1989) call "highly
   questionable". The round robins measured why the ingredients matter: the
   same data refined under different protocols spread by up to ×17–25 of the
   quoted esds on cell dimensions (Hill, 1992; Hill & Cranswick, 1994, *J.
   Appl. Cryst.* **27**, 802 — whose
   explanation is §3's first degeneracy row, the cell compensating 2θ-scale
   errors). Durbin-Watson is in the trio because serial correlation is
   precisely what makes the raw esds untrustworthy, and d stays discriminating
   where Rwp and GoF do not (Hill & Flack, 1987, *J. Appl. Cryst.* **20**,
   356).
6. **Whether the converged answer is the only one** —
   `report.identifiability.exchanges` and `.soft_modes`, and this outranks
   the statistics because it is about what "converged" *means*. `converged`
   is a statement about the free set; an exchange row with
   `exchangeable=True` says a **held** parameter's signature is reproducible
   inside the fitted span (`r2` → 1) *and* a fitted partner stands many σ
   from its null — an E2-shaped answer reads "converged, but the fitted
   zero_shift is exchangeable with the held sample_displacement — **this
   fit** cannot tell you which is physical". **The verdict that licenses is
   `ambiguous`, not `converged`** — measured, the fit carrying a planted
   displacement inside a compensating zero and its clean reference differ in
   *nothing* but this row (χ²_red 1.012 vs 1.010, R² identical to six
   decimals; only the partner's 128σ-vs-1.6σ separates them).

   **The first resolution is the swap, and it is a measurement.** Fit each
   member of the pair *alone* with the other held at its **null** (0 for
   zero, displacement and transparency) and compare χ² — two warm fits,
   seconds. `compare_rivals` (§9) does exactly this. R² is a **geometric**
   statement about column overlap and cannot say whether the counts in hand
   separate the pair: on real SRM 660c an R² of 0.9977 pair comes apart
   decisively, χ² 4.0752 (zero only) against 3.4890 (displacement only) on
   5332 points, with the zero-only model biasing *a* by +100 ppm.

   **Read the outcome by the decision band, and follow through.** The grade
   is `RIVAL_DECISIVE_MIN_CHI2_RATIO` (= 1.10, `rietx.report`), read on
   the losing rival's χ² over the winning rival's. At or above it **the data
   has chosen: the winning rival's fit is the answer, and you quote it
   without caveat.** Hedging a won swap is a measured failure, not caution —
   on the round-3 eval's solvable control (rivals decisive at 1.1679, the
   SRM 660c pair above) the agents that ran the swap recovered the true
   displacement and still declined or hedged the answer; the control went
   0/7 valid. Below the band the pair is genuinely unresolved — the two real
   tie states measure 1.0075 and 1.0001 — and the resolution is protocol (a
   calibrant-fixed zero, a wider angular window) or declaring the ambiguity;
   no sentence converts a tie into an answer.

   **The sentence travels beside the numbers too.** The summary's
   identifiability clause — the finding, the swap and this band's license —
   is also delivered verbatim as `result.statistics.identifiability_clause`
   (`report_thresholds_version` 1.3, WP-1108). Measured consumers pipe the
   JSON response to a file and grep the statistics back, and the summary
   string is what those greps drop (the license reached agent context in 2
   of 12 cells from the summary; 4/4 from the statistics block once placed
   there). So a pipeline that keeps only the statistics still holds the
   license; `None` there means no report was built or nothing crossed a
   comment threshold, never a verdict.

   What you must **not** do is free the held parameter alongside its partner
   and refit: both free lands on the degenerate ridge of §3, and it reports
   the unconstrained combination at a *better* Rwp, which is the trap. This
   is the single most common misreading of the clause — measured over 30
   agent runs, seven of twenty position cells took it (WP-1059). Note the
   difference between the two moves: the swap runs each rival **alone**, the
   ridge runs them **together**. A `soft_modes` entry quoted in the summary
   is the same statement about a fitted *combination*: the named parameters
   trade freely and their individual esds are not independent.
7. **What the background is doing** — `report.background`, and it belongs
   *above* Rwp because it decides how to read Rwp. Two rows:
   `worst_absorption` (with `worst_absorption_path`) is how much of a
   structural parameter the background column span can reproduce, and
   `off_region_chi2_reduced` with `off_region_durbin_watson` is whether the
   residual *between* the peak regions is systematic (the Durbin-Watson d of
   Hill & Flack, 1987, applied off-region — the statistic built to detect
   exactly this). Layer 0's regions are peak clusters, so that second failure
   lands in no `report.regions` entry and step 2 cannot see it at all.
8. **Only then Rwp and GoF** — as a pair with
   `background.rwp_background_subtracted`, never alone. Measured: a sharp
   LaB₆ fit and one under 0.6° of broadening both report Rwp **0.0137**, and
   background-subtracted they read 0.0490 and 0.0766. Raw Rwp is flattered by
   whatever the background carries (89 % of the observed intensity in both),
   so the number that separates two fits is the subtracted one. The
   literature says the same twice: Toby (2006, Fig. 1) shows identical model
   discrepancies reading Rwp 23 % with no background and 3.5 % with one, and
   Hill's 1992 round robin recommends quoting the background-subtracted forms
   for exactly this comparison. It is
   published on every report and deliberately never mentioned in `summary` —
   every background-dominated pattern would trigger it, including converged
   ones.

9. **Last, the structure R factors** — `result.phase_agreement`, one
   `PhaseAgreement` per phase, carrying `r_bragg` (R_B, eq 14 of McCusker et
   al. 1999) and `r_f` (R_F, eq 13). They are last on purpose. A powder
   pattern does not measure individual reflection intensities, so I(obs) is
   the observed pattern *partitioned in proportion to I(calc)*: a wrong model
   receives the intensity it predicted, and both indices flatter it. Both
   papers say so — the guidelines beside eq (13), "biased towards the
   structural model", and Toby (2006): R_Bragg "has no statistical validity". They are
   for watching R_B fall as you improve a model, and for the publication that
   will ask for one — never for judging a model in isolation, and never as
   evidence that a correction helped. Absent (an empty list) in Le Bail and
   Pawley mode, where the intensities *are* the fit and the comparison would
   be circular.

   **Do not compare a trace phase's R_B with the major phase's.** Neither
   index is weighted, so a reflection the fit barely constrains weighs as much
   as one that dominates it — the weighted R_WI of Cox & Papoular (1996,
   *Mater. Sci. Forum* **228–231**, 233) exists to answer exactly this, and is
   not computed here (`optimize.statistics`' docstring holds the pointer) —
   and a minor phase's windows sit under the major
   phase's peaks, where the counts the major phase failed to describe are
   handed out too. Measured on 11-BM NAC with 1.35 wt % CaF₂: 0.052 for the
   major phase against 0.385 for the impurity, all of the latter in four
   reflections at I(obs)/I(calc) ≈ 2.2, each under a strong NAC peak. Read it
   beside `qpa.phases[].weight_fraction`, and treat a trace phase's value as a
   question rather than a measurement.

   `write_refinement_cif` writes them as `_refine_ls_R_I_factor` and
   `_refine_ls_R_factor_all` on each phase's own block, beside a
   `_pd_proc_ls_special_details` that states the esd method in full — the
   base estimator √diag(χ²_red·(JᵀJ)⁻¹), then the Bérar-Lelann factor it was
   multiplied by, which §10 of the guidelines requires any publication to
   state.

**Adding parameters: use ΔBIC, not Hamilton's R-ratio.** Measured on this
package's own data (WP-0503): at 7251 channels Hamilton's test blesses a 0.13 %
χ² improvement that is physically inert. ΔBIC has the sample-size penalty that
makes it meaningful at powder-pattern channel counts.

**Comparing against another code means adopting its protocol, not just reading
its numbers.** Mirror its refined-parameter set, its held parameters and its
excluded regions, then *check the channel count matches* before believing any
Rwp comparison. Measured: guessing a plausible protocol on the GSAS-II
fluorapatite tutorial gave Rwp 16 % and a +390 ppm cell; mirroring the
converged `.EXP` gave 9.73 % against GSAS's 10.05 % on an identical 5750
channels. The round robin measured the same class of error at community
scale: most of its alarming Rwp spread came not from the algorithms but from
what each program's sums *included* — background in or out, peak-only regions
or every channel (Hill, 1992).

---

## 4b. Declare the deliverable — "good enough" is a question about purpose

Much real work is non-ideal by construction: nanoparticle broadening erases
the fine detail a sharp-line protocol assumes, and porous frameworks (MOFs,
zeolites) carry intensity error from unknown pore contents that no profile
correction touches. **No bar moves for such data** — the gates auto-scale to
information content (measured: a zero error read at confidence 0.997 on sharp
data produces silence, GoF 1.02, on the same error under 0.6° broadening),
and "good enough" is a different question answered exactly, not a relaxed
standard. What changes is *which report rows decide your deliverable*.
Declare the deliverable, then read its rows — the report itself is
purpose-neutral, and it will not infer your purpose for you.

**Phase ID — "which phases are present?"** The rows that decide:
`report.unmatched` (`kind="unmatched_obs"`: strong entries are lines your
phase set does not produce) and `report.lebail_gap`, the structural-vs-profile
triage. The gap re-partitions the per-hkl intensities at the frozen converged
state (an evaluate-only Le Bail — θ never moves) and reports both Rwp: a
`ratio` ≫ 1 means positions and profile alone account for the pattern, so
every line is indexed and identification is safe **at any absolute Rwp** —
the misfit lives in intensities, which phase ID does not rest on. Stopping
criterion: no strong unmatched observed peaks, gap readable — done, whatever
Rwp says. An abstention with `abstained_kind="resolution_limited"` does not
block this deliverable (see below).

**QPA — "how much of each?"** Fractions ride on scales, so the deciding rows
are the ones that bias scales silently. The first of them is
`report.background.absorption`, keyed by parameter path: the block projection
R² of each structural parameter's Jacobian column onto the background column
span, the detector for the scale↔Biso↔background degeneracy of §3. A pairwise
ρ cannot see it (measured: ~0.2 per coefficient while the block absorbed
46 %), and the whole table is published rather than only the entries over
`BACKGROUND_ABSORPTION_NOTABLE` — a fired/not-fired bit is a verdict, and the
diagnostic already carries the verdict. Then absorption geometry (µR is
*exactly* a scale/Biso reparameterisation; µt is not, and its ΔBiso is larger
and negative), and physically-impossible refined values (§4.4: a negative
Biso is a background error laundered through a scale). The Le Bail gap must
be read the other way here: a large ratio means the intensity model is wrong,
and wrong intensities *are* wrong fractions.

Measured on this deliverable, and the reason the row outranks every statistic
beside it (LaB₆, broad peaks, same data both times, 2026-08-12): fitted with a
1°-knot unpenalized spline the refinement reports Rwp **0.08852** and GoF
1.022, against **0.08969** and 1.025 with a correct Chebyshev-6 — the wrong
background wins on every agreement index — and its displacement parameters
come back 0.958 and 0.000 Å² against a truth of 0.5, one of them on its bound,
where the correct background gives 0.691 and 0.327. `worst_absorption` reads
0.46 against 0.08. **Nothing else in the report distinguishes these two fits,
and the plot does not either**: the over-flexible residual is white noise
inside ±3σ. Stopping criterion: fractions stable under a
background-flexibility change, `worst_absorption` below its threshold, and no
unresolved scale-family diagnostic — never "Rwp stopped falling", which here
points the wrong way.

Two of this deliverable's rules are the QPA round robins' own findings
(Madsen et al., 2001, *J. Appl. Cryst.* **34**, 409; Scarlett et al., 2002,
*J. Appl. Cryst.* **35**, 383). A Rietveld σ(W) reflects only the fit's
mathematical precision and is "not necessarily related to the accuracy" —
judge a fraction against the published participant spread, never against its
own esd (the policy `tests/data/README.md` applies to the bundled `qarr/`
patterns, which are the round robin's own samples). And microabsorption is
the largest physical obstacle to X-ray QPA — "may prove to be insurmountable
in some circumstances" — with a Brindley correction applied where none is
needed *reducing* accuracy (their sample 1 and synthetic bauxite; §7's
`BRINDLEY_OUTSIDE_REGIME`).

**Structure — "where are the atoms?"** Everything above, plus the
intensity-model rows themselves: per-region intensity coefficients and their
angular trends (ADP vs scale vs texture), `report.texture` / `report.strain`
with their caveats, restraint tension, ADP positive-definiteness — and
`report.identifiability.exchanges` with `.soft_modes` (§4 step 6), because a
structural claim rests on the parameters *meaning* what they say: an
`exchangeable=True` row is a converged fit whose fitted partner and a held
parameter the data cannot separate, and the deliverable it supports is
`ambiguous`, not a structure. Here a
notable Le Bail gap is a *blocker*, not a comfort — the intensity model
carries the structural claim, and the gap says it does not carry the pattern.
Stopping criterion: §10's full ladder (diagnostics resolved, no attributable
region, ΔBIC refuses the next parameter), with no `exchangeable` row
unaddressed — addressed by running the swap (each rival **alone**, the other
at its null: `compare_rivals`, §4 step 6), and where that ties, by protocol (a
calibrant-fixed aberration, a wider window). Where it does **not** tie,
addressed means adopted: a decisive swap (≥ `RIVAL_DECISIVE_MIN_CHI2_RATIO`)
is an answered question, and the winning rival's fit is the structure's
answer, quoted without caveat — re-declaring it ambiguous after winning the
measurement is the mirror image of the ridge, and as wrong. Never by freeing
the rival into the same fit (§3's ridge), which is the
two-parameters-**together** move the swap exists to replace.

**The capability floor.** Whatever is reading this report, the floor is:
verify before acting (`predict_then_verify`, or a history branch), treat a
*capped* confidence (an `add_impurity_phase` at 0.3, a texture call capped
below its likely cause) as an **unresolved question**, never as a
low-priority instruction, and never execute a vetoed action. There is no
ceiling: a consumer able to reason past the floor may — the report supplies
evidence, judgment stays with the reader.

**The worked example, measured (LaB₆ pore proxy: a guest scatterer at the 1b
site in the data only, host model refined to convergence, 2026-08-12).**
Rietveld Rwp 0.0405, GoF 2.97 — a "bad fit" by GoF. The report: zero
suggested actions; intensity carries 83 % of the misfit in per-region errors
of 9–18 % with **alternating sign** ((100) low, (110) high, (111) low —
structure-factor interference, which scale, ADP and texture cannot produce;
the summary names it as un-modelled scattering contents); and
`lebail_gap.rwp_lebail` 0.0170 against 0.0405, ratio ×2.4. Read by
deliverable: phase ID is **done** — stop, at GoF 2.97. A structure
determination is **not** — and its next move is chemistry (what occupies the
pores), never finer profile corrections, which this evidence says cannot
help.

**Resolution-limited is a stopping point, not a failure.** On broad-peak
data a real aggregate misfit can be unattributable per kind: the abstention
then carries `abstained_kind="resolution_limited"` (the shape basis explains
the failing regions at median R² ≳ 0.9 — the edit directions are merely
indistinguishable on merged peaks). For phase-ID-grade work that is a
legitimate end state; for structure-grade work it means *collect better
data* — pushing finer corrections into a fit whose attribution is
resolution-limited changes numbers it cannot justify.

---

## 10. A worked default

If you have a lab pattern, a CIF and no other information, this is the sequence
to run and the checks to make. Adapt, do not skip the checks — adaptation is
the literature's own instruction, because the right order depends on the data
and the starting values (Toby, 2024, the "recipe problem").

```python
import rietx as rx

data       = rx.read_pattern("sample.xy")
structure  = rx.Structure.from_cif("phase.cif")
instrument = rx.Instrument.bragg_brentano(radiation="CuKa",
                                          monochromator_two_theta=26.6)
instrument.background = rx.background.auto_background(data)

ref = rx.Refinement(structure, instrument, history="session.jsonl")

# 1. structure-free first: cell + profile without any structural assumption
ref.fit(data, mode="lebail", plan="profile_only")

# 2. Rietveld from the converged cell/profile
result = ref.fit(data, plan="lab_bragg_brentano")

# 3. guards outrank statistics
for d in result.diagnostics:
    print(d.level, d.code, d.where, d.message)

# 4. numbers, not pixels
report = ref.report(plan="lab_bragg_brentano")
if report.abstained_reason:
    print("Layer 1 abstained:", report.abstained_reason)   # fix the fit first
else:
    for r in report.attribution:
        if r.gates_passed:
            print(r.two_theta_lo, r.two_theta_hi,
                  [(c.kind, c.value, c.stderr, c.share) for c in r.coefficients])

# 5. impurities / missing phases
print([u for u in report.unmatched if u.kind == "unmatched_obs"])

# 6. only now, the statistics
print(result.statistics.rwp, result.statistics.gof,
      result.statistics.durbin_watson, result.statistics.esd_inflation)
```

**Stop conditions.** Stop refining when (a) every diagnostic is understood and
either resolved or reported as a caveat, (b) Layer 1 attributes no remaining
region above the significance gate, and (c) adding the next parameter group
fails a ΔBIC test or trips a guard. Do **not** stop merely because Rwp stopped
falling, and do not continue merely because it is still falling. These are the
*structure-grade* conditions — §4b maps the earlier stopping points a declared
phase-ID or QPA deliverable is entitled to.

**What to report.** The refined values with their (inflated) esds, the
diagnostics you could not resolve named as systematics, the protocol you
actually ran (plan, held parameters, excluded ranges, channel count), and the
package version, backend and solver from `result.provenance`. A number without
its protocol is not a measurement.

---

## See also

- [`README.md`](../README.md) — capability table and worked examples
- [`DESIGN.md`](DESIGN.md) — why the FitReport is shaped this way (the
  "Outputs & fit assessment" section is the agent-native design record)
- [`ROADMAP.md`](ROADMAP.md) — what is implemented, what is fenced
- `tests/data/README.md` — provenance and reference values for every dataset
- `rietx compare` — browser UI comparing refinement settings side by side on
  the bundled standards (`src/rietx/viz/compare.py` is its registry, and a
  usable API on its own: `compare.run("zincite", "dispersion")`). Its
  cumulative-Δχ² panel is the machine-readable form of §8.1's rule — it shows
  *where* a correction acted, not just whether Rwp moved

Papers are cited author-year throughout; each citation resolves in the
manual's bibliography (`docs/manual/references.bib`) or carries its journal
reference inline at first mention.

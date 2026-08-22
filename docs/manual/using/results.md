# Reading the numbers

A finished fit hands back a `RefinementResult`. This chapter is what is on it,
and how to read each part: the agreement indices, the two structure R-factors,
the distances and angles, what any restraints did, and the two counts that say
whether the pattern could support the model at all. The refined parameter values
themselves are the one part covered elsewhere, in [](model.md), because they are
a view of the parameter table rather than a statistic about the fit.

The guidelines rank that evidence, and the ranking is not the one a table of R
values suggests. The two most important criteria for judging a refinement are
the fit of the calculated pattern to the observed one and *the chemical sense of
the structure* {cite}`mccusker1999`. Rwp is half of the first.

Where a section here names a formula, Part 2 carries it as a numbered equation
and this chapter links to it rather than restating it.

## Fit statistics

`RefinementResult.statistics` is a `Statistics` object. The definitions follow
Toby {cite}`toby2006`, and Part 2 gives them as equation
{eq}`est-indices`.

| Field | Is | Reads as |
|---|---|---|
| `Statistics.rwp` | the weighted profile R-factor | how well the calculated pattern matches the measured one, weighted by the counting statistics. A **fraction**: 0.0933 is 9.3 %. |
| `Statistics.rp` | the unweighted profile R-factor | the same comparison with every point weighted equally, so strong peaks dominate it. |
| `Statistics.rexp` | the expected R-factor | the Rwp that perfect counting statistics alone would produce. It is a property of the data and the parameter count, not of the model. |
| `Statistics.chi2` | the **reduced** χ², Σw δ²/(N − P) | how far the fit is from statistical perfection. 1.0 means the residual is the size of the noise. |
| `Statistics.gof` | Rwp / Rexp | the square root of `Statistics.chi2`. Also called S or χ. |
| `Statistics.rwp_background_subtracted` | Rwp with the background removed from both patterns | the more meaningful figure when the background carries most of the raw intensity. |
| `Statistics.durbin_watson` | the serial-correlation statistic | ≈ 2 means neighbouring residuals are independent. Far from 2 means the misfit is structured, whatever Rwp says. |
| `Statistics.esd_inflation` | the Bérar-Lelann factor | the amount the reported esds were multiplied by to account for that serial correlation. It has **already been applied**. |
| `Statistics.n_points` , `Statistics.n_free_parameters` | N and P | what makes the rest interpretable. |
| `Statistics.max_shift_over_esd` | max \|Δθ\|/esd over the last accepted step, external units both sides | the convergence quantity (McCusker 1999 §7: converged when ≤ 0.1, a band quoted and never tuned). A converged fit satisfies it a fortiori; on a stage that stopped on its iteration budget it says **how far** the solve was still moving. `None` when it cannot be measured: no accepted step, no esds, a replay, or a joint multi-pattern fit. |
| `Statistics.identifiability_clause` | the report's identifiability sentence, verbatim: the exchange finding with the swap experiment and its license, and/or the softest notable mode | the same sentence the report's summary carries, delivered beside the numbers so a consumer that reads only the statistics block still gets it. The evidence behind it is `FitReport.identifiability` ([](report.md)). Written by `build_report`, never by the fit: `None` until a report is built, and `None` when nothing crossed a comment threshold, and neither is a verdict about the fit. |

`Statistics.chi2` is the reduced χ², not Σw δ². The two differ by a factor of
N − P, which on a real pattern is several thousand.

The literature is not consistent about which of the two is called χ². The IUCr
guidelines {cite}`mccusker1999` write χ² = Rwp/Rexp and say it should approach 1;
that quantity is `Statistics.gof` here, and `Statistics.chi2` is its square. Both
conventions say the same thing about a fit, and the naming here follows Toby
{cite}`toby2006`, but a number copied from a paper needs the convention copied
with it.

`Statistics.esd_inflation` is conservative by construction. Perfectly white
residuals still land near 1.51, because same-sign runs happen by chance, and lab
data with unmodelled profile detail typically lands at 2 to 4. Treat it as an
upper bound on the serial-correlation damage rather than as a measurement of it.

## Structure agreement indices

Every field above measures the *pattern*. Two more measure the **structure**, and
a journal will ask for at least one of them {cite}`mccusker1999`. They live on
`RefinementResult.phase_agreement`, one `PhaseAgreement` row per phase, keyed by
`PhaseAgreement.name`, the same name the phase carries everywhere else. Part 2
defines both as equation {eq}`est-structure-r`.

| Field | Is | Reads as |
|---|---|---|
| `PhaseAgreement.r_bragg` | R_B, the Bragg-intensity R-factor | how well the model reproduces the *integrated intensities* I = m·F² with m the multiplicity, rather than the profile. Written to a CIF as `_refine_ls_R_I_factor`. |
| `PhaseAgreement.r_f` | R_F, the structure-factor R-factor | the same comparison on the amplitude rather than the intensity, so it is the number a single-crystal R is directly comparable with. Written as `_refine_ls_R_factor_all`. |
| `PhaseAgreement.n_reflections` | how many reflections were summed | smaller than the phase's reflection list whenever one falls off the Ewald sphere. |

A joint multi-histogram fit reports them per histogram, on
`HistogramResult.phase_agreement`: the partition is of one pattern's counts, so
there is no pooled value.

Both are biased towards the model you are testing. A powder pattern does not
measure individual reflection intensities, because overlapped peaks share their
counts, so the "observed" intensity of each reflection is the observed pattern
*partitioned in proportion to the calculated one*. A wrong model therefore
receives the intensity it predicted, and both indices flatter it. That is the
paper's own warning, and it fixes what they are for: watching an R_B fall as you
improve a model, not judging a model in isolation.

A trace phase's R_B is not comparable with the major phase's. Neither index is
weighted (the sums count every reflection alike, whatever its counting
statistics), so a reflection the fit barely constrains weighs as much as one
that dominates it, and a minor phase's windows sit under
the major phase's peaks, where the counts the major phase failed to describe are
handed out too. Measured on the 11-BM NAC pattern with its 1.35 wt % CaF₂
impurity: NAC reads R_B 0.052 and the impurity 0.385, with the whole of the
impurity's misfit in four reflections at I(obs)/I(calc) ≈ 2.2, every one of
them under a strong NAC peak with a large positive residual. Read R_B beside the
phase's weight fraction, and treat a trace phase's value as a question rather
than a measurement.

Both are absent, an empty list, for a Le Bail or Pawley fit. There the
intensities *are* the fit, so the partition would be compared against itself.

## The bonding geometry

The other thing a journal asks for is the distances and angles, and the
guidelines rank them above every R value: the two most important criteria for
judging a refinement are the profile fit and *the chemical sense of the
structure* {cite}`mccusker1999`. `RefinementResult.geometry` is a
`GeometryTable` carrying them.

| Field | Is | Reads as |
|---|---|---|
| `GeometryTable.distances` | one `GeometryDistance` per neighbour | every asymmetric-unit atom's **whole** environment, so the number of rows naming an atom is its coordination number. A bond between two sites is therefore in the list twice, once from each end. |
| `GeometryTable.bonds` , `GeometryTable.contacts` | the two halves of that list | split by `GeometryDistance.bonded`: at most the two covalent radii plus `GeometryTable.bond_slack`, or beyond it out to `GeometryTable.contact_max`. The guidelines ask for both: "interatomic distances (both bonding and nonbonding) should be reasonable". |
| `GeometryTable.angles` | one `GeometryAngle` per pair of bonded neighbours | at every vertex, over that vertex's complete bonded environment. Contacts are not arms. |
| `GeometryTable.notes` | where coverage stopped | a per-atom contact cap or a phase too large to search. Empty means nothing was bounded. |

A row's value is `GeometryDistance.distance` in ångströms, or
`GeometryAngle.angle` in degrees. Each names its atoms twice. Once by the labels
the structure carries, as `GeometryDistance.atom_1` and
`GeometryDistance.atom_2`, with `GeometryAngle.atom_1`, `GeometryAngle.atom_2`
and `GeometryAngle.atom_3` putting the vertex in the middle. Once by index, as
`GeometryDistance.atom_index_1`, `GeometryDistance.atom_index_2`,
`GeometryAngle.atom_index_1`, `GeometryAngle.atom_index_2` and
`GeometryAngle.atom_index_3`, which index `Phase.atoms` directly.
`GeometryDistance.phase_index` and `GeometryAngle.phase_index` say which phase,
in a multi-phase fit.

`GeometryDistance.symmetry_2` is the CIF `n_klm` code of the image the second
atom sits at, and resolves against the operation list the exported CIF writes
beside it. `GeometryDistance.symmetry_1` is always `.`, the published position;
so is `GeometryAngle.symmetry_2`, the vertex, while `GeometryAngle.symmetry_1`
and `GeometryAngle.symmetry_3` code the two arms.

### The esd is the point

`GeometryDistance.stderr` is propagated through the **whole** parameter
covariance, which is what the guidelines require of any derived quantity: "the
whole correlation matrix, not just the diagonal elements, should be included in
the calculation" {cite}`mccusker1999`. Part 2 gives the propagation as equation
{eq}`est-derived`. `GeometryDistance.stderr_diagonal` is the same propagation
with the refined parameters' correlations zeroed, the number a reader combining
the printed parameter esds in quadrature would get. It is carried so the
difference is visible rather than asserted, and it is never the answer.
`GeometryAngle.stderr` and `GeometryAngle.stderr_diagonal` are the same pair, in
degrees.

```{image} figures/geometry-esd-light.png
:class: only-light
:alt: Diagonal-only esd divided by the full-covariance esd for each NAC distance, scattered from 0.86 to 1.41 on both sides of a dotted line at one
```

```{image} figures/geometry-esd-dark.png
:class: only-dark
:alt: Diagonal-only esd divided by the full-covariance esd for each NAC distance, scattered from 0.86 to 1.41 on both sides of a dotted line at one
```

Dropping the correlations is not a conservative approximation, and that is the
whole reason both numbers are reported. The figure is the 88 distances of an
11-BM NAC refinement under `mccusker_structural` (Rwp 0.0819), each plotted as
its diagonal-only esd over its full one: the ratio runs from 0.86 to 1.41, on
both sides of equality, so the cheap number is sometimes too small and
sometimes 40 % too large, with nothing in the row to say which.

The spread appears only once the *coordinates* refine. Under a plan that frees
the cell and nothing structural, a cubic phase's distances depend on one free
parameter, the quadratic form has one term, and the two esds agree to the last
digit. Correlation between coordinates is what the guideline is about, which is
also why a table quoted from a profile-only refinement has nothing to say here.

An esd is `None` when it cannot be measured, which is absence rather than
σ = 0. Four routes lead there, and they mean the same thing. A result with no
covariance behind it (any evaluate-only pass, a replay of a history node
included) has distances and no esds at all. So does a row nothing free
reaches. A row whose value is fixed by symmetry has no variance to report: a
fluorite Ca–F distance with the cell held, or a rutile O–Ti–O angle, which stays
at exactly 90° however the one free coordinate degree of freedom moves. And an
angle at 0° or 180° is a stationary point, where the linearisation behind
{eq}`est-derived` does not hold at all. The distance or angle itself is exact in
every one of the four; it is the uncertainty that is withheld.

Geometry is Rietveld-only. `RefinementResult.geometry` is `None` in Le Bail and
Pawley mode, where the dummy atom the mode requires is not a structure to
measure, and it is computed at the close of the fit rather than on demand: the
covariance it needs is read off the final Jacobian, which is never stored.

## How many observations there are

`Statistics.n_points` is the N the least-squares algorithm uses, and it is not
the number of observations the pattern holds. Only the integrated intensities of
individual reflections are unique observations {cite}`mccusker1999`; the profile
steps across one peak are repeated measurements of the same number. The
consequence is that the algorithm will refine far more parameters than the data
support, without complaining, because its N runs into the thousands.

`RefinementResult.data_support` is a `DataSupport` object carrying the count
that answers this. Part 2 states the correction it applies as equation
{eq}`est-mind`.

| Field | Is | Reads as |
|---|---|---|
| `DataSupport.n_unique_reflections` | reflections this pattern measured, summed over phases | one symmetry orbit is one reflection, and a Kα doublet's second line is the same reflection measured again, not a second observation. A reflection counts when a fitted channel lies within half its own FWHM of its position, so an excluded region removes what sits under it and a peak half-measured at a range end still counts. |
| `DataSupport.n_effective_observations` | the same count corrected for overlap | each reflection contributes the fraction of its own area on which no overlapping reflection stands higher, so an isolated line is worth 1 and an exactly coincident pair is worth 1 between the two of them. A **float**, because a partly resolved pair is worth more than one and less than two. |
| `DataSupport.n_structural_parameters` | the free parameters the ratio is about | the atomic ones: coordinate DOFs, occupancies, Biso, ADP components. The cell, zero, profile, background, scale, preferred orientation and extinction are excluded, because peak positions and shape determine those rather than the intensities being counted. |
| `DataSupport.observations_per_parameter` | the raw count divided by the parameters | the upper bound on the ratio. `None` when no structural parameter is free, which is a profile-only stage, a Le Bail fit or a Pawley fit. |
| `DataSupport.effective_observations_per_parameter` | the effective count divided by the parameters | **the number the guideline is about**: at least three and preferably five {cite}`mccusker1999`. `None` on the same terms as the row above. |

The complement of `DataSupport.n_structural_parameters` is
`Statistics.n_free_parameters` minus it: the profile, background and cell
parameters, which the same fit refined against the same pattern but which the
peak *positions* pay for.

`DataSupport.n_unique_reflections` over-counts, on purpose. Two reflections at
the same 2θ are one observation, and both are counted here. In a cubic cell that
pair is common: (300) and (221) coincide exactly. The raw count is therefore an
upper bound on the information, and the ratio built from it is optimistic.
`DataSupport.n_effective_observations` is the corrected number, by the method of
Altomare *et al.* {cite}`altomare1995`, and the gap between the two is the
pattern's overlap.

```{image} figures/effective-observations-light.png
:class: only-light
:alt: Reflection count flat at 26 while the effective observation count falls from 22 to 4 as the peaks broaden
```

```{image} figures/effective-observations-dark.png
:class: only-dark
:alt: Reflection count flat at 26 while the effective observation count falls from 22 to 4 as the peaks broaden
```

The figure is one Cu Kα LaB6 pattern over 15-140°, holding the cell and the
reflection list fixed and widening the peaks with Lorentzian size broadening
alone, so the overlap is the only thing that moves. Twenty-six reflections
throughout; 22.0 effective observations while the lines are sharp, and 3.7 by
the time the pattern is one hump. The raw count cannot see any of that, which
is what makes it the wrong denominator for a parameter ratio.

The estimate is not a theorem. The paper says so, and the IUCr guidelines
repeat it: the approach "may not have a rigorous basis", and what it gives is a
reasonable estimate of how many parameters the data will support. Two numbers a
reader should have with it: the interval each reflection is judged over is
±2 FWHM, and the paper's own check at ±4 FWHM lands 6.5 % lower on average, so
the reported figure is a little generous.

Nothing here refuses anything. The number is evidence, read beside the fit
rather than as a gate on it, and a ratio below three is a reason to hold
parameters rather than a reason the fit is wrong. The sharper question, *which*
parameter is unsupported rather than how many the pattern can carry, is the
next section. A ratio below five raises the `DATA_SUPPORT_LOW` diagnostic, as a
warning below three and as information between three and five.

## Which parameters the data could not separate

`RefinementResult.identifiability` is an `Identifiability`, and it exists because
these statistics cannot be recovered afterwards. They are read off the **final
Jacobian**, an N × P array nothing serializes (a history node stores state, not
curves), so they are screened at fit time or lost. Rwp and the residual, which
any consumer can recompute from the arrays already on the result, are the
contrast.

| Field | Is | Reads as |
|---|---|---|
| `Identifiability.background_absorption` | dot-path → the block projection R² of that structural column onto the background column span | how much of a parameter the background could imitate. Every screened path is here, not only the ones over the guard threshold: a fired/not-fired bit is a verdict, 0.46 against 0.08 is evidence, and these are the *same* numbers the `BACKGROUND_ABSORPTION` diagnostic decided on rather than a second measurement |
| `Identifiability.top_correlations` | the worst-\|ρ\| pairs, each a `CorrelationPair`, worst first | which two refined parameters moved together |
| `Identifiability.soft_modes` | the softest directions of the scale-normalised normal matrix, each a `SoftMode` | the same problem where it involves three parameters or more, which no pairwise list can show |
| `Identifiability.exchangeability` | one `ExchangeRow` per held parameter screened | whether a parameter you held could have been absorbed by the ones you refined |

| Field | Is |
|---|---|
| `CorrelationPair.path_a`, `CorrelationPair.path_b` | the two dot-paths |
| `CorrelationPair.rho` | their signed correlation, from the same final Jacobian the `HIGH_CORRELATION` guard read, so the two can never disagree |
| `SoftMode.eigenvalue` | of ĴᵀĴ with every column normalised to unit length, so it is dimensionless: for a single pair with correlation ρ it is 1 − \|ρ\|, and 0 is exact degeneracy |
| `SoftMode.loadings` | dot-path → component of the unit eigenvector, kept above 0.1 and signed so the largest is positive |
| `ExchangeRow.held` | the held parameter's dot-path |
| `ExchangeRow.r2` | the block projection R² of its column onto the span of the free ones, evaluated at the converged values with the candidate freed on a *copy* of the vary set, never refined |
| `ExchangeRow.partners` | dot-path → signed loading of the reconstruction, kept above 0.05: which fitted values absorb the held parameter's signature |

The softest modes are carried whatever their eigenvalues, because the number is
the evidence and deciding where comment starts is the report's job. Read
`ExchangeRow.r2` alone with care: it is a property of the design matrix over the
sampled range and fires on clean fits too, measured at 0.999945 on both a
degenerate fixture and its clean reference. The discriminating half, whether
anything significant is riding the exchange, is in [the report](report.md), whose
`ExchangeFinding` carries the fitted partner's value and esd beside the same R².
That chapter's `FitReport.identifiability` is a different type from this one, and
the warning there says how they differ.

## How finely the peaks were sampled

The other half of the question is about the experiment rather than the model.
There should be at least five steps across the top of each peak, and generally
not more than ten {cite}`mccusker1999`. Below five, the integrated intensity of
that reflection was never measured, and no refinement afterwards recovers it.

`PatternDiagnostics.steps_per_fwhm` is that number: the median, over the
pattern's resolved peaks, of how many channels span the peak's half-height
width. `PatternDiagnostics.n_peaks_measured` says how many peaks the median was
taken over. Both come from `diagnose(data)`, which needs no model, so this is a
question to ask of a file **before** refining it, and the answer does not change
afterwards:

<!-- api-doc: no-exec — it needs the reader's own pattern -->
```python
d = rx.diagnose(data)
print(d.steps_per_fwhm, "steps per FWHM over", d.n_peaks_measured, "peaks")
```

A refinement reports the same measurement on its fitted channels, as the
`PATTERN_UNDERSAMPLED` diagnostic, and only when it falls below five. There is
no code for the upper end of the band: oversampling costs beam time, not
validity.

### Everything else `diagnose` measures

The object that call returns is a `PatternDiagnostics`, and the two sampling
fields above are two of its fourteen. The rest describe the pattern itself, with
no model involved, and they are what the background chapter's defaults are chosen
from.

| Field | Is | Reads as |
|---|---|---|
| `PatternDiagnostics.n_points` | channels in the file | |
| `PatternDiagnostics.two_theta_min`, `PatternDiagnostics.two_theta_max` | the range, in degrees | |
| `PatternDiagnostics.noise_sigma_median` | the median channel noise | the scale a peak height is significant against |
| `PatternDiagnostics.peak_fraction` | share of channels more than 3σ above the background envelope | how much of the pattern is peak rather than background |
| `PatternDiagnostics.n_peaks` | resolved peaks found | |
| `PatternDiagnostics.peak_density_per_deg` | those per degree 2θ | above roughly 2/deg the pattern is dense, which favours a stiff baseline and a low background order |
| `PatternDiagnostics.signal_to_background` | near-maximum net signal over the median background level | |
| `PatternDiagnostics.air_scatter_gain` | how much of the envelope's cubic-fit residual variance a 1/(2θ) column explains | a nested-model test for the low-angle air-scatter rise; a high value is what turns the 1/x background term on |
| `PatternDiagnostics.amorphous_hump_score` | RMS of the envelope residual after *both* the cubic and the 1/x term, over the median level | what is left is genuinely broad non-polynomial structure (amorphous content, capillary glass), and calls for a more flexible background |
| `PatternDiagnostics.baseline_lambda` | the arPLS stiffness the whiteness rule picked for this pattern | |
| `PatternDiagnostics.steps_per_fwhm`, `PatternDiagnostics.n_peaks_measured` | the sampling pair above | null when no peak was measurable |
| `PatternDiagnostics.contamination` | Kβ and W Lα ghost candidates, each a `ContaminationFlag` | see the warning below |

| Field | Is |
|---|---|
| `ContaminationFlag.kind` | which ghost line it is consistent with |
| `ContaminationFlag.two_theta` | the weak peak's position |
| `ContaminationFlag.parent_two_theta` | the strong peak it would be a ghost of |
| `ContaminationFlag.intensity_ratio` | the weak peak's height over the parent's |

:::{warning}
An empty `PatternDiagnostics.contamination` means "nothing was flagged **or**
nothing was checked". The Kβ position is anode-specific, so the screen needs
`wavelength=`, and a wavelength matching no tabulated Kα1 is skipped silently.
Measured on the 11-BM pattern, `diagnose(data)` and
`diagnose(data, wavelength=0.4139090)` both return an empty list: the first
because nothing was asked, the second because a synchrotron wavelength has no
anode. On the round-robin corundum pattern at Cu Kα the same call returns three
flags, two Kβ ghosts and one tungsten Lα.
:::

## What the restraints did

If the fit carried soft restraints, `RefinementResult.restraints` is a
`RestraintReport`, and on a restrained refinement it is the first thing to read,
before Rwp. [](concepts.md) covers declaring them and scheduling their weight;
this is the object that comes back.

| Field | Is | Reads as |
|---|---|---|
| `RestraintReport.rows` | one `RestraintRow` per restraint | `RestraintRow.computed` against `RestraintRow.target`, with `RestraintRow.deviation` and `RestraintRow.deviation_over_sigma` the two ways of reading the gap, the second measured against the `RestraintRow.sigma` you declared, and `RestraintRow.weight` beside it. `RestraintRow.kind`, `RestraintRow.atoms`, `RestraintRow.path` and `RestraintRow.phase_index` say which restraint it was. |
| `RestraintReport.restraint_chi2` | Σ weight·(deviation/σ)² | the penalty term S_G of {eq}`par-restraint-weight`, at unit weight scale. |
| `RestraintReport.weight_scale` | the c_w the stage ran at | so the penalty the fit actually minimised is `RestraintReport.weight_scale` × `RestraintReport.restraint_chi2`. |
| `RestraintReport.n_restraints` | how many rows there were | the rows are in the covariance but out of Rwp, so this is not part of N. |

The deviations themselves are always reported unscaled, because "is this
restraint satisfied?" is a question about the geometry and c_w is a choice about
how hard to insist on the answer. A row past three σ raises `RESTRAINT_TENSION`:
the restraint and the data are pulling against each other, and one of them is
wrong. A joint fit reports the same object per histogram on
`HistogramResult.restraints`.

## What the statistics cannot tell you

They measure agreement, not correctness. A background flexible enough to imitate
the peaks biases displacement parameters up and phase fractions down *while Rwp
improves*. Of the eight corrections shipped in v0.5, two provably cannot move
Rwp, one moves it the wrong way when it is right, and the two largest accuracy
wins are invisible in it.

That is what [the report](report.md) is for, and why a correction in this
package ships with a record field or a diagnostic saying what it changed, rather
than with an Rwp comparison as its evidence.

## What the absorption correction did

`RefinementResult.absorption` is the worked example of that rule.
Specimen absorption is one seam with three geometries behind it, and one of them
provably cannot move Rwp: the capillary factor is exactly a constant times
exp(c·sin²θ), so applying it is an exact reparameterisation of the phase scale
and the displacement parameters. A comparison of fits would show nothing. The
`AbsorptionCorrection` record is where the correction says what it changed.

It is present only for a Rietveld fit that carried a specimen dimension, and
`None` otherwise, including for a fit that declared none, which is not the same
as a specimen of no thickness. [](data.md) covers declaring it.

| Field | Is | Reads as |
|---|---|---|
| `AbsorptionCorrection.method` | `rouse_cylinder`, `flat_plate_reflection` or `flat_plate_transmission` | which geometry's expression ran |
| `AbsorptionCorrection.mu_r` | the dimensionless µ·(length) | the capillary radius for the cylinder, the specimen thickness for the two plates |
| `AbsorptionCorrection.mu_r_source` | `given` or `estimated` | estimated means composition × packing × that length, so it inherits their uncertainty |
| `AbsorptionCorrection.wavelength` | the λ it was computed at | µ is wavelength-dependent, so the number is not portable between sources |
| `AbsorptionCorrection.equivalent_delta_biso` | the Biso bias, in Å², that refining **without** this correction would have absorbed | positive means add this to recover the unbiased value. For the cylinder this is the entire content of the correction |
| `AbsorptionCorrection.unabsorbed_fraction` | the share of ln A that a free scale and a free Biso cannot reproduce | zero for the cylinder to rounding, a few to tens of per cent for a plate, and hence how far to trust the ΔBiso above |
| `AbsorptionCorrection.identifiable_fraction` | the same measure applied to ∂lnA/∂µt | the number behind the decision not to make the thickness refinable |
| `AbsorptionCorrection.intensity_fraction_of_optimal` | µt·exp(1 − µt), transmission only | the counts this specimen delivered as a fraction of the best it could have. A specimen-preparation number no fit statistic can express: a badly chosen thickness costs counting statistics, not accuracy |
| `AbsorptionCorrection.out_of_range` | whether µR left the expression's validated range | |
| `AbsorptionCorrection.skipped` | why no correction ran, or null | absence with a reason attached |

The flat-plate cases are **not** exactly reparameterisable, which makes their
`AbsorptionCorrection.equivalent_delta_biso` a lower bound rather than the
answer: the projection behind it is unweighted while a refinement finds a
weighted compromise, and measured against synthetic refits the bias a fit really
absorbs runs 1.06 to 1.5× the predicted one, tracking
`AbsorptionCorrection.unabsorbed_fraction`.

## Diagnostics

`RefinementResult.diagnostics` is the channel for "your answer is wrong although
Rwp is fine". Each entry is a `Diagnostic` with a `Diagnostic.code`, a
`Diagnostic.level`, a human-readable `Diagnostic.message`, a
`Diagnostic.suggestion`, `Diagnostic.where` naming the parameter paths
involved, and `Diagnostic.value` carrying the headline number where the
diagnostic has one (a correlation's ρ, an absorption's block R²). `None`
means "no single number", not zero.

The codes are an open vocabulary, deliberately: a new correction ships with the
diagnostic that states what it changed. Read them before the statistics, every
time.

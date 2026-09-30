# How much of each phase

A multi-phase Rietveld fit refines one scale per phase, and those scales are
proportional to how much of each phase is there. Turning them into weight
fractions is the Hill-Howard relation {cite}`hill1987`, eq. {eq}`corr-qpa`:
W_p ∝ S_p·(Z·M·V)_p, renormalised across the phases.

The package does this whenever a Rietveld fit has more than one phase, and hands
it back on `RefinementResult.qpa`. Nothing has to be switched on.

<!-- api-doc: no-exec — refines a three-phase mixture, tens of seconds of solver time -->
```python
result = rx.refine(pattern, structure, instrument)
for row in result.qpa.phases:
    print(row.name, 100 * row.weight_fraction)
```

## The table

`QuantitativePhaseAnalysis` is the mixture-level answer.

| Field | Holds |
|---|---|
| `QuantitativePhaseAnalysis.phases` | one `PhaseQuantity` per phase |
| `QuantitativePhaseAnalysis.method` | `"zmv"`, the Hill-Howard route; the only one today |
| `QuantitativePhaseAnalysis.crystalline_only` | whether the fractions are of the crystalline content alone |
| `QuantitativePhaseAnalysis.microabsorption` | the `MicroabsorptionCorrection` record, when one ran |
| `QuantitativePhaseAnalysis.microabsorption_skipped` | why it did not, when something asked for it |

`PhaseQuantity` is one phase's row.

| Field | Holds |
|---|---|
| `PhaseQuantity.name` | the phase name |
| `PhaseQuantity.weight_fraction` | its mass fraction, 0 to 1 |
| `PhaseQuantity.weight_fraction_stderr` | that fraction's esd, or `None` |
| `PhaseQuantity.scale` | the refined Rietveld scale it came from |
| `PhaseQuantity.cell_mass` | Z·M, the mass in one unit cell |
| `PhaseQuantity.cell_volume` | V, in Å³ |
| `PhaseQuantity.zmv` | their product, the quantity the fractions are proportional to |
| `PhaseQuantity.z` | formula units per cell |
| `PhaseQuantity.molar_mass` | one formula unit's mass |
| `PhaseQuantity.particle_radius_um` | the radius you supplied, or `None` |
| `PhaseQuantity.mu_cm` | that phase's linear attenuation, cm⁻¹ |
| `PhaseQuantity.mu_r` | its µ·R |
| `PhaseQuantity.brindley_tau` | its Brindley particle-absorption factor |
| `PhaseQuantity.weight_fraction_corrected` | the fraction after that correction |

`PhaseQuantity.cell_mass` and `PhaseQuantity.cell_volume` are the unambiguous
quantities. `PhaseQuantity.z` and `PhaseQuantity.molar_mass` are a best-effort
split of the first into an integer count and a formula-unit mass, and they fall
back to `z = 1` with `molar_mass = cell_mass` when the composition does not
reduce to integers under refined occupancies. The weight fraction never depends
on that split, so a surprising `z` is a cosmetic problem and not a wrong
answer.

`PhaseQuantity.weight_fraction_stderr` is propagated from the correlated scale
block of the covariance rather than from σ(S) treated as independent, so it
carries the same conditioning as every other esd the package reports.

### A worked mixture

Fitting `cpd-1e` of the IUCr round-robin (corundum, zincite and fluorite,
weighed at 55.12, 15.25 and 29.62 wt %) reaches Rwp 0.126 and gives:

| Phase | W (%) | esd | Z | Z·M | V (Å³) | Weighed | Error |
|---|---|---|---|---|---|---|---|
| corundum | 57.33 | 0.52 | 6 | 611.77 | 254.75 | 55.12 | +2.21 |
| zincite | 12.93 | 0.27 | 2 | 162.76 | 47.60 | 15.25 | −2.32 |
| fluorite | 29.74 | 0.45 | 4 | 312.30 | 163.09 | 29.62 | +0.12 |

The errors are well inside the published participant spread for this sample,
and they are much larger than the esds. That is the normal state of affairs and
the first thing to understand about a QPA esd. It measures how well the scales
are determined by this model against this pattern, and not how close the answer
is to the truth.

## An esd describes one basin

`PhaseQuantity.weight_fraction_stderr` comes from the curvature of χ² at the
point the fit converged to. It describes the basin the fit stopped in, and it
cannot see any other. For most fractions that is the whole story. For a trace
phase it may not be.

A phase's scale and its peak width trade against each other. Broaden a weak
phase far enough and its peaks turn into a hump the background can share, and
then its scale can grow with almost no change in χ². Along that ridge the χ²
surface can hold separate basins at nearly the same χ². Each basin has ordinary
curvature, so each gives a tight esd, and the fit reports whichever basin it
reached.

This was measured on a lab Cu Kα in-situ series. At one pattern the fit
reported a phase at 1.41 ± 0.65 wt% with no diagnostic. Pinning that phase's
`lor_strain` at a series of values and refitting everything else found three
reproducible basins, at 0 %, about 1.5 % and 98.7 %. All three lay within
0.011 percentage points of Rwp of each other, and the lowest Rwp of the scan
belonged to the 98.7 % basin. Another program reported the same pattern at
25.3 ± 0.5 wt%, just as confidently. At the pattern taken 100 °C lower the same
scan spanned 0.636 percentage points of Rwp around a single minimum, 58 times as
much, so the problem belongs to that pattern and not to the setup.

No local quantity sees this, because every basin looks healthy from inside. The
check is the scan itself, a width profile, and `Refinement.profile_fraction`
runs it:

1. It pins one of the phase's width terms at a series of values, from no sample
   broadening at all up to a peak width of half the fitted range.
2. At each value it refits everything else, starting from where the previous
   value finished.
3. It reads the phase's weight fraction and the data's χ² at every point.

<!-- api-doc: no-exec — needs a fitted multi-phase refinement; tests/test_qpa_multimodal.py runs this call -->
```python
profile = ref.profile_fraction(data, "CaF2")
print(profile.range_low, profile.range_high, profile.excess)
for d in profile.diagnostics:
    print(d.code, d.message)
```

It is opt-in, because it costs one refit per point: twelve points for each
width term of the phase that was free in the last fit. Every refit runs on a
branch, so the working state and `Refinement.result_` are left as they were.
The axes are the phase's own `lor_strain`, `lor_size`, `gauss_strain` and
`gauss_size`, and never its scale. A refit at a pinned scale can reach the hump
basin only by broadening the phase until it drops below the noise, and at that
point the package holds the phase's structure for the stage, so the scan would
stop short of the basin it was looking for.

A point is admissible when its χ² is within
{{ FRACTION_PROFILE_DCHI2 }} × χ²_red × f² of the lowest χ²
the profile found, with f the fit's `Statistics.esd_inflation`. That is the 95 %
Δχ² for one parameter, scaled by the same two factors every esd already carries.
On a single well-behaved minimum it therefore reproduces W ± 1.96 esd. On the
test suite's control patterns every admissible fraction stayed inside that
interval, at most 0.79 of the way to its edge.

`FractionProfile` is the answer.

| Field | Holds |
|---|---|
| `FractionProfile.phase` | the phase's name |
| `FractionProfile.phase_index` | its position in the structure |
| `FractionProfile.axes` | the width paths that were pinned |
| `FractionProfile.weight_fraction` | the fit's fraction, copied from its QPA row |
| `FractionProfile.weight_fraction_stderr` | the fit's esd, or `None` |
| `FractionProfile.points` | one `FractionProfilePoint` per pinned value |
| `FractionProfile.chi2_fit` | the fit's own data χ², not reduced |
| `FractionProfile.chi2_best` | the lowest data χ² found, the fit's included |
| `FractionProfile.delta_chi2_cut` | the admissibility cut, in χ² |
| `FractionProfile.fit_admissible` | whether the fit's own point is within the cut |
| `FractionProfile.range_low` | the smallest admissible fraction |
| `FractionProfile.range_high` | the largest admissible fraction |
| `FractionProfile.excess` | the farthest admissible fraction from the fit's, in units of 1.96 esd |
| `FractionProfile.diagnostics` | the finding below, when it fires |

| Field | Holds |
|---|---|
| `FractionProfilePoint.axis` | the width path pinned |
| `FractionProfilePoint.value` | its value, in its own units |
| `FractionProfilePoint.fwhm` | that value as the phase's FWHM at mid-range, degrees 2θ |
| `FractionProfilePoint.admissible` | whether the point is within the cut |
| `FractionProfilePoint.weight_fraction` | the fraction the refit reached |
| `FractionProfilePoint.chi2` | its data χ² |
| `FractionProfilePoint.delta_chi2` | its distance above `FractionProfile.chi2_best` |
| `FractionProfilePoint.rwp` | its Rwp |
| `FractionProfilePoint.status` | how the refit's stage ended |
| `FractionProfilePoint.error` | why a refit raised, with the numbers left `None` |
| `FractionProfilePoint.node_id` | the history node the refit recorded |

The range is an inner bound. Each admissible point's fraction is inside the 95 %
profile interval for W, so a finer grid can only widen it. When
`FractionProfile.fit_admissible` is `False`, a pinned refit found χ² lower than
the fit's by more than the cut, which means the fit did not reach the lowest
basin along this ridge.

`QPA_FRACTION_UNDETERMINED` fires when an admissible fraction lies more than
{{ FRACTION_PROFILE_EXCESS }} times the esd's 95 % half-width from the fit's
fraction. That factor is a choice, not a measurement. The controls reached at most 0.79 and the synthetic
trace fixture reached about 75, so it sits well clear of both. The warning names
the range and the widths that produced it. A fraction it fires on is not
determined by this pattern, whatever its esd says, so quote the range rather
than the point. The basins separate only on information the fit does not have:
a width held at a value the specimen justifies, a background that can take the
hump itself, or more counts on the phase's strongest lines.

On that synthetic fixture, LaB₆ with a trace of CaF₂ and a small amorphous hump
under a six-term Chebyshev background, the fit reports CaF₂ at 1.19 ± 0.53 wt%.
The profile admits everything from 0.86 % to 77 %, in two basins separated by a
barrier the data can see.

This is a different failure from a wrong ZMV. A fraction is proportional to
scale × Z·M·V, and a wrong site multiplicity or a wrong space-group setting
(`SITE_SNAPPED_TO_SPECIAL_POSITION`, `SPACE_GROUP_SETTING_ASSUMED`) moves the
Z·M·V half. That error is a fixed multiplicative offset on one phase, at an
unchanged Rwp, and a width profile cannot see it. A width profile finds the
case where the pattern admits several fractions at once.

## What the fractions are fractions of

`QuantitativePhaseAnalysis.crystalline_only` is `True`, and it is not a caveat
to skim. The fractions are of the modelled crystalline content. They are
renormalised across the phases in the model, so they sum to 1 exactly whatever
is missing: in the mixture above, to 1.0 to nine decimal places.

Two things therefore do not show up as a shortfall:

- an amorphous fraction: glass, a poorly crystalline binder, an X-ray amorphous
  gel. The crystalline phases absorb it in proportion.
- a missing crystalline phase, one you did not put in the model. Its intensity
  is redistributed among the phases you did.

Neither is detectable from the fractions themselves, because both leave a set
that sums to 1. What does show them is the fit. An amorphous fraction is a broad
hump the background has to absorb, and a missing phase is a set of peaks with no
tick under them. [](report.md)'s Layer 0 is where both are named.
`PatternDiagnostics.amorphous_hump_score` is the pattern-level version of the
first: the RMS of what is left in the background envelope after a cubic and a
1/2θ term, relative to the median level, so what it measures is broad structure
that no ordinary background shape accounts for.

Internal-standard and amorphous quantification, spiking with a known weight of a
known phase and solving for the rest, is not implemented.

:::{admonition} For agents
:class: agent
Never report a weight fraction without the scope. "57.3 % corundum" is wrong if
the specimen is 20 % glass, while "57.3 % of the crystalline content" is right
either way. `crystalline_only` is `True` on every result this package produces today,
so the qualification is unconditional.
:::

## Microabsorption

Phases in a mixture do not all absorb the same. A strongly absorbing coarse
phase shadows its own particles' interiors, so its intensity is suppressed
relative to a weakly absorbing one and its weight fraction comes back low. This
is the Brindley microabsorption effect {cite}`brindley1945`, eq.
{eq}`corr-brindley`.

The correction needs a particle radius per phase, and there is no way to get one
from the pattern. Set `Phase.particle_radius_um` on every phase from a
micrograph or a particle-size measurement, and [](data.md) says why profile
broadening is not a substitute. Leave it `None` on any of them and the
correction does not run.

µ is the histogram's own radiation's. An X-ray histogram reads the McMaster
photoabsorption table by element, and a constant-wavelength neutron one reads
the Sears (1992) cross-sections by nuclide, the same two tables the capillary µR
estimate uses. A source with neither skips the correction and says why. Before
issue #543 a neutron fit was corrected with the X-ray µ, two to four orders of
magnitude too large. A nuclide in the structure (`D`, `2H`, `7Li`) enters the
cell mass at its own mass: 2.0141 for ²H, and the mass number otherwise, within
0.26 % of the nuclide's mass above A = 4.

When it does run, `QuantitativePhaseAnalysis.microabsorption` records what it
assumed.

| Field | Holds |
|---|---|
| `MicroabsorptionCorrection.method` | `"brindley_sphere"` |
| `MicroabsorptionCorrection.wavelength` | the primary line µ was evaluated at |
| `MicroabsorptionCorrection.mu_mean_cm` | the volume-weighted mean attenuation of the solid mixture |

The corrected fraction is reported alongside rather than substituted.
`PhaseQuantity.weight_fraction` stays the uncorrected Hill-Howard number and
`PhaseQuantity.weight_fraction_corrected` sits beside it. The esd belongs to the
uncorrected one. The corrected fraction inherits the systematic uncertainty of
the radii you supplied, which dominates and is not statistical, so quoting the
statistical esd against it would be a claim the package cannot support.

### The fence, and a case that fires it

Brindley's treatment is derived for the fine-to-medium powder regime, µ·D ≤ 0.1
with D the particle diameter, so µ·R ≤ {{ BRINDLEY_MU_R_FENCE }}. Past it the
expression is being used outside what it was derived for, and
`BRINDLEY_OUTSIDE_REGIME` says so and names the phases. `PhaseQuantity.mu_r`
travels with the answer for exactly that reason.

Sample 4 of the round robin is the dataset's designed microabsorption failure:
corundum, magnetite and zircon, weighed at 50.46, 19.64 and 29.90 wt %. With
order-of-magnitude radii of 0.5, 5.0 and 1.5 µm the fit reaches Rwp 0.279 and
gives:

| Phase | µ (cm⁻¹) | µR | τ | W (%) | Error | Corrected (%) | Error |
|---|---|---|---|---|---|---|---|
| corundum | 125.8 | 0.006 | 1.009 | 74.69 | +24.23 | 71.04 | +20.58 |
| magnetite | 1134.8 | 0.567 | 0.520 | 4.57 | −15.07 | 8.43 | −11.21 |
| zircon | 379.8 | 0.057 | 0.969 | 20.74 | −9.16 | 20.53 | −9.37 |

Read that table as three separate statements. The uncorrected errors have the
microabsorption shape, the two absorbing phases suppressed and the weakly
absorbing one inflated, which is the diagnosis. The correction moves the two
extremes toward the weighed values and leaves zircon slightly worse, the shape a
correction takes when it is applied outside its regime. And
`BRINDLEY_OUTSIDE_REGIME` fires on magnetite (µR = 0.567) and zircon
(µR = 0.057), so the corrected numbers arrive already labelled as not quotable.

The lesson is the one the package applies to every correction: the failure is
characterised rather than tuned away. A corrected fraction that is still 11 wt %
from the truth is no QPA result. It is evidence that this specimen needs a
different preparation.

## Writing it out

`Refinement.write_qpa_table` writes the table to a file, with the
crystalline-only caveat included; [](files.md) has it beside the other writers.
A joint fit reports the same object per histogram on `HistogramResult.qpa`, and
a series reports it per pattern on `SeriesEntry.qpa`, with
`SeriesResult.qpa_trajectory` turning one phase's fraction into a trajectory
across the series ([](series.md)).

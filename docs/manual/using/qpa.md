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
reduce to integers under refined occupancies. **The weight fraction never
depends on that split**, so a surprising `z` is a cosmetic problem and not a
wrong answer.

`PhaseQuantity.weight_fraction_stderr` is propagated from the **correlated**
scale block of the covariance, not from σ(S) treated as independent, so it
carries the same conditioning as every other esd the package reports.

### A worked mixture

Fitting `cpd-1e` of the IUCr round-robin — corundum, zincite and fluorite,
weighed at 55.12, 15.25 and 29.62 wt % — reaches Rwp 0.126 and gives:

| Phase | W (%) | esd | Z | Z·M | V (Å³) | Weighed | Error |
|---|---|---|---|---|---|---|---|
| corundum | 57.33 | 0.52 | 6 | 611.77 | 254.75 | 55.12 | +2.21 |
| zincite | 12.93 | 0.27 | 2 | 162.76 | 47.60 | 15.25 | −2.32 |
| fluorite | 29.74 | 0.45 | 4 | 312.30 | 163.09 | 29.62 | +0.12 |

The errors are well inside the published participant spread for this sample,
and they are much larger than the esds — which is the normal state of affairs
and the first thing to understand about a QPA esd. It measures how well the
scales are determined **by this model against this pattern**, not how close the
answer is to the truth.

## What the fractions are fractions of

`QuantitativePhaseAnalysis.crystalline_only` is `True`, and it is not a caveat
to skim. The fractions are of the **modelled crystalline content**. They are
renormalised across the phases in the model, so they sum to 1 exactly — in the
mixture above, to 1.0 to nine decimal places — whatever is missing.

Two things therefore do not show up as a shortfall:

- an **amorphous** fraction: glass, a poorly crystalline binder, an X-ray
  amorphous gel. The crystalline phases absorb it in proportion.
- a **missing crystalline phase**: one you did not put in the model. Its
  intensity is redistributed among the phases you did.

Neither is detectable from the fractions themselves, because both leave a set
that sums to 1. What does show them is the fit: an amorphous fraction is a broad
hump the background has to absorb, and a missing phase is a set of peaks with no
tick under them. [](report.md)'s Layer 0 is where both are named.
`PatternDiagnostics.amorphous_hump_score` is the pattern-level version of the
first — the RMS of what is left in the background envelope after a cubic and a
1/2θ term, relative to the median level, so what it measures is broad structure
that no ordinary background shape accounts for.

Internal-standard and amorphous quantification — spiking with a known weight of
a known phase and solving for the rest — is not implemented.

:::{admonition} For agents
:class: agent
Never report a weight fraction without the scope. "57.3 % corundum" is wrong if
the specimen is 20 % glass; "57.3 % of the crystalline content" is right either
way. `crystalline_only` is `True` on every result this package produces today,
so the qualification is unconditional.
:::

## Microabsorption

Phases in a mixture do not all absorb the same. A strongly absorbing coarse
phase shadows its own particles' interiors, so its intensity is suppressed
relative to a weakly absorbing one and its weight fraction comes back low —
the Brindley microabsorption effect {cite}`brindley1945`, eq.
{eq}`corr-brindley`.

The correction needs a particle radius per phase, and there is no way to get one
from the pattern. Set `Phase.particle_radius_um` on **every** phase from a
micrograph or a particle-size measurement ([](data.md) says why profile
broadening is not a substitute); leave it `None` on any of them and the
correction does not run.

When it does run, `QuantitativePhaseAnalysis.microabsorption` records what it
assumed.

| Field | Holds |
|---|---|
| `MicroabsorptionCorrection.method` | `"brindley_sphere"` |
| `MicroabsorptionCorrection.wavelength` | the primary line µ was evaluated at |
| `MicroabsorptionCorrection.mu_mean_cm` | the volume-weighted mean attenuation of the solid mixture |

**The corrected fraction is reported alongside, never substituted.**
`PhaseQuantity.weight_fraction` stays the uncorrected Hill-Howard number and
`PhaseQuantity.weight_fraction_corrected` sits beside it. The esd belongs to the
uncorrected one: the corrected fraction inherits the systematic uncertainty of
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
microabsorption **shape** — the two absorbing phases suppressed, the weakly
absorbing one inflated — which is the diagnosis. The correction moves the two
extremes toward the weighed values and leaves zircon slightly worse, which is
what a correction being applied outside its regime looks like. And
`BRINDLEY_OUTSIDE_REGIME` fires on magnetite (µR = 0.567) and zircon
(µR = 0.057), so the corrected numbers arrive already labelled as not quotable.

The lesson is the one the package applies to every correction: the failure is
characterised rather than tuned away. A corrected fraction that is still 11 wt %
from the truth is not a QPA result — it is evidence that this specimen needs a
different preparation.

## Writing it out

`Refinement.write_qpa_table` writes the table to a file, with the
crystalline-only caveat included; [](files.md) has it beside the other writers.
A joint fit reports the same object per histogram on `HistogramResult.qpa`, and
a series reports it per pattern on `SeriesEntry.qpa`, with
`SeriesResult.qpa_trajectory` turning one phase's fraction into a trajectory
across the series ([](series.md)).

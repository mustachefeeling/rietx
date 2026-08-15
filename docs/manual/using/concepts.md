# How a refinement works

A Rietveld refinement is one non-linear least-squares problem. The package
computes a pattern from the model, compares it with the measurement point by
point, and moves the free parameters to reduce the weighted sum of squares.

Almost everything that goes wrong is a *correlation*: two parameters change the
calculated pattern in nearly the same way, so the data cannot tell them apart,
and the solver splits the difference between them however the starting point
happened to lean. This chapter is about which parameters those are, what the
package does about it, and how to read the numbers that come back.

## The parameter groups

Every refinable quantity has a dot-path, and the paths group by what the
parameter does to the pattern.

| Group | Paths | Changes | Angular signature |
|---|---|---|---|
| scale | `phases.*.scale` | total intensity of each phase | flat in Q |
| background | `instrument.background.*` | the pedestal under the peaks | smooth in 2θ |
| position corrections | `instrument.zero_shift`, `instrument.geometry.sample_displacement` | where every peak sits | constant, cos θ |
| cell | `phases.*.cell.*` | where each peak sits, through its d-spacing | tan θ |
| instrument profile | `instrument.profile.u`, `.v`, `.w`, `.x`, `.y` | peak widths and shape | Gaussian: `w` constant, `v` tan θ, `u` tan²θ. Lorentzian: `x` tan θ, `y` 1/cos θ |
| sample broadening | `phases.*.gauss_size`, `phases.*.lor_size`, `phases.*.gauss_strain`, `phases.*.lor_strain` | the specimen's own width contribution | size 1/cos θ, strain tan θ |
| anisotropic strain | `phases.*.microstrain.dof.*` | width, per hkl rather than per θ | tan θ, scaled by direction |
| coordinates | `phases.*.atoms.*.dof.*` | relative peak intensities | none — it is an hkl effect |
| displacement | `phases.*.atoms.*.biso`, `phases.*.atoms.*.adp.*` | intensity falling off with Q | exp(−2B sin²θ/λ²) |
| occupancy | `phases.*.atoms.*.occ` | relative peak intensities | none |
| intensity corrections | `phases.*.preferred_orientation.r`, `phases.*.extinction`, `instrument.geometry.surface_roughness.*` | intensity, as a smooth or hkl-selective rescaling | various, all smooth in Q |

Coordinates and occupancies refine differently from the rest, and it matters
when you read a plan. A coordinate is not free in x, y and z; it is free along
the directions its site symmetry allows, and `ParameterTable` wires one
`phases.*.atoms.*.dof.*` entry per allowed direction and ties x, y and z to
them. A fully fixed special position contributes no entries at all, so the glob
is always safe to use, and setting `vary=True` on such a coordinate raises.

Anisotropic displacement parameters work the same way, through
`phases.*.atoms.*.adp.*`, and so do the fifteen Stephens strain coefficients
through `phases.*.microstrain.dof.*`. In each case the *symmetry-allowed
subspace* is derived from the space-group operators, and a value outside it
raises rather than being quietly symmetrised.

## Why the groups correlate

Two parameters are hard to separate when their effects on the pattern have the
same shape in 2θ. Over the whole range of a good dataset the shapes differ. Over
a short range they do not, and that is where the trouble is.

```{image} figures/angular-signatures-light.png
:class: only-light
:alt: Four angular signatures over 110 degrees, where they separate, and over 20 degrees, where they nearly coincide
```

```{image} figures/angular-signatures-dark.png
:class: only-dark
:alt: Four angular signatures over 110 degrees, where they separate, and over 20 degrees, where they nearly coincide
```

Each curve is normalised to 1 at the middle of its range, because separability
is a question about *shape* and not about scale: two effects that differ only by
a constant factor are one parameter, whatever their sizes. On the left, over
110° of data, the four are plainly different functions. On the right, over 20°,
three of them are within a few per cent of each other and of a straight line.
A refinement over that range reports four numbers and measures rather fewer.

| Correlated group | Signatures | What goes wrong |
|---|---|---|
| zero shift · sample displacement · cell | constant · cos θ · tan θ | over a narrow 2θ range these three are collinear. A cell refined against a free zero shift on 20° of data is not measured. |
| crystallite size · microstrain | 1/cos θ · tan θ | the Williamson-Hall separation. Over a short range they are one parameter, not two. |
| scale · displacement · background · absorption · surface roughness · extinction | all smooth in Q | the big one. Every member lifts or depresses intensity smoothly with angle, so any of them can absorb any other. |
| preferred orientation · occupancy | both rescale specific hkl | an occupancy refined against uncorrected texture is a texture measurement. |
| overlapped intensities (Le Bail, Pawley) | identical | the *sum* is determined by the data; the split is not. |

Two of those groups are worse than correlated. Capillary absorption is *exactly*
a reparameterisation of the scale and the displacement parameters — the fit is
identical with and without it — so `Geometry.mu_r` is computed from the specimen
and never refined. Flat-plate absorption is 60 to 99 % absorbable, so
`Geometry.mu_t` is also computed rather than refined; the part that is not
absorbable does move Rwp, and a wrong thickness lands partly in the fit and
partly in the displacement parameters.

Two rules follow, and they are the reason plans exist:

1. **Do not free the second member of a group until the first is pinned by
   something outside the fit.** This is what the `lab_calibrate` workflow is
   for: refining a certified standard with its **cell held fixed** is what
   decorrelates zero shift from displacement from cell, because the cell is
   supplied rather than fitted.
2. **A correlation above 0.98 means you refined one parameter and reported
   two.** The package raises `HIGH_CORRELATION` when that happens. The answer is
   almost never to widen the bounds. Fix one of the pair, extend the data range
   until the signatures separate, or — where chemistry says the two quantities
   are the same quantity — constrain them to each other.

## Constraining parameters to each other

A **constraint** makes two parameters one: the dependent leaves the free vector
and follows its source exactly, so the parameter count drops by one and the
observation-to-parameter ratio rises. That is different from a restraint, which
adds an observation (a bond length, say) with a weight and leaves the parameter
count alone.

Use one where the data cannot separate two quantities and chemistry says they
need not be separated. Two of the cases the guidelines {cite}`mccusker1999`
recommend are available here: equal displacement parameters across atoms in the
same environment, and occupancies that must sum to a known total. The third,
rigid bodies, is not.

<!-- api-doc: no-exec — it needs the reader's own structure and instrument -->
```python
ref = rx.Refinement(structure, instrument)

# the three oxygens of one phosphate group refine as one B
ref.tie_equal(["phases.0.atoms.4.biso",
               "phases.0.atoms.5.biso",
               "phases.0.atoms.6.biso"])

# a mixed site: occupancies that sum to 1
ref.tie("phases.0.atoms.1.occ", "phases.0.atoms.0.occ", scale=-1.0, offset=1.0)

ref.untie("phases.0.atoms.*.biso")     # release them again
```

`Refinement.tie_equal` takes the same fnmatch globs as `set_vary`, and the
first match in table order carries the freedom while the rest follow it; pass
`source` to choose a different one. `Refinement.tie` is the general affine
form, `value = scale·source + offset`, of which `tie_equal` is the
`scale=1, offset=0` case, and `Refinement.untie` releases them. Each verb
records a history node, so a constrained refinement replays as one, and a
project reopens with the constraint still in force.

A tie shows up in the parameter listing as a held row: `refinable` is false,
`held_because` names the sources, and `TieSpec.user` is true for the ones you
declared. The ties the space group creates — `b` following `a` in a tetragonal
cell, a coordinate following its site-symmetry direction — read the same way
with that flag false, and they cannot be released: symmetry outranks a user tie
everywhere the two meet.

The verbs refuse rather than approximate. A locked parameter, an already-tied
one, a source that is itself tied (which would make a chain), a target the
current intensity mode force-fixes, and an implied value outside the target's
own bounds are all refused with the reason and the parameter holding it.

:::{admonition} What a constraint buys, and how to check it was earned
:class: tip

Fluorapatite on a laboratory diffractometer, refined twice under one protocol
— the second time with the three phosphate oxygens' `biso` tied together:

| | free | tied |
|---|---|---|
| free parameters | 20 | 18 |
| observations per parameter | 287.5 | 319.4 |
| Rwp | 0.097307 | 0.097355 |
| B(O5) / Å² | 0.2763(1810) | 0.4138(899) |
| B(O6) / Å² | 0.5279(1911) | 0.4138(899) |
| B(O7) / Å² | 0.4149(1282) | 0.4138(899) |

The return is precision: the constrained esd is smaller than the best of the
three free ones. Rwp is not the evidence and cannot be — it moved by 0.05 % of
itself, which is what "the constraint costs no fit quality" looks like.

The check to run first is in the free column. Each of the three intervals
contains the tied value, so the free refinement does not contradict the claim
that these are one parameter. Where the free values disagree by more than
their esds, the atoms are telling you they are not in the same environment, and
tying them replaces a measurement with an assumption.
:::

## Refinement plans

Because the groups correlate, freeing everything at once from a poor starting
point walks into a local minimum that a staged release avoids. A fit here is
therefore a *plan*: a list of stages, each freeing one group and running to
convergence before the next group joins. Parameters stay free once freed, so
each stage refines everything released so far.

`RefinementPlan` carries the presets, named for the job each does:

```python
import rietx as rx

rx.RefinementPlan.mccusker_default()      # scale+bkg -> zero -> cell -> W -> U,V,X,Y
rx.RefinementPlan.mccusker_structural()   # ... then coordinates, displacement, PO
rx.RefinementPlan.lab_bragg_brentano()    # ... with sample displacement, Ka2, FCJ axial
rx.RefinementPlan.lab_calibrate()         # instrument calibration, certified cell HELD
rx.RefinementPlan.lab_sample_refine()     # sample against a frozen calibrated instrument
rx.RefinementPlan.profile_only()          # Le Bail
rx.RefinementPlan.pawley_default()        # Pawley
```

The two standard presets are one chain. `mccusker_default` stops after the
widths; `mccusker_structural` continues into the structure:

```{mermaid}
graph TD
  subgraph a ["mccusker_default"]
    A["scale + background"] --> B["zero shift"] --> C["cell"]
    C --> D["W, the constant width"] --> E["U, V, X, Y"]
  end
  subgraph b ["mccusker_structural adds"]
    F["coordinates"] --> G["displacement"] --> H["preferred orientation"]
    H --> I["extinction"] --> J["surface roughness"]
  end
  E --> F
```

Each box is a `Stage`. Every stage runs to convergence with everything above it
still free.

`Refinement.fit` also takes a plan by name (`plan="mccusker_default"`).
`PLAN_INFO` reports each preset's title, description, modes and when to use it,
so a program can offer the choice without hard-coding a list.

A plan is an ordinary object, so you can edit it:

<!-- api-doc: no-exec — it needs the reader's own structure and instrument -->
```python
plan = rx.RefinementPlan.mccusker_default()
plan.stages.append(rx.Stage("biso", ["phases.*.atoms.*.biso"]))
result = ref.fit(data, plan=plan)
```

`Stage` takes fnmatch globs over the dot-paths, which is why paths carry no
brackets: fnmatch reads `[..]` as a character class rather than an index.

### The order the presets encode

The backbone is the order McCusker et al. {cite}`mccusker1999` set out in the
IUCr Rietveld refinement guidelines:

1. **Background and scale first.** The guidelines want good starting values for
   the background before the structure is touched, and the calculated pattern
   scaled to the observed one before anything is read off a difference plot.
2. **Peak positions before everything else.** The cell and the 2θ correction —
   the zero shift, plus sample displacement where the geometry has one — refine
   before the widths and before the structure. The guidelines put it flatly:
   unless the observed and calculated peak positions match, a Rietveld
   refinement cannot and will not work.
3. **Then the widths, then the asymmetry.** `mccusker_default` stops after the
   widths. `lab_bragg_brentano` and `lab_calibrate` continue in the guidelines'
   order with a `lines_axial` stage — the FCJ axial-divergence ratios and the
   Kα2 weight — after them.
4. **Then the structure: coordinates, then displacement parameters.** The
   guidelines note that the scale, the occupancies and the displacement
   parameters are correlated with each other and are the parameters most
   sensitive to a background error, so they follow the positions rather than
   accompany them.
5. **Everything free together at the end.** Stages are cumulative for a reason
   the guidelines state explicitly: the esds are only correct when all
   parameters, profile and structural, are refined simultaneously. The last
   stage of every preset does that.

One departure: the guidelines suggest refining the heavier atoms' positions
before the lighter ones, and `mccusker_structural` frees every coordinate in one
`coordinates` stage. Nothing here measures what the split would buy. If your
structure has a large scattering contrast and a poor starting model, split that
stage yourself — a plan is an ordinary object.

Three further ordering rules are this package's own rather than the guidelines':

- **Widths last among the profile terms, and `w` before `u`, `v`, `x`, `y`.**
  `w` is the constant term of the Gaussian width. Free the tan θ and 1/cos θ
  terms first and they absorb a constant offset, then fight it when `w` joins.
- **Intensity-scaling corrections go last, after the structure has settled.**
  Preferred orientation, extinction and surface roughness all rescale
  intensities as a function of Q — and so do the scale, the occupancies and the
  displacement parameters. Free a correction early and it eats intensity that
  belongs to the structure.
- **Anisotropic strain is freed *inside* the sample-broadening stage, not after
  it.** A Stephens block locks `phases.*.lor_strain`, because the isotropic
  direction of the block is identically that column. Deferring the block would
  leave the isotropic width unrefined until fifteen correlated coefficients turn
  on at once.

:::{admonition} For automated callers
:class: agent
[`docs/AGENT_PROTOCOL.md`](https://github.com/yue-here/rietx/blob/main/docs/AGENT_PROTOCOL.md)
§2 and §3 give the same order as an operating discipline, with the measured
findings behind each rule — including what a Le Bail pass does that one `fit`
call cannot.
:::

## Fit statistics

`RefinementResult.statistics` is a `Statistics` object. The definitions follow
Toby {cite}`toby2006`, and Part 2 gives them as equation
{eq}`est-indices`.

| Field | Is | Reads as |
|---|---|---|
| `Statistics.rwp` | the weighted profile R-factor | how well the calculated pattern matches the measured one, weighted by the counting statistics. A **fraction**: 0.0932 is 9.3 %. |
| `Statistics.rp` | the unweighted profile R-factor | the same comparison with every point weighted equally, so strong peaks dominate it. |
| `Statistics.rexp` | the expected R-factor | the Rwp that perfect counting statistics alone would produce. It is a property of the data and the parameter count, not of the model. |
| `Statistics.chi2` | the **reduced** χ², Σw δ²/(N − P) | how far the fit is from statistical perfection. 1.0 means the residual is the size of the noise. |
| `Statistics.gof` | Rwp / Rexp | the square root of `Statistics.chi2`. Also called S or χ. |
| `Statistics.rwp_background_subtracted` | Rwp with the background removed from both patterns | the more meaningful figure when the background carries most of the raw intensity. |
| `Statistics.durbin_watson` | the serial-correlation statistic | ≈ 2 means neighbouring residuals are independent. Far from 2 means the misfit is structured, whatever Rwp says. |
| `Statistics.esd_inflation` | the Bérar-Lelann factor | the amount the reported esds were multiplied by to account for that serial correlation. It has **already been applied**. |
| `Statistics.n_points` , `Statistics.n_free_parameters` | N and P | what makes the rest interpretable. |

**`Statistics.chi2` is the reduced χ², not Σw δ².** The two differ by a factor
of N − P, which on a real pattern is several thousand.

**The literature is not consistent about which of the two is called χ².** The
IUCr guidelines {cite}`mccusker1999` write χ² = Rwp/Rexp and say it should
approach 1; that quantity is `Statistics.gof` here, and `Statistics.chi2` is its
square. Both conventions say the same thing about a fit — the naming follows
Toby {cite}`toby2006` — but a number copied from a paper needs the convention
copied with it.

`Statistics.esd_inflation` is conservative by construction. Perfectly white
residuals still land near 1.51, because same-sign runs happen by chance, and lab
data with unmodelled profile detail typically lands at 2 to 4. Treat it as an
upper bound on the serial-correlation damage rather than as a measurement of it.

### Structure agreement indices

Every field above measures the *pattern*. Two more measure the **structure**, and
a journal will ask for at least one of them {cite}`mccusker1999`. They live on
`RefinementResult.phase_agreement`, one `PhaseAgreement` row per phase, keyed by
`PhaseAgreement.name` — the same name the phase carries everywhere else.

| Field | Is | Reads as |
|---|---|---|
| `PhaseAgreement.r_bragg` | R_B, the Bragg-intensity R-factor | how well the model reproduces the *integrated intensities* I = m·F², m the multiplicity — rather than the profile. Written to a CIF as `_refine_ls_R_I_factor`. |
| `PhaseAgreement.r_f` | R_F, the structure-factor R-factor | the same comparison on the amplitude rather than the intensity, so it is the number a single-crystal R is directly comparable with. Written as `_refine_ls_R_factor_all`. |
| `PhaseAgreement.n_reflections` | how many reflections were summed | smaller than the phase's reflection list whenever one falls off the Ewald sphere. |

A joint multi-histogram fit reports them per histogram, on
`HistogramResult.phase_agreement`: the partition is of one pattern's counts, so
there is no pooled value.

**Both are biased towards the model you are testing.** A powder pattern does not
measure individual reflection intensities — overlapped peaks share their counts —
so the "observed" intensity of each reflection is the observed pattern
*partitioned in proportion to the calculated one*. A wrong model therefore
receives the intensity it predicted, and both indices flatter it. That is the
paper's own warning, and it fixes what they are for: watching an R_B fall as you
improve a model, not judging a model in isolation.

**A trace phase's R_B is not comparable with the major phase's.** Neither index
is weighted — the sums count every reflection alike, whatever its counting
statistics — so a reflection the fit barely constrains weighs as much as one
that dominates it, and a minor phase's windows sit under
the major phase's peaks, where the counts the major phase failed to describe are
handed out too. Measured on the 11-BM NAC pattern with its 1.35 wt % CaF₂
impurity: NAC reads R_B 0.052 and the impurity 0.385, with the whole of the
impurity's misfit in four reflections at I(obs)/I(calc) ≈ 2.2 — every one of
them under a strong NAC peak with a large positive residual. Read R_B beside the
phase's weight fraction, and treat a trace phase's value as a question rather
than a measurement.

Both are absent — an empty list — for a Le Bail or Pawley fit. There the
intensities *are* the fit, so the partition would be compared against itself.

### How many observations there are

`Statistics.n_points` is the N the least-squares algorithm uses, and it is not
the number of observations the pattern holds. Only the integrated intensities of
individual reflections are unique observations {cite}`mccusker1999`; the profile
steps across one peak are repeated measurements of the same number. The
consequence is that the algorithm will refine far more parameters than the data
support, without complaining, because its N runs into the thousands.

`RefinementResult.data_support` is a `DataSupport` object carrying the count
that answers this.

| Field | Is | Reads as |
|---|---|---|
| `DataSupport.n_unique_reflections` | reflections this pattern measured, summed over phases | one symmetry orbit is one reflection, and a Kα doublet's second line is the same reflection measured again, not a second observation. A reflection counts when a fitted channel lies within half its own FWHM of its position, so an excluded region removes what sits under it and a peak half-measured at a range end still counts. |
| `DataSupport.n_effective_observations` | the same count corrected for overlap | each reflection contributes the fraction of its own area on which no overlapping reflection stands higher, so an isolated line is worth 1 and an exactly coincident pair is worth 1 between the two of them. A **float**, because a partly resolved pair is worth more than one and less than two. |
| `DataSupport.n_structural_parameters` | the free parameters the ratio is about | the atomic ones: coordinate DOFs, occupancies, Biso, ADP components. The cell, zero, profile, background, scale, preferred orientation and extinction are excluded — peak positions and shape determine those, not the intensities being counted. |
| `DataSupport.observations_per_parameter` | the raw count divided by the parameters | the upper bound on the ratio. `None` when no structural parameter is free, which is a profile-only stage, a Le Bail fit or a Pawley fit. |
| `DataSupport.effective_observations_per_parameter` | the effective count divided by the parameters | **the number the guideline is about**: at least three and preferably five {cite}`mccusker1999`. `None` on the same terms as the row above. |

The complement of `DataSupport.n_structural_parameters` is
`Statistics.n_free_parameters` minus it — the profile, background and cell
parameters, which the same fit refined against the same pattern but which the
peak *positions* pay for.

**`DataSupport.n_unique_reflections` over-counts, on purpose.** Two reflections
at the same 2θ are one observation, and both are counted here. In a cubic cell
that pair is common — (300) and (221) coincide exactly — so the raw count is an
upper bound on the information, and the ratio built from it is optimistic.
`DataSupport.n_effective_observations` is the corrected number, by the method of
Altomare *et al.* {cite}`altomare1995`, and the **gap between the two is the
pattern's overlap**. Measured on a Cu Kα LaB6 pattern over 15-140°, holding the
cell and the reflection list fixed and widening the peaks with Lorentzian size
broadening alone: 26 reflections throughout, and 22.0, 17.2, 10.2, 3.9 effective
observations as the broadening goes from none to enough to merge the pattern
into one hump. The raw count cannot see any of that.

**The estimate is not a theorem.** The paper says so, and the IUCr guidelines
repeat it: the approach "may not have a rigorous basis", and what it gives is a
reasonable estimate of how many parameters the data will support. Two numbers a
reader should have with it: the interval each reflection is judged over is
±2 FWHM, and the paper's own check at ±4 FWHM lands 6.5 % lower on average, so
the reported figure is a little generous.

**Nothing here refuses anything.** The number is evidence, read beside the fit
rather than as a gate on it, and a ratio below three is a reason to hold
parameters rather than a reason the fit is wrong. The sharper question — *which*
parameter is unsupported, rather than how many the pattern can carry — is the
identifiability evidence in [the report](report.md).

### What the statistics cannot tell you

They measure agreement, not correctness. A background flexible enough to imitate
the peaks biases displacement parameters up and phase fractions down *while Rwp
improves*. Of the eight corrections shipped in v0.5, two provably cannot move
Rwp, one moves it the wrong way when it is right, and the two largest accuracy
wins are invisible in it.

That is what [the report](report.md) is for, and why a correction in this
package ships with a record field or a diagnostic saying what it changed, rather
than with an Rwp comparison as its evidence.

## Diagnostics

`RefinementResult.diagnostics` is the channel for "your answer is wrong although
Rwp is fine". Each entry is a `Diagnostic` with a `Diagnostic.code`, a
`Diagnostic.level`, a human-readable `Diagnostic.message`, a
`Diagnostic.suggestion`, and `Diagnostic.where` naming the parameter paths
involved.

The codes are an open vocabulary, deliberately: a new correction ships with the
diagnostic that states what it changed. Read them before the statistics, every
time.

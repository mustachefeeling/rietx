# A first refinement

A fit takes three objects and returns one. You supply a `PatternData` from
`read_pattern`, a `Structure` from a CIF, and an `Instrument` that describes the
diffractometer. The package returns a `RefinementResult`.

Throughout this manual, the `examples/` scripts, and the API calls the history
prints back at you, `rietx` is imported as `rx`.

<!-- api-doc: no-exec — it reads a pattern file the reader supplies -->
```python
import rietx as rx

data = rx.read_pattern("my_sample.xye")
structure = rx.Structure.from_cif("my_phase.cif")
instrument = rx.Instrument.debye_scherrer(wavelength=0.4139090)

result = rx.refine(data, structure, instrument)
print(result.status, result.statistics.rwp)
```

The print line writes two values:

```text
converged 0.0932
```

`RefinementResult.status` is a plain string: `converged`, `max_iter` or
`diverged`. `max_iter` means the solver ran out of iterations. It does not mean
the fit failed.

One more line draws the fit:

<!-- api-doc: no-exec — it needs a result from the reader's own data -->
```python
result.plot(path="my_sample.png", two_theta_range=(2.0, 12.0))
```

```{image} figures/nac-fit-light.png
:class: only-light
:alt: Observed, calculated and difference curves for the NAC fit, with a delta over sigma panel below
```

```{image} figures/nac-fit-dark.png
:class: only-dark
:alt: Observed, calculated and difference curves for the NAC fit, with a delta over sigma panel below
```

Observed points, the calculated line, one row of reflection ticks per phase,
and Δ/σ in the lower panel. The difference is *weighted* by default, because a
raw difference shares the intensity axis and the eye then reads a small
deviation on a strong peak as a large error. Δ/σ has expectation 1 under a
correct model, so the ±3 band is an absolute scale rather than a relative one.
Pass `weighted=False` for the classic offset raw difference, and `style="dark"`
for a figure going onto a dark page.

**`Statistics.rwp` is a fraction, not a percentage.** 0.0932 is the Rwp of 9.3 %
you would quote in a paper. Every R-factor in the package is stored this way.
[](concepts.md) says what each statistic measures.

## `refine` or a `Refinement` session

`refine` runs one fit and discards the session. It is the right call when one
fit is all you need, and it keeps no history unless you ask for one
(`history=True`).

The object form keeps the session:

<!-- api-doc: no-exec — it refines the reader's own pattern -->
```python
ref = rx.Refinement(structure, instrument)
result = ref.fit(data, plan="mccusker_default")
result = ref.fit(data, plan="mccusker_structural")   # continues from the first
```

`Refinement` holds the models between calls, so the second `fit` starts where
the first stopped rather than from the CIF. Three things come with that:

- `Refinement.fitted_structure` and `Refinement.fitted_instrument` return the
  models as the last fit left them.
- `Refinement.history` records every stage as a restorable node, and it is on by
  default here. `Refinement.edit` puts a change to the *model* on the same
  record, so adding a phase is a recorded move rather than a fresh start.
- `Refinement.report` builds the `FitReport` with the compiled model attached,
  which `build_report` on a bare result cannot do.

Reach for the object form as soon as a fit needs a second attempt, which in
practice is most of the time.

## Le Bail before Rietveld

One decision matters more than any plan: **get the peaks into the right places
before you ask a structure to explain their intensities.**

A Le Bail fit (`mode="lebail"`) refines the cell, the zero shift and the profile
with the intensities extracted per reflection instead of computed from the
structure. It therefore converges from a much worse start, and it tells you
whether the cell and the profile are right *independently of whether the
structure is*. Only then does a Rietveld fit (`mode="rietveld"`, the default)
face a fair question.

It pays a second time. A Le Bail report flags observed peaks the model does not
account for, so an impurity phase shows up as unmatched peaks at positions you
can identify — before it can distort a structural refinement by being absorbed
into a background or a width.

```{image} figures/impurity-peak-light.png
:class: only-light
:alt: Two zoomed panels near 7.5 degrees; the left has an observed peak with no calculated intensity, the right fits it
```

```{image} figures/impurity-peak-dark.png
:class: only-dark
:alt: Two zoomed panels near 7.5 degrees; the left has an observed peak with no calculated intensity, the right fits it
```

That is the mechanism in one picture, from the worked example below. The Le Bail
fit knows nothing about CaF₂, so the line at 7.52° is observed intensity the
model cannot place, and the report says so. Adding the phase accounts for it.

## Worked example: NAC on 11-BM

This is `examples/nac_11bm.py`, which the test suite runs on every push. It
refines Na₂Ca₃Al₂F₁₄ against APS 11-BM synchrotron data: Le Bail first, then the
CaF₂ impurity its report exposes, then Rietveld.

```{literalinclude} ../../../examples/nac_11bm.py
:language: python
:caption: examples/nac_11bm.py
```

Six things in it recur in every fit after this one:

- **One `Refinement` is the session.** `Refinement.fit` can be called again, and
  the models carry over.
- **Every stage commits a node.** `Refinement.history` holds both refinements
  *and* the model edit between them, and `RefinementTree.tag` names a node to
  come back to.
- **A plan is editable.** `plan.stages.append(rx.Stage("biso", [...]))` adds a
  displacement stage after the preset's, and `Stage` takes fnmatch globs over
  the parameter dot-paths (`phases.*.atoms.*.biso`).
- **`RefinementResult.parameter`** looks one parameter up by path, with its esd:
  `result.parameter("phases.0.cell.a").stderr`.
- **`RefinementResult.diagnostics`** is the channel for "your answer is wrong
  although Rwp is fine". Read it every time. [](report.md) says what the codes
  mean and what they do not.
- **`build_report`** turns the result into a `FitReport`: where the misfit is,
  what would fix it, and whether the package is confident enough to say so.

## The `RefinementResult` object

`RefinementResult.status` says whether the solver converged.
`RefinementResult.statistics` carries the agreement indices, of which
`Statistics.rwp` and `Statistics.gof` are the two usually quoted, and
`Statistics.n_points`, `Statistics.n_free_parameters` and
`Statistics.esd_inflation` are what make them interpretable.

The curves are on the result as `RefinementResult.y_obs`,
`RefinementResult.y_calc` and `RefinementResult.y_background`, over
`RefinementResult.two_theta`. `RefinementResult.plot` writes an
observed/calculated/difference figure with matplotlib (the `viz` extra).

**Rwp is not the answer.** It is a fit statistic, and this package can show you a
fit whose Rwp improved while its displacement parameters and phase fractions
moved *away* from the truth. What the package hands you instead is
[the report](report.md).

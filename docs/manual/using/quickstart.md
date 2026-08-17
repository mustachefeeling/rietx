# A first refinement

A fit takes three objects and returns one. You supply a `PatternData` from
`read_pattern`, a `Structure` from a CIF, and an `Instrument` that describes the
diffractometer. The package returns a `RefinementResult`.

Throughout this manual, the `examples/` scripts, and the API calls the history
prints back at you, `rietx` is imported as `rx`.

## The minimal call

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

`RefinementResult.status` is a plain string, one of `converged`, `max_iter` and
`diverged`. The second of those means the solver ran out of iterations. It does
not mean the fit failed.

**`Statistics.rwp` is a fraction, not a percentage.** 0.0932 is the Rwp of 9.3 %
you would quote in a paper. Every R-factor in the package is stored this way.
[](results.md) says what each statistic measures.

One more line draws the fit:

<!-- api-doc: no-exec — it needs a result from the reader's own data -->
```python
result.plot(path="my_sample.png", two_theta_range=(2.0, 12.0),
            wavelength=0.4139090)
```

```{image} figures/nac-fit-light.png
:class: only-light
:alt: Observed points, calculated line, the obs minus calc difference below them and one row of reflection ticks per phase below that
```

```{image} figures/nac-fit-dark.png
:class: only-dark
:alt: Observed points, calculated line, the obs minus calc difference below them and one row of reflection ticks per phase below that
```

Reading down: observed points, the calculated line, the `obs − calc` difference
on the same axis at the same scale, then one row of reflection ticks per phase.
The residual sits directly under the peaks that caused it, and nothing comes
between them. Every series is named in the right-hand margin rather than in a
legend the eye has to look up; the fit statistics sit in the corner, because a
figure's title is its caption. `two_theta_range` is a *window*, not a crop — the
intensity scale and the rows below it are built from what the window contains,
so a zoom into a weak region is a figure of its own data.

`weighted=True` draws Δ/σ instead, in its own panel with a ±3σ band: a raw
difference shares the intensity axis, so the eye reads a small deviation on a
strong peak as a large error, while Δ/σ has expectation 1 under a correct model
and the band is an absolute scale rather than a relative one. It is not the
default because it costs the one thing the classic layout gives away free — the
residual and the peak that caused it in a single glance.

`wavelength=` puts λ on the 2θ axis, which is meaningless without it; the result
does not carry the emission line, so it has to be passed. It is also what
`x_axis="q"` and `x_axis="d"` are derived through, and those two carry no λ of
their own — that is the point of them. `y_scale=` takes `"sqrt"` (equal display
distance for equal counting σ), `"log"` or `"asinh"`; any of them moves the
difference into its own panel, since an offset raw difference is negative by
construction and a nonlinear intensity axis cannot draw it. `style="dark"` is
for a figure going onto a dark page, and `figsize=`/`font_size=` are the
exposure surface: build the figure at the width it will be read at rather than
scaling it in the document afterwards.

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
face a fair question. This is the IUCr guidelines' own advice for a partial or
uncertain model {cite}`mccusker1999`.

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
  although Rwp is fine". Read it every time. [](results.md) says what a
  diagnostic carries, beside the statistics it outranks.
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
[](results.md) goes through the rest of the object field by field — the
structure R-factors, the bonding geometry, and the two counts that say whether
the pattern supported the model.

**Rwp is not the answer.** It is a fit statistic, and this package can show you a
fit whose Rwp improved while its displacement parameters and phase fractions
moved *away* from the truth. What the package hands you instead is
[the report](report.md).

## Your own data

The script above builds its structure and instrument in code, which is the
shortest way to show a whole fit. [](data.md) is the reference for doing that
with your own experiment: what each field of `PatternData`, `Structure` and
`Instrument` means, which of the three instrument presets matches your
diffractometer, and how to calibrate one on a standard and reuse it.
[](files.md) is the same ground from the file side, for data you already have on
disk.

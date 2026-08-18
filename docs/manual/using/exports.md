# Exports and derived tables

A finished fit holds more than its refined parameters. The calculated pattern,
the reflection list behind it and the tick positions drawn under it are all
functions of the converged state, and the package will compute any of them on
request. This chapter is those derived quantities and the files they become.
Where each file lands, and the rest of the on-disk map, is [](files.md).

## The calculated pattern

`RefinementResult` carries the curves of the fit itself: `RefinementResult.y_obs`,
`RefinementResult.y_calc` and `RefinementResult.y_background` on
`RefinementResult.two_theta`. Two more belong with them.

`RefinementResult.sigma` is the per-point σ the fit divided by, copied verbatim
from the pattern at stage compile. `RefinementResult.sig` is the method to call
rather than the field to read: it is **the one authority** for σ, and every
weighted residual in the package — the static plot, the interactive page, the
report's Layer 0, the GUI's own window — goes through it. Two conditioning steps
are the reason it is a method. A result recorded before v0.2 carries no σ at all
and gets the Poisson √max(y,1) fallback the fit itself would have used, and
non-positive entries are floored, so a zero esd becomes a small σ rather than an
infinity that would lose the whole trace.

`RefinementResult.sig` says nothing about **where** σ came from. By the time a
result exists, a file's esd column and a Poisson estimate are the same array of
floats. `DataRef.has_sigma` is the fact that survives, and it is what a plot
axis and the text document are labelled from ([](files.md)).

`RefinementResult.ticks` maps a phase name to its reflection positions in
degrees 2θ. **It covers every emission line, not only the primary one.** The
calculated pattern really does have a peak at each Kα₂ position, and a tick list
that omitted them would make the report flag every Kα₂ peak as an unindexed
impurity — which it once did.

`Refinement.predict` evaluates y_calc at the fitted parameters. With no argument
it uses the fit grid. Given an array of 2θ values it compiles a fresh model on
that grid, so it will extrapolate beyond the fitted range or resample inside it;
in Le Bail mode the extracted intensities are carried over by hkl.

<!-- api-doc: no-exec — needs a converged refinement -->
```python
import numpy as np

fine = np.arange(10.0, 90.0, 0.001)
y = refinement.predict(fine)
```

## The reflection list

`Refinement.reflection_table` returns one row per **(emission line,
reflection)** of every phase — not one row per reflection. `reflection_table` is
the same table as a function, taking the compiled model, the decoded parameter
values and the structure, for a caller that has those rather than a
`Refinement`.

`ReflectionRow` is one row.

| Field | Holds |
|---|---|
| `ReflectionRow.phase` | the phase name |
| `ReflectionRow.line` | which emission line, indexed from 0 |
| `ReflectionRow.wavelength` | that line's λ in Å |
| `ReflectionRow.h`, `ReflectionRow.k`, `ReflectionRow.l` | the Miller indices |
| `ReflectionRow.d` | the d-spacing in Å |
| `ReflectionRow.two_theta` | the **apparent** position, in degrees |
| `ReflectionRow.multiplicity` | the Laue-group multiplicity of the orbit |
| `ReflectionRow.f_squared` | \|F\|², or `None` in Le Bail and Pawley mode |
| `ReflectionRow.intensity` | the modelled integrated intensity of this row |

Three of those repay reading carefully.

`ReflectionRow.two_theta` is where the model **places** the peak — the Bragg
angle plus the zero shift plus the geometry's own position correction — so it
matches `RefinementResult.ticks` rather than the ideal Bragg angle. A reflection
whose 2θ is non-physical at a given line's wavelength (sin θ > 1) is dropped for
that line only, so a row missing from one line may be present in another.

`ReflectionRow.intensity` is the whole modelled contribution, not \|F\|²: in
Rietveld mode it is scale × multiplicity × \|F\|² × preferred orientation ×
line weight × Lp × extinction × absorption × roughness. It is what the peak
under the tick is made of.

`ReflectionRow.f_squared` is `None` in Le Bail and Pawley mode, where the
per-reflection intensity is extracted or refined rather than computed from the
structure. With anomalous scattering on — the default — it is the
**Friedel-averaged** ⟨|F|²⟩, not the representative reflection's own \|F(h)\|².
The two differ in a non-centrosymmetric group, both land in the same powder
peak, and only the average is observable in a powder.

## Writing them out

[](files.md) has the three writers that turn a result into a file, what each
file contains, and why the CIF carries a symmetry-operation loop of its own.
`Refinement` carries the same three as methods on the refinement that produced
the result, which saves passing the pieces back in: `Refinement.write_cif`,
`Refinement.write_reflection_table` and `Refinement.write_qpa_table`. Each takes
a path and passes any other keyword through, so
`refinement.write_reflection_table("refl.tsv")` picks a tab delimiter from the
suffix.

## Numbers with uncertainties

`format_su` writes a value and its esd in the crystallographic `value(su)`
notation {cite}`schwarzenbach1989`: the su carries **two significant figures**
and the value is quoted to exactly that precision.

```python
from rietx.io.exporters import format_su

assert format_su(4.593700, 2.5e-4) == "4.59370(25)"
assert format_su(123.4, 2.5) == "123.4(25)"
assert format_su(12345.0, 250.0) == "12340(250)"
```

`4.59370(25)`, not `4.593700(250)`: an esd of 2.5 × 10⁻⁴ says the sixth decimal
is not knowledge, so the esd sets the number of decimals and the `decimals`
argument governs only the case where there is none.

Three cases the function handles that a format string does not. An esd like
0.0999 rounds **up** to two figures as 100, which is renormalised to 0.10 and one
fewer decimal rather than written as a spurious three-figure `(100)`. An esd of
1 or more takes decimals off the value and keeps its own trailing magnitude, so
12345 ± 250 is `12340(250)`. And no esd at all — `None`, non-positive, or not
finite, which is a fixed parameter or one the fit could not estimate — writes
the plain number, never an implied uncertainty.

```python
from rietx.io.exporters import format_su

assert format_su(1.234567, 0.0999) == "1.23(10)"
assert format_su(4.5937, None) == "4.593700"
```

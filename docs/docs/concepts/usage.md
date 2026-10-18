# About the calls most fits use

A refinement in rietx usually needs seven calls: read the pattern, read the structure, build the instrument and its background, make a `Refinement`, fit, and plot.
Everything else in the API serves a particular task.

The tiers below count which rietx functions the seven tutorials and three worked examples call, out of ten scripts.
They count calls only, so reading a field such as `RefinementResult.statistics` does not appear, and neither does a result a notebook displays.
The [API reference](../reference/api.md) lists every name.

This is how the second tutorial makes the first six of the seven calls:

```{literalinclude} ../../../examples/tutorials/02_simple_rietveld.py
:language: python
:start-at: import rietx as rx
:end-before: print(result)
```

## Every fit

Seven or more of the ten scripts make these calls.

| Call | Scripts | What it does |
|---|---|---|
| `rx.Refinement` | 10 | holds the structure and instrument being refined |
| `Refinement.fit` | 9 | runs a plan of stages against a pattern |
| `rx.Structure.from_cif` | 9 | reads phases from a CIF |
| `rx.Instrument.bragg_brentano` | 8 | builds a flat-plate laboratory instrument |
| `rx.BackgroundChebyshev.with_terms` | 8 | builds a Chebyshev background with a given number of terms |
| `RefinementResult.plot` | 8 | draws the observed, calculated and difference curves |
| `rx.read_pattern` | 7 | reads a pattern file in any supported format |

## Often

Three or four of the ten make these calls.

| Call | Scripts | What it does |
|---|---|---|
| `RefinementResult.parameter` | 4 | returns one refined parameter with its esd |
| `PatternData.plot` | 4 | draws a pattern before any fit |
| `rx.diagnose` | 3 | checks a raw pattern before a fit for humps, air scatter and lines from a stray wavelength |
| `Refinement.summary` | 3 | says whether a fit is finished, and why |
| `Refinement.predict` | 3 | calculates the pattern from the current models without refining |
| `Refinement.checkout` | 3 | returns the model to an earlier node of its history |

## For a particular task

Two of the ten scripts make each of these calls, or one does.

| Task | Calls |
|---|---|
| Holding and tying parameters | `Refinement.hold`, `Refinement.set_values`, `Refinement.tie_equal` |
| Reading the history | `RefinementTree.summary` |
| Reading the report | `Refinement.report`, `rx.build_report` |
| Working in a project | `rx.Project.create`, `Project.save`, `Project.fit` |
| Choosing a background | `rx.auto_background` |
| A capillary instrument | `rx.Instrument.debye_scherrer` |
| An unknown cell | `rx.pick_peaks`, `rx.fit_peaks`, `rx.index_pattern` |
| Calibrating the instrument | `rx.save_instrument_profile`, `rx.load_instrument_profile` |
| A series of patterns | `rx.refine_sequential` |
| Exporting and drawing | `Refinement.fitted_structure`, `Refinement.write_cif`, `rietx.viz.render_structure`, `rietx.viz.write_html` |

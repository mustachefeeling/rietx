# Quickstart

Five executed notebooks teach the package on a laboratory pattern and on synthetic
ones.
Each runs in under a minute, and the data ships inside the package.
Read a notebook here with its outputs, or download it and run it yourself.
Its first code cell installs `rietx`.

The notebooks are written for people who drive `rietx` through an agent and need
to judge its work, so each one ends with a list of checks to make on an agent's
fit.
[](first-refinement.md) covers the same ground as a script, on a synchrotron
pattern with an impurity phase.

| Notebook | What it teaches | Download |
|---|---|---|
| [](tutorials/01_quickstart.ipynb) | Look at a pattern, check a model against it, fit the cell and peak shapes with Le Bail, and read the summary in order | {download}`01_quickstart.ipynb <tutorials/01_quickstart.ipynb>` |
| [](tutorials/02_simple_rietveld.ipynb) | A staged Rietveld refinement, two parameters the data cannot separate, ties, bond lengths and the history | {download}`02_simple_rietveld.ipynb <tutorials/02_simple_rietveld.ipynb>` |
| [](tutorials/03_peaks_indexing_lebail.ipynb) | Picking peaks, indexing with a narrowed search, why the indexer abstains, and checking a candidate cell with Le Bail | {download}`03_peaks_indexing_lebail.ipynb <tutorials/03_peaks_indexing_lebail.ipynb>` |
| [](tutorials/04_peak_shape_and_microstructure.ipynb) | Calibrating an instrument on a standard, then measuring crystallite size and strain against a known truth | {download}`04_peak_shape_and_microstructure.ipynb <tutorials/04_peak_shape_and_microstructure.ipynb>` |
| [](tutorials/05_sequential_fits.ipynb) | Fitting a heating ramp pattern by pattern, a parameter's trajectory, and what the series reports when one frame fails | {download}`05_sequential_fits.ipynb <tutorials/05_sequential_fits.ipynb>` |

Notebooks 01 and 02 fit fluorapatite from the GSAS-II `LabData` tutorial, a
laboratory Cu Kα pattern.
The other three build their patterns in the notebook, so each fit can be checked
against the values it was built from.

<!-- Guard note (WP-1916): tests/test_manual_api.py checks the names on this
page and never in the notebooks, so a rietx name in a notebook's markdown cell
goes unchecked.  Their code is covered, because tests/test_tutorials.py executes
every notebook.  docs/manual/conf.py copies the notebooks here from
examples/tutorials/ at build, and each is generated from the .py of its name. -->

```{toctree}
:hidden:

tutorials/01_quickstart
tutorials/02_simple_rietveld
tutorials/03_peaks_indexing_lebail
tutorials/04_peak_shape_and_microstructure
tutorials/05_sequential_fits
```

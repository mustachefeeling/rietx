# rietx tutorials

Executed notebooks that build a working picture of what rietx does with a powder pattern.
They are written for people who drive rietx through an agent and need to judge its work, and they serve anyone learning the package.
Each notebook ends with a list of checks to make on an agent's fit.

Every notebook runs after `pip install "rietx[viz]"` in a Jupyter kernel.
The data ships inside the package, so no download is needed.

| Notebook | What it teaches | Data and licence | Runtime |
|---|---|---|---|
| [`01_quickstart.ipynb`](01_quickstart.ipynb) | Look at a pattern, check a model against it before fitting, fit the cell and peak shapes with Le Bail, read the summary in order, keep the best pass | `FAP.XRA` and `fluorapatite.cif`, fluorapatite from the GSAS-II `LabData` tutorial (Argonne/APS tutorial data, U.S. Government work) | under 30 s |
| [`02_simple_rietveld.ipynb`](02_simple_rietveld.ipynb) | A staged Rietveld refinement: the plan's stages, the parameter table, two parameters the data cannot separate and holding one, tying three atoms' Biso, bond lengths, the history, a verdict for a declared deliverable | The same two files | under 30 s |

Runtimes were measured on an Apple M-series laptop, kernel start included.

## Not covered yet

- Background shapes and amorphous humps.
- Kβ lines and other contaminating wavelengths.
- A second phase: NAC's fluorite impurity and what the difference curve shows.
- Quantitative phase analysis.

## Adding a tutorial

Each notebook is generated from the script of the same name.
Edit the `.py`, never the `.ipynb`.

1. Write `NN_slug.py` in jupytext's percent format.
   `# %%` opens a code cell.
   `# %% [markdown]` opens a markdown cell, and each of its lines starts `# `.
   Put every import in the first code cell.
2. Build it with `python examples/tutorials/build.py NN_slug`.
   The build executes the notebook in a fresh kernel and refuses to write one that raised, printed to stderr, or printed your home directory.
3. Add its row to the table above.
4. Run `pytest tests/test_tutorials.py`.
   The tests find tutorials by file name, so none of them needs an edit.

Keep each notebook to a minute or less.
The test suite executes every notebook on every push.

Rebuild every notebook with `python examples/tutorials/build.py` when the package version changes.
`build.py --check` reports a notebook whose cells or version stamp have fallen behind its source.

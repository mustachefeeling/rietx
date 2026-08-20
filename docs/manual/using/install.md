# Installation

```sh
pip install rietx
```

## Requirements

Python 3.11 or newer, and five packages: `numpy`, `scipy`, `pydantic`, `gemmi`
and `spglib`.

That core install is a complete refinement package. It reads patterns and CIFs,
applies every correction, runs the whole staged refinement machinery, builds the
report, indexes an unknown cell, and keeps projects and history. Nothing in that
list is optional or lazily imported.

## Optional extras

No extra makes a refinement more accurate. Each one adds a rendering (plots,
HTML, the GUI), a second opinion on the Jacobian (the differentiable backends),
or the development toolchain.

Install an extra by naming it in brackets. Quote the argument, because `zsh`
reads bare brackets as a glob:

```sh
pip install "rietx[viz]"           # one extra
pip install "rietx[viz,jax]"       # several, comma-separated, no spaces
uv pip install -e ".[dev]"         # from a source checkout
```

| Extra | Installs | What it buys |
|---|---|---|
| `viz` | matplotlib, plotly | Plots. `RefinementResult.plot` and the report figures need matplotlib; `viz.html.write_html` writes the interactive plotly page. |
| `gui` | plotly | The refinement GUI, `rietx gui`. Plotly only: the built frontend is committed inside the package, so this extra never needs node. |
| `jax` | jax | The `backend="jax"` Jacobian (`jacfwd`, chunked). |
| `torch` | torch | **Experimental.** `backend="torch"` (CPU fp64) and `backend="torch-mps"` (Apple GPU, necessarily fp32). About 500 MB, and *slower* than numpy on this hardware. It buys an independent opinion in the Jacobian-agreement matrix, and the forward model as a differentiable layer. It does not buy speed. |
| `docs` | sphinx, myst-parser, sphinxcontrib-bibtex, furo | Builds this manual. |
| `dev` | the `docs` extra, pytest, pytest-xdist, hypothesis, matplotlib, plotly, ruff | The test suite. |

That is the whole list. Background estimation needs nothing installed: arPLS,
SNIP and the penalised spline are implemented in the core, the spline as penalty
rows inside the least squares rather than as a pre-subtraction. See
`auto_background`.

**Use the numpy backend.** `backend="numpy"` is the default and the only backend
a refinement needs. The others exist to hold the analytic Jacobian to an
independent account. An Apple-GPU refinement runs 46 to 182 times *slower* than
numpy, because the work is launch-latency-bound.

Precision is not the trade. A GPU backend may compute Jacobian columns in fp32,
but the residual used for the cost and the statistics, and the solve itself,
stay fp64 on the host.

## Checking an install

`rietx.__version__` is the version of the installed distribution — the same
string `capabilities().package_version` reports and every `Provenance`,
`TreeHeader` and `project.json` is stamped with, so a result and the package
that produced it can never disagree about it.

```python
import rietx

rietx.__version__
```

It reads `0.0.0+dev` when no distribution of that name is installed. That is a
checkout on `sys.path` ahead of its own install, and it is worth fixing before
you refine anything: the string travels into the provenance of every result.

Ask the package rather than a table that goes stale. `capabilities()` reports
the versions, the backends, the plans, the modes, the anodes, the pattern
formats it can open, and the feature flags. For each backend it reports whether
the optional dependency imports *here*:

```python
from rietx import capabilities

caps = capabilities()
caps.package_version
[backend.name for backend in caps.backends if backend.available]
[fmt.name for fmt in caps.reader_formats]
```

`Capabilities.backends` is the field that answers "did my `jax` extra take?".
Each `BackendCapability` carries `BackendCapability.available` (does it import
here), `BackendCapability.requires` (the distribution to install) and
`BackendCapability.experimental`. [](agents.md) covers the rest of the object.

## Installing from source

```sh
git clone https://github.com/yue-here/rietx
cd rietx
uv venv --python 3.12 && uv pip install -e ".[dev]"
```

Then run the suite. The fast selection is the unit and property tests. The full
selection adds the real-data acceptance suites, which refine certified standards
and take tens of minutes:

```sh
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"   # fast
.venv/bin/python -m pytest -n auto --dist loadgroup                 # everything
```

`--dist loadgroup` is not optional. It honours the marks that keep a shared
refinement fixture on one worker; plain `--dist load` silently refits. The suite
prints its own counts, and those counts depend on the extras installed: `jax` and
`torch` turn skips into passes.

## Validation and accuracy claims

[`docs/VALIDATION.md`](https://github.com/yue-here/rietx/blob/main/docs/VALIDATION.md)
tabulates every real-data assertion in the repository and says what each
tolerance is referenced to. It is generated from the suite, so it is the
accuracy claim, and nothing in this manual restates it.

Read it with its own opening rule in mind: judge a correction by what it
changed, never by ΔRwp. Of the eight corrections in v0.5, two provably cannot
move Rwp, one moves it the wrong way when it is right, and the two largest
accuracy wins are invisible in it.

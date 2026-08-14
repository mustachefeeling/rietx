# Installing

```sh
pip install rietx
```

Python 3.11 or newer. The core install is deliberately small — `numpy`,
`scipy`, `pydantic`, `gemmi`, `spglib` — and it is a complete refinement
package: reading patterns and CIFs, every correction, the whole staged
refinement machinery, the report, indexing, projects and history. Nothing in
that list is optional or lazily imported.

Everything past that is an extra, and none of them makes a refinement more
accurate. They add a *rendering* (plots, HTML, the GUI), a second opinion on
the Jacobian (the differentiable backends), or the development toolchain.

## Extras

| Extra | Installs | What it buys |
|---|---|---|
| `viz` | matplotlib, plotly | Plots. `RefinementResult.plot` and the report figures need matplotlib; `viz.html.write_html` writes the interactive plotly page. |
| `gui` | plotly | The refinement GUI, `rietx gui`. Plotly only: the built frontend is committed inside the package, so installing this never needs node. |
| `jax` | jax | The `backend="jax"` Jacobian (`jacfwd`, chunked). |
| `torch` | torch | **Experimental.** `backend="torch"` (CPU fp64) and `backend="torch-mps"` (Apple GPU, necessarily fp32). ~500 MB, and *slower* than numpy on this hardware — it buys an independent opinion in the Jacobian-agreement matrix, and the forward model as a differentiable layer, not speed. |
| `docs` | sphinx, myst-parser, sphinxcontrib-bibtex, furo | Builds this manual. |
| `dev` | the above `docs` extra, pytest, pytest-xdist, hypothesis, matplotlib, plotly, ruff | The test suite. |

`baselines` also exists and currently buys nothing: no module imports
`pybaselines`. The penalized-spline background is implemented in the package
itself, as penalty rows inside the least squares rather than as a
pre-subtraction — see `auto_background`.

**The numpy path is the default and the one to use.** `backend="numpy"` is
the only backend anyone running refinements needs; the others exist to hold
the analytic Jacobian to an independent account, and an Apple-GPU refinement
is 46–182× *slower* than numpy because the work is launch-latency-bound.
Precision is not the trade: a GPU backend may compute Jacobian columns in
fp32, but the residual used for cost and statistics, and the solve, stay fp64
on the host.

## What this build can actually do

Ask the package rather than a table that goes stale. `capabilities()` is one
call reporting the versions, the backends **with whether each optional
dependency imports here**, the plans, the modes, the anodes, the pattern
formats it can open, and the feature flags:

```python
from rietx import capabilities

caps = capabilities()
caps.package_version
[backend.name for backend in caps.backends if backend.available]
[fmt.name for fmt in caps.reader_formats]
```

`Capabilities.backends` is the field that answers "did my `jax` extra take?"
— each `BackendCapability` carries `BackendCapability.available` (does it
import *here*), `BackendCapability.requires` (the distribution to install) and
`BackendCapability.experimental`. The rest of the object, and the five
versioned contracts it reports, are in the chapter on driving the package
from a program.

## From source

```sh
git clone https://github.com/yue-here/rietx
cd rietx
uv venv --python 3.12 && uv pip install -e ".[dev]"
```

Then the suite. The fast selection is unit and property tests; the full one
adds the real-data acceptance suites, which refine certified standards and
take tens of minutes:

```sh
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"   # fast
.venv/bin/python -m pytest -n auto --dist loadgroup                 # everything
```

`--dist loadgroup` is not optional: it honours the marks that keep a shared
refinement fixture on one worker, and plain `--dist load` silently refits.
The suite prints its own counts, which depend on the extras installed —
`jax` and `torch` turn skips into passes.

## What the package is known to get right

Every real-data assertion in the repository, with what each tolerance is
referenced to, is tabulated in
[`docs/VALIDATION.md`](https://github.com/yue-here/rietx/blob/main/docs/VALIDATION.md).
That file is generated from the suite, so it is the accuracy claim; nothing
in this manual restates it. Read it with its own opening rule in mind: judge
a correction by what it changed, never by ΔRwp — of the eight corrections in
v0.5, two provably cannot move Rwp, one moves it the wrong way when it is
right, and the two largest accuracy wins are invisible in it.

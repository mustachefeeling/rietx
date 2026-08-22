# Installation

```sh
pip install rietx
```

## Requirements

Python 3.11 or newer, and six packages: `numpy`, `scipy`, `pydantic`, `gemmi`,
`spglib` and `numba`.

That core install is a complete refinement package. It reads patterns and CIFs,
applies every correction, runs the whole staged refinement machinery, builds the
report, indexes an unknown cell, and keeps projects and history. Nothing in that
list is optional or lazily imported.

`numba` is the odd one out: it is there for speed rather than for a feature, and
it is what makes a refinement about twice as fast on a multi-phase lab pattern.
{ref}`the-compiled-kernels` says what it costs, and how to run without it.

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

(the-compiled-kernels)=
## The compiled kernels

The peak profile, its derivatives and the accumulation that scatters them onto
the pattern are evaluated by compiled kernels rather than by numpy expressions.
They are on by default and there is nothing to install or select. Measured on a
four-phase Cu Kα refinement they take the fit from 17.6 s to 8.9 s; on a
three-phase one, from 4.2 s to 2.2 s; on a two-phase synchrotron pattern with no
axial divergence, from 0.54 s to 0.40 s.

This is why `numba` is a requirement and not an extra, and the shape is worth
stating plainly because it is the opposite of the extras above. An extra can
only ever *add* a dependency. There is no way to spell "install rietx with fewer
dependencies", so "fast by default, and still installable without the compiler"
cannot be a packaging choice at all. It is a code one:

- the import is soft, and every kernel has the numpy expression it replaces
  standing behind it, so an install that omits `numba` — `pip install rietx
  --no-deps` plus the other five, a constraint file, a distribution package —
  runs every refinement correctly, only slower;
- `RIETX_COMPILED=0` in the environment switches the tier off with no
  reinstall, for a machine where the compiler misbehaves or a run that must
  reproduce another one exactly.

`capabilities().features` answers both questions separately, because they can
disagree: `compiled_kernels` is whether `numba` imports here, and
`compiled_kernels_active` is whether the next refinement will use it.

```python
from rietx import capabilities

caps = capabilities()
caps.features["compiled_kernels"]
caps.features["compiled_kernels_active"]
```

Two costs, both deliberate. The install is about 2.3 times larger — `llvmlite`
is 137 MB of the 157 MB added, against a 124 MB baseline — and `numba` carries
an upper bound on `numpy`, so a very new numpy may have to wait for a `numba`
that admits it. Per-project virtual environments are the assumption that makes
both acceptable.

The first process on a machine pays a 0.6 s compile; every later one pays 0.12 s
to load the result from disk. Most of even that overlaps with other work: the
compile starts on a background thread when the model is compiled, and runs while
the file is read and the parameter table is built. The machine code is cached
under `~/.rietx/numba-cache`, or under `$RIETX_STATE_DIR` if that is set.

Numbers, not adjectives: the compiled and numpy paths agree to within one or two
units in the last place, everywhere and on every platform. The accumulation is
bit-for-bit identical — it is multiplication and addition in a fixed order, with
no library function in it. The peak shapes call `exp`, whose last bit belongs to
whichever library provides it, so they land on the same doubles on some
platforms and one part in 3e-17 away on others; peaks carrying the
axial-divergence correction differ by about 1e-16 on all of them, a different
summation order for the same quadrature. None of this is a different model, and
none of it is visible in a refined parameter or its esd.

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

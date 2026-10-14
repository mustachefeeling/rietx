# The tutorials in the browser (JupyterLite)

A JupyterLite site that runs the tutorial notebooks in a browser tab, on
Pyodide (CPython compiled to WebAssembly). Nothing is installed and no
account or server is needed. The kernel is a Web Worker in the reader's own
tab. Written 2026-10-14 with Claude Code (WP-1963).

## What is here

| path | what |
|---|---|
| `build_wheels.py` | `python build_wheels.py OUT` cross-compiles gemmi and spglib for the Pyodide the site loads. Pyodide ships neither, and PyPI has no WebAssembly wheel of either. It takes about five minutes and needs `uv`, `git`, `cmake` and `ninja` |
| `build.py` | `python build.py --wheels OUT` builds the site into `site/`. It takes the notebooks at the newest `vX.Y.Z` tag, through the same reader the landing page's Colab links use, and puts in each one a browser install cell instead of `%pip install rietx` |
| `smoke.mjs` | `PW=<playwright> node smoke.mjs site/` runs every notebook of a built site in headless Chromium and fails on any error output |
| `requirements.txt` | the JupyterLite pins for `build.py`. They move together with `build_wheels.PYODIDE` |

```sh
uv venv --python 3.12 /tmp/lite && uv pip install --python /tmp/lite/bin/python -r docs/lite/requirements.txt
python3 docs/lite/build_wheels.py docs/lite/wheels
/tmp/lite/bin/python docs/lite/build.py --wheels docs/lite/wheels
python3 -m http.server -d docs/lite/site 8000    # then open http://localhost:8000/notebooks/?path=01_quickstart.ipynb
```

To try a change before it is released, build a wheel and serve it from the
site: `uv build --wheel --out-dir dist .` then
`build.py --wheels docs/lite/wheels --ref HEAD --rietx-wheel dist/rietx-….whl`.

## Why rietx runs there at all

WP-1917 parked JupyterLite because `pip` refuses rietx in Pyodide. There were
four gaps, and none of them was a wall.

1. **`rietx-kernels` has no WebAssembly build.** Its import is soft
   (`model/compiled.py`), so rietx runs the numpy path. Only the resolver
   objects. The install cell gives micropip a mock of it with no modules, and
   sets `RIETX_COMPILED=0`, the switch the decline warning itself names.
2. **gemmi and spglib are not in Pyodide.** `build_wheels.py` builds them.
   Each needs a change a native build does not, and each change is written
   beside its package in `PACKAGES`.
3. **wasm32's index type is 32 bits**, and `np.repeat` refuses int64 counts
   there. One call did this, in `model.preferred_orientation.orbit_layout`,
   and every `summary()` reached it.
4. **JupyterLite's kernel replaces `fcntl` with an empty module**
   (`pyodide_kernel/mocks.py`). `import fcntl` succeeds and `fcntl.flock`
   raises `AttributeError`, so `Project.create` failed. The lock sites now
   import `flock` by name, which turns the mock into the `ImportError` they
   already read as Windows.

Gaps 3 and 4 were fixed in rietx (WP-1963), so a release older than that fix
fails in tutorials 02 and 06. That is why the Pages build serves a wheel built
from the same commit as its notebooks.

## Two rules for changing the package

Nothing in CI runs the browser, so these hold only if they are kept.

- A count or an index handed to numpy is `intp`, never a fixed int64.
- A POSIX primitive is imported by name (`from fcntl import flock`), never
  as a module whose attributes are read later.

`smoke.mjs` is the check. Run it after a change that touches either.

## The numbers, 2026-10-14

Measured in a Linux cloud container (4 cores) with headless Chromium. Pyodide
was served locally, rietx from the site, and nothing else was running. Every
tutorial ran to the end with no error output. The printed numbers in 01 match
the committed notebook digit for digit. The table is in WP-1963's handover
entry.

## What it is not

- **Not the agent's tool.** An agent driving rietx runs it in a Python
  with the compiled kernels. This is a reader's door.
- **Not as fast as Colab.** Tutorial 02 took almost four minutes in the
  browser against half a minute natively. Most of that is the missing compiled
  kernels, since the native numpy path took 135 s. WebAssembly itself cost
  1.7-1.8×.
- **Files you upload stay in the browser** (IndexedDB), as JupyterLite keeps
  them. Notebook 06's text points at Colab's folder icon. JupyterLite's file
  browser has an upload button instead, and reading a pattern uploaded that
  way has not been tried.

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
three gaps, and none of them was a wall.

1. **`rietx-kernels` has no WebAssembly build.** Its import is soft
   (`model/compiled.py`), so rietx runs the numpy path. Only the resolver
   objects. The install cell gives micropip a mock of it with no modules, and
   sets `RIETX_COMPILED=0`, the switch the decline warning itself names.
2. **gemmi and spglib are not in Pyodide.** `build_wheels.py` builds them.
   Each needs a change a native build does not, and each change is written
   beside its package in `PACKAGES`.
3. **wasm32's index type is 32 bits**, and `np.repeat` refuses int64 counts
   there. One call did this, in `model.preferred_orientation.orbit_layout`,
   and every `summary()` reached it. The fix reaches PyPI with the next
   release. Until then, a site built at a tag older than the fix fails at
   `summary()` in tutorials 02 and 06.

## The numbers, 2026-10-14

These were measured in a Linux cloud container (4 cores) with headless
Chromium, Pyodide served locally, rietx served from the site, and nothing else
running. Every tutorial ran to the end with no error output. The printed
numbers in 01 match the committed notebook digit for digit.

The full table is in WP-1963's handover entry.

## What it is not

- **Not the agent's tool.** An agent driving rietx runs it in a Python
  with the compiled kernels. This is a reader's door.
- **Not a replacement for Colab on long fits.** The numpy path in WebAssembly
  is slower than native, and the slowest tutorial (02) feels it most.
- **Files you upload stay in the browser** (IndexedDB), as JupyterLite keeps
  them. Notebook 06 reads them from the file browser's upload button, where
  its text says Colab's folder icon.

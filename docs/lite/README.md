# The tutorials in the browser (JupyterLite)

A JupyterLite site that runs the tutorial notebooks in a browser tab, on
Pyodide (CPython compiled to WebAssembly). Nothing is installed and no
account or server is needed. The kernel is a Web Worker in the reader's own
tab. Written 2026-10-14 with Claude Code (WP-1966).

## What is here

| path | what |
|---|---|
| `build_wheels.py` | `python build_wheels.py OUT` cross-compiles gemmi, spglib and rietx-kernels for the Pyodide the site loads. Pyodide ships none of them and PyPI has no WebAssembly wheel of any. The kernels come from this checkout's `kernels/`. It takes about six minutes and needs `uv`, `git`, `cmake`, `ninja` and `rustup` |
| `build.py` | `python build.py --wheels OUT` builds the site into `site/`. It takes the notebooks at the newest `vX.Y.Z` tag, through the same reader the landing page's Colab links use, and puts in each one a browser install cell instead of `%pip install rietx`. The site follows the reader's light or dark setting when every figure carries a light and a dark image, and stays light when any figure is drawn on white alone, as at a tag cut before WP-1970. The build marks the outputs trusted, because JupyterLite strips the `<style>` that picks between the two images from an untrusted output |
| `smoke.mjs` | `PW=<playwright> node smoke.mjs site/` runs every notebook of a built site in headless Chromium. It fails on any raised error, an unrun cell, or a warning that the compiled kernels did not load, and prints other stderr without failing |
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

1. **`rietx-kernels` had no WebAssembly build.** The crate cross-compiles
   unchanged: it starts no threads of its own, and its x86-only SLEEF code
   already had a libm fallback, the one the arm64 wheel uses. Pyodide's CPython
   has no threads, so `compiled.n_threads()` answers 1 there and the kernels
   run on the caller. Under Pyodide, `tests/test_compiled_kernels.py` passes
   22 and skips 1. The three it fails start threads, or assert a thread count
   above one.
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

Gaps 3 and 4, and the thread count, were fixed in rietx (WP-1966), so a
release older than that fix fails in tutorials 02 and 06. That is why the
Pages build serves a wheel built from the same commit as its notebooks.

## Three rules for changing the package

Nothing in CI runs the browser, so these hold only if they are kept.

- A count or an index handed to numpy is `intp`, never a fixed int64.
- A POSIX primitive is imported by name (`from fcntl import flock`), never
  as a module whose attributes are read later.
- Nothing assumes a thread can start. The kernel pool asks `n_threads()`.

`smoke.mjs` is the check. Run it after a change that touches any of them.
The root CLAUDE.md states the same three rules, so a change to one changes both.

## The numbers, 2026-10-14

Measured in a Linux cloud container (4 cores) with headless Chromium. Pyodide
was served locally, rietx from the site, and nothing else was running. Every
tutorial ran to the end with no error output. The printed numbers in 01 match
the committed notebook digit for digit. The table is in WP-1966's handover
entry.

## What it is not

- **Not the agent's tool.** An agent driving rietx runs it in a Python
  with the compiled kernels. This is a reader's door.
- **Not as fast as Colab.** Tutorial 02, the slowest, took 91 s in the
  browser against 31 s natively. It took 226 s before the kernels were built
  for WebAssembly. The rest are within about 30 s of native, most of that
  the install cell.
- **Files you upload stay in the browser** (IndexedDB), as JupyterLite keeps
  them. Notebook 06's text points at Colab's folder icon. JupyterLite's file
  browser has an upload button instead, and reading a pattern uploaded that
  way has not been tried.

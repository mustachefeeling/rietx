# WP-1963 — the tutorials run in the browser, in JupyterLite

Milestone: unscheduled · Status: 🔄 2026-10-14 — all six tutorials run in JupyterLite in headless Chromium; the site goes to /lite/ on merge, which is the maintainer's call
Track: Render what the fit already knows
Depends on: —
Priority: P3 2026-10-14 — Colab covers it; a second door with no Google account and no server

## Goal

Every tutorial notebook runs live in a browser tab with nothing installed and
no account, as a JupyterLite site served beside the landing page. A build
script reproduces the site from the repository, including the two dependencies
Pyodide does not ship.

## Context

WP-1917 parked JupyterLite as a non-goal: "Pyodide has no `rietx-kernels`
wheel, so pip refuses rietx there". That is one of four gaps, and none is a
wall.

- **`rietx-kernels`**: no WebAssembly build. Its import is already soft
  (`model/compiled.py`, `_load`), so rietx runs its numpy path. Only the
  *resolver* refuses, and micropip's `add_mock_package(..., modules={})`
  records the distribution without creating a module. `RIETX_COMPILED=0`
  silences the decline warning, as the warning itself offers.
- **gemmi and spglib**: absent from Pyodide's distribution and with no
  wasm wheel on PyPI (checked 2026-10-14: gemmi 0.7.5, spglib 2.8.0). Both
  cross-compile with `pyodide-build` against the Pyodide JupyterLite pins.
  gemmi needs three changes: nanobind `<3` (its CMake asks for 2.4 under
  SameMajorVersion), `BUILD_GEMMI_PROGRAM=OFF`, and dummy `FE_*` macros,
  because a vendored `half.hpp` names floating-point exception flags wasm's
  libc lacks. It uses them only for CCP4 maps, which rietx never reads.
  spglib needs `SPGLIB_SHARED_LIBS=OFF`, or `_spglib.so` links a
  `libsymspg.so` Pyodide's loader cannot find.
- **wasm32's index type is 32 bits.** `np.repeat` casts its counts to
  `intp` under the 'safe' rule, so int64 counts raise there.
  `model.preferred_orientation.orbit_layout` did, and every `summary()`
  reached it through `report.texture`. The fit path itself is clean: every
  tutorial's fits ran.
- **JupyterLite's kernel empties `fcntl`** (`pyodide_kernel/mocks.py` puts
  a bare module in `sys.modules`). Plain Pyodide has `fcntl.flock`, so a
  Node run never sees this. `import fcntl` succeeds and `.flock` raises
  `AttributeError`, past every `except ImportError`. `Project.create`
  reached it through `history/store.py`. Importing `flock` by name turns
  the mock into the `ImportError` each lock site reads as Windows.

The Pyodide pin follows `jupyterlite-pyodide-kernel`: 0.8.6 loads Pyodide
314.0.6 (CPython 3.14.2, ABI `pyemscripten_2026_0`), and the two wheels must
match that ABI.

## Non-goals

- A WebAssembly build of `rietx-kernels`. PyO3 targets emscripten, but the
  kernels' thread pool has no threads there.
- A dependency marker (`rietx-kernels; sys_platform != "emscripten"`). It
  would remove the mock line, and `pyproject.toml`'s comment on the
  dependency rejects markers on purpose. That decision is the maintainer's.
- Upstreaming gemmi and spglib recipes to `pyodide-recipes`, which would put
  them on Pyodide's CDN and retire the build script.

## Tasks

- [x] `orbit_layout` passes its counts as `intp` (the one wasm32 failure).
- [x] The three `fcntl.flock` sites import it by name.
- [x] `docs/lite/build_wheels.py`: gemmi and spglib for the pinned Pyodide.
- [x] `docs/lite/build.py`: the six notebooks, each with a browser install
  cell in place of `%pip install rietx`, built into a JupyterLite site.
- [x] `docs/lite/smoke.mjs`: the site's six tutorials run in headless
  Chromium; `tests/test_lite.py` holds the projection and the `fcntl` mock.
- [x] The site at `/lite/` in `pages.yml`, a wheel from the same commit.
- [ ] The maintainer opens the site and decides whether it ships. If it
  does: a "Run in the browser" link per landing-page row, and the two
  `docs/lite/README.md` rules as a root CLAUDE.md bullet (the file is at
  its pinned cap, so that is a cap decision).
- [x] Skill: none. An agent driving rietx runs it in a Python with the
  kernels; this is a reader's door.

## Acceptance

```sh
python3 docs/lite/build_wheels.py docs/lite/wheels
<lite venv>/bin/python docs/lite/build.py --wheels docs/lite/wheels --ref HEAD --rietx-wheel <wheel>
PW=<playwright> node docs/lite/smoke.mjs docs/lite/site
.venv/bin/python -m pytest tests/test_lite.py
```

`smoke.mjs` prints `ok` for all six notebooks.

## References

- Pyodide 314.0.6 and `pyodide-build` 0.39.1; JupyterLite 0.8.6 with
  `jupyterlite-pyodide-kernel` 0.8.6.
- PEP 783 (the `pyemscripten` platform tag).

## Handover log

### 2026-10-14 — all six tutorials run in a browser tab

The tutorials now run in JupyterLite, in a browser tab, with nothing
installed and no account. All six run to the end in headless Chromium with
no error and no stderr, and 01's printed numbers match the committed notebook
digit for digit. WP-1917's reason for parking this was one of four gaps.
Two were packaging: gemmi and spglib had to be cross-compiled, and the
compiled kernels had to be skipped. The other two were real rietx bugs that
any 32-bit or JupyterLite user would have hit, and both are fixed here. What
it costs is speed. Without the compiled kernels the structure tutorial (02)
takes almost four minutes, and natively the kernels alone account for most
of that.

*Done.* `orbit_layout` passes `intp` counts. The three `flock` sites import
it by name. `docs/lite/`: `build_wheels.py` (reproduced both wheels from a
clean work directory), `build.py`, `smoke.mjs`, `requirements.txt`, README.
`tests/test_lite.py` covers the projection on every notebook, the mock's
version against rietx's `rietx-kernels` range, and the `fcntl` mock at all
three lock sites. The store guard was made to fail once against the old code,
which raises the browser's exact `AttributeError`. `pages.yml` builds the
site to `/lite/`, but that has not run in CI.

*Measured* (Linux cloud container, 4 cores, nothing else running; seconds).
"Browser" is the smoke run's cell time, which includes the install cell, with
Pyodide served locally. "Native" is `tests/test_tutorials.py`'s call time,
which includes a kernel start, in this worktree's `[dev]` venv.

| notebook | native, kernels | native, numpy path | browser |
|---|---|---|---|
| 01 quickstart | 11 | 11 | 37 |
| 02 simple Rietveld | 31 | 135 | 226 |
| 03 peaks, indexing | 58 | 60 | 106 |
| 04 peak shape | 7 | 9 | 37 |
| 05 sequential | 11 | 12 | 42 |
| 06 your own data | 11 | 16 | 50 |

WebAssembly costs 1.7-1.8× over the native numpy path where a notebook is
long enough to tell (02, 03). The rest of the gap is install and the
kernels. A first visit downloads about 55 MB: Pyodide core 13.5, its packages
33.4 (summed from the wheels the run loaded), and the site's gemmi, spglib
and rietx 6.8. The browser caches all of it. The site itself is 535 files,
28 MB. The `--wheels` build takes about five minutes on four cores.

*Gotchas.* Plain Pyodide in Node has `fcntl.flock`, so the `fcntl` bug shows
only under the JupyterLite kernel. Run `smoke.mjs`, not a Node harness. An
artifact cannot host the site: its sandbox blocks every outside fetch
(Pyodide's CDN, PyPI) and service workers. `smoke.mjs` behind a proxy needs
Playwright's forced loopback proxying switched off, which it does itself.
The kernel fetches `comm` from PyPI at start, so even a fully self-hosted
site needs PyPI.

*Next.* (1) The maintainer opens the site and decides whether it ships. A
local copy needs `python -m http.server` over the built `site/`. (2) If it
ships: the first `pages.yml` run on `main` is the CI check, then a "Run in
the browser" link beside each Colab link on the landing page. (3) If it
ships, the two `docs/lite/README.md` rules go into the root CLAUDE.md, at
the cost of raising its cap. (4) Optional speed: a single-threaded emscripten
build of `rietx-kernels` would take back most of 02's time.

- **2026-10-14** — created. No open WP owns it: 1917, which parked
  JupyterLite, is closed.

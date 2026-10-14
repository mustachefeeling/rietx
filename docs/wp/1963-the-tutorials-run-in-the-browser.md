# WP-1963 — the tutorials run in the browser, in JupyterLite

Milestone: unscheduled · Status: 🔄 2026-10-14 — explored and working in a scratch build; the example site and its tooling on the branch
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
wheel, so pip refuses rietx there". That is one of three gaps, and none is a
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

- [ ] `orbit_layout` passes its counts as `intp` (the one wasm32 failure).
- [ ] `docs/lite/build_wheels.sh`: gemmi and spglib for the pinned Pyodide.
- [ ] `docs/lite/build.py`: the six notebooks, each with a browser install
  cell in place of `%pip install rietx`, built into a JupyterLite site.
- [ ] The site's six tutorials run in headless Chromium.
- [ ] An example page the maintainer can open.
- [ ] Skill: none. An agent driving rietx runs it in a Python with the
  kernels; this is a reader's door.

## Acceptance

```sh
bash docs/lite/build_wheels.sh <out dir>
.venv/bin/python docs/lite/build.py --wheels <out dir>
```

and every tutorial's cells run in the built site without an error.

## References

- Pyodide 314.0.6 and `pyodide-build` 0.39.1; JupyterLite 0.8.6 with
  `jupyterlite-pyodide-kernel` 0.8.6.
- PEP 783 (the `pyemscripten` platform tag).

## Handover log

- **2026-10-14** — created. No open WP owns it: 1917, which parked
  JupyterLite, is closed.

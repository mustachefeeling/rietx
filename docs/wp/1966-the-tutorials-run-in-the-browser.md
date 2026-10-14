# WP-1966 — the tutorials run in the browser, in JupyterLite

Milestone: unscheduled · Status: ✅ 2026-10-14 — the site is live at /lite/, each landing-page row links it as
JupyterLite, and its three rules are in the root CLAUDE.md
Track: Render what the fit already knows
Depends on: —

## Goal

Every tutorial notebook runs live in a browser tab with nothing installed and
no account, as a JupyterLite site served beside the landing page. A build
script reproduces the site from the repository, including the two dependencies
Pyodide does not ship.

## Context

WP-1917 parked JupyterLite as a non-goal: "Pyodide has no `rietx-kernels`
wheel, so pip refuses rietx there". That is one of four gaps, and none is a
wall.

- **`rietx-kernels`**: no WebAssembly build, and no sdist to make one from.
  The crate cross-compiles unchanged with `pyodide-build` (maturin, the Rust
  1.93.0 toolchain Pyodide's cross-build environment names, the stock
  `wasm32-unknown-emscripten` target). It starts no threads of its own,
  and its x86-only SLEEF `exp` already falls back to Rust's `f64::exp`, as
  the arm64 wheel does. What did need a change was Python's side: Pyodide's
  CPython has no threads (`sys._emscripten_info.pthreads` is False), so
  `compiled.n_threads()` answers 1 there. Before the kernels were built,
  micropip's `add_mock_package(..., modules={})` let rietx install on its
  numpy path. That is the fallback if a kernel build ever breaks.
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

- Publishing the WebAssembly kernels to PyPI. The site builds them from
  `kernels/` at its own commit. A published `pyemscripten` wheel would be a
  second release artefact for `docs/RELEASING.md`.
- A dark theme. The site is pinned light because every notebook figure is
  drawn on white. Dark needs the figures drawn for it first, which WP-1970
  owns.
- Upstreaming gemmi and spglib recipes to `pyodide-recipes`, which would put
  them on Pyodide's CDN and retire most of the build script.

## Tasks

- [x] `orbit_layout` passes its counts as `intp` (the one wasm32 failure).
- [x] The three `fcntl.flock` sites import it by name.
- [x] `docs/lite/build_wheels.py`: gemmi and spglib for the pinned Pyodide.
- [x] rietx-kernels for the pinned Pyodide too, from `kernels/`, and
  `compiled.n_threads()` answers 1 where the platform has no threads.
- [x] The site's theme pinned to JupyterLab Light.
- [x] `docs/lite/build.py`: the six notebooks, each with a browser install
  cell in place of `%pip install rietx`, built into a JupyterLite site.
- [x] `docs/lite/smoke.mjs`: the site's six tutorials run in headless
  Chromium; `tests/test_lite.py` holds the projection and the `fcntl` mock.
- [x] The site at `/lite/` in `pages.yml`, a wheel from the same commit.
- [x] The maintainer opens the site and decides whether it ships. It
  does: a "JupyterLite" link per landing-page row, before Colab.
- [x] The `docs/lite/README.md` rules as a root CLAUDE.md bullet. There
  are three now, and the cap went from 978 to 983 lines.
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

### 2026-10-14 (5th session) — "Hands-on", and the dark-figures WP renumbered

The lead's first word now reads "Hands-on", at the maintainer's request.
Main filed WP-1967 to WP-1969 for issues #933 to #935 while this branch was
open. This branch had filed the dark-figures WP as WP-1967, so it is now
WP-1970. Commit e0fa96dc still carries the prefix `WP-1967:`, and that
commit belongs to WP-1970. The merge with main was clean, because the two
1967 rows sat in different sections of the generated index.

### 2026-10-14 (4th session) — the panel names JupyterLite, and the rules reach CLAUDE.md

The landing page now offers the browser copy first and calls it by its
name. Each tutorial row reads Read, JupyterLite, Colab, Download, and the
panel says both run live in the browser. The old label, Browser, did not say
how the link differs from Colab, because Colab runs in a browser too. The
three rules that keep rietx running under Pyodide are now in the root
CLAUDE.md, so a session changing the package meets them without opening
`docs/lite/`. That was the last task, and the WP closes. The maintainer's
question about dark-mode figures became WP-1970.

*Done.* The lead reads "Run them live in your browser with JupyterLite, or
on Colab." The maintainer gave that sentence and asked for a light polish.
"With" replaced "on" before JupyterLite, which runs inside the page. The row
link is `JupyterLite`, placed ahead of Colab in `notebook_rows`, and the
test, the landing README and the panel comment follow it. The name follows
scikit-learn's gallery, whose button says "launch lite" beside "launch
binder". The sentence tells a reader what it is. The CLAUDE.md bullet sits
after the compiled-tier rule and carries all three README rules. The task
named two, and the third (no assumed thread) came in the 2nd session. The
cap rose from 978 to 983 lines, logged in the test's diary and in
`process.md` § The caps diary. The lite README now says the root CLAUDE.md
states the same rules.

*Measured.* In Chromium at 375 px and 1280 px, in both themes, the four
links stay on one line with no horizontal scroll. The layout is the same as
before the rename. The fast selection gave 9713 passed, 187 skipped and
1 xfailed (`[dev]` venv, macOS arm64, CPython 3.12.10, no other suite
running at the start). Those are the 3rd session's counts exactly, as a
rename should leave them. The wall clock was 22:38 against that session's
3:38 on the same machine, so the machine was loaded by something else.
`added_test_times` lists the renamed case at 0.00 s. The full selection did
not run, because no measured number can move.

*Review* (`/code-review high --fix` over this session's range): no
correctness bug. It fixed two doc lines. The ticked task still named the
Browser link, and WP-1970's Priority line offered `style=` to
`render_structure`, which takes `background=`. It also found the cap
diary missing its 973 → 978 row of 2026-09-21. That row is restored from
the `SIZE_CAPS` comment that recorded the raise. Declined: the finding that
the lead sentence is public copy. The maintainer gave the sentence this
session.

*Dark mode.* The maintainer asked whether the notebook figures can follow a
dark theme. They can. A `text/html` output holds a light and a dark image,
with the dark one hidden by an inline style. A `<style>` keyed on the
frontend's dark marker swaps them. Where the `<style>` is stripped, as on
GitHub or in a notebook opened untrusted, the light figure shows. WP-1970
holds the frontend table read from source, the prior art and the costs,
about 0.25 s and 27 kB a figure. Its first task decides between drawing the
dark copy again and recolouring a copy. Today every pattern figure takes
`style="dark"` and `render_structure` a dark `background=`. The series
figure has no dark form. The Lite site stays pinned light until WP-1970
lifts the pin.

*Next.* Nothing remains in this WP. (1) WP-1970, when the maintainer wants
dark figures. (2) The lead's first sentence, "Hands on", is the
maintainer's copy and was left as written. As a compound adjective it is
usually hyphenated. (The 5th session hyphenated it.)

### 2026-10-14 (3rd session) — the landing page links the browser copy

A reader of rietx.org can now open any tutorial in the browser site
straight from the landing page, with no account. Each tutorial row has a
Browser link beside Colab. The browser copy comes from the latest commit on
`main` and the other links come from the release, so a tutorial renamed on
`main` before a release would leave its Browser link pointing at nothing.

*Done.* `build.LITE` is
`https://rietx.org/lite/notebooks/index.html?path=`, the URL form
`smoke.mjs` opens. `notebook_rows` puts the Browser link between Colab and
Download. `tests/test_landing.py` gains one case. It checks one Browser link
per notebook, `LITE` against `smoke.mjs`'s URL, and `pages.yml` still building
the site to `site/lite`. The row test now counts three mentions of each
notebook's file name. The landing README, the panel comment and the CSS
comment name the Browser link as the one exception to the tag rule.

*Measured.* All six notebooks and `notebooks/index.html?path=01_quickstart.ipynb`
answered 200 on the live site. In Chromium at 375 px the four links fit on
their own line under the title, in both themes, with no horizontal scroll. At
1280 px they fit beside the title. The fast selection gave 9713 passed,
187 skipped and 1 xfailed in 3:38 (`[dev]` venv, macOS arm64, nothing else
running). main's baseline was not measured, so the +1 is the new case's own
count, not a measured delta. `added_test_times` puts the new case at 0.00 s.
The full selection did not run, because no measured number can move.

*Review* (`/code-review high --fix`): seven findings, four fixed in one
commit (the three comments and the test above). Three were declined. (1) No
build check that each Browser link's name still exists at `HEAD`. The landing
build could check this, since both builds run in one `pages.yml` checkout and
`notebooks("HEAD")` is available. But the check would have to drop a link
silently or fail the whole site deploy, for a rename that fixes itself at the
next tag. (2) The panel's lead sentence is the maintainer's copy, left as
written. It still says to choose Colab to run the tutorials in the browser.
(3) `nb.name` goes into the query unencoded. The Colab and Download links are
unencoded in the same way, and none of today's six names needs encoding.

*Next.* (1) The maintainer rewords the lead sentence if they want it to name
the Browser option. (2) The two `docs/lite/README.md` rules go into the root
CLAUDE.md, which is a cap decision. That is the last open task, and it closes
the WP.

### 2026-10-14 (2nd session) — the compiled kernels run in the browser too

rietx's compiled kernels now run in the browser, so the browser copy is no
longer stuck on the slow path. The Rust crate cross-compiled to WebAssembly
without a single change. Under Pyodide it passes the same agreement tests the
native wheels do. The slowest tutorial (02) went from 226 s to 91 s, against
31 s natively. The site is also pinned to the light theme, and stays light
when the reader's system asks for dark, because every figure in the notebooks
is drawn on white.

*Done.* `build_wheels.py` builds rietx-kernels from `kernels/` with the Rust
toolchain the cross-build environment names (`pyodide config get
rust_toolchain`, 1.93.0) and installs it through `rustup`. The crate is
copied first, so `target/` stays out of the checkout. `compiled.n_threads()`
answers 1 where `sys._emscripten_info.pthreads` is False, with a native test
that patches `_CAN_THREAD`. The install cell lost its mock and
`RIETX_COMPILED=0`, and `build.py` refuses a site whose kernels the installed
rietx's own requirement would not accept. `SETTINGS` pins JupyterLab Light
with `adaptive-theme` off, through `--settings-overrides`. `pages.yml` keys
the wheel cache on `kernels/Cargo.*` and `kernels/src/**` too.

*Measured* (same machine and conditions as the table below, nothing else
running; seconds of cell time in the browser):

| notebook | numpy path in the browser | kernels in the browser | native, kernels |
|---|---|---|---|
| 01 | 37 | 39 | 11 |
| 02 | 226 | 91 | 31 |
| 03 | 106 | 101 | 58 |
| 04 | 37 | 31 | 7 |
| 05 | 42 | 37 | 11 |
| 06 | 50 | 41 | 11 |

Under Pyodide in Node, with the four wasm wheels, `tests/test_compiled_kernels.py`
passed 22 and skipped 1 (the x86-only FCJ build check), with three deselected.
Those three fail by construction there: two start threads, and one asserts
that a count of 4 is honoured. The kernels wheel is 0.13 MB, and
`build_wheels.py` runs in about six minutes from cold. With the OS asking for
dark, the built site's body reported `JupyterLab Light`.
Natively, `tests/test_compiled_kernels.py` gives 27 passed (+1),
`tests/test_lite.py` 13 passed and 1 skipped (`[dev]`, CPython 3.12.3, Linux
x86-64). The full fast selection was not rerun after this round. The one
`src/` change returns what it returned before on every platform with threads.

*Answers given to the maintainer.* Notebook parity with Colab: Colab opens
v1.9.0's notebooks and installs 1.9.0, and `/lite/` opens `main`'s with a
wheel from `main`. Their tutorial sources are identical today (`git diff
v1.9.0 HEAD -- 'examples/tutorials/*.py'` is empty). Their outputs differ in
version stamps and in one wall-clock-dependent indexing note in 03. The repo
gains scripts only: wheels, site and toolchain are gitignored and built in
CI, and the wheel cache holds about 2 MB.

*Review* (`/code-review high --fix` over the whole branch, before the PR):
ten findings. Five were fixed. `smoke.mjs` now fails a notebook whose stderr
says the compiled kernels did not load. Before this, a broken kernel wheel
would have passed on the numpy path. The wheel cache keys on `kernels/**`,
the path `kernels.yml` rebuilds on. It is restored and saved as two steps, so
a run cancelled after the build still keeps the wheels. The two dist-name
literals come from `_about`. `build.py` builds beside the old site and swaps
it in, so a failed build leaves the old site standing. I removed the two
`test_lite.py` tests the review showed could not fail, since each compared a
constant with a copy of itself, so the file is 11 passed and 1 skipped.
Declined: one shared `flock` helper (three sites, each tested), a WASI
threads check (no WASI target exists), and making the Lite steps
`continue-on-error`. That last one is the maintainer's call, because it
decides whether a broken browser site blocks the manual's deploy. Today it
does.

*Renumbered.* This was filed as WP-1963. The same afternoon `main` filed
its own WP-1963 (a kernel over the pattern coordinates, #976) and took 1964
and 1965, so this WP is 1966. The branch's commits up to the merge of
`main` carry the old prefix, `WP-1963:`. The worktree and its local branch
are still named `wp1963-…`, and only the pushed branch name matters.

*Next.* Unchanged from the entry below, less item (4), which this did.

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

*Review* (`/code-review high --fix`): eight findings, all fixed in one commit.
`counts` is built as `intp` at the source. The mock's floor is now read from
the rietx the site serves, with its patch digit kept (it had read the
working tree and dropped the patch digit). `build.py` refuses a missing
`--rietx-wheel` and an `--out` that is not a previous site, and takes the
dist and env names from `_about`. The kernel pin is checked against
`requirements.txt` without JupyterLite installed. `smoke.mjs`'s path check
carries a separator, and `pages.yml` runs `apt-get update`. One minor finding
was dropped: `notebooks(ref)` is called twice, but it is cached. After
the fixes, the six notebooks were rebuilt and smoke-run on the final tree.
All six passed, each within 6 s of the table below.

*Tests* (`[dev]` venv, CPython 3.12.3, Linux x86-64, 4 cores, alone). The
fast selection gave 9700 passed, 198 skipped, 1 xfailed and 1 failed in
21:52. The failure was this branch's: `test_portability` requires every
write handle to name `newline=`, and a `test_lite.py` handle did not. It is
fixed, and that file and `test_lite.py` pass on a rerun. `test_lite.py` adds
13 cases, 12 passing and 1 skipping (the kernel-pin check against an
installed `jupyterlite_pyodide_kernel`), 0.03 s in all. The baseline on
`main` was not measured, so the +13 is the file's count and not a measured
delta. The full selection did not run: the two `src/` changes are
value-identical on every 64-bit platform, so neither can move a measured
number.

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

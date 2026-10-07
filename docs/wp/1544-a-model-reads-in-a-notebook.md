# WP-1544 — a model reads in a notebook

Milestone: unscheduled · Status: ✅ 2026-10-07 — objects print as trees and views, figures show in a notebook, pre-fit ticks (PR #810)
Track: Render what the fit already knows
Depends on: —

## Goal

Every rietx object a person or an agent looks at prints as something readable.
That holds in a terminal, in `print()`, in a traceback and in a Jupyter cell.
The library's plotting functions behave inside a notebook.

## Context

**The trigger.** A friend's public demo notebook (LLongley94/rietx_demo,
`example_bim.ipynb`) drives rietx from Jupyter. Most of its cells print
pydantic one-liners. No rietx class defines a `_repr_*` hook. Measured on
`89c26036`:

| Object | What a cell or `print` shows |
|---|---|
| `PatternData`, 48k points (FAP: 5.7k) | 1 405 370 chars (FAP: 79 607) |
| `RefinementResult` | 809 339 chars of repr; `print` gives the designed view (`schemas/results.py:1413`) |
| `Instrument` / `Structure` | 2 727 / 2 600-char nested one-liner |
| `rx.diagnose(...)` | 743-char one-liner |
| `ref.parameters()` | 36 `ParameterRow` one-liners of ~300 chars |
| `FitReport` / `capabilities()` | 26.6k / 21k chars |
| `Refinement` | `<rietx.refine.Refinement object at 0x…>` |

**`print()` is no workaround.** Pydantic 2.13's `BaseModel.__str__` is
`__repr_str__(' ')`, so `str(data)` is the same 79 590 chars as its repr. So
is the friend's `for k, v in instrument: print(v)` habit. The fix therefore
sits in `Base.__repr_args__` (`schemas/common.py:415`), one rank below
Jupyter's hooks. Nothing in `src` parses a model's repr.

**Text is the authority, and HTML is a projection of it.** Agents read
stdout, and WP-1302's termination views are `__str__` methods
(`schemas/results.py:1413`, `schemas/sequential.py:1061`). A single
`_repr_pretty_` on `Base` that returns `str(self)` hands every designed
`__str__` to IPython.

**Three rules for anything that renders an object.**
- **A display reads fields and never computes.** IPython builds text/plain
  and text/html on every display. `Refinement.summary()` builds a report
  (`refine.py:4831`), and layer 2 runs rival fits, so a repr calling it would
  run fits twice per displayed cell. The telemetry rule records one report
  build writing four run directories.
- **No glosses.** A display never says what a name *is*. It prints the field
  name, or `help.py`'s `HelpEntry.label` where an arm exists (WP-1202).
- **No colour of its own.** HTML uses semantic tags only, with no `<style>`
  and no inline colour. JupyterLab's and GitHub's sanitisers strip styles, and
  a colour here would be a fourth surface beside `viz/theme.py`'s three.

**Matplotlib in a notebook.** `matplotlib.use("Agg", force=False)` runs at
`viz/plots.py:305,862,971` and `viz/indexing.py:59`. On matplotlib 3.11 it
does one of two things. With pyplot already imported it calls
`plt.switch_backend("Agg")`, which may take a live notebook off its inline
backend. Without pyplot it sets `rcParams['backend']`, which may stop the
inline figure formatter from ever loading. Both branches set
`backend_fallback=False` for the process. Neither effect is measured yet,
because IPython was not in the venv. The GUI server and the CLI need Agg,
since a GUI backend off the main thread fails on macOS.

**`rx.diagnose` is fit to show from v1.6.0.** WP-1442 took the demo's Kβ
flags from 34 to 0. Its census moved from 292 to 197 between WP-1415's filing
and its fix, and WP-1415 removed the census's σ-scale dependence. `n_peaks`,
`peak_density_per_deg` and `peak_fraction` are still not counts a reader
should quote. `docs/manual/using/results.md:431-445` still glosses them the
old way: it says seventeen fields where there are eighteen, and claims that
`peak_density_per_deg` feeds the background defaults, though nothing in `src`
reads it. `background/diagnostics.py:614-618` says "dense patterns (≳2/deg)
favour stiff baselines", which needs checking against what the code does.

**The data-only plot exists.** `data.plot()` forwards to
`rx.viz.plot_pattern` (`viz/plots.py:723`), documented in `using/data.md`.
The missing piece is a pre-fit overlay of the model's reflection ticks. It
answers SKILL §1's "is the cell within about 1 % and is λ right?" before any
fit. `viz/snapshot.stage_ticks` already builds ticks from a compiled model.

**Baseline, measured 2026-10-07 in a real kernel** (ipykernel 7.4.0,
IPython 9.17.1, matplotlib 3.11.2, nbclient 0.11.0, macOS; FAP data and
`examples/fap_lab.py`'s fit). Sizes are the cell's text/plain output in
characters. No object produced any text/html.

| Cell | Output |
|---|---|
| `data` | 79 607 |
| `instrument` / `structure` | 2 988 / 6 781 |
| `rx.diagnose(data, wavelength=1.5406)` | 500 |
| `result` | 495 796 |
| `ref.parameters()` | 19 473 |
| `ref` | 40 (`<rietx.refine.Refinement object at 0x…>`) |
| `print(data)` / `print(instrument)` | 79 591 / 2 972 |

**No rietx plot shows an image in a kernel, in either import order.**
`result.plot()` as a cell's last line displays only its 35-character text,
`<Figure size … with 1 Axes>`. `fig = result.plot()` and `data.plot();` display
nothing. Afterwards `matplotlib.get_backend()` reads `Agg`, and a plain
`plt.plot([1, 2]); plt.show()` emits "FigureCanvasAgg is non-interactive, and
thus cannot be shown" with no image. That holds whether pyplot was imported
before the first rietx plot or not. One rietx plot call therefore disables
matplotlib for the rest of the session.

## Non-goals

- **No new public names.** An opt-in zoomable fit (`rx.viz.interactive`) was
  considered and cut. It would add API, it dies in an untrusted notebook, and
  it puts 275 KB into every committed output. A live session can already use
  `write_html` with `IPython.display.IFrame`. A `ParameterRows` list subclass
  was cut too: once item reprs are short, IPython's list printer is readable.
- **No widgets.** `DESIGN.md` keeps notebook widgets fenced until v2, and
  that covers drag-editing peaks and a live fit view.
- **No designed views yet** for `FitReport`, `ExtinctionScreen` or
  `Capabilities`. No history picture and no correlation-matrix plot. Each one
  is built when a WP-1545 notebook needs it.
- **`__repr__` stays pydantic's**, apart from the elision. Only its long
  sequences change.

## Tasks

- [x] **Baseline probe.** Add a `notebooks` extra (`ipykernel`, `nbclient`,
  `nbformat`) that `[dev]` includes, after checking cp314 wheels for pyzmq and
  debugpy. Execute a scratchpad probe notebook with nbclient and record
  repr/str/text-plain sizes for every object in the table. Record matplotlib
  in both import orders: whether the image appears, appears once or twice, and
  whether a later `plt.plot(); plt.show()` still renders. Record the inline
  PNG size at `dpi=300`. The numbers go in this file's handover.
- [x] **`Base.__repr_args__` elision.** A list, tuple or array longer than
  eight items renders as a count and a range (`<5753 floats 15.0…130.04>`), or
  as a count and a type for a list of models (`<212 Reflection>`).
- [x] **A text tree for nested models.** `Base.__str__` becomes an indented
  field tree, one line per `Parameter`: value(esd) through
  `crystallography.cif.format_su`, unit through `help.UNIT_DISPLAY`, vary and
  bounds. `Base._repr_pretty_` returns `str(self)`. First grep `src` for
  `str(model)` and f-string uses whose text a message or test depends on.
- [x] **Designed text views** where a tree is the wrong shape, reading fields
  only. `PatternData`: points, range, step, σ source, excluded regions,
  metadata. `PatternDiagnostics`: fields in its docstring's reading order.
  `IndexingResult`: `cli._print_index` (`cli.py:342-383`) moves here, and the
  CLI prints `str(result)`. `Refinement`: phases, mode, free count, last
  status, history head and the parameter table. `RefinementTree`: `summary()`.
  `StructureFigure`: `_repr_png_` from its RGBA array.
- [x] **HTML projection for tables only.** `_repr_html_` on the result's
  parameter and diagnostic rows, `Refinement`'s parameter table and
  `IndexingResult`'s candidates. One row builder feeds both renderers, in a
  private `src/rietx/_display.py`.
- [x] **Matplotlib in a kernel**, as the probe dictates. Skip `matplotlib.use`
  when a kernel is running or a backend is already resolved, and keep Agg for
  the GUI and CLI. One plot call gives one image. `fig.dpi` does not change
  silently.
- [x] **Pre-fit ticks.** `plot_pattern(data, model=ref)` and
  `data.plot(model=ref)` draw the reflection ticks of a `Refinement` from
  `stage_ticks`, before any fit.
- [x] **Docs.** Fix `results.md:431-445` and the `diagnostics.py` docstring.
  Add a short section on reading objects in a notebook or terminal to
  `using/results.md`. Document `model=` in `using/data.md`. Add a
  compatibility note for the changed `__str__` text and the backend change.
  Add the three display rules to the root CLAUDE.md Conventions.
- [x] **Tests** (`tests/test_display.py`). The repr and str of every object in
  the table stay under a ceiling on real fixtures. The tree renders for
  `Instrument` and `Structure`. HTML escapes `<`. Displaying a fitted
  `Refinement` writes no run and runs no fit. With IPython installed, the
  `DisplayFormatter`'s text/plain stays under the ceiling. The CLI's `index`
  output is byte-identical after the move. (The last was checked once, against
  the old printer from git on two real indexing results. A suite test would
  need a whole indexing run.)
- [x] Skill: none. The cheapest place for this guidance is the package's own
  output (WP-1338), and that output is now readable: an agent that prints an
  object reads the tree with nothing extra to learn. The body is over budget.

## Acceptance

Every object in the Context table prints under a ceiling the tests set,
measured before and after in the handover. The probe notebook shows each plot
call's image exactly once in both import orders.

```sh
.venv/bin/python -m pytest tests/test_display.py tests/test_manual_api.py -q
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

## References

- IPython rich display protocol: `_repr_pretty_`, `_repr_html_`, `_repr_png_`
  (IPython documentation, "Rich output").
- Pydantic v2 `BaseModel.__repr_args__`.

## Handover log

### 2026-10-07 — closed: objects print readably, and figures show in a notebook

A rietx object can now be printed or shown in a notebook cell and read. A
pattern used to print every channel, a result most of a megabyte, and a model
one long line. Now each prints as a short tree or a designed view, and the
same text reaches a terminal, a log and an agent's transcript. The larger find
was in plotting. Measured in a real kernel, no rietx figure had ever shown an
image in Jupyter, and the first plot call disabled matplotlib for the rest of
the session. That is fixed and pinned by a test that runs a kernel.
`data.plot(model=ref)` now draws a model's reflection ticks before any fit.
That gives the tutorials (WP-1545) a "does my cell match my data" step.

**Done** (commits `26e43f27` … `4ab33fdb` on `wp1544-notebook-display`):
- `Base.__repr_args__` elides any long sequence. `Base.__str__` is a field
  tree. `Base._repr_pretty_` hands `str` to IPython.
- Designed `__str__` views for `PatternData`, `PatternDiagnostics` (stated
  reading order, `_READING_ORDER`), `IndexingResult` (the CLI printer moved
  here), `ParameterRow`, `Refinement`, `RefinementTree`. `StructureFigure` got
  `_repr_png_` and a short repr.
- HTML tables for the result's parameters, `Refinement`'s varying rows and
  `IndexingResult`'s candidates (`_display.py`, private).
- `viz.plots._pyplot`: Agg is forced except in a Jupyter kernel.
  `_handed_back` detaches a returned figure from pyplot on the inline backend.
- `plot_pattern(..., model=)`, using `stage_ticks` on a model compiled as
  `predict` compiles.
- Docs: `results.md` gets a notebook section and a corrected `diagnose`
  table. `data.md` documents `model=`. The 1.7.0 notes are staged, and root
  CLAUDE.md has one bullet.
- A `notebooks` extra (`ipykernel`, `nbclient`, `nbformat`) is in `[dev]`.

**Measured** (macOS arm64, `[dev,notebooks]` venv; ipykernel 7.4.0, IPython
9.17.1, matplotlib 3.11.2). Text/plain sizes in a kernel, before → after: `data`
79 607 → 191; `instrument` 2 988 → 748; `structure` 6 781 → 1 117; `diagnose`
500 → 448; `result` 495 796 → 2 497 (plus 6 015 of HTML); `ref.parameters()`
19 473 → 3 484. Figures per cell after the fix: a bare plot 1 (was 0 before
the fix, 2 when Agg was simply dropped); `;` 0; `fig = …` 0; a later
`plt.show()` 1, with the backend still inline. A rietx figure at `dpi=300`
embeds a 259 kB PNG. `IndexingResult.__str__` equals the old CLI printer byte
for byte on a validated and an unvalidated silicon search. Fast suite
`-m "not slow"`: 8594 passed, 167 skipped, 1 failed. passed+skipped+failed is
8762, +25 on `origin/main`, all of them `tests/test_display.py`. Another
pytest process was running, so its wall time is not quoted. The added tests
cost 4.29 s over 25 cases on that run. The tail is the kernel test at 3.19 s,
and it stays in the fast tier: it is the only guard of the notebook plotting
bug, and per-push execution is its value. No full suite was run, because
nothing here moves a measured number.

**Review** (`/code-review high --fix`): 10 findings, 6 acted on.
- Five were fixed by the pass: a dict of model lists printed `None`; a nested
  label doubled its colon; a nested designed view was bypassed; the vary count
  included held and mode-fixed rows; `plot_indexing`'s figures were never drawn
  in a notebook.
- One was a skip I reversed: leaving any resolved backend alone stopped
  forcing Agg in a script whose matplotlibrc names a GUI backend. Agg is now
  forced everywhere but a kernel.
- Declined: `_model_ticks` keys by phase name, and a magnetic phase gets one
  row where `result.ticks` splits it. Both copy what `refine._build_result`
  does, so the class fix belongs there. Also declined: `Refinement`'s table is
  built twice per displayed cell (3.1 ms on FAP; a cache would go stale on
  `set_values`), and `IndexingResult`'s HTML formats candidates beside its
  text, which is cleanup only.

**Gotchas.**
- `tests/conftest.py` pins `MPLBACKEND=Agg` and a kernel inherits it, so the
  kernel test starts its kernel without it.
- `test_backend_shim.py::…[toy_anomalous]` fails on bare `main` in this venv
  (numpy 2.5.3, checked on `origin/main`'s source). It is already recorded in
  WPs 1418, 1534 and 1906.
- Under ipympl (`%matplotlib widget`) a returned figure is untested and may
  still show twice, because `_handed_back` recognises only `inline`.

**Next:** WP-1545, the tutorial notebooks. Its Context carries what this
session measured that it needs: the silicon indexing abstention, and the
259 kB-per-figure cost that decides whether the notebooks pass `dpi=`.

- **2026-10-07** — created. No open WP owns notebook display; the index has no
  row for notebooks, reprs or Jupyter. The plan had a fresh adversarial review
  before filing. That review moved the fix from Jupyter's hooks down to
  `__repr_args__`, and cut two new public names.
